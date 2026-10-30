"""Helpers for godot-check and frames: the art repo's Godot project (godot/), staging and importing a GLB headless,
running the inspection script, and the assertions on its description (docs/godot.md). The assertions are pure Python
(evaluate()), so the tests run them without Godot."""

from __future__ import annotations

import json
import os
import re
import shutil
import time
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
HELD_CLIP = re.compile(r"(^|\|)Pose(Legs|Arms)_")  # held poses (art #196, the photo poses): identical keys by design,
# so they must NOT move; every other animation must
SIZE_TOLERANCE_M = 0.002  # Godot's rest-pose height equals Blender's
JOINT_TOLERANCE_M = 0.001  # Godot's rest joints equal Blender's bone heads
LENGTH_TOLERANCE_S = 1e-3
FACE_AHEAD_M = 0.05  # the eyes sit at least this far in front of the Head joint
# The Ultimate Modular rig: the floor a GLB without its export.json is held to (expectations() then reads the GLB).
PACK_BONES = 62
PACK_ANIMATIONS = 24
# the alien profile (art #196 B2, `godot-check --profile alien`): the shared alien body's clips (S4b), the floor of an
# alien character without its .export.json; its eyes are part of the head mesh, its bones the contract's own names
ALIEN_CLIPS = ("Crouch_Fwd", "Crouch_Idle", "Idle", "Jog_Fwd", "Jump_Air", "Jump_Land", "Jump_Start", "Sprint_Fwd",
               "Talk_Upper", "Walk")
# near-white and near-black each at least this share of the eye caps' vertices: half the smallest share measured
# (B4, r5: chameleon 2282 white and 182 black of 5228, 43.6 % and 3.5 %; axolotl 1495 and 607 of 2485, 60 % and 24 %)
ALIEN_EYE_SHARE = 0.017
PROFILES = ("pack", "alien")
# The alien heads' spring bones beyond the contract's 56 are declared in contract/contract.toml ([kinds.alien]
# spring_sets under spring_parent, bones = "all_and_springs"; the engineer, art #196 comment 6374319309):
# alien_extra_bones passes whole sets under Head and fails any other extra bone or a set in part, in every mode.
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


# Godot's scene importer gives an animation whose name ends in _loop, -loop, _cycle or -cycle (any case; trailing digits,
# spaces and underscores ignored; also "loop_mode") the loop mode LINEAR and drops that suffix: an animation set's
# "Idle_Loop" is "Idle" in Godot (art #33; measured with godot-check on the MVP set).
LOOP_WORDS = ("loop_mode", "loop", "cycle")


def godot_name(name: str) -> tuple[str, bool]:
    """The name Godot's importer gives an animation and whether it makes it loop (its loop suffix)."""
    loops = False
    for word in LOOP_WORDS:
        what = name
        while what and (what[-1].isdigit() or what[-1] <= " " or what[-1] == "_"):
            what = what[:-1]
        end = name[len(what):]
        low = what.lower()
        if "$" + word in low:
            i = low.index("$" + word)
            name, loops = what[:i] + what[i + len(word) + 1:] + end, True
        elif low.endswith("-" + word) or low.endswith("_" + word):
            name, loops = what[: len(what) - len(word) - 1] + end, True
    return name, loops


def import_params(glb: Path) -> dict[str, Any]:
    """The import options for a GLB: IMPORT_PARAMS, with animation/fps the export's own fps when its .export.json says
    (an animation set is baked at 30 fps: imported at 24 its keys would be resampled, art #33)."""
    info_path = glb.with_name(f"{glb.stem}.export.json")
    if info_path.is_file():
        fps = json.loads(info_path.read_text(encoding="utf-8")).get("fps")
        if fps:
            return {**IMPORT_PARAMS, "animation/fps": fps}
    return dict(IMPORT_PARAMS)


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


def clear_staged(keep: set[str]) -> list[str]:
    """Removes the GLBs (and their .import files) an earlier run left in godot/import/ whose stem is not in keep, so
    that `--import` imports only this run's files and their errors cannot land on another character. One run at a time
    (docs/godot.md). Returns the removed names."""
    removed = []
    for glb in sorted(IMPORT_DIR.glob("*.glb")) if IMPORT_DIR.is_dir() else []:
        if glb.stem not in keep:
            glb.unlink()
            glb.with_name(glb.name + ".import").unlink(missing_ok=True)
            removed.append(glb.name)
    return removed


