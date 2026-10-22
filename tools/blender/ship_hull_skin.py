"""The manta's skin (art #263, hull lane; docs/ship.md "The hull skin"): one continuous faceted surface from the
centre to the lens tips, cut into kit pieces. The HULL lane owns this file.

The half-span (east; the west mirrors x) is lofted through sections across x. Every section is the same loop of 14
(y, h) points, so the facets run as long creases from the body to the tips:

    0 lead edge (the blade), 1..2 the upper front slope, 3 the front eave, 4..5 the ridge, 6 the rear eave, 7..8 the
    upper rear slope, 9 trail edge, 10 lower rear, 11..12 the belly, 13 lower front

Launch 3 (manager update 2): the heights come from ship.toml (deck 0.6, corridors 2.4, tip rooms 2.5, the hall 3.2 /
3.8), and no outside face stands within ~25 deg of vertical (steep()). The rooms give the inner envelope
(clearance()); a variant (VARIANTS) gives the outside: the lead and trail edges in plan, the blade's height by x (low
at the body, rising to the tip's blade), the crest falling from the spine to the tips, the nose and the swept tip.
Past x 10.75 the tip fairing is a lens revolved round the tip room's centre: its lower and upper faces meet in a sharp
horizontal blade edge at about the room's mid-height, 0.7 m past the room's wall (r 3.0: span 27.5 m); the window is a
slanted band cut into the lens's upper face within 65 deg of the axis; its 90 deg profiles equal the loft's last
section."""

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
COR_TOP = FLOOR + _ROOM["corridor_e"]["clear_h"]                     # 3.0, the corridor's ceiling
TIP_TOP = FLOOR + _ROOM["tip_e"]["clear_h"]                          # 3.1, the tip room's wall top
TIP_APEX = FLOOR + _ROOM["tip_e"]["apex_h"]                          # 3.4
HALL_TOP = FLOOR + _ROOM["hall"]["clear_h"]                          # 3.8, the hall's rim
HALL_APEX = FLOOR + _ROOM["hall"]["apex_h"]                          # 4.4
TIP_X = 10.75
R_WALL = 2.3           # the tip room's wall, outside
R_WIN = 2.3            # the window frame's radius (the inside's glass stands inside it)
SILL = FLOOR + _ROOM["tip_e"]["window"]["sill_h"]
HEAD = FLOOR + _ROOM["tip_e"]["window"]["head_h"]
EAVE_TIP = (2.24, TIP_TOP + 0.1)                                    # the lens's upper face meets the roof here
RIDGE_TIP = (1.0, TIP_APEX + 0.22)
BELLY = FLOOR - 0.3                                                  # 0.3: under the 0.35 slab bottoms
HALL_RIM = 3.72
HALL_EAVE = HALL_TOP + 0.3
COR_W = 1.6            # the corridor's wall outside (1.45) and a margin
MOUTH_X, MOUTH_Y = 1.3, -4.6
LEAN = math.tan(math.radians(25.0))   # no outside face steeper than this (dy / dh)

