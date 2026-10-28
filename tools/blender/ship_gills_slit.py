"""The gills pilot (art #263): ONE gill slit cut into the hall's back wall, built to answer "can it be beautiful in
Blender" against the concept (<raw>/ship/v5/gills-pilot/concept/fit_hero_close.jpg, fit_strip.jpg). Plain Python,
like ship_interior_gills.py, whose frame and chord it shares: the spot at the origin, u along the wall (+ toward the
vault's door; the west piece mirrors u), v out of the wall into the hall, h over the deck (absolute in the parts).

`station_gills_slit` builds the whole chord (1.638 m, deck to rim) as the wall's own matte metal (int_silver_*):
chamfered plates with 12 mm grooves, the gill column between two cyan seam lines, and in it one slit:
- the slit: an angular crescent, a wide shallow V under a straight hinge line, SLIT_W wide, rising TILT_DEG toward
  the door, its edge chamfered; behind it a cavity CAVITY_D deep (`<id>_cavity`, a closed cup);
- `<id>_lip`: the thick chamfered plate that shuts it, its own node with its origin on the hinge (the straight top
  edge, LIP_HINGE_V into the wall): ship.gd's "turn" swings it open about HINGE_AXIS (OPEN_DEG);
- `<id>_comb`: COMB_N glowing cyan filaments (curved blades) and `<id>_comb_deep`, the cavity's dim cyan back;
- `<id>_fault`: the red-orange seam just behind the shut lip's lower edge (the faulty state);
- `<id>_hand*`: the scanner, a chamfered octagonal recess beside the slit with a three-fingered hand glowing cyan.

`slit_states()` gives ship.py the shots' states (shut, half, open) as ship.gd's "stations" request."""

from __future__ import annotations

import math

import ship_interior as S
import ship_interior_geom as G
import ship_interior_gills as GL
import ship_lib as L

HALF = round(GL.CHORD_HALF, 5)       # the chord's half width (0.81895), the old gills' band
TOP = GL.TOP                         # the rim (3.2)
PLATE_T = 0.03                       # the wall plates' thickness
SEAM = 0.012                         # the groove between two plates
CH = 0.014                           # the plates' front chamfer (pass 2: 8 mm read as no edge at night)
KICK = 0.14                          # the kick plate's top
BAND = 2.30                          # the upper band's seam
COLUMN = (-0.66, 0.30)               # the gill column (u) between its cyan lines (pass 2: wider, as the concept's panel)
LINE_W = 0.004                       # the cyan seam lines' width (in the column's grooves)

SLIT_C = (-0.12, 1.40)               # the slit's middle (u, h over the deck): chest to eye height
SLIT_W = 0.58                        # tip to tip (the brief: 55..60 cm)
SLIT_D = 0.135                       # the opening's depth under the hinge at its deepest
SLIT_LOW = -0.05                     # where the V is deepest (slit-local x; toward the mouth end)
TIP_H = 0.014                        # the blunt tips' end edge
V_POW = 1.7                          # the V's curve: steep at the tips, rounder at the bottom (convex)
V_KNOTS = 7                          # facets a side: an angular crescent, not a smooth arc
TILT_DEG = 6.0                       # rising toward the door
ROW = (0.10, -(SLIT_D + 0.075))      # the slit plate's top and bottom seams from the hinge (tilted like the slit)
SCALE_V = 0.016                      # pass 2: the slit plate leans out like a scale, flush at its top, this proud at its foot
HOLE_CH = 0.010                      # the opening's chamfer
CAVITY_D = 0.10                      # the cavity's back (v)
CUP_T = 0.004
CLEAR = 0.003                        # the lip's clearance in the opening
TOP_CLEAR = 0.010                    # pass 2: over the hinge (the lip's top corners swing up to 9 mm as the visor opens)
GAP = 0.007                          # the shut lip's lower edge over the opening's: the fault seam shows through it
LIP_BACK = (-0.008, -0.022)          # the lip's back face (v) at the hinge and at the V's bottom: thin at its top, so it swings
LIP_FRONT = (round(SCALE_V * ROW[0] / (ROW[0] - ROW[1]), 6), 0.030)   # its face at the hinge (the plate's), at the V's bottom
LIP_CH = 0.006
LIP_TAPER = 0.002                    # the back face inset (clearance when it swings)
LIP_HINGE_V = round((LIP_BACK[0] + LIP_FRONT[0]) / 2, 6)   # the hinge line: the lip's top edge, half its depth
OPEN_DEG = {"shut": 0.0, "half": 30.0, "open": 72.0}   # pass 2: a visor (38 deg hid the comb from eye height)
COMB_N = 27
COMB_W = (0.0042, 0.0030)            # a filament's half width across the slit at its root and its tip
COMB_T = 0.0022                      # its half thickness
COMB_V = (-0.090, -0.030)            # its root deep in the cavity, its tip near the mouth
COMB_FAN = 0.12                      # the tips spread out from the middle
COMB_BOW = -0.018                    # each curves toward the mouth end
FAULT_V = (-0.028, -0.024)
FAULT_H = (0.0006, 0.012)            # over the opening's lower edge

