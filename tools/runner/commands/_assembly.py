"""Helpers for the assemble command: finding recipes, the pure-Python recipe module of tools/blender/um/, the summary
of a build report and its comparison with a reference report (the regression against the final character test)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from .. import common

RECIPES = common.ROOT / "recipes"
BLENDER_DIR = common.ROOT / "tools" / "blender"
SCRIPT = "assemble_characters.py"

# The regression tolerances (docs/assembly.md): triangles are exact; heights within 1 mm, seam overlaps within
# 0.2 mm, and each probe band's see-through and poke-through counts within 2 rays of the reference.
HEIGHT_TOLERANCE_M = 0.001
SEAM_TOLERANCE_MM = 0.2
PROBE_TOLERANCE_RAYS = 2
HEIGHTS = ("height_m", "height_without_hair_m", "posed_height_m")


def recipe_module() -> ModuleType:
    """tools/blender/um/recipe.py (pure Python), imported from the runner."""
    if str(BLENDER_DIR) not in sys.path:
        sys.path.append(str(BLENDER_DIR))
    from um import recipe  # type: ignore[import-not-found]

    return recipe


def available() -> list[str]:
    return sorted(p.name for p in RECIPES.glob("*.json"))


def find_recipe(name: str) -> Path:
    """A recipe path, a path from the repo root, or a file name in recipes/ (".json" may be left out)."""
    for candidate in (Path(name), common.ROOT / name, RECIPES / name, RECIPES / f"{name}.json"):
        if candidate.is_file():
            return candidate.resolve()
    raise common.Failure(f"no recipe {name!r}; recipes/ has: {', '.join(available()) or 'nothing'}")


def _rename_feet(value: Any) -> Any:
    """The final test called the shoes slot "feet"; the repo calls it "shoes" (the contract's slot name)."""
    if isinstance(value, dict):
        return {("shoes" if k == "feet" else k): _rename_feet(v) for k, v in value.items()}
    return value


def extract(report: dict[str, Any]) -> dict[str, Any]:
    """The numbers the regression compares, per character: triangles per part and in total, heights (rest, without
    hair, posed), rest seam overlaps, and each probe band's rays, see-through and poke-through counts (rest, posed)."""
    out: dict[str, Any] = {}
    for cid, rep in report.get("characters", {}).items():
        rep = _rename_feet(rep)
        entry: dict[str, Any] = {"triangles": rep["triangles"], "triangles_total": rep["triangles_total"]}
        for key in HEIGHTS:
            if key in rep:
                entry[key] = rep[key]
        entry["seam_overlap_rest"] = rep["seam_overlap_rest"]
        for key in ("probe_rest", "probe_posed"):
            if key in rep:
                entry[key] = {band: {k: v for k, v in counts.items() if k in ("rays", "see_through", "poke_through")}
                              for band, counts in rep[key].items()}
        out[cid] = entry
    return out


def compare(reference: dict[str, Any], report: dict[str, Any]) -> list[str]:
    """Differences between a report and a reference (either a full build_report.json or an extract()), outside the
    tolerances, for the characters the report holds. Empty when the build reproduces the reference."""
    ref = extract(reference) if "characters" in reference else reference
    new = extract(report)
    problems: list[str] = []
    for cid, got in new.items():
        if cid not in ref:
            problems.append(f"{cid}: not in the reference")
            continue
        want = ref[cid]
        if got["triangles"] != want["triangles"] or got["triangles_total"] != want["triangles_total"]:
            problems.append(f"{cid}: triangles {got['triangles']} (total {got['triangles_total']}), "
                            f"reference {want['triangles']} (total {want['triangles_total']})")
        for key in HEIGHTS:
            if key in want and abs(got.get(key, float("inf")) - want[key]) > HEIGHT_TOLERANCE_M + 1e-9:
                problems.append(f"{cid}: {key} {got.get(key)}, reference {want[key]}")
        for seam, value in want["seam_overlap_rest"].items():
            if abs(got["seam_overlap_rest"].get(seam, float("inf")) - value) > SEAM_TOLERANCE_MM + 1e-9:
                problems.append(f"{cid}: seam {seam} {got['seam_overlap_rest'].get(seam)}, reference {value}")
        for key in ("probe_rest", "probe_posed"):
            for band, counts in want.get(key, {}).items():
                have = got.get(key, {}).get(band)
                if have is None:
                    problems.append(f"{cid}: {key}.{band} missing")
                    continue
                if have["rays"] != counts["rays"]:
                    problems.append(f"{cid}: {key}.{band} cast {have['rays']} rays, reference {counts['rays']}")
                for kind in ("see_through", "poke_through"):
                    if kind in counts and abs(have.get(kind, 10**9) - counts[kind]) > PROBE_TOLERANCE_RAYS:
                        problems.append(f"{cid}: {key}.{band}.{kind} {have.get(kind)}, reference {counts[kind]}")
    return problems


def summary(report: dict[str, Any]) -> list[str]:
    """One line per character: heights, triangles and the probe's see-through and poke-through totals."""
    lines = []
    for cid, rep in report.get("characters", {}).items():
        def total(key: str, kind: str) -> int:
            return sum(band.get(kind, 0) for band in rep.get(key, {}).values())

        lines.append(
            f"{cid}: height {rep['height_m']} m rest, {rep.get('posed_height_m', '-')} m posed; "
            f"{rep['triangles_total']} triangles; seams {rep['seam_overlap_rest']}; see-through rays "
            f"{total('probe_rest', 'see_through')} rest, {total('probe_posed', 'see_through')} posed; poke-through "
            f"{total('probe_rest', 'poke_through')} rest, {total('probe_posed', 'poke_through')} posed"
        )
    return lines
