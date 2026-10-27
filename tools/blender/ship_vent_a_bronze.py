"""The throat vent's body, way A, the look step (art #263 station 1, vents-a4; docs/ship.md "Station 1"): Meshy's
mesh kept, its baked albedo replaced by one clean polished bronze, and its painted lights measured so the builder
(ship_interior_vent.py) can lay clean emissive pieces over them.
    blender -b --python ship_vent_a_bronze.py -- --in <body4k dir> --out <dir>
- The bronze: Cycles bakes two masks on the body's own UV (2048 px): the edges (the Bevel node's rounded normal
  against the true normal: 1 on a hard edge, 0 on a flat facet) and the ambient occlusion (5 cm). The albedo is
  BRONZE lerped to EDGE by the edge mask, times the occlusion (AO_MIN .. 1); the well's faces are darkened. Metallic
  METAL, the roughness ROUGH[0] on the facets and ROUGH[1] on the edges; Meshy's normal map kept, its emission dropped.
- The lights: every texel of Meshy's emission map brighter than GLOW_MIN is mapped to its 3D point (the UV triangles
  rasterized), sorted by hue (cyan, red, amber/green), and joined into islands (GRID voxels). Cyan islands outside the
  well and the hand's screen are the frame's strips: each one's centre, long and short axes on the surface, normal
  and half extents (its 3rd..97th percentiles) go into lights.json. The lamp, the band and the hand's screen are the
  boxes of their faces (the materials `__lamp`, `__band`, `__hand` that ship_vent_a.py cut); those faces turn a dark
  glass (not emissive) under the clean pieces.
Writes <out>/body.glb, <out>/textures/*.png, <out>/lights.json (the body's frame: u, v out of the wall, h over the
deck) and <out>/bronze.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ship_interior_vent as V  # noqa: E402

SIZE = 2048
BRONZE = (0.50, 0.29, 0.13)        # linear: the facets' polished bronze
EDGE = (1.00, 0.78, 0.50)          # linear: the hard edges' highlight
AO_MIN = 0.45
METAL, ROUGH = 0.9, (0.36, 0.2)
BEVEL_R = 0.006                    # the edge mask's rounding (m)
EDGE_DOT = (0.97, 0.80)            # bevel . true normal: above the first flat (0), below the second a full edge (1)
ALB_MIN = 0.40                     # the albedo's brightness of a painted (unlit) strip
GLOW_MIN = 0.12                    # the emission map's brightness that counts as a painted light
GRID = 0.012                       # the islands' voxel (m)
MIN_TEXELS = 60                    # a smaller island is a speck
WELL_V = 0.36                      # behind this inside the opening is the well (ship_vent_a_finish.WELL_V)


def arg(k, d=None):
    a = sys.argv[sys.argv.index("--") + 1:]
    return a[a.index(k) + 1] if k in a else d


def pixels(img) -> np.ndarray:
    w, h = img.size
    return np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)


def to_srgb(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def save(arr: np.ndarray, name: str, out: Path, cs: str):
    h, w = arr.shape[:2]
    if arr.ndim == 2:
        arr = np.repeat(arr[..., None], 3, -1)
    img = bpy.data.images.new(name, w, h, alpha=False)
    img.colorspace_settings.name = cs
    img.pixels[:] = np.concatenate([np.clip(arr[..., :3], 0, 1), np.ones((h, w, 1), np.float32)], -1).ravel()
    img.filepath_raw = str(out / "textures" / f"{name}.png")
    img.file_format = "PNG"
    img.save()
    return img


def raster(obj, size: int):
    """Per texel: its 3D point in the body's frame (u, v, h), its face normal (u, v, h), its material index (-1: no
    face)."""
    me = obj.data
    me.calc_loop_triangles()
    uv = me.uv_layers[0].data
    pos = np.zeros((size, size, 3), np.float32)
    nrm = np.zeros((size, size, 3), np.float32)
    mat = np.full((size, size), -1, np.int16)
    for t in me.loop_triangles:
        st = np.array([uv[i].uv[:] for i in t.loops], np.float64) * size
        p3 = np.array([me.vertices[i].co[:] for i in t.vertices], np.float64)
        x0, y0 = np.floor(st.min(0)).astype(int)
        x1, y1 = np.ceil(st.max(0)).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, size - 1), min(y1, size - 1)
        if x1 < x0 or y1 < y0:
            continue
        yy, xx = np.mgrid[y0:y1 + 1, x0:x1 + 1]
        px, py = xx + 0.5, yy + 0.5
        (ax, ay), (bx, by), (cx, cy) = st
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12:
            continue
        w0 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / den
        w1 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / den
        w2 = 1 - w0 - w1
        inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not inside.any():
            continue
        p = w0[..., None] * p3[0] + w1[..., None] * p3[1] + w2[..., None] * p3[2]
        ys, xs = yy[inside], xx[inside]
        q = p[inside]
        pos[ys, xs] = np.stack([q[:, 0], -q[:, 1], q[:, 2]], -1)   # Blender (x, y, z) -> (u, v, h)
        n = t.normal
        nrm[ys, xs] = (n.x, -n.y, n.z)
        mat[ys, xs] = t.material_index
    return pos, nrm, mat


def islands(pts: np.ndarray) -> list[np.ndarray]:
    """Index arrays of the points joined through neighbouring GRID voxels."""
    keys = np.floor(pts / GRID).astype(np.int64)
    vox = {}
    for i, k in enumerate(map(tuple, keys)):
        vox.setdefault(k, []).append(i)
    parent = {k: k for k in vox}

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k
    for k in vox:
        for d in ((1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0), (1, 0, 1), (0, 1, 1), (1, -1, 0), (1, 0, -1), (0, 1, -1)):
            n = (k[0] + d[0], k[1] + d[1], k[2] + d[2])
            if n in vox:
                a, b = find(k), find(n)
                if a != b:
                    parent[a] = b
    groups = {}
    for k, idx in vox.items():
        groups.setdefault(find(k), []).extend(idx)
    return [np.array(g) for g in groups.values()]


def fit(p: np.ndarray, n: np.ndarray) -> dict:
    """An island's oriented rectangle on its surface: centre, long axis, short axis, normal, half extents."""
    nm = n.mean(0)
    nm /= np.linalg.norm(nm) + 1e-9
    c = p.mean(0)
    q = p - c
    q -= np.outer(q @ nm, nm)                       # onto the surface's plane
    w, vec = np.linalg.eigh(q.T @ q)
    a1 = vec[:, 2]
    a2 = np.cross(nm, a1)
    s1, s2 = q @ a1, q @ a2
    lo1, hi1 = np.percentile(s1, [3, 97])
    lo2, hi2 = np.percentile(s2, [3, 97])
    c = c + a1 * (lo1 + hi1) / 2 + a2 * (lo2 + hi2) / 2
    front = float((p @ nm).max())                   # the island's outermost point along the normal
    c = c + nm * (front - c @ nm)
    r = lambda x: [round(float(v), 5) for v in x]   # noqa: E731
    return {"c": r(c), "a1": r(a1), "a2": r(a2), "n": r(nm), "e1": round(float(hi1 - lo1) / 2, 4),
            "e2": round(float(hi2 - lo2) / 2, 4), "texels": int(len(p))}


