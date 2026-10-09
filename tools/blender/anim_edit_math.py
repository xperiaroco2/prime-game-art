"""The pure math of the clip edits (tools/blender/anim_edit.py; docs/animations.md, "Clip edits"): no bpy, so the
unit tests run it with the system Python and the runner validates edit steps with it.

Conventions: vectors are tuples in metres (world space: front -Y, left +X, up +Z, floor z = 0); quaternions are
(w, x, y, z); yaws are degrees about +Z, 0 = facing or moving forward (-Y), positive = turned to the left (+X); times
are seconds or frame indices on the 30 fps grid; 4x4 matrices are lists of 4 rows.
"""

from __future__ import annotations

import math
from statistics import median

import anim_math as am

FPS = 30
CONTACT_WINDOW_M = am.CONTACT_WINDOW_M  # a foot is on the ground while within 2 cm of its lowest height
TRAVEL_YAW = {"forward": 0.0, "left": 90.0, "back": 180.0, "right": -90.0}

# ------------------------------------------------------------------------------------------------- the op schema
# op -> {parameter: {"type", "required", "default", "choices"}}. Types: "number" (int or float, not bool), "string"
# (one of "choices"), "bool", "range" (two numbers [a, b], a < b), "number_or_auto" (a number or "auto").
_N = "number"


def _p(kind: str, default=None, required: bool = False, choices=None) -> dict:
    out = {"type": kind, "required": required, "default": default}
    if choices:
        out["choices"] = list(choices)
    return out


OPS = {
    "trim": {"start_s": _p(_N, 0.0), "end_s": _p(_N)},
    "retime": {"seconds": _p(_N), "rate": _p(_N), "speed_m_s": _p(_N), "natural_m_s": _p(_N)},
    "reverse": {},
    "cycle": {"min_s": _p(_N, required=True), "max_s": _p(_N, required=True), "within": _p("range"),
              "max_raw_seam_deg": _p(_N, 15.0)},
    "in_place": {"mode": _p("string", "linear", choices=("linear", "path")), "smooth_s": _p(_N, 0.6)},
    "heading": {"travel": _p("string", choices=tuple(TRAVEL_YAW)),
                "facing": _p("string", choices=("start", "end", "mean"))},
    "turn": {"total_deg": _p(_N, required=True)},
    "mirror": {},
    "stride": {"speed_m_s": _p(_N, required=True), "cadence": _p(_N), "rate": _p(_N), "plant": _p("bool", True),
               "natural_m_s": _p(_N), "warn": _p("range", [0.6, 1.6]), "fail": _p("range", [0.4, 2.5])},
    "floor": {"mode": _p("string", "lift", choices=("lift", "hips", "settle")), "from_s": _p(_N, 0.0), "to_s": _p(_N),
              "fade_s": _p(_N, 0.2), "min_depth_cm": _p(_N, 0.3)},
    "arm_offset": {"abduct_deg": _p("number_or_auto", "auto"), "max_deg": _p(_N, 12.0), "margin_cm": _p(_N, 0.3),
                   "axis": _p("string", "out", choices=("out", "swing"))},
    "hand_spacing": {"min_gap_cm": _p(_N), "gap_m": _p(_N), "at": _p("string", "all", choices=("all", "end", "mean")),
                     "deg": _p("number_or_auto", "auto"), "max_deg": _p(_N, 25.0)},
    "lean": {"deg": _p(_N, required=True), "bone": _p("string", "Torso")},
    # the side grip (art #65): docs/animations.md, "The ops"
    "side_grip": {"gap_m": _p(_N, required=True), "tilt_deg": _p(_N, 0.0), "forearm_share": _p(_N, 0.5),
                  "from_s": _p(_N, 0.0), "fade_s": _p(_N, 0.0), "max_deg": _p(_N, 40.0), "tol_cm": _p(_N, 0.3)},
    # the upper layer's bones into another clip's frame at an end (art #65: the lift hands over to the carry)
    "upper_match": {"from_clip": _p("string", required=True), "frame": _p("int", 0),
                    "at": _p("string", "end", choices=("start", "end")), "fade_s": _p(_N, 0.3),
                    "base_clip": _p("string")},
    # the relaxed idle (art #49): docs/animations.md, "The relaxed idle"
    "foot_turn": {"bone": _p("string", required=True, choices=("Foot.L", "Foot.R")),
                  "toe_in_deg": _p(_N, required=True)},
    "stance": {"out_cm": _p(_N, 2.0), "keep": _p("string", "leg_extension_f0", choices=("leg_extension_f0",))},
    "shoulders": {"drop_deg": _p(_N, required=True)},
    "head_level": {"target_deg": _p(_N, 0.0), "neck_share": _p(_N, 0.4)},
    "hands_relax": {"curl_deg": _p("curl", required=True), "cap": _p(_N)},
    "thumb_in": {"beside": _p("string", "Index3", choices=("Index3", "Index4")), "side_cm": _p(_N, 1.6),
                 "max_deg": _p(_N, 40.0), "frame": _p("int", 0), "from_clip": _p("string")},
    "idle_ends": {"at": _p("string", required=True, choices=("start", "end", "both")),
                  "from_clip": _p("string", required=True), "fade_frames": _p("int", 8),
                  "plant_speed_cm": _p(_N, 1.0), "plant_rise_cm": _p(_N, 1.5), "upper": _p("bool", True),
                  "step_cm": _p(_N, 4.0), "knees_out_deg": _p(_N, 25.0), "knees_out_from_deg": _p(_N, 25.0),
                  "knees_out_full_deg": _p(_N, 75.0), "match": _p("string", "set", choices=("set", "root"))},
}
# the relaxed idle's ops (art #49): anim_edit.apply keeps the clip's first frame as it was before the first of them
# (its "relax base"), which idle_ends reads to carry the idle's own change into the clips that meet it
RELAX_OPS = ("foot_turn", "stance", "shoulders", "head_level", "hands_relax", "thumb_in")
# idle_ends (match = "set") places a clip in the idle's frame; these ops after it keep the placement (the touching
# frames stay where they are), any other clears it (art #49)
KEEP_PLACE = ("idle_ends", "reverse", "retime")
FINGER_SEGMENTS = {"Index": 3, "Middle": 3, "Ring": 3, "Pinky": 3, "Thumb": 2}  # the curled segments: 2-4, Thumb 2-3
COMMON = {"op", "body"}  # keys every step may have
ONE_OF = {"retime": ("seconds", "rate", "speed_m_s"), "heading": ("travel", "facing"),
          "hand_spacing": ("min_gap_cm", "gap_m")}  # exactly one of these
POSITIVE = {"seconds", "rate", "cadence", "min_s", "max_s", "smooth_s", "max_raw_seam_deg", "max_deg", "gap_m",
            "fade_frames", "knees_out_full_deg", "cap", "plant_speed_cm", "plant_rise_cm", "tol_cm"}
