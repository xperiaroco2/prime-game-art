"""Full-body clip frames of one character's builds side by side (art #196, T3), plain Python: the job for
godot/alien/body_clips.gd (each row a loco build's character under char_shots.gd's game look, staged under its own
name) and the run in the runner's off-screen window. Six clips at a fixed phase: idle, walk, run (Jog_Fwd), crouch
(Crouch_Fwd), jump (Jump_Start at its take-off), strafe (Strafe_Left).

    $PYTHON_BIN tools/blender/alien_body_clips.py --char axolotl --rows r2b=loco/f3/build,t3=loco/t3/build --out bodies_a/t3

Rows are folders under anim_bare holding <char>/<char>_char.glb with its support files; --out is under the pilot
folder; an existing sheet is refused (the raw folder is never written over).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools"))

CLIPS = [{"label": "idle", "anim": "Idle", "phase": 0.0}, {"label": "walk", "anim": "Walk", "phase": 0.25},
         {"label": "run", "anim": "Jog_Fwd", "phase": 0.25}, {"label": "crouch", "anim": "Crouch_Fwd", "phase": 0.25},
         {"label": "jump", "anim": "Jump_Start", "phase": 0.7}, {"label": "strafe", "anim": "Strafe_Left", "phase": 0.25}]


def rows_arg(text: str) -> list[tuple[str, str]]:
    rows = [tuple(x.split("=", 1)) for x in text.split(",") if x]
    if not rows or any(len(r) != 2 or not r[0] or not r[1] for r in rows):
        raise ValueError(f"--rows {text!r}: expected label=folder[,label=folder]")
    return rows


def main() -> int:
    from runner.commands import _godot
    import alien_char_run as R
    ap = argparse.ArgumentParser()
    ap.add_argument("--char", required=True, choices=("chameleon", "axolotl"))
    ap.add_argument("--rows", required=True, help="label=folder under anim_bare (e.g. r2b=loco/f3/build), in order")
    ap.add_argument("--out", required=True, help="the sheet's folder under the pilot folder (e.g. bodies_a/t3)")
    a = ap.parse_args()
    out = R.PILOT / a.out
    sheet = f"body_clips_{a.char}"
    if (out / f"{sheet}.jpg").exists():
        print(f"{out / sheet}.jpg exists: pick a new --out", flush=True)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    slots_job = json.loads((R.SLOTS / "job.json").read_text(encoding="utf-8"))["heads"]
    rows = []
    for label, folder in rows_arg(a.rows):
        hd = R.PILOT / "anim_bare" / folder / a.char
        head = R.head_job(a.char, hd, json.loads((hd / "bases.json").read_text(encoding="utf-8")), slots_job)
        head["char"] = _godot.stage(hd / f"{a.char}_char.glb", f"body_{label}_{a.char}")
        rows.append({"label": label, "head": head})
    job = {"hdri": str(R.HDRI), "fix": dict(R.FIX), "out": str(out), "sheet": sheet, "rows": rows, "clips": CLIPS}
    jp = out / f"{sheet}_job.json"
    jp.write_text(json.dumps(job, indent=1), encoding="utf-8", newline="\n")
    _godot.import_project()
    code, output = _godot.window(["--path", str(_godot.PROJECT), "-s", "res://alien/body_clips.gd", "--", str(jp)],
                                 (1280, 720), 900)
    (out / f"{sheet}_godot.log").write_text(output, encoding="utf-8", newline="\n")
    print(f"godot body clips: exit {code}", *[x for x in output.splitlines() if "BODY" in x or "ERROR" in x][-20:],
          sep="\n", flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