def bake(obj, img, nodes_fn, kind: str, samples: int):
    """Bake one mask into img with a temporary material on every slot."""
    tmp = bpy.data.materials.new(f"bake_{kind}")
    tmp.use_nodes = True
    nt = tmp.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nodes_fn(nt, out)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.nodes.active = tex
    saved = [s.material for s in obj.material_slots]
    for s in obj.material_slots:
        s.material = tmp
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    with bpy.context.temp_override(active_object=obj, selected_objects=[obj]):
        if kind == "ao":
            bpy.ops.object.bake(type="AO", margin=8, use_clear=True)
        else:
            bpy.ops.object.bake(type="EMIT", margin=8, use_clear=True)
    for s, m in zip(obj.material_slots, saved):
        s.material = m
    return pixels(img)[..., 0].copy()


def edge_nodes(nt, out):
    bev = nt.nodes.new("ShaderNodeBevel")
    bev.inputs["Radius"].default_value = BEVEL_R
    bev.samples = 16
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    nt.links.new(bev.outputs["Normal"], dot.inputs[0])
    nt.links.new(geo.outputs["True Normal"], dot.inputs[1])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = EDGE_DOT
    mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = 0.0, 1.0
    nt.links.new(dot.outputs["Value"], mr.inputs["Value"])
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(mr.outputs["Result"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])


