"""The first-person hands (art#136, xperiaroco2/prime-game#1587, concept A): build, check, shoot. Plain Python.

    $PYTHON_BIN tools/blender/fp_hands_run.py --tag <tag> [--no-build] [--preview] [--no-shots] [--fps 30]
        [--asset assets/body/fp_hands] [--look-grid <variants.json>] [--hit-grid <poses.json>]

1. fp_hands_build.py in headless Blender: <raw>/2026-11-11-fp-hands/<tag>/fp_hands.{blend,glb}, build.json.
2. glTF-Validator: validator.json (no errors).
3. The shots: a copy of the ship package (<raw>/ship/v5/export/v9, a Godot project) under tools/out/fp_hands/<tag>/proj
   with the hands, the energy crystal (assets/prop/energy_crystal) and godot/fp_hands/shots.gd, imported headless,
   then shot in an off-screen window (the runner's _godot.window()): each clip's frames, check.json.
4. The videos (Blender's FFmpeg, encode_clips.py): one per clip and reel.mp4 (idle, punch, run, then the same with
   the crystal), and a key-frame sheet per clip.
5. The golden-frame check (fp_hands.toml [golden], tools/blender/fp_golden.py in headless Blender): the eye stills
   of the approved hold and the punch's contact against the golden run's, inside each frame's hand box; a gated
   frame past its threshold fails the run (a guard for the approved poses while another pose changes).
6. With --asset, and only when every check passed: the GLB and the .blend copied into the asset folder (its manifest
   and HANDOFF are written by hand).
--look-grid: only the look's variant grid on the tag's build (no build, no checks): each variant of the JSON list (a
name and any of fp_hands.toml [look]'s keys over it) shot at LOOK_SHOTS into <tag>/frames/variants/<name>_<shot>.png.
--rest-grid: the free hand at rest from the eye, a variant grid in Godot (art#136 q2): a JSON {"override": {...},
"base": {...}, "cells": [...]}, each cell a place and turn (rest_R) and any of [grips.rest]'s keys over the base; one
build with a static clip per cell, each shot from the game's camera into <tag>/frames/stills/<cell>.png, and a sheet
with the engineer's reference first (<tag>/grid.png); no checks. A cell's `bend` [up, side] gives the hand the
viewmodel's forearm (along the hand bent at the wrist, no reach limit); `pitch` (degrees down) shoots it with the
camera looking down, the hands kept in the body's space (`hands` "body", the default) or carried by the camera
("camera", a plain viewmodel: the same hand over another background); review shots only.
--hit-grid: only the crystal hit's contact grid (fp_hands_build.py --hit-grid: crystal poses from the eye, the hold
carried to each, their numbers and renders from the eye) into <tag>/hitgrid/, no export, no checks.
The hold's fit lists its fallbacks per hand (fit_hold: a default taken or a search's edge); the run prints each as a
`warning (not failing): ...` line and in FP_RUN's `hold_fallback`, without failing.
--golden-only: only the golden check on the tag's frames (--golden-dir another golden folder, e.g. a run's frames
to measure the noise floor); --make-golden: copy the tag's frames named in [golden] into its golden folder and print
their SHA-256 for fp_hands.toml.
Prints one JSON line `FP_RUN {...}`; exit 0 only when every check passes. Long: run it in the background.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from runner import blender, common  # noqa: E402
from runner.commands import _export, _godot  # noqa: E402

RAW = common.raw_dir()
OUT = RAW / "2026-11-11-fp-hands"
SHIP = RAW / "ship" / "v5" / "export" / "v9"   # the ship package v9 (art#263, PR #376), a Godot project
CRYSTAL = ROOT / "assets" / "prop" / "energy_crystal" / "export"
SIZE = (1280, 720)
FOV = 75.0          # the game's Camera3D (player.tscn: Godot's default 75 degrees, vertical)
EYE = [0.0, 2.8, 2.6]       # the hall: its floor at 1.2 m, the eye 1.6 m over it (the game's eye_height_m),
LOOK = [0.0, 2.55, -3.0]    # by the hall's back wall looking past the console into the throat
SOCKET_TOL_M = 0.002
LIGHT_LEVELS = [1.0, 0.4, 0.15]   # the held crystal's own light on the hands: as built, and two lower (a question)
# close-ups of the right hand from beside the eye with a long lens, for judging the hand itself (closeup_<name>.png)
CLOSEUPS = [{"name": "open", "clip": "Idle", "t": 0.0}, {"name": "fist", "clip": "Punch", "t": 0.15},
            {"name": "windup", "clip": "Punch", "t": 0.06}, {"name": "run", "clip": "Run", "t": 0.25},
            # the thumb's web (art#136 round 2): as drawn, without the normal map, with the back faces drawn
            {"name": "web", "clip": "Idle", "t": 0.0, "bone": "RightThumbProximal", "fov": 9.0},
            {"name": "web_nonormal", "clip": "Idle", "t": 0.0, "bone": "RightThumbProximal", "fov": 9.0, "no_normal": True},
            {"name": "web_nocull", "clip": "Idle", "t": 0.0, "bone": "RightThumbProximal", "fov": 9.0, "no_cull": True},
            # neutral close-ups of the open hand at rest (art#136 m31, five digits): its back from the eye's side and
            # its palm from beyond it, 35 cm off the hand's middle (the middle finger's root)
            {"name": "back", "clip": "Idle", "t": 0.0, "bone": "RightMiddleProximal", "side": "back", "dist": 0.35, "fov": 40.0},
            {"name": "palm", "clip": "Idle", "t": 0.0, "bone": "RightMiddleProximal", "side": "palm", "dist": 0.35, "fov": 40.0},
            # the same two without the normal map (art#136 q2): a crease that stays is the mesh's (skinning), one that
            # goes is the bake's
            {"name": "back_nonormal", "clip": "Idle", "t": 0.0, "bone": "RightMiddleProximal", "side": "back", "dist": 0.35,
             "fov": 40.0, "no_normal": True},
            {"name": "palm_nonormal", "clip": "Idle", "t": 0.0, "bone": "RightMiddleProximal", "side": "palm", "dist": 0.35,
             "fov": 40.0, "no_normal": True}]
# the look grid's shots: the fist at the punch's contact, the open hand, the crystal held
LOOK_SHOTS = [{"name": "fist", "clip": "Punch", "t": 0.15}, {"name": "open", "clip": "Idle", "t": 0.0},
              {"name": "hold", "clip": "Crystal_Idle", "t": 0.0, "crystal": True}]
# stills from the eye at moments no frame lands on (frames/stills/<name>.png): the golden check's
STILLS = [{"name": "punch_hit", "clip": "Punch", "t": 0.15}, {"name": "hold", "clip": "Crystal_Idle", "t": 0.0, "crystal": True},
          {"name": "idle", "clip": "Idle", "t": 0.0}, {"name": "run", "clip": "Run", "t": 0.0}]
# the reel: (clip, times) in order; the hits between idles, as a player sees them
REEL = [("Idle_Loop", 1), ("Punch", 1), ("Punch", 1), ("Run_Loop", 2),
        ("Crystal_Idle_Loop", 1), ("Crystal_Hit", 1), ("Crystal_Hit", 1), ("Crystal_Run_Loop", 2)]


GRIP_KEYS = ("Index", "Middle", "Ring", "Little", "spread", "Thumb", "ThumbTurn")
CELL_NAMES = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"   # letters: Godot's importer strips a clip name's trailing digits


def toml_cfg() -> dict:
    return tomllib.loads((ROOT / "tools" / "blender" / "fp_hands.toml").read_text(encoding="utf-8"))


def rest_R(c: dict, fov_deg: float) -> dict:
    """A free hand's frame from the eye (rest grid): `place` [% across, % down, distance m] the wrist in the hands'
    camera (vertical FOV fov_deg, 16:9); `angle` the fingers' direction in the picture (degrees from the right: 90 up,
    135 up-left); `lean` the fingers tilted away from the eye; `tip` the hand turned about its side axis, fingers
    away and the back up toward the view's top (the wrist's pitch); `roll` the back's turn about the fingers (0: the
    back square to the eye; + the thumb's side toward the eye)."""
    th = math.tan(math.radians(fov_deg) / 2.0)
    x_pct, y_pct, dist = c["place"]
    p = [(x_pct / 100.0 - 0.5) * 2.0 * dist * th * SIZE[0] / SIZE[1], dist, -(y_pct / 100.0 - 0.5) * 2.0 * dist * th]
    a, e = math.radians(c.get("angle", 135.0)), math.radians(c.get("lean", 0.0))

    def unit(v):
        L = math.sqrt(sum(x * x for x in v))
        return [x / L for x in v]

    def cross(u, v):
        return [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]

    def turn(v, k, deg):   # v about the unit axis k (Rodrigues)
        r = math.radians(deg)
        kv = cross(k, v)
        d = sum(x * y for x, y in zip(k, v))
        return [v[i] * math.cos(r) + kv[i] * math.sin(r) + k[i] * d * (1 - math.cos(r)) for i in range(3)]

    f = unit([math.cos(a) * math.cos(e), math.sin(e), math.sin(a) * math.cos(e)])
    eye = [-x for x in p]
    d = sum(x * y for x, y in zip(eye, f))
    n = unit([eye[i] - d * f[i] for i in range(3)])     # the back square to the eye
    side = unit(cross(f, n))
    n = unit(turn(n, side, -c.get("tip", 0.0)))   # side = f x n: a negative turn takes the fingers away
    f = unit(turn(f, side, -c.get("tip", 0.0)))
    n = unit(turn(n, f, c.get("roll", 0.0)))
    return {"p": [round(x, 4) for x in p], "f": [round(x, 4) for x in f], "n": [round(x, 4) for x in n]}


