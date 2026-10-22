"""The ship's EXTERIOR pieces (art #263, docs/ship.md): the EXTERIOR lane owns this file and ship_hull_*.py. Each
builder(args, layout) returns ship_lib parts in the piece's local frame (plan axes x east, y south, h up; metres;
layouts/ship/exterior.toml places them).

This module holds the shared helpers (boxes, rods, lathes, the panelled skin: every face cut into plates with a real
chamfer sinking into a dark seam, over a dark under-skin) and the pieces that are not the skin: the tip windows' frames,
the mouth's portal and lights, the ramp, the landing legs and the clearing. The skin itself is ship_hull_j.py (the live hull P since lens step 2; before it variant
J of the blockouts, ship_hull_shape.py, plated with this module's _plate; rebuild B); its details (canopies, pods,
ground lamps) are ship_hull_detail.py. Skin faces point outward, so from inside the ship they are back faces
and never hide a room (the interior lane's walls close the rooms). Belly h 0.6 (under the 0.75 slab bottoms)."""

from __future__ import annotations

import math

import ship_lib as L

MODULES: list = []  # further exterior modules (ship_hull_*.py) the harness searches for builders

L.MATERIALS.update({
    "ext_silver_b": {"base": (0.62, 0.64, 0.67, 1.0), "metallic": 0.9, "roughness": 0.28},
    "ext_silver_c": {"base": (0.47, 0.49, 0.52, 1.0), "metallic": 0.9, "roughness": 0.36},
    "ext_seam": {"base": (0.035, 0.037, 0.04, 1.0), "metallic": 0.6, "roughness": 0.6},
    "ext_frame": {"base": (0.16, 0.17, 0.18, 1.0), "metallic": 0.85, "roughness": 0.35},
    "ext_chrome": {"base": (0.8, 0.8, 0.82, 1.0), "metallic": 1.0, "roughness": 0.12},
    "ext_nozzle_inner": {"base": (0.03, 0.03, 0.035, 1.0), "metallic": 0.7, "roughness": 0.5},
    "ext_glow_warm": {"base": (1.0, 0.55, 0.22, 1.0), "metallic": 0.0, "roughness": 0.5, "emission": (1.0, 0.5, 0.18),
                      "strength": 1.6},
    "ext_glow_cyan_dim": {"base": (0.1, 0.6, 0.8, 1.0), "metallic": 0.0, "roughness": 0.4,
                          "emission": (0.15, 0.85, 1.0), "strength": 2.5},
    # details 1: the lens band's faint warm glow seen from outside (one-sided: "cull"), the canopies' lighter glass
    # and their cockpit screens
    "ext_window_glow": {"base": (1.0, 0.62, 0.3, 0.18), "metallic": 0.0, "roughness": 0.5, "alpha": True,
                        "emission": (1.0, 0.55, 0.22), "strength": 3.0, "cull": True},
    "glass_canopy": {"base": (0.16, 0.19, 0.22, 0.28), "metallic": 0.0, "roughness": 0.05, "alpha": True},
    "ext_seat": {"base": (0.6, 0.62, 0.65, 1.0), "metallic": 0.3, "roughness": 0.45},   # catches the cockpit's glow
    "ext_screen": {"base": (0.1, 0.7, 0.9, 1.0), "metallic": 0.0, "roughness": 0.3, "emission": (0.15, 0.85, 1.0),
                   "strength": 5.0},
    "ext_ground": {"base": (0.05, 0.062, 0.035, 1.0), "metallic": 0.0, "roughness": 0.95},
    "ext_bark": {"base": (0.12, 0.075, 0.05, 1.0), "metallic": 0.0, "roughness": 0.9},
    "ext_needles": {"base": (0.03, 0.075, 0.045, 1.0), "metallic": 0.0, "roughness": 0.85},
    "ext_rock": {"base": (0.2, 0.2, 0.21, 1.0), "metallic": 0.0, "roughness": 0.85},
})

