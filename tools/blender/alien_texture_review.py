"""The M3a review sheets (art #196): M2's look (the flat mask colours, half the vertex AO, roughness 0.55, the normal
map) beside the authored texture set, in Blender (Eevee, AgX) under light D (docs/godot.md, "Light D": the key, fill,
back and rim directional lights of look_presets.json, turned into Blender's axes), beside the target paintover rf2.

Runs in background Blender through the runner, never by hand and never in a window:
tools/runner/blender.py's run_script("alien_texture_review.py", args) with args
      --character <M2/export/alien_character.blend> --tex <M3a/textures> --normal <M3a/bake/normal.png> \
      --rf2 <rf2.png> --out <M3a/sheets> [--images <the parts build's export/>] [--tile 420] [--sss 0] \
      [--grid <variants dir> --names a,b,c] [--before-tex <M3a/textures> --before-normal <normal.png>]       [--labels m3a,m3c]

Shots (alien_detail_review's framings), the Idle clip's first frame: face34 (0.5 m), face_front, face_close (0.25 m),
near (the face at 3/4 from 0.6 m with a 70 mm lens, M3c: the showroom's close view), close (cheek and eye at 0.18 m),
hand, knee (M3c: the accent spot), neck_back34, body (1.5 m). Writes `<shot>_m2.png`, `<shot>_m3a.png` and:
- `face.png`: rf2 | M2 | M3a at face34; below M3a face_close | M2 face_front | M3a face_front;
- `close.png`: the cheek and eye, M2 | M3a;
- `body.png`: hand, neck_back34, body; M2 above, M3a below.
--grid: only the variants (each a folder of albedo.png and orm.png, in --names order) at --shots (default face34,
face_close, body), one column per variant, into `grid.png` (rf2 first in the top row's place of a label-less sheet: the column order
is printed and written to grid.json).
--sss k: the review's subsurface weight from sss.png times k (0: none, as a plain glTF viewer shows it).
--before-tex (M3c): the left side is that texture set (with --before-normal) instead of M2's look; --labels names the
two sides in the file names (default m2,m3a).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_detail_review as R  # noqa: E402
import alien_texture as X  # noqa: E402

# light D (look_presets.json, Godot model space: y up, the character faces +z) -> Blender (x, -z, y)
LIGHTS = (("key", (-2.0, 3.2, 3.0), 3.0, 0.6, True, (1.0, 0.97, 0.92)),
          ("fill", (3.0, 1.6, 2.0), 0.12, 0.0, False, (0.92, 0.96, 1.0)),
          ("back", (0.5, 2.5, -3.0), 0.30, 0.0, False, (1.0, 1.0, 1.0)),
          ("rim", (0.7, 1.6, -2.8), 3.0, 0.5, False, (0.95, 0.98, 1.0)))
AMBIENT = ((0.42, 0.43, 0.46, 1.0), 0.5)  # the grey of light D's Godot proofs (lightD/final.png), half strength
# Godot's directional energy E lights a white surface facing it to about E; Blender's sun strength S to S / pi
# (Lambert's 1 / pi): at E alone the face rendered grey and the irises black, at E * pi the lit teal washed out
# beside rf2 under Blender's AgX; E * 2.5 sits between
SUN_SCALE = 2.5


def args():
    p = argparse.ArgumentParser()
    p.add_argument("--character", required=True)
    p.add_argument("--tex", required=True)
    p.add_argument("--normal", required=True)
    p.add_argument("--rf2", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--images", default="")
    p.add_argument("--tile", type=int, default=420)
    p.add_argument("--sss", type=float, default=0.0)
    p.add_argument("--grid", default="")
    p.add_argument("--names", default="")
    p.add_argument("--shots", default="face34,face_close,body", help="--grid: the rows")
    p.add_argument("--before-tex", default="", help="the left side's texture set instead of M2's look")
    p.add_argument("--before-normal", default="")
    p.add_argument("--labels", default="m2,m3a", help="the two sides' names in the file names")
    return p.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])


def stage_d(sc):
    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = 48
    for k in ("use_shadows", "use_raytracing"):
        if hasattr(sc.eevee, k):
            setattr(sc.eevee, k, True)
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = math.log2(0.9)
    w = bpy.data.worlds.new("studio")
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value, bg.inputs["Strength"].default_value = AMBIENT
    sc.world = w
    target = Vector((0.0, 0.0, 0.9))
    for name, (gx, gy, gz), energy, spec, shadow, col in LIGHTS:
        ld = bpy.data.lights.new(name, "SUN")
        ld.energy, ld.color, ld.specular_factor, ld.use_shadow = energy * SUN_SCALE, col, spec, shadow
        ld.angle = math.radians(2.0)
        lo = bpy.data.objects.new(name, ld)
        sc.collection.objects.link(lo)
        lo.location = Vector((gx, -gz, gy)) + target
        lo.rotation_euler = (target - lo.location).to_track_quat("-Z", "Y").to_euler()
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    return cam


def m3a_material(body, tex, normal, sss, name="alien_hue_m3a"):
    orig = body.data.materials[0]
    m3 = orig.copy()
    m3.name = name
    body.data.materials[0] = m3
    X.texture_skin(body, Path(tex), Path(normal), name)
    nt = m3.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    if sss > 0:
        img = bpy.data.images.load(str(Path(tex) / "sss.png"))
        img.colorspace_settings.name = "Non-Color"
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = img
        uv = nt.nodes.new("ShaderNodeUVMap")
        uv.uv_map = X.UV_LAYER
        nt.links.new(uv.outputs["UV"], node.inputs["Vector"])
        mul = nt.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = sss
        nt.links.new(node.outputs["Color"], mul.inputs[0])
        nt.links.new(mul.outputs[0], bsdf.inputs["Subsurface Weight"])
        bsdf.inputs["Subsurface Radius"].default_value = (1.0, 0.45, 0.3)
        bsdf.inputs["Subsurface Scale"].default_value = 0.006
    body.data.materials[0] = orig
    return m3


def setup(a):
    bpy.ops.wm.open_mainfile(filepath=a.character)
    sc = bpy.context.scene
    body = bpy.data.objects["Body"]
    arm = body.find_armature()
    for im in bpy.data.images:
        if im.source == "FILE" and not im.has_data and a.images and (Path(a.images) / f"{im.name}.png").is_file():
            im.filepath = str(Path(a.images) / f"{im.name}.png")
            im.reload()
    for o in bpy.data.objects:
        if o.type == "MESH" and o is not body:
            o.hide_render = not o.name.startswith(("eye_bored_", "mouth_frog_rest"))
    idle = next((ac for ac in bpy.data.actions if ac.name.lower().split("|")[-1].startswith("idle")), None)
    if idle is not None:
        arm.animation_data_create()
        arm.animation_data.action = idle
        if hasattr(arm.animation_data, "action_slot") and idle.slots:
            arm.animation_data.action_slot = idle.slots[0]
        sc.frame_set(int(idle.frame_range[0]))
    bpy.context.view_layer.update()
    cam = stage_d(sc)
    m3 = m3a_material(body, a.tex, a.normal, a.sss)
    orig = body.data.materials[0]
    if a.before_tex:  # the left side: another texture set (M3c: M3a's)
        orig = m3a_material(body, a.before_tex, a.before_normal or a.normal, a.sss, "alien_hue_before")
    else:
        R.skin(body)  # the M2 look, on the original material
    mw = arm.matrix_world
    pb = arm.pose.bones
    head = mw @ pb["Head"].head
    eyes = [o for o in bpy.data.objects if o.name.startswith("eye_bored_ball_")]
    eye_c = sum((o.matrix_world.translation for o in eyes), Vector()) / max(len(eyes), 1)
    face_c = Vector((head.x, eye_c.y, eye_c.z - 0.02))
    neck = mw @ pb["Neck"].head + Vector((0, 0, 0.05))
    hand = mw @ pb["LeftHand"].head
    hand_c = hand + (mw @ pb["LeftMiddleProximal"].head - hand) * 0.9
    knee = mw @ pb["LeftLowerLeg"].head if "LeftLowerLeg" in pb else Vector((0.1, 0, 0.5))
    cheek = [o for o in eyes if o.name.endswith("_L")]
    cheek_c = (cheek[0].matrix_world.translation if cheek else eye_c) + Vector((0.0, 0.0, -0.02))
    a34 = math.radians(35)
    shots = {
        "face34": (face_c + Vector((0, 0, -0.06)), (math.sin(a34), -math.cos(a34), 0.08), 0.5, 30),
        "face_front": (face_c, (0, -1, 0.05), 0.5, 40),
        "face_close": (face_c + Vector((0.01, 0, -0.01)), (math.sin(a34), -math.cos(a34), 0.05), 0.25, 45),
        "near": (face_c + Vector((0, 0, -0.03)), (math.sin(a34), -math.cos(a34), 0.08), 0.6, 70),
        "knee": (knee, (0.5, -1, 0.1), 0.45, 45),
        "close": (cheek_c, (0.45, -1, 0.05), 0.18, 45),
        "hand": (hand_c, (0.9, -0.8, 0.15), 0.35, 40),
        "neck_back34": (neck, (0.6, 0.8, 0.15), 0.5, 40),
        "body": (Vector((0, 0, 0.88)), (0.35, -1, 0.0), 1.5, 28),
    }
    return sc, cam, body, orig, m3, shots


def grid(a, sc, cam, body, m3, shots, out):
    names = [n for n in a.names.split(",") if n]
    nt = m3.node_tree
    body.data.materials[0] = m3
    T = a.tile
    cols = {}
    for n in names:
        d = Path(a.grid) / n
        for node, f in (("alien_skin_albedo", "albedo.png"), ("alien_skin_orm", "orm.png")):
            img = nt.nodes[node].image
            img.filepath = str(d / f)
            img.reload()
        tiles = []
        for s in a.shots.split(","):
            t, dd, dist, lens = shots[s]
            R.look(cam, t, dd, dist, lens)
            p = out / "grid" / f"{s}_{n}.png"
            R.render(sc, p, T)
            tiles.append(R.load(p, T * 2 // 3 if len(names) > 4 else T))
        cols[n] = tiles
        X.log(f"grid {n}")
    tt = T * 2 // 3 if len(names) > 4 else T
    rf2 = R.load(Path(a.rf2), tt)
    rows = [[rf2] + [cols[n][i] for n in names] if i == 0 else [rf2 * 0 + 0.06] + [cols[n][i] for n in names]
            for i in range(len(a.shots.split(",")))]
    R.sheet(rows, out / "grid.png")
    (out / "grid.json").write_text(json.dumps({"columns": ["rf2"] + names, "rows": a.shots.split(",")}),
                                   encoding="utf-8", newline="\n")
    X.log("GRID " + str(out / "grid.png") + " columns rf2," + ",".join(names))


def main():
    a = args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sc, cam, body, orig, m3, shots = setup(a)
    if a.grid:
        (out / "grid").mkdir(exist_ok=True)
        grid(a, sc, cam, body, m3, shots, out)
        return
    lb, la = a.labels.split(",")
    for name, (t, d, dist, lens) in shots.items():
        px = a.tile * 2 if name == "close" else a.tile
        R.look(cam, t, d, dist, lens)
        for tag, mt in ((lb, orig), (la, m3)):
            body.data.materials[0] = mt
            R.render(sc, out / f"{name}_{tag}.png", px)
        X.log(f"shot {name}")
    T = a.tile
    L = lambda n: R.load(out / f"{n}.png", T)  # noqa: E731
    R.sheet([[R.load(Path(a.rf2), T), L(f"face34_{lb}"), L(f"face34_{la}")],
             [L(f"near_{la}"), L(f"face_front_{lb}"), L(f"face_front_{la}")]], out / "face.png")
    C = lambda n: R.load(out / f"{n}.png", T * 3 // 2)  # noqa: E731
    R.sheet([[C(f"near_{lb}"), C(f"near_{la}")], [C(f"close_{lb}"), C(f"close_{la}")]], out / "close.png")
    B = lambda n: R.load(out / f"{n}.png", T)  # noqa: E731
    R.sheet([[B(f"{s}_{lb}") for s in ("hand", "knee", "neck_back34", "body")],
             [B(f"{s}_{la}") for s in ("hand", "knee", "neck_back34", "body")]], out / "body.png")
    X.log("SHEETS " + str(out))


if __name__ == "__main__":
    main()
