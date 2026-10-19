"""The M2 review sheets (art #196): the S9d look beside the normal-mapped M2 look, in Blender (Eevee) under a soft
studio light with a rim, beside the target paintover rf2.

  blender -b --factory-startup --python-exit-code 1 --python tools/blender/alien_detail_review.py -- \
      --character <M2/export/alien_character.blend> --rf2 <rf2.png> --out <M2/sheets> [--tile 420] \
      [--images <the parts build's export/, for the eye textures>]

Both looks are the same file and the same skin material (alien_hue's mask mix of the hue and its pale tint, times half
the baked AO, a soft roughness); the S9d look only unlinks the normal map. Pose: the first frame of the Idle clip.
Writes per shot `<shot>_s9d.png` and `<shot>_m2.png`, and:
- `face.png` (3 x 2 tiles): rf2 | S9d | M2 at the face's three-quarter view, 0.5 m; below an M2 close-up at 0.25 m |
  S9d | M2 from the front at 0.5 m;
- `body.png` (4 x 2): the left hand, the neck from the side, the neck from the three-quarter back, the full body at
  1.5 m; S9d above, M2 below;
- `close.png` (2 x 1): the cheek and eye at 0.18 m, S9d | M2, for the grain and the folds.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector


TEAL, PALE = (0.11, 0.48, 0.51), (0.86, 0.92, 0.81)  # sRGB, docs/godot.md S9 (sampled against rf2)


def args():
    p = argparse.ArgumentParser()
    p.add_argument("--character", required=True)
    p.add_argument("--rf2", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--tile", type=int, default=420)
    p.add_argument("--images", default="", help="the folder of the eye textures (alien_parts.py's export/)")
    return p.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])


def stage(sc):
    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = 32
    try:
        sc.eevee.use_shadows = True
        sc.eevee.use_raytracing = True
    except AttributeError:
        pass
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "None"
    sc.render.film_transparent = False
    w = bpy.data.worlds.new("studio")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.20, 0.21, 0.23, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35
    sc.world = w
    for name, loc, energy, size, col in (("key", (1.6, -2.2, 2.4), 150.0, 1.6, (1.0, 0.96, 0.9)),
                                         ("fill", (-2.2, -1.6, 1.5), 30.0, 2.5, (0.9, 0.95, 1.0)),
                                         ("rim", (-0.6, 2.4, 2.2), 240.0, 0.8, (0.92, 0.97, 1.0))):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy, ld.size, ld.color = energy, size, col
        lo = bpy.data.objects.new(name, ld)
        sc.collection.objects.link(lo)
        lo.location = loc
        lo.rotation_euler = (Vector((0, 0, 1.2)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    return cam


def skin(body):
    """alien_hue as the review's skin: its existing base colour times mix(1, ao, 0.5), roughness 0.55; returns the
    normal map link's two sockets (or None)."""
    mt = body.data.materials[0]
    nt = mt.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = 0.55
    base = bsdf.inputs["Base Color"]
    # the hue and its pale tint by the light mask (`masks` u), as alien_hue.gdshader (the accent left out)
    uvm = nt.nodes.new("ShaderNodeUVMap")
    uvm.uv_map = "masks"
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(uvm.outputs["UV"], sep.inputs["Vector"])
    hue = nt.nodes.new("ShaderNodeMix")
    hue.data_type = "RGBA"
    lin = lambda c: tuple(((x + 0.055) / 1.055) ** 2.4 for x in c) + (1.0,)  # noqa: E731
    sock = lambda node, name, kind, out=False: next(s for s in (node.outputs if out else node.inputs)  # noqa: E731
                                                    if s.name == name and s.type == kind)
    sock(hue, "A", "RGBA").default_value = lin(TEAL)
    sock(hue, "B", "RGBA").default_value = lin(PALE)
    nt.links.new(sep.outputs["X"], sock(hue, "Factor", "VALUE"))
    nt.links.new(sock(hue, "Result", "RGBA", True), base)
    if base.is_linked:
        src = base.links[0].from_socket
        ao = nt.nodes.new("ShaderNodeVertexColor")
        ao.layer_name = "ao"
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 0.5
        a_col = next(s for s in mix.inputs if s.name == "A" and s.type == "RGBA")  # not the float "A"
        b_col = next(s for s in mix.inputs if s.name == "B" and s.type == "RGBA")
        nt.links.new(src, a_col)
        nt.links.new(ao.outputs["Color"], b_col)
        nt.links.new(next(s for s in mix.outputs if s.type == "RGBA"), base)
    nl = bsdf.inputs["Normal"].links
    return (nl[0].from_socket, bsdf.inputs["Normal"]) if nl else None


def look(cam, target, direction, dist, lens):
    d = Vector(direction).normalized()
    cam.location = target + d * dist
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
    cam.data.clip_start = 0.01


