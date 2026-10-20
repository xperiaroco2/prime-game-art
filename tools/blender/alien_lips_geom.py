"""M8 (art #196): the alien's lips shaped like lips, not two rolls of one thickness. Plain Python (no Blender), used by
alien_mouths.py's build_piece and tested in tools/tests/test_alien_lips_geom.py.

The S6..M6c lips are tubes (closed shapes) or a ring (open shapes) whose half-height follows the sheet's measured
edges, smoothed, with an elliptical section; on the head they read as two sausages of nearly one thickness end to end.
The approved sheets (mf1, mo1) and rf2 show each lip fine at the corners and fullest in the middle, the upper lip
thinner with a soft dip at its centre (a gentle bow), the lower lip a rounder cushion, a defined line where they meet
and the corners tucked into the skin. A lip shape (LIP_SHAPE, or a variant merged over it) is:

- w: how far the designed profile replaces the measured one (0: the M6c lips exactly, 1: the designed profile);
- corner: a lip's thickness at its corners as a share of its centre's; pw: the profile's exponent (T below);
- full: the centre's thickness times this (against the measured centre);
- upper, lower: each lip's thickness times this (the upper thinner, the lower fuller);
- bow: the upper lip's top edge dips at its centre by this share of the upper lip's centre height (bow_w: the dip's
  half width in s), with two soft peaks either side (bow_peak of the dip, at bow_at);
- lean: the section's forward swell moves toward the lip line (the edge where the lips meet) by this share, so both
  lips are fullest at the line and it reads as a crisp crease; square: the section's superellipse exponent (1: an
  ellipse; below 1 a flatter, cushion-like front);
- depth_corner: the share of a lip's constant depth (alien_mouths.DEPTH_C) kept at the corners, so the corners sink
  to a point instead of ending as blunt caps;
- ring: per open shape (A, E, O) the weight of the profile on the ring (O's pucker is round, so less);
- width (M8b): the mouth's width as a share of the sheet-measured one (1: M8's first lips, about 0.8 of the face's
  silhouette at the socket). Every x of a piece (lips, cup, tongue, teeth) is scaled about the face's centre line by
  it (scale_x), its heights are kept, so all six phases narrow together and the corners still meet the skin where
  they now sit (the pieces are laid on the skin by ray casts at the scaled x).

Every edit keeps the lip line where the sheet measured it: the upper lip moves its top edge, the lower lip its bottom
edge, an open ring its outer edge, so the six speech phases keep their openings and stay consistent.
"""
from __future__ import annotations

import math

# The M6c lips (S9's tubes and rings): no change at all.
LIP_SHAPE_M6C = {"w": 0.0}

# The pick (M8's grid, cell c8: corner 0.15, full 1.2, bow 0.30; see docs/godot.md, M8).
LIP_SHAPE = {
    "w": 1.0, "corner": 0.15, "pw": 1.8, "full": 1.2, "upper": 0.82, "lower": 1.12,
    "bow": 0.30, "bow_w": 0.085, "bow_peak": 0.35, "bow_at": 0.20,
    "lean": 0.30, "square": 0.85, "depth_corner": 0.25,
    "ring": {"A": 1.0, "E": 1.0, "O": 0.35},
    "width": 0.72,
}


def merged(over: dict | None) -> dict:
    """LIP_SHAPE with `over` merged on top (the ring weights merged key by key); None or {} is LIP_SHAPE itself."""
    out = dict(LIP_SHAPE)
    out["ring"] = dict(LIP_SHAPE["ring"])
    for k, v in (over or {}).items():
        if k == "ring":
            out["ring"].update(v)
        else:
            out[k] = v
    return out


def scale_x(world, k: float):
    """world(x_px, y_px) -> (x, z) with x scaled by k about the face's centre line (x = 0); world itself for k = 1."""
    if k == 1.0:
        return world

    def scaled(x, y):
        wx, wz = world(x, y)
        return wx * k, wz
    return scaled