def noteworthy(output: str) -> list[str]:
    """Godot's error and warning lines (with the "at:" line that follows each), colour codes removed."""
    lines = [ANSI.sub("", line).rstrip() for line in output.splitlines()]
    found = []
    for i, line in enumerate(lines):
        if line.lstrip().startswith(NOTEWORTHY) or "couldn't resolve track" in line:
            where = lines[i + 1].strip() if i + 1 < len(lines) and lines[i + 1].strip().startswith("at:") else ""
            found.append(f"{line.strip()} {where}".strip())
    return found


def lines_for(lines: list[str], res_path: str, staged: list[str]) -> list[str]:
    """Godot's import lines that belong to res_path: those that name it, and those that name no staged file (an error
    that does not say where it came from counts against every file of the run)."""
    others = [p for p in staged if p != res_path]
    return [line for line in lines if res_path in line or not any(p in line for p in others)]


def godot(args: list[str], timeout: float, env: dict[str, str] | None = None) -> tuple[int, str]:
    result = common.run([common.godot_bin(), *args], timeout, env=env)
    return result.returncode, (result.stdout or "") + (result.stderr or "")


# The off-screen review window (#214, docs/godot.md). Godot 4.7.2 on Windows clamps a new window's position into the
# primary screen's usable area, up to its far edge minus a third of the window's size, whatever --position asks. A
# borderless 1x1 window's third is 0, so asked far right and down it opens at (screen width, usable height): just past
# the screen's right edge. godot/lib/offscreen.gd then moves it to -30000,-30000 and grows it to WINDOW_ENV's size.
OFFSCREEN_GD = PROJECT / "lib" / "offscreen.gd"
WINDOW_ENV = "PRIME_WINDOW"
WINDOW_START = ["--position", "30000,30000", "--resolution", "1x1"]
WINDOW_SETTINGS = ("window/size/borderless=true", "window/size/no_focus=true")  # [display] of every window project
_OFFSCREEN = re.compile(r"OFFSCREEN window (-?\d+),(-?\d+) (\d+)x(\d+) screens (\S+)")


def window_env(size: tuple[int, int]) -> dict[str, str]:
    w, h = size
    if w <= 0 or h <= 0:
        raise ValueError(f"window size {w}x{h}")
    return {WINDOW_ENV: f"{w}x{h}"}


def _overlap(a: tuple[int, ...], b: tuple[int, ...]) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def offscreen_problems(output: str) -> list[str]:
    """Why a window run's output does not prove its window stayed off every screen: no OFFSCREEN line (the script
    never placed its window), or a line whose window rect meets one of the screens it lists. Empty: proven."""
    found = _OFFSCREEN.findall(ANSI.sub("", output))
    if not found:
        return ["no OFFSCREEN line: the script never moved its window off-screen (godot/lib/offscreen.gd place())"]
    problems = []
    for x, y, w, h, screens in found:
        rect = (int(x), int(y), int(w), int(h))
        for i, screen in enumerate(screens.split(";")):
            try:
                s = tuple(int(v) for v in screen.split(","))
            except ValueError:
                s = ()
            if len(s) != 4:
                problems.append(f"screen {i} of the OFFSCREEN line is not <x>,<y>,<w>,<h>: {screen!r}")
                continue
            if _overlap(rect, s):
                problems.append(f"the {w}x{h} window at {x},{y} is on screen {i} ({s[2]}x{s[3]} at {s[0]},{s[1]})")
    return problems


def install_offscreen(project: Path) -> None:
    """Copies offscreen.gd into another Godot project's lib/ (godot/ragdoll, the House export and review folders)."""
    project = Path(project)
    if project.resolve() != PROJECT.resolve():
        (project / "lib").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(OFFSCREEN_GD, project / "lib" / OFFSCREEN_GD.name)


