"""Line-up review sheets of the built props (art #82, docs/props.md), in headless Blender:

  blender -b --factory-startup --python-exit-code 1 --python tools/blender/props_task_review.py -- \
      --spec props/tasks.toml --glbs D:/prime-art-raw/props/task/v1 --out D:/prime-art-raw/review/house/82

Imports each prop's GLB (its colliders hidden; a switch shows its `on` state), stands a 1.8 m grey capsule (0.5 m
wide) at its left, and renders it from the front and from three-quarters (Workbench, the paint from the vertex
colours, cavity and shadow, orthographic so the sizes compare). One sheet per group, 1280 px wide: two props a row,
each as a front and a 3/4 cell of 320 px. `switch_8m.png` (1280 x 720) shows the post switch on and off from 8 m at
a 1.6 m eye height (Godot's default 75 degree vertical field of view), the question of #82b's acceptance.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import props_task  # noqa: E402
import render_views as rv  # noqa: E402

CELL = 320
CAPSULE_H, CAPSULE_R = 1.8, 0.25
GROUPS = [
    ("delivery", lambda p: p["chain"] == "delivery"),
    ("burgers", lambda p: p["chain"] == "burgers"),
    ("power", lambda p: p["chain"] == "generator" or p["id"] in ("boiler", "pump", "water_tank", "switchboard",
                                                                   "cable_drum")),
    ("photo_repair", lambda p: p["chain"] in ("photo", "car_repair", "other") or p["id"] in ("enlarger",
                                                                                           "tray_table")),
    ("house_yard", lambda p: p["id"] in ("toy_chest", "utility_pole", "birdbath", "bulkhead_stairs")),
]


def args() -> dict:
    argv = sys.argv[sys.argv.index("--") + 1:]
    return {argv[i].lstrip("-"): argv[i + 1] for i in range(0, len(argv), 2)}


def clear() -> None:
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for me in list(bpy.data.meshes):
        bpy.data.meshes.remove(me)


def srgb_paint_to_linear(obj) -> None:
    """COLOR_0 holds sRGB-encoded paint for Godot's -vcol import (docs/kit.md); Workbench reads it as linear."""
    attr = obj.data.color_attributes.active_color
    if attr is None:
        return
    px = np.empty(len(attr.data) * 4, dtype=np.float32)
    attr.data.foreach_get("color", px)
    px = px.reshape(-1, 4)
    c = px[:, :3]
    px[:, :3] = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    attr.data.foreach_set("color", px.ravel())


def import_prop(glb: Path, offset=(0.0, 0.0, 0.0), state: str = "on") -> list:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(glb))
    new = [o for o in bpy.data.objects if o not in before]
    shown = []
    for o in new:
        hide = "convcolonly" in o.name or o.type != "MESH" or (o.name.endswith(("_on", "_off"))
                                                               and not o.name.endswith(f"_{state}"))
        o.hide_render = hide
        if o.parent is None:
            o.location = Vector(o.location) + Vector(offset)
        if not hide:
            srgb_paint_to_linear(o)
            shown.append(o)
    return shown


def capsule(x: float) -> None:
    bpy.ops.mesh.primitive_cylinder_add(radius=CAPSULE_R, depth=CAPSULE_H - 2 * CAPSULE_R,
                                        location=(x, 0, CAPSULE_H / 2), vertices=24)
    body = bpy.context.object
    for z in (CAPSULE_R, CAPSULE_H - CAPSULE_R):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=CAPSULE_R, location=(x, 0, z), segments=24, ring_count=12)
    for o in (body, bpy.context.object):
        o.color = (0.55, 0.55, 0.58, 1)


def world_bounds(objs) -> tuple[np.ndarray, np.ndarray]:
    bpy.context.view_layer.update()
    pts = np.array([list(o.matrix_world @ Vector(c)) for o in objs for c in o.bound_box])
    return pts.min(axis=0), pts.max(axis=0)


def setup(width: int, height: int):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x, scene.render.resolution_y = width, height
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"
    sh = scene.display.shading
    sh.light = "STUDIO"
    sh.studio_light = "Default"
    sh.color_type = "VERTEX"
    sh.show_cavity = True
    sh.cavity_type = "WORLD"
    sh.show_shadows = True
    sh.show_object_outline = True
    sh.object_outline_color = (0.12, 0.12, 0.12)
    cam = bpy.data.objects.get("ReviewCam")
    if cam is None:
        cam = bpy.data.objects.new("ReviewCam", bpy.data.cameras.new("ReviewCam"))
    if cam.name not in scene.collection.objects:
        scene.collection.objects.link(cam)
    scene.camera = cam
    return cam


