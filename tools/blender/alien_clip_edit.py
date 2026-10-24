"""The alien's clip edits (art #196, A1), in Blender on the character's own actions (the contract skeleton's names), so
the clips look right on the bare alien body: alien_char_build.py runs them before the export when given
`--clip-edits <toml>` (tools/blender/anim_sets/alien.toml). The human MVP set (anim_sets/mvp.toml, anim_set.py) is not
touched: these clips are the shared alien body's UAL1 clips copied key for key (alien_body.py, step 7), not the set's.

The settings: `[defaults]` and one `[clips.<name>]` table per clip, each key overriding the default:
- `finger_cap_deg`: every finger bone's turn from its rest (its basis rotation; the contract rest has straight
  fingers) capped to this angle on every key, the same axis kept (anim_edit's `hands_relax` with `cap`, for a rig
  without the UM finger names): a fist opens to a relaxed hand, a smaller gesture stays. 0 or absent: untouched.
- `thumb_cap_deg`: the same for the thumb's Proximal and Distal (the Metacarpal is left alone).
- `abduct_deg`: each upper arm turned away from the body about the body's forward axis at the shoulder (the bone's
  rest frame, so it rides on the clavicle), one angle on every key: the hands come out of a body thinner than the
  clip's own (anim_edit's `arm_offset`); negative brings them in.
- `swing_deg`: each upper arm turned about the body's left-right axis, positive swinging the hands forward
  (anim_edit's `arm_offset` with `axis = "swing"`).
- `head_up_deg` (A2): Neck and Head each turned half of it about the body's left-right axis, positive lifting the
  face (the crouch sank the head into the chest).
- `lean_deg` (A2): Spine turned about the body's left-right axis, positive leaning the trunk forward.
- `cut_straight_deg` (A2, a one-shot's in-place push-off): the frames after the first on which both knees bend less
  than this angle (the straight stand between the crouch and the tuck: in place the body does not rise, so it read as a
  snap to a rest pose) are dropped, the later keys moved earlier so `cut_gap` frames (default 3) join the two sides.
- `hips_up_cm` (A2, the crouch): the Hips' keys raised by this much and the legs solved again (two-bone IK per frame:
  each ankle and foot kept where the clip put them in the world, the knee in the plane of the clip's own, turned
  `knees_in_deg` toward the body's middle about the hip-ankle line).
- `chest_up_deg` (A3, the crouch): Spine and Chest each turned half of it about the body's left-right axis, positive
  lifting the chest (the trunk more upright), applied like `lean_deg` (which turns the Spine alone the other way).
- `repeat` (A3, a loop): the clip's cycle played this many times in one longer loop (the keys copied, each copy shifted
  by the cycle's length), so a slow layer (the sway) can span several of the clip's own cycles.
- `sway_cm` (A3, the idle's weight shift): the Hips moved sideways by up to this much, once to each side over the
  (repeated) loop (a sine, so the seam is clean), the legs solved again per frame as with `hips_up_cm` (the feet kept);
  `sway_counter_deg`: the Spine rolled the other way by up to this much and the Head back by half of it, so the head
  stays over the feet.
- `floor`: `true` lifts the Hips on the frames whose posed skin goes under the floor (anim_edit's `floor` with
  `mode = "lift"`): per frame the lowest skinned vertex below z = 0, a running max over +-2 frames smoothed over
  +-2 frames (`lift_profile`; a `*_Loop` clip wraps around its seam), added to the Hips' location keys along the
  world's up; a clip still more than 0.5 cm under the floor afterwards fails the build. `floor_reach` (A3, default 2):
  the running max and average's half width in frames; 0 lifts each frame by exactly its own need, the Hips' location
  keyed on every frame (the crouch: the smoothing floated the planted foot up to 2.95 cm). `"ground"` (A3, a one-shot
  that leaves the floor in place, Jump_Start): no lift, but the frames up to the push-off (the cut's last kept crouch
  frame, every frame without a cut) still fail the build under -0.5 cm; `false`: neither lifted nor checked (an
  airborne loop, Jump_Air, which the game holds off the floor).
Only the clips listed under `[clips.*]` are edited, each with `[defaults]` under its own keys; an unlisted clip is
left exactly as the body carries it (A2: A1 gave every clip the defaults).
Pure maths (`cap_turn`, `axis_turn`, `q_rotate`, `lift_profile`, `cut_frames`, `two_bone`) has no bpy and is unit-tested (tools/tests/test_alien_clip_edit.py).
"""
from __future__ import annotations

