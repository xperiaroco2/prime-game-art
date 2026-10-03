"""`export`: a saved character (.blend from `assemble --blend`) to a glTF 2.0 binary with fixed options, checked against
what Blender exported and by the pinned glTF-Validator (docs/godot.md)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .. import blender, common
from . import _export

NAME = "export"
HELP = "export saved characters (.blend from assemble --blend) to GLB with fixed options; glTF-Validator report.json"
TIMEOUT = 600


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("blend", type=Path, nargs="+", help="saved character files (assemble --blend writes blend/<id>.blend)")
    parser.add_argument("--out", type=Path, help="output folder; each character goes into <out>/<id>/ (default tools/out/export/)")


def run(args: argparse.Namespace) -> int:
    blends = []
    for path in args.blend:
        candidate = path if path.is_file() else common.ROOT / path
        if not candidate.is_file() or candidate.suffix.lower() != ".blend":
            raise common.Failure(f"no saved character file {path.as_posix()} (a .blend from `assemble --blend`)")
        blends.append(candidate.resolve())
    failed = 0
    for blend in blends:
        failed += not export_one(blend, (args.out or _export.OUT).resolve() / blend.stem)
    return 1 if failed else 0


def export_one(blend: Path, out: Path) -> bool:
    cid = blend.stem
    glb, info_path, report_path = out / f"{cid}.glb", out / f"{cid}.export.json", out / "report.json"
    out.mkdir(parents=True, exist_ok=True)
    for stale in (glb, info_path, report_path):
        stale.unlink(missing_ok=True)
    common.say(f"export: {blend.as_posix()} -> {glb.as_posix()}")
    blender.run_script(_export.SCRIPT, ["--blend", str(blend), "--glb", str(glb), "--json", str(info_path)], timeout=TIMEOUT)
    if not glb.is_file() or not info_path.is_file():
        raise common.Failure(f"{_export.SCRIPT} wrote no {glb.name} or {info_path.name}")
    info = json.loads(info_path.read_text(encoding="utf-8"))
    summary = _export.summarize(_export.glb_json(glb))
    good = True
    problems = _export.check(info, summary)
    for problem in problems:
        common.bad(problem)
        good = False
    if not problems:
        common.ok(f"{len(summary['meshes'])} skinned mesh nodes ({', '.join(sorted(summary['meshes']))}), one skin of "
                  f"{len(summary['skins'][0])} joints, {len(summary['animations'])} animations, "
                  f"{len(summary['materials'])} materials; {glb.stat().st_size / 1e6:.2f} MB")
    report = _export.validate(glb, report_path)
    found = _export.issues(report)
    passed, line = _export.verdict(report)
    line += f" -> {report_path.as_posix()}"
    if not passed:
        common.bad(line)
        for message in found["error"][:20]:
            common.say(f"        {message}")
        good = False
    else:
        common.ok(line)
    for message in found["warning"][:20]:
        common.warn(message)
    common.say(f"  height {info['height_m']} m, feet at y {info['feet_y_m']} m (glTF axes, rest pose)")
    return good
