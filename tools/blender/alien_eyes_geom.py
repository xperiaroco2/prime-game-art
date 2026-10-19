"""The M4 eyes' pure parts (art #196): the wet line's profile under a lid's rolled rim, and the cornea's optics that
godot/alien/alien_eye.gdshader draws (the same formulas, so a test can check them without Godot). Plain Python, no
bpy: read by alien_eyes.py inside Blender and by tools/tests/test_alien_eyes_geom.py.

Lengths are in eyeball radii; elevations in radians about the lid's hinge (alien_parts_geom.lid_shell: the lid's
moving edge at p = 0, the upper lid covering p > 0, the lower p < 0).
"""
from __future__ import annotations

import json
import math
import struct

# The wet line (a tear film where a lid meets the ball): a strip in the lid's own frame, so it turns with the lid.
# Seen from the front it is a thin glossy band on the ball just beyond the lid's rim, which runs on under the rim
# close to the ball (hidden there; the shader fades it out just under the rim).
WET = {
    "beyond_deg": 1.5,  # how far the band reaches past the rim's farthest point onto the ball
    "lift": 0.0015,  # the band's height above the ball where it starts (a share of r), so it never z-fights
    # under the rim: this share of the way from the ball up to the rim's lower surface. 0.7 (the first M4) stood the
    # strip up as a wall under the rim, a grey shelf with a light line in a turned view; 0.1 keeps it on the ball
    "fill": 0.1,
    "t_max_deg": 80.0,  # the band's span across the lid (the lid's own latitude), faded at both ends by the shader
    "seg_t": 48,
    # segments beyond the rim (v 0 to RIM_V) and under it (RIM_V to 1): the rim's reach is at v = RIM_V on every lid,
    # so alien_wet.gdshader's alpha ramp (`rim_v`) follows it
    "seg_beyond": 3, "seg_under": 3,
}
# The cornea (alien_eye.gdshader's defaults; alien.gd EYE_LOOK sets limbus_deg per design)
CORNEA = {"limbus_deg": 27.0, "bulge": 0.12, "iris_depth": 0.05, "ior": 1.336}


def rim(rho_in: float, rho_out: float, bead: float) -> tuple[float, float]:
    """The rolled rim of lid_shell(): its centre radius and half width (both in r), as lid_shell builds them."""
    re = rho_out + bead
    return (re + rho_in) / 2, (re - rho_in) / 2


def rim_reach(rho_in: float, rho_out: float, bead: float) -> float:
    """How far (radians, about the hinge) the rolled rim's farthest point lies beyond the lid's edge: the lid hides
    the ball that far past its edge (alien_eye.gdshader's contact shadow starts there, alien.gd EYE_LOOK's
    `*_reach_deg`)."""
    rm, hw = rim(rho_in, rho_out, bead)
    return hw / rm


def rim_v(w: dict = WET) -> float:
    """The strip's V (from the ball's side) at the rim's reach (alien_wet.gdshader's `rim_v`)."""
    return w["seg_beyond"] / (w["seg_beyond"] + w["seg_under"])


def rim_lower_surface(p_abs: float, rm: float, hw: float) -> float | None:
    """The radius of the rim's half circle on the ball's side at |p| beyond the edge (None past the rim's reach)."""
    s = p_abs * rm / hw
    if s > 1.0:
        return None
    return rm - hw * math.sqrt(1.0 - s * s)


def wet_profile(rho_in: float, rho_out: float, bead: float, upper: bool, w: dict = WET) -> list[tuple[float, float]]:
    """The wet line's cross-section as (rho, p) from the ball's side (beyond the rim, on the ball) to under the rim's
    inner edge (p = 0): lift above the ball beyond the rim's reach, then rising evenly to `fill` of the way up to the
    lid's inner surface at its edge (under the rim's lower surface all the way)."""
    sgn = 1.0 if upper else -1.0
    rm, hw = rim(rho_in, rho_out, bead)
    reach = rim_reach(rho_in, rho_out, bead)
    p0 = reach + math.radians(w["beyond_deg"])
    nb, nu = w["seg_beyond"], w["seg_under"]
    out = []
    for j in range(nb + nu + 1):  # |p| from the band's far edge to the rim's reach, then on to the lid's edge
        pa = p0 - (p0 - reach) * j / nb if j <= nb else reach * (1.0 - (j - nb) / nu)
        rho = 1.0 + w["lift"]
        if pa < reach:  # under the rim: rising evenly from the ball toward the lid's inner surface, never a wall
            rho += (rho_in - rho) * w["fill"] * (1.0 - pa / reach)
        out.append((rho, -sgn * pa))
    return out


def lid_point(rho: float, p: float, t: float) -> tuple[float, float, float]:
    """lid_shell()'s point at radius rho, elevation p and latitude t (local -Y the edge's direction, +Z up)."""
    return (rho * math.sin(t), -rho * math.cos(t) * math.cos(p), rho * math.cos(t) * math.sin(p))


def cornea_sphere(limbus_deg: float, bulge: float) -> tuple[float, float]:
    """The cornea: a sphere through the limbus ring and the apex 1 + bulge on the axis; (centre on the axis, radius)."""
    lim = math.radians(limbus_deg)
    d = 1.0 + bulge - math.cos(lim)
    rc = (math.sin(lim) ** 2 + d * d) / (2.0 * d)
    return 1.0 + bulge - rc, rc


