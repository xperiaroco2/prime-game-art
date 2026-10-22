"""The hull's shape (art #263, rebuild B): the blockouts' variants and the hull the build makes from variant J, the
engineer's pick (art #263 comment 6340589162: F's outline, span 30 m, length 18.9 m with the nozzles, the wing tips
rounded in plan, radius 1.5 m, edge 0.3 m). Plain Python, no Blender: `ship --check`, the tests, the exterior lane's
builders (ship_hull_j.py, ship_hull_detail.py) and the blockout sheets (ship_hull_blockout.py) all read it.

The hull is the CONVEX HULL of a few design points (plan metres: x east, y south, h up), mirrored in x, so it is one
faceted shape with no local bump by construction (the spine, the nose wedge, the lead and trail edges, the rounded
tip, the stern face, the flat belly under every room; ship_hull_blockout.py's docstring has the parts), with the mouth
recess (|x| < 1.3, y < -4.6, h < 3.0) cut away. `facets()` holds its planes (n . p <= d inside) and polygons;
`surface()` the outer faces after the cut (the recess's faces turned into it); `skin()` a point's distance to the
outside (negative outside); `clearance()` every room's sampled outer surface against SKIN; `outline_rows()` the plan
footprint as ship.toml's [hull] rows.

Only variant P (DEFAULT since lens step 2: the union of convex parts at the end of this module, J's throat notch) is live: the build, `ship --check` and the exterior lane use it, and
`clearance(name, rooms)` samples every room of the layout it is given (ship_layout.hull_skin passes the checked
layout's rooms). The other variants are the blockouts' history (ship_hull_blockout.py, docs/ship.md "History"); they
keep v2's hall at the centre and sample the tip rooms at the old window's SILL and HEAD."""

from __future__ import annotations

import math
import sys
import tomllib
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHIP = tomllib.loads((ROOT / "layouts/ship/ship.toml").read_text(encoding="utf-8"))
RM = {r["id"]: r for r in SHIP["rooms"]}
FLOOR = SHIP["deck"]["floor_h"]                                        # 0.6
SLAB = FLOOR - SHIP["deck"]["slab_m"]                                  # 0.35: the slabs' bottoms
WALL = SHIP["deck"]["wall_m"]                                          # 0.2: a room's wall outside its clear size
ROOF = 0.12                                                            # a room's ceiling over its clear height
SKIN = 0.15                                                            # the least hull around every room
HALL_C = tuple(RM["hall"]["centre"])                                   # rebuild C: (0, -1)
HALL_R = RM["hall"]["radius"] + WALL                                   # 4.2
HALL_RIM = FLOOR + RM["hall"]["clear_h"] + ROOF                        # 3.92
HALL_APEX = FLOOR + RM["hall"]["apex_h"] + ROOF                        # 4.52
# lens step 1 (art#263): ship.toml's corridors and tip rooms are the lens rooms now (P's, outside J); J and the
# blockouts keep rebuild E's rooms, pinned here, so the live hull J builds as before until step 2 makes P the hull
J_ROOMS = {"corridor_e": {"axis": [[0.0, -0.4], [8.3, 3.6]], "along": [3.708, 8.219], "width": 3.0, "clear_h": 2.4},
           "tip_e": {"centre": [8.3, 3.6], "radius": 1.8, "clear_h": 2.5, "apex_h": 2.8}}
COR_S = tuple(J_ROOMS["corridor_e"]["along"])                          # (3.708, 8.219): the floor along the axis
COR_A = J_ROOMS["corridor_e"]["axis"]
COR_D = math.dist(*COR_A)                                              # 9.214: the hall's centre to the tip room's
COR_Y = RM["corridor_e"]["width"] / 2 + WALL                           # 1.7
COR_TOP = FLOOR + RM["corridor_e"]["clear_h"] + ROOF                   # 3.12
# rebuild C pins the outside: the design points read J's own numbers, no longer the rooms' (the inside moved 1 m
# forward under the same hull); the blockouts' variants without a throat keep v2's mouth recess box
MOUTH_X, MOUTH_Y, MOUTH_TOP = 1.3, -4.6, 3.0                           # the old recess (variants without a throat)
TIP_X = 8.3
PIN_HALL_R, PIN_TIP_R = 4.2, 2.0                                       # the belly rings' rooms (v2's hall, J's tips)
TIP_C_ROOM = tuple(J_ROOMS["tip_e"]["centre"])                              # rebuild C: (8.3, 3.0)
# rebuild C: the throat (ship.toml room "throat"); J's mouth notch is cut along it (`cutters`)
TH = RM["throat"]
TH_PTS = [tuple(p) for p in TH["points"]]                              # mouth (-+1.65, -7.1), hall corners (+-2.915, -3.252)
TH_ROOF_Y = TH["roof_y"]                                               # -5.5608: the ceiling from here aft
TH_TOP = FLOOR + TH["clear_h"] + ROOF                                  # 3.02: the throat's roof
TH_CH = TH["chamfer"]                                                  # walls vertical to 1.35, then 0.55 in
TIP_R = J_ROOMS["tip_e"]["radius"] + WALL                              # 2.0
TIP_RIM = FLOOR + J_ROOMS["tip_e"]["clear_h"] + ROOF                   # 3.22
TIP_APEX = FLOOR + J_ROOMS["tip_e"]["apex_h"] + ROOF                   # 3.52
# the old tip window's band (variant D only; the blockouts' tip walls are sampled at its heights, J's at the slab,
# mid-wall and rim)
WIN_HALF = math.radians(65.0)
SILL, HEAD = FLOOR + 1.0, FLOOR + 2.2                                  # 1.6, 2.8
RAMP = SHIP["ramp"]

BELLY = SLAB - 0.18                                                    # 0.17
SPINE_X = 1.3
SPINE = [(-4.6, 4.3), (-1.0, 4.82), (1.6, 4.82), (4.6, 4.3)]          # (plan y, h): the spine's profile, peak over the hall
NOSE = (2.2, -7.1, 2.0)                                                # the nose's edge (+-x, y, h): a wedge, the mouth cut in it
LEAD_PIVOT = (TIP_X, -3.4)                                             # the lead edge passes here: 1.4 m before the room
LEAD_SLOPE = (LEAD_PIVOT[1] - NOSE[1]) / (LEAD_PIVOT[0] - NOSE[0])
TRAIL_END = (4.4, 6.1, 2.3)
STERN_Y = 6.3
STERN = [(1.4, 3.75), (3.2, 3.25), (3.2, 0.95), (1.4, 0.7)]
NOZZLES = [(-2.75, 3.85, 2.15, 1.05, 3.25), (0.0, 4.25, 2.45, 1.2, 3.65), (2.75, 3.85, 2.15, 1.05, 3.25)]
CANOPY = (2.25, -3.6, 0.95, 1.35, 0.75)                                # x, y, half axes, height over the hull
LEGS = [(4.3, -4.5), (5.0, 4.7), (11.6, 0.4)]                         # plan spots, mirrored; a leg needs 0.45 m under
VARIANTS = {   # half span, tip height, the tip rooms' windows
    "A": {"half": 13.75, "tip_h": 3.3, "window": False},
    "B": {"half": 15.0, "tip_h": 3.15, "window": False},
    "C": {"half": 16.0, "tip_h": 3.2, "window": False},
    "D": {"half": 15.0, "tip_h": 1.2, "window": True},
    # The arrowhead (2026-10-22): the tip rooms moved back into the rear corners (the hall stays at the centre), the
    # corridors run straight along the diagonal from the hall's wall to them, the lead edge runs straight from the
    # nose to a tip at the rear corner and the trail edge near-straight from the tip in to a stern moved back.
    # Optional keys: tip_c the tip rooms' plan centre (x, y), tip_y the tip's plan y (else through LEAD_PIVOT),
    # nose_y the nose edge's y, nose_x its half width, stern_y the stern face's y (the stern block, the spine's rear and the pods move with
    # it), trail (x, h) the trail edge's stern corner.
    "E": {"half": 15.0, "tip_h": 3.25, "window": False, "tip_c": (8.3, 2.5), "tip_y": 4.4, "nose_y": -7.1,
          "stern_y": 8.8, "trail": (4.4, 2.6)},
    "F": {"half": 15.0, "tip_h": 3.25, "window": False, "tip_c": (8.3, 4.0), "tip_y": 5.7, "nose_y": -7.1,
          "stern_y": 10.2, "trail": (4.4, 2.6)},
    "G": {"half": 13.75, "tip_h": 3.3, "window": False, "tip_c": (8.3, 4.0), "tip_y": 5.4, "nose_y": -8.6,
          "stern_y": 10.2, "trail": (4.4, 2.6)},
    # The true triangle (2026-10-22): the trail edge straight across, level with the tips (a blunt back face over
    # the rear rooms, thinning out to the tips); only the nozzle pods stick out behind it. trail (x, h): the back
    # edge's corner outboard of the tip room, at stern_y - 0.2. I: the nose edge narrowed to the mouth's width plus
    # its walls and skin (nose_x), on the lead edge's line, so the nose comes to a point.
    "H": {"half": 15.0, "tip_h": 3.25, "window": False, "tip_c": (8.3, 4.0), "tip_y": 6.1, "nose_y": -7.1,
          "stern_y": 6.4, "trail": (10.6, 3.6)},
    "I": {"half": 15.0, "tip_h": 3.25, "window": False, "tip_c": (8.3, 4.0), "tip_y": 6.1, "nose_y": -7.67,
          "nose_x": MOUTH_X + WALL + SKIN, "stern_y": 6.4, "trail": (10.6, 3.6)},
    # Rounded tips on F's outline (2026-10-22): tip_r the tip's plan radius (an arc tangent to the lead and trail
    # edges, the corner pushed out along the lead edge so the span stays), tip_e the arc's half thickness about the
    # edge's height, lip the radius of a rounded lip along the arc and both edges (the edge seen end-on is a half
    # round 2 * lip thick), smooth the hull smooth-shaded (normals smooth below SMOOTH_DEG, weighted by face area).
    "J": {"half": 15.0, "tip_h": 3.25, "window": False, "tip_c": (8.3, 4.0), "tip_y": 5.7, "nose_y": -7.1,
          "stern_y": 10.2, "trail": (4.4, 2.6), "tip_r": 1.5, "tip_e": 0.15, "throat": True,
          "belly_also": ((8.3, 3.6, PIN_TIP_R + 0.25),)},
    "K": {"half": 15.0, "tip_h": 3.25, "window": False, "tip_c": (8.3, 4.0), "tip_y": 5.7, "nose_y": -7.1,
          "stern_y": 10.2, "trail": (4.4, 2.6), "tip_r": 3.0, "tip_e": 0.15},
    "L": {"half": 15.0, "tip_h": 3.25, "window": False, "tip_c": (8.3, 4.0), "tip_y": 5.7, "nose_y": -7.1,
          "stern_y": 10.2, "trail": (4.4, 2.6),
          "tip_r": 3.0, "lip": 0.18, "smooth": True},
}
SMOOTH_DEG = 30.0


