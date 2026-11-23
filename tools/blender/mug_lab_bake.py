"""The mug lab's baked glass (research, round 12 on): Cycles bakes what does not depend on the view into one texture
on the glass's own UVs, and the Godot glass shader (godot/mug_lab/glass.gdshader) reads it; the beer, its level and
the foam stay live. Real refraction depends on the view and cannot be baked, so the bake carries what makes glass read
thick and cut:
- R: thickness, ambient occlusion from inside the glass within 2.5 cm (1 thick, 0 thin);
- G: edges, the bevel normal's turn from the face normal (1 on a crisp ridge or groove);
- B: studio light, a glossy bake of warm softboxes, a cold window and two strips (the concept's light shapes).
The texture is packed as glass_map.png and set as the glass material's base colour, so the GLB carries it.

Args after "--": --blend IN.blend --out DIR [--res 1024] [--samples 48]
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np


def argv() -> dict:
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = {"res": "1024", "samples": "48"}
    for i in range(0, len(a), 2):
        out[a[i].lstrip("-")] = a[i + 1]
    return out


def unwrap(ob) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.006, area_weight=0.0)
    bpy.ops.object.mode_set(mode="OBJECT")


def lights() -> None:
    """The studio as a world: a glossy bake reflects along each face's normal, so a facet catches what lies along it.
    An equirectangular image drawn here (Blender's mapping: u = atan2(y, -x) / 2pi + 0.5, v = asin(z) / pi + 0.5):
    a warm ring a little over the horizon (the hall's warm lights), a warm softbox overhead toward the holder (-y), a
    cold window on -x, a thin warm strip; dark elsewhere. Every panel gets its own light shape, as in the concept."""
    W, H = 1024, 512
    u = (np.arange(W) + 0.5) / W
    v = (np.arange(H) + 0.5) / H
    lon = (u[None, :] - 0.5) * 2 * np.pi
    lat = (v[:, None] - 0.5) * np.pi
    cl = np.cos(lat)
    x = -np.cos(lon) * cl
    y = np.sin(lon) * cl
    z = np.sin(lat) * np.ones_like(lon)

    def band(t, lo, hi, soft):
        return np.clip((t - (lo - soft)) / soft, 0, 1) * np.clip(((hi + soft) - t) / soft, 0, 1)
    ring = band(z, 0.12, 0.42, 0.08) * 2.4
    soft = band(z, 0.55, 1.0, 0.1) * band(-y, 0.2, 1.0, 0.15) * 3.0
    window = band(-x, 0.72, 1.0, 0.1) * band(z, -0.2, 0.5, 0.1) * 3.2
    strip = band(z, 0.25, 0.28, 0.02) * band(x, 0.3, 1.0, 0.1) * 5.0
    warm = ring + soft + strip
    img = np.zeros((H, W, 4), dtype=np.float32)
    img[:, :, 0] = warm * 1.0 + window * 0.5
    img[:, :, 1] = warm * 0.8 + window * 0.75
    img[:, :, 2] = warm * 0.58 + window * 1.0
    img[:, :, 3] = 1.0
    env = bpy.data.images.new("bake_env", W, H, alpha=False, float_buffer=True)
    env.pixels.foreach_set(img.ravel())
    w = bpy.data.worlds.new("bake_world")
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    tex = nt.nodes.new("ShaderNodeTexEnvironment")
    tex.image = env
    nt.links.new(tex.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    bpy.context.scene.world = w


def bake(ob, name: str, res: int, build, kind: str = "EMIT") -> np.ndarray:
    img = bpy.data.images.new(name, res, res, alpha=False, float_buffer=True)
    m = bpy.data.materials.new("bake_" + name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    surf = build(nt)
    nt.links.new(surf, out.inputs["Surface"])
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.nodes.active = tex
    ob.data.materials.clear()
    ob.data.materials.append(m)
    sc = bpy.context.scene
    if kind == "GLOSSY":
        sc.render.bake.use_pass_direct = True
        sc.render.bake.use_pass_indirect = True
        sc.render.bake.use_pass_color = False
    bpy.ops.object.bake(type=kind, margin=8, use_clear=True)
    px = np.empty(res * res * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    return px.reshape(res, res, 4)[:, :, 0]


def main() -> None:
    a = argv()
    out = Path(a["out"])
    res, samples = int(a["res"]), int(a["samples"])
    bpy.ops.wm.open_mainfile(filepath=a["blend"])
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    glass = bpy.data.objects["Mug"]
    keep = list(glass.data.materials)
    unwrap(glass)
    lights()

    def thickness(nt):
        ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
        ao.inside = True
        ao.samples = 16
        ao.inputs["Distance"].default_value = 0.025
        em = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(ao.outputs["AO"], em.inputs["Color"])
        return em.outputs[0]

    def edges(nt):
        bev = nt.nodes.new("ShaderNodeBevel")
        bev.samples = 8
        bev.inputs["Radius"].default_value = 0.003
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        dot = nt.nodes.new("ShaderNodeVectorMath")
        dot.operation = "DOT_PRODUCT"
        nt.links.new(bev.outputs["Normal"], dot.inputs[0])
        nt.links.new(geo.outputs["Normal"], dot.inputs[1])
        mr = nt.nodes.new("ShaderNodeMapRange")   # dot 1 on flat faces -> 0; dot <= 0.9 on a ridge -> 1
        mr.inputs["From Min"].default_value = 0.998
        mr.inputs["From Max"].default_value = 0.95
        nt.links.new(dot.outputs["Value"], mr.inputs["Value"])
        em = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(mr.outputs["Result"], em.inputs["Color"])
        return em.outputs[0]

    def glossy(nt):
        p = nt.nodes.new("ShaderNodeBsdfPrincipled")
        p.inputs["Base Color"].default_value = (1, 1, 1, 1)
        p.inputs["Metallic"].default_value = 1.0
        p.inputs["Roughness"].default_value = 0.18
        return p.outputs[0]

    r = bake(glass, "thick", res, thickness)
    g = bake(glass, "edge", res, edges)
    b = bake(glass, "light", res, glossy, "GLOSSY")
    b = b / max(float(np.percentile(b, 99.5)), 1e-4)   # the light map normalised: its brightest 0.5 % at 1
    packed = np.ones((res, res, 4), dtype=np.float32)
    packed[:, :, 0] = np.clip(r, 0, 1)
    packed[:, :, 1] = np.clip(g, 0, 1)
    packed[:, :, 2] = np.clip(b, 0, 1)
    img = bpy.data.images.new("glass_map", res, res, alpha=False)
    img.pixels.foreach_set(packed.ravel())
    img.filepath_raw = str(out / "glass_map.png")
    img.file_format = "PNG"
    img.save()
    # back to the glass material, now with the map as its base colour (the GLB carries it; Godot's look reads it)
    glass.data.materials.clear()
    for mt in keep:
        glass.data.materials.append(mt)
    gm = bpy.data.materials["mug_glass"]   # by name: the boolean union can leave an empty first slot
    if gm.name not in [m.name for m in glass.data.materials if m]:
        glass.data.materials.append(gm)
    bsdf = gm.node_tree.nodes.get("Principled BSDF")
    tex = gm.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(out / "glass_map.png"))
    gm.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    for o in bpy.context.scene.objects:
        o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(out / "mug.glb"), export_format="GLB", use_selection=True, export_yup=True,
                              export_apply=True, export_normals=True, export_texcoords=True,
                              export_materials="EXPORT", export_extras=False, export_cameras=False,
                              export_lights=False)
    stats = {"res": res, "samples": samples,
             "thick_mean": round(float(r.mean()), 3), "edge_mean": round(float(g.mean()), 3),
             "light_p99": round(float(np.percentile(b, 99)), 3)}
    (out / "bake.json").write_text(json.dumps(stats, indent=1) + "\n", encoding="utf-8")
    print("MUG_BAKE " + json.dumps(stats), flush=True)


if __name__ == "__main__":
    main()
