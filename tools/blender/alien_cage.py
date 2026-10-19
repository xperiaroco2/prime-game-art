"""The alien parts kit's body rebuilt from a clean cage (art #196, step S4a): a symmetric low-poly quad cage built by
measurement to the approved u1 turnaround, subdivided (Catmull-Clark, level 2, applied) into a smooth designer-toy
body, with S1c's hands welded at a standard wrist ring and the standard neck ring of S1 unchanged, on S1c's contract
skeleton and clips.

    blender -b --factory-startup --python-exit-code 1 --python tools/blender/alien_cage.py -- \
        --src <S1c/build/alien_body.blend> --ring <S1/build/neck_ring.json> --out <dir>

Writes <out>/alien_body.blend (a saved character for `tools/run.py export` and `alien_assemble.py`, with the cage kept
as the hidden object `BodyCage`), <out>/neck_ring.json (S1's, copied unchanged: the assembler reads it beside the
body), <out>/wrist_ring.json and <out>/cage.json (the cage's counts and poles, the measures against u1).

The method (no sculpting, no smoothing passes over a dense mesh; every shape is a number at the top):
1. The cage, left half and midline (x >= 0), mirrored and merged at x = 0:
   - the trunk: rings of 12 vertices (index k at 30k degrees from the front midline towards the left side, 7 per
     half), each a superellipse of half width a and its own front and back depth (TRUNK, measured on u1 front and
     side: the round belly, the soft seat, the waist), from the crotch to the neck;
   - the arm hole: between the rings `armpit`, `shoulder` and `top` the side vertices k = 2..4 are the 8 vertices of
     an ellipse around the arm's root (ARM_HOLE); the shoulder ring has no k = 3;
   - the arms: rings of 8 along x (ARM: the T-pose arm, edge loops either side of the elbow) to the wrist;
   - the legs: the crotch vertex C closes each leg's first loop (the trunk's bottom k = 0..6 and C); rings of 8 down
     the leg (LEG: loops at the hip, knee and ankle) turn by 22.5 degrees from hip to ankle, so the ankle ring has
     four vertices in front and four behind;
   - the feet: the rings bend from horizontal to vertical (FOOT: the heel is the bend's outer side), the front four
     become the top of the foot and the back four its flat sole; the last ring's three quads are the three toes, each
     extruded twice and capped (TOE), the middle one longest.
   The poles (vertices of valence 3 or 5 and more) sit at the arm hole's corners, the crotch and the toes, away from
   the elbow, knee, wrist, ankle and neck loops.
2. Subdivision: Catmull-Clark, level 2, applied. The soles: the cage's lowest vertices are lowered until the
   subdivided sole touches z = 0.
3. Rings: the neck's open end (48 vertices) is laid on the ellipse just below S1's ring and joined to S1's two rings
   (2 to 1), so the head welds exactly as before; each wrist's open end (32 vertices) is laid on the standard wrist
   ring (an ellipse measured on S1c's wrist, wrist_ring.json) and S1c's hand, cut WRIST_GAP beyond it, is zipped to it.
4. Weights: copied from S1c's body (the Quaternius base's weights, refitted) by nearest-face interpolation, then
   blended with the neighbours' at every joint (WEIGHT_SMOOTH passes; the hands and the rings keep theirs), at most
   four per vertex, normalised. The Little finger's bones stay, unweighted.
"""
from __future__ import annotations

import argparse
import json
import math
import sys

import bmesh
import bpy
from mathutils import Vector

