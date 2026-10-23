"""The alien pilot's static heads (art #196): the player's colour slots, plain Python. The same maths lives in
godot/alien/alien_static.gd (`slot_colours`) and tools/web/alien_colour/colour.js (`slotColours`); the per-texel
recolour (`texel` here) in alien_static.gdshader's `recolour` and colour.js's GLSL. Their uniforms are checked against
this file: the JS by test_alien_colour_slots.py (node, within 1e-6), the GDScript by test_alien_parse_godot.py
(headless Godot, a heavy test, within 1e-5) and by the proof's every cell (alien_colour_slots.py).

Slots, each an sRGB colour the player picks, applied as picked (CS6, the engineer 2026-10-23: "the player chooses;
maybe he wants it acidic, it's his choice"; no guard rails since):
- skin: every skin texel follows it;
- lips: the lips (the accent mask's R) in their own colour;
- detail: the marks (the accent's G: the chameleon's crest stripes, the axolotl's freckles and gills) in their own
  colour when `detail_on`; off, they follow the skin as the build's paint does;
- gills (the axolotl, with the details on): "gradient" (the default: the accent's G, skin at the gill's root to the
  details colour at its tips), "whole" (the whole gill, stalk and fringe: `<head>_gill.png`) or "skin"; any other
  value is an error (ValueError here; colour.js throws, alien_static.gd push_errors and returns {});
- the pale front (the accent's B) is no slot but a derived colour (CS6b), by the picks' "front" (FRONT_MODES):
  "keep" (the default) keeps the panel's two-tone against the skin, pale on dark skins and a little darker than a
  very light skin (`front_for`), "follow" follows the skin down and up; either a tinted cream (its chroma never
  above the build's front's).

The recolour (CS6, `shift`): each region has a base, the median (OKLab, per component) of its painted texels
(`bases_from_texels`, REGIONS), and a target; a texel keeps its offset from the base, carried onto the target in
OKLab: the lightness offset scaled down where the target has less room (above it toward white, below it toward
black), the a/b offset turned by the hue turn and scaled down when the target has less chroma than the base; on a
target darker than the base every offset is scaled by the lightness ratio too (CS6b: the paint's mottling relative,
not absolute, so a dark pick is not blotchy). The base texel becomes the target; over a region the recoloured
median is within the albedo table's dE of the pick (CS6b: 0.003 at most where the shifted texels stay inside the
sRGB gamut; a pick on the gamut's edge, e.g. #ff00ff, up to 0.009 on the skin: the per-channel clamp moves its
lighter texels, and a clip toward the pick, tried, made the median exact but flattened every such texel onto the
pick), and a target at its base is the identity. v1-v5 turned the hue and scaled
sRGB HSV saturation and value by the target/base ratios, from one detail base for the freckles, the crest and the
gills alike, after guard rails on every pick; the rails made a picked detail miss (#ffee00 became #d9d7b1: the
details' lightness cap 0.871, the light knee and the yellow-green band cut its chroma from 0.197 to 0.050).
"""
from __future__ import annotations

import math

GILL_MODES = ("skin", "gradient", "whole")  # the shader's gill_mode: 0, 1, 2
FRONT_MODES = ("keep", "follow")  # the pale front (CS6b): keep its two-tone against the skin, or follow it
# The regions whose medians are the bases (`bases_from_texels`): 8-bit thresholds on the masks; every texel in the
# skin mask (R >= SKIN_GATE)
SKIN_GATE = 230
UNPAINTED = 8 / 255  # an albedo texel this dark in every channel is no paint (the atlas' gaps): never in a median
REGIONS = {"skin": "no accent, no gill (all under 13)", "lips": "accent R >= 230",
           "front": "accent B >= 230, G under 25, not lips", "detail": "accent G >= 230, gill under 25, not lips",
           "gill_tips": "gill >= 230 and accent G >= 230 (the gradient's tips)", "gill_whole": "gill >= 230"}

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




