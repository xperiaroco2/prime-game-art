"""`outdoor`: the House map outside the house (art #81a, #81c): checks `layouts/house/outdoor/` and writes the fence
and stairs plan, the ground and backdrop GLBs, the sky and flats PNGs and a top-down plan. Pure Python, about 5 s.
docs/house-outdoor.md."""

from __future__ import annotations

import argparse
from pathlib import Path

from .. import common, house_outdoor

NAME = "outdoor"
HELP = "the House map's plot: fence, ground, street, outdoor stairs, sky and backdrop from layouts/house/outdoor/"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--layouts", type=Path, default=house_outdoor.DATA, help="the outdoor layout folder")
    parser.add_argument("--out", type=Path, help="output folder (default <raw>/house/81/build)")
    parser.add_argument("--check", action="store_true", help="only check the layout; write nothing")


def run(args: argparse.Namespace) -> int:
    data = house_outdoor.load(args.layouts)
    if args.check:
        problems = house_outdoor.plan(data)["problems"]
    else:
        out = (args.out or common.raw_dir() / "house" / "81" / "build").resolve()
        summary = house_outdoor.write(data, out)
        problems = summary["problems"]
        pieces = ", ".join(f"{k} {v}" for k, v in summary["pieces"].items())
        common.say(f"outdoor: {summary['fence_m']:g} m of fence; {pieces}")
        common.say(f"outdoor: ground triangles {summary['ground_tris']}; {summary['flats']} flats; "
                   f"sky {summary['sky']['size']}, wrap step {summary['sky']['seam_step']} "
                   f"(inner {summary['sky']['inner_step']}); lit windows {summary['windows']}")
        common.say(f"outdoor: wrote {out}")
    for p in problems:
        common.say(f"outdoor: PROBLEM {p}")
    common.say(f"outdoor: {'FAILED' if problems else 'ok'}")
    return 1 if problems else 0
