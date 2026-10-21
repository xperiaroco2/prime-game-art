"""M19 (art #196, brief UPDATE 38): the plain geometry of the AI mouth route's fit (tools/blender/alien_mouth_fit.py),
without Blender: where an AI-made lip form goes on our mouth socket and how it is cleaned.

Frames are the kit's world axes in metres: x across the face (the mirror plane x = 0), y the depth (the face looks
toward -y, so a smaller y sticks out further), z up. Points are (x, y, z) tuples.

- `bbox`, `seam_z` (the lip line of a closed form: the most recessed front row in the middle of its height),
  `align` (one uniform scale and a shift: the form's width to ours, its centre on x = 0, its lip line on ours and its
  front on our front), `apply`;
- `close_back` (the form's back pushed into the skin, so no gap shows behind the lips) and `taper_back` (the
  same with the side curving under, no straight wall), `wrap_weight` (how much of our
  tube follows the AI surface: the front-facing part fully, the part tucked into the skin not at all), `decimate_ratio`
  (to our budget) and `mirror_error` (how far a form is from its own mirror);
- M20 (brief UPDATE 42, the hybrid pout: the AI forms become the kit's closed pieces rest, M and small): `lip_line`
  and `line_at` (the closed form's lip line across its width), `jaw_closed` (the jaw weight of a one-piece closed
  form: the part below the line moves with the jaw, the corners stay), `corner_sink` (the thin ends sit deeper
  under the skin), `stretch` and `stretch_below` (the AI lips' height toward mp1's fullness);
- M20b (brief UPDATE 44, PR #260's review): `reflect`, `to_plane` and `best_plane` (the AI form's own best mirror
  plane, a vertical plane through x0 turned by yaw about z, put on x = 0 before the mirror, so the mirror leaves no
  kink down the lips' middle), `contact_distance` (a skin point inside the closed form touches it).
"""
from __future__ import annotations

import math

FIT = {
    "budget_tris": 6000,  # a piece's triangles after the clean-up (our pout's closed pieces: about 5k)
    "seam_band": (0.25, 0.75),  # seam_z looks for the lip line in this share of the height
    "seam_half_width": 0.12,  # ... in the columns within this share of the width round the centre
    "seam_bins": 48,
    "sink": 0.003,  # close_back: the back goes this far (m) under the skin
    "seat": "back",  # alien_mouth_fit.py: "back" seats the form's flat back on the skin, "front" keeps align's front
    "seat_sink": 0.004,  # ... that far (m) under the skin at the lip line's centre
    "taper": 0.35,  # taper_back: how far a closed-back vertex comes in toward the centre, per depth it went back
    "smooth": 8,  # alien_mouth_fit.py: smoothing passes over the closed back (bmesh smooth_vert, factor 0.5)
    "wrap_lo": -0.15, "wrap_hi": 0.35,  # wrap_weight: n.(-y) from no wrap to the full wrap
    # M20 (the hybrid pout: the AI forms as the kit's closed pieces)
    "line_columns": 12, "line_reach": 0.8, "line_band": 0.2,  # lip_line: columns over the middle 80 %, +-20 % height
    "jaw_band": 0.0015,  # jaw_closed: the smoothstep's half width (m) across the lip line
    "corner_sink": 0.0015, "corner_start": 0.6,  # corner_sink: the ends' extra depth under the skin (m), from 60 %
    "slit_depth": 0.55,  # alien_mouth_fit.py: small's parting, front-seen faces deeper than this share of the depth,
    "slit_band": 0.12, "slit_reach": 0.5,  # ... within this share of the height of its lip line, the middle 50 %
    "closed_align": "centre",  # the closed shapes' height: "centre" (the visible lips' middle) or "line" (seam_z)
    "z_scale": {"rest": 1.10, "M": 1.40, "small": 1.30},  # stretch: the AI lips' height toward mp1's fullness
    "y_follow": 0.5,  # ... the depth stretched by this share of the height's
    "lower_scale": 1.12,  # stretch_below: the closed shapes' lower lip a little fuller (front lower / upper 0.8 -> 0.9)
    # M20b (PR #260's review majors 1-2, minor 4)
    "plane_span": 0.005, "plane_step": 0.0005, "plane_yaws": (-3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0),  # best_plane
    "plane_sample": 6000,  # ... the points it scores (every k-th of the form)
    "mid_band": 0.002, "mid_smooth": 6,  # alien_mouth_fit.py: the band |x| < mid_band smoothed in depth (y) only
    "line_band_z": 0.0012, "line_smooth": 2,  # ... and the lip line's band (+-line_band_z), the facets' specks
    "contact_margin": 0.005,  # contact_distance: an outside skin point's distance less this (m; 2.5 mm: full 52,
    # 3.5 mm: 61 and a pale band still under the lower lip at 3/4)
    "cleft_band": 0.004, "cleft_most": 0.002,  # alien_mouth_fit.py fill_cleft: the lower lip's central groove
    # filled within +-4 mm, a vertex at most 2 mm behind the band edge's front (M20's groove: 0.8-1.4 mm)
    "xy_scale": {"M": (1.04, 0.92)},  # a closed shape's width and depth about its centre / front (minor 4: M wider,
    # pressed flatter; mp1's M in front is as wide as its rest and 0.92 of its height, which M20's already was)
}


