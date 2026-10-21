"""The ship's EXTERIOR pieces (art #263, docs/ship.md): the EXTERIOR lane owns this file and ship_hull_*.py. Each
builder(args, layout) returns ship_lib parts in the piece's local frame (plan axes x east, y south, h up; metres;
layouts/ship/exterior.toml places them).

The hull is a kit of faceted skins, each its own piece: the drum over the hall, the nose over the mouth, three wing
sections per side (lofted sections that hug the corridors and widen into the tip pods), the tip pods' outer halves
with the window opening, and the nozzle mount. Every skin face is cut into panels; each panel is a plate with a real
chamfer that sinks into a dark seam (geometry, not a texture), over a dark under-skin. Skin faces point outward, so
from inside the ship they are back faces and never hide a room (the interior lane's walls close the rooms).

Numbers (plan metres; ship.toml holds the rooms): belly h 0.6 (under the 0.75 slab bottoms); wing crest h 4.0 over the
corridors' ceilings (3.85); the wing's half-width at the crest and belly 1.6 by the corridors, widening to the pods;
the lead chine from (1.5, -6.2) to (9.0, -3.0) to (10.75, -2.5), the trail chine from (3.3, 5.0) to (9.0, 2.9) to
(10.75, 2.5); the chines rise from h 1.4 at the root to 2.0 at the pods (the manta's raised tips). The pod profile
(r, h) round each tip room: (2.25, 0.6), (2.41, 1.5), (2.5, 2.0), (2.36, 3.4), (2.3, 4.0), (1.3, 4.45), (0, 4.6): the
window opening is the band h 1.5..3.4 within 65 deg of the tip's axis. The drum over the hall: r 3.85..3.95 up to h
4.75, a faceted cupola to h 5.55."""

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
    "ext_ground": {"base": (0.075, 0.07, 0.05, 1.0), "metallic": 0.0, "roughness": 0.95},
    "ext_bark": {"base": (0.12, 0.075, 0.05, 1.0), "metallic": 0.0, "roughness": 0.9},
    "ext_needles": {"base": (0.03, 0.075, 0.045, 1.0), "metallic": 0.0, "roughness": 0.85},
    "ext_rock": {"base": (0.2, 0.2, 0.21, 1.0), "metallic": 0.0, "roughness": 0.85},
})

BELLY_H = 0.6
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


# --- the wing ------------------------------------------------------------------------------------------------------
def _wing_rows(x):
    """The wing section at |x| (plan, east half): its loop of (y, h) points."""
    u = (x - ROOT_X) / (POD_X - ROOT_X)
    lead = _lin([(ROOT_X, -6.2), (9.0, -3.0), (POD_X, -2.5)], x)
    trail = _lin([(ROOT_X, 5.2), (3.3, 5.0), (9.0, 2.9), (POD_X, 2.5)], x)
    hc = 1.4 + 0.6 * u
    c = _lin([(ROOT_X, 1.6), (8.0, 1.6), (POD_X, 2.3)], x)
    b = _lin([(ROOT_X, 1.6), (8.0, 1.6), (POD_X, 2.25)], x)
    raise_ = 0.16 * max(0.0, 1.0 - max(0.0, x - 8.0) / (POD_X - 8.0))
    if x >= POD_X - 1e-6:  # the pod's profile at 90 deg, so the wing meets the pod without a step
        return [(lead, hc), (-2.41, 1.5), (-b, BELLY_H), (b, BELLY_H), (2.41, 1.5), (trail, hc), (2.36, 3.4),
                (c, CREST_H), (-c, CREST_H), (-2.36, 3.4)]
    fl = _lerp((0, lead, hc), (0, -b, BELLY_H), 0.5)
    rl = _lerp((0, trail, hc), (0, b, BELLY_H), 0.5)
    fu = _lerp((0, lead, hc), (0, -c, CREST_H), 0.5)
    ru = _lerp((0, trail, hc), (0, c, CREST_H), 0.5)
    return [(lead, hc), (fl[1], fl[2]), (-b, BELLY_H), (b, BELLY_H), (rl[1], rl[2]), (trail, hc),
            (ru[1], ru[2] + raise_), (c, CREST_H), (-c, CREST_H), (fu[1], fu[2] + raise_)]


