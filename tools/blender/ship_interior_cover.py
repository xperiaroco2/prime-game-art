"""The throat's gill covers, the pilot (art #263, 2026-10-29; design's gill-covers concept, prime-game-design c275972
ideas/ship-components/gill-covers/covers_ingame.jpg; docs/ship.md "The gill cover pilot"): ONE rigid, already-curved
metal cover like a fish's gill cover on the clean east wall (th_wall_e), at the middle slit's place, before all ten.

The cover in front view is a crescent: both edges arcs through the same two tips 1.20 m apart straight up the wall (the
chord, t 0.75-1.95 above the deck, on the hall's side): the outer (convex) arc sags SAG_O toward the mouth, the inner
SAG_I, so the plate is 30 cm at its widest; its middle stands at s 2.69. The plate is a 6 mm shell domed out of the
wall: its outer arc and its tips rest on the wall, it rises BULGE in its middle, and its open edge (the inner arc,
toward the hall) stands LIP off the wall even shut, so a thin red line shows under it. It turns on a vertical hinge
along its outer edge (the edge toward the ramp): the axis touches the outer arc's furthest point, KNUCKLE_R off the
wall, three knuckles on it (the top and bottom fixed to the wall on small tabs, the middle one on the plate). Every
plate point lies on the hall's side of the axis and in front of the wall, so any outward turn (0..MAX_DEG) lifts it
further off the wall: no swept point passes through the wall (tests: test_ship_cover).

Behind the plate a shallow pocket (POCKET_D) is cut into the band in the plate's shape, INSET in from the outer arc and
the tips (the plate rests on the wall there) and EDGE_GAP out past the open edge: its walls a dark metal with a faint glow, its floor a glow the
game turns red (shut, gasping) or cyan (open). A thin strip on the plate's open edge face (`rim`) glows the same way.

Parts (Godot `cover<k>_<part>`; k = 3, the middle of the five slots): `plate`, `rim` and `knuckle` turn about the
hinge (their object origins on the axis at the cover's middle height: rotate them about local Y; the open edge moves
out, the GLB's +z, for a negative turn on the east wall, positive on the mirrored west); `hinge` (the fixed knuckles
and tabs), `pocket` (walls) and `glow` (the floor) stay. godot/ship/gill_cover.gd is the reference controller.

Frame: the wall's (ship_interior_throat.point): u = s along the wall from the mouth's corner, t up from the deck, w out
of the wall into the throat. Plain Python (ship_build.py makes the meshes)."""

from __future__ import annotations

import math

import ship_interior as S
import ship_lib as L

P = S.P

K = 3                                                   # the slot (the middle of the five)
S_MID, T_MID = 2.69, 1.35                               # the crescent's middle (the old middle slit's place)
CHORD = 1.20                                            # the tips' line, t 0.75-1.95
SAG_O, SAG_I = 0.335, 0.035                             # the outer and inner arcs' sag toward the mouth
WIDTH = SAG_O - SAG_I                                   # 0.30 at the middle
U_HINGE = S_MID - WIDTH / 2                             # the outer arc's furthest point toward the mouth (2.54)
U_CHORD = U_HINGE + SAG_O                               # the tips' line (2.875)
TIP = 0.014                                             # the tips cut where the crescent is this wide
THICK = 0.006                                           # the plate's shell
W_REST = 0.003                                          # the plate's back off the wall where it rests
BULGE = 0.055                                           # the dome's height over the wall at its middle
LIP = 0.016                                             # the open edge's height off the wall at the middle (shut)
KNUCKLE_R = 0.011
AXIS_U = U_HINGE - 0.004                                # the hinge axis: just toward the mouth of the plate's edge
AXIS_W = KNUCKLE_R + 0.002                              # and off the wall (the knuckles clear it by 2 mm)
KNUCKLE_MID = (-0.040, 0.040)                           # the plate's knuckle (t from T_MID)
KNUCKLE_FIX = ((-0.125, -0.043), (0.043, 0.125))        # the fixed ones
TAB_W = 0.034                                           # their tabs on the wall, toward the mouth
POCKET_D = 0.045                                        # the pocket's depth
INSET = 0.022                                           # the pocket's edge inside the plate's outer arc and tips
EDGE_GAP = 0.008                                        # and out past the open edge (the shut red line)
RIM_W = 0.009                                           # the rim band on the plate's front along the open edge
RIM_OUT = 0.0008                                        # the rim strip off the open edge face
ROWS, COLS = 48, 12                                     # the plate's grid (along the chord, across)
MAX_DEG = 35.0                                          # the tests' sweep (the open swing's overshoot peaks under 33)
PLATE_MAT, RIM_MAT, GLOW_MAT, WALL_MAT, HINGE_MAT = (
    "cover_metal", "int_cyan__cover_rim", "int_cyan__cover_glow", "int_cyan__cover_wall", "cover_hinge")

