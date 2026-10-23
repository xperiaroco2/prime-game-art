"""The throat vents (art #263 step 2, station 1; docs/ship.md "Station 1: the throat vents"): `station_vent_e` and its
mirror `station_vent_w`, each a chunky faceted metal box hung flat on the throat's slanted wall at its spot (ship.toml
[stations] vent_e / vent_w), its front a grille of six curved gill slats in a faceted frame, a column on the hall's
side with a palm scanner for a four-fingered hand, a light bar with a green band and a sliding white marker, and a red
problem lamp at its head. Plain Python: the harness (ship_build.py) makes the meshes.

The piece's frame: the spot at the origin, u (plan x) along the wall, v (plan y) out of the wall into the throat
(the placement's yaw turns +v onto the spot's normal), h absolute (the deck at FLOOR). East: +u runs toward the hall;
the west piece mirrors u, so its column is toward the hall too. In Godot (x, h, v): each slat a leaf node
`<id>_slat<k>` (k 1..6 from the top) with its origin on its hinge (the slat's upper edge, along x): it opens with
rotation.x = -OPEN_RAD * t (t 0 shut .. 1 open); the marker `<id>_marker` a leaf with its origin at its rest point,
the bar's bottom: it slides with position.y = rest + MARK_TRAVEL * t. The game drives the glows by material:
`int_halo__vent_heat` (the heat behind the slats, the problem state), `glow_nav_green__vent_band`,
`glow_nav_white__vent_marker`, `int_cyan__vent_hand` (the scanner's outline) and `glow_nav_red__vent_lamp`; each is
a copy of the library material before its "__" (the night look's [light.mats] family: they glow, light nothing).
Convex colliders `<id>_col0-convcolonly` (the box) and `<id>_col1-convcolonly` (the column); the open slats stay
inside the frame's depth, so they need none."""

from __future__ import annotations

import math

import ship_interior as S
import ship_lib as L

FLOOR = S.FLOOR
BEND, IN, TOP = S.TH_BEND, S.TH_IN, S.TH_H      # the throat wall: vertical to 1.45, then 0.55 in at 2.3

# the driveable glows: copies of library materials, their family before "__"
for _name in ("int_halo__vent_heat", "glow_nav_green__vent_band", "glow_nav_white__vent_marker",
              "int_cyan__vent_hand", "glow_nav_red__vent_lamp"):
    L.MATERIALS[_name] = dict(L.MATERIALS[_name.split("__")[0]])

METAL, TRIM, DARK, CYAN = "int_silver_c", "int_silver_a", "int_dark", "int_cyan"

# --- the numbers (u east piece, h over the deck) ---------------------------------------------------------------------
BOX_U, BOX_H, BOX_V = (-0.78, 0.33), (-0.02, 2.08), 0.48    # the grille box: 1.11 m wide, its front 0.48 m out
COL_U, COL_H, COL_V = (0.32, 0.78), (-0.02, 2.00), 0.44      # the column (0.46 m) on the hall's side
OPEN_U, OPEN_H = (-0.66, 0.21), (0.59, 1.80)                 # the grille's opening
WELL_V = 0.25                                                # the well's back (the heat panel just in front)
SLATS, HINGE_TOP, PITCH, CHORD = 6, 1.77, 0.19, 0.21         # hinges every 0.19 m from 1.77 down; chord 0.21
HINGE_V, TILT, BULGE = 0.29, math.radians(9.0), 0.02         # shut: 9 deg out from vertical, bowed 2 cm outward
THICK = (0.016, 0.007)                                       # a slat's thickness at its hinge and its tip
END_GAP = 0.015                                              # a slat's ends to the well's sides
OPEN_RAD = math.radians(62.0)                                # fully open: 71 deg from hanging, the tip at 0.49 m
UC = (COL_U[0] + COL_U[1]) / 2                               # the column's centre line
PAD_H = (1.02, 1.355)                                        # the scanner's bezel (its centre 1.19)
BAR_H, GLASS_H, BAND_H = (1.37, 1.885), (1.395, 1.862), (1.80, 1.835)
MARK_H = 0.03                                                # the marker's height; it slides from GLASS_H[0]
MARK_TRAVEL = GLASS_H[1] - GLASS_H[0] - MARK_H
LAMP_H, LAMP_R = 1.94, 0.038
UNIT = [-0.78, 0.78, -0.01, 0.5, -0.02, 2.08]                # u0 u1 v0 v1 h0 h1: ship.toml's spot band and depth


def cv(h: float) -> float:
    """How far the throat's wall face stands out at height h over the deck (its chamfer above BEND)."""
    return 0.0 if h <= BEND else (h - BEND) / (TOP - BEND) * IN