S = math.sqrt(0.5)
SUPER = 2.5  # the trunk sections' superellipse exponent (2: an ellipse; higher: fuller sides)
# The trunk rings: (name, z, half width a, front y, back y); Blender, front is -Y. u1 front (width) and side (depth),
# 0.0019 m per pixel, the side image's x mapped by y = 0.346 - x (its neck centre on the ring's centre).
TRUNK = [
    ("crotch", 0.790, 0.150, -0.066, 0.140),
    ("hip", 0.860, 0.142, -0.098, 0.152),
    ("belly", 0.930, 0.132, -0.110, 0.140),
    ("navel", 1.000, 0.119, -0.103, 0.126),
    ("waist", 1.070, 0.115, -0.090, 0.127),
    ("chest", 1.140, 0.127, -0.076, 0.136),
    ("armpit", 1.200, 0.134, -0.063, 0.146),
    ("shoulder", 1.262, 0.132, -0.034, 0.146),
    ("top", 1.312, 0.112, -0.010, 0.128),
    ("neck", 1.348, 0.066, -0.012, 0.108),
]
NECK_END = 1.374  # m: the cage's last neck ring (its subdivided edge is laid on the ring ellipse here)
CROTCH = (0.0, 0.035, 0.748)  # the vertex C closing both legs' first loops
CROTCH_Z = {0: 0.778, 6: 0.786}  # the bottom ring's front and back midline, m
# The arm hole: centre, (ry, rz), and x for its bottom, middle and top vertices.
ARM_HOLE = ((0.055, 1.266), (0.060, 0.054), (0.142, 0.150, 0.156))
# Arm rings along x: (x, y centre, z centre, ry, rz); the last is the wrist's end (replaced by the measured ring).
ARM = [
    (0.200, 0.061, 1.271, 0.047, 0.046),
    (0.280, 0.065, 1.275, 0.042, 0.041),
    (0.360, 0.068, 1.2765, 0.037, 0.036),
    (0.413, 0.070, 1.2765, 0.034, 0.033),
    (0.465, 0.069, 1.2765, 0.034, 0.032),
    (0.540, 0.067, 1.2765, 0.031, 0.029),
]
# The order of the arm's octagon (dy, dz), matching the hole: bottom-front, bottom, bottom-back, back, top-back, top,
# top-front, front (+Y is back).
OCT = [(-S, -S), (0, -1), (S, -S), (1, 0), (S, S), (0, 1), (-S, S), (-1, 0)]
WRIST_X = 0.605   # m: the standard wrist ring's plane
WRIST_GAP = 0.005  # m: S1c's hand is cut this far beyond it and zipped to it
WRIST_N = 32      # the ring's vertex count: the cage's 8 times 4
# Leg rings: (z, x centre, y centre, rx, ry); a ring of 8 turning by 22.5 degrees from the first to the last.
LEG = [
    (0.715, 0.104, 0.030, 0.066, 0.071),
    (0.630, 0.111, 0.033, 0.058, 0.063),
    (0.560, 0.114, 0.036, 0.050, 0.055),
    (0.515, 0.114, 0.038, 0.047, 0.052),
    (0.470, 0.114, 0.043, 0.047, 0.053),
    (0.380, 0.114, 0.054, 0.046, 0.053),
    (0.265, 0.114, 0.068, 0.037, 0.043),
    (0.170, 0.114, 0.080, 0.036, 0.042),
]
# Foot rings: (y, z centre, tilt deg from horizontal, half width, height above centre, depth below centre). The tilted
# ring is a regular octagon in its frame; vertical rings (90) are a rounded box with a flat sole.
FOOT = [
    (0.084, 0.100, 25.0, 0.042, 0.050, 0.070),
    (0.055, 0.058, 55.0, 0.050, 0.062, 0.075),
    (-0.005, 0.046, 90.0, 0.058, 0.050, 0.046),
    (-0.048, 0.038, 90.0, 0.070, 0.040, 0.038),
    (-0.080, 0.032, 90.0, 0.077, 0.032, 0.032),
]
FOOT_X = 0.117
# Toes: per extrusion (forward m, width scale, height scale, drop m); the middle toe reaches TOE_MID further.
TOE = [(0.016, 0.98, 0.90, 0.002), (0.032, 0.84, 0.70, 0.006)]
TOE_MID = 0.006
WRIST_SMOOTH = (0.012, 6)  # m either side of the wrist ring, passes: the weld's band eased across (y and z only)
SUBDIV = 2
# The trunk's fit: which of each ring's numbers are corrected against u1 (the arm hole's rings only their depth).
FIT = {"hip": ("a", "yf", "yb"), "belly": ("a", "yf", "yb"), "navel": ("a", "yf", "yb"),
       "waist": ("a", "yf", "yb"), "chest": ("a", "yf", "yb"), "armpit": ("yf", "yb"),
       "shoulder": ("yf", "yb"), "top": ("yf",)}
FIT_TOL = 0.001
FIT_ITERS = 8
WEIGHT_SMOOTH = 4
RING_W = {"Neck": 0.7, "Head": 0.3}


