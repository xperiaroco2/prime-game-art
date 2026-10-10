"""The clay face kit's data and its pure-Python rules (no bpy): the features (colours, eyes, brows, noses, ears,
mouths, facial hair) and the pick rules from faces/clay_kit.json, the per-hair flags from faces/clay_hair.json, the
builder's tuning constants, and the picks, colours and ear states (docs/faces.md, "The clay face kit").

Ported from the faces lab's round E kit (D:/prime-art-raw/research/2026-10-05-faces/lab/clay_e/clay_face_b.py, the data section and its helpers).
The runner and the tests import this module; the Blender modules of this package read the same names.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
KIT_FILE = ROOT / "faces" / "clay_kit.json"
HAIR_FILE = ROOT / "faces" / "clay_hair.json"
HEAD_FILE = ROOT / "faces" / "clay_head.json"  # the bean head the features sit on (art #42)


def _tup(v):
    """JSON to the kit's Python shapes: a list of numbers becomes a tuple (a vector or a range); dicts recurse."""
    if isinstance(v, dict):
        return {k: _tup(x) for k, x in v.items()}
    if isinstance(v, list):
        items = [_tup(x) for x in v]
        if items and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in items):
            return tuple(items)
        return items
    return v


def load(path=KIT_FILE):
    return _tup(json.loads(Path(path).read_text(encoding="utf-8")))


KIT = load()
HAIR_ITEMS = json.loads(HAIR_FILE.read_text(encoding="utf-8"))["items"]
HEAD = load(HEAD_FILE)  # nose_flatten, bean (heads.bean_warp), rigid_margin, in the lab's order
# the kit's data in the clay library's piece keys (claylook.keys_for): a changed feature, hair flag or head re-bakes the faces
HEAD_SHA = hashlib.sha256(HEAD_FILE.read_bytes()).hexdigest()[:16]  # the hair and extras follow the head: in their keys
DATA_SHA = hashlib.sha256(KIT_FILE.read_bytes() + HAIR_FILE.read_bytes() + HEAD_FILE.read_bytes()).hexdigest()[:16]

# ----------------------------------------------------------------------------------------------- the features (data)
SKINS = KIT["colours"]["skins"]  # the lab's clay skins (linear); a character's skin is any RGB (skin_key picks the tint)
TINT = KIT["colours"]["tint"]  # multipliers on the skin's linear RGB per skin key: nose, lip, crease
FIXED = KIT["colours"]["fixed"]  # eye white, pupil, mouth cavity, teeth
GLOSS = KIT["colours"]["gloss"]  # roughness of the glossy pieces
BROW_RGB = KIT["colours"]["brow_default"]  # the brow of a face built without a brow colour, per skin key
HAIR_RGB = KIT["colours"]["hair_default"]
BROW_COLOURS = KIT["colours"]["brow_palette"]
EYE_SIZES = KIT["eyes"]["sizes"]  # radius; both eyes always the same size
LOUD_EYE_R = KIT["eyes"]["loud_radius"]
PUPILS = KIT["eyes"]["pupils"]  # half width, half height / eye radius
LIDS = KIT["eyes"]["lids"]  # the resting upper lid's edge, deg above the eye centre
LOOK = KIT["eyes"]["look"]
BROWS = KIT["brows"]["styles"]
NOSES = KIT["noses"]["styles"]
NOSE_SCALE = KIT["noses"]["scale"]
EARS = KIT["ears"]["styles"]
MOUTHS = KIT["mouths"]["styles"]
STATES = tuple(KIT["mouths"]["states"])
FACIAL_HAIR = KIT["facial_hair"]["styles"]
ASYM = KIT["picks"]["asym"]
WEIGHTS = {cat: {(True if k == "true" else k): w for k, w in t.items()} for cat, t in KIT["picks"]["weights"].items()}
LOUD = {cat: set(v) for cat, v in KIT["picks"]["loud"].items()}
LOUD_WEIGHTS = KIT["picks"]["loud_weights"]
LOUD_SCALE = KIT["picks"]["loud_scale"]
RULES = KIT["picks"]["rules"]
DEFAULTS = KIT["picks"]["defaults"]
SMILING_AT_REST = set(KIT["picks"]["smiling_at_rest"])
VISIBLE_SMILE = set(KIT["picks"]["visible_smile"])
MASK_UV = KIT["mask"]["uv"]  # the mask UV layer (glTF TEXCOORD_1 after the atlas UV)
MASK = KIT["mask"]["values"]  # brows (1, 0), facial hair (0, 1), the rest (0, 0)
PICKS = {"mouth": list(MOUTHS), "nose": list(NOSES), "eye_size": list(EYE_SIZES), "pupil": list(PUPILS),
         "lid": list(LIDS), "brows": list(BROWS), "ears": list(EARS), "facial_hair": list(FACIAL_HAIR),
         "teeth": [True], "asym": list(ASYM)}
