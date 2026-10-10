"""`attic`: checks the attic's old things and hiding spots and the free roof's stations and lookout
(layouts/house/dressing/attic_roof/attic.toml, house_attic.py; docs/house.md, "The attic and the free roof") and writes
the report: every spot's standing point, the dormer's climb-out, the lookout's view per eye. With --shoot, it generates
the house's scenes, places the dressing (library GLBs, grey boxes for the placeholders) and shoots the attic and the
free roof at dusk in an off-screen Godot window through godot/house/zones.gd."""

from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path

from .. import common, house_attic, house_layout
from . import _props, zones
from . import house as house_cmd

NAME = "attic"
HELP = "check the attic's hiding spots and the free roof's stations and lookout (layouts/house/dressing)"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", type=Path, default=common.ROOT / "tools" / "out" / "attic" / "report.json",
                        help="where the report goes (default tools/out/attic/report.json)")
    parser.add_argument("--shoot", type=Path, metavar="DIR",
                        help="then shoot the attic and the free roof at dusk off-screen into DIR (sheet.png, frames)")
    parser.add_argument("--kit", type=Path, action="append", default=[], metavar="DIR",
                        help="a folder searched before the layout's kit_dir for kit GLBs (a piece not built there yet)")


def run(args: argparse.Namespace) -> int:
    rep = house_attic.report()
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8", newline="\n")
    spots = rep["attic"]["spots"]
    common.say(f"attic: {rep['attic']['items']} items, {sum(s['reachable'] for s in spots)}/{len(spots)} hiding "
               f"spots reachable for a pick-up")
    for c in rep["attic"]["climb"]:
        common.say(f"attic: {c['id']} from its foot {c['foot']} (reached from the hatch) up {c['top_h']:.3f} m at "
                   f"{c['slope_deg']} deg to {c['top']}, the dormer window's sill")
    for dm in rep["roof"]["dormers"]:
        w, h = dm["opening"]
        common.say(f"roof: dormer {dm['id']}: window at {dm['window']}, {w:g} x {h:g} m, its sill {dm['sill']:.2f} m over "
                   f"the attic floor, {dm['step_at_wall']:.2f} m over the roof at its front wall (the game's step "
                   f"{house_attic.STEP_H:g} m), the eave {dm['roof_top_eave']:.2f} m; {rep['roof']['walkable_m2']} m2 of "
                   f"roof walkable from it")
        if dm["open"]:
            common.say(f"roof: dormer {dm['id']}: OPEN for the engineer: {dm['open']}")
    for k, v in enumerate(rep["roof"]["lookout"]):
        see = ", ".join(f"{t} {100 * f:.0f}%" for t, f in v["see"].items())
        label = "the station" if k == 0 else "an alternative, not the acceptance"
        common.say(f"roof: lookout eye {v['eye']} at {v['eye_h']:.2f} m ({label}): {see}; house windows in view "
                   f"{len(v['house_windows'])}; attic windows {v['attic_windows'] or 'none'}; across the yard "
                   f"{v['other_windows'] or 'none'}")
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


F = 6.4  # the attic's floor (layouts/house/attic.toml); views are plan [x, y, height]


def _top(y: float) -> float:
    """The roof's top at plan y over the ground (where a player on the free roof stands)."""
    return F + house_attic.roof_top(house_layout.load(), y)


## Review lamps under the attic's ridge (review only; the game's lights are #83a's): plan x, y, height over the floor.
LAMPS = [[25.0, 34.0, 4.0], [35.0, 34.0, 4.0]]
LAMP = [[1.0, 0.8, 0.55], 1.6, 9.0]
## Name, title, eye, look (plan x, y, height), fov. The hatch's hole centres at (28, 29); the dormer's window at
## (35, 43), its sill 2.97 m over the attic floor; the ridge on y 34.
VIEWS = [
    ["hatch", "attic: from the hatch (head 0.9 m over the floor), toward the dormer", [28.0, 29.6, F + 0.9],
     [35.0, 41.0, F + 1.8], 75.0],
    ["inside", "attic: inside at 1.6 m, toward the west gable", [40.5, 36.0, F + 1.6], [18.0, 30.0, F + 1.4], 75.0],
    ["spots_sw", "attic: hiding spots, the south-west corner", [25.0, 37.5, F + 1.6], [19.0, 43.0, F + 0.4], 75.0],
    ["spots_n", "attic: hiding spots, the north eave", [27.0, 31.0, F + 1.6], [21.0, 24.5, F + 0.4], 75.0],
    ["climb_out", "attic: the climb-out, the dormer's window over its stair", [35.0, 38.0, F + 1.6],
     [35.0, 43.5, F + 3.2], 75.0],
    ["street", "the free roof from the street", [30.0, 64.0, 1.7], [30.0, 34.0, F + 3.0], 55.0],
    ["roof_high", "the free roof from the south-east, high", [54.0, 58.0, F + 10.0], [30.0, 34.0, F + 2.0], 55.0],
    ["slope", "on the south slope out of the dormer at 1.6 m, toward the lookout", [33.5, 43.4, _top(43.4) + 1.6],
     [40.0, 40.0, _top(40.0) + 1.0], 75.0],
    ["ridge", "from the ridge at 1.6 m to the yard", [30.0, 34.2, _top(34.2) + 1.6], [30.0, 56.0, 0.0], 75.0],
]
LOOKOUT_FOV = 70.0  # wide enough for both openings (the wicket due south, the gates south-east)


def shoot_request(kits: list[Path], scenes: Path = house_cmd.DEFAULT_OUT) -> tuple[dict, dict[str, Path], list[str]]:
    """The zones.gd request for the attic and the free roof, the GLBs to stage and the kit pieces found nowhere."""
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
    attic = house_attic.load("attic")
    roof = house_attic.roof_zone(attic, data)
    for name, z in (("attic", attic), ("roof", roof)):
        for it in z["items"]:
            fy = F if name == "attic" else F + house_attic.roof_top(data, it["at"][1])  # roof items on the slope's top
            entry = {"zone": name, "id": it["id"], "src": it["src"], "pos": [it["at"][0], fy, it["at"][1]],
                     "yaw": it["yaw"]}
            if it["src"] == "library":
                staged[f"prop_{it['id']}"] = lib / f"{it['id']}.glb"
                entry["scene"] = f"res://import/prop_{it['id']}.glb"
            else:
                entry["size"] = it.get("size", [0.6, 0.6, 0.6])
            pieces.append(entry)
    for sp in attic.get("spots", []):  # the hiding spots as small labelled boxes at their height
        pieces.append({"zone": "spots", "id": sp["name"], "src": "spot", "yaw": 0.0, "size": [0.12, 0.12, 0.12],
                       "pos": [sp["at"][0], F + float(sp["h"]), sp["at"][1]]})
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
                      [x, y, _top(y) + 1.6], [tx, ty, 0.8], LOOKOUT_FOV])
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
