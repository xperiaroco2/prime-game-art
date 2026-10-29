"""The cloth's baked maps made safe for mipmaps, and the denim's colour shift (art #196, clothes step 2, C1d; numpy,
run inside Blender by clothes_dress.py; tested by tools/tests/test_clothes_texture_blender.py).

Why: the denim was baked near-black (the legs' albedo median sRGB 23, 31, 45; Godot's frames 28, 36, 50 against the
sketch's 44, 55, 73), so beside a little specular it read as wet leather. `denim_weight` and `shift` scale the
denim's linear colour by a gain, the texture's own detail (seams, stitching, pockets) kept: the stripes (neutral) and
the orange stitching (red over blue) keep their colour. And the cleaner bakes onto fresh UVs whose many small
islands sit in black (albedo, roughness and normal 0): a far camera samples a small mip of the 2048 px maps, where
the black around thin islands (the straps) bleeds in. `fill` grows every map's island colours into the empty texels
(a push-pull pyramid), so every mip averages cloth only.

Blender's Image.pixels of an 8-bit image are its stored values (sRGB for the albedo), not linear: these functions
take and return stored sRGB values.
"""
from __future__ import annotations

import numpy as np


def island_mask(uv_tris: np.ndarray, w: int, h: int, grow: int = 1) -> np.ndarray:
    """Which texels the UV triangles (n x 3 x 2, in 0..1) cover, as an h x w bool array (row 0 at v = 0), grown by
    `grow` texels (the bake's own margin is kept anyway: it is filled from the islands)."""
    mask = np.zeros((h, w), bool)
    for tri in uv_tris:
        p = tri * np.array([w, h], dtype=np.float64)
        x0, y0 = np.floor(p.min(0)).astype(int)
        x1, y1 = np.ceil(p.max(0)).astype(int)
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, w - 1), min(y1, h - 1)
        if x1 < x0 or y1 < y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = p
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12:
            continue
        l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / den
        l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / den
        inside = (l1 >= -1e-6) & (l2 >= -1e-6) & (1 - l1 - l2 >= -1e-6)
        mask[y0:y1 + 1, x0:x1 + 1] |= inside
    for _ in range(grow):
        m = mask.copy()
        m[1:] |= mask[:-1]
        m[:-1] |= mask[1:]
        m[:, 1:] |= mask[:, :-1]
        m[:, :-1] |= mask[:, 1:]
        mask = m
    return mask


def fill(px: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """px (h x w x c) with every texel outside `valid` (h x w bool) replaced by the mean of the nearest valid texels
    (push-pull: halve with valid-weighted means down to one texel, then fill each level's holes from the coarser
    one). Valid texels stay exactly as they were."""
    if valid.all() or not valid.any():
        return px.copy()
    levels = [(px.astype(np.float64), valid.astype(np.float64))]
    while max(levels[-1][0].shape[:2]) > 1:
        c, w = levels[-1]
        hh, ww = c.shape[:2]
        ph, pw = hh % 2, ww % 2  # pad to even with zero weight
        c = np.pad(c * w[..., None], ((0, ph), (0, pw), (0, 0)))
        w = np.pad(w, ((0, ph), (0, pw)))
        cs = c[0::2, 0::2] + c[1::2, 0::2] + c[0::2, 1::2] + c[1::2, 1::2]
        ws = w[0::2, 0::2] + w[1::2, 0::2] + w[0::2, 1::2] + w[1::2, 1::2]
        levels.append((cs / np.maximum(ws, 1e-12)[..., None], np.minimum(ws, 1.0)))
    out = levels[-1][0]
    for c, w in reversed(levels[:-1]):
        hh, ww = c.shape[:2]
        up = np.repeat(np.repeat(out, 2, 0), 2, 1)[:hh, :ww]
        out = np.where((w > 0)[..., None], c, up)
    res = px.copy()
    res[~valid] = out[~valid].astype(px.dtype)
    return res


def to_srgb(lin: np.ndarray) -> np.ndarray:
    lin = np.clip(lin, 0.0, None)
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1 / 2.4) - 0.055)


def to_linear(s: np.ndarray) -> np.ndarray:
    s = np.clip(s, 0.0, None)
    return np.where(s <= 0.04045, s / 12.92, np.power((s + 0.055) / 1.055, 2.4))