# ----------------------------------------------------------------------------------------------- per-hair flags
# Per hair and headwear item (catalogue ids, faces/clay_hair.json): (ears free where they are, ears free tucked).
EAR_RULES = {iid: tuple(v["ears_free"]) for iid, v in HAIR_ITEMS.items()}
COVERS_EARS = {k for k, (f, b) in EAR_RULES.items() if not f and not b}
# The hairs whose hanging locks the brows are tucked behind (an item not listed tucks: a no-op where no lock hangs).
BROW_TUCK_HAIRS = {iid for iid, v in HAIR_ITEMS.items() if v.get("brow_tuck", True)}
NO_BROW_TUCK = {iid for iid, v in HAIR_ITEMS.items() if not v.get("brow_tuck", True)}
HAIR_BROW_FORBID = {}  # brief3's forbid rule is gone (the engineer chose the tuck): every hair x brow pair is allowed


def hair_item(spec, gender=None):
    """The catalogue id of a recipe's hair or headwear spec ({file, object, materials}; the pack of its `gender`, else
    of the character's gender), or the spec's own `item`, or None."""
    if spec is None:
        return None
    if spec.get("item"):
        return spec["item"]
    mats = sorted(spec.get("materials") or [])
    g = spec.get("gender") or gender
    for iid, v in HAIR_ITEMS.items():
        if (v.get("file"), v.get("object"), sorted(v.get("materials") or [])) == (spec.get("file"), spec.get("object"), mats)                 and (g is None or v.get("body_type") == g):
            return iid
    return None


def hair_flags(*items):
    """The face flags the worn items set, as the game applies them: {"ears": "free" | "tuck" | "hide",
    "brow_tuck": bool}. items: catalogue ids (None skipped); an unknown item leaves the ears free and tucks."""
    worn = [i for i in items if i]
    return {"ears": ear_state(*worn), "brow_tuck": not any(i.split("@")[0] in NO_BROW_TUCK for i in worn)}


LAYOUT = {"eye_dz": -0.006, "eye_gap": -0.002, "eye_embed": 0.12, "eye_mouth": 0.072, "brow_gap": -0.003,
          "brow_lift": 0.004, "nose_clear": 0.002, "moustache_clear": 0.0008}


# Round E fix (2026-10-09, brief2 FIX 1): the goatee hangs this far under the lower lip (was 1.5 mm: it read as a
# separate lump in the front view); settle_goatee still lowers it off every mouth and teeth state.
GOATEE_LIP_GAP = 0.0005


EYEBALL = {"white_seg": 16, "white_rings": 8, "pupil_seg": 16, "pupil_rings": 3, "pupil_lift": 0.0002,
           "pupil_lift_frac": 0.03, "lid_scale": 1.05, "lid_lo_scale": 1.04, "lid_seg": 12, "lid_rings": 3,
           "lo_seg": 8, "lo_rings": 3, "lid_line_rad": 0.2, "lid_back_margin": 0.3, "closed_edge": -10.0,
           "lo_edge": -100.0, "closed_overlap": 6.0}


# Iterator round 1: the library clay head is 5 % wider at nose level than wave A's head (measured: 0.217 against
# 1.3 x 0.159 m), so the kit's nose and mouth read 5 and 8 % smaller on it than on wave A's man: both scale back.
NOSE_K, MOUTH_K = 1.05, 1.06


LIP_W, LIP_H, FLOOR = 0.006, 0.0085, 0.0014  # wave A's thicker lip roll (ITER lip_w, lip_h)


MOUTH_N = 8  # outline segments per lip half: 2 * MOUTH_N points round the mouth


# the lip sausage's cross-section: (offset along the outline's outward normal in lip widths, lift off the skin in lip
# heights), from the outer edge (sunk 0.1 into the skin) over the top of the roll to its inner side over the cavity
PROFILE = ((1.0, -0.1), (0.78, 0.6), (0.38, 0.95), (-0.05, 0.92), (-0.3, 0.55))