import math
import tomllib

FINGERS = ("Index", "Middle", "Ring", "Little")
SEGMENTS = ("Proximal", "Intermediate", "Distal")
THUMB = ("ThumbProximal", "ThumbDistal")
KEYS = ("finger_cap_deg", "thumb_cap_deg", "abduct_deg", "swing_deg", "head_up_deg", "lean_deg", "cut_straight_deg",
        "cut_gap", "hips_up_cm", "knees_in_deg", "floor", "floor_reach", "chest_up_deg", "repeat", "sway_cm",
        "sway_counter_deg")
FLOOR_FAIL_CM = -0.5  # A2: a clip still this far under the floor after its lift fails the build
ANKLE_MISS_FAIL_CM = 0.5  # A3: a re-solved leg whose Foot lands this far from its kept place (re-evaluated) fails


def sway(n: int) -> list[float]:
    """A3: the idle's weight shift per frame of a loop of n frames (the last the first again): one sine period, 0 at
    the seam, +1 a quarter in (over the left foot), -1 three quarters in."""
    m = max(1, n - 1)
    return [math.sin(2.0 * math.pi * i / m) for i in range(n)]


def repeat_keys(keys: list[float], f0: float, f1: float, times: int) -> list[tuple[float, int]]:
    """A3: (frame, source index) of a cycle's keys repeated `times` times: the keys on [f0, f1) copied, each copy
    shifted by f1 - f0, then the last key at f1 (the seam) moved to the end; plain data for the bpy side."""
    period = f1 - f0
    body = [(k, i) for i, k in enumerate(keys) if k < f1 - 1e-6]
    end = [(k, i) for i, k in enumerate(keys) if k >= f1 - 1e-6]
    out = [(k + r * period, i) for r in range(max(1, times)) for k, i in body]
    out += [(k + (max(1, times) - 1) * period, i) for k, i in end]
    return out


def settings(path: str, clip: str) -> dict:
    """The clip's settings: [defaults] under [clips.<clip>]; {} for a clip not listed (left untouched, A2); an unknown
    key raises."""
    with open(path, "rb") as f:
        data = tomllib.load(f)
    clips = data.get("clips", {})
    for name, cfg in [("defaults", data.get("defaults", {}))] + list(clips.items()):
        bad = sorted(set(cfg) - set(KEYS))
        if bad:
            raise ValueError(f"{path} [{name}]: unknown keys {bad}")
    if clip not in clips:
        return {}
    out = dict(data.get("defaults", {}))
    out.update(clips[clip])
    return out


def cap_turn(q: tuple[float, float, float, float], cap_deg: float) -> tuple[float, float, float, float]:
    """q (w, x, y, z) shortened to at most cap_deg about its own axis (unchanged under the cap)."""
    w, x, y, z = q
    if w < 0.0:
        w, x, y, z = -w, -x, -y, -z
    s = math.sqrt(x * x + y * y + z * z)
    ang = 2.0 * math.atan2(s, w)
    cap = math.radians(cap_deg)
    if cap_deg <= 0.0 or ang <= cap or s < 1e-12:
        return (w, x, y, z)
    h = cap * 0.5
    k = math.sin(h) / s
    return (math.cos(h), x * k, y * k, z * k)


def axis_turn(axis: tuple[float, float, float], deg: float) -> tuple[float, float, float, float]:
    """The quaternion (w, x, y, z) of deg about axis."""
    n = math.sqrt(sum(a * a for a in axis))
    h = math.radians(deg) * 0.5
    return (math.cos(h), *(a / n * math.sin(h) for a in axis))


