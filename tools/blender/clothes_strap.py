"""The new straps' strip maths, pure (art #196, clothes step 2, C1e; no bpy, unittest-tested in
tools/tests/test_clothes_strap.py). clothes_top.py's straps imports it.

- the path's values smoothed with its ends held (smooth_open);
- per station a frame (frames): the path's tangent, the body's normal and the strip's width direction across, and
  the arc length along it (arcs);
- the strip is a grid of quads (strip_quads) with UVs on a clean denim patch, mirrored along the strap's length
  (mirror_v) so the twill keeps its texel density.

C1e's rebuild of the Meshy straps in place and the sleeves' smoothing were dropped for the hybrid route; their code
went in C1h.
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


