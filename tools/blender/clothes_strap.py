"""The dungarees' strap rebuild and the sleeves' smoothing, pure maths (art #196, clothes step 2, C1e; no bpy,
unittest-tested in tools/tests/test_clothes_strap.py). clothes_dress.py imports it.

The Meshy garment's straps break up over the shoulders into folded flaps. clothes_dress.py deletes the garment's faces
in a corridor along each strap's path over the shoulder and lays a clean strip there instead:
- the path: the strap's own faces (its UV column) binned by their angle around the shoulder in the side view
  (bin_angles), every bin filled (fill_bins) and smoothed (smooth_open);
- per station a frame (frames): the path's tangent, the body's normal and the strip's width direction across;
- a garment point's place in the strip's frame (strip_coords: along the path, across it, above the body line) decides
  whether it goes (strip_delete);
- the strip is a grid of quads (strip_quads) with UVs on a clean denim rectangle, mirrored along the strap's length
  (mirror_v) so the twill keeps its texel density.

The sleeves: normal_step moves each vertex toward its neighbours' mean only along its own normal, so the texture does
not slide over the surface (an umbrella step along the surface turns the stripes into zig-zags, C1d r19).
"""
from __future__ import annotations

import math

Vec = tuple[float, float, float]


def dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Vec, b: Vec) -> Vec:
    return a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]


def sub(a: Vec, b: Vec) -> Vec:
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def unit(a: Vec) -> Vec:
    n = math.sqrt(dot(a, a))
    if n == 0.0:
        raise ValueError("zero vector")
    return a[0] / n, a[1] / n, a[2] / n


def median(xs: list[float]) -> float:
    s = sorted(xs)
    if not s:
        raise ValueError("no values")
    m = len(s) // 2
    return s[m] if len(s) % 2 else 0.5 * (s[m - 1] + s[m])


def angle(y: float, z: float, y0: float, z0: float) -> float:
    """The angle around the shoulder axis (y0, z0) in the side view: 0 straight up, negative to the front (-y)."""
    return math.atan2(y - y0, z - z0)


def bin_angles(pts: list[Vec], y0: float, z0: float, lo: float, hi: float, step: float) -> list[tuple[float, float]]:
    """The strap's points binned by angle (radians, lo to hi): per bin with points its centre angle and median x."""
    out = []
    n = int(round((hi - lo) / step))
    for i in range(n):
        a, b = lo + i * step, lo + (i + 1) * step
        xs = [p[0] for p in pts if a <= angle(p[1], p[2], y0, z0) < b]
        if xs:
            out.append((0.5 * (a + b), median(xs)))
    return out


def fill_bins(bins: list[tuple[float, float]], angles: list[float]) -> list[float]:
    """x at every angle: linear between the bins, the nearest bin's beyond them."""
    if not bins:
        raise ValueError("no bins")
    out = []
    for t in angles:
        if t <= bins[0][0]:
            out.append(bins[0][1])
        elif t >= bins[-1][0]:
            out.append(bins[-1][1])
        else:
            k = next(i for i in range(len(bins) - 1) if bins[i][0] <= t <= bins[i + 1][0])
            (ta, xa), (tb, xb) = bins[k], bins[k + 1]
            out.append(xa + (xb - xa) * (t - ta) / (tb - ta))
    return out


def smooth_open(values: list[float], iters: int, alpha: float = 0.5) -> list[float]:
    """Laplacian smoothing of an open line of numbers; the ends stay."""
    v = list(values)
    for _ in range(iters):
        v = [v[0]] + [(1 - alpha) * v[i] + alpha * 0.5 * (v[i - 1] + v[i + 1]) for i in range(1, len(v) - 1)] + [v[-1]]
    return v


def frames(centres: list[Vec], normals: list[Vec]) -> list[Vec]:
    """Per station the strip's width direction: across the path's tangent and the body's normal (unit)."""
    sides = []
    for i in range(len(centres)):
        a, b = centres[max(0, i - 1)], centres[min(len(centres) - 1, i + 1)]
        sides.append(unit(cross(unit(sub(b, a)), normals[i])))
    return sides


def arcs(centres: list[Vec]) -> list[float]:
    out = [0.0]
    for a, b in zip(centres, centres[1:]):
        out.append(out[-1] + math.sqrt(dot(sub(b, a), sub(b, a))))
    return out