HAND_C = (0.46, 1.38)                # the scanner's octagon (u, h), on the door side's panel
HAND_OCT = (0.07, 0.095, 0.035)      # half width, half height, corner cut
BEZEL = (0.012, 0.020, 0.024, 0.010)   # the raised ring: inner chamfer top, flat, outer edge (from the octagon), proud
RECESS_V = -0.018                    # the recess floor

L.MATERIALS.setdefault("int_cyan__slit_comb", {**L.MATERIALS["int_cyan"], "base": (0.10, 0.70, 1.0, 1.0),
                                               "emission": (0.10, 0.70, 1.0), "strength": 9.0})
L.MATERIALS.setdefault("int_cyan__slit_deep", {**L.MATERIALS["int_cyan"], "base": (0.0, 0.22, 0.85, 1.0),
                                               "emission": (0.0, 0.22, 0.85), "strength": 2.0})
L.MATERIALS.setdefault("int_cyan__slit_line", dict(L.MATERIALS["int_cyan"]))
L.MATERIALS.setdefault("int_halo__slit_fault", {**L.MATERIALS["int_halo"], "base": (1.0, 0.20, 0.02, 1.0),
                                                "emission": (1.0, 0.20, 0.02), "strength": 6.0})
L.MATERIALS.setdefault("glow_cyan__slit_hand", {**L.MATERIALS["int_cyan"], "base": (0.15, 0.80, 1.0, 1.0),
                                                "emission": (0.15, 0.80, 1.0), "strength": 9.0})

_T = math.radians(TILT_DEG)
HINGE = (SLIT_C[0], SLIT_C[1] + SLIT_D / 2)
HINGE_AXIS = (math.cos(_T), math.sin(_T))   # along the hinge in (u, h); ship.gd turns the lip about it


# --- 2D -------------------------------------------------------------------------------------------------------------
def xf(x: float, y: float) -> tuple[float, float]:
    """Slit-local (x along the hinge, y up from it) -> (u, h over the deck)."""
    c, s = math.cos(_T), math.sin(_T)
    return HINGE[0] + x * c - y * s, HINGE[1] + x * s + y * c


def lower(x: float) -> float:
    """The opening's lower edge (slit-local y) under x: a convex V, TIP_H at the tips, SLIT_D at SLIT_LOW."""
    hw = SLIT_W / 2
    x = max(-hw, min(hw, x))
    s = (x + hw) / (SLIT_LOW + hw) if x <= SLIT_LOW else (hw - x) / (hw - SLIT_LOW)
    return -TIP_H - (SLIT_D - TIP_H) * (1 - (1 - s) ** V_POW)


def knots(hw: float = SLIT_W / 2) -> list[float]:
    a = [-hw + (SLIT_LOW + hw) * k / V_KNOTS for k in range(V_KNOTS + 1)]
    return a + [SLIT_LOW + (hw - SLIT_LOW) * k / V_KNOTS for k in range(1, V_KNOTS + 1)]


def opening() -> list[tuple[float, float]]:
    """The opening (slit-local, counter-clockwise): the V's facets, the blunt tips, the hinge line CLEAR over y 0."""
    hw = SLIT_W / 2
    return [(x, lower(x)) for x in knots()] + [(hw, TOP_CLEAR), (-hw, TOP_CLEAR)]


def lip_outline() -> list[tuple[float, float]]:
    """The lip (slit-local, counter-clockwise): the opening less CLEAR at the ends and GAP over its lower edge."""
    xl = SLIT_W / 2 - CLEAR
    return [(x, lower(x) + GAP) for x in knots(xl)] + [(xl, 0.0), (-xl, 0.0)]