def refract(v, n, eta):
    """GLSL's refract() for 3-tuples (v, n unit)."""
    c = sum(a * b for a, b in zip(v, n))
    k = 1.0 - eta * eta * (1.0 - c * c)
    if k < 0.0:
        return (0.0, 0.0, 0.0)
    return tuple(eta * a - (eta * c + math.sqrt(k)) * b for a, b in zip(v, n))


def front_rho(x: float, c: dict = CORNEA) -> float:
    """The iris plane's radius that a ray along the axis at distance x reaches through the cornea: the shader's
    front_rho(), which keeps the design's iris and pupil angles as they looked from the front."""
    zc, rc = cornea_sphere(c["limbus_deg"], c["bulge"])
    zp = math.cos(math.radians(c["limbus_deg"])) - c["iris_depth"]
    hz = zc + math.sqrt(max(rc * rc - x * x, 0.0))
    ln = math.hypot(x, hz - zc)
    r = refract((0.0, 0.0, -1.0), (x / ln, 0.0, (hz - zc) / ln), 1.0 / c["ior"])
    return x + r[0] * (zp - hz) / min(r[2], -1e-3)


# M5 (art #196): the skin's subsurface mask in the ORM's B channel (the glTF metallic channel, unused: the material's
# metallicFactor is 0, so plain viewers stay non-metal). Linear like the rest of the ORM, and out of the albedo's
# alpha, which Godot's importer treats as alpha (fix_alpha_border) and which is sRGB-sampled.
# alien_hue's glTF extras (in Godot the material's "extras" metadata), read by godot/alien/alien.gd
SSS_MARKER = {"prime_sss": "orm_b"}
# The 2x mask upscale: output texel (2y + dy, 2x + dx) sits a quarter texel from its source texel's centre, toward
# y - 1 (dy 0) or y + 1 (dy 1), and the same in x: bilinear between the source texel (9/16), its two edge neighbours
# on that side (3/16 each) and the diagonal one (1/16); edges clamp.
UPSCALE2_TAPS = ((0, 0, 0.5625), (1, 0, 0.1875), (0, 1, 0.1875), (1, 1, 0.0625))  # (step in y, step in x, weight)


def upscale2_step(d: int) -> int:
    """The neighbour's direction for output phase d (0 or 1): -1 or +1 source texels."""
    return -1 if d == 0 else 1


def upscale2(grid: list[list[float]]) -> list[list[float]]:
    """The reference 2x upscale of a row-major grid (plain Python, for tests and small grids); alien_eyes.py does the
    same with numpy from UPSCALE2_TAPS on the 2K mask."""
    h, w = len(grid), len(grid[0])
    out = [[0.0] * (2 * w) for _ in range(2 * h)]
    for y in range(h):
        for x in range(w):
            for dy in (0, 1):
                for dx in (0, 1):
                    sy, sx = upscale2_step(dy), upscale2_step(dx)
                    v = 0.0
                    for ky, kx, wt in UPSCALE2_TAPS:
                        yy = min(max(y + ky * sy, 0), h - 1)
                        xx = min(max(x + kx * sx, 0), w - 1)
                        v += wt * grid[yy][xx]
                    out[2 * y + dy][2 * x + dx] = v
    return out


def glb_json(b: bytes) -> tuple[dict, int]:
    """A GLB's JSON chunk and the BIN chunk's data offset."""
    n, kind = struct.unpack_from("<I4s", b, 12)
    if b[:4] != b"glTF" or kind != b"JSON":
        raise ValueError("not a GLB")
    return json.loads(b[20:20 + n]), 20 + n + 8


def glb_texture_png(b: bytes, material: str, slot: str) -> bytes:
    """The image bytes behind a material's texture slot ("baseColorTexture" or "metallicRoughnessTexture" under
    pbrMetallicRoughness, or a top-level one such as "occlusionTexture")."""
    g, bin0 = glb_json(b)
    for m in g.get("materials", []):
        if m.get("name") == material:
            ref = m.get("pbrMetallicRoughness", {}).get(slot) or m.get(slot)
            if ref is None:
                raise ValueError(f"{material}: no {slot}")
            im = g["images"][g["textures"][ref["index"]]["source"]]
            v = g["bufferViews"][im["bufferView"]]
            o = bin0 + v.get("byteOffset", 0)
            return b[o:o + v["byteLength"]]
    raise ValueError(f"no material {material}")


def sss_orm_problems(b: bytes, material: str, orm_png: bytes) -> list[str]:
    """What is wrong with a GLB's ORM-B subsurface route for one material: its metallicRoughness and occlusion
    textures must be the very PNG written with the mask in B, its metallicFactor 0 and its extras SSS_MARKER."""
    g, _ = glb_json(b)
    mats = [m for m in g.get("materials", []) if m.get("name") == material]
    if not mats:
        return [f"no material {material}"]
    m, bad = mats[0], []
    if m.get("pbrMetallicRoughness", {}).get("metallicFactor", 1.0) != 0:
        bad.append("metallicFactor is not 0")
    for slot in ("metallicRoughnessTexture", "occlusionTexture"):
        try:
            if glb_texture_png(b, material, slot) != orm_png:
                bad.append(f"{slot} is not the ORM with the mask")
        except ValueError as e:
            bad.append(str(e))
    extras = m.get("extras", {})
    for k, v in SSS_MARKER.items():
        if extras.get(k) != v:
            bad.append(f"extras.{k} is not {v!r}")
    return bad
