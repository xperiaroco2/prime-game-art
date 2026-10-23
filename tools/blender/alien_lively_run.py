"""The static head's liveliness proof (art #196, lively): the driver (plain Python, outside Blender). It adds the
minimal skin and the clean sclera to the merged static chameleon head in headless Blender (alien_lively_build.py),
checks the skinned GLB with glTF-Validator, shoots the proof in an off-screen Godot window (godot/alien/lively_shots.gd
through the runner's _godot.window(): sheet.jpg, the video's frames) and encodes the video with Blender's FFmpeg
(encode_clips.py). godot-check runs separately (`tools/run.sh godot-check --textured <glb>`). The static head's folder
is only read.

    $PYTHON_BIN tools/blender/alien_lively_run.py [--out DIR] [--no-build] [--seconds 20] [--neck y0,y1]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from runner import blender, common  # noqa: E402
from runner.commands import _export, _godot  # noqa: E402

RAW = common.raw_dir()
PILOT = RAW / "research" / "2026-10-22-roster" / "design" / "pilot3d"
STATIC = PILOT / "static_v5" / "chameleon"  # the merged static head (PR #299)
OUT = PILOT / "lively"
HDRI = RAW / "env" / "polyhaven" / "studio_small_09" / "studio_small_09_2k.hdr"  # CC0, sources/polyhaven_hdris_2k.toml


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--no-shots", action="store_true")
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--neck", default="")
    ap.add_argument("--crest-root", default="0.45")
    args = ap.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    glb = out / "chameleon_lively.glb"
    if not args.no_build:
        extra = ["--neck", args.neck] if args.neck else []
        result = blender.run_script("alien_lively_build.py", [
            "--glb", str(STATIC / "chameleon_static.glb"), "--albedo", str(STATIC / "chameleon_albedo.png"),
            "--mask", str(STATIC / "chameleon_mask.png"), "--build", str(STATIC / "build.json"), "--out", str(out),
            "--crest-root", args.crest_root, *extra], timeout=1200)
        lines = [x for x in (result.stdout or "").splitlines() if x.startswith("LIVELY ")]
        print(*lines, sep="\n", flush=True)
    report = _export.validate(glb, out / "chameleon_lively.validator.json")
    ok, text = _export.verdict(report)
    print(f"validator {glb.name}: {text}", flush=True)
    if args.no_shots:
        return 0 if ok else 1
    build = json.loads((STATIC / "build.json").read_text(encoding="utf-8"))
    base = "%.4f,%.4f,%.4f" % tuple(build["base_skin_srgb"])
    res = _godot.stage(glb, "lively_chameleon")
    still = _godot.stage(STATIC / "chameleon_static.glb", "static_chameleon")
    _godot.import_project()
    video = out / "video" / "lively"
    if video.is_dir():
        shutil.rmtree(video)
    code, output = _godot.window(["--path", str(_godot.PROJECT), "-s", "res://alien/lively_shots.gd", "--", res, still,
                                  str(out), str(STATIC / "chameleon_mask.png"), base, str(HDRI), str(out / "lively.json"),
                                  str(out / "chameleon_sclera.png"), str(args.seconds)], (1280, 720), 900)
    (out / "godot_shots.log").write_text(output, encoding="utf-8", newline="\n")
    print(f"godot shots: exit {code}", *[x for x in output.splitlines() if "LIVELY" in x or "ERROR" in x][-6:],
          sep="\n", flush=True)
    if code != 0:
        return 1
    if args.seconds > 0:
        blender.run_script("encode_clips.py", ["--frames", str(video), "--out", str(out), "--fps", "24",
                                               "--repeat", "1"], timeout=900)
        clip = out / "lively.mp4"
        print(f"video {clip} {clip.stat().st_size // 1024} KB", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
