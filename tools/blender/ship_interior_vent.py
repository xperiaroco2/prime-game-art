"""The throat vents (art #263 step 2, station 1; docs/ship.md "Station 1: the throat vents"), way A (art#263 comment
6363433518): `station_vent_e` and its mirror `station_vent_w`. The body (the faceted bronze frame round the empty well
with its copper hinge caps, the column with its light bar, palm scanner and red lamp, the feet) is Meshy's
multi-image-to-3D model of the concept's body views (batch 2026-10-23-ship-vent-a-body), cleaned and baked by
ship_vent_a.py into <raw>/BODY; the seven gill blades are copies of one rigid Meshy blade (ship_vent_a_blade.py,
<raw>/BLADE_GLB) on pivots through the caps; the bar's marker, the glows and the colliders are built here. Plain
Python: the harness (ship_build.py) makes the meshes and imports the body and the blades (parts with "glb"; a blade
carries "rot_u", its closed turn, and "hull", its box's corners for the checks).

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
BLADE, DARK = "vent_a_blade", "int_dark"   # the blade GLB's material

# --- the body (ship_vent_a.py's clean.json, 2026-10-23) ---------------------------------------------------------------
BODY = "ship/v4/vents-a/body4k_r4/body.glb"  # under the raw folder (step 3: the box side and back repainted)
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
# step 3 (art#263, vents-a3): one rigid blade from Meshy (batch 2026-10-23-ship-vent-a-body item blade1, from our own
# isolated blade shot), cleaned by ship_vent_a_blade.py into <raw>/BLADE_GLB: about 500 triangles, its origin on the
# pivot, the calm pose; seven copies. Its blade.json (2026-10-23): the calm blade's box about the pivot (du, dv, dh),
# the calm seam straight from the front 4.7 cm (the slices' median), closed 1.9 cm at CLOSED_DEG, the first cut at
# 58 deg; 36.5 deg (a 7.5 mm seam) and 34 dipped the bottom blade's tip below the frame's bottom (vent_motion.gd).
BLADE_GLB = "ship/v4/vents-a/blade_r4/blade.glb"
BLADE_BOX = ((-0.3877, 0.3874), (-0.03, 0.2649), (-0.0966, 0.0303))
NOSE_R = 0.03                                 # the root's back behind the pivot (ship_vent_a_blade.NOSE_R)
BLADE_SEAMS = {"calm": 0.0473, "closed": 0.0187, "first_cut_deg": 58.0}
CLOSED_DEG = 33.0
# closed: each blade CLOSED_DEG further down than calm, a seam of about 1.9 cm straight on (front_closed's lit seams)
OPEN_RAD = math.radians(CLOSED_DEG)
MARK_H = 0.03                                 # the marker's height; it slides from GLASS_H[0]
MARK_TRAVEL = GLASS_H[1] - GLASS_H[0] - MARK_H
COOL_V = WELL_V + 0.012                       # the cool glow's panel, just in front of the heat's
UC = (GLASS_U[0] + GLASS_U[1]) / 2            # the bar's centre line
UNIT = [-0.80, 0.80, -0.01, 0.60, -0.02, 1.82]   # u0 u1 v0 v1 h0 h1 (the calm blades' tips at v 0.595)


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
