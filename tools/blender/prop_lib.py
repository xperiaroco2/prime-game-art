"""The shared Blender helper for props (art #87, docs/props.md): the library's materials (the kit's, re-pointed by
props/library.toml's [materials], plus an emissive one), a pack file's import (decimated to the class's budget, its
colours read per face from the material or its texture), and the export of one described prop as one GLB with its
collider and light anchor. The geometry and the paint are prop_geom.py's (pure Python); this file only touches bpy.
The task props (#82) use it too: `materials`, `import_pack` and `export_prop` are the interface.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit_build  # noqa: E402
import kit_geom  # noqa: E402
import prop_geom  # noqa: E402

EMISSION_STRENGTH = 1.0  # the bulbs' glow in the GLB; the map's lights do the lighting


def materials(bpy, np, spec: dict, ambientcg: Path, out: Path) -> tuple[dict, dict]:
    """One `kit_<name>-vcol` material per spec material (detail textures from ambientCG as the kit makes them)."""
    textures = kit_build.make_textures(bpy, np, spec, ambientcg, out / "textures")
    mats = kit_build.make_materials(bpy, spec, textures)
    return mats, textures


def set_emission(mats: dict, spec: dict, role: str | None) -> None:
    """Sets the emissive material's glow to the prop's emissive paint (one emissive role per prop)."""
    for name, mat in mats.items():
        if not spec["materials"][name].get("emissive"):
            continue
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if role is None:
            bsdf.inputs["Emission Strength"].default_value = 0.0
            continue
        h = spec["roles"][role]["hex"].lstrip("#")
        lin = [kit_geom.srgb_to_linear(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4)]
        bsdf.inputs["Emission Color"].default_value = (*lin, 1.0)
        bsdf.inputs["Emission Strength"].default_value = EMISSION_STRENGTH


def _find_image(socket, depth: int = 0):
    for link in socket.links:
        node = link.from_node
        if node.type == "TEX_IMAGE" and node.image is not None:
            return node.image
        if depth < 4:
            for s in node.inputs:
                img = _find_image(s, depth + 1)
                if img is not None:
                    return img
    return None


def _material_colour(np, mat, cache: dict):
    """("img", pixels h x w x 4 in linear RGB) or ("const", linear RGB) for a pack material's base colour."""
    key = mat.name if mat is not None else ""
    if key in cache:
        return cache[key]
    info = ("const", (0.8, 0.8, 0.8))
    if mat is not None and mat.use_nodes:
        bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is not None:
            inp = bsdf.inputs["Base Color"]
            img = _find_image(inp)
            if img is not None and img.size[0] > 0:
                w, h = img.size
                px = np.empty(w * h * 4, dtype=np.float32)
                img.pixels.foreach_get(px)
                px = px.reshape(h, w, 4)[:, :, :3]
                if img.colorspace_settings.name == "sRGB":
                    px = np.where(px <= 0.04045, px / 12.92, ((px + 0.055) / 1.055) ** 2.4)
                info = ("img", px)
            else:
                info = ("const", tuple(inp.default_value)[:3])
    cache[key] = info
    return info


def import_pack(bpy, np, p: dict, env: Path, max_triangles: int | None) -> tuple[list[dict], int]:
    """Imports a pack prop's files (several are stacked by prop_geom.pack_piece) and returns, per file, its faces in
    Godot axes with each face's linear colour and area, and the source's triangles. With max_triangles, every
    object gets a Decimate (collapse) modifier at the ratio that brings the prop under it."""
    groups = []
    for f in p["files"]:
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(env / f))
        groups.append([o for o in bpy.data.objects if o not in before and o.type == "MESH"])
    src = sum(len(pl.vertices) - 2 for objs in groups for o in objs for pl in o.data.polygons)
    if max_triangles and src > max_triangles:
        for objs in groups:
            for o in objs:
                mod = o.modifiers.new("decimate", "DECIMATE")
                mod.ratio = max_triangles / src
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    cache: dict = {}
    parts = []
    for objs in groups:
        part = {"verts": [], "faces": [], "rgb": [], "area": []}
        for o in objs:
            ev = o.evaluated_get(dg)
            me = ev.to_mesh()
            mw = o.matrix_world
            base = len(part["verts"])
            for v in me.vertices:
                w = mw @ v.co
                part["verts"].append((w.x, w.z, -w.y))
            uv = me.uv_layers.active.data if me.uv_layers.active else None
            slots = [s.material for s in o.material_slots]
            for pl in me.polygons:
                mat = slots[pl.material_index] if pl.material_index < len(slots) else None
                kind, val = _material_colour(np, mat, cache)
                if kind == "img" and uv is not None:
                    us = [uv[li].uv for li in pl.loop_indices]
                    u = sum(c[0] for c in us) / len(us)
                    v = sum(c[1] for c in us) / len(us)
                    h, w_ = val.shape[0], val.shape[1]
                    rgb = tuple(float(c) for c in val[int(v % 1.0 * h) % h, int(u % 1.0 * w_) % w_])
                else:
                    rgb = tuple(val) if kind == "const" else (0.8, 0.8, 0.8)
                part["faces"].append([base + i for i in pl.vertices])
                part["rgb"].append(rgb)
                part["area"].append(pl.area)
            ev.to_mesh_clear()
        parts.append(part)
    return parts, src


def export_prop(bpy, bmesh, d: dict, spec: dict, mats: dict, glb: Path) -> dict:
    """One described prop (prop_geom.describe) as one GLB: its mesh, its collider(s) `<id>_col<n>-convcolonly`, a
    `LightAnchor` empty at its emissive part. Returns what the file holds, measured in Blender."""
    kit_build.clear_scene(bpy)
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    scene = bpy.context.scene
    objs = {m["name"]: kit_build.mesh_object(bpy, scene, m, spec, mats) for m in d["meshes"]}
    bpy.context.view_layer.update()
    cols = []
    for c in d["colliders"]:
        obj, faces, verts = kit_build.collider_object(bpy, bmesh, scene, c, None)
        cols.append({"name": c["name"], "faces": faces, "verts": verts})
    if d.get("light_anchor"):
        e = bpy.data.objects.new(prop_geom.LIGHT_ANCHOR, None)
        e.location = kit_build.to_blender(d["light_anchor"])
        scene.collection.objects.link(e)
    lit = [r for r in d["roles"] if prop_geom.is_emissive(spec, r)]
    set_emission(mats, spec, lit[0] if lit else None)
    glb.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(glb), **kit_build.KIT_EXPORT_OPTIONS)
    return {
        "glb": str(glb),
        "objects": {o.name: {"triangles": sum(len(pl.vertices) - 2 for pl in o.data.polygons),
                             "materials": [s.material.name for s in o.material_slots if s.material]}
                    for o in objs.values()},
        "colliders": cols,
    }
