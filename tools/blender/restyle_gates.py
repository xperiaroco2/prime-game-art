"""The gates a restyled base body passes before the humans judge its look (art #14), in headless Blender:

    blender -b --factory-startup --python-exit-code 1 --python tools/blender/restyle_gates.py -- SPEC.json

SPEC.json (written by tools/runner/commands/stylize_quaternius.py): {"model", "out", "tasks", "base_model",
"lineup", "lineup_out", "cell"}. Tasks:
- measure: height, lowest point, the soles' centre, the eye bones' height, the head's size, the limb bone
  lengths, triangles, materials; with base_model, the median distance of this model's vertices from base_model's
  surface (a preset that changes nothing shows about 0);
- defects: per hand the connected parts of slices across the arm 1 to 12 cm in from the fingertips
  (five fingers show as five parts), open and non-manifold edges after welding at 0.01 mm, connected parts;
- closeups: closeups/head.png (front, side, three-quarter, back in colour; front and side in clay; front and side
  wireframe) and closeups/hands.png (per hand: top in colour, top wireframe, front and bottom in clay);
- poses: poses.png: fist, point, wave, thumbs up, knee bend, sit and arms down, each as a full figure and a close
  look at the joint or the hand it tests;
- lineup: lineup_out: every model of "lineup" at 40 pixels per metre (a 1.75 m figure is 70 px tall, about what a
  1080p screen shows at 20 m), front row and side row, unlit by any outline; and a copy enlarged 4 times.
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_views as rv  # noqa: E402

CLAY = (0.78, 0.74, 0.68, 1.0)
WIRE = (0.03, 0.03, 0.03, 1.0)
LINEUP_PX_PER_M = 40
LINEUP_BACKGROUND = (0.69, 0.8, 0.88)


# --- loading -------------------------------------------------------------------------------------------------------


def load(path: str) -> None:
    _wires.clear()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path, merge_vertices=True, disable_bone_shape=True)


def meshes() -> list[bpy.types.Object]:
    return [o for o in bpy.context.scene.objects if o.type == "MESH" and o.visible_get() and o not in _wires]


def armature() -> bpy.types.Object | None:
    found = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    return found[0] if found else None


def world_points(objects: list[bpy.types.Object] | None = None) -> np.ndarray:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    depsgraph.update()
    chunks = []
    for obj in objects or meshes():
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        co = np.empty(len(mesh.vertices) * 3)
        mesh.vertices.foreach_get("co", co)
        evaluated.to_mesh_clear()
        matrix = np.array(obj.matrix_world)
        chunks.append(co.reshape(-1, 3) @ matrix[:3, :3].T + matrix[:3, 3])
    return np.vstack(chunks)


def welded_bmesh() -> bmesh.types.BMesh:
    """Every mesh, deformed, in world space, in one bmesh welded at 0.01 mm (a GLB splits vertices at UV seams)."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    for obj in meshes():
        mesh = obj.evaluated_get(depsgraph).to_mesh().copy()
        mesh.transform(obj.matrix_world)
        bm.from_mesh(mesh)
        bpy.data.meshes.remove(mesh)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    bm.verts.ensure_lookup_table()
    return bm


def head_weights(obj: bpy.types.Object, bone: str) -> np.ndarray:
    group = obj.vertex_groups.get(bone)
    weights = np.zeros(len(obj.data.vertices))
    if group is None:
        return weights
    for vertex in obj.data.vertices:
        total = sum(g.weight for g in vertex.groups)
        for g in vertex.groups:
            if g.group == group.index and total > 0:
                weights[vertex.index] = g.weight / total
    return weights


# --- measure -------------------------------------------------------------------------------------------------------


