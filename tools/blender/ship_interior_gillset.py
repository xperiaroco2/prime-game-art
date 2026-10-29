"""The throat's gill set (art #263, 2026-10-29; the engineer's pick, prime-game-design
ideas/ship-components/slits-lamps/set_plate.jpg; docs/ship.md "The gill set"): on the east throat wall, five static
crescent niches that glow (red shut, cyan open), a curved bevelled groove with a thin cyan glow round the set's mouth
side (a fish's gill cover edge), a short light bar above each slit (the turn indicator) and the round button at the
hall end. NOTHING MOVES: the game only recolours the glows (godot/ship/gill_set.gd), puffs steam and holds a cloud.

Each slit is a crescent between two arcs through its tips, both bulging toward the mouth (the picture's): the outer
arc sags SAG_O x chord / 1.2 from the tips' line, the inner SAG_I x chord / 1.2. Its tips stand `chord` apart up the
wall; the crescent leans back (top toward the hall) by `lean` degrees as a shear. The mouth-side slit is the tallest
(1.18 m), each next one shorter (0.80 m at slot 5), the bottoms rising gently (0.80 -> 0.84), all under the fold.
`SLOTS[k]` is the crescent's middle in s (the old slots, 37 cm apart): its tips' line sits SAG_O/2 toward the hall of it.

The niche is a smooth scoop cut into the band (its hole one column per slit, plain quads between): depth DEPTH in the
middle, easing to nothing at the hole's edges and tips. Across it, three glowing parts: `scoop` (the mouth-side half,
dimmer), `glow` (the middle) and `edge` (the inner, hall-side lip: the bright line). Every part is decor ("nocol").

Parts (Godot `gill<k>_<part>`, k = 1..5 from the mouth): `scoop`, `glow`, `edge`, `bar` (the bevelled frame of the
wall's metal), `bar_glow`; and `groove`, `groove_glow`, `btn_bezel`, `btn_ring`, `btn_dome`. The glows' GLB colour is
the shut red (bars red, groove and button cyan); the game drives them.

Frame: the wall's (ship_interior_throat.point): u = s along the wall from the mouth's corner, t up from the deck, w out
of the wall into the throat. Plain Python (ship_build.py makes the meshes)."""

from __future__ import annotations

import math

import ship_interior as S
import ship_lib as L

P = S.P

# k: (middle s, bottom t, chord (tip to tip, vertical), lean deg (top toward the hall))
SLITS = {1: (1.95, 0.80, 1.18, 3.0), 2: (2.32, 0.81, 1.08, 4.0), 3: (2.69, 0.82, 0.98, 5.0),
         4: (3.06, 0.83, 0.89, 6.0), 5: (3.43, 0.84, 0.80, 7.0)}
SLOTS = {k: v[0] for k, v in SLITS.items()}
SAG_O, SAG_I = 0.26, 0.11                       # per 1.20 m of chord: the outer and inner arcs' sag toward the mouth
TIP = 0.012                                     # the tips cut where the crescent is this wide
DEPTH = 0.065                                   # the scoop's depth at its middle
MARGIN = 0.03                                   # each slit's band column past its hole
ACROSS = (0.0, 0.08, 0.2, 0.34, 0.5, 0.62, 0.74, 0.84, 0.92, 0.97, 1.0)   # the scoop's columns (0 mouth side .. 1 inner)
SPLIT = (4, 8)                                  # scoop | glow | edge at ACROSS[4] and ACROSS[8]
FOLD_T = 2.086                                  # the band's top (ship_interior_throat: FOLD - GAP_H)
BAR_UP = 0.06                                   # the bar's middle over its slit's top tip
BAR_GLOW = (0.14, 0.03)                        # the bar's light strip (w x h)
BAR_FRAME = (0.18, 0.06)                       # its frame's outside
BAR_PROUD, BAR_BEVEL, BAR_SINK = 0.004, 0.003, 0.002   # the frame's face off the wall, its outer bevel; the strip's w
BUTTON = (3.73, 1.15)                           # the round button's centre (s, t), the hall end (the picture's)
BTN_DOME_R, BTN_DOME_UP = 0.048, 0.026
BTN_RING = (0.048, 0.068)
BTN_BEZEL = 0.088                               # the octagonal bezel's outer corner radius
BTN_W = 0.006
# the groove's centre line: a cubic Bezier from its top end (left of bar 1, under the fold) round the mouth side of
# slit 1 to its tail under slits 1-2 (the picture's sweep); GROOVE_HW the half width (lips), GROOVE_G the glow's
GROOVE = ((1.93, 2.055), (1.66, 1.95), (1.56, 0.40), (2.50, 0.68))   # (a grid search: 5 cm clear of the holes)
GROOVE_HW, GROOVE_BEVEL, GROOVE_G = 0.016, 0.006, 0.004
GROOVE_PROUD, GROOVE_SINK = 0.004, 0.0015       # the lips' top, the glow strip's w
GROOVE_N = 96
RED, CYAN = (1.0, 0.12, 0.04), (0.1, 0.85, 1.0)

