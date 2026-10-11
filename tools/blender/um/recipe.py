"""Recipes: characters as data (docs/assembly.md). Pure Python, so the runner validates a recipe before Blender starts
and Blender loads it with the same code.

load(path, raw_dir) reads a recipe JSON file, resolves "extends", checks its structure and, when the raw folder is
given, every pack folder, file, object, material and action it names against the packs themselves. Every problem is
reported at once, each naming what exists instead.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

from . import claylook, glb, zones
from .clayface import kit as claykit

GENDERS = ("M", "W")
PACK_LABEL = {"M": "Men", "W": "Women"}
# Pack parts and the slot each fills; the scripted face parts are added by build_character.
PACK_PARTS = ("head", "hair", "top", "bottom", "shoes")
FACE_PARTS = ("eyes", "brows", "mouth")
FINGER_JOINTS = {"Thumb": 3, "Index": 4, "Middle": 4, "Ring": 4, "Pinky": 4}
VIEWS = ("front", "34", "side", "back", "in34")
CATALOGUE = Path(__file__).resolve().parents[3] / "catalogue" / "ultimate_modular.json"
EXTRA_KINDS_NOT = ("skull", "hair", "brows")  # catalogue kinds that are never an extra
MODES = ("chars", "face", "hands", "lineup", "crossgender", "qa", "ankles")
DEFAULT_MODES = ("chars", "face", "hands", "lineup", "crossgender")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_]*$")

TOP_REQUIRED = ("packs", "skeleton", "head_bone_rest", "face", "characters")
TOP_OPTIONAL = ("description", "face_shading", "hands", "crossgender", "modes", "look", "clay")
CHAR_REQUIRED = ("id", "gender", "head", "hair", "top", "bottom", "shoes", "eyes", "brows", "mouth", "pose")
CHAR_OPTIONAL = ("skin", "extras", "recolor", "extend", "notes", "face_kit")


class RecipeError(Exception):
    def __init__(self, source: str, problems: list[str]):
        self.problems = problems
        lines = "\n".join(f"  - {p}" for p in problems)
        super().__init__(f"recipe {source}: {len(problems)} problem(s)\n{lines}")


# ---------------------------------------------------------------------------------------------------- reading
def read(path: Path, _seen: tuple[Path, ...] = ()) -> dict[str, Any]:
    """The recipe at path with "extends" resolved: a variant names a base recipe file (relative to its own folder),
    overrides its top-level keys and merges "every_character" into each character (key by key)."""
    path = Path(path).resolve()
    if path in _seen:
        raise RecipeError(str(path), ["extends loops back to " + path.name])
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RecipeError(str(path), [f"cannot read: {exc}"]) from exc
    except json.JSONDecodeError as exc:
        raise RecipeError(str(path), [f"not valid JSON: {exc}"]) from exc
    if not isinstance(data, dict):
        raise RecipeError(str(path), ["the recipe must be a JSON object"])
    if "extends" not in data:
        if "every_character" in data:
            raise RecipeError(str(path), ["every_character needs extends (it changes a base recipe's characters)"])
        return data
    base_file = data["extends"]
    if not isinstance(base_file, str) or not base_file:
        raise RecipeError(str(path), ["extends must name a recipe file next to this one"])
    merged = copy.deepcopy(read(path.parent / base_file, _seen + (path,)))
    every = data.get("every_character", {})
    if not isinstance(every, dict):
        raise RecipeError(str(path), ["every_character must be an object of character keys"])
    for key, value in data.items():
        if key not in ("extends", "every_character"):
            merged[key] = copy.deepcopy(value)
    for char in merged.get("characters", []):
        if isinstance(char, dict):
            char.update(copy.deepcopy(every))
    return merged


def load(path: Path, raw_dir: Path | None = None) -> dict[str, Any]:
    """The checked recipe; raises RecipeError with every problem. raw_dir None checks the structure only."""
    path = Path(path).resolve()
    data = read(path)
    problems = check_structure(data)
    if not problems and raw_dir is not None:
        problems = check_contents(data, Path(raw_dir))
    if not problems and raw_dir is not None and CATALOGUE.is_file():
        cat = json.loads(CATALOGUE.read_text(encoding="utf-8"))
        problems = check_extras(data, cat) + check_heads(data, cat)
    if problems:
        raise RecipeError(path.name, problems)
    data["_name"] = path.stem
    return data


def pack_dir(recipe: dict[str, Any], raw_dir: Path, gender: str) -> Path:
    return Path(raw_dir) / recipe["packs"][gender]


def modes(recipe: dict[str, Any]) -> list[str]:
    return list(recipe.get("modes", DEFAULT_MODES))


# ---------------------------------------------------------------------------------------------------- structure
def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


class _Check:
    def __init__(self) -> None:
        self.problems: list[str] = []

    def bad(self, where: str, text: str) -> None:
        self.problems.append(f"{where}: {text}")

    def keys(self, table: Any, where: str, required: tuple[str, ...], optional: tuple[str, ...] = ()) -> bool:
        if not isinstance(table, dict):
            self.bad(where, "must be an object")
            return False
        for key in required:
            if key not in table:
                self.bad(where, f"missing key {key!r}")
        allowed = set(required) | set(optional)
        for key in table:
            if key not in allowed:
                self.bad(where, f"unknown key {key!r} (allowed: {', '.join(sorted(allowed))})")
        return True

    def text(self, value: Any, where: str) -> None:
        if not (isinstance(value, str) and value.strip()):
            self.bad(where, "must be a non-empty string")

    def names(self, value: Any, where: str, empty_ok: bool = False) -> None:
        if not (isinstance(value, list) and all(isinstance(v, str) and v for v in value) and (value or empty_ok)):
            self.bad(where, "must be a list of names" + ("" if empty_ok else " (at least one)"))

    def rgb(self, value: Any, where: str) -> None:
        if not (isinstance(value, list) and len(value) == 3 and all(_num(v) and 0.0 <= v <= 1.0 for v in value)):
            self.bad(where, "must be [r, g, b] with each value from 0 to 1")

    def colour(self, value: Any, where: str, roles: set[str]) -> None:
        """[r, g, b], or {"from_part": role, "material": name}: that part's material colour."""
        if isinstance(value, dict):
            if self.keys(value, where, ("from_part", "material")):
                if value.get("from_part") not in roles:
                    self.bad(where, f"from_part {value.get('from_part')!r} is not a pack part of this character "
                             f"({', '.join(sorted(roles))})")
                self.text(value.get("material"), where + ".material")
        else:
            self.rgb(value, where)

    def cuts(self, value: Any, where: str) -> None:
        if not isinstance(value, list) or any(z not in zones.CUT_ZONES for z in value):
            self.bad(where, f"must be a list of zone names from {', '.join(sorted(zones.CUT_ZONES))}")

    def piece_zones(self, value: Any, where: str) -> None:
        if not isinstance(value, list) or any(z not in zones.PIECE_ZONES for z in value):
            self.bad(where, f"must be a list of piece zone names from {', '.join(sorted(zones.PIECE_ZONES))}")

    def file_name(self, value: Any, where: str) -> None:
        if not (isinstance(value, str) and value.lower().endswith(".glb") and "/" not in value and "\\" not in value):
            self.bad(where, "must be a .glb file name in the pack folder")


