"""The throat vents (art #263 step 2, station 1; docs/ship.md "Station 1: the throat vents"): `station_vent_e` and its
mirror `station_vent_w`, each a chunky faceted metal box hung flat on the throat's slanted wall at its spot (ship.toml
[stations] vent_e / vent_w), its front a grille of seven crescent gill slats in a faceted frame, a column on the hall's
side with a palm scanner for a four-fingered hand, a light bar with a green band and a sliding white marker, and a red
problem lamp at its head. Plain Python: the harness (ship_build.py) makes the meshes.

The piece's frame: the spot at the origin, u (plan x) along the wall, v (plan y) out of the wall into the throat
(the placement's yaw turns +v onto the spot's normal), h absolute (the deck at FLOOR). East: +u runs toward the hall;
the west piece mirrors u, so its column is toward the hall too. In Godot (x, h, v): each slat a leaf node
`<id>_slat<k>` (k 1..7 from the top) with its origin on its hinge (the slat's upper edge, along x): it opens with
rotation.x = -OPEN_RAD * t (t 0 shut: 30 deg out from hanging, a lit crescent slit under each slat .. 1 open: 85 deg,
wide lit gaps); the marker `<id>_marker` a leaf with its origin at its rest point,
the bar's bottom: it slides with position.y = rest + MARK_TRAVEL * t. The game drives the glows by material:
`int_halo__vent_heat` (the heat behind the slats, the problem state; `<id>_heat`), `int_cyan__vent_cool` (the calm
glow on `<id>_cool`, 4 mm in front of the heat: shown calm, hidden for the problem), `glow_nav_green__vent_band`,
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

# the driveable glows: copies of library materials, their family before "__"; the heat a saturated orange and the
# problem lamp a deep red (step 2: the library's strengths washed them to tan and pink under AgX)
for _name in ("int_halo__vent_heat", "int_cyan__vent_cool", "glow_nav_green__vent_band", "glow_nav_white__vent_marker",
              "int_cyan__vent_hand", "glow_nav_red__vent_lamp"):
    L.MATERIALS[_name] = dict(L.MATERIALS[_name.split("__")[0]])
L.MATERIALS["int_halo__vent_heat"].update(base=(1.0, 0.30, 0.02, 1.0), emission=(1.0, 0.30, 0.02), strength=1.5)
L.MATERIALS["int_cyan__vent_cool"].update(base=(0.02, 0.62, 1.0, 1.0), emission=(0.02, 0.62, 1.0), strength=1.5)
L.MATERIALS["glow_nav_red__vent_lamp"].update(base=(1.0, 0.015, 0.01, 1.0), emission=(1.0, 0.015, 0.01), strength=1.2,
                                              roughness=0.15)

# the hall's and throat's own metals (cor_wall_*: panels int_silver_a / _b, belts and lips int_silver_c)
FRAME, COLUMN, SLAT = "int_silver_a", "int_silver_b", "int_silver_c"   # the frame as tone a's panels, slats as trims
TRIM, DARK, CYAN = "int_silver_c", "int_dark", "int_cyan"

# --- the numbers (u east piece, h over the deck) ---------------------------------------------------------------------
BOX_U, BOX_H, BOX_V = (-0.78, 0.33), (-0.02, 2.08), 0.48    # the grille box: 1.11 m wide, its front 0.48 m out
COL_U, COL_H, COL_V = (0.32, 0.78), (-0.02, 2.00), 0.44      # the column (0.46 m) on the hall's side
BOX_C, COL_C = (0.12, 0.04, 0.05, 0.15), (0.04, 0.06, 0.10, 0.04)   # their 45 deg corner cuts (bl, br, tr, tl)
OPEN_U, OPEN_H = (-0.60, 0.15), (0.17, 1.79)                 # the grille's opening: the whole front inside the frame;
OPEN_C = (0.05, 0.05, 0.08, 0.05)                            # its top is the wall's chamfer behind the well (cv 0.2)
WELL_V = 0.215                                               # the well's back (the heat panel just in front)
SLATS, HINGE_TOP, PITCH, CHORD = 7, 1.765, 0.225, 0.215      # hinges every 0.225 m from 1.765 down; chord at the ends
CRESCENT = 0.24                                              # the chord 24 % shorter mid-blade: the tail's edge arches
HINGE_V, TILT, BULGE = 0.25, math.radians(30.0), 0.015       # shut: 30 deg out from hanging, bowed 1.5 cm outward
NOSE_R, TAIL_T = 0.009, 0.0025                               # the gill's round nose round its hinge, its thin tail
SWEEP_V = 0.010                                              # its tail bowed out along u by 1.0 cm at its middle
END_GAP = 0.012                                              # a slat's ends to the well's sides
OPEN_RAD = math.radians(55.0)                                # fully open: 85 deg from hanging, the tip at 0.47 m
COOL_V = WELL_V + 0.012                                      # the cool glow's panel, just in front of the heat's
UC = (COL_U[0] + COL_U[1]) / 2                               # the column's centre line
PAD_H = (0.94, 1.27)                                         # the scanner's bezel (its centre 1.105)
BAR_H, GLASS_H, BAND_H = (1.30, 1.775), (1.325, 1.75), (1.685, 1.72)
MARK_H = 0.03                                                # the marker's height; it slides from GLASS_H[0]
MARK_TRAVEL = GLASS_H[1] - GLASS_H[0] - MARK_H
LAMP_H, LAMP_R = 1.857, 0.045                                # the beacon's centre on the column's face, its dome
LAMP_BASE = 0.058                                            # its octagonal base's radius (the face's top at 1.92)
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


def hemisphere_v(c, r, v0, rings=4, segs=16, depth=None) -> tuple[list, list]:
    """A dome on the plane v = v0 bulging toward +v, centred at (u, h) = c; depth: its height (else r, a half ball)."""
    depth = r if depth is None else depth
    verts = [(c[0] + r * math.cos(t) * math.cos(2 * math.pi * j / segs), v0 + depth * math.sin(t),
              FLOOR + c[1] + r * math.cos(t) * math.sin(2 * math.pi * j / segs))
             for t in [math.pi / 2 * i / rings for i in range(rings)] for j in range(segs)]
    verts.append((c[0], v0 + depth, FLOOR + c[1]))
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


def disc_v(c, r, v0, v1, segs=16) -> tuple[list, list]:
    """A round plate (a cylinder along v) from v0 to v1 centred at (u, h) = c."""
    pts = [(c[0] + r * math.cos(2 * math.pi * (j + 0.5) / segs), c[1] + r * math.sin(2 * math.pi * (j + 0.5) / segs))
           for j in range(segs)]
    return loft([ring(pts, v0), ring(pts, v1)])


def corner_cut(h0: float, h1: float) -> tuple[float, float]:
    """How far the opening's 45 deg corners narrow it at its u0 and u1 sides anywhere between h0 and h1."""
    bl, br, tr, tl = OPEN_C
    lo, hi = OPEN_H
    return (max(0.0, lo + bl - h0, h1 - (hi - tl)), max(0.0, lo + br - h0, h1 - (hi - tr)))


