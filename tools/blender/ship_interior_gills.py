"""The throat vents rebuilt as the ray's gills (art #263, gills step 1: the form, static, calm; docs/ship.md "Station 1:
the ray's gills"): `station_gills` builds `station_vent_e` and its mirror `station_vent_w`, sunk flush into the
throat's wall. The design track's drawing in cm (prime-game-design ideas/ship-components/vent-wall/drawing/drawing.js,
the engineer's yes 2026-10-27) held every number; since gills step 4 (option A, 2026-10-27: "the concept wins over the
drawing") the concept (c_close.jpg, c_ramp.jpg) wins where they differ: narrower ribs that stand out, wide lit slots.

The piece replaces the free-standing unit (ship_interior_vent.py, vents-b5, kept for the record) and the throat's low
and middle wall modules under its 160 cm band (layouts/ship/interior.toml): it is the band itself, a bronze plate flush
with the wall's face with one window into the well behind it (step 4), COVERS ribs and the fixed fifth arch with the
scanner, the timing bar and the red lamp. Gills step 6: each rib one static piece from 8 cm over the deck up the
leaning wall to CROWN_TOP, one profile (the concept's chunky bow), its back RIB_SINK into the wall.

Frame: the spot at the origin, u along the wall (+ toward the hall; the west piece mirrors u), v out of the wall into
the throat, h absolute (the deck at FLOOR). In Godot (x, h, -v; ship_build's frame): each rib a leaf `<id>_cover<k>`
(k 1..COVERS from the mouth, the old name) with its origin at the foot of its rocking axis (rib_axis: through its
back's middle at its foot and its top); the motion, not built in this static pass, rocks it at most RIB_ROCK_DEG about
that axis. Its children `<id>_lip<k>` (the lit chamfers), `<id>_flank<k>` and `<id>_flank<k>b` (the cyan flank
liners, bright at the front, dim behind) rock with it. The glows keep the old names for vent_glow.gd and ship.gd:
`<id>_heat` (int_halo__vent_heat, the problem) and, 4 mm in front of it, `<id>_cool` (int_cyan__vent_cool, calm) on
the well's back; `<id>_seam<k>` (int_halo__vent_seam) the red in each gap, 2 mm behind the cyan; `<id>_lamp`
(glow_nav_red__vent_lamp).

The well: the drawing's box is 127 x 129 x 45 cm (h 12 to 141) behind the covers. The hull is thinner there (the
belly rises behind the wall's foot, the mouth's open notch behind its mouth end): `well_depth` gives each point of the
box's back the depth that keeps SKIN_M of hull behind it, at most 45 cm, at least WELL_MIN; the back follows it."""

from __future__ import annotations

import math
import os

import ship_hull_shape as H
import ship_interior as S
import ship_interior_geom as G
import ship_lib as L
import ship_interior_vent as V   # its helpers, read at build time (ship_interior imports both modules at its end)

# gills step 8 (the engineer's option A): on the hall's back wall beside the vault's door (ship_interior.GILL_A0), a
# flat chord straight from the deck to the ceiling (S.H_HALL, 3.2 m). The throat's leaning upper wall is gone: IN 0,
# so the old "leaning wall" over BEND is the same vertical face (cv 0) and BEND is only the well's top now
TOP, IN = S.H_HALL, 0.0
BEND = 2.70                          # the well's (and the band plate's window's) top; the plain upper wall over it
HOOD_TOP = S.H_HALL                  # gills step 9: the hood's slope meets the wall at the rim (3.2; step 8 3.14 left a
                                     # 6 cm wall strip over it); ship --check lets this piece reach the rim (to_rim)
UNIT = [-0.80, 0.80, -0.45, 0.42, 0.0, HOOD_TOP]   # the ribs and the column, the well 45 cm behind, the hood


def cv(h: float) -> float:
    """The upper wall's face at h (v): vertical on the hall's chord (the throat's leaning wall, ship_interior_vent.cv,
    until gills step 7)."""
    return 0.0


_GILL_HALF = (90.0 - S.BACK_DEG - S.GILL_A0) / 2
CHORD_HALF = S.HV * math.sin(math.radians(_GILL_HALF))       # 0.819: the gills' chord (1.638 m)
CHORD_APO = S.HV * math.cos(math.radians(_GILL_HALF))        # 3.995

# --- the drawing (cm in drawing.js, metres here) ---------------------------------------------------------------------
BAND = (-0.80, 0.80)                 # the plain band the vent sits on
BAND_PLATE = (-round(CHORD_HALF, 5), round(CHORD_HALF, 5))   # the band as built: the whole chord (gills step 8)
# gills step 6: the rib count and width a variant's (SHIP_GILLS_RIBS, SHIP_GILLS_RIB_W), the pitch filling the band
# from its mouth end to the fifth arch (the drawing's 4 at 31.75 cm)
# gills step 7 (the concept's count): 4 ribs of 22 cm with 12 cm slots, an equal END_GAP at both ends of the rib band
# (the band's mouth end to the fifth arch, narrowed to 28 cm for it), so no rib folds into the casing
COVERS = int(os.environ.get("SHIP_GILLS_RIBS") or 4)
SLOT_W = float(os.environ.get("SHIP_GILLS_SLOT") or 0.12)
DRAWING_COVER_W = 0.30               # the drawing's cover; gills step 4 (option A, the concept wins): narrower ribs
# gills step 4: a rib's built width (SHIP_GILLS_RIB_W, the step's grid), centred in its pitch cell
# gills step 5: 21 cm; step 6's A/B: a) 4 ribs of 22 cm (slot 9.75), b) 3 ribs of 28 cm at a 42.33 cm pitch (slot
# 14.33, 0.51 of the rib); the pick b: from the ramp every slot on both walls shows cyan (a's packed ribs hid the far
# slots) and the ribs read chunky, as the concept's
COVER_W = float(os.environ.get("SHIP_GILLS_RIB_W") or 0.22)
PITCH = round(COVER_W + SLOT_W, 6)
# gills step 6 (the manager's decision, the engineer's "static and pretty wins"): each rib ONE static piece from its
# foot to CROWN_TOP, one profile (no groove, no step, no collar, no width change); its back RIB_SINK into the wall's
# face (into the well's window below the bend, into the leaning wall above it), so no gap shows behind its flanks
COVER_H = (0.05, BEND)               # the well's window's height (the old hinged cover's; the well and seams use it)
RIB_H = (0.05, 2.97)                 # the rib: 5 cm over the deck (1 cm into the sill, step 10) to its top in the hood
RIB_SINK = 0.015
TOP_R = 0.03                         # the rib's top rounded off over its last 3 cm
CROWN_TOP = RIB_H[1]
PROUD = 0.035                        # the rib's crest out of the wall's face at its foot
# gills step 5: the well up to 1 cm under the bend (the drawing's box to 1.41), the lit slots run on up the leaning wall
FIXED = (0.52, 0.80)                 # the fifth arch, fixed (gills step 7: 28 cm, step 6's 33 for the fourth rib)
END_GAP = round((FIXED[0] - BAND[0] - COVERS * COVER_W - (COVERS - 1) * SLOT_W) / 2, 6)
WELL_TOP = 2.82                      # gills step 10: the well's roof behind the hood's lip (2.78..2.86), over the bend
WELL_U, WELL_H, WELL_D = (-0.81, FIXED[0] - 0.01), (0.12, WELL_TOP), 0.45   # the box behind the ribs (132 x 132 x 45)
# gills step 4: one window through the band plate over the well (the drawing's four slits and step 3's grooves are
# gone): every gap between two ribs is a slot into the lit well, the concept's "wide slots with light"
WIN_U, WIN_H = (BAND[0] + 0.006, WELL_U[1]), WELL_H
WELL_MIN = 0.06                      # the well's least depth from the wall's face (the plate 3 cm and 3 cm of light)
SKIN_M = 0.17                        # the hull kept behind the well (the design's 17 cm skin)
PLATE_T = 0.03                       # the band plate's thickness
COLUMN_STRIP_W = 0.010                       # gills step 12: the bronze strip on the column's door side
FIXED_TOP = BEND + 0.006                    # its plate's top, 4 mm under its crown (no groove: it does not turn)
HAND_C, HAND_HW, HAND_HH = 1.20, 0.112, 0.142   # the scanner's bezel: middle 1.20, 22.4 x 28.4
BAR_W, BAR_H, BAR_GREEN = 0.05, (1.36, 1.88), (1.78, 1.84)
LAMP_R, LAMP_H = 0.086, (1.92, 2.02)
# the rib's crest in side view: its horizontal distance x(h) out of the vertical wall's plane, one quintic (C2
# everywhere, no corner at the bend) through the knots below with ARCH_FOOT_SLOPE at the foot and ARCH_TOP_SLOPE at the
# top (the leaning wall's own slope is IN / (TOP - BEND), 0.647). Gills step 6: the fuller lower bow (the concept's
# chunky ")"; step 5 had 7.7 cm at 0.74): 3.5 cm proud at the foot, 12.5 at 0.74, 16.5 at 1.4, its most at the bend,
# CROWN_PROUD at the top; the proud rises to the bend and falls after it, no dip.
# gills step 7: the fuller ")" (about 20 cm at the bend; step 6 16.5 at 1.4, 12.5 at 0.74)
# gills step 8: the ")" on the 2.9 m rib, its fullest 20 cm at PEAK_H (about the middle), back to 4.5 cm at its top
# inside the hood
PEAK_H, PEAK = 1.55, 0.20
LOW_H, LOW = 0.80, 0.155
HIGH_H, HIGH = 2.35, 0.12
CROWN_PROUD = 0.040                  # the rib's top, off the wall inside the hood
ARCH_FOOT_SLOPE, ARCH_TOP_SLOPE = 0.20, -0.14
ARCH_KNOTS = ((RIB_H[0], PROUD), (LOW_H, LOW), (PEAK_H, PEAK), (HIGH_H, HIGH), (CROWN_TOP, CROWN_PROUD))


