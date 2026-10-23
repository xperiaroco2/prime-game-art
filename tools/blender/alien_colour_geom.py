"""The alien pilot's static heads (art #196): the player's colour slots, plain Python. The same maths lives in
godot/alien/alien_static.gd (`slot_colours`, `guard`) and tools/web/alien_colour/colour.js (`slotColours`, `guard`);
test_alien_colour_slots.py checks all three against this file.

Slots, each an sRGB colour the player picks:
- skin: every skin texel follows it (hue turned, saturation and value scaled from the build's `base_skin`);
- lips: the lips (the accent mask's R) in their own colour;
- detail: the marks (the accent's G: the chameleon's crest stripes, the axolotl's freckles and gills) in their own
  colour when `detail_on`; off, they follow the skin as the build's paint does;
- gills (the axolotl, with the details on): "gradient" (the default: the accent's G, skin at the gill's root to the
  details colour at its tips), "whole" (the whole gill, stalk and fringe: the accent's A, 1 - gill) or "skin";
- the pale front (the accent's B) is no slot: it follows the skin as a tinted cream (study variant E).

Guard rails, in OKLCh (OKLab's lightness, chroma and hue; v2: the hue angle kept, CIELAB's chroma cut bent blue
toward violet), on every picked colour (a slot the player leaves out keeps the build's own paint, the
approved look, never guarded): a chroma cap and a lightness range per slot, the cap lowered round the yellow-green
and the hot pink hues (BANDS: they read acidic at a chroma the others carry), for a dark skin (a deep colour at full
chroma reads neon: below the dark knee) and for light lips and details (a light colour at full chroma reads neon:
above the light knee), and the lips at least LIP_CONTRAST from
the skin (OKLab delta E; moved darker in L, or lighter when darker leaves the range). The recolour itself runs in sRGB HSV, in the
shader too (it converts the linear albedo to sRGB and back), so every cap is in one space.
"""
from __future__ import annotations

import colorsys
import math

# per slot: (chroma cap C, L min, L max, dark knee, light knee) in OKLab (OKLCh: L 0-1, the chroma C, the hue kept):
# the cap scaled by (L - 0.009) / (dark - 0.009) below the dark knee and by (1 - L) / (1 - light) above the light knee
# (None: no knee). v2 (2026-10-23): the CS1 rails were CIELAB (C* 40/42/42/16, L* 35-85, 25-80, 20-85, 82-93, knees
# L* 55 and 70) and a CIELAB chroma cut bends blue toward violet (navy went violet-slate); re-derived here: L = (L* +
# 16) / 116 on the greys, C = 0.0027 C* (the median ratio at C* 40 over every hue and L* 40-85), the bands' edges
# mapped from CIELAB hues (yellow-green 90-161, hot pink 300-22).
RAILS = {"skin": (0.108, 0.44, 0.871, 0.612, None), "lips": (0.113, 0.353, 0.828, None, 0.741),
         "detail": (0.113, 0.31, 0.871, None, 0.741), "front": (0.043, 0.845, 0.94, None, None)}
# hue bands with a lower cap: (centre, half width (OKLCh hue degrees), the cap's factor at the centre, a cosine bump)
BANDS = [(125.0, 36.0, 0.7), (341.0, 41.0, 0.8)]  # yellow-green, hot pink
LIP_CONTRAST = 0.1  # OKLab delta E (CIE76's 12 in lightness), lips against the skin
GILL_MODES = ("skin", "gradient", "whole")  # the shader's gill_mode: 0, 1, 2
FRONT_SAT_GAIN = 1.4  # a front texel's HSV saturation never above max(its own, this x the front target's)

# The study's E palettes (studio/Ea.jpg, Eb.jpg; their skin and accent with the study's HSV caps applied, so the
# presets are the colours he saw): E1 is the build's own paint (no picks).
PRESETS = [
    ("alien teal", {}),
    ("coral reef", {"skin": "#e39c8c", "lips": "#a2575a", "detail": "#a2575a", "detail_on": True}),
    ("lilac", {"skin": "#a99cd8", "lips": "#6c5896", "detail": "#6c5896", "detail_on": True}),
    ("honey", {"skin": "#e2c07a", "lips": "#a96e51", "detail": "#a96e51", "detail_on": True}),
    ("cobalt", {"skin": "#6c87c6", "lips": "#d48c72", "detail": "#d48c72", "detail_on": True}),
    ("sage", {"skin": "#8fb99f", "lips": "#4e7a65", "detail": "#4e7a65", "detail_on": True}),
    ("plum", {"skin": "#a07596", "lips": "#5c3a5a", "detail": "#5c3a5a", "detail_on": True}),
    ("slate", {"skin": "#7f98a8", "lips": "#c98a7e", "detail": "#c98a7e", "detail_on": True}),
]


def hexc(h: str) -> tuple:
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5))


def hexs(c) -> str:
    return "#" + "".join(f"{round(max(0.0, min(1.0, x)) * 255):02x}" for x in c)


def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _srgb(c: float) -> float:
    c = max(0.0, min(1.0, c))
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def to_oklab(c) -> tuple:
    r, g, b = (_lin(x) for x in c)
    lms = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b,
           0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b,
           0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    l, m, s = (math.copysign(abs(v) ** (1 / 3), v) for v in lms)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def from_oklab(lab) -> tuple:
    L, a, b = lab
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return tuple(_srgb(v) for v in (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
                                    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
                                    -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s))


def delta_e(c1, c2) -> float:
    """OKLab delta E."""
    return math.dist(to_oklab(c1), to_oklab(c2))


