"""The throat vents (art #263 step 2, station 1; docs/ship.md "Station 1: the throat vents"), way B (art#263 comments
6363433518 and 6374327838, vents-b1): `station_vent_e` and its mirror `station_vent_w`. The body (the faceted bronze
frame round the empty well with its copper hinge caps, the column with its light bar, palm scanner and red lamp, the
feet) and the gill blade are built in Blender from the concept's views by ship_vent_b.py into <raw>/BODY and
<raw>/BLADE_GLB (way A's Meshy body only as the to-scale guide); the seven gill blades are copies of the one blade on
pivots by the caps; the bar's marker, the glows, the light pieces and the colliders are built here. Plain
Python: the harness (ship_build.py) makes the meshes and imports the body and the blades (parts with "glb"; a blade
carries "rot_u", its closed turn, and "hull", its box's corners for the checks). Way A (Meshy's body and blade,
ship_vent_a*.py) is archived: its scripts stay for the record, nothing here imports its files.

The piece's frame: the spot at the origin, u (plan x) along the wall, v (plan y) out of the wall into the throat,
h absolute (the deck at FLOOR). East: +u runs toward the hall; the west piece mirrors u, so its column is toward the
hall too. In Godot (x, h, v): each blade a leaf `<id>_slat<k>` (k 1..7 from the top) with its origin on its pivot (the
caps' axis, along x): it opens with rotation.x = -OPEN_RAD * t (t 0 shut: the blades turned CLOSED_DEG down from calm,
each tip over the next blade's back like shingles, an orange seam between; t 1 calm, standing open as the concept's
front view; godot/ship/vent_anim.gd drives them in degrees from shut); the marker
`<id>_marker` a leaf with its origin at its rest point, the glass's bottom: position.y = rest + MARK_TRAVEL * t.
The game drives the glows by material: `int_halo__vent_heat` (the heat panel in the well, the problem state;
`<id>_heat`), `int_cyan__vent_cool` (the calm glow 4 mm in front of it: shown calm, hidden for the problem;
vents-b2: each panel carries its well lights, godot/ship/vent_glow.gd, so calm hides `heat`),
`glow_nav_white__vent_marker`, and the body's own faces `vent_a_body__lamp`, `vent_a_body__band`, `vent_a_body__hand`
(the body's dark glass under the light pieces; the names kept from way A). Convex colliders `<id>_col0-convcolonly` (the
box) and `<id>_col1-convcolonly` (the column)."""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import ship_interior as S
import ship_lib as L

FLOOR = S.FLOOR
BEND, IN, TOP = S.TUN_BEND, S.TUN_IN, S.TH_H    # the throat wall they were built for (no longer placed since the gills):
                                                # vertical to 1.45, then 0.55 in at 2.3 (the tunnel keeps that profile)

for _name in ("int_halo__vent_heat", "int_cyan__vent_cool", "glow_nav_white__vent_marker"):
    L.MATERIALS[_name] = dict(L.MATERIALS[_name.split("__")[0]])
# the well's two glows. vents-b3: the heat a deep red-orange (b2's 1/0.22/0 at 12 read peach under AgX), the calm
# cyan saturated (b2's strength 3 read ice-blue); the lamp a deep red, the bar's amber saturated, its band clear green
L.MATERIALS["int_halo__vent_heat"].update(base=(1.0, 0.10, 0.0, 1.0), emission=(1.0, 0.10, 0.0), strength=4.0)
L.MATERIALS["int_cyan__vent_cool"].update(base=(0.0, 0.50, 1.0, 1.0), emission=(0.0, 0.50, 1.0), strength=1.4)
DARK = "int_dark"                             # the colliders' material
# the look step (vents-a4): every light a clean emissive piece over the body's painted one (a glow material's suffix
# names it; the strengths set for the game's night light, the concept's bright neon)
for _name, _base, _upd in (
        ("glow_cyan__vent_strip", "glow_cyan", dict(base=(0.0, 0.62, 1.0, 1.0), emission=(0.0, 0.62, 1.0), strength=1.3)),
        ("glow_cyan__vent_hand", "glow_cyan", dict(base=(0.0, 0.62, 1.0, 1.0), emission=(0.0, 0.62, 1.0), strength=1.3)),
        ("glow_nav_red__vent_lamp", "glow_nav_red", dict(base=(0.25, 0.0, 0.0, 1.0), emission=(0.8, 0.0, 0.0), strength=0.5)),
        ("glow_amber__vent_bar", "glow_amber", dict(base=(1.0, 0.36, 0.0, 1.0), emission=(1.0, 0.36, 0.0), strength=1.6)),
        ("glow_nav_green__vent_band", "glow_nav_green", dict(base=(0.0, 1.0, 0.08, 1.0), emission=(0.0, 1.0, 0.08),
                                                             strength=1.4)),
        ("glow_nav_white__vent_bar_hot", "glow_nav_white", dict(base=(1.0, 0.93, 0.75, 1.0), emission=(1.0, 0.93, 0.75),
                                                                 strength=1.8)),
        ("int_dark__vent_screen", "int_dark", dict(base=(0.002, 0.002, 0.003, 1.0), metallic=0.0, roughness=0.7))):
    L.MATERIALS[_name] = {**L.MATERIALS[_base], **_upd}