def ref_rest() -> Path:
    """The engineer's rest reference (specs/fp_hand_dims.toml [reference.picks] rest, a raw-root path; private)."""
    spec = tomllib.loads((ROOT / "specs" / "fp_hand_dims.toml").read_text(encoding="utf-8"))
    return RAW / spec["reference"]["picks"]["rest"]


def rest_grid(tag: str, grid_path: Path, fps: int) -> dict:
    """The rest grid (see the module's doc): one build, a still per cell from the eye, the sheet."""
    out = OUT / tag
    if (out / "fp_hands.glb").exists():
        raise common.Failure(f"{out} holds a build: pick a new --tag")
    out.mkdir(parents=True, exist_ok=True)
    grid = json.loads(grid_path.read_text(encoding="utf-8"))
    cfg = toml_cfg()
    over = json.loads(json.dumps(grid.get("override", {})))
    rest = {**cfg["grips"]["rest"], **over.get("grips", {}).get("rest", {})}
    cells, table = [], {}
    for i, cell in enumerate(grid["cells"]):
        c = {**grid.get("base", {}), **cell}
        name = CELL_NAMES[i]
        over.setdefault("grips", {})["grid" + name] = {**rest, **{k: c[k] for k in GRIP_KEYS if k in c}}
        R = rest_R(c, float(cfg["view"]["fov_deg"])) if c.get("place") else dict(cfg["poses"]["idle"]["R"])
        if "bend" in c:   # the viewmodel's forearm: along the hand bent by [up, side] degrees, no reach limit
            R["bend"] = c["bend"]
        over.setdefault("poses", {})["grid" + name] = {"R": R, "grip_R": "grid" + name}
        over.setdefault("clips", {})["Grid" + name] = {"pose": "grid" + name, "seconds": 0.1}
        cells.append(name)
        table[name] = {"cell": c, "R": R}
    (out / "grid_override.json").write_text(json.dumps(over, indent=1), encoding="utf-8")
    blender.run_script("fp_hands_build.py", ["--raw", str(RAW), "--out", str(out), "--override",
                                             str(out / "grid_override.json")], timeout=1200)
    build = json.loads((out / "build.json").read_text(encoding="utf-8"))
    for name in cells:
        table[name]["out_of_reach_mm"] = build["clips"]["Grid" + name]["out_of_reach_mm"]
    proj = stage(tag, out / "fp_hands.glb")
    code, text = _godot.godot(["--headless", "--path", str(proj), "--import"], 900)
    if code != 0:
        raise common.Failure("the Godot import failed:\n" + "\n".join(text.splitlines()[-15:]))
    frames = out / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    req = {"scene": "res://levels/ship/ship.tscn", "hands": "res://fp/fp_hands.glb", "crystal": "res://fp/energy_crystal.glb",
           "eye": EYE, "look": LOOK, "fov": FOV, "vm_fov": build["vm_fov"], "size": list(SIZE), "fps": fps,
           "out": str(frames).replace("\\", "/"), "clips": [], "closeups": [], "skin": look(),
           "stills": [{"name": n, "clip": "Grid" + n, "t": 0.0,
                       **{k: table[n]["cell"][k] for k in ("pitch", "hands") if k in table[n]["cell"]}} for n in cells]}
    rq = out / "shots_request.json"
    rq.write_text(json.dumps(req, indent=1), encoding="utf-8")
    code, text = _godot.window(["--path", str(proj), "-s", "res://fp/shots.gd", "--", str(rq)], SIZE, 1500,
                               log=out / "shots.log")
    (out / "shots.log").write_text(text, encoding="utf-8")
    if code != 0:
        raise common.Failure("the grid's shots failed:\n" + "\n".join(text.splitlines()[-15:]))
    files = [str(ref_rest())] + [str(frames / "stills" / f"{n}.png") for n in cells]
    sheets = out / "sheets.json"
    # the whole frames, and the hand's region larger (the lower 60 %, from 20 % across to the right edge)
    sheets.write_text(json.dumps({str(out / "grid.png"): {"files": files, "cols": 4, "w": 320, "h": 180},
                                  str(out / "grid_crop.png"): {"files": files, "cols": 3, "w": 427, "h": 234,
                                                               "crop": [0.2, 0.4, 1.0, 1.0]}}), encoding="utf-8")
    blender.run_script("fp_hands_build.py", ["--sheets", str(sheets)], timeout=300)
    (out / "grid.json").write_text(json.dumps(table, indent=1), encoding="utf-8")
    return {"grid": str(out / "grid.png"), "out_of_reach_mm": {n: table[n]["out_of_reach_mm"] for n in cells}}


