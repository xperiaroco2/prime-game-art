"""The throat vents (art #263 step 2, station 1; docs/ship.md "Station 1: the throat vents"), way B (art#263 comments
6363433518 and 6374327838, vents-b1): `station_vent_e` and its mirror `station_vent_w`. The body (the faceted bronze
frame round the empty well with its copper hinge caps, the column with its light bar, palm scanner and red lamp, the
feet) and the gill blade are built in Blender from the concept's views by ship_vent_b.py into <raw>/BODY and
<raw>/BLADE_GLB (way A's Meshy body only as the to-scale guide); the seven gill blades are copies of the one blade on
pivots by the caps; the bar's marker, the glows, the light pieces and the colliders are built here. Plain
Python: the harness (ship_build.py) makes the meshes and imports the body and the blades (parts with "glb"; a blade
carries "rot_u", its closed turn, and "hull", its box's corners for the checks).

The piece's frame: the spot at the origin, u (plan x) along the wall, v (plan y) out of the wall into the throat,
h absolute (the deck at FLOOR). East: +u runs toward the hall; the west piece mirrors u, so its column is toward the
hall too. In Godot (x, h, v): each blade a leaf `<id>_slat<k>` (k 1..7 from the top) with its origin on its pivot (the
caps' axis, along x): it opens with rotation.x = -OPEN_RAD * t (t 0 closed: the blades hang 33 deg down, each tip over the
next blade's back, an orange seam between; t 1 calm, as the concept's front and side views); the marker
`<id>_marker` a leaf with its origin at its rest point, the glass's bottom: position.y = rest + MARK_TRAVEL * t.
The game drives the glows by material: `int_halo__vent_heat` (the heat panel in the well, the problem state;
`<id>_heat`), `int_cyan__vent_cool` (the calm glow 4 mm in front of it: shown calm, hidden for the problem;
vents-b2: each panel carries its well lights, godot/ship/vent_glow.gd, so calm hides `heat`),
`glow_nav_white__vent_marker`, and the body's own faces `vent_a_body__lamp`, `vent_a_body__band`, `vent_a_body__hand`
(copies of the baked body material cut from it by colour and place). Convex colliders `<id>_col0-convcolonly` (the
box) and `<id>_col1-convcolonly` (the column)."""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import ship_interior as S
import ship_lib as L

FLOOR = S.FLOOR
BEND, IN, TOP = S.TH_BEND, S.TH_IN, S.TH_H      # the throat wall: vertical to 1.45, then 0.55 in at 2.3

for _name in ("int_halo__vent_heat", "int_cyan__vent_cool", "glow_nav_white__vent_marker"):
    L.MATERIALS[_name] = dict(L.MATERIALS[_name.split("__")[0]])
# the well's two glows (step 2: hotter and deeper, strength 1.5 read tan and pale blue under AgX)
L.MATERIALS["int_halo__vent_heat"].update(base=(1.0, 0.22, 0.0, 1.0), emission=(1.0, 0.22, 0.0), strength=12.0)
# way B: the calm cyan brighter (r6's barely showed between the blades)
L.MATERIALS["int_cyan__vent_cool"].update(base=(0.0, 0.55, 1.0, 1.0), emission=(0.0, 0.55, 1.0), strength=1.8)
# vents-b2: the well pours light (the concept's charm): the calm wall far brighter, the frame's strips brighter, the
# lamp a deep red (b1's read salmon under AgX: less strength, no green), the bar's amber saturated, its band clear green
L.MATERIALS["int_cyan__vent_cool"].update(base=(0.0, 0.42, 1.0, 1.0), emission=(0.0, 0.42, 1.0), strength=3.0)
BLADE, DARK = "vent_b_bronze", "int_dark"   # the blade GLB's main material
# the look step (vents-a4): every light a clean emissive piece over the body's painted one (a glow material's suffix
# names it; the strengths set for the game's night light, the concept's bright neon)
for _name, _base, _upd in (
        ("glow_cyan__vent_strip", "glow_cyan", dict(base=(0.05, 0.8, 1.0, 1.0), emission=(0.05, 0.8, 1.0), strength=3.5)),
        ("glow_cyan__vent_hand", "glow_cyan", dict(base=(0.15, 0.75, 1.0, 1.0), emission=(0.15, 0.75, 1.0), strength=2.0)),
        ("glow_nav_red__vent_lamp", "glow_nav_red", dict(base=(0.25, 0.0, 0.0, 1.0), emission=(0.8, 0.0, 0.0), strength=0.5)),
        ("glow_amber__vent_bar", "glow_amber", dict(base=(1.0, 0.36, 0.0, 1.0), emission=(1.0, 0.36, 0.0), strength=1.6)),
        ("glow_nav_green__vent_band", "glow_nav_green", dict(base=(0.0, 1.0, 0.08, 1.0), emission=(0.0, 1.0, 0.08),
                                                             strength=1.4)),
        ("glow_nav_white__vent_bar_hot", "glow_nav_white", dict(base=(1.0, 0.93, 0.75, 1.0), emission=(1.0, 0.93, 0.75),
                                                                 strength=1.8)),
        ("int_dark__vent_screen", "int_dark", {})):
    L.MATERIALS[_name] = {**L.MATERIALS[_base], **_upd}