def octo(u0, u1, h0, h1, c) -> list[tuple[float, float]]:
    """A rectangle with chamfered corners (bl, br, tr, tl), counter-clockwise in (u, h)."""
    bl, br, tr, tl = c
    return [(u0 + bl, h0), (u1 - br, h0), (u1, h0 + br), (u1, h1 - tr), (u1 - tr, h1), (u0 + tl, h1), (u0, h1 - tl),
            (u0, h0 + bl)]


def grow(u0, u1, h0, h1, c, d) -> list[tuple[float, float]]:
    """octo grown by d (negative: inset), its corners kept 45 deg."""
    return octo(u0 - d, u1 + d, h0 - d, h1 + d, [max(0.006, k + 0.4142 * d) for k in c])


def split(outline) -> list[tuple[float, float]]:
    """An octo outline with a point at the wall's bend (h BEND) on each side (indices 3 and 8): its back folds there."""
    (a, b), (c, d) = outline[2], outline[6]
    return [*outline[:3], (a, BEND), *outline[3:7], (c, BEND), *outline[7:]]


def ring(outline, v, back=False) -> list[tuple[float, float, float]]:
    """An outline at depth v; back: kept 2 cm inside the wall's chamfer (the box's back follows the wall)."""
    return [(u, max(v, cv(h) - 0.02) if back else v, FLOOR + h) for u, h in outline]


def loft(loops, cap0=True, cap1=True, fold=False) -> tuple[list, list]:
    """Loops of equal length joined by quads, the end loops capped (convex loops); fold: the first loop (a `split`
    outline's back, folded along the wall's chamfer: no plane) capped in its two planar parts."""
    n = len(loops[0])
    verts = [p for lp in loops for p in lp]
    faces = [(i * n + j, i * n + (j + 1) % n, (i + 1) * n + (j + 1) % n, (i + 1) * n + j)
             for i in range(len(loops) - 1) for j in range(n)]
    if fold:   # a split outline's back: below and above the bend, each part a plane (vertical; on the chamfer)
        faces += [(3, 2, 1, 0, 9, 8), (8, 7, 6, 5, 4, 3)]
    elif cap0:
        faces.append(tuple(range(n - 1, -1, -1)))
    if cap1:
        faces.append(tuple(range((len(loops) - 1) * n, len(loops) * n)))
    return verts, faces


def plate(outline, v0, v1, bevel=0.0) -> tuple[list, list]:
    """A flat plate in (u, h) from v0 to v1, its front edges bevelled."""
    if bevel <= 0:
        return loft([ring(outline, v0), ring(outline, v1)])
    us, hs = [p[0] for p in outline], [p[1] for p in outline]
    inner = [(u + (bevel if u < (min(us) + max(us)) / 2 else -bevel), h + (bevel if h < (min(hs) + max(hs)) / 2
              else -bevel)) for u, h in outline]
    return loft([ring(outline, v0), ring(outline, v1 - bevel), ring(inner, v1)])


def hemisphere_v(c, r, v0, rings=4, segs=16) -> tuple[list, list]:
    """A dome on the plane v = v0 bulging toward +v, centred at (u, h) = c."""
    verts = [(c[0] + r * math.cos(t) * math.cos(2 * math.pi * j / segs), v0 + r * math.sin(t),
              FLOOR + c[1] + r * math.cos(t) * math.sin(2 * math.pi * j / segs))
             for t in [math.pi / 2 * i / rings for i in range(rings)] for j in range(segs)]
    verts.append((c[0], v0 + r, FLOOR + c[1]))
    faces = [(i * segs + j, i * segs + (j + 1) % segs, (i + 1) * segs + (j + 1) % segs, (i + 1) * segs + j)
             for i in range(rings - 1) for j in range(segs)]
    top, last = len(verts) - 1, (rings - 1) * segs
    faces += [(last + j, last + (j + 1) % segs, top) for j in range(segs)] + [tuple(range(segs - 1, -1, -1))]
    return verts, faces


def ribbon(points, width, v0, v1) -> tuple[list, list]:
    """A closed outline (u, h) drawn as a flat strip `width` wide from v0 to v1 (mitred corners): a closed ring."""
    n, loops = len(points), []
    for i in range(n):
        a, b, c = points[i - 1], points[i], points[(i + 1) % n]
        d0 = (b[0] - a[0], b[1] - a[1])
        d1 = (c[0] - b[0], c[1] - b[1])
        l0, l1 = math.hypot(*d0), math.hypot(*d1)
        n0, n1 = (-d0[1] / l0, d0[0] / l0), (-d1[1] / l1, d1[0] / l1)
        m = (n0[0] + n1[0], n0[1] + n1[1])
        lm = math.hypot(*m)
        m = (m[0] / lm, m[1] / lm)
        k = min(2.5, 1.0 / max(0.4, m[0] * n1[0] + m[1] * n1[1])) * width / 2
        lo, hi = (b[0] - m[0] * k, b[1] - m[1] * k), (b[0] + m[0] * k, b[1] + m[1] * k)
        loops.append([(lo[0], v0, FLOOR + lo[1]), (hi[0], v0, FLOOR + hi[1]), (hi[0], v1, FLOOR + hi[1]),
                      (lo[0], v1, FLOOR + lo[1])])
    verts = [p for lp in loops for p in lp]
    faces = [(i * 4 + j, i * 4 + (j + 1) % 4, ((i + 1) % n) * 4 + (j + 1) % 4, ((i + 1) % n) * 4 + j)
             for i in range(n) for j in range(4)]
    return verts, faces


