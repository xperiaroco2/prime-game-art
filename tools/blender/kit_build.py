"""Builds every piece of a kit spec (kits/house.json) as its own GLB (art #74, docs/kit.md). The runner calls it
(tools/run.py kit); by hand, background only:

  blender -b --factory-startup --python-exit-code 1 --python tools/blender/kit_build.py -- \
      --spec kits/house.json --out D:/prime-art-raw/kits/house/v1 --ambientcg D:/prime-art-raw/env/ambientcg [--only id,...]

The geometry comes from kit_geom.py (pure Python, Godot axes); this script only turns it into Blender objects (Blender
axes: x, -z, y), makes the detail textures and materials, and exports. Per piece: <out>/<id>.glb; for the kit:
<out>/textures/<material>_{d,n}.png (made from the ambientCG CC0 maps, sources/ambientcg_materials_2k.toml) and
<out>/build.json (what each GLB holds, measured in Blender before the export).

Materials: one per exported material (v2, art #86, look.md section 5: `set` packs plaster, wood and concrete; metal;
glass); the paint is the vertex colour (COLOR_0, multiplied into the base colour), so the kit needs three materials
however many paints it uses. A pack's material is plain white in the GLB; its detail lives in the packed textures
<out>/textures/set_d.png (RGB: the layers' detail), set_n0.png (RG, BA: layers 0 and 1's normal XY) and set_n1.png
(RG: layer 2's), which godot/kit/kit_set.gdshader reads by the vertex colour's alpha (kit_geom.layer_alpha). An
unpacked textured material keeps its own detail texture. Each material is named `kit_<name>-vcol`: Godot's scene importer strips the suffix and sets
vertex colour as albedo with sRGB vertex colours (Godot 4.7.2's glTF importer misses that flag on a mesh's first
primitive), so COLOR_0 holds sRGB-encoded paint (kit_geom.role_colour). KIT_EXPORT_OPTIONS is a plain constant (bpy is imported only in main()).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit_geom  # noqa: E402

TEX_SIZE = 512

KIT_EXPORT_OPTIONS = {
    "export_format": "GLB",
    "use_active_scene": True,
    "use_selection": False,
    "use_visible": False,
    "use_renderable": False,
    "use_active_collection": False,
    "export_yup": True,
    "export_apply": False,
    "export_skins": False,
    "export_animations": False,
    "export_morph": False,
    "export_cameras": False,
    "export_lights": False,
    "export_materials": "EXPORT",
    "export_image_format": "AUTO",
    "export_vertex_color": "ACTIVE",
    "export_all_vertex_colors": False,
    "export_active_vertex_color_when_no_material": False,
    "export_texcoords": True,
    "export_normals": True,
    "export_tangents": False,
    "export_attributes": False,
    "export_extras": False,
    "export_shared_accessors": False,
    "export_gpu_instances": False,
    "export_draco_mesh_compression_enable": False,
    "export_meshopt_compression_enable": False,
    "export_use_gltfpack": False,
    "check_existing": False,
    "will_save_settings": False,
}


def to_blender(p, origin=(0.0, 0.0, 0.0)):
    """A Godot-axes point (relative to origin) in Blender axes; the exporter's +Y-up conversion turns it back."""
    x, y, z = p[0] - origin[0], p[1] - origin[1], p[2] - origin[2]
    return (x, -z, y)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:]
    out = {"only": ""}
    for i in range(0, len(argv), 2):
        out[argv[i].lstrip("-")] = argv[i + 1]
    return out


