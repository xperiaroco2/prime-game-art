"""The first-person hands' golden-frame check (art#136): a run's frames against the golden ones, inside each frame's
hand box. Runs in headless Blender for its PNG reader and numpy (the runner is standard library only):

    blender -b --python tools/blender/fp_golden.py -- --spec <spec.json> --out <golden.json>

spec.json: {"changed": 0.1, "max_share": 0.01, "frames": [{"name", "golden", "run", "box": [x0, y0, x1, y1]
(fractions of the frame, from the top left), "gate": bool}]}. Per frame: `share`, the box's pixels whose largest
channel moved more than `changed` (0..1); `mean`, the box's mean absolute difference (0..255); `pass`, share within
max_share (a frame with gate false is reported, never failed). fp_hands_run.py golden() writes the spec and reads
the result."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy
import numpy as np


def pixels(path: str) -> np.ndarray:
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    a = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    return a.reshape(h, w, 4)[::-1, :, :3]   # Blender's rows run from the bottom


def main(argv: list[str]) -> None:
    spec = json.loads(Path(argv[argv.index("--spec") + 1]).read_text(encoding="utf-8"))
    out = Path(argv[argv.index("--out") + 1])
    changed, max_share = float(spec["changed"]), float(spec["max_share"])
    rows = []
    for f in spec["frames"]:
        row = {"name": f["name"], "gate": bool(f.get("gate", True))}
        if not Path(f["run"]).is_file():
            row.update({"pass": False, "why": f"no frame {f['run']}"})
            rows.append(row)
            continue
        g, r = pixels(f["golden"]), pixels(f["run"])
        if g.shape != r.shape:
            row.update({"pass": False, "why": f"size {r.shape[1]}x{r.shape[0]}, golden {g.shape[1]}x{g.shape[0]}"})
            rows.append(row)
            continue
        h, w = g.shape[:2]
        x0, y0, x1, y1 = f["box"]
        d = np.abs(g - r)[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]
        share = float((d.max(2) > changed).mean())
        row.update({"share": round(share, 5), "mean": round(float(d.mean()) * 255, 3),
                    "pass": share <= max_share})
        rows.append(row)
    ok = all(r["pass"] for r in rows if r["gate"])
    out.write_text(json.dumps({"ok": ok, "changed": changed, "max_share": max_share, "frames": rows}, indent=1),
                   encoding="utf-8")
    print("FP_GOLDEN " + json.dumps({"ok": ok, "frames": rows}))


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
