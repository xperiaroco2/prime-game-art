"""The alien's hand and wrist rebuilt in place: the maths (art #196, Hands H1b; no bpy, standard library only).

The hand keeps its topology (every vertex, face, weight and UV; f1, f2, the heads and the clothes keep working). Only
vertex positions move, and only in the hand region: the wrist band and the fingers.

- **The wrist band** (`wrist_band`): the vertices between the forearm's last clean ring (`s_fore`, m along the arm
  from the wrist joint, negative) and the palm (`s_palm`) that the LowerArm and Hand carry (a vertex the thumb carries
  half or more stays) are first relaxed by Taubin rounds with every vertex outside the band held: the pinched neck and
  the lump after the joint go, and the scattered vertices spread evenly (the bend's rows). Then each is scaled about
  the band's smooth centre line, across (u, the palm's width) and through (v, its thickness), so the band's measured
  extents follow the spec's profile: the forearm's own at `s_fore`, `wrist_width_ratio` and `wrist_thick_ratio` of it
  at the joint, the palm's own at `s_palm`, joined by monotone cubic eases (no second waist, no lump).
- **The fingers** (`finger`): each finger's vertices (its chain carrying a share of them) get a new radius about the
  chain's own polyline: the measured mean radius (smoothed over `MEASURE_SIGMA`) is mapped to the spec's profile, the
  root's radius tapering only `taper` to the dome's start, then a dome of that radius over the tip (no knuckle bulge,
  no thin end). The move ramps in from the knuckle (`ramp`) and with the vertex's share on the chain.

The checks: `extents_table` (the band's width and thickness along s), `section` (a cross-section's width, thickness,
area and the deepest fold, the crease, measured against its convex hull), `row_gaps` (the largest gap between the
band's vertices along s near the joint).
"""
from __future__ import annotations

import math

MEASURE_SIGMA = 0.0015  # m: the fingers' measured radius, per ring (5 mm apart): a bulge is measured, then mapped away
WINDOW = 0.008          # m: the band's extents measured over s +- WINDOW


def sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def add(a, b):
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]


def mul(a, k):
    return [a[0] * k, a[1] * k, a[2] * k]


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def norm(a):
    n = math.sqrt(dot(a, a))
    return [a[0] / n, a[1] / n, a[2] / n] if n else [0.0, 0.0, 0.0]


def smoothstep(e0: float, e1: float, x: float) -> float:
    if e1 == e0:
        return 1.0 if x >= e1 else 0.0
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def ease(y0: float, y1: float, t: float) -> float:
    """Monotone cubic from y0 to y1 over t in 0..1 with flat ends."""
    return y0 + (y1 - y0) * smoothstep(0.0, 1.0, t)


def frame(axis, hint):
    """An orthonormal (d, u, v): d along the axis, u the hint made perpendicular to it, v = d x u."""
    d = norm(axis)
    u = norm(sub(hint, mul(d, dot(hint, d))))
    return d, u, cross(d, u)


def adjacency(n_or_ids, edges) -> dict:
    adj = {}
    for a, b in edges:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    return adj


def taubin(pos: dict, adj: dict, movable: set, iters: int, lam: float = 0.5, mu: float = -0.53) -> dict:
    """Taubin rounds on the movable vertices (uniform weights); the others are held. Returns new positions."""
    p = {k: list(v) for k, v in pos.items()}
    for _ in range(iters):
        for f in (lam, mu):
            new = {}
            for i in movable:
                nb = [j for j in adj.get(i, ()) if j in p]
                if not nb:
                    continue
                c = [sum(p[j][k] for j in nb) / len(nb) for k in range(3)]
                new[i] = add(p[i], mul(sub(c, p[i]), f))
            p.update(new)
    return p


def coords(p, origin, fr):
    d, u, v = fr
    r = sub(p, origin)
    return dot(r, d), dot(r, u), dot(r, v)