def window(args: list[str], size: tuple[int, int], timeout: float, log: Path | None = None) -> tuple[int, str]:
    """Runs a Godot window script (args: --path and the rest, no --position or --resolution) in a window of size that
    never shows on a screen; the script calls godot/lib/offscreen.gd place() first. Raises Failure when the output
    does not prove the window stayed off every screen (offscreen_problems), after writing the run's whole output to
    log (the caller's log; None: a new file under tools/out/godot-window/)."""
    install_offscreen(Path(args[args.index("--path") + 1]))
    code, output = godot([*WINDOW_START, *args], timeout, env=window_env(size))
    problems = offscreen_problems(output)
    if problems:
        if log is None:
            log = common.OUT / "godot-window" / f"{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}.log"
        log = Path(log)
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(output, encoding="utf-8")
        tail = "\n".join(ANSI.sub("", output).splitlines()[-8:])
        if code != 0 and not _OFFSCREEN.search(ANSI.sub("", output)):
            head = (f"Godot exited {code}: the script failed before placing its window off-screen (no OFFSCREEN line,"
                    " godot/lib/offscreen.gd place())")
        else:
            head = (f"Godot's window was not proven off-screen (#214, docs/godot.md): {'; '.join(problems[:3])}"
                    f"\nexit code {code}")
        raise common.Failure(f"{head}\nthe whole output: {log.as_posix()}; its last lines:\n{tail}")
    return code, output


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
        names = {name: godot_name(name) for name in info["actions"]}  # Godot drops a loop suffix (art #33)
        return {
            "source": info_path.name,
            "parts": sorted(info["parts"]),
            "bones": list(info["bones"]),
            "bone_parents": info.get("bone_parents", {}),
            "rest_heads_m": info.get("rest_heads_m", {}),
            "animations": {names[name][0]: (end - start) / fps for name, (start, end) in info["actions"].items()},
            "height_m": info.get("height_m"),
            "seams": {names[name][0]: seam for name, seam in info.get("seams", {}).items() if name in names},
            "fps": fps,
            "actions": {g: name for name, (g, _) in names.items()},
            "loop_suffix": sorted(g for g, loops in names.values() if loops),
        }
    return expect_from_summary(glb.name, _export.summarize(_export.glb_json(glb)))


