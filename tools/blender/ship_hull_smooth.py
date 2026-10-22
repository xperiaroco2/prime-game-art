"""The manta's smooth skin (art #263 v2, hull lane; docs/ship.md "The smooth skin"): one continuous, softly shaded
surface over the mirrored rooms, no plates and no seam grid. The HULL lane owns this file.

The skin is two height fields over one plan outline, the top and the belly, meeting at the outline's blade edge, and
the mouth's face (the recess in the low nose). Every height is a plain function of (x, y) (plan metres: x east,
y south, h up), symmetric in x:

    the wing:   a camber from the lead edge's height to the trail edge's (low at the body, curling up to the tips),
                plus and minus a half-thickness times a rounded chord profile (zero at the edges, at the tips)
    the rooms:  the hall's dome and the spine, the corridors' round tube, the tip rooms' pods (a steep outer face in
                the window's sector, softer elsewhere) and the belly under every floor: smooth-maxed with the wing, and
                faded to the camber within EDGE m of the outline so the top and the belly meet at the blade

The mesh: x stations across the body between the two tip room centres (chord samples from lead to trail), and past
each tip centre a polar patch round it (rays every ~5 deg, rings at fixed radii, then out to the outline), so the
tip window's hole is a clean band of rings between the window's head and sill within its half angle. A variant
(VARIANTS) sets the plan outline, the edge heights (the curl), the thickness and the spine."""

from __future__ import annotations

import math
import tomllib
from pathlib import Path

import ship_hull as H
import ship_lib as L

with (Path(__file__).resolve().parents[2] / "layouts" / "ship" / "ship.toml").open("rb") as _f:
    _SHIP = tomllib.load(_f)
_ROOM = {r["id"]: r for r in _SHIP["rooms"]}
FLOOR = _SHIP["deck"]["floor_h"]                                     # 0.6
HALL_R = _ROOM["hall"]["radius"]                                     # 4.0
HALL_TOP = FLOOR + _ROOM["hall"]["clear_h"]                          # 3.8
HALL_APEX = FLOOR + _ROOM["hall"]["apex_h"]                          # 4.4
COR_TOP = FLOOR + _ROOM["corridor_e"]["clear_h"]                     # 3.0
TIP_X = _ROOM["tip_e"]["centre"][0]                                  # 8.3
TIP_R = _ROOM["tip_e"]["radius"]                                     # 1.8
TIP_TOP = FLOOR + _ROOM["tip_e"]["clear_h"]                          # 3.1
TIP_APEX = FLOOR + _ROOM["tip_e"]["apex_h"]                          # 3.4
SILL = FLOOR + _ROOM["tip_e"]["window"]["sill_h"]                    # 1.6
HEAD = FLOOR + _ROOM["tip_e"]["window"]["head_h"]                    # 2.8
HALF = math.radians(_ROOM["tip_e"]["window"]["half_angle_deg"])     # 65 deg
SPAN_X = 13.75                                                       # the wing tips (span 27.5)
BELLY = FLOOR - 0.3                                                  # 0.3: under the 0.35 slab bottoms
MOUTH_Y, MOUTH_HW, MOUTH_TOP, MOUTH_SILL = -4.6, 1.25, COR_TOP + 0.15, FLOOR - 0.05
NOTCH = (1.62, 2.6)     # the lead edge sits on the mouth's plane to 1.62, back on the wing's line by 2.6
BROW = 3.45             # the top's edge over the mouth
POD_R = TIP_R + 0.15    # the tip room's wall outside (1.95)
POD_TOP = TIP_TOP + 0.2  # the pod's shoulder over the wall's top
EDGE = 0.9              # the rooms fade to the camber within this distance of the outline
STATION = 0.18          # x step between the body's stations
RAY = math.radians(5.0)

