"""Render helpers: Workbench with flat material colours and specular off (with it on, decals looked grey on dark
skin and the flat-shaded pack meshes showed a checkerboard sheen), an orthographic camera fitted to objects, text
labels, and side-by-side composition of PNGs."""

import math

import bpy
from mathutils import Euler, Vector

from .util import world_points

# Output size in percent of the nominal pixel sizes (tests render small); framing does not change.
RES_PERCENT = 100

# Camera yaw per hand view; in34 is the three-quarter view from the body's midline (thumb side).
VIEW_YAW = {"front": 0, "34": 40, "side": 90, "back": 180, "in34": -40}


def setup_render():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light = "STUDIO"
    sh.color_type = "MATERIAL"
    sh.show_specular_highlight = False
    scene.display.render_aa = "16"
    scene.view_settings.view_transform = "Standard"
    scene.world = bpy.data.worlds.new("bg")
    scene.world.color = (0.66, 0.66, 0.66)
    scene.render.film_transparent = False
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.type = "ORTHO"
    cam.data.clip_end = 200
    return cam


def render(path, objs, rot, height=1200, margin=1.08, min_width=500, centre=None, extent=None, width=None):
    """Ortho camera at Euler rot (degrees) fitted to objs (evaluated), height px tall."""
    scene = bpy.context.scene
    cam = scene.camera
    cam.rotation_euler = Euler(tuple(math.radians(a) for a in rot))
    Rm = cam.rotation_euler.to_matrix(); Ri = Rm.inverted()
    pts = [Ri @ p for p in world_points(objs)]
    x0, x1 = min(p.x for p in pts), max(p.x for p in pts)
    y0, y1 = min(p.y for p in pts), max(p.y for p in pts)
    z1 = max(p.z for p in pts)
    if centre is not None:
        c = Ri @ centre
        cx, cy = c.x, c.y
        w = h = extent
    else:
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        w, h = (x1 - x0) * margin, (y1 - y0) * margin
    if width is None:
        width = max(min_width, int(round(height * w / h)))
    scene.render.resolution_x, scene.render.resolution_y = width, height
    scene.render.resolution_percentage = RES_PERCENT
    cam.data.sensor_fit = "VERTICAL"
    cam.data.ortho_scale = max(h, w * height / width)
    cam.location = Rm @ Vector((cx, cy, z1 + 10))
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("RENDERED", path, width * RES_PERCENT // 100, "x", height * RES_PERCENT // 100)


def label(text, loc, size=0.07, coll=None):
    cu = bpy.data.curves.new("lbl", "FONT"); cu.body = text; cu.size = size; cu.align_x = "CENTER"
    t = bpy.data.objects.new("lbl", cu)
    (coll or bpy.context.scene.collection).objects.link(t)
    t.location = loc; t.rotation_euler = (math.radians(90), 0, 0)
    m = bpy.data.materials.get("label") or bpy.data.materials.new("label"); m.diffuse_color = (0.05, 0.05, 0.05, 1)
    cu.materials.append(m)
    return t


def compose(paths, out):
    """The PNGs side by side, bottom-aligned on white, with a grey 6 px separator."""
    import numpy as np

    imgs = [bpy.data.images.load(p) for p in paths]
    arrs = [np.array(im.pixels[:], dtype=np.float32).reshape(im.size[1], im.size[0], 4) for im in imgs]
    h = max(a.shape[0] for a in arrs)
    arrs = [np.pad(a, ((h - a.shape[0], 0), (0, 0), (0, 0)), constant_values=1.0) for a in arrs]
    sep = np.ones((h, 6, 4), dtype=np.float32); sep[..., :3] = 0.55
    row = arrs[0]
    for a in arrs[1:]:
        row = np.concatenate([row, sep, a], axis=1)
    img = bpy.data.images.new("comp", row.shape[1], row.shape[0], alpha=True)
    img.pixels.foreach_set(row.ravel())
    img.filepath_raw = out; img.file_format = "PNG"; img.save()
    for im in imgs + [img]:
        bpy.data.images.remove(im)
    print("COMPOSED", out, row.shape[1], "x", row.shape[0])


def facing_deg(arm):
    """Yaw of the posed body: average of the shoulder and hip left-right axes (0 = facing -Y like the rest pose)."""
    mw = arm.matrix_world; pb = arm.pose.bones
    v = (mw @ pb["UpperArm.L"].head - mw @ pb["UpperArm.R"].head).normalized() + (mw @ pb["UpperLeg.L"].head - mw @ pb["UpperLeg.R"].head).normalized()
    return math.degrees(math.atan2(v.y, v.x))
