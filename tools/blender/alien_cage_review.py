"""Review sheets of the cage body (art #196, S4a) beside the first test: the assembled characters (alien_assemble.py's
build/alien_character.blend) under the same Workbench cameras, one flat colour so the forms show, stitched with numpy
into sheets of about 1280 px.

    blender -b --factory-startup --python-exit-code 1 --python tools/blender/alien_cage_review.py -- \
        --shots <character.blend> --tag <name> --out <dir>          (once per character)
    blender -b ... -- --sheets --tags first,cage --u1 <dir with the u1 *part_0..2.png> --out <dir>

The shots: the silhouettes (front and side, orthographic, 640 px per metre), turntables at 1 m and 3 m (8 angles),
Idle and Walk frames (3/4 view), the neck weld (4 views) and the left wrist (rest and in the Walk). The sheets put the
characters' tiles side by side, u1 first in the silhouettes (scaled to the same metres per pixel, the soles aligned).
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

PX_PER_M = 640
SOLE = {"0": 967, "1": 969, "2": 954}  # u1's sole rows (alien_body.py)
U1_PX_M = 0.0019
SHOW = ("eye_bored_", "mouth_frog_rest")


def setup(res):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "SINGLE"
    sh.single_color = (0.16, 0.42, 0.40)
    sh.show_specular_highlight = True
    sh.show_shadows = False
    sh.show_cavity = False
    sc.render.film_transparent = False
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    cam = bpy.data.objects.get("ReviewCam") or bpy.data.objects.new("ReviewCam", bpy.data.cameras.new("ReviewCam"))
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    sc.camera = cam
    return sc, cam


def look(cam, loc, target, ortho=None, lens=50):
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cam.data.type = "ORTHO" if ortho else "PERSP"
    if ortho:
        cam.data.ortho_scale = ortho
    cam.data.lens = lens
    cam.data.clip_start = 0.01


def shot(sc, path):
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def load(path):
    img = bpy.data.images.load(path)
    w, h = img.size
    a = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1]
    bpy.data.images.remove(img)
    return a


def save(arr, path):
    h, w = arr.shape[:2]
    img = bpy.data.images.new("sheet", w, h, alpha=True)
    img.pixels = arr[::-1].ravel()
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def grid(rows, out):
    """rows: lists of arrays; each row's tiles padded to the tallest, rows padded to the widest."""
    bg = np.array([0.22, 0.22, 0.22, 1.0], dtype=np.float32)
    built = []
    for tiles in rows:
        h = max(t.shape[0] for t in tiles)
        padded = []
        for t in tiles:
            p = np.empty((h, t.shape[1], 4), dtype=np.float32)
            p[:] = bg
            p[: t.shape[0]] = t
            padded.append(p)
        built.append(np.concatenate(padded, axis=1))
    w = max(r.shape[1] for r in built)
    full = []
    for r in built:
        p = np.empty((r.shape[0], w, 4), dtype=np.float32)
        p[:] = bg
        p[:, : r.shape[1]] = r
        full.append(p)
    save(np.concatenate(full, axis=0), out)


