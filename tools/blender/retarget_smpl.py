"""Meshy text to motion (art #33): one clip per FBX file on an SMPL-H skeleton (52 bones with fingers, a grey
mannequin skinned to it), loaded for the retarget and the review (docs/animations.md, "Text to motion").

Every file holds the same rig and one action, "Reference|SMPLH_Animation|Base Layer", keyed from frame 1. Its rest is
centred on the pelvis (the mannequin's soles at z = -1.161) while its animation stands on z = 0, so the loader lifts
the armature onto the floor (the floor shift; the meshes are its children and follow) and every sampler of the file
takes the same lift back out of the top bone's basis location (anim_libs.Shifted): the rest and the motion then share
the floor z = 0, as on every other rig, and the animated world poses stay the file's own. A Rig (retarget_core) caches
the armature's matrix, so it is built after the shift.
"""

from __future__ import annotations

import bpy
from mathutils import Matrix, Vector

import retarget_core as rc
from anim_metrics import world_points

FORMAT = "smplh_fbx"  # the review settings' `format` of a library of these files
TOP = "Pelvis"  # the top bone (no root): its location keys carry the travel
# the importer's options, explicit so a changed default cannot move the rig: the animation from frame 1, every bone
# kept as it is in the file, no custom properties (the file's "Short" properties only warn), metres as authored
IMPORT = {"use_anim": True, "anim_offset": 1.0, "ignore_leaf_bones": False, "automatic_bone_orientation": False,
          "use_custom_props": False, "global_scale": 1.0, "axis_forward": "-Z", "axis_up": "Y"}


def lowest(meshes) -> float:
    """The lowest world height of the meshes as they are posed now."""
    bpy.context.view_layer.update()
    return min(float(world_points(o)[:, 2].min()) for o in meshes)


def import_fbx(path: str, shift: bool = True) -> dict:
    """Imports one text-to-motion FBX at 30 fps. Returns rc.load_glb's dict without `actions`: {arm, root (None),
    meshes {base name: obj}, objects, path, action (the file's one action, unassigned), floor_shift_m}, the empties
    removed and the pose reset. With shift (the default) the armature is lifted by the rest's depth below the floor
    (floor_shift_m); without it the file stays as imported (floor_shift_m 0, for comparisons)."""
    scene = bpy.context.scene
    scene.render.fps, scene.render.fps_base = rc.FPS, 1.0
    before_obj, before_act = set(bpy.data.objects), set(bpy.data.actions)
    bpy.ops.import_scene.fbx(filepath=path, **IMPORT)
    if scene.render.fps != rc.FPS:
        raise SystemExit(f"{path}: the import set the scene to {scene.render.fps} fps")
    new = [o for o in bpy.data.objects if o not in before_obj]
    for o in [o for o in new if o.type == "EMPTY"]:  # body.001, qiu_L, qiu_R: grouping nodes that deform nothing
        new.remove(o)
        bpy.data.objects.remove(o, do_unlink=True)
    arms = [o for o in new if o.type == "ARMATURE"]
    actions = [a for a in bpy.data.actions if a not in before_act]
    if len(arms) != 1 or len(actions) != 1:
        raise SystemExit(f"{path}: {len(arms)} armatures and {len(actions)} actions, not one clip on one rig")
    arm = arms[0]
    rc.reset_pose(arm)  # unassigns the action: the rest pose
    meshes = {rc.base_name(o.name): o for o in new if o.type == "MESH"}
    h = -lowest(meshes.values()) if shift else 0.0
    if h:
        arm.matrix_world = Matrix.Translation((0.0, 0.0, h)) @ arm.matrix_world
        bpy.context.view_layer.update()
    return {"arm": arm, "root": None, "meshes": meshes, "objects": new, "path": path, "action": actions[0],
            "floor_shift_m": h}


def floor_offset(rig: rc.Rig, shift_m: float, bone: str = TOP) -> Vector:
    """The top bone's basis location that moves it down by shift_m metres in world space on rig (built after the
    shift): world -> armature space (the armature's scale and rotation) -> the bone's rest frame, where its basis
    location lives (a top bone's pose is rest @ basis), as anim_libs.InPlace takes out its drift."""
    if rig.parent.get(bone) is not None:
        raise ValueError(f"floor shift: {bone!r} is not the rig's top bone")
    return rc.rot(rig.rest[bone]).inverted() @ (rig.Wi.to_3x3() @ Vector((0.0, 0.0, shift_m)))
