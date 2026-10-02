"""Builds a 1.75 m stand-in humanoid with an armature and exports it as GLB; a test fixture, never committed.

Run through the runner (`tools/run.py probe` builds it), or directly:
    blender -b --factory-startup --python-exit-code 1 --python tools/blender/make_fixture.py -- --out DIR [--textured]

The figure faces -Y (Blender's front, +Z in glTF), stands in an A-pose with its feet at z = 0 and the top of its head at
z = 1.75, and has a red nose so the front reads at a glance. Each body part is a box bound with weight 1 to one bone.
The armature carries one action, "Wave": the right arm swings up and back over 24 frames. With --textured the shirt
gets a generated checker image (packed into the GLB), to exercise texture colours in the review sheet.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

HEIGHT = 1.75

# Bones: name -> (head, tail, parent). The figure's left side is +X.
BONES: dict[str, tuple[tuple[float, float, float], tuple[float, float, float], str | None]] = {
    "hips": ((0.0, 0.0, 0.95), (0.0, 0.0, 1.05), None),
    "spine": ((0.0, 0.0, 1.05), (0.0, 0.0, 1.25), "hips"),
    "chest": ((0.0, 0.0, 1.25), (0.0, 0.0, 1.45), "spine"),
    "neck": ((0.0, 0.0, 1.45), (0.0, 0.0, 1.55), "chest"),
    "head": ((0.0, 0.0, 1.55), (0.0, 0.0, 1.75), "neck"),
}
for side, sx in (("L", 1.0), ("R", -1.0)):
    BONES.update(
        {
            f"upper_arm.{side}": ((0.2 * sx, 0.0, 1.42), (0.36 * sx, 0.0, 1.17), "chest"),
            f"forearm.{side}": ((0.36 * sx, 0.0, 1.17), (0.48 * sx, 0.0, 0.94), f"upper_arm.{side}"),
            f"hand.{side}": ((0.48 * sx, 0.0, 0.94), (0.53 * sx, 0.0, 0.84), f"forearm.{side}"),
            f"thigh.{side}": ((0.1 * sx, 0.0, 0.95), (0.1 * sx, 0.0, 0.5), "hips"),
            f"shin.{side}": ((0.1 * sx, 0.0, 0.5), (0.1 * sx, 0.0, 0.08), f"thigh.{side}"),
            f"foot.{side}": ((0.1 * sx, 0.0, 0.08), (0.1 * sx, -0.16, 0.02), f"shin.{side}"),
        }
    )

MATERIALS = {
    "skin": (0.88, 0.68, 0.55),
    "shirt": (0.2, 0.42, 0.82),
    "pants": (0.25, 0.27, 0.33),
    "shoes": (0.1, 0.1, 0.1),
    "nose": (0.85, 0.15, 0.12),
}


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(prog="make_fixture.py")
    parser.add_argument("--out", required=True, help="the folder the GLB goes to")
    parser.add_argument("--name", default="", help="file name without extension (default humanoid[_textured])")
    parser.add_argument("--textured", action="store_true", help="give the shirt a generated checker texture")
    return parser.parse_args(argv)


def box_between(head: Vector, tail: Vector, width: float, depth: float) -> Matrix:
    """The matrix of a unit cube stretched from head to tail, width along X-ish and depth along Y-ish."""
    direction = tail - head
    rotation = Vector((0.0, 0.0, 1.0)).rotation_difference(direction.normalized()).to_matrix().to_4x4()
    scale = Matrix.Diagonal((width, depth, direction.length, 1.0))
    return Matrix.Translation((head + tail) / 2) @ rotation @ scale


def box_at(center: tuple[float, float, float], size: tuple[float, float, float]) -> Matrix:
    return Matrix.Translation(center) @ Matrix.Diagonal((*size, 1.0))


def parts() -> list[tuple[str, str, Matrix]]:
    """(bone, material, cube matrix) for every body part."""
    v = {name: (Vector(head), Vector(tail)) for name, (head, tail, _) in BONES.items()}
    out = [
        ("hips", "pants", box_at((0.0, 0.0, 0.97), (0.34, 0.2, 0.16))),
        ("spine", "shirt", box_at((0.0, 0.0, 1.15), (0.32, 0.19, 0.2))),
        ("chest", "shirt", box_at((0.0, 0.0, 1.34), (0.4, 0.22, 0.22))),
        ("neck", "skin", box_at((0.0, 0.0, 1.5), (0.1, 0.1, 0.1))),
        ("head", "skin", box_at((0.0, 0.0, 1.65), (0.2, 0.22, 0.2))),
        ("head", "nose", box_at((0.0, -0.12, 1.63), (0.04, 0.05, 0.05))),
    ]
    for side, sx in (("L", 1.0), ("R", -1.0)):
        out += [
            (f"upper_arm.{side}", "shirt", box_between(*v[f"upper_arm.{side}"], 0.1, 0.1)),
            (f"forearm.{side}", "skin", box_between(*v[f"forearm.{side}"], 0.08, 0.08)),
            (f"hand.{side}", "skin", box_between(*v[f"hand.{side}"], 0.07, 0.04)),
            (f"thigh.{side}", "pants", box_between(*v[f"thigh.{side}"], 0.14, 0.15)),
            (f"shin.{side}", "pants", box_between(*v[f"shin.{side}"], 0.11, 0.12)),
            (f"foot.{side}", "shoes", box_at((0.1 * sx, -0.05, 0.04), (0.1, 0.24, 0.08))),
        ]
    return out


def make_material(name: str, color: tuple[float, float, float], image: bpy.types.Image | None) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.diffuse_color = (*color, 1.0)
    tree = material.node_tree
    if tree is None:  # Blender 5 materials always have nodes; older ones need use_nodes.
        material.use_nodes = True
        tree = material.node_tree
    bsdf = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.8
    if image is not None:
        texture = tree.nodes.new("ShaderNodeTexImage")
        texture.image = image
        tree.links.new(texture.outputs["Color"], bsdf.inputs["Base Color"])
    return material


def checker_image(folder: Path) -> bpy.types.Image:
    """A 256 x 256 blue-and-yellow checker, saved as PNG and packed so the GLB carries it."""
    import numpy as np

    size, square = 256, 32
    yy, xx = np.mgrid[0:size, 0:size]
    on = ((xx // square + yy // square) % 2).astype(bool)
    pixels = np.empty((size, size, 4), dtype=np.float32)
    pixels[on] = (0.95, 0.8, 0.1, 1.0)
    pixels[~on] = (0.15, 0.3, 0.85, 1.0)
    image = bpy.data.images.new("shirt_checker", size, size, alpha=False)
    image.pixels.foreach_set(pixels.ravel())
    image.filepath_raw = str(folder / "shirt_checker.png")
    image.file_format = "PNG"
    image.save()
    image.pack()
    return image


def build(textured: bool, folder: Path) -> bpy.types.Object:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 24

    armature_data = bpy.data.armatures.new("Armature")
    armature = bpy.data.objects.new("Armature", armature_data)
    scene.collection.objects.link(armature)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="EDIT")
    for name, (head, tail, parent) in BONES.items():
        bone = armature_data.edit_bones.new(name)
        bone.head, bone.tail = head, tail
        if parent:
            bone.parent = armature_data.edit_bones[parent]
            bone.use_connect = Vector(head) == Vector(BONES[parent][1])
    bpy.ops.object.mode_set(mode="OBJECT")

    image = checker_image(folder) if textured else None
    materials = {name: make_material(name, color, image if name == "shirt" else None) for name, color in MATERIALS.items()}
    order = list(materials)

    mesh = bpy.data.meshes.new("Body")
    bm = bmesh.new()
    bm.loops.layers.uv.new("UVMap")  # create_cube(calc_uvs=True) fills it
    deform = bm.verts.layers.deform.verify()
    groups = list(BONES)
    for bone, material, matrix in parts():
        created = bmesh.ops.create_cube(bm, size=1.0, matrix=matrix, calc_uvs=True)
        verts = created["verts"]
        for vert in verts:
            vert[deform][groups.index(bone)] = 1.0
        faces = {face for vert in verts for face in vert.link_faces}
        for face in faces:
            face.material_index = order.index(material)
    bm.to_mesh(mesh)
    bm.free()
    for material in materials.values():
        mesh.materials.append(material)

    body = bpy.data.objects.new("Body", mesh)
    scene.collection.objects.link(body)
    for name in groups:
        body.vertex_groups.new(name=name)
    body.parent = armature
    body.modifiers.new("Armature", "ARMATURE").object = armature

    add_wave(armature)
    return armature


def add_wave(armature: bpy.types.Object) -> None:
    """The right arm swings out and up (around the figure's front-back axis, so it reads from the front) and back."""
    pose_bone = armature.pose.bones["upper_arm.R"]
    rest = armature.data.bones["upper_arm.R"].matrix_local.to_3x3()
    axis = (rest.inverted() @ Vector((0.0, 1.0, 0.0))).normalized()
    pose_bone.rotation_mode = "QUATERNION"
    for frame, angle in ((1, 0.0), (12, 110.0), (24, 0.0)):
        pose_bone.rotation_quaternion = Quaternion(axis, math.radians(angle))
        pose_bone.keyframe_insert("rotation_quaternion", frame=frame)
    armature.animation_data.action.name = "Wave"
    pose_bone.rotation_quaternion = Quaternion()
    bpy.context.scene.frame_set(1)


def main() -> None:
    args = parse_args()
    folder = Path(args.out)
    folder.mkdir(parents=True, exist_ok=True)
    name = args.name or ("humanoid_textured" if args.textured else "humanoid")
    build(args.textured, folder)
    target = folder / f"{name}.glb"
    bpy.ops.export_scene.gltf(filepath=str(target), export_format="GLB", export_animations=True, export_apply=False)
    if not target.is_file():
        raise RuntimeError(f"the glTF exporter wrote no {target}")
    print(f"FIXTURE {target}")


main()