# Variant -> the outside. lead/trail: the plan edges y by x (spline); edge: the blade's height by x (the curl);
# t: the half-thickness by x (0 at the tip); spine: the ridge over the hall; front: the hall's fall toward the nose
# (> 1 lower); p: the chord profile's power (lower = rounder edges); stern: the trail edge's rise at the body.
VARIANTS = {
    "K": {"lead": [(0.0, -8.0), (2.0, -7.0), (4.0, -6.0), (6.0, -4.9), (8.3, -3.75), (11.0, -1.9), (SPAN_X, 0.6)],
          "trail": [(0.0, 5.8), (1.6, 5.6), (3.2, 5.0), (5.5, 4.5), (8.3, 4.1), (11.0, 2.9), (SPAN_X, 0.95)],
          "edge": [(0.0, 1.0), (4.0, 1.0), (8.3, 1.2), (10.1, 1.45), (12.0, 2.1), (SPAN_X, 3.2)],
          "t": [(0.0, 1.0), (4.0, 0.95), (8.3, 0.75), (10.1, 0.65), (12.0, 0.45), (SPAN_X, 0.0)],
          "spine": 4.95, "front": 1.15, "p": 0.6, "stern": 1.4},
    "L": {"lead": [(0.0, -6.15), (2.0, -5.75), (4.0, -5.15), (6.0, -4.45), (8.3, -3.75), (11.0, -1.5), (SPAN_X, 1.8)],
          "trail": [(0.0, 5.8), (1.6, 5.6), (3.2, 5.1), (5.5, 4.7), (8.3, 4.3), (11.0, 3.4), (SPAN_X, 2.2)],
          "edge": [(0.0, 0.95), (4.0, 0.95), (8.3, 1.0), (10.1, 1.0), (11.0, 1.1), (12.0, 1.65), (13.0, 2.8),
                   (SPAN_X, 3.8)],
          "t": [(0.0, 1.0), (4.0, 0.95), (8.3, 0.75), (10.1, 0.66), (11.0, 0.6), (12.0, 0.48), (13.0, 0.28),
                (SPAN_X, 0.0)],
          "spine": 5.1, "front": 1.2, "p": 0.65, "stern": 1.4},
    "M": {"lead": [(0.0, -7.6), (2.0, -6.8), (4.0, -5.8), (6.0, -4.8), (8.3, -3.75), (11.0, -2.1), (SPAN_X, 0.0)],
          "trail": [(0.0, 5.8), (1.6, 5.6), (3.2, 5.0), (5.5, 4.5), (8.3, 4.0), (11.0, 2.7), (SPAN_X, 0.4)],
          "edge": [(0.0, 1.05), (4.0, 1.05), (8.3, 1.2), (10.1, 1.4), (12.0, 1.9), (SPAN_X, 3.0)],
          "t": [(0.0, 1.0), (4.0, 0.95), (8.3, 0.8), (10.1, 0.75), (12.0, 0.55), (SPAN_X, 0.0)],
          "spine": 4.9, "front": 1.1, "p": 0.55, "stern": 1.4},
    "N": {"lead": [(0.0, -8.8), (2.0, -7.5), (4.0, -6.3), (6.0, -5.0), (8.3, -3.75), (11.0, -1.7), (SPAN_X, 1.2)],
          "trail": [(0.0, 5.8), (1.6, 5.6), (3.2, 5.0), (5.5, 4.5), (8.3, 4.1), (11.0, 3.0), (SPAN_X, 1.55)],
          "edge": [(0.0, 0.95), (4.0, 0.95), (8.3, 1.2), (10.1, 1.5), (12.0, 2.3), (SPAN_X, 3.6)],
          "t": [(0.0, 1.0), (4.0, 0.95), (8.3, 0.72), (10.1, 0.6), (12.0, 0.38), (SPAN_X, 0.0)],
          "spine": 5.05, "front": 1.25, "p": 0.75, "stern": 1.5},
}
DEFAULT = "L"   # grid smooth2: the highest curl and the most swept tips; its nose -8.4 -> -6.15 (ship --check: 14 +- 0.5 m with the nozzles)
# hull-3: L's wing stays low (edge 1.0..1.1, top about 1.7) out to x 11 and curls up only past x 12, so the tip window
# looks over the wing onto the clearing (the old L's wing top stood 2.39 at the band's sill, over eye height 2.25)
LIP = 0.06     # the window band's sill lip over SILL (the skin's top never under the room's sill at the band)


