"""The face kit's data (docs/faces.md), in pure Python so that the runner checks it before Blender starts and Blender
loads it with the same code:

- faces/styles.json: the style families (one design language each for eyes, brows and mouths) and the shared
  expressions, which a family may override;
- faces/review.json: what the review sheets show (the heads recipe, skin tones, per-head colours, the game's camera
  read from the game repo, the distances, the frame strip).

load_styles() and load_review() report every problem at once, each naming what is allowed.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

# Mirrors of tools/blender/um/facekit.py (which needs bpy); faces_render.py asserts that they agree.
EYE_KINDS = ("dot", "ball", "toon", "almond", "painted")
EYE_SHAPES = ("ellipse", "almond")
CLOSED_STYLES = ("lid", "arc")
HAPPY_STYLES = ("lid", "arc")
LIP_STYLES = ("none", "rim", "full")
FAMILY_COLORS = ("white", "pupil", "highlight", "lash", "line", "dark", "teeth", "tongue", "dot")

PARTS = ("eyes", "brows", "mouth")
# The expressions the game needs (art #21): every family has all of them.
REQUIRED_EXPRESSIONS = ("neutral", "happy", "talk_a", "surprised", "angry", "closed")
# What an expression may set per part; eyes and brows also take key_l / key_r for one side.
EXPRESSION_KEYS = {
    "eyes": {"open": "number", "lower": "number", "tilt": "number", "scale": "number", "pupil": "number", "look": "pair"},
    "brows": {"raise": "number", "inner": "number", "arch": "number"},
    "mouth": {"w": "number", "mid": "number", "corner": "number", "side": "number", "gap": "number", "skew": "number",
              "round": "number", "shift": "number", "teeth": "bool"},
}
SIDED = ("eyes", "brows")

EYE_REQUIRED = {"kind": "choice", "shape": "choice", "w": "length", "h": "length"}
EYE_OPTIONAL = {
    "depth": "length", "protrude": "length", "top": "number", "bottom": "number", "slant": "number",
    "top_pow": "number", "bottom_pow": "number", "rest_open": "number", "lid_scale": "number", "iris": "length",
    "pupil": "length", "iris_v": "number", "highlights": "highlights", "lash": "length", "lash_grow": "number",
    "flick": "length", "flick_rise": "number", "flick_lift": "length", "closed": "choice", "happy": "choice",
    "arc": "length", "arc_lift": "length", "lift": "length", "dx": "number", "dz": "number", "cols": "count",
}
BROW_KEYS = {"pts": "points", "w": "lengths", "thick": "length", "lift": "length", "cols": "count"}
MOUTH_REQUIRED = {"w": "length", "lips": "choice"}
MOUTH_OPTIONAL = {"line": "length", "rim": "length", "lip_up": "length", "lip_lo": "length", "teeth": "length",
                  "tongue": "bool", "corner": "number", "lift": "length", "dz": "number", "line_color": "choice",
                  "cols": "count"}
FAMILY_KEYS = ("name", "summary", "eyes", "brows", "mouth", "lip_tint", "colors", "expressions")
FAMILY_ID_RE = re.compile(r"^f[0-9]+_[a-z0-9_]+$")
CHOICES = {"kind": EYE_KINDS, "shape": EYE_SHAPES, "closed": CLOSED_STYLES, "happy": HAPPY_STYLES, "lips": LIP_STYLES,
           "line_color": ("line", "dark", "lip")}
# Sizes are metres: a face part beyond 10 cm is a typo.
MAX_LENGTH_M = 0.1

REVIEW_KEYS = ("description", "heads_recipe", "heads", "skins", "overview_skins", "game_camera", "distances_m",
               "distance_sheet", "strip")
SHEETS = ("close", "distance", "overview", "strip")


class StylesError(Exception):
    def __init__(self, source: str, problems: list[str]):
        self.problems = problems
        lines = "\n".join(f"  - {p}" for p in problems)
        super().__init__(f"{source}: {len(problems)} problem(s)\n{lines}")


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _rgb_ok(v: Any) -> bool:
    return isinstance(v, list) and len(v) == 3 and all(_is_number(x) and 0.0 <= x <= 1.0 for x in v)


def _check_value(where: str, key: str, kind: str, v: Any, problems: list[str]) -> None:
    bad = None
    if kind == "number" and not _is_number(v):
        bad = "a number"
    elif kind == "length" and not (_is_number(v) and 0.0 <= v <= MAX_LENGTH_M):
        bad = f"a length in metres from 0 to {MAX_LENGTH_M}"
    elif kind == "count" and not (isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 64):
        bad = "a whole number from 1 to 64"
    elif kind == "bool" and not isinstance(v, bool):
        bad = "true or false"
    elif kind == "pair" and not (isinstance(v, list) and len(v) == 2 and all(_is_number(x) for x in v)):
        bad = "[x, y]"
    elif kind == "choice" and v not in CHOICES[key]:
        bad = "one of " + ", ".join(CHOICES[key])
    elif kind == "highlights" and not (isinstance(v, list) and all(
            isinstance(h, list) and len(h) == 3 and all(_is_number(x) for x in h) and 0 < h[2] <= MAX_LENGTH_M for h in v)):
        bad = "a list of [dx, dz, radius_m]"
    elif kind == "points" and not (isinstance(v, list) and len(v) >= 2 and all(
            isinstance(p, list) and len(p) == 2 and all(_is_number(x) and abs(x) <= MAX_LENGTH_M for x in p) for p in v)):
        bad = "a list of at least two [x, z] points in metres"
    elif kind == "lengths" and not (isinstance(v, list) and v and all(_is_number(x) and 0 < x <= MAX_LENGTH_M for x in v)):
        bad = "a list of half-widths in metres"
    if bad:
        problems.append(f"{where}.{key}: {v!r} is not {bad}")


def _check_part(where: str, spec: Any, required: dict, optional: dict, problems: list[str]) -> None:
    if not isinstance(spec, dict):
        problems.append(f"{where}: must be an object")
        return
    for key, kind in required.items():
        if key not in spec:
            problems.append(f"{where}: missing {key}")
        else:
            _check_value(where, key, kind, spec[key], problems)
    for key, v in spec.items():
        if key in required:
            continue
        if key not in optional:
            problems.append(f"{where}: unknown key {key!r}; known: {', '.join(sorted({**required, **optional}))}")
        else:
            _check_value(where, key, optional[key], v, problems)


def _check_eyes(where: str, e: dict, problems: list[str]) -> None:
    _check_part(where, e, EYE_REQUIRED, EYE_OPTIONAL, problems)
    if not isinstance(e, dict):
        return
    if e.get("kind") != "painted":
        for key in ("depth", "protrude"):
            if key not in e:
                problems.append(f"{where}: a {e.get('kind')} eye needs {key} (only painted eyes are flat)")
    if e.get("shape") == "almond":
        for key in ("top", "bottom"):
            if key not in e:
                problems.append(f"{where}: an almond shape needs {key}")
    if e.get("kind") in ("almond", "painted") and e.get("shape") != "almond":
        problems.append(f"{where}: kind {e.get('kind')} needs shape almond")
    if e.get("kind") in ("dot", "ball", "toon") and e.get("shape") != "ellipse":
        problems.append(f"{where}: kind {e.get('kind')} needs shape ellipse")


def _check_brows(where: str, b: Any, problems: list[str]) -> None:
    _check_part(where, b, {"pts": "points", "w": "lengths"}, {k: v for k, v in BROW_KEYS.items() if k not in ("pts", "w")},
                problems)
    if isinstance(b, dict) and isinstance(b.get("pts"), list) and isinstance(b.get("w"), list):
        if len(b["pts"]) != len(b["w"]):
            problems.append(f"{where}: pts has {len(b['pts'])} points but w {len(b['w'])} half-widths")
        xs = [p[0] for p in b["pts"] if isinstance(p, list) and p]
        if xs != sorted(xs) or len(set(xs)) != len(xs):
            problems.append(f"{where}.pts: x must grow from the inner end to the outer end")


def _check_mouth(where: str, m: Any, problems: list[str]) -> None:
    _check_part(where, m, MOUTH_REQUIRED, MOUTH_OPTIONAL, problems)
    if not isinstance(m, dict):
        return
    if m.get("lips") == "full":
        for key in ("lip_up", "lip_lo"):
            if key not in m:
                problems.append(f"{where}: full lips need {key}")
    if m.get("lips") == "rim" and "rim" not in m:
        problems.append(f"{where}: lips rim needs rim")


def _check_expression(where: str, ex: Any, problems: list[str]) -> None:
    if not isinstance(ex, dict):
        problems.append(f"{where}: must be an object of parts")
        return
    for part, values in ex.items():
        if part not in EXPRESSION_KEYS:
            problems.append(f"{where}: unknown part {part!r}; known: {', '.join(PARTS)}")
            continue
        if not isinstance(values, dict):
            problems.append(f"{where}.{part}: must be an object")
            continue
        for key, v in values.items():
            base = key[:-2] if part in SIDED and key.endswith(("_l", "_r")) else key
            if base not in EXPRESSION_KEYS[part]:
                problems.append(f"{where}.{part}: unknown key {key!r}; known: {', '.join(EXPRESSION_KEYS[part])}"
                                + (" (with _l or _r for one side)" if part in SIDED else ""))
                continue
            _check_value(f"{where}.{part}", key, EXPRESSION_KEYS[part][base], v, problems)


def merge_expression(base: dict, override: dict) -> dict:
    """The shared expression with a family's override merged in, part by part and key by key."""
    out = copy.deepcopy(base)
    for part, values in override.items():
        out.setdefault(part, {}).update(copy.deepcopy(values))
    return out


