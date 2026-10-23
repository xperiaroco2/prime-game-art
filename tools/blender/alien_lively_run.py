"""The static head's liveliness proof (art #196, lively): the driver (plain Python, outside Blender). It adds the
minimal skin and the clean sclera to the merged static chameleon head in headless Blender (alien_lively_build.py),
checks the skinned GLB with glTF-Validator, shoots the proof in an off-screen Godot window (godot/alien/lively_shots.gd
through the runner's _godot.window(): sheet.jpg, the video's frames) and encodes the video with Blender's FFmpeg
(encode_clips.py). godot-check runs separately (`tools/run.sh godot-check --textured <glb>`). The static head's folder
is only read.

    $PYTHON_BIN tools/blender/alien_lively_run.py [--out DIR] [--no-build] [--seconds 20] [--neck y0,y1] [--tag v3]
        [--pit-before DIR] [--no-pit-fix]

--tag names this run's sheet, shots and video (sheet_<tag>.jpg, shots_<tag>.json, video/lively_<tag>/,
lively_<tag>.mp4); a run never deletes in the raw folder, so a tag whose frame folder exists is refused. Since v3 a
tagged build writes into its own folder, <out>/<tag>/ (the GLB, the sclera, lively.json, crest_weights.png,
eye_residual.png), and a ready web folder, <out>/web_<tag>/ (index.html and lively.js from <out>/web/ beside the
tag's assets); an existing tag folder is refused. --pit-before DIR (default <out>, the v2 build) adds the eye pit's
before/after close-ups, eyes_pit_<tag>.jpg (godot/alien/eye_pit_shots.gd).
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
    ap.add_argument("--tag", default="", help="names the sheet, shots and video of this run (no overwrite of an older one)")
    ap.add_argument("--pit-before", type=Path, default=None, help="the build folder of the eye pit sheet's before (default: --out)")
    ap.add_argument("--no-pit-fix", action="store_true", help="build as v2 did (the eyeballs as sculpted, the old fill)")
    args = ap.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    suffix = f"_{args.tag}" if args.tag else ""
    video = out / "video" / f"lively{suffix}"
    if not args.no_shots and args.seconds > 0 and video.exists():
        print(f"{video} exists: pick a new --tag (a run never deletes in the raw folder)", flush=True)
        return 2
    build_dir = out / args.tag if args.tag else out
    glb = build_dir / "chameleon_lively.glb"
    if not args.no_build:
        if args.tag and build_dir.exists():
            print(f"{build_dir} exists: pick a new --tag (a run never overwrites in the raw folder)", flush=True)
            return 2
        build_dir.mkdir(parents=True, exist_ok=True)
        extra = ["--neck", args.neck] if args.neck else []
        extra += ["--no-pit-fix"] if args.no_pit_fix else []
        result = blender.run_script("alien_lively_build.py", [
            "--glb", str(STATIC / "chameleon_static.glb"), "--albedo", str(STATIC / "chameleon_albedo.png"),
            "--mask", str(STATIC / "chameleon_mask.png"), "--build", str(STATIC / "build.json"), "--out", str(build_dir),
            "--crest-root", args.crest_root, *extra], timeout=1200)
        lines = [x for x in (result.stdout or "").splitlines() if x.startswith("LIVELY ")]
        (build_dir / "build.log").write_text((result.stdout or "") + (result.stderr or ""), encoding="utf-8", newline="\n")
        print(*lines, sep="\n", flush=True)
        if result.returncode != 0:
            print(f"build: exit {result.returncode} (see {build_dir / 'build.log'})", flush=True)
            return 1
        web = out / f"web{suffix}"
        if args.tag and (out / "web").is_dir() and not web.exists():
            web.mkdir()
            for name in ("index.html", "lively.js"):
                shutil.copy2(out / "web" / name, web / name)
            for name in ("chameleon_lively.glb", "chameleon_sclera.png", "lively.json"):
                shutil.copy2(build_dir / name, web / name)
            print(f"web {web}", flush=True)
    report = _export.validate(glb, build_dir / "chameleon_lively.validator.json")
    ok, text = _export.verdict(report)
    print(f"validator {glb.name}: {text}", flush=True)
    if args.no_shots:
        return 0 if ok else 1
    build = json.loads((STATIC / "build.json").read_text(encoding="utf-8"))
    base = "%.4f,%.4f,%.4f" % tuple(build["base_skin_srgb"])
    res = _godot.stage(glb, "lively_chameleon" + suffix)
    still = _godot.stage(STATIC / "chameleon_static.glb", "static_chameleon")
    before = args.pit_before or out
    pit = args.tag and before.resolve() != build_dir.resolve() and (before / "chameleon_lively.glb").exists()
    if pit:
        res_before = _godot.stage(before / "chameleon_lively.glb", "lively_chameleon_before")
    _godot.import_project()
    if pit:
        code, output = _godot.window(["--path", str(_godot.PROJECT), "-s", "res://alien/eye_pit_shots.gd", "--",
                                      res_before, str(before / "chameleon_sclera.png"), str(before / "lively.json"),
                                      res, str(build_dir / "chameleon_sclera.png"), str(build_dir / "lively.json"),
                                      str(STATIC / "chameleon_mask.png"), base, str(HDRI),
                                      str(out / f"eyes_pit{suffix}.jpg")], (1280, 720), 600)
        (out / f"godot_pit{suffix}.log").write_text(output, encoding="utf-8", newline="\n")
        print(f"godot pit shots: exit {code}", *[x for x in output.splitlines() if "PIT" in x or "ERROR" in x][-6:],
              sep="\n", flush=True)
        if code != 0:
            return 1
    code, output = _godot.window(["--path", str(_godot.PROJECT), "-s", "res://alien/lively_shots.gd", "--", res, still,
                                  str(out), str(STATIC / "chameleon_mask.png"), base, str(HDRI), str(build_dir / "lively.json"),
                                  str(build_dir / "chameleon_sclera.png"), str(args.seconds), suffix], (1280, 720), 900)
    (out / f"godot_shots{suffix}.log").write_text(output, encoding="utf-8", newline="\n")
    print(f"godot shots: exit {code}", *[x for x in output.splitlines() if "LIVELY" in x or "ERROR" in x][-6:],
          sep="\n", flush=True)
    if code != 0:
        return 1
    if args.seconds > 0:
        blender.run_script("encode_clips.py", ["--frames", str(video), "--out", str(out), "--fps", "24",
                                               "--repeat", "1"], timeout=900)
        clip = out / f"lively{suffix}.mp4"
        print(f"video {clip} {clip.stat().st_size // 1024} KB", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
