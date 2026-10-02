"""Shared by the contract scripts in headless Blender (check_model.py, rename_bones.py, make_contract_fixture.py):
reading a script's arguments, loading a model into an empty scene, saving it, and converting Blender coordinates to
glTF's (the contract's) space.

Blender is Z-up with the front at -Y; glTF and the contract are Y-up with the front at +Z. A Blender point (x, y, z)
is the glTF point (x, z, -y).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy

LOADABLE = (".glb", ".gltf", ".fbx", ".obj", ".blend")
SAVABLE = (".glb", ".gltf", ".blend")


def script_args() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def read_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str, data: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def empty_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def load_model(path: str) -> None:
    """Opens a .blend, or imports a .glb, .gltf, .fbx or .obj into an empty scene."""
    suffix = Path(path).suffix.lower()
    if suffix not in LOADABLE:
        raise SystemExit(f"cannot load {path}: the formats are {', '.join(LOADABLE)}")
    if not Path(path).is_file():
        raise SystemExit(f"no such file: {path}")
    if suffix == ".blend":
        bpy.ops.wm.open_mainfile(filepath=path)
        return
    empty_scene()
    if suffix in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif suffix == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    else:
        bpy.ops.wm.obj_import(filepath=path)


def save_model(path: str) -> None:
    """Saves the scene as .blend, or exports it as .glb or .gltf (Y-up, every bone, the skin, UVs, materials)."""
    suffix = Path(path).suffix.lower()
    if suffix not in SAVABLE:
        raise SystemExit(f"cannot save {path}: the formats are {', '.join(SAVABLE)}")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if suffix == ".blend":
        bpy.ops.wm.save_as_mainfile(filepath=path, check_existing=False)
    else:
        bpy.ops.export_scene.gltf(
            filepath=path,
            export_format="GLB" if suffix == ".glb" else "GLTF_SEPARATE",
            export_yup=True,
            export_apply=False,
        )


def to_gltf(v) -> list[float]:
    """A Blender-space point or direction as a glTF-space [x, y, z]."""
    return [float(v[0]), float(v[2]), -float(v[1])]