BELLY_H = 0.6
CLEARING_K = 1.25   # rebuild B: the clearing scaled to the hull J (span 30 m, 18.9 m long; v2's 27.5 by 14)
CREST_H = 4.0
ROOT_X = 1.5
POD_X = 10.75
POD = [(0.0, 0.6), (2.25, 0.6), (2.41, 1.5), (2.5, 2.0), (2.36, 3.4), (2.3, 4.0), (1.3, 4.45), (0.0, 4.6)]
SILVERS = ("hull_silver", "hull_silver", "hull_silver", "ext_silver_b", "ext_silver_c")


# --- vector helpers ------------------------------------------------------------------------------------------------
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a, b, k=1.0):
    return (a[0] + b[0] * k, a[1] + b[1] * k, a[2] + b[2] * k)


def _lerp(a, b, t):
    return tuple(a[k] + (b[k] - a[k]) * t for k in range(3))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a):
    n = math.sqrt(_dot(a, a)) or 1.0
    return (a[0] / n, a[1] / n, a[2] / n)


def _newell(p):
    n = [0.0, 0.0, 0.0]
    for a, b in zip(p, p[1:] + p[:1]):
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return _norm(tuple(n))


def _hash(*v) -> float:
    s = math.sin(sum(x * k for x, k in zip(v, (12.9898, 78.233, 37.719, 4.581))) + 0.5) * 43758.5453
    return s - math.floor(s)


def _lin(points, x):
    """Piecewise-linear value at x over [(x, v)]."""
    if x <= points[0][0]:
        return points[0][1]
    for (x0, v0), (x1, v1) in zip(points, points[1:]):
        if x <= x1:
            return v0 + (v1 - v0) * (x - x0) / (x1 - x0)
    return points[-1][1]


def _obox(c, ax, ay, az):
    """A solid box: centre c, half-axis vectors ax, ay, az."""
    v = []
    for sz in (-1, 1):
        for sy in (-1, 1):
            for sx in (-1, 1):
                v.append(tuple(c[k] + ax[k] * sx + ay[k] * sy + az[k] * sz for k in range(3)))
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return v, f


def _rod(p0, p1, r, n=10):
    """A closed n-sided rod from p0 to p1."""
    d = _norm(_sub(p1, p0))
    u = _norm(_cross(d, (0.0, 0.0, 1.0) if abs(d[2]) < 0.9 else (1.0, 0.0, 0.0)))
    w = _cross(d, u)
    v = []
    for p in (p0, p1):
        for i in range(n):
            a = 2 * math.pi * i / n
            v.append(_add(_add(p, u, r * math.cos(a)), w, r * math.sin(a)))
    f = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i)
                                                                    for i in range(n)]
    return v, f