def chroma_cap(slot: str, hue_deg: float, L: float) -> float:
    cap, _, _, dark, light = RAILS[slot]
    for centre, half, k in BANDS:
        d = abs((hue_deg - centre + 180.0) % 360.0 - 180.0)
        if d < half:
            cap *= 1.0 - (1.0 - k) * 0.5 * (1.0 + math.cos(math.pi * d / half))
    if dark is not None:
        cap *= min(1.0, (L - 0.009) / (dark - 0.009))
    if light is not None:
        cap *= min(1.0, (1.0 - L) / (1.0 - light))
    return cap


def guard(slot: str, c) -> tuple:
    """One picked sRGB colour inside its slot's rails (OKLCh): the chroma capped (lower in the hue bands and past the
    knees), the lightness clamped, the hue angle kept; a colour inside the rails comes back unchanged. sRGB's gamut
    clip (a channel past 0 or 1 after the cut) may still turn the hue a little: the chroma is halved until it fits."""
    L, a, b = to_oklab(c)
    lo, hi = RAILS[slot][1:3]
    Lc = max(lo, min(hi, L))
    ch, hue = math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360.0
    cap = chroma_cap(slot, hue, Lc)
    if ch <= cap and lo <= L <= hi:
        return tuple(c)
    k = min(1.0, cap / ch) if ch > 0 else 1.0
    return _in_gamut((Lc, a * k, b * k))


def _in_gamut(lab) -> tuple:
    """OKLab to sRGB, the chroma scaled down (bisection, the hue and L kept) until every channel is inside 0-1."""
    def raw(k):
        L, a, b = lab[0], lab[1] * k, lab[2] * k
        l, m, s = ((L + 0.3963377774 * a + 0.2158037573 * b) ** 3, (L - 0.1055613458 * a - 0.0638541728 * b) ** 3,
                   (L - 0.0894841775 * a - 1.2914855480 * b) ** 3)
        return (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
                -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
                -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)
    if all(-1e-6 <= v <= 1.0 + 1e-6 for v in raw(1.0)):
        return from_oklab(lab)
    lo, hi = 0.0, 1.0
    for _ in range(20):
        k = 0.5 * (lo + hi)
        if all(-1e-6 <= v <= 1.0 + 1e-6 for v in raw(k)):
            lo = k
        else:
            hi = k
    return from_oklab((lab[0], lab[1] * lo, lab[2] * lo))


def lip_contrast(lips, skin) -> tuple:
    """The lips at least LIP_CONTRAST (OKLab) from the skin: L moved darker (lighter when darker leaves the range),
    the hue and chroma kept."""
    if delta_e(lips, skin) >= LIP_CONTRAST:
        return tuple(lips)
    L, a, b = to_oklab(lips)
    Ls, a_s, b_s = to_oklab(skin)
    dl = math.sqrt(max(0.0, LIP_CONTRAST ** 2 - (a - a_s) ** 2 - (b - b_s) ** 2)) + 0.005
    lo, hi = RAILS["lips"][1:3]
    L = Ls - dl if Ls - dl >= lo else min(hi, Ls + dl)
    return _in_gamut((L, a, b))


def recolour(c, base, target) -> tuple:
    """alien_static.gdshader's recolour on one sRGB colour: the hue turned by target - base, the saturation and value
    scaled by their ratios (sRGB HSV, as the shader does it)."""
    h, s, v = colorsys.rgb_to_hsv(*c)
    bh, bs, bv = colorsys.rgb_to_hsv(*base)
    th, ts, tv = colorsys.rgb_to_hsv(*target)
    return colorsys.hsv_to_rgb((h + th - bh) % 1.0, min(1.0, s * ts / max(bs, 1e-4)), min(1.0, v * tv / max(bv, 1e-4)))


def front_for(skin, base_skin, front_base) -> tuple:
    """The pale front for a picked skin: the build's front recoloured with the skin, kept a tinted cream."""
    return guard("front", recolour(front_base, base_skin, skin))


def _pick(v):
    return hexc(v) if isinstance(v, str) else tuple(v)


def slot_colours(bases: dict, picks: dict) -> dict:
    """The shader's colour uniforms (sRGB) for a head. bases: the build's own colours, {"skin" (the GLB's
    base_skin_srgb), "lips", "detail", "front" (the accent JSON's region medians)}; picks: any of "skin", "lips",
    "detail" (sRGB or "#rrggbb"), "detail_on" (default: true when "detail" is picked), "gills" (GILL_MODES, default "gradient").
    No picks: every target is its base, the identity."""
    base = tuple(bases["skin"])
    out = {"base_skin": base, "lip_base": tuple(bases["lips"]), "detail_base": tuple(bases["detail"]),
           "front_base": tuple(bases["front"])}
    skin = guard("skin", _pick(picks["skin"])) if "skin" in picks else base
    out["skin_color"] = skin
    if "skin" in picks:
        out["front_color"] = front_for(skin, base, out["front_base"])
        hs = colorsys.rgb_to_hsv(*out["front_color"])[1]
        out["front_sat_max"] = min(1.0, FRONT_SAT_GAIN * hs)
    else:
        out["front_color"], out["front_sat_max"] = out["front_base"], 1.0
    if "lips" in picks:
        out["lip_color"] = lip_contrast(guard("lips", _pick(picks["lips"])), skin)
    else:  # the build's lips, following a picked skin as its paint does
        out["lip_color"] = recolour(out["lip_base"], base, skin)
    on = bool(picks.get("detail_on", "detail" in picks))
    if "detail" in picks:
        out["detail_color"] = guard("detail", _pick(picks["detail"]))
    else:  # the build's marks, following a picked skin
        out["detail_color"] = recolour(out["detail_base"], base, skin)
    out["detail_on"] = 1.0 if on else 0.0
    out["gill_mode"] = float(GILL_MODES.index(picks.get("gills", "gradient")))
    return out
