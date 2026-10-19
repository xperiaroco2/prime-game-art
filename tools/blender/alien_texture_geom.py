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

import json
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
# band round the knuckle spots. M3A is the shipped M3a set's settings (PR #233); TEX, the current set's, is M3A with
# M3C's changes over it.
M3A = {
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
    # M3c (the tuning toward rf2; at these values the formulas are M3a's): the texture's own pale and face warmth
    # (the kit's PALE_SRGB and WARM_MUL read yellow-olive beside rf2's mint), the accent's peak, chroma kept through
    # its edge (keep_chroma) and its blur (texels at 4K, alien_texture.py), the contact AO (contact_ao: the AO lifted
    # to its deepest part, everywhere by `contact` and round the eyes by `socket_contact`, so the lids leave a thin
    # contact shade instead of a dark ring) and the cavity's darkening cut in the eye sockets
    "pale_srgb": PALE_SRGB, "warm_mul": WARM_MUL, "accent_mix": ACCENT_MIX, "accent_keep": 0.0, "accent_blur": 0,
    "contact": 0.0, "socket_contact": 0.0, "contact_hi": 0.6, "socket_cavity": 0.0,
}
# M3c (art #196): M3a tuned toward rf2 on two grids (M3c/variants/g1: the pale's hue, the AO, the accent; g2: the
# roughness; rf2 first). Beside rf2 M3a's face read yellow-olive (rendered green barely above red), a dark ring sat
# round the eye sockets (M2's 5 cm AO under the large lids, plus the sockets' cavity), its roughness of about 0.5 drew
# M2's pores as a glossy orange peel at 0.6 m, and the knee and knuckle spots were crisp coral discs (stickers).
# - the pale: its own mint (green well above red, blue about red: rf2's cheek renders 0.82/0.88/0.79), no blue cut
#   by the face warmth; g1's cooler pale (blue above red) read cyan, the creamier one yellow again;
# - the AO: lifted to its contact shade round the eyes (socket_contact 1) and partly everywhere (contact 0.45), with
#   the sockets' cavity darkening off, and 0.4 of it in the albedo;
# - roughness 0.66 (g2: 0.72 read flat and chalky beside rf2's soft sheen on the dome), convex only 0.06 glossier, no
#   T-zone, the lips' surroundings 0.14 glossier (rf2's soft sheen there);
# - the accent: the kit's full soft edge, blurred (accent_blur 32 texels at 4K) and full from 0.6 of the blurred mask
#   (g2's 24 texels on the full edge erased the small knuckle spots), 0.85 at its peak, its chroma kept 0.6 through
#   the edge (no dusty band); the teal (hue_sat) stays M3a's.
M3C = {
    "pale_srgb": (0.81, 0.94, 0.82), "pale_sat": 1.15, "warm_mul": (1.0, 1.0, 0.97), "ao": 0.4,
    "contact": 0.45, "socket_contact": 1.0, "contact_hi": 0.55, "socket_cavity": 1.0,
    "rough": 0.66, "rough_convex": 0.06, "rough_concave": 0.04, "rough_tzone": 0.0, "rough_mouth": 0.14,
    "rough_fine": 0.01, "rough_max": 0.85,
    "accent_edge": (0.0, 0.6), "accent_mix": 0.85, "accent_keep": 0.6, "accent_blur": 32,
}
TEX = {**M3A, **M3C}
# The texture sets alien_texture.py composes and exports (--set, required): each name's settings in full.
SETS = {"m3a": M3A, "m3c": TEX}


def settings_diff(old: dict, new: dict, legacy: dict = M3A) -> list:
    """The keys whose values differ between a texture folder's recorded settings (old: settings.json's "settings")
    and new, compared as JSON (tuples as lists). A key missing from old counts as its legacy value: M3a's
    settings.json predates M3c's keys, whose M3A values reproduce M3a's formulas."""
    def norm(v):
        return json.loads(json.dumps(v))

    return sorted(k for k in set(old) | set(new)
                  if norm(old.get(k, legacy.get(k))) != norm(new.get(k, legacy.get(k))))