def tip_c(var):
    return var.get("tip_c", (TIP_X, 0.0))


def stern_shift(var):
    return var.get("stern_y", STERN_Y) - STERN_Y


def corridor_frame(var):
    """The corridor's axis from the hall's centre to the east tip room's: (unit along, unit across, s0, s1), the box
    running from s0 (inside the hall's wall) to s1 (inside the tip room's wall): the corridor's `along` keys, s1 moved
    with the tip room in a variant whose room is elsewhere."""
    cx, cy = tip_c(var)
    d = math.hypot(cx, cy)
    u = (cx / d, cy / d)
    return u, (-u[1], u[0]), COR_S[0], d - (COR_D - COR_S[1])


def arg(name, default=None):
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return argv[argv.index(name) + 1] if name in argv else default


def bl(p):
    return (p[0], -p[1], p[2])


def mirrored(pts):
    out = []
    for x, y, z in pts:
        out.append((x, y, z))
        if abs(x) > 1e-6:
            out.append((-x, y, z))
    return out


def ring(cx, cy, r, z, n=16, a0=0.0, a1=360.0):
    """Points on a circle circumscribing the room's circle (the chords stay outside r)."""
    rr = r / math.cos(math.pi / n)
    k = max(1, round((a1 - a0) / (360.0 / n)))
    return [(cx + rr * math.cos(math.radians(a0 + (a1 - a0) * i / k)),
             cy + rr * math.sin(math.radians(a0 + (a1 - a0) * i / k)), z) for i in range(k + 1)]


def _unit(x, y):
    n = math.hypot(x, y)
    return x / n, y / n


def rounded_tip(var, nose, tip, trail, n=10):
    """The tip as a plan arc of radius tip_r tangent to the lead edge (nose -> corner) and the trail edge (corner ->
    trail): the corner is pushed out along the lead edge until the arc reaches x = half again. Each arc point is a
    pair at its height +- tip_e or, with lip, a half round of radius lip whose outer face is the outline, and the lip
    runs on along both edges. Returns (points, the arc's outermost point)."""
    r, half = var["tip_r"], var["half"]
    vx, vy = tip[0], tip[1]
    for _ in range(6):
        a, b = _unit(vx - nose[0], vy - nose[1]), _unit(trail[0] - vx, trail[1] - vy)
        u1, u2 = (-a[0], -a[1]), b
        th = math.acos(max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1])))
        d = r / math.tan(th / 2)
        bis = _unit(u1[0] + u2[0], u1[1] + u2[1])
        c = (vx + bis[0] * r / math.sin(th / 2), vy + bis[1] * r / math.sin(th / 2))
        t1, t2 = (vx + u1[0] * d, vy + u1[1] * d), (vx + u2[0] * d, vy + u2[1] * d)
        p1, p2 = math.atan2(t1[1] - c[1], t1[0] - c[0]), math.atan2(t2[1] - c[1], t2[0] - c[0])
        sweep = (p2 - p1 + math.pi) % (2 * math.pi) - math.pi     # the short way round, through the corner's side
        arc = [(c[0] + r * math.cos(p1 + sweep * k / n), c[1] + r * math.sin(p1 + sweep * k / n)) for k in range(n + 1)]
        gap = half - max(x for x, _ in arc)
        if abs(gap) < 1e-4:
            break
        vx, vy = vx + gap, vy + gap * a[1] / a[0]
    lead_len, trail_len = math.hypot(vx - nose[0], vy - nose[1]), math.hypot(trail[0] - vx, trail[1] - vy)
    h1 = nose[2] + (tip[2] - nose[2]) * (lead_len - d) / lead_len
    h2 = tip[2] + (trail[2] - tip[2]) * d / trail_len
    edge = []   # (plan x, y, h, outward unit)
    for k, (x, y) in enumerate(arc):
        edge.append((x, y, h1 + (h2 - h1) * k / n, _unit(x - c[0], y - c[1])))
    out = []
    lip = var.get("lip")
    if lip:
        na, nb = (a[1], -a[0]), (b[1], -b[0])     # the lead edge's outward normal (forward), the trail edge's (back)
        for f in (0.15, 0.35, 0.55, 0.75, 0.9):
            x, y = nose[0] + (t1[0] - nose[0]) * f, nose[1] + (t1[1] - nose[1]) * f
            edge.append((x, y, nose[2] + (h1 - nose[2]) * f, na))
            x, y = t2[0] + (trail[0] - t2[0]) * f, t2[1] + (trail[1] - t2[1]) * f
            edge.append((x, y, h2 + (trail[2] - h2) * f, nb))
        for x, y, h, (ox, oy) in edge:
            for deg in range(-90, 91, 30):
                g = math.radians(deg)
                out.append((x - ox * lip * (1 - math.cos(g)), y - oy * lip * (1 - math.cos(g)), h + lip * math.sin(g)))
    else:
        e = var.get("tip_e", 0.15)
        for x, y, h, _ in edge:
            out += [(x, y, h + e), (x, y, h - e)]
    far = max(edge, key=lambda q: q[0])
    return out, (far[0], far[1], far[2])


def design_points(var):
    half, tip_h = var["half"], var["tip_h"]
    tip_y = var.get("tip_y", LEAD_PIVOT[1] + LEAD_SLOPE * (half - LEAD_PIVOT[0]))
    tip = (half, tip_y, tip_h)
    ds = stern_shift(var)
    spine = SPINE[:-1] + [(SPINE[-1][0] + ds, SPINE[-1][1])]
    tx, th = var.get("trail", (TRAIL_END[0], TRAIL_END[2]))
    nose = (var.get("nose_x", NOSE[0]), var.get("nose_y", NOSE[1]), NOSE[2])
    trail = (tx, TRAIL_END[1] + ds, th)
    pts = [(SPINE_X, y, z) for y, z in spine] + [nose, trail]
    if "tip_r" in var:
        edge, tip = rounded_tip(var, nose, tip, trail)
        pts += edge
    else:
        pts.append(tip)
    pts += [(x, STERN_Y + ds, z) for x, z in STERN]
    cx, cy = tip_c(var)
    pts += ring(0.0, 0.0, PIN_HALL_R + 0.3, BELLY) + ring(cx, cy, PIN_TIP_R + 0.25, BELLY)
    pts += [(1.8, -4.8, BELLY)]                                        # pinned (v2's mouth room's corner)
    # rebuild C: the flat belly also under rooms moved forward, rings (x, y, r) pinned here. Rebuild E (the inside
    # 0.4 m forward of step A): only the tip rooms' ring at (8.3, 3.6) is left; without it their slab fronts keep
    # 0.10 m of skin under the rising belly. The hall's slab keeps 0.18 m on step A's ring, so C's hall ring is gone.
    # The plan outline, span, length, nose and top stay
    for bx, by, r in var.get("belly_also", ()):
        pts += ring(bx, by, r, BELLY)
    if var["window"]:   # the room's cover: the wing steps down beyond it to a tip under the sill
        pts += ring(TIP_X, 0.0, TIP_R + 0.25, TIP_RIM + 0.25, a0=-90.0, a1=90.0)
    return mirrored([p for p in pts if p[0] >= -1e-6]), tip


STEP_DEG = 2.5     # the round walls' sample step; the samples lie on the polygon circumscribed about the wall (+1 mm)
STEP_M = 0.15      # the straight walls' sample step, both ends included


