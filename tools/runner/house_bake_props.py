"""Lab props in the House's bake (#83; docs/house.md "Baking with lab props"), the pure parts: `house --bake
--props-dir DIR [--props-map TOML]` stages GLBs from DIR in place of the named props (and adds extra pieces to a room)
for the bake and its review shots only; the committed props and the raw prop folders are not touched. With
`--before DIR` the review also writes a before / after sheet: a labelled PNG of about 1280 px (a 5x7 pixel font, the
standard library only) and its numbers.

The mapping file (all keys optional):

    label = "C2-white"                  # the after rows' title on the sheet (default: DIR's name)
    [props]                             # prop id -> GLB path relative to DIR; without it every DIR/<id>.glb whose
    fridge = "fridge.glb"               # id is a dressing prop replaces that prop
    [[extra]]                           # a piece that is no dressing prop, placed in one room's Dressing group
    id = "backsplash_l"                 # a new id (prop_<id> when staged)
    room = "kitchen"
    glb = "detail/backsplash_l.glb"     # relative to DIR
    at = [1.47, 0.9, 0.1]               # room-local metres like the dressing's at = [x, h, z]
    yaw = 0.0                           # degrees
"""

from __future__ import annotations

import math
import re
import tomllib
from pathlib import Path

ID = re.compile(r"[a-z0-9_]+")


def load_map(path: Path | None) -> dict:
    """The mapping file as {"label", "props", "extra"}; raises ValueError naming every problem."""
    if path is None:
        return {"label": None, "props": None, "extra": []}
    raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    return check_map(raw)


def check_map(raw: dict) -> dict:
    problems = [f"unknown key {k}" for k in raw if k not in ("label", "props", "extra")]
    label = raw.get("label")
    if label is not None and not isinstance(label, str):
        problems.append("label must be a string")
    props = raw.get("props")
    if props is not None:
        for pid, rel in props.items():
            if not ID.fullmatch(pid) or not isinstance(rel, str) or not rel.endswith(".glb"):
                problems.append(f"props.{pid}: needs a lower-case id and a .glb path")
    extra = []
    for i, e in enumerate(raw.get("extra", [])):
        name = f"extra[{i}] {e.get('id')}"
        at = e.get("at", [])
        if not ID.fullmatch(str(e.get("id", ""))) or not isinstance(e.get("room"), str):
            problems.append(f"{name}: needs a lower-case id and a room")
        elif not str(e.get("glb", "")).endswith(".glb"):
            problems.append(f"{name}: needs a .glb path")
        elif len(at) != 3 or not all(isinstance(v, (int, float)) for v in at):
            problems.append(f"{name}: needs at = [x, h, z]")
        else:
            extra.append({"id": e["id"], "room": e["room"], "glb": e["glb"], "at": [float(v) for v in at],
                          "yaw": float(e.get("yaw", 0.0))})
    ids = [e["id"] for e in extra]
    problems += [f"extra id {x} twice" for x in sorted({x for x in ids if ids.count(x) > 1})]
    if problems:
        raise ValueError("props map: " + "; ".join(problems))
    return {"label": label, "props": dict(props) if props is not None else None, "extra": extra}


def swap(found: dict, known: set[str], props_dir: Path, mapping: dict, files: list[str] | None = None) -> dict:
    """The bake's prop id -> GLB table: `found` (the raw prop folders) with the props from props_dir in place of the
    named ones, and the extras added. `known` are the dressing's prop ids; `files` the GLB names in props_dir (read
    from it when None). Returns {"found", "swapped", "extra"}; raises ValueError on a mapped id that no room dresses,
    an extra id that is a dressing prop, or a missing file."""
    props_dir = Path(props_dir)
    if files is None:
        files = sorted(p.name for p in props_dir.glob("*.glb"))
    problems = []
    if mapping["props"] is None:
        pairs = {Path(f).stem: f for f in files if Path(f).stem in known}
        if not pairs:
            problems.append(f"no GLB in {props_dir.as_posix()} is named after a dressing prop")
    else:
        pairs = dict(mapping["props"])
        problems += [f"props.{pid}: no room dresses it" for pid in sorted(pairs) if pid not in known]
    problems += [f"extra {e['id']}: a dressing prop id" for e in mapping["extra"] if e["id"] in known]
    rels = list(pairs.values()) + [e["glb"] for e in mapping["extra"]]
    listed = set(files)
    missing = [r for r in rels if (r not in listed if "/" not in r else not (props_dir / r).is_file())]
    problems += [f"no {props_dir.as_posix()}/{r}" for r in missing]
    if problems:
        raise ValueError("--props-dir: " + "; ".join(problems))
    out = dict(found)
    for pid, rel in pairs.items():
        out[pid] = props_dir / rel
    for e in mapping["extra"]:
        out[e["id"]] = props_dir / e["glb"]
    return {"found": out, "swapped": sorted(pairs), "extra": [e["id"] for e in mapping["extra"]]}


def add_extras(dressing: dict, extra: list[dict]) -> dict:
    """A copy of the dressing (room id -> report) with each extra as one more resolved prop of its room."""
    out = dict(dressing)
    for e in extra:
        if e["room"] not in out:
            raise ValueError(f"extra {e['id']}: room {e['room']} has no dressing")
        rep = dict(out[e["room"]])
        rep["resolved"] = list(rep["resolved"]) + [{"kind": "props", "id": e["id"], "at": list(e["at"]),
                                                    "yaw": e["yaw"]}]
        out[e["room"]] = rep
    return out


