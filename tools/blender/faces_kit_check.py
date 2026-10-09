"""The clay face kit's many-face check (tools/run.py faces --kit-check N, docs/faces.md): N random faces per body type
on the recipe's heads under random hair items, measured (um/clayface/survey.py); writes kit_check.json.

The runner calls it; by hand, background only:
  blender -b --factory-startup --python-exit-code 1 --python tools/blender/faces_kit_check.py -- \
      --recipe recipes/clay_round_d.json --raw D:/prime-art-raw --out tools/out/faces_kit --n 320 [--bodies M,W]
"""

import argparse
import json
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from um import packs as pk  # noqa: E402
from um import recipe as recipes  # noqa: E402
from um.clayface import kit, survey  # noqa: E402


def parse():
    p = argparse.ArgumentParser(prog="faces_kit_check.py")
    p.add_argument("--recipe", required=True)
    p.add_argument("--raw", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--n", type=int, default=320)
    p.add_argument("--bodies", default="M,W")
    return p.parse_args(sys.argv[sys.argv.index("--") + 1:])


def main():
    args = parse()
    R = recipes.load(args.recipe, args.raw)
    packs = pk.Packs({g: recipes.pack_dir(R, args.raw, g) for g in recipes.GENDERS})
    bpy.ops.wm.read_factory_settings(use_empty=True)
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    report = {"recipe": R["_name"], "n": args.n, "seeds": survey.SEEDS, "kit_data_sha": kit.DATA_SHA, "bodies": {}}
    for g in args.bodies.split(","):
        rc = next((c for c in R["characters"] if c["gender"] == g), None)
        if rc is None:
            raise RuntimeError(f"the recipe has no character of body type {g}")
        report["bodies"][g] = survey.run_body(packs, R, rc, args.n, log=lambda s: print(s, flush=True))
        print("CHECK", g, json.dumps({k: v for k, v in report["bodies"][g].items()
                                      if k not in ("picks_seen", "hairs_seen", "updo")}), flush=True)
    with open(os.path.join(out, "kit_check.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, indent=1)
    print("WROTE", os.path.join(out, "kit_check.json"))


main()
