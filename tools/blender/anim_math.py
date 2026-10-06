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


def _dot(a, b) -> float:
    return sum(x * y for x, y in zip(a, b))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _slide_stats(vels: list, contact_frames: int) -> dict:
    if not vels:
        return {"contact_frames": contact_frames, "raw_mean_cm_s": None, "raw_max_cm_s": None,
                "ground_speed_cm_s": None, "slide_mean_cm_s": None, "slide_max_cm_s": None, "samples": 0}
    ground = (median(v[0] for v in vels), median(v[1] for v in vels))
    raw = [math.hypot(*v) for v in vels]
    slide = [math.hypot(v[0] - ground[0], v[1] - ground[1]) for v in vels]
    return {
        "contact_frames": contact_frames,
        "samples": len(vels),
        "raw_mean_cm_s": round(100 * sum(raw) / len(raw), 1),
        "raw_max_cm_s": round(100 * max(raw), 1),
        "ground_speed_cm_s": round(100 * math.hypot(*ground), 1),
        "slide_mean_cm_s": round(100 * sum(slide) / len(slide), 1),
        "slide_max_cm_s": round(100 * max(slide), 1),
    }


def foot_sliding(feet: dict, fps: float, window: float = CONTACT_WINDOW_M) -> dict:
    """feet: {name: [(x, y, z) per frame]}: a foot bone's head, one cycle sampled at fps. A foot is in contact while
    its height is within `window` of its own lowest height in the clip. Returns, in cm/s: the raw horizontal speed in
    contact (mean, max), the ground speed (the median contact velocity of both feet: the speed of the treadmill an
    in-place clip walks on, near zero for a clip that stands still) and the sliding (the contact velocity minus the
    ground velocity: mean, max). Velocities are central differences over frames in contact on both sides."""
    vels, contact_frames = [], 0
    for pts in feet.values():
        low = min(p[2] for p in pts)
        contact = [p[2] <= low + window for p in pts]
        contact_frames += sum(contact)
        for i in range(1, len(pts) - 1):
            if contact[i - 1] and contact[i] and contact[i + 1]:
                d = _sub(pts[i + 1], pts[i - 1])
                vels.append((d[0] * fps / 2, d[1] * fps / 2))
    return _slide_stats(vels, contact_frames)


def sole_sliding(feet: dict, floor: float = 0.0, window: float = CONTACT_WINDOW_M) -> dict:
    """feet: {name: [(z, (vx, vy)) per frame]}: the height of the foot's lowest sole vertex and that same vertex's
    horizontal velocity (m/s). The sole is in contact while its lowest point is within `window` of the floor (the
    sole's rest height) or below it; it follows heel and toe roll, which a single foot bone does not, and it counts a
    foot dragged low along the floor as sliding. Same results as foot_sliding."""
    vels, contact_frames = [], 0
    for series in feet.values():
        for z, v in series:
            if z <= floor + window:
                contact_frames += 1
                vels.append(v)
    return _slide_stats(vels, contact_frames)


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
    """The angle (degrees) that turns direction a into direction b about the unit axis, signed by the right hand: the
    bend in the plane normal to axis (a bend in another plane counts by its share in this one)."""
    return math.degrees(math.atan2(_dot(_cross(a, b), axis), _dot(a, b)))


def hyperextension(angles: list[float]) -> float:
    """Degrees bent past straight: angles are signed joint flexions (positive = the normal bend). An angle beyond -90
    degrees is a deep normal bend that wrapped past 180 (a folded elbow measured about a tilted hinge axis), not a
    joint bent backwards, so it is left out."""
    back = [a for a in angles if -90.0 < a < 0.0]
    return round(-min(back), 1) if back else 0.0


def loop_seam(first: dict, last: dict, steps: list[float]) -> dict:
    """first and last: {bone: quaternion} local rotations; steps: the per-frame largest bone rotation in the clip.
    The seam is the largest bone rotation between the last and the first frame; a clean loop has a seam no larger than
    an ordinary frame step (ratio about 1 or below)."""
    seam = max((quat_angle(first[b], last[b]) for b in first if b in last), default=0.0)
    step = median(steps) if steps else 0.0
    return {"seam_deg": round(seam, 1), "median_step_deg": round(step, 2),
            "seam_ratio": round(seam / step, 1) if step > 1e-6 else None}



def floor_clamp_weight(dz: float, full: float = 0.20, fade: float = 0.10, below: float = 0.02,
                       below_fade: float = 0.04) -> float:
    """How much the retarget's floor clamp (the toe lift, retarget_core) acts on a foot whose pivot is dz m above its
    rest height: fully from `below` m under it to `full` m over it, fading out linearly over `fade` m above and over
    `below_fade` m below. A pivot well under the floor is an in-place jump without its rise, which the clamp leaves
    alone; the fade below keeps a foot hovering on that line from switching the clamp fully on and off between two
    frames (art #33: UAL's Jump_Loop flicked the right foot 53 degrees and back four times a loop)."""
    if dz < -below:
        return min(max(1.0 - (-below - dz) / below_fade, 0.0), 1.0)
    return min(max(1.0 - (dz - full) / fade, 0.0), 1.0)


POP_MIN_DEG, POP_RATIO = 20.0, 3.0  # a one-frame pop: one step this large, its neighbours under a third of it


def one_frame_pops(steps: list[float], loop: bool = False, min_deg: float = POP_MIN_DEG,
                   ratio: float = POP_RATIO) -> list[int]:
    """The one-frame pops of a bone (art #33's review): steps[i] is its rotation (degrees) from frame i to frame i + 1;
    a pop is a step of at least min_deg whose neighbouring steps are both under 1/ratio of it (a snap between two
    poses that are each held, which no seam or median-step measure sees). A loop's steps wrap round (its last frame
    is its first); a one-shot's first and last steps have one neighbour. Returns the indices i."""
    n = len(steps)
    out = []
    for i, st in enumerate(steps):
        if st < min_deg:
            continue
        near = [steps[j % n] for j in (i - 1, i + 1) if loop or 0 <= j < n]
        if all(x < st / ratio for x in near if x is not None):
            out.append(i)
    return out

def summary(values: list[float], digits: int = 1) -> dict:
    if not values:
        return {"min": None, "max": None, "mean": None}
    return {"min": round(min(values), digits), "max": round(max(values), digits),
            "mean": round(sum(values) / len(values), digits)}