def _ring_pts(cx, cy, r, step=STEP_DEG):
    """(plan angle in (-180, 180], x, y): every `step` deg on the polygon circumscribed about the circle r, so a round
    wall face between two samples never lies farther out than they do."""
    rr = r / math.cos(math.radians(step / 2))
    out = []
    for i in range(int(round(360 / step))):
        d = i * step
        a = (d + 180) % 360 - 180
        out.append((a, cx + rr * math.cos(math.radians(d)), cy + rr * math.sin(math.radians(d))))
    return out


def _steps(a, b, step=STEP_M):
    n = max(1, math.ceil(abs(b - a) / step - 1e-9))
    return [a + (b - a) * i / n for i in range(n + 1)]


def _room_points(rooms):
    """rebuild D: every room's outer surface where `rooms` (a layout's rooms by id) has it, each room on its own (no
    mirroring): the hall with the throat's opening, the throat's covered part, every corridor strip, every tip room.
    rebuild E: the hall's rim is its full height all round (the engineer, art#263 c6342342554)."""
    pts = []
    hall = rooms["hall"]
    hx, hy = hall["centre"]
    hr = hall["radius"] + WALL
    rim, apex = FLOOR + hall["clear_h"] + ROOF, FLOOR + hall["apex_h"] + ROOF
    th = next((r for r in rooms.values() if r.get("exit") and r["shape"] == "poly"), None)
    open_lo = open_hi = None
    back = []
    if th:   # the throat's opening in the hall's wall: between its two points farthest aft (the hall's corners)
        back = sorted(th["points"], key=lambda p: p[1])[-2:]
        angs = sorted(math.degrees(math.atan2(p[1] - hy, p[0] - hx)) for p in back)
        open_lo, open_hi = angs
    ring = _ring_pts(hx, hy, hr)
    if th:   # rebuild E: the wall's ends at the opening's corners, sampled too (the wall top's least skin is there)
        rr = hr / math.cos(math.radians(STEP_DEG / 2))
        ring += [(a, hx + rr * math.cos(math.radians(a)), hy + rr * math.sin(math.radians(a))) for a in angs]
    for a, x, y in ring:
        in_open = th and open_lo + 1e-6 < a < open_hi - 1e-6
        if in_open:   # rebuild E: over the opening the hall's ceiling meets the throat's header at the full rim
            pts.append(("hall rim", (x, y, rim)))
        else:
            # rebuild E (D's skip, narrowed): only the slab bottom within a wall's thickness and 12 cm (rebuild F: the
            # thin zone's real width; E had 5 cm) of the opening's corner is skipped. It is the edge of the throat's open underside (the "belly" cutter, whose back plane
            # runs through the hall's corners and whose ceiling is the throat's slab), plated by the cheeks; the wall
            # above it is checked like the rest
            joint = th and min(math.dist((x, y), p) for p in back) < WALL + 0.12
            for h in (SLAB, 1.4, 2.6, rim):
                if not (joint and h == SLAB):
                    pts.append(("hall wall", (x, y, h)))
        c, s = (x - hx) / math.hypot(x - hx, y - hy), (y - hy) / math.hypot(x - hx, y - hy)
        for rr in (1.0, 2.0, 3.0, 4.0):
            pts.append(("hall roof", (hx + rr * c, hy + rr * s, apex - (apex - rim) * rr / hr)))
            # by the throat's open underside. NOTE: in_cutter is J's notch as built, from ship.toml's throat (cutters()),
            # not from `rooms`: a layout with another throat is checked against ship.toml's notch here
            if not in_cutter((hx + rr * c, hy + rr * s - 0.2, SLAB - 0.02)):
                pts.append(("hall slab", (hx + rr * c, hy + rr * s, SLAB)))
    pts.append(("hall crown", (hx, hy, apex)))
    if th:   # the throat's covered part (aft of roof_y): its walls' tops, the chamfers' outer edges and the roof
        top = FLOOR + th["clear_h"] + ROOF
        ch_h, ch_in = th["chamfer"]
        side = [(a, b) for a, b in zip(th["points"], th["points"][1:] + th["points"][:1]) if abs(a[1] - b[1]) > 1e-6]
        y_end = max(p[1] for p in th["points"])
        for y in _steps(th["roof_y"] + SKIN, y_end):
            row = []
            for a, b in side:
                if min(a[1], b[1]) - 1e-6 <= y <= max(a[1], b[1]) + 1e-6:
                    xw = a[0] + (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1])
                    k = math.hypot(b[0] - a[0], b[1] - a[1]) / abs(b[1] - a[1])   # an across distance as an x offset
                    row.append((xw, k))
            if len(row) != 2:
                continue
            (x0, k0), (x1, k1) = sorted(row)
            for what, x, h in (("throat wall", x0 - WALL * k0, FLOOR + ch_h), ("throat wall", x1 + WALL * k1, FLOOR + ch_h),
                               ("throat chamfer", x0 + (ch_in - 0.17) * k0, top),
                               ("throat chamfer", x1 - (ch_in - 0.17) * k1, top),
                               ("throat roof", x0 + ch_in * k0, top), ("throat roof", x1 - ch_in * k1, top),
                               ("throat roof", 0.5 * (x0 + x1), top)):
                if math.hypot(x - hx, y - hy) > hr - 0.3:
                    pts.append((what, (x, y, h)))
    for r in rooms.values():
        if r["shape"] == "strip":
            (ax, ay), (bx, by) = r["axis"]
            dd = math.hypot(bx - ax, by - ay)
            u = ((bx - ax) / dd, (by - ay) / dd)
            n = (-u[1], u[0])
            half, top = r["width"] / 2 + WALL, FLOOR + r["clear_h"] + ROOF
            for s in _steps(*r["along"]):
                for w, hs, what in ((-half, (SLAB, 1.7, top), "corridor"), (half, (SLAB, 1.7, top), "corridor"),
                                    (-half, (top,), "corridor roof"), (0.0, (top,), "corridor roof"),
                                    (half, (top,), "corridor roof")):
                    for h in hs:
                        pts.append((f"{what} {r['id']}", (ax + s * u[0] + w * n[0], ay + s * u[1] + w * n[1], h)))
        elif r["shape"] == "circle" and r["id"] != "hall" and r.get("ceiling") == "slant":
            # lens step 2: the lens room's ceiling falls outward along the axis from the hall's centre (P's rooms)
            cx, cy = r["centre"]
            tr = r["radius"] + WALL
            dd = math.hypot(cx - hx, cy - hy)
            ux, uy = (cx - hx) / dd, (cy - hy) / dd
            lo, hi = r["clear_h"], r.get("clear_h_in", r["clear_h"])

            def roof(x, y):
                t = (x - cx) * ux + (y - cy) * uy
                return FLOOR + lo + (hi - lo) * (tr - t) / (2 * tr) + ROOF
            for _a, x, y in _ring_pts(cx, cy, tr):
                for h in (SLAB, 0.5 * (SLAB + roof(x, y)), roof(x, y)):
                    pts.append((f"tip wall {r['id']}", (x, y, h)))
                c, s = (x - cx) / math.hypot(x - cx, y - cy), (y - cy) / math.hypot(x - cx, y - cy)
                for f in (0.3, 0.6, 0.9):
                    q = (cx + f * tr * c, cy + f * tr * s)
                    pts.append((f"tip roof {r['id']}", (*q, roof(*q))))
                    pts.append((f"tip slab {r['id']}", (*q, SLAB)))
            pts.append((f"tip crown {r['id']}", (cx, cy, roof(cx, cy))))
        elif r["shape"] == "rect" and r.get("closed"):
            # lens step 2: a closed room (the vault): its walls, roof (clear_h at y0 falling to clear_h_back at y1)
            # and slab, every STEP_M
            (x0, x1), (y0, y1) = r["x"], r["y"]
            h0, h1 = r["clear_h"], r.get("clear_h_back", r["clear_h"])
            X0, X1, Y0, Y1 = x0 - WALL, x1 + WALL, y0 - WALL, y1 + WALL

            def vroof(y):
                return FLOOR + h0 + (h1 - h0) * (y - y0) / (y1 - y0) + ROOF
            for y in _steps(Y0, Y1):
                for x in (X0, X1):
                    for h in (SLAB, 0.5 * (SLAB + vroof(y)), vroof(y)):
                        pts.append((f"vault wall {r['id']}", (x, y, h)))
                for x in _steps(X0, X1):
                    pts += [(f"vault roof {r['id']}", (x, y, vroof(y))), (f"vault slab {r['id']}", (x, y, SLAB))]
            for x in _steps(X0, X1):
                for y in (Y0, Y1):
                    for h in (SLAB, 0.5 * (SLAB + vroof(y)), vroof(y)):
                        pts.append((f"vault wall {r['id']}", (x, y, h)))
        elif r["shape"] == "circle" and r["id"] != "hall":
            cx, cy = r["centre"]
            tr = r["radius"] + WALL
            rim, tap = FLOOR + r["clear_h"] + ROOF, FLOOR + r.get("apex_h", r["clear_h"]) + ROOF
            for _a, x, y in _ring_pts(cx, cy, tr):
                for h in (SLAB, 0.5 * (SLAB + rim), rim):
                    pts.append((f"tip wall {r['id']}", (x, y, h)))
                c, s = (x - cx) / math.hypot(x - cx, y - cy), (y - cy) / math.hypot(x - cx, y - cy)
                for f in (0.3, 0.6, 0.9):
                    pts.append((f"tip roof {r['id']}", (cx + f * tr * c, cy + f * tr * s, tap - (tap - rim) * f)))
                    pts.append((f"tip slab {r['id']}", (cx + f * tr * c, cy + f * tr * s, SLAB)))
            pts.append((f"tip crown {r['id']}", (cx, cy, tap)))
    return pts


