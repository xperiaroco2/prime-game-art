"""The clay face kit's entry point: build_face (every piece on the head, bound 100 % to the Head bone), the Face
with its states (mouth, blink, look, ears), the brow and facial-hair mask UV, the one game mesh and the head-scale bake.

Ported from the faces lab's round E kit (D:/prime-art-raw/research/2026-10-05-faces/lab/clay_e/clay_face_b.py).
"""
import bpy
import numpy as np
from mathutils import Vector

from .. import clay as cl
from ..util import update
from .kit import (
    CLOSED_PIECES, EAR_KEYS, LAYOUT, LOOK, LOUD_SCALE, MASK, MASK_UV, MOUTHS, NOSE_SCALE, SCALE_FADE, STATES,
    nose_axes, nose_loud)
from .mesh import Ctx, add_keys, apply_skin, bind as bind_head, data_object, drop_piece, materials, piece_coords
from .mouth import build_mouth, outer2d
from .eyes import build_eyes
from .brows import build_brows
from .nose import build_nose, nose_eye_overlap, nose_meets_pupils, settle_nose
from .ears import build_ears
from .fhair import build_facial_hair, lift_moustache, seat_moustache, settle_goatee


class Face:
    def __init__(self, h, picks, skin):
        self.h, self.picks, self.skin = h, dict(picks), skin
        self.pieces = {}  # name -> object
        self.cat = {}  # name -> category
        self.meta = {"picks": dict(picks), "skin": skin if isinstance(skin, str) else list(skin)}
        self.state = {"mouth": "rest", "blink": 0.0, "look": (0.0, 0.0)}

    def add(self, name, o, cat):
        self.pieces[name] = o
        self.cat[name] = cat
        return o

    def objects(self):
        return list(self.pieces.values())

    def keys_of(self, o):
        sk = o.data.shape_keys
        return {kb.name: kb for kb in sk.key_blocks[1:]} if sk else {}

    def set_state(self, mouth=None, blink=None, look=None, frame=None):
        """mouth: a state name; blink: 0, 0.5 or 1 (the blink's three exact steps); look: (yaw, pitch) degrees,
        + yaw toward the character's left, + pitch up. Keyframes at frame when given (constant interpolation)."""
        if mouth is not None:
            self.state["mouth"] = mouth
        if blink is not None:
            self.state["blink"] = blink
        if look is not None:
            self.state["look"] = look
        m, b, (yaw, pitch) = self.state["mouth"], self.state["blink"], self.state["look"]
        val = {f"mouth_{s}": 1.0 if s == m else 0.0 for s in STATES if s != "rest"}
        val["blink_half"] = 1.0 if abs(b - 0.5) < 0.26 else 0.0
        val["blink"] = 1.0 if b >= 0.76 else 0.0
        val["look_l"] = max(0.0, yaw) / LOOK["yaw"]
        val["look_r"] = max(0.0, -yaw) / LOOK["yaw"]
        val["look_u"] = max(0.0, pitch) / self.meta["look"]["pitch_up"] if self.meta["look"]["pitch_up"] else 0.0
        val["look_d"] = max(0.0, -pitch) / LOOK["pitch_down"]
        for o in self.objects():
            for k, kb in self.keys_of(o).items():
                if k in val:
                    kb.value = min(1.0, val[k])
                    if frame is not None:
                        kb.keyframe_insert("value", frame=frame)

    def teeth_visible(self, on):
        t = self.pieces.get("teeth")
        if t is not None:
            t.hide_render = not on

    def set_skin(self, skin):
        self.skin = skin
        apply_skin(self.h, self.mats, skin)

    def set_brow(self, rgb):
        """Round D: the brow colour on its own (None: the dark brow of the skin)."""
        self.h.fb_brow_colour = tuple(rgb) if rgb is not None else None
        apply_skin(self.h, self.mats, self.skin)
        self.meta["brow_colour"] = list(self.h.fb_brow_colour) if rgb is not None else None

    def set_ears(self, state, frame=None):
        """Fixer, round D: the ears as ear_state gives them: "free" (shown), "tuck" (ears_tuck = 1), "hide" (ears_hide = 1)."""
        o = self.pieces.get("ears")
        keys = self.keys_of(o) if o is not None else {}
        for k, val in EAR_KEYS[state].items():
            kb = keys.get(k)
            if kb is not None:
                kb.value = val
                if frame is not None:
                    kb.keyframe_insert("value", frame=frame)
        self.meta["ears_state"] = state
        self.meta["ears_hidden"] = state == "hide"

    def hide_ears(self, on, frame=None):
        """Round D: ears_hide = 1 folds both ears inside the head (a hair or headwear in COVERS_EARS is worn)."""
        o = self.pieces.get("ears")
        kb = self.keys_of(o).get("ears_hide") if o is not None else None
        if kb is not None:
            kb.value = 1.0 if on else 0.0
            if frame is not None:
                kb.keyframe_insert("value", frame=frame)
        self.meta["ears_hidden"] = bool(on)

    def tris(self):
        return {k: cl.tris(o.data) for k, o in self.pieces.items()}

    def remove(self):
        for o in self.objects():
            me = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            if me.users == 0:
                bpy.data.meshes.remove(me)
        self.pieces = {}


