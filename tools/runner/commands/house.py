"""`house`: checks the House map's layout data (layouts/house/*.toml) and generates its Godot scenes from the House
kit: one scene per room and per level and house.tscn (tools/runner/house_layout.py, docs/house.md)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .. import common, house_layout
from . import _frames, _godot

NAME = "house"
HELP = "check the House layout (layouts/house/*.toml) and generate its room, level and house scenes from the kit"
DEFAULT_OUT = common.ROOT / "godot" / "import" / "house"
WALK = "res://house/walk.gd"
WALK_TIMEOUT = 240


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--layouts", type=Path, default=house_layout.LAYOUT_DIR, help="the layout folder")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="where the scenes go (default godot/import/house, res://import/house)")
    parser.add_argument("--check", action="store_true", help="only check the layout; write nothing")
    parser.add_argument("--walk", type=Path, metavar="DIR",
                        help="stage the kit GLBs, import, then walk and shoot the house in an off-screen Godot window "
                             "into DIR (walk.json, sheet.png, exterior.png, stills)")


def run(args: argparse.Namespace) -> int:
    data = house_layout.load(args.layouts)
    problems = house_layout.validate(data)
    rooms = sum(len(lv["rooms"]) for lv in data["levels"])
    common.say(f"house layout: {len(data['levels'])} levels, {rooms} rooms, kit {data['settings']['kit_dir']}")
    if problems:
        for p in problems:
            common.say(f"  {p}")
        raise common.Failure(f"house layout: {len(problems)} problems")
    common.say("house layout: grid, openings, corners, footprints, stairs and holes hold")
    if args.check:
        return 0
    planned = house_layout.plan(data)
    summary = house_layout.write_scenes(data, planned, args.out)
    for name, s in summary["levels"].items():
        common.say(f"  {name}: {s['rooms']} rooms, {s['instances']} piece instances")
    report = common.OUT / "house" / "plan.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"summary": summary, "plan": planned}, indent=1), encoding="utf-8", newline="\n")
    common.say(f"house: {summary['instances']} instances of {len(summary['pieces'])} pieces -> {args.out.as_posix()}; "
               f"plan {report.as_posix()}")
    if args.walk:
        if args.out.resolve() != DEFAULT_OUT.resolve():
            raise common.Failure("--walk needs the scenes in godot/import/house (drop --out)")
        return walk(data, summary, args.walk.resolve())
    return 0


def walk(data: dict, summary: dict, folder: Path) -> int:
    """Stages the pieces the scenes use from the kit folder, imports them headless, then runs godot/house/walk.gd in a
    window off-screen (pictures need one): every doorway of the ground and upper floors and every flight, walked by
    a 1.36 m capsule; the stills, the plan, sheet.png and the exterior at dusk (exterior.png); draw calls per view."""
    kit = common.raw_dir() / data["settings"]["kit_dir"]
    names = {pid: f"kit_{pid}" for pid in summary["pieces"]}
    missing = [pid for pid in names if not (kit / f"{pid}.glb").is_file()]
    if missing:
        raise common.Failure(f"no {', '.join(sorted(missing))} in {kit.as_posix()} (build the kit first)")
    _godot.clear_staged(set(names.values()))
    for pid, name in names.items():
        _godot.stage(kit / f"{pid}.glb", name)
    errors = [line for line in _godot.import_project() if "ERROR" in line]
    for line in errors[:10]:
        common.say(f"  import: {line}")
    folder.mkdir(parents=True, exist_ok=True)
    req = common.OUT / "house" / "walk_request.json"
    request = house_layout.walk_request(data)
    for name in request["closed"]:
        common.say(f"  not walked (closed kit leaf): {name}")
    req.write_text(json.dumps(request, indent=1), encoding="utf-8", newline="\n")
    (folder / "walk.json").unlink(missing_ok=True)
    code, output = _godot.godot(["--path", _godot.PROJECT, "--audio-driver", "Dummy", "--position", _frames.POSITION,
                                 "--resolution", "1600x900", "-s", WALK, "--", req.as_posix(), folder.as_posix()],
                                WALK_TIMEOUT)
    if code != 0 or not (folder / "walk.json").is_file():
        tail = "\n".join(output.splitlines()[-20:])
        raise common.Failure(f"walk.gd failed (exit code {code}):\n{tail}")
    result = json.loads((folder / "walk.json").read_text(encoding="utf-8"))
    failed = [w for w in result["walks"] if not w["pass"]] + ([] if result["control"]["pass"] else [result["control"]])
    for w in result["walks"] + [result["control"]]:
        mark = "ok  " if w["pass"] else "FAIL"
        common.say(f"  {mark} {w['name']}: {'arrived' if w['arrived'] else 'stopped'} at {w['end']} "
                   f"({w['reached']}/{w['of']} points, {w['seconds']} s)")
    for name, info in result["shots"].items():
        common.say(f"  {name}: {info['draw_calls']} draw calls, {info['objects']} objects, {info['primitives']} primitives")
    common.say(f"  {result['instances']['mesh_instances']} mesh instances, {result['instances']['static_bodies']} bodies; "
               f"sheet {(folder / 'sheet.png').as_posix()}")
    if failed or errors:
        common.bad(f"house walk: {len(failed)} walks failed, {len(errors)} import errors")
        return 1
    common.ok(f"house walk: {len(result['walks'])} walks with a {2 * result['radius_m']:g} m capsule, the 1.5 m control stops")
    return 0