def interior_points(var, rooms=None):
    """(what, plan point) of every room's outer surface: walls, ceilings, crowns and slab bottoms. A variant with a
    throat (J, the live hull) samples every room of `rooms` (a layout's rooms by id; default ship.toml's) on its own;
    the blockouts' variants keep v2's hall at the centre and the tip rooms and corridors where the variant puts them,
    mirrored."""
    if var.get("throat"):
        return _room_points(rooms if rooms is not None else RM)
    pts = []
    (hx, hy), (tcx, tcy) = (0.0, 0.0), tip_c(var)
    u, n, s0, s1 = corridor_frame(var)
    for d in range(0, 360, 5):
        c, s = math.cos(math.radians(d)), math.sin(math.radians(d))
        x, y = hx + HALL_R * c, hy + HALL_R * s
        if not (abs(x) < MOUTH_X + WALL and y < 0):   # v2's mouth room's opening
            for h in (SLAB, 1.4, 2.6, HALL_RIM):
                pts.append(("hall wall", (x, y, h)))
        for rr in (1.0, 2.0, 3.0, 4.0):
            pts.append(("hall roof", (hx + rr * c, hy + rr * s, HALL_APEX - (HALL_APEX - HALL_RIM) * rr / HALL_R)))
            pts.append(("hall slab", (hx + rr * c, hy + rr * s, SLAB)))
    pts.append(("hall crown", (hx, hy, HALL_APEX)))
    for side in (-1, 1):
        s = s0
        while s <= s1 + 1e-6:
            for w in (-COR_Y, COR_Y):
                for h in (SLAB, 1.7, COR_TOP):
                    pts.append(("corridor", (hx + side * (s * u[0] + w * n[0]), hy + s * u[1] + w * n[1], h)))
            for w in (-COR_Y, 0.0, COR_Y):
                pts.append(("corridor roof", (hx + side * (s * u[0] + w * n[0]), hy + s * u[1] + w * n[1], COR_TOP)))
            s += 0.3
        for d in range(0, 360, 5):
            c, s = math.cos(math.radians(d)), math.sin(math.radians(d))
            for h in (SLAB, SILL, HEAD, TIP_RIM):
                pts.append(("tip wall", (side * (tcx + TIP_R * c), tcy + TIP_R * s, h)))
            for rr in (0.6, 1.2, 1.8):
                pts.append(("tip roof", (side * (tcx + rr * c), tcy + rr * s,
                                         TIP_APEX - (TIP_APEX - TIP_RIM) * rr / TIP_R)))
                pts.append(("tip slab", (side * (tcx + rr * c), tcy + rr * s, SLAB)))
        pts.append(("tip crown", (side * tcx, tcy, TIP_APEX)))
    return pts


DEFAULT = "P"                                                          # the hull the build makes (lens step 2; J: rebuild B..lens step 1)


# --- the convex hull (plain Python) --------------------------------------------------------------------------------
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _unit3(a):
    n = math.sqrt(_dot(a, a)) or 1.0
    return (a[0] / n, a[1] / n, a[2] / n)


def _neg(a):
    return (-a[0], -a[1], -a[2])


def _plane(p, a, b, c):
    n = _unit3(_cross(_sub(p[b], p[a]), _sub(p[c], p[a])))
    return n, _dot(n, p[a])


def _chain(q):
    """A 2D convex hull (monotone chain) of sorted (u, v, payload) tuples, collinear corners dropped."""
    def turn(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for c in q:
        while len(lo) >= 2 and turn(lo[-2], lo[-1], c) <= 1e-9:
            lo.pop()
        lo.append(c)
    for c in reversed(q):
        while len(hi) >= 2 and turn(hi[-2], hi[-1], c) <= 1e-9:
            hi.pop()
        hi.append(c)
    return lo[:-1] + hi[:-1]


def convex_hull(points, eps=1e-7):
    """The convex hull of 3D points: [(unit outward normal n, d, polygon)] with n . p <= d inside, each polygon the
    facet's corners in order, coplanar triangles merged."""
    pts = list(dict.fromkeys((round(x, 9), round(y, 9), round(z, 9)) for x, y, z in points))
    i0 = 0
    i1 = max(range(len(pts)), key=lambda i: _dot(_sub(pts[i], pts[i0]), _sub(pts[i], pts[i0])))
    line = _sub(pts[i1], pts[i0])

    def off_line(i):
        c = _cross(line, _sub(pts[i], pts[i0]))
        return _dot(c, c)
    i2 = max(range(len(pts)), key=off_line)
    n0, d0 = _plane(pts, i0, i1, i2)
    i3 = max(range(len(pts)), key=lambda i: abs(_dot(n0, pts[i]) - d0))
    seed = (i0, i1, i2, i3)
    mid = tuple(sum(pts[i][k] for i in seed) / 4 for k in range(3))
    faces = {}
    for t in ((i0, i1, i2), (i0, i1, i3), (i0, i2, i3), (i1, i2, i3)):
        n, d = _plane(pts, *t)
        if _dot(n, mid) - d > 0:
            t = (t[0], t[2], t[1])
        faces[t] = _plane(pts, *t)
    for k, p in enumerate(pts):
        if k in seed:
            continue
        vis = [f for f, (n, d) in faces.items() if _dot(n, p) - d > eps]
        if not vis:
            continue
        edges = {(f[j], f[(j + 1) % 3]) for f in vis for j in range(3)}
        for f in vis:
            del faces[f]
        for a, b in edges:
            if (b, a) not in edges:
                faces[(a, b, k)] = _plane(pts, a, b, k)
    groups = []   # coplanar triangles -> one facet
    for f, (n, d) in faces.items():
        for g in groups:
            if _dot(g[0], n) > 1 - 1e-9 and abs(g[1] - d) < 1e-6:
                g[2].update(f)
                break
        else:
            groups.append([n, d, set(f)])
    out = []
    for n, d, idx in groups:
        c = tuple(sum(pts[i][k] for i in idx) / len(idx) for k in range(3))
        e1 = _unit3(_sub(pts[next(iter(idx))], c))
        e2 = _cross(n, e1)
        ring_ = _chain(sorted({(round(_dot(pts[i], e1), 9), round(_dot(pts[i], e2), 9), i) for i in idx}))
        out.append((n, d, [pts[q[2]] for q in ring_]))
    return out


@lru_cache(maxsize=None)
def facets(name: str = DEFAULT):
    """The variant's hull before the mouth cut: [(n, d, polygon)]; P: its parts' facets one after another (they
    overlap: `_parts` keeps them apart)."""
    if VARIANTS[name].get("parts"):
        return [f for _nm, fac, _bb in p_facets() for f in fac]
    pts, _tip = design_points(VARIANTS[name])
    return convex_hull(pts)


def clip(poly, n, d):
    """The part of a convex polygon with n . p <= d (Sutherland-Hodgman)."""
    out = []
    for i, a in enumerate(poly):
        b = poly[(i + 1) % len(poly)]
        sa, sb = _dot(n, a) - d, _dot(n, b) - d
        if sa <= 0:
            out.append(a)
        if (sa < 0 < sb) or (sb < 0 < sa):
            t = sa / (sa - sb)
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t))
    return out


def _newell(p):
    n = [0.0, 0.0, 0.0]
    for a, b in zip(p, p[1:] + p[:1]):
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return tuple(n)


def area(poly):
    return 0.5 * math.sqrt(_dot(_newell(poly), _newell(poly)))


RECESS_FLOOR = -1.0   # the mouth cutter's bottom (under the ground: the recess opens down through the belly's front)
X, Y, H = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)


@lru_cache(maxsize=None)
def cutters():
    """rebuild C: J's mouth notch as two convex cutters [(n, d)] (inside n . p <= d), each side plane the throat
    wall's outer face (its face line from the mouth to the hall's corner, WALL out): "notch" the open front, all
    heights, forward of the roof line (the nose is too low for head room there: no roof, the throat open to the sky);
    "belly" under the throat's covered part, below its slab (the belly rises over the deck there)."""
    (mx, my), (kx, ky) = TH_PTS[1], TH_PTS[2]
    ln = math.hypot(kx - mx, ky - my)
    ne = ((ky - my) / ln, -(kx - mx) / ln, 0.0)                         # the east wall's outward normal
    nw = (-ne[0], ne[1], 0.0)
    de = _dot(ne, (mx, my, 0.0)) + WALL
    sides = [(ne, de), (nw, de)]
    notch = sides + [(Y, TH_ROOF_Y), (_neg(H), -RECESS_FLOOR)]
    belly = sides + [(_neg(Y), -TH_ROOF_Y), (Y, ky), (H, SLAB - 0.005), (_neg(H), -RECESS_FLOOR)]
    return {"notch": notch, "belly": belly}


def in_cutter(p) -> bool:
    return any(all(_dot(n, p) <= d for n, d in planes) for planes in cutters().values())


