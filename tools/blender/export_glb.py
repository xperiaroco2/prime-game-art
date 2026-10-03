"""glTF 2.0 binary export of a saved character (the .blend `assemble --blend` writes, docs/assembly.md) with fixed
options (each with its reason in docs/godot.md). The runner calls it (tools/run.py export); by hand, background only:

  blender -b --factory-startup --python-exit-code 1 --python tools/blender/export_glb.py -- \
      --blend tools/out/assemble/um_final_test/blend/m1_rex.blend --glb <out>/m1_rex.glb --json <out>/m1_rex.export.json

Writes the GLB and a JSON description of what was exported, measured in Blender before the export and converted to
glTF axes (+Y up, front +Z): the armature and its bones' rest heads, every part (object, triangles, vertex groups,
materials), the actions with their frame ranges, the rest-pose bounds and height. `tools/run.py godot-check` compares
Godot's import with these numbers.

The description also holds each action's seam (seams()): how far its last frame is from its first.

EXPORT_OPTIONS is a plain module constant (bpy is imported only inside main()), so the runner and the tests can read
the options without Blender.
"""

import math

# Every option the export depends on, passed explicitly so that a changed Blender default cannot change the output.
# The reasons are in docs/godot.md ("The export options").
EXPORT_OPTIONS = {
    "export_format": "GLB",
    "use_active_scene": True,
    "use_selection": False,
    "use_visible": False,
    "use_renderable": False,
    "use_active_collection": False,
    "export_yup": True,
    "export_apply": False,
    "export_skins": True,
    "export_influence_nb": 4,
    "export_all_influences": False,
    "export_def_bones": False,
    "export_rest_position_armature": True,
    "export_reset_pose_bones": True,
    "export_leaf_bone": False,
    "export_hierarchy_flatten_bones": False,
    "export_hierarchy_flatten_objs": False,
    "export_armature_object_remove": False,
    "export_animations": True,
    "export_animation_mode": "ACTIONS",
    "export_action_filter": False,
    "export_extra_animations": False,
    "export_bake_animation": False,
    "export_anim_single_armature": True,
    "export_frame_range": False,
    "export_frame_step": 1,
    "export_force_sampling": True,
    "export_sampling_interpolation_fallback": "LINEAR",
    "export_optimize_animation_size": True,
    "export_optimize_animation_keep_anim_armature": True,
    "export_optimize_animation_keep_anim_object": False,
    "export_anim_slide_to_zero": False,
    "export_negative_frame": "SLIDE",
    "export_current_frame": False,
    "export_pointer_animation": False,
    "export_morph": False,
    "export_cameras": False,
    "export_lights": False,
    "export_materials": "EXPORT",
    "export_image_format": "NONE",
    "export_vertex_color": "NONE",
    "export_all_vertex_colors": False,
    "export_active_vertex_color_when_no_material": False,
    "export_texcoords": True,
    "export_normals": True,
    "export_tangents": False,
    "export_attributes": False,
    "export_extras": False,
    "export_shared_accessors": False,
    "export_gpu_instances": False,
    "export_gn_mesh": False,
    "export_draco_mesh_compression_enable": False,
    "export_meshopt_compression_enable": False,
    "export_use_gltfpack": False,
    "export_original_specular": False,
    "check_existing": False,
    "will_save_settings": False,
}

ACTION_PREFIX = "CharacterArmature|"


def gltf_axes(v):
    """A Blender point (+Z up, front -Y) in glTF axes (+Y up, front +Z), as the exporter converts it."""
    return [round(v[0], 5), round(v[2], 5), round(-v[1], 5)]


def describe(bpy, arm, parts):
    """The character as the export sees it, in glTF axes."""
    dg = bpy.context.evaluated_depsgraph_get()
    lo, hi = [float("inf")] * 3, [float("-inf")] * 3
    out_parts = {}
    for o in parts:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        pts = [gltf_axes(ev.matrix_world @ v.co) for v in me.vertices]
        ev.to_mesh_clear()
        plo = [min(p[i] for p in pts) for i in range(3)]
        phi = [max(p[i] for p in pts) for i in range(3)]
        lo = [min(a, b) for a, b in zip(lo, plo)]
        hi = [max(a, b) for a, b in zip(hi, phi)]
        out_parts[o.name] = {
            "triangles": sum(len(p.vertices) - 2 for p in o.data.polygons),
            "vertices": len(o.data.vertices),
            "vertex_groups": len(o.vertex_groups),
            "materials": [{"name": s.material.name, "rgb": [round(c, 4) for c in s.material.diffuse_color[:3]]}
                          for s in o.material_slots if s.material],
            "bounds_m": {"min": plo, "max": phi},
        }
    mw = arm.matrix_world
    return {
        "armature": arm.name,
        "bones": [b.name for b in arm.data.bones],
        "bone_parents": {b.name: b.parent.name if b.parent else None for b in arm.data.bones},
        "rest_heads_m": {b.name: gltf_axes(mw @ b.head_local) for b in arm.data.bones},
        "parts": out_parts,
        "actions": {a.name: [int(a.frame_range[0]), int(a.frame_range[1])] for a in sorted(bpy.data.actions, key=lambda a: a.name)},
        "fps": bpy.context.scene.render.fps,
        "bounds_m": {"min": lo, "max": hi},
        "height_m": round(hi[1] - lo[1], 4),
        "feet_y_m": round(lo[1], 4),
    }


