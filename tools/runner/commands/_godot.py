"""Helpers for godot-check and frames: the art repo's Godot project (godot/), staging and importing a GLB headless,
running the inspection script, and the assertions on its description (docs/godot.md). The assertions are pure Python
(evaluate()), so the tests run them without Godot."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from .. import common, pins
from . import _contract, _export

PROJECT = common.ROOT / "godot"
IMPORT_DIR = PROJECT / "import"
INSPECT = "res://check/inspect.gd"
OUT = common.OUT / "godot-check"
IMPORT_TIMEOUT = 600
INSPECT_TIMEOUT = 300

# Thresholds of the assertions (docs/godot.md).
MOVE_MIN_DEG = 0.5  # an animation moves a bone by at least this much between its samples at 0, 1/3 and 2/3 ...
MOVE_MIN_M = 0.002  # ... or translates one by at least this much
SIZE_TOLERANCE_M = 0.002  # Godot's rest-pose height equals Blender's
JOINT_TOLERANCE_M = 0.001  # Godot's rest joints equal Blender's bone heads
LENGTH_TOLERANCE_S = 1e-3
FACE_AHEAD_M = 0.05  # the eyes sit at least this far in front of the Head joint
ANSI = re.compile(r"\x1b\[[0-9;]*m")
NOTEWORTHY = ("ERROR", "WARNING", "SCRIPT ERROR", "USER ERROR", "USER WARNING")


# The import options godot-check and frames set; every other option keeps Godot's default (docs/godot.md). Godot's
# editor import resamples a glTF animation at animation/fps (default 30): the pack's actions are 24 fps, and at 30 the
# joints on the pack's own frames moved by up to 7.6 mm against Blender's (m1_rex's Walk).
IMPORT_PARAMS = {"animation/fps": 24}
# The importer's AnimationPlayer node options (_subresources "nodes"). Godot's animation optimizer (on by default) drops
# keys it finds linearly interpolable within its velocity and angle errors: with it, joints moved by up to 16.7 mm
# against Blender's (m1_rex's Run, the left hand at frame 17); without it, every joint of every clip is within 0.02 mm.
PLAYER_NODE = "PATH:AnimationPlayer"
PLAYER_OPTIONS = {"optimizer/enabled": False}


class Resource(str):
    """A res:// path written as Resource("...") in an .import file."""


def variant(value: Any) -> str:
    """value in Godot's text format (the .import _subresources): dicts, bools, numbers, strings and Resource paths."""
    if isinstance(value, Resource):
        return f'Resource("{value}")'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, dict):
        if not value:
            return "{}"
        return "{\n" + ",\n".join(f"{json.dumps(str(k))}: {variant(v)}" for k, v in value.items()) + "\n}"
    return json.dumps(value)


def subresources(nodes: dict[str, dict[str, Any]] | None = None) -> str:
    """The _subresources of every import: PLAYER_OPTIONS on the AnimationPlayer, plus the given node options."""
    return variant({"nodes": {PLAYER_NODE: dict(PLAYER_OPTIONS), **(nodes or {})}})


def import_file(params: dict[str, Any], subresources: str = "{}") -> str:
    """The text of a minimal .import file: Godot fills in every option left out with its default on import."""
    lines = ["[remap]", "", 'importer="scene"', 'type="PackedScene"', "", "[params]", ""]
    lines += [f"{key}={json.dumps(value)}" for key, value in params.items()]
    lines.append(f"_subresources={subresources}")
    return "\n".join(lines) + "\n"


def stage(glb: Path, name: str | None = None, params: dict[str, Any] | None = None,
          nodes: dict[str, dict[str, Any]] | None = None) -> str:
    """Copies glb into godot/import/ as <name>.glb with a fresh .import file holding IMPORT_PARAMS (and params) and
    subresources(nodes), so the next import starts from Godot's defaults plus those, and returns its res:// path."""
    name = name or glb.stem
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    target = IMPORT_DIR / f"{name}.glb"
    shutil.copyfile(glb, target)
    text = import_file({**IMPORT_PARAMS, **(params or {})}, subresources(nodes))
    (IMPORT_DIR / f"{name}.glb.import").write_text(text, encoding="utf-8", newline="\n")
    return f"res://import/{name}.glb"


def noteworthy(output: str) -> list[str]:
    """Godot's error and warning lines (with the "at:" line that follows each), colour codes removed."""
    lines = [ANSI.sub("", line).rstrip() for line in output.splitlines()]
    found = []
    for i, line in enumerate(lines):
        if line.lstrip().startswith(NOTEWORTHY) or "couldn't resolve track" in line:
            where = lines[i + 1].strip() if i + 1 < len(lines) and lines[i + 1].strip().startswith("at:") else ""
            found.append(f"{line.strip()} {where}".strip())
    return found


