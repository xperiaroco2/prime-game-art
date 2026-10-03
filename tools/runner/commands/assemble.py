"""`assemble`: characters from an Ultimate Modular recipe (recipes/, docs/assembly.md), built, posed, measured and
rendered in headless Blender; with --blend one clean .blend per character, the input of the glTF export."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .. import blender, common
from . import _assembly

NAME = "assemble"
HELP = "assemble Ultimate Modular characters from a recipe: renders, build_report.json, --blend files (docs/assembly.md)"
TIMEOUT = 3600


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("recipe", help="a recipe file, or its name in recipes/ (um_final_test)")
    parser.add_argument("--ids", default="", help="comma list of character ids to build (default: all)")
    parser.add_argument(
        "--modes", default="",
        help="comma list of chars, face, hands, lineup, crossgender, qa, ankles, or none (default: the recipe's "
             "modes, else chars,face,hands,lineup,crossgender)",
    )  # fmt: skip
    parser.add_argument("--out", type=Path, help="output folder (default tools/out/assemble/<recipe>/)")
    parser.add_argument("--blend", action="store_true", help="also save blend/<id>.blend and blend/<id>.json")
    parser.add_argument("--res", type=int, default=100, help="render size in percent (default 100; tests use less)")
    parser.add_argument(
        "--compare", type=Path, metavar="REPORT",
        help="a reference build_report.json: list the differences and fail on any outside the tolerances",
    )  # fmt: skip


def run(args: argparse.Namespace) -> int:
    path = _assembly.find_recipe(args.recipe)
    recipes = _assembly.recipe_module()
    raw = common.raw_dir()
    try:
        recipe = recipes.load(path, raw)
    except recipes.RecipeError as exc:
        raise common.Failure(str(exc)) from exc
    ids = [i for i in args.ids.split(",") if i]
    known = [c["id"] for c in recipe["characters"]]
    if any(i not in known for i in ids):
        raise common.Failure(f"unknown ids {', '.join(i for i in ids if i not in known)}; {path.name} has: {', '.join(known)}")
    modes = [m for m in args.modes.split(",") if m]
    if modes != ["none"] and any(m not in recipes.MODES for m in modes):
        bad = ", ".join(m for m in modes if m not in recipes.MODES)
        raise common.Failure(f"unknown modes {bad}; use {', '.join(recipes.MODES)} or none")
    if not 5 <= args.res <= 100:
        raise common.Failure("--res must be from 5 to 100 (percent)")
    reference = None
    if args.compare:
        if not args.compare.is_file():
            raise common.Failure(f"no reference report {args.compare}")
        reference = json.loads(args.compare.read_text(encoding="utf-8"))

    out = (args.out or common.OUT / "assemble" / path.stem).resolve()
    script_args = ["--recipe", str(path), "--raw", str(raw), "--out", str(out), "--res", str(args.res)]
    if ids:
        script_args += ["--ids", ",".join(ids)]
    if modes:
        script_args += ["--modes", ",".join(modes)]
    if args.blend:
        script_args.append("--blend")
    common.say(f"assemble: {path.name} ({', '.join(ids) or 'every character'}) -> {out.as_posix()}")
    blender.run_script(_assembly.SCRIPT, script_args, timeout=TIMEOUT)

    report_path = out / "build_report.json"
    if not report_path.is_file():
        raise common.Failure(f"{_assembly.SCRIPT} wrote no {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    for line in _assembly.summary(report):
        common.say(f"  {line}")
    common.say(f"report: {report_path.as_posix()}")
    if args.blend:
        for cid in report["characters"]:
            sidecar = json.loads((out / "blend" / f"{cid}.json").read_text(encoding="utf-8"))
            seen = sidecar.get("inspected", {})
            common.ok(f"blend/{cid}.blend: {len(seen.get('objects', {}))} objects, {len(seen.get('actions', {}))} "
                      f"actions, feet at z {sidecar['feet_z_m']} m, transform check {sidecar['transform_check_max_error_m']} m")
    if reference is not None:
        problems = _assembly.compare(reference, report)
        for line in problems:
            common.bad(line)
        if problems:
            raise common.Failure(f"{len(problems)} difference(s) from {args.compare}")
        common.ok(f"matches {args.compare.as_posix()} for {', '.join(report['characters'])}")
    return 0
