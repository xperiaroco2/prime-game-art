"""The pinball machine's art (art #374, Gate 3), made in headless Blender with numpy (Blender's own Python), called by
pinball_build.py before it builds the materials:

- earth_field.png (1024 x 2048): the playfield's night Earth seen from orbit, the limb arc across the field as in the
  concept (the planet at the player's end, the arc bulging up the table), the city lights from NASA's Black Marble
  (the hall's cut `lobby/hall/v11/earth/earth_night_cap.jpg`, lat -8..82, lon -48..72; no new download), a thin
  blue atmosphere on the limb, navy space with sparse stars beyond it;
- earth_side.png (2048 x 600): the side panels' art, the same imagery with the planet along the panel's foot
  and its limb rising from the front edge to the top toward the back (both sides use it, so they mirror each other);
- rough_dark.png, rough_light.png (512 x 512, tiling): the two greys' roughness break-up in the green channel (stored
  as data), like the hall's panels: soft blotches and fine grain around the material's roughness.

Each Earth is an orthographic view of a sphere: a pixel at (east, north) cm from the sphere's centre on the panel is
the point (e, n) = (east, north) / R on the unit disc, turned to latitude and longitude about the sub-point (lat0,
lon0) by the inverse orthographic projection, and the night map is sampled there (2 x 2 supersampling). Credit:
"Earth imagery: NASA" (sources/nasa_earth_lobby.toml).
"""

import math
from pathlib import Path

import bpy
import numpy as np

CAP = {"lat": (-8.0, 82.0), "lon": (-48.0, 72.0)}     # earth_night_cap.jpg's box (lobby --earth-tex)
# the playfield (table frame, cm): x -36..36 across, z -66..65 (far end first); the sphere and its sub-point
FIELD = {"size": (1024, 2048), "x": (-36.0, 36.0), "z": (-66.0, 65.0), "centre": (0.0, 50.0), "r": 65.0,
         "sub": (5.0, 15.0), "seed": 7}
# a side panel (cm from its front end along it, and up from its bottom edge): 86 x 25.3; the limb rises to the back
SIDE = {"size": (2048, 600), "len": 86.0, "h": 25.3, "centre": (51.0, -56.0), "r": 83.0, "sub": (-5.0, 15.0),
        "seed": 11}
SPACE = np.array([0.020, 0.040, 0.105])      # navy (sRGB 0..1) at the limb, darker away from it
SPACE_FAR = np.array([0.008, 0.014, 0.045])
ATMO = np.array([0.30, 0.62, 1.00])          # the limb's blue
LIGHTS_GAIN = 1.5                            # the city lights a little brighter than the map's
LAND = np.array([0.30, 0.42, 0.85])          # the land and sea's dim tone (the map's lilac turned navy)
GOLD = np.array([1.00, 0.80, 0.50])          # the city lights' tone


def load(path: Path) -> np.ndarray:
    im = bpy.data.images.load(str(path), check_existing=False)
    w, h = im.size
    a = np.empty(w * h * 4, dtype=np.float32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(h, w, 4)[::-1, :, :3].copy()     # top row first, the stored sRGB values


def save(rgb: np.ndarray, path: Path) -> None:
    h, w = rgb.shape[:2]
    im = bpy.data.images.new(path.stem, w, h, alpha=False)
    a = np.ones((h, w, 4), dtype=np.float32)
    a[..., :3] = np.clip(rgb, 0.0, 1.0)
    im.pixels.foreach_set(np.ascontiguousarray(a[::-1]).ravel())
    im.filepath_raw = str(path)
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)


