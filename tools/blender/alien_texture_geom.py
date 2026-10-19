"""Pure formulas of the alien skin's authored texture set (art #196, step M3a), with no Blender import, so
tools/tests/test_alien_texture_geom.py runs them with the standard library. alien_texture.py calls the same functions
on numpy arrays (`xp=numpy`): every formula here uses only arithmetic and `xp.clip`, so one code path serves both.

The inputs are per-texel fields on Body's `UVMap` (alien_texture.py bakes them): the masks (light, accent), M2's bakes
(AO, curvature with 0.5 flat, thickness with white thick), the S9 shader's gradient terms (deep, face warmth) as
baked fields, low-frequency noises (blotch, hue), a fine noise and the pore cavity of M2's normal map, and region
masks (T-zone, the mouth's rim, the flush round the mouth and cheeks, the warm thin parts: fingers, crest, neck).
All colours are linear; the colour constants are sRGB as the kit's (alien_assemble.HUES_SRGB, PALE_SRGB,
alien_face.ACCENT) and converted here.
"""
from __future__ import annotations

import math

TEAL_SRGB = (0.11, 0.48, 0.51)  # alien_assemble.HUES_SRGB["teal"] (S9, sampled against rf2)
PALE_SRGB = (0.86, 0.92, 0.81)  # alien_assemble.PALE_SRGB["teal"]
ACCENT_SRGB = (0.89, 0.42, 0.36)  # alien_face.ACCENT (knees, elbows, knuckles)
LIGHT_MIX, ACCENT_MIX = 0.88, 0.9  # alien_assemble.LIGHT_MIX, ACCENT_MIX (alien_hue.gdshader light_mix, accent_mix)
DEEP_MUL = (0.55, 0.72, 0.78)  # alien_hue.gdshader deep_mul: the deep hue = hue * DEEP_MUL (linear)
WARM_MUL = (1.06, 1.0, 0.90)  # alien_hue.gdshader warm_mul: the pale tint's warm shift toward the face

# The look's strengths, chosen on variant grids against rf2 (M3a/variants/g1, g2; alien_texture.py --settings merges
# overrides): g2's `quiet` column. Stronger cavity and pore darkening drew M2's creases as dark lines (an older,
# wrinkled face, never rf2's clean toy skin). Roughness (g3's `clean`): 0.55 everywhere read matte beside rf2's broad
# sheen, 0.48 with a T-zone of -0.14 laid a wet patch on the forehead, and a pore-scale roughness noise of 0.05 made
# the highlight sparkle on the back (M2's normal map already breaks the highlight up at the pore scale).
# The accent's edge is narrowed (accent_edge): teal and coral mixed half and half are grey, which read as a dirty
# band round the knuckle spots.
TEX = {
    # the S9 gradient (alien.gd SKIN deep_top/deep_back/face_warm; baked into the `deep` and `face` fields)
    "deep": 1.0, "face_warm": 0.6,
    # baked AO multiplied into the albedo: mix(1, ao, ao)
    "ao": 0.5,
    # curvature cavity: concave darker and bluer, convex lighter in its own hue (cavity in -1..1 from the curvature map)
    "cavity_dark": 0.20, "cavity_blue": 0.25, "convex_light": 0.10, "curv_gain": 2.5,
    # low-frequency colour: warm/cool hue drift and soft value blotches (noise fields in -1..1)
    "hue_shift": 0.06, "blotch": 0.05, "pale_hue_shift": 0.03,
    # warm translucency at the thin parts (fingers, crest, neck), times thinness
    "thin_warm": 0.35, "thin_floor": 0.35,
    # a soft coral flush round the mouth and cheeks (on the pale)
    "flush": 0.10,
    # the accent mask's soft edge narrowed to this smoothstep range (0, 1: the kit's own edge)
    "accent_edge": (0.2, 0.8),
    # saturation of the kit's teal and pale about their luminance (1: the kit's colours). Under light D and AgX the
    # kit's pale rendered grey-white beside rf2's mint (Blender and Godot alike); grid g4 chose 1.15 and 1.6 (2.2 and
    # 1.3 turned the pale pistachio)
    "hue_sat": 1.15, "pale_sat": 1.6,
    # pores: a faint albedo darkening in the normal map's pores
    "pore_dark": 0.0,
    # roughness
    "rough": 0.52, "rough_convex": 0.14, "rough_concave": 0.06, "rough_tzone": 0.06, "rough_mouth": 0.16,
    "rough_fine": 0.015, "rough_pore": 0.0, "rough_min": 0.30, "rough_max": 0.80,
    # the subsurface mask for the Godot shader (M5): thinness, plus the warm parts
    "sss_thin": 1.0, "sss_region": 0.35, "sss_gamma": 1.4,
}
WARM_TINT = (1.45, 1.18, 0.86)  # the thin parts' multiplier at full warmth (linear): more red and green, less blue, so a
# teal turns a lighter, warmer green-teal and keeps its saturation (a coral mix turned the fingers grey)
COOL_TINT = (0.80, 0.95, 1.12)  # the cavity's blue shift (linear multiplier direction)
FLUSH = (0.95, 0.55, 0.50)  # the flush's colour (linear): a soft coral, the lips' family


