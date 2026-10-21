"""M14 (art #196): the tongue mouth mt2's tongue and teeth as plain geometry (no Blender, so it is unit-tested).

The mt2 sheet (`D:/prime-art-raw/2026-10-20-alien-face-sheets-2/mt2/`): soft coral lips, a few small gappy blunt
teeth and a soft pink tongue with a centre groove that pokes out over the lower lip in every shape (rest: out at one
corner; M: the tip between pressed lips; small: resting on the lower lip; A: lolling out of the dropped jaw; E: out of
one corner; O: the tip out of the round opening). The tongue is the same size in every shape; each shape only places
it (TONGUE["shapes"]).

The tongue is built round the lower lip it lies on: alien_mouths.build_tongue_out measures that lip at the tongue's x
(its front's top and bottom on the built piece: the lip's roll as a circle of radius R about C) and calls spine():
- a part inside the mouth (`inside` long) up onto the roll's top from behind it (its root `dip` lower);
- a wrap over the roll's front (`wrap` degrees: 0 lies on its top, 90 hangs straight down in front of it), at R plus
  half the tongue's thickness plus `clear`;
- a straight hang along the wrap's last tangent (`hang` long), leaning sideways by `slant` degrees as it leaves the
  lip, twisted by `roll` degrees toward the tip;
- the last 0.45 width a round tip (in plan a half ellipse; in profile plump to the end, M14b: TONGUE["tip"]).
Coordinates are the world's (x to the viewer's right, y backward: the front is -y, z up). Sections are flattened
ellipses (`width` x `thick`), squarer at the sides, a flatter underside (`flat`) and a soft groove on top (`groove`);
the top faces up inside the mouth and toward the viewer where the tongue hangs. Each vertex carries a flop weight
(0 up to the lip's top, rising to 1 at the tip): godot/alien/alien_mouth_motion.gdshaderinc bends the tongue by it
(`tongue_flop`).

The teeth (TEETH): two upper teeth either side of a gap and one lower tooth on the left, uneven in size and tilt, each
a rounded box (a superellipsoid) hanging from under its lip's inner edge (tucked `tuck` into it), its front `front` of
the lip's depth in front of the lip's axis.
"""
from __future__ import annotations

import math

TONGUE = {
    "width": 0.039,  # m, the widest (the sheet's: about 0.42 of the rest mouth's width; M14 grid g1: 32 / 36 / 40 mm)
    "thick": 0.010,  # m, the thickest (top to underside; M14b grid g3: 7.5 read as a strap in profile, 11 a sausage)
    "groove": 0.70,  # the centre groove's depth, a share of the half thickness (M14b: 0.50 barely read)
    "groove_root": 0.45,  # M14b: the groove's share up to the lip's top (deep there it notched the root's top edge)
    "flat": 0.75,  # the underside's half thickness, a share of the top's
    "square": 0.75,  # the section's sides: 1 an ellipse, lower squarer
    "clear": 0.0015,  # m, the underside's gap over the lip (it lies on it, its top well above the lip's)
    "dip": 0.007,  # m, how far the root end sinks below the lip's top inside the mouth
    "root_w": 0.68,  # the width at the root (inside the mouth), a share of `width`: a spatula, widest near the tip
    "widest": 0.75,  # where it is widest, a share of the length
    # M14b (PR #251's review: the tip was knife-thin in profile): over the tip the half thickness follows
    # c ** pow * (1 - taper * q) (q 0 to 1 along the tip, c the plan's quarter ellipse), never below `floor` of the
    # half thickness before the last station: plump with a round end, as mt2's
    "tip": {"pow": 0.25, "taper": 0.2, "floor": 0.5},
    # M14b: alien_mouths.drape's smoothing passes and how far the section's sides sink into the lip (m)
    "drape": {"sink": 0.002, "passes": 10},  # sink: `clear` plus 0.5 mm into the lip
    "shapes": {
        # x: the tongue's centre line off the mouth's centre, a share of the lips' outer half width (+: the viewer's
        # right); inside (m): how far it reaches back behind the lip's top; wrap (deg); hang (m); slant, roll (deg);
        # w (M14b): the width, a share of `width` (O's tongue narrower than its ring's hole)
        "rest": {"x": 0.28, "inside": 0.020, "wrap": 80.0, "hang": 0.007, "slant": 16.0, "roll": 10.0},
        "M": {"x": 0.0, "inside": 0.014, "wrap": 55.0, "hang": 0.0, "slant": 0.0, "roll": 0.0},
        "small": {"x": 0.04, "inside": 0.020, "wrap": 45.0, "hang": 0.0, "slant": 0.0, "roll": 0.0},
        "A": {"x": 0.12, "inside": 0.022, "wrap": 85.0, "hang": 0.006, "slant": -6.0, "roll": -4.0},
        "E": {"x": 0.45, "inside": 0.020, "wrap": 82.0, "hang": 0.004, "slant": 24.0, "roll": 16.0},
        "O": {"x": 0.0, "inside": 0.016, "wrap": 78.0, "hang": 0.0, "slant": 0.0, "roll": 0.0, "w": 0.75},
    },
}
STATIONS = 40  # along the spine
AROUND = 24  # vertices per section

