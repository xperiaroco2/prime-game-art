"""Every clip on the bare aliens in motion (art #196, A1): stages each head's built character (a folder that
alien_char_run.py built: <from>/<head>/<head>_char.glb), runs godot/alien/clip_reels.gd in the runner's off-screen
window (one 1280x720 reel per clip, framed to the clip's motion; clips_<head>.jpg; reels.json with the measures)
and encodes one MP4 per clip and head with Blender's FFmpeg.

    $PYTHON_BIN tools/blender/alien_clip_run.py --from <tag dir> --out <proof dir> [--heads chameleon,axolotl]
        [--on-clip auto|yes|no] [--split] [--head60 Jog_Fwd,Sprint_Fwd] [--yaw-counter 0.3] [--darts 0]
        [--eye-mode lead|fixed|free] [--eyes | --backface]

The frames go to tools/out/alien_clips/<out's name>/ (temporary); the MP4s, sheets and reels.json into --out, never
overwritten (an --out holding reels.json is refused). Long: run it in the background.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "blender"))
from runner import blender  # noqa: E402
from runner.commands import _godot  # noqa: E402
import alien_char_run as R  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--heads", default="chameleon,axolotl")
    ap.add_argument("--on-clip", choices=("auto", "yes", "no"), default="auto",
                    help="the lively controller on top of the clip (A1); auto: yes for a build made with --clip-edits, "
                         "no for an older one (its before, as the r5 proof played it)")
    ap.add_argument("--split", action="store_true", help="A2: 2x2 review frames (three-quarter, side, back, close-up)")
    ap.add_argument("--head60", default="", help="A2: clips that also get a 60 fps head reel, e.g. Jog_Fwd,Sprint_Fwd")
    ap.add_argument("--yaw-counter", type=float, default=0.0, help="A2: the controller's yaw_counter on the locomotion")
    ap.add_argument("--darts", type=float, default=0.0, help="A2: the controller's eye darts (degrees)")
    ap.add_argument("--eye-mode", choices=("fixed", "lead", "free"), default="lead",
                    help="A3: the controller's eye_mode in the clip reels (R1: lead, the engineer's choice, art #196"
                         " comment 6391652501: the eyes lead a head turn by at most 8 degrees; fixed: the pupils centred)")
    ap.add_argument("--eyes", action="store_true",
                    help="A3: the eyes' proof instead of the clip reels (godot/alien/eye_reels.gd): the lower rim's "
                         "close-ups (rim_<head>.jpg, rim_<head>_4x/) and the look-around per eye mode "
                         "(<head>_look_fixed.mp4, <head>_look_lead.mp4, <head>_look_side.mp4), eyes.json")
    ap.add_argument("--backface", action="store_true",
                    help="R2: the back-face test instead (godot/alien/backface_shots.gd): the head's back faces red, "
                         "the red pixels counted per gaze and view (backface.json, backface_<head>.jpg, <head>_4x/)")
    args = ap.parse_args()
    if args.eyes and args.backface:
        ap.error("--eyes and --backface are two runs")
    src, out = Path(args.src), Path(args.out)
    stem = "eyes" if args.eyes else "backface" if args.backface else "reels"
    done = out / f"{stem}.json"
    if done.exists():
        print(f"{done} exists: pick a new --out", flush=True)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    frames = ROOT / "tools" / "out" / "alien_clips" / out.name
    shutil.rmtree(frames, ignore_errors=True)  # our own temporary frames
    frames.mkdir(parents=True)
    slots_job = json.loads((R.SLOTS / "job.json").read_text(encoding="utf-8"))["heads"]
    heads = args.heads.split(",")
    job = {"hdri": str(R.HDRI), "out": str(out), "fix": dict(R.FIX), "frames": str(frames), "sheet_out": str(out),
           "heads": {h: R.head_job(h, src / h, json.loads((src / h / "bases.json").read_text(encoding="utf-8")),
                                   slots_job) for h in heads}}
    edited = all("clip_edits" in json.loads((src / h / "char.json").read_text(encoding="utf-8")) for h in heads)
    job["on_clip"] = edited if args.on_clip == "auto" else args.on_clip == "yes"
    job.update(split=args.split, head60=[c for c in args.head60.split(",") if c], yaw_counter=args.yaw_counter,
               darts=args.darts, eye_mode=args.eye_mode)
    print(f"on_clip {job['on_clip']}", flush=True)
    (out / f"{stem}_job.json").write_text(json.dumps(job, indent=1), encoding="utf-8", newline="\n")
    _godot.import_project()
    script = {"eyes": "res://alien/eye_reels.gd", "backface": "res://alien/backface_shots.gd"}.get(stem,
                                                                                               "res://alien/clip_reels.gd")
    code, output = _godot.window(["--path", str(_godot.PROJECT), "-s", script, "--", str(out / f"{stem}_job.json")],
                                 (1280, 720), 3000 * (4 if args.split else 1))
    (out / f"{stem}_godot.log").write_text(output, encoding="utf-8", newline="\n")
    print(f"godot {stem}: exit {code}", *[x for x in output.splitlines() if "REEL" in x or "EYES" in x
                                          or "ERROR" in x][-30:], sep="\n", flush=True)
    if code != 0:
        return 1
    folders = sorted(str(d) for d in frames.iterdir() if d.is_dir())
    ok = True
    for fps, group in ((24, [f for f in folders if not f.endswith("_head60")]),
                       (60, [f for f in folders if f.endswith("_head60")])):
        if not group:
            continue
        res = blender.run_script("encode_clips.py", ["--frames", *group, "--out", str(out / "mp4"), "--fps", str(fps),
                                                     "--repeat", "1"], timeout=2400)
        print(*[x for x in (res.stdout or "").splitlines() if x.startswith("ENCODED")], sep="\n", flush=True)
        ok &= res.returncode == 0
    sizes = {p.name: p.stat().st_size // 1024 for p in sorted((out / "mp4").glob("*.mp4"))}
    print("mp4 KB", json.dumps(sizes), flush=True)
    return 0 if ok and len(sizes) == len(folders) else 1


if __name__ == "__main__":
    sys.exit(main())
