"""`gate2`: a garment build's Gate 2 checks (art #196; docs/clothes.md, "Gate 2"): the spec numbers on the build, the
silhouette overlap per view against the concept, the motion numbers per clip (slip, flatness, stretch, pokes) and the
review page. Headless Blender dumps the build (garment_spec_probe.py) and measures its motion (garment_motion.py);
the rest is plain Python (tools/blender/garment_gate2.py)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .. import blender, common

NAME = "gate2"
HELP = "a garment build's Gate 2 checks and review page against its spec (docs/clothes.md, \"Gate 2\")"
TIMEOUT = 3600


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--spec", required=True, type=Path, help="specs/<garment>_dims.toml with its [gate2] section")
    parser.add_argument("--body", required=True, type=Path, help="garment_spec_probe.py's dump of the undressed character")
    parser.add_argument("--blend", required=True, type=Path, help="the dressed build's .blend")
    parser.add_argument("--dress", type=Path, help="its dress.json (recorded only: every size is measured on the mesh)")
    parser.add_argument("--poke", type=Path, help="clothes_proof.py's poke.json of the build (the pokes per clip)")
    parser.add_argument("--video", type=Path, help="`frames --video Walk,Jog_Fwd --video-camera ...`'s output folder")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--probe", type=Path, help="the build's dump if made already (else made into OUT/probe.json)")
    parser.add_argument("--motion", type=Path, help="garment_motion.py's result if made already (else OUT/motion.json)")
    parser.add_argument("--tag", default="build")


def run(args: argparse.Namespace) -> int:
    sys.path.insert(0, str(blender.SCRIPTS))
    import garment_gate2 as GG
    import garment_spec as S

    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    blend = args.blend.resolve()
    if not blend.is_file():
        raise common.Failure(f"no build {blend.as_posix()}")
    probe = args.probe or out / "probe.json"
    if not args.probe:
        common.say(f"gate2: the build's rest dump -> {probe.as_posix()}")
        blender.run_script("garment_spec_probe.py", ["--blend", str(blend), "--out", str(probe)], timeout=TIMEOUT)
    motion = args.motion or out / "motion.json"
    if not args.motion:
        spec = S.load_spec(args.spec)
        build = S.load_probe(probe)
        body = S.load_probe(args.body)
        sec = S.Sections(body, [spec["body"]["mesh"]])
        meas, _ = GG.spec_numbers(spec, build, sec)
        cfg = out / "motion_config.json"
        cfg.write_text(json.dumps(GG.motion_config(spec, meas, blend.as_posix()), indent=1), encoding="utf-8")
        common.say(f"gate2: the motion numbers in headless Blender -> {motion.as_posix()}")
        blender.run_script("garment_motion.py", ["--config", str(cfg), "--out", str(motion)], timeout=TIMEOUT)
    argv = ["--spec", str(args.spec), "--body", str(args.body), "--probe", str(probe), "--blend", str(blend), "--out", str(out), "--motion", str(motion), "--tag", args.tag]
    if args.poke:
        argv += ["--poke", str(args.poke)]
    if args.dress:
        argv += ["--dress", str(args.dress)]
    if args.video:
        argv += ["--video", str(args.video)]
    code = GG.run(GG.parser().parse_args(argv))
    (common.ok if code == 0 else common.warn)(f"gate2: {'PASS' if code == 0 else 'NOT PASSED'}; page "
                                              f"{(out / 'index.html').as_posix()}")
    return code
