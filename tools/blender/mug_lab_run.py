"""The mug lab (research: AI-only pipelines for release-quality props, the beer stein of art#392): the driver.
1. pipeline A: mug_lab_build.py in headless Blender (the stein from code, mug_lab.toml), unless --glb is given;
2. glTF-Validator on the GLB;
3. the Godot shots in an off-screen window (godot/mug_lab/shots.gd through the runner's _godot.window()), with the
   lab's shaders (mug_look.gd) or, with --plain, the GLB's own materials (an AI mesh as it comes);
4. the first-person drink clip, drink.mp4, from the frames (encode_clips.py in headless Blender).
Everything goes under <raw>/research/mug-lab/<tag>/.

    $PYTHON_BIN tools/blender/mug_lab_run.py --tag a1 [--glb FILE] [--plain] [--quick] [--no-build] [--bake]
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--glb", type=Path, help="shoot this GLB instead of building pipeline A's")
    ap.add_argument("--plain", action="store_true", help="the GLB's own materials, not the lab's shaders")
    ap.add_argument("--baseline-mats", action="store_true",
                    help="the art lane's first mug's plain materials on the GLB's meshes (the split's other half)")
    ap.add_argument("--shaders-on-glb", action="store_true",
                    help="the lab's glass and beer shaders on the GLB's mug_glass and mug_beer surfaces (the split)")
    ap.add_argument("--quick", action="store_true", help="the full state only, no drink clip")
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--spec", type=Path, default=ROOT / "tools" / "blender" / "mug_lab.toml")
    ap.add_argument("--bake", action="store_true", help="bake the glass in Cycles (mug_lab_bake.py) before the shots")
    ap.add_argument("--bake-res", type=int, default=1024)
    args = ap.parse_args()
    out = RAW / "research" / "mug-lab" / args.tag
    out.mkdir(parents=True, exist_ok=True)
    levels = {}
    if args.glb:
        glb = out / "mug.glb"
        if args.glb.resolve() != glb.resolve():
            shutil.copyfile(args.glb, glb)
        built = args.glb.parent / "build.json"   # mug_lab_ai.py's hybrid writes the levels its look needs
        if built.is_file():
            levels = json.loads(built.read_text(encoding="utf-8")).get("levels_cm", {})
    else:
        glb = out / "mug.glb"
        if not args.no_build:
            r = blender.run_script("mug_lab_build.py", ["--out", str(out), "--spec", str(args.spec)], timeout=600)
            print(*[x for x in (r.stdout or "").splitlines() if x.startswith("MUG_LAB")][-1:], sep="\n", flush=True)
        levels = json.loads((out / "build.json").read_text(encoding="utf-8"))["levels_cm"]
        if args.bake:
            r = blender.run_script("mug_lab_bake.py", ["--blend", str(out / "mug.blend"), "--out", str(out),
                                                       "--res", str(args.bake_res)], timeout=1500)
            print(*[x for x in (r.stdout or "").splitlines() if x.startswith("MUG_BAKE")][-1:], flush=True)
    report = _export.validate(glb, out / "mug.validator.json")
    ok, text = _export.verdict(report)
    print(f"validator: {text}", flush=True)
    res = _godot.stage(glb, f"mug_lab_{args.tag.replace('-', '_')}")
    _godot.import_project()
    shots = out / "godot"
    if shots.exists():
        shutil.rmtree(shots)
    shots.mkdir()
    code, output = _godot.window(["--path", str(_godot.PROJECT), "-s", "res://mug_lab/shots.gd", "--", res,
                                  str(shots), json.dumps(levels), "shaders_on_glb" if args.shaders_on_glb else ("baseline_mats" if args.baseline_mats else ("plain" if args.plain else "look")),
                                  "quick" if args.quick else "all"], (1280, 720), 1200, log=out / "godot_shots.log")
    print(*[x for x in output.splitlines() if x.startswith("MUGLAB") or "ERROR" in x or "SCRIPT" in x][:40], sep="\n")
    print(f"godot shots: exit {code} {shots}", flush=True)
    drink = shots / "drink"
    if code == 0 and drink.is_dir():
        blender.run_script("encode_clips.py", ["--frames", str(drink), "--out", str(shots), "--fps", "24"],
                           timeout=300)
        print(f"clip: {[p.name for p in shots.glob('*.mp4')]}", flush=True)
    return 0 if ok and code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