# --- the body (ship_vent_b.py, vents-b1, 2026-10-24) ------------------------------------------------------------------
BODY = "ship/v4/vents-b/b2/body.glb"          # under the raw folder (way B: built in Blender, flat facets, chamfers)
LIGHTS = "ship/v4/vents-b/b2/lights.json"     # the light pieces' places on the body (ship_vent_b.py)
LIGHT_OUT = (0.0015, 0.0045)                  # a light piece's back and front off its surface
# the light bar's segments up the glass (front_ortho, bottom to top): white-hot, amber, the green band, amber
# (the green band at 141..146.4 cm of the bar's 62.2..154.8, the comment's numbers)
BAR = (("bar_hot", 0.0, 0.31, "glow_nav_white__vent_bar_hot"), ("bar", 0.31, 0.851, "glow_amber__vent_bar"),
       ("band", 0.851, 0.909, "glow_nav_green__vent_band"), ("bar_top", 0.909, 1.0, "glow_amber__vent_bar"))
BOX_U, COL_U = (-0.80, 0.466), (0.466, 0.80)  # the box with its feet, the column
BOX_TOP, BOX_FACE = 1.608, 0.415              # the box's top, the frame's face (v)
COL_TOP, COL_FACE = 1.84, 0.40                # the column's top (the lamp's dome after the 20 cm raise), its face
WELL_V = 0.115                                # the well's back
OPEN_U, OPEN_H = (-0.44, 0.28), (0.30, 1.33)   # the well's opening between the cap rows (way B: under the header)
CAP_U = (-0.48, 0.32)                         # the cap rows' centres
CAP_R = 0.035                                 # a cap's radius
PIVOT_V = 0.33                                # the caps' axis
GLASS_U, GLASS_H = (0.500, 0.556), (0.622, 1.548)   # the light bar's glass after the raise (the comment's 62.2..154.8)
GLASS_V = 0.405                               # the glass's face

