"""Review sheets of the alien body (art #196, S1): fit beside u1, turntables at 1 m and 3 m, hands at rest and in a
fist, the Walk's knees and elbows, the neck ring. Workbench renders, stitched with numpy into sheets of about 1280 px.

    blender -b --factory-startup --python-exit-code 1 --python tools/blender/alien_body_review.py -- \
        --blend <alien_body.blend> --u1 <dir with the u1 *part_0..2.png> --out <dir>
"""

from __future__ import annotations

import argparse
import glob
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

PX_M = 0.0019  # u1: metres per pixel, the sole on row 967 (alien_body.py)
SOLE_ROW = 967


def setup(res):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "MATERIAL"
    sc.display.shading.show_specular_highlight = True
    sc.display.shading.show_shadows = True
    sc.display.shading.show_cavity = False
    sc.render.film_transparent = False
    sc.world = sc.world or bpy.data.worlds.new("w")
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.image_settings.file_format = "PNG"
    cam = bpy.data.objects.get("ReviewCam") or bpy.data.objects.new("ReviewCam", bpy.data.cameras.new("ReviewCam"))
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    sc.camera = cam
    return sc, cam


def look(cam, loc, target, ortho=None, lens=50):
    cam.location = Vector(loc)
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    if ortho:
        cam.data.type, cam.data.ortho_scale = "ORTHO", ortho
    else:
        cam.data.type, cam.data.lens = "PERSP", lens
    cam.data.clip_start = 0.01


def shot(sc, path):
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def load(path):
    im = bpy.data.images.load(path, check_existing=False)
    w, h = im.size
    a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)
    bpy.data.images.remove(im)
    return a


def stitch(paths, cols, out):
    tiles = [load(p) for p in paths]
    h, w = tiles[0].shape[:2]
    rows = math.ceil(len(tiles) / cols)
    sheet = np.ones((rows * h, cols * w, 4), dtype=np.float32)
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        y0 = (rows - 1 - r) * h  # Blender's pixel rows run bottom-up
        sheet[y0:y0 + h, c * w:c * w + w] = t[:h, :w]
    im = bpy.data.images.new("sheet", cols * w, rows * h, alpha=True)
    im.pixels[:] = sheet.ravel()
    im.filepath_raw = out
    im.file_format = "PNG"
    im.save()
    for p in paths:
        os.remove(p)