# the plate: a pale bronze-silver (the concept's champagne metal), the hinge a darker steel; the glows' GLB colour is
# the shut state's red (the game drives both)
L.MATERIALS.update({
    "cover_metal": {"base": (0.50, 0.42, 0.33, 1.0), "metallic": 0.85, "roughness": 0.27},
    "cover_hinge": {"base": (0.30, 0.30, 0.31, 1.0), "metallic": 0.9, "roughness": 0.32},
    "int_cyan__cover_rim": {**L.MATERIALS["int_cyan"], "base": (1.0, 0.12, 0.04, 1.0), "emission": (1.0, 0.12, 0.04),
                            "strength": 2.0},
    "int_cyan__cover_glow": {**L.MATERIALS["int_cyan"], "base": (0.25, 0.03, 0.01, 1.0), "emission": (1.0, 0.12, 0.04),
                             "strength": 0.8},
    # the pocket's walls: a dark metal with a weaker glow of the same colour (int_dark read as a black hole)
    "int_cyan__cover_wall": {**L.MATERIALS["int_cyan"], "base": (0.12, 0.02, 0.01, 1.0), "emission": (1.0, 0.12, 0.04),
                             "strength": 0.35, "metallic": 0.5, "roughness": 0.45},
})


def _r(sag: float) -> float:
    return (CHORD ** 2 / 4 + sag ** 2) / (2 * sag)


R_O, R_I = _r(SAG_O), _r(SAG_I)                         # the arcs' radii (0.750, 5.16)
CX_O, CX_I = U_CHORD + R_O - SAG_O, U_CHORD + R_I - SAG_I   # their centres' u (both at T_MID)


def arc_u(cx: float, r: float, t: float) -> float:
    """The u of the arc (centre (cx, T_MID), radius r) at height t, on the mouth's side of the centre."""
    return cx - math.sqrt(max(0.0, r * r - (t - T_MID) ** 2))


def outer(t: float) -> float:
    return arc_u(CX_O, R_O, t)


def inner(t: float) -> float:
    return arc_u(CX_I, R_I, t)


def _span(width, lo: float, limit: float) -> float:
    """The t from the middle where width(t) falls to `limit` (bisection; width shrinks toward the tips)."""
    a, b = 0.0, CHORD / 2
    for _ in range(60):
        m = (a + b) / 2
        a, b = (m, b) if width(T_MID + m) > limit else (a, m)
    return a


HALF = _span(lambda t: inner(t) - outer(t), 0.0, TIP)                                        # the plate's half height
HOLE_L = lambda t: arc_u(CX_O, R_O - INSET, t)                                             # noqa: E731
HOLE_R = lambda t: inner(t) + EDGE_GAP * max(0.0, 1.0 - ((t - T_MID) / HALF) ** 2) - 0.004 * ((t - T_MID) / HALF) ** 2   # noqa: E731
# (the gap past the open edge tapers to nothing at the tips, and the hole tucks 4 mm under the plate there: no
# dark sliver beside the tips, where the shell rests on the wall)
HOLE_HALF = _span(lambda t: HOLE_R(t) - HOLE_L(t), 0.0, 0.012)


def numbers() -> dict:
    return {"k": K, "s_mid": S_MID, "t_mid": T_MID, "chord": CHORD, "width": WIDTH, "half": HALF,
            "axis": (AXIS_U, AXIS_W), "pocket_d": POCKET_D, "hole_half": HOLE_HALF, "max_deg": MAX_DEG}


def back_w(a: float, v: float) -> float:
    """The plate's back off the wall at across a (0 outer edge .. 1 open edge) and v (-1 .. 1 tip to tip)."""
    taper = max(0.0, 1.0 - v * v) ** 0.6
    return W_REST + taper * (BULGE * math.sin(math.pi * min(a, 1.0) ** 0.9) * (1.0 - 0.25 * a) + LIP * a ** 2)


