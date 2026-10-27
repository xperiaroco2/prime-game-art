"""The ship engine's energy crystal (art#263's station props): the driver (plain Python, outside Blender).
1. crystal_build.py in headless Blender: the model from code, the GLB (the plain-PBR fallback), the .blend with the
   look materials, build.json, and the Blender review renders of both states;
2. glTF-Validator on the GLB;
3. crystal_drawing.py: the engineering drawing (front, side, top in cm) over the concept's views and the model's
   orthographic renders, into <tag>/drawing/;
4. the Godot shots and the review sheet in an off-screen window (godot/crystal/shots.gd through the runner's
   _godot.window(); the look from godot/crystal/crystal.gd), beside the concept's crops.
Everything goes under <raw>/energy-crystal/<tag>/: the build, renders/ (Blender) and godot/ (the shots, sheet.png).
--asset DIR then writes the asset folder (assets/prop/energy_crystal): the GLB and the material files in export/,
the .blend in source/, report.json and manifest.toml with the raw files' hashes.
The concept's crops are read from <raw>/energy-crystal/ref/ (the originals are prime-game-design's
ideas/ship-components/cartridge-v2/socket-claws.jpg and charge.jpg, copied there).

    $PYTHON_BIN tools/blender/crystal_run.py [--tag build] [--no-build] [--no-shots] [--res 900] [--samples 64]
        [--asset assets/prop/energy_crystal]
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from runner import blender, common  # noqa: E402
from runner.commands import _export, _godot  # noqa: E402

import crystal_drawing  # noqa: E402  (beside this file)

RAW = common.raw_dir()
REF = RAW / "energy-crystal" / "ref"
MATERIAL_FILES = ("crystal.gd", "crystal_shell.gdshader", "crystal_core.gdshader", "crystal_metal.gdshader")
HDRI = RAW / "env" / "polyhaven" / "studio_small_09" / "studio_small_09_2k.hdr"  # CC0, sources/polyhaven_hdris_2k.toml


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="build", help="the output folder under <raw>/energy-crystal/")
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--no-shots", action="store_true")
    ap.add_argument("--res", type=int, default=900, help="the Blender renders' size in pixels")
    ap.add_argument("--samples", type=int, default=64, help="the Blender renders' EEVEE samples")
    ap.add_argument("--asset", type=Path, help="write the asset folder here from this build")
    ap.add_argument("--approved", nargs=3, metavar=("LOGIN", "DATE", "PR_URL"),
                    help="the look's approval for the manifest (docs/manifest.md: all three together)")
    args = ap.parse_args()
    if args.asset and args.no_shots:
        ap.error("--asset needs this run's shots (report.json takes their GPU cost)")
    out = RAW / "energy-crystal" / args.tag
    renders = out / "renders"
    if not args.no_build:
        r = blender.run_script("crystal_build.py", ["--out", str(out), "--render", str(renders), "--res",
                                                    str(args.res), "--samples", str(args.samples),
                                                    "--views", str(REF / "crystal-views.jpg")], timeout=1200)
        print(*[x for x in (r.stdout or "").splitlines() if x.startswith("CRYSTAL_BUILD")], sep="\n", flush=True)
    if (out / "features.json").is_file():  # the engineering drawing over the concept's views and the model's
        sys.argv[1:] = [str(out)]
        crystal_drawing.main()
    glb = out / "energy_crystal.glb"
    report = _export.validate(glb, out / "energy_crystal.validator.json")
    ok, text = _export.verdict(report)
    print(f"validator energy_crystal.glb: {text}", flush=True)
    code = 0
    if not args.no_shots:
        res = _godot.stage(glb, f"energy_crystal_{args.tag.replace('-', '_')}")
        _godot.import_project()
        shots = out / "godot"
        shots.mkdir(exist_ok=True)
        code, output = _godot.window(["--path", str(_godot.PROJECT), "-s", "res://crystal/shots.gd", "--", res,
                                      str(shots), str(renders), str(REF / "views_charged.png"),
                                      str(REF / "views_spent.png"), str(REF / "concept_charger.png"), str(HDRI)],
                                     (1280, 720), 300, log=out / "godot_shots.log")
        print(*[x for x in output.splitlines() if x.startswith("CRYSTAL ")], sep="\n")
        print(f"godot shots: exit {code} {shots}", flush=True)
    if args.asset and ok and code == 0:
        write_asset(args.asset, out, args.tag, report, args.approved)
        print(f"asset: {args.asset}", flush=True)
    return 0 if ok and code == 0 else 1


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_asset(asset: Path, out: Path, tag: str, validator: dict, approved: list | None = None) -> None:
    """The asset folder from the build in out: export/ (the GLB, the Godot look's files), source/ (the .blend),
    report.json, manifest.toml (HANDOFF.md is written by hand)."""
    asset = asset if asset.is_absolute() else ROOT / asset
    (asset / "export").mkdir(parents=True, exist_ok=True)
    (asset / "source").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(out / "energy_crystal.glb", asset / "export" / "energy_crystal.glb")
    shutil.copyfile(out / "energy_crystal.blend", asset / "source" / "energy_crystal.blend")
    for name in MATERIAL_FILES:
        shutil.copyfile(ROOT / "godot" / "crystal" / name, asset / "export" / name)
    build = json.loads((out / "build.json").read_text(encoding="utf-8"))
    cost = json.loads((out / "godot" / "cost.json").read_text(encoding="utf-8"))
    counts = validator.get("issues", {})
    size = build["size_m"]  # Blender axes: x, y (depth), z (height)
    report = {
        "asset": "energy_crystal",
        "built_by": f"tools/blender/crystal_run.py --tag {tag} --asset {asset.relative_to(ROOT).as_posix()}",
        "mesh": {"triangles": build["triangles"], "vertices": build["vertices"],
                 "triangles_by_material": build["triangles_by_material"],
                 "triangles_by_part": build["triangles_by_part"],
                 "size_m": size, "budget_class": "hero", "budget_triangles": 4000, "front": "+Z",
                 "origin": "the crystal's tip, its lowest point, under its middle"},
        "states": {"charged": "crystal.gd set_charge(look, 1.0)", "spent": "set_charge(look, 0.0)"},
        "gltf_validator": {k: counts.get(k, 0) for k in ("numErrors", "numWarnings", "numInfos", "numHints")},
        "godot_gpu_ms_hand_view_1280x720": cost,
        "review": f"<raw>/energy-crystal/{tag}/godot/sheet.png",
    }
    (asset / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    raws = ["energy-crystal/ref/crystal-views.jpg", "energy-crystal/ref/socket-claws.jpg", "energy-crystal/ref/charge.jpg",
            f"energy-crystal/{tag}/energy_crystal.glb", f"energy-crystal/{tag}/energy_crystal.blend"]
    today = datetime.date.today().isoformat()
    lines = [
        "# The ship engine's energy crystal (art#263's station props; the cartridge of xperiaroco2/prime-game#1033).",
        f"# Built by tools/blender/crystal_run.py --tag {tag} --asset {asset.relative_to(ROOT).as_posix()}; a rebuild",
        "# changes the hashes below.",
        'id = "energy_crystal"',
        'kind = "prop"',
        'slot = ""',
        "title = \"The ship engine's energy crystal\"",
        ("notes = \"The engine's cartridge: "
         'a faceted energy crystal in a bronze and graphite cap with a hexagonal carry '
         f'loop, {size[2]:.3f} m tall, {size[0]:.3f} x {size[1]:.3f} m across the octagonal cap, one mesh of '
         f'{build["triangles"]:,} '
         'triangles in five surfaces (hero class), front +Z, origin at the tip. Two states on one mesh: '
         'export/crystal.gd set_charge (1 charged, 0 spent; HANDOFF.md). From the concept the engineer picked '
         '(prime-game#1033 comment 6361383461; prime-game-design ideas/ship-components/cartridge-v2: crystal-views.jpg, the '
         'straight views its drawing tools/blender/crystal_dims.toml was measured from, and socket-claws.jpg and charge.jpg, '
         'copied to the raw folder; 2D concepts used only as references), built from code in '
         'headless Blender (tools/blender/crystal_build.py): no part of the model was generated or downloaded."'),
        'tools = ["blender 5.2.2", "prime-game-art crystal_build.py, crystal_run.py", '
        '"glTF-Validator 2.0.0-dev.3.10", "Godot 4.7.2 (shots)"]',
        'licence = "own-work"',
        'licence_url = "https://github.com/xperiaroco2/prime-game"',
        "public_repo_ok = true",
        "ai_generated = false",
        f'approved_by = ["{approved[0]}"]' if approved else "approved_by = []",
        f"approved_at = {approved[1]}" if approved else 'approved_at = ""',
        f'approval_pr = "{approved[2]}"' if approved else 'approval_pr = ""',
        "",
        "[source]",
        'service = "own"',
        'plan = "own-work"',
        'model_version = ""',
        "task_ids = []",
        f"generated_at = {today}",
        'url = "https://github.com/xperiaroco2/prime-game-art/issues/263"',
    ]
    for rel in raws:
        lines += ["", "[[raw]]", f'file = "{rel}"', f'sha256 = "{sha256(RAW / rel)}"']
    (asset / "manifest.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