def hand(c) -> list[tuple[float, float]]:
    """A four-fingered hand's outline (a thumb and three fingers) round (u, h) = c, counter-clockwise (the west piece
    mirrors it with the rest)."""
    pts = [(0.048, -0.085), (0.05, 0.0)]                        # the wrist's right corner up the palm's outer side
    for bu, ang, length, w in ((0.034, -10.0, 0.066, 0.022), (0.0, 0.0, 0.076, 0.022),
                               (-0.034, 10.0, 0.068, 0.022), (-0.05, 48.0, 0.055, 0.022)):  # 3 fingers, the thumb
        a = math.radians(90.0 + ang)
        d, nrm = (math.cos(a), math.sin(a)), (math.cos(a - math.pi / 2), math.sin(a - math.pi / 2))
        base = (bu, 0.012 if abs(ang) < 20 else -0.02)
        tip = (base[0] + d[0] * length, base[1] + d[1] * length)
        pts.append((base[0] + nrm[0] * w / 2, base[1] + nrm[1] * w / 2))
        pts.append((tip[0] + nrm[0] * w / 2, tip[1] + nrm[1] * w / 2))
        for t in (0.25, 0.5, 0.75):                              # the round finger tip
            q = a - math.pi / 2 + math.pi * t
            pts.append((tip[0] + math.cos(q) * w / 2, tip[1] + math.sin(q) * w / 2))
        pts.append((tip[0] - nrm[0] * w / 2, tip[1] - nrm[1] * w / 2))
        pts.append((base[0] - nrm[0] * w / 2, base[1] - nrm[1] * w / 2))
    pts += [(-0.052, -0.04), (-0.044, -0.085)]                 # down the palm's thumb side to the wrist
    return [(c[0] + u, c[1] + h) for u, h in pts]


