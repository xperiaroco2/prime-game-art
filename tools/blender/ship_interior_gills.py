"""The throat vents rebuilt as the ray's gills (art #263, gills step 1: the form, static, calm; docs/ship.md "Station 1:
the ray's gills"): `station_gills` builds `station_vent_e` and its mirror `station_vent_w`, sunk flush into the
throat's wall. The design track's drawing in cm (prime-game-design ideas/ship-components/vent-wall/drawing/drawing.js,
the engineer's yes 2026-10-27) holds every number; GILL below mirrors it.

The piece replaces the free-standing unit (ship_interior_vent.py, vents-b5, kept for the record) and the throat's low
and middle wall modules under its 160 cm band (layouts/ship/interior.toml): it is the band itself, a dark plate flush
with the wall's face with four slits into one well behind it, four hinged gill covers 3 cm proud, the fixed crowns on
the leaning upper wall, the fixed fifth arch with the scanner, the timing bar and the red lamp.

Frame: the spot at the origin, u along the wall (+ toward the hall; the west piece mirrors u), v out of the wall into
the throat, h absolute (the deck at FLOOR). In Godot (x, h, -v; ship_build's frame): each cover a leaf
`<id>_cover<k>` (k 1..4 from the mouth) with its origin on its hinge, a vertical line at the cover's hall-side edge
(u = -80 + 31.75 (k - 1) + 30 cm, v = 1.5 cm): turning it about Godot's y swings its free edge out toward the mouth.
Built in the calm pose (CALM_DEG). The glows keep the old names for vent_glow.gd and ship.gd: `<id>_heat`
(int_halo__vent_heat, the problem) and, 4 mm in front of it, `<id>_cool` (int_cyan__vent_cool, calm) on the well's
back; `<id>_seam<k>` (int_halo__vent_seam) the red behind each seam; `<id>_lamp` (glow_nav_red__vent_lamp).

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

BEND, IN, TOP = S.TH_BEND, S.TH_IN, S.TH_H      # the throat wall: vertical to 1.45, then 0.55 in at 2.3
UNIT = [-0.80, 0.80, -0.45, 0.42, 0.0, 2.06]  # the covers and fixed arch, the well 45 cm behind, the crowns' lamp

# --- the drawing (cm in drawing.js, metres here) ---------------------------------------------------------------------
BAND = (-0.80, 0.80)                 # the plain band the vent sits on
BAND_PLATE = (-0.81012, 0.81012)     # the band as built: the two wall modules it replaces (0.81012 each)
COVERS, PITCH, COVER_W = 4, 0.3175, 0.30
COVER_H = (0.08, 1.446)              # the hinged plate: 8 cm over the deck to the bend (4 mm under the crown)
CROWN_TOP = 2.05
PROUD = 0.03                         # a shut cover's face out of the wall's face (its mean: 2.6 at the edges, the bow)
SLIT_W, SLIT_H = 0.22, (0.15, 1.38)
WELL_U, WELL_H, WELL_D = (-0.81, 0.46), (0.12, 1.41), 0.45   # the box behind the covers (127 x 129 x 45)
WELL_MIN = 0.06                      # the well's least depth from the wall's face (the plate 3 cm and 3 cm of light)
SKIN_M = 0.17                        # the hull kept behind the well (the design's 17 cm skin)
PLATE_T = 0.03                       # the band plate's thickness
FIXED = (0.47, 0.80)                 # the fifth arch, fixed
HAND_C, HAND_HW, HAND_HH = 1.20, 0.112, 0.142   # the scanner's bezel: middle 1.20, 22.4 x 28.4
BAR_W, BAR_H, BAR_GREEN = 0.05, (1.36, 1.88), (1.78, 1.84)
LAMP_R, LAMP_H = 0.086, (1.92, 2.02)
BOW = 0.080                          # gills step 2: a cover's front bows out up its height, PROUD at its foot
TOP_RISE = 0.030                     # gills step 3: its top stands 3 cm more (6 cm), the crown's foot (one rib)
SETBACK = 0.050                      # gills step 3: convex across its width, the edges 5 cm behind its crest
CH = 0.011                           # the lit chamfer on each edge
EDGE_MIN = 0.025                     # an edge's least height out of the wall's face (the back 6 mm, the chamfer)
UNDERCUT = 0.020                     # the flanks lean in: the back 2 cm narrower each side, the grooves show under the edges
HINGE = "hall"                       # the drawing's side: each cover hinged on its hall-side edge ("mouth": the other)
CALM_DEG = 16.0                      # the static pose: the calm breathing's widest (10..16 deg; the concept's open gaps)
# gills step 3: a groove 1.2 cm deep in the band under every rib edge (the gaps' middles and cover 1's mouth edge),
# lit cyan calm (part of `<id>_cool`), its red seam behind the cyan (the problem): the concept's lit slits
GROOVE_W, GROOVE_D, GROOVE_H = 0.055, 0.012, (0.10, 1.43)
OPEN_DEG = 70.0                      # the exhale (step 2)
NEIGHBOUR_DEG = 20.0                 # gills step 3: neighbouring covers clear while within this of each other (22: touch)
HINGE_V = PROUD / 2

# gills step 2: the stations' shared bronze (godot/console/console.gd's `bronze` on console_metal.gdshader: base
# sRGB (0.774, 0.556, 0.349), worn (1.0, 0.854, 0.665), metallic 0.35, roughness 0.42); ship.gd swaps these three for
# that shader by name (GILL_BRONZE), the GLB keeps the same colours for any other viewer (linear here)
for _n, (_c, _m, _r) in {"gill_bronze": ((0.56, 0.35, 0.18), 0.62, 0.33),       # gills step 3: darker, ship.gd's
                         "gill_bronze2": ((0.50, 0.31, 0.16), 0.62, 0.36),
                         "gill_edge": ((1.0, 0.82, 0.56), 0.75, 0.18)}.items():
    L.MATERIALS.setdefault(_n, {"base": (*(x ** 2.2 for x in _c), 1.0), "metallic": _m, "roughness": _r})
L.MATERIALS.setdefault("glow_white__vent_bar", {**L.MATERIALS["glow_amber"], "base": (1.0, 1.0, 1.0, 1.0),
                                                "emission": (0.88, 0.95, 1.0)})
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
    """Cover i's (0..3) mouth-side edge."""
    return BAND[0] + i * PITCH


