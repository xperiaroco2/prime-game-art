"""Cloth and shoes only from a Meshy outfit model (art #196, clothes step 2): imports Meshy's textured GLB (the whole
figure, skin and all) and welds its UV seams, tells skin from cloth per face by its texels' colour (clothes_geom.is_skin: teal and mint),
deletes the skin (head, hands, neck and ankles) and the cloth specks left on it (the eye whites), keeps the garment
and the shoes as pieces (the shoes are the pieces below the ankle band, or the pale faces low down when the hems sit on them; with --split-z the garment is cut at that
height into a top and a bottom), drops floaters, removes the openings' spikes and fills small holes, decimates each piece to its triangle target
and bakes Meshy's texture onto fresh UVs (matte: the roughness has a fabric floor). The openings at the collar, cuffs and ankles stay open (nothing is filled). Scaled so the whole figure is
--height m tall, its feet on z = 0 and its footprint centred, facing -Y as imported.

    blender -b --factory-startup --python tools/blender/clothes_clean.py -- MODEL.glb OUT_DIR --height 1.80
        [--garment-tris 8000] [--shoe-tris 1600] [--split-z 0.0] [--top-tris 4500]
        [--ray 0.01] [--rough-floor 0.85] [--spike-deg 40] [--hole-sides 10]

Writes OUT_DIR/cloth.blend, cloth.glb and cloth.json (per piece its triangles, faces dropped and why); prints
CLOTHES_CLEAN lines.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clothes_geom as cg  # noqa: E402


def say(*a) -> None:
    print("CLOTHES_CLEAN", *a, flush=True)


def base_image(obj) -> bpy.types.Image:
    for slot in obj.material_slots:
        nt = slot.material.node_tree
        bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        link = bsdf.inputs["Base Color"].links
        if link and link[0].from_node.type == "TEX_IMAGE":
            return link[0].from_node.image
    raise SystemExit("CLOTHES_CLEAN no base colour texture")


def face_skin(me, img) -> tuple[np.ndarray, np.ndarray]:
    """Per triangle: skin when most of its four texel samples (the centroid and halfway to each corner) are; and
    strong when its centroid's colour is saturated (denim, burgundy: the garment, never the white shoes)."""
    w, h = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)[:, :, :3]
    uv = np.zeros(len(me.loops) * 2, dtype=np.float32)
    me.uv_layers.active.data.foreach_get("uv", uv)
    if any(p.loop_total != 3 for p in me.polygons):
        raise SystemExit("CLOTHES_CLEAN the model is not all triangles (the texel samples assume three loops a face)")
    uv = uv.reshape(-1, 3, 2)
    c = uv.mean(axis=1, keepdims=True)
    samples = np.concatenate([c, (c + uv) / 2.0], axis=1).reshape(-1, 2)
    x = np.clip((samples[:, 0] % 1.0) * w, 0, w - 1).astype(int)
    y = np.clip((samples[:, 1] % 1.0) * h, 0, h - 1).astype(int)
    rgb = px[y, x]
    votes = cg.skin_mask(rgb).reshape(-1, 4)
    cen = rgb.reshape(-1, 4, 3)[:, 0]
    sat = (cen.max(axis=1) - cen.min(axis=1)) / np.maximum(cen.max(axis=1), 1e-9)
    return votes.sum(axis=1) > 2, sat > 0.35


def components(bm, faces) -> list[list]:
    """Edge-connected groups of the given faces."""
    want = set(f.index for f in faces)
    seen, out = set(), []
    for f in faces:
        if f.index in seen:
            continue
        group, stack = [], [f]
        seen.add(f.index)
        while stack:
            g = stack.pop()
            group.append(g)
            for e in g.edges:
                for n in e.link_faces:
                    if n.index in want and n.index not in seen:
                        seen.add(n.index)
                        stack.append(n)
        out.append(group)
    return out


def decimate(obj, target: int) -> None:
    tris = len(obj.data.polygons)
    if tris <= target:
        return
    mod = obj.modifiers.new("dec", "DECIMATE")
    mod.ratio = target / tris
    mod.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)


