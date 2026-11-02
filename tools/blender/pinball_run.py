"""The lobby's pinball machine (art #374): the driver (plain Python, outside Blender), as crystal_run.py.
1. pinball_build.py in headless Blender: pinball.glb (the cabinet with the TableMount, CloseUp and Display markers),
   pinball_table.glb (the table's art in the contract's frame), pinball.blend, build.json, features.json and the
   orthographic renders;
2. glTF-Validator on both GLBs;
3. pinball_drawing.py: the drawing (front, side, top in cm) on paper, over the model's orthographic renders and beside
   the concept, into drawing/;
4. the clearances in the hall (the east wall, its pilasters and door D2) from the build's bounds and the placement;
5. the shots in our hall (godot/pinball/shots.gd, which extends the lobby's godot/lobby/hall.gd: the hall, the ship
   and the light of `lobby --shoot`) in an off-screen window (_godot.window()): a 3/4 front, the side, the player's
   eye at the machine's spawn, the CloseUp camera, the backbox close-up, the hall around it, sheet.png with the concept
   beside, and the drawing's SVGs as PNGs;
6. the MP4 (10 s, 1280x720) from the CloseUp camera: the flippers at the contract's swing and speed, a ball on a
   scripted path; frames from the off-screen window, encoded by the ship's ship_video.py in headless Blender.
Everything goes under <raw>/lobby/pinball/<tag>/.

    $PYTHON_BIN tools/blender/pinball_run.py [--tag v1] [--no-build] [--no-shots] [--no-video]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from runner import blender, common, lobby_layout  # noqa: E402
from runner.commands import _export, _godot  # noqa: E402
from runner.commands import lobby as lobby_cmd  # noqa: E402

import pinball_drawing  # noqa: E402  (beside this file)

RAW = common.raw_dir()
BASE = RAW / "lobby" / "pinball"
CONCEPT = BASE / "ref" / "concept_p2.png"
DIMS = tomllib.loads((Path(__file__).with_name("pinball_dims.toml")).read_text(encoding="utf-8"))
SCRIPT = "res://pinball/shots.gd"
GLBS = ("pinball", "pinball_table")
VIDEO = {"size": [1280, 720], "fps": 30, "seconds": 10.0, "max_mb": 15.0}


def clearances(build: dict, layout: dict) -> dict:
    """The cabinet's footprint in the hall (m) and its gaps to the east wall, the east wall's pilasters and door D2."""
    o = [c / 100.0 for c in DIMS["placement"]["origin"]]
    b = build["cabinet"]["bounds_cm"]
    x0, x1 = o[0] + b["min"][0] / 100, o[0] + b["max"][0] / 100
    z0, z1 = o[2] + b["min"][2] / 100, o[2] + b["max"][2] / 100
    h = layout["hall"]
    out = {"footprint_x": [round(x0, 3), round(x1, 3)], "footprint_z": [round(z0, 3), round(z1, 3)],
           "east_wall": round(h["x1"] - x1, 3)}
    face = h["x1"] - h["pilaster_d"]
    near = [z for z in h["ribs"] if abs(z - (z0 + z1) / 2) < 6.0]
    out["pilasters"] = {f"z {z:g}": round(max(face - x1, 0.0) if z - h["pilaster_w"] / 2 < z1 and
                                          z + h["pilaster_w"] / 2 > z0 else
                                          ((face - x1) ** 2 + min(abs(z - h["pilaster_w"] / 2 - z1),
                                                                  abs(z0 - z - h["pilaster_w"] / 2)) ** 2) ** 0.5, 3)
                        for z in near}
    for d in layout["door"]["doors"]:
        if d[1] == "E":
            out[f"door {d[0]} (z {d[2] - layout['door']['w'] / 2:g}..{d[2] + layout['door']['w'] / 2:g})"] = \
                round(h["x1"] - x1, 3)
    spot = [c / 100.0 for c in DIMS["placement"]["spot"]]
    out["spot_to_front"] = round(z0 - spot[2], 3)
    return out


def request(layout: dict, mode: str, out: Path) -> tuple[dict, dict]:
    place = lobby_cmd.ship_scene(layout)[0]
    pieces = lobby_cmd.raw(layout) / "pieces"
    req, staged, _want = lobby_cmd.scene_request(layout, pieces, place, lobby_layout.ship_report(layout))
    staged.update({f"pinball_{g}": out / f"{g}.glb" for g in GLBS})
    req["pieces"]["pinball"] = "res://import/pinball_pinball.glb"
    o = [c / 100.0 for c in DIMS["placement"]["origin"]]
    req["place"].append(["pinball", o, 0.0])
    req.update({"mode": mode, "watchdog_s": 540, "background": layout["review"]["background"], "top": layout["review"]["top"],
                "look": lobby_cmd.look_request(layout, layout["look"]["scheme"])})
    if "earth" in layout:
        req["earth"] = lobby_cmd.earth_request(layout, layout["earth"]["variant"])["earth"]
    if "light" in layout:
        req["light"] = lobby_cmd.light_request(layout, layout["light"]["mood"])["light"]
    spot = [c / 100.0 for c in DIMS["placement"]["spot"]]
    k = DIMS["contract"]
    req["pinball"] = {
        "table": "res://import/pinball_pinball_table.glb", "concept": CONCEPT.as_posix(), "spot": spot,
        "origin": o, "fov": DIMS["markers"]["closeup_fov"],
        "lines": ["BEST 48 200   ORBIT-7", "SCORE 12 450", "BALL 2 / 3"],
        "swing_deg": k["flipper_swing_deg"], "speed_deg_s": k["flipper_speed_deg_s"], "rest_deg": k["flipper_rest_deg"],
        "ball_r": k["ball_r"] / 100.0,
        "svgs": [str(p) for p in sorted((out / "drawing").glob("drawing*.svg"))],
        "video": VIDEO,
    }
    return req, staged


def godot_run(layout: dict, mode: str, out: Path, folder: Path, size: tuple[int, int]) -> tuple[int, str]:
    req, staged = request(layout, mode, out)
    errors = lobby_cmd._stage(staged)
    for line in errors[:5]:
        print(f"  import: {line}")
    folder.mkdir(parents=True, exist_ok=True)
    path = common.OUT / "pinball" / f"{mode}_request.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
    code, output = _godot.window(["--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s", SCRIPT, "--",
                                  path.as_posix(), folder.as_posix()], size, 600, log=out / f"godot_{mode}.log")
    (out / f"godot_{mode}.log").write_text(output, encoding="utf-8")
    print(*[x for x in output.splitlines() if x.startswith(("PINBALL", "LOBBY")) or "SCRIPT ERROR" in x][:20], sep="\n")
    return code, output


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="v1", help="the output folder under <raw>/lobby/pinball/")
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--no-shots", action="store_true")
    ap.add_argument("--no-video", action="store_true")
    ap.add_argument("--px", type=int, default=4, help="the orthographic renders' pixels per cm")
    args = ap.parse_args()
    out = BASE / args.tag
    out.mkdir(parents=True, exist_ok=True)
    if not args.no_build:
        r = blender.run_script("pinball_build.py", ["--out", str(out), "--px", str(args.px)], timeout=900)
        print(*[x for x in (r.stdout or "").splitlines() if x.startswith("PINBALL_BUILD")], sep="\n", flush=True)
    ok = True
    for g in GLBS:
        passed, text = _export.verdict(_export.validate(out / f"{g}.glb", out / f"{g}.validator.json"))
        print(f"validator {g}.glb: {text}", flush=True)
        ok = ok and passed
    sys.argv[1:] = [str(out)]
    pinball_drawing.main()
    build = json.loads((out / "build.json").read_text(encoding="utf-8"))
    layout = lobby_layout.load()
    cl = clearances(build, layout)
    (out / "clearances.json").write_text(json.dumps(cl, indent=1) + "\n", encoding="utf-8")
    print(f"clearances (m): {cl}", flush=True)
    code = 0
    if not args.no_shots:
        code, _ = godot_run(layout, "shoot", out, out / "shots", lobby_cmd.VIEW_SIZE)
        print(f"godot shots: exit {code} {(out / 'shots').as_posix()}", flush=True)
    if not args.no_video and code == 0:
        work = out / "video"
        shutil.rmtree(work / "frames", ignore_errors=True)
        code, _ = godot_run(layout, "video", out, work, tuple(VIDEO["size"]))
        if code == 0:
            clip = out / "pinball_closeup.mp4"
            clip.unlink(missing_ok=True)
            r = blender.run_script(lobby_cmd.VIDEO_SCRIPT, ["--frames", str(work / "frames"), "--out", str(clip),
                                                            "--fps", str(VIDEO["fps"]), "--max-mb",
                                                            str(VIDEO["max_mb"])], timeout=900)
            print(*[x for x in (r.stdout or "").splitlines() if x.startswith("ENCODED")], sep="\n", flush=True)
            for f in sorted((work / "frames").glob("*.png")):   # keep the key frames for the review, drop the rest
                if int(f.stem) % 30:
                    f.unlink()
        print(f"godot video: exit {code}", flush=True)
    return 0 if ok and code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
