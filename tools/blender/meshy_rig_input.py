"""A rig input for Meshy (art #25): one assembled character as a static, textured GLB facing +Z.

Meshy rigs "textured humanoid GLB files" whose face points to +Z (docs.meshy.ai/en/api/rigging-and-animation). Our
characters are flat colours without UVs or textures, so this script bakes them into a small palette for the rig input
only: every material becomes one square cell of a PNG, every face of it gets UVs at that cell's centre, and one
material samples the PNG. The parts are joined into one mesh in the rest pose (the T-pose); the armature, the actions
and the toe bones stay out (Meshy builds its own skeleton). Blender's glTF exporter (+Y up) turns Blender's front -Y
into glTF's +Z.

Usage (background Blender only; `tools/run.py meshy rig-input` runs it):
  blender -b --factory-startup --python-exit-code 1 --python meshy_rig_input.py -- --blend <character.blend> --out <dir>
Writes <dir>/<id>.glb, <id>_texture.png (the palette, also sent as texture_image_url) and <id>.json (what was made).
"""

import argparse
import json
import math
import os
import sys

import bpy

CELL = 8  # pixels per palette cell


def parse():
    p = argparse.ArgumentParser(prog="meshy_rig_input.py")
    p.add_argument("--blend", required=True)
    p.add_argument("--out", required=True)
    return p.parse_args(sys.argv[sys.argv.index("--") + 1:])


def main():
    a = parse()
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(a.blend))
    cid = os.path.splitext(os.path.basename(a.blend))[0]
    scene = bpy.context.scene
    arms = [o for o in scene.objects if o.type == "ARMATURE"]
    parts = [o for o in scene.objects if o.type == "MESH"]
    if len(arms) != 1 or not parts:
        raise SystemExit(f"{a.blend}: not a saved character (one armature and its parts)")
    arm = arms[0]
    arm.data.pose_position = "REST"
    bpy.context.view_layer.update()

    # the palette: one cell per material, by its viewport colour (equal to the Principled base colour when saved)
    mats = []
    for o in parts:
        for slot in o.material_slots:
            if slot.material and slot.material not in mats:
                mats.append(slot.material)
    side = max(1, math.ceil(math.sqrt(len(mats))))
    size = side * CELL
    pixels = [0.0] * (size * size * 4)
    cells = {}
    for n, m in enumerate(mats):
        cx, cy = n % side, n // side
        rgb = [max(0.0, min(1.0, c)) for c in m.diffuse_color[:3]]
        srgb = [c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055 for c in rgb]  # linear -> sRGB
        for y in range(cy * CELL, (cy + 1) * CELL):
            for x in range(cx * CELL, (cx + 1) * CELL):
                i = (y * size + x) * 4
                pixels[i:i + 4] = [*srgb, 1.0]
        cells[m.name] = ((cx + 0.5) / side, (cy + 0.5) / side)
    img = bpy.data.images.new(f"{cid}_palette", size, size, alpha=False)
    img.colorspace_settings.name = "sRGB"
    img.pixels = pixels
    os.makedirs(a.out, exist_ok=True)
    png = os.path.join(os.path.abspath(a.out), f"{cid}_texture.png")
    img.filepath_raw = png
    img.file_format = "PNG"
    img.save()
    img.pack()

    # one static mesh: each part's evaluated rest shape, UVs at its material's cell, one textured material
    tex = bpy.data.materials.new(f"{cid}_palette")
    tex.use_nodes = True
    nodes = tex.node_tree.nodes
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    node = nodes.new("ShaderNodeTexImage")
    node.image = img
    node.interpolation = "Closest"
    tex.node_tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.8
    dg = bpy.context.evaluated_depsgraph_get()
    joined = []
    for o in parts:
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), depsgraph=dg)
        me.transform(o.matrix_world)
        uv = me.uv_layers.new(name="UVMap") if not me.uv_layers else me.uv_layers[0]
        for poly in me.polygons:
            slot_mat = o.material_slots[poly.material_index].material if o.material_slots else None
            u, v = cells.get(slot_mat.name if slot_mat else "", (0.5 / side, 0.5 / side))
            for li in poly.loop_indices:
                uv.data[li].uv = (u, v)
        me.materials.clear()
        me.materials.append(tex)
        obj = bpy.data.objects.new(f"{cid}_{o.name}_static", me)
        scene.collection.objects.link(obj)
        joined.append(obj)
    for o in list(scene.objects):
        if o not in joined:
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.object.select_all(action="DESELECT")
    for o in joined:
        o.select_set(True)
    bpy.context.view_layer.objects.active = joined[0]
    bpy.ops.object.join()
    body = bpy.context.view_layer.objects.active
    body.name = body.data.name = cid
    zs = [(body.matrix_world @ v.co).z for v in body.data.vertices]
    tris = sum(len(p.vertices) - 2 for p in body.data.polygons)
    glb = os.path.join(os.path.abspath(a.out), f"{cid}.glb")
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", use_selection=False, export_yup=True,
                              export_apply=True, export_animations=False, export_skins=False,
                              export_materials="EXPORT", export_image_format="AUTO")
    info = {"id": cid, "blend": os.path.abspath(a.blend), "glb": glb, "texture": png, "palette_px": size,
            "materials": {m.name: [round(c, 4) for c in m.diffuse_color[:3]] for m in mats},
            "triangles": tris, "vertices": len(body.data.vertices), "height_m": round(max(zs) - min(zs), 3),
            "feet_z_m": round(min(zs), 4), "facing": "glTF +Z (Blender -Y, the exporter's +Y up conversion)",
            "glb_bytes": os.path.getsize(glb), "texture_bytes": os.path.getsize(png)}
    with open(os.path.join(os.path.abspath(a.out), f"{cid}.json"), "w", encoding="utf-8") as fh:
        json.dump(info, fh, indent=1)
    print("RIG_INPUT", json.dumps({k: info[k] for k in ("glb", "triangles", "height_m", "glb_bytes")}))


main()
