"""`props`: the House dressing library (props/library.toml, docs/props.md). Checks the mapping file: classes, budgets,
paints, the sources' licences and the scale of every pack prop against its inventory size; `--measure` reads the
packs' glTF files again and compares their bounds and triangles with the record."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .. import common
from . import _props

NAME = "props"
HELP = "check the dressing library's mapping file (props/library.toml): budgets, paints, licences, pack scales"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--library", type=Path, default=_props.LIBRARY, help="the mapping file (default props/library.toml)")
    parser.add_argument("--measure", action="store_true", help="also measure the pack files in <raw>/env again")
    parser.add_argument("--table", type=Path, help="write the prop table (markdown) here")


def run(args: argparse.Namespace) -> int:
    path = args.library if args.library.is_absolute() else common.ROOT / args.library
    lib = _props.load(path)
    kit_path = common.ROOT / lib["kit_spec"]
    kit = json.loads(kit_path.read_text(encoding="utf-8"))
    props = lib.get("prop", [])
    packs = sum(p["route"] == "pack" for p in props)
    common.say(f"library {lib['library']} v{lib['version']}: {len(props)} props ({packs} pack, "
               f"{len(props) - packs} procedural), {len(lib.get('skip', {}))} inventory ids made elsewhere")
    problems = _props.check(lib, _props.sources_index(), kit)
    if args.measure:
        found_problems, found = _props.remeasure(lib, _props.env_dir())
        common.say(f"measured {found} pack props in {_props.env_dir().as_posix()}")
        problems += found_problems
    if args.table:
        out = args.table if args.table.is_absolute() else common.ROOT / args.table
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_props.table_md(lib), encoding="utf-8", newline="\n")
        common.say(f"table -> {out.as_posix()}")
    if problems:
        for p in problems:
            common.bad(p)
        raise common.Failure(f"{len(problems)} problems in {path.name}")
    common.ok(f"{path.name}: clean")
    return 0
