"""The static head's liveliness proof (art #196, lively): the driver (plain Python, outside Blender). It adds the
minimal skin and the clean sclera to a merged static head in headless Blender (alien_lively_build.py), checks the
skinned GLB with glTF-Validator, shoots the proof in an off-screen Godot window (godot/alien/lively_shots.gd through the
runner's _godot.window(): sheet.jpg, the gate, the eye close-ups, the video's frames) and encodes the video with
Blender's FFmpeg (encode_clips.py). godot-check runs separately (`tools/run.sh godot-check --textured <glb>`). The
static head's folder is only read.

    $PYTHON_BIN tools/blender/alien_lively_run.py [--head chameleon|axolotl] [--out DIR] [--no-build] [--seconds 20]
        [--neck y0,y1] [--tag v3] [--pit-before DIR] [--no-pit-fix] [--rim-smooth N] [--rim-cut ORDER] [--lip-smooth N] [--lip-mode normals|taubin] [--rim-split] [--web-with <other head's build folder>]

--head (AL1, 2026-10-23): the chameleon (a painted iris that moves, the crest) or the axolotl (dark beads with a catch
light fixed to the light, no gaze, six gills on springs); the build's files are named by the head (<head>_lively.glb,
<head>_sclera.png).
--tag names this run's sheet, shots and video (sheet_<tag>.jpg, shots_<tag>.json, video/lively_<tag>/,
lively_<tag>.mp4); a run never deletes in the raw folder, so a tag whose frame folder exists is refused. Since v3 a
tagged build writes into its own folder, <out>/<tag>/ (the GLB, the sclera, lively.json, the weights' and the eyes'
proofs), and a ready web folder, <out>/web_<tag>/ (index.html and lively.js from tools/web/lively/, the tag's assets as
<head>_lively.glb, <head>_lively.json, <head>_sclera.png, heads.json; --web-with adds another head's); an existing tag
folder is refused, and so is any untagged build (it would write into <out> itself, PR #306 review) and any shots run
whose sheet_<tag>.jpg exists. --pit-before DIR (default <out>, the v2 build) adds a
painted head's eye pit before/after close-ups, eyes_pit_<tag>.jpg (godot/alien/eye_pit_shots.gd).
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
OUT = PILOT / "lively"
WEB = ROOT / "tools" / "web" / "lively"  # the page and the module, copied into each tag's web folder
HDRI = RAW / "env" / "polyhaven" / "studio_small_09" / "studio_small_09_2k.hdr"  # CC0, sources/polyhaven_hdris_2k.toml
# the heads: the merged static_v5 builds (PR #299); the axolotl's gill roots are step 2a's pivots
HEADS = {
    "chameleon": {"kind": "painted", "extra": []},
    "axolotl": {"kind": "bead", "extra": ["--gills", str(PILOT / "step2a" / "axolotl" / "v2" / "build.json"),
                                          "--detail", str(PILOT / "static_v5" / "axolotl" / "axolotl_detail.png")]},
}


def run_refusal(out: Path, tag: str, build: bool, shots: bool, seconds: float) -> str | None:
    """Why a run must not start (a run never overwrites in the raw folder), or None. A build needs a new tag: an
    untagged one would write into <out> itself, over the v2 chameleon's GLB, lively.json and build.log (PR #306
    review, major 1), and a tagged one's folder must not exist. Shots need a new sheet, eye pit sheet and shots JSON
    (sheet_<tag>.jpg, eyes_pit_<tag>.jpg, shots_<tag>.json, even with --no-build or --seconds 0: they and the logs share
    the tag; minor 9, AL7) and, with a video, a new frame folder."""
    suffix = f"_{tag}" if tag else ""
    if build and not tag:
        return f"an untagged build would write into {out} itself (an older build's GLB, lively.json, build.log): pass a new --tag"
    if build and (out / tag).exists():
        return f"{out / tag} exists: pick a new --tag (a run never overwrites in the raw folder)"
    for name in (f"sheet{suffix}.jpg", f"eyes_pit{suffix}.jpg", f"shots{suffix}.json"):
        if shots and (out / name).exists():
            return f"{out / name} exists: pick a new --tag (a run never overwrites in the raw folder)"
    if shots and seconds > 0 and (out / "video" / f"lively{suffix}").exists():
        return f"{out / 'video' / f'lively{suffix}'} exists: pick a new --tag (a run never deletes in the raw folder)"
    return None


def copy_web(web: Path, dirs: list[Path]) -> list[str]:
    """The web folder: the page and the module, and each build folder's head as <head>_lively.glb,
    <head>_lively.json and <head>_sclera.png; heads.json lists them."""
    web.mkdir()
    for name in ("index.html", "lively.js"):
        shutil.copy2(WEB / name, web / name)
    heads: list[str] = []
    for d in dirs:
        h = next(p.name[:-len("_lively.glb")] for p in d.glob("*_lively.glb"))
        shutil.copy2(d / f"{h}_lively.glb", web / f"{h}_lively.glb")
        shutil.copy2(d / f"{h}_sclera.png", web / f"{h}_sclera.png")
        shutil.copy2(d / "lively.json", web / f"{h}_lively.json")
        heads += [h] if h not in heads else []
    (web / "heads.json").write_text(json.dumps(heads) + "\n", encoding="utf-8", newline="\n")
    return heads


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--head", choices=sorted(HEADS), default="chameleon")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--no-shots", action="store_true")
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--neck", default="")
    ap.add_argument("--crest-root", default="0.45")
    ap.add_argument("--tag", default="", help="names the sheet, shots and video of this run (no overwrite of an older one)")
    ap.add_argument("--pit-before", type=Path, default=None, help="the build folder of the eye pit sheet's before (default: --out)")
    ap.add_argument("--no-pit-fix", action="store_true", help="build as v2 did (the eyeballs as sculpted, the old fill)")
    ap.add_argument("--sclera-normal-map", type=float, default=None,
                    help="A3b: the eye texels' normal map strength in lively.json (alien_lively_build.py --sclera-normal-map)")
    ap.add_argument("--rim-smooth", type=int, default=0,
                    help="A3b: Taubin steps along the eye rim (alien_lively_build.py --rim-smooth; 0: the v6 builds' rim)")
    ap.add_argument("--rim-cut", type=int, default=0,
                    help="R1: the eye rim cut along one smooth curve, this Fourier order (alien_lively_build.py --rim-cut)")
    ap.add_argument("--gill-lift", choices=("centre", "skull", "centre_pinned"), default="centre",
                    help="the axolotl's gill weights' lift (alien_lively_build.py --gill-lift)")
    ap.add_argument("--web-with", type=Path, default=None, help="another head's tagged build folder, copied into the web folder too")
    ap.add_argument("--lip-smooth", type=int, default=0,
                    help="R2: with --rim-cut, the lid's lip smoothed this many steps (alien_lively_build.py --lip-smooth)")
    ap.add_argument("--lip-mode", choices=("normals", "taubin"), default="normals", help="R2: lip_smooth's mode")
    ap.add_argument("--rim-split", action="store_true",
                    help="R2b: with --rim-cut, the eyeball shaded as its sphere up to the lid (alien_lively_build.py --rim-split)")
    args = ap.parse_args()
    head = args.head
    static = PILOT / "static_v5" / head
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    suffix = f"_{args.tag}" if args.tag else ""
    video = out / "video" / f"lively{suffix}"
    why = run_refusal(out, args.tag, not args.no_build, not args.no_shots, args.seconds)
    if why:
        print(why, flush=True)
        return 2
    build_dir = out / args.tag if args.tag else out
    glb = build_dir / f"{head}_lively.glb"
    sclera = build_dir / f"{head}_sclera.png"
    if not args.no_build:
        build_dir.mkdir(parents=True, exist_ok=True)
        extra = ["--neck", args.neck] if args.neck else []
        extra += ["--no-pit-fix"] if args.no_pit_fix else []
        extra += ["--rim-smooth", str(args.rim_smooth)] if args.rim_smooth else []
        extra += ["--rim-cut", str(args.rim_cut)] if args.rim_cut else []
        extra += ["--lip-smooth", str(args.lip_smooth), "--lip-mode", args.lip_mode] if args.lip_smooth else []
        extra += ["--rim-split"] if args.rim_split else []
        extra += ["--sclera-normal-map", str(args.sclera_normal_map)] if args.sclera_normal_map is not None else []
        extra += ["--gill-lift", args.gill_lift] if head == "axolotl" else []
        result = blender.run_script("alien_lively_build.py", [
            "--glb", str(static / f"{head}_static.glb"), "--albedo", str(static / f"{head}_albedo.png"),
            "--mask", str(static / f"{head}_mask.png"), "--build", str(static / "build.json"), "--out", str(build_dir),
            "--name", head, "--kind", HEADS[head]["kind"], "--crest-root", args.crest_root, *HEADS[head]["extra"],
            *extra], timeout=1500)
        lines = [x for x in (result.stdout or "").splitlines() if x.startswith("LIVELY ")]
        (build_dir / "build.log").write_text((result.stdout or "") + (result.stderr or ""), encoding="utf-8", newline="\n")
        print(*lines, sep="\n", flush=True)
        if result.returncode != 0:
            print(f"build: exit {result.returncode} (see {build_dir / 'build.log'})", flush=True)
            return 1
        web = out / f"web{suffix}"
        if args.tag and not web.exists():
            heads = copy_web(web, [build_dir] + ([args.web_with] if args.web_with else []))
            print(f"web {web} {heads}", flush=True)
    report = _export.validate(glb, build_dir / f"{head}_lively.validator.json")
    ok, text = _export.verdict(report)
    print(f"validator {glb.name}: {text}", flush=True)
    if args.no_shots:
        return 0 if ok else 1
    build = json.loads((static / "build.json").read_text(encoding="utf-8"))
    base = "%.4f,%.4f,%.4f" % tuple(build["base_skin_srgb"])
    res = _godot.stage(glb, f"lively_{head}" + suffix)
    still = _godot.stage(static / f"{head}_static.glb", f"static_{head}")
    before = args.pit_before or out
    pit = (HEADS[head]["kind"] == "painted" and args.tag and before.resolve() != build_dir.resolve()
           and (before / f"{head}_lively.glb").exists())
    if pit:
        res_before = _godot.stage(before / f"{head}_lively.glb", f"lively_{head}_before")
    _godot.import_project()
    if pit:
        code, output = _godot.window(["--path", str(_godot.PROJECT), "-s", "res://alien/eye_pit_shots.gd", "--",
                                      res_before, str(before / f"{head}_sclera.png"), str(before / "lively.json"),
                                      res, str(sclera), str(build_dir / "lively.json"),
                                      str(static / f"{head}_mask.png"), base, str(HDRI),
                                      str(out / f"eyes_pit{suffix}.jpg")], (1280, 720), 600)
        (out / f"godot_pit{suffix}.log").write_text(output, encoding="utf-8", newline="\n")
        print(f"godot pit shots: exit {code}", *[x for x in output.splitlines() if "PIT" in x or "ERROR" in x][-6:],
              sep="\n", flush=True)
        if code != 0:
            return 1
    code, output = _godot.window(["--path", str(_godot.PROJECT), "-s", "res://alien/lively_shots.gd", "--", res, still,
                                  str(out), str(static / f"{head}_mask.png"), base, str(HDRI), str(build_dir / "lively.json"),
                                  str(sclera), str(args.seconds), suffix], (1280, 720), 900)
    (out / f"godot_shots{suffix}.log").write_text(output, encoding="utf-8", newline="\n")
    print(f"godot shots: exit {code}", *[x for x in output.splitlines() if "LIVELY" in x or "ERROR" in x][-8:],
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