def _clip_y(poly, ymax):
    """The (y, h) polygon clipped to y <= ymax."""
    out = []
    for a, b in zip(poly, poly[1:] + poly[:1]):
        ina, inb = a[0] <= ymax, b[0] <= ymax
        if ina:
            out.append(a)
        if ina != inb:
            t = (ymax - a[0]) / (b[0] - a[0])
            out.append((ymax, a[1] + (b[1] - a[1]) * t))
    return out


def hull_wing(args: dict, layout: dict) -> list:
    """One wing section of the kit: lofted between its stations (args x: [x0, ..., x1], side), with the wedge's
    root cap in front of the mouth on the first section."""
    side = float(args.get("side", 1.0))
    xs = [float(x) for x in args["x"]]
    secs = [[(side * x, y, h) for y, h in _wing_rows(x)] for x in xs]
    n = len(secs[0])
    verts = [p for s in secs for p in s]
    faces = [(i * n + j, i * n + (j + 1) % n, (i + 1) * n + (j + 1) % n, (i + 1) * n + j)
             for i in range(len(secs) - 1) for j in range(n)]

    def inner(c):
        x = abs(c[0])
        rows = _wing_rows(min(max(x, ROOT_X), POD_X))
        return (c[0], sum(r[0] for r in rows) / len(rows), sum(r[1] for r in rows) / len(rows))
    faces = L.orient(verts, faces, inner)
    if xs[0] <= ROOT_X + 1e-6:
        mouth_y = next(r for r in layout["rooms"] if r["id"] == "mouth")["y"][0]
        cap = _clip_y(_wing_rows(xs[0]), mouth_y)
        k = len(verts)
        verts += [(side * xs[0], y, h) for y, h in cap]
        faces += L.orient(verts, [tuple(range(k, len(verts)))], lambda c: (c[0] + side, c[1], c[2]))
    return _skin(f"wing_{'e' if side > 0 else 'w'}", verts, faces)


def stripes(args: dict, layout: dict) -> list:
    """The cyan diagonal light bars along a wing's lower lead facet (one light strip, its own piece)."""
    side = float(args.get("side", 1.0))
    count, x0, x1 = int(args.get("count", 14)), 3.6, 9.4

    def at(x, t):
        r = _wing_rows(x)
        return _lerp((side * x, r[0][0], r[0][1]), (side * x, r[2][0], r[2][1]), t)
    out = []
    step = (x1 - x0) / count
    for k in range(count):
        xa = x0 + k * step
        quad = [at(xa, 0.14), at(xa + 0.2, 0.14), at(xa + 0.2 + 0.34, 0.72), at(xa + 0.34, 0.72)]
        n = _norm(_cross(_sub(at(xa + 0.1, 0.4), at(xa, 0.4)), _sub(at(xa, 0.5), at(xa, 0.4))))
        if n[1] > 0:
            n = (-n[0], -n[1], -n[2])
        v = [_add(q, n, 0.014) for q in quad] + [_add(q, n, -0.03) for q in quad]
        out.append((v, [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]))
    return [L.part("stripes", *L.merge(*out), "glow_cyan")]


def blade(args: dict, layout: dict) -> list:
    """A thin knife-edge flange along a wing's chine (args side, edge "lead" or "trail"): the manta's sharp edge that
    the thick wing (the corridors' height) cannot have. Its root sinks 0.3 m into the hull; it reaches out w(x) in plan
    (lead: forward, 0.75 m at the root, 0.95 m mid-wing, 0 at the pod; trail: back, 0.5 m) and thins from 0.12 m to a
    2 cm edge. Its top catches the moon as a bright line along the wing."""
    side = float(args.get("side", 1.0))
    lead = args.get("edge", "lead") == "lead"
    s = -1.0 if lead else 1.0
    row = 0 if lead else 5
    x0 = 1.65 if lead else 3.4
    widths = [(x0, 0.75 if lead else 0.5), (6.0, 0.95 if lead else 0.55), (9.0, 0.6 if lead else 0.35), (10.2, 0.0)]
    xs = [x0 + (10.2 - x0) * k / 16 for k in range(17)]
    secs = []
    for x in xs:
        y, h = _wing_rows(x)[row]
        w = max(0.02, _lin(widths, x))
        t = 0.06 * min(1.0, w / 0.5) + 0.01
        secs.append([(side * x, y - s * 0.3, h + t), (side * x, y + s * w, h + 0.012), (side * x, y + s * w, h - 0.012),
                     (side * x, y - s * 0.3, h - t)])
    n = 4
    verts = [p for sec in secs for p in sec]
    faces = [(i * n + j, i * n + (j + 1) % n, (i + 1) * n + (j + 1) % n, (i + 1) * n + j)
             for i in range(len(secs) - 1) for j in range(n)]
    faces += [(0, 1, 2, 3), tuple(range(len(verts) - 1, len(verts) - 5, -1))]

    def inner(c):
        y, h = _wing_rows(min(max(abs(c[0]), x0), 10.2))[row]
        return (c[0], y, h)
    faces = L.orient(verts, faces, inner)
    return [L.part("blade", verts, faces, "hull_silver", solid=False)]


