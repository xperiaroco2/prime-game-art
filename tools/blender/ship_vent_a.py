"""The throat vent's body, way A (art #263 station 1; docs/ship.md "Station 1"): Meshy's multi-image-to-3D body
(batch 2026-10-23-ship-vent-a-body) cleaned into the game body the vent builder (ship_interior_vent.py) imports.

    blender -b --python ship_vent_a.py -- --in <meshy.glb> --out <dir> [--tris 4000] [--tex 2048] [--no-bake]

In the piece's frame (Blender x = u along the wall, -y = v out of it, z = h over the deck; the deck at 0 here, the
builder adds FLOOR): the full model is welded, its specks (loose bits) dropped, scaled to 1.60 m wide with the box's
top at 1.608, its back on the wall (v 0) and cut along the throat wall's chamfer (vertical to BEND, then IN in at
TOP); the column's top part (bar, scanner, lamp) is raised RAISE with the plain panel and the bar stretched, and the
lamp is moved out until it clears the chamfer. A decimated copy (`--tris`) with a fresh Smart UV layout is baked from
the full model (albedo, roughness, metallic, a tangent normal; the plush's lesson, docs/props.md: decimating Meshy's
GLB in place makes triangles sample the next island's texels), and an emission map is masked from the albedo's
glow colours. The driven glows get their own faces and materials where a region can be cut: `lamp` (the red dome),
`band` (the bar's glass) and `hand` (the scanner's pad). Writes <out>/body.glb, <out>/textures/*.png,
<out>/clean.json (the numbers the builder and the checks need) and <out>/body.blend."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector

BEND, IN, TOP = 1.45, 0.55, 2.30      # the throat wall (ship.toml [throat]): checked against the builder's numbers
WIDTH, BOX_TOP, DEPTH = 1.60, 1.608, 0.415
COL_U0 = 0.466                        # the column from u 46.6 (the concept traced at 160 cm)
RAISE, RAISE_AT = 0.20, 0.95          # the column's top part up 20 cm, cut at 0.95 m (the bar's glass, a plain panel)
LAMP_DROP = 0.19                      # the lamp (rings and dome) is the column's top 19 cm (body_side traced)


def cv(h: float) -> float:
    return 0.0 if h <= BEND else (h - BEND) / (TOP - BEND) * IN


def args() -> dict:
    a = sys.argv[sys.argv.index("--") + 1:]
    get = lambda k, d=None: a[a.index(k) + 1] if k in a else d  # noqa: E731
    return {"in": Path(get("--in")), "out": Path(get("--out")), "tris": int(get("--tris", 4000)),
            "tex": int(get("--tex", 2048)), "bake": "--no-bake" not in a}


def load(path: Path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(path))
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    for o in bpy.context.scene.objects:
        o.select_set(o in objs)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    hi = bpy.context.view_layer.objects.active
    hi.parent = None
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for o in list(bpy.context.scene.objects):
        if o is not hi:
            bpy.data.objects.remove(o, do_unlink=True)
    hi.name = "hi"
    return hi


def bounds(verts):
    co = np.array([v.co[:] for v in verts])
    return co.min(0), co.max(0)


def clean(hi, rep: dict) -> None:
    bm = bmesh.new()
    bm.from_mesh(hi.data)
    rep["meshy_tris"] = sum(len(f.verts) - 2 for f in bm.faces)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    # the specks: loose bits under 40 faces or 3 cm across (in Meshy units: scaled below, so by share of the size)
    lo, hi_ = bounds(bm.verts)
    size = float(np.linalg.norm(hi_ - lo))
    seen, drop, parts = set(), [], 0
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, isl = [f], []
        seen.add(f.index)
        while stack:
            g = stack.pop()
            isl.append(g)
            for e in g.edges:
                for n in e.link_faces:
                    if n.index not in seen:
                        seen.add(n.index)
                        stack.append(n)
        parts += 1
        pts = np.array([v.co[:] for g in isl for v in g.verts])
        if len(isl) < 40 or np.linalg.norm(pts.max(0) - pts.min(0)) < 0.015 * size:
            drop += isl
    rep["loose_parts"], rep["dropped_faces"] = parts, len(drop)
    bmesh.ops.delete(bm, geom=list(set(drop)), context="FACES")
    bm.to_mesh(hi.data)
    bm.free()


def fit(hi, rep: dict) -> None:
    me = hi.data
    lo, up = bounds(me.vertices)
    ext = up - lo
    rep["meshy_extent"] = ext.round(4).tolist()
    if not (ext[0] > ext[1] and ext[2] > ext[1]):
        raise SystemExit(f"ship_vent_a: unexpected orientation, extent {ext}")
    s = WIDTH / ext[0]
    cx = (lo[0] + up[0]) / 2
    for v in me.vertices:   # u centred, h from 0, the back (max y: the front faces -y) on y 0
        v.co = Vector(((v.co.x - cx) * s, (v.co.y - up[1]) * s, (v.co.z - lo[2]) * s))
    co = np.array([v.co[:] for v in me.vertices])
    box_top = float(co[co[:, 0] < COL_U0 - 0.05, 2].max())
    k = BOX_TOP / box_top
    depth = float(-co[:, 1].min())
    rep["uniform_scale"], rep["box_top_uniform"], rep["depth_uniform"] = round(s, 5), round(box_top, 4), round(depth, 4)
    rep["h_scale"] = round(k, 4)
    # the frame's face (the 95th percentile of the box's front at mid height) to the concept's 41.5 deep
    mid = co[(np.abs(co[:, 2] - 0.9) < 0.1) & (co[:, 0] < COL_U0 - 0.05), 1]
    face = float(-np.percentile(mid, 5))
    kv = DEPTH / face
    rep["frame_face_uniform"], rep["v_scale"] = round(face, 4), round(kv, 4)
    for v in me.vertices:   # heights to the box's top 1.608 (the width stays 1.60), depth to the frame's 41.5
        v.co.z *= k
        v.co.y *= kv
    me.update()


def raise_column(hi, rep: dict) -> None:
    """The column's top part up RAISE: the faces across RAISE_AT bisected, everything of the column above moved."""
    bm = bmesh.new()
    bm.from_mesh(hi.data)
    col = [f for f in bm.faces if all(v.co.x > COL_U0 - 0.02 for v in f.verts)]
    geom = list({e for f in col for e in f.edges}) + col + list({v for f in col for v in f.verts})
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, RAISE_AT), plane_no=(0, 0, 1))
    moved = 0
    for v in bm.verts:
        if v.co.x > COL_U0 - 0.02 and v.co.z > RAISE_AT + 1e-5:
            v.co.z += RAISE
            moved += 1
    bm.to_mesh(hi.data)
    bm.free()
    co = np.array([v.co[:] for v in hi.data.vertices])
    rep["raised_verts"], rep["column_top"] = moved, round(float(co[co[:, 0] > COL_U0, 2].max()), 4)


