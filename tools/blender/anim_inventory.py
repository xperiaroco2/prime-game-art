"""The animation inventory (tools/run.py anim-review inventory; docs/animations.md): every Ultimate Modular pack
file's 24 actions (names, lengths, whether they are identical across the files of a body type, how the men's and the
women's differ) and the Universal Animation Library's clips in both files of each library, UAL1 ("ual", "ual_rm")
and the review settings' [libraries] ("ual2", "ual2_rm"; art #24): names, lengths, loops, root motion.

Usage: blender -b --factory-startup --python-exit-code 1 --python anim_inventory.py -- --raw <raw dir>
           --config <anim_review.toml> --out <inventory.json>
"""

import argparse
import hashlib
import json
import math
import os
import sys
import tomllib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anim_libs  # noqa: E402
import anim_math as am  # noqa: E402
import retarget_core as rc  # noqa: E402
import retarget_map  # noqa: E402

SAMPLES = 24  # normalised times at which the men's and the women's versions of an action are compared


def action_hash(action) -> str:
    h = hashlib.sha256()
    for fc in sorted(rc.fcurves_of(action), key=lambda f: (f.data_path, f.array_index)):
        h.update(f"{fc.data_path}[{fc.array_index}]".encode())
        for k in fc.keyframe_points:
            h.update(f"{k.co.x:.3f},{k.co.y:.5f};".encode())
    return h.hexdigest()[:16]


def local_rotations(sampler, frac):
    basis = sampler.basis(sampler.start + frac * sampler.frames)
    return {b: tuple(rc.rot(m)) for b, m in basis.items()}


def compare_rigs(ref: dict, other: dict) -> dict:
    """Another library's rig against UAL1's: the same bone names and parents, and the largest rest offset (mm) and
    rest rotation difference (degrees, world space) of a bone: whether UAL1's bone map serves it unchanged."""
    common = [n for n in ref if n in other]
    off = {n: (ref[n][1].translation - other[n][1].translation).length * 1000 for n in common}
    ang = {n: math.degrees(ref[n][1].to_quaternion().rotation_difference(other[n][1].to_quaternion()).angle)
           for n in common}
    ang = {n: min(a, 360 - a) for n, a in ang.items()}
    worst = max(ang, key=ang.get) if ang and round(max(ang.values()), 3) > 0.0 else None  # none for 0.0 shown
    return {"same_bone_names": sorted(ref) == sorted(other),
            "same_parents": all(ref[n][0] == other[n][0] for n in common),
            "only_in_ual": sorted(set(ref) - set(other)), "only_here": sorted(set(other) - set(ref)),
            "max_rest_offset_mm": round(max(off.values(), default=0.0), 3),
            "max_rest_rotation_deg": round(ang.get(worst, 0.0), 3), "most_turned_bone": worst}


