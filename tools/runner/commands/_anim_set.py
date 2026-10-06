"""Helpers of the anim-set command (art #33; docs/animations.md, "Animation sets"): the set's settings (read and checked
by tools/blender/anim_set_cfg.py, shared with Blender) and the set's own checks on what Blender built, what the export
wrote and what Godot imported. Standard library only."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from .. import common
from . import _anim, _godot

if str(_anim.BLENDER_DIR) not in sys.path:
    sys.path.append(str(_anim.BLENDER_DIR))
import anim_set_cfg  # noqa: E402  (tools/blender, pure)

LENGTH_TOLERANCE_S = 1e-3  # an exported clip's length against its frames / 30
SEAM_MM, SEAM_DEG = 0.5, 0.5  # a closed loop's last frame against its first (export.json's seams)
IN_PLACE_M = 0.05  # a loop's Body travel from its first frame to its last
# warnings the build table prints (docs/animations.md, the measures that decide; the review judges them)
FLOOR_WARN_CM = -1.2
STRIDE_FITS = ("warn", "fail")
FACING_WARN_DEG = 5.0  # a locomotion loop's hips or head facing off the game's aim
SEAM_STEP_WARN = 1.5  # a loop's last step onto its first against its median frame step


def load(cfg: dict, key: str) -> tuple[Path, dict]:
    """A set of the review settings' [sets] and its checked settings; raises Failure when it is unknown or invalid."""
    sets = cfg.get("sets", {})
    if key not in sets:
        raise common.Failure(f"no set {key!r} in the review settings' [sets]; known: {', '.join(sets) or 'none'}")
    path = _anim.set_file(cfg, key)
    try:
        data = anim_set_cfg.load(path)
    except (OSError, ValueError) as error:
        raise common.Failure(f"cannot read {path}: {error}") from error
    errors = anim_set_cfg.check(data, _anim.sources(cfg) - set(sets))
    if errors:
        raise common.Failure(f"{path.name}: " + "; ".join(errors))
    return path, data


def selected(data: dict, clips: str) -> list[str]:
    """The clips a run builds: "all", or the named ones (with the clips they are made from); raises Failure on an
    unknown name."""
    try:
        return anim_set_cfg.closure(data, None if clips == "all" else [c for c in clips.split(",") if c])
    except ValueError as error:
        raise common.Failure(str(error)) from error


def reported(data: dict, clips: str) -> list[str]:
    """The clips a build reports: all of them, or the named ones (not the clips they are made from, which a partial
    build makes but does not report)."""
    return selected(data, "all") if clips == "all" else [c for c in clips.split(",") if c]


def check_build(report: dict, data: dict, names: list[str]) -> list[str]:
    """Problems with Blender's build_report.json: a clip missing, a loop that travels or is not closed by its source or
    a cycle step (the build refuses that), a clip whose length is not its frames."""
    problems = []
    table = anim_set_cfg.clips(data)
    for name in names:
        rep = report.get("clips", {}).get(name)
        if rep is None:
            problems.append(f"{name}: not built")
            continue
        if rep["loop"] != table[name]["loop"]:
            problems.append(f"{name}: built with loop {rep['loop']}, the settings say {table[name]['loop']}")
        if abs(rep["seconds"] - rep["frames"] / anim_set_cfg.FPS) > LENGTH_TOLERANCE_S:
            problems.append(f"{name}: {rep['seconds']} s for {rep['frames']} frames")
        if rep["loop"] and rep["travel_left_m"] is not None and rep["travel_left_m"] >= IN_PLACE_M:
            problems.append(f"{name}: a loop that travels {rep['travel_left_m']} m (in place: under {IN_PLACE_M} m)")
    return problems


def check_export(info: dict, report: dict) -> list[str]:
    """Problems with the export (<stem>.export.json) against the build: every exported clip an action of its length,
    nothing else, every loop closed (its last frame its first, within 0.5 mm and 0.5 degrees)."""
    problems = []
    want = report.get("exported", [])
    actions = info.get("actions", {})
    fps = info.get("fps")
    if fps != anim_set_cfg.FPS:
        problems.append(f"the saved scene runs at {fps} fps, not {anim_set_cfg.FPS}")
    if sorted(actions) != sorted(want):
        problems.append(f"actions {sorted(set(actions) - set(want))} are not the set's; "
                        f"{sorted(set(want) - set(actions))} are missing")
    for name in want:
        if name not in actions:
            continue
        start, end = actions[name]
        frames = report["clips"][name]["frames"]
        if end - start != frames:
            problems.append(f"{name}: frames {start} to {end}, built {frames}")
        seam = info.get("seams", {}).get(name)
        if report["clips"][name]["loop"] and seam and (seam["position_mm"] > SEAM_MM or seam["rotation_deg"] > SEAM_DEG):
            problems.append(f"{name}: a loop whose last frame is {seam['position_mm']} mm and {seam['rotation_deg']} "
                            f"degrees from its first")
    return problems


