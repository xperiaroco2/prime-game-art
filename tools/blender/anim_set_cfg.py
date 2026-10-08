"""The settings of an animation set (art #33; docs/animations.md, "Animation sets"): pure Python (no bpy), so the
runner, the unit tests and Blender's Python read and check a set the same way.

A set (tools/blender/anim_sets/<set>.toml) lists clips. Each clip has a `name` (the action and glTF animation name; a
loop ends in `_Loop`), a `source` clip key ("ual:Jog_Fwd_Loop", "tm:strafe-left", "pack:Sword_Slash"; anim_keys.py) or
`from` (an earlier clip of the set, as that clip stands after its edits), `loop`, the `edits` (steps of
anim_edit_math.OPS, run in order), `needs` (the game's needs the clip serves: the need's text and number, the layer it
plays on and the speed and rate it plays at), an optional `speed_m_s` (the ground speed of the clip at rate 1.0: what
the game divides its speed by) and `export = false` for a review candidate that is built but not written to the GLB.
"""

from __future__ import annotations

import re
import tomllib

import anim_edit_math as em
import anim_keys

FPS = 30
TOP_KEYS = {"title", "fps", "stem", "upper", "clips"}
CLIP_KEYS = {"name", "source", "from", "loop", "export", "speed_m_s", "edits", "needs", "note"}
NEED_KEYS = {"need", "no", "layer", "speed_m_s", "rate", "body", "note"}
LAYERS = ("full", "upper")
NAME = re.compile(r"[A-Za-z0-9_]+")
LOOP_SUFFIX = "_Loop"
GODOT_LOOP_WORDS = ("loop_mode", "loop", "cycle")  # tools/runner/commands/_godot.LOOP_WORDS


def godot_name(name: str) -> tuple[str, bool]:
    """The name Godot's importer gives a clip and whether it loops: _godot.godot_name for this set's names
    ([A-Za-z0-9_]+), where a trailing _loop, _cycle or _loop_mode in any case (before trailing digits) makes a loop
    and is dropped. A test keeps the two in step."""
    loops = False
    for word in GODOT_LOOP_WORDS:
        what = name.rstrip("0123456789_")
        end = name[len(what):]
        if what.lower().endswith("_" + word):
            name, loops = what[: len(what) - len(word) - 1] + end, True
    return name, loops
RATE_TOLERANCE = 0.01  # a need's speed against the clip's speed times the need's rate (relative)


