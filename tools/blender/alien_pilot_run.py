"""The alien 3D pilot, step 2a (art #196): the driver (plain Python, outside Blender). Per head it builds the parts in
headless Blender (alien_pilot_head.py), checks both GLBs with glTF-Validator and shoots one picture in an off-screen
Godot window (godot/alien/pilot_shots.gd through the runner's _godot.window()). godot-check runs separately
(`tools/run.sh godot-check <glb>`). Inputs are read from the raw folder, never written.

    $PYTHON_BIN tools/blender/alien_pilot_run.py [--heads chameleon,axolotl] [--out DIR] [--no-build] [--no-shots]
        [--tag v2] [--prev DIR] [--rig] [--only-rig] [--rig-tag T] [--grid] [--grid-mouth] [--src-dir DIR]

--prev: an earlier build's views for the comparison sheet's middle row, "{head}" standing for the head
(e.g. .../step2a/{head}/v2/views). --rig (step 2b-1) runs alien_pilot_rig.py on the build: the face skeleton,
weights, blink and expression blend shapes, <head>_rig.glb and its review sheet; the validator and the Godot shot
then take the rigged GLB. --only-rig skips the head build and rigs the existing one.

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
    ap.add_argument("--prev", default=None, help="an earlier build's views/ for the middle row, {head} for the head")
    ap.add_argument("--rig", action="store_true", help="rig the build (step 2b-1)")
    ap.add_argument("--only-rig", action="store_true", help="rig the existing build, no head build")
    ap.add_argument("--rig-tag", default="", help="rig into <head>/<rig-tag>/; its sheet and shot copied up tagged")
    ap.add_argument("--grid", action="store_true", help="only the rig's variant grids (lips, expression amounts)")
    ap.add_argument("--grid-mouth", action="store_true", help="only the rig's mouth grid (2b-2)")
    ap.add_argument("--src-dir", type=Path, default=None,
                    help="rig the head build in <src-dir>/<head>/ (read only), writing into --out (2b-2)")
    args = ap.parse_args()
    summary = {}
    failed = False
    for head in args.heads.split(","):
        out = args.out / head / args.tag if args.tag else args.out / head
        out.mkdir(parents=True, exist_ok=True)
        if not args.no_build and not args.only_rig:
            extra = ["--smooth", args.smooth] if args.smooth else []
            if args.prev:
                extra += ["--prev-views", args.prev.format(head=head)]
            elif args.tag and (args.out / head / "views").is_dir():
                extra += ["--prev-views", str(args.out / head / "views")]
            result = blender.run_script("alien_pilot_head.py", ["--head", head, "--src", str(SRC[head]), "--view2d",
                                                        str(VIEWS[head]), "--expr", str(EXPR[head]), "--out", str(out),
                                                        *extra], timeout=1500)
            lines = [x for x in (result.stdout or "").splitlines() if x.startswith("PILOT ")]
            (out / "build.log").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
            print(f"built {head}", *lines[-3:], sep="\n", flush=True)
        glbs = [out / f"{head}.glb", out / f"{head}_lod1.glb"]
        if args.rig or args.only_rig or args.grid or args.grid_mouth:
            rig_out = out / args.rig_tag if args.rig_tag else out
            rig_out.mkdir(parents=True, exist_ok=True)
            src = args.src_dir / head if args.src_dir else out
            extra = (["--grid"] if args.grid else []) + (["--grid-mouth"] if args.grid_mouth else []) + (
                ["--suffix", f"_{args.rig_tag}"] if args.rig_tag else [])
            result = blender.run_script("alien_pilot_rig.py", ["--head", head, "--blend", str(src / f"{head}.blend"),
                                                       "--build", str(src / "build.json"), "--expr", str(EXPR[head]),
                                                       "--view2d", str(VIEWS[head]), "--out", str(rig_out), *extra],
                                        timeout=2400)
            lines = [x for x in (result.stdout or "").splitlines() if x.startswith("RIG ")]
            grid = args.grid or args.grid_mouth
            (rig_out / ("grid.log" if grid else "rig.log")).write_text("\n".join(lines) + "\n", encoding="utf-8",
                                                                           newline="\n")
            print(f"rigged {head} exit {result.returncode}", *lines[-4:], sep="\n", flush=True)
            if result.returncode:
                print((result.stderr or "")[-2000:], (result.stdout or "")[-3000:], sep="\n", flush=True)
                failed = True
            if grid:
                continue
            out = rig_out
            glbs = [out / f"{head}_rig.glb"]
        for glb in glbs:
            report = _export.validate(glb, out / f"{glb.stem}.validator.json")
            ok, text = _export.verdict(report)
            summary[glb.name] = text
            print(f"validator {glb.name}: {text}", flush=True)
        if not args.no_shots:
            res = _godot.stage(glbs[0], f"pilot_{head}")
            _godot.import_project()
            shot = out / f"{head}_godot.png"
            code, _ = _godot.window(["--path", str(_godot.PROJECT), "-s", "res://alien/pilot_shots.gd", "--", res,
                                     str(shot), "30"], (1024, 1024), 180, log=out / "godot_shot.log")
            print(f"godot shot {head}: exit {code} {shot}", flush=True)
            summary[f"{head}_godot"] = code
            failed = failed or code != 0
        if args.rig_tag:  # the rig's sheet and Godot shot copied up beside the head's earlier ones, the tag in the name
            for name, dst in ((f"{head}_rig_1280_{args.rig_tag}", f"{head}_rig_1280_{args.rig_tag}"),
                              (f"{head}_godot", f"{head}_godot_{args.rig_tag}")):
                if (out / f"{name}.png").exists():
                    shutil.copyfile(out / f"{name}.png", out.parent / f"{dst}.png")
        if args.tag:
            for name in (f"{head}_compare_1280", f"{head}_godot"):
                if (out / f"{name}.png").exists():
                    shutil.copyfile(out / f"{name}.png", args.out / head / f"{name}_{args.tag}.png")
    (args.out / f"run_summary{'_' + (args.tag or args.rig_tag) if (args.tag or args.rig_tag) else ''}{'_grid' if args.grid or args.grid_mouth else ''}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8", newline="\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
