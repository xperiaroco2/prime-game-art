"""Pure helpers of the alien's texture UV and detail sculpt (art #196, step M2), with no Blender import, so
tools/tests/test_alien_detail_geom.py runs them with the standard library. alien_uv.py and alien_detail.py use them
(their numpy versions follow the same formulas)."""
from __future__ import annotations

import math

# The UV islands. Each face of Body gets a part from the bone that weighs most on its vertices; a part is one island,
# except the torso (split front and back along the flanks, under the arms) and the hands (split palm and back along
# the side of the hand and the fingers). A tube part gets one lengthwise cut where it is least seen: the head and neck
# at the back (up the nape and along the crest blade's back edge), the arms underneath (T-pose), the legs on the
# inner side. The cut is the line where the angle around the part's axis wraps (BRANCH_SIDE).
PARTS = ("head", "torso", "arm", "hand", "leg", "foot")
BRANCH_SIDE = {"head": "back", "arm": "down", "leg": "inner"}
# Texel density per part, relative (a linear factor: a part's UV area grows with its square): the face and the hands
# are looked at from close.
DENSITY = {"head": 1.75, "hand": 1.45, "foot": 0.8, "torso": 1.0, "arm": 1.0, "leg": 0.9}
UV = {"size": 4096, "margin_px": 24, "method": "MINIMUM_STRETCH", "smooth_labels": 3, "min_island": 60, "sole_nz": 0.55, "hand_smooth": 4}


def part_of_bone(name: str) -> str:
    """The UV part a deform bone's vertices belong to (side suffix `_L` / `_R` for the limbs)."""
    side = "_L" if name.startswith("Left") else "_R" if name.startswith("Right") else ""
    base = name[4:] if side == "_L" else name[5:] if side == "_R" else name
    if base in ("Head", "Neck"):
        return "head"
    if base in ("UpperArm", "LowerArm"):
        return "arm" + side
    if base == "Hand" or base.startswith(("Index", "Middle", "Ring", "Little", "Thumb")):
        return "hand" + side
    if base in ("UpperLeg", "LowerLeg"):
        return "leg" + side
    if base in ("Foot", "Toes"):
        return "foot" + side
    return "torso"  # Root, Hips, Spine, Chest, UpperChest, the shoulders


def density(part: str) -> float:
    """DENSITY of a labelled part (`hand_L_palm` -> hand)."""
    return DENSITY[part.split("_")[0]]


def crosses_branch(t1: float, t2: float) -> bool:
    """True when two neighbouring faces' angles (radians, -pi..pi around a part's axis, the cut side at +-pi) lie on
    opposite sides of the cut: the edge between them is a seam. Faces either side of the angle's zero (the seen side)
    do not count."""
    return t1 * t2 < 0 and abs(t1 - t2) > math.pi


# The detail sculpt. A crease is a Ricker profile across its line (a soft valley with slight shoulders, no volume
# change); `depth` and `width` in mm (width: the distance from the line to the profile's zero crossing).
def crease(s: float, width: float) -> float:
    """The crease height (units of its depth) at distance s from its line: -1 on the line, 0 at s = width, a shoulder
    of +0.45 at s = 1.73 width (the skin pushed up either side), back to 0 by about 4 widths; its integral across the
    line is 0."""
    q = (s / width) ** 2
    return -(1.0 - q) * math.exp(-0.5 * q)


def smoothstep(a: float, b: float, x: float) -> float:
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