def extents_at(samples, s: float, half: float = WINDOW):
    """Centre and half extents (u, v) of the samples [(s, u, v)] within s +- half; None when fewer than 4."""
    w = [(a, b) for (t, a, b) in samples if abs(t - s) <= half]
    if len(w) < 4:
        return None
    us, vs = [a for a, _ in w], [b for _, b in w]
    cu, cv = (max(us) + min(us)) / 2, (max(vs) + min(vs)) / 2
    return cu, cv, (max(us) - min(us)) / 2, (max(vs) - min(vs)) / 2


def slice_points(pos: dict, edges, origin, n, u, v, rmax: float = 0.08) -> list:
    """The section of the mesh by the plane through origin with normal n: every edge crossing it, cut where it
    crosses, as (u, v) points (m); edges farther than rmax from origin are left out (the other limbs)."""
    out = []
    for a, b in edges:
        if a not in pos or b not in pos:
            continue
        pa, pb = pos[a], pos[b]
        da, db = dot(sub(pa, origin), n), dot(sub(pb, origin), n)
        if (da > 0) == (db > 0) or da == db:
            continue
        q = add(pa, mul(sub(pb, pa), da / (da - db)))
        r = sub(q, origin)
        if dot(r, r) <= rmax * rmax:
            out.append((dot(r, u), dot(r, v)))
    return out


def slice_extents(pos: dict, edges, origin, fr, s: float):
    """(centre u, centre v, half width, half thickness) of the section at s along the frame's axis; None if empty."""
    d, u, v = fr
    pts = slice_points(pos, edges, add(origin, mul(d, s)), d, u, v)
    if len(pts) < 3:
        return None
    us, vs = [a for a, _ in pts], [b for _, b in pts]
    return (max(us) + min(us)) / 2, (max(vs) + min(vs)) / 2, (max(us) - min(us)) / 2, (max(vs) - min(vs)) / 2


def _interp(grid: list, s: float):
    """Linear interpolation in a [(s, tuple)] grid sorted by s, clamped at the ends."""
    if s <= grid[0][0]:
        return grid[0][1]
    for (s0, a), (s1, b) in zip(grid, grid[1:]):
        if s <= s1:
            t = (s - s0) / (s1 - s0)
            return tuple(x + (y - x) * t for x, y in zip(a, b))
    return grid[-1][1]


def band_target(s: float, s_fore: float, s_palm: float, fore, palm, wrist_w: float, wrist_t: float):
    """The spec's half extents (u, v) at s: the forearm's, eased to the wrist's at 0, eased to the palm's."""
    if s <= 0:
        t = (s - s_fore) / (0 - s_fore)
        return ease(fore[0], wrist_w, t), ease(fore[1], wrist_t, t)
    t = s / s_palm
    return ease(wrist_w, palm[0], t), ease(wrist_t, palm[1], t)


def wrist_band(pos: dict, weights: dict, adj: dict, origin, fr, side: str, spec: dict, held_extra=()) -> tuple:
    """The wrist band rebuilt (module docstring). pos: {index: [x, y, z]} of the region; weights: {index: {bone: w}}.
    Returns (new positions of the moved vertices, report)."""
    s_fore, s_palm = spec["s_fore"], spec["s_palm"]
    lo, hand = f"{side}LowerArm", f"{side}Hand"
    sc = {i: coords(p, origin, fr) for i, p in pos.items()}
    band = set()
    for i, (s, _, _) in sc.items():
        w = weights[i]
        arm = w.get(lo, 0) + w.get(hand, 0)
        thumb = sum(x for k, x in w.items() if "Thumb" in k)
        if s_fore + 1e-4 < s < s_palm and arm + thumb >= 0.5 and i not in held_extra:
            band.add(i)
    smooth = taubin(pos, adj, band, spec.get("taubin", 40))
    edges = [(a, b) for a in pos for b in adj.get(a, ()) if a < b and b in pos]
    fore = slice_extents(pos, edges, origin, fr, s_fore)
    palm = slice_extents(pos, edges, origin, fr, s_palm)
    if fore is None or palm is None:
        raise ValueError(f"{side}: the band's ends cut no section")
    ww, wt = spec["wrist_width_ratio"] * fore[2], spec["wrist_thick_ratio"] * fore[3]
    grid = []
    k = 0
    while s_fore + k * 0.002 <= s_palm:
        s = s_fore + k * 0.002
        m = slice_extents(smooth, edges, origin, fr, s)
        if m:
            tu, tv = band_target(s, s_fore, s_palm, fore[2:], palm[2:], ww, wt)
            tt = smoothstep(s_fore, s_palm, s)
            grid.append((s, (fore[0] + (palm[0] - fore[0]) * tt, fore[1] + (palm[1] - fore[1]) * tt,
                             tu / m[2], tv / m[3], m[0], m[1])))
        k += 1
    new = {}
    d, uu, vv = fr
    for i in band:
        s, u, v = coords(smooth[i], origin, fr)
        cu, cv, fu, fv, mu_, mv_ = _interp(grid, s)
        new[i] = add(origin, add(mul(d, s), add(mul(uu, cu + (u - mu_) * fu), mul(vv, cv + (v - mv_) * fv))))
    rep = {"band": len(band), "fore_mm": [round(fore[2] * 2000, 1), round(fore[3] * 2000, 1)],
           "palm_mm": [round(palm[2] * 2000, 1), round(palm[3] * 2000, 1)],
           "wrist_target_mm": [round(ww * 2000, 1), round(wt * 2000, 1)]}
    return new, rep