def stage(tag: str, glb: Path) -> Path:
    proj = common.OUT / "fp_hands" / tag / "proj"
    if proj.exists():
        shutil.rmtree(proj)
    shutil.copytree(SHIP, proj, ignore=shutil.ignore_patterns("_check", ".godot"))
    (proj / "fp").mkdir()
    shutil.copyfile(glb, proj / "fp" / "fp_hands.glb")
    shutil.copyfile(CRYSTAL / "energy_crystal.glb", proj / "fp" / "energy_crystal.glb")
    (proj / "crystal").mkdir()
    for f in CRYSTAL.iterdir():
        if f.suffix in (".gd", ".gdshader"):
            shutil.copyfile(f, proj / "crystal" / f.name)
    shutil.copyfile(ROOT / "godot" / "fp_hands" / "shots.gd", proj / "fp" / "shots.gd")
    _godot.install_offscreen(proj)
    return proj


def look() -> dict:
    """fp_hands.toml [look]: the body colour the shots tint the skin with and the hands' fill light."""
    return tomllib.loads((ROOT / "tools" / "blender" / "fp_hands.toml").read_text(encoding="utf-8"))["look"]


def shoot(proj: Path, out: Path, build: dict, fps: int, variants: list | None = None) -> dict:
    code, text = _godot.godot(["--headless", "--path", str(proj), "--import"], 900)
    if code != 0:
        raise common.Failure("the Godot import failed:\n" + "\n".join(text.splitlines()[-15:]))
    frames = out / "frames"
    if frames.exists():
        shutil.rmtree(frames)
    clips = [{"name": _godot.godot_name(n)[0], "crystal": c["holds_crystal"], "hit": c["hit_s"], "cycles": 2 if "Run" in n else 1}
             for n, c in build["clips"].items()]
    req = {"scene": "res://levels/ship/ship.tscn", "hands": "res://fp/fp_hands.glb",
           "crystal": "res://fp/energy_crystal.glb", "eye": EYE, "look": LOOK, "fov": FOV, "vm_fov": build["vm_fov"], "size": list(SIZE), "fps": fps,
           "out": str(frames).replace("\\", "/"), "clips": clips, "light_levels": LIGHT_LEVELS, "closeups": CLOSEUPS, "stills": STILLS, "skin": look()}
    if variants:
        req.update({"variants": variants, "variant_shots": LOOK_SHOTS})
    frames.mkdir(parents=True)
    rq = out / "shots_request.json"
    rq.write_text(json.dumps(req, indent=1), encoding="utf-8")
    code, text = _godot.window(["--path", str(proj), "-s", "res://fp/shots.gd", "--", str(rq)], SIZE, 1500,
                               log=out / "shots.log")
    (out / "shots.log").write_text(text, encoding="utf-8")
    if code != 0 or variants:
        if variants and code == 0:
            return {}
        raise common.Failure(f"shots.gd failed (exit {code}):\n" + "\n".join(text.splitlines()[-15:]))
    return json.loads((frames / "check.json").read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def golden(out: Path, gdir: Path | None = None) -> dict:
    """The golden-frame check: fp_hands.toml [golden]'s frames of this run (frames/<frame>) against the golden ones
    (<raw>/[golden] dir/<name>.png, their SHA-256 checked first), each inside its hand box, in headless Blender
    (fp_golden.py). Returns its golden.json: ok, and per frame the changed share and mean difference."""
    g = tomllib.loads((ROOT / "tools" / "blender" / "fp_hands.toml").read_text(encoding="utf-8"))["golden"]
    rows = []
    for f in g["frames"]:
        gold = (gdir / f["frame"]) if gdir else (RAW / g["dir"] / f"{f['name']}.png")
        if gdir is None and sha256(gold) != f["sha256"]:
            raise common.Failure(f"the golden frame {gold} does not match its SHA-256 in fp_hands.toml [golden]")
        rows.append({"name": f["name"], "golden": str(gold), "run": str(out / "frames" / f["frame"]),
                     "box": f["box"], "gate": f.get("gate", True)})
    spec = out / "golden_spec.json"
    spec.write_text(json.dumps({"changed": g["changed"], "max_share": g["max_share"], "frames": rows}, indent=1),
                    encoding="utf-8")
    res = out / "golden.json"
    blender.run_script("fp_golden.py", ["--spec", str(spec), "--out", str(res)], timeout=300)
    return json.loads(res.read_text(encoding="utf-8"))


def make_golden(out: Path) -> dict:
    g = tomllib.loads((ROOT / "tools" / "blender" / "fp_hands.toml").read_text(encoding="utf-8"))["golden"]
    gdir = RAW / g["dir"]
    gdir.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for f in g["frames"]:
        dst = gdir / f"{f['name']}.png"
        if dst.exists():
            raise common.Failure(f"{dst} exists: the golden frames are never overwritten")
        shutil.copyfile(out / "frames" / f["frame"], dst)
        hashes[f["name"]] = sha256(dst)
    return hashes


def build_checks(build: dict) -> list[str]:
    """Blender's own numbers: no wrist out of the arm's reach, no held hand inside or off the crystal."""
    bad = []
    for name, c in build["clips"].items():
        for side, mm in c["out_of_reach_mm"].items():
            if mm > 1.0:
                bad.append(f"{name}: the {side} wrist is {mm} mm out of the arm's reach")
        for side, cc in c.get("crystal_contact_mm", {}).items():
            if cc["deepest_inside"] > 3.0:
                bad.append(f"{name}: the {side} hand is {cc['deepest_inside']} mm inside the crystal")
            if cc["nearest_gap"] > 4.0:
                bad.append(f"{name}: the {side} hand floats {cc['nearest_gap']} mm off the crystal")
    return bad


def checks(build: dict, check: dict) -> list[str]:
    """Godot's import against the build: the socket, every clip's length and loop mode, the fist at the punch."""
    bad = []
    if check.get("socket_parent") != "BoneAttachment3D":
        bad.append(f"CrystalSocket's parent is {check.get('socket_parent')}, not a BoneAttachment3D")
    want = build["socket_in_view"]  # Blender's view space (x right, y forward, z up) -> Godot's (x, z, -y)
    for name, c in build["clips"].items():
        got = check["clips"].get(_godot.godot_name(name)[0])
        if got is None:
            bad.append(f"{name}: not in the GLB")
            continue
        if abs(got["length"] - c["seconds"]) > 0.02:
            bad.append(f"{name}: {got['length']:.3f} s in Godot, {c['seconds']} s built")
        if (got["loop"] != 0) != c["loop"]:
            bad.append(f"{name}: loop mode {got['loop']}, built {'a loop' if c['loop'] else 'once'}")
        if c["hit_s"] is not None and not c["holds_crystal"] and got.get("fist_at_hit", 0) < 0.99:
            bad.append(f"{name}: the fist morph is {got.get('fist_at_hit')} at the hit")
        w = want.get(name)
        if w is not None:
            g = got["socket"]["origin"]
            d = math.dist(g, [w[0], w[2], -w[1]])
            if d > SOCKET_TOL_M:
                bad.append(f"{name}: CrystalSocket {d * 1000:.1f} mm from Blender's in Godot")
    return bad


def videos(out: Path, build: dict, fps: int) -> None:
    frames = out / "frames"
    reel = frames / "_reel"
    if reel.exists():
        shutil.rmtree(reel)
    reel.mkdir()
    k = 0
    for name, times in REEL:
        files = sorted((frames / _godot.godot_name(name)[0]).glob("*.png"))
        for _ in range(times):
            for f in files:
                shutil.copyfile(f, reel / f"{k:05d}.png")
                k += 1
    names = [_godot.godot_name(n)[0] for n in build["clips"]]
    dirs = [str(frames / n) for n in names] + [str(reel)]
    blender.run_script("encode_clips.py", ["--frames", *dirs, "--out", str(out / "video"), "--fps", str(fps),
                                           "--repeat", "1"], timeout=900)
    spec = {}
    for name in names:
        files = sorted((frames / name).glob("*.png"))
        n = len(files)
        picks = [round(i * (n - 1) / 5) for i in range(6)]
        spec[str(out / "sheets" / f"{name}.png")] = [str(files[i]) for i in picks]
    (out / "sheets").mkdir(exist_ok=True)
    sp = out / "sheets" / "spec.json"
    sp.write_text(json.dumps(spec), encoding="utf-8")
    blender.run_script("fp_hands_build.py", ["--sheets", str(sp)], timeout=600)


def main() -> int:
    ap = argparse.ArgumentParser(prog="fp_hands_run.py")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--no-shots", action="store_true")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--asset", default="")
    ap.add_argument("--look-grid", default="")
    ap.add_argument("--hit-grid", default="")
    ap.add_argument("--rest-grid", default="")
    ap.add_argument("--golden-only", action="store_true")
    ap.add_argument("--golden-dir", default="")
    ap.add_argument("--make-golden", action="store_true")
    ap.add_argument("--override", default="", help="a JSON object merged over fp_hands.toml's tables for this build "
                    "(a review variant: e.g. {\"poses\": {\"idle\": {\"R\": ...}}}); never for an --asset run")
    a = ap.parse_args()
    out = OUT / a.tag
    glb = out / "fp_hands.glb"
    if a.make_golden:
        print("FP_RUN " + json.dumps({"tag": a.tag, "golden_sha256": make_golden(out)}))
        return 0
    if a.golden_only:
        res = golden(out, Path(a.golden_dir) if a.golden_dir else None)
        print("FP_RUN " + json.dumps({"tag": a.tag, "golden": res}))
        return 0 if res["ok"] else 1
    if a.look_grid:
        build = json.loads((out / "build.json").read_text(encoding="utf-8"))
        variants = json.loads(Path(a.look_grid).read_text(encoding="utf-8"))
        shoot(stage(a.tag, glb), out, build, a.fps, variants)
        print("FP_RUN " + json.dumps({"tag": a.tag, "look_grid": str(out / "frames" / "variants")}))
        return 0
    if a.rest_grid:
        print("FP_RUN " + json.dumps({"tag": a.tag, "rest_grid": rest_grid(a.tag, Path(a.rest_grid).resolve(), a.fps)}))
        return 0
    if a.hit_grid:
        out.mkdir(parents=True, exist_ok=True)
        blender.run_script("fp_hands_build.py", ["--raw", str(RAW), "--out", str(out), "--hit-grid",
                                                 str(Path(a.hit_grid).resolve())], timeout=1200)
        print("FP_RUN " + json.dumps({"tag": a.tag, "hit_grid": str(out / "hitgrid")}))
        return 0
    if not a.no_build:
        if glb.exists():
            print(f"{out} holds a build: pick a new --tag", file=sys.stderr)
            return 2
        if a.override and a.asset:
            print("--override builds a review variant, never the asset", file=sys.stderr)
            return 2
        args = ["--raw", str(RAW), "--out", str(out)] + (["--preview"] if a.preview else [])
        args += ["--override", str(Path(a.override).resolve())] if a.override else []
        blender.run_script("fp_hands_build.py", args, timeout=1200)
    build = json.loads((out / "build.json").read_text(encoding="utf-8"))
    report = _export.validate(glb, out / "validator.json")
    ok, why = _export.verdict(report)
    problems = ([] if ok else ["glTF-Validator reports errors"]) + build_checks(build)
    result = {"tag": a.tag, "validator": why}
    fallback = {side: f.get("fallback", []) for side, f in build.get("hold_fit", {}).items()}
    for side, items in fallback.items():
        for item in items:
            print(f"warning (not failing): the {side} hold's fit fell back: {item}")
    result["hold_fallback"] = fallback
    if not a.no_shots:
        proj = stage(a.tag, glb)
        check = shoot(proj, out, build, a.fps)
        videos(out, build, a.fps)
        problems += checks(build, check)
        res = golden(out)
        result["golden"] = {r["name"]: {k: r.get(k) for k in ("share", "mean", "pass", "gate")} for r in res["frames"]}
        problems += [f"golden {r['name']}: {r.get('why') or str(r['share']) + ' of its box changed'} (max "
                     f"{res['max_share']})" for r in res["frames"] if r["gate"] and not r["pass"]]
        result["gpu_ms"] = {n: c["gpu_ms"] for n, c in check["clips"].items()}
    result["problems"] = problems
    if a.asset and not problems:
        asset = ROOT / a.asset
        (asset / "export").mkdir(parents=True, exist_ok=True)
        (asset / "source").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(glb, asset / "export" / "fp_hands.glb")
        shutil.copyfile(out / "fp_hands.blend", asset / "source" / "fp_hands.blend")
        shutil.copyfile(out / "validator.json", asset / "report.json")
    print("FP_RUN " + json.dumps(result))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