def _solve(a, b):
    """Gaussian elimination with partial pivoting (the arch's 6 x 6)."""
    n = len(a)
    m = [list(r) + [v] for r, v in zip(a, b)]
    for i in range(n):
        piv = max(range(i, n), key=lambda r: abs(m[r][i]))
        m[i], m[piv] = m[piv], m[i]
        for r in range(n):
            if r != i:
                f = m[r][i] / m[i][i]
                m[r] = [x - f * y for x, y in zip(m[r], m[i])]
    return [m[i][n] / m[i][i] for i in range(n)]


def _arch_coeffs():
    n = len(ARCH_KNOTS) + 2
    val = lambda h: [h ** k for k in range(n)]
    der = lambda h: [k * h ** (k - 1) if k else 0.0 for k in range(n)]
    rows = [val(h) for h, _ in ARCH_KNOTS] + [der(RIB_H[0]), der(CROWN_TOP)]
    return _solve(rows, [x for _, x in ARCH_KNOTS] + [ARCH_FOOT_SLOPE, ARCH_TOP_SLOPE])


ARCH_C = _arch_coeffs()
SETBACK = 0.050                      # gills step 3: convex across its width, the edges 5 cm behind its crest
CH = 0.016                           # the lit chamfer on each edge (gills step 6: 1.4 cm, the rim highlight reads at night)
EDGE_MIN = 0.025                     # an edge's least height out of the wall's face (the back 6 mm, the chamfer)
UNDERCUT = 0.0                       # gills step 6: the flanks square to the wall (step 5's 2 cm undercut showed black wedges)
# gills step 6, the motion (option b, built in, the pass static): each whole rib rocks about its own axis, the straight
# line through its back's middle at its foot and at its top (rib_axis), at most RIB_ROCK_DEG either way: rigid, so it
# never breaks; it moves at most 1.9 cm sideways, its back's edges at most RIB_SINK in or out of the wall's face
# (they sit RIB_SINK into it, so no gap opens). Calm 0; hold -RIB_ROCK_DEG (the slots narrower); exhale +RIB_ROCK_DEG
# with the cyan; the problem 0 with the red (the states read by their light).
RIB_ROCK_DEG = 4.0
# gills step 4: per gap a red seam on the well's back 2 mm behind the cyan (the problem), vent_glow.gd's gap lights
SEAM_W = 0.035

# gills step 2: the stations' shared bronze (godot/console/console.gd's `bronze` on console_metal.gdshader: base
# sRGB (0.774, 0.556, 0.349), worn (1.0, 0.854, 0.665), metallic 0.35, roughness 0.42); ship.gd swaps these three for
# that shader by name (GILL_BRONZE), the GLB keeps the same colours for any other viewer (linear here)
# gills step 5: glossier and a little lighter (the concept's bright rim highlight), the edges a glossy bronze bevel
for _n, (_c, _m, _r) in {"gill_bronze": ((0.64, 0.42, 0.22), 0.70, 0.30),       # gills step 3: darker, ship.gd's
                         "gill_bronze2": ((0.58, 0.38, 0.20), 0.70, 0.32),
                         # gills step 4: the chamfers nearer the bronze (step 3's pale gold read as pasted-on lines)
                         "gill_edge": ((0.74, 0.52, 0.30), 0.85, 0.18),
                         # gills step 4: the ribs' flanks a pale steel that takes the well's cyan (the concept's lit
                         # slot sides); ship.gd leaves it a plain material
                         "gill_flank": ((0.62, 0.66, 0.70), 0.50, 0.50)}.items():
    L.MATERIALS.setdefault(_n, {"base": (*(x ** 2.2 for x in _c), 1.0), "metallic": _m, "roughness": _r})
# gills step 4: the timing bar's glass a teal (step 2's white bloomed near-white), ship.toml's colour
L.MATERIALS.setdefault("glow_white__vent_bar", {**L.MATERIALS["glow_amber"], "base": (0.10, 0.80, 0.70, 1.0),
                                                "emission": (0.10, 0.80, 0.70)})
for _n, (_b, _m, _r) in {   # ship_vent_b.MATS (vents-b3's patinated bronze; linear colours)
        "vent_b_bronze": ((0.085, 0.052, 0.024), 0.78, 0.46), "vent_b_bronze2": ((0.072, 0.047, 0.024), 0.74, 0.52),
        "vent_b_edge": ((0.42, 0.26, 0.11), 0.95, 0.30), "vent_b_dark": ((0.035, 0.03, 0.028), 0.85, 0.42),
        "vent_b_well": ((0.03, 0.05, 0.07), 0.7, 0.38)}.items():
    L.MATERIALS.setdefault(_n, {"base": (*_b, 1.0), "metallic": _m, "roughness": _r})
L.MATERIALS.setdefault("int_halo__vent_seam", {**L.MATERIALS["int_halo"], "base": (1.0, 0.12, 0.0, 1.0),
                                               "emission": (1.0, 0.12, 0.0), "strength": 2.0})

LEAN = math.hypot(IN, TOP - BEND)
LEAN_V, LEAN_H = IN / LEAN, (TOP - BEND) / LEAN          # up the leaning wall
NORM_V, NORM_H = LEAN_H, -LEAN_V                          # its face's normal, out into the throat


def cover_u(i: int) -> float:
    """Rib i's (0..COVERS-1) mouth-side edge: gills step 7, END_GAP from the band's mouth end, then every PITCH."""
    return BAND[0] + END_GAP + i * PITCH


def gap_u() -> list[float]:
    """The gaps' middles (k 0..COVERS from the mouth): the end gap by the band's mouth end, the slots between ribs,
    the end gap by the fifth arch."""
    return ([BAND[0] + END_GAP / 2] + [cover_u(k) - SLOT_W / 2 for k in range(1, COVERS)]
            + [FIXED[0] - END_GAP / 2])


def seam(k: int) -> tuple[float, float]:
    """Seam k's span along the wall (the end ones as wide as their half gap allows)."""
    g = gap_u()[k]
    w = min(SEAM_W, END_GAP - 0.01) if k in (0, COVERS) else SEAM_W
    return max(g - w / 2, WIN_U[0] + 0.002), min(g + w / 2, WIN_U[1] - 0.002)   # inside the window


def _seg_dist(p, a, b) -> float:
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / max(dx * dx + dy * dy, 1e-12)))
    return math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)


def neighbour_gap(h: float | None = None) -> float:
    """The clear distance (m) between ribs 2 and 3's plan sections at h (default the peak): the slot a player sees."""
    h = PEAK_H if h is None else h
    a = rib_section(cover_u(1), cover_u(1) + COVER_W, cover_front(h), wall_back(h))
    b = rib_section(cover_u(2), cover_u(2) + COVER_W, cover_front(h), wall_back(h))
    return min(min(_seg_dist(p, q, r) for q, r in zip(b, b[1:] + b[:1])) for p in a)


def slit_c(i: int) -> float:
    return cover_u(i) + COVER_W / 2


# --- the well's depth against the hull -------------------------------------------------------------------------------
WELL_NU, WELL_NH = 28, 24   # gills step 2: twice step 1's grid (the corner rule below loses less depth)