# --- the drum over the hall, the nose, the pods, the nozzle mount --------------------------------------------------
DRUM = [(0.0, BELLY_H), (3.85, BELLY_H), (3.95, 1.4), (3.95, CREST_H), (3.9, 4.75), (3.0, 5.15), (1.5, 5.45),
        (0.0, 5.55)]


def _revolve(profile, a_list, skip=None):
    """Faces of a faceted solid of revolution round the h axis (plan frame): profile [(r, h)], angles a_list;
    skip(mid_angle, h0, h1) leaves a cell out."""
    verts, faces = [], []
    for a0, a1 in zip(a_list, a_list[1:]):
        for (r0, h0), (r1, h1) in zip(profile, profile[1:]):
            if skip and skip((a0 + a1) / 2, min(h0, h1), max(h0, h1), max(r0, r1)):
                continue
            p = [(r0 * math.cos(a0), r0 * math.sin(a0), h0), (r0 * math.cos(a1), r0 * math.sin(a1), h0),
                 (r1 * math.cos(a1), r1 * math.sin(a1), h1), (r1 * math.cos(a0), r1 * math.sin(a0), h1)]
            if r0 < 1e-6:
                p = [p[0], p[2], p[3]]
            elif r1 < 1e-6:
                p = p[:3]
            k = len(verts)
            verts += p
            faces.append(tuple(range(k, k + len(p))))
    return verts, faces


def hull_drum(args: dict, layout: dict) -> list:
    """The faceted drum and cupola over the hall, open where the corridors and the mouth pass (the wings and the nose
    cover those from outside)."""
    cor = 1.6
    a_cor = math.asin(cor / 3.95)
    cuts = (-a_cor, a_cor, math.pi - a_cor, -math.pi + a_cor, -math.pi / 2 - a_cor, -math.pi / 2 + a_cor)
    a = L.angles(-math.pi, math.pi, math.radians(22.5), cuts)

    def skip(mid, h0, h1, r):
        if r < 3.8 or h0 >= CREST_H - 1e-6 or h1 <= BELLY_H + 1e-6:
            return False
        x, y = math.cos(mid), math.sin(mid)
        return abs(y) * 3.95 < cor or (y < 0 and abs(x) * 3.95 < cor)
    v, f = _revolve(DRUM, a, skip)
    f = L.orient(v, f, lambda c: (0.0, 0.0, 2.6))
    return _skin("drum", v, f, size=1.6)


def hull_nose(args: dict, layout: dict) -> list:
    """The brow over the mouth from the mouth frame up into the drum, its sides down to the wing roots, and the plate
    under the mouth."""
    hw = ROOT_X + 0.12

    def slope(y):
        r = _wing_rows(ROOT_X)
        return r[0][1] + (y - r[0][0]) / (r[-2][0] - r[0][0]) * (r[-2][1] - r[0][1])
    prof = [(-4.75, slope(-4.75)), (-4.75, 3.6), (-4.88, 3.95), (-3.1, 4.9), (-3.1, slope(-3.1))]
    verts, faces = [], []
    for s in (-1, 1):
        k = len(verts)
        verts += [(s * hw, y, h) for y, h in prof]
        faces.append(tuple(range(k, k + len(prof))))
    k = len(verts)
    verts += [(-hw, -4.75, 3.6), (hw, -4.75, 3.6), (hw, -4.88, 3.95), (-hw, -4.88, 3.95)]
    faces.append((k, k + 1, k + 2, k + 3))
    k = len(verts)
    verts += [(-hw, -4.88, 3.95), (hw, -4.88, 3.95), (hw, -3.1, 4.9), (-hw, -3.1, 4.9)]
    faces.append((k, k + 1, k + 2, k + 3))
    k = len(verts)
    verts += [(-hw, -4.75, BELLY_H), (hw, -4.75, BELLY_H), (hw, -3.3, BELLY_H), (-hw, -3.3, BELLY_H)]
    faces.append((k, k + 1, k + 2, k + 3))
    faces = L.orient(verts, faces, lambda c: (0.0, -3.9, 2.4))
    return _skin("nose", verts, faces, size=1.4)