NON_NEGATIVE = {"start_s", "end_s", "speed_m_s", "natural_m_s", "from_s", "to_s", "fade_s", "min_depth_cm",
                "margin_cm", "min_gap_cm", "out_cm", "side_cm", "frame", "step_cm", "knees_out_deg",
                "knees_out_from_deg"}


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _type_ok(spec: dict, v) -> bool:
    kind = spec["type"]
    if kind == "number":
        return _is_number(v)
    if kind == "number_or_auto":
        return _is_number(v) or v == "auto"
    if kind == "bool":
        return isinstance(v, bool)
    if kind == "string":
        return isinstance(v, str) and v in spec.get("choices", [v])
    if kind == "range":
        return isinstance(v, (list, tuple)) and len(v) == 2 and all(_is_number(x) for x in v) and v[0] < v[1]
    if kind == "int":
        return isinstance(v, int) and not isinstance(v, bool)
    if kind == "curl":
        return not curl_errors(v)
    return False


def curl_errors(table) -> list[str]:
    """What is wrong with a hands_relax curl table: {finger: [degrees per curled segment]}, the fingers of
    FINGER_SEGMENTS (Index to Pinky: segments 2, 3, 4; Thumb: 2, 3), each angle 0 to 180."""
    if not isinstance(table, dict) or not table:
        return ["a table of fingers"]
    out = []
    for finger, degs in table.items():
        if finger not in FINGER_SEGMENTS:
            out.append(f"unknown finger {finger!r}")
        elif not isinstance(degs, (list, tuple)) or len(degs) != FINGER_SEGMENTS[finger] \
                or not all(_is_number(d) and 0 <= d <= 180 for d in degs):
            out.append(f"{finger}: {FINGER_SEGMENTS[finger]} angles of 0 to 180 degrees")
    return out


def check_steps(steps, bodies=("men", "women")) -> list[str]:
    """The errors of a list of edit steps (empty when they are valid): unknown ops or parameters, missing required
    ones, wrong types or values, not exactly one of retime's seconds/rate/speed_m_s (heading's travel/facing,
    hand_spacing's min_gap_cm/gap_m), a stride with neither cadence nor rate (or both), a bad body."""
    errors: list[str] = []
    if not isinstance(steps, (list, tuple)):
        return ["the edits must be a list of steps"]
    for k, step in enumerate(steps):
        where = f"step {k + 1}"
        if not isinstance(step, dict):
            errors.append(f"{where}: a step must be a table")
            continue
        op = step.get("op")
        if op not in OPS:
            errors.append(f"{where}: unknown op {op!r} (known: {', '.join(sorted(OPS))})")
            continue
        where = f"step {k + 1} ({op})"
        schema = OPS[op]
        for key in sorted(set(step) - set(schema) - COMMON):
            errors.append(f"{where}: unknown parameter {key!r}")
        if "body" in step and step["body"] not in bodies:
            errors.append(f"{where}: body must be one of {list(bodies)}, not {step['body']!r}")
        for key, spec in schema.items():
            if key not in step:
                if spec["required"]:
                    errors.append(f"{where}: missing {key!r}")
                continue
            v = step[key]
            if not _type_ok(spec, v):
                want = spec["type"] + (f" in {spec['choices']}" if "choices" in spec else "")
                if spec["type"] == "curl":
                    want = "curl table (" + "; ".join(curl_errors(v)) + ")"
                elif spec["type"] == "int":
                    want = "whole number"
                errors.append(f"{where}: {key} must be a {want}, not {v!r}")
                continue
            if _is_number(v) and key in POSITIVE and v <= 0:
                errors.append(f"{where}: {key} must be > 0")
            if _is_number(v) and key in NON_NEGATIVE and v < 0:
                errors.append(f"{where}: {key} must be >= 0")
        if op in ONE_OF:
            given = [key for key in ONE_OF[op] if key in step]
            if len(given) != 1:
                errors.append(f"{where}: give exactly one of {', '.join(ONE_OF[op])}")
        if op == "stride" and ("cadence" in step) == ("rate" in step):
            errors.append(f"{where}: give exactly one of cadence, rate")
        if op == "trim" and _is_number(step.get("end_s")) and _is_number(step.get("start_s", 0.0)) \
                and step["end_s"] <= step.get("start_s", 0.0):
            errors.append(f"{where}: end_s must be after start_s")
        if op == "cycle" and _is_number(step.get("min_s")) and _is_number(step.get("max_s")) \
                and step["max_s"] < step["min_s"]:
            errors.append(f"{where}: max_s must be >= min_s")
        if op == "floor" and _is_number(step.get("to_s")) and step["to_s"] <= step.get("from_s", 0.0):
            errors.append(f"{where}: to_s must be after from_s")
        if op == "head_level" and _is_number(step.get("neck_share")) and not 0 <= step["neck_share"] <= 1:
            errors.append(f"{where}: neck_share must be 0 to 1")
        if op == "side_grip" and _is_number(step.get("forearm_share")) and not 0 <= step["forearm_share"] <= 1:
            errors.append(f"{where}: forearm_share must be 0 to 1")
        if op == "side_grip" and _is_number(step.get("tilt_deg")) and not -90 < step["tilt_deg"] < 90:
            errors.append(f"{where}: tilt_deg must be between -90 and 90")
        if op == "thumb_in" and "from_clip" in step:
            for key in sorted({"beside", "side_cm", "max_deg", "frame"} & set(step)):
                errors.append(f"{where}: {key} has no effect with from_clip (the turn is that clip's)")
        if op == "idle_ends":
            lo, hi = step.get("knees_out_from_deg", 25.0), step.get("knees_out_full_deg", 75.0)
            if _is_number(lo) and _is_number(hi) and hi <= lo:
                errors.append(f"{where}: knees_out_full_deg must be over knees_out_from_deg")
    return errors


def from_clips(steps) -> list[str]:
    """The other clips a list of steps reads (their `from_clip` and `base_clip`): a set builds them first."""
    if not isinstance(steps, (list, tuple)):
        return []
    return [s[k] for s in steps if isinstance(s, dict) for k in ("from_clip", "base_clip") if isinstance(s.get(k), str)]


def params(step: dict) -> dict:
    """A step's parameters with the defaults filled in."""
    out = {key: spec["default"] for key, spec in OPS[step["op"]].items()}
    out.update({k: v for k, v in step.items() if k not in COMMON})
    return out


