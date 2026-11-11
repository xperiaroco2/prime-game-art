"""The first-person hands (art#136, xperiaroco2/prime-game#1587, concept A): build, check, shoot. Plain Python.

    $PYTHON_BIN tools/blender/fp_hands_run.py --tag <tag> [--no-build] [--preview] [--no-shots] [--fps 30]
        [--asset assets/body/fp_hands]

1. fp_hands_build.py in headless Blender: <raw>/2026-11-11-fp-hands/<tag>/fp_hands.{blend,glb}, build.json.
2. glTF-Validator: validator.json (no errors).
3. The shots: a copy of the ship package (<raw>/ship/v5/export/v9, a Godot project) under tools/out/fp_hands/<tag>/proj
   with the hands, the energy crystal (assets/prop/energy_crystal) and godot/fp_hands/shots.gd, imported headless,
   then shot in an off-screen window (the runner's _godot.window()): each clip's frames, check.json.
4. The videos (Blender's FFmpeg, encode_clips.py): one per clip and reel.mp4 (idle, punch, run, then the same with
   the crystal), and a key-frame sheet per clip.
5. With --asset, and only when every check passed: the GLB and the .blend copied into the asset folder (its manifest
   and HANDOFF are written by hand).
Prints one JSON line `FP_RUN {...}`; exit 0 only when every check passes. Long: run it in the background.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
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
# the reel: (clip, times) in order; the hits between idles, as a player sees them
REEL = [("Idle_Loop", 1), ("Punch", 1), ("Punch", 1), ("Run_Loop", 2),
        ("Crystal_Idle_Loop", 1), ("Crystal_Hit", 1), ("Crystal_Hit", 1), ("Crystal_Run_Loop", 2)]


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


def shoot(proj: Path, out: Path, build: dict, fps: int) -> dict:
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
           "out": str(frames).replace("\\", "/"), "clips": clips, "light_levels": LIGHT_LEVELS}
    frames.mkdir(parents=True)
    rq = out / "shots_request.json"
    rq.write_text(json.dumps(req, indent=1), encoding="utf-8")
    code, text = _godot.window(["--path", str(proj), "-s", "res://fp/shots.gd", "--", str(rq)], SIZE, 1500,
                               log=out / "shots.log")
    (out / "shots.log").write_text(text, encoding="utf-8")
    if code != 0:
        raise common.Failure(f"shots.gd failed (exit {code}):\n" + "\n".join(text.splitlines()[-15:]))
    return json.loads((frames / "check.json").read_text(encoding="utf-8"))


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
    a = ap.parse_args()
    out = OUT / a.tag
    glb = out / "fp_hands.glb"
    if not a.no_build:
        if glb.exists():
            print(f"{out} holds a build: pick a new --tag", file=sys.stderr)
            return 2
        args = ["--raw", str(RAW), "--out", str(out)] + (["--preview"] if a.preview else [])
        blender.run_script("fp_hands_build.py", args, timeout=1200)
    build = json.loads((out / "build.json").read_text(encoding="utf-8"))
    report = _export.validate(glb, out / "validator.json")
    ok, why = _export.verdict(report)
    problems = ([] if ok else ["glTF-Validator reports errors"]) + build_checks(build)
    result = {"tag": a.tag, "validator": why}
    if not a.no_shots:
        proj = stage(a.tag, glb)
        check = shoot(proj, out, build, a.fps)
        videos(out, build, a.fps)
        problems += checks(build, check)
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
