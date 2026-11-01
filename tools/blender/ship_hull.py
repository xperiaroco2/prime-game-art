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
    # polish n3: the nozzles' stator blades and spinner, dark gunmetal with a faint teal cast (the throat's glow on
    # them), their leading edges' bevel a rim lit by the glow behind (so they shade, not silhouette as black cut-outs)
    "ext_blade": {"base": (0.07, 0.085, 0.095, 1.0), "metallic": 0.7, "roughness": 0.3,
                  "emission": (0.03, 0.3, 0.33), "strength": 0.35},
    "ext_blade_edge": {"base": (0.2, 0.6, 0.62, 1.0), "metallic": 0.3, "roughness": 0.3,
                       "emission": (0.25, 0.9, 0.92), "strength": 1.6},
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


def _lathe_y(profile, n, a0=0.0, caps=True):
    """A closed solid of revolution round the y axis: profile [(r, y)] from one end to the other (r 0 ends close).
    caps False: an end ring off the axis stays open (fix 2, art #263: no flat disc across a ring or a nozzle)."""
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
    if caps and len(rings[0]) > 1:
        f.append(tuple(rings[0]))
    if caps and len(rings[-1]) > 1:
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
    floor = layout["deck"]["floor_h"] - layout["deck"].get("lift_m", 0.0)   # lifted by ship_build
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
    floor = layout["deck"]["floor_h"] - layout["deck"].get("lift_m", 0.0)   # lifted by ship_build
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
    floor = layout["deck"]["floor_h"] - layout["deck"].get("lift_m", 0.0)   # lifted by ship_build
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
    """A standing landing leg (the raise, 2026-10-23; local +x outward, exterior.toml yaws it; built at the real
    heights, the ground at h 0): args top (the mount's height: the lowest belly over it + 0.1, the mount box reaching
    0.42 + rise over it, into the skin), reach (the mount's pivot to the foot's centre, plan) and rise (rebuild D: the
    mount's top raised more under a steep belly). A faceted fairing out of the belly (the raise step 2: 8 sides,
    r 0.62 in the skin to 0.36 at a dark frame lip, smooth hull silver) over a yoke and its pin; the oleo strut from the
    pin down and out to the ankle at a steep angle: a thick sleeve, a collar, the chrome piston and a forked end; two
    side braces from the yoke's cheeks to the sleeve (an A-frame seen from the front); the ankle's knuckle pin; a
    broad flat footpad (r 0.6) with a raised hub, four ribs and a dark sole."""
    top, reach = float(args.get("top", 1.2)), float(args.get("reach", 0.5))
    rise = float(args.get("rise", 0.0))
    piv, ank = (0.05, 0.0, top - 0.15), (reach, 0.0, 0.34)
    at = lambda t, y=0.0: (piv[0] + (ank[0] - piv[0]) * t, y, piv[2] + (ank[2] - piv[2]) * t)  # noqa: E731
    # step 2 of the raise: a faceted fairing grows out of the belly (its top inside the skin, where step 1's dark box
    # reached) in the hull's smooth silver, tapering down to a dark frame lip over the yoke (was a plain dark box)
    fair = L.disc(0.62, 8, top - 0.16, top + 0.42 + rise)
    fair = ([(x * (0.36 / 0.62), y * (0.36 / 0.62), h) if h < top else (x, y, h) for x, y, h in fair[0]], fair[1])
    lip_ring = L.disc(0.39, 8, top - 0.2, top - 0.12)
    cheeks = [_obox((0.05, s * 0.25, top - 0.12), (0.2, 0, 0), (0, 0.05, 0), (0, 0, 0.16)) for s in (-1, 1)]
    pin = _rod((piv[0], -0.31, piv[2]), (piv[0], 0.31, piv[2]), 0.1, 10)
    sleeve = _rod(at(-0.04), at(0.56), 0.19, 10)          # step 2: stouter (r 0.15 -> 0.19), read from the yard
    collar = _rod(at(0.53), at(0.6), 0.23, 10)
    piston = _rod(at(0.5), at(0.86), 0.11, 10)
    fork = _rod(at(0.84), at(0.97), 0.145, 8)
    braces = [_rod((piv[0] - 0.05, s * 0.27, top - 0.22), at(0.4, s * 0.15), 0.06, 8) for s in (-1, 1)]
    knuckle = _rod((ank[0], -0.17, ank[2]), (ank[0], 0.17, ank[2]), 0.1, 10)
    ears = [_obox((ank[0], s * 0.13, 0.27), (0.09, 0, 0), (0, 0.03, 0), (0, 0, 0.11)) for s in (-1, 1)]
    pad = L.disc(0.6, 12, 0.03, 0.11)
    hub = L.disc(0.3, 12, 0.11, 0.2)
    sole = L.disc(0.62, 12, 0.0, 0.03)
    sh = lambda d: ([(x + ank[0], y, h) for x, y, h in d[0]], d[1])  # noqa: E731
    ribs = [_obox((ank[0] + 0.44 * math.cos(a), 0.44 * math.sin(a), 0.135),
                  (0.13 * math.cos(a), 0.13 * math.sin(a), 0), (-0.035 * math.sin(a), 0.035 * math.cos(a), 0),
                  (0, 0, 0.025)) for a in (math.pi / 4 + k * math.pi / 2 for k in range(4))]
    if args.get("heavy"):
        return _leg_heavy(top, reach, rise, piv, ank, at, fair, lip_ring, cheeks)
    return [L.part("leg_fairing", *fair, "hull_silver"), L.part("leg_lip", *lip_ring, "ext_frame"),
            L.part("leg_mount", *L.merge(*cheeks), "hull_dark"),
            L.part("leg_strut", *L.merge(sleeve, *braces), "leg_metal"),
            L.part("leg_joint", *L.merge(pin, collar, fork, knuckle, *ears, *ribs), "ext_frame"),
            L.part("leg_piston", *piston, "ext_chrome"),
            L.part("leg_pad", *L.merge(sh(pad), sh(hub)), "leg_metal"),
            L.part("leg_sole", *sh(sole), "hull_dark")]


