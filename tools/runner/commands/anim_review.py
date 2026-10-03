"""`anim-review`: judges the animations in motion: the inventory, the measures, frame strips, MP4 clips and
side-by-side comparisons of the Ultimate Modular pack's clips and the retargeted Universal Animation Library."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .. import blender, common
from . import _anim

NAME = "anim-review"
HELP = ("judge animations in motion: inventory, measures, frame strips, MP4 clips, side-by-side pairs, "
        "locomotion at the game's speeds")
STEPS = ("inventory", "clips", "pairs", "rates", "sheets", "table", "all")


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("step", choices=STEPS, help="what to make; 'all' runs every step in order")
    parser.add_argument("--body", choices=(*_anim.BODIES, "both"), default="both", help="body type (default both)")
    parser.add_argument("--clips", default="all", help="clips as pack:<name>,ual:<name> (default all)")
    parser.add_argument("--only", default="", help="pairs: comma-separated pack clip names (default every pair)")
    parser.add_argument("--jobs", type=int, default=4, help="parallel Blender processes per body type (default 4)")
    parser.add_argument("--out", type=Path, help="output folder (default tools/out/anim-review)")
    parser.add_argument("--no-video", action="store_true", help="clips: measures and strips only")
    parser.add_argument("--no-strips", action="store_true", help="clips: measures and videos only")


def inventory(out: Path) -> dict:
    path = out / "inventory.json"
    blender.run_script("anim_inventory.py", ["--raw", str(common.raw_dir()), "--config", str(_anim.CONFIG),
                                             "--out", str(path)], timeout=1800)
    inv = json.loads(path.read_text(encoding="utf-8"))
    for body in _anim.BODIES:
        acts = inv["pack"][body]["actions"]
        same = sum(a["identical_in_all_files"] for a in acts.values())
        common.ok(f"{body}: {len(acts)} pack actions, {same} identical in all {len(inv['pack'][body]['files'])} files")
    for key, ual in inv["ual"].items():
        moving = sum(c["root_travel_m"] > 0 for c in ual["clips"].values())
        common.ok(f"{Path(ual['file']).name}: {len(ual['clips'])} clips, {moving} with root motion")
    common.say(f"inventory: {path}")
    return inv


def body_args(cfg: dict, body: str) -> list[str]:
    return ["--body", body, "--character", str(_anim.raw_path(cfg["bodies"][body]["character"])),
            "--ual", str(_anim.raw_path(cfg["ual"]))]


def clips(args: argparse.Namespace, out: Path, cfg: dict, bodies: list[str]) -> None:
    inv_path = out / "inventory.json"
    inv = json.loads(inv_path.read_text(encoding="utf-8")) if inv_path.is_file() else inventory(out)
    jobs = []
    for body in bodies:
        if args.clips == "all":  # a full run replaces every earlier measure of the body type
            keys, prefix = _anim.clip_keys(inv, body), "_c"
            for old in (out / "metrics").glob(f"{body}*.json"):
                old.unlink()
        else:  # a partial run adds files that sort after the full run's, so merge() lets them win
            keys, prefix = args.clips.split(","), "_part_c"
            for old in (out / "metrics").glob(f"{body}_part_c*.json"):
                old.unlink()
        for i, chunk in enumerate(_anim.chunks(keys, args.jobs, _anim.clip_seconds(inv, body))):
            extra = ["--clips", ",".join(chunk), "--tag", f"{prefix}{i}"]
            extra += ["--no-video"] if args.no_video else []
            extra += ["--no-strips"] if args.no_strips else []
            jobs.append(["clips", *body_args(cfg, body), "--out", str(out), *extra])
    common.say(f"{len(jobs)} Blender processes")
    with ThreadPoolExecutor(max_workers=max(1, args.jobs) * len(bodies)) as pool:
        for future in [pool.submit(blender.run_script, "anim_review.py", job, 7200) for job in jobs]:
            future.result()
    common.ok(f"clips measured and rendered into {out}")


def pairs(args: argparse.Namespace, out: Path, cfg: dict, bodies: list[str]) -> None:
    jobs = [["pairs", *body_args(cfg, body), "--out", str(out), "--only", args.only] for body in bodies]
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        for future in [pool.submit(blender.run_script, "anim_review.py", job, 7200) for job in jobs]:
            future.result()
    common.ok(f"side-by-side pairs in {out / 'pairs'}")


def rates(out: Path, cfg: dict, bodies: list[str]) -> None:
    jobs = [["rates", *body_args(cfg, body), "--ual-rm", str(_anim.raw_path(cfg["ual_rm"])), "--out", str(out)]
            for body in bodies]
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        for future in [pool.submit(blender.run_script, "anim_review.py", job, 7200) for job in jobs]:
            future.result()
    for body in bodies:
        report = json.loads((out / "rates" / body / "rates.json").read_text(encoding="utf-8"))
        for name, row in report["rows"].items():
            lanes = ", ".join(f"{lane['clip']} x{lane['rate']} ({lane['cadence_steps_s']} steps/s)"
                              for lane in row["lanes"])
            common.ok(f"{body} {name}: {lanes}")
    common.ok(f"the game's speeds in {out / 'rates'}")


def sheets(out: Path) -> None:
    stems = sorted({p.stem for p in (out / "strips").glob("*/*.png")}, key=lambda s: (not s.startswith("pack"), s))
    names = out / "tmp" / "sheet_names.txt"
    names.parent.mkdir(parents=True, exist_ok=True)
    names.write_text("\n".join(stems) + "\n", encoding="utf-8")
    blender.run_script("anim_review.py", ["sheets", "--out", str(out), "--names", str(names)], timeout=1800)
    common.ok(f"review sheets in {out / 'sheets'}")


def write_table(out: Path) -> None:
    merged = _anim.merge(out / "metrics")
    if not merged:
        raise common.Failure(f"no measures in {out / 'metrics'}: run the clips step first")
    (out / "metrics.json").write_text(json.dumps(merged, indent=1) + "\n", encoding="utf-8")
    (out / "metrics.md").write_text(_anim.table(merged), encoding="utf-8")
    common.ok(f"{sum(len(v) for v in merged.values())} clips measured: {out / 'metrics.json'}, {out / 'metrics.md'}")


def run(args: argparse.Namespace) -> int:
    if args.jobs < 1:
        raise common.Failure("--jobs must be at least 1")
    cfg = _anim.load_config()
    out = (args.out or common.OUT / "anim-review").resolve()
    out.mkdir(parents=True, exist_ok=True)
    bodies = list(_anim.BODIES) if args.body == "both" else [args.body]
    steps = ("inventory", "clips", "pairs", "rates", "sheets", "table") if args.step == "all" else (args.step,)
    for step in steps:
        common.say(f"== {step}")
        if step == "inventory":
            inventory(out)
        elif step == "clips":
            clips(args, out, cfg, bodies)
        elif step == "pairs":
            pairs(args, out, cfg, bodies)
        elif step == "rates":
            rates(out, cfg, bodies)
        elif step == "sheets":
            sheets(out)
        else:
            write_table(out)
    return 0
