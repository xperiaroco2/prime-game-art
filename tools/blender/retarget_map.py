"""The bone map of the retarget: loads and checks a map file (tools/blender/retarget_maps/*.toml).

Pure Python (no bpy), so the unit tests read it with the system Python and Blender's Python reads it the same way.
The format is documented in docs/animations.md and in the head of tools/blender/retarget_maps/ual_um.toml.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

MAPS = Path(__file__).resolve().parent / "retarget_maps"
DEFAULT = MAPS / "ual_um.toml"
KEYS = {"title", "source_rig", "target_rig", "root", "hips", "height", "bones", "follow", "legs", "rest", "unused"}


class MapError(ValueError):
    """A map file that cannot be used, with every reason found."""


def _names(data: dict, key: str, errors: list[str]) -> list[str]:
    table = data.get(key)
    if not isinstance(table, dict) or not isinstance(table.get("bones"), list):
        errors.append(f"[{key}] needs a 'bones' list")
        return []
    names = table["bones"]
    if not all(isinstance(n, str) and n for n in names):
        errors.append(f"[{key}] bones must be non-empty strings")
        return []
    if len(set(names)) != len(names):
        errors.append(f"[{key}] lists a bone twice")
    return list(names)


def check(data: dict) -> dict:
    """Validates a parsed map and returns it normalised; raises MapError listing every problem."""
    errors: list[str] = []
    unknown = set(data) - KEYS
    if unknown:
        errors.append(f"unknown keys {sorted(unknown)}")
    src_bones = _names(data, "source_rig", errors)
    tgt_bones = _names(data, "target_rig", errors)
    src, tgt = set(src_bones), set(tgt_bones)
    bones = data.get("bones", {})
    if not isinstance(bones, dict) or not bones:
        errors.append("[bones] must map source bone names to target bone names")
        bones = {}
    for s, t in bones.items():
        if s not in src:
            errors.append(f"[bones] {s!r} is not a source rig bone")
        if t not in tgt:
            errors.append(f"[bones] {s!r} maps to {t!r}, not a target rig bone")
    targets = list(bones.values())
    if len(set(targets)) != len(targets):
        errors.append("[bones] maps two source bones to one target bone")
    for key in ("root", "hips"):
        pair = data.get(key)
        if not (isinstance(pair, list) and len(pair) == 2 and bones.get(pair[0]) == pair[1]):
            errors.append(f"{key} must be [source, target], a pair that [bones] maps")
    height = data.get("height", {})
    if not (isinstance(height, dict) and set(height) == {"source", "target"}):
        errors.append("[height] needs 'source' and 'target' bone lists (the hip joints)")
    else:
        for side, rig in (("source", src), ("target", tgt)):
            if not height[side] or any(b not in rig for b in height[side]):
                errors.append(f"[height] {side} must list bones of the {side} rig")
    follow = data.get("follow", {})
    for t, carrier in follow.items():
        if t not in tgt or carrier not in tgt:
            errors.append(f"[follow] {t!r} = {carrier!r}: both must be target rig bones")
        if t not in targets:
            errors.append(f"[follow] {t!r} must also be a mapped target bone (it takes the source's rotation)")
    legs = data.get("legs", [])
    for leg in legs:
        chain, foot = leg.get("target", []), leg.get("source_foot")
        if len(chain) != 3 or any(b not in tgt for b in chain):
            errors.append(f"[[legs]] target must be three target bones (upper, lower, foot): {chain}")
        elif follow.get(chain[2]) != chain[1]:
            errors.append(f"[[legs]] the foot {chain[2]!r} must follow the lower leg {chain[1]!r} in [follow]")
        if foot not in src:
            errors.append(f"[[legs]] source_foot {foot!r} is not a source rig bone")
    rest = _names(data, "rest", errors)
    unused = _names(data, "unused", errors)
    covered = targets + rest
    for b in sorted(tgt - set(covered)):
        errors.append(f"target bone {b!r} is neither mapped nor kept at rest")
    for b in sorted(set(rest) & set(targets)):
        errors.append(f"target bone {b!r} is both mapped and kept at rest")
    for b in sorted(set(rest) - tgt):
        errors.append(f"[rest] {b!r} is not a target rig bone")
    for b in sorted(src - set(bones) - set(unused)):
        errors.append(f"source bone {b!r} is neither mapped nor listed as unused")
    for b in sorted(set(unused) & set(bones)):
        errors.append(f"source bone {b!r} is both mapped and unused")
    if errors:
        raise MapError("; ".join(errors))
    return {
        "title": data.get("title", ""),
        "source_bones": src_bones,
        "target_bones": tgt_bones,
        "bones": dict(bones),
        "root": tuple(data["root"]),
        "hips": tuple(data["hips"]),
        "height": {"source": list(height["source"]), "target": list(height["target"])},
        "follow": dict(follow),
        "legs": [{"target": list(leg["target"]), "source_foot": leg["source_foot"]} for leg in legs],
        "rest": rest,
        "unused": unused,
    }


def load(path: Path | str = DEFAULT) -> dict:
    """Reads and checks a map file."""
    path = Path(path)
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise MapError(f"cannot read the bone map {path}: {error}") from error
    try:
        return check(data)
    except MapError as error:
        raise MapError(f"{path.name}: {error}") from None