def polyline_project(p, pts):
    """(s along the polyline, the radial vector from it) for the nearest segment; the ends extend 30 mm."""
    best, acc = None, 0.0
    for k in range(len(pts) - 1):
        a, b = pts[k], pts[k + 1]
        dv = sub(b, a)
        L = math.sqrt(dot(dv, dv))
        t = dot(sub(p, a), dv) / L
        lo = -0.03 if k == 0 else 0.0
        hi = L + 0.03 if k == len(pts) - 2 else L
        t = min(hi, max(lo, t))
        q = add(a, mul(dv, t / L))
        r = sub(p, q)
        dd = dot(r, r)
        if best is None or dd < best[0]:
            best = (dd, acc + t, r, q, norm(dv))
        acc += L
    return best[1], best[2], best[3], best[4]


def gauss_profile(samples, sigma: float):
    """A function s -> the Gaussian-weighted mean of the samples' values [(s, value)]."""
    def f(s):
        num = den = 0.0
        for t, val in samples:
            w = math.exp(-0.5 * ((t - s) / sigma) ** 2)
            num += w * val
            den += w
        return num / den if den else 0.0
    return f


def finger(pos: dict, share: dict, chain_pts, spec: dict) -> tuple:
    """One finger rebuilt (module docstring). share: {index: the vertex's weight on the chain}; chain_pts: the
    chain's joints from the knuckle to the last bone's tail. Returns (new positions, report)."""
    pr = {i: polyline_project(p, chain_pts) for i, p in pos.items()}
    mine = [i for i in pos if share[i] >= 0.5]
    tip = max(pr[i][0] for i in mine)
    meas = gauss_profile([(pr[i][0], math.sqrt(dot(pr[i][1], pr[i][1]))) for i in mine], MEASURE_SIGMA)
    root = spec["root_radius"] if spec.get("root_radius") else finger_root(pos, share, chain_pts, spec["root_at"])
    r_end = root * (1 - spec["taper"])
    s_c = tip - r_end
    ramp0, ramp1 = spec["ramp"]
    new, worst = {}, 0.0
    for i, p in pos.items():
        s, r, q, dirv = pr[i]
        k = smoothstep(ramp0, ramp1, s) * min(1.0, share[i] / 0.7)
        if k <= 0:
            continue
        rl = math.sqrt(dot(r, r))
        target = root + (r_end - root) * min(1.0, max(0.0, s - spec["root_at"]) / max(1e-6, s_c - spec["root_at"]))
        m = meas(min(s, s_c - 0.002))
        tube = add(q, mul(r, target / m)) if rl > 1e-9 and m > 1e-9 else list(p)
        dome_w = smoothstep(s_c - 0.003, s_c + 0.003, s)
        if dome_w > 0:
            c = add(chain_pts[-1], mul(dirv, s_c - _len(chain_pts)))
            dv = sub(p, c)
            sph = add(c, mul(norm(dv), r_end))
            tube = add(mul(tube, 1 - dome_w), mul(sph, dome_w))
        np_ = add(p, mul(sub(tube, p), k))
        worst = max(worst, math.sqrt(dot(sub(np_, p), sub(np_, p))))
        new[i] = np_
    rep = {"verts": len(new), "root_mm": round(root * 2000, 1), "end_mm": round(r_end * 2000, 1),
           "tip_s_mm": round(tip * 1000, 1), "largest_move_mm": round(worst * 1000, 1)}
    return new, rep


