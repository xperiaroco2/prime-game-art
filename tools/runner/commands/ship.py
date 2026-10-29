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
import math
from pathlib import Path

from .. import blender, common, ship_layout
from . import _export, _godot

NAME = "ship"
HELP = "the empty ship (layouts/ship): check the layout; --build one GLB per piece; --godot import, sizes, colliders, walk; --shoot DIR, --walk DIR, --motion DIR (the stations' moving parts); --vent-anim DIR (the vents' animation in place); --charger-cycle DIR (the east charger's cycle); --play (the engineer's walk)"
BUILD_SCRIPT = blender.SCRIPTS / "ship_build.py"
GODOT_SCRIPT = "res://ship/ship.gd"
CHARGER_SCRIPT = "res://charger/room.gd"   # --shoot --charger (lens C step 3)
BUILD_TIMEOUT = 900
GODOT_TIMEOUT = 300
VIEW_SIZE = (1920, 1080)
SIZE_TOL_M = 0.01
PLAY_DEFAULT = Path("<raw>/play")  # --play with no DIR: <raw>/<raw_dir>/play
PLAY_HOURS = 8  # the most one --play session stays open


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--check", action="store_true", help="only the layout check (the default when nothing else is asked)")
    parser.add_argument("--build", action="store_true", help="build one GLB per piece and run glTF-Validator on each")
    parser.add_argument("--only", default="", help="comma-separated piece ids to build (default every piece)")
    parser.add_argument("--out", type=Path, help="the pieces folder (default <raw>/<ship.toml raw_dir>/pieces, v2: <raw>/ship/v2/pieces)")
    parser.add_argument("--godot", action="store_true", help="headless import: sizes, colliders and the capsule walk")
    parser.add_argument("--walk", type=Path, metavar="DIR",
                        help="the capsule walk (headless) into DIR/check.json, then the eye-height walk-through video "
                             "DIR/walkthrough.mp4 (off-screen window, 1280x720)")
    parser.add_argument("--no-video", action="store_true", help="--walk without the video")
    parser.add_argument("--shoot", type=Path, metavar="DIR", help="off-screen shots at night, plan compare and sheet into DIR")
    parser.add_argument("--views", default="", metavar="FILE|PREFIXES",
                        help="--shoot only these views: a JSON file (a list of [name, title, eye [x, y, h], look [x, y, h],"
                             " fov] in plan coordinates, an optional 6th {\"ssil\"|\"ssao\"|\"glow\"|\"shadows\": false}"
                             " A/B switch or a reference image's path to compare it with) and the plan view, no day views;"
                             " or comma-separated prefixes of"
                             " ship.toml's view names (no plan view), e.g. in_vent_,cu_vent_")
    parser.add_argument("--charger", action="store_true",
                        help="--shoot with the crystal charger's GLB (assets/prop/crystal_charger) and a crystal on "
                             "renewer_e and renewer_w, for the look review only (the package keeps the spots as markers)")
    parser.add_argument("--vent-states", default="", help="--shoot with the vents in a state each, e.g. e=problem,w=calm "
                        "(calm: slats open, the cyan glow, the lamp dim; problem: slats shut, the orange heat, the lamp lit)")
    parser.add_argument("--motion", type=Path, metavar="DIR",
                        help="the stations' motion proof (step 2: the vents) off-screen: checks, MP4, sheets into DIR")
    parser.add_argument("--vent-anim", type=Path, metavar="DIR",
                        help="the east vent's animation in place at night (godot/ship/vent_anim.gd through its demo: calm, "
                             "the problem, a hold, the cough, calm) from the player's eye off-screen: MP4 and key sheet into DIR")
    parser.add_argument("--charger-cycle", type=Path, metavar="DIR",
                        help="the east crystal charger's cycle in lens room C at night (godot/charger/cycle.gd: idle, "
                             "the crystal in, the button, charging, charged, the crystal out) from the player's eye "
                             "off-screen: cycle.mp4 (1280x720, 30 fps) and keys_sheet.png into DIR")
    parser.add_argument("--export", type=Path, metavar="DIR",
                        help="the game-ready package into DIR (art #335; assets/environment/ship/, levels/ship/ship.tscn, "
                             "package.json): then its headless load, sizes and walk, and its views beside --shoot's")
    parser.add_argument("--no-compare", action="store_true", help="--export without the off-screen views and compare")
    parser.add_argument("--play", type=Path, nargs="?", const=PLAY_DEFAULT, metavar="DIR",
                        help="FOR THE ENGINEER ONLY (an on-screen window; agents never run it): walk the built ship in "
                             "first person at night; P saves a screenshot and its position into DIR "
                             "(default <raw>/<raw_dir>/play)")
    parser.add_argument("--play-test", type=Path, metavar="DIR",
                        help="the --play scene off-screen: the capsule walks 2 s, saves one shot and DIR/play.json")
    parser.set_defaults(_ship_parser=parser)   # lens C step 4: run() refuses --charger without --shoot as a usage error


def raw(layout: dict) -> Path:
    return common.raw_dir() / layout["raw_dir"]


