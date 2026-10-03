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
    for key, lib in cfg.get("libraries", {}).items():
        if key in ("pack", "blend", "layer", "ual") or not key.isidentifier():
            raise common.Failure(f"{path.name}: [libraries.{key}] needs another name")
        if not (isinstance(lib, dict) and {"file", "rm"} <= set(lib) and set(lib) <= {"file", "rm", "label"}):
            raise common.Failure(f"{path.name}: [libraries.{key}] takes file, rm and label")
    return cfg


def libraries(cfg: dict) -> dict[str, dict]:
    """Every Universal Animation Library source, UAL1 first: {key: {file, rm, label}} (raw-relative paths)."""
    out = {"ual": {"file": cfg["ual"], "rm": cfg["ual_rm"], "label": "UAL"}}
    for key, lib in cfg.get("libraries", {}).items():
        out[key] = {"file": lib["file"], "rm": lib["rm"], "label": lib.get("label", key.upper())}
    return out


def sources(cfg: dict) -> set[str]:
    """Every clip source of the review: the pack and each library."""
    return {"pack", *libraries(cfg)}


def raw_path(relative: str) -> Path:
    path = common.raw_dir() / relative
    if not path.exists():
        raise common.Failure(f"missing raw file {path} (ART_RAW_DIR is {common.raw_dir()})")
    return path


def clip_keys(inventory: dict, body: str, only: set[str] | None = None) -> list[str]:
    """Every clip of a body type as "pack:<name>", "ual:<name>" and "<library>:<name>", from inventory.json; `only`
    keeps the clips of those sources (None: all)."""
    keys = [f"pack:{n}" for n in sorted(inventory["pack"][body]["actions"])]
    for lib in inventory.get("libraries", ["ual"]):  # an inventory of art #20 knows UAL1 alone
        keys += [f"{lib}:{n}" for n in sorted(inventory["ual"][lib]["clips"])]
    return [k for k in keys if only is None or k.split(":", 1)[0] in only]


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
    for lib in inventory.get("libraries", ["ual"]):
        out.update({f"{lib}:{n}": c["seconds"] for n, c in inventory["ual"][lib]["clips"].items()})
    return out


def run_tag(only: set[str] | None) -> str:
    """The measures file tag of a clips run over every clip of the sources `only` (None: all sources)."""
    return "_c" if only is None else "_s" + "+".join(sorted(only)) + "_c"


def _rank(path: Path) -> tuple[int, int, str]:
    """A measures file's place in merge(): full runs, then runs over some sources, then partial runs; within one kind
    the older file first, so that of two runs over overlapping sources the later one wins."""
    rest = path.stem.split("_", 1)[1] if "_" in path.stem else ""
    kind = 2 if rest.startswith("part_c") else 1 if rest.startswith("s") else 0
    return kind, path.stat().st_mtime_ns, path.name


def merge(metrics_dir: Path) -> dict:
    """Joins metrics/<body>*.json (one per chunk) into {body: {clip key: measures}}: a full run's <body>_c*.json
    first, then the runs over some sources (<body>_s<sources>_c*.json, oldest first), then a partial run's
    <body>_part_c*.json, each replacing the earlier measures of the same clips."""
    merged: dict[str, dict] = {}
    for body in BODIES:
        for path in sorted(metrics_dir.glob(f"{body}_*.json"), key=_rank):
            merged.setdefault(body, {}).update(json.loads(path.read_text(encoding="utf-8")))
    return merged


def _fmt(value, digits: int = 1) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


MIN_SLIDE_SAMPLES = 4  # contact velocities below which the foot slide is shown as "-"

COLUMNS = (
    "| Body | Source | Clip | s | Loop | Ground m/s | Foot slide mean/max cm/s | Lowest cm "
    "| Hands in torso/head/other hand/legs cm | Seam deg (x step) | Knee past straight deg | Forearm twist deg "
    "| Finger curl deg |"
)


def table(merged: dict, verdicts: dict | None = None) -> str:
    """The measures as one Markdown table, a row per body type and clip (docs/animations.md defines the columns)."""
    verdicts = verdicts or {}
    lines = [COLUMNS + (" Verdict |" if verdicts else ""), "|" + "---|" * (13 + (1 if verdicts else 0))]
    for body in BODIES:
        for key, m in merged.get(body, {}).items():
            fs, low = m["foot_sliding"], m.get("lowest_vertex_cm", {})
            hands = "/".join(_fmt(m.get(k, {}).get("max_depth_cm"))
                             for k in ("hands_in_torso", "hands_in_head", "hands_in_each_other", "hands_in_legs"))
            few = fs.get("samples", MIN_SLIDE_SAMPLES) < MIN_SLIDE_SAMPLES  # too few contact velocities to say
            seam, hyp = m["loop_seam"], m["hyperextension_deg"]
            curl = m["finger_curl_deg"]
            ratio = f" (x{_fmt(seam['seam_ratio'])})" if m["loop"] and seam["seam_ratio"] is not None else ""
            row = [
                body, m["source"], m["clip"], _fmt(m["seconds"], 2), "yes" if m["loop"] else "no",
                _fmt(m["root_motion"]["ground_speed_m_s"], 2),
                "-" if few else f"{_fmt(fs['slide_mean_cm_s'])} / {_fmt(fs['slide_max_cm_s'])}",
                _fmt(low.get("min")),
                hands,
                f"{_fmt(seam['seam_deg'])}{ratio}",
                _fmt(max(hyp["knee.L"], hyp["knee.R"])),
                _fmt(max(m["forearm_twist_deg"].values())),
                f"{_fmt(min(curl['L']['min'], curl['R']['min']))}-{_fmt(max(curl['L']['max'], curl['R']['max']))}",
            ]
            if verdicts:
                row.append(verdicts.get(f"{body}:{key}", verdicts.get(key, "")))
            lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"
