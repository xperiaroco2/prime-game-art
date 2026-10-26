"""The head follows the player's aim (art #196, H1): the plain-Python driver of the head-look proof.

`$PYTHON_BIN tools/blender/alien_headlook_run.py --check` runs godot/alien/head_look_check.gd headless on both
characters' GLBs (the animations' newest build, loco/f1): the modifier's unit check (HEADLOOK lines, exit 1 on a failure).
`... --shots [--chars chameleon,axolotl] [--no-video]` runs godot/alien/head_look_shots.gd in the runner's off-screen
window: per character the range grids (yaw x pitch on Idle and Jog_Fwd from three-quarter), the extremes' close-ups
(front and side), and the motion reels (the nod and the shake on Idle, Jog_Fwd and Strafe_Left; the body-lag demo at
dead zones 45 and 60), the reels' frames encoded to MP4 by Blender's encode_clips.py, into
<raw>/research/2026-10-22-roster/design/pilot3d/anim_bare/headlook/<char>/.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runner import blender  # noqa: E402
from runner.commands import _godot  # noqa: E402
import alien_char_run as R  # noqa: E402

BUILD = R.PILOT / "anim_bare" / "loco" / "f1" / "build"  # the newest loco build (F1: the back cap at 2.0)
OUT = R.PILOT / "anim_bare" / "headlook"
CHARS = ("chameleon", "axolotl")
# the extremes' variants (at R1's clamps, 70 / 50 down / 40 up): R1's split, and the modifier's defaults (H1's "trunk"
# split: more of the turn in the trunk, less in the head bone)
VARIANTS = [
    {"name": "r1", "set": {"pitch_down_deg": 50.0,
                           "yaw_split": {"Spine": 0.10, "Chest": 0.15, "UpperChest": 0.15, "Neck": 0.25, "Head": 0.35},
                           "pitch_split": {"UpperChest": 0.15, "Neck": 0.35, "Head": 0.50}}},
    {"name": "trunk", "set": {"pitch_down_deg": 50.0}},
    {"name": "rec"},  # the recommendation: the defaults (trunk split, 70 / 35 down / 40 up)
]


def _check(chars: list[str]) -> int:
    glbs = [_godot.stage(BUILD / c / f"{c}_char.glb", f"char_{c}") for c in chars]
    _godot.import_project()
    code, output = _godot.godot(["--headless", "--fixed-fps", "60", "--path", str(_godot.PROJECT), "-s",
                                 "res://alien/head_look_check.gd", "--", *glbs], 600)
    print(*[x for x in output.splitlines() if x.startswith(("HEADLOOK", "FOLLOW", "ERROR", "SCRIPT ERROR"))],
          sep="\n", flush=True)
    return code


def _shots(chars: list[str], video: bool) -> int:
    slots_job = json.loads((R.SLOTS / "job.json").read_text(encoding="utf-8"))["heads"]
    bad = 0
    for c in chars:
        hd = BUILD / c
        out = OUT / c
        frames = ROOT / "tools" / "out" / "headlook" / "frames" / c
        shutil.rmtree(frames, ignore_errors=True)  # our own temporary frames
        frames.mkdir(parents=True)
        out.mkdir(parents=True, exist_ok=True)
        job = {"hdri": str(R.HDRI), "fix": dict(R.FIX), "out": str(out), "frames": str(frames), "video": video, "variants": VARIANTS,
               "head": R.head_job(c, hd, json.loads((hd / "bases.json").read_text(encoding="utf-8")), slots_job)}
        (out / "shots_job.json").write_text(json.dumps(job, indent=1), encoding="utf-8", newline="\n")
        _godot.import_project()
        code, output = _godot.window(["--fixed-fps", "24", "--path", str(_godot.PROJECT), "-s",
                                      "res://alien/head_look_shots.gd", "--", str(out / "shots_job.json")],
                                     (1280, 720), 3000)
        (out / "shots_godot.log").write_text(output, encoding="utf-8", newline="\n")
        print(f"{c} godot shots: exit {code}", *[x for x in output.splitlines() if "SHOT" in x or "ERROR" in x][-40:],
              sep="\n", flush=True)
        if code != 0:
            bad += 1
            continue
        folders = sorted(str(d) for d in frames.iterdir() if d.is_dir())
        if not folders:
            continue
        res = blender.run_script("encode_clips.py", ["--frames", *folders, "--out", str(out / "mp4"), "--fps", "24",
                                                     "--repeat", "1"], timeout=2400)
        sizes = {p.name: p.stat().st_size // 1024 for p in sorted((out / "mp4").glob("*.mp4"))}
        print(f"{c} mp4 KB", json.dumps(sizes), flush=True)
        bad += int(res.returncode != 0 or len(sizes) < len(folders))
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--shots", action="store_true")
    ap.add_argument("--chars", default=",".join(CHARS))
    ap.add_argument("--no-video", action="store_true")
    a = ap.parse_args()
    chars = a.chars.split(",")
    code = 0
    if a.check:
        code = _check(chars)
    if a.shots and code == 0:
        code = _shots(chars, not a.no_video)
    return code


if __name__ == "__main__":
    sys.exit(main())
