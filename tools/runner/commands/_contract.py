"""The character contract as data: loading and validating contract/, and dumping Godot's humanoid profile.

Used by the commands contract, check and rename-bones. Pure standard library; the only external tool is the game's
pinned Godot, run headless by dump_profile().
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

from .. import common, pins

CONTRACT_DIR = common.ROOT / "contract"
HUMANOID_JSON = CONTRACT_DIR / "humanoid.json"
CONTRACT_TOML = CONTRACT_DIR / "contract.toml"
BONE_MAPS = CONTRACT_DIR / "bone_maps"
GODOT_PROJECT = common.ROOT / "tools" / "godot"
DUMP_SCRIPT = "res://dump_profile.gd"
FINGERS = ("Thumb", "Index", "Middle", "Ring", "Little")
SIDES = ("Left", "Right")
KINDS = ("body", "clothing", "accessory", "prop")
DECIMALS = 6
SEVERITIES = ("fail", "warn", "off")
# The values each kinds.<kind> rule may take in contract.toml.
RULE_VALUES = {
    "rig": ("required", "forbidden"),
    "bones": ("all", "subset"),
    "fingers": SEVERITIES,
    "height": SEVERITIES,
    "eyes": SEVERITIES,
    "feet": SEVERITIES,
    "facing": SEVERITIES,
}


# --- Godot's humanoid profile -------------------------------------------------------------------------------------


def dump_profile(out: Path, timeout: float = 120) -> dict[str, Any]:
    """Runs tools/godot/dump_profile.gd in the pinned Godot (headless) and returns the raw dump it wrote to out."""
    godot = common.godot_bin()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    cmd = [godot, "--headless", "--path", GODOT_PROJECT, "--script", DUMP_SCRIPT, "--", out.as_posix()]
    result = common.run(cmd, timeout)
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0 or not out.is_file():
        tail = "\n".join(output.splitlines()[-20:])
        raise common.Failure(f"dump_profile.gd failed (exit code {result.returncode}):\n{tail}")
    raw = json.loads(out.read_text(encoding="utf-8"))
    # dump_profile.gd writes major.minor.patch.status; a prefix match would let 4.7.20 or 4.7.2.rc1 through.
    if raw.get("godot_version") != f"{pins.GODOT}.stable":
        raise common.Failure(
            f"GODOT_BIN is Godot {raw.get('godot_version')}, the contract is pinned to {pins.GODOT}.stable"
        )
    return raw


def _clean(value: Any) -> Any:
    """Rounds floats to DECIMALS places (and -0.0 to 0.0) so the file is stable across float noise."""
    if isinstance(value, float):
        rounded = round(value, DECIMALS)
        return 0.0 if rounded == 0 else rounded
    if isinstance(value, list):
        return [_clean(v) for v in value]
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    return value


def format_profile(raw: dict[str, Any]) -> str:
    """The text of contract/humanoid.json: keys sorted, bones and groups in profile index order, floats rounded."""
    data = _clean(raw)
    data["bones"] = sorted(data["bones"], key=lambda b: b["index"])
    data["groups"] = sorted(data["groups"], key=lambda g: g["index"])
    data["generated_by"] = "tools/run.py contract (tools/godot/dump_profile.gd); never edit by hand"
    text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
    return _SCALAR_LIST.sub(lambda m: "[" + ", ".join(v.strip() for v in m.group(1).split(",")) + "]", text) + "\n"


# A JSON list of numbers that indent=2 spreads over several lines; format_profile puts it on one line.
_SCALAR_LIST = re.compile(r"\[\s+([-0-9.e,\s]+?)\s+\]")


def load_profile(path: Path = HUMANOID_JSON) -> dict[str, Any]:
    if not path.is_file():
        raise common.Failure(f"{path} is missing: run `tools/run.py contract`")
    return json.loads(path.read_text(encoding="utf-8"))


def profile_parents(profile: dict[str, Any]) -> dict[str, str]:
    """Bone name -> parent name ("" for the root), in profile order."""
    return {b["name"]: b["parent"] for b in profile["bones"]}


def finger_chains(profile: dict[str, Any]) -> dict[str, list[str]]:
    """"LeftThumb" -> its bones from the hand outwards, read from the profile's parents."""
    parents = profile_parents(profile)
    chains: dict[str, list[str]] = {}
    for side in SIDES:
        for finger in FINGERS:
            prefix = side + finger
            bones = [name for name in parents if name.startswith(prefix)]
            bones.sort(key=lambda name: _depth(name, parents))
            chains[prefix] = bones
    return chains


