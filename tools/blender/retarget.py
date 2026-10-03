"""`tools/run.py retarget`: bakes Universal Animation Library clips onto an Ultimate Modular armature (docs/animations.md).

Usage (background Blender only, through tools/runner/blender.py):
  blender -b --factory-startup --python-exit-code 1 --python retarget.py -- --source <UAL.glb> --target <UM.glb>
      --out <dir> [--map <map.toml>] [--clips Walk_Loop,Idle_Loop|all] [--no-ik] [--blend]
Writes <out>/retarget_report.json (the hip-height ratio, the rest-pose check, each clip's frames and IK misses) and,
with --blend, <out>/<target>_ual.blend: the target character with the baked actions "UAL|<clip>" and nothing else.
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402

import retarget_core as rc  # noqa: E402
import retarget_map  # noqa: E402


def main(argv):
    ap = argparse.ArgumentParser(prog="retarget.py")
    ap.add_argument("--source", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--map", default=str(retarget_map.DEFAULT))
    ap.add_argument("--clips", default="all")
    ap.add_argument("--no-ik", action="store_true")
    ap.add_argument("--blend", action="store_true")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    bmap = retarget_map.load(a.map)
    rc.new_scene()
    src = rc.load_glb(a.source)
    tgt = rc.load_glb(a.target)
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
        "soles": sorted(rt.soles),
        "rest_check": rt.rest_error(),
        "clips": {},
    }
    t0 = time.time()
    for name in names:
        act, frames = rt.clip(src["actions"][name], "UAL|" + name, tgt["arm"])
        report["clips"][name] = {"frames": frames, "seconds": round(frames / rc.FPS, 3), "action": act.name,
                                 "ik_miss_mm": round(rt.miss_mm, 2)}
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
            if act not in tgt["actions"].values() and not act.name.startswith("UAL|"):
                bpy.data.actions.remove(act)
        rc.reset_pose(tgt["arm"])
        stem = os.path.splitext(os.path.basename(a.target))[0].replace(" ", "_")
        path = os.path.join(a.out, f"{stem}_ual.blend")
        bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
        report["blend"] = path
        with open(os.path.join(a.out, "retarget_report.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, indent=1)
    print("REPORT", json.dumps({k: v for k, v in report.items() if k != "clips"}))


main(sys.argv[sys.argv.index("--") + 1:])
