"""`lobby`: the lobby hall (art #356, docs/lobby.md): checks layouts/lobby/hall.toml with art #263's ship in place;
--build the grey massing in headless Blender, one GLB per piece with glTF-Validator; --godot the headless import
(sizes, colliders), a capsule walk and the doors' and the corridor's end's proof; --shoot DIR the review views beside
concepts A and C, a top view, a spawn's eye and the close-ups, in an off-screen window; --grid DIR the taste grid (the
wall-and-floor metal's variants, [look.variants], in the layout's grid views)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .. import blender, common, lobby_layout
from . import _export, _godot

NAME = "lobby"
HELP = ("the lobby hall (layouts/lobby/hall.toml): check it with the ship in place; --build the grey massing GLBs; "
        "--godot import, colliders, walk, doors; --shoot DIR the review views off-screen; --grid DIR the metal variants")
BUILD_SCRIPT = blender.SCRIPTS / "lobby_build.py"
GODOT_SCRIPT = "res://lobby/hall.gd"
BUILD_TIMEOUT = 600
GODOT_TIMEOUT = 300
VIEW_SIZE = (1920, 1080)
SIZE_TOL_M = 0.01


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--check", action="store_true", help="only the layout's check and its text plan (the default)")
    parser.add_argument("--build", action="store_true", help="build the hall's pieces in headless Blender")
    parser.add_argument("--godot", action="store_true", help="import headless: sizes, colliders, the walk, the doors")
    parser.add_argument("--shoot", type=Path, metavar="DIR", help="shoot the review views into DIR (off-screen)")
    parser.add_argument("--grid", type=Path, metavar="DIR", help="shoot the metal variants' grid into DIR (off-screen)")
    parser.add_argument("--out", type=Path, help="the pieces' folder (default <raw>/<layout raw_dir>/pieces)")


def raw(layout: dict) -> Path:
    return common.raw_dir() / layout["raw_dir"]


def ship_scene(layout: dict) -> tuple[list, list, dict, dict]:
    """The ship's kept placements (plan), the dropped ids, the ship's build report and its layout."""
    ship = lobby_layout.ship_layout_data()
    report = lobby_layout.ship_report(layout)
    ids = {p["id"] for p in ship["pieces"]}
    unknown = sorted(set(layout["ship"]["drop"]) - ids)
    if unknown:
        raise common.Failure(f"lobby: [ship] drop names no ship piece: {', '.join(unknown)}")
    return lobby_layout.ship_place(layout, ship), layout["ship"]["drop"], report, ship


def run(args: argparse.Namespace) -> int:
    layout = lobby_layout.load()
    place, drop, report, _ship = ship_scene(layout)
    fp = lobby_layout.footprint(layout, lobby_layout.hull_outline(layout["ship"]["hull"]), report, place)
    problems = lobby_layout.check(layout, fp)
    n = lobby_layout.ship_numbers(layout, fp)
    gaps = lobby_layout.wall_gaps(layout, fp)
    spawn = min(lobby_layout.poly_dist(fp, (x, layout["floor"]["spawns_z"])) for x in layout["floor"]["spawns_x"])
    r, cz = lobby_layout.arc(layout)
    common.say(f"lobby hall v{layout['version']}: window arc r {r:.3f} m (centre z {cz:.3f}); ship nose z {n['nose_z']:.2f}, "
               f"aft z {n['aft_z']:.2f}, middle z {n['middle_z']:.2f}, half span {n['half_span']:.2f} m; "
               f"{len(place)} ship placements, {len(drop)} clearing pieces dropped")
    common.say(f"  spawns to the ship {spawn:.2f} m; ship to " + ", ".join(f"{k} {v:.2f}" for k, v in gaps.items()))
    for p in problems:
        common.say(f"  {p}")
    if problems:
        raise common.Failure(f"lobby: {len(problems)} layout problems")
    plan = raw(layout) / "plan" / "plan.txt"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(lobby_layout.ascii_plan(layout, fp), encoding="utf-8", newline="\n")
    common.ok(f"lobby: hall, arc, ribs, arch, doors, spawns and the ship's place hold; plan {plan.as_posix()}")
    out = (args.out or raw(layout) / "pieces").resolve()
    if args.build:
        code = build(layout, out, n["middle_z"])
        if code:
            return code
    if args.godot:
        code = godot_check(layout, out, place, report, raw(layout) / "godot")
        if code:
            return code
    if args.shoot:
        code = shoot(layout, out, place, args.shoot.resolve())
        if code:
            return code
    if args.grid:
        return shoot(layout, out, place, args.grid.resolve(), grid=True)
    return 0


def look_request(layout: dict, variant: str) -> dict:
    """The look Godot applies to the hall's metals: [look] with one variant."""
    lk = layout["look"]
    return {"id": variant, **lk["variants"][variant], "metals": lk["metals"], "floor": lk["floor"]}