def build_face(h, picks, skin, coll=None, hair_rgb=None, bind=True, brow_colour=None):
    """Builds the picked face on head h (lab_base.Head of an option A character: bean-warped pack head at rest,
    yaw 0, head scale 1). Every piece is bound to h.arm, 100 % Head. Returns a Face."""
    arm = h.arm
    old = arm.data.pose_position
    arm.data.pose_position = "REST"
    update()
    coll = coll or h.coll
    face = Face(h, picks, skin)
    face.mats = materials(h, skin, hair_rgb, brow_colour)
    face.meta["brow_colour"] = list(brow_colour) if brow_colour is not None else None
    apply_skin(h, face.mats, skin)
    ctx = Ctx(h)
    lay = build_eyes(face, ctx, coll)
    build_brows(face, ctx, lay, coll)
    M = build_mouth(face, ctx, coll)
    fh, centre_z = build_facial_hair(face, ctx, M, coll)
    settle_goatee(face)
    lift_moustache(face, ctx)
    # Iterator round 1 (resumed): a loud nose (x1.25) on the library heads could reach a pupil (the 300-face check on
    # the library heads: 50 nose|pupil triangle pairs). The nose is built at its full scale and, while it meets a
    # pupil, rebuilt 0.05 smaller (never below its quiet size, then never below wave A's size).
    # Fixer, round D: the loud nose grows per axis (LOUD_NOSE_AXES); while it meets a pupil its loudness steps down by
    # 0.1 (to the quiet size at 0), and a quiet nose that meets one drops to wave A's size (1.0), as before
    # Round E: no loud nose; a nose that meets a pupil drops to wave A's size (x NOSE_SCALE), as before
    cands = [(0.0, nose_axes(picks)), (0.0, (NOSE_SCALE.get(picks["nose"], 1.0),) * 3)]
    for t, ax in cands:
        build_nose(face, ctx, M, coll, moustache_z=centre_z, axes=ax)
        settle_nose(face)
        if not nose_meets_pupils(face) or (t, ax) == cands[-1]:
            break
        drop_piece(face, "nose")
    face.meta["nose"]["meets_pupils"] = bool(nose_meets_pupils(face))
    full = cands[0][1]
    kf = (full[0] * full[1] * full[2]) ** (1.0 / 3.0)
    face.meta["nose"]["scale_full"] = round(kf, 3)
    face.meta["nose"]["scale_xyz_full"] = [round(x, 3) for x in full]
    face.meta["nose"]["loudness"] = t if nose_loud(picks) else None
    face.meta["nose"]["shrunk_for_pupils"] = round(kf - face.meta["nose"]["scale"], 3)
    seat_moustache(face, ctx, M)
    face.ctx = ctx  # step 2 (brief5): the check's visible-poke test reads the skin
    build_ears(face, ctx, coll)
    face.meta["layout"] = {"eye_z": round(ctx.ez, 4), "mouth_z": round(ctx.mz, 4)}
    face.meta["points_pulled_in"] = getattr(ctx, "pulled_in", 0)
    face.meta["flipped"] = orient_pieces(face, ctx, lay)
    for o in face.objects():
        cl.add_rest(o)
        if bind:
            bind_head(o, arm)
    face.meta["tris"] = face.tris()
    face.meta["tris_total"] = sum(face.meta["tris"].values())
    face.meta["nose_eye_overlap_mm"] = nose_eye_overlap(face, lay)
    arm.data.pose_position = old
    update()
    face.set_state("rest", 0.0, (0.0, 0.0))
    return face