def _leg_heavy(top, reach, rise, piv, ank, at, fair, lip_ring, cheeks) -> list:
    """polish n1 (art #263): the stern legs under the big bells, sturdier in the same footprint (pad r 0.6): a
    thicker 16-sided oleo (sleeve r 0.25, chrome piston r 0.14), two side dampers (a sleeve and a chrome rod each),
    a torque link (scissor) on the inner face, a hydraulic line, a 16-sided pad with a hub, eight ribs and eight
    bolt heads, a dark sole."""
    n = 16
    pin = _rod((piv[0], -0.36, piv[2]), (piv[0], 0.36, piv[2]), 0.12, n)
    caps = [_rod((piv[0], s * 0.36, piv[2]), (piv[0], s * 0.4, piv[2]), 0.075, n) for s in (-1, 1)]
    sleeve = _rod(at(-0.06), at(0.55), 0.25, n)
    bands = [_rod(at(t), at(t + 0.03), 0.265, n) for t in (0.08, 0.3)]
    collar = _rod(at(0.52), at(0.6), 0.29, n)
    piston = _rod(at(0.5), at(0.86), 0.14, n)
    fork = _rod(at(0.84), at(0.97), 0.17, n)
    braces = [_rod((piv[0] - 0.05, s * 0.3, top - 0.22), at(0.42, s * 0.2), 0.075, 10) for s in (-1, 1)]
    dsl = [_rod(at(0.02, s * 0.36), at(0.5, s * 0.36), 0.075, 12) for s in (-1, 1)]       # the dampers' sleeves
    drod = [_rod(at(0.48, s * 0.36), at(0.9, s * 0.36), 0.04, 12) for s in (-1, 1)]       # their chrome rods
    deyes = [_rod(at(t, s * 0.36 - 0.05), at(t, s * 0.36 + 0.05), 0.07, 12) for s in (-1, 1) for t in (0.0, 0.92)]
    # the torque link: two arms from the sleeve's collar and the fork meeting at a knee on the inner face (-x)
    c0, c1 = at(0.6), at(0.9)
    knee = ((c0[0] + c1[0]) / 2 - 0.26, 0.0, (c0[2] + c1[2]) / 2)
    link = [_rod((c0[0] - 0.2, 0.0, c0[2]), knee, 0.045, 8), _rod(knee, (c1[0] - 0.15, 0.0, c1[2]), 0.045, 8),
            _rod((knee[0], -0.06, knee[2]), (knee[0], 0.06, knee[2]), 0.05, 10)]
    hose = [_rod((piv[0] + 0.12, 0.2, top - 0.25), at(0.3, 0.27), 0.022, 8)]
    knuckle = _rod((ank[0], -0.2, ank[2]), (ank[0], 0.2, ank[2]), 0.12, n)
    ears = [_obox((ank[0], s * 0.16, 0.27), (0.11, 0, 0), (0, 0.035, 0), (0, 0, 0.12)) for s in (-1, 1)]
    pad = L.disc(0.6, n, 0.03, 0.1)
    bevel = ([(x * (0.56 / 0.6) if h > 0.11 else x, y * (0.56 / 0.6) if h > 0.11 else y, h)
              for x, y, h in L.disc(0.6, n, 0.1, 0.13)[0]], L.disc(0.6, n, 0.1, 0.13)[1])
    hub = L.disc(0.32, n, 0.13, 0.24)
    sole = L.disc(0.62, n, 0.0, 0.03)
    sh = lambda d: ([(x + ank[0], y, h) for x, y, h in d[0]], d[1])  # noqa: E731
    ribs = [_obox((ank[0] + 0.44 * math.cos(a), 0.44 * math.sin(a), 0.16),
                  (0.12 * math.cos(a), 0.12 * math.sin(a), 0), (-0.03 * math.sin(a), 0.03 * math.cos(a), 0),
                  (0, 0, 0.035)) for a in (math.pi / 8 + k * math.pi / 4 for k in range(8))]
    bolts = [_rod((ank[0] + 0.5 * math.cos(a), 0.5 * math.sin(a), 0.125),
                  (ank[0] + 0.5 * math.cos(a), 0.5 * math.sin(a), 0.155), 0.026, 8)
             for a in (k * math.pi / 4 for k in range(8))]
    return [L.part("leg_fairing", *fair, "hull_silver"), L.part("leg_lip", *lip_ring, "ext_frame"),
            L.part("leg_mount", *L.merge(*cheeks), "hull_dark"),
            L.part("leg_strut", *L.merge(sleeve, *braces, *dsl), "leg_metal"),
            L.part("leg_joint", *L.merge(pin, *caps, *bands, collar, fork, knuckle, *ears, *ribs, *deyes, *link),
                   "ext_frame"),
            L.part("leg_piston", *L.merge(piston, *drod, *bolts), "ext_chrome"),
            L.part("leg_hose", *L.merge(*hose), "hull_dark"),
            L.part("leg_pad", *L.merge(sh(pad), sh(bevel), sh(hub)), "leg_metal"),
            L.part("leg_sole", *sh(sole), "hull_dark")]


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
import ship_hull_fittings  # noqa: E402  (details 2: portholes, vents, mast and dome, hatches, stripes)

MODULES.append(ship_hull_fittings)
import ship_hull_clearing  # noqa: E402  (the clearing: dirt, path, tufts, bushes, logs, pines, party lights; step 3)

MODULES.append(ship_hull_clearing)

import ship_hull_jaw  # noqa: E402  (art #263: the jaw nose)

MODULES.append(ship_hull_jaw)
