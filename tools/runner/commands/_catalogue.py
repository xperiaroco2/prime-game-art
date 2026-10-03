"""Helpers for the catalogue command (docs/catalogue.md): the data file's place, its schema check, its summary and the
comparison of two runs. Pure Python; the tests use them on the committed file."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .. import common

DATA = common.ROOT / "catalogue" / "ultimate_modular.json"
SCRIPT = "catalogue.py"
SCHEMA = "prime-game-art/catalogue/ultimate-modular/1"
MODES = ("sheets", "matrices", "confirm")
SLOTS = ("top", "bottom", "shoes")
ITEM_KINDS = ("skull", "hair", "brows", "facial_hair", "headwear", "earrings", "accessory")
MATRICES = {
    "bottom_shoes": ("ok_tucked", "ok_over", "needs_fix", "gap", "poke"),
    "top_bottom": ("ok_over", "ok_tucked", "needs_fix", "gap", "poke"),
    "head_top": ("ok", "needs_fix", "gap", "poke"),
    "hair_skull": ("ok", "needs_fix", "gap", "poke"),
}
FIXES = ("extend_edge", "inflate", "tuck_cull")
TOP_KEYS = ("schema", "generated_by", "sources", "conventions", "thresholds", "characters", "files", "parts", "heads",
            "items", "proposed_zones", "rules", "matrices", "summary")


def load(path: Path = DATA) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(data: dict[str, Any]) -> list[str]:
    """Every schema problem of a catalogue, as readable lines (empty when it is valid)."""
    p: list[str] = []
    missing = [k for k in TOP_KEYS if k not in data]
    if missing:
        return [f"missing top-level keys: {', '.join(missing)}"]
    if data["schema"] != SCHEMA:
        p.append(f"schema is {data['schema']!r}, expected {SCHEMA!r}")
    for f in data["files"]:
        for k in ("body_type", "file", "character", "sha256", "parts", "animations"):
            if k not in f:
                p.append(f"files[{f.get('file')}]: no {k}")
        if sorted(f.get("parts", {})) != ["bottom", "head", "shoes", "top"]:
            p.append(f"files[{f.get('file')}]: parts {sorted(f.get('parts', {}))}")
    for pid, e in data["parts"].items():
        slot, g, _ = pid.split("_", 2)
        if slot not in SLOTS or g.upper() not in ("M", "W") or e.get("slot") != slot or e.get("body_type") != g.upper():
            p.append(f"parts[{pid}]: id, slot and body type disagree")
        for k in ("triangles", "vertices", "materials", "bounds", "seams"):
            if k not in e:
                p.append(f"parts[{pid}]: no {k}")
    for iid, e in data["items"].items():
        if e.get("kind") not in ITEM_KINDS:
            p.append(f"items[{iid}]: kind {e.get('kind')!r}")
        if not iid.startswith((e.get("subkind") or e.get("kind", "?")) + "_"):
            p.append(f"items[{iid}]: the id does not start with its kind")
        for k in ("head", "source", "materials", "triangles", "recipe", "recipe_check", "geometry"):
            if k not in e:
                p.append(f"items[{iid}]: no {k}")
        twin = e.get("same_geometry_as")
        if twin is not None and twin not in data["items"]:
            p.append(f"items[{iid}]: same_geometry_as {twin} is not an item")
    for hid, h in data["heads"].items():
        if h.get("skull_type") not in ("full", "open_top", "none"):
            p.append(f"heads[{hid}]: skull_type {h.get('skull_type')!r}")
        for iid in h.get("items", []):
            if iid not in data["items"]:
                p.append(f"heads[{hid}]: unknown item {iid}")
    known = set(data["parts"]) | set(data["items"])
    for name, verdicts in MATRICES.items():
        for g in ("M", "W"):
            m = data["matrices"].get(name, {}).get(g)
            if m is None:
                p.append(f"matrices.{name}.{g} is missing")
                continue
            if len(m["cells"]) != len(m["rows"]) * len(m["cols"]):
                p.append(f"matrices.{name}.{g}: {len(m['cells'])} cells for {len(m['rows'])} x {len(m['cols'])}")
            for c in m["cells"]:
                if c["a"] not in known or c["b"] not in known:
                    p.append(f"matrices.{name}.{g}: unknown ids {c['a']} x {c['b']}")
                if c.get("verdict") not in verdicts:
                    p.append(f"matrices.{name}.{g}: {c['a']} x {c['b']} verdict {c.get('verdict')!r}")
                if c.get("verdict") == "needs_fix" and c.get("fix", {}).get("fix") not in FIXES:
                    p.append(f"matrices.{name}.{g}: {c['a']} x {c['b']} needs_fix without a known fix")
    rule_ids = {r.get("id") for r in data["rules"]}
    if rule_ids != set(MATRICES):
        p.append(f"rules: {sorted(rule_ids)}, expected {sorted(MATRICES)}")
    return p


def cell(data: dict[str, Any], name: str, g: str, a: str, b: str) -> dict[str, Any]:
    for c in data["matrices"][name][g]["cells"]:
        if c["a"] == a and c["b"] == b:
            return c
    raise KeyError(f"{name}.{g}: no cell {a} x {b}")


def summary(data: dict[str, Any]) -> list[str]:
    ch = data["characters"]
    lines = [f"characters: {ch['M']} men's, {ch['W']} women's ({ch['total']}); parts {len(data['parts'])}, "
             f"head items {len(data['items'])}"]
    for name, per in data["summary"].items():
        for g, s in sorted(per.items()):
            verdicts = ", ".join(f"{k} {v}" for k, v in s["verdicts"].items())
            gap = f"; gap over 5 mm {s['gap_over_5mm']}" if "gap_over_5mm" in s else ""
            lines.append(f"{name} {g}: {s['pairs']} pairs: {verdicts}{gap}")
    return lines


def diff(a: Any, b: Any, path: str = "", out: list[str] | None = None, limit: int = 20) -> list[str]:
    """The paths where two catalogues differ (at most limit)."""
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{path}/{k}: only in {'the new run' if k in b else 'the committed file'}")
            else:
                diff(a[k], b[k], f"{path}/{k}", out, limit)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, f"{path}[{i}]", out, limit)
    elif a != b:
        out.append(f"{path}: {json.dumps(a)[:80]} != {json.dumps(b)[:80]}")
    return out