# --- the body (ship_vent_b.py, vents-b1, 2026-10-24; vents-b3 the heavier frame; vents-b4 the recess, the scanner) ---
# vents-b4: a review build (`SHIP_VENT_REVIEW`, a JSON object: "dir" the body's folder under the raw folder, "scan_h"
# its scanner height, "recess" {"e": m, "w": m}; vents-b5: "dir_w" the west body's folder, "tip_back" {"e": m, "w": m}
# its blades' depth) builds the grids' variants; never set for the game's build
_REVIEW = json.loads(os.environ.get("SHIP_VENT_REVIEW") or "{}")
_BODY_DIR = _REVIEW.get("dir", "ship/v4/vents-b/b5b")
BODY = _BODY_DIR + "/body.glb"                # under the raw folder (way B: built in Blender, flat facets, chamfers)
LIGHTS = _BODY_DIR + "/lights.json"           # the light pieces' places on the body (ship_vent_b.py)
_BODY_W = _REVIEW.get("dir_w", _BODY_DIR)
# vents-b4: the vent sat RECESS into the throat wall; vents-b5: back on the wall's face (the engineer did not mean the
# recess), RECESS 0, the wall's modules behind it the pillow panels again (as b3). The parts still move RECESS behind
# the spot, so a review can try one. It is 0 because the engineer did not mean the recess (b4's 8 cm read as built
# into the wall). One source: ship.toml's `recess_m` on the vents' spots
RECESS = next(s["recess_m"] for s in S._SHIP["stations"]["spot"] if s["id"] == "vent_e")
RECESS_SIDE = {k: float(_REVIEW.get("recess", {}).get(k, RECESS)) for k in "ew"}
# vents-b4: the scanner's centre over the deck (ship_vent_b.SCAN_H; b3 1.398), the column's top dropped with it
SCAN_H = float(_REVIEW.get("scan_h", 1.20))
COL_DROP = 1.398 - SCAN_H
LIGHT_OUT = (0.0015, 0.0045)                  # a light piece's back and front off its surface
# the light bar's segments up the glass (front_ortho, bottom to top): white-hot, amber, the green band, amber
# (the green band at 141..146.4 cm of the bar's 62.2..154.8, the comment's numbers)
BAR = (("bar_hot", 0.0, 0.31, "glow_nav_white__vent_bar_hot"), ("bar", 0.31, 0.851, "glow_amber__vent_bar"),
       ("band", 0.851, 0.909, "glow_nav_green__vent_band"), ("bar_top", 0.909, 1.0, "glow_amber__vent_bar"))
# vents-b5: the box's right side and opening 4 cm along (ship_vent_b.BOX_DU), the side column wider (b4 0.466..0.80)
BOX_DU = -0.04
BOX_U, COL_U = (-0.80, 0.466 + BOX_DU), (0.466 + BOX_DU, 0.80)   # the box with its feet, the column
BOX_TOP, BOX_FACE = 1.64, 0.44                # the box's top, the frame's face (v; vents-b3: the fatter shoulder)
COL_TOP, COL_FACE = 1.84 - COL_DROP, 0.40     # the column's top (the lamp's dome, vents-b4 dropped), its face
# vents-b5: the blades inside the frame: the calm tips TIP_BACK behind the frame's face (ship_vent_b.TIP_BACK; the
# review grid's 0, 3 and 6 cm), the hinge line PIVOT_V = BOX_FACE - TIP_BACK - TIP_DV (b4 0.33: the tips 14.7 cm past
# the face), the well's back WELL_GAP behind it (b4 0.115)
TIP_DV, WELL_GAP = 0.257, 0.065
TIP_BACK = 0.03
TIP_BACK_SIDE = {k: float(_REVIEW.get("tip_back", {}).get(k, TIP_BACK)) for k in "ew"}


