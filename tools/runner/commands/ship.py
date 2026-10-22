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
from pathlib import Path

from .. import blender, common, ship_layout
from . import _export, _godot

NAME = "ship"
HELP = "the empty ship (layouts/ship): check the layout; --build one GLB per piece; --godot import, sizes, colliders, walk; --shoot DIR, --walk DIR"
BUILD_SCRIPT = blender.SCRIPTS / "ship_build.py"
GODOT_SCRIPT = "res://ship/ship.gd"
BUILD_TIMEOUT = 900
GODOT_TIMEOUT = 300
VIEW_SIZE = (1920, 1080)
SIZE_TOL_M = 0.01


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


def raw(layout: dict) -> Path:
    return common.raw_dir() / layout["raw_dir"]


def run(args: argparse.Namespace) -> int:
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
    if args.shoot:
        return shoot(layout, out, args.shoot.resolve())
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
           "outside": [p["id"] for p in layout["pieces"] if p["lane"] != "interior" and p["id"] in ids]}
    return req, {f"ship_{pid}": out / f"{pid}.glb" for pid in ids}


def shoot(layout: dict, out: Path, folder: Path) -> int:
    req, staged = built_request(layout, out)
    views, compares = shot_views(layout)
    req.update({"mode": "shoot", "light": {**layout["light"], "lamps": [[*_g(l[:3]), *l[3:]] for l in layout["light"]["lamps"]]},
                "views": [[v[0], v[1], _g(v[2]), _g(v[3]), v[4]] for v in views],
                "top": {"name": "top", "title": "top: plan view, south up (as plan-3)", "size_m": 36.0},
                "compare": [["top", layout["plan_ref"]], *compares], "rooms": room_boxes(layout)})
    errors = _stage(staged)
    folder.mkdir(parents=True, exist_ok=True)
    path = common.OUT / "ship" / "shoot_request.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
    (folder / "shots.json").unlink(missing_ok=True)
    code, output = _godot.window(["--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s", GODOT_SCRIPT, "--",
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
    req.update({"mode": "video", "video": video, "watchdog_s": VIDEO_TIMEOUT - 60,
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