def plate_grid() -> list[list[tuple[float, float, float, float]]]:
    """Rows along the chord of (u, t, w_back, w_front) across the plate (cosine rows: dense at the tips)."""
    rows = []
    for i in range(ROWS + 1):
        t = T_MID - HALF * math.cos(math.pi * i / ROWS)
        v = (t - T_MID) / (CHORD / 2)
        uo, ui = outer(t), inner(t)
        row = []
        for j in range(COLS + 1):
            a = j / COLS
            wb = back_w(a, v)
            row.append((uo + (ui - uo) * a, t, wb, wb + THICK))
        rows.append(row)
    return rows


def _grid_solid(rows, pt) -> tuple[list, list]:
    """A closed shell from rows of (u, t, w_back, w_front): front, back, the four sides."""
    nr, nc = len(rows), len(rows[0])
    verts = [pt(u, t, wf) for row in rows for (u, t, _wb, wf) in row] + \
            [pt(u, t, wb) for row in rows for (u, t, wb, _wf) in row]
    off = nr * nc
    f = lambda i, j: i * nc + j                                                            # noqa: E731
    faces = []
    for i in range(nr - 1):
        for j in range(nc - 1):
            faces.append((f(i, j), f(i, j + 1), f(i + 1, j + 1), f(i + 1, j)))
            faces.append((off + f(i, j), off + f(i + 1, j), off + f(i + 1, j + 1), off + f(i, j + 1)))
    ring = [f(0, j) for j in range(nc)] + [f(i, nc - 1) for i in range(1, nr)] + \
           [f(nr - 1, j) for j in range(nc - 2, -1, -1)] + [f(i, 0) for i in range(nr - 2, 0, -1)]
    for a, b in zip(ring, ring[1:] + ring[:1]):
        faces.append((a, off + a, off + b, b))
    return verts, faces