def _subtract(poly, planes):
    """A convex polygon minus a convex region: its disjoint convex pieces outside it."""
    out, rest = [], poly
    for n, d in planes:
        piece = clip(rest, _neg(n), -d)
        if len(piece) >= 3 and area(piece) > 1e-6:
            out.append(piece)
        rest = clip(rest, n, d)
        if len(rest) < 3:
            break
    return out


def _plane_quad(n, d, size=40.0):
    a = X if abs(n[0]) < 0.9 else Y
    e1 = _unit3(_sub(a, tuple(n[k] * _dot(a, n) for k in range(3))))
    e2 = _cross(n, e1)
    o = tuple(n[k] * d for k in range(3))
    return [tuple(o[k] + size * (s1 * e1[k] + s2 * e2[k]) for k in range(3)) for s1, s2 in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def _throat_surface(hull):
    """rebuild C: the hull's faces outside both cutters, and the cutters' own faces inside the hull facing into them
    ("mouth"): the notch's sides and the lintel over the throat's roof (its back plane only above TH_TOP: below it the
    throat runs on aft), the belly cut's sides, its ceiling under the slab and its back."""
    cut = cutters()
    # rebuild F: the throat's covered part as a third region with no faces of its own: J's belly rises over the deck
    # forward of the hall (0.78 m at the roof line, under the floor's 0.6 only aft of y -5.33), so its front facet
    # crossed the throat's floor as a dark bar with sloped ends (the "dark band" of rebuild E's in_throat). Every hull
    # face inside the room (between the walls' outer faces, roof line to the hall's corners, slab to roof) is cut away;
    # the room's floor slab is the underside there, as under the "belly" cut
    room = cut["notch"][:2] + [(_neg(Y), -TH_ROOF_Y), (Y, TH_PTS[2][1]), (_neg(H), -(SLAB - 0.005)), (H, TH_TOP)]
    out = []
    for n, d, poly in hull:
        kind = "top" if n[2] >= -0.05 else "belly"
        for a in _subtract(poly, cut["notch"]):
            for b in _subtract(a, cut["belly"]):   # the room cuts only the belly: a top facet keeps its sliver aft
                out += [(c, n, kind) for c in (_subtract(b, room) if kind == "belly" else [b])]   # of the jamb cap
    for name, planes in cut.items():
        for i, (n, d) in enumerate(planes):
            if name == "belly" and n == _neg(Y):
                continue   # its front borders the notch
            poly = _plane_quad(n, d)
            for j, (m, e) in enumerate(planes):
                if j != i:
                    poly = clip(poly, m, e)
            if name == "notch" and n == Y:
                poly = clip(poly, _neg(H), -TH_TOP)
            for hn, hd, _p in hull:
                if len(poly) < 3:
                    break
                poly = clip(poly, hn, hd)
            if len(poly) >= 3 and area(poly) > 1e-6:
                out.append((poly, _neg(n), "mouth"))
    return out


@lru_cache(maxsize=None)
def surface(name: str = DEFAULT):
    """The hull's outer faces after the mouth cut: [(polygon, outward n, kind)], kind "top" (n_h >= -0.05), "belly" or
    "mouth" (the recess's back, sides and ceiling, facing into it); every polygon convex, its Newell normal along n
    (plan coordinates)."""
    mx, my, mt = MOUTH_X, MOUTH_Y, MOUTH_TOP
    if VARIANTS[name].get("parts"):
        return list(_p_surface())
    hull = facets(name)
    if VARIANTS[name].get("throat"):
        out = _throat_surface(hull)
        return [(p if _dot(_newell(p), n) > 0 else list(reversed(p)), n, kind) for p, n, kind in out]
    out = []
    for n, d, poly in hull:   # each facet outside the recess's box: four disjoint convex pieces
        kind = "top" if n[2] >= -0.05 else "belly"
        mid = clip(clip(poly, X, mx), _neg(X), mx)
        pieces = [clip(poly, _neg(X), -mx), clip(poly, X, -mx), clip(mid, _neg(Y), -my),
                  clip(clip(mid, Y, my), _neg(H), -mt)]
        out += [(p, n, kind) for p in pieces if len(p) >= 3 and area(p) > 1e-6]
    far = 30.0
    box = [   # the recess's faces inside the hull, facing into the recess
        ([(-mx, my, RECESS_FLOOR), (mx, my, RECESS_FLOOR), (mx, my, mt), (-mx, my, mt)], _neg(Y)),
        ([(mx, my, RECESS_FLOOR), (mx, -far, RECESS_FLOOR), (mx, -far, mt), (mx, my, mt)], _neg(X)),
        ([(-mx, -far, RECESS_FLOOR), (-mx, my, RECESS_FLOOR), (-mx, my, mt), (-mx, -far, mt)], X),
        ([(-mx, my, mt), (mx, my, mt), (mx, -far, mt), (-mx, -far, mt)], _neg(H)),
    ]
    for poly, n in box:
        for hn, hd, _p in hull:
            poly = clip(poly, hn, hd)
            if len(poly) < 3:
                break
        if len(poly) >= 3 and area(poly) > 1e-6:
            out.append((poly, n, "mouth"))
    return [(p if _dot(_newell(p), n) > 0 else list(reversed(p)), n, kind) for p, n, kind in out]


def skin(p, name: str = DEFAULT) -> float:
    """A point's distance to the hull's outside (the convex hull's planes and the mouth recess's box); negative
    outside."""
    x, y, h = p
    inner = max(min(d - _dot(n, p) for n, d, _poly in fac) for fac in _parts(name))   # P: the union's lower bound
    if VARIANTS[name].get("throat"):   # the cutters' plane distances (a lower bound of the true distance)
        return min([inner] + [max(_dot(n, p) - d for n, d in planes) for planes in cutters().values()])
    dx, dy = max(abs(x) - MOUTH_X, 0.0), max(y - MOUTH_Y, 0.0)
    dh = max(h - MOUTH_TOP, RECESS_FLOOR - h, 0.0)
    if dx == dy == dh == 0.0:   # inside the recess's box
        return -min(MOUTH_X - abs(x), MOUTH_Y - y, MOUTH_TOP - h)
    return min(inner, math.sqrt(dx * dx + dy * dy + dh * dh))


def clearance(name: str = DEFAULT, rooms=None):
    """(least skin, problems): every room's sampled outer surface (interior_points; `rooms` a layout's rooms by id,
    default ship.toml's) with less than SKIN of hull."""
    least, bad = 9.0, []
    for what, p in interior_points(VARIANTS[name], rooms):
        s = skin(p, name)
        least = min(least, s)
        if s < SKIN - 1e-4:
            bad.append(f"{what} ({p[0]:+.2f}, {p[1]:+.2f}, h {p[2]:.2f}): {'skin' if s >= 0 else 'POKES OUT'} {s:.3f} m")
    return least, bad


def room_skin(name: str = DEFAULT, rooms=None) -> dict:
    """rebuild E: {room: (least skin, sample kind)} over clearance's samples, the room the sample's kind names (a
    corridor's or tip room's id, else "hall" or "throat")."""
    ids = list(rooms if rooms is not None else RM)
    out = {}
    for what, p in interior_points(VARIANTS[name], rooms):
        room = next((r for r in ids if what.endswith(" " + r)), what.split()[0])
        s = skin(p, name)
        if room not in out or s < out[room][0]:
            out[room] = (s, what)
    return out


def heights(x: float, y: float, name: str = DEFAULT):
    """(top, bottom) of the hull over plan (x, y), None off its footprint (the mouth recess not cut); P: the union's
    highest top and lowest bottom over the parts there."""
    if VARIANTS[name].get("parts"):
        got = [tb for tb in (_heights(fac, x, y) for fac in _parts(name)) if tb]
        return (max(t for t, _b in got), min(b for _t, b in got)) if got else None
    return _heights(facets(name), x, y)


def _heights(fac, x, y):
    top, bot = 99.0, -99.0
    for n, d, _poly in fac:
        rest = d - n[0] * x - n[1] * y
        if n[2] > 1e-9:
            top = min(top, rest / n[2])
        elif n[2] < -1e-9:
            bot = max(bot, rest / n[2])
        elif rest < 0:
            return None
    return (top, bot) if top > bot else None


def outline(name: str = DEFAULT):
    """The plan footprint: the design points' plan convex hull, counter-clockwise in plan (x, y)."""
    pts = sorted({(round(x, 6), round(y, 6), 0) for x, y, _h in design_points(VARIANTS[name])[0]})
    return [(u, v) for u, v, _ in _chain(pts)]


def _span_at(poly, x):
    ys = []
    for i, a in enumerate(poly):
        b = poly[(i + 1) % len(poly)]
        if (a[0] - x) * (b[0] - x) <= 0 and a[0] != b[0]:
            ys.append(a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0]))
        elif a[0] == x:
            ys.append(a[1])
    return min(ys), max(ys)


def outline_rows(name: str = DEFAULT):
    """ship.toml's [hull] rows from the footprint: (core, plate) with rows [x, lead y, trail y, bottom h, top h, -1]
    at every corner's x from the centre line out (x >= 0); the plate row is the tip's outermost x."""
    if VARIANTS[name].get("parts"):
        return p_outline_rows()
    poly = outline(name)
    xmax = max(p[0] for p in poly)
    xs = sorted({round(x, 3) for x, _y in poly if x >= -1e-6} | {0.0})
    rows = []
    for x in xs:
        x = min(x, xmax)
        lead, trail = _span_at(poly, x - 1e-9 if x > 0 else x)
        hb = heights(max(0.0, x - 1e-3), (lead + trail) / 2, name)
        bot, top = (hb[1], hb[0]) if hb else (0.0, 0.0)
        rows.append([round(x, 3), round(lead, 3), round(trail, 3), round(bot, 2), round(top, 2), -1])
    return rows[:-1], rows[-1:]


