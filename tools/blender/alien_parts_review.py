"""Review sheets of the alien parts kit (art #196, step S2a), Eevee, from alien_parts.py's .blend:

  blender -b --factory-startup --python-exit-code 1 --python tools/blender/alien_parts_review.py -- \
      --blend <S2a/alien_head_parts.blend> --out <S2a/review> [--only heads|parts]

heads.png (4 x 320 px cells): the two face designs at 1 m (front, three-quarter, side, back), the crests, the three
hues. parts.png (6 x 212 px cells): each eye design's open, rest, half and closed lids (front, and the closed lids from
the side and three-quarter), each mouth design's six pieces.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_views as RV  # noqa: E402  (read_png, draw_text, write_png)

STATES = ("open", "rest", "half", "closed")
VISEMES = ("rest", "M", "small", "A", "E", "O")


def args():
    p = argparse.ArgumentParser()
    p.add_argument("--blend", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--only", default="")
    return p.parse_args(sys.argv[sys.argv.index("--") + 1:])


def setup(res):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = 48
    sc.render.resolution_x = sc.render.resolution_y = res
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = 0.0
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.20, 0.20, 0.21, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.9
    sc.world = w
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    for name, loc, energy, size in (("key", (-0.9, -1.2, 2.3), 60, 1.2), ("fill", (1.3, -1.0, 1.6), 20, 1.5),
                                    ("rim", (0.4, 1.4, 2.2), 40, 0.8)):
        L = bpy.data.lights.new(name, "AREA")
        L.energy, L.size = energy, size
        o = bpy.data.objects.new(name, L)
        o.location = loc
        d = Vector((0, 0, 1.6)) - Vector(loc)
        o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        sc.collection.objects.link(o)
    return cam


def aim(cam, target, yaw_deg, dist, lens, pitch_deg=4.0):
    a, p = math.radians(yaw_deg), math.radians(pitch_deg)
    pos = target + Vector((math.sin(a) * math.cos(p), -math.cos(a) * math.cos(p), math.sin(p))) * dist
    cam.location = pos
    cam.rotation_euler = (target - pos).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens


def show(head, eye=None, mouth=None, crest=None, hue=None, lid_state="rest"):
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        n = o.name
        vis = n == "alien_head"
        if eye and n.startswith(f"eye_{eye}_"):
            vis = True
        if mouth and (n == f"mouth_{mouth}" or (mouth.startswith("overbite") and n == "mouth_overbite_teeth")):
            vis = True
        if crest and n == f"crest_{crest}":
            vis = True
        o.hide_render = not vis
        if hue is not None and "alien_hue" in o:
            o["alien_hue"] = hue
            o.update_tag()
        if vis and "states" in o:
            side = n[-1]
            sock = bpy.data.objects[f"Eye_{side}"].matrix_world
            o.matrix_world = sock @ Matrix.Rotation(math.radians(o["states"][lid_state]), 4, "X")


def shot(cam, path, target, yaw, dist, lens):
    aim(cam, target, yaw, dist, lens)
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    return RV.read_png(path)


def sheet(tiles, labels, cols, cell, path):
    rows = math.ceil(len(tiles) / cols)
    canvas = np.zeros((rows * cell, cols * cell, 3), dtype=np.float32) + 0.2
    for i, (t, lab) in enumerate(zip(tiles, labels)):
        r, c = divmod(i, cols)
        tile = canvas[r * cell:(r + 1) * cell, c * cell:(c + 1) * cell]
        rgb = t[:, :, :3]
        tile[:] = np.where(rgb <= 0.0031308, rgb * 12.92, 1.055 * np.power(np.clip(rgb, 0, 1), 1 / 2.4) - 0.055) \
            if False else rgb
        tile[:, 0] = tile[0, :] = 0.35
        RV.draw_text(tile, lab, 4, 4, 2)
    RV.write_png(path, canvas)


def main():
    a = args()
    out = Path(a.out)
    (out / "cells").mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=a.blend)
    parts = json.loads((Path(a.blend).parent / "parts.json").read_text(encoding="utf-8"))
    hues = {k: [((c / 12.92) if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4) for c in v]
            for k, v in parts["hues_srgb"].items()}
    head = bpy.data.objects["alien_head"]
    eL, eR = bpy.data.objects["Eye_L"].matrix_world.translation, bpy.data.objects["Eye_R"].matrix_world.translation
    mouth = bpy.data.objects["Mouth"].matrix_world.translation
    centre = Vector(((eL.x + eR.x) / 2, (eL.y + mouth.y) / 2 + 0.03, (eL.z + mouth.z) / 2 + 0.05))
    if a.only in ("", "heads"):
        cam = setup(320)
        tiles, labels = [], []
        combos = (("A", "bored", "frog_rest"), ("B", "manic", "overbite_rest"))
        for tag, eye, m in combos:
            show(head, eye, f"{m}", hue=hues["teal"])
            for yaw, lab in ((0, "front"), (35, "3q"), (90, "side"), (180, "back")):
                tiles.append(shot(cam, out / "cells" / f"h_{tag}_{lab}.png", centre, yaw, 1.0, 70))
                labels.append(f"{tag} {eye} {m.split('_')[0]} {lab} 1m")
        for crest, eye, m in (("antennae", "manic", "overbite_rest"), ("fins", "bored", "frog_rest")):
            show(head, eye, m, crest=crest, hue=hues["teal"])
            tiles.append(shot(cam, out / "cells" / f"c_{crest}.png", centre + Vector((0, 0, 0.02)), 35, 1.0, 62))
            labels.append(f"crest {crest}")
        for hn in ("coral", "violet"):
            show(head, "bored", "frog_rest", crest="fins" if hn == "violet" else "antennae", hue=hues[hn])
            tiles.append(shot(cam, out / "cells" / f"hue_{hn}.png", centre + Vector((0, 0, 0.02)), 35, 1.0, 62))
            labels.append(f"hue {hn}")
        sheet(tiles, labels, 4, 320, out / "heads.png")
    if a.only in ("", "parts"):
        cam = bpy.context.scene.camera or setup(212)
        bpy.context.scene.render.resolution_x = bpy.context.scene.render.resolution_y = 212
        tiles, labels = [], []
        ecent = (eL + eR) / 2 + Vector((0, 0, 0.0))
        for eye in ("bored", "manic"):
            for st in STATES:
                show(head, eye, "frog_rest" if eye == "bored" else "overbite_rest", hue=hues["teal"], lid_state=st)
                tiles.append(shot(cam, out / "cells" / f"e_{eye}_{st}.png", ecent, 0, 0.56, 85))
                labels.append(f"{eye} {st}")
            for yaw, lab in ((90, "side"), (40, "3q")):
                tiles.append(shot(cam, out / "cells" / f"e_{eye}_closed_{lab}.png", eL, yaw, 0.30, 85))
                labels.append(f"closed {lab}")
            show(head, eye, "frog_rest", hue=hues["teal"], lid_state="rest")
        for m in ("frog", "overbite"):
            for v in VISEMES:
                show(head, "bored", f"{m}_{v}", hue=hues["teal"])
                tiles.append(shot(cam, out / "cells" / f"m_{m}_{v}.png", mouth + Vector((0, 0, 0.005)), 20, 0.36, 85))
                labels.append(f"{m} {v}")
        sheet(tiles, labels, 6, 212, out / "parts.png")
    print("SHEETS", out)


if __name__ == "__main__":
    main()
