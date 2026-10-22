"""The clearing round the ship (art #263, hull lane step 3; docs/ship.md "The clearing"): the dirt patch under the ship
and the dirt path from the ramp's foot to the treeline, grass tufts, bushes, fallen logs and stumps, the irregular
pines of the forest edge, and the string of warm party lights along the path (its posts are their own pieces). The
EXTERIOR lane owns this file. Builders work in the plan frame (x east, y south, h up; metres); the dirt and the
string are placed at the origin, the rest at their own spot (exterior.toml). Numbers:
- dirt patch: an irregular blob about 15 x 11 m round the ship (radius capped at 15.6, inside the ground's flat 16 m),
  0.006 over the ground; the path: PATH's centre line from the ramp's foot (0, -9.6) north-west to the treeline at
  r ~ 41, 2.0 m wide at the ramp narrowing to 1.3 m, 0.012 over the ground (0.05 beyond r 16, over its coarse facets).
- tufts: 9..14 blades 0.18..0.5 m; bushes: 5..8 lumps in a size-metre spread; logs: r 0.22..0.3, 3..4.5 m with cut
  ends and stubs; stumps r 0.3, 0.45 m.
- pines (`pine2`): a bare trunk below `bare` x height, then 8..13 layers of 5..7 drooping branch clumps each, every
  clump its own angle, length and droop (the silhouette reads as branches, not stacked cones), a slight lean.
- party lights: posts 2.7 m, 1.6 m off the path's centre on alternating sides at POST_T; the string sags 0.45 m between posts, a bulb every 0.6 m, one in four amber."""

from __future__ import annotations

import math

import ship_hull as H
import ship_lib as L

L.MATERIALS.update({
    "ext_dirt": {"base": (0.15, 0.1, 0.065, 1.0), "metallic": 0.0, "roughness": 0.97},
    "ext_path": {"base": (0.2, 0.14, 0.09, 1.0), "metallic": 0.0, "roughness": 0.95},
    "ext_grass": {"base": (0.07, 0.11, 0.04, 1.0), "metallic": 0.0, "roughness": 0.85},
    "ext_grass_dry": {"base": (0.2, 0.16, 0.07, 1.0), "metallic": 0.0, "roughness": 0.9},
    "ext_leaf": {"base": (0.035, 0.07, 0.035, 1.0), "metallic": 0.0, "roughness": 0.8},
    "ext_leaf_b": {"base": (0.06, 0.085, 0.03, 1.0), "metallic": 0.0, "roughness": 0.85},
    "ext_wood_cut": {"base": (0.42, 0.3, 0.18, 1.0), "metallic": 0.0, "roughness": 0.8},
    "ext_wire": {"base": (0.02, 0.02, 0.02, 1.0), "metallic": 0.3, "roughness": 0.6},
    "ext_bulb": {"base": (1.0, 0.85, 0.6, 1.0), "metallic": 0.0, "roughness": 0.3, "emission": (1.0, 0.78, 0.45),
                 "strength": 8.0},
    "ext_bulb_amber": {"base": (1.0, 0.55, 0.2, 1.0), "metallic": 0.0, "roughness": 0.3,
                       "emission": (1.0, 0.45, 0.12), "strength": 8.0},
})

# the path's centre line from the ramp's foot (the ramp ends at y -9.4) north-west to the treeline
PATH = [(0.0, -9.6), (-0.5, -13.0), (-2.6, -16.6), (-6.0, -19.8), (-10.4, -22.6), (-15.4, -25.4), (-21.0, -28.8),
        (-26.5, -32.5)]
POST_T = (0.015, 0.11, 0.2, 0.29, 0.38, 0.48, 0.58)  # the posts' arc fractions along the path
POST_OFF = 1.6  # metres off the path's centre, sides alternating
POST_H = 2.7


# --- the ground's height (the ground piece's own facets) -------------------------------------------------------------
_GROUND: list = []


def ground_h(x: float, y: float) -> float:
    """The ground piece's height at (x, y): its triangle under the point, interpolated (0 inside r 16)."""
    if math.hypot(x, y) <= 16.0:
        return 0.0
    if not _GROUND:
        part = H.ground({}, {})[0]
        v = part["verts"]
        _GROUND.extend((v[a], v[b], v[c]) for a, b, c in part["faces"])
    for a, b, c in _GROUND:
        d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(d) < 1e-12:
            continue
        w0 = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / d
        w1 = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / d
        w2 = 1.0 - w0 - w1
        if min(w0, w1, w2) >= -1e-9:
            return w0 * a[2] + w1 * b[2] + w2 * c[2] + 0.005
    return 0.0


