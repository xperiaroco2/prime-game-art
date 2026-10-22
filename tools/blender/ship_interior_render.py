"""Night check renders of the ship's INTERIOR in headless Blender (art #263, docs/ship.md): the INTERIOR lane's own
look check before the Godot shots. Imports each piece GLB once, instances it at every placement of
layouts/ship/interior.toml, lights the scene with ship.toml's [light] lamps and a moon, renders the views with Eevee and
writes a compare sheet (the approved 2D left, the render right; about 1280 px wide).

    blender -b --factory-startup --python ship_interior_render.py -- --root <repo> --pieces <dir> --out <dir>
        [--views name,name] [--size 640x360] [--refs <2d dir>]"""

from __future__ import annotations

import math
import sys
import tomllib
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

# name: (eye [x, y, h], look [x, y, h], fov, the 2D sheet it answers)
VIEWS = {
    "in_hall": ((0.0, -4.3, 2.6), (0.0, 2.0, 2.45), 75.0, "hall_in-3.jpg"),
    "in_hall_out": ((0.0, 2.6, 2.7), (0.0, -4.0, 2.3), 75.0, "hall_out-2.jpg"),
    "in_corridor_e": ((3.0, 0.0, 2.6), (10.0, 0.0, 2.3), 70.0, "corridor.jpg"),
    "in_corridor_w": ((-3.0, 0.0, 2.6), (-10.0, 0.0, 2.3), 70.0, "corridor.jpg"),
    "in_tip_e": ((8.9, 0.0, 2.6), (12.5, 0.0, 2.15), 80.0, "tip-3.jpg"),
    "in_tip_w": ((-8.9, 0.0, 2.6), (-12.5, 0.0, 2.15), 80.0, "tip-3.jpg"),
    "close_seam": ((1.75, 1.17, 3.6), (2.83, 1.89, 3.95), 45.0, "materials-3.jpg"),
    "close_floor": ((5.6, 0.1, 1.9), (5.03, -1.0, 1.0), 55.0, "materials-3.jpg"),
    "close_cable": ((5.0, -0.1, 2.3), (5.03, -1.3, 2.25), 45.0, "materials-3.jpg"),
}


def arg(name: str, default=None):
    argv = sys.argv[sys.argv.index("--") + 1:]
    return argv[argv.index(name) + 1] if name in argv else default


def setup(scene, ship: dict) -> None:
    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = engine
            break
        except TypeError:
            continue
    ee = scene.eevee
    for attr, val in (("taa_render_samples", 48), ("use_raytracing", True), ("use_shadows", True),
                      ("use_gtao", True), ("use_bloom", True)):
        if hasattr(ee, attr):
            setattr(ee, attr, val)
    scene.view_settings.view_transform = "AgX" if "AgX" in [i.identifier for i in
                                                            scene.view_settings.bl_rna.properties["view_transform"]
                                                            .enum_items] else "Filmic"
    world = bpy.data.worlds.new("night")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.006, 0.009, 0.02, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
    scene.world = world
    pitch, yaw = ship["light"]["moon_dir_deg"]
    sun = bpy.data.objects.new("moon", bpy.data.lights.new("moon", "SUN"))
    sun.data.energy, sun.data.color = 0.35, (0.7, 0.8, 1.0)
    sun.rotation_euler = (math.radians(90 + pitch), 0.0, math.radians(yaw))
    scene.collection.objects.link(sun)
    for i, (x, y, h, energy, rng, r, g, b) in enumerate(ship["light"]["lamps"]):
        lamp = bpy.data.objects.new(f"lamp{i}", bpy.data.lights.new(f"lamp{i}", "POINT"))
        lamp.data.energy, lamp.data.color, lamp.data.shadow_soft_size = 30.0 * energy, (r, g, b), 0.15
        lamp.location = (x, -y, h)
        scene.collection.objects.link(lamp)


def place(scene, root: Path, pieces: Path) -> int:
    with (root / "layouts" / "ship" / "interior.toml").open("rb") as f:
        data = tomllib.load(f)
    colls = {}
    for pid in sorted({p[0] for p in data["place"]}):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(pieces / f"{pid}.glb"))
        coll = bpy.data.collections.new(pid)
        for obj in set(bpy.data.objects) - before:
            for c in list(obj.users_collection):
                c.objects.unlink(obj)
            coll.objects.link(obj)
        colls[pid] = coll
    for i, (pid, (x, y, h), yaw) in enumerate(data["place"]):
        inst = bpy.data.objects.new(f"{pid}.{i}", None)
        inst.instance_type, inst.instance_collection = "COLLECTION", colls[pid]
        inst.location, inst.rotation_euler = (x, -y, h), (0.0, 0.0, math.radians(yaw))
        scene.collection.objects.link(inst)
    return len(data["place"])


def camera(scene, eye, look, fov):
    cam = scene.camera
    if cam is None:
        cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
        scene.collection.objects.link(cam)
        scene.camera = cam
    e, t = Vector((eye[0], -eye[1], eye[2])), Vector((look[0], -look[1], look[2]))
    cam.location = e
    cam.rotation_euler = (t - e).to_track_quat("-Z", "Y").to_euler()
    cam.data.angle = math.radians(fov)
    cam.data.clip_start = 0.03


def pixels(path: Path, w: int, h: int) -> np.ndarray:
    img = bpy.data.images.load(str(path))
    sw, sh = img.size
    s = min(w / sw, h / sh)
    img.scale(max(1, int(sw * s)), max(1, int(sh * s)))
    iw, ih = img.size
    buf = np.empty(iw * ih * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    cell = np.zeros((h, w, 4), dtype=np.float32)
    cell[..., 3] = 1.0
    y0, x0 = (h - ih) // 2, (w - iw) // 2
    cell[y0:y0 + ih, x0:x0 + iw] = buf.reshape(ih, iw, 4)
    bpy.data.images.remove(img)
    return cell


def main() -> None:
    root, pieces, out = Path(arg("--root")), Path(arg("--pieces")), Path(arg("--out"))
    refs = Path(arg("--refs", "D:/prime-game-design/ideas/ship-components/2d"))
    w, h = (int(v) for v in arg("--size", "640x360").split("x"))
    names = arg("--views", ",".join(VIEWS)).split(",")
    out.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    with (root / "layouts" / "ship" / "ship.toml").open("rb") as f:
        ship = tomllib.load(f)
    setup(scene, ship)
    n = place(scene, root, pieces)
    print(f"SHIPR placed {n}")
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = w, h, 100
    rows = []
    for name in names:
        eye, look, fov, ref = VIEWS[name]
        camera(scene, eye, look, fov)
        scene.render.filepath = str(out / f"{name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"SHIPR rendered {name}")
        left = pixels(refs / ref, w, h) if (refs / ref).is_file() else np.zeros((h, w, 4), np.float32)
        rows.append(np.concatenate([left, pixels(out / f"{name}.png", w, h)], axis=1))
    sheet = np.concatenate(rows[::-1], axis=0)
    img = bpy.data.images.new("sheet", sheet.shape[1], sheet.shape[0])
    img.pixels.foreach_set(sheet.ravel())
    img.filepath_raw, img.file_format = str(out / "compare.png"), "PNG"
    img.save()
    print(f"SHIPR sheet {out / 'compare.png'}")


if __name__ == "__main__":
    main()
