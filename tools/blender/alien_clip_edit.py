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
- `floor`: `true` lifts the Hips on the frames whose posed skin goes under the floor (anim_edit's `floor` with
  `mode = "lift"`): per frame the lowest skinned vertex below z = 0, a running max over +-2 frames smoothed over
  +-2 frames (`lift_profile`), added to the Hips' location keys along the world's up. The clips came from a rig whose
  legs and feet differ from the alien's (the body's rest was refitted, alien_body.py step 1), so the stand sank
  about 1.2 cm and the crouch about 8 cm.
Pure maths (`cap_turn`, `axis_turn`) has no bpy and is unit-tested (tools/tests/test_alien_clip_edit.py).
"""
from __future__ import annotations

import math
import tomllib

FINGERS = ("Index", "Middle", "Ring", "Little")
SEGMENTS = ("Proximal", "Intermediate", "Distal")
THUMB = ("ThumbProximal", "ThumbDistal")
KEYS = ("finger_cap_deg", "thumb_cap_deg", "abduct_deg", "swing_deg", "floor")


def settings(path: str, clip: str) -> dict:
    """The clip's settings: [defaults] under [clips.<clip>]; an unknown key raises."""
    with open(path, "rb") as f:
        data = tomllib.load(f)
    out = dict(data.get("defaults", {}))
    out.update(data.get("clips", {}).get(clip, {}))
    bad = sorted(set(out) - set(KEYS))
    if bad:
        raise ValueError(f"{path} [{clip}]: unknown keys {bad}")
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


def lift_profile(lowest: list[float], reach: int = 2) -> list[float]:
    """Per frame the lift (m) that puts the lowest point on the floor: max(0, -lowest) as a running max over +-reach
    frames, then a moving average over +-reach (the ends held), so no frame stays under and the lift has no step."""
    n = len(lowest)
    need = [max(0.0, -z) for z in lowest]
    run = [max(need[max(0, i - reach):i + reach + 1]) for i in range(n)]
    return [sum(run[max(0, i - reach):i + reach + 1]) / len(run[max(0, i - reach):i + reach + 1]) for i in range(n)]


def q_mul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (aw * bw - ax * bx - ay * by - az * bz, aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx, aw * bz + ax * by - ay * bx + az * bw)


def apply(arm, skin, path: str) -> dict:
    """Edits every CharacterArmature|<clip> action of arm (a Blender armature object) by its settings; returns the
    report per clip (the settings used and the largest finger turn before and after)."""
    from mathutils import Vector  # Blender only

    rest = {b.name: b.matrix_local.to_3x3() for b in arm.data.bones}
    world = arm.matrix_world.to_3x3().normalized().inverted()
    fwd_arm = world @ Vector((0.0, -1.0, 0.0))  # the character faces -Y in Blender
    side_arm = world @ Vector((1.0, 0.0, 0.0))  # its left
    report = {}
    for act in [a for a in __import__("bpy").data.actions if a.name.startswith("CharacterArmature|")]:
        clip = act.name.split("|", 1)[1]
        cfg = settings(path, clip)
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
        rep = {"settings": cfg, "finger_max_before_deg": 0.0, "finger_max_after_deg": 0.0, "bones_edited": 0}
        for layer in act.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
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
        if cfg.get("floor"):
            rep["floor"] = floor(arm, skin, act, rest["Hips"].inverted() @ (world @ Vector((0.0, 0.0, 1.0))))
        report[clip] = rep
    return report


def floor(arm, skin, act, up_hips) -> dict:
    """The `floor` edit on one action: samples the posed skin on every frame, lifts the Hips' location keys by
    lift_profile. up_hips: the world's up in the Hips' rest frame (a basis location is in that frame)."""
    import bpy
    import numpy as np

    scene = bpy.context.scene
    ad = arm.animation_data or arm.animation_data_create()
    ad.action = act
    ad.action_slot = act.slots[0]
    f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])

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
    lift = lift_profile(before)
    loc = {}
    for layer in act.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for fc in bag.fcurves:
                    if fc.data_path == 'pose.bones["Hips"].location':
                        loc[fc.array_index] = fc
    if len(loc) != 3:
        raise ValueError(f"{act.name}: no Hips location keys to lift")
    for i, fc in loc.items():
        for kp in fc.keyframe_points:
            f = min(max(int(round(kp.co[0])), f0), f1)
            d = lift[f - f0] * up_hips[i]
            kp.co[1] += d
            kp.handle_left[1] += d
            kp.handle_right[1] += d
        fc.update()
    after = lowest_per_frame()
    ad.action = None
    return {"lowest_before_cm": round(min(before) * 100, 2), "lowest_after_cm": round(min(after) * 100, 2),
            "max_lift_cm": round(max(lift) * 100, 2), "highest_low_after_cm": round(max(after) * 100, 2)}
