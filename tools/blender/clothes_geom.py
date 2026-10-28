"""The clothes step's pure maths (art #196, clothes step 2; no bpy, unittest-tested in tools/tests):
cutting a turnaround sheet into its views, telling skin from cloth by a texel's colour, and the fit numbers against
the base body. The Blender scripts clothes_views.py, clothes_clean.py and clothes_measure.py import it.
"""
from __future__ import annotations

import colorsys

# The aliens' skin is teal with mint at the face and palms: in Meshy's textures (batch 2026-10-28-alien-clothes-m1)
# hue 120-195 degrees at value 0.45-0.8, saturated enough to tell it from the white stripes and the off-white shoes.
# Denim reaches down to hue 200 but is dark (value 0.12-0.23); navy stripes (about 220-235) and burgundy (about
# 340-355) fall outside the hues.
SKIN_HUE = (115.0, 196.0)
SKIN_SAT = 0.10
SKIN_VAL = 0.30


def spans(occupied: list[bool], min_gap: int = 8, min_width: int = 40) -> list[tuple[int, int]]:
    """The runs of True in occupied as (start, end) with end exclusive; runs closer than min_gap are joined, runs
    narrower than min_width dropped (specks of the sheet's shadow or noise)."""
    runs: list[list[int]] = []
    for i, on in enumerate(occupied):
        if not on:
            continue
        if runs and i - runs[-1][1] < min_gap:
            runs[-1][1] = i + 1
        else:
            runs.append([i, i + 1])
    return [(a, b) for a, b in runs if b - a >= min_width]


def common_square(boxes: list[tuple[int, int, int, int]], margin: float = 0.06) -> int:
    """The side of one square that holds every box (x0, y0, x1, y1; end exclusive) with margin on every side."""
    big = max(max(x1 - x0, y1 - y0) for x0, y0, x1, y1 in boxes)
    return int(round(big * (1.0 + 2.0 * margin)))


def place(box: tuple[int, int, int, int], side: int, ground: int) -> tuple[int, int]:
    """Where box's top left corner goes in a square of side px (y down): centred across, its bottom on the row ground,
    so every view of a sheet has the same scale and ground line."""
    x0, y0, x1, y1 = box
    return (side - (x1 - x0)) // 2, ground - (y1 - y0)


def is_skin(r: float, g: float, b: float) -> bool:
    """True when the sRGB colour (0..1) is the alien's teal or mint skin."""
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    hue = h * 360.0
    return SKIN_HUE[0] <= hue <= SKIN_HUE[1] and s >= SKIN_SAT and v >= SKIN_VAL


def majority(votes: list[bool], share: float = 0.5) -> bool:
    """True when more than share of votes are True (a face is skin when most of its texel samples are)."""
    return bool(votes) and sum(votes) > share * len(votes)


def band(values: list[float], lo: float, hi: float) -> tuple[float, float] | None:
    """The (min, max) of the values inside [lo, hi], or None when none is (a width at one height band)."""
    inside = [v for v in values if lo <= v <= hi]
    return (min(inside), max(inside)) if inside else None


def fit_lines(cloth: dict[str, float], body: dict[str, float]) -> dict[str, dict[str, float]]:
    """Per named line (height, shoulder width, ...) the cloth's value, the body's, their difference and ratio."""
    out = {}
    for key in sorted(set(cloth) & set(body)):
        c, b = cloth[key], body[key]
        out[key] = {"cloth": round(c, 4), "body": round(b, 4), "diff": round(c - b, 4),
                    "ratio": round(c / b, 4) if b else 0.0}
    return out


def colour_cut(zs: list[float], strong: list[bool], floor: float = 0.04, step: float = 0.01,
               share: float = 0.5) -> float:
    """The height (m) where the shoes end and a hem sitting on them begins: the bottom of the lowest step-tall band
    above floor (under it the soles) in which more than share of the faces are strong (saturated: the hem's colour,
    not the white shoes). Falls back to floor when no band is."""
    top = max(zs) if zs else floor
    z = floor
    while z < top:
        votes = [s for h, s in zip(zs, strong) if z <= h < z + step]
        if len(votes) >= 8 and majority(votes, share):
            return round(z, 4)
        z += step
    return floor
