"""`props`: the House dressing library (props/library.toml, docs/props.md). Checks the mapping file: classes, budgets,
paints, the sources' licences and the scale of every pack prop against its inventory size; `--measure` reads the
packs' glTF files again and compares their bounds and triangles with the record; `--build` makes the GLBs in
headless Blender (tools/blender/prop_build.py) into <raw>/props/library/v1/ and checks them: nodes, UV2, vertex
colours, `-vcol` materials, glTF-Validator, the class's triangle budget."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .. import blender, common
from . import _props

NAME = "props"
BUILD_TIMEOUT = 1500  # seconds for one Blender run of a batch (about 60 props)
HELP = "check the dressing library (props/library.toml); --build makes and checks its GLBs"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--library", type=Path, default=_props.LIBRARY, help="the mapping file (default props/library.toml)")
    parser.add_argument("--measure", action="store_true", help="also measure the pack files in <raw>/env again")
    parser.add_argument("--table", type=Path, help="write the prop table (markdown) here")
    parser.add_argument("--build", action="store_true", help="build the GLBs in headless Blender and check them")
    parser.add_argument("--batch", type=int, default=0, help="with --build: only this batch (1 indoor, 2 outdoor)")
    parser.add_argument("--only", default="", help="with --build: only these prop ids (comma-separated)")
    parser.add_argument("--out", type=Path, help="with --build: the output folder (default <raw>/props/library/v<n>)")
    parser.add_argument("--no-blender", action="store_true", help="with --build: check the GLBs already built")


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
    if args.build and not problems:
        problems += build(args, path, lib)
    if problems:
        for p in problems:
            common.bad(p)
        raise common.Failure(f"{len(problems)} problems in {path.name}")
    common.ok(f"{path.name}: clean")
    return 0


def build(args: argparse.Namespace, path: Path, lib: dict) -> list[str]:
    only = [s for s in args.only.split(",") if s]
    props = [p for p in lib["prop"] if (not args.batch or p["batch"] == args.batch) and (not only or p["id"] in only)]
    unknown = set(only) - {p["id"] for p in props}
    if unknown:
        raise common.Failure(f"no prop {', '.join(sorted(unknown))} in {path.name} (batch {args.batch or 'any'})")
    out = (args.out or _props.default_out(lib)).resolve()
    common.say(f"building {len(props)} props -> {out.as_posix()}")
    if not args.no_blender:
        out.mkdir(parents=True, exist_ok=True)
        for p in props:
            (out / f"{p['id']}.glb").unlink(missing_ok=True)
        cmd = ["--library", str(path), "--kit", str(common.ROOT / lib["kit_spec"]), "--out", str(out),
               "--ambientcg", str(common.raw_dir() / "env" / "ambientcg"), "--env", str(_props.env_dir()),
               "--batch", str(args.batch)]
        if only:
            cmd += ["--only", ",".join(only)]
        blender.run_script(_props.SCRIPT, cmd, timeout=BUILD_TIMEOUT)
    problems, notes = _props.check_build(lib, props, out)
    for n in notes:
        common.say(f"  note: {n}")
    table = out / "props.md"
    table.write_text(_props.build_table_md(lib, out), encoding="utf-8", newline="\n")
    common.say(f"  build table: {table.as_posix()}")
    if not problems:
        common.ok(f"{len(props)} props built and checked: nodes, UV2, vertex colours, materials, glTF-Validator, budgets")
    return problems
