"""The ship engine's start console (art#263's stations): the driver (plain Python, outside Blender).
1. the references: the picked concept, its hologram and its straight views and drawing (prime-game-design
   ideas/ship-components/stations-final/: console-final.jpg, holo14-diamond-2.jpg, console-drawing/) copied into
   <raw>/start-console/ref/ when missing;
2. console_build.py in headless Blender: the model from code (the hologram from the ship's built hull pieces in
   <raw>/<ship.toml raw_dir>/pieces/), the GLB (the plain-PBR fallback), the .blend with the look materials,
   build.json, features.json, the Blender review renders of the states and the drawing's orthographic views;
3. glTF-Validator on the GLB;
4. console_drawing.py: the drawing (front, side, top in cm) over the concept's stretched views and over the model's
   orthographic renders, into <tag>/drawing/;
5. the Godot shots in the ship's hall at night in an off-screen window: godot/console/hall.gd (ship.gd's shoot mode
   with every built ship piece and the console on its station spot, its button toward the mouth) through the
   runner's _godot.window(), into <tag>/hall/;
6. godot/console/sheet.gd: the review sheet beside the concept and the console's GPU cost, into <tag>/godot/.
Everything goes under <raw>/start-console/<tag>/. --spinup: the spin-up's review on the current pieces (the deck at
1.2 m, refused on another): its four states from the console's front, the throat and both corridors' mouths and the
close-ups into <tag>/review/ (sheet.png), the before/after against the shipped build2 GLB with the spin-up hidden
(<tag>/before/, after/, diff/), and the scripted round's MP4 (<tag>/round/round.mp4; --no-video skips it).
--asset DIR then writes the asset folder
(assets/prop/start_console): the GLB and the look's files in export/, the .blend in source/, report.json and
manifest.toml with the raw files' hashes.

    $PYTHON_BIN tools/blender/console_run.py [--tag build] [--no-build] [--no-shots] [--res 900] [--samples 64]
        [--asset assets/prop/start_console] [--spinup [--no-video]]
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from runner import blender, common, pins, ship_layout  # noqa: E402
from runner.commands import _export, _godot  # noqa: E402
from runner.commands import ship as ship_cmd  # noqa: E402

import console_drawing  # noqa: E402  (beside this file)

RAW = common.raw_dir()
REF = RAW / "start-console" / "ref"
DESIGN = Path("D:/prime-game-design/ideas/ship-components/stations-final")
REFS = {"console-final.jpg": DESIGN / "console-final.jpg", "holo14-diamond-2.jpg": DESIGN / "holo14-diamond-2.jpg",
        "front-ortho.jpg": DESIGN / "console-drawing" / "front-ortho.jpg",
        "side-ortho.jpg": DESIGN / "console-drawing" / "side-ortho.jpg",
        "top-ortho.jpg": DESIGN / "console-drawing" / "top-ortho.jpg",
        "drawing.js": DESIGN / "console-drawing" / "drawing.js"}
MATERIAL_FILES = ("console.gd", "console_metal.gdshader", "console_signal.gdshader", "console_holo.gdshader")
HDRI = RAW / "env" / "polyhaven" / "studio_small_09" / "studio_small_09_2k.hdr"  # CC0, sources/polyhaven_hdris_2k.toml
YAW = 180.0                 # the console's front (glTF +Z) turned to the ship's mouth (Godot -Z)
# the hall shots: name, yaw from the front, elevation (deg), target (u, d, h cm), distance (m), fov, state
HALL_VIEWS = [
    ("q34", -35.0, 14.0, (0.0, 0.0, 95.0), 3.0, 46.0, "idle"),
    ("front", 0.0, 3.0, (0.0, 0.0, 95.0), 3.2, 42.0, "idle"),
    ("side", -90.0, 3.0, (0.0, 0.0, 95.0), 3.2, 42.0, "idle"),
    ("top_down", 0.0, 88.0, (0.0, 0.0, 110.0), 1.8, 72.0, "idle"),
    ("button", -18.0, 8.0, (0.0, 50.0, 86.0), 0.62, 32.0, "idle"),
    ("strips", 12.0, 14.0, (0.0, 52.0, 99.0), 0.62, 32.0, "idle"),
    ("emitter", -20.0, 42.0, (0.0, 0.0, 109.0), 1.3, 36.0, "idle"),
    ("holo", -28.0, 22.0, (0.0, 0.0, 146.0), 2.2, 40.0, "idle"),
    ("holo_order", -28.0, 22.0, (0.0, 0.0, 146.0), 2.2, 40.0, "order"),
    ("strips_stage", 12.0, 14.0, (0.0, 52.0, 99.0), 0.62, 32.0, "stage"),
]
EYE = ("eye", (-30.0, 200.0, 160.0), (0.0, 0.0, 118.0), 75.0)  # a player 2 m before the button, eyes at 1.6 m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="build", help="the output folder under <raw>/start-console/")
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--no-shots", action="store_true")
    ap.add_argument("--res", type=int, default=900, help="the Blender renders' size in pixels")
    ap.add_argument("--samples", type=int, default=64, help="the Blender renders' EEVEE samples")
    ap.add_argument("--asset", type=Path, help="write the asset folder here from this build")
    ap.add_argument("--approved", nargs=3, metavar=("LOGIN", "DATE", "PR_URL"),
                    help="the look's approval for the manifest (docs/manifest.md: all three together)")
    ap.add_argument("--spinup", action="store_true", help="the spin-up's review shots, before/after and round MP4")
    ap.add_argument("--no-video", action="store_true", help="--spinup without the round's MP4")
    args = ap.parse_args()
    if args.asset and args.no_shots:
        ap.error("--asset needs this run's shots (report.json takes their GPU cost)")
    copy_refs()
    layout = ship_layout.load()
    pieces = ship_cmd.raw(layout) / "pieces"
    out = RAW / "start-console" / args.tag
    renders = out / "renders"
    if not args.no_build:
        r = blender.run_script("console_build.py", ["--out", str(out), "--pieces", str(pieces), "--render",
                                                    str(renders), "--res", str(args.res), "--samples",
                                                    str(args.samples), "--views", str(REF), "--hdri", str(HDRI),
                                                    "--lift", str(layout["deck"].get("lift_m", 0.0))], timeout=1800)
        for line in (r.stdout or "").splitlines():
            if line.startswith("CONSOLE_BUILD"):
                info = json.loads(line[len("CONSOLE_BUILD "):])
                print(f"CONSOLE_BUILD triangles {info['triangles']} {info['triangles_by_material']} size "
                      f"{info['size_m']}", flush=True)
            elif line.startswith("CONSOLE"):
                print(line, flush=True)
    if (out / "features.json").is_file():
        sys.argv[1:] = [str(out)]
        console_drawing.main()
    glb = out / "start_console.glb"
    report = _export.validate(glb, out / "start_console.validator.json")
    ok, text = _export.verdict(report)
    print(f"validator start_console.glb: {text}", flush=True)
    code = 0
    if not args.no_shots:
        code = hall_shots(layout, pieces, glb, out / "hall")
        if code == 0:
            shots = out / "godot"
            shots.mkdir(exist_ok=True)
            code, output = _godot.window(["--path", str(_godot.PROJECT), "-s", "res://console/sheet.gd", "--",
                                          "res://import/start_console.glb", str(shots), str(renders),
                                          str(out / "hall"), str(REF / "console-final.jpg"),
                                          str(REF / "holo14-diamond-2.jpg")], (1280, 720), 300,
                                         log=out / "godot_sheet.log")
            print(*[x for x in output.splitlines() if x.startswith("CONSOLE ")], sep="\n")
            print(f"godot sheet: exit {code} {shots}", flush=True)
    if args.spinup and code == 0:
        code = spinup_review(layout, pieces, glb, out, not args.no_video)
        print(f"spinup review: exit {code} {out}", flush=True)
    if args.asset and ok and code == 0:
        write_asset(args.asset, out, args.tag, report, args.approved)
        print(f"asset: {args.asset}", flush=True)
    return 0 if ok and code == 0 else 1


def copy_refs() -> None:
    REF.mkdir(parents=True, exist_ok=True)
    for name, src in REFS.items():
        if not (REF / name).is_file():
            if not src.is_file():
                raise common.Failure(f"no reference {src} (prime-game-design beside this checkout)")
            shutil.copyfile(src, REF / name)


def spot() -> tuple[float, float]:
    """The console's station spot in the ship (plan x, y): layouts/ship/ship.toml [[stations.spot]] "console"."""
    at = next(s["at"] for s in ship_layout.load()["stations"]["spot"] if s["id"] == "console")
    return float(at[0]), float(at[1])


