"""M6's pure parts (art #196): the lid shells' rounded corners, the eye unit's size and the skin's contact field. Plain
Python, no bpy: read by alien_parts_geom.lid_shell (the shell's profile), alien_eyes.py (the wet strips follow the
same profile), alien_m6.py inside Blender and tools/tests/test_alien_lids_geom.py.

Lengths are in eyeball radii; elevations p in radians about the lid's hinge (lid_shell: the moving edge at p = 0,
the upper lid covering p > 0, the lower p < 0); latitudes t in radians from the lid's middle toward the hinge poles
(the eye's inner and outer corners, at t = +-t_max).

Why: seen from the front, S7's rolled rim (`bead`, a swell of the outer surface over the last degrees before the
edge) kept its full height out to the hinge poles, so at both corners the upper lid's rim stuck out sideways past the
dome's outline as a point (the engineer, 2026-10-19: "very sharp corners"). M6 tapers the swell to nothing toward the
corners and lets the upper lid's edge droop a little there (the lower lid's rise), so the two lids meet in a soft
almond, as in the paintover rf2. The middle of each lid (|t| below `from_deg`) is unchanged, so the rim's reach, the
eye shader's contact band and the blink are as before.
"""
from __future__ import annotations

import math

# The corner rounding (chosen on M6's grid; alien_m6.py --corner JSON merges a variant over it). from_deg: the
# latitude where the taper starts (the lid's middle keeps S7's rim); bead_keep: the share of the swell left at the
# pole; droop_deg / lift_deg: how far the upper lid's edge moves down and the lower lid's edge up at the pole (the
# back of the shell stays; the shift fades out toward it).
CORNER = {"from_deg": 35.0, "bead_keep": 0.0, "droop_deg": 10.0, "lift_deg": 5.0}
# No rounding: S7's shell (alien_parts_geom.lid_shell without `corner`)
CORNER_OFF = {"from_deg": 90.0, "bead_keep": 1.0, "droop_deg": 0.0, "lift_deg": 0.0}

# The eye unit's size (ball, lids and wet strips scaled together about the socket, the ball's centre) and the iris
# and pupil's angular size (alien.gd EYE_LOOK); chosen on M6's grid beside rf2.
EYE_SCALE = 0.95
EYE_SINK = 0.002  # m: the unit moved back into the head along the socket's axis, so the smaller domes meet the skin
IRIS_SCALE = 1.0

# The skin's contact shade near the lids and lips (alien_hue.gdshader `contact_*`): full where the skin touches a
# part, none `reach` m away (a smoothstep), stored per Body vertex in the UV layer CONTACT_UV (glTF TEXCOORD_4,
# Godot CUSTOM1.x).
CONTACT = {"reach": 0.007, "smooth": 2}
CONTACT_UV = "contact"


def smoothstep(a: float, b: float, x: float) -> float:
    if b == a:
        return 0.0 if x < a else 1.0
    s = min(1.0, max(0.0, (x - a) / (b - a)))
    return s * s * (3.0 - 2.0 * s)


def corner_weight(t: float, t_max: float, c: dict = CORNER) -> float:
    """0 in the lid's middle, rising to 1 at the hinge poles (|t| = t_max)."""
    t0 = math.radians(c["from_deg"])
    if t0 >= t_max:
        return 0.0
    return smoothstep(t0, t_max, abs(t))


def bead_at(bead: float, t: float, t_max: float, c: dict = CORNER) -> float:
    """The rolled rim's swell at latitude t: the full `bead` in the middle, `bead_keep` of it at the poles."""
    return bead * (1.0 - (1.0 - c["bead_keep"]) * corner_weight(t, t_max, c))


def edge_shift(t: float, t_max: float, upper: bool, c: dict = CORNER) -> float:
    """How far (radians) the lid's edge moves at latitude t: the upper lid's down (negative p), the lower lid's up
    (positive p), so the edges bend toward each other at the corners."""
    d = math.radians(c["droop_deg"] if upper else c["lift_deg"])
    return (-d if upper else d) * corner_weight(t, t_max, c)


