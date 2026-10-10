"""The face kit on an assembled character (um/assemble.py build_character with face="kit", the clay look): the pack
head's own ears and nose flattened, its face skin given to the Head bone alone, the kit's face built from the recipe
character's `face_kit` picks and merged into two skinned meshes:

- `<id>_eyes`: the eye whites and pupils (one glossy material whose colour is the vertex colour EYE_RGB: white or
  pupil per face; not baked; the look keys), the part godot-check finds the eyes by;
- `<id>_face`: lids, brows, nose, mouth, teeth, ears and facial hair with every expression key (mouth, blink, ears),
  joined into the head by the clay pass (claylook.JOIN_INTO_HEAD) and baked into its atlas; its mask UV (brows (1, 0),
  facial hair (0, 1)) lets the game tint them.

The mouth cavity becomes clay (baked into the head atlas, not a surface of its own) and the eyes are one surface
(one_eye_material): the character stays within the contract's 8 surfaces. The ear state comes from the hair item
(kit.hair_flags); apply it after the bake (set_ears).
"""
import bpy
import numpy as np

from .. import facekit as fk
from .. import heads
from .. import clay as cl
from ..util import relink
from . import checks, kit
from .face import build_face, game_mesh, rigid_full_z

EYE_MATERIAL = "fb_eye"  # the eyes' one material (shared by every character)
EYE_RGB = "eye_rgb"  # its colour attribute (corner domain, linear float): kit.FIXED's white or pupil per face
EYE_PIECES = ("whites", "pupils")  # the pieces of the eyes object; every other piece goes into the face object
EAR_TUCK_X = 0.082  # the pack head's own ears flattened to this half-width (m) unless the recipe tucks them itself
RIGID_FRONT_Y = -0.07  # the face skin in front of this world y follows the Head bone alone (facekit.rigid_face_skin)
RIGID_BLEND_M = 0.03  # ... fading back to the pack's weights over this height below the kit's lowest point
# the pack nose pushed back into the face before the kit's nose is seated (heads.flatten_nose): the faces lab's
# params_r2.json "nose_flatten", on which every lab face was built (art #42: without it the kit's ball sat on the pack
# nose's tip and read as a forward cone); the mouth centre the box ends at is the kit's (LAYOUT eye_dz, eye_mouth)
NOSE_FLATTEN = {"half_w": 0.026, "side_x": 0.03, "top_dz": 0.012, "bottom_dz": 0.012, "bulge": 0.004, "fade": 0.012,
                "smooth": 30}


class KitHead:
    """The kit's view of an assembled character's head (the lab's lab_base.Head interface): id, arm, coll, parts
    (head, hair), x, eye_z(), skin material, worn hair item, headwear."""

    def __init__(self, cid, arm, parts, coll, eyes_at, hair_item, skin_mat):
        self.id, self.arm, self.coll = cid, arm, coll
        self.parts = {"head": parts["head"], "hair": parts.get("hair")}
        self.x = arm.matrix_world.translation.x + arm.data.bones["Head"].head_local.x
        self._ez = sum(v[2] for v in eyes_at.values()) / len(eyes_at)
        self.skin = skin_mat
        self.worn = hair_item
        self.headwear = None

    def eye_z(self):
        return self._ez


def _merge(face, names, name, coll):
    """game_mesh of the face's pieces in names (the others hidden meanwhile)."""
    shown = {k: o.hide_render for k, o in face.pieces.items()}
    for k, o in face.pieces.items():
        o.hide_render = k not in names or shown[k]
    o = game_mesh(face, name=name, coll=coll)
    for k, p in face.pieces.items():
        p.hide_render = shown[k]
    return o


def eye_material():
    """The eyes' one glossy material (the manager's call, 2026-10-10: one surface for the whites and the pupils): the
    base colour is the colour attribute EYE_RGB (glTF COLOR_0, which Godot's importer multiplies into the albedo), the
    roughness the white's (kit.GLOSS)."""
    mat = bpy.data.materials.get(EYE_MATERIAL)
    if mat is not None:
        return mat
    # the unlinked base colour and the viewport colour: the white (Workbench and blendfile's check read them)
    mat = cl.gloss(bpy.data.materials.new(EYE_MATERIAL), tuple(kit.FIXED["white"]), rough=kit.GLOSS["white"], spec=0.5)
    nt = mat.node_tree
    p = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    vc = nt.nodes.new("ShaderNodeVertexColor")
    vc.layer_name = EYE_RGB
    nt.links.new(vc.outputs["Color"], p.inputs["Base Color"])
    mat["base_from"] = "vertex_colour"  # materials.sync_principled leaves its base colour alone
    return mat