# ------------------------------------------------------------------------------------------------- time maps
def trim_times(frames: int, fps: float, start_s: float, end_s: float | None = None) -> list[float]:
    """The fractional frame indices (into frames 0..frames) that a trim to [start_s, end_s] samples: a whole number
    of frames on the grid from start_s (end_s omitted or past the end: to the end)."""
    total = frames / fps
    end = total if end_s is None else min(end_s, total)
    if start_s < 0 or start_s >= end:
        raise ValueError(f"trim [{start_s}, {end_s}] is outside the clip (0 to {total:.3f} s)")
    n = max(1, round((end - start_s) * fps))
    s0 = start_s * fps
    return [min(s0 + k, float(frames)) for k in range(n + 1)]


def retime_count(intervals: int, rate: float) -> tuple[int, float]:
    """(new frame intervals, the effective rate) for a clip of `intervals` frame intervals played at `rate`: a whole
    number of frames, so the effective rate differs a little from the asked one."""
    if rate <= 0:
        raise ValueError("the rate must be > 0")
    m = max(1, round(intervals / rate))
    return m, intervals / m


def retime_times(intervals: int, new_intervals: int) -> list[float]:
    """The fractional frame indices that a retime samples: k * N / M for k = 0..M. The first and last frames are kept,
    so an open clip keeps its ends and a closed loop (last frame = first) stays closed with its period scaled."""
    return [k * intervals / new_intervals for k in range(new_intervals + 1)]


def catmull_rom(f: float) -> tuple[float, float, float, float]:
    """The weights of frames i-1, i, i+1, i+2 for a point at fraction f between frames i and i+1 (a uniform
    Catmull-Rom spline: it passes through the frames, keeps a straight line straight and follows a curve far closer
    than a linear blend, so a retime there and back stays within a fraction of a degree)."""
    f2, f3 = f * f, f * f * f
    return (-0.5 * f3 + f2 - 0.5 * f, 1.5 * f3 - 2.5 * f2 + 1.0, -1.5 * f3 + 2.0 * f2 + 0.5 * f, 0.5 * f3 - 0.5 * f2)


def neighbours(i: int, last: int, closed: bool) -> tuple[int, int, int, int]:
    """Frames i-1, i, i+1, i+2 of a clip with frames 0..last: clamped at the ends, or wrapped over a closed loop's
    seam (its frame `last` is its frame 0)."""
    if closed and last > 1:
        return ((i - 1) % last, i, i + 1, (i + 2) % last if i + 2 > last else i + 2)
    return (max(i - 1, 0), i, min(i + 1, last), min(i + 2, last))


def split_index(t: float, last: int) -> tuple[int, float]:
    """A fractional frame index as (frame, fraction towards the next), clamped to 0..last."""
    t = min(max(t, 0.0), float(last))
    i = min(int(math.floor(t)), max(last - 1, 0))
    return i, t - i


# --------------------------------------------------------------------------------------------- quaternions
def q_mul(a, b):
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return (w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2, w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2, w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2)


def q_conj(q):
    return (q[0], -q[1], -q[2], -q[3])


def q_norm(q):
    n = math.sqrt(sum(c * c for c in q))
    return tuple(c / n for c in q) if n > 1e-12 else (1.0, 0.0, 0.0, 0.0)


def q_hemi(q, ref):
    """q or -q, whichever is on ref's hemisphere (the same rotation; interpolation then takes the short way)."""
    return q if sum(a * b for a, b in zip(q, ref)) >= 0 else tuple(-c for c in q)


def q_slerp(a, b, t: float):
    b = q_hemi(b, a)
    d = min(1.0, sum(x * y for x, y in zip(a, b)))
    if d > 0.9995:
        return q_norm(tuple(x + (y - x) * t for x, y in zip(a, b)))
    th = math.acos(d)
    s = math.sin(th)
    wa, wb = math.sin((1 - t) * th) / s, math.sin(t * th) / s
    return tuple(wa * x + wb * y for x, y in zip(a, b))


def q_axis_angle(axis, degrees: float):
    n = math.sqrt(sum(c * c for c in axis))
    h = math.radians(degrees) / 2
    return (math.cos(h), *(math.sin(h) * c / n for c in axis))


def q_rotate(q, v):
    return q_mul(q_mul(q, (0.0, *v)), q_conj(q))[1:]


def q_angle(a, b) -> float:
    return am.quat_angle(a, b)


def lerp(a, b, t: float):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


# ---------------------------------------------------------------------------------------------------- cycle
def central_diff(series: list) -> list:
    """Per-frame central differences of a list of equal-length vectors (one-sided at the ends)."""
    n = len(series)
    out = []
    for i in range(n):
        a, b = series[max(i - 1, 0)], series[min(i + 1, n - 1)]
        span = max(min(i + 1, n - 1) - max(i - 1, 0), 1)
        out.append([(y - x) / span for x, y in zip(a, b)])
    return out


def best_cycle(features: list, velocities: list, fps: float, min_s: float, max_s: float, within=None,
               vel_weight: float = 1.0) -> tuple[int, int, float]:
    """The frame pair (i, j), i < j, whose poses differ least, with j - i between min_s and max_s seconds (whole
    frames) and both inside `within` = [a_s, b_s] (the whole clip when omitted): the cost is the squared distance
    of the feature vectors plus vel_weight times that of their velocities. Returns (i, j, cost)."""
    n = len(features)
    lo, hi = 0, n - 1
    if within is not None:
        lo = max(0, math.ceil(within[0] * fps - 1e-6))
        hi = min(n - 1, math.floor(within[1] * fps + 1e-6))
    dmin, dmax = max(1, round(min_s * fps)), round(max_s * fps)
    best = None
    for i in range(lo, hi + 1):
        fi, vi = features[i], velocities[i]
        for j in range(i + dmin, min(i + dmax, hi) + 1):
            fj, vj = features[j], velocities[j]
            c = sum((a - b) ** 2 for a, b in zip(fi, fj))
            if vel_weight:
                c += vel_weight * sum((a - b) ** 2 for a, b in zip(vi, vj))
            if best is None or c < best[2]:
                best = (i, j, c)
    if best is None:
        raise ValueError(f"no frame pair {min_s}-{max_s} s apart inside {within} (the clip has {n} frames)")
    return best


def close_ramp(intervals: int) -> list[float]:
    """The weights k / T (k = 0..T) with which a loop's residual is spread over its cycle."""
    return [k / intervals for k in range(intervals + 1)]


def close_vectors(series: list) -> list:
    """A cut cycle's vector channel (locations, scales) closed: x'(k) = x(k) + (x(0) - x(T)) k / T, so the first frame
    is unchanged and the last equals it."""
    first, last = series[0], series[-1]
    ramp = close_ramp(len(series) - 1)
    return [tuple(x + (a - b) * w for x, a, b in zip(p, first, last)) for p, w in zip(series, ramp)]


