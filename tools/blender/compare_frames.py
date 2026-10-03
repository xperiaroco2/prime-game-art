"""Blender's side of the Blender-against-Godot comparison (`tools/run.py frames --compare`, docs/godot.md): the saved
character posed at the times Godot rendered, through the same orthographic camera, rendered with Workbench
(tools/blender/um/render.py), and each joint's world position in glTF axes. Background only:

  blender -b --factory-startup --python-exit-code 1 --python tools/blender/compare_frames.py -- \
      --blend <id>.blend --frames <frames.json> --clips Idle,Walk,Wave --out <folder>

frames.json is what godot/frames/frames.gd wrote (per clip: the animation, the times, the camera, the window size,
Godot's joints, axis points and kept frames). Writes <out>/blender/<label>/<i>.png, <out>/<label>.png (Godot's frames above
Blender's, one column per time) and <out>/blender_joints.json.
"""

import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from um import render as rd  # noqa: E402

CELL = (200, 250)
GAP = 4
AXIS_LEVER = 0.1  # godot/lib/character.gd AXIS_LEVER


def to_blender(v):
    """A glTF point (+Y up, front +Z) in Blender's axes (+Z up, front -Y)."""
    return Vector((v[0], -v[2], v[1]))


def gltf(v):
    return [round(v[0], 5), round(v[2], 5), round(-v[1], 5)]


def axis_points(arm):
    """Each bone's two axis points as godot/lib/character.gd axis_points() computes them: AXIS_LEVER from the joint along
    glTF +X and +Y (Blender +X and +Z) in the rest pose, carried by the bone's pose; in glTF axes."""
    mw = arm.matrix_world
    inv = mw.inverted()
    out = {}
    for pb in arm.pose.bones:
        rest = pb.bone.matrix_local
        moved = pb.matrix @ rest.inverted()
        head = mw @ rest.translation
        for axis, offset in (("x", Vector((AXIS_LEVER, 0, 0))), ("y", Vector((0, 0, AXIS_LEVER)))):
            out[f"{pb.name}+{axis}"] = gltf(mw @ (moved @ (inv @ (head + offset))))
    return out


def place_camera(cam, spec, window):
    right, up, back = (to_blender(spec[k]) for k in ("right", "up", "back"))
    centre = to_blender(spec["centre"])
    rot = Matrix((right, up, back)).transposed()  # columns: the camera's +X, +Y and +Z (it looks down -Z)
    cam.matrix_world = Matrix.Translation(centre + back * spec["distance"]) @ rot.to_4x4()
    cam.data.type = "ORTHO"
    cam.data.sensor_fit = "VERTICAL"
    cam.data.ortho_scale = spec["ortho_size"]  # Godot's orthographic size is the vertical extent too
    cam.data.clip_end = 100.0
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = window
    scene.render.resolution_percentage = 100


def caption(cam, spec, window, text):
    """A label in the frame's upper left, in front of everything, facing the camera."""
    obj = bpy.data.objects.get("caption")
    if obj is None:
        obj = rd.label(text, Vector(), size=1.0)
        obj.name = "caption"
        obj.data.align_x = "LEFT"
    obj.data.body = text
    px = spec["ortho_size"] / window[1]  # metres per pixel
    obj.data.size = 20 * px
    half_w, half_h = window[0] / 2 * px, window[1] / 2 * px
    local = Vector((-half_w + 12 * px, half_h - 26 * px, -1.0))
    obj.matrix_world = cam.matrix_world @ Matrix.Translation(local)
    return obj


def compose(rows, out):
    """Rows of PNG paths into one image: every cell scaled to CELL, GAP pixels apart, on white."""
    import numpy as np

    cols = max(len(r) for r in rows)
    w, h = CELL
    W, H = cols * w + (cols + 1) * GAP, len(rows) * h + (len(rows) + 1) * GAP
    canvas = np.ones((H, W, 4), dtype=np.float32)
    for r, row in enumerate(rows):
        for c, path in enumerate(row):
            img = bpy.data.images.load(path)
            img.scale(w, h)
            a = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
            bpy.data.images.remove(img)
            y0 = H - (GAP + r * (h + GAP)) - h  # Blender images start at the bottom row
            x0 = GAP + c * (w + GAP)
            canvas[y0 : y0 + h, x0 : x0 + w] = a
    canvas[..., 3] = 1.0
    img = bpy.data.images.new("comparison", W, H, alpha=False)
    img.pixels.foreach_set(canvas.ravel())
    img.filepath_raw = out
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    print("COMPOSED", out, W, "x", H)


def main():
    p = argparse.ArgumentParser(prog="compare_frames.py")
    p.add_argument("--blend", required=True)
    p.add_argument("--frames", required=True)
    p.add_argument("--clips", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    with open(args.frames, encoding="utf-8") as fh:
        record = json.load(fh)
    frames_dir = os.path.dirname(os.path.abspath(args.frames))

    bpy.ops.wm.open_mainfile(filepath=args.blend)
    scene = bpy.context.scene
    arm = next(o for o in scene.objects if o.type == "ARMATURE")
    cam = rd.setup_render()
    scene.display.shading.show_object_outline = False
    window = tuple(record["window"])
    fps = scene.render.fps
    ad = arm.animation_data or arm.animation_data_create()
    joints = {}
    for label in args.clips.split(","):
        clip = record["clips"].get(label)
        if clip is None:
            raise SystemExit(f"frames.json has no clip {label}; it has {sorted(record['clips'])}")
        act = bpy.data.actions[clip["name"]]
        ad.action = act
        ad.action_slot = act.slots[0]
        place_camera(cam, clip["camera"], window)
        joints[label] = []
        godot_row, blender_row = [], []
        for i, t in enumerate(clip["times"]):
            f = t * fps
            # an action leaves the channels it does not key where the last one put them; the export sampled every
            # bone from the rest pose (export_reset_pose_bones), so start each pose from the rest pose too
            for pb in arm.pose.bones:
                pb.location = (0.0, 0.0, 0.0)
                pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
                pb.scale = (1.0, 1.0, 1.0)
            scene.frame_set(int(math.floor(f)), subframe=f - math.floor(f))
            bpy.context.view_layer.update()
            mw = arm.matrix_world
            joints[label].append({**{pb.name: gltf(mw @ pb.head) for pb in arm.pose.bones}, **axis_points(arm)})
            caption(cam, clip["camera"], window, f"Blender {bpy.app.version_string.split()[0]}   f{f:.1f}")
            path = os.path.join(args.out, "blender", label, f"{i:02d}.png")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            scene.render.filepath = path
            bpy.ops.render.render(write_still=True)
            godot_row.append(os.path.join(frames_dir, "frames", label, f"{i:02d}.png"))
            blender_row.append(path)
        compose([godot_row, blender_row], os.path.join(args.out, f"{label}.png"))
    ad.action = None
    with open(os.path.join(args.out, "blender_joints.json"), "w", encoding="utf-8") as fh:
        json.dump({"blender": bpy.app.version_string, "fps": fps, "joints": joints}, fh)
    print("COMPARED", ",".join(joints))


if __name__ == "__main__":
    main()