def expect_from_summary(source: str, summary: dict[str, Any]) -> dict[str, Any]:
    """The expectations from a GLB's own summary (_export.summarize) when no .export.json lies beside it: the
    animations under the names Godot gives them (a loop suffix dropped, art #33), and those must import looping."""
    names = {name: godot_name(name) for name in summary["animations"]}
    return {
        "source": source,
        "parts": sorted(summary["meshes"]),
        "bones": summary["skins"][0] if summary["skins"] else [],
        "bone_parents": {},
        "rest_heads_m": {},
        "animations": {names[name][0]: a["duration_s"] for name, a in summary["animations"].items()},
        "height_m": None,
        "seams": {},
        "loop_suffix": sorted(g for g, loops in names.values() if loops),
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
             strict_contract: bool = False, renamed: dict[str, str] | None = None,
             textured: bool = False, profile: str = "pack", allowance: str = "",
             body_type: str = "") -> list[dict[str, str]]:
    """The assertions of godot-check on inspect.gd's description of an imported character (docs/godot.md). renamed maps
    the rig's bone names to the names the import gave them (the SkeletonProfileHumanoid trial); then the bone set is
    compared through it and the rest joints are not compared. Contract v1 gates are warnings unless strict_contract.
    textured (a baked clay character): the textured checks (_textured) replace flat_colours. profile "alien" (art #196
    B2): the alien kind's own equivalents of the Ultimate Modular rules: facing_plus_z from the LeftEye and RightEye
    bones and the contract's bone names, eye_pupils on the head mesh's eye caps, pack_floor the contract skeleton's
    weighted bones (each the heaviest bone of some vertex) and the shared alien body's clips (ALIEN_CLIPS), and
    alien_extra_bones (whole [kinds.alien] spring_sets below spring_parent pass; any other extra bone fails).
    allowance (the alien profile only, B4): a named height allowance of the contract's body
    (`<allowance>_height_max_m`, e.g. "plasticine"); without one the alien profile holds [kinds.alien]'s rule (the
    body below the Head's skin at most height_max_m, the top at most head_top_max_m), textured or not."""
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r} (known: {', '.join(PROFILES)})")
    if allowance and (profile != "alien" or f"{allowance}_height_max_m" not in contract["body"]):
        raise ValueError(f"no height allowance {allowance!r} for the {profile} profile (the contract's body has "
                         f"{sorted(k for k in contract['body'] if k.endswith('_height_max_m'))})")
    if body_type:  # art #196: a body type's own table replaces the body's height_min_m (the alien only)
        types = contract.get("body_types", {})
        if profile != "alien" or body_type not in types:
            raise ValueError(f"no body type {body_type!r} for the {profile} profile (the contract has {sorted(types)})")
        contract = {**contract, "body": {**contract["body"], "height_min_m": types[body_type]["height_min_m"]}}
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
    if profile == "alien":
        _alien_extra_bones(c, skeleton, renamed, contract)
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
    def _still(a: dict) -> bool:
        return not a["motion"] or (a["motion"]["max_rotation_deg"] < MOVE_MIN_DEG and
                                   a["motion"]["max_translation_m"] < MOVE_MIN_M)

    held = {n: a for n, a in anims.items() if HELD_CLIP.search(n)}
    moving = {n: a for n, a in anims.items() if n not in held}
    still = [n for n, a in sorted(moving.items()) if _still(a)]
    least = min(moving.items(), key=lambda kv: kv[1]["motion"].get("max_rotation_deg", 0.0)) if moving else None
    c.add("animations_move", not still and bool(moving),
          (f"every animation moves bones between 0, 1/3 and 2/3 of its length (least: {least[0]}, "
           f"{least[1]['motion']['max_rotation_deg']:.1f} deg on {least[1]['motion']['most_moved_bone']})") if not still and least else
          f"no bone moves {MOVE_MIN_DEG} deg or {MOVE_MIN_M * 1000:.0f} mm in: {', '.join(still)}")
    if held:
        drift = [n for n, a in sorted(held.items()) if not _still(a)]
        c.add("held_poses_hold", not drift,
              f"all {len(held)} held pose clips (PoseLegs_/PoseArms_) keep every bone still" if not drift else
              f"held pose clips that move: {', '.join(drift)}")

    _loops(c, anims, expect.get("seams", {}))
    if expect.get("loop_suffix"):  # animations named as loops: Godot must import them looping (art #33)
        once = [n for n in expect["loop_suffix"] if n in anims and not anims[n].get("loop_mode", 0)]
        c.add("loop_suffix", not once, f"all {len(expect['loop_suffix'])} animations named as loops (_Loop) import "
              f"with loop_mode LINEAR under their name without it" if not once else
              f"named as loops but import playing once: {', '.join(once)}")

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
        (_facing_alien if profile == "alien" else _facing)(c, dump, skeleton, renamed)
        rules = contract["kinds"]["body"]
        severity = rules["height"] if strict_contract else "warn"
        if profile == "alien" and not allowance:  # art #196 comment 6374319309: the head may pass the capsule
            _alien_height(c, dump, skeleton, renamed, contract, low, height, severity)
        else:
            if profile == "alien":  # B4: a named allowance replaces the alien rule (never the paused plasticine's)
                top = body[f"{allowance}_height_max_m"]
                look = f" with the {allowance} allowance"
            else:
                top = body["plasticine_height_max_m"] if textured else body["height_max_m"]  # the baked clay look
                look = " for the plasticine look" if textured else ""
            c.add("contract_height", body["height_min_m"] <= height <= top,
                  f"{height:.3f} m to the top (contract v1{look}: {body['height_min_m']} to {top} m)", severity)
        eyes = _part(dump, "eyes")
        if eyes:
            eye = _centre(eyes["rest_bounds"])[1]
            c.add("contract_eye_height", abs(eye - body["eye_height_m"]) <= body["eye_tolerance_m"],
                  f"eyes at {eye:.3f} m (contract v1: {body['eye_height_m']} +- {body['eye_tolerance_m']} m)",
                  rules["eyes"] if strict_contract else "warn")
    else:
        c.add("feet_at_zero", False, "no skinned vertices to measure")
    if textured:
        _textured(c, dump, contract, profile)
    else:
        textured_ = [f"{m['name']}/{mat['name']}" for m in dump["meshes"] for mat in m["materials"] if mat.get("textured")]
        c.add("flat_colours", not textured_, "every surface a flat albedo colour, no texture" if not textured_ else
              f"textured: {', '.join(textured_)}")
    errors = [line for line in output if line.startswith(("ERROR", "SCRIPT ERROR", "USER ERROR"))]
    warnings = [line for line in output if not line.startswith(("ERROR", "SCRIPT ERROR", "USER ERROR"))]
    c.add("godot_output", not errors, f"{len(errors)} errors, {len(warnings)} warnings in Godot's import and inspection output"
          + (f": {errors[0]}" if errors else ""))
    if not expect["source"].endswith(".export.json"):
        c.add("expectations", False, f"no .export.json beside the GLB: the parts, bones and animations come from "
              f"{expect['source']} itself, so what the GLB already lacks is not caught, and the rest joints, the bone "
              f"hierarchy and Blender's height are not compared", "warn")
        if profile == "alien":
            weighted = list(contract["skeleton"]["weighted"])
            lack_b = [b for b in weighted if renamed.get(b, b) not in got]
            heavy = {b for m in dump["meshes"] for b in (m.get("bone_bounds") or {})}  # B4: the weights counted
            lack_w = [b for b in weighted if renamed.get(b, b) in got and renamed.get(b, b) not in heavy]
            labels = {n.rsplit("|", 1)[-1].removesuffix("_Loop") for n in anims}
            lack_c = [n for n in ALIEN_CLIPS if n not in labels]
            c.add("pack_floor", not lack_b and not lack_w and not lack_c,
                  f"alien profile: {len(weighted) - len(lack_b)} of the contract's {len(weighted)} weighted bones "
                  f"({len(weighted) - len(lack_b) - len(lack_w)} the heaviest bone of some vertex), "
                  f"{len(ALIEN_CLIPS) - len(lack_c)} of the shared alien body's {len(ALIEN_CLIPS)} clips"
                  + (f"; missing bones {lack_b}" if lack_b else "") + (f"; no vertex weighted to {lack_w}" if lack_w else "") + (f"; missing clips {lack_c}" if lack_c else ""))
        else:
            c.add("pack_floor", len(got) >= PACK_BONES and len(anims) >= PACK_ANIMATIONS,
                  f"{len(got)} bones and {len(anims)} animations (the Ultimate Modular rig has {PACK_BONES} bones and "
                  f"{PACK_ANIMATIONS} actions)")
    return c.items


