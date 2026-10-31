"""`lobby --export DIR`'s Godot parts (art #356 step 5b, docs/lobby.md "The export"): the scene saved by
godot/lobby/export_scene.gd in the art project, then the package (tools/runner/lobby_export.py) opened as its own Godot
project beside a copy of the ship package it instances: the headless load, the hall pieces' sizes against Blender's,
the scene's tree, the capsule walk, and the off-screen views beside `lobby --shoot`'s (the look unchanged, by
numbers), as the ship's export (_ship_export.py)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .. import common, lobby_export
from . import _godot, _house_export

EXPORT_SCRIPT = "res://lobby/export_scene.gd"
CHECK_SCRIPT = common.ROOT / "godot" / "lobby" / "export_check.gd"
CHECK_DIR = "_check"
TIMEOUT = 300
SIZE_TOL_M = 0.01
# the views shot from the package and by `lobby --shoot` ([review] views): a spawn's eye (the player's first view),
# the whole hall from the north-west corner, the ship and the hall from the window
VIEWS = ("spawn_eye", "corner_nw", "c_back")
MAX_MEAN_ABS = 2.0


def stage_earth(files: dict[str, str]) -> dict[str, str]:
    """Copies the Earth's JPEGs into godot/import/lobby_earth/ with the package's .import (VRAM compressed, mipmaps),
    so the scene refers to imported textures; returns map -> res:// path. Only changed files are written."""
    dst = _godot.IMPORT_DIR / lobby_export.EARTH_STAGE
    dst.mkdir(parents=True, exist_ok=True)
    out = {}
    for k, path in files.items():
        src = Path(path)
        target = dst / src.name
        if not target.is_file() or target.read_bytes() != src.read_bytes():
            shutil.copyfile(src, target)
        imp = target.with_name(target.name + ".import")
        if not imp.is_file() or "compress/mode=2" not in imp.read_text(encoding="utf-8"):
            imp.write_text(lobby_export.earth_import_text(), encoding="utf-8", newline="\n")
        out[k] = f"res://import/{lobby_export.EARTH_STAGE}/{src.name}"
    return out


def scene(layout: dict, request: dict, staged: dict[str, Path], folder: Path, stage) -> Path:
    """Runs export_scene.gd headless; returns godot/import/lobby_export/ (lobby_hall.tscn and the .tres files)."""
    built = _godot.IMPORT_DIR / lobby_export.BUILT
    if built.is_dir():
        shutil.rmtree(built)
    request["earth"]["textures"] = stage_earth(request["earth"]["textures"])
    errors = stage(staged)
    if errors:
        raise common.Failure(f"lobby --export: {len(errors)} import errors")
    h = layout["hall"]
    request.update({"mode": "export", "spawns": [s["at"] for s in lobby_export.spawns(layout)],
                    "spawn_yaw": lobby_export.SPAWN_YAW,
                    "size_m": [h["x1"] - h["x0"], h["zS"] - h["zN"]],
                    "meta": {"art_issue": "prime-game-art#356", "credit": lobby_export.CREDIT,
                             "ship_scene": f"res://{lobby_export.SHIP_SCENE}"}})
    path = folder / CHECK_DIR / "export_request.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(request, indent=1), encoding="utf-8", newline="\n")
    code, output = _godot.godot(["--headless", "--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s",
                                 EXPORT_SCRIPT, "--", path.as_posix(), (folder / CHECK_DIR).as_posix()], TIMEOUT)
    bad = [line.strip() for line in output.splitlines() if "SCRIPT ERROR" in line]
    if code != 0 or bad or not (built / "lobby_hall.tscn").is_file():
        raise common.Failure(f"export_scene.gd failed (exit {code}):\n" + "\n".join((bad or output.splitlines())[-20:]))
    info = json.loads((folder / CHECK_DIR / "export.json").read_text(encoding="utf-8"))
    common.say(f"  scene: {info['hall_pieces']} hall placements, {info['lights']} lights, {info['probes']} probes, "
               f"{info['spawns']} spawns, {info['editable_instances']} editable instances, the ship {info['ship']}")
    return built