def hull_pod(args: dict, layout: dict) -> list:
    """A tip pod's outer half (built facing +x; the west one is placed at yaw 180): the panelled skin with the window
    opening (the band h 1.5..3.4 within 65 deg of the axis), the full cupola on top."""
    room = next(r for r in layout["rooms"] if r["id"] == "tip_e")
    win = room["window"]
    floor = layout["deck"]["floor_h"]
    sill, head = floor + win["sill_h"], floor + win["head_h"]
    half = math.radians(win["half_angle_deg"])
    a = L.angles(-math.pi / 2, math.pi / 2, math.radians(12.0), (-half, half))

    def skip(mid, h0, h1, r):
        return abs(mid) < half and h0 >= sill - 1e-6 and h1 <= head + 1e-6
    wall = [p for p in POD if p[1] < 4.0 + 1e-6]
    v, f = _revolve(wall, a, skip)
    top = [p for p in POD if p[1] >= 4.0 - 1e-6]
    v2, f2 = _revolve(top, L.angles(-math.pi, math.pi, math.radians(12.0)))
    v, f = L.merge((v, f), (v2, f2))
    f = L.orient(v, f, lambda c: (0.0, 0.0, 2.3))
    return _skin("pod", v, f, size=1.5)


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


def nozzle_mount(args: dict, layout: dict) -> list:
    """The faceted block behind the hall that holds the three nozzles (open toward the hall)."""
    sec = [(-3.25, 0.6), (3.25, 0.6), (3.25, 3.3), (2.6, 3.9), (-2.6, 3.9), (-3.25, 3.3)]
    ys = [(3.0, 0.0), (4.95, 0.0), (5.35, 0.22)]
    secs = []
    for y, k in ys:
        cx, ch = 0.0, 2.25
        secs.append([(cx + (x - cx) * (1 - k * 0.6 / 3.25 * 3.25 / 3.25), y, ch + (h - ch) * (1 - k * 0.6 / 1.65))
                     for x, h in sec])
    n = len(sec)
    verts = [p for s in secs for p in s]
    faces = [(i * n + j, i * n + (j + 1) % n, (i + 1) * n + (j + 1) % n, (i + 1) * n + j)
             for i in range(len(secs) - 1) for j in range(n)]
    faces.append(tuple(range(2 * n, 3 * n)))
    faces = L.orient(verts, faces, lambda c: (0.0, min(c[1], 5.0) - (0.6 if c[1] > 5.3 else 0.0), 2.25))
    return _skin("mount", verts, faces, size=1.5)


# --- the parts that sit on the hull --------------------------------------------------------------------------------
def bubble_collar(args: dict, layout: dict) -> list:
    """The cockpit bubble's collar (local origin: the glass's base), sunk into the wedge, with its lip."""
    collar = L.disc(0.8, 16, -1.0, -0.02)
    lip = L.ring(0.7, 0.86, [-0.02, 0.07], math.radians(22.5))
    return _skin("collar", *collar, size=1.0, inset=0.015, depth=0.01) + [L.part("collar_lip", *lip, "ext_frame")]


def bubble_glass(args: dict, layout: dict) -> list:
    """The tinted glass dome and its two frame arches (outside only: the hall's ceiling closes it from inside)."""
    rings, segs, r = 6, 24, 0.74
    v = [(r * math.cos(math.pi / 2 * i / rings) * math.cos(2 * math.pi * j / segs),
          r * math.cos(math.pi / 2 * i / rings) * math.sin(2 * math.pi * j / segs),
          0.05 + r * math.sin(math.pi / 2 * i / rings)) for i in range(rings) for j in range(segs)]
    v.append((0.0, 0.0, 0.05 + r))
    f = [(i * segs + j, i * segs + (j + 1) % segs, (i + 1) * segs + (j + 1) % segs, (i + 1) * segs + j)
         for i in range(rings - 1) for j in range(segs)]
    f += [((rings - 1) * segs + j, (rings - 1) * segs + (j + 1) % segs, len(v) - 1) for j in range(segs)]
    f = L.orient(v, f, lambda c: (0.0, 0.0, 0.0))
    arches = []
    for k in range(-6, 6):
        t0, t1 = math.pi / 2 * (k / 6), math.pi / 2 * ((k + 1) / 6)
        p0 = (0.0, (r + 0.02) * math.sin(t0), 0.05 + (r + 0.02) * math.cos(t0))
        p1 = (0.0, (r + 0.02) * math.sin(t1), 0.05 + (r + 0.02) * math.cos(t1))
        arches.append(_obox(_lerp(p0, p1, 0.5), (0.035, 0, 0), _lerp((0, 0, 0), _sub(p1, p0), 0.5),
                            _add((0, 0, 0), _norm(_lerp(p0, p1, 0.5)), 0.025)))
    return [L.part("bubble_glass", v, f, "glass_tint", solid=False), L.part("bubble_arch", *L.merge(*arches), "ext_frame")]


