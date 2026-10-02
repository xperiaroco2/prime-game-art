"""The plan for `stylize-quaternius`: presets and the per-bone parameters tools/blender/stylize_quaternius.py applies.
Pure Python, so every number has a test without Blender. Bones are found by their contract (profile) names through
the Quaternius bone map, so the Blender script never hard-codes a vendor name.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import common
from . import _contract

SOURCE_PARTS = ("quaternius", "Universal_Base_Characters", "Universal Base Characters[Standard]", "Base Characters",
                "Godot - UE", "Superhero_Male_FullBody.gltf")

# Helper and face meshes the source carries: the glTF importer's bone shape, the eyes and the eyebrows (a blank face:
# eyes and mouth are changeable slots later).
DROP_OBJECTS = ("Icosphere", "Eyes", "Eyebrows")

HEIGHT = 1.75
TARGET_TRIANGLES = 7500  # within the issue's 7,000 to 9,000 and under the contract's body cap of 8,000

# Flat colours (sRGB); the shared palette replaces them later.
SKIN = (0.87, 0.64, 0.49)
SHORTS = (0.36, 0.32, 0.27)

# Body regions by profile bone name. "slim" scales a region across its bones (the bone's length stays), "soften"
# smooths it.
REGIONS: dict[str, tuple[str, ...]] = {
    "torso": ("Hips", "Spine", "Chest", "UpperChest"),
    "shoulder": ("LeftShoulder", "RightShoulder"),
    "arm": ("LeftUpperArm", "LeftLowerArm", "RightUpperArm", "RightLowerArm"),
    "leg": ("LeftUpperLeg", "LeftLowerLeg", "RightUpperLeg", "RightLowerLeg"),
    "neck": ("Neck",),
}
SOFTEN_REGIONS = ("torso", "shoulder", "arm", "leg", "neck")
FINGERS = ("Thumb", "Index", "Middle", "Ring", "Little")

PRESETS: dict[str, dict[str, Any]] = {
    # The issue's middle: 17 percent slimmer, a 12 percent bigger head, a nose 3 cm longer.
    "base": {
        "slim": {"torso": 0.83, "shoulder": 0.85, "arm": 0.83, "leg": 0.84, "neck": 0.9},
        "head": 1.12, "nose": 0.03, "soften": 12,
    },
    # Lankier: 20 percent slimmer limbs and torso, a slightly smaller head growth, a longer nose.
    "lanky": {
        "slim": {"torso": 0.8, "shoulder": 0.82, "arm": 0.8, "leg": 0.8, "neck": 0.85},
        "head": 1.1, "nose": 0.036, "soften": 14,
    },
    # The most cartoony: 15 percent slimmer, a 15 percent bigger head and the longest nose.
    "bighead": {
        "slim": {"torso": 0.85, "shoulder": 0.87, "arm": 0.85, "leg": 0.85, "neck": 0.9},
        "head": 1.15, "nose": 0.045, "soften": 12,
    },
}


def default_source() -> Path:
    return common.raw_dir().joinpath(*SOURCE_PARTS)


def default_out() -> Path:
    return common.raw_dir() / "stylized"


def source_names(bone_map: dict[str, Any]) -> dict[str, str]:
    """Profile name -> the rig's own name, from the map."""
    return {target: source for source, target in bone_map["rename"].items()}


def plan(preset: str, source: Path, out_glb: Path, info: Path, bone_map: dict[str, Any] | None = None,
         target_triangles: int = TARGET_TRIANGLES) -> dict[str, Any]:
    """Everything stylize_quaternius.py needs for one preset, with the rig's own bone names."""
    if preset not in PRESETS:
        raise common.Failure(f"no preset {preset!r}; the presets are {', '.join(PRESETS)}")
    settings = PRESETS[preset]
    names = source_names(bone_map or _contract.load_map("quaternius"))
    slim = {names[bone]: factor for region, factor in settings["slim"].items() for bone in REGIONS[region]}
    soften = [names[bone] for region in SOFTEN_REGIONS for bone in REGIONS[region]]
    probe = {f"{side}{finger}Proximal": names[f"{side}{finger}Proximal"] for side in ("Left", "Right")
             for finger in FINGERS}
    probe.update({bone: names[bone] for bone in ("Head", "LeftLowerArm", "RightLowerLeg")})
    return {
        "preset": preset,
        "source": source.as_posix(),
        "out_glb": out_glb.as_posix(),
        "info": info.as_posix(),
        "drop_objects": list(DROP_OBJECTS),
        "slim": slim,
        "head_bone": names["Head"],
        "head_scale": settings["head"],
        "nose_length": settings["nose"],
        "soften_bones": soften,
        "soften_iterations": settings["soften"],
        "height": HEIGHT,
        "target_triangles": target_triangles,
        "probe_bones": probe,
        "skin": list(SKIN),
        "shorts": list(SHORTS),
    }
