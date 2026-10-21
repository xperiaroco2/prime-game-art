"""Plain-Python mesh helpers of the ship's INTERIOR lane (art #263, docs/ship.md): bevelled slabs on any plane,
pillow (folded) panels, slotted grates (radial and straight), tubes for cables, and the crushed cup. Every helper
returns (verts, faces) in plan coordinates (x east, y south, h up; metres) for ship_lib.part / ship_lib.merge. Solids
are closed; the build harness recomputes their normals outward. No bpy here: the fast tests import it."""

from __future__ import annotations

import math
import random

import ship_lib as L


# --- vectors -------------------------------------------------------------------------------------------------------
def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def unit(a):
    n = math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2) or 1.0
    return (a[0] / n, a[1] / n, a[2] / n)


class Frame:
    """A plane: origin O, in-plane axes U and V, normal N (toward the room); point(u, v, w) = O + uU + vV + wN."""

    def __init__(self, o, u, v, n=None):
        self.o, self.u, self.v = tuple(o), unit(u), unit(v)
        self.n = unit(n) if n is not None else unit(cross(self.u, self.v))

    def point(self, u: float, v: float, w: float = 0.0):
        return add(add(add(self.o, mul(self.u, u)), mul(self.v, v)), mul(self.n, w))


def floor_frame(h: float) -> Frame:
    return Frame((0.0, 0.0, h), (1, 0, 0), (0, 1, 0), (0, 0, 1))


def wall_frame(h: float, x: float = 0.0) -> Frame:
    """The plane x = const facing -x (a wall built at plan angle 0, the room toward -x); u along +y, v up."""
    return Frame((x, 0.0, h), (0, 1, 0), (0, 0, 1), (-1, 0, 0))


# --- polygons ------------------------------------------------------------------------------------------------------
def area2(poly) -> float:
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1]))


def inset(poly, d: float):
    """A convex polygon moved inward by d (outward for d < 0); either winding."""
    s = 1.0 if area2(poly) > 0 else -1.0
    n = len(poly)
    lines = []
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        ex, ey = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(ex, ey) or 1.0
        nx, ny = -ey / ln * s, ex / ln * s
        lines.append(((a[0] + nx * d, a[1] + ny * d), (ex, ey)))
    out = []
    for i in range(n):
        (p, e), (q, f) = lines[i - 1], lines[i]
        den = e[0] * f[1] - e[1] * f[0]
        if abs(den) < 1e-12:
            out.append(q)
            continue
        t = ((q[0] - p[0]) * f[1] - (q[1] - p[1]) * f[0]) / den
        out.append((p[0] + e[0] * t, p[1] + e[1] * t))
    return out


def arc(r: float, a0: float, a1: float, step: float = math.radians(6.0)):
    return [(r * math.cos(a), r * math.sin(a)) for a in L.angles(a0, a1, step)]


def rect(u0, u1, v0, v1):
    return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]


# --- solids --------------------------------------------------------------------------------------------------------
def slab(fr: Frame, poly, w0: float, w1: float, bevel: float = 0.0):
    """A convex polygon (u, v) extruded from w0 to w1 along the frame's normal; the w1 face's edges chamfered."""
    n = len(poly)
    verts = [fr.point(u, v, w0) for u, v in poly]
    if bevel > 0:
        verts += [fr.point(u, v, w1 - bevel) for u, v in poly]
        verts += [fr.point(u, v, w1) for u, v in inset(poly, bevel)]
        faces = [tuple(range(n)), tuple(range(2 * n, 3 * n))]
        faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
        faces += [(n + i, n + (i + 1) % n, 2 * n + (i + 1) % n, 2 * n + i) for i in range(n)]
    else:
        verts += [fr.point(u, v, w1) for u, v in poly]
        faces = [tuple(range(n)), tuple(range(n, 2 * n))]
        faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return verts, faces


