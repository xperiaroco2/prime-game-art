"""A retexture input (art #196 M3b, docs/meshy.md "Retexture inputs"): one mesh of a saved character as a static
rest-pose GLB that holds its texture UV and nothing else, so Meshy's retexture (`enable_original_uv`) paints our own
UV and the result maps straight back onto the kit. Background Blender only, through the runner
(`tools/run.py meshy retexture-input`):

  blender -b --factory-startup --python-exit-code 1 --python tools/blender/meshy_retexture_input.py -- \
      --blend <M2/export/alien_character.blend> --out <M3b/input> [--object Body] [--uv UVMap] [--name alien_body]

What it writes into --out:
- `<name>.glb`: one node, one mesh, the object's own mesh data (the kit exports it with `export_apply` off, so no
  modifier is applied; the armature is put in its rest pose and dropped), placed by its world matrix; no skin, no shape
  keys, no animation; only POSITION, NORMAL and the one UV set (TEXCOORD_0); one plain grey material without textures;
- `<name>.json`: triangles, vertices, height, bytes, sha256 and the UV check.

The UV check re-imports the GLB into an empty scene and compares its UV islands with the source's: the same number
of islands, and per island (sorted by area) the same UV area and bounding box within 1e-4. It fails the run on a
mismatch.
"""
import argparse
import hashlib
import json
import os
import sys

import bmesh
import bpy


def args():
    p = argparse.ArgumentParser()
    p.add_argument("--blend", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--object", default="Body")
    p.add_argument("--uv", default="UVMap")
    p.add_argument("--name", default="alien_body")
    return p.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])