def one_eye_material(eyes):
    """Folds the eyes' white and pupil materials into eye_material(): every corner gets its face's old material colour
    (kit.FIXED) in the colour attribute EYE_RGB, then one material slot. Returns {old material: faces}."""
    me = eyes.data
    old = [s.material for s in eyes.material_slots]
    rgb = np.array([(*(kit.FIXED.get(m.name[3:]) if m and m.name.startswith("fb_") and m.name[3:] in kit.FIXED
                       else m.diffuse_color[:3]), 1.0) for m in old], np.float32)
    idx = np.zeros(len(me.polygons), np.int32)
    me.polygons.foreach_get("material_index", idx)
    tot = np.zeros(len(me.polygons), np.int32)
    me.polygons.foreach_get("loop_total", tot)
    col = me.color_attributes.get(EYE_RGB) or me.color_attributes.new(EYE_RGB, "FLOAT_COLOR", "CORNER")
    col.data.foreach_set("color", rgb[np.repeat(idx, tot)].ravel())
    me.polygons.foreach_set("material_index", np.zeros(len(me.polygons), np.int32))
    me.materials.clear()
    me.materials.append(eye_material())
    return {m.name: int((idx == i).sum()) for i, m in enumerate(old) if m}


def build(arm, parts, coll, rc, eyes_at, skin_mat):
    """Builds the kit face on parts["head"] (rest pose, at the origin, after the skin material is set). Returns
    ({"eyes": obj, "face": obj}, report)."""
    cid, g = rc["id"], rc["gender"]
    head = parts["head"]
    spec = rc.get("face_kit") or {}
    rep = {"kit": True}
    if not rc["head"].get("tuck_ears"):
        rep["pack_ears_tucked"] = {"x_max_m": EAR_TUCK_X, "vertices_moved": heads.tuck_ears(head, EAR_TUCK_X)}
    item = kit.hair_item(rc["hair"], g)
    picks = kit.picks_for(spec, g)
    h = KitHead(cid, arm, parts, coll, eyes_at, item, skin_mat)
    mouth_z = h.eye_z() + kit.LAYOUT["eye_dz"] - kit.LAYOUT["eye_mouth"]
    rep["pack_nose_flattened"] = heads.flatten_nose(head, h.x, h.eye_z(), mouth_z, **NOSE_FLATTEN)
    z_full = rigid_full_z(h)
    n, most = fk.rigid_face_skin(head, RIGID_FRONT_Y, z_full, z_full - RIGID_BLEND_M)
    rep["rigid_face_skin"] = {"z_full": round(z_full, 4), "vertices": n, "largest_change": round(most, 3)}
    skin = tuple(rc["skin"]) if rc.get("skin") else tuple(skin_mat.diffuse_color[:3])
    face = build_face(h, picks, skin, coll=coll, brow_colour=spec.get("brow_rgb"))
    # the check's numbers on this head (the 300+ check runs the same on many faces: faces --check)
    rep.update({"picks": picks, "hair_item": item, "flags": kit.hair_flags(item), "tris": face.meta["tris"],
                "tris_total": face.meta["tris_total"], "collisions": checks.collisions(face),
                "brow_in_white": checks.brow_in_white(face), "nose_meets_pupils": face.meta["nose"]["meets_pupils"],
                "layout": face.meta["layout"], "points_pulled_in": face.meta["points_pulled_in"]})
    cav = face.mats.get("cavity")
    if cav is not None and not cl.is_clay(cav):  # baked into the head atlas: one surface fewer
        cl.clay(cav, tuple(cav.diffuse_color[:3]))
    eyes = _merge(face, EYE_PIECES, cid + "_eyes", coll)
    rep["eye_material"] = {"name": EYE_MATERIAL, "faces": one_eye_material(eyes)}
    fo = _merge(face, [k for k in face.pieces if k not in EYE_PIECES], cid + "_face", coll)
    rep["mask_faces"] = face.meta.get("mask_faces")
    face.remove()
    for o in (eyes, fo):
        relink(o, coll)
    rep["objects"] = {"eyes": eyes.name, "face": fo.name}
    rep["keys"] = {k: [kb.name for kb in o.data.shape_keys.key_blocks[1:]] if o.data.shape_keys else []
                   for k, o in (("eyes", eyes), ("face", fo))}
    return {"eyes": eyes, "face": fo}, rep


def set_ears(obj, state):
    """The ear keys of the face (or the head it is joined into) as kit.EAR_KEYS[state]; returns the state."""
    sk = obj.data.shape_keys
    for k, v in kit.EAR_KEYS[state].items():
        kb = sk.key_blocks.get(k) if sk else None
        if kb is not None:
            kb.value = v
    return state