def shots(blend, tag, out):
    bpy.ops.wm.open_mainfile(filepath=blend)
    arm = bpy.data.objects["CharacterArmature"]
    # one eye design, one mouth piece, no crest: hide every other variant (and its children)
    for o in bpy.data.objects:
        n = o.name
        if n.startswith(("eye_", "mouth_", "crest_")) and not n.startswith(SHOW):
            for c in [o] + list(o.children_recursive):
                c.hide_render = True
    if arm.animation_data:
        arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    d = f"{out}/{tag}"
    os.makedirs(d, exist_ok=True)
    # silhouettes: front and side, orthographic, 2.0 m tall at 1280 px
    sc, cam = setup((640, 1280))
    look(cam, (0, -6, 0.9), (0, 0, 0.9), ortho=2.0)
    shot(sc, f"{d}/sil_front.png")
    look(cam, (6, 0, 0.9), (0, 0, 0.9), ortho=2.0)
    shot(sc, f"{d}/sil_side.png")
    look(cam, (0, 6, 0.9), (0, 0, 0.9), ortho=2.0)
    shot(sc, f"{d}/sil_back.png")
    # turntables
    sc, cam = setup((240, 400))
    for dist, tz, lens in ((1.0, 0.85, 14), (3.0, 0.85, 40)):
        for k in range(8):
            a = 2 * math.pi * k / 8
            look(cam, (math.sin(a) * dist, -math.cos(a) * dist, tz + 0.05), (0, 0, tz), lens=lens)
            shot(sc, f"{d}/turn_{int(dist)}_{k}.png")
    # close 3/4 views of the body below the neck, for the forms (knees, groin, belly, seat)
    sc, cam = setup((420, 760))
    for k, deg in enumerate((35, 145, 215, 325)):
        a = math.radians(deg)
        look(cam, (math.sin(a) * 1.9, -math.cos(a) * 1.9, 0.95), (0, 0, 0.72), lens=35)
        shot(sc, f"{d}/close_{k}.png")
    # Idle and Walk, 3/4 front
    sc, cam = setup((240, 400))
    arm.animation_data_create()
    for clip in ("Idle_Loop", "Walk_Loop"):
        act = bpy.data.actions[f"CharacterArmature|{clip}"]
        arm.animation_data.action = act
        if act.slots:
            arm.animation_data.action_slot = act.slots[0]
        f0, f1 = act.frame_range
        for k in range(4):
            sc.frame_set(int(f0 + (f1 - f0) * k / 4))
            look(cam, (2.1, -2.1, 1.0), (0, 0, 0.8), lens=40)
            shot(sc, f"{d}/{clip}_{k}.png")
    # the left wrist in the Walk (2 phases) and at rest
    sc, cam = setup((320, 320))
    act = bpy.data.actions["CharacterArmature|Walk_Loop"]
    f0, f1 = act.frame_range
    for k in range(2):
        sc.frame_set(int(f0 + (f1 - f0) * k / 2))
        bpy.context.view_layer.update()
        w = arm.matrix_world @ arm.pose.bones["LeftHand"].head
        look(cam, w + Vector((0.35, -0.12, 0.05)), w, lens=50)
        shot(sc, f"{d}/wrist_walk_{k}.png")
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    sc.frame_set(1)
    bpy.context.view_layer.update()
    w = arm.data.bones["LeftHand"].head_local
    for k, off in enumerate(((0, -0.3, 0.05), (0, 0.0, 0.3), (0, 0.0, -0.3))):
        look(cam, w + Vector(off), w, lens=50)
        shot(sc, f"{d}/wrist_rest_{k}.png")
    # the neck weld: front, side, back, 3/4 back
    sc, cam = setup((320, 320))
    c = Vector((0, 0.04, 1.40))
    for k, off in enumerate(((0, -0.6, 0.05), (0.6, 0, 0.05), (0, 0.6, 0.05), (0.42, 0.42, 0.1))):
        look(cam, c + Vector(off), c, lens=50)
        shot(sc, f"{d}/neck_{k}.png")
    # the left foot close: 3/4 front, front, side, 3/4 back, top; then two Walk phases from the side
    f = Vector((0.117, -0.01, 0.06))
    for k, off in enumerate(((0.3, -0.35, 0.18), (0.0, -0.45, 0.1), (0.45, 0.0, 0.05), (0.3, 0.35, 0.15),
                             (0.05, -0.12, 0.45))):
        look(cam, f + Vector(off), f, lens=50)
        shot(sc, f"{d}/foot_{k}.png")
    arm.animation_data.action = act
    if act.slots:
        arm.animation_data.action_slot = act.slots[0]
    for k in range(2):
        sc.frame_set(int(f0 + (f1 - f0) * (0.1 + k / 2)))
        bpy.context.view_layer.update()
        a_ = arm.matrix_world @ arm.pose.bones["LeftFoot"].head
        look(cam, a_ + Vector((0.55, -0.05, 0.0)), a_ + Vector((0, -0.04, -0.04)), lens=50)
        shot(sc, f"{d}/foot_walk_{k}.png")
    arm.animation_data.action = None