def pod_ends(name: str = DEFAULT):
    """The nozzle pods' rear ends' plan y (the blockout's pods: from the stern-shifted y, length ln)."""
    if VARIANTS[name].get("parts"):
        return [P_STERN_Y + o for _x, _h, _r, o in P_PODS]
    ds = stern_shift(VARIANTS[name])
    return [y + ds + ln for _x, y, _h, _r, ln in NOZZLES]


def measures(name: str = DEFAULT) -> dict:
    """The hull's numbers: span, length (nose to the pods' ends), top, belly, the least skin, facets and faces."""
    vs = [p for fac in _parts(name) for _n, _d, poly in fac for p in poly]
    least, bad = clearance(name)
    return {"span_m": round(max(v[0] for v in vs) - min(v[0] for v in vs), 3),
            "length_m": round(max(pod_ends(name)) - min(v[1] for v in vs), 3),
            "hull_top_m": round(max(v[2] for v in vs), 3), "belly_m": round(min(v[2] for v in vs), 3),
            "least_skin_m": round(least, 3), "pokes": bad, "facets": sum(len(f) for f in _parts(name)),
            "faces": len(surface(name))}


# --- lens step 2: the hull P, the live hull --------------------------------------------------------------------------
# P (art#263 comment 6344879087; designed in ship_hull_blockout.py RAYS["P"], sheet <raw>/ship/v2/blockout6) as the
# UNION of five convex parts: the body (the hump over the hall, the throat's nose, the vault and the tail tapering to
# the nozzle pods), the two fins (a ridge over each corridor, thin diamond edges) and the two lenses (round, the slanted
# top over the lens room's ceiling, the rim's profile). Two corrections against the blockout (lens step 2): the tail
# TAPERS to the pods (the stern face P_STERN narrower and sloped, the fins' trail corners in to P_TRAIL; the blockout's
# stern stood 4.0 m wide with near-vertical sides behind the hall), and the fins' roots on the lens rim sit at
# P_LEAD_DEG / P_TRAIL_DEG round the lens's axis, so the window band (P_BAND) stays fully visible with 6 deg to spare
# (the blockout's rear tangent hid it from +45.0). The fins' edges come down to P_LENS_EDGE at the rim, under the band's
# sill, so the edge light runs at one height round the lens. The openings (the band, three roof windows per lens) are
# cut from the faces (`p_openings`), not from the skin: the skin is measured on the closed union.
# The rooms' numbers come from ship.toml (the east lens room `tip_e`, the west mirrored, and the `vault`), the band as
# the interior builds it (`_p_band`), so the cuts and the rooms cannot drift apart.


def _p_band():
    """The window band as built (deg round the lens's axis, + aft): ship.toml's band snapped to the lens room's wall
    facets (ship_interior.tip_band_facets: each end to a vertex within 1.5 deg; facets 3..7, -65.86..43.91 for the
    asked -65..45)."""
    import ship_interior   # plain Python (bpy only inside its builders); it reads the same ship.toml
    tv, fs = ship_interior.tip_vertices(), ship_interior.tip_band_facets(1)
    return tv[fs[0]], tv[fs[-1] + 1]


_LENS, _VAULT = RM["tip_e"], RM["vault"]
P_TIP = tuple(_LENS["centre"])          # the lens rooms' centres (mirrored): (10.5, 1.2)
P_ROOM_R = _LENS["radius"]              # 2.0
P_RIM_R = P_ROOM_R + WALL + 0.35        # 2.55: the lens's rim radius
P_CLEAR = (_LENS["clear_h"], _LENS["clear_h_in"])   # the lens room's clear height at its outer wall, at its inner
#                                                     wall: (2.35, 2.45)
P_RIDGE = (3.30, 1.85, 2.05)            # the corridor ridge's top h, its top and belly half widths about the axis
P_VAULT = (_VAULT["x"][1], *_VAULT["y"], _VAULT["clear_h"], _VAULT["clear_h_back"])   # half width, clear y0..y1,
#                                         clear height at the door and at the back: (0.9, 3.85, 5.85, 2.3, 1.6)
P_STERN_Y = STERN_Y + 3.9 + 2.5         # 12.7: J's stern moved 2.5 m aft (P's stern_ext)
P_STERN = [(1.2, 4.0), (2.2, 3.55), (2.75, 2.45), (2.35, 1.25), (1.2, 0.9)]   # (x, h): the tapered stern face
P_SPINE_END = (11.0, 4.3)               # the spine's rear (y, h)
P_TRAIL = (3.3, P_STERN_Y - 0.4, 2.0, 0.4)     # the fins' trail corner: x, y, the edge's mid h and thickness
P_NOSE_EDGE = (NOSE[2], 0.3)            # the fins' edge at the nose: mid h, thickness
P_LENS_EDGE = (1.35, 0.4)               # at the lens rim: under the band's sill (1.6)
P_LEAD_DEG, P_TRAIL_DEG = -72.0, 50.0   # the fins' roots on the rim, deg round the lens's outward axis (+ aft)
P_BAND = _p_band()                      # the window band as built (ship_interior: the lens room's facets 3..7)
P_BAND_IN = 2.13                        # the band's cut from this radius out (the room's wall's outer face 2.21)
P_OCULUS_D = _LENS["oculus"]["d"]                 # details 1: the oculus's clear diameter (1.4, inside the well's lining)
P_OCULUS_N = _LENS["oculus"]["sides"]             # its polygon (32): side k's normal at k 360/N deg round the axis
P_OCULUS_WELL = 0.025                             # the well's lining (ship_interior.tip_ceiling) inside the hull's cut
P_OCULUS_R = P_OCULUS_D / 2 + P_OCULUS_WELL       # 0.725: the hull's cut, its sides' apothem round the lens's centre
P_ROOF_CUT = 0.245                      # the oculus's reveal down to this over the ceiling (the well's top 0.26)
P_PODS = [(3.0, 2.0, 1.42, 2.0), (0.0, 2.55, 1.62, 2.3)]   # (x, h, r, out past the stern face): 2.84 / 3.24 across
P_POD_IN = 1.6                          # a pod's full barrel starts this far forward of the stern face
P_LENS_N = 48
P_FAIR = (60.0, 3.0)                    # details 3: a fairing round each fin root under the lens (deg of the lens's low
#                                         barrel past the root it takes in, m along the fin's edge where it ends flush)
P_TOP_LIFT = 0.04                       # lens polish: the lens's top 4 cm up, over the fin's ridge (3.30 at the lens's
#                                         centre stood 2.5 cm proud of the old top: a ledge across the lens's roof)
P_PROFILE = [(0.2, ("top", 0.0)), (0.0, ("top", 0.3)), (0.0, ("abs", 1.0)), (0.08, ("abs", 0.5)),
             (0.25, ("abs", BELLY))]    # the lens rim: (inset from P_RIM_R, depth under the top plane or a height)
POD_TAIL = SHIP["hull"]["pod_tail_m"]   # a pod's end past its builder's length
EPS = 1e-5

VARIANTS["P"] = {"half": P_TIP[0] + P_RIM_R, "tip_h": P_LENS_EDGE[0], "window": False, "tip_c": P_TIP,
                 "throat": True, "parts": True}


def p_axis(sx=1):
    """The lens's outward axis (the corridor's, from the hall's centre) as a plan unit vector; sx -1 the west."""
    a = math.atan2(P_TIP[1] - HALL_C[1], P_TIP[0] - HALL_C[0])
    return sx * math.cos(a), math.sin(a)


def p_axis_deg():
    return math.degrees(math.atan2(P_TIP[1] - HALL_C[1], P_TIP[0] - HALL_C[0]))   # 8.664


def p_ceiling(x, y, sx=1):
    """The lens room's ceiling over plan (x, y) (h over the ground): it falls outward along the axis."""
    ux, uy = p_axis(sx)
    rw = P_ROOM_R + WALL
    t = (x - sx * P_TIP[0]) * ux + (y - P_TIP[1]) * uy
    return FLOOR + P_CLEAR[0] + (P_CLEAR[1] - P_CLEAR[0]) * (rw - t) / (2 * rw)


def p_top(x, y, sx=1):
    """The lens's top plane: the ceiling + ROOF + SKIN + 5 mm + P_TOP_LIFT."""
    return p_ceiling(x, y, sx) + ROOF + SKIN + 0.005 + P_TOP_LIFT


def p_rim(deg, sx=1, r=P_RIM_R):
    """The plan point r from the lens's centre at deg round its outward axis (+ aft), the west mirrored."""
    a = math.radians(p_axis_deg() + deg)
    return sx * (P_TIP[0] + r * math.cos(a)), P_TIP[1] + r * math.sin(a)