def check_godot(godot: dict, report: dict) -> list[str]:
    """Problems with Godot's import (godot-check's report.json): every exported clip under the name Godot gives it
    (a loop's _Loop dropped), as long as its frames, looping (LINEAR) exactly when the set says it loops."""
    problems = []
    anims = godot.get("animations", {})
    for name in report.get("exported", []):
        rep = report["clips"][name]
        gname, suffixed = _godot.godot_name(name)
        a = anims.get(gname)
        if a is None:
            problems.append(f"{name}: no animation {gname!r} in Godot (it has {', '.join(sorted(anims))})")
            continue
        if abs(a["length"] - rep["frames"] / anim_set_cfg.FPS) > LENGTH_TOLERANCE_S:
            problems.append(f"{name}: {a['length']:.4f} s in Godot, {rep['frames']} frames built")
        loops = bool(a.get("loop_mode", 0))
        if loops != rep["loop"]:
            problems.append(f"{name}: imports as {gname} with loop_mode {a.get('loop_mode')} "
                            f"({'loops' if loops else 'plays once'}), the set says loop = {str(rep['loop']).lower()}")
        if suffixed != rep["loop"]:
            problems.append(f"{name}: the name's loop suffix and loop = {str(rep['loop']).lower()} disagree")
    return problems


def warnings(report: dict) -> list[str]:
    """What the build table flags for the review: stride fits outside the warn range, auto searches that found no
    angle, floors below -1.2 cm on a clip that is not lying, a locomotion loop (one with a speed) whose hips or head
    face more than 5 degrees off the aim, a loop whose step onto its first frame is over 1.5 median frame steps, a
    bone that snaps in one frame between two held poses (anim_math.one_frame_pops)."""
    out = []
    for name, rep in report.get("clips", {}).items():
        if rep["loop"] and rep.get("speed_m_s"):
            hips, head = rep.get("facing_mean_deg"), rep.get("head_facing_mean_deg")
            if any(a is not None and abs(a) > FACING_WARN_DEG for a in (hips, head)):
                out.append(f"{name}: faces {hips} degrees (hips) and {head} (head) off the aim on average")
        ratio = rep.get("seam_step_ratio")
        if rep["loop"] and ratio is not None and ratio > SEAM_STEP_WARN:
            out.append(f"{name}: its step onto the first frame is {ratio} median frame steps")
        if rep.get("pops"):
            top = ", ".join(f"{b} {d} deg at frame {f}" for b, f, d in rep["pops"][:3])
            out.append(f"{name}: {rep.get('pop_count', len(rep['pops']))} one-frame pop(s), the largest {top}")
        for step in rep["steps"]:
            if step.get("fit") in STRIDE_FITS:
                out.append(f"{name}: stride scale {step['scale']} ({step['fit']}): {step['cadence']} steps/s of "
                           f"{step['step_m']} m")
            if step.get("found") is False:
                out.append(f"{name}: {step['op']} found no angle up to its max_deg (used {step.get('deg')})")
        low = rep.get("lowest_cm")
        if low is not None and low < FLOOR_WARN_CM:
            out.append(f"{name}: lowest vertex {low} cm at {rep['lowest_at_s']} s")
    return out


def table(report: dict) -> str:
    """The build as a Markdown table, a row per clip."""
    lines = ["| Clip | Source | s | Loop | Export | Speed m/s | Travel left m | Yaw drift deg | Facing deg (hips, head) | "
             "Seam step | Lowest cm | Pops | Steps |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, rep in report.get("clips", {}).items():
        steps = ", ".join(s["op"] + (" (skipped)" if "skipped" in s else "") for s in rep["steps"]) or "-"
        lines.append(f"| {name} | {rep['source'] or 'from ' + str(rep['from'])} | {rep['seconds']} | "
                     f"{'yes' if rep['loop'] else 'no'} | {'yes' if rep['export'] else 'no'} | "
                     f"{rep['speed_m_s'] if rep['speed_m_s'] is not None else '-'} | {rep['travel_left_m']} | "
                     f"{rep['yaw_drift_deg']} | {rep.get('facing_mean_deg', '-')}, {rep.get('head_facing_mean_deg', '-')} | "
                     f"{rep.get('seam_step_ratio') or '-'} | {rep.get('lowest_cm', '-')} | {rep.get('pop_count', '-')} | "
                     f"{steps} |")
    return "\n".join(lines) + "\n"


def donor_facing(check: dict[str, str]) -> bool:
    """godot-check's facing check that cannot tell on a set's donor, a pack original whose parts are not named by
    role (it finds no _eyes and no _shoes part): not a failure of the set (it keeps the donor's rest and facing)."""
    return check["check"] == "facing_plus_z" and check["status"] == "fail" and check["detail"].startswith("cannot tell")


def summary(godot: dict[str, Any] | None) -> dict[str, int]:
    """godot-check's verdicts counted: {"pass": n, "warn": n, "fail": n}."""
    out = {"pass": 0, "warn": 0, "fail": 0}
    for c in (godot or {}).get("checks", []):
        out[c["status"]] = out.get(c["status"], 0) + 1
    return out