# The teeth: (x m off the centre line, width m, visible height m, tilt deg); depth, the tuck into the lip (m), the
# superellipsoid's exponent (smaller: boxier), the shapes that show them (O's small hole and M's closed lips none).
TEETH = {
    "upper": [(-0.0135, 0.0105, 0.0070, -4.0), (0.0125, 0.0095, 0.0062, 5.0)],
    "lower": [(-0.0240, 0.0090, 0.0075, -7.0)],
    "depth": 0.0060, "tuck": 0.0030, "round": 0.45, "front": 0.5, "max_open": 0.55,
    "shapes": ["rest", "small", "A", "E"],
    # M14b: per shape keys over the above (A: the sheet's two lower teeth at the opening's lower left, forward of the
    # lip's axis and tucked deeper: at the default tuck they floated over the ring's lower edge; the one at -24 mm sat
    # in the ring's side, out of sight)
    "per_shape": {"A": {"lower": [(-0.0200, 0.0090, 0.0075, -7.0), (-0.0130, 0.0072, 0.0058, 4.0)], "front": 0.9,
                        "tuck": 0.007}},
}


def merged(over: dict | None = None) -> dict:
    """TONGUE with `over` merged on top (`shapes` shape by shape, key by key)."""
    out = {k: v for k, v in TONGUE.items() if k != "shapes"}
    out["shapes"] = {k: dict(v) for k, v in TONGUE["shapes"].items()}
    for k, v in (over or {}).items():
        if k == "shapes":
            for s, sp in v.items():
                out["shapes"].setdefault(s, {}).update(sp)
        else:
            out[k] = v
    return out


def merged_teeth(over: dict | None = None) -> dict:
    out = dict(TEETH)
    out.update(over or {})
    return out


def teeth_for(t: dict, shape: str) -> dict:
    """M14b: the teeth settings of one shape: t with t["per_shape"][shape]'s keys on top."""
    out = {k: v for k, v in t.items() if k != "per_shape"}
    out.update((t.get("per_shape") or {}).get(shape, {}))
    return out


def shape_params(p: dict, shape: str) -> dict:
    """M14b: the tongue's settings for one shape: `width` times the shape's `w` (default 1)."""
    out = dict(p)
    out["width"] = p["width"] * p["shapes"][shape].get("w", 1.0)
    return out


