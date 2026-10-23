"""B4 review (a) and (b), art #196: the alien characters' spring bones through the contract's import path, and their
heights against the game's 1.80 m capsule. Measures only; changes no build, contract or doc.

    $PYTHON_BIN tools/blender/alien_char_bones.py --tag body_v2/r5 [--heads chameleon,axolotl]

1. `godot-check --profile alien --humanoid` on each `<tag>/<head>/<head>_char.glb`: the plain import's checks (named
   extra bones, height without an allowance) and the SkeletonProfileHumanoid trial (Godot 4.7.2's BoneMap retarget,
   with and without its default track removal), reports in `<tag>/godot_check/`.
2. godot/alien/bones_probe.gd, headless, on the three imports: bones after import, the springs driven by the lively
   controller (pose angles, the spring-weighted vertices' head-relative swing as vectors in rest world space, their
   difference and swing-direction angle against the plain import), the
   Head bone's scale over a breath, every clip's unresolved tracks and turn.
3. `<tag>/bones.json` and `<tag>/bones.md` (with the heights from each build's char.json).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from runner import common  # noqa: E402
from runner.commands import _godot  # noqa: E402

PILOT = common.raw_dir() / "research" / "2026-10-22-roster" / "design" / "pilot3d"
CONTRACT_BONES = 56
VARIANTS = (("plain", ""), ("keep_positions", "_humanoid"), ("godot_defaults", "_humanoid_defaults"))


def table(heads: list[str], out: Path, probe: dict) -> str:
    rows = ["# The alien characters' bones and heights (art #196, B4 review a and b)", "",
            f"Measured from `{out.as_posix()}` by `tools/blender/alien_char_bones.py` (headless Godot 4.7.2); nothing "
            "rescaled or changed. The contract (docs/contract.md) asks for exactly the 56 profile bones; whether the "
            "springs may stay is the engineer's call.", "",
            "## Bones through the import path", "",
            "| head | variant | bones in | bones after import | springs found | spring pose max deg (the controller's "
            "own value) | spring swing max mm (head-relative, rest world space) | against the plain import: vector "
            "difference max mm | swing direction angle max / mean deg | clips (unresolved tracks) | Head scale range "
            "over a breath % (held / following) |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for h in heads:
        char = json.loads((out / h / "char.json").read_text(encoding="utf-8"))
        for v, _ in VARIANTS:
            r = probe[h].get(v, {})
            clips = r.get("clips", {})
            lost = sum(c["unresolved"] for c in clips.values())
            moving = sum(c["turn_deg"] > 1.0 for c in clips.values())
            hs = r.get("head_scale_range_pct", {})
            rows.append(f"| {h} | {v} | {char['bones']} | {r.get('bone_count')} | {len(r.get('springs_found', []))} of "
                        f"{len(char['springs'])} | {r.get('spring_max_deg')} | {r.get('spring_move_max_mm')} | "
                        f"{r.get('against_first_mm')} | {r.get('swing_angle_max_deg')} / {r.get('swing_angle_mean_deg')} | {len(clips)} clips, {moving} turning > 1 deg, {lost} unresolved "
                        f"| {hs.get('held')} / {hs.get('follow')} |")
    rows += ["", "## Heights (rest pose, m above the lowest vertex)", "",
             "| head | whole top | over the 1.80 m capsule | skull top | crest/gill top | body top (no head weight) | "
             "eyes |", "|---|---|---|---|---|---|---|"]
    for h in heads:
        t = json.loads((out / h / "char.json").read_text(encoding="utf-8"))["heights"]
        rows.append(f"| {h} | {t['all_top_m']:.3f} | {t['over_capsule_m']:+.3f} | {t['skull_top_m']:.3f} | "
                    f"{t['springs_top_m']:.3f} | {t['body_top_m']:.3f} | {t['LeftEye_m']:.3f} |")
    return "\n".join(rows) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="body_v2/r5")
    ap.add_argument("--heads", default="chameleon,axolotl")
    ap.add_argument("--probe-only", action="store_true", help="the godot-check imports already staged")
    args = ap.parse_args()
    heads, out = args.heads.split(","), PILOT / args.tag
    glbs = [str(out / h / f"{h}_char.glb") for h in heads]
    if not args.probe_only:
        gc = subprocess.run([sys.executable, str(ROOT / "tools" / "run.py"), "godot-check", "--profile", "alien",
                             "--humanoid", "--textured", "--out", str(out / "godot_check"), *glbs],
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1500)
        (out / "godot_check.log").write_text(gc.stdout + gc.stderr, encoding="utf-8", newline="\n")
        print(f"godot-check: exit {gc.returncode} ({out / 'godot_check.log'})", flush=True)
    job = {"out": str(out / "bones.json"), "heads": {
        h: {"lively": str(out / h / f"{h}_char_lively.json"),
            "variants": {v: f"res://import/{h}_char{s}.glb" for v, s in VARIANTS}} for h in heads}}
    (out / "bones_job.json").write_text(json.dumps(job, indent=1), encoding="utf-8", newline="\n")
    code, text = _godot.godot(["--headless", "--path", str(_godot.PROJECT), "-s", "res://alien/bones_probe.gd", "--",
                               str(out / "bones_job.json")], 900)
    (out / "bones_probe.log").write_text(text, encoding="utf-8", newline="\n")
    print(*[x for x in text.splitlines() if x.startswith(("BONES", "ERROR", "SCRIPT ERROR"))], sep="\n", flush=True)
    if code != 0 or not (out / "bones.json").exists():
        print(f"bones_probe: exit {code}", flush=True)
        return 1
    probe = json.loads((out / "bones.json").read_text(encoding="utf-8"))
    (out / "bones.md").write_text(table(heads, out, probe), encoding="utf-8", newline="\n")
    print(f"wrote {out / 'bones.md'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