def convex(poly) -> bool:
    n = len(poly)
    cr = [(poly[(i + 1) % n][0] - poly[i][0]) * (poly[(i + 2) % n][1] - poly[(i + 1) % n][1])
          - (poly[(i + 1) % n][1] - poly[i][1]) * (poly[(i + 2) % n][0] - poly[(i + 1) % n][0]) for i in range(n)]
    return all(c > -1e-12 for c in cr) or all(c < 1e-12 for c in cr)


def octagon(cu: float, ch: float, hw: float, hh: float, cut: float) -> list[tuple[float, float]]:
    return [(cu - hw + cut, ch - hh), (cu + hw - cut, ch - hh), (cu + hw, ch - hh + cut), (cu + hw, ch + hh - cut),
            (cu + hw - cut, ch + hh), (cu - hw + cut, ch + hh), (cu - hw, ch + hh - cut), (cu - hw, ch - hh + cut)]


def grow(poly, d: float) -> list[tuple[float, float]]:
    return [tuple(p) for p in G.inset(poly, -d)]


def shrink(poly, d: float) -> list[tuple[float, float]]:
    return [tuple(p) for p in G.inset(poly, d)]


def _cross(o, a, b) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def earclip(pts, seq) -> list[tuple[int, int, int]]:
    """A simple polygon (seq: indices into pts, counter-clockwise; a keyhole's bridge repeats two points) as
    triangles."""
    idx, tris = list(seq), []
    while len(idx) > 3:
        n = len(idx)
        for i in range(n):
            a, b, c = idx[i - 1], idx[i], idx[(i + 1) % n]
            A, B, C = pts[a], pts[b], pts[c]
            if _cross(A, B, C) <= 1e-12:
                continue
            if any(_cross(A, B, pts[j]) >= -1e-12 and _cross(B, C, pts[j]) >= -1e-12 and _cross(C, A, pts[j]) >= -1e-12
                   for j in idx if pts[j] not in (A, B, C)):
                continue
            tris.append((a, b, c))
            del idx[i]
            break
        else:
            raise ValueError("earclip: no ear left")
    tris.append(tuple(idx))
    return tris


def holed_tris(outer, hole) -> list[tuple[int, int, int]]:
    """A convex outline with a convex hole inside as triangles, indices into outer + hole (a keyhole from the hole's
    rightmost point along +u to the outline)."""
    n, m = len(outer), len(hole)
    oi = list(range(n)) if G.area2(outer) > 0 else list(range(n))[::-1]
    hi = list(range(m)) if G.area2(hole) < 0 else list(range(m))[::-1]
    pts = [tuple(p) for p in outer] + [tuple(p) for p in hole]
    k = max(range(m), key=lambda j: (hole[hi[j]][0], hole[hi[j]][1]))
    X, best = hole[hi[k]], None
    for a in range(n):
        p, q = outer[oi[a]], outer[oi[(a + 1) % n]]
        if (p[1] - X[1]) * (q[1] - X[1]) > 0 or abs(q[1] - p[1]) < 1e-12:
            continue
        xi = p[0] + (X[1] - p[1]) / (q[1] - p[1]) * (q[0] - p[0])
        if xi >= X[0] and (best is None or xi < best[0]):
            best = (xi, a if p[0] > q[0] else (a + 1) % n)
    b = best[1]
    seq = oi[:b + 1] + [n + hi[(k + j) % m] for j in range(m + 1)] + oi[b:]
    return earclip(pts, seq)


# --- meshes ---------------------------------------------------------------------------------------------------------
class Mesh:
    """Vertices (u, v, h over the deck) and faces, built from rings of (u, h) points at depths v."""

    def __init__(self):
        self.v, self.f = [], []

    def ring(self, poly, v) -> int:
        """A ring of (u, h) points at v (a number, or a function of (u, h)); its first index."""
        base = len(self.v)
        self.v += [(p[0], v(p) if callable(v) else v, p[1]) for p in poly]
        return base

    def bridge(self, a: int, b: int, n: int):
        self.f += [(a + i, a + (i + 1) % n, b + (i + 1) % n, b + i) for i in range(n)]

    def cap(self, a: int, n: int, flip: bool = False):
        self.f.append(tuple(range(a, a + n))[::-1] if flip else tuple(range(a, a + n)))

    def tris(self, a: int, n: int, b: int, tris):   # outer ring at a (n points), hole ring at b
        self.f += [tuple(a + i if i < n else b + i - n for i in t) for t in tris]

    def out(self):
        return self.v, self.f