def godot(args: list[str], timeout: float) -> tuple[int, str]:
    result = common.run([common.godot_bin(), *args], timeout)
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def import_project() -> list[str]:
    """Imports everything new in godot/ headless; returns Godot's error and warning lines."""
    code, output = godot(["--headless", "--path", PROJECT, "--import"], IMPORT_TIMEOUT)
    if code != 0:
        tail = "\n".join(ANSI.sub("", output).splitlines()[-20:])
        raise common.Failure(f"godot --import exited {code}:\n{tail}")
    return noteworthy(output)


def inspect(res_path: str, out: Path, request: dict[str, Any] | None = None) -> tuple[dict[str, Any], list[str]]:
    """Runs check/inspect.gd headless on an imported scene; returns its description and Godot's noteworthy lines."""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    args = ["--headless", "--path", PROJECT, "-s", INSPECT, "--", res_path, out.as_posix()]
    if request:
        req = out.with_suffix(".request.json")
        req.write_text(json.dumps(request), encoding="utf-8")
        args.append(req.as_posix())
    code, output = godot(args, INSPECT_TIMEOUT)
    errors = [ANSI.sub("", line).removeprefix("INSPECT error ") for line in output.splitlines() if "INSPECT error" in line]
    if code != 0 or errors or not out.is_file():
        tail = "\n".join(ANSI.sub("", output).splitlines()[-20:])
        raise common.Failure(f"inspect.gd failed (exit code {code}): {'; '.join(errors) or tail}")
    dump = json.loads(out.read_text(encoding="utf-8"))
    if not str(dump.get("godot", "")).startswith(f"{pins.GODOT}-stable"):
        raise common.Failure(f"GODOT_BIN is Godot {dump.get('godot')}, the art repo is pinned to {pins.GODOT}")
    return dump, noteworthy(output)


def expectations(glb: Path) -> dict[str, Any]:
    """What the import must hold: the export's description (<stem>.export.json beside the GLB, written by `export`),
    else what the GLB itself says (parts, bones, animations; no Blender height then)."""
    info_path = glb.with_name(f"{glb.stem}.export.json")
    if info_path.is_file():
        info = json.loads(info_path.read_text(encoding="utf-8"))
        fps = info.get("fps", 24)
        return {
            "source": info_path.name,
            "parts": sorted(info["parts"]),
            "bones": list(info["bones"]),
            "bone_parents": info.get("bone_parents", {}),
            "rest_heads_m": info.get("rest_heads_m", {}),
            "animations": {name: (end - start) / fps for name, (start, end) in info["actions"].items()},
            "height_m": info.get("height_m"),
            "seams": info.get("seams", {}),
        }
    summary = _export.summarize(_export.glb_json(glb))
    return {
        "source": glb.name,
        "parts": sorted(summary["meshes"]),
        "bones": summary["skins"][0] if summary["skins"] else [],
        "bone_parents": {},
        "rest_heads_m": {},
        "animations": {name: a["duration_s"] for name, a in summary["animations"].items()},
        "height_m": None,
        "seams": {},
    }


class Checks:
    def __init__(self) -> None:
        self.items: list[dict[str, str]] = []

    def add(self, name: str, good: bool, detail: str, severity: str = "fail") -> None:
        self.items.append({"check": name, "status": "pass" if good else severity, "detail": detail})