# --- the blades ------------------------------------------------------------------------------------------------------
SLATS, PIVOT_TOP, PITCH = 7, 1.276, 0.15      # the pivots 127.6 .. 37.6 every 15 cm (the comment's numbers)
# step 3 (art#263, vents-a3): one rigid blade from Meshy (batch 2026-10-23-ship-vent-a-body item blade1, from our own
# isolated blade shot), cleaned by ship_vent_a_blade.py into <raw>/BLADE_GLB: about 500 triangles, its origin on the
# pivot, the calm pose; seven copies. Its blade.json (2026-10-23): the calm blade's box about the pivot (du, dv, dh),
# the calm seam straight from the front 4.7 cm (the slices' median), closed 1.9 cm at CLOSED_DEG, the first cut at
# 58 deg; 36.5 deg (a 7.5 mm seam) and 34 dipped the bottom blade's tip below the frame's bottom (vent_motion.gd).
# way B (vents-b1): one faceted claw built by ship_vent_b.py (412 triangles, the calm pose 22 deg tip down, bowed
# 1.4 cm), its box about the pivot from its blade.json
# vents-b2: the thicker, hooked claw (656 triangles; blade.json: the calm seam 4.0 cm, closed 6 mm at 8.9 deg, the
# first cut at 46.4 deg)
BLADE_GLB = "ship/v4/vents-b/b2/blade.glb"
BLADE_BOX = ((-0.361, 0.361), (-0.034, 0.264), (-0.0711, 0.052))
NOSE_R = 0.034                                # the root's back behind the pivot (ship_vent_b.SECTION)
# step 4 (vents-a4): the calm pose tilted 22 deg tip down (the concept's claws, the upper bevel facet to the front),
# the section squashed to 0.5 in h; blade_r5/blade.json: the calm seam 5.9 cm, closed 1.35 cm at CLOSED_DEG more
# (33 deg from flat, the bottom blade's limit), the first cut at 50; each blade carries a lit seam strip on its lower
# edge (`int_halo__vent_seam`, 32 triangles: the heat state, dark calm).
BLADE_SEAMS = {"calm": 0.040, "closed": 0.006, "first_cut_deg": 46.4}   # way B: ship_vent_b.blade_numbers()
CLOSED_DEG = 9.0
# closed: each blade CLOSED_DEG further down than calm, a seam of about 1.9 cm straight on (front_closed's lit seams)
OPEN_RAD = math.radians(CLOSED_DEG)
MARK_H = 0.03                                 # the marker's height; it slides from GLASS_H[0]
MARK_TRAVEL = GLASS_H[1] - GLASS_H[0] - MARK_H
COOL_V = WELL_V + 0.012                       # the cool glow's panel, just in front of the heat's
UC = (GLASS_U[0] + GLASS_U[1]) / 2            # the bar's centre line
UNIT = [-0.80, 0.80, -0.01, 0.60, -0.02, 1.85]   # u0 u1 v0 v1 h0 h1 (the calm blades' tips at v 0.598, the lamp 1.841)


def raw_root() -> Path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from runner import pins
    return Path(os.environ.get(pins.RAW_ENV) or pins.RAW_DEFAULT)


def cv(h: float) -> float:
    """How far the throat's wall face stands out at height h over the deck (its chamfer above BEND)."""
    return 0.0 if h <= BEND else (h - BEND) / (TOP - BEND) * IN


def turn(p, a):
    """(dv, dh) turned by a about the pivot (positive: the tip swings out and up)."""
    c, s = math.cos(a), math.sin(a)
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)


def blade_hull(hinge, a: float) -> list[tuple[float, float, float]]:
    """The calm blade's box (BLADE_BOX) about hinge (u, v, h), turned by a (turn's sense): its eight corners, for the
    checks without the GLB."""
    out = []
    for du in BLADE_BOX[0]:
        for dv in BLADE_BOX[1]:
            for dh in BLADE_BOX[2]:
                v, h = turn((dv, dh), a)
                out.append((hinge[0] + du, hinge[1] + v, hinge[2] + h))
    return out


def loft(loops) -> tuple[list, list]:
    n = len(loops[0])
    verts = [p for lp in loops for p in lp]
    faces = [(i * n + j, i * n + (j + 1) % n, (i + 1) * n + (j + 1) % n, (i + 1) * n + j)
             for i in range(len(loops) - 1) for j in range(n)]
    faces.append(tuple(range(n - 1, -1, -1)))
    faces.append(tuple(range((len(loops) - 1) * n, len(loops) * n)))
    return verts, faces


def prism(u0, u1, profile) -> tuple[list, list]:
    """A convex (v, h) profile (counter-clockwise seen from +u) extruded from u0 to u1."""
    return loft([[(u0, v, h) for v, h in profile], [(u1, v, h) for v, h in profile]])


def wall_profile(face: float, top: float) -> list[tuple[float, float]]:
    """A block's side from the wall to its face, its back on the wall (the chamfer above BEND)."""
    back = [(cv(top), FLOOR + top)] if top > BEND else []
    return [(0.0, FLOOR), (face, FLOOR), (face, FLOOR + top), *back, *([(0.0, FLOOR + BEND)] if top > BEND else []),
            *([] if top > BEND else [(0.0, FLOOR + top)])]


