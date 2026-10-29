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
SLITS = {1: (2.074, 0.82, 1.08, 3.0), 2: (2.438, 0.83, 0.99, 4.0), 3: (2.801, 0.84, 0.9, 5.0),
         4: (3.164, 0.85, 0.82, 6.0), 5: (3.526, 0.86, 0.74, 7.0)}
SLOTS = {k: v[0] for k, v in SLITS.items()}
SAG_O, SAG_I = 0.40, 0.156                      # per 1.20 m of chord (step 4, "more open": 0.26, 0.11 before)
TIP = 0.012                                     # the tips cut where the crescent is this wide
DEPTH = 0.15                                    # step 4: a real cut, 15 cm at its middle (6.5 cm before)
RIM_N = 32                                      # each slit's own rows (the band's strips: every slit's together)
# step 4 ("cut out of the wall, real gills"): the cut's section across, (a, depth fraction) from the mouth-side rim
# (a 0) to the hall-side rim (a 1): a 45 deg-ish bevelled lip, the thin glowing rim at its foot, the inner wall falling
# into shadow, the floor, then UNDER the hall-side rim (a > 1: UNDER m past it at the middle) the back wall and the
# overhang's underside back up to the rim, so the hall-side edge overhangs and shades the floor
PROFILE = ((0.0, 0.0), (0.04, 0.07), (0.08, 0.15), (0.11, 0.2), (0.16, 0.27), (0.22, 0.6), (0.3, 0.88), (0.42, 1.0),
           (0.6, 1.0), (0.8, 1.0), (1.0, 1.0), (1.5, 0.92), (1.9, 0.7), (1.9, 0.4), (1.45, 0.16), (1.0, 0.0))
UNDER = 0.05                                    # the overhang's reach past the hall-side rim at a 2 (scaled by the tips)
PARTS = {"lip": (0, 3), "edge": (3, 4), "glow": (4, 6), "scoop": (6, len(PROFILE) - 1)}   # PROFILE's column runs
FOLD_T = 2.086                                  # the band's top (ship_interior_throat: FOLD - GAP_H)
BAR_UP = 0.06                                   # the bar's middle over its slit's top tip
BAR_GLOW = (0.12, 0.014)                       # step 4: the bar's light strip (w x h; 14 x 3 cm before, "too wide")
BAR_FRAME = (0.14, 0.03)                       # its slim frame's outside (18 x 6 cm before)
BAR_PROUD, BAR_BEVEL, BAR_SINK = 0.004, 0.002, 0.002   # the frame's face off the wall, its outer bevel; the strip's w
END_U = 3.98                                    # step 4: the wall's hall-end frame (the jamb removed)
BUTTON = (3.86, 1.15)                           # the round button's centre (s, t), the hall end (the picture's)
BTN_DOME_R, BTN_DOME_UP = 0.06, 0.03            # step 4: the dark dome bigger (r 0.05 before)
BTN_RING = (0.06, 0.072)                        # the glowing ring, 1.2 cm thin (2.8 cm before: "too fat")
BTN_BEZEL = 0.11                                # the octagonal bezel's outer corner radius
BTN_W = 0.009                                   # the bezel's face off the wall (a 9 mm 45 deg outer bevel)
BTN_IN = (0.006, 0.004)                         # its round inner bevel down to the ring: across, down
BTN_RING_W = BTN_W - BTN_IN[1] + 0.0006         # the ring's face (just over the inner bevel's foot)
# the groove's centre line: a cubic Bezier from its top end (left of bar 1, under the fold) round the mouth side of
# slit 1 to its tail under slits 1-2 (the picture's sweep); GROOVE_HW the half width (lips), GROOVE_G the glow's
GROOVE = ((2.07, 2.042), (1.869, 1.789), (1.737, 1.564), (1.737, 1.348),
          (1.737, 0.754), (2.241, 0.649), (2.673, 0.638))   # step 4: traced from the picture