def q_mul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (aw * bw - ax * bx - ay * by - az * bz, aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx, aw * bz + ax * by - ay * bx + az * bw)


def q_rotate(q, v):
    """v turned by q (w, x, y, z)."""
    p = q_mul(q_mul(q, (0.0, *v)), (q[0], -q[1], -q[2], -q[3]))
    return p[1:]


def lift_profile(lowest: list[float], reach: int = 2, wrap: bool = False) -> list[float]:
    """Per frame the lift (m) that puts the lowest point on the floor: max(0, -lowest) as a running max over +-reach
    frames, then a moving average over +-reach, so no frame stays under and the lift has no step. The ends are held;
    wrap (a loop whose last frame repeats its first, A2): the window runs around the seam, so the last frame's lift
    equals the first's and the loop does not pop."""
    n = len(lowest)
    need = [max(0.0, -z) for z in lowest]
    if wrap and n > 2:
        m = n - 1  # the period: the last frame is the first again
        cyc = need[:m]
        cyc[0] = max(cyc[0], need[-1])
        run = [max(cyc[(i + d) % m] for d in range(-reach, reach + 1)) for i in range(m)]
        avg = [sum(run[(i + d) % m] for d in range(-reach, reach + 1)) / (2 * reach + 1) for i in range(m)]
        return avg + [avg[0]]
    run = [max(need[max(0, i - reach):i + reach + 1]) for i in range(n)]
    return [sum(run[max(0, i - reach):i + reach + 1]) / len(run[max(0, i - reach):i + reach + 1]) for i in range(n)]


def cut_frames(straight: list[bool], gap: int):
    """The push-off's straight run to drop: (lo, hi, shift), lo and hi the frames kept on each side of the first run of
    straight frames after the first frame, shift what moves hi and the frames after it earlier so gap frames join lo
    to hi; None without such a run (or one reaching the end)."""
    idx = [i for i, s in enumerate(straight) if s and i > 0]
    if not idx:
        return None
    b = idx[0]
    while b + 1 < len(straight) and straight[b + 1]:
        b += 1
    lo, hi = idx[0] - 1, b + 1
    if hi >= len(straight):
        return None
    return lo, hi, max(0, (hi - lo) - gap)


def two_bone(hip, knee, ankle, new_hip, pole_turn=None):
    """The knee for a hip moved to new_hip with the ankle kept (plain tuples): the same thigh and shin lengths, the knee
    in the plane through the hip-ankle line and the clip's own knee (pole_turn(axis, pole): turns that pole first)."""
    def sub(a, b): return tuple(x - y for x, y in zip(a, b))
    def add(a, b): return tuple(x + y for x, y in zip(a, b))
    def mul(a, k): return tuple(x * k for x in a)
    def dot(a, b): return sum(x * y for x, y in zip(a, b))

    def norm(a):
        n = math.sqrt(dot(a, a))
        return mul(a, 1.0 / n) if n > 1e-12 else a
    la = math.sqrt(dot(sub(knee, hip), sub(knee, hip)))
    lb = math.sqrt(dot(sub(ankle, knee), sub(ankle, knee)))
    ax0 = norm(sub(ankle, hip))
    pole = sub(knee, hip)
    pole = sub(pole, mul(ax0, dot(pole, ax0)))
    if pole_turn is not None:
        pole = tuple(pole_turn(ax0, pole))
    dv = sub(ankle, new_hip)
    d = min(math.sqrt(dot(dv, dv)), (la + lb) * 0.9995)
    axis = norm(dv)
    pole = norm(sub(pole, mul(axis, dot(pole, axis))))
    x = (la * la - lb * lb + d * d) / (2.0 * d)
    h = math.sqrt(max(0.0, la * la - x * x))
    return add(add(new_hip, mul(axis, x)), mul(pole, h))


def _bags(act):
    for layer in act.layers:
        for strip in layer.strips:
            yield from strip.channelbags