class _Py:
    """The pure-Python stand-in for numpy's clip (scalars only)."""

    @staticmethod
    def clip(x, lo, hi):
        return min(max(x, lo), hi)


PY = _Py()


def srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c: float) -> float:
    c = min(max(c, 0.0), 1.0)
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1.0 / 2.4) - 0.055


def lin3(c):
    return tuple(srgb_to_linear(x) for x in c)


def smoothstep(a, b, x, xp=PY):
    t = xp.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def mix(a, b, t):
    return a + (b - a) * t


def saturate(c, k):
    """A linear colour's saturation scaled by k about its luminance (Rec. 709), each channel kept above 0.001."""
    y = 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    return tuple(max(y + (x - y) * k, 0.001) for x in c)


def cavity(curv, s=None, xp=PY):
    """The curvature map (0.5 flat) as a signed cavity in -1..1: negative concave, positive convex."""
    s = TEX if s is None else s
    return xp.clip((curv - 0.5) * 2.0 * s["curv_gain"], -1.0, 1.0)


def albedo(f, s=None, xp=PY):
    """The skin's linear albedo (r, g, b) from a dict of fields f (scalars or same-shaped arrays):
    light, accent, ao, curv, thick, deep, face, blotch, hue, warm, flush, pore (pore: 0 none .. 1 a deep pore).
    The order: the kit's flat look (alien_hue.gdshader: the gradient, the pale tint by the light mask, the accent),
    then the hue drift and blotches, the cavity tint, the thin parts' warmth, the flush, AO, the pores."""
    s = TEX if s is None else s
    teal, pale = saturate(lin3(TEAL_SRGB), s["hue_sat"]), saturate(lin3(PALE_SRGB), s["pale_sat"])
    acc = lin3(ACCENT_SRGB)
    light = xp.clip(f["light"], 0.0, 1.0)
    deep = xp.clip(f["deep"] * s["deep"], 0.0, 1.0) * (1.0 - light)
    face = f["face"] * s["face_warm"]
    cav = cavity(f["curv"], s, xp)
    concave = xp.clip(-cav, 0.0, 1.0)
    convex = xp.clip(cav, 0.0, 1.0)
    thin = xp.clip(1.0 - f["thick"], 0.0, 1.0)
    out = []
    for i in range(3):
        base = mix(teal[i], teal[i] * DEEP_MUL[i], deep)
        p = pale[i] * mix(1.0, WARM_MUL[i], face)
        # the low-frequency drift: on the hue a warm/cool shift (red up, blue down for warm) and value blotches
        sign = (1.0, 0.0, -1.0)[i]
        base = base * (1.0 + s["hue_shift"] * f["hue"] * sign) * (1.0 + s["blotch"] * f["blotch"])
        p = p * (1.0 + s["pale_hue_shift"] * f["hue"] * sign) * (1.0 + 0.5 * s["blotch"] * f["blotch"])
        c = mix(base, p, light * LIGHT_MIX)
        c = mix(c, acc[i], smoothstep(s["accent_edge"][0], s["accent_edge"][1], f["accent"], xp) * ACCENT_MIX)
        # the cavity: concave darker and bluer, convex lighter in its own hue (a mix toward the pale washed the
        # thin, all-convex fingers out to grey)
        c = c * (1.0 - s["cavity_dark"] * concave) * mix(1.0, COOL_TINT[i], s["cavity_blue"] * concave)
        c = c * (1.0 + s["convex_light"] * convex)
        # the thin parts' warmth (light through the skin): a multiply toward the warm tint
        w = s["thin_warm"] * xp.clip(f["warm"], 0.0, 1.0) * mix(s["thin_floor"], 1.0, thin)
        c = c * mix(1.0, WARM_TINT[i], w)
        # the flush (on the pale only)
        c = mix(c, c * FLUSH[i] / max(FLUSH) * 1.1, s["flush"] * xp.clip(f["flush"], 0.0, 1.0) * light)
        c = c * mix(1.0, f["ao"], s["ao"])
        c = c * (1.0 - s["pore_dark"] * xp.clip(f["pore"], 0.0, 1.0))
        out.append(xp.clip(c, 0.0, 1.0))
    return tuple(out)


