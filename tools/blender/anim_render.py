"""Workbench rendering for the animation review: flat material colours, specular off, a neutral background, a floor
line, orthographic front and side cameras, labels as text objects, frame strips composed with numpy and looping
H.264 clips through Blender's FFmpeg. Background Blender only (docs/animations.md)."""

from __future__ import annotations

import math
import os

import bpy
import numpy as np
from mathutils import Euler, Vector

BACKGROUND = (0.80, 0.80, 0.78)
FLOOR = (0.30, 0.30, 0.30, 1.0)
INK = (0.06, 0.06, 0.06, 1.0)
VIEWS = {  # camera Euler angles (degrees): front looks along +Y at the character's face, side along +X at its right
    "front": (90.0, 0.0, 0.0),
    "side": (90.0, 0.0, -90.0),
    "three_quarter": (82.0, 0.0, -30.0),
}


def setup(scene) -> None:
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light = "STUDIO"
    sh.color_type = "MATERIAL"
    sh.show_specular_highlight = False
    scene.display.render_aa = "8"
    scene.view_settings.view_transform = "Standard"
    scene.world = bpy.data.worlds.new("bg")
    scene.world.color = BACKGROUND
    scene.render.film_transparent = False
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.type = "ORTHO"
    cam.data.sensor_fit = "VERTICAL"
    cam.data.clip_end = 400
    floor = bpy.data.objects.new("floor", bpy.data.meshes.new("floor"))
    s, t = 40.0, 0.012  # a 40 m slab whose top is the floor (z = 0): a line in the horizontal views
    v = [(-s, -s, -t), (s, -s, -t), (s, s, -t), (-s, s, -t), (-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    floor.data.from_pydata(v, [], f)
    floor.data.materials.append(material("floor", FLOOR))
    scene.collection.objects.link(floor)


def material(name: str, rgba) -> bpy.types.Material:
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = rgba
    return m


def text(name: str, size: float, view: str = "front", align: str = "CENTER"):
    cu = bpy.data.curves.new(name, "FONT")
    cu.size, cu.align_x = size, align
    cu.materials.append(material("ink", INK))
    obj = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(obj)
    obj.rotation_euler = Euler(tuple(math.radians(a) for a in VIEWS[view]))
    return obj


def aim(view: str, centre: Vector, height: float, width_px: int, height_px: int) -> None:
    """Points the orthographic camera along a view at centre, `height` metres tall in the picture."""
    scene = bpy.context.scene
    cam = scene.camera
    cam.rotation_euler = Euler(tuple(math.radians(a) for a in VIEWS[view]))
    forward = cam.rotation_euler.to_matrix() @ Vector((0.0, 0.0, -1.0))
    cam.location = centre - forward * 50.0
    cam.data.ortho_scale = height
    scene.render.resolution_x, scene.render.resolution_y = width_px, height_px


def render(path: str) -> np.ndarray:
    """Renders the scene to a PNG and returns it as a float RGB array, top row first."""
    scene = bpy.context.scene
    scene.render.image_settings.media_type = "IMAGE"
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return read_png(path)


def read_png(path: str) -> np.ndarray:
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    arr = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(arr)
    bpy.data.images.remove(img)
    return arr.reshape(h, w, 4)[::-1, :, :3].copy()


def save_png(arr: np.ndarray, path: str) -> None:
    h, w = arr.shape[:2]
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[..., :3] = arr
    img = bpy.data.images.new("out", w, h, alpha=False)
    img.pixels.foreach_set(rgba[::-1].ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def grid(rows: list[list[np.ndarray]], gap: int = 2, shade: float = 0.55) -> np.ndarray:
    """Joins equal-height cells into rows and rows into one picture, with thin grey gaps."""
    joined = []
    for row in rows:
        parts = []
        for k, cell in enumerate(row):
            if k:
                parts.append(np.full((cell.shape[0], gap, 3), shade, dtype=np.float32))
            parts.append(cell)
        joined.append(np.concatenate(parts, axis=1))
    width = max(r.shape[1] for r in joined)
    out = []
    for k, r in enumerate(joined):
        if r.shape[1] < width:
            r = np.concatenate([r, np.ones((r.shape[0], width - r.shape[1], 3), dtype=np.float32)], axis=1)
        if k:
            out.append(np.full((gap, width, 3), shade, dtype=np.float32))
        out.append(r)
    return np.concatenate(out, axis=0)


def video_settings(path: str, width: int, height: int, start: int, end: int) -> None:
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = width, height
    ims = scene.render.image_settings
    ims.media_type = "VIDEO"
    ims.file_format = "FFMPEG"
    ims.color_mode = "RGB"
    ff = scene.render.ffmpeg
    ff.format = "MPEG4"
    ff.codec = "H264"
    ff.constant_rate_factor = "MEDIUM"
    ff.ffmpeg_preset = "GOOD"
    ff.gopsize = 12
    ff.audio_codec = "NONE"
    scene.render.use_file_extension = False
    scene.render.filepath = path
    scene.frame_start, scene.frame_end = start, end
    os.makedirs(os.path.dirname(path), exist_ok=True)


def render_video(path: str, width: int, height: int, frames: int, pose_frame) -> None:
    """Renders frames 0..frames-1 into an H.264 MP4; pose_frame(f) poses the scene for frame f (a frame-change
    handler, so Blender's own animation render drives it)."""

    def handler(scene, *_):
        pose_frame(scene.frame_current)

    video_settings(path, width, height, 0, frames - 1)
    bpy.app.handlers.frame_change_pre.append(handler)
    try:
        bpy.ops.render.render(animation=True)
    finally:
        bpy.app.handlers.frame_change_pre.remove(handler)
        bpy.context.scene.render.image_settings.media_type = "IMAGE"
        bpy.context.scene.render.image_settings.file_format = "PNG"