L.MATERIALS.update({
    "int_cyan__gset_glow": {**L.MATERIALS["int_cyan"], "base": (0.3, 0.04, 0.02, 1.0), "emission": RED, "strength": 1.4},
    "int_cyan__gset_scoop": {**L.MATERIALS["int_cyan"], "base": (0.12, 0.02, 0.01, 1.0), "emission": RED,
                             "strength": 0.5, "metallic": 0.5, "roughness": 0.4},
    "int_cyan__gset_edge": {**L.MATERIALS["int_cyan"], "base": (1.0, 0.12, 0.04, 1.0), "emission": RED, "strength": 3.0},
    "int_cyan__gset_bar": {**L.MATERIALS["int_cyan"], "base": (1.0, 0.12, 0.04, 1.0), "emission": RED, "strength": 2.6},
    "int_cyan__gset_groove": {**L.MATERIALS["int_cyan"], "base": (0.1, 0.85, 1.0, 1.0), "emission": CYAN,
                              "strength": 2.2},
    "int_cyan__cover_btn": {**L.MATERIALS["int_cyan"], "base": (0.1, 0.85, 1.0, 1.0), "emission": CYAN, "strength": 2.4},
    "int_dark__cover_btn": {**L.MATERIALS["int_dark"], "base": (0.035, 0.04, 0.045, 1.0), "metallic": 0.6,
                            "roughness": 0.38},
})
METAL = "int_silver_b"                          # the bar frames, the groove's lips and the bezel: the band's metal


class Slit:
    """Slit k's crescent: outline(t) -> (u_left, u_right), rows, the tips."""

    def __init__(self, k: int):
        self.k = k
        self.s_mid, self.bottom, self.chord, self.lean = SLITS[k]
        self.top = self.bottom + self.chord
        self.t_mid = self.bottom + self.chord / 2
        f = self.chord / 1.2
        self.sag_o, self.sag_i = SAG_O * f, SAG_I * f
        self.u_chord = self.s_mid + self.sag_o / 2          # the tips' line at the middle height
        self.shear = math.tan(math.radians(self.lean))
        self.r_o, self.r_i = self._r(self.sag_o), self._r(self.sag_i)
        a, b = 0.0, self.chord / 2                           # the half height where the crescent is TIP wide
        for _ in range(60):
            m = (a + b) / 2
            a, b = (m, b) if self._width(self.t_mid + m) > TIP else (a, m)
        self.half = a

    def _r(self, sag: float) -> float:
        return (self.chord ** 2 / 4 + sag ** 2) / (2 * sag)

    def _arc(self, r: float, sag: float, t: float) -> float:
        cx = self.u_chord + r - sag
        return cx - math.sqrt(max(0.0, r * r - (t - self.t_mid) ** 2))

    def _width(self, t: float) -> float:
        return self._arc(self.r_i, self.sag_i, t) - self._arc(self.r_o, self.sag_o, t)

    def outline(self, t: float) -> tuple[float, float]:
        d = (t - self.t_mid) * self.shear
        return self._arc(self.r_o, self.sag_o, t) + d, self._arc(self.r_i, self.sag_i, t) + d

    def rows(self, n: int = 48) -> list[tuple[float, float, float]]:
        """(t, u_left, u_right) bottom to top, cosine-spaced (dense at the tips)."""
        out = []
        for i in range(n + 1):
            t = self.t_mid - self.half * math.cos(math.pi * i / n)
            out.append((t, *self.outline(t)))
        return out

    def extent(self) -> tuple[float, float]:
        us = [u for _t, a, b in self.rows() for u in (a, b)]
        return min(us), max(us)

    def column(self) -> tuple[float, float]:
        lo, hi = self.extent()
        return lo - MARGIN, hi + MARGIN

    def tips(self) -> tuple[tuple[float, float], tuple[float, float]]:
        r = self.rows()
        return (r[0][1], r[0][0]), (r[-1][2], r[-1][0])

    def bar(self) -> tuple[float, float]:
        """The bar's middle (u, t): over the top tip, a little toward the slit's middle."""
        (_ub, _tb), (ut, tt) = self.tips()
        return ut - 0.03, self.top + BAR_UP

    def depth(self, t: float, a: float) -> float:
        v = (t - self.t_mid) / self.half
        return DEPTH * max(0.0, 1.0 - v * v) ** 0.5 * math.sin(math.pi * a) ** 0.45


