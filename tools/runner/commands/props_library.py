"""`props-library`: the House dressing library (props/library.toml, docs/props.md). Checks the mapping file: classes,
budgets, paints, the sources' licences and the scale of every pack prop against its inventory size; `--measure` reads
the packs' glTF files again and compares their bounds and triangles with the record; `--build` makes the GLBs in
headless Blender (tools/blender/prop_build.py) into <raw>/props/library/v1/ and checks them: nodes, UV2, vertex colours,
`-vcol` materials, glTF-Validator, the class's triangle budget; then Godot's headless import (sizes, pivot, Y up, UV2,
vertex colours, closed collision, the fixtures' LightAnchor; godot/check/kit.gd); `--sheets DIR` adds the line-up sheets
from an off-screen Godot window (godot/props/lineup.gd)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .. import blender, common
from . import _frames, _godot, _kit, _props

NAME = "props-library"
BUILD_TIMEOUT = 1500  # seconds for one Blender run of a batch (about 60 props)
CHECK_TIMEOUT = 600
LINEUP_TIMEOUT = 240
CHECK = "res://check/kit.gd"
LINEUP = "res://props/lineup.gd"
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
    parser.add_argument("--no-godot", action="store_true", help="with --build: skip the Godot import check")
    parser.add_argument("--sheets", type=Path, help="with --build: also shoot the line-up sheets into this folder "
                                                    "(an off-screen Godot window)")


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
        blender.run_script(lib.get("script", _props.SCRIPT), cmd, timeout=BUILD_TIMEOUT)
    problems, notes = _props.check_build(lib, props, out)
    for n in notes:
        common.say(f"  note: {n}")
    table = out / "props.md"
    table.write_text(_props.build_table_md(lib, out), encoding="utf-8", newline="\n")
    common.say(f"  build table: {table.as_posix()}")
    if not problems:
        common.ok(f"{len(props)} props built and checked: nodes, UV2, vertex colours, materials, glTF-Validator, budgets")
    if problems or args.no_godot:
        return problems
    built = json.loads((out / "build.json").read_text(encoding="utf-8"))["props"]
    dump = godot_check(props, built, out)
    problems += dump.pop("problems")
    if args.sheets and not problems:
        problems += sheets(props, built, dump, out, args.sheets.resolve())
    return problems


def godot_check(props: list[dict], built: dict, out: Path) -> dict:
    """Imports every prop into godot/ (as prop_<id>) and checks it headless with the kit's describer."""
    names = {p["id"]: f"prop_{p['id']}" for p in props}
    _godot.clear_staged(set(names.values()))
    described, request = {}, {"pieces": {}}
    for p in props:
        pid = p["id"]
        described[pid] = _props.godot_described(p, built[pid], out / f"{pid}.glb")
        request["pieces"][pid] = {"scene": _godot.stage(out / f"{pid}.glb", names[pid]),
                                  "rays": _kit.rays(described[pid])}
    lines = _godot.import_project()
    work = common.OUT / "props"
    work.mkdir(parents=True, exist_ok=True)
    req, dump_path = work / "godot_request.json", work / "godot_props.json"
    req.write_text(json.dumps(request), encoding="utf-8")
    dump_path.unlink(missing_ok=True)
    code, output = _godot.godot(["--headless", "--path", _godot.PROJECT, "-s", CHECK, "--",
                                 req.as_posix(), dump_path.as_posix()], CHECK_TIMEOUT)
    if code != 0 or not dump_path.is_file():
        tail = "\n".join(output.splitlines()[-20:])
        raise common.Failure(f"kit.gd failed (exit code {code}):\n{tail}")
    dump = json.loads(dump_path.read_text(encoding="utf-8"))
    problems = []
    for p in props:
        got = dump["pieces"].get(p["id"], {"error": "not in Godot's output"})
        problems += _kit.evaluate(got, described[p["id"]]) + _props.evaluate_anchor(p["id"], got, built[p["id"]])
    problems += [f"Godot import: {line}" for line in lines if "ERROR" in line]
    rays = sum(len(d["colliders"]) for d in described.values())
    anchors = sum(len(v.get("anchors", [])) for v in dump["pieces"].values())
    what = (f"Godot {dump.get('godot', '?')} import of {len(props)} props: sizes and pivots, Y up, UV2, vertex colours, "
            f"closed collision ({rays} rays), {anchors} light anchors; {len(lines)} import warnings")
    if problems:
        common.bad(f"{what}: {len(problems)} problems")
    else:
        common.ok(what)
    (out / "godot.json").write_text(json.dumps(dump, indent=1), encoding="utf-8")
    dump["problems"] = problems
    return dump


def sheets(props: list[dict], built: dict, dump: dict, out: Path, folder: Path) -> list[str]:
    """The line-up sheets (_props.sheet_plan) from godot/props/lineup.gd in a window off-screen."""
    kit = json.loads((common.ROOT / _props.load()["kit_spec"]).read_text(encoding="utf-8"))
    layers = [kit["materials"][m] for m in kit.get("packs", {}).get("set", {}).get("layers", [])]
    plan = _props.sheet_plan(props, built)
    by_id = {p["id"]: p for p in props}
    request = {"textures": (out / "textures").as_posix(),
               "pack": {"roughness": [m["roughness"] for m in layers],
                        "normal_strength": [m["normal_strength"] for m in layers]},
               "sheets": []}
    for k, rows in enumerate(plan, 1):
        count = sum(len(r) for r in rows)
        batches = sorted({str(by_id[i]["batch"]) for r in rows for i in r})
        request["sheets"].append({
            "file": f"lineup_{k}.png",
            "title": f"House dressing library v1, sheet {k} of {len(plan)}: {count} props (batch "
                     f"{', '.join(batches)}), tallest first; the capsule is 1.8 m",
            "rows": [[{"id": i, "scene": f"res://import/prop_{i}.glb", **dump["pieces"][i]["bounds"]} for i in r]
                     for r in rows]})
    folder.mkdir(parents=True, exist_ok=True)
    req = common.OUT / "props" / "lineup_request.json"
    req.write_text(json.dumps(request), encoding="utf-8")
    (folder / "lineup.json").unlink(missing_ok=True)
    code, output = _godot.godot(["--path", _godot.PROJECT, "--audio-driver", "Dummy", "--position", _frames.POSITION,
                                 "--resolution", "1600x900", "-s", LINEUP, "--", req.as_posix(), folder.as_posix()],
                                LINEUP_TIMEOUT)
    if code != 0 or not (folder / "lineup.json").is_file():
        tail = "\n".join(output.splitlines()[-20:])
        raise common.Failure(f"lineup.gd failed (exit code {code}):\n{tail}")
    common.ok(f"line-up: {len(plan)} sheets -> {folder.as_posix()}/lineup_<n>.png")
    return []