def p_edges():
    """The east fin's edge corners (x, y, mid h, thickness): nose, lead root on the rim, trail root, trail corner."""
    return [(NOSE[0], NOSE[1], *P_NOSE_EDGE), (*p_rim(P_LEAD_DEG), *P_LENS_EDGE), (*p_rim(P_TRAIL_DEG), *P_LENS_EDGE),
            P_TRAIL]


def _inside_plan(poly, x, y, margin):
    sgn = 0
    for (ax, ay), (bx, by) in zip(poly, poly[1:] + poly[:1]):
        ln = math.hypot(bx - ax, by - ay)
        c = ((bx - ax) * (y - ay) - (by - ay) * (x - ax)) / ln
        sgn = sgn or (1 if c > 0 else -1)
        if c * sgn < margin:
            return False
    return True


def _mx(pts):
    return [(-x, y, h) for x, y, h in pts]


@lru_cache(maxsize=None)
def p_parts():
    """((name, points)): the body (mirrored in itself), the fins and the lenses, east and west."""
    cx, cy = P_TIP
    hx, hy = HALL_C
    spine = SPINE[:-1] + [P_SPINE_END]
    body = [(SPINE_X, y, z) for y, z in spine] + [NOSE, (1.8, -4.8, BELLY)]
    body += ring(0.0, 0.0, PIN_HALL_R + 0.3, BELLY)
    edges = p_edges()
    half = [(e[0], e[1]) for e in edges]
    diamond = [(-x, y) for x, y in reversed(half)] + half
    for a in range(0, 360, 15):   # J's own top over the hall's ring, and the skirt into the fins
        x, y = hx + (HALL_R + 0.4) * math.cos(math.radians(a)), hy + (HALL_R + 0.4) * math.sin(math.radians(a))
        tb = heights(x, y, "J")
        if tb and x >= -1e-6:
            body.append((x, y, tb[0]))
        x, y = hx + 6.2 * math.cos(math.radians(a)), hy + 6.2 * math.sin(math.radians(a))
        if x >= -1e-6 and _inside_plan(diamond, x, y, 0.8):
            body.append((x, y, 2.2))
    hw, _y0, y1, _h0, _h1 = P_VAULT
    body += [(hw + 0.6, 3.4, BELLY), (hw + 0.6, y1 + 0.8, BELLY)]
    body += [(x, P_STERN_Y, z) for x, z in P_STERN]
    ux, uy = p_axis()
    nx, ny = -uy, ux
    d = math.hypot(cx - hx, cy - hy)
    rh, rw, rwb = P_RIDGE
    wing = []
    for s in (3.0, d):
        px, py = hx + s * ux, hy + s * uy
        wing += [(px + w * nx, py + w * ny, rh) for w in (-rw, rw)]
        wing += [(px + w * nx, py + w * ny, BELLY) for w in (-rwb, rwb)]
    for x, y, h, e in edges:
        wing += [(x, y, h + e / 2), (x, y, h - e / 2)]
    lens = []
    for inset, (kind, h) in P_PROFILE:
        rr = (P_RIM_R - inset) / math.cos(math.pi / P_LENS_N)
        for i in range(P_LENS_N):
            g = 2 * math.pi * i / P_LENS_N
            x, y = cx + rr * math.cos(g), cy + rr * math.sin(g)
            lens.append((x, y, h if kind == "abs" else p_top(x, y) - h))
    fair = p_fairings()
    return (("body", tuple(mirrored([p for p in body if p[0] >= -1e-6]))), ("fin_e", tuple(wing)),
            ("fin_w", tuple(_mx(wing))), ("lens_e", tuple(lens)), ("lens_w", tuple(_mx(lens))),
            *((f"fair_{k}_e", tuple(pts)) for k, pts in fair), *((f"fair_{k}_w", tuple(_mx(pts))) for k, pts in fair))


def _lens_at(g, inset, h):
    """The point of the lens's 48-gon (its rim inset by `inset`) at plan angle g (radians) round its centre, height h:
    on the polygon's side the ray at g meets (its apothem P_RIM_R - inset), so on the lens's surface."""
    cx, cy = P_TIP
    step = 2 * math.pi / P_LENS_N
    gm = (math.floor(g / step + 1e-9) + 0.5) * step
    r = (P_RIM_R - inset) / math.cos(g - gm)
    return cx + r * math.cos(g), cy + r * math.sin(g), h


def p_fairings():
    """Details 3: the east side's two fairings [("lead" | "trail", points)]. Under each fin root the lens's lower
    barrel stood out past the fin's underside (lens step 2: the barrel goes down to the belly, the fin's edge stops at
    h 1.15). A fairing is the convex hull of the lens's low barrel (the rim from the fin edge's bottom down to the
    belly, every profile level) from the root to P_FAIR[0] deg past it, and the fin edge's bottom line from the root
    to P_FAIR[1] m along it: its outer face falls from that line to the barrel, so the underside runs on as one
    surface and ends flush with the fin's edge. Every point lies on the lens's or the fin's surface; the union only
    grows, so no room loses skin; the fairing stays under the edge's bottom (the edge light untouched)."""
    span, length = P_FAIR
    edges = p_edges()
    step = 2 * math.pi / P_LENS_N
    out = []
    for kind, deg, sgn, root, far in (("lead", P_LEAD_DEG, -1, edges[1], edges[0]),
                                      ("trail", P_TRAIL_DEG, 1, edges[2], edges[3])):
        (fx, fy, fh, fe), (tx, ty, th, te) = root, far
        k = length / math.hypot(tx - fx, ty - fy)
        bottom = fh - fe / 2
        pts = [(fx, fy, bottom),
               (fx + (tx - fx) * k, fy + (ty - fy) * k, fh + (th - fh) * k - (fe + (te - fe) * k) / 2)]
        g0 = math.radians(p_axis_deg() + deg)
        gs = [g0]
        g = (math.floor(g0 / step) + (1 if sgn > 0 else 0)) * step
        while abs(g - g0) <= math.radians(span) + 1e-9:
            if abs(g - g0) > 1e-6:
                gs.append(g)
            g += sgn * step
        for g in gs:
            pts += [_lens_at(g, 0.0, bottom)] + [_lens_at(g, inset, h) for inset, (lvl, h) in P_PROFILE if lvl == "abs"]
        out.append((kind, pts))
    return out


def _bbox(polys):
    vs = [v for p in polys for v in p]
    return tuple(min(v[k] for v in vs) for k in range(3)), tuple(max(v[k] for v in vs) for k in range(3))


@lru_cache(maxsize=None)
def p_facets():
    """((name, facets, bbox)) of P's parts."""
    out = []
    for name, pts in p_parts():
        fac = convex_hull(list(pts))
        out.append((name, fac, _bbox([poly for _n, _d, poly in fac])))
    return tuple(out)


def _parts(name):
    """The facet lists of a variant's convex parts (one for the single convex hulls)."""
    if VARIANTS[name].get("parts"):
        return [fac for _nm, fac, _bb in p_facets()]
    return [facets(name)]


def _overlap(bb, cc, e=1e-4):
    return all(bb[0][k] <= cc[1][k] + e and cc[0][k] <= bb[1][k] + e for k in range(3))


def _wedge_planes(c, g0, g1, r0, r1, h0, h1):
    """The convex cutter of the plan wedge round c from angle g0 to g1 (radians, counter-clockwise in plan), r0..r1,
    h0..h1: [(n, d)] inside n . p <= d, in the order side g0, side g1, inner, outer, sill, head."""
    gm = 0.5 * (g0 + g1)
    out = []
    for n in ((math.sin(g0), -math.cos(g0), 0.0), (-math.sin(g1), math.cos(g1), 0.0)):
        out.append((n, n[0] * c[0] + n[1] * c[1]))
    u = (math.cos(gm), math.sin(gm), 0.0)
    out.append((_neg(u), -(u[0] * c[0] + u[1] * c[1]) - r0))
    out.append((u, u[0] * c[0] + u[1] * c[1] + r1))
    out += [(_neg(H), -h0), (H, h1)]
    return out


def _mirror_planes(planes):
    return [((-n[0], n[1], n[2]), d) for n, d in planes]


@lru_cache(maxsize=None)
def p_openings():
    """The openings cut through P's faces: ((planes, emitted plane indices, what)): per lens the window band as wedges
    between the lens rim's vertices (the band's sill and head faces, its two end faces) and the oculus (details 1: a
    prism of P_OCULUS_N sides from P_ROOF_CUT over the ceiling up: its sides). The west's mirrored."""
    c = P_TIP
    g0, g1 = math.radians(p_axis_deg() + P_BAND[0]), math.radians(p_axis_deg() + P_BAND[1])
    step = 2 * math.pi / P_LENS_N
    cuts = [g0] + [k * step for k in range(math.floor(g0 / step) + 1, math.ceil(g1 / step))] + [g1]
    east = []
    for i, (a, b) in enumerate(zip(cuts, cuts[1:])):
        planes = _wedge_planes(c, a, b, P_BAND_IN, P_RIM_R + 0.6, SILL - 0.004, HEAD + 0.004)
        emit = [4, 5] + ([0] if i == 0 else []) + ([1] if i == len(cuts) - 2 else [])
        east.append((planes, tuple(emit), "band"))
    ux, uy = p_axis()
    nx, ny = -uy, ux
    k = (P_CLEAR[1] - P_CLEAR[0]) / (2 * (P_ROOM_R + WALL))
    cc = FLOOR + 0.5 * (P_CLEAR[0] + P_CLEAR[1]) + k * (c[0] * ux + c[1] * uy)   # h + k (ux x + uy y) = cc: the ceiling
    ln = math.sqrt(1 + k * k)
    planes = []   # details 1: the oculus, a prism of P_OCULUS_N sides round the lens's centre (side 0 on the axis)
    for j in range(P_OCULUS_N):
        a = 2 * math.pi * j / P_OCULUS_N
        ax, ay = ux * math.cos(a) - nx * math.sin(a), uy * math.cos(a) - ny * math.sin(a)
        planes.append(((ax, ay, 0.0), ax * c[0] + ay * c[1] + P_OCULUS_R))
    planes.append(((-k * ux / ln, -k * uy / ln, -1 / ln), -(cc + P_ROOF_CUT) / ln))
    planes.append((H, 9.0))
    east.append((planes, tuple(range(P_OCULUS_N)), "roof"))
    out = [(tuple(p), e, w) for p, e, w in east] + [(tuple(_mirror_planes(p)), e, w) for p, e, w in east]
    return tuple(out)