def slits() -> list[Slit]:
    return [Slit(k) for k in SLITS]


def numbers() -> list[dict]:
    """The as-built table: per slit its middle s, bottom/top t, chord, lean, sags and its bar's middle."""
    out = []
    for sl in slits():
        lo, hi = sl.extent()
        out.append({"k": sl.k, "s_mid": sl.s_mid, "bottom": round(sl.t_mid - sl.half, 3),
                    "top": round(sl.t_mid + sl.half, 3), "chord": sl.chord, "lean": sl.lean,
                    "u": (round(lo, 3), round(hi, 3)), "width": round(sl.sag_o - sl.sag_i, 3),
                    "bar": tuple(round(v, 3) for v in sl.bar())})
    return out


def _band_column(pt, sl: Slit, t0: float, t1: float) -> tuple[list, list]:
    """Slit sl's band column (its column's u, t0..t1 at w 0) with its hole, quads facing the room."""
    u0, u1 = sl.column()
    rows = sl.rows()
    quads = []
    (ta, la, ra), (tb, lb, rb) = rows[0], rows[-1]
    for lo, hi, l_, r_ in ((t0, ta, la, ra), (tb, t1, lb, rb)):
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


def band(pt, u0: float, u1: float, t0: float, t1: float) -> tuple[list, list]:
    """The band u0..u1 with every slit's hole (one column each, plain quads between)."""
    verts, faces = [], []

    def add(vf):
        n = len(verts)
        verts.extend(vf[0])
        faces.extend(tuple(i + n for i in f) for f in vf[1])

    a = u0
    for sl in slits():
        lo, hi = sl.column()
        if lo > a + 1e-9:
            add(([pt(a, t0), pt(lo, t0), pt(lo, t1), pt(a, t1)], [(0, 1, 2, 3)]))
        add(_band_column(pt, sl, t0, t1))
        a = hi
    if u1 > a + 1e-9:
        add(([pt(a, t0), pt(u1, t0), pt(u1, t1), pt(a, t1)], [(0, 1, 2, 3)]))
    return verts, faces


def scoop(pt, sl: Slit) -> dict[str, tuple[list, list]]:
    """The niche's surface (facing out of the wall), split across into scoop | glow | edge."""
    rows = sl.rows()
    grid = [[(ul + (ur - ul) * a, t, -sl.depth(t, a)) for a in ACROSS] for t, ul, ur in rows]
    out = {}
    for name, (j0, j1) in (("scoop", (0, SPLIT[0])), ("glow", SPLIT), ("edge", (SPLIT[1], len(ACROSS) - 1))):
        verts, faces = [], []
        for ra, rb in zip(grid, grid[1:]):
            for j in range(j0, j1):
                n = len(verts)
                verts += [pt(*ra[j]), pt(*ra[j + 1]), pt(*rb[j + 1]), pt(*rb[j])]
                faces.append((n, n + 1, n + 2, n + 3))
        out[name] = (verts, faces)
    return out


def _ring(pt, uc: float, tc: float, outer: tuple[float, float], inner: tuple[float, float], w_o: float,
          w_i: float) -> tuple[list, list]:
    """A rectangular ring band from the outer rect (half sizes) at w_o to the inner at w_i, facing the room."""
    def rect(h, w):
        return [pt(uc - h[0], tc - h[1], w), pt(uc + h[0], tc - h[1], w), pt(uc + h[0], tc + h[1], w),
                pt(uc - h[0], tc + h[1], w)]
    v = rect(outer, w_o) + rect(inner, w_i)
    return v, [(i, (i + 1) % 4, 4 + (i + 1) % 4, 4 + i) for i in range(4)]