def _textured(c: Checks, dump: dict[str, Any], contract: dict[str, Any], profile: str = "pack") -> None:
    """A baked clay character as Godot imported it: textured surfaces with their normal maps, no texture side over the
    contract's texture_character_px, the surfaces within its surfaces_per_character_cap."""
    limits = contract["budgets"]["limits"]
    mats = [(m["name"], mat) for m in dump["meshes"] for mat in m["materials"]]
    with_tex = [f"{n}/{mat['name']}" for n, mat in mats if mat.get("textured")]
    c.add("textured", bool(with_tex), f"{len(with_tex)} of {len(mats)} surfaces textured" if with_tex else "no textured surface")
    flat_nrm = [f"{n}/{mat['name']}" for n, mat in mats if mat.get("textured") and not mat.get("normal_mapped")
                and not n.endswith("_eyes")]
    c.add("normal_maps", not flat_nrm, "every textured surface normal-mapped (the _eyes part aside)" if not flat_nrm
          else f"textured without a normal map: {', '.join(flat_nrm)}")
    good, detail = eye_caps(dump) if profile == "alien" else eye_pupils(dump)
    c.add("eye_pupils", good, detail)
    sides = [max(mat.get(k) or [0]) for _, mat in mats for k in ("albedo_px", "normal_px")]
    cap_px = limits["texture_character_px"]
    c.add("texture_size", max(sides, default=0) <= cap_px,
          f"largest texture side {max(sides, default=0)} px (contract: {cap_px})")
    surfaces = sum(m["surfaces"] for m in dump["meshes"])
    cap = limits["surfaces_per_character_cap"]
    c.add("surfaces_cap", surfaces <= cap, f"{surfaces} surfaces (contract: target {limits['surfaces_per_character_target']}, "
          f"cap {cap})")