def _meets(poly, planes, e=1e-6):
    """Whether a convex polygon reaches into a convex region by more than a crumb (else it is kept whole: subtracting
    a region it does not meet would only split it along the region's planes)."""
    q = poly
    for n, d in planes:
        q = clip(q, n, d - e)
        if len(q) < 3:
            return False
    return area(q) > 1e-7


def _cut(pieces, planes):
    return [r for pc in pieces for r in (_subtract(pc, planes) if _meets(pc, planes) else [pc])]


def _union_pieces(poly):
    """A convex polygon's pieces inside P's union, each point in one piece (the first part that holds it)."""
    parts = p_facets()
    out = []
    for k, (_nm, fac, _bb) in enumerate(parts):
        q = poly
        for n, d, _p in fac:
            q = clip(q, n, d)
            if len(q) < 3:
                break
        if len(q) < 3 or area(q) < 1e-6:
            continue
        pieces = [q]
        for j in range(k):
            pieces = _cut(pieces, [(n, d + EPS) for n, d, _p in parts[j][1]])
        out += pieces
    return out


def _cut_faces(planes, emit):
    """A convex cutter's emitted faces inside P's union, facing into the cutter: [(polygon, n)]."""
    out = []
    for i in emit:
        n, d = planes[i]
        poly = _plane_quad(n, d)
        for j, (m, e) in enumerate(planes):
            if j != i:
                poly = clip(poly, m, e)
        if len(poly) < 3 or area(poly) < 1e-6:
            continue
        out += [(q, _neg(n)) for q in _union_pieces(poly)]
    return out


@lru_cache(maxsize=None)
def _p_surface():
    """P's outer faces: every part's facets outside the other parts (a face on another part's boundary kept once),
    then J's throat cuts (`_throat_surface`'s rules) and the openings; the cutters' own faces: the mouth's, the band's
    sill, head and ends, the roof windows' sides ("top"/"belly" by their normal, plated like the hull)."""
    parts = p_facets()
    cut = cutters()
    room = cut["notch"][:2] + [(_neg(Y), -TH_ROOF_Y), (Y, TH_PTS[2][1]), (_neg(H), -(SLAB - 0.005)), (H, TH_TOP)]
    opens = p_openings()
    out = []
    for k, (_nm, fac, _bb) in enumerate(parts):
        for n, d, poly in fac:
            pieces = [poly]
            pb = _bbox([poly])
            for j, (_m, other, ob) in enumerate(parts):
                if j == k or not _overlap(pb, ob):
                    continue
                e = EPS if j < k else -EPS
                planes = [(m, dd + e) for m, dd, _p in other]
                pieces = _cut(pieces, planes)
            kind = "top" if n[2] >= -0.05 else "belly"
            done = []
            for a in pieces:
                for b in _cut([a], cut["notch"]):
                    for c2 in _cut([b], cut["belly"]):
                        done += _cut([c2], room) if kind == "belly" else [c2]
            for planes, _emit, _what in opens:
                done = _cut(done, list(planes))
            out += [(c2, n, kind) for c2 in done]
    for name, planes in cut.items():   # the mouth's faces, as _throat_surface
        for i, (n, d) in enumerate(planes):
            if name == "belly" and n == _neg(Y):
                continue
            poly = _plane_quad(n, d)
            for j, (m, e) in enumerate(planes):
                if j != i:
                    poly = clip(poly, m, e)
            if name == "notch" and n == Y:
                poly = clip(poly, _neg(H), -TH_TOP)
            if len(poly) >= 3 and area(poly) > 1e-6:
                out += [(q, _neg(n), "mouth") for q in _union_pieces(poly)]
    for planes, emit, _what in opens:
        out += [(q, m, "top" if m[2] >= -0.05 else "belly") for q, m in _cut_faces(planes, emit)]
    # a crumb (under 1 mm2) or a hull artefact thinner than 0.1 mm (a near-flat sliver along an edge) is no face
    return tuple((p if _dot(_newell(p), n) > 0 else list(reversed(p)), n, kind) for p, n, kind in out
                 if len(p) >= 3 and area(p) > 1e-6 and 2 * area(p) / sum(math.dist(a, b) for a, b in zip(p, p[1:] + p[:1])) > 1e-4)


def p_outline_rows():
    """[hull] rows of P: at every part corner's x the union's lead and trail y (the parts' plan hulls' spans)."""
    hulls = []
    for nm, pts in p_parts():
        if nm.startswith("fair_"):   # details 3: a fairing lies under its fin and lens in plan (test_ship_fairing)
            continue
        q = sorted({(round(x, 6), round(y, 6), 0) for x, y, _h in pts})
        hulls.append([(u, v) for u, v, _ in _chain(q)])
    xmax = max(p[0] for poly in hulls for p in poly)
    xs = sorted({round(x, 3) for poly in hulls for x, _y in poly if x >= -1e-6} | {0.0})
    rows = []
    for x in xs:
        x = min(x, xmax)
        spans = []
        for poly in hulls:
            lo, hi = min(p[0] for p in poly), max(p[0] for p in poly)
            if lo - 1e-9 <= x <= hi + 1e-9:
                spans.append(_span_at(poly, min(max(x, lo + 1e-9), hi - 1e-9)))
        lead, trail = min(s[0] for s in spans), max(s[1] for s in spans)
        hb = heights(max(0.0, x - 1e-3), (lead + trail) / 2, "P")
        bot, top = (hb[1], hb[0]) if hb else (0.0, 0.0)
        rows.append([round(x, 3), round(lead, 3), round(trail, 3), round(bot, 2), round(top, 2), -1])
    return rows[:-1], rows[-1:]


def p_pods():
    """The nozzle pods' placements [(x, nose y, h, r, length)] for nozzle_pod / pod_ring: the pod's end (its length +
    POD_TAIL) is P_STERN_Y + out."""
    out = []
    for x, h, r, o in P_PODS:
        y0 = P_STERN_Y - P_POD_IN - 1.5
        for sx in ((-1, 1) if x else (1,)):
            out.append((sx * x, y0, h, r, round(P_STERN_Y + o - POD_TAIL - y0, 3)))
    return out


def p_edge_line(sx=1):
    """The edge light's path on the east (sx -1: west) side: [(point, outward n)] along the fin's lead edge (nose to
    the lead root), round the lens rim's facets from the lead root to the trail root at P_LENS_EDGE's height (a point
    at every rim vertex), and along the fin's trail edge to its corner. The points lie on the faces."""
    (n0x, n0y, n0h, _e0), (fx, fy, fh, _e1), (bx, by, bh, _e2), (tx, ty, th, _e3) = p_edges()
    hx, hy = HALL_C

    def flat(ax, ay, bx_, by_):
        dx, dy = bx_ - ax, by_ - ay
        ln = math.hypot(dx, dy)
        n = (dy / ln, -dx / ln, 0.0)
        return _neg(n) if n[0] * (hx - ax) + n[1] * (hy - ay) > 0 else n
    lead, trail = flat(n0x, n0y, fx, fy), flat(bx, by, tx, ty)
    cx, cy = P_TIP
    step = 2 * math.pi / P_LENS_N
    a0, a1 = math.radians(p_axis_deg() + P_LEAD_DEG), math.radians(p_axis_deg() + P_TRAIL_DEG)

    def on_rim(g):   # the rim's face at plan angle g (its facet's plane, apothem P_RIM_R)
        gm = (math.floor(g / step + 1e-9) + 0.5) * step
        r = P_RIM_R / math.cos(g - gm)
        return (cx + r * math.cos(g), cy + r * math.sin(g), P_LENS_EDGE[0]), (math.cos(gm), math.sin(gm), 0.0)
    pts = [((n0x, n0y, n0h), lead), ((fx, fy, fh), lead)]
    verts = [a0 + 1e-6] + [k * step for k in range(math.floor(a0 / step) + 1, math.ceil(a1 / step))] + [a1 - 1e-6]
    pts += [on_rim(g) for g in verts]
    pts += [((bx, by, bh), trail), ((tx, ty, th), trail)]
    if sx < 0:
        pts = [((-p[0], p[1], p[2]), (-n[0], n[1], n[2])) for p, n in pts]
    return pts