def orient_pieces(face, ctx, lay):
    """Every piece's faces turned to face OUTWARD (iterator round 2: the tech and look critics found the lips and the
    mouth cavity drawn only from behind; a game shader that culls back faces lost them). Closed pieces by their signed
    volume, eye pieces away from the nearest eye centre, the mouth away from a point 4 cm behind it, the rest away
    from their own centre. Returns {piece: faces flipped}."""
    eyes = [c for c, _ in lay.values()]
    sk = ctx.on(ctx.mx, ctx.mz, 0.0)
    behind_mouth = Vector((ctx.mx, sk.y + 0.04, ctx.mz))
    out = {}
    for name, o in face.pieces.items():
        me = o.data
        if not len(me.polygons):
            continue
        V = [o.matrix_world @ v.co for v in me.vertices]
        if name in CLOSED_PIECES:  # the state with the largest volume (hidden teeth collapse to a point at rest)
            sets = [V]
            if me.shape_keys:
                sets += [[o.matrix_world @ d.co for d in kb.data] for kb in me.shape_keys.key_blocks[1:]]
            vols = []
            for W in sets:
                vol = 0.0
                for p in me.polygons:
                    vs = [W[i] for i in p.vertices]
                    for k in range(1, len(vs) - 1):
                        vol += vs[0].dot(vs[k].cross(vs[k + 1])) / 6.0
                vols.append(vol)
            vol = max(vols, key=abs)
            bad = vol < 0.0
        else:
            cen = sum(V, Vector()) / len(V)
            score = 0.0
            for p in me.polygons:
                fc = o.matrix_world @ p.center
                nrm = (o.matrix_world.to_3x3() @ p.normal)
                if name in ("whites", "pupils", "lids"):
                    ref = min(eyes, key=lambda e: (e - fc).length)
                elif name == "mouth":
                    ref = behind_mouth
                else:
                    ref = cen
                score += p.area * nrm.dot(fc - ref)
            bad = score < 0.0
        if bad:
            for p in me.polygons:
                p.flip()
            me.update()
        out[name] = bool(bad)
    return out


def rigid_full_z(h, margin=0.005):
    """The z down to which the head skin must follow the Head bone alone: below every mouth state and goatee of the
    kit (any pick), minus a margin. Call before smoothing the head (fk.rigid_face_skin(head, -0.07, z, z - 0.03))."""
    ez = h.eye_z() + LAYOUT["eye_dz"]
    mz = ez - LAYOUT["eye_mouth"]
    low = 0.0
    for M in MOUTHS.values():
        for st in M["states"].values():
            low = min(low, min(z for _, z in outer2d(M, st, 0.0, 0.0)))
    goatee_extra = 0.0015 + 2 * 0.0165 * LOUD_SCALE["facial_hair"] + 0.003  # the goatee lump at its lowest (the "a" state)
    return mz + low - goatee_extra - margin


def mask_rules(face):
    """Round D: {material name: mask uv} of a face: its brow material (1, 0), its facial-hair material (0, 1)."""
    return {face.mats["brow"].name: MASK["brow"], face.mats["fhair"].name: MASK["fhair"]}


def write_mask_uv(o, rules, layer=MASK_UV):
    """Round D: writes the mask UV layer of mesh object o by material: every loop of a face whose material is in
    rules gets rules[name], the rest (0, 0). The layer is added after the existing ones (the atlas UV stays first, the
    active and the render UV), so the glTF exporter writes it as TEXCOORD_1 when there is one UV before it.
    Returns {name: faces marked}."""
    me = o.data
    keep = me.uv_layers.active.name if me.uv_layers.active else None
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
        keep = "UVMap"
    lay = me.uv_layers.get(layer) or me.uv_layers.new(name=layer)
    names = [s.material.name if s.material else "" for s in o.material_slots]
    uv = np.zeros((len(me.loops), 2), np.float32)
    count = {k: 0 for k in rules}
    for p in me.polygons:
        n = names[p.material_index] if p.material_index < len(names) else ""
        if n in rules:
            count[n] += 1
            uv[p.loop_start:p.loop_start + p.loop_total] = rules[n]
    # the glTF exporter writes V as 1 - v (glTF's origin is top left): store 1 - v so the GLB and Godot read the mask
    # values as given (brows UV2 = (1, 0), facial hair (0, 1), the rest (0, 0))
    uv[:, 1] = 1.0 - uv[:, 1]
    lay.data.foreach_set("uv", uv.ravel())
    if keep:
        me.uv_layers.active = me.uv_layers[keep]
        for u in me.uv_layers:
            u.active_render = u.name == keep
    return count