def u1_plane(png, x, rot_z):
    """The u1 view as an image plane at 1:1 metres, the sole on the floor, at x beside the body."""
    im = bpy.data.images.load(png)
    w, h = im.size
    mat = bpy.data.materials.new("u1")
    mat.use_nodes = True
    nt = mat.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = im
    nt.links.new(tex.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    mat.diffuse_color = (1, 1, 1, 1)
    bpy.ops.mesh.primitive_plane_add(size=1)
    p = bpy.context.active_object
    p.scale = (w * PX_M, h * PX_M, 1)
    p.rotation_euler = (math.pi / 2, 0, rot_z)
    p.location = (x, 0.3, (h / 2 - (h - SOLE_ROW)) * PX_M)
    p.data.materials.append(mat)
    return p


def pose_fist(arm, amount):
    for pb in arm.pose.bones:
        n = pb.name
        if any(f in n for f in ("Index", "Middle", "Ring", "Little")):
            pb.rotation_mode = "XYZ"
            pb.rotation_euler = (math.radians(80 * amount), 0, 0)
        elif "Thumb" in n and "Metacarpal" not in n:
            pb.rotation_mode = "XYZ"
            pb.rotation_euler = (math.radians(35 * amount), 0, math.radians(20 * amount))


def main():
    p = argparse.ArgumentParser(prog="alien_body_review.py")
    p.add_argument("--blend", required=True)
    p.add_argument("--u1", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args(sys.argv[sys.argv.index("--") + 1:])
    os.makedirs(args.out, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=args.blend)
    arm = bpy.data.objects["CharacterArmature"]
    body = bpy.data.objects["Body"]
    out = args.out
    body.active_material.diffuse_color = (0.16, 0.42, 0.40, 1.0)
    u1 = {k: next(iter(glob.glob(f"{args.u1}/*part_{k}.png"))) for k in "012"}

    # 1. Fit: front, side, back beside u1 (ortho, 1:1).
    sc, cam = setup((640, 1280))
    sc.display.shading.color_type = "TEXTURE"
    tiles = []
    for key, view, rot in (("0", "front", 0.0), ("1", "side", -math.pi / 2), ("2", "back", math.pi)):
        plane = u1_plane(u1[key], 0.0, rot)
        # Body at the origin, the plane beside it, both facing the camera.
        d = Vector((math.sin(rot), -math.cos(rot), 0))
        side = Vector((math.cos(rot), math.sin(rot), 0))
        plane.location = Vector((0, 0, plane.location.z)) + side * 0.55 - d * 0.6  # behind the T-pose arm
        look(cam, Vector((0, 0, 0.9)) + d * 6 + side * 0.275, Vector((0, 0, 0.9)) + side * 0.275, ortho=2.0)
        sc.render.resolution_x = 1280 // 2
        tiles.append(shot(sc, f"{out}/_fit_{view}.png"))
        bpy.data.objects.remove(plane)
    stitch(tiles, 3, f"{out}/fit_vs_u1.png")

    # 2. Turntables: 8 angles at 1 m and at 3 m, both framing the whole body, perspective.
    sc, cam = setup((320, 480))
    tiles = []
    for dist, target, lens in ((1.0, (0, 0, 0.7), 16), (3.0, (0, 0, 0.75), 40)):
        for k in range(8):
            a = 2 * math.pi * k / 8
            loc = (math.sin(a) * dist, -math.cos(a) * dist, target[2] + 0.05)
            look(cam, loc, target, lens=lens)
            tiles.append(shot(sc, f"{out}/_turn_{dist}_{k}.png"))
    stitch(tiles, 8, f"{out}/turntable_1m_3m.png")

    # 3. Hands: rest and fist, back and palm side, left hand.
    sc, cam = setup((320, 320))
    hand = arm.data.bones["LeftHand"].head_local
    centre = hand + Vector((0.09, 0, 0))
    tiles = []
    for amount in (0.0, 1.0):
        pose_fist(arm, amount)
        bpy.context.view_layer.update()
        for loc in ((0, 0, 0.45), (0, -0.45, 0.05), (0, 0.0, -0.45), (0.45, -0.1, 0.1)):
            look(cam, centre + Vector(loc), centre, lens=50)
            tiles.append(shot(sc, f"{out}/_hand_{amount}_{len(tiles)}.png"))
    pose_fist(arm, 0.0)
    stitch(tiles, 4, f"{out}/hands_rest_fist.png")

    # 4. Walk: 4 phases, side and three-quarter, knees and elbows.
    act = bpy.data.actions.get("CharacterArmature|Walk_Loop")
    arm.animation_data_create()
    arm.animation_data.action = act
    if act.slots:
        arm.animation_data.action_slot = act.slots[0]
    sc, cam = setup((320, 640))
    tiles = []
    f0, f1 = act.frame_range
    for view in ((3.0, 0, 0), (2.2, -2.2, 0)):
        for k in range(4):
            sc.frame_set(int(f0 + (f1 - f0) * k / 4))
            look(cam, (view[0], view[1], 0.8), (0, 0, 0.7), lens=45)
            tiles.append(shot(sc, f"{out}/_walk_{len(tiles)}.png"))
    stitch(tiles, 4, f"{out}/walk_knees_elbows.png")
    # Close-ups at four phases: the left knee from the side and the front, the left elbow from the side and behind.
    sc, cam = setup((320, 320))
    tiles = []
    for k in range(4):
        sc.frame_set(int(f0 + (f1 - f0) * k / 4))
        bpy.context.view_layer.update()
        knee = arm.matrix_world @ arm.pose.bones["LeftLowerLeg"].head
        elbow = arm.matrix_world @ arm.pose.bones["LeftLowerArm"].head
        for c, off in ((knee, (0.55, 0, 0.05)), (knee, (0.1, -0.55, 0.05)), (elbow, (0.55, 0, 0.0)), (elbow, (0.1, 0.55, 0.0))):
            look(cam, c + Vector(off), c, lens=50)
            tiles.append(shot(sc, f"{out}/_joint_{len(tiles)}.png"))
    stitch(tiles, 4, f"{out}/walk_knee_elbow_closeups.png")
    arm.animation_data.action = None

    # 5. The neck ring from above and the front.
    sc, cam = setup((480, 480))
    tiles = []
    foot = (0.14, -0.08, 0.03)
    for loc, target in (((0, -0.5, 1.6), (0, 0, 1.33)), ((0.5, 0, 1.55), (0, 0, 1.33)), ((0, 0.001, 1.9), (0, 0, 1.33)),
                        ((0.14, -0.6, 0.12), foot), ((0.42, -0.42, 0.45), foot), ((0.6, -0.1, 0.1), foot)):
        look(cam, loc, target, lens=50)
        tiles.append(shot(sc, f"{out}/_neck_{len(tiles)}.png"))
    stitch(tiles, 3, f"{out}/neck_ring_feet.png")


if __name__ == "__main__":
    main()