def _assign(arm, act):
    ad = arm.animation_data or arm.animation_data_create()
    ad.action = act
    ad.action_slot = act.slots[0]
    return int(act.frame_range[0]), int(act.frame_range[1])


def apply(arm, skin, path: str) -> dict:
    """Edits every CharacterArmature|<clip> action of arm (a Blender armature object) listed in the settings; returns
    the report per clip (the settings used, the largest finger turn before and after, the cut, the hips, the floor)."""
    from mathutils import Vector  # Blender only

    rest = {b.name: b.matrix_local.to_3x3() for b in arm.data.bones}
    world = arm.matrix_world.to_3x3().normalized().inverted()
    fwd_arm = world @ Vector((0.0, -1.0, 0.0))  # the character faces -Y in Blender
    side_arm = world @ Vector((1.0, 0.0, 0.0))  # its left
    up_arm = world @ Vector((0.0, 0.0, 1.0))
    report = {}
    for act in [a for a in __import__("bpy").data.actions if a.name.startswith("CharacterArmature|")]:
        clip = act.name.split("|", 1)[1]
        cfg = settings(path, clip)
        if not cfg:
            report[clip] = {"settings": {}, "untouched": True}
            continue
        rep0 = {}
        if int(cfg.get("repeat", 1)) > 1:
            rep0["repeat"] = repeat(act, int(cfg["repeat"]))
        caps = {}
        for side in ("Left", "Right"):
            for f in FINGERS:
                for seg in SEGMENTS:
                    caps[f"{side}{f}{seg}"] = float(cfg.get("finger_cap_deg", 0.0))
            for t in THUMB:
                caps[f"{side}{t}"] = float(cfg.get("thumb_cap_deg", 0.0))
        turns = {}
        for side, sign in (("Left", 1.0), ("Right", -1.0)):
            b = f"{side}UpperArm"
            if b not in rest:
                continue
            r_inv = rest[b].inverted()
            q = (1.0, 0.0, 0.0, 0.0)
            if cfg.get("abduct_deg"):
                q = q_mul(axis_turn(tuple(r_inv @ fwd_arm), sign * float(cfg["abduct_deg"])), q)
            if cfg.get("swing_deg"):
                # positive: the hands forward (toward -Y) about the left-right axis: about +X by a negative angle
                q = q_mul(axis_turn(tuple(r_inv @ side_arm), -float(cfg["swing_deg"])), q)
            if q != (1.0, 0.0, 0.0, 0.0):
                turns[b] = q
        # A2: the face up (Neck and Head, half each) and the trunk's lean forward; about +X a negative angle lifts -Y
        for bones, deg in ((("Neck", "Head"), -float(cfg.get("head_up_deg", 0.0)) * 0.5),
                           (("Spine",), float(cfg.get("lean_deg", 0.0))),
                           (("Spine", "Chest"), -float(cfg.get("chest_up_deg", 0.0)) * 0.5)):  # A3
            for b in bones:
                if deg and b in rest:
                    t = axis_turn(tuple(rest[b].inverted() @ side_arm), deg)
                    turns[b] = q_mul(t, turns[b]) if b in turns else t
        rep = {"settings": cfg, "finger_max_before_deg": 0.0, "finger_max_after_deg": 0.0, "bones_edited": 0, **rep0}
        for bag in _bags(act):
            groups: dict[str, list] = {}
            for fc in bag.fcurves:
                if fc.data_path.endswith(".rotation_quaternion"):
                    groups.setdefault(fc.data_path.split('"')[1], [None] * 4)[fc.array_index] = fc
            for bone, fcs in groups.items():
                cap = caps.get(bone, 0.0)
                turn = turns.get(bone)
                if (cap <= 0.0 and turn is None) or None in fcs:
                    continue
                n = len(fcs[0].keyframe_points)
                if any(len(fc.keyframe_points) != n for fc in fcs):
                    raise ValueError(f"{act.name} {bone}: rotation channels keyed apart")
                vals = []
                for fc in fcs:
                    buf = [0.0] * (2 * n)
                    fc.keyframe_points.foreach_get("co", buf)
                    vals.append(buf)
                for k in range(n):
                    q = tuple(vals[i][2 * k + 1] for i in range(4))
                    if cap > 0.0:
                        before = 2.0 * math.degrees(math.acos(min(1.0, abs(q[0]) / max(1e-12, math.sqrt(sum(c * c for c in q))))))
                        q = cap_turn(q, cap)
                        rep["finger_max_before_deg"] = max(rep["finger_max_before_deg"], round(before, 2))
                        rep["finger_max_after_deg"] = max(rep["finger_max_after_deg"],
                                                          round(2.0 * math.degrees(math.acos(min(1.0, abs(q[0])))), 2))
                    if turn is not None:
                        q = q_mul(turn, q)
                    for i in range(4):
                        vals[i][2 * k + 1] = q[i]
                for i, fc in enumerate(fcs):
                    fc.keyframe_points.foreach_set("co", vals[i])
                    for kp in fc.keyframe_points:  # the handles follow the new values
                        kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
                    fc.update()
                rep["bones_edited"] += 1
        if cfg.get("cut_straight_deg"):
            rep["cut"] = cut(arm, act, float(cfg["cut_straight_deg"]), int(cfg.get("cut_gap", 3)))
        if cfg.get("hips_up_cm") or cfg.get("sway_cm"):
            rep["hips_up"] = hips_up(arm, act, float(cfg.get("hips_up_cm", 0.0)) / 100.0,
                                     float(cfg.get("knees_in_deg", 0.0)), up_arm, side_arm, rest,
                                     sway_m=float(cfg.get("sway_cm", 0.0)) / 100.0,
                                     counter_deg=float(cfg.get("sway_counter_deg", 0.0)), fwd_arm=fwd_arm)
        mode = cfg.get("floor", False)
        if mode is True:
            rep["floor"] = floor(arm, skin, act, rest, up_arm, wrap=clip.endswith("_Loop"),
                                 reach=int(cfg.get("floor_reach", 2)))
            if rep["floor"]["lowest_after_cm"] < FLOOR_FAIL_CM:
                raise ValueError(f"{act.name}: still {rep['floor']['lowest_after_cm']} cm under the floor after the lift")
        elif mode == "ground":  # A3: no lift; the crouch before the push-off still checked
            last = rep.get("cut", {}).get("frames_dropped", [None])[0]
            rep["floor"] = floor(arm, skin, act, rest, up_arm, check_only=True,
                                 check_to=None if last is None else last - 1)
            if rep["floor"]["lowest_after_cm"] < FLOOR_FAIL_CM:
                raise ValueError(f"{act.name}: its ground frames are {rep['floor']['lowest_after_cm']} cm under the floor")
        elif mode not in (False, None):
            raise ValueError(f"{act.name}: floor must be true, false or \"ground\", not {mode!r}")
        report[clip] = rep
    return report