GROOVE_HW, GROOVE_BEVEL, GROOVE_G = 0.017, 0.005, 0.0075   # step 2: the glow 15 mm (was 8)
GROOVE_PROUD, GROOVE_SINK = 0.004, 0.0015       # the lips' top, the glow strip's w
GROOVE_N = 72
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
# the cut's parts in the GLB (what --play shows without gill_set.gd): the lip the wall's metal, the fall and the floor
# dark, only the rim glowing the shut red
NICHE_MAT = {"lip": METAL, "edge": "int_cyan__gset_edge", "glow": "int_dark__cover_btn", "scoop": "int_dark__cover_btn"}


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

    def rows(self, n: int = 32) -> list[tuple[float, float, float]]:
        """(t, u_left, u_right) bottom to top, cosine-spaced (dense at the tips)."""
        out = []
        for i in range(n + 1):
            t = self.t_mid - self.half * math.cos(math.pi * i / n)
            out.append((t, *self.outline(t)))
        return out

    def extent(self) -> tuple[float, float]:
        us = [u for _t, a, b in self.rows() for u in (a, b)]
        return min(us), max(us)

    def rim(self, levels: list[float]) -> list[tuple[float, float, float]]:
        """(t, u_left, u_right) at every level inside this slit's span (its own rows are among them)."""
        lo, hi = self.t_mid - self.half - 1e-7, self.t_mid + self.half + 1e-7
        return [(t, *self.outline(t)) for t in levels if lo <= t <= hi]

    def tips(self) -> tuple[tuple[float, float], tuple[float, float]]:
        r = self.rows()
        return (r[0][1], r[0][0]), (r[-1][2], r[-1][0])

    def bar(self) -> tuple[float, float]:
        """The bar's middle (u, t): over the top tip, a little toward the slit's middle."""
        (_ub, _tb), (ut, tt) = self.tips()
        return ut - 0.03, self.top + BAR_UP

    def section(self, t: float, ul: float, ur: float) -> list[tuple[float, float, float]]:
        """PROFILE at height t between the rims ul..ur: (u, t, w) per column, its depth and overhang easing to
        nothing at the tips (sqrt(1 - v^2)), so the tips stay sharp."""
        v = (t - self.t_mid) / self.half
        env = max(0.0, 1.0 - v * v) ** 0.5
        out = []
        for a, f in PROFILE:
            u = ul + (ur - ul) * a if a <= 1.0 else ur + (a - 1.0) * UNDER * env
            out.append((u, t, -DEPTH * f * env))
        return out


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


def rim_levels() -> list[float]:
    """Every slit's row heights (step 4: the fatter crescents nest, so the band is cut in horizontal strips at every
    level where any slit has a rim vertex; each slit's rim then holds them all inside its span: no T-junctions)."""
    return sorted({round(t, 9) for sl in slits() for t, _a, _b in sl.rows(RIM_N)})


def band(pt, u0: float, u1: float, t0: float, t1: float) -> tuple[list, list]:
    """The band u0..u1, t0..t1 with every slit's hole: one strip per pair of rim levels, a face per solid gap
    between the holes crossing it (its edges carry the tips of holes that end on the strip's lines)."""
    levels = rim_levels()
    rims = {sl.k: {t: (a, b) for t, a, b in sl.rim(levels)} for sl in slits()}
    span = {k: (min(r), max(r)) for k, r in rims.items()}
    verts, faces = [], []
    for ta, tb in zip(*(lambda lv: (lv, lv[1:]))(sorted({t0, t1, *levels}))):
        act = sorted((k for k in rims if span[k][0] <= ta and span[k][1] >= tb), key=lambda k: rims[k][ta][0])
        lefts = [(u0, u0)] + [(rims[k][ta][1], rims[k][tb][1]) for k in act]
        rights = [(rims[k][ta][0], rims[k][tb][0]) for k in act] + [(u1, u1)]
        lo = [u for k in rims if span[k][1] == ta for u in rims[k][ta]]
        hi = [u for k in rims if span[k][0] == tb for u in rims[k][tb]]
        for (la, lb), (ra, rb) in zip(lefts, rights):
            bot = [la] + sorted(u for u in lo if la + 1e-9 < u < ra - 1e-9) + [ra]
            top = [rb] + sorted((u for u in hi if lb + 1e-9 < u < rb - 1e-9), reverse=True) + [lb]
            n = len(verts)
            verts += [pt(u, ta, 0.0) for u in bot] + [pt(u, tb, 0.0) for u in top]
            faces.append(tuple(range(n, len(verts))))
    return verts, faces


def scoop(pt, sl: Slit) -> dict[str, tuple[list, list]]:
    """The cut's surface (facing out of the wall), split across into PARTS: `lip` (the bevel, the wall's metal),
    `edge` (the thin glowing rim), `glow` (the inner wall's fall, a soft glow) and `scoop` (the dark floor, the back
    wall and the overhang's underside)."""
    grid = [sl.section(t, ul, ur) for t, ul, ur in sl.rim(rim_levels())]
    out = {}
    for name, (j0, j1) in PARTS.items():
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


def _cubic(q, s: float) -> tuple[float, float, float, float]:
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = q
    a, b, c, d = (1 - s) ** 3, 3 * (1 - s) ** 2 * s, 3 * (1 - s) * s * s, s ** 3
    du = 3 * (1 - s) ** 2 * (x1 - x0) + 6 * (1 - s) * s * (x2 - x1) + 3 * s * s * (x3 - x2)
    dt = 3 * (1 - s) ** 2 * (y1 - y0) + 6 * (1 - s) * s * (y2 - y1) + 3 * s * s * (y3 - y2)
    return a * x0 + b * x1 + c * x2 + d * x3, a * y0 + b * y1 + c * y2 + d * y3, du, dt