def game_mesh(face, name=None, coll=None):
    """Merges a face's pieces into one mesh object with every shape key by name (zero delta where a piece has none),
    skinned 100 % to Head. The pieces stay (hidden). Returns the object."""
    h = face.h
    verts, faces, fmats, mats = [], [], [], []
    keyed = {}
    pieces = [o for o in face.objects() if not o.hide_render]
    names = sorted({k for o in pieces for k in face.keys_of(o)})
    for o in pieces:
        base = len(verts)
        basis = piece_coords(o)
        verts += basis
        slot = []
        for s in o.material_slots:
            if s.material not in mats:
                mats.append(s.material)
            slot.append(mats.index(s.material))
        for p in o.data.polygons:
            faces.append(tuple(v + base for v in p.vertices))
            fmats.append(slot[p.material_index])
        ks = face.keys_of(o)
        for k in names:
            keyed.setdefault(k, [])
            keyed[k] += piece_coords(o, k) if k in ks else basis
    arm = h.arm
    old = arm.data.pose_position
    arm.data.pose_position = "REST"
    update()
    o = data_object(name or f"{h.id}_face", verts, faces, fmats, mats, coll or h.coll)
    add_keys(o, keyed, None)
    face.meta["mask_faces"] = write_mask_uv(o, mask_rules(face))  # round D
    cl.add_rest(o)
    bind_head(o, arm)
    arm.data.pose_position = old
    update()
    for p in pieces:
        p.hide_render = True
        p.hide_viewport = True
    return o


def bake_head_scale(arm, objs, s, fade=SCALE_FADE):
    """Bakes a uniform scale s of the Head bone (about its head, the rest pose) into skinned meshes, shape keys
    included: each vertex moves by k (s - 1) (v - pivot), k = its Head weight x a smoothstep that fades the scale to
    nothing over `fade` below the pivot. The formula of clay_parts.bake_head_scale (the head and its items), so a face
    baked here stays on a head baked there; fade=0 is exactly the lab's Copy Scale on the Head pose bone."""
    pivot_w = arm.matrix_world @ arm.data.bones["Head"].head_local
    out = {}
    for o in objs:
        vg = o.vertex_groups.get("Head")
        if vg is None:
            continue
        gi = vg.index
        me = o.data
        inv = o.matrix_world.inverted()
        pivot = inv @ pivot_w
        lin = inv.to_3x3() @ o.matrix_world.to_3x3()  # identity up to rounding; keeps the formula in object space
        ws = np.zeros(len(me.vertices))
        for v in me.vertices:
            for g in v.groups:
                if g.group == gi:
                    ws[v.index] = g.weight
        P = np.array(pivot)
        mwz = np.array(o.matrix_world, dtype=np.float64)
        blocks = [me.shape_keys.key_blocks[i] for i in range(len(me.shape_keys.key_blocks))] if me.shape_keys else []
        targets = [me.vertices] + [kb.data for kb in blocks]
        kf = np.ones(len(me.vertices))
        if fade > 0:  # the fade is measured on the world z of the basis (rest) positions
            b0 = np.empty(len(me.vertices) * 3, np.float32)
            me.vertices.foreach_get("co", b0)
            wz = b0.reshape(-1, 3).astype(np.float64) @ mwz[2, :3] + mwz[2, 3]
            tt = np.clip((wz - (pivot_w.z - fade)) / fade, 0.0, 1.0)
            kf = tt * tt * (3 - 2 * tt)
        for t in targets:
            co = np.empty(len(me.vertices) * 3, np.float32)
            t.foreach_get("co", co)
            co = co.reshape(-1, 3).astype(np.float64)
            k = ws * kf
            co += (k[:, None] * (s - 1.0)) * (co - P)
            t.foreach_set("co", co.astype(np.float32).ravel())
        me.update()
        cl.add_rest(o)
        out[o.name] = int((ws * kf > 1e-4).sum())
    return out