def close_quats(series: list) -> list:
    """A cut cycle's rotation channel closed: q'(k) = q(k) slerp(1, q(T)^-1 q(0), k / T)."""
    delta = q_norm(q_mul(q_conj(series[-1]), series[0]))
    delta = q_hemi(delta, (1.0, 0.0, 0.0, 0.0))
    ramp = close_ramp(len(series) - 1)
    return [q_norm(q_mul(q, q_slerp((1.0, 0.0, 0.0, 0.0), delta, w))) for q, w in zip(series, ramp)]


# ------------------------------------------------------------------------------------------- paths and yaws
def linear_drift(points: list) -> list:
    """The offsets that take a path's first-to-last travel out in proportion to time: (p(N) - p(0)) k / N."""
    n = len(points) - 1
    d = [b - a for a, b in zip(points[0], points[-1])]
    return [tuple(c * k / n for c in d) if n else tuple(0.0 for _ in d) for k in range(n + 1)]


def moving_average(points: list, half: int, odd: bool = False) -> list:
    """A centred moving average over 2 * half + 1 samples. At the ends the window shrinks, or with odd=True the path
    is extended by its point reflection about each end (p(-k) = 2 p(0) - p(k)), so a straight path at constant speed
    averages to itself up to its ends."""
    n = len(points)
    dims = range(len(points[0]))

    def at(k):
        if 0 <= k < n or not odd:
            return points[k]
        e, m = (0, -k) if k < 0 else (n - 1, 2 * (n - 1) - k)
        m = min(max(m, 0), n - 1)
        return tuple(2 * points[e][c] - points[m][c] for c in dims)

    out = []
    for i in range(n):
        a, b = (i - half, i + half + 1) if odd else (max(0, i - half), min(n, i + half + 1))
        win = [at(k) for k in range(a, b)]
        out.append(tuple(sum(p[c] for p in win) / len(win) for c in dims))
    return out


def path_offsets(points: list, fps: float, smooth_s: float) -> list:
    """The offsets that hold a one-shot's body over its start: its path low-passed by a centred moving average of
    smooth_s seconds (the ends extended by point reflection), less that average's first value (the sway about the
    average stays)."""
    half = max(1, round(smooth_s * fps / 2))
    avg = moving_average(points, half, odd=True)
    return [tuple(a - b for a, b in zip(p, avg[0])) for p in avg]


def moving_speed(points: list, fps: float, threshold: float = 0.1) -> float:
    """The mean speed (m/s) of a path over its frames moving faster than threshold m/s (0 when it never does)."""
    dist = steps = 0
    for a, b in zip(points, points[1:]):
        d = math.dist(a, b)
        if d * fps > threshold:
            dist, steps = dist + d, steps + 1
    return dist * fps / steps if steps else 0.0


def lsq_direction(points: list, times: list) -> tuple[tuple[float, float], float]:
    """The least-squares velocity of a 2D path over time: (unit direction, speed m/s). The direction is (0, 0) for a
    path that does not move."""
    n = len(points)
    tm = sum(times) / n
    xm = sum(p[0] for p in points) / n
    ym = sum(p[1] for p in points) / n
    den = sum((t - tm) ** 2 for t in times)
    if den <= 0:
        return (0.0, 0.0), 0.0
    vx = sum((t - tm) * (p[0] - xm) for t, p in zip(times, points)) / den
    vy = sum((t - tm) * (p[1] - ym) for t, p in zip(times, points)) / den
    speed = math.hypot(vx, vy)
    return ((vx / speed, vy / speed) if speed > 1e-12 else (0.0, 0.0)), speed


def wrap(deg: float) -> float:
    """An angle in (-180, 180]."""
    a = (deg + 180.0) % 360.0 - 180.0
    return 180.0 if a == -180.0 else a


def yaw_of(v) -> float:
    """The yaw (degrees) of a horizontal direction: 0 = forward (-Y), 90 = left (+X), 180 = back, -90 = right."""
    return math.degrees(math.atan2(v[0], -v[1]))


def signed_angle_2d(a, b) -> float:
    """The angle (degrees, -180..180) that turns 2D direction a into b, positive counter-clockwise from above."""
    return math.degrees(math.atan2(a[0] * b[1] - a[1] * b[0], a[0] * b[0] + a[1] * b[1]))


def facing_yaw(forward, left) -> float:
    """A body's facing yaw from its forward and left axes in world space: the horizontal forward axis plus the
    horizontal left axis turned 90 degrees clockwise (the hip line), so the facing holds while the body bends
    forward (all fours) and while it lies on its back or side."""
    fx, fy = forward[0] + left[1], forward[1] - left[0]
    return yaw_of((fx, fy)) if math.hypot(fx, fy) > 1e-9 else 0.0


def unwrap(degs: list) -> list:
    """Angles made continuous (no jump of more than 180 degrees between neighbours)."""
    out = [degs[0]] if degs else []
    for d in degs[1:]:
        out.append(out[-1] + wrap(d - out[-1]))
    return out


def circular_mean(degs: list) -> float:
    s = sum(math.sin(math.radians(d)) for d in degs)
    c = sum(math.cos(math.radians(d)) for d in degs)
    return math.degrees(math.atan2(s, c))


def turn_correction(yaws: list, total: float) -> list:
    """The extra yaw per frame that rescales a turn's net yaw (last minus first) to `total`: (total / net - 1) *
    (yaw(t) - yaw(0)); yaws are unwrapped degrees."""
    net = yaws[-1] - yaws[0]
    if abs(net) < 1.0:
        raise ValueError(f"the clip turns {net:.1f} degrees: nothing to rescale")
    k = total / net - 1.0
    return [k * (y - yaws[0]) for y in yaws]


# ---------------------------------------------------------------------------------------------------- stride
def contact_mask(heights: list, window: float = CONTACT_WINDOW_M) -> list[bool]:
    low = min(heights)
    return [h <= low + window for h in heights]


def contact_windows(mask: list[bool], cyclic: bool) -> list[list[int]]:
    """The runs of contact frames as lists of frame indices; in a cyclic clip (its frames 0..n-1, the frame after
    n-1 being 0) a run over the end continues at the start."""
    n = len(mask)
    if all(mask):
        return [list(range(n))]
    runs, cur = [], []
    for i, c in enumerate(mask):
        if c:
            cur.append(i)
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    if cyclic and len(runs) > 1 and runs[0][0] == 0 and runs[-1][-1] == n - 1:
        runs[0] = runs.pop() + runs[0]
    return runs


def contact_velocities(feet: dict, fps: float, window: float = CONTACT_WINDOW_M) -> list[tuple[float, float]]:
    """The horizontal contact velocities (m/s) of the feet, by anim_math.foot_sliding's rule (central differences of
    frames in contact on both sides); feet: {name: [(x, y, z) per frame]}."""
    vels = []
    for pts in feet.values():
        contact = contact_mask([p[2] for p in pts], window)
        for i in range(1, len(pts) - 1):
            if contact[i - 1] and contact[i] and contact[i + 1]:
                vels.append(((pts[i + 1][0] - pts[i - 1][0]) * fps / 2, (pts[i + 1][1] - pts[i - 1][1]) * fps / 2))
    return vels