def _frame(layout: dict, side: str):
    spot = next(s for s in layout["stations"]["spot"] if s["id"] == f"vent_{side}")
    n = spot["normal"]
    ln = math.hypot(*n)
    n = (n[0] / ln, n[1] / ln)
    t = (n[1], -n[0]) if -n[0] > 0 else (-n[1], n[0])   # along the wall, + toward the hall (+y)
    return spot["at"], n, t


def skin_at(layout: dict, side: str, u: float, d: float, h: float) -> float:
    """The hull behind the point d behind the wall's face (u along the wall, h over the deck)."""
    at, n, t = _frame(layout, side)
    p = (at[0] + t[0] * u - n[0] * d, at[1] + t[1] * u - n[1] * d)
    return min(H.skin((*p, S.FLOOR + h)), vault_gap(layout, p))


def vault_gap(layout: dict, p) -> float:
    """gills step 8: the plan distance from p to the vault's clear floor (the closed room behind the hall's back wall,
    beside the gills): the well keeps SKIN_M of wall to it as to the hull."""
    v = next(r for r in layout["rooms"] if r["id"] == "vault")
    dx = max(v["x"][0] - p[0], 0.0, p[0] - v["x"][1])
    dy = max(v["y"][0] - p[1], 0.0, p[1] - v["y"][1])
    return math.hypot(dx, dy)


def room(layout: dict, side: str, u: float, h: float, skin: float = SKIN_M) -> float:
    """The deepest well (<= 1.2 m) behind the face at (u, h) with `skin` of hull behind it; 0 when the face has less."""
    if skin_at(layout, side, u, 0.0, h) < skin:
        return 0.0
    lo, hi = 0.0, 1.2
    if skin_at(layout, side, u, hi, h) >= skin:
        return hi
    for _ in range(18):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if skin_at(layout, side, u, mid, h) >= skin else (lo, mid)
    return lo


def well_depth(layout: dict, side: str) -> dict:
    """The well's back over a WELL_NU x WELL_NH grid: {"u", "h", "d" (rows by h), "full" the share of the drawing's
    box (45 cm) the hull holds, "least_skin" the hull behind the full box, "least_built" behind the built back}."""
    us = [WELL_U[0] + (WELL_U[1] - WELL_U[0]) * i / (WELL_NU - 1) for i in range(WELL_NU)]
    hs = [WELL_H[0] + (WELL_H[1] - WELL_H[0]) * j / (WELL_NH - 1) for j in range(WELL_NH)]
    d, full, least, built = [], 0, 9.0, 9.0
    for h in hs:
        row = []
        for u in us:
            r = room(layout, side, u, h)
            full += r >= WELL_D - 1e-6
            least = min(least, skin_at(layout, side, u, WELL_D, h))
            row.append(round(min(WELL_D, max(WELL_MIN, r)), 4))
            built = min(built, skin_at(layout, side, u, row[-1], h))
        d.append(row)
    return {"u": us, "h": hs, "d": d, "full": full / (WELL_NU * WELL_NH), "least_skin": least, "least_built": built}


def _depth(w: dict, u: float, h: float) -> float:
    """The well's back depth at (u, h): bilinear on the grid, at most its cell's shallowest corner."""
    us, hs = w["u"], w["h"]
    fi = min(max((u - us[0]) / (us[-1] - us[0]) * (len(us) - 1), 0.0), len(us) - 1 - 1e-9)
    fj = min(max((h - hs[0]) / (hs[-1] - hs[0]) * (len(hs) - 1), 0.0), len(hs) - 1 - 1e-9)
    i, j = int(fi), int(fj)
    a, b = fi - i, fj - j
    r0 = w["d"][j][i] * (1 - a) + w["d"][j][i + 1] * a
    r1 = w["d"][j + 1][i] * (1 - a) + w["d"][j + 1][i + 1] * a
    # gills step 2: never deeper than the cell's shallowest corner (bilinear between a 6 and a 40 cm corner passed
    # the 17 cm skin by 1.4 cm, test_ship_gills)
    return min(r0 * (1 - b) + r1 * b, w["d"][j][i], w["d"][j][i + 1], w["d"][j + 1][i], w["d"][j + 1][i + 1])


# --- meshes ----------------------------------------------------------------------------------------------------------
def wall_v(h: float) -> float:
    """The wall's face at h (v): the vertical wall to the bend, the leaning wall over it."""
    return 0.0 if h <= BEND else cv(h)


def wall_back(h: float) -> float:
    """A rib's back at h: RIB_SINK into the wall's face."""
    return wall_v(h) - RIB_SINK


def rib_axis(i: int):
    """Rib i's rocking axis (u, v, h): the line through its back's middle at its foot and at its top."""
    uc = cover_u(i) + COVER_W / 2
    return (uc, wall_back(RIB_H[0]), RIB_H[0]), (uc, wall_back(RIB_H[1]), RIB_H[1])


def rock(p, i: int, deg: float):
    """(u, v, h) turned deg about rib i's axis (Rodrigues)."""
    (a0, a1) = rib_axis(i)
    k = [a1[j] - a0[j] for j in range(3)]
    ln = math.sqrt(sum(x * x for x in k))
    k = [x / ln for x in k]
    x = [p[j] - a0[j] for j in range(3)]
    c, s_ = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    kx = [k[1] * x[2] - k[2] * x[1], k[2] * x[0] - k[0] * x[2], k[0] * x[1] - k[1] * x[0]]
    kd = sum(k[j] * x[j] for j in range(3))
    return tuple(a0[j] + x[j] * c + kx[j] * s_ + k[j] * kd * (1 - c) for j in range(3))


def plate_section(u0: float, u1: float, front, back: float = 0.006, ch: float = 0.006, n: int = 9):
    """A curved plate's plan section from u0 to u1 (counter-clockwise from +h): its back flat at v = back, its front
    front(q) (q -1 at u0 .. 1 at u1), both front corners chamfered."""
    pts = [(u0 + 0.003, back), (u1 - 0.003, back), (u1, back + 0.004), (u1, front(1.0) - ch)]
    for k in range(n):
        q = 1.0 - 2.0 * k / (n - 1)
        u = (u0 + u1) / 2 + q * ((u1 - u0) / 2 - ch)
        pts.append((u, front(q)))
    pts += [(u0, front(-1.0) - ch), (u0, back + 0.004)]
    return pts


def arch(h: float) -> tuple[float, float]:
    """The rib's crest at h in side view (the quartic ARCH_C): its distance out of the vertical wall's plane and its
    slope."""
    h = min(max(h, COVER_H[0]), CROWN_TOP)
    return (sum(c * h ** k for k, c in enumerate(ARCH_C)),
            sum(k * c * h ** (k - 1) for k, c in enumerate(ARCH_C) if k))


BEND_PROUD = arch(COVER_H[1])[0]     # the cover's top (18 cm)


def rib_proud(h: float) -> float:
    """The rib's crest out of the wall's face at h (horizontally; over the bend the leaning wall's face is cv(h))."""
    return arch(h)[0] - cv(h)


def cover_front(h: float) -> float:
    """A shut cover's crest out of the wall's face at h: PROUD at its foot, PEAK at PEAK_H, BEND_PROUD at its top."""
    return arch(h)[0]


def edge_front(f: float, back: float = 0.006) -> float:
    """A rib's edge height for the crest f: SETBACK behind it, at least EDGE_MIN (over the back and its chamfer)."""
    return max(f - SETBACK, back + EDGE_MIN - 0.006)


def rib_section(u0: float, u1: float, f: float, back: float = 0.006, n: int = 13, e: float | None = None,
                ch: float = CH):
    """gills step 3: a rib's plan section (counter-clockwise from +h), convex across its width: its back flat at v =
    back, its two sides straight up to the edges at edge_front(f), each edge chamfered CH (the lit chamfers), the
    front a parabolic arc from the edges up to the crest f in the middle; the flanks lean in UNDERCUT to the back (the
    lit groove under each edge shows past it)."""
    e = edge_front(f, back) if e is None else e
    a0, a1 = u0 + ch, u1 - ch
    uc = min(UNDERCUT, max(e - ch - back - 0.004, 0.0))   # no more in than the flank is tall (45 deg at most)
    pts = [(u0 + uc + 0.003, back), (u1 - uc - 0.003, back), (u1 - uc, back + 0.004), (u1, e - ch)]
    for k in range(n):
        q = 1.0 - 2.0 * k / (n - 1)
        pts.append(((a0 + a1) / 2 + q * (a1 - a0) / 2, e + (f - e) * (1.0 - q * q)))
    return pts + [(u0, e - ch), (u0 + uc, back + 0.004)]