# --- smooth helpers ---------------------------------------------------------------------------------------------
def _spline(pts, x):
    """A C1 cubic Hermite through (x, y) points (slopes from the neighbours), held flat past the ends."""
    if x <= pts[0][0]:
        return pts[0][1]
    if x >= pts[-1][0]:
        return pts[-1][1]
    i = max(k for k in range(len(pts) - 1) if pts[k][0] <= x)
    (x0, y0), (x1, y1) = pts[i], pts[i + 1]

    def slope(k):
        a, b = pts[max(k - 1, 0)], pts[min(k + 1, len(pts) - 1)]
        return (b[1] - a[1]) / (b[0] - a[0])
    h = x1 - x0
    t = (x - x0) / h
    m0, m1 = slope(i) * h, slope(i + 1) * h
    return ((2 * t ** 3 - 3 * t ** 2 + 1) * y0 + (t ** 3 - 2 * t ** 2 + t) * m0 + (-2 * t ** 3 + 3 * t ** 2) * y1
            + (t ** 3 - t ** 2) * m1)


def _sstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def _smax(a, b, k):
    h = max(k - abs(a - b), 0.0) / k
    return max(a, b) + h * h * k / 4


def _smin(a, b, k):
    return -_smax(-a, -b, k)


# --- the shape ----------------------------------------------------------------------------------------------------
def lead(x, var):
    """The lead edge's plan y at |x|: the nose's point at x 0 (the top's brow overhangs the mouth's recess)."""
    return _spline(var["lead"], abs(x))


def trail(x, var):
    return _spline(var["trail"], abs(x))


def _mouth_w(x):
    return 1.0 - _sstep(*NOTCH, abs(x))


def edge_h(x, var):
    """(lead top, lead belly, trail) edge heights at |x|: the nose's edge rises to the brow over the mouth."""
    ax = abs(x)
    e = _spline(var["edge"], ax)
    m = _mouth_w(ax)
    top = e + (BROW - e) * m
    return top, top, e + var["stern"] * (1 - _sstep(1.6, 4.2, ax))


def _needs(x, y, var):
    """The rooms' top (the hall and the spine, the corridors, the tip pods) and the belly's ceiling."""
    ax = abs(x)
    rho = math.hypot(ax, y * (var["front"] if y < 0 else 1.0))
    hall = 4.75 * math.sqrt(max(0.0, 1 - (rho / 7.0) ** 4))
    along = _sstep(-6.0, -3.2, y) * (1 - 0.45 * _sstep(3.2, 6.0, y))
    spine = var["spine"] * math.exp(-(ax / 0.85) ** 2) * along
    nose = (BROW + 0.35) * (1 - _sstep(NOTCH[0], NOTCH[1] + 0.6, ax)) * (1 - _sstep(-4.0, -3.0, y))
    d = math.hypot(max(abs(y) - 1.0, 0.0), max(ax - 7.5, 0.0), max(2.0 - ax, 0.0))
    tube = 3.4 * math.sqrt(max(0.0, 1 - (d / 1.5) ** 2))
    dx, r = ax - TIP_X, math.hypot(ax - TIP_X, y)
    th = abs(math.atan2(y, dx))
    if r <= POD_R:
        pod = POD_TOP + 0.3 * (1 - (r / POD_R) ** 2) ** 2
    else:
        wf = 0.9 + 0.7 * _sstep(math.radians(70), math.radians(100), th)  # steep in the window's sector
        pod = POD_TOP * (1 - min(1.0, (r - POD_R) / wf) ** 2) ** 0.5
    top = _smax(_smax(_smax(hall, nose, 0.4), spine, 0.5), _smax(tube, pod, 0.6), 0.5)
    dist = min(max(math.hypot(ax, y) - 4.2, 0.0), math.hypot(max(abs(y) - 1.7, 0.0), max(ax - 7.5, 0.0), max(2.0 - ax, 0.0)),
               max(r - 2.1, 0.0))
    return top, BELLY + 1.5 * (dist / 1.5) ** 2


