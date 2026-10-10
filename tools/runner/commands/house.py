"""`house`: checks the House map's layout data (layouts/house/*.toml) and generates its Godot scenes from the House
kit: one scene per room and per level and house.tscn (tools/runner/house_layout.py, docs/house.md)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .. import common, house_basement, house_dressing, house_layout, house_routes
from . import _frames, _godot

NAME = "house"
HELP = "check the House layout (layouts/house/*.toml) and generate its room, level and house scenes from the kit"
DEFAULT_OUT = common.ROOT / "godot" / "import" / "house"
WALK = "res://house/walk.gd"
WALK_TIMEOUT = 240


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--layouts", type=Path, default=house_layout.LAYOUT_DIR, help="the layout folder")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="where the scenes go (default godot/import/house, res://import/house)")
    parser.add_argument("--check", action="store_true", help="only check the layout; write nothing")
    parser.add_argument("--props-spec", type=Path, action="append", default=[], metavar="TOML",
                        help="another prop catalogue for the dressing's sizes (e.g. a library.toml not yet on main)")
    parser.add_argument("--walk", type=Path, metavar="DIR",
                        help="stage the kit GLBs, import, then walk and shoot the house in an off-screen Godot window "
                             "into DIR (walk.json, sheet.png, exterior.png, stills)")


def run(args: argparse.Namespace) -> int:
    data = house_layout.load(args.layouts)
    problems = house_layout.validate(data)
    rooms = sum(len(lv["rooms"]) for lv in data["levels"])
    common.say(f"house layout: {len(data['levels'])} levels, {rooms} rooms, kit {data['settings']['kit_dir']}")
    if problems:
        for p in problems:
            common.say(f"  {p}")
        raise common.Failure(f"house layout: {len(problems)} problems")
    common.say("house layout: grid, openings, corners, footprints, stairs and holes hold")
    dressing = check_dressing(data, args.layouts, args.props_spec)
    check_basement(data, args.layouts, args.props_spec)
    routes = house_routes.load(args.layouts)
    bad_routes = house_routes.problems(data, routes)
    if bad_routes:
        for p in bad_routes:
            common.say(f"  {p}")
        raise common.Failure(f"house routes: {len(bad_routes)} problems")
    if args.check:
        return 0
    planned = house_layout.plan(data)
    found = prop_glbs(data, dressing)
    st = data["settings"]
    summary = house_layout.write_scenes(data, planned, args.out, dressing,
                                        lambda pid: st["prop_res"].format(id=pid) if pid in found else None)
    held = {rid: ids for rid, ids in summary["placeholders"].items() if ids}
    if summary["props"]:
        common.say(f"  dressing: {sum(summary['props'].values())} props and fixtures in {len(dressing)} rooms, "
                   f"{sum(len(v) for v in held.values())} as placeholder boxes (no GLB yet: "
                   f"{', '.join(sorted({i for v in held.values() for i in v})) or '-'})")
    for name, s in summary["levels"].items():
        common.say(f"  {name}: {s['rooms']} rooms, {s['instances']} piece instances")
    report = common.OUT / "house" / "plan.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"summary": summary, "plan": planned}, indent=1), encoding="utf-8", newline="\n")
    common.say(f"house: {summary['instances']} instances of {len(summary['pieces'])} pieces -> {args.out.as_posix()}; "
               f"plan {report.as_posix()}")
    if args.walk:
        if args.out.resolve() != DEFAULT_OUT.resolve():
            raise common.Failure("--walk needs the scenes in godot/import/house (drop --out)")
        return walk(data, summary, args.walk.resolve(), found, routes)
    return 0


def check_dressing(data: dict, layouts: Path, extra) -> dict:
    """Checks layouts/house/dressing/*.toml against the rooms (house_dressing.check); writes tools/out/house/dressing.json;
    returns room id -> its report. A problem fails the command."""
    st = data["settings"]
    folder = Path(layouts) / st.get("dressing_dir", "dressing")
    if not folder.is_dir():
        return {}
    paths = house_dressing.spec_paths(st, extra=extra)
    missing = [p.as_posix() for p in paths if not p.is_file()]
    cat = house_dressing.catalogue(paths)
    result = house_dressing.check(data, house_dressing.load(folder), cat)
    report = common.OUT / "house" / "dressing.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    slim = {rid: {k: v for k, v in r.items() if k != "resolved"} for rid, r in result["rooms"].items()}
    report.write_text(json.dumps({"catalogues": [p.as_posix() for p in paths], "missing": missing, "rooms": slim,
                                  "problems": result["problems"], "notes": result["notes"]}, indent=1),
                      encoding="utf-8", newline="\n")
    for r in result["rooms"].values():
        common.say(f"  dressing {r['room']}: {r['props']} props, {r['fixtures']} fixtures; capsule reaches "
                   f"{sum(r['reach'].values())}/{len(r['reach'])} doors, stairs, stations and spawns")
    for n in result["notes"]:
        common.say(f"  note: {n}")
    if result["problems"]:
        for p in result["problems"]:
            common.say(f"  {p}")
        hint = f" (catalogues missing: {', '.join(missing)}; pass --props-spec)" if missing else ""
        raise common.Failure(f"house dressing: {len(result['problems'])} problems{hint}")
    common.say(f"house dressing: {len(result['rooms'])} rooms hold (bounds, overlaps, stations, the capsule's paths); "
               f"{report.as_posix()}")
    return result["rooms"]


def prop_glbs(data: dict, dressing: dict) -> dict:
    """prop id -> its GLB under the raw folder (the first of house.toml's prop_dirs that has it)."""
    raw = common.raw_dir()
    ids = {r["id"] for rep in dressing.values() for r in rep["resolved"]}
    found = {}
    for pid in sorted(ids):
        for d in data["settings"].get("prop_dirs", []):
            glb = raw / d / f"{pid}.glb"
            if glb.is_file():
                found[pid] = glb
                break
    return found


def walk(data: dict, summary: dict, folder: Path, props: dict | None = None, routes: dict | None = None) -> int:
    """Stages the pieces the scenes use from the kit folder, imports them headless, then runs godot/house/walk.gd in a
    window off-screen (pictures need one): every doorway of the ground and upper floors and every flight, walked by
    a 1.36 m capsule; the design doc's routes (routes.toml) at their speed, judged against the doc's times; the stills,
    the plan, sheet.png and the exterior at dusk (exterior.png); draw calls per view."""
    kit = common.raw_dir() / data["settings"]["kit_dir"]
    names = {pid: f"kit_{pid}" for pid in summary["pieces"]}
    missing = [pid for pid in names if not (kit / f"{pid}.glb").is_file()]
    if missing:
        raise common.Failure(f"no {', '.join(sorted(missing))} in {kit.as_posix()} (build the kit first)")
    props = props or {}
    _godot.clear_staged(set(names.values()) | {f"prop_{pid}" for pid in props})
    for pid, name in names.items():
        _godot.stage(kit / f"{pid}.glb", name)
    for pid, glb in props.items():
        _godot.stage(glb, f"prop_{pid}")
    errors = [line for line in _godot.import_project() if "ERROR" in line]
    for line in errors[:10]:
        common.say(f"  import: {line}")
    folder.mkdir(parents=True, exist_ok=True)
    req = common.OUT / "house" / "walk_request.json"
    request = house_layout.walk_request(data)
    request["walks"] += house_routes.walks(data, request, routes or {})
    for name in request["closed"]:
        common.say(f"  not walked (closed kit leaf): {name}")
    req.write_text(json.dumps(request, indent=1), encoding="utf-8", newline="\n")
    (folder / "walk.json").unlink(missing_ok=True)
    code, output = _godot.godot(["--path", _godot.PROJECT, "--audio-driver", "Dummy", "--position", _frames.POSITION,
                                 "--resolution", "1600x900", "-s", WALK, "--", req.as_posix(), folder.as_posix()],
                                WALK_TIMEOUT)
    if code != 0 or not (folder / "walk.json").is_file():
        tail = "\n".join(output.splitlines()[-20:])
        raise common.Failure(f"walk.gd failed (exit code {code}):\n{tail}")
    result = json.loads((folder / "walk.json").read_text(encoding="utf-8"))
    tolerance = float((routes or {}).get("tolerance_s", 1.0))
    for w, r in zip(request["walks"], result["walks"]):
        if w["kind"] == "route":
            r.update(house_routes.judge(w, r, tolerance))
            common.say(f"  route {w['name']}: {r['seconds']} s walked at {w['speed']:g} m/s, the doc {r['doc_s']:g} s "
                       f"({r['delta_s']:+g} s, {'within' if r['time_ok'] else 'OVER'} {tolerance:g} s), {r['plan_m']:g} m on the "
                       f"plan, the doc {r['doc_m']:g} m")
    (folder / "walk.json").write_text(json.dumps(result, indent=1), encoding="utf-8", newline="\n")
    failed = [w for w in result["walks"] if not w["pass"]] + ([] if result["control"]["pass"] else [result["control"]])
    for w in result["walks"] + [result["control"]]:
        mark = "ok  " if w["pass"] else "FAIL"
        common.say(f"  {mark} {w['name']}: {'arrived' if w['arrived'] else 'stopped'} at {w['end']} "
                   f"({w['reached']}/{w['of']} points, {w['seconds']} s)")
    for name, info in result["shots"].items():
        common.say(f"  {name}: {info['draw_calls']} draw calls, {info['objects']} objects, {info['primitives']} primitives")
    common.say(f"  {result['instances']['mesh_instances']} mesh instances, {result['instances']['static_bodies']} bodies; "
               f"sheet {(folder / 'sheet.png').as_posix()}")
    if failed or errors:
        common.bad(f"house walk: {len(failed)} walks failed, {len(errors)} import errors")
        return 1
    common.ok(f"house walk: {len(result['walks'])} walks with a {2 * result['radius_m']:g} m capsule, the 1.5 m control stops")
    return 0


def check_basement(data: dict, layouts: Path, extra) -> None:
    """The basement's dead ends and sight lines (house_basement, art #78) into tools/out/house/basement.json; a dead end
    with more than one door, or a switch out of sight from a door of its room, fails the command."""
    st = data["settings"]
    folder = Path(layouts) / st.get("dressing_dir", "dressing")
    if not any(lv["level"] == house_basement.LEVEL for lv in data["levels"]):
        return
    dressings = house_dressing.load(folder) if folder.is_dir() else {}
    cat = house_dressing.catalogue(house_dressing.spec_paths(st, extra=extra))
    ends = house_basement.dead_ends(data)
    hall = house_basement.hall_sight(data, dressings, cat)
    switches = house_basement.switch_sight(data, dressings, cat)
    report = common.OUT / "house" / "basement.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"dead_ends": {k: {"doors": d, "stairs": s} for k, (d, s) in ends.items()},
                                  "hall_sight": hall, "switch_sight": switches}, indent=1),
                      encoding="utf-8", newline="\n")
    problems = [f"dead end {k}: {d} doors, {s} stairs (one door, no stairs)" for k, (d, s) in ends.items()
                if (d, s) != (1, 0)]
    problems += [f"{r['line']}: blocked by {r['nearest']}" for r in switches if r["clear"] is not None and r["clear"] <= 0]
    for r in hall:
        common.say(f"  sight {r['line']}: {r['length']:g} m, clear by {r['clear']} m ({r['nearest']})")
    if problems:
        for p in problems:
            common.say(f"  {p}")
        raise common.Failure(f"house basement: {len(problems)} problems")
    blocked = [r["line"] for r in hall if r["clear"] is not None and r["clear"] <= 0]
    common.say(f"house basement: {len(ends)} dead ends with one door each; {len(switches)} switch lines clear; "
               f"hall sight lines blocked: {', '.join(blocked) or 'none'}; {report.as_posix()}")
