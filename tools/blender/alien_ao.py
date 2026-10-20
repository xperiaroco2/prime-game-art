"""The alien's baked ambient occlusion (art #196, S9): the soft shade in the creases of the release-look paintover
(under the lids, around the lips, under the jaw, at the neck) baked into the skin's vertices, so Godot and three.js
show the same.

  blender -b --factory-startup --python-exit-code 1 --python tools/blender/alien_ao.py -- \
      --character <mouths/build/alien_character.blend> --out <S9/cage/ao>

The method: Cycles bakes AO (distance AO["distance"], AO["samples"] samples) into a float colour attribute `ao` on the
Point domain of the skin mesh (`Body`, the welded body and head), in the rest pose, with every part hidden (M9: no
eye, no mouth piece, no crest), so the skin's AO is the Body's own shape (sockets, creases, nostrils) and fits every
eye and mouth design; each part's shade on the skin is its design's contact channel (alien_m6.py). The raw values are lifted by AO["floor"] (no black creases) and smoothed over the
mesh once. The GLB is exported again with the attribute as glTF COLOR_0 (grey, linear), which three.js multiplies into
the base colour by itself and alien_hue.gdshader reads as COLOR.r. Writes build/alien_character.blend,
export/alien_character.glb (with character.json and the mouths' atlases copied beside it) and build_report.json.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_glb  # noqa: E402

AO = {"distance": 0.06, "samples": 96, "floor": 0.18, "smooth": 1}
REST_UV = ("rest_xy", "rest_zn")  # S9b: TEXCOORD_2 and TEXCOORD_3 (rest_coords)
# M7: no mouth piece. With the frog rest piece in the bake the skin under it baked to about 0.3 (0.03 in the
# 2K map), and every other mouth piece, smaller than frog rest, showed that skin as a black strip beside it
# (art #196); the lips' own shade on the skin is the per-design contact field (alien_m6.py, TEXCOORD_5).
# M9 (brief UPDATE 8): no eye either, since more eye designs come; the eyes' shade is TEXCOORD_4's channels.
SHOWN = ()  # M9 (UPDATE 8): no part occludes the skin in the bake, only the Body's own shape
# S9c: the band under the jaw. The jaw's overhang shades the top of the throat into a grey band that made the throat's
# join into the jaw look dirty (S9, S9b); rf2 keeps only a faint shade there. Over the front of the neck (within
# "deg" degrees of the front around the neck ring's axis, soft), from z[0..1] up to z[2..3] (m) and within "r" of the
# axis (the jaw's underside included), the AO is lifted by "lift" toward 1.
JAW_LIFT = {"lift": 0.7, "deg": (60.0, 100.0), "z": (1.36, 1.39, 1.445, 1.475), "r": (0.13, 0.15)}


def args():
    p = argparse.ArgumentParser()
    p.add_argument("--character", required=True)
    p.add_argument("--out", required=True)
    return p.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])


def rest_coords(me):
    """S9b: the skin's rest-pose position and normal in two extra UV layers, so alien_hue.gdshader's gradient and grain
    stay on the skin in motion (Godot's VERTEX in vertex() is already skinned; three.js's `position` is the rest pose
    and needs none of this). In glTF axes (x, z, -y of Blender): REST_UV[0] = (x, y), REST_UV[1] = (z, the normal's
    z + 2; never under 1, so a part without the layers, read as 0, falls back to VERTEX). The exporter writes
    1 - v, so v is stored flipped here. Exported as TEXCOORD_2 and TEXCOORD_3; Godot imports them as CUSTOM0 (RGBA)."""
    n = len(me.vertices)
    co = np.empty(n * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    nr = np.empty(n * 3)
    me.vertex_normals.foreach_get("vector", nr)
    nr = nr.reshape(-1, 3)
    gl = np.stack([co[:, 0], co[:, 2], -co[:, 1]], 1)
    ngl_z = -nr[:, 1]
    lv = np.empty(len(me.loops), dtype=np.int64)
    me.loops.foreach_get("vertex_index", lv)
    for name in REST_UV:
        if name in me.uv_layers:
            me.uv_layers.remove(me.uv_layers[name])
    vals = {REST_UV[0]: (gl[:, 0], gl[:, 1]), REST_UV[1]: (gl[:, 2], ngl_z + 2.0)}
    for name in REST_UV:
        layer = me.uv_layers.new(name=name)
        u, v = vals[name]
        uv = np.stack([u[lv], 1.0 - v[lv]], 1).astype(np.float32).ravel()
        layer.data.foreach_set("uv", uv)
    return {"layers": list(REST_UV), "uv_layers": [u.name for u in me.uv_layers], "y_range": [round(float(gl[:, 1].min()), 3),
            round(float(gl[:, 1].max()), 3)]}


def _ss(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def jaw_mask(co, ring):
    """S9c: JAW_LIFT's weight per vertex (Blender axes, rest pose)."""
    cx, cy = ring["centre"]
    dx, dy = co[:, 0] - cx, co[:, 1] - cy
    deg = np.degrees(np.abs(np.arctan2(dx, -dy)))
    z = co[:, 2]
    J = JAW_LIFT
    return ((1 - _ss(*J["deg"], deg)) * _ss(J["z"][0], J["z"][1], z) * (1 - _ss(J["z"][2], J["z"][3], z))
            * (1 - _ss(*J["r"], np.hypot(dx, dy))))


