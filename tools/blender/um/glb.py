"""The table of contents of a pack GLB, read from its JSON chunk with the standard library (no Blender): mesh objects
with their materials, and the animations. Used to validate recipes before anything is imported."""

from __future__ import annotations

import json
import re
import struct
from functools import lru_cache
from pathlib import Path

GLB_MAGIC = b"glTF"
JSON_CHUNK = 0x4E4F534A
# Every pack file carries a stray 80-triangle Icosphere; it is never a part.
STRAY_OBJECTS = frozenset({"Icosphere"})
# The pack's animations are named "CharacterArmature|<action>"; Blender's importer keeps that name for the action.
ACTION_PREFIX = "CharacterArmature|"


def base_name(name: str) -> str:
    """A Blender name without its ".001" duplicate suffix."""
    return re.sub(r"\.\d{3}$", "", name)


class GlbError(Exception):
    pass


@lru_cache(maxsize=64)
def _read(path: str, mtime: float) -> dict:
    data = Path(path).read_bytes()
    if len(data) < 20 or data[:4] != GLB_MAGIC:
        raise GlbError(f"{path} is not a GLB file")
    length, kind = struct.unpack("<II", data[12:20])
    if kind != JSON_CHUNK:
        raise GlbError(f"{path}: the first chunk is not JSON")
    return json.loads(data[20 : 20 + length])


def contents(path: Path) -> dict:
    """{"objects": {node name: [material base names]}, "actions": [action names without the prefix]} of a GLB.
    Objects are the nodes that carry a mesh (the importer names each mesh object after its node), minus the stray
    Icosphere."""
    gltf = _read(str(path), path.stat().st_mtime)
    materials = [base_name(m.get("name", "")) for m in gltf.get("materials", [])]
    objects: dict[str, list[str]] = {}
    for node in gltf.get("nodes", []):
        if "mesh" not in node or not node.get("name") or node["name"] in STRAY_OBJECTS:
            continue
        mesh = gltf["meshes"][node["mesh"]]
        names: list[str] = []
        for prim in mesh.get("primitives", []):
            index = prim.get("material")
            if index is not None and materials[index] not in names:
                names.append(materials[index])
        objects[node["name"]] = names
    actions = [a.get("name", "") for a in gltf.get("animations", [])]
    actions = [a[len(ACTION_PREFIX) :] if a.startswith(ACTION_PREFIX) else a for a in actions]
    return {"objects": objects, "actions": actions}