def ship_copy(ship_src: Path, folder: Path) -> int:
    """The ship package's files (its package.json's list) beside the lobby's, for the check only (not the lobby's
    files); only changed files are written. Returns their count."""
    meta = json.loads((ship_src / "package.json").read_text(encoding="utf-8"))
    for rel in meta["files"]:
        target = folder / rel
        if not target.is_file() or target.stat().st_size != (ship_src / rel).stat().st_size:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ship_src / rel, target)
        imp = ship_src / f"{rel}.import"
        if imp.is_file() and not (folder / f"{rel}.import").is_file():
            shutil.copyfile(imp, folder / f"{rel}.import")
    return len(meta["files"])


def project(folder: Path) -> None:
    """The package's project.godot (the House export's: Forward Plus, the off-screen window) and the check script."""
    (folder / "project.godot").write_text(_house_export.PROJECT, encoding="utf-8", newline="\n")
    (folder / CHECK_DIR).mkdir(exist_ok=True)
    _godot.install_offscreen(folder)
    shutil.copyfile(CHECK_SCRIPT, folder / CHECK_DIR / CHECK_SCRIPT.name)


def check(layout: dict, pieces: Path, folder: Path) -> tuple[list[str], dict]:
    """The headless import and load of the package; returns (problems, load.json)."""
    project(folder)
    code, output = _godot.godot(["--headless", "--path", folder, "--import"], TIMEOUT)
    if code != 0:
        raise common.Failure(f"godot --import of the package exited {code}:\n" + "\n".join(output.splitlines()[-20:]))
    errors = [line for line in _godot.noteworthy(output) if "ERROR" in line]
    w = layout["walk"]
    req = {"scene": f"res://{lobby_export.SCENE}",
           "pieces": {pid: f"res://{lobby_export.ASSET_DIR}/{pid}.glb" for pid in lobby_export.piece_ids(layout)},
           "walk": {"r": w["r"], "h": w["h"], "points": [[float(p[0]), 0.0, float(p[1])] for p in w["points"]]}}
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
    return problems(layout, pieces, got, errors), got


def problems(layout: dict, pieces: Path, got: dict, errors: list[str]) -> list[str]:
    """What load.json must hold (plain Python, tested): sizes, colliders, the tree, the spawns, the ship, the Earth,
    the walk."""
    blender = json.loads((pieces / "build_report.json").read_text(encoding="utf-8"))["pieces"]
    out = list(errors[:10])
    worst = 0.0
    for pid, b in got["bounds"].items():
        want = blender[pid]["bounds"]
        off = max(abs(x - y) for k in ("min", "max") for x, y in zip(b[k], want[k]))
        worst = max(worst, off)
        if off > SIZE_TOL_M:
            out.append(f"{pid}: the package's bounds differ from Blender's by {off:.3f} m")
    got["size_worst_m"] = worst
    for p in layout["pieces"]:
        if p["collide"] and got["colliders"].get(p["id"], 0) < 1:
            out.append(f"{p['id']}: no collider in the package")
    if got["root"] != "LobbyHall" or "size_m" not in got["meta"] or "camera_far_m" not in got["meta"]:
        out.append(f"the scene's root is {got['root']}, metadata {sorted(got['meta'])}")
    want_groups = ["Hall", "Ship", "Earth", "Environment", "Lights", "Probes", "Markers"]
    if sorted(got["groups"]) != sorted(want_groups):
        out.append(f"the root holds {got['groups']}, wants {want_groups}")
    out += [f"a script on {n}" for n in got["scripts"]]
    want_sp = lobby_export.spawns(layout)
    if [s["name"] for s in got["spawns"]] != [s["name"] for s in want_sp]:
        out.append(f"Markers holds {[s['name'] for s in got['spawns']]}")
    for g, w in zip(got["spawns"], want_sp):
        if max(abs(a - b) for a, b in zip(g["at"], w["at"])) > 1e-3 or abs(g["forward"][2] - 1.0) > 1e-3:
            out.append(f"{g['name']} at {g['at']} facing {g['forward']}, wants {w['at']} facing +z (the window)")
    s = got["ship"]
    if s["scene"] != f"res://{lobby_export.SHIP_SCENE}":
        out.append(f"Ship instances {s['scene']!r}, wants the ship package's res://{lobby_export.SHIP_SCENE}")
    if max(abs(a - b) for a, b in zip(s["at"], layout["ship"]["origin"])) > 1e-3:
        out.append(f"Ship stands at {s['at']}, wants {layout['ship']['origin']}")
    if s["clearing_visible"] or s["clearing_processing"]:
        out.append("Ship/Clearing is still drawn or processed")
    if s["environments"] or s["suns_visible"]:
        out.append(f"the ship package keeps {s['environments']} environments and {s['suns_visible']} suns on")
    if any(v is None or abs(v) > 0.05 for v in s["jaws"].values()):
        out.append(f"the jaw nose is not shut: {s['jaws']}")
    if s["off_layer"]:
        out.append(f"{s['off_layer']} of the ship's {s['meshes']} drawn meshes are off render layer 11")
    if s["colliders_on"] < 1:
        out.append("the ship has no collider on")
    e = got["earth"]
    if not e or e["far_mode"] != 1.0 or any(not t for t in e["textures"]):
        out.append(f"Earth/EarthObject: {e}")
    elif any(not t.startswith(f"res://{lobby_export.EARTH_DIR}/") for t in e["textures"]):
        out.append(f"the Earth's textures lie outside the package: {e['textures']}")
    w = got["walk"]
    if not w["arrived"]:
        out.append(f"the capsule walk stopped at {w['reached']}/{w['of']} near {w['stuck']}")
    common.say(f"  load: {len(got['bounds'])} hall GLBs within {worst * 1000:.1f} mm of Blender's; {got['lights']} "
               f"lights, {got['probes']} probes, {len(got['spawns'])} spawns; the ship {s['colliders_on']} colliders on "
               f"({s['colliders_off']} off in Clearing), {s['meshes']} meshes drawn, {s['lights_visible']} lamps on, "
               f"jaws {s['jaws']}; walk {w['reached']}/{w['of']} points in {w['seconds']:.1f} s, lowest {w['min_y']:.2f} m")
    return out