def cut(arm, act, straight_deg: float, gap: int) -> dict:
    """The `cut_straight_deg` edit: drops the push-off's straight-legged frames (both LowerLegs under straight_deg from
    their rest) and moves the later keys earlier (cut_frames)."""
    import bpy

    f0, f1 = _assign(arm, act)
    pb = arm.pose.bones
    straight = []
    bends = []
    for f in range(f0, f1 + 1):
        bpy.context.scene.frame_set(f)
        b = [math.degrees(pb[f"{s}LowerLeg"].matrix_basis.to_quaternion().angle) for s in ("Left", "Right")]
        bends.append(round(max(b), 1))
        straight.append(max(b) < straight_deg)
    arm.animation_data.action = None
    found = cut_frames(straight, gap)
    if not found:
        return {"cut": None, "knee_bend_deg": bends}
    lo, hi, shift = found
    lo_f, hi_f = f0 + lo, f0 + hi
    for bag in _bags(act):
        for fc in bag.fcurves:
            pts = fc.keyframe_points
            for i in reversed(range(len(pts))):
                if lo_f < pts[i].co[0] < hi_f:
                    pts.remove(pts[i], fast=True)
            for kp in pts:
                if kp.co[0] >= hi_f:
                    kp.co[0] -= shift
                    kp.handle_left[0] -= shift
                    kp.handle_right[0] -= shift
                kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
            fc.update()
    act.use_frame_range = False
    return {"frames_dropped": [lo_f + 1, hi_f - 1], "shift": shift, "knee_bend_deg": bends,
            "frames_before": f1 - f0, "frames_after": int(act.frame_range[1] - act.frame_range[0])}


