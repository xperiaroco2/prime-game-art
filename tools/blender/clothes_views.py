"""Cuts a three-view turnaround sheet (front, left profile, back; side by side on a plain grey) into one square PNG
per view, every view at the sheet's scale with the same ground line, padded with the sheet's own grey
(art #196, clothes step 2). Runs in headless Blender for its image I/O; the maths is clothes_geom.

    blender -b --factory-startup --python tools/blender/clothes_views.py -- SHEET.png OUT_DIR [--names front,left,back]

Prints CLOTHES_VIEWS lines: each figure's box on the sheet and the square's side.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clothes_geom as cg  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--names", default="front,left,back")
    ap.add_argument("--threshold", type=float, default=0.06, help="colour distance from the grey that is figure")
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    names = args.names.split(",")
    img = bpy.data.images.load(str(args.sheet))
    w, h = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1, :, :3]  # rows top down
    corners = np.concatenate([px[:20, :20].reshape(-1, 3), px[:20, -20:].reshape(-1, 3)])
    grey = np.median(corners, axis=0)
    mask = np.abs(px - grey).max(axis=2) > args.threshold
    cols = cg.spans(list(mask.sum(axis=0) > 3), min_gap=12, min_width=60)
    if len(cols) != len(names):
        raise SystemExit(f"CLOTHES_VIEWS found {len(cols)} figures on {args.sheet}, expected {len(names)}: {cols}")
    boxes = []
    for x0, x1 in cols:
        rows = cg.spans(list(mask[:, x0:x1].sum(axis=1) > 2), min_gap=12, min_width=60)
        y0, y1 = rows[0][0], rows[-1][1]
        boxes.append((x0, y0, x1, y1))
    side = cg.common_square(boxes)
    ground = side - int(round((side - max(b[3] - b[1] for b in boxes)) / 2))
    args.out.mkdir(parents=True, exist_ok=True)
    for name, box in zip(names, boxes):
        x0, y0, x1, y1 = box
        canvas = np.empty((side, side, 4), dtype=np.float32)
        canvas[:, :, :3] = grey
        canvas[:, :, 3] = 1.0
        ox, oy = cg.place(box, side, ground)
        canvas[oy:oy + (y1 - y0), ox:ox + (x1 - x0), :3] = px[y0:y1, x0:x1]
        out = bpy.data.images.new(name, side, side, alpha=False)
        out.pixels[:] = canvas[::-1].ravel()
        out.filepath_raw = str(args.out / f"{name}.png")
        out.file_format = "PNG"
        out.save()
        print(f"CLOTHES_VIEWS {name} box={box} side={side} at={ox},{oy}", flush=True)


main()
