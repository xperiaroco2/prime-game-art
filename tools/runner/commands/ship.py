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
NOSE_SHEET_W = 1600     # art #263: the jaw nose's review sheets (3 views a row)
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
    parser.add_argument("--gill-anim", type=Path, metavar="DIR",
                        help="the throat gills' proof (godot/ship/gill_row.gd's 6 s demo on the east row's working slit: "
                             "shut, the gasp, shut, the press, open with an overshoot, settle) off-screen: MP4 into DIR")
    parser.add_argument("--gill-set", type=Path, metavar="DIR",
                        help="the throat's gill set (godot/ship/gill_set.gd's 14 s demo on both walls: the white bar runs, "
                             "presses open and shut slits, all five open hold a steam cloud) from the concept's camera, "
                             "a close one and the mouth (both rows): <DIR>/<cam>/<cam>.mp4, keys_sheet.png, the stills, the posed views and "
                             "close-ups, and sheet.png beside set_plate.jpg; off-screen")
    parser.add_argument("--gill-grid", action="store_true",
                        help="with --gill-set: only the look grid (GILL_GRID's variants from the concept camera, posed) "
                             "into <DIR>/grid/ and grid_sheet.png beside set_plate.jpg")
    parser.add_argument("--gill-demo", choices=("slit", "row"), default="slit",
                        help="--gill-anim's demo: slit (gill_anim.mp4, 6 s) or row (gill_row.mp4, 10 s: the breath runs "
                             "along the row, presses open the gasping slits, all five open -> the exhale)")
    parser.add_argument("--jaw-video", type=Path, metavar="DIR",
                        help="the jaw nose opening (art #263) from a still 3/4 front camera at night: DIR/open.mp4")
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
                        help="the --play scene off-screen: the capsule walks 2 s, presses the gill set's button (E), saves two shots and "
                             "DIR/play.json")
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
    if getattr(args, "gill_set", None):
        code = gill_set(layout, out, args.gill_set.resolve(), getattr(args, "gill_grid", False))
        if code:
            return code
    if getattr(args, "gill_anim", None):
        code = gill_anim(layout, out, args.gill_anim.resolve(), getattr(args, "gill_demo", "slit"))
        if code:
            return code
    if args.jaw_video:
        code = walk_video(layout, out, args.jaw_video.resolve(), jaw_video_request(layout), "open.mp4")
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
           "place": places(layout)}
    return req, staged


def places(layout: dict, ids: list[str] | None = None) -> list:
    """The request's placements [id, [x, h, y], yaw] (Godot); a jaw piece's row carries its pose's angle about x as a
    4th element (art #263, ship.toml [jaw])."""
    deg = ship_layout.jaw_deg(layout)
    return [[pid, _g(at), yaw, *([deg[pid]] if pid in deg else [])] for pid, at, yaw in layout["place"]
            if ids is None or pid in ids]


def jaw_request(layout: dict) -> dict:
    """{pose: {piece: degrees about x}} for a view's or the video's {"jaw": pose} (ship.gd _jaw_pose)."""
    return {pose: ship_layout.jaw_deg(layout, pose) for pose in ship_layout.JAW_POSES} if layout.get("jaw") else {}


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
           "place": places(layout, ids), "jaw": jaw_request(layout),
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
        # (the gills, 2026-10-28: a dict's "ref" does the same beside its pose)
        compares = [[v[0], v[5] if isinstance(v[5], str) else v[5]["ref"]] for v in views
                    if len(v) > 5 and (isinstance(v[5], str) or (isinstance(v[5], dict) and "ref" in v[5]))]
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
    if any(len(v) > 5 and isinstance(v[5], dict) and ("jaw" in v[5] or v[5].get("solo")) for v in req["views"]):
        # art #263, the nose: a view's {"jaw": pose} shows the jaw in that pose ([jaw] in ship.toml); {"solo": true}
        # alone; either way the sheet holds the review's views alone, NOSE_SHEET_W wide (no plan, top or day views)
        req.update({"sheet_px": NOSE_SHEET_W, "compare": []})
        for key in ("top", "top_full", "day_views"):
            req.pop(key, None)
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
        # step 5: and a scripted E press at the gill set's button flips the slit under the white bar (a shot each);
        # step 6: on each wall (its own row, its own button), the other wall's row untouched
        press = result.get("press", {})
        walls = press.get("walls", {})
        if (result["moved_m"] < 1.0 or not result["on_floor"] or result["shots"] != 3 or not press.get("ok")
                or set(walls) != {"e", "w"}):
            common.bad(f"ship --play-test: {result}")
            return 1
        flips = ", ".join(f"{p['side']} slit {p['slit']} {p['state']}" for p in press["presses"])
        common.ok(f"ship --play-test: walked {result['moved_m']} m on the floor; E at each wall's button flipped "
                  f"{flips}; three shots in {folder.as_posix()}")
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