def to_godot(u: float, d: float, h: float) -> list[float]:
    """The console's frame (cm: u across, d toward the button, h up) -> Godot's world in the ship: the console
    on its station spot on the deck, its front turned to the mouth (-Z)."""
    floor = ship_layout.load()["deck"]["floor_h"]
    a = math.radians(YAW)
    x, z = u * 0.01, d * 0.01  # glTF: x = u, z = d (front +Z)
    sx, sy = spot()
    return [round(x * math.cos(a) + z * math.sin(a) + sx, 4), round(floor + h * 0.01, 4),
            round(-x * math.sin(a) + z * math.cos(a) + sy, 4)]


def view_rows() -> list:
    rows = []
    for name, yaw, elev, (u, d, h), dist, fov, state in HALL_VIEWS:
        y, e = math.radians(yaw), math.radians(elev)
        eye = (u + math.sin(y) * math.cos(e) * dist * 100.0, d + math.cos(y) * math.cos(e) * dist * 100.0,
               h + math.sin(e) * dist * 100.0)
        rows.append([name, "", to_godot(*eye), to_godot(u, d, h), fov, {"console": state}])
    name, eye, look, fov = EYE
    rows.append([name, "", to_godot(*eye), to_godot(*look), fov, {"console": "idle"}])
    return rows