def bbox(points) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    pts = list(points)
    if not pts:
        raise ValueError("bbox of no points")
    return (tuple(min(p[i] for p in pts) for i in range(3)), tuple(max(p[i] for p in pts) for i in range(3)))


def seam_z(points, band=None, half_width=None, bins=None) -> float:
    """The lip line of a closed lip form: in the columns near its centre (|x - cx| <= half_width x its width), per
    height bin the front-most depth (the least y); the line is the bin in the band of the height whose front lies
    deepest (the most y) - the groove where the two lips meet. Returns its z (the bin's centre)."""
    band = band or FIT["seam_band"]
    half_width = FIT["seam_half_width"] if half_width is None else half_width
    bins = bins or FIT["seam_bins"]
    lo, hi = bbox(points)
    cx, w, h = (lo[0] + hi[0]) / 2, hi[0] - lo[0], hi[2] - lo[2]
    if h <= 0 or w <= 0:
        raise ValueError("seam_z of a flat form")
    front = [math.inf] * bins
    for x, y, z in points:
        if abs(x - cx) <= half_width * w:
            b = min(bins - 1, int((z - lo[2]) / h * bins))
            front[b] = min(front[b], y)
    cand = [b for b in range(bins) if band[0] <= (b + 0.5) / bins <= band[1] and front[b] < math.inf]
    if not cand:
        raise ValueError("seam_z: no points in the centre columns")
    b = max(cand, key=lambda k: front[k])
    return lo[2] + (b + 0.5) / bins * h


def align(src_lo, src_hi, src_line_z: float, dst_width: float, dst_line_z: float, dst_front_y: float,
          dst_x: float = 0.0) -> tuple[float, tuple[float, float, float]]:
    """One uniform scale s and a shift t (p' = s p + t): the form's width (x) to dst_width, its centre (x) to dst_x,
    its lip line src_line_z to dst_line_z and its front (the least y) to dst_front_y."""
    w = src_hi[0] - src_lo[0]
    if w <= 0 or dst_width <= 0:
        raise ValueError("align: a zero width")
    s = dst_width / w
    cx = (src_lo[0] + src_hi[0]) / 2
    return s, (dst_x - s * cx, dst_front_y - s * src_lo[1], dst_line_z - s * src_line_z)


def apply(points, s: float, t) -> list[tuple[float, float, float]]:
    return [(s * x + t[0], s * y + t[1], s * z + t[2]) for x, y, z in points]


def close_back(y: float, normal_y: float, skin_y: float | None, sink: float | None = None) -> float:
    """A vertex's new depth: a back-facing vertex (its normal toward +y, into the head) in front of the skin goes back
    to sink under it (skin_y + sink), so the form meets the face with no gap; any other vertex, or one where no skin
    was found (skin_y None), stays."""
    sink = FIT["sink"] if sink is None else sink
    if skin_y is None or normal_y <= 0.0:
        return y
    return max(y, skin_y + sink)


def taper_back(p, normal_y: float, skin_y: float | None, centre, depth: float, sink: float | None = None,
               taper: float | None = None) -> tuple[float, float, float]:
    """close_back for a whole vertex, rounding the closed back into the skin instead of a straight wall: a vertex that
    goes back by dy also comes in toward the form's centre (cx, cz) by taper x dy / depth of its distance (at most
    half), so the side of the form curves under like a fillet. Any other vertex stays."""
    taper = FIT["taper"] if taper is None else taper
    x, y, z = p
    y1 = close_back(y, normal_y, skin_y, sink)
    if y1 == y or depth <= 0:
        return (x, y, z)
    k = 1.0 - min(0.5, taper * (y1 - y) / depth)
    return (centre[0] + (x - centre[0]) * k, y1, centre[1] + (z - centre[1]) * k)


