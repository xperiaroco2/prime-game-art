"""Renders a model into an 8-view review sheet (and optionally an animation contact sheet) in headless Blender.

    blender -b --factory-startup --python-exit-code 1 --python tools/blender/render_views.py -- \
        <model> --out DIR [--cell 512] [--anim ACTION] [--frames 8]

Imports GLB, glTF, FBX, OBJ or .blend. The model's front is -Y in Blender (+Z in glTF). Eight orthographic Workbench
views at 45-degree steps, front first and then counter-clockwise seen from above (the camera passes the model's left
side first), all at the same scale and centre, go into views/ and into sheet.png: 4 x 2 cells of --cell pixels on a
neutral light-grey background, each labelled with its angle, with a faint line at z = 0, and a caption naming the
model. stats.json describes the model. With --anim, anim_<action>.png (the name made file-safe) holds --frames evenly
spaced whole frames of that action, seen from the front. --pose ACTION shows the eight views at the first frame of that
action (to compare two models in the same pose). --no-outline drops the dark object outline.

Texture colours are used when any visible material has an image texture with pixels, material colours otherwise.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import zlib
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

BACKGROUND = (0.86, 0.86, 0.86)  # neutral light grey, sRGB
TEXT = (0.2, 0.2, 0.2)
GROUND = (0.62, 0.62, 0.62)
BORDER = (0.74, 0.74, 0.74)
MARGIN = 1.08  # the model fills about 92 percent of the cell along its largest extent
FEET_TOLERANCE = 0.01  # metres: feet count as "at 0" when the lowest point is within 1 cm of z = 0
COLUMNS = 4

VIEWS = [(0, "FRONT"), (45, ""), (90, "LEFT"), (135, ""), (180, "BACK"), (225, ""), (270, "RIGHT"), (315, "")]

# A 5 x 7 bitmap font for the labels: one string of 7 rows of 5 bits per glyph.
FONT = {
    "0": "01110 10001 10011 10101 11001 10001 01110",
    "1": "00100 01100 00100 00100 00100 00100 01110",
    "2": "01110 10001 00001 00010 00100 01000 11111",
    "3": "11110 00001 00001 01110 00001 00001 11110",
    "4": "00010 00110 01010 10010 11111 00010 00010",
    "5": "11111 10000 11110 00001 00001 10001 01110",
    "6": "00110 01000 10000 11110 10001 10001 01110",
    "7": "11111 00001 00010 00100 01000 01000 01000",
    "8": "01110 10001 10001 01110 10001 10001 01110",
    "9": "01110 10001 10001 01111 00001 00010 01100",
    "A": "01110 10001 10001 11111 10001 10001 10001",
    "B": "11110 10001 10001 11110 10001 10001 11110",
    "C": "01110 10001 10000 10000 10000 10001 01110",
    "E": "11111 10000 10000 11110 10000 10000 11111",
    "F": "11111 10000 10000 11110 10000 10000 10000",
    "G": "01110 10001 10000 10111 10001 10001 01111",
    "H": "10001 10001 10001 11111 10001 10001 10001",
    "I": "01110 00100 00100 00100 00100 00100 01110",
    "K": "10001 10010 10100 11000 10100 10010 10001",
    "L": "10000 10000 10000 10000 10000 10000 11111",
    "N": "10001 11001 10101 10011 10001 10001 10001",
    "O": "01110 10001 10001 10001 10001 10001 01110",
    "R": "11110 10001 10001 11110 10100 10010 10001",
    "T": "11111 00100 00100 00100 00100 00100 00100",
    "D": "11110 10001 10001 10001 10001 10001 11110",
    "J": "00111 00010 00010 00010 00010 10010 01100",
    "M": "10001 11011 10101 10101 10001 10001 10001",
    "P": "11110 10001 10001 11110 10000 10000 10000",
    "Q": "01110 10001 10001 10001 10101 10010 01101",
    "S": "01111 10000 10000 01110 00001 00001 11110",
    "U": "10001 10001 10001 10001 10001 10001 01110",
    "V": "10001 10001 10001 10001 10001 01010 00100",
    "W": "10001 10001 10001 10101 10101 10101 01010",
    "X": "10001 10001 01010 00100 01010 10001 10001",
    "Y": "10001 10001 01010 00100 00100 00100 00100",
    "Z": "11111 00001 00010 00100 01000 10000 11111",
    ".": "00000 00000 00000 00000 00000 01100 01100",
    "-": "00000 00000 00000 11111 00000 00000 00000",
    "_": "00000 00000 00000 00000 00000 00000 11111",
    ":": "00000 01100 01100 00000 01100 01100 00000",
    "/": "00001 00001 00010 00100 01000 10000 10000",
    "?": "01110 10001 00001 00010 00100 00000 00100",
    " ": "00000 00000 00000 00000 00000 00000 00000",
}
GLYPH = 6  # a glyph's advance in font dots: 5 wide and 1 apart


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(prog="render_views.py")
    parser.add_argument("model")
    parser.add_argument("--out", required=True)
    parser.add_argument("--cell", type=int, default=512)
    parser.add_argument("--anim", default="", help="the action for an animation contact sheet")
    parser.add_argument("--frames", type=int, default=8)
    parser.add_argument("--pose", default="", help="show the views posed at the first frame of this action")
    parser.add_argument("--no-outline", action="store_true", help="no object outline (it is a review aid only)")
    return parser.parse_args(argv)


# --- loading -----------------------------------------------------------------------------------------------------


def load(model: Path) -> None:
    suffix = model.suffix.lower()
    if suffix == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(model))
        for obj in list(bpy.data.objects):
            if obj.type in {"CAMERA", "LIGHT"}:
                bpy.data.objects.remove(obj)
        return
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if suffix in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(model), disable_bone_shape=True)  # no stray bone-shape sphere
    elif suffix == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(model))
    elif suffix == ".obj":
        bpy.ops.wm.obj_import(filepath=str(model))
    else:
        raise SystemExit(f"cannot import {model.name}: use GLB, glTF, FBX, OBJ or .blend")


def visible(kind: str) -> list[bpy.types.Object]:
    return [obj for obj in bpy.context.scene.objects if obj.type == kind and obj.visible_get()]


def world_points() -> np.ndarray:
    """Every vertex of every visible mesh, deformed and in world space, as an (n, 3) array."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    chunks = []
    for obj in visible("MESH"):
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        coords = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
        mesh.vertices.foreach_get("co", coords)
        evaluated.to_mesh_clear()
        coords = coords.reshape(-1, 3)
        matrix = np.array(obj.matrix_world, dtype=np.float64)
        chunks.append(coords @ matrix[:3, :3].T + matrix[:3, 3])
    if not chunks or not sum(len(c) for c in chunks):
        raise SystemExit("the model has no visible mesh vertices")
    return np.concatenate(chunks)


