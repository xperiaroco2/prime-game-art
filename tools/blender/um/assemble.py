"""build_character: one character from a recipe, on its body type's skeleton, measured in the rest pose; pose_character:
its recipe pose with the posed measurements; crossgender: the final test's clothing-across-body-types experiment.

A character is five pack parts from source characters of its own body type (a head stripped to bald skin, a hairstyle
split off another head, a top, a bottom and shoes; extras such as a moustache are more head regions), each rebound to
the skeleton file's rest pose and parented to its armature with an Armature modifier, plus our scripted eyes, brows and
mouth weighted 1.0 to the Head bone, and a toe bone per foot (um/toes.py; 64 bones in all). Objects are named
<id>_<slot>: head, hair, top, bottom, shoes, eyes, brows, mouth and the extras' roles.
"""

import json

import bpy
from mathutils import Vector

from . import facekit as fk
from . import fit, heads, jaw, poses, toes, zones
from .materials import color_of, set_color
from .packs import attach, discard, place, source_label
from .rebind import rebind
from .util import base_name, relink, tris, update, world_points


def check_styles(recipe):
    """Every eye, brow and mouth style the recipe names exists in the face kit; raises with the known styles."""
    problems = []
    known = {"eyes": fk.EYE_STYLES, "brows": tuple(fk.BROWS), "mouth": fk.MOUTH_STYLES}
    for rc in recipe["characters"]:
        for part, styles in known.items():
            if rc[part]["style"] not in styles:
                problems.append(f"characters[{rc['id']}].{part}.style: {rc[part]['style']!r} is not a face-kit style; "
                                f"it has: {', '.join(styles)}")
    if problems:
        raise ValueError("recipe: " + "; ".join(problems))


def take_part(packs, char_id, role, gender, spec, arm, keep=None, extra_report=None, drop_piece=None):
    gender = spec.get("gender", gender)  # a head item may come from the other body type's pack (same Head bone)
    src = packs.load(gender, spec["file"])
    obj = src["meshes"][spec["object"]]
    moved = rebind(obj, src["arm"], arm)
    attach(obj, arm)
    discard(src, keep=[obj])
    obj.name = "%s_%s" % (char_id, role)
    obj.data.name = obj.name
    update()
    info = {"file": source_label(gender, spec["file"]), "object": spec["object"], "rebind_max_move_m": round(moved, 4)}
    if keep is not None:
        info["faces_kept"] = heads.filter_faces(obj, arm, keep, drop_piece=drop_piece)
    if extra_report:
        info.update(extra_report)
    return obj, info