def plate(poly, front: float = 0.0, back: float = -PLATE_T, ch: float = CH, hole=None, hole_ch: float = 0.0):
    """A wall plate: a convex (u, h) outline from back to front, its front edges chamfered ch; with a convex hole
    through it, the hole's front edge chamfered hole_ch. A closed solid."""
    m = Mesh()
    n = len(poly)
    fr = front if callable(front) else (lambda p, f=front: f)

    def less(d):
        return lambda p: fr(p) - d
    outer = [(poly, back)] + ([(poly, less(ch)), (shrink(poly, ch), fr)] if ch > 0 else [(poly, fr)])
    rs = [m.ring(p, v) for p, v in outer]
    for a, b in zip(rs, rs[1:]):
        m.bridge(a, b, n)
    if hole is None:
        m.cap(rs[0], n, True)
        m.cap(rs[-1], n)
        return m.out()
    k = len(hole)
    inner = ([(grow(hole, hole_ch), fr), (hole, less(hole_ch))] if hole_ch > 0 else [(hole, fr)]) + [(hole, back)]
    hs = [m.ring(p, v) for p, v in inner]
    for a, b in zip(hs, hs[1:]):
        m.bridge(a, b, k)
    m.tris(rs[-1], n, hs[0], holed_tris(outer[-1][0], inner[0][0]))
    m.tris(rs[0], n, hs[-1], [t[::-1] for t in holed_tris(poly, hole)])
    return m.out()


def prism(poly, v0: float, v1: float):
    m = Mesh()
    a, b = m.ring(poly, v0), m.ring(poly, v1)
    m.bridge(a, b, len(poly))
    m.cap(a, len(poly), True)
    m.cap(b, len(poly))
    return m.out()


def cup(poly, v0: float, v1: float, t: float = CUP_T):
    """A cavity's closed shell: the inside of poly from v0 back to v1, t thick."""
    m = Mesh()
    n = len(poly)
    big = grow(poly, t)
    a, b = m.ring(poly, v0), m.ring(poly, v1)
    c, d = m.ring(big, v1 - t), m.ring(big, v0)
    m.bridge(a, b, n)
    m.bridge(b, c, n)
    m.bridge(c, d, n)
    m.bridge(d, a, n)
    m.cap(b, n)
    m.cap(c, n, True)
    return m.out()


def sweep_ring(poly, profile):
    """A closed ring solid round a convex outline: profile [(grow, v)] a closed cross-section."""
    m = Mesh()
    n = len(poly)
    rs = [m.ring(grow(poly, g) if g else [tuple(p) for p in poly], v) for g, v in profile]
    for a, b in zip(rs, rs[1:] + rs[:1]):
        m.bridge(a, b, n)
    return m.out()


def rod(path, half_w, half_t: float, sides: int = 8):
    """A blade along path (u, v, h points): an elliptic section half_w(s) across the wall's u, half_t through it;
    capped."""
    vs, fs = [], []
    n = len(path)
    for i, p in enumerate(path):
        q0, q1 = path[max(i - 1, 0)], path[min(i + 1, n - 1)]
        t = [q1[k] - q0[k] for k in range(3)]
        lt = math.sqrt(sum(x * x for x in t))
        t = [x / lt for x in t]
        side = [1.0 - t[0] * t[0], -t[0] * t[1], -t[0] * t[2]]   # u minus its part along t
        ls = math.sqrt(sum(x * x for x in side))
        side = [x / ls for x in side]
        nrm = [t[1] * side[2] - t[2] * side[1], t[2] * side[0] - t[0] * side[2], t[0] * side[1] - t[1] * side[0]]
        w = half_w(i / (n - 1))
        for k in range(sides):
            a = 2 * math.pi * k / sides
            vs.append(tuple(p[j] + side[j] * w * math.cos(a) + nrm[j] * half_t * math.sin(a) for j in range(3)))
    for i in range(n - 1):
        fs += [(i * sides + k, i * sides + (k + 1) % sides, (i + 1) * sides + (k + 1) % sides, (i + 1) * sides + k)
               for k in range(sides)]
    fs.append(tuple(range(sides))[::-1])
    fs.append(tuple(range((n - 1) * sides, n * sides)))
    return vs, fs