def hall_shots(layout: dict, pieces: Path, glb: Path, folder: Path, views: list | None = None,
               log: str = "godot_hall.log") -> int:
    """The console in the ship's hall at night: ship.gd's shoot request (every built piece, the night light, the
    rooms' probes) plus the console, shot by godot/console/hall.gd."""
    req, staged = ship_cmd.built_request(layout, pieces)
    req["pieces"]["start_console"] = "res://import/start_console.glb"
    req["place"].append(["start_console", to_godot(0.0, 0.0, 0.0), YAW])
    staged["start_console"] = glb
    req.update({"mode": "shoot", "watchdog_s": 280.0, "nav_blink": False, "compare": [],
                "light": {**layout["light"], "lamps": [[*ship_cmd._g(l[:3]), *l[3:]] for l in layout["light"]["lamps"]]},
                "views": views or view_rows(), "rooms": ship_cmd.room_boxes(layout)})
    if views is None:
        req["top"] = {"name": "plan", "title": "", "size_m": 12.0}
    errors = ship_cmd._stage(staged)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "request.json"
    path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
    (folder / "shots.json").unlink(missing_ok=True)
    code, output = _godot.window(["--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s",
                                  "res://console/hall.gd", "--", path.as_posix(), folder.as_posix()],
                                 ship_cmd.VIEW_SIZE, ship_cmd.GODOT_TIMEOUT, log=folder.parent / log)
    (folder.parent / log).write_text(output, encoding="utf-8")
    print(*[x for x in output.splitlines() if x.startswith(("CONSOLE", "SHIP"))], sep="\n")
    for line in errors[:10]:
        print(f"  import: {line}")
    if code != 0 or not (folder / "shots.json").is_file():
        print("hall shots failed:\n" + "\n".join(output.splitlines()[-20:]))
        return code or 1
    result = json.loads((folder / "shots.json").read_text(encoding="utf-8"))
    print(f"hall shots: {len(result['shots'])} in {folder}", flush=True)
    return 0