def depths(tip_back: float) -> tuple[float, float]:
    """The hinge line and the well's back for blades tip_back behind the frame's face (ship_vent_b's numbers)."""
    pivot = round(BOX_FACE - tip_back - TIP_DV, 4)
    return pivot, round(pivot - WELL_GAP, 4)


PIVOT_V, WELL_V = depths(TIP_BACK)            # the caps' axis (0.153), the well's back (0.088)
# the well's opening between the cap rows (way B: under the header); vents-b5: its floor 0.22 (b4 0.30), under the shut
# bottom blade's tip (0.238)
OPEN_U, OPEN_H = (-0.44 + BOX_DU, 0.28 + BOX_DU), (0.216, 1.33)
CAP_U = (-0.48 + BOX_DU, 0.32 + BOX_DU)       # the cap rows' centres
# the light bar's glass (vents-b4: its top dropped; vents-b5: 4 cm along with the wider column), the scanner's centre
# and the lamp's axis along the wall (ship_vent_b.SCAN_U, LAMP)
GLASS_U, GLASS_H = (0.460, 0.516), (0.622, 1.548 - COL_DROP)
SCAN_U, LAMP_U = 0.660, 0.615
GLASS_V = 0.405                               # the glass's face

# --- the blades ------------------------------------------------------------------------------------------------------
SLATS, PIVOT_TOP, PITCH = 7, 1.276, 0.15      # the pivots 127.6 .. 37.6 every 15 cm (the comment's numbers)
# One blade built by ship_vent_b.py into <raw>/BLADE_GLB, its origin on the pivot, in the calm pose; seven copies. Its
# blade.json: the calm blade's box about the pivot (du, dv, dh), the seams straight from the front, the first cut.
# Each blade carries a lit seam strip on its lip (`int_halo__vent_seam`: the heat state, dark calm). (Way A's Meshy
# blade, b1's faceted claw and b2's hooked claw are in the history: b2's calm sat 9 deg from shut with a 4 cm seam.)
# vents-b3: the swept wedge standing open (blade.json: the calm seam 5.4 cm, shut with a 1 cm overlap from 18.1 deg,
# the first cut at 57 deg); shut is CLOSED_DEG 20 below calm, a 1.8 cm overlap
BLADE_GLB = "ship/v4/vents-b/b3/blade.glb"
BLADE_BOX = ((-0.361, 0.361), (-0.030, 0.257), (-0.056, 0.054))
NOSE_R = 0.030                                # the root's back behind the pivot (ship_vent_b.SECTION; ship --motion's hinge check)
BLADE_SEAMS = {"calm": 0.054, "closed": -0.018, "first_cut_deg": 57.0}   # ship_vent_b.blade_numbers(), closed at CLOSED_DEG
CLOSED_DEG = 20.0
OPEN_RAD = math.radians(CLOSED_DEG)
MARK_H = 0.03                                 # the marker's height; it slides from GLASS_H[0]
MARK_TRAVEL = GLASS_H[1] - GLASS_H[0] - MARK_H
COOL_V = WELL_V + 0.012                       # the cool glow's panel, just in front of the heat's
UC = (GLASS_U[0] + GLASS_U[1]) / 2            # the bar's centre line
# u0 u1 v0 v1 h0 h1 in the spot's frame (vents-b5: the column's foot 0.49 the proudest, the blades inside the frame;
# b4 0.60 with the calm tips at 0.598; the backs RECESS behind the wall's face)
UNIT = [-0.80, 0.80, round(-0.01 - RECESS, 4), round(0.50 - RECESS, 4), -0.02, 1.85]


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


HAND_W = 0.085     # vents-b4: the hand's line width (the palm's width 1): one even stroke all round
HAND_K = 0.28      # the fillet where the thumb meets the palm (0.12 folded the stroke's outer side; vents-b5: 0.20 folded it
                   # with the higher thumb)