TAPER, TUCK = 0.5, 0.65  # at the corners the lip is 50 % as wide and 35 % as high (it tucks into the cheek)


TOOTH_SEG = 8


LOUD_BROW_HH = 1.15  # a loud brow's height factor (no brow is loud in round C; kept for the code path)


BROW_GAP_K = 1.0  # the gap between the two brows' inner ends is at least this x the brow's full height (2 hh)


BROW_HAIR_CLEAR = 0.004  # a brow's top edge stays this far under the fringe / hairline above it


# round E fix 2 (brief3): a brow never pokes out of a lock (build_brows, hair_lock_test)
BROW_LOCK_SAMPLES = 41  # stations tested along the brow's length


BROW_LOCK_DROP = 0.006  # the most a brow is lowered under a lock (the lid gap below still wins)


BROW_LOCK_MIN_LEN = 0.45  # a brow shortened under locks keeps at least this share of its length, else it cannot fit


BROW_LOCK_BEHIND = 0.008  # hair this close behind a visible brow point is a poke (the check's test)


BROW_LOCK_PAD = 0.0005  # the lock test's brow is this much taller than the built one


BROW_LOCK_LID_MARGIN = 0.002  # a lowered brow's lower edge stays this far above the lid gap (the rounded mesh sags)


# Round E fix 3 (brief5): a brow under a hanging lock is TUCKED (tuck_brows): every point of the built brow that pokes
# out of the hair (the check's test: seen from the front with hair right behind it) is pressed back in depth, along
# -FWD only, until it sits BROW_TUCK_CLEAR behind that hair surface; the brow keeps its length, height and place, and
# where no lock covers it nothing moves. Like the ears' COVERS_EARS, a per-hair flag: BROW_TUCK_HAIRS lists the hairs
# whose locks hang over the brows (None = every hair; the tuck is a no-op under a hair that covers no brow).
BROW_TUCK_CLEAR = 0.0005  # a tucked point sits this far behind the hair surface it poked out of


BROW_TUCK_BEHIND = 0.008  # hair this close behind a visible brow point is a poke (the check's test)


BROW_TUCK_MAX = 0.015  # the most a vertex is pressed back


BROW_TUCK_ROUNDS = 12  # rounds of the seal (vertices, triangle centres and edge midpoints) until nothing pokes


# step 2 (brief5): hair that lies under the skin (the hair cap's front surface behind a high brow) is covered by the
# skin, so a brow in front of it is on visible skin, not out of a lock: the tuck ignores hair hits deeper than this
# under the skin, and a brow point under the skin is hidden (no need to press it). None = the step-1 tuck.
BROW_TUCK_SKIN_TOL = 0.0005


BROW_PAD_CAP = False  # manager 2026-10-10: off (e5 cap erased brows on 164 m / 174 w faces); e4 behaviour  # brief6: no brow station rises above the top of the stations fitted under the hair


BROW_PAD_HH_MIN = 0.3  # a capped station keeps at least this share of its half height (then it is lowered)


BROW_PAD_TOL = 0.0005  # brow_above_pad: a brow vertex this far over the pad's top edge counts


def hair_brow_ok(hair, picks):
    """False for a hair x brow pair whose brow cannot fit under the hair's locks (HAIR_BROW_FORBID)."""
    return picks.get("brows") not in HAIR_BROW_FORBID.get(hair, ())


EAR_SEG = (16, 10)  # the sphere of an ear with a dent (u segments, rings); without one: (10, 6) as in round C


EAR_HIDE = {"inward": 0.008, "shrink": 0.15}  # ears_hide: each ear shrinks to 15 % about its centre moved 8 mm further in


# Fixer, round D: ears_tuck, a second shape key: each ear scaled EAR_TUCK["scale"] about its root on the skin and moved
# EAR_TUCK["back"] backwards and EAR_TUCK["down"] down along the head's side (x follows the side's surface). It exists
# for the women's punk mohawk, whose low side edge and sideburn flap lie over the top of the round D ear while the
# shaved side below is bare: folded in, the ear left her side looking earless. Measured (face_sheets earprobe, x1.3):
# scale 0.85, 8 mm back, 12 mm down is the least change that clears the mohawk (0 overlaps, 0 pokes, 2.3 mm clear),
# and the ear still stands 10.7 mm out of the skin (12.5 at full size; round B's small ear 7.9). Units here: unscaled.
EAR_TUCK = {"scale": 0.8, "back": 0.008 / 1.3, "down": 0.015 / 1.3}