# --- the spin-up's review (art#263, step 1) ------------------------------------------------------------------------
BEFORE = RAW / "start-console" / "build2" / "start_console.glb"  # the shipped console before the spin-up
DECK_H = 1.2                 # the raise: the deck the console stands on (refuse shots on another)
G_SPOT = (0.0, 0.6)          # the console's spot (plan x, y): Godot (x, h, y)
EYE_H = 1.6
SPIN_STATES = {
    "calling": {"clock": 3.15, "calling": True, "charge": 0.0},
    "charging": {"clock": 5.0, "spin": 1.2, "charge": 0.55, "stations": {}},
    "failures": {"clock": 10.0, "spin": 1.2, "charge": 0.55, "countdown": 4.3,
                 "stations": {"vent_e": ["broken", 1.2], "breaker_w": ["broken", 2.5]}},
    "full": {"clock": 6.0, "spin": 1.2, "charge": 1.0, "stations": {}},
}
ALL_OK = {sid: ["ok", 1.0] for sid in ("socket_w", "socket_e", "socket_fw", "socket_fe", "breaker_w", "breaker_e",
                                       "vent_w", "vent_e")}
# the stills' eyes (plan x, y; at eye height) and fov: the console's front, the throat, the corridors' mouths
SPIN_EYES = {"front": ((0.0, -1.6), 62.0), "throat": ((0.0, -4.6), 50.0), "corridor_e": ((4.3, 0.25), 50.0),
             "corridor_w": ((-4.3, 0.25), 50.0)}
# the close-ups: name, state, eye (Godot), look (Godot), fov
SPIN_CLOSE = [
    ("close_turbines", "charging", (0.32, 2.92, 0.2), (0.0, 2.76, 1.22), 34.0),
    ("close_fans_calling", "calling", (-0.3, 2.9, 0.25), (0.0, 2.76, 1.22), 30.0),
    ("close_points", "failures", (1.0, 3.45, -0.45), (0.0, 2.58, 0.62), 42.0),
    ("close_ring", "charging", (-1.05, 2.9, -0.35), (0.0, 2.6, 0.6), 36.0),
    ("close_digits", "failures", (0.45, 3.0, -1.2), (0.0, 3.2, 0.6), 30.0),
    ("close_fixed", "fixed", (0.9, 3.3, -0.6), (0.0, 2.6, 0.6), 40.0),
    # step 2's parts: the call's glow and wash, a broken point's bead and pillar, the deck ring
    ("close_call_glow", "calling", (0.0, 2.95, -0.9), (0.0, 2.75, 1.1), 44.0),
    ("close_broken", "failures", (0.0, 2.85, -1.1), (0.0, 2.68, 0.6), 40.0),
    ("close_deck", "charging", (0.85, 2.8, -0.45), (0.0, 2.3, 0.6), 40.0),
]
SPIN2_BEFORE = RAW / "start-console" / "spinup1" / "review"  # step 1's stills: before_after.png's left column
GRID_STATE = "charging"      # the variant grid: the ring's style x the bar's colour, from the hall's four eyes
GRID_STYLES = ("band", "deck", "both")
GRID_FILLS = ("cyan", "green")
VIDEO = {"fps": 24, "fov": 52.0, "size": (1280, 720), "max_mb": 15.0,
         "keys": [[(0.0, 2.8, -3.0), (0.0, 2.75, 0.6), 0.0], [(0.0, 2.8, -3.0), (0.0, 2.75, 0.6), 9.0],
                  [(2.2, 2.8, -2.3), (0.0, 2.75, 0.6), 7.0], [(3.4, 2.8, -0.6), (0.0, 2.75, 0.6), 8.0],
                  [(3.4, 2.8, -0.6), (0.0, 2.75, 0.6), 4.0], [(1.6, 2.9, -2.6), (0.0, 2.75, 0.6), 8.0],
                  [(0.0, 2.8, -3.0), (0.0, 2.75, 0.6), 8.0]]}


def spin_state(name: str) -> dict:
    s = json.loads(json.dumps(SPIN_STATES.get(name, SPIN_STATES["charging"])))
    if name == "fixed":
        s["stations"] = {**ALL_OK, "vent_e": ["fixed", 1.0, 0.25]}
    elif "stations" in s:
        s["stations"] = {**ALL_OK, **s["stations"]}
    return s