def has_texture(material: bpy.types.Material) -> bool:
    if not material.node_tree:
        return False
    for node in material.node_tree.nodes:
        if node.type == "TEX_IMAGE" and node.image is not None:
            size = tuple(node.image.size)
            if node.image.has_data or (size[0] and size[1]):
                return True
    return False


def materials_used() -> list[bpy.types.Material]:
    found: dict[str, bpy.types.Material] = {}
    for obj in visible("MESH"):
        for slot in obj.material_slots:
            if slot.material is not None:
                found[slot.material.name] = slot.material
    return list(found.values())


def sync_viewport_colours(materials: list[bpy.types.Material]) -> None:
    """Workbench's material colour is the viewport colour, which not every importer sets: copy the Principled BSDF's
    base colour into it when that input is a plain colour."""
    for material in materials:
        if not material.node_tree:
            continue
        for node in material.node_tree.nodes:
            if node.type == "BSDF_PRINCIPLED":
                base = node.inputs["Base Color"]
                if not base.is_linked:
                    material.diffuse_color = tuple(base.default_value)
                break


def stats(model: Path, points: np.ndarray, color_type: str) -> dict:
    triangles = vertices = 0
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for obj in visible("MESH"):
        mesh = obj.evaluated_get(depsgraph).to_mesh()
        mesh.calc_loop_triangles()
        triangles += len(mesh.loop_triangles)
        vertices += len(mesh.vertices)
        obj.evaluated_get(depsgraph).to_mesh_clear()
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    low, high = points.min(axis=0), points.max(axis=0)
    materials = materials_used()
    return {
        "model": str(model),
        "triangles": triangles,
        "vertices": vertices,
        "objects": sum(1 for obj in bpy.context.scene.objects if obj.visible_get()),
        "meshes": len(visible("MESH")),
        "materials": len(materials),
        "textured_materials": sum(1 for m in materials if has_texture(m)),
        "armatures": len(armatures),
        "bones": sum(len(obj.data.bones) for obj in armatures),
        "actions": sorted(action.name for action in bpy.data.actions),
        "bounding_box": {"min": [round(v, 4) + 0.0 for v in low], "max": [round(v, 4) + 0.0 for v in high],
                         "size": [round(v, 4) for v in high - low]},
        "height": round(float(high[2] - low[2]), 4),
        "feet_at_zero": bool(abs(low[2]) <= FEET_TOLERANCE),
        "color_type": color_type,
    }