def eye_pupils(dump: dict[str, Any], least: float = 0.02) -> tuple[bool, str]:
    """Whether the eyes show their pupils as Godot draws them (art #42): the _eyes part's surfaces, from inspect.gd's
    tones (the albedo at each vertex: colour, vertex colour if used as albedo, texture at the UV), need both
    near-white and near-black vertices, each at least `least` of the vertices."""
    eyes = _part(dump, "eyes")
    if eyes is None:
        return False, "no _eyes part"
    tones = [mat["tones"] for mat in eyes["materials"] if mat.get("tones")]
    if not tones:
        return False, f"{eyes['name']}: no albedo tones in the dump"
    n = sum(t["vertices"] for t in tones)
    white, black = sum(t["white"] for t in tones), sum(t["black"] for t in tones)
    good = n > 0 and white >= least * n and black >= least * n
    how = "texture" if any(t.get("image") for t in tones) else (
        "vertex colours" if any(t.get("uses_vertex_colours") for t in tones) else "flat colour")
    unused = " (COLOR_0 present, not used as albedo)" if any(
        t.get("has_vertex_colours") and not t.get("uses_vertex_colours") for t in tones) else ""
    return good, (f"{eyes['name']}: {white} near-white, {black} near-black of {n} vertices from the {how}{unused}"
                  + ("" if good else ": no pupils"))


def eye_caps(dump: dict[str, Any], least: float = ALIEN_EYE_SHARE) -> tuple[bool, str]:
    """eye_pupils for the alien profile: its eyes are part of the head mesh, so inspect.gd's eye_tones (the albedo at
    the vertices of the eyes' front caps round the LeftEye and RightEye bones) need near-white (the sclera) and
    near-black (the pupils) vertices, each at least `least` of the caps' vertices."""
    caps = [m["eye_tones"] for m in dump["meshes"] if m.get("eye_tones")]
    if not caps:
        return False, "alien profile: no eye caps in the dump (no LeftEye/RightEye bones, or an _eyes part)"
    n = sum(t["vertices"] for t in caps)
    white, black = sum(t["white"] for t in caps), sum(t["black"] for t in caps)
    good = n > 0 and white >= least * n and black >= least * n
    return good, (f"alien profile: the eye caps (within {caps[0].get('cap_m', 0) * 100:.1f} cm of the eye bones): "
                  f"{white} near-white, {black} near-black of {n} vertices" + ("" if good else ": no pupils"))


def _facing_alien(c: Checks, dump: dict[str, Any], skeleton: dict[str, Any], renamed: dict[str, str]) -> None:
    """facing_plus_z for the alien profile: the eyes are the LeftEye and RightEye bones (on the head mesh's eye
    centres), the feet the skin of the contract's foot and toe bones, the wrists its hand bones."""
    joints = skeleton["rest_joints"]
    name = lambda bone: renamed.get(bone, bone)  # noqa: E731
    needed = [name(b) for b in ("Head", "LeftEye", "RightEye", "LeftFoot", "RightFoot", "LeftHand", "RightHand")]
    feet = _body_feet(dump, [name(b) for b in ("LeftFoot", "RightFoot", "LeftToes", "RightToes")])
    if not all(b in joints for b in needed) or feet is None:
        c.add("facing_plus_z", False, f"alien profile: cannot tell: needs the bones {needed} and skin on the foot and "
              f"toe bones")
        return
    head, eye_l, eye_r, foot_l, foot_r, hand_l, hand_r = (joints[b] for b in needed)
    caps = [m["eye_tones"] for m in dump["meshes"] if (m.get("eye_tones") or {}).get("near_vertices")]
    if not caps:
        c.add("facing_plus_z", False, "alien profile: cannot tell: no eye surface round the eye bones in the dump "
              "(inspect.gd's eye_tones near_vertices)")
        return
    # B4 review: from the geometry: the eye surfaces round the eye centres bulge forward, and their centres sit
    # ahead of the Head joint
    bulge = sum(t["bulge"][2] * t["near_vertices"] for t in caps) / sum(t["near_vertices"] for t in caps)
    ahead = caps[0]["eye_mid"][2] - head[2]
    foot_z = (foot_l[2] + foot_r[2]) / 2
    toes, heels = feet["max"][2] - foot_z, foot_z - feet["min"][2]
    left = hand_l[0] - hand_r[0]
    good = ahead >= FACE_AHEAD_M and bulge > 0 and toes > heels and left > 0 and eye_l[0] > eye_r[0]
    c.add("facing_plus_z", good, f"alien profile: the eye surfaces bulge {bulge * 1000:+.1f} mm in z round eye "
          f"centres {ahead * 100:+.1f} cm ahead of the Head joint, bare feet "
          f"reach {toes * 100:.1f} cm forward and {heels * 100:.1f} cm back from the ankles, left hand at "
          f"{'+X' if left > 0 else '-X'}, left eye at {'+X' if eye_l[0] > eye_r[0] else '-X'}")


