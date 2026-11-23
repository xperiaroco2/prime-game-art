"""The prop lab's hybrid (research trial 2): Meshy's shape with the house materials. Takes Meshy's textured model,
reads its base colour under every face, maps each face to the nearest class of the style guide's library by colour
(teal -> painted metal, near-black -> rubber, grey and brass -> steel: no warm metals in the set, bright or cyan ->
energy), then bakes those library materials (prop_lab_light.py's material() and bake_set()) into one texture set and
exports a GLB Godot imports as a plain material. The shape is the generator's; the look is the house's.

Args after "--": --src GLB --out DIR [--length 22] [--res 1024] [--samples 32]
"""
from __future__ import annotations

import colorsys
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prop_lab_light as L  # noqa: E402


def argv() -> dict:
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = {"length": "22", "res": "1024", "samples": "32", "keep": "0", "bake": "0"}
    for i in range(0, len(a), 2):
        out[a[i].lstrip("-")] = a[i + 1]
    return out


def classify(rgb) -> str:
    """The library class for a texel colour (sRGB 0..1)."""
    h, s, v = colorsys.rgb_to_hsv(*rgb)
    if v < 0.16:
        return "rubber"
    if s > 0.35 and 0.42 < h < 0.6 and v > 0.75:
        return "energy"          # a bright cyan
    if s > 0.15 and 0.4 < h < 0.6:
        return "paint"           # the teal body (round 3: any teal, so the light teal barrel is paint, not steel)
    if s > 0.25 and 0.05 < h < 0.17:
        return "steel"           # brass and copper become steel (the style guide: no warm metals)
    if v < 0.32:
        return "frame"           # dark grey housings
    return "steel"


def main() -> None:
    a = argv()
    out = Path(a["out"])
    out.mkdir(parents=True, exist_ok=True)
    L.clear()
    bpy.ops.import_scene.gltf(filepath=a["src"])
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if len(meshes) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    for o in list(bpy.context.scene.objects):
        if o is not ob:
            bpy.data.objects.remove(o)
    ob.name = "Light"
    if a["keep"] == "1":   # Meshy as it comes: only to real size, base on the floor, centred
        vs = np.array([list(ob.matrix_world @ v.co) for v in ob.data.vertices])
        s = float(a["length"]) * L.CM / float((vs.max(0) - vs.min(0)).max())
        ob.data.transform(Matrix.Scale(s, 4))
        vs = np.array([list(v.co) for v in ob.data.vertices])
        c = (vs.max(0) + vs.min(0)) / 2
        ob.data.transform(Matrix.Translation((-c[0], -c[1], -vs[:, 2].min())))
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.export_scene.gltf(filepath=str(out / "light.glb"), export_format="GLB", use_selection=True,
                                  export_yup=True, export_apply=True, export_materials="EXPORT")
        tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
        (out / "build.json").write_text(json.dumps({"triangles": tris, "kept": True}), encoding="utf-8")
        print("PROP_KEEP " + json.dumps({"triangles": tris}), flush=True)
        return
    # the base colour texture and the faces' UV centres
    mat = ob.data.materials[0]
    img = next(n.image for n in mat.node_tree.nodes if n.type == "TEX_IMAGE" and n.image
               and "metal" not in n.image.name.lower() and "normal" not in n.image.name.lower()
               and "rough" not in n.image.name.lower())
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)
    uv = ob.data.uv_layers.active.data
    classes = {}
    face_class = []   # set after the slots exist: clearing the slots resets every face's index
    names = list(L.LIB.keys())
    for poly in ob.data.polygons:
        us = [uv[i].uv for i in poly.loop_indices]
        cu = sum(u.x for u in us) / len(us)
        cv = sum(u.y for u in us) / len(us)
        x = min(w - 1, max(0, int(cu % 1.0 * w)))
        y = min(h - 1, max(0, int(cv % 1.0 * h)))
        c = px[y, x, :3]
        srgb = [float(min(1.0, max(0.0, ch))) for ch in c]   # an 8-bit sRGB image's pixels come as stored (sRGB)
        k = classify(srgb)
        classes[k] = classes.get(k, 0) + 1
        face_class.append(names.index(k))
    ob.data.materials.clear()
    for k in names:
        if a.get("bake", "0") == "1":
            ob.data.materials.append(L.material(k))
        else:   # the library as plain constants (a generator's triangle soup unwraps into thousands of islands)
            base, met, rough, emit, _wear, ecol = L.LIB[k]
            m = bpy.data.materials.new("light_" + k)
            m.use_nodes = True
            p = m.node_tree.nodes["Principled BSDF"]
            p.inputs["Base Color"].default_value = (*[c ** 2.2 for c in base], 1)
            p.inputs["Metallic"].default_value = met
            p.inputs["Roughness"].default_value = rough
            if emit > 0:
                p.inputs["Emission Color"].default_value = (*[c ** 2.2 for c in ecol], 1)
                p.inputs["Emission Strength"].default_value = emit
            ob.data.materials.append(m)
    for poly, idx in zip(ob.data.polygons, face_class):
        poly.material_index = idx
    # real size: the longest side `length` cm, the base on the floor, centred; the long axis along x
    vs = np.array([list(ob.matrix_world @ v.co) for v in ob.data.vertices])
    ext = vs.max(0) - vs.min(0)
    s = float(a["length"]) * L.CM / float(ext.max())
    ob.data.transform(Matrix.Scale(s, 4))
    vs = np.array([list(v.co) for v in ob.data.vertices])
    c = (vs.max(0) + vs.min(0)) / 2
    ob.data.transform(Matrix.Translation((-c[0], -c[1], -vs[:, 2].min())))
    for p in ob.data.polygons:
        p.use_smooth = True
    ob.data.set_sharp_from_angle(angle=math.radians(35))   # round 3: smooth shading; the generator's triangles showed
    if a.get("bake", "0") != "1":
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.export_scene.gltf(filepath=str(out / "light.glb"), export_format="GLB", use_selection=True,
                                  export_yup=True, export_apply=True, export_normals=True, export_materials="EXPORT")
        tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
        rep = {"triangles": tris, "faces_by_class": classes, "src": a["src"], "length_cm": float(a["length"]),
               "materials": "library constants, no bake"}
        (out / "build.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
        print("PROP_REMAT " + json.dumps(rep), flush=True)
        return
    # a fresh UV set for the bake (Meshy's islands are many and small)
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bake_uv = ob.data.uv_layers.new(name="bake")
    ob.data.uv_layers.active = bake_uv
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(55), island_margin=0.004)
    bpy.ops.object.mode_set(mode="OBJECT")
    tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    L.bake_set(ob, out, int(a["res"]), int(a["samples"]))
    for layer in list(ob.data.uv_layers):
        if layer.name != "bake":
            ob.data.uv_layers.remove(layer)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=str(out / "light.glb"), export_format="GLB", use_selection=True, export_yup=True,
                              export_apply=True, export_texcoords=True, export_normals=True, export_materials="EXPORT")
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "light.blend"))
    rep = {"triangles": tris, "faces_by_class": classes, "src": a["src"], "length_cm": float(a["length"])}
    (out / "build.json").write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
    print("PROP_REMAT " + json.dumps(rep), flush=True)


if __name__ == "__main__":
    main()
