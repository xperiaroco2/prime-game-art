"""Builds a contract fixture in headless Blender: an armature with every bone of contract/humanoid.json in Godot's
reference T-pose, and a box mesh with one box per bone, weighted fully to that bone, 1.75 m tall, feet at 0, front
+Z in glTF. Tests use it to exercise `check` and `rename-bones` without any real asset.

    blender -b --factory-startup --python make_contract_fixture.py -- <spec.json>

spec.json: {"profile": ".../humanoid.json", "out": ".../fixture.glb|.blend",
            "names": {profile name: name in the fixture} (optional, to fake a vendor rig),
            "extra_leaves": {bone name: profile parent} (optional end bones, unweighted unless listed below),
            "weighted_leaves": [bone name, ...] (optional: these end bones take the tail end of their parent's box),
            "connected": true (optional: a bone whose head is at its parent's tail is connected to it),
            "omit": [profile name, ...] (optional: leave these bones out, as Mixamo has no Root and no Jaw),
            "defects": [...] (optional; see DEFECTS)}
"""

from __future__ import annotations

import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import contract_io  # noqa: E402

HEIGHT_M = 1.75
HEAD_TOP_ABOVE_HEAD_BONE = 0.30  # in profile units, before scaling
DEFECTS = {
    "extra_bone": "a Socket_HandR bone under RightHand",
    "missing_bone": "no LeftLittleDistal bone (and no box for it)",
    "five_weights": "one Hips vertex with five influences",
    "unweighted_vertex": "one Spine vertex without weights",
    "weighted_root": "one Hips vertex weighted to Root",
    "ngon": "a separate pentagon",
    "non_manifold": "a fin face on an edge of the Hips box (three faces on one edge)",
    "loose_vertex": "a vertex without edges",
    "unapplied_scale": "the mesh object scaled by 1.02",
    "too_tall": "2.0 m instead of 1.75 m",
    "backwards": "turned 180 degrees: the front at -Z in glTF",
    "no_uv": "no UV map",
}


def half_width(name: str) -> float:
    if any(f in name for f in ("Thumb", "Index", "Middle", "Ring", "Little")):
        return 0.008
    if name in ("Hips", "Spine", "Chest", "UpperChest"):
        return 0.12
    if name in ("LeftEye", "RightEye", "Jaw"):
        return 0.015
    if name in ("Neck",):
        return 0.04
    if name.endswith("Hand"):
        return 0.03
    return 0.045


def godot_matrix(pose: dict) -> Matrix:
    m = Matrix.Identity(4)
    for col, key in enumerate(("basis_x", "basis_y", "basis_z")):
        for row in range(3):
            m[row][col] = pose[key][row]
    for row in range(3):
        m[row][3] = pose["origin"][row]
    return m


def global_heads(profile: dict) -> tuple[dict[str, Vector], dict[str, Matrix]]:
    """Each bone's head in Godot's profile space, and its global transform."""
    globals_: dict[str, Matrix] = {}
    for bone in profile["bones"]:  # parents come before children in the profile
        local = godot_matrix(bone["reference_pose"])
        parent = bone["parent"]
        globals_[bone["name"]] = globals_[parent] @ local if parent else local
    return {name: m.to_translation() for name, m in globals_.items()}, globals_


def tails(profile: dict, heads: dict[str, Vector], mats: dict[str, Matrix]) -> dict[str, Vector]:
    children: dict[str, list[str]] = {}
    for bone in profile["bones"]:
        children.setdefault(bone["parent"], []).append(bone["name"])
    result: dict[str, Vector] = {}
    for bone in profile["bones"]:
        name = bone["name"]
        kids = children.get(name, [])
        if bone["tail_direction"] == "specific_child" and bone["tail"]:
            tail = heads[bone["tail"]].copy()
        elif kids and bone["tail_direction"] != "end":
            tail = sum((heads[k] for k in kids), Vector()) / len(kids)
        else:
            parent = bone["parent"]
            length = max((heads[name] - heads[parent]).length * 0.6, 0.02) if parent else 0.1
            axis = mats[name].to_3x3() @ Vector((0, 1, 0))
            tail = heads[name] + axis.normalized() * length
        if (tail - heads[name]).length < 1e-4:
            tail = heads[name] + Vector((0, 0.05, 0))
        result[name] = tail
    if "Head" in result:
        result["Head"] = heads["Head"] + Vector((0, HEAD_TOP_ABOVE_HEAD_BONE, 0))
    return result