def build_character(packs, recipe, rc, coll, face="pack"):
    """Returns (armature, {role: object}, report) with the rig in its rest pose at the origin. face: "pack" (the
    scripted eyes, brows and mouth of um/facekit.py) or "kit" (the clay face kit, um/clayface: the eyes and face parts;
    the clay look)."""
    cid, g = rc["id"], rc["gender"]
    skel = packs.load(g, recipe["skeleton"][g])
    arm = skel["arm"]
    discard(skel, keep=[arm, skel["root"]])
    arm.name = cid + "_rig"; skel["root"].name = cid + "_root"
    for o in (arm, skel["root"]):
        relink(o, coll)
    arm.data.pose_position = "REST"
    update()
    hb = arm.matrix_world @ arm.data.bones["Head"].head_local
    assert (hb - Vector(recipe["head_bone_rest"])).length < 0.002, (
        "rig %s: Head bone rest %s is not the reference %s; the world-space constants would be wrong" % (cid, hb, recipe["head_bone_rest"]))
    parts, rep = {}, {"skeleton": source_label(g, recipe["skeleton"][g]) + " CharacterArmature", "parts": {}}

    # head: keep only skin; note the eye spots first
    hs = rc["head"]
    head, info = take_part(packs, cid, "head", g, hs, arm)
    eyes_at = heads.eye_centres(head, arm, hs["eye_materials"])
    keepset = set(hs["keep"]) | set(hs.get("as_skin", []))
    hcuts = [zones.CUT_ZONES[z] for z in hs.get("cut", [])]
    info["faces_kept"] = heads.filter_faces(head, arm, lambda m, c: m in keepset and not any(z(c) for z in hcuts))
    if hcuts:
        info["cut"] = hs["cut"]
    info["materials"] = "kept " + ", ".join(sorted(keepset)) + " (bald, no eyes, brows or facial hair)"
    if hs.get("straighten"):
        info["straightened"] = {"materials": hs["straighten"], "max_move_mm": heads.straighten_ring(head, set(hs["straighten"]))}
    if hs.get("tuck_ears"):
        info["ears_tucked"] = {"x_max_m": hs["tuck_ears"], "vertices_moved": heads.tuck_ears(head, hs["tuck_ears"])}
    parts["head"] = head; rep["parts"]["head"] = info

    # hairstyle and other split head regions; never take eyes or brows along with a hair material
    for role, spec in [("hair", rc["hair"])] + [(e["role"], e) for e in rc.get("extras", [])]:
        mats = set(spec["materials"])
        cuts = [zones.CUT_ZONES[z] for z in spec.get("cut", [])]
        pzs = [zones.PIECE_ZONES[z] for z in spec.get("drop_pieces", [])]
        obj, info = take_part(packs, cid, role, g, spec, arm,
                              keep=lambda m, c, mats=mats, role=role, cuts=cuts: m in mats and (role != "hair" or not zones.BROW_ZONE(c)) and not any(z(c) for z in cuts),
                              drop_piece=(lambda c, pzs=pzs: any(z(c) for z in pzs)) if pzs else None)
        if cuts:
            info["cut"] = spec["cut"]
        if pzs:
            info["drop_pieces"] = spec["drop_pieces"]
        heads.inflate(obj, arm, spec.get("inflate", 0.0))
        info["materials"] = ", ".join(sorted(mats)) + " faces of the source head"
        info["inflate"] = spec.get("inflate", 0.0)
        parts[role] = obj; rep["parts"][role] = info

    for role in ("top", "bottom", "shoes"):
        obj, info = take_part(packs, cid, role, g, rc[role], arm)
        parts[role] = obj; rep["parts"][role] = info
    update()
    rep["parts"]["bottom"]["tuck"] = fit.tuck_cull(parts["bottom"], parts["shoes"], arm)
    for ex in rc.get("extend", []):
        rep["parts"][ex["part"]]["extended"] = fit.extend_edge(parts[ex["part"]], ex["drop"])
    update()
    # a toe bone per foot at the ball of the shoes, the shoes' fronts reweighted to it (art #25): any clip can bend
    # the shoe at push-off; the pack's own actions never key a toe, so they play as before
    rep["toe_bones"] = toes.add_toe_bones(arm, parts["shoes"], list(parts.values()))

    for o in parts.values():
        relink(o, coll)

    # one skin material for the whole character
    skin = None
    for slot in head.material_slots:
        if slot.material and base_name(slot.material.name) == "Skin":
            skin = slot.material.copy(); skin.name = cid + "_skin"
    if rc.get("skin"):
        set_color(skin, rc["skin"])
    skin_names = {"Skin"} | set(hs.get("as_skin", []))
    for role, o in parts.items():
        for slot in o.material_slots:
            if slot.material and (base_name(slot.material.name) == "Skin" or (role == "head" and base_name(slot.material.name) in skin_names)):
                slot.material = skin
    rep["skin_rgb"] = [round(x, 3) for x in skin.diffuse_color[:3]]

    # recolours
    rep["recolor"] = []
    for rcol in rc.get("recolor", []):
        o = parts[rcol["part"]]
        hits = [slot for slot in o.material_slots if slot.material and base_name(slot.material.name) == rcol["material"]]
        if not hits:
            raise KeyError("recolor: no material %s on the %s part (%s)" % (rcol["material"], rcol["part"], o.name))
        for slot in hits:
            old = [round(x, 3) for x in slot.material.diffuse_color[:3]]
            rgb = color_of(rcol["rgb"], parts)
            m = slot.material.copy(); m.name = "%s_%s_%s_recolor" % (cid, rcol["part"], rcol["material"])
            set_color(m, rgb)
            slot.material = m
            rep["recolor"].append({"part": rcol["part"], "object": o.name, "material": rcol["material"], "from_rgb": old,
                                   "to_rgb": rgb, "rgb_spec": rcol["rgb"], "was": rcol.get("was")})

    # scripted face parts on the bald head
    update()
    if face == "kit":
        from .clayface import adapter
        built, rep["face_kit"] = adapter.build(arm, parts, coll, rc, eyes_at, skin,
                                               pack_mouth_dz=recipe.get("face", {}).get(g, {}).get("mouth_dz"))
        parts.update(built)
        for role, o in built.items():
            rep["parts"][role] = {"kit": True, "object": o.name, "bone": "Head (weight 1.0)"}
    else:
        surf = fk.Surface(head)
        fe = rc["eyes"]
        smooth = recipe.get("face_shading", "smooth") == "smooth"
        eyes = fk.eyes(surf, eyes_at, fe["style"], {"iris": fe.get("iris", (0.1, 0.25, 0.6)), "lash": fe.get("lash", (0.02, 0.01, 0.01))}, skin)
        parts["eyes"] = eyes.to_object(cid + "_eyes", head, arm, smooth=smooth)
        br = rc["brows"]
        brow_rgb = color_of(br["rgb"], parts)
        parts["brows"] = fk.brows(surf, eyes_at, br["style"], brow_rgb).to_object(cid + "_brows", head, arm, smooth=smooth)
        rep["brow_rgb"] = brow_rgb
        ez = (eyes_at["L"].z + eyes_at["R"].z) / 2
        mz = ez + rc["mouth"].get("dz", recipe["face"][g]["mouth_dz"])
        mo = rc["mouth"]
        parts["mouth"] = fk.mouth(surf, 0.0, mz, mo["style"], {"lip": mo.get("lip", (0.3, 0.07, 0.07))}).to_object(cid + "_mouth", head, arm, smooth=smooth)
        for role in ("eyes", "brows", "mouth"):
            o = parts[role]
            relink(o, coll)
            rep["parts"][role] = {"scripted": True, "style": rc[role]["style"], "object": o.name, "bone": "Head (weight 1.0)"}
    if face == "kit":
        mz = rep["face_kit"]["layout"]["mouth_z"]
    rep["eye_centres"] = {k: [round(x, 4) for x in v] for k, v in eyes_at.items()}
    rep["mouth_centre_z"] = round(mz, 4)
    update()
    rep["jaw"] = jaw_measure(parts, (eyes_at["L"].x + eyes_at["R"].x) / 2, mz)

    # numbers in the rest pose
    update()
    rep["seam_overlap_rest"] = fit.seam_overlaps(parts["head"], parts["top"], parts["bottom"], parts["shoes"])
    edges = fit.rest_edges(arm, parts)
    tucked = {s: rep["parts"]["bottom"]["tuck"][s]["tucked"] for s in ("L", "R")}
    arm["seam_edges"] = json.dumps(edges); arm["tucked"] = json.dumps(tucked)
    rep["probe_rest"] = fit.probe(arm, parts, edges, tucked)
    zs = world_points(parts.values())
    rep["height_m"] = round(max(p.z for p in zs) - min(p.z for p in zs), 3)
    rep["height_without_hair_m"] = round(max(p.z for p in world_points([parts[k] for k in parts if k not in ("hair",)])) - min(p.z for p in zs), 3)
    rep["triangles"] = {k: tris(o) for k, o in parts.items()}
    rep["triangles_total"] = sum(rep["triangles"].values())
    rep["objects"] = {k: {"name": o.name, "parent": o.parent.name, "armature_modifier": next((m.object.name for m in o.modifiers if m.type == "ARMATURE"), None),
                          "vertex_groups": len(o.vertex_groups)} for k, o in parts.items()}
    return arm, parts, rep


