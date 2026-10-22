"""Hull shape blockouts (art #263): the manta's outer shape alone, grey, untextured, under even studio light, so the
engineer can judge the SHAPE before any material, light or detail.

His decisions (2026-10-22): flat wings with sharp, swept-back tips (no upcurl); the rooms hidden inside one clean
shape (no domes, pods or pillow bulges); no tip windows in the main variants, so the wing thins to a sharp edge
beyond the tip rooms; the night build's faceted look (crisp planes and edges, the spine with the two canopy bumps
over the mouth, the mouth recess, the stern's three nozzle pods, landing legs as blocks); the span may grow.

The hull is the CONVEX HULL of a few design points (plan metres: x east, y south, h up; Blender gets (x, -y, h)),
mirrored in x, so it is one faceted shape with no local bump by construction:
    the spine     a ridge 2.6 m wide, its profile SPINE rising from the brow to a peak over the hall's crown
    the nose      a wedge with its edge NOSE across the front; the mouth recess is cut into it
    the lead edge one straight 3D line from the nose's corner to the tip, through LEAD_PIVOT in plan (ahead of the
                  tip room)
    the tip       one vertex: the lead and trail edges meet there (a variant's span and tip height)
    the trail     one straight 3D line from the tip back to the stern's corner
    the stern     a flat face with the three nozzle pods (stand-ins) sticking out
    the belly     flat at BELLY under every room's slab, rising toward every edge
then the mouth recess (and, in a window variant, the tip rooms' window sectors) cut away and coplanar facets merged.
Variants E-G (the arrowhead, 2026-10-22): the tip rooms moved back into the rear corners (tip_c), the corridors
straight boxes along the diagonal from the hall's wall to them, the tip at the rear corner (tip_y), the stern moved
back (stern_y) so the top view's proportions approach the 2D's; the checks, legs and ghosts follow the rooms.
Variants H-I (the true triangle): the trail edge straight across, level with the tips; I with a pointed nose.
J is drawn as the build makes it (ship_hull_shape.surface, the throat notch cut) with ship.toml's rooms. Variants M-O
(the lens-tip diamonds, 2026-10-22 evening, `LENS` below): the round tip room is the wing's tip, the hull a union of
convex pieces with a dark recessed window band round each lens, the stern longer, the nozzle pods 1.35x.
Every room's outer surface (ship.toml: the clear sizes plus the walls, the roofs and the slabs) is sampled and must
lie inside the hull with at least SKIN of hull around it; the mouth's own opening is the only exception.

    blender -b --factory-startup --python ship_hull_blockout.py -- --out <dir> [--variants J,M,N,O]
            [--crops <dir>] [--hero <jpg>] [--no-render]

Writes <out>/sheet.png (the 2D's turnaround crops and hero, then one row per variant: front, side, back, top, hero
in flat grey, the variant's numbers on the row), <out>/ghost.png (each variant's top and front with the rooms as a
faint ghost), <out>/report.json (per variant: span, length, height, the wing's thickness 1 m from the tip, the
interior points closer than SKIN to the outside), <out>/blockout.blend and prints BLOCKOUT lines."""

from __future__ import annotations

import json
import math
import sys
import tomllib
from pathlib import Path

try:
    import bmesh
    import bpy
    import numpy as np
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
except ImportError:   # plain Python: the lens variants' shape and skin checks alone (ship_hull_lens below)
    bpy = None

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ship_hull_shape import *  # noqa: E402,F403  (the variants, the design points and the rooms' samples: plain Python)
from ship_hull_shape import (HALL_R, MOUTH_X, MOUTH_Y, MOUTH_TOP, WALL, SLAB, COR_Y, COR_TOP, TIP_APEX, TIP_R, TIP_X,  # noqa: E402,F401
                             RM, SPINE, SPINE_X, STERN, STERN_Y, NOSE, BELLY, PIN_HALL_R, TRAIL_END, COR_S, COR_D,
                             SILL, HEAD, WIN_HALF, cutters, ring)
BG = np.array([0.05, 0.07, 0.1, 1.0], dtype=np.float32) if bpy else None


def arg(name, default=None):
    """The script's own argument reader (ship_hull_shape.arg, star-imported above, uses sys without importing it)."""
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return argv[argv.index(name) + 1] if name in argv else default


# --- the lens-tip diamonds M, N, O (2026-10-22 evening, art #263) ----------------------------------------------------
# The engineer's new direction: more diamond than triangle, the round tip room IS the wing's tip. The hull is no longer
# one convex hull: it is the UNION of convex pieces (their points plain Python; Blender's convex hull and EXACT
# boolean union make the mesh, its BVH the skin check):
#     core   J's spine, nose, belly and stern (the stern `stern_ext` longer) with a lead edge from the nose through
#            `lead_mid` (x, y, h) and a trail edge from the stern's corner, both running into the lens's rim at the
#            angles `lead_a` and `trail_a` (deg, plan: 0 east, 90 south), `edge_e` the lead edge's half thickness at
#            lead_mid and `rim_e` where it meets the rim; the wing's top point over the tip room's centre (`top_h`);
#            the corridor's envelope (its walls `cor_margin` out, belly to roof) so the wedge holds it
#     lens   per side a round lobe of rim radius `rim_r` about the tip room, its top the wing's own top plane (the
#            core's slope carried on outward, never above the core: no dome), its belly the flat belly, its rim a
#            rounded edge LENS_PROFILE with a vertical band that holds the window band
#     necks  per side the convex hull of the lens and a pair of points on each edge, `necks` and `trail_necks`
#            (m back from the rim, half thickness): the concave fillets where the fin thickens into the lobe
# then J's throat notch (ship_hull_shape.cutters()) and the window band (SILL..HEAD over +-WIN_HALF about the
# corridor's axis, WIN_DEPTH deep) cut away. The rooms are ship.toml's with the tip rooms at `tip_c` and the corridors
# on the new axes (the same hall and throat).
LENS = {
    "M": {"tip_c": (8.3, 3.6), "rim_r": 2.5, "stern_ext": 2.5, "lead_mid": (5.4, -3.2, 2.15), "lead_a": -75.0,
          "trail_a": 150.0, "top_h": 3.85, "edge_h": 2.2, "edge_e": 0.12, "rim_e": 0.3,
          "necks": ((0.9, 0.3), (2.2, 0.18)), "trail_necks": ((0.5, 0.6), (1.1, 0.35)), "trail": (4.2, 2.6),
          "cor_margin": 0.25},
}
LENS["N"] = {**LENS["M"], "tip_c": (11.0, 3.6), "lead_mid": (6.6, -3.2, 2.15)}
LENS["O"] = {**LENS["N"], "stern_ext": 4.5}
J_DS = VARIANTS["J"]["stern_y"] - STERN_Y                              # 3.9: J's stern shift
LENS_STERN = [(1.4, 4.25), (4.0, 3.5), (4.0, 0.8), (1.4, 0.6)]         # the wider, taller stern face for the bigger pods
# (x, h, r, out): the nozzle pods 1.35x J's diameter (2.4 -> 3.24, 2.1 -> 2.84), `out` m behind the stern face
LENS_PODS = [(-3.0, 2.0, 1.42, 2.0), (0.0, 2.55, 1.62, 2.3), (3.0, 2.0, 1.42, 2.0)]
POD_IN, POD_CUP, POD_RING = 1.6, 1.0, 0.4                             # the pods' start inside, the nozzle's depth, ring
WIN_DEPTH = 0.15
# the rim's profile: (inset from rim_r, ("top", depth under the top plane) or ("abs", height))
LENS_PROFILE = [(0.35, ("top", 0.0)), (0.12, ("top", 0.15)), (0.0, ("top", 0.45)), (0.0, ("abs", 1.15)),
                (0.12, ("abs", 0.55)), (0.3, ("abs", BELLY))]
LENS_N = 48


def lens_ds(v):
    return J_DS + v["stern_ext"]


def lens_stern_y(v):
    return STERN_Y + lens_ds(v)


def lens_rooms(v):
    """ship.toml's rooms with the tip rooms at tip_c and the corridors' axes and floor ends moved with them."""
    cx, cy = v["tip_c"]
    rooms = {k: dict(r) for k, r in RM.items()}
    hx, hy = RM["hall"]["centre"]
    for side, sx in (("e", 1), ("w", -1)):
        rooms[f"tip_{side}"]["centre"] = [sx * cx, cy]
        d = math.hypot(cx - hx, cy - hy)
        rooms[f"corridor_{side}"]["axis"] = [[hx, hy], [sx * cx, cy]]
        rooms[f"corridor_{side}"]["along"] = [COR_S[0], d - (COR_D - COR_S[1])]
    return rooms