def spinup_rows() -> list:
    look = [G_SPOT[0], DECK_H + 1.5, G_SPOT[1]]
    rows = []
    for state in SPIN_STATES:
        for eye, ((x, y), fov) in SPIN_EYES.items():
            rows.append([f"{state}_{eye}", f"{state}, {eye.replace('_', ' ')}", [x, DECK_H + EYE_H, y], look, fov,
                         {"spin": spin_state(state)}])
    for name, state, eye, at, fov in SPIN_CLOSE:
        rows.append([name, name.replace("_", " "), list(eye), list(at), fov, {"spin": spin_state(state)}])
    return rows


def grid_rows() -> list:
    """Step 2's variant grid: the charge ring's styles x the bar's colours, the charging state, the four eyes."""
    look = [G_SPOT[0], DECK_H + 1.5, G_SPOT[1]]
    rows = []
    for style in GRID_STYLES:
        for fill in GRID_FILLS:
            for eye, ((x, y), fov) in SPIN_EYES.items():
                rows.append([f"{style}_{fill}_{eye}", f"{style}, {fill}, {eye.replace('_', ' ')}",
                             [x, DECK_H + EYE_H, y], look, fov,
                             {"spin": spin_state(GRID_STATE), "ring": style, "fill": fill}])
    return rows


def diff_rows() -> list:
    """The before/after views with the spin-up's surfaces hidden: the old hall views of the hologram and body (the
    strips in their old green)."""
    return [r[:5] + [{"console": "idle", "hide_spinup": True, "fill": "green", "ring": "step1"}]
            for r in view_rows() if r[0] in ("q34", "front", "holo")]


def deck_ok(layout: dict, pieces: Path) -> str:
    """'' when the pieces stand on the raised deck (floor_h 1.2: the hall floor's top), else why not."""
    if abs(layout["deck"]["floor_h"] - DECK_H) > 1e-6:
        return f"ship.toml deck floor_h {layout['deck']['floor_h']} is not {DECK_H}"
    glb = pieces / "hall_flat_floor_socket.glb"
    data = glb.read_bytes()
    n = int.from_bytes(data[12:16], "little")
    doc = json.loads(data[20:20 + n])
    top = max(doc["accessors"][p["attributes"]["POSITION"]]["max"][1] + node.get("translation", [0, 0, 0])[1]
              for node in doc["nodes"] if "mesh" in node for p in doc["meshes"][node["mesh"]]["primitives"])
    return "" if abs(top - DECK_H) < 0.02 else f"{glb.name}'s top at {top:.3f} m, not the deck's {DECK_H}"


def spinup_review(layout: dict, pieces: Path, glb: Path, out: Path, video: bool) -> int:
    why = deck_ok(layout, pieces)
    if why:
        print(f"refused: {why}")
        return 1
    code = hall_shots(layout, pieces, glb, out / "review", spinup_rows(), log="godot_review.log")
    if code == 0:
        code = hall_shots(layout, pieces, glb, out / "grid", grid_rows(), log="godot_grid.log")
    names = [f"{s}_throat" for s in SPIN_STATES]
    if code == 0 and all((SPIN2_BEFORE / f"{n}.png").is_file() for n in names):
        r = blender.run_script("console_diff.py", ["--before", str(SPIN2_BEFORE), "--after", str(out / "review"),
                                                   "--pairs", ",".join(names), "--out",
                                                   str(out / "before_after.png")], timeout=300)
        print(*[x for x in (r.stdout or "").splitlines() if x.startswith("CONSOLE_PAIRS")], sep="\n")
    elif code == 0:
        print(f"before_after.png skipped: no step 1 stills in {SPIN2_BEFORE}")
    for tag, model in (("before", BEFORE), ("after", glb)):
        if code == 0:
            code = hall_shots(layout, pieces, model, out / tag, diff_rows(), log=f"godot_{tag}.log")
    if code == 0:
        r = blender.run_script("console_diff.py", ["--before", str(out / "before"), "--after", str(out / "after"),
                                                   "--out", str(out / "diff")], timeout=300)
        print(*[x for x in (r.stdout or "").splitlines() if x.startswith("CONSOLE_DIFF")], sep="\n")
    if code == 0 and video:
        code = round_video(layout, pieces, glb, out / "round")
    return code