# Variant -> the outside. lead/trail: plan edge y by x (to the tip room's centre); hl: the blade's height by x (to the
# tip centre); blade: the lens's blade height in the window's direction; crest: the ridge by x (from the hall's rim to
# the tip); tip: the swept tip's outline round the tip centre (dx, dy) from the lead edge's end to the trail edge's end
# (r 3.0 in the window's sector); brow: how far the brow overhangs the mouth; spine: the ridge over the hall's middle.
VARIANTS = {
    "G": {"lead": [(1.5, -6.3), (4.0, -5.5), (8.0, -4.1), (TIP_X, -3.0)],
          "trail": [(0.0, 5.0), (3.0, 5.15), (6.0, 5.05), (8.0, 5.0), (TIP_X, 4.9)],
          "hl": [(1.5, 0.95), (6.0, 1.2), (TIP_X, 1.6)], "blade": 1.7,
          "crest": [(HALL_RIM, 4.35), (6.0, 3.85), (TIP_X, 3.62)],
          "tip": [(2.25, -2.05), (2.9, -0.9), (3.0, 0.0), (2.9, 1.0), (2.6, 2.4), (1.6, 4.9)],
          "brow": 0.9, "spine": 4.95},
    "H": {"lead": [(1.5, -6.6), (4.0, -5.7), (8.0, -4.2), (TIP_X, -3.0)],
          "trail": [(0.0, 5.0), (3.0, 5.2), (6.0, 5.2), (8.0, 5.2), (TIP_X, 5.1)],
          "hl": [(1.5, 0.85), (6.0, 1.05), (TIP_X, 1.6)], "blade": 1.75,
          "crest": [(HALL_RIM, 4.2), (5.0, 3.8), (TIP_X, 3.62)],
          "tip": [(2.25, -2.05), (2.9, -0.9), (3.0, 0.0), (2.9, 1.0), (2.5, 2.8), (1.4, 5.9)],
          "brow": 1.1, "spine": 4.85},
    "I": {"lead": [(1.5, -6.9), (4.0, -5.8), (8.0, -4.2), (TIP_X, -3.0)],
          "trail": [(0.0, 5.0), (3.0, 5.15), (6.0, 4.9), (8.0, 4.7), (TIP_X, 4.4)],
          "hl": [(1.5, 1.05), (TIP_X, 1.6)], "blade": 1.65,
          "crest": [(HALL_RIM, 4.45), (8.0, 3.75), (TIP_X, 3.62)],
          "tip": [(2.25, -2.05), (2.9, -0.9), (3.0, 0.0), (2.85, 1.2), (2.3, 3.0), (1.3, 4.4)],
          "brow": 0.8, "spine": 5.1},
    "J": {"lead": [(1.5, -6.5), (4.0, -5.4), (8.0, -3.9), (TIP_X, -3.0)],
          "trail": [(0.0, 5.0), (3.0, 5.2), (6.0, 5.3), (8.0, 5.4), (TIP_X, 5.4)],
          "hl": [(1.5, 0.9), (4.0, 0.95), (8.0, 1.2), (TIP_X, 1.6)], "blade": 1.7,
          "crest": [(HALL_RIM, 4.3), (5.5, 3.75), (TIP_X, 3.62)],
          "tip": [(2.25, -2.05), (2.9, -0.9), (3.0, 0.0), (2.95, 1.0), (2.75, 3.0), (1.8, 6.4)],
          "brow": 1.0, "spine": 4.9},
}
DEFAULT = "J"                 # launch 3 grid (grid/hull31): the most swept tips, the spine standing out
LOWER = (9, 10, 11, 12, 13)   # the loop's faces from the trail edge round the belly to the lead edge
LOWER_MATS = ("ext_silver_c", "ext_silver_c", "leg_metal")
STATIONS = {"body": [0.0, 0.65, MOUTH_X, 1.5, 2.2, 2.9, 3.4, 3.75], "wing1": [3.75, 4.6, 5.5, 6.5],
            "wing2": [6.5, 7.5, 8.4, 9.1], "wing3": [9.1, 9.6, 10.1, 10.45, TIP_X]}


