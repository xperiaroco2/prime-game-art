"""`tools/run.py retarget`: bakes Universal Animation Library clips onto an Ultimate Modular armature (docs/animations.md).

Usage (background Blender only, through tools/runner/blender.py):
  blender -b --factory-startup --python-exit-code 1 --python retarget.py -- --source <UAL.glb> --target <UM.glb>
      --out <dir> [--map <map.toml>] [--clips Walk_Loop,Idle_Loop|all] [--no-ik] [--floor] [--blend] [--prefix UAL2]
A pack original as the target gets the assembler's toe bones first (um/toes.py, art #25) when the map drives them.
Writes <out>/retarget_report.json (the hip-height ratio, the rest-pose check, each clip's frames and IK misses; with
--floor also each clip's lowest vertex on the target and on the source's own mesh, scaled to the target) and,
with --blend, <out>/<target>_<prefix>.blend (lower case): the target character with the baked actions "<prefix>|<clip>"
(UAL|, UAL2|, Meshy|, TTM|) and nothing else. UAL2 (art #24) has UAL1's rig and takes the same bone map. A library of
Meshy text-to-motion FBX files (art #33) loads through anim_libs.load (retarget_smpl.py: the rig lifted onto the
floor, `floor_shift_m` in the report).
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402

import retarget_core as rc  # noqa: E402
import anim_libs  # noqa: E402
import retarget_map  # noqa: E402
from anim_metrics import world_points  # noqa: E402


def lowest(char: dict) -> float:
    """The lowest world height of the character's posed meshes."""
    bpy.context.view_layer.update()
    return min(float(world_points(o)[:, 2].min()) for o in char["meshes"].values())


def floor(rt, src: dict, tgt: dict, sampler, baked) -> dict:
    """The lowest vertex (cm) of the retargeted clip on the target, and of the source clip on the source's own mesh
    scaled to the target's size: how deep a clip goes into the floor by itself, against what the retarget adds. The
    source is sampled as the retarget sampled it (the library's sampler: in place, or with an SMPL-H floor shift)."""
    s, t = sampler, rc.Sampler(baked)
    low_t = low_s = float("inf")
    for i in range(int(round(t.frames)) + 1):
        rc.apply_basis(tgt["arm"], t.basis(t.start + i))
        low_t = min(low_t, lowest(tgt))
        rc.apply_basis(src["arm"], s.basis(s.start + i))
        low_s = min(low_s, (lowest(src) - rt.src_o.z) * rt.ratio + rt.tgt_o.z)
    rc.reset_pose(tgt["arm"]), rc.reset_pose(src["arm"])
    return {"lowest_cm": round(100 * low_t, 1), "source_lowest_cm": round(100 * low_s, 1)}


def main(argv):
    ap = argparse.ArgumentParser(prog="retarget.py")
    ap.add_argument("--source", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--map", default=str(retarget_map.DEFAULT))
    ap.add_argument("--clips", default="all")
    ap.add_argument("--no-ik", action="store_true")
    ap.add_argument("--blend", action="store_true")
    ap.add_argument("--floor", action="store_true")
    ap.add_argument("--prefix", default="UAL", help="the baked actions' name prefix (UAL, UAL2, Meshy, TTM)")
    ap.add_argument("--config", help="the review settings: the library's extra files, renames and in-place clips")
    ap.add_argument("--library", help="the library's key in the review settings (meshy, art #25; tm, art #33)")
    ap.add_argument("--raw", help="the raw folder, which the settings' paths are relative to")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    bmap = retarget_map.load(a.map)
    rc.new_scene()
    ent = {}
    if a.config and a.library:
        import tomllib

        with open(a.config, "rb") as f:
            ent = anim_libs.entry(tomllib.load(f), a.library)
    # with a Meshy library's extra files (art #25), or a text-to-motion library's clip files (art #33)
    src = anim_libs.load(a.source, ent, a.raw, bmap["hips"][0])
    tgt = rc.load_glb(a.target)
    toes = None
    if any(b.startswith("Toe.") and b not in tgt["arm"].data.bones for b in bmap["target_bones"]):
        toes = rc.add_toes(tgt)  # the assembler's toe bones (art #25) on a pack original
    missing = [b for b in bmap["source_bones"] if b not in src["arm"].data.bones]
    missing += [b for b in bmap["target_bones"] if b not in tgt["arm"].data.bones]
    if missing:
        raise SystemExit(f"the rigs lack bones of the map: {missing}")
    rt = rc.Retargeter(rc.Rig(src["arm"]), rc.Rig(tgt["arm"]), bmap)
    rt.ik = not a.no_ik
    rt.set_soles(tgt["meshes"].values())
    names = sorted(src["actions"]) if a.clips == "all" else a.clips.split(",")
    unknown = [n for n in names if n not in src["actions"]]
    if unknown:
        raise SystemExit(f"no such source clips: {unknown}; the source has {sorted(src['actions'])}")
    report = {
        "source": a.source, "target": a.target, "map": bmap["title"], "ik": rt.ik, "fps": rc.FPS,
        "hip_height_m": {"source": round(rt.src_hip, 4), "target": round(rt.tgt_hip, 4)},
        "translation_scale": round(rt.ratio, 4),
        "floor_shift_m": round(src.get("floor_shift_m", 0.0), 4),  # the source rig lifted onto the floor (SMPL-H)
        "soles": sorted(rt.soles),
        "toe_bones_added": bool(toes and toes.get("added")),
        "rest_check": rt.rest_error(),
        "clips": {},
    }
    t0 = time.time()
    for name in names:
        act, frames = rt.clip(src["actions"][name], f"{a.prefix}|{name}", tgt["arm"], src["samplers"][name])
        report["clips"][name] = {"frames": frames, "seconds": round(frames / rc.FPS, 3), "action": act.name,
                                 "ik_miss_mm": round(rt.miss_mm, 2)}
        if a.floor:
            report["clips"][name].update(floor(rt, src, tgt, src["samplers"][name], act))
        print("RETARGETED", name, frames, "frames, IK miss", round(rt.miss_mm, 2), "mm")
    report["seconds_spent"] = round(time.time() - t0, 1)
    with open(os.path.join(a.out, "retarget_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    if a.blend:
        keep = {tgt["arm"], *tgt["meshes"].values(), tgt["root"]} - {None}
        keep |= {o for o in tgt["objects"] if o.parent in keep and o.type == "EMPTY"}
        for o in list(bpy.data.objects):
            if o not in keep:
                bpy.data.objects.remove(o, do_unlink=True)
        for act in list(bpy.data.actions):
            if act not in tgt["actions"].values() and not act.name.startswith(f"{a.prefix}|"):
                bpy.data.actions.remove(act)
        rc.reset_pose(tgt["arm"])
        stem = os.path.splitext(os.path.basename(a.target))[0].replace(" ", "_")
        path = os.path.join(a.out, f"{stem}_{a.prefix.lower()}.blend")
        bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
        report["blend"] = path
        with open(os.path.join(a.out, "retarget_report.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, indent=1)
    print("REPORT", json.dumps({k: v for k, v in report.items() if k != "clips"}))


main(sys.argv[sys.argv.index("--") + 1:])
