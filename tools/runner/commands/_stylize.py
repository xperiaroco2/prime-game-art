"""The plan for `stylize-quaternius`: presets and every parameter tools/blender/stylize_quaternius.py applies to restyle
the CC0 Quaternius base body into our base body (art #14). Pure Python, so every number has a test without Blender.
Bones are named by their contract (profile) names here and turned into the rig's own names through the Quaternius bone
map, so the Blender script never hard-codes a vendor name.

The route (the batch 2 review, art #5): the Quaternius body is the rig, weight and topology donor; our mannequin-lanky
(art #11) is the look target: an egg head, a blank face with a long cone nose, a soft and lanky adult body.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any

from .. import common
from . import _contract

SOURCE_PARTS = ("quaternius", "Universal_Base_Characters", "Universal Base Characters[Standard]", "Base Characters",
                "Godot - UE", "Superhero_Male_FullBody.gltf")

# Meshes the source carries beside the body: the eyes and eyebrows (a blank face: eyes and mouth are changeable slots).
# "Icosphere" is the glTF importer's bone display shape, never in the file; it is listed so a .blend made elsewhere
# loses it too. Any other mesh that is not skinned to the armature is deleted as well.
DROP_OBJECTS = ("Icosphere", "Eyes", "Eyebrows")
BODY = "Body"  # the body mesh's name in our files (the source calls it SuperHero_Male)
# The meshes an exported base body may hold; clothing pieces join this list when the cut-piece tool exists.
ALLOWED_MESHES = (BODY,)

HEIGHT = 1.75
TARGET_TRIANGLES = 6000  # the contract's body target (cap 8,000)

# The palette: one matte material whose base colour is a small image of flat colour cells; every face's UVs sit in
# the centre of its colour's cell. The shared game palette replaces these cells later; the layout stays.
PALETTE_CELLS = 4  # 4 x 4 cells
PALETTE_CELL_PX = 4
PALETTE = {
    "skin": {"cell": 0, "srgb": (0.87, 0.64, 0.49)},
    "briefs": {"cell": 1, "srgb": (0.56, 0.58, 0.62)},
}

# Body regions by profile bone name.
REGIONS: dict[str, tuple[str, ...]] = {
    "hips": ("Hips",),
    "waist": ("Spine",),
    "chest": ("Chest",),
    "upper_chest": ("UpperChest",),
    "shoulder": ("LeftShoulder", "RightShoulder"),
    "upper_arm": ("LeftUpperArm", "RightUpperArm"),
    "forearm": ("LeftLowerArm", "RightLowerArm"),
    "thigh": ("LeftUpperLeg", "RightUpperLeg"),
    "shin": ("LeftLowerLeg", "RightLowerLeg"),
    "neck": ("Neck",),
}
# The bones the issue lengthens; nothing else may grow along its length (hands and feet are never stretched).
LENGTHENED = ("upper_arm", "forearm", "thigh", "shin", "neck")
SOFTEN_REGIONS = ("hips", "waist", "chest", "upper_chest", "shoulder", "neck")  # the trunk: normal-only smoothing
TUBE_REGIONS = ("upper_arm", "forearm", "thigh", "shin", "neck")  # limbs: a smooth radius profile along the bone
TRUNK = ("Hips", "Spine", "Chest", "UpperChest")  # the trunk's smooth surface runs from the hips to the neck
# Each lengthened or smoothed bone's next joint along the limb (the end of its axis).
NEXT = {"LeftUpperArm": "LeftLowerArm", "LeftLowerArm": "LeftHand", "RightUpperArm": "RightLowerArm",
        "RightLowerArm": "RightHand", "LeftUpperLeg": "LeftLowerLeg", "LeftLowerLeg": "LeftFoot",
        "RightUpperLeg": "RightLowerLeg", "RightLowerLeg": "RightFoot", "Neck": "Head"}
FINGERS = ("Thumb", "Index", "Middle", "Ring", "Little")
# The joints whose edge loops the smoothing and the decimation protect: each named bone's head is the joint.
JOINTS = {"shoulder": ("LeftUpperArm", "RightUpperArm"), "elbow": ("LeftLowerArm", "RightLowerArm"),
          "hip": ("LeftUpperLeg", "RightUpperLeg"), "knee": ("LeftLowerLeg", "RightLowerLeg")}

# The restyled head (all lengths are fractions of the head's own height, chin to crown, so they hold at any size).
GROIN = (0.07, 40)  # the radius (m) and the plain Laplacian passes that flatten the source's bulge at the groin
NECK_UPRIGHT = 1.0  # the source's neck leans forward about 17 degrees; the look target's stands upright

HEAD = {
    "egg_strength": 1.0,      # how far the cranium and face move onto the egg (1: all the way)
    "egg_width": 1.0,         # the egg's half width at the temples against the source cranium's
    "egg_depth": 0.97,        # the egg's half depth at the brow against the source cranium's (nose excluded)
    "egg_jaw": 0.35,          # how far the egg's lower end leans forward, as a fraction of its half depth
    "ear_smooth": 8,          # plain Laplacian passes that round the ears off (they lose their folds)
    "ear_keep": 0.85,         # how much of the ears' height above the egg stays
    "cut_front": 0.0,         # the egg ends at this height above the chin at the front (fraction of its height)
    "cut_back": 0.16,         # and at this height at the back, where the skull meets the neck
    "egg_relax": 25,          # passes that even out the vertices on the egg (each smooths, then projects)
    "seam_smooth": 300,       # Laplacian passes that span a membrane from the egg down to the neck
    "nose_root": 0.4,         # the nose's root height above the chin (the mannequin's: just under the eyes)
    "nose_droop": 0.2,        # the nose points forward and this much down (the mannequin's)
    "nose_root_radius": (0.07, 0.11),  # half width and half height of the nose's root: a tall, narrow bridge
    "nose_tip_radius": 0.035, # the tip's radius
}

PRESETS: dict[str, dict[str, Any]] = {
    # The restyled base: soft, slightly lanky (longer limbs and a long thin neck, narrow shoulders), a head 12.5
    # percent bigger than the source's at the same height, and a long cone nose.
    "base": {
        "scale": {  # region -> (across the bone, along the bone)
            "hips": (0.94, 1.0), "waist": (0.88, 1.0), "chest": (0.85, 1.0), "upper_chest": (0.82, 1.0),
            "shoulder": (0.82, 0.86), "upper_arm": (0.8, 1.08), "forearm": (0.76, 1.1), "thigh": (0.8, 1.1),
            "shin": (0.8, 1.12), "neck": (0.78, 1.5),
        },
        "head": 1.125, "nose": 0.42, "soften": 120, "tube": 0.8,
    },
    # Lankier than base: thinner, the legs, arms and neck 9 to 17 percent longer than base's before the figure is
    # scaled back to 1.75 m (about 5 percent longer for its height), a head 10 percent bigger than the source's.
    "lanky": {
        "scale": {
            "hips": (0.92, 1.0), "waist": (0.84, 1.0), "chest": (0.8, 1.0), "upper_chest": (0.78, 1.0),
            "shoulder": (0.78, 0.82), "upper_arm": (0.7, 1.2), "forearm": (0.68, 1.22), "thigh": (0.7, 1.22),
            "shin": (0.7, 1.24), "neck": (0.7, 1.75),
        },
        "head": 1.1, "nose": 0.45, "soften": 120, "tube": 0.85,
    },
    # Base's body with a head 25 percent bigger than the source's and a shorter neck: the most cartoony.
    "bighead": {
        "scale": {
            "hips": (0.94, 1.0), "waist": (0.88, 1.0), "chest": (0.85, 1.0), "upper_chest": (0.82, 1.0),
            "shoulder": (0.82, 0.86), "upper_arm": (0.8, 1.08), "forearm": (0.76, 1.1), "thigh": (0.8, 1.1),
            "shin": (0.8, 1.12), "neck": (0.8, 1.3),
        },
        "head": 1.25, "nose": 0.42, "soften": 120, "tube": 0.8,
    },
}

# The face bones the Quaternius rig lacks; added under the head bone, unweighted, with the profile's names.
FACE_BONES = ("Jaw", "LeftEye", "RightEye")

# Gates the restyled body must pass (stylize-quaternius fails otherwise).
EYE_HEIGHT = (1.55, 1.65)        # the contract wants 1.6 +- 0.08; the restyle aims nearer
HEAD_RATIO_TOLERANCE = 0.02      # the measured head size within this of the preset's
MIN_PRESET_SHIFT = 0.0105  # a preset's median per-vertex distance from base (m): three times batch 2's 3.5 mm
FINGER_ISLANDS = 5


def default_source() -> Path:
    return common.raw_dir().joinpath(*SOURCE_PARTS)


def default_out() -> Path:
    return common.raw_dir() / "restyled"


def default_references() -> dict[str, Path]:
    """The look target and the batch 2 donor, for the 20 m line-up."""
    raw = common.raw_dir()
    return {"mannequin-lanky": raw / "mannequin" / "lanky" / "mannequin_lanky.glb",
            "quaternius-base": raw / "stylized" / "base" / "quaternius_base.glb"}


def source_names(bone_map: dict[str, Any]) -> dict[str, str]:
    """Profile name -> the rig's own name, from the map."""
    return {target: source for source, target in bone_map["rename"].items()}