# gills step 6: the rib's rows up its one profile (the bend among them, so the back's kink is exact), then its top
# rounded off over TOP_R
RIB_HS = sorted({round(RIB_H[0] + (BEND - RIB_H[0]) * k / 45, 6) for k in range(46)} |   # gills step 8: 45 rows (2.6 m)
                {round(BEND + (RIB_H[1] - TOP_R - BEND) * k / 20, 6) for k in range(21)})
TOP_A = (25.0, 50.0, 70.0, 84.0)     # the rounded top's rows (deg round its quarter circle)


def rib_rows(u0: float, u1: float):
    """A rib's rows up its height: (h, its plan section, back, crest, edge); the last TOP_A rows its rounded top."""
    rows = []
    for h in RIB_HS:
        b, f = wall_back(h), cover_front(h)
        rows.append((h, rib_section(u0, u1, f, b), b, f, edge_front(f, b)))
    h0 = RIB_HS[-1]
    for a in TOP_A:
        c = math.cos(math.radians(a))
        h = h0 + TOP_R * math.sin(math.radians(a))
        b, f = wall_back(h), cover_front(h)
        e = edge_front(f, b)
        r = 0.02 * (1.0 - c)
        rows.append((h, rib_section(u0 + r, u1 - r, b + (f - b) * c, b, e=b + (e - b) * c, ch=CH * c), b, f, e))
    return rows


def _place(i: int, deg: float):
    return (lambda u, v, h: (u, v, h)) if not deg else (lambda u, v, h: rock((u, v, h), i, deg))


def cover_mesh(i: int, deg: float = 0.0):
    """Rib i (gills step 6: the whole rib, foot to top, one loft of one profile), rocked deg about its axis."""
    pl = _place(i, deg)
    return V.loft([[pl(u, v, h) for u, v in sec] for h, sec, *_ in rib_rows(cover_u(i), cover_u(i) + COVER_W)])


def chamfer_strips(u0: float, u1: float, rows, ch: float, place):
    """The lit chamfers: a thin bright ribbon 1.2 mm over each front chamfer of a plate's two long edges. rows: (h, the
    edge's height f) up the plate, or (h, f, u0, u1) where the edges move; place(u, v, h) -> the point in the piece's
    frame."""
    o = 0.0012 / math.sqrt(2)
    out = []
    for side in (0, 1):
        loops = []
        for row in rows:
            h, f = row[0], row[1]
            e = (row[2] if len(row) > 2 else u0) if side == 0 else (row[3] if len(row) > 2 else u1)
            du = 1.0 if side == 0 else -1.0
            a, b = (e - du * o, f - ch + o), (e + du * (ch - o), f + o)          # on the chamfer, o out along its normal
            c, d = (b[0] + du * 0.0008, b[1] - 0.0008), (a[0] + du * 0.0008, a[1] - 0.0008)   # 1.1 mm back into it
            loops.append([place(*q, h) for q in ((a, b, c, d) if du > 0 else (b, a, d, c))])
        out.append(V.loft(loops))
    return L.merge(*out)


def lip_mesh(i: int, deg: float = 0.0):
    """Rib i's two lit chamfers up its height (not over the rounded top), rocked with it (a child of the rib)."""
    u0, u1 = cover_u(i), cover_u(i) + COVER_W
    return chamfer_strips(u0, u1, [(h, e) for h, sec, b, f, e in rib_rows(u0, u1)[:len(RIB_HS)]], CH, _place(i, deg))


def upper_mesh():
    """The leaning wall over the band (the upper modules it replaces): its 20 cm body and, under the crowns, a dark
    panel 2 mm proud of its face from the bend to 2.10."""
    # gills step 10: the wall's body round the well's window, which runs on over the bend to WELL_TOP (the wall is
    # upright on the chord: IN 0)
    wt = max(BEND, WELL_TOP)
    body = L.merge(L.box(BAND_PLATE[0], WIN_U[0], -0.2, 0.0, BEND, TOP), L.box(WIN_U[1], BAND_PLATE[1], -0.2, 0.0, BEND, TOP),
                   L.box(WIN_U[0], WIN_U[1], -0.2, 0.0, wt, TOP))
    # gills step 5: the dark panel's top corners rounded (R 12 cm) and its edges a soft 1.5 cm slope from the wall's
    # face up to its 2 mm (step 4's hard straight rectangle)
    top, rad, soft = HOOD_TOP - 0.06, 0.12, 0.015
    u0, u1 = BAND[0] - 0.005, BAND[1] + 0.005
    outline = [(u0, wt), (u1, wt)]
    for cu, a0 in ((u1 - rad, 0), (u0 + rad, 90)):
        outline += [(cu + rad * math.cos(math.radians(a0 + d)), top - rad + rad * math.sin(math.radians(a0 + d)))
                    for d in range(0, 91, 10)]
    inner = [(u, h) for u, h in V.shrink(outline, soft)]
    inner = [(u, max(h, wt)) for u, h in inner]
    n = len(outline)
    lift = lambda u, h, w: (u, cv(h) + w * NORM_V, h + w * NORM_H)
    verts = [lift(u, h, 0.0004) for u, h in outline] + [lift(u, h, 0.002) for u, h in inner]
    faces = [(j, (j + 1) % n, n + (j + 1) % n, n + j) for j in range(n)] + [tuple(range(n, 2 * n))]
    return body, (verts, faces)


def fixed_mesh():
    """The fifth arch's plate: flat-faced, 3 cm proud, chamfered."""
    sec = plate_section(FIXED[0], FIXED[1], lambda q: PROUD, ch=CH)
    return V.loft([[(u, v, h) for u, v in sec] for h in (COVER_H[0], FIXED_TOP)])


# gills step 6: the flank's front half bright, its back dim; gills step 7: the back part runs 2 cm under the front one
# (0.2 mm lower), so no dashed seam shows where they meet
FLANK_PARTS = {"": (0.50, 0.94), "b": (0.06, 0.53)}
FLANK_OFF = {"": 0.001, "b": 0.0008}


def flank_strips(u0: float, u1: float, hs, place, t: tuple[float, float] = (0.08, 0.92), off: float = 0.001):
    """A cyan liner 1 mm off each of a rib's two flanks (from 4 mm over its back to just under the edge's chamfer),
    the part t (0 the back, 1 the edge) of it, up the rows hs (h, crest f, back); place(u, v, h) -> the piece's frame.
    Gills step 6: two parts per flank (FLANK_PARTS), the front one brighter: the slot's glow brightest at its edges."""
    out = []
    for side in (0, 1):
        loops = []
        for row in hs:
            h, f, back = row[:3]
            e = edge_front(f, back)
            uc = min(UNDERCUT, max(e - CH - back - 0.004, 0.0))
            if side == 0:   # the mouth-side flank: from (u0 + uc, back + .004) up to (u0, e - CH)
                a, b, du = (u0 + uc, back + 0.004), (u0, e - CH), -1.0
            else:
                a, b, du = (u1 - uc, back + 0.004), (u1, e - CH), 1.0
            tx, ty = b[0] - a[0], b[1] - a[1]
            ln = max(math.hypot(tx, ty), 1e-6)
            nx, ny = ty / ln, -tx / ln   # the flank's outward normal (away from the rib, du's way)
            if nx * du < 0:
                nx, ny = -nx, -ny
            p0 = (a[0] + tx * t[0] + nx * off, a[1] + ty * t[0] + ny * off)
            p1 = (a[0] + tx * t[1] + nx * off, a[1] + ty * t[1] + ny * off)
            q0, q1 = (p0[0] - nx * 0.0008, p0[1] - ny * 0.0008), (p1[0] - nx * 0.0008, p1[1] - ny * 0.0008)
            loop = [p0, p1, q1, q0] if side == 1 else [p1, p0, q0, q1]
            loops.append([place(u, v, h) for u, v in loop])
        out.append(V.loft(loops))
    return L.merge(*out)


def flank_mesh(i: int, deg: float = 0.0, part: str = ""):
    """Rib i's flank liners' part ("" the bright front, "b" the dim back), rocked with it (a child of the rib)."""
    u0, u1 = cover_u(i), cover_u(i) + COVER_W
    return flank_strips(u0, u1, [(h, f, b) for h, sec, b, f, e in rib_rows(u0, u1)[:len(RIB_HS)]], _place(i, deg),
                        FLANK_PARTS[part], FLANK_OFF[part])


CROWN_IN = (0.02, 0.04)              # gills step 7: the crown's insets at its foot and top (the drawing's 3 and 6 cm)


