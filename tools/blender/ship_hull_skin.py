"""The manta's skin (art #263, hull lane step 1; docs/ship.md "The hull skin"): one continuous faceted surface from the
centre to the swept tips, cut into kit pieces. The EXTERIOR lane owns this file.

The half-span (east; the west mirrors x) is lofted through sections across x. Every section is the same loop of 14
(y, h) points, so the facets run as long creases from the body to the tips:

    0 lead edge, 1..2 the upper front slope, 3 the front eave, 4..5 the ridge, 6 the rear eave, 7..8 the upper rear
    slope, 9 trail edge, 10 lower rear, 11..12 the belly, 13 lower front

The rooms (ship.toml) give the inner envelope: the hall (rim r 3.72 to h 4.75, the spine above it), the mouth (the
opening's face cut out between x -1.3 and 1.3, under a brow), the corridors (eave 0.12 m outside their walls at h 3.95,
rising toward the hall), the tip rooms (r 2.41 window band h 1.5..3.4 at x 10.75). A variant (VARIANTS) gives the
outside: the lead and trail edges in plan, the edge heights, the nose, the spine and the swept tip. Past x 10.75 the
tip fairing is a revolve round the tip room's centre whose 90 deg profiles equal the loft's last section, with the
window cut within 65 deg of the axis and the wing plate reaching out under the sill to the swept tip point."""

from __future__ import annotations

import math

import ship_hull as H
import ship_lib as L

TIP_X = 10.75
R_WIN = 2.41           # the window band's radius (the window frame's pieces sit on it)
SILL, HEAD = 1.5, 3.4  # floor 1.0 + the tip window's sill 0.5 and head 2.4
EAVE_TIP = (2.28, 4.02)
RIDGE_TIP = (1.35, 4.42)
BELLY = 0.6
HALL_RIM = 3.72
HALL_EAVE = 4.75
MOUTH_X, MOUTH_Y = 1.3, -4.6

# Variant -> the outside. lead/trail: plan edge y by x (to the tip room's centre); hl: edge height by x; tip: the swept
# tip's outline round the tip centre (dx, dy) from the lead edge's end to the trail edge's end; nose: the cheek's lead
# y at x 1.5; brow: how far the brow overhangs the mouth; spine: the ridge height over the hall's middle; stern: the
# body's trail y at x 0.
VARIANTS = {
    "B": {"lead": [(1.5, -5.8), (4.0, -5.05), (8.0, -3.7), (TIP_X, -2.8)],
          "trail": [(0.0, 5.0), (3.0, 5.1), (6.0, 4.55), (8.0, 4.15), (TIP_X, 3.6)],
          "hl": [(1.5, 1.3), (TIP_X, 1.4)], "tip": [(1.95, -2.1), (2.47, -0.5), (2.48, 3.4), (1.7, 3.55)],
          "brow": 0.45, "spine": 5.85},
    "C": {"lead": [(1.5, -6.1), (4.0, -5.15), (8.0, -3.6), (TIP_X, -2.75)],
          "trail": [(0.0, 5.0), (3.0, 5.05), (5.0, 4.7), (8.0, 4.55), (TIP_X, 4.4)],
          "hl": [(1.5, 1.25), (TIP_X, 1.38)], "tip": [(1.95, -2.05), (2.47, -0.4), (2.48, 4.45), (1.2, 4.45)],
          "brow": 0.5, "spine": 5.9},
    "D": {"lead": [(1.5, -5.9), (4.0, -5.2), (8.0, -3.9), (TIP_X, -2.95)],
          "trail": [(0.0, 5.0), (3.0, 5.15), (6.0, 4.75), (8.0, 4.3), (TIP_X, 3.75)],
          "hl": [(1.5, 1.15), (6.0, 1.2), (TIP_X, 1.3)], "tip": [(2.05, -2.2), (2.47, -0.5), (2.48, 3.6),
                                                                   (1.7, 3.75)],
          "brow": 0.55, "spine": 6.05},
    "E": {"lead": [(1.5, -5.9), (4.0, -5.1), (8.0, -3.7), (TIP_X, -2.8)],
          "trail": [(0.0, 5.0), (3.0, 5.1), (6.0, 4.95), (8.0, 4.85), (TIP_X, 4.7)],
          "hl": [(1.5, 1.2), (TIP_X, 1.4)], "tip": [(1.95, -2.1), (2.47, -0.5), (2.48, 5.55), (1.1, 5.1)],
          "brow": 0.5, "spine": 5.95, "keel": 0.35},
    "F": {"lead": [(1.5, -6.3), (4.0, -5.5), (8.0, -4.1), (TIP_X, -3.0)],
          "trail": [(0.0, 5.0), (3.0, 5.15), (6.0, 5.05), (8.0, 5.0), (TIP_X, 4.9)],
          "hl": [(1.5, 1.1), (6.0, 1.2), (TIP_X, 1.38)], "tip": [(2.1, -2.2), (2.47, -0.6), (2.48, 5.9),
                                                                   (1.2, 5.4)],
          "brow": 0.55, "spine": 6.05, "keel": 0.35},
}
DEFAULT = "E"
STATIONS = {"body": [0.0, 0.65, MOUTH_X, 1.5, 2.2, 2.9, 3.4, 3.75], "wing1": [3.75, 4.6, 5.5, 6.5],
            "wing2": [6.5, 7.5, 8.4, 9.1], "wing3": [9.1, 9.6, 10.1, 10.45, TIP_X]}