# vents-b5: human finger lengths (the engineer): index, middle, ring from the thumb's side, the middle longest, the ring
# a little shorter, the index the shortest; narrower fingers (HAND_FR, b4 0.125) with wider U gaps between (HAND_GAP,
# b4 0.125), so the dark gap inside the stroke reads at 2 m (b4 0.04 of the palm's width, now 0.085); the thumb a
# little lower and shorter, 41 deg out from the index's line (b4 48)
HAND_FINGERS = (-0.39, 0.0, 0.39)     # the three fingers' centre lines (index, middle, ring)
HAND_TIPS = (1.60, 1.80, 1.70)        # their tips (b4 one length, 1.705)
HAND_TIP = max(HAND_TIPS)
HAND_FR = 0.11                        # a finger's half width
HAND_GAP = 0.17                       # the gap between two fingers (their U crotch's width)
HAND_THUMB = ((-0.30, 0.36), (-0.72, 0.84), 0.125)   # its axis from the palm out to the tip's centre, its half width
# vents-b5b: the hand's box 70 % of the screen's height (b4/b5 80 %: the ring finger's tip ran into the octagon's top
# right corner and the hand read off-centre), its box centred on the octagon's
HAND_FILL = 0.70


def _hand_field(x: float, y: float) -> float:
    """vents-b4: the hand's silhouette as a signed distance (the palm's width 1, its heel at y 0; negative inside): a
    palm with rounded heel corners, three fingers (vents-b5: HAND_TIPS, capsules 2 HAND_FR wide, U crotches HAND_GAP
    wide), a thumb tilted out (HAND_THUMB), filleted into the palm."""
    def capsule(ax, ay, bx, by, r):
        px, py, dx, dy = x - ax, y - ay, bx - ax, by - ay
        t = max(0.0, min(1.0, (px * dx + py * dy) / (dx * dx + dy * dy)))
        return math.hypot(px - dx * t, py - dy * t) - r
    # the palm: x -0.5..0.5, y 0..1.08, its heel corners rounded 0.30 (its top under the fingers)
    rr = 0.30 if y < 0.54 else 0.0
    qx, qy = abs(x) - 0.5 + rr, abs(y - 0.54) - 0.54 + rr
    palm = math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0) - rr
    d = min([palm] + [capsule(cx, 0.70, cx, tip - HAND_FR, HAND_FR) for cx, tip in zip(HAND_FINGERS, HAND_TIPS)])
    for a, b in zip(HAND_FINGERS, HAND_FINGERS[1:]):   # the crotches: round at the bottom, the gap's half width
        gx = (a + b) / 2
        d = max(d, -capsule(gx, 1.08, gx, 3.0, HAND_GAP / 2))
    (ax, ay), (bx, by), tr = HAND_THUMB
    th = capsule(ax, ay, bx, by, tr)
    h = max(0.0, min(1.0, 0.5 + 0.5 * (th - d) / HAND_K))   # a smooth union (polynomial smin)
    return th * (1 - h) + d * h - HAND_K * h * (1 - h)



def hand_outline(step: float = 0.004, turn_deg: float = 7.0, max_len: float = 0.10) -> list[tuple[float, float]]:
    """vents-b4: the hand's silhouette (_hand_field's zero line) as a closed counter-clockwise loop: walked along its
    tangent from the palm's right side, pulled back onto the line each step, then kept where it turns turn_deg or
    every max_len (smooth curves, few points on the straights). b3's ribbon of mitred corners read ugly."""
    def grad(x, y, e=1e-5):
        gx = (_hand_field(x + e, y) - _hand_field(x - e, y)) / (2 * e)
        gy = (_hand_field(x, y + e) - _hand_field(x, y - e)) / (2 * e)
        n = math.hypot(gx, gy) or 1.0
        return gx / n, gy / n

    def snap(x, y):
        for _ in range(3):
            f = _hand_field(x, y)
            gx, gy = grad(x, y)
            x, y = x - f * gx, y - f * gy
        return x, y
    start = snap(0.5, 0.6)
    pts, (x, y), walked = [start], start, 0.0
    while True:
        gx, gy = grad(x, y)
        x, y = snap(x - gy * step, y + gx * step)
        walked += step
        if walked > 1.0 and math.dist((x, y), start) < step * 1.5:
            break
        pts.append((x, y))
        if walked > 40.0:
            raise RuntimeError("the hand's outline did not close")
    keep, last_a, run = [pts[0]], None, 0.0
    for a, b in zip(pts, pts[1:]):
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        run += math.dist(a, b)
        if last_a is None:
            last_a = ang
        if abs((ang - last_a + math.pi) % (2 * math.pi) - math.pi) >= math.radians(turn_deg) or run >= max_len:
            keep.append(b)
            last_a, run = ang, 0.0
    return keep