def _lab_lin(c) -> tuple:
    """OKLab from linear sRGB (the shader's albedo and uniforms are linear)."""
    r, g, b = c
    lms = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b,
           0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b,
           0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    l, m, s = (math.copysign(abs(v) ** (1 / 3), v) for v in lms)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def shift(x, b, t) -> tuple:
    """One texel x (OKLab) from its region's base b to the target t: its offset from b carried onto t. kr =
    min(1, L_t / L_b) (CS6b: relative on a darker target); the lightness offset scaled by kr, a lighter texel's also
    by the room toward white (min(kr, (1 - L_t) / (1 - L_b))); the a/b offset turned by the hue turn b -> t and
    scaled by min(1, C_t / C_b) * kr. shift(b, b, t) == t; shift(x, b, b) == x."""
    dl = x[0] - b[0]
    kr = min(1.0, t[0] / max(b[0], 1e-4))
    kl = min(kr, (1.0 - t[0]) / max(1.0 - b[0], 1e-4)) if dl > 0.0 else kr
    cb, ct = math.hypot(b[1], b[2]), math.hypot(t[1], t[2])
    co, si = 1.0, 0.0
    if cb > 1e-4 and ct > 1e-4:
        co, si = (b[1] * t[1] + b[2] * t[2]) / (cb * ct), (b[1] * t[2] - b[2] * t[1]) / (cb * ct)
    kc = min(1.0, ct / max(cb, 1e-4)) * kr
    da, db = x[1] - b[1], x[2] - b[2]
    return (t[0] + dl * kl, t[1] + (da * co - db * si) * kc, t[2] + (da * si + db * co) * kc)


def _lab_rgb(lab) -> tuple:
    """OKLab to linear sRGB, unclipped."""
    L, a, b = lab
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)


def recolour(c, base, target) -> tuple:
    """`shift` on one sRGB colour (sRGB in and out, clamped to the gamut)."""
    return from_oklab(shift(to_oklab(c), to_oklab(base), to_oklab(target)))


def front_for(skin, base_skin, front_base, mode: str = "keep") -> tuple:
    """The pale front for a picked skin: the build's front shifted with the skin, its chroma never above the build's
    front's (a tinted cream, the panel's design; no slot of its own). "follow": that colour. "keep" (CS6b): its
    lightness at least the build's front's, then at least the build's two-tone (d = L_front_base - L_base_skin, the
    painted default) away from the skin's: above it where the colour there is inside the sRGB gamut, else below it.
    A skin at its base gives the build's front in both modes."""
    L, a, b = shift(to_oklab(front_base), to_oklab(base_skin), to_oklab(skin))
    fb, ls = to_oklab(front_base), to_oklab(skin)[0]
    cf, c = math.hypot(fb[1], fb[2]), math.hypot(a, b)
    k = min(1.0, cf / c) if c > 0.0 else 1.0
    if mode == "keep":
        d = fb[0] - to_oklab(base_skin)[0]
        L = max(L, fb[0])
        if abs(L - ls) < d - 1e-6:
            up = _lab_rgb((ls + d, a * k, b * k))
            L = ls + d if min(up) >= -1e-6 and max(up) <= 1.0 + 1e-6 else ls - d
    return from_oklab((L, a * k, b * k))


def _pick(v):
    return hexc(v) if isinstance(v, str) else tuple(v)


def slot_colours(bases: dict, picks: dict) -> dict:
    """The shader's colour uniforms (sRGB) for a head. bases: the build's own colours, {"skin", "lips", "detail",
    "front"} and, on a head with gills, "gill_tips" and "gill_whole" (the regions' medians, `bases_from_texels`;
    missing gill bases are the detail base); picks: any of "skin", "lips", "detail" (sRGB or "#rrggbb", applied as
    picked), "detail_on" (default: true when "detail" is picked), "gills" (GILL_MODES, default "gradient"),
    "front" (FRONT_MODES, default "keep"). No picks: every target is its base, the identity."""
    gills = picks.get("gills", "gradient")
    if gills not in GILL_MODES:
        raise ValueError(f"unknown gills {gills!r} (one of {', '.join(GILL_MODES)})")
    front = picks.get("front", "keep")
    if front not in FRONT_MODES:
        raise ValueError(f"unknown front {front!r} (one of {', '.join(FRONT_MODES)})")
    base = tuple(bases["skin"])
    gb = tuple(bases.get("gill_whole" if gills == "whole" else "gill_tips", bases["detail"]))
    out = {"base_skin": base, "lip_base": tuple(bases["lips"]), "detail_base": tuple(bases["detail"]),
           "gill_base": gb, "front_base": tuple(bases["front"])}
    skin = _pick(picks["skin"]) if "skin" in picks else base
    out["skin_color"] = skin
    out["front_color"] = front_for(skin, base, out["front_base"], front) if "skin" in picks else out["front_base"]
    # a slot left out: the build's paint there, following a picked skin as its paint does
    out["lip_color"] = _pick(picks["lips"]) if "lips" in picks else (
        recolour(out["lip_base"], base, skin) if "skin" in picks else out["lip_base"])
    for k, b in (("detail_color", out["detail_base"]), ("gill_color", gb)):
        out[k] = _pick(picks["detail"]) if "detail" in picks else (
            recolour(b, base, skin) if "skin" in picks else b)
    out["detail_on"] = 1.0 if bool(picks.get("detail_on", "detail" in picks)) else 0.0
    out["gill_mode"] = float(GILL_MODES.index(gills))
    return out