def check_styles(data: Any, source: str = "styles") -> dict[str, Any]:
    """The styles with every family's expressions merged ({"expressions": [names], "families": {id: family}}, each
    family with "expressions" = {name: merged}); raises StylesError with every problem."""
    problems: list[str] = []
    if not isinstance(data, dict):
        raise StylesError(source, ["the file must be a JSON object with expressions and families"])
    for key in data:
        if key not in ("description", "expressions", "families"):
            problems.append(f"unknown top-level key {key!r}; known: description, expressions, families")
    library = data.get("expressions")
    if not isinstance(library, dict) or not library:
        problems.append("expressions: must be an object of named expressions")
        library = {}
    for name in REQUIRED_EXPRESSIONS:
        if name not in library:
            problems.append(f"expressions: missing {name!r}; the game needs {', '.join(REQUIRED_EXPRESSIONS)}")
    for name, ex in library.items():
        _check_expression(f"expressions.{name}", ex, problems)
    families = data.get("families")
    if not isinstance(families, dict) or not families:
        problems.append("families: must be an object of style families")
        families = {}
    out: dict[str, Any] = {"expressions": list(library), "families": {}}
    for fid, fam in families.items():
        where = f"families.{fid}"
        if not FAMILY_ID_RE.match(fid):
            problems.append(f"{where}: an id is f<number>_<name> in lowercase (f3_almond)")
        if not isinstance(fam, dict):
            problems.append(f"{where}: must be an object")
            continue
        for key in fam:
            if key not in FAMILY_KEYS:
                problems.append(f"{where}: unknown key {key!r}; known: {', '.join(FAMILY_KEYS)}")
        for key in ("name", "summary"):
            if not isinstance(fam.get(key), str) or not fam.get(key):
                problems.append(f"{where}.{key}: must be a non-empty text")
        _check_eyes(f"{where}.eyes", fam.get("eyes"), problems)
        _check_brows(f"{where}.brows", fam.get("brows"), problems)
        _check_mouth(f"{where}.mouth", fam.get("mouth"), problems)
        if not _rgb_ok(fam.get("lip_tint")):
            problems.append(f"{where}.lip_tint: must be [r, g, b] from 0 to 1 (the lip colour is the skin times this)")
        colors = fam.get("colors")
        if not isinstance(colors, dict):
            problems.append(f"{where}.colors: must be an object with {', '.join(FAMILY_COLORS)}")
            colors = {}
        for name in FAMILY_COLORS:
            if name not in colors:
                problems.append(f"{where}.colors: missing {name}")
            elif not _rgb_ok(colors[name]):
                problems.append(f"{where}.colors.{name}: must be [r, g, b] from 0 to 1 (linear)")
        for name in colors:
            if name not in FAMILY_COLORS:
                problems.append(f"{where}.colors: unknown colour {name!r}; known: {', '.join(FAMILY_COLORS)}")
        overrides = fam.get("expressions", {})
        if not isinstance(overrides, dict):
            problems.append(f"{where}.expressions: must be an object")
            overrides = {}
        for name, ex in overrides.items():
            if name not in library:
                problems.append(f"{where}.expressions: {name!r} is not a shared expression; known: {', '.join(library)}")
            _check_expression(f"{where}.expressions.{name}", ex, problems)
        if isinstance(fam.get("mouth"), dict) and fam["mouth"].get("line_color") == "lip" and fam["mouth"].get("lips") == "none":
            problems.append(f"{where}.mouth: line_color lip needs lips rim or full")
        merged = copy.deepcopy(fam)
        merged["expressions"] = {name: merge_expression(ex if isinstance(ex, dict) else {}, overrides.get(name, {})
                                                        if isinstance(overrides.get(name, {}), dict) else {})
                                 for name, ex in library.items()}
        out["families"][fid] = merged
    if problems:
        raise StylesError(source, problems)
    return out