EAR_KEY_NAMES = ("ears_hide", "ears_tuck")


EAR_KEYS = {"free": {"ears_hide": 0.0, "ears_tuck": 0.0}, "tuck": {"ears_hide": 0.0, "ears_tuck": 1.0},
            "hide": {"ears_hide": 1.0, "ears_tuck": 0.0}}


def ear_state(*items):
    """"free", "tuck" or "hide" for the worn hair and headwear ids (with or without their @M / @W suffix)."""
    rules = [EAR_RULES.get(i.split("@")[0], (True, True)) for i in items if i]
    if all(r[0] for r in rules):
        return "free"
    if all(r[1] for r in rules):
        return "tuck"
    return "hide"


def covers_ears(*items):
    """True when the worn hair and headwear hide the ears (ear_state "hide")."""
    return ear_state(*items) == "hide"


EAR_POS = {"y": -0.035, "dz": -0.019}  # round B's spot: y (world, unscaled), z below the eye centre


# brows are the dark brow colour, except under white or grey hair: then a light cool grey that still reads on a medium
# skin (note 4; contrasts in colour_checks)
BROW_GREY = (0.56, 0.58, 0.62)


def nose_loud(picks):
    """Round E: always False (the nose is never loud); kept for callers."""
    return picks.get("loud") == "nose" and picks.get("nose") in LOUD.get("nose", ())


def nose_axes(picks, t=1.0):
    """(kx, ky, kz): NOSE_K x the loud nose's growth per axis at loudness t (1 full, 0 quiet size); a quiet nose NOSE_K."""
    return (NOSE_K * NOSE_SCALE.get(picks["nose"], 1.0),) * 3  # round E: one size per nose, never loud


def nearest_brow(hair_rgb):
    """The BROW_COLOURS entry nearest the hair colour (sRGB distance): the cast's "match" brows."""
    h = srgb(hair_rgb)
    return min(BROW_COLOURS, key=lambda k: sum((a - b) ** 2 for a, b in zip(srgb(BROW_COLOURS[k]), h)))


BROW_MATCH_SHARE = 0.7  # random faces: brows that match the hair this often, a free palette pick otherwise


def random_brow(rng, hair_rgb, share=BROW_MATCH_SHARE):
    """A generated face's brow colour (fixer, round D): mostly the colour nearest the hair (independent brows on every
    random face looked dyed), otherwise any palette colour. The player still picks any combination."""
    if rng.random() < share:
        return nearest_brow(hair_rgb)
    return sorted(BROW_COLOURS)[rng.randrange(len(BROW_COLOURS))]


def loud_k(picks, cat):
    """The loud scale of a category for these picks (1.0 unless it is the face's loud feature with a loud value)."""
    if picks.get("loud") == cat and picks.get(cat) in LOUD.get(cat, ()):
        return LOUD_SCALE.get(cat, 1.0)
    return 1.0


def lum(rgb):
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def mul(a, b):
    return tuple(x * y for x, y in zip(a, b))


def skin_rgb(skin):
    return tuple(SKINS[skin]) if isinstance(skin, str) else tuple(skin)


def skin_key(skin):
    """The tint table entry for a skin: its name, or the nearer of light / dark by luminance for an RGB."""
    if isinstance(skin, str):
        return skin
    return "dark" if lum(skin) < (lum(SKINS["light"]) + lum(SKINS["dark"])) / 2 else "light"


def weighted(rng, table, allowed=None):
    items = [(k, w) for k, w in table.items() if (allowed is None or k in allowed) and w > 0]
    tot = sum(w for _, w in items)
    r = rng.uniform(0.0, tot)
    for k, w in items:
        r -= w
        if r <= 0:
            return k
    return items[-1][0]


def forbidden(p):
    for a, va, b, vb in RULES["forbid"]:
        if p.get(a) == va and p.get(b) == vb:
            return True
    return False