def crown_mesh(u0: float, u1: float):
    """A fixed crown over an arch: from the bend to CROWN_TOP along the leaning wall, 3.5 cm proud of it (3 mm clear of
    the upper wall's panels), CROWN_IN in from the arch's edges at its foot, narrowing to its top."""
    loops = []
    for k in range(5):
        h = BEND + (CROWN_TOP - BEND) * k / 4
        a = CROWN_IN[0] + (CROWN_IN[1] - CROWN_IN[0]) * k / 4
        w0 = cv(h)
        sec = plate_section(u0 + a, u1 - a, lambda q: 0.035 + 0.004 * (1 - q * q), back=-0.01, ch=0.007, n=5)
        loops.append([(u, w0 + v, h) for u, v in sec])
    return V.loft(loops)


def crown_strips(u0: float, u1: float):
    """A crown's two lit chamfers, on crown_mesh's edges (its 3..6 cm insets) up the leaning wall."""
    out = []
    for k in range(4):
        hs = [BEND + (CROWN_TOP - BEND) * (k + j) / 4 for j in (0, 1)]
        a = [CROWN_IN[0] + (CROWN_IN[1] - CROWN_IN[0]) * (k + j) / 4 for j in (0, 1)]
        # each quarter its own straight run (the insets narrow linearly), lofted between its two ends
        for e, du in ((0, 1.0), (1, -1.0)):
            loops = []
            for h, ai in zip(hs, a):
                eu = (u0 + ai) if e == 0 else (u1 - ai)
                o, f, ch = 0.0012 / math.sqrt(2), 0.035, 0.007
                pa, pb = (eu - du * o, f - ch + o), (eu + du * (ch - o), f + o)
                pc, pd = (pb[0] + du * 0.0008, pb[1] - 0.0008), (pa[0] + du * 0.0008, pa[1] - 0.0008)
                w0 = cv(h)
                loops.append([(q[0], w0 + q[1], h) for q in ((pa, pb, pc, pd) if du > 0 else (pb, pa, pd, pc))])
            out.append(V.loft(loops))
    return L.merge(*out)


def octagon(cu: float, ch: float, hw: float, hh: float, cut: float):
    return [(cu - hw + cut, ch - hh), (cu + hw - cut, ch - hh), (cu + hw, ch - hh + cut), (cu + hw, ch + hh - cut),
            (cu + hw - cut, ch + hh), (cu - hw + cut, ch + hh), (cu - hw, ch + hh - cut), (cu - hw, ch - hh + cut)]


def ring(outer, inner, v0: float, v1: float, bev: float):
    """A bezel: the ring between two (u, h) polygons from v0 out to v1, both of its front edges chamfered."""
    loops = [[(u, v0, h) for u, h in outer], [(u, v1 - bev, h) for u, h in outer],
             [(u, v1, h) for u, h in V.shrink(outer, bev)], [(u, v1, h) for u, h in V.shrink(inner, -bev)],
             [(u, v1 - bev, h) for u, h in inner], [(u, v0, h) for u, h in inner]]
    n = len(outer)
    verts = [p for lp in loops for p in lp]
    faces = [(k * n + j, k * n + (j + 1) % n, (k + 1) * n + (j + 1) % n, (k + 1) * n + j)
             for k in range(len(loops) - 1) for j in range(n)]
    return verts, faces


def flat(poly, v: float, dv: float = 0.0012):
    """A thin plate on the (u, h) polygon at v."""
    n = len(poly)
    verts = [(u, v + d, h) for d in (0.0, dv) for u, h in poly]
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))] + [(j, (j + 1) % n, n + (j + 1) % n, n + j)
                                                                     for j in range(n)]
    return verts, faces


def on_crown(u: float, h: float, w: float):
    """A point on the fixed arch's crown face at height h (on the leaning wall), w out of the crown's face."""
    return (u, cv(h) + 0.039 + w * NORM_V, h + w * NORM_H)


# gills step 5: the well's back a flat deep cyan (the concept's), brightest at the foot and fading up in bands, each its
# own material (int_cyan__vent_cool at the foot, then cool2..cool5; the slots up the leaning wall cool6, cool7); step 4's
# honeycomb (pale, busy, torn into long diagonals where the well's depth jumps) is gone
GLOW_C = (0.05, 0.55, 1.0)
# gills step 6: the well's back much darker (step 5's 0.30..0.10 read as a flat light-blue plate), the glow on the ribs'
# flanks instead, brightest at their front edges (FLANK_E) and dim behind (FLANK2_E): a dark slot with bright cyan edges
# gills step 7: the slots full of cyan again (the concept's glowing slots; step 6's read dark navy with thin edge
# lines): 0.40 from 40 cm fading up to 0.22 at the bend, the lower pocket darker (0.25) for depth
# gills step 8: the bands spread over the taller well (to BEND, 2.70), the slots lit on up the wall into the hood
# gills step 10: one smooth gradient (step 9's five bands stepped and read near-black at the foot and the top): GLOW_N
# thin bands, each at glow_e of its middle: 0.70 of the peak at the foot, the peak at GLOW_PEAK_H, easing down to 0.64
# under the roof; the peak 30 % over step 9's 0.36 (the gills read from the throat and the ramp). The well's floor,
# roof and ends are lit with the band at their height (no dark wall shows anywhere)
GLOW_PEAK, GLOW_PEAK_H, GLOW_FOOT, GLOW_TOP, GLOW_N = 0.47, 1.0, 0.70, 0.64, 24


def glow_e(h: float) -> float:
    """The well's back glow (emission share) at h: a smoothstep up from the foot to the peak, a cosine down to the roof."""
    if h <= GLOW_PEAK_H:
        t = min(max((h - WELL_H[0]) / (GLOW_PEAK_H - WELL_H[0]), 0.0), 1.0)
        return GLOW_PEAK * (GLOW_FOOT + (1.0 - GLOW_FOOT) * t * t * (3 - 2 * t))
    t = min(max((h - GLOW_PEAK_H) / (WELL_H[1] - GLOW_PEAK_H), 0.0), 1.0)
    return GLOW_PEAK * (GLOW_TOP + (1.0 - GLOW_TOP) * (0.5 + 0.5 * math.cos(math.pi * t)))


_GH = [WELL_H[0] + (WELL_H[1] - WELL_H[0]) * k / GLOW_N for k in range(GLOW_N + 1)]
COOL_BANDS = tuple((round(a, 6), round(b, 6), "" if k == 0 else str(k + 1), round(glow_e((a + b) / 2), 4))
                   for k, (a, b) in enumerate(zip(_GH, _GH[1:])))
SLOT_TOP = 2.95                      # the lit slots run on up the wall between the ribs to here (inside the hood)
SLOT_BANDS = ((WELL_TOP - 0.002, 2.885, "6", round(GLOW_PEAK * 0.58, 4)),
              (2.885, SLOT_TOP, "7", round(GLOW_PEAK * 0.45, 4)))   # parts slots6, slots7 (materials vent_slot6, 7)
FLANK_E, FLANK2_E = 0.585, 0.156   # gills step 10: +30 % (0.45, 0.12)
# gills step 7: a cyan strip on the deck at each slot's foot (the concept's), its edge faded in three nested steps
# FLOOR_STEPS: (material suffix, emission, inset from the slot's flanks, depth out from the sill's front)
# gills step 10: a soft light spill, not hard decals: the core the slot's full 12 cm, the outer steps 5 and 2.5 cm wider
# each side (onto the ribs' feet), dimmer and longer (step 9: 8.4 cm cores at 0.45)
FLOOR_STEPS = (("floor3", 0.05, -0.05, 0.24), ("floor2", 0.13, -0.025, 0.16), ("floor", 0.30, 0.0, 0.09))
for _sfx, _e in ([("cool" + b[2], b[3]) for b in COOL_BANDS] + [("slot" + b[2], b[3]) for b in SLOT_BANDS]
                 + [("flank", FLANK_E), ("flank2", FLANK2_E)] + [(f[0], f[1]) for f in FLOOR_STEPS]):
    _n = "int_cyan__vent_" + _sfx
    L.MATERIALS[_n] = {**L.MATERIALS["int_cyan"], "base": (*GLOW_C, 1.0), "emission": GLOW_C,   # the root: import order
                       "strength": 4.0 * _e}