def lens_axis(v):
    """The east tip room's outward axis (the corridor's, hall to tip): its angle in plan, radians."""
    cx, cy = v["tip_c"]
    hx, hy = RM["hall"]["centre"]
    return math.atan2(cy - hy, cx - hx)


def _rim_pt(v, deg, r=None):
    cx, cy = v["tip_c"]
    r = v["rim_r"] if r is None else r
    return (cx + r * math.cos(math.radians(deg)), cy + r * math.sin(math.radians(deg)))


def _edges(v):
    """The lead edge (nose corner -> rim at lead_a) and the trail edge (rim at trail_a -> the stern corner), each as
    ((x, y, h), (x, y, h)), east side."""
    sy = lens_stern_y(v)
    ax, ay = _rim_pt(v, v["lead_a"])
    bx, by = _rim_pt(v, v["trail_a"])
    tx, th = v["trail"]
    return (v["lead_mid"], (ax, ay, v["edge_h"])), ((bx, by, v["edge_h"]), (tx, sy - 0.2, th))


def _along(a, b, dist_from_b):
    f = dist_from_b / math.dist(a[:2], b[:2])
    return tuple(b[k] + (a[k] - b[k]) * f for k in range(3))


def lens_core_points(v):
    ds = lens_ds(v)
    sy = lens_stern_y(v)
    cx, cy = v["tip_c"]
    spine = SPINE[:-1] + [(SPINE[-1][0] + ds, SPINE[-1][1])]
    pts = [(SPINE_X, y, z) for y, z in spine] + [NOSE]
    (_n0, a), (b, t1) = _edges(v)
    e, re_ = v["edge_e"], v["rim_e"]
    m = v["lead_mid"]
    pts += [t1, (a[0], a[1], a[2] + re_), (a[0], a[1], a[2] - re_), (b[0], b[1], b[2] + re_),
            (b[0], b[1], b[2] - re_), (m[0], m[1], m[2] + e), (m[0], m[1], m[2] - e)]
    cor = lens_rooms(v)["corridor_e"]   # the corridor's envelope: its walls cor_margin out, belly to roof + skin
    (ax0, ay0), (ax1, ay1) = cor["axis"]
    dd = math.hypot(ax1 - ax0, ay1 - ay0)
    cu = ((ax1 - ax0) / dd, (ay1 - ay0) / dd)
    hw = cor["width"] / 2 + WALL + v["cor_margin"]
    for su in cor["along"]:
        for w in (-hw, hw):
            x, y = ax0 + su * cu[0] - w * cu[1], ay0 + su * cu[1] + w * cu[0]
            pts += [(x, y, BELLY), (x, y, COR_TOP + 0.25)]
    pts += [(x, sy, z) for x, z in LENS_STERN]
    pts += ring(0.0, 0.0, PIN_HALL_R + 0.3, BELLY) + [(1.8, -4.8, BELLY)]
    pts += ring(cx, cy, 0.8, BELLY) + [(cx, cy, v["top_h"])]
    hx, hy = RM["hall"]["centre"]   # J's own top over the hall's front half (the hall's rim keeps J's skin there)
    for a in range(-180, 1, 15):
        x, y = hx + (HALL_R + 0.4) * math.cos(math.radians(a)), hy + (HALL_R + 0.4) * math.sin(math.radians(a))
        tb = heights(x, y, "J")
        if tb and x >= -1e-6:
            pts.append((x, y, tb[0]))
    return mirrored([p for p in pts if p[0] >= -1e-6])


def _mirror_x(pts):
    return [(-x, y, z) for x, y, z in pts]


def lens_ring_points(v):
    """The east lens's rim rings: the top on the wing's top plane (the core's slope from the spine to top_h carried
    outward along the corridor's axis)."""
    cx, cy = v["tip_c"]
    R = v["rim_r"]
    u = lens_axis(v)
    k = (SPINE[1][1] - 0.2 - v["top_h"]) / (cx - SPINE_X)             # the wing's slope outward
    out = []
    for inset, (kind, h) in LENS_PROFILE:
        rr = (R - inset) / math.cos(math.pi / LENS_N)
        for i in range(LENS_N):
            g = 2 * math.pi * i / LENS_N
            x, y = cx + rr * math.cos(g), cy + rr * math.sin(g)
            if kind == "abs":
                out.append((x, y, h))
                continue
            plane = v["top_h"] - k * ((x - cx) * math.cos(u) + (y - cy) * math.sin(u))
            out.append((x, y, plane - h))
    return out


def lens_parts(name):
    """[(part name, points)]: the core and per side the lens and its necks."""
    v = LENS[name]
    core_pts = lens_core_points(v)
    rim = lens_ring_points(v)
    (n0, a), (b, t1) = _edges(v)
    parts = [("core", core_pts)]
    cx, cy = v["tip_c"]
    for k, ((dd, e), (gg, f)) in enumerate(zip(v["necks"], v["trail_necks"])):
        p, q = _along(n0, a, dd), _along(t1, b, gg)
        # each neck holds the whole lens (no separate lens piece); the second's lens 2 cm smaller all round, so no
        # two pieces share a face (shared faces broke the EXACT union)
        sh = 1.0 - 0.02 * k / v["rim_r"]
        lens = [(cx + (x - cx) * sh, cy + (y - cy) * sh, z - 0.02 * k if z > 1.0 else z + 0.02 * k) for x, y, z in rim]
        neck = lens + [(p[0], p[1], p[2] + e), (p[0], p[1], p[2] - e), (q[0], q[1], q[2] + f), (q[0], q[1], q[2] - f)]
        parts += [(f"neck{k}_e", neck), (f"neck{k}_w", _mirror_x(neck))]
    return parts


# --- the ray variants P, Q (round 2, 2026-10-22: the approved layout, art#263 comment 6344490367) -------------------
# A ray, not a slab: the lens rooms (r 2.0 clear) at RAY_TIP, straight corridors about 9 deg aft, a vault under the
# stern. The hull is the union of convex parts:
#     body   the spine, the nose, J's own top over the hall (its rim keeps J's skin), a skirt sloping the hump into
#            the fins, the belly under the hall and the vault, the narrower stern face for the bigger pods
#     wing   per side the ridge (the corridor's box, its top RIDGE_H, its belly flat) and the thin fin edges: the
#            nose's corner -> the lens's front tangent, the lens's rear tangent -> the stern's corner, `edge_lens`
#            thick at the lens, `edge_nose` at the nose: the edges draw the diamond from the top
#     lens   per side a round lobe of rim radius rim_r (the wall + 0.35) about the lens room, its top the room's
#            slanted ceiling + roof + skin (falling outward along the corridor's axis), its rim RAY_PROFILE
# then J's throat notch, the window band (sill 1.6, head 2.8, +-WIN_HALF about the corridor's axis) as a thin shell
# round the rim and the roof windows (dark recessed panels in the slanted top) cut away. The skin is measured on the
# union before the windows are cut (they are openings).
RAY_TIP = (10.5, 1.2)
RAY_ROOM_R = 2.0
RAY_CLEAR_OUT, RAY_CLEAR_IN = 2.35, 2.45     # the lens room's ceiling: clear at the outer wall, at the inner wall
RIDGE_H = 3.30                               # the corridor's top 3.12 + skin 0.15 + 3 cm
RIDGE_W, RIDGE_WB = 1.85, 2.05               # the ridge's top and belly half widths about the corridor's axis
VAULT = (0.9, 3.85, 5.85, 2.3, 1.6)          # half width, clear y0..y1, clear height at the door and at the back
RAY_STERN = [(1.4, 4.25), (3.4, 3.7), (4.0, 2.3), (3.6, 0.9), (1.4, 0.6)]
RAY_PANELS = [(0.35, -0.8), (0.35, 0.8), (1.3, 0.0)]   # roof windows' centres (along the axis, across) from the centre
RAY_PANEL = (0.9, 0.7, 0.06)                           # along, across, depth
RAYS = {
    "P": {"tip_c": RAY_TIP, "rim_r": RAY_ROOM_R + WALL + 0.35, "stern_ext": 2.5, "edge_h": 2.0, "edge_lens": 0.4,
          "edge_nose": 0.3, "trail": (4.2, 2.0), "trail_e": 0.4},
    "Q": {"tip_c": RAY_TIP, "rim_r": RAY_ROOM_R + WALL + 0.35, "stern_ext": 4.0, "edge_h": 2.0, "edge_lens": 0.3,
          "edge_nose": 0.25, "trail": (3.8, 2.0), "trail_e": 0.3},
}


def lens_var(name):
    return LENS.get(name) or RAYS[name]


