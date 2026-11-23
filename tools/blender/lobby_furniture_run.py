"""The lobby's bar, mirror and match console (art #389, #390, #391): the driver (plain Python, outside Blender), as
pinball_run.py.
1. lobby_furniture_build.py in headless Blender per piece: <piece>.glb and <piece>.json into <out>/<piece>/;
2. glTF-Validator on each GLB;
3. the clearances in the hall: each piece's footprint (its bounds turned and placed by its spec's [placement]) against
   the hall's walls, the side walls' pilasters and the doors' openings (clearances.json);
4. the shots in our hall (godot/lobby_furniture/shots.gd, which extends the lobby's hall.gd) in an off-screen window
   (_godot.window()): per piece a 3/4 view, the front, the player's eye and close-ups, and a sheet with the concept.
Everything goes under <raw>/lobby/furniture/<tag>/.

    $PYTHON_BIN tools/blender/lobby_furniture_run.py [--tag v1] [--only bar,mirror] [--no-build] [--no-shots]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from runner import blender, common, lobby_layout  # noqa: E402
from runner.commands import _export, _godot  # noqa: E402
from runner.commands import lobby as lobby_cmd  # noqa: E402

RAW = common.raw_dir()
BASE = RAW / "lobby" / "furniture"
CONCEPTS = RAW / "2026-11-22-lobby-bar-mirror-console-concepts"
PIECES = {"bar": ("bar_dims.toml", "bar2_galley"), "mirror": ("mirror_dims.toml", "mir3_fins"),
          "match_console": ("match_console_dims.toml", "con2_monolith"), "mug": ("mug_dims.toml", "mug3_stein")}
CONCEPT_DIRS = {"mug": RAW / "2026-11-23-lobby-mug-concepts"}   # the others: CONCEPTS
ON_BAR = {"mug"}   # placed on the bar's top (their spec's [placement] on_bar, in the bar's frame), no floor clearances
SCRIPT = "res://lobby_furniture/shots.gd"
PLINTH = 0.2   # a pilaster's plinth reaches 0.1 m beyond its shaft either side and out (measured on walls.glb, v20)


def dims(piece: str) -> dict:
    return tomllib.loads((Path(__file__).with_name(PIECES[piece][0])).read_text(encoding="utf-8"))


def placement(piece: str) -> tuple[list, float]:
    """The piece's origin (cm, the hall's frame) and yaw (degrees): its spec's, or on the bar's top."""
    pl = dims(piece)["placement"]
    if piece in ON_BAR:
        return [c * 100.0 for c in to_hall("bar", pl["on_bar"])], pl["yaw_deg"]
    return pl["origin"], pl["yaw_deg"]


def to_hall(piece: str, p) -> list[float]:
    """A point (cm, the piece's frame) in the hall's frame (m)."""
    o, yaw = placement(piece)
    a = math.radians(yaw)
    x, y, z = p
    hx = x * math.cos(a) + z * math.sin(a)
    hz = -x * math.sin(a) + z * math.cos(a)
    return [round((o[0] + hx) / 100.0, 4), round((o[1] + y) / 100.0, 4), round((o[2] + hz) / 100.0, 4)]


def footprint(piece: str, bounds: dict) -> tuple[list, list]:
    lo, hi = bounds["min"], bounds["max"]
    pts = [to_hall(piece, (x, 0.0, z)) for x in (lo[0], hi[0]) for z in (lo[2], hi[2])]
    return [min(p[0] for p in pts), max(p[0] for p in pts)], [min(p[2] for p in pts), max(p[2] for p in pts)]


def clearances(piece: str, bounds: dict, layout: dict) -> dict:
    """The gaps (m, negative: an overlap) from the piece's footprint to the walls, the side walls' pilasters (from the
    walls' faces out to pilaster_d, pilaster_w wide at each rib), the doors' openings (side doors: 1 m out from the
    wall) and the ship's footprint."""
    h = layout["hall"]
    (x0, x1), (z0, z1) = footprint(piece, bounds)
    out = {"footprint_x": [round(x0, 3), round(x1, 3)], "footprint_z": [round(z0, 3), round(z1, 3)],
           "west_wall": round(x0 - h["x0"], 3), "east_wall": round(h["x1"] - x1, 3), "south_wall": round(h["zS"] - z1, 3)}

    def gap(bx, bz) -> float:   # the gap between the footprint and a box (negative inside)
        dx = max(bx[0] - x1, x0 - bx[1])
        dz = max(bz[0] - z1, z0 - bz[1])
        return round(max(dx, dz) if dx < 0 or dz < 0 else math.hypot(dx, dz), 3)

    pw, pd = h["pilaster_w"] + PLINTH, h["pilaster_d"] + PLINTH / 2   # the pilasters with their plinths
    pil = [gap((h["x0"], h["x0"] + pd), (r - pw / 2, r + pw / 2)) for r in h["ribs"]]
    pil += [gap((h["x1"] - pd, h["x1"]), (r - pw / 2, r + pw / 2)) for r in h["ribs"]]
    out["pilasters"] = min(pil)
    dw = layout["door"]["w"]
    doors = []
    for _id, wall, at in layout["door"]["doors"]:
        if wall == "W":
            doors.append(gap((h["x0"], h["x0"] + 1.0), (at - dw / 2, at + dw / 2)))
        elif wall == "E":
            doors.append(gap((h["x1"] - 1.0, h["x1"]), (at - dw / 2, at + dw / 2)))
        else:
            doors.append(gap((at - dw / 2, at + dw / 2), (h["zN"], h["zN"] + 1.0)))
    out["doors"] = min(doors)
    return out


def views(piece: str, b: dict) -> list:
    """Per piece: [name, title, eye, target, fov] in the hall's frame."""
    lo, hi = b["min"], b["max"]
    cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    w = hi[0] - lo[0]
    T = lambda p: to_hall(piece, p)   # noqa: E731
    if piece == "bar":
        k = dims("bar")["tap"]
        tap = (0.0, 110.0 + 20.0, k["at_z"])
        return [["bar_q34", "the bar, 3/4 front (the concept's side)", T((-380, 165, 420)), T((-20, 70, 0)), 45.0],
                ["bar_front", "the bar from the hall", T((0, 150, 330)), T((0, 70, 0)), 75.0],
                ["bar_eye", "the player's eye at the tap (1.65 m)", T((0, 165, 150)), T((0, 100, 0)), 75.0],
                ["bar_tap", "the tap close up", T((45, 150, 110)), T(tap), 35.0],
                ["bar_end", "an end and the plinth's glow", T((380, 60, 160)), T((260, 50, 20)), 40.0],
                ["bar_hall", "in the hall by the west wall, from its south end", T((-760, 260, 300)), T((0, 60, 0)), 55.0]]
    if piece == "mirror":
        return [["mirror_q34", "the mirror, 3/4 (the concept's side)", T((-260, 165, 420)), T((0, 125, 0)), 50.0],
                ["mirror_front", "the mirror from the players' places", T((0, 165, 520)), T((0, 125, 0)), 50.0],
                ["mirror_eye", "a player's eye at MirrorPlace2 (1.65 m)", T((0, 165, 60)), T((0, 150, 0)), 75.0],
                ["mirror_fins", "the left fins close up", T((-90, 120, 150)), T((-135, 110, 6)), 40.0],
                ["mirror_tips", "the fins' steel tips", T((90, 220, 120)), T((130, 235, 6)), 35.0],
                ["mirror_hall", "on the west wall, between the pilaster and the corner", T((250, 380, 1100)), T((0, 120, 0)), 55.0]]
    if piece == "mug":   # close views (cm, the mug's frame: the holder's side +z, the handle +x on its right); the
        # empty mug 25 cm to its left
        return [["mug_q34", "the mug, 3/4 (the concept's side: the handle on the right)", T((-22, 28, 40)), T((1.5, 8.5, 0)), 30.0],
                ["mug_front", "from the holder's side", T((0, 12, 55)), T((1.5, 8.5, 0)), 25.0],
                ["mug_handle", "the handle's side", T((60, 14, 4)), T((2.5, 8.5, 0)), 25.0],
                ["mug_top", "the head from above", T((4, 55, 20)), T((0, 15, 0)), 25.0],
                ["mug_pair", "full and empty (the Beer node hidden)", T((-14, 32, 62)), T((-12, 8, 0)), 35.0],
                ["mug_bar", "on the bar by the tap, from the player's eye", T((-60, 55, 130)), T((-30, 5, 0)), 55.0]]
    s = dims("match_console")["screen"]
    return [["con_q34", "the console, 3/4 front", T((150, 165, 260)), T((0, 90, 0)), 45.0],
            ["con_front", "the console from the front", T((0, 120, 330)), T((0, 85, 0)), 45.0],
            ["con_eye", "the player's eye at 1 m (1.65 m)", T((0, 165, 100)), T((0, s["centre_y"], 15)), 75.0],
            ["con_screen", "the screen's frame and line", T((50, 130, 80)), T((40, 125, 15)), 35.0],
            ["con_base", "the base and its ring", T((110, 60, 140)), T((40, 10, 30)), 40.0],
            ["con_hall", "in the hall behind the spawns", T((400, 400, 900)), T((0, 80, 0)), 55.0]]


def request(layout: dict, out: Path, built: dict) -> tuple[dict, dict]:
    place = lobby_cmd.ship_scene(layout)[0]
    pieces = lobby_cmd.raw(layout) / "pieces"
    req, staged, _want = lobby_cmd.scene_request(layout, pieces, place, lobby_layout.ship_report(layout))
    vs, sheets = [], []
    for piece, b in built.items():
        staged[f"furn_{piece}"] = out / piece / f"{piece}.glb"
        req["pieces"][f"furn_{piece}"] = f"res://import/furn_{piece}.glb"
        o, yaw = placement(piece)
        req["place"].append([f"furn_{piece}", [c / 100.0 for c in o], yaw])
        if piece == "mug":   # an empty one beside it, its Beer hidden (shots.gd "hide")
            req["place"].append([f"furn_{piece}", to_hall("mug", (-25.0, 0.0, 0.0)), yaw])
            req.setdefault("hide", []).append([f"furn_{piece}", 1, "Beer"])
        v = views(piece, b)
        vs += v
        n = [x[0] for x in v]
        sheets.append([f"{piece}_sheet.png", (CONCEPT_DIRS.get(piece, CONCEPTS) / PIECES[piece][1] / "image-0.png").as_posix(),
                       [["concept", n[0]], [n[1], n[2]], [n[3], n[4]], [n[5]]]])
    req.update({"mode": "shoot", "watchdog_s": 540, "background": layout["review"]["background"],
                "top": layout["review"]["top"], "look": lobby_cmd.look_request(layout, layout["look"]["scheme"]),
                "furniture": {"views": vs, "sheets": sheets, "hide": req.pop("hide", [])}})
    if "earth" in layout:
        req["earth"] = lobby_cmd.earth_request(layout, layout["earth"]["variant"])["earth"]
    if "light" in layout:
        req["light"] = lobby_cmd.light_request(layout, layout["light"]["mood"])["light"]
    return req, staged


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="v1")
    ap.add_argument("--only", default=",".join(PIECES))
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--no-shots", action="store_true")
    args = ap.parse_args()
    out = BASE / args.tag
    only = [p for p in args.only.split(",") if p]
    layout = lobby_layout.load()
    ok = True
    built, report = {}, {}
    for piece in only:
        folder = out / piece
        if not args.no_build:
            r = blender.run_script("lobby_furniture_build.py", ["--piece", piece, "--out", str(folder)], timeout=600)
            print(*[x for x in (r.stdout or "").splitlines() if x.startswith("FURNITURE_BUILD")], sep="\n", flush=True)
        passed, text = _export.verdict(_export.validate(folder / f"{piece}.glb", folder / f"{piece}.validator.json"))
        print(f"validator {piece}.glb: {text}", flush=True)
        ok = ok and passed
        b = json.loads((folder / f"{piece}.json").read_text(encoding="utf-8"))["bounds_cm"]
        built[piece] = b
        if piece in ON_BAR:
            continue
        cl = clearances(piece, b, layout)
        report[piece] = cl
        print(f"clearances {piece} (m): {cl}", flush=True)
        if min(cl["west_wall"], cl["east_wall"], cl["south_wall"]) < -0.001 or cl["pilasters"] < 0.0 or cl["doors"] < 0.0:
            print(f"CLASH {piece}: {cl}", flush=True)
            ok = False
    (out / "clearances.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    code = 0
    if not args.no_shots and built:
        req, staged = request(layout, out, built)
        for line in lobby_cmd._stage(staged)[:5]:
            print(f"  import: {line}")
        shots = out / "shots"
        shots.mkdir(parents=True, exist_ok=True)
        path = common.OUT / "lobby_furniture" / "shoot_request.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
        code, output = _godot.window(["--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s", SCRIPT, "--",
                                      path.as_posix(), shots.as_posix()], lobby_cmd.VIEW_SIZE, 600,
                                     log=out / "godot_shoot.log")
        (out / "godot_shoot.log").write_text(output, encoding="utf-8")
        print(*[x for x in output.splitlines() if x.startswith(("FURNITURE", "LOBBY")) or "SCRIPT ERROR" in x][:20],
              sep="\n")
        print(f"godot shots: exit {code} {shots.as_posix()}", flush=True)
    return 0 if ok and code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