def run(args: argparse.Namespace) -> int:
    if getattr(args, "charger", False) and not args.shoot:
        args._ship_parser.error("--charger only works with --shoot DIR (the look review's chargers and crystals)")
    layout = ship_layout.load()
    problems = ship_layout.check(layout)
    width, length = ship_layout.extent(layout)
    lens = ship_layout.lengths(layout)
    common.say(f"ship v{layout['version']}: {width:.2f} x {length:.2f} m (with the nozzles), {len(layout['rooms'])} rooms, "
               f"{len(layout['pieces'])} pieces, {len(layout['place'])} placements; length with the nozzles "
               f"{lens['nozzles']:.2f} m, ramp foot to nozzle tips {lens['overall']:.2f} m")
    skins = ship_layout.room_skin(layout)
    if skins:
        common.say("  least skin: " + ", ".join(f"{r} {s:.3f} ({w})" for r, (s, w) in skins.items()))
    for p in problems:
        common.say(f"  {p}")
    if problems:
        raise common.Failure(f"ship: {len(problems)} layout problems")
    plan = raw(layout) / "plan" / "plan.txt"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(ship_layout.ascii_plan(layout), encoding="utf-8", newline="\n")
    held = "footprint, corridors, stations, hull, skin, head room and the one entrance"
    common.ok(f"ship: {held} hold; plan {plan.as_posix()}")
    out = (args.out or raw(layout) / "pieces").resolve()
    # Each stage stops the run on a failure: a later stage would work on pieces just reported bad.
    if args.build:
        code = build(layout, out, [s for s in args.only.split(",") if s])
        if code:
            return code
    if args.godot or args.walk:
        code = godot_check(layout, out, args.walk.resolve() if args.walk else common.OUT / "ship" / "godot")
        if code:
            return code
    if args.walk and not args.no_video:
        code = walk_video(layout, out, args.walk.resolve())
        if code:
            return code
    if args.motion:
        code = motion(layout, out, args.motion.resolve())
        if code:
            return code
    if args.vent_anim:
        code = vent_anim(layout, out, args.vent_anim.resolve())
        if code:
            return code
    if args.charger_cycle:
        code = charger_cycle(layout, out, args.charger_cycle.resolve())
        if code:
            return code
    if args.shoot:
        code = shoot(layout, out, args.shoot.resolve(), args.views, args.vent_states, args.charger)
        if code:
            return code
    if args.export:
        code = export(layout, out, args.export.resolve(), not args.no_compare)
        if code:
            return code
    if args.play_test:
        return play(layout, out, args.play_test.resolve(), test=True)
    if args.play:
        folder = raw(layout) / "play" if args.play == PLAY_DEFAULT else args.play.resolve()
        return play(layout, out, folder, test=False)
    return 0


# --- build ---------------------------------------------------------------------------------------------------------
def build(layout: dict, out: Path, only: list[str]) -> int:
    unknown = set(only) - {p["id"] for p in layout["pieces"]}
    if unknown:
        raise common.Failure(f"no piece {', '.join(sorted(unknown))}")
    out.mkdir(parents=True, exist_ok=True)
    request = common.OUT / "ship" / "build_request.json"
    request.parent.mkdir(parents=True, exist_ok=True)
    request.write_text(json.dumps({"layout": layout, "only": only}, indent=1), encoding="utf-8", newline="\n")
    old = _old_report(out) if only else {}
    blender.run_script(BUILD_SCRIPT, ["--request", str(request), "--out", str(out)], timeout=BUILD_TIMEOUT)
    report = json.loads((out / "build_report.json").read_text(encoding="utf-8"))
    _keep_others(out, report, old)
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


def _old_report(out: Path) -> dict:
    path = out / "build_report.json"
    return json.loads(path.read_text(encoding="utf-8"))["pieces"] if path.is_file() else {}


def _keep_others(out: Path, report: dict, old: dict) -> None:
    """An --only build keeps the other pieces' entries of the previous report (the lanes build their own pieces)."""
    merged = {**{k: v for k, v in old.items() if Path(v["glb"]).is_file()}, **report["pieces"]}
    (out / "build_report.json").write_text(json.dumps({"pieces": merged}, indent=1), encoding="utf-8", newline="\n")


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
    path.parent.mkdir(parents=True, exist_ok=True)
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


# The whole ship from straight above: the ramp's foot (y -12.6 since the raise) to the nozzles (15.0) and both lenses
# (+-13.1) in a 29.5 m high frame (1920x1080: 52 m wide), centred between them; south up as `top`.
TOP_FULL = {"name": "top_full", "title": "top: the whole ship from straight above, at night", "size_m": 29.5,
            "centre": [0.0, 1.2, 0.0], "day_name": "top_full_day",
            "day_title": "top: the whole ship from straight above, by day"}


def shot_views(layout: dict) -> tuple[list, list]:
    """The review views: the exterior lane's (exterior.toml [shots], each with its 2D sheet) replace ship.toml's of the
    same name; ship.toml's others follow. Returns (views [name, title, eye, look, fov] in plan coordinates, compares
    [name, reference image])."""
    import tomllib
    with (common.ROOT / layout["exterior"]).open("rb") as f:
        ext = tomllib.load(f).get("shots", {})
    mine = {v[0]: v for v in ext.get("views", [])}
    # rebuild A: the inside lane's "in_" views in ship.toml win over the exterior's of the same name (the rooms moved;
    # the exterior's reference image for the compare stays)
    inner = {v[0]: v for v in layout["shots"]["views"] if v[0].startswith("in_")}
    mine = {k: (inner[k][:5] + list(v[5:]) if k in inner else v) for k, v in mine.items()}
    views = list(mine.values()) + [v for v in layout["shots"]["views"] if v[0] not in mine]
    compares = [[v[0], f"{ext['ref_dir'].rstrip('/')}/{v[5]}"] for v in mine.values() if len(v) > 5]
    return [v[:5] for v in views], compares


