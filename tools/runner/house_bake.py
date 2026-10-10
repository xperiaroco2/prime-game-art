"""The House's lightmap bake, the pure parts (#83; docs/house.md "Light"): the night window, the pieces a zone scene
uses, the zone build's arguments, the review cameras and the frame measures (L*, the dark share, C* p90).

The bake itself needs the Godot editor with a window (LightmapGI.bake() is editor-only C++): `house --bake` stages
the pieces, builds each zone's bake scene headless (godot/house/zone_build.gd), presses the editor's bake button
through the lmbake plugin (godot/addons/lmbake) in an off-screen window, and shoots the baked and real-time frames
(godot/house/bake_shots.gd). Editor runs only at night (00:00-08:00 local) or inside a window the manager granted."""

from __future__ import annotations

import math
import re
import struct
import time
import zlib
from pathlib import Path

NIGHT_START_H, NIGHT_END_H = 0, 8
# One grant file for the lab runner and this command: "until YYYY-MM-DD HH:MM" (local), written by the manager only
# after the engineer's yes in chat, removed after the run (labrun.py's rule).
GRANT = "research/2026-10-06-locations/lab/editor_window.txt"
EDITOR_BAN = ("house --bake: the editor bakes only between 00:00 and 08:00 local (or inside a window the manager "
              "granted); build the zones by day with --no-bake and bake at night")
PROP_IMPORT = {"meshes/light_baking": 2, "meshes/lightmap_texel_size": 0.2}  # Godot unwraps the props' UV2
KIT_IMPORT = {"meshes/light_baking": 1}  # the kit keeps its own UV2 (one island per face, docs/kit.md)
PROP_TEXEL_PER_M = 1.0 / PROP_IMPORT["meshes/lightmap_texel_size"]
ABOVE_OTHER_K = 0.1  # Above's walls and props only occlude: a tenth of the texels


def granted_until(text: str | None) -> float | None:
    """The grant file's end time (epoch seconds), or None when there is none or it is unreadable."""
    for line in (text or "").splitlines():
        if line.startswith("until "):
            try:
                return time.mktime(time.strptime(line[6:].strip(), "%Y-%m-%d %H:%M"))
            except ValueError:
                return None
    return None


def editor_allowed(now: float, grant_text: str | None = None) -> bool:
    """True inside the night window (local hours NIGHT_START_H..NIGHT_END_H) or before a grant's end."""
    until = granted_until(grant_text)
    if until is not None and now < until:
        return True
    return NIGHT_START_H <= time.localtime(now).tm_hour < NIGHT_END_H


def grant_text(raw: Path | None) -> str | None:
    path = raw / GRANT if raw else None
    try:
        return path.read_text(encoding="utf-8") if path else None
    except OSError:
        return None


def used_glbs(texts) -> set[str]:
    """The kit_<id> and prop_<id> names the zone and room scenes instance (res://import/<name>.glb)."""
    found: set[str] = set()
    for t in texts:
        found |= set(re.findall(r"res://import/((?:kit|prop)_[a-z0-9_]+)\.glb", t))
    return found


def uv2_table(pieces: list[dict]) -> dict[str, float]:
    """kit piece id -> its UV2 units per metre (the kit's pieces.json), for the lightmap size hints."""
    return {p["id"]: p["uv2_per_m"] for p in pieces if p.get("uv2_per_m")}


def size_hint(texel_per_m: float, uv2_per_m: float, k: float = 1.0) -> int:
    """A kit piece's lightmap_size_hint for texel_per_m (times k); at least 4. zone_build.gd computes the same."""
    return max(4, math.ceil(texel_per_m * k / uv2_per_m - 1e-9))


def build_args(zone: str, tag: str, texel: float, bake: dict, uv2_json: str, bake_json: str, above: float = 1.0,
               merge: bool = False) -> list[str]:
    """The user arguments of zone_build.gd for one zone and preset."""
    return [f"zone={zone}", f"tag={tag}", f"texel={texel:g}", f"denoiser={int(bool(bake['denoiser']))}",
            f"energy={float(bake['bounce_indirect_energy']):g}", f"above={above:g}", f"merge={int(merge)}",
            f"uv2={uv2_json}", f"bake={bake_json}"]