def _cylinder(pt, u: float, w: float, r: float, t0: float, t1: float, n: int = 16) -> tuple[list, list]:
    verts = [pt(u + r * math.cos(2 * math.pi * k / n), t, w + r * math.sin(2 * math.pi * k / n))
             for t in (t0, t1) for k in range(n)]
    faces = [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
    faces += [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
    return verts, faces


def _box(pt, u0, u1, t0, t1, w0, w1) -> tuple[list, list]:
    v = [pt(u, t, w) for t in (t0, t1) for w in (w0, w1) for u in (u0, u1)]
    return v, [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]


def hole_rows(n: int = 40) -> list[tuple[float, float, float]]:
    """The pocket's outline as rows (t, u_left, u_right), cosine-spaced, bottom to top."""
    return [(t, HOLE_L(t), HOLE_R(t))
            for t in (T_MID - HOLE_HALF * math.cos(math.pi * i / n) for i in range(n + 1))]


def band_with_hole(pt, u0: float, u1: float, t0: float, t1: float) -> tuple[list, list]:
    """The wall's flat band (u0..u1, t0..t1 at w 0) with the pocket's hole, as quads counter-clockwise from the room."""
    rows = hole_rows()
    quads = []
    (ta, la, ra), (tb, lb, rb) = rows[0], rows[-1]
    for lo, hi in ((t0, ta), (tb, t1)):
        l_, r_ = (la, ra) if hi == ta else (lb, rb)
        for x0, x1 in ((u0, l_), (l_, r_), (r_, u1)):
            quads.append([(x0, lo), (x1, lo), (x1, hi), (x0, hi)])
    for (ta_, la_, ra_), (tb_, lb_, rb_) in zip(rows, rows[1:]):
        quads.append([(u0, ta_), (la_, ta_), (lb_, tb_), (u0, tb_)])
        quads.append([(ra_, ta_), (u1, ta_), (u1, tb_), (rb_, tb_)])
    verts, faces = [], []
    for q in quads:
        faces.append(tuple(range(len(verts), len(verts) + 4)))
        verts += [pt(u, t, 0.0) for u, t in q]
    return verts, faces


def pocket(pt) -> tuple[tuple[list, list], tuple[list, list]]:
    """The pocket's walls (facing in) and its floor (facing out), from the hole's outline."""
    rows = hole_rows()
    loop = [(r[2], r[0]) for r in rows] + [(r[1], r[0]) for r in rows[::-1]]   # right side up, left side down: CCW
    loop = [(rows[0][1], rows[0][0])] + loop[:-1]                                # from the bottom-left corner
    wv, wf = [], []
    for (u_a, t_a), (u_b, t_b) in zip(loop, loop[1:] + loop[:1]):
        n = len(wv)
        wv += [pt(u_a, t_a, 0.0), pt(u_b, t_b, 0.0), pt(u_b, t_b, -POCKET_D), pt(u_a, t_a, -POCKET_D)]
        wf.append((n, n + 1, n + 2, n + 3))
    fv, ff = [], []
    for (ta, la, ra), (tb, lb, rb) in zip(rows, rows[1:]):
        n = len(fv)
        fv += [pt(la, ta, -POCKET_D), pt(ra, ta, -POCKET_D), pt(rb, tb, -POCKET_D), pt(lb, tb, -POCKET_D)]
        ff.append((n, n + 1, n + 2, n + 3))
    return (wv, wf), (fv, ff)


def cover_parts(pt) -> list[dict]:
    """The cover's parts in the east wall's frame (pt: ship_interior_throat.point)."""
    rows = plate_grid()
    plate = _grid_solid(rows, pt)
    rim_v, rim_f = [], []
    for (ua, ta, wba, wfa), (ub, tb, wbb, wfb) in zip([r[-1] for r in rows], [r[-1] for r in rows[1:]]):
        n = len(rim_v)   # the open edge's face, a hair out along +u: faces the hall
        rim_v += [pt(ua + RIM_OUT, ta, wba), pt(ub + RIM_OUT, tb, wbb), pt(ub + RIM_OUT, tb, wfb),
                  pt(ua + RIM_OUT, ta, wfa)]
        rim_f.append((n, n + 1, n + 2, n + 3))
    band = []   # and a RIM_W band on the plate's front along the open edge, a hair out: the line seen from the front
    for row in rows:
        u1, t, _wb, wf1 = row[-1]
        width = u1 - row[0][0]
        a0 = max(0.5, 1.0 - RIM_W / max(width, 1e-6))
        v = (t - T_MID) / (CHORD / 2)
        band.append(((row[0][0] + width * a0, t, back_w(a0, v) + THICK + RIM_OUT), (u1, t, wf1 + RIM_OUT)))
    for (pa, qa), (pb, qb) in zip(band, band[1:]):
        n = len(rim_v)
        rim_v += [pt(*pa), pt(*qa), pt(*qb), pt(*pb)]
        rim_f.append((n, n + 1, n + 2, n + 3))
    knuckle = _cylinder(pt, AXIS_U, AXIS_W, KNUCKLE_R, T_MID + KNUCKLE_MID[0], T_MID + KNUCKLE_MID[1])
    # the plate's knuckle leaf: a short strap from the knuckle onto the plate's edge (under the plate's front)
    strap = _box(pt, AXIS_U, AXIS_U + 0.022, T_MID + KNUCKLE_MID[0] + 0.004, T_MID + KNUCKLE_MID[1] - 0.004,
                 AXIS_W - 0.004, AXIS_W + 0.003)
    hinge = []
    for lo, hi in KNUCKLE_FIX:
        hinge.append(_cylinder(pt, AXIS_U, AXIS_W, KNUCKLE_R, T_MID + lo, T_MID + hi))
        hinge.append(_box(pt, AXIS_U - TAB_W, AXIS_U, T_MID + lo + 0.006, T_MID + hi - 0.006, 0.0005, 0.005))
    walls, floor = pocket(pt)
    origin = pt(AXIS_U, T_MID, AXIS_W)
    pre = f"cover{K}_"
    out = [{**P(pre + "plate", S.M(plate), PLATE_MAT), "origin": origin, "smooth_deg": 50},
           {**P(pre + "rim", (rim_v, rim_f), RIM_MAT), "origin": origin},
           {**P(pre + "knuckle", S.M(knuckle, strap), HINGE_MAT), "origin": origin, "smooth_deg": 50},
           {**P(pre + "hinge", S.M(*hinge), HINGE_MAT), "smooth_deg": 50},
           P(pre + "pocket", walls, WALL_MAT), P(pre + "glow", floor, GLOW_MAT)]
    for p in out:
        p["solid"] = p["name"].endswith(("plate", "knuckle", "hinge"))
    return out


def turn(p: tuple[float, float, float], deg: float) -> tuple[float, float, float]:
    """A plate point (u, t, w) turned `deg` outward about the hinge axis (the open edge out of the wall)."""
    u, t, w = p
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    du, dw = u - AXIS_U, w - AXIS_W
    return AXIS_U + du * c - dw * s, t, AXIS_W + du * s + dw * c