def check_structure(data: dict[str, Any]) -> list[str]:
    c = _Check()
    if not c.keys(data, "recipe", TOP_REQUIRED, TOP_OPTIONAL):
        return c.problems
    packs = data.get("packs")
    if c.keys(packs, "packs", GENDERS):
        for g in GENDERS:
            p = packs.get(g)
            pure = PurePosixPath(p) if isinstance(p, str) else None
            if pure is None or not p or "\\" in p or ":" in p or pure.is_absolute() or ".." in pure.parts:
                c.bad(f"packs.{g}", "must be a folder relative to the raw folder, with / separators")
    if c.keys(data.get("skeleton"), "skeleton", GENDERS):
        for g in GENDERS:
            c.file_name(data["skeleton"].get(g), f"skeleton.{g}")
    hb = data.get("head_bone_rest")
    if not (isinstance(hb, list) and len(hb) == 3 and all(_num(v) for v in hb)):
        c.bad("head_bone_rest", "must be [x, y, z] in metres")
    for problem in claylook.check(data):
        c.problems.append(problem)
    if data.get("face_shading", "smooth") not in ("smooth", "flat"):
        c.bad("face_shading", "must be smooth or flat")
    if c.keys(data.get("face"), "face", GENDERS):
        for g in GENDERS:
            if c.keys(data["face"].get(g), f"face.{g}", ("mouth_dz",)) and not _num(data["face"][g].get("mouth_dz")):
                c.bad(f"face.{g}.mouth_dz", "must be a number (metres from the eye centres)")
    if "modes" in data and not (isinstance(data["modes"], list) and all(m in MODES for m in data["modes"])):
        c.bad("modes", f"must be a list from {', '.join(MODES)}")
    if "description" in data:
        c.text(data["description"], "description")

    chars = data.get("characters")
    ids: list[str] = []
    if not (isinstance(chars, list) and chars):
        c.bad("characters", "must be a list of at least one character")
        chars = []
    for i, ch in enumerate(chars):
        cid = ch.get("id") if isinstance(ch, dict) else None
        where = f"characters[{cid if isinstance(cid, str) else i}]"
        if not c.keys(ch, where, CHAR_REQUIRED, CHAR_OPTIONAL):
            continue
        if not (isinstance(cid, str) and ID_RE.fullmatch(cid)):
            c.bad(where + ".id", "must be lowercase letters, digits and underscores")
        elif cid in ids:
            c.bad(where + ".id", "is used twice")
        else:
            ids.append(cid)
        _check_character(c, ch, where)

    for i, hs in enumerate(data.get("hands", []) if isinstance(data.get("hands", []), list) else [None]):
        where = f"hands[{i}]"
        if not c.keys(hs, where, ("id", "shots")):
            continue
        if hs.get("id") not in ids:
            c.bad(where + ".id", f"{hs.get('id')!r} is not a character of this recipe ({', '.join(ids)})")
        shots = hs.get("shots")
        if not (isinstance(shots, list) and shots):
            c.bad(where + ".shots", "must be a list of [side, view] or [side, view, tilt]")
            continue
        for k, shot in enumerate(shots):
            ok = isinstance(shot, list) and len(shot) in (2, 3) and shot[0] in ("L", "R") and shot[1] in VIEWS
            if not ok or (len(shot) == 3 and not _num(shot[2])):
                c.bad(f"{where}.shots[{k}]", f"must be [L|R, {'|'.join(VIEWS)}] or with a camera pitch in degrees")

    for i, cg in enumerate(data.get("crossgender", []) if isinstance(data.get("crossgender", []), list) else [None]):
        where = f"crossgender[{i}]"
        if not c.keys(cg, where, ("id", "label", "gender", "base_file", "replace", "pose")):
            continue
        c.text(cg.get("id"), where + ".id")
        c.text(cg.get("label"), where + ".label")
        if cg.get("gender") not in GENDERS:
            c.bad(where + ".gender", "must be M or W")
        c.file_name(cg.get("base_file"), where + ".base_file")
        rp = cg.get("replace")
        if c.keys(rp, where + ".replace", ("role", "remove", "gender", "file", "object")):
            if rp.get("role") not in ("head", "top", "bottom", "shoes"):
                c.bad(where + ".replace.role", "must be head, top, bottom or shoes")
            if rp.get("gender") not in GENDERS:
                c.bad(where + ".replace.gender", "must be M or W")
            c.file_name(rp.get("file"), where + ".replace.file")
            c.text(rp.get("remove"), where + ".replace.remove")
            c.text(rp.get("object"), where + ".replace.object")
        _check_pose(c, cg.get("pose"), where + ".pose", neutral_ok=False)
    return c.problems


