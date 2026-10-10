"""`faces`: the face kit's review sheets (docs/faces.md): every style family of faces/styles.json in every expression
on the review heads of faces/review.json, built and rendered in headless Blender, with the numbers in
faces_report.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from .. import blender, common
from . import _assembly

NAME = "faces"
HELP = "the face kit: style families of eyes, brows and mouths rendered as review sheets (docs/faces.md)"
TIMEOUT = 3600
SCRIPT = "faces_render.py"
FACES = common.ROOT / "faces"
# A decal (brows, mouths, painted eyes) closer to the skin than this may flicker in the game: the check fails.
MIN_DECAL_CLEARANCE_MM = 0.2
# The same limit holds in motion: a decal's clearance from the skin as the pack actions of review.json "motion" deform
# it (the face parts are rigid on the Head bone; skin weighted partly to another bone slides under them).
MIN_MOTION_CLEARANCE_MM = MIN_DECAL_CLEARANCE_MM
# The face parts are bound to the Head bone: over the frame strip they may not move in its frame. With Head-only
# weights this holds by construction; it catches a part bound to another rig or bone.
MAX_HEAD_SPACE_MOVE_MM = 0.01
# The review heads' hair (or a hat) may hide at most this share of a face part from the front: brows under a fringe
# hide the brow-led expressions and judge the families unfairly.
MIN_VISIBLE_FRONT = 0.6
# The clay face kit's many-face check (--kit-check): faces_kit_check.py on the recipe's heads.
KIT_SCRIPT = "faces_kit_check.py"
KIT_RECIPE = common.ROOT / "recipes" / "clay_round_d.json"
KIT_CHECK_DEFAULT = 320
# A face over this many triangles fails (the lab's limit; the contract's budget is for the whole character).
KIT_MAX_TRIS = 2000


def styles_module() -> ModuleType:
    """tools/blender/faces_styles.py (pure Python), imported from the runner."""
    if str(_assembly.BLENDER_DIR) not in sys.path:
        sys.path.append(str(_assembly.BLENDER_DIR))
    import faces_styles  # type: ignore[import-not-found]

    return faces_styles


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--families", default="", help="comma list of family ids (default: all in the styles file)")
    parser.add_argument("--expressions", default="", help="comma list of expressions for the close sheets (default: all)")
    parser.add_argument(
        "--sheets", default="",
        help=f"comma list of {', '.join(styles_module().SHEETS)}, or none (build and measure only); default: all",
    )  # fmt: skip
    parser.add_argument("--out", type=Path, help="output folder (default tools/out/faces/)")
    parser.add_argument("--res", type=int, default=100, help="render size in percent (default 100; tests use less)")
    parser.add_argument("--styles", type=Path, default=FACES / "styles.json", help="the style families file")
    parser.add_argument("--review", type=Path, default=FACES / "review.json", help="what the sheets show")
    parser.add_argument("--check", action="store_true", help="only check the styles, review and heads files (no Blender)")
    parser.add_argument(
        "--kit-check", type=int, nargs="?", const=KIT_CHECK_DEFAULT, default=0, metavar="N",
        help=f"the clay face kit's check instead of the sheets: N random faces per body type (default {KIT_CHECK_DEFAULT})"
             " under random hair items, collisions, brows in the white, visible pokes, ears, nose and moustache; "
             "non-zero exit on a failure",
    )  # fmt: skip
    parser.add_argument("--recipe", type=Path, default=KIT_RECIPE, help="--kit-check: the recipe whose heads carry the faces")


def _pick(value: str, known: list[str], what: str) -> list[str]:
    chosen = [v for v in value.split(",") if v]
    unknown = [v for v in chosen if v not in known]
    if unknown:
        raise common.Failure(f"unknown {what} {', '.join(unknown)}; known: {', '.join(known)}")
    return chosen


def load_inputs(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Path]:
    """The checked styles, review settings and heads recipe; every problem fails the command before Blender starts."""
    fst = styles_module()
    try:
        styles = fst.load_styles(args.styles)
        review = fst.load_review(args.review, styles)
    except fst.StylesError as exc:
        raise common.Failure(str(exc)) from exc
    heads_path = (Path(args.review).resolve().parent / review["heads_recipe"]).resolve()
    recipes = _assembly.recipe_module()
    try:
        heads = recipes.load(heads_path, common.raw_dir())
    except recipes.RecipeError as exc:
        raise common.Failure(str(exc)) from exc
    ids = [c["id"] for c in heads["characters"]]
    problems = [f"{heads_path.name}: head {i} has no colours in {Path(args.review).name}" for i in ids if i not in review["heads"]]
    problems += [f"{Path(args.review).name}: head {i} is not in {heads_path.name}" for i in review["heads"] if i not in ids]
    if problems:
        raise common.Failure("; ".join(problems))
    return styles, review, heads, heads_path


def check_report(report: dict[str, Any]) -> list[str]:
    """What a finished run must show: every part weighted 1.0 to the Head bone alone with an Armature modifier,
    decals off the skin in the rest pose and in motion, face parts not hidden by the hair, and the face bound to the
    head over the strip."""
    problems = []
    for fid, fam in report.get("families", {}).items():
        for ename, heads in fam["expressions"].items():
            for hid, parts in heads.items():
                for part, info in parts.items():
                    where = f"{fid}/{ename}/{hid}/{part}"
                    if info["vertex_groups"] != ["Head"]:
                        problems.append(f"{where}: vertex groups {info['vertex_groups']}, want only Head")
                    if not info["armature"]:
                        problems.append(f"{where}: no Armature modifier")
                    if info.get("decal") and info["clearance_min_mm"] < MIN_DECAL_CLEARANCE_MM:
                        problems.append(f"{where}: a decal {info['clearance_min_mm']} mm off the skin "
                                        f"(at least {MIN_DECAL_CLEARANCE_MM} mm)")
                    moving = info.get("clearance_motion_min_mm")
                    if moving is not None and moving < MIN_MOTION_CLEARANCE_MM:
                        problems.append(f"{where}: a decal {moving} mm off the skin in {info.get('clearance_motion_where')} "
                                        f"(at least {MIN_MOTION_CLEARANCE_MM} mm in motion)")
                    if info.get("visible_front", 1.0) < MIN_VISIBLE_FRONT:
                        problems.append(f"{where}: the hair hides {round(100 * (1 - info['visible_front']))} % of it from the "
                                        f"front (at most {round(100 * (1 - MIN_VISIBLE_FRONT))} %)")
    for key, strip in report.get("strip", {}).items():
        if strip["face_in_head_space_max_move_mm"] > MAX_HEAD_SPACE_MOVE_MM:
            problems.append(f"strip {key}: the face moved {strip['face_in_head_space_max_move_mm']} mm in the Head bone's "
                            f"frame (parts bound to it move 0)")
    return problems


def summary(report: dict[str, Any]) -> list[str]:
    """One line per family: triangles per part (the range over the expressions), materials, decal clearance at rest
    and in motion, and the least share of a part the hair leaves visible."""
    lines = []
    for fid, fam in report.get("families", {}).items():
        tri: dict[str, list[int]] = {"eyes": [], "brows": [], "mouth": []}
        mats: dict[str, int] = {"eyes": 0, "brows": 0, "mouth": 0}
        clear, moving, vis = [], [], []
        for heads in fam["expressions"].values():
            for parts in heads.values():
                for part, info in parts.items():
                    tri[part].append(info["triangles"])
                    mats[part] = max(mats[part], info["materials"])
                    if info.get("decal"):
                        clear.append(info["clearance_min_mm"])
                    if info.get("clearance_motion_min_mm") is not None:
                        moving.append(info["clearance_motion_min_mm"])
                    if info.get("visible_front") is not None:
                        vis.append(info["visible_front"])
        span = ", ".join(f"{p} {min(v)}-{max(v)}" if min(v) != max(v) else f"{p} {v[0]}" for p, v in tri.items() if v)
        lines.append(f"{fid} ({fam['name']}): triangles {span}; materials {mats['eyes']}/{mats['brows']}/{mats['mouth']}; "
                     f"decals at least {min(clear) if clear else '-'} mm off the skin, "
                     f"{min(moving) if moving else '-'} mm in motion; hair hides at most "
                     f"{round(100 * (1 - min(vis))) if vis else '-'} % of a part")
    return lines


def distance_lines(report: dict[str, Any]) -> list[str]:
    """Per family and distance-sheet head: how many screen pixels the neutral face covers at each distance, and how
    many change when it blinks or talks (0: the game cannot show it there)."""
    dist = report.get("distance", {})
    lines = []
    for fid, fp in dist.get("face_pixels", {}).items():
        heads = sorted({k.split("_neutral_")[0] for k in fp if "_neutral_" in k})
        parts = []
        for hid in heads:
            ds = sorted({k.rsplit("_", 1)[1] for k in fp if k.startswith(hid + "_neutral_")}, key=lambda d: float(d[:-1]))
            row = lambda key: "/".join(str(fp.get(f"{hid}_{key}_{d}", "-")) for d in ds)  # noqa: E731
            parts.append(f"{hid} face {row('neutral')}, blink {row('blink_change')}, talk {row('talk_change')} px at {'/'.join(ds)}")
        lines.append(f"{fid}: " + "; ".join(parts))
    return lines


def kit_problems(report: dict[str, Any]) -> list[str]:
    """The failures in a kit_check.json report: any face with a collision, a brow in the white, a visible poke, an ear
    in the hair, a pupil sinking into the white, a nose meeting a pupil or the moustache, a nose below the mouth's top,
    brows sunk into the eyes or hidden from the front (checks.brow_visibility, art #42 round 3) or over KIT_MAX_TRIS
    triangles."""
    out = []
    for g, b in report["bodies"].items():
        where = f"{g} ({b['head']})"
        if b["faces"] != b["requested"]:
            out.append(f"{where}: {b['faces']} of {b['requested']} faces measured")
        for key, what in (("faces_with_collision", "faces with a collision"), ("brow_in_white_faces", "faces with a brow in the white"),
                          ("pokes", "faces with a visible brow poke"), ("ear_hair_overlap_faces", "faces with an ear in the hair"),
                          ("meets_pupils_faces", "faces whose nose meets a pupil"),
                          ("brow_hidden_faces", "faces whose brows sink into the eyes or hide from the front")):
            if b.get(key):
                out.append(f"{where}: {b[key]} {what}")
        ms = b["moustache_seat"]
        if ms["overlap_faces"] or ms["cannot_clear_faces"]:
            out.append(f"{where}: moustache seat: {ms['overlap_faces']} faces with the nose on it, {ms['cannot_clear_faces']} not cleared")
        if b["faces"] and b["nose_above_mouth_mm_min"] < 0:
            out.append(f"{where}: the nose dips {-b['nose_above_mouth_mm_min']} mm below the mouth's top")
        if b["look_sag_mm_max"] > 0:
            out.append(f"{where}: a pupil sinks {b['look_sag_mm_max']} mm into the white as the eyes look around")
        if b["tris_max"] > KIT_MAX_TRIS:
            out.append(f"{where}: a face of {b['tris_max']} triangles (at most {KIT_MAX_TRIS})")
    return out


def kit_summary(report: dict[str, Any]) -> list[str]:
    lines = []
    for g, b in report["bodies"].items():
        ms = b["moustache_seat"]
        lines.append(f"{g} on {b['head']}: {b['faces']} faces under {len(b['hairs_seen'])} hairs; collisions {b['faces_with_collision']}, "
                     f"brow in white {b['brow_in_white_faces']}, visible pokes {b['pokes']}, ear/hair {b['ear_hair_overlap_faces']}, "
                     f"nose meets pupils {b['meets_pupils_faces']}; nose above mouth min {b['nose_above_mouth_mm_min']} mm; "
                     f"look sag max {b['look_sag_mm_max']} mm; moustache faces {ms['faces']} (nose clear min "
                     f"{ms['nose_clear_mm_min']} mm); brows tucked {b['brow_tuck_faces']}, hidden {b.get('brow_hidden_faces', 0)} "
                     f"(eye clear min {b.get('brow_eye_clear_mm_min', '-')} mm, seen min {b.get('brow_seen_min', '-')}); tris max {b['tris_max']} "
                     f"mean {b['tris_mean']}; {b['seconds']} s")
    return lines


def run_kit_check(args: argparse.Namespace) -> int:
    if args.kit_check < 1:
        raise common.Failure("--kit-check N needs N >= 1")
    out = (args.out or common.OUT / "faces_kit").resolve()
    script_args = ["--recipe", str(Path(args.recipe).resolve()), "--raw", str(common.raw_dir()), "--out", str(out),
                   "--n", str(args.kit_check)]
    common.say(f"faces --kit-check: {args.kit_check} faces per body type on {Path(args.recipe).name} -> {out.as_posix()}")
    blender.run_script(KIT_SCRIPT, script_args, timeout=TIMEOUT)
    path = out / "kit_check.json"
    if not path.is_file():
        raise common.Failure(f"{KIT_SCRIPT} wrote no {path}")
    report = json.loads(path.read_text(encoding="utf-8"))
    for line in kit_summary(report):
        common.say(f"  {line}")
    problems = kit_problems(report)
    for line in problems:
        common.bad(line)
    if problems:
        raise common.Failure(f"{len(problems)} problem(s) in {path}")
    common.ok(f"kit check: {sum(b['faces'] for b in report['bodies'].values())} faces pass; report: {path.as_posix()}")
    return 0


def run(args: argparse.Namespace) -> int:
    if args.kit_check:
        return run_kit_check(args)
    styles, _, heads, heads_path = load_inputs(args)
    families = _pick(args.families, list(styles["families"]), "families")
    expressions = _pick(args.expressions, styles["expressions"], "expressions")
    sheets = ["none"] if args.sheets == "none" else _pick(args.sheets, list(styles_module().SHEETS), "sheets")
    if not 5 <= args.res <= 100:
        raise common.Failure("--res must be from 5 to 100 (percent)")
    common.ok(f"{Path(args.styles).name}: {len(styles['families'])} families, {len(styles['expressions'])} expressions; "
              f"{heads_path.name}: {', '.join(c['id'] for c in heads['characters'])}")
    if args.check:
        return 0
    out = (args.out or common.OUT / "faces").resolve()
    script_args = ["--styles", str(Path(args.styles).resolve()), "--review", str(Path(args.review).resolve()),
                   "--raw", str(common.raw_dir()), "--out", str(out), "--res", str(args.res)]
    if families:
        script_args += ["--families", ",".join(families)]
    if expressions:
        script_args += ["--expressions", ",".join(expressions)]
    if args.sheets:
        script_args += ["--sheets", ",".join(sheets)]
    common.say(f"faces: {', '.join(families) or 'every family'} -> {out.as_posix()}")
    blender.run_script(SCRIPT, script_args, timeout=TIMEOUT)
    report_path = out / "faces_report.json"
    if not report_path.is_file():
        raise common.Failure(f"{SCRIPT} wrote no {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    for line in summary(report):
        common.say(f"  {line}")
    for line in distance_lines(report):
        common.say(f"  {line}")
    for hid, skin in report.get("face_skin_to_head", {}).items():
        common.say(f"  face skin {hid}: {skin['vertices']} vertices given to the Head bone alone "
                   f"(the largest weight moved from Neck: {skin['largest_weight_moved']})")
    for key, sp in report.get("spacing", {}).items():
        apart = ", ".join(f"{hid} {mm}" for hid, mm in sp["eye_centres_apart_mm"].items())
        common.say(f"  spacing {key}: eye centres {apart} mm apart; decals at least {sp['decal_clearance_min_mm']} mm off the skin")
    for key, strip in report.get("strip", {}).items():
        common.say(f"  strip {key}: {strip['action']} frames {strip['frames'][0]}-{strip['frames'][-1]}, the face moved "
                   f"{strip['face_in_head_space_max_move_mm']} mm in the Head bone's space")
    problems = check_report(report)
    for line in problems:
        common.bad(line)
    if problems:
        raise common.Failure(f"{len(problems)} problem(s) in {report_path}")
    common.ok(f"{report['renders']} renders; report: {report_path.as_posix()}")
    return 0
