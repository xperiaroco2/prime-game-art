"""Toe bones: a Toe.L and a Toe.R at the ball of each shoe, so that any clip can bend the shoe at push-off (art #25).

The Ultimate Modular armature has no toe bone: each shoe is weighted to its foot alone and tips onto its toe as one
rigid piece when a clip rolls over the toes. add_toe_bones() gives an armature in its rest pose two more bones, each a
child of its foot (Foot.L, Foot.R), its head at the ball of that shoe and its tail at the shoe's tip, with the foot's
axes (X to the character's left, the bone pointing forward), and splits every part's foot weights over the ball with a
smooth blend: behind the ball the foot keeps its weight, in front of it the toe takes it, and across the blend zone the
weight passes from one to the other (a smoothstep), the sum unchanged.

With the toe at rest relative to its foot a vertex moves exactly as before (weights split between two bones that move
together), so every pack action plays as it did: none of them keys a toe. The ball sits at BALL_FRACTION of the shoe's
length from its back, measured along the foot's forward axis on the shoe's vertices weighted to that foot.
"""

from __future__ import annotations

import bpy
from mathutils import Vector

from .util import update

SIDES = ("L", "R")
BALL_FRACTION = 0.68  # the ball of the foot: this fraction of the shoe's length from its back (the toe box ends there)
BLEND_M = 0.025  # half-width (m) of the weight blend across the ball
SLICE_M = 0.01  # half-width (m) of the slice whose vertices give the ball's side position and the sole's height
SOLE_LIFT_M = 0.005  # the bend axis's height above the sole at the ball


def toe_name(side: str) -> str:
    return f"Toe.{side}"


def _weight(v, index: int) -> float:
    return next((g.weight for g in v.groups if g.group == index), 0.0)


def _smoothstep(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * (3.0 - 2.0 * x)


def _geometry(arm, shoes, side: str) -> dict:
    """The foot pivot, forward axis and the ball and tip of one shoe in world space (the rig in its rest pose)."""
    bone = arm.data.bones[f"Foot.{side}"]
    W = arm.matrix_world
    pivot = W @ bone.head_local
    fwd = (W @ bone.tail_local - pivot)
    fwd.z = 0.0  # along the floor: the foot bone points forward and nearly level
    fwd.normalize()
    group = shoes.vertex_groups.get(bone.name)
    if group is None:
        raise RuntimeError(f"{shoes.name}: no vertex group {bone.name}; cannot place {toe_name(side)}")
    pts = [shoes.matrix_world @ v.co for v in shoes.data.vertices if _weight(v, group.index) > 0.01]
    if len(pts) < 8:
        raise RuntimeError(f"{shoes.name}: {len(pts)} vertices weighted to {bone.name}; cannot place {toe_name(side)}")
    d = [(p - pivot).dot(fwd) for p in pts]
    back, tip = min(d), max(d)
    ball = back + BALL_FRACTION * (tip - back)
    near = [p for p, k in zip(pts, d) if abs(k - ball) < SLICE_M] or pts
    side_off = sum(p.x for p in near) / len(near) - pivot.x  # the shoe's middle at the ball, across the foot
    across = Vector((side_off, 0.0, 0.0))
    head = pivot + fwd * ball + across
    tail = pivot + fwd * tip + across
    head.z = tail.z = min(p.z for p in near) + SOLE_LIFT_M  # the bend axis just above the sole, as a shoe bends
    return {"pivot": pivot, "fwd": fwd, "back": back, "tip": tip, "ball": ball, "head": head, "tail": tail}


def add_toe_bones(arm, shoes, parts) -> dict:
    """Adds Toe.L and Toe.R to arm (in its rest pose, at the ball of `shoes`) and splits the foot weights of every
    object in `parts` over the ball. Returns a report; an armature that already has both toes is left alone, one with
    a single toe is refused (adding both would make a second bone named Toe.L.001)."""
    present = [toe_name(s) for s in SIDES if toe_name(s) in arm.data.bones]
    if len(present) == len(SIDES):
        return {"added": False, "bones": len(arm.data.bones)}
    if present:
        raise RuntimeError(f"{arm.name} has only {present}: a partial earlier run or a hand-edited rig; "
                           "remove it and add both toes again")
    update()
    geo = {s: _geometry(arm, shoes, s) for s in SIDES}
    Wi = arm.matrix_world.inverted()

    # the bones, in edit mode on the armature's own data (armature space)
    view_layer = bpy.context.view_layer
    previous = view_layer.objects.active
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        ebones = arm.data.edit_bones
        for s in SIDES:
            foot = ebones[f"Foot.{s}"]
            eb = ebones.new(toe_name(s))
            eb.head = Wi @ geo[s]["head"]
            eb.tail = Wi @ geo[s]["tail"]
            eb.roll = foot.roll  # parallel to the foot: the same roll gives the foot's axes
            eb.parent = foot
            eb.use_connect = False
            eb.use_deform = True
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
        view_layer.objects.active = previous
    for s in SIDES:
        pb = arm.pose.bones[toe_name(s)]
        pb.rotation_mode = "QUATERNION"
    update()

    report = {"added": True, "bones": len(arm.data.bones), "ball_fraction": BALL_FRACTION, "blend_m": BLEND_M,
              "sides": {}, "reweighted": {}}
    for s in SIDES:
        g = geo[s]
        b = arm.data.bones[toe_name(s)]
        x_axis = (arm.matrix_world.to_3x3() @ b.matrix_local.to_3x3().col[0]).normalized()
        report["sides"][s] = {
            "head_m": [round(x, 4) for x in g["head"]], "tail_m": [round(x, 4) for x in g["tail"]],
            "shoe_length_m": round(g["tip"] - g["back"], 4), "ball_from_pivot_m": round(g["ball"], 4),
            "x_axis": [round(x, 3) for x in x_axis],
        }
    for obj in parts:
        moved = 0
        for s in SIDES:
            gf = obj.vertex_groups.get(f"Foot.{s}")
            if gf is None:
                continue
            gt = obj.vertex_groups.get(toe_name(s)) or obj.vertex_groups.new(name=toe_name(s))
            g = geo[s]
            M = obj.matrix_world
            for v in obj.data.vertices:
                w = _weight(v, gf.index)
                if w <= 0.0:
                    continue
                d = (M @ v.co - g["pivot"]).dot(g["fwd"])
                t = _smoothstep((d - (g["ball"] - BLEND_M)) / (2.0 * BLEND_M))
                if t <= 0.0:
                    continue
                if t >= 1.0:
                    gf.remove([v.index])
                else:
                    gf.add([v.index], w * (1.0 - t), "REPLACE")
                gt.add([v.index], w * t, "REPLACE")
                moved += 1
        if moved:
            report["reweighted"][obj.name] = moved
    update()
    return report


def shoes_of(meshes: dict):
    """The shoe part among a pack character's meshes ({name: object}): the one named <Name>_Feet."""
    for name, obj in meshes.items():
        if name.endswith("_Feet"):
            return obj
    raise RuntimeError(f"no <Name>_Feet mesh among {sorted(meshes)}")
