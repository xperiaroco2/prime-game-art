"""The throat vent's body, way A step 3 (art #263 station 1; docs/ship.md "Station 1"): the box's pale outer side and
back repainted bronze by face direction (step 2 went by colour and left the side washed out).

    blender -b --python ship_vent_a_sides.py -- --in <body dir> --out <dir>

The box's faces (u below the column) whose normal points out of its outer side (-u) or back toward the wall (-v)
are rasterized in the body's UV layout; their texels, outside the glows (the emission map), are set to the body's
bronze median (its finish.json) at their own lightness moved onto the bronze's (its median and spread, held to its
10th..90th percentile), so the mottle stays and nothing goes pale. Writes <out>/body.glb, <out>/textures/*.png (the other maps copied) and
<out>/finish.json (the input's, with a "sides" entry)."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ship_interior_vent as V  # noqa: E402
import ship_vent_a_finish as F  # noqa: E402

OUTER_U = -0.70     # the box's outer side: face centres beyond this
BACK_V = 0.12       # the back: face centres behind this


def side_mask(obj, size: int) -> tuple[np.ndarray, dict]:
    mask = np.zeros((size, size), bool)
    uv = obj.data.uv_layers[0].data
    yy, xx = np.mgrid[0:size, 0:size]
    count = {"side": 0, "back": 0}
    for poly in obj.data.polygons:
        c, n = poly.center, poly.normal
        if c.x > V.COL_U[0]:
            continue
        kind = "side" if (n.x < -0.7 and c.x < OUTER_U) else "back" if (n.y > 0.7 and -c.y < BACK_V) else None
        if not kind:
            continue
        count[kind] += 1
        pts = np.array([uv[i].uv[:] for i in poly.loop_indices]) * size
        for k in range(1, len(pts) - 1):
            a, b, d = pts[0], pts[k], pts[k + 1]
            x0, x1 = int(max(0, min(a[0], b[0], d[0]) - 1)), int(min(size, max(a[0], b[0], d[0]) + 2))
            y0, y1 = int(max(0, min(a[1], b[1], d[1]) - 1)), int(min(size, max(a[1], b[1], d[1]) + 2))
            den = (b[1] - d[1]) * (a[0] - d[0]) + (d[0] - b[0]) * (a[1] - d[1])
            if x1 <= x0 or y1 <= y0 or abs(den) < 1e-9:
                continue
            px, py = xx[y0:y1, x0:x1] + 0.5, yy[y0:y1, x0:x1] + 0.5
            w0 = ((b[1] - d[1]) * (px - d[0]) + (d[0] - b[0]) * (py - d[1])) / den
            w1 = ((d[1] - a[1]) * (px - d[0]) + (a[0] - d[0]) * (py - d[1])) / den
            mask[y0:y1, x0:x1] |= (w0 >= -0.01) & (w1 >= -0.01) & (1 - w0 - w1 >= -0.01)
    return mask, count


def main() -> None:
    src, out = Path(F.arg("--in")), Path(F.arg("--out"))
    (out / "textures").mkdir(parents=True, exist_ok=True)
    rep = json.loads((src / "finish.json").read_text(encoding="utf-8"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(src / "body.glb"))
    body = next(o for o in bpy.context.scene.objects if o.type == "MESH")
    base = next(m for m in body.data.materials if m.name == "vent_a_body")
    bsdf = next(n for n in base.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    alb_img = bsdf.inputs["Base Color"].links[0].from_node.image
    size = alb_img.size[0]
    alb = F.pixels(alb_img)[..., :3].copy()
    em = F.pixels(bpy.data.images.load(str(src / "textures" / "vent_a_emission.png")))[..., :3]
    mask, count = side_mask(body, size)
    mask &= em.max(-1) <= 0.08
    target = np.array(rep["bronze"]["after"], np.float32)
    r, g, b = alb[..., 0], alb[..., 1], alb[..., 2]
    bronze = ~mask & (em.max(-1) <= 0.08) & (r > g) & (g > b) & (alb.max(-1) > 0.05)
    blum, mlum = alb[bronze].mean(-1), alb[mask].mean(-1)
    lo, hi = np.percentile(blum, 10), np.percentile(blum, 90)
    # the patch's lightness moved onto the bronze's: its median and spread (its own mottle kept, not its paleness)
    k = float(np.std(blum)) / max(1e-4, float(np.std(mlum)))
    lum = np.clip(np.median(blum) + (alb.mean(-1, keepdims=True) - np.median(mlum)) * k, lo, hi)
    before = np.median(alb[mask], 0)
    alb = np.where(mask[..., None], target[None, None, :] * lum / max(1e-4, float(target.mean())), alb)
    new = F.save(alb, "vent_a_albedo", out)
    for m in body.data.materials:
        if m and m.use_nodes:
            for n in m.node_tree.nodes:
                if n.type == "TEX_IMAGE" and n.image == alb_img:
                    n.image = new
    for name in ("vent_a_emission", "vent_a_metal", "vent_a_normal", "vent_a_rough"):
        shutil.copyfile(src / "textures" / f"{name}.png", out / "textures" / f"{name}.png")
    for o in bpy.context.scene.objects:
        o.select_set(o is body)
    bpy.ops.export_scene.gltf(filepath=str(out / "body.glb"), export_format="GLB", use_selection=True,
                              export_yup=True, export_apply=True, export_materials="EXPORT")
    rep["sides"] = {"in": src.as_posix(), "faces": count, "texels": int(mask.sum()),
                    "before": before.round(3).tolist(), "after": np.median(alb[mask], 0).round(3).tolist(),
                    "materials": [m.name for m in body.data.materials]}
    (out / "finish.json").write_text(json.dumps(rep, indent=1), encoding="utf-8", newline="\n")
    print("VENTSIDES " + json.dumps(rep["sides"]))


if __name__ == "__main__":
    main()