def ground_velocity(vels: list) -> tuple[float, float] | None:
    """The median contact velocity (the treadmill's velocity under an in-place clip), or None without contacts."""
    if not vels:
        return None
    return (median(v[0] for v in vels), median(v[1] for v in vels))


def natural_cadence(windows: int, cycle_s: float) -> float:
    """Steps per second: the contact windows of both feet in one cycle over its length."""
    return windows / cycle_s


def stride_rate(intervals: int, c0: float, cadence: float | None = None, rate: float | None = None):
    """(new intervals, effective rate) for a loop of `intervals` frames with natural cadence c0 played at
    `cadence` steps/s (or at `rate`), rounded to whole frames."""
    r = rate if rate is not None else cadence / c0
    return retime_count(intervals, r)


def stride_scale(speed: float, rate_eff: float, v0: float) -> float:
    """How much the feet's travel along the ground axis scales so the retimed loop's planted feet move at speed."""
    return speed / (rate_eff * v0)


def stride_fit(scale: float, warn=(0.6, 1.6), fail=(0.4, 2.5)) -> str:
    if not fail[0] <= scale <= fail[1]:
        return "fail"
    if not warn[0] <= scale <= warn[1]:
        return "warn"
    return "ok"


def scale_offset(o, d, s: float):
    """A foot's horizontal offset from the body scaled by s along the unit ground axis d: o + (s - 1)(o.d)d."""
    k = (s - 1.0) * (o[0] * d[0] + o[1] * d[1])
    return (o[0] + k * d[0], o[1] + k * d[1])


def plant(points: list, windows: list, velocity, fps: float, blend: int = 2, cyclic: bool = True) -> list:
    """A foot's horizontal track with each contact window replaced by a straight line at `velocity` (m/s, the
    ground's), anchored at the window's middle frame; the `blend` frames before and after each window move towards
    the line by (blend + 1 - j) / (blend + 1). points: [(x, y)] per frame (a cyclic clip's frames 0..n-1)."""
    n = len(points)
    out = [tuple(p) for p in points]
    weight = [0.0] * n
    target = list(out)
    for win in windows:
        mid = (len(win) - 1) / 2  # between two frames in a window of an even length
        a, b = points[win[int(math.floor(mid))]], points[win[int(math.ceil(mid))]]
        anchor = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        for pos in range(-blend, len(win) + blend):
            if 0 <= pos < len(win):
                idx, w = win[pos], 1.0
            else:
                j = -pos if pos < 0 else pos - len(win) + 1
                idx = win[0] - j if pos < 0 else win[-1] + j
                if cyclic:
                    idx %= n
                elif not 0 <= idx < n:
                    continue
                w = (blend + 1 - j) / (blend + 1)
            if w > weight[idx]:
                weight[idx] = w
                target[idx] = (anchor[0] + velocity[0] * (pos - mid) / fps, anchor[1] + velocity[1] * (pos - mid) / fps)
    for i in range(n):
        if weight[i] > 0:
            out[i] = lerp(points[i], target[i], weight[i])
    return out


# ------------------------------------------------------------------------------------------------------- IK
def _v_sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _v_add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def _v_mul(a, k):
    return tuple(x * k for x in a)


def _v_len(a):
    return math.sqrt(sum(x * x for x in a))


def _v_dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def two_bone_ik(H, K, A, goal, pole):
    """A two-bone chain hip H, knee K, ankle A reaching for goal, bending towards pole (a direction): the new knee
    and ankle and the miss (the ankle's distance from the goal; 0 when it is reachable). The bone lengths are kept;
    an unreachable goal gives a straight leg pointing at it."""
    L1, L2 = _v_len(_v_sub(K, H)), _v_len(_v_sub(A, K))
    dv = _v_sub(goal, H)
    dist = _v_len(dv)
    d = min(max(dist, abs(L1 - L2) + 1e-7), (L1 + L2) * (1 - 1e-6))
    if dist > 1e-12:
        u = _v_mul(dv, 1 / dist)
    else:
        ha = _v_sub(A, H)
        u = _v_mul(ha, 1 / max(_v_len(ha), 1e-12))
    n = _v_sub(pole, _v_mul(u, _v_dot(pole, u)))
    if _v_len(n) < 1e-9:  # a pole along the leg: any perpendicular
        alt = (1.0, 0.0, 0.0) if abs(u[0]) < 0.9 else (0.0, 1.0, 0.0)
        n = _v_sub(alt, _v_mul(u, _v_dot(alt, u)))
    n = _v_mul(n, 1 / _v_len(n))
    a = (L1 * L1 - L2 * L2 + d * d) / (2 * d)
    h = math.sqrt(max(L1 * L1 - a * a, 0.0))
    K2 = _v_add(_v_add(H, _v_mul(u, a)), _v_mul(n, h))
    A2 = _v_add(H, _v_mul(u, d))
    return K2, A2, _v_len(_v_sub(A2, goal))


# ---------------------------------------------------------------------------------------------------- floor
def floor_profile(depths: list, i0: int, i1: int, fade: int, run: int = 2, smooth: int = 2) -> list:
    """The lift per frame (m) that takes a clip's lowest vertex out of the floor inside frames i0..i1: the depths
    (m below the floor, 0 where none) as a running max over +-run frames, smoothed by a centred average over
    +-smooth frames (both inside the window), then held at the window's edge values and faded linearly to 0 over
    `fade` frames outside the window."""
    n = len(depths)
    i0, i1 = max(0, i0), min(n - 1, i1)
    d = [max(0.0, x) for x in depths]
    rm = {i: max(d[max(i0, i - run):min(i1, i + run) + 1]) for i in range(i0, i1 + 1)}
    out = [0.0] * n
    for i in range(i0, i1 + 1):
        a, b = max(i0, i - smooth), min(i1, i + smooth)
        out[i] = sum(rm[k] for k in range(a, b + 1)) / (b - a + 1)
    for j in range(1, fade + 1):
        w = 1.0 - j / (fade + 1)
        if i0 - j >= 0:
            out[i0 - j] = out[i0] * w
        if i1 + j < n:
            out[i1 + j] = out[i1] * w
    return out