# --- build ---------------------------------------------------------------------------------------------------------
def build(layout: dict, out: Path, ring_z: float) -> int:
    out.mkdir(parents=True, exist_ok=True)
    request = common.OUT / "lobby" / "build_request.json"
    request.parent.mkdir(parents=True, exist_ok=True)
    request.write_text(json.dumps({"layout": layout, "arc": list(lobby_layout.arc(layout)), "ring_z": ring_z}, indent=1),
                       encoding="utf-8", newline="\n")
    blender.run_script(BUILD_SCRIPT, ["--request", str(request), "--out", str(out)], timeout=BUILD_TIMEOUT)
    report = json.loads((out / "build_report.json").read_text(encoding="utf-8"))
    reports = out / "reports"
    reports.mkdir(exist_ok=True)
    bad = []
    for pid, info in report["pieces"].items():
        passed, line = _export.verdict(_export.validate(Path(info["glb"]), reports / f"{pid}.json"))
        common.say(f"  {pid}: {info['triangles']} triangles; {line}")
        if not passed:
            bad.append(pid)
    if bad:
        common.bad(f"lobby --build: {', '.join(bad)} fail glTF-Validator")
        return 1
    tris = sum(i["triangles"] for i in report["pieces"].values())
    common.ok(f"lobby --build: {len(report['pieces'])} GLBs, {tris} triangles, glTF-Validator clean -> {out.as_posix()}")
    return 0


# --- Godot ---------------------------------------------------------------------------------------------------------
def scene_request(layout: dict, out: Path, place: list, ship_report: dict) -> tuple[dict, dict[str, Path], dict]:
    """The pieces (the hall's and the ship's), their placements in the lobby, the GLBs to stage and Blender's bounds."""
    hall = json.loads((out / "build_report.json").read_text(encoding="utf-8"))["pieces"]
    missing = [p["id"] for p in layout["pieces"] if p["id"] not in hall]
    if missing:
        raise common.Failure(f"pieces not built (lobby --build): {', '.join(missing)}")
    ship_dir = common.raw_dir() / layout["ship"]["pieces_dir"]
    ship_ids = sorted({p[0] for p in place})
    staged = {f"lobby_{p['id']}": out / f"{p['id']}.glb" for p in layout["pieces"]}
    staged.update({f"ship_{pid}": ship_dir / f"{pid}.glb" for pid in ship_ids})
    pieces = {p["id"]: f"res://import/lobby_{p['id']}.glb" for p in layout["pieces"]}
    pieces.update({f"ship_{pid}": f"res://import/ship_{pid}.glb" for pid in ship_ids})
    ox, oy, oz = layout["ship"]["origin"]
    places = [[pid, at, yaw] for pid, at, yaw in layout["place"]]
    places += [["door", *door_place(layout, d)] for d in layout["door"]["doors"]]
    places += [[f"ship_{pid}", [at[0] + ox, at[2] + oy, at[1] + oz], yaw] for pid, at, yaw in place]
    bounds = {p["id"]: hall[p["id"]]["bounds"] for p in layout["pieces"]}
    bounds.update({f"ship_{pid}": ship_report[pid]["bounds"] for pid in ship_ids})
    collide = [p["id"] for p in layout["pieces"] if p["collide"]]
    return {"pieces": pieces, "place": places}, staged, {"bounds": bounds, "collide": collide}


def door_place(layout: dict, door: list) -> tuple[list, float]:
    """A door piece's position and yaw: built facing +z with the wall's inner face at its z 0."""
    h = layout["hall"]
    _id, wall, at = door
    if wall == "N":
        return [at, 0.0, h["zN"]], 0.0
    return ([h["x0"], 0.0, at], 90.0) if wall == "W" else ([h["x1"], 0.0, at], -90.0)


def _stage(staged: dict[str, Path]) -> list[str]:
    _godot.clear_staged(set(staged))
    for name, glb in staged.items():
        _godot.stage(glb, name)
    errors = [line for line in _godot.import_project() if "ERROR" in line]
    for line in errors[:10]:
        common.say(f"  import: {line}")
    return errors


def _xz(p: list, y: float = 0.0) -> list[float]:
    return [float(p[0]), y, float(p[1])]