def u1_tile(path, key):
    img = load(path)
    s = PX_PER_M * U1_PX_M  # u1 pixels per output pixel
    h, w = img.shape[:2]
    out_h = 1280
    sole_out = int(640 + 0.9 * PX_PER_M)
    rows = (np.arange(out_h) - sole_out) / s + SOLE[key]
    cols = np.arange(int(w * s)) / s
    ri = np.clip(rows.astype(int), 0, h - 1)
    ci = np.clip(cols.astype(int), 0, w - 1)
    t = img[ri][:, ci]
    t[(rows < 0) | (rows >= h)] = 0
    bg = np.array([0.22, 0.22, 0.22, 1.0], dtype=np.float32)
    a = t[..., 3:4]
    return t * a + bg * (1 - a)


def sheets(tags, u1, out):
    sc = bpy.context.scene
    sc.render.image_settings.file_format = "PNG"
    u1p = {k: next(iter(glob.glob(f"{u1}/*part_{k}.png"))) for k in "012"}
    crop = lambda a: a[:, 80:560]  # noqa: E731
    rows = [[u1_tile(u1p["0"], "0")] + [crop(load(f"{out}/{t}/sil_front.png")) for t in tags]
            + [u1_tile(u1p["1"], "1")] + [load(f"{out}/{t}/sil_side.png")[:, 160:480] for t in tags]]
    tg = "_".join(tags)
    grid(rows, f"{out}/silhouettes_u1_{tg}.png")
    for dist in (1, 3):
        grid([[load(f"{out}/{t}/turn_{dist}_{k}.png") for k in range(8)] for t in tags],
             f"{out}/turntable_{dist}m_{tg}.png")
    grid([[load(f"{out}/{t}/{c}_{k}.png") for c in ("Idle_Loop", "Walk_Loop") for k in range(4)] for t in tags],
         f"{out}/idle_walk_{tg}.png")
    grid([[load(f"{out}/{t}/{n}.png") for n in ("neck_0", "neck_1", "neck_2", "neck_3")] for t in tags],
         f"{out}/neck_weld_{tg}.png")
    grid([[load(f"{out}/{t}/{n}.png") for n in ("wrist_rest_0", "wrist_rest_1", "wrist_rest_2", "wrist_walk_0",
                                                 "wrist_walk_1")] for t in tags],
         f"{out}/wrist_{tg}.png")
    if all(os.path.exists(f"{out}/{t}/close_0.png") for t in tags):
        grid([[load(f"{out}/{t}/close_{k}.png") for k in range(4)] for t in tags], f"{out}/close_{tg}.png")
    if all(os.path.exists(f"{out}/{t}/foot_0.png") for t in tags):
        grid([[load(f"{out}/{t}/foot_{k}.png") for k in range(5)]
              + [load(f"{out}/{t}/foot_walk_{k}.png") for k in range(2)] for t in tags], f"{out}/feet_{tg}.png")


def main():
    p = argparse.ArgumentParser(prog="alien_cage_review.py")
    p.add_argument("--shots")
    p.add_argument("--tag")
    p.add_argument("--sheets", action="store_true")
    p.add_argument("--tags", default="first,cage")
    p.add_argument("--u1")
    p.add_argument("--out", required=True)
    a = p.parse_args(sys.argv[sys.argv.index("--") + 1:])
    os.makedirs(a.out, exist_ok=True)
    if a.shots:
        shots(a.shots, a.tag, a.out)
    if a.sheets:
        sheets(a.tags.split(","), a.u1, a.out)


if __name__ == "__main__":
    main()
