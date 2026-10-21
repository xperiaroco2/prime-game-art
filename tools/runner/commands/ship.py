"""`ship`: the empty ship, a wide metal manta (art #263, docs/ship.md). Always checks the layout
(layouts/ship/ship.toml with the interior and exterior lanes' pieces; tools/runner/ship_layout.py) and writes the text
plan; --build makes one GLB per piece in headless Blender (tools/blender/ship_build.py) and runs glTF-Validator on
each; --godot imports them headless and checks each piece's size against Blender's, the colliders and the capsule
walk from the ramp into both tip rooms and back; --walk DIR writes that walk into DIR; --shoot DIR assembles the ship
at night in an off-screen window and shoots the views, the plan view and its side-by-side compare with plan-3.jpg.

The command's core (this file's check, build and godot parts) is SHARED and FROZEN after the foundation step; the
EXTERIOR lane owns the shoot and walk parts (`shoot`, `walk_request`, VIEW_SIZE) and godot/ship/."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .. import blender, common, ship_layout
from . import _export, _godot

NAME = "ship"
HELP = "the empty ship (layouts/ship): check the layout; --build one GLB per piece; --godot import, sizes, colliders, walk; --shoot DIR, --walk DIR"
BUILD_SCRIPT = blender.SCRIPTS / "ship_build.py"
GODOT_SCRIPT = "res://ship/ship.gd"
BUILD_TIMEOUT = 900
GODOT_TIMEOUT = 300
VIEW_SIZE = (1920, 1080)
SIZE_TOL_M = 0.01


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--check", action="store_true", help="only the layout check (the default when nothing else is asked)")
    parser.add_argument("--build", action="store_true", help="build one GLB per piece and run glTF-Validator on each")
    parser.add_argument("--only", default="", help="comma-separated piece ids to build (default every piece)")
    parser.add_argument("--out", type=Path, help="the pieces folder (default <raw>/ship/v1/pieces)")
    parser.add_argument("--godot", action="store_true", help="headless import: sizes, colliders and the capsule walk")
    parser.add_argument("--walk", type=Path, metavar="DIR", help="the capsule walk (headless) into DIR/walk.json")
    parser.add_argument("--shoot", type=Path, metavar="DIR", help="off-screen shots at night, plan compare and sheet into DIR")


def raw(layout: dict) -> Path:
    return common.raw_dir() / layout["raw_dir"]


def run(args: argparse.Namespace) -> int:
    layout = ship_layout.load()
    problems = ship_layout.check(layout)
    width, length = ship_layout.extent(layout)
    common.say(f"ship v{layout['version']}: {width:.2f} x {length:.2f} m, {len(layout['rooms'])} rooms, "
               f"{len(layout['pieces'])} pieces, {len(layout['place'])} placements")
    for p in problems:
        common.say(f"  {p}")
    if problems:
        raise common.Failure(f"ship: {len(problems)} layout problems")
    plan = raw(layout) / "plan" / "plan.txt"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(ship_layout.ascii_plan(layout), encoding="utf-8", newline="\n")
    common.ok(f"ship: footprint, corridors, stations, hull, head room and the one entrance hold; plan {plan.as_posix()}")
    out = (args.out or raw(layout) / "pieces").resolve()
    code = 0
    if args.build:
        code |= build(layout, out, [s for s in args.only.split(",") if s])
    if args.godot or args.walk:
        code |= godot_check(layout, out, args.walk.resolve() if args.walk else common.OUT / "ship" / "godot")
    if args.shoot:
        code |= shoot(layout, out, args.shoot.resolve())
    return code


# --- build ---------------------------------------------------------------------------------------------------------
def build(layout: dict, out: Path, only: list[str]) -> int:
    unknown = set(only) - {p["id"] for p in layout["pieces"]}
    if unknown:
        raise common.Failure(f"no piece {', '.join(sorted(unknown))}")
    out.mkdir(parents=True, exist_ok=True)
    request = common.OUT / "ship" / "build_request.json"
    request.parent.mkdir(parents=True, exist_ok=True)
    request.write_text(json.dumps({"layout": layout, "only": only}, indent=1), encoding="utf-8", newline="\n")
    blender.run_script(BUILD_SCRIPT, ["--request", str(request), "--out", str(out)], timeout=BUILD_TIMEOUT)
    report = json.loads((out / "build_report.json").read_text(encoding="utf-8"))
    reports = out / "reports"
    reports.mkdir(exist_ok=True)
    bad = []
    for pid, info in report["pieces"].items():
        result = _export.validate(Path(info["glb"]), reports / f"{pid}.json")
        passed, line = _export.verdict(result)
        if not passed:
            bad.append(f"{pid}: {line}")
    tris = sum(i["triangles"] for i in report["pieces"].values())
    for b in bad:
        common.say(f"  {b}")
    if bad:
        common.bad(f"ship --build: {len(bad)} of {len(report['pieces'])} GLBs fail glTF-Validator")
        return 1
    common.ok(f"ship --build: {len(report['pieces'])} GLBs, {tris} triangles, glTF-Validator clean -> {out.as_posix()}")
    return 0


# --- Godot ---------------------------------------------------------------------------------------------------------
def _g(p: list) -> list[float]:
    """Plan (x, y, h) -> Godot (x, h, y)."""
    return [float(p[0]), float(p[2]), float(p[1])]


def scene_request(layout: dict, out: Path) -> tuple[dict, dict[str, Path]]:
    """The scene part of a Godot request (pieces, placements, colliders, Blender's bounds) and the GLBs to stage."""
    report = json.loads((out / "build_report.json").read_text(encoding="utf-8"))["pieces"]
    missing = [p["id"] for p in layout["pieces"] if p["id"] not in report]
    if missing:
        raise common.Failure(f"pieces not built (ship --build): {', '.join(missing)}")
    staged = {f"ship_{p['id']}": out / f"{p['id']}.glb" for p in layout["pieces"]}
    req = {"pieces": {p["id"]: f"res://import/ship_{p['id']}.glb" for p in layout["pieces"]},
           "collide": [p["id"] for p in layout["pieces"] if p["collide"]],
           "bounds": {pid: report[pid]["bounds"] for pid in req_ids(layout)},
           "place": [[pid, _g(at), yaw] for pid, at, yaw in layout["place"]]}
    return req, staged


def req_ids(layout: dict) -> list[str]:
    return [p["id"] for p in layout["pieces"]]


def walk_request(layout: dict) -> dict:
    pl = layout["player"]
    return {"r": pl["capsule_radius_m"], "h": pl["capsule_height_m"], "points": [_g(p) for p in layout["walk"]["points"]]}


def _stage(staged: dict[str, Path]) -> list[str]:
    _godot.clear_staged(set(staged))
    for name, glb in staged.items():
        _godot.stage(glb, name)
    errors = [line for line in _godot.import_project() if "ERROR" in line]
    for line in errors[:10]:
        common.say(f"  import: {line}")
    return errors


def godot_check(layout: dict, out: Path, folder: Path) -> int:
    req, staged = scene_request(layout, out)
    req.update({"mode": "check", "walk": walk_request(layout)})
    errors = _stage(staged)
    folder.mkdir(parents=True, exist_ok=True)
    path = common.OUT / "ship" / "check_request.json"
    path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
    (folder / "check.json").unlink(missing_ok=True)
    code, output = _godot.godot(["--headless", "--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s",
                                 GODOT_SCRIPT, "--", path.as_posix(), folder.as_posix()], GODOT_TIMEOUT)
    if code != 0 or not (folder / "check.json").is_file():
        raise common.Failure(f"ship.gd check failed (exit code {code}):\n" + "\n".join(output.splitlines()[-20:]))
    result = json.loads((folder / "check.json").read_text(encoding="utf-8"))
    problems = list(errors)
    for pid, got in result["bounds"].items():
        want = req["bounds"][pid]
        off = max(abs(a - b) for k in ("min", "max") for a, b in zip(got[k], want[k]))
        if off > SIZE_TOL_M:
            problems.append(f"{pid}: Godot's bounds differ from Blender's by {off:.3f} m")
    for pid in req["collide"]:
        if result["colliders"].get(pid, 0) < 1:
            problems.append(f"{pid}: no collider after import")
    w = result["walk"]
    common.say(f"  walk: {w['reached']}/{w['of']} points, end {[round(v, 2) for v in w['end']]}, {w['seconds']:.1f} s, "
               f"lowest {w['min_y']:.2f} m" + ("" if w["arrived"] else f"; stuck near {w.get('stuck')}"))
    if not w["arrived"]:
        problems.append("the capsule walk did not arrive")
    for p in problems:
        common.say(f"  {p}")
    if problems:
        common.bad(f"ship --godot: {len(problems)} problems")
        return 1
    common.ok(f"ship --godot: {len(result['bounds'])} pieces import at Blender's sizes, "
              f"{sum(result['colliders'].values())} colliders, the walk arrives ({folder.as_posix()})")
    return 0


def shoot(layout: dict, out: Path, folder: Path) -> int:
    req, staged = scene_request(layout, out)
    req.update({"mode": "shoot", "light": {**layout["light"], "lamps": [[*_g(l[:3]), *l[3:]] for l in layout["light"]["lamps"]]},
                "views": [[v[0], v[1], _g(v[2]), _g(v[3]), v[4]] for v in layout["shots"]["views"]],
                "top": {"name": "top", "title": "top: plan view, south up (as plan-3)", "size_m": 30.0},
                "compare": [["top", layout["plan_ref"]]]})
    errors = _stage(staged)
    folder.mkdir(parents=True, exist_ok=True)
    path = common.OUT / "ship" / "shoot_request.json"
    path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
    (folder / "shots.json").unlink(missing_ok=True)
    code, output = _godot.window(["--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s", GODOT_SCRIPT, "--",
                                  path.as_posix(), folder.as_posix()], VIEW_SIZE, GODOT_TIMEOUT)
    if code != 0 or not (folder / "shots.json").is_file():
        raise common.Failure(f"ship.gd shoot failed (exit code {code}):\n" + "\n".join(output.splitlines()[-20:]))
    result = json.loads((folder / "shots.json").read_text(encoding="utf-8"))
    for name, info in result["shots"].items():
        common.say(f"  {name}: {info['draw_calls']} draw calls, {info['primitives']} primitives")
    if errors:
        common.bad(f"ship --shoot: {len(errors)} import errors")
        return 1
    common.ok(f"ship --shoot: {len(result['shots'])} shots, sheet {(folder / 'sheet.png').as_posix()}")
    return 0