def bbox(x0, x1, y0, y1, h0, h1, bevel: float = 0.0):
    """A box, its top edges chamfered."""
    return slab(floor_frame(0.0), rect(x0, x1, y0, y1), h0, h1, bevel)


def pillow(fr: Frame, u0, u1, v0, v1, w0: float, w1: float, apex: float, bevel: float):
    """A folded panel: a bevelled rectangle whose face rises in four facets to a ridge point at its centre."""
    r = rect(u0, u1, v0, v1)
    verts = [fr.point(u, v, w0) for u, v in r] + [fr.point(u, v, w1) for u, v in r]
    verts += [fr.point(u, v, w1 + bevel) for u, v in inset(r, bevel)]
    verts.append(fr.point((u0 + u1) / 2, (v0 + v1) / 2, apex))
    faces = [(0, 1, 2, 3)] + [(i, (i + 1) % 4, 4 + (i + 1) % 4, 4 + i) for i in range(4)]
    faces += [(4 + i, 4 + (i + 1) % 4, 8 + (i + 1) % 4, 8 + i) for i in range(4)]
    faces += [(8 + i, 8 + (i + 1) % 4, 12) for i in range(4)]
    return verts, faces


def band(fr: Frame, inner, outer, w0: float, w1: float, bevel: float, edges):
    """Bevelled quads between an inner and an outer polyline (a frame around an opening), for the edge indices."""
    n = len(inner)
    return L.merge(*[slab(fr, [inner[i], inner[(i + 1) % n], outer[(i + 1) % n], outer[i]], w0, w1, bevel)
                     for i in edges])


# --- grates --------------------------------------------------------------------------------------------------------
def radial_grate(r0, r1, a0, a1, h0, h1, pitch=0.11, slot=0.17, bar=0.024, border=0.045):
    """A slotted sector plate: ring bars every `pitch` and ties every `slot` along each ring of slots."""
    out = []
    m = max(1, round((r1 - r0) / pitch))
    step = (r1 - r0) / m
    step_a = math.radians(5.0)
    for k in range(m + 1):
        rr = r0 + k * step
        lo, hi = (r0, r0 + border) if k == 0 else (r1 - border, r1) if k == m else (rr - bar / 2, rr + bar / 2)
        a = L.angles(a0, a1, step_a)
        out += [L.sector(lo, hi, p, q, h0, h1) for p, q in zip(a, a[1:])]
    for k in range(m):
        ri = r0 + k * step + (border if k == 0 else bar / 2)
        ro = r0 + (k + 1) * step - (border if k == m - 1 else bar / 2)
        rm = (ri + ro) / 2
        n = max(1, round(rm * (a1 - a0) / slot))
        for j in range(n + 1):
            aj = a0 + j * (a1 - a0) / n
            w = (border if j in (0, n) else bar) / rm
            lo, hi = (a0, a0 + w) if j == 0 else (a1 - w, a1) if j == n else (aj - w / 2, aj + w / 2)
            out.append(L.sector(ri, ro, lo, hi, h0, h1))
    return L.merge(*out)


def rect_grate(x0, x1, y0, y1, h0, h1, pitch=0.075, slot=0.18, bar=0.022, border=0.04):
    """A slotted rectangular plate: cross bars along y every `pitch` in x, ties every `slot` in y between them."""
    out = []
    m = max(1, round((x1 - x0) / pitch))
    step = (x1 - x0) / m
    for k in range(m + 1):
        xx = x0 + k * step
        lo, hi = (x0, x0 + border) if k == 0 else (x1 - border, x1) if k == m else (xx - bar / 2, xx + bar / 2)
        out.append(L.box(lo, hi, y0, y1, h0, h1))
    n = max(1, round((y1 - y0) / slot))
    for k in range(m):
        xi = x0 + k * step + (border if k == 0 else bar / 2)
        xo = x0 + (k + 1) * step - (border if k == m - 1 else bar / 2)
        for j in range(n + 1):
            yy = y0 + j * (y1 - y0) / n
            lo, hi = (y0, y0 + border) if j == 0 else (y1 - border, y1) if j == n else (yy - bar / 2, yy + bar / 2)
            out.append(L.box(xi, xo, lo, hi, h0, h1))
    return L.merge(*out)