def _mix(p, q, w) -> tuple:
    return tuple(x + (y - x) * w for x, y in zip(p, q))


def texel(c, acc, gill: float, u: dict) -> tuple:
    """alien_static.gdshader's recolour on one sRGB albedo texel (sRGB out): acc the accent (lips, details, front;
    0-1), gill the whole gills' weight, u slot_colours' uniforms. The shader gets the albedo and the uniforms linear
    and mixes the regions in OKLab; so does this."""
    lin = lambda k: tuple(_lin(v) for v in u[k])  # noqa: E731
    lab = lambda k: _lab_lin(lin(k))  # noqa: E731
    x = to_oklab(c)
    t = shift(x, lab("base_skin"), lab("skin_color"))
    t = _mix(t, shift(x, lab("front_base"), lab("front_color")), acc[2])
    gm = u["gill_mode"]
    dw = max(acc[1] - gill, 0.0) if gm < 0.5 else (acc[1] if gm < 1.5 else max(acc[1], gill))
    db = _lab_lin(_mix(lin("detail_base"), lin("gill_base"), gill))
    dt = _lab_lin(_mix(lin("detail_color"), lin("gill_color"), gill))
    t = _mix(t, shift(x, db, dt), u["detail_on"] * dw)
    t = _mix(t, shift(x, lab("lip_base"), lab("lip_color")), acc[0])
    return from_oklab(t)


def region_of(acc8, gill8: int) -> list:
    """The regions (REGIONS) one skin texel counts in, from its 8-bit accent (R, G, B) and gill weight."""
    ar, ag, ab = acc8
    out = []
    if gill8 >= 230:
        out.append("gill_whole")
        if ag >= 230:
            out.append("gill_tips")
    if ar >= 230:
        out.append("lips")
    elif ab >= 230 and ag < 25:
        out.append("front")
    elif ag >= 230 and gill8 < 25:
        out.append("detail")
    elif max(acc8) < 13 and gill8 < 13:
        out.append("skin")
    return out


def median_lab(cols) -> tuple:
    """The per-component OKLab median of sRGB colours, as sRGB."""
    labs = [to_oklab(c) for c in cols]
    n = len(labs) // 2
    return from_oklab(tuple(sorted(v[k] for v in labs)[n] for k in range(3)))


def bases_from_texels(texels) -> dict:
    """The bases (`slot_colours`) from a head's skin texels [(albedo sRGB 0-1, accent 8-bit RGB, gill 8-bit)]: each
    region's median; a head without gills gets the detail median for both gill bases, a head without details outside
    the gills the gill tips' (else the skin's) for its details."""
    by: dict = {k: [] for k in REGIONS}
    for c, acc, g in texels:
        if max(c) < UNPAINTED:  # the atlas' unpainted gaps inside the skin mask (a quarter of the axolotl's)
            continue
        for k in region_of(acc, g):
            by[k].append(c)
    out = {k: median_lab(v) for k, v in by.items() if v}
    out.setdefault("detail", out.get("gill_tips", out["skin"]))
    for k in ("gill_tips", "gill_whole"):
        out.setdefault(k, out["detail"])
    return out
