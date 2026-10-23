"""Pure formulas of the alien pilot's static premium heads (art #196, static_v5), with no Blender import, so
tools/tests/test_alien_static_geom.py runs them with the standard library. alien_static_head.py calls the same
functions on numpy arrays (`xp=numpy`, each coordinate or colour channel a separate array): every formula here uses
only arithmetic and the few `xp` functions `_Py` mirrors, so one code path serves both. alien_static_run.py calls
`fix_tangents` on the exported GLBs.
"""
from __future__ import annotations

import json
import math
import struct
from pathlib import Path


class _Py:
    """The numpy functions the formulas use, on plain floats."""

    @staticmethod
    def clip(x, lo, hi):
        return min(max(x, lo), hi)

    @staticmethod
    def sqrt(x):
        return math.sqrt(x)

    @staticmethod
    def exp(x):
        return math.exp(x)

    @staticmethod
    def abs(x):
        return abs(x)

    @staticmethod
    def maximum(a, b):
        return max(a, b)

    @staticmethod
    def where(cond, a, b):
        return a if cond else b


PY = _Py()


def smoothstep(a, b, x, xp=PY):
    t = xp.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def to_linear(c, xp=PY):
    """sRGB to linear (one channel)."""
    return xp.where(c <= 0.04045, c / 12.92, ((xp.maximum(c, 0.04045) + 0.055) / 1.055) ** 2.4)


def to_srgb(c, xp=PY):
    """Linear to sRGB (one channel), clipped to 0..1 first."""
    c = xp.clip(c, 0.0, 1.0)
    return xp.where(c <= 0.0031308, c * 12.92, 1.055 * xp.maximum(c, 0.0031308) ** (1 / 2.4) - 0.055)


def eye_dist(x, y, z, ec, r, xp=PY):
    """The distance to the nearer fitted eye sphere's centre, in eye radii. ec: the right eye's centre with
    ec[0] >= 0 (the left eye mirrors it in x); Blender coordinates."""
    return xp.sqrt((xp.abs(x) - ec[0]) ** 2 + (y - ec[1]) ** 2 + (z - ec[2]) ** 2) / r


def ellipsoid_w(x, y, z, centre, radii, lo=0.6, xp=PY):
    """1 inside lo of the ellipsoid, falling linearly to 0 on its surface."""
    e = xp.sqrt(((x - centre[0]) / radii[0]) ** 2 + ((y - centre[1]) / radii[1]) ** 2
                + ((z - centre[2]) / radii[2]) ** 2)
    return 1.0 - xp.clip((e - lo) / (1.0 - lo), 0.0, 1.0)


def keep_weights(x, y, z, ec, r, mouth, half_w, rim_w, rims=True, xp=PY):
    """static_v2: where the decimation keeps more of the dense original: the lips (an ellipsoid around the lip line)
    and the lid rims (a shell 1.1 eye radii round each fitted eye sphere, rim_w metres its Gaussian width)."""
    lips = ellipsoid_w(x, y, z, mouth, (half_w * 1.25, 0.09, 0.09), 0.5, xp)
    if not rims:
        return lips
    rim = xp.exp(-((eye_dist(x, y, z, ec, r, xp) - 1.1) * r / rim_w) ** 2)
    return xp.clip(xp.maximum(lips, rim), 0.0, 1.0)


def alive_colour(c, top, flush, crease, teal, k=1.0, xp=PY):
    """static_v4: the alive layers' colour on one texel (or arrays of texels): c the plain albedo's (r, g, b) in sRGB,
    top, flush and crease the layers' weights (alien_static_head.alive), teal the skin's own teal (sRGB), k the
    strength (0 = the plain albedo). Every change is a lerp toward the teal (the crown, scaled by the texel's
    lightness so the shading stays; the flush) or toward a darker teal of the same hue (the crease, 0.72 of it):
    never a hue shift. Returns (r, g, b), clipped to 0..1."""
    tl = [min(max(float(t), 0.0), 1.0) for t in teal]
    lum = (c[0] + c[1] + c[2]) / 3 / max(sum(tl) / 3, 1e-3)
    kt = min(0.85 * k, 1.0)
    out = []
    for i in range(3):
        a = c[i]
        a = a + kt * top * (xp.clip(tl[i] * (0.75 + 0.25 * lum), 0.0, 1.0) - a)
        a = a + k * 0.22 * flush * (tl[i] - a)
        a = a + k * 0.3 * crease * (0.72 * tl[i] - a)
        out.append(xp.clip(a, 0.0, 1.0))
    return tuple(out)


def fix_tangents(glb: Path) -> int:
    """static_v2: Blender exports a zero TANGENT where a triangle's UVs have no area (glTF-Validator: non-unit
    TANGENT; a glTF viewer then shades the vertex black). Each zero tangent becomes a unit vector perpendicular to its
    vertex normal (w = 1); returns how many were fixed. The GLB is rewritten in place (the chunks keep their sizes).
    Interleaved buffer views are honoured (`byteStride`; a tight view packs VEC4 at 16 bytes, VEC3 at 12)."""
    data = bytearray(Path(glb).read_bytes())
    jlen = struct.unpack_from("<I", data, 12)[0]
    doc = json.loads(data[20:20 + jlen])
    base = 20 + jlen + 8  # the BIN chunk's data
    fixed = 0

    def where(i: int, tight: int) -> tuple[int, int, int]:
        acc = doc["accessors"][i]
        view = doc["bufferViews"][acc["bufferView"]]
        return base + view.get("byteOffset", 0) + acc.get("byteOffset", 0), acc["count"], view.get("byteStride", tight)

    for mesh in doc["meshes"]:
        for prim in mesh["primitives"]:
            att = prim["attributes"]
            if "TANGENT" not in att or "NORMAL" not in att:
                continue
            t0, n, ts = where(att["TANGENT"], 16)
            n0, _, ns = where(att["NORMAL"], 12)
            for k in range(n):
                tx, ty, tz, _w = struct.unpack_from("<4f", data, t0 + ts * k)
                if tx * tx + ty * ty + tz * tz > 0.5:
                    continue
                nx, ny, nz = struct.unpack_from("<3f", data, n0 + ns * k)
                ax = (0.0, 1.0, 0.0) if abs(ny) < 0.9 else (1.0, 0.0, 0.0)
                cx, cy, cz = ny * ax[2] - nz * ax[1], nz * ax[0] - nx * ax[2], nx * ax[1] - ny * ax[0]
                ln = math.sqrt(cx * cx + cy * cy + cz * cz) or 1.0
                struct.pack_into("<4f", data, t0 + ts * k, cx / ln, cy / ln, cz / ln, 1.0)
                fixed += 1
    if fixed:
        Path(glb).write_bytes(bytes(data))
    return fixed
