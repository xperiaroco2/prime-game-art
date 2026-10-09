"""Assemble characters from a recipe (tools/blender/um/, docs/assembly.md): build, pose, measure, render and save them.

The runner calls it (tools/run.py assemble); by hand, background only:
  blender -b --factory-startup --python-exit-code 1 --python tools/blender/assemble_characters.py -- \
      --recipe recipes/um_final_test.json --raw D:/prime-art-raw --out tools/out/assemble/um_final_test \
      [--modes chars,face,hands,lineup,crossgender,qa,ankles|none] [--ids m1_rex,w1_ivy] [--blend] [--res 100]
  ... -- --inspect <character.blend> --json <out.json>     describe a saved character file

Writes into --out: build_report.json; characters/<id>_front.png, _threequarter.png, _face.png, _hands.png; lineup.png;
crossgender.png; work/ (the single views the composites are made of, qa and ankle views); with --blend,
blend/<id>.blend and blend/<id>.json (the sidecar, with the reopened file's inspection under "inspected").
"""

import argparse
import json
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from um import assemble, blendfile, fit  # noqa: E402
from um import packs as pk  # noqa: E402
from um import recipe as recipes  # noqa: E402
from um import render as rd  # noqa: E402
from um.util import update, world_points  # noqa: E402


def parse():
    p = argparse.ArgumentParser(prog="assemble_characters.py")
    p.add_argument("--recipe")
    p.add_argument("--raw")
    p.add_argument("--out")
    p.add_argument("--modes", default="")
    p.add_argument("--ids", default="")
    p.add_argument("--blend", action="store_true")
    p.add_argument("--res", type=int, default=100)
    p.add_argument("--look", default="")
    p.add_argument("--clay-lib", default="")
    p.add_argument("--inspect")
    p.add_argument("--json")
    return p.parse_args(sys.argv[sys.argv.index("--") + 1:])


