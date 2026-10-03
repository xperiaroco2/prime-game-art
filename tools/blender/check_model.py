"""Measures a model in headless Blender for `tools/run.py check`: mesh counts and topology, UVs, transforms, bounds,
bones and skin weights. It only measures; the runner (tools/runner/commands/_checks.py) judges the numbers against
contract/contract.toml and writes report.json.

    blender -b --factory-startup --python check_model.py -- <model> <params.json> <measure.json>

params.json: {"min_weight", "weight_sum_tolerance", "max_weights", "weld_distance", "small_island_faces"}.
Every position in measure.json is in glTF space (Y up, front +Z, metres), the contract's space.
"""

from __future__ import annotations

import math
import os
import sys

import bmesh
import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import contract_io  # noqa: E402


def transform_of(obj) -> dict:
    loc, rot, scale = obj.matrix_world.decompose()
    return {
        "location": [round(c, 6) for c in contract_io.to_gltf(loc)],
        "rotation_deg": round(math.degrees(rot.angle), 4),
        "scale": [round(c, 6) for c in scale],
    }


def islands(bm: bmesh.types.BMesh) -> list[int]:
    """Face counts of the connected parts (faces joined by shared edges)."""
    seen: set[int] = set()
    sizes: list[int] = []
    for face in bm.faces:
        if face.index in seen:
            continue
        stack, size = [face], 0
        seen.add(face.index)
        while stack:
            current = stack.pop()
            size += 1
            for edge in current.edges:
                for other in edge.link_faces:
                    if other.index not in seen:
                        seen.add(other.index)
                        stack.append(other)
        sizes.append(size)
    return sizes


def measure_mesh(obj, params: dict) -> dict:
    me = obj.data
    world = obj.matrix_world
    points = [contract_io.to_gltf(world @ v.co) for v in me.vertices]
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=params["weld_distance"])
    bm.faces.ensure_lookup_table()
    bm.faces.index_update()
    parts = islands(bm)
    uv_out = 0
    if me.uv_layers:
        for loop_uv in me.uv_layers[0].data:
            u, v = loop_uv.uv
            if not (-0.001 <= u <= 1.001 and -0.001 <= v <= 1.001):
                uv_out += 1
    used_materials = {p.material_index for p in me.polygons}
    result = {
        "name": obj.name,
        "vertices": len(me.vertices),
        "triangles": sum(len(p.vertices) - 2 for p in me.polygons),
        "faces": len(me.polygons),
        "ngons": sum(1 for p in me.polygons if len(p.vertices) > 4),
        "loose_vertices": sum(1 for v in bm.verts if not v.link_edges),
        "loose_edges": sum(1 for e in bm.edges if not e.link_faces),
        "non_manifold_edges": sum(1 for e in bm.edges if len(e.link_faces) > 2),
        "boundary_edges": sum(1 for e in bm.edges if len(e.link_faces) == 1),
        "islands": len(parts),
        "small_islands": sum(1 for size in parts if size < params["small_island_faces"]),
        "uv_layers": len(me.uv_layers),
        "uv_loops_out_of_range": uv_out,
        "materials": len(used_materials),
        "shape_keys": len(me.shape_keys.key_blocks) - 1 if me.shape_keys else 0,
        "modifiers": [m.type for m in obj.modifiers if m.type != "ARMATURE"],
        "skinned": any(m.type == "ARMATURE" for m in obj.modifiers),
        "transform": transform_of(obj),
        "min": [min(p[i] for p in points) for i in range(3)] if points else [0.0, 0.0, 0.0],
        "max": [max(p[i] for p in points) for i in range(3)] if points else [0.0, 0.0, 0.0],
    }
    bm.free()
    result["weights"] = measure_weights(obj, params)
    return result


def measure_weights(obj, params: dict) -> dict:
    bones: set[str] = set()
    for modifier in obj.modifiers:
        if modifier.type == "ARMATURE" and modifier.object:
            bones |= {b.name for b in modifier.object.data.bones}
    if obj.parent and obj.parent.type == "ARMATURE":
        bones |= {b.name for b in obj.parent.data.bones}
    names = {g.index: g.name for g in obj.vertex_groups}
    weighted: dict[str, int] = {}
    max_influences = over = unweighted = below = unnormalized = 0
    for vertex in obj.data.vertices:
        influences = [(names[g.group], g.weight) for g in vertex.groups if g.weight > 0 and names.get(g.group) in bones]
        count = len(influences)
        max_influences = max(max_influences, count)
        if count > params["max_weights"]:
            over += 1
        if count == 0:
            unweighted += 1
            continue
        if any(w < params["min_weight"] for _, w in influences):
            below += 1
        if abs(sum(w for _, w in influences) - 1.0) > params["weight_sum_tolerance"]:
            unnormalized += 1
        for name, _ in influences:
            weighted[name] = weighted.get(name, 0) + 1
    return {
        "groups": len(names),
        "groups_without_bone": sorted(n for n in names.values() if n not in bones),
        "max_influences": max_influences,
        "vertices_over_limit": over,
        "unweighted_vertices": unweighted,
        "vertices_below_min_weight": below,
        "vertices_not_normalized": unnormalized,
        "weighted_bones": dict(sorted(weighted.items())),
    }


def measure_armature(obj) -> dict:
    world = obj.matrix_world
    return {
        "name": obj.name,
        "transform": transform_of(obj),
        "bones": [
            {
                "name": bone.name,
                "parent": bone.parent.name if bone.parent else "",
                "head": [round(c, 6) for c in contract_io.to_gltf(world @ bone.head_local)],
                "tail": [round(c, 6) for c in contract_io.to_gltf(world @ bone.tail_local)],
                "deform": bone.use_deform,
            }
            for bone in obj.data.bones
        ],
    }


def main() -> None:
    model, params_path, out = contract_io.script_args()
    params = contract_io.read_json(params_path)
    contract_io.load_model(model)
    armatures = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    for arm in armatures:
        arm.data.pose_position = "REST"
    bpy.context.view_layer.update()
    # A glTF imported without disable_bone_shape (a .blend saved elsewhere) holds the importer's bone display shape
    # ("Icosphere") in a glTF_not_exported collection: not the model.
    shapes = {pb.custom_shape for a in armatures for pb in a.pose.bones if pb.custom_shape}
    ignored = [
        o
        for o in bpy.context.scene.objects
        if o in shapes or any(c.name.startswith("glTF_not_exported") for c in o.users_collection)
    ]
    meshes = [measure_mesh(o, params) for o in bpy.context.scene.objects if o.type == "MESH" and o not in ignored]
    others = sorted({o.type for o in bpy.context.scene.objects if o not in ignored} - {"MESH", "ARMATURE", "EMPTY"})
    contract_io.write_json(
        out,
        {
            "model": model,
            "space": "glTF: Y up, front +Z, metres",
            "blender": bpy.app.version_string,
            "meshes": meshes,
            "armatures": [measure_armature(a) for a in armatures],
            "empties": sorted(o.name for o in bpy.context.scene.objects if o.type == "EMPTY"),
            "other_objects": others,
            "ignored_objects": sorted(o.name for o in ignored),
        },
    )
    print(f"check_model: measured {len(meshes)} meshes and {len(armatures)} armatures in {model}")


if __name__ == "__main__":
    main()