def well_meshes(w: dict):
    """The well behind the plate: its walls, the back's cool bands (foot to top) and the heat 4 mm behind them."""
    us = [WELL_U[0] + (WELL_U[1] - WELL_U[0]) * i / 20 for i in range(21)]
    hs = [WELL_H[0] + (WELL_H[1] - WELL_H[0]) * j / 20 for j in range(21)]

    def field(off: float, h0: float = WELL_H[0], h1: float = WELL_H[1], n_h: int = 20):
        rows = [h0 + (h1 - h0) * j / n_h for j in range(n_h + 1)]
        verts = [(u, -_depth(w, u, h) + off, h) for h in rows for u in us]
        n = len(us)
        faces = [(j * n + i, j * n + i + 1, (j + 1) * n + i + 1, (j + 1) * n + i)
                 for j in range(len(rows) - 1) for i in range(n - 1)]
        return verts, faces
    walls = []
    edges = ([(u, WELL_H[0]) for u in us], [(u, WELL_H[1]) for u in us][::-1],
             [(WELL_U[0], h) for h in hs][::-1], [(WELL_U[1], h) for h in hs])
    for e in edges:
        for (ua, ha), (ub, hb) in zip(e, e[1:]):
            walls.append(([(ua, -PLATE_T + 0.001, ha), (ub, -PLATE_T + 0.001, hb), (ub, -_depth(w, ub, hb) - 0.006, hb),
                           (ua, -_depth(w, ua, ha) - 0.006, ha)], [(0, 1, 2, 3)]))
    # gills step 10: the well's floor, roof and ends lit (step 9's dark floor and roof read as black bands from above
    # and below): a glow wall `inset` inside each dark one, from behind the plate's face to the back; the cool's with
    # the band at its height, the heat's (1.5 mm inside) merged into the heat
    def lit_walls(inset: float, back: float, h0: float, h1: float, foot: bool, roof: bool):
        u0, u1 = WELL_U[0] + inset, WELL_U[1] - inset
        a, b = max(h0, WELL_H[0] + inset), min(h1, WELL_H[1] - inset)
        n = max(1, round((b - a) / 0.065))
        hs_ = [a + (b - a) * j / n for j in range(n + 1)]
        us_ = [u0 + (u1 - u0) * i / 20 for i in range(21)]
        es = [[(u0, h) for h in hs_][::-1], [(u1, h) for h in hs_]]
        if foot:
            es.append([(u, a) for u in us_])
        if roof:
            es.append([(u, b) for u in us_][::-1])
        out = []
        for e in es:
            for (ua, ha), (ub, hb) in zip(e, e[1:]):
                out.append(([(ua, -0.002, ha), (ub, -0.002, hb), (ub, -_depth(w, ub, hb) + back, hb),
                             (ua, -_depth(w, ua, ha) + back, ha)], [(0, 1, 2, 3)]))
        return L.merge(*out)
    last = len(COOL_BANDS) - 1
    bands = [(sfx, L.merge(field(0.0, h0, h1, max(2, round((h1 - h0) / 0.065))),
                           lit_walls(0.003, 0.0, h0, h1, k == 0, k == last)))
             for k, (h0, h1, sfx, _) in enumerate(COOL_BANDS)]
    heat = L.merge(field(-0.004), lit_walls(0.0015, -0.004, WELL_H[0], WELL_H[1], True, True))
    return L.merge(*walls), bands, heat


def slot_span(k: int, h: float) -> tuple[float, float]:
    """Slot k's (0..COVERS from the mouth) span along the wall on the leaning wall at h: from the rib on its mouth side
    (the band's mouth end for k 0) to the one on its hall side (the fifth arch's crown for the last), 4 mm under each
    rib (their backs sit RIB_SINK into the wall)."""
    lo = BAND[0] + 0.006 if k == 0 else cover_u(k - 1) + COVER_W - 0.004
    t5 = min(max((h - BEND) / (CROWN_TOP - BEND), 0.0), 1.0)
    hi = FIXED[0] + CROWN_IN[0] + (CROWN_IN[1] - CROWN_IN[0]) * t5 + 0.004 if k == COVERS else cover_u(k) + 0.004
    return lo, hi


def slot_strips(h0: float, h1: float, w_off: float):
    """The lit slots between the crowns from h0 to h1, w_off out of the leaning wall's face (one mesh, five strips);
    a row under the bend lies on the band plate's top strip."""
    out = []
    n = max(2, round((h1 - h0) / 0.04))
    for k in range(COVERS + 1):
        loops = []
        for j in range(n + 1):
            h = h0 + (h1 - h0) * j / n
            v = (0.0 if h < BEND else cv(h)) + w_off
            lo, hi = slot_span(k, max(h, BEND))
            loops.append([(lo, v, h), (hi, v, h), (hi, v - 0.0008, h), (lo, v - 0.0008, h)])
        out.append(V.loft(loops))
    return L.merge(*out)


def plate_meshes():
    """The band plate flush with the wall: dark, 3 cm thick round one window over the well (step 4: the drawing's slits
    and step 3's grooves gone, every gap a slot into the lit well); behind it outside the well the wall's 20 cm body
    (the low and middle modules it replaces)."""
    v0 = -PLATE_T
    boxes = [L.box(BAND_PLATE[0], WIN_U[0], v0, 0.0, S.FLOOR, S.FLOOR + BEND),
             L.box(WIN_U[1], BAND_PLATE[1], v0, 0.0, S.FLOOR, S.FLOOR + BEND),
             L.box(WIN_U[0], WIN_U[1], v0, 0.0, S.FLOOR, S.FLOOR + WIN_H[0])]
    if WIN_H[1] < BEND:
        boxes.append(L.box(WIN_U[0], WIN_U[1], v0, 0.0, S.FLOOR + WIN_H[1], S.FLOOR + BEND))
    body = [L.box(WELL_U[1], BAND_PLATE[1], -0.2, v0, S.FLOOR, S.FLOOR + BEND),
            L.box(BAND_PLATE[0], WELL_U[1], -0.2, v0, S.FLOOR, S.FLOOR + WELL_H[0])]
    if WELL_H[1] < BEND:
        body.append(L.box(BAND_PLATE[0], WELL_U[1], -0.2, v0, S.FLOOR + WELL_H[1], S.FLOOR + BEND))
    return L.merge(*boxes), L.merge(*body)


def seam_mesh(w: dict, k: int, off: float = -0.002):
    """Seam k (0..4) on the well's back, off behind the cyan (the problem's red in each gap), its window's height."""
    a, b = seam(k)
    us = [a, (a + b) / 2, b]
    hs = [WIN_H[0] + 0.01 + (WIN_H[1] - WIN_H[0] - 0.02) * j / 12 for j in range(13)]
    verts = [(u, -_depth(w, u, h) + off, h) for h in hs for u in us]
    faces = [(j * 3 + i, j * 3 + i + 1, (j + 1) * 3 + i + 1, (j + 1) * 3 + i) for j in range(12) for i in range(2)]
    return verts, faces


# gills step 7: the arched bronze hood over the slots (the concept's; step 6's ribs ended bluntly under a flat panel):
# a bronze casing HOOD_P proud of the leaning wall from its lip up to HOOD_TOP, its lip an arch across the rib band
# (HOOD_LO at the band's ends, HOOD_HI in its middle), stepping up over the fifth arch to HOOD_LIP5 (a visor over the
# red lamp); a rounded nose (HOOD_R) with a lit edge; the ribs run on up into it (their tops inside it)
HOOD_P, HOOD_R = 0.075, 0.03
HOOD_LO, HOOD_HI = 2.78, 2.86        # gills step 8: the lip's arch on the 3.2 m wall (step 7: 1.80, 1.90)
HOOD_LIP5 = HOOD_LO                  # gills step 8: no visor step over the column (its lamp is at 2 m, far under it)
HOOD_U = (BAND_PLATE[0], BAND_PLATE[1])
HOOD_FACE = 0.16                     # the face's full proud over this much above the nose, then it slopes back to the wall
HOOD_END = 0.04                      # the hood's proud tapers to HOOD_END_F of itself over its last 4 cm at either end
HOOD_END_F = 0.15
HOOD_APEX = (BAND[0] + FIXED[0]) / 2   # gills step 10: the lip one smooth arc, its apex over the rib band's middle
HOOD_GROOVE = (0.02, 0.006)          # gills step 10: a 2 cm shadow line 6 mm deep across the face's middle


def hood_lip(u: float) -> float:
    """The hood's lip height at u: one smooth arc (gills step 10; step 9's arch fell steeply into a step at the
    column): two half parabolas meeting level at HOOD_APEX (HOOD_HI), HOOD_LO at the hood's two ends."""
    half = (HOOD_APEX - HOOD_U[0]) if u <= HOOD_APEX else (HOOD_U[1] - HOOD_APEX)
    x = min(abs(u - HOOD_APEX) / half, 1.0)
    return HOOD_LO + (HOOD_HI - HOOD_LO) * (1.0 - x * x)


def on_lean(h: float, n: float):
    """(v, h) of the point n out of the leaning wall's face at height h (on the face)."""
    return cv(h) + n * NORM_V, h + n * NORM_H