def aim(cam, lo, hi, azimuth: float, elevation: float) -> None:
    """Orthographic, looking at the box's centre; azimuth 0 is the front (Blender -Y), positive to the right."""
    a, e = math.radians(azimuth), math.radians(elevation)
    d = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
    centre = Vector(((lo + hi) / 2).tolist())
    size = float(np.linalg.norm(hi - lo))
    cam.data.type = "ORTHO"
    cam.location = centre + d * (size * 2 + 2)
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    rot = cam.rotation_euler.to_matrix()
    right, up = rot @ Vector((1, 0, 0)), rot @ Vector((0, 1, 0))
    corners = [Vector((x, y, z)) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    w = max(c.dot(right) for c in corners) - min(c.dot(right) for c in corners)
    h = max(c.dot(up) for c in corners) - min(c.dot(up) for c in corners)
    cam.data.ortho_scale = max(w, h) * 1.12
    cam.data.clip_start, cam.data.clip_end = 0.01, size * 6 + 10


def render(path: Path) -> np.ndarray:
    rv.render_to(path)
    return rv.read_png(path)


def paste(sheet, img, top, left) -> None:
    h, w = img.shape[:2]
    tile = sheet[top:top + h, left:left + w]
    alpha = img[:, :, 3:4]
    tile[:] = img[:, :, :3] * alpha + tile * (1 - alpha)


def lineups(spec: dict, glbs: Path, out: Path) -> list[str]:
    cells = out / "cells"
    cells.mkdir(parents=True, exist_ok=True)
    made = []
    scale = rv.label_scale(CELL) // 2 or 1
    for name, pick in GROUPS:
        props = [p for p in spec["props"] if pick(p)]
        if not props:
            continue
        rows = math.ceil(len(props) / 2)
        band = 24
        sheet = np.empty((band + rows * CELL, 4 * CELL, 3), dtype=np.float32)
        sheet[:] = rv.BACKGROUND
        rv.draw_text(sheet, f"#82 PROPS: {name.upper()}  (FRONT, 3/4; CAPSULE 1.8 M)", 6, 6, 2)
        for i, p in enumerate(props):
            clear()
            cam = setup(CELL, CELL)
            objs = import_prop(glbs / f"{p['id']}.glb")
            lo, hi = world_bounds(objs)
            capsule(float(lo[0]) - 0.35 - CAPSULE_R)
            lo, hi = world_bounds([o for o in bpy.data.objects if o.type == "MESH" and not o.hide_render])
            top, left = band + (i // 2) * CELL, (i % 2) * 2 * CELL
            for k, (az, el) in enumerate(((0, 4), (38, 24))):
                aim(cam, lo, hi, az, el)
                img = render(cells / f"{p['id']}_{k}.png")
                paste(sheet, img, top, left + k * CELL)
            sheet[top, left:left + 2 * CELL] = 0.7
            sheet[top:top + CELL, left] = 0.7
            size = f"{p['w']:g}X{p['d']:g}X{p['h']:g} M"
            rv.draw_text(sheet, f"{p['id']}  {size}", left + 6, top + 6, scale)
        path = out / f"lineup_{name}.png"
        rv.write_png(path, sheet)
        made.append(str(path))
        print(f"REVIEW {path}")
    return made


def switch_8m(glbs: Path, out: Path) -> str:
    clear()
    cam = setup(1280, 720)
    for x, state in ((-0.7, "on"), (0.7, "off")):
        import_prop(glbs / "wall_switch_post.glb", (x, 0, 0), state)
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 2, 0))
    floor = bpy.context.object
    floor.color = (0.45, 0.43, 0.4, 1)
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 1.0, 0), rotation=(math.radians(90), 0, 0))
    wall = bpy.context.object
    wall.color = (0.23, 0.38, 0.39, 1)
    for o in (floor, wall):  # planes have no paint: give them vertex colours
        attr = o.data.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
        for d in attr.data:
            d.color = o.color
    cam.data.type = "PERSP"
    cam.data.sensor_fit = "VERTICAL"
    cam.data.angle_y = math.radians(75)
    cam.location = (0, -8, 1.6)
    cam.rotation_euler = (Vector((0, 0, 1.3)) - Vector(cam.location)).to_track_quat("-Z", "Y").to_euler()
    path = out / "switch_8m.png"
    img = render(out / "cells" / "switch_8m_raw.png")
    canvas = np.empty((720, 1280, 3), dtype=np.float32)
    canvas[:] = rv.BACKGROUND
    paste(canvas, img, 0, 0)
    rv.draw_text(canvas, "WALL_SWITCH_POST FROM 8 M, EYE 1.6 M, FOV 75: LEFT ON, RIGHT OFF", 8, 8, 2)
    rv.write_png(path, canvas)
    print(f"REVIEW {path}")
    return str(path)


def main() -> None:
    a = args()
    spec = props_task.load_spec(Path(a["spec"]))
    glbs, out = Path(a["glbs"]), Path(a["out"])
    out.mkdir(parents=True, exist_ok=True)
    lineups(spec, glbs, out)
    switch_8m(glbs, out)


if __name__ == "__main__":
    main()
