"""Poses as recipe data: a pack action at a frame, or the neutral pose, each with an optional finger curl.

    {"action": "Wave", "frame": 20}                       the skeleton file's own action, after a full reset
    {"neutral": {"down_deg": 70}}                         straight legs, arms lowered from the T-pose, fingers straight
    ... "curl": {"Middle.R": [60, 70, 40], ...}            extra bend per finger joint on top of either

Use the skeleton file's own actions (every import duplicates the 24 actions with a ".001" suffix, and the women's
actions differ from the men's) and reset every pose bone before applying one: the importer leaves the rig in Death,
which turned Interact and Idle_Gun_Pointing upside down. Judge animations in motion: single frozen frames of the
pack's Idle and Walk look twisted, and the pack originals show the same stance.
"""

import math

import bpy
from mathutils import Quaternion, Vector

from .packs import own_action, reset_pose
from .util import update


def action_pose(arm, action, frame):
    """The pose of the rig's own action at frame, kept as plain pose-bone values (no action stays assigned)."""
    reset_pose(arm)
    act = own_action(arm, action)
    ad = arm.animation_data or arm.animation_data_create()
    ad.action = act
    ad.action_slot = act.slots[0]
    bpy.context.scene.frame_set(frame)
    update()
    snap = {pb.name: (pb.location.copy(), pb.rotation_quaternion.copy(), pb.scale.copy()) for pb in arm.pose.bones}
    ad.action = None
    for pb in arm.pose.bones:
        pb.location, pb.rotation_quaternion, pb.scale = snap[pb.name]
    arm.data.pose_position = "POSE"
    update()


def neutral_pose(arm, down_deg=70.0):
    """Straight legs, arms lowered from the T-pose by down_deg toward the floor, fingers straight."""
    reset_pose(arm)
    arm.data.pose_position = "POSE"
    update()
    mw = arm.matrix_world
    for side in ("L", "R"):
        pb = arm.pose.bones["UpperArm." + side]
        head_w = mw @ pb.head; tail_w = mw @ pb.tail
        d = (tail_w - head_w).normalized()
        down = Vector((0.0, 0.0, -1.0))
        axis = d.cross(down)
        if axis.length < 1e-6:
            continue
        rw = Quaternion(axis.normalized(), math.radians(down_deg))
        mq = (mw @ pb.matrix).to_quaternion()
        pb.rotation_quaternion = pb.rotation_quaternion @ (mq.inverted() @ rw @ mq)
        update()


def curl_fingers(arm, curl):
    """curl: {"Middle.R": [deg1, deg2, deg3], ...}: extra bend of each finger joint on top of the pose, about the
    bones' local -X (the pack's curl axis, read from the actions' own finger rotations)."""
    for key, angles in (curl or {}).items():
        finger, side = key.split(".")
        for k, a in enumerate(angles):
            pb = arm.pose.bones["%s%d.%s" % (finger, k + 1, side)]
            pb.rotation_quaternion = pb.rotation_quaternion @ Quaternion((-1.0, 0.0, 0.0), math.radians(a))
    update()


def apply(arm, spec):
    """Pose the rig from a recipe pose spec (one code path for the pack-action pose and the neutral pose)."""
    if "neutral" in spec:
        neutral_pose(arm, spec["neutral"].get("down_deg", 70.0))
    else:
        action_pose(arm, spec["action"], spec["frame"])
    curl_fingers(arm, spec.get("curl"))