WARM_TINT = (1.45, 1.18, 0.86)  # the thin parts' multiplier at full warmth (linear): more red and green, less blue, so a
# teal turns a lighter, warmer green-teal and keeps its saturation (a coral mix turned the fingers grey)
COOL_TINT = (0.80, 0.95, 1.12)  # the cavity's blue shift (linear multiplier direction)
FLUSH = (0.95, 0.55, 0.50)  # the flush's colour (linear): a soft coral, the lips' family


class _Py:
    """The pure-Python stand-in for numpy's clip (scalars only)."""

    @staticmethod
    def clip(x, lo, hi):
        return min(max(x, lo), hi)

    @staticmethod
    def sqrt(x):
        return math.sqrt(x)


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


def chroma(c, xp=PY):
    """A linear colour's distance from its own grey (Rec. 709 luminance)."""
    y = 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    return xp.sqrt((c[0] - y) ** 2 + (c[1] - y) ** 2 + (c[2] - y) ** 2)


def keep_chroma(c, a, b, t, k, cap=2.0, xp=PY):
    """c, the linear mix of colours a and b by t, with its chroma pushed back (by k, 0..1) toward the mix of a's and
    b's chromas, at most cap times its own, about its luminance: two far-apart hues (the teal and the accent's coral)
    mixed half and half are a dusty grey, which drew a grey band round the knee and knuckle spots."""
    y = 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    want = mix(chroma(a, xp), chroma(b, xp), t)
    g = mix(1.0, xp.clip(want / (chroma(c, xp) + 1e-4), 1.0, cap), k)
    return tuple(xp.clip(y + (x - y) * g, 0.001, 1.0e3) for x in c)


def contact_ao(ao, socket, s=None, xp=PY):
    """The AO (1 open, 0 closed) lifted toward its deepest part: ao / contact_hi clipped to 1, never darker than ao,
    blended in by `contact` everywhere and `socket_contact` times the socket mask (the skin round the eyes). M2's AO
    reaches 5 cm, so the large lids drew a dark ring round each socket; lifted, only their contact shade stays."""
    s = TEX if s is None else s
    w = xp.clip(s["contact"] + s["socket_contact"] * socket, 0.0, 1.0)
    return mix(ao, xp.clip(ao / s["contact_hi"], 0.0, 1.0), w)


def cavity(curv, s=None, xp=PY):
    """The curvature map (0.5 flat) as a signed cavity in -1..1: negative concave, positive convex."""
    s = TEX if s is None else s
    return xp.clip((curv - 0.5) * 2.0 * s["curv_gain"], -1.0, 1.0)


