"""The clay look's settings and its pure-Python rules (no bpy): the recipe's `look` and `clay` keys, the triangle
budgets and lump amplitudes per part kind, the texel densities and texture sizes of the bake, the bake margin in
colour-map pixels, and the content key of a baked piece in the clay library (docs/assembly.md, "The clay look").

Ported from the faces lab's round D (D:/prime-art-raw/research/2026-10-05-faces/lab/clay_d: clay_parts.py,
clay_bake.py, clay_libbake.py; README_bake.txt holds the measurements behind every number here). The runner imports
this module to validate a recipe before Blender starts; the Blender modules um/clay.py and um/claybake.py read the
same constants.
"""

import hashlib
import json
import math

LOOKS = ("pack", "clay")
DEFAULT_LOOK = "pack"

# Triangles per part kind after the clay pass (subdivide once, then decimate to this): round D's library budgets.
BUDGET = {"head": 1200, "hair": 1200, "top": 3000, "bottom": 1400, "shoes": 900, "headwear": 800, "helmet": 1200,
          "earrings": 300, "accessory": 300, "moustache": 300, "beard": 300}
# The shared world-space lump field's amplitude per kind (m): every part pushed along its normal by one Perlin field
# (seed 0), so nested layers at the same place move together.
LUMP = {"head": 0.001, "hair": 0.0015, "top": 0.0025, "bottom": 0.0025, "shoes": 0.002, "headwear": 0.0015,
        "helmet": 0.0015, "earrings": 0.001, "accessory": 0.001, "moustache": 0.001, "beard": 0.001}
LUMP_FREQ = 22.0
LUMP_SEED = 0
# Open shoe collars and hat rims rolled thick (Solidify, rim only, inward); garment hems stay (they are seams).
RIMS = {"shoes": 0.003, "headwear": 0.003}
HEAD_SCALE = 1.3  # the clay head and everything on it, about the Head bone's head, baked into the meshes
SCALE_FADE = 0.08  # the x1.3 fades out over this height below the Head joint (long hair, the neck)
HEAD_ROLES = ("head", "hair", "eyes", "brows", "mouth")  # plus every extra (a head item); clothing is not scaled
BODY_ROLES = ("top", "bottom", "shoes")  # the clothing: never scaled with the head
FACE_ROLES = ("eyes", "brows", "mouth")  # the repo's scripted face: the hook where the face kit (art #42 B) plugs in
JOIN_INTO_HEAD = ("brows", "mouth")  # one head atlas, as round D: the surfaces stay within the contract's cap of 8
GLOSSY = {"eye_white": 0.17, "eye_black": 0.08, "white": 0.17, "pupil": 0.08, "iris": 0.12, "teeth": 0.28,
          "tongue": 0.45}  # material name part: roughness
DEFAULT_KIND = "accessory"

# The bake. Normal-map texel density (px per metre of surface) per role: heads and faces are seen face to face at
# about 1 m (1 mm per texel carries the 6 mm fingerprint dents), bodies mostly from 2 m and more. The base colour is
# half the normal map's size in each direction (its finest feature is the 2 cm mottle).
DENSITY = {"head": 1024, "eyes": 1024, "brows": 1024, "mouth": 1024, "hair": 512, "top": 512, "bottom": 512,
           "shoes": 512}
DEFAULT_DENSITY = 512
COLOUR_DIV = 2
MIN_SIZE = 128
MAX_SIZE = 1024  # the contract's texture_character_px
MARGIN_PX = 3.0  # the island gap in colour-map texels at the colour map's final size
MARGIN_START = 0.006
COLOUR_SS = 2  # the colour and skin-mask bakes run at 2 x and are box-filtered down (no texel staircase on borders)
BAKE_MARGIN_PX = 16
BAKE_SAMPLES = 16
UV_ANGLE = 75.0
ROUGHNESS = 0.8
SPECULAR_LEVEL = 0.5  # glTF's default dielectric; Godot 4.7.2 ignores KHR_materials_specular
NORMAL_MIN_Z = 0.5  # baked normals tipped further come from folded pack triangles: set flat
CAGE_M = 0.03  # the pack-colour bake (selected to active): rays start 3 cm outside, no length limit
GREY = 0.9  # the mottle bake's flat colour
BAKE_VERSION = 1  # part of every library key: raise it when the clay pass or the bake changes their output

CLAY_KEYS = ("head_scale", "budget", "lump", "density")


def look_of(recipe, override=None):
    """The look a build uses: the command's --look, else the recipe's `look`, else the pack look."""
    return override or recipe.get("look") or DEFAULT_LOOK


def settings(recipe):
    """The clay settings: the defaults above, overridden by the recipe's optional `clay` object."""
    c = recipe.get("clay") or {}
    return {
        "head_scale": float(c.get("head_scale", HEAD_SCALE)),
        "budget": dict(BUDGET, **c.get("budget", {})),
        "lump": dict(LUMP, **c.get("lump", {})),
        "density": dict(DENSITY, **c.get("density", {})),
    }