def bubble_glow(args: dict, layout: dict) -> list:
    """The warm glow inside the bubble seen through the tinted glass: a lit floor disc and a dark console block."""
    disc = L.disc(0.62, 16, 0.05, 0.08)
    block = _obox((0.0, 0.2, 0.3), (0.28, 0, 0), (0, 0.14, 0), (0, 0, 0.22))
    return [L.part("bubble_light", *disc, "ext_glow_warm"), L.part("bubble_console", *block, "ext_frame")]


def mouth_frame(args: dict, layout: dict) -> list:
    """The portal round the mouth (local origin: the ramp's hinge): two jambs and the lintel, chamfered."""
    out = []
    for s in (-1, 1):
        out.append(L.box(s * 1.3 if s > 0 else -1.78, 1.78 if s > 0 else -1.3, -0.3, 0.12, BELLY_H - 1.0, 2.95))
    out.append(L.box(-1.78, 1.78, -0.32, 0.1, 2.55, 3.05))
    boxes = []
    for bv, bf in out:
        c = tuple(sum(q[k] for q in bv) / len(bv) for k in range(3))
        boxes.append((bv, L.orient(bv, bf, lambda _c, c=c: c)))
    v, f = L.merge(*boxes)
    return _skin("portal", [(x, y, h + 1.0) for x, y, h in v], f, size=1.2, inset=0.02, depth=0.012,
                 mats=("ext_frame", "hull_silver"))


def mouth_lights(args: dict, layout: dict) -> list:
    """The amber strips on the portal's inner faces and under its lintel (local origin: the ramp's hinge)."""
    out = []
    for s in (-1, 1):
        for k in range(5):
            h0 = 1.15 + k * 0.48
            out.append(L.box(s * 1.285 - 0.02, s * 1.285 + 0.02, -0.22, -0.06, h0, h0 + 0.34))
    for k in range(4):
        x0 = -1.0 + k * 0.55
        out.append(L.box(x0, x0 + 0.35, -0.24, -0.08, 3.53, 3.56))
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
    """The amber dashes along both edges of the ramp's deck (local origin: the hinge)."""
    rp, deck = layout["ramp"], layout["deck"]
    run = rp["hinge"][1] - rp["foot"][1]
    fall = deck["floor_h"] - deck["ground_h"]
    length = math.hypot(run, fall)
    along = (0.0, -run / length, -fall / length)
    up = _norm((0.0, -fall, run))
    out = []
    for s in (-1, 1):
        for k in range(6):
            sa = 0.25 + k * (length - 0.5) / 5.5
            c = _add(_add(_add((0.0, 0.0, deck["floor_h"]), along, sa), (1.0, 0, 0), s * (rp["width_m"] / 2 - 0.2)),
                     up, 0.004)
            out.append(_obox(c, (0.035, 0, 0), _lerp((0, 0, 0), along, 0.13), _lerp((0, 0, 0), up, 0.01)))
    return [L.part("ramp_lights", *L.merge(*out), "glow_amber")]


