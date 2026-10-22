"""The hull skin's silhouette grid (art #263, hull lane; docs/ship.md "The hull skin"): every variant of
ship_hull_skin.VARIANTS in four views (front, side from the west, top with the nose up, three-quarter) with the rooms
as an orange ghost inside (Workbench, X-ray), under a row of the approved 2D (turnaround's front, side and top crops and
hero.jpg) and a row of the Meshy silhouette reference scaled to the footprint. One sheet, 4 x 320 px wide.

    blender -b --factory-startup --python ship_hull_grid.py -- --out <dir> [--ref <glb>] [--crops <dir>]
        [--variants A,B,C,D]

Prints per variant the room points outside the skin (SKIN clear) and the footprint rows for ship.toml [hull]."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ship_hull_skin as S  # noqa: E402

W, H_ = 320, 180
SPAN = 27.5            # the manager's update 2: the span up to about 27.5 m (the lens blades)
PARTS = ("body", "wing1", "wing2", "wing3", "tip")
REFS = ("turnaround_1_front.png", "turnaround_2_side.png", "turnaround_4_top.png",
        "D:/prime-game-design/ideas/ship-components/2d/hero.jpg")


def arg(name, default=None):
    argv = sys.argv[sys.argv.index("--") + 1:]
    return argv[argv.index(name) + 1] if name in argv else default


def mat(name, rgb):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1.0)
    return m


def mesh(name, verts, faces, m, coll):
    me = bpy.data.meshes.new(name)
    me.from_pydata([(x, -y, h) for x, y, h in verts], [], faces)
    me.validate()
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def ghost(coll):
    m = mat("room", (1.0, 0.45, 0.1))
    def cyl(name, cx, r, h0, h1, n=32):
        v = [(cx + r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n), h) for h in (h0, h1)
             for k in range(n)]
        f = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))] + [(k, (k + 1) % n, n + (k + 1) % n, n + k)
                                                                     for k in range(n)]
        mesh(name, v, f, m, coll)
    def box(name, x0, x1, y0, y1, h0, h1):
        v = [(x, y, h) for h in (h0, h1) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
        f = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        mesh(name, v, f, m, coll)
    f = S.FLOOR - 0.25  # the slabs' bottoms; tops: the rooms' ceilings (ship.toml's heights)
    cyl("hall", 0.0, 3.6, f, S.HALL_APEX)
    box("mouth", -1.5, 1.5, -4.6, -3.3, f, S.COR_TOP + 0.1)
    box("corr_w", -9.1, -3.3, -1.45, 1.45, f, S.COR_TOP + 0.1)
    box("corr_e", 3.3, 9.1, -1.45, 1.45, f, S.COR_TOP + 0.1)
    cyl("tip_w", -10.75, 2.25, f, S.TIP_TOP + 0.1)
    cyl("tip_e", 10.75, 2.25, f, S.TIP_TOP + 0.1)
    box("ramp", -1.3, 1.3, -7.4, -4.6, 0.0, 0.15)


def camera(scene, view):
    cam = scene.camera
    if view == "q":
        cam.data.type = "PERSP"
        e, t = Vector((-19.0, 17.0, 9.0)), Vector((0.5, 0.0, 1.8))
        cam.location = e
        cam.rotation_euler = (t - e).to_track_quat("-Z", "Y").to_euler()
        cam.data.angle = math.radians(50.0)
        return
    cam.data.type = "ORTHO"
    if view == "front":
        cam.location, cam.rotation_euler, cam.data.ortho_scale = (0, 40, 3.6), (math.pi / 2, 0, math.pi), 29.0
    elif view == "side":
        cam.location, cam.rotation_euler, cam.data.ortho_scale = (-40, 0, 3.2), (math.pi / 2, 0, -math.pi / 2), 19.0
    else:
        cam.location, cam.rotation_euler, cam.data.ortho_scale = (0, 0.3, 40), (0, 0, 0), 29.0


def pixels(path, w=W, h=H_):
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


def main():
    out = Path(arg("--out"))
    out.mkdir(parents=True, exist_ok=True)
    crops = Path(arg("--crops", "D:/prime-art-raw/ship/v1/meshy_in"))
    names = arg("--variants", ",".join(S.VARIANTS)).split(",")
    scene = bpy.context.scene
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light, sh.color_type = "STUDIO", "MATERIAL"
    sh.show_xray, sh.xray_alpha = True, 0.6
    sh.show_cavity, sh.cavity_type = True, "BOTH"
    sh.show_object_outline = True
    world = bpy.data.worlds.new("bg")
    world.color = (0.05, 0.07, 0.1)
    scene.world = world
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = W, H_, 100
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    rooms = bpy.data.collections.new("rooms")
    scene.collection.children.link(rooms)
    ghost(rooms)
    colls = {}
    skin = mat("skin", (0.72, 0.74, 0.78))
    layout = {"rooms": [{"id": "tip_e", "window": {"half_angle_deg": 65.0}}]}
    for name in names:
        coll = bpy.data.collections.new(f"v{name}")
        scene.collection.children.link(coll)
        for part in PARTS:
            for side in (1.0, -1.0):
                for p in S.hull_skin({"part": part, "side": side, "variant": name}, layout):
                    mesh(p["name"], p["verts"], p["faces"], skin, coll)
        colls[name] = coll
        var = S.VARIANTS[name]
        bad = S.clearance(var)
        steep = S.steep(var)
        print(f"SKIN steep {name}: {len(steep)} faces within 25 deg of vertical" + (f", e.g. {steep[:4]}" if steep else ""))
        print(f"SKIN clear {name}: {len(bad)} room points outside" + (f", e.g. {bad[:4]}" if bad else ""))
        print(f"SKIN outline {name}: " + ", ".join(f"[{x:.2f}, {a:.2f}, {b:.2f}]" for x, a, b in S.outline(var)))
    ref = arg("--ref")
    if ref:
        coll = bpy.data.collections.new("vref")
        scene.collection.children.link(coll)
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=ref)
        objs = [o for o in set(bpy.data.objects) - before if o.type == "MESH"]
        for o in set(bpy.data.objects) - before:
            for c in list(o.users_collection):
                c.objects.unlink(o)
            coll.objects.link(o)
        bpy.context.view_layer.update()
        from mathutils import Matrix
        for o in objs:
            o.data.transform(o.matrix_world)
            o.parent = None
            o.matrix_world = Matrix.Identity(4)
            o.data.materials.clear()
            o.data.materials.append(skin)
        pts = [v.co.copy() for o in objs for v in o.data.vertices]
        lo = Vector([min(p[k] for p in pts) for k in range(3)])
        hi = Vector([max(p[k] for p in pts) for k in range(3)])
        s = SPAN / (hi.y - lo.y)  # its span lies along y (Meshy faced it sideways)
        # its height scaled up only as much as the rooms need: its top over the hall's dome plus the skin
        sz = max(s, (S.HALL_APEX + 0.4) / (hi.z - lo.z))
        print(f"SKIN ref bbox {tuple(round(v, 3) for v in lo)} {tuple(round(v, 3) for v in hi)} scale {s:.3f} "
              f"height x {sz:.3f}")
        sc = Matrix.Diagonal((s, s, sz, 1.0))
        m = (Matrix.Translation((0.0, -0.5, 0.0)) @ Matrix.Rotation(-math.pi / 2, 4, "Z") @ sc
             @ Matrix.Translation(-Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))))
        for o in objs:
            o.data.transform(m)
        colls["ref"] = coll
    rows = [np.concatenate([pixels(crops / r if not r.startswith("D:") else r) for r in REFS], axis=1)]
    for key in (["ref"] if "ref" in colls else []) + names:
        for k, c in colls.items():
            c.hide_render = k != key
        cells = []
        for view in ("front", "side", "top", "q"):
            camera(scene, view)
            scene.render.filepath = str(out / f"{key}_{view}.png")
            bpy.ops.render.render(write_still=True)
            cells.append(pixels(out / f"{key}_{view}.png"))
        rows.append(np.concatenate(cells, axis=1))
        print(f"SKIN rendered {key}")
    sheet = np.concatenate(rows[::-1], axis=0)
    img = bpy.data.images.new("sheet", sheet.shape[1], sheet.shape[0])
    img.pixels.foreach_set(sheet.ravel())
    img.filepath_raw, img.file_format = str(out / "grid.png"), "PNG"
    img.save()
    print(f"SKIN sheet {out / 'grid.png'} rows: 2D, " + ", ".join((["meshy ref"] if "ref" in colls else []) + names))


if __name__ == "__main__":
    main()