def roughness(f, s=None, xp=PY):
    """The skin's roughness from fields f: curv, tzone, mouth, fine (-1..1), pore (0..1). Glossier on convex
    forms, the T-zone and round the mouth; rougher in the creases; a fine breakup and the pores rougher."""
    s = TEX if s is None else s
    cav = cavity(f["curv"], s, xp)
    r = (s["rough"] - s["rough_convex"] * xp.clip(cav, 0.0, 1.0) + s["rough_concave"] * xp.clip(-cav, 0.0, 1.0)
         - s["rough_tzone"] * xp.clip(f["tzone"], 0.0, 1.0) - s["rough_mouth"] * xp.clip(f["mouth"], 0.0, 1.0)
         + s["rough_fine"] * f["fine"] + s["rough_pore"] * xp.clip(f["pore"], 0.0, 1.0))
    return xp.clip(r, s["rough_min"], s["rough_max"])


def sss_mask(f, s=None, xp=PY):
    """The subsurface mask (0..1, white = more light through): thinness (1 - thickness) raised to sss_gamma, plus
    the warm parts' region."""
    s = TEX if s is None else s
    thin = xp.clip(1.0 - f["thick"], 0.0, 1.0)
    return xp.clip(s["sss_thin"] * thin ** s["sss_gamma"] + s["sss_region"] * xp.clip(f["warm"], 0.0, 1.0), 0.0, 1.0)


def orm(ao, rough):
    """glTF's packed occlusion-roughness-metallic texel: R occlusion, G roughness, B metallic (0)."""
    return (ao, rough, 0.0)


# The bake cage (PR #231 minor 6): an explicit cage, Body's copy with each vertex moved out along its smoothed normal
# by cage_offset(clearance), where clearance is the distance along that normal to the next surface of the low mesh
# (the next finger, the nostril's far wall). M2's uniform 2 mm extrusion put the rays' start inside the next finger in
# the webs and across the nostril slits.
CAGE = {"max_mm": 2.0, "min_mm": 0.3, "share": 0.4, "ray_mm": 4.0, "probe_mm": 20.0}


def cage_offset(clearance_mm: float, c=None) -> float:
    """The cage's offset (mm) at a vertex whose normal meets the low mesh again after clearance_mm (math.inf: never):
    `share` of the clearance, within min_mm..max_mm."""
    c = CAGE if c is None else c
    if math.isinf(clearance_mm):
        return c["max_mm"]
    return min(max(c["share"] * clearance_mm, c["min_mm"]), c["max_mm"])


def micro_pore(div, gain: float = 6.0, xp=PY):
    """A pore's depth (0..1) from the tangent-space normal map's divergence (d nx / du + d ny / dv per texel, OpenGL
    +Y). For a height field h the normal leans along -grad h, so the divergence is -laplacian(h): in a pit (h at a
    minimum) it is negative, on a bump positive."""
    return xp.clip(-div * gain, 0.0, 1.0)
