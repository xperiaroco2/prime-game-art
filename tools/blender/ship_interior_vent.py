"""The throat vents (art #263 step 2, station 1; docs/ship.md "Station 1: the throat vents"), way A (art#263 comment
6363433518): `station_vent_e` and its mirror `station_vent_w`. The body (the faceted bronze frame round the empty well
with its copper hinge caps, the column with its light bar, palm scanner and red lamp, the feet) is Meshy's
multi-image-to-3D model of the concept's body views (batch 2026-10-23-ship-vent-a-body), cleaned and baked by
ship_vent_a.py into <raw>/BODY; the moving parts are built here: seven thick curved bevelled gill blades on pivots
through the caps and the bar's marker. Plain Python: the harness (ship_build.py) makes the meshes and imports the
body (a part with "glb").

The piece's frame: the spot at the origin, u (plan x) along the wall, v (plan y) out of the wall into the throat,
h absolute (the deck at FLOOR). East: +u runs toward the hall; the west piece mirrors u, so its column is toward the
hall too. In Godot (x, h, v): each blade a leaf `<id>_slat<k>` (k 1..7 from the top) with its origin on its pivot (the
caps' axis, along x): it opens with rotation.x = -OPEN_RAD * t (t 0 closed: the blades hang flat, each tip over the
next blade's back, an orange seam between; t 1 calm, as the concept's front and side views); the marker
`<id>_marker` a leaf with its origin at its rest point, the glass's bottom: position.y = rest + MARK_TRAVEL * t.
The game drives the glows by material: `int_halo__vent_heat` (the heat panel in the well, the problem state;
`<id>_heat`), `int_cyan__vent_cool` (the calm glow 4 mm in front of it: shown calm, hidden for the problem),
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
L.MATERIALS["int_halo__vent_heat"].update(base=(1.0, 0.22, 0.0, 1.0), emission=(1.0, 0.22, 0.0), strength=5.0)
L.MATERIALS["int_cyan__vent_cool"].update(base=(0.0, 0.5, 1.0, 1.0), emission=(0.0, 0.5, 1.0), strength=4.0)
BLADE, DARK = "vent_a_blade", "int_dark"

# --- the body (ship_vent_a.py's clean.json, 2026-10-23) ---------------------------------------------------------------
BODY = "ship/v4/vents-a/body4k_r2/body.glb"  # under the raw folder (step 2: graded, the blue patch gone)
BLADE_TEX = "ship/v4/vents-a/body4k_r2/textures/vent_a_blade_{}.png"   # the blade's maps (ship_vent_a_finish.py)
BOX_U, COL_U = (-0.80, 0.466), (0.466, 0.80)  # the box with its feet, the column
BOX_TOP, BOX_FACE = 1.608, 0.415              # the box's top, the frame's face (v)
COL_TOP, COL_FACE = 1.81, 0.40                # the column's top (the lamp's dome after the 20 cm raise), its face
WELL_V = 0.115                                # the well's back
OPEN_U, OPEN_H = (-0.44, 0.28), (0.30, 1.40)  # the well's opening (between the cap rows)
CAP_U = (-0.48, 0.32)                         # the cap rows' centres
CAP_R = 0.035                                 # a cap's radius
PIVOT_V = 0.33                                # the caps' axis
GLASS_U, GLASS_H = (0.507, 0.547), (0.66, 1.52)   # the light bar's glass after the raise
GLASS_V = 0.405                               # the glass's face

# --- the blades ------------------------------------------------------------------------------------------------------
SLATS, PIVOT_TOP, PITCH = 7, 1.276, 0.15      # the pivots 127.6 .. 37.6 every 15 cm (the comment's numbers)
# step 2 (art#263, vents-a2): a faceted, curved bronze claw as side_left and front_ortho draw it. The calm section about
# the pivot (dv out, dh up), counter-clockwise from the nose's back: a thick rounded root round the caps' axis (9 cm),
# an upper facet up to the ridge, a front facet sweeping out and down to a thin sharp trailing edge 26.5 cm out (19 cm
# past the frame's face), a concave underside back to the root. Flat facets: each corner over SMOOTH_DEG is sharp.
UPPER = [(-0.030, 0.0), (-0.024, 0.028), (0.0, 0.050), (0.09, 0.062), (0.18, 0.030), (0.235, -0.002)]
TIP = [(0.265, -0.030), (0.261, -0.037)]
LOWER = [(0.21, -0.025), (0.14, -0.027), (0.07, -0.036), (0.02, -0.042), (-0.018, -0.030)]
EDGES = (1, 3, 5, 6, 7)                       # the section's corners with a bright worn edge (nose, ridge, tip)
NOSE_R = 0.03                                 # the root's radius round the pivot
SMOOTH_DEG = 18
# along u: (t from -1 to 1, the section's scale about the pivot, its droop): small at the ends (into the caps), the
# middle's trailing edge dropped DROOP (front_ortho's crescent) with a crease at t 0
STATIONS = [(-1.0, 0.32, 0.0), (-0.93, 0.62, 0.0), (-0.8, 0.92, 0.0), (-0.4, 1.0, 0.5), (0.0, 1.0, 1.0),
            (0.4, 1.0, 0.5), (0.8, 0.92, 0.0), (0.93, 0.62, 0.0), (1.0, 0.32, 0.0)]
DROOP = 0.008
# closed: each blade 11 deg further down than calm, the tip over the next blade's ridge with a seam of about 1 cm
# (calm 4.6 cm): front_closed's thin lit seams; flatter plates would cut the next blade
OPEN_RAD = math.radians(11.0)
MARK_H = 0.03                                 # the marker's height; it slides from GLASS_H[0]
MARK_TRAVEL = GLASS_H[1] - GLASS_H[0] - MARK_H
COOL_V = WELL_V + 0.012                       # the cool glow's panel, just in front of the heat's
UC = (GLASS_U[0] + GLASS_U[1]) / 2            # the bar's centre line
UNIT = [-0.80, 0.80, -0.01, 0.60, -0.02, 1.82]   # u0 u1 v0 v1 h0 h1 (the calm blades' tips at v 0.595)


def blade_material() -> None:
    """The blades' material: the body's bronze, graded, with bright worn edges, as maps painted by
    ship_vent_a_finish.py on the blade's UV layout (blade_uvs)."""
    tex = {k: str(raw_root() / BLADE_TEX.format(k)) for k in ("albedo", "rough", "metal")}
    L.MATERIALS[BLADE] = {"base": (0.6, 0.4, 0.24, 1.0), "metallic": 0.8, "roughness": 0.4, "tex": tex}


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