def compare(layout: dict, folder: Path, refs: Path) -> tuple[list[str], dict]:
    """The VIEWS from the package off-screen beside `lobby --shoot`'s shots in refs; returns (problems, shots.json)."""
    views = [v[:5] for v in layout["review"]["views"] if v[0] in VIEWS]
    missing = [v[0] for v in views if not (refs / f"{v[0]}.png").is_file()]
    if missing:
        raise common.Failure(f"no reference shots of {', '.join(missing)} in {refs.as_posix()} (lobby --shoot)")
    project(folder)
    req = {"scene": f"res://{lobby_export.SCENE}", "refs": refs.as_posix(), "views": views}
    path = folder / CHECK_DIR / "shoot_request.json"
    path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
    shots = folder / CHECK_DIR / "shots"
    (shots / "shots.json").unlink(missing_ok=True)
    from .lobby import VIEW_SIZE
    code, output = _godot.window(["--path", folder, "--audio-driver", "Dummy", "-s",
                                  f"res://{CHECK_DIR}/{CHECK_SCRIPT.name}", "--", "shoot", path.as_posix(),
                                  shots.as_posix()], VIEW_SIZE, TIMEOUT)
    if code != 0 or not (shots / "shots.json").is_file():
        raise common.Failure(f"export_check.gd shoot failed (exit {code}):\n" + "\n".join(output.splitlines()[-20:]))
    got = json.loads((shots / "shots.json").read_text(encoding="utf-8"))["shots"]
    ref_info = json.loads((refs / "shots.json").read_text(encoding="utf-8"))["shots"] if (refs / "shots.json").is_file() else {}
    out = []
    for name, s in got.items():
        r = ref_info.get(name, {})
        common.say(f"  {name}: mean difference {s.get('mean_abs')} of 255, {100 * s.get('off_share', 1):.2f}% pixels "
                   f"off by more than 16; {s['draw_calls']} draw calls ({r.get('draw_calls')} in --shoot), "
                   f"{s['primitives']} primitives, {s['gpu_ms']} GPU ms ({r.get('gpu_ms', 0):.2f}) at "
                   f"{s['size'][0]}x{s['size'][1]}")
        if not 0 <= s.get("mean_abs", -1) <= MAX_MEAN_ABS:
            out.append(f"{name}: the package's view differs from lobby --shoot's (mean {s.get('mean_abs')})")
    return out, got
