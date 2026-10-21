"""M13 (art #196): the fangs mouth's two lower fangs (the mg2 sheet,
D:/prime-art-raw/2026-10-20-alien-face-sheets-2/mg2/). Plain Python (no Blender): the fang's shape and its spine in
front of the lips, used by alien_mouths.build_fangs and tested in tools/tests/test_alien_fangs_geom.py.

A fang is short, blunt, ivory and slightly curved, cute-tough and never gory: a rounded cone that rises from behind
the lower lip, stands in front of the upper lip (closed shapes) or in the opening's sides (A, E), and ends in a round
tip, never a point. FANG (a variant merges over it, merged()):

- x: a closed mouth's fang at this share of the lips' half width, on the lower lip's top (the sheet's rest: about
  0.78, "at the corners' inner thirds"); x_open: an open ring's (A, E) at this share of the opening's half width, on
  the lower lip's inner edge; O's fangs beside the pursed ring, o_gap (m) past its outer edge, o_drop of its half
  height below its centre (fang_roots, below; M14 moved it here from alien_mouths);
- length: base to tip, m, the same in every shape (the sheet: "the same size in every panel");
- radius: the base's half width, m; tip: the tip's radius as a share of it (a blunt, round end); pw: the taper's
  exponent (1: a straight cone; above 1 fuller toward the tip); flat: the
  section's front-to-back half axis as a share of the side-to-side one (a slightly flattened tooth);
- curve: the tip's sideways bend toward the face's centre line, as a share of the length (M13 read the sheet's fangs
  as leaning in; M13b: they lean out a little, so negative); lean: the tip's extra forward lean, as a share of
  the length;
- root: the share of the length below the root's top, hidden behind the lower lip (it rises from behind it); out: above the root, the share of the fang's front-to-back half axis in front of the lips' front (1:
  touching, the whole fang in front);
- lift: the root's top (where the fang leaves the lips) above the lower lip's top, m.

M13b (UPDATE 22: the M13 fangs read as small thin pins hanging in front of the lip, floating on the cheeks in O and
jumping between shapes):
- x_m: when set, every shape's fang stands this far from the face's centre line (m), the same in rest, M, small, A
  and E: the fangs sit on the lower jaw, which only drops (no sideways jump between pieces); x and x_open are then
  unused. O's pursed lips pull them in: O's fangs stand o_in of their base radius inside the pursed ring's outer edge
  (attached to its sides, not on the cheek);
- sink: below the root the axis sinks this share of the fang's front-to-back half axis behind the lips' front (the
  lower lip wraps the base: the fang rises out of it); blend: the share of the length over which the axis moves from
  sunk to standing in front, starting blend_at of it below the root;
- keep_front: above and below the lips the axis keeps the nearest lip's front (0: the skin's, M13; the philtrum
  slopes back, so the tip bent back toward the face and read as a flat top from the front);
- ring_drop: per open ring (A, E) the root's height, this share of the ring's half height below its centre (on the
  lower lip in the opening's corner; the jaw drop lowers it with the lower lip).
"""
from __future__ import annotations

import math

_FANG_M13 = {"x": 0.72, "x_open": 0.80, "o_gap": 0.002, "o_drop": 0.40, "length": 0.020, "radius": 0.0065, "tip": 0.50,
              "pw": 1.6, "flat": 0.90, "curve": 0.08, "lean": 0.0, "root": 0.30, "out": 0.70, "lift": 0.0,
              "sink": 0.5, "blend": 0.25, "blend_at": 0.5}
# M13b: the pick of M13b's grids (docs/godot.md, M13b) over M13's fangs.
FANG_M13B = {"x_m": 0.034, "o_in": 0.6, "o_drop": 0.80, "ring_drop": {"A": 0.40, "E": 0.25}, "length": 0.025,
             "radius": 0.0075, "tip": 0.42, "pw": 1.3, "flat": 0.95, "curve": -0.08, "root": 0.15, "out": 0.50,
             "sink": 1.0, "blend": 0.30, "blend_at": 0.0, "keep_front": 1}
FANG = dict(_FANG_M13, **FANG_M13B)
SEG = 18  # around
ROWS = 16  # along the body (base to the tip's cap)
CAP = 5  # rings of the round tip


def merged(over: dict | None = None) -> dict:
    out = dict(FANG)
    out.update(over or {})
    return out


def radius_at(t: float, p: dict) -> float:
    """The fang's half width at t (0 the base, 1 the tip's cap start): a soft cone, full at the base, p["tip"] of it
    at the tip, convex (no waist), so it reads as a stubby tooth."""
    t = max(0.0, min(1.0, t))
    return p["radius"] * (p["tip"] + (1.0 - p["tip"]) * (1.0 - t ** p.get("pw", 1.0)))


