"""The alien skin's detail sculpt and its bake (art #196, step M2): a high-resolution copy of `Body` with the fine
detail of a modern stylised character, baked onto `Body`'s texture UV (alien_uv.py) as a tangent-space normal map
and AO, curvature and thickness maps; then the kit exported with the normal map on the skin.

  blender -b --factory-startup --python-exit-code 1 --python tools/blender/alien_detail.py -- \
      --character <M2/uv/build/alien_character.blend> --out <M2> --stage high|bake|export [--size 4096 --aux 2048] \
      [--kit <the kit's export folder: character.json and the mouth atlases; export only>]

Stages (each a separate run, so none blocks for long; each reads the one before from --out):
- `high`: the copy (`Body_high`, the rest pose, no armature) subdivided HIGH["levels"] times (Catmull-Clark, about
  two million quads), then moved along its normals by the joint and face creases of alien_detail_geom.CREASES (a
  Ricker profile, soft valleys with slight shoulders, no volume change; at most MAX_DISP_MM): finger joints (three
  fine lines on the back, one deeper on the palm side), wrists (palm side), elbows (inner side), knees (the back),
  armpits, the neck (two rings in front, one at the nape), a fold above each eye socket and a softer one below, a
  groove round the mouth, the philtrum, a slight nasolabial line from beside the nostrils' place down past the mouth's
  corners, the belly's centre line. Each crease is a field of the rest position: its distance from a joint plane (the
  bone's own axis), a ring (the eyes, the neck) or a curve (the face), faded by side (the normal) and by the part's
  bone weights (point attributes written on the low mesh before subdividing, so they interpolate). The fine grain
  (pores and a soft orange peel, alien_detail_geom.GRAIN, stronger on the face) is a bump on the copy's material:
  Cycles bakes the shading normal, so it lands in the normal map without more polygons. The mean curvature of the
  displaced surface is stored as a colour attribute for the curvature bake. Saves high/alien_high.blend.
- `bake`: Cycles, selected to active from `Body_high` to `Body` (cage extrusion BAKE["cage"], ray distance
  BAKE["ray"]): `normal.png` (tangent space, OpenGL +Y, --size), `ao.png` (BAKE["ao_dist"], no part shown, M9),
  `curvature.png` (0.5 flat, brighter convex, darker concave) and `thickness.png` (AO from inside: white thick, dark
  thin within BAKE["thick_dist"]) at --aux, each with a 1024 px preview, into bake/.
- `export`: `Body`'s material `alien_hue` takes `normal.png` through a Normal Map node on `UVMap`, so the GLB's skin
  has `normalTexture` (texCoord 0) and the mesh tangents; export/alien_character.glb with character.json beside it.

M2b (art #196): `--sculpt m2|m2b|m6c|m8b` (high, grid; default m2, the shipped sculpt) picks alien_detail_geom.SCULPTS (the
creases, grain, the jaw's `soften` and the curvature colour's smoothing), `--settings JSON` goes over it; `--cage
capped` (bake) bakes all four maps through M3a's capped cage (alien_texture's cage helpers) instead of the uniform
extrusion; `--stage grid --variants FILE --vout DIR` subdivides once and writes per variant (name: sculpt settings)
`normal.png` (--size) and `curvature.png` (--aux) through the capped cage, for alien_texture_review.py --grid.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_detail_geom as G  # noqa: E402
import export_glb  # noqa: E402

HIGH = {"levels": 3}
BAKE = {"cage": 0.002, "ray": 0.004, "margin": 16, "normal_samples": 8, "ao_samples": 64, "ao_dist": 0.05,
        "thick_samples": 64, "thick_dist": 0.06}  # the curvature colour: alien_detail_geom.CURVATURE
SHOWN = ()  # alien_ao.SHOWN: no part in the AO bake (M7: no mouth piece; M9: no eye either)
CHAINS = ("Index", "Middle", "Ring")  # the thumb leaves its bones' line (alien_cage.THUMB_DIR): no joint planes
FINGER_K = 0.984  # alien_cage.FINGER_K: the mesh's finger joints sit at J0 + K (J - J0) of the bones'
UV_LAYER = "UVMap"


def finger_k(ob) -> float:
    """The character's FINGER_K: the cage's own (alien_cage.py writes its digits into Body["prime_digits"]; PR #240's
    review: a --digits variant must not get the default's joint planes), else FINGER_K."""
    if "prime_digits" in ob.keys():
        return float(json.loads(ob["prime_digits"])["FINGER_K"])
    return FINGER_K


def args():
    p = argparse.ArgumentParser()
    p.add_argument("--character", default="", help="high, export, grid: the UV'd character (.blend)")
    p.add_argument("--out", required=True)
    p.add_argument("--stage", required=True, choices=("high", "bake", "export", "grid"))
    p.add_argument("--size", type=int, default=4096)
    p.add_argument("--aux", type=int, default=2048)
    p.add_argument("--kit", default="", help="export: the folder of the kit's character.json and mouth atlases")
    p.add_argument("--sculpt", default="m2", choices=tuple(G.SCULPTS), help="high, grid: alien_detail_geom.SCULPTS")
    p.add_argument("--settings", default="", help="high: a JSON object over the sculpt (alien_detail_geom.sculpt)")
    p.add_argument("--cage", default="uniform", choices=("uniform", "capped"),
                   help="bake: M2's uniform extrusion, or the capped cage of alien_texture_geom.cage_offset (M3a)")
    p.add_argument("--variants", default="", help="grid: a JSON file {name: sculpt settings} -> --vout/<name>/normal.png")
    p.add_argument("--vout", default="")
    a = p.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    if a.stage in ("high", "export", "grid") and not a.character:
        p.error(f"--stage {a.stage} needs --character")
    if a.stage == "grid" and not (a.variants and a.vout):
        p.error("--stage grid needs --variants and --vout")
    return a


def ss(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def ricker(s, w):
    q = (s / w) ** 2
    return -(1.0 - q) * np.exp(-0.5 * q)  # alien_detail_geom.crease


def group_weights(obj, names):
    """{name: per-vertex weight array} for the vertex groups whose names start with any of names' entries."""
    me = obj.data
    idx = {g.index: g.name for g in obj.vertex_groups}
    out = {n: np.zeros(len(me.vertices)) for n in names}
    for v in me.vertices:
        for g in v.groups:
            gn = idx[g.group]
            for n in names:
                if gn.startswith(n):
                    out[n][v.index] += g.weight
    return out


def put_attr(me, name, values):
    if name in me.attributes:
        me.attributes.remove(me.attributes[name])
    a = me.attributes.new(name, "FLOAT", "POINT")
    a.data.foreach_set("value", np.asarray(values, dtype=np.float32))


def get_attr(me, name):
    a = np.empty(len(me.vertices), dtype=np.float32)
    me.attributes[name].data.foreach_get("value", a)
    return a.astype(np.float64)


def world_bbox(o):
    from mathutils import Vector as V
    pts = [o.matrix_world @ V(c) for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def landmarks(arm):
    """Joints (rest, world) and face landmarks the creases hang on."""
    mw = arm.matrix_world
    bones = arm.data.bones
    j = {}
    for b in bones:
        j[b.name] = (mw @ b.head_local, (mw @ b.tail_local - mw @ b.head_local).normalized())
    face = {}
    for s in ("L", "R"):
        ball = bpy.data.objects[f"eye_bored_ball_{s}"]
        lo, hi = world_bbox(ball)
        face[f"eye_{s}"] = ((lo + hi) / 2, max(hi - lo) / 2)
    lo, hi = world_bbox(bpy.data.objects["mouth_frog_rest"])
    face["mouth"] = ((lo + hi) / 2, (hi.x - lo.x) / 2, (hi.z - lo.z) / 2, lo.y)
    return j, face


# ---------------------------------------------------------------- the high copy
def build_high():
    """Body's copy `Body_high` in the rest pose, its weight attributes written, subdivided HIGH["levels"] times; returns
    (body, arm, hi, P, N, edges) with the subdivided positions, normals and edges (before any sculpt)."""
    body = bpy.data.objects["Body"]
    arm = body.find_armature()
    arm.data.pose_position = "REST"
    bpy.context.view_layer.update()
    hi = body.copy()
    hi.data = body.data.copy()
    hi.name = hi.data.name = "Body_high"
    bpy.context.scene.collection.objects.link(hi)
    hi.parent = None
    hi.matrix_world = body.matrix_world.copy()
    for m in list(hi.modifiers):
        hi.modifiers.remove(m)
    lw = group_weights(body, ["Head", "Neck", "LeftHand", "RightHand"] + [f"{s}{c}" for s in ("Left", "Right") for c in CHAINS])
    me = hi.data
    head = np.clip(lw["Head"] + 0.5 * lw["Neck"], 0, 1)
    put_attr(me, "w_head", head)
    for s in ("Left", "Right"):
        put_attr(me, f"w_{s}Hand", lw[f"{s}Hand"])
        for c in CHAINS:
            put_attr(me, f"w_{s}{c}", lw[f"{s}{c}"])
    hi.vertex_groups.clear()  # read above; two million vertices need none of the 53 groups
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    hi.select_set(True)
    bpy.context.view_layer.objects.active = hi
    mod = hi.modifiers.new("sub", "SUBSURF")
    mod.levels = mod.render_levels = HIGH["levels"]
    t = time.time()
    bpy.ops.object.modifier_apply(modifier=mod.name)
    print(f"M2 subdivided {len(me.vertices)} verts {len(me.polygons)} faces {time.time() - t:.0f}s", flush=True)
    n = len(me.vertices)
    P = np.empty(n * 3)
    me.vertices.foreach_get("co", P)
    P = P.reshape(-1, 3)
    N = np.empty(n * 3)
    me.vertex_normals.foreach_get("vector", N)
    N = N.reshape(-1, 3)
    ed = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get("vertices", ed)
    return body, arm, hi, P, N, ed.reshape(-1, 2)


def jaw_region(P, me, joints, face):
    """The region `soften` works in (0..1): the head and neck below the rest mouth's lower edge (less 3 mm) down to
    4 cm under the Neck joint, faded over 1 cm at each end."""
    m, _hw, hh, _my = face["mouth"]
    z_top = m.z - hh - 0.003
    z_low = joints["Neck"][0].z - 0.04
    z = P[:, 2]
    return (np.clip(get_attr(me, "w_head") * 2.0, 0, 1) * (1 - ss(z_top - 0.01, z_top, z)) * ss(z_low, z_low + 0.01, z))


def spread(w, ed, passes):
    """The weight grown over the mesh: each pass a vertex takes the larger of its own and its neighbours' mean, so a
    thin band of high curvature (the crumpled fold under the jaw) widens by about an edge per pass."""
    n = len(w)
    deg = np.bincount(ed.ravel(), minlength=n).astype(float)
    deg[deg == 0] = 1
    a, b = ed[:, 0], ed[:, 1]
    for _ in range(passes):
        w = np.maximum(w, (np.bincount(a, w[b], n) + np.bincount(b, w[a], n)) / deg)
    return w


def relax(P, N, ed, weight, s):
    """`soften`: s["passes"] Laplacian passes along the normal (each moves a vertex `step` of the way to its
    neighbours' mean, times its weight), the total move clipped to s["max_mm"]. Returns the new positions and the
    move (m) per vertex."""
    n = len(P)
    deg = np.bincount(ed.ravel(), minlength=n).astype(float)
    deg[deg == 0] = 1
    move = np.zeros(n)
    cap = s["max_mm"] / 1000.0
    a, b = ed[:, 0], ed[:, 1]
    for _ in range(int(s["passes"])):
        Q = P + N * move[:, None]
        mean = np.stack([(np.bincount(a, Q[b, k], n) + np.bincount(b, Q[a, k], n)) / deg for k in range(3)], 1)
        move = np.clip(move + s["step"] * weight * ((mean - Q) * N).sum(1), -cap, cap)
    return P + N * move[:, None], move


def sculpt_high(hi, arm, P, N, ed, S, report_extra=None):
    """Sculpt S (alien_detail_geom.sculpt) on the subdivided copy from its unsculpted positions P and normals N:
    `soften` under the jaw, the creases, the curvature colour `curv`, the grain material. Returns the report."""
    me = hi.data
    joints, face = landmarks(arm)
    soft = S["soften"]
    P1, move, w = P, np.zeros(len(P)), None
    if soft["passes"] > 0:
        c0 = curvature(me, P, ed, S["curvature"])
        w = ss(soft["lo"], soft["hi"], np.abs(c0 - 0.5) / 0.5)  # G.edge_weight
        w = spread(w, ed, int(soft["spread"])) * jaw_region(P, me, joints, face)
        P1, move = relax(P, N, ed, w, soft)
    D, terms = displacement(P1, N, me, joints, face, S["creases"])
    cap = G.MAX_DISP_MM / 1000.0
    D = np.clip(D, -cap, cap)
    P2 = P1 + N * D[:, None]
    me.vertices.foreach_set("co", P2.ravel())
    me.update()
    curv = curvature(me, P2, ed, S["curvature"], w)
    if "curv" in me.color_attributes:
        me.color_attributes.remove(me.color_attributes["curv"])
    ca = me.color_attributes.new("curv", "FLOAT_COLOR", "POINT")
    ca.data.foreach_set("color", np.stack([curv, curv, curv, np.ones(len(P))], 1).astype(np.float32).ravel())
    g = S["grain"]
    put_attr(me, "m_grain", g["body"] + (g["face"] - g["body"]) * get_attr(me, "w_head"))
    hi.data.materials.clear()
    hi.data.materials.append(high_material(g))
    hi.hide_render = False
    rep = {"high": {"levels": HIGH["levels"], "vertices": len(P), "faces": len(me.polygons)},
           "disp_mm": {"min": round(float(D.min() * 1000), 3), "max": round(float(D.max() * 1000), 3),
                       "moved_over_0p05mm": int((np.abs(D) > 5e-5).sum())},
           "soften_mm": {"min": round(float(move.min() * 1000), 3), "max": round(float(move.max() * 1000), 3),
                         "moved_over_0p1mm": int((np.abs(move) > 1e-4).sum())},
           "terms_mm_min": terms, "curv_p1_p99": [round(float(np.percentile(curv, 1)), 3), round(float(np.percentile(curv, 99)), 3)],
           "sculpt": S, "landmarks": {k: [round(x, 4) for x in v[0]] for k, v in face.items()}}
    rep.update(report_extra or {})
    return rep


def sculpt_settings(a):
    return G.sculpt(a.sculpt, json.loads(a.settings) if a.settings else None)


def stage_high(a, out):
    S = sculpt_settings(a)
    body, arm, hi, P, N, ed = build_high()
    rep = sculpt_high(hi, arm, P, N, ed, S, {"sculpt_name": a.sculpt})
    arm.data.pose_position = "POSE"
    (out / "high").mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "high" / "alien_high.blend"))
    (out / "high" / "high_report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8", newline="\n")
    print("M2 HIGH " + json.dumps({k: rep[k] for k in ("high", "disp_mm", "soften_mm", "terms_mm_min", "curv_p1_p99")}),
          flush=True)


def displacement(P, N, me, joints, face, C=None):
    """The creases' sum (m) per vertex of the high copy, and each term's deepest value (mm) for the report."""
    D = np.zeros(len(P))
    terms = {}
    C = G.CREASES if C is None else C

    def add(name, s, mask, key=None):
        c = C[key or name]
        d = np.zeros(len(P))
        for off in G.line_offsets(c["lines"], c["gap"]):
            d += ricker(s - off / 1000.0, c["width"] / 1000.0)
        d *= c["depth"] / 1000.0 * mask
        D[:] += d
        terms[name] = round(float(d.min() * 1000), 3)

    def plane(jname, radius, at=None):
        p, dd = joints[jname]
        p = at if at is not None else p
        r = P - np.array(p)
        s = r @ np.array(dd)
        rad = np.linalg.norm(r - s[:, None] * np.array(dd), axis=1)
        return s, 1.0 - ss(0.6 * radius, radius, rad)

    fk = finger_k(bpy.data.objects["Body"])  # the low mesh carries the cage's digits
    up = np.array([0.0, 0.0, 1.0])
    front = np.array([0.0, -1.0, 0.0])
    for side in ("Left", "Right"):
        hand = get_attr(me, f"w_{side}Hand")
        for c in CHAINS:
            w = get_attr(me, f"w_{side}{c}")
            j0 = joints[f"{side}{c}Proximal"][0]
            for k, seg in enumerate(("Proximal", "Intermediate", "Distal")):
                s, near = plane(f"{side}{c}{seg}", 0.022, j0 + (joints[f"{side}{c}{seg}"][0] - j0) * fk)
                wm = ss(0.15, 0.5, w + (hand if k == 0 else 0.0)) * near
                dors = ss(-0.1, 0.35, N @ up)
                add(f"knuckle_dorsal_{side}{c}{k}", s, wm * dors, "knuckle_dorsal")
                add(f"knuckle_palm_{side}{c}{k}", s, wm * (1 - dors), "knuckle_palm")
        s, near = plane(f"{side}Hand", 0.05)
        add(f"wrist_{side}", s + 0.004, near * ss(0.0, 0.4, -(N @ up)), "wrist")
        s, near = plane(f"{side}LowerArm", 0.07)
        add(f"elbow_{side}", s, near * ss(0.1, 0.6, N @ front), "elbow")
        s, near = plane(f"{side}LowerLeg", 0.09)
        add(f"knee_{side}", s, near * ss(0.1, 0.6, -(N @ front)), "knee")
        s, near = plane(f"{side}UpperArm", 0.08)
        add(f"armpit_{side}", s - 0.025, near * ss(0.2, 0.7, -(N @ up)), "armpit")
    # the neck: rings round the Neck bone's axis
    nk, nd = joints["Neck"]
    hd, _ = joints["Head"]
    s, near = plane("Neck", 0.095)
    mid = 0.5 * (hd - nk).length
    hw = ss(-0.1, 0.5, N @ front)
    add("neck_front", s - mid, near * hw, "neck_front")
    add("neck_back", s - mid - 0.01, near * ss(0.2, 0.7, -(N @ front)), "neck_back")
    # the eyes: a fold above each socket and a softer one below
    for s_ in ("L", "R"):
        e, rb = face[f"eye_{s_}"]
        r = P - np.array(e)
        dist = np.linalg.norm(r, axis=1)
        fwd = ss(-0.2, 0.4, (r @ front) / np.maximum(dist, 1e-9))
        upper = ss(-0.15, 0.35, r[:, 2] / max(rb, 1e-6))
        add(f"lid_fold_{s_}", dist - 1.42 * rb, fwd * upper * (dist < 2.2 * rb), "lid_fold")
        add(f"under_eye_{s_}", dist - 1.50 * rb, fwd * (1 - upper) * ss(-0.9, -0.4, r[:, 2] / rb) * (dist < 2.2 * rb), "under_eye")
    # the mouth: a groove round the rest mouth's outline, the philtrum, the nasolabial lines
    m, hw_m, hh_m, my = face["mouth"]
    dx, dz = P[:, 0] - m.x, P[:, 2] - m.z
    on_face = ss(0.2, 0.6, N @ front) * (P[:, 1] < my + 0.03) * ss(1.30, 1.38, P[:, 2])
    ax_, bz = hw_m + 0.0015, hh_m + 0.002
    ell = np.sqrt((dx / ax_) ** 2 + (dz / bz) ** 2)
    # below the mouth and round its corners only: over the upper lip the ring read as a moustache line (M2 review)
    add("lip_groove", (ell - 1.0) * min(ax_, bz), on_face * (ell < 2.0) * (1 - ss(0.0, 0.5 * bz, dz)), "lip_groove")
    phil = ss(bz, bz + 0.003, dz) * (1 - ss(bz + 0.010, bz + 0.016, dz))
    add("philtrum", np.abs(dx), on_face * phil, "philtrum")
    for sg in (-1.0, 1.0):
        a0 = np.array([sg * 0.55 * hw_m, bz + 0.016])
        a1 = np.array([sg * (hw_m + 0.008), -0.35 * bz])
        q = np.stack([dx, dz], 1)
        t = np.clip(((q - a0) @ (a1 - a0)) / ((a1 - a0) @ (a1 - a0)), 0, 1)
        dist = np.linalg.norm(q - (a0 + t[:, None] * (a1 - a0)), axis=1)
        fade = ss(0.0, 0.25, t) * (1 - ss(0.8, 1.0, t))
        add(f"nasolabial_{'L' if sg > 0 else 'R'}", dist, on_face * fade, "nasolabial")
    # the belly's centre line
    belly = ss(0.4, 0.8, N @ front) * ss(0.96, 1.02, P[:, 2]) * (1 - ss(1.18, 1.24, P[:, 2]))
    add("belly_line", np.abs(P[:, 0]), belly * (np.abs(P[:, 0]) < 0.03), "belly_line")
    return D, terms


def curvature(me, P, ed, cs, heavy=None):
    """The mean curvature's sign and size per vertex (umbrella Laplacian along the normal over the mean squared edge),
    smoothed cs["smooth"] times, mapped to 0.5 + 0.5 tanh(c / cs["scale"]) (alien_detail_geom.CURVATURE). The normals
    are the mesh's current ones (P set on it, or its unsculpted state). heavy (0..1 per vertex, M2b: the soften
    weight) blends toward cs["jaw_smooth"] passes more."""
    n = len(P)
    N = np.empty(n * 3)
    me.vertex_normals.foreach_get("vector", N)
    N = N.reshape(-1, 3)
    a, b = ed[:, 0], ed[:, 1]
    deg = np.bincount(ed.ravel(), minlength=n).astype(float)
    deg[deg == 0] = 1
    acc = np.stack([np.bincount(a, P[b, k], n) + np.bincount(b, P[a, k], n) for k in range(3)], 1)
    L = acc / deg[:, None] - P
    l2 = ((P[a] - P[b]) ** 2).sum(1)
    el = (np.bincount(a, l2, n) + np.bincount(b, l2, n)) / deg
    c = -2.0 * (L * N).sum(1) / np.maximum(el, 1e-14)  # convex (bulging) positive: the neighbours lie below
    for _ in range(int(cs["smooth"])):
        s = np.bincount(a, c[b], n) + np.bincount(b, c[a], n)
        c = 0.5 * c + 0.5 * s / deg
    if heavy is not None and cs.get("jaw_smooth", 0) > 0:  # M2b: far smoother where `soften` worked (the jaw's fold)
        h = c.copy()
        for _ in range(int(cs["jaw_smooth"])):
            s = np.bincount(a, h[b], n) + np.bincount(b, h[a], n)
            h = 0.5 * h + 0.5 * s / deg
        c = c + np.clip(heavy, 0, 1) * (h - c)
    return 0.5 + 0.5 * np.tanh(c / cs["scale"])


def high_material(g=None):
    """The copy's material: a plain Principled whose normal is bumped by the grain (pores: Voronoi pits, the orange
    peel: noise), scaled by the `m_grain` attribute; emission from the `curv` colour for the curvature bake."""
    g = G.GRAIN if g is None else g
    mt = bpy.data.materials.new("alien_high")
    mt.use_nodes = True
    nt = mt.node_tree
    ns, ln = nt.nodes, nt.links
    bsdf = ns["Principled BSDF"]
    tc = ns.new("ShaderNodeTexCoord")
    vor = ns.new("ShaderNodeTexVoronoi")
    vor.voronoi_dimensions = "3D"
    vor.feature = "F1"
    vor.inputs["Scale"].default_value = 1000.0 / g["pore_mm"]
    vor.inputs["Randomness"].default_value = 0.85
    ln.new(tc.outputs["Object"], vor.inputs["Vector"])
    pit = ns.new("ShaderNodeMapRange")
    pit.interpolation_type = "SMOOTHSTEP"
    pit.inputs["From Min"].default_value = 0.08
    pit.inputs["From Max"].default_value = 0.42
    pit.inputs["To Min"].default_value = -g["pore_depth_mm"] / 1000.0
    pit.inputs["To Max"].default_value = 0.0
    ln.new(vor.outputs["Distance"], pit.inputs["Value"])
    noi = ns.new("ShaderNodeTexNoise")
    noi.inputs["Scale"].default_value = 1000.0 / g["peel_mm"]
    noi.inputs["Detail"].default_value = 2.0
    ln.new(tc.outputs["Object"], noi.inputs["Vector"])
    peel = ns.new("ShaderNodeMapRange")
    peel.inputs["To Min"].default_value = -g["peel_depth_mm"] / 1000.0
    peel.inputs["To Max"].default_value = g["peel_depth_mm"] / 1000.0
    peel.inputs["From Min"].default_value = 0.3
    peel.inputs["From Max"].default_value = 0.7
    ln.new(noi.outputs["Fac"], peel.inputs["Value"])
    add = ns.new("ShaderNodeMath")
    add.operation = "ADD"
    ln.new(pit.outputs["Result"], add.inputs[0])
    ln.new(peel.outputs["Result"], add.inputs[1])
    att = ns.new("ShaderNodeAttribute")
    att.attribute_name = "m_grain"
    mul = ns.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    ln.new(add.outputs[0], mul.inputs[0])
    ln.new(att.outputs["Fac"], mul.inputs[1])
    bump = ns.new("ShaderNodeBump")
    bump.inputs["Distance"].default_value = 1.0
    bump.inputs["Strength"].default_value = 1.0
    ln.new(mul.outputs[0], bump.inputs["Height"])
    ln.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    cv = ns.new("ShaderNodeAttribute")
    cv.attribute_name = "curv"
    cv.name = "curv"
    em = ns.new("ShaderNodeEmission")
    em.name = "curv_emit"
    ln.new(cv.outputs["Color"], em.inputs["Color"])
    return mt


# ---------------------------------------------------------------- the bake
def target(body, name, size, non_color=True):
    img = bpy.data.images.new(name, size, size, alpha=False, float_buffer=False)
    if non_color:
        img.colorspace_settings.name = "Non-Color"
    mt = body.data.materials[0]
    node = mt.node_tree.nodes.get("bake_target") or mt.node_tree.nodes.new("ShaderNodeTexImage")
    node.name = "bake_target"
    node.image = img
    uvn = mt.node_tree.nodes.get("bake_uv") or mt.node_tree.nodes.new("ShaderNodeUVMap")
    uvn.name = "bake_uv"
    uvn.uv_map = UV_LAYER
    if not node.inputs["Vector"].is_linked:
        mt.node_tree.links.new(uvn.outputs["UV"], node.inputs["Vector"])
    mt.node_tree.nodes.active = node
    return img


def save(img, path, preview=1024):
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()
    pv = img.copy()
    pv.scale(preview, preview)
    pv.filepath_raw = str(path.with_name(path.stem + "_1k.png"))
    pv.file_format = "PNG"
    pv.save()


def make_cage(body):
    """M3a's capped cage (alien_texture.stage_cage): Body's copy, each vertex out along its normal by
    alien_texture_geom.cage_offset of its clearance to the low mesh's next surface, invisible to every ray."""
    import alien_texture as X  # noqa: PLC0415  (Blender-only; its cage helpers)
    co, nr = X.vertex_arrays(body.data)
    off = X.cage_offsets(body.data, X.clearances(body.data, co, nr))
    cage = body.copy()
    cage.data = body.data.copy()
    cage.name = cage.data.name = "Body_cage"
    for m in list(cage.modifiers):
        cage.modifiers.remove(m)
    cage.parent = None
    cage.matrix_world = body.matrix_world.copy()
    bpy.context.scene.collection.objects.link(cage)
    cage.data.vertices.foreach_set("co", (co + nr * off[:, None]).astype(np.float32).ravel())
    for attr in ("visible_camera", "visible_diffuse", "visible_glossy", "visible_transmission",
                 "visible_volume_scatter", "visible_shadow"):
        setattr(cage, attr, False)
    print(f"M2 cage capped: offset mm min {off.min() * 1000:.2f} mean {off.mean() * 1000:.2f}", flush=True)
    return cage, {"kind": "capped", "cage": X.T.CAGE, "offset_mm": {"min": round(float(off.min() * 1000), 3),
                                                                    "mean": round(float(off.mean() * 1000), 3)}}


def bake(kind, body, hi, img_name, size, samples, out, cage=None, **kw):
    sc = bpy.context.scene
    sc.cycles.samples = samples
    img = target(body, img_name, size)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    hi.select_set(True)
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    t = time.time()
    if cage is not None:  # the capped cage (M3a): rays from the cage, at most CAGE["ray_mm"]
        import alien_texture_geom as T  # noqa: PLC0415
        kw.update(use_cage=True, cage_object=cage.name, max_ray_distance=T.CAGE["ray_mm"] / 1000.0)
    else:
        kw.update(cage_extrusion=BAKE["cage"], max_ray_distance=BAKE["ray"])
    res = bpy.ops.object.bake(type=kind, use_selected_to_active=True, margin=BAKE["margin"], margin_type="EXTEND",
                              use_clear=True, uv_layer=UV_LAYER, **kw)
    if res != {"FINISHED"}:
        raise SystemExit(f"bake {kind}: {res}")
    save(img, out / f"{img_name}.png")
    px = np.empty(size * size * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(-1, 4)[:, :3]
    print(f"M2 baked {img_name} {size}px {time.time() - t:.0f}s mean {px.mean(0).round(3).tolist()}", flush=True)
    return {"px": size, "samples": samples, "s": round(time.time() - t), "mean": px.mean(0).round(3).tolist()}


def stage_bake(a, out):
    sc = bpy.context.scene
    body = bpy.data.objects["Body"]
    hi = bpy.data.objects["Body_high"]
    arm = body.find_armature()
    arm.data.pose_position = "REST"
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    if sc.world is None:
        sc.world = bpy.data.worlds.new("w")
    bdir = out / "bake"
    bdir.mkdir(parents=True, exist_ok=True)
    bpy.context.view_layer.update()
    cage, crep = make_cage(body) if a.cage == "capped" else (None, {"kind": "uniform"})
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    for o in meshes:
        o.hide_render = not (o is body or o is hi or o is cage or o.name.startswith(SHOWN))
    rep = {"settings": BAKE, "cage": crep}
    rep["normal"] = bake("NORMAL", body, hi, "normal", a.size, BAKE["normal_samples"], bdir, cage,
                         normal_space="TANGENT")
    sc.world.light_settings.distance = BAKE["ao_dist"]
    rep["ao"] = bake("AO", body, hi, "ao", a.aux, BAKE["ao_samples"], bdir, cage)
    # curvature: the copy emits its `curv` colour
    mt = hi.data.materials[0]
    out_node = mt.node_tree.nodes["Material Output"]
    mt.node_tree.links.new(mt.node_tree.nodes["curv_emit"].outputs["Emission"], out_node.inputs["Surface"])
    rep["curvature"] = bake("EMIT", body, hi, "curvature", a.aux, 1, bdir, cage)
    # thickness: AO from inside the copy (its normals flipped), the face parts hidden
    for o in meshes:
        o.hide_render = not (o is body or o is hi or o is cage)
    hi.data.flip_normals()
    sc.world.light_settings.distance = BAKE["thick_dist"]
    rep["thickness"] = bake("AO", body, hi, "thickness", a.aux, BAKE["thick_samples"], bdir, cage)
    (bdir / "bake_report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8", newline="\n")
    print("M2 BAKE " + json.dumps(rep), flush=True)


def stage_grid(a, out):
    """A sculpt tuning grid (M2b): the copy subdivided once, then per variant of --variants (name: settings over
    --sculpt) the sculpt and a normal map (--size) and curvature (--aux) baked through the capped cage into
    --vout/<name>/ with its `high_report.json`."""
    variants = json.loads(Path(a.variants).read_text(encoding="utf-8"))
    sc = bpy.context.scene
    body, arm, hi, P, N, ed = build_high()
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    if sc.world is None:
        sc.world = bpy.data.worlds.new("w")
    cage, crep = make_cage(body)
    for o in [o for o in bpy.data.objects if o.type == "MESH"]:
        o.hide_render = not (o is body or o is hi or o is cage)
    for name, settings in variants.items():
        S = G.sculpt(a.sculpt, settings)
        hi.data.vertices.foreach_set("co", P.ravel())  # back to the unsculpted copy
        hi.data.update()
        rep = sculpt_high(hi, arm, P, N, ed, S, {"variant": name, "cage": crep})
        vdir = Path(a.vout) / name
        vdir.mkdir(parents=True, exist_ok=True)
        bake("NORMAL", body, hi, "normal", a.size, BAKE["normal_samples"], vdir, cage, normal_space="TANGENT")
        mt = hi.data.materials[0]
        mt.node_tree.links.new(mt.node_tree.nodes["curv_emit"].outputs["Emission"],
                               mt.node_tree.nodes["Material Output"].inputs["Surface"])
        bake("EMIT", body, hi, "curvature", a.aux, 1, vdir, cage)
        (vdir / "high_report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8", newline="\n")
        print("M2 GRID " + name + " " + json.dumps({k: rep[k] for k in ("disp_mm", "soften_mm", "curv_p1_p99")}),
              flush=True)


# ---------------------------------------------------------------- the export
def stage_export(a, out):
    body = bpy.data.objects["Body"]
    mt = body.data.materials[0]
    nt = mt.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    img = bpy.data.images.load(str(out / "bake" / "normal.png"))
    img.colorspace_settings.name = "Non-Color"
    img.name = "alien_skin_normal"
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.name = "skin_normal"
    tex.image = img
    uvn = nt.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = UV_LAYER
    nt.links.new(uvn.outputs["UV"], tex.inputs["Vector"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.space = "TANGENT"
    nm.uv_map = UV_LAYER
    nt.links.new(tex.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    body.data.uv_layers.active = body.data.uv_layers[UV_LAYER]
    ex = out / "export"
    ex.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(ex / "alien_character.blend"))
    opts = dict(export_glb.options(False), export_image_format="AUTO", export_vertex_color="ACTIVE", export_tangents=True)
    res = bpy.ops.export_scene.gltf(filepath=str(ex / "alien_character.glb"), **opts)
    if res != {"FINISHED"}:
        raise SystemExit(f"export: {res}")
    if not a.kit:
        raise SystemExit("--stage export needs --kit (the kit's export folder with character.json)")
    src = Path(a.kit)
    for f in src.iterdir():
        if f.suffix == ".png":
            shutil.copy2(f, ex / f.name)
    cj = json.loads((src / "character.json").read_text(encoding="utf-8"))
    cj["note_m2_detail"] = ("art #196 M2: the skin (Body) has a texture UV, `UVMap` = glTF TEXCOORD_0 (masks stay "
                            "TEXCOORD_1, AO COLOR_0, rest pose TEXCOORD_2/3), and a 4K tangent-space normal map baked from "
                            "a detail sculpt (alien_detail.py) as the alien_hue material's normalTexture (texCoord 0). "
                            "AO, curvature and thickness maps for the texture set are in M2/bake/.")
    (ex / "character.json").write_text(json.dumps(cj, indent=1), encoding="utf-8", newline="\n")
    print("M2 EXPORT " + str(ex / "alien_character.glb"), flush=True)


def main():
    a = args()
    out = Path(a.out)
    src = {"high": a.character, "bake": str(out / "high" / "alien_high.blend"), "export": a.character,
           "grid": a.character}[a.stage]
    bpy.ops.wm.open_mainfile(filepath=src)
    {"high": stage_high, "bake": stage_bake, "export": stage_export, "grid": stage_grid}[a.stage](a, out)


if __name__ == "__main__":
    main()
