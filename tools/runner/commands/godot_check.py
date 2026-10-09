"""`godot-check`: imports exported characters into the art repo's Godot 4.7.2 project (godot/) headless and asserts what
the game needs: one Skeleton3D with the rig's bones, every part a separate MeshInstance3D skinned to it, every action an
animation whose tracks resolve and whose bones move, the size, the feet at y = 0 and the front +Z (docs/godot.md)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .. import common
from . import _godot

NAME = "godot-check"
HELP = "import exported character GLBs into Godot 4.7.2 headless and assert skeleton, parts, animations (docs/godot.md)"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("glb", type=Path, nargs="+", help="GLB files from `export` (their .export.json beside them adds Blender's numbers)")
    parser.add_argument("--out", type=Path, help="report folder; each GLB gets <out>/<stem>/ (default tools/out/godot-check/)")
    parser.add_argument("--strict-contract", action="store_true",
                        help="fail on the contract v1 body gates (height, eyes) with the contract's own severities")
    parser.add_argument("--humanoid", action="store_true",
                        help="also the trial: import with a BoneMap to SkeletonProfileHumanoid and report what maps and works")
    parser.add_argument("--textured", action="store_true",
                        help="a baked clay character (export --textured): textures, normal maps, sizes and surfaces "
                             "checked instead of flat colours")


def run(args: argparse.Namespace) -> int:
    glbs = []
    for path in args.glb:
        candidate = path if path.is_file() else common.ROOT / path
        if not candidate.is_file() or candidate.suffix.lower() != ".glb":
            raise common.Failure(f"no GLB {path.as_posix()}")
        glbs.append(candidate.resolve())
    contract = _godot.load_contract()
    _godot.clear_staged({g.stem for g in glbs})
    staged = {glb: _godot.stage(glb, params=_godot.import_params(glb)) for glb in glbs}
    common.say(f"godot-check: importing {', '.join(g.name for g in glbs)} into {_godot.PROJECT.as_posix()} (headless)")
    import_lines = _godot.import_project()
    failed = 0
    for glb, res_path in staged.items():
        out = (args.out or _godot.OUT).resolve() / glb.stem
        failed += not check_one(glb, res_path, out, contract, import_lines, args.strict_contract, list(staged.values()),
                            args.textured)
    if args.humanoid:
        from . import _humanoid

        for glb in glbs:
            out = (args.out or _godot.OUT).resolve() / glb.stem
            _humanoid.trial(glb, out, contract)
    return 1 if failed else 0


def check_one(glb: Path, res_path: str, out: Path, contract: dict, import_lines: list[str], strict: bool,
              staged: list[str], textured: bool = False) -> bool:
    expect = _godot.expectations(glb)
    dump, lines = _godot.inspect(res_path, out / "inspect.json")
    mine = _godot.lines_for(import_lines, res_path, staged)
    output = mine + lines
    checks = _godot.evaluate(dump, expect, contract, output, strict_contract=strict, textured=textured)
    failed = [c for c in checks if c["status"] == "fail"]
    report = {
        "glb": glb.as_posix(),
        "res_path": res_path,
        "godot": dump["godot"],
        "expectations_from": expect["source"],
        "passed": not failed,
        "checks": checks,
        "godot_output": output,
        "skeleton": dump["skeletons"][0]["path"] if dump["skeletons"] else None,
        "parts": {m["name"]: {"vertices": m["vertices"], "surfaces": m["surfaces"], "binds": len(m["binds"]),
                              "rest_bounds": m["rest_bounds"], "materials": m["materials"]} for m in dump["meshes"]},
        "animations": {name: {k: a.get(k) for k in ("length", "loop_mode", "tracks", "track_types", "position_tracks", "motion")}
                       for p in dump["players"] for name, a in p["animations"].items()},
    }
    (out / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    common.say(f"{glb.name} in {dump['godot']}:")
    for c in checks:
        {"pass": common.ok, "warn": common.warn}.get(c["status"], common.bad)(f"{c['check']}: {c['detail']}")
    for line in output:
        common.say(f"        godot: {line}")
    common.say(f"report: {(out / 'report.json').as_posix()}")
    return not failed