def _chord(x, y, var):
    lo, hi = lead(x, var), trail(x, var)
    u = (y - lo) / (hi - lo) if hi > lo else 0.5
    return max(0.0, min(1.0, u)), min(y - lo, hi - y)


def heights(x, y, var):
    """(top, belly) at plan (x, y)."""
    u, dist = _chord(x, y, var)
    lt, lb, tr = edge_h(x, var)
    ct, cb = lt + (tr - lt) * u, lb + (tr - lb) * u
    t = _spline(var["t"], abs(x))
    f = (4 * u * (1 - u)) ** var["p"]
    e = _sstep(0.0, EDGE, dist)
    need, ceil = _needs(x, y, var)
    top = _smax(ct + t * f, ct + e * (need - ct), 0.35 * e + 1e-6)
    dx = abs(x) - TIP_X
    rr, th = math.hypot(dx, y), abs(math.atan2(y, dx))
    lip = (SILL + LIP) * (1 - _sstep(_RS + 0.02, _RS + 0.32, rr)) * (1 - _sstep(HALF + 0.05, HALF + 0.3, th))
    top = _smax(top, lip, 0.12)
    bot = _smin(cb - 0.7 * t * f, cb + e * (ceil - cb), 0.3 * e + 1e-6)
    return top, max(bot, 0.22)


def pod_r(h):
    """The pod's window-sector radius where its outer face passes height h (the band's rings)."""
    return POD_R + 0.9 * math.sqrt(max(0.0, 1 - (h / POD_TOP) ** 2))


_RS = pod_r(SILL - 0.05)   # the band's sill ring


# --- the mesh -----------------------------------------------------------------------------------------------------
def _edge_r(var, ang):
    """Distance from the tip centre to the outline along plan direction ang (0 east, -90 deg north)."""
    xs = [TIP_X + k * (SPAN_X - TIP_X) / 120 for k in range(121)]
    poly = [(x, lead(x, var)) for x in xs] + [(x, trail(x, var)) for x in reversed(xs)]
    d = (math.cos(ang), math.sin(ang))
    best = 0.0
    for a, b in zip(poly, poly[1:]):
        ax, ay = a[0] - TIP_X, a[1]
        ex, ey = b[0] - a[0], b[1] - a[1]
        den = d[0] * ey - d[1] * ex
        if abs(den) < 1e-12:
            continue
        s = (ax * ey - ay * ex) / den
        u = (ax * d[1] - ay * d[0]) / den
        if s > 0 and -1e-6 <= u <= 1 + 1e-6:
            best = max(best, s)
    return best


RINGS = [0.0, 0.55, 1.05, 1.45, 1.75, POD_R, 2.1]   # then the band's head and sill rings, then out to the outline
OUTER = 7


def _rings(var, ang):
    rh, rs = pod_r(HEAD + 0.05), pod_r(SILL - 0.05)
    inner = RINGS + [rh, (rh + rs) / 2, rs]
    re = _edge_r(var, ang)
    a = inner[-1]
    return inner + [a + (re - a) * math.sin(math.pi / 2 * k / OUTER) for k in range(1, OUTER + 1)]


BAND = (len(RINGS), len(RINGS) + 2)   # ring indices of the window band (head .. sill)