def bar_parts(pt, sl: Slit) -> list[dict]:
    """The turn indicator over slit sl: a bevelled frame of the wall's metal (4 mm proud), the strip 2 mm off the
    wall inside it."""
    uc, tc = sl.bar()
    fo = (BAR_FRAME[0] / 2, BAR_FRAME[1] / 2)
    fb = (fo[0] - BAR_BEVEL, fo[1] - BAR_BEVEL)
    gi = (BAR_GLOW[0] / 2, BAR_GLOW[1] / 2)
    frame = S.M(_ring(pt, uc, tc, fo, fb, 0.0, BAR_PROUD), _ring(pt, uc, tc, fb, gi, BAR_PROUD, BAR_PROUD),
                _ring(pt, uc, tc, gi, gi, BAR_PROUD, BAR_SINK))
    glow = ([pt(uc - gi[0], tc - gi[1], BAR_SINK), pt(uc + gi[0], tc - gi[1], BAR_SINK),
             pt(uc + gi[0], tc + gi[1], BAR_SINK), pt(uc - gi[0], tc + gi[1], BAR_SINK)], [(0, 1, 2, 3)])
    return [P(f"gill{sl.k}_bar", frame, METAL), P(f"gill{sl.k}_bar_glow", glow, "int_cyan__gset_bar")]


def groove_line(n: int = GROOVE_N) -> list[tuple[float, float, float, float, float]]:
    """(u, t, nu, nt, taper) along the groove: points, the unit normal in the wall (toward the slits' side) and the
    width factor (tapering to nothing over each end's 12 %)."""
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = GROOVE
    out = []
    for i in range(n + 1):
        s = i / n
        a, b, c, d = (1 - s) ** 3, 3 * (1 - s) ** 2 * s, 3 * (1 - s) * s * s, s ** 3
        u, t = a * x0 + b * x1 + c * x2 + d * x3, a * y0 + b * y1 + c * y2 + d * y3
        du = 3 * (1 - s) ** 2 * (x1 - x0) + 6 * (1 - s) * s * (x2 - x1) + 3 * s * s * (x3 - x2)
        dt = 3 * (1 - s) ** 2 * (y1 - y0) + 6 * (1 - s) * s * (y2 - y1) + 3 * s * s * (y3 - y2)
        m = math.hypot(du, dt)
        taper = min(1.0, s / 0.12, (1 - s) / 0.12)
        out.append((u, t, dt / m, -du / m, max(0.0, taper) ** 0.6))
    return out


def groove_parts(pt) -> list[dict]:
    """The groove: two bevelled lips (GROOVE_PROUD) with a channel between them, its floor the thin glow strip."""
    line = groove_line()
    prof = [(-1.0, 0.0), (-1.0 + GROOVE_BEVEL / GROOVE_HW, GROOVE_PROUD), (-GROOVE_G / GROOVE_HW, GROOVE_PROUD),
            (-GROOVE_G / GROOVE_HW, GROOVE_SINK), (GROOVE_G / GROOVE_HW, GROOVE_SINK), (GROOVE_G / GROOVE_HW, GROOVE_PROUD),
            (1.0 - GROOVE_BEVEL / GROOVE_HW, GROOVE_PROUD), (1.0, 0.0)]
    pts = [[pt(u + nu * x * GROOVE_HW * k, t + nt * x * GROOVE_HW * k, w) for x, w in prof] for u, t, nu, nt, k in line]
    metal, glow = ([], []), ([], [])
    for ra, rb in zip(pts, pts[1:]):
        for j in range(len(prof) - 1):
            dst = glow if j == 3 else metal
            n = len(dst[0])
            dst[0].extend([ra[j + 1], ra[j], rb[j], rb[j + 1]])
            dst[1].append((n, n + 1, n + 2, n + 3))
    return [{**P("groove", metal, METAL), "smooth_deg": 35}, P("groove_glow", glow, "int_cyan__gset_groove")]


