"""`house`: checks the House map's layout data (layouts/house/*.toml) and generates its Godot scenes from the House
kit: one scene per room and per level and house.tscn (tools/runner/house_layout.py, docs/house.md)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .. import common, house_layout

NAME = "house"
HELP = "check the House layout (layouts/house/*.toml) and generate its room, level and house scenes from the kit"
DEFAULT_OUT = common.ROOT / "godot" / "import" / "house"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--layouts", type=Path, default=house_layout.LAYOUT_DIR, help="the layout folder")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="where the scenes go (default godot/import/house, res://import/house)")
    parser.add_argument("--check", action="store_true", help="only check the layout; write nothing")


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
    return 0