def hinge_side(args: dict | None = None) -> str:
    """The covers' hinge side: the piece's args, else SHIP_GILLS_HINGE (the step 2 comparison builds), else HINGE."""
    h = (args or {}).get("hinge") or os.environ.get("SHIP_GILLS_HINGE") or HINGE
    if h not in ("hall", "mouth"):
        raise ValueError(f"gills: hinge {h!r}, not 'hall' or 'mouth'")
    return h


def calm_deg(args: dict | None = None) -> float:
    """The built calm angle: the piece's args, else SHIP_GILLS_CALM (the step 3 grid), else CALM_DEG."""
    d = float((args or {}).get("calm") or os.environ.get("SHIP_GILLS_CALM") or CALM_DEG)
    if not 0.0 <= d <= OPEN_DEG:
        raise ValueError(f"gills: calm {d} deg, not in 0..{OPEN_DEG}")
    return d


def groove_u() -> list[float]:
    """The grooves' middles: cover 1's mouth edge's gap, then the gap after each cover (the last by the fifth arch)."""
    gap = PITCH - COVER_W
    return [cover_u(k) - gap / 2 for k in range(COVERS + 1)]


def groove(k: int) -> tuple[float, float]:
    g = groove_u()[k]
    return max(g - GROOVE_W / 2, BAND_PLATE[0]), min(g + GROOVE_W / 2, BAND_PLATE[1])


def hinge_u(i: int, hinge: str = HINGE) -> float:
    """Cover i's hinge line: its hall-side edge (the drawing) or its mouth-side edge."""
    return cover_u(i) + (COVER_W if hinge == "hall" else 0.0)


def swing(hinge: str) -> float:
    """rot()'s sign: the free edge swings out into the throat on either side."""
    return 1.0 if hinge == "hall" else -1.0


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
    return H.skin((at[0] + t[0] * u - n[0] * d, at[1] + t[1] * u - n[1] * d, S.FLOOR + h))


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
def rot(p, hu: float, deg: float):
    """(u, v) turned about the hinge (hu, HINGE_V) by deg (positive: the free edge, at lower u, out into the throat)."""
    a = math.radians(deg)
    x, y = p[0] - hu, p[1] - HINGE_V
    return (hu + x * math.cos(a) + y * math.sin(a), HINGE_V - x * math.sin(a) + y * math.cos(a))


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