def leg(args: dict, layout: dict) -> list:
    """A landing leg (splaying toward local +x; exterior.toml yaws it outward): the mount under the belly, the strut,
    the knee, the lower strut, a chrome piston and the faceted foot pad."""
    top = BELLY_H
    knee, ankle, foot = (0.42, 0.0, 0.34), (0.62, 0.0, 0.14), (0.66, 0.0, 0.0)
    mount = _obox((0.0, 0.0, top - 0.07), (0.3, 0, 0), (0, 0.24, 0), (0, 0, 0.07))
    upper = _rod((0.0, 0.0, top - 0.1), knee, 0.1, 10)
    lower = _rod(knee, ankle, 0.085, 10)
    joint = _rod((knee[0], -0.14, knee[2]), (knee[0], 0.14, knee[2]), 0.13, 12)
    piston = _rod((-0.12, 0.0, top - 0.12), (0.55, 0.0, 0.2), 0.045, 8)
    pad_v, pad_f = L.disc(0.36, 8, 0.0, 0.07)
    cap_v, cap_f = L.disc(0.28, 8, 0.07, 0.13)
    pad = L.merge(([(x + foot[0], y, h) for x, y, h in pad_v], pad_f), ([(x + foot[0], y, h) for x, y, h in cap_v], cap_f))
    return [L.part("leg_mount", *mount, "hull_dark"), L.part("leg_strut", *L.merge(upper, lower), "leg_metal"),
            L.part("leg_joint", *joint, "ext_frame"), L.part("leg_piston", *piston, "ext_chrome"),
            L.part("leg_pad", *pad, "hull_dark")]


def nozzle(args: dict, layout: dict) -> list:
    """An engine nozzle along +y (south): faceted housing, the bell, the dark throat (lights: nozzle_ring)."""
    housing = _lathe_y([(0.0, -0.6), (0.78, -0.6), (0.8, 0.3), (0.74, 0.55)], 12, math.pi / 12)
    bell = _lathe_y([(0.71, 0.5), (0.69, 1.32), (0.6, 1.36)], 24)
    tv, tf = _lathe_y([(0.58, 1.34), (0.45, 1.0), (0.0, 0.85)], 24)
    throat = (tv, L.orient(tv, tf, lambda c: (0.0, c[1] - 1.0, 0.0)))  # the funnel's inside faces the back
    return (_skin("housing", *housing, size=0.9, inset=0.015, depth=0.01, mats=("hull_dark", "ext_frame"))
            + [L.part("bell", *bell, "ext_frame"), L.part("throat", *throat, "ext_nozzle_inner")])


def nozzle_ring(args: dict, layout: dict) -> list:
    """A nozzle's cyan lights: the band round the bell and the segmented ring in its rear face."""
    band = _lathe_y([(0.0, 1.0), (0.705, 1.0), (0.705, 1.12), (0.0, 1.12)], 24)
    segs = []
    for k in range(8):
        a0, a1 = 2 * math.pi * k / 8 + 0.08, 2 * math.pi * (k + 1) / 8 - 0.08
        v, f = L.sector(0.42, 0.52, a0, a1, 1.18, 1.22)
        segs.append(([(x, h, y) for x, y, h in v], f))
    core = _lathe_y([(0.0, 0.88), (0.18, 0.88), (0.0, 0.9)], 12)
    return [L.part("nozzle_band", *band, "glow_cyan"), L.part("nozzle_segments", *L.merge(*segs), "glow_cyan"),
            L.part("nozzle_core", *core, "ext_glow_cyan_dim")]


# --- the clearing --------------------------------------------------------------------------------------------------
def ground(args: dict, layout: dict) -> list:
    """The clearing's ground: flat within 16 m (the walk's world boundary stays at h 0), rolling gently beyond."""
    radii = [0.0, 5.0, 10.0, 16.0, 21.0, 27.0, 35.0, 45.0, 58.0, 75.0]
    segs = 40
    v = [(0.0, 0.0, 0.0)]
    for r in radii[1:]:
        for j in range(segs):
            a = 2 * math.pi * (j + 0.5 * (radii.index(r) % 2)) / segs
            h = 0.0 if r <= 16.0 else (r - 16.0) * 0.035 + 0.6 * _hash(r, j) * min(1.0, (r - 16.0) / 10.0)
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


for _name in ("hull_wing", "stripes", "blade", "hull_drum", "hull_nose", "hull_pod", "window_frame", "nozzle_mount",
              "bubble_collar", "bubble_glass", "bubble_glow", "mouth_frame", "mouth_lights", "ramp", "ramp_lights",
              "leg", "nozzle", "nozzle_ring", "ground", "pine", "rock"):
    globals()[_name] = _outward(globals()[_name])

import ship_hull_skin  # noqa: E402  (the manta's skin; it imports this module's helpers)

MODULES.append(ship_hull_skin)