# --- rendering ---------------------------------------------------------------------------------------------------


def setup_scene(cell: int, color_type: str, outline: bool) -> bpy.types.Object:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = scene.render.resolution_y = cell
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.view_settings.view_transform = "Standard"
    shading = scene.display.shading
    shading.light = "STUDIO"
    shading.studio_light = "Default"
    shading.color_type = color_type
    shading.show_cavity = True
    shading.cavity_type = "WORLD"
    shading.show_object_outline = outline
    shading.object_outline_color = (0.15, 0.15, 0.15)
    camera_data = bpy.data.cameras.new("ReviewCamera")
    camera_data.type = "ORTHO"
    camera = bpy.data.objects.new("ReviewCamera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    return camera


def label_scale(cell: int) -> int:
    """The pixel size of one font dot: 4 at the default 512 cell."""
    return max(2, cell // 128)


def label_band(cell: int) -> int:
    """The strip at the top of a cell that holds the label; the model is framed below it."""
    return 13 * label_scale(cell)


class Framing:
    """One centre and one orthographic scale for every view, from the model's bounding box; the model is centred in
    the part of the cell below the label band."""

    def __init__(self, points: np.ndarray, cell: int) -> None:
        low, high = points.min(axis=0), points.max(axis=0)
        horizontal = math.hypot(*(high[:2] - low[:2]))  # the widest the model can look from any side
        free = (cell - label_band(cell)) / cell
        self.scale = max(float(high[2] - low[2]), horizontal, 1e-3) * MARGIN / free
        center = (low + high) / 2
        center[2] += self.scale * (1 - free) / 2  # the camera looks a little higher, so the model sits lower
        self.center = Vector(center.tolist())
        self.distance = self.scale * 2 + float(np.linalg.norm(high - low))

    def place(self, camera: bpy.types.Object, angle: float) -> None:
        """Angle 0 looks at the front from -Y; positive angles move the camera counter-clockwise seen from above."""
        a = math.radians(angle)
        direction = Vector((math.sin(a), -math.cos(a), 0.0))
        camera.location = self.center + direction * self.distance
        camera.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
        camera.data.ortho_scale = self.scale
        camera.data.clip_start = 0.01
        camera.data.clip_end = self.distance * 2 + self.scale

    def ground_row(self, cell: int) -> int | None:
        """The pixel row (from the top) where z = 0 falls in a cell, or None when it is outside."""
        row = cell / 2 + (float(self.center.z) / self.scale) * cell
        return int(round(row)) if 0 <= row < cell else None


def render_to(path: Path) -> None:
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    if not path.is_file():
        raise RuntimeError(f"Blender rendered no {path}")


def read_png(path: Path) -> np.ndarray:
    """A PNG as an (h, w, 4) float array in 0..1, top row first."""
    image = bpy.data.images.load(str(path))
    width, height = image.size
    pixels = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    bpy.data.images.remove(image)
    return pixels.reshape(height, width, 4)[::-1]


# --- composing ---------------------------------------------------------------------------------------------------


def text_width(text: str, scale: int) -> int:
    return max(len(text) * GLYPH - 1, 0) * scale


def fit(text: str, width: int, scale: int) -> str:
    """text cut to at most width pixels, ending in `..` when it was cut."""
    if text_width(text, scale) <= width:
        return text
    keep = max((width // scale + 1) // GLYPH - 2, 0)
    return text[:keep] + ".." if keep else ""


def draw_text(canvas: np.ndarray, text: str, x: int, y: int, scale: int) -> None:
    """Draws text in the 5 x 7 font (upper case; an unknown character shows as `?`), cut to the canvas width."""
    text = fit(text, canvas.shape[1] - x, scale)
    for char in text.upper():
        rows = FONT.get(char, FONT["?"]).split()
        for r, bits in enumerate(rows):
            for c, bit in enumerate(bits):
                if bit == "1":
                    canvas[y + r * scale : y + (r + 1) * scale, x + c * scale : x + (c + 1) * scale] = TEXT
        x += GLYPH * scale


def compose(images: list[np.ndarray], labels: list[str], cell: int, ground: int | None,
            caption: list[str]) -> np.ndarray:
    """The cells in rows of 4, each with its label at the top left, and up to two caption lines in small type at the
    top right of the first row, in the label band of its last cell (the label band never holds the model)."""
    rows = math.ceil(len(images) / COLUMNS)
    columns = min(COLUMNS, len(images))
    sheet = np.empty((rows * cell, columns * cell, 3), dtype=np.float32)
    sheet[:] = BACKGROUND
    scale = label_scale(cell)
    labels = [label if text_width(label, scale) <= cell - 6 * scale else label.split()[0] for label in labels]
    for index, (image, label) in enumerate(zip(images, labels)):
        top, left = (index // COLUMNS) * cell, (index % COLUMNS) * cell
        tile = sheet[top : top + cell, left : left + cell]
        if ground is not None:
            tile[ground, :] = GROUND
        alpha = image[:, :, 3:4]
        tile[:] = image[:, :, :3] * alpha + tile * (1 - alpha)
        tile[:, 0] = tile[0, :] = BORDER
        draw_text(tile, label, 3 * scale, 3 * scale, scale)
    small = max(1, scale // 2)
    last = (columns - 1) * cell
    free_left = last + 3 * scale + text_width(labels[columns - 1], scale) + 6 * scale
    right = columns * cell - 3 * scale
    for line, text in enumerate(caption[:2]):
        text = fit(text.upper(), right - free_left, small)
        y = 3 * scale + line * 9 * small
        draw_text(sheet[:, : right], text, right - text_width(text, small), y, small)
    return sheet


def write_png(path: Path, rgb: np.ndarray) -> None:
    """An 8-bit RGB PNG from an (h, w, 3) float array, with zlib alone (no colour management on the way out)."""
    data = (np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8)
    height, width = data.shape[:2]
    raw = np.concatenate([np.zeros((height, 1), dtype=np.uint8), data.reshape(height, width * 3)], axis=1)

    def chunk(kind: bytes, body: bytes) -> bytes:
        return len(body).to_bytes(4, "big") + kind + body + zlib.crc32(kind + body).to_bytes(4, "big")

    header = width.to_bytes(4, "big") + height.to_bytes(4, "big") + bytes((8, 2, 0, 0, 0))
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw.tobytes(), 6)) + chunk(b"IEND", b"")
    )


# --- animation ---------------------------------------------------------------------------------------------------


def safe_name(name: str) -> str:
    """An action name as a file or folder name: Mixamo and Meshy FBX clips are named like `Armature|mixamo.com|Layer0`,
    and `|`, `/` or `:` are not allowed in a Windows file name, so every run of other characters becomes `_`."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._") or "action"


def assign_action(name: str) -> tuple[float, float]:
    action = bpy.data.actions.get(name)
    if action is None:
        known = ", ".join(sorted(a.name for a in bpy.data.actions)) or "none"
        raise SystemExit(f"no action named {name!r}; the model has: {known}")
    targets = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"] or [
        obj for obj in bpy.context.scene.objects if obj.animation_data and obj.animation_data.action
    ]
    if not targets:
        raise SystemExit("the model has no armature to play an action on")
    for obj in targets:
        data = obj.animation_data or obj.animation_data_create()
        for track in list(data.nla_tracks):  # NLA strips the importer adds would blend over the chosen action
            track.mute = True
        data.action = action
        slots = getattr(action, "slots", None)
        if slots and hasattr(data, "action_slot") and data.action_slot is None:
            data.action_slot = slots[0]
    start, end = action.frame_range
    return float(start), float(end)


def frames_of(start: float, end: float, count: int) -> list[int]:
    """count whole frames spread evenly from start to end inclusive; fewer when the clip has fewer frames."""
    first, last = round(start), round(end)
    if count <= 1 or last <= first:
        return [first]
    return sorted({round(first + (last - first) * i / (count - 1)) for i in range(count)})


def set_frame(frame: int) -> None:
    bpy.context.scene.frame_set(frame)


# --- main --------------------------------------------------------------------------------------------------------


def main() -> None:
    args = parse_args()
    model, out = Path(args.model), Path(args.out)
    if not model.is_file():
        raise SystemExit(f"no model at {model}")
    if args.cell < 64:
        raise SystemExit("--cell must be at least 64")
    out.mkdir(parents=True, exist_ok=True)
    load(model)
    if args.pose:
        start, _end = assign_action(args.pose)
        bpy.context.scene.frame_set(int(start))
    else:
        bpy.context.scene.frame_set(bpy.context.scene.frame_start)

    color_type = "TEXTURE" if any(has_texture(m) for m in materials_used()) else "MATERIAL"
    sync_viewport_colours(materials_used())
    points = world_points()
    report = stats(model, points, color_type)
    camera = setup_scene(args.cell, color_type, not args.no_outline)

    framing = Framing(points, args.cell)
    views = out / "views"
    views.mkdir(exist_ok=True)
    images, labels = [], []
    for index, (angle, name) in enumerate(VIEWS):
        framing.place(camera, angle)
        path = views / f"{index}_{angle:03d}{'_' + name.lower() if name else ''}.png"
        render_to(path)
        images.append(read_png(path))
        labels.append(f"{angle} {name}".strip())
    sheet = out / "sheet.png"
    caption = [model.name, f"{report['triangles']} TRIS  {report['height']:.2f} M  {color_type}"]
    write_png(sheet, compose(images, labels, args.cell, framing.ground_row(args.cell), caption))
    report["sheet"] = str(sheet)
    report["cell"] = args.cell
    report["views"] = labels
    report["outline"] = not args.no_outline
    report["pose"] = args.pose

    if args.anim:
        start, end = assign_action(args.anim)
        frames = frames_of(start, end, args.frames)
        sampled = []
        for frame in frames:
            set_frame(frame)
            sampled.append(world_points())
        anim_framing = Framing(np.concatenate(sampled), args.cell)
        anim_framing.place(camera, 0)
        frame_dir = out / f"anim_{safe_name(args.anim)}"
        frame_dir.mkdir(exist_ok=True)
        anim_images = []
        for index, frame in enumerate(frames):
            set_frame(frame)
            path = frame_dir / f"{index}_frame_{frame:04d}.png"
            render_to(path)
            anim_images.append(read_png(path))
        anim_sheet = out / f"anim_{safe_name(args.anim)}.png"
        anim_labels = [f"F {frame}" for frame in frames]
        anim_caption = [model.name, f"{args.anim}  F {frames[0]}-{frames[-1]}"]
        write_png(anim_sheet, compose(anim_images, anim_labels, args.cell, anim_framing.ground_row(args.cell),
                                      anim_caption))
        report["anim"] = {"action": args.anim, "frame_range": [start, end], "frames": frames, "sheet": str(anim_sheet)}

    (out / "stats.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"SHEET {sheet}")
    print(f"STATS {out / 'stats.json'}")


if __name__ == "__main__":  # Blender runs a --python script as __main__; props_task_review.py imports it
    main()