def cover_front(h: float) -> float:
    """A shut cover's crest out of the wall's face at h: PROUD at its foot, PROUD + BOW about mid-height, PROUD +
    TOP_RISE at its top (the crown's foot)."""
    t = min(max((h - COVER_H[0]) / (COVER_H[1] - COVER_H[0]), 0.0), 1.0)
    return PROUD + BOW * math.sin(math.pi * t) + TOP_RISE * t ** 3


def edge_front(f: float, back: float = 0.006) -> float:
    """A rib's edge height for the crest f: SETBACK behind it, at least EDGE_MIN (over the back and its chamfer)."""
    return max(f - SETBACK, back + EDGE_MIN - 0.006)


def rib_section(u0: float, u1: float, f: float, back: float = 0.006, n: int = 13, e: float | None = None):
    """gills step 3: a rib's plan section (counter-clockwise from +h), convex across its width: its back flat at v =
    back, its two sides straight up to the edges at edge_front(f), each edge chamfered CH (the lit chamfers), the
    front a parabolic arc from the edges up to the crest f in the middle; the flanks lean in UNDERCUT to the back (the
    lit groove under each edge shows past it)."""
    e = edge_front(f, back) if e is None else e
    a0, a1 = u0 + CH, u1 - CH
    uc = min(UNDERCUT, max(e - CH - back - 0.004, 0.0))   # no more in than the flank is tall (45 deg at most)
    pts = [(u0 + uc + 0.003, back), (u1 - uc - 0.003, back), (u1 - uc, back + 0.004), (u1, e - CH)]
    for k in range(n):
        q = 1.0 - 2.0 * k / (n - 1)
        pts.append(((a0 + a1) / 2 + q * (a1 - a0) / 2, e + (f - e) * (1.0 - q * q)))
    return pts + [(u0, e - CH), (u0 + uc, back + 0.004)]


def cover_section(u0: float, u1: float, f: float, back: float = 0.006, n: int = 13):
    """A cover's plan section: the convex rib (step 2's flat field between raised bands is gone)."""
    return rib_section(u0, u1, f, back, n)


COVER_HS = [COVER_H[0] + (COVER_H[1] - COVER_H[0]) * k / 18 for k in range(19)]


def cover_mesh(i: int, deg: float, hinge: str = HINGE):
    """Cover i: the bowed bronze rib, lofted up its height, turned deg about its hinge."""
    u0, u1, hu = cover_u(i), cover_u(i) + COVER_W, hinge_u(i, hinge)
    return V.loft([[(*rot(p, hu, swing(hinge) * deg), h) for p in cover_section(u0, u1, cover_front(h))]
                   for h in COVER_HS])


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


def lip_mesh(i: int, deg: float, hinge: str = HINGE):
    """Cover i's two lit chamfers, turned with it (a child of the cover)."""
    u0, u1, hu = cover_u(i), cover_u(i) + COVER_W, hinge_u(i, hinge)
    return chamfer_strips(u0, u1, [(h, edge_front(cover_front(h))) for h in COVER_HS], CH,
                          lambda u, v, h: (*rot((u, v), hu, swing(hinge) * deg), h))


def upper_mesh():
    """The leaning wall over the band (the upper modules it replaces): its 20 cm body and, under the crowns, a dark
    panel 2 mm proud of its face from the bend to 2.10."""
    prof = [(0.0, BEND), (IN, TOP), (IN - 0.2 * NORM_V, TOP - 0.2 * NORM_H), (-0.2 * NORM_V, BEND - 0.2 * NORM_H)]
    body = V.loft([[(u, v, h) for v, h in prof] for u in BAND_PLATE])
    top = 2.10
    sec = [(V.cv(BEND) + 0.0, BEND), (V.cv(top), top), (V.cv(top) + 0.002 * NORM_V, top + 0.002 * NORM_H),
           (0.002 * NORM_V, BEND + 0.002 * NORM_H)]
    dark = V.loft([[(u, v, h) for v, h in sec] for u in (BAND[0] - 0.005, BAND[1] + 0.005)])
    return body, dark


