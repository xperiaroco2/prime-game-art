"""The photo poses' Godot side (art #196): the plain-Python driver of the layers check and the review pictures.

`$PYTHON_BIN tools/blender/alien_poses_run.py [--raw D:/prime-art-raw] [--step s3] --check [--chars ...]` (the
default step: the newest with both GLBs) writes per
character the Blender-composed reference of all 48 pairs (`ref_<char>.json`: the plain-Python composition of the
same clips, every bone's head and world turn from the rest in glTF axes; pure skinning equals Blender's evaluated pose, step 2) and runs
godot/alien/pose_layers_check.gd headless on the step's GLBs: pose_layers.gd's two filtered layers against the
reference, the hold, stop(), the head look's slide on the contact pairs (`layers_<char>.json`; POSES lines, exit 1 on
a failure).
`... --shots [--chars ...]` runs godot/alien/pose_shots.gd in the runner's off-screen window: the review pictures of
docs/animations.md, "The photo poses (art #196)", into <raw>/<poses>/<step>/ (`shots_<char>.json` says what each
sheet shows).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))
import alien_pose_math as A  # noqa: E402
import alien_poses as P  # noqa: E402


def gltf(v) -> list:
    """Blender's armature space (Z up, -Y forward) to glTF's (Y up, +Z forward)."""
    return [round(v[0], 6), round(v[2], 6), round(-v[1], 6)]


def gltf_q(q) -> list:
    """A rotation (w, x, y, z) in Blender's armature space as glTF's (x, y, z, w), Godot's Quaternion order."""
    return [round(q[1], 6), round(q[3], 6), round(-q[2], 6), round(q[0], 6)]


def turn(Pm: dict, R: dict, b: str) -> list:
    """The bone's world turn from its rest (pose * rest^-1): free of how an exporter orients the bones' own axes."""
    return gltf_q(A.M.q_mul(A.S.mat_q(Pm[b]), A.M.q_conj(A.S.mat_q(R[b]))))


def reference(dump: dict, cfg: dict) -> dict:
    """Every pair's bone heads and world turns from the rest, composed from its two layers as the GLB's clips are
    (alien_pose_math.compose)."""
    model = A.Model(dump["skel"], dump["skin"], cfg)
    R = A.Rig(dump["skel"]).P()
    legs = {n: model.legs(n) for n in cfg["legs"]}
    arms = {n: model.arms(n) for n in cfg["arms"]}
    arms.update(model.variants(legs, arms))
    pairs = {}
    for lg, am in P.pairs_of(cfg, "all"):
        Pm = A.compose(legs[lg], A.arms_for(arms, am, lg)).P()
        pairs[f"{lg}+{am}"] = {"legs": lg, "arms": am, "heads": {b: gltf(A.S.pos(m)) for b, m in Pm.items()},
                                "turns": {b: turn(Pm, R, b) for b in Pm}}
    return {"pairs": pairs}


def built_data(hd: Path, cfg: dict) -> tuple[dict, str]:
    """The pose data a build's clips were solved from (its `pose_data.json`, written by alien_poses.py; an older
    build without one: the TOML's) and the top-level parts of it that differ from the TOML's ("" when none)."""
    f = hd / "pose_data.json"
    if not f.is_file():
        return cfg, ""
    built = json.loads(f.read_text(encoding="utf-8"))
    now = json.loads(json.dumps(cfg))
    return built, ", ".join(k for k in sorted(set(built) | set(now)) if built.get(k) != now.get(k))


def newest_step(raw: str, cfg: dict) -> str:
    """The newest step folder (s1, s2, ... by number) whose build holds every character's GLB, or ""."""
    base = Path(raw) / cfg["set"]["raw_base"] / cfg["set"]["out"]
    steps = [d for d in base.glob("s*") if d.name[1:].isdigit() and
             all((d / "build" / c / f"{c}_char.glb").is_file() for c in cfg["set"]["chars"])]
    return max(steps, key=lambda d: int(d.name[1:])).name if steps else ""


def main() -> int:
    from runner.commands import _godot
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="", help="the raw root (default: alien_char_run's)")
    ap.add_argument("--step", default="", help="default: the newest step with both GLBs")
    ap.add_argument("--chars", default="")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--shots", action="store_true")
    a = ap.parse_args()
    cfg = A.load()
    if not a.raw:
        import alien_char_run as R
        a.raw = str(R.RAW)
    a.step = a.step or newest_step(a.raw, cfg)
    if not a.step:
        print("no poses build with every character's GLB", flush=True)
        return 1
    chars = a.chars.split(",") if a.chars else cfg["set"]["chars"]
    _, out = P._dirs(a.raw, a.step, cfg)
    code = 0
    if a.check:
        job = {"chars": []}
        for c in chars:
            dump = json.loads((out / f"{c}_dump.json").read_text(encoding="utf-8"))
            built, stale = built_data(out / "build" / c, cfg)
            if stale:
                print(f"NOTE {c}: the build's pose data differs from the TOML ({stale}); the reference follows the "
                      f"build's (rebuild with alien_poses.py --glb)", flush=True)
            ref = out / f"ref_{c}.json"
            ref.write_text(json.dumps(reference(dump, built)), encoding="utf-8", newline="\n")
            job["chars"].append({"glb": _godot.stage(out / "build" / c / f"{c}_char.glb", f"poses_{c}"),
                                 "ref": str(ref), "out": str(out / f"layers_{c}.json")})
        (out / "check_job.json").write_text(json.dumps(job, indent=1), encoding="utf-8", newline="\n")
        _godot.import_project()
        rc, output = _godot.godot(["--headless", "--path", str(_godot.PROJECT), "-s", "res://alien/pose_layers_check.gd",
                                   "--", str(out / "check_job.json")], 900)
        (out / "check_godot.log").write_text(output, encoding="utf-8", newline="\n")
        print(*[x for x in output.splitlines() if x.startswith(("POSES", "ERROR", "SCRIPT ERROR"))], sep="\n", flush=True)
        code |= rc
    if a.shots:
        import alien_char_run as R
        slots_job = json.loads((R.SLOTS / "job.json").read_text(encoding="utf-8"))["heads"]
        for c in chars:
            hd = out / "build" / c
            job = {"hdri": str(R.HDRI), "fix": dict(R.FIX), "out": str(out), "char_name": c,
                   "head": R.head_job(c, hd, json.loads((hd / "bases.json").read_text(encoding="utf-8")), slots_job),
                   "legs": list(cfg["legs"]), "arms": list(cfg["arms"]), "starting": cfg["set"]["starting"]}
            (out / f"shots_job_{c}.json").write_text(json.dumps(job, indent=1), encoding="utf-8", newline="\n")
            _godot.import_project()
            rc, output = _godot.window(["--path", str(_godot.PROJECT), "-s", "res://alien/pose_shots.gd", "--",
                                        str(out / f"shots_job_{c}.json")], (1280, 720), 3000)
            (out / f"shots_godot_{c}.log").write_text(output, encoding="utf-8", newline="\n")
            print(f"{c} godot shots: exit {rc}", *[x for x in output.splitlines() if "SHOT" in x or "ERROR" in x][-30:],
                  sep="\n", flush=True)
            code |= rc
    return code


if __name__ == "__main__":
    raise SystemExit(main())