def to_blender(v: Vector) -> Vector:
    return Vector((v.x, -v.z, v.y))  # Godot/glTF (x, y, z) -> Blender (x, -z, y)


def box(bm: bmesh.types.BMesh, head: Vector, tail: Vector, half: float) -> list:
    axis = (tail - head).normalized()
    gap = min(0.002, (tail - head).length * 0.1)  # boxes of neighbouring bones never share a vertex
    head, tail = head + axis * gap, tail - axis * gap
    helper = Vector((0, 0, 1)) if abs(axis.z) < 0.9 else Vector((1, 0, 0))
    u = axis.cross(helper).normalized() * half
    w = axis.cross(u).normalized() * half
    corners = []
    for end in (head, tail):
        for su, sw in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            corners.append(bm.verts.new(end + u * su + w * sw))
    a, b = corners[:4], corners[4:]
    faces = [
        (a[3], a[2], a[1], a[0]),
        (b[0], b[1], b[2], b[3]),
        (a[0], a[1], b[1], b[0]),
        (a[1], a[2], b[2], b[1]),
        (a[2], a[3], b[3], b[2]),
        (a[3], a[0], b[0], b[3]),
    ]
    for f in faces:
        bm.faces.new(f)
    return corners


def main() -> None:
    spec = contract_io.read_json(contract_io.script_args()[0])
    profile = contract_io.read_json(spec["profile"])
    defects = set(spec.get("defects", []))
    unknown = defects - set(DEFECTS)
    if unknown:
        raise SystemExit(f"unknown defects {sorted(unknown)}; known: {sorted(DEFECTS)}")
    names = {b["name"]: spec.get("names", {}).get(b["name"], b["name"]) for b in profile["bones"]}
    skip = {"LeftLittleDistal"} if "missing_bone" in defects else set()
    skip |= set(spec.get("omit", []))

    heads_g, mats = global_heads(profile)
    tails_g = tails(profile, heads_g, mats)
    heads = {n: to_blender(v) for n, v in heads_g.items()}
    tails_b = {n: to_blender(v) for n, v in tails_g.items()}

    # Boxes in Blender space, then shift the feet to z = 0 and scale to the height.
    contract_io.empty_scene()
    bm = bmesh.new()
    owner: dict[int, str] = {}
    for bone in profile["bones"]:
        name = bone["name"]
        if name == "Root" or name in skip:
            continue
        start = len(bm.verts)
        box(bm, heads[name], tails_b[name], half_width(name))
        for i in range(start, len(bm.verts)):
            owner[i] = name
    bm.verts.ensure_lookup_table()
    low = min(v.co.z for v in bm.verts)
    high = max(v.co.z for v in bm.verts)
    height = 2.0 if "too_tall" in defects else HEIGHT_M
    scale = height / (high - low)
    fix = Matrix.Scale(scale, 4) @ Matrix.Translation((0, 0, -low))
    if "backwards" in defects:
        fix = Matrix.Rotation(math.pi, 4, "Z") @ fix
    bmesh.ops.transform(bm, matrix=fix, verts=bm.verts)
    heads = {n: fix @ v for n, v in heads.items()}
    heads["Root"].z = 0.0  # Root on the ground between the feet
    tails_b = {n: fix @ v for n, v in tails_b.items()}

    extra_verts: list = []
    if "ngon" in defects:
        angles = [k * 2 * math.pi / 5 for k in range(5)]
        ring = [bm.verts.new((0.6 + 0.05 * math.cos(a), 0.0, 0.5 + 0.05 * math.sin(a))) for a in angles]
        bm.faces.new(ring)
        extra_verts += ring
    if "non_manifold" in defects:
        hips_verts = [v for i, v in enumerate(bm.verts) if owner.get(i) == "Hips"]
        e0, e1 = hips_verts[0], hips_verts[1]
        tip = bm.verts.new(e0.co + Vector((0, 0.2, 0)))
        tip2 = bm.verts.new(e1.co + Vector((0, 0.2, 0)))
        bm.faces.new((e0, e1, tip2, tip))
        owner[len(bm.verts) - 2] = "Hips"
        owner[len(bm.verts) - 1] = "Hips"
    if "loose_vertex" in defects:
        extra_verts.append(bm.verts.new((0.0, 0.5, 0.2)))

    mesh = bpy.data.meshes.new("FixtureBody")
    if "no_uv" not in defects:
        uv = bm.loops.layers.uv.new("UVMap")
        corners = ((0, 0), (1, 0), (1, 1), (0, 1))
        for face in bm.faces:
            for k, loop in enumerate(face.loops):
                loop[uv].uv = corners[k % 4]
    bm.to_mesh(mesh)
    bm.free()
    material = bpy.data.materials.new("FixtureMaterial")
    mesh.materials.append(material)
    body = bpy.data.objects.new("FixtureBody", mesh)
    bpy.context.scene.collection.objects.link(body)

    # The armature, in edit mode.
    arm_data = bpy.data.armatures.new("FixtureRig")
    rig = bpy.data.objects.new("FixtureRig", arm_data)
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    edit = {}
    for bone in profile["bones"]:
        name = bone["name"]
        if name in skip:
            continue
        eb = arm_data.edit_bones.new(names[name])
        eb.head = heads[name]
        eb.tail = tails_b[name]
        eb.use_deform = name != "Root"
        if bone["parent"] in edit:  # an omitted parent leaves the bone at the top
            eb.parent = edit[bone["parent"]]
            if spec.get("connected") and (eb.head - tails_b[bone["parent"]]).length < 1e-5:
                eb.use_connect = True
        edit[name] = eb
    if "extra_bone" in defects:
        eb = arm_data.edit_bones.new("Socket_HandR")
        eb.head = heads["RightHand"]
        eb.tail = heads["RightHand"] + Vector((0, 0, 0.05))
        eb.parent = edit["RightHand"]
    weighted_leaves = set(spec.get("weighted_leaves", []))
    for leaf, parent in spec.get("extra_leaves", {}).items():  # end bones, as vendor rigs have
        eb = arm_data.edit_bones.new(leaf)
        eb.head = tails_b[parent]
        eb.tail = tails_b[parent] + (tails_b[parent] - heads[parent]).normalized() * 0.03
        eb.parent = edit[parent]
        eb.use_deform = leaf in weighted_leaves
    bpy.ops.object.mode_set(mode="OBJECT")

    # Skin: one group per bone, each box fully weighted to its bone.
    groups = {name: body.vertex_groups.new(name=names[name]) for name in names if name not in skip}
    by_bone: dict[str, list[int]] = {}
    for index, name in owner.items():
        by_bone.setdefault(name, []).append(index)
    for name, indices in by_bone.items():
        groups[name].add(indices, 1.0, "REPLACE")
    for leaf, parent in spec.get("extra_leaves", {}).items():
        if leaf in weighted_leaves:  # the four corners at the tail end of the parent's box
            tip = by_bone[parent][-4:]
            groups[parent].remove(tip)
            body.vertex_groups.new(name=leaf).add(tip, 1.0, "REPLACE")
    if "five_weights" in defects:
        v = by_bone["Hips"][0]
        groups["Hips"].add([v], 0.6, "REPLACE")
        for other in ("Spine", "Chest", "UpperChest", "LeftUpperLeg"):
            groups[other].add([v], 0.1, "REPLACE")
    if "unweighted_vertex" in defects:
        groups["Spine"].remove([by_bone["Spine"][0]])
    if "weighted_root" in defects:
        v = by_bone["Hips"][1]
        groups["Hips"].add([v], 0.5, "REPLACE")
        groups["Root"].add([v], 0.5, "REPLACE")
    body.parent = rig
    modifier = body.modifiers.new("Armature", "ARMATURE")
    modifier.object = rig
    if "unapplied_scale" in defects:
        body.scale = (1.02, 1.02, 1.02)

    contract_io.save_model(spec["out"])
    print(f"make_contract_fixture: wrote {spec['out']} with defects {sorted(defects)}")


if __name__ == "__main__":
    main()