def main():
    a = args()
    out = Path(a.out)
    (out / "build").mkdir(parents=True, exist_ok=True)
    (out / "export").mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=a.character)
    src_cj = json.loads((Path(a.character).parent.parent / "export" / "character.json").read_text(encoding="utf-8"))
    ring = src_cj["report"]["ring"]
    sc = bpy.context.scene
    body = bpy.data.objects["Body"]
    arm = body.find_armature()
    if arm is not None:
        arm.data.pose_position = "REST"
    hidden = {}
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        show = o is body or o.name.startswith(SHOWN)
        hidden[o.name] = o.hide_render
        o.hide_render = not show
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = AO["samples"]
    if sc.world is None:
        sc.world = bpy.data.worlds.new("w")
    sc.world.light_settings.distance = AO["distance"]
    me = body.data
    if "ao" in me.color_attributes:
        me.color_attributes.remove(me.color_attributes["ao"])
    attr = me.color_attributes.new("ao", "FLOAT_COLOR", "POINT")
    me.color_attributes.active_color = attr
    me.color_attributes.render_color_index = me.color_attributes.find("ao")
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    res = bpy.ops.object.bake(type="AO", target="VERTEX_COLORS")
    if res != {"FINISHED"}:
        raise SystemExit(f"bake: {res}")
    n = len(me.vertices)
    col = np.empty(n * 4, dtype=np.float32)
    attr.data.foreach_get("color", col)
    raw = col.reshape(-1, 4)[:, 0].astype(np.float64)
    v = AO["floor"] + (1 - AO["floor"]) * raw
    co = np.empty(n * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    jaw = jaw_mask(co, ring)
    jaw_before = float(v[jaw > 0.5].mean()) if (jaw > 0.5).any() else None
    v = v + JAW_LIFT["lift"] * jaw * (1 - v)
    ed = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get("vertices", ed)
    ed = ed.reshape(-1, 2)
    deg = np.bincount(ed.ravel(), minlength=n).astype(float)
    deg[deg == 0] = 1
    for _ in range(AO["smooth"]):
        s = np.zeros(n)
        np.add.at(s, ed[:, 0], v[ed[:, 1]])
        np.add.at(s, ed[:, 1], v[ed[:, 0]])
        v = 0.5 * v + 0.5 * s / deg
    out_col = np.stack([v, v, v, np.ones(n)], 1).astype(np.float32).ravel()
    attr.data.foreach_set("color", out_col)
    me.update()
    rest = rest_coords(me)
    for name, h in hidden.items():
        bpy.data.objects[name].hide_render = h
    if arm is not None:
        arm.data.pose_position = "POSE"
    sc.render.engine = "BLENDER_EEVEE"
    z = co[:, 2]
    rep = {"ao": AO, "vertices": n, "raw_min": round(float(raw.min()), 3), "raw_mean": round(float(raw.mean()), 3),
           "value_p5": round(float(np.percentile(v, 5)), 3), "value_mean": round(float(v.mean()), 3),
           "head_mean": round(float(v[z > 1.40].mean()), 3), "below_0p7": int((v < 0.7).sum()), "rest": rest,
           "jaw_lift": {**JAW_LIFT, "vertices": int((jaw > 0.5).sum()), "mean_before": round(jaw_before, 3) if jaw_before else None,
                        "mean_after": round(float(v[jaw > 0.5].mean()), 3) if (jaw > 0.5).any() else None}}
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "build" / "alien_character.blend"))
    opts = dict(export_glb.options(False), export_image_format="AUTO", export_vertex_color="ACTIVE")
    glb = out / "export" / "alien_character.glb"
    res = bpy.ops.export_scene.gltf(filepath=str(glb), **opts)
    if res != {"FINISHED"}:
        raise SystemExit(f"export: {res}")
    src = Path(a.character).parent.parent / "export"
    for f in src.iterdir():
        if f.suffix == ".png":
            shutil.copy2(f, out / "export" / f.name)
    cj = json.loads((src / "character.json").read_text(encoding="utf-8"))
    cj["note_s9_ao"] = ("art #196 S9: the skin (Body) carries baked ambient occlusion as COLOR_0 (grey, linear; "
                        "three.js multiplies it into the base colour, alien_hue.gdshader reads COLOR.r). S9b: the rest-pose "
                        "position and normal z in TEXCOORD_2 (x, y) and TEXCOORD_3 (z, normal z + 2), glTF axes, for "
                        "Godot's gradient and grain (three.js's position attribute is already the rest pose).")
    cj["report_s9_ao"] = rep
    (out / "export" / "character.json").write_text(json.dumps(cj, indent=1), encoding="utf-8", newline="\n")
    (out / "build_report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8", newline="\n")
    print("AO " + json.dumps(rep))


if __name__ == "__main__":
    main()
