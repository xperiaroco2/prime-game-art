"""Bodies by drawing, step D3c (art #196): the feet's new forefoot, the maths only (no bpy; body_fit_blend.py
builds it in Blender).

The fitted bodies' toes stayed split (slits, flaps, holes) through two projection tries, so the region ahead of the
Toes head is cut off along one plane (y = the cut) and replaced by new geometry: one closed, rounded mitten front
grown from the cut's own vertex loop. Ring k sits at y(t) = cut - t * (cut - tip) and is the cut's section scaled
about the section's middle in x and about a low centre in z (the sole stays flat until the front rounds it up):

- the top view's width rises from the cut's width to the table's foot width at `t_w`, then rounds to 0 at the tip
  as a superellipse of exponent `n` (`outline`);
- the side view's top rises from the cut's top to the table's toe height at `t_h`, then rounds the same way; below
  the centre only the rounding acts (no sole sinks under the floor).

The last ring is closed by a fan to one tip vertex; the cut's loop is shared, so the weld has no seam, and a Taubin
smoothing (`taubin`, no shrinking) over the new front and a blend zone behind the cut evens the join.
"""
from __future__ import annotations

import math


def smoothstep(a: float, b: float, x: float) -> float:
    if b == a:
        return 1.0 if x >= b else 0.0
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


TOE_BLEND = 0.012  # m: the new front's Toes share rises from this far behind the Toes head to this far ahead


def toe_share(y: float, joint_y: float, near: float, blend: float = TOE_BLEND) -> float:
    """A new forefoot vertex's Toes share (D3e): its nearest old toe vertex's (`near`), but never less than a
    smoothstep from `blend` m behind the Toes head to `blend` m ahead (the front at -y). The front is longer than the
    old toes; on Foot it pitched with the heel on a tiptoe (Crouch_Fwd) and sank under the floor."""
    return max(near, smoothstep(joint_y + blend, joint_y - blend, y))


def outline(t: float, start: float, peak: float, t_peak: float, n: float) -> float:
    """A profile along the forefoot, t in [0, 1] from the cut to the tip: `start` at the cut, easing (zero slope at
    both ends) to `peak` at `t_peak`, then a superellipse quarter of exponent n down to 0 at t = 1."""
    if t <= t_peak:
        return start + (peak - start) * smoothstep(0.0, t_peak, t)
    u = min(1.0, (t - t_peak) / (1.0 - t_peak))
    return peak * max(0.0, 1.0 - u ** n) ** (1.0 / n)


def ring_ts(k: int, power: float = 2.0) -> list:
    """The rings' t (k of them, the tip excluded): denser toward the tip, where the front turns fastest."""
    return [1.0 - (1.0 - i / (k + 1)) ** power for i in range(1, k + 1)]


def four_point(p0, p1, p2, p3):
    """The four-point scheme's midpoint between p1 and p2 (a smooth curve through the section, not its chord)."""
    return tuple((-a + 9 * b + 9 * c - d) / 16.0 for a, b, c, d in zip(p0, p1, p2, p3))


def forefoot(boundary: list, tip_y: float, width: float, toe_height: float, rings: int = 14, t_w: float = 0.45,
             t_h: float = 0.45, n: float = 2.2, centre_share: float = 0.15, min_columns: int = 40) -> tuple:
    """New forefoot geometry from the cut's closed loop `boundary` ([(x, y, z)] in order, the y all the cut's; the
    body's face along it runs B_j -> B_j+1), forward -y to `tip_y`. Returns (points, faces): points[0:N] are the
    boundary's own (unmoved), the rest new; faces index points and wind opposite the body's face at the boundary,
    so the front's normals agree with the body's. Fewer than `min_columns` boundary vertices: the first ring doubles
    them (a quad and a triangle per boundary edge)."""
    nb = len(boundary)
    y0 = sum(p[1] for p in boundary) / nb
    xs = [p[0] for p in boundary]
    zs = [p[2] for p in boundary]
    cx = 0.5 * (min(xs) + max(xs))
    sole = min(zs)
    top = max(zs)
    zc = sole + centre_share * (top - sole)
    w0 = max(xs) - min(xs)
    h0 = top - zc
    cols = list(boundary)
    double = nb < min_columns
    if double:
        cols = []
        for j in range(nb):
            cols.append(boundary[j])
            cols.append(four_point(boundary[j - 1], boundary[j], boundary[(j + 1) % nb], boundary[(j + 2) % nb]))
    nc = len(cols)
    pts = [tuple(p) for p in boundary]
    faces = []
    length = y0 - tip_y
    prev = list(range(nb))
    for r, t in enumerate(ring_ts(rings)):
        sx = outline(t, w0, width, t_w, n) / w0
        s_top = outline(t, h0, toe_height - zc, t_h, n) / h0
        s_bot = outline(t, 1.0, 1.0, t_h, n)
        y = y0 - t * length
        base = len(pts)
        for (x, _, z) in cols:
            s = s_top if z >= zc else s_bot
            pts.append((cx + (x - cx) * sx, y, max(sole, zc + (z - zc) * s)))  # the 4-point midpoints dip
        cur = list(range(base, base + nc))
        if r == 0 and double:
            for j in range(nb):
                a, b = prev[j], prev[(j + 1) % nb]
                faces.append((b, a, cur[2 * j], cur[2 * j + 1]))
                faces.append((b, cur[2 * j + 1], cur[(2 * j + 2) % nc]))
        else:
            m = len(prev)
            for j in range(m):
                faces.append((prev[(j + 1) % m], prev[j], cur[j], cur[(j + 1) % m]))
        prev = cur
    tip = len(pts)
    pts.append((cx, tip_y, zc))
    for j in range(nc):
        faces.append((prev[(j + 1) % nc], prev[j], tip))
    return pts, faces