def ray_rooms(v, ghost=False):
    """ship.toml's rooms with the corridors on the new axes; with ghost the lens rooms and the vault too (the skin
    samples take those from ray_samples: their ceilings slant)."""
    rooms = lens_rooms({**v, "tip_c": v["tip_c"]})
    cx, cy = v["tip_c"]
    hx, hy = RM["hall"]["centre"]
    d = math.hypot(cx - hx, cy - hy)
    for side in ("e", "w"):
        rooms[f"corridor_{side}"]["along"] = [COR_S[0], d - math.sqrt(RAY_ROOM_R ** 2 - 1.5 ** 2)]
        rooms[f"tip_{side}"]["radius"] = RAY_ROOM_R
        rooms[f"tip_{side}"]["clear_h"] = rooms[f"tip_{side}"]["apex_h"] = RAY_CLEAR_IN
        if not ghost:
            del rooms[f"tip_{side}"]
    if ghost:
        hw, y0, y1, h0, _h1 = VAULT
        rooms["vault"] = {"id": "vault", "shape": "poly", "points": [[-hw, y0], [hw, y0], [hw, y1], [-hw, y1]],
                          "clear_h": h0}
    return rooms


def ray_axis(v, sx=1):
    cx, cy = v["tip_c"]
    hx, hy = RM["hall"]["centre"]
    a = math.atan2(cy - hy, sx * cx - hx)
    return math.cos(a), math.sin(a)


def ray_roof(v, x, y, sx=1):
    """The lens room's roof top (ceiling + ROOF) over plan (x, y): the ceiling falls outward along the axis."""
    cx, cy = v["tip_c"]
    ux, uy = ray_axis(v, sx)
    rw = RAY_ROOM_R + WALL
    t = (x - sx * cx) * ux + (y - cy) * uy
    clear = RAY_CLEAR_OUT + (RAY_CLEAR_IN - RAY_CLEAR_OUT) * (rw - t) / (2 * rw)
    return FLOOR + clear + ROOF


def vault_roof(y):
    _hw, y0, y1, h0, h1 = VAULT
    return FLOOR + h0 + (h1 - h0) * (y - y0) / (y1 - y0) + ROOF


def ray_samples(v):
    """(what, plan point): the rooms' samples (interior_points on ray_rooms) plus the lens rooms' (slanted ceilings)
    and the vault's walls, roof and slab."""
    pts = list(interior_points({"throat": True}, ray_rooms(v)))
    cx, cy = v["tip_c"]
    rw = RAY_ROOM_R + WALL
    for sx, side in ((1, "e"), (-1, "w")):
        for i in range(144):
            g = 2 * math.pi * i / 144
            rr = rw / math.cos(math.pi / 144)
            x, y = sx * cx + rr * math.cos(g), cy + rr * math.sin(g)
            top = ray_roof(v, x, y, sx)
            for h in (SLAB, 0.5 * (SLAB + top), top):
                pts.append((f"lens wall {side}", (x, y, h)))
            for f in (0.3, 0.6, 0.9):
                q = (sx * cx + f * rw * math.cos(g), cy + f * rw * math.sin(g))
                pts.append((f"lens roof {side}", (*q, ray_roof(v, *q, sx))))
                pts.append((f"lens slab {side}", (*q, SLAB)))
    hw, y0, y1, _h0, _h1 = VAULT
    X0, Y1 = hw + WALL, y1 + WALL
    for k in range(13):
        y = y0 + (Y1 - y0) * k / 12
        for x in (-X0, X0):
            for h in (SLAB, 0.5 * (SLAB + vault_roof(y)), vault_roof(y)):
                pts.append(("vault wall", (x, y, h)))
        for x in (-X0, 0.0, X0):
            pts += [("vault roof", (x, y, vault_roof(y))), ("vault slab", (x, y, SLAB))]
    for k in range(7):
        x = -X0 + 2 * X0 * k / 6
        for h in (SLAB, 1.2, vault_roof(Y1)):
            pts.append(("vault wall", (x, Y1, h)))
    return pts


def _tangent(p, c, r, pick):
    """The tangent point on circle (c, r) of a line through p: pick chooses one of the two."""
    dx, dy = c[0] - p[0], c[1] - p[1]
    d = math.hypot(dx, dy)
    phi, al = math.atan2(dy, dx), math.asin(r / d)
    out = []
    for a in (phi - al, phi + al):
        ux, uy = math.cos(a), math.sin(a)
        t = dx * ux + dy * uy
        out.append((p[0] + t * ux, p[1] + t * uy))
    return pick(out)


def ray_edges(v):
    """The east fin's edge corners: nose corner, the lens's front tangent F, its rear tangent B, the stern corner."""
    sy = lens_stern_y(v)
    tx, th = v["trail"]
    n0 = (NOSE[0], NOSE[1])
    st = (tx, sy - 0.2)
    f = _tangent(n0, v["tip_c"], v["rim_r"], lambda q: min(q, key=lambda t: t[1]))
    b = _tangent(st, v["tip_c"], v["rim_r"], lambda q: max(q, key=lambda t: t[0]))
    return n0, f, b, st, th


RAY_PROFILE = [(0.2, ("top", 0.0)), (0.0, ("top", 0.3)), (0.0, ("abs", 1.0)), (0.08, ("abs", 0.5)),
               (0.25, ("abs", BELLY))]


def ray_parts(name):
    v = RAYS[name]
    ds, sy = lens_ds(v), lens_stern_y(v)
    cx, cy = v["tip_c"]
    hx, hy = RM["hall"]["centre"]
    spine = SPINE[:-1] + [(SPINE[-1][0] + ds, SPINE[-1][1])]
    body = [(SPINE_X, y, z) for y, z in spine] + [NOSE, (1.8, -4.8, BELLY)]
    body += ring(0.0, 0.0, PIN_HALL_R + 0.3, BELLY)
    n0, f, b, st, th = ray_edges(v)
    diamond = [(-n0[0], n0[1]), n0, f, b, st, (-st[0], st[1]), (-b[0], b[1]), (-f[0], f[1])]
    for a in range(0, 360, 15):   # J's own top over the hall's ring, and the skirt into the fins
        x, y = hx + (HALL_R + 0.4) * math.cos(math.radians(a)), hy + (HALL_R + 0.4) * math.sin(math.radians(a))
        tb = heights(x, y, "J")
        if tb and x >= -1e-6:
            body.append((x, y, tb[0]))
        x, y = hx + 6.2 * math.cos(math.radians(a)), hy + 6.2 * math.sin(math.radians(a))
        if x >= -1e-6 and _inside_poly(diamond, x, y, 0.8):
            body.append((x, y, 2.2))
    hw, _y0, y1, _h0, _h1 = VAULT
    body += [(hw + 0.6, 3.4, BELLY), (hw + 0.6, y1 + 0.6, BELLY)]
    body += [(x, sy, z) for x, z in RAY_STERN]
    parts = [("body", mirrored([p for p in body if p[0] >= -1e-6]))]
    ux, uy = ray_axis(v)
    nx, ny = -uy, ux
    d = math.hypot(cx - hx, cy - hy)
    wing = []
    for s in (3.0, d):
        px, py = hx + s * ux, hy + s * uy
        for w in (-RIDGE_W, RIDGE_W):
            wing.append((px + w * nx, py + w * ny, RIDGE_H))
        for w in (-RIDGE_WB, RIDGE_WB):
            wing.append((px + w * nx, py + w * ny, BELLY))
    for (x, y), h, e in ((n0, NOSE[2], v["edge_nose"]), (f, v["edge_h"], v["edge_lens"]),
                         (b, v["edge_h"], v["edge_lens"]), (st, th, v["trail_e"])):
        wing += [(x, y, h + e / 2), (x, y, h - e / 2)]
    lens = []
    R = v["rim_r"]
    for inset, (kind, h) in RAY_PROFILE:
        rr = (R - inset) / math.cos(math.pi / LENS_N)
        for i in range(LENS_N):
            g = 2 * math.pi * i / LENS_N
            x, y = cx + rr * math.cos(g), cy + rr * math.sin(g)
            lens.append((x, y, h if kind == "abs" else ray_roof(v, x, y) + SKIN + 0.005 - h))
    parts += [("wing_e", wing), ("wing_w", _mirror_x(wing)), ("lens_e", lens), ("lens_w", _mirror_x(lens))]
    return parts


def _inside_poly(poly, x, y, margin):
    """Whether (x, y) lies at least margin inside the convex plan polygon poly (either winding)."""
    sgn = 0
    for (ax, ay), (bx, by) in zip(poly, poly[1:] + poly[:1]):
        ln = math.hypot(bx - ax, by - ay)
        c = ((bx - ax) * (y - ay) - (by - ay) * (x - ax)) / ln
        sgn = sgn or (1 if c > 0 else -1)
        if c * sgn < margin:
            return False
    return True