def strip_coords(p: Vec, centres: list[Vec], sides: list[Vec], normals: list[Vec],
                 along: list[float]) -> tuple[float, float, float]:
    """p in the strip's frame: (along the path, across it, above the centre line), from the nearest segment; along
    runs below 0 or past the end beyond the path's ends."""
    best = None
    for i in range(len(centres) - 1):
        a, b = centres[i], centres[i + 1]
        ab = sub(b, a)
        ll = dot(ab, ab)
        t = 0.0 if ll == 0.0 else dot(sub(p, a), ab) / ll
        tc = min(1.0, max(0.0, t))
        q = (a[0] + ab[0] * tc, a[1] + ab[1] * tc, a[2] + ab[2] * tc)
        d = dot(sub(p, q), sub(p, q))
        if best is None or d < best[0]:
            best = (d, i, t)
    _d, i, t = best
    tc = min(1.0, max(0.0, t))
    s = tuple(sides[i][k] * (1 - tc) + sides[i + 1][k] * tc for k in range(3))
    n = tuple(normals[i][k] * (1 - tc) + normals[i + 1][k] * tc for k in range(3))
    c = tuple(centres[i][k] + (centres[i + 1][k] - centres[i][k]) * tc for k in range(3))
    seg = along[i + 1] - along[i]
    return along[i] + t * seg, dot(sub(p, c), s), dot(sub(p, c), n)


def strip_delete(at: tuple[float, float, float], length: float, half: float, outer: bool, inset: float = 0.002,
                 reach: float = 0.025, below: float = 0.02, above: float = 0.04, end: float = 0.005) -> str | None:
    """Whether a garment face (its centre's strip_coords at) goes: "core" when under the strip (less inset from its
    edges), "flap" when within reach of its edges and an outer layer (outer: more garment lies between it and the
    body); None otherwise, or beyond the path's ends (less end) or far above or below the strip."""
    s, lat, h = at
    if s < end or s > length - end or h < -below or h > above:
        return None
    if abs(lat) < half - inset:
        return "core"
    if outer and abs(lat) < half + reach:
        return "flap"
    return None


def strip_quads(rows: int, cols: int) -> list[list[int]]:
    """Quads of a grid of rows x cols vertices (row-major), wound the same way across the grid."""
    return [[r * cols + c, r * cols + c + 1, (r + 1) * cols + c + 1, (r + 1) * cols + c]
            for r in range(rows - 1) for c in range(cols - 1)]


def mirror_v(s: float, v0: float, v1: float, per_m: float) -> float:
    """The v of a point s m along the strap: a triangle wave between v0 and v1 at per_m UV units per metre, so a strap
    longer than the clean rectangle walks back and forth over it."""
    span = v1 - v0
    if span <= 0 or per_m <= 0:
        raise ValueError("empty rectangle")
    x = (s * per_m) % (2 * span)
    return v0 + (x if x <= span else 2 * span - x)


def normal_step(pos: list[Vec], normals: list[Vec], nbrs: list[list[int]], alpha: float,
                pinned: set[int] | None = None) -> list[Vec]:
    """One smoothing step along each vertex's normal only: the move toward its neighbours' mean, projected on its
    normal; pinned vertices (the openings) stay."""
    pinned = pinned or set()
    out = []
    for i, p in enumerate(pos):
        if i in pinned or not nbrs[i]:
            out.append(p)
            continue
        m = tuple(sum(pos[j][k] for j in nbrs[i]) / len(nbrs[i]) for k in range(3))
        h = alpha * dot(sub(m, p), normals[i])
        out.append((p[0] + normals[i][0] * h, p[1] + normals[i][1] * h, p[2] + normals[i][2] * h))
    return out


def keep_clearance(old: float, new: float, floor: float) -> bool:
    """A smoothed vertex keeps its move when its new distance from the body (signed, m) stays at least the smaller
    of its old distance and floor: smoothing never brings the cloth nearer the body than it was or than floor."""
    return new >= min(old, floor)


def follow_run(xs: list[float], prev: float, window: float = 0.04, max_width: float = 0.06) -> float | None:
    """Down the back, where the strap's UV column ends: the denim faces' x at one station (xs), those within window
    of the strap's last x (prev); their middle, or None when there are none or they spread wider than max_width
    (the strap has reached the back bib)."""
    near = [x for x in xs if abs(x - prev) <= window]
    if not near or max(near) - min(near) > max_width:
        return None
    return 0.5 * (min(near) + max(near))


def clamp_move(p0: Vec, p: Vec, most: float) -> Vec:
    """p moved from p0 by at most most (m), along the same direction."""
    d = sub(p, p0)
    n = math.sqrt(dot(d, d))
    if n <= most:
        return p
    k = most / n
    return p0[0] + d[0] * k, p0[1] + d[1] * k, p0[2] + d[2] * k
