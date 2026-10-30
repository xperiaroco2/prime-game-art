"""The lobby window's Earth textures (art #356, docs/lobby.md "Step 3b"): NASA's source images (sources/
nasa_earth_lobby.toml) scaled to game size in headless Blender and saved as JPEG; the raw sources are only read.
    blender -b --factory-startup --python lobby_earth_tex.py -- --request <request.json>
request.json: {"size": [w, h], "quality": q, "out": dir, "maps": {name: source path}} -> <out>/earth_<name>.jpg and
<out>/earth_tex.json ({name: {"file", "size", "source"}})."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy


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
    (out / "earth_tex.json").write_text(json.dumps(report, indent=1), encoding="utf-8", newline="\n")


main()