def settle_profile(heights: list, i0: int, i1: int, fade: int, run: int = 2, smooth: int = 2) -> list:
    """The drop per frame (m, >= 0) that brings a floating clip's lowest vertex down onto the floor inside frames
    i0..i1 (art #33, `floor {mode = "settle"}`): the heights above the floor (0 where a vertex is on or under it) as a
    running min over +-run frames, smoothed by a centred average over +-smooth frames, held and faded as
    floor_profile does. Every smoothed value averages minima that include the frame itself, and a faded frame outside
    the window drops at most its own height, so no frame is put under the floor."""
    n = len(heights)
    i0, i1 = max(0, i0), min(n - 1, i1)
    h = [max(0.0, x) for x in heights]
    rm = {i: min(h[max(i0, i - run):min(i1, i + run) + 1]) for i in range(i0, i1 + 1)}
    out = [0.0] * n
    for i in range(i0, i1 + 1):
        a, b = max(i0, i - smooth), min(i1, i + smooth)
        out[i] = sum(rm[k] for k in range(a, b + 1)) / (b - a + 1)
    for j in range(1, fade + 1):
        w = 1.0 - j / (fade + 1)
        if i0 - j >= 0:
            out[i0 - j] = min(out[i0] * w, h[i0 - j])
        if i1 + j < n:
            out[i1 + j] = min(out[i1] * w, h[i1 + j])
    return out


# ------------------------------------------------------------------------------------------------- searching
def search_angle(ok, lo: float, hi: float, tol: float = 0.5) -> tuple[float, bool]:
    """The smallest angle in [lo, hi] (to tol) at which ok(angle) holds, for an ok that stays true once it holds
    (monotone); (hi, False) when it does not hold even at hi."""
    if ok(lo):
        return lo, True
    if not ok(hi):
        return hi, False
    while hi - lo > tol:
        mid = (lo + hi) / 2
        if ok(mid):
            hi = mid
        else:
            lo = mid
    return hi, True


def secant(f, goal: float, x0: float, x1: float, tol: float, lo: float, hi: float,
           max_iter: int = 8) -> tuple[float, float, bool]:
    """A root of f(x) = goal by the secant method from x0 and x1, each step clamped to [lo, hi]: (x, f(x), found
    within tol). For a measure that is about linear near the answer (the side grip's gap against the arms' turn)."""
    y0 = f(x0) - goal
    if abs(y0) <= tol:
        return x0, y0 + goal, True
    y1 = f(x1) - goal
    for _ in range(max_iter):
        if abs(y1) <= tol:
            return x1, y1 + goal, True
        if y1 == y0:
            break
        x2 = max(lo, min(hi, x1 - y1 * (x1 - x0) / (y1 - y0)))
        if x2 == x1:
            break
        x0, y0, x1, y1 = x1, y1, x2, f(x2) - goal
    if abs(y0) < abs(y1):
        x1, y1 = x0, y0
    return x1, y1 + goal, abs(y1) <= tol


# ------------------------------------------------------------------------------------------ the side grip (art #65)
def _v_cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _v_unit(a):
    n = _v_len(a)
    return tuple(x / n for x in a) if n > 1e-12 else (0.0, 0.0, 0.0)


def palm_normal(wrist, middle, index, pinky, side: str):
    """The unit normal out of a hand's palm from world joint positions: the wrist, the middle finger's knuckle and the
    index and pinky knuckles. Forward f (wrist to middle) and across a (index to pinky): a x f on the left hand, f x a
    on the right (world: front -Y, left +X, up +Z; a left palm down has a = +X, f = -Y and the normal -Z)."""
    f = _v_sub(middle, wrist)
    a = _v_sub(pinky, index)
    return _v_unit(_v_cross(a, f) if side == "L" else _v_cross(f, a))


def grip_goal(towards, tilt_deg: float = 0.0):
    """Where a gripping palm faces: the horizontal direction towards the other hand, turned up by tilt_deg (0: the
    palms vertical, facing each other; positive: turned up towards a tray)."""
    h = _v_unit((towards[0], towards[1], 0.0))
    t = math.radians(tilt_deg)
    return (h[0] * math.cos(t), h[1] * math.cos(t), math.sin(t))


def roll_angle(normal, goal, axis) -> float:
    """The signed angle (degrees, right-handed about axis) that turns normal onto goal, both projected onto the plane
    across axis (the forearm's roll that points the palm at the goal); 0 when either projection vanishes."""
    u = _v_unit(axis)
    n = _v_sub(normal, _v_mul(u, _v_dot(normal, u)))
    g = _v_sub(goal, _v_mul(u, _v_dot(goal, u)))
    if _v_len(n) < 1e-9 or _v_len(g) < 1e-9:
        return 0.0
    return math.degrees(math.atan2(_v_dot(u, _v_cross(n, g)), _v_dot(n, g)))


def grip_weights(frames: int, fps: float, from_s: float = 0.0, fade_s: float = 0.0) -> list[float]:
    """The side grip's weight per frame: 1 from from_s on, a smoothstep from 0 over the fade_s before it, 0 earlier."""
    out = []
    for k in range(frames):
        t = k / fps
        if t >= from_s - 1e-9:
            out.append(1.0)
        elif fade_s <= 0.0:
            out.append(0.0)
        else:
            out.append(smoothstep((t - (from_s - fade_s)) / fade_s))
    return out


def end_weights(frames: int, fps: float, at: str, fade_s: float) -> list[float]:
    """upper_match's weight per frame (frames: the count, both ends included): 1 on the touching frame (the last for
    at = "end", the first for "start"), a smoothstep to 0 over the fade_s from it, 0 beyond."""
    out = []
    for k in range(frames):
        t = ((frames - 1 - k) if at == "end" else k) / fps
        out.append(1.0 if t <= 1e-9 else 0.0 if fade_s <= 0.0 else smoothstep(1.0 - t / fade_s))
    return out


def spread(values: list) -> dict:
    """min, mean and max of a list of numbers (None when empty)."""
    if not values:
        return {"min": None, "mean": None, "max": None}
    return {"min": min(values), "mean": sum(values) / len(values), "max": max(values)}


# ---------------------------------------------------------------------------------------------------- mirror
def mirror_name(name: str) -> str:
    """X.L <-> X.R; other names (the centre bones) map to themselves."""
    if name.endswith(".L"):
        return name[:-2] + ".R"
    if name.endswith(".R"):
        return name[:-2] + ".L"
    return name


def mirror_pairs(names) -> dict:
    """Each bone's mirror partner; a side bone without its partner is an error."""
    names = set(names)
    out = {}
    for n in names:
        m = mirror_name(n)
        if m not in names:
            raise ValueError(f"{n} has no mirror partner {m}")
        out[n] = m
    return out


def mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def mat_inv(m):
    """The inverse of a 4x4 matrix (Gauss-Jordan with partial pivoting)."""
    a = [list(map(float, row)) + [1.0 if i == j else 0.0 for j in range(4)] for i, row in enumerate(m)]
    for c in range(4):
        p = max(range(c, 4), key=lambda r: abs(a[r][c]))
        if abs(a[p][c]) < 1e-15:
            raise ValueError("singular matrix")
        a[c], a[p] = a[p], a[c]
        piv = a[c][c]
        a[c] = [x / piv for x in a[c]]
        for r in range(4):
            if r != c and a[r][c]:
                f = a[r][c]
                a[r] = [x - f * y for x, y in zip(a[r], a[c])]
    return [row[4:] for row in a]