def make_textures(bpy, np, spec, ambientcg: Path, out: Path) -> dict:
    """<material>_d.png: the source's luminance as a grey detail map, linear mean TEX_MEAN and the material's
    lum_std (relative to a 0.5 mean, as the house lab's shader); <material>_n.png: its OpenGL normal map. 512 px."""
    out.mkdir(parents=True, exist_ok=True)
    made = {}
    for name, mat in spec["materials"].items():
        src = mat.get("source")
        if not src:
            continue
        base = ambientcg / src / f"{src}_2K-JPG"
        col = bpy.data.images.load(str(base / f"{src}_2K-JPG_Color.jpg"))
        col.scale(TEX_SIZE, TEX_SIZE)
        px = np.empty(TEX_SIZE * TEX_SIZE * 4, dtype=np.float32)
        col.pixels.foreach_get(px)
        px = px.reshape(-1, 4)
        lin = np.where(px[:, :3] <= 0.04045, px[:, :3] / 12.92, ((px[:, :3] + 0.055) / 1.055) ** 2.4)
        lum = lin @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
        z = (lum - lum.mean()) / max(float(lum.std()), 1e-6)
        val = np.clip(kit_geom.TEX_MEAN * (1.0 + (mat["lum_std"] / 0.5) * z), 0.0, 1.0)
        enc = np.where(val <= 0.0031308, val * 12.92, 1.055 * val ** (1 / 2.4) - 0.055)
        d = bpy.data.images.new(f"{name}_d", TEX_SIZE, TEX_SIZE, alpha=False)
        rgba = np.ones((TEX_SIZE * TEX_SIZE, 4), dtype=np.float32)
        rgba[:, 0] = rgba[:, 1] = rgba[:, 2] = enc
        d.pixels.foreach_set(rgba.ravel())
        d.filepath_raw = str(out / f"{name}_d.png")
        d.file_format = "PNG"
        d.save()
        nrm = bpy.data.images.load(str(base / f"{src}_2K-JPG_NormalGL.jpg"))
        nrm.colorspace_settings.name = "Non-Color"
        nrm.scale(TEX_SIZE, TEX_SIZE)
        nrm.filepath_raw = str(out / f"{name}_n.png")
        nrm.file_format = "PNG"
        nrm.save()
        bpy.data.images.remove(col)
        made[name] = {"d": str(out / f"{name}_d.png"), "n": str(out / f"{name}_n.png"),
                      "d_linear_mean": round(float(val.mean()), 4), "d_linear_std": round(float(val.std()), 4)}
        made[name]["_d"], made[name]["_n"] = enc, nrm
    for pack, d in spec.get("packs", {}).items():
        made[pack] = pack_textures(bpy, np, pack, [made[m] for m in d["layers"]], out)
    for name in spec["materials"]:
        if name in made:
            made[name].pop("_d", None)
            made[name].pop("_n", None)
    return made


def pack_textures(bpy, np, pack: str, layers: list, out: Path) -> dict:
    """<pack>_d.png: the layers' sRGB detail in R, G, B; <pack>_n0.png: layer 0's normal XY in RG, layer 1's in BA;
    <pack>_n1.png: layer 2's in RG (B 0.5, A 1)."""
    n = TEX_SIZE * TEX_SIZE
    d = np.ones((n, 4), dtype=np.float32)
    for i, layer in enumerate(layers[:3]):
        d[:, i] = layer["_d"]
    normals = []
    for layer in layers:
        px = np.empty(n * 4, dtype=np.float32)
        layer["_n"].pixels.foreach_get(px)
        normals.append(px.reshape(-1, 4))
    n0 = np.ones((n, 4), dtype=np.float32)
    n1 = np.full((n, 4), 0.5, dtype=np.float32)
    n1[:, 3] = 1.0
    n0[:, 0:2] = normals[0][:, 0:2]
    if len(normals) > 1:
        n0[:, 2:4] = normals[1][:, 0:2]
    if len(normals) > 2:
        n1[:, 0:2] = normals[2][:, 0:2]
    files = {}
    for key, arr, alpha in (("d", d, False), ("n0", n0, True), ("n1", n1, False)):
        img = bpy.data.images.new(f"{pack}_{key}", TEX_SIZE, TEX_SIZE, alpha=alpha, float_buffer=False)
        img.colorspace_settings.name = "sRGB" if key == "d" else "Non-Color"
        img.alpha_mode = "STRAIGHT"
        img.pixels.foreach_set(arr.ravel())
        img.filepath_raw = str(out / f"{pack}_{key}.png")
        img.file_format = "PNG"
        if alpha:
            bpy.context.scene.render.image_settings.color_mode = "RGBA"
        img.save()
        files[key] = str(out / f"{pack}_{key}.png")
    return {"files": files, "layers": [Path(layer["d"]).stem[:-2] for layer in layers]}


def make_materials(bpy, spec, textures: dict) -> dict:
    """One Blender material per exported material: a pack (plain white; its shader reads the packed textures in Godot)
    or an unpacked kit material (its own detail texture)."""
    mats = {}
    for pack, d in spec.get("packs", {}).items():
        mat = bpy.data.materials.new(f"kit_{pack}-vcol")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (1, 1, 1, 1)
        layers = [spec["materials"][m] for m in d["layers"]]
        bsdf.inputs["Roughness"].default_value = sum(m.get("roughness", 0.8) for m in layers) / len(layers)
        mats[pack] = mat
    for name, m in spec["materials"].items():
        if m.get("pack"):
            continue
        mat = bpy.data.materials.new(f"kit_{name}-vcol")
        mat.use_nodes = True
        nt = mat.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (1, 1, 1, 1)
        bsdf.inputs["Roughness"].default_value = m.get("roughness", 0.8)
        bsdf.inputs["Metallic"].default_value = m.get("metallic", 0.0)
        if name in textures:
            uv = nt.nodes.new("ShaderNodeUVMap")
            uv.uv_map = "UVMap"
            d = nt.nodes.new("ShaderNodeTexImage")
            d.image = bpy.data.images.load(textures[name]["d"])
            nt.links.new(uv.outputs["UV"], d.inputs["Vector"])
            nt.links.new(d.outputs["Color"], bsdf.inputs["Base Color"])
            n = nt.nodes.new("ShaderNodeTexImage")
            n.image = bpy.data.images.load(textures[name]["n"])
            n.image.colorspace_settings.name = "Non-Color"
            nt.links.new(uv.outputs["UV"], n.inputs["Vector"])
            nm = nt.nodes.new("ShaderNodeNormalMap")
            nm.inputs["Strength"].default_value = m.get("normal_strength", 0.2)
            nt.links.new(n.outputs["Color"], nm.inputs["Color"])
            nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
        if "alpha" in m:
            bsdf.inputs["Alpha"].default_value = m["alpha"]
            mat.surface_render_method = "BLENDED"
        mats[name] = mat
    return mats