def _check_part(c: _Check, spec: Any, where: str, required: tuple[str, ...], optional: tuple[str, ...]) -> bool:
    if not c.keys(spec, where, required, optional):
        return False
    c.file_name(spec.get("file"), where + ".file")
    c.text(spec.get("object"), where + ".object")
    return True


def _check_character(c: _Check, ch: dict[str, Any], where: str) -> None:
    if ch.get("gender") not in GENDERS:
        c.bad(where + ".gender", "must be M or W")
    if ch.get("skin") is not None:
        c.rgb(ch.get("skin"), where + ".skin")
    head = ch.get("head")
    if _check_part(c, head, where + ".head", ("file", "object", "keep", "eye_materials"),
                   ("as_skin", "straighten", "tuck_ears", "cut")):  # fmt: skip
        c.names(head.get("keep"), where + ".head.keep")
        c.names(head.get("eye_materials"), where + ".head.eye_materials")
        for key in ("as_skin", "straighten"):
            if key in head:
                c.names(head[key], f"{where}.head.{key}")
        if "tuck_ears" in head and not (_num(head["tuck_ears"]) and 0.05 < head["tuck_ears"] < 0.12):
            c.bad(where + ".head.tuck_ears", "must be the skull half-width in metres (0.05 to 0.12)")
        if "cut" in head:
            c.cuts(head["cut"], where + ".head.cut")
    roles = ["head", "hair", "top", "bottom", "shoes"]
    extras = ch.get("extras", [])
    if not isinstance(extras, list):
        c.bad(where + ".extras", "must be a list")
        extras = []
    for k, spec in enumerate([("hair", ch.get("hair"))] + [(None, e) for e in extras]):
        role, part = spec
        w = where + (".hair" if role else f".extras[{k - 1}]")
        required = ("file", "object", "materials") + (() if role else ("role",))
        if not _check_part(c, part, w, required, ("cut", "drop_pieces", "inflate") + (() if role else ("gender",))):
            continue
        if "gender" in part and part["gender"] not in GENDERS:
            c.bad(w + ".gender", "must be M or W (the pack a head item comes from; default the character's)")
        c.names(part.get("materials"), w + ".materials")
        if "cut" in part:
            c.cuts(part["cut"], w + ".cut")
        if "drop_pieces" in part:
            c.piece_zones(part["drop_pieces"], w + ".drop_pieces")
        if "inflate" in part and not (_num(part["inflate"]) and 0.0 <= part["inflate"] < 0.05):
            c.bad(w + ".inflate", "must be a small scale offset (0 to 0.05)")
        if not role:
            r = part.get("role")
            if not (isinstance(r, str) and ID_RE.fullmatch(r)) or r in PACK_PARTS + FACE_PARTS or r in roles:
                c.bad(w + ".role", f"{r!r} must be a new lowercase name, not a slot or a used role")
            else:
                roles.append(r)
    for slot in ("top", "bottom", "shoes"):
        _check_part(c, ch.get(slot), f"{where}.{slot}", ("file", "object"), ())
    role_set = set(roles)
    eyes = ch.get("eyes")
    if c.keys(eyes, where + ".eyes", ("style",), ("iris", "lash")):
        c.text(eyes.get("style"), where + ".eyes.style")
        for key in ("iris", "lash"):
            if key in eyes:
                c.rgb(eyes[key], f"{where}.eyes.{key}")
    brows = ch.get("brows")
    if c.keys(brows, where + ".brows", ("style", "rgb")):
        c.text(brows.get("style"), where + ".brows.style")
        c.colour(brows.get("rgb"), where + ".brows.rgb", role_set)
    mouth = ch.get("mouth")
    if c.keys(mouth, where + ".mouth", ("style",), ("lip", "dz")):
        c.text(mouth.get("style"), where + ".mouth.style")
        if "lip" in mouth:
            c.rgb(mouth["lip"], where + ".mouth.lip")
        if "dz" in mouth and not _num(mouth["dz"]):
            c.bad(where + ".mouth.dz", "must be a number (metres from the eye centres)")
    recolor = ch.get("recolor", [])
    for k, rc in enumerate(recolor if isinstance(recolor, list) else [None]):
        w = f"{where}.recolor[{k}]"
        if c.keys(rc, w, ("part", "material", "rgb"), ("was",)):
            if rc.get("part") not in role_set:
                c.bad(w + ".part", f"{rc.get('part')!r} is not a pack part of this character ({', '.join(roles)})")
            c.text(rc.get("material"), w + ".material")
            c.colour(rc.get("rgb"), w + ".rgb", role_set)
    extend = ch.get("extend", [])
    for k, ex in enumerate(extend if isinstance(extend, list) else [None]):
        w = f"{where}.extend[{k}]"
        if c.keys(ex, w, ("part", "drop"), ("why",)):
            if ex.get("part") not in role_set:
                c.bad(w + ".part", f"{ex.get('part')!r} is not a pack part of this character ({', '.join(roles)})")
            if not (_num(ex.get("drop")) and 0.0 < ex["drop"] < 0.1):
                c.bad(w + ".drop", "must be metres (0 to 0.1)")
    if "face_kit" in ch:  # the clay look's face (um/clayface): picks over the body type's defaults
        for problem in claykit.check_picks(ch["face_kit"], ch.get("gender"), where + ".face_kit"):
            w, _, text = problem.partition(": ")
            c.bad(w, text)
    _check_pose(c, ch.get("pose"), where + ".pose", neutral_ok=True)


