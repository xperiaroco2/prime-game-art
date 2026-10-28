"""The ship's crystal charger (art#263's stations): the driver (plain Python, outside Blender).
1. the references: the engineer's pick (the charger on long legs) and its drawing (prime-game-design
   ideas/ship-components/stations-final/: charger-legs.jpg, charger-drawing/drawing.js, drawing.html,
   front-ortho.jpg, top-ortho.jpg) copied into <raw>/ship/v4/charger/ref-legs/ when missing;
2. charger_build.py in headless Blender: the model from code with the built energy crystal on its anchor
   (assets/prop/energy_crystal/export/energy_crystal.glb), the GLB (the plain-PBR fallback), the .blend with the
   look materials, build.json (with the clearance checks), features.json, the Blender review renders;
3. glTF-Validator on the GLB;
4. charger_drawing.py: the drawing (front, side, top in cm) over the model's orthographic renders, into
   <tag>/drawing/;
5. the Godot shots in the east lens room at night in an off-screen window: godot/charger/room.gd (ship.gd's shoot
   mode with every built ship piece, the charger on renewer_e and the crystal on its anchor) through the runner's
   _godot.window(), into <tag>/room/;
6. godot/charger/sheet.gd: the sheets (compare_sheet.png beside the approved sheet, room_sheet.png, closeups.png)
   and the charger's GPU cost, into <tag>/sheets/.
Everything goes under <raw>/ship/v4/charger/<tag>/. --asset DIR writes the asset folder
(assets/prop/crystal_charger).

    $PYTHON_BIN tools/blender/charger_run.py [--tag build] [--no-build] [--no-shots] [--res 900] [--samples 64]
        [--asset assets/prop/crystal_charger] [--pieces <raw>/<ship.toml raw_dir>/pieces]
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import shutil
import tomllib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from runner import blender, common, pins, ship_layout  # noqa: E402
from runner.commands import _export, _godot  # noqa: E402
from runner.commands import ship as ship_cmd  # noqa: E402

import charger_drawing  # noqa: E402  (beside this file)

RAW = common.raw_dir()
BASE = RAW / "ship" / "v4" / "charger"
REF = BASE / "ref-legs"  # the legs pick's references (ref/ keeps the first drawing's: raw files are not overwritten)
DESIGN = Path("D:/prime-game-design/ideas/ship-components/stations-final")
REFS = {"charger-legs.jpg": DESIGN / "charger-legs.jpg", "drawing.js": DESIGN / "charger-drawing" / "drawing.js",
        "drawing.html": DESIGN / "charger-drawing" / "drawing.html",
        "front-ortho.jpg": DESIGN / "charger-drawing" / "front-ortho.jpg",
        "top-ortho.jpg": DESIGN / "charger-drawing" / "top-ortho.jpg"}
# lens room C (art#263, 2026-10-28): the pedestal in the wall's alcove, from the lens room's drawing and concept
REF_LENS = BASE / "ref-lens"
DESIGN_LENS = Path("D:/prime-game-design/ideas/ship-components/lens-room")
REFS_LENS = {"c_lounge.jpg": DESIGN_LENS / "c_lounge.jpg", "drawing.js": DESIGN_LENS / "drawing" / "drawing.js"}
DIMS = tomllib.loads((Path(__file__).with_name("charger_dims.toml")).read_text(encoding="utf-8"))
AX = DIMS["frame"]["axis_d"]
CRYSTAL = ROOT / "assets" / "prop" / "energy_crystal" / "export" / "energy_crystal.glb"
METAL = ROOT / "godot" / "console" / "console_metal.gdshader"  # shared with the console, not forked
HDRI = RAW / "env" / "polyhaven" / "studio_small_09" / "studio_small_09_2k.hdr"  # CC0, sources/polyhaven_hdris_2k.toml
SPOT = "renewer_e"
# fix1 (art#263): the layout's raw_dir pieces, the current build (ship/v5/pieces, deck at floor_h 1.2; the same bytes
# as the vents' b5b build the station steps shot on). The deck check below still refuses pieces built before the raise
PIECES = RAW / ship_layout.load()["raw_dir"] / "pieces"
# the room shots: name, yaw from the front, elevation (deg), target (u, d, h cm), distance (m), fov, state
CHARGING = {"charger": "charging", "ring": 35.0, "rise": 1.0, "carrier": 20.0, "crystal": True, "charge": 0.5}
IDLE = {"charger": "idle", "crystal": False}
ROOM_VIEWS = [
    ("q34_idle", -32.0, 12.0, (0.0, AX, 78.0), 3.0, 46.0, IDLE),
    ("q34_charging", -32.0, 12.0, (0.0, AX, 78.0), 3.0, 46.0, CHARGING),
    ("q34_charged", -32.0, 12.0, (0.0, AX, 78.0), 3.0, 46.0, {"charger": "charged", "crystal": True, "charge": 1.0}),
    ("front", 0.0, 4.0, (0.0, AX, 72.0), 3.0, 44.0, IDLE),
    ("side", -62.0, 8.0, (0.0, AX, 72.0), 1.6, 64.0, IDLE),
    ("top_down", 0.0, 35.0, (0.0, AX + 10.0, 85.0), 1.3, 64.0, IDLE),
    ("deck_charging", -20.0, 40.0, (0.0, AX, 108.0), 1.1, 44.0, CHARGING),
    ("wall_back", -62.0, 14.0, (-40.0, 18.0, 45.0), 1.0, 60.0, IDLE),
    ("low", -28.0, 3.0, (0.0, AX, 40.0), 1.9, 50.0, IDLE),
    ("button", -15.0, 6.0, (0.0, 68.0, 76.0), 0.6, 34.0, IDLE),
]
TURN = [0.0, 30.0, 60.0, 90.0, 120.0, 150.0]  # the ring's full-turn check from above (it is symmetric every 180)
# a player at the button (the capsule's centre 1.04 + 0.4 m out, eyes at 1.6 m), and the pass behind them: from the
# room's far side, low, back toward the charger over the floor a player crosses (pass_m 1.6 behind the capsule)
EYE = ("eye", (-20.0, 150.0, 160.0), (0.0, AX, 100.0), 75.0)
PASS = ("pass", (130.0, 360.0, 150.0), (-10.0, 150.0, 40.0), 70.0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="build", help="the output folder under <raw>/ship/v4/charger/")
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--no-shots", action="store_true")
    ap.add_argument("--res", type=int, default=900)
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--asset", type=Path, help="write the asset folder here from this build")
    ap.add_argument("--pieces", type=Path, default=PIECES, help="the built ship pieces for the lens room shots")
    args = ap.parse_args()
    if args.asset and args.no_shots:
        ap.error("--asset needs this run's shots (report.json takes their GPU cost)")
    copy_refs()
    out = BASE / args.tag
    renders = out / "renders"
    if not args.no_build:
        r = blender.run_script("charger_build.py", ["--out", str(out), "--crystal", str(CRYSTAL), "--render",
                                                    str(renders), "--res", str(args.res), "--samples",
                                                    str(args.samples), "--hdri", str(HDRI)], timeout=1800)
        lines = [x for x in (r.stdout or "").splitlines() if x.startswith("CHARGER")]
        print(*lines, sep="\n", flush=True)
        if not lines or r.returncode != 0:
            print("\n".join(((r.stdout or "") + (r.stderr or "")).splitlines()[-30:]))
            return 1
    sys.argv[1:] = [str(out)]
    charger_drawing.main()
    glb = out / "crystal_charger.glb"
    report = _export.validate(glb, out / "crystal_charger.validator.json")
    ok, text = _export.verdict(report)
    print(f"validator crystal_charger.glb: {text}", flush=True)
    code = 0
    if not args.no_shots:
        code = room_shots(glb, out / "room", args.pieces)
        if code == 0:
            sheets = out / "sheets"
            sheets.mkdir(exist_ok=True)
            code, output = _godot.window(["--path", str(_godot.PROJECT), "-s", "res://charger/sheet.gd", "--",
                                          "res://import/crystal_charger.glb", str(sheets), str(renders),
                                          str(out / "room"), str(REF_LENS / "c_lounge.jpg")], (1280, 720), 300,
                                         log=out / "godot_sheet.log")
            print(*[x for x in output.splitlines() if x.startswith("CHARGER ")], sep="\n")
            print(f"godot sheets: exit {code} {sheets}", flush=True)
    if args.asset and ok and code == 0:
        write_asset(args.asset, out, args.tag, report)
        print(f"asset: {args.asset}", flush=True)
    return 0 if ok and code == 0 else 1


def copy_refs() -> None:
    for folder, refs in ((REF, REFS), (REF_LENS, REFS_LENS)):
        folder.mkdir(parents=True, exist_ok=True)
        for name, src in refs.items():
            if not (folder / name).is_file():
                if not src.is_file():
                    raise common.Failure(f"no reference {src} (prime-game-design beside this checkout, its PR branch)")
                shutil.copyfile(src, folder / name)


def spot() -> dict:
    return next(s for s in ship_layout.load()["stations"]["spot"] if s["id"] == SPOT)


def yaw_deg() -> float:
    """The charger's front (glTF +Z) along the spot's normal (into the room)."""
    n = spot()["normal"]
    return math.degrees(math.atan2(n[0], n[1]))


def to_godot(u: float, d: float, h: float) -> list[float]:
    """The charger's frame (cm: u across, d out of the wall, h up) -> Godot's world in the ship on its spot."""
    floor = ship_layout.load()["deck"]["floor_h"]
    a = math.radians(yaw_deg())
    x, z = u * 0.01, d * 0.01
    sx, sy = spot()["at"]
    return [round(x * math.cos(a) + z * math.sin(a) + sx, 4), round(floor + h * 0.01, 4),
            round(-x * math.sin(a) + z * math.cos(a) + sy, 4)]


def view_rows() -> list:
    rows = []
    for name, yaw, elev, (u, d, h), dist, fov, state in ROOM_VIEWS:
        y, e = math.radians(yaw), math.radians(elev)
        eye = (u + math.sin(y) * math.cos(e) * dist * 100.0, d + math.cos(y) * math.cos(e) * dist * 100.0,
               h + math.sin(e) * dist * 100.0)
        rows.append([name, "", to_godot(*eye), to_godot(u, d, h), fov, state])
    for k in TURN:  # the ring's full turn, straight down on the deck
        rows.append([f"turn_{int(k):03d}", "", to_godot(0.0, AX + 110.0, 168.0), to_godot(0.0, AX, 100.0), 34.0,
                     {"charger": "charging", "ring": k, "rise": 0.0, "crystal": False}])
    for name, eye, look, fov in (EYE, PASS):
        rows.append([name, "", to_godot(*eye), to_godot(*look), fov, IDLE])
    return rows


def _node_matrix(node: dict) -> list[list[float]]:
    """A glTF node's local matrix (row-major 4x4) from its matrix or its translation, rotation and scale."""
    if "matrix" in node:
        m = node["matrix"]  # column-major
        return [[m[c * 4 + r] for c in range(4)] for r in range(4)]
    tx, ty, tz = node.get("translation", (0.0, 0.0, 0.0))
    x, y, z, w = node.get("rotation", (0.0, 0.0, 0.0, 1.0))
    sx, sy, sz = node.get("scale", (1.0, 1.0, 1.0))
    rot = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
           [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
           [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
    return [[rot[r][0] * sx, rot[r][1] * sy, rot[r][2] * sz, (tx, ty, tz)[r]] for r in range(3)] + [[0.0, 0.0, 0.0, 1.0]]


def _mul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[sum(a[r][k] * b[k][c] for k in range(4)) for c in range(4)] for r in range(4)]


def deck_top(glb: Path) -> float:
    """A built piece's highest point (metres, glTF +Y up): each mesh's POSITION bounds (the accessors' min and max in
    the GLB's JSON chunk) through its node's world transform (fix1: node transforms were ignored)."""
    data = glb.read_bytes()
    size = int.from_bytes(data[12:16], "little")
    doc = json.loads(data[20:20 + size])
    acc, nodes = doc["accessors"], doc["nodes"]
    top = -math.inf
    ident = [[float(r == c) for c in range(4)] for r in range(4)]
    stack = [(i, ident) for i in doc["scenes"][doc.get("scene", 0)]["nodes"]]
    while stack:
        i, parent = stack.pop()
        world = _mul(parent, _node_matrix(nodes[i]))
        if "mesh" in nodes[i]:
            for prim in doc["meshes"][nodes[i]["mesh"]]["primitives"]:
                a = acc[prim["attributes"]["POSITION"]]
                for cx in (a["min"][0], a["max"][0]):
                    for cy in (a["min"][1], a["max"][1]):
                        for cz in (a["min"][2], a["max"][2]):
                            top = max(top, world[1][0] * cx + world[1][1] * cy + world[1][2] * cz + world[1][3])
        stack.extend((c, world) for c in nodes[i].get("children", ()))
    return top


def room_shots(glb: Path, folder: Path, pieces: Path) -> int:
    layout = ship_layout.load()
    deck = deck_top(pieces / "tip_floor_rim.glb")  # fix1: the lens room's own floor ring (was the corridor's grate)
    if abs(deck - layout["deck"]["floor_h"]) > 0.05:
        raise common.Failure(f"the pieces in {pieces} have their lens room deck at {deck:.3f} m, not floor_h "
                             f"{layout['deck']['floor_h']} (built before the raise?): pass --pieces")
    print(f"pieces: {pieces} (lens room deck {deck:.3f} m)", flush=True)
    req, staged = ship_cmd.built_request(layout, pieces)
    req["pieces"]["crystal_charger"] = "res://import/crystal_charger.glb"
    req["pieces"]["energy_crystal"] = "res://import/energy_crystal.glb"
    req["place"].append(["crystal_charger", to_godot(0.0, 0.0, 0.0), yaw_deg()])
    req["place"].append(["energy_crystal", to_godot(0.0, AX, DIMS["slot"]["tip"]), yaw_deg()])
    staged["crystal_charger"] = glb
    staged["energy_crystal"] = CRYSTAL
    req.update({"mode": "shoot", "watchdog_s": 280.0, "nav_blink": False, "compare": [],
                "light": {**layout["light"], "lamps": [[*ship_cmd._g(l[:3]), *l[3:]] for l in layout["light"]["lamps"]]},
                "views": view_rows(), "rooms": ship_cmd.room_boxes(layout)})
    errors = ship_cmd._stage(staged)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "request.json"
    path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
    (folder / "shots.json").unlink(missing_ok=True)
    code, output = _godot.window(["--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s",
                                  "res://charger/room.gd", "--", path.as_posix(), folder.as_posix()],
                                 ship_cmd.VIEW_SIZE, ship_cmd.GODOT_TIMEOUT, log=folder.parent / "godot_room.log")
    (folder.parent / "godot_room.log").write_text(output, encoding="utf-8")
    print(*[x for x in output.splitlines() if x.startswith(("CHARGER", "SHIP look"))], sep="\n")
    for line in errors[:10]:
        print(f"  import: {line}")
    if code != 0 or not (folder / "shots.json").is_file():
        print("room shots failed:\n" + "\n".join(output.splitlines()[-20:]))
        return code or 1
    result = json.loads((folder / "shots.json").read_text(encoding="utf-8"))
    print(f"room shots: {len(result['shots'])} in {folder}", flush=True)
    return 0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exported_look() -> str:
    """charger.gd as the game keeps it: the console's metal beside it (one shared file, not a fork)."""
    src = (ROOT / "godot" / "charger" / "charger.gd").read_text(encoding="utf-8")
    return src.replace('preload("res://console/console_metal.gdshader")', 'preload("console_metal.gdshader")')


def write_asset(asset: Path, out: Path, tag: str, validator: dict) -> None:
    asset = asset if asset.is_absolute() else ROOT / asset
    (asset / "export").mkdir(parents=True, exist_ok=True)
    (asset / "source").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(out / "crystal_charger.glb", asset / "export" / "crystal_charger.glb")
    shutil.copyfile(out / "crystal_charger.blend", asset / "source" / "crystal_charger.blend")
    shutil.copyfile(METAL, asset / "export" / "console_metal.gdshader")
    (asset / "export" / "charger.gd").write_text(exported_look(), encoding="utf-8", newline="\n")
    build = json.loads((out / "build.json").read_text(encoding="utf-8"))
    cost = json.loads((out / "sheets" / "cost.json").read_text(encoding="utf-8"))
    counts = validator.get("issues", {})
    report = {
        "asset": "crystal_charger",
        "built_by": f"tools/blender/charger_run.py --tag {tag} --asset {asset.relative_to(ROOT).as_posix()}",
        "mesh": {"triangles": build["triangles"],
                 "by_object": {k: {"triangles": build[k]["triangles"], "by_material": build[k]["by_material"],
                                   "pivot_cm": build[k]["pivot_cm"], "open_edges": build[k]["open_edges"]}
                               for k in ("body", "carrier", "ring", "button")},
                 "size_cm": build["size_cm"], "front": "+Z (out of the wall, along the spot's normal)",
                 "origin": "on the floor at the wall's face under the crystal's axis (the spot's `at`)"},
        "anchor_cm": build["anchor_cm"],
        "colliders": build["colliders"],
        "checks": build["checks"],
        "states": {"idle": "charger.gd set_state(look, \"idle\"): carrier down, ring still, lights at rest",
                   "charging": "set_state(look, \"charging\"); the game drives set_carrier(look, rise01, angle) and "
                               "set_ring(look, angle) and its lightning",
                   "charged": "set_state(look, \"charged\"): carrier down, the cyan lights full"},
        "placement": f"layouts/ship/ship.toml [[stations.spot]] renewer_e, renewer_w: origin at (at.x, floor_h, at.y), "
                     "rotation.y = atan2(normal.x, normal.y)",
        "gltf_validator": {k: counts.get(k, 0) for k in ("numErrors", "numWarnings", "numInfos", "numHints")},
        "godot_cost": cost,
        "review": f"<raw>/ship/v4/charger/{tag}/sheets/",
    }
    (asset / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    raws = [f"ship/v4/charger/{REF.name}/{name}" for name in REFS] + \
        [f"ship/v4/charger/{REF_LENS.name}/{name}" for name in REFS_LENS] + \
        [f"ship/v4/charger/{tag}/crystal_charger.glb", f"ship/v4/charger/{tag}/crystal_charger.blend"]
    today = datetime.date.today().isoformat()
    lines = [
        "# The ship's crystal charger (art#263's stations).",
        f"# Built by tools/blender/charger_run.py --tag {tag} --asset {asset.relative_to(ROOT).as_posix()}; a rebuild",
        "# changes the hashes below.",
        'id = "crystal_charger"',
        'kind = "prop"',
        'slot = ""',
        "title = \"The ship's crystal charger\"",
        ("notes = \"The crystal charger, one in each lens room's alcove on the aft wall (renewer_e, renewer_w): a "
         "faceted pedestal (lens room C, 2026-10-28: the back u +-44 on the alcove's back panel at d 10, chamfers to "
         "the front face u +-22 at d 68, a graphite plinth h 0..10, bronze plates on a graphite core, a deck slab "
         "h 86..99.1 overhanging it), the crystal's axis 38 cm out, the slot at 95.7 cm, the fixed outer prongs to "
         "139.7 cm, the start button at 75.9 cm; leaves: the carrier cup under the crystal (rises 6 cm, spins; "
         "crystal_anchor), the track ring with the inner prongs (spins), the button (presses 1 cm). "
         f"{build['triangles']:,} triangles, front +Z, origin on the floor at the spot's vertex. The head from the "
         "engineer's pick of 2026-10-25 and its drawing in cm (prime-game-design commit a53ce6f, "
         "ideas/ship-components/stations-final: charger-legs.jpg, an AI concept used only as a reference, and "
         "charger-drawing/), the pedestal from the lens room's drawing (prime-game-design commit 7f335c2, "
         "ideas/ship-components/lens-room: c_lounge.jpg, an AI concept used only as a reference, and drawing/); "
         "copied to the raw folder. Built from code in headless Blender (tools/blender/charger_build.py from "
         "charger_dims.toml): no part of the model was generated or downloaded. Approval: pending; the new "
         "pedestal waits for the engineer's look yes (art#263).\""),
        f'tools = ["blender {pins.BLENDER}", "prime-game-art charger_build.py, charger_run.py", '
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