def slat_loops(k: int):
    """Slat k's loops along u (shut), and its hinge (u mid, v, h): a gill blade, its thick round nose round the hinge,
    swept down and out to a thin tail, bowed outward across its chord and along u, its chord shorter at its ends."""
    hk = HINGE_TOP - k * PITCH
    d, nrm = (math.sin(TILT), -math.cos(TILT)), (math.cos(TILT), math.sin(TILT))   # down the blade, out of it
    c0, c1 = corner_cut(hk - CHORD * math.cos(TILT) - 0.01, hk + NOSE_R)
    u0, u1 = OPEN_U[0] + END_GAP + c0, OPEN_U[1] - END_GAP - c1
    loops, n_u, n_s = [], 9, 6
    for i in range(n_u):
        a = i / (n_u - 1)
        u = u0 + (u1 - u0) * a
        chord = CHORD * (1.0 - CRESCENT * math.sin(math.pi * a))   # the tail arches: a crescent slit under it
        sv = SWEEP_V * math.sin(math.pi * a)
        mids, tans = [], []
        for j in range(n_s + 1):
            s = j / n_s
            b = BULGE * math.sin(math.pi * s)
            db = BULGE * math.pi * math.cos(math.pi * s) / chord
            mids.append((HINGE_V + sv * s + d[0] * chord * s + nrm[0] * b, hk + d[1] * chord * s + nrm[1] * b))
            tx, ty = d[0] + nrm[0] * db, d[1] + nrm[1] * db
            tl = math.hypot(tx, ty)
            tans.append((tx / tl, ty / tl))
        up, low = [], []
        for j, ((mv, mh), (tx, ty)) in enumerate(zip(mids, tans)):
            t = TAIL_T + (NOSE_R - TAIL_T) * (1.0 - j / n_s) ** 1.4
            nv, nh = -ty, tx            # the tangent turned: out of the blade's outer face (+v)
            if nv < 0:
                nv, nh = -nv, -nh
            up.append((u, mv + nv * t, FLOOR + mh + nh * t))
            low.append((u, mv - nv * t, FLOOR + mh - nh * t))
        # the nose: a half round over the leading edge, from the outer face over the top to the inner face
        cvv, chh = mids[0]
        ov, oh = up[0][1] - cvv, up[0][2] - FLOOR - chh
        nose = []
        for q in (0.2, 0.4, 0.6, 0.8):
            ca, sa = math.cos(math.pi * q), math.sin(math.pi * q)
            nose.append((u, cvv + ov * ca - tans[0][0] * NOSE_R * sa, FLOOR + chh + oh * ca - tans[0][1] * NOSE_R * sa))
        loops.append(up[::-1] + nose + low)
    return loops, ((u0 + u1) / 2, HINGE_V, FLOOR + hk)


