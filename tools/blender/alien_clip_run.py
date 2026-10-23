"""Every clip on the bare aliens in motion (art #196, A1): stages each head's built character (a folder that
alien_char_run.py built: <from>/<head>/<head>_char.glb), runs godot/alien/clip_reels.gd in the runner's off-screen
window (one 1280x720 reel per clip, framed to the clip's motion; clips_<head>.jpg; reels.json with the measures)
and encodes one MP4 per clip and head with Blender's FFmpeg.

    $PYTHON_BIN tools/blender/alien_clip_run.py --from <tag dir> --out <proof dir> [--heads chameleon,axolotl]
        [--on-clip auto|yes|no]

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
    args = ap.parse_args()
    src, out = Path(args.src), Path(args.out)
    if (out / "reels.json").exists():
        print(f"{out / 'reels.json'} exists: pick a new --out", flush=True)
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
    print(f"on_clip {job['on_clip']}", flush=True)
    (out / "reels_job.json").write_text(json.dumps(job, indent=1), encoding="utf-8", newline="\n")
    _godot.import_project()
    code, output = _godot.window(["--path", str(_godot.PROJECT), "-s", "res://alien/clip_reels.gd", "--",
                                  str(out / "reels_job.json")], (1280, 720), 3000)
    (out / "reels_godot.log").write_text(output, encoding="utf-8", newline="\n")
    print(f"godot reels: exit {code}", *[x for x in output.splitlines() if "REEL" in x or "ERROR" in x][-30:],
          sep="\n", flush=True)
    if code != 0:
        return 1
    folders = sorted(str(d) for d in frames.iterdir() if d.is_dir())
    res = blender.run_script("encode_clips.py", ["--frames", *folders, "--out", str(out / "mp4"), "--fps", "24",
                                                 "--repeat", "1"], timeout=2400)
    print(*[x for x in (res.stdout or "").splitlines() if x.startswith("ENCODED")], sep="\n", flush=True)
    sizes = {p.name: p.stat().st_size // 1024 for p in sorted((out / "mp4").glob("*.mp4"))}
    print("mp4 KB", json.dumps(sizes), flush=True)
    return 0 if res.returncode == 0 and len(sizes) == len(folders) else 1


if __name__ == "__main__":
    sys.exit(main())
