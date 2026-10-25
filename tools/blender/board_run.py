"""The ship's breaker board, the shells (art#263's stations): the driver (plain Python, outside Blender).
1. the references: the picked sheet and its drawing's straight views and numbers (prime-game-design commit 6b0e83e,
   ideas/ship-components/stations-final/: board-variants/v3-shell-final.jpg, board-drawing/) copied into
   <raw>/ship/v4/board/ref/ when missing;
2. board_build.py in headless Blender: the model from code, the GLB, the .blend, build.json (sizes, the measured
   numbers, the shells' sweep check) and the drawing's overlays (the model over the straight views);
3. glTF-Validator on the GLB;
4. board_drawing.py: the drawing (front and side in cm, the built numbers against the drawing's) into <tag>/drawing/;
5. the Godot shots in the east corridor at night in an off-screen window: godot/board/corridor.gd (ship.gd's shoot
   mode with every built ship piece and a board on each of breaker_e and breaker_w) through the runner's
   _godot.window(), into <tag>/corridor/: the board all on and tripped like the sheet (compare_*.png: the sheet left,
   the shot right), the yellow shell's trip at 0, 1/4, 1/2, 3/4 and 1, and the close-ups of every edge and seam.
Everything goes under <raw>/ship/v4/board/<tag>/. --asset DIR then writes the asset folder
(assets/prop/breaker_board): the GLB and the look's files in export/, the .blend in source/, report.json and
manifest.toml with the raw files' hashes.

    $PYTHON_BIN tools/blender/board_run.py [--tag b1] [--no-build] [--no-shots] [--res 1024]
        [--asset assets/prop/breaker_board]
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

import board_drawing  # noqa: E402  (beside this file)

RAW = common.raw_dir()
BASE = RAW / "ship" / "v4" / "board"
REF = BASE / "ref"
DESIGN = Path("D:/prime-game-design/ideas/ship-components/stations-final")
DESIGN_COMMIT = "6b0e83e"
REFS = {"v3-shell-final.jpg": "board-variants/v3-shell-final.jpg", "front-ortho.jpg": "board-drawing/front-ortho.jpg",
        "side-ortho.jpg": "board-drawing/side-ortho.jpg", "drawing.js": "board-drawing/drawing.js"}
MATERIAL_FILES = ("board.gd", "board_metal.gdshader", "board_core.gdshader")
SPOTS = ("breaker_e", "breaker_w")
SHOT_SPOT = "breaker_e"
ON = {"open": [0, 0, 0, 0], "on": [True] * 4, "problem": False}
TRIPPED = {"open": [0, 1, 1, 0], "on": [True, False, False, True], "problem": True}
# the corridor shots: name, yaw from the front (deg, + from the board's right), elevation, target (u, d, h cm),
# distance (m), fov, state
VIEWS = [
    ("on_q34", -32.0, 6.0, (0.0, 0.0, 92.0), 2.3, 50.0, ON),
    ("tripped_q34", -32.0, 6.0, (0.0, 0.0, 92.0), 2.3, 50.0, TRIPPED),
    ("tripped_front", 0.0, 2.0, (0.0, 0.0, 92.0), 2.2, 48.0, TRIPPED),
    ("tripped_side", 62.0, 8.0, (0.0, 0.0, 88.0), 2.0, 50.0, TRIPPED),
    ("eye", -12.0, 22.0, (0.0, 0.0, 92.0), 1.6, 70.0, TRIPPED),
]
SWEEP = [("sweep_%03d" % round(t * 100), t) for t in (0.0, 0.25, 0.5, 0.75, 1.0)]
SWEEP_VIEW = (68.0, 12.0, (-16.8, 26.0, 76.0), 0.95, 50.0)
CLOSE = [  # the edges and seams, close
    ("close_hinge", -28.0, 18.0, (-16.8, 25.0, 68.0), 0.42, 45.0, TRIPPED),
    ("close_rim", -38.0, 10.0, (-50.4, 28.0, 92.0), 0.5, 45.0, ON),
    ("close_core", 18.0, 8.0, (16.8, 18.0, 88.0), 0.45, 45.0, TRIPPED),
    ("close_beacon", -30.0, 18.0, (0.0, 12.0, 131.0), 0.42, 45.0, TRIPPED),
    ("close_cables", -30.0, -8.0, (-55.4, 12.0, 50.0), 0.5, 50.0, ON),
    ("close_clamp", 35.0, 12.0, (-37.3, 10.0, 24.0), 0.5, 50.0, ON),
    ("close_plate", -72.0, 10.0, (-78.0, 4.0, 62.0), 0.55, 50.0, ON),
    ("close_corner", 32.0, 22.0, (62.0, 22.0, 124.0), 0.55, 50.0, ON),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="b1", help="the output folder under <raw>/ship/v4/board/")
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--no-shots", action="store_true")
    ap.add_argument("--res", type=int, default=1024, help="the overlays' width in pixels")
    ap.add_argument("--asset", type=Path, help="write the asset folder here from this build")
    args = ap.parse_args()
    copy_refs()
    out = BASE / args.tag
    if not args.no_build:
        r = blender.run_script("board_build.py", ["--out", str(out), "--views", str(REF), "--res", str(args.res)],
                               timeout=900)
        for line in (r.stdout or "").splitlines():
            if line.startswith("BOARD"):
                print(line, flush=True)
    if (out / "build.json").is_file():
        sys.argv[1:] = [str(out)]
        board_drawing.main()
    glb = out / "breaker_board.glb"
    report = _export.validate(glb, out / "breaker_board.validator.json")
    ok, text = _export.verdict(report)
    print(f"validator breaker_board.glb: {text}", flush=True)
    code = 0
    if not args.no_shots:
        code = corridor_shots(glb, out / "corridor")
    if args.asset and ok and code == 0:
        write_asset(args.asset, out, args.tag, report)
        print(f"asset: {args.asset}", flush=True)
    return 0 if ok and code == 0 else 1


def copy_refs() -> None:
    REF.mkdir(parents=True, exist_ok=True)
    for name, rel in REFS.items():
        if not (REF / name).is_file():
            src = DESIGN / rel
            if not src.is_file():
                raise common.Failure(f"no reference {src} (prime-game-design at {DESIGN_COMMIT} beside this checkout)")
            shutil.copyfile(src, REF / name)


def spot(name: str) -> tuple[float, float, float, float]:
    """A wall spot (layouts/ship/ship.toml [[stations.spot]]): plan x, y and its normal into the room."""
    s = next(s for s in ship_layout.load()["stations"]["spot"] if s["id"] == name)
    return float(s["at"][0]), float(s["at"][1]), float(s["normal"][0]), float(s["normal"][1])


def yaw(name: str) -> float:
    """The board's turn on its spot: glTF +Z (out of the wall) along the spot's normal (Godot x, z = plan x, y)."""
    _, _, nx, ny = spot(name)
    return math.degrees(math.atan2(nx, ny))


def to_godot(name: str, u: float, d: float, h: float) -> list[float]:
    """The board's frame (cm: u across, d out of the wall, h up) on its spot -> Godot's world in the ship."""
    floor = ship_layout.load()["deck"]["floor_h"]
    sx, sy, nx, ny = spot(name)
    rx, ry = ny, -nx  # the board's +u: its right as you face it
    return [round(sx + (u * rx + d * nx) * 0.01, 4), round(floor + h * 0.01, 4), round(sy + (u * ry + d * ny) * 0.01, 4)]


def view_row(name: str, yaw_deg: float, elev: float, target: tuple, dist: float, fov: float, state: dict) -> list:
    y, e = math.radians(yaw_deg), math.radians(elev)
    u, d, h = target
    eye = (u + math.sin(y) * math.cos(e) * dist * 100.0, d + math.cos(y) * math.cos(e) * dist * 100.0,
           h + math.sin(e) * dist * 100.0)
    return [name, "", to_godot(SHOT_SPOT, *eye), to_godot(SHOT_SPOT, *target), fov, {"board": state}]


def view_rows() -> list:
    rows = [view_row(*v) for v in VIEWS]
    for name, t in SWEEP:
        rows.append(view_row(name, *SWEEP_VIEW, {"open": [0, t, 0, 0], "on": [True, t == 0, True, True],
                                                  "problem": t > 0}))
    rows += [view_row(*v) for v in CLOSE]
    return rows


def corridor_shots(glb: Path, folder: Path) -> int:
    layout = ship_layout.load()
    pieces = ship_cmd.raw(layout) / "pieces"
    req, staged = ship_cmd.built_request(layout, pieces)
    req["pieces"]["breaker_board"] = "res://import/breaker_board.glb"
    for s in SPOTS:
        req["place"].append(["breaker_board", to_godot(s, 0.0, 0.0, 0.0), round(yaw(s), 3)])
    staged["breaker_board"] = glb
    sheet = str(REF / "v3-shell-final.jpg")
    req.update({"mode": "shoot", "watchdog_s": 280.0, "nav_blink": False,
                "compare": [["on_q34", sheet], ["tripped_q34", sheet]],
                "light": {**layout["light"], "lamps": [[*ship_cmd._g(l[:3]), *l[3:]] for l in layout["light"]["lamps"]]},
                "views": view_rows(), "rooms": ship_cmd.room_boxes(layout)})
    errors = ship_cmd._stage(staged)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "request.json"
    path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
    (folder / "shots.json").unlink(missing_ok=True)
    code, output = _godot.window(["--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s",
                                  "res://board/corridor.gd", "--", path.as_posix(), folder.as_posix()],
                                 ship_cmd.VIEW_SIZE, ship_cmd.GODOT_TIMEOUT, log=folder.parent / "godot_corridor.log")
    (folder.parent / "godot_corridor.log").write_text(output, encoding="utf-8")
    print(*[x for x in output.splitlines() if x.startswith(("BOARD", "SHIP"))], sep="\n")
    for line in errors[:10]:
        print(f"  import: {line}")
    if code != 0 or not (folder / "shots.json").is_file():
        print("corridor shots failed:\n" + "\n".join(output.splitlines()[-20:]))
        return code or 1
    result = json.loads((folder / "shots.json").read_text(encoding="utf-8"))
    print(f"corridor shots: {len(result['shots'])} in {folder}", flush=True)
    return 0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_asset(asset: Path, out: Path, tag: str, validator: dict) -> None:
    """The asset folder from the build in out: export/ (the GLB, the Godot look's files), source/ (the .blend),
    report.json, manifest.toml (HANDOFF.md is written by hand)."""
    asset = asset if asset.is_absolute() else ROOT / asset
    (asset / "export").mkdir(parents=True, exist_ok=True)
    (asset / "source").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(out / "breaker_board.glb", asset / "export" / "breaker_board.glb")
    shutil.copyfile(out / "breaker_board.blend", asset / "source" / "breaker_board.blend")
    for name in MATERIAL_FILES:
        shutil.copyfile(ROOT / "godot" / "board" / name, asset / "export" / name)
    build = json.loads((out / "build.json").read_text(encoding="utf-8"))
    counts = validator.get("issues", {})
    m = build["measured_cm"]
    report = {
        "asset": "breaker_board",
        "built_by": f"tools/blender/board_run.py --tag {tag} --asset {asset.relative_to(ROOT).as_posix()}",
        "mesh": {"triangles": build["triangles"], "triangles_by_material": build["triangles_by_material"],
                 "triangles_by_object": build["triangles_by_object"], "colliders": build["colliders"],
                 "size_m": build["size_m"], "front": "+Z (out of the wall)",
                 "origin": "on the wall's face at the floor under the centre line"},
        "leaves": {f"shell_{c}": {"hinge_cm": h, "axis": "local X", "closed_deg": 0.0, "tripped_deg": build["trip_deg"]}
                   for c, h in zip(("red", "yellow", "green", "blue"), m["hinges"])},
        "measured_cm": {"all_closed": m["all_closed"], "shell_tripped": m["shell_tripped"],
                        "beacon_top_h": m["beacon"]["h"][1], "cable_low_h": m["cable_low_h"]},
        "sweep_check": build["sweep_check"],
        "states": {"shell": "board.gd set_shell(look, i, open01): 0 closed .. 1 tripped (110 deg forward and down)",
                   "lamp": "set_on(look, i, on): green on, dark off; set_lamp(look, i, 0 dark | 1 yellow | 2 green)",
                   "beacon": "set_problem(look, on): the red dome and its light",
                   "core": "set_core(look, i, glow): the crystal core's glow, 1 full"},
        "placement": {s: {"at_godot": to_godot(s, 0.0, 0.0, 0.0), "yaw_deg": round(yaw(s), 3)} for s in SPOTS},
        "gltf_validator": {k: counts.get(k, 0) for k in ("numErrors", "numWarnings", "numInfos", "numHints")},
        "review": f"<raw>/ship/v4/board/{tag}/corridor/sheet.png",
    }
    (asset / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    raws = [f"ship/v4/board/ref/{name}" for name in REFS] + \
        [f"ship/v4/board/{tag}/breaker_board.glb", f"ship/v4/board/{tag}/breaker_board.blend"]
    today = datetime.date.today().isoformat()
    lines = [
        "# The ship's breaker board, the shells (art#263's stations).",
        f"# Built by tools/blender/board_run.py --tag {tag} --asset {asset.relative_to(ROOT).as_posix()}; a rebuild",
        "# changes the hashes below.",
        'id = "breaker_board"',
        'kind = "prop"',
        'slot = ""',
        "title = \"The ship's breaker board, the shells\"",
        ("notes = \"The breaker board on each corridor's front wall (breaker_e, breaker_w): an octagonal bronze board "
         f'{build["size_m"][0]:.2f} m wide on a graphite wall plate, four bays left to right red, yellow, green, blue, '
         'in each a glowing crystal core behind an enamel shell on a bottom hinge (four leaves shell_<colour>, their '
         'origin on the hinge axis, local X rotation 0 closed, 110 degrees tripped, each with its convex collider), a '
         'lamp over each bay, the red problem beacon on top, cyan strips and two cable loops into the wall; '
         f'{build["triangles"]:,} triangles, front +Z, origin on the wall face at the floor. States: '
         'export/board.gd (HANDOFF.md). From the sheet the engineer picked on 2026-10-25 and its drawing in cm '
         f'(prime-game-design {DESIGN_COMMIT}, ideas/ship-components/stations-final: board-variants/v3-shell-final.jpg, '
         'board-drawing/; copied to the raw folder; the AI concept used only as a reference), built from code in '
         'headless Blender (tools/blender/board_build.py from board_dims.toml): no part of the model was generated or '
         'downloaded."'),
        f'tools = ["blender {pins.BLENDER}", "prime-game-art board_build.py, board_run.py", '
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
    for rel in raws:
        lines += ["", "[[raw]]", f'file = "{rel}"', f'sha256 = "{sha256(RAW / rel)}"']
    (asset / "manifest.toml").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    sys.exit(main())