def planform(var):
    """The plan mesh: vertices (x, y) and quads (as index tuples), with the window band's quads marked."""
    angs = L.angles(-math.pi / 2, math.pi / 2, RAY, (-HALF, HALF))
    rn, rs_ = _rings(var, -math.pi / 2), _rings(var, math.pi / 2)
    K = len(rn) - 1
    ys_tip = [-r for r in reversed(rn)] + rs_[1:]                # the column at the tip centre, lead to trail
    lo, hi = lead(TIP_X, var), trail(TIP_X, var)
    u_tip = [(y - lo) / (hi - lo) for y in ys_tip]
    n = len(u_tip)
    u_cos = [0.5 * (1 - math.cos(math.pi * j / (n - 1))) for j in range(n)]
    marks = [0.0, MOUTH_HW, NOTCH[0], NOTCH[1], TIP_X]
    xs = sorted({round(v, 4) for v in [s * m for m in marks for s in (-1, 1)]
                 + [s * k * STATION for k in range(int(TIP_X / STATION) + 1) for s in (-1, 1)]
                 if abs(v) <= TIP_X})
    xs = [x for i, x in enumerate(xs) if i == 0 or x - xs[i - 1] > 0.05 or abs(x) in marks]
    key, verts, quads, band = {}, [], [], set()

    def vid(x, y):
        k = (round(x, 4), round(y, 4))
        if k not in key:
            key[k] = len(verts)
            verts.append((x, y))
        return key[k]
    grid, notch = [], set()
    lo, hi = lead(0.0, var), trail(0.0, var)
    jm = min(range(1, n - 1), key=lambda j: abs(lo + (hi - lo) * u_cos[j] - MOUTH_Y))   # the mouth's plane
    for x in xs:
        w = _sstep(6.0, TIP_X, abs(x))
        lo, hi = lead(x, var), trail(x, var)
        us = [u_cos[j] + (u_tip[j] - u_cos[j]) * w for j in range(n)]
        ys = [lo + (hi - lo) * u for u in us]
        if abs(x) <= NOTCH[0] + 1e-6:  # the recess: one chord line on the mouth's plane
            um = us[jm]
            ys = [lo + (MOUTH_Y - lo) * us[j] / um if j <= jm else MOUTH_Y + (hi - MOUTH_Y) * (us[j] - um) / (1 - um)
                  for j in range(n)]
        grid.append([vid(x, y) for y in ys])
    for a in range(len(xs) - 1):
        for j in range(n - 1):
            quads.append((grid[a][j], grid[a][j + 1], grid[a + 1][j + 1], grid[a + 1][j]))
            if j < jm and abs(xs[a]) <= NOTCH[0] + 1e-6 and abs(xs[a + 1]) <= NOTCH[0] + 1e-6:
                notch.add(len(quads) - 1)
    inn = [a for a, x in enumerate(xs) if abs(x) <= NOTCH[0] + 1e-6]
    walls = {"back": [grid[a][jm] for a in inn], "sides": [[grid[a][j] for j in range(jm + 1)] for a in (inn[0], inn[-1])]}
    for side in (1, -1):
        col = grid[-1] if side > 0 else grid[0]
        rays = []
        for i, ang in enumerate(angs):
            rr = _rings(var, ang)
            if i == 0:
                rays.append([col[K - k] for k in range(K + 1)])
            elif i == len(angs) - 1:
                rays.append([col[K + k] for k in range(K + 1)])
            else:
                rays.append([vid(side * (TIP_X + r * math.cos(ang)), r * math.sin(ang)) for r in rr])
        for i in range(len(angs) - 1):
            mid = (angs[i] + angs[i + 1]) / 2
            for k in range(K):
                q = (rays[i][k], rays[i][k + 1], rays[i + 1][k + 1], rays[i + 1][k])
                quads.append(q)
                if BAND[0] <= k < BAND[1] and abs(mid) < HALF:
                    band.add(len(quads) - 1)
    return verts, quads, band, notch, walls


def _orient(verts, faces, up):
    out = []
    for f in faces:
        f = [q for k, q in enumerate(f) if q != f[k - 1]]
        if len(f) < 3:
            continue
        nz = H._newell([verts[i] for i in f])[2]
        out.append(tuple(f) if (nz > 0) == up else tuple(reversed(f)))
    return out


