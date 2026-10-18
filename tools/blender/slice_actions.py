"""Puts an animation set's clips on a saved character (art #42 part C: the slice character; docs/godot.md, "The slice
character"). Runs inside Blender:

    blender -b --python slice_actions.py -- --character <id>.blend --anim <set>_<body>.blend --clips A,B,...
        --out <slice>.blend --json <slice>.actions.json

The character is a saved one (`assemble --blend`, docs/assembly.md, "The saved character"): one armature with the
transforms applied and the body type's pack actions. The set's file (`anim-set`, docs/animations.md, "Animation sets")
holds the same rig with the clips baked under their own names, its transforms applied the same way (location keys in
metres). This drops the pack's actions, appends the named clips, checks that every clip's bones exist on the
character's rig and that the two rigs' rest poses agree (the toes excepted: their rest follows each shoe), and saves a
copy at the set's 30 fps that `export --textured` accepts. With `--eye-height H` it then scales the whole character
uniformly about the origin (the floor) so the eyes' rest centre is at H metres: the rig's rest, every part's mesh
with its shape keys, and every clip's location keys (the engineer's `eyes16`, art #42).

With `--own-proportions` (art #207) the character's skeleton may differ from the donor's (the alien base character's
by up to 214 mm, art #196): the rest difference is only reported, and the clips' Root and Hips location keys (and the
armature object's) scale by the character's leg length over the donor's, before any `--eye-height` scale. The rules
live in slice_math.py.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys

import bpy
from mathutils import Matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import slice_math  # noqa: E402

TOES = slice_math.TOES
BONE_RE = re.compile(r'pose\.bones\["([^"]+)"\]')


def _fcurves(action):
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                yield from bag.fcurves


def _one_armature(objects):
    arms = [o for o in objects if o.type == "ARMATURE"]
    if len(arms) != 1:
        raise SystemExit(f"expected one armature, found {[o.name for o in arms]}")
    return arms[0]


def _eye_z(parts):
    """The eyes' rest centre height (the middle of their lowest and highest vertex, as godot-check measures it)."""
    eyes = next((o for o in parts if o.name.endswith("_eyes")), None)
    if eyes is None:
        raise SystemExit("no _eyes part to scale by")
    zs = [(eyes.matrix_world @ v.co).z for v in eyes.data.vertices]
    return (min(zs) + max(zs)) / 2


def scale_character(arm, parts, actions, s):
    """Scales the character by s about the origin: the rig's rest bones, every part with its shape keys, and the
    clips' location keys (pose locations are in the bones' rest space, so they scale with it)."""
    for o in [arm] + parts:
        if not all(abs(a - b) < 1e-6 for ra, rb in zip(o.matrix_world, Matrix.Identity(4)) for a, b in zip(ra, rb)):
            raise SystemExit(f"{o.name} has a transform; the saved character has its transforms applied")
    m = Matrix.Scale(s, 4)
    arm.data.transform(m)
    for o in parts:
        o.data.transform(m, shape_keys=True)
        o.data.update()
    keys = 0
    for act in actions:
        for fc in _fcurves(act):
            if fc.data_path.endswith(".location") or fc.data_path == "location":
                for kp in fc.keyframe_points:
                    kp.co[1] *= s
                    kp.handle_left[1] *= s
                    kp.handle_right[1] *= s
                    keys += 1
                fc.update()
    return keys


def scale_leg_keys(actions, s):
    """Scales the clips' Root and Hips location keys (and the armature object's) by s, the leg length ratio of
    --own-proportions; the other bones' keys are rotations, which carry over to any proportions."""
    keys = 0
    for act in actions:
        for fc in _fcurves(act):
            if slice_math.scales_with_legs(fc.data_path):
                for kp in fc.keyframe_points:
                    kp.co[1] *= s
                    kp.handle_left[1] *= s
                    kp.handle_right[1] *= s
                    keys += 1
                fc.update()
    return keys