def spine(x0: float, z0: float, z1: float, ys: list[float], p: dict, side: float) -> list[tuple]:
    """len(ys) points (x, y, z; Blender: z up, the face toward -y) from the base (z0) up to the tip (z1) at the axis
    depths ys (axis_depths at those heights), the tip bent toward the face's centre line (side: +1 for a fang at
    x > 0) by p["curve"] x the length and forward by p["lean"] x the length, both growing with t^2 (a gentle, even
    curve)."""
    n = len(ys) - 1
    L = z1 - z0
    return [(x0 - side * p["curve"] * L * (i / n) ** 2, ys[i] - p["lean"] * L * (i / n) ** 2, z0 + L * i / n)
            for i in range(n + 1)]


def _norm(v):
    ln = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / ln for c in v)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def mesh(pts: list[tuple], p: dict) -> tuple[list[tuple], list[tuple]]:
    """The fang's vertices and quads/triangles along a spine: an elliptical section (side half axis radius_at, front
    half axis that times p["flat"]) per spine point, a closed base, and a round cap (a squashed half ellipsoid of the
    tip's section) at the tip."""
    n = len(pts) - 1
    verts, faces = [], []
    rings = []
    tans = []
    for i in range(n + 1):
        a, b = pts[max(0, i - 1)], pts[min(n, i + 1)]
        tans.append(_norm((b[0] - a[0], b[1] - a[1], b[2] - a[2])))
    for i, (c, t) in enumerate(zip(pts, tans)):
        fwd = (0.0, -1.0, 0.0)  # the face's front
        side = _norm(_cross(t, fwd))  # across, in the face's plane
        front = _norm(_cross(side, t))
        r = radius_at(i / n, p)
        ring = []
        for k in range(SEG):
            ph = 2 * math.pi * k / SEG
            off = [side[j] * r * math.cos(ph) + front[j] * r * p["flat"] * math.sin(ph) for j in range(3)]
            ring.append(len(verts))
            verts.append((c[0] + off[0], c[1] + off[1], c[2] + off[2]))
        rings.append((ring, side, front, r))
    for i in range(n):
        for k in range(SEG):
            k2 = (k + 1) % SEG
            faces.append((rings[i][0][k], rings[i][0][k2], rings[i + 1][0][k2], rings[i + 1][0][k]))
    b0 = len(verts)  # the base, closed (hidden behind the lower lip)
    verts.append(pts[0])
    for k in range(SEG):
        faces.append((rings[0][0][(k + 1) % SEG], rings[0][0][k], b0))
    ring, side, front, r = rings[-1]  # the round tip
    t = tans[-1]
    c = pts[-1]
    prev = ring
    for j in range(1, CAP + 1):
        a = (math.pi / 2) * j / (CAP + 1)
        rr, h = r * math.cos(a), r * 0.9 * math.sin(a)
        cur = []
        for k in range(SEG):
            ph = 2 * math.pi * k / SEG
            off = [side[q] * rr * math.cos(ph) + front[q] * rr * p["flat"] * math.sin(ph) + t[q] * h for q in range(3)]
            cur.append(len(verts))
            verts.append((c[0] + off[0], c[1] + off[1], c[2] + off[2]))
        for k in range(SEG):
            k2 = (k + 1) % SEG
            faces.append((prev[k], prev[k2], cur[k2], cur[k]))
        prev = cur
    top = len(verts)
    verts.append(tuple(c[q] + t[q] * r * 0.9 for q in range(3)))
    for k in range(SEG):
        faces.append((prev[k], prev[(k + 1) % SEG], top))
    return verts, faces


