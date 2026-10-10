"""`zones`: checks the yard's chill zone and photo gazebo (layouts/house/outdoor/zones/*.toml, house_zones.py) and, with
--shoot, assembles them in an off-screen Godot window at dusk: the zone props, the task props, the kit's gazebo and
railing, grey proxies for the dressing placeholders, a light at every fixture socket; the zones' [[views]] at eye
height, the gazebo with the pose screen and a line-up of the zone props beside a 1.8 m capsule (docs/zones.md)."""

from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path

from .. import common, house_zones
from . import _frames, _godot
from . import props as props_cmd

NAME = "zones"
HELP = "check the chill zone and the photo gazebo (layouts/house/outdoor/zones) and shoot them at dusk off-screen"
SCRIPT = "res://house/zones.gd"
TIMEOUT = 240
HOUSE = common.ROOT / "layouts" / "house" / "house.toml"
KIT_SPEC = common.ROOT / "kits" / "house.json"
## Review light only (not the game's): colour, energy and range per fixture prop at each `light_<k>` socket.
LIGHTS = {"lantern": [[1.0, 0.78, 0.5], 1.6, 4.0], "string_lights_set": [[1.0, 0.82, 0.6], 1.0, 3.5],
          "string_lights_gazebo": [[1.0, 0.82, 0.6], 1.0, 3.0], "fire_pit": [[1.0, 0.5, 0.2], 3.0, 5.5]}
## Extra frames besides the zones' own [[views]]: name, title, eye (x, y, height), look (x, y, height), fov.
EXTRA = [["gazebo_pose", "photo: the gazebo with the pose screen", [13.2, 13.4, 1.6], [8.4, 11.0, 1.1], 60.0],
         ["photo_high", "photo zone from the south-east", [19.0, 21.0, 6.0], [9.0, 11.0, 0.8], 50.0],
         ["chill_high", "chill zone from the south-east", [20.0, 63.0, 6.0], [8.0, 51.0, 0.5], 50.0]]
LINEUP_AT = [40.0, -20.0]  # the line-up's row (plan x, y), away from both zones


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--shoot", type=Path, metavar="DIR",
                        help="stage the GLBs, import, assemble both zones at dusk in an off-screen window and shoot "
                             "them into DIR (sheet.png, frames, zones.json)")


def run(args: argparse.Namespace) -> int:
    zones = house_zones.load_all()
    problems = [f"{z['name']}: {p}" for z in zones for p in house_zones.check(z)]
    for z in zones:
        common.say(f"zone {z['name']}: {len(z['items'])} items, {len(house_zones.placements(z))} pieces placed")
    if problems:
        for p in problems:
            common.say(f"  {p}")
        raise common.Failure(f"zones: {len(problems)} problems")
    common.say("zones: inside the rects, stations, opening, fixtures, overlaps and the walk hold")
    if not args.shoot:
        return 0
    return shoot(zones, args.shoot.resolve())


def request(zones: list[dict]) -> tuple[dict, dict[str, Path]]:
    """The Godot request and the GLBs to stage (staged name -> source file)."""
    raw = common.raw_dir()
    with HOUSE.open("rb") as f:
        kit_dir = raw / tomllib.load(f)["kit_dir"]
    spec = json.loads(KIT_SPEC.read_text(encoding="utf-8"))
    g = props_cmd.geom()
    folders = {}
    built = []
    for src in ("tasks", "zones"):
        pspec = g.load_spec(house_zones.SPECS[src])
        folders[src] = props_cmd.default_out(pspec)
        if src == "zones":
            built = g.build_all(pspec)
    sockets = {d["id"]: [v for _, v in sorted(d["sockets"].items())] for d in built}
    staged: dict[str, Path] = {}
    pieces = []
    for z in zones:
        for p in house_zones.placements(z):
            entry = {"zone": z["name"], "id": p["id"], "src": p["src"], "pos": p["pos"], "yaw": p["yaw"]}
            if p["src"] in ("zones", "tasks", "kit"):
                name = f"kit_{p['id']}" if p["src"] == "kit" else f"prop_{p['id']}"
                staged[name] = (kit_dir if p["src"] == "kit" else folders[p["src"]]) / f"{p['id']}.glb"
                entry["scene"] = f"res://import/{name}.glb"
                if p["id"] in LIGHTS:
                    entry["lights"] = sockets.get(p["id"], [])
                    entry["light"] = LIGHTS[p["id"]]
            else:
                entry["size"] = p["size"]
            pieces.append(entry)
    views = [[f"{z['name']}_{v['name']}", f"{z['name']}: {v['name']} (eye {v['eye'][2]:g} m)", v["eye"], v["look"], 70.0]
             for z in zones for v in z.get("views", [])]
    lineup = [{"id": d["id"], "scene": f"res://import/prop_{d['id']}.glb", "min": d["bounds_m"]["min"],
               "max": d["bounds_m"]["max"]} for d in built]
    for d in built:
        staged[f"prop_{d['id']}"] = folders["zones"] / f"{d['id']}.glb"
    mats = [spec["materials"][m] for m in spec.get("packs", {}).get("set", {}).get("layers", [])]
    pack = {"textures": (kit_dir / "textures").as_posix(), "roughness": [m["roughness"] for m in mats],
            "normal_strength": [m["normal_strength"] for m in mats]} if len(mats) == 3 else {}
    req = {"pieces": pieces, "views": views + EXTRA, "lineup": lineup, "lineup_at": LINEUP_AT, "pack": pack,
           "rects": {z["name"]: z["rect"] for z in zones}}
    return req, staged


def shoot(zones: list[dict], folder: Path) -> int:
    req, staged = request(zones)
    missing = sorted(p.as_posix() for p in staged.values() if not p.is_file())
    if missing:
        raise common.Failure(f"missing GLBs (build the kit and the props first): {', '.join(missing)}")
    return render(req, staged, folder, common.OUT / "zones" / "request.json", "zones")


def render(req: dict, staged: dict[str, Path], folder: Path, path: Path, label: str) -> int:
    """Stages the GLBs, imports them headless and runs zones.gd off-screen on req (also the attic's shoot, attic.py)."""
    _godot.clear_staged(set(staged))
    for name, glb in staged.items():
        _godot.stage(glb, name)
    errors = [line for line in _godot.import_project() if "ERROR" in line]
    for line in errors[:10]:
        common.say(f"  import: {line}")
    folder.mkdir(parents=True, exist_ok=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
    (folder / "zones.json").unlink(missing_ok=True)
    code, output = _godot.godot(["--path", _godot.PROJECT, "--audio-driver", "Dummy", "--position", _frames.POSITION,
                                 "--resolution", "1600x900", "-s", SCRIPT, "--", path.as_posix(), folder.as_posix()],
                                TIMEOUT)
    if code != 0 or not (folder / "zones.json").is_file():
        tail = "\n".join(output.splitlines()[-20:])
        raise common.Failure(f"zones.gd failed (exit code {code}):\n{tail}")
    result = json.loads((folder / "zones.json").read_text(encoding="utf-8"))
    for name, info in result["shots"].items():
        common.say(f"  {name}: {info['draw_calls']} draw calls, {info['primitives']} primitives")
    common.say(f"  {result['instances']} instances, {result['lights']} lights, {result['proxies']} proxies; "
               f"sheet {(folder / 'sheet.png').as_posix()}")
    if errors:
        common.bad(f"{label}: {len(errors)} import errors")
        return 1
    common.ok(f"{label}: {len(result['shots'])} frames at dusk")
    return 0