def random_picks(rng, gender, loud=None, ears_visible=True):
    """One face's picks: exactly one loud feature (LOUD), the rest quiet, weighted (WEIGHTS), within RULES.
    ears_visible: False when the character's hair covers the ears (then the ears cannot be its loud feature)."""
    for _ in range(200):
        cats = {k: v for k, v in LOUD_WEIGHTS.items() if not (k == "facial_hair" and gender not in RULES["facial_hair_bodies"])
                and not (k == "ears" and not ears_visible)}
        lc = loud or weighted(rng, cats)
        p = {}
        for cat, table in WEIGHTS.items():
            if cat == "facial_hair" and gender not in RULES["facial_hair_bodies"]:
                p[cat] = "none"
                continue
            loud_set = LOUD.get(cat, set())
            # round D: both noses may be loud; a quiet nose is either one at its quiet size
            allowed = loud_set if cat == lc else ([k for k in table if k not in loud_set] or list(table))
            p[cat] = weighted(rng, table, allowed)
        if p["mouth"] in RULES["teeth_forced"]:
            p["teeth"] = RULES["teeth_forced"][p["mouth"]]
        p["loud"] = lc
        if not forbidden(p):
            return p
    raise RuntimeError("no allowed picks found")


def default_picks(gender, **kw):
    """Wave A's face (round D: the bulb on both; the potato is gone), with kw changed."""
    p = dict(DEFAULTS[gender])
    p.update(kw)
    return p


FHAIR_LIFT = 1.13  # facial hair is the hair colour lifted 13 % in display value (sRGB), and never below sRGB 0.17


