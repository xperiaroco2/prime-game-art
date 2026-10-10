"""Builds every prop of props/tasks.toml as its own GLB (art #82, docs/props.md). The runner calls it
(tools/run.py props); by hand, background only:

  blender -b --factory-startup --python-exit-code 1 --python tools/blender/props_task_build.py -- \
      --spec props/tasks.toml --out D:/prime-art-raw/props/task/v1 --ambientcg D:/prime-art-raw/env/ambientcg [--only id,...]

The geometry comes from props_task.py (pure Python); the objects, detail textures, materials and the export are the
kit's (kit_build.py), so a prop shares the kit's materials and paint encoding. The game surface's material is
named `surface_game-vcol` (Godot imports it as `surface_game`). Writes <out>/<id>.glb, <out>/textures/ and
<out>/build.json.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit_build  # noqa: E402
import props_task  # noqa: E402


def main():
    import bmesh
    import bpy
    import numpy as np

    a = kit_build.args()
    spec = props_task.load_spec(Path(a["spec"]))
    out = Path(a["out"])
    out.mkdir(parents=True, exist_ok=True)
    only = {s for s in a["only"].split(",") if s}
    kit_build.clear_scene(bpy)
    textures = kit_build.make_textures(bpy, np, spec, Path(a["ambientcg"]), out / "textures")
    mats = kit_build.make_materials(bpy, spec, textures)
    mats[props_task.SURFACE_MATERIAL].name = f"{props_task.SURFACE_MATERIAL}-vcol"
    for name, m in spec["materials"].items():  # an emissive material (props/zones.toml: bulbs, candles, embers)
        if m.get("emission"):
            bsdf = mats[name].node_tree.nodes.get("Principled BSDF")
            rgb = [int(m["emission"][i:i + 2], 16) / 255 for i in (1, 3, 5)]
            lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
            bsdf.inputs["Emission Color"].default_value = (*lin, 1.0)
            bsdf.inputs["Emission Strength"].default_value = m.get("emission_strength", 1.0)
    scene = bpy.context.scene
    report = {"textures": textures, "props": {}}
    for p in spec["props"]:
        if only and p["id"] not in only:
            continue
        d = props_task.describe(props_task.build_prop(p, spec), spec)
        kit_build.clear_scene(bpy)
        objs = {}
        for m in d["meshes"]:
            objs[m["name"]] = kit_build.mesh_object(bpy, scene, m, spec, mats)
        bpy.context.view_layer.update()
        cols = []
        for c in d["colliders"]:
            obj, faces, verts = kit_build.collider_object(bpy, bmesh, scene, c, objs.get(c["parent"]))
            cols.append({"name": c["name"], "parent": c["parent"], "faces": faces, "verts": verts})
        glb = out / f"{p['id']}.glb"
        bpy.ops.export_scene.gltf(filepath=str(glb), **kit_build.KIT_EXPORT_OPTIONS)
        report["props"][p["id"]] = {
            "glb": str(glb),
            "objects": {o.name: {"triangles": sum(len(pl.vertices) - 2 for pl in o.data.polygons),
                                 "materials": [s.material.name for s in o.material_slots if s.material]}
                        for o in objs.values()},
            "colliders": cols,
            "triangles": d["triangles"],
        }
        print(f"PROPS built {p['id']}: {d['triangles']} triangles, {len(cols)} colliders")
    (out / "build.json").write_text(json.dumps(report, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
