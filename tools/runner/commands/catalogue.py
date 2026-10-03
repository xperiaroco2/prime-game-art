"""`catalogue`: the parts catalogue of the Ultimate Modular packs (docs/catalogue.md): every part inventoried, heads split
into offerable items, compatibility measured pair by pair in headless Blender; writes catalogue/ultimate_modular.json
(deterministic), with --renders the contact sheets, matrix grids and confirmation renders."""

from __future__ import annotations

import argparse
from pathlib import Path

from .. import blender, common
from . import _catalogue

NAME = "catalogue"
HELP = "the Ultimate Modular parts catalogue with compatibility rules: catalogue/ultimate_modular.json (docs/catalogue.md)"
TIMEOUT = 3600


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--check", action="store_true",
        help="regenerate into tools/out/catalogue/check.json and fail if it differs from the committed file",
    )  # fmt: skip
    parser.add_argument("--renders", default="", help="comma list of sheets, matrices, confirm (default: none)")
    parser.add_argument("--out", type=Path, help="render folder (default tools/out/catalogue/)")
    parser.add_argument("--res", type=int, default=100, help="render size in percent (default 100)")


def run(args: argparse.Namespace) -> int:
    modes = [m for m in args.renders.split(",") if m]
    unknown = [m for m in modes if m not in _catalogue.MODES]
    if unknown:
        raise common.Failure(f"unknown renders {', '.join(unknown)}; use {', '.join(_catalogue.MODES)}")
    if not 5 <= args.res <= 100:
        raise common.Failure("--res must be from 5 to 100 (percent)")
    raw = common.raw_dir()
    for pack in ("Ultimate_Modular_Men_Pack", "Ultimate_Modular_Women_Pack"):
        if not (raw / "refs" / pack).is_dir():
            raise common.Failure(f"no {pack} in {(raw / 'refs').as_posix()} (sources/quaternius_ultimate_modular_*.toml)")
    out = (args.out or common.OUT / "catalogue").resolve()
    data_path = out / "check.json" if args.check else _catalogue.DATA
    script_args = ["--raw", str(raw), "--data", str(data_path), "--res", str(args.res)]
    if modes:
        script_args += ["--out", str(out), "--modes", ",".join(modes)]
    common.say(f"catalogue: {data_path.as_posix()}" + (f", renders {', '.join(modes)} -> {out.as_posix()}" if modes else ""))
    blender.run_script(_catalogue.SCRIPT, script_args, timeout=TIMEOUT)
    data = _catalogue.load(data_path)
    problems = _catalogue.validate(data)
    for line in _catalogue.summary(data):
        common.say(f"  {line}")
    if problems:
        for line in problems[:20]:
            common.bad(line)
        raise common.Failure(f"{data_path.name}: {len(problems)} schema problems")
    if args.check:
        if not _catalogue.DATA.is_file():
            raise common.Failure(f"no committed {_catalogue.DATA.relative_to(common.ROOT).as_posix()} to compare with")
        differences = _catalogue.diff(_catalogue.load(), data)
        if differences:
            for line in differences:
                common.bad(line)
            raise common.Failure("the regenerated catalogue differs from the committed file")
        common.ok("the regenerated catalogue equals the committed file")
    return 0