def despike(bm, angle_deg: float, rounds: int = 4) -> int:
    """Removes the thin spikes the skin cut leaves on the openings (the collar's top edge, the cuffs' ends): a
    boundary vertex whose two boundary edges meet at less than angle_deg and that has at most two faces is a spike's
    tip; its faces go, for a few rounds (a spike two triangles long). Returns the faces removed."""
    import math
    gone = 0
    for _ in range(rounds):
        tips = []
        for v in bm.verts:
            be = [e for e in v.link_edges if e.is_boundary]
            if len(be) != 2 or len(v.link_faces) > 2:
                continue
            a, b = (e.other_vert(v).co - v.co for e in be)
            if a.length > 0 and b.length > 0 and math.degrees(a.angle(b)) < angle_deg:
                tips.append(v)
        faces = list({f for v in tips for f in v.link_faces})
        if not faces:
            break
        gone += len(faces)
        bmesh.ops.delete(bm, geom=faces, context="FACES")
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    return gone


def fill_holes(bm, sides: int, start: int) -> int:
    """Fills the small holes inside the cloth (boundary loops of at most sides edges; the collar, cuffs and hems are
    far longer), each new face's UVs taken from the same vertex in a face beside it. The new faces get the indices
    from start on (the old faces keep theirs: the per-face masks are read by index). Returns the faces added."""
    uv = bm.loops.layers.uv.active
    old = set(bm.faces)
    bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=sides)
    new = [f for f in bm.faces if f not in old]
    if uv is not None:
        for f in new:
            for loop in f.loops:
                src = next((lp for lp in loop.vert.link_loops if lp.face in old), None)
                if src is not None:
                    loop[uv].uv = src[uv].uv
    if new:
        bmesh.ops.triangulate(bm, faces=new)
    new = [f for f in bm.faces if f not in old]
    for k, f in enumerate(new):
        f.index = start + k
    return len(new)


