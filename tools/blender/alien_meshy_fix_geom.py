"""The plain maths of M1b (art #196): the fixes to the Meshy body route's axolotl (`alien_meshy_body.py`, the
`fingers`, `bends`, `arm_thicken`, `degenerate` and `smooth_rest` keys of a target file). No Blender, no numpy.

- `label_fingers`: each free finger's vertices (cut levels swept down the hand: a part beyond the cut holding one tip).
- `fit_line`: a straight centre line through slice centres (least squares, the parameter along it).
- `ownership`: a palm vertex's pull toward each finger's line.
- `chain_weights`: a finger chain's bone weights by the parameter along the chain, soft over each joint.
- `pick_crease`: a joint on the finger's thinnest slice near its proportional guess.
- `keep_roll_z`: a re-aimed bone's z axis kept as near the old one as the new direction allows.
- `ring_share`: a joint's child share across its band; `ring_blend`: a vertex's weights with the ring applied.
- `profile`: a piecewise-linear factor along the arm.
"""
from __future__ import annotations

import math

FINGERS = ("Thumb", "Index", "Middle", "Ring", "Little")
CHAIN = {"Thumb": ("Metacarpal", "Proximal", "Distal")}
CHAIN_DEFAULT = ("Proximal", "Intermediate", "Distal")


def chain_names(side: str, finger: str) -> list[str]:
    """The contract's bone names of one finger, root first (`LeftThumbMetacarpal`, ...)."""
    return [f"{side}{finger}{s}" for s in CHAIN.get(finger, CHAIN_DEFAULT)]


def sstep(a: float, b: float, x: float) -> float:
    if b == a:
        return 0.0 if x < a else 1.0
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def components(nodes, adj) -> list[list[int]]:
    """The connected parts of the sub-graph on `nodes` (adj: vertex -> neighbours)."""
    left, out = set(nodes), []
    while left:
        s = left.pop()
        stack, part = [s], [s]
        while stack:
            u = stack.pop()
            for w in adj.get(u, ()):
                if w in left:
                    left.remove(w)
                    stack.append(w)
                    part.append(w)
        out.append(part)
    return out


def label_fingers(x: dict, adj: dict, step: float = 0.001, min_part: int = 6) -> tuple[dict, dict]:
    """Each free finger of a hand: x maps each hand vertex to its coordinate along the hand (|x| from the wrist out).
    Cuts swept from the outermost vertex inward by `step`: a part beyond the cut holding no tip yet (and at least
    `min_part` vertices) gets a new tip (its outermost vertex); a part holding exactly one tip labels its vertices
    with it; once two tips share a part, both stop growing. Returns ({vertex: tip}, {tip: the cut where it stopped})."""
    if not x:
        return {}, {}
    top, low = max(x.values()), min(x.values())
    label: dict = {}
    tips: list = []
    stopped: dict = {}
    level = top - step
    while level > low:
        parts = components([v for v, c in x.items() if c > level], adj)
        for part in parts:
            held = [t for t in tips if t in set(part)] if tips else []
            if not held:
                if len(part) >= min_part:
                    t = max(part, key=lambda v: x[v])
                    tips.append(t)
                    held = [t]
                else:
                    continue
            if len(held) == 1 and held[0] not in stopped:
                for v in part:
                    label[v] = held[0]
            elif len(held) > 1:
                for t in held:
                    stopped.setdefault(t, level)
        if len(stopped) == len(tips) and tips:
            break
        level -= step
    for t in tips:
        stopped.setdefault(t, level)
    return label, stopped


def fit_line(points: list) -> tuple[list, list]:
    """A straight line through 3D points: (a point on it, its unit direction), the direction the points' main axis
    (power iteration on the covariance), pointing from the first point toward the last."""
    n = len(points)
    c = [sum(p[k] for p in points) / n for k in range(3)]
    cov = [[sum((p[i] - c[i]) * (p[j] - c[j]) for p in points) for j in range(3)] for i in range(3)]
    d = [points[-1][k] - points[0][k] for k in range(3)]
    if math.sqrt(sum(v * v for v in d)) < 1e-12:
        d = [1.0, 0.0, 0.0]
    for _ in range(60):
        d = [sum(cov[i][j] * d[j] for j in range(3)) for i in range(3)]
        m = math.sqrt(sum(v * v for v in d)) or 1.0
        d = [v / m for v in d]
    if sum(d[k] * (points[-1][k] - points[0][k]) for k in range(3)) < 0:
        d = [-v for v in d]
    return c, d


def along(p, c, d) -> float:
    return sum((p[k] - c[k]) * d[k] for k in range(3))


def off_line(p, c, d) -> float:
    s = along(p, c, d)
    return math.sqrt(sum((p[k] - c[k] - s * d[k]) ** 2 for k in range(3)))


