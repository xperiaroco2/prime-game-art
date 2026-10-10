"""The jaw check (art #42): every assembled character keeps a whole lower jaw, measured on the built geometry, not
on the recipe (recipe.check_heads compares only material names). m4 lost its lower jaw because its recipe kept the
Casual head's "Skin" without the painted stubble "Skin_Darker"; a head cut zone, the face adapter, or a mask or
other extra in front of the chin would cut or hide it the same way, and so would a head the catalogue has no
skull item for.

The measure, in the rest pose (world space: the face toward -Y, +X the character's left): from the front and from 35
degrees on each side (the review sheets' 3/4 views), at LEVELS_MM below the mouth centre, a ray toward the head's
axis (x of the eyes, y AXIS_Y). A whole jaw is met on the face's front (y below JAW_FRONT_Y_MAX); a cut jaw lets the
ray through to the inside of the neck or the back of the head (or nothing). The part met before the head must be the
face kit's or the scripted face's (SIGHT_CLEAR_ROLES) or the hairstyle (COVER_OK_ROLES: m2's King beard, w2's lock
of hair at 3/4), never a mask, another extra or clothing.

No Blender needed here: build_character feeds the hits in (assemble.jaw_measure) and the cast build fails on a
problem (assemble_characters.py).
"""

from __future__ import annotations

import math
from typing import Any

LEVELS_MM = (10, 20, 30)  # mm below the mouth centre: the lower lip, the chin's front, the chin's bottom
AXIS_Y = -0.05  # m: the head's vertical axis (about the Head bone, y -0.043) the rays aim at
JAW_FRONT_Y_MAX = -0.08  # m: a whole jaw's surface is met in front of this y (the cast: -0.096 to -0.155)
SIGHT_DEG = {"front": 0.0, "threequarter_L": 35.0, "threequarter_R": -35.0}
SIGHT_CLEAR_ROLES = ("eyes", "face", "brows", "mouth")  # may stand in front of the jaw: the face parts
COVER_OK_ROLES = ("hair",)  # may cover the jaw by design (a beard, a lock of hair): reported, never a problem


def sight_dirs(degrees: dict[str, float] = SIGHT_DEG) -> dict[str, tuple[float, float, float]]:
    """Unit directions from the head toward each viewer: 0 degrees straight in front (-Y), positive toward the
    character's left (+X)."""
    return {k: (math.sin(math.radians(a)), -math.cos(math.radians(a)), 0.0) for k, a in degrees.items()}


def read_ray(hits: list[tuple[str, float, float]], clear: tuple[str, ...] = SIGHT_CLEAR_ROLES) -> dict[str, Any]:
    """hits: (role, distance from the viewer, hit y) of each part's nearest surface on one ray. Returns {"head_y": the
    head's hit y in m or None, "blocker": the nearest role outside clear in front of the head (or of nothing) or
    None}."""
    head = next((h for h in hits if h[0] == "head"), None)
    limit = head[1] if head else math.inf
    blockers = sorted((h for h in hits if h[0] != "head" and h[0] not in clear and h[1] < limit), key=lambda h: h[1])
    return {"head_y": round(head[2], 4) if head else None, "blocker": blockers[0][0] if blockers else None}


def problems(cid: str, m: dict[str, Any], front_y_max: float = JAW_FRONT_Y_MAX,
             cover_ok: tuple[str, ...] = COVER_OK_ROLES) -> list[str]:
    """The problems of one character's jaw measure m (assemble.jaw_measure): {"rays": {view: [{"dz_mm", "head_y",
    "blocker"}, ...]}}."""
    out = []
    for view, rows in sorted(m.get("rays", {}).items()):
        for r in rows:
            at = f"{cid}: {view} view, {r['dz_mm']} mm below the mouth"
            if r["head_y"] is None:
                out.append(f"{at}: no head there (the lower jaw is cut away)")
            elif r["head_y"] > front_y_max:
                out.append(f"{at}: the head is first met at y {r['head_y']:.3f} m, behind the face's front "
                           f"({front_y_max} m): the lower jaw is cut open (head keep/as_skin, cut zones or the face adapter)")
            if r["blocker"] and r["blocker"] not in cover_ok:
                out.append(f"{at}: the jaw is covered by the {r['blocker']} part")
    return out
