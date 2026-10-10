"""`attic`: checks the attic's old things and hiding spots and the roof deck's dressing and lookout
(layouts/house/dressing/attic_roof/attic.toml and roof.toml, house_attic.py; docs/house.md, "The attic and the roof
deck") and writes the report: every spot's standing point, the lookout's view per eye. With --shoot, it generates the house's
scenes, places the dressing (library GLBs, grey boxes for the placeholders) and shoots the attic and the roof deck at
dusk in an off-screen Godot window through godot/house/zones.gd."""

from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path

from .. import common, house_attic, house_layout
from . import _props, zones
from . import house as house_cmd

NAME = "attic"
HELP = "check the attic's hiding spots and the roof deck's dressing and lookout (layouts/house/dressing)"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", type=Path, default=common.ROOT / "tools" / "out" / "attic" / "report.json",
                        help="where the report goes (default tools/out/attic/report.json)")
    parser.add_argument("--shoot", type=Path, metavar="DIR",
                        help="then shoot the attic and the roof deck at dusk off-screen into DIR (sheet.png, frames)")
    parser.add_argument("--kit", type=Path, action="append", default=[], metavar="DIR",
                        help="a folder searched before the layout's kit_dir for kit GLBs (a piece not built there yet)")


def run(args: argparse.Namespace) -> int:
    rep = house_attic.report()
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8", newline="\n")
    spots = rep["attic"]["spots"]
    common.say(f"attic: {rep['attic']['items']} items, {sum(s['reachable'] for s in spots)}/{len(spots)} hiding "
               f"spots reachable for a pick-up")
    for k, v in enumerate(rep["roof"]["lookout"]):
        see = ", ".join(f"{t} {100 * f:.0f}%" for t, f in v["see"].items())
        label = "the station" if k == 0 else "an alternative, not the acceptance"
        common.say(f"roof: lookout eye {v['eye']} ({label}): {see}; house windows in view {len(v['house_windows'])}; "
                   f"attic windows in view {v['attic_windows'] or 'none'}")
    if rep["roof"]["open"]:
        for m in rep["roof"]["not_met"]:
            common.say(f"roof: NOT MET, open for the engineer: {m}")
        common.say(f"roof: open: {rep['roof']['open']}")
    problems = [f"attic: {p}" for p in rep["attic"]["problems"]] + [f"roof: {p}" for p in rep["roof"]["problems"]]
    for p in problems:
        common.say(f"  {p}")
    common.say(f"report: {args.json}")
    if problems:
        raise common.Failure(f"attic: {len(problems)} problems")
    if not args.shoot:
        return 0
    return shoot(args.shoot.resolve(), [k.resolve() for k in args.kit])


F = 6.4  # the attic's and the deck's floor (layouts/house/attic.toml, roof.toml); views are plan [x, y, height]
## Review lamps under the attic's ridge (review only; the game's lights are #83a's): plan x, y, height over the floor.
LAMPS = [[25.0, 33.0, 3.6], [35.0, 33.0, 3.6]]
LAMP = [[1.0, 0.8, 0.55], 1.6, 9.0]
## Name, title, eye, look (plan x, y, height), fov. The hatch's hole centres at (28, 29).
VIEWS = [
    ["hatch", "attic: from the hatch (head 0.9 m over the floor)", [28.0, 29.6, F + 0.9], [36.0, 37.0, F + 1.0], 75.0],
    ["inside", "attic: inside at 1.6 m, toward the west gable", [38.5, 36.0, F + 1.6], [20.0, 30.0, F + 1.4], 75.0],
    ["spots_sw", "attic: hiding spots, the south-west corner", [27.0, 33.5, F + 1.6], [21.0, 39.0, F + 0.4], 75.0],
    ["spots_n", "attic: hiding spots, the north eave", [29.0, 33.0, F + 1.6], [23.0, 26.5, F + 0.4], 75.0],
    ["deck_high", "roof deck from the south-east, high", [50.0, 52.0, F + 9.0], [30.0, 34.0, F], 55.0],
    ["deck_door", "roof deck: out of the roof door at 1.6 m, toward the south strip", [41.5, 32.0, F + 1.6],
     [36.0, 43.5, F + 0.5], 75.0],
]
LOOKOUT_FOV = 70.0  # wide enough for both openings (the wicket due south, the gates south-east)