def islands(me, uv_name):
    """Per UV island (faces joined across an edge whose two loops agree in UV): (area, (umin, vmin, umax, vmax))."""
    bm = bmesh.new()
    bm.from_mesh(me)
    uvl = bm.loops.layers.uv[uv_name]
    bm.faces.ensure_lookup_table()
    parent = list(range(len(bm.faces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for e in bm.edges:
        loops = list(e.link_loops)
        if len(loops) != 2:
            continue
        a, b = loops
        ua = {a.vert.index: a[uvl].uv.copy(), a.link_loop_next.vert.index: a.link_loop_next[uvl].uv.copy()}
        ub = {b.vert.index: b[uvl].uv.copy(), b.link_loop_next.vert.index: b.link_loop_next[uvl].uv.copy()}
        if all((ua[v] - ub[v]).length < 1e-6 for v in ua):
            parent[find(a.face.index)] = find(b.face.index)
    out = {}
    for f in bm.faces:
        uvs = [lp[uvl].uv for lp in f.loops]
        area = 0.0
        for i in range(1, len(uvs) - 1):  # a fan of triangles: the same area for a quad and its two triangles
            d1, d2 = uvs[i] - uvs[0], uvs[i + 1] - uvs[0]
            area += abs(d1.x * d2.y - d1.y * d2.x) / 2
        r = find(f.index)
        a0, box = out.get(r, (0.0, [9.0, 9.0, -9.0, -9.0]))
        for uv in uvs:
            box = [min(box[0], uv.x), min(box[1], uv.y), max(box[2], uv.x), max(box[3], uv.y)]
        out[r] = (a0 + area, box)
    bm.free()
    return sorted(out.values(), key=lambda t: (-t[0], t[1]))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    a = args()
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(a.blend))
    src = bpy.data.objects.get(a.object)
    if src is None or src.type != "MESH":
        raise SystemExit(f"{a.blend}: no mesh object {a.object!r}")
    if a.uv not in src.data.uv_layers:
        raise SystemExit(f"{a.object} has no UV map {a.uv!r} (it has {[u.name for u in src.data.uv_layers]})")
    arm = src.find_armature()
    if arm is not None:
        arm.data.pose_position = "REST"
    modifiers = [(m.name, m.type) for m in src.modifiers]
    src_islands = islands(src.data, a.uv)

    me = src.data.copy()
    me.name = a.name
    me.transform(src.matrix_world)
    if me.shape_keys:
        tmp = bpy.data.objects.new("tmp", me)
        bpy.context.scene.collection.objects.link(tmp)
        tmp.shape_key_clear()
        bpy.data.objects.remove(tmp, do_unlink=True)
    for uv in [u for u in me.uv_layers if u.name != a.uv]:
        me.uv_layers.remove(uv)
    for ca in list(me.color_attributes):
        me.color_attributes.remove(ca)
    for att in [t for t in me.attributes if not t.is_internal and not t.is_required
                and t.name not in (a.uv, "sharp_face", "sharp_edge", "material_index")
                and not t.name.startswith(".")]:
        try:
            me.attributes.remove(att)
        except RuntimeError:
            pass
    me.materials.clear()
    mat = bpy.data.materials.new(f"{a.name}_plain")
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (0.5, 0.5, 0.5, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.6
    me.materials.append(mat)

    scene = bpy.context.scene
    for o in list(scene.objects):  # only the new object stays in the scene
        bpy.data.objects.remove(o, do_unlink=True)
    obj = bpy.data.objects.new(a.name, me)
    scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    os.makedirs(a.out, exist_ok=True)
    out = os.path.abspath(a.out)
    glb = os.path.join(out, f"{a.name}.glb")
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", use_selection=True, export_yup=True,
                              export_apply=False, export_animations=False, export_skins=False, export_morph=False,
                              export_texcoords=True, export_normals=True, export_tangents=False,
                              export_vertex_color="NONE", export_attributes=False, export_materials="EXPORT",
                              export_image_format="NONE", export_extras=False, export_cameras=False,
                              export_lights=False)
    zs = [v.co.z for v in me.vertices]
    tris = sum(len(p.vertices) - 2 for p in me.polygons)

    for o in list(scene.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.import_scene.gltf(filepath=glb)
    got = [o for o in scene.objects if o.type == "MESH"]
    if len(got) != 1:
        raise SystemExit(f"{glb}: re-imported {len(got)} meshes, expected one")
    back = got[0].data
    back_uv = back.uv_layers[0].name
    back_islands = islands(back, back_uv)
    problems = []
    if len(back.uv_layers) != 1:
        problems.append(f"the GLB has {len(back.uv_layers)} UV sets")
    if len(back_islands) != len(src_islands):
        problems.append(f"{len(back_islands)} UV islands in the GLB, {len(src_islands)} in {a.object}.{a.uv}")
    else:
        for n, ((a0, b0), (a1, b1)) in enumerate(zip(src_islands, back_islands)):
            if abs(a0 - a1) > 1e-4 or max(abs(x - y) for x, y in zip(b0, b1)) > 1e-4:
                problems.append(f"island {n}: area {a0:.6f} vs {a1:.6f}, box {b0} vs {b1}")
    info = {
        "blend": os.path.abspath(a.blend), "object": a.object, "uv": a.uv, "modifiers_not_applied": modifiers,
        "glb": glb, "glb_bytes": os.path.getsize(glb), "sha256": sha256(glb),
        "triangles": tris, "vertices": len(me.vertices), "height_m": round(max(zs) - min(zs), 4),
        "feet_z_m": round(min(zs), 4), "facing": "glTF +Z (Blender -Y, the exporter's +Y up conversion)",
        "uv_check": {"islands": len(src_islands), "islands_glb": len(back_islands),
                     "uv_area_used": round(sum(t[0] for t in src_islands), 5),
                     "islands_detail": [{"area": round(t[0], 6), "box": [round(x, 5) for x in t[1]]}
                                        for t in src_islands],
                     "equal": not problems, "problems": problems},
    }
    with open(os.path.join(out, f"{a.name}.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(info, fh, indent=1)
        fh.write("\n")
    print("RETEXTURE_INPUT", json.dumps({k: info[k] for k in ("glb", "triangles", "glb_bytes", "sha256")}), flush=True)
    if problems:
        raise SystemExit("the GLB's UV differs from the source's: " + "; ".join(problems))


if __name__ == "__main__":
    main()
