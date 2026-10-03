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
        "locomotion at the game's speeds, close-ups of the feet")
STEPS = ("inventory", "clips", "pairs", "rates", "feet", "sheets", "table", "all")


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("step", choices=STEPS, help="what to make; 'all' runs every step in order")
    parser.add_argument("--body", choices=(*_anim.BODIES, "both"), default="both", help="body type (default both)")
    parser.add_argument("--clips", default="all",
                        help="clips as pack:<name>,ual:<name>,ual2:<name> or a layered <base>|<upper> (default all: "
                             "every clip and the settings' [layer] clips)")
    parser.add_argument("--sources", default="all",
                        help="clips, pairs, rates: only these sources' clips, and the pairs and rates rows that play "
                             "one, e.g. ual2 (comma-separated: pack, ual, ual2; default all); not with --clips")
    parser.add_argument("--only", default="",
                        help="pairs, feet: comma-separated pair or [[feet]] row names (a pack clip name for art #20's pairs, e.g. Wave; "
                             "ual2_carry for art #24's; default every pair)")
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
    for key, ual in inv["ual"].items():  # each library in place and with root motion ("ual", "ual_rm", "ual2", ...)
        moving = sum(c["root_travel_m"] > 0 for c in ual["clips"].values())
        common.ok(f"{Path(ual['file']).name}: {len(ual['clips'])} clips, {moving} with root motion")
    common.say(f"inventory: {path}")
    return inv


def body_args(cfg: dict, body: str, rm: bool = False) -> list[str]:
    """The Blender script's arguments for a body type: the character and every library (with rm, also their
    root-motion files)."""
    out = ["--body", body, "--character", str(_anim.raw_path(cfg["bodies"][body]["character"])),
           "--raw", str(common.raw_dir())]
    for key, lib in _anim.libraries(cfg).items():
        out += ["--lib", f"{key}={_anim.raw_path(lib['file'])}"]
        for extra in lib["extra"]:
            _anim.raw_path(extra)  # refuse a missing file before Blender starts
        if rm and lib["rm"]:
            out += ["--lib-rm", f"{key}={_anim.raw_path(lib['rm'])}"]
    return out


def only_sources(args: argparse.Namespace, cfg: dict) -> set[str] | None:
    known = _anim.sources(cfg)
    want = {s.strip() for s in args.sources.split(",") if s.strip()} if args.sources not in ("", "all") else None
    if want is not None and (not want or want - known):
        raise common.Failure(f"unknown sources in --sources {args.sources}; known: {', '.join(sorted(known))}")
    return want


def clips(args: argparse.Namespace, out: Path, cfg: dict, bodies: list[str]) -> None:
    inv_path = out / "inventory.json"
    inv = json.loads(inv_path.read_text(encoding="utf-8")) if inv_path.is_file() else inventory(out)
    only = only_sources(args, cfg)
    if any(lib not in inv["ual"] for lib in _anim.libraries(cfg)):  # an older inventory without a new library
        inv = inventory(out)
    jobs = []
    for body in bodies:
        if args.clips == "all":  # a full run replaces every earlier measure of the body type (of its sources)
            keys = _anim.clip_keys(inv, body, only) + _anim.layered_keys(cfg, only)
            prefix = _anim.run_tag(only)
            stale = f"{body}_*.json" if only is None else f"{body}{prefix}*.json"
            for old in [*(out / "metrics").glob(stale), *(out / "metrics").glob(f"{body}_part_c*.json")]:
                old.unlink(missing_ok=True)
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
    jobs = [["pairs", *body_args(cfg, body), "--out", str(out), "--only", args.only, "--sources", args.sources]
            for body in bodies]
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        for future in [pool.submit(blender.run_script, "anim_review.py", job, 7200) for job in jobs]:
            future.result()
    common.ok(f"side-by-side pairs in {out / 'pairs'}")


def rates(args: argparse.Namespace, out: Path, cfg: dict, bodies: list[str]) -> None:
    jobs = [["rates", *body_args(cfg, body, rm=True), "--out", str(out), "--sources", args.sources] for body in bodies]
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


def feet(args: argparse.Namespace, out: Path, cfg: dict, bodies: list[str]) -> None:
    """Close-ups of the feet (art #25): each [[feet]] clip with rigid shoes against the toe bones."""
    jobs = [["feet", *body_args(cfg, body), "--out", str(out), "--only", args.only] for body in bodies]
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        for future in [pool.submit(blender.run_script, "anim_review.py", job, 7200) for job in jobs]:
            future.result()
    for body in bodies:
        for path in sorted((out / "feet" / body).glob("*.json")):
            for key, lanes in json.loads(path.read_text(encoding="utf-8")).items():
                if "rigid_shoes" not in lanes:  # a set of any clips (art #25's comparisons)
                    for lane, res in lanes["lanes"].items():
                        t, slide = res.get("toe", {}), res["foot_sliding"]
                        common.ok(f"{body} {key} {lane}: the front of the shoe at a 20 deg heel lift "
                                  f"{t.get('front_pitch_at_20_deg_lift')} deg, heel lift with the front level "
                                  f"{t.get('heel_lift_front_level_max_deg')} deg, foot sliding "
                                  f"{slide.get('slide_mean_cm_s')} cm/s, lowest vertex "
                                  f"{res.get('lowest_vertex_cm', {}).get('min')} cm")
                    continue
                r, t = lanes["rigid_shoes"].get("toe", {}), lanes["toe_bones"].get("toe", {})
                common.ok(f"{body} {key}: the front of the shoe at a 20 deg heel lift "
                          f"{r.get('front_pitch_at_20_deg_lift')} -> {t.get('front_pitch_at_20_deg_lift')} deg, heel "
                          f"lift with the front level {r.get('heel_lift_front_level_max_deg')} -> "
                          f"{t.get('heel_lift_front_level_max_deg')} deg, bend {r.get('bend_in_contact_max_deg')} -> "
                          f"{t.get('bend_in_contact_max_deg')} deg (rigid shoes -> toe bones)")
    common.ok(f"close-ups of the feet in {out / 'feet'}")


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
    only_sources(args, cfg)  # refuse an unknown source before any Blender run
    if args.clips != "all" and args.sources not in ("", "all"):
        raise common.Failure("--clips names the clips itself: give --clips or --sources, not both")
    bodies = list(_anim.BODIES) if args.body == "both" else [args.body]
    steps = (("inventory", "clips", "pairs", "rates", "feet", "sheets", "table") if args.step == "all"
             else (args.step,))
    for step in steps:
        common.say(f"== {step}")
        if step == "inventory":
            inventory(out)
        elif step == "clips":
            clips(args, out, cfg, bodies)
        elif step == "pairs":
            pairs(args, out, cfg, bodies)
        elif step == "rates":
            rates(args, out, cfg, bodies)
        elif step == "feet":
            feet(args, out, cfg, bodies)
        elif step == "sheets":
            sheets(out)
        else:
            write_table(out)
    return 0