def shoot_request(kits: list[Path], scenes: Path = house_cmd.DEFAULT_OUT) -> tuple[dict, dict[str, Path], list[str]]:
    """The zones.gd request for the attic and the deck, the GLBs to stage and the kit pieces found nowhere."""
    data = house_layout.load()
    planned = house_layout.plan(data)
    summary = house_layout.write_scenes(data, planned, scenes)
    kit_dir = common.raw_dir() / data["settings"]["kit_dir"]
    staged: dict[str, Path] = {}
    missing = []
    for pid in summary["pieces"]:
        glb = next((k / f"{pid}.glb" for k in kits + [kit_dir] if (k / f"{pid}.glb").is_file()), None)
        if glb is None:
            missing.append(pid)
        else:
            staged[f"kit_{pid}"] = glb
    lib = _props.default_out(_props.load())
    pieces = [{"zone": "house", "id": "house", "src": "layout", "pos": [0, 0, 0], "yaw": 0.0,
               "scene": f"{data['settings']['scene_res'].rstrip('/')}/house.tscn"}]
    for name in ("attic", "roof"):
        for it in house_attic.load(name)["items"]:
            entry = {"zone": name, "id": it["id"], "src": it["src"], "pos": [it["at"][0], F, it["at"][1]],
                     "yaw": it["yaw"]}
            if it["src"] == "library":
                staged[f"prop_{it['id']}"] = lib / f"{it['id']}.glb"
                entry["scene"] = f"res://import/prop_{it['id']}.glb"
            else:
                entry["size"] = it.get("size", [0.6, 0.6, 0.6])
            pieces.append(entry)
    for sp in house_attic.load("attic").get("spots", []):  # the hiding spots as small labelled boxes at their height
        pieces.append({"zone": "spots", "id": sp["name"], "src": "spot", "yaw": 0.0, "size": [0.12, 0.12, 0.12],
                       "pos": [sp["at"][0], F + float(sp["h"]), sp["at"][1]]})
    roof = house_attic.load("roof")
    with house_attic.PLOT.open("rb") as f:
        plot = tomllib.load(f)
    post_h = float(plot["fence"].get("post_h", 1.8))
    see = roof["lookout"]["see"]
    ops = [op for op in plot["fence"]["openings"] if op["id"] in see]
    for op in ops:  # the fence openings the lookout must see, as labelled boxes (the yard is #81's)
        pieces.append({"zone": "yard", "id": op["id"], "src": "fence opening", "yaw": 0.0, "size": [op["width"], 0.2, post_h],
                       "pos": [op["centre"][0], 0.0, op["centre"][1]]})
    tx = sum(float(op["centre"][0]) for op in ops) / max(1, len(ops))
    ty = sum(float(op["centre"][1]) for op in ops) / max(1, len(ops))
    views = [list(v) for v in VIEWS]
    for k, (x, y) in enumerate(roof["lookout"]["eyes"]):
        views.append([f"lookout_{k + 1}", f"lookout at ({x:g}, {y:g}), eye 1.6 m, toward {' and '.join(see)}",
                      [x, y, F + 1.6], [tx, ty, 0.8], LOOKOUT_FOV])
    spec = json.loads(zones.KIT_SPEC.read_text(encoding="utf-8"))
    mats = [spec["materials"][m] for m in spec.get("packs", {}).get("set", {}).get("layers", [])]
    pack = {"textures": (kit_dir / "textures").as_posix(), "roughness": [m["roughness"] for m in mats],
            "normal_strength": [m["normal_strength"] for m in mats]} if len(mats) == 3 else {}
    lamps = [[x, F + h, y] for x, y, h in LAMPS]
    return {"pieces": pieces, "views": views, "pack": pack, "lamps": lamps, "lamp": LAMP}, staged, missing


def shoot(folder: Path, kits: list[Path]) -> int:
    req, staged, missing = shoot_request(kits)
    absent = sorted(p.as_posix() for p in staged.values() if not p.is_file())
    if missing or absent:
        raise common.Failure(f"missing GLBs (build the kit and the library first): {', '.join(missing + absent)}")
    return zones.render(req, staged, folder, common.OUT / "attic" / "request.json", "attic")