def godot_check(layout: dict, out: Path, place: list, ship_report: dict, folder: Path) -> int:
    req, staged, want = scene_request(layout, out, place, ship_report)
    w = layout["walk"]
    req.update({"mode": "check", "walk": {"r": w["r"], "h": w["h"], "points": [_xz(p) for p in w["points"]]},
                "blocks": [[b[0], _xz(b[1]), _xz(b[2])] for b in w["blocks"]]})
    errors = _stage(staged)
    folder.mkdir(parents=True, exist_ok=True)
    path = common.OUT / "lobby" / "check_request.json"
    path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
    (folder / "check.json").unlink(missing_ok=True)
    code, output = _godot.godot(["--headless", "--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s",
                                 GODOT_SCRIPT, "--", path.as_posix(), folder.as_posix()], GODOT_TIMEOUT)
    if code != 0 or not (folder / "check.json").is_file():
        raise common.Failure(f"hall.gd check failed (exit code {code}):\n" + "\n".join(output.splitlines()[-20:]))
    result = json.loads((folder / "check.json").read_text(encoding="utf-8"))
    problems = list(errors)
    for pid, got in result["bounds"].items():
        exp = want["bounds"][pid]
        off = max(abs(a - b) for k in ("min", "max") for a, b in zip(got[k], exp[k]))
        if off > SIZE_TOL_M:
            problems.append(f"{pid}: Godot's bounds differ from Blender's by {off:.3f} m")
    for pid in want["collide"]:
        if result["colliders"].get(pid, 0) < 1:
            problems.append(f"{pid}: no collider after import")
    wk = result["walk"]
    common.say(f"  walk: {wk['reached']}/{wk['of']} points, {wk['length_m']:.1f} m in {wk['seconds']:.1f} s, end "
               f"{[round(v, 2) for v in wk['end']]}, lowest {wk['min_y']:.3f} m"
               + ("" if wk["arrived"] else f"; stuck near {[round(v, 2) for v in wk['stuck']]}"))
    if not wk["arrived"]:
        problems.append("the capsule walk did not arrive")
    for name, _a, _b, axis, face, side in w["blocks"]:
        b = result["blocks"][name]
        end = b["end"][0 if axis == "x" else 2]
        held = not b["arrived"] and (end - face) * side > 0
        common.say(f"  block {name}: stopped at {axis} {end:.2f} ({(end - face) * side:.2f} m on the hall's side of "
                   f"{axis} {face}){'' if held else ' PASSED THROUGH'}")
        if not held:
            problems.append(f"{name}: the capsule passed")
    for p in problems:
        common.say(f"  {p}")
    if problems:
        common.bad(f"lobby --godot: {len(problems)} problems")
        return 1
    common.ok(f"lobby --godot: {len(result['bounds'])} pieces import at Blender's sizes, "
              f"{sum(result['colliders'].values())} colliders, the walk arrives, {len(w['blocks'])} blocks hold "
              f"({folder.as_posix()})")
    return 0


def shoot(layout: dict, out: Path, place: list, folder: Path, grid: bool = False) -> int:
    req, staged, _want = scene_request(layout, out, place, lobby_layout.ship_report(layout))
    rv = layout["review"]
    req.update({"mode": "shoot", "background": rv["background"], "views": [v[:5] for v in rv["views"]],
                "top": rv["top"], "compare": [[v[0], v[5]] for v in rv["views"] if v[5]],
                "look": look_request(layout, layout["look"]["variant"])})
    if grid:
        req.update({"mode": "grid", "views": [v[:5] for v in rv["views"] if v[0] in rv["grid"]],
                    "variants": [look_request(layout, k) for k in layout["look"]["variants"]]})
    errors = _stage(staged)
    folder.mkdir(parents=True, exist_ok=True)
    path = common.OUT / "lobby" / "shoot_request.json"
    path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
    (folder / "shots.json").unlink(missing_ok=True)
    code, output = _godot.window(["--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s", GODOT_SCRIPT, "--",
                                  path.as_posix(), folder.as_posix()], VIEW_SIZE, GODOT_TIMEOUT)
    if code != 0 or not (folder / "shots.json").is_file():
        raise common.Failure(f"hall.gd shoot failed (exit code {code}):\n" + "\n".join(output.splitlines()[-20:]))
    result = json.loads((folder / "shots.json").read_text(encoding="utf-8"))
    for name, info in result["shots"].items():
        common.say(f"  {name}: {info['draw_calls']} draw calls, {info['primitives']} primitives")
    if errors:
        common.bad(f"lobby --shoot: {len(errors)} import errors")
        return 1
    sheet = folder / ("grid.png" if grid else "sheet.png")
    common.ok(f"lobby --{'grid' if grid else 'shoot'}: {len(result['shots'])} shots, sheet {sheet.as_posix()}")
    return 0