def taper(s: float, p: dict) -> float:
    """The thickness along a lip relative to its centre's: 1 at s = 0, p["corner"] at the corners (|s| = 1), a
    pointed lens between (1 - |s|^pw has a finite slope at the end, so the lip ends in a point, not a round cap)."""
    a = min(1.0, abs(s))
    return p["corner"] + (1.0 - p["corner"]) * (1.0 - a ** p["pw"])


def bow(s: float, p: dict) -> float:
    """The upper lip's top-edge offset in shares of its centre height: negative (down) at the centre, a small rise
    at +-bow_at, nothing toward the corners."""
    g = math.exp(-(s / p["bow_w"]) ** 2)
    pk = math.exp(-((abs(s) - p["bow_at"]) / p["bow_w"]) ** 2)
    return p["bow"] * (-g + p["bow_peak"] * pk)


def centre_value(ss, vals, within: float = 0.3) -> float:
    """The median of vals where |s| < within (the lip's measured centre)."""
    mid = sorted(v for s, v in zip(ss, vals) if abs(s) < within)
    if not mid:
        mid = sorted(vals)
    n = len(mid)
    return mid[n // 2] if n % 2 else 0.5 * (mid[n // 2 - 1] + mid[n // 2])


def closed_edges(ss, top, bot, lip: str, p: dict):
    """A closed shape's lip (`u` or `l`) re-profiled: ss the stations' s in [-1, 1], top/bot its measured edges (z, m,
    top > bot). Keeps the lip line (the upper lip's bottom, the lower lip's top) and moves the outer edge to the
    designed thickness: returns (top, bot) lists."""
    w = p.get("w", 0.0)
    if w <= 0.0:
        return list(top), list(bot)
    hb = [(t - b) / 2 for t, b in zip(top, bot)]
    hc = centre_value(ss, hb)
    k = p["upper"] if lip == "u" else p["lower"]
    nt, nb = [], []
    for s, t, b, h in zip(ss, top, bot, hb):
        target = hc * p["full"] * k * taper(s, p)
        h2 = h + w * (target - h)
        if lip == "u":
            t2 = b + 2 * h2 + w * bow(s, p) * 2 * hc * k * p["full"]
            nt.append(max(t2, b + 1e-4))
            nb.append(b)
        else:
            nt.append(t)
            nb.append(t - 2 * h2)
    return nt, nb


def depth_scale(s: float, p: dict) -> float:
    """The share of the constant depth term kept at s (1 at the centre, depth_corner at the corners), blended by w."""
    w = p.get("w", 0.0)
    if w <= 0.0:
        return 1.0
    t = (taper(s, p) - p["corner"]) / max(1e-6, 1.0 - p["corner"])
    return 1.0 + w * (p["depth_corner"] + (1.0 - p["depth_corner"]) * t - 1.0)


def ring_width(th: float, hw: float, hc: float, low: float, shape: str, p: dict) -> float:
    """An open ring's lip half width at angle th (cos th = +-1 at the corners, sin th > 0 the lower lip; low the
    lower lip's share at th): hw measured, hc the ring's measured centre width."""
    w = p.get("w", 0.0) * p.get("ring", {}).get(shape, 1.0)
    if w <= 0.0:
        return hw
    s = math.cos(th)
    k = p["upper"] + (p["lower"] - p["upper"]) * low
    target = hc * p["full"] * k * taper(s, p)
    up = max(0.0, -math.sin(th))  # the upper lip's top centre: the bow
    target *= 1.0 + bow(s, p) * up * up
    return hw + w * (target - hw)


def section(phi: float, lean: float, square: float, toward_line: float) -> tuple[float, float]:
    """A lip's section point at angle phi: (along the skin normal, across) in shares of the half axes. The ellipse
    (cos, sin) with the front made flatter by `square` (a superellipse) and its forward swell moved toward the lip
    line by `lean`: toward_line is +1 when sin(phi) > 0 points at the lip line, -1 when it points away."""
    c, s = math.cos(phi), math.sin(phi)
    cn = math.copysign(abs(c) ** square, c)
    if c > 0:
        cn *= 1.0 + lean * s * toward_line
    return cn, s
