"""The female variant of the shared alien body (art #196, clothes step 2): the same mesh, the same topology, vertex
order, weights and skeleton, only vertex positions moved by a few smooth, compactly supported fields. No bpy: the
maths and the target file's checks, tested in tools/tests/test_alien_female_geom.py; alien_body_female.py applies it.

The frame is the body's: x lateral (the body is mirror-symmetric in x), z up from the sole, f forward from the trunk's
centre line at that height (the Hips-Spine-Chest-Neck bone chain). Each field is a product of kernels
k(t) = (1 - t^2)^2 for |t| < 1, else 0 (C1, exactly zero outside its box), so nothing outside the boxes moves:
- chest: two soft rounds pushed forward (f), centred at +-x, on the front half only (a ramp on f);
- hips: the sides pushed out in x, linearly in x (the outer hip by amount_m at ref_x, the midline not at all);
- seat: two rounds pushed backward (-f), on the back half only;
- waist: the sides pulled in, as hips with a negative sign.
Every move is scaled by the vertex's trunk weight (the sum of its weights on the mask bones), so arms, hands, feet,
the neck and the head never move.
"""
from __future__ import annotations

import math
import tomllib
from pathlib import Path

TOP_KEYS = {"name", "note", "chest", "hips", "seat", "waist", "mask", "limits"}
NESTED = {
    "chest": {"amount_m", "z", "half_z", "x", "half_x", "ramp_m"},
    "seat": {"amount_m", "z", "half_z", "x", "half_x", "ramp_m"},
    "hips": {"amount_m", "z", "half_z", "ref_x"},
    "waist": {"amount_m", "z", "half_z", "ref_x"},
    "mask": {"bones"},
    "limits": {"still_above_z", "still_below_z", "max_delta_m"},
}
SHAPES = ("chest", "seat", "hips", "waist")


def load(path: str | Path) -> dict:
    """A female target file, every key and nested key checked; ValueError names the first problem."""
    return check(tomllib.loads(Path(path).read_text(encoding="utf-8")), str(path))


def check(d: dict, name: str = "target") -> dict:
    bad = set(d) - TOP_KEYS
    if bad:
        raise ValueError(f"{name}: unknown keys {sorted(bad)}")
    missing = (TOP_KEYS - {"note"}) - set(d)
    if missing:
        raise ValueError(f"{name}: missing keys {sorted(missing)}")
    for table, keys in NESTED.items():
        t = d[table]
        if not isinstance(t, dict):
            raise ValueError(f"{name}: {table} is not a table")
        if set(t) != keys:
            raise ValueError(f"{name}: {table} keys {sorted(t)}, want {sorted(keys)}")
        for k, v in t.items():
            if k == "bones":
                if not (isinstance(v, list) and v and all(isinstance(b, str) for b in v)):
                    raise ValueError(f"{name}: mask.bones must be a list of bone names")
            elif not isinstance(v, (int, float)) or isinstance(v, bool):
                raise ValueError(f"{name}: {table}.{k} is not a number")
            elif k not in ("amount_m", "z") and v <= 0:
                raise ValueError(f"{name}: {table}.{k} must be > 0")
    lim = d["limits"]
    for table in SHAPES:
        t = d[table]
        if not 0 <= t["amount_m"] <= lim["max_delta_m"]:
            raise ValueError(f"{name}: {table}.amount_m must be in [0, limits.max_delta_m]")
        if t["z"] + t["half_z"] > lim["still_above_z"] or t["z"] - t["half_z"] < lim["still_below_z"]:
            raise ValueError(f"{name}: {table}'s box leaves [still_below_z, still_above_z]")
    return d


def kernel(t: float) -> float:
    """(1 - t^2)^2 inside |t| < 1, 0 outside: 1 at the centre, C1 at the edge."""
    return (1.0 - t * t) ** 2 if abs(t) < 1.0 else 0.0


def ramp(t: float) -> float:
    """smoothstep from 0 (t <= 0) to 1 (t >= 1)."""
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def _pair(x: float, z: float, f_side: float, b: dict) -> float:
    """Two mirrored rounds at +-x, on one side (f_side: the distance in front of, or behind, the centre line)."""
    kz = kernel((z - b["z"]) / b["half_z"])
    if kz == 0.0:
        return 0.0
    kx = kernel((x - b["x"]) / b["half_x"]) + kernel((x + b["x"]) / b["half_x"])
    return b["amount_m"] * kz * min(1.0, kx) * ramp(f_side / b["ramp_m"])


def _side(x: float, z: float, b: dict) -> float:
    """The lateral move, linear in x (0 on the midline, amount_m at +-ref_x), times its height kernel."""
    return b["amount_m"] * kernel((z - b["z"]) / b["half_z"]) * x / b["ref_x"]


def delta(x: float, f: float, z: float, trunk_w: float, t: dict) -> tuple[float, float]:
    """(dx, df) for a vertex at x, f (forward of the centre line), z with trunk weight trunk_w (0..1)."""
    if trunk_w <= 0.0 or z > t["limits"]["still_above_z"] or z < t["limits"]["still_below_z"]:
        return 0.0, 0.0
    w = min(1.0, trunk_w)
    dx = _side(x, z, t["hips"]) - _side(x, z, t["waist"])
    df = _pair(x, z, f, t["chest"]) - _pair(x, z, -f, t["seat"])
    return w * dx, w * df


def centre_f(z: float, chain: list[tuple[float, float]]) -> float:
    """The trunk centre line's forward coordinate at z, linear between the chain's (z, f) points, held flat past its
    ends."""
    pts = sorted(chain)
    if z <= pts[0][0]:
        return pts[0][1]
    for (z0, f0), (z1, f1) in zip(pts, pts[1:]):
        if z <= z1:
            return f0 + (f1 - f0) * (z - z0) / (z1 - z0) if z1 > z0 else f1
    return pts[-1][1]


def report(base: list[tuple[float, float, float]], moved: list[tuple[float, float, float]],
           bins: tuple[float, ...] = (0.80, 0.86, 0.93, 1.00, 1.07, 1.14, 1.20)) -> dict:
    """Per-vertex delta numbers, and per height the half width and the front and back (x, f, z points) before and
    after."""
    if len(base) != len(moved):
        raise ValueError("vertex counts differ")
    d = [math.dist(a, b) for a, b in zip(base, moved)]
    nz = [v for v in d if v > 1e-7]
    out = {"vertices": len(base), "moved": len(nz), "max_m": round(max(d), 5),
           "mean_moved_m": round(sum(nz) / len(nz), 5) if nz else 0.0,
           "top_z_m": [round(max(p[2] for p in base), 5), round(max(p[2] for p in moved), 5)],
           "low_z_m": [round(min(p[2] for p in base), 5), round(min(p[2] for p in moved), 5)],
           "stations": {}}
    for z in bins:
        row = {}
        for tag, pts in (("base", base), ("female", moved)):
            sl = [p for p in pts if abs(p[2] - z) < 0.006 and abs(p[0]) < 0.25]
            if sl:
                row[tag] = {"half_x": round(max(abs(p[0]) for p in sl), 4),
                            "front_f": round(max(p[1] for p in sl), 4), "back_f": round(min(p[1] for p in sl), 4)}
        out["stations"][f"{z:.2f}"] = row
    return out
