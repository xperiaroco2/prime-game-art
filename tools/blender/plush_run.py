"""The vault plush (art#297): the driver (plain Python, outside Blender). From a Meshy multi-image-to-3D model it
cleans the mesh (plush_clean.py: welded, 0.30 m on the floor, 4,000 triangles, the dense model's normals baked),
repaints it to the concept (plush_paint.py: the albedo, the shader's mask, the plain-PBR GLB), checks the GLB with
glTF-Validator and shoots the review sheets in an off-screen Godot window (godot/plush/shots.gd through the runner's
_godot.window(), the material from godot/plush/plush.gd). Inputs are read from the raw folder, never written; the
outputs go under the batch folder's clean/, paint/ and paint/godot/.

    $PYTHON_BIN tools/blender/plush_run.py [--batch 2026-10-22-vault-plush-3d-2] [--no-build] [--no-shots]
        [--shells 12]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from runner import blender, common  # noqa: E402
from runner.commands import _export, _godot  # noqa: E402

RAW = common.raw_dir()
HDRI = RAW / "env" / "polyhaven" / "studio_small_09" / "studio_small_09_2k.hdr"  # CC0, sources/polyhaven_hdris_2k.toml
CONCEPT = RAW / "vault-plush" / "ref" / "final.jpg"


def lines(result, tag: str) -> list[str]:
    return [x for x in (result.stdout or "").splitlines() if x.startswith(tag)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", default="2026-10-22-vault-plush-3d-2")
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--no-shots", action="store_true")
    ap.add_argument("--shells", type=int, default=12)
    ap.add_argument("--tris", type=int, default=4000, help="the game mesh's triangles")
    ap.add_argument("--tag", default="", help="a suffix for the game folder, to keep a trial apart")
    args = ap.parse_args()
    base = RAW / args.batch
    # the full model is welded, sized and painted with Meshy's own UVs; only then is the game mesh decimated, with
    # fresh UVs, and the paint baked onto it (decimating Meshy's UVs in place pulled texels across islands: specks)
    clean, paint, game = base / "clean_full", base / "paint_full", base / f"game{args.tag}"
    if not args.no_build:
        r = blender.run_script("plush_clean.py", [str(base / "plush" / "multi_image_to_3d-model.glb"),
                                                  str(clean / "plush.glb"), "--height", "0.30", "--tris", "10000000"],
                               timeout=900)
        print(*lines(r, "PLUSH_CLEAN"), sep="\n", flush=True)
        # option A for the mouth (the engineer, 2026-10-23): the crease closed to a seam, the smile's line with curls
        r = blender.run_script("plush_mouth.py", [str(clean / "plush.glb"), str(clean / "plush_mouth.glb"),
                                                  str(clean / "smile.json")], timeout=900)
        print(*lines(r, "PLUSH_MOUTH"), sep="\n", flush=True)
        r = blender.run_script("plush_paint.py", [str(clean / "plush_mouth.glb"), str(paint),
                                                  "--smile", str(clean / "smile.json")], timeout=900)
        print(*lines(r, "PLUSH_PAINT"), sep="\n", flush=True)
        r = blender.run_script("plush_bake.py", [str(paint / "plush.glb"), str(paint / "plush_albedo.png"),
                                                 str(paint / "plush_mask.png"), str(game), "--tris", str(args.tris)],
                               timeout=1500)
        print(*lines(r, "PLUSH_BAKE"), sep="\n", flush=True)
    paint = game
    report = _export.validate(paint / "plush.glb", paint / "plush.validator.json")
    ok, text = _export.verdict(report)
    print(f"validator plush.glb: {text}", flush=True)
    code = 0
    if not args.no_shots:
        res = _godot.stage(paint / "plush.glb", f"vault_plush{args.tag.replace('-', '_')}")
        _godot.import_project()
        shots = paint / "godot"
        shots.mkdir(exist_ok=True)
        code, output = _godot.window(["--path", str(_godot.PROJECT), "-s", "res://plush/shots.gd", "--", res,
                                      str(shots), str(paint / "plush_albedo.png"), str(paint / "plush_normal.png"),
                                      str(paint / "plush_mask.png"), str(HDRI), str(CONCEPT), str(args.shells)],
                                     (1280, 720), 170, log=paint / "godot_shots.log")
        print(*[x for x in output.splitlines() if x.startswith("PLUSH ")], sep="\n")
        print(f"godot shots: exit {code} {shots}", flush=True)
    return 0 if ok and code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