def clear_scene(bpy):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for me in list(bpy.data.meshes):
        bpy.data.meshes.remove(me)


def mesh_object(bpy, scene, m: dict, spec: dict, mats: dict):
    origin = m["origin"]
    me = bpy.data.meshes.new(m["name"])
    me.from_pydata([to_blender(v, origin) for v in m["verts"]], [], m["faces"])
    me.update()
    exported = {r: kit_geom.export_material(spec, spec["roles"][r]["material"]) for r in set(m["roles"])}
    names = sorted(set(exported.values()))
    for n in names:
        me.materials.append(mats[n])
    for poly, role in zip(me.polygons, m["roles"]):
        poly.material_index = names.index(exported[role])
    layers = [me.uv_layers.new(name="UVMap"), me.uv_layers.new(name="UV2")]
    for layer, key in zip(layers, ("uv0", "uv2")):
        for poly, uvs in zip(me.polygons, m[key]):
            for li, uv in zip(poly.loop_indices, uvs):
                layer.data[li].uv = uv
    me.uv_layers.active = layers[0]
    layers[0].active_render = True
    col = me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
    colours = {r: kit_geom.role_colour(spec, r) for r in set(m["roles"])}
    for poly, role in zip(me.polygons, m["roles"]):
        for li in poly.loop_indices:
            col.data[li].color = colours[role]
    me.color_attributes.active_color = col
    me.color_attributes.render_color_index = 0
    obj = bpy.data.objects.new(m["name"], me)
    obj.location = to_blender(origin)
    scene.collection.objects.link(obj)
    return obj


def collider_object(bpy, bmesh, scene, c: dict, parent):
    bm = bmesh.new()
    for p in c["points"]:
        bm.verts.new(to_blender(p))
    bmesh.ops.convex_hull(bm, input=bm.verts[:])
    for f in bm.faces:
        f.normal_update()
    me = bpy.data.meshes.new(c["name"])
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(c["name"], me)
    scene.collection.objects.link(obj)
    if parent is not None:
        obj.parent = parent
        obj.matrix_parent_inverse = parent.matrix_world.inverted()
    return obj, len(me.polygons), len(me.vertices)


def main():
    import bmesh
    import bpy
    import numpy as np

    a = args()
    spec = kit_geom.load_spec(Path(a["spec"]))
    out = Path(a["out"])
    out.mkdir(parents=True, exist_ok=True)
    only = {s for s in a["only"].split(",") if s}
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    textures = make_textures(bpy, np, spec, Path(a["ambientcg"]), out / "textures")
    mats = make_materials(bpy, spec, textures)
    scene = bpy.context.scene
    report = {"textures": textures, "pieces": {}}
    for p in spec["pieces"]:
        if only and p["id"] not in only:
            continue
        d = kit_geom.describe(kit_geom.build_piece(p, spec), spec)
        clear_scene(bpy)
        objs = {}
        for m in d["meshes"]:
            objs[m["name"]] = mesh_object(bpy, scene, m, spec, mats)
        cols = []
        bpy.context.view_layer.update()
        for c in d["colliders"]:
            obj, faces, verts = collider_object(bpy, bmesh, scene, c, objs.get(c["parent"]))
            cols.append({"name": c["name"], "group": c["group"], "parent": c["parent"], "faces": faces, "verts": verts})
        glb = out / f"{p['id']}.glb"
        bpy.ops.export_scene.gltf(filepath=str(glb), **KIT_EXPORT_OPTIONS)
        report["pieces"][p["id"]] = {
            "glb": str(glb),
            "objects": {o.name: {"triangles": sum(len(pl.vertices) - 2 for pl in o.data.polygons),
                                 "uv_layers": [u.name for u in o.data.uv_layers],
                                 "materials": [s.material.name for s in o.material_slots if s.material]}
                        for o in objs.values()},
            "colliders": cols,
            "triangles": d["triangles"],
        }
        print(f"KIT built {p['id']}: {d['triangles']} triangles, {len(cols)} colliders")
    (out / "build.json").write_text(json.dumps(report, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