def hood_scale(u: float) -> float:
    """The hood's proud at u as a share of HOOD_P: 1 inside, a smoothstep down to HOOD_END_F at its two ends (the
    hood dies into the casing, no box end)."""
    d = min(u - HOOD_U[0], HOOD_U[1] - u) / HOOD_END
    a = min(max(d, 0.0), 1.0)
    return HOOD_END_F + (1.0 - HOOD_END_F) * a * a * (3 - 2 * a)


def hood_us():
    us = [HOOD_U[0] + HOOD_END * k / 6 for k in range(6)]
    us += [HOOD_U[0] + HOOD_END + (HOOD_U[1] - HOOD_U[0] - 2 * HOOD_END) * k / 56 for k in range(57)]
    return us + [HOOD_U[1] - HOOD_END + HOOD_END * k / 6 for k in range(1, 7)]


def hood_profile(u: float, n_arc: int = 7):
    """The hood's section at u, counter-clockwise in (v, h): from its back at the lip round the nose, up its face
    HOOD_FACE, then sloping back into the wall at HOOD_TOP (a visor, not a slab), its back 1 cm in; its proud x
    hood_scale(u)."""
    h0 = hood_lip(u)
    f = hood_scale(u)
    s_top, face = hood_span(h0)
    sn = [(0.0, -0.01)]
    for k in range(n_arc):   # the nose: a quarter round of HOOD_R, from the lip's underside up onto the face
        a = math.radians(-90 + 90 * k / (n_arc - 1))
        sn.append((HOOD_R + HOOD_R * math.sin(a), (HOOD_P - HOOD_R + HOOD_R * math.cos(a)) * f))
    gm, (gw, gd) = HOOD_R + face / 2, HOOD_GROOVE
    sn += [(gm - gw / 2, HOOD_P * f), (gm - gw / 2 + 0.004, (HOOD_P - gd) * f), (gm + gw / 2 - 0.004, (HOOD_P - gd) * f),
           (gm + gw / 2, HOOD_P * f)]
    sn += [(HOOD_R + face, HOOD_P * f), (s_top, 0.004), (s_top, -0.01)]
    return [on_lean(h0 + s * LEAN_H, n) for s, n in sn]


def hood_span(h0: float) -> tuple[float, float]:
    """The hood's length up the leaning wall from its lip at h0 to HOOD_TOP (at least its nose and 6 cm), and its full
    face's length in it (HOOD_FACE, shorter over the fifth arch, where the lip is high: no box over the lamp)."""
    s_top = max((HOOD_TOP - h0) / LEAN_H, HOOD_R + 0.06)
    return s_top, min(HOOD_FACE, s_top - HOOD_R - 0.03)


def hood_front(u: float, h: float) -> float:
    """The hood's face out of the leaning wall (perpendicular) at u and h, from the nose's top up (0 under the nose)."""
    h0 = hood_lip(u)
    s_ = (h - h0) / LEAN_H
    s_top, face = hood_span(h0)
    f = hood_scale(u)
    if s_ < HOOD_R:
        return 0.0
    if s_ <= HOOD_R + face:
        return (HOOD_P - (HOOD_GROOVE[1] if abs(s_ - HOOD_R - face / 2) < HOOD_GROOVE[0] / 2 else 0.0)) * f
    t = min((s_ - HOOD_R - face) / (s_top - HOOD_R - face), 1.0)
    return HOOD_P * f + (0.004 - HOOD_P * f) * t


def hood_mesh():
    return V.loft([[(u, v, h) for v, h in hood_profile(u)] for u in hood_us()])


def hood_edge_mesh(n_arc: int = 7):
    """The lit edge on the hood's nose: a 1 mm ribbon 1 mm over its quarter round."""
    loops = []
    for u in hood_us():
        h0 = hood_lip(u)
        ring = []
        for r in (HOOD_R + 0.0012, HOOD_R + 0.0002):
            pts = []
            for k in range(n_arc):
                a = math.radians(-80 + 70 * k / (n_arc - 1))
                pts.append(on_lean(h0 + (HOOD_R + r * math.sin(a)) * LEAN_H,
                                   (HOOD_P - HOOD_R + r * math.cos(a)) * hood_scale(u)))
            ring += pts if r > HOOD_R + 0.001 else pts[::-1]
        loops.append([(u, v, h) for v, h in ring])
    return V.loft(loops)


# gills step 7: a bronze sill along the band's foot, SILL_P proud, the ribs' and the fifth arch's feet seated on it
# (step 6's stood on a strip 8 cm over the deck with a gap under them)
SILL_P, SILL_H, SILL_CH = 0.05, 0.06, 0.016   # gills step 10: lower (was 8.8 cm), a rounder top edge, the ribs' bronze


def sill_mesh():
    edge = [(SILL_P - SILL_CH + SILL_CH * math.cos(math.radians(a)), SILL_H - SILL_CH + SILL_CH * math.sin(math.radians(a)))
            for a in (0, 22.5, 45, 67.5, 90)]
    prof = [(-0.03, 0.0), (SILL_P - 0.004, 0.0), (SILL_P, 0.004)] + edge + [(-0.03, SILL_H)]
    return V.prism(BAND_PLATE[0], BAND_PLATE[1], prof)


def floor_glow(k: int, step):
    """Slot k's floor strip, the FLOOR_STEPS step: on the deck in front of the sill, across the slot."""
    sfx, _e, inset, depth = step
    lo = BAND[0] if k == 0 else cover_u(k - 1) + COVER_W
    hi = FIXED[0] if k == COVERS else cover_u(k)
    lo, hi = max(lo + inset, BAND_PLATE[0] + 0.01) - inset, min(hi - inset, FIXED[0] + 0.01) + inset
    lift = {"floor3": 0.0012, "floor2": 0.0020, "floor": 0.0028}[sfx]
    return L.box(lo + inset, hi - inset, SILL_P - 0.002, SILL_P + depth, S.FLOOR + lift - 0.0006, S.FLOOR + lift)