def slab(c, a1, a2, n, e1, e2, d0, d1):
    """A thin box on a surface: centre c, axes a1, a2 (half extents e1, e2) and its normal n, from d0 to d1 out."""
    def at(i, j, d):
        return tuple(c[k] + i * e1 * a1[k] + j * e2 * a2[k] + d * n[k] for k in range(3))
    v = [at(i, j, d) for d in (d0, d1) for j in (-1, 1) for i in (-1, 1)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return v, f


def ribbon(pts, w: float) -> list[list[tuple[float, float]]]:
    """An open 2D polyline as quads of width w with mitred joints (the mitre capped at a sharp turn)."""
    def nrm(a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy) or 1.0
        return (-dy / ln, dx / ln)
    side = []
    for i in range(len(pts)):
        ns = ([nrm(pts[i - 1], pts[i])] if i else []) + ([nrm(pts[i], pts[i + 1])] if i < len(pts) - 1 else [])
        mx, my = sum(q[0] for q in ns) / len(ns), sum(q[1] for q in ns) / len(ns)
        ln2 = mx * mx + my * my or 1.0
        k = min(1.0 / ln2, 3.0)
        side.append((mx * k * w / 2, my * k * w / 2))
    return [[(a[0] - sa[0], a[1] - sa[1]), (b[0] - sb[0], b[1] - sb[1]), (b[0] + sb[0], b[1] + sb[1]),
             (a[0] + sa[0], a[1] + sa[1])] for a, b, sa, sb in zip(pts, pts[1:], side, side[1:])]


def hand_outline() -> list[tuple[float, float]]:
    """The scanner's hand as one outline (the palm's width 1, the wrist at y 0, open there): a thumb and three
    fingers of one length (the four-fingered rule), the thumb on the left, tilted out 50 deg."""
    def u_shape(cx, cy, w, length, ang, steps=8):
        up, rt = (-math.sin(ang), math.cos(ang)), (math.cos(ang), math.sin(ang))
        r = w / 2
        tip = (cx + up[0] * (length - r), cy + up[1] * (length - r))
        pts = [(cx - rt[0] * r, cy - rt[1] * r)]
        for i in range(steps + 1):
            a = math.pi - math.pi * i / steps
            pts.append((tip[0] + rt[0] * r * math.cos(a) + up[0] * r * math.sin(a),
                        tip[1] + rt[1] * r * math.cos(a) + up[1] * r * math.sin(a)))
        pts.append((cx + rt[0] * r, cy + rt[1] * r))
        return pts

    def outside(pts, x):   # the thumb's points left of the palm's side, cut where they cross it
        out = []
        for a, b in zip(pts, pts[1:]):
            if a[0] <= x:
                out.append(a)
            if (a[0] - x) * (b[0] - x) < 0:
                t = (x - a[0]) / (b[0] - a[0])
                out.append((x, a[1] + t * (b[1] - a[1])))
        if pts[-1][0] <= x:
            out.append(pts[-1])
        return out
    pts = [(-0.40, 0.0), (-0.5, 0.14)]
    pts += outside(u_shape(-0.36, 0.34, 0.27, 0.62, math.radians(50)), -0.5)
    pts += [(-0.5, 0.80)]
    for cx in (-0.335, 0.0, 0.335):
        pts += u_shape(cx, 0.88, 0.25, 0.62, 0.0)
    pts += [(0.5, 0.80), (0.5, 0.14), (0.40, 0.0)]
    return pts


def lights(pid: str, s: float) -> list[dict]:
    """The clean light pieces over the body's painted lights (lights.json, the east frame; mirrored by s): the
    frame's cyan strips, the lamp's dome, the bar's segments with the green band, the hand's dark screen and its
    outline. Each a closed thin solid (its normals recalculated), its own glow material."""
    import json
    path = raw_root() / LIGHTS
    if not path.is_file():   # no raw folder (the pure-Python tests): no lights; a real build fails on the body first
        return []
    lj = json.loads(path.read_text(encoding="utf-8"))
    out = []

    def put(name, vf, mat):
        v, f = vf
        out.append(L.part(f"{pid}_{name}", [(s * x, y, FLOOR + h) for x, y, h in v], f, mat))
    strips = []   # one per place (a strip's texels can fall in two UV islands), none on the bar's glass (its own)
    for st in sorted(lj["strips"], key=lambda q: -q["texels"]):
        c = st["c"]
        if GLASS_U[0] - 0.01 <= c[0] <= GLASS_U[1] + 0.01 and GLASS_H[0] <= c[2] <= GLASS_H[1]:
            continue
        if all(math.dist(c, q["c"]) > 0.03 for q in strips):
            strips.append(st)
    for i, st in enumerate(sorted(strips, key=lambda q: (-q["c"][2], q["c"][0]))):
        put(f"strip{i + 1}", slab(st["c"], st["a1"], st["a2"], st["n"], max(st["e1"] - 0.002, 0.005),
                                  max(st["e2"] - 0.001, 0.003), *LIGHT_OUT), "glow_cyan__vent_strip")
    # the lamp: a dome on its faces' box, 3 mm proud
    lo, hi = lj["lamp"]["lo"], lj["lamp"]["hi"]
    cu, cw = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    r = max(hi[0] - lo[0], hi[1] - lo[1]) / 2 + 0.003
    h0, h1 = lo[2] + 0.002, hi[2] + 0.003
    hm = h0 + 0.55 * (h1 - h0)
    prof = [(r, h0), (r, hm)] + [(r * math.cos(math.radians(d)), hm + (h1 - hm) * math.sin(math.radians(d)))
                                  for d in (30, 55, 75)]
    seg, verts, faces = 20, [], []
    for rr, hh in prof:
        verts += [(cu + rr * math.cos(2 * math.pi * j / seg), cw + rr * math.sin(2 * math.pi * j / seg), hh)
                  for j in range(seg)]
    for i in range(len(prof) - 1):
        faces += [(i * seg + j, i * seg + (j + 1) % seg, (i + 1) * seg + (j + 1) % seg, (i + 1) * seg + j)
                  for j in range(seg)]
    verts.append((cu, cw, h1))
    k = (len(prof) - 1) * seg
    faces += [(k + j, k + (j + 1) % seg, len(verts) - 1) for j in range(seg)]
    faces.append(tuple(range(seg - 1, -1, -1)))
    put("lamp", (verts, faces), "glow_nav_red__vent_lamp")
    # the bar: its segments on the glass, under the marker (the marker stands 2 mm off the glass)
    gh = GLASS_H[1] - GLASS_H[0]
    for name, f0, f1, mat in BAR:
        put(name, L.box(GLASS_U[0] + 0.002, GLASS_U[1] - 0.002, GLASS_V + 0.0004, GLASS_V + 0.0016,
                        GLASS_H[0] + f0 * gh + (0.0015 if f0 else 0.0),
                        GLASS_H[0] + f1 * gh - (0.0015 if f1 < 1 else 0.0)), mat)
    # the hand: a dark screen on its faces' box, the outline 2 mm in front of it
    lo, hi = lj["hand"]["lo"], lj["hand"]["hi"]
    face = hi[1]
    su, sh = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2
    wu, wh = (hi[0] - lo[0]) / 2, (hi[2] - lo[2]) / 2
    # vents-b2: the dark screen is the bezel's octagon 1.5 mm in (b1's rectangle's corners cut through the octagonal
    # bezel and flickered), 1 mm off the body's screen face
    poly = shrink(lj["hand"].get("poly") or [(lo[0], lo[2]), (hi[0], lo[2]), (hi[0], hi[2]), (lo[0], hi[2])], 0.0015)
    n = len(poly)
    sv = [(x, face + d, y) for d in (0.0010, 0.0020) for x, y in poly]
    sf = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))] + [(j, (j + 1) % n, n + (j + 1) % n, n + j)
                                                                   for j in range(n)]
    put("screen", (sv, sf), "int_dark__vent_screen")
    # way B: the hand as big as the screen allows (4 mm in from its edges), centred on it
    pts = hand_outline()
    lw = 0.075
    x0, x1 = min(x for x, _ in pts) - lw, max(x for x, _ in pts) + lw
    y0, y1 = min(y for _, y in pts) - lw, max(y for _, y in pts) + lw
    scale = min((wu * 0.92 - 0.004) * 2 / (x1 - x0), (wh * 0.94 - 0.004) * 2 / (y1 - y0))
    xc, yc = (x0 + x1) / 2, (y0 + y1) / 2
    inner = shrink(poly, 0.004)   # the outline's every corner (its ribbon's half width out) 4 mm inside the octagon
    ring = [(x + dx, y + dy) for x, y in pts for dx in (-lw, lw) for dy in (-lw, lw)]
    while scale > 0.01 and not all(inside(inner, (su + (x - xc) * scale, sh + (y - yc) * scale)) for x, y in ring):
        scale *= 0.98
    hv, hf = [], []
    for q in ribbon(pts, lw):
        b = len(hv)
        hv += [(su + (x - xc) * scale, face + d, sh + (y - yc) * scale) for d in (0.0022, 0.0036) for x, y in q]
        hf += [tuple(b + i for i in f) for f in ((0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3),
                                                  (3, 7, 4, 0))]
    put("hand", (hv, hf), "glow_cyan__vent_hand")
    return out