def lamp_out(hi, rep: dict) -> None:
    """The lamp (the column's top LAMP_DROP) out along v until its back clears the wall's chamfer by 1 cm."""
    me = hi.data
    co = np.array([v.co[:] for v in me.vertices])
    top = float(co[co[:, 0] > COL_U0, 2].max())
    sel = [v for v in me.vertices if v.co.x > COL_U0 - 0.02 and v.co.z > top - LAMP_DROP]
    back = min(-v.co.y for v in sel)
    need = max(0.0, max(cv(v.co.z) for v in sel) + 0.01 - back)
    for v in sel:
        v.co.y -= need
    me.update()
    rep["lamp"] = {"top": round(top, 4), "back_v": round(back, 4), "moved_out": round(need, 4),
                   "verts": len(sel), "z0": round(top - LAMP_DROP, 4)}


def wall_cut(hi, rep: dict) -> None:
    """The back flat on the wall: every vertex behind the wall's face (v < 0 below BEND, v < cv(h) on the chamfer)
    is moved onto it along v, so the body's back follows the wall with no holes."""
    moved = 0
    for v in hi.data.vertices:
        w = cv(v.co.z)
        if -v.co.y < w:
            v.co.y = -w
            moved += 1
    hi.data.update()
    rep["wall_projected_verts"] = moved


def scan(rep: dict, hi) -> None:
    """The numbers the builder needs, by rays from the front: the caps' heights (peaks of the depth along the caps'
    column), the well's back, the opening's sides, the bar's glass."""
    dg = bpy.context.evaluated_depsgraph_get()
    sc = bpy.context.scene

    def depth(u, h):
        ok, loc, *_ = sc.ray_cast(dg, Vector((u, -2.0, h)), Vector((0, 1, 0)))
        return -loc.y if ok else None

    hs = np.arange(0.20, 1.60, 0.005)
    best = None
    for u in [*np.arange(-0.53, -0.43, 0.005), *np.arange(0.27, 0.37, 0.005)]:
        prof = [depth(u, h) or 0.0 for h in hs]
        var = float(np.var(prof))
        if best is None or var > best[0]:
            best = (var, float(u), prof)
    _, cu, prof = best
    peaks = [round(float(hs[i]), 3) for i in range(2, len(hs) - 2)
             if prof[i] >= max(prof[i - 2:i + 3]) and prof[i] > np.median(prof) + 0.01]
    merged = []
    for p in peaks:
        if merged and p - merged[-1][-1] < 0.04:
            merged[-1].append(p)
        else:
            merged.append([p])
    rep["caps"] = {"u": round(cu, 3), "best_u_side": "l" if cu < 0 else "r", "h": [round(sum(m) / len(m), 3) for m in merged],
                   "front_v": round(max(prof), 4)}
    rep["well_back_v"] = round(min(depth(u, 0.9) or 9 for u in np.arange(-0.3, 0.1, 0.05)), 4)
    rep["front_v"] = {f"{u:.2f}": round(depth(u, 0.9) or -1, 4) for u in np.arange(-0.78, 0.8, 0.04)}


