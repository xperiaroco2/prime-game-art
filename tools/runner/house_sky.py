"""The House map's evening sky and backdrop textures (art #81c, docs/house-outdoor.md), standard library only: a PNG
writer, periodic value noise (no seam where u wraps), the equirectangular dusk sky and the flats' silhouettes with
their lit windows. The settings are `layouts/house/outdoor/sky.toml`; `house_outdoor` writes the files."""

from __future__ import annotations

import math
import random
import struct
import zlib
from pathlib import Path

# ---------------------------------------------------------------- PNG


def png_bytes(width: int, height: int, rows: list[bytes], channels: int = 3) -> bytes:
    """An 8-bit RGB (channels 3) or RGBA (4) PNG from `height` rows of width * channels bytes."""
    if len(rows) != height or any(len(r) != width * channels for r in rows):
        raise ValueError("rows do not match the size")

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    colour = {3: 2, 4: 6}[channels]
    head = struct.pack(">IIBBBBB", width, height, 8, colour, 0, 0, 0)
    raw = b"".join(b"\x00" + r for r in rows)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", head) + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")


def write_png(path: Path, width: int, height: int, rows: list[bytes], channels: int = 3) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png_bytes(width, height, rows, channels))
    return path


def read_png(path: Path) -> tuple[int, int, int, list[bytes]]:
    """Reads back a PNG this module wrote (8-bit, filter 0): width, height, channels, rows."""
    data = path.read_bytes()
    pos, idat, width = 8, b"", 0
    while pos < len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        kind, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + n]
        if kind == b"IHDR":
            width, height, _, colour = struct.unpack(">IIBB", body[:10])
            channels = {2: 3, 6: 4}[colour]
        elif kind == b"IDAT":
            idat += body
        pos += 12 + n
    raw = zlib.decompress(idat)
    stride = width * channels + 1
    rows = [raw[i * stride + 1:(i + 1) * stride] for i in range(height)]
    return width, height, channels, rows


# ---------------------------------------------------------------- colour


def hex_rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in range(0, 6, 2))


