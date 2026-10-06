"""`anim-set`: builds an animation set (art #33; docs/animations.md, "Animation sets") per body type: every clip of
the set's settings from its source through its edit steps, saved with the body type's donor, exported to GLB and
checked by godot-check and the set's own checks (lengths, loop modes, closed loops in place)."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .. import blender, common
from . import _anim, _anim_set, _godot, anim_review, export, godot_check

NAME = "anim-set"
HELP = "build an animation set (the MVP) per body type: clips from their sources and edits, GLB export, godot-check"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--set", default="mvp", help="a set of the review settings' [sets] (default mvp)")
    parser.add_argument("--body", choices=(*_anim.BODIES, "both"), default="both", help="body type (default both)")
    parser.add_argument("--clips", default="all",
                        help="comma-separated clip names, built with the clips they are made from (default all); a "
                             "partial build is checked, not saved or exported, its reports in <out>/<body>/partial/")
    parser.add_argument("--out", type=Path, help="output folder (default <raw>/anim-sets/<set>); each body type in "
                                                 "<out>/<body>/")
    parser.add_argument("--no-export", action="store_true", help="build, save and check the .blend only")
    parser.add_argument("--no-godot", action="store_true", help="skip godot-check")


def build(cfg: dict, set_path: Path, body: str, out: Path, clips: str) -> dict:
    report_path = out / "build_report.json"
    report_path.unlink(missing_ok=True)
    args = ["--set", str(set_path), *anim_review.body_args(cfg, body), "--out", str(out), "--clips", clips]
    if clips != "all":
        args.append("--no-save")
    blender.run_script("anim_set.py", args, timeout=7200)
    if not report_path.is_file():
        raise common.Failure(f"anim_set.py wrote no {report_path}")
    return json.loads(report_path.read_text(encoding="utf-8"))


def run(args: argparse.Namespace) -> int:
    cfg = _anim.load_config()
    set_path, data = _anim_set.load(cfg, args.set)
    names = _anim_set.selected(data, args.clips)
    bodies = list(_anim.BODIES) if args.body == "both" else [args.body]
    root = (args.out or common.raw_dir() / "anim-sets" / args.set).resolve()
    # a partial build reports beside, not over, the full build's reports (they describe the saved .blend and GLB)
    outs = {body: root / body / ("partial" if args.clips != "all" else "") for body in bodies}
    for out in outs.values():
        out.mkdir(parents=True, exist_ok=True)
    common.say(f"anim-set {args.set}: {len(names)} clips of {set_path.name} on {', '.join(bodies)} -> {root}")
    with ThreadPoolExecutor(max_workers=len(bodies)) as pool:
        futures = {body: pool.submit(build, cfg, set_path, body, outs[body], args.clips) for body in bodies}
        reports = {body: f.result() for body, f in futures.items()}
    failed = False
    glbs = {}
    for body in bodies:
        report, out = reports[body], outs[body]
        (out / "build.md").write_text(_anim_set.table(report), encoding="utf-8")
        common.say(f"{body}: {len(report['clips'])} clips built in {report['seconds_spent']} s -> {out / 'build.md'}")
        # Blender reports the clips asked for; the ones they are made from are built but not reported
        problems = _anim_set.check_build(report, data, _anim_set.reported(data, args.clips))
        for p in problems:
            common.bad(f"{body} build: {p}")
        if not problems:
            common.ok(f"{body} build: every clip as long as its frames, every loop closed and in place")
        for w in _anim_set.warnings(report):
            common.warn(f"{body} {w}")
        failed |= bool(problems)
        if args.clips != "all" or args.no_export:
            continue
        saved = report["saved"]
        common.ok(f"{body}: saved {saved['blend']} ({len(saved['actions'])} actions, {saved['bones']} bones, the "
                  f"transforms applied within {saved['transform_check_max_error_mm']} mm)")
        blend = Path(saved["blend"])
        if not export.export_one(blend, out):
            failed = True
        glb = out / f"{blend.stem}.glb"
        info = json.loads((out / f"{blend.stem}.export.json").read_text(encoding="utf-8"))
        problems = _anim_set.check_export(info, report)
        for p in problems:
            common.bad(f"{body} export: {p}")
        if not problems:
            common.ok(f"{body} export: {len(report['exported'])} clips at 30 fps, every loop closed")
        failed |= bool(problems)
        glbs[body] = glb
    if glbs and not args.no_godot:
        failed |= not godot(glbs, reports, outs)
    return 1 if failed else 0


def godot(glbs: dict[str, Path], reports: dict[str, dict], outs: dict[str, Path]) -> bool:
    """godot-check on the set's GLBs (one import, headless), then the set's checks on Godot's animations."""
    contract = _godot.load_contract()
    _godot.clear_staged({g.stem for g in glbs.values()})
    staged = {body: _godot.stage(glb, params=_godot.import_params(glb)) for body, glb in glbs.items()}
    common.say(f"godot-check: importing {', '.join(g.name for g in glbs.values())} (headless)")
    import_lines = _godot.import_project()
    good = True
    for body, glb in glbs.items():
        out = outs[body] / "godot-check"
        godot_check.check_one(glb, staged[body], out, contract, import_lines, False, list(staged.values()))
        result = json.loads((out / "report.json").read_text(encoding="utf-8"))
        fails = [c for c in result["checks"] if c["status"] == "fail" and not _anim_set.donor_facing(c)]
        if any(_anim_set.donor_facing(c) for c in result["checks"]):
            common.warn(f"{body}: facing_plus_z cannot tell on the pack donor, whose parts are not named by role "
                        f"(_eyes, _shoes); the set keeps the donor's rest, which faces -Y in Blender (+Z in glTF)")
        good &= not fails
        problems = _anim_set.check_godot(result, reports[body])
        for p in problems:
            common.bad(f"{body} in Godot: {p}")
        if not problems:
            loops = sum(reports[body]["clips"][n]["loop"] for n in reports[body]["exported"])
            common.ok(f"{body} in Godot: {len(reports[body]['exported'])} animations as long as built; {loops} loops "
                      f"import LINEAR without their _Loop suffix, the one-shots play once")
        good &= not problems
    return good
