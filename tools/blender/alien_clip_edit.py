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
  that leaves the floor in place, Jump_Start): the frames up to the push-off (the cut's last kept crouch frame, every
  frame without a cut) lifted onto the floor by their own need, the lift faded out over `cut_gap` frames into the
  tuck, which is not lifted (the game lifts the body); those ground frames fail the build under -0.5 cm (A2's
  `false` hid its crouch 5.6 cm under the floor); `false`: neither lifted nor checked (an
  airborne loop, Jump_Air, which the game holds off the floor).
Only the clips listed under `[clips.*]` are edited, each with `[defaults]` under its own keys; an unlisted clip is
left exactly as the body carries it (A2: A1 gave every clip the defaults).
Pure maths (`cap_turn`, `axis_turn`, `q_rotate`, `lift_profile`, `cut_frames`, `two_bone`; B1b: `ground_clips`,
`foot_raise`, `raise_knee`) has no bpy and is unit-tested (tools/tests/test_alien_clip_edit.py).
"""
from __future__ import annotations

import math
import tomllib
from pathlib import Path

from alien_contact import can_fly

FINGERS = ("Index", "Middle", "Ring", "Little")
SEGMENTS = ("Proximal", "Intermediate", "Distal")
THUMB = ("ThumbProximal", "ThumbDistal")
KEYS = ("finger_cap_deg", "thumb_cap_deg", "abduct_deg", "swing_deg", "head_up_deg", "lean_deg", "cut_straight_deg",
        "cut_gap", "hips_up_cm", "knees_in_deg", "floor", "floor_reach", "floor_feet", "chest_up_deg", "repeat",
        "sway_cm", "sway_counter_deg", "leg_fit_bob", "cross_out_cm")
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
    pre = [(k, i) for i, k in enumerate(keys) if k < f0 - 1e-6]  # A3d: keys before the cycle stay, once
    body = [(k, i) for i, k in enumerate(keys) if f0 - 1e-6 <= k < f1 - 1e-6]
    end = [(k, i) for i, k in enumerate(keys) if k >= f1 - 1e-6]
    out = pre + [(k + r * period, i) for r in range(max(1, times)) for k, i in body]
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


FLOAT_TOL_M = 0.005  # B1 (the Walk hop): a frame whose lowest point is this far over the floor floats


def floated_frames(before: list[float], after: list[float], tol: float = FLOAT_TOL_M) -> list[int]:
    """B1 (art #196, the Walk hop): the frames the floor lift floated, each frame's lowest point (m) before and after
    the lift: on or under the floor within tol before (a foot planted or sunk), more than tol over it after. A frame
    already off the floor before (a run's real flight) is not counted. floor_reach 2 floated the Walk's planted frames
    up to 21 mm (18 of 32); reach 0 lifts each frame by exactly its own need, so it floats none."""
    return [i for i, (b, a) in enumerate(zip(before, after)) if b <= tol and a > tol]


def lowest_of(per_mesh: list[list[float]]) -> list[float]:
    """B1: per frame the lowest of several meshes' lowest points (the body and the sneakers: the soles reach 5 to 6.5
    mm under the bare foot at heel strike and toe-off)."""
    return [min(col) for col in zip(*per_mesh)]


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
        if mode is True and cfg.get("floor_feet"):  # B1b: at the foot, the Hips untouched (feet_floor)
            rep["floor"] = feet_floor(arm, skin, act, rest, up_arm, wrap=clip.endswith("_Loop"),
                                      no_flight=not can_fly(clip))
            if rep["floor"]["lowest_after_cm"] < FLOOR_FAIL_CM:  # B1i (the review's minor 2): A2's rule kept
                raise ValueError(f"{act.name}: still {rep['floor']['lowest_after_cm']} cm under the floor at the foot")
        elif mode is True:
            rep["floor"] = floor(arm, skin, act, rest, up_arm, wrap=clip.endswith("_Loop"),
                                 reach=int(cfg.get("floor_reach", 2)))
            if rep["floor"]["lowest_after_cm"] < FLOOR_FAIL_CM:
                raise ValueError(f"{act.name}: still {rep['floor']['lowest_after_cm']} cm under the floor after the lift")
        elif mode == "ground":  # A3: the crouch before the push-off on the floor and checked, the tuck not lifted
            last = rep.get("cut", {}).get("frames_dropped", [None])[0]
            rep["floor"] = floor(arm, skin, act, rest, up_arm, check_only=True,
                                 check_to=None if last is None else last - 1, fade=int(cfg.get("cut_gap", 3)))
            if rep["floor"]["lowest_after_cm"] < FLOOR_FAIL_CM:
                raise ValueError(f"{act.name}: its ground frames are {rep['floor']['lowest_after_cm']} cm under the floor")
        elif mode not in (False, None):
            raise ValueError(f"{act.name}: floor must be true, false or \"ground\", not {mode!r}")
        report[clip] = rep
    return report


SOLE_UNDER_M = 0.002  # B1b: the target: no sole more than this under the floor after the feet pass
SOLE_BAND_M = 0.25  # B1b: only skin points this close to the floor count for a foot's sole


def ground_clips(names: list[str], path: str) -> list[str]:
    """B1b (art #196): the clips the soles' floor covers: every clip the game plays on the ground. A clip the
    settings list counts when its floor is true; a clip they do not list counts too (the loco set's derived actions:
    Jog_Fwd_Left, Jog_Bwd*, the strafes, the __p2 / __arm* / __w03 / __ual variants, which B1 left 5 to 19 mm under
    the floor). Not floor false (Jump_Air: held off the floor) nor "ground" (Jump_Start: its tuck leaves the floor)."""
    with open(path, "rb") as f:
        listed = tomllib.load(f).get("clips", {})
    return [n for n in names if n not in listed or settings(path, n).get("floor", False) is True]


def foot_raise(lowest: list[float]) -> list[float]:
    """B1b: per frame the raise (m) of one foot that puts its sole on the floor: its own need, max(0, -lowest). A
    frame on or over the floor is not touched, so the other foot (the trailing toe at heel strike) stays down and
    the Hips do not move: B1's Hips lift by the sole's need jerked them 18.6 mm in a frame at heel strike."""
    return [max(0.0, -z) for z in lowest]


PLANT_TOL_M = 0.0005  # B1e: a no-flight frame's lower foot this high or less is left as it is
PLANT_SLIDE_M = 0.002  # B1i: a planted foot moving this far a frame off the ground's travel slides (a skid)
PLANT_PATCH_M = 0.003  # B1i: a foot's contact patch: its points this close over its lowest
PLANT_ON_M = 0.0015  # B1k: a sole this close over the floor stands on it (the planted frames' bar)
PLANT_EASE = 2  # B1k: the frames a foot's plant eases in over before its landing and out over after its lift-off
PLANT_HOLD_MAX_M = 0.15  # B1k: a stance run needing a longer hold is the clip's own slide, lowered but not held
PLANT_EASE_STEP_M = 0.010  # B1l: a hold eases out over the swing by at most this a frame beyond the source's own step


def patch_steps(frames_xy: list, patch: list, wrap: bool = False) -> list[tuple[float, float] | None]:
    """B1k (art #196): per frame j a foot's horizontal step (m, x and y) from frame j-1, on its contact patch's own
    points: the points of patch[j-1] and those of patch[j] (indices into every frame's points frames_xy[f], the skins'
    (x, y)) each followed from j-1 to j, the two means averaged. A rolling foot's points at its contact move up, not
    along (B1j: the patch's centre slid along the toe as the foot rolled). None where neither frame has a patch and at
    frame 0 of a clip that does not wrap; wrap: a loop whose last frame repeats its first, frame 0's step is the last
    frame's."""
    n = len(frames_xy)
    out = [None] * n
    for j in range(1, n):
        a, b = frames_xy[j - 1], frames_xy[j]
        means = [(sum(b[k][0] - a[k][0] for k in p) / len(p), sum(b[k][1] - a[k][1] for k in p) / len(p))
                 for p in (patch[j - 1], patch[j]) if p]
        if means:
            out[j] = (sum(x for x, _ in means) / len(means), sum(y for _, y in means) / len(means))
    if wrap and n > 2:
        out[0] = out[-1]
    return out


def ground_step(lows: dict[str, list[float]], steps: dict[str, list]) -> tuple[float, float]:
    """B1k: the ground's travel a frame (m, x and y): per component the median step of the lower foot (in a clip with
    no flight a foot stands on most frames, and the clips play in place, so a standing foot travels back at the
    ground speed); (0, 0) without a step."""
    vs = [steps["Left" if a <= b else "Right"][i] for i, (a, b) in enumerate(zip(lows["Left"], lows["Right"]))]
    vs = [v for v in vs if v is not None]
    if not vs:
        return 0.0, 0.0

    def med(a):
        a = sorted(a)
        h = len(a) // 2
        return a[h] if len(a) % 2 else 0.5 * (a[h - 1] + a[h])
    return med([v[0] for v in vs]), med([v[1] for v in vs])


def foot_stances(lows: dict[str, list[float]], wrap: bool = False) -> dict[str, list[list[int]]]:
    """B1k: per foot its stance runs (frame index lists, _runs): the frames it is the lower foot (both on a tie) or
    its sole within PLANT_ON_M of the floor. In a clip with no flight one foot stands on every frame; the crouch's
    lower foot hovers 9-19 mm through its stance and is still the lower one while it lifts off, until the other
    lands."""
    n = len(lows["Left"])
    out = {}
    for s, o in (("Left", "Right"), ("Right", "Left")):
        out[s] = _runs([lows[s][i] <= lows[o][i] or lows[s][i] <= PLANT_ON_M for i in range(n)], wrap)
    return out


def merge_runs(runs: list[list[int]], n: int, wrap: bool = False, gap: int = 2 * PLANT_EASE) -> list[list[int]]:
    """B1l (the review's minor 2): one foot's stance runs (foot_stances) with the gaps of `gap` frames or fewer between
    two of its runs filled in, so a 1-frame gap carries the hold across instead of dropping it to 0 and back (a 90 mm
    pop in one frame). wrap: a loop of n frames whose last is the first, a gap over the seam joined too."""
    m = n - 1 if wrap and n > 2 else n
    flags = [False] * m
    for run in runs:
        for i in run:
            flags[i] = True
    order = sorted(runs, key=lambda r: r[0])
    pairs = list(zip(order, order[1:]))
    if wrap and order:
        pairs.append((order[-1], order[0]))
    for a, b in pairs:
        k = (b[0] - a[-1] - 1) % m if wrap else b[0] - a[-1] - 1
        if 0 < k <= gap:
            for d in range(1, k + 1):
                flags[(a[-1] + d) % m] = True
    return _runs(flags + ([flags[0]] if wrap and n > 2 else []), wrap)


def ease_weights(hold: float, room: int, ease: int = PLANT_EASE, step: float = PLANT_EASE_STEP_M) -> list[float]:
    """B1l (the review's major 1): the weights w[0..k] (w[0] = 1, the run's end; d = 1..k the frames past it) that ease
    a hold of `hold` m out: a raised cosine over k frames, k the fewest from `ease` on whose largest step is `step` or
    less, never past `room` (the frames to the foot's next landing). Where room is too short for that, a straight ramp
    over room frames (the smallest largest step: hold / (room + 1)). B1k eased every hold over 2 frames: his 108 mm
    hold caught up 27, 54 and 27 mm a frame just after the lift-off, a few mm over the floor, unseen by plant_slides."""
    def cos_w(k):
        return [0.5 * (1.0 + math.cos(math.pi * d / (k + 1))) for d in range(k + 1)]

    def top(w):
        return hold * max(abs(a - b) for a, b in zip(w, w[1:] + [0.0]))
    k = min(ease, room)
    while k < room and top(cos_w(k)) > step:
        k += 1
    w = cos_w(k)
    if top(w) > step and k > 0:
        w = [1.0 - d / (k + 1) for d in range(k + 1)]
    return w


def plant_ease_step(off: dict[str, list], runs: dict[str, list[list[int]]]) -> float:
    """B1l: the largest step (m a frame, x and y) an offset (plant_offsets') adds to a foot beyond the source's own on
    the steps touching a frame outside its stance runs (merge_runs'): the eased swing frames."""
    top = 0.0
    for s, o in off.items():
        n = len(o)
        inr = [False] * n
        for run in runs[s]:
            for i in run:
                inr[i] = True
        for j in range(1, n):
            if not (inr[j] and inr[j - 1]):
                top = max(top, math.hypot(o[j][0] - o[j - 1][0], o[j][1] - o[j - 1][1]))
    return top


def plant_offsets(lows: dict[str, list[float]], steps: dict[str, list], ground: tuple[float, float],
                  no_flight: bool, wrap: bool = False, ease: int = PLANT_EASE, unheld: dict | None = None
                  ) -> tuple[dict[str, list[tuple[float, float, float]]], dict[str, list[int]]]:
    """B1k (art #196, the crouch's lift-off slide): per foot and frame its world offset (m: x, y, z) and per foot the
    frames it lowers. A foot under the floor is raised by its own need (foot_raise) on every frame. In a clip with no
    flight (alien_contact.can_fly false) each foot is planted on its own through each stance run (foot_stances) that
    has a frame hovering over PLANT_TOL_M: its sole put on the floor (z, its own height) on the run's frames, and on
    each step of the run that touches a lowered frame its own drift off the ground's travel (patch_steps less
    ground_step) taken back, so it stands still on the floor through its lift-off until the other foot is down; the
    hold starts at the run's first frame, so the foot lands where the clip puts it (a run around a whole loop closes
    on itself). The offset
    eases in over `ease` frames before the run (the landing) and out over `ease` after it (the lift-off) by a raised
    cosine, never under the floor; B1l: the hold (x, y) eases out over as many frames as keep its step within
    PLANT_EASE_STEP_M (ease_weights, never past the next landing), and a foot's runs `2 * ease` frames apart or less are
    one (merge_runs). A run whose hold would pass PLANT_HOLD_MAX_M is lowered without a hold and its
    first frame added to unheld[foot] (a dict given): that is the clip's own slide, not a lift-off's drag (the
    Crouch_Fwd__ual slides 13 cm a frame on his floor; holding it put her Foot 17 cm out of reach). B1e lowered both
    feet by the lower foot's height instead: the lowered foot dragged 37-53 mm a frame along the floor at the crouch's
    lift-off. A frame in no lowered run keeps its height and place."""
    n = len(lows["Left"])
    m = n - 1 if wrap and n > 2 else n
    raw = foot_stances(lows, wrap) if no_flight else {"Left": [], "Right": []}
    runs = {s: merge_runs(raw[s], n, wrap, 2 * ease) for s in raw}
    out, lowered = {}, {}
    unheld = unheld if unheld is not None else {}
    unheld.setdefault("Left", [])
    unheld.setdefault("Right", [])
    for s in ("Left", "Right"):
        z = lows[s]
        off = [[0.0, 0.0, max(0.0, -h)] for h in z]
        in_run = [False] * n
        for run in runs[s]:
            for i in run:
                in_run[i] = True
        stood = {i for run in raw[s] for i in run}  # a merged gap's frames keep their height (merge_runs)
        eased = [[0.0, 0.0, 0.0] for _ in range(n)]
        low_s = []
        for run in runs[s]:
            low_r = {i for i in run if i in stood and PLANT_TOL_M < z[i] < SOLE_BAND_M}
            if not low_r:
                continue
            low_s += sorted(low_r)
            hold = [(0.0, 0.0)]
            pairs = list(zip(run, run[1:]))
            whole = wrap and len(run) == m
            if whole:
                pairs.append((run[-1], run[0]))
            for a, b in pairs:
                st = steps[s][b]
                d = (st[0] - ground[0], st[1] - ground[1]) if st is not None and (a in low_r or b in low_r) else (0, 0)
                hold.append((hold[-1][0] - d[0], hold[-1][1] - d[1]))
            if whole:  # around the loop: the drift left at the seam spread evenly
                res = hold.pop()
                hold = [(h[0] - res[0] * t / m, h[1] - res[1] * t / m) for t, h in enumerate(hold)]
            if max(math.hypot(*h) for h in hold) > PLANT_HOLD_MAX_M:
                hold = [(0.0, 0.0)] * len(run)
                unheld[s].append(run[0])
            for i, h in zip(run, hold):
                off[i] = [h[0], h[1], -z[i] if (i in low_r or z[i] < 0.0) else 0.0]
            if whole:
                continue
            for end, sign in ((run[0], -1), (run[-1], 1)):
                room = 0  # the frames to the foot's next landing (or back to its last lift-off)
                while room < m:
                    j = (end + sign * (room + 1)) % m if wrap and n > 2 else end + sign * (room + 1)
                    if not 0 <= j < n or in_run[j]:
                        break
                    room += 1
                wxy = ease_weights(math.hypot(off[end][0], off[end][1]), room, ease)
                wz = ease_weights(0.0, room, ease)
                for d in range(1, max(len(wxy), len(wz))):
                    j = (end + sign * d) % m if wrap and n > 2 else end + sign * d
                    a = wxy[d] if d < len(wxy) else 0.0
                    b = wz[d] if d < len(wz) else 0.0
                    eased[j] = [eased[j][0] + a * off[end][0], eased[j][1] + a * off[end][1],
                                eased[j][2] + b * off[end][2]]
        for j in range(n):
            if not in_run[j] and any(eased[j]):
                off[j] = [eased[j][0], eased[j][1], max(eased[j][2], -z[j])]
        if wrap and n > 2:
            off[-1] = list(off[0])
        out[s] = [tuple(o) for o in off]
        lowered[s] = low_s
    return out, lowered


def plant_slides(lows: dict[str, list[float]], steps: dict[str, list], ground: tuple[float, float],
                 lowered: dict[str, list[int]] | None = None, on: float = PLANT_ON_M) -> dict[int, float]:
    """B1k: per frame j the largest slide (m a frame, off the ground's travel) of a foot standing on the floor (within
    on) at both j-1 and j; lowered given, only of a foot the plant lowered at j-1 or j (the plant's own frames)."""
    out = {}
    for s in ("Left", "Right"):
        z, low = lows[s], set(lowered[s]) if lowered is not None else None
        for j in range(1, len(z)):
            st = steps[s][j]
            if st is None or z[j - 1] > on or z[j] > on or (low is not None and not ({j - 1, j} & low)):
                continue
            out[j] = max(out.get(j, 0.0), math.hypot(st[0] - ground[0], st[1] - ground[1]))
    return out


def raise_knee(hip, knee, ankle, lift):
    """B1b: the knee for the ankle moved by the vector lift with the hip kept (plain tuples): two_bone in a frame
    moved by -lift, so the thigh and shin keep their lengths and the knee stays in the leg's own plane. An ankle out
    of reach lands short (two_bone's 0.9995 of the leg); the pass measures where it landed."""
    moved_hip = tuple(h - d for h, d in zip(hip, lift))
    k = two_bone(tuple(hip), tuple(knee), tuple(ankle), moved_hip)
    return tuple(x + d for x, d in zip(k, lift))


CROSS_GRID_M = (0.004, 0.001, 0.000125)  # B1g: the grid steps the shoes' overlap is searched at, coarse to fine
CROSS_TOUCH_M = 1e-5  # B1g: an overlap this small or less is none (a shoe resting against the other)


def hull_slab(planes, a: float, b: float):
    """B1g (art #196, the crossing shoes): a convex hull's extent along its depth axis u at (a, b) of the two other
    axes: planes are (nu, na, nb, d), the hull being nu*u + na*a + nb*b <= d. Returns (lo, hi), or None where the line
    misses the hull."""
    lo, hi = -math.inf, math.inf
    for nu, na, nb, d in planes:
        r = d - na * a - nb * b
        if abs(nu) < 1e-9:
            if r < -1e-9:
                return None
        elif nu > 0.0:
            hi = min(hi, r / nu)
        else:
            lo = max(lo, r / nu)
    return (lo, hi) if lo <= hi else None


def hull_gaps(swing, planted):
    """B1g: the gap function cross_depth searches, in plain Python (hull_slab): per (a, b) point (out, inn), out the
    planted hull's far side less the swinging hull's near side (how far the swinging shoe must move along +u to clear
    the planted one there), inn the reverse (along -u); None where either hull is missed."""
    def gaps(pts):
        out = []
        for a, b in pts:
            s, p = hull_slab(swing, a, b), hull_slab(planted, a, b)
            out.append(None if s is None or p is None else (p[1] - s[0], s[1] - p[0]))
        return out
    return gaps


def _grid(a0, a1, b0, b1, step):
    na = max(2, int(math.ceil((a1 - a0) / step)) + 1)
    nb = max(2, int(math.ceil((b1 - b0) / step)) + 1)
    return [(a0 + (a1 - a0) * i / (na - 1), b0 + (b1 - b0) * j / (nb - 1)) for i in range(na) for j in range(nb)]


def cross_depth(gaps, box, steps=CROSS_GRID_M, keep: int = 4):
    """B1g: two convex shoes' overlap along the depth axis u, the largest of gaps' (out, inn) over the two hulls' shared
    (a, b) box (a0, a1, b0, b1): a grid at steps[0], then around the best `keep` points a grid at each finer step
    (out and inn are concave over the shared projection, so the search converges on the one top). For convex hulls
    the swinging shoe overlaps the planted one, moved by t along u, for t in [-inn, out]: they overlap now when
    out > 0 and inn > 0, and out is the push along +u that clears them (inn along -u). Returns (out, inn) in m, or
    None when the projections share no point."""
    a0, a1, b0, b1 = box
    if a1 < a0 or b1 < b0:
        return None
    best = []
    pts = _grid(a0, a1, b0, b1, steps[0])
    vals = gaps(pts)
    for k in (0, 1):
        cand = sorted(((v[k], p) for p, v in zip(pts, vals) if v is not None), reverse=True)[:keep]
        if not cand:
            return None
        prev = steps[0]
        for st in steps[1:]:
            nxt = []
            for _, (a, b) in cand:
                q = _grid(max(a0, a - prev), min(a1, a + prev), max(b0, b - prev), min(b1, b + prev), st)
                nxt += [(v[k], p) for p, v in zip(q, gaps(q)) if v is not None]
            cand = sorted(cand + nxt, reverse=True)[:keep]
            prev = st
        best.append(cand[0][0])
    return best[0], best[1]


def cross_need(depth, clear: float) -> float:
    """B1g: the push (m) a frame's measured depth (cross_depth's (out, inn), or None) asks for along +u: the overlap
    out plus clear when the shoes really overlap (out and inn over CROSS_TOUCH_M) and +u is the short way out
    (out <= inn); 0 otherwise. B1f's 1 cm cells counted shoes within the clearance as meeting: the crouches and the
    back jogs got 1 to 1.7 cm pushes with no overlap at all."""
    if depth is None:
        return 0.0
    out, inn = depth
    if out > CROSS_TOUCH_M and inn > CROSS_TOUCH_M and out <= inn:
        return out + clear
    return 0.0


def cross_overlap(depth) -> float:
    """B1g: the overlap (m) along the side axis: the shorter way out, min(out, inn), when both are over
    CROSS_TOUCH_M; else 0."""
    if depth is None or min(depth) <= CROSS_TOUCH_M:
        return 0.0
    return min(depth)


def cross_bump(need: list[float], reach: int = 2, wrap: bool = False) -> list[float]:
    """B1f: per frame the outward push (m): each frame's need spread over +-reach frames by a raised cosine (1 at the
    frame, 0.75 and 0.25 one and two frames away at reach 2), the largest taken, so no frame gets less than its need
    and the push eases in and out over reach frames on each side of the overlap. wrap: a loop whose last frame repeats
    its first; the bump runs around the seam."""
    n = len(need)
    w = [0.5 * (1.0 + math.cos(math.pi * d / (reach + 1))) for d in range(reach + 1)]
    if wrap and n > 2:
        m = n - 1
        cyc = need[:m]
        cyc[0] = max(cyc[0], need[-1])
        out = [max(cyc[(i + d) % m] * w[abs(d)] for d in range(-reach, reach + 1)) for i in range(m)]
        return out + [out[0]]
    return [max(need[j] * w[abs(j - i)] for j in range(max(0, i - reach), min(n, i + reach + 1))) for i in range(n)]


CROSS_MAX_M = 0.04  # B1f: no frame's need counts over this; B1g: a frame needing more is a crossed-over step


def _runs(flags: list[bool], wrap: bool) -> list[list[int]]:
    """B1f: the runs of True frames (index lists); wrap: a loop whose last frame is the first, a run joined over
    the seam."""
    n = len(flags)
    m = n - 1 if wrap and n > 2 else n
    runs, cur = [], []
    for i in range(m):
        if flags[i]:
            cur.append(i)
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    if wrap and len(runs) > 1 and runs[0][0] == 0 and runs[-1][-1] == m - 1:
        runs[0] = runs.pop() + runs[0]
    return runs


def cross_pushes(lows: dict[str, list[float]], need: list[float], reach: int = 2, wrap: bool = False,
                 plant: float = FLOAT_TOL_M) -> dict[str, list[float]]:
    """B1f, B1g: per foot the outward push (m) per frame from each frame's need (cross_need: the overlap plus the
    clearance, 0 on a frame without an overlap), at most CROSS_MAX_M. A frame's need goes to the higher foot; B1g:
    when both feet stand (each lowest within plant) each takes half (his Jog_Bwd: both soles at 0.0, neither pushed,
    0.9 mm left). Then cross_bump, and a foot on the floor never slides: over each of its stance runs the push is held
    at the run's largest, and the swing frames around it ease from it (the raised cosine), so a foot that lands into
    the other shoe lands that much wider and stays there. A clip without an overlap gets exactly 0."""
    n = len(lows["Left"])
    w = [0.5 * (1.0 + math.cos(math.pi * d / (reach + 1))) for d in range(reach + 1)]
    m = n - 1 if wrap and n > 2 else n
    share = {"Left": [0.0] * n, "Right": [0.0] * n}
    for i, nd in enumerate(need):
        if nd <= 0.0:
            continue
        nd = min(nd, CROSS_MAX_M)
        lo, ro = lows["Left"][i], lows["Right"][i]
        if lo <= plant and ro <= plant:
            share["Left"][i] = share["Right"][i] = 0.5 * nd
        else:
            share["Left" if lo > ro else "Right"][i] = nd
    out = {}
    for s in ("Left", "Right"):
        p = cross_bump(share[s], reach, wrap)
        for run in _runs([z <= plant for z in lows[s]], wrap):
            hold = max(p[i] for i in run)
            for i in run:
                p[i] = hold
            for d in range(1, reach + 1):  # the ease out of the stance on both sides
                for j in ((run[0] - d) % m if wrap else run[0] - d, (run[-1] + d) % m if wrap else run[-1] + d):
                    if 0 <= j < n and lows[s][j] > plant:
                        p[j] = max(p[j], hold * w[d])
        if wrap and n > 2:
            p[-1] = p[0]
        out[s] = p
    return out


def cross_lifts(lows: dict[str, list[float]], lift: list[float], reach: int = 2, wrap: bool = False,
                plant: float = FLOAT_TOL_M) -> dict[str, list[float]]:
    """B1g (the crossed-over step, Strafe_Left__s4b): per foot the lift (m) per frame from each crossed frame's lift
    (the vertical overlap plus the clearance): the higher foot only, when it is off the floor (over plant), eased by
    cross_bump and never on a frame that foot stands on; such a step crosses on purpose, so it is not pushed apart.
    A lift over CROSS_MAX_M is not made: Strafe_Left__s4b's hop has the feet in an X at one height on one frame (10
    to 12 cm to lift), the clip's own crossing, left as it is."""
    n = len(lows["Left"])
    share = {"Left": [0.0] * n, "Right": [0.0] * n}
    for i, lf in enumerate(lift):
        s = "Left" if lows["Left"][i] > lows["Right"][i] else "Right"
        if 0.0 < lf <= CROSS_MAX_M and lows[s][i] > plant:
            share[s][i] = lf
    out = {}
    for s in ("Left", "Right"):
        p = cross_bump(share[s], reach, wrap)
        out[s] = [0.0 if z <= plant else x for x, z in zip(p, lows[s])]
        if wrap and n > 2:
            out[s][-1] = out[s][0]
    return out


CROSS_SLIDE_FAIL_MM = 1.0  # B1i: a cross push sliding a planted foot this far (mm) over a stance fails the clip


def cross_slide_mm(lows: dict[str, list[float]], push: dict[str, list[float]], wrap: bool = False,
                   plant: float = FLOAT_TOL_M) -> dict[str, float]:
    """B1g: per foot how far the push slides it while it stands (mm): over each stance run the push's range."""
    out = {}
    for s in ("Left", "Right"):
        r = [max(push[s][i] for i in run) - min(push[s][i] for i in run)
             for run in _runs([z <= plant for z in lows[s]], wrap)]
        out[s] = round(max(r, default=0.0) * 1000, 2)
    return out


def _side_axes(arm):
    """B1f: the world side axis (the right hip to the left, horizontal) and the forward axis (up x side)."""
    from mathutils import Vector
    b = arm.data.bones
    side = arm.matrix_world.to_3x3() @ (b["LeftUpperLeg"].head_local - b["RightUpperLeg"].head_local)
    side = Vector((side.x, side.y, 0.0)).normalized()
    return side, Vector((0.0, 0.0, 1.0)).cross(side)


def _shoe_split(arm, p):
    """B1f: world points p (numpy n x 3) split by foot: each to the foot whose Foot-to-Toes segment is nearer."""
    import numpy as np
    pb, mw = arm.pose.bones, arm.matrix_world
    dist = []
    for s in ("Left", "Right"):
        a = np.array(mw @ pb[f"{s}Foot"].head)
        b = np.array(mw @ pb[f"{s}Toes"].tail)
        ab = b - a
        t = np.clip(((p - a) @ ab) / max(1e-12, float(ab @ ab)), 0.0, 1.0)
        dist.append(np.linalg.norm(p - (a + t[:, None] * ab), axis=1))
    left = dist[0] <= dist[1]
    return {"Left": p[left], "Right": p[~left]}


def _hull_planes(p):
    """B1g: the convex hull of world points p (numpy n x 3; bmesh's convex_hull) as planes (F x 4: the outward unit
    normal, d), the hull being n.x <= d; d is the points' support along n, as bmesh's sliver faces put up to 26 mm of
    the shoe outside their own plane."""
    import bmesh
    import numpy as np
    bm = bmesh.new()
    for v in p.tolist():
        bm.verts.new(v)
    geom = bmesh.ops.convex_hull(bm, input=list(bm.verts))["geom"]
    c = p.mean(axis=0)
    ns = set()
    for f in geom:
        if not isinstance(f, bmesh.types.BMFace):
            continue
        f.normal_update()
        n = np.array(f.normal)
        if n @ n < 0.5:
            continue
        if n @ (np.array(f.verts[0].co) - c) < 0.0:
            n = -n
        ns.add(tuple(round(float(x), 9) for x in n))
    bm.free()
    n = np.array(sorted(ns))
    return np.column_stack([n, (p @ n.T).max(axis=0)])  # each plane through the points' support: no point outside


def _np_gaps(swing, planted):
    """B1g: hull_gaps with numpy (Blender), the same maths on many points at once; planes (F x 4) in the depth
    frame (nu, na, nb, d)."""
    import numpy as np

    def slabs(P, A, B):
        nu = P[:, 0]
        r = P[None, :, 3] - P[None, :, 1] * A[:, None] - P[None, :, 2] * B[:, None]
        pos, neg = nu > 1e-9, nu < -1e-9
        zer = ~(pos | neg)
        hi = (r[:, pos] / nu[pos]).min(axis=1) if pos.any() else np.full(len(A), np.inf)
        lo = (r[:, neg] / nu[neg]).max(axis=1) if neg.any() else np.full(len(A), -np.inf)
        ok = lo <= hi
        if zer.any():
            ok &= (r[:, zer] >= -1e-9).all(axis=1)
        return lo, hi, ok

    def gaps(pts):
        out = []
        for k in range(0, len(pts), 1500):
            q = np.array(pts[k:k + 1500])
            sl, sh, so = slabs(swing, q[:, 0], q[:, 1])
            pl, ph, po = slabs(planted, q[:, 0], q[:, 1])
            ok = so & po
            out += [(float(a), float(b)) if g else None for a, b, g in zip(ph - sl, sh - pl, ok)]
        return out
    return gaps


def _depth(hs, hp, vs, vp, axes):
    """B1g: cross_depth of the swinging hull hs over the planted hp (world planes) along axes[0], searched over
    axes[1] x axes[2] where both shoes' points (vs, vp) project. Returns the depth and the two hulls' planes in the
    depth frame."""
    import numpy as np
    E = np.array(axes)
    sw = np.column_stack([hs[:, :3] @ E.T, hs[:, 3]])
    pl = np.column_stack([hp[:, :3] @ E.T, hp[:, 3]])
    qs, qp = vs @ E[1:].T, vp @ E[1:].T
    lo, hi = np.maximum(qs.min(axis=0), qp.min(axis=0)), np.minimum(qs.max(axis=0), qp.max(axis=0))
    return cross_depth(_np_gaps(sw, pl), (lo[0], hi[0], lo[1], hi[1])), (sw, pl)


def _shoe_sides(shoes):
    """B1g: per vertex of the shoes mesh whether it is the left shoe's (its weights to the Left* bones over the
    Right* ones), or None without such groups. The nearer Foot-Toes segment (_shoe_split) gave 29 of the right
    shoe's heel collar points to the left foot in her Crouch_Fwd: a 0.8 mm overlap with the feet 17 cm apart."""
    import numpy as np
    gn = {g.index: g.name for g in shoes.vertex_groups}
    if not any(n.startswith("Left") for n in gn.values()) or not any(n.startswith("Right") for n in gn.values()):
        return None
    lr = [sum(e.weight * (1.0 if gn[e.group].startswith("Left") else -1.0 if gn[e.group].startswith("Right") else 0.0)
              for e in v.groups if e.group in gn) for v in shoes.data.vertices]
    return np.array(lr) > 0.0


def cross_measure(arm, shoes, act, clear: float) -> dict:
    """B1f, B1g: per frame each foot's lowest shoe point and the shoes' overlap from their convex hulls (the shoes
    mesh's evaluated points, each to its foot by its weights, _shoe_sides): along the body's side axis, cross_depth with the left shoe as
    the swinging one (the relative motion is the same for either), `need` the push apart (cross_need: the overlap
    plus clear, 0 without one), `overlap` (cross_overlap). A frame whose overlap is a crossed-over step (the shorter
    way out is across, the shoes' centres on the wrong sides, or a push over CROSS_MAX_M: Strafe_Left__s4b's hop, the
    feet in an X, 15 cm either way) is `crossed`, not pushed, and `lift` is the higher shoe's vertical overlap over
    the other plus clear.
    Frames whose shoes' boxes do not meet are not searched (0)."""
    import bpy
    import numpy as np

    f0, f1 = _assign(arm, act)
    side, fwd = _side_axes(arm)
    sd, fw, up = np.array(side), np.array(fwd), np.array((0.0, 0.0, 1.0))
    lows = {"Left": [], "Right": []}
    need, lift, overlap, crossed = [], [], [], []
    checked = False
    sides = _shoe_sides(shoes)
    for f in range(f0, f1 + 1):
        bpy.context.scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        ev = shoes.evaluated_get(dg)
        me = ev.to_mesh()
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3) @ np.array(ev.matrix_world.to_3x3()).T + np.array(ev.matrix_world.translation)
        ev.to_mesh_clear()
        feet = ({"Left": co[sides], "Right": co[~sides]} if sides is not None and len(sides) == len(co)
                else _shoe_split(arm, co))
        for s in ("Left", "Right"):
            lows[s].append(float(feet[s][:, 2].min()) if len(feet[s]) else 1.0)
        nd = lf = ov = 0.0
        cr = False
        L, R = feet["Left"], feet["Right"]
        if len(L) > 3 and len(R) > 3:
            box = [np.stack([q @ sd, q @ fw, q[:, 2]], axis=1) for q in (L, R)]
            if (box[0].min(axis=0) < box[1].max(axis=0)).all() and (box[1].min(axis=0) < box[0].max(axis=0)).all():
                hl, hr = _hull_planes(L), _hull_planes(R)
                d, (sw, pl) = _depth(hl, hr, L, R, (sd, fw, up))
                if not checked and d is not None:  # the numpy search against the plain maths, once a clip
                    q = (L @ np.array((fw, up)).T)[:: max(1, len(L) // 7)].tolist()
                    a, b = _np_gaps(sw, pl)(q), hull_gaps(sw.tolist(), pl.tolist())(q)
                    if any((x is None) != (y is None) or (x and max(abs(x[0] - y[0]), abs(x[1] - y[1])) > 1e-7)
                           for x, y in zip(a, b)):
                        raise ValueError(f"{act.name}: the hull gaps differ between numpy and plain Python")
                    checked = True
                nd, ov = cross_need(d, clear), cross_overlap(d)
                swapped = float((L @ sd).mean()) < float((R @ sd).mean())
                if ov > 0.0 and (nd == 0.0 or nd - clear > CROSS_MAX_M or swapped):
                    cr, nd = True, 0.0  # crossed over: the higher shoe lifted over the other instead
                    hi_left = lows["Left"][-1] > lows["Right"][-1]
                    hs, hp, vs, vp = (hl, hr, L, R) if hi_left else (hr, hl, R, L)
                    du, _ = _depth(hs, hp, vs, vp, (up, sd, fw))
                    lf = du[0] + clear if du is not None and du[0] > CROSS_TOUCH_M else 0.0
        need.append(nd)
        lift.append(lf)
        overlap.append(ov)
        crossed.append(cr)
    arm.animation_data.action = None
    return {"lows": lows, "need": need, "lift": lift, "overlap": overlap, "crossed": crossed, "side": tuple(side)}


def feet_cross(arm, shoes, act, clear: float, wrap: bool) -> dict:
    """B1f, B1g (art #196, the crossing shoes): where the shoes really overlap (cross_measure's convex hulls), they
    move apart along the body's side axis by the overlap plus clear (cross_pushes: the higher foot, or half each when
    both stand; held over a stance, eased by a raised cosine), a crossed-over step's higher foot lifted over the
    other instead (cross_lifts); the legs solved again by _raise_ankles (the Foot's world rotation kept, the knee in
    its own plane), the Hips untouched; three times at most. A clip with no overlap is not touched (asserted).
    B1i: the clearance goes into the first pass only (a later pass asks for the overlap still left); a push sliding a
    planted foot over CROSS_SLIDE_FAIL_MM (each pass's push over its own stance runs, and the summed push over the
    final ones: `slide_max_mm`) or a Foot missing its place over ANKLE_MISS_FAIL_CM fails the clip.
    Returns the overlap per frame before and after (mm), the push, the lift and the planted feet's slide."""
    m0 = m = cross_measure(arm, shoes, act, clear)
    side = m["side"]
    n = len(m["need"])
    pushed = {s: [0.0] * n for s in ("Left", "Right")}
    lifted = {s: [0.0] * n for s in ("Left", "Right")}
    sign = {"Left": 1.0, "Right": -1.0}
    miss = slide = 0.0
    passes = []
    for _ in range(3):
        passes.append({"frames": sum(x > 0.0 for x in m["need"]), "need_max_mm": round(max(m["need"]) * 1000, 2),
                       "overlap_max_mm": round(max(m["overlap"]) * 1000, 3)})
        push = cross_pushes(m["lows"], m["need"], wrap=wrap)
        lift = cross_lifts(m["lows"], m["lift"], wrap=wrap)
        if not any(x > 0.0 for v in (*push.values(), *lift.values()) for x in v):
            break
        # B1i (the review's minor 6): each pass's push slides no planted foot over that pass's own stance runs
        slide = max(slide, *cross_slide_mm(m["lows"], push, wrap).values())
        off = {s: [(sign[s] * x * side[0], sign[s] * x * side[1], z) for x, z in zip(push[s], lift[s])]
               for s in push}
        miss = max(miss, _raise_ankles(arm, act, off)["ankle_miss_max_cm"])
        pushed = {s: [a + b for a, b in zip(pushed[s], push[s])] for s in pushed}
        lifted = {s: [a + b for a, b in zip(lifted[s], lift[s])] for s in lifted}
        # B1i (the review's minor 5): the first pass gave the clearance; a later one asks only for what still overlaps
        m = cross_measure(arm, shoes, act, 0.0)
    ob = [round(x * 1000, 1) for x in m0["overlap"]]
    oa = [round(x * 1000, 1) for x in m["overlap"]]
    moved = any(x != 0.0 for v in (*pushed.values(), *lifted.values()) for x in v)
    if moved and not any(x > 0.0 for x in m0["overlap"]):
        raise ValueError(f"{act.name}: the shoes do not overlap, yet the cross pass moved a foot")
    final = cross_slide_mm(m["lows"], pushed, wrap)  # the summed push over the final stance runs
    slide = max(slide, *final.values())
    if slide > CROSS_SLIDE_FAIL_MM:
        raise ValueError(f"{act.name}: the cross push slides a planted foot {slide} mm (over {CROSS_SLIDE_FAIL_MM})")
    if miss > ANKLE_MISS_FAIL_CM:  # B1i (the review's minor 3)
        raise ValueError(f"{act.name}: a pushed Foot lands {miss} cm from its place (over {ANKLE_MISS_FAIL_CM})")
    return {"clear_cm": round(clear * 100, 2), "overlap_before_mm": ob, "overlap_after_mm": oa,
            "overlap_max_before_mm": max(ob), "overlap_max_after_mm": max(oa),
            "overlap_frames_before": sum(x > 0 for x in ob), "overlap_frames_after": sum(x > 0 for x in oa),
            "push_max_cm": {s: round(max(v) * 100, 2) for s, v in pushed.items()},
            "push_cm": {s: [round(x * 100, 2) for x in v] for s, v in pushed.items()},
            "lift_max_cm": {s: round(max(v) * 100, 2) for s, v in lifted.items()},
            "zero_push": not moved,
            "slide_mm": final, "slide_max_mm": slide,
            "crossed_frames": sum(m0["crossed"]), "crossed_frames_after": sum(m["crossed"]),
            "ankle_miss_max_cm": miss, "passes": passes}


FOOT_REACH_M = 0.15  # B1i (the review's minor 4): a point farther than this from both feet counts for neither


def _foot_lows(arm, skins, f0: int, f1: int, tracks: dict | None = None) -> dict[str, list[float]]:
    """B1b: per frame each foot's lowest point (m, world z): the skins' points within SOLE_BAND_M of the floor, each
    counted for the foot whose Foot-to-Toes segment is nearer (1.0 when none is that low); B1i: only points within
    FOOT_REACH_M of that segment (a hand or a knee near the floor raised the nearer foot). tracks (B1i, B1j): a dict
    filled per foot with its contact patch per frame, the indices of its points within PLANT_PATCH_M over its lowest
    (an empty list when it has none), and under "xy" every frame's points (x, y) for patch_steps."""
    import bpy
    import numpy as np

    scene = bpy.context.scene
    pb = arm.pose.bones
    mw = arm.matrix_world
    out = {"Left": [], "Right": []}
    for f in range(f0, f1 + 1):
        scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        pts = []
        for sk in skins:
            ev = sk.evaluated_get(dg)
            me = ev.to_mesh()
            co = np.empty(len(me.vertices) * 3)
            me.vertices.foreach_get("co", co)
            co = co.reshape(-1, 3) @ np.array(ev.matrix_world.to_3x3()).T + np.array(ev.matrix_world.translation)
            pts.append(co if tracks is not None else co[co[:, 2] < SOLE_BAND_M])
            ev.to_mesh_clear()
        p = np.concatenate(pts) if pts else np.empty((0, 3))
        if tracks is not None:  # B1j: every point's (x, y), so a patch's own points can be followed between frames
            tracks.setdefault("xy", []).append(p[:, :2].astype(np.float64))
            band = np.nonzero(p[:, 2] < SOLE_BAND_M)[0]
            p = p[band]
        else:
            band = None
        dist = []
        for s in ("Left", "Right"):
            a = np.array(mw @ pb[f"{s}Foot"].head)
            b = np.array(mw @ pb[f"{s}Toes"].tail)
            ab = b - a
            t = np.clip(((p - a) @ ab) / max(1e-12, float(ab @ ab)), 0.0, 1.0)
            dist.append(np.linalg.norm(p - (a + t[:, None] * ab), axis=1))
        left = dist[0] <= dist[1]
        near = np.minimum(dist[0], dist[1]) <= FOOT_REACH_M
        for s, m in (("Left", left & near), ("Right", ~left & near)):
            low = float(p[m, 2].min()) if m.any() else 1.0
            out[s].append(low)
            if tracks is not None:
                tracks.setdefault(s, []).append([int(j) for j in band[m & (p[:, 2] <= low + PLANT_PATCH_M)]])
    return out


def _raise_ankles(arm, act, raises: dict[str, list]) -> dict:
    """B1b: each leg with a raise solved again per frame: its Foot moved up by raises[side][f - f0] metres (world; B1f:
    or by that world offset, a 3-tuple)
    with its world rotation kept (the Toes follow), the knee by raise_knee, the Hips untouched; the UpperLeg,
    LowerLeg and Foot rotations keyed linearly on every frame (as hips_up). Returns the feet's largest miss (cm) on
    the re-evaluated rig."""
    import bpy
    from mathutils import Matrix, Vector

    f0, f1 = _assign(arm, act)
    pb = arm.pose.bones
    bones = arm.data.bones
    raises = {s: [tuple(x) if isinstance(x, (tuple, list)) else (0.0, 0.0, float(x)) for x in v]
              for s, v in raises.items()}  # B1f: a world offset per frame, or a raise (z) as before
    legs = [(s, f"{s}UpperLeg", f"{s}LowerLeg", f"{s}Foot") for s in ("Left", "Right")
            if max(abs(c) for x in raises.get(s, [(0.0,)]) for c in x) > 1e-5]
    if not legs:
        arm.animation_data.action = None
        return {"ankle_miss_max_cm": 0.0, "legs": []}
    names = {bones[u].parent.name for _, u, _, _ in legs} | {x for leg in legs for x in leg[1:]}
    rec = {}
    for f in range(f0, f1 + 1):
        bpy.context.scene.frame_set(f)
        rec[f] = {n: pb[n].matrix.copy() for n in names}
    arm.animation_data.action = None
    to_arm = arm.matrix_world.inverted().to_3x3()

    def rel(child):
        b = bones[child]
        return b.parent.matrix_local.inverted() @ b.matrix_local

    fcs = {}
    for bag in _bags(act):
        for fc in bag.fcurves:
            if fc.data_path.endswith(".rotation_quaternion"):
                fcs[(fc.data_path.split('"')[1], fc.array_index)] = fc
    prev, solved, want = {}, {}, {}
    for f in range(f0, f1 + 1):
        r = rec[f]
        for side, u, lo, ft in legs:
            d = to_arm @ Vector(raises[side][f - f0])
            mu, ml, mf = r[u], r[lo], r[ft]
            hip, knee, ank = mu.translation, ml.translation, mf.translation
            knee2 = Vector(raise_knee(tuple(hip), tuple(knee), tuple(ank), tuple(d)))
            ank2 = ank + d
            want[(f, ft)] = ank2
            du = (knee - hip).rotation_difference(knee2 - hip)
            mu2 = Matrix.Translation(hip) @ (du.to_matrix() @ mu.to_3x3()).to_4x4()
            dl = (du @ (ank - knee)).rotation_difference(ank2 - knee2)
            ml2 = Matrix.Translation(knee2) @ (dl.to_matrix() @ du.to_matrix() @ ml.to_3x3()).to_4x4()
            mf2 = Matrix.Translation(ank2) @ mf.to_3x3().to_4x4()
            for name, m, par in ((u, mu2, r[bones[u].parent.name]), (lo, ml2, mu2), (ft, mf2, ml2)):
                q = (rel(name).inverted() @ par.inverted() @ m).to_quaternion().normalized()
                if name in prev and q.dot(prev[name]) < 0.0:
                    q = -q
                prev[name] = q
                for i in range(4):
                    if (name, i) not in fcs:
                        raise ValueError(f"{act.name}: {name} has no rotation keys")
                    solved.setdefault((name, i), []).extend((float(f), q[i]))
    for key, co in solved.items():
        fc = fcs[key]
        fc.keyframe_points.clear()
        fc.keyframe_points.add(len(co) // 2)
        fc.keyframe_points.foreach_set("co", co)
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
        fc.update()
    _assign(arm, act)
    miss = 0.0
    for f in range(f0, f1 + 1):
        bpy.context.scene.frame_set(f)
        for _, _, _, ft in legs:
            miss = max(miss, (pb[ft].matrix.translation - want[(f, ft)]).length)
    arm.animation_data.action = None
    return {"ankle_miss_max_cm": round(miss * 100.0, 3), "legs": [leg[0] for leg in legs]}


def feet_floor(arm, skins, act, rest, up_arm, wrap: bool, no_flight: bool = False) -> dict:
    """B1b: one clip on the floor at the foot (sole_floor's and the build's `floor_feet` pass): each foot's lowest
    point per frame (_foot_lows over skins), a foot under the floor raised by its own need (foot_raise) and its leg
    solved again (_raise_ankles), twice at most, the Hips untouched; what a leg cannot reach goes to the Hips by
    floor() at reach 0 (`hips_fallback_cm`). no_flight (B1e, B1k): each foot planted on its own through its stance
    (plant_offsets: its sole on the floor and its drift off the ground's travel held back, on its contact patch's own
    points, patch_steps; eased in before its landing and out after its lift-off), so the lower foot stands on the
    floor without sliding (`max_lower_cm`, `plant_hold_mm` the largest hold, `plant_ease_step_mm` the largest step
    its ease adds to a swing frame, B1l; `floated_after` counts the frames still both up after). The report
    measures the slide after: `plant_slide_mm` the largest slide a frame of a foot the plant lowered, standing
    within PLANT_ON_M on both frames of the step, `plant_moving_frames` its frames over PLANT_SLIDE_M, and `floor_slide_mm` the same over every foot on the floor (the clip's own, a walk's heel strike).
    A Foot missing its place over ANKLE_MISS_FAIL_CM fails the clip. Returns the report (sole_floor's keys)."""
    skins = skins if isinstance(skins, (list, tuple)) else [skins]
    f0, f1 = _assign(arm, act)
    tracks = {}
    lows = before = _foot_lows(arm, skins, f0, f1, tracks)
    n = f1 - f0 + 1
    total = {s: [(0.0, 0.0, 0.0)] * n for s in lows}
    lowered = {"Left": set(), "Right": set()}
    unheld = {}
    miss = 0.0

    def steps_of(tr):
        return {s: patch_steps(tr["xy"], tr[s], wrap) for s in ("Left", "Right")}
    for _ in range(2):
        steps = steps_of(tracks)
        r, low_s = plant_offsets(lows, steps, ground_step(lows, steps), no_flight, wrap, unheld=unheld)
        if max(abs(c) for v in r.values() for x in v for c in x) < 1e-4:
            break
        for s in lowered:
            lowered[s] |= set(low_s[s])
        miss = max(miss, _raise_ankles(arm, act, r)["ankle_miss_max_cm"])
        total = {s: [tuple(a + b for a, b in zip(x, y)) for x, y in zip(total[s], r[s])] for s in total}
        _assign(arm, act)
        tracks = {}
        lows = _foot_lows(arm, skins, f0, f1, tracks)
    steps = steps_of(tracks)
    g = ground_step(lows, steps)
    stances = foot_stances(before, wrap) if no_flight else {"Left": [], "Right": []}
    runs_b = {s: merge_runs(r, n, wrap) for s, r in stances.items()}
    slid = plant_slides(lows, steps, g, {s: sorted(v) for s, v in lowered.items()})
    floor_slid = plant_slides(lows, steps, g)
    low_b = [min(a, b) for a, b in zip(before["Left"], before["Right"])]
    low_a = [min(a, b) for a, b in zip(lows["Left"], lows["Right"])]
    rep = {"feet": True, "lowest_before_cm": round(min(low_b) * 100, 2),
           "max_raise_cm": {s: round(max(0.0, max(x[2] for x in v)) * 100, 2) for s, v in total.items()},
           "no_flight": no_flight,
           "max_lower_cm": round(max(0.0, -min(x[2] for v in total.values() for x in v)) * 100, 2),
           "plant_hold_mm": round(max(math.hypot(x[0], x[1]) for v in total.values() for x in v) * 1000, 1),
           "plant_ease_step_mm": round(plant_ease_step(total, runs_b) * 1000, 1),
           "plant_frames": {s: len(v) for s, v in lowered.items()},
           "plant_unheld_runs": {s: sorted(set(v)) for s, v in unheld.items()},
           "ankle_miss_max_cm": miss, "hips_fallback_cm": 0.0,
           "plant_slide_mm": round(max(slid.values(), default=0.0) * 1000, 2),
           "plant_moving_frames": sorted(j for j, v in slid.items() if v > PLANT_SLIDE_M),
           "floor_slide_mm": round(max(floor_slid.values(), default=0.0) * 1000, 2)}
    if miss > ANKLE_MISS_FAIL_CM:  # B1i (the review's minor 3): two_bone's clamp left a Foot short
        raise ValueError(f"{act.name}: a re-solved Foot lands {miss} cm from its place (over {ANKLE_MISS_FAIL_CM})")
    if min(low_a) < -SOLE_UNDER_M:  # a leg out of reach: the rest at the Hips, each frame its own need
        fb = floor(arm, skins, act, rest, up_arm, wrap=wrap, reach=0)
        rep["hips_fallback_cm"] = fb["max_lift_cm"]
        _assign(arm, act)
        lows = _foot_lows(arm, skins, f0, f1)
        low_a = [min(a, b) for a, b in zip(lows["Left"], lows["Right"])]
    arm.animation_data.action = None
    rep.update(lowest_after_cm=round(min(low_a) * 100, 2), highest_low_after_cm=round(max(low_a) * 100, 2),
               under_2mm_frames=sum(z < -SOLE_UNDER_M for z in low_a),
               floated_frames=len(floated_frames(low_b, low_a)),
               floated_after=sum(z > FLOAT_TOL_M for z in low_a) if no_flight else 0,
               lowest_before_mm=[round(x * 1000, 1) for x in low_b],
               lowest_after_mm=[round(x * 1000, 1) for x in low_a])
    return rep


def cross_clear_cm(path: str, clip: str):
    """B1f: the clip's `cross_out_cm` (the crossing shoes' clearance, cm; None: no cross pass): its settings', or for
    a clip the settings do not list (the loco set's strafes and variants, which sole_floor covers too) [defaults]'."""
    with open(path, "rb") as f:
        data = tomllib.load(f)
    if clip in data.get("clips", {}):
        return settings(path, clip).get("cross_out_cm")
    return data.get("defaults", {}).get("cross_out_cm")


def sole_floor(arm, skins, path: str) -> dict:
    """B1 (art #196, the Walk hop), B1b (the heel strike): after the dress, every ground clip (ground_clips: the
    settings' floor-true clips and every clip they do not list) put on the floor with all of skins measured (the
    body and the sneakers: the sole dips up to 19 mm under the floor at heel strike) at the foot, not the Hips: per
    frame each foot's lowest (_foot_lows) and its raise (foot_raise), the leg solved again (_raise_ankles), twice at
    most; what a leg cannot reach (a straight leg) is lifted at the Hips by floor() at reach 0 (`hips_fallback_cm`).
    A clip still under FLOOR_FAIL_CM fails. Returns per clip the feet's lowest before and after, the raises, the miss,
    `under_2mm_frames` and `floated_frames` (floated_frames over the lower foot)."""
    from mathutils import Vector  # Blender only
    import bpy

    p = Path(path)
    if not p.is_file():
        p = Path(__file__).resolve().parent / "anim_sets" / f"{path}.toml"
    rest = {b.name: b.matrix_local.to_3x3() for b in arm.data.bones}
    up_arm = arm.matrix_world.to_3x3().normalized().inverted() @ Vector((0.0, 0.0, 1.0))
    frame = bpy.context.scene.frame_current
    keep = arm.animation_data.action if arm.animation_data else None
    keep_slot = arm.animation_data.action_slot if keep is not None else None
    acts = {a.name.split("|", 1)[1]: a for a in bpy.data.actions if a.name.startswith("CharacterArmature|")}
    out = {}
    shoes = next((s for s in skins if s.name == "shoes"), None)
    for clip in ground_clips(sorted(acts), str(p)):
        act = acts[clip]
        cross = cross_clear_cm(str(p), clip)
        rep = feet_floor(arm, skins, act, rest, up_arm, clip.endswith("_Loop"), no_flight=not can_fly(clip))
        # B1g: the shoes apart after the floor: the push is across, the Foot's world rotation kept, so the soles stay
        # where the floor put them (B1f pushed first, and the floor's raises put 0.7 to 3 mm of overlap back)
        cr = feet_cross(arm, shoes, act, cross / 100.0, clip.endswith("_Loop")) if shoes and cross is not None else None
        if cr is not None:
            rep["cross"] = cr
        out[clip] = rep
        if rep["lowest_after_cm"] < FLOOR_FAIL_CM:
            raise ValueError(f"{act.name}: still {rep['lowest_after_cm']} cm under the floor with the soles")
    if keep is not None:
        arm.animation_data.action = keep
        if keep_slot is not None:
            arm.animation_data.action_slot = keep_slot
    bpy.context.scene.frame_set(frame)
    return out


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
    shifted by the cycle's length (repeat_keys), the seam key moved to the new end. Each copy keeps its source key's
    interpolation, handle types and handles (shifted with it, A3d), so the curve's shape repeats as it was."""
    f0, f1 = (float(x) for x in act.frame_range)
    for bag in _bags(act):
        for fc in bag.fcurves:
            pts = fc.keyframe_points
            n = len(pts)
            co, hl, hr = [0.0] * (2 * n), [0.0] * (2 * n), [0.0] * (2 * n)
            pts.foreach_get("co", co)
            pts.foreach_get("handle_left", hl)
            pts.foreach_get("handle_right", hr)
            kinds = [(p.interpolation, p.handle_left_type, p.handle_right_type) for p in pts]
            plan = repeat_keys([co[2 * i] for i in range(n)], f0, f1, times)
            pts.clear()
            pts.add(len(plan))
            for kp, (_, i) in zip(pts, plan):  # the types first, so setting the handles below does not re-align them
                kp.interpolation, kp.handle_left_type, kp.handle_right_type = kinds[i]
            pts.foreach_set("co", [x for fr, i in plan for x in (fr, co[2 * i + 1])])
            pts.foreach_set("handle_left", [x for fr, i in plan for x in (hl[2 * i] + fr - co[2 * i], hl[2 * i + 1])])
            pts.foreach_set("handle_right", [x for fr, i in plan for x in (hr[2 * i] + fr - co[2 * i], hr[2 * i + 1])])
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


def ground_lift(lowest: list[float], last: int, fade: int) -> list[float]:
    """A3, floor "ground": per frame the lift that puts frames 0..last (the crouch before the push-off) exactly on
    the floor, then the last one's lift faded to 0 over fade frames (a smoothstep), 0 after (the airborne tuck)."""
    out = []
    for i, z in enumerate(lowest):
        if i <= last:
            out.append(max(0.0, -z))
        else:
            u = min(1.0, (i - last) / max(1, fade))
            out.append(out[last] * (1.0 - u * u * (3.0 - 2.0 * u)))
    return out


def floor(arm, skin, act, rest, up_arm, wrap: bool = False, reach: int = 2, check_only: bool = False,
          check_to=None, fade: int = 3) -> dict:
    """The `floor` edit on one action: samples the posed skin on every frame, lifts the Hips' location keys by
    lift_profile (wrap: a loop; reach 0: each frame its own need, keyed on every frame). check_only (A3, "ground"):
    the frames up to check_to (all without it) lifted onto the floor, the lift faded out over fade frames after
    (ground_lift), and checked as lowest_after_cm. skin may be a list of meshes (B1: the body and the sneakers, so the
    soles count); each frame's lowest is the lowest of them (lowest_of). The report's floated_frames
    (floated_frames) counts the frames the lift put more than 5 mm over the floor that were on it before."""
    import bpy
    import numpy as np
    from mathutils import Vector

    scene = bpy.context.scene
    f0, f1 = _assign(arm, act)

    def lowest_per_frame():
        out = []
        skins = skin if isinstance(skin, (list, tuple)) else [skin]
        for f in range(f0, f1 + 1):
            scene.frame_set(f)
            dg = bpy.context.evaluated_depsgraph_get()
            lows = []
            for sk in skins:
                ev = sk.evaluated_get(dg)
                me = ev.to_mesh()
                co = np.empty(len(me.vertices) * 3)
                me.vertices.foreach_get("co", co)
                co = co.reshape(-1, 3) @ np.array(ev.matrix_world.to_3x3()).T + np.array(ev.matrix_world.translation)
                lows.append([float(co[:, 2].min())] if len(co) else [])
                ev.to_mesh_clear()
            out.append(lowest_of([x for x in lows if x])[0])
        return out

    before = lowest_per_frame()
    if check_only:  # A3 "ground": the ground frames lifted by their own need, the lift faded out over fade frames
        last = len(before) - 1 if check_to is None else min(len(before) - 1, max(0, check_to - f0))
        lift = ground_lift(before, last, fade)
    else:
        lift = lift_profile(before, reach=reach, wrap=wrap)
    up_h = rest["Hips"].inverted() @ Vector(up_arm).normalized()
    _shift_hips(act, f0, f1, [up_h * x for x in lift], bake=reach == 0 or check_only)
    after = lowest_per_frame()
    arm.animation_data.action = None
    if check_only:
        return {"ground": True, "ground_frames": [f0, f0 + last], "lowest_before_cm": round(min(before[:last + 1]) * 100, 2),
                "lowest_after_cm": round(min(after[:last + 1]) * 100, 2), "max_lift_cm": round(max(lift) * 100, 2),
                "highest_low_after_cm": round(max(after[:last + 1]) * 100, 2), "lowest_all_after_cm": round(min(after) * 100, 2)}
    return {"lowest_before_cm": round(min(before) * 100, 2), "lowest_after_cm": round(min(after) * 100, 2),
            "max_lift_cm": round(max(lift) * 100, 2), "highest_low_after_cm": round(max(after) * 100, 2),
            "wrap": wrap, "reach": reach, "floated_frames": len(floated_frames(before, after)),
            "lowest_before_mm": [round(x * 1000, 1) for x in before], "lowest_after_mm": [round(x * 1000, 1) for x in after]}