# --- tubes and the cup ---------------------------------------------------------------------------------------------
def tube(path, r: float, sides: int = 7):
    """A closed tube of radius r along a polyline of 3D points."""
    tangents = []
    for i in range(len(path)):
        a, b = path[max(0, i - 1)], path[min(len(path) - 1, i + 1)]
        tangents.append(unit(sub(b, a)))
    ref = (1.0, 0.0, 0.0) if any(abs(t[2]) > 0.9 for t in tangents) else (0.0, 0.0, 1.0)
    verts = []
    for p, t in zip(path, tangents):
        side = unit(cross(t, ref))
        up = cross(side, t)
        verts += [add(p, add(mul(side, r * math.cos(2 * math.pi * j / sides)),
                             mul(up, r * math.sin(2 * math.pi * j / sides)))) for j in range(sides)]
    n = len(path)
    faces = [(i * sides + j, i * sides + (j + 1) % sides, (i + 1) * sides + (j + 1) % sides, (i + 1) * sides + j)
             for i in range(n - 1) for j in range(sides)]
    faces += [tuple(range(sides - 1, -1, -1)), tuple(range((n - 1) * sides, n * sides))]
    return verts, faces


def cup(seed: int, rings: int = 9, segs: int = 18):
    """A crushed party cup lying on its side: (body, rim) closed shells; the cup's axis along +x, resting on h = 0."""
    rnd = random.Random(seed)
    length, rb, rt, wall = 0.12, 0.030, 0.046, 0.0035
    dents = [(rnd.uniform(0.25, 0.85), rnd.uniform(0, 2 * math.pi), rnd.uniform(0.15, 0.45)) for _ in range(4)]
    squash = rnd.uniform(0.55, 0.75)

    def radius(t: float, a: float) -> float:
        r = rb + (rt - rb) * t
        for tc, ac, depth in dents:
            r *= 1 - depth * math.exp(-((t - tc) / 0.14) ** 2) * max(0.0, math.cos(a - ac)) ** 3
        r *= 1 + 0.06 * math.sin(7 * a + 13 * t + seed)
        return r

    def ring(t: float, off: float):
        out = []
        for j in range(segs):
            a = 2 * math.pi * j / segs
            r = radius(t, a) - off
            sq = 1 - (1 - squash) * math.sin(math.pi * min(1.0, t * 1.2))
            out.append((t * length, r * math.cos(a), r * math.sin(a) * sq))
        return out
    ts = [i / (rings - 1) * 0.94 for i in range(rings)]
    verts = []
    for t in ts:
        verts += ring(t, 0.0)
    for t in reversed(ts):
        verts += ring(t, wall)
    n = 2 * rings
    faces = [(i * segs + j, i * segs + (j + 1) % segs, (i + 1) * segs + (j + 1) % segs, (i + 1) * segs + j)
             for i in range(n - 1) for j in range(segs)]
    faces += [tuple(range(segs - 1, -1, -1)), tuple(range((n - 1) * segs, n * segs))]
    pts = ring(0.94, -0.0025)  # the rolled white lip: a closed ring of four strips round the opening
    lip = [(p[0] + dx, p[1] * s, p[2] * s) for dx, s in ((0.004, 1.0), (-0.008, 1.0), (-0.008, 0.9), (0.004, 0.9))
           for p in pts]
    lip_faces = [(k * segs + j, k * segs + (j + 1) % segs, ((k + 1) % 4) * segs + (j + 1) % segs,
                  ((k + 1) % 4) * segs + j) for k in range(4) for j in range(segs)]
    lo = min(v[2] for v in verts)
    shift = lambda vs: [(x, y, h - lo) for x, y, h in vs]  # noqa: E731
    return (shift(verts), faces), (shift(lip), lip_faces)
