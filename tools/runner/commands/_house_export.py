"""The House export's Godot check (`house --export`, art #119, docs/house.md "The export"): opens the export folder
as its own Godot project, imports it headless and loads every room scene with godot/house/export_check.gd."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .. import common
from . import _godot

SCRIPT = common.ROOT / "godot" / "house" / "export_check.gd"
SHEET_SCRIPT = common.ROOT / "godot" / "house" / "export_sheet.gd"
WALKER = common.ROOT / "godot" / "house" / "walker.gd"  # export_check.gd preloads it from beside itself
SHEET_ROOMS = ("kitchen", "storage", "attic")  # the review sheet's rooms: ground floor, basement, attic
SHEET_TILE = (640, 360)  # two tiles per room: a 1280 px wide sheet
CHECK_DIR = "_check"  # the check's own files in the export folder (not part of the package)
PROJECT = """; The House export opened as a Godot project for the art repo's check (house --export); not part of the package.
config_version=5

[application]

config/name="prime-game-art house export check"
config/features=PackedStringArray("4.7", "Forward Plus")

[display]

window/size/borderless=true
window/size/no_focus=true
"""  # [display]: the window starts as one borderless, unfocused pixel; lib/offscreen.gd moves it off-screen (#214)
TIMEOUT = 900


def project(folder: Path) -> None:
    """Writes the export folder's project.godot and the check script (both outside the package's files)."""
    (folder / "project.godot").write_text(PROJECT, encoding="utf-8", newline="\n")
    (folder / CHECK_DIR).mkdir(exist_ok=True)
    for script in (SCRIPT, SHEET_SCRIPT, WALKER):
        shutil.copyfile(script, folder / CHECK_DIR / script.name)


def check(folder: Path, summary: dict, room_dir: str = "levels/house/rooms") -> int:
    """Imports the package headless and loads every room scene: each must load, keep its game root and size_m, hold
    layer-1 static bodies and nothing the game refuses; then the assembled package's check (summary["check"],
    house_export.check_request: colliders, surfaces, the capsule's walks), every problem named by room and node.
    Writes <folder>/_check/load.json (the report) and request.json."""
    return run(folder, summary, room_dir)[0]


def package_lines(pkg: dict) -> list[str]:
    """The summary lines of the package check's report (load.json's "package"): the kit pieces with a collider, the
    floor rays' surfaces and walks, the roof rays' first hits (miss: nothing under the ray), the plot's rays over the
    ground (art #128; hole: no ground, another package's floor) and every collider hit
    without a surface by room (a roof ray's room is "<room> roof"), named by its piece under Dressing, Shell or
    Fixtures."""
    walks = pkg.get("walks", [])
    lines = [f"  package: {sum(1 for p in pkg.get('pieces', {}).values() if p)}/{len(pkg.get('pieces', {}))} kit "
             f"GLBs with a surface hold a collider; {pkg.get('rays', 0)} rays down, surfaces hit "
             f"{json.dumps(pkg.get('surfaces', {}), sort_keys=True)}; {sum(1 for w in walks if w['arrived'])}/"
             f"{len(walks)} walks of the 1.36 m capsule arrive"]
    paints = pkg.get("paints", {})
    if paints.get("surfaces"):
        lines.append(f"  kit material: {paints['surfaces']} set surfaces, {paints.get('bare', 0)} without it; painted "
                     f"rooms carrying their paint: {', '.join(paints.get('painted', [])) or 'none'}")
    if pkg.get("roof_rays"):
        lines.append(f"  roof: {pkg['roof_rays']} rays down from over the ridge, first hits "
                     f"{json.dumps(pkg.get('roof_surfaces', {}), sort_keys=True)} (miss: past the eaves)")
    if pkg.get("plot_rays"):
        lines.append(f"  plot: {pkg['plot_rays']} rays down over the ground, surfaces hit "
                     f"{json.dumps(pkg.get('plot_surfaces', {}), sort_keys=True)} (hole: another package's floor)")
    if pkg.get("none_at"):
        where: dict = {}
        for path, rid in pkg["none_at"].items():
            group = next((g for g in ("Dressing", "Shell", "Fixtures") if f"/{g}/" in path), "")
            where.setdefault(rid, []).append(path.split(f"/{group}/")[1].split("/")[0] if group else path)
        lines.append("  hits without a surface (not the shell): " + "; ".join(
            f"{rid}: {', '.join(sorted(set(names)))}" for rid, names in sorted(where.items())))
    return lines


def run(folder: Path, summary: dict, room_dir: str = "levels/house/rooms") -> tuple[int, list[str]]:
    """check's work: (exit code, the problems found)."""
    project(folder)
    request = folder / CHECK_DIR / "request.json"
    request.write_text(json.dumps(summary.get("check", {"rooms": []}), indent=1), encoding="utf-8", newline="\n")
    code, output = _godot.godot(["--headless", "--path", folder, "--import"], TIMEOUT)
    errors = [line for line in _godot.noteworthy(output) if "ERROR" in line]
    if code != 0:
        raise common.Failure(f"godot --import of the export exited {code}:\n" + "\n".join(output.splitlines()[-20:]))
    out = folder / CHECK_DIR / "load.json"
    out.unlink(missing_ok=True)
    code, output = _godot.godot(["--headless", "--path", folder, "-s", f"res://{CHECK_DIR}/{SCRIPT.name}", "--",
                                 f"res://{room_dir}", out.as_posix(), request.as_posix()], TIMEOUT)
    if code != 0 or not out.is_file():
        raise common.Failure(f"export_check.gd failed (exit {code}):\n" + "\n".join(output.splitlines()[-20:]))
    errors += [line for line in _godot.noteworthy(output) if "ERROR" in line]
    report = json.loads(out.read_text(encoding="utf-8"))
    rooms = report["rooms"]
    bad = []
    for rid, want in summary["rooms"].items():
        r = rooms.get(rid)
        if not r or not r["loaded"]:
            bad.append(f"{rid}: does not load")
            continue
        if r["root"] != want["node"] or r["size_m"] is None:
            bad.append(f"{rid}: root {r['root']}, size_m {r['size_m']}")
        if want["kit"] and r["bodies"] == 0:
            bad.append(f"{rid}: no layer-1 static body")
        bad += [f"{rid}: {x}" for x in r["refused"]]
        common.say(f"  {rid}: {r['instances']} instances, {r['meshes']} meshes, {r['bodies']} layer-1 bodies "
                   f"({r['shapes']} shapes), {r['lights']} lights")
    pkg = report.get("package", {})
    bad += pkg.get("problems", [])
    for line in package_lines(pkg):
        common.say(line)
    if pkg.get("outside"):
        common.say(f"  walks leaving the package (walked with the next): {', '.join(pkg['outside'])}")
    for line in errors[:10]:
        common.say(f"  godot: {line}")
    for b in bad:
        common.say(f"  {b}")
    if bad or errors:
        common.bad(f"house export check: {len(bad)} problems, {len(errors)} Godot errors; {out.as_posix()}")
        return 1, bad + errors
    common.ok(f"house export check: {len(rooms)} room scenes load headless from {folder.as_posix()}; {out.as_posix()}")
    return 0, []


def sheet(folder: Path, summary: dict, room_dir: str = "levels/house/rooms") -> int:
    """The review sheet: export_sheet.gd in an off-screen window opens SHEET_ROOMS (those in the package) from the
    export folder and shoots two eye-height views of each; <folder>/_check/sheet.png (1280 px wide) and sheet.json."""
    names = [n for n in SHEET_ROOMS if n in summary["rooms"]]
    if not names:
        common.say("  review sheet: none of its rooms is in this package")
        return 0
    project(folder)
    out = folder / CHECK_DIR
    (out / "sheet.json").unlink(missing_ok=True)
    w, h = SHEET_TILE
    code, output = _godot.window(["--path", folder, "--audio-driver", "Dummy", "-s",
                                  f"res://{CHECK_DIR}/{SHEET_SCRIPT.name}", "--", f"rooms=res://{room_dir}",
                                  f"names={','.join(names)}", f"out={out.as_posix()}", f"tile={w}x{h}"],
                                 (w * 2, h * 2), TIMEOUT)
    if code != 0 or not (out / "sheet.json").is_file():
        raise common.Failure(f"export_sheet.gd failed (exit {code}):\n" + "\n".join(output.splitlines()[-20:]))
    for shot in json.loads((out / "sheet.json").read_text(encoding="utf-8"))["shots"]:
        common.say(f"  {shot['room']} view {shot['cam']}: {shot['draw_calls']} draw calls, {shot['lights']} lights")
    common.ok(f"house export sheet: {', '.join(names)}; {(out / 'sheet.png').as_posix()}")
    return 0