def neighbours(n: int, faces: list) -> list:
    nbr = [set() for _ in range(n)]
    for f in faces:
        for i, a in enumerate(f):
            b = f[(i + 1) % len(f)]
            nbr[a].add(b)
            nbr[b].add(a)
    return [sorted(s) for s in nbr]


def taubin(pts: list, nbr: list, wt: list, iters: int, lam: float = 0.5, mu: float = -0.53) -> list:
    """Taubin smoothing (a shrink step lam, an inflate step mu per round), each vertex by its weight wt (0: fixed).
    Evens facets and steps without pulling the front back as plain umbrella smoothing does."""
    p = [tuple(q) for q in pts]
    for _ in range(iters):
        for k in (lam, mu):
            nxt = list(p)
            for i, w in enumerate(wt):
                if w > 0 and nbr[i]:
                    avg = [sum(p[j][a] for j in nbr[i]) / len(nbr[i]) for a in range(3)]
                    nxt[i] = tuple(p[i][a] + k * w * (avg[a] - p[i][a]) for a in range(3))
            p = nxt
    return p


def laplace(pts: list, nbr: list, wt: list, iters: int, lam: float = 0.5) -> list:
    """Plain umbrella smoothing by weight: fills a dent (the ankle's front) where Taubin would keep it."""
    p = [tuple(q) for q in pts]
    for _ in range(iters):
        nxt = list(p)
        for i, w in enumerate(wt):
            if w > 0 and nbr[i]:
                avg = [sum(p[j][a] for j in nbr[i]) / len(nbr[i]) for a in range(3)]
                nxt[i] = tuple(p[i][a] + lam * w * (avg[a] - p[i][a]) for a in range(3))
        p = nxt
    return p


def order_loop(edges: list) -> list:
    """One closed loop's vertices in order from its edges [(a, b)]; raises when they are not one simple loop."""
    nbr: dict = {}
    for a, b in edges:
        nbr.setdefault(a, []).append(b)
        nbr.setdefault(b, []).append(a)
    if any(len(v) != 2 for v in nbr.values()):
        raise ValueError("the cut is not one simple loop")
    start = next(iter(nbr))
    loop, prev, cur = [start], None, start
    while True:
        nxt = [v for v in nbr[cur] if v != prev]
        nxt = nxt[0] if prev is not None else nbr[cur][0]
        if nxt == start:
            break
        loop.append(nxt)
        prev, cur = cur, nxt
        if len(loop) > len(nbr):
            raise ValueError("the cut is not one simple loop")
    if len(loop) != len(nbr):
        raise ValueError(f"the cut is more than one loop ({len(loop)} of {len(nbr)} vertices in the first)")
    return loop


def front_extent(pts: list) -> dict:
    """The front's outline numbers: length (y), width (x), top (z) of the given points."""
    xs, ys, zs = zip(*pts)
    return {"width": max(xs) - min(xs), "min_y": min(ys), "top": max(zs), "sole": min(zs)}


def tip_from_table(heel_y: float, length: float) -> float:
    """The front's tip: the table's foot length ahead of the body's heel (the heel is kept)."""
    return heel_y - length


def dihedral_max(pts: list, faces: list) -> float:
    """The largest angle (degrees) between neighbouring faces' normals: a facet or a fold check."""
    def normal(f):
        a, b, c = pts[f[0]], pts[f[1]], pts[f[2]]
        u = [b[i] - a[i] for i in range(3)]
        v = [c[i] - a[i] for i in range(3)]
        nx = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        ln = math.sqrt(sum(q * q for q in nx)) or 1.0
        return tuple(q / ln for q in nx)
    by_edge: dict = {}
    for fi, f in enumerate(faces):
        for i, a in enumerate(f):
            by_edge.setdefault(frozenset((a, f[(i + 1) % len(f)])), []).append(fi)
    ns = [normal(f) for f in faces]
    worst = 0.0
    for fs in by_edge.values():
        if len(fs) == 2:
            d = max(-1.0, min(1.0, sum(p * q for p, q in zip(ns[fs[0]], ns[fs[1]]))))
            worst = max(worst, math.degrees(math.acos(d)))
    return worst
