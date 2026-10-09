"""`props`: builds the House map's procedural props (props/tasks.toml: the task-station props of #82 and the
room-defining props no other package owns) as one GLB per prop with headless Blender and checks each: the spec's
sizes, pivots, budgets and game surfaces, glTF-Validator, and Godot's headless import (sizes, Y up, UV2, vertex
colours, closed collision that stops a ray). docs/props.md."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from .. import blender, common
from . import _export, _godot, _kit

NAME = "props"
HELP = "build the House map's procedural props (props/tasks.toml) as GLBs and check each: size, budget, surfaces, glTF-Validator, Godot import, collision"
SPEC = common.ROOT / "props" / "tasks.toml"
SCRIPT = "props_task_build.py"
REVIEW_SCRIPT = "props_task_review.py"
REVIEW_TIMEOUT = 900
BUILD_TIMEOUT = 900
CHECK_TIMEOUT = 600


def geom():
    """tools/blender/props_task.py as a module (plain Python)."""
    name = "props_task"
    if name in sys.modules:
        return sys.modules[name]
    _kit.geom()
    path = common.ROOT / "tools" / "blender" / "props_task.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def default_out(spec: dict[str, Any]) -> Path:
    return common.raw_dir() / "props" / "task" / f"v{spec['version']}"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--spec", type=Path, default=SPEC, help="the prop spec (default props/tasks.toml)")
    parser.add_argument("--out", type=Path, help="output folder (default <raw>/props/task/v<version>)")
    parser.add_argument("--only", default="", help="comma-separated prop ids (default every prop)")
    parser.add_argument("--no-build", action="store_true", help="check the GLBs already in --out")
    parser.add_argument("--no-godot", action="store_true", help="skip the Godot import check")
    parser.add_argument("--review", type=Path, help="also render the line-up sheets (front and 3/4 with a 1.8 m "
                                                    "capsule) and the switch from 8 m into this folder")


def run(args: argparse.Namespace) -> int:
    g = geom()
    spec_path = args.spec if args.spec.is_absolute() else common.ROOT / args.spec
    spec = g.load_spec(spec_path)
    out = (args.out or default_out(spec)).resolve()
    only = [s for s in args.only.split(",") if s]
    props = [p for p in spec["props"] if not only or p["id"] in only]
    unknown = set(only) - {p["id"] for p in props}
    if unknown:
        raise common.Failure(f"no prop {', '.join(sorted(unknown))} in {spec_path.name}")
    problems = list(g.check_spec(spec))
    described = {}
    for p in props:
        d = g.describe(g.build_prop(p, spec), spec)
        described[p["id"]] = d
        problems += g.check_prop(d, p, spec)
    common.say(f"props v{spec['version']}: {len(props)} props, "
               f"{sum(d['triangles'] for d in described.values())} triangles -> {out.as_posix()}")
    _report(problems, "spec: sizes, pivots, budgets, colliders, UV2, game surfaces, state meshes")
    if not args.no_build:
        out.mkdir(parents=True, exist_ok=True)
        for p in props:
            (out / f"{p['id']}.glb").unlink(missing_ok=True)
        cmd = ["--spec", str(spec_path), "--out", str(out), "--ambientcg", str(common.raw_dir() / "env" / "ambientcg")]
        if only:
            cmd += ["--only", ",".join(only)]
        blender.run_script(SCRIPT, cmd, timeout=BUILD_TIMEOUT)
    glb_problems, reports = [], out / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    errors = warnings = 0
    for p in props:
        glb = out / f"{p['id']}.glb"
        if not glb.is_file():
            glb_problems.append(f"{p['id']}: no {glb.as_posix()}")
            continue
        gltf = _export.glb_json(glb)
        glb_problems += _kit.check_glb(gltf, described[p["id"]], len(g.kit_geom.export_materials(spec)))
        glb_problems += check_surface_material(gltf, p, g.SURFACE_MATERIAL)
        report = _export.validate(glb, reports / f"{p['id']}.json")
        passed, _line = _export.verdict(report)
        counts = report.get("issues", {})
        errors += counts.get("numErrors", 1)
        warnings += counts.get("numWarnings", 0)
        if not passed:
            glb_problems += [f"{p['id']}: {m}" for m in _export.issues(report)["error"][:5]]
    _report(glb_problems, f"GLBs: nodes, UV2, vertex colours, game surface; glTF-Validator {errors} errors, "
                          f"{warnings} warnings")
    problems += glb_problems
    if not args.no_godot:
        problems += godot_check(props, described, out)
    if args.review and not problems:
        if only:
            return _fail("--review needs every prop (drop --only)")
        folder = args.review.resolve()
        folder.mkdir(parents=True, exist_ok=True)
        blender.run_script(REVIEW_SCRIPT, ["--spec", str(spec_path), "--glbs", str(out), "--out", str(folder)],
                           timeout=REVIEW_TIMEOUT)
        common.ok(f"review sheets: {', '.join(sorted(f.name for f in folder.glob('*.png')))} in {folder.as_posix()}")
    rows = g.prop_table([described[p["id"]] for p in props], spec)
    (out / "props.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    (out / "props.md").write_text(g.table_md(rows), encoding="utf-8", newline="\n")
    common.say(f"  prop table: {(out / 'props.md').as_posix()}")
    if problems:
        common.bad(f"props: {len(problems)} problems")
        return 1
    common.ok(f"props: {len(props)} props built and checked")
    return 0


RAY_LEAD_M = 0.5  # every collider is probed by a ray that starts this far outside it
RAY_OFFSET = 0.17  # of the half size along the other two axes: off the face's triangle diagonals


def rays(described: dict[str, Any]) -> list[list[list[float]]]:
    """One ray per collider, as the kit's (`_kit.rays`) but aimed a little off its centre: a ray at a box face's
    centre meets the diagonal between the face's two triangles, where Godot's segment test can miss both (it did on
    computer_set). The target stays inside every box and convex prism collider."""
    out = []
    for c in described["colliders"]:
        pts = c["points"]
        lo = [min(p[i] for p in pts) for i in range(3)]
        hi = [max(p[i] for p in pts) for i in range(3)]
        centre = [sum(p[i] for p in pts) / len(pts) for i in range(3)]
        axis = min(range(3), key=lambda i: hi[i] - lo[i])
        target = [centre[i] + (0.0 if i == axis else RAY_OFFSET * (hi[i] - lo[i]) / 2) for i in range(3)]
        start = list(target)
        start[axis] = lo[axis] - RAY_LEAD_M
        out.append([[round(v, 5) for v in start], [round(v, 5) for v in target]])
    return out


def check_surface_material(gltf: dict[str, Any], p: dict[str, Any], surface: str) -> list[str]:
    """A prop with a game surface has the `surface_game-vcol` material; one without has none."""
    has = any(m.get("name") == f"{surface}-vcol" for m in gltf.get("materials", []))
    if has != bool(p.get("surface")):
        return [f"{p['id']}: the {surface} material is {'there' if has else 'missing'}, "
                f"the spec says surface = {bool(p.get('surface'))}"]
    return []


def godot_check(props: list[dict], described: dict, out: Path) -> list[str]:
    names = {p["id"]: f"prop_{p['id']}" for p in props}
    _godot.clear_staged(set(names.values()))
    request = {"pieces": {}}
    for pid, name in names.items():
        res = _godot.stage(out / f"{pid}.glb", name)
        request["pieces"][pid] = {"scene": res, "rays": rays(described[pid])}
    lines = _godot.import_project()
    work = common.OUT / "props"
    work.mkdir(parents=True, exist_ok=True)
    req, dump_path = work / "godot_request.json", work / "godot_props.json"
    req.write_text(json.dumps(request), encoding="utf-8")
    dump_path.unlink(missing_ok=True)
    code, output = _godot.godot(["--headless", "--path", _godot.PROJECT, "-s", _kit.CHECK, "--",
                                 req.as_posix(), dump_path.as_posix()], CHECK_TIMEOUT)
    if code != 0 or not dump_path.is_file():
        tail = "\n".join(output.splitlines()[-20:])
        raise common.Failure(f"kit.gd failed on the props (exit code {code}):\n{tail}")
    dump = json.loads(dump_path.read_text(encoding="utf-8"))
    problems = []
    for pid in names:
        problems += _kit.evaluate(dump["pieces"].get(pid, {"error": "not in Godot's output"}), described[pid])
    problems += [f"Godot import: {line}" for line in lines if "ERROR" in line]
    _report(problems, f"Godot {dump.get('godot', '?')} import: sizes, Y up, UV2, vertex colours, closed collision "
                      f"({sum(len(described[p]['colliders']) for p in names)} rays); {len(lines)} import warnings")
    (out / "godot.json").write_text(json.dumps(dump, indent=1), encoding="utf-8")
    return problems


def _fail(message: str) -> int:
    common.bad(message)
    return 1


def _report(problems: list[str], what: str) -> None:
    if problems:
        common.bad(f"{what}: {len(problems)} problems")
        for line in problems[:30]:
            common.say(f"        {line}")
    else:
        common.ok(what)