def ray_panels(v):
    """The roof windows per side: (plan polygon, the recess's floor height)."""
    cx, cy = v["tip_c"]
    out = []
    la, lw, dep = RAY_PANEL
    for sx in (1, -1):
        ux, uy = ray_axis(v, sx)
        nx, ny = -uy, ux
        for t, w in RAY_PANELS:
            mx, my = sx * cx + t * ux + w * nx, cy + t * uy + w * ny
            poly = [(mx + a * la / 2 * ux + b * lw / 2 * nx, my + a * la / 2 * uy + b * lw / 2 * ny)
                    for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            zb = min(ray_roof(v, x, y, sx) for x, y in poly) + SKIN + 0.005 - dep
            out.append((poly, zb))
    return out


def mat(name, rgb):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1.0)
    return m


def new_obj(name, bm, m, coll):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = False
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def bm_from(verts, faces):
    bm = bmesh.new()
    vs = [bm.verts.new(bl(v)) for v in verts]
    for f in faces:
        bm.faces.new([vs[i] for i in f])
    return bm


def prism(poly, z0, z1):
    """A closed prism over a plan polygon (counter-clockwise or not: normals are recalculated)."""
    n = len(poly)
    v = [(x, y, z0) for x, y in poly] + [(x, y, z1) for x, y in poly]
    f = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i)
                                                                 for i in range(n)]
    return v, f


def sector_prism(cx, sign, r0, r1, z0, z1, n=24):
    """The window's clear sector: from radius r0 (the glass) outward, +-WIN_HALF around the room's outward axis."""
    a = [(-WIN_HALF + 2 * WIN_HALF * i / n) for i in range(n + 1)]
    inner = [(cx + sign * r0 * math.cos(t), r0 * math.sin(t)) for t in a]
    outer = [(cx + sign * r1 * math.cos(t), r1 * math.sin(t)) for t in a]
    v, f = [], []
    for z in (z0, z1):
        v += [(x, y, z) for x, y in inner] + [(x, y, z) for x, y in outer]
    m = n + 1
    ib, ob, it, ot = 0, m, 2 * m, 3 * m
    for i in range(n):
        f.append((ib + i, ib + i + 1, ob + i + 1, ob + i))          # bottom
        f.append((it + i, ot + i, ot + i + 1, it + i + 1))          # top
        f.append((ib + i, it + i, it + i + 1, ib + i + 1))          # inner wall
        f.append((ob + i, ob + i + 1, ot + i + 1, ot + i))          # outer wall
    f.append((ib, ob, ot, it))
    f.append((ib + n, it + n, ot + n, ob + n))
    return v, f


def hull_object(name, var, coll, m, m_recess, cut_coll):
    pts, tip = design_points(var)
    bm = bmesh.new()
    for p in pts:
        bm.verts.new(bl(p))
    res = bmesh.ops.convex_hull(bm, input=bm.verts, use_existing_faces=False)
    drop = list({g for g in res["geom_interior"] + res["geom_unused"] if isinstance(g, bmesh.types.BMVert)})
    bmesh.ops.delete(bm, geom=drop, context="VERTS")
    ob = new_obj(name, bm, m, coll)
    cv, cf = prism([(-MOUTH_X, MOUTH_Y), (MOUTH_X, MOUTH_Y), (MOUTH_X, -12.0), (-MOUTH_X, -12.0)], -1.0, MOUTH_TOP)
    if var["window"]:
        for sign in (-1, 1):
            v, f = sector_prism(sign * TIP_X, sign, TIP_R + 0.2, 30.0, SILL - SKIN, 20.0)
            cf += [tuple(len(cv) + i for i in face) for face in f]
            cv += v
    cutter = new_obj(f"{name}_cut", bm_from(cv, cf), m, cut_coll)
    mod = ob.modifiers.new("cut", "BOOLEAN")
    mod.operation, mod.solver, mod.object = "DIFFERENCE", "EXACT", cutter
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    ob.modifiers.clear()
    old = ob.data
    ob.data = me
    bpy.data.meshes.remove(old)
    bpy.data.objects.remove(cutter, do_unlink=True)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.3), verts=bm.verts, edges=bm.edges)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(m_recess)
    for p in me.polygons:   # the mouth recess's faces a shade darker, so the opening reads in flat grey
        p.use_smooth = False
        if all(abs(me.vertices[i].co.x) <= MOUTH_X + 1e-3 and me.vertices[i].co.z <= MOUTH_TOP + 1e-3
               for i in p.vertices):
            p.material_index = 1
    if var.get("smooth"):   # smooth normals, sharp edges above SMOOTH_DEG, weighted by face area; no subdivision
        for p in me.polygons:
            p.use_smooth = True
        me.set_sharp_from_angle(angle=math.radians(SMOOTH_DEG))
        wn = ob.modifiers.new("wn", "WEIGHTED_NORMAL")
        wn.mode, wn.weight, wn.keep_sharp = "FACE_AREA", 50, True
    return ob, tip


def bvh_of(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    t = BVHTree.FromBMesh(bm)
    bm.free()
    return t


RAY = Vector((0.0123, 0.0071, 1.0)).normalized() if bpy else None


def inside(bvh, p):
    hits, o = 0, Vector(p)
    for _ in range(40):
        loc = bvh.ray_cast(o, RAY)[0]
        if loc is None:
            break
        hits += 1
        o = loc + RAY * 1e-4
    return hits % 2 == 1


def vertical(bvh, x, y):
    """(top, bottom) of the hull over plan (x, y), None where the ray misses."""
    hit = bvh.ray_cast(Vector((x, -y, 50.0)), Vector((0, 0, -1)))[0]
    low = bvh.ray_cast(Vector((x, -y, -50.0)), Vector((0, 0, 1)))[0]
    return (hit.z, low.z) if hit is not None and low is not None else None


def thickness_at(bvh, x):
    best = 0.0
    for k in range(-700, 701):
        tb = vertical(bvh, x, k * 0.02)
        if tb:
            best = max(best, tb[0] - tb[1])
    return best


def measure(hull, bvh, details, var, rooms=None, pts=None):
    bad, least = [], 9.0
    for what, (x, y, h) in (pts if pts is not None else interior_points(var, rooms)):
        p = Vector(bl((x, y, h)))
        d = bvh.find_nearest(p)[3]
        ins = inside(bvh, p)
        least = min(least, d if ins else -d)
        if not ins or d < SKIN - 1e-4:
            bad.append(f"{what} ({x:+.2f}, {y:+.2f}, h {h:.2f}): {'inside' if ins else 'OUTSIDE'}, skin {d:.3f}")
    hv = [hull.matrix_world @ v.co for v in hull.data.vertices]
    allv = list(hv)
    for ob in details:
        allv += [ob.matrix_world @ v.co for v in ob.data.vertices]
    xmax = max(v.x for v in hv)
    plan_y = [-v.y for v in allv if v.z > 0.05]
    return {
        "span_m": round(xmax - min(v.x for v in hv), 3),
        "length_m": round(max(plan_y) - min(-v.y for v in hv), 3),
        "height_m": round(max(v.z for v in allv), 3),
        "hull_top_m": round(max(v.z for v in hv), 3),
        "belly_m": round(min(v.z for v in hv), 3),
        "wing_thickness_1m_from_tip_m": round(thickness_at(bvh, xmax - 1.0), 3),
        "wing_thickness_2m_from_tip_m": round(thickness_at(bvh, xmax - 2.0), 3),
        "least_skin_m": round(least, 3),
        "pokes": bad,
        "hull_faces": len(hull.data.polygons),
    }


def details(name, var, bvh, coll, m_dark, m_glass, m_ramp):
    obs = []
    n = 12
    ds = stern_shift(var)
    tcx, tcy = tip_c(var)
    for k, (x, y, h, r, ln) in enumerate([] if var.get("no_pods") else NOZZLES):
        y += ds
        ring_ = [(x + r * math.cos(2 * math.pi * a / n + math.pi / n), h + r * math.sin(2 * math.pi * a / n + math.pi / n))
                 for a in range(n)]
        v = [(px, y + t, pz) for t in (0.0, ln) for px, pz in ring_]
        f = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))] + [(a, (a + 1) % n, n + (a + 1) % n, n + a)
                                                                     for a in range(n)]
        obs.append(new_obj(f"{name}_pod{k}", bm_from(v, f), m_dark, coll))
    cx, cy, ax, ay, ch = CANOPY
    for side in (-1, 1):
        x0 = side * cx
        tops = [t[0] for t in (vertical(bvh, x0 + ax * u, cy + ay * w) for u in (-1, 0, 1) for w in (-1, 0, 1)) if t]
        base, apex = min(tops) - 0.05, max(tops) + ch
        rings, segs = 3, 10
        v = []
        for i in range(rings + 1):
            t = math.pi / 2 * i / rings
            for a in range(segs):
                g = 2 * math.pi * a / segs
                v.append((x0 + ax * math.cos(t) * math.cos(g), cy + ay * math.cos(t) * math.sin(g),
                          base + (apex - base) * math.sin(t)))
        f = [tuple(range(segs - 1, -1, -1))]
        for i in range(rings):
            for a in range(segs):
                f.append((i * segs + a, i * segs + (a + 1) % segs, (i + 1) * segs + (a + 1) % segs,
                          (i + 1) * segs + a))
        bm = bm_from(v, f)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
        obs.append(new_obj(f"{name}_canopy{side}", bm, m_dark, coll))
    hx, hy = RAMP["hinge"]
    fx, fy = RAMP["foot"]
    w, t = RAMP["width_m"] / 2, RAMP["thickness_m"]
    v = [(-w, hy, FLOOR), (w, hy, FLOOR), (w, fy, 0.0), (-w, fy, 0.0),
         (-w, hy, FLOOR - t), (w, hy, FLOOR - t), (w, fy + 0.6, 0.0), (-w, fy + 0.6, 0.0)]
    f = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    obs.append(new_obj(f"{name}_ramp", bm_from(v, f), m_ramp, coll))
    for lx, ly in LEGS:
        if lx > 10:   # the wing leg: outboard of the tip room, level with it
            lx, ly = min(tcx + (lx - TIP_X), var["half"] - 2.4), tcy + ly
        elif ly > 0:  # the rear leg moves back with the stern
            ly += ds
        for side in (-1, 1):
            x = side * lx
            tb = vertical(bvh, x, ly)
            if not tb or tb[1] < 0.45:
                continue
            bot = tb[1]
            for (hw, z0, z1) in ((0.45, 0.0, 0.14), (0.18, 0.14, bot + 0.2)):
                v, f = prism([(x - hw, ly - hw), (x + hw, ly - hw), (x + hw, ly + hw), (x - hw, ly + hw)], z0, z1)
                obs.append(new_obj(f"{name}_leg{side}_{lx}", bm_from(v, f), m_dark, coll))
    if var["window"]:
        for sign in (-1, 1):
            nn = 24
            a = [(-WIN_HALF + 2 * WIN_HALF * i / nn) for i in range(nn + 1)]
            r = TIP_R + 0.21
            v = [(sign * TIP_X + sign * r * math.cos(t), r * math.sin(t), z) for z in (SILL, HEAD) for t in a]
            f = [(i, i + 1, nn + 2 + i, nn + 1 + i) for i in range(nn)]
            obs.append(new_obj(f"{name}_glass{sign}", bm_from(v, f), m_glass, coll))
    return obs


