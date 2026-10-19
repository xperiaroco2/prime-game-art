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