def axis_depths(zs: list[float], fronts: list[float | None], skin: list[float], radii: list[float], p: dict,
                z_root: float, straight: bool = False) -> list[float]:
    """The fang's axis depth (Blender y; the face toward -y, smaller is further forward) at each height zs (rising),
    from the lips' front at that height (fronts: None where no lip is hit at the fang's x: the opening, or above or
    below the lips) and the skin's front (skin). In an opening the front is interpolated between the lips above and
    below it; past the lips the skin's. Above z_root the axis stands p["out"] of its front half axis in front of the
    front (so the fang stands before the upper lip, never in it); below, it sinks to half its half axis behind the
    front (the root behind the lower lip); the result smoothed and kept in front where it must be. straight (O): one
    straight line through those depths, moved forward as a whole until the part above the root clears them."""
    n = len(zs)
    hit = [i for i, f in enumerate(fronts) if f is not None]
    fr = []
    for i in range(n):
        if fronts[i] is not None:
            fr.append(fronts[i])
            continue
        lo = max((j for j in hit if j < i), default=None)
        hi = min((j for j in hit if j > i), default=None)
        if lo is not None and hi is not None:
            f = (zs[i] - zs[lo]) / max(1e-9, zs[hi] - zs[lo])
            fr.append(fronts[lo] + (fronts[hi] - fronts[lo]) * f)
        elif p.get("keep_front") and (lo is not None or hi is not None):  # M13b: past the lips the nearest lip's
            fr.append(fronts[lo if lo is not None else hi])  # front (the skin's bent the tip back: a flat top)
        else:
            fr.append(skin[i])
    fr = [min(f, s) for f, s in zip(fr, skin)]  # never behind the skin
    want = []
    for z, f, r in zip(zs, fr, radii):
        h = r * p["flat"]
        u = max(0.0, min(1.0, (z - z_root) / max(1e-6, p.get("blend", 0.25) * p["length"]) + p.get("blend_at", 0.5)))
        u = u * u * (3 - 2 * u)
        want.append(f + h * (p.get("sink", 0.5) * (1 - u) - p["out"] * u))
    if not straight:
        y = list(want)
        for _ in range(6):  # smooth, then keep the part above the root in front
            y = [y[0]] + [(y[i - 1] + 2 * y[i] + y[i + 1]) / 4 for i in range(1, n - 1)] + [y[-1]]
            y = [min(v, w) if z > z_root else v for v, w, z in zip(y, want, zs)]
        return y
    # straight (O's fangs beside the ring): the least-squares line through the wanted depths, moved forward as a
    # whole until the part above the root clears its fronts (the smoothed axis kinked where the ring ends and the
    # cheek falls away: the far fang bent sideways at 3/4)
    m = len(zs)
    mz, my = sum(zs) / m, sum(want) / m
    sz = sum((z - mz) ** 2 for z in zs) or 1e-12
    k = sum((z - mz) * (w - my) for z, w in zip(zs, want)) / sz
    y = [my + k * (z - mz) for z in zs]
    push = max([v - w for v, w, z in zip(y, want, zs) if z > z_root] or [0.0])
    y = [v - max(0.0, push) for v in y]
    return y


def fang_roots(anchor, p):
    """M13: the two fangs' (x, z) where they leave the lips (their root's top), from the built piece's lips (anchor):
    a closed mouth's at p["x"] of the lips' half width on the lower lip's top (the crease); an open ring's (A, E) at
    p["x_open"] of the opening's half width on the lower lip's inner edge (they stand in the opening's sides); O's
    beside the pursed ring (p["o_gap"] past its outer edge), p["o_drop"] of its half height below its centre. M13b:
    with p["x_m"] every shape but O at that x about the face's centre line (closed: on the crease there, both at their
    mean height; A, E: p["ring_drop"][shape] of the ring's half height below its centre, on the lower lip in the
    opening's corner), O's attached to the ring (p["o_in"] of the base radius inside its outer edge)."""
    def z_at(pts, x):
        if x <= pts[0][0]:
            return pts[0][1]
        for (x0, z0), (x1, z1) in zip(pts, pts[1:]):
            if x0 <= x <= x1:
                return z0 + (z1 - z0) * (x - x0) / max(1e-9, x1 - x0)
        return pts[-1][1]
    cx, cz = anchor["centre"]
    out = []
    for side in (-1.0, 1.0):
        if anchor["form"] == "O":
            if p.get("x_m"):  # M13b: attached to the pursed ring's sides, o_in of the base radius inside its edge
                x = cx + side * (anchor["outer_hw"] - p["o_in"] * p["radius"])
            else:
                x = cx + side * (anchor["outer_hw"] + p["o_gap"])
            out.append((x, cz - p["o_drop"] * anchor["outer_hh"]))
            continue
        if p.get("x_m"):  # M13b: one place on the lower jaw in every shape, about the face's centre line
            x = side * p["x_m"]
        elif anchor["form"] == "tubes":
            x = cx + side * p["x"] * anchor["outer_hw"]
        else:
            x = cx + side * p["x_open"] * anchor["inner_hw"]
        if anchor["form"] == "ring" and p.get("x_m"):  # M13b: on the lower lip in the opening's corner, the
            # shape's ring_drop of the ring's half height below its centre (on the opening's edge at x they stood
            # beside the opening's top: a round opening is at its widest there)
            out.append((x, cz - p["ring_drop"].get(anchor["shape"], 0.3) * anchor["outer_hh"] + p["lift"]))
            continue
        out.append((x, z_at(anchor["lower"], x) + p["lift"]))
    if p.get("x_m") and anchor["form"] == "tubes":  # M13b: both at one height (the sheet's crease is 1.6 mm aslant)
        zm = sum(z for _x, z in out) / len(out)
        out = [(x, zm) for x, _z in out]
    return out