def _parent_names(skeleton: dict[str, Any]) -> dict[str, str]:
    """Each bone of a dumped Skeleton3D to its parent's name ("" for a root or an unknown parent)."""
    bones, parents = skeleton.get("bones", []), skeleton.get("parents", [])
    return {b: (bones[parents[i]] if i < len(parents) and 0 <= parents[i] < len(bones) else "")
            for i, b in enumerate(bones)}


def _below(top: str, parent_of: dict[str, str]) -> set[str]:
    """top and every bone below it."""
    out = set()
    for bone in parent_of:
        seen, b = set(), bone
        while b and b not in seen:
            if b == top:
                out.add(bone)
                break
            seen.add(b)
            b = parent_of.get(b, "")
    return out


def _alien_extra_bones(c: Checks, skeleton: dict[str, Any], renamed: dict[str, str],
                       contract: dict[str, Any] | None = None) -> None:
    """Every bone beyond the contract profile's, named, against `[kinds.alien]`'s spring rule (bones =
    "all_and_springs", art #196 comment 6374319309): whole spring_sets chained under spring_parent pass (each spring
    bone directly under it or under the bone before it in its chain, a chain's first bone under it alone); an extra bone in no set, a set in part or a
    spring bone off its chain fails, with or without --strict-contract."""
    got = skeleton["bones"]
    profile_bones = {renamed.get(b, b) for b in _contract.profile_parents(_contract.load_profile())}
    extra = [b for b in got if b not in profile_bones]
    if not extra:
        c.add("alien_extra_bones", True, f"alien profile: {len(got)} bones, the contract's {len(profile_bones)}, "
              "no extra bone")
        return
    rules = (contract or _contract.load_contract())["kinds"]["alien"]
    top = renamed.get(rules.get("spring_parent", ""), rules.get("spring_parent", ""))
    split = _contract.spring_split({**rules, "spring_parent": top}, extra, _parent_names(skeleton))
    bad = split["stray"] or split["partial"] or split["unchained"]
    named = "; ".join(f"the {n} springs {v}" for n, v in split["sets"].items())
    c.add("alien_extra_bones", not bad,
          f"alien profile: {len(got)} bones: {len(got) - len(extra)} of the contract's {len(profile_bones)} and "
          f"{len(extra)} extra: {named or '-'}"
          + (f"; not in a declared spring set: {split['stray']}" if split["stray"] else "")
          + (f"; spring sets in part: {split['partial']}" if split["partial"] else "")
          + (f"; not chained under {top}: {split['unchained']}" if split["unchained"] else "")
          + (f"; all in whole declared spring sets chained under {top} (contract [kinds.alien] bones = \"{rules['bones']}\")"
             if not bad else ""))


def _alien_height(c: Checks, dump: dict[str, Any], skeleton: dict[str, Any], renamed: dict[str, str],
                  contract: dict[str, Any], low: float, height: float, severity: str) -> None:
    """contract_height for the alien: the binding rule is the whole height from body.height_min_m to [kinds.alien]
    head_top_max_m (the art manager's sanity cap against a runaway scale; the eye height is contract_eye_height's).
    The body, the skin whose heaviest bone is not spring_parent or below it (inspect.gd's bone_bounds), is also held
    to body.height_max_m and reported, but on a real alien it never binds: r5's chameleon has 1.418 m of body under a
    1.884 m top, so it would take a scale of about 1.27 before the body passed 1.80 m."""
    body, rules = contract["body"], contract["kinds"]["alien"]
    cap = rules.get("head_top_max_m", body["height_max_m"])
    top = renamed.get(rules.get("spring_parent", "Head"), rules.get("spring_parent", "Head"))
    head = _below(top, _parent_names(skeleton))
    boxes = [box for m in dump["meshes"] for b, box in (m.get("bone_bounds") or {}).items() if b not in head]
    trunk = max(box["max"][1] for box in boxes) - low if boxes else None
    good = body["height_min_m"] <= height <= cap and trunk is not None and trunk <= body["height_max_m"]
    c.add("contract_height", good,
          f"{height:.3f} m to the top (the binding rule: {body['height_min_m']} to {cap} m); "
          + (f"the body below {top}'s skin {trunk:.3f} m" if trunk is not None else "no skin outside the head to measure")
          + f" (reported against {body['height_max_m']} m; it never binds on a real alien, the head top and the eye"
          " height bind first)", severity)