def pack_files(raw, cfg, body):
    folder = os.path.join(raw, cfg["bodies"][body]["pack"])
    return sorted(f for f in os.listdir(folder) if f.endswith(".glb")), folder


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    with open(a.config, "rb") as f:
        cfg = tomllib.load(f)
    inv = {"fps": rc.FPS, "pack": {}, "ual": {}}
    donors = {}
    for body in ("men", "women"):
        files, folder = pack_files(a.raw, cfg, body)
        per_file, hashes = {}, {}
        for name in files:
            rc.new_scene()
            ch = rc.load_glb(os.path.join(folder, name))
            per_file[name] = {"actions": len(ch["actions"]), "bones": len(ch["arm"].data.bones),
                              "parts": sorted(ch["meshes"])}
            for act_name, act in ch["actions"].items():
                hashes.setdefault(act_name, {}).setdefault(action_hash(act), []).append(name)
        donor = os.path.basename(cfg["bodies"][body]["character"])
        rc.new_scene()
        ch = rc.load_glb(os.path.join(folder, donor))
        actions = {}
        for act_name, act in sorted(ch["actions"].items()):
            s = rc.Sampler(act)
            variants = hashes[act_name]
            actions[act_name] = {
                "frames_30fps": round(s.frames, 2), "seconds": round(s.seconds, 3),
                "keys": max(len(fc.keyframe_points) for fc in rc.fcurves_of(act)),
                "identical_in_all_files": len(variants) == 1,
                "variants": [sorted(v) for v in variants.values()] if len(variants) > 1 else [],
            }
        donors[body] = {n: [local_rotations(rc.Sampler(act), i / (SAMPLES - 1)) for i in range(SAMPLES)]
                        for n, act in ch["actions"].items()}
        inv["pack"][body] = {"donor": donor, "files": per_file, "actions": actions}
    cmp = {}
    for n in sorted(donors["men"]):
        if n not in donors["women"]:
            cmp[n] = {"women": "missing"}
            continue
        diffs = [max(am.quat_angle(m[b], w[b]) for b in m if b in w)
                 for m, w in zip(donors["men"][n], donors["women"][n])]
        cmp[n] = {"max_pose_difference_deg": round(max(diffs), 1), "mean_pose_difference_deg": round(sum(diffs) / len(diffs), 1),
                  "men_s": inv["pack"]["men"]["actions"][n]["seconds"],
                  "women_s": inv["pack"]["women"]["actions"][n]["seconds"]}
    inv["pack"]["men_vs_women"] = cmp
    files, rests = {"ual": (cfg["ual"], "ual")}, {}
    files["ual_rm"] = (cfg["ual_rm"], "ual")
    for lib, entry in cfg.get("libraries", {}).items():
        files[lib] = (entry["file"], lib)
        if "rm" in entry:  # a Meshy library has none: its clips keep their travel, or the settings take it out
            files[f"{lib}_rm"] = (entry["rm"], lib)
    inv["libraries"] = ["ual", *cfg.get("libraries", {})]
    for key, (rel, lib) in files.items():
        rc.new_scene()
        ent = anim_libs.entry(cfg, lib) if key == lib else {}
        bmap = retarget_map.load(retarget_map.MAPS / ent["map"]) if ent.get("map") else retarget_map.load()
        root, pelvis = (bmap["root"] or bmap["hips"])[0], bmap["hips"][0]  # UAL's root and pelvis, Meshy's Hips
        ch = anim_libs.load(os.path.join(a.raw, rel), ent, a.raw, pelvis)
        rig = rc.Rig(ch["arm"])
        clips = {}
        for n in sorted(ch["actions"]):
            s = ch["samplers"][n]
            p0 = rc.fk(rig, s.basis(s.start))
            p1 = rc.fk(rig, s.basis(s.end))
            r0, r1 = rig.W @ p0[root].translation, rig.W @ p1[root].translation
            h0, h1 = rig.W @ p0[pelvis].translation, rig.W @ p1[pelvis].translation
            dist = math.hypot(r1.x - r0.x, r1.y - r0.y)
            clips[n] = {"frames_30fps": round(s.frames, 2), "seconds": round(s.seconds, 3),
                        "loop": n.endswith("_Loop"), "root_travel_m": round(dist, 3),
                        "root_speed_m_s": round(dist / s.seconds, 2) if s.seconds else 0.0,
                        "root_rise_m": round(r1.z - r0.z, 3),
                        "pelvis_travel_m": round(math.hypot(h1.x - h0.x, h1.y - h0.y), 3)}
        inv["ual"][key] = {"file": rel, "clips": clips, "bones": len(ch["arm"].data.bones)}
        rests[key] = {b.name: (b.parent.name if b.parent else None, ch["arm"].matrix_world @ b.matrix_local)
                      for b in ch["arm"].data.bones}
    for key in [k for k in inv["libraries"] if k != "ual" and not anim_libs.entry(cfg, k).get("map")]:
        inv["ual"][key]["rig_vs_ual"] = compare_rigs(rests["ual"], rests[key])
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(inv, f, indent=1)
    print("INVENTORY", a.out, {b: len(inv["pack"][b]["actions"]) for b in ("men", "women")},
          {k: len(v["clips"]) for k, v in inv["ual"].items()})


main(sys.argv[sys.argv.index("--") + 1:])