def load(path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def _number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check(cfg: dict, sources: set[str] | None = None, bodies=("men", "women")) -> list[str]:
    """The errors of a set's settings, empty when it is valid. `sources` are the clip sources a `source` may name
    (None: any)."""
    errors = []
    extra = set(cfg) - TOP_KEYS
    if extra:
        errors.append(f"unknown keys {sorted(extra)} (a set takes {sorted(TOP_KEYS)})")
    if cfg.get("fps", FPS) != FPS:
        errors.append(f"fps {cfg.get('fps')}: the clip edits work at {FPS} fps")
    if not isinstance(cfg.get("stem", ""), str) or not NAME.fullmatch(cfg.get("stem", "set") or "-"):
        errors.append(f"stem {cfg.get('stem')!r} must match {NAME.pattern}")
    clips = cfg.get("clips")
    if not isinstance(clips, list) or not clips:
        return errors + ["no [[clips]]"]
    seen: list[str] = []
    godot_names: dict[str, str] = {}
    for i, c in enumerate(clips):
        where = f"clips[{i}]" + (f" ({c.get('name')})" if isinstance(c, dict) and c.get("name") else "")
        if not isinstance(c, dict):
            errors.append(f"{where}: not a table")
            continue
        unknown = set(c) - CLIP_KEYS
        if unknown:
            errors.append(f"{where}: unknown keys {sorted(unknown)}")
        name = c.get("name")
        if not isinstance(name, str) or not NAME.fullmatch(name):
            errors.append(f"{where}: name {name!r} must match {NAME.pattern}")
            continue
        if name in seen:
            errors.append(f"{where}: a second clip named {name}")
        loop = c.get("loop")
        if not isinstance(loop, bool):
            errors.append(f"{where}: loop must be true or false")
        elif loop != name.endswith(LOOP_SUFFIX):
            errors.append(f"{where}: a name ends in {LOOP_SUFFIX} exactly when the clip loops (loop = {str(loop).lower()})")
        elif godot_name(name)[1] != loop:
            errors.append(f"{where}: Godot would {'not ' if loop else ''}loop {name} (a _loop or _cycle ending in any "
                          f"case loops it)")
        gname = godot_name(name)[0]
        if gname in godot_names and godot_names[gname] != name:
            errors.append(f"{where}: Godot would name it {gname}, as it names {godot_names[gname]}")
        godot_names.setdefault(gname, name)
        if ("source" in c) == ("from" in c):
            errors.append(f"{where}: give source (a clip key) or from (an earlier clip), one of them")
        elif "source" in c:
            errors += _check_source(where, c["source"], sources)
        elif c["from"] not in seen:
            errors.append(f"{where}: from = {c['from']!r} names no earlier clip")
        if not isinstance(c.get("export", True), bool):
            errors.append(f"{where}: export must be true or false")
        speed = c.get("speed_m_s")
        if speed is not None and (not _number(speed) or speed < 0):
            errors.append(f"{where}: speed_m_s must be a number >= 0")
        edits = c.get("edits", [])
        if not isinstance(edits, list):
            errors.append(f"{where}: edits must be a list of steps")
        else:
            errors += [f"{where}: {e}" for e in em.check_steps(edits, bodies)]
            errors += [f"{where}: from_clip = {n!r} names no earlier clip" for n in em.from_clips(edits)
                       if n not in seen]
        errors += _check_needs(where, c.get("needs", []), speed if _number(speed) else None, bodies)
        seen.append(name)
    return errors


def _check_source(where: str, key, sources) -> list[str]:
    if not isinstance(key, str):
        return [f"{where}: source must be a clip key"]
    try:
        src, _ = anim_keys.split(key)
    except ValueError as e:
        return [f"{where}: {e}"]
    if src in ("blend", "layer"):
        return [f"{where}: source {key!r} is not one clip (a blend or a layer)"]
    if sources is not None and anim_keys.base_source(src) not in sources:
        return [f"{where}: source {key!r}: no source {src!r} (known: {', '.join(sorted(sources))})"]
    return []


def _check_needs(where: str, needs, speed, bodies) -> list[str]:
    if not isinstance(needs, list):
        return [f"{where}: needs must be a list"]
    errors = []
    for k, n in enumerate(needs):
        at = f"{where}: needs[{k}]"
        if not isinstance(n, dict):
            errors.append(f"{at}: not a table")
            continue
        if set(n) - NEED_KEYS:
            errors.append(f"{at}: unknown keys {sorted(set(n) - NEED_KEYS)}")
        if not isinstance(n.get("need"), str) or not n["need"].strip():
            errors.append(f"{at}: need (the game's need, as text) is missing")
        if n.get("layer", "full") not in LAYERS:
            errors.append(f"{at}: layer {n.get('layer')!r} is not one of {', '.join(LAYERS)}")
        rate = n.get("rate", 1.0)
        if not _number(rate) or rate <= 0:
            errors.append(f"{at}: rate must be a number > 0")
            rate = None
        nspeed = n.get("speed_m_s")
        if nspeed is not None and (not _number(nspeed) or nspeed < 0):
            errors.append(f"{at}: speed_m_s must be a number >= 0")
            nspeed = None
        if n.get("body", bodies[0]) not in bodies:
            errors.append(f"{at}: body {n.get('body')!r} is not one of {', '.join(bodies)}")
        if "no" in n and not (isinstance(n["no"], int) and not isinstance(n["no"], bool) and n["no"] > 0):
            errors.append(f"{at}: no (the need's number in the list) must be a whole number > 0")
        if speed and nspeed and rate and abs(nspeed - speed * rate) > RATE_TOLERANCE * nspeed:
            errors.append(f"{at}: {nspeed} m/s is not the clip's {speed} m/s at rate {rate} ({speed * rate:.3f})")
    return errors


def clips(cfg: dict) -> dict[str, dict]:
    """The set's clips by name, in settings order, with their defaults (export true, edits and needs empty)."""
    return {c["name"]: {"export": True, "edits": [], "needs": [], **c} for c in cfg["clips"]}


def closure(cfg: dict, names) -> list[str]:
    """The clips needed to build `names` ("all" or None: every clip): each with the earlier clips it is made `from`
    or its edits read (`from_clip`, art #49), in settings order; raises ValueError on an unknown name."""
    table = clips(cfg)
    if names in (None, "all"):
        return list(table)
    unknown = [n for n in names if n not in table]
    if unknown:
        raise ValueError(f"no clips {unknown} in the set; known: {', '.join(table)}")
    need = set()
    stack = list(names)
    while stack:
        n = stack.pop()
        if n in need:
            continue
        need.add(n)
        if "from" in table[n]:
            stack.append(table[n]["from"])
        stack.extend(em.from_clips(table[n]["edits"]))
    return [n for n in table if n in need]


def exported(cfg: dict) -> list[str]:
    """The clips the set writes to its GLB."""
    return [n for n, c in clips(cfg).items() if c["export"]]


def sources(cfg: dict, names=None) -> list[str]:
    """The source clip keys the clips `names` (and the clips they are made from) start from, without repeats."""
    table = clips(cfg)
    return list(dict.fromkeys(table[n]["source"] for n in closure(cfg, names) if "source" in table[n]))


def speed_of(clip: dict) -> float | None:
    """A clip's ground speed at rate 1.0 (m/s): its speed_m_s, else its first need's speed over that need's rate."""
    if clip.get("speed_m_s") is not None:
        return float(clip["speed_m_s"])
    for n in clip.get("needs", []):
        if n.get("speed_m_s"):
            return float(n["speed_m_s"]) / float(n.get("rate", 1.0))
    return None