def bake_low(hi, a: dict, rep: dict) -> None:
    out = a["out"]
    (out / "textures").mkdir(parents=True, exist_ok=True)
    low = hi.copy()
    low.data = hi.data.copy()
    low.name = "body"
    bpy.context.scene.collection.objects.link(low)
    bpy.context.view_layer.objects.active = low
    for o in bpy.context.scene.objects:
        o.select_set(o is low)
    mod = low.modifiers.new("dec", "DECIMATE")
    mod.ratio = min(1.0, a["tris"] / max(1, sum(len(p.vertices) - 2 for p in low.data.polygons)))
    bpy.ops.object.modifier_apply(modifier=mod.name)
    tri = low.modifiers.new("tri", "TRIANGULATE")
    bpy.ops.object.modifier_apply(modifier=tri.name)
    while low.data.uv_layers:
        low.data.uv_layers.remove(low.data.uv_layers[0])
    low.data.uv_layers.new(name="UVMap")
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004)
    bpy.ops.object.mode_set(mode="OBJECT")
    for poly in low.data.polygons:
        poly.use_smooth = False
    low.data.materials.clear()
    rep["game_tris"] = len(low.data.polygons)
    if not a["bake"]:
        return
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 4
    size = a["tex"]
    mat = bpy.data.materials.new("vent_a_body")
    mat.use_nodes = True
    low.data.materials.append(mat)
    nt = mat.node_tree
    imgs = {}
    for key, cs in (("albedo", "sRGB"), ("rough", "Non-Color"), ("metal", "Non-Color"), ("normal", "Non-Color"),
                    ("emission", "sRGB")):
        img = bpy.data.images.new(f"vent_a_{key}", size, size, alpha=False, float_buffer=False)
        img.colorspace_settings.name = cs
        imgs[key] = img
    tex = nt.nodes.new("ShaderNodeTexImage")
    nt.nodes.active = tex
    for o in sc.objects:
        o.select_set(o in (hi, low))
    sc.view_layers[0].objects.active = low
    bk = sc.render.bake
    bk.use_selected_to_active, bk.cage_extrusion, bk.max_ray_distance, bk.margin = True, 0.02, 0.05, 8

    def run(kind, img, **kw):
        tex.image = img
        bpy.ops.object.bake(type=kind, **kw)
        img.filepath_raw = str(out / "textures" / f"{img.name}.png")
        img.file_format = "PNG"
        img.save()

    run("DIFFUSE", imgs["albedo"], pass_filter={"COLOR"})
    run("ROUGHNESS", imgs["rough"])
    run("NORMAL", imgs["normal"], normal_space="TANGENT")
    run("EMIT", imgs["emission"])   # Meshy's own emission map
    # metallic: each of the full model's materials emits its metallic channel for one EMIT bake
    for m in hi.data.materials:
        if not (m and m.use_nodes):
            continue
        bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        outn = next((n for n in m.node_tree.nodes if n.type == "OUTPUT_MATERIAL"), None)
        if not (bsdf and outn):
            continue
        em = m.node_tree.nodes.new("ShaderNodeEmission")
        src = bsdf.inputs["Metallic"]
        if src.links:
            m.node_tree.links.new(src.links[0].from_socket, em.inputs["Color"])
        else:
            em.inputs["Color"].default_value = (src.default_value,) * 3 + (1.0,)
        m.node_tree.links.new(em.outputs[0], outn.inputs["Surface"])
    run("EMIT", imgs["metal"])
    em = np.array(imgs["emission"].pixels[:], dtype=np.float32)
    rep["emission_max"] = round(float(em.max()), 3)
    if em.max() < 0.05:   # no emission map came through: mask the albedo's glow colours instead
        emission(imgs["albedo"], out, size)
        rep["emission_route"] = "albedo mask"
    else:
        rep["emission_route"] = "meshy emission baked"
    shade(low, mat, imgs, out)
    glows(low, imgs["albedo"], rep)


