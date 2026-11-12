"""Gate R's reference board inside headless Blender (tools/runner/commands/refs.py): frames from trailers every N
seconds (the sequencer reads the MP4 with Blender's own decoder) and contact sheets of the screenshots and frames,
24 tiles of 320 px each (PREFIX_00.jpg, PREFIX_01.jpg, ...; 1280 px wide, as CLAUDE.md asks of agents' sheets).

    blender -b --python refs_frames.py -- --out DIR --every S --sheet PREFIX --images a.jpg ... --videos v.mp4 ...

Prints one `REFS_FRAME {"path", "video", "t"}` line per frame written (DIR/<video stem>/t0012.0.jpg)."""

import argparse
import json
import sys
from pathlib import Path

import bpy
import numpy as np

TILE = (320, 180)
COLS = 4
PER_SHEET = 24


def frames(video: Path, out: Path, every: float) -> list[Path]:
    sc = bpy.context.scene
    sc.sequence_editor_create()
    for s in list(sc.sequence_editor.strips):
        sc.sequence_editor.strips.remove(s)
    st = sc.sequence_editor.strips.new_movie("v", str(video), 1, 1)
    el = st.elements[0] if st.elements else None
    sc.render.resolution_x = el.orig_width if el else 1280
    sc.render.resolution_y = el.orig_height if el else 720
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "JPEG"
    sc.render.image_settings.quality = 90
    sc.view_settings.view_transform = "Standard"   # the video's own colours, as in the store's screenshots
    sc.view_settings.look = "None"
    fps = st.fps or 30.0
    n = st.frame_final_duration
    if n < 1 or el is None:
        raise RuntimeError(f"Blender cannot read {video}: {n} frames")
    sc.frame_start, sc.frame_end = 1, n
    d = out / video.stem
    d.mkdir(parents=True, exist_ok=True)
    got = []
    step = max(1, round(every * fps))
    for f in range(1, n + 1, step):
        t = (f - 1) / fps
        p = d / f"t{t:06.1f}.jpg"
        sc.frame_set(f)
        sc.render.filepath = str(p)
        bpy.ops.render.render(write_still=True)
        got.append(p)
        print("REFS_FRAME " + json.dumps({"path": str(p), "video": str(video), "t": round(t, 2)}), flush=True)
    sc.sequence_editor.strips.remove(st)
    return got


def tile(path: Path) -> np.ndarray:
    im = bpy.data.images.load(str(path))
    w, h = im.size
    tw, th = TILE
    s = min(tw / w, th / h)
    im.scale(max(1, int(w * s)), max(1, int(h * s)))
    w2, h2 = im.size
    px = np.array(im.pixels[:], np.float32).reshape(h2, w2, 4)
    out = np.full((th, tw, 4), 0.12, np.float32)
    out[..., 3] = 1.0
    y0, x0 = (th - h2) // 2, (tw - w2) // 2
    out[y0:y0 + h2, x0:x0 + w2] = px
    out[:, :1] = out[:1, :] = 0.0
    bpy.data.images.remove(im)
    return out


def sheets(files: list[Path], prefix: str) -> list[Path]:
    out = []
    for k in range(0, len(files), PER_SHEET):
        tiles = [tile(f) for f in files[k:k + PER_SHEET]]
        while len(tiles) % COLS:
            tiles.append(np.full_like(tiles[0], 0.12))
        rows = [np.concatenate(tiles[i:i + COLS], 1) for i in range(0, len(tiles), COLS)]
        sh = np.concatenate(rows[::-1], 0)   # Blender's rows start at the bottom: the first file on top
        path = Path(f"{prefix}_{k // PER_SHEET:02d}.jpg")
        img = bpy.data.images.new("sheet", sh.shape[1], sh.shape[0])
        img.pixels = sh.ravel()
        img.filepath_raw = str(path)
        img.file_format = "JPEG"
        img.save()
        bpy.data.images.remove(img)
        out.append(path)
    return out


def main(argv) -> None:
    ap = argparse.ArgumentParser(prog="refs_frames.py")
    ap.add_argument("--out", required=True)
    ap.add_argument("--every", type=float, default=2.0)
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--images", nargs="*", default=[])
    ap.add_argument("--videos", nargs="*", default=[])
    a = ap.parse_args(argv)
    out = Path(a.out)
    files = [Path(p) for p in a.images]
    for v in a.videos:
        files += frames(Path(v), out, a.every)
    for path in sheets(files, a.sheet):
        print(f"REFS_SHEET {path}", flush=True)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