def fixed_mesh():
    """The fifth arch's plate: flat-faced, 3 cm proud, chamfered."""
    sec = plate_section(FIXED[0], FIXED[1], lambda q: PROUD, ch=CH)
    return V.loft([[(u, v, h) for u, v in sec] for h in (COVER_H[0], COVER_H[1])])


CROWN_ROWS = 9
CROWN_INSET = 0.03       # gills step 3: a rib crown is the cover's full 30 cm at its foot, 3 cm in each side at its top
CROWN_CREST = 0.040      # its crest out of the leaning wall at its top (the foot: the cover's top, cover_front)


def rib_crown_rows(u0: float, u1: float):
    """A rib crown's rows up the leaning wall: (h, its edges u0, u1, its crest, its edges' height)."""
    rows = []
    for k in range(CROWN_ROWS):
        t = k / (CROWN_ROWS - 1)
        h = BEND + (CROWN_TOP - BEND) * t
        a = CROWN_INSET * t * t
        f = cover_front(COVER_H[1]) + (CROWN_CREST - cover_front(COVER_H[1])) * (1 - (1 - t) ** 2)
        rows.append((h, u0 + a, u1 - a, f, edge_front(f)))
    return rows


def rib_crown_mesh(u0: float, u1: float):
    """gills step 3: a cover's crown as the same convex rib, continuing the shut cover's top up the leaning wall (its
    back 1 cm into the wall's panel), so cover and crown read as one arch."""
    return V.loft([[(u, V.cv(h) + v, h) for u, v in rib_section(a, b, f, back=-0.01, e=e)]
                   for h, a, b, f, e in rib_crown_rows(u0, u1)])


def rib_crown_strips(u0: float, u1: float):
    return chamfer_strips(u0, u1, [(h, e, a, b) for h, a, b, f, e in rib_crown_rows(u0, u1)], CH,
                          lambda u, v, h: (u, V.cv(h) + v, h))


def crown_mesh(u0: float, u1: float):
    """A fixed crown over an arch: from the bend to CROWN_TOP along the leaning wall, 3.5 cm proud of it (3 mm clear of
    the upper wall's panels), 24 cm wide at its foot narrowing to 18 (the drawing's 3 and 6 cm insets)."""
    loops = []
    for k in range(5):
        h = BEND + (CROWN_TOP - BEND) * k / 4
        a = 0.03 + 0.03 * k / 4
        w0 = V.cv(h)
        sec = plate_section(u0 + a, u1 - a, lambda q: 0.035 + 0.004 * (1 - q * q), back=-0.01, ch=0.007, n=5)
        loops.append([(u, w0 + v, h) for u, v in sec])
    return V.loft(loops)


def crown_strips(u0: float, u1: float):
    """A crown's two lit chamfers, on crown_mesh's edges (its 3..6 cm insets) up the leaning wall."""
    out = []
    for k in range(4):
        hs = [BEND + (CROWN_TOP - BEND) * (k + j) / 4 for j in (0, 1)]
        a = [0.03 + 0.03 * (k + j) / 4 for j in (0, 1)]
        # each quarter its own straight run (the insets narrow linearly), lofted between its two ends
        for e, du in ((0, 1.0), (1, -1.0)):
            loops = []
            for h, ai in zip(hs, a):
                eu = (u0 + ai) if e == 0 else (u1 - ai)
                o, f, ch = 0.0012 / math.sqrt(2), 0.035, 0.007
                pa, pb = (eu - du * o, f - ch + o), (eu + du * (ch - o), f + o)
                pc, pd = (pb[0] + du * 0.0008, pb[1] - 0.0008), (pa[0] + du * 0.0008, pa[1] - 0.0008)
                w0 = V.cv(h)
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
    return (u, V.cv(h) + 0.039 + w * NORM_V, h + w * NORM_H)


