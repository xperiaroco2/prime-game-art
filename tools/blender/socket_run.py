"""The ship's crystal socket (art#263's stations): the driver (plain Python, outside Blender).
1. the references: the picked sheet and the drawing's straight views and script (prime-game-design
   ideas/ship-components/stations-final/: socket.jpg, socket-drawing/) copied into <raw>/ship/v4/socket/ref/ when
   missing;
2. socket_build.py in headless Blender: the model from code, the GLB (plain-PBR fallback, the charged state), the
   .blend, build.json with the checks against the built crystal (assets/prop/energy_crystal), the orthographic
   renders and the drawing over them and over the drawing's views (renders/overlay.png);
3. socket_drawing.py: the same lines as an SVG, into <tag>/drawing/;
4. glTF-Validator on the GLB;
5. the Godot shots in the ship's hall at night in an off-screen window (godot/socket/hall.gd through the runner's
   _godot.window(): every built ship piece, a socket on each of the four socket spots, the built crystal on each
   anchor): the hall views beside the sheet into <tag>/hall/, the close-ups of the edges and seams into
   <tag>/close/.
Everything goes under <raw>/ship/v4/socket/<tag>/. --asset DIR then writes the asset folder
(assets/prop/crystal_socket): the GLB and the look's files in export/, the .blend in source/, report.json and
manifest.toml with the raw files' hashes.

    $PYTHON_BIN tools/blender/socket_run.py [--tag build1] [--no-build] [--no-shots] [--samples 32]
        [--asset assets/prop/crystal_socket]
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

import socket_drawing  # noqa: E402  (beside this file)

RAW = common.raw_dir()
HOME = RAW / "ship" / "v4" / "socket"
REF = HOME / "ref"
DESIGN = Path("D:/prime-game-design/ideas/ship-components/stations-final")
REFS = {"socket.jpg": DESIGN / "socket.jpg", "front-ortho.jpg": DESIGN / "socket-drawing" / "front-ortho.jpg",
        "side-ortho.jpg": DESIGN / "socket-drawing" / "side-ortho.jpg",
        "drawing.js": DESIGN / "socket-drawing" / "drawing.js"}
CRYSTAL = ROOT / "assets" / "prop" / "energy_crystal" / "export" / "energy_crystal.glb"
MATERIAL_FILES = ("socket.gd", "socket_metal.gdshader")
SPOTS = ("socket_e", "socket_w", "socket_fe", "socket_fw")
SHOT_SPOT = "socket_e"
# the hall views on SHOT_SPOT: name, title, yaw from the front (+ toward +u), elevation (deg), target (u, d, h - mount
# in cm), distance (m), fov, state
HALL_VIEWS = [
    ("hero_charged", "charged", -28.0, 4.0, (0.0, 12.0, -6.0), 1.55, 42.0, "charged"),
    ("front_spent", "spent: the lamp lit", 0.0, 2.0, (0.0, 12.0, -6.0), 1.5, 42.0, "spent"),
    ("side_charged", "side", -78.0, 3.0, (0.0, 12.0, -6.0), 1.25, 46.0, "charged"),
    ("empty", "empty: the lamp lit", 22.0, 4.0, (0.0, 12.0, -6.0), 1.5, 42.0, "empty"),
    ("eye", "a player 2 m away", -10.0, 2.0, (0.0, 10.0, -10.0), 2.0, 70.0, "charged"),
]
CLOSE_VIEWS = [
    ("claws", "claws on the cap", -30.0, 14.0, (0.0, 17.0, 10.0), 0.42, 32.0, "charged"),
    ("claw_side", "claw roots, side", -72.0, 6.0, (8.0, 15.0, 15.0), 0.42, 34.0, "charged"),
    ("claw_under", "claws from below", 12.0, -38.0, (0.0, 17.0, 9.0), 0.42, 34.0, "charged"),
    ("lamp_neck", "lamp and neck", -35.0, 18.0, (0.0, 12.0, 30.0), 0.42, 32.0, "spent"),
    ("frame_upper", "upper frame chamfers", 35.0, 10.0, (17.0, 10.0, 10.0), 0.55, 34.0, "charged"),
    ("waist", "the waist", -60.0, 2.0, (-19.0, 8.0, -9.0), 0.5, 34.0, "charged"),
    ("plate_wall", "plate to wall", 82.0, 2.0, (22.0, 3.0, -20.0), 0.6, 36.0, "charged"),
    ("plate_top", "plate to wall, top", 15.0, 62.0, (0.0, 5.0, 28.0), 0.55, 36.0, "charged"),
    ("collar_tip", "the tip on the collar", -20.0, 12.0, (0.0, 17.0, -18.0), 0.38, 32.0, "charged"),
    ("bottom", "bottom block", 22.0, -16.0, (0.0, 12.0, -42.0), 0.55, 36.0, "charged"),
    ("bay", "into the bay, empty", -42.0, 6.0, (0.0, 10.0, 0.0), 0.5, 40.0, "empty"),
    ("strip_low", "strips beside the block", 30.0, -6.0, (-6.0, 15.0, -32.0), 0.45, 34.0, "charged"),
]
# the four spots in place: eye and target in the ship's plan (x, y, h above the deck, m), fov, state
PLACE_VIEWS = [
    ("back_pair", "the back pair: e charged, w spent", (0.0, -0.9, 1.75), (0.0, 3.1, 1.3), 74.0, "mixed"),
    ("front_pair", "the front pair: fe empty, fw charged", (0.0, 1.0, 1.75), (0.0, -2.4, 1.3), 86.0, "mixed"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="build1", help="the output folder under <raw>/ship/v4/socket/")
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--no-shots", action="store_true")
    ap.add_argument("--samples", type=int, default=32, help="the Blender renders' EEVEE samples")
    ap.add_argument("--asset", type=Path, help="write the asset folder here from this build")
    ap.add_argument("--grid", type=Path, help="a JSON list of bronze variants for the studio's grid.png")
    ap.add_argument("--studio-only", action="store_true", help="only the studio shots of an existing build")
    args = ap.parse_args()
    if args.studio_only:
        out = HOME / args.tag
        ship_cmd._stage({"crystal_socket": out / "crystal_socket.glb", "energy_crystal": CRYSTAL})
        return studio(out, args.grid)
    copy_refs()
    layout = ship_layout.load()
    pieces = ship_cmd.raw(layout) / "pieces"
    out = HOME / args.tag
    if not args.no_build:
        r = blender.run_script("socket_build.py", ["--out", str(out), "--crystal", str(CRYSTAL), "--refs", str(REF),
                                                   "--samples", str(args.samples)], timeout=1200)
        for line in (r.stdout or "").splitlines():
            if line.startswith("SOCKET_BUILD"):
                info = json.loads(line[len("SOCKET_BUILD "):])
                print(f"SOCKET_BUILD triangles {info['triangles']} {info['triangles_by_material']} size "
                      f"{info['size_cm']} anchor {info['anchor_cm']}", flush=True)
                print("SOCKET_CHECKS " + json.dumps(info.get("checks", {})), flush=True)
    sys.argv[1:] = [str(out)]
    socket_drawing.main()
    glb = out / "crystal_socket.glb"
    report = _export.validate(glb, out / "crystal_socket.validator.json")
    ok, text = _export.verdict(report)
    print(f"validator crystal_socket.glb: {text}", flush=True)
    code = 0
    if not args.no_shots:
        code = shots(layout, pieces, glb, out / "hall", hall_rows(), [["hero_charged", str(REF / "socket.jpg")]])
        if code == 0:
            code = shots(layout, pieces, glb, out / "close", view_rows(CLOSE_VIEWS), [])
        if code == 0:
            code = studio(out, args.grid)
    if args.asset and ok and code == 0:
        write_asset(args.asset, out, args.tag, report)
        print(f"asset: {args.asset}", flush=True)
    return 0 if ok and code == 0 else 1


def copy_refs() -> None:
    REF.mkdir(parents=True, exist_ok=True)
    for name, src in REFS.items():
        if not (REF / name).is_file():
            if not src.is_file():
                raise common.Failure(f"no reference {src} (prime-game-design beside this checkout)")
            shutil.copyfile(src, REF / name)


def spot(sid: str) -> tuple[float, float, float]:
    """A socket spot (layouts/ship/ship.toml [[stations.spot]]): plan x, y and the yaw (deg) that turns the
    socket's glTF +Z to the spot's normal."""
    s = next(s for s in ship_layout.load()["stations"]["spot"] if s["id"] == sid)
    nx, ny = s["normal"]
    return float(s["at"][0]), float(s["at"][1]), math.degrees(math.atan2(nx, ny))


def to_godot(sid: str, u: float, d: float, h: float) -> list[float]:
    """The socket's frame (cm: u across, d out of the wall, h up from the deck) on spot sid -> Godot's world."""
    floor = ship_layout.load()["deck"]["floor_h"]
    sx, sy, yaw = spot(sid)
    a = math.radians(yaw)
    x, z = u * 0.01, d * 0.01  # glTF: x = u, z = d (out of the wall)
    return [round(x * math.cos(a) + z * math.sin(a) + sx, 4), round(floor + h * 0.01, 4),
            round(-x * math.sin(a) + z * math.cos(a) + sy, 4)]


def view_rows(views: list) -> list:
    mount = socket_drawing.load()["mount"]["h"]
    rows = []
    for name, title, yaw, elev, (u, d, h), dist, fov, state in views:
        y, e = math.radians(yaw), math.radians(elev)
        eye = (u + math.sin(y) * math.cos(e) * dist * 100.0, d + math.cos(y) * math.cos(e) * dist * 100.0,
               h + mount + math.sin(e) * dist * 100.0)
        rows.append([name, title, to_godot(SHOT_SPOT, *eye), to_godot(SHOT_SPOT, u, d, h + mount), fov,
                     {"socket": state}])
    return rows


def hall_rows() -> list:
    floor = ship_layout.load()["deck"]["floor_h"]
    rows = view_rows(HALL_VIEWS)
    for name, title, eye, look, fov, state in PLACE_VIEWS:
        rows.append([name, title, [eye[0], floor + eye[2], eye[1]], [look[0], floor + look[2], look[1]], fov,
                     {"socket": state}])
    return rows


def shots(layout: dict, pieces: Path, glb: Path, folder: Path, views: list, compare: list) -> int:
    """The sockets in the ship's hall at night: ship.gd's shoot request (every built piece, the night light, the
    rooms' probes) plus a socket on each socket spot, shot by godot/socket/hall.gd."""
    req, staged = ship_cmd.built_request(layout, pieces)
    req["pieces"]["crystal_socket"] = "res://import/crystal_socket.glb"
    for sid in SPOTS:
        req["place"].append(["crystal_socket", to_godot(sid, 0.0, 0.0, 0.0), spot(sid)[2]])
    staged["crystal_socket"] = glb
    staged["energy_crystal"] = CRYSTAL
    req.update({"mode": "shoot", "watchdog_s": 280.0, "nav_blink": False, "compare": compare,
                "crystal": "res://import/energy_crystal.glb",
                "light": {**layout["light"], "lamps": [[*ship_cmd._g(l[:3]), *l[3:]] for l in layout["light"]["lamps"]]},
                "views": views, "rooms": ship_cmd.room_boxes(layout)})
    errors = ship_cmd._stage(staged)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "request.json"
    path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
    (folder / "shots.json").unlink(missing_ok=True)
    log = folder.parent / f"godot_{folder.name}.log"
    code, output = _godot.window(["--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s",
                                  "res://socket/hall.gd", "--", path.as_posix(), folder.as_posix()],
                                 ship_cmd.VIEW_SIZE, ship_cmd.GODOT_TIMEOUT, log=log)
    log.write_text(output, encoding="utf-8")
    print(*[x for x in output.splitlines() if x.startswith(("SOCKET", "SHIP"))], sep="\n")
    for line in errors[:10]:
        print(f"  import: {line}")
    if code != 0 or not (folder / "shots.json").is_file():
        print(f"{folder.name} shots failed:\n" + "\n".join(output.splitlines()[-20:]))
        return code or 1
    result = json.loads((folder / "shots.json").read_text(encoding="utf-8"))
    print(f"{folder.name} shots: {len(result['shots'])} in {folder}", flush=True)
    return 0


def studio(out: Path, grid: Path | None) -> int:
    """socket-2: the socket on a neutral backdrop at the sheet's three-quarter angle (godot/socket/studio.gd, after
    shots() staged the socket and the crystal): <tag>/studio/studio.png, compare_sheet.png beside the sheet, and with
    `grid` its variants' grid.png."""
    folder = out / "studio"
    folder.mkdir(parents=True, exist_ok=True)
    code, output = _godot.window(["--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s",
                                  "res://socket/studio.gd", "--", folder.as_posix(), (REF / "socket.jpg").as_posix(),
                                  grid.resolve().as_posix() if grid else ""], (900, 1000), 300, log=out / "godot_studio.log")
    print(*[x for x in output.splitlines() if x.startswith("SOCKET")], sep="\n")
    if code != 0 or not (folder / "compare_sheet.png").is_file():
        print("studio shots failed:\n" + "\n".join(output.splitlines()[-20:]))
        return code or 1
    shutil.copyfile(folder / "compare_sheet.png", out / "compare_sheet.png")
    return 0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_asset(asset: Path, out: Path, tag: str, validator: dict) -> None:
    """The asset folder from the build in out: export/ (the GLB, the Godot look's files), source/ (the .blend),
    report.json, manifest.toml (HANDOFF.md is written by hand)."""
    asset = asset if asset.is_absolute() else ROOT / asset
    (asset / "export").mkdir(parents=True, exist_ok=True)
    (asset / "source").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(out / "crystal_socket.glb", asset / "export" / "crystal_socket.glb")
    shutil.copyfile(out / "crystal_socket.blend", asset / "source" / "crystal_socket.blend")
    for name in MATERIAL_FILES:
        shutil.copyfile(ROOT / "godot" / "socket" / name, asset / "export" / name)
    build = json.loads((out / "build.json").read_text(encoding="utf-8"))
    counts = validator.get("issues", {})
    rel = asset.relative_to(ROOT).as_posix()
    report = {
        "asset": "crystal_socket",
        "built_by": f"tools/blender/socket_run.py --tag {tag} --asset {rel}",
        "mesh": {k: build[k] for k in ("triangles", "triangles_by_material", "vertices", "size_cm", "u_cm", "d_cm",
                                       "h_cm")},
        "front": "+Z (out of the wall)",
        "origin": "on the wall's face at the hall's floor level, under the crystal's axis",
        "mount_cm": build["mount_cm"],
        "crystal_anchor_cm": build["anchor_cm"],
        "colliders": build["colliders"],
        "checks": build["checks"],
        "states": {"charged": "socket.gd set_state(look, \"charged\"): the lamp off",
                   "spent": "set_state(look, \"spent\"): the lamp lit red", "empty": "set_state(look, \"empty\"): "
                   "the lamp lit red, no crystal on the anchor"},
        "placement": "the four socket spots of layouts/ship/ship.toml (socket_e, socket_w, socket_fe, socket_fw): "
                     "origin at the spot's `at` on the deck (floor_h), yaw atan2(normal x, normal y) so glTF +Z is the "
                     "spot's normal",
        "gltf_validator": {k: counts.get(k, 0) for k in ("numErrors", "numWarnings", "numInfos", "numHints")},
        "review": f"<raw>/ship/v4/socket/{tag}/hall/sheet.png",
    }
    (asset / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    raws = [f"ship/v4/socket/ref/{name}" for name in REFS] + \
        [f"ship/v4/socket/{tag}/crystal_socket.glb", f"ship/v4/socket/{tag}/crystal_socket.blend"]
    size = build["size_cm"]
    today = datetime.date.today().isoformat()
    lines = [
        "# The ship's crystal socket (art#263's stations).",
        f"# Built by tools/blender/socket_run.py --tag {tag} --asset {rel}; a rebuild changes the hashes below.",
        'id = "crystal_socket"',
        'kind = "prop"',
        'slot = ""',
        "title = \"The ship's crystal socket\"",
        ("notes = \"The wall socket that holds one energy crystal, four of them on the ship's hall walls: a bronze and "
         f'graphite frame {size["u"]:.1f} cm wide and {size["h"]:.1f} cm tall with its red problem-lamp, '
         f'{size["d"]:.1f} cm out of the wall, two fixed claws holding the built crystal\'s cap, a cyan strip round '
         f'the bay and amber windows; {build["triangles"]:,} triangles in five surfaces, convex colliders, the '
         'crystal_anchor node at the crystal\'s pivot. Front +Z, origin on the wall at floor level under the axis. '
         'States: export/socket.gd set_state (HANDOFF.md). From the sheet the engineer picked on 2026-10-25 and its '
         'drawing in cm (prime-game-design ea27a81, ideas/ship-components/stations-final: socket.jpg, '
         'socket-drawing/; copied to the raw folder). The sheet and the drawing\'s straight views are AI images '
         '(OpenAI gpt-image, batch 2026-10-25-ship-socket-drawing), used only as references; the model is built '
         'from code in headless Blender (tools/blender/socket_build.py from socket_dims.toml): no part of it was '
         'generated or downloaded."'),
        f'tools = ["blender {pins.BLENDER}", "prime-game-art socket_build.py, socket_run.py", '
        f'"glTF-Validator {pins.GLTF_VALIDATOR}", "Godot {pins.GODOT} (shots)"]',
        'licence = "own-work"',
        'licence_url = "https://github.com/xperiaroco2/prime-game"',
        "public_repo_ok = true",
        "ai_generated = false",
        "approved_by = []",
        'approved_at = ""',
        'approval_pr = ""',
        "",
        "[source]",
        'service = "own"',
        'plan = "own-work"',
        'model_version = ""',
        "task_ids = []",
        f"generated_at = {today}",
        'url = "https://github.com/xperiaroco2/prime-game-art/issues/263"',
    ]
    for r in raws:
        lines += ["", "[[raw]]", f'file = "{r}"', f'sha256 = "{sha256(RAW / r)}"']
    (asset / "manifest.toml").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    sys.exit(main())
