"""World-space zones and constants of the packs' standard rest pose (no Blender needed: points are anything with x, y
and z). They hold only while the target rig's Head bone sits at the recipe's "head_bone_rest"
([-0.0003, -0.0431, 1.5873] for men and women alike); build_character asserts that. The face looks toward -Y and +X is
the character's left.
"""

from __future__ import annotations

# Named boxes used to cut regions out of a split part (a recipe's "cut" list).
CUT_ZONES = {
    "chin_tuft": lambda c: c.z < 1.63 and c.y < -0.12,  # Punk's goatee in "Red"
    "over_ears": lambda c: abs(c.x) > 0.084 and -0.115 < c.y < 0.0 and 1.625 < c.z < 1.735,  # hair crossing the ears
    "ears": lambda c: abs(c.x) > 0.088 and -0.11 < c.y < 0.0 and 1.62 < c.z < 1.74,  # the head's own ears
    # art #42 round 4, w4's crest to the nape: the women's Punk skull cap (z 1.66-1.823) keeps only its centre band
    # (|x| < 0.022); its sides go below 0.125 m from the skull centre, which spares the crest spikes standing on top
    "punk_cap_sides": lambda c: abs(c.x) > 0.022 and _dist(c, SKULL_CENTRE) < 0.125,
}

# Named boxes that drop whole loose pieces of a split part (a recipe's "drop_pieces" list): a piece (faces joined by
# shared world positions) goes when the centre of its bounding box is inside; the catalogue classifies pieces the same
# way (tools/blender/catalogue_heads.py FACIAL_HAIR), so the King's 9 beard pieces go and his 18 hair pieces stay.
PIECE_ZONES = {
    "facial_hair": lambda c: c.z < 1.655 and c.y < -0.09 and abs(c.x) < 0.07,  # beards and moustaches
    # art #42 round 3, w4's true mohawk: the women's Punk "Pink" hair is 9 pieces: the skull cap (172 faces, x +-0.097,
    # z 1.66-1.823, centre y -0.054 z 1.742), six crest spikes (64-88 faces each, |x| < 0.036, centres z 1.77-1.86)
    # and two side strips by the ears (66 faces each, |x| 0.074-0.095, z 1.59-1.69); these two zones drop the cap and
    # the strips and keep the crest (the bean skull shows on the sides)
    "punk_cap": lambda c: abs(c.x) < 0.01 and -0.08 < c.y < -0.03 and c.z < 1.76,
    "punk_side_strips": lambda c: abs(c.x) > 0.06 and c.z < 1.70 and c.y < -0.08,
}

# Both ears of every pack head (tuck_ears flattens the vertices in it).
EAR_BOX = lambda p: -0.125 < p.y < -0.015 and 1.62 < p.z < 1.735  # noqa: E731

# The brows of a source head: never taken along with a hair material.
BROW_ZONE = lambda c: abs(c.x) < 0.085 and c.y < -0.125 and 1.672 < c.z < 1.722  # noqa: E731

# The skull centre that hair-like parts are inflated about.
SKULL_CENTRE = (0.0, -0.055, 1.69)


def _dist(c, p) -> float:
    return ((c.x - p[0]) ** 2 + (c.y - p[1]) ** 2 + (c.z - p[2]) ** 2) ** 0.5


# Where shaved hair leaves a stubble tone on the head's skin (a recipe hair's "stubble" zone, art #42 round 4). Unlike
# the boxes above, a stubble zone is relative to the Head joint in the built clay head (x1.3 baked in): dy back, dz up,
# metres. "line" is the hairline as (dy, lowest dz) points from the forehead to the nape: above it is scalp, below it
# the face, the ears and the neck; "feather" softens the line; in front of the first point nothing is scalp. Measured
# on the bean head of w4 (round 4 before cast): head top dz 0.304, face front dy -0.189, back dy +0.132, the eyes about
# dz 0.127, the kit ear dy -0.038 to 0.0 and dz 0.07 to 0.122, the nape about dz 0.03.
STUBBLE_ZONES = {
    "scalp": {
        "line": ((-0.19, 0.24), (-0.12, 0.20), (-0.06, 0.155), (-0.03, 0.15), (0.0, 0.14), (0.02, 0.11),
                 (0.06, 0.045), (0.14, 0.03)),
        "feather": 0.012,
    },
}


def stubble_line(dy: float, zone: str = "scalp") -> float | None:
    """The zone's hairline height dz at dy (linear between the points, flat after the last); None in front of it."""
    line = STUBBLE_ZONES[zone]["line"]
    if dy < line[0][0]:
        return None
    for (y0, z0), (y1, z1) in zip(line, line[1:]):
        if dy <= y1:
            return z0 + (z1 - z0) * (dy - y0) / (y1 - y0)
    return line[-1][1]


def stubble_weight(dy: float, dz: float, zone: str = "scalp") -> float:
    """How much stubble a skin point at (dy, dz) from the Head joint takes: 0 below the hairline, 1 a feather above
    it, smooth between (and fading in over a feather behind the zone's front point)."""
    z = stubble_line(dy, zone)
    if z is None:
        return 0.0
    f = STUBBLE_ZONES[zone]["feather"]

    def smooth(t: float) -> float:
        t = min(1.0, max(0.0, t))
        return t * t * (3.0 - 2.0 * t)

    return smooth((dz - z) / f) * smooth((dy - STUBBLE_ZONES[zone]["line"][0][0]) / f)

# Eye faces sit below this height; brows sharing the eye material (women's Formal and Medieval "Brown") sit higher.
EYE_Z_MAX = 1.70 + 0.012