def e1_cam(rect: list[float], floor_y: float) -> list[float]:
    """The lab's E1 view: from a corner at eye height (1.6 m) across the room to three quarters, 0.9 m up."""
    x, z, w, d = rect
    return [x + 0.8, floor_y + 1.6, z + 0.8, x + w * 0.75, floor_y + 0.9, z + d * 0.75]


def seam_cam(rect: list[float], floor_y: float) -> list[float]:
    """A level view along the room's long middle line from 1 m inside its north wall: the ceiling and the floor tiles
    both in frame (#83a's seam camera stood inside a wall)."""
    x, z, w, d = rect
    return [x + w / 2, floor_y + 1.6, z + 1.0, x + w / 2, floor_y + 1.6, z + d * 0.6]


def views(data: dict, room_ids: list[str]) -> list[list[float]]:
    """E1 cameras of the given rooms, then the first room's seam camera."""
    found = {r["id"]: (r["rect"], lv["floor_y"]) for lv in data["levels"] for r in lv["rooms"]}
    missing = [r for r in room_ids if r not in found]
    if missing:
        raise ValueError(f"no room {', '.join(missing)}")
    return [e1_cam(*found[r]) for r in room_ids] + [seam_cam(*found[room_ids[0]])]


# ---------------------------------------------------------------- frame measures
def read_png(path: Path) -> tuple[int, int, list[tuple[int, int, int]]]:
    """An 8-bit RGB or RGBA PNG (any filter, not interlaced) as width, height and RGB pixels."""
    data = Path(path).read_bytes()
    pos, idat, width, height, ch = 8, b"", 0, 0, 3
    while pos < len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        kind, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + n]
        if kind == b"IHDR":
            width, height, depth, colour, _, _, interlace = struct.unpack(">IIBBBBB", body[:13])
            if depth != 8 or colour not in (2, 6) or interlace:
                raise ValueError(f"{path}: only 8-bit RGB/RGBA, not interlaced")
            ch = 3 if colour == 2 else 4
        elif kind == b"IDAT":
            idat += body
        pos += 12 + n
    raw = zlib.decompress(idat)
    stride = width * ch
    prev = bytearray(stride)
    px = []
    for y in range(height):
        f = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - ch] if i >= ch else 0
            b = prev[i]
            c = prev[i - ch] if i >= ch else 0
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        px.extend((line[i], line[i + 1], line[i + 2]) for i in range(0, stride, ch))
        prev = line
    return width, height, px


def srgb_lab(r: int, g: int, b: int) -> tuple[float, float, float]:
    """8-bit sRGB -> CIELAB (D65)."""
    def lin(v: int) -> float:
        c = v / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    rl, gl, bl = lin(r), lin(g), lin(b)
    x = (0.4124 * rl + 0.3576 * gl + 0.1805 * bl) / 0.95047
    y = 0.2126 * rl + 0.7152 * gl + 0.0722 * bl
    z = (0.0193 * rl + 0.1192 * gl + 0.9505 * bl) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116
    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def measures(width: int, height: int, px: list[tuple[int, int, int]], grid: int = 160) -> dict:
    """The house lab's frame numbers on a grid of about `grid` pixels across: L* mean, the share under L* 20 (dark %)
    and C* p90."""
    step = max(1, width // grid)
    ls, cs = [], []
    for y in range(step // 2, height, step):
        for x in range(step // 2, width, step):
            lum, a, b = srgb_lab(*px[y * width + x])
            ls.append(lum)
            cs.append(math.hypot(a, b))
    cs.sort()
    return {"L_mean": round(sum(ls) / len(ls), 1), "dark_pct": round(100 * sum(v < 20 for v in ls) / len(ls), 1),
            "C_p90": round(cs[min(len(cs) - 1, int(0.9 * len(cs)))], 1)}
