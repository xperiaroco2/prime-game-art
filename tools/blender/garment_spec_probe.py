"""Dumps a character's rest for a garment spec drawing (art #196, Gate 1): the armature's bones (world head and
tail) and every visible mesh object's rest-pose evaluated vertices and triangles, each triangle with its material's
name. Plain Python (garment_spec.py, garment_drawing.py) projects, draws and measures them; no maths here.

    tools/runner/blender.py's run_script("garment_spec_probe.py", ["--blend", <character.blend>, "--out", <json>])
(headless Blender, as every Blender run here; never a window)

Read only: the .blend is opened and never saved. The frame is the character's: x lateral, z up from the sole, the
front at -y. Coordinates in metres, rounded to 0.1 mm.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    bpy.ops.wm.open_mainfile(filepath=args.blend)
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    for a in arms:
        a.data.pose_position = "REST"
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    bones = {}
    if arms:
        arm = arms[0]
        bones = {b.name: {"head": [round(c, 5) for c in arm.matrix_world @ b.head_local],
                          "tail": [round(c, 5) for c in arm.matrix_world @ b.tail_local]} for b in arm.data.bones}
    meshes = []
    for o in bpy.data.objects:
        if o.type != "MESH" or o.hide_render or o.hide_get():
            continue
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        me.calc_loop_triangles()
        mw = o.matrix_world
        verts = [[round(c, 4) for c in mw @ v.co] for v in me.vertices]
        mats = [m.name if m else "" for m in me.materials] or [""]
        tris = [[t.vertices[0], t.vertices[1], t.vertices[2], t.material_index] for t in me.loop_triangles]
        meshes.append({"name": o.name, "materials": mats, "vertices": verts, "tris": tris})
        ev.to_mesh_clear()
    out = {"blend": args.blend, "bones": bones, "meshes": meshes}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print("probe: " + ", ".join(f"{m['name']} {len(m['vertices'])}v {len(m['tris'])}t {m['materials']}"
                                for m in meshes) + f" -> {args.out}")


main()