def render(sc, path, px):
    sc.render.resolution_x = sc.render.resolution_y = px
    sc.render.resolution_percentage = 100
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def load(path, px):
    im = bpy.data.images.load(str(path))
    w, h = im.size
    a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)
    if w != h:  # centre square crop
        s = min(w, h)
        a = a[(h - s) // 2:(h - s) // 2 + s, (w - s) // 2:(w - s) // 2 + s]
        im2 = bpy.data.images.new("crop", s, s)
        im2.pixels.foreach_set(a.ravel())
        im = im2
    if im.size[0] != px:
        im.scale(px, px)
    return np.array(im.pixels[:], dtype=np.float32).reshape(px, px, 4)


def sheet(rows, path):
    """rows: lists of equally sized tiles (top row first) -> one PNG with 4 px gaps."""
    g = 4
    th, tw = rows[0][0].shape[:2]
    H = len(rows) * th + (len(rows) - 1) * g
    W = max(len(r) for r in rows) * tw + (max(len(r) for r in rows) - 1) * g
    out = np.full((H, W, 4), 0.06, dtype=np.float32)
    out[..., 3] = 1
    for i, r in enumerate(rows):
        for j, t in enumerate(r):
            y0 = H - (i + 1) * th - i * g  # Blender pixels: bottom row first
            out[y0:y0 + th, j * (tw + g):j * (tw + g) + tw] = t
    im = bpy.data.images.new(path.stem, W, H)
    im.pixels.foreach_set(out.ravel())
    im.filepath_raw = str(path)
    im.file_format = "PNG"
    im.save()


def main():
    a = args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=a.character)
    sc = bpy.context.scene
    body = bpy.data.objects["Body"]
    arm = body.find_armature()
    for im in bpy.data.images:  # the eye textures live beside the parts build (alien_parts.py's export/)
        if im.source == "FILE" and not im.has_data and a.images and (Path(a.images) / f"{im.name}.png").is_file():
            im.filepath = str(Path(a.images) / f"{im.name}.png")
            im.reload()
    for o in bpy.data.objects:
        if o.type == "MESH" and o is not body:
            o.hide_render = not o.name.startswith(("eye_bored_", "mouth_frog_rest"))
    idle = next((ac for ac in bpy.data.actions if ac.name.lower().split("|")[-1].startswith("idle")), None)
    print("M2 actions", [ac.name for ac in bpy.data.actions][:12], "idle", idle.name if idle else None, flush=True)
    if idle is not None:
        arm.animation_data_create()
        arm.animation_data.action = idle
        if hasattr(arm.animation_data, "action_slot") and idle.slots:
            arm.animation_data.action_slot = idle.slots[0]
        sc.frame_set(int(idle.frame_range[0]))
    bpy.context.view_layer.update()
    cam = stage(sc)
    link = skin(body)
    nt = body.data.materials[0].node_tree
    mw = arm.matrix_world
    pb = arm.pose.bones
    head = mw @ pb["Head"].head
    eyes = [o for o in bpy.data.objects if o.name.startswith("eye_bored_ball_")]
    eye_c = sum((o.matrix_world.translation for o in eyes), Vector()) / max(len(eyes), 1)
    face_c = Vector((head.x, eye_c.y, eye_c.z - 0.02))
    neck = mw @ pb["Neck"].head + Vector((0, 0, 0.05))
    hand = mw @ pb["LeftHand"].head
    hand_c = hand + (mw @ pb["LeftMiddleProximal"].head - hand) * 0.9
    cheek = [o for o in eyes if o.name.endswith("_L")]
    cheek_c = (cheek[0].matrix_world.translation if cheek else eye_c) + Vector((0.0, 0.0, -0.02))
    a34 = math.radians(35)
    shots = {
        "face34": (face_c + Vector((0, 0, -0.06)), (math.sin(a34), -math.cos(a34), 0.08), 0.5, 30),
        "face_front": (face_c, (0, -1, 0.05), 0.5, 40),
        "face_close": (face_c + Vector((0.01, 0, -0.01)), (math.sin(a34), -math.cos(a34), 0.05), 0.25, 45),
        "close": (cheek_c, (0.45, -1, 0.05), 0.18, 45),
        "hand": (hand_c, (0.9, -0.8, 0.15), 0.35, 40),
        "neck_side": (neck, (1, -0.15, 0.05), 0.5, 40),
        "neck_back34": (neck, (0.6, 0.8, 0.15), 0.5, 40),
        "body": (Vector((0, 0, 0.88)), (0.35, -1, 0.0), 1.5, 28),
    }
    for name, (t, d, dist, lens) in shots.items():
        px = a.tile * 2 if name == "close" else a.tile
        look(cam, t, d, dist, lens)
        for tag in ("s9d", "m2"):
            if link:
                if tag == "s9d":
                    for lk in list(link[1].links):
                        nt.links.remove(lk)
                else:
                    nt.links.new(link[0], link[1])
            render(sc, out / f"{name}_{tag}.png", px)
        print(f"M2 shot {name}", flush=True)
    T = a.tile
    L = lambda n: load(out / f"{n}.png", T)  # noqa: E731
    rf2 = load(Path(a.rf2), T)
    sheet([[rf2, L("face34_s9d"), L("face34_m2")], [L("face_close_m2"), L("face_front_s9d"), L("face_front_m2")]],
          out / "face.png")
    T4 = int(T * 0.75)
    L4 = lambda n: load(out / f"{n}.png", T4)  # noqa: E731
    sheet([[L4(f"{s}_s9d") for s in ("hand", "neck_side", "neck_back34", "body")],
           [L4(f"{s}_m2") for s in ("hand", "neck_side", "neck_back34", "body")]], out / "body.png")
    C = lambda n: load(out / f"{n}.png", T * 3 // 2)  # noqa: E731
    sheet([[C("close_s9d"), C("close_m2")]], out / "close.png")
    print("M2 SHEETS " + str(out), flush=True)


if __name__ == "__main__":
    main()