def main():
    args = parse()
    if args.inspect:
        result = blendfile.inspect(os.path.abspath(args.inspect))
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=1)
        print("INSPECTED", args.inspect, "problems:", len(result["problems"]))
        return

    R = recipes.load(args.recipe, args.raw)
    assemble.check_styles(R)
    modes = recipes.modes(R) if not args.modes else ([] if args.modes == "none" else args.modes.split(","))
    unknown = [m for m in modes if m not in recipes.MODES]
    if unknown:
        raise RuntimeError(f"unknown modes {unknown}; known: {', '.join(recipes.MODES)}")
    known_ids = [rc["id"] for rc in R["characters"]]
    only = args.ids.split(",") if args.ids else None
    if only and any(i not in known_ids for i in only):
        raise RuntimeError(f"unknown ids {[i for i in only if i not in known_ids]}; the recipe has: {', '.join(known_ids)}")
    out = os.path.abspath(args.out)
    os.makedirs(os.path.join(out, "characters"), exist_ok=True)
    os.makedirs(os.path.join(out, "work"), exist_ok=True)
    packs = pk.Packs({g: recipes.pack_dir(R, args.raw, g) for g in recipes.GENDERS})
    rd.RES_PERCENT = args.res

    bpy.ops.wm.read_factory_settings(use_empty=True)
    report = {"recipe": R["_name"], "characters": {}, "crossgender": {}}
    rd.setup_render()
    chars = {}
    recs = [rc for rc in R["characters"] if only is None or rc["id"] in only]
    # "none" builds and measures without rendering; crossgender alone needs no characters (as in the final test)
    need_chars = args.blend or not modes or any(m in modes for m in ("chars", "hands", "lineup", "qa", "face", "ankles"))
    for i, rc in enumerate(recs if need_chars else []):
        coll = bpy.data.collections.new(rc["id"]); bpy.context.scene.collection.children.link(coll)
        arm, parts, rep = assemble.build_character(packs, R, rc, coll)
        if (args.look or R.get("look", "pack")) == "clay":
            assemble.clay_look(R, rc, arm, parts, rep, lib=args.clay_lib or None)
        report["characters"][rc["id"]] = rep
        chars[rc["id"]] = (arm, parts, coll, rc)
        print("BUILT", rc["id"], "height", rep["height_m"], "tris", rep["triangles_total"])
        pk.place(arm.parent, x=(i + 1) * 3.0)  # park it away from the origin so the next build has the origin free

    for cid, (arm, parts, coll, rc) in chars.items():
        rep = report["characters"][cid]
        assemble.pose_character(arm, parts, rc, rep)
        print("PROBE", cid, "rest", rep["probe_rest"], "posed", rep["probe_posed"])

    def solo(cid):
        for k, (arm, parts, coll, rc) in chars.items():
            coll.hide_render = (k != cid) if cid else False

    def path(*names):
        return os.path.join(out, *names)

    if "chars" in modes:
        for cid, (arm, parts, coll, rc) in chars.items():
            solo(cid)
            objs = list(parts.values())
            yaw = rd.facing_deg(arm)
            report["characters"][cid]["facing_yaw_deg"] = round(yaw, 1)
            rd.render(path("characters", cid + "_front.png"), objs, (90, 0, yaw))
            rd.render(path("characters", cid + "_threequarter.png"), objs, (84, 0, yaw + 38))
        solo(None)

    if "face" in modes or "qa" in modes:
        for cid, (arm, parts, coll, rc) in chars.items():
            solo(cid)
            hb = arm.matrix_world @ arm.pose.bones["Head"].head
            c = hb + Vector((0, 0, 0.11))
            views = [path("work", cid + "_face_" + v + ".png") for v in ("front", "34", "side", "back")]
            objs = list(parts.values())
            yaw = rd.facing_deg(arm)
            for p, rot in zip(views, ((90, 0, yaw), (86, 0, yaw + 40), (90, 0, yaw + 90), (70, 0, yaw + 180))):
                rd.render(p, objs, rot, height=600, centre=c, extent=0.36, width=600)
            rd.compose(views, path("work", cid + "_face.png"))
            if "face" in modes:
                # deliverable close-up: the whole head with its hair, front and three-quarter, 1200 px tall
                hp = world_points([parts[k] for k in parts if k in ("head", "hair", "moustache", "eyes", "brows", "mouth")])
                lo = Vector((min(p.x for p in hp), min(p.y for p in hp), min(p.z for p in hp)))
                hi = Vector((max(p.x for p in hp), max(p.y for p in hp), max(p.z for p in hp)))
                hc = (lo + hi) / 2
                ext = max(0.36, (hi.z - lo.z) * 1.12)
                f1, f2 = path("work", cid + "_face_d1.png"), path("work", cid + "_face_d2.png")
                rd.render(f1, objs, (90, 0, yaw), height=1200, width=1000, centre=hc, extent=ext)
                rd.render(f2, objs, (87, 0, yaw + 38), height=1200, width=1000, centre=hc, extent=ext)
                rd.compose([f1, f2], path("characters", cid + "_face.png"))
        solo(None)

    if "qa" in modes:
        for cid, (arm, parts, coll, rc) in chars.items():
            solo(cid)
            objs = list(parts.values())
            p1, p2 = path("work", cid + "_qa_back.png"), path("work", cid + "_qa_side.png")
            yaw = rd.facing_deg(arm)
            rd.render(p1, objs, (90, 0, yaw + 180), height=900)
            rd.render(p2, objs, (90, 0, yaw - 90), height=900)
            rd.compose([p1, p2], path("work", cid + "_qa.png"))
        solo(None)

    if "ankles" in modes:  # each shoe collar from four directions, in the pose
        for cid, (arm, parts, coll, rc) in chars.items():
            solo(cid)
            e = json.loads(arm["seam_edges"]); yaw = rd.facing_deg(arm)
            shots = []
            for side in ("L", "R"):
                c, _ = fit.bone_ray_points(arm, "LowerLeg." + side, e["collar_lo_" + side] - 0.04)
                for k in range(0, 360, 90):
                    p = path("work", "%s_ankle_%s_%d.png" % (cid, side, k))
                    rd.render(p, list(parts.values()), (80, 0, yaw + k), height=500, width=500, centre=c, extent=0.32)
                    shots.append(p)
            rd.compose(shots, path("work", cid + "_ankles.png"))
        solo(None)

    for hs in [h for h in R.get("hands", []) if h["id"] in chars and "hands" in modes]:
        cid = hs["id"]
        arm, parts, coll, rc = chars[cid]
        solo(cid)
        yaw = rd.facing_deg(arm)
        objs = list(parts.values())
        shots = []
        for shot in hs["shots"]:
            side, view = shot[0], shot[1]
            tilt = shot[2] if len(shot) > 2 else 90  # camera pitch: 90 = level, smaller = looking down
            # frame the wrist and every fingertip (a curled middle finger alone would cut the pointing index off)
            hp = [arm.matrix_world @ arm.pose.bones["Wrist." + side].head] + [arm.matrix_world @ arm.pose.bones[b + "." + side].tail for b in ("Index4", "Middle4", "Ring4", "Pinky4", "Thumb3")]
            lo = Vector((min(p.x for p in hp), min(p.y for p in hp), min(p.z for p in hp)))
            hi = Vector((max(p.x for p in hp), max(p.y for p in hp), max(p.z for p in hp)))
            c = (lo + hi) / 2
            ext = max(0.15, (hi - lo).length * 1.45)
            turn = rd.VIEW_YAW[view] * (1 if side == "L" or view == "back" else -1)  # turn toward that hand's side
            p = path("work", "%s_hand_%s_%s.png" % (cid, side, view))
            rd.render(p, objs, (tilt, 0, yaw + turn), height=700, width=700, centre=c, extent=ext)
            shots.append(p)
        rd.compose(shots, path("characters", cid + "_hands.png"))
        solo(None)

    if "lineup" in modes and chars:
        # same scale: one ortho camera over all, spaced 0.95 m apart in their poses, each turned to face the camera
        order = [rc["id"] for rc in recs]
        for i, cid in enumerate(order):
            pk.place(chars[cid][0].parent, x=i * 0.95)
            pk.place(chars[cid][0].parent, x=i * 0.95, yaw=-rd.facing_deg(chars[cid][0]))
        update()
        allobjs = [o for cid in order for o in chars[cid][1].values()]
        rd.render(path("lineup.png"), allobjs, (90, 0, 0), height=1200, margin=1.06)

    if "crossgender" in modes and R.get("crossgender"):
        for k, (arm, parts, coll, rc) in chars.items():
            coll.hide_render = True
        report["crossgender"] = assemble.crossgender(packs, R, path("crossgender.png"), rd)

    report["actions_in_session"] = len(bpy.data.actions)  # 24 per rig still in the scene: the duplicates are gone
    with open(path("build_report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    print("REPORT", path("build_report.json"))

    if args.blend:
        sidecars = {}
        for cid, (arm, parts, coll, rc) in chars.items():
            sidecars[cid] = blendfile.save_character(cid, arm, parts, rc, report["characters"][cid], path("blend"))
        problems = []
        for cid, sidecar in sidecars.items():  # reopen each file: this replaces the session, so it comes last
            seen = blendfile.inspect(path("blend", cid + ".blend"))
            sidecar["inspected"] = seen
            with open(path("blend", cid + ".json"), "w", encoding="utf-8") as fh:
                json.dump(sidecar, fh, indent=1)
            problems += [f"{cid}.blend: {p}" for p in seen["problems"]]
            print("INSPECTED", cid, "objects", len(seen["objects"]), "actions", len(seen["actions"]), "problems", len(seen["problems"]))
        if problems:
            raise RuntimeError("saved files break the rules:\n" + "\n".join(problems))


main()
