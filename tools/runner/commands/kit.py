"""`kit`: builds a modular kit (kits/house.json) as one GLB per piece with headless Blender and checks every piece: the
spec's grid and budgets, glTF-Validator, and Godot's headless import (sizes, Y up, UV2, vertex colours, closed
collision that stops a ray). docs/kit.md."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .. import blender, common
from . import _export, _frames, _godot, _kit

NAME = "kit"
HELP = "build a modular kit (kits/house.json) as one GLB per piece and check each: grid, budgets, glTF-Validator, Godot import, collision"
BUILD_TIMEOUT = 900
CHECK_TIMEOUT = 600
PROOF_TIMEOUT = 240


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--spec", type=Path, default=_kit.SPEC, help="the kit spec (default kits/house.json)")
    parser.add_argument("--out", type=Path, help="output folder (default <raw>/kits/<kit>/v<version>)")
    parser.add_argument("--only", default="", help="comma-separated piece ids (default every piece)")
    parser.add_argument("--no-build", action="store_true", help="check the GLBs already in --out")
    parser.add_argument("--no-godot", action="store_true", help="skip the Godot import check")
    parser.add_argument("--proof", type=Path, help="also assemble the test room, corridor and stairs in an off-screen "
                                                   "Godot window, walk them and shoot them into this folder")


def run(args: argparse.Namespace) -> int:
    g = _kit.geom()
    spec_path = args.spec if args.spec.is_absolute() else common.ROOT / args.spec
    spec = g.load_spec(spec_path)
    out = (args.out or _kit.default_out(spec)).resolve()
    only = [s for s in args.only.split(",") if s]
    pieces = [p for p in spec["pieces"] if not only or p["id"] in only]
    unknown = set(only) - {p["id"] for p in pieces}
    if unknown:
        raise common.Failure(f"no piece {', '.join(sorted(unknown))} in {spec_path.name}")
    problems = list(g.check_spec(spec))
    described = {}
    for p in pieces:
        d = g.describe(g.build_piece(p, spec), spec)
        described[p["id"]] = d
        problems += g.check_piece(d, p, spec)
    common.say(f"kit {spec['kit']} v{spec['version']}: {len(pieces)} pieces, "
               f"{sum(d['triangles'] for d in described.values())} triangles -> {out.as_posix()}")
    _report(problems, "spec: grid, sizes, budgets, colliders, UV2")
    if not args.no_build:
        out.mkdir(parents=True, exist_ok=True)
        for p in pieces:
            (out / f"{p['id']}.glb").unlink(missing_ok=True)
        cmd = ["--spec", str(spec_path), "--out", str(out), "--ambientcg", str(common.raw_dir() / "env" / "ambientcg")]
        if only:
            cmd += ["--only", ",".join(only)]
        blender.run_script(_kit.SCRIPT, cmd, timeout=BUILD_TIMEOUT)
    glb_problems, reports = [], out / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    errors = warnings = 0
    for p in pieces:
        glb = out / f"{p['id']}.glb"
        if not glb.is_file():
            glb_problems.append(f"{p['id']}: no {glb.as_posix()}")
            continue
        glb_problems += _kit.check_glb(_export.glb_json(glb), described[p["id"]], len(spec["materials"]))
        report = _export.validate(glb, reports / f"{p['id']}.json")
        passed, _line = _export.verdict(report)
        counts = report.get("issues", {})
        errors += counts.get("numErrors", 1)
        warnings += counts.get("numWarnings", 0)
        if not passed:
            glb_problems += [f"{p['id']}: {m}" for m in _export.issues(report)["error"][:5]]
    _report(glb_problems, f"GLBs: nodes, UV2, vertex colours; glTF-Validator {errors} errors, {warnings} warnings")
    problems += glb_problems
    if not args.no_godot:
        problems += godot_check(pieces, described, out)
        if args.proof and not problems:
            problems += proof(pieces, described, args.proof.resolve())
    rows = g.piece_table([described[p["id"]] for p in pieces])
    (out / "pieces.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    (out / "pieces.md").write_text(_kit.table_md(rows, spec["budget_tris"]), encoding="utf-8", newline="\n")
    common.say(f"  piece table: {(out / 'pieces.md').as_posix()}")
    if problems:
        common.bad(f"kit: {len(problems)} problems")
        return 1
    common.ok(f"kit: {len(pieces)} pieces built and checked")
    return 0


def godot_check(pieces: list[dict], described: dict, out: Path) -> list[str]:
    names = {p["id"]: f"kit_{p['id']}" for p in pieces}
    _godot.clear_staged(set(names.values()))
    request = {"pieces": {}}
    for pid, name in names.items():
        res = _godot.stage(out / f"{pid}.glb", name)
        request["pieces"][pid] = {"scene": res, "rays": _kit.rays(described[pid])}
    lines = _godot.import_project()
    work = common.OUT / "kit"
    work.mkdir(parents=True, exist_ok=True)
    req, dump_path = work / "godot_request.json", work / "godot_kit.json"
    req.write_text(json.dumps(request), encoding="utf-8")
    dump_path.unlink(missing_ok=True)
    code, output = _godot.godot(["--headless", "--path", _godot.PROJECT, "-s", _kit.CHECK, "--",
                                 req.as_posix(), dump_path.as_posix()], CHECK_TIMEOUT)
    if code != 0 or not dump_path.is_file():
        tail = "\n".join(output.splitlines()[-20:])
        raise common.Failure(f"kit.gd failed (exit code {code}):\n{tail}")
    dump = json.loads(dump_path.read_text(encoding="utf-8"))
    problems = []
    for pid in names:
        problems += _kit.evaluate(dump["pieces"].get(pid, {"error": "not in Godot's output"}), described[pid])
    problems += [f"Godot import: {line}" for line in lines if "ERROR" in line]
    _report(problems, f"Godot {dump.get('godot', '?')} import: sizes, Y up, UV2, vertex colours, closed collision "
                      f"({sum(len(described[p]['colliders']) for p in names)} rays); {len(lines)} import warnings")
    (out / "godot.json").write_text(json.dumps(dump, indent=1), encoding="utf-8")
    return problems


def proof(pieces: list[dict], described: dict, folder: Path) -> list[str]:
    """godot/kit/proof.gd in a window off-screen (pictures need one): the shots, sheet.png and the walks."""
    request = {"pieces": {p["id"]: {"scene": f"res://import/kit_{p['id']}.glb", **described[p["id"]]["bounds_m"]}
                          for p in pieces}}
    missing = {"stairs_main", "wall_storey_2m_ext", "wall_storey_2m_door_int"} - set(request["pieces"])
    if missing:
        return [f"proof: needs {', '.join(sorted(missing))} (drop --only)"]
    folder.mkdir(parents=True, exist_ok=True)
    req = common.OUT / "kit" / "proof_request.json"
    req.write_text(json.dumps(request), encoding="utf-8")
    (folder / "proof.json").unlink(missing_ok=True)
    code, output = _godot.godot(["--path", _godot.PROJECT, "--audio-driver", "Dummy", "--position", _frames.POSITION,
                                 "--resolution", "1600x900", "-s", _kit.PROOF, "--", req.as_posix(),
                                 folder.as_posix()], PROOF_TIMEOUT)
    if code != 0 or not (folder / "proof.json").is_file():
        tail = "\n".join(output.splitlines()[-20:])
        raise common.Failure(f"proof.gd failed (exit code {code}):\n{tail}")
    walks = json.loads((folder / "proof.json").read_text(encoding="utf-8"))["walks"]
    problems = [f"proof: walk {k} {'arrived' if w['arrived'] else 'stopped'} at {[round(c, 2) for c in w['end']]}"
                for k, w in walks.items() if not w["pass"]]
    _report(problems, "proof: the 0.8 m capsule walks room, door, corridor and stairs to 3.2 m; a 1.5 m one stops at "
                      f"the door; sheet {(folder / 'sheet.png').as_posix()}")
    return problems


def _report(problems: list[str], what: str) -> None:
    if problems:
        common.bad(f"{what}: {len(problems)} problems")
        for line in problems[:30]:
            common.say(f"        {line}")
    else:
        common.ok(what)