def finger_root(pos: dict, share: dict, chain_pts, root_at: float) -> float:
    """The finger's root radius: its measured mean radius averaged over root_at .. root_at + 12 mm."""
    mine = [i for i in pos if share[i] >= 0.5]
    pr = {i: polyline_project(pos[i], chain_pts) for i in mine}
    meas = gauss_profile([(pr[i][0], math.sqrt(dot(pr[i][1], pr[i][1]))) for i in mine], MEASURE_SIGMA)
    xs = [root_at + k * 0.002 for k in range(7)]
    return sum(meas(s) for s in xs) / len(xs)


def _len(pts) -> float:
    return sum(math.dist(pts[k], pts[k + 1]) for k in range(len(pts) - 1))


def hull(points2d):
    pts = sorted(set(points2d))
    if len(pts) < 3:
        return pts

    def turn(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and turn(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and turn(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _seg_dist(p, a, b):
    ab = (b[0] - a[0], b[1] - a[1])
    L = ab[0] ** 2 + ab[1] ** 2
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1]) / L))
    return math.hypot(p[0] - a[0] - t * ab[0], p[1] - a[1] - t * ab[1])


def section(points2d) -> dict:
    """A cross-section's width (u), thickness (v), hull area and the deepest fold (the largest distance of a point
    inside the hull from its boundary: 0 for a convex section, the crease's depth otherwise), all in mm."""
    if len(points2d) < 3:
        return {"n": len(points2d)}
    h = hull(points2d)
    area = 0.5 * abs(sum(h[k][0] * h[k - 1][1] - h[k - 1][0] * h[k][1] for k in range(len(h))))
    fold = max(min(_seg_dist(p, h[k - 1], h[k]) for k in range(len(h))) for p in points2d)
    us, vs = [p[0] for p in points2d], [p[1] for p in points2d]
    return {"n": len(points2d), "w": round((max(us) - min(us)) * 1000, 1), "t": round((max(vs) - min(vs)) * 1000, 1),
            "area_cm2": round(area * 1e4, 2), "fold_mm": round(fold * 1000, 1)}


def row_gaps(ss, lo: float, hi: float) -> float:
    """The largest gap (mm) between the band's vertices along s within lo..hi."""
    xs = sorted(s for s in ss if lo <= s <= hi)
    xs = [lo] + xs + [hi]
    return round(max(b - a for a, b in zip(xs, xs[1:])) * 1000, 1)


def grid_index(pos: dict, cell: float) -> dict:
    """The points {id: p} in a hash grid of the given cell (for nearest-point lookups)."""
    out = {}
    for i, p in pos.items():
        out.setdefault(tuple(int(c // cell) for c in p), []).append((i, p))
    return {"cell": cell, "cells": out}


def grid_nearest(grid: dict, p, tol: float):
    """(id, distance) of the nearest indexed point within tol of p; (None, nearest distance within 3 cells or None)."""
    c = grid["cell"]
    k = tuple(int(x // c) for x in p)
    best, bd = None, None
    for dx in (-3, -2, -1, 0, 1, 2, 3):
        for dy in (-3, -2, -1, 0, 1, 2, 3):
            for dz in (-3, -2, -1, 0, 1, 2, 3):
                for i, q in grid["cells"].get((k[0] + dx, k[1] + dy, k[2] + dz), ()):
                    d = sum((a - b) ** 2 for a, b in zip(p, q)) ** 0.5
                    if bd is None or d < bd:
                        best, bd = i, d
    return (best, bd) if bd is not None and bd <= tol else (None, bd)