def path_point(t: float) -> tuple:
    """The path's centre at arc fraction t (0 the ramp's foot, 1 the treeline) and its unit direction."""
    seg = [math.dist(p, q) for p, q in zip(PATH, PATH[1:])]
    s = t * sum(seg)
    for (p, q), d in zip(zip(PATH, PATH[1:]), seg):
        if s <= d or (p, q) == (PATH[-2], PATH[-1]):
            k = min(s / d, 1.0)
            return (p[0] + (q[0] - p[0]) * k, p[1] + (q[1] - p[1]) * k), ((q[0] - p[0]) / d, (q[1] - p[1]) / d)
        s -= d
    return PATH[-1], (0.0, -1.0)


def _flat(name, outline, h, mat):
    """A flat polygon (fan from its centroid) at height h(x, y), facing up."""
    cx = sum(p[0] for p in outline) / len(outline)
    cy = sum(p[1] for p in outline) / len(outline)
    v = [(cx, cy, h(cx, cy))] + [(x, y, h(x, y)) for x, y in outline]
    n = len(outline)
    f = L.orient(v, [(0, 1 + i, 1 + (i + 1) % n) for i in range(n)], lambda c: (c[0], c[1], c[2] - 1.0))
    return L.part(name, v, f, mat, solid=False)



def _posts() -> list:
    out = []
    for k, t in enumerate(POST_T):
        (x, y), (dx, dy) = path_point(t)
        side = 1.0 if k % 2 == 0 else -1.0
        out.append((round(x - dy * POST_OFF * side, 2), round(y + dx * POST_OFF * side, 2)))
    return out


POSTS = _posts()  # the party lights' posts along the path [(x, y)]


# --- the builders --------------------------------------------------------------------------------------------------
def dirt_patch(args: dict, layout: dict) -> list:
    """The trodden dirt under the ship: an irregular blob about 15 x 11 m, two rings of facets."""
    n = 56
    outer, inner = [], []
    for i in range(n):
        a = 2 * math.pi * i / n
        r = 1.0 / math.hypot(math.cos(a) / 15.0, math.sin(a) / 11.0)
        r = min(r * (0.86 + 0.16 * H._hash(i, 7.0) + 0.06 * math.sin(3 * a + 1.0)), 15.6)
        outer.append((r * math.cos(a), r * math.sin(a), 0.006))
        inner.append((0.55 * r * math.cos(a), 0.55 * r * math.sin(a), 0.006))
    v = [(0.0, 0.0, 0.006)] + inner + outer
    f = [(0, 1 + i, 1 + (i + 1) % n) for i in range(n)]
    f += [(1 + i, 1 + n + i, 1 + n + (i + 1) % n, 1 + (i + 1) % n) for i in range(n)]
    f = L.orient(v, f, lambda c: (c[0], c[1], c[2] - 1.0))
    return [L.part("dirt", v, f, "ext_dirt", solid=False)]


def dirt_path(args: dict, layout: dict) -> list:
    """The path from the ramp's foot to the treeline: a ribbon with a jittered edge, following the ground."""
    steps = 60
    left, right = [], []
    for i in range(steps + 1):
        t = i / steps
        (x, y), (dx, dy) = path_point(t)
        w = (1.0 - 0.35 * t) * (0.9 + 0.2 * H._hash(i, 3.0))
        for side, out in ((1.0, left), (-1.0, right)):
            px, py = x - dy * w * side, y + dx * w * side
            lift = 0.012 if math.hypot(px, py) <= 15.8 else 0.05
            out.append((px, py, ground_h(px, py) + lift))
    v = left + right
    m = steps + 1
    f = [(i, i + 1, m + i + 1, m + i) for i in range(steps)]
    f = L.orient(v, f, lambda c: (c[0], c[1], c[2] - 1.0))
    return [L.part("path", v, f, "ext_path", solid=False)]


def _blade(x, y, h, lean, a, w):
    """One grass blade: a thin closed tetrahedron from a small base triangle to a leaning tip."""
    base = [(x + w * math.cos(a + k * 2.1), y + w * math.sin(a + k * 2.1), -0.03) for k in range(3)]
    tip = (x + lean * math.cos(a), y + lean * math.sin(a), h)
    return base + [tip], [(0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3)]