def ownership(dist: float, eps: float, power: float = 4.0) -> float:
    """A palm vertex's pull toward a finger's line: 1 / (dist + eps)^power (normalised by the caller over the chains
    and the palm's own pull, ownership(palm_r, 0)): smooth, unlike a Gaussian's ratios, and local."""
    return 1.0 / (dist + eps) ** power


def chain_weights(s: float, joints: list[float], half: list[float]) -> list[float]:
    """The weights of len(joints) + 1 bones (the parent first) at the parameter s along a chain whose child bones
    start at `joints` (increasing): each joint passes the weight on over [j - h, j + h] by a smoothstep. Sums to 1."""
    w = [1.0]
    for j, h in zip(joints, half):
        t = sstep(j - h, j + h, s)
        w = [v * (1.0 - t) for v in w[:-1]] + [w[-1] * (1.0 - t), w[-1] * t]
    return w


def pick_crease(samples: list, guess: float, window: float) -> float:
    """The joint's parameter: the thinnest sample (s, thickness) within `window` of `guess` when it is a local
    minimum inside the window (a crease), else the guess."""
    inside = [(s, t) for s, t in samples if abs(s - guess) <= window]
    if len(inside) < 3:
        return guess
    k = min(range(len(inside)), key=lambda i: inside[i][1])
    if k in (0, len(inside) - 1):
        return guess
    return inside[k][0]


def keep_roll_z(old_z, new_y) -> list[float]:
    """The z axis nearest to old_z that is square to new_y (old_z less its part along new_y, unit length)."""
    m = math.sqrt(sum(v * v for v in new_y))
    y = [v / m for v in new_y]
    dot = sum(a * b for a, b in zip(old_z, y))
    z = [a - dot * b for a, b in zip(old_z, y)]
    n = math.sqrt(sum(v * v for v in z))
    if n < 1e-6:  # old z along the new direction: any square axis
        z = [y[1], -y[0], 0.0] if abs(y[2]) < 0.9 else [0.0, y[2], -y[1]]
        n = math.sqrt(sum(v * v for v in z))
    return [v / n for v in z]


def ring_share(u: float, width: float, offset: float = 0.0) -> float:
    """A joint's child share at the signed distance u past the joint along the child bone: 0 at offset - width,
    1 at offset + width."""
    return sstep(offset - width, offset + width, u)


def ring_blend(weights: dict, child_family: set, parent: str, child: str, share: float, blend: float) -> dict:
    """A vertex's weights (group -> weight) with the joint's ring share applied: the child family (the child and its
    descendants) together `share`, the rest `1 - share`, each side in its old proportions (all to `child` or `parent`
    when that side held none); then mixed with the old weights by `blend` (0 the old, 1 the ring). Sums to 1."""
    tot = sum(weights.values()) or 1.0
    old = {g: w / tot for g, w in weights.items()}
    fam = {g: w for g, w in old.items() if g in child_family}
    rest = {g: w for g, w in old.items() if g not in child_family}
    sf, sr = sum(fam.values()), sum(rest.values())
    ring = {}
    for g, w in (fam.items() if sf > 1e-9 else [(child, 1.0)]):
        ring[g] = ring.get(g, 0.0) + share * w / (sf if sf > 1e-9 else 1.0)
    for g, w in (rest.items() if sr > 1e-9 else [(parent, 1.0)]):
        ring[g] = ring.get(g, 0.0) + (1.0 - share) * w / (sr if sr > 1e-9 else 1.0)
    out = {}
    for g in set(old) | set(ring):
        v = (1.0 - blend) * old.get(g, 0.0) + blend * ring.get(g, 0.0)
        if v > 1e-6:
            out[g] = v
    s = sum(out.values())
    return {g: v / s for g, v in out.items()}


def profile(stations: list[list[float]], x: float) -> float:
    """A factor along the arm from [x, factor] stations (sorted), held flat beyond the ends."""
    if x <= stations[0][0]:
        return stations[0][1]
    for (x0, f0), (x1, f1) in zip(stations, stations[1:]):
        if x <= x1:
            return f0 + (f1 - f0) * (x - x0) / (x1 - x0)
    return stations[-1][1]


# M1c (art #196): the thumb's base, the fingers' bases and the knee's notch.

def thumb_share(dist: float, falloff: list[float]) -> float:
    """A palm vertex's share for the thumb's chain by its distance from the thumb's line: 1 inside falloff[0], a
    smoothstep down to 0 at falloff[1] (the thenar follows the metacarpal softly into the palm, no step to stretch)."""
    return 1.0 - sstep(falloff[0], falloff[1], dist)


def split_palm(g_others: list[float], palm_pull: float, t: float) -> tuple[list[float], float]:
    """The palm vertex's ownership with the thumb's share t taken first: the other chains' pulls normalised against
    the palm's own pull, scaled by 1 - t; returns (their shares, the pure Hand share). The shares and t sum to 1 with
    the Hand's."""
    tot = sum(g_others) + palm_pull
    rest = [(1.0 - t) * g / tot for g in g_others]
    return rest, 1.0 - t - sum(rest)