def jaw_measure(parts, x, mouth_z):
    """The jaw check's measures (um/jaw.py) on the built parts in the rest pose: per sight line (front, 3/4 left and
    right) and per level below the mouth centre z, a ray toward the head's axis: the y of the head's first surface it
    meets (None: none) and the part met before it outside jaw.SIGHT_CLEAR_ROLES (None: none)."""
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    trees = {}
    for role, o in parts.items():
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        trees[role] = BVHTree.FromPolygons([o.matrix_world @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
        ev.to_mesh_clear()
    reach = 2.0
    out = {"mouth_z": round(mouth_z, 4), "rays": {}}
    for view, d in jaw.sight_dirs().items():
        dv = Vector(d)
        rows = []
        for dz_mm in jaw.LEVELS_MM:
            aim = Vector((x, jaw.AXIS_Y, mouth_z - dz_mm / 1000.0))
            hits = []
            for role, t in trees.items():
                hit, _, _, dist = t.ray_cast(aim + dv * reach, -dv, reach)
                if hit is not None:
                    hits.append((role, dist, hit.y))
            rows.append(dict(dz_mm=dz_mm, **jaw.read_ray(hits)))
        out["rays"][view] = rows
    return out


def clay_look(recipe, rc, arm, parts, rep, lib=None):
    """The clay pass (um/clay.py) on a built character, still at the origin in the rest pose; with lib, the bake from
    the per-piece clay library (um/claybake.py). Records rep["clay"] (and rep["clay_bake"]); the triangles become the
    clay ones (the pack's stay under triangles_pack)."""
    from . import clay, claybake, claylook

    cfg = claylook.settings(recipe)
    crep, sources = clay.apply(rc["id"], arm, parts, cfg)
    rep["look"] = "clay"
    rep["clay"] = crep
    if lib:
        keys = claylook.keys_for(recipe, rc, cfg)
        scene = bpy.context.scene
        engine = scene.render.engine  # the bake runs Cycles; the review renders keep the assembler's engine
        try:
            rep["clay_bake"] = claybake.bake_character(rc["id"], arm, parts, sources, keys, rc["gender"], lib, cfg)
        finally:
            scene.render.engine = engine
    clay.remove_sources(sources)
    if "face_kit" in rep:  # the ears as the hair item sets them (the game applies the same flags), after the bake
        from .clayface import adapter
        rep["face_kit"]["ears_state"] = adapter.set_ears(parts["head"], rep["face_kit"]["flags"]["ears"])
    rep["surfaces"] = sum(len(o.material_slots) for o in parts.values())
    rep["triangles_pack"], rep["triangles_total_pack"] = rep["triangles"], rep["triangles_total"]
    rep["triangles"] = {k: tris(o) for k, o in parts.items()}
    rep["triangles_total"] = sum(rep["triangles"].values())


def pose_character(arm, parts, rc, rep):
    """The recipe pose, the posed height and the posed seam probe."""
    poses.apply(arm, rc["pose"])
    rep["pose"] = rc["pose"]
    pts = world_points(parts.values())
    rep["posed_height_m"] = round(max(p.z for p in pts) - min(p.z for p in pts), 3)
    rep["probe_posed"] = fit.probe(arm, parts, json.loads(arm["seam_edges"]), json.loads(arm["tucked"]))


def crossgender(packs, recipe, render_path, render_mod):
    """Each crossgender entry: a pack original with one part replaced by the other body type's, raw and rebound,
    front and side, posed; one labelled render. Returns the report section."""
    out = {}
    cg_coll = bpy.data.collections.new("crossgender"); bpy.context.scene.collection.children.link(cg_coll)
    figs = []
    for r_i, cg in enumerate(recipe.get("crossgender", [])):
        rep = {"label": cg["label"], "modes": {}}
        for m_i, mode in enumerate(("raw", "rebind")):
            for v_i, view in enumerate(("front", "side")):
                g = cg["gender"]
                base = packs.load(g, cg["base_file"])
                arm = base["arm"]
                rp = cg["replace"]
                old = base["meshes"][rp["remove"]]
                keep_objs = [o for n, o in base["meshes"].items() if o is not old and n not in ("Backpack", "Sword", "Pistol")]
                discard(base, keep=keep_objs + [arm, base["root"]])
                src = packs.load(rp["gender"], rp["file"])
                part = src["meshes"][rp["object"]]
                moved = rebind(part, src["arm"], arm) if mode == "rebind" else 0.0
                attach(part, arm)
                discard(src, keep=[part])
                skin = next(s.material for o in keep_objs for s in o.material_slots if s.material and base_name(s.material.name) == "Skin")
                for s in part.material_slots:
                    if s.material and base_name(s.material.name) == "Skin":
                        s.material = skin
                for o in keep_objs + [part, arm, base["root"]]:
                    relink(o, cg_coll)
                arm.data.pose_position = "REST"
                update()
                byname = {base_name(o.name): o for o in keep_objs}
                roles = {"head": next(o for n, o in byname.items() if n.endswith("Head")),
                         "top": next((o for n, o in byname.items() if n.endswith("_Body")), None),
                         "bottom": next((o for n, o in byname.items() if n.endswith(("_Legs", "_Pants"))), None),
                         "shoes": next(o for n, o in byname.items() if n.endswith("_Feet"))}
                roles[rp["role"]] = part
                overl = fit.seam_overlaps(roles["head"], roles["top"], roles["bottom"], roles["shoes"])
                poses.apply(arm, cg["pose"])
                col = m_i * 2 + v_i
                place(base["root"], x=col * 1.0, z=-r_i * 2.25, yaw=90 if view == "side" else 0)
                if view == "front":
                    rep["modes"][mode] = {"rebind_max_move_m": round(moved, 4), "seam_overlap_rest": overl}
                figs += keep_objs + [part]
                render_mod.label("%s - %s" % (mode, view), (col * 1.0, -0.6, -r_i * 2.25 - 0.13), 0.075, cg_coll)
        render_mod.label(cg["label"], (1.5, -0.6, -r_i * 2.25 + 2.0), 0.08, cg_coll)
        out[cg["id"]] = rep
    update()
    lbls = [o for o in cg_coll.objects if o.type == "FONT"]
    # include labels in the framing via their bound boxes: add their corners as a temporary mesh
    me = bpy.data.meshes.new("frame_pts")
    corners = [o.matrix_world @ Vector(c) for o in lbls for c in o.bound_box]
    me.from_pydata(corners, [], []); fo = bpy.data.objects.new("frame_pts", me); cg_coll.objects.link(fo)
    render_mod.render(render_path, figs + [fo], (90, 0, 0), height=2000, margin=1.04)
    return out