def _smooth(a: float, b: float, x: float) -> float:
    if b <= a:
        return 1.0 if x >= b else 0.0
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def spine2d(radii: tuple, p: dict, sp: dict) -> tuple[list[tuple], float]:
    """The tongue's centre line in the lip roll's plane: points (f, u) (f forward of the roll's centre C, u up from
    it), sampled every arc length, and the arc length where it passes the roll's top (the flop weight starts there).
    radii (ra, rb): the centre line's ellipse about C, forward and up (the lip's depth and half height plus half the
    tongue's thickness and the clearance). Returns ([(f, u, s)], s_top), s the arc length from the root."""
    ra, rb = radii
    pts = []  # a dense polyline first
    n_in = 12
    for i in range(n_in):
        q = 1 - i / n_in  # M14: the root dips into the mouth (`dip`), so its end goes into the dark
        pts.append((-sp["inside"] * q, rb - p.get("dip", 0.0) * q * q))
    wrap = math.radians(max(0.0, sp["wrap"]))
    n_w = max(2, int(sp["wrap"] / 3))
    for i in range(n_w + 1):
        ph = wrap * i / n_w
        pts.append((ra * math.sin(ph), rb * math.cos(ph)))
    if sp["hang"] > 0:
        t = _norm((ra * math.cos(wrap), -rb * math.sin(wrap)))
        f0, u0 = pts[-1]
        n_h = max(2, int(sp["hang"] / 0.001))
        for i in range(1, n_h + 1):
            pts.append((f0 + t[0] * sp["hang"] * i / n_h, u0 + t[1] * sp["hang"] * i / n_h))
    # the round tip: the spine runs on by the tip's length along the last direction
    tip = 0.45 * p["width"]
    (fa, ua), (fb, ub) = pts[-2], pts[-1]
    d = math.hypot(fb - fa, ub - ua) or 1.0
    tdir = ((fb - fa) / d, (ub - ua) / d)
    for i in range(1, 7):
        pts.append((fb + tdir[0] * tip * i / 6, ub + tdir[1] * tip * i / 6))
    acc = [0.0]
    for a, b in zip(pts, pts[1:]):
        acc.append(acc[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    L = acc[-1]
    out = []
    j = 0
    for k in range(STATIONS + 1):
        s = L * k / STATIONS
        while j < len(acc) - 2 and acc[j + 1] < s:
            j += 1
        f = (s - acc[j]) / max(1e-12, acc[j + 1] - acc[j])
        out.append((pts[j][0] + (pts[j + 1][0] - pts[j][0]) * f, pts[j][1] + (pts[j + 1][1] - pts[j][1]) * f, s))
    return out, sp["inside"]


def profile(s: float, L: float, p: dict) -> tuple[float, float]:
    """The half width and the half thickness at arc length s of L: the root a little narrower, the last 0.45 width a
    round tip (a quarter ellipse in plan; in profile plump with a round end, p["tip"]: M14b, the old
    c ** 0.5 * (1 - 0.45 q) made a knife-thin blade; never thicker than wide)."""
    tip = 0.45 * p["width"]
    w = p["width"] / 2 * (p["root_w"] + (1 - p["root_w"]) * _smooth(0.0, p.get("widest", 0.5) * L, s))
    h = p["thick"] / 2
    if s > L - tip:
        q = min(1.0, (s - (L - tip)) / tip)
        c = math.sqrt(max(0.0, 1 - q * q))
        w *= c
        t = p.get("tip", {"pow": 0.5, "taper": 0.45, "floor": 0.0})
        f = c ** t["pow"] * (1.0 - t["taper"] * q)
        if q < 1.0:
            f = max(f, t["floor"])
        h = min(h * f, w)
    return w, h


def _norm(v):
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / n for c in v)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def frames(pts3: list[tuple]) -> list[tuple]:
    """Per station (T, S, N): the tangent, the side (x orthogonalised against T) and the top N = T x S (up inside the
    mouth, toward the viewer where it hangs)."""
    out = []
    n = len(pts3)
    for i in range(n):
        a, b = pts3[max(0, i - 1)], pts3[min(n - 1, i + 1)]
        T = _norm(tuple(q - r for q, r in zip(b, a)))
        X = (1.0, 0.0, 0.0)
        S = _norm(tuple(x - _dot(X, T) * t for x, t in zip(X, T)))
        N = _cross(T, S)
        out.append((T, S, N))
    return out


def world_spine(sp2d: list[tuple], s_top: float, x0: float, c_y: float, c_z: float, sp: dict) -> list[tuple]:
    """The 2D spine in the world at the tongue's x: (x, y, z), leaning sideways by `slant` past the lip's top."""
    sl = math.sin(math.radians(sp.get("slant", 0.0)))
    return [(x0 + sl * max(0.0, s - s_top), c_y - f, c_z + u) for f, u, s in sp2d]


def tongue_mesh(pts3: list[tuple], ss: list[float], s_top: float, p: dict, sp: dict):
    """The tongue's vertices, quad faces (and the two caps' triangles) and per vertex flop weight."""
    L = ss[-1]
    fr = frames(pts3)
    verts, flop, faces = [], [], []
    rings = []
    for (P, s, (T, S, N)) in zip(pts3, ss, fr):
        w, h = profile(s, L, p)
        ang = math.radians(sp.get("roll", 0.0)) * _smooth(s_top, L, s)
        ca, sa = math.cos(ang), math.sin(ang)
        S2 = tuple(ca * a + sa * b for a, b in zip(S, N))
        N2 = tuple(-sa * a + ca * b for a, b in zip(S, N))
        wt = max(0.0, (s - s_top) / max(1e-9, L - s_top)) ** 2 if s > s_top else 0.0
        gr = p.get("groove_root", 1.0)
        groove = p["groove"] * (gr + (1.0 - gr) * _smooth(s_top, s_top + 0.010, s))  # M14b: deep where it hangs
        ring = []
        for k in range(AROUND):
            ps = 2 * math.pi * k / AROUND
            c, sn = math.cos(ps), math.sin(ps)
            sx = w * math.copysign(abs(c) ** p["square"], c)
            if sn >= 0:
                sy = h * sn
                sy -= groove * h * math.exp(-(sx / max(1e-9, 0.22 * w)) ** 2) * sn ** 2
            else:
                sy = h * p["flat"] * sn
            ring.append(len(verts))
            verts.append(tuple(Pc + S2c * sx + N2c * sy for Pc, S2c, N2c in zip(P, S2, N2)))
            flop.append(wt)
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(AROUND):
            k2 = (k + 1) % AROUND
            faces.append((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]))
    for ring, P, last in ((rings[0], pts3[0], False), (rings[-1], pts3[-1], True)):
        c = len(verts)
        verts.append(tuple(P))
        flop.append(flop[ring[0]])
        for k in range(AROUND):
            a, b = ring[k], ring[(k + 1) % AROUND]
            faces.append((a, b, c) if last else (b, a, c))
    return verts, faces, flop