def face_v(u: float, h: float) -> float:
    """The slit plate's leaning face (v) at (u, h over the deck): 0 at its top seam, SCALE_V at its foot."""
    dh = h - (HINGE[1] + (u - HINGE[0]) * math.tan(_T))
    return SCALE_V * (ROW[0] - dh) / (ROW[0] - ROW[1])


def lip_front(y: float) -> float:
    return LIP_FRONT[0] + (LIP_FRONT[1] - LIP_FRONT[0]) * (-y / SLIT_D)


def lip_back(y: float) -> float:
    return LIP_BACK[0] + (LIP_BACK[1] - LIP_BACK[0]) * (-y / SLIT_D)


def lip_mesh():
    """The lip: its outline's back face LIP_BACK, its face leaning out to LIP_FRONT[1] at the V's bottom, chamfered.
    Slit-local, then placed (u, h); y read back from the slit-local point for the face's lean."""
    m = Mesh()
    lo = lip_outline()
    n = len(lo)
    back = [xf(*p) for p in shrink(lo, LIP_TAPER)]
    mid = [xf(*p) for p in lo]
    face = [xf(*p) for p in shrink(lo, LIP_CH)]
    ys = {}
    for loc, pl in ((shrink(lo, LIP_TAPER), back), (lo, mid), (shrink(lo, LIP_CH), face)):
        for a, b in zip(loc, pl):
            ys[b] = a[1]
    a = m.ring(back, lambda p: lip_back(ys[p]))
    b = m.ring(mid, lambda p: lip_front(ys[p]) - LIP_CH)
    c = m.ring(face, lambda p: lip_front(ys[p]))
    m.bridge(a, b, n)
    m.bridge(b, c, n)
    m.cap(a, n, True)
    m.cap(c, n)
    return m.out()


def comb_paths() -> list[list[tuple[float, float, float]]]:
    """Each filament's centre line (u, v, h over the deck): from the cavity's top back, curving forward and down to
    the opening's lower edge."""
    hw = SLIT_W / 2 - 0.05
    out = []
    for i in range(COMB_N):
        x0 = -hw + 2 * hw * i / (COMB_N - 1)
        x1 = x0 + (x0 - SLIT_LOW) * COMB_FAN
        y0, y1 = -0.006, lower(x1) + 0.009
        pts = []
        for k in range(9):
            s = k / 8
            x = x0 + (x1 - x0) * s + COMB_BOW * math.sin(math.pi * s)
            y = y0 + (y1 - y0) * s
            v = COMB_V[0] + (COMB_V[1] - COMB_V[0]) * math.sin(s * math.pi / 2)
            u, h = xf(x, y)
            pts.append((u, v, h))
        out.append(pts)
    return out


def fault_mesh():
    m = Mesh()
    xs = knots(SLIT_W / 2 - 0.012)
    bot = [xf(x, lower(x) + FAULT_H[0]) for x in xs]
    top = [xf(x, lower(x) + FAULT_H[1]) for x in xs]
    n = len(xs)
    for v in FAULT_V:
        b0, t0 = m.ring(bot, v), m.ring(top, v)
    b_f, t_f, b_b, t_b = 2 * n, 3 * n, 0, n          # rings: back bot, back top, front bot, front top
    for i in range(n - 1):
        m.f += [(b_f + i, b_f + i + 1, t_f + i + 1, t_f + i), (b_b + i + 1, b_b + i, t_b + i, t_b + i + 1),
                (b_b + i, b_b + i + 1, b_f + i + 1, b_f + i), (t_b + i + 1, t_b + i, t_f + i, t_f + i + 1)]
    m.f += [(b_b, b_f, t_f, t_b), (b_f + n - 1, b_b + n - 1, t_b + n - 1, t_f + n - 1)]
    return m.out()


def hand_shapes() -> list[list[tuple[float, float]]]:
    """The three-fingered hand (u, h; convex pieces): the palm, then the fingers (middle, mouth side, door side)."""
    cu, ch = HAND_C[0], HAND_C[1] - 0.030
    palm = [(cu + 0.027 * math.cos(a) * (1.0 if math.sin(a) > 0 else 0.92),
             ch + 0.024 * math.sin(a) * (1.0 if math.sin(a) > 0 else 1.15))
            for a in (2 * math.pi * k / 18 for k in range(18))]
    out = [palm]
    for ang, ln in ((90.0, 0.074), (122.0, 0.060), (58.0, 0.060)):
        a = math.radians(ang)
        d, nrm = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))
        bw, tw = 0.0105, 0.0068
        b0 = (cu + d[0] * 0.010, ch + d[1] * 0.010)
        tip = (b0[0] + d[0] * (ln - tw), b0[1] + d[1] * (ln - tw))
        f = [(b0[0] - nrm[0] * bw, b0[1] - nrm[1] * bw)]
        f += [(tip[0] + tw * math.cos(a - math.pi / 2 + math.pi * k / 8), tip[1] + tw * math.sin(a - math.pi / 2 + math.pi * k / 8))
              for k in range(9)]
        f += [(b0[0] + nrm[0] * bw, b0[1] + nrm[1] * bw)]
        out.append(f)
    return out


