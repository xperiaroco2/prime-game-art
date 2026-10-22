"""The alien 3D pilot, step 2a (art #196): the driver (plain Python, outside Blender). Per head it builds the parts in
headless Blender (alien_pilot_head.py), checks both GLBs with glTF-Validator and shoots one picture in an off-screen
Godot window (godot/alien/pilot_shots.gd through the runner's _godot.window()). godot-check runs separately
(`tools/run.sh godot-check <glb>`). Inputs are read from the raw folder, never written.

    $PYTHON_BIN tools/blender/alien_pilot_run.py [--heads chameleon,axolotl] [--out DIR] [--no-build] [--no-shots]
        [--tag v2]

--tag builds into <out>/<head>/<tag>/ (a build without a tag, or with the same tag, is overwritten), puts the earlier build's views in the
comparison sheet's middle row and copies the sheet and the Godot shot up as <head>_compare_1280_<tag>.png and
<head>_godot_<tag>.png.
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
SRC = {h: RAW / "2026-10-22-alien-pilot-3d" / h / "multi_image_to_3d-model.glb" for h in ("chameleon", "axolotl")}
VIEWS = {h: RAW / "2026-10-22-alien-pilot-3d" / "views" / h for h in ("chameleon", "axolotl")}
EXPR = {"chameleon": RAW / "2026-10-22-alien-pilot-2d" / "ch_expr" / "image-0.png",
        "axolotl": RAW / "2026-10-22-alien-pilot-2d" / "ax_expr" / "image-0.png"}
OUT = RAW / "research" / "2026-10-22-roster" / "design" / "pilot3d" / "step2a"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--heads", default="chameleon,axolotl")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--no-shots", action="store_true")
    ap.add_argument("--smooth", default=None, help="iterations,lambda for every head's smooth region")
    ap.add_argument("--tag", default="", help="build into <out>/<head>/<tag>/ and copy its sheets up with the tag")
    args = ap.parse_args()
    summary = {}
    failed = False
    for head in args.heads.split(","):
        out = args.out / head / args.tag if args.tag else args.out / head
        out.mkdir(parents=True, exist_ok=True)
        if not args.no_build:
            extra = ["--smooth", args.smooth] if args.smooth else []
            if args.tag and (args.out / head / "views").is_dir():
                extra += ["--prev-views", str(args.out / head / "views")]
            result = blender.run_script("alien_pilot_head.py", ["--head", head, "--src", str(SRC[head]), "--view2d",
                                                        str(VIEWS[head]), "--expr", str(EXPR[head]), "--out", str(out),
                                                        *extra], timeout=1500)
            lines = [x for x in (result.stdout or "").splitlines() if x.startswith("PILOT ")]
            (out / "build.log").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
            print(f"built {head}", *lines[-3:], sep="\n", flush=True)
        for glb in (out / f"{head}.glb", out / f"{head}_lod1.glb"):
            report = _export.validate(glb, out / f"{glb.stem}.validator.json")
            ok, text = _export.verdict(report)
            summary[glb.name] = text
            print(f"validator {glb.name}: {text}", flush=True)
        if not args.no_shots:
            res = _godot.stage(out / f"{head}.glb", f"pilot_{head}")
            _godot.import_project()
            shot = out / f"{head}_godot.png"
            code, _ = _godot.window(["--path", str(_godot.PROJECT), "-s", "res://alien/pilot_shots.gd", "--", res,
                                     str(shot), "30"], (1024, 1024), 180, log=out / "godot_shot.log")
            print(f"godot shot {head}: exit {code} {shot}", flush=True)
            summary[f"{head}_godot"] = code
            failed = failed or code != 0
        if args.tag:
            for name in (f"{head}_compare_1280", f"{head}_godot"):
                if (out / f"{name}.png").exists():
                    shutil.copyfile(out / f"{name}.png", args.out / head / f"{name}_{args.tag}.png")
    (args.out / (f"run_summary_{args.tag}.json" if args.tag else "run_summary.json")).write_text(json.dumps(summary, indent=2), encoding="utf-8", newline="\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