def det3(m) -> float:
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


def mirror_correction(S, rest_b, rest_m):
    """C[b] = (S rest[m(b)])^-1 rest[b]: the constant frame correction of bone b, whose partner is m(b), for the
    reflection S (armature space). It assumes nothing about bone rolls."""
    return mat_mul(mat_inv(mat_mul(S, rest_m)), rest_b)


def mirror_pose(S, pose_m, C):
    """P'[b] = S P[m(b)] C[b]: bone b's mirrored pose from its partner's. Exact at rest, a proper rotation
    (det +1), and mirroring twice gives the pose back (S S = I, C[m(b)] C[b] = I)."""
    return mat_mul(mat_mul(S, pose_m), C)


# ---------------------------------------------------------------------------------------- the relaxed idle (art #49)
def smoothstep(t: float) -> float:
    """3t^2 - 2t^3 on t clamped to [0, 1]."""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def finger_curls(table: dict) -> dict:
    """A hands_relax curl table as {bone base name: degrees}: {"Index": [16, 22, 12]} -> Index2 16, Index3 22,
    Index4 12 (segment 1, the metacarpal, is never curled)."""
    return {f"{finger}{k + 2}": float(d) for finger, degs in table.items() for k, d in enumerate(degs)}


def curl_goal(angle: float, curl: float, cap: float | None) -> float:
    """A finger joint's new angle (degrees): the curl, or with a cap the joint's own angle up to cap times the curl
    (a talk's gesture stays, its fist goes)."""
    return curl if cap is None else min(angle, curl * cap)


def stance_targets(hips: dict, rest_offset: dict, feet_z: dict, out_m: float) -> dict:
    """The feet of a stance, one fixed point per side: its own hip joint plus the rest pose's hip-to-ankle offset
    (horizontally) plus out_m outwards along X (the left is +X), at the foot's own height. Points are (x, y, z) in
    world metres in the set's frame (the character faces -Y)."""
    out = {}
    for side, sign in (("L", 1.0), ("R", -1.0)):
        h, o = hips[side], rest_offset[side]
        out[side] = (h[0] + o[0] + sign * out_m, h[1] + o[1], feet_z[side])
    return out


def stance_lift(hips: dict, feet: dict, targets: dict, span: float = 0.2, rounds: int = 60) -> float:
    """The one constant lift of the hips (m) that keeps the legs' mean hip-to-ankle distance when the feet move from
    `feet` to `targets` (bisection in [-span, span]: the distance grows with the lift)."""
    want = sum(_v_len(_v_sub(feet[s], hips[s])) for s in "LR") / 2.0
    lo, hi = -span, span
    for _ in range(rounds):
        mid = (lo + hi) / 2.0
        d = sum(_v_len(_v_sub(targets[s], _v_add(hips[s], (0.0, 0.0, mid)))) for s in "LR") / 2.0
        if d > want:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2.0


def pitch_of(forward) -> float:
    """A forward direction's angle above the horizontal (degrees; + looks up)."""
    n = _v_len(forward)
    return math.degrees(math.asin(max(-1.0, min(1.0, forward[2] / n)))) if n > 1e-12 else 0.0


def head_fix(pitches: list, target_deg: float = 0.0) -> float:
    """The constant pitch (degrees) that puts a clip's mean head pitch at target_deg."""
    return target_deg - sum(pitches) / len(pitches)


def yaw_out(foot, toe, side: str) -> float:
    """A foot's yaw out (degrees, + = the toe turned outwards) against the set's aim (-Y): the floor direction from the
    foot's head to its toe's head; the left foot turns out to +X (counter-clockwise from above), the right to -X."""
    f = (toe[0] - foot[0], toe[1] - foot[1])
    return (1.0 if side == "L" else -1.0) * signed_angle_2d((0.0, -1.0), f)


def knees_out(flex_deg: float, deg: float, from_deg: float, full_deg: float, weight: float = 1.0) -> float:
    """How far (degrees) a knee swings out in a bend: 0 below from_deg of knee bend, `deg` from full_deg, a
    smoothstep between, times the weight."""
    return deg * smoothstep((flex_deg - from_deg) / (full_deg - from_deg)) * weight


def reach_lift(hip, foot, reach: float) -> float:
    """The most the hip may rise (m) while a leg of length `reach` still reaches its foot (+Z up); 0 minus the
    foot's depth below the hip when the foot is horizontally out of reach."""
    h2 = (foot[0] - hip[0]) ** 2 + (foot[1] - hip[1]) ** 2
    if reach * reach <= h2:
        return 0.0
    return math.sqrt(reach * reach - h2) - (hip[2] - foot[2])


def planted_until(track: list, start: int, step: int, speed_m: float, rise_m: float) -> int:
    """The last frame, going from `start` by `step` (+1 or -1), up to which a foot stays planted (its points (x, y, z),
    +Z up): each frame it moves less than speed_m along the floor and it stays less than rise_m above where it is at
    `start`. A flat foot that creeps along the floor or settles onto it is planted; a foot that lifts or moves off is
    not (art #49: a distance from the touching frame counted a creeping or settling foot as moving, and idle_ends then
    slid it along the floor)."""
    p = start
    z0 = track[start][2]
    while 0 <= p + step < len(track):
        a, b = track[p], track[p + step]
        if math.hypot(b[0] - a[0], b[1] - a[1]) >= speed_m or b[2] - z0 >= rise_m:
            break
        p += step
    return p


AIR_M = 0.01  # idle_ends: a foot lifted more than this is in the air; never both feet at once