def well_meshes(w: dict):
    """The well behind the plate: its walls, the back (the cool glow), the heat 4 mm behind it, the honeycomb mesh
    1.5 cm in front of it."""
    us = [WELL_U[0] + (WELL_U[1] - WELL_U[0]) * i / 20 for i in range(21)]
    hs = [WELL_H[0] + (WELL_H[1] - WELL_H[0]) * j / 20 for j in range(21)]

    def field(off: float):
        verts = [(u, -_depth(w, u, h) + off, h) for h in hs for u in us]
        n = len(us)
        faces = [(j * n + i, j * n + i + 1, (j + 1) * n + i + 1, (j + 1) * n + i)
                 for j in range(len(hs) - 1) for i in range(n - 1)]
        return verts, faces
    walls = []
    edges = ([(u, WELL_H[0]) for u in us], [(u, WELL_H[1]) for u in us][::-1],
             [(WELL_U[0], h) for h in hs][::-1], [(WELL_U[1], h) for h in hs])
    for e in edges:
        for (ua, ha), (ub, hb) in zip(e, e[1:]):
            walls.append(([(ua, -PLATE_T + 0.001, ha), (ub, -PLATE_T + 0.001, hb), (ub, -_depth(w, ub, hb) - 0.006, hb),
                           (ua, -_depth(w, ua, ha) - 0.006, ha)], [(0, 1, 2, 3)]))
    # the honeycomb: hexagons of 3.5 cm edge (flat sides up), each edge a thin bar facing the throat
    hexes, e = [], 0.035
    dx, dy = 1.5 * e, math.sqrt(3) * e
    cols = int((WELL_U[1] - WELL_U[0]) / dx) + 2
    rows = int((WELL_H[1] - WELL_H[0]) / dy) + 2
    seen = set()
    for c in range(cols):
        for r in range(rows):
            cu = WELL_U[0] + c * dx
            chh = WELL_H[0] + r * dy + (dy / 2 if c % 2 else 0.0)
            corners = [(cu + e * math.cos(math.pi * k / 3), chh + e * math.sin(math.pi * k / 3)) for k in range(6)]
            for a, b in zip(corners, corners[1:] + corners[:1]):
                key = tuple(sorted((round(a[0], 4), round(a[1], 4), round(b[0], 4), round(b[1], 4))))
                if key in seen:
                    continue
                seen.add(key)
                a2 = (min(max(a[0], WELL_U[0] + 0.004), WELL_U[1] - 0.004), min(max(a[1], WELL_H[0] + 0.004), WELL_H[1] - 0.004))
                b2 = (min(max(b[0], WELL_U[0] + 0.004), WELL_U[1] - 0.004), min(max(b[1], WELL_H[0] + 0.004), WELL_H[1] - 0.004))
                if math.dist(a2, b2) < 0.004:
                    continue
                tx, ty = b2[0] - a2[0], b2[1] - a2[1]
                ln = math.hypot(tx, ty)
                nx, ny = -ty / ln * 0.003, tx / ln * 0.003
                q = [(a2[0] - nx, a2[1] - ny), (b2[0] - nx, b2[1] - ny), (b2[0] + nx, b2[1] + ny), (a2[0] + nx, a2[1] + ny)]
                dv = [-_depth(w, x, y) for x, y in q]
                verts = [(x, d + 0.004, y) for (x, y), d in zip(q, dv)] + [(x, d + 0.016, y) for (x, y), d in zip(q, dv)]
                hexes.append((verts, [(4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (1, 2, 6, 5), (3, 0, 4, 7)]))
    return L.merge(*walls), field(0.0), field(-0.004), L.merge(*hexes)


def plate_meshes():
    """The band plate flush with the wall: dark, 3 cm thick round the four slits, a groove GROOVE_D deep under each
    rib edge (step 3); behind it outside the well the wall's 20 cm body (the low and middle modules it replaces)."""
    v0 = -PLATE_T
    cuts = sorted([(slit_c(i) - SLIT_W / 2, slit_c(i) + SLIT_W / 2, "slit") for i in range(COVERS)]
                  + [(*groove(k), "groove") for k in range(COVERS + 1)])
    runs = {"slit": [(0.0, SLIT_H[0], 0.0), (SLIT_H[1], BEND, 0.0)],
            "groove": [(0.0, GROOVE_H[0], 0.0), (GROOVE_H[0], GROOVE_H[1], -GROOVE_D), (GROOVE_H[1], BEND, 0.0)],
            "full": [(0.0, BEND, 0.0)]}
    spans, x = [], BAND_PLATE[0]
    for a, b, kind in cuts:
        if a - x > 1e-6:
            spans.append((x, a, "full"))
        spans.append((a, b, kind))
        x = b
    if BAND_PLATE[1] - x > 1e-6:
        spans.append((x, BAND_PLATE[1], "full"))
    boxes = [L.box(a, b, v0, v1, S.FLOOR + h0, S.FLOOR + h1) for a, b, kind in spans for h0, h1, v1 in runs[kind]]
    body = [L.box(WELL_U[1], BAND_PLATE[1], -0.2, v0, S.FLOOR, S.FLOOR + BEND),
            L.box(BAND_PLATE[0], WELL_U[1], -0.2, v0, S.FLOOR, S.FLOOR + WELL_H[0]),
            L.box(BAND_PLATE[0], WELL_U[1], -0.2, v0, S.FLOOR + WELL_H[1], S.FLOOR + BEND)]
    return L.merge(*boxes), L.merge(*body)


def groove_strips(k: int, v: float):
    """Groove k's lit strip at v (the cyan 4.5 mm off its floor, the red seam 1 mm off it), 2 mm in from its sides."""
    a, b = groove(k)
    return L.box(a + 0.002, b - 0.002, -GROOVE_D + v, -GROOVE_D + v + 0.001, GROOVE_H[0] + 0.004, GROOVE_H[1] - 0.004)


def station_gills(args, layout):
    pid, side = args["id"], args.get("side", "e")
    s = -1.0 if side == "w" else 1.0
    hinge = hinge_side(args)
    calm = calm_deg(args)
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
    add("band", plate, "vent_b_dark")
    add("body", body, "int_silver_b")
    walls, back, heat, mesh = well_meshes(well_depth(layout, side))
    add("well", hh(walls), "vent_b_well")
    add("cool", hh(L.merge(back, *(groove_strips(k, 0.0045) for k in range(COVERS + 1)))), "int_cyan__vent_cool")
    add("heat", hh(heat), "int_halo__vent_heat")
    add("mesh", hh(mesh), "vent_b_dark")
    upper, dark = upper_mesh()
    add("upper", hh(upper), "int_silver_b")
    add("upper_panel", hh(dark), "vent_b_dark")
    for i in range(COVERS):
        add(f"cover{i + 1}", hh(cover_mesh(i, calm, hinge)), "gill_bronze",
            origin=(hinge_u(i, hinge), HINGE_V, S.FLOOR + COVER_H[0]))
        add(f"lip{i + 1}", hh(lip_mesh(i, calm, hinge)), "gill_edge", parent=f"{pid}_cover{i + 1}")
        # the slit's two jambs lit cyan down their 3 cm cut (the concept's bright lines in each gap)
        for k, x in enumerate((slit_c(i) - SLIT_W / 2, slit_c(i) + SLIT_W / 2)):
            d = 0.0015 if k == 0 else -0.0015
            add(f"jamb{i + 1}{'ab'[k]}", hh(L.box(min(x, x + d), max(x, x + d), -PLATE_T + 0.004, -0.004, SLIT_H[0] + 0.01,
                                                  SLIT_H[1] - 0.01)), "glow_cyan__vent_strip")
        add(f"crown{i + 1}", hh(rib_crown_mesh(cover_u(i), cover_u(i) + COVER_W)), "gill_bronze")
        add(f"crown{i + 1}_edge", hh(rib_crown_strips(cover_u(i), cover_u(i) + COVER_W)), "gill_edge")
    for k in range(COVERS + 1):   # step 3: the red seam on each groove's floor, behind its cyan (k 1 at cover 1's mouth edge)
        add(f"seam{k + 1}", hh(groove_strips(k, 0.001)), "int_halo__vent_seam")
    add("fixed", hh(fixed_mesh()), "gill_bronze")
    add("fixed_edge", hh(chamfer_strips(FIXED[0], FIXED[1], [(COVER_H[0], PROUD), (COVER_H[1], PROUD)], CH,
                                        lambda u, v, h: (u, v, h))), "gill_edge")
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
        if p["name"].endswith(("_cover1", "_cover2", "_cover3", "_cover4", "_crown1", "_crown2", "_crown3", "_crown4",
                               "_crown5", "_fixed")):
            p["smooth_deg"] = 30.0
    # the collider: the band's wall and the shut covers (a cover's swing stays inside the player's 0.6 m pass)
    add("col0-convcolonly", L.box(BAND_PLATE[0], BAND_PLATE[1], -0.2, PROUD + 0.005, S.FLOOR, S.FLOOR + BEND), "int_dark")
    add("col1-convcolonly", hh(upper), "int_dark")
    return parts