def brow_under(x, y, top, var):
    """The nose's underside over the mouth's recess: 0.45 m under the top, meeting it at the nose's edge."""
    return min(top, max(MOUTH_TOP + 0.12, top - 0.45 * min(1.0, (y - lead(x, var)) / EDGE)))


def _walls(walls, bot, brow):
    """The recess's walls: the back wall on the mouth's plane (open over |x| < MOUTH_HW from MOUTH_SILL to MOUTH_TOP)
    and the two side walls at |x| NOTCH[0], each from the belly up to the brow's underside."""
    verts, faces = [], []

    def quad(a, b, c, d, n):
        k = len(verts)
        verts.extend([a, b, c, d])
        f = (k, k + 1, k + 2, k + 3)
        nn = H._newell([a, b, c, d])
        if abs(nn[0]) + abs(nn[1]) + abs(nn[2]) > 1e-8:
            faces.append(f if H._dot(nn, n) > 0 else tuple(reversed(f)))
    back = walls["back"]
    for i0, i1 in zip(back, back[1:]):
        (x0, y0, b0), (x1, y1, b1) = bot[i0], bot[i1]
        t0, t1 = brow[i0][2], brow[i1][2]
        lv0 = [b0, max(b0, MOUTH_SILL), min(max(b0, MOUTH_TOP), t0), t0]
        lv1 = [b1, max(b1, MOUTH_SILL), min(max(b1, MOUTH_TOP), t1), t1]
        for j in range(3):
            if j == 1 and abs((x0 + x1) / 2) < MOUTH_HW:
                continue
            quad((x0, y0, lv0[j]), (x1, y1, lv1[j]), (x1, y1, lv1[j + 1]), (x0, y0, lv0[j + 1]), (0.0, -1.0, 0.0))
    for side in walls["sides"]:
        for i0, i1 in zip(side, side[1:]):
            (x0, y0, b0), (x1, y1, b1) = bot[i0], bot[i1]
            n = (-1.0 if x0 > 0 else 1.0, 0.0, 0.0)
            quad((x0, y0, b0), (x1, y1, b1), (x1, y1, max(b1, brow[i1][2])), (x0, y0, max(b0, brow[i0][2])), n)
    return verts, faces


def skin(var):
    """The skin's surfaces as {name: (verts, faces)}: top (the window bands open), belly (open under the nose's
    recess), brow (the nose's underside over the recess), mouth (the recess's walls)."""
    pv, quads, band, notch, walls = planform(var)
    hs = [heights(x, y, var) for x, y in pv]
    top = [(x, y, h[0]) for (x, y), h in zip(pv, hs)]
    bot = [(x, y, h[1]) for (x, y), h in zip(pv, hs)]
    brow = [(x, y, brow_under(x, y, h[0], var)) for (x, y), h in zip(pv, hs)]
    return {"top": (top, _orient(top, [q for k, q in enumerate(quads) if k not in band], True)),
            "belly": (bot, _orient(bot, [q for k, q in enumerate(quads) if k not in notch], False)),
            "brow": (brow, _orient(brow, [q for k, q in enumerate(quads) if k in notch], False)),
            "mouth": _walls(walls, bot, brow)}


def _compact(verts, faces):
    """Only the vertices the faces use (the parts share the plan's vertex list; a loose vertex would widen Blender's
    bounds past the GLB's, which `ship --godot` compares)."""
    keep = sorted({i for f in faces for i in f})
    new = {i: k for k, i in enumerate(keep)}
    return [verts[i] for i in keep], [tuple(new[i] for i in f) for f in faces]


MATS = {"top":"hull_silver", "belly": "ext_silver_c", "brow": "ext_silver_c", "mouth": "ext_silver_c"}


def smooth_skin(args: dict, layout: dict) -> list:
    """One smooth skin piece (args part: top, belly, brow or mouth; variant), shaded smooth, one material."""
    part = args["part"]
    v, f = _compact(*skin(VARIANTS[args.get("variant", DEFAULT)])[part])
    p = L.part(f"skin_{part}", v, f, MATS[part], solid=False)
    p["smooth"] = True
    return [p]