def _disc_rows(pt, us: float, ts: float, rings: list[tuple[float, float]], n: int = 48, rot: float = 0.0):
    verts, faces = [], []
    for r, w in rings:
        verts += [pt(us + r * math.cos(2 * math.pi * i / n + rot), ts + r * math.sin(2 * math.pi * i / n + rot), w)
                  for i in range(n)]
    for j in range(len(rings) - 1):
        a, b = j * n, (j + 1) * n
        faces += [(a + i, a + (i + 1) % n, b + (i + 1) % n, b + i) for i in range(n)]
    return verts, faces


def button(pt) -> list[dict]:
    """The round button (the picture's): an octagonal bezel of the wall's metal, a cyan ring, a dark dome."""
    us, ts = BUTTON
    r0, r1 = BTN_RING
    oct8 = math.pi / 8
    bezel = _disc_rows(pt, us, ts, [(BTN_BEZEL, 0.0), (BTN_BEZEL, BTN_W * 0.6), (BTN_BEZEL - 0.005, BTN_W),
                                    (r1 / math.cos(oct8), BTN_W), (r1 / math.cos(oct8), 0.0)], n=8, rot=oct8)
    ring = _disc_rows(pt, us, ts, [(r1 + 0.002, BTN_W + 0.0006), (r0, BTN_W + 0.0006)])
    rho = (BTN_DOME_R ** 2 + BTN_DOME_UP ** 2) / (2 * BTN_DOME_UP)
    dome = [(BTN_DOME_R, BTN_W - 0.004), (BTN_DOME_R, BTN_W)]
    for i in range(1, 10):
        r = BTN_DOME_R * (1 - i / 10)
        dome.append((r, BTN_W + BTN_DOME_UP - rho + math.sqrt(rho ** 2 - r ** 2)))
    dv, df = _disc_rows(pt, us, ts, dome)
    n, top = 48, len(dv) - 48
    dv.append(pt(us, ts, BTN_W + BTN_DOME_UP))
    df += [(top + i, top + (i + 1) % n, len(dv) - 1) for i in range(n)]
    return [P("btn_bezel", bezel, METAL), P("btn_ring", ring, "int_cyan__cover_btn"),
            {**P("btn_dome", (dv, df), "int_dark__cover_btn"), "smooth_deg": 60}]


def parts(pt) -> list[dict]:
    """Every gill-set part in the east wall's frame (pt: ship_interior_throat.point); all decor (no colliders)."""
    out = []
    for sl in slits():
        sc = scoop(pt, sl)
        out += [{**P(f"gill{sl.k}_{name}", sc[name], f"int_cyan__gset_{name}"), "smooth_deg": 70}
                for name in ("scoop", "glow", "edge")]
        out += bar_parts(pt, sl)
    out += groove_parts(pt) + button(pt)
    for p in out:
        p["solid"], p["nocol"] = False, True
    return out


def clearances() -> dict:
    """The checks' numbers: the groove's least distance (centre line, less its half width) to any slit hole, the
    least gap between neighbouring columns, the button bezel's gap to slit 5's hole and to the jamb (s 3.88)."""
    holes = [(sl, sl.rows(96)) for sl in slits()]

    def hole_dist(u, t):
        best = 9.0
        for sl, rows in holes:
            for (ta, la, ra) in rows:
                for uu in (la, ra):
                    best = min(best, math.hypot(u - uu, t - ta))
            if rows[0][0] <= t <= rows[-1][0]:
                ul, ur = sl.outline(t)
                if ul <= u <= ur:
                    return -1.0
        return best
    g = min(hole_dist(u, t) - GROOVE_HW * k for u, t, _a, _b, k in groove_line())
    cols = [sl.column() for sl in slits()]
    lo5, hi5 = slits()[-1].extent()
    return {"groove_hole": g, "column_gap": min(b[0] - a[1] for a, b in zip(cols, cols[1:])),
            "button_hole": BUTTON[0] - BTN_BEZEL - hi5, "button_jamb": 3.88 - BUTTON[0] - BTN_BEZEL,
            "groove_u_min": min(u - GROOVE_HW * k for u, _t, _a, _b, k in groove_line()),
            "groove_t_min": min(t - GROOVE_HW * k for _u, t, _a, _b, k in groove_line()),
            "groove_t_max": max(t + GROOVE_HW * k for _u, t, _a, _b, k in groove_line())}
