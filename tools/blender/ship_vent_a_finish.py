"""The throat vent's body, way A, step 2 (art #263 station 1; docs/ship.md "Station 1"): the baked body of
ship_vent_a.py finished without a new generation, and the blades' maps.

    blender -b --python ship_vent_a_finish.py -- --in <body4k dir> --concept <front_ortho.png> --out <dir>

- The light-blue patch: texels of the body outside the well (its faces' UV triangles rasterized) that are neither a
  glow (the emission map) nor bronze-hued but light blue (blue over red) are repainted bronze at their own lightness.
- The grade: the body's bronze texels (outside the well, no glow) scaled per channel toward the concept's frame bronze
  (front_ortho's top and bottom bars, the median of their bronze pixels times LIT, a lit picture being brighter than
  its albedo); the well stays dark.
- The blade's maps on its UV layout (ship_interior_vent.blade_uvs: U along the blade, V round its section): the graded
  bronze with a mottle as strong as the body's, bright worn edges along the section's EDGES corners (the nose, the
  ridge, the trailing edge), a darker underside; roughness and metallic from the body's bronze, the edges polished.

Writes <out>/body.glb (the body with the graded albedo), <out>/textures/*.png and <out>/finish.json."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ship_interior_vent as V  # noqa: E402

LIT = 0.82                       # the concept's lit bronze over its albedo
BARS = ((455, 940, 185, 235), (430, 940, 1245, 1290))    # front_ortho (1536 px): the frame's top and bottom bars
WELL_V = 0.36                    # faces behind this inside the opening are the well's
BLADE_LIFT, MOTTLE = 1.25, 0.22   # the blade's bronze over the body's median (it stands out in the light), its mottle
                                 # over the body's spread (a fine patina; 1.1 read as camouflage blotches in Godot)


def arg(k, d=None):
    a = sys.argv[sys.argv.index("--") + 1:]
    return a[a.index(k) + 1] if k in a else d


def pixels(img) -> np.ndarray:
    w, h = img.size
    return np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)


def save(arr: np.ndarray, name: str, out: Path, cs: str = "sRGB"):
    h, w = arr.shape[:2]
    img = bpy.data.images.new(name, w, h, alpha=False)
    img.colorspace_settings.name = cs
    if arr.ndim == 2:
        arr = np.repeat(arr[..., None], 3, -1)
    img.pixels[:] = np.concatenate([np.clip(arr[..., :3], 0, 1), np.ones((h, w, 1), np.float32)], -1).ravel()
    img.filepath_raw = str(out / "textures" / f"{name}.png")
    img.file_format = "PNG"
    img.save()
    return img


def label_map(obj, size: int) -> np.ndarray:
    """Per texel: 0 no face, 1 a body face outside the well, 2 a well face (inside the opening, behind WELL_V)."""
    lab = np.zeros((size, size), np.uint8)
    uv = obj.data.uv_layers[0].data
    yy, xx = np.mgrid[0:size, 0:size]
    for poly in obj.data.polygons:
        c = poly.center
        well = (V.OPEN_U[0] - 0.02 < c.x < V.OPEN_U[1] + 0.02 and V.OPEN_H[0] - 0.02 < c.z < V.OPEN_H[1] + 0.02
                and -c.y < WELL_V)
        pts = np.array([uv[i].uv[:] for i in poly.loop_indices]) * size
        for k in range(1, len(pts) - 1):
            a, b, d = pts[0], pts[k], pts[k + 1]
            x0, x1 = int(max(0, min(a[0], b[0], d[0]) - 1)), int(min(size, max(a[0], b[0], d[0]) + 2))
            y0, y1 = int(max(0, min(a[1], b[1], d[1]) - 1)), int(min(size, max(a[1], b[1], d[1]) + 2))
            if x1 <= x0 or y1 <= y0:
                continue
            px, py = xx[y0:y1, x0:x1] + 0.5, yy[y0:y1, x0:x1] + 0.5
            den = (b[1] - d[1]) * (a[0] - d[0]) + (d[0] - b[0]) * (a[1] - d[1])
            if abs(den) < 1e-9:
                continue
            w0 = ((b[1] - d[1]) * (px - d[0]) + (d[0] - b[0]) * (py - d[1])) / den
            w1 = ((d[1] - a[1]) * (px - d[0]) + (a[0] - d[0]) * (py - d[1])) / den
            inside = (w0 >= -0.02) & (w1 >= -0.02) & (1 - w0 - w1 >= -0.02)
            sub = lab[y0:y1, x0:x1]
            sub[inside & (sub == 0)] = 2 if well else 1
            if not well:
                sub[inside] = 1
    return lab


def noise(h: int, w: int, rng) -> np.ndarray:
    """A mottle: octaves of smoothed random grids, zero mean, unit spread."""
    out = np.zeros((h, w), np.float32)
    for cells, amp in ((16, 0.5), (48, 0.6), (140, 0.45)):
        g = rng.standard_normal((max(2, cells * h // w + 1), cells + 1)).astype(np.float32)
        yi = np.linspace(0, g.shape[0] - 1, h)
        xi = np.linspace(0, g.shape[1] - 1, w)
        y0, x0 = np.floor(yi).astype(int), np.floor(xi).astype(int)
        y1, x1 = np.minimum(y0 + 1, g.shape[0] - 1), np.minimum(x0 + 1, g.shape[1] - 1)
        fy, fx = (yi - y0)[:, None], (xi - x0)[None, :]
        fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
        out += amp * ((g[y0][:, x0] * (1 - fx) + g[y0][:, x1] * fx) * (1 - fy)
                      + (g[y1][:, x0] * (1 - fx) + g[y1][:, x1] * fx) * fy)
    return (out - out.mean()) / out.std()


def main() -> None:
    src, out, concept = Path(arg("--in")), Path(arg("--out")), Path(arg("--concept"))
    (out / "textures").mkdir(parents=True, exist_ok=True)
    rep: dict = {"in": src.as_posix()}
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(src / "body.glb"))
    body = next(o for o in bpy.context.scene.objects if o.type == "MESH")
    base = next(m for m in body.data.materials if m.name == "vent_a_body")
    bsdf = next(n for n in base.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    img_of = lambda sock: bsdf.inputs[sock].links[0].from_node.image   # noqa: E731
    alb_img = img_of("Base Color")
    size = alb_img.size[0]
    alb = pixels(alb_img)[..., :3].copy()
    em = pixels(bpy.data.images.load(str(src / "textures" / "vent_a_emission.png")))[..., :3]
    rough = pixels(bpy.data.images.load(str(src / "textures" / "vent_a_rough.png")))[..., 0]
    metal = pixels(bpy.data.images.load(str(src / "textures" / "vent_a_metal.png")))[..., 0]
    lab = label_map(body, size)
    glow = em.max(-1) > 0.08
    body_px = (lab == 1) & ~glow
    r, g, b = alb[..., 0], alb[..., 1], alb[..., 2]
    blue = body_px & (b > r + 0.04) & (b > 0.18)
    rep["texels"] = {"body": int(body_px.sum()), "well": int((lab == 2).sum()), "glow": int(glow.sum()),
                     "light_blue": int(blue.sum())}
    bronze = body_px & ~blue & (r > g) & (g > b)
    cur = np.median(alb[bronze], 0)
    # where the blue sat: the faces whose UV centre is a blue texel, by their place
    uv = body.data.uv_layers[0].data
    places = {}
    for poly in body.data.polygons:
        c = sum((np.array(uv[i].uv[:]) for i in poly.loop_indices)) / poly.loop_total
        x, y = min(size - 1, int(c[0] * size)), min(size - 1, int(c[1] * size))
        if blue[y, x]:
            p, n = poly.center, poly.normal
            where = ("column" if p.x > V.COL_U[0] else "box") + (" side" if abs(n.x) > 0.7 else " back" if n.y > 0.7
                                                                 else " top" if n.z > 0.7 else " front/other")
            places[where] = places.get(where, 0) + 1
    rep["light_blue_faces"] = places
    # repaint the blue bronze at its own lightness
    # at its own lightness held to the bronze's 10th..90th percentile (r2 kept it whole: the patch went pale)
    blum = alb[bronze].mean(-1)
    lum = np.clip(alb.mean(-1, keepdims=True), np.percentile(blum, 10), np.percentile(blum, 90))
    alb = np.where(blue[..., None], cur[None, None, :] * lum / max(1e-4, float(cur.mean())), alb)
    # the grade toward the concept's frame bronze
    cimg = pixels(bpy.data.images.load(str(concept)))[..., :3]
    ch = cimg.shape[0]
    samples = []
    for x0, x1, y0, y1 in BARS:
        patch = cimg[ch - y1:ch - y0, x0:x1].reshape(-1, 3)   # Blender's rows run bottom-up
        samples.append(patch[(patch[:, 0] > patch[:, 1]) & (patch[:, 1] > patch[:, 2])])
    target = np.median(np.concatenate(samples), 0) * LIT
    gain = np.clip(target / np.maximum(cur, 1e-4), 0.8, 2.4)
    graded = body_px | blue
    alb = np.where(graded[..., None], np.clip(alb * gain, 0, 1), alb)
    rep["bronze"] = {"before": cur.round(3).tolist(), "concept_lit": (target / LIT).round(3).tolist(),
                     "target": target.round(3).tolist(), "gain": gain.round(3).tolist(),
                     "after": np.median(alb[bronze], 0).round(3).tolist()}
    new = save(alb, "vent_a_albedo", out)
    bsdf_links = [m for m in body.data.materials if m and m.use_nodes]
    for m in bsdf_links:
        for n in m.node_tree.nodes:
            if n.type == "TEX_IMAGE" and n.image == alb_img:
                n.image = new
    for name in ("vent_a_emission", "vent_a_metal", "vent_a_normal", "vent_a_rough"):
        shutil.copyfile(src / "textures" / f"{name}.png", out / "textures" / f"{name}.png")
    # the blade's maps
    bw, bh = 1024, 512
    rng = np.random.default_rng(263)
    spread = float(np.std(alb[bronze].mean(-1)))
    us, vs = V.blade_uv_marks()
    vy = (np.arange(bh) + 0.5) / bh
    ux = (np.arange(bw) + 0.5) / bw
    edge = np.zeros((bh, bw), np.float32)
    for j in V.EDGES:
        edge = np.maximum(edge, np.exp(-((vy[:, None] - vs[j]) / 0.012) ** 2) * np.ones((1, bw)))
    under = ((vy > vs[V.EDGES[-1]]) & (vy < vs[-2] + 0.01))[:, None] * np.ones((1, bw))
    ends = np.clip(1 - np.minimum(ux - us[0], us[-1] - ux) / 0.06, 0, 1)[None, :] * np.ones((bh, 1))
    mot = noise(bh, bw, rng)
    lum = float(np.median(alb[bronze].mean(-1)))
    col = BLADE_LIFT * np.median(alb[bronze], 0)[None, None, :]
    col = col * (1 + MOTTLE * spread / max(1e-4, lum) * mot[..., None])
    col = col * (1 - 0.2 * under[..., None]) * (1 - 0.2 * ends[..., None])
    hi_col = np.array([1.0, 0.82, 0.58], np.float32)
    wear = np.clip(edge * (0.75 + 0.25 * noise(bh, bw, rng)), 0, 1)[..., None]
    col = col * (1 - wear) + hi_col * wear
    save(col, "vent_a_blade_albedo", out)
    r0, m0 = float(np.median(rough[bronze])), float(np.median(metal[bronze]))
    save(np.clip(r0 * (1 + 0.15 * mot) - 0.2 * wear[..., 0], 0.05, 1), "vent_a_blade_rough", out, "Non-Color")
    save(np.clip(np.full((bh, bw), m0) + 0.1 * wear[..., 0], 0, 1), "vent_a_blade_metal", out, "Non-Color")
    rep["blade"] = {"albedo_median": np.median(col.reshape(-1, 3), 0).round(3).tolist(), "rough": round(r0, 3),
                    "metal": round(m0, 3), "mottle_spread": round(spread, 4), "lum": round(lum, 3)}
    for o in bpy.context.scene.objects:
        o.select_set(o is body)
    bpy.ops.export_scene.gltf(filepath=str(out / "body.glb"), export_format="GLB", use_selection=True,
                              export_yup=True, export_apply=True, export_materials="EXPORT")
    rep["tris"] = sum(len(p.vertices) - 2 for p in body.data.polygons)
    rep["materials"] = [m.name for m in body.data.materials]
    (out / "finish.json").write_text(json.dumps(rep, indent=1), encoding="utf-8", newline="\n")
    print("VENTA2 " + json.dumps(rep))


if __name__ == "__main__":
    main()