def measure(spec: dict) -> dict:
    points = world_points()
    low, high = points.min(axis=0), points.max(axis=0)
    height = float(high[2] - low[2])
    soles = points[points[:, 2] < low[2] + 0.03 * height]
    rig = armature()
    out = {
        "height": round(height, 4),
        "lowest": round(float(low[2]), 4),
        "soles_centre": [round(float(v), 4) for v in (soles.min(axis=0) + soles.max(axis=0))[:2] / 2],
        "width": round(float(high[0] - low[0]), 4),
        "triangles": sum(len(p.vertices) - 2 for o in meshes() for p in o.data.polygons),
        "vertices": sum(len(o.data.vertices) for o in meshes()),
        "meshes": sorted(o.name for o in meshes()),
        "materials": sorted({m.name for o in meshes() for m in o.data.materials if m}),
        "images": sorted(i.name for i in bpy.data.images if i.size[0] > 0),
    }
    if rig is not None:
        bones = rig.data.bones
        out["bones"] = len(bones)
        eyes = [bones[n].head_local.z for n in ("LeftEye", "RightEye") if n in bones]
        out["eye_height"] = round(float(np.mean(eyes)), 4) if eyes else None
        lengths = {}
        for name in ("Neck", "LeftUpperArm", "LeftLowerArm", "LeftHand", "LeftUpperLeg", "LeftLowerLeg", "LeftFoot",
                     "LeftShoulder"):
            if name in bones and bones[name].children:
                child = min(bones[name].children, key=lambda c: abs(c.head_local.x) if name == "Neck" else 0)
                lengths[name] = round((child.head_local - bones[name].head_local).length / height, 4)
        out["bone_lengths_per_height"] = lengths
        body = meshes()[0]
        weights = head_weights(body, "Head")
        if weights.any():
            co = world_points([body])
            head = co[weights >= 0.5, 2]
            out["head_ratio"] = round(float(head.max() - head.min()) / height, 5)
    if spec.get("base_model") and Path(spec["base_model"]).is_file():
        out["surface_from_base"] = shift_from(points, spec["base_model"])
    return out


def shift_from(points: np.ndarray, other: str) -> dict:
    """How far every vertex of this model lies from the other model's surface (the nearest point on its triangles,
    so two decimations of one shape measure about 0, unlike a nearest-vertex distance, whose floor is about half an
    edge): median, 95th percentile, maximum."""
    load(other)
    reference = welded_bmesh()
    reference.faces.ensure_lookup_table()
    tree = BVHTree.FromBMesh(reference)
    distances = np.array([tree.find_nearest(Vector(p))[3] for p in points])
    reference.free()
    return {"model": other, "median": round(float(np.median(distances)), 4),
            "p95": round(float(np.percentile(distances, 95)), 4), "max": round(float(distances.max()), 4)}


# --- defects -------------------------------------------------------------------------------------------------------


def slice_parts(bm: bmesh.types.BMesh, x: float) -> list[dict]:
    """The connected loops where the plane at this x cuts the mesh."""
    copy = bm.copy()
    cut = bmesh.ops.bisect_plane(copy, geom=copy.verts[:] + copy.edges[:] + copy.faces[:], plane_co=(x, 0, 0),
                                 plane_no=(1, 0, 0), dist=1e-6)
    verts = [g for g in cut["geom_cut"] if isinstance(g, bmesh.types.BMVert)]
    on = set(verts)
    parent = {v: v for v in verts}

    def find(v):
        while parent[v] is not v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    for v in verts:
        for edge in v.link_edges:
            other = edge.other_vert(v)
            if other in on:
                a, b = find(v), find(other)
                if a is not b:
                    parent[a] = b
    groups: dict = {}
    for v in verts:
        groups.setdefault(find(v), []).append(v.co.copy())
    parts = []
    for group in groups.values():
        array = np.array([c[:] for c in group])
        parts.append({"y": round(float(array[:, 1].mean()), 4), "z": round(float(array[:, 2].mean()), 4)})
    copy.free()
    return sorted(parts, key=lambda p: p["y"])


FINGER_JOINTS = {"Thumb": ("Proximal", "Distal"), "Index": ("Proximal", "Intermediate", "Distal"),
                 "Middle": ("Proximal", "Intermediate", "Distal"), "Ring": ("Proximal", "Intermediate", "Distal"),
                 "Little": ("Proximal", "Intermediate", "Distal")}


# The free part of each finger: past the web (which joins the four fingers' first segments in a real hand too).
FREE_JOINTS = {"Thumb": ("Proximal", "Distal"), "Index": ("Intermediate", "Distal"),
               "Middle": ("Intermediate", "Distal"), "Ring": ("Intermediate", "Distal"),
               "Little": ("Intermediate", "Distal")}