def shell_profile(rho_in: float, rho_out: float, bead: float, upper: bool, span_deg: float = 200.0, seg_p: int = 12,
                  rim_seg: int = 5, bead_deg: float = 26.0, shift: float = 0.0,
                  crowd: bool | None = None) -> list[tuple[float, float, float]]:
    """lid_shell()'s closed cross-section as (rho, p, p0) round the loop: the outer surface from the back to the edge,
    the rim's half circle beyond the edge, the inner surface back again (rho in r; p the elevation, p0 the same point's
    elevation before `shift`, for the accent mask). `bead` swells the outer surface over the last bead_deg before the
    edge, the rim's half circle spanning the thicker edge; the samples crowd toward the edge (quadratic) when bead > 0.
    `shift` moves the edge by that many radians, fading out to nothing at the shell's back (span_deg), so the shell
    stays closed and its back is unchanged. With shift 0 this is S7's profile exactly. `crowd` (default: bead > 0)
    sets the quadratic sampling apart from the bead, so a rounded shell tapered to no bead at its poles keeps the
    same sampling in every row (no crease)."""
    sgn = 1.0 if upper else -1.0
    ex = 2 if (bool(bead) if crowd is None else crowd) else 1
    span = math.radians(span_deg)
    ro, ri = rho_out, rho_in
    re = ro + bead
    rm, hw = (re + ri) / 2, (re - ri) / 2
    bd = math.radians(bead_deg)
    out = []

    def put(rho, p):
        out.append((rho, p + shift * (1.0 - min(1.0, abs(p) / span)), p))

    for j in range(seg_p + 1):
        f = (1 - j / seg_p) ** ex
        p = span * f
        swell = bead * (1 - smoothstep(0.0, bd, p)) if bead else 0.0
        put(ro + swell, sgn * p)
    for j in range(1, rim_seg):
        a = math.pi * j / rim_seg
        put(rm + hw * math.cos(a), -sgn * (hw * math.sin(a)) / rm)
    for j in range(seg_p + 1):
        put(ri, sgn * span * (j / seg_p) ** ex)
    return out


def front_outline(rho_out: float, bead: float, edge_deg: float, upper: bool, t_max_deg: float = 89.0,
                  c: dict = CORNER, n: int = 90) -> list[tuple[float, float]]:
    """The lid edge's rim seen from the front (x right, z up, in r): per latitude the outermost point of the rim at
    the lid's rest edge elevation edge_deg (the lid turned so its edge lies there). For the test: how far the corner
    sticks out beyond the dome's own outline (rho_out)."""
    tm = math.radians(t_max_deg)
    pts = []
    for i in range(n + 1):
        t = -tm + 2 * tm * i / n
        b = bead_at(bead, t, tm, c)
        p = math.radians(edge_deg) + edge_shift(t, tm, upper, c)
        rho = rho_out + b
        pts.append((rho * math.sin(t), rho * math.cos(t) * math.sin(p)))
    return pts


def corner_overhang(rho_out: float, bead: float, c: dict = CORNER, t_max_deg: float = 89.0) -> float:
    """How far (in r) the rim at the pole reaches sideways past the dome's outline: S7's full bead there was the
    point the engineer saw."""
    tm = math.radians(t_max_deg)
    return (rho_out + bead_at(bead, tm, tm, c)) * math.sin(tm) - rho_out


def scale_about(co: tuple[float, float, float], pivot: tuple[float, float, float], k: float) -> tuple:
    """A point scaled by k about a pivot (the eye unit about its socket)."""
    return tuple(p + k * (x - p) for x, p in zip(co, pivot))


def iris_look(look: dict, k: float) -> dict:
    """An eye design's EYE_LOOK angles with the iris and pupil scaled by k: iris_deg and pupil_deg times k, and
    limbus_deg (the cornea's edge) moved by as much as the iris' edge, so iris_deg + edge 0.9 <= limbus_deg -
    limbus_soft_deg still holds; with no iris (manic) the limbus scales with the pupil."""
    out = dict(look)
    iris = out.get("iris_deg", 0.0)
    for key in ("iris_deg", "pupil_deg"):
        if key in out:
            out[key] = round(out[key] * k, 3)
    if "limbus_deg" in out:
        out["limbus_deg"] = round(out["limbus_deg"] - iris * (1.0 - k) if iris > 0 else out["limbus_deg"] * k, 3)
    return out


def contact(dist: float, reach: float = CONTACT["reach"]) -> float:
    """The contact field at a skin point `dist` m from the nearest lid or lip surface: 1 at contact, 0 beyond reach."""
    return 1.0 - smoothstep(0.0, reach, dist)
