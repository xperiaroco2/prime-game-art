"""The alien parts kit's body (art #196, step S1): the Universal Base Characters male body (Quaternius, CC0) refitted by
measurement to the approved u1 turnaround, with four fingers, three-toe paddle feet and no head (the neck ends in a
standard ring the separate head welds to), on the contract skeleton with Universal Animation Library clips.

    blender -b --factory-startup --python-exit-code 1 --python tools/blender/alien_body.py -- \
        --body <Superhero_Male_FullBody.gltf> --clips <UAL1_Standard.glb> --map contract/bone_maps/quaternius.toml \
        --out <dir>

Writes <out>/alien_body.blend (a saved character for `tools/run.py export`), <out>/neck_ring.json and
<out>/fit.json (the measured widths before and after against the targets).

How the fit works (no sculpting, all by numbers):
1. Rest rebuild. Each bone b gets an affine map M_b = T(new head) * S_b * T(-old head), with S_b a scale along world
   axes (the body is in a T-pose, so arms run along X, legs and spine along Z): one factor along the bone (its new
   length) and two across it (its thickness). A child's new head is its parent's map of its old head. Every vertex
   moves by the weight blend of its bones' maps, the same blend its skin uses, so joints stay where they bend.
2. Bands. The trunk and neck are then scaled per height band in width (X) and depth (Y) to the u1 targets, blended by
   how much of each vertex the trunk bones carry; a soft forward bulge gives the u1 belly.
3. Smoothing. The muscle relief (pecs, abs, ribs) is relaxed with a volume-keeping Laplacian smooth.
4. Hands: the Little finger's mesh is removed and its hole closed; its bones stay, unweighted. The other fingers
   are thickened. Feet: the five sculpted toes are smoothed away and two grooves cut three toe lobes.
5. The neck is cut at RING_Z, and its open edge is resampled to RING_N vertices at equal angles on an ellipse: the
   standard neck ring (neck_ring.json: positions, the next loop below, the weights).
6. Bones renamed to the contract (the bone map), the leaf bones dropped, Jaw and eye bones added (unweighted).
7. The clips: Universal Animation Library actions copied as-is (the same 65-bone rig), renamed to the game's names.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import tomllib

import bmesh
import bpy
from mathutils import Matrix, Vector

# u1 (D:/prime-art-raw/2026-10-18-alien-2d-turn2/u1, part_0 front, part_1 side), measured per pixel row; the sole is
# row 967 and one pixel is 0.0019 m (1.75 m from the sole to the top of the head without the crest).
PX_M = 0.0019
# (z m, width m, depth m) of the trunk and neck; None = not constrained there (arms merge into the silhouette).
BANDS = [
    (0.783, 0.304, 0.198),
    (0.859, 0.277, 0.232),
    (0.935, 0.262, 0.252),
    (1.011, 0.232, 0.246),
    (1.087, 0.236, 0.224),
    (1.125, 0.255, 0.217),
    (1.200, None, 0.218),
    (1.315, None, 0.135),
    (1.353, 0.124, 0.110),
    (1.391, 0.114, 0.106),
]
# Bone scales: (along, across, across) in world axes per bone, and the thickness targets (radius m) measured on u1.
LENGTH = {
    "pelvis": 0.907, "spine_01": 0.907, "spine_02": 0.907, "spine_03": 0.907, "neck_01": 1.25,
    "clavicle": 0.668, "upperarm": 1.04, "lowerarm": 0.95, "hand": 1.12,
    "thigh": 0.753, "calf": 0.884, "foot": 1.25, "ball": 1.2,
}
RADIUS = {"upperarm": 0.042, "lowerarm": 0.031, "thigh": 0.066, "calf": 0.054}
FINGER_THICK = 1.4
PADDLE = 0.5
HAND_SCALE = 1.12
FOOT_WIDTH = 1.3
RING_Z = 1.39
RING_N = 24
RING_STEP = 0.008
BELLY = 0.022
CLIPS = {  # the game's name: the Universal Animation Library's
    "Idle_Loop": "Idle_Loop", "Walk_Loop": "Walk_Loop", "Jog_Fwd_Loop": "Jog_Fwd_Loop",
    "Sprint_Fwd_Loop": "Sprint_Loop", "Crouch_Idle_Loop": "Crouch_Idle_Loop", "Crouch_Fwd_Loop": "Crouch_Fwd_Loop",
    "Jump_Start": "Jump_Start", "Jump_Air_Loop": "Jump_Loop", "Jump_Land": "Jump_Land",
    "Talk_Upper_Loop": "Idle_Talking_Loop",
}
TRUNK = ("pelvis", "spine_01", "spine_02", "spine_03", "neck_01", "Head")


def kind(name):
    base = name[:-2] if name[-2:] in ("_l", "_r") else name
    for f in ("thumb", "index", "middle", "ring", "pinky"):
        if base.startswith(f):
            return "finger"
    return base


def axis_of(bone_name):
    """The world axis a bone runs along in the T-pose: 0 X (arms, hands, fingers), 1 Y (feet), 2 Z (trunk, legs)."""
    k = kind(bone_name)
    if k in ("clavicle", "upperarm", "lowerarm", "hand", "finger"):
        return 0
    if k in ("foot", "ball"):
        return 1
    return 2


def weights_of(obj):
    names = [g.name for g in obj.vertex_groups]
    out = []
    for v in obj.data.vertices:
        ws = {names[g.group]: g.weight for g in v.groups if g.weight > 1e-4}
        s = sum(ws.values()) or 1.0
        out.append({k: w / s for k, w in ws.items()})
    return out


def dominant(ws):
    return max(ws.items(), key=lambda kv: kv[1])[0] if ws else None


def radial(obj, ws, bones, name):
    """The median distance of the bone's dominant vertices from its axis line."""
    b = bones[name]
    h, t = b["head"], b["tail"]
    d = (t - h).normalized()
    rs = []
    for v, w in zip(obj.data.vertices, ws):
        if dominant(w) == name:
            p = v.co - h
            rs.append((p - d * p.dot(d)).length)
    rs.sort()
    return rs[len(rs) // 2] if rs else None


def band_measure(obj, ws, z, half=0.012):
    xs, ys = [], []
    for v, w in zip(obj.data.vertices, ws):
        if abs(v.co.z - z) < half and sum(w.get(n, 0) for n in TRUNK) > 0.8:
            xs.append(v.co.x)
            ys.append(v.co.y)
    if len(xs) < 16:
        return None
    return max(xs) - min(xs), max(ys) - min(ys), (max(ys) + min(ys)) / 2


def lerp_bands(z, idx):
    pts = [(b[0], b[idx]) for b in BANDS if b[idx] is not None]
    if z <= pts[0][0] or z >= pts[-1][0]:
        return None
    for (z0, a), (z1, b) in zip(pts, pts[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / (z1 - z0)
            return a + (b - a) * t
    return None


def boundary_loop(bm, zmin):
    """The longest closed boundary loop whose vertices all lie above zmin near the body's centre line (the neck cut)."""
    edges = [e for e in bm.edges if e.is_boundary and all(v.co.z > zmin and abs(v.co.x) < 0.15 for v in e.verts)]
    adj = {}
    for e in edges:
        a, b = e.verts
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    seen, best = set(), []
    for start in adj:
        if start in seen:
            continue
        loop, prev, cur = [start], None, start
        seen.add(start)
        while True:
            nxt = [v for v in adj[cur] if v is not prev]
            if not nxt or nxt[0] is start or nxt[0] in seen:
                break
            prev, cur = cur, nxt[0]
            seen.add(cur)
            loop.append(cur)
        if len(loop) > len(best):
            best = loop
    return best


def main():
    p = argparse.ArgumentParser(prog="alien_body.py")
    p.add_argument("--body", required=True)
    p.add_argument("--clips", required=True)
    p.add_argument("--map", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args(sys.argv[sys.argv.index("--") + 1:])
    report = {"source": args.body, "clips_source": args.clips}

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=args.body, merge_vertices=True)  # one vertex per position: no seams to tear
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    body = next(o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("SuperHero"))
    for o in list(bpy.data.objects):
        if o not in (arm, body):
            bpy.data.objects.remove(o)
    # Bake the object transforms so the armature and the mesh live in world space.
    for o in (arm, body):
        o.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    body.parent = arm
    body.matrix_parent_inverse = Matrix.Identity(4)

    bones = {b.name: {"head": b.head_local.copy(), "tail": b.tail_local.copy(),
                      "parent": b.parent.name if b.parent else None} for b in arm.data.bones}
    ws = weights_of(body)
    report["before"] = {"verts": len(body.data.vertices), "tris": sum(len(f.vertices) - 2 for f in body.data.polygons)}

    # 1. The rest rebuild.
    meas = {}
    scales = {}
    for name in bones:
        k = kind(name)
        ax = axis_of(name)
        if k == "finger":
            s_len, s_rad = HAND_SCALE, HAND_SCALE * FINGER_THICK
        elif k == "hand":
            s_len, s_rad = HAND_SCALE, HAND_SCALE
        elif k in ("foot", "ball"):
            s_len, s_rad = LENGTH[k], FOOT_WIDTH
        else:
            s_len = LENGTH.get(k, LENGTH.get(name, 1.0))
            s_rad = 1.0
            if k in RADIUS:
                r = radial(body, ws, bones, name)
                meas[name] = r
                s_rad = max(0.5, min(1.2, RADIUS[k] / r)) if r else 1.0
        s = [s_rad, s_rad, s_rad]
        s[ax] = s_len
        if k in ("foot", "ball"):  # feet: longer forward and taller, wider in X
            s = [FOOT_WIDTH, s_len, s_len]
        if k == "ball":
            s = [FOOT_WIDTH, s_len, 1.0]
        if name == "neck_01":
            s = [1.0, 1.0, s_len]
        scales[name] = s
    report["radius_measured"] = meas
    new_head, maps = {}, {}
    order = []
    def visit(n):
        order.append(n)
        for c in [c for c, b in bones.items() if b["parent"] == n]:
            visit(c)
    for root in [n for n, b in bones.items() if b["parent"] is None]:
        visit(root)
    for n in order:
        b = bones[n]
        par = b["parent"]
        nh = maps[par] @ b["head"] if par else b["head"].copy()
        new_head[n] = nh
        maps[n] = Matrix.Translation(nh) @ Matrix.Diagonal((*scales[n], 1.0)) @ Matrix.Translation(-b["head"])
    me = body.data
    newco = []
    for v, w in zip(me.vertices, ws):
        acc = Vector((0, 0, 0))
        for n, wt in w.items():
            acc += wt * (maps[n] @ v.co) if n in maps else wt * v.co
        newco.append(acc)
    for v, c in zip(me.vertices, newco):
        v.co = c
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    for eb in arm.data.edit_bones:
        eb.use_connect = False
    for eb in arm.data.edit_bones:
        b = bones[eb.name]
        d = b["tail"] - b["head"]
        L = (maps[eb.name] @ b["tail"] - new_head[eb.name]).length
        roll = eb.roll
        eb.head = new_head[eb.name]
        eb.tail = new_head[eb.name] + d.normalized() * L
        eb.roll = roll
    bpy.ops.object.mode_set(mode="OBJECT")
    # Floor: soles at z = 0 (the rebuild shortened the legs, so the body floats).
    lowest = min(v.co.z for v in me.vertices)
    for v in me.vertices:
        v.co.z -= lowest
    bpy.ops.object.mode_set(mode="EDIT")
    for eb in arm.data.edit_bones:
        eb.head.z -= lowest
        eb.tail.z -= lowest
    bpy.ops.object.mode_set(mode="OBJECT")
    report["floor_shift"] = lowest

    # 2. Bands: trunk and neck width and depth.
    ws = weights_of(body)
    me = body.data
    zs = sorted({round(v.co.z, 2) for v in me.vertices})
    cur = {}
    for z in zs:
        m = band_measure(body, ws, z, 0.01)
        if m:
            cur[z] = m
    band_report = {}
    for v, w in zip(me.vertices, ws):
        s = sum(w.get(n, 0) for n in TRUNK)
        if v.co.z > 0.80:  # the seat: the thighs carry the buttocks
            s = min(1.0, s + sum(w.get(n, 0) for n in ("thigh_l", "thigh_r")) * min(1.0, (v.co.z - 0.80) / 0.06))
        if s < 0.05:
            continue
        z = round(v.co.z, 2)
        if z not in cur:
            continue
        cw, cd, cy = cur[z]
        tw, td = lerp_bands(v.co.z, 1), lerp_bands(v.co.z, 2)
        # Outside the trunk the arms and the outer thighs keep their shape (a soft falloff, never a cut).
        s *= max(0.0, min(1.0, (0.85 * cw - abs(v.co.x)) / (0.3 * cw)))
        if tw:
            v.co.x *= 1 + s * (min(1.25, max(0.6, tw / cw)) - 1)
        if td:
            v.co.y = cy + (v.co.y - cy) * (1 + s * (min(1.25, max(0.6, td / cd)) - 1))
        # The belly: a soft forward bulge below the chest (front is -Y).
        if 0.84 < v.co.z < 1.06 and v.co.y < cy:
            t = (v.co.z - 0.84) / 0.22
            fall = math.sin(math.pi * t) ** 2 * math.exp(-(v.co.x / 0.09) ** 2)
            v.co.y -= s * BELLY * fall
    ws = weights_of(body)
    for b in BANDS:
        band_report[str(b[0])] = {"target": [b[1], b[2]], "after": band_measure(body, ws, b[0])}
    report["bands"] = band_report

    # 3-5 in bmesh.
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    deform = bm.verts.layers.deform.verify()
    gi = {g.name: g.index for g in body.vertex_groups}
    def wsum(v, names):
        d = v[deform]
        return sum(d.get(gi[n], 0.0) for n in names if n in gi)
    # A plain neighbour-average relax (the Laplacian operator with volume keeping threw spikes here).
    trunk_names = [n for n in TRUNK if n != "Head"] + ["clavicle_l", "clavicle_r"]
    relax = [v for v in bm.verts if wsum(v, trunk_names) > 0.6 and 0.86 < v.co.z < RING_Z - 0.03]
    for _ in range(6):
        bmesh.ops.smooth_vert(bm, verts=relax, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    # Hands: remove the Little finger.
    pinky = [f"pinky_{i:02d}_{s}" for i in (1, 2, 3) for s in "lr"] + ["pinky_04_leaf_l", "pinky_04_leaf_r"]
    gone = [v for v in bm.verts if wsum(v, pinky) > 0.5]
    report["pinky_removed_verts"] = len(gone)
    bmesh.ops.delete(bm, geom=gone, context="VERTS")
    holes = [e for e in bm.edges if e.is_boundary and abs(e.verts[0].co.x) > 0.5]
    filled = bmesh.ops.holes_fill(bm, edges=holes, sides=0)
    newf = filled["faces"]
    bmesh.ops.triangulate(bm, faces=[f for f in newf if len(f.verts) > 4])
    hand_rim = {v for e in holes for v in e.verts if e.is_valid}
    near = {v for v in bm.verts if v.is_valid and any((v.co - r.co).length < 0.02 for r in hand_rim)}
    for _ in range(4):
        bmesh.ops.smooth_vert(bm, verts=list(near), factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    for v in bm.verts:
        d = v[deform]
        for side in "lr":
            hw = 0.0
            for n in pinky:
                if n.endswith(side) and n in gi and gi[n] in d:
                    hw += d[gi[n]]
                    del d[gi[n]]
            if hw > 0:
                d[gi[f"hand_{side}"]] = d.get(gi[f"hand_{side}"], 0.0) + hw
    # Feet: smooth the five toes, cut three lobes.
    foot_info = {}
    for side, sx in (("l", 1), ("r", -1)):
        toes = [v for v in bm.verts if wsum(v, [f"ball_{side}", f"ball_leaf_{side}"]) > 0.25]
        if not toes:
            continue
        yball = max(v.co.y for v in toes)
        fore = [v for v in bm.verts if wsum(v, [f"foot_{side}", f"ball_{side}", f"ball_leaf_{side}"]) > 0.3
                and v.co.y < yball + 0.06 and v.co.z < 0.12]
        for _ in range(24):  # melt the five sculpted toes into one paddle
            bmesh.ops.smooth_vert(bm, verts=toes, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
        cx = sum(v.co.x for v in toes) / len(toes)
        for v in fore:  # a paddle: the forefoot fans out to about 1.5 times its width at the toes
            f = max(0.0, min(1.0, (yball + 0.06 - v.co.y) / 0.12))
            v.co.x = cx + (v.co.x - cx) * (1 + PADDLE * f)
        half = (max(v.co.x for v in toes) - min(v.co.x for v in toes)) / 2
        ytip = min(v.co.y for v in toes)
        ztop = max(v.co.z for v in toes)
        foot_info[side] = {"centre_x": cx, "half_width": half, "tip_y": ytip, "ball_y": yball}
        for v in toes:  # two grooves cut three toe lobes: a notch at the tip and a crease on top
            u = (v.co.x - cx) / half
            g = math.exp(-((u - 0.34) / 0.12) ** 2) + math.exp(-((u + 0.34) / 0.12) ** 2)
            front = max(0.0, min(1.0, (yball - v.co.y) / max(1e-6, yball - ytip)))
            v.co.y += g * 0.03 * front ** 2
            v.co.z -= g * 0.012 * front * max(0.0, (v.co.z - 0.004) / max(1e-6, ztop - 0.004))
    report["feet"] = foot_info
    # 5. The neck ring: cut below RING_Z, build two standard rings of RING_N vertices at equal angles on an ellipse
    # (RING_Z - RING_STEP and RING_Z, quads between them) and zip the cut's uneven edge to the lower one.
    zcut = RING_Z - 2 * RING_STEP
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, zcut), plane_no=(0, 0, 1), clear_outer=True)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    cut = boundary_loop(bm, zcut - 0.003)
    report["ring_from_cut"] = len(cut)
    cy = (max(v.co.y for v in cut) + min(v.co.y for v in cut)) / 2
    ax = (max(v.co.x for v in cut) - min(v.co.x for v in cut)) / 2
    ay = (max(v.co.y for v in cut) - min(v.co.y for v in cut)) / 2
    taper = 0.98  # the neck narrows slightly towards the head
    # Angles: 0 at the front (-Y), growing towards the character's left (+X).
    ang = lambda co: math.atan2(co.x, -(co.y - cy)) % (2 * math.pi)
    cut.sort(key=lambda v: ang(v.co))
    rings = []
    for level, z in enumerate((RING_Z - RING_STEP, RING_Z)):
        kx, ky = ax * taper ** (level + 1), ay * taper ** (level + 1)
        rings.append([bm.verts.new((kx * math.sin(2 * math.pi * k / RING_N), cy - ky * math.cos(2 * math.pi * k / RING_N), z))
                      for k in range(RING_N)])
    lower, ring_v = rings
    for k in range(RING_N):
        bm.faces.new((lower[k], lower[(k + 1) % RING_N], ring_v[(k + 1) % RING_N], ring_v[k]))
    M, N = len(cut), RING_N
    angA = [ang(v.co) for v in cut]
    angB = [2 * math.pi * k / N for k in range(N)]
    i = j = 0
    while i < M or j < N:
        a_next = angA[(i + 1) % M] + (2 * math.pi if i + 1 >= M else 0)
        b_next = angB[(j + 1) % N] + (2 * math.pi if j + 1 >= N else 0)
        if j >= N or (i < M and a_next <= b_next):
            bm.faces.new((cut[i % M], cut[(i + 1) % M], lower[j % N]))
            i += 1
        else:
            bm.faces.new((cut[i % M], lower[(j + 1) % N], lower[j % N]))
            j += 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    # Weights: both rings share Neck and Head, so the head's ring can copy them exactly.
    ring_w = {"neck_01": 0.7, "Head": 0.3}
    for v in lower + ring_v:
        d = v[deform]
        for n, w in ring_w.items():
            d[gi[n]] = w
    near_ring = [v for v in bm.verts if zcut - 0.05 < v.co.z <= zcut + 1e-4]
    for _ in range(2):
        bmesh.ops.smooth_vert(bm, verts=near_ring, factor=0.4, use_axis_x=True, use_axis_y=True, use_axis_z=False)
    ring = {
        "count": RING_N, "z": RING_Z, "step": RING_STEP, "centre": [0.0, cy],
        "semi_axes": [ax * taper ** 2, ay * taper ** 2],
        "order": "index k at angle 2*pi*k/count from the front (-Y in Blender, +Z in glTF), towards the character's left (+X)",
        "axes": "Blender (Z up, front -Y); glTF/Godot: (x, z, -y)",
        "loop": [[round(c, 5) for c in v.co] for v in ring_v],
        "loop_below": [[round(c, 5) for c in v.co] for v in lower],
        "weights": {"Neck": ring_w["neck_01"], "Head": ring_w["Head"]},
        "cut_count": report["ring_from_cut"],
    }
    bm.to_mesh(me)
    bm.free()

    # 6. The contract skeleton.
    with open(args.map, "rb") as fh:
        bmap = tomllib.load(fh)
    for leaf in bmap["drop"]:
        if leaf not in arm.data.bones:
            continue
        parent = arm.data.bones[leaf].parent.name
        g, pg = body.vertex_groups.get(leaf), body.vertex_groups.get(parent)
        if g:
            for v in me.vertices:
                for e in v.groups:
                    if e.group == g.index and e.weight > 0:
                        pg.add([v.index], e.weight, "ADD")
            body.vertex_groups.remove(g)
    bpy.ops.object.mode_set(mode="EDIT")
    for leaf in bmap["drop"]:
        if leaf in arm.data.edit_bones:
            arm.data.edit_bones.remove(arm.data.edit_bones[leaf])
    head = arm.data.edit_bones["Head"]
    hz = head.head.z
    for name, off in (("Jaw", (0, -0.03, 0.0)), ("LeftEye", (0.035, -0.08, 0.17)), ("RightEye", (-0.035, -0.08, 0.17))):
        eb = arm.data.edit_bones.new(name)
        eb.head = head.head + Vector(off)
        eb.tail = eb.head + Vector((0, -0.04, 0)) if name != "Jaw" else eb.head + Vector((0, -0.08, -0.03))
        eb.parent = head
    bpy.ops.object.mode_set(mode="OBJECT")
    for old, new in bmap["rename"].items():
        if old in arm.data.bones:
            arm.data.bones[old].name = new
        g = body.vertex_groups.get(old)
        if g:
            g.name = new
    # Little fingers: their groups stay present and empty.
    for v in me.vertices:
        for g in body.vertex_groups:
            if "Little" in g.name:
                g.remove([v.index])
    arm.name = "CharacterArmature"
    arm.data.name = "CharacterArmature"
    body.name = "Body"
    body.data.name = "Body"
    body.modifiers.clear()
    mod = body.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    # One material, no texture: S2's hue shader replaces it in Godot.
    mat = bpy.data.materials.new("M_AlienBody")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.16, 0.42, 0.40, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.6
    me.materials.clear()
    me.materials.append(mat)
    for poly in me.polygons:
        poly.use_smooth = True

    # 7. The clips.
    keep = set(bpy.data.actions)
    before_objs = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=args.clips)
    for o in set(bpy.data.objects) - before_objs:
        bpy.data.objects.remove(o)
    found = {}
    rename = bmap["rename"]
    for act in list(bpy.data.actions):
        if act in keep:
            continue
        src = act.name.split("|")[-1]
        game = next((g for g, s in CLIPS.items() if s == src), None)
        if not game:
            bpy.data.actions.remove(act)
            continue
        for layer in act.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    for fc in list(cb.fcurves):
                        path = fc.data_path
                        if path.startswith('pose.bones["'):
                            bname = path.split('"')[1]
                            if bname in bmap["drop"]:
                                cb.fcurves.remove(fc)
                                continue
                            if bname in rename:
                                fc.data_path = path.replace(f'"{bname}"', f'"{rename[bname]}"', 1)
        act.name = f"CharacterArmature|{game}"
        for slot in act.slots:  # the imported armature's slot, renamed so the exporter binds it to this armature
            slot.name_display = arm.name
        act.use_fake_user = True
        found[game] = [act.frame_range[0], act.frame_range[1]]
    report["clips"] = found
    report["clips_missing"] = [g for g in CLIPS if g not in found]
    if arm.animation_data:
        arm.animation_data_clear()

    me.calc_loop_triangles()
    report["after"] = {"verts": len(me.vertices), "tris": len(me.loop_triangles),
                       "height": max(v.co.z for v in me.vertices),
                       "bones": {b.name: [round(c, 4) for c in b.head_local] for b in arm.data.bones}}
    with open(f"{args.out}/neck_ring.json", "w", encoding="utf-8") as fh:
        json.dump(ring, fh, indent=1)
    with open(f"{args.out}/fit.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, default=lambda o: list(o) if hasattr(o, "__iter__") else str(o))
    bpy.ops.wm.save_as_mainfile(filepath=f"{args.out}/alien_body.blend")


if __name__ == "__main__":
    main()
