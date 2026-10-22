"""The alien 3D pilot's pure geometry, step 2a (art #196): no bpy, so tools/tests runs it without Blender.

alien_pilot_head.py (in headless Blender) uses it to find the painted eyes on Meshy's fused head (a sphere fitted to
the eye's pixels' surface), the lip line (the deepest valley between the two lips in the front profile), the gill
stalks (clusters of points), to build the lids as spherical shells around the new eyeballs and to paint the eyeball's
texture.
"""
from __future__ import annotations

import math
from typing import Iterable, Sequence

Vec = tuple[float, float, float]


def solve(a: list[list[float]], b: list[float]) -> list[float]:
    """Solves a x = b (square, Gaussian elimination with partial pivoting); raises ValueError when singular."""
    n = len(b)
    m = [list(map(float, row)) + [float(b[i])] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-12:
            raise ValueError("singular system")
        m[col], m[piv] = m[piv], m[col]
        for r in range(col + 1, n):
            f = m[r][col] / m[col][col]
            for c in range(col, n + 1):
                m[r][c] -= f * m[col][c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (m[r][n] - sum(m[r][c] * x[c] for c in range(r + 1, n))) / m[r][r]
    return x


def fit_sphere(points: Sequence[Vec]) -> tuple[Vec, float]:
    """Least-squares sphere through points: |p|^2 = 2 c.p + d, so centre c and radius sqrt(d + |c|^2)."""
    if len(points) < 4:
        raise ValueError("a sphere needs at least 4 points")
    ata = [[0.0] * 4 for _ in range(4)]
    atb = [0.0] * 4
    for x, y, z in points:
        row = (2 * x, 2 * y, 2 * z, 1.0)
        rhs = x * x + y * y + z * z
        for i in range(4):
            atb[i] += row[i] * rhs
            for j in range(4):
                ata[i][j] += row[i] * row[j]
    cx, cy, cz, d = solve(ata, atb)
    return (cx, cy, cz), math.sqrt(max(d + cx * cx + cy * cy + cz * cz, 0.0))


def smoothstep(e0: float, e1: float, x: float) -> float:
    t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def ellipsoid_weight(p: Vec, centre: Vec, radii: Vec, core: float = 0.35) -> float:
    """1 inside the core fraction of the ellipsoid, falling smoothly to 0 at its surface."""
    d = math.sqrt(sum(((p[i] - centre[i]) / radii[i]) ** 2 for i in range(3)))
    return 1.0 - smoothstep(core, 1.0, d)


def clusters(points: Sequence[Vec], link: float) -> list[list[int]]:
    """Groups point indices whose chains of neighbours lie within link of each other (a grid hash and union-find);
    largest first."""
    parent = list(range(len(points)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    grid: dict[tuple[int, int, int], list[int]] = {}
    for i, p in enumerate(points):
        grid.setdefault(tuple(int(math.floor(c / link)) for c in p), []).append(i)
    l2 = link * link
    for (gx, gy, gz), members in grid.items():
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for j in grid.get((gx + dx, gy + dy, gz + dz), ()):
                        for i in members:
                            if i < j and sum((points[i][k] - points[j][k]) ** 2 for k in range(3)) <= l2:
                                ri, rj = find(i), find(j)
                                if ri != rj:
                                    parent[ri] = rj
    groups: dict[int, list[int]] = {}
    for i in range(len(points)):
        groups.setdefault(find(i), []).append(i)
    return sorted(groups.values(), key=len, reverse=True)


def valley(profile: Sequence[float]) -> tuple[int, float]:
    """The index of the deepest valley in profile (how far forward the surface reaches per height bin) and its
    prominence: min(highest before, highest after) - value. (-1, 0.0) when there is none."""
    best, best_prom = -1, 0.0
    for i in range(1, len(profile) - 1):
        prom = min(max(profile[:i]), max(profile[i + 1:])) - profile[i]
        if prom > best_prom:
            best, best_prom = i, prom
    return best, best_prom


def frame(forward: Vec, up: Vec = (0.0, 0.0, 1.0)) -> tuple[Vec, Vec, Vec]:
    """An orthonormal (forward, side, up) frame with up made perpendicular to forward."""
    f = normalize(forward)
    d = sum(up[i] * f[i] for i in range(3))
    u = normalize(tuple(up[i] - d * f[i] for i in range(3)))
    s = (f[1] * u[2] - f[2] * u[1], f[2] * u[0] - f[0] * u[2], f[0] * u[1] - f[1] * u[0])
    return f, s, u


def normalize(v: Iterable[float]) -> Vec:
    v = tuple(v)
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


def shell_point(centre: Vec, axes: tuple[Vec, Vec, Vec], radius: float, alpha: float, beta: float) -> Vec:
    """A point on the sphere around centre: alpha the horizontal angle from forward toward side, beta the vertical
    angle from the eye's horizontal plane toward up (radians)."""
    f, s, u = axes
    cb = math.cos(beta)
    return tuple(centre[i] + radius * (cb * math.cos(alpha) * f[i] + cb * math.sin(alpha) * s[i] + math.sin(beta) * u[i])
                 for i in range(3))


def lid_grid(beta_from: float, beta_to: float, alpha_half: float, n_alpha: int, n_beta: int) -> list[list[tuple[float, float]]]:
    """Rows of (alpha, beta) in radians for a lid shell: beta from its free edge (beta_from) to its root (beta_to);
    the free edge is row 0."""
    return [[(-alpha_half + 2 * alpha_half * a / n_alpha, beta_from + (beta_to - beta_from) * b / n_beta)
             for a in range(n_alpha + 1)] for b in range(n_beta + 1)]


def eye_pixel(v: float, u: float, spec: dict) -> tuple[float, float, float]:
    """The eyeball texture's sRGB colour at (u, v): v the polar angle from the gaze pole / pi, u the azimuth / 2 pi.
    spec: iris_deg, pupil_deg, sclera, iris, iris_rim, pupil, glint (u, v, radius in v units) or absent."""
    ang = v * 180.0
    if ang <= spec["pupil_deg"]:
        col = spec["pupil"]
    elif ang <= spec["iris_deg"]:
        t = (ang - spec["pupil_deg"]) / (spec["iris_deg"] - spec["pupil_deg"])
        col = tuple(spec["iris"][i] * (1 - t * t) + spec["iris_rim"][i] * t * t for i in range(3))
    else:
        t = smoothstep(spec["iris_deg"], spec["iris_deg"] + 3.0, ang)
        col = tuple(spec["iris_rim"][i] * (1 - t) + spec["sclera"][i] * t for i in range(3))
    glint = spec.get("glint")
    if glint:
        gu, gv, gr = glint
        du = min(abs(u - gu), 1 - abs(u - gu)) * 2 * math.pi * math.sin(max(v, 1e-3) * math.pi) / math.pi
        if math.hypot(du, v - gv) < gr:
            col = (1.0, 1.0, 1.0)
    return col


def channel_gains(have: Sequence[float], want: Sequence[float], low: float = 0.7, high: float = 2.2) -> Vec:
    """Per-channel gains taking the median colour have (sRGB 0-1) to want, clamped to [low, high]."""
    return tuple(min(max(want[i] / max(have[i], 1e-4), low), high) for i in range(3))


def luminance(rgb: Sequence[float]) -> float:
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def grade_gains(have: Sequence[float], want: Sequence[float], chroma: float = 0.3, low: float = 0.7,
                high: float = 2.0) -> Vec:
    """Gains taking the median colour have toward want: the luminance ratio for all channels (keeps each region's hue,
    so the mint face stays mint) times a part (chroma, 0-1) of each channel's own ratio over it."""
    g = luminance(want) / max(luminance(have), 1e-4)
    return tuple(min(max(g * ((want[i] / max(have[i], 1e-4)) / g) ** chroma, low), high) for i in range(3))