def room_boxes(layout: dict) -> list:
    """A reflection probe box per room: [id, centre (Godot), size (Godot), interior]: every room an interior probe
    (ship.toml probe_intensity, 0.15, the tip rooms too, as in the step C shots) but the exit room, the throat open to
    the sky (1.0)."""
    deck = layout["deck"]
    out = []
    for r in layout["rooms"]:
        if r["shape"] == "circle":
            cx, cy, sx, sy = r["centre"][0], r["centre"][1], 2 * r["radius"], 2 * r["radius"]
        elif r["shape"] == "strip":   # rebuild A: a diagonal corridor's probe is its plan's bounding box
            _o, _u, u0, u1, half = ship_layout.strip_frame(r)
            pts = [ship_layout.strip_point(r, u, v) for u in (u0, u1) for v in (-half, half)]
            xs, ys = [q[0] for q in pts], [q[1] for q in pts]
            cx, cy, sx, sy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, max(xs) - min(xs), max(ys) - min(ys)
        elif r["shape"] == "poly":   # rebuild C: the throat's probe is its plan's bounding box
            xs, ys = [q[0] for q in r["points"]], [q[1] for q in r["points"]]
            cx, cy, sx, sy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, max(xs) - min(xs), max(ys) - min(ys)
        else:
            cx, cy = sum(r["x"]) / 2, sum(r["y"]) / 2
            sx, sy = r["x"][1] - r["x"][0], r["y"][1] - r["y"][0]
        hh = r.get("apex_h", r["clear_h"])
        out.append([r["id"], _g([cx, cy, deck["floor_h"] + hh / 2]), [sx + 0.4, hh + 0.2, sy + 0.4],
                    not r.get("exit")])
    return out


def built_request(layout: dict, out: Path) -> tuple[dict, dict[str, Path]]:
    """The scene part of a shoot or walk request from the pieces whose GLBs exist (the current whole while a lane
    is mid-change); says which placed pieces are missing."""
    ids = [p["id"] for p in layout["pieces"] if (out / f"{p['id']}.glb").is_file()]
    missing = sorted({p["id"] for p in layout["pieces"]} - set(ids))
    if missing:
        common.say(f"  not built, left out: {', '.join(missing)}")
    req = {"pieces": {pid: f"res://import/ship_{pid}.glb" for pid in ids},
           "collide": [p["id"] for p in layout["pieces"] if p["collide"] and p["id"] in ids],
           "place": [[pid, _g(at), yaw] for pid, at, yaw in layout["place"] if pid in ids],
           # inside-2: the outside pieces draw on render layer 2, out of reach of the inside's strip lights
           # (an exterior piece with layer = "inside", the tunnel's inside, draws with the inside's)
           "outside": [p["id"] for p in layout["pieces"]
                       if p["lane"] != "interior" and p.get("layer") != "inside" and p["id"] in ids]}
    return req, {f"ship_{pid}": out / f"{pid}.glb" for pid in ids}


# vents-b2: each glow panel carries its well lights (godot/ship/vent_glow.gd): calm hides the heat, the problem the cool.
# vents-b3: "dark" turns a surface's glow off and its colour to dark bronze, as vent_anim.gd does the seams calm (b2's
# "dim" kept their orange colour: the seams read lit in the calm shots)
VENT_STATES = {"calm": {"slats": 1.0, "show": [], "hide": ["heat"], "dim": ["lamp"], "dark": ["slat*:__vent_seam"]},
               "problem": {"slats": 0.0, "show": ["heat"], "hide": ["cool"], "dim": [], "dark": []}}



def vent_states(spec: str) -> dict:
    """--vent-states "e=problem,w=calm" as ship.gd's "stations" request: {piece: {"slats", "show", "hide", "dim"}}."""
    states = {}
    for item in (i for i in spec.split(",") if i):
        side, _, state = item.partition("=")
        if side not in ("e", "w") or state not in VENT_STATES:
            raise common.Failure(f"ship --vent-states: {item!r}, wants e=<state> or w=<state>, states {sorted(VENT_STATES)}")
        states[f"station_vent_{side}"] = VENT_STATES[state]
    return states


CHARGER_GLB = common.ROOT / "assets" / "prop" / "crystal_charger" / "export" / "crystal_charger.glb"
CRYSTAL_GLB = common.ROOT / "assets" / "prop" / "energy_crystal" / "export" / "energy_crystal.glb"


def charger_places(layout: dict) -> list:
    """Lens room C's look review (art#263): the charger on each renewer spot (its origin on the spot's vertex at the
    deck, its front along the spot's normal: the charger's HANDOFF) and a crystal on its anchor (the axis 38 cm out,
    the tip at 95.1 cm). Only --shoot --charger places them; the package keeps the spots as markers."""
    floor, out = layout["deck"]["floor_h"], []
    for spot in layout["stations"]["spot"]:
        if spot["id"] not in ("renewer_e", "renewer_w"):
            continue
        (x, y), (nx, ny) = spot["at"], spot["normal"]
        yaw = math.degrees(math.atan2(nx, ny))
        out.append(["crystal_charger", [round(x, 4), floor, round(y, 4)], round(yaw, 3)])
        out.append(["energy_crystal", [round(x + nx * 0.38, 4), round(floor + 0.951, 4), round(y + ny * 0.38, 4)],
                    round(yaw, 3)])
    return out


CHARGER_STATE = {"charger": "idle", "crystal": True, "charge": 0.0}   # the game's default: idle, a spent crystal seated


def charger_rows(views: list) -> list:
    """--shoot --charger's views (lens C step 3): every row's 6th element becomes charger/room.gd's state, the game's
    default (CHARGER_STATE: the charger idle, the crystal seated and spent; a full one's light floods the lens room
    cyan) under the row's own keys."""
    for v in views:
        off = v[5] if len(v) > 5 else {}
        v[5:6] = [{**CHARGER_STATE, **off}]
    return views


def shoot_script(charger: bool) -> str:
    """The shoot's Godot script: charger/room.gd (ship.gd plus the charger's and the crystal's game looks) for
    --charger, else ship.gd."""
    return CHARGER_SCRIPT if charger else GODOT_SCRIPT


