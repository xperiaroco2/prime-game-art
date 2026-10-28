"""The alien's locomotion set onto the built characters (art #196, option A step 3): the clips of
anim_sets/alien_loco.toml (alien_loco_math.expand) made with step 1's edits (alien_stride_math: cycle on the left
foot's contact, stride, arm_swing, mirror) from each R2b character's UAL clips and step 2's text-to-motion loops,
written as CharacterArmature|<name>_Loop (a game clip replaces the build's action of that name), one GLB per
character with export_glb.py's fixed options (textured, the build's morph-free export), glTF-Validator; then the
treadmill reels of one character (godot/alien/treadmill_reels.gd in the runner's off-screen window, MP4s with
Blender's FFmpeg).

    $PYTHON_BIN tools/blender/alien_loco.py --raw D:/prime-art-raw [--chars chameleon,axolotl]   # the GLBs
    $PYTHON_BIN tools/blender/alien_loco.py --raw D:/prime-art-raw --reels [--only NAME,...] [--char NAME]  # reels
    $PYTHON_BIN tools/blender/alien_loco.py --raw D:/prime-art-raw --build r2c/build --out loco/t1  # T1: new bodies

Into <raw>/<raw_base>/<out>/build/<char>/: <char>_char.blend, <char>_char.glb, its validator report, loco.json (per
clip the edits' reports, the numbers before and after, the rates at the game's speeds), the build's support files
(bases, char.json, lively, body maps) copied beside it for the reels; the chameleon's reels into <out>/reels/, the
axolotl's into <out>/reels/axolotl/ (never overwritten: an --out holding reels.json is refused). Long: run it in
the background.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import alien_loco_math as L  # noqa: E402

PREFIX = "CharacterArmature|"
COPY = ("bases.json", "char.json", "{c}_char_lively.json", "{c}_body_albedo.png", "{c}_body_mask.png",
        "{c}_body_detail.png", "{c}_body_accent.png", "{c}_body_normal.png")


def _paths(raw: str, cfg: dict) -> tuple[Path, Path, Path]:
    base = Path(raw) / cfg["set"]["raw_base"]
    return base / cfg["set"]["build"], base / cfg["set"]["ttm"], base / cfg["set"]["out"]


def _same_skeleton(a: dict, b: dict) -> bool:
    return a["parent"] == b["parent"] and all(
        max(abs(x - y) for ra, rb in zip(a["rest"][k], b["rest"][k]) for x, y in zip(ra, rb)) < 1e-6 for k in a["rest"])


def _make(S, skel, srcs: dict, jobs: list[dict], cfg: dict) -> tuple[dict, dict]:
    """Every clip of the set from the sampled sources: (clips by name, reports by name)."""
    clips, reps = {}, {}
    foot = cfg["set"]["foot"]
    for j in jobs:
        rep = {k: j.get(k) for k in ("base", "source", "mirror", "speed", "frames", "arm_swing", "play_at")}
        if j.get("pick"):
            beat = 1.0 / L.footstep_interval(j["speed"], cfg)
            rows = [{"name": n, "c0": reps[n]["after"]["c0"], "arm_swing": reps[n]["arm_swing"],
                     "slide_mm": max(reps[n]["after"]["foot_slide_mm"].values())} for n in j["pick"]]
            best = L.pick_default(rows, beat, S.SLIDE_BOUND_MM, j["default_arm_swing"])
            c = S.copy_clip(clips[best["name"]])
            rep = {**reps[best["name"]], "picked": best["name"], "beat_cadence": round(beat, 4), "pick_rows": rows}
        elif j.get("mirror"):
            c, cyc = S.cycle(skel, S.mirror(skel, clips[j["mirror"]]), foot=foot, loop=True)
            rep.update(before=reps[j["mirror"]]["before"], cycle=cyc, stride=reps[j["mirror"]].get("stride"))
        else:
            if j.get("from"):  # a made clip of the set (the approved Jog_Fwd) turned into another direction (P2)
                c = S.copy_clip(clips[j["from"]])
                rep["before"] = reps[j["from"]]["after"]
            else:
                c = S.copy_clip(srcs[j["source"]])
                rep["before"] = S.measure(skel, c)
                c, rep["cycle"] = S.cycle(skel, c, foot=foot, loop=True)
                # step 2's bakes keep the source's world travel and place in the Hips' basis: every loop is cut in
                # place before the stride, so the stride plants its feet in the frame the measure was made for (4b)
                c, rep["in_place_first"] = L.in_place(skel, c)
                if j.get("even_steps"):  # the other foot's contact moved to half the cycle (P4: 6/8 -> 7/7)
                    c, rep["even_steps"] = S.even_steps(skel, c, foot)
            if j.get("lean_deg"):  # the trunk leant forward over the feet (the backpedal, P2)
                c = S.pitch(skel, c, j["lean_deg"], L.LEAN_SPLIT)
            if j.get("orient"):  # the hips toward the travel, the head on the aim (orient_warp; absolute headings)
                c, rep["orient"] = L.orient(S, skel, c, j["orient"])
            rate = S.frames(c) / j["frames"] if j.get("frames") else None
            if j.get("cadence"):
                rate = L.cadence_rate(j["name"], j["cadence"], S.measure(skel, c)["c0"])
            if j.get("max_scale") and j.get("speed"):
                rate = L.capped_rate(j["speed"], S.measure(skel, c)["v0"], j["max_scale"], rate, S.frames(c))
            if rate is not None or j.get("speed") is not None:
                c, st = S.stride(skel, c, rate=rate, speed=j.get("speed"), bend_min_deg=j.get("bend_min_deg"),
                                 widen_m=j.get("widen_m") or 0.0)
                rep["stride"] = {k: st[k] for k in ("rate_eff", "intervals", "scale", "fit", "ankle_miss_mm",
                                                    "planted_slide_mm", "slide_bound_mm", "knee_floor_mm")}
                L.check_max_scale(j["name"], st["scale"], j.get("max_scale"))
            if j.get("lift_m") or j.get("bob_m") or j.get("flight_m"):  # the hips' height, its bob, a flight (P3)
                c, rep["lift"] = S.lift_hips(skel, c, j.get("lift_m") or 0.0, j.get("bob_m") or 0.0,
                                             j.get("flight_m") or 0.0)
            if j.get("arm_swing", 1.0) != 1.0:
                c, rep["arm_swing_report"] = S.arm_swing(c, j["arm_swing"])
            if j.get("arms_from"):
                af = j["arms_from"]
                c, rep["arms_from_report"] = S.arms_from(c, clips[af["clip"]], k=af.get("k", 1.0), w=af.get("w", 1.0),
                                                         phase=af.get("phase", 0.0))
            if j.get("arms_in_deg"):  # the elbows brought in toward the body (P3)
                c = S.arms_in(skel, c, j["arms_in_deg"])
            if j.get("head_level") is not None:  # the eyes on the way ahead (the crouch, P2)
                c, rep["head"] = S.level_head(skel, c, j["head_level"])
            if j.get("orient") and not j["orient"].get("whole"):  # the planted feet's travel set to the asked heading
                c, rep["trim"] = L.trim_travel(S, skel, c, j["orient"]["travel"])
            if j.get("pin"):  # the planted feet pinned by the honest test (P3: the backpedal)
                c, rep["pin"] = S.pin_feet(skel, c)
            if j.get("arms_carry"):  # the arms solved onto a running carriage in the trunk's frame (P4: the backpedal)
                c, rep["arms_carry"] = S.arms_carry(skel, c, **j["arms_carry"])
        if not j.get("pick"):
            c, rep["in_place"] = L.in_place(skel, c)
        c["name"] = j["name"] + L.LOOP
        if not j.get("pick"):
            rep["after"] = S.measure(skel, c)
            # the honest numbers (step 4b): the planted feet by height and speed alone, the knees, the hands
            rep["honest_slide"] = S.honest_slide(skel, c, rep["after"]["ground_m_s"])
            rep["knee"] = S.knee_bend(skel, c)
            rep["hands_m"] = S.hand_clearance(skel, c)
            rep["airborne_frames"] = S.airborne_frames(skel, c)  # P3: a run's flight, the legs' room, the elbows
            rep["legs_m"] = S.leg_spacing(skel, c)
            rep["elbow_deg"] = S.elbow_bend(skel, c)
            rep["arms_m"] = S.arm_carriage(skel, c)  # P4: midline, wrist height and place, elbows from the axis
            rep["facing"] = {**S.facing(skel, c), "travel_deg": round(S.travel_heading_deg(rep["after"]), 2)}
        rep["hips"] = L.hips_extent(skel, c)
        a = rep["after"]
        scale = (rep.get("stride") or {}).get("scale")
        rep["stride_flag"] = L.stride_flag(scale, cfg)
        rep["play"] = L.play_rows(a["v0"], a["c0"], j.get("play_at") or [], cfg)
        rep["reel"] = {"fps": a["fps"], "frames": a["intervals"], "v0": a["v0"], "c0": a["c0"],
                       "ground": L.godot_xz(a["ground_m_s"]), "hips": L.godot_xz(a["hips_m_s"]),
                       "contacts": a["contacts"]}
        clips[j["name"]], reps[j["name"]] = c, rep
        hs = rep["honest_slide"]
        print(f"CLIP {j['name']} v0 {a['v0']} c0 {a['c0']} scale {scale} rate "
              f"{(rep.get('stride') or {}).get('rate_eff')} flag {rep['stride_flag']} slide {a['foot_slide_mm']} honest "
              f"{[(hs[s]['drift_mm'], hs[s]['skate_m_s']) for s in hs]} knee "
              f"{[(v['min_deg'], v['swing_min_deg']) for v in rep['knee'].values()]} hands {rep['hands_m']} "
              f"play {[(p['speed'], p['rate'], p['step_s'], p['beat_s']) for p in rep['play']]} hips {rep['hips']} "
              f"facing {rep.get('facing')}",
              flush=True)
    return clips, reps


def _export(arm, path: Path) -> None:
    import bpy
    import export_glb as EG
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.location, pb.rotation_quaternion, pb.scale = (0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0), (1.0, 1.0, 1.0)
    bpy.context.view_layer.update()
    for o in bpy.context.scene.objects:
        o.select_set(o == arm or (o.type == "MESH" and o.parent == arm))
    bpy.context.view_layer.objects.active = arm
    # the fixed textured options; the character build's GLB has no morph targets (alien_char_build.py exports none)
    opts = {**EG.options(textured=True), "use_selection": True, "export_morph": False}
    if bpy.ops.export_scene.gltf(filepath=str(path), **opts) != {"FINISHED"}:
        raise SystemExit(f"the glTF exporter failed on {path}")
    EG.fix_zero_tangents(str(path))


def _blender_main(argv: list[str]) -> None:
    import bpy
    import alien_stride as ST
    import alien_stride_math as S
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--chars", default="")
    ap.add_argument("--dump", default="", help="only write the first character's skeleton and sampled sources here")
    ap.add_argument("--build", default="")
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    cfg = L.with_paths(L.load(), a.build, a.out)
    jobs = L.expand(cfg)
    build, ttm, out = _paths(a.raw, cfg)
    mocap = Path(a.raw) / cfg["set"]["raw_base"] / cfg["set"]["mocap"] if cfg["set"].get("mocap") else None
    made = None
    for char in a.chars.split(",") if a.chars else cfg["set"]["chars"]:
        bpy.ops.wm.open_mainfile(filepath=str(build / char / f"{char}_char.blend"))
        arm = ST._armature()
        sk = ST.skeleton(arm)
        need = L.sources(jobs)
        with bpy.data.libraries.load(str(ttm), link=False) as (src, dst):
            dst.actions = [n for n in src.actions if n.startswith(PREFIX + "TM_") and n[len(PREFIX):] in need]
        if mocap is not None:  # P1's 100STYLE loops MC_<style>_<take>_Loop (the axolotl shares the skeleton)
            with bpy.data.libraries.load(str(mocap), link=False) as (src, dst):
                dst.actions = [n for n in src.actions if n.startswith(PREFIX + "MC_") and n[len(PREFIX):] in need]
        # T2: a build fitted to its body's legs (char.json leg_fit) gets the same fit on the loops appended from the
        # S4b rig's files (alien_leg_fit.py); a build without it: untouched
        fitted = json.loads((build / char / "char.json").read_text(encoding="utf-8")).get("leg_fit")
        if fitted:
            import alien_leg_fit
            lf = alien_leg_fit.fit(arm, fitted["donor"], [bpy.data.actions[PREFIX + n] for n in need
                                                         if n.startswith(("TM_", "MC_"))],
                                  mode=fitted.get("mode", "lowest"))
            print(f"CHAR {char}: leg fit {lf['scale']} on the appended loops ({lf['keys']} keys), foot match "
                  f"{json.dumps(lf['foot_match'])}", flush=True)
        srcs = {n: ST.sample(arm, bpy.data.actions[PREFIX + n]) for n in need}
        for n in need:
            if n.startswith(("TM_", "MC_")):
                bpy.data.actions.remove(bpy.data.actions[PREFIX + n])
        if a.dump:  # the plain-Python tuning's input (grids on dumped data, no Blender per try)
            Path(a.dump).write_text(json.dumps({"skel": sk, "srcs": srcs}), encoding="utf-8", newline="\n")
            print(f"DUMP {a.dump} {len(srcs)} sources", flush=True)
            return
        if made and _same_skeleton(made[0], sk):  # the same skeleton: the same clips (step 1 measured them equal)
            clips, reps = made[1], json.loads(json.dumps(made[2]))
            print(f"CHAR {char}: the skeleton equals {made[3]}'s, its clips reused", flush=True)
        else:
            clips, reps = _make(S, S.prepare(sk), srcs, jobs, cfg)
            made = (sk, clips, reps, char)
        for n, c in clips.items():
            ST.write(arm, c, n + L.LOOP)
        hd = out / "build" / char
        hd.mkdir(parents=True, exist_ok=True)
        _export(arm, hd / f"{char}_char.glb")
        bpy.ops.wm.save_as_mainfile(filepath=str(hd / f"{char}_char.blend"), compress=True)
        actions = sorted(x.name for x in bpy.data.actions)
        (hd / "loco.json").write_text(json.dumps({"char": char, "set": str(L.SET), "clips": reps, "actions": actions},
                                                 indent=1), encoding="utf-8", newline="\n")
        print(f"CHAR {char} {len(clips)} clips, {len(actions)} actions -> {hd / f'{char}_char.glb'}", flush=True)


def _reels(a, cfg: dict) -> int:
    from runner import blender
    from runner.commands import _godot
    import alien_char_run as R
    build, _, out = _paths(a.raw, cfg)
    char = a.char
    reels_dir = out / "reels" if char == "chameleon" else out / "reels" / char  # F3: the axolotl's beside them
    if (reels_dir / "reels.json").exists():
        print(f"{reels_dir / 'reels.json'} exists: move it aside first", flush=True)
        return 2
    reels_dir.mkdir(parents=True, exist_ok=True)
    frames = ROOT / "tools" / "out" / "loco" / "frames"
    shutil.rmtree(frames, ignore_errors=True)  # our own temporary frames
    frames.mkdir(parents=True)
    hd = out / "build" / char
    slots_job = json.loads((R.SLOTS / "job.json").read_text(encoding="utf-8"))["heads"]
    plan = L.reel_plan(L.expand(cfg), cfg.get("reel"))
    if a.only:
        plan = [r for r in plan if r["name"] in a.only.split(",")]
    loco = json.loads((hd / "loco.json").read_text(encoding="utf-8"))["clips"]
    for r in plan:
        for c in r["clips"]:
            c["timeline"] = L.reel_timeline(loco[c["clip"]]["reel"], c["speed"], r.get("seconds", L.REEL_S), cfg,
                                            r.get("start", {}).get("at", 0.0), c.get("travel"))
    job = {"hdri": str(R.HDRI), "fix": dict(R.FIX), "out": str(reels_dir), "frames": str(frames),
           "head": R.head_job(char, hd, json.loads((hd / "bases.json").read_text(encoding="utf-8")), slots_job),
           "reels": plan,
           "seconds": L.REEL_S}
    (reels_dir / "reels_job.json").write_text(json.dumps(job, indent=1), encoding="utf-8", newline="\n")
    _godot.import_project()
    code, output = _godot.window(["--path", str(_godot.PROJECT), "-s", "res://alien/treadmill_reels.gd", "--",
                                  str(reels_dir / "reels_job.json")], (1280, 720), 3000)
    (reels_dir / "reels_godot.log").write_text(output, encoding="utf-8", newline="\n")
    print(f"godot reels: exit {code}", *[x for x in output.splitlines() if "REEL" in x or "ERROR" in x][-40:],
          sep="\n", flush=True)
    if code != 0:
        return 1
    folders = sorted(str(d) for d in frames.iterdir() if d.is_dir())
    res = blender.run_script("encode_clips.py", ["--frames", *folders, "--out", str(reels_dir / "mp4"), "--fps", "24",
                                                 "--repeat", "1"], timeout=2400)
    print(*[x for x in (res.stdout or "").splitlines() if x.startswith("ENCODED")], sep="\n", flush=True)
    sizes = {p.name: p.stat().st_size // 1024 for p in sorted((reels_dir / "mp4").glob("*.mp4"))}
    print("mp4 KB", json.dumps(sizes), flush=True)
    return 0 if res.returncode == 0 and len(sizes) == len(folders) else 1


def main() -> int:
    sys.path.insert(0, str(ROOT / "tools"))
    from runner import blender
    from runner.commands import _export
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--chars", default="")
    ap.add_argument("--reels", action="store_true")
    ap.add_argument("--only", default="", help="--reels: only these reels (names from alien_loco_math.reel_plan)")
    ap.add_argument("--char", default="chameleon", choices=("chameleon", "axolotl"),
                    help="--reels: the character (not the chameleon: into reels/<char>/)")
    ap.add_argument("--dump", default="", help="write the chameleon's skeleton and sampled sources as JSON, no build")
    ap.add_argument("--build", default="", help="T1: the characters' build instead of [set] build (under raw_base, "
                    "e.g. r2c/build); needs --out")
    ap.add_argument("--out", default="", help="T1: the output instead of [set] out (under raw_base, e.g. loco/t1)")
    a = ap.parse_args()
    cfg = L.with_paths(L.load(), a.build, a.out)
    paths = [*(["--build", a.build] if a.build else []), *(["--out", a.out] if a.out else [])]
    if a.reels:
        return _reels(a, cfg)
    if a.dump:
        res = blender.run_script(Path(__file__).resolve(), ["--raw", a.raw, "--chars", "chameleon", "--dump", a.dump, *paths],
                                 timeout=1200)
        print(*[x for x in (res.stdout or "").splitlines() if x.startswith("DUMP")], sep="\n", flush=True)
        return res.returncode
    build, _, out = _paths(a.raw, cfg)
    chars = a.chars.split(",") if a.chars else cfg["set"]["chars"]
    for c in chars:  # a run never overwrites in the raw folder
        if (out / "build" / c / f"{c}_char.glb").exists():
            print(f"{out / 'build' / c} holds a build: pick a new --out", flush=True)
            return 2
    for c in chars:
        hd = out / "build" / c
        hd.mkdir(parents=True, exist_ok=True)
        for f in COPY:
            p = build / c / f.format(c=c)
            if p.exists():
                shutil.copy2(p, hd / p.name)
    res = blender.run_script(Path(__file__).resolve(), ["--raw", a.raw, "--chars", ",".join(chars), *paths],
                             timeout=3600)
    (out / "build" / "build.log").write_text((res.stdout or "") + (res.stderr or ""), encoding="utf-8", newline="\n")
    print(*[x for x in (res.stdout or "").splitlines() if x.startswith(("CLIP", "CHAR"))], sep="\n", flush=True)
    if res.returncode != 0:
        print(f"blender: exit {res.returncode} (see {out / 'build' / 'build.log'})", flush=True)
        return 1
    ok = True
    for c in chars:
        glb = out / "build" / c / f"{c}_char.glb"
        good, text = _export.verdict(_export.validate(glb, glb.with_suffix(".validator.json")))
        print(f"validator {glb.name}: {text}", flush=True)
        ok &= good
    return 0 if ok else 1


if __name__ == "__main__":
    if "bpy" in sys.modules:
        _blender_main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    else:
        sys.exit(main())