def tuft(args: dict, layout: dict) -> list:
    """A grass tuft (args seed, dry 0/1): 9..14 leaning blades."""
    seed = float(args.get("seed", 1.0))
    n = 9 + int(6 * H._hash(seed, 1.0))
    blades = []
    for k in range(n):
        a = 2 * math.pi * H._hash(seed, k, 2.0)
        r = 0.12 * H._hash(seed, k, 3.0)
        h = 0.18 + 0.32 * H._hash(seed, k, 4.0)
        blades.append(_blade(r * math.cos(a), r * math.sin(a), h, 0.06 + 0.12 * H._hash(seed, k, 5.0), a, 0.018))
    mat = "ext_grass_dry" if float(args.get("dry", 0.0)) > 0.5 else "ext_grass"
    return [L.part("tuft", *L.merge(*blades), mat)]


def bush(args: dict, layout: dict) -> list:
    """A low bush (args size, seed): 5..8 faceted lumps in two greens."""
    size, seed = float(args.get("size", 1.0)), float(args.get("seed", 1.0))
    n = 5 + int(4 * H._hash(seed, 9.0))
    lumps = ([], [])
    for k in range(n):
        a = 2 * math.pi * (k + 0.5 * H._hash(seed, k)) / n
        d = size * 0.45 * H._hash(seed, k, 1.0) if k else 0.0
        r = size * (0.32 + 0.22 * H._hash(seed, k, 2.0))
        v, f = L.sphere(1.0, 4, 7)
        c = (d * math.cos(a), d * math.sin(a), r * 0.55)
        v = [(c[0] + x * r * (0.85 + 0.3 * H._hash(seed, k, i)), c[1] + y * r * (0.85 + 0.3 * H._hash(k, i, seed)),
              c[2] + z * r * 0.8) for i, (x, y, z) in enumerate(v)]
        lumps[k % 2].append((v, f))
    return [L.part("bush_a", *L.merge(*lumps[0]), "ext_leaf"), L.part("bush_b", *L.merge(*lumps[1]), "ext_leaf_b")]


def _cap(p, d, r, n):
    """A thin cut disc (0.012 thick) at p facing along the unit direction d: the log's light end grain."""
    u = H._norm(H._cross(d, (0.0, 0.0, 1.0) if abs(d[2]) < 0.9 else (1.0, 0.0, 0.0)))
    w = H._cross(d, u)
    v = []
    for off in (-0.002, 0.01):
        q = H._add(p, d, off)
        v += [H._add(H._add(q, u, r * math.cos(2 * math.pi * i / n)), w, r * math.sin(2 * math.pi * i / n))
              for i in range(n)]
    f = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i)
                                                                    for i in range(n)]
    return v, f


def log(args: dict, layout: dict) -> list:
    """A fallen log along x (args length, r, seed): bark, two light cut ends, two branch stubs."""
    length, r, seed = float(args.get("length", 3.5)), float(args.get("r", 0.25)), float(args.get("seed", 1.0))
    p0, p1 = (-length / 2, 0.0, r * 0.8), (length / 2, 0.0, r * 0.75)
    bark = [H._rod(p0, p1, r, 9)]
    for k in (0.3, 0.68):
        a = 2.4 * H._hash(seed, k)
        s = (length * (k - 0.5), 0.0, r * 0.78)
        bark.append(H._rod(s, H._add(s, (0.15, 0.45 * math.cos(a), 0.45 * abs(math.sin(a)) + 0.1)), r * 0.28, 6))
    ends = L.merge(_cap(p0, (-1.0, 0.0, 0.0), r * 0.92, 9), _cap(p1, (1.0, 0.0, 0.0), r * 0.92, 9))
    return [L.part("log_bark", *L.merge(*bark), "ext_bark"), L.part("log_cut", *ends, "ext_wood_cut")]


def stump(args: dict, layout: dict) -> list:
    """A sawn stump: a short trunk with three root flares and a light cut top."""
    r, h = float(args.get("r", 0.3)), float(args.get("h", 0.45))
    parts = [H._rod((0.0, 0.0, -0.2), (0.0, 0.0, h), r, 10)]
    for k in range(3):
        a = 2 * math.pi * k / 3 + 0.4
        parts.append(H._rod((0.0, 0.0, 0.15), (r * 2.0 * math.cos(a), r * 2.0 * math.sin(a), -0.08), r * 0.35, 6))
    return [L.part("stump_bark", *L.merge(*parts), "ext_bark"),
            L.part("stump_cut", *_cap((0.0, 0.0, h), (0.0, 0.0, 1.0), r * 0.92, 10), "ext_wood_cut")]