def _lathe_y(profile, n, a0=0.0):
    """A closed solid of revolution round the y axis: profile [(r, y)] from one end to the other (r 0 ends close)."""
    v, f = [], []
    rings = []
    for r, y in profile:
        if r < 1e-6:
            rings.append([len(v)])
            v.append((0.0, y, 0.0))
        else:
            rings.append(list(range(len(v), len(v) + n)))
            v += [(r * math.cos(a0 + 2 * math.pi * i / n), y, r * math.sin(a0 + 2 * math.pi * i / n)) for i in range(n)]
    for a, b in zip(rings, rings[1:]):
        for i in range(n):
            if len(a) == 1:
                f.append((a[0], b[(i + 1) % n], b[i]))
            elif len(b) == 1:
                f.append((a[i], a[(i + 1) % n], b[0]))
            else:
                f.append((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
    if len(rings[0]) > 1:
        f.append(tuple(rings[0]))
    if len(rings[-1]) > 1:
        f.append(tuple(reversed(rings[-1])))
    ys = [y for _r, y in profile]
    lo, hi = min(ys) + 0.02, max(ys) - 0.02
    return v, L.orient(v, f, lambda c: (0.0, min(max(c[1], lo), hi), 0.0))


# --- the panelled skin ---------------------------------------------------------------------------------------------
def _split(p, size):
    """A quad cut into a grid of panels about `size` metres (staggered by a hash); other polygons stay whole."""
    if len(p) != 4:
        return [p]
    la = max(math.dist(p[0], p[1]), math.dist(p[3], p[2]))
    lb = max(math.dist(p[1], p[2]), math.dist(p[0], p[3]))
    c = _lerp(p[0], p[2], 0.5)
    nu = max(1, math.ceil(la / size - 0.15 + 0.3 * _hash(*c)))
    nv = max(1, math.ceil(lb / size - 0.15))
    out = []
    for i in range(nu):
        for j in range(nv):
            def at(u, v):
                return _lerp(_lerp(p[0], p[1], u), _lerp(p[3], p[2], u), v)
            u0, u1, v0, v1 = i / nu, (i + 1) / nu, j / nv, (j + 1) / nv
            out.append([at(u0, v0), at(u1, v0), at(u1, v1), at(u0, v1)])
    return out


def _plate(p, inset, depth):
    """A panel: its face inset by `inset` at the surface, chamfered down to its outline sunk `depth` along the normal."""
    n = _newell(p)
    k = len(p)
    top = []
    for i in range(k):
        a, b, c = p[i - 1], p[i], p[(i + 1) % k]
        e1, e2 = _norm(_sub(a, b)), _norm(_sub(c, b))
        bis = _norm(_add(e1, e2))
        half = math.acos(max(-1.0, min(1.0, _dot(e1, e2)))) / 2
        dist = min(inset / max(0.25, math.sin(half)), 0.3 * min(math.dist(a, b), math.dist(b, c)))
        top.append(_add(b, bis, dist))
    bot = [_add(q, n, -depth) for q in p]
    v = top + bot
    f = [tuple(range(k))] + [((i + 1) % k, i, k + i, k + (i + 1) % k) for i in range(k)]
    return v, f


def _skin(name, verts, faces, size=1.7, inset=0.022, depth=0.014, mats=SILVERS):
    """Outward faces -> panel plates grouped by material, and the dark under-skin below the seams."""
    groups: dict = {}
    under = []
    for face in faces:
        p = [verts[i] for i in face]
        for q in _split(p, size):
            c = [sum(x[k] for x in q) / len(q) for k in range(3)]
            mat = mats[int(_hash(round(c[0], 1), round(c[1], 1), round(c[2], 1)) * len(mats)) % len(mats)]
            groups.setdefault(mat, []).append(_plate(q, inset, depth))
        n = _newell(p)
        under.append(([_add(x, n, -depth * 1.8) for x in p], [tuple(range(len(p)))]))
    parts = [L.part(f"{name}_{mat}", *L.merge(*g), mat, solid=False) for mat, g in sorted(groups.items())]
    parts.append(L.part(f"{name}_seam", *L.merge(*under), "ext_seam", solid=False))
    return parts


def window_frame(args: dict, layout: dict) -> list:
    """The tip window's frame (facing +x): sill, head and jambs from the glass (r 2.2) out through the pod skin,
    and four mullions; closes the jamb between the room's wall and the skin."""
    room = next(r for r in layout["rooms"] if r["id"] == "tip_e")
    win = room["window"]
    floor = layout["deck"]["floor_h"]
    sill, head = floor + win["sill_h"], floor + win["head_h"]
    half = math.radians(win["half_angle_deg"])
    out = []
    a = L.angles(-half, half, math.radians(6.0))
    for a0, a1 in zip(a, a[1:]):
        out.append(L.sector(2.18, 2.47, a0, a1, sill - 0.08, sill + 0.02))
        out.append(L.sector(2.18, 2.42, a0, a1, head - 0.02, head + 0.08))
    for ang in (-half, half):
        d = 0.05 / 2.3
        out.append(L.sector(2.18, 2.53, ang - d if ang > 0 else ang, ang if ang > 0 else ang + d, sill - 0.08,
                            head + 0.08))
    for ang in (-2 * half / 3, -half / 3, half / 3, 2 * half / 3):
        out.append(L.sector(2.27, 2.36, ang - 0.012, ang + 0.012, sill, head))
    return [L.part("window_frame", *L.merge(*out), "ext_frame")]


def _ring_prism(inner, outer, y0, y1):
    """A closed frame between two (x, h) outlines (same count, open at the bottom ends), from y0 to y1."""
    n = len(inner)
    v = ([(x, y0, h) for x, h in inner] + [(x, y0, h) for x, h in outer] + [(x, y1, h) for x, h in inner]
         + [(x, y1, h) for x, h in outer])
    f = []
    for i in range(n - 1):
        f.append((i, i + 1, n + i + 1, n + i))                      # front face
        f.append((2 * n + i, 3 * n + i, 3 * n + i + 1, 2 * n + i + 1))  # back face
        f.append((i, 2 * n + i, 2 * n + i + 1, i + 1))              # the opening's side
        f.append((n + i, n + i + 1, 3 * n + i + 1, 3 * n + i))      # the outer side
    for i in (0, n - 1):                                            # the two feet
        f.append((i, n + i, 3 * n + i, 2 * n + i))
    # outward: from the nearest point of the frame's mid line (between the outlines, mid depth; the feet's points
    # lifted so a foot face sees its inside above it)
    mids = []
    for i in range(n):
        lift = 0.03 if i in (0, n - 1) else 0.0
        mids.append(((inner[i][0] + outer[i][0]) / 2, (inner[i][1] + outer[i][1]) / 2 + lift))
    mids += [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in zip(mids, mids[1:])]
    ym = (y0 + y1) / 2

    def inside(c):
        x, h = min(mids, key=lambda m: (m[0] - c[0]) ** 2 + (m[1] - c[2]) ** 2)
        return (x, ym, h)
    return v, L.orient(v, f, inside)


def _mouth_outlines(layout):
    """The mouth's opening (the inside's portal: half width 1.25, clear_h with 0.3 x 0.35 chamfers) and the frame's
    outer outline, which covers the skin's rectangular hole (x +-1.3 up to the corridor's top + 0.15), as (x, h)."""
    floor = layout["deck"]["floor_h"]
    hm = next(r for r in layout["rooms"] if r["id"] == "mouth")["clear_h"]
    inner = [(-1.25, floor - 0.02), (-1.25, floor + hm - 0.35), (-0.95, floor + hm), (0.95, floor + hm),
             (1.25, floor + hm - 0.35), (1.25, floor - 0.02)]
    outer = [(-1.62, floor - 0.25), (-1.62, floor + hm - 0.1), (-1.12, floor + hm + 0.4), (1.12, floor + hm + 0.4),
             (1.62, floor + hm - 0.1), (1.62, floor - 0.25)]
    return inner, outer


def mouth_frame(args: dict, layout: dict) -> list:
    """The portal round the mouth (local origin: the ramp's hinge on the ground; hull 3-2): a chamfered frame from the
    inside's opening out over the skin's hole, 0.3 m deep, panelled; a thin inner lip."""
    inner, outer = _mouth_outlines(layout)
    v, f = _ring_prism(inner, outer, -0.2, 0.1)
    lip_o = [(x * 1.03, h + (0.04 if h > 2.0 else 0.0)) for x, h in inner]
    lv, lf = _ring_prism(inner, lip_o, -0.26, -0.18)
    return [L.part("portal", v, f, "ext_frame"), L.part("portal_lip", lv, lf, "ext_chrome")]  # v2: no plates


def mouth_lights(args: dict, layout: dict) -> list:
    """The amber strips on the portal's inner faces and along its head (local origin: the ramp's hinge, on the
    ground)."""
    floor = layout["deck"]["floor_h"]
    hm = next(r for r in layout["rooms"] if r["id"] == "mouth")["clear_h"]
    out = []
    for s in (-1, 1):
        for k in range(4):
            h0 = floor + 0.2 + k * 0.48
            out.append(L.box(s * 1.235 - 0.02, s * 1.235 + 0.02, -0.17, 0.03, h0, h0 + 0.34))
    for k in range(3):
        x0 = -0.8 + k * 0.6
        out.append(L.box(x0, x0 + 0.4, -0.17, 0.03, floor + hm - 0.04, floor + hm - 0.01))
    return [L.part("mouth_lights", *L.merge(*out), "glow_amber")]


def ramp(args: dict, layout: dict) -> list:
    """The mouth ramp from its hinge (the local origin, at floor height) down north to its foot on the ground: the
    deck with low anti-slip ribs, side stringers, the hinge barrel and the foot lip (all colliders)."""
    rp, deck = layout["ramp"], layout["deck"]
    run = rp["hinge"][1] - rp["foot"][1]
    fall = deck["floor_h"] - deck["ground_h"]
    hw, t = rp["width_m"] / 2, rp["thickness_m"]
    length = math.hypot(run, fall)
    along = (0.0, -run / length, -fall / length)
    up = (0.0, -fall / length, run / length)
    if up[2] < 0:
        up = (0.0, -up[1], -up[2])
    top0 = (0.0, 0.0, deck["floor_h"])

    def p(s, x, d):
        return _add(_add(_add(top0, along, s), (1.0, 0.0, 0.0), x), up, d)
    deckv, deckf = _obox(p(length / 2, 0.0, -t / 2), (hw - 0.12, 0, 0), _lerp((0, 0, 0), along, length / 2),
                         _lerp((0, 0, 0), up, t / 2))
    parts = [L.part("ramp_deck", deckv, deckf, "floor_grate")]
    ribs = []
    for k in range(1, int(length / 0.32)):
        ribs.append(_obox(p(k * 0.32, 0.0, 0.01), (hw - 0.3, 0, 0), _lerp((0, 0, 0), along, 0.03),
                          _lerp((0, 0, 0), up, 0.012)))
    parts.append(L.part("ramp_ribs", *L.merge(*ribs), "ext_frame"))
    rails = [_obox(p(length / 2, s * (hw - 0.06), 0.0), (0.06, 0, 0), _lerp((0, 0, 0), along, length / 2),
                   _lerp((0, 0, 0), up, 0.1)) for s in (-1, 1)]
    parts.append(L.part("ramp_rails", *L.merge(*rails), "hull_silver"))
    hinge = _rod((-hw + 0.05, 0.02, deck["floor_h"] - 0.12), (hw - 0.05, 0.02, deck["floor_h"] - 0.12), 0.09, 12)
    parts.append(L.part("ramp_hinge", *hinge, "ext_chrome"))
    lip = _obox(p(length - 0.04, 0.0, -t / 2), (hw, 0, 0), _lerp((0, 0, 0), along, 0.05), _lerp((0, 0, 0), up, t / 2))
    parts.append(L.part("ramp_lip", *lip, "ext_frame"))
    return parts


def ramp_lights(args: dict, layout: dict) -> list:
    """The ramp's amber light (local origin: the hinge; step 2): a continuous strip along each edge of the deck, inside
    the rails, and a cross strip at the foot."""
    rp, deck = layout["ramp"], layout["deck"]
    run = rp["hinge"][1] - rp["foot"][1]
    fall = deck["floor_h"] - deck["ground_h"]
    length = math.hypot(run, fall)
    along = (0.0, -run / length, -fall / length)
    up = _norm((0.0, -fall, run))
    if up[2] < 0:
        up = (0.0, -up[1], -up[2])
    out = []
    for s in (-1, 1):
        c = _add(_add(_add((0.0, 0.0, deck["floor_h"]), along, length / 2), (1.0, 0, 0), s * (rp["width_m"] / 2 - 0.2)),
                 up, 0.004)
        out.append(_obox(c, (0.03, 0, 0), _lerp((0, 0, 0), along, length / 2 - 0.15), _lerp((0, 0, 0), up, 0.012)))
    c = _add(_add((0.0, 0.0, deck["floor_h"]), along, length - 0.25), up, 0.004)
    out.append(_obox(c, (rp["width_m"] / 2 - 0.3, 0, 0), _lerp((0, 0, 0), along, 0.03), _lerp((0, 0, 0), up, 0.012)))
    return [L.part("ramp_lights", *L.merge(*out), "glow_amber")]


def leg(args: dict, layout: dict) -> list:
    """A chunky landing leg splaying toward local +x (exterior.toml yaws it outward; hull 3-2): args top (the mount's
    height: about the lowest belly under its footprint + 0.1; the mount box reaches 0.42 over it, into the skin) and
    reach (mount to foot). A faceted mount box with cheeks, a thick upper strut down to the knee drum at (0.62 reach, 0.45 top + 0.12), the lower strut to the ankle, a twin chrome
    piston pair in dark sleeves, a broad faceted foot plate (r 0.5) with three toes and a dark sole."""
    top, reach = float(args.get("top", 0.9)), float(args.get("reach", 1.5))
    rise = float(args.get("rise", 0.0))   # rebuild D: the mount's top raised this much more (a steep belly over it)
    knee, ankle, foot = (0.62 * reach, 0.0, 0.45 * top + 0.12), (reach, 0.0, 0.2), (reach, 0.0, 0.0)
    mount = _obox((0.0, 0.0, top + 0.1 + rise / 2), (0.42, 0, 0), (0, 0.34, 0), (0, 0, 0.32 + rise / 2))
    cheek = [_obox((0.22, s * 0.25, top - 0.2), (0.26, 0, 0), (0, 0.05, 0), (0, 0, 0.13)) for s in (-1, 1)]
    upper = _rod((0.08, 0.0, top - 0.2), knee, 0.17, 8)
    lower = _rod(knee, ankle, 0.14, 8)
    joint = _rod((knee[0], -0.25, knee[2]), (knee[0], 0.25, knee[2]), 0.22, 12)
    ajoint = _rod((ankle[0], -0.17, ankle[2]), (ankle[0], 0.17, ankle[2]), 0.13, 10)
    p1 = (0.85 * reach, 0.0, 0.3)
    pistons = [_rod((-0.12, s * 0.16, top - 0.22), (p1[0], s * 0.16, p1[2]), 0.05, 8) for s in (-1, 1)]
    mid = lambda t: (-0.12 + (p1[0] + 0.12) * t, 0.0, top - 0.22 + (p1[2] - top + 0.22) * t)  # noqa: E731
    sleeves = [_rod((-0.12, s * 0.16, top - 0.22), (mid(0.45)[0], s * 0.16, mid(0.45)[2]), 0.08, 8) for s in (-1, 1)]
    pad = L.disc(0.5, 8, 0.03, 0.13)
    padv = [(x + foot[0], y, hh) for x, y, hh in pad[0]]
    cap_v, cap_f = L.disc(0.3, 8, 0.13, 0.22)
    capv = [(x + foot[0], y, hh) for x, y, hh in cap_v]
    toes = [_obox(_add((foot[0], 0.0, 0.06), (math.cos(a), math.sin(a), 0.0), 0.55),
                  (0.12 * math.cos(a), 0.12 * math.sin(a), 0), (-0.09 * math.sin(a), 0.09 * math.cos(a), 0),
                  (0, 0, 0.05))
            for a in (-0.9, 0.0, 0.9)]
    sole = L.disc(0.52, 8, 0.0, 0.03)
    solev = [(x + foot[0], y, hh) for x, y, hh in sole[0]]
    return [L.part("leg_mount", *L.merge(mount, *cheek), "hull_dark"),
            L.part("leg_strut", *L.merge(upper, lower), "leg_metal"),
            L.part("leg_joint", *L.merge(joint, ajoint), "ext_frame"),
            L.part("leg_piston", *L.merge(*pistons), "ext_chrome"),
            L.part("leg_sleeve", *L.merge(*sleeves), "hull_dark"),
            L.part("leg_pad", *L.merge((padv, pad[1]), (capv, cap_f), *toes), "leg_metal"),
            L.part("leg_sole", solev, sole[1], "hull_dark")]


# --- the clearing --------------------------------------------------------------------------------------------------
def ground(args: dict, layout: dict) -> list:
    """The clearing's ground: flat within 16 m * CLEARING_K (the walk's world boundary stays at h 0), rolling gently
    beyond."""
    radii = [r * CLEARING_K for r in (0.0, 5.0, 10.0, 16.0, 21.0, 27.0, 35.0, 45.0, 58.0, 75.0)]
    flat = 16.0 * CLEARING_K
    segs = 40
    v = [(0.0, 0.0, 0.0)]
    for r in radii[1:]:
        for j in range(segs):
            a = 2 * math.pi * (j + 0.5 * (radii.index(r) % 2)) / segs
            h = 0.0 if r <= flat else (r - flat) * 0.035 + 0.6 * _hash(r / CLEARING_K, j) * min(1.0, (r - flat) / 10.0)
            v.append((r * math.cos(a), r * math.sin(a), h - 0.005))
    f = [(0, 1 + (j + 1) % segs, 1 + j) for j in range(segs)]
    for i in range(len(radii) - 2):
        a, b = 1 + i * segs, 1 + (i + 1) * segs
        f += [(a + j, b + j, b + (j + 1) % segs) for j in range(segs)] + [(a + j, b + (j + 1) % segs, a + (j + 1) % segs)
                                                                          for j in range(segs)]
    f = L.orient(v, f, lambda c: (c[0], c[1], c[2] - 1.0))
    return [L.part("ground", v, f, "ext_ground", solid=False)]


def pine(args: dict, layout: dict) -> list:
    """A pine: a tapered trunk and stacked drooping branch skirts (args height, seed); each skirt's rim alternates
    long branch tips and short notches with a seeded jitter, so the silhouette reads as branches, not a cone."""
    height, seed = float(args.get("height", 14.0)), float(args.get("seed", 1.0))
    trunk = _rod((0.0, 0.0, -0.3), (0.0, 0.0, height * 0.7), 0.2 * height / 14.0, 8)
    skirts = []
    n, m = 8, 18
    for k in range(n):
        u = k / (n - 1)
        base = height * (0.16 + 0.68 * u)
        r = height * (0.27 - 0.215 * u) * (0.9 + 0.2 * _hash(seed, k))
        ring = []
        for j in range(m):
            a = 2 * math.pi * (j + 0.35 * _hash(seed, k, j)) / m
            rr = r * ((0.95 + 0.25 * _hash(seed, j, k)) if j % 2 == 0 else 0.58)
            droop = r * (0.42 if j % 2 == 0 else 0.22) * (0.8 + 0.4 * _hash(k, j, seed))
            ring.append((rr * math.cos(a), rr * math.sin(a), base - droop))
        top = base + height * (0.13 if k < n - 1 else 0.2)
        v = ring + [(0.0, 0.0, top), (0.0, 0.0, base - 0.25 * r)]
        f = [(j, (j + 1) % m, m) for j in range(m)] + [((j + 1) % m, j, m + 1) for j in range(m)]
        skirts.append((v, f))
    v, f = L.merge(*skirts)
    return [L.part("pine_trunk", *trunk, "ext_bark"), L.part("pine_needles", v, f, "ext_needles")]


def rock(args: dict, layout: dict) -> list:
    """A faceted boulder (args size, seed), half sunk into the ground."""
    size, seed = float(args.get("size", 1.0)), float(args.get("seed", 1.0))
    v, f = L.sphere(1.0, 5, 7)
    v = [(x * size * (0.8 + 0.4 * _hash(seed, i, 1)), y * size * (0.75 + 0.4 * _hash(seed, i, 2)),
          h * size * (0.5 + 0.3 * _hash(seed, i, 3)) + 0.1 * size) for i, (x, y, h) in enumerate(v)]
    return [L.part("rock", v, f, "ext_rock")]


# --- winding -------------------------------------------------------------------------------------------------------
def _outward(fn):
    """The plan frame (x east, y south, h up) is left-handed: the harness's (x, -y, h) mirrors it, which flips every
    winding set in plan coordinates. A builder's open parts (solid False, oriented here with ship_lib.orient) are
    reversed once, so their faces point outward in Blender, the GLB and Godot."""
    def run(args: dict, layout: dict) -> list:
        parts = fn(args, layout)
        for p in parts:
            if not p["solid"]:
                p["faces"] = [tuple(reversed(f)) for f in p["faces"]]
        return parts
    run.__doc__, run.__name__ = fn.__doc__, fn.__name__
    return run


for _name in ("window_frame", "mouth_frame", "mouth_lights", "ramp", "ramp_lights", "leg", "ground", "pine", "rock"):
    globals()[_name] = _outward(globals()[_name])

import ship_hull_j  # noqa: E402  (rebuild B: the hull J, plated; it imports this module's helpers)

MODULES.append(ship_hull_j)
import ship_hull_detail  # noqa: E402  (the canopies, pods, blades, hatches and lamps; step 2)

MODULES.append(ship_hull_detail)
import ship_hull_clearing  # noqa: E402  (the clearing: dirt, path, tufts, bushes, logs, pines, party lights; step 3)

MODULES.append(ship_hull_clearing)