# --- the piece ------------------------------------------------------------------------------------------------------
def column_rows():
    """The gill column's plates (u, h outlines): kick, low, the slit's plate, mid, upper; the slit plate's seams tilt
    with the slit."""
    c0, c1 = COLUMN
    k = math.tan(_T)

    def line(dh):
        return lambda u: HINGE[1] + dh + (u - HINGE[0]) * k
    top, bot = line(ROW[0]), line(ROW[1])
    sl = [(c0, bot(c0)), (c1, bot(c1)), (c1, top(c1)), (c0, top(c0))]
    low = [(c0, KICK + SEAM), (c1, KICK + SEAM), (c1, bot(c1) - SEAM), (c0, bot(c0) - SEAM)]
    mid = [(c0, top(c0) + SEAM), (c1, top(c1) + SEAM), (c1, BAND), (c0, BAND)]
    return {"kick": G.rect(c0, c1, 0.0, KICK), "low": low, "slit": sl, "mid": mid,
            "upper": G.rect(c0, c1, BAND + SEAM, TOP)}


def side_rows(u0: float, u1: float):
    return {"kick": G.rect(u0, u1, 0.0, KICK), "main": G.rect(u0, u1, KICK + SEAM, BAND),
            "upper": G.rect(u0, u1, BAND + SEAM, TOP)}


def station_gills_slit(args, layout):
    pid, side = args["id"], args.get("side", "e")
    s = -1.0 if side == "w" else 1.0
    parts = []

    def add(name, vf, mat, **extra):
        v, f = vf
        p = L.part(f"{pid}_{name}", [(s * x, y, S.FLOOR + h) for x, y, h in v], f, mat)
        if "origin" in extra:
            o = extra["origin"]
            extra["origin"] = (s * o[0], o[1], S.FLOOR + o[2])
        p.update(extra)
        parts.append(p)

    hole = [xf(*p) for p in opening()]
    left, right = side_rows(-HALF, COLUMN[0] - SEAM), side_rows(COLUMN[1] + SEAM, HALF)
    oct_ = octagon(HAND_C[0], HAND_C[1], *HAND_OCT)
    plates = []
    for name, poly in column_rows().items():
        if name == "slit":
            plates.append(plate(poly, front=lambda p: face_v(*p), hole=hole, hole_ch=HOLE_CH))
        else:
            plates.append(plate(poly))
    for name, poly in left.items():
        plates.append(plate(poly))
    for name, poly in right.items():
        plates.append(plate(poly, hole=grow(oct_, BEZEL[1] - 0.004)) if name == "main" else plate(poly))
    add("panel", L.merge(*plates), "int_silver_b")
    # the grooves' floor: one sheet behind the plates, holed round the cavity's cup
    add("backing", plate(G.rect(-HALF, HALF, 0.0, TOP), front=-PLATE_T - 0.002, back=-PLATE_T - 0.012, ch=0.0,
                         hole=grow(hole, CUP_T + 0.001)), "int_dark")
    add("body", L.box(-HALF, HALF, -0.20, -0.11, 0.0, TOP), "int_silver_b")
    # the cyan seam lines up the column's two grooves (the corridor portals' strips)
    lines = [L.box(u - LINE_W / 2, u + LINE_W / 2, -0.012, -0.008, KICK + 0.06, TOP - 0.12)
             for u in (COLUMN[0] - SEAM / 2, COLUMN[1] + SEAM / 2)]
    add("lines", L.merge(*lines), "int_cyan__slit_line")
    # the slit
    add("cavity", cup(hole, -PLATE_T, -CAVITY_D), "int_silver_c")
    add("comb_deep", prism(shrink(hole, 0.0005), -CAVITY_D + 0.0006, -CAVITY_D + 0.0016), "int_cyan__slit_deep")
    add("comb", L.merge(*[rod(p, lambda t: COMB_W[0] + (COMB_W[1] - COMB_W[0]) * t, COMB_T) for p in comb_paths()]),
        "int_cyan__slit_comb", smooth_deg=70.0)
    add("fault", fault_mesh(), "int_halo__slit_fault")
    add("lip", lip_mesh(), "int_silver_b", origin=(HINGE[0], LIP_HINGE_V, HINGE[1]))
    # the scanner: the raised bezel, the recess, its cyan rim line, the hand
    b_in, b_flat, b_out, b_v = BEZEL
    add("hand_bezel", sweep_ring(oct_, [(0.0, -0.004), (0.0, -0.002), (b_in, b_v), (b_flat, b_v),
                                        (b_out, b_v - 0.004), (b_out, -0.004)]), "int_silver_a")
    add("hand_recess", cup(oct_, -0.002, RECESS_V, 0.003), "int_dark")
    add("hand_rim", sweep_ring(shrink(oct_, 0.007), [(0.0, RECESS_V + 0.0002), (0.0035, RECESS_V + 0.0002),
                                                     (0.0035, RECESS_V + 0.0014), (0.0, RECESS_V + 0.0014)]),
        "glow_cyan__slit_hand")
    hv = RECESS_V + 0.0004
    add("hand", L.merge(*[prism(p, hv + 0.0005 * (k > 0), hv + 0.0012 + 0.0005 * (k > 0))
                          for k, p in enumerate(hand_shapes())]), "glow_cyan__slit_hand")
    # the soffit closing the ceiling's rim behind the chord (ship_interior_gills's)
    back = S.HV - GL.CHORD_APO
    sv = [(u, v, h) for h in (TOP, TOP + 0.08) for u, v in ((-HALF, 0.0), (0.0, -back), (HALF, 0.0))]
    add("soffit", (sv, [(2, 1, 0), (3, 4, 5), (0, 1, 4, 3), (1, 2, 5, 4), (2, 0, 3, 5)]), "int_silver_b")
    add("col0-convcolonly", L.box(-HALF, HALF, -0.2, 0.02, 0.0, BAND), "int_dark")
    return parts


