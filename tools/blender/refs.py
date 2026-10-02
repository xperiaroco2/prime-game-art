"""Clean orthographic reference images of the scene's visible meshes, for image-to-image and multi-image-to-3D.

Imported by scripts in tools/blender/ (mannequin.py), never run on its own. Every view has the same scale and centre,
so the front, side and back line up: the scale fits the largest of the model's height, width and depth with a small
margin, so the whole body fills the square frame. Workbench, no outline, no cavity, no shadow, no specular, no text,
on a pure white background. Light "studio" is Workbench's soft default studio light, even and without cast shadows,
which keeps the forms readable; "flat" is unlit flat colour (silhouettes and colour regions only).
"""

from __future__ import annotations

from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

# name -> direction from the model's centre to the camera. The model faces -Y; "side" shows its left side (+X).
VIEWS = {"front": (0.0, -1.0, 0.0), "side": (1.0, 0.0, 0.0), "back": (0.0, 1.0, 0.0)}
MARGIN = 1.03


def visible_points() -> list[Vector]:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    points: list[Vector] = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or obj.hide_get() or obj.hide_render:
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        points.extend(evaluated.matrix_world @ v.co for v in mesh.vertices)
        evaluated.to_mesh_clear()
    if not points:
        raise RuntimeError("no visible mesh to render")
    return points


def sync_viewport_colours() -> None:
    """Workbench reads a material's viewport colour; copy each plain Principled base colour into it."""
    for material in bpy.data.materials:
        tree = material.node_tree
        node = tree and next((n for n in tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if node and not node.inputs["Base Color"].is_linked:
            material.diffuse_color = tuple(node.inputs["Base Color"].default_value)


def setup(size: int, light: str) -> bpy.types.Object:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.display.render_aa = "16"
    scene.render.dither_intensity = 0.0  # no noise: the background stays exactly white
    world = scene.world or bpy.data.worlds.new("RefWorld")
    scene.world = world
    world.color = (1.0, 1.0, 1.0)
    shading = scene.display.shading
    shading.light = "FLAT" if light == "flat" else "STUDIO"
    if light != "flat":
        shading.studio_light = "Default"
    shading.color_type = "MATERIAL"
    shading.show_cavity = False
    shading.show_object_outline = False
    shading.show_shadows = False
    shading.show_specular_highlight = False
    shading.show_xray = False
    sync_viewport_colours()
    camera = scene.objects.get("RefCamera")
    if camera is None:
        camera = bpy.data.objects.new("RefCamera", bpy.data.cameras.new("RefCamera"))
        scene.collection.objects.link(camera)
    camera.data.type = "ORTHO"
    scene.camera = camera
    return camera


def measure(path: Path) -> dict:
    """The corner colours (0..255) and the box of non-white pixels (left, top, right, bottom; from the top left) of a
    rendered image, so a caller can confirm the background is white and the model fills the frame."""
    image = bpy.data.images.load(str(path))
    width, height = image.size
    pixels = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    bpy.data.images.remove(image)
    rgb = np.round(pixels.reshape(height, width, 4)[::-1, :, :3] * 255).astype(int)
    corners = [rgb[0, 0], rgb[0, -1], rgb[-1, 0], rgb[-1, -1]]
    ys, xs = np.nonzero((rgb < 250).any(axis=2))
    box = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else None
    return {"corners": [[int(c) for c in corner] for corner in corners], "content_box": box}


def render(out: Path, size: int = 1024, light: str = "studio") -> dict:
    """Writes front.png, side.png and back.png into out; returns where they went and the framing."""
    points = visible_points()
    low = Vector((min(p[i] for p in points) for i in range(3)))
    high = Vector((max(p[i] for p in points) for i in range(3)))
    extent = high - low
    center = (low + high) / 2
    scale = max(extent) * MARGIN
    distance = max(extent) * 3 + 1.0
    camera = setup(size, light)
    camera.data.ortho_scale = scale
    camera.data.clip_start = 0.01
    camera.data.clip_end = distance * 2
    out.mkdir(parents=True, exist_ok=True)
    files, measured = {}, {}
    for name, direction in VIEWS.items():
        towards = Vector(direction)
        camera.location = center + towards * distance
        camera.rotation_euler = (-towards).to_track_quat("-Z", "Y").to_euler()
        path = out / f"{name}.png"
        bpy.context.scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        if not path.is_file():
            raise RuntimeError(f"Blender rendered no {path}")
        files[name] = path.as_posix()
        measured[name] = measure(path)
    return {"files": files, "measured": measured, "size": size, "light": light, "ortho_scale": round(scale, 4),
            "center": [round(v, 4) for v in center]}