def shrink(poly, d):
    """A convex polygon's edges moved d inward (as ship_vent_b.inset), counter-clockwise."""
    pts = [tuple(p) for p in poly]
    if sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1])) < 0:
        pts = pts[::-1]
    n, lines, out = len(pts), [], []
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy)
        lines.append(((a[0] - dy / ln * d, a[1] + dx / ln * d), (dx, dy)))
    for i in range(n):
        (p1, d1), (p2, d2) = lines[i - 1], lines[i]
        den = d1[0] * d2[1] - d1[1] * d2[0]
        if abs(den) < 1e-12:
            out.append(p2)
            continue
        t = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / den
        out.append((p1[0] + t * d1[0], p1[1] + t * d1[1]))
    return out


def inside(poly, q) -> bool:
    """q inside a convex counter-clockwise polygon."""
    return all((b[0] - a[0]) * (q[1] - a[1]) - (b[1] - a[1]) * (q[0] - a[0]) >= 0
               for a, b in zip(poly, poly[1:] + poly[:1]))


def station_vent(args, layout):
    pid, s = args["id"], (-1.0 if args.get("side") == "w" else 1.0)
    parts = []

    def add(name, vf, mat, **extra):
        v, f = vf
        p = L.part(f"{pid}_{name}", [(s * x, y, h) for x, y, h in v], f, mat)
        if "origin" in extra:
            o = extra["origin"]
            extra["origin"] = (s * o[0], o[1], o[2])
        p.update(extra)
        parts.append(p)

    # the body: Meshy's, cleaned and baked (its lamp, band and hand faces carry their own materials)
    parts.append({"name": f"{pid}_body", "glb": str(raw_root() / BODY), "offset": (0.0, 0.0, FLOOR),
                  "mirror_u": s < 0})
    # the glow in the well behind the blades: the heat (the problem) and, 4 mm in front of it, the cool glow (calm)
    ou = (OPEN_U[0] + 0.004, OPEN_U[1] - 0.004)
    oh = (FLOOR + OPEN_H[0] + 0.004, FLOOR + OPEN_H[1] - 0.004)
    add("heat", L.box(*ou, WELL_V + 0.002, WELL_V + 0.006, *oh), "int_halo__vent_heat")
    add("cool", L.box(*ou, COOL_V - 0.002, COOL_V + 0.002, *oh), "int_cyan__vent_cool")
    # the marker on the bar's glass
    add("marker", L.box(GLASS_U[0] + 0.004, GLASS_U[1] - 0.004, GLASS_V + 0.002, GLASS_V + 0.009, FLOOR + GLASS_H[0],
                        FLOOR + GLASS_H[0] + MARK_H), "glow_nav_white__vent_marker",
        origin=(UC, GLASS_V + 0.005, FLOOR + GLASS_H[0]))
    parts += lights(pid, s)
    # the blades: seven copies of the one Meshy blade, leaves with their origin on the pivot (the caps' axis), closed
    u0, u1 = CAP_U[0] + 0.012, CAP_U[1] - 0.012
    for k in range(SLATS):
        hinge = ((u0 + u1) / 2, PIVOT_V, FLOOR + PIVOT_TOP - k * PITCH)
        parts.append({"name": f"{pid}_slat{k + 1}", "glb": str(raw_root() / BLADE_GLB), "mirror_u": s < 0,
                      "offset": (s * hinge[0], hinge[1], hinge[2]), "rot_u": -OPEN_RAD,
                      "origin": (s * hinge[0], hinge[1], hinge[2]),
                      "hull": [(s * x, y, h) for x, y, h in blade_hull(hinge, -OPEN_RAD)]})
    # convex colliders: the box and the column, their backs on the wall
    add("col0-convcolonly", prism(BOX_U[0], BOX_U[1], wall_profile(BOX_FACE, BOX_TOP)), DARK)
    add("col1-convcolonly", prism(COL_U[0], COL_U[1], wall_profile(COL_FACE, COL_TOP)), DARK)
    return parts
