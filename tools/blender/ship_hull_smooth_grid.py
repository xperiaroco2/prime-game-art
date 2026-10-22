"""The smooth skin's silhouette grid (art #263 v2, hull lane; docs/ship.md "The smooth skin"): every variant of
ship_hull_smooth.VARIANTS in four views (front, side from the west, top with the nose up, three-quarter), shaded smooth,
with the mirrored rooms as an orange ghost inside (Workbench, X-ray), under a row of the approved 2D (turnaround's
front, side and top crops and hero.jpg). One sheet, 4 x 320 px wide.

    blender -b --factory-startup --python ship_hull_smooth_grid.py -- --out <dir> [--crops <dir>] [--variants K,L] [--solid]

Prints per variant the room points the skin does not clear, the outer wing's thickness, the tip's height and the
window band's gap to the outline."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ship_hull_grid as G  # noqa: E402
import ship_hull_smooth as S  # noqa: E402


def ghost(coll):
    m = G.mat("room", (1.0, 0.45, 0.1))

    def cyl(name, cx, r, h0, h1, n=32):
        v = [(cx + r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n), h) for h in (h0, h1)
             for k in range(n)]
        f = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))] + [(k, (k + 1) % n, n + (k + 1) % n, n + k)
                                                                     for k in range(n)]
        G.mesh(name, v, f, m, coll)

    def box(name, x0, x1, y0, y1, h0, h1):
        v = [(x, y, h) for h in (h0, h1) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
        f = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        G.mesh(name, v, f, m, coll)
    f = S.FLOOR - 0.25
    cyl("hall", 0.0, S.HALL_R, f, S.HALL_APEX)
    box("mouth", -1.25, 1.25, -4.6, -3.7, f, S.MOUTH_TOP)
    box("corr_w", -7.3, -3.7, -1.5, 1.5, f, S.COR_TOP)
    box("corr_e", 3.7, 7.3, -1.5, 1.5, f, S.COR_TOP)
    cyl("tip_w", -S.TIP_X, S.TIP_R, f, S.TIP_APEX)
    cyl("tip_e", S.TIP_X, S.TIP_R, f, S.TIP_APEX)
    box("ramp", -1.3, 1.3, -7.4, -4.6, 0.0, 0.15)


def main():
    out = Path(G.arg("--out"))
    out.mkdir(parents=True, exist_ok=True)
    crops = Path(G.arg("--crops", "D:/prime-art-raw/ship/v1/meshy_in"))
    names = G.arg("--variants", ",".join(S.VARIANTS)).split(",")
    scene = bpy.context.scene
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light, sh.color_type = "STUDIO", "MATERIAL"
    sh.show_xray, sh.xray_alpha = "--solid" not in sys.argv, 0.75   # --solid: the skin opaque (its shading)
    sh.show_cavity = False
    sh.show_specular_highlight = True
    sh.show_object_outline = True
    world = bpy.data.worlds.new("bg")
    world.color = (0.05, 0.07, 0.1)
    scene.world = world
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = G.W, G.H_, 100
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    rooms = bpy.data.collections.new("rooms")
    scene.collection.children.link(rooms)
    ghost(rooms)
    colls = {}
    skin = G.mat("skin", (0.72, 0.74, 0.78))
    belly = G.mat("belly", (0.45, 0.47, 0.5))
    for name in names:
        coll = bpy.data.collections.new(f"v{name}")
        scene.collection.children.link(coll)
        var = S.VARIANTS[name]
        tris = 0
        for part, (v, f) in S.skin(var).items():
            ob = G.mesh(f"{name}_{part}", v, f, skin if part == "top" else belly, coll)
            for p in ob.data.polygons:
                p.use_smooth = True
            tris += sum(len(p.vertices) - 2 for p in ob.data.polygons)
        colls[name] = coll
        bad = S.clearance(var)
        ms = S.measures(var)
        print(f"SMOOTH clear {name}: {len(bad)} room points not cleared" + (f", e.g. {bad[:4]}" if bad else ""))
        print(f"SMOOTH measures {name}: {tris} tris, " + ", ".join(f"{k} {v:.2f}" for k, v in ms.items()))
    rows = [np.concatenate([G.pixels(crops / r if not r.startswith("D:") else r) for r in G.REFS], axis=1)]
    for key in names:
        for k, c in colls.items():
            c.hide_render = k != key
        cells = []
        for view in ("front", "side", "top", "q"):
            G.camera(scene, view)
            scene.render.filepath = str(out / f"{key}_{view}.png")
            bpy.ops.render.render(write_still=True)
            cells.append(G.pixels(out / f"{key}_{view}.png"))
        rows.append(np.concatenate(cells, axis=1))
        print(f"SMOOTH rendered {key}")
    sheet = np.concatenate(rows[::-1], axis=0)
    img = bpy.data.images.new("sheet", sheet.shape[1], sheet.shape[0])
    img.pixels.foreach_set(sheet.ravel())
    img.filepath_raw, img.file_format = str(out / "grid.png"), "PNG"
    img.save()
    print(f"SMOOTH sheet {out / 'grid.png'} rows: 2D, " + ", ".join(names))


if __name__ == "__main__":
    main()