def _loops(c: Checks, anims: dict[str, Any], seams: dict[str, dict[str, float]]) -> None:
    """The cycles (Idle*, Walk*, Run*) as Godot imported them: a warning while any plays once (loop_mode 0, NONE; the
    glTF names carry no loop suffix), naming the open cycles whose loop is one frame longer than their keys."""
    from . import _frames

    cycles = sorted(n for n in anims if _frames.is_loop(_frames.label(n)))
    once = [_frames.label(n) for n in cycles if not anims[n].get("loop_mode", 0)]
    open_cycles = [_frames.label(n) for n in cycles if _frames.is_open(seams.get(n))]
    detail = (f"{len(once)} of {len(cycles)} cycles import as loop_mode NONE ({', '.join(once)}): the game sets their loop "
              f"mode at import" if once else f"all {len(cycles)} cycles loop")
    if open_cycles:
        detail += f"; open cycles, one frame longer than their keys: {', '.join(open_cycles)}"
    c.add("loop_modes", not once, detail, "warn")


def _body_feet(dump: dict[str, Any], bones: list[str]) -> dict[str, list[float]] | None:
    """A barefoot character's feet: the bounds of the skin whose heaviest bone is a Foot or Toe bone, over every part
    but the eyes (inspect.gd's bone_bounds); None when no part has skin on those bones."""
    boxes = [m["bone_bounds"][b] for m in dump["meshes"] if not m["name"].endswith("_eyes")
             for b in bones if (m.get("bone_bounds") or {}).get(b)]
    if not boxes:
        return None
    return {"min": [min(b["min"][i] for b in boxes) for i in range(3)],
            "max": [max(b["max"][i] for b in boxes) for i in range(3)]}


def _facing(c: Checks, dump: dict[str, Any], skeleton: dict[str, Any], renamed: dict[str, str]) -> None:
    """Front +Z: the eyes in front of the Head joint, the shoes reaching further forward than back from the ankles, and
    the character's left wrist at +X. Without a _shoes part (a barefoot body, art #196) the body's feet stand in: the
    skin whose heaviest bone is a Foot or Toe bone (each vertex counts for its heaviest bone only)."""
    joints = skeleton["rest_joints"]
    name = lambda bone: renamed.get(bone, bone)  # noqa: E731
    needed = [name(b) for b in ("Head", "Foot.L", "Foot.R", "Wrist.L", "Wrist.R")]
    eyes, shoes = _part(dump, "eyes"), _part(dump, "shoes")
    feet, what = (shoes["rest_bounds"], "shoes") if shoes is not None else (
        _body_feet(dump, [name(b) for b in ("Foot.L", "Foot.R", "Toe.L", "Toe.R")]), "bare feet")
    if not all(b in joints for b in needed) or eyes is None or feet is None:
        c.add("facing_plus_z", False, f"cannot tell: needs the bones {needed}, an _eyes part, and a _shoes part or "
              f"skin on the foot and toe bones")
        return
    head, foot_l, foot_r, wrist_l, wrist_r = (joints[b] for b in needed)
    ahead = _centre(eyes["rest_bounds"])[2] - head[2]
    foot_z = (foot_l[2] + foot_r[2]) / 2
    toes = feet["max"][2] - foot_z
    heels = foot_z - feet["min"][2]
    left = wrist_l[0] - wrist_r[0]
    good = ahead >= FACE_AHEAD_M and toes > heels and left > 0
    c.add("facing_plus_z", good, f"eyes {ahead * 100:+.1f} cm ahead of the Head joint, {what} reach {toes * 100:.1f} cm "
          f"forward and {heels * 100:.1f} cm back from the ankles, left wrist at {'+X' if left > 0 else '-X'}")


def load_contract() -> dict[str, Any]:
    return _contract.load_contract()