def _check_pose(c: _Check, pose: Any, where: str, neutral_ok: bool) -> None:
    """{"action": name, "frame": n} or {"neutral": {"down_deg": a}}, each with an optional finger "curl"."""
    if not isinstance(pose, dict):
        c.bad(where, "must be an object")
        return
    if "neutral" in pose and neutral_ok:
        if c.keys(pose, where, ("neutral",), ("curl",)) and c.keys(pose["neutral"], where + ".neutral", (), ("down_deg",)):
            down = pose["neutral"].get("down_deg", 70.0)
            if not (_num(down) and 0.0 <= down <= 90.0):
                c.bad(where + ".neutral.down_deg", "must be degrees from 0 to 90")
    elif c.keys(pose, where, ("action", "frame"), ("curl",)):
        c.text(pose.get("action"), where + ".action")
        if not (isinstance(pose.get("frame"), int) and not isinstance(pose.get("frame"), bool) and pose["frame"] >= 0):
            c.bad(where + ".frame", "must be a whole frame number from 0")
    curl = pose.get("curl", {})
    if not isinstance(curl, dict):
        c.bad(where + ".curl", "must be an object {\"Middle.R\": [deg, deg, deg], ...}")
        return
    for key, angles in curl.items():
        finger, _, side = key.partition(".")
        joints = FINGER_JOINTS.get(finger)
        if joints is None or side not in ("L", "R"):
            c.bad(f"{where}.curl", f"{key!r} must be <finger>.<L|R> with a finger from {', '.join(FINGER_JOINTS)}")
        elif not (isinstance(angles, list) and 0 < len(angles) <= joints and all(_num(a) for a in angles)):
            c.bad(f"{where}.curl.{key}", f"must be 1 to {joints} angles in degrees (from the finger's base)")