def _dist(a: list[float], b: list[float]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _centre(bounds: dict[str, list[float]]) -> list[float]:
    return [(lo + hi) / 2 for lo, hi in zip(bounds["min"], bounds["max"])]


def _part(dump: dict[str, Any], slot: str) -> dict[str, Any] | None:
    return next((m for m in dump["meshes"] if m["name"].endswith(f"_{slot}") and m.get("rest_bounds")), None)


def evaluate(dump: dict[str, Any], expect: dict[str, Any], contract: dict[str, Any], output: list[str],
             strict_contract: bool = False, renamed: dict[str, str] | None = None) -> list[dict[str, str]]:
    """The assertions of godot-check on inspect.gd's description of an imported character (docs/godot.md). renamed maps
    the rig's bone names to the names the import gave them (the SkeletonProfileHumanoid trial); then the bone set is
    compared through it and the rest joints are not compared. Contract v1 gates are warnings unless strict_contract."""
    renamed = renamed or {}
    c = Checks()
    skeletons = dump["skeletons"]
    c.add("one_skeleton", len(skeletons) == 1, f"{len(skeletons)} Skeleton3D: {', '.join(s['path'] for s in skeletons) or 'none'}")
    skeleton = skeletons[0] if len(skeletons) == 1 else {"path": "", "bones": [], "parents": [], "rest_joints": {}}
    want_bones = [renamed.get(b, b) for b in expect["bones"]]
    got = skeleton["bones"]
    missing, extra = sorted(set(want_bones) - set(got)), sorted(set(got) - set(want_bones))
    c.add("skeleton_bones", not missing and not extra and len(got) == len(want_bones),
          f"{len(got)} bones, the rig has {len(want_bones)}" + (f"; missing {missing}" if missing else "") + (f"; extra {extra}" if extra else ""))
    if expect.get("bone_parents") and got:
        wrong = []
        for bone, parent in expect["bone_parents"].items():
            name = renamed.get(bone, bone)
            if name not in got:
                continue
            index = skeleton["parents"][got.index(name)]
            have = got[index] if index >= 0 else None
            if have != (renamed.get(parent, parent) if parent else None):
                wrong.append(f"{name} under {have}")
        c.add("bone_hierarchy", not wrong, "every bone under its rig parent" if not wrong else "; ".join(wrong[:8]))
    if expect.get("rest_heads_m") and not renamed:
        worst, worst_bone = 0.0, ""
        for bone, head in expect["rest_heads_m"].items():
            if bone in skeleton["rest_joints"]:
                d = _dist(head, skeleton["rest_joints"][bone])
                if d > worst:
                    worst, worst_bone = d, bone
        c.add("rest_joints", worst <= JOINT_TOLERANCE_M,
              f"rest joints within {worst * 1000:.3f} mm of Blender's bone heads (worst {worst_bone or '-'}; allowed {JOINT_TOLERANCE_M * 1000:.0f} mm)")

    meshes = {m["name"]: m for m in dump["meshes"]}
    parts = expect["parts"]
    c.add("parts_separate", sorted(meshes) == sorted(parts),
          f"{len(meshes)} MeshInstance3D ({', '.join(sorted(meshes))}); the export has {len(parts)} parts"
          + ("" if sorted(meshes) == sorted(parts) else f"; missing {sorted(set(parts) - set(meshes))}, extra {sorted(set(meshes) - set(parts))}"))
    bad = []
    for name, m in sorted(meshes.items()):
        if not m["skin"]:
            bad.append(f"{name}: no Skin")
        elif m["skeleton"] != skeleton["path"] or not m["skeleton_is_skeleton3d"]:
            bad.append(f"{name}: bound to {m['skeleton'] or 'nothing'}, not {skeleton['path']}")
        elif m["unresolved_binds"]:
            bad.append(f"{name}: binds {m['unresolved_binds'][:5]} name no bone")
    c.add("parts_skinned", not bad and bool(meshes),
          f"every part has a Skin bound to {skeleton['path']} ({len(next(iter(meshes.values()))['binds']) if meshes else 0} binds each)" if not bad else "; ".join(bad))

    players = dump["players"]
    c.add("one_animation_player", len(players) == 1, f"{len(players)} AnimationPlayer")
    anims = players[0]["animations"] if players else {}
    want = expect["animations"]
    c.add("animations", sorted(anims) == sorted(want),
          f"{len(anims)} animations, the export has {len(want)}" + ("" if sorted(anims) == sorted(want) else
          f"; missing {sorted(set(want) - set(anims))}, extra {sorted(set(anims) - set(want))}"))
    wrong_length = [f"{n} {anims[n]['length']:.4f} s (want {s:.4f})" for n, s in sorted(want.items())
                    if n in anims and abs(anims[n]["length"] - s) > LENGTH_TOLERANCE_S]
    c.add("animation_lengths", not wrong_length, "every animation as long as its action" if not wrong_length else "; ".join(wrong_length))
    unresolved = {n: a["unresolved"] for n, a in anims.items() if a["unresolved"]}
    warned = [line for line in output if "couldn't resolve track" in line]
    tracks = sum(a["tracks"] for a in anims.values())
    c.add("tracks_resolve", not unresolved and not warned,
          f"all {tracks} tracks of {len(anims)} animations resolve to a node and bone" if not unresolved and not warned else
          "; ".join(f"{n}: {len(p)} unresolved, e.g. {p[0]}" for n, p in sorted(unresolved.items())) + "; ".join(warned[:3]))
    still = [n for n, a in sorted(anims.items()) if not a["motion"] or
             (a["motion"]["max_rotation_deg"] < MOVE_MIN_DEG and a["motion"]["max_translation_m"] < MOVE_MIN_M)]
    least = min(anims.items(), key=lambda kv: kv[1]["motion"].get("max_rotation_deg", 0.0)) if anims else None
    c.add("animations_move", not still and bool(anims),
          (f"every animation moves bones between 0, 1/3 and 2/3 of its length (least: {least[0]}, "
           f"{least[1]['motion']['max_rotation_deg']:.1f} deg on {least[1]['motion']['most_moved_bone']})") if not still and least else
          f"no bone moves {MOVE_MIN_DEG} deg or {MOVE_MIN_M * 1000:.0f} mm in: {', '.join(still)}")

    boxes = [m["rest_bounds"] for m in dump["meshes"] if m.get("rest_bounds")]
    body = contract["body"]
    if boxes:
        low = min(b["min"][1] for b in boxes)
        high = max(b["max"][1] for b in boxes)
        height = high - low
        if expect.get("height_m") is not None:
            c.add("size_kept", abs(height - expect["height_m"]) <= SIZE_TOLERANCE_M,
                  f"rest height {height:.4f} m in Godot, {expect['height_m']:.4f} m in Blender (allowed {SIZE_TOLERANCE_M * 1000:.0f} mm)")
        c.add("feet_at_zero", abs(low) <= body["feet_tolerance_m"],
              f"the lowest skinned vertex at y = {low:.4f} m (contract: within {body['feet_tolerance_m']} m of 0)")
        _facing(c, dump, skeleton, renamed)
        rules = contract["kinds"]["body"]
        severity = rules["height"] if strict_contract else "warn"
        c.add("contract_height", body["height_min_m"] <= height <= body["height_max_m"],
              f"{height:.3f} m to the top (contract v1: {body['height_min_m']} to {body['height_max_m']} m)", severity)
        eyes = _part(dump, "eyes")
        if eyes:
            eye = _centre(eyes["rest_bounds"])[1]
            c.add("contract_eye_height", abs(eye - body["eye_height_m"]) <= body["eye_tolerance_m"],
                  f"eyes at {eye:.3f} m (contract v1: {body['eye_height_m']} +- {body['eye_tolerance_m']} m)",
                  rules["eyes"] if strict_contract else "warn")
    else:
        c.add("feet_at_zero", False, "no skinned vertices to measure")
    textured = [f"{m['name']}/{mat['name']}" for m in dump["meshes"] for mat in m["materials"] if mat.get("textured")]
    c.add("flat_colours", not textured, "every surface a flat albedo colour, no texture" if not textured else f"textured: {', '.join(textured)}")
    errors = [line for line in output if line.startswith(("ERROR", "SCRIPT ERROR", "USER ERROR"))]
    warnings = [line for line in output if not line.startswith(("ERROR", "SCRIPT ERROR", "USER ERROR"))]
    c.add("godot_output", not errors, f"{len(errors)} errors, {len(warnings)} warnings in Godot's import and inspection output"
          + (f": {errors[0]}" if errors else ""))
    return c.items


def _facing(c: Checks, dump: dict[str, Any], skeleton: dict[str, Any], renamed: dict[str, str]) -> None:
    """Front +Z: the eyes in front of the Head joint, the shoes reaching further forward than back from the ankles, and
    the character's left wrist at +X."""
    joints = skeleton["rest_joints"]
    name = lambda bone: renamed.get(bone, bone)  # noqa: E731
    needed = [name(b) for b in ("Head", "Foot.L", "Foot.R", "Wrist.L", "Wrist.R")]
    eyes, shoes = _part(dump, "eyes"), _part(dump, "shoes")
    if not all(b in joints for b in needed) or eyes is None or shoes is None:
        c.add("facing_plus_z", False, f"cannot tell: needs the bones {needed}, an _eyes and a _shoes part")
        return
    head, foot_l, foot_r, wrist_l, wrist_r = (joints[b] for b in needed)
    ahead = _centre(eyes["rest_bounds"])[2] - head[2]
    foot_z = (foot_l[2] + foot_r[2]) / 2
    toes = shoes["rest_bounds"]["max"][2] - foot_z
    heels = foot_z - shoes["rest_bounds"]["min"][2]
    left = wrist_l[0] - wrist_r[0]
    good = ahead >= FACE_AHEAD_M and toes > heels and left > 0
    c.add("facing_plus_z", good, f"eyes {ahead * 100:+.1f} cm ahead of the Head joint, shoes reach {toes * 100:.1f} cm forward "
          f"and {heels * 100:.1f} cm back from the ankles, left wrist at {'+X' if left > 0 else '-X'}")


def load_contract() -> dict[str, Any]:
    return _contract.load_contract()
