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
  (to our budget) and `mirror_error` (how far a form is from its own mirror).
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