def main(argv):
    a = slice_math.arguments(argv)
    clips = [c for c in a.clips.split(",") if c]

    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(a.character))
    arm = _one_armature(bpy.data.objects)
    parts = sorted((o for o in bpy.data.objects if o.type == "MESH"), key=lambda o: o.name)
    dropped = sorted(act.name for act in bpy.data.actions)
    if arm.animation_data:
        for track in list(arm.animation_data.nla_tracks):
            arm.animation_data.nla_tracks.remove(track)
        arm.animation_data.action = None
    for act in list(bpy.data.actions):
        bpy.data.actions.remove(act)

    with bpy.data.libraries.load(os.path.abspath(a.anim), link=False) as (src, dst):
        missing = [c for c in clips if c not in src.actions]
        if missing:
            raise SystemExit(f"the set's file has no action {missing}")
        dst.actions = list(clips)
        dst.armatures = list(src.armatures)
    if len(dst.armatures) != 1:
        raise SystemExit(f"the set's file holds {len(dst.armatures)} armatures, expected one")
    donor = dst.armatures[0]
    bones = {b.name: b for b in arm.data.bones}
    rest, turns = {}, {}
    for b in donor.bones:
        mine = bones.get(b.name)
        if mine is None:
            raise SystemExit(f"the set's rig has bone {b.name!r}, the character's rig has not")
        rest[b.name] = (mine.head_local - b.head_local).length
        q_mine, q_donor = mine.matrix_local.to_quaternion(), b.matrix_local.to_quaternion()
        turns[b.name] = math.degrees(q_donor.rotation_difference(q_mine).angle)
    if set(bones) - set(rest):
        raise SystemExit(f"the character's rig has bones the set's has not: {sorted(set(bones) - set(rest))}")
    body_err, worst, refusal = slice_math.rest_check(rest, a.own_proportions)
    if refusal:
        raise SystemExit(refusal)
    turn, turn_worst = slice_math.rest_turn(turns)
    leg, leg_m = 1.0, None  # leg_m: [the donor's leg length, the character's] (m)
    if a.own_proportions:
        mine_heads = {b.name: tuple(b.head_local) for b in arm.data.bones}
        donor_heads = {b.name: tuple(b.head_local) for b in donor.bones}
        leg = slice_math.leg_scale(mine_heads, donor_heads)
        leg_m = [round(slice_math.leg_length(donor_heads), 4), round(slice_math.leg_length(mine_heads), 4)]
    bpy.data.armatures.remove(donor)

    actions = {}
    for name in clips:
        act = bpy.data.actions.get(name)
        if act is None:
            raise SystemExit(f"{name} was not appended")
        unknown = sorted({m.group(1) for fc in _fcurves(act) for m in [BONE_RE.search(fc.data_path)] if m} - set(bones))
        if unknown:
            raise SystemExit(f"{name} animates bones the rig lacks: {unknown}")
        act.use_fake_user = True
        actions[name] = [int(act.frame_range[0]), int(act.frame_range[1])]
    for pb in arm.pose.bones:
        pb.location = (0.0, 0.0, 0.0)
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)

    leg_keys = scale_leg_keys([bpy.data.actions[n] for n in actions], leg) if a.own_proportions else 0

    eyes_before = _eye_z(parts)
    scale, scaled_keys = 1.0, 0
    if a.eye_height:
        scale = a.eye_height / eyes_before
        scaled_keys = scale_character(arm, parts, [bpy.data.actions[n] for n in actions], scale)
    eyes_after = _eye_z(parts)

    scene = bpy.context.scene
    scene.render.fps = 30
    scene.render.fps_base = 1.0
    scene.frame_start = min(r[0] for r in actions.values())
    scene.frame_end = max(r[1] for r in actions.values())
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.out), copy=True, compress=True)
    report = {"character": a.character.replace("\\", "/"), "anim": a.anim.replace("\\", "/"),
              "out": a.out.replace("\\", "/"), "armature": arm.name, "bones": len(bones),
              "parts": [o.name for o in parts], "fps": 30, "dropped_actions": dropped, "actions": actions,
              "rest_max_mm": round(body_err * 1000, 4), "rest_worst": worst,
              "rest_turn_max_deg": round(turn, 3), "rest_turn_worst": turn_worst,
              "own_proportions": a.own_proportions, "leg_m": leg_m, "leg_scale": round(leg, 6),
              "leg_scaled_location_keys": leg_keys,
              "toes_rest_mm": {t: round(rest[t] * 1000, 2) for t in TOES if t in rest},
              "scale": round(scale, 6), "eyes_m": [round(eyes_before, 4), round(eyes_after, 4)],
              "scaled_location_keys": scaled_keys}
    with open(a.json, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    print("SLICE", json.dumps({k: report[k] for k in ("bones", "rest_max_mm", "rest_turn_max_deg", "rest_turn_worst", "toes_rest_mm", "leg_scale", "scale", "eyes_m")}), len(actions), "clips")


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