def repeat(act, times: int) -> dict:
    """The `repeat` edit (A3): every channel's keys on the cycle [f0, f1) copied times - 1 more times, each copy
    shifted by the cycle's length (repeat_keys), the seam key moved to the new end."""
    f0, f1 = (float(x) for x in act.frame_range)
    for bag in _bags(act):
        for fc in bag.fcurves:
            pts = fc.keyframe_points
            n = len(pts)
            co = [0.0] * (2 * n)
            pts.foreach_get("co", co)
            plan = repeat_keys([co[2 * i] for i in range(n)], f0, f1, times)
            vals = [(fr, co[2 * i + 1], pts[i].interpolation) for fr, i in plan]
            pts.clear()
            pts.add(len(vals))
            pts.foreach_set("co", [x for fr, v, _ in vals for x in (fr, v)])
            for kp, (_, _, ip) in zip(pts, vals):
                kp.interpolation = ip
                kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
            fc.update()
    act.use_frame_range = False
    return {"times": times, "frames_before": int(f1 - f0), "frames_after": int(act.frame_range[1] - act.frame_range[0])}


def _hips_loc(act):
    loc = {}
    for bag in _bags(act):
        for fc in bag.fcurves:
            if fc.data_path == 'pose.bones["Hips"].location':
                loc[fc.array_index] = fc
    if len(loc) != 3:
        raise ValueError(f"{act.name}: no Hips location keys to move")
    return loc