def trunk_vert(k, z, a, yf, yb, n=SUPER):
    th = math.radians(30 * k)
    s, c = math.sin(th), math.cos(th)
    x = a * abs(s) ** (2 / n)
    yc = 0.5 * (yf + yb)
    y = yc - (yc - yf) * abs(c) ** (2 / n) if c > 0 else yc + (yb - yc) * abs(c) ** (2 / n)
    return Vector((x, y, z))


def build_cage(sole_drop, trunk):
    """The half cage (x >= 0) as a bmesh, and the named vertex lists."""
    bm = bmesh.new()
    V = lambda co: bm.verts.new(co)  # noqa: E731
    rings = {}
    (hy, hz), (hry, hrz), (hx0, hx1, hx2) = ARM_HOLE
    hole = [V((hx0 if dz < 0 else (hx2 if dz > 0 else hx1), hy + hry * dy, hz + hrz * dz)) for dy, dz in OCT]
    for name, z, a, yf, yb in trunk:
        ring = []
        for k in range(7):
            if name == "armpit" and k in (2, 3, 4):
                ring.append(hole[{2: 0, 3: 1, 4: 2}[k]])
            elif name == "shoulder" and k in (2, 3, 4):
                ring.append({2: hole[7], 3: None, 4: hole[3]}[k])
            elif name == "top" and k in (2, 3, 4):
                ring.append(hole[{2: 6, 3: 5, 4: 4}[k]])
            else:
                co = trunk_vert(k, z, a, yf, yb)
                if name == "crotch" and k in CROTCH_Z:
                    co.z = CROTCH_Z[k]
                ring.append(V(co))
        rings[name] = ring
    # the neck's end ring: an ellipse on the ring's centre, sized so its subdivided edge lies near the ring
    names = [t[0] for t in trunk]
    end = []
    for k in range(7):
        th = math.radians(30 * k)
        end.append(V((0.0605 * math.sin(th), 0.047 - 0.0565 * math.cos(th), NECK_END)))
    rings["end"] = end
    names.append("end")
    for lo, hi in zip(names, names[1:]):
        A, B = rings[lo], rings[hi]
        for k in range(6):
            if (lo, hi) in (("armpit", "shoulder"), ("shoulder", "top")) and k in (2, 3):
                continue  # the arm hole
            bm.faces.new((A[k], A[k + 1], B[k + 1], B[k]))
    # arms
    prev = hole
    for x, yc, zc, ry, rz in ARM + [(WRIST_X, 0.0, 0.0, 0.0, 0.0)]:
        if x == WRIST_X:
            ring = [V((x, 0, 0)) for _ in OCT]  # placed after the wrist is measured
            rings["wrist_cage"] = ring
        else:
            ring = [V((x, yc + ry * dy, zc + rz * dz)) for dy, dz in OCT]
        for i in range(8):
            bm.faces.new((prev[i], prev[(i + 1) % 8], ring[(i + 1) % 8], ring[i]))
        prev = ring
    # legs: the first loop is the crotch ring's k = 0..6 and C
    c = V(CROTCH)
    loop = rings["crotch"][:7] + [c]
    prev = loop
    for i, (z, cx, cy, rx, ry) in enumerate(LEG):
        tw = 22.5 * i / (len(LEG) - 1)
        ring = []
        for j in range(8):
            ph = math.radians(-45 + 45 * j + tw)
            ring.append(V((cx + rx * math.sin(ph), cy - ry * math.cos(ph), z)))
        for j in range(8):
            bm.faces.new((prev[j], prev[(j + 1) % 8], ring[(j + 1) % 8], ring[j]))
        prev = ring
    # feet: the ankle ring's j at -22.5 + 45 j degrees; front four (7, 0, 1, 2) become the top, back four the sole
    role = {7: (-1.0, 0.35, 1), 0: (-0.4, 1.0, 1), 1: (0.4, 1.0, 1), 2: (1.0, 0.35, 1),
            3: (1.0, -0.6, -1), 4: (0.4, -1.0, -1), 5: (-0.4, -1.0, -1), 6: (-1.0, -0.6, -1)}
    for y, zc, tilt, w, ht, hb in FOOT:
        al = math.radians(tilt)
        v = Vector((0, -math.cos(al), math.sin(al)))
        ring = []
        for j in range(8):
            if tilt < 89:
                ph = math.radians(-22.5 + 45 * j)
                off = Vector((w * math.sin(ph), 0, 0)) + v * ((ht if math.cos(ph) > 0 else hb) * math.cos(ph))
            else:
                u, h, sgn = role[j]
                off = Vector((u * w, 0, h * (ht if sgn > 0 else hb)))
            co = Vector((FOOT_X, y, zc)) + off
            if co.z < 0.004:
                co.z -= sole_drop
            ring.append(V(co))
        for j in range(8):
            bm.faces.new((prev[j], prev[(j + 1) % 8], ring[(j + 1) % 8], ring[j]))
        prev = ring
    top = [prev[7], prev[0], prev[1], prev[2]]
    bot = [prev[6], prev[5], prev[4], prev[3]]
    for i in range(3):
        base = [top[i], top[i + 1], bot[i + 1], bot[i]]
        cen = sum((p.co for p in base), Vector()) / 4
        last = base
        for fwd, sw, sh, drop in TOE:
            f = fwd + (TOE_MID * fwd / TOE[-1][0] if i == 1 else 0.0)
            ring = []
            for p in base:
                d = p.co - cen
                co = Vector((cen.x + d.x * sw, cen.y - f, cen.z - drop + d.z * sh))
                if p in bot:
                    co.z = min(co.z, p.co.z + 0.002 + drop * 0.3)
                ring.append(V(co))
            for j in range(4):
                bm.faces.new((last[j], last[(j + 1) % 4], ring[(j + 1) % 4], ring[j]))
            last = ring
        bm.faces.new(last)
    return bm, rings


