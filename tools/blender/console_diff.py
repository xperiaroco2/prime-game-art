"""The start console's before/after (art#263, the spin-up step 1): the same hall views shot with the shipped GLB and
with the new one (the spin-up's surfaces hidden), compared pixel by pixel in headless Blender (numpy). For each
<name>.png in both folders: diff_<name>.png in --out (before | after | the difference x 8, red where a pixel moved by
more than 2/255, about 1280 px wide) and one CONSOLE_DIFF line: the share of changed pixels and their box.

    blender -b --python console_diff.py -- --before DIR --after DIR --out DIR
    blender -b --python console_diff.py -- --before DIR --after DIR --pairs a,b,c --out FILE.png   (step 2)
"""

import json
import sys
from pathlib import Path

import bpy
import numpy as np


def argv() -> dict:
    a = sys.argv[sys.argv.index("--") + 1:]
    return {a[i].lstrip("-"): a[i + 1] for i in range(0, len(a), 2)}


def load(path: Path) -> np.ndarray:
    img = bpy.data.images.load(str(path))
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)[:, :, :3]


def save(arr: np.ndarray, path: Path) -> None:
    h, w, _ = arr.shape
    img = bpy.data.images.new(path.stem, w, h, alpha=False)
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[:, :, :3] = np.clip(arr, 0.0, 1.0)
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def pairs(before: Path, after: Path, names: list, out: Path) -> None:
    """Step 2's before_after.png: per name a row of before | after (the same view, two builds), about 1280 px wide."""
    rows = []
    for name in names:
        x, y = load(before / f"{name}.png"), load(after / f"{name}.png")
        if x.shape != y.shape:
            raise SystemExit(f"pairs: {name} is {x.shape} before and {y.shape} after: shoot both at one size")
        step = max(1, int(round(x.shape[1] * 2 / 1280)))
        rows.append(np.concatenate([x[::step, ::step], y[::step, ::step]], axis=1))
    save(np.concatenate(rows[::-1], axis=0), out)  # Blender's pixels run bottom-up: the first name on top
    print("CONSOLE_PAIRS " + json.dumps({"out": str(out), "rows": names}), flush=True)


def main() -> None:
    a = argv()
    if "pairs" in a:
        pairs(Path(a["before"]), Path(a["after"]), a["pairs"].split(","), Path(a["out"]))
        return
    before, after, out = Path(a["before"]), Path(a["after"]), Path(a["out"])
    out.mkdir(parents=True, exist_ok=True)
    result = {}
    for b in sorted(before.glob("*.png")):
        if b.name == "sheet.png" or not (after / b.name).is_file():
            continue
        x, y = load(b), load(after / b.name)
        d = np.abs(x - y).max(axis=2)
        moved = d > 2.0 / 255.0
        rows, cols = np.nonzero(moved)
        box = [int(cols.min()), int(rows.min()), int(cols.max()), int(rows.max())] if rows.size else []
        vis = np.repeat(np.clip(d * 8.0, 0.0, 1.0)[:, :, None], 3, axis=2)
        vis[moved] = vis[moved] * 0.5 + np.array([0.5, 0.0, 0.0])
        step = max(1, int(round(x.shape[1] * 3 / 1280)))
        tri = np.concatenate([x[::step, ::step], y[::step, ::step], vis[::step, ::step]], axis=1)
        save(tri, out / f"diff_{b.name}")
        result[b.stem] = {"changed_share": round(float(moved.mean()), 5), "max": round(float(d.max()), 4),
                          "box_px": box, "size": [int(x.shape[1]), int(x.shape[0])]}
        print("CONSOLE_DIFF " + json.dumps({b.stem: result[b.stem]}), flush=True)
    (out / "diff.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


main()