def station_gills(args, layout):
    pid, side = args["id"], args.get("side", "e")
    s = -1.0 if side == "w" else 1.0
    parts = []

    def add(name, vf, mat, **extra):
        v, f = vf
        p = L.part(f"{pid}_{name}", [(s * x, y, h) for x, y, h in v], f, mat)
        if "origin" in extra:
            o = extra["origin"]
            extra["origin"] = (s * o[0], o[1], o[2])
        p.update(extra)
        parts.append(p)

    def hh(vf):   # (u, v, h over the deck) -> h absolute
        v, f = vf
        return [(x, y, S.FLOOR + h) for x, y, h in v], f

    plate, body = plate_meshes()
    add("band", plate, "gill_bronze2")   # gills step 6: bronze, the casing (step 5: a black frame)
    add("body", body, "int_silver_b")
    w = well_depth(layout, side)
    walls, bands, heat = well_meshes(w)
    add("well", hh(walls), "vent_b_well")
    # the cool bands: the foot's `cool` (vent_glow.gd's anchor, hidden for the problem) and the rest its children
    for sfx, vf in bands:
        add(f"cool{sfx}", hh(vf), f"int_cyan__vent_cool{sfx}", **({"parent": f"{pid}_cool"} if sfx else {}))
    add("heat", hh(heat), "int_halo__vent_heat")
    upper, dark = upper_mesh()
    add("upper", hh(upper), "int_silver_b")
    # gills step 8: the soffit closing the ceiling's rim behind the chord (ship_interior.flat_panel's)
    back = S.HV - CHORD_APO
    sv = [(u, v, S.FLOOR + h) for h in (TOP, TOP + 0.08) for u, v in ((BAND_PLATE[0], 0.0), (0.0, -back),
                                                                    (BAND_PLATE[1], 0.0))]
    add("soffit", (sv, [(2, 1, 0), (3, 4, 5), (0, 1, 4, 3), (1, 2, 5, 4), (2, 0, 3, 5)]), "int_silver_b")
    add("upper_panel", hh(dark), "gill_bronze2")
    # gills step 5: the slots lit on up the leaning wall between the crowns to SLOT_TOP (the cool's children; the
    # heat's red one 3 mm behind them, the heat's child)
    for h0, h1, sfx, _ in SLOT_BANDS:
        add(f"slots{sfx}", hh(slot_strips(h0, h1, 0.0070)), f"int_cyan__vent_slot{sfx}", parent=f"{pid}_cool")
    add("heat_slots", hh(slot_strips(SLOT_BANDS[0][0], SLOT_TOP, 0.0040)), "int_halo__vent_heat",
        parent=f"{pid}_heat")
    for i in range(COVERS):   # gills step 6: each rib one static piece, its origin at the foot of its rocking axis
        add(f"cover{i + 1}", hh(cover_mesh(i)), "gill_bronze", origin=rib_axis(i)[0][:2] + (S.FLOOR + RIB_H[0],))
        add(f"lip{i + 1}", hh(lip_mesh(i)), "gill_edge", parent=f"{pid}_cover{i + 1}")
        add(f"flank{i + 1}", hh(flank_mesh(i)), "int_cyan__vent_flank", parent=f"{pid}_cover{i + 1}")
        add(f"flank{i + 1}b", hh(flank_mesh(i, part="b")), "int_cyan__vent_flank2", parent=f"{pid}_cover{i + 1}")
    for k in range(COVERS + 1):   # the red seam in each gap on the well's back, behind the cyan (k 1 by the mouth end)
        add(f"seam{k + 1}", hh(seam_mesh(w, k)), "int_halo__vent_seam")
    add("hood", hh(hood_mesh()), "gill_bronze2")
    add("hood_edge", hh(hood_edge_mesh()), "gill_edge")
    add("sill", hh(sill_mesh()), "gill_bronze")
    for k in range(COVERS + 1):   # the floor strips, the cool's children (hidden for the problem)
        for st in FLOOR_STEPS:
            add(f"{st[0]}{k + 1}", floor_glow(k, st), f"int_cyan__vent_{st[0]}", parent=f"{pid}_cool")
    add("fixed", hh(fixed_mesh()), "gill_bronze")
    add("fixed_edge", hh(chamfer_strips(FIXED[0], FIXED[1], [(COVER_H[0], PROUD), (FIXED_TOP, PROUD)], CH,
                                        lambda u, v, h: (u, v, h))), "gill_edge")
    # gills step 12: a 1 cm bronze strip up the column's door side (r9's critic: its side met the band's plain plate
    # with no edge), the glossy edge bronze, 3 mm short of the column's face
    add("column_strip", hh(L.box(FIXED[1], FIXED[1] + COLUMN_STRIP_W, -0.002, PROUD - 0.003, COVER_H[0], FIXED_TOP)),
        "gill_edge")
    add("crown5", hh(crown_mesh(*FIXED)), "gill_bronze2")
    add("crown5_edge", hh(crown_strips(*FIXED)), "gill_edge")
    # the scanner: the bezel ring 1.4 cm proud of the arch, its dark screen 6 mm in, the hand's cyan stroke on it
    fu = (FIXED[0] + FIXED[1]) / 2
    outer = octagon(fu, HAND_C, HAND_HW, HAND_HH, 0.035)
    inner = V.shrink(outer, 0.016)
    add("bezel", hh(ring(outer, inner, PROUD - 0.002, PROUD + 0.014, 0.005)), "gill_edge")
    screen_v = PROUD + 0.008
    add("screen", hh(flat(V.shrink(inner, -0.002), screen_v - 0.0012)), "int_dark__vent_screen")
    st = V.hand_stroke(V.hand_outline())
    allp = [q for pair in st for q in pair]
    x0, x1 = min(x for x, _ in allp), max(x for x, _ in allp)
    y0, y1 = min(y for _, y in allp), max(y for _, y in allp)
    pu, ph = [q[0] for q in inner], [q[1] for q in inner]
    su, sh = (min(pu) + max(pu)) / 2, (min(ph) + max(ph)) / 2
    scale = min((max(ph) - min(ph)) * V.HAND_FILL / (y1 - y0), (max(pu) - min(pu)) * 0.90 / (x1 - x0))
    xc, yc = (x0 + x1) / 2, (y0 + y1) / 2
    inner2 = V.shrink(inner, 0.010)
    while scale > 0.01 and not all(V.inside(inner2, (su + (x - xc) * scale, sh + (y - yc) * scale)) for x, y in allp):
        scale *= 0.98
    n = len(st)
    hv = [(su + (q[0] - xc) * scale, screen_v + d, sh + (q[1] - yc) * scale)
          for d in (0.0026, 0.0012) for pair in st for q in pair]
    hf = []
    for k in range(n):
        j = (k + 1) % n
        fo, fi, fo2, fi2 = 2 * k, 2 * k + 1, 2 * j, 2 * j + 1
        bo, bi, bo2, bi2 = fo + 2 * n, fi + 2 * n, fo2 + 2 * n, fi2 + 2 * n
        hf += [(fo, fo2, fi2, fi), (bo, bi, bi2, bo2), (fo, bo, bo2, fo2), (fi, fi2, bi2, bi)]
    add("hand", hh((hv, hf)), "glow_cyan__vent_hand")
    # the timing bar: a dark channel up the arch and over the bend onto its crown, the amber glass, the green band
    def bar(h0, h1, w, out, mat, name):
        segs = []
        for a, b in ((h0, min(h1, BEND)), (max(h0, BEND), h1)):
            if b - a < 1e-4:
                continue
            if b <= BEND + 1e-9:
                segs.append(L.box(fu - w / 2, fu + w / 2, PROUD - 0.002, PROUD + out, a, b))
            else:
                corners = [on_crown(u, hq, ww) for hq in (a, b) for u in (fu - w / 2, fu + w / 2) for ww in (-0.002, out)]
                v = [corners[k] for k in (0, 2, 1, 3, 4, 6, 5, 7)]   # as L.box's order: h, then v, then u
                segs.append((v, [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]))
        add(name, hh(L.merge(*segs)), mat)
    bar(BAR_H[0] - 0.01, BAR_H[1] + 0.01, BAR_W + 0.016, 0.006, "vent_b_dark", "bar_frame")
    bar(BAR_H[0], BAR_GREEN[0] - 0.002, BAR_W, 0.008, "glow_white__vent_bar", "bar")
    bar(BAR_GREEN[0], BAR_GREEN[1], BAR_W, 0.008, "glow_nav_green__vent_band", "bar_green")
    bar(BAR_GREEN[1] + 0.002, BAR_H[1], BAR_W, 0.008, "glow_white__vent_bar", "bar_top")
    # the red lamp on the crown: a bronze collar and a squat dome, 17 cm wide, 10 cm tall seen from the front
    lc = (LAMP_H[0] + LAMP_H[1]) / 2
    ru, rs = LAMP_R, (LAMP_H[1] - LAMP_H[0]) / 2 / LEAN_H

    def dome(r_u, r_s, w0, w1, rings):
        seg, verts, faces = 32, [], []
        for k, (f, w) in enumerate(rings):
            for j in range(seg):
                a = 2 * math.pi * j / seg
                du, ds = r_u * f * math.cos(a), r_s * f * math.sin(a)
                p = on_crown(fu + du, lc + ds * LEAN_H, w0 + (w1 - w0) * w)
                verts.append(p)
        for k in range(len(rings) - 1):
            faces += [(k * seg + j, k * seg + (j + 1) % seg, (k + 1) * seg + (j + 1) % seg, (k + 1) * seg + j)
                      for j in range(seg)]
        faces.append(tuple(range(seg - 1, -1, -1)))
        faces.append(tuple(range((len(rings) - 1) * seg, len(rings) * seg)))
        return verts, faces
    add("lamp_collar", hh(dome(ru, rs, -0.004, 0.012, [(1.0, 0.0), (1.0, 0.8), (0.94, 1.0), (0.80, 1.0)])),
        "gill_edge")
    add("lamp", hh(dome(ru * 0.80, rs * 0.80, 0.010, 0.050,
                        [(1.0, 0.0), (1.0, 0.25)] + [(math.cos(math.radians(d)), 0.25 + 0.75 * math.sin(math.radians(d)))
                                                      for d in (20, 40, 58, 74, 86)])), "glow_nav_red__vent_lamp")
    parts[-1]["smooth_deg"] = 40.0
    for p in parts:
        if p["name"].endswith(tuple(f"_cover{i + 1}" for i in range(COVERS)) + ("_crown5", "_fixed", "_hood")):
            p["smooth_deg"] = 30.0
        if "__vent_cool" in p.get("mat", ""):   # gills step 6: the well's back smooth (step 5's read faceted)
            p["smooth_deg"] = 80.0
    # the collider: the band's wall and the shut covers (a cover's swing stays inside the player's 0.6 m pass)
    # gills step 8: the box 15 cm out over the ribs' bow (their crests 3.5..20 cm), the column's front under it
    add("col0-convcolonly", L.box(BAND_PLATE[0], BAND_PLATE[1], -0.2, 0.15, S.FLOOR, S.FLOOR + BEND), "int_dark")
    add("col1-convcolonly", hh(upper), "int_dark")
    return parts