def hand_stroke(pts, w: float = HAND_W):
    """The loop's even stroke: per point its outer and inner offsets w/2 along the field's normal (exact on a level
    line; every curve's radius is over w/2, so neither side folds)."""
    out = []
    for x, y in pts:
        e = 1e-5
        gx = (_hand_field(x + e, y) - _hand_field(x - e, y)) / (2 * e)
        gy = (_hand_field(x, y + e) - _hand_field(x, y - e)) / (2 * e)
        n = math.hypot(gx, gy) or 1.0
        out.append(((x + gx / n * w / 2, y + gy / n * w / 2), (x - gx / n * w / 2, y - gy / n * w / 2)))
    return out


def lights(pid: str, s: float, body_dir: str = _BODY_DIR) -> list[dict]:
    """The clean light pieces over the body's painted lights (lights.json, the east frame; mirrored by s): the
    frame's cyan strips, the lamp's dome, the bar's segments with the green band, the hand's dark screen and its
    outline. Each a closed thin solid (its normals recalculated), its own glow material."""
    import json
    path = raw_root() / body_dir / "lights.json"
    if not path.is_file():
        if (raw_root() / body_dir / "body.glb").is_file():   # vents-b3: a body without its lights builds a silent vent
            raise FileNotFoundError(f"{path}: the vent's lights.json is missing beside its body.glb")
        return []   # no raw folder (the pure-Python tests): no lights; a real build fails on the body first
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
    # vents-b3: more rings and segments, shaded smooth (b2's dome showed its facets)
    prof = [(r, h0), (r, hm)] + [(r * math.cos(math.radians(d)), hm + (h1 - hm) * math.sin(math.radians(d)))
                                  for d in (15, 30, 45, 60, 72, 84)]
    seg, verts, faces = 32, [], []
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
    out[-1]["smooth_deg"] = 40.0
    # the bar: its segments on the glass, under the marker (the marker stands 2 mm off the glass)
    gh = GLASS_H[1] - GLASS_H[0]
    for name, f0, f1, mat in BAR:
        put(name, L.box(GLASS_U[0] + 0.002, GLASS_U[1] - 0.002, GLASS_V + 0.0004, GLASS_V + 0.0016,
                        GLASS_H[0] + f0 * gh + (0.0015 if f0 else 0.0),
                        GLASS_H[0] + f1 * gh - (0.0015 if f1 < 1 else 0.0)), mat)
    # the hand: a dark screen on its faces' box, the outline 2 mm in front of it
    lo, hi = lj["hand"]["lo"], lj["hand"]["hi"]
    face = hi[1]
    # vents-b2: the dark screen is the bezel's octagon 1.5 mm in (b1's rectangle's corners cut through the octagonal
    # bezel and flickered), 1 mm off the body's screen face
    poly = shrink(lj["hand"].get("poly") or [(lo[0], lo[2]), (hi[0], lo[2]), (hi[0], hi[2]), (lo[0], hi[2])], 0.0015)
    n = len(poly)
    sv = [(x, face + d, y) for d in (0.0010, 0.0020) for x, y in poly]
    sf = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))] + [(j, (j + 1) % n, n + (j + 1) % n, n + j)
                                                                   for j in range(n)]
    put("screen", (sv, sf), "int_dark__vent_screen")
    # vents-b4: the hand an even stroke round its smooth silhouette (hand_outline, hand_stroke), its box HAND_FILL of
    # the screen's height, centred on the screen's octagon, every point 1 cm inside it
    st = hand_stroke(hand_outline())
    allp = [q for pair in st for q in pair]
    x0, x1 = min(x for x, _ in allp), max(x for x, _ in allp)
    y0, y1 = min(y for _, y in allp), max(y for _, y in allp)
    pu, ph = [q[0] for q in poly], [q[1] for q in poly]
    su, sh = (min(pu) + max(pu)) / 2, (min(ph) + max(ph)) / 2
    scale = min((max(ph) - min(ph)) * HAND_FILL / (y1 - y0), (max(pu) - min(pu)) * 0.90 / (x1 - x0))
    xc, yc = (x0 + x1) / 2, (y0 + y1) / 2
    inner = shrink(poly, 0.010)
    while scale > 0.01 and not all(inside(inner, (su + (x - xc) * scale, sh + (y - yc) * scale)) for x, y in allp):
        scale *= 0.98
    n = len(st)
    hv = [(su + (q[0] - xc) * scale, face + d, sh + (q[1] - yc) * scale)
          for d in (0.0036, 0.0022) for pair in st for q in pair]   # the front's outer, inner pairs, then the back's
    hf = []
    for i in range(n):
        j = (i + 1) % n
        fo, fi, fo2, fi2 = 2 * i, 2 * i + 1, 2 * j, 2 * j + 1
        bo, bi, bo2, bi2 = fo + 2 * n, fi + 2 * n, fo2 + 2 * n, fi2 + 2 * n
        hf += [(fo, fo2, fi2, fi), (bo, bi, bi2, bo2), (fo, bo, bo2, fo2), (fi, fi2, bi2, bi)]
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

    # the body: ship_vent_b.py's (its lamp, band and hand faces carry their own dark glass materials)
    body_dir = _BODY_W if s < 0 else _BODY_DIR
    pivot_v, well_v = depths(TIP_BACK_SIDE["w" if s < 0 else "e"])
    cool_v = well_v + (COOL_V - WELL_V)
    parts.append({"name": f"{pid}_body", "glb": str(raw_root() / body_dir / "body.glb"), "offset": (0.0, 0.0, FLOOR),
                  "mirror_u": s < 0})
    # the glow in the well behind the blades: the heat (the problem) and, 4 mm in front of it, the cool glow (calm)
    ou = (OPEN_U[0] + 0.004, OPEN_U[1] - 0.004)
    # vents-b3: the panels end under the top blade's root (b2's showed as a cyan plate in the slot over the top blade)
    oh = (FLOOR + OPEN_H[0] + 0.004, FLOOR + PIVOT_TOP - 0.03)

    add("heat", L.box(*ou, well_v + 0.002, well_v + 0.006, *oh), "int_halo__vent_heat")
    add("cool", L.box(*ou, cool_v - 0.002, cool_v + 0.002, *oh), "int_cyan__vent_cool")
    # the marker on the bar's glass
    add("marker", L.box(GLASS_U[0] + 0.004, GLASS_U[1] - 0.004, GLASS_V + 0.002, GLASS_V + 0.009, FLOOR + GLASS_H[0],
                        FLOOR + GLASS_H[0] + MARK_H), "glow_nav_white__vent_marker",
        origin=(UC, GLASS_V + 0.005, FLOOR + GLASS_H[0]))
    parts += lights(pid, s, body_dir)
    # the blades: seven copies of the one blade, leaves with their origin on the pivot (the caps' axis), shut

    u0, u1 = CAP_U[0] + 0.012, CAP_U[1] - 0.012
    for k in range(SLATS):
        hinge = ((u0 + u1) / 2, pivot_v, FLOOR + PIVOT_TOP - k * PITCH)
        parts.append({"name": f"{pid}_slat{k + 1}", "glb": str(raw_root() / BLADE_GLB), "mirror_u": s < 0,
                      "offset": (s * hinge[0], hinge[1], hinge[2]), "rot_u": -OPEN_RAD,
                      "origin": (s * hinge[0], hinge[1], hinge[2]),
                      "hull": [(s * x, y, h) for x, y, h in blade_hull(hinge, -OPEN_RAD)]})
    # convex colliders: the box and the column, their backs on the wall
    add("col0-convcolonly", prism(BOX_U[0], BOX_U[1], wall_profile(BOX_FACE, BOX_TOP)), DARK)
    add("col1-convcolonly", prism(COL_U[0], COL_U[1], wall_profile(COL_FACE, COL_TOP)), DARK)
    # vents-b4: the whole vent RECESS into the wall (the parts, the body's and blades' offsets, the leaves' origins)
    r = RECESS_SIDE["w" if s < 0 else "e"]
    for p in parts:
        if "verts" in p:
            p["verts"] = [(x, y - r, h) for x, y, h in p["verts"]]
        for k in ("offset", "origin"):
            if k in p:
                p[k] = (p[k][0], p[k][1] - r, p[k][2])
        if "hull" in p:
            p["hull"] = [(x, y - r, h) for x, y, h in p["hull"]]
    return parts