def round_video(layout: dict, pieces: Path, glb: Path, folder: Path) -> int:
    """The scripted round in an off-screen window (hall.gd's video mode), frames to an MP4 in headless Blender."""
    req, staged = ship_cmd.built_request(layout, pieces)
    req["pieces"]["start_console"] = "res://import/start_console.glb"
    req["place"].append(["start_console", to_godot(0.0, 0.0, 0.0), YAW])
    staged["start_console"] = glb
    req.update({"mode": "video", "watchdog_s": 1400.0, "nav_blink": False,
                "light": {**layout["light"], "lamps": [[*ship_cmd._g(l[:3]), *l[3:]] for l in layout["light"]["lamps"]]},
                "rooms": ship_cmd.room_boxes(layout),
                "video": {"fps": VIDEO["fps"], "fov": VIDEO["fov"],
                          "keys": [[list(e), list(t), s] for e, t, s in VIDEO["keys"]]}})
    errors = ship_cmd._stage(staged)
    shutil.rmtree(folder / "frames", ignore_errors=True)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "request.json"
    path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
    (folder / "video.json").unlink(missing_ok=True)
    code, output = _godot.window(["--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s",
                                  "res://console/hall.gd", "--", path.as_posix(), folder.as_posix()],
                                 VIDEO["size"], 1500, log=folder / "godot_round.log")
    if code != 0 or not (folder / "video.json").is_file():
        print("round failed:\n" + "\n".join(output.splitlines()[-20:]))
        return code or 1
    clip = folder / "round.mp4"
    clip.unlink(missing_ok=True)
    blender.run_script(ship_cmd.VIDEO_SCRIPT, ["--frames", str(folder / "frames"), "--out", str(clip), "--fps",
                                               str(VIDEO["fps"]), "--max-mb", str(VIDEO["max_mb"])], timeout=1500)
    if not clip.is_file():
        print(f"no {clip}")
        return 1
    shutil.rmtree(folder / "frames", ignore_errors=True)
    info = json.loads((folder / "video.json").read_text(encoding="utf-8"))
    mb = clip.stat().st_size / 2 ** 20
    print(f"round: {clip} {info['seconds']:.1f} s, {info['frames']} frames, {mb:.1f} MB, {len(errors)} import errors; "
          f"phases {info['phases']}", flush=True)
    return 0 if mb <= VIDEO["max_mb"] else 1


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_asset(asset: Path, out: Path, tag: str, validator: dict, approved: list | None = None) -> None:
    """The asset folder from the build in out: export/ (the GLB, the Godot look's files), source/ (the .blend),
    report.json, manifest.toml (HANDOFF.md is written by hand)."""
    asset = asset if asset.is_absolute() else ROOT / asset
    (asset / "export").mkdir(parents=True, exist_ok=True)
    (asset / "source").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(out / "start_console.glb", asset / "export" / "start_console.glb")
    shutil.copyfile(out / "start_console.blend", asset / "source" / "start_console.blend")
    for name in MATERIAL_FILES:
        shutil.copyfile(ROOT / "godot" / "console" / name, asset / "export" / name)
    build = json.loads((out / "build.json").read_text(encoding="utf-8"))
    cost = json.loads((out / "godot" / "cost.json").read_text(encoding="utf-8"))
    counts = validator.get("issues", {})
    size = build["size_m"]  # Blender axes: x, y (depth), z (height)
    report = {
        "asset": "start_console",
        "built_by": f"tools/blender/console_run.py --tag {tag} --asset {asset.relative_to(ROOT).as_posix()}",
        "mesh": {"triangles": build["triangles"], "vertices": build["vertices"],
                 "triangles_by_material": build["triangles_by_material"],
                 "triangles_by_part": build["triangles_by_part"], "hologram": build["hologram"],
                 "size_m": size, "pedestal_size_m": build["pedestal_size_m"], "front": "+Z",
                 "origin": "on the floor under the console's middle"},
        "spinup": build.get("spinup", {}),
        "states": {"idle": "console.gd set_state(look, \"idle\"): set_passed(look, 1), set_lit(look, -1)",
                   "spinup": "set_calling, call_phase, set_charge, set_spin, set_station, set_countdown, reset_spinup "
                             "(HANDOFF.md)",
                   "order": "set_lit(look, i) while the order plays (0..3 west, 4..7 east, from the hall outward)",
                   "stage": "set_passed(look, n): n strips green"},
        "placement": "on the ship's console spot (layouts/ship/ship.toml: plan (0, 0.6), 1 m aft of the hall's centre) on "
                     "the deck, yaw 180 (its front, the button, toward the mouth)",
        "gltf_validator": {k: counts.get(k, 0) for k in ("numErrors", "numWarnings", "numInfos", "numHints")},
        "godot_cost": cost,
        "review": f"<raw>/start-console/{tag}/godot/sheet.png",
    }
    (asset / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    raws = [f"start-console/ref/{name}" for name in REFS] + \
        [f"start-console/{tag}/start_console.glb", f"start-console/{tag}/start_console.blend"]
    today = datetime.date.today().isoformat()
    lines = [
        "# The ship engine's start console (art#263's stations).",
        f"# Built by tools/blender/console_run.py --tag {tag} --asset {asset.relative_to(ROOT).as_posix()}; a rebuild",
        "# changes the hashes below.",
        'id = "start_console"',
        'kind = "prop"',
        'slot = ""',
        "title = \"The ship engine's start console\"",
        ("notes = \"The engine's start console in the ship's hall: a round bronze and graphite pedestal "
         f'({build["pedestal_size_m"][0]:.2f} m across, {build["pedestal_size_m"][2]:.3f} m tall) with the orange '
         'start button at hip height, three stage strips, two cyan strips and the hologram emitter, and over it the '
         "hologram of the ship from the built hull's own mesh at 1:16.3 (lines, a faint shell, eight order lamps), "
         f'{build["triangles"]:,} triangles in thirteen surfaces, front +Z, origin on the floor under the middle; the '
         "engine's spin-up on the hologram (the turbines' fans and calling glow, the stations' wiring with a broken "
         "point's pillar, the charge ring and its second ring on the emitter deck, the countdown). "
         'States on one mesh: export/console.gd set_state, set_passed, set_lit and the spin-up\'s set_calling, '
         'set_charge, set_spin, set_station, set_countdown, set_fill, set_ring_style (HANDOFF.md). From the concept the '
         'engineer picked on 2026-10-24 and its drawing in cm (prime-game-design ideas/ship-components/stations-final: '
         'console-final.jpg, holo14-diamond-2.jpg, console-drawing/; copied to the raw folder; 2D concepts used only '
         'as references), built from code in headless Blender (tools/blender/console_build.py from '
         'console_dims.toml): no part of the model was generated or downloaded."'),
        f'tools = ["blender {pins.BLENDER}", "prime-game-art console_build.py, console_run.py", '
        f'"glTF-Validator {pins.GLTF_VALIDATOR}", "Godot {pins.GODOT} (shots)"]',
        'licence = "own-work"',
        'licence_url = "https://github.com/xperiaroco2/prime-game"',
        "public_repo_ok = true",
        "ai_generated = false",
        f'approved_by = ["{approved[0]}"]' if approved else "approved_by = []",
        f"approved_at = {approved[1]}" if approved else 'approved_at = ""',
        f'approval_pr = "{approved[2]}"' if approved else 'approval_pr = ""',
        "",
        "[source]",
        'service = "own"',
        'plan = "own-work"',
        'model_version = ""',
        "task_ids = []",
        f"generated_at = {today}",
        'url = "https://github.com/xperiaroco2/prime-game-art/issues/263"',
    ]
    for rel in raws:
        lines += ["", "[[raw]]", f'file = "{rel}"', f'sha256 = "{sha256(RAW / rel)}"']
    (asset / "manifest.toml").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    sys.exit(main())