def load_styles(path: Path) -> dict[str, Any]:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise StylesError(str(path), [f"cannot read: {exc}"]) from exc
    except json.JSONDecodeError as exc:
        raise StylesError(str(path), [f"not valid JSON: {exc}"]) from exc
    return check_styles(data, path.name)


def lip_rgb(skin: list[float], tint: list[float]) -> list[float]:
    """The lip colour of a family on a skin tone: the skin times the family's tint."""
    return [round(s * t, 4) for s, t in zip(skin, tint)]


def pixels_per_metre(game_camera: dict[str, Any], distance_m: float) -> float:
    """How many screen pixels one metre covers at distance_m, at the centre of the game's view (a vertical FOV kept
    for the height, the window height in pixels)."""
    import math

    return game_camera["height"] / (2.0 * distance_m * math.tan(math.radians(game_camera["fov_deg"]) / 2.0))


def check_review(data: Any, styles: dict[str, Any] | None = None, source: str = "review") -> dict[str, Any]:
    """The review settings, checked (heads, skins, camera, distances, strip); raises StylesError."""
    problems: list[str] = []
    if not isinstance(data, dict):
        raise StylesError(source, ["the file must be a JSON object"])
    for key in data:
        if key not in REVIEW_KEYS:
            problems.append(f"unknown key {key!r}; known: {', '.join(REVIEW_KEYS)}")
    if not isinstance(data.get("heads_recipe"), str):
        problems.append("heads_recipe: must name the heads recipe (an assembler recipe next to this file)")
    heads = data.get("heads")
    if not isinstance(heads, dict) or not heads:
        problems.append("heads: must be an object {id: {label, iris, brow}}")
        heads = {}
    for hid, h in heads.items():
        if not isinstance(h, dict):
            problems.append(f"heads.{hid}: must be an object")
            continue
        if not isinstance(h.get("label"), str):
            problems.append(f"heads.{hid}.label: must be a text")
        for key in ("iris", "brow"):
            if not _rgb_ok(h.get(key)):
                problems.append(f"heads.{hid}.{key}: must be [r, g, b] from 0 to 1")
    skins = data.get("skins")
    if not isinstance(skins, dict) or not skins:
        problems.append("skins: must be an object {name: [r, g, b]}")
        skins = {}
    for name, rgb in skins.items():
        if not _rgb_ok(rgb):
            problems.append(f"skins.{name}: must be [r, g, b] from 0 to 1")
    for hid, skin in (data.get("overview_skins") or {}).items():
        if hid not in heads:
            problems.append(f"overview_skins: unknown head {hid!r}; heads: {', '.join(heads)}")
        if skin not in skins:
            problems.append(f"overview_skins.{hid}: unknown skin {skin!r}; skins: {', '.join(skins)}")
    cam = data.get("game_camera")
    if not isinstance(cam, dict):
        problems.append("game_camera: must be an object with fov_deg, width, height, eye_height_m")
    else:
        for key in ("fov_deg", "width", "height", "eye_height_m"):
            if not _is_number(cam.get(key)) or cam.get(key) <= 0:
                problems.append(f"game_camera.{key}: must be a positive number")
    dists = data.get("distances_m")
    if not (isinstance(dists, list) and dists and all(_is_number(d) and 0.5 <= d <= 100 for d in dists)):
        problems.append("distances_m: must be a list of distances from 0.5 to 100 m")
    expr_names = set(styles["expressions"]) if styles else None
    ds = data.get("distance_sheet")
    if not isinstance(ds, dict):
        problems.append("distance_sheet: must be an object with heads [[head, skin], ...] and expressions")
    else:
        for pair in ds.get("heads", []):
            if not (isinstance(pair, list) and len(pair) == 2 and pair[0] in heads and pair[1] in skins):
                problems.append(f"distance_sheet.heads: {pair!r} is not [head, skin] of heads and skins")
        for name in ds.get("expressions", []):
            if expr_names is not None and name not in expr_names:
                problems.append(f"distance_sheet.expressions: unknown {name!r}; known: {', '.join(sorted(expr_names))}")
    strip = data.get("strip")
    if not isinstance(strip, dict):
        problems.append("strip: must be an object with action, frames and rows [[head, skin, family], ...]")
    else:
        if not isinstance(strip.get("action"), str):
            problems.append("strip.action: must name a pack action (Walk, Idle)")
        if not (isinstance(strip.get("frames"), int) and 2 <= strip["frames"] <= 24):
            problems.append("strip.frames: must be a whole number from 2 to 24")
        for row in strip.get("rows", []):
            ok = isinstance(row, list) and len(row) == 3 and row[0] in heads and row[1] in skins
            if ok and styles is not None:
                ok = row[2] in styles["families"]
            if not ok:
                problems.append(f"strip.rows: {row!r} is not [head, skin, family]")
    if problems:
        raise StylesError(source, problems)
    return data


def load_review(path: Path, styles: dict[str, Any] | None = None) -> dict[str, Any]:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise StylesError(str(path), [f"cannot read: {exc}"]) from exc
    except json.JSONDecodeError as exc:
        raise StylesError(str(path), [f"not valid JSON: {exc}"]) from exc
    return check_review(data, styles, path.name)