def check(recipe):
    """Problems with the recipe's `look` and `clay` keys, as `where: what` strings (empty when fine)."""
    out = []
    look = recipe.get("look", DEFAULT_LOOK)
    if look not in LOOKS:
        out.append(f"look: {look!r} is not a look; known: {', '.join(LOOKS)}")
    c = recipe.get("clay")
    if c is None:
        return out
    if not isinstance(c, dict):
        return out + ["clay: must be an object"]
    for k in c:
        if k not in CLAY_KEYS:
            out.append(f"clay.{k}: unknown key; known: {', '.join(CLAY_KEYS)}")
    hs = c.get("head_scale", HEAD_SCALE)
    if not isinstance(hs, (int, float)) or isinstance(hs, bool) or not 0.5 <= hs <= 2.0:
        out.append("clay.head_scale: a number from 0.5 to 2.0")
    for k in ("budget", "lump", "density"):
        v = c.get(k, {})
        if not isinstance(v, dict):
            out.append(f"clay.{k}: must be an object of kind: number")
            continue
        for kind, x in v.items():
            if not isinstance(x, (int, float)) or isinstance(x, bool) or x < 0:
                out.append(f"clay.{k}.{kind}: must be a number >= 0")
    return out


def kind_of(role, extra_kinds=None):
    """The part kind that picks a budget and a lump: the role itself, or an extra's role mapped to a known kind."""
    if role in BUDGET:
        return role
    return (extra_kinds or {}).get(role, DEFAULT_KIND)


def pick_size(area_m2, uv_frac, density, max_size=MAX_SIZE):
    """The normal map's side: the smallest power of two from MIN_SIZE whose texel density on this part reaches 90 %
    of the target, capped at max_size."""
    size = MIN_SIZE
    while size < max_size and size * math.sqrt(uv_frac / max(area_m2, 1e-9)) < 0.9 * density:
        size *= 2
    return size


def colour_size(normal_px):
    return max(64, normal_px // COLOUR_DIV)


def margin_needed(colour_px):
    """The pack margin (a fraction of the texture side) that leaves MARGIN_PX texels at this colour-map size."""
    return MARGIN_PX / colour_px


def texel_density(size, uv_frac, area_m2):
    return size * math.sqrt(uv_frac / max(area_m2, 1e-9))


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c):
    c = min(1.0, max(0.0, c))
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def piece_key(role, gender, spec, cfg, skin=None, recolor=(), context=None, kind=None):
    """The content key of one baked piece in the clay library: everything its clay mesh and textures depend on (the
    role, the body type, the part's recipe spec, the character's skin tone and the recolours of this part, the clay
    settings of its kind and the bake version). Two characters wearing the same piece in the same colours share it.
    `context` adds what the piece depends on beyond its own spec: the head a face part is built on, the shoes the
    bottom is culled against, the part's `extend` edits, the rig a head item is scaled on. Returns 16 hex digits."""
    kind = kind or role
    data = {
        "v": BAKE_VERSION, "role": role, "gender": gender, "spec": spec,
        "skin": [round(float(x), 4) for x in skin] if skin is not None else None,
        "recolor": [dict(r) for r in recolor],
        "head_scale": cfg["head_scale"],
        "budget": cfg["budget"].get(kind), "lump": cfg["lump"].get(kind),
        "density": cfg["density"].get(role, DEFAULT_DENSITY),
        "context": context,
    }
    blob = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def keys_for(recipe, rc, cfg):
    """{role: library key} for every part of character rc: the pack parts, its extras and the scripted face. Beyond
    a part's own spec, skin and recolours the key holds what the build does to it before the bake (assemble.build):
    every head item (the head, hair, extras and face; clay.head_scale) is scaled about the Head joint of the body
    type's skeleton, so its key holds the skeleton and `head_bone_rest`; the bottom is culled against the shoes
    (fit.tuck_cull) and its foot weights split at the shoes' ball (toes.add_toe_bones), so its key holds the shoes;
    a part the character's `extend` lengthens (fit.extend_edge) holds its edits; a face part holds the head it is
    built on, the face settings and the hair."""
    g, skin = rc["gender"], rc.get("skin")
    recolor = rc.get("recolor", [])

    def rec(role):
        return [r for r in recolor if r.get("part") == role]

    def extend(role):
        return [{"drop": e["drop"]} for e in rc.get("extend", []) if e.get("part") == role]

    rig = {"skeleton": recipe.get("skeleton", {}).get(g), "head_bone_rest": recipe.get("head_bone_rest")}

    def ctx(role, **more):
        """The context of a part: the rig for a head item, the shoes for the bottom, the part's extend edits."""
        c = dict(more)
        if role not in BODY_ROLES:
            c["rig"] = rig
        if role == "bottom":
            c["shoes"] = rc["shoes"]
        if extend(role):
            c["extend"] = extend(role)
        return c or None

    face = {"head": rc["head"], "face": recipe.get("face", {}).get(g), "shading": recipe.get("face_shading", "smooth"),
            "hair": rc["hair"]}
    joined = {r: rc[r] for r in JOIN_INTO_HEAD}  # the face parts baked into the head's atlas
    keys = {"head": piece_key("head", g, rc["head"], cfg, skin, rec("head"), context=ctx("head", joined=joined, **face))}
    keys["hair"] = piece_key("hair", g, rc["hair"], cfg, None, rec("hair"), context=ctx("hair"))
    for e in rc.get("extras", []):
        keys[e["role"]] = piece_key(e["role"], g, e, cfg, None, rec(e["role"]), context=ctx(e["role"]),
                                    kind=kind_of(e["role"]))
    for role in BODY_ROLES:
        keys[role] = piece_key(role, g, rc[role], cfg, skin, rec(role), context=ctx(role))
    for role in FACE_ROLES:
        keys[role] = piece_key(role, g, rc[role], cfg, skin, rec(role), context=ctx(role, **face))
    return keys
