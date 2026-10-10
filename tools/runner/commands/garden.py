"""`garden`: checks the garden and the greenhouse's roof (layouts/house/outdoor/garden.toml, house_garden.py) and
writes the seeded scatter, the glass roof's placements, the herb route and a top-down plan (docs/house-garden.md)."""

from __future__ import annotations

import argparse
from pathlib import Path

from .. import common, house_garden, house_layout, house_outdoor

NAME = "garden"
HELP = "check the garden and the greenhouse roof (layouts/house/outdoor/garden.toml); write the scatter and a plan"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--check", action="store_true", help="only validate; write nothing")
    parser.add_argument("--out", type=Path, help="output folder (default <raw>/house/80/build)")


def run(args: argparse.Namespace) -> int:
    data, plot, layout = house_garden.load(), house_outdoor.load(), house_layout.load()
    if args.check:
        rep = house_garden.build(data, plot, layout)
    else:
        out = (args.out or common.raw_dir() / "house" / "80" / "build").resolve()
        rep = house_garden.write(data, plot, layout, out)
        common.say(f"garden: wrote {out}")
    rt = rep["route"]
    common.say(f"garden: scatter {rep['counts']}; {len(rep['props'])} props; {len(rep['roof'])} roof pieces")
    common.say(f"garden: herb route {rt['length_m']} m, {rt['time_s']} s (doc {rt['doc_m']} m, {rt['doc_s']} s)")
    for g in rep["roof_gaps"]:
        common.say(f"garden: NOTE {g}")
    for p in rep["problems"]:
        common.say(f"garden: PROBLEM {p}")
    common.say(f"garden: {'FAILED' if rep['problems'] else 'ok'}")
    return 1 if rep["problems"] else 0
