"""Plain-Python geometry of the Meshy body route (art #196, pilot M1; `alien_meshy_body.py`): the Meshy surface kept
as it is and moved onto the refit skeleton. Every function here runs without Blender (tools/tests).

Frames: the Meshy frame is the Meshy GLB's own (x to her left, -y her front, the sole on z 0); the rig frame is the
refit skeleton's (the same axes). The z map (WRAP_Z, pairs [rig z, Meshy z] as in the cage targets) moves each
height; the legs and the arms are then shifted onto their bones, the hands scaled about the wrist.
"""
from __future__ import annotations

import math
import tomllib
from pathlib import Path

TARGETS = Path(__file__).resolve().parent / "alien_meshy_targets"
KEYS = {"name", "meshy", "rig_body", "wrap_z", "arm_x", "arm_band_z", "arm_blend_x", "arm_station_x", "hand",
        "leg_fade_z", "leg_station_z", "foot_z", "ring_z", "ring_half_x", "neck_scale_from_z", "decimate_pre",
        "body_tris", "smooth", "bust", "keep_hands", "smooth_after", "weight_smooth"}
# M1b (art #196): the fixes, each optional (alien_meshy_body.py steps 6 to 10; M1's file has none)
KEYS_M1B = {"degenerate", "arm_thicken", "smooth_rest", "fingers", "bends"}
# M1c (art #196): the knee notch found by its concavity (`notch`); the fingers' M1c keys live inside `fingers`
KEYS_M1C = {"notch"}
FINGER_KEYS_M1C = {"thumb_falloff", "base_band", "base_smooth"}


def load(path: str | Path) -> dict:
    """A Meshy body target file (alien_meshy_targets/*.toml), its keys checked."""
    d = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    bad = set(d) - KEYS - KEYS_M1B - KEYS_M1C
    if bad:
        raise ValueError(f"unknown keys {sorted(bad)}")
    missing = KEYS - set(d)
    if missing:
        raise ValueError(f"missing keys {sorted(missing)}")
    return d


def sstep(a: float, b: float, x: float) -> float:
    """0 at or below a, 1 at or above b, smooth between."""
    if b == a:
        return 0.0 if x < a else 1.0
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def interp(xs: list[float], ys: list[float], x: float) -> float:
    """Piecewise linear through (xs, ys), xs increasing; straight on past both ends (the end segments' slopes)."""
    if len(xs) != len(ys) or len(xs) < 2:
        raise ValueError("two or more points")
    i = 1
    while i < len(xs) - 1 and x > xs[i]:
        i += 1
    x0, x1, y0, y1 = xs[i - 1], xs[i], ys[i - 1], ys[i]
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def z_to_rig(wrap_z: list[list[float]], z: float) -> float:
    """A Meshy height in the rig's frame (WRAP_Z's pairs [rig, meshy], inverted)."""
    return interp([p[1] for p in wrap_z], [p[0] for p in wrap_z], z)


def z_to_meshy(wrap_z: list[list[float]], z: float) -> float:
    """A rig height in the Meshy frame."""
    return interp([p[0] for p in wrap_z], [p[1] for p in wrap_z], z)


def soft_box(p, box: list[float], margin: float) -> float:
    """1 inside [x0, x1, y0, y1, z0, z1], falling to 0 over `margin` outside each face."""
    w = 1.0
    for k in range(3):
        lo, hi = box[2 * k], box[2 * k + 1]
        w *= sstep(lo - margin, lo, p[k]) * (1.0 - sstep(hi, hi + margin, p[k]))
    return w


def soft_sphere(p, c, r: float) -> float:
    """1 at the centre, 0 at and beyond r: (1 - (d / r)^2)^2."""
    d2 = sum((p[k] - c[k]) ** 2 for k in range(3)) / (r * r)
    return (1.0 - d2) ** 2 if d2 < 1.0 else 0.0


def hand_factor(x: float, wrist: float, scale: float, blend: float) -> float:
    """The hand's scale at |x| (Meshy frame): 1 up to the wrist, `scale` from wrist + blend on, smooth between."""
    return 1.0 + (scale - 1.0) * sstep(wrist, wrist + blend, x)


def hand_x(x: float, wrist: float, scale: float, blend: float, steps: int = 64) -> float:
    """The scaled hand's |x|: the wrist plus the integral of hand_factor from the wrist (monotone, no fold)."""
    if x <= wrist:
        return x
    h = (x - wrist) / steps
    return wrist + sum(hand_factor(wrist + (i + 0.5) * h, wrist, scale, blend) for i in range(steps)) * h


def neck_factor(z: float, z0: float, ring_z: float, k: float) -> float:
    """The neck's xy scale about its axis (rig frame): 1 at and below z0, k at the ring, smooth between."""
    return 1.0 + (k - 1.0) * sstep(z0, ring_z, z)


def bust_push(p, n, centre, push: float, radius: float) -> float:
    """The chest's forward push (m, along -y) of a vertex at p with normal n: `push` at the centre [x, z] (each side,
    mirrored), falling to 0 at `radius` in the xz plane, only on front-facing vertices (n.y < 0)."""
    dx, dz = abs(p[0]) - centre[0], p[2] - centre[1]
    d2 = (dx * dx + dz * dz) / (radius * radius)
    if d2 >= 1.0 or n[1] >= 0.0:
        return 0.0
    return push * (1.0 - d2) ** 2 * min(1.0, -n[1] / 0.5)


def pre_ratio(tris: int, target: int) -> float:
    """The first collapse ratio (the whole Meshy mesh down to about `target` triangles), at most 1."""
    if tris <= 0 or target <= 0:
        raise ValueError("positive counts")
    return min(1.0, target / tris)


def body_ratio(body_tris: int, target: int, protected: int = 0) -> float:
    """The collapse ratio that brings a cut body of body_tris to about target, `protected` of them kept."""
    if body_tris <= protected or target <= 0:
        raise ValueError("nothing to collapse")
    return min(1.0, max(0.0, target / body_tris))


def angle_deg(a, b) -> float:
    """The angle between two 3-vectors in degrees."""
    dot = sum(a[k] * b[k] for k in range(3))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return math.degrees(math.acos(max(-1.0, min(1.0, dot / (na * nb)))))