def groove_line(n: int = GROOVE_N) -> list[tuple[float, float, float, float, float]]:
    """(u, t, nu, nt, taper) along the groove (GROOVE's two cubic segments, n steps each): points, the unit normal in
    the wall (toward the slits' side) and the width factor (tapering to nothing over each end's 8 %)."""
    segs = (GROOVE[:4], GROOVE[3:])
    out = []
    for i in range(2 * n + 1):
        j, s = (0, i / n) if i < n else (1, (i - n) / n)
        u, t, du, dt = _cubic(segs[j], s)
        m = math.hypot(du, dt)
        g = i / (2 * n)
        taper = min(1.0, g / 0.08, (1 - g) / 0.08)
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


def _octagon(r: float, a: float) -> float:
    """The radius at angle a of a regular octagon with corner radius r, a corner at a = 0 (and every 45 deg)."""
    oct8 = math.pi / 8
    return r * math.cos(oct8) / math.cos((a % (2 * oct8)) - oct8)


def button(pt) -> list[dict]:
    """The round button (the picture's): an octagonal bezel of the wall's metal (a 45 deg outer bevel to a flat face,
    a round inner bevel down to the ring), a thin cyan ring, a dark dome. The ring runs 1 mm under the inner bevel's
    foot, so no wall shows between them (step 3's slivers at the octagon's inner corners)."""
    us, ts = BUTTON
    r0, r1 = BTN_RING
    n, rot = 48, math.pi / 8                            # 6 rows per octagon edge, corners at rot + k x 45 deg
    rows = [(lambda a: _octagon(BTN_BEZEL, a - rot), 0.0), (lambda a: _octagon(BTN_BEZEL - BTN_W, a - rot), BTN_W),
            (lambda a: r1 + BTN_IN[0], BTN_W), (lambda a: r1, BTN_W - BTN_IN[1])]
    bv, bf = [], []
    for fn, w in rows:
        bv += [pt(us + fn(a) * math.cos(a), ts + fn(a) * math.sin(a), w)
               for a in (2 * math.pi * i / n + rot for i in range(n))]
    for j in range(len(rows) - 1):
        a, b = j * n, (j + 1) * n
        bf += [(a + i, a + (i + 1) % n, b + (i + 1) % n, b + i) for i in range(n)]
    ring = _disc_rows(pt, us, ts, [(r1 + 0.001, BTN_RING_W), (r0, BTN_RING_W)])
    rho = (BTN_DOME_R ** 2 + BTN_DOME_UP ** 2) / (2 * BTN_DOME_UP)
    dome = [(BTN_DOME_R, BTN_RING_W - 0.004), (BTN_DOME_R, BTN_RING_W)]
    for i in range(1, 10):
        r = BTN_DOME_R * (1 - i / 10)
        dome.append((r, BTN_RING_W + BTN_DOME_UP - rho + math.sqrt(rho ** 2 - r ** 2)))
    dv, df = _disc_rows(pt, us, ts, dome)
    top = len(dv) - 48
    dv.append(pt(us, ts, BTN_RING_W + BTN_DOME_UP))
    df += [(top + i, top + (i + 1) % 48, len(dv) - 1) for i in range(48)]
    return [{**P("btn_bezel", (bv, bf), METAL), "smooth_deg": 30}, P("btn_ring", ring, "int_cyan__cover_btn"),
            {**P("btn_dome", (dv, df), "int_dark__cover_btn"), "smooth_deg": 60}]


def parts(pt) -> list[dict]:
    """Every gill-set part in the east wall's frame (pt: ship_interior_throat.point); all decor (no colliders)."""
    out = []
    for sl in slits():
        sc = scoop(pt, sl)
        out += [{**P(f"gill{sl.k}_{name}", sc[name], NICHE_MAT[name]), "smooth_deg": 40} for name in PARTS]
        out += bar_parts(pt, sl)
    out += groove_parts(pt) + button(pt)
    for p in out:
        p["solid"], p["nocol"] = False, True
    return out


def clearances() -> dict:
    """The checks' numbers: the groove's least distance (centre line, less its half width) to any slit hole, the
    least gap between neighbouring holes (they nest), the button bezel's gap to slit 5's hole and to the wall's
    hall-end frame (END_U)."""
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
    rims = [[(u, t) for t, lo, hi in rows for u in (lo, hi)] for _sl, rows in holes]
    gap = min(min(math.dist(p, q) for p in a for q in b) for a, b in zip(rims, rims[1:]))
    lo5, hi5 = slits()[-1].extent()
    return {"groove_hole": g, "hole_gap": gap,
            "button_hole": BUTTON[0] - BTN_BEZEL - hi5, "button_end": END_U - BUTTON[0] - BTN_BEZEL,
            "groove_u_min": min(u - GROOVE_HW * k for u, _t, _a, _b, k in groove_line()),
            "groove_t_min": min(t - GROOVE_HW * k for _u, t, _a, _b, k in groove_line()),
            "groove_t_max": max(t + GROOVE_HW * k for _u, t, _a, _b, k in groove_line())}