def to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def to_srgb(c: float) -> float:
    c = min(max(c, 0.0), 1.0)
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def mix(a, b, t: float):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def smooth(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def byte(c: float) -> int:
    return max(0, min(255, int(round(c * 255))))


# ---------------------------------------------------------------- noise


class Noise:
    """Value noise on a grid of cells, periodic in u (and in v when `wrap_v`), smoothstep-interpolated; octaves double
    the cells and halve the weight. u and v run 0..1."""

    def __init__(self, seed: int, cells: tuple[int, int], octaves: int = 3, wrap_v: bool = False) -> None:
        rnd = random.Random(seed)
        self.layers = []
        cx, cy = cells
        for o in range(octaves):
            nx, ny = cx * 2 ** o, cy * 2 ** o
            grid = [[rnd.random() for _ in range(nx)] for _ in range(ny + 1)]
            self.layers.append((nx, ny, grid, 0.5 ** o))
        self.total = sum(w for *_, w in self.layers)
        self.wrap_v = wrap_v

    def __call__(self, u: float, v: float) -> float:
        s = 0.0
        for nx, ny, grid, w in self.layers:
            x, y = (u % 1.0) * nx, min(max(v, 0.0), 1.0) * ny
            i, j = int(x), min(int(y), ny - 1)
            fx, fy = smooth(x - i), smooth(y - j)
            i0, i1 = i % nx, (i + 1) % nx
            j1 = (j + 1) % ny if self.wrap_v else j + 1
            a = grid[j][i0] + (grid[j][i1] - grid[j][i0]) * fx
            b = grid[j1][i0] + (grid[j1][i1] - grid[j1][i0]) * fx
            s += (a + (b - a) * fy) * w
        return s / self.total


# ---------------------------------------------------------------- the sky


def stop_colour(stops: list, elev: float) -> tuple[float, float, float]:
    """The sky's colour at an elevation: smooth between the stops, mixed in linear light."""
    pts = sorted((float(e), tuple(to_linear(c) for c in hex_rgb(h))) for e, h in stops)
    if elev <= pts[0][0]:
        return pts[0][1]
    for (e0, c0), (e1, c1) in zip(pts, pts[1:]):
        if elev <= e1:
            return mix(c0, c1, smooth((elev - e0) / (e1 - e0)))
    return pts[-1][1]


def sky_rows(cfg: dict) -> tuple[int, int, list[bytes]]:
    """The equirectangular sky: rows from the zenith down, colours from the stops, soft clouds, faint stars."""
    width, height = cfg["size"]
    seed = int(cfg.get("seed", 0))
    cl, st = cfg["clouds"], cfg["stars"]
    noise = Noise(seed, tuple(cl["cells"]), 4)
    cloud_lin = tuple(to_linear(c) for c in hex_rgb(cl["hex"]))
    rim_lin = tuple(to_linear(c) for c in hex_rgb(cl["rim_hex"]))
    rnd = random.Random(seed + 1)
    stars: dict[tuple[int, int], float] = {}
    top = int(height * (90 - st["from_deg"]) / 180)
    for _ in range(int(st["count"])):
        r, c = rnd.randrange(0, max(top, 1)), rnd.randrange(0, width)
        elev = 90 - 180 * (r + 0.5) / height
        fade = smooth((elev - st["from_deg"]) / 25.0)
        stars[(r, c)] = st["brightness"] * fade * (0.4 + 0.6 * rnd.random())
    rows = []
    for r in range(height):
        elev = 90 - 180 * (r + 0.5) / height
        base = stop_colour(cfg["stops"], elev)
        in_band = cl["from_deg"] <= elev <= cl["to_deg"]
        band = smooth((elev - cl["from_deg"]) / 4.0) * smooth((cl["to_deg"] - elev) / 8.0)
        rim = smooth((cl["rim_deg"] - elev) / max(cl["rim_deg"] - cl["from_deg"], 1e-6))
        tint = mix(cloud_lin, rim_lin, rim)
        v = (elev - cl["from_deg"]) / (cl["to_deg"] - cl["from_deg"])
        out = bytearray()
        for c in range(width):
            col = base
            if in_band:
                n = noise(c / width, v)
                a = smooth((n - (1 - cl["cover"])) / cl["softness"]) * band * cl["strength"]
                if a > 0:
                    col = mix(col, tint, a)
            s = stars.get((r, c))
            if s:
                col = tuple(x + s * (1 - x) for x in col)
            out += bytes(byte(to_srgb(x)) for x in col)
        rows.append(bytes(out))
    return width, height, rows


def seam_step(rows: list[bytes], channels: int = 3) -> tuple[float, float]:
    """The mean colour step across the wrap (last column to the first) and the mean step between neighbouring
    columns elsewhere, in 0..255: a seam shows as a wrap step much larger than the others."""
    w = len(rows[0]) // channels
    wrap = inner = 0.0
    for r in rows:
        wrap += sum(abs(r[(w - 1) * channels + k] - r[k]) for k in range(3))
        inner += sum(abs(r[(w // 2) * channels + k] - r[(w // 2 - 1) * channels + k]) for k in range(3))
    return wrap / (3 * len(rows)), inner / (3 * len(rows))


# ---------------------------------------------------------------- the flats


def profile(kind: str, noise: Noise, u: float) -> float:
    """The silhouette's top as a fraction of the flat's height at u (0..1 round the ring)."""
    if kind == "trees":
        n = noise(u, 0.2)
        crowns = 0.5 + 0.5 * math.sin(u * 2 * math.pi * 160 + 6 * noise(u, 0.7))
        return 0.42 + 0.38 * n + 0.14 * crowns ** 2
    if kind == "hills":
        return 0.30 + 0.62 * noise(u, 0.4)
    return 0.55 + 0.35 * noise(u, 0.6)


def flat_rows(flat: dict, seed: int) -> tuple[int, int, list[bytes], int]:
    """One flat's RGBA texture (row 0 its top) with its lit windows painted in, opaque; returns the windows placed.

    The windows live in the colour texture, not in an emission texture: the flats' materials are unlit
    (KHR_materials_unlit), so the colour is what shows, and Godot's unshaded materials ignore emission."""
    width, height = flat["texture"]
    kind = flat["profile"]
    cells = {"trees": (48, 2), "hills": (9, 2), "haze": (5, 2)}[kind]
    noise = Noise(seed, cells, 4 if kind == "trees" else 3)
    low = tuple(to_linear(c) for c in hex_rgb(flat["hex_low"]))
    high = tuple(to_linear(c) for c in hex_rgb(flat["hex_high"]))
    alpha_max = 0.7 if kind == "haze" else 1.0
    tops = [profile(kind, noise, (c + 0.5) / width) for c in range(width)]
    rgba = []
    for r in range(height):
        f = 1 - (r + 0.5) / height  # height fraction of this row
        col = mix(low, high, smooth(f))
        px = bytes(byte(to_srgb(x)) for x in col)
        out = bytearray()
        for c in range(width):
            edge = (tops[c] - f) * height  # pixels below the silhouette's top
            a = min(max(edge + 0.5, 0.0), 1.0) * alpha_max
            if kind == "haze":
                a *= smooth(edge / (height * 0.25))
            out += px + bytes((byte(a),))
        rgba.append(out)
    placed = 0
    win = flat.get("windows")
    if win:
        rnd = random.Random(seed + 7)
        wx, wy = win["size_px"]
        lit = bytes(byte(c) for c in hex_rgb(win["hex"])) + b"\xff"
        tries = 0
        while placed < win["count"] and tries < win["count"] * 50:
            tries += 1
            c0 = rnd.randrange(0, width - wx)
            f = rnd.uniform(*win["band"])
            r0 = int((1 - f) * height) - wy
            if min(tops[c0:c0 + wx]) - f < (wy + 3) / height:
                continue  # the window must sit under the silhouette
            for r in range(r0, r0 + wy):
                for c in range(c0, c0 + wx):
                    rgba[r][c * 4:c * 4 + 4] = lit
            placed += 1
    return width, height, [bytes(r) for r in rgba], placed
