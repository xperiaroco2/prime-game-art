"""The M4 eyes' pure parts (art #196): the wet line's profile under a lid's rolled rim, and the cornea's optics that
godot/alien/alien_eye.gdshader draws (the same formulas, so a test can check them without Godot). Plain Python, no
bpy: read by alien_eyes.py inside Blender and by tools/tests/test_alien_eyes_geom.py.

Lengths are in eyeball radii; elevations in radians about the lid's hinge (alien_parts_geom.lid_shell: the lid's
moving edge at p = 0, the upper lid covering p > 0, the lower p < 0).
"""
from __future__ import annotations

import math

# The wet line (a tear film where a lid meets the ball): a strip in the lid's own frame, so it turns with the lid.
# Seen from the front it is a thin glossy band on the ball just beyond the lid's rim, which runs on under the rim
# into the gap between the ball and the lid's inner surface (a meniscus).
WET = {
    "beyond_deg": 1.0,  # how far the band reaches past the rim's farthest point onto the ball
    "lift": 0.0015,  # the band's height above the ball where it starts (a share of r), so it never z-fights
    "fill": 0.7,  # the meniscus under the rim: this share of the way from the ball up to the rim's lower surface
    "t_max_deg": 80.0,  # the band's span across the lid (the lid's own latitude), faded at both ends by the shader
    "seg_t": 48, "seg_p": 6,
}
# The cornea (alien_eye.gdshader's defaults; alien.gd EYE_LOOK sets limbus_deg per design)
CORNEA = {"limbus_deg": 27.0, "bulge": 0.12, "iris_depth": 0.05, "ior": 1.336}


def rim(rho_in: float, rho_out: float, bead: float) -> tuple[float, float]:
    """The rolled rim of lid_shell(): its centre radius and half width (both in r), as lid_shell builds them."""
    re = rho_out + bead
    return (re + rho_in) / 2, (re - rho_in) / 2


def rim_lower_surface(p_abs: float, rm: float, hw: float) -> float | None:
    """The radius of the rim's half circle on the ball's side at |p| beyond the edge (None past the rim's reach)."""
    s = p_abs * rm / hw
    if s > 1.0:
        return None
    return rm - hw * math.sqrt(1.0 - s * s)


def wet_profile(rho_in: float, rho_out: float, bead: float, upper: bool, w: dict = WET) -> list[tuple[float, float]]:
    """The wet line's cross-section as (rho, p) from the ball's side (beyond the rim, on the ball) to under the rim's
    inner edge (p = 0). The radius follows the meniscus: lift above the ball, then fill of the way up to the rim's
    lower surface where the rim is over it."""
    sgn = 1.0 if upper else -1.0
    rm, hw = rim(rho_in, rho_out, bead)
    reach = hw / rm  # the rim's farthest point beyond the edge (lid_shell's half circle)
    p0 = reach + math.radians(w["beyond_deg"])
    out = []
    n = w["seg_p"]
    for j in range(n + 1):
        pa = p0 * (1.0 - j / n)  # |p| from the band's far edge to the lid's edge
        rho = 1.0 + w["lift"]
        under = rim_lower_surface(pa, rm, hw)
        if under is not None:
            rho = max(rho, rho + (under - rho) * w["fill"])
        out.append((rho, -sgn * pa))
    return out


def lid_point(rho: float, p: float, t: float) -> tuple[float, float, float]:
    """lid_shell()'s point at radius rho, elevation p and latitude t (local -Y the edge's direction, +Z up)."""
    return (rho * math.sin(t), -rho * math.cos(t) * math.cos(p), rho * math.cos(t) * math.sin(p))


def cornea_sphere(limbus_deg: float, bulge: float) -> tuple[float, float]:
    """The cornea: a sphere through the limbus ring and the apex 1 + bulge on the axis; (centre on the axis, radius)."""
    lim = math.radians(limbus_deg)
    d = 1.0 + bulge - math.cos(lim)
    rc = (math.sin(lim) ** 2 + d * d) / (2.0 * d)
    return 1.0 + bulge - rc, rc


def refract(v, n, eta):
    """GLSL's refract() for 3-tuples (v, n unit)."""
    c = sum(a * b for a, b in zip(v, n))
    k = 1.0 - eta * eta * (1.0 - c * c)
    if k < 0.0:
        return (0.0, 0.0, 0.0)
    return tuple(eta * a - (eta * c + math.sqrt(k)) * b for a, b in zip(v, n))


def front_rho(x: float, c: dict = CORNEA) -> float:
    """The iris plane's radius that a ray along the axis at distance x reaches through the cornea: the shader's
    front_rho(), which keeps the design's iris and pupil angles as they looked from the front."""
    zc, rc = cornea_sphere(c["limbus_deg"], c["bulge"])
    zp = math.cos(math.radians(c["limbus_deg"])) - c["iris_depth"]
    hz = zc + math.sqrt(max(rc * rc - x * x, 0.0))
    ln = math.hypot(x, hz - zc)
    r = refract((0.0, 0.0, -1.0), (x / ln, 0.0, (hz - zc) / ln), 1.0 / c["ior"])
    return x + r[0] * (zp - hz) / min(r[2], -1e-3)