def bake_low(hi, target: int, size: int, ray: float, rough_floor: float):
    """A decimated copy of hi with fresh UVs and hi's base colour, roughness and normal baked onto it (Cycles,
    selected to active). Decimating Meshy's own UVs in place garbles the stripes and the laces (texels pulled across
    islands), so the low mesh never keeps them. ray is the bake's reach: B's 0.04 m reached the denim beside the
    arm and left a dark smear on the inner right sleeve. The baked roughness is raised to at least rough_floor
    (fabric: Meshy's map read as leather gloss) and the specular is lowered, so the denim stays matte."""
    lo = hi.copy()
    lo.data = hi.data.copy()
    bpy.context.collection.objects.link(lo)
    decimate(lo, target)
    for o in bpy.context.scene.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = lo
    lo.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.004)
    bpy.ops.object.mode_set(mode="OBJECT")
    lo.data.materials.clear()
    mat = bpy.data.materials.new(hi.name + "_baked")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Specular IOR Level"].default_value = 0.3
    lo.data.materials.append(mat)
    imgs = {}
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 4
    sc.cycles.device = "CPU"
    bk = sc.render.bake
    bk.use_selected_to_active = True
    bk.cage_extrusion = min(0.01, ray)
    bk.max_ray_distance = ray
    bk.margin = 8
    hi.select_set(True)
    lo.select_set(True)
    bpy.context.view_layer.objects.active = lo
    for kind, colour in (("DIFFUSE", "sRGB"), ("ROUGHNESS", "Non-Color"), ("NORMAL", "Non-Color")):
        img = bpy.data.images.new(f"{hi.name}_{kind.lower()}", size, size, alpha=False)
        img.colorspace_settings.name = colour
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = img
        nt.nodes.active = node
        if kind == "DIFFUSE":
            bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"})
        else:
            bpy.ops.object.bake(type=kind)
        imgs[kind] = node
        if kind == "ROUGHNESS" and rough_floor > 0:
            px = np.array(img.pixels[:], dtype=np.float32).reshape(-1, 4)
            px[:, :3] = np.maximum(px[:, :3], rough_floor)
            img.pixels[:] = px.ravel()
            img.update()
    nt.links.new(imgs["DIFFUSE"].outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(imgs["ROUGHNESS"].outputs["Color"], bsdf.inputs["Roughness"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(imgs["NORMAL"].outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    nt.nodes.active = imgs["DIFFUSE"]  # Workbench's texture view and the review shots show the active image
    for img in (n.image for n in imgs.values()):
        img.pack()
    name = hi.name
    bpy.data.objects.remove(hi)
    lo.name = lo.data.name = name
    return lo


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("model", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--height", type=float, required=True, help="the whole figure's height in m (the base body's)")
    ap.add_argument("--garment-tris", type=int, default=8000)
    ap.add_argument("--top-tris", type=int, default=4500, help="with --split-z: the top's share of --garment-tris")
    ap.add_argument("--shoe-tris", type=int, default=1600, help="both shoes together")
    ap.add_argument("--split-z", type=float, default=0.0, help="cut the garment into top and bottom at this z (m)")
    ap.add_argument("--bake", type=int, default=2048, help="the baked maps' size in px")
    ap.add_argument("--skin-speck", type=float, default=0.004,
                    help="skin pieces under this share of the faces become cloth (the ankle bands are larger)")
    ap.add_argument("--ray", type=float, default=0.01, help="the bake's max ray distance in m (0.04 smeared the sleeve)")
    ap.add_argument("--rough-floor", type=float, default=0.85, help="the baked roughness's floor (fabric, matte)")
    ap.add_argument("--spike-deg", type=float, default=40.0, help="a boundary tip sharper than this is a spike (0: keep)")
    ap.add_argument("--hole-sides", type=int, default=10, help="fill holes of at most this many edges (0: none)")
    ap.add_argument("--speck", type=float, default=0.02, help="pieces under this share of the faces are dropped (the eye whites are about 1 %%)")
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(args.model))
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    for o in bpy.context.scene.objects:
        o.select_set(o in meshes)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for o in list(bpy.context.scene.objects):
        if o is not obj:
            bpy.data.objects.remove(o)
    me = obj.data
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    lo, hi = co.min(axis=0), co.max(axis=0)
    scale = args.height / (hi[2] - lo[2])
    co = (co - [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]]) * scale
    me.vertices.foreach_set("co", co.ravel())
    me.update()
    total = len(me.polygons)
    say(f"model={args.model.name} tris={total} scale={scale:.4f} height={args.height}")

    skin, strong = face_skin(me, base_image(obj))
    bm = bmesh.new()
    bm.from_mesh(me)
    # glTF splits the vertices at every UV seam, so the islands are not edge-connected: weld them (UVs are per loop,
    # so welding keeps them); the face order, and so skin[], is unchanged
    welded = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    welded -= len(bm.verts)
    # a weld that collapses a face would shift every later face's index against skin[] and strong[]
    if len(bm.faces) != total:
        raise SystemExit(f"CLOTHES_CLEAN the UV weld removed {total - len(bm.faces)} faces: the per-face masks would shift")
    bm.faces.ensure_lookup_table()
    bm.faces.index_update()
    report = {"welded_verts": welded, "model": str(args.model), "tris_in": total, "scale": scale, "height": args.height}
    # skin specks inside the cloth (a shade that reads teal) become cloth; cloth specks on the skin (the eye whites,
    # the pupils) become skin, so they go with it
    for flag, label, share in ((True, "skin_specks_to_cloth", args.skin_speck), (False, "cloth_specks_to_skin", args.speck)):
        groups = components(bm, [f for f in bm.faces if skin[f.index] == flag])
        small = [g for g in groups if len(g) < share * total]
        for g in small:
            for f in g:
                skin[f.index] = not flag
        report[label] = sum(len(g) for g in small)
    dead = [f for f in bm.faces if skin[f.index]]
    report["skin_faces"] = len(dead)
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    report["spike_faces"] = despike(bm, args.spike_deg) if args.spike_deg > 0 else 0
    report["hole_faces"] = fill_holes(bm, args.hole_sides, total) if args.hole_sides > 0 else 0
    strong = np.concatenate([strong, np.zeros(report["hole_faces"], dtype=bool)])  # a filled hole is garment
    say(f"spikes={report['spike_faces']} faces removed, holes={report['hole_faces']} faces added")
    bm.faces.ensure_lookup_table()
    groups = components(bm, list(bm.faces))
    groups.sort(key=len, reverse=True)
    keep = [g for g in groups if len(g) >= args.speck * total]
    report["floater_faces"] = sum(len(g) for g in groups if len(g) < args.speck * total)
    zs = [max(v.co.z for f in g for v in f.verts) for g in keep]
    ankle = 0.12 * args.height
    shoes = [g for g, z in zip(keep, zs) if z < ankle]
    garment = [g for g, z in zip(keep, zs) if z >= ankle]
    report["groups"] = [{"faces": len(g), "top_z": round(z, 4)} for g, z in zip(keep, zs)]
    tag = {}
    if not shoes:
        # the hems sit on the shoes (no skin between): the shoes are the pale faces low down (white or off-white;
        # the hems are denim or burgundy), kept as the pieces of them big enough to be a shoe
        low = [f for g in garment for f in g if f.calc_center_median().z < 0.11 * args.height and not strong[f.index]]
        parts = [g for g in components(bm, low) if len(g) >= args.speck * total]
        ids = set(f.index for g in parts for f in g)
        garment = [[f for f in g if f.index not in ids] for g in garment]
        shoes = parts
        report["shoes_by_colour"] = [len(g) for g in parts]
        say(f"shoes split off by colour: {[len(g) for g in parts]} faces")
    for g in shoes:
        for f in g:
            tag[f.index] = "shoes"
    for g in garment:
        for f in g:
            c = f.calc_center_median()
            tag[f.index] = ("top" if c.z >= args.split_z else "bottom") if args.split_z else "garment"
    drop = [f for f in bm.faces if f.index not in tag]
    names = [tag[f.index] for f in bm.faces if f.index in tag]
    bmesh.ops.delete(bm, geom=drop, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(me)
    bm.free()
    me.update()
    # one object per piece
    names_arr = np.array(names)
    pieces = {}
    for name in sorted(set(names)):
        o = obj.copy()
        o.data = me.copy()
        o.name = o.data.name = name
        bpy.context.collection.objects.link(o)
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if names_arr[f.index] != name], context="FACES")
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
        bm.to_mesh(o.data)
        bm.free()
        pieces[name] = o
    bpy.data.objects.remove(obj)
    targets = {"garment": args.garment_tris, "top": args.top_tris, "bottom": args.garment_tris - args.top_tris,
               "shoes": args.shoe_tris}
    report["pieces"] = {}
    for name, o in pieces.items():
        before = len(o.data.polygons)
        if before > targets[name]:
            o = pieces[name] = bake_low(o, targets[name], args.bake, args.ray, args.rough_floor)
        cs = np.zeros(len(o.data.vertices) * 3)
        o.data.vertices.foreach_get("co", cs)
        cs = cs.reshape(-1, 3)
        report["pieces"][name] = {"tris_before": before, "tris": len(o.data.polygons),
                                  "min": cs.min(axis=0).round(4).tolist(), "max": cs.max(axis=0).round(4).tolist()}
        say(f"piece={name} tris {before} -> {len(o.data.polygons)}")
    report["tris_total"] = sum(p["tris"] for p in report["pieces"].values())
    say(f"skin={report['skin_faces']} floaters={report['floater_faces']} total={report['tris_total']}")
    args.out.mkdir(parents=True, exist_ok=True)
    for img in bpy.data.images:
        if img.source == "FILE" or img.packed_file is None:
            img.pack()
    bpy.ops.wm.save_as_mainfile(filepath=str(args.out / "cloth.blend"), compress=True)
    bpy.ops.export_scene.gltf(filepath=str(args.out / "cloth.glb"), export_format="GLB", export_yup=True,
                              export_apply=True, export_materials="EXPORT", export_image_format="AUTO")
    (args.out / "cloth.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    say("wrote", args.out)


main()