def unexpected_failures(report: dict[str, Any]) -> list[str]:
    """The failed checks of a `check` report as 'check: detail' lines; empty when nothing failed."""
    return [f"{r.get('check')}: {r.get('detail', '')}" for r in report.get("results", []) if r.get("status") == "fail"]


def glb_meshes(path: Path) -> list[str]:
    """The names of the nodes that carry a mesh in a GLB, read from its JSON chunk (no Blender): the export check."""
    data = path.read_bytes()
    if data[:4] != b"glTF":
        raise common.Failure(f"{path} is not a GLB")
    length, kind = struct.unpack("<I4s", data[12:20])
    if kind != b"JSON":
        raise common.Failure(f"{path} has no JSON chunk first")
    document = json.loads(data[20 : 20 + length])
    return sorted(node.get("name", "") for node in document.get("nodes", []) if "mesh" in node)


def stray_meshes(names: list[str], allowed: tuple[str, ...] = ALLOWED_MESHES) -> list[str]:
    return [name for name in names if name not in allowed]


def tubes(names: dict[str, str], strength: float) -> list[dict[str, Any]]:
    """The smooth parts of step 2, in the rig's names: the trunk from the hips' joint to the neck's (fitted between
    just above the hips and the armpits, faded out over the shoulders), then every limb bone and the neck from its
    joint to the next (faded out at both joints)."""
    parts = [{"name": "trunk", "weights": [names[b] for b in TRUNK], "start": names["Hips"], "end": names["Neck"],
              "fit": [0.0, 0.82], "fade": [-0.12, 0.03, 0.8, 0.97], "strength": min(1.0, strength + 0.1),
              "degree": 2}]
    for region in TUBE_REGIONS:
        for bone in REGIONS[region]:
            parts.append({"name": bone, "weights": [names[bone]], "start": names[bone], "end": names[NEXT[bone]],
                          "fit": [0.1, 0.9], "fade": [-0.02, 0.06, 0.94, 1.02], "strength": strength,
                          "degree": 1})
    return parts


