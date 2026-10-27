"""M1c (art #196): how far the game's clips bend a welded alien's joints, and what the body shows there.

blender -b --python alien_body_clip_bends.py -- --blend <char.blend> --clips <loco build char.blend> --out <dir>

The game's clips are the loco build's actions (`anim_sets/alien_loco.toml`'s build: the game's move clips beside the
build's UAL clips) without "__" (variants, befores) and not the sources (TM_, MC_). Each is appended onto the
character's armature (the same contract skeleton) and played frame by frame. Per frame and side:
- knee, elbow: the angle between the two bones minus the rest's;
- hip, shoulder: the child bone's direction (the thigh, the upper arm) in its parent's frame (Hips; the shoulder
  bone's parent) against the rest's; with the bone's world direction at that frame (fwd: -y, down: -z);
- the thumb's and the fingers' local rotations (degrees from rest).
clip_bends.json: per clip the deepest frame per joint, and per joint the deepest clip. clip_frames.png (1280 px): per
joint (knee, elbow, hip, shoulder; the hand at the thumb's deepest metacarpal turn) its deepest clip's frame in two
close-ups, from the bend's inside (the knee's back, the elbow's crease, the groin, the armpit, the thumb's web) and in
profile across the bend's plane; the clip, frame and angle in each file name. The refit review's light and ground."""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import alien_body_refit_review as R  # noqa: E402

FING = ["ThumbMetacarpal", "ThumbProximal", "ThumbDistal", "IndexProximal", "MiddleProximal", "RingProximal",
        "LittleProximal", "IndexIntermediate", "MiddleIntermediate"]
# per joint: the bone at its centre (its head), the bend's two sides: (the parent side's bone, its sign: +1 its own
# direction, -1 reversed; the child bone), seen from the bend's inside (the two sides' bisector, tilted a little
# toward the outside) and in profile (across the bend's plane, from the body's outside), at a distance in m
VIEWS = {
    "knee": ("LowerLeg", ("UpperLeg", -1), "LowerLeg", 0.6),
    "elbow": ("LowerArm", ("UpperArm", -1), "LowerArm", 0.55),
    "hip": ("UpperLeg", ("Spine", 1), "UpperLeg", 0.65),
    "shoulder": ("UpperArm", ("Spine", -1), "UpperArm", 0.6),
    "ThumbMetacarpal": ("ThumbProximal", ("Hand", -1), "ThumbProximal", 0.38),  # the hand: the thumb's web, side
}


def bend_views(arm, side, parent, child, dist):
    """The two camera offsets of a bend: from its inside (the bisector of the two sides' directions away from the
    joint, tilted 0.35 toward the outside) and in profile (across the bend's plane, the side's outside)."""
    pb = arm.pose.bones
    name, sign = parent
    pn = name if name in pb else f"{side}{name}"
    u = (pb[pn].tail - pb[pn].head).normalized() * sign
    v = (pb[f"{side}{child}"].tail - pb[f"{side}{child}"].head).normalized()
    n = u.cross(v)
    if n.length < 1e-3:  # straight: any axis across the bone
        n = v.cross(Vector((0.0, 0.0, 1.0)))
    n.normalize()
    if n.x * (1 if side == "Left" else -1) < 0:
        n = -n
    b = u + v
    b = b.normalized() if b.length > 1e-3 else -n
    return [(b + 0.35 * n).normalized() * dist, (n - 0.15 * b).normalized() * dist]


def ang(u, v):
    return math.degrees(u.angle(v)) if u.length > 1e-9 and v.length > 1e-9 else 0.0


def game_clip(name: str) -> bool:
    """A game clip of the loco build: no variant or before ("__"), not a source (TM_, MC_)."""
    n = name.split("|")[-1]
    return "__" not in n and not n.startswith(("TM_", "MC_"))