MAX_DISP_MM = 1.6  # the sculpt never moves the surface further (the silhouette stays)
# depth, width (mm) and the side of each joint crease; `lines` parallel creases `gap` mm apart.
CREASES = {
    "knuckle_dorsal": {"depth": 0.30, "width": 0.9, "lines": 3, "gap": 1.6},
    "knuckle_palm": {"depth": 0.60, "width": 1.1, "lines": 1, "gap": 0.0},
    "wrist": {"depth": 0.35, "width": 1.6, "lines": 2, "gap": 4.0},
    "elbow": {"depth": 0.45, "width": 2.6, "lines": 2, "gap": 6.0},
    "knee": {"depth": 0.45, "width": 3.0, "lines": 2, "gap": 7.0},
    "armpit": {"depth": 0.35, "width": 3.0, "lines": 1, "gap": 0.0},
    "neck_front": {"depth": 0.30, "width": 2.4, "lines": 2, "gap": 13.0},
    "neck_back": {"depth": 0.25, "width": 2.6, "lines": 1, "gap": 0.0},
    "lid_fold": {"depth": 0.70, "width": 1.5, "lines": 1, "gap": 0.0},
    "under_eye": {"depth": 0.22, "width": 2.2, "lines": 1, "gap": 0.0},
    "lip_groove": {"depth": 0.40, "width": 1.6, "lines": 1, "gap": 0.0},
    "philtrum": {"depth": 0.22, "width": 2.2, "lines": 1, "gap": 0.0},
    "nasolabial": {"depth": 0.45, "width": 3.2, "lines": 1, "gap": 0.0},
    "belly_line": {"depth": 0.40, "width": 4.0, "lines": 1, "gap": 0.0},
}
# The fine grain is a bump on the high copy's material (alien_detail.GRAIN), baked into the normal map with the
# geometry: pores (cells `pore_mm` across) and a soft orange-peel noise; `face` and `body` scale its strength.
GRAIN = {"pore_mm": 1.1, "pore_depth_mm": 0.045, "peel_mm": 4.5, "peel_depth_mm": 0.06, "face": 1.0, "body": 0.45}


def line_offsets(lines: int, gap: float) -> list[float]:
    """The offsets (mm) of a crease's parallel lines, centred on the joint."""
    return [(i - (lines - 1) / 2.0) * gap for i in range(lines)]


