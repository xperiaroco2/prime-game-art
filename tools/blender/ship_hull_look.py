"""A quick look at the built exterior (art #263, hull lane; docs/ship.md "The hull's details"): every exterior.toml
placement except the clearing, from its GLB in the pieces folder, in headless Blender (Workbench, material colours,
studio light, cavity): the approved 2D crops over front, side, back and top, then a three-quarter and three close-ups
(a canopy, the pods, a leg with its lamp). One sheet, 4 x 320 px wide; cheaper than a Godot shoot for checking shape.

    blender -b --factory-startup --python ship_hull_look.py -- --pieces <dir> --out <dir> [--crops <dir>]"""

from __future__ import annotations

import math
import sys
import tomllib
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ship_hull_grid as G  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CLEARING = ("ground", "pine", "rock", "bush", "log", "tuft", "path", "party")
REFS = ("turnaround_1_front.png", "turnaround_2_side.png", "turnaround_3_back.png", "turnaround_4_top.png")
# (eye, look, fov) in plan coordinates (x east, y south, h up); None: an ortho view
VIEWS = {
    "front": ("ORTHO", (0, -40, 3.0), (math.pi / 2, 0, math.pi), 29.0),
    "side": ("ORTHO", (-40, 0, 3.0), (math.pi / 2, 0, -math.pi / 2), 19.0),
    "back": ("ORTHO", (0, 40, 3.0), (math.pi / 2, 0, 0), 29.0),
    "top": ("ORTHO", (0, 0.5, 40), (0, 0, 0), 29.0),
    "q": ((-17.0, -16.0, 8.0), (0.5, 0.0, 2.0), 50.0),
    "canopy": ((-1.0, -9.0, 6.4), (2.0, -3.2, 4.6), 38.0),
    "pods": ((7.5, 13.5, 4.5), (0.0, 5.5, 2.4), 45.0),
    "leg": ((10.5, -5.0, 1.6), (7.6, -1.0, 0.5), 50.0),
}


def place(scene, pieces: Path) -> int:
    with (ROOT / "layouts" / "ship" / "exterior.toml").open("rb") as f:
        data = tomllib.load(f)
    rows = [p for p in data["place"] if not p[0].startswith(CLEARING)]
    colls = {}
    for pid in sorted({p[0] for p in rows}):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(pieces / f"{pid}.glb"))
        coll = bpy.data.collections.new(pid)
        for obj in set(bpy.data.objects) - before:
            for c in list(obj.users_collection):
                c.objects.unlink(obj)
            coll.objects.link(obj)
        colls[pid] = coll
    for i, (pid, (x, y, h), yaw) in enumerate(rows):
        inst = bpy.data.objects.new(f"{pid}.{i}", None)
        inst.instance_type, inst.instance_collection = "COLLECTION", colls[pid]
        inst.location, inst.rotation_euler = (x, -y, h), (0.0, 0.0, math.radians(yaw))
        scene.collection.objects.link(inst)
    return len(rows)


def camera(scene, view):
    cam = scene.camera
    spec = VIEWS[view]
    if spec[0] == "ORTHO":
        _t, (x, y, h), rot, scale = spec
        cam.data.type, cam.data.ortho_scale = "ORTHO", scale
        cam.location, cam.rotation_euler = (x, -y, h), rot
        return
    eye, look, fov = spec
    cam.data.type = "PERSP"
    e, t = Vector((eye[0], -eye[1], eye[2])), Vector((look[0], -look[1], look[2]))
    cam.location = e
    cam.rotation_euler = (t - e).to_track_quat("-Z", "Y").to_euler()
    cam.data.angle = math.radians(fov)


def main():
    pieces, out = Path(G.arg("--pieces")), Path(G.arg("--out"))
    crops = Path(G.arg("--crops", "D:/prime-art-raw/ship/v1/meshy_in"))
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light, sh.color_type, sh.show_cavity, sh.show_shadows = "STUDIO", "MATERIAL", True, True
    sh.background_type, sh.background_color = "VIEWPORT", (0.1, 0.12, 0.16)
    scene.render.resolution_x, scene.render.resolution_y = G.W * 2, G.H_ * 2
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.data.clip_end = 300.0
    scene.collection.objects.link(cam)
    scene.camera = cam
    print(f"LOOK placed {place(scene, pieces)}")
    rows = [np.concatenate([G.pixels(crops / r) if (crops / r).exists() else G.pixels(G.REFS[3]) for r in REFS], axis=1)]
    for names in (("front", "side", "back", "top"), ("q", "canopy", "pods", "leg")):
        cells = []
        for view in names:
            camera(scene, view)
            scene.render.filepath = str(out / f"{view}.png")
            bpy.ops.render.render(write_still=True)
            cells.append(G.pixels(out / f"{view}.png"))
        rows.append(np.concatenate(cells, axis=1))
    sheet = np.concatenate(rows[::-1], axis=0)
    img = bpy.data.images.new("sheet", sheet.shape[1], sheet.shape[0])
    img.pixels.foreach_set(sheet.ravel())
    img.filepath_raw, img.file_format = str(out / "look.png"), "PNG"
    img.save()
    print(f"LOOK sheet {out / 'look.png'}")


if __name__ == "__main__":
    main()
