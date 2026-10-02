"""Renames a rig's bones to the contract's profile names in headless Blender, for `tools/run.py rename-bones`.

    blender -b --factory-startup --python rename_bones.py -- <model> <plan.json> <out> <summary.json>

plan.json (written by the runner from contract/bone_maps/<name>.toml): {"map", "prefix_pattern", "rename", "drop",
"profile_bones"}. Renaming a bone through Blender's data API also renames the vertex groups of the meshes it deforms,
so the skin follows. Bones in "drop" are deleted only when no vertex carries a weight for them (their children move
to their parent); weighted ones are kept and reported. The model is saved as <out> (.glb, .gltf or .blend).
"""

from __future__ import annotations

import os
import re
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import contract_io  # noqa: E402


def weighted_groups(rig) -> set[str]:
    names: set[str] = set()
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or not any(m.type == "ARMATURE" and m.object == rig for m in obj.modifiers):
            continue
        index = {g.index: g.name for g in obj.vertex_groups}
        for vertex in obj.data.vertices:
            names |= {index[g.group] for g in vertex.groups if g.weight > 0}
    return names


def main() -> None:
    model, plan_path, out, summary_path = contract_io.script_args()
    plan = contract_io.read_json(plan_path)
    pattern = re.compile(plan["prefix_pattern"]) if plan["prefix_pattern"] else None
    contract_io.load_model(model)
    rigs = [o for o in bpy.context.scene.objects if o.type == "ARMATURE" and o.data.bones]
    if len(rigs) != 1:
        raise SystemExit(f"rename_bones: expected one armature with bones, found {len(rigs)}")
    rig = rigs[0]

    def stripped(name: str) -> str:
        return pattern.sub("", name, count=1) if pattern else name

    weighted = weighted_groups(rig)
    to_drop = [b.name for b in rig.data.bones if stripped(b.name) in plan["drop"] and b.name not in weighted]
    kept = sorted(b.name for b in rig.data.bones if stripped(b.name) in plan["drop"] and b.name in weighted)
    if to_drop:
        bpy.context.view_layer.objects.active = rig
        bpy.ops.object.mode_set(mode="EDIT")
        edit_bones = rig.data.edit_bones
        for name in to_drop:
            bone = edit_bones[name]
            for child in list(bone.children):
                child.parent = bone.parent
            edit_bones.remove(bone)
        bpy.ops.object.mode_set(mode="OBJECT")

    # Two passes, so a rename never collides with a name that is about to change.
    targets = {b.name: plan["rename"].get(stripped(b.name), stripped(b.name)) for b in rig.data.bones}
    changes = {old: new for old, new in targets.items() if old != new}
    for index, old in enumerate(changes):
        rig.data.bones[old].name = f"__rename_{index}__"
    for index, (old, new) in enumerate(changes.items()):
        rig.data.bones[f"__rename_{index}__"].name = new
    final = [b.name for b in rig.data.bones]
    contract_io.save_model(out)
    contract_io.write_json(
        summary_path,
        {
            "model": model,
            "out": out,
            "map": plan["map"],
            "renamed": dict(sorted(changes.items())),
            "dropped": sorted(to_drop),
            "kept_weighted_drop_bones": kept,
            "not_in_profile": sorted(n for n in final if n not in plan["profile_bones"]),
            "missing_from_profile": [n for n in plan["profile_bones"] if n not in final],
        },
    )
    print(f"rename_bones: renamed {len(changes)}, dropped {len(to_drop)}, wrote {out}")


if __name__ == "__main__":
    main()
