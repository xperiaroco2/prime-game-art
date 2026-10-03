"""Shared helpers of the animation commands (retarget, anim-review): the review settings, the clip list, chunks for
parallel Blender runs, merging the measures and the Markdown table. Standard library only; docs/animations.md."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from .. import common

BLENDER_DIR = common.ROOT / "tools" / "blender"
CONFIG = BLENDER_DIR / "anim_review.toml"
BODIES = ("men", "women")


def load_config(path: Path = CONFIG) -> dict:
    try:
        cfg = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise common.Failure(f"cannot read {path}: {error}") from error
    missing = [k for k in ("ual", "ual_rm", "bodies", "loops", "pairs") if k not in cfg]
    missing += [f"bodies.{b}" for b in BODIES if b not in cfg.get("bodies", {})]
    if missing:
        raise common.Failure(f"{path.name} lacks {', '.join(missing)}")
    return cfg


def raw_path(relative: str) -> Path:
    path = common.raw_dir() / relative
    if not path.exists():
        raise common.Failure(f"missing raw file {path} (ART_RAW_DIR is {common.raw_dir()})")
    return path


def clip_keys(inventory: dict, body: str) -> list[str]:
    """Every clip of a body type as "pack:<name>" and "ual:<name>", from inventory.json."""
    pack = sorted(inventory["pack"][body]["actions"])
    ual = sorted(inventory["ual"]["ual"]["clips"])
    return [f"pack:{n}" for n in pack] + [f"ual:{n}" for n in ual]


def chunks(keys: list[str], n: int, seconds: dict[str, float] | None = None) -> list[list[str]]:
    """Splits keys into at most n lists of similar total length (longest first, each to the lightest list)."""
    n = max(1, min(n, len(keys)))
    cost = seconds or {}
    order = sorted(keys, key=lambda k: -cost.get(k, 1.0))
    out: list[list[str]] = [[] for _ in range(n)]
    load = [0.0] * n
    for k in order:
        i = load.index(min(load))
        out[i].append(k)
        load[i] += cost.get(k, 1.0) + 0.5
    return [sorted(c, key=keys.index) for c in out if c]


def clip_seconds(inventory: dict, body: str) -> dict[str, float]:
    out = {f"pack:{n}": a["seconds"] for n, a in inventory["pack"][body]["actions"].items()}
    out.update({f"ual:{n}": c["seconds"] for n, c in inventory["ual"]["ual"]["clips"].items()})
    return out


def merge(metrics_dir: Path) -> dict:
    """Joins metrics/<body>*.json (one per chunk) into {body: {clip key: measures}}; in name order, so a partial
    run's <body>_part_c*.json replaces the full run's measures of the same clips."""
    merged: dict[str, dict] = {}
    for body in BODIES:
        for path in sorted(metrics_dir.glob(f"{body}*.json")):
            merged.setdefault(body, {}).update(json.loads(path.read_text(encoding="utf-8")))
    return merged


def _fmt(value, digits: int = 1) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


COLUMNS = (
    "| Body | Source | Clip | s | Loop | Ground m/s | Foot slide mean/max cm/s | Lowest cm | Hands in torso/head cm "
    "| Seam deg (x step) | Knee/elbow past straight deg | Forearm twist deg | Finger curl deg |"
)


def table(merged: dict, verdicts: dict | None = None) -> str:
    """The measures as one Markdown table, a row per body type and clip (docs/animations.md defines the columns)."""
    verdicts = verdicts or {}
    lines = [COLUMNS + (" Verdict |" if verdicts else ""), "|" + "---|" * (13 + (1 if verdicts else 0))]
    for body in BODIES:
        for key, m in merged.get(body, {}).items():
            fs, low = m["foot_sliding"], m.get("lowest_vertex_cm", {})
            hands, head = m.get("hands_in_torso", {}), m.get("hands_in_head", {})
            seam, hyp = m["loop_seam"], m["hyperextension_deg"]
            curl = m["finger_curl_deg"]
            ratio = f" (x{_fmt(seam['seam_ratio'])})" if m["loop"] and seam["seam_ratio"] is not None else ""
            row = [
                body, m["source"], m["clip"], _fmt(m["seconds"], 2), "yes" if m["loop"] else "no",
                _fmt(m["root_motion"]["ground_speed_m_s"], 2),
                f"{_fmt(fs['slide_mean_cm_s'])} / {_fmt(fs['slide_max_cm_s'])}",
                _fmt(low.get("min")),
                f"{_fmt(hands.get('max_depth_cm'))} / {_fmt(head.get('max_depth_cm'))}",
                f"{_fmt(seam['seam_deg'])}{ratio}",
                f"{_fmt(max(hyp['knee.L'], hyp['knee.R']))} / {_fmt(max(hyp['elbow.L'], hyp['elbow.R']))}",
                _fmt(max(m["forearm_twist_deg"].values())),
                f"{_fmt(min(curl['L']['min'], curl['R']['min']))}-{_fmt(max(curl['L']['max'], curl['R']['max']))}",
            ]
            if verdicts:
                row.append(verdicts.get(f"{body}:{key}", verdicts.get(key, "")))
            lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"