def measure(arm, acts):
    def vec(b):
        return b.tail_local - b.head_local

    def rel_rest(child, parent):
        return (arm.data.bones[parent].matrix_local.to_3x3().inverted() @ vec(arm.data.bones[child])).normalized()

    def rel_pose(child, parent):
        pb = arm.pose.bones
        return (pb[parent].matrix.to_3x3().inverted() @ (pb[child].tail - pb[child].head)).normalized()
    rest = {}
    bb = arm.data.bones
    for s in ("Left", "Right"):
        rest[s] = {"knee": ang(vec(bb[f"{s}UpperLeg"]), vec(bb[f"{s}LowerLeg"])),
                   "elbow": ang(vec(bb[f"{s}UpperArm"]), vec(bb[f"{s}LowerArm"])),
                   "hip": rel_rest(f"{s}UpperLeg", "Hips"), "shp": bb[f"{s}Shoulder"].parent.name}
        rest[s]["shoulder"] = rel_rest(f"{s}UpperArm", rest[s]["shp"])
    clips = {}
    for act in acts:
        arm.animation_data.action = act
        f0, f1 = (int(round(x)) for x in act.frame_range)
        best = {}
        for f in range(f0, f1 + 1):
            bpy.context.scene.frame_set(f)
            pb = arm.pose.bones
            for s in ("Left", "Right"):
                d = {"knee": ang(pb[f"{s}UpperLeg"].tail - pb[f"{s}UpperLeg"].head,
                                 pb[f"{s}LowerLeg"].tail - pb[f"{s}LowerLeg"].head) - rest[s]["knee"],
                     "elbow": ang(pb[f"{s}UpperArm"].tail - pb[f"{s}UpperArm"].head,
                                  pb[f"{s}LowerArm"].tail - pb[f"{s}LowerArm"].head) - rest[s]["elbow"],
                     "hip": ang(rel_pose(f"{s}UpperLeg", "Hips"), rest[s]["hip"]),
                     "shoulder": ang(rel_pose(f"{s}UpperArm", rest[s]["shp"]), rest[s]["shoulder"])}
                for n in FING:
                    if f"{s}{n}" in pb:
                        d[n] = math.degrees(pb[f"{s}{n}"].matrix_basis.to_quaternion().angle)
                for k, v in d.items():
                    if v > best.get(k, {"deg": -1e9})["deg"]:
                        e = {"deg": round(v, 1), "frame": f, "side": s}
                        if k in ("hip", "shoulder"):
                            b = pb[f"{s}UpperLeg" if k == "hip" else f"{s}UpperArm"]
                            w = (b.tail - b.head).normalized()
                            e.update(fwd=round(-w.y, 3), down=round(-w.z, 3))
                        best[k] = e
        name = act.name.split("|")[-1].rsplit(".", 1)[0]
        clips[name] = {"frames": [f0, f1], **best}
        print("CLIP", name, f0, f1, {k: (v["deg"], v["frame"], v["side"][0]) for k, v in best.items()}, flush=True)
    deepest = {}
    for c, v in clips.items():
        for k, e in v.items():
            if k != "frames" and e["deg"] > deepest.get(k, {"deg": -1e9})["deg"]:
                deepest[k] = {"clip": c, **e}
    return clips, deepest


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--blend", required=True)
    p.add_argument("--clips", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args(sys.argv[sys.argv.index("--") + 1:])
    os.makedirs(a.out, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=a.blend)
    with bpy.data.libraries.load(a.clips, link=False) as (src, dst):
        dst.actions = [n for n in src.actions if game_clip(n)]
    acts = [x for x in dst.actions if x is not None]
    arm = bpy.data.objects["CharacterArmature"]
    arm.animation_data_create()
    clips, deepest = measure(arm, acts)
    by = {x.name.split("|")[-1].rsplit(".", 1)[0]: x for x in acts}
    for o in bpy.data.objects:
        if o.type == "MESH" and not o.hide_render:
            for m in o.data.materials:
                if m and "eye" not in m.name.lower():
                    m.diffuse_color = (*R.BODY_RGB, 1.0)
    sc, cam = R.setup((640, 640))
    gm = bpy.data.materials.new("Ground")
    gm.diffuse_color = (0.42, 0.42, 0.42, 1.0)
    bpy.ops.mesh.primitive_plane_add(size=8, location=(0, 0, 0))
    bpy.context.active_object.data.materials.append(gm)
    shots = []
    for j, (bone, parent, child, dist) in VIEWS.items():
        e = deepest[j]
        arm.animation_data.action = by[e["clip"]]
        sc.frame_set(e["frame"])
        bpy.context.view_layer.update()
        c = arm.matrix_world @ arm.pose.bones[f"{e['side']}{bone}"].head
        for k, v in enumerate(bend_views(arm, e["side"], parent, child, dist)):
            R.look(cam, c + v, c, lens=60)
            name = f"clip_{j}_{k}_{e['clip']}_f{e['frame']}_{round(e['deg'])}deg.png"
            shots.append(R.shot(sc, os.path.join(a.out, name), (640, 640)))
    R.stitch(shots, 4, os.path.join(a.out, "clip_frames.png"), cell=(320, 320))
    with open(os.path.join(a.out, "clip_bends.json"), "w", encoding="utf-8") as fh:
        json.dump({"deepest": deepest, "clips": clips}, fh, indent=1)
    print("BENDS deepest", json.dumps(deepest), flush=True)


if __name__ == "__main__":
    main()
