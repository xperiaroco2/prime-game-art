"""Body type B's hands against its hips in motion (art #196, B1): per clip, every second frame, the posed skin's least
distance from a hand vertex (heaviest on a Hand or finger bone) to a hip or thigh vertex (heaviest on Hips, Spine or an
UpperLeg), in headless Blender, so B's wider hips can be compared with A's in the same clips.

    blender -b --factory-startup --python tools/blender/alien_body_b_clearance.py -- --blend <char>_char.blend
        [--blend <other>_char.blend] --clips Idle_Loop,Walk_Loop,Jog_Fwd_Loop --out clearance.json

Writes per file and clip the least distance (mm), its frame and side, and the frames under 10 mm.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import kdtree

HIPS = ("Hips", "Spine", "LeftUpperLeg", "RightUpperLeg")
DIGITS = ("Hand", "Thumb", "Index", "Middle", "Ring", "Little")


def one(path: str, clips: list[str]) -> dict:
    bpy.ops.wm.open_mainfile(filepath=str(Path(path).resolve()))
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    skin = max((o for o in bpy.data.objects if o.type == "MESH" and o.find_armature() == arm),
               key=lambda o: len(o.data.vertices))
    names = {g.index: g.name for g in skin.vertex_groups}
    hand, hip = {}, []
    for v in skin.data.vertices:
        if not v.groups:
            continue
        g = max(v.groups, key=lambda x: x.weight)
        n = names.get(g.group, "")
        if any(d in n for d in DIGITS) and n.startswith(("Left", "Right")):
            hand[v.index] = "Left" if n.startswith("Left") else "Right"
        elif n in HIPS:
            hip.append(v.index)
    out = {"skin": skin.name, "hand_vertices": len(hand), "hip_vertices": len(hip), "clips": {}}
    for c in clips:
        act = bpy.data.actions.get("CharacterArmature|" + c) or bpy.data.actions.get(c)
        if act is None:
            out["clips"][c] = {"missing": True}
            continue
        arm.animation_data_create()
        arm.animation_data.action = act
        f0, f1 = (int(x) for x in act.frame_range)
        best, near = (1e9, None, None), []
        for f in range(f0, f1 + 1, 2):
            bpy.context.scene.frame_set(f)
            dg = bpy.context.evaluated_depsgraph_get()
            me = skin.evaluated_get(dg).to_mesh()
            tree = kdtree.KDTree(len(hip))
            for i, vi in enumerate(hip):
                tree.insert(me.vertices[vi].co, i)
            tree.balance()
            low = 1e9
            for vi, side in hand.items():
                _, _, d = tree.find(me.vertices[vi].co)
                if d < low:
                    low = d
                if d < best[0]:
                    best = (d, f, side)
            skin.evaluated_get(dg).to_mesh_clear()
            if low < 0.010:
                near.append(f)
        out["clips"][c] = {"min_mm": round(best[0] * 1000, 1), "frame": best[1], "side": best[2],
                           "frames_under_10mm": near}
        print(f"CLEAR {Path(path).name} {c} {out['clips'][c]}", flush=True)
    return out


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", action="append", required=True)
    ap.add_argument("--clips", default="Idle_Loop,Walk_Loop,Jog_Fwd_Loop")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    res = {p: one(p, a.clips.split(",")) for p in a.blend}
    Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