def finger_islands() -> dict:
    """Per hand, the connected parts of the skin that the free finger bones move most (every corner of a face
    dominated by a finger's middle or end segment, the thumb's last two): five separate fingers give five parts, each
    one finger; fingers fused by decimation or a webbed paddle merge into one part."""
    body = meshes()[0]
    names = {g.index: g.name for g in body.vertex_groups}
    owner = {}
    for side in ("Left", "Right"):
        for finger, joints in FREE_JOINTS.items():
            for joint in joints:
                owner[f"{side}{finger}{joint}"] = (side, finger)
    dominant = []
    for vertex in body.data.vertices:
        best = max(vertex.groups, key=lambda g: g.weight, default=None)
        dominant.append(owner.get(names.get(best.group, "")) if best is not None else None)
    parent = list(range(len(dominant)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for polygon in body.data.polygons:
        corners = list(polygon.vertices)
        if all(dominant[v] is not None and dominant[v][0] == dominant[corners[0]][0] for v in corners):
            for v in corners[1:]:
                a, b = find(v), find(corners[0])
                if a != b:
                    parent[a] = b
    result = {}
    for side in ("Left", "Right"):
        parts: dict[int, set] = {}
        for v, who in enumerate(dominant):
            if who is not None and who[0] == side:
                parts.setdefault(find(v), set()).add(who[1])
        islands = [sorted(fingers) for fingers in parts.values()]
        result[side.lower()] = {"islands": len(islands), "fingers_per_island": sorted(islands),
                                "five_separate": len(islands) == 5 and all(len(i) == 1 for i in islands)}
    return result


def defects() -> dict:
    fingers = finger_islands()
    bm = welded_bmesh()
    co = np.array([v.co[:] for v in bm.verts])
    low, high = co.min(axis=0), co.max(axis=0)
    hands = {}
    for side, tip in (("left", float(high[0])), ("right", float(low[0]))):
        sign = 1.0 if side == "left" else -1.0
        slices = []
        for cm in range(1, 13):
            parts = slice_parts(bm, tip - sign * cm / 100)
            slices.append({"cm_from_tip": cm, "parts": len(parts)})
        hands[side] = {"slices": slices, "most_parts": max(s["parts"] for s in slices), **fingers[side]}
    open_edges = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    non_manifold = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    wire = sum(1 for e in bm.edges if not e.link_faces)
    # connected parts
    parent = list(range(len(bm.verts)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for e in bm.edges:
        a, b = find(e.verts[0].index), find(e.verts[1].index)
        if a != b:
            parent[a] = b
    parts = len({find(i) for i in range(len(bm.verts))})
    bm.free()
    return {"hands": hands, "open_edges": open_edges, "non_manifold_edges": non_manifold, "wire_edges": wire,
            "connected_parts": parts}


# --- rendering -----------------------------------------------------------------------------------------------------


def setup_scene(size: int, outline: bool = True) -> bpy.types.Object:
    """Workbench on a transparent film (the background is composed in numpy, like render_views)."""
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.view_settings.view_transform = "Standard"
    scene.display.render_aa = "16"
    shading = scene.display.shading
    shading.light = "STUDIO"
    shading.show_specular_highlight = False
    shading.show_cavity = outline
    shading.cavity_type = "WORLD"
    shading.show_object_outline = outline
    shading.object_outline_color = (0.1, 0.1, 0.1)
    camera = bpy.data.objects.get("GateCamera")
    if camera is None:
        data = bpy.data.cameras.new("GateCamera")
        data.type = "ORTHO"
        camera = bpy.data.objects.new("GateCamera", data)
        scene.collection.objects.link(camera)
    scene.camera = camera
    return camera


def colour_mode() -> str:
    textured = any(n.type == "TEX_IMAGE" and n.image and n.image.size[0] > 0
                   for o in meshes() for m in o.data.materials if m and m.node_tree for n in m.node_tree.nodes)
    for obj in meshes():
        for material in obj.data.materials:
            if material and material.node_tree:
                bsdf = next((n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
                if bsdf is not None and not bsdf.inputs["Base Color"].links:
                    material.diffuse_color = bsdf.inputs["Base Color"].default_value
                material.roughness = 1.0
    return "TEXTURE" if textured else "MATERIAL"


def look(camera: bpy.types.Object, centre, direction, scale: float) -> None:
    d = Vector(direction).normalized()
    up = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((0, 1, 0))
    z = -d
    x = up.cross(z).normalized()
    y = z.cross(x)
    camera.matrix_world = Matrix.Translation(Vector(centre) - d * 10.0) @ Matrix((x, y, z)).transposed().to_4x4()
    camera.data.ortho_scale = scale
    camera.data.clip_start = 0.01
    camera.data.clip_end = 40.0


_wires: list[bpy.types.Object] = []


def wire_copies(on: bool) -> None:
    global _wires
    if on and not _wires:
        material = bpy.data.materials.new("GateWire")
        material.diffuse_color = WIRE
        for obj in meshes():
            copy = obj.copy()
            copy.data = obj.data.copy()
            bpy.context.scene.collection.objects.link(copy)
            copy.data.materials.clear()
            copy.data.materials.append(material)
            modifier = copy.modifiers.new("Wire", "WIREFRAME")
            modifier.thickness = 0.0015
            modifier.use_replace = True
            modifier.use_even_offset = True
            # the wireframe goes after the armature, so it follows a pose
            _wires.append(copy)
    for copy in _wires:
        copy.hide_render = not on


def shot(path: Path, background=rv.BACKGROUND) -> np.ndarray:
    rv.render_to(path)
    rgba = rv.read_png(path)
    alpha = rgba[..., 3:4]
    return rgba[..., :3] * alpha + np.array(background) * (1.0 - alpha)


def render_tile(path: Path, camera, centre, direction, scale: float, mode: str, colour: str) -> np.ndarray:
    shading = bpy.context.scene.display.shading
    look(camera, centre, direction, scale)
    wire_copies(mode == "wire")
    if mode == "colour":
        shading.color_type = colour
    else:
        shading.color_type = "OBJECT"
        for obj in meshes():
            obj.color = CLAY
        for obj in _wires:
            obj.color = WIRE
    return shot(path)


def label(tile: np.ndarray, text: str) -> np.ndarray:
    tile = tile.copy()
    scale = max(2, tile.shape[0] // 160)
    rv.draw_text(tile, text, 2 * scale, 2 * scale, scale)
    return tile


def grid(tiles: list[np.ndarray], columns: int) -> np.ndarray:
    size = tiles[0].shape[0]
    rows = math.ceil(len(tiles) / columns)
    sheet = np.ones((rows * size, columns * size, 3), dtype=np.float32) * np.array(rv.BORDER)
    for i, tile in enumerate(tiles):
        r, c = divmod(i, columns)
        sheet[r * size + 1 : (r + 1) * size - 1, c * size + 1 : (c + 1) * size - 1] = tile[1:-1, 1:-1]
    return sheet


def closeups(out: Path, cell: int) -> dict:
    camera = setup_scene(cell)
    colour = colour_mode()
    folder = out / "closeups"
    tiles_dir = folder / "tiles"
    tiles_dir.mkdir(parents=True, exist_ok=True)
    points = world_points()
    low, high = points.min(axis=0), points.max(axis=0)
    height = float(high[2] - low[2])
    head = points[points[:, 2] > high[2] - 0.17 * height]
    centre = (head.min(axis=0) + head.max(axis=0)) / 2
    scale = float(max(head.max(axis=0) - head.min(axis=0))) * 1.15
    views = [("FRONT", (0, 1, 0), "colour"), ("LEFT", (-1, 0, 0), "colour"), ("3/4", (-1, 1, 0), "colour"),
             ("BACK", (0, -1, 0), "colour"), ("FRONT CLAY", (0, 1, 0), "clay"), ("LEFT CLAY", (-1, 0, 0), "clay"),
             ("FRONT WIRE", (0, 1, 0), "wire"), ("LEFT WIRE", (-1, 0, 0), "wire")]
    tiles = [label(render_tile(tiles_dir / f"head_{i}.png", camera, centre, d, scale, mode, colour), name)
             for i, (name, d, mode) in enumerate(views)]
    rv.write_png(folder / "head.png", grid(tiles, 4))
    tiles = []
    hand_len = 0.16 * height
    for side, sign in (("LEFT", 1.0), ("RIGHT", -1.0)):
        tip = float(high[0]) if sign > 0 else float(low[0])
        hand = points[sign * (points[:, 0] - tip) > -hand_len]
        hand = hand[hand[:, 2] > low[2] + 0.5 * height]
        c = (hand.min(axis=0) + hand.max(axis=0)) / 2
        extent = hand.max(axis=0) - hand.min(axis=0)
        top, front = float(max(extent[0], extent[1])) * 1.15, float(max(extent[0], extent[2])) * 1.6
        views = ((f"{side} TOP", (0, 0, -1), top, "colour"), (f"{side} TOP WIRE", (0, 0, -1), top, "wire"),
                 (f"{side} FRONT", (0, 1, 0), front, "clay"), (f"{side} PALM", (0, 0, 1), top, "clay"))
        for name, d, s, mode in views:
            tiles.append(label(render_tile(tiles_dir / f"hand_{len(tiles)}.png", camera, c, d, s, mode, colour), name))
    rv.write_png(folder / "hands.png", grid(tiles, 4))
    wire_copies(False)
    return {"head": str(folder / "head.png"), "hands": str(folder / "hands.png")}


# --- poses ---------------------------------------------------------------------------------------------------------


def pose_bone(name: str) -> bpy.types.PoseBone:
    return armature().pose.bones[name]


def direction(pb: bpy.types.PoseBone) -> Vector:
    return (pb.tail - pb.head).normalized()


def rotate(pb: bpy.types.PoseBone, axis, degrees: float) -> None:
    """Turns the bone (and so its children) about a world axis through its head."""
    matrix = pb.matrix.copy()
    head = matrix.translation.copy()
    turn = Matrix.Rotation(math.radians(degrees), 4, Vector(axis).normalized())
    pb.matrix = Matrix.Translation(head) @ turn @ Matrix.Translation(-head) @ matrix
    bpy.context.view_layer.update()


def swing(name: str, target, degrees: float | None = None) -> None:
    """Turns the bone's direction towards target (by degrees, or all the way)."""
    pb = pose_bone(name)
    d, t = direction(pb), Vector(target).normalized()
    axis = d.cross(t)
    if axis.length < 1e-6:
        return
    rotate(pb, axis, math.degrees(d.angle(t)) if degrees is None else degrees)


def twist(name: str, degrees: float) -> None:
    pb = pose_bone(name)
    rotate(pb, direction(pb), degrees)


def palm(side: str) -> Vector:
    """The palm's normal now: the rest pose has the palms down (-Z)."""
    hand = pose_bone(f"{side}Hand")
    turn = hand.matrix.to_3x3() @ hand.bone.matrix_local.to_3x3().inverted()
    return (turn @ Vector((0, 0, -1))).normalized()


def curl(side: str, finger: str, angles: tuple[float, float, float]) -> None:
    joints = (("Metacarpal", "Proximal", "Distal") if finger == "Thumb" else ("Proximal", "Intermediate", "Distal"))
    names = [f"{side}{finger}{j}" for j in joints]
    axis = direction(pose_bone(names[0])).cross(palm(side))
    if axis.length < 1e-6:
        return
    for name, angle in zip(names, angles):
        rotate(pose_bone(name), axis, angle)


def fist(side: str, thumb: bool = True) -> None:
    for finger in ("Index", "Middle", "Ring", "Little"):
        curl(side, finger, (80, 95, 60))
    if thumb:
        fold_thumb(side)


def fold_thumb(side: str) -> None:
    hand = pose_bone(f"{side}Hand")
    along = direction(hand)
    rotate(pose_bone(f"{side}ThumbMetacarpal"), along, 35 if side == "Left" else -35)
    curl(side, "Thumb", (10, 45, 40))


def rest_pose() -> None:
    for pb in armature().pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


def arms_down(side: str, degrees: float = 75) -> None:
    swing(f"{side}UpperArm", (0, 0, -1), degrees)


POSES = ["FIST", "POINT", "WAVE", "THUMBS UP", "KNEE BEND", "SIT", "ARMS DOWN"]


def hand_centre(name: str) -> Vector:
    """The middle of a posed hand: the mean of its bones' heads and tails."""
    side = name.replace("Hand", "")
    bones = [pose_bone(name)] + [pose_bone(f"{side}{f}{j}") for f, joints in FINGER_JOINTS.items() for j in joints]
    points = [b.head for b in bones] + [b.tail for b in bones]
    return sum(points, Vector()) / len(points)


def apply_pose(name: str) -> tuple[str, str, float]:
    """Poses the rig; returns the bone whose joint (its head; a hand's middle) the close look centres on, the view
    direction's name and the close look's width in metres."""
    rest_pose()
    if name == "FIST":
        fist("Left")
        fist("Right")
        return "LeftHand", "below", 0.2
    if name == "POINT":
        swing("RightUpperArm", (0, -1, 0), 80)
        for finger in ("Middle", "Ring", "Little"):
            curl("Right", finger, (80, 95, 60))
        fold_thumb("Right")
        arms_down("Left")
        return "RightHand", "side", 0.22
    if name == "WAVE":
        arms_down("Left")
        twist("RightUpperArm", 90)  # the elbow's crease faces up, so the forearm bends up
        swing("RightLowerArm", (0, 0, 1), 85)
        for finger, spread in (("Index", 6), ("Little", -8), ("Ring", -3)):
            rotate(pose_bone(f"Right{finger}Proximal"), palm("Right"), spread)
        return "RightLowerArm", "front", 0.3
    if name == "THUMBS UP":
        arms_down("Right")
        swing("LeftUpperArm", (0, -1, 0), 75)
        swing("LeftLowerArm", (0, -1, 0), 30)
        twist("LeftLowerArm", -80)  # the thumb's side turns up
        fist("Left", thumb=False)
        thumb = pose_bone("LeftThumbProximal")
        swing("LeftThumbMetacarpal", (0, 0, 1), 25)
        swing("LeftThumbProximal", (0, 0, 1))
        swing("LeftThumbDistal", (0, 0, 1))
        del thumb
        return "LeftHand", "side", 0.2
    if name == "KNEE BEND":
        arms_down("Left")
        arms_down("Right")
        swing("LeftUpperLeg", (0, -1, 0), 75)
        swing("LeftLowerLeg", (0, 1, 0), 100)
        return "LeftLowerLeg", "side", 0.4
    if name == "SIT":
        arms_down("Left", 70)
        arms_down("Right", 70)
        for side in ("Left", "Right"):
            swing(f"{side}UpperLeg", (0, -1, 0), 88)
            swing(f"{side}LowerLeg", (0, 0, -1))
        swing("Spine", (0, -1, 0), 4)
        return "LeftUpperLeg", "side", 0.55
    if name == "ARMS DOWN":
        arms_down("Left", 80)
        arms_down("Right", 80)
        return "LeftUpperArm", "front", 0.35
    raise ValueError(name)


VIEW = {"front": (0, 1, 0), "side": (-1, 0, 0), "below": (0, 0.6, 0.8), "three": (-0.6, 1, 0)}


def poses(out: Path, cell: int) -> dict:
    camera = setup_scene(cell)
    colour = colour_mode()
    folder = out / "poses"
    folder.mkdir(parents=True, exist_ok=True)
    full, close = [], []
    for i, name in enumerate(POSES):
        focus, view, size = apply_pose(name)
        points = world_points()
        low, high = points.min(axis=0), points.max(axis=0)
        centre = (low + high) / 2
        span = float(max(high[2] - low[2], math.hypot(*(high[:2] - low[:2])))) * 1.12
        full.append(label(render_tile(folder / f"{i}_full.png", camera, centre, (-0.55, 1, 0), span, "colour",
                                      colour), name))
        pb = pose_bone(focus)
        where = pb.head if "Hand" not in focus else hand_centre(focus)
        close.append(label(render_tile(folder / f"{i}_close.png", camera, where, VIEW[view], size, "clay", colour),
                           name + " CLOSE"))
    rest_pose()
    sheet = grid(full + close, len(POSES))
    rv.write_png(out / "poses.png", sheet)
    return {"poses": POSES, "sheet": str(out / "poses.png")}


# --- lineup --------------------------------------------------------------------------------------------------------


def lineup(entries: list[dict], out: Path) -> dict:
    """Each model alone, at one pixel scale, front row and side row; composed side by side with labels."""
    columns, found = [], []
    tmp = out.parent / (out.stem + "_tiles")
    tmp.mkdir(parents=True, exist_ok=True)
    height_px = int(2.0 * LINEUP_PX_PER_M) + 8
    for index, entry in enumerate(entries):
        if not Path(entry["path"]).is_file():
            continue
        load(entry["path"])
        points = world_points()
        low, high = points.min(axis=0), points.max(axis=0)
        width_m = max(float(high[0] - low[0]), float(high[1] - low[1])) + 0.2
        width_px = max(int(math.ceil(width_m * LINEUP_PX_PER_M)), 24)
        camera = setup_scene(height_px, outline=False)
        scene = bpy.context.scene
        scene.render.resolution_x, scene.render.resolution_y = width_px, height_px
        colour = colour_mode()
        bpy.context.scene.display.shading.color_type = colour
        tiles = []
        for view, d in (("front", (0, 1, 0)), ("side", (-1, 0, 0))):
            scale = max(width_px, height_px) / LINEUP_PX_PER_M
            centre = ((low[0] + high[0]) / 2 if view == "front" else 0.0,
                      (low[1] + high[1]) / 2 if view == "side" else 0.0, height_px / LINEUP_PX_PER_M / 2 - 0.1)
            look(camera, centre, d, scale)
            tiles.append(shot(tmp / f"{index}_{view}.png", LINEUP_BACKGROUND))
        columns.append((entry["label"], tiles))
        found.append({"label": entry["label"], "path": entry["path"],
                      "height_px": round(float(high[2] - low[2]) * LINEUP_PX_PER_M, 1)})
    gap = 6
    width = sum(t[0].shape[1] for _, t in columns) + gap * (len(columns) + 1)
    sheet = np.ones((2 * height_px + 3 * gap, width, 3), dtype=np.float32) * np.array(LINEUP_BACKGROUND)
    x = gap
    for _, (front, side) in columns:
        w = front.shape[1]
        sheet[gap : gap + height_px, x : x + w] = front
        sheet[2 * gap + height_px : 2 * gap + 2 * height_px, x : x + w] = side
        x += w + gap
    rv.write_png(out, sheet)
    big = np.repeat(np.repeat(sheet, 4, axis=0), 4, axis=1)
    band = 40
    labelled = np.ones((big.shape[0] + band, big.shape[1], 3), dtype=np.float32) * np.array(rv.BACKGROUND)
    labelled[band:] = big
    x = gap * 4
    for name, (front, _) in columns:
        rv.draw_text(labelled, name, x, 10, 3)
        x += (front.shape[1] + gap) * 4
    x4 = out.with_name(out.stem + "_x4.png")
    rv.write_png(x4, labelled)
    return {"lineup": str(out), "lineup_x4": str(x4), "px_per_m": LINEUP_PX_PER_M, "models": found}


# --- main ----------------------------------------------------------------------------------------------------------


def main() -> None:
    spec = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
    out = Path(spec["out"])
    out.mkdir(parents=True, exist_ok=True)
    tasks = spec["tasks"]
    result: dict = {}
    if "lineup" in tasks:
        result["lineup"] = lineup(spec["lineup"], Path(spec["lineup_out"]))
    model_tasks = [t for t in tasks if t != "lineup"]
    for task in model_tasks:
        load(spec["model"])
        if task == "measure":
            result["measure"] = measure(spec)
        elif task == "defects":
            result["defects"] = defects()
        elif task == "closeups":
            result["closeups"] = closeups(out, spec.get("cell", 512))
        elif task == "poses":
            result["poses"] = poses(out, spec.get("cell", 512))
        else:
            raise SystemExit(f"unknown task {task}")
    Path(spec["result"]).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"GATES {', '.join(tasks)}")


main()
