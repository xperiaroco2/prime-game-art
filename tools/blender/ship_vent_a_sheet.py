"""The throat vent's review sheets beside the concept (art #263 station 1, way A): the built piece GLB alone, its blades
calm (t 1) or closed (t 0), in a neutral studio light and in a warm light like the concept's, from the concept's
three-quarter view, straight front calm, straight front closed and the side (the column's side, as side_left), each
row beside the matching concept view; and a sheet of close-ups (the body's texture, the blade ends at the caps, the
frame's bevels, the scanner, the lamp, the closed seams). EEVEE, headless.

    blender -b --python ship_vent_a_sheet.py -- --glb <station_vent_e.glb> --concept <dir> --out <dir>
        [--open-rad R] [--floor F] [--tile 420] [--game <calm.png>,<problem.png>]

<concept>/<item>/image-0.png: final_wide_hand, front_ortho, front_closed, side_left. Writes <out>/sheet.png,
<out>/closeups.png and each tile."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector


def arg(k, d=None):
    a = sys.argv[sys.argv.index("--") + 1:]
    return a[a.index(k) + 1] if k in a else d


GLB, CONCEPT, OUT = Path(arg("--glb")), Path(arg("--concept")), Path(arg("--out"))
OPEN_RAD, FLOOR, TILE = float(arg("--open-rad", math.radians(25))), float(arg("--floor", 0.0)), int(arg("--tile", 420))
GAME = arg("--game", "")   # two comma-separated PNGs: the last row, calm and the problem in Godot


def scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(GLB))
    for o in list(bpy.context.scene.objects):
        if "convcolonly" in o.name:
            bpy.data.objects.remove(o, do_unlink=True)
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x = sc.render.resolution_y = TILE * 2
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "AgX"
    return sc


def blades(t: float, heat: bool):
    for o in bpy.context.scene.objects:
        if "_slat" in o.name:
            o.rotation_mode = "XYZ"
            o.rotation_euler = (-OPEN_RAD * t, 0, 0)
        if o.name.endswith("_heat"):
            o.hide_render = not heat
        if o.name.endswith("_cool"):   # calm: the cyan glow in front of the heat; the problem: hidden
            o.hide_render = heat


def light(kind: str):
    for o in list(bpy.context.scene.objects):
        if o.type == "LIGHT":
            bpy.data.objects.remove(o, do_unlink=True)
    w = bpy.data.worlds.new(kind)
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bpy.context.scene.world = w

    def add(name, kind_, loc, energy, color, size=1.0):
        ld = bpy.data.lights.new(name, kind_)
        ld.energy, ld.color = energy, color
        if kind_ == "AREA":
            ld.size = size
        ob = bpy.data.objects.new(name, ld)
        bpy.context.scene.collection.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = (Vector((0, -0.2, FLOOR + 0.9)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    if kind == "neutral":
        bg.inputs[0].default_value, bg.inputs[1].default_value = (0.42, 0.42, 0.44, 1), 0.6
        add("key", "AREA", (-2.0, -3.0, FLOOR + 2.6), 600, (1, 1, 1), 2.5)
        add("fill", "AREA", (2.5, -2.5, FLOOR + 1.2), 250, (1, 1, 1), 3.0)
    else:   # the concept's: a deep navy room, a warm key from the front left, a cool rim from the right
        bg.inputs[0].default_value, bg.inputs[1].default_value = (0.05, 0.08, 0.16, 1), 0.5
        add("key", "AREA", (-2.2, -2.6, FLOOR + 2.4), 700, (1.0, 0.78, 0.55), 2.0)
        add("rim", "AREA", (2.4, 0.2, FLOOR + 2.0), 300, (0.55, 0.7, 1.0), 1.5)
        add("fill", "AREA", (0.5, -3.0, FLOOR + 0.5), 120, (0.6, 0.65, 0.9), 3.0)


def camera(loc, at, ortho=None, lens=50):
    cam = bpy.context.scene.camera
    if cam is None:
        cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
        bpy.context.scene.collection.objects.link(cam)
        bpy.context.scene.camera = cam
    cam.data.type = "ORTHO" if ortho else "PERSP"
    if ortho:
        cam.data.ortho_scale = ortho
    cam.data.lens = lens
    cam.location = loc
    cam.rotation_euler = (Vector(at) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


def shoot(name: str) -> np.ndarray:
    path = OUT / "tiles" / f"{name}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    return load(path)


def load(path: Path, crop=None) -> np.ndarray:
    img = bpy.data.images.load(str(path))
    w, h = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1]
    if crop:   # (x0, y0, x1, y1) as shares, from the top left
        x0, y0, x1, y1 = crop
        px = px[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]
    hh, ww = px.shape[:2]
    s = TILE / max(hh, ww)
    ys = (np.arange(int(hh * s)) / s).astype(int).clip(0, hh - 1)
    xs = (np.arange(int(ww * s)) / s).astype(int).clip(0, ww - 1)
    small = px[ys][:, xs]
    tile = np.zeros((TILE, TILE, 4), np.float32)
    tile[..., 3] = 1
    oy, ox = (TILE - small.shape[0]) // 2, (TILE - small.shape[1]) // 2
    tile[oy:oy + small.shape[0], ox:ox + small.shape[1]] = small
    return tile


def save(rows, path: Path):
    grid = np.concatenate([np.concatenate(r, 1) for r in rows], 0)
    h, w = grid.shape[:2]
    img = bpy.data.images.new(path.stem, w, h, alpha=False)
    img.pixels[:] = grid[::-1].ravel()
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    scene()
    f, c = FLOOR, (0.0, -0.2, FLOOR + 0.92)
    views = [  # name, concept (item, crop), t, heat, camera
        ("34", ("final_wide_hand", (0.08, 0.0, 0.66, 1.0)), 1.0, False,
         dict(loc=(-1.9, -3.4, f + 1.35), at=(0.05, -0.2, f + 0.9), lens=45)),
        ("front_calm", ("front_ortho", None), 1.0, False, dict(loc=(0.0, -5.0, f + 0.93), at=c, ortho=2.0)),
        ("front_closed", ("front_closed", None), 0.0, True, dict(loc=(0.0, -5.0, f + 0.93), at=c, ortho=2.0)),
        ("side", ("side_left", None), 1.0, False, dict(loc=(5.0, -0.25, f + 0.93), at=(0.0, -0.25, f + 0.93),
                                                       ortho=2.0)),
    ]
    rows = []
    for name, (item, crop), t, heat, cam in views:
        blades(t, heat)
        camera(**cam)
        row = [load(CONCEPT / item / "image-0.png", crop)]
        for kind in ("neutral", "warm"):
            light(kind)
            row.append(shoot(f"{name}_{kind}"))
        rows.append(row)
    if GAME:   # the game's look: Godot shots of the vent alone in the ship's night light (ship --motion)
        rows.append([load(CONCEPT / "final_wide" / "image-0.png", (0.0, 0.0, 1.0, 1.0))]
                    + [load(Path(g)) for g in GAME.split(",")][:2])
    save(rows, OUT / "sheet.png")
    # close-ups in the warm light: (name, camera, target, lens, t)
    cu = [("texture_frame", (-0.9, -1.2, f + 1.5), (-0.6, -0.42, f + 1.35), 50, 1.0),
          ("blade_ends_caps", (-0.75, -0.95, f + 1.0), (-0.45, -0.38, f + 0.95), 50, 1.0),
          ("frame_bevels_feet", (-1.2, -1.3, f + 0.45), (-0.6, -0.4, f + 0.2), 40, 1.0),
          ("scanner", (0.75, -1.0, f + 1.25), (0.65, -0.4, f + 1.25), 60, 1.0),
          ("lamp", (0.95, -1.0, f + 1.95), (0.65, -0.3, f + 1.72), 60, 1.0),
          ("closed_seams", (-0.2, -1.4, f + 0.95), (-0.1, -0.35, f + 0.85), 45, 0.0)]
    light("warm")
    tiles = []
    for name, loc, at, lens, t in cu:
        blades(t, t == 0.0)
        camera(loc, at, lens=lens)
        tiles.append(shoot(f"cu_{name}"))
    save([tiles[:3], tiles[3:]], OUT / "closeups.png")
    print("SHEET done", OUT)


if __name__ == "__main__":
    main()
