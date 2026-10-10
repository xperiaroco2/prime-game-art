"""`house --bake`: the House's lightmap bake per zone (#83, from #83a's spike; docs/house.md "Light"). Stages the kit
and prop GLBs the zone scenes use, imports them, builds each zone's bake scene headless (godot/house/zone_build.gd),
bakes it in the editor through the lmbake plugin in an off-screen window (night only: house_bake.editor_allowed),
then shoots the baked and real-time frames (godot/house/bake_shots.gd) and measures them. Every Godot run takes the
heavy-run lock (common.run)."""

from __future__ import annotations

import json
import time
from pathlib import Path

from .. import common, house_bake
from . import _frames, _godot

BUILD = "res://house/zone_build.gd"
SHOTS = "res://house/bake_shots.gd"
BAKE_DIR = _godot.PROJECT / "import" / "house" / "bake"
TIMEOUT = 900
REVIEW_ROOMS = {"ground": ["living_room", "kitchen"], "basement": ["storage", "generator_hall"],
                "upper": ["bedroom", "landing"]}


def stage(data: dict, scenes: Path, props: dict) -> list[str]:
    """Stages every kit piece and prop GLB the scenes under `scenes` instance; returns the names staged."""
    texts = [p.read_text(encoding="utf-8") for p in scenes.rglob("*.tscn")]
    names = house_bake.used_glbs(texts)
    kit = common.raw_dir() / data["settings"]["kit_dir"]
    staged = []
    for name in sorted(names):
        if name.startswith("kit_"):
            src, params = kit / f"{name[4:]}.glb", house_bake.KIT_IMPORT
        else:
            src, params = props.get(name[5:]), house_bake.PROP_IMPORT
        if src is None or not Path(src).is_file():
            common.say(f"  bake: no GLB for {name} (left out)")
            continue
        _godot.stage(Path(src), name, params)
        staged.append(name)
    return staged


def run(data: dict, lights: dict, zones: list[str], preset: str, review: Path | None, no_bake: bool,
        props: dict) -> int:
    unknown = [z for z in zones if z not in lights["zones"]]
    if unknown:
        raise common.Failure(f"house --bake: no zone {', '.join(unknown)} in lights.toml")
    raw = common.raw_dir()
    if not no_bake and not house_bake.editor_allowed(time.time(), house_bake.grant_text(raw)):
        raise common.Failure(house_bake.EDITOR_BAN)
    staged = stage(data, _godot.PROJECT / "import" / "house", props)
    _godot.clear_staged(set(staged))
    errors = [line for line in _godot.import_project() if "ERROR" in line]
    for line in errors[:10]:
        common.say(f"  import: {line}")
    work = common.OUT / "house" / "bake"
    work.mkdir(parents=True, exist_ok=True)
    uv2 = work / "uv2.json"
    pieces = json.loads((raw / data["settings"]["kit_dir"] / "pieces.json").read_text(encoding="utf-8"))
    uv2.write_text(json.dumps(house_bake.uv2_table(pieces)), encoding="utf-8", newline="\n")
    bake_json = work / "bake.json"
    bake_json.write_text(json.dumps(lights["bake"]), encoding="utf-8", newline="\n")
    report: dict = {"preset": preset, "zones": {}}
    for zone in zones:
        texel = float(lights["zones"][zone][lights["presets"][preset]["lightmap"]])
        args = house_bake.build_args(zone, preset, texel, lights["bake"], uv2.as_posix(), bake_json.as_posix())
        code, out = _godot.godot(["--headless", "--path", _godot.PROJECT, "-s", BUILD, "--", *args], TIMEOUT)
        built = BAKE_DIR / f"{zone}_{preset}_build.json"
        if code != 0 or not built.is_file():
            raise common.Failure(f"zone_build.gd {zone} exited {code}:\n" + "\n".join(out.splitlines()[-15:]))
        z = report["zones"][zone] = {"build": json.loads(built.read_text(encoding="utf-8"))}
        common.say(f"  {zone} {preset}: {z['build']['meshes']} meshes, {z['build']['lights']} lights, "
                   f"{z['build']['texels'] / 1e6:.2f} M texels at {texel:g}/m")
        if no_bake:
            continue
        if not house_bake.editor_allowed(time.time(), house_bake.grant_text(raw)):
            raise common.Failure(house_bake.EDITOR_BAN)
        t0 = time.time()
        scene = f"res://import/house/bake/{zone}_{preset}.scn"
        code, out = _godot.godot(["--editor", "--path", _godot.PROJECT, "--position", _frames.POSITION,
                                  "--resolution", "1280x720", "--", f"lmbake={scene}"], TIMEOUT)
        log = BAKE_DIR / f"{zone}_{preset}_bake_log.txt"
        z["bake"] = {"exit": code, "seconds": round(time.time() - t0),
                     "log": log.read_text(encoding="utf-8") if log.is_file() else ""}
        if code != 0 or "light_data=none" in z["bake"]["log"] or not log.is_file():
            raise common.Failure(f"the editor bake of {zone} failed (exit {code}): {z['bake']['log'][-400:]}")
        common.say(f"  {zone} {preset}: baked in {z['bake']['seconds']} s")
    (work / "bake_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8", newline="\n")
    if review and not no_bake:
        shoot(data, zones, preset, review)
    common.ok(f"house --bake: {len(zones)} zones ({preset}); {(work / 'bake_report.json').as_posix()}")
    return 0


def shoot(data: dict, zones: list[str], preset: str, review: Path) -> None:
    """Per zone a baked and a real-time row from its review rooms' E1 cameras and seam camera; sheet.png, the frames
    and measures.json (L*, dark %, C* p90 per frame) into `review`."""
    rows = []
    for zone in zones:
        cams = house_bake.views(data, REVIEW_ROOMS.get(zone, [])) if zone in REVIEW_ROOMS else []
        scene = f"res://import/house/bake/{zone}_{preset}.scn"
        rows += [{"label": f"{zone}_{preset}_{mode}", "scene": scene, "mode": mode, "cams": cams}
                 for mode in ("baked", "realtime") if cams]
    jobs = common.OUT / "house" / "bake" / "shots.json"
    jobs.write_text(json.dumps({"tile": [426, 240], "per_line": 1, "rows": rows}, indent=1), encoding="utf-8",
                    newline="\n")
    review.mkdir(parents=True, exist_ok=True)
    code, out = _godot.godot(["--path", _godot.PROJECT, "--position", _frames.POSITION, "--resolution", "1280x720",
                              "-s", SHOTS, "--", f"jobs={jobs.as_posix()}", f"out={review.as_posix()}"], TIMEOUT)
    if code != 0:
        raise common.Failure(f"bake_shots.gd exited {code}:\n" + "\n".join(out.splitlines()[-15:]))
    numbers = {}
    for png in sorted(review.glob("*_*_*.png")):
        if png.name != "sheet.png":
            numbers[png.stem] = house_bake.measures(*house_bake.read_png(png))
    (review / "measures.json").write_text(json.dumps(numbers, indent=1), encoding="utf-8", newline="\n")
    for name, m in numbers.items():
        common.say(f"  {name}: L* {m['L_mean']}, dark {m['dark_pct']} %, C* p90 {m['C_p90']}")
