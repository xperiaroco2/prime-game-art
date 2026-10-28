"""The alien clips fitted to a body with its own leg proportions (art #196, T2), in Blender: alien_char_build.py runs
it with `--leg-fit <donor.blend>` before the clip edits, alien_loco.py on the loops it appends from other files when
the build's char.json records a leg_fit.

The clips were made on the donor rig (S4b's body); their rotations are bone-local, so they carry over, but the feet
land elsewhere on legs of other proportions (M1f's: thigh 0.255 m against 0.323, shin 0.420 against 0.403, the ankle
1.9 cm lower, the foot 3.6 cm shorter). Two steps, per action:
1. the Root and Hips location keys (and the armature object's) scaled by the body's leg length over the donor's
   (alien_char_geom.leg_fit, slice --own-proportions' rule): the bob and the travel in proportion to the legs;
2. the foot match: per frame the Hips moved along the world's up so the lowest of the feet's points (each Foot and
   Toes bone's head, each Toes bone's tail) is as high as on the donor rig playing the unscaled clip, keyed on every
   frame. On M1f the scale alone left the jog's planted toes rising 4.6 cm over a stance of 4 frames (the donor's
   1.4 cm), so a contact lasted 2 frames and the loco set's measure found no ground speed. With the match the
   contacts are found, but the feet's horizontal sweep still differs (the sprint measures 4.60 m/s against the
   donor's 7.80): the next step is the feet on the donor's trajectories by IK (docs/animations.md, T2).
"""
from __future__ import annotations

import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_char_geom as G  # noqa: E402
import alien_clip_edit as E  # noqa: E402
import slice_actions  # noqa: E402

FEET = ("LeftFoot", "LeftToes", "RightFoot", "RightToes")
TIPS = ("LeftToes", "RightToes")


def _donor(path: str):
    with bpy.data.libraries.load(str(Path(path).resolve()), link=False) as (src, dst):
        dst.armatures = list(src.armatures)
    if len(dst.armatures) != 1:
        raise SystemExit(f"--leg-fit {path}: {len(dst.armatures)} armatures, expected one")
    obj = bpy.data.objects.new("leg_fit_donor", dst.armatures[0])
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _lowest(obj, f0: int, f1: int) -> list[float]:
    """Per frame the lowest of the feet's points (world z, m) of obj playing its assigned action."""
    scene, mw, out = bpy.context.scene, obj.matrix_world, []
    for f in range(f0, f1 + 1):
        scene.frame_set(f)
        pts = [obj.pose.bones[b].head for b in FEET] + [obj.pose.bones[b].tail for b in TIPS]
        out.append(min((mw @ p).z for p in pts))
    return out


def fit(arm, donor_path: str, actions: list) -> dict:
    """Both steps on actions (bpy actions of arm, keyed for the donor's proportions); returns the report: leg_m,
    scale, donor, keys (the scaled ones) and per action the foot match's Hips offset (min and max, cm)."""
    donor = _donor(donor_path)
    rep = G.leg_fit({b.name: tuple(arm.matrix_world @ b.head_local) for b in arm.data.bones},
                    {b.name: tuple(b.head_local) for b in donor.data.bones})
    theirs = {}
    for act in actions:  # the donor on the clips as they were made
        f0, f1 = E._assign(donor, act)
        theirs[act.name] = (f0, f1, _lowest(donor, f0, f1))
    keys = slice_actions.scale_leg_keys(actions, rep["scale"])
    up_h = (arm.data.bones["Hips"].matrix_local.to_3x3().inverted()
            @ (arm.matrix_world.to_3x3().normalized().inverted() @ Vector((0.0, 0.0, 1.0)))).normalized()
    match = {}
    for act in actions:
        f0, f1, low = theirs[act.name]
        E._assign(arm, act)
        dz = [t - m for m, t in zip(_lowest(arm, f0, f1), low)]
        E._shift_hips(act, f0, f1, [up_h * d for d in dz], bake=True)
        after = _lowest(arm, f0, f1)
        match[act.name.split("|", 1)[-1]] = {
            "dz_cm": [round(min(dz) * 100, 2), round(max(dz) * 100, 2)],
            "miss_mm": round(max(abs(a - t) for a, t in zip(after, low)) * 1000, 2)}
    arm.animation_data.action = None
    data = donor.data
    bpy.data.objects.remove(donor)
    bpy.data.armatures.remove(data)
    return {**rep, "donor": str(donor_path), "actions": len(actions), "keys": keys, "foot_match": match}