def albedo(f, s=None, xp=PY):
    """The skin's linear albedo (r, g, b) from a dict of fields f (scalars or same-shaped arrays):
    light, accent, ao, curv, thick, deep, face, blotch, hue, warm, flush, pore (pore: 0 none .. 1 a deep pore),
    socket (optional, 0: the skin round the eyes for contact_ao and socket_cavity).
    The order: the kit's flat look (alien_hue.gdshader: the gradient, the pale tint by the light mask, the accent),
    then the hue drift and blotches, the cavity tint, the thin parts' warmth, the flush, AO, the pores."""
    s = TEX if s is None else s
    teal, pale = saturate(lin3(TEAL_SRGB), s["hue_sat"]), saturate(lin3(s["pale_srgb"]), s["pale_sat"])
    acc = lin3(ACCENT_SRGB)
    socket = f.get("socket", 0.0)
    light = xp.clip(f["light"], 0.0, 1.0)
    deep = xp.clip(f["deep"] * s["deep"], 0.0, 1.0) * (1.0 - light)
    face = f["face"] * s["face_warm"]
    cav = cavity(f["curv"], s, xp)
    concave = xp.clip(-cav, 0.0, 1.0) * (1.0 - s["socket_cavity"] * xp.clip(socket, 0.0, 1.0))
    convex = xp.clip(cav, 0.0, 1.0)
    thin = xp.clip(1.0 - f["thick"], 0.0, 1.0)
    ao = contact_ao(f["ao"], socket, s, xp)
    skin = []
    for i in range(3):
        base = mix(teal[i], teal[i] * DEEP_MUL[i], deep)
        p = pale[i] * mix(1.0, s["warm_mul"][i], face)
        # the low-frequency drift: on the hue a warm/cool shift (red up, blue down for warm) and value blotches
        sign = (1.0, 0.0, -1.0)[i]
        base = base * (1.0 + s["hue_shift"] * f["hue"] * sign) * (1.0 + s["blotch"] * f["blotch"])
        p = p * (1.0 + s["pale_hue_shift"] * f["hue"] * sign) * (1.0 + 0.5 * s["blotch"] * f["blotch"])
        skin.append(mix(base, p, light * LIGHT_MIX))
    t = smoothstep(s["accent_edge"][0], s["accent_edge"][1], f["accent"], xp) * s["accent_mix"]
    c = [mix(skin[i], acc[i], t) for i in range(3)]
    if s["accent_keep"]:
        c = keep_chroma(c, skin, acc, t, s["accent_keep"], xp=xp)
    out = []
    for i in range(3):
        # the cavity: concave darker and bluer, convex lighter in its own hue (a mix toward the pale washed the
        # thin, all-convex fingers out to grey)
        ci = c[i] * (1.0 - s["cavity_dark"] * concave) * mix(1.0, COOL_TINT[i], s["cavity_blue"] * concave)
        ci = ci * (1.0 + s["convex_light"] * convex)
        # the thin parts' warmth (light through the skin): a multiply toward the warm tint
        w = s["thin_warm"] * xp.clip(f["warm"], 0.0, 1.0) * mix(s["thin_floor"], 1.0, thin)
        ci = ci * mix(1.0, WARM_TINT[i], w)
        # the flush (on the pale only)
        ci = mix(ci, ci * FLUSH[i] / max(FLUSH) * 1.1, s["flush"] * xp.clip(f["flush"], 0.0, 1.0) * light)
        ci = ci * mix(1.0, ao, s["ao"])
        ci = ci * (1.0 - s["pore_dark"] * xp.clip(f["pore"], 0.0, 1.0))
        out.append(xp.clip(ci, 0.0, 1.0))
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



def blur(arr, mask, r, xp):
    """arr (h, w) blurred by three box passes of radius r texels (about a Gaussian), only over mask's texels
    (normalised by the blurred mask, so the UV gaps' fill never bleeds in); outside mask arr is kept. Arrays only:
    xp is numpy (tools/tests/test_alien_texture_blur_blender.py runs it in Blender's Python)."""
    if r < 1:
        return arr

    def box(x):
        for ax in (0, 1):
            c = xp.cumsum(xp.pad(x, [(r + 1, r) if i == ax else (0, 0) for i in range(2)], mode="edge"), axis=ax,
                          dtype=xp.float64)
            hi = [slice(None)] * 2
            lo = [slice(None)] * 2
            hi[ax], lo[ax] = slice(2 * r + 1, None), slice(None, -2 * r - 1)
            x = ((c[tuple(hi)] - c[tuple(lo)]) / (2 * r + 1)).astype(xp.float32)
        return x

    m = mask.astype(xp.float32)
    v, w = arr * m, m
    for _ in range(3):
        v, w = box(v), box(w)
    return xp.where(mask, v / xp.maximum(w, 1e-6), arr)


def texture_note(name: str, s: dict) -> str:
    """character.json's note on the exported texture set `name`, its numbers from the set's settings s."""
    ao = f"{s['ao']:g} of the AO baked in"
    if s["contact"] or s["socket_contact"]:
        ao += (f" (the AO lifted toward its contact shade, ao / {s['contact_hi']:g}: by {s['contact']:g} everywhere, "
               f"fully round the eyes)" if s["socket_contact"] >= 1 else
               f" (the AO lifted toward its contact shade, ao / {s['contact_hi']:g}, by {s['contact']:g})")
    accent = (f", the accent spots blurred ({s['accent_blur']:g} texels at 4K)" if s["accent_blur"] else "")
    return (
        f"art #196 {name.upper()}: the skin (Body, material alien_hue) carries an authored 4K texture set on UVMap "
        "(TEXCOORD_0): baseColorTexture (sRGB albedo: the teal and pale by the masks with hue drift, blotches, cavity "
        f"tint, thin-part warmth, flush{accent} and {ao}), metallicRoughnessTexture and occlusionTexture in one ORM "
        f"image (R occlusion, G roughness about {s['rough']:g}, B metallic 0), normalTexture (the M2 detail normal map "
        "rebaked through an explicit cage). alien_skin_sss.png beside the GLB is the subsurface mask (white: thin) for "
        "the Godot shader (M5). The alternative crests (crest_antennae, crest_fins) are on alien_hue_part, an "
        "untextured copy of the skin's material (no image: their UVs are not Body's UVMap). COLOR_0 (the vertex AO) "
        "is still exported for alien_hue.gdshader; a plain glTF viewer multiplies it into the albedo again. The albedo "
        "is for the teal hue only.")