def trunk_measure(me, z):
    """The subdivided trunk at height z: half width (|x| < 0.2) and the midline's front and back y."""
    band = [v.co for v in me.vertices if abs(v.co.z - z) < 0.004 and abs(v.co.x) < 0.2]
    mid = [c for c in band if abs(c.x) < 0.012]
    return {"a": max((abs(c.x) for c in band), default=None),
            "yf": min((c.y for c in mid), default=None), "yb": max((c.y for c in mid), default=None)}


def subdivided(bm_half, name):
    """Mirrors and subdivides a half cage; returns (cage object, subdivided mesh object)."""
    me = bpy.data.meshes.new(name + "Cage")
    bm_half.to_mesh(me)
    cage = bpy.data.objects.new(name + "Cage", me)
    bpy.context.scene.collection.objects.link(cage)
    mm = cage.modifiers.new("Mirror", "MIRROR")
    mm.use_axis = (True, False, False)
    mm.use_clip = True
    mm.use_mirror_merge = True
    mm.merge_threshold = 1e-5
    dg = bpy.context.evaluated_depsgraph_get()
    full = bpy.data.meshes.new_from_object(cage.evaluated_get(dg))
    cage.modifiers.clear()
    cage.data = full
    bm = bmesh.new()
    bm.from_mesh(full)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(full)
    bm.free()
    sd = cage.modifiers.new("Subdiv", "SUBSURF")
    sd.levels = sd.render_levels = SUBDIV
    sd.quality = 3
    sd.boundary_smooth = "ALL"
    dg = bpy.context.evaluated_depsgraph_get()
    sub = bpy.data.meshes.new_from_object(cage.evaluated_get(dg))
    cage.modifiers.clear()
    obj = bpy.data.objects.new(name, sub)
    bpy.context.scene.collection.objects.link(obj)
    return cage, obj