def shoot(layout: dict, out: Path, folder: Path, only: str = "", states: str = "", charger: bool = False) -> int:
    req, staged = built_request(layout, out)
    if charger:
        req["pieces"].update({"crystal_charger": "res://import/crystal_charger.glb",
                              "energy_crystal": "res://import/energy_crystal.glb"})
        staged.update({"crystal_charger": CHARGER_GLB, "energy_crystal": CRYSTAL_GLB})
        req["place"] += charger_places(layout)
    if states:   # step 3: the vents calm or in their problem state, as the game drives them
        import importlib
        import sys
        sys.path.insert(0, str(blender.SCRIPTS))
        req.update({"stations": vent_states(states), "open_rad": importlib.import_module("ship_interior_vent").OPEN_RAD})
    views, compares = shot_views(layout)
    prefixes: tuple = ()
    if only and (only.endswith(".json") or Path(only).is_file()):   # the raise (2026-10-23): a review's own views
        views = json.loads(Path(only).read_text(encoding="utf-8"))
        # lens C step 2: a row whose 6th element is a string names a reference image (an absolute path) to compare
        # the shot with side by side (an A/B dict there stays the night look's switch)
        compares = [[v[0], v[5]] for v in views if len(v) > 5 and isinstance(v[5], str)]
        views = [v[:5] if len(v) > 5 and isinstance(v[5], str) else v for v in views]
        layout = {**layout, "shots": {**layout["shots"], "day_views": []}}
    elif only:   # step 2: a view set alone by name prefix (the vents' in-place shots and close-ups), no plan view
        prefixes = tuple(p for p in only.split(",") if p)
        views = [v for v in views if v[0].startswith(prefixes)]
        if not views:
            raise common.Failure(f"ship --shoot --views {only}: no view matches")
    req.update({"mode": "shoot", "light": {**layout["light"], "lamps": [[*_g(l[:3]), *l[3:]] for l in layout["light"]["lamps"]]},
                # fix 2: a --views row's optional 6th element switches the night look's parts off for that shot
                # (an A/B: {"ssil": false, "ssao": false, "glow": false, "shadows": false}, "mats": {name: {"roughness":
                # r, "metallic": m, "specular": s}} for a glTF material; ship.gd _ab)
                "views": [[v[0], v[1], _g(v[2]), _g(v[3]), v[4], *v[5:6]] for v in views],
                # details 1: views by day, after the night's (ship.toml [shots] day_views)
                "day_views": [[v[0], v[1], _g(v[2]), _g(v[3]), v[4]] for v in layout["shots"].get("day_views", [])],
                "top": {"name": "top", "title": "top: plan view, south up (as plan-3)", "size_m": 36.0},
                # light layer: the whole ship from straight above (the top view crops the stern and the pods), at night
                # and by day; shots show the nav lamps' static glow (nav_blink off; on in game)
                "top_full": {**TOP_FULL, "centre": _g(TOP_FULL["centre"])}, "nav_blink": False,
                "compare": [["top", layout["plan_ref"]], *compares], "rooms": room_boxes(layout)})
    if prefixes:
        for key in ("top", "top_full", "day_views"):
            req.pop(key)
        req["compare"] = []
    # lens C step 3: --charger runs charger/room.gd instead of the GLBs' plain materials, which ship.gd's pass made
    # strip lights of
    script = shoot_script(charger)
    if charger:
        charger_rows(req["views"])
    errors = _stage(staged)
    folder.mkdir(parents=True, exist_ok=True)
    path = common.OUT / "ship" / "shoot_request.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
    (folder / "shots.json").unlink(missing_ok=True)
    code, output = _godot.window(["--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s", script, "--",
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


# --- the game's package (art #335) ----------------------------------------------------------------------------------
def export(layout: dict, out: Path, folder: Path, compare: bool = True) -> int:
    """`--export DIR`: the scene (godot/ship/export_scene.gd), the package (ship_export.write), its headless check and,
    unless compare is off, the views beside --shoot's; <DIR>/_check/report.json (outside the package's files)."""
    from .. import ship_export
    from . import _ship_export
    req, staged = built_request(layout, out)
    missing = sorted({p["id"] for p in layout["pieces"]} - set(req["pieces"]))
    if missing:
        raise common.Failure(f"ship --export: pieces not built (ship --build): {', '.join(missing)}")
    req.update({"light": {**layout["light"], "lamps": [[*_g(l[:3]), *l[3:]] for l in layout["light"]["lamps"]]},
                "rooms": room_boxes(layout)})
    folder.mkdir(parents=True, exist_ok=True)
    built = _ship_export.scene(layout, out, req, staged, folder)
    try:
        summary = ship_export.write(layout, out, built, common.ROOT / "godot", folder)
    except ValueError as e:
        raise common.Failure(f"ship --export: {e}") from e
    common.say(f"  package: {len(summary['files'])} files, {summary['bytes'] / 1e6:.1f} MB -> {folder.as_posix()}")
    problems, load = _ship_export.check(layout, out, folder)
    shots: dict = {}
    if compare:
        more, shots = _ship_export.compare(layout, out, folder)
        problems += more
    report = {"package": {k: summary[k] for k in ("version", "scene", "pieces", "placements", "bytes")},
              "files": len(summary["files"]), "stations": len(summary["stations"]),
              "load": {k: load[k] for k in ("pieces", "bodies", "lights", "size_worst_m", "walk")}, "views": shots,
              "problems": problems}
    path = folder / _ship_export.CHECK_DIR / "report.json"
    path.write_text(json.dumps(report, indent=1), encoding="utf-8", newline="\n")
    for p in problems:
        common.say(f"  {p}")
    if problems:
        common.bad(f"ship --export: {len(problems)} problems")
        return 1
    common.ok(f"ship --export: the package loads headless, sizes and walk hold"
              + (", the views match --shoot's" if compare else "") + f" ({folder.as_posix()})")
    return 0


# --- the engineer's walk --------------------------------------------------------------------------------------------
def play(layout: dict, out: Path, folder: Path, test: bool) -> int:
    """The built ship at night in first person (godot/ship/player.gd), from the ramp's foot. For the engineer: a
    normal window on the screen (CLAUDE.md keeps Godot windows off the screen for agents; this one is his, and an
    agent only runs the test). test: the same scene off-screen through _godot.window(); the capsule walks forward 2 s,
    saves one shot and play.json."""
    req, staged = built_request(layout, out)
    walk = walk_request(layout)
    req.update({"mode": "play", "test": test, "walk": walk, "spawn": walk["points"][0], "spawn_yaw": 180.0,
                "light": {**layout["light"], "lamps": [[*_g(l[:3]), *l[3:]] for l in layout["light"]["lamps"]]},
                "rooms": room_boxes(layout)})
    errors = _stage(staged)
    if errors:
        common.bad(f"ship --play: {len(errors)} import errors")
        return 1
    folder.mkdir(parents=True, exist_ok=True)
    path = common.OUT / "ship" / "play_request.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
    args = ["--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s", GODOT_SCRIPT, "--", path.as_posix(),
            folder.as_posix()]
    if test:
        (folder / "play.json").unlink(missing_ok=True)
        code, output = _godot.window(args, VIEW_SIZE, GODOT_TIMEOUT)
        if code != 0 or not (folder / "play.json").is_file():
            raise common.Failure(f"ship.gd play test failed (exit code {code}):\n" + "\n".join(output.splitlines()[-20:]))
        result = json.loads((folder / "play.json").read_text(encoding="utf-8"))
        if result["moved_m"] < 1.0 or not result["on_floor"] or result["shots"] != 1:
            common.bad(f"ship --play-test: {result}")
            return 1
        common.ok(f"ship --play-test: walked {result['moved_m']} m on the floor, one shot in {folder.as_posix()}")
        return 0
    common.say(f"ship --play: a window opens; P saves a screenshot into {folder.as_posix()}, Ctrl+Q or closing it quits")
    # ship.gd's _play sizes and centres his window itself. heavy=False: it may stay open for hours, so it does not hold
    # the heavy-run lock (the import above took it)
    result = common.run([common.godot_bin(), *args], PLAY_HOURS * 3600, heavy=False)
    code = result.returncode
    if code != 0:
        common.say("\n".join(((result.stdout or "") + (result.stderr or "")).splitlines()[-20:]))
    shots = sorted(folder.glob("shot_*.png"))
    common.say(f"ship --play: closed (exit code {code}); {len(shots)} screenshots in {folder.as_posix()}")
    return 0 if code == 0 else 1


# --- the walk-through video (the exterior lane) --------------------------------------------------------------------
VIDEO_SCRIPT = "ship_video.py"
VIDEO_TIMEOUT = 1500


def video_request(layout: dict) -> dict:
    """exterior.toml's [video] in Godot coordinates: size, fps, fov, keys [[eye, look, seconds]], max_mb."""
    import tomllib
    with (common.ROOT / layout["exterior"]).open("rb") as f:
        v = tomllib.load(f)["video"]
    return {"size": v["size"], "fps": v["fps"], "fov": v["fov"], "max_mb": v["max_mb"],
            "keys": [[_g(eye), _g(look), float(sec)] for eye, look, sec in v["keys"]]}


def walk_video(layout: dict, out: Path, folder: Path) -> int:
    """The eye-height walk-through: Godot renders every frame in the off-screen window (ship.gd mode "video"), headless
    Blender encodes them (ship_video.py, under max_mb), and the frames are deleted."""
    import shutil
    video = video_request(layout)
    req, staged = built_request(layout, out)
    req.update({"mode": "video", "video": video, "watchdog_s": VIDEO_TIMEOUT - 60, "nav_blink": False,
                "light": {**layout["light"], "lamps": [[*_g(l[:3]), *l[3:]] for l in layout["light"]["lamps"]]},
                "rooms": room_boxes(layout)})
    errors = _stage(staged)
    work = folder / "video"
    shutil.rmtree(work / "frames", ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)
    path = common.OUT / "ship" / "video_request.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
    code, output = _godot.window(["--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s", GODOT_SCRIPT, "--",
                                  path.as_posix(), work.as_posix()], tuple(video["size"]), VIDEO_TIMEOUT)
    if code != 0 or not (work / "video.json").is_file():
        raise common.Failure(f"ship.gd video failed (exit code {code}):\n" + "\n".join(output.splitlines()[-20:]))
    info = json.loads((work / "video.json").read_text(encoding="utf-8"))
    clip = folder / "walkthrough.mp4"
    clip.unlink(missing_ok=True)
    blender.run_script(VIDEO_SCRIPT, ["--frames", str(work / "frames"), "--out", str(clip), "--fps", str(video["fps"]),
                                      "--max-mb", str(video["max_mb"])], timeout=VIDEO_TIMEOUT)
    if not clip.is_file():
        raise common.Failure(f"{VIDEO_SCRIPT} wrote no {clip}")
    shutil.rmtree(work / "frames", ignore_errors=True)
    mb = clip.stat().st_size / 2 ** 20
    if errors or mb > video["max_mb"]:
        common.bad(f"ship --walk: video {mb:.1f} MB (max {video['max_mb']}), {len(errors)} import errors")
        return 1
    common.ok(f"ship --walk: {clip.as_posix()} {video['size'][0]}x{video['size'][1]}, {info['seconds']:.1f} s, "
              f"{info['frames']} frames, {mb:.1f} MB (rendered in {info['render_s']:.0f} s)")
    return 0


# --- step 2: the stations' motion proof ----------------------------------------------------------------------------
MOTION_SCRIPT = "res://ship/vent_motion.gd"
MOTION_TIMEOUT = 900
MOTION = {"size": (1280, 720), "fps": 24, "seconds": 22.0, "max_mb": 15}   # vents-anim1: vent_anim.gd's demo, 22 s


def motion_request(layout: dict) -> dict:
    """The vents' numbers for ship/vent_motion.gd from their builder (tools/blender/ship_interior_vent.py), in the
    piece's Godot frame (x along the wall, y up, z out of it): the opening the slats keep to, the glass the marker
    keeps to, the close-ups' cameras."""
    import importlib
    import sys
    sys.path.insert(0, str(blender.SCRIPTS))
    v = importlib.import_module("ship_interior_vent")
    f = v.FLOOR + float(layout["deck"].get("lift_m", 0.0))   # the raise: the built GLBs stand lifted (ship_build.lifted)
    vents = {}
    r = v.RECESS   # vents-b4: the piece's parts stand RECESS behind the wall's face (ship_interior_vent.station_vent)
    for pid, s in (("station_vent_e", 1.0), ("station_vent_w", -1.0)):
        # way A: the blades keep between the cap rows (their ends sit in the caps), in front of the well's glow
        u = sorted((s * v.CAP_U[0], s * v.CAP_U[1]))
        g = sorted((s * v.GLASS_U[0], s * v.GLASS_U[1]))
        # vents-b5c: the blades stay inside the opening in every plane and behind the frame's face (+5 mm)
        vents[pid] = {"opening": {"u0": u[0], "u1": u[1], "h0": f + v.OPEN_H[0], "h1": f + v.OPEN_H[1],
                                  "v_back": v.COOL_V + 0.002 - r,
                                  # v_max: the unit's depth (the body's check); v_front: the frame's face plus
                                  # 5 mm, the plane no blade vertex may pass (vents-b5c; b5 left it at v_max)
                                  "v_max": v.UNIT[3], "v_front": v.BOX_FACE - r + 0.005},
                      "glass": {"u0": g[0], "u1": g[1], "h0": f + v.GLASS_H[0], "h1": f + v.GLASS_H[1]},
                      # each blade's pivot on the caps' axis (Godot x, y, z)
                      "pivots": [[s * (v.CAP_U[0] + v.CAP_U[1]) / 2, f + v.PIVOT_TOP - k * v.PITCH, v.PIVOT_V - r]
                                 for k in range(v.SLATS)]}
    # way B (vents-b1): re-aimed on the built body (four of way A's framed empty air)
    # vents-b4: the looks RECESS back, the column's top and the scanner COL_DROP down; vents-b5: the box's right side
    # BOX_DU along, the blades' ends on their hinge line, the opening's floor lower, the scanner and lamp SCAN_U, LAMP_U
    d, du = v.COL_DROP, v.BOX_DU
    cu = [["frame_corner_tl", [-0.30, f + 1.62, 1.05], [-0.64, f + 1.40, 0.41 - r]],
          ["opening_corner_br", [0.5 + du, f + 0.35, 1.0], [0.2 + du, f + 0.28, 0.40 - r]],
          ["slat_ends_l", [-0.3 + du, f + 1.3, 0.9], [-0.50 + du, f + 1.13, v.PIVOT_V + 0.08 - r]],
          ["box_column_top", [0.85, f + 1.85 - d, 1.0], [0.47 + du, f + 1.56 - d, 0.36 - r]],
          ["lamp_base", [0.95, f + 1.95 - d, 0.85], [v.LAMP_U, f + 1.77 - d, 0.335 - r]],
          ["scanner", [0.72, f + v.SCAN_H + 0.02, 0.85], [v.SCAN_U, f + v.SCAN_H, 0.43 - r]],
          ["box_floor_l", [-1.2, f + 0.35, 1.0], [-0.70, f + 0.10, 0.40 - r]],
          ["box_wall_top", [-0.2, f + 1.95, 0.95], [-0.2, f + 1.58, 0.15 - r]],
          ["column_wall_r", [1.4, f + 0.5, 0.8], [0.78, f + 0.3, 0.2 - r]]]
    return {"ids": list(vents), "vents": vents, "slats": v.SLATS, "open_rad": v.OPEN_RAD, "mark_travel": v.MARK_TRAVEL, "gap_m": 3.0,
            "nose_r": v.NOSE_R, "min_tip_swing": 0.04,
            "fps": MOTION["fps"], "seconds": MOTION["seconds"], "closeups": cu, "watchdog_s": MOTION_TIMEOUT - 60,
            "wall": {"floor": f, "bend": v.BEND, "in": v.IN, "top": v.TOP}}


# vents-anim1: the east vent from about 3 m across the throat at the player's eye (deck 1.2 + 1.6), plan (x, y, h)
VENT_ANIM = {"piece": "station_vent_e", "eye": [-0.25, -3.05, 2.8], "look": [2.108, -4.745, 2.12], "fov": 50.0,
             "size": (1280, 720), "fps": 24, "max_mb": 15}


def vent_anim(layout: dict, out: Path, folder: Path) -> int:
    """The vent's animation in place (art #263, vents-anim1): ship.gd mode "vent_anim" renders the controller's demo
    on the whole ship at night in the off-screen window, the key moments labelled into keys_sheet.png; headless
    Blender encodes the MP4 (ship_video.py, under max_mb); the frames are deleted."""
    import importlib
    import shutil
    import sys
    sys.path.insert(0, str(blender.SCRIPTS))
    v = importlib.import_module("ship_interior_vent")
    req, staged = built_request(layout, out)
    a = VENT_ANIM
    req.update({"mode": "vent_anim", "watchdog_s": VIDEO_TIMEOUT - 60, "nav_blink": False,
                "anim": {"piece": a["piece"], "eye": _g(a["eye"]), "look": _g(a["look"]), "fov": a["fov"], "fps": a["fps"],
                         "mark_travel": v.MARK_TRAVEL},
                "light": {**layout["light"], "lamps": [[*_g(l[:3]), *l[3:]] for l in layout["light"]["lamps"]]},
                "rooms": room_boxes(layout)})
    errors = _stage(staged)
    shutil.rmtree(folder / "frames", ignore_errors=True)
    folder.mkdir(parents=True, exist_ok=True)
    path = common.OUT / "ship" / "vent_anim_request.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
    (folder / "anim.json").unlink(missing_ok=True)
    code, output = _godot.window(["--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s", GODOT_SCRIPT, "--",
                                  path.as_posix(), folder.as_posix()], a["size"], VIDEO_TIMEOUT)
    if code != 0 or not (folder / "anim.json").is_file():
        raise common.Failure(f"ship.gd vent_anim failed (exit code {code}):\n" + "\n".join(output.splitlines()[-20:]))
    info = json.loads((folder / "anim.json").read_text(encoding="utf-8"))
    clip = folder / "vent_anim.mp4"
    clip.unlink(missing_ok=True)
    blender.run_script(VIDEO_SCRIPT, ["--frames", str(folder / "frames"), "--out", str(clip), "--fps", str(a["fps"]),
                                      "--max-mb", str(a["max_mb"])], timeout=VIDEO_TIMEOUT)
    if not clip.is_file():
        raise common.Failure(f"{VIDEO_SCRIPT} wrote no {clip}")
    shutil.rmtree(folder / "frames", ignore_errors=True)
    mb = clip.stat().st_size / 2 ** 20
    if errors or mb > a["max_mb"]:
        common.bad(f"ship --vent-anim: video {mb:.1f} MB (max {a['max_mb']}), {len(errors)} import errors")
        return 1
    common.ok(f"ship --vent-anim: {clip.as_posix()} {a['size'][0]}x{a['size'][1]}, {info['seconds']:.1f} s, "
              f"{info['frames']} frames, {mb:.1f} MB; states {info['states']}; sheet {(folder / 'keys_sheet.png').as_posix()}")
    return 0


# The charger's cycle (art #263, lens room C): the east charger from the player's eye (deck + 1.6 m), 1.5 m in front
# of its front (its reach 0.70 + 1.5 out of the spot's vertex), looking at its axis's middle; fov wide enough for the
# whole charger and the alcove round it (h 0..2 m)
CHARGER_CYCLE = {"spot": "renewer_e", "eye_d": 2.2, "eye_h": 1.6, "look_d": 0.3, "look_h": 0.98, "fov": 60.0,
                 "size": (1280, 720), "fps": 30, "max_mb": 15,
                 # zap-4: the engineer's close camera, about 1.0 m from the crystal (its axis 0.38 m out of the
                 # spot's vertex, the charger's front at depth_m 0.7), at a player's eye, looking at the crystal
                 "close": {"eye_d": 1.4, "eye_h": 1.5, "look_d": 0.38, "look_h": 1.05}}
CYCLE_SCRIPT = "res://charger/cycle.gd"


def cycle_view(layout: dict, close: bool = False) -> tuple[list[float], list[float]]:
    """The cycle camera's eye and look point, plan (x, y, h), from the spot's vertex along its normal; `close`: the
    close camera's (CHARGER_CYCLE["close"])."""
    c = CHARGER_CYCLE["close"] if close else CHARGER_CYCLE
    spot = next(s for s in layout["stations"]["spot"] if s["id"] == CHARGER_CYCLE["spot"])
    (x, y), (nx, ny) = spot["at"], spot["normal"]
    floor = layout["deck"]["floor_h"]
    return ([round(x + nx * c["eye_d"], 4), round(y + ny * c["eye_d"], 4), round(floor + c["eye_h"], 4)],
            [round(x + nx * c["look_d"], 4), round(y + ny * c["look_d"], 4), round(floor + c["look_h"], 4)])


def charger_cycle(layout: dict, out: Path, folder: Path) -> int:
    """One full cycle of the east charger at night (charger/cycle.gd in ship.gd's off-screen "shoot" mode): the
    chargers on both spots, a crystal only for the east one; one PNG per frame, the beats' key moments labelled into
    keys_sheet.png; headless Blender encodes cycle.mp4 (ship_video.py, under max_mb); the frames are deleted."""
    import shutil
    req, staged = built_request(layout, out)
    req["pieces"].update({"crystal_charger": "res://import/crystal_charger.glb",
                          "energy_crystal": "res://import/energy_crystal.glb"})
    staged.update({"crystal_charger": CHARGER_GLB, "energy_crystal": CRYSTAL_GLB})
    # both chargers, and a crystal only on the east one (plan x > 0)
    req["place"] += [p for p in charger_places(layout) if p[0] == "crystal_charger" or p[1][0] > 0]
    c = CHARGER_CYCLE
    eye, look = cycle_view(layout)
    near_eye, near_look = cycle_view(layout, close=True)
    req.update({"mode": "shoot", "watchdog_s": VIDEO_TIMEOUT - 60, "nav_blink": False,
                "cycle": {"eye": _g(eye), "look": _g(look), "fov": c["fov"], "fps": c["fps"],
                          "close": {"eye": _g(near_eye), "look": _g(near_look)}},
                "light": {**layout["light"], "lamps": [[*_g(l[:3]), *l[3:]] for l in layout["light"]["lamps"]]},
                "rooms": room_boxes(layout)})
    errors = _stage(staged)
    shutil.rmtree(folder / "frames", ignore_errors=True)
    shutil.rmtree(folder / "keys", ignore_errors=True)
    shutil.rmtree(folder / "close", ignore_errors=True)
    folder.mkdir(parents=True, exist_ok=True)
    path = common.OUT / "ship" / "charger_cycle_request.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
    (folder / "cycle.json").unlink(missing_ok=True)
    code, output = _godot.window(["--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s", CYCLE_SCRIPT, "--",
                                  path.as_posix(), folder.as_posix()], c["size"], VIDEO_TIMEOUT)
    if code != 0 or not (folder / "cycle.json").is_file():
        raise common.Failure(f"charger/cycle.gd failed (exit code {code}):\n" + "\n".join(output.splitlines()[-20:]))
    info = json.loads((folder / "cycle.json").read_text(encoding="utf-8"))
    if info.get("arc_ends_off"):  # cycle.gd _check_ends: frames whose arcs landed off the crystal
        common.bad(f"ship --charger-cycle: {info['arc_ends_off']} of {info.get('arc_frames', 0)} arc frames "
                   "with an arc end off its electrode or the crystal")
        return 1
    sizes = {}
    for frames, clip in ((folder / "frames", folder / "cycle.mp4"), (folder / "close" / "frames",
                                                                     folder / "close" / "cycle.mp4")):
        clip.unlink(missing_ok=True)
        blender.run_script(VIDEO_SCRIPT, ["--frames", str(frames), "--out", str(clip), "--fps", str(c["fps"]),
                                          "--max-mb", str(c["max_mb"])], timeout=VIDEO_TIMEOUT)
        if not clip.is_file():
            raise common.Failure(f"{VIDEO_SCRIPT} wrote no {clip}")
        shutil.rmtree(frames, ignore_errors=True)
        sizes[clip] = clip.stat().st_size / 2 ** 20
    if errors or max(sizes.values()) > c["max_mb"]:
        common.bad(f"ship --charger-cycle: videos {', '.join(f'{mb:.1f}' for mb in sizes.values())} MB "
                   f"(max {c['max_mb']}), {len(errors)} import errors")
        return 1
    for clip, mb in sizes.items():
        common.ok(f"ship --charger-cycle: {clip.as_posix()} {c['size'][0]}x{c['size'][1]}, {info['seconds']:.1f} s, "
                  f"{info['frames']} frames, {mb:.1f} MB")
    common.ok(f"ship --charger-cycle: states {info['states']}; sheets {(folder / 'keys_sheet.png').as_posix()}, "
              f"{(folder / 'close' / 'keys_sheet.png').as_posix()}, {(folder / 'zoom_sheet.png').as_posix()}")
    return 0


def motion(layout: dict, out: Path, folder: Path) -> int:
    """The vents' motion proof on the exported GLBs (art #263 step 2): ship/vent_motion.gd in the off-screen window
    checks the leaves by their names and numbers and renders the frames, sheets and shots; headless Blender encodes
    the MP4 (ship_video.py, under max_mb)."""
    import shutil
    ids = ["station_vent_e", "station_vent_w"]
    missing = [pid for pid in ids if not (out / f"{pid}.glb").is_file()]
    if missing:
        raise common.Failure(f"ship --motion: build {', '.join(missing)} first (--build --only)")
    errors = _stage({f"ship_{pid}": out / f"{pid}.glb" for pid in ids})
    shutil.rmtree(folder / "frames", ignore_errors=True)
    folder.mkdir(parents=True, exist_ok=True)
    path = common.OUT / "ship" / "motion_request.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(motion_request(layout), indent=1), encoding="utf-8", newline="\n")
    (folder / "motion.json").unlink(missing_ok=True)
    code, output = _godot.window(["--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s", MOTION_SCRIPT, "--",
                                  path.as_posix(), folder.as_posix()], MOTION["size"], MOTION_TIMEOUT)
    for line in output.splitlines():
        if line.startswith("VENT"):
            common.say(f"  {line}")
    if not (folder / "motion.json").is_file():
        raise common.Failure(f"vent_motion.gd failed (exit code {code}):\n" + "\n".join(output.splitlines()[-20:]))
    result = json.loads((folder / "motion.json").read_text(encoding="utf-8"))
    clip = folder / "vent_motion.mp4"
    clip.unlink(missing_ok=True)
    blender.run_script(VIDEO_SCRIPT, ["--frames", str(folder / "frames"), "--out", str(clip), "--fps",
                                      str(MOTION["fps"]), "--max-mb", str(MOTION["max_mb"])], timeout=MOTION_TIMEOUT)
    mb = clip.stat().st_size / 2 ** 20 if clip.is_file() else 0.0
    if clip.is_file():
        shutil.rmtree(folder / "frames", ignore_errors=True)
    for pid, r in result["vents"].items():
        common.say(f"  {pid}: {r.get('triangles')} triangles, {r.get('convex_colliders')} convex colliders, hinge edge "
                   f"drift {r.get('hinge_edge_drift_m', -1):.4f} m, tip swing {r.get('tip_swing_m', -1):.3f} m, "
                   f"{len(r.get('slat_cuts', []))} cuts, {len(r.get('slat_outside_opening', []))} outside; "
                   f"problems {r['problems']}")
    if code != 0 or errors or not result.get("ok") or not clip.is_file() or mb > MOTION["max_mb"]:
        common.bad(f"ship --motion: exit {code}, {len(errors)} import errors, ok {result.get('ok')}, video {mb:.1f} MB")
        return 1
    common.ok(f"ship --motion: the leaves hold; {clip.as_posix()} {mb:.1f} MB, sheets in {folder.as_posix()}")
    return 0