def denim_weight(srgb: np.ndarray) -> np.ndarray:
    """0 to 1 per texel: how much of the denim's shift it takes, from its sRGB colour (blue over red by 3 to 8 points
    of 100, blue over green by 0 to 3). The stripes (neutral) and the orange stitching (red over blue) get 0."""
    r, g, b = srgb[..., 0], srgb[..., 1], srgb[..., 2]
    return np.clip((b - r - 0.03) / 0.05, 0.0, 1.0) * np.clip((b - g) / 0.03, 0.0, 1.0)


def shift(srgb: np.ndarray, gain: tuple[float, float, float]) -> np.ndarray:
    """Each texel's linear colour times 1 + weight * (gain - 1), per channel, clipped to 1; sRGB in and out."""
    wgt = denim_weight(srgb)[..., None]
    lin = to_linear(srgb.astype(np.float64)) * (1.0 + wgt * (np.asarray(gain, dtype=np.float64) - 1.0))
    return to_srgb(np.clip(lin, 0.0, 1.0)).astype(srgb.dtype)


def blur(a: np.ndarray, r: int) -> np.ndarray:
    """A box blur of a 2D map, 2r + 1 texels wide each way, its edges padded with their own values."""
    k = np.ones(2 * r + 1, dtype=np.float32) / (2 * r + 1)
    a = np.apply_along_axis(lambda m: np.convolve(np.pad(m, r, mode="edge"), k, mode="valid"), 0, a)
    return np.apply_along_axis(lambda m: np.convolve(np.pad(m, r, mode="edge"), k, mode="valid"), 1, a)


def free_rect(used: np.ndarray, pw: int, ph: int, margin: int):
    """The first pw x ph texel window (row, column of its low corner) with no used texel within margin and at least
    margin texels from the map's edges (so a repeat-wrapped mip does not mix in the opposite edge), or None."""
    h, w = used.shape
    m = used.copy()
    for _ in range(margin):
        g = m.copy()
        g[1:] |= m[:-1]
        g[:-1] |= m[1:]
        g[:, 1:] |= m[:, :-1]
        g[:, :-1] |= m[:, 1:]
        m = g
    if margin > 0:
        m[:margin] = m[-margin:] = True
        m[:, :margin] = m[:, -margin:] = True
    if ph > h or pw > w:
        return None
    sat = np.zeros((h + 1, w + 1), dtype=np.int64)
    sat[1:, 1:] = np.cumsum(np.cumsum(m, axis=0), axis=1)
    win = sat[ph:, pw:] - sat[:-ph, pw:] - sat[ph:, :-pw] + sat[:-ph, :-pw]
    ok = np.argwhere(win == 0)
    if not len(ok):
        return None
    r, c = ok[0]
    return int(r), int(c)


def stripe_image(navy, white, period, duty, per_m, islands: dict, v0: dict, size: tuple[int, int]) -> np.ndarray:
    """The shell top's albedo (linear, h x w x 3): white, and per island (name: u0, width) rows of navy and white
    from its edge (v0[name]), per_m UV units per metre in v (clothes_shell.stripe_cover per row); the torso's columns
    reach 0.8 % before it and 2 % past it, an arm's 0.5 and 0.8 %, so the island's margin keeps its stripes."""
    import clothes_shell as H
    w, h = size
    lin_n, lin_w = to_linear(np.asarray(navy)), to_linear(np.asarray(white))
    out = np.empty((h, w, 3), dtype=np.float32)
    out[:] = lin_w
    cols = np.arange(w) / w
    for name, (u0, wd) in islands.items():
        lo = u0 - 0.008 if name == H.TORSO else u0 - 0.005
        hi = u0 + wd + (0.02 if name == H.TORSO else 0.008)
        sel = (cols >= lo) & (cols < hi)
        for r in range(h):
            d0, d1 = (r / h - v0[name]) / per_m, ((r + 1) / h - v0[name]) / per_m
            c = H.stripe_cover(d0, d1, period, duty) if d1 > 0 else 0.0
            out[r, sel] = c * lin_n + (1 - c) * lin_w
    return out


def vertex_normals(pts: np.ndarray, faces: list[list[int]]) -> np.ndarray:
    """Per vertex its area-weighted normal from faces (fan-triangulated), unit length (0-length: left 0)."""
    acc = np.zeros_like(pts)
    for f in faces:
        for k in range(1, len(f) - 1):
            a, b, c = f[0], f[k], f[k + 1]
            n = np.cross(pts[b] - pts[a], pts[c] - pts[a])
            acc[a] += n
            acc[b] += n
            acc[c] += n
    ln = np.linalg.norm(acc, axis=1)
    ln[ln == 0] = 1.0
    return acc / ln[:, None]