def ghost_rooms(name, var, coll, m):
    def cyl(gname, cx, cy, r, h0, h1, n=32):
        v = [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n), h) for h in (h0, h1)
             for k in range(n)]
        f = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))] + [(k, (k + 1) % n, n + (k + 1) % n, n + k)
                                                                     for k in range(n)]
        new_obj(gname, bm_from(v, f), m, coll)
    cyl(f"g{name}_hall", 0.0, 0.0, HALL_R, SLAB, HALL_APEX)
    new_obj(f"g{name}_mouth", bm_from(*prism([(-MOUTH_X - WALL, MOUTH_Y), (MOUTH_X + WALL, MOUTH_Y),
                                               (MOUTH_X + WALL, -3.7), (-MOUTH_X - WALL, -3.7)], SLAB,
                                              MOUTH_TOP + ROOF)), m, coll)
    tcx, tcy = tip_c(var)
    u, n, s0, s1 = corridor_frame(var)
    for side in (-1, 1):
        box = [(side * (s * u[0] + w * n[0]), s * u[1] + w * n[1]) for s, w in
               ((s0, -COR_Y), (s1, -COR_Y), (s1, COR_Y), (s0, COR_Y))]
        new_obj(f"g{name}_cor{side}", bm_from(*prism(box, SLAB, COR_TOP)), m, coll)
        cyl(f"g{name}_tip{side}", side * tcx, tcy, TIP_R, SLAB, TIP_APEX)


# --- the live J and the lens variants in Blender -------------------------------------------------------------------
def _apply_bool(ob, other, op):
    mod = ob.modifiers.new(op.lower(), "BOOLEAN")
    mod.operation, mod.solver, mod.object = op, "EXACT", other
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    ob.modifiers.clear()
    old = ob.data
    ob.data = me
    bpy.data.meshes.remove(old)


def _hull_mesh(name, pts, m, coll):
    bm = bmesh.new()
    for p in pts:
        bm.verts.new(bl(p))
    res = bmesh.ops.convex_hull(bm, input=bm.verts, use_existing_faces=False)
    drop = list({g for g in res["geom_interior"] + res["geom_unused"] if isinstance(g, bmesh.types.BMVert)})
    bmesh.ops.delete(bm, geom=drop, context="VERTS")
    return new_obj(name, bm, m, coll)