def chunky(outline, c, vf, depth):
    """The rings of a heavy machined block: its sides from the wall out to vf - depth, a deep 45 deg chamfer and a
    second facet up to the front at vf, then a groove (1.4 cm wide, 1.2 cm deep) round the front face's edge."""
    def g(d):
        return split(grow(*outline, c, d))
    return [ring(split(octo(*outline, c)), -0.01, True), ring(split(octo(*outline, c)), vf - depth, True),
            ring(g(-0.044), vf - 0.018, True), ring(g(-0.056), vf), ring(g(-0.062), vf),
            ring(g(-0.064), vf - 0.012), ring(g(-0.078), vf - 0.012), ring(g(-0.08), vf)]


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

    box_rings = chunky((*BOX_U, *BOX_H), BOX_C, BOX_V, 0.065)

    def op(d):
        return split(grow(*OPEN_U, *OPEN_H, OPEN_C, d))
    edge = split(octo(*OPEN_U, *OPEN_H, OPEN_C))
    add("body", loft(box_rings + [ring(op(0.06), BOX_V), ring(op(0.03), BOX_V - 0.03), ring(op(0.012), BOX_V - 0.04),
                                  ring(edge, BOX_V - 0.05), ring(edge, WELL_V)], fold=True), FRAME)
    col_rings = chunky((*COL_U, *COL_H), COL_C, COL_V, 0.06)
    add("column", loft(col_rings, fold=True), COLUMN)
    # the glow behind the slats: the heat (the problem) and, 4 mm in front of it, the cool glow (calm); the game shows
    # `cool` when calm and hides it for the problem, so the slits glow cyan or orange
    add("heat", plate(grow(*OPEN_U, *OPEN_H, OPEN_C, -0.004), WELL_V - 0.004, WELL_V + 0.006), "int_halo__vent_heat")
    add("cool", plate(grow(*OPEN_U, *OPEN_H, OPEN_C, -0.004), COOL_V - 0.002, COOL_V + 0.002), "int_cyan__vent_cool")
    # the cyan strips, each in its groove (the groove's floor 1.2 cm under the face, its middle 7.1 cm in)
    gi = 0.071
    runs = [(BOX_U[0] + gi, 0.40, 1.00, "v", BOX_V), (BOX_U[0] + gi, 1.12, 1.62, "v", BOX_V),
            (BOX_H[0] + gi, -0.48, -0.10, "h", BOX_V), (BOX_H[1] - gi, -0.40, -0.02, "h", BOX_V),
            (COL_U[1] - gi, 0.30, 0.86, "v", COL_V), (COL_U[0] + gi, 0.20, 0.70, "v", COL_V)]
    vfs = []
    for at, a0, a1, kind, front in runs:
        u0, u1, h0, h1 = (at - 0.004, at + 0.004, a0, a1) if kind == "v" else (a0, a1, at - 0.004, at + 0.004)
        vfs.append(L.box(u0, u1, front - 0.013, front - 0.005, FLOOR + h0, FLOOR + h1))
    add("strips", L.merge(*vfs), CYAN)
    # the scanner: a faceted bezel, a dark pad sunk in it, the hand's glowing outline
    pad_o, pad_c = (UC - 0.13, UC + 0.13, *PAD_H), (0.035,) * 4
    add("pad_bezel", loft([ring(octo(*pad_o, pad_c), COL_V - 0.01), ring(octo(*pad_o, pad_c), COL_V + 0.006),
                           ring(grow(*pad_o, pad_c, -0.012), COL_V + 0.018),
                           ring(grow(*pad_o, pad_c, -0.02), COL_V + 0.018),
                           ring(grow(*pad_o, pad_c, -0.024), COL_V + 0.008)]), TRIM)
    add("pad", plate(grow(*pad_o, pad_c, -0.024), COL_V + 0.004, COL_V + 0.009), DARK)
    add("hand", ribbon(hand((UC + 0.02, (PAD_H[0] + PAD_H[1]) / 2 - 0.005)), 0.006, COL_V + 0.008, COL_V + 0.012),
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
    # the problem lamp near the column's head: a beacon, an octagonal base, a metal collar, a red dome on a red band
    lc = (UC, LAMP_H)
    base = [(UC + LAMP_BASE * math.cos(math.pi * (i + 0.5) / 4), LAMP_H + LAMP_BASE * math.sin(math.pi * (i + 0.5) / 4))
            for i in range(8)]
    lip = [(UC + (x - UC) * 0.86, LAMP_H + (h - LAMP_H) * 0.86) for x, h in base]
    # (9 cm across; the dome flattened to 2.9 cm so the beacon keeps to the unit's 0.5 m depth)
    add("lamp_collar", L.merge(loft([ring(base, COL_V - 0.01), ring(base, COL_V + 0.008), ring(lip, COL_V + 0.013)]),
                               disc_v(lc, LAMP_R + 0.006, COL_V + 0.012, COL_V + 0.022, segs=20),
                               disc_v(lc, LAMP_R + 0.003, COL_V + 0.022, COL_V + 0.025, segs=20)), TRIM, smooth_deg=40)
    add("lamp", L.merge(disc_v(lc, LAMP_R, COL_V + 0.024, COL_V + 0.031, segs=20),
                        hemisphere_v(lc, LAMP_R, COL_V + 0.031, rings=5, segs=20, depth=0.029)),
        "glow_nav_red__vent_lamp", smooth_deg=50)
    # the slats: leaves with their origin on the hinge (the nose's axis)
    for k in range(SLATS):
        loops, hinge = slat_loops(k)
        add(f"slat{k + 1}", loft(loops), SLAT, origin=hinge, smooth_deg=40)
    # convex colliders: the box and the column (their outer loops)
    add("col0-convcolonly", loft(box_rings[:4], fold=True), DARK)
    add("col1-convcolonly", loft(col_rings[:4], fold=True), DARK)
    return parts
