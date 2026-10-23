"""The alien pilot's static heads (art #196): the player's colour slots, plain Python. The same maths lives in
godot/alien/alien_static.gd (`slot_colours`, `guard`) and tools/web/alien_colour/colour.js (`slotColours`, `guard`);
test_alien_colour_slots.py checks all three against this file.

Slots, each an sRGB colour the player picks:
- skin: every skin texel follows it (hue turned, saturation and value scaled from the build's `base_skin`);
- lips: the lips (the accent mask's R) in their own colour;
- detail: the marks (the accent's G: the chameleon's crest stripes, the axolotl's freckles and gills) in their own
  colour when `detail_on`; off, they follow the skin as the build's paint does;
- gills_detail (the axolotl): the gills (the accent's A, 1 - gill) take the detail colour (default) or the skin's;
- the pale front (the accent's B) is no slot: it follows the skin as a tinted cream (study variant E).

Guard rails, in CIELAB (D65), on every picked colour (a slot the player leaves out keeps the build's own paint, the
approved look, never guarded): a chroma cap and a lightness range per slot, the cap lowered round the yellow-green
hues (ACID: they read acidic at a chroma the others carry), and the lips at least LIP_CONTRAST (CIE76 delta E) from
the skin (moved darker in L*, or lighter when darker leaves the range). The recolour itself runs in sRGB HSV, in the
shader too (it converts the linear albedo to sRGB and back), so every cap is in one space.
"""
from __future__ import annotations

import colorsys
import math

# per slot: (chroma cap C*, L* min, L* max)
RAILS = {"skin": (40.0, 35.0, 85.0), "lips": (42.0, 25.0, 80.0), "detail": (42.0, 20.0, 85.0),
         "front": (16.0, 82.0, 93.0)}
ACID = (125.0, 35.0, 0.7)  # the yellow-green band: its centre and half width (CIELAB hue degrees), the cap's factor
LIP_CONTRAST = 12.0  # CIE76 delta E, lips against the skin
FRONT_SAT_GAIN = 1.4  # a front texel's HSV saturation never above max(its own, this x the front target's)
WHITE = (0.95047, 1.0, 1.08883)

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


def _f(t: float) -> float:
    return t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116


def _finv(t: float) -> float:
    return t ** 3 if t ** 3 > 216 / 24389 else (116 * t - 16) / (24389 / 27)


def to_lab(c) -> tuple:
    r, g, b = (_lin(x) for x in c)
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / WHITE[0]
    y = (0.2126729 * r + 0.7151522 * g + 0.0721750 * b) / WHITE[1]
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / WHITE[2]
    fx, fy, fz = _f(x), _f(y), _f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def from_lab(lab) -> tuple:
    L, a, b = lab
    fy = (L + 16) / 116
    x, y, z = _finv(fy + a / 500) * WHITE[0], _finv(fy) * WHITE[1], _finv(fy - b / 200) * WHITE[2]
    r = 3.2404542 * x - 1.5371385 * y - 0.4985314 * z
    g = -0.9692660 * x + 1.8760108 * y + 0.0415560 * z
    bl = 0.0556434 * x - 0.2040259 * y + 1.0572252 * z
    return tuple(_srgb(v) for v in (r, g, bl))


def delta_e(c1, c2) -> float:
    return math.dist(to_lab(c1), to_lab(c2))


def chroma_cap(slot: str, hue_deg: float) -> float:
    cap = RAILS[slot][0]
    centre, half, k = ACID
    d = abs((hue_deg - centre + 180.0) % 360.0 - 180.0)
    if d < half:
        cap *= 1.0 - (1.0 - k) * 0.5 * (1.0 + math.cos(math.pi * d / half))
    return cap


def guard(slot: str, c) -> tuple:
    """One picked sRGB colour inside its slot's rails: the chroma capped (lower in the yellow-green band), the
    lightness clamped; a colour inside the rails comes back unchanged."""
    L, a, b = to_lab(c)
    cmax, lo, hi = RAILS[slot]
    ch, hue = math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360.0
    cap = chroma_cap(slot, hue)
    if ch <= cap and lo <= L <= hi:
        return tuple(c)
    k = min(1.0, cap / ch) if ch > 0 else 1.0
    return from_lab((max(lo, min(hi, L)), a * k, b * k))


def lip_contrast(lips, skin) -> tuple:
    """The lips at least LIP_CONTRAST from the skin: L* moved darker (lighter when darker leaves the range)."""
    if delta_e(lips, skin) >= LIP_CONTRAST:
        return tuple(lips)
    L, a, b = to_lab(lips)
    Ls, a_s, b_s = to_lab(skin)
    dl = math.sqrt(max(0.0, LIP_CONTRAST ** 2 - (a - a_s) ** 2 - (b - b_s) ** 2)) + 0.5
    lo, hi = RAILS["lips"][1:]
    L = Ls - dl if Ls - dl >= lo else min(hi, Ls + dl)
    return from_lab((L, a, b))


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
    "detail" (sRGB or "#rrggbb"), "detail_on" (default: true when "detail" is picked), "gills_detail" (default true).
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
    out["gills_detail"] = 1.0 if picks.get("gills_detail", True) else 0.0
    return out
