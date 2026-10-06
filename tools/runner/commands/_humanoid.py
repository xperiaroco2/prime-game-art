"""The SkeletonProfileHumanoid trial of `godot-check --humanoid` (docs/godot.md): the character imported a second time
with Godot's import-time retargeting (a BoneMap to SkeletonProfileHumanoid on the Skeleton3D), then checked like the
plain import and compared with it pose by pose. Input for the character contract v2; not adopted: the plain import
stays what the check asserts, and the trial never fails the command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .. import common
from . import _godot

# SkeletonProfileHumanoid bone -> Ultimate Modular rig bone. The rig's fingers have four joints, the first in the palm
# (Index1.L starts 2.8 cm from the wrist, at the thumb's base): that one is a metacarpal, which the profile has only for
# the thumb, so Index2-4 map to Proximal, Intermediate and Distal and Index1 stays unmapped.
BONE_MAP: dict[str, str] = {"Root": "Root", "Hips": "Hips", "Spine": "Abdomen", "Chest": "Torso", "UpperChest": "Chest",
                            "Neck": "Neck", "Head": "Head"}
for _side, _s in (("Left", "L"), ("Right", "R")):
    BONE_MAP.update({
        f"{_side}Shoulder": f"Shoulder.{_s}", f"{_side}UpperArm": f"UpperArm.{_s}", f"{_side}LowerArm": f"LowerArm.{_s}",
        f"{_side}Hand": f"Wrist.{_s}", f"{_side}ThumbMetacarpal": f"Thumb1.{_s}", f"{_side}ThumbProximal": f"Thumb2.{_s}",
        f"{_side}ThumbDistal": f"Thumb3.{_s}", f"{_side}UpperLeg": f"UpperLeg.{_s}", f"{_side}LowerLeg": f"LowerLeg.{_s}",
        f"{_side}Foot": f"Foot.{_s}",
    })
    for _finger, _rig in (("Index", "Index"), ("Middle", "Middle"), ("Ring", "Ring"), ("Little", "Pinky")):
        for _joint, _n in (("Proximal", 2), ("Intermediate", 3), ("Distal", 4)):
            BONE_MAP[f"{_side}{_finger}{_joint}"] = f"{_rig}{_n}.{_s}"
# Profile bones the rig has nothing for.
PROFILE_ONLY = ("LeftEye", "RightEye", "Jaw", "LeftToes", "RightToes")
BONE_MAP_RES = "res://import/um_humanoid_bone_map.tres"
# The trial's imports. Godot's retarget/remove_tracks/unimportant_positions (on by default) drops the position tracks of
# every mapped bone but the root and the hips; the pack moves the feet and the shoulders with position keys, so with it
# the retargeted Walk's feet end up about 52 cm off. With it off every mapped joint stays within about 1 mm. Both runs
# are reported; keeping those tracks is exact here because the trial retargets onto the same rig, and may not carry over
# to a skeleton with other proportions (the reason Godot drops them by default).
VARIANTS: dict[str, dict[str, Any]] = {
    "keep_positions": {"retarget/remove_tracks/unimportant_positions": False},
    "godot_defaults": {},
}


def staged_name(stem: str, variant: str) -> str:
    return f"{stem}_humanoid" if variant == "keep_positions" else f"{stem}_humanoid_defaults"
# Poses compared between the plain and the retargeted import: (animation, whole frames at 24 fps).
POSES = {"CharacterArmature|Idle": (0, 10, 20, 30), "CharacterArmature|Walk": (0, 8, 16, 24), "CharacterArmature|Wave": (0, 15, 30)}


def bone_map_tres(mapping: dict[str, str] = BONE_MAP) -> str:
    """The BoneMap resource as text (Godot's .tres format): the profile is a SkeletonProfileHumanoid sub-resource."""
    lines = ['[gd_resource type="BoneMap" load_steps=2 format=3]', "",
             '[sub_resource type="SkeletonProfileHumanoid" id="SkeletonProfileHumanoid_um"]', "", "[resource]",
             'profile = SubResource("SkeletonProfileHumanoid_um")']
    lines += [f'bone_map/{profile} = &"{rig}"' for profile, rig in mapping.items()]
    return "\n".join(lines) + "\n"


def nodes(skeleton_path: str) -> dict[str, dict]:
    """The importer's node options that put the BoneMap on the skeleton node (its retarget options)."""
    return {f"PATH:{skeleton_path}": {"retarget/bone_map": _godot.Resource(BONE_MAP_RES)}}


def _request(fps: int = 24) -> dict[str, Any]:
    return {"poses": {name: [round(f / fps, 6) for f in frames] for name, frames in POSES.items()}}


def pose_deviation(plain: dict[str, Any], retargeted: dict[str, Any], renamed: dict[str, str]) -> dict[str, Any]:
    """The largest distance between a mapped joint in the plain and in the retargeted import at the same pose."""
    worst, where, compared = 0.0, "", 0
    for anim, times in plain.get("poses", {}).items():
        for t, joints in times.items():
            other = retargeted.get("poses", {}).get(anim, {}).get(t, {})
            for rig, profile in renamed.items():
                if rig in joints and profile in other:
                    d = sum((a - b) ** 2 for a, b in zip(joints[rig], other[profile])) ** 0.5
                    compared += 1
                    if d > worst:
                        worst, where = d, f"{profile} in {anim} at {t} s"
    return {"max_mm": round(worst * 1000, 3), "where": where, "joints_compared": compared}


def trial(glb: Path, out: Path, contract: dict[str, Any]) -> dict[str, Any]:
    """Imports glb with the BoneMap once per VARIANTS entry, checks each like godot-check and compares its poses with
    the plain import (which godot-check staged first). Writes <out>/humanoid.json and prints a summary; never fails
    the command."""
    common.say(f"{glb.name}: SkeletonProfileHumanoid trial (report only, not adopted)")
    plain_path = f"res://import/{glb.stem}.glb"
    plain, _ = _godot.inspect(plain_path, out / "plain_poses.json", _request())
    skeleton_path = plain["skeletons"][0]["path"]
    (_godot.IMPORT_DIR / Path(BONE_MAP_RES).name).write_text(bone_map_tres(), encoding="utf-8", newline="\n")
    staged = {}
    for variant, options in VARIANTS.items():
        node = nodes(skeleton_path)
        node[f"PATH:{skeleton_path}"].update(options)
        staged[variant] = _godot.stage(glb, staged_name(glb.stem, variant), nodes=node, params=_godot.import_params(glb))
    lines = _godot.import_project()
    renamed = {rig: profile for profile, rig in BONE_MAP.items()}
    expect = _godot.expectations(glb)
    rig_bones = expect["bones"]
    report: dict[str, Any] = {
        "glb": glb.as_posix(),
        "mapped": {profile: rig for profile, rig in BONE_MAP.items()},
        "mapped_count": len(BONE_MAP),
        "rig_bones_unmapped": [b for b in rig_bones if b not in renamed],
        "profile_bones_without_rig_bone": list(PROFILE_ONLY),
        "variants": {},
    }
    common.say(f"  mapped {len(BONE_MAP)} of the profile's {len(BONE_MAP) + len(PROFILE_ONLY)} bones; rig bones left "
               f"unmapped: {', '.join(report['rig_bones_unmapped'])}; profile bones without a rig bone: {', '.join(PROFILE_ONLY)}")
    for variant, res_path in staged.items():
        dump, more = _godot.inspect(res_path, out / f"humanoid_{variant}_inspect.json", _request())
        mine = _godot.lines_for(lines, res_path, list(staged.values()))
        checks = _godot.evaluate(dump, expect, contract, mine + more, renamed=renamed)
        dev = pose_deviation(plain, dump, renamed)
        report["variants"][variant] = {
            "res_path": res_path,
            "retarget_options": VARIANTS[variant],
            "skeleton": dump["skeletons"][0]["path"] if dump["skeletons"] else None,
            "bones_after_import": dump["skeletons"][0]["bones"] if dump["skeletons"] else [],
            "checks": checks,
            "position_tracks": {n: a.get("position_tracks") for p in dump["players"] for n, a in p["animations"].items()
                                if n.endswith("|Walk")},
            "pose_deviation_from_plain_import": dev,
            "godot_output": mine + more,
        }
        common.say(f"  {variant} ({VARIANTS[variant] or 'every retarget option at its default'}):")
        for c in checks:
            common.say(f"    {'ok   ' if c['status'] == 'pass' else c['status']:5} {c['check']}: {c['detail']}")
        common.say(f"    mapped joints against the plain import: within {dev['max_mm']} mm over {dev['joints_compared']} "
                   f"joint positions (worst {dev['where'] or '-'})")
    (out / "humanoid.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    common.say(f"  report: {(out / 'humanoid.json').as_posix()}")
    return report