# ---------------------------------------------------------------------------------------------------- contents
def check_extras(data: dict[str, Any], catalogue: dict[str, Any]) -> list[str]:
    """Every extra is a whole item of the parts catalogue of the character's own body type (art #42: m1's stray blue
    strip was a woman's headset): its file, object and materials equal one item's recipe (kind not skull, hair or
    brows) whose source body type is the character's. A cut the assembler cannot make yet is not compared."""
    items = catalogue.get("items", {})
    problems: list[str] = []

    def same(it: dict[str, Any], e: dict[str, Any]) -> bool:
        r = it.get("recipe", {})
        return (r.get("file"), r.get("object"), sorted(r.get("materials") or [])) == (
            e.get("file"), e.get("object"), sorted(e.get("materials") or []))

    for ch in data.get("characters", []):
        g = ch.get("gender")
        for k, e in enumerate(ch.get("extras", [])):
            w = f"characters[{ch.get('id')}].extras[{k}]"
            if e.get("gender", g) != g:
                problems.append(f"{w}.gender: {e['gender']!r} is not the character's {g!r}: an extra is an item of "
                                f"the character's own body type")
                continue
            ok = [i for i, it in sorted(items.items()) if it.get("kind") not in EXTRA_KINDS_NOT
                  and it.get("source", {}).get("body_type") == g and same(it, e)]
            if not ok:
                near = [i for i, it in sorted(items.items()) if it.get("kind") not in EXTRA_KINDS_NOT
                        and it.get("source", {}).get("body_type") == g and it.get("recipe", {}).get("file") == e.get("file")]
                problems.append(f"{w}: {e.get('object')} {e.get('materials')} is not a whole catalogue item of body type "
                                f"{g}; items of {e.get('file')}: {', '.join(near) or 'none'}")
    return problems


