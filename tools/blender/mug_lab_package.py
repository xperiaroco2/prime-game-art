"""The research mug's asset folder (assets/prop/mug_research, the research branch only) from a mug lab build (plain
Python), baked or not. M8 ships the art lane's mug (assets/prop/mug); this packages the research's round-14 mug, which the
engineer found "more or less fine" (2026-11-23), as the pipeline's worked example.
From <raw>/research/mug-lab/<tag>/ (mug_lab_run.py --tag <tag> --bake):
- export/: mug.glb (the glass's baked map inside, as its base colour), mug_look.gd and the three shaders it preloads
  from its own folder (glass, beer, foam);
- source/mug.blend: the baked build (its map packed);
- report.json: triangles, bounds, Grip, levels, the bake, the GPU cost of the first-person view, glTF-Validator, the
  package check and the critics' last scores;
- manifest.toml (HANDOFF.md is written by hand).
--check stages export/ into godot/import/mug_pkg and runs godot/mug_lab/package_check.gd headless first; the folder is
written only when it passes.

    $PYTHON_BIN tools/blender/mug_lab_package.py --tag m1 [--asset assets/prop/mug] [--check]
        [--approved LOGIN DATE PR_URL]
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
from runner import common  # noqa: E402
from runner.commands import _godot  # noqa: E402

RAW = common.raw_dir()
LOOK = ("mug_look.gd", "glass.gdshader", "beer.gdshader", "foam.gdshader")
CONCEPT = "2026-11-23-lobby-mug-concepts/mug3_stein/image-0.png"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(build: Path) -> dict:
    stage = _godot.PROJECT / "import" / "mug_pkg"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    shutil.copyfile(build / "mug.glb", stage / "mug.glb")
    for name in LOOK:
        shutil.copyfile(ROOT / "godot" / "mug_lab" / name, stage / name)
    _godot.import_project()
    code, output = _godot.godot(["--headless", "--path", str(_godot.PROJECT), "-s", "res://mug_lab/package_check.gd",
                                 "--", "res://import/mug_pkg"], 300)
    line = next((x for x in output.splitlines() if x.startswith("PKGCHECK ")), None)
    if line is None:
        raise common.Failure("package_check.gd printed no PKGCHECK line:\n" + "\n".join(output.splitlines()[-20:]))
    result = json.loads(line[len("PKGCHECK "):])
    result["exit"] = code
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--asset", type=Path, default=Path("assets/prop/mug_research"))
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--approved", nargs=3, metavar=("LOGIN", "DATE", "PR_URL"))
    args = ap.parse_args()
    build = RAW / "research" / "mug-lab" / args.tag
    for f in ("mug.glb", "mug.blend", "build.json", "mug.validator.json", "godot/cost.json"):
        if not (build / f).is_file():
            raise common.Failure(f"{build / f} is missing: run mug_lab_run.py --tag {args.tag} first")
    blend = "mug_baked.blend" if (build / "mug_baked.blend").is_file() else "mug.blend"   # --bake builds bake
    pkg = check(build) if args.check else None
    if pkg is not None:
        print("package check: " + json.dumps(pkg), flush=True)
        if pkg["problems"] or pkg["exit"] != 0:
            print("package check failed; the asset folder is not written", flush=True)
            return 1
    asset = args.asset if args.asset.is_absolute() else ROOT / args.asset
    (asset / "export").mkdir(parents=True, exist_ok=True)
    (asset / "source").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(build / "mug.glb", asset / "export" / "mug.glb")
    for name in LOOK:
        shutil.copyfile(ROOT / "godot" / "mug_lab" / name, asset / "export" / name)
    shutil.copyfile(build / blend, asset / "source" / "mug.blend")
    b = json.loads((build / "build.json").read_text(encoding="utf-8"))
    bake = json.loads((build / "bake.json").read_text(encoding="utf-8")) if (build / "bake.json").is_file() else None
    cost = json.loads((build / "godot" / "cost.json").read_text(encoding="utf-8"))
    val = json.loads((build / "mug.validator.json").read_text(encoding="utf-8")).get("issues", {})
    critic = RAW / "research" / "mug-lab" / "critic"
    scores = {}
    for name in ("r14a_b35_opus.json", "r14b_b35_opus.json"):
        p = critic / name
        if p.is_file():
            scores[name] = json.loads(p.read_text(encoding="utf-8")).get("scores")
    report = {
        "asset": "mug_research",
        "built_by": f"tools/blender/mug_lab_run.py --tag {args.tag}{' --bake' if bake else ''}; tools/blender/mug_lab_package.py --tag {args.tag}",
        "mesh": {"triangles": b["triangles"], "by_mesh": b["by_mesh"], "budget_triangles": 10000,
                 "levels_cm": b["levels_cm"], "front": "+Z (the holder's side)", "handle": "+X",
                 "origin": "the middle of the base's underside"},
        "bake": bake,
        "states": {"full": "mug_look.gd set_fill(look, 1.0)", "half": "set_fill(look, 0.5)",
                   "empty": "set_fill(look, 0.0): Beer hidden, lacing on the glass"},
        "gltf_validator": {k: val.get(k, 0) for k in ("numErrors", "numWarnings", "numInfos", "numHints")},
        "godot_gpu_ms_first_person_1280x720": cost,
        "package_check": pkg,
        "critics_round_14_opus": scores,
        "review": f"<raw>/research/mug-lab/{args.tag}/godot/ and https://claude.ai/artifact/8JSFkeqdCA2EQuhnnDc2vU",
    }
    (asset / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    raws = [CONCEPT, f"research/mug-lab/{args.tag}/mug.glb", f"research/mug-lab/{args.tag}/{blend}"]
    today = datetime.date.today().isoformat()
    login, date, pr = args.approved if args.approved else (None, None, None)
    lines = [
        "# The AI-art pipeline research's round-14 mug of beer (art#392 follow-up), packaged on the research branch only:",
        "# M8 ships the art lane's mug (assets/prop/mug). The engineer found this one \"more or less fine\" (2026-11-23).",
        f"# Built by tools/blender/mug_lab_run.py --tag {args.tag} and",
        f"# tools/blender/mug_lab_package.py --tag {args.tag}; a rebuild changes the hashes below.",
        'id = "mug_research"',
        'kind = "prop"',
        'slot = ""',
        'title = "Mug of beer (pipeline research)"',
        'notes = "A faceted glass stein of beer, 15 cm tall and 9 cm across, the handle on +X reaching 8 cm, the foam head '
        f'to 18.2 cm; {b["triangles"]:,} triangles (glass {b["by_mesh"]["Mug"]:,}, beer {b["by_mesh"]["Liquid"]:,}, foam '
        f'{b["by_mesh"]["Foam"]:,}; the held-prop budget 10,000). Meshes Mug and Beer (holding Liquid and Foam), the Grip '
        'marker; origin at the middle of the base underside. The look is export/mug_look.gd with three shaders, as the '
        'engineer approved it in round 14 (set_fill 1 full, 0.5, 0 empty; HANDOFF.md); no baked map. Built from code in headless Blender (mug_lab_build.py, mug_lab.toml): no part of the model '
        'was generated or downloaded. The concept the engineer picked (art#392 concept 3, gpt-image-2.5-sunburst, batch '
        '2026-11-23-lobby-mug-concepts) was a reference for the shape and, measured by script, for the colours."',
        'tools = ["blender 5.2.2", "prime-game-art mug_lab_build.py, mug_lab_run.py, mug_lab_package.py", "glTF-Validator 2.0.0-dev.3.10", "Godot 4.7.2 (shots, package check)"]',
        'licence = "own-work"',
        'licence_url = "https://github.com/xperiaroco2/prime-game"',
        "public_repo_ok = true",
        "ai_generated = false",
        f'approved_by = ["{login}"]' if login else "approved_by = []",
        f"approved_at = {date}" if date else 'approved_at = ""',
        f'approval_pr = "{pr}"' if pr else 'approval_pr = ""',
        "",
        "[source]",
        'service = "own"',
        'plan = "own-work"',
        'model_version = ""',
        "task_ids = []",
        f"generated_at = {today}",
        'url = "https://github.com/xperiaroco2/prime-game-art/issues/392"',
    ]
    for r in raws:
        lines += ["", "[[raw]]", f'file = "{r}"', f'sha256 = "{sha256(RAW / r)}"']
    (asset / "manifest.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"asset: {asset}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except common.Failure as e:
        print(f"FAILED: {e}", file=sys.stderr)
        raise SystemExit(1)