def lip_turn(deg: float, side: str = "e") -> list[float]:
    """ship.gd's "turn" for the lip: its node's axis (Godot, the piece's frame: x = u, y = h, z = -v) and angle."""
    s = -1.0 if side == "w" else 1.0
    return [round(s * HINGE_AXIS[0], 6), round(HINGE_AXIS[1], 6), 0.0, round(s * deg, 3)]   # a mirror flips the turn


def _rel(x: float, y: float, v: float, side: str = "e") -> list[float]:
    """A point (slit-local x, y and v) relative to the lip's node origin (the hinge), Godot axes."""
    s = -1.0 if side == "w" else 1.0
    u, h = xf(x, y)
    return [round(s * (u - HINGE[0]), 4), round(h - HINGE[1], 4), round(-(v - LIP_HINGE_V), 4)]


def slit_states(side: str = "e") -> dict:
    """The shots' states as ship.gd's "stations" request: shut and faulty (the red seam), half open, open (the comb
    lit); "omni": lights placed from the lip node's origin [[node suffix, dx, dy, dz, r, g, b, energy, range]]."""
    cyan, red = [0.1, 0.65, 1.0], [1.0, 0.2, 0.02]
    mid = SLIT_LOW
    inside = ["lip", *_rel(mid, -SLIT_D * 0.7, -0.03, side), *cyan]
    out = ["lip", *_rel(mid, -SLIT_D - 0.03, 0.06, side), *cyan]
    return {
        "slit_shut": {"show": ["fault"], "hide": ["comb", "comb_deep"], "turn": {"lip": lip_turn(0.0, side)},
                      "omni": [["lip", *_rel(mid, -SLIT_D + 0.015, 0.02, side), *red, 0.2, 0.18]]},
        "slit_half": {"show": ["comb", "comb_deep"], "hide": ["fault"], "turn": {"lip": lip_turn(OPEN_DEG["half"], side)},
                      "omni": [inside + [0.2, 0.3], out + [0.06, 0.6]]},
        "slit_open": {"show": ["comb", "comb_deep"], "hide": ["fault"], "turn": {"lip": lip_turn(OPEN_DEG["open"], side)},
                      "omni": [inside + [0.35, 0.35], out + [0.12, 0.7]]},
    }