# art #263, the jaw nose: the opening from a still 3/4 front camera at eye height, [t, lower deg, upper deg, seam glow]
# keys (eased between): closed, the seam lights, the lower jaw lowers to the ground as the ramp, the upper lifts
JAW_VIDEO = {"size": [1280, 720], "fps": 30, "fov": 50.0, "max_mb": 15, "eye": [-9.9, -22.4, 1.7], "look": [0.0, -8.0, 2.0],
             "seconds": 6.5, "jaw": [[0.0, 0.0, 0.0, 0.0], [0.4, 0.0, 0.0, 0.0], [1.3, 0.0, 0.0, 1.0], [1.6, 0.0, 0.0, 1.0],
                                    [3.0, -9.0, 1.6, 1.0], [4.9, None, None, 1.0], [6.5, None, None, 1.0]]}


def jaw_video_request(layout: dict) -> dict:
    """JAW_VIDEO in Godot coordinates, its keys' None the open pose's angles."""
    v, deg = JAW_VIDEO, ship_layout.jaw_deg(layout, "open")
    lower, upper = deg[layout["jaw"]["lower"][0]], deg[layout["jaw"]["upper"][0]]
    keys = [[t, lower if lo is None else lo, upper if up is None else up, g] for t, lo, up, g in v["jaw"]]
    return {"size": v["size"], "fps": v["fps"], "fov": v["fov"], "max_mb": v["max_mb"],
            "keys": [[_g(v["eye"]), _g(v["look"]), 0.0], [_g(v["eye"]), _g(v["look"]), v["seconds"]]],
            "jaw": keys, "lower": layout["jaw"]["lower"], "upper": layout["jaw"]["upper"]}


def walk_video(layout: dict, out: Path, folder: Path, video: dict | None = None, name: str = "walkthrough.mp4") -> int:
    """The eye-height walk-through: Godot renders every frame in the off-screen window (ship.gd mode "video"), headless
    Blender encodes them (ship_video.py, under max_mb), and the frames are deleted. `video`: another camera path (the
    jaw's opening, `--jaw-video`) into `name`."""
    import shutil
    video = video or video_request(layout)
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
    clip = folder / name
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


def gill_view(layout: dict, s: float, t: float, back: float, along: float = 0.0, up: float = 0.0,
              side: str = "e") -> tuple:
    """(eye, look) in plan (x, y, h) for a point on the east gills' wall (s along it from the mouth's corner, t up its
    vertical part), the eye `back` m into the throat, `along` m toward the hall and `up` m higher; side "w": the same
    on the west wall (step 6: the ship's mirror in x)."""
    import importlib
    import sys
    sys.path.insert(0, str(blender.SCRIPTS))
    g = importlib.import_module("ship_interior_gills")
    m = [g.S.TH_PTS[1][0] + g.S.HALL_C[0], g.S.TH_PTS[1][1] + g.S.HALL_C[1]]
    d, n = g.WALL_D, (-g.WALL_D[1], g.WALL_D[0])
    h = layout["deck"]["floor_h"] + t
    look = [m[0] + d[0] * s, m[1] + d[1] * s, h]
    eye = [look[0] + n[0] * back + d[0] * along, look[1] + n[1] * back + d[1] * along, h + up]
    if side == "w":
        eye[0], look[0] = 2 * g.S.HALL_C[0] - eye[0], 2 * g.S.HALL_C[0] - look[0]
    return [round(v, 4) for v in eye], [round(v, 4) for v in look]


def throat_axis(layout: dict) -> tuple[float, float, float]:
    """(x, y at the mouth's corners, y at the walls' hall end) of the throat's middle line (step 6's both-wall views)."""
    import importlib
    import sys
    sys.path.insert(0, str(blender.SCRIPTS))
    g = importlib.import_module("ship_interior_gills")
    my = g.S.TH_PTS[1][1] + g.S.HALL_C[1]
    return g.S.HALL_C[0], my, my + g.WALL_D[1] * 4.047