def plan(preset: str, source: Path, out: Path, bone_map: dict[str, Any] | None = None,
         target_triangles: int = TARGET_TRIANGLES, base_positions: Path | None = None) -> dict[str, Any]:
    """Everything stylize_quaternius.py needs for one preset, with the rig's own bone names; out is the preset's
    folder; base_positions is base's normalized skin, to measure a preset against."""
    if preset not in PRESETS:
        raise common.Failure(f"no preset {preset!r}; the presets are {', '.join(PRESETS)}")
    settings = PRESETS[preset]
    names = source_names(bone_map or _contract.load_map("quaternius"))

    def rig(profile_names: tuple[str, ...]) -> list[str]:
        return [names[n] for n in profile_names]

    scale = {bone: list(settings["scale"][region]) for region in REGIONS for bone in rig(REGIONS[region])}
    fingers = {side: {finger: rig(tuple(f"{side}{finger}{joint}" for joint in
                                        (("Metacarpal", "Proximal", "Distal") if finger == "Thumb"
                                         else ("Proximal", "Intermediate", "Distal"))))
                      for finger in FINGERS} for side in ("Left", "Right")}
    build = out / "build"
    return {
        "preset": preset,
        "source": source.as_posix(),
        "stage_blend": (build / f"stage_{preset}.blend").as_posix(),
        "info": (build / "build.json").as_posix(),
        "positions": (build / "normalized.npy").as_posix(),
        "base_positions": base_positions.as_posix() if base_positions and preset != "base" else None,
        "drop_objects": list(DROP_OBJECTS),
        "body_name": BODY,
        "height": HEIGHT,
        "target_triangles": target_triangles,
        "scale": scale,
        "head_bone": names["Head"],
        "neck_bone": names["Neck"],
        "head_ratio": settings["head"],
        "head": dict(HEAD, nose_length=settings["nose"]),
        "soften_bones": [b for region in SOFTEN_REGIONS for b in rig(REGIONS[region])],
        "soften_iterations": settings["soften"],
        "tubes": tubes(names, settings["tube"]),
        "neck_upright": NECK_UPRIGHT,
        "groin_radius": GROIN[0],
        "groin_smooth": GROIN[1],
        "hand_bones": rig(("LeftHand", "RightHand")),
        "foot_bones": rig(("LeftFoot", "RightFoot", "LeftToes", "RightToes")),
        "fingers": fingers,
        "joints": {joint: rig(bones) for joint, bones in JOINTS.items()},
        "hips_bone": names["Hips"],
        "legs": rig(("LeftUpperLeg", "RightUpperLeg")),
        "palette": {"cells": PALETTE_CELLS, "cell_px": PALETTE_CELL_PX,
                    "colours": {k: {"cell": v["cell"], "srgb": list(v["srgb"])} for k, v in PALETTE.items()}},
        "face_bones": list(FACE_BONES),
    }