def ao_nodes(nt, out):
    nt.links.new(nt.nodes.new("ShaderNodeBsdfDiffuse").outputs[0], out.inputs["Surface"])


def main() -> None:
    src, out = Path(arg("--in")), Path(arg("--out"))
    (out / "textures").mkdir(parents=True, exist_ok=True)
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.import_scene.gltf(filepath=str(src / "body.glb"))
    body = next(o for o in bpy.context.scene.objects if o.type == "MESH")
    names = [m.name for m in body.data.materials]
    rep = {"in": src.as_posix(), "triangles": sum(len(p.vertices) - 2 for p in body.data.polygons), "materials": names}
    pos, nrm, mat = raster(body, SIZE)
    on = mat >= 0
    em = pixels(bpy.data.images.load(str(src / "textures" / "vent_a_emission.png")))[..., :3]
    if em.shape[0] != SIZE:
        raise SystemExit(f"emission map {em.shape[0]} px, wants {SIZE}")
    u, v, h = pos[..., 0], pos[..., 1], pos[..., 2]
    well = on & (u > V.OPEN_U[0] - 0.02) & (u < V.OPEN_U[1] + 0.02) & (h > V.OPEN_H[0] - 0.02) \
        & (h < V.OPEN_H[1] + 0.02) & (v < WELL_V)
    # the lights: the cut faces' boxes, then the painted cyan islands
    lights = {}
    for suffix in ("lamp", "band", "hand"):
        k = next((i for i, n in enumerate(names) if n.endswith("__" + suffix)), None)
        sel = mat == k
        if suffix == "hand":   # the screen's front faces only (the cut also caught a few on the column's sides)
            sel &= (nrm[..., 1] > 0.6) & (pos[..., 1] > 0.3)
        if k is None or not sel.any():
            raise SystemExit(f"no __{suffix} faces")
        p = pos[sel]
        extra = []
        if suffix == "hand":   # the cut also holds the column's lower strip: the top island is the screen
            ys_, xs_ = np.nonzero(sel)
            groups = sorted((g for g in islands(p) if len(g) >= MIN_TEXELS), key=lambda g: -p[g, 2].mean())
            extra = [fit(p[g], nrm[ys_[g], xs_[g]]) for g in groups[1:]]
            p = p[groups[0]]
            lights["hand_strips"] = extra
        lights[suffix] = {"lo": [round(float(x), 4) for x in np.percentile(p, 1, 0)],
                          "hi": [round(float(x), 4) for x in np.percentile(p, 99, 0)],
                          "n": [round(float(x), 3) for x in nrm[sel].mean(0)]}
    hl, hh = np.array(lights["hand"]["lo"]) - 0.03, np.array(lights["hand"]["hi"]) + 0.03
    lum = em.max(-1)
    alb0 = pixels(bpy.data.images.load(str(src / "textures" / "vent_a_albedo.png")))[..., :3]
    cyan = on & (lum > GLOW_MIN) & (em[..., 2] > em[..., 0] * 1.3) & (em[..., 1] > em[..., 0])
    # or painted: a pale cyan in the albedo (the strips Meshy left unlit)
    cyan |= on & (alb0.max(-1) > ALB_MIN) & (alb0[..., 2] > alb0[..., 0] * 1.35) & (alb0[..., 1] > alb0[..., 0] * 1.15)
    cyan &= ~well & (nrm[..., 1] > 0.5)
    in_hand = np.all((pos >= hl) & (pos <= hh), -1)
    cyan &= ~in_hand
    ys, xs = np.nonzero(cyan)
    strips = []
    for g in islands(pos[ys, xs]):
        if len(g) < MIN_TEXELS:
            continue
        f = fit(pos[ys[g], xs[g]], nrm[ys[g], xs[g]])
        if f["e1"] < 0.015 or f["e2"] < 0.003:
            continue
        strips.append(f)
    strips += lights.pop("hand_strips")
    lights["strips"] = sorted(strips, key=lambda s: (-s["c"][2], s["c"][0]))
    rep["glow_texels"] = {"cyan": int(cyan.sum()), "well": int(well.sum())}
    # the masks
    bpy.context.scene.world = bpy.context.scene.world or bpy.data.worlds.new("w")
    bake_img = bpy.data.images.new("bake", SIZE, SIZE, alpha=False, float_buffer=True)
    bake_img.colorspace_settings.name = "Non-Color"
    edge = bake(body, bake_img, edge_nodes, "edge", 16)
    ao = bake(body, bake_img, ao_nodes, "ao", 32)
    edge = np.clip(edge, 0, 1)
    ao = np.clip(ao, 0, 1)
    rep["edge_mean"], rep["ao_mean"] = float(edge[on].mean()), float(ao[on].mean())
    alb = (np.array(BRONZE) * (1 - edge[..., None]) + np.array(EDGE) * edge[..., None]) \
        * (AO_MIN + (1 - AO_MIN) * ao[..., None])
    alb[well] *= 0.3
    rough = ROUGH[0] + (ROUGH[1] - ROUGH[0]) * edge
    imgs = {"vent_b_albedo": save(to_srgb(alb), "vent_b_albedo", out, "sRGB"),
            "vent_b_rough": save(rough, "vent_b_rough", out, "Non-Color"),
            "vent_b_metal": save(np.full((SIZE, SIZE), METAL, np.float32), "vent_b_metal", out, "Non-Color")}
    # the body's materials: the bronze on the main one; the cut light faces a dark glass
    for m in body.data.materials:
        bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        nt = m.node_tree
        for sock in ("Emission Color", "Emission Strength"):
            for lk in list(bsdf.inputs[sock].links):
                nt.links.remove(lk)
        bsdf.inputs["Emission Strength"].default_value = 0.0
        if "__" in m.name:
            for sock in ("Base Color", "Roughness", "Metallic"):
                for lk in list(bsdf.inputs[sock].links):
                    nt.links.remove(lk)
            bsdf.inputs["Base Color"].default_value = (0.012, 0.014, 0.018, 1.0)
            bsdf.inputs["Roughness"].default_value = 0.12
            bsdf.inputs["Metallic"].default_value = 0.0
            continue
        for key, sock in (("vent_b_albedo", "Base Color"), ("vent_b_rough", "Roughness"), ("vent_b_metal", "Metallic")):
            link = bsdf.inputs[sock].links[0] if bsdf.inputs[sock].links else None
            node = link.from_node if link and link.from_node.type == "TEX_IMAGE" else None
            if node is None or (link and link.from_node.type != "TEX_IMAGE"):
                if link:
                    nt.links.remove(link)
                node = nt.nodes.new("ShaderNodeTexImage")
                nt.links.new(node.outputs["Color"], bsdf.inputs[sock])
            node.image = imgs[key]
    for o in bpy.context.scene.objects:
        o.select_set(o == body)
    bpy.ops.export_scene.gltf(filepath=str(out / "body.glb"), export_format="GLB", use_selection=True,
                              export_yup=True, export_apply=True, export_materials="EXPORT")
    (out / "lights.json").write_text(json.dumps(lights, indent=1), encoding="utf-8", newline="\n")
    rep["strips"] = len(lights["strips"])
    (out / "bronze.json").write_text(json.dumps(rep, indent=1), encoding="utf-8", newline="\n")
    print(f"BRONZE ok: {rep['triangles']} triangles, {rep['strips']} strips, edge {rep['edge_mean']:.3f}, "
          f"ao {rep['ao_mean']:.3f}")


if __name__ == "__main__":
    main()