def idle_end_weights(frames: int, ends, feet: dict, fade: int, speed_m: float, rise_m: float, step_m: float,
                     upper: bool = True) -> dict:
    """The weights of idle_ends over frames 0..frames (anim_edit.op_idle_ends; the lab's round D, blend_transitions in
    D:/prime-art-raw/research/2026-10-05-faces/lab/clay_d/clay_idle.py).

    ends: "start" and/or "end", the clip's ends that meet the idle. feet: {"L"/"R": [(x, y, z) per frame]}, the feet
    before the edit (world m). Returns
      upper   per frame, the upper body's weight: 1 at a touching frame, a smoothstep to 0 over `fade` frames (all 0
              with upper=False: the feet and legs only);
      ends    per end: its touching frame and per side the foot's plan:
              "planted"  the foot stays planted (by planted_until with speed_m and rise_m) to the other end;
              "held"     fewer than 2 frames would be left: held to the other end;
              "hold"     both ends meet the idle and the foot only shuffles along the floor between them (it moves
                         after the start's planted frames and before the end's, rising under step_m / 2): held at the
                         idle's on every frame (its window: the frames it moves on), so neither end's fade slides
                         it or lifts it (art #49: the package clips' feet both shuffled, and both were lifted at once);
              "fade"     held while planted, then a smoothstep to 0 over up to `fade` frames (its window); a foot that
                         shuffles along the floor there, rising under step_m / 2, is lifted to the step's arc above
                         where it was planted so the fade does not slide it ("lifted"); a foot that leaves the floor by
                         itself is not;
              "step"     planted all through, and the clip's other end meets another clip: the foot steps step_m high
                         over min(fade, frames) frames where the other foot moves least, off the frames where the
                         other foot is lifted;
              never both feet in the air: a lift that has both feet over AIR_M up on a common frame (steps keep
              theirs first, then the earlier lift) is dropped ("lift_dropped"; that foot fades along the floor);
      w       per end and side, the foot's weight per frame;
      feet    per side, the foot's weight per frame (the largest over the ends);
      lift    per side, the lift per frame (m): a step's arc, step_m * 4x(1 - x) for the foot's weight x, and in a
              fade what the foot itself lacks of that arc;
      hold    per held side, the share of the end's numbers per frame: 0 up to its window, a smoothstep to 1 over it.
    """
    n = frames
    ends = tuple(ends)
    upper_on = upper
    upper = [0.0] * (n + 1)
    w = {e: {s: [0.0] * (n + 1) for s in "LR"} for e in ends}
    lifts = {}  # (end, side) -> the lift per frame (m)
    plan = {}
    hold = {}

    def moved(s, a, b):
        return sum(_v_len(_v_sub(feet[s][f + 1], feet[s][f])) for f in range(a, b))

    if "start" in ends and "end" in ends:
        for s in "LR":
            a = planted_until(feet[s], 0, 1, speed_m, rise_m)
            b = planted_until(feet[s], n, -1, speed_m, rise_m)
            if a < b:
                rise = max(feet[s][f][2] for f in range(a, b + 1)) - min(feet[s][a][2], feet[s][b][2])
                if rise < step_m / 2.0:
                    hold[s] = {"window": [a, b], "shuffle_rise_cm": round(rise * 100.0, 2),
                               "shuffle_moves_cm": round(moved(s, a, b) * 100.0, 1)}

    for e in ends:
        ft, d = (0, 1) if e == "start" else (n, -1)
        far = n if d == 1 else 0
        far_idle = ("end" if e == "start" else "start") in ends
        for f in range(n + 1):
            if upper_on:
                upper[f] = max(upper[f], 1.0 - smoothstep(d * (f - ft) / fade))
        info = {"frame": ft, "upper_fade_to": ft + d * fade}
        steps = []
        for s in "LR":
            p = planted_until(feet[s], ft, d, speed_m, rise_m)
            rem = abs(far - p)
            fi = {"planted_to": p}
            if s in hold:
                fi.update(mode="hold", **hold[s])
                w[e][s] = [1.0] * (n + 1)
            elif rem == 0 and not far_idle:
                fi["mode"] = "step"
                steps.append(s)
            elif rem < 2:
                fi["mode"] = "planted" if rem == 0 else "held"
                w[e][s] = [1.0] * (n + 1)
            else:
                span = min(fade, rem)
                fi.update(mode="fade", window=sorted([p, p + d * span]))
                w[e][s] = [1.0 - smoothstep(d * (f - p) / span) for f in range(n + 1)]
                z0 = feet[s][p][2]
                lo_w, hi_w = fi["window"]
                fi["lifted"] = max(feet[s][f][2] - z0 for f in range(lo_w, hi_w + 1)) < step_m / 2.0
                if fi["lifted"]:
                    lifts[(e, s)] = [max(0.0, step_m * 4.0 * x * (1.0 - x) - max(0.0, feet[s][f][2] - z0))
                                     if 0.0 < x < 1.0 else 0.0 for f, x in enumerate(w[e][s])]
            info[s] = fi
        for s in steps:  # after the other foot's plan: a step keeps off the frames where the other foot is lifted
            span = min(fade, n)
            o = "R" if s == "L" else "L"
            busy = {f for (_e, s2), li in lifts.items() if s2 == o for f, v in enumerate(li) if v > AIR_M}
            cands = [(any(a < f < a + span for f in busy), round(moved(o, a, a + span) * 100.0, 1),
                      abs((a + span if d == 1 else a) - far), a) for a in range(0, n - span + 1)]
            _clash, cost, _dist, a = min(cands)
            lo, hi = a, a + span
            info[s].update(mode="step", window=[lo, hi], other_foot_moves_cm=cost)
            for f in range(n + 1):
                t = (f - lo) / span if d == 1 else (hi - f) / span
                w[e][s][f] = 1.0 - smoothstep(t)
            lifts[(e, s)] = [step_m * 4.0 * x * (1.0 - x) for x in w[e][s]]
        plan[e] = info

    # never both feet in the air at once: steps keep their lift first, then the earlier lifts
    def first(k):
        return min(f for f, v in enumerate(lifts[k]) if v > 0.0) if any(v > 0.0 for v in lifts[k]) else n + 1

    kept = {s: [0.0] * (n + 1) for s in "LR"}
    for k in sorted(lifts, key=lambda k: (plan[k[0]][k[1]]["mode"] != "step", first(k), k)):
        e, s = k
        o = "R" if s == "L" else "L"
        both = [f for f, v in enumerate(lifts[k]) if v > AIR_M and kept[o][f] > AIR_M]
        if both:
            plan[e][s].update(lifted=False, lift_dropped=f"the other foot is lifted on frames {both[0]}-{both[-1]}")
            continue
        kept[s] = [max(a, b) for a, b in zip(kept[s], lifts[k])]
    feet_w = {s: [max(w[e][s][f] for e in ends) for f in range(n + 1)] for s in "LR"}
    mix = {}
    for s, h in hold.items():
        a, b = h["window"]
        mix[s] = [smoothstep((f - a) / (b - a)) for f in range(n + 1)]
    return {"upper": upper, "ends": plan, "w": w, "feet": feet_w, "lift": kept, "hold": mix}


def end_mix(weights: dict, side: str, f: int, frames: int) -> list:
    """The ends whose edit reaches frame f for one foot, each with its share; a clip whose both ends meet the idle
    moves from the start's numbers to the end's along the clip. weights: idle_end_weights' "w"."""
    ws = [(e, weights[e][side][f]) for e in weights if weights[e][side][f] > 0.0]
    if len(ws) <= 1:
        return [(e, 1.0) for e, _ in ws]
    span = max(1, frames)
    ts = [(e, x * (((frames - f) if e == "start" else f) / span)) for e, x in ws]
    tot = sum(t for _, t in ts)
    return [(e, t / tot) for e, t in ts] if tot > 0.0 else [(e, 1.0 / len(ws)) for e, _ in ws]
