"""The fitted bodies in motion (art #196, step D3d; D3 item 7), in headless Blender: opens a body from `body_fit_blend.py
apply` (its armature keeps S4b's clips), with `--leg-fit` scales the clips' Root and Hips keys to this body's legs and
matches the feet's lowest point per frame (alien_leg_fit.py, the character build's T2 step: body B, whose legs are
shorter than the S4b rig the clips were made on), and saves `<out>/<name>.blend` for `tools/run.sh export`.

    blender -b --factory-startup --python tools/blender/body_fit_motion.py -- --body <alien_body.blend>
        --out DIR --name body_b [--leg-fit <S4b alien_body.blend>]

An out folder holding the .blend is refused (the raw folder is never written over).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--body", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--leg-fit", default="", help="the .blend of the rig the clips were made on (S4b's body)")
    a = ap.parse_args(argv)
    out = Path(a.out)
    blend = out / f"{a.name}.blend"
    if blend.exists():
        raise SystemExit(f"refused: {blend} exists")
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(Path(a.body).resolve()))
    arm = bpy.data.objects["CharacterArmature"]
    actions = [x for x in bpy.data.actions if x.name.startswith("CharacterArmature|")]
    rep = {"body": a.body, "actions": len(actions), "objects": sorted(o.name for o in bpy.data.objects)}
    if not actions:
        raise SystemExit("no CharacterArmature| actions in the body file")
    if a.leg_fit:
        import alien_leg_fit
        lf = alien_leg_fit.fit(arm, a.leg_fit, actions)
        rep["leg_fit"] = {k: lf[k] for k in ("leg_m", "scale", "donor") if k in lf}
    bpy.ops.wm.save_as_mainfile(filepath=str(blend.resolve()))
    rep["blend"] = str(blend)
    (out / f"{a.name}_motion.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8", newline="\n")
    print("MOTION", json.dumps(rep, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