def tooth_mesh(centre: tuple, w: float, d: float, h: float, tilt_deg: float, rnd: float, n: int = 10):
    """A blunt tooth: a superellipsoid (exponent rnd: 1 an ellipsoid, smaller boxier) of w x d x h about centre,
    tilted by tilt_deg about the y axis. Returns (verts, faces) (quads and the poles' triangles)."""
    ta = math.radians(tilt_deg)
    ct, st = math.cos(ta), math.sin(ta)

    def sp(v, e):
        return math.copysign(abs(v) ** e, v)
    verts = [(centre[0] - st * h / 2, centre[1], centre[2] + ct * h / 2)]
    for i in range(1, n):
        th = math.pi * i / n  # from the top pole down
        rows = []
        for j in range(2 * n):
            ph = 2 * math.pi * j / (2 * n)
            x = w / 2 * sp(math.sin(th), rnd) * sp(math.cos(ph), rnd)
            y = d / 2 * sp(math.sin(th), rnd) * sp(math.sin(ph), rnd)
            z = h / 2 * sp(math.cos(th), rnd)
            rows.append((centre[0] + ct * x - st * z, centre[1] + y, centre[2] + st * x + ct * z))
        verts += rows
    verts.append((centre[0] + st * h / 2, centre[1], centre[2] - ct * h / 2))
    m = 2 * n
    faces = []
    for j in range(m):
        faces.append((0, 1 + (j + 1) % m, 1 + j))
    for i in range(n - 2):
        for j in range(m):
            a, b = 1 + i * m + j, 1 + i * m + (j + 1) % m
            faces.append((a, b, b + m, a + m))
    last = len(verts) - 1
    base = 1 + (n - 2) * m
    for j in range(m):
        faces.append((base + j, base + (j + 1) % m, last))
    return verts, faces


def tooth_boxes(edge_z, edge_y, opening_h: float, t: dict, cx: float = 0.0) -> list[dict]:
    """The teeth of one piece: edge_z(lip, x) the opening's upper ("upper") or lower ("lower") edge's height at x
    (off the mouth's centre cx), edge_y(lip, x, z) the depth of the tooth's front at the world x (alien_mouths:
    t["front"] of the lip's depth in front of its axis: a tooth set back in the mouth went dark in its AO); opening_h the opening's height at the centre (m). Each tooth hangs
    from (or stands on) its lip's inner edge, tucked t["tuck"] into the lip, its visible height at most
    t["max_open"] of the opening."""
    out = []
    for lip, sign in (("upper", -1.0), ("lower", 1.0)):
        for x, w, hv, tilt in t[lip]:
            vis = min(hv, t["max_open"] * opening_h)
            if vis < 0.0008:
                continue
            ze = edge_z(lip, x)
            z0, z1 = ze - sign * t["tuck"], ze + sign * vis
            zc = (z0 + z1) / 2
            yc = edge_y(lip, cx + x, ze) + t["depth"] / 2
            out.append({"lip": lip, "centre": (cx + x, yc, zc), "w": w, "d": t["depth"], "h": abs(z1 - z0), "tilt": tilt,
                        "visible_mm": round(vis * 1000, 1)})
    return out