def compare_rows(zone: str, preset: str, sheen: str | None, label: str) -> list[dict]:
    """The before / after sheet's rows: the before run's baked row, then this run's baked row and its sheen row
    (house_bake.shot_rows' labels for a preset review)."""
    rows = [{"title": "today baked", "side": "before", "row": f"{zone}_{preset}_baked"},
            {"title": f"{label} baked", "side": "after", "row": f"{zone}_{preset}_baked"}]
    if sheen:
        rows.append({"title": f"{label} baked + {preset} sheen", "side": "after", "row": f"{zone}_{preset}_{sheen}"})
    return rows


# ---------------------------------------------------------------- the labelled sheet
# 5x7 glyphs: seven rows of five bits as two hex digits each (the left pixel is the 0x10 bit).
FONT = {
    "A": "0e11111f111111", "B": "1e11111e11111e", "C": "0e11101010110e", "D": "1c12111111121c",
    "E": "1f10101e10101f", "F": "1f10101e101010", "G": "0e11101711110f", "H": "1111111f111111",
    "I": "0e04040404040e", "J": "0702020202120c", "K": "11121418141211", "L": "1010101010101f",
    "M": "111b1515111111", "N": "11111915131111", "O": "0e11111111110e", "P": "1e11111e101010",
    "Q": "0e11111115120d", "R": "1e11111e141211", "S": "0f10100e01011e", "T": "1f040404040404",
    "U": "1111111111110e", "V": "11111111110a04", "W": "1111111515150a", "X": "11110a040a1111",
    "Y": "11110a04040404", "Z": "1f01020408101f", "0": "0e11131519110e", "1": "040c040404040e",
    "2": "0e11010204081f", "3": "1f02040201110e", "4": "02060a121f0202", "5": "1f101e0101110e",
    "6": "0608101e11110e", "7": "1f010204080808", "8": "0e11110e11110e", "9": "0e11110f01020c",
    " ": "00000000000000", "-": "0000001f000000", "+": "0004041f040400", ".": "00000000000c0c",
    "/": "00010204081000", ":": "000c0c000c0c00", "_": "0000000000001f", "(": "02040808080402",
    ")": "08040202020408", ",": "000000000c0408",
}


def glyph(ch: str) -> list[int]:
    """A character's seven 5-bit rows (an unknown character: a box)."""
    code = FONT.get(ch.upper(), "1f11111111111f")
    return [int(code[i:i + 2], 16) for i in range(0, 14, 2)]


def draw_label(rows: list[bytearray], text: str, x0: int = 4, y0: int = 4, scale: int = 2) -> None:
    """Writes `text` (upper case) in white on a black box into RGB rows, clipped to the image."""
    h, w = len(rows), len(rows[0]) // 3 if rows else 0
    tw, th = (len(text) * 6 + 1) * scale, 9 * scale
    for y in range(y0, min(h, y0 + th)):
        for x in range(x0, min(w, x0 + tw)):
            rows[y][3 * x:3 * x + 3] = b"\x00\x00\x00"
    for i, ch in enumerate(text):
        for gy, bits in enumerate(glyph(ch)):
            for gx in range(5):
                if bits & (0x10 >> gx):
                    for sy in range(scale):
                        for sx in range(scale):
                            x = x0 + (1 + i * 6 + gx) * scale + sx
                            y = y0 + (1 + gy) * scale + sy
                            if x < w and y < h:
                                rows[y][3 * x:3 * x + 3] = b"\xff\xff\xff"


def downscale(width: int, height: int, px: list[tuple[int, int, int]], tw: int, th: int) -> list[bytearray]:
    """A box-filtered tw x th copy of an RGB frame (house_bake.read_png's pixels) as RGB rows."""
    xs = [(x * width // tw, max(x * width // tw + 1, (x + 1) * width // tw)) for x in range(tw)]
    out = []
    for y in range(th):
        y0, y1 = y * height // th, max(y * height // th + 1, (y + 1) * height // th)
        line = bytearray(3 * tw)
        for x, (x0, x1) in enumerate(xs):
            r = g = b = 0
            for yy in range(y0, y1):
                base = yy * width
                for p in px[base + x0:base + x1]:
                    r += p[0]
                    g += p[1]
                    b += p[2]
            n = (y1 - y0) * (x1 - x0)
            line[3 * x:3 * x + 3] = bytes((r // n, g // n, b // n))
        out.append(line)
    return out


def sheet(tiles: list[list[list[bytearray] | None]], titles: list[str], tw: int, th: int) -> list[bytes]:
    """Rows of tiles (None: a grey gap) into one image's RGB rows; each row's first tile carries its title."""
    grey = bytes((48, 48, 48)) * tw
    out: list[bytes] = []
    for row, title in zip(tiles, titles):
        band = [bytearray() for _ in range(th)]
        for t in row:
            for y in range(th):
                band[y] += t[y] if t is not None else grey
        draw_label(band, title)
        out += [bytes(b) for b in band]
    return out


def tile_size(cams: int, width: int = 1280) -> tuple[int, int]:
    tw = width // max(1, cams)
    return tw, int(math.floor(tw * 9 / 16))