def _planes_mesh(name, planes, m, coll, size=40.0):
    """A convex region n . p <= d (plan coordinates) as a closed mesh: a big cube bisected by every plane."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2 * size)
    for n, d in planes:
        nb = Vector((n[0], -n[1], n[2]))
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=nb * d, plane_no=nb,
                               clear_outer=True)
        bmesh.ops.holes_fill(bm, edges=bm.edges[:], sides=0)
    return new_obj(name, bm, m, coll)


def _finish(ob, m_recess, m_win, win=None, panels=()):
    """Merges coplanar faces and colours the throat's cut faces (m_recess) and the window band's (m_win)."""
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.3), verts=bm.verts, edges=bm.edges)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(m_recess)
    me.materials.append(m_win)
    for p in me.polygons:
        p.use_smooth = False
        c, nn = p.center, p.normal
        q = (c.x + 0.01 * nn.x, -(c.y + 0.01 * nn.y), c.z + 0.01 * nn.z)
        if in_cutter(q):
            p.material_index = 1
        elif any(c.z < zb + 0.045 and _inside_poly(poly, c.x, -c.y, -0.02) for poly, zb in panels):
            p.material_index = 2
        elif win:
            for cx, cy, r_in, a0, a1 in win:
                r = math.hypot(c.x - cx, -c.y - cy)
                a = math.degrees(math.atan2(-c.y - cy, c.x - cx))
                if r < r_in + 0.03 and SILL - 0.01 <= c.z <= HEAD + 0.01 and a0 - 1 <= a <= a1 + 1:
                    p.material_index = 2


def j_hull_object(name, coll, m, m_recess, m_win):
    """The live hull J as the build makes it: ship_hull_shape.surface("J") (the throat notch cut)."""
    verts, faces, index = [], [], {}
    for poly, _n, _kind in surface("J"):
        f = []
        for p in poly:
            k = tuple(round(c, 5) for c in p)
            if k not in index:
                index[k] = len(verts)
                verts.append(p)
            f.append(index[k])
        if len(set(f)) >= 3:
            faces.append(f)
    bm = bmesh.new()
    vs = [bm.verts.new(bl(v)) for v in verts]
    for f in faces:
        try:
            bm.faces.new([vs[i] for i in dict.fromkeys(f)])
        except ValueError:
            pass
    ob = new_obj(name, bm, m, coll)
    _finish(ob, m_recess, m_win)
    v = VARIANTS["J"]
    hv = [Vector(bl(p)) for p in verts]
    far = max(hv, key=lambda q: q.x)
    return ob, (far.x, -far.y, far.z)


def lens_windows(name):
    """Per side (cx, cy, inner radius, a0, a1) of the window band in plan (deg)."""
    v = lens_var(name)
    cx, cy = v["tip_c"]
    u = math.degrees(lens_axis(v))
    w = math.degrees(WIN_HALF)
    return [(cx, cy, v["rim_r"] - WIN_DEPTH, u - w, u + w), (-cx, cy, v["rim_r"] - WIN_DEPTH, 180 - u - w, 180 - u + w)]


def lens_hull_object(name, coll, m, m_recess, m_win, cut_coll):
    """The union of the core, the lenses and the necks, the throat notch and the window bands cut away."""
    parts = [_hull_mesh(f"{name}_{pn}", pts, m, coll) for pn, pts in lens_parts(name)]
    ob = parts[0]
    ob.name = f"hull_{name}"
    for other in parts[1:]:
        _apply_bool(ob, other, "UNION")
        bpy.data.objects.remove(other, do_unlink=True)
    for cname, planes in cutters().items():
        cut = _planes_mesh(f"{name}_{cname}", planes, m, cut_coll)
        _apply_bool(ob, cut, "DIFFERENCE")
        bpy.data.objects.remove(cut, do_unlink=True)
    win = lens_windows(name)
    tree, (cx, cy, _r0, a0, a1) = bvh_of(ob), win[0]
    hidden = []   # the band's angles (deg off the axis) whose point 5 cm outside the rim is inside the hull
    for i in range(int(round((a1 - a0) / 2.5)) + 1):
        a = a0 + 2.5 * i
        q = (cx + (LENS[name]["rim_r"] + 0.05) * math.cos(math.radians(a)),
             cy + (LENS[name]["rim_r"] + 0.05) * math.sin(math.radians(a)), 0.5 * (SILL + HEAD))
        if inside(tree, bl(q)):
            hidden.append(round(a - 0.5 * (a0 + a1), 1))
    for k, (cx, cy, r0, a0, a1) in enumerate(win):
        nn = 32
        inner = [(cx + r0 * math.cos(math.radians(a0 + (a1 - a0) * i / nn)),
                  cy + r0 * math.sin(math.radians(a0 + (a1 - a0) * i / nn))) for i in range(nn + 1)]
        outer = [(cx + 6.0 * math.cos(math.radians(a0 + (a1 - a0) * i / nn)),
                  cy + 6.0 * math.sin(math.radians(a0 + (a1 - a0) * i / nn))) for i in range(nn + 1)]
        v, f = prism(inner + outer[::-1], SILL, HEAD)
        cut = new_obj(f"{name}_win{k}", bm_from(v, f), m, cut_coll)
        _apply_bool(ob, cut, "DIFFERENCE")
        bpy.data.objects.remove(cut, do_unlink=True)
    _finish(ob, m_recess, m_win, win)
    v = LENS[name]
    return ob, (v["tip_c"][0] + v["rim_r"], v["tip_c"][1], 2.2), hidden


def ray_hull_object(name, coll, m, m_recess, m_win, cut_coll):
    """P, Q: the body, the wings and the lenses united, the throat notch cut; then the window band (a thin shell round
    each lens's rim, so the fins stay whole) and the roof windows. Returns the hull, its tip, the band's hidden
    angles and the BVH before the windows (the skin's)."""
    v = RAYS[name]
    parts = [_hull_mesh(f"{name}_{pn}", pts, m, coll) for pn, pts in ray_parts(name)]
    ob = parts[0]
    ob.name = f"hull_{name}"
    for other in parts[1:]:
        _apply_bool(ob, other, "UNION")
        bpy.data.objects.remove(other, do_unlink=True)
    for cname, planes in cutters().items():
        cut = _planes_mesh(f"{name}_{cname}", planes, m, cut_coll)
        _apply_bool(ob, cut, "DIFFERENCE")
        bpy.data.objects.remove(cut, do_unlink=True)
    pre = bvh_of(ob)
    win = lens_windows(name)
    cx, cy, _r0, a0, a1 = win[0]
    hidden = []
    for i in range(int(round((a1 - a0) / 2.5)) + 1):
        a = a0 + 2.5 * i
        q = (cx + (v["rim_r"] + 0.05) * math.cos(math.radians(a)), cy + (v["rim_r"] + 0.05) * math.sin(math.radians(a)),
             0.5 * (SILL + HEAD))
        if inside(pre, bl(q)):
            hidden.append(round(a - 0.5 * (a0 + a1), 1))
    cutters_ = []
    for cx, cy, r0, a0, a1 in win:
        nn = 32
        arc = [math.radians(a0 + (a1 - a0) * i / nn) for i in range(nn + 1)]
        inner = [(cx + r0 * math.cos(t), cy + r0 * math.sin(t)) for t in arc]
        outer = [(cx + (v["rim_r"] + 0.1) * math.cos(t), cy + (v["rim_r"] + 0.1) * math.sin(t)) for t in arc]
        cutters_.append(prism(inner + outer[::-1], SILL, HEAD))
    panels = ray_panels(v)
    cutters_ += [prism(poly, zb, zb + 3.0) for poly, zb in panels]
    for k, (cv, cf) in enumerate(cutters_):
        cut = new_obj(f"{name}_win{k}", bm_from(cv, cf), m, cut_coll)
        _apply_bool(ob, cut, "DIFFERENCE")
        bpy.data.objects.remove(cut, do_unlink=True)
    _finish(ob, m_recess, m_win, win, panels)
    return ob, (v["tip_c"][0] + v["rim_r"], v["tip_c"][1], 2.2), hidden, pre


def ray_numbers(name, bvh):
    """The fin edge's, the ridge's and the vault's numbers on the hull before the windows."""
    v = RAYS[name]
    n0, f, b, st, _th = ray_edges(v)
    hx, hy = RM["hall"]["centre"]

    def thick(x, y):
        tb = vertical(bvh, x, y)
        return round(tb[0] - tb[1], 3) if tb else None

    def inward(p, q, k=0.1):   # a point k m in from the edge p..q's middle, toward the corridor's axis
        mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
        dx, dy = q[0] - p[0], q[1] - p[1]
        ln = math.hypot(dx, dy)
        nx, ny = -dy / ln, dx / ln
        if nx * (hx - mx) + ny * (hy - mx * 0 - my) < 0:
            nx, ny = -nx, -ny
        return mx + k * nx, my + k * ny
    ux, uy = ray_axis(v)
    cor = ray_rooms(v)["corridor_e"]
    sm = 0.5 * sum(cor["along"])
    cx, cy = v["tip_c"]
    rim = vertical(bvh, cx + (v["rim_r"] - 0.2) * ux, cy + (v["rim_r"] - 0.2) * uy)
    vs = [(what, p) for what, p in ray_samples(v) if what.startswith("vault")]
    vault = min((bvh.find_nearest(Vector(bl(p)))[3] if inside(bvh, bl(p)) else -bvh.find_nearest(Vector(bl(p)))[3])
                for _w, p in vs)
    return {"fin_edge_design_m": {"nose": v["edge_nose"], "lens": v["edge_lens"], "stern": v["trail_e"]},
            "fin_thickness_lead_mid_0_1m_in_m": thick(*inward(n0, f)),
            "fin_thickness_trail_mid_0_1m_in_m": thick(*inward(b, st)),
            "ridge_thickness_m": thick(hx + sm * ux, hy + sm * uy),
            "lens_rim_top_m": round(rim[0], 3) if rim else None,
            "lens_room": {"centre": [cx, cy], "radius": RAY_ROOM_R, "clear_out": RAY_CLEAR_OUT,
                          "clear_in": RAY_CLEAR_IN},
            "vault_skin_m": round(vault, 3), "front_tangent": [round(c, 3) for c in f],
            "rear_tangent": [round(c, 3) for c in b], "roof_windows": len(RAY_PANELS)}


def lens_details(name, bvh, coll, m_dark, m_ring, m_nozzle, m_ramp):
    """The bigger nozzle pods (housing, a ring round the end, a recessed nozzle), the canopies, the ramp, the legs."""
    v = lens_var(name)
    obs = []
    sy = lens_stern_y(v)
    n = 20
    for k, (x, h, r, out) in enumerate(LENS_PODS):
        y0, y1 = sy - POD_IN, sy + out
        circ = [(math.cos(2 * math.pi * a / n + math.pi / n), math.sin(2 * math.pi * a / n + math.pi / n))
                for a in range(n)]
        ri = 0.72 * r
        rings_ = [(r, y0), (r, y1), (ri, y1), (ri, y1 - POD_CUP)]
        vs = [(x + rr * c, yy, h + rr * s) for rr, yy in rings_ for c, s in circ]
        fs = [tuple(range(n - 1, -1, -1))]
        for j in range(3):
            fs += [(j * n + a, j * n + (a + 1) % n, (j + 1) * n + (a + 1) % n, (j + 1) * n + a) for a in range(n)]
        fs.append(tuple(3 * n + a for a in range(n)))
        obs.append(new_obj(f"{name}_pod{k}", bm_from(vs, fs), m_dark, coll))
        rv = [(x + rr * c, yy, h + rr * s) for rr, yy in ((1.1 * r, y1 - POD_RING), (1.1 * r, y1 + 0.05),
                                                           (0.97 * r, y1 + 0.05), (0.97 * r, y1 - POD_RING))
              for c, s in circ]
        rf = []
        for j in range(4):
            jn = (j + 1) % 4
            rf += [(j * n + a, j * n + (a + 1) % n, jn * n + (a + 1) % n, jn * n + a) for a in range(n)]
        obs.append(new_obj(f"{name}_ring{k}", bm_from(rv, rf), m_ring, coll))
        dv = [(x + 0.7 * r * c, y1 - POD_CUP + 0.02, h + 0.7 * r * s) for c, s in circ]
        obs.append(new_obj(f"{name}_nozzle{k}", bm_from(dv, [tuple(range(n))]), m_nozzle, coll))
    obs += details(name, {**VARIANTS["J"], "stern_y": sy, "no_pods": True, "half": v["tip_c"][0] + 2.0,
                          "tip_c": v["tip_c"]}, bvh, coll, m_dark, None, m_ramp)
    return obs


def ghost_from_rooms(name, rooms, coll, m):
    """The layout's rooms as they stand: the hall, the throat, the corridors' strips, the tip rooms."""
    def cyl(gname, cx, cy, r, h0, h1, nn=32):
        v = [(cx + r * math.cos(2 * math.pi * k / nn), cy + r * math.sin(2 * math.pi * k / nn), h) for h in (h0, h1)
             for k in range(nn)]
        f = [tuple(range(nn)), tuple(range(2 * nn - 1, nn - 1, -1))] + [(k, (k + 1) % nn, nn + (k + 1) % nn, nn + k)
                                                                         for k in range(nn)]
        new_obj(gname, bm_from(v, f), m, coll)
    for r in rooms.values():
        top = FLOOR + r["clear_h"] + ROOF
        if r["shape"] == "circle":
            cyl(f"g{name}_{r['id']}", *r["centre"], r["radius"] + WALL, SLAB,
                FLOOR + r.get("apex_h", r["clear_h"]) + ROOF)
        elif r["shape"] == "poly":
            new_obj(f"g{name}_{r['id']}", bm_from(*prism([tuple(p) for p in r["points"]], SLAB, top)), m, coll)
        elif r["shape"] == "strip":
            (ax, ay), (bx, by) = r["axis"]
            d = math.hypot(bx - ax, by - ay)
            u = ((bx - ax) / d, (by - ay) / d)
            nn = (-u[1], u[0])
            hw = r["width"] / 2 + WALL
            s0, s1 = r["along"]
            box = [(ax + s * u[0] + w * nn[0], ay + s * u[1] + w * nn[1]) for s, w in
                   ((s0, -hw), (s1, -hw), (s1, hw), (s0, hw))]
            new_obj(f"g{name}_{r['id']}", bm_from(*prism(box, SLAB, top)), m, coll)


VIEWS = {   # name: (location, rotation, ortho scale or None for perspective) in Blender coordinates (y north)
    "front": ((0.0, 60.0, 2.8), (math.pi / 2, 0.0, math.pi), 34.0),
    "side": ((-60.0, -4.0, 2.8), (math.pi / 2, 0.0, -math.pi / 2), 28.0),   # 2026-10-22 evening: the longer sterns
    "back": ((0.0, -60.0, 2.8), (math.pi / 2, 0.0, 0.0), 34.0),
    "top": ((0.0, -4.2, 60.0), (0.0, 0.0, 0.0), 46.0),
    "hero": ((-27.0, 27.0, 14.0), None, None),
}
HERO_AIM = Vector((-1.2, -3.5, 1.6)) if bpy else None
CROPS = {"front": "turnaround_1_front.png", "side": "turnaround_2_side.png", "back": "turnaround_3_back.png",
         "top": "turnaround_4_top.png"}


def pixels(path, w, h):
    img = bpy.data.images.load(str(path))
    sw, sh = img.size
    s = min(w / sw, h / sh)
    if abs(s - 1.0) > 1e-6:
        img.scale(max(1, int(sw * s)), max(1, int(sh * s)))
    iw, ih = img.size
    buf = np.empty(iw * ih * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    cell = np.zeros((h, w, 4), dtype=np.float32)
    cell[...] = BG
    y0, x0 = (h - ih) // 2, (w - iw) // 2
    cell[y0:y0 + ih, x0:x0 + iw] = buf.reshape(ih, iw, 4)
    bpy.data.images.remove(img)
    return cell


def over_bg(cell):
    a = cell[..., 3:4]
    out = cell * a + BG * (1 - a)
    out[..., 3] = 1.0
    return out


def save(arr, path):
    img = bpy.data.images.new(Path(path).stem, arr.shape[1], arr.shape[0])
    img.pixels.foreach_set(np.ascontiguousarray(arr, dtype=np.float32).ravel())
    img.filepath_raw, img.file_format = str(path), "PNG"
    img.save()
    bpy.data.images.remove(img)


def set_view(cam, view, tip=None):
    if view == "tipzoom":   # a three-quarter close-up of the east wing tip, from ahead, outboard and above
        aim = Vector(bl(tip)) + Vector((-2.8, 0.0, 0.0))
        cam.location = aim + Vector((12.0, 7.0, 7.5))
        cam.data.type, cam.data.lens = "PERSP", 35.0
        cam.rotation_euler = (aim - cam.location).to_track_quat("-Z", "Y").to_euler()
        return
    loc, rot, scale = VIEWS[view]
    cam.location = loc
    if scale is None:
        cam.data.type, cam.data.lens = "PERSP", 35.0
        cam.rotation_euler = (HERO_AIM - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    else:
        cam.data.type, cam.data.ortho_scale = "ORTHO", scale
        cam.rotation_euler = rot


def render(scene, path):
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def label_scene():
    sc = bpy.data.scenes.new("labels")
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "FLAT"
    sc.display.shading.color_type = "SINGLE"
    sc.display.shading.single_color = (1.0, 1.0, 1.0)
    sc.render.film_transparent = True
    sc.render.resolution_percentage = 100
    sc.world = bpy.data.worlds.new("lw")
    cam = bpy.data.objects.new("lcam", bpy.data.cameras.new("lcam"))
    cam.data.type = "ORTHO"
    sc.collection.objects.link(cam)
    sc.camera = cam
    cu = bpy.data.curves.new("ltext", "FONT")
    cu.size, cu.align_y = 0.17, "CENTER"
    tx = bpy.data.objects.new("ltext", cu)
    sc.collection.objects.link(tx)
    return sc


def label(sc, text, w, h, path):
    cam, tx = sc.objects["lcam"], sc.objects["ltext"]
    sc.render.resolution_x, sc.render.resolution_y = w, h
    cam.data.ortho_scale = w / 100.0
    cam.location = (w / 200.0, h / 200.0, 10.0)
    tx.data.body = text
    tx.location = (0.12, h / 200.0, 0.0)
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True, scene=sc.name)
    a = pixels(path, w, h)[..., 3:4]
    out = BG * (1 - a) + np.array([0.92, 0.92, 0.92, 1.0], dtype=np.float32) * a
    out[..., 3] = 1.0
    return out


def main():
    out = Path(arg("--out"))
    cells = out / "cells"
    cells.mkdir(parents=True, exist_ok=True)
    crops = Path(arg("--crops", "D:/prime-art-raw/ship/v1/meshy_in"))
    hero_2d = Path(arg("--hero", "D:/prime-game-design/ideas/ship-components/2d/hero.jpg"))
    names = arg("--variants", ",".join(VARIANTS)).split(",")
    scene = bpy.context.scene
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light, sh.color_type = "STUDIO", "MATERIAL"
    sh.show_cavity = False
    sh.show_specular_highlight = False
    sh.show_object_outline = False
    sh.show_shadows = False
    scene.world = bpy.data.worlds.new("bg")
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.data.clip_end = 300.0
    scene.collection.objects.link(cam)
    scene.camera = cam
    m_room = mat("room", (1.0, 1.0, 1.0))
    ghost = {}
    for name in names:   # each variant's rooms where it puts them
        ghost[name] = bpy.data.collections.new(f"rooms_{name}")
        scene.collection.children.link(ghost[name])
        if name in RAYS:
            ghost_from_rooms(name, ray_rooms(RAYS[name], ghost=True), ghost[name], m_room)
        elif name in LENS or VARIANTS[name].get("throat"):
            ghost_from_rooms(name, lens_rooms(LENS[name]) if name in LENS else RM, ghost[name], m_room)
        else:
            ghost_rooms(name, VARIANTS[name], ghost[name], m_room)
        ghost[name].hide_render = True
    cut_coll = bpy.data.collections.new("cutters")
    scene.collection.children.link(cut_coll)
    cut_coll.hide_render = True
    grey = mat("grey", (0.6, 0.6, 0.6))
    dark = mat("dark", (0.42, 0.42, 0.44))
    glass = mat("glass", (0.1, 0.12, 0.16))
    ramp = mat("ramp", (0.34, 0.34, 0.35))
    report, colls = {}, {}
    win = mat("window", (0.05, 0.06, 0.08))
    ring_m = mat("ring", (0.25, 0.25, 0.27))
    nozzle = mat("nozzle", (0.03, 0.03, 0.035))
    for name in names:
        lens = name in LENS
        var = LENS.get(name) or RAYS.get(name) or VARIANTS[name]
        coll = bpy.data.collections.new(f"v{name}")
        scene.collection.children.link(coll)
        if name in RAYS:   # the rays: the approved layout, the ridge and thin fins, the slanted lenses, the vault
            hull, tip, hidden, pre = ray_hull_object(name, coll, grey, ramp, win, cut_coll)
            obs = lens_details(name, pre, coll, dark, ring_m, nozzle, ramp)
            meas = measure(hull, pre, [o for o in obs if "ramp" not in o.name], {"throat": True},
                           pts=ray_samples(var))
            meas.update(ray_numbers(name, pre))
            meas["rim_radius_m"] = var["rim_r"]
            meas["pod_diameters_m"] = [round(2 * r, 2) for _x, _h, r, _o in LENS_PODS]
            meas["window_band"] = {"sill_h": SILL, "head_h": HEAD, "half_deg": round(math.degrees(WIN_HALF), 1),
                                   "axis_deg": round(math.degrees(lens_axis(var)), 1), "depth_m": WIN_DEPTH,
                                   "hidden_deg": hidden}
        elif lens:   # the lens-tip diamonds: the union, the bigger pods, ship.toml's rooms with the tips moved
            hull, tip, hidden = lens_hull_object(name, coll, grey, ramp, win, cut_coll)
            bvh = bvh_of(hull)
            obs = lens_details(name, bvh, coll, dark, ring_m, nozzle, ramp)
            meas = measure(hull, bvh, [o for o in obs if "ramp" not in o.name], {"throat": True},
                           lens_rooms(var))
            meas["rim_radius_m"] = var["rim_r"]
            meas["pod_diameters_m"] = [round(2 * r, 2) for _x, _h, r, _o in LENS_PODS]
            meas["window_band"] = {"sill_h": SILL, "head_h": HEAD, "half_deg": round(math.degrees(WIN_HALF), 1),
                                   "axis_deg": round(math.degrees(lens_axis(var)), 1), "depth_m": WIN_DEPTH,
                                   "hidden_deg": hidden}
        elif var.get("throat"):   # the live J (ship_hull_shape.surface) and ship.toml's rooms
            hull, tip = j_hull_object(f"hull_{name}", coll, grey, ramp, win)
            bvh = bvh_of(hull)
            obs = details(name, var, bvh, coll, dark, glass, ramp)
            meas = measure(hull, bvh, [o for o in obs if "ramp" not in o.name], var, RM)
            meas["pod_diameters_m"] = [round(2 * r, 2) for _x, _y, _h, r, _l in NOZZLES]
        else:
            hull, tip = hull_object(f"hull_{name}", var, coll, grey, ramp, cut_coll)
            bvh = bvh_of(hull)
            obs = details(name, var, bvh, coll, dark, glass, ramp)
            meas = measure(hull, bvh, [o for o in obs if "ramp" not in o.name], var)
        meas["tip"] = [round(v, 3) for v in tip]
        meas["variant"] = var
        meas["tip_radius_m"] = var.get("tip_r", 0.0)
        meas["edge_thickness_m"] = round(2 * var["lip"] if "lip" in var else 2 * var.get("tip_e", 0.0), 3)
        report[name] = meas
        colls[name] = coll
        print(f"BLOCKOUT {name}: {len(meas['pokes'])} interior points with less than {SKIN} m of skin"
              + (f", e.g. {meas['pokes'][:6]}" if meas["pokes"] else ""))
        print(f"BLOCKOUT {name} measures: " + json.dumps({k: v for k, v in meas.items() if k != "pokes"}))
    if "--no-render" in sys.argv:   # the numbers alone (a quick fit check)
        (out / "report.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
        return
    order = ("front", "side", "back", "top", "hero", "tipzoom")
    W, H = 320, 180
    shots, ghosts = {}, {}
    for name in names:
        for c in colls.values():
            c.hide_render = True
        colls[name].hide_render = False
        shots[name] = {}
        for view in order:
            set_view(cam, view, report[name]["tip"])
            scene.render.resolution_x, scene.render.resolution_y = (W, H)
            render(scene, cells / f"{name}_{view}.png")
            shots[name][view] = over_bg(pixels(cells / f"{name}_{view}.png", W, H))
        ghosts[name] = {}
        for view in ("top", "front"):
            set_view(cam, view)
            scene.render.resolution_x, scene.render.resolution_y = (640, 360)
            colls[name].hide_render, ghost[name].hide_render = False, True
            render(scene, cells / f"{name}_{view}_big.png")
            solid = over_bg(pixels(cells / f"{name}_{view}_big.png", 640, 360))
            colls[name].hide_render, ghost[name].hide_render = True, False
            render(scene, cells / "_mask.png")
            mask = pixels(cells / "_mask.png", 640, 360)[..., 3:4] * 0.3
            g = solid * (1 - mask) + np.array([1.0, 0.45, 0.1, 1.0], dtype=np.float32) * mask
            g[..., 3] = 1.0
            ghosts[name][view] = g
        colls[name].hide_render, ghost[name].hide_render = True, True
    lsc = label_scene()
    lab = cells / "_label.png"
    blank = np.zeros((H, W, 4), dtype=np.float32)
    blank[...] = BG
    top_down = [label(lsc, "2D turnaround (approved): front, side, back, top; hero   (last column: a close-up of the"
                      " east wing tip)", 6 * W, 28, lab),
                np.concatenate([pixels(crops / CROPS[v], W, H) for v in order[:4]] + [pixels(hero_2d, W, H), blank],
                               axis=1)]
    gl = []
    for name in names:
        m = report[name]
        var = LENS.get(name) or RAYS.get(name) or VARIANTS[name]
        tag = "  (tip windows)" if var.get("window") else ""
        if name in RAYS:
            tag += "  lens rooms ({:.1f}, {:.1f}), rim r {:.2f}, stern +{:.1f} m".format(*var["tip_c"], var["rim_r"],
                                                                                    var["stern_ext"])
        elif name in LENS:
            tag += "  lens tips at ({:.1f}, {:.1f}), rim r {:.1f}, stern +{:.1f} m, pods {:.2f}/{:.2f} m".format(
                *var["tip_c"], var["rim_r"], var["stern_ext"], *m["pod_diameters_m"][:2])
        elif var.get("throat"):
            tag += "  (the live hull, reference)"
        elif "tip_r" in var:
            tag += f"  tip r {var['tip_r']:.1f} m, edge {m['edge_thickness_m']:.2f} m" + (", smooth" if var.get("smooth")
                                                                                         else "")
        elif "tip_c" in var:
            tag += "  tip rooms at ({:.1f}, {:.1f})".format(*var["tip_c"])
        elif len(names) > 1 and any("tip_c" in VARIANTS[o] for o in names):
            tag += "  (last round, reference)"
        text = (f"{name}{tag}   span {m['span_m']:.1f} m   "
                f"length {m['length_m']:.1f} m   height {m['height_m']:.2f} m   "
                f"wing 1 m in {m['wing_thickness_1m_from_tip_m']:.2f} m   least skin {m['least_skin_m']:.2f} m"
                f"   pokes {len(m['pokes'])}")
        if name in RAYS:
            text = (f"{name}{tag}   span {m['span_m']:.1f}   length {m['length_m']:.1f}   "
                    f"fin edge {m['fin_edge_design_m']['lens']:.2f} (0.1 m in {m['fin_thickness_lead_mid_0_1m_in_m']:.2f})"
                    f"   ridge {m['ridge_thickness_m']:.2f}   lens rim h {m['lens_rim_top_m']:.2f}   least skin "
                    f"{m['least_skin_m']:.2f}   pokes {len(m['pokes'])}   vault skin {m['vault_skin_m']:.2f}")
        top_down.append(label(lsc, text, 6 * W, 28, lab))
        top_down.append(np.concatenate([shots[name][v] for v in order], axis=1))
        gl.append(label(lsc, text.split("   wing")[0].split("   fin edge")[0] + "   (rooms ghosted orange)", 1280, 28,
                        lab))
        gl.append(np.concatenate([ghosts[name]["top"], ghosts[name]["front"]], axis=1))
    save(np.concatenate(top_down[::-1], axis=0), out / "sheet.png")
    save(np.concatenate(gl[::-1], axis=0), out / "ghost.png")
    for p in (lab, cells / "_mask.png"):
        p.unlink(missing_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    bpy.data.scenes.remove(lsc)
    for c in colls.values():
        c.hide_render = False
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "blockout.blend"))
    print(f"BLOCKOUT sheet {out / 'sheet.png'} ghost {out / 'ghost.png'}")


if __name__ == "__main__":
    main()
