"""Review images of a refitted alien body against its concept (art #196, the A body's refit route): Workbench renders
with studio light on a mid-grey ground, stitched with numpy.

    blender -b --factory-startup --python-exit-code 1 --python tools/blender/alien_body_refit_review.py -- \
        --blend <alien_body.blend> --out <dir> [--concept <turnaround.png> --bands <bands.json>] [--only turn]

Writes into <out>:
- turnaround.png: 8 views (every 45 degrees from the front) in an A-pose (the upper arms lowered by ARM_DOWN), 1280 px;
- compare.png (with --concept and --bands, the measure of alien_body_measure.py): front and side, the concept's
  silhouette at the body's scale (its sole on z = 0, its px_m), the body's, and both overlaid (white both, blue the
  concept only, red the body only), below the ring only (the head is drawn at its own scale);
- close_*.png, about 1 Mpx each, in the rest pose: both hands' backs (from above) and palms (from below), both feet
  from the side, top and front, the neck-shoulder join from the front, side and back, the crotch from the front and
  back, both armpits; and close_sheet.png, all of them at 320 px for an agent. H1 added: each hand from its thumb
  side, the crotch from behind and below, both knees (front and side), both elbows (front and below), the armpits
  framed closer, the hands framed back to the wrist;
- with --fingers, fingers.png: the left hand at rest and with each finger chain (Index, Middle, Ring, Little, Thumb)
  curled alone by FINGER_CURL degrees at every joint, about the axis across the finger and the palm's normal (the
  fingers bend one at a time without dragging their neighbours).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

ARM_DOWN = math.radians(72)
FINGER_CURL = 60.0  # degrees per joint in fingers.png
BODY_RGB = (0.16, 0.42, 0.40)


def setup(res):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light, sh.color_type = "STUDIO", "MATERIAL"
    sh.show_specular_highlight, sh.show_shadows, sh.show_cavity = True, True, False
    sc.render.film_transparent = False
    sc.world = sc.world or bpy.data.worlds.new("w")
    sc.world.color = (0.35, 0.35, 0.36)
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    cam = bpy.data.objects.new("ReviewCam", bpy.data.cameras.new("ReviewCam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    return sc, cam


def look(cam, loc, target, ortho=None, lens=50):
    cam.location = Vector(loc)
    d = Vector(target) - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    cam.data.type = "ORTHO" if ortho else "PERSP"
    if ortho:
        cam.data.ortho_scale = ortho
    cam.data.lens = lens
    cam.data.clip_start = 0.01


def shot(sc, path, res=None):
    if res:
        sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def load(path):
    img = bpy.data.images.load(path)
    a = np.array(img.pixels[:], dtype=np.float32).reshape(img.size[1], img.size[0], 4)[::-1]
    bpy.data.images.remove(img)
    return a


def save(arr, path):
    h, w = arr.shape[:2]
    img = bpy.data.images.new("out", w, h, alpha=True)
    rgba = np.ones((h, w, 4), np.float32)
    rgba[..., :arr.shape[2]] = arr[..., :4] if arr.shape[2] >= 4 else arr
    img.pixels = rgba[::-1].ravel().tolist()
    img.filepath_raw, img.file_format = path, "PNG"
    img.save()
    bpy.data.images.remove(img)


def stitch(paths, cols, out, cell=None):
    ims = [load(p) for p in paths]
    if cell:
        ims = [resize(i, cell) for i in ims]
    h, w = ims[0].shape[:2]
    rows = (len(ims) + cols - 1) // cols
    sheet = np.ones((rows * h, cols * w, 4), np.float32)
    for k, im in enumerate(ims):
        r, c = divmod(k, cols)
        sheet[r * h:(r + 1) * h, c * w:(c + 1) * w] = im[:h, :w]
    save(sheet, out)


def resize(im, size):
    w, h = size
    ys = (np.arange(h) * im.shape[0] / h).astype(int)
    xs = (np.arange(w) * im.shape[1] / w).astype(int)
    return im[ys][:, xs]


def a_pose(arm, amount):
    bpy.context.view_layer.update()
    for side, sgn in (("Left", 1), ("Right", -1)):
        pb = arm.pose.bones[f"{side}UpperArm"]
        h = arm.matrix_world @ pb.head
        rot = Matrix.Translation(h) @ Matrix.Rotation(sgn * amount, 4, "Y") @ Matrix.Translation(-h)
        pb.matrix = arm.matrix_world.inverted() @ rot @ arm.matrix_world @ pb.matrix
        bpy.context.view_layer.update()


def rest(arm):
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


def concept_panel(png, panel, px_m, sole_row, mpp, size, z_top, cx_world, body_mask):
    """The concept's silhouette (one panel of the turnaround) resampled onto the render's grid: px_m metres per
    concept pixel below the ring, the sole on sole_row; x aligned so the trunk rows' centroids match the body's."""
    im = load(png)
    pw = im.shape[1] // 3
    sub = im[:, panel * pw:(panel + 1) * pw, :3]
    bg = np.median(np.stack([sub[2, 45], sub[2, pw - 25], sub[-3, 45], sub[-3, pw - 25]]), axis=0)
    m = np.abs(sub - bg).sum(-1) > 38 / 255
    m[:, :40] = False
    m[:, pw - 20:] = False
    W, H = size
    out = np.zeros((H, W), bool)
    zs = z_top - (np.arange(H) + 0.5) * mpp
    rows = np.clip(np.round(sole_row - zs / px_m).astype(int), 0, m.shape[0] - 1)
    xs_m = (np.arange(W) + 0.5 - W / 2) * mpp + cx_world
    # centroid alignment over the trunk's rows (z 0.9 .. 1.2 m)
    sel = (zs > 0.9) & (zs < 1.2)
    bc = np.mean([np.mean(np.nonzero(body_mask[i])[0]) for i in np.nonzero(sel)[0] if body_mask[i].any()])
    cc = np.mean([np.mean(np.nonzero(m[r])[0]) for r in rows[sel] if m[r].any()])
    cols = np.round(cc + (np.arange(W) - bc) * mpp / px_m).astype(int)
    ok = (cols >= 0) & (cols < pw)
    for i in range(H):
        out[i, ok] = m[rows[i], cols[ok]]
    return out, xs_m


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--blend", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--concept", default="")
    p.add_argument("--bands", default="")
    p.add_argument("--only", default="", help="turn: the turnaround only")
    p.add_argument("--fingers", action="store_true", help="H1: fingers.png, each finger curled alone")
    a = p.parse_args(sys.argv[sys.argv.index("--") + 1:])
    os.makedirs(a.out, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=a.blend)
    for o in bpy.data.objects:
        if o.type == "MESH" and o.name.startswith("BodyCage"):
            o.hide_render = True
    arm = bpy.data.objects["CharacterArmature"]
    meshes = [o for o in bpy.data.objects if o.type == "MESH" and not o.hide_render]
    for o in meshes:
        for m in o.data.materials:
            if m and "eye" not in m.name.lower():
                m.diffuse_color = (*BODY_RGB, 1.0)
    sc, cam = setup((320, 560))
    gm = bpy.data.materials.new("Ground")
    gm.diffuse_color = (0.42, 0.42, 0.42, 1.0)
    bpy.ops.mesh.primitive_plane_add(size=8, location=(0, 0, 0))
    ground = bpy.context.active_object
    ground.data.materials.append(gm)
    tmp = os.path.join(a.out, "_tmp")
    os.makedirs(tmp, exist_ok=True)
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    top = max((o.evaluated_get(deps).matrix_world @ v.co).z for o in meshes
              for v in o.evaluated_get(deps).to_mesh().vertices)
    a_pose(arm, ARM_DOWN)
    # 1. The turnaround.
    paths = []
    for k in range(8):
        ang = math.radians(45 * k)
        look(cam, (-6 * math.sin(ang), -6 * math.cos(ang), top / 2), (0, 0, top / 2), ortho=top * 1.12)
        paths.append(shot(sc, os.path.join(tmp, f"turn_{k}.png"), (320, 560)))
    stitch(paths, 4, os.path.join(a.out, "turnaround.png"))
    if a.only == "turn":
        return
    # 2. The concept comparison (front and side, at the body's scale, below the ring).
    if a.concept and a.bands:
        with open(a.bands, encoding="utf-8") as fh:
            bands = json.load(fh)
        px_m, sole, ring_z = bands["px_m"], bands["rows"]["sole"], bands["z"]["ring"]
        S, z_top, span = 640, 2.0, 2.04
        mpp = span / S
        ground.hide_render = True
        sc.render.film_transparent = True
        tiles = []
        for name, panel, loc in (("front", 0, (0, -6, 0)), ("side", 1, (-6, 0, 0))):
            look(cam, (loc[0], loc[1], z_top - span / 2), (0, 0, z_top - span / 2), ortho=span)
            im = load(shot(sc, os.path.join(tmp, f"cmp_{name}.png"), (S, S)))
            bm = im[..., 3] > 0.5
            cm, _ = concept_panel(a.concept, panel, px_m, sole, mpp, (S, S), z_top, 0.0, bm)
            zs = z_top - (np.arange(S) + 0.5) * mpp
            above = zs > ring_z
            cm[above], bm2 = False, bm.copy()
            bm2[above] = False
            grey = np.full((S, S, 4), 0.42, np.float32)
            grey[..., 3] = 1
            c_img = grey.copy()
            c_img[cm, :3] = (0.75, 0.9, 0.85)
            b_img = grey.copy()
            b_img[..., :3] = im[..., :3] * im[..., 3:4] + grey[..., :3] * (1 - im[..., 3:4])
            ov = grey.copy()
            ov[cm & bm2, :3] = 0.95
            ov[cm & ~bm2, :3] = (0.2, 0.4, 1.0)
            ov[~cm & bm2, :3] = (1.0, 0.25, 0.2)
            r = int(round((z_top - ring_z) / mpp))
            for t in (c_img, b_img, ov):
                t[r, :, :3] = (1.0, 1.0, 0.0)
            tiles.append(np.concatenate([c_img, b_img, ov], axis=1))
            inter, union = (cm & bm2).sum(), (cm | bm2).sum()
            print(f"COMPARE {name} iou={inter / max(union, 1):.3f} concept_only={(cm & ~bm2).sum()} "
                  f"body_only={(~cm & bm2).sum()}", flush=True)
        sheet = np.concatenate(tiles, axis=0)
        save(resize(sheet, (1280, int(sheet.shape[0] * 1280 / sheet.shape[1]))), os.path.join(a.out, "compare.png"))
        ground.hide_render = False
        sc.render.film_transparent = False
    # 3. Close-ups in the rest pose.
    rest(arm)
    bones = {b.name: arm.matrix_world @ b.head_local for b in arm.data.bones}
    tails = {b.name: arm.matrix_world @ b.tail_local for b in arm.data.bones}
    close = []
    R = (1024, 1024)

    def cl(name, loc, target, lens=50):
        look(cam, loc, target, lens=lens)
        close.append(shot(sc, os.path.join(a.out, f"close_{name}.png"), R))
    for side, sgn in (("Left", 1), ("Right", -1)):
        hc = (bones[f"{side}Hand"] + bones[f"{side}MiddleDistal"]) / 2
        hc.x -= sgn * 0.01  # H1: framed back to the wrist
        cl(f"hand_{side.lower()}_back", hc + Vector((0, 0.05, 0.6)), hc, 55)
        cl(f"hand_{side.lower()}_palm", hc + Vector((0, 0.05, -0.6)), hc, 55)
        cl(f"hand_{side.lower()}_side", hc + Vector((0, -0.6, -0.08)), hc, 55)
    for side, sgn in (("Left", 1), ("Right", -1)):
        fc = (bones[f"{side}Foot"] + bones[f"{side}Toes"]) / 2
        fc.z = 0.05
        cl(f"foot_{side.lower()}_side", fc + Vector((sgn * 0.7, -0.05, 0.12)), fc, 60)
    mid = Vector((0, (bones["LeftFoot"].y + bones["LeftToes"].y) / 2 - 0.03, 0.05))
    cl("feet_top", mid + Vector((0, -0.25, 0.9)), mid, 50)
    cl("feet_front", mid + Vector((0, -0.95, 0.18)), mid, 50)
    nz = bones["Neck"].z
    nk = Vector((0, bones["Neck"].y, nz - 0.03))
    cl("neck_front", nk + Vector((0, -0.85, 0.08)), nk, 50)
    cl("neck_side", nk + Vector((0.85, 0, 0.08)), nk, 50)
    cl("neck_back", nk + Vector((0, 0.85, 0.08)), nk, 50)
    cz = bones["LeftUpperLeg"].z - 0.05
    cr = Vector((0, 0.03, cz))
    cl("crotch_front", cr + Vector((0, -0.8, -0.15)), cr, 50)
    cl("crotch_back", cr + Vector((0, 0.8, -0.15)), cr, 50)
    cl("crotch_below", cr + Vector((0, 0.45, -0.7)), cr, 50)
    for side, sgn in (("Left", 1), ("Right", -1)):
        ap = bones[f"{side}UpperArm"] + Vector((-sgn * 0.02, 0.0, -0.07))
        cl(f"armpit_{side.lower()}", ap + Vector((sgn * 0.18, -0.55, -0.25)), ap, 60)
    for side, sgn in (("Left", 1), ("Right", -1)):
        kn = bones[f"{side}LowerLeg"]
        cl(f"knee_{side.lower()}_front", kn + Vector((0, -0.7, 0.05)), kn, 60)
        cl(f"knee_{side.lower()}_side", kn + Vector((sgn * 0.7, 0, 0.05)), kn, 60)
    for side, sgn in (("Left", 1), ("Right", -1)):
        el = bones[f"{side}LowerArm"]
        cl(f"elbow_{side.lower()}_front", el + Vector((0, -0.7, 0.05)), el, 60)
        cl(f"elbow_{side.lower()}_below", el + Vector((0, 0.05, -0.7)), el, 60)
    stitch(close, 5, os.path.join(a.out, "close_sheet.png"), cell=(256, 256))
    print("REVIEW done", len(close), "close-ups", flush=True)
    if a.fingers:
        fingers(arm, cam, sc, a.out, bones, tails)


def fingers(arm, cam, sc, out, bones, tails):
    """H1: the left hand at rest, then each finger chain curled alone (FINGER_CURL at every joint) about the axis
    across its proximal bone and the palm's normal (-Z in the T-pose), seen from the thumb side and a little below."""
    hc = (bones["LeftHand"] + bones["LeftMiddleDistal"]) / 2
    shots = []
    look(cam, hc + Vector((0.05, -0.5, -0.22)), hc, lens=60)
    shots.append(shot(sc, os.path.join(out, "finger_rest.png"), (768, 768)))
    for f in ("Index", "Middle", "Ring", "Little", "Thumb"):
        chain = [f"Left{f}{s}" for s in (("Metacarpal", "Proximal", "Distal") if f == "Thumb"
                                         else ("Proximal", "Intermediate", "Distal"))]
        chain = [n for n in chain if n in arm.pose.bones]
        d = (tails[chain[0]] - bones[chain[0]]).normalized()
        axis = d.cross(Vector((0.0, 0.0, -1.0))).normalized()
        for pb in arm.pose.bones:
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = (1, 0, 0, 0)
        for n in chain:
            b = arm.data.bones[n]
            loc_axis = (b.matrix_local.to_3x3().inverted() @ axis).normalized()
            arm.pose.bones[n].rotation_quaternion = Quaternion(loc_axis, math.radians(FINGER_CURL))
        bpy.context.view_layer.update()
        shots.append(shot(sc, os.path.join(out, f"finger_{f.lower()}.png"), (768, 768)))
    for pb in arm.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
    stitch(shots, 3, os.path.join(out, "fingers.png"), cell=(512, 512))
    print("REVIEW fingers", len(shots), flush=True)


if __name__ == "__main__":
    main()