GILL_ANIM = {"s": 2.66, "t": 1.32, "back": 0.95, "along": -0.45, "up": 0.08, "fov": 50.0, "fps": 30,
             "size": (1280, 720), "max_mb": 8}
GILL_ROW = {**GILL_ANIM, "s": 2.78, "t": 1.30, "back": 2.05, "along": -0.55, "up": 0.15, "fov": 62.0}   # the whole row


def gill_anim(layout: dict, out: Path, folder: Path, demo: str = "slit") -> int:
    """The gills' proof (art #263, 2026-10-28): ship.gd mode "gill_anim" renders gill_row.gd's demo on the east row's
    working slit at night in the off-screen window; headless Blender encodes the MP4; the frames are deleted."""
    import shutil
    a = GILL_ROW if demo == "row" else GILL_ANIM
    eye, look = gill_view(layout, a["s"], a["t"], a["back"], a["along"], a["up"])
    req, staged = built_request(layout, out)
    req.update({"mode": "gill_anim", "watchdog_s": VIDEO_TIMEOUT - 60, "nav_blink": False,
                "anim": {"eye": _g(eye), "look": _g(look), "fov": a["fov"], "fps": a["fps"], "demo": demo},
                "light": {**layout["light"], "lamps": [[*_g(l[:3]), *l[3:]] for l in layout["light"]["lamps"]]},
                "rooms": room_boxes(layout)})
    errors = _stage(staged)
    shutil.rmtree(folder / "frames", ignore_errors=True)
    folder.mkdir(parents=True, exist_ok=True)
    path = common.OUT / "ship" / "gill_anim_request.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
    (folder / "anim.json").unlink(missing_ok=True)
    code, output = _godot.window(["--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s", GODOT_SCRIPT, "--",
                                  path.as_posix(), folder.as_posix()], a["size"], VIDEO_TIMEOUT)
    if code != 0 or not (folder / "anim.json").is_file():
        raise common.Failure(f"ship.gd gill_anim failed (exit code {code}):\n" + "\n".join(output.splitlines()[-20:]))
    info = json.loads((folder / "anim.json").read_text(encoding="utf-8"))
    clip = folder / ("gill_row.mp4" if demo == "row" else "gill_anim.mp4")
    clip.unlink(missing_ok=True)
    blender.run_script(VIDEO_SCRIPT, ["--frames", str(folder / "frames"), "--out", str(clip), "--fps", str(a["fps"]),
                                      "--max-mb", str(a["max_mb"])], timeout=VIDEO_TIMEOUT)
    if not clip.is_file():
        raise common.Failure(f"{VIDEO_SCRIPT} wrote no {clip}")
    shutil.rmtree(folder / "frames", ignore_errors=True)
    mb = clip.stat().st_size / 2 ** 20
    if errors or mb > a["max_mb"]:
        common.bad(f"ship --gill-anim: video {mb:.1f} MB (max {a['max_mb']}), {len(errors)} import errors")
        return 1
    common.ok(f"ship --gill-anim: {clip.as_posix()}, {info['seconds']:.1f} s, {info['frames']} frames, {mb:.1f} MB; "
              f"beats {info['states']}")
    return 0


# the gill set (art #263, 2026-10-29): the concept camera frames the wall square-on from the ramp frame to the jamb as
# set_plate.jpg does (2.4 m out, eye 1.25 m; the old wall_square_on is the view "concept_wide"), the close one 1.5 m out from slot 3 a little toward the hall; the views (s, t, back, along, up on the east wall, or plan
# points) are posed: "open" the slits open (1..5), "at" the white bar's slit
GILL_SET = {"concept": {"s": 2.85, "t": 1.25, "back": 2.4, "along": 0.0, "up": 0.0, "fov": 58.0},
            "close": {"s": 2.69, "t": 1.35, "back": 1.5, "along": 0.35, "up": 0.2, "fov": 55.0},
            "both": {"eye": (0.3, 1.6), "look": (4.0, 1.3), "fov": 75.0},   # step 7: as mouth_both (dy, h)
            "ref": "D:/prime-game-design/ideas/ship-components/slits-lamps/set_plate.jpg",
            "fps": 30, "size": (1280, 720), "max_mb": 15}
