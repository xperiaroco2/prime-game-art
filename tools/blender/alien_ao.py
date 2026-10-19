"""The alien's baked ambient occlusion (art #196, S9): the soft shade in the creases of the release-look paintover
(under the lids, around the lips, under the jaw, at the neck) baked into the skin's vertices, so Godot and three.js
show the same.

  blender -b --factory-startup --python-exit-code 1 --python tools/blender/alien_ao.py -- \
      --character <mouths/build/alien_character.blend> --out <S9/cage/ao>

The method: Cycles bakes AO (distance AO["distance"], AO["samples"] samples) into a float colour attribute `ao` on the
Point domain of the skin mesh (`Body`, the welded body and head), in the rest pose, with the default face shown
(bored eyes at their rest lids, the frog mouth's rest piece; no crest) so the lids and lips occlude the skin; every
other part is hidden from the bake. The raw values are lifted by AO["floor"] (no black creases) and smoothed over the
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
SHOWN = ("eye_bored_", "mouth_frog_rest")  # the parts that occlude the skin in the bake (with Body)


def args():
    p = argparse.ArgumentParser()
    p.add_argument("--character", required=True)
    p.add_argument("--out", required=True)
    return p.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])


def main():
    a = args()
    out = Path(a.out)
    (out / "build").mkdir(parents=True, exist_ok=True)
    (out / "export").mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=a.character)
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
    for name, h in hidden.items():
        bpy.data.objects[name].hide_render = h
    if arm is not None:
        arm.data.pose_position = "POSE"
    sc.render.engine = "BLENDER_EEVEE"
    co = np.empty(n * 3)
    me.vertices.foreach_get("co", co)
    z = co.reshape(-1, 3)[:, 2]
    rep = {"ao": AO, "vertices": n, "raw_min": round(float(raw.min()), 3), "raw_mean": round(float(raw.mean()), 3),
           "value_p5": round(float(np.percentile(v, 5)), 3), "value_mean": round(float(v.mean()), 3),
           "head_mean": round(float(v[z > 1.40].mean()), 3), "below_0p7": int((v < 0.7).sum())}
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
                        "three.js multiplies it into the base colour, alien_hue.gdshader reads COLOR.r).")
    cj["report_s9_ao"] = rep
    (out / "export" / "character.json").write_text(json.dumps(cj, indent=1), encoding="utf-8", newline="\n")
    (out / "build_report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8", newline="\n")
    print("AO " + json.dumps(rep))


if __name__ == "__main__":
    main()
