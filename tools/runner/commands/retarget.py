"""`retarget`: bakes Universal Animation Library clips onto an Ultimate Modular armature in headless Blender."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .. import blender, common
from . import _anim

NAME = "retarget"
HELP = "bake Universal Animation Library clips onto the Ultimate Modular armature of a body type (docs/animations.md)"

REST_TOLERANCE = {"max_offset_mm": 0.01, "max_rotation_deg": 0.01}


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--body", choices=_anim.BODIES, default="men", help="the body type (default men)")
    parser.add_argument("--target", type=Path, help="target GLB (default: the body type's donor in anim_review.toml)")
    parser.add_argument("--library", default="ual",
                        help="the source library of the review settings: ual (UAL1, the default) or ual2 (art #24)")
    parser.add_argument("--source", type=Path, help="source GLB (default: the library's in-place GLB, raw folder)")
    parser.add_argument("--map", type=Path, help="bone map (default tools/blender/retarget_maps/ual_um.toml)")
    parser.add_argument("--clips", default="all", help="comma-separated source clip names (default all)")
    parser.add_argument("--out", type=Path,
                        help="output folder (default tools/out/retarget/<body>; another library: .../<library>/<body>)")
    parser.add_argument("--no-ik", action="store_true", help="skip the leg IK that keeps the source's foot contacts")
    parser.add_argument("--blend", action="store_true", help="also save the character with the baked actions")
    parser.add_argument("--floor", action="store_true",
                        help="also measure each clip's lowest vertex, on the target and on the source's own mesh")


def run(args: argparse.Namespace) -> int:
    cfg = _anim.load_config()
    libs = _anim.libraries(cfg)
    if args.library not in libs:
        raise common.Failure(f"no library {args.library!r} in the review settings; known: {', '.join(libs)}")
    target = args.target or _anim.raw_path(cfg["bodies"][args.body]["character"])
    source = args.source or _anim.raw_path(libs[args.library]["file"])
    for path in (target, source):
        if not Path(path).is_file():
            raise common.Failure(f"no file {path}")
    default = common.OUT / "retarget" / (args.body if args.library == "ual" else f"{args.library}/{args.body}")
    out = (args.out or default).resolve()
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "retarget_report.json"
    report_path.unlink(missing_ok=True)
    script_args = ["--source", str(source), "--target", str(target), "--out", str(out), "--clips", args.clips,
                   "--prefix", libs[args.library]["label"]]
    if args.map:
        script_args += ["--map", str(args.map.resolve())]
    if args.no_ik:
        script_args.append("--no-ik")
    if args.blend:
        script_args.append("--blend")
    if args.floor:
        script_args.append("--floor")
    blender.run_script("retarget.py", script_args, timeout=1800)
    if not report_path.is_file():
        raise common.Failure(f"retarget.py wrote no {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    rest = report["rest_check"]
    common.say(f"{Path(source).name} -> {Path(target).name}: translation scale {report['translation_scale']} "
               f"(hip joints {report['hip_height_m']['source']} m -> {report['hip_height_m']['target']} m)")
    bad = {k: v for k, v in rest.items() if v > REST_TOLERANCE[k]}
    if bad:
        common.bad(f"the source rest does not land on the target rest: {rest}", "check the bone map and the rigs")
        return 1
    common.ok(f"rest check: {rest['max_offset_mm']} mm, {rest['max_rotation_deg']} degrees")
    misses = {n: c["ik_miss_mm"] for n, c in report["clips"].items() if c["ik_miss_mm"] > 1.0}
    common.ok(f"{len(report['clips'])} clips baked in {report['seconds_spent']} s")
    if misses:
        common.warn(f"legs short of the source's ankle path (mm, the target's legs are too short there): {misses}")
    if args.floor:
        deep = {n: f"{c['lowest_cm']} (source {c['source_lowest_cm']})" for n, c in report["clips"].items()
                if c["lowest_cm"] < -1.0}
        common.say(f"lowest vertex below -1 cm, target (source's own mesh, scaled): {deep or 'none'}")
    if "blend" in report:
        common.say(f"blend: {report['blend']}")
    common.say(f"report: {report_path}")
    return 0