MID = ([1, 2, 3], 4)
GILL_VIEWS = [  # name, (s, t, back, along, up) eye, (s, t) look, fov, (open, at)
    ("square_on", (2.75, 1.35, 2.2, 0.0, 0.25), (2.75, 1.35), 60.0, MID),
    ("square_on_open", (2.75, 1.35, 2.2, 0.0, 0.25), (2.75, 1.35), 60.0, ([1, 2, 3, 4, 5], 3)),
    ("from_mouth", (1.0, 1.55, 1.4, 0.0, 0.0), (3.0, 1.30), 70.0, MID),
    ("from_hall", (4.6, 1.55, 1.4, 0.0, 0.0), (2.4, 1.30), 70.0, MID),
    ("cu_slit1", (1.97, 1.36, 0.85, -0.25, 0.1), (2.10, 1.36), 55.0, MID),   # step 4: the slits spread (s 2.07-3.53)
    ("cu_slit2", (2.34, 1.32, 0.85, -0.25, 0.1), (2.47, 1.32), 55.0, MID),
    ("cu_slit3", (2.70, 1.29, 0.85, -0.25, 0.1), (2.83, 1.29), 55.0, MID),
    ("cu_slit4", (3.06, 1.26, 0.85, -0.25, 0.1), (3.19, 1.26), 55.0, MID),
    ("cu_slit5", (3.43, 1.23, 0.85, -0.25, 0.1), (3.56, 1.23), 55.0, MID),
    ("cu_slit_graze", (3.95, 1.30, 0.5, 0.0, 0.05), (2.5, 1.30), 50.0, MID),
    ("cu_groove_top", (2.0, 1.95, 0.55, 0.0, 0.05), (2.0, 1.95), 50.0, MID),
    ("cu_groove_left", (1.80, 1.35, 0.6, 0.0, 0.05), (1.80, 1.35), 50.0, MID),
    ("cu_groove_tail", (2.40, 0.72, 0.6, 0.0, 0.1), (2.40, 0.72), 50.0, MID),
    ("cu_bars", (2.95, 1.80, 0.9, 0.0, 0.05), (2.95, 1.80), 55.0, MID),
    ("cu_button", (3.86, 1.15, 0.5, -0.1, 0.05), (3.86, 1.15), 45.0, MID),
    ("cu_end", (3.80, 1.25, 0.9, -0.3, 0.1), (4.0, 1.1), 55.0, MID),
    # step 6: the west wall (the mirror, side "w"): the concept camera shut, mid and all open, its groove ends, button
    # and end; and the row of all five square on at one scale, shut and open, on both walls (the glow's balance)
    ("e_concept_shut", (2.85, 1.25, 2.4, 0.0, 0.0), (2.85, 1.25), 58.0, ([], 0)),
    ("e_concept_mid", (2.85, 1.25, 2.4, 0.0, 0.0), (2.85, 1.25), 58.0, MID),
    ("e_concept_open", (2.85, 1.25, 2.4, 0.0, 0.0), (2.85, 1.25), 58.0, ([1, 2, 3, 4, 5], 3)),
    ("w_concept_shut", (2.85, 1.25, 2.4, 0.0, 0.0), (2.85, 1.25), 58.0, ([], 0), "w"),
    ("w_concept_mid", (2.85, 1.25, 2.4, 0.0, 0.0), (2.85, 1.25), 58.0, MID, "w"),
    ("w_concept_open", (2.85, 1.25, 2.4, 0.0, 0.0), (2.85, 1.25), 58.0, ([1, 2, 3, 4, 5], 3), "w"),
    ("w_cu_groove_top", (2.0, 1.95, 0.55, 0.0, 0.05), (2.0, 1.95), 50.0, MID, "w"),
    ("w_cu_groove_tail", (2.40, 0.72, 0.6, 0.0, 0.1), (2.40, 0.72), 50.0, MID, "w"),
    ("w_cu_button", (3.86, 1.15, 0.5, -0.1, 0.05), (3.86, 1.15), 45.0, MID, "w"),
    ("w_cu_end", (3.80, 1.25, 0.9, -0.3, 0.1), (4.0, 1.1), 55.0, MID, "w"),
    ("row_shut", (2.80, 1.36, 1.8, 0.0, 0.0), (2.80, 1.36), 40.0, ([], 0)),
    ("row_open", (2.80, 1.36, 1.8, 0.0, 0.0), (2.80, 1.36), 40.0, ([1, 2, 3, 4, 5], 3)),
    ("w_row_shut", (2.80, 1.36, 1.8, 0.0, 0.0), (2.80, 1.36), 40.0, ([], 0), "w"),
    ("w_row_open", (2.80, 1.36, 1.8, 0.0, 0.0), (2.80, 1.36), 40.0, ([1, 2, 3, 4, 5], 3), "w"),
]
# step 6: both walls in view from the throat's middle line: (name, eye (dy from the mouth's corners, h over the deck),
# look (dy, h), fov, pose); dy < 0: |dy| past the walls' hall end into the hall
GILL_AXIS_VIEWS = [("mouth_both", (0.3, 1.6), (4.0, 1.3), 75.0, MID), ("hall_both", (-1.2, 1.6), (0.0, 1.3), 70.0, MID)]
# step 7: the corner flats' clad at eye height (1.6 m over the deck), plan points (x, y) of the east one (the flat's
# middle 3.44, -2.31, facing the hall), side "w" the ship's mirror: from the throat by its hall end, and 2.4 m before it
# from the hall
CLAD_VIEWS = [("clad_throat", (0.0, -4.0, 1.6), (3.44, -2.31, 1.4), 60.0, "e"),
              ("w_clad_throat", (0.0, -4.0, 1.6), (3.44, -2.31, 1.4), 60.0, "w"),
              ("clad_hall", (1.34, -1.14, 1.6), (3.44, -2.31, 1.4), 60.0, "e"),
              ("w_clad_hall", (1.34, -1.14, 1.6), (3.44, -2.31, 1.4), 60.0, "w"),
              # his --play shot 003 (<raw>/ship/v5/play/shots.txt: plan 0.274, -2.18, look [0.906, -0.421, 0.052], the
              # player's fov 75) and its mirror: the throat's hall end, the end frame and the flat
              ("play003", (0.274, -2.18, 1.6), (2.992, -3.443, 1.756), 75.0, "e"),
              ("w_play003", (0.274, -2.18, 1.6), (2.992, -3.443, 1.756), 75.0, "w")]