def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def _l2(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _half(x: float, var: dict, s: int) -> dict:
    """One half of the loop at |x| (s -1 the front, +1 the rear) away from the mouth: the blade e, the slope's points a
    and b, the eave v, the ridge r, the lower face low and the belly's edge, as (y, h)."""
    hall = math.sqrt(max(0.0, HALL_RIM ** 2 - x * x))
    wt = math.sqrt(max(0.0, R_WALL ** 2 - (x - TIP_X) ** 2))
    t = _clamp((x - 9.1) / (TIP_X - 9.1))
    crest = H._lin(var["crest"], max(x, HALL_RIM))
    if x < HALL_RIM:
        ridge = H._lin([(0.0, var["spine"]), (0.9, var["spine"]), (2.2, var["spine"] - 0.35),
                        (HALL_RIM, max(crest, HALL_EAVE + 0.1))], x)
        w, eave = hall + 0.12, HALL_EAVE
        rw = max((3.4 if s > 0 else 2.6) * (1 - x / HALL_RIM), H._lin([(0.0, 0.7), (HALL_RIM, 0.5 * w)], x))
    else:
        rise = _clamp((5.0 - x) / (5.0 - HALL_RIM))
        w = max(COR_W, wt + 0.05)
        eave = max(COR_TOP + 0.08, crest - 0.45) + 0.25 * rise
        ridge, rw = crest, 0.55 + 0.3 * rise
        # toward the tip the eave and the ridge become the lens's roof (EAVE_TIP, RIDGE_TIP)
        w, eave = w + (EAVE_TIP[0] - w) * t, eave + (EAVE_TIP[1] - eave) * t
        ridge, rw = ridge + (RIDGE_TIP[1] - ridge) * t, rw + (RIDGE_TIP[0] - rw) * t
    edge_y = H._lin(var["lead"], max(x, 1.5)) if s < 0 else H._lin(var["trail"], x)
    hl = H._lin(var["hl"], max(x, 1.5))
    if s > 0 and x < 3.0:
        hl = max(hl, 2.2)  # the stern under the nozzle housing
    e = (edge_y, hl)
    v = (s * w, eave)
    a = _l2(e, v, 0.38)
    b = _l2(e, v, 0.72)
    a, b = (a[0], a[1] + 0.1), (b[0], b[1] + 0.08)
    # toward the tip the slope's two points become the window band's edges on the lens's upper face
    a, b = _l2(a, _l2(e, v, 0.15), t), _l2(b, _l2(e, v, 0.85), t)
    wb = hall + 0.1 if x < HALL_RIM else max(COR_W - 0.05, wt)
    # the lower face: from the belly's edge up to the blade; at the tip, the lens's lower face (never steeper than LEAN)
    low = _l2(e, (s * wb, BELLY), 0.5)
    low = (low[0], low[1] - 0.12 * (1 - t))
    lt = (edge_y - s * LEAN * (hl - (BELLY + 0.15)), BELLY + 0.15)
    low = _l2(low, lt, t)
    wb = min(wb, abs(low[0]) - 0.05)
    return {"e": e, "a": a, "b": b, "v": v, "r": (s * rw, ridge), "low": low, "belly": (s * wb, BELLY)}


def section(x: float, var: dict) -> list[tuple[float, float]]:
    """The loop of 14 (y, h) points at |x| (see the module's doc)."""
    f, r = _half(x, var, -1), _half(x, var, 1)
    pts = {0: f["e"], 1: f["a"], 2: f["b"], 3: f["v"], 4: f["r"], 5: r["r"], 6: r["v"], 7: r["b"], 8: r["a"],
           9: r["e"], 10: r["low"], 11: r["belly"], 12: f["belly"], 13: f["low"]}
    if x <= MOUTH_X + 1e-6:  # the mouth: the opening's face under the brow (faces 13 and 0 are the hole)
        top = COR_TOP + 0.15
        pts[13], pts[0], pts[1] = (MOUTH_Y, FLOOR - 0.05), (MOUTH_Y, (FLOOR + top) / 2), (MOUTH_Y, top)
        pts[2] = (MOUTH_Y - var["brow"], top + 0.3)
        pts[3] = (MOUTH_Y + 0.4, HALL_EAVE + 0.2)
        pts[12] = (MOUTH_Y + 0.6, BELLY)
    return [pts[i] for i in range(14)]


def _turn_up(verts, faces, ref):
    """Faces of one loft or revolve share one winding: turn them all so faces[ref] (a ridge face) points up (+h).
    ship_lib.orient's inner-point test failed on the long flat blades far from the axis (tops turned down)."""
    p = [verts[i] for i in faces[ref]]
    n = H._newell(p)
    return faces if n[2] > 0 else [tuple(reversed(f)) for f in faces]


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

    ref = next(k for k, f in enumerate(faces) if f[0] % n == 4)
    return verts, _turn_up(verts, faces, ref)


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
    """The lens's (r, h) profile at plan angle ang, from the belly's centre to the crown; at +-90 deg it equals the
    loft's last section: belly, belly edge, lower face, blade, the window band's two edges, eave, ridge, crown."""
    re = _edge_r(var, ang)
    hl = H._lin(var["hl"], TIP_X)
    hb = hl + (var["blade"] - hl) * abs(math.cos(ang))
    blade = (re, hb)
    lower = (re - LEAN * (hb - (BELLY + 0.15)), BELLY + 0.15)
    wb = min(max(COR_W - 0.05, R_WALL), lower[0] - 0.05)
    return [(0.0, BELLY), (wb, BELLY), lower, blade, _l2(blade, EAVE_TIP, 0.15), _l2(blade, EAVE_TIP, 0.85),
            EAVE_TIP, RIDGE_TIP, (0.0, RIDGE_TIP[1] + 0.03)]


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
    ref = next(k for k, f in enumerate(faces) if f[0] % m == 6 and abs(verts[f[0]][2] - EAVE_TIP[1]) < 1e-6)
    return verts, _turn_up(verts, faces, ref)


def hull_skin(args: dict, layout: dict) -> list:
    """One skin piece of the kit: args part ("body", "wing1", "wing2", "wing3" or "tip"), side (1 east, -1 west),
    variant (VARIANTS). Panelled with chamfered seams (ship_hull._skin)."""
    var = VARIANTS[args.get("variant", DEFAULT)]
    side = float(args.get("side", 1.0))
    part = args["part"]
    name = f"skin_{part}_{'e' if side > 0 else 'w'}"
    if part == "tip":
        v, f = _tip(var, side, layout)
        m, low, size = len(tip_profile(var, 0.0)), (0, 1, 2), 1.5
    else:
        v, f = _loft(STATIONS[part], var, side, _mouth_skip if part == "body" else None)
        m, low, size = 14, LOWER, 1.7
    # two tones: the underside (the loop's lower facets) darker than the bright upper skin (turnaround front)
    under = [q for q in f if q[0] % m in low]
    upper = [q for q in f if q[0] % m not in low]
    return H._skin(name, v, upper, size=size) + H._skin(f"{name}_low", v, under, size=size, mats=LOWER_MATS)


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
    """Room points outside the loft's sections (plain geometry, for the grid and the tests): the hall's wall top and
    dome, the corridors' chamfered top corners and slab, the tip room's wall top and crown (ship.toml's heights)."""
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
                ring = HALL_TOP + (HALL_APEX - HALL_TOP) * (1 - 1.25 / 3.4)
                dome = H._lin([(0.0, HALL_APEX), (1.25, ring), (3.47, HALL_TOP)], x)
                need += [(-r, HALL_TOP + 0.15), (r, HALL_TOP + 0.15), (-r, FLOOR - 0.2), (r, FLOOR - 0.2),
                         (0.0, dome + 0.15)]
            if 3.3 <= x <= 9.1:
                need += [(-1.45, COR_TOP - 1.1), (1.45, COR_TOP - 1.1), (-1.1, COR_TOP + 0.2), (1.1, COR_TOP + 0.2),
                         (-1.45, FLOOR - 0.2), (1.45, FLOOR - 0.2)]
            if x > 8.5:
                r = math.sqrt(max(0.0, 2.25 ** 2 - (x - TIP_X) ** 2))
                need += [(-r, TIP_TOP + 0.05), (r, TIP_TOP + 0.05), (-r, FLOOR - 0.2), (r, FLOOR - 0.2),
                         (0.0, TIP_TOP + 0.05 + 0.35 * max(0.0, 1 - ((x - TIP_X) / 2.05) ** 2))]
            if x <= MOUTH_X:
                need = [p for p in need if p[0] > MOUTH_Y + 0.05] + [(-4.4, COR_TOP + 0.1)]
            bad += [f"x {x:.2f}: ({p[0]:.2f}, {p[1]:.2f})" for p in need if not inside(poly, p)]
    return bad


def steep(var: dict) -> list[str]:
    """The loft's outside faces steeper than ~25 deg from vertical (24 with rounding; the mouth's hole excepted):
    'x, face j: lean in deg' for every section."""
    out = []
    for xs in STATIONS.values():
        for x in xs:
            s = section(x, var)
            for j in range(14):
                if x <= MOUTH_X + 1e-6 and j in (13, 0):
                    continue
                (y0, h0), (y1, h1) = s[j], s[(j + 1) % 14]
                if abs(h1 - h0) < 1e-6:
                    continue
                lean = math.degrees(math.atan2(abs(y1 - y0), abs(h1 - h0)))
                if lean < 24.0:
                    out.append(f"x {x:.2f} j {j}: {lean:.0f}")
    return out


def outline(var: dict) -> list[tuple[float, float, float]]:
    """(x, lead y, trail y) rows of the footprint for ship.toml's [hull] (core up to the tip centre, then the tip)."""
    rows = [(x, section(x, var)[0][0] if x >= 1.5 else MOUTH_Y, H._lin(var["trail"], x))
            for x in [0.0, 1.5, 3.0, 4.0, 6.0, 8.0, 9.1]]
    tip = tip_outline(var)
    for dx in (0.6, 1.4, 2.0, 2.5, 2.85):
        lo = min(_edge_r(var, a) * math.sin(a) for a in [math.radians(d) for d in range(-90, 91, 2)]
                 if abs(_edge_r(var, a) * math.cos(a) - dx) < 0.12) if dx < max(p[0] for p in tip) else 0.0
        hi = max(_edge_r(var, a) * math.sin(a) for a in [math.radians(d) for d in range(-90, 91, 2)]
                 if abs(_edge_r(var, a) * math.cos(a) - dx) < 0.12)
        rows.append((TIP_X + dx, lo, hi))
    return rows


for _name in ("hull_skin", "skin_stripes"):
    globals()[_name] = H._outward(globals()[_name])