def _depth(name: str, parents: dict[str, str]) -> int:
    depth = 0
    while parents.get(name):
        name = parents[name]
        depth += 1
    return depth


# --- contract.toml ------------------------------------------------------------------------------------------------


def load_contract(path: Path = CONTRACT_TOML) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def validate_contract(contract: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    """Every problem that makes contract.toml disagree with itself or with the profile; empty when it is sound."""
    errors: list[str] = []
    bones = profile_parents(profile)
    skeleton = contract.get("skeleton", {})
    if skeleton.get("root") != profile.get("root_bone"):
        errors.append(
            f"skeleton.root is {skeleton.get('root')!r}, the profile's root bone is {profile.get('root_bone')!r}"
        )
    for key in ("weighted", "weights_optional"):
        for name in skeleton.get(key, []):
            if name not in bones:
                errors.append(f"skeleton.{key} names {name!r}, which is not a profile bone")
    listed = set(skeleton.get("weighted", [])) | set(skeleton.get("weights_optional", []))
    finger_bones = {b for chain in finger_chains(profile).values() for b in chain}
    for name in bones:
        if name != skeleton.get("root") and name not in listed and name not in finger_bones:
            errors.append(f"profile bone {name!r} is in neither skeleton.weighted nor skeleton.weights_optional")
    for socket in contract.get("sockets", []):
        if socket.get("bone") not in bones:
            errors.append(f"socket {socket.get('name')} is on {socket.get('bone')!r}, which is not a profile bone")
        if not str(socket.get("name", "")).startswith("Socket_"):
            errors.append(f"socket {socket.get('name')!r} does not start with Socket_")
        if "scene_position" in socket and socket.get("model_position") != model_from_scene(socket["scene_position"]):
            errors.append(f"socket {socket.get('name')}: model_position is not scene_position turned 180 degrees")
    slot_ids = [slot.get("id") for slot in contract.get("slots", [])]
    if len(slot_ids) != len(set(slot_ids)):
        errors.append("two slots share an id")
    socket_names = {s.get("name") for s in contract.get("sockets", [])}
    for slot in contract.get("slots", []):
        if slot.get("socket") and slot["socket"] not in socket_names:
            errors.append(f"slot {slot.get('id')} uses the unknown socket {slot['socket']!r}")
        if slot.get("check_kind") and slot["check_kind"] not in KINDS:
            errors.append(f"slot {slot.get('id')} has the unknown check_kind {slot['check_kind']!r}")
    for kind in KINDS:
        rules = contract.get("kinds", {}).get(kind)
        if not rules:
            errors.append(f"kinds.{kind} is missing")
            continue
        if rules.get("budget") not in contract.get("budgets", {}):
            errors.append(f"kinds.{kind}.budget names {rules.get('budget')!r}, which is not in budgets")
        for key, allowed in RULE_VALUES.items():
            if rules.get(key) not in allowed:
                errors.append(f"kinds.{kind}.{key} is {rules.get(key)!r}; it must be one of {', '.join(allowed)}")
        if not isinstance(rules.get("max_materials"), int):
            errors.append(f"kinds.{kind}.max_materials must be an integer")
    for name, budget in contract.get("budgets", {}).items():
        if name == "limits":
            continue
        for metric in ("triangles", "vertices"):
            if metric == "vertices" and f"{metric}_cap" not in budget:
                continue  # vertex budgets are optional
            target, cap = budget.get(f"{metric}_target"), budget.get(f"{metric}_cap")
            if not isinstance(target, int) or not isinstance(cap, int) or target > cap:
                errors.append(f"budgets.{name}: {metric}_target and {metric}_cap must be integers, target <= cap")
    for slot in contract.get("slots", []):
        if slot.get("budget") and slot["budget"] not in contract.get("budgets", {}):
            errors.append(f"slot {slot.get('id')} names the unknown budget {slot['budget']!r}")
    return errors


def model_from_scene(position: list[float]) -> list[float]:
    """A point in the character scene (front -Z, like the greybox) in model space (front +Z): turned 180 degrees about
    Y, because the character scene turns the +Z-facing model to face -Z."""
    return [_clean(-float(position[0])), _clean(float(position[1])), _clean(-float(position[2]))]


def checkable_slot(contract: dict[str, Any], slot_id: str) -> dict[str, Any]:
    """The slot `check --slot` judges a piece for; a Failure for an unknown slot or one without a model."""
    slots = {s["id"]: s for s in contract.get("slots", [])}
    if slot_id not in slots:
        raise common.Failure(f"no slot {slot_id!r}; the slots are {', '.join(slots)}")
    if not slots[slot_id].get("check_kind"):
        raise common.Failure(f"slot {slot_id!r} holds no model ({slots[slot_id].get('type')}): nothing to check")
    return slots[slot_id]


# --- bone maps ----------------------------------------------------------------------------------------------------


def map_names() -> list[str]:
    return sorted(p.stem for p in BONE_MAPS.glob("*.toml"))


def load_map(name: str) -> dict[str, Any]:
    path = BONE_MAPS / f"{name}.toml"
    if not path.is_file():
        raise common.Failure(f"no bone map {name!r}; the maps are {', '.join(map_names())}")
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    data["name"] = name
    return data


def validate_map(bone_map: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    name = bone_map.get("name", "?")
    bones = profile_parents(profile)
    if not isinstance(bone_map.get("confirmed"), bool):
        errors.append(f"bone map {name}: `confirmed` must be true or false")
    try:
        re.compile(bone_map.get("prefix_pattern", ""))
    except re.error as exc:
        errors.append(f"bone map {name}: prefix_pattern does not compile: {exc}")
    seen: dict[str, str] = {}
    for source, target in bone_map.get("rename", {}).items():
        if target not in bones:
            errors.append(f"bone map {name}: {source!r} -> {target!r}, which is not a profile bone")
        if target in seen:
            errors.append(f"bone map {name}: {seen[target]!r} and {source!r} both map to {target!r}")
        seen[target] = source
    for source in bone_map.get("drop", []):
        if source in bone_map.get("rename", {}):
            errors.append(f"bone map {name}: {source!r} is both renamed and dropped")
    return errors


def mapped_name(name: str, bone_map: dict[str, Any] | None) -> str:
    """A bone's name after the map: the prefix stripped, then renamed (names the map does not list stay)."""
    if not bone_map:
        return name
    pattern = bone_map.get("prefix_pattern", "")
    if pattern:
        name = re.sub(pattern, "", name, count=1)
    return bone_map.get("rename", {}).get(name, name)


def is_dropped(name: str, bone_map: dict[str, Any] | None) -> bool:
    if not bone_map:
        return False
    pattern = bone_map.get("prefix_pattern", "")
    stripped = re.sub(pattern, "", name, count=1) if pattern else name
    return stripped in bone_map.get("drop", [])


def rename_plan(bone_map: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """What rename_bones.py needs, as JSON-ready data (Blender's Python reads no TOML from us)."""
    return {
        "map": bone_map["name"],
        "confirmed": bone_map["confirmed"],
        "prefix_pattern": bone_map.get("prefix_pattern", ""),
        "rename": dict(bone_map.get("rename", {})),
        "drop": list(bone_map.get("drop", [])),
        "profile_bones": list(profile_parents(profile)),
    }