def poles(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    out = {}
    for v in bm.verts:
        n = len(v.link_edges)
        interior = not any(e.is_boundary for e in v.link_edges)
        if interior and n != 4:
            out.setdefault(n, []).append([round(c, 3) for c in v.co])
    bm.free()
    return out


def angle_sort(verts, centre, axis):
    """Sorts a loop by its angle around an axis ('x' for the wrists, 'z' for the neck): 0 at the front (-Y)."""
    if axis == "z":
        key = lambda v: (math.atan2(v.co.x - centre[0], -(v.co.y - centre[1])) + 1e-4) % (2 * math.pi)  # noqa: E731
    else:
        key = lambda v: (math.atan2(v.co.z - centre[1], -(v.co.y - centre[0])) + 1e-4) % (2 * math.pi)  # noqa: E731
    return sorted(verts, key=key), key


def zip_loops(bm, a, ka, b, kb):
    """Joins two closed loops, both sorted by angle, with triangles in angle order (the S1 neck zip)."""
    M, N = len(a), len(b)
    angA, angB = [ka(v) for v in a], [kb(v) for v in b]
    shift = min(range(N), key=lambda j: abs(((angB[j] - angA[0] + math.pi) % (2 * math.pi)) - math.pi))
    b = b[shift:] + b[:shift]
    angB = [(x - angA[0]) % (2 * math.pi) for x in angB[shift:] + angB[:shift]]
    angA = [(x - angA[0]) % (2 * math.pi) for x in angA]
    if angB[0] > math.pi:
        angB[0] -= 2 * math.pi
    i = j = 0
    while i < M or j < N:
        a_next = angA[(i + 1) % M] + (2 * math.pi if i + 1 >= M else 0)
        b_next = angB[(j + 1) % N] + (2 * math.pi if j + 1 >= N else 0)
        if j >= N or (i < M and a_next <= b_next):
            bm.faces.new((a[i % M], a[(i + 1) % M], b[j % N]))
            i += 1
        else:
            bm.faces.new((a[i % M], b[(j + 1) % N], b[j % N]))
            j += 1


def main():
    p = argparse.ArgumentParser(prog="alien_cage.py")
    p.add_argument("--src", required=True)
    p.add_argument("--ring", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args(sys.argv[sys.argv.index("--") + 1:])
    report = {"src": args.src}
    with open(args.ring, encoding="utf-8") as fh:
        ring = json.load(fh)
    bpy.ops.wm.open_mainfile(filepath=args.src)
    arm = bpy.data.objects["CharacterArmature"]
    old = bpy.data.objects["Body"]
    if arm.animation_data:
        arm.animation_data.action = None
    arm.data.pose_position = "REST"
    bpy.context.view_layer.update()

    # The wrist: S1c's section just beyond the ring's plane, measured: its centre and half extents in y and z.
    sec = [v.co for v in old.data.vertices if abs(v.co.x - (WRIST_X + WRIST_GAP)) < 0.004]
    wy = (max(c.y for c in sec) + min(c.y for c in sec)) / 2
    wz = (max(c.z for c in sec) + min(c.z for c in sec)) / 2
    wry = (max(c.y for c in sec) - min(c.y for c in sec)) / 2
    wrz = (max(c.z for c in sec) - min(c.z for c in sec)) / 2
    wrist = {"count": WRIST_N, "x": WRIST_X, "centre": [round(wy, 5), round(wz, 5)],
             "semi_axes": [round(wry, 5), round(wrz, 5)],
             "order": "index k at angle 2*pi*k/count around +X from the front (-Y) towards up (+Z); the right "
                      "wrist is the mirror (x -> -x)",
             "axes": "Blender (Z up, front -Y); glTF/Godot: (x, z, -y)"}
    wrist["loop"] = [[WRIST_X, round(wy - wry * math.cos(2 * math.pi * k / WRIST_N), 5),
                      round(wz + wrz * math.sin(2 * math.pi * k / WRIST_N), 5)] for k in range(WRIST_N)]

    # 1-2. The cage, mirrored and subdivided; the soles lowered until the subdivided sole is at z = 0.
    # The trunk's rings are fitted the same way: subdivision pulls a ring towards its neighbours (the belly's peak
    # comes back about a third), so each ring's cage numbers are corrected by the subdivided body's error against the
    # u1 target, until it is under FIT_TOL.
    drop = 0.0
    trunk = [list(t) for t in TRUNK]
    for it in range(FIT_ITERS):
        bm, rings = build_cage(drop, trunk)
        for (dy, dz), v in zip(OCT, rings["wrist_cage"]):  # a subdivided octagon's edge lies at 0.902 of its radius
            v.co = Vector((WRIST_X, wy + wry * dy / 0.902, wz + wrz * dz / 0.902))
        cage_faces = len(bm.faces)
        cage, body = subdivided(bm, "BodyNew")
        bm.free()
        low = min(v.co.z for v in body.data.vertices)
        worst = 0.0
        for row, target in zip(trunk, TRUNK):
            name, z = row[0], row[1]
            if name not in FIT:
                continue
            m = trunk_measure(body.data, z)
            for i, key in ((2, "a"), (3, "yf"), (4, "yb")):
                if key in FIT[name] and m[key] is not None:
                    err = target[i] - m[key]
                    worst = max(worst, abs(err))
                    row[i] += err
        report.setdefault("fit_iterations", []).append({"sole_drop": round(drop, 5), "lowest": round(low, 5),
                                                        "trunk_worst_mm": round(worst * 1000, 2)})
        if (abs(low) < 0.0003 and worst < FIT_TOL) or it == FIT_ITERS - 1:
            break
        drop += low / 0.75
        for o in (cage, body):
            me = o.data
            bpy.data.objects.remove(o)
            bpy.data.meshes.remove(me)
    report["cage_trunk"] = [[t[0]] + [round(x, 4) for x in t[1:]] for t in trunk]
    report["cage"] = {"half_faces": cage_faces, "faces": len(cage.data.polygons), "verts": len(cage.data.vertices),
                      "poles": {str(k): len(v) for k, v in poles(cage.data).items()},
                      "pole_positions": poles(cage.data)}
    cage_me = cage.data
    cage_me.name = "BodyCage"
    cage_me.use_fake_user = True  # kept in the file as mesh data only, so no export picks it up
    bpy.data.objects.remove(cage)

    # 3. Rings. The body's open ends: the neck (z > 1.3) and the two wrists.
    me = body.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bnd = {v for e in bm.edges if e.is_boundary for v in e.verts}
    neck = [v for v in bnd if v.co.z > 1.3]
    cy = ring["centre"][1]
    ax, ay = (s / 0.98 for s in ring["semi_axes"])  # loop_below's semi-axes
    ax, ay = ax / 0.98, ay / 0.98
    neck, kn = angle_sort(neck, (0.0, cy), "z")
    zb = ring["z"] - 2 * ring["step"]
    err = 0.0
    nn = len(neck)
    for k, v in enumerate(neck):
        t = 2 * math.pi * k / nn
        new = Vector((ax * math.sin(t), cy - ay * math.cos(t), zb))
        err = max(err, (new - v.co).length)
        v.co = new
    report["neck"] = {"open_end": nn, "snap_max_mm": round(err * 1000, 2)}
    lower = [bm.verts.new(c) for c in ring["loop_below"]]
    top = [bm.verts.new(c) for c in ring["loop"]]
    N = len(lower)
    for k in range(N):
        bm.faces.new((lower[k], lower[(k + 1) % N], top[(k + 1) % N], top[k]))
    step = nn // N
    for i in range(N):
        a0, a1, a2 = neck[step * i], neck[step * i + 1], neck[(step * i + 2) % nn]
        bm.faces.new((a0, a1, lower[i]))
        bm.faces.new((a1, a2, lower[(i + 1) % N], lower[i]))
    wr = {}
    for sx in (1, -1):
        loopv = [v for v in bnd if v.co.x * sx > 0.5]
        loopv, kw = angle_sort(loopv, (wy, wz), "x")
        e = 0.0
        for k, v in enumerate(loopv):
            t = 2 * math.pi * k / len(loopv)
            new = Vector((sx * WRIST_X, wy - wry * math.cos(t), wz + wrz * math.sin(t)))
            e = max(e, (new - v.co).length)
            v.co = new
        wr[sx] = ([v.index for v in loopv], kw)
        report.setdefault("wrist", {})["l" if sx > 0 else "r"] = {"open_end": len(loopv), "snap_max_mm": round(e * 1000, 2)}
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    ring_ids = {v.index for v in me.vertices if v.co.z > ring["z"] - ring["step"] - 1e-4}

    # 4. Weights: from S1c's body by nearest-face interpolation.
    for g in old.vertex_groups:
        body.vertex_groups.new(name=g.name)
    dt = body.modifiers.new("Weights", "DATA_TRANSFER")
    dt.object = old
    dt.use_vert_data = True
    dt.data_types_verts = {"VGROUP_WEIGHTS"}
    dt.vert_mapping = "POLYINTERP_NEAREST"
    dt.layers_vgroup_select_src = "ALL"
    dt.layers_vgroup_select_dst = "NAME"
    with bpy.context.temp_override(object=body, active_object=body):
        bpy.ops.object.modifier_apply(modifier=dt.name)
    nbody = len(me.vertices)

    # The hands: S1c's mesh beyond WRIST_X + WRIST_GAP, joined and zipped to the wrist rings.
    hands = old.copy()
    hands.data = old.data.copy()
    hands.modifiers.clear()
    bpy.context.scene.collection.objects.link(hands)
    hm = hands.data
    bm = bmesh.new()
    bm.from_mesh(hm)
    xc = WRIST_X + WRIST_GAP
    for sx in (1, -1):
        side = [f for f in bm.faces if all(v.co.x * sx > 0.3 for v in f.verts)]
        geom = list({v for f in side for v in f.verts}) + list({e for f in side for e in f.edges}) + side
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(sx * xc, 0, 0), plane_no=(sx, 0, 0))
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if abs(v.co.x) < xc - 1e-5], context="VERTS")
    bm.to_mesh(hm)
    bm.free()
    report["hands_verts"] = len(hm.vertices)
    for o in bpy.data.objects:
        o.select_set(False)
    body.select_set(True)
    hands.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    me = body.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    for sx in (1, -1):
        cut = [v for v in bm.verts if v.index >= nbody and abs(v.co.x - sx * xc) < 1e-4
               and any(e.is_boundary for e in v.link_edges)]
        cut, kc = angle_sort(cut, (wy, wz), "x")
        ringv = [bm.verts[i] for i in wr[sx][0]]
        zip_loops(bm, ringv, wr[sx][1], cut, kc)
        report["wrist"]["l" if sx > 0 else "r"]["hand_cut"] = len(cut)
    # S1c's right hand keeps an open hole where its Little finger was removed: closed here.
    hole = [e for e in bm.edges if e.is_boundary and abs(e.verts[0].co.x) > 0.65]
    report["hand_hole_edges_closed"] = len(hole)
    if hole:  # walk the loop and cap it with one face, triangulated
        loop = [hole[0].verts[0]]
        e = hole[0]
        while True:
            nxt = e.other_vert(loop[-1])
            if nxt is loop[0]:
                break
            loop.append(nxt)
            e = next(x for x in nxt.link_edges if x is not e and x in hole)
        # a fan around a new centre vertex (the loop's chords may already be edges of the hand), weights averaged
        dl = bm.verts.layers.deform.verify()
        c = bm.verts.new(sum((v.co for v in loop), Vector()) / len(loop))
        for v in loop:
            for g, w in v[dl].items():
                c[dl][g] = c[dl].get(g, 0.0) + w / len(loop)
        for i in range(len(loop)):
            bm.faces.new((loop[i], loop[(i + 1) % len(loop)], c))
        hv = set(loop) | {c}
        for _ in range(3):
            bmesh.ops.smooth_vert(bm, verts=list(hv), factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    # The weld's band: eased across in y and z (lengths along the arm kept), so the hand's and the arm's sections
    # meet without a step.
    band_w, passes = WRIST_SMOOTH
    band = [v for v in bm.verts if abs(abs(v.co.x) - WRIST_X - WRIST_GAP / 2) < band_w]
    for _ in range(passes):
        bmesh.ops.smooth_vert(bm, verts=band, factor=0.5, use_axis_x=False, use_axis_y=True, use_axis_z=True)
    # Loose parts and open edges (only the neck ring's top should be open).
    seen, parts = set(), 0
    for v0 in bm.verts:
        if v0 in seen:
            continue
        parts += 1
        stack = [v0]
        seen.add(v0)
        while stack:
            for e in stack.pop().link_edges:
                for o in e.verts:
                    if o not in seen:
                        seen.add(o)
                        stack.append(o)
    report["loose_parts"] = parts
    report["open_edges_below_ring"] = [[round(c, 3) for c in (e.verts[0].co + e.verts[1].co) / 2]
                                       for e in bm.edges if e.is_boundary and e.verts[0].co.z < ring["z"] - 1e-4]
    deform = bm.verts.layers.deform.verify()
    gi = {g.name: g.index for g in body.vertex_groups}
    # The joints: each cage vertex's weights blended with its neighbours' (the hands and the rings keep theirs).
    free = [v for v in bm.verts if v.index < nbody and v.index not in ring_ids]
    for _ in range(WEIGHT_SMOOTH):
        new = []
        for v in free:
            acc = {}
            nbs = [e.other_vert(v) for e in v.link_edges]
            for src, fw in [(v, 0.5)] + [(n, 0.5 / len(nbs)) for n in nbs]:
                for g, w in src[deform].items():
                    acc[g] = acc.get(g, 0.0) + fw * w
            new.append(acc)
        for v, acc in zip(free, new):
            d = v[deform]
            for g in list(d.keys()):
                del d[g]
            for g, w in acc.items():
                d[g] = w
    for v in bm.verts:
        d = v[deform]
        if v.index in ring_ids:
            for g in list(d.keys()):
                del d[g]
            for n, w in RING_W.items():
                d[gi[n]] = w
            continue
        top4 = sorted(d.items(), key=lambda kv: -kv[1])[:4]
        tot = sum(w for _, w in top4) or 1.0
        for g in list(d.keys()):
            del d[g]
        for g, w in top4:
            if w / tot > 0.005:
                d[g] = w / tot
    little = [gi[n] for n in gi if "Little" in n]
    leak = sum(1 for v in bm.verts if any(g in v[deform] for g in little))
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    report["little_weighted_verts"] = leak

    # The character: the new body replaces S1c's.
    old_name_mat = old.data.materials[0] if old.data.materials else None
    bpy.data.objects.remove(old)
    body.name = body.data.name = "Body"
    body.parent = arm
    body.modifiers.clear()
    mod = body.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    me.materials.clear()
    if old_name_mat:
        me.materials.append(old_name_mat)
    for poly in me.polygons:
        poly.material_index = 0
    if me.has_custom_normals:
        with bpy.context.temp_override(object=body, active_object=body, selected_editable_objects=[body]):
            bpy.ops.mesh.customdata_custom_splitnormals_clear()
    for uv in list(me.uv_layers):
        me.uv_layers.remove(uv)
    me.uv_layers.new(name="UVMap")
    arm.data.pose_position = "POSE"
    me.calc_loop_triangles()
    report["body"] = {"verts": len(me.vertices), "tris": len(me.loop_triangles),
                      "height": round(max(v.co.z for v in me.vertices), 4),
                      "lowest": round(min(v.co.z for v in me.vertices), 5)}
    bm = bmesh.new()
    bm.from_mesh(me)
    report["body"]["open_edges"] = sum(1 for e in bm.edges if e.is_boundary and e.verts[0].co.z < 1.385)
    report["body"]["non_manifold_edges"] = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    bm.free()
    # u1's measures against the body's: the trunk's front width (|x| < 0.2 at the midline's height) and midline depth.
    meas = {}
    for name, z, a, yf, yb in TRUNK:
        band = [v.co for v in me.vertices if abs(v.co.z - z) < 0.006 and abs(v.co.x) < 0.2]
        mid = [c for c in band if abs(c.x) < 0.01]
        if band and mid:
            meas[name] = {"z": z, "target_half_width": a, "half_width": round(max(abs(c.x) for c in band), 4),
                          "target_front_back": [yf, yb],
                          "front_back": [round(min(c.y for c in mid), 4), round(max(c.y for c in mid), 4)]}
    report["fit"] = meas
    # the midline's side profile every 2 cm (the front and back y) and the trunk's half width, for the u1 comparison
    report["profile"] = []
    for zc in range(70, 138, 2):
        m = trunk_measure(me, zc / 100)
        report["profile"].append([zc / 100] + [None if m[k] is None else round(m[k], 4) for k in ("a", "yf", "yb")])
    with open(f"{args.out}/wrist_ring.json", "w", encoding="utf-8") as fh:
        json.dump(wrist, fh, indent=1)
    with open(f"{args.out}/neck_ring.json", "w", encoding="utf-8") as fh:
        json.dump(ring, fh, indent=1)
    with open(f"{args.out}/cage.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    bpy.ops.wm.save_as_mainfile(filepath=f"{args.out}/alien_body.blend")
    print("cage:", json.dumps({k: report[k] for k in ("body", "neck", "wrist", "fit_iterations", "loose_parts",
                                                      "open_edges_below_ring", "little_weighted_verts")}))


if __name__ == "__main__":
    main()