def smoothstep(e0: float, e1: float, x: float) -> float:
    if e1 == e0:
        return 1.0 if x >= e1 else 0.0
    u = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return u * u * (3 - 2 * u)


def wrap_weight(normal_y: float, inside_skin: bool) -> float:
    """How far one of our tube's vertices follows the AI surface: by how much its normal faces forward (n . -y,
    smoothstep from wrap_lo to wrap_hi); 0 for a vertex tucked under the skin (it stays where it seals the lips in)."""
    if inside_skin:
        return 0.0
    return smoothstep(FIT["wrap_lo"], FIT["wrap_hi"], -normal_y)


def decimate_ratio(tris: int, budget: int | None = None) -> float:
    """The collapse ratio that takes `tris` triangles to the budget (1.0 when already within it)."""
    budget = budget or FIT["budget_tris"]
    if tris <= 0:
        raise ValueError("decimate_ratio of no triangles")
    return min(1.0, budget / tris)


def lip_line(points, columns: int | None = None, reach: float | None = None, bins: int | None = None) -> list:
    """M20: the lip line of a closed form across its width, as (x, z) knots: per column of the middle `reach` share of
    the width (columns of them), the groove the way seam_z finds it in the centre (the deepest front in the height
    band), searched only within FIT["line_band"] of the height round the centre's line, so a column never jumps to the
    form's top or bottom edge; the two ends are the form's corners at the centre's line height."""
    columns = columns or FIT["line_columns"]
    reach = FIT["line_reach"] if reach is None else reach
    bins = bins or FIT["seam_bins"]
    pts = list(points)
    lo, hi = bbox(pts)
    cx, w, h = (lo[0] + hi[0]) / 2, hi[0] - lo[0], hi[2] - lo[2]
    z0 = seam_z(pts)
    knots = [(lo[0], z0)]
    for c in range(columns):
        x0 = cx - reach * w / 2 + reach * w * c / columns
        x1 = x0 + reach * w / columns
        front = [math.inf] * bins
        for x, y, z in pts:
            if x0 <= x < x1:
                b = min(bins - 1, int((z - lo[2]) / h * bins))
                front[b] = min(front[b], y)
        cand = [b for b in range(bins) if abs(lo[2] + (b + 0.5) / bins * h - z0) <= FIT["line_band"] * h
                and front[b] < math.inf]
        z = z0 if not cand else lo[2] + (max(cand, key=lambda k: front[k]) + 0.5) / bins * h
        knots.append(((x0 + x1) / 2, z))
    knots.append((hi[0], z0))
    # mirrored and lightly smoothed: the form is symmetric, a column's bin step should not show as a kink
    zs = [k[1] for k in knots]
    zs = [(a + b) / 2 for a, b in zip(zs, reversed(zs))]
    sm = [zs[0]] + [(zs[i - 1] + 2 * zs[i] + zs[i + 1]) / 4 for i in range(1, len(zs) - 1)] + [zs[-1]]
    return [(k[0], z) for k, z in zip(knots, sm)]


def line_at(knots, x: float) -> float:
    """The lip line's height at x (linear between the knots, held beyond the ends)."""
    if x <= knots[0][0]:
        return knots[0][1]
    for (xa, za), (xb, zb) in zip(knots, knots[1:]):
        if x <= xb:
            return za if xb == xa else za + (zb - za) * (x - xa) / (xb - xa)
    return knots[-1][1]


def jaw_closed(p, knots, centre_x: float, half_w: float, band: float, jaw: dict) -> float:
    """M20: the jaw weight of a closed one-piece form's vertex (alien_m12.jaw_weights' rule for two tubes, made
    smooth): 0 above the lip line, 1 below it, a smoothstep across `band` metres either side, times jaw's falloff
    toward the corners (jaw "from" and "corner" as alien_m12.JAW: the corners stay put)."""
    x, _y, z = p
    zl = line_at(knots, x)
    g = smoothstep(zl + band, zl - band, z)
    u = min(1.0, max(0.0, (abs(x - centre_x) / (half_w or 1.0) - jaw["from"]) / (1.0 - jaw["from"])))
    return g * (1.0 - (1.0 - jaw["corner"]) * u * u * (3 - 2 * u))