def check_heads(data: dict[str, Any], catalogue: dict[str, Any]) -> list[str]:
    """Every head keeps its whole skull (art #42: m4's jaw was cut off because its recipe kept the Casual head's
    "Skin" without the painted stubble "Skin_Darker", which is the skull's lower jaw): keep plus as_skin must hold
    every material of the catalogue's skull item of the same file and object and body type. A head the catalogue has
    no skull item for is not compared."""
    items = catalogue.get("items", {})
    problems: list[str] = []
    for ch in data.get("characters", []):
        h, g = ch.get("head") or {}, ch.get("gender")
        if not h:
            continue
        skulls = [(i, it) for i, it in sorted(items.items()) if it.get("kind") == "skull"
                  and it.get("source", {}).get("body_type") == g
                  and (it.get("recipe", {}).get("file"), it.get("recipe", {}).get("object")) == (h.get("file"), h.get("object"))]
        kept = set(h.get("keep") or []) | set(h.get("as_skin") or [])
        for i, it in skulls:
            missing = sorted(set(it.get("materials") or []) - kept)
            if missing:
                problems.append(f"characters[{ch.get('id')}].head: drops {', '.join(missing)} of the skull {i} "
                                f"(the skull is cut open there); add them to as_skin as {i}'s recipe does")
    return problems


