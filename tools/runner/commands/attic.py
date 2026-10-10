"""`attic`: checks the attic's old things and hiding spots and the roof deck's dressing and lookout
(layouts/house/dressing/attic.toml and roof.toml, house_attic.py; docs/house.md, "The attic and the roof deck") and
writes the report: every spot's standing point, the lookout's view per eye."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .. import common, house_attic

NAME = "attic"
HELP = "check the attic's hiding spots and the roof deck's dressing and lookout (layouts/house/dressing)"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", type=Path, default=common.ROOT / "tools" / "out" / "attic" / "report.json",
                        help="where the report goes (default tools/out/attic/report.json)")


def run(args: argparse.Namespace) -> int:
    rep = house_attic.report()
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8", newline="\n")
    spots = rep["attic"]["spots"]
    common.say(f"attic: {rep['attic']['items']} items, {sum(s['reachable'] for s in spots)}/{len(spots)} hiding "
               f"spots reachable for a pick-up")
    for v in rep["roof"]["lookout"]:
        see = ", ".join(f"{k} {100 * f:.0f}%" for k, f in v["see"].items())
        common.say(f"roof: lookout eye {v['eye']}: {see}; house windows in view {len(v['house_windows'])}; "
                   f"attic windows in view {v['attic_windows'] or 'none'}")
    problems = [f"attic: {p}" for p in rep["attic"]["problems"]] + [f"roof: {p}" for p in rep["roof"]["problems"]]
    for p in problems:
        common.say(f"  {p}")
    common.say(f"report: {args.json}")
    if problems:
        raise common.Failure(f"attic: {len(problems)} problems")
    return 0