GILL_SHEET = [["ref", "concept_mid"], ["w_concept_mid", "mouth_both"]]   # set_plate | east mid; west mid | both


# the look grid (step 3; LOOK holds its pick "deep_mid", after deep_lo, halo and blue_mid lost): gill_set.gd LOOK
# overrides and an optional pose ([open slits], white bar); "mid" LOOK posed, then the all-open cloud's strength and drift
ALL_OPEN = [[1, 2, 3, 4, 5], 3]
# (a grid tile holds the cloud about 2.5 s; the MP4's 6 s build is denser, hence LOOK's 0.3 and drift 1.6)
GILL_GRID = [["mid", {}], ["cloud_04", {"cloud": 0.4, "drift": 1.0}, ALL_OPEN],
             ["cloud_06", {"cloud": 0.6, "drift": 1.0}, ALL_OPEN], ["cloud_09", {"cloud": 0.9, "drift": 1.0}, ALL_OPEN],
             ["cloud_06_drift14", {"cloud": 0.6, "drift": 1.4}, ALL_OPEN]]


def gill_set(layout: dict, out: Path, folder: Path, grid: bool = False, only: list[str] | None = None) -> int:
    """The gill set's proof: ship.gd mode "gill_set" renders gill_set.gd's demo on th_wall_e from both cameras at night
    in the off-screen window, then the posed views and close-ups; headless Blender encodes each camera's MP4; the
    frames are deleted."""
    import shutil
    a = GILL_SET
    c = a["close"]
    k = a["concept"]
    cams = [["concept", _g(gill_view(layout, k["s"], k["t"], k["back"], k["along"], k["up"])[0]),
             _g(gill_view(layout, k["s"], k["t"], 0.05)[0]), k["fov"]],
            ["close", _g(gill_view(layout, c["s"], c["t"], c["back"], c["along"], c["up"])[0]),
             _g(gill_view(layout, c["s"], c["t"], 0.05)[0]), c["fov"]]]
    x0, y_mouth, y_hall = throat_axis(layout)
    deck = layout["deck"]["floor_h"]
    b = a["both"]   # step 7: both walls' rows running, from the mouth up the throat
    cams.append(["both", _g([x0, y_mouth + b["eye"][0], deck + b["eye"][1]]),
                 _g([x0, y_mouth + b["look"][0], deck + b["look"][1]]), b["fov"]])
    views = [["concept_wide", _g([-1.7323, -3.6196, 2.43]), _g([2.3527, -4.9625, 2.43]), 52.0, *MID]]
    views += [[name, _g(gill_view(layout, *eye, side=v[0] if v else "e")[0]),
               _g(gill_view(layout, *look, 0.0, side=v[0] if v else "e")[0]), fov, pose[0], pose[1]]
              for name, eye, look, fov, pose, *v in GILL_VIEWS]
    for name, (de, he), (dl, hl), fov, pose in GILL_AXIS_VIEWS:
        ye, yl = (y_mouth + de if de >= 0 else y_hall - de), (y_mouth + dl if dl >= 0 else y_hall - dl)
        views.append([name, _g([x0, ye, deck + he]), _g([x0, yl, deck + hl]), fov, pose[0], pose[1]])
    for name, (xe, ye, he), (xl, yl, hl), fov, side in CLAD_VIEWS:
        sx = -1.0 if side == "w" else 1.0
        views.append([name, _g([sx * xe, ye, deck + he]), _g([sx * xl, yl, deck + hl]), fov, *MID])
    if only is not None:   # step 6: a views-only run (no demo, no videos): the named views
        cams, views = [], [v for v in views if v[0] in only]
    req, staged = built_request(layout, out)
    req.update({"mode": "gill_set", "watchdog_s": VIDEO_TIMEOUT - 60, "nav_blink": False,
                "anim": {"cams": cams, "views": views, "fps": a["fps"], "ref": a["ref"],
                         **({"grid": GILL_GRID} if grid else {}), **({} if only is not None else {"sheet": GILL_SHEET})},
                "light": {**layout["light"], "lamps": [[*_g(l[:3]), *l[3:]] for l in layout["light"]["lamps"]]},
                "rooms": room_boxes(layout)})
    errors = _stage(staged)
    for cam in cams:
        shutil.rmtree(folder / cam[0] / "frames", ignore_errors=True)
        shutil.rmtree(folder / cam[0] / "keys", ignore_errors=True)
    folder.mkdir(parents=True, exist_ok=True)
    path = common.OUT / "ship" / "gill_set_request.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
    (folder / "anim.json").unlink(missing_ok=True)
    code, output = _godot.window(["--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s", GODOT_SCRIPT, "--",
                                  path.as_posix(), folder.as_posix()], a["size"], VIDEO_TIMEOUT)
    if code != 0 or not (folder / "anim.json").is_file():
        raise common.Failure(f"ship.gd gill_set failed (exit code {code}):\n" + "\n".join(output.splitlines()[-20:]))
    info = json.loads((folder / "anim.json").read_text(encoding="utf-8"))
    if grid:
        common.ok(f"ship --gill-set --gill-grid: {(folder / 'grid_sheet.png').as_posix()}")
        return 0
    if only is not None:
        common.ok(f"ship --gill-set: {len(views)} views in {(folder / 'stills').as_posix()}")
        return 0
    sizes = {}
    for cam in cams:
        clip = folder / f"{cam[0]}.mp4"
        clip.unlink(missing_ok=True)
        blender.run_script(VIDEO_SCRIPT, ["--frames", str(folder / cam[0] / "frames"), "--out", str(clip),
                                          "--fps", str(a["fps"]), "--max-mb", str(a["max_mb"])], timeout=VIDEO_TIMEOUT)
        if not clip.is_file():
            raise common.Failure(f"{VIDEO_SCRIPT} wrote no {clip}")
        shutil.rmtree(folder / cam[0] / "frames", ignore_errors=True)
        sizes[clip] = clip.stat().st_size / 2 ** 20
    if errors or max(sizes.values()) > a["max_mb"]:
        common.bad(f"ship --gill-set: videos {', '.join(f'{mb:.1f}' for mb in sizes.values())} MB "
                   f"(max {a['max_mb']}), {len(errors)} import errors")
        return 1
    for clip, mb in sizes.items():
        common.ok(f"ship --gill-set: {clip.as_posix()}, {info['seconds']:.1f} s, {info['frames']} frames, {mb:.1f} MB")
    common.ok(f"ship --gill-set: presses {info['presses']}; sheet {(folder / 'sheet.png').as_posix()}")
    return 0


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