def _shift_hips(act, f0, f1, offsets, bake=False):
    """The Hips' location keys moved by offsets[f - f0] (a vector in the Hips' rest frame: a basis location is in
    that frame). bake (A3): the channels first keyed on every frame (linear), so a per-frame offset holds between the
    clip's own keys."""
    for i, fc in _hips_loc(act).items():
        if bake:
            co = [x for f in range(f0, f1 + 1) for x in (float(f), fc.evaluate(f) + offsets[f - f0][i])]
            fc.keyframe_points.clear()
            fc.keyframe_points.add(len(co) // 2)
            fc.keyframe_points.foreach_set("co", co)
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
        else:
            for kp in fc.keyframe_points:
                f = min(max(int(round(kp.co[0])), f0), f1)
                d = offsets[f - f0][i]
                kp.co[1] += d
                kp.handle_left[1] += d
                kp.handle_right[1] += d
        fc.update()


def hips_up(arm, act, metres: float, knees_in_deg: float, up_arm, side_arm, rest, sway_m: float = 0.0,
            counter_deg: float = 0.0, fwd_arm=None) -> dict:
    """The `hips_up_cm` and `sway_cm` edits: the Hips raised (and swayed sideways, A3), each leg solved again per
    frame (two_bone), the feet kept in the world; keys on every frame for the UpperLeg, LowerLeg and Foot rotations
    (and the Hips' location with a sway). A3: the UpperLeg's parent is read from the rig (it moves rigidly with the
    Hips), and the feet are measured on the re-evaluated rig afterwards (ankle_miss_max_cm; over ANKLE_MISS_FAIL_CM
    fails the build)."""
    import bpy
    from mathutils import Matrix, Quaternion, Vector

    f0, f1 = _assign(arm, act)
    pb = arm.pose.bones
    bones = arm.data.bones
    legs = [(s, f"{s}UpperLeg", f"{s}LowerLeg", f"{s}Foot") for s in ("Left", "Right")]
    parents = {bones[u].parent.name for _, u, _, _ in legs}
    rec = {}
    for f in range(f0, f1 + 1):
        bpy.context.scene.frame_set(f)
        rec[f] = {n: pb[n].matrix.copy() for n in parents | {x for leg in legs for x in leg[1:]}}
    arm.animation_data.action = None
    sw = sway(f1 - f0 + 1)
    up, side = Vector(up_arm).normalized(), Vector(side_arm).normalized()
    moves = [up * metres + side * (sway_m * sw[f - f0]) for f in range(f0, f1 + 1)]  # armature space
    hips_rest_inv = rest["Hips"].inverted()
    _shift_hips(act, f0, f1, [hips_rest_inv @ m for m in moves], bake=bool(sway_m))
    if counter_deg and sway_m:  # the Spine rolls against the shift, the Head back by half
        for bone, k in (("Spine", -1.0), ("Head", 0.5)):
            _roll_keys(act, bone, rest[bone].inverted() @ Vector(fwd_arm), [k * counter_deg * x for x in sw], f0)

    def rel(child):  # the child's rest relative to its parent's
        b = bones[child]
        return b.parent.matrix_local.inverted() @ b.matrix_local

    fcs = {}
    for bag in _bags(act):
        for fc in bag.fcurves:
            if fc.data_path.endswith(".rotation_quaternion"):
                fcs[(fc.data_path.split('"')[1], fc.array_index)] = fc
    prev = {}
    solved: dict[tuple[str, int], list[float]] = {}
    for f in range(f0, f1 + 1):
        r = rec[f]
        lift = moves[f - f0]
        for side_name, u, lo, ft in legs:
            parent = Matrix.Translation(lift) @ r[bones[u].parent.name]
            mu, ml, mf = r[u], r[lo], r[ft]
            hip, knee, ank = mu.translation, ml.translation, mf.translation
            outward = side * (1.0 if side_name == "Left" else -1.0)

            def turn_pole(ax0, pole, outward=outward):
                if not knees_in_deg:
                    return pole
                q = Quaternion(Vector(ax0), math.radians(knees_in_deg))
                a, b = q @ Vector(pole), q.inverted() @ Vector(pole)
                return a if a.dot(outward) < b.dot(outward) else b

            new_hip = hip + lift
            knee2 = Vector(two_bone(tuple(hip), tuple(knee), tuple(ank), tuple(new_hip), turn_pole))
            du = (knee - hip).rotation_difference(knee2 - new_hip)
            mu2 = Matrix.Translation(new_hip) @ (du.to_matrix() @ mu.to_3x3()).to_4x4()
            dl = (du @ (ank - knee)).rotation_difference(ank - knee2)
            ml2 = Matrix.Translation(knee2) @ (dl.to_matrix() @ du.to_matrix() @ ml.to_3x3()).to_4x4()
            for name, m, par in ((u, mu2, parent), (lo, ml2, mu2), (ft, mf, ml2)):
                q = (rel(name).inverted() @ par.inverted() @ m).to_quaternion().normalized()
                if name in prev and q.dot(prev[name]) < 0.0:
                    q = -q
                prev[name] = q
                for i in range(4):
                    if (name, i) not in fcs:
                        raise ValueError(f"{act.name}: {name} has no rotation keys")
                    solved.setdefault((name, i), []).extend((float(f), q[i]))
    # the solved legs replace their channels whole, one linear key per frame (inserting beside the clip's own keys
    # left the frames between them unsolved: the feet rose with the hips on 3 frames of 4)
    for key, co in solved.items():
        fc = fcs[key]
        fc.keyframe_points.clear()
        fc.keyframe_points.add(len(co) // 2)
        fc.keyframe_points.foreach_set("co", co)
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
        fc.update()
    # A3: the feet measured on the re-evaluated rig (A2 read the solved geometry: 0.0 while the feet rose 10 cm)
    _assign(arm, act)
    miss = 0.0
    for f in range(f0, f1 + 1):
        bpy.context.scene.frame_set(f)
        for _, _, _, ft in legs:
            miss = max(miss, (pb[ft].matrix.translation - rec[f][ft].translation).length)
    arm.animation_data.action = None
    if miss * 100.0 > ANKLE_MISS_FAIL_CM:
        raise ValueError(f"{act.name}: a re-solved foot lands {miss * 100:.2f} cm from its place")
    return {"hips_up_cm": round(metres * 100, 2), "sway_cm": round(sway_m * 100, 2), "knees_in_deg": knees_in_deg,
            "frames": f1 - f0 + 1, "ankle_miss_max_cm": round(miss * 100, 3), "parents": sorted(parents)}


def _roll_keys(act, bone, axis_local, degs, f0):
    """Each rotation key of bone turned by degs[frame - f0] about axis_local (the bone's rest frame), on the left."""
    groups = [None] * 4
    for bag in _bags(act):
        for fc in bag.fcurves:
            if fc.data_path == f'pose.bones["{bone}"].rotation_quaternion':
                groups[fc.array_index] = fc
    if None in groups:
        raise ValueError(f"{act.name}: {bone} has no rotation keys")
    n = len(groups[0].keyframe_points)
    vals = []
    for fc in groups:
        buf = [0.0] * (2 * n)
        fc.keyframe_points.foreach_get("co", buf)
        vals.append(buf)
    for k in range(n):
        fr = min(max(int(round(vals[0][2 * k])) - f0, 0), len(degs) - 1)
        q = q_mul(axis_turn(tuple(axis_local), degs[fr]), tuple(vals[i][2 * k + 1] for i in range(4)))
        for i in range(4):
            vals[i][2 * k + 1] = q[i]
    for i, fc in enumerate(groups):
        fc.keyframe_points.foreach_set("co", vals[i])
        fc.update()


def floor(arm, skin, act, rest, up_arm, wrap: bool = False, reach: int = 2, check_only: bool = False,
          check_to=None) -> dict:
    """The `floor` edit on one action: samples the posed skin on every frame, lifts the Hips' location keys by
    lift_profile (wrap: a loop; reach 0: each frame its own need, keyed on every frame). check_only (A3, "ground"):
    no lift, the lowest point over the frames up to check_to (all without it) reported as lowest_after_cm."""
    import bpy
    import numpy as np
    from mathutils import Vector

    scene = bpy.context.scene
    f0, f1 = _assign(arm, act)

    def lowest_per_frame():
        out = []
        for f in range(f0, f1 + 1):
            scene.frame_set(f)
            dg = bpy.context.evaluated_depsgraph_get()
            ev = skin.evaluated_get(dg)
            me = ev.to_mesh()
            co = np.empty(len(me.vertices) * 3)
            me.vertices.foreach_get("co", co)
            co = co.reshape(-1, 3) @ np.array(ev.matrix_world.to_3x3()).T + np.array(ev.matrix_world.translation)
            out.append(float(co[:, 2].min()))
            ev.to_mesh_clear()
        return out

    before = lowest_per_frame()
    if check_only:
        arm.animation_data.action = None
        upto = before if check_to is None else before[:max(1, check_to - f0 + 1)]
        return {"check_only": True, "checked_frames": [f0, f0 + len(upto) - 1],
                "lowest_after_cm": round(min(upto) * 100, 2), "lowest_all_cm": round(min(before) * 100, 2)}
    lift = lift_profile(before, reach=reach, wrap=wrap)
    up_h = rest["Hips"].inverted() @ Vector(up_arm).normalized()
    _shift_hips(act, f0, f1, [up_h * x for x in lift], bake=reach == 0)
    after = lowest_per_frame()
    arm.animation_data.action = None
    return {"lowest_before_cm": round(min(before) * 100, 2), "lowest_after_cm": round(min(after) * 100, 2),
            "max_lift_cm": round(max(lift) * 100, 2), "highest_low_after_cm": round(max(after) * 100, 2),
            "wrap": wrap, "reach": reach}