# The bake cage (PR #231 minor 6): an explicit cage, Body's copy with each vertex moved out along its smoothed normal
# by cage_offset(clearance), where clearance is the distance along that normal to the next surface of the low mesh
# (the next finger, the nostril's far wall). M2's uniform 2 mm extrusion put the rays' start inside the next finger in
# the webs and across the nostril slits.
CAGE = {"max_mm": 2.0, "min_mm": 0.3, "share": 0.4, "ray_mm": 4.0, "probe_mm": 20.0}


def cage_offset(clearance_mm: float, c=None) -> float:
    """The cage's offset (mm) at a vertex whose normal meets the low mesh again after clearance_mm (math.inf: never):
    `share` of the clearance, within min_mm..max_mm, and never past half the clearance (in a gap narrower than
    2 * min_mm the floor would start the rays beyond its middle, nearer the far wall)."""
    c = CAGE if c is None else c
    if math.isinf(clearance_mm):
        return c["max_mm"]
    return min(max(c["share"] * clearance_mm, c["min_mm"]), 0.5 * clearance_mm, c["max_mm"])


def micro_pore(div, gain: float = 6.0, xp=PY):
    """A pore's depth (0..1) from the tangent-space normal map's divergence (d nx / du + d ny / dv per texel, OpenGL
    +Y). For a height field h the normal leans along -grad h, so the divergence is -laplacian(h): in a pit (h at a
    minimum) it is negative, on a bump positive."""
    return xp.clip(-div * gain, 0.0, 1.0)


# The export's image check: the materials that may reference an image in the GLB. The skin carries the texture set on
# Body's UVMap; the flipbook mouths their atlases. Anything else (as M3a's first export, whose alien_hue_part kept M2's
# 4K normal map and sampled it through the crests' own UVs) fails the export stage.
IMAGE_MATERIALS = ("alien_hue",)
IMAGE_MATERIAL_PREFIXES = ("alien_mouth_flip_",)


def _texture_refs(o):
    """The texture indices of a glTF material (any `*Texture` object with an index, extensions included)."""
    if isinstance(o, dict):
        for k, v in o.items():
            if k.endswith("Texture") and isinstance(v, dict) and "index" in v:
                yield v["index"]
            yield from _texture_refs(v)
    elif isinstance(o, list):
        for v in o:
            yield from _texture_refs(v)


def image_materials(gltf: dict) -> dict:
    """{material name: the sorted names (or indices) of the images it references} of a parsed glTF JSON, only the
    materials with at least one."""
    images, textures = gltf.get("images", []), gltf.get("textures", [])
    out = {}
    for i, m in enumerate(gltf.get("materials", [])):
        refs = set()
        for t in _texture_refs(m):
            src = textures[t].get("source")
            refs.add(images[src].get("name", str(src)) if src is not None else f"texture {t}")
        if refs:
            out[m.get("name", f"material {i}")] = sorted(refs)
    return out


def unexpected_images(gltf: dict) -> dict:
    """image_materials() without the materials allowed an image (IMAGE_MATERIALS, IMAGE_MATERIAL_PREFIXES)."""
    return {k: v for k, v in image_materials(gltf).items()
            if k not in IMAGE_MATERIALS and not k.startswith(IMAGE_MATERIAL_PREFIXES)}