def section(scale: float, droop: float) -> list[tuple[float, float]]:
    """The calm section at one station, counter-clockwise from the nose's back, scaled about the pivot, its outer
    part dropped by droop * DROOP (most at the tip)."""
    pts = [*UPPER, *TIP, *LOWER]
    return [(dv * scale, (dh - droop * DROOP * max(0.0, dv) / TIP[0][0]) * scale) for dv, dh in pts]


def slat_loops(k: int):
    """Blade k's loops (u, v, h) in the closed pose (calm turned down by OPEN_RAD) and its pivot (u, v, h)."""
    hk = FLOOR + PIVOT_TOP - k * PITCH
    u0, u1 = CAP_U[0] + 0.012, CAP_U[1] - 0.012
    loops = []
    for t, sc, droop in STATIONS:
        u = u0 + (t + 1) / 2 * (u1 - u0)
        loops.append([(u, PIVOT_V + dv, hk + dh) for dv, dh in (turn(p, -OPEN_RAD) for p in section(sc, droop))])
    return loops, ((u0 + u1) / 2, PIVOT_V, hk)


def blade_uv_marks() -> tuple[list[float], list[float]]:
    """The texture's layout of a blade (U along it, V round its section): each station's U and each section corner's
    V (the full-scale section's perimeter fraction from the nose's back); the end caps take U < 0.02."""
    pts = [*UPPER, *TIP, *LOWER, UPPER[0]]
    run = [0.0]
    for p, q in zip(pts, pts[1:]):
        run.append(run[-1] + math.dist(p, q))
    return [0.02 + 0.98 * (t + 1) / 2 for t, _, _ in STATIONS], [r / run[-1] for r in run]


def blade_uvs(loops) -> list[list[tuple[float, float]]]:
    """Per face of loft(loops), its corners' UVs (blade_uv_marks; the caps planar in the U < 0.02 strip)."""
    us, vs = blade_uv_marks()
    n = len(loops[0])
    uvs = [[(us[i], vs[j]), (us[i], vs[j + 1]), (us[i + 1], vs[j + 1]), (us[i + 1], vs[j])]
           for i in range(len(loops) - 1) for j in range(n)]
    cap = [(0.01 + 0.03 * dv, 0.5 + 1.2 * dh) for dv, dh in section(1.0, 0.0)]
    uvs.append(list(reversed(cap)))
    uvs.append(cap)
    return uvs


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


def station_vent(args, layout):
    pid, s = args["id"], (-1.0 if args.get("side") == "w" else 1.0)
    parts = []
    blade_material()

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
    # the blades: leaves with their origin on the pivot (the caps' axis)
    for k in range(SLATS):
        loops, hinge = slat_loops(k)
        add(f"slat{k + 1}", loft(loops), BLADE, origin=hinge, smooth_deg=SMOOTH_DEG, uv=blade_uvs(loops))
    # convex colliders: the box and the column, their backs on the wall
    add("col0-convcolonly", prism(BOX_U[0], BOX_U[1], wall_profile(BOX_FACE, BOX_TOP)), DARK)
    add("col1-convcolonly", prism(COL_U[0], COL_U[1], wall_profile(COL_FACE, COL_TOP)), DARK)
    return parts