def fhair_rgb(rgb):
    """Iterator round 2 (the look critic: a near-black goatee read as a bead): the hair colour lifted in display value."""
    srgb = [(1.055 * c ** (1 / 2.4) - 0.055) if c > 0.0031308 else c * 12.92 for c in rgb]
    k = FHAIR_LIFT
    mx = max(srgb)
    if mx * k < 0.17:
        k = 0.17 / max(mx, 1e-4)
    out = [min(1.0, c * k) for c in srgb]
    return tuple(((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92 for c in out)


def srgb(rgb):
    return tuple((1.055 * c ** (1 / 2.4) - 0.055) if c > 0.0031308 else c * 12.92 for c in rgb)


def grey_hair(rgb):
    """White or grey hair: low chroma and light in display values (sRGB): max - min < 0.12 and max > 0.35."""
    d = srgb(rgb)
    return max(d) - min(d) < 0.12 and max(d) > 0.35


def brow_rgb(key, hair_rgb=None, brow=None):
    """Round D (note 2): the brow colour is its own parameter (brow); without one the dark brow of the skin. The hair
    colour no longer matters (hair_rgb is ignored: round C's grey-under-grey-hair rule is gone)."""
    return tuple(brow) if brow is not None else BROW_RGB[key]


def contrast(a, b):
    la, lb = lum(a), lum(b)
    return round((max(la, lb) + 0.05) / (min(la, lb) + 0.05), 2)


def colour_checks():
    """The nose must never be darker than the skin (luminance), on both skins."""
    out = {}
    for s, rgb in SKINS.items():
        nose = mul(rgb, TINT["nose"][s])
        out[s] = {"skin_lum": round(lum(rgb), 4), "nose_lum": round(lum(nose), 4),
                  "nose_over_skin": round(lum(nose) / lum(rgb), 3), "ok": lum(nose) >= lum(rgb),
                  "wave_a_nose_over_skin": round(lum(mul(rgb, {"light": (1.04, 0.9, 0.85), "dark": (1.28, 1.15, 1.1)}[s])) / lum(rgb), 3)}
    med = tuple((a + b) / 2 for a, b in zip(SKINS["light"], SKINS["dark"]))
    out["grey_brow"] = {"rgb": BROW_GREY, "contrast_on": {"light": contrast(BROW_GREY, SKINS["light"]),
                                                          "medium": contrast(BROW_GREY, med),
                                                          "dark": contrast(BROW_GREY, SKINS["dark"])},
                        "dark_brow_contrast_on": {k: contrast(BROW_RGB[k], SKINS[k]) for k in SKINS}}
    out["brow_colours_contrast"] = {b: {"light": contrast(rgb, SKINS["light"]), "medium": contrast(rgb, med),
                                        "dark": contrast(rgb, SKINS["dark"])} for b, rgb in BROW_COLOURS.items()}
    return out


def eye_radius(picks):
    if picks.get("loud") == "eye_size" and picks.get("eye_size") in LOUD["eye_size"]:
        return LOUD_EYE_R
    return EYE_SIZES[picks["eye_size"]]


PUPIL_EXP = 2.6  # the pupil outline's superellipse exponent (2 = an ellipse): a rounded oval, no straight sides


CLOSED_PIECES = ("brows", "teeth", "fhair")  # closed meshes: oriented by their signed volume


NOSE_RAISE_FOR_MOUSTACHE = 0.006  # the most the nose rises off a moustache it cannot clear by the squash


# brief3's look grid for the engineer (no choice made here): "c" as now (seated under the nose by the squash), "a" the
# ball seated ON TOP of the untouched moustache (the nose rises, at most NOSE_RAISE_ON_TOP), "b" a moustache thinner
# and lower in the middle (build_fhair), then seated as "c". The engineer chose "a" (2026-10-09 20:44 UTC, review page,
# moustache_ball = a): the lab's default since brief5
MOUSTACHE_VARIANT = "a"


NOSE_RAISE_ON_TOP = 0.012


# step 2 (brief5): a ball raised onto the moustache can reach the pupils (check7: 56 of 158 moustached faces); it then
# shrinks about its lowest point (it keeps sitting on the moustache) in 0.05 steps down to this scale
NOSE_PUPIL_SHRINK_MIN = 0.6


BAD_PAIRS = {("nose", "mouth"), ("nose", "teeth"), ("fhair", "mouth"), ("fhair", "teeth"), ("brow", "pupil"), ("mouth", "eye"), ("mouth", "lid"), ("mouth", "pupil"), ("teeth", "eye"),
             ("ear", "eye"), ("ear", "lid"), ("ear", "brow"), ("ear", "nose"), ("ear", "mouth"), ("ear", "fhair"),
             ("brow", "nose"), ("fhair", "eye"), ("fhair", "lid"), ("nose", "pupil"),
             ("nose", "fhair")}  # round E fix: the moustache sits below the nose (seat_moustache)
# art #42: the pinocchio stands far out in front, so it must clear the eyes and lids too (the ball and the bean nose
# may stand in front of the eyes' lower edge by design)
STRICT_NOSES = {"pinocchio"}
STRICT_NOSE_PAIRS = {("nose", "eye"), ("nose", "lid")}


SCALE_FADE = 0.08  # the same fade as clay_parts.bake_head_scale (SCALE_FADE): face and head stay in register


# ----------------------------------------------------------------------------------------------- recipe picks
PICK_KEYS = tuple(PICKS) + ("loud",)  # a recipe character's `face_kit` object: any of these, the rest its defaults
FACE_KIT_KEYS = PICK_KEYS + ("brow_rgb",)  # brow_rgb: the brow's own colour (linear RGB); default the skin's brow


def check_picks(spec, gender, where="face_kit"):
    """Problems with a recipe character's `face_kit` object as `where: what` strings (empty when fine): known keys,
    known values per category, facial hair only on the bodies that may wear it, the kit's forbid rules."""
    if spec is None:
        return []
    if not isinstance(spec, dict):
        return [f"{where}: must be an object of picks ({', '.join(FACE_KIT_KEYS)})"]
    out = []
    for k, v in spec.items():
        if k not in FACE_KIT_KEYS:
            out.append(f"{where}.{k}: unknown key; known: {', '.join(FACE_KIT_KEYS)}")
        elif k == "brow_rgb":
            if not (isinstance(v, list) and len(v) == 3 and all(isinstance(x, (int, float)) and not isinstance(x, bool)
                                                                and 0.0 <= x <= 1.0 for x in v)):
                out.append(f"{where}.brow_rgb: must be three numbers from 0 to 1")
        elif k == "loud":
            if v is not None and v not in LOUD_WEIGHTS:
                out.append(f"{where}.loud: {v!r} is not a loud category; known: {', '.join(LOUD_WEIGHTS)}")
        elif v not in PICKS[k]:
            out.append(f"{where}.{k}: {v!r} is not a pick; known: {', '.join(map(str, PICKS[k]))}")
    if out or gender not in DEFAULTS:
        return out
    p = picks_for(spec, gender)
    if p.get("facial_hair", "none") != "none" and gender not in RULES["facial_hair_bodies"]:
        out.append(f"{where}.facial_hair: body type {gender} wears no facial hair")
    if forbidden(p):
        out.append(f"{where}: the picks break a forbid rule of the kit ({RULES['forbid']})")
    return out


def picks_for(spec, gender):
    """The picks a recipe character's `face_kit` object gives: the body type's defaults with its picks on top (the
    mouth's forced teeth applied)."""
    p = default_picks(gender, **{k: v for k, v in (spec or {}).items() if k in PICK_KEYS})
    if p.get("mouth") in RULES["teeth_forced"]:
        p["teeth"] = RULES["teeth_forced"][p["mouth"]]
    return p