# What each preset must change against base, in the finished figures (as fractions of the height): lanky's limbs
# and neck longer, bighead's head bigger.
LANKY_BONES = ("Neck", "LeftUpperArm", "LeftLowerArm", "LeftUpperLeg", "LeftLowerLeg")
MIN_LANKY_GAIN = 1.03
MIN_BIGHEAD_GAIN = 1.07


def preset_differences(info: dict[str, Any]) -> list[str]:
    """The ways a preset fails to differ from base as it should (needs base's measurements in info["base_measure"])."""
    mine, base = info.get("measure", {}), info.get("base_measure")
    if not base or not mine:
        return []
    found = []
    if info["preset"] == "lanky":
        for bone in LANKY_BONES:
            gain = mine["bone_lengths_per_height"][bone] / base["bone_lengths_per_height"][bone]
            if gain < MIN_LANKY_GAIN:
                found.append(f"{bone} only {gain:.3f} x base's length (at least {MIN_LANKY_GAIN} wanted)")
    if info["preset"] == "bighead":
        gain = mine["head_ratio"] / base["head_ratio"]
        if gain < MIN_BIGHEAD_GAIN:
            found.append(f"the head only {gain:.3f} x base's (at least {MIN_BIGHEAD_GAIN} wanted)")
    return found


def gate_failures(info: dict[str, Any]) -> list[str]:
    """Every gate of the issue that the finished preset fails (info.json after the gates), as readable lines."""
    found = [f"check: {line}" for line in unexpected_failures(info.get("check", {}))]
    measure, defects = info.get("measure", {}), info.get("defects", {})
    if measure:
        if measure["meshes"] != list(ALLOWED_MESHES):
            found.append(f"meshes {measure['meshes']}, wanted {list(ALLOWED_MESHES)}")
        if len(measure["materials"]) != 1:
            found.append(f"materials {measure['materials']}: one palette material wanted")
        if abs(measure["height"] - HEIGHT) > 0.002 or abs(measure["lowest"]) > 0.002:
            found.append(f"height {measure['height']} m with the lowest point at {measure['lowest']} m")
        if max(abs(v) for v in measure["soles_centre"]) > 0.01:
            found.append(f"the soles are centred at {measure['soles_centre']}, not on the origin")
        eye = measure.get("eye_height")
        if eye is None or not EYE_HEIGHT[0] <= eye <= EYE_HEIGHT[1]:
            found.append(f"eyes at {eye} m, outside {EYE_HEIGHT[0]} to {EYE_HEIGHT[1]} m")
        wanted = info["source_head_ratio"] * info["head_ratio_target"]
        ratio = measure.get("head_ratio")
        if ratio is None or abs(ratio / wanted - 1.0) > HEAD_RATIO_TOLERANCE:
            found.append(f"head {ratio} of the height, wanted {wanted:.4f} ({info['head_ratio_target']} x the source)")
        if measure["triangles"] > info.get("target_triangles", TARGET_TRIANGLES) * 1.1:
            found.append(f"{measure['triangles']} triangles, about {TARGET_TRIANGLES} wanted")
    shift = info.get("shift_from_base")
    if info.get("preset") != "base":
        if not shift or "median" not in shift:
            found.append("not measured against base (build base first)")
        elif shift["median"] < MIN_PRESET_SHIFT:
            found.append(f"only {shift['median'] * 1000:.1f} mm (median) from base: the preset changes too little")
        found += preset_differences(info)
    if defects:
        for side, hand in defects["hands"].items():
            if not hand["five_separate"]:
                found.append(f"the {side} hand's fingers are not {FINGER_ISLANDS} separate parts: "
                             f"{hand['fingers_per_island']}")
        for key in ("open_edges", "non_manifold_edges"):
            if defects[key]:
                found.append(f"{defects[key]} {key.replace('_', ' ')}")
    return found
