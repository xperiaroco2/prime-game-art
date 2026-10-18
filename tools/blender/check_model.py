"""Measures a model in headless Blender for `tools/run.py check`: mesh counts and topology, UVs, transforms, bounds,
bones, skin weights and the bones that carry the vertices each shape key moves, and how far. It only measures; the
runner (tools/runner/commands/_checks.py) judges the numbers against contract/contract.toml and writes report.json.

    blender -b --factory-startup --python check_model.py -- <model> <params.json> <measure.json>

params.json: {"min_weight", "weight_sum_tolerance", "max_weights", "weld_distance", "small_island_faces",
"morph_epsilon"}.
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

# Weights closer than this are equal: a vertex at 0.5 Head and 0.5 Neck is on both. glTF may store weights in 8 bits:
# two equal weights can come back one step (1/255) apart, one more after the exporter renormalises the sum to 1.
TIE = 2 / 255


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
    result["shape_key_bones"] = measure_shape_keys(obj, params)
    return result


def armature_bones(obj) -> set[str]:
    """The names of the bones that can deform obj: its armature modifiers' and its armature parent's."""
    bones: set[str] = set()
    for modifier in obj.modifiers:
        if modifier.type == "ARMATURE" and modifier.object:
            bones |= {b.name for b in modifier.object.data.bones}
    if obj.parent and obj.parent.type == "ARMATURE":
        bones |= {b.name for b in obj.parent.data.bones}
    return bones


def main_bones(vertex, names: dict[int, str], bones: set[str]) -> str:
    """The bone with the vertex's largest weight, counting only vertex groups that are armature bones (a clay
    `.blend`'s `clay_border` group is not); bones tied for it (within TIE) are joined by "|" in name order, so the
    runner can settle a tie in the head bones' favour; "" for a vertex on no bone."""
    weights = [(g.weight, names[g.group]) for g in vertex.groups if g.weight > 0 and names.get(g.group) in bones]
    if not weights:
        return ""
    top = max(w for w, _ in weights)
    return "|".join(sorted(name for w, name in weights if top - w <= TIE))


def measure_shape_keys(obj, params: dict) -> dict:
    """Per shape key, the vertices it moves (farther than morph_epsilon from its relative key), grouped by their main
    bones (main_bones): per group the vertex count and the largest move in mm. The runner tells face morphs (skin on
    the head bones) from body-shape morphs by it."""
    me = obj.data
    if not me.shape_keys:
        return {}
    names = {g.index: g.name for g in obj.vertex_groups}
    bones = armature_bones(obj)
    main = [main_bones(vertex, names, bones) for vertex in me.vertices]
    epsilon = params["morph_epsilon"]
    result: dict[str, dict[str, dict]] = {}
    for key in me.shape_keys.key_blocks[1:]:
        base = key.relative_key
        moves: dict[str, dict] = {}
        for index, (moved, rest) in enumerate(zip(key.data, base.data)):
            distance = (moved.co - rest.co).length
            if distance > epsilon:
                entry = moves.setdefault(main[index], {"vertices": 0, "max_mm": 0.0})
                entry["vertices"] += 1
                entry["max_mm"] = max(entry["max_mm"], round(distance * 1000, 3))
        result[key.name] = dict(sorted(moves.items()))
    return result


def measure_weights(obj, params: dict) -> dict:
    bones = armature_bones(obj)
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
    # The glTF importer adds a bone display shape ("Icosphere") in a glTF_not_exported collection: not the model.
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
