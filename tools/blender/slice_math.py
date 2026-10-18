"""The pure rules of slice_actions.py (docs/godot.md, "The slice character"), without bpy so the tests run them: the
rest-pose guard between the character's rig and the animation set's donor, and the leg scale of `--own-proportions`
(art #207) for a body whose skeleton differs from the donor's on purpose (the alien base character, art #196)."""

from __future__ import annotations

import argparse
import re

# The rest heads of the two rigs must agree within this (the set's donor and the character share the body type's
# skeleton; the toes follow the shoe, so they differ and are only reported).
REST_TOLERANCE_M = 0.002
TOES = ("Toe.L", "Toe.R")
# The bones whose location keys carry the body over the floor: with --own-proportions they scale with the legs.
LEG_KEYED = ("Root", "Hips")
LEG_CHAIN = (("UpperLeg", "LowerLeg"), ("LowerLeg", "Foot"))
_LOCATION_RE = re.compile(r'^pose\.bones\["([^"]+)"\]\.location$')

Vec = tuple[float, float, float] | list[float]


def rest_check(rest: dict[str, float], own_proportions: bool = False) -> tuple[float, str, str | None]:
    """rest: per bone the distance (m) between the character's rest head and the donor's. Returns the largest distance
    outside the toes, its bone, and the refusal (None when the rigs may share the clips). With own_proportions any
    difference is accepted and only reported."""
    body = {k: v for k, v in rest.items() if k not in TOES}
    if not body:
        return 0.0, "", None
    worst = max(body, key=body.get)
    err = body[worst]
    if own_proportions or err <= REST_TOLERANCE_M:
        return err, worst, None
    return err, worst, (f"the rest poses differ by {err * 1000:.2f} mm at {worst} (tolerance {REST_TOLERANCE_M * 1000} mm; "
                        f"slice --own-proportions accepts a skeleton with its own proportions)")


def rest_turn(turns: dict[str, float]) -> tuple[float, str]:
    """turns: per bone the angle (degrees) between the character's rest orientation and the donor's. Returns the
    largest outside the toes and its bone, only reported: a bone-local rotation key turns a bone the same about its own
    axes on both rigs, so where the rest orientations differ the pose differs by that much (art #210)."""
    body = {k: v for k, v in turns.items() if k not in TOES}
    if not body:
        return 0.0, ""
    worst = max(body, key=body.get)
    return body[worst], worst


def arguments(argv: list[str]) -> argparse.Namespace:
    """slice_actions.py's command line (kept here so the tests parse it without Blender)."""
    ap = argparse.ArgumentParser(prog="slice_actions.py")
    ap.add_argument("--character", required=True)
    ap.add_argument("--anim", required=True)
    ap.add_argument("--clips", required=True, help="comma list of the set's action names to put on the character")
    ap.add_argument("--out", required=True)
    ap.add_argument("--json", required=True)
    ap.add_argument("--eye-height", type=float, help="scale the character so its eyes' rest centre is at this height (m)")
    ap.add_argument("--own-proportions", action="store_true",
                    help="accept a skeleton that differs from the donor's; scale the root and hip keys to the leg length")
    return ap.parse_args(argv)


def _dist(a: Vec, b: Vec) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def leg_length(heads: dict[str, Vec]) -> float:
    """A rig's leg length (m) from its rest heads (z up, the floor at z = 0): the thigh, the shin and the ankle's height,
    averaged over both legs."""
    legs = []
    for side in ("L", "R"):
        names = [f"{b}.{side}" for b in ("UpperLeg", "LowerLeg", "Foot")]
        missing = [n for n in names if n not in heads]
        if missing:
            raise ValueError(f"cannot measure the leg: no bone {missing}")
        up, low, foot = (heads[n] for n in names)
        legs.append(_dist(up, low) + _dist(low, foot) + foot[2])
    return sum(legs) / len(legs)


def leg_scale(character: dict[str, Vec], donor: dict[str, Vec]) -> float:
    """The factor for the clips' root and hip location keys: the character's leg length over the donor's, so a stride
    and a bob cover what the character's own legs reach."""
    theirs = leg_length(donor)
    if theirs <= 0:
        raise ValueError(f"the donor's leg length is {theirs} m")
    return leg_length(character) / theirs


def scales_with_legs(data_path: str) -> bool:
    """Whether an F-curve is a location the legs carry: the Root and Hips bones' locations, or the armature object's."""
    if data_path == "location":
        return True
    m = _LOCATION_RE.match(data_path)
    return bool(m) and m.group(1) in LEG_KEYED