# M2b (art #196, the engineer's notes on v27): the sculpt softened toward rf2's smooth toy skin. A sculpt is CREASES
# and GRAIN with changes over them, plus:
# - `soften`: before the creases, the high copy's sharp ridges and folds under the jaw (the jaw's edge from the mouth's
#   corners to the neck, and the fold where the jaw's underside meets the throat) relaxed along the normal: `passes`
#   Laplacian passes of `step`, each vertex weighted by its curvature (edge_weight: |curvature| from `lo` to `hi` of the
#   half range) grown over `spread` edges, inside the jaw region; the total move capped at `max_mm` (within the bake's
#   cage and ray). The low mesh is an irregular triangulation, and its subdivision crumples where the jaw's underside
#   folds into the throat: a ragged crease in the high copy, drawn by the normal map and, far darker, by the texture's
#   cavity tint from the curvature bake. That is "the scar under the neck" (v27);
# - `curvature`: the curvature colour's smoothing passes and tanh scale (alien_detail.curvature).
# M2 is the shipped sculpt, no changes.
SOFTEN = {"passes": 0, "step": 0.5, "lo": 0.15, "hi": 0.5, "spread": 0, "max_mm": 1.5}
CURVATURE = {"smooth": 2, "scale": 120.0, "jaw_smooth": 0}  # jaw_smooth: more passes where `soften` worked
SCULPT_PARTS = ("creases", "grain", "soften", "curvature")
SCULPTS = {
    "m2": {},
    # Chosen on two grids (M2b/variants/g1, g2; rf2 first, light D, M3c's texture without its cavity tint): the neck
    # rings gone (rf2 has none), the brow folds a third as deep and twice as wide, the creases under the mouth softer
    # (the groove at the mouth's corners read as a short cut beside the chin at 0.28 mm),
    # the pores finer (0.7 mm) and about a third as deep on the face, a faint even grain left (g2's f_grain_mid, at
    # 0.024 mm and 0.6 on the face, read sandy again at 0.25 m); the jaw's fold relaxed over 24 edges (g2's d_fold,
    # 12 edges and 120 passes, left the crumple) and its curvature smoothed 120 passes more.
    "m2b": {
        "creases": {"neck_front": {"depth": 0.0}, "neck_back": {"depth": 0.0},
                    "lid_fold": {"depth": 0.22, "width": 3.0}, "under_eye": {"depth": 0.08},
                    "lip_groove": {"depth": 0.15}, "nasolabial": {"depth": 0.30}},
        "grain": {"pore_mm": 0.7, "pore_depth_mm": 0.016, "peel_depth_mm": 0.022, "face": 0.45},
        "curvature": {"smooth": 6, "jaw_smooth": 120},
        "soften": {"passes": 300, "step": 0.6, "lo": 0.08, "hi": 0.3, "spread": 24, "max_mm": 1.8},
    },
}
# M6c (the engineer on v28: the release candidate's skin "smooth again, without any texture"; v27's "M3c + M4" with
# M2's grain read better): M2b's neck fix, soft creases and jaw relax, with M2's fine grain back (the pores 1.1 mm and
# 0.045 mm deep, the peel 0.06 mm, full on the head). Measured on the face (M6c's handoff): M2b's grain left 55 % of
# M2's normal-map energy at the pore scale and a third of its lit-luminance grain in Godot at 0.4 m; the albedo and
# ORM did not change (the grain is a bump, never in the curvature or the AO).
SCULPTS["m6c"] = {k: v for k, v in SCULPTS["m2b"].items() if k != "grain"}
# M8b (art #196): M6c without the lip groove. The groove was cut round one mouth's outline (frog rest's box, the
# widest piece), so it drew a faint dark line round that old footprint on every other mouth and width: the normal map
# and the texture's cavity tint (the curvature bake) both traced it. The skin carries no mouth's mark now, as the AO
# since M7; each mouth's shade on the skin is its own contact channel (TEXCOORD_5).
SCULPTS["m8b"] = dict(SCULPTS["m6c"], creases=dict(SCULPTS["m6c"]["creases"], lip_groove={"depth": 0.0}))


def sculpt(name: str, extra: dict | None = None) -> dict:
    """The full settings of sculpt `name` (SCULPTS) with `extra` (the same shape) over them: {"creases", "grain",
    "soften", "curvature"}, each a fresh dict. An unknown crease or key is an error, so a typo never passes silently."""
    if name not in SCULPTS:
        raise KeyError(f"no sculpt {name!r}; known: {', '.join(SCULPTS)}")
    out = {"creases": {k: dict(v) for k, v in CREASES.items()}, "grain": dict(GRAIN), "soften": dict(SOFTEN),
           "curvature": dict(CURVATURE)}
    for changes in (SCULPTS[name], extra or {}):
        unknown = set(changes) - set(SCULPT_PARTS)
        if unknown:
            raise KeyError(f"unknown sculpt keys {sorted(unknown)}")
        for k, v in changes.get("creases", {}).items():
            if k not in out["creases"]:
                raise KeyError(f"no crease {k!r}")
            bad = set(v) - set(out["creases"][k])
            if bad:
                raise KeyError(f"unknown keys {sorted(bad)} in crease {k!r}")
            out["creases"][k].update(v)
        for part in ("grain", "soften", "curvature"):
            bad = set(changes.get(part, {})) - set(out[part])
            if bad:
                raise KeyError(f"unknown {part} keys {sorted(bad)}")
            out[part].update(changes.get(part, {}))
    return out


def edge_weight(curv01: float, lo: float, hi: float) -> float:
    """How strongly `soften` relaxes a vertex: its curvature colour (0..1, 0.5 flat) away from flat, as a share of the
    half range (a convex ridge and a concave fold alike), smoothstepped from lo to hi."""
    return smoothstep(lo, hi, abs(curv01 - 0.5) / 0.5)