def corner_sink(x: float, centre_x: float, half_w: float, depth: float | None = None, start: float | None = None) -> float:
    """M20: how much further (m) the closed back goes under the skin at x: 0 inside `start` of the half width, rising
    smoothly to `depth` at the corner (the thin ends sit deeper, so no glossy rim of the back shows where they meet
    the skin)."""
    depth = FIT["corner_sink"] if depth is None else depth
    start = FIT["corner_start"] if start is None else start
    return depth * smoothstep(start, 1.0, abs(x - centre_x) / (half_w or 1.0))


def stretch(points, line_z: float, front_y: float, kz: float, ky: float) -> list:
    """M20: the points stretched about the lip line (z) by kz and back from the front (y) by ky; x unchanged."""
    return [(x, front_y + (y - front_y) * ky, line_z + (z - line_z) * kz) for x, y, z in points]


def stretch_below(points, line_z: float, k: float) -> list:
    """M20: the part below the lip line stretched down by k (heights under line_z times k); the rest unchanged."""
    return [(x, y, z if z >= line_z else line_z + (z - line_z) * k) for x, y, z in points]


def reflect(p, x0: float, yaw_deg: float) -> tuple[float, float, float]:
    """M20b: p mirrored in the vertical plane through (x0, *, *) whose normal is x turned by yaw (degrees) about z."""
    a = math.radians(yaw_deg)
    nx, ny = math.cos(a), math.sin(a)
    d = (p[0] - x0) * nx + p[1] * ny
    return (p[0] - 2 * d * nx, p[1] - 2 * d * ny, p[2])


def to_plane(points, x0: float, yaw_deg: float) -> list:
    """M20b: the points moved so the plane (x0, yaw) becomes x = 0: turned by -yaw about z round (x0, 0), shifted by
    -x0."""
    a = math.radians(-yaw_deg)
    c, s = math.cos(a), math.sin(a)
    return [((x - x0) * c - y * s, (x - x0) * s + y * c, z) for x, y, z in points]


def best_plane(points, nearest, span: float | None = None, step: float | None = None, yaws=None):
    """M20b: the vertical mirror plane (x0, yaw) that a form fits best: the least mean distance from each point's
    reflection to the form (nearest(q) -> distance), over x0 in +-span by step and the yaws, then a finer x0 step
    round the best. Returns (x0, yaw, mean distance)."""
    span = FIT["plane_span"] if span is None else span
    step = FIT["plane_step"] if step is None else step
    yaws = FIT["plane_yaws"] if yaws is None else yaws
    pts = list(points)

    def cost(x0, yaw):
        return sum(nearest(reflect(p, x0, yaw)) for p in pts) / len(pts)

    n = int(round(span / step))
    best = min(((cost(k * step, y), k * step, y) for k in range(-n, n + 1) for y in yaws))
    fine = min((cost(best[1] + k * step / 5, best[2]), best[1] + k * step / 5, best[2]) for k in range(-4, 5))
    return fine[1], fine[2], fine[0]


def contact_distance(dist: float, inside: bool, margin: float | None = None) -> float:
    """M20b: the distance the skin's contact field takes for a skin point dist m from a closed lip form: 0 inside it
    (the form's back goes 3-4 mm under the skin, so a point under the lips was 3-4 mm from the nearest surface and its
    contact stayed near half: PR #260's `full` 0), else dist less margin."""
    margin = FIT["contact_margin"] if margin is None else margin
    return 0.0 if inside else max(0.0, dist - margin)


def mirror_error(points, cell: float = 0.002) -> float:
    """The largest distance (m) from a point's mirror (-x, y, z) to the nearest point of the set: 0 for an exact mirror.
    A grid of `cell` metres keeps it near linear; a mirror farther than one cell from every point counts the
    distance to the nearest point of the 27 cells round it, or `cell` x 2 when there is none."""
    pts = list(points)
    grid: dict[tuple[int, int, int], list] = {}
    for p in pts:
        grid.setdefault(tuple(int(math.floor(c / cell)) for c in p), []).append(p)
    worst = 0.0
    for x, y, z in pts:
        q = (-x, y, z)
        k = tuple(int(math.floor(c / cell)) for c in q)
        best = math.inf
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for r in grid.get((k[0] + dx, k[1] + dy, k[2] + dz), ()):
                        best = min(best, math.dist(q, r))
        worst = max(worst, best if best < math.inf else 2 * cell)
    return worst