def emission(albedo, out: Path, size: int) -> None:
    """The emission map: the albedo's glow colours (saturated and bright: the cyan strips, the bar, the red dome, the
    hand), black elsewhere."""
    px = np.array(albedo.pixels[:], dtype=np.float32).reshape(size, size, 4)[..., :3]
    mx, mn = px.max(-1), px.min(-1)
    sat = (mx - mn) / np.maximum(mx, 1e-4)
    glow = ((sat > 0.55) & (mx > 0.55)) | (mn > 0.85)
    em = np.where(glow[..., None], px, 0.0)
    img = bpy.data.images.new("vent_a_emission", size, size, alpha=False)
    img.pixels[:] = np.concatenate([em, np.ones((size, size, 1), np.float32)], -1).ravel()
    img.filepath_raw = str(out / "textures" / "vent_a_emission.png")
    img.file_format = "PNG"
    img.save()


def shade(low, mat, imgs, out: Path) -> None:
    nt = mat.node_tree
    nt.nodes.clear()
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(bsdf.outputs[0], outn.inputs["Surface"])

    def tex(img, cs="Non-Color"):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = img
        img.colorspace_settings.name = cs
        return t
    nt.links.new(tex(imgs["albedo"], "sRGB").outputs[0], bsdf.inputs["Base Color"])
    nt.links.new(tex(imgs["rough"]).outputs[0], bsdf.inputs["Roughness"])
    nt.links.new(tex(imgs["metal"]).outputs[0], bsdf.inputs["Metallic"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(tex(imgs["normal"]).outputs[0], nm.inputs["Color"])
    nt.links.new(nm.outputs[0], bsdf.inputs["Normal"])
    em = bpy.data.images.load(str(out / "textures" / "vent_a_emission.png"))
    nt.links.new(tex(em, "sRGB").outputs[0], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = 1.5


def glows(low, albedo, rep: dict) -> None:
    """The driven glows as their own faces where a region can be cut: per face, the albedo at its UV centre and its
    place; each a copy of the body's material named for the game (`vent_a_body__lamp`, ...)."""
    size = albedo.size[0]
    px = np.array(albedo.pixels[:], dtype=np.float32).reshape(size, size, 4)[..., :3]
    uv = low.data.uv_layers[0].data
    lamp_z0 = rep["lamp"]["z0"]
    kinds = {"lamp": [], "band": [], "hand": []}
    for poly in low.data.polygons:
        c = sum((uv[i].uv for i in poly.loop_indices), Vector((0, 0))) / poly.loop_total
        r, g, b = px[min(size - 1, int(c.y * size)), min(size - 1, int(c.x * size))]
        p = poly.center
        if p.x < COL_U0 - 0.02:
            continue
        if p.z > lamp_z0 and r > 0.45 and g < 0.25 and b < 0.25:
            kinds["lamp"].append(poly.index)
        elif g > 0.4 and r < 0.4 and b < 0.4:
            kinds["band"].append(poly.index)
        elif b > 0.45 and g > 0.35 and r < 0.3:
            kinds["hand"].append(poly.index)
    base = low.data.materials[0]
    for k, faces in kinds.items():
        if not faces:
            continue
        m = base.copy()
        m.name = f"vent_a_body__{k}"
        low.data.materials.append(m)
        slot = len(low.data.materials) - 1
        for i in faces:
            low.data.polygons[i].material_index = slot
    rep["glow_faces"] = {k: len(v) for k, v in kinds.items()}


def main() -> None:
    a = args()
    a["out"].mkdir(parents=True, exist_ok=True)
    rep: dict = {"source": a["in"].as_posix()}
    hi = load(a["in"])
    clean(hi, rep)
    fit(hi, rep)
    raise_column(hi, rep)
    lamp_out(hi, rep)
    wall_cut(hi, rep)
    hi.data.update()
    scan(rep, hi)
    rep["full_tris"] = sum(len(p.vertices) - 2 for p in hi.data.polygons)
    bake_low(hi, a, rep)
    lo, up = bounds(hi.data.vertices)
    rep["bounds"] = {"min": lo.round(4).tolist(), "max": up.round(4).tolist()}
    bpy.ops.wm.save_as_mainfile(filepath=str(a["out"] / "body.blend"))
    if a["bake"]:
        for o in bpy.context.scene.objects:
            o.select_set(o.name == "body")
        bpy.ops.export_scene.gltf(filepath=str(a["out"] / "body.glb"), export_format="GLB", use_selection=True,
                                  export_yup=True, export_apply=True, export_materials="EXPORT")
    (a["out"] / "clean.json").write_text(json.dumps(rep, indent=1), encoding="utf-8", newline="\n")
    print("VENTA " + json.dumps({k: rep[k] for k in rep if k != "front_v"}))


if __name__ == "__main__":
    main()
