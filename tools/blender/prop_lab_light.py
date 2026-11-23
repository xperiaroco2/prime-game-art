"""The prop lab (research trial 2, art#392 follow-up): a crew work light, an opaque hard-surface held prop, built from
code in headless Blender with the style guide's material library (docs/research/2026-11-23-prop-style-guide.md) and
baked in Cycles into one PBR texture set, so Godot imports it as plain StandardMaterial3D. Godot axes (y up, cm): the
light stands on its tail, the lens up (+Y); the thumb switch on +Z (the holder's side).

Modes:
- `--mode profile --src GLB --out DIR`: measures a blockout's radius by height (Meshy's preview) and writes
  profile.json, the outline the code build follows (the hybrid: AI shape, clean geometry);
- `--mode build --out DIR [--profile profile.json] [--res 1024] [--samples 32]`: the light (with the profile's
  outline when given), materials, UVs, the bake (base colour with AO and worn edges, metallic-roughness, emission),
  light.glb and build.json.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

CM = 0.01
HEIGHT = 20.0          # cm, the tail to the lens's face


def argv() -> dict:
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = {"res": "1024", "samples": "32", "profile": ""}
    for i in range(0, len(a), 2):
        out[a[i].lstrip("-")] = a[i + 1]
    return out


def B(p) -> Vector:
    return Vector((p[0] * CM, -p[2] * CM, p[1] * CM))


def clear() -> None:
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)


# --- the blockout's outline ---------------------------------------------------------------------------------------
def profile(src: str, out: Path) -> None:
    clear()
    bpy.ops.import_scene.gltf(filepath=src)
    vs = []
    for o in bpy.context.scene.objects:
        if o.type == "MESH":
            vs += [o.matrix_world @ v.co for v in o.data.vertices]
    p = np.array([[v.x, v.y, v.z] for v in vs])
    # the long axis is the light's: put it on z
    ext = p.max(0) - p.min(0)
    ax = int(np.argmax(ext))
    order = [i for i in range(3) if i != ax] + [ax]
    p = p[:, order]
    z0, z1 = p[:, 2].min(), p[:, 2].max()
    cx, cy = np.median(p[:, 0]), np.median(p[:, 1])
    r = np.hypot(p[:, 0] - cx, p[:, 1] - cy)
    t = (p[:, 2] - z0) / (z1 - z0)
    rows = []
    for k in range(41):
        sel = np.abs(t - k / 40) < 0.02
        if sel.sum() < 8:
            continue
        rows.append([round(k / 40, 4), float(np.percentile(r[sel], 85) / (z1 - z0))])   # 85th: past switch spikes
    # which end is the head (the wider one)
    head_top = np.mean([x[1] for x in rows if x[0] > 0.8]) > np.mean([x[1] for x in rows if x[0] < 0.2])
    if not head_top:
        rows = [[round(1 - a, 4), b] for a, b in reversed(rows)]
    (out / "profile.json").write_text(json.dumps({"src": src, "rows": rows}, indent=1) + "\n", encoding="utf-8")
    print("PROP_PROFILE " + json.dumps({"rows": len(rows), "head_ratio": rows[-1][1] / max(rows[len(rows) // 3][1], 1e-6)}))


# --- materials (the style guide's library) ------------------------------------------------------------------------
LIB = {
    # name: base sRGB, metallic, roughness, emission strength, edge wear (lighter, smoother edges), emission colour
    "paint": ((0.32, 0.44, 0.45), 0.4, 0.5, 0.0, 0.35, None),   # a step more saturated than the walls (the guide)
    "frame": ((0.25, 0.30, 0.31), 0.45, 0.48, 0.0, 0.3, None),
    "steel": ((0.60, 0.64, 0.66), 0.9, 0.32, 0.0, 0.15, None),
    "rubber": ((0.06, 0.065, 0.07), 0.0, 0.72, 0.0, 0.0, None),
    "lens": ((0.05, 0.07, 0.08), 0.0, 0.05, 0.0, 0.0, None),
    "energy": ((0.15, 0.85, 1.0), 0.0, 0.35, 1.2, 0.0, (0.15, 0.85, 1.0)),
    "emitter": ((0.85, 0.97, 1.0), 0.0, 0.2, 3.0, 0.0, (0.75, 0.95, 1.0)),   # the lit lens face: the brightest surface
}


def material(name: str) -> bpy.types.Material:
    base, met, rough, emit, wear, ecol = LIB[name]
    m = bpy.data.materials.new("light_" + name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    lin = [c ** 2.2 for c in base]
    if wear > 0:
        # worn edges: the bevel normal turning from the face normal marks an edge; lighter, smoother there
        bev = nt.nodes.new("ShaderNodeBevel")
        bev.inputs["Radius"].default_value = 0.0015
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        dot = nt.nodes.new("ShaderNodeVectorMath")
        dot.operation = "DOT_PRODUCT"
        nt.links.new(bev.outputs["Normal"], dot.inputs[0])
        nt.links.new(geo.outputs["Normal"], dot.inputs[1])
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value = 0.999
        mr.inputs["From Max"].default_value = 0.96
        nt.links.new(dot.outputs["Value"], mr.inputs["Value"])
        ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
        ao.inputs["Distance"].default_value = 0.012
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.inputs[6].default_value = (*lin, 1)
        mix.inputs[7].default_value = (*[min(1.0, c * (1 + wear * 1.6)) for c in lin], 1)
        nt.links.new(mr.outputs["Result"], mix.inputs[0])
        cav = nt.nodes.new("ShaderNodeMix")
        cav.data_type = "RGBA"
        cav.blend_type = "MULTIPLY"
        cav.inputs[0].default_value = 0.6
        nt.links.new(mix.outputs[2], cav.inputs[6])
        nt.links.new(ao.outputs["Color"], cav.inputs[7])
        nt.links.new(cav.outputs[2], p.inputs["Base Color"])
        rr = nt.nodes.new("ShaderNodeMapRange")
        rr.inputs["To Min"].default_value = rough
        rr.inputs["To Max"].default_value = rough * (1 - wear * 0.8)
        nt.links.new(mr.outputs["Result"], rr.inputs["Value"])
        nt.links.new(rr.outputs["Result"], p.inputs["Roughness"])
    else:
        p.inputs["Base Color"].default_value = (*lin, 1)
        p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = met
    if emit > 0:
        p.inputs["Emission Color"].default_value = (*[c ** 2.2 for c in ecol], 1)
        p.inputs["Emission Strength"].default_value = emit
    return m


# --- geometry -----------------------------------------------------------------------------------------------------
def lathe(name: str, prof: list, sides: int, mat: str, phase: float = 0.0, ribs: tuple | None = None):
    """A turned part: prof is [(y cm, r cm), ...] bottom to top; closed at both ends; `ribs` (pitch cm, depth cm)
    adds rings of rubber ribs."""
    bm = bmesh.new()
    rings = []
    for y, r in prof:
        if ribs:
            r = r + ribs[1] * (0.5 + 0.5 * math.cos(2 * math.pi * y / ribs[0]))
        rings.append([bm.verts.new(B((r * math.cos(phase + 2 * math.pi * k / sides), y,
                                       -r * math.sin(phase + 2 * math.pi * k / sides)))) for k in range(sides)])
    for a, b in zip(rings, rings[1:]):
        for k in range(sides):
            q = (k + 1) % sides
            bm.faces.new((a[k], a[q], b[q], b[k]))
    for ring, top in ((rings[0], False), (rings[-1], True)):
        c = bm.verts.new(sum((v.co for v in ring), Vector()) / sides)
        for k in range(sides):
            q = (k + 1) % sides
            bm.faces.new((ring[k], ring[q], c) if top else (ring[q], ring[k], c))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(material(mat))
    for p in ob.data.polygons:
        p.use_smooth = True
    ob.data.set_sharp_from_angle(angle=math.radians(35))
    return ob


def box(name: str, at, size, mat: str, bevel: float):
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (size[0] * CM, size[2] * CM, size[1] * CM)
    ob.location = B(at)
    bv = ob.modifiers.new("b", "BEVEL")
    bv.width = bevel * CM
    bv.segments = 3
    bpy.ops.object.modifier_apply(modifier="b")
    bpy.ops.object.transform_apply(scale=True)
    ob.data.materials.append(material(mat))
    for p in ob.data.polygons:
        p.use_smooth = True
    ob.data.set_sharp_from_angle(angle=math.radians(35))
    return ob


def loop_ring(name: str, at, mat: str):
    bpy.ops.mesh.primitive_torus_add(major_radius=0.9 * CM, minor_radius=0.3 * CM, major_segments=24, minor_segments=10)
    ob = bpy.context.active_object
    ob.name = name
    ob.location = B(at)
    ob.rotation_euler = (math.radians(90), 0, 0)
    ob.data.materials.append(material(mat))
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def outline(prof_json: str | None):
    """The radius by height (cm) of the light's turned body: from the blockout's profile when given (scaled to HEIGHT),
    else the drawn default. Returned as a function r(y)."""
    if prof_json:
        rows = json.loads(Path(prof_json).read_text(encoding="utf-8"))["rows"]
        ys = [a * HEIGHT for a, _ in rows]
        rs = [b * HEIGHT for _, b in rows]
    else:
        ys = [0, 1.2, 10.5, 14.5, 16.5, 18.2, 20.0]
        rs = [2.3, 2.2, 2.1, 2.2, 3.1, 3.2, 3.2]

    def r(y):
        return float(np.interp(y, ys, rs))
    return r


def build(out: Path, prof_json: str | None, res: int, samples: int) -> None:
    clear()
    R = outline(prof_json)
    # the parts' heights (cm) are the design's; their radii follow the outline, clamped to the style's proportions
    grip_r = max(1.9, min(2.3, R(6.0)))
    body_r = max(2.0, min(2.5, R(12.5)))
    head_r = max(2.8, min(3.6, R(18.5)))
    parts = []
    parts.append(lathe("tail", [(0.0, grip_r + 0.05), (0.15, grip_r + 0.2), (1.1, grip_r + 0.2), (1.25, grip_r)], 24, "steel"))
    grip = [(1.25 + 0.15 * i, grip_r) for i in range(int((10.3 - 1.25) / 0.15) + 1)]
    parts.append(lathe("grip", grip, 24, "rubber", ribs=(1.6, 0.1)))   # round 2: fewer, wider pads (not a bellows)
    parts.append(lathe("band", [(10.2, body_r + 0.12), (10.35, body_r + 0.2), (11.0, body_r + 0.2), (11.15, body_r + 0.1)], 24, "steel"))
    body = lathe("body", [(11.1, body_r), (14.3, body_r), (14.6, body_r + 0.1), (16.4, head_r - 0.15),
                          (16.7, head_r - 0.05)], 8, "paint", phase=math.pi / 8)
    bv = body.modifiers.new("b", "BEVEL")   # round 2: the octagon's edges bevelled (the guide: 1.5-3 mm on a hand prop)
    bv.width = 0.2 * CM
    bv.segments = 2
    bv.limit_method = "ANGLE"
    with bpy.context.temp_override(active_object=body, object=body):
        bpy.ops.object.modifier_apply(modifier="b")
    parts.append(body)
    parts.append(lathe("bezel", [(16.6, head_r), (16.8, head_r + 0.12), (18.6, head_r + 0.12), (18.9, head_r - 0.1),
                                 (19.2, head_r - 0.45)], 32, "steel"))
    parts.append(lathe("ring", [(19.0, head_r - 0.42), (19.25, head_r - 0.42), (19.3, head_r - 0.75), (19.05, head_r - 0.8)], 32, "energy"))
    parts.append(lathe("lens", [(18.8, head_r - 0.78), (19.35, head_r - 0.8), (19.55, (head_r - 0.8) * 0.6), (19.6, 0.01)], 32, "emitter"))
    parts.append(box("switch_base", (0.0, 12.6, body_r - 0.05), (1.5, 2.6, 0.5), "steel", 0.15))
    parts.append(box("switch", (0.0, 12.4, body_r + 0.22), (0.95, 1.4, 0.4), "rubber", 0.18))   # a dark rocker
    parts.append(box("pip", (0.0, 13.55, body_r + 0.22), (0.35, 0.3, 0.2), "energy", 0.06))      # a small status pip
    parts.append(box("lug", (grip_r + 0.15, 0.65, 0.0), (0.6, 0.8, 0.6), "steel", 0.12))   # the loop's anchor
    parts.append(loop_ring("loop", (grip_r + 0.75, 0.65, 0.0), "steel"))
    # one mesh, one UV set, the bake on it
    for o in parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = "Light"
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(55), island_margin=0.004)
    bpy.ops.object.mode_set(mode="OBJECT")
    tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    bake_set(ob, out, res, samples)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=str(out / "light.glb"), export_format="GLB", use_selection=True, export_yup=True,
                              export_apply=True, export_texcoords=True, export_normals=True, export_materials="EXPORT")
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "light.blend"))
    rep = {"triangles": tris, "height_cm": HEIGHT, "grip_r": grip_r, "body_r": body_r, "head_r": head_r,
           "profile": prof_json or "default", "res": res}
    (out / "build.json").write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
    print("PROP_BUILD " + json.dumps(rep), flush=True)


def bake_set(ob, out: Path, res: int, samples: int) -> None:
    """Cycles bakes the library's node materials into one texture set on the joined mesh's UVs: base colour (with the
    worn edges and AO), roughness and metallic (glTF's packed G and B), emission. Then one plain material uses them."""
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.render.bake.margin = 6
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1)
    sc.world = w
    imgs = {}
    for key, kind, cs in (("base", "DIFFUSE", "sRGB"), ("rough", "ROUGHNESS", "Non-Color"), ("emit", "EMIT", "sRGB")):
        img = bpy.data.images.new(f"light_{key}", res, res, alpha=False)
        img.colorspace_settings.name = cs
        for m in ob.data.materials:
            nt = m.node_tree
            t = nt.nodes.new("ShaderNodeTexImage")
            t.image = img
            nt.nodes.active = t
        if kind == "DIFFUSE":
            for m in ob.data.materials:
                pb = m.node_tree.nodes["Principled BSDF"]
                pb["_met"] = pb.inputs["Metallic"].default_value
                pb.inputs["Metallic"].default_value = 0.0
            sc.render.bake.use_pass_direct = False
            sc.render.bake.use_pass_indirect = False
            sc.render.bake.use_pass_color = True
        bpy.ops.object.bake(type=kind, use_clear=True)
        if kind == "DIFFUSE":   # the metals' metallic back for the metallic bake
            for m in ob.data.materials:
                pb = m.node_tree.nodes["Principled BSDF"]
                pb.inputs["Metallic"].default_value = pb["_met"]
        imgs[key] = img
    # metallic: per material constant, baked by an emission override of its value
    met = bpy.data.images.new("light_metal", res, res, alpha=False)
    met.colorspace_settings.name = "Non-Color"
    saved = []
    for m in ob.data.materials:
        nt = m.node_tree
        p = nt.nodes["Principled BSDF"]
        out_node = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
        em = nt.nodes.new("ShaderNodeEmission")
        v = p.inputs["Metallic"].default_value
        em.inputs["Color"].default_value = (v, v, v, 1)
        saved.append((nt, out_node, out_node.inputs["Surface"].links[0].from_socket))
        nt.links.new(em.outputs[0], out_node.inputs["Surface"])
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = met
        nt.nodes.active = t
    bpy.ops.object.bake(type="EMIT", use_clear=True)
    for nt, out_node, sock in saved:
        nt.links.new(sock, out_node.inputs["Surface"])
    # pack roughness (G) and metallic (B) as glTF wants
    r = np.empty(res * res * 4, np.float32)
    imgs["rough"].pixels.foreach_get(r)
    mm = np.empty(res * res * 4, np.float32)
    met.pixels.foreach_get(mm)
    orm = np.ones((res * res, 4), np.float32)
    orm[:, 1] = r.reshape(-1, 4)[:, 0]
    orm[:, 2] = mm.reshape(-1, 4)[:, 0]
    mr_img = bpy.data.images.new("light_mr", res, res, alpha=False)
    mr_img.colorspace_settings.name = "Non-Color"
    mr_img.pixels.foreach_set(orm.ravel())
    for key, img in (("base", imgs["base"]), ("mr", mr_img), ("emit", imgs["emit"])):
        img.filepath_raw = str(out / f"light_{key}.png")
        img.file_format = "PNG"
        img.save()
    # the plain material on every face
    pm = bpy.data.materials.new("light")
    pm.use_nodes = True
    nt = pm.node_tree
    p = nt.nodes["Principled BSDF"]
    tb = nt.nodes.new("ShaderNodeTexImage")
    tb.image = bpy.data.images.load(str(out / "light_base.png"))
    nt.links.new(tb.outputs["Color"], p.inputs["Base Color"])
    tm = nt.nodes.new("ShaderNodeTexImage")
    tm.image = bpy.data.images.load(str(out / "light_mr.png"))
    tm.image.colorspace_settings.name = "Non-Color"
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(tm.outputs["Color"], sep.inputs[0])
    nt.links.new(sep.outputs[1], p.inputs["Roughness"])
    nt.links.new(sep.outputs[2], p.inputs["Metallic"])
    te = nt.nodes.new("ShaderNodeTexImage")
    te.image = bpy.data.images.load(str(out / "light_emit.png"))
    nt.links.new(te.outputs["Color"], p.inputs["Emission Color"])
    p.inputs["Emission Strength"].default_value = 2.0
    ob.data.materials.clear()
    ob.data.materials.append(pm)
    for poly in ob.data.polygons:
        poly.material_index = 0


def main() -> None:
    a = argv()
    out = Path(a["out"])
    out.mkdir(parents=True, exist_ok=True)
    if a["mode"] == "profile":
        profile(a["src"], out)
    else:
        build(out, a["profile"] or None, int(a["res"]), int(a["samples"]))


if __name__ == "__main__":
    main()