def earth(night: np.ndarray, east: np.ndarray, north: np.ndarray, r: float, sub, seed: int) -> np.ndarray:
    """The view at panel points (east, north) cm from the sphere's centre: the Earth inside r, space outside."""
    lat0, lon0 = (math.radians(a) for a in sub)
    e, n = east / r, north / r
    rho = np.sqrt(e * e + n * n)
    inside = rho < 1.0
    c = np.arcsin(np.clip(rho, 0.0, 1.0))
    sc, cc = np.sin(c), np.cos(c)
    safe = np.where(rho > 1e-9, rho, 1.0)
    lat = np.arcsin(np.clip(cc * math.sin(lat0) + n * sc * math.cos(lat0) / safe, -1.0, 1.0))
    lon = lon0 + np.arctan2(e * sc, rho * cc * math.cos(lat0) - n * sc * math.sin(lat0))
    lat, lon = np.degrees(lat), (np.degrees(lon) + 180.0) % 360.0 - 180.0
    h, w = night.shape[:2]
    u = (lon - CAP["lon"][0]) / (CAP["lon"][1] - CAP["lon"][0]) * (w - 1)
    v = (CAP["lat"][1] - lat) / (CAP["lat"][1] - CAP["lat"][0]) * (h - 1)
    in_cap = (u >= 0) & (u <= w - 1) & (v >= 0) & (v <= h - 1)
    col = night[np.clip(v, 0, h - 1).astype(int), np.clip(u, 0, w - 1).astype(int)] * in_cap[..., None]
    lum = col @ np.array([0.2126, 0.7152, 0.0722])          # the concept's tones: the land deep navy, the lights gold
    k = np.clip((lum - 0.30) / 0.45, 0.0, 1.0)[..., None]
    col = (1.0 - k) * LAND * np.power(lum, 1.4)[..., None] / 0.3 ** 0.4 + k * GOLD * lum[..., None] * 1.25
    col = col * LIGHTS_GAIN * (0.55 + 0.45 * np.power(cc, 0.5))[..., None]   # darker toward the limb
    d = (rho - 1.0) * r                         # cm outside the limb (negative inside)
    rim_in = 0.45 * np.exp(np.minimum(d, 0.0) / 1.0)
    rim_out = 0.75 * np.exp(-np.maximum(d, 0.0) / 1.6)
    far = np.clip(d / 40.0, 0.0, 1.0)[..., None]
    space = SPACE * (1.0 - far) + SPACE_FAR * far
    rng = np.random.default_rng(seed)
    stars = (rng.random(d.shape) < 0.0015) * rng.uniform(0.25, 0.85, d.shape)
    space = space + stars[..., None] * np.array([0.85, 0.9, 1.0])
    out = np.where(inside[..., None], col + rim_in[..., None] * ATMO, space + rim_out[..., None] * ATMO)
    return out


def supersample(fn, xs: np.ndarray, ys: np.ndarray, dx: float, dy: float) -> np.ndarray:
    acc = 0.0
    for ox in (-0.25, 0.25):
        for oy in (-0.25, 0.25):
            acc = acc + fn(xs + ox * dx, ys + oy * dy)
    return acc / 4.0


def field_art(night: np.ndarray, path: Path) -> None:
    f = FIELD
    w, h = f["size"]
    x = f["x"][0] + (np.arange(w) + 0.5) / w * (f["x"][1] - f["x"][0])
    z = f["z"][0] + (np.arange(h) + 0.5) / h * (f["z"][1] - f["z"][0])     # top row: the far end
    xs, zs = np.meshgrid(x, z)
    dx, dz = (f["x"][1] - f["x"][0]) / w, (f["z"][1] - f["z"][0]) / h
    img = supersample(lambda a, b: earth(night, a - f["centre"][0], f["centre"][1] - b, f["r"], f["sub"], f["seed"]),
                      xs, zs, dx, dz)
    save(img, path)


def side_art(night: np.ndarray, path: Path) -> None:
    s = SIDE
    w, h = s["size"]
    along = (np.arange(w) + 0.5) / w * s["len"]               # image left: the front end
    up = s["h"] - (np.arange(h) + 0.5) / h * s["h"]            # top row first
    xs, ys = np.meshgrid(along, up)
    img = supersample(lambda a, b: earth(night, a - s["centre"][0], b - s["centre"][1], s["r"], s["sub"], s["seed"]),
                      xs, ys, s["len"] / w, s["h"] / h)
    save(img, path)


def rough(path: Path, base: float, amp: float, seed: int, n: int = 512) -> None:
    """A tiling roughness break-up: 1/f noise (blotches) plus fine grain, in [base - amp, base + amp]."""
    rng = np.random.default_rng(seed)
    k = np.fft.fftfreq(n)[:, None] ** 2 + np.fft.fftfreq(n)[None, :] ** 2
    k[0, 0] = 1.0
    blot = np.real(np.fft.ifft2(np.fft.fft2(rng.standard_normal((n, n))) / k ** 0.9))
    blot = (blot - blot.mean()) / (np.abs(blot).max() + 1e-9)
    grain = rng.standard_normal((n, n)) * 0.12
    val = np.clip(base + amp * (0.85 * blot + grain), 0.05, 0.95)
    save(np.repeat(val[..., None], 3, axis=2), path)


def make(folder: Path, night_path: Path, rough_specs: dict) -> dict:
    """All four images into folder; rough_specs: {file: (base, amp)}. Returns their sizes."""
    folder.mkdir(parents=True, exist_ok=True)
    night = load(night_path)
    field_art(night, folder / "earth_field.png")
    side_art(night, folder / "earth_side.png")
    for i, (name, (base, amp)) in enumerate(sorted(rough_specs.items())):
        rough(folder / name, base, amp, 100 + i)
    return {"earth_field.png": list(FIELD["size"]), "earth_side.png": list(SIDE["size"]),
            **{k: [512, 512] for k in rough_specs}, "night_map": night_path.as_posix()}