def check_contents(data: dict[str, Any], raw_dir: Path) -> list[str]:
    """Every pack folder, file, object, material and action the recipe names exists; each problem names what does."""
    problems: list[str] = []
    folders: dict[str, Path] = {}
    for g in GENDERS:
        folder = pack_dir(data, raw_dir, g)
        if not folder.is_dir():
            problems.append(f"packs.{g}: no folder {folder.as_posix()} (the raw folder is {Path(raw_dir).as_posix()})")
        else:
            folders[g] = folder
    if problems:
        return problems

    def toc(where: str, g: str, file: str) -> dict | None:
        path = folders[g] / file
        if not path.is_file():
            have = sorted(p.name for p in folders[g].glob("*.glb"))
            problems.append(f"{where}: {file!r} is not in {PACK_LABEL[g]} ({data['packs'][g]}); it has: {', '.join(have)}")
            return None
        try:
            return glb.contents(path)
        except (OSError, ValueError, glb.GlbError) as exc:
            problems.append(f"{where}: cannot read {path.as_posix()}: {exc}")
            return None

    def obj(where: str, g: str, file: str, name: str) -> list[str] | None:
        t = toc(where + ".file", g, file)
        if t is None:
            return None
        if name not in t["objects"]:
            problems.append(f"{where}.object: {name!r} is not an object in {PACK_LABEL[g]}/{file}; it has: "
                            f"{', '.join(sorted(t['objects']))}")
            return None
        return t["objects"][name]

    def mats(where: str, wanted: list[str], have: list[str], what: str) -> None:
        missing = [m for m in wanted if m not in have]
        if missing:
            problems.append(f"{where}: {', '.join(repr(m) for m in missing)} not on {what}; it has: {', '.join(have)}")

    actions = {}
    for g in GENDERS:
        t = toc(f"skeleton.{g}", g, data["skeleton"][g])
        if t is not None:
            actions[g] = t["actions"]

    def action(where: str, g: str, name: str) -> None:
        if g in actions and name not in actions[g]:
            problems.append(f"{where}: {name!r} is not an action of {PACK_LABEL[g]}/{data['skeleton'][g]}; it has: "
                            f"{', '.join(actions[g])}")

    for ch in data["characters"]:
        where, g = f"characters[{ch['id']}]", ch["gender"]
        available: dict[str, list[str]] = {}
        head = ch["head"]
        hm = obj(where + ".head", g, head["file"], head["object"])
        if hm is not None:
            what = f"{head['object']} ({PACK_LABEL[g]}/{head['file']})"
            for key in ("keep", "eye_materials", "as_skin", "straighten"):
                mats(f"{where}.head.{key}", head.get(key, []), hm, what)
            available["head"] = list(head["keep"]) + list(head.get("as_skin", []))
        for spec, w in [(ch["hair"], where + ".hair")] + [(e, f"{where}.extras[{k}]") for k, e in enumerate(ch.get("extras", []))]:
            sg = spec.get("gender", g)
            m = obj(w, sg, spec["file"], spec["object"])
            if m is not None:
                mats(w + ".materials", spec["materials"], m, f"{spec['object']} ({PACK_LABEL[sg]}/{spec['file']})")
                available[spec.get("role", "hair")] = list(spec["materials"])
        for slot in ("top", "bottom", "shoes"):
            m = obj(f"{where}.{slot}", g, ch[slot]["file"], ch[slot]["object"])
            if m is not None:
                available[slot] = m
        # build_character swaps every part's Skin (and the head's as_skin) for the character's one skin material
        # before recolours and colour references are looked up: those names are gone by then.
        skinned = {role: {"Skin"} | (set(head.get("as_skin", [])) if role == "head" else set()) for role in available}

        def material_ref(w: str, role: str, name: str) -> None:
            if role not in available:
                return
            if name in skinned[role]:
                problems.append(f"{w}: {name!r} on the {role} part becomes the character's shared skin material "
                                f"({ch['id']}_skin); set the skin colour with the character's 'skin' key")
            else:
                mats(w, [name], available[role], f"the {role} part")

        colours = [(f"{where}.brows.rgb", ch["brows"]["rgb"])]
        for k, rc in enumerate(ch.get("recolor", [])):
            material_ref(f"{where}.recolor[{k}].material", rc["part"], rc["material"])
            colours.append((f"{where}.recolor[{k}].rgb", rc["rgb"]))
        for w, spec in colours:
            if isinstance(spec, dict):
                material_ref(w + ".material", spec["from_part"], spec["material"])
        if "action" in ch["pose"]:
            action(where + ".pose.action", g, ch["pose"]["action"])
    for i, cg in enumerate(data.get("crossgender", [])):
        where = f"crossgender[{i}]"
        t = toc(where + ".base_file", cg["gender"], cg["base_file"])
        if t is not None and cg["replace"]["remove"] not in t["objects"]:
            problems.append(f"{where}.replace.remove: {cg['replace']['remove']!r} is not an object in "
                            f"{PACK_LABEL[cg['gender']]}/{cg['base_file']}; it has: {', '.join(sorted(t['objects']))}")
        rp = cg["replace"]
        obj(where + ".replace", rp["gender"], rp["file"], rp["object"])
        action(where + ".pose.action", cg["gender"], cg["pose"]["action"])
    return problems
