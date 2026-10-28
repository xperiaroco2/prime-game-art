"""Close-ups of a cleaned outfit for the defect hunt (art #196, clothes step 2): the collar, both cuffs, the straps or
chest, the crotch from the front, the back, the shoes from the front and from the side, and the inside through the
collar, each a textured Workbench shot (flat studio light, so specks, smears and wrong stripes show), as one sheet of
4 x 2 cells of 320 px. Targets come from the cloth's own box; nothing is changed.

    blender -b --factory-startup --python tools/blender/clothes_closeups.py -- CLOTH.blend OUT.png

Prints CLOTHES_CLOSEUPS lines.
"""
from __future__ import annotations

import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

CELL = 320


def look(cam, eye: Vector, target: Vector) -> None:
    cam.location = eye
    cam.rotation_euler = (target - eye).to_track_quat("-Z", "Y").to_euler()


def main() -> None:
    cloth, out = (Path(a) for a in sys.argv[sys.argv.index("--") + 1:][:2])
    bpy.ops.wm.open_mainfile(filepath=str(cloth))
    objs = {o.name: o for o in bpy.data.objects if o.type == "MESH"}
    co = {n: np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices]) for n, o in objs.items()}
    gar = np.concatenate([v for k, v in co.items() if k != "shoes"])
    top = float(gar[:, 2].max())
    shoes = co.get("shoes", gar[gar[:, 2] < 0.15])
    # the cuffs: the sleeves' lowest points on either side (arms hang down beside the body)
    upper = gar[gar[:, 2] > 0.45 * top]
    side = upper[np.abs(upper[:, 0]) > 0.75 * np.abs(upper[:, 0]).max()]
    cuff = {s: side[np.sign(side[:, 0]) == s] for s in (1, -1)}
    cuffs = {s: Vector(c[c[:, 2].argmin()]) if len(c) else Vector((0.3 * s, 0, 0.8)) for s, c in cuff.items()}
    hip = 0.53 * top
    shots = [
        ("collar", Vector((0, -0.55, top + 0.15)), Vector((0, 0, top - 0.06))),
        ("chest", Vector((0, -0.75, top - 0.2)), Vector((0, 0, top - 0.25))),
        ("cuff_R", cuffs[-1] + Vector((-0.25, -0.35, 0.05)), cuffs[-1]),
        ("cuff_L", cuffs[1] + Vector((0.25, -0.35, 0.05)), cuffs[1]),
        ("crotch", Vector((0, -0.7, hip - 0.1)), Vector((0, 0, hip - 0.05))),
        ("back", Vector((0, 1.3, top - 0.25)), Vector((0, 0, top - 0.4))),
        ("shoes", Vector((0.1, -0.7, 0.3)), Vector((0, float(shoes[:, 1].mean()), 0.06))),
        ("shoe_side", Vector((0.75, 0.1, 0.2)), Vector((float(shoes[:, 0].max()) - 0.05, float(shoes[:, 1].mean()), 0.05))),
    ]
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "TEXTURE"
    sc.display.shading.show_backface_culling = False
    sc.render.resolution_x = sc.render.resolution_y = CELL
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    cam.data.lens = 50
    cam.data.clip_start = 0.01
    sc.camera = cam
    tmp = out.parent / (out.stem + "_cells")
    tmp.mkdir(parents=True, exist_ok=True)
    cells = []
    for name, eye, target in shots:
        look(cam, eye, target)
        sc.render.filepath = str(tmp / f"{name}.png")
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(sc.render.filepath)
        cells.append(np.array(img.pixels[:], dtype=np.float32).reshape(CELL, CELL, 4))
        print("CLOTHES_CLOSEUPS", name, tuple(round(x, 3) for x in target), flush=True)
    rows = [np.concatenate(cells[4:], axis=1), np.concatenate(cells[:4], axis=1)]  # pixels are bottom up
    sheet = bpy.data.images.new("closeups", 4 * CELL, 2 * CELL)
    sheet.pixels[:] = np.concatenate(rows, axis=0).ravel()
    sheet.filepath_raw = str(out)
    sheet.file_format = "PNG"
    sheet.save()
    print("CLOTHES_CLOSEUPS wrote", out, flush=True)


main()
