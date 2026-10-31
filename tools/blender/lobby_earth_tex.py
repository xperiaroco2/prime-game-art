"""The lobby window's Earth textures (art #356, docs/lobby.md "Step 3b"): NASA's source images (sources/
nasa_earth_lobby.toml) scaled to game size in headless Blender and saved as JPEG; the raw sources are only read.
    blender -b --factory-startup --python lobby_earth_tex.py -- --request <request.json>
request.json: {"size": [w, h], "quality": q, "out": dir, "maps": {name: source path}, "caps": {name: {"source", "lat",
"lon", "size"}}} -> <out>/earth_<name>.jpg and <out>/earth_tex.json ({name: {"file", "size", "source"}}). Step 5a4:
each cap is a [lat0, lat1] x [lon0, lon1] degree box cut from its source's equirectangular pixels at full resolution
and scaled to its size (the part of the globe the window shows up close: docs/lobby.md "Step 5a4")."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy
import numpy as np


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:]
    req = json.loads(Path(argv[argv.index("--request") + 1]).read_text(encoding="utf-8"))
    out = Path(req["out"])
    out.mkdir(parents=True, exist_ok=True)
    w, h = req["size"]
    scene = bpy.context.scene
    settings = scene.render.image_settings
    settings.file_format = "JPEG"
    settings.color_mode = "RGB"
    settings.quality = int(req["quality"])
    # the pixels as they are: sRGB in, the Standard view out (no AgX or Filmic look on the saved file)
    scene.display_settings.display_device = "sRGB"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    report = {}
    for name, src in req["maps"].items():
        img = bpy.data.images.load(src, check_existing=False)
        sw, sh = img.size
        img.scale(w, h)
        dest = out / f"earth_{name}.jpg"
        img.save_render(str(dest), scene=scene)
        report[name] = {"file": dest.name, "size": [w, h], "source": src, "source_size": [sw, sh]}
        print(f"LOBBY earth {name}: {sw}x{sh} -> {w}x{h} {dest}")
        bpy.data.images.remove(img)
    for name, c in req.get("caps", {}).items():
        img = bpy.data.images.load(c["source"], check_existing=False)
        sw, sh = img.size
        is_float, space = img.is_float, img.colorspace_settings.name   # a 16-bit TIFF loads as linear floats
        px = np.empty(sw * sh * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        bpy.data.images.remove(img)
        px = px.reshape(sh, sw, 4)[::-1]   # top row first: y = (90 - lat) / 180 * sh
        (lat0, lat1), (lon0, lon1) = c["lat"], c["lon"]
        x0, x1 = round((lon0 + 180.0) / 360.0 * sw), round((lon1 + 180.0) / 360.0 * sw)
        y0, y1 = round((90.0 - lat1) / 180.0 * sh), round((90.0 - lat0) / 180.0 * sh)
        crop = np.ascontiguousarray(px[y0:y1, x0:x1][::-1])
        del px
        cw, ch = x1 - x0, y1 - y0
        img = bpy.data.images.new(f"cap_{name}", cw, ch, alpha=False, float_buffer=is_float)
        img.colorspace_settings.name = space
        img.pixels.foreach_set(crop.ravel())
        del crop
        w2, h2 = c["size"]
        img.scale(w2, h2)
        dest = out / f"earth_{name}.jpg"
        img.save_render(str(dest), scene=scene)
        report[name] = {"file": dest.name, "size": [w2, h2], "source": c["source"], "source_size": [sw, sh],
                        "crop_px": [x0, y0, x1, y1], "lat": c["lat"], "lon": c["lon"]}
        print(f"LOBBY earth cap {name}: {sw}x{sh} [{x0}:{x1}, {y0}:{y1}] {cw}x{ch} -> {w2}x{h2} {dest} (float {is_float}, {space})")
        bpy.data.images.remove(img)
    (out / "earth_tex.json").write_text(json.dumps(report, indent=1), encoding="utf-8", newline="\n")


main()
