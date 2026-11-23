"""The M8 clearing's ground looks (prime-game#1704): review shots only, no package.

Stages the art ship package (default v12, `<raw>/ship/v5/export/v12/`) into godot/import/ship_pkg/ the way
`lobby --export` does, imports headless, then runs godot/clearing/ground_looks.gd in the off-screen window
(`_godot.window()`): the game's clearing ("today": the greybox box, prime-game levels/clearing/ at b54c482a) and the
looks pad, soil and forest, each from the same four cameras at 1280 x 720. PNGs go to <out>/<look>/<view>.png, copies
to <review>/img/<look>_<view>.png, a 2 x 2 sheet per look to <review>/sheet_<look>.png, the GPU ms to
<out>/shots.json.

    $PYTHON_BIN tools/review/clearing_ground_looks.py [--looks today,pad] [--out DIR] [--review DIR]
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runner import common  # noqa: E402
from runner.commands import _godot, lobby  # noqa: E402

PACKAGE = "ship/v5/export/v12"
SHIP_AT = [116.0, 0.0, 72.0]          # clearing.tscn: Ground and Ship
FOV = 75.0                            # client/player: the player camera's field of view
EYE_H = 1.62                          # the player camera over the floor (client/dev/clearing_preview.gd)
SIZE = (1280, 720)
TIMEOUT = 900
# levels/estate/rooms/ship.tscn art_free
FREE_GAME = ["Environment", "Lights/@DirectionalLight3D@3", "Lights/@DirectionalLight3D@4", "Clearing"]
LOOKS = {
    "today": {"ground": "box", "free": FREE_GAME},
    "pad": {"ground": "pad", "free": FREE_GAME},
    "soil": {"ground": "soil", "free": FREE_GAME},
    "forest": {"ground": "none", "free": FREE_GAME[:3]},   # the package's own Clearing kept, the greybox box removed
}


def views() -> list[dict]:
    cx, _, cz = SHIP_AT
    a = math.radians(35.0)   # off the ramp's axis (the ramp points -z)
    close = [117.6, EYE_H, 56.2]
    return [
        # markers.tscn RoundPlayer01: the round-start view
        {"name": "round_start", "eye_h": EYE_H,
         "marker": "Transform3D(-0.127522, 0, -0.991836, 0, 1, 0, 0.991836, 0, -0.127522, 109, 0, 58.5)"},
        {"name": "spawn_wide", "eye": [cx, 1.7, 52.0], "target": [cx, 3.0, cz]},
        {"name": "three_quarter", "eye": [cx + 22.0 * math.sin(a), 6.0, cz - 22.0 * math.cos(a)], "target": [cx, 2.0, cz]},
        {"name": "ground_close", "eye": close,
         "target": [close[0], 0.0, close[2] + EYE_H / math.tan(math.radians(30.0))]},
        # the validator's round_start (prime-game b54c482a pass 2) matches RoundPlayer02's eye, not 01's
        {**DIAG[0], "name": "round_start_p02"},
    ]


# the validator's round_start framing against the other front-row markers (markers.tscn)
DIAG = [{"name": "diag_p02", "eye_h": EYE_H,
         "marker": "Transform3D(-0.177153, 0, -0.984183, 0, 1, 0, 0.984183, 0, -0.177153, 111, 0, 58.5)"},
        {"name": "diag_p03", "eye_h": EYE_H,
         "marker": "Transform3D(-0.287348, 0, -0.957826, 0, 1, 0, 0.957826, 0, -0.287348, 113, 0, 58.5)"}]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--looks", default=",".join(LOOKS))
    ap.add_argument("--out", type=Path, default=common.raw_dir() / "clearing" / "ground-looks")
    ap.add_argument("--review", type=Path, default=common.OUT / "review" / "clearing-ground")
    ap.add_argument("--diag", action="store_true", help="only the framing check: round_start from RoundPlayer02 and 03")
    args = ap.parse_args()
    args.out, args.review = args.out.resolve(), args.review.resolve()   # Godot runs in its project folder
    names = [n for n in args.looks.split(",") if n]
    scene = lobby.stage_package({"dir": PACKAGE})
    errors = [line for line in _godot.import_project() if "ERROR" in line]
    for line in errors[:10]:
        common.say(f"  import: {line}")
    req = {"ship": scene, "at": SHIP_AT, "fov": FOV, "size": list(SIZE), "views": DIAG if args.diag else views(),
           "looks": [{"name": n, **LOOKS[n]} for n in names], "sheets": args.review.as_posix()}
    path = common.OUT / "clearing-ground" / "request.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "shots.json").unlink(missing_ok=True)
    code, output = _godot.window(["--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s",
                                  "res://clearing/ground_looks.gd", "--", path.as_posix(), args.out.as_posix()],
                                 SIZE, TIMEOUT, log=common.OUT / "clearing-ground" / "godot.log")
    (common.OUT / "clearing-ground" / "godot.log").write_text(output, encoding="utf-8")
    for line in [ln for ln in output.splitlines() if "SCRIPT ERROR" in ln or "FAILED" in ln][:8]:
        common.say(f"  {line.strip()}")
    if code != 0 or not (args.out / "shots.json").is_file():
        common.bad(f"ground_looks.gd failed (exit code {code})")
        return 1
    shots = json.loads((args.out / "shots.json").read_text(encoding="utf-8"))
    img = args.review / "img"
    img.mkdir(parents=True, exist_ok=True)
    for look, per in shots.items():
        for view, info in per.items():
            shutil.copyfile(args.out / look / f"{view}.png", img / f"{look}_{view}.png")
            common.say(f"  {look}/{view}: GPU {info['gpu_ms']:.2f} ms, {info['draw_calls']} draw calls, "
                       f"{info['size'][0]}x{info['size'][1]}")
    common.ok(f"clearing ground looks: {sum(len(v) for v in shots.values())} shots in {args.out.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
