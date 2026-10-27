"""`ship --export DIR`'s Godot parts (art #335, docs/ship.md "The export"): the scene saved by
godot/ship/export_scene.gd in the art project, then the package (tools/runner/ship_export.py) opened as its own Godot
project: the headless load, the pieces' sizes against Blender's, the capsule walk on the exported scene, and the
off-screen views beside `ship --shoot`'s of the same views (the look unchanged, by numbers)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .. import common, ship_export, ship_layout
from . import _godot, _house_export

EXPORT_SCRIPT = "res://ship/export_scene.gd"
CHECK_SCRIPT = common.ROOT / "godot" / "ship" / "export_check.gd"
CHECK_DIR = "_check"
TIMEOUT = 300
SIZE_TOL_M = 0.01
# the views shot from the package and by `ship --shoot` (ship.toml [shots]): outside, the hall at eye height (a
# player's view), a tip room; the look is unchanged when each pair's mean difference stays under MAX_MEAN_ABS (0..255)
VIEWS = ("out_hero", "in_hall", "in_tip_e")
MAX_MEAN_ABS = 2.0


def scene(layout: dict, pieces: Path, request: dict, staged: dict[str, Path], folder: Path) -> Path:
    """Runs export_scene.gd headless on the staged pieces; returns godot/import/ship_export/ (ship.tscn and .tres)."""
    from .ship import _stage
    built = _godot.IMPORT_DIR / ship_export.BUILT
    if built.is_dir():
        shutil.rmtree(built)
    errors = _stage(staged)
    if errors:
        raise common.Failure(f"ship --export: {len(errors)} import errors")
    floor = layout["deck"]["floor_h"]
    walk = layout["walk"]["points"][0]
    request.update({"mode": "export", "stations": [[s["name"], s["spot"], s["package"], s["kind"], s["at"], s["yaw"]]
                                                   for s in ship_export.stations(layout)],
                    "spawn": [walk[0], walk[2], walk[1]], "spawn_yaw": 180.0, "deck_h": floor,
                    "size_m": [round(v, 3) for v in ship_layout.extent(layout)]})
    path = folder / CHECK_DIR / "export_request.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(request, indent=1), encoding="utf-8", newline="\n")
    code, output = _godot.godot(["--headless", "--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s",
                                 EXPORT_SCRIPT, "--", path.as_posix(), (folder / CHECK_DIR).as_posix()], TIMEOUT)
    if code != 0 or not (built / "ship.tscn").is_file():
        raise common.Failure(f"export_scene.gd failed (exit {code}):\n" + "\n".join(output.splitlines()[-20:]))
    info = json.loads((folder / CHECK_DIR / "export.json").read_text(encoding="utf-8"))
    common.say(f"  scene: {info['pieces']} pieces, {info['lights']} lights ({info['emissive_lights']} from the glow), "
               f"{info['probes']} probes, {info['overrides']} material overrides, {info['stations']} station spots")
    return built


def project(folder: Path) -> None:
    """The package's project.godot (the House export's: Forward Plus, the off-screen window) and the check script."""
    _house_export.project(folder)
    shutil.copyfile(CHECK_SCRIPT, folder / CHECK_DIR / CHECK_SCRIPT.name)


def check(layout: dict, pieces: Path, folder: Path) -> tuple[list[str], dict]:
    """The headless import and load of the package; returns (problems, load.json)."""
    project(folder)
    code, output = _godot.godot(["--headless", "--path", folder, "--import"], TIMEOUT)
    if code != 0:
        raise common.Failure(f"godot --import of the package exited {code}:\n" + "\n".join(output.splitlines()[-20:]))
    errors = [line for line in _godot.noteworthy(output) if "ERROR" in line]
    pl = layout["player"]
    req = {"scene": f"res://{ship_export.SCENE}",
           "pieces": {p["id"]: f"res://{ship_export.ASSET_DIR}/{p['id']}.glb" for p in layout["pieces"]},
           "walk": {"r": pl["capsule_radius_m"], "h": pl["capsule_height_m"],
                    "points": [[p[0], p[2], p[1]] for p in layout["walk"]["points"]]}}
    path = folder / CHECK_DIR / "check_request.json"
    path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
    out = folder / CHECK_DIR / "load.json"
    out.unlink(missing_ok=True)
    code, output = _godot.godot(["--headless", "--path", folder, "--audio-driver", "Dummy", "-s",
                                 f"res://{CHECK_DIR}/{CHECK_SCRIPT.name}", "--", "check", path.as_posix(),
                                 (folder / CHECK_DIR).as_posix()], TIMEOUT)
    if code != 0 or not out.is_file():
        raise common.Failure(f"export_check.gd failed (exit {code}):\n" + "\n".join(output.splitlines()[-20:]))
    errors += [line for line in _godot.noteworthy(output) if "ERROR" in line]
    got = json.loads(out.read_text(encoding="utf-8"))
    blender = json.loads((pieces / "build_report.json").read_text(encoding="utf-8"))["pieces"]
    problems = list(errors[:10])
    worst = 0.0
    for pid, b in got["bounds"].items():
        want = blender[pid]["bounds"]
        off = max(abs(x - y) for k in ("min", "max") for x, y in zip(b[k], want[k]))
        worst = max(worst, off)
        if off > SIZE_TOL_M:
            problems.append(f"{pid}: the package's bounds differ from Blender's by {off:.3f} m")
    for p in layout["pieces"]:
        if p["collide"] and got["colliders"].get(p["id"], 0) < 1:
            problems.append(f"{p['id']}: no collider in the package")
    if got["root"] != "Ship" or not got["size_m"]:
        problems.append(f"the scene's root is {got['root']}, size_m {'set' if got['size_m'] else 'missing'}")
    problems += [f"a script on {n}" for n in got["scripts"]]
    want_st = {s["name"] for s in ship_export.stations(layout)}
    if set(got["stations"]) != want_st:
        problems.append(f"Stations holds {sorted(got['stations'])}, wants {sorted(want_st)}")
    w = got["walk"]
    if not w["arrived"]:
        problems.append(f"the capsule walk stopped at {w['reached']}/{w['of']} near {w['stuck']}")
    got["size_worst_m"] = worst
    common.say(f"  load: {got['pieces']} pieces, {got['bodies']} layer-1 bodies, {got['lights']} lights, "
               f"{len(got['stations'])} station spots; sizes within {worst * 1000:.1f} mm of Blender's; walk "
               f"{w['reached']}/{w['of']} points in {w['seconds']:.1f} s, lowest {w['min_y']:.2f} m")
    return problems, got


def compare(layout: dict, pieces: Path, folder: Path) -> tuple[list[str], dict]:
    """`ship --shoot` of VIEWS into <folder>/_check/ref, then the same views from the package off-screen; returns
    (problems, shots.json)."""
    from .ship import shoot, shot_views
    views = [v for v in shot_views(layout)[0] if v[0] in VIEWS]
    ref = folder / CHECK_DIR / "ref"
    views_file = folder / CHECK_DIR / "views.json"
    views_file.write_text(json.dumps(views, indent=1), encoding="utf-8", newline="\n")
    built_at = (pieces / "build_report.json").stat().st_mtime
    if all((ref / f"{v[0]}.png").is_file() and (ref / f"{v[0]}.png").stat().st_mtime > built_at for v in views):
        common.say(f"  the reference shots of {', '.join(VIEWS)} are newer than the build: kept ({ref.as_posix()})")
    elif shoot(layout, pieces, ref, str(views_file)):
        raise common.Failure("ship --shoot of the compare views failed")
    project(folder)
    req = {"scene": f"res://{ship_export.SCENE}", "refs": ref.as_posix(),
           "views": [[v[0], v[1], [v[2][0], v[2][2], v[2][1]], [v[3][0], v[3][2], v[3][1]], v[4]] for v in views]}
    path = folder / CHECK_DIR / "shoot_request.json"
    path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
    shots = folder / CHECK_DIR / "shots"
    (shots / "shots.json").unlink(missing_ok=True)
    from .ship import VIEW_SIZE
    code, output = _godot.window(["--path", folder, "--audio-driver", "Dummy", "-s",
                                  f"res://{CHECK_DIR}/{CHECK_SCRIPT.name}", "--", "shoot", path.as_posix(),
                                  shots.as_posix()], VIEW_SIZE, TIMEOUT)
    if code != 0 or not (shots / "shots.json").is_file():
        raise common.Failure(f"export_check.gd shoot failed (exit {code}):\n" + "\n".join(output.splitlines()[-20:]))
    got = json.loads((shots / "shots.json").read_text(encoding="utf-8"))["shots"]
    problems = []
    for name, s in got.items():
        common.say(f"  {name}: mean difference {s.get('mean_abs')} of 255, {100 * s.get('off_share', 1):.2f}% pixels "
                   f"off by more than 16; {s['draw_calls']} draw calls, {s['primitives']} primitives, "
                   f"{s['gpu_ms']} GPU ms at {s['size'][0]}x{s['size'][1]}")
        if not 0 <= s.get("mean_abs", -1) <= MAX_MEAN_ABS:
            problems.append(f"{name}: the package's view differs from ship --shoot's (mean {s.get('mean_abs')})")
    return problems, got