def slat_loops(k: int):
    """Slat k's loops along u (shut), and its hinge (u mid, v, h): a curved gill blade, its chord shorter at its ends."""
    hk = HINGE_TOP - k * PITCH
    d, nrm = (math.sin(TILT), -math.cos(TILT)), (math.cos(TILT), math.sin(TILT))   # down the blade, out of it
    u0, u1 = OPEN_U[0] + END_GAP, OPEN_U[1] - END_GAP
    loops = []
    for i in range(9):
        u = u0 + (u1 - u0) * i / 8
        chord = CHORD * (0.84 + 0.16 * math.sin(math.pi * i / 8))
        top, bot = [], []
        for j in range(6):
            s = j / 5
            mid = (HINGE_V + d[0] * chord * s + nrm[0] * BULGE * math.sin(math.pi * s),
                   hk + d[1] * chord * s + nrm[1] * BULGE * math.sin(math.pi * s))
            t = (THICK[0] + (THICK[1] - THICK[0]) * s) / 2
            top.append((u, mid[0] + nrm[0] * t, FLOOR + mid[1] + nrm[1] * t))
            bot.append((u, mid[0] - nrm[0] * t, FLOOR + mid[1] - nrm[1] * t))
        loops.append(top + bot[::-1])
    return loops, ((u0 + u1) / 2, HINGE_V, FLOOR + hk)


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

    box_c, col_c, open_c = (0.06, 0.02, 0.03, 0.16), (0.03, 0.05, 0.10, 0.04), (0.03, 0.03, 0.025, 0.025)
    box = split(octo(*BOX_U, *BOX_H, box_c))
    add("body", loft([ring(box, -0.01, True), ring(box, BOX_V - 0.03, True),
                      ring(split(grow(*BOX_U, *BOX_H, box_c, -0.025)), BOX_V),
                      ring(split(grow(*OPEN_U, *OPEN_H, open_c, 0.055)), BOX_V),
                      ring(split(grow(*OPEN_U, *OPEN_H, open_c, 0.02)), BOX_V - 0.02),
                      ring(split(octo(*OPEN_U, *OPEN_H, open_c)), BOX_V - 0.04),
                      ring(split(octo(*OPEN_U, *OPEN_H, open_c)), WELL_V)], fold=True), METAL)
    col = split(octo(*COL_U, *COL_H, col_c))
    add("column", loft([ring(col, -0.01, True), ring(col, COL_V - 0.03, True),
                        ring(split(grow(*COL_U, *COL_H, col_c, -0.025)), COL_V)], fold=True), METAL)
    # the heat behind the slats and the lower panel's plate
    add("heat", plate(grow(*OPEN_U, *OPEN_H, open_c, -0.004), WELL_V - 0.004, WELL_V + 0.006), "int_halo__vent_heat")
    add("kick", plate(octo(-0.70, 0.25, 0.10, 0.48, (0.04, 0.04, 0.04, 0.04)), BOX_V - 0.01, BOX_V + 0.008, 0.006),
        TRIM)
    # the cyan edge strips (sunk half into the faces they lie on)
    strips = [(-0.737, -0.725, 0.75, 1.25), (-0.737, -0.725, 1.35, 1.6), (-0.30, -0.05, 0.035, 0.047),
              (0.0, 0.17, 2.025, 2.037), (0.733, 0.745, 0.35, 0.95)]
    vs = [(BOX_V - 0.004, BOX_V + 0.003)] * 4 + [(COL_V - 0.004, COL_V + 0.003)]
    add("strips", L.merge(*[L.box(u0, u1, v0, v1, FLOOR + h0, FLOOR + h1) for (u0, u1, h0, h1), (v0, v1)
                            in zip(strips, vs)]), CYAN)
    # the scanner: a bezel, a dark pad, the hand's glowing outline
    add("pad_bezel", plate(octo(UC - 0.13, UC + 0.13, *PAD_H, (0.03,) * 4), COL_V - 0.01, COL_V + 0.015, 0.006), TRIM)
    add("pad", plate(octo(UC - 0.105, UC + 0.105, PAD_H[0] + 0.025, PAD_H[1] - 0.025, (0.02,) * 4), COL_V + 0.01,
                     COL_V + 0.021), DARK)
    add("hand", ribbon(hand((UC + 0.02, (PAD_H[0] + PAD_H[1]) / 2 - 0.005)), 0.006, COL_V + 0.019, COL_V + 0.025),
        "int_cyan__vent_hand")
    # the light bar: a housing with a recess, its dark glass, the green band, the marker
    bar_o, bar_c = (UC - 0.055, UC + 0.055, *BAR_H), (0.02,) * 4
    add("bar_housing", loft([ring(octo(*bar_o, bar_c), COL_V - 0.01), ring(octo(*bar_o, bar_c), COL_V + 0.014),
                             ring(grow(*bar_o, bar_c, -0.008), COL_V + 0.022),
                             ring(grow(*bar_o, bar_c, -0.02), COL_V + 0.022),
                             ring(grow(*bar_o, bar_c, -0.02), COL_V + 0.012)]), TRIM)
    glass = (UC - 0.032, UC + 0.032)
    add("bar_glass", L.box(*glass, COL_V + 0.006, COL_V + 0.014, FLOOR + GLASS_H[0], FLOOR + GLASS_H[1]), DARK)
    add("band", L.box(*glass, COL_V + 0.012, COL_V + 0.017, FLOOR + BAND_H[0], FLOOR + BAND_H[1]),
        "glow_nav_green__vent_band")
    add("marker", L.box(UC - 0.026, UC + 0.026, COL_V + 0.012, COL_V + 0.019, FLOOR + GLASS_H[0],
                        FLOOR + GLASS_H[0] + MARK_H), "glow_nav_white__vent_marker",
        origin=(UC, COL_V + 0.014, FLOOR + GLASS_H[0]))
    # the problem lamp at the column's head: a collar and a red dome
    collar = [(UC + 0.048 * math.cos(math.pi * (i + 0.5) / 4), LAMP_H + 0.048 * math.sin(math.pi * (i + 0.5) / 4))
              for i in range(8)]
    add("lamp_collar", plate(collar, COL_V - 0.01, COL_V + 0.016), TRIM)
    add("lamp", hemisphere_v((UC, LAMP_H), LAMP_R, COL_V + 0.014), "glow_nav_red__vent_lamp")
    # the slats: leaves with their origin on the hinge
    for k in range(SLATS):
        loops, hinge = slat_loops(k)
        add(f"slat{k + 1}", loft(loops), METAL, origin=hinge)
    # convex colliders: the box and the column (their outer loops)
    add("col0-convcolonly", loft([ring(box, -0.01, True), ring(box, BOX_V - 0.03, True),
                                  ring(split(grow(*BOX_U, *BOX_H, box_c, -0.025)), BOX_V)], fold=True), DARK)
    add("col1-convcolonly", loft([ring(col, -0.01, True), ring(col, COL_V - 0.03, True),
                                  ring(split(grow(*COL_U, *COL_H, col_c, -0.025)), COL_V)], fold=True), DARK)
    return parts