def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def _l2(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def envelope(x: float) -> tuple[float, float, float]:
    """The rooms at |x|: (half-extent in y the skin keeps outside, eave height, ridge height before the spine)."""
    hall = math.sqrt(max(0.0, HALL_RIM ** 2 - x * x))
    tip = math.sqrt(max(0.0, R_WIN ** 2 - (x - TIP_X) ** 2))
    if hall >= 1.6:
        return hall, HALL_EAVE, HALL_EAVE + 0.75 * (1 - x / HALL_RIM) + 0.1
    w = max(1.6, tip) + 0.12
    rise = _clamp((5.5 - x) / (5.5 - HALL_RIM))
    return w, 3.95 + 0.8 * rise, 4.15 + 0.7 * rise


def section(x: float, var: dict) -> list[tuple[float, float]]:
    """The loop of 14 (y, h) points at |x| (see the module's doc)."""
    w, eave, ridge = envelope(x)
    t = _clamp((x - 9.1) / (TIP_X - 9.1))
    wt = math.sqrt(max(0.0, R_WIN ** 2 - (x - TIP_X) ** 2))
    hl = H._lin(var["hl"], max(x, 1.5))
    spine = var["spine"]
    ridge = max(ridge, H._lin([(0.0, spine), (0.9, spine), (2.2, spine - 0.45), (HALL_RIM, HALL_EAVE + 0.1)], x)
                if x < HALL_RIM else ridge)
    ridge = ridge + (RIDGE_TIP[1] - ridge) * t
    rw = 0.55 * w + (RIDGE_TIP[0] - 0.55 * w) * t
    if x < HALL_RIM:
        rw = max(0.35, H._lin([(0.0, 0.7), (0.9, 0.7), (HALL_RIM, 0.5 * w)], x))
    keel = var.get("keel", BELLY)
    belly = H._lin([(0.0, keel), (2.4, keel + 0.5 * (BELLY - keel)), (HALL_RIM, BELLY)], x)
    yl = H._lin(var["lead"], x) if x >= 1.5 else MOUTH_Y
    yt = H._lin(var["trail"], x)
    ht = 2.45 if x < 3.0 else hl
    pts = {}
    if x <= MOUTH_X + 1e-6:  # the mouth: the opening's face under the brow
        pts[13], pts[0], pts[1] = (MOUTH_Y, 0.95), (MOUTH_Y, 2.3), (MOUTH_Y, 3.65)
        pts[2], pts[3] = (MOUTH_Y - var["brow"], 3.92), (-4.05, 4.72)
        pts[4] = (-2.6, ridge)
        pts[12] = (-4.45, belly)
    else:
        e = (yl, hl)
        v = (-(w + 0.12) + (-EAVE_TIP[0] + (w + 0.12)) * t, eave + (EAVE_TIP[1] - eave) * t)
        if x < HALL_RIM:
            v = (-(w + 0.12), HALL_EAVE)
        a = _l2(e, v, 0.38)
        b = _l2(e, v, 0.72)
        a = _l2((a[0], a[1] + 0.1), (-wt, SILL), t)
        b = _l2((b[0], b[1] + 0.08), (-wt + 0.03, HEAD), t)
        pts[0], pts[1], pts[2], pts[3] = e, a, b, v
        pts[4] = (-rw, ridge) if x >= HALL_RIM else (min(-2.6 * (1 - x / HALL_RIM), -rw), ridge)
        pts[12] = (-min(w, 2.2 + 1.5 * (1 - t)) if x >= HALL_RIM else -w * 0.92, belly)
        pts[13] = _l2(e, pts[12], 0.5)
        pts[13] = (pts[13][0], pts[13][1] - 0.12 * (1 - t))
    # the rear half
    if x < HALL_RIM:
        wr = math.sqrt(max(0.0, HALL_RIM ** 2 - x * x))
        e = (yt, ht)
        v = (wr + 0.12, HALL_EAVE)
        pts[5] = (max(3.4 * (1 - x / HALL_RIM), rw), ridge)
        pts[6] = v
        pts[7] = _l2(v, e, 0.45)
        pts[7] = (pts[7][0], pts[7][1] + 0.12)
        pts[8] = _l2(v, e, 0.8)
        pts[9] = e
        pts[11] = (wr * 0.92, belly)
        pts[10] = _l2(e, pts[11], 0.5)
        pts[10] = (pts[10][0], pts[10][1] - 0.15)
    else:
        e = (yt, ht)
        v = ((w + 0.12) + (EAVE_TIP[0] - (w + 0.12)) * t, eave + (EAVE_TIP[1] - eave) * t)
        a = _l2(e, v, 0.38)
        b = _l2(e, v, 0.72)
        pts[8] = _l2((a[0], a[1] + 0.1), (wt, SILL), t)
        pts[7] = _l2((b[0], b[1] + 0.08), (wt - 0.03, HEAD), t)
        pts[6], pts[5], pts[9] = v, (rw, ridge), e
        pts[11] = (min(w, 2.2 + 1.5 * (1 - t)), BELLY)
        pts[10] = _l2(e, pts[11], 0.5)
        pts[10] = (pts[10][0], pts[10][1] - 0.12 * (1 - t))
    return [pts[i] for i in range(14)]


def _loft(xs, var, side, skip=None):
    secs = [[(side * x, y, h) for y, h in section(x, var)] for x in xs]
    n = 14
    verts = [p for s in secs for p in s]
    faces = []
    for i in range(len(xs) - 1):
        for j in range(n):
            if skip and skip(xs[i], xs[i + 1], j):
                continue
            faces.append((i * n + j, i * n + (j + 1) % n, (i + 1) * n + (j + 1) % n, (i + 1) * n + j))

    def inner(c):
        loop = section(min(max(abs(c[0]), 0.0), TIP_X), var)
        return (c[0], sum(p[0] for p in loop) / n, 2.4)
    return verts, L.orient(verts, faces, inner)


def _mouth_skip(x0, x1, j):
    return x1 <= MOUTH_X + 1e-6 and j in (13, 0)


def tip_outline(var: dict) -> list[tuple[float, float]]:
    """The tip's plan outline round the tip centre (dx, dy), from the lead edge's end to the trail edge's end."""
    return [(0.0, H._lin(var["lead"], TIP_X)), *var["tip"], (0.0, H._lin(var["trail"], TIP_X))]


def _edge_r(var, ang):
    """The distance from the tip centre to the tip outline along the plan direction ang (0: +x, -90: north)."""
    d = (math.cos(ang), math.sin(ang))
    pts = tip_outline(var)
    best = None
    for a, b in zip(pts, pts[1:]):
        ex, ey = b[0] - a[0], b[1] - a[1]
        den = d[0] * ey - d[1] * ex
        if abs(den) < 1e-9:
            continue
        s = (a[0] * ey - a[1] * ex) / den
        u = (a[0] * d[1] - a[1] * d[0]) / den
        if s > 0 and -1e-6 <= u <= 1 + 1e-6:
            best = s if best is None else max(best, s)
    return best if best is not None else R_WIN


def tip_profile(var: dict, ang: float) -> list[tuple[float, float]]:
    """The fairing's (r, h) profile at plan angle ang, from the belly's centre to the crown; at +-90 deg it equals the
    loft's last section."""
    re = _edge_r(var, ang)
    hl = H._lin(var["hl"], TIP_X)
    lower = ((2.2 + re) / 2, (BELLY + hl) / 2)
    return [(0.0, BELLY), (2.2, BELLY), lower, (re, hl), (R_WIN, SILL), (R_WIN - 0.03, HEAD), EAVE_TIP, RIDGE_TIP,
            (0.0, RIDGE_TIP[1])]


def _tip(var, side, layout):
    room = next(r for r in layout["rooms"] if r["id"] == "tip_e")
    half = math.radians(room["window"]["half_angle_deg"])
    tip_ang = [math.atan2(dy, dx) for dx, dy in var["tip"]]
    angs = sorted(set([round(a, 6) for a in L.angles(-math.pi / 2, math.pi / 2, math.radians(10.0), (-half, half))]
                      + [round(a, 6) for a in tip_ang if -math.pi / 2 < a < math.pi / 2]))
    profs = [tip_profile(var, a) for a in angs]
    m = len(profs[0])
    verts = [(side * (TIP_X + r * math.cos(a)), r * math.sin(a), h) for a, prof in zip(angs, profs) for r, h in prof]
    faces = []
    for i in range(len(angs) - 1):
        mid = (angs[i] + angs[i + 1]) / 2
        for j in range(m - 1):
            if j == 4 and abs(mid) < half:  # the window band
                continue
            quad = [i * m + j, i * m + j + 1, (i + 1) * m + j + 1, (i + 1) * m + j]
            face = [q for k, q in enumerate(quad) if math.dist(verts[q], verts[quad[k - 1]]) > 1e-6]
            if len(face) >= 3:
                faces.append(tuple(face))
    faces = L.orient(verts, faces, lambda c: (side * TIP_X, 0.0, 2.4))
    return verts, faces


def hull_skin(args: dict, layout: dict) -> list:
    """One skin piece of the kit: args part ("body", "wing1", "wing2", "wing3" or "tip"), side (1 east, -1 west),
    variant (VARIANTS). Panelled with chamfered seams (ship_hull._skin)."""
    var = VARIANTS[args.get("variant", DEFAULT)]
    side = float(args.get("side", 1.0))
    part = args["part"]
    name = f"skin_{part}_{'e' if side > 0 else 'w'}"
    if part == "tip":
        v, f = _tip(var, side, layout)
        return H._skin(name, v, f, size=1.5)
    v, f = _loft(STATIONS[part], var, side, _mouth_skip if part == "body" else None)
    return H._skin(name, v, f)


def skin_stripes(args: dict, layout: dict) -> list:
    """The cyan diagonal light bars on a wing's lower lead facet (points 13..0 of the loft), one piece per side."""
    var = VARIANTS[args.get("variant", DEFAULT)]
    side = float(args.get("side", 1.0))
    count, x0, x1 = int(args.get("count", 16)), 4.2, 9.8

    def at(x, t):
        s = section(x, var)
        a, b = s[0], s[13]
        return (side * x, a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    out = []
    step = (x1 - x0) / count
    for k in range(count):
        xa = x0 + k * step
        quad = [at(xa, 0.12), at(xa + 0.16, 0.12), at(xa + 0.16 + 0.3, 0.7), at(xa + 0.3, 0.7)]
        n = H._norm(H._cross(H._sub(quad[1], quad[0]), H._sub(quad[3], quad[0])))
        if n[1] > 0:
            n = (-n[0], -n[1], -n[2])
        v = [H._add(q, n, 0.014) for q in quad] + [H._add(q, n, -0.03) for q in quad]
        out.append((v, [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]))
    return [L.part("stripes", *L.merge(*out), "glow_cyan")]


def clearance(var: dict) -> list[str]:
    """Room points outside the loft's sections (plain geometry, for the grid and the tests): the hall's rim at h 4.75,
    the corridors' top corners (y 1.45, h 3.85) and the tip room's wall top (r 2.25, h 3.8)."""
    def inside(poly, p):
        c = False
        for a, b in zip(poly, poly[1:] + poly[:1]):
            if (a[1] > p[1]) != (b[1] > p[1]):
                if p[0] < a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1]):
                    c = not c
        return c
    bad = []
    for part, xs in STATIONS.items():
        for x in xs:
            poly = section(x, var)
            need = []
            if x < 3.6:
                r = math.sqrt(max(0.0, 3.6 ** 2 - x * x))
                need += [(-r, 4.4), (r, 4.4), (-r, 1.0), (r, 1.0)]
            if 3.3 <= x <= 9.1:
                need += [(-1.45, 3.85), (1.45, 3.85), (-1.45, 0.8), (1.45, 0.8)]
            if x > 8.5:
                r = math.sqrt(max(0.0, 2.25 ** 2 - (x - TIP_X) ** 2))
                need += [(-r, 3.8), (r, 3.8), (0.0, 3.8 + 0.4 * max(0.0, 1 - ((x - TIP_X) / 2.05) ** 2))]
            if x <= MOUTH_X:
                need = [p for p in need if p[0] > MOUTH_Y + 0.05] + [(-4.4, 3.65)]
            bad += [f"x {x:.2f}: ({p[0]:.2f}, {p[1]:.2f})" for p in need if not inside(poly, p)]
    return bad


def outline(var: dict) -> list[tuple[float, float, float]]:
    """(x, lead y, trail y) rows of the footprint for ship.toml's [hull] (core up to the tip centre, then the tip)."""
    rows = [(x, section(x, var)[0][0] if x >= 1.5 else MOUTH_Y, H._lin(var["trail"], x))
            for x in [0.0, 1.5, 3.0, 4.0, 6.0, 8.0, 9.1]]
    tip = tip_outline(var)
    for dx in (0.6, 1.4, 1.9, 2.3):
        lo = min(_edge_r(var, a) * math.sin(a) for a in [math.radians(d) for d in range(-90, 91, 2)]
                 if abs(_edge_r(var, a) * math.cos(a) - dx) < 0.12) if dx < max(p[0] for p in tip) else 0.0
        hi = max(_edge_r(var, a) * math.sin(a) for a in [math.radians(d) for d in range(-90, 91, 2)]
                 if abs(_edge_r(var, a) * math.cos(a) - dx) < 0.12)
        rows.append((TIP_X + dx, lo, hi))
    return rows


for _name in ("hull_skin", "skin_stripes"):
    globals()[_name] = H._outward(globals()[_name])