def in_base_band(s: float, s_base: float, band: float) -> bool:
    """A free finger's vertex within `band` of its web (s along its line): it joins the palm's smoothing."""
    return s < s_base + band


def notch_pick(cands: list[tuple[float, tuple]]) -> tuple:
    """The notch's centre: the candidate (depth, xyz) with the deepest inward offset from its neighbours' mean."""
    return max(cands, key=lambda c: c[0])[1]


# M2b (art #196): the fingers' shape and the seat's depth.

def finger_radial(s: float, s_base: float, s_tip: float, shape: dict) -> float:
    """A free finger's radial factor at s along its line: 1 at the web, 1 - slim past `ramp` (m), and the tip's
    last `tip_len` (m) a further 1 - tip (smaller tip balls; reached at half tip_len before the end)."""
    k = 1.0 - shape.get("slim", 0.0) * sstep(s_base, s_base + shape["ramp"], s)
    tl = shape.get("tip_len", 0.0)
    if tl > 0:
        k *= 1.0 - shape.get("tip", 0.0) * sstep(s_tip - tl, s_tip - tl / 2, s)
    return k


def finger_point(p, centre_s, centre_base, k: float, length: float):
    """A finger vertex moved: its offset from its slice's centre scaled by k, the centre moved toward the web's
    centre by the length factor (1: the finger's length kept; the thumb's 1 - thumb_shorten)."""
    c = [b + (a - b) * length for a, b in zip(centre_s, centre_base)]
    return [ci + (pi - ai) * k for ci, pi, ai in zip(c, p, centre_s)]


def seat_y(y: float, base: float, w: float, depth: float, ramp: float) -> float:
    """The seat's back y: its depth d behind the base line scaled to `depth` (weight w), eased in over `ramp` (m) so
    the surface keeps its slope at the line (d - w (1 - depth) d sstep(0, ramp, d))."""
    d = y - base
    if d <= 0 or w <= 0:
        return y
    return base + d - w * (1.0 - depth) * d * sstep(0.0, ramp, d)


def thumb_radial(s: float, s_base: float, shape: dict) -> float:
    """M1d: the thumb's radial factor at s along its line: 1 at the web, `thumb_thick` past `ramp` (m) from it (a
    thicker thumb, eased in so the thenar keeps its join)."""
    return 1.0 + (shape.get("thumb_thick", 1.0) - 1.0) * sstep(s_base, s_base + shape["ramp"], s)


def height_smooth(uv, h, area, sigma: float) -> list[float]:
    """M1d: a heightfield's heights h over the points uv blurred by a Gaussian of `sigma` (m), each point weighted by
    its area: the tip spreads and the volume (the sum of area * h) stays near what it was."""
    out = []
    for u0, v0 in uv:
        num = den = 0.0
        for (u, v), hj, aj in zip(uv, h, area):
            g = aj * math.exp(-((u - u0) ** 2 + (v - v0) ** 2) / (2.0 * sigma * sigma))
            num += g * hj
            den += g
        out.append(num / den if den > 0 else 0.0)
    return out


def tip_radius(r: list[float], h: list[float], r_max: float) -> float:
    """M1d: the tip's radius of curvature from its heights h (<= 0 below the apex) at planar distances r: the least
    squares fit h = h0 - r^2 / (2 rho) over r < r_max; returns rho (m), inf for a flat tip."""
    pts = [(ri * ri, hi) for ri, hi in zip(r, h) if ri < r_max]
    n = len(pts)
    if n < 3:
        return math.inf
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pts)
    if sxx <= 0 or sxy >= 0:
        return math.inf
    return -1.0 / (2.0 * sxy / sxx)


def width_factor(x: float, xs: list[float], measured: list[float], target: list[list[float]], lo: float,
                 hi: float) -> float | None:
    """M1d: the arm's scale at |x| toward a target front width: target(x) / measured(x) (both interpolated), clamped
    to [lo, hi]; None outside the target's range (the profile then rules)."""
    tx = [p[0] for p in target]
    if x < tx[0] or x > tx[-1]:
        return None
    t = profile(target, x)
    m = profile([[a, b] for a, b in zip(xs, measured)], x)
    if m <= 0:
        return None
    return min(hi, max(lo, t / m))


def keep_volume(dh: list[float], w: list[float], area: list[float]) -> list[float]:
    """M1d: the blur's moves dh (a convex tip only comes down) lifted by c * w, the blend's own shares, so that the
    sum of area * dh is 0: the tip keeps its volume, the core (w 1) lifted evenly and its rounding kept."""
    den = sum(a * x for a, x in zip(area, w))
    if den <= 0:
        return list(dh)
    c = -sum(a * d for a, d in zip(area, dh)) / den
    return [d + c * x for d, x in zip(dh, w)]
