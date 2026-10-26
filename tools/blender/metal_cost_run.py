"""What the stations' shared bronze noise costs on the GPU (art#263, fix pass 2; option A shipped): the driver (plain
Python, outside Blender). Places the four stations' approved exports (assets/prop/*/export: the start console, a
crystal socket on each socket spot, a breaker board on each breaker spot, the crystal charger on renewer_e) in the
built ship at night, as their own drivers place them, and runs godot/ship/metal_cost.gd through the runner's
_godot.window() (off-screen, 1920x1080): per view the median GPU ms with the metal shader as shipped (the slope from
the noise's exact derivative), with dent and wave off, with one octave of the noise, with the slope as it shipped
before option A (the forward difference, metal_cost.gd FINITE), and with the view's station hidden; per console view
also the console alone before and after option A, which must match pixel for pixel. The views are the stations' own
(their drivers' view rows): a close view and the player's. Writes <out>/request.json, cost.json, cost.md (the table),
the variants' frames and the before/after strips.

    $PYTHON_BIN tools/blender/metal_cost_run.py [--out DIR] [--rounds 3] [--frames 120] [--pieces DIR]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from runner import common, ship_layout  # noqa: E402
from runner.commands import _godot  # noqa: E402
from runner.commands import ship as ship_cmd  # noqa: E402

import board_run  # noqa: E402  (beside this file: each station's placement and views)
import charger_run  # noqa: E402
import console_run  # noqa: E402
import socket_run  # noqa: E402

RAW = common.raw_dir()
EXPORT = ROOT / "assets" / "prop"
GLBS = {"start_console": EXPORT / "start_console" / "export" / "start_console.glb",
        "crystal_socket": EXPORT / "crystal_socket" / "export" / "crystal_socket.glb",
        "breaker_board": EXPORT / "breaker_board" / "export" / "breaker_board.glb",
        "crystal_charger": EXPORT / "crystal_charger" / "export" / "crystal_charger.glb"}
# per station the views from its own driver's rows: a close view (the station fills most of the frame), the player's
# view, and a near close-up where the bronze fills the frame (the worst case per pixel)
VIEWS = {"console": ("q34", "eye"),
         "socket": ("hero_charged", "eye", "back_pair", "frame_upper"),
         "board": ("on_q34", "eye", "close_seam_panel"),
         "charger": ("side", "eye", "button")}
TIMEOUT = 900


def rows() -> list:
    """[name, station, eye, look, fov] per view, the eye and look in Godot's world from the stations' drivers."""
    own = {"console": console_run.view_rows(),
           "socket": socket_run.hall_rows() + socket_run.view_rows(socket_run.CLOSE_VIEWS),
           "board": board_run.view_rows(),
           "charger": charger_run.view_rows()}
    out = []
    for station, names in VIEWS.items():
        by_name = {r[0]: r for r in own[station]}
        for n in names:
            r = by_name[n]
            out.append([f"{station}_{n}", station, r[2], r[3], r[4]])
    return out


def request(pieces: Path, spec: dict) -> tuple[dict, dict[str, Path]]:
    layout = ship_layout.load()
    req, staged = ship_cmd.built_request(layout, pieces)
    for pid, glb in GLBS.items():
        req["pieces"][pid] = f"res://import/{pid}.glb"
        staged[pid] = glb
    req["place"].append(["start_console", console_run.to_godot(0.0, 0.0, 0.0), console_run.YAW])
    for s in socket_run.SPOTS:
        req["place"].append(["crystal_socket", socket_run.to_godot(s, 0.0, 0.0, 0.0), socket_run.spot(s)[2]])
    for s in board_run.SPOTS:
        req["place"].append(["breaker_board", board_run.to_godot(s, 0.0, 0.0, 0.0), round(board_run.yaw(s), 3)])
    req["place"].append(["crystal_charger", charger_run.to_godot(0.0, 0.0, 0.0), charger_run.yaw_deg()])
    req.update({"mode": "shoot", "watchdog_s": float(TIMEOUT - 30), "nav_blink": False, "compare": [],
                "light": {**layout["light"], "lamps": [[*ship_cmd._g(l[:3]), *l[3:]] for l in layout["light"]["lamps"]]},
                "views": rows(), "rooms": ship_cmd.room_boxes(layout), "cost": spec})
    return req, staged


def table(cost: dict) -> str:
    lines = [f"GPU ms, median of {int(cost['spec']['rounds'])} rounds x {int(cost['spec']['frames'])} frames, "
             f"{cost['size'][0]}x{cost['size'][1]}, {cost['adapter']}; before = the forward-difference slope, "
             "shipped = option A's exact derivative", "",
             "| view | before | shipped | saves | dent = wave = 0 | noise | one octave | 2nd octave | station hidden | "
             "station | px mean vs shipped: flat / one oct. / before | console alone identical |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in cost["views"]:
        solo = "-"
        if "solo_identical" in r:
            solo = f"{'yes' if r['solo_identical'] else 'NO'} (max {r['solo_px_max']:.0f})"
        lines.append(f"| {r['view']} | {r['gpu_ms_finite']:.3f} | {r['gpu_ms_shipped']:.3f} | "
                     f"{r['analytic_saves_ms']:+.3f} | {r['gpu_ms_flat']:.3f} | {r['noise_ms']:+.3f} | "
                     f"{r['gpu_ms_one_octave']:.3f} | {r['octave2_ms']:+.3f} | {r['gpu_ms_hidden']:.3f} | "
                     f"{r['station_ms']:+.3f} | "
                     f"{r['px_mean_flat']:.2f} / {r['px_mean_one_octave']:.2f} / {r['px_mean_finite']:.2f} | {solo} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=RAW / "ship" / "v4" / "bronze-a" / "cost")
    ap.add_argument("--pieces", type=Path, default=RAW / ship_layout.load()["raw_dir"] / "pieces")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--frames", type=int, default=120)
    ap.add_argument("--settle", type=int, default=20)
    args = ap.parse_args()
    for pid, glb in GLBS.items():
        if not glb.is_file() or glb.read_bytes()[:4] != b"glTF":
            raise common.Failure(f"{glb} is missing or an LFS pointer (git lfs pull)")
    req, staged = request(args.pieces, {"rounds": args.rounds, "frames": args.frames, "settle": args.settle})
    errors = ship_cmd._stage(staged)
    for line in errors[:10]:
        print(f"  import: {line}")
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "request.json"
    path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
    (args.out / "cost.json").unlink(missing_ok=True)
    log = args.out / "godot.log"
    code, output = _godot.window(["--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s",
                                  "res://ship/metal_cost.gd", "--", path.as_posix(), args.out.as_posix()],
                                 ship_cmd.VIEW_SIZE, TIMEOUT, log=log)
    log.write_text(output, encoding="utf-8")
    if code != 0 or not (args.out / "cost.json").is_file():
        print("metal cost failed:\n" + "\n".join(output.splitlines()[-20:]))
        return code or 1
    cost = json.loads((args.out / "cost.json").read_text(encoding="utf-8"))
    md = table(cost)
    (args.out / "cost.md").write_text(md, encoding="utf-8", newline="\n")
    print(md, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
