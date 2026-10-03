"""Pure-Python measures for the animation review (no bpy, so the unit tests run them with the system Python).

Vectors are (x, y, z) tuples in metres, quaternions (w, x, y, z); the results are in centimetres and degrees.
anim_metrics.py feeds them from Blender; docs/animations.md defines each measure.
"""

from __future__ import annotations

import math
from statistics import median

CONTACT_WINDOW_M = 0.02  # a foot is on the ground while within 2 cm of its lowest height in the clip


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _norm(a) -> float:
    return math.sqrt(sum(x * x for x in a))


def _dot(a, b) -> float:
    return sum(x * y for x, y in zip(a, b))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def foot_sliding(feet: dict, fps: float, window: float = CONTACT_WINDOW_M) -> dict:
    """feet: {name: [(x, y, z) per frame]}, one cycle sampled at fps. A foot is in contact while its height is within
    `window` of its own lowest height in the clip. Returns, in cm/s: the raw horizontal speed in contact (mean, max),
    the ground speed (the median contact velocity of both feet: the speed of the treadmill an in-place clip walks on,
    near zero for a clip that stands still) and the sliding (the contact velocity minus the ground velocity: mean,
    max). Velocities are central differences over frames that are in contact on both sides."""
    vels, per_foot = [], {}
    for name, pts in feet.items():
        low = min(p[2] for p in pts)
        contact = [p[2] <= low + window for p in pts]
        v = []
        for i in range(1, len(pts) - 1):
            if contact[i - 1] and contact[i] and contact[i + 1]:
                d = _sub(pts[i + 1], pts[i - 1])
                v.append((d[0] * fps / 2, d[1] * fps / 2))
        per_foot[name] = {"contact_frames": sum(contact), "v": v}
        vels += v
    contact_frames = sum(f["contact_frames"] for f in per_foot.values())
    if not vels:
        return {"contact_frames": contact_frames, "raw_mean_cm_s": None, "raw_max_cm_s": None, "ground_speed_cm_s": None,
                "slide_mean_cm_s": None, "slide_max_cm_s": None}
    ground = (median(v[0] for v in vels), median(v[1] for v in vels))
    raw = [math.hypot(*v) for v in vels]
    slide = [math.hypot(v[0] - ground[0], v[1] - ground[1]) for v in vels]
    return {
        "contact_frames": contact_frames,
        "raw_mean_cm_s": round(100 * sum(raw) / len(raw), 1),
        "raw_max_cm_s": round(100 * max(raw), 1),
        "ground_speed_cm_s": round(100 * math.hypot(*ground), 1),
        "slide_mean_cm_s": round(100 * sum(slide) / len(slide), 1),
        "slide_max_cm_s": round(100 * max(slide), 1),
    }


def quat_angle(q1, q2) -> float:
    """The angle (degrees) of the rotation between two unit quaternions."""
    d = min(1.0, abs(_dot(q1, q2)))
    return math.degrees(2 * math.acos(d))


def twist_angle(q, axis) -> float:
    """The twist (degrees, -180..180) of rotation q about the unit axis, by the swing-twist decomposition."""
    w, v = q[0], q[1:]
    p = _dot(v, axis)
    if abs(p) < 1e-12 and abs(w) < 1e-12:
        return 180.0
    ang = math.degrees(2 * math.atan2(p, w))
    return (ang + 180.0) % 360.0 - 180.0


def signed_angle(a, b, axis) -> float:
    """The angle (degrees) that turns direction a into direction b, signed by the right hand about axis."""
    ang = math.degrees(math.atan2(_norm(_cross(a, b)), _dot(a, b)))
    return ang if _dot(_cross(a, b), axis) >= 0 else -ang


def hyperextension(angles: list[float]) -> float:
    """Degrees bent past straight: angles are signed joint flexions (positive = the normal bend)."""
    return round(max(0.0, -min(angles)), 1) if angles else 0.0


def loop_seam(first: dict, last: dict, steps: list[float]) -> dict:
    """first and last: {bone: quaternion} local rotations; steps: the per-frame largest bone rotation in the clip.
    The seam is the largest bone rotation between the last and the first frame; a clean loop has a seam no larger than
    an ordinary frame step (ratio about 1 or below)."""
    seam = max((quat_angle(first[b], last[b]) for b in first if b in last), default=0.0)
    step = median(steps) if steps else 0.0
    return {"seam_deg": round(seam, 1), "median_step_deg": round(step, 2),
            "seam_ratio": round(seam / step, 1) if step > 1e-6 else None}


def summary(values: list[float], digits: int = 1) -> dict:
    if not values:
        return {"min": None, "max": None, "mean": None}
    return {"min": round(min(values), digits), "max": round(max(values), digits),
            "mean": round(sum(values) / len(values), digits)}
