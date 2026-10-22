"""T1 "socketed head", step 2 (art #196): the pure parts of alien_t1_kit.py, no bpy, so tools/tests runs them.

The kit is one head with recesses (two eye sockets, a mouth dish) and separate face pieces seated in them; an
expression is a set of visible pieces (nodes) plus a gaze turn of the eyeballs. This module holds the node names, the
expression table (written as t1_expressions.json), the lid shells' shape (a lid is a spherical shell hinged on the
eye's side axis, so its free edge reads as a straight line from the front, and the upper and lower lids meet at the
corners), the brows' poses and the seat rule that sinks a piece's back into the skin.
"""
from __future__ import annotations

import math

Vec = tuple[float, float, float]

MOUTHS = ("rest", "smile", "sad", "o")
LID_STATES = ("open", "half", "closed")
BROW_POSES = ("sad", "raised", "angry")
SIDES = ("L", "R")  # L: the character's left, +X in Blender (it faces -Y)

# Lid edges in degrees of the hinge angle phi (0 = the rest gaze, +90 = up) for the upper and the lower lid. The
# iris spans 19 degrees from the gaze pole (alien_t1_kit.EYE_SPEC), the pupil 9.
LIDS = {
    "open": {"upper": 52.0, "lower": -44.0},    # wide: white above and below the iris
    "half": {"upper": 13.0, "lower": -40.0},    # the 2D rest: the lid edge over the iris top
    "closed": {"upper": -13.0, "lower": -15.0},  # the upper lid down onto the lower one
}
# Brows sit on the skin above the lids: their centre BROW_BASE eyeball radii above the ball's centre, plus a pose's lift
# (same unit); tilt in degrees (+ = the inner end up); BROW_WIDTH eyeball radii long.
BROW_BASE = 1.12
BROW_WIDTH = 1.5
BROWS = {
    "sad": {"tilt": 16.0, "lift": 0.10},
    "raised": {"tilt": -3.0, "lift": 0.36},
    "angry": {"tilt": -20.0, "lift": -0.06},
}
GAZE_DEG = 24.0  # the gaze pair's turn of both eyeballs about the head's up axis


def node_names() -> list[str]:
    names = ["head"] + [f"mouth_{m}" for m in MOUTHS]
    for s in SIDES:
        names.append(f"eye_{s}")
        names += [f"lid_{s}_{st}" for st in LID_STATES]
        names += [f"brow_{s}_{p}" for p in BROW_POSES]
    return names


def _set(mouth: str, lids: str, brows: str | None = None) -> list[str]:
    nodes = ["head", f"mouth_{mouth}"]
    for s in SIDES:
        nodes += [f"eye_{s}", f"lid_{s}_{lids}"]
        if brows:
            nodes.append(f"brow_{s}_{brows}")
    return nodes


def expressions() -> dict:
    """Expression -> visible nodes and the eyeballs' gaze turn (degrees about the head's up axis; + turns the eyes
    toward the character's left)."""
    return {
        "rest": {"nodes": _set("rest", "half"), "gaze_deg": 0.0},
        "smile": {"nodes": _set("smile", "half"), "gaze_deg": 0.0},
        "sad": {"nodes": _set("sad", "half", "sad"), "gaze_deg": 0.0},
        "surprised": {"nodes": _set("o", "open", "raised"), "gaze_deg": 0.0},
        "angry": {"nodes": _set("sad", "half", "angry"), "gaze_deg": 0.0},
        "gaze_left": {"nodes": _set("rest", "half"), "gaze_deg": GAZE_DEG},
        "gaze_right": {"nodes": _set("rest", "half"), "gaze_deg": -GAZE_DEG},
        "blink": {"nodes": _set("rest", "closed"), "gaze_deg": 0.0},
    }


def smoothstep(e0: float, e1: float, x: float) -> float:
    t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def back_weight(normal_y: float) -> float:
    """How much a piece's vertex belongs to its back (its normal toward +Y, into the head): 0 front, 1 back."""
    return smoothstep(-0.1, 0.5, normal_y)


def seat_weight(normal_y: float, depth_frac: float) -> float:
    """back_weight, only on the piece's back part (depth_frac: 0 at its front, 1 at its back), so the lips' seam and
    the curled ends, whose faces also turn backward, keep their shape."""
    return back_weight(normal_y) * smoothstep(0.45, 0.7, depth_frac)


def seat_y(y: float, y_skin: float | None, weight: float, sink: float) -> float:
    """The seat rule: a back vertex in front of the skin (smaller y) is pulled to sink behind it, so no gap shows from
    any side; a vertex already inside, or with no skin behind it, stays."""
    if y_skin is None:
        return y
    return y + weight * max(0.0, y_skin + sink - y)


def lid_thickness(phi_deg: float, edge_deg: float, t0: float, bead: float = 1.1, width_deg: float = 9.0) -> float:
    """The shell's thickness: t0, swelling to t0 (1 + bead) at the free edge (the rolled clay lid)."""
    return t0 * (1.0 + bead * math.exp(-abs(phi_deg - edge_deg) / width_deg))


def lid_dir(axes: tuple[Vec, Vec, Vec], phi: float, psi: float) -> Vec:
    """A unit direction on the hinged shell: phi turns from forward toward up about the side axis, psi leans toward
    the side (radians). Constant phi is a plane through the side axis: a straight lid edge from the front."""
    f, s, u = axes
    cp = math.cos(psi)
    return tuple(cp * (math.cos(phi) * f[i] + math.sin(phi) * u[i]) + math.sin(psi) * s[i] for i in range(3))


def lid_span(state: str, upper: bool, root_deg: float = 172.0) -> tuple[float, float]:
    """(edge, root) of a lid's hinge angle in degrees: the free edge first."""
    edge = LIDS[state]["upper" if upper else "lower"]
    return (edge, root_deg) if upper else (edge, -root_deg)


def brow_tilt_rad(side: str, pose: str) -> float:
    """The brow's turn about +Y (Blender): the inner end (toward x = 0) rises for a positive tilt on both sides."""
    t = math.radians(BROWS[pose]["tilt"])
    return t if side == "L" else -t
