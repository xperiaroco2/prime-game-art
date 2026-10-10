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
}

# Named boxes that drop whole loose pieces of a split part (a recipe's "drop_pieces" list): a piece (faces joined by
# shared world positions) goes when the centre of its bounding box is inside; the catalogue classifies pieces the same
# way (tools/blender/catalogue_heads.py FACIAL_HAIR), so the King's 9 beard pieces go and his 18 hair pieces stay.
PIECE_ZONES = {
    "facial_hair": lambda c: c.z < 1.655 and c.y < -0.09 and abs(c.x) < 0.07,  # beards and moustaches
}

# Both ears of every pack head (tuck_ears flattens the vertices in it).
EAR_BOX = lambda p: -0.125 < p.y < -0.015 and 1.62 < p.z < 1.735  # noqa: E731

# The brows of a source head: never taken along with a hair material.
BROW_ZONE = lambda c: abs(c.x) < 0.085 and c.y < -0.125 and 1.672 < c.z < 1.722  # noqa: E731

# The skull centre that hair-like parts are inflated about.
SKULL_CENTRE = (0.0, -0.055, 1.69)

# Eye faces sit below this height; brows sharing the eye material (women's Formal and Medieval "Brown") sit higher.
EYE_Z_MAX = 1.70 + 0.012