def pine2(args: dict, layout: dict) -> list:
    """An irregular pine (args height, seed, bare): a leaning bare trunk, then layers of separate drooping branch
    clumps (each a flat faceted spindle with its own angle, length and droop) and a spike top."""
    height, seed, bare = float(args.get("height", 16.0)), float(args.get("seed", 1.0)), float(args.get("bare", 0.3))
    lean = (0.015 * height * (H._hash(seed, 1.0) - 0.5), 0.015 * height * (H._hash(seed, 2.0) - 0.5))

    def axis(h):
        return (lean[0] * h / height, lean[1] * h / height, h)

    r0 = 0.018 * height + 0.08
    trunk = L.merge(H._rod(axis(-0.3), axis(height * 0.5), r0, 8), H._rod(axis(height * 0.5), axis(height * 0.93),
                                                                            r0 * 0.55, 6))
    n = 8 + int(height / 4)
    clumps = []
    for k in range(n):
        u = k / (n - 1)
        hb = height * (bare + (0.9 - bare) * u)
        reach = height * (0.26 * (1.0 - u) ** 0.85 + 0.035) * (0.8 + 0.4 * H._hash(seed, k))
        m = 5 + int(3 * H._hash(seed, k, 1.0))
        for j in range(m):
            a = 2 * math.pi * (j + 0.7 * H._hash(seed, k, j)) / m
            ln = reach * (0.65 + 0.5 * H._hash(seed, j, k))
            droop = ln * (0.3 + 0.3 * H._hash(k, j, seed))
            wid, thick = ln * 0.36, ln * 0.13
            d, p = (math.cos(a), math.sin(a), 0.0), (-math.sin(a), math.cos(a), 0.0)
            root = H._add(axis(hb + 0.15 * ln), d, r0 * 0.6)
            tip = H._add(H._add(root, d, ln), (0.0, 0.0, -droop))
            mid = H._add(H._add(root, d, ln * 0.5), (0.0, 0.0, -droop * 0.3))
            v = [root, tip, H._add(mid, p, wid), H._add(mid, (0, 0, 1), thick), H._add(mid, p, -wid),
                 H._add(mid, (0, 0, 1), -thick * 0.5)]
            f = [(0, 2, 3), (0, 3, 4), (0, 4, 5), (0, 5, 2), (1, 3, 2), (1, 4, 3), (1, 5, 4), (1, 2, 5)]
            clumps.append((v, f))
    top = axis(height)
    spike = H._rod(axis(height * 0.86), top, height * 0.025, 6)
    clumps.append(spike)
    return [L.part("pine_trunk", *trunk, "ext_bark"), L.part("pine_needles", *L.merge(*clumps), "ext_needles")]


def party_post(args: dict, layout: dict) -> list:
    """A wooden post for the party lights: 2.7 m, a small cross arm and a hook ring at the top."""
    parts = [H._rod((0.0, 0.0, -0.3), (0.0, 0.0, POST_H), 0.055, 7),
             H._rod((-0.18, 0.0, POST_H - 0.12), (0.18, 0.0, POST_H - 0.12), 0.03, 6)]
    return [L.part("post", *L.merge(*parts), "ext_bark")]


def party_lights(args: dict, layout: dict) -> list:
    """The string of party lights (in the plan frame, placed at the origin): over the posts POSTS from the ramp's
    foot along the path, sagging 0.45 m per span, a bulb hanging every 0.6 m (one in four amber)."""
    pts = [(x, y, ground_h(x, y) + POST_H - 0.1) for x, y in POSTS]
    wire, warm, amber = [], [], []
    count = 0
    for p, q in zip(pts, pts[1:]):
        span = math.dist(p[:2], q[:2])
        steps = max(6, int(span / 0.6))
        line = []
        for i in range(steps + 1):
            t = i / steps
            line.append(H._lerp(p, q, t)[:2] + (p[2] + (q[2] - p[2]) * t - 0.45 * 4 * t * (1 - t),))
        for i, (a, b) in enumerate(zip(line, line[1:])):
            wire.append(H._rod(a, b, 0.009, 4))
            if i:
                c = (a[0], a[1], a[2] - 0.09)
                v, f = L.sphere(0.055, 3, 6)
                (amber if count % 4 == 3 else warm).append(([(x + c[0], y + c[1], z + c[2]) for x, y, z in v], f))
                wire.append(H._rod(a, (a[0], a[1], a[2] - 0.05), 0.012, 4))
                count += 1
    return [L.part("wire", *L.merge(*wire), "ext_wire"), L.part("bulbs", *L.merge(*warm), "ext_bulb"),
            L.part("bulbs_amber", *L.merge(*amber), "ext_bulb_amber")]


for _name in ("dirt_patch", "dirt_path"):
    globals()[_name] = H._outward(globals()[_name])