def _angle_deg(a, b):
    """The rotation between two quaternions in degrees, 0 to 180 (q and -q are the same rotation)."""
    deg = math.degrees(a.rotation_difference(b).angle)
    return min(deg, 360.0 - deg)


def seams(bpy, arm):
    """Per action: how far its last frame's pose is from its first, over every bone (the joint's world position in
    mm, the rotation in armature space in degrees). A closed cycle's last key repeats its first; an open one (the
    pack's Run, Run_Left, Run_Right) ends one frame before its first pose comes round again."""
    scene = bpy.context.scene
    ad = arm.animation_data or arm.animation_data_create()
    mw = arm.matrix_world

    def pose_at(frame):
        for pb in arm.pose.bones:  # start from the rest pose, as the export samples (export_reset_pose_bones)
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
            pb.scale = (1.0, 1.0, 1.0)
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        return {pb.name: (mw @ pb.head, pb.matrix.to_quaternion()) for pb in arm.pose.bones}

    out = {}
    for act in sorted(bpy.data.actions, key=lambda a: a.name):
        ad.action = act
        ad.action_slot = act.slots[0]
        first, last = pose_at(int(act.frame_range[0])), pose_at(int(act.frame_range[1]))
        out[act.name] = {
            "position_mm": round(max((first[b][0] - last[b][0]).length for b in first) * 1000, 3),
            "rotation_deg": round(max(_angle_deg(first[b][1], last[b][1]) for b in first), 3),
        }
    ad.action = None
    for pb in arm.pose.bones:
        pb.location = (0.0, 0.0, 0.0)
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)
    return out


def exporter_version():
    """The glTF add-on's version, e.g. "5.2.10"."""
    import io_scene_gltf2

    return ".".join(str(n) for n in io_scene_gltf2.bl_info["version"])


def main():
    import argparse
    import json
    import os
    import sys

    import bpy

    p = argparse.ArgumentParser(prog="export_glb.py")
    p.add_argument("--blend", required=True)
    p.add_argument("--glb", required=True)
    p.add_argument("--json", required=True)
    args = p.parse_args(sys.argv[sys.argv.index("--") + 1 :])

    bpy.ops.wm.open_mainfile(filepath=args.blend)
    scene = bpy.context.scene
    arms = [o for o in scene.objects if o.type == "ARMATURE"]
    others = [o for o in scene.objects if o.type not in ("ARMATURE", "MESH")]
    if len(arms) != 1 or others:
        raise SystemExit(f"{args.blend}: not a saved character ({len(arms)} armatures, other objects {[o.name for o in others]})")
    arm = arms[0]
    parts = sorted((o for o in scene.objects if o.type == "MESH"), key=lambda o: o.name)
    for o in parts:
        mods = [m.type for m in o.modifiers]
        if o.parent is not arm or mods != ["ARMATURE"]:
            raise SystemExit(f"{o.name}: not parented to {arm.name} with one Armature modifier ({mods})")
    if arm.animation_data and (arm.animation_data.action or arm.animation_data.nla_tracks):
        raise SystemExit(f"{arm.name}: an action or NLA track is assigned; a saved character has none")
    for pb in arm.pose.bones:  # the rest pose: what the skin's inverse bind matrices are taken from
        pb.location = (0.0, 0.0, 0.0)
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)
    bpy.context.view_layer.update()

    info = describe(bpy, arm, parts)
    os.makedirs(os.path.dirname(os.path.abspath(args.glb)), exist_ok=True)
    result = bpy.ops.export_scene.gltf(filepath=args.glb, **EXPORT_OPTIONS)
    if result != {"FINISHED"}:
        raise SystemExit(f"the glTF exporter returned {result}")
    info.update({
        "blend": os.path.abspath(args.blend).replace("\\", "/"),
        "glb": os.path.abspath(args.glb).replace("\\", "/"),
        "blender": bpy.app.version_string,
        "exporter": exporter_version(),
        "options": EXPORT_OPTIONS,
        "seams": seams(bpy, arm),
    })
    with open(args.json, "w", encoding="utf-8") as fh:
        json.dump(info, fh, indent=1)
    print("EXPORTED", args.glb)


if __name__ == "__main__":
    main()