smooth_skin = H._outward(smooth_skin)


# --- checks (plain Python: the grid and the fast tests) ----------------------------------------------------------
def clearance(var) -> list[str]:
    """Room points the skin does not clear: the hall's wall top and dome, the corridors' top corners, the tip rooms'
    wall tops and crowns, the mouth's brow, and the belly over every floor's slab."""
    bad = []

    def need(x, y, h, what):
        top = heights(x, y, var)[0]
        if top < h:
            bad.append(f"{what} ({x:.2f}, {y:.2f}): top {top:.2f} < {h:.2f}")

    def under(x, y, what):
        b = heights(x, y, var)[1]
        if b > FLOOR - 0.25:
            bad.append(f"{what} ({x:.2f}, {y:.2f}): belly {b:.2f} > {FLOOR - 0.25:.2f}")
    for d in range(0, 360, 10):
        a = math.radians(d)
        x, y = (HALL_R + 0.15) * math.cos(a), (HALL_R + 0.15) * math.sin(a)
        if not (abs(x) < NOTCH[0] and y < 0):
            need(x, y, HALL_TOP + 0.15, "hall wall")
        under(HALL_R * math.cos(a), HALL_R * math.sin(a), "hall slab")
    need(0.0, 0.0, HALL_APEX + 0.15, "hall dome")
    for x in (0.0, MOUTH_HW):
        for y in (MOUTH_Y - 0.3, MOUTH_Y):
            b = brow_under(x, y, heights(x, y, var)[0], var)
            if b < MOUTH_TOP + 0.1:
                bad.append(f"mouth brow ({x:.2f}, {y:.2f}): {b:.2f} < {MOUTH_TOP + 0.1:.2f}")
    for k in range(10):
        x = 3.7 + k * 0.4
        for y in (-1.5, 1.5):
            need(x, y, COR_TOP + 0.12, "corridor corner")
            under(x, y, "corridor slab")
        need(x, 0.0, COR_TOP + 0.2, "corridor roof")
    for d in range(0, 360, 10):
        a = math.radians(d)
        need(TIP_X + POD_R * math.cos(a), POD_R * math.sin(a), TIP_TOP + 0.12, "tip wall")
        under(TIP_X + TIP_R * math.cos(a), TIP_R * math.sin(a), "tip slab")
    need(TIP_X, 0.0, TIP_APEX + 0.12, "tip crown")
    return bad


def measures(var) -> dict:
    """The silhouette's numbers: the outer wing's thickness at x 10.5 / 11.5 / 12.5 (max over the chord), the tip's
    height, the spine, and the smallest gap from the window band to the outline."""
    out = {}
    for x in (10.5, 11.5, 12.5):
        lo, hi = lead(x, var), trail(x, var)
        out[f"thick_{x}"] = max(heights(x, lo + (hi - lo) * k / 40, var)[0] - heights(x, lo + (hi - lo) * k / 40,
                                                                                      var)[1] for k in range(41))
    out["tip_h"] = _spline(var["edge"], SPAN_X)
    out["spine"] = heights(0.0, 0.0, var)[0]
    rs = pod_r(SILL - 0.05)
    out["band_gap"] = min(_edge_r(var, a) - rs for a in [-HALF + k * HALF / 13 for k in range(27)])
    return out


def outline_rows(var) -> list[list[float]]:
    """ship.toml [hull] rows: [x, lead y, trail y, edge h, top h at mid-chord, -1] across the half-span."""
    rows = []
    for x in (0.0, 2.0, 4.0, 6.0, TIP_X, 10.1, 11.0, 12.0, 13.0, SPAN_X):
        lo, hi = lead(x, var), trail(x, var)
        rows.append([x, round(lo, 2), round(hi, 2), round(_spline(var["edge"], x), 2),
                     round(heights(x, (lo + hi) / 2, var)[0], 2), -1])
    return rows
