"""The alien's neck as one column (art #196, S9b; runs inside Blender from alien_assemble.py after the weld).

The engineer's note on S9: "the neck still looks crooked". Two causes, measured on S9's character:
1. The shape. Per angle around the ring's axis the neck's radius had a plateau from the body's side of the weld
   (z 1.36 to 1.40) and then a second fast drop on the head's side (1.41 to 1.44, up to 4.8 mm per 8 mm at the back):
   a pinch above the weld and a step at the nape; at the front the throat dipped 4 mm at the weld.
2. The skinning. The Neck bone (1.339 to 1.437) never owned more than 0.70 of any vertex; the Head bone already held
   0.30 at the weld (1.39) and the shoulders up to 0.88 of the neck's sides at 1.35. So Idle's shoulders dragged the
   neck's sides (an uneven bump seen from behind) and a nod swung the weld band about a pivot 5 cm above it.

The fix, one smooth column from the shoulders to under the jaw:
- loft(): per angle, the radius between a lower anchor on the shoulders (LOW_Z) and an upper anchor under the jaw and
  at the nape (TOP_Z) is replaced by a monotone cubic Hermite through the anchors' radius and slope (Fritsch and
  Carlson's limits, so it never dips below its ends: no pinch), eased in over the band's outer EASE share.
  Vertices move only along the horizontal radial line from the ring's axis, so the weld ring stays one ring.
- column_weights(): in the same column the weights become a smooth field of height: the lower bones (UpperChest and
  the shoulders, in their own proportions) fade out over WEIGHT_LOW, the Head fades in over WEIGHT_HEAD (relative to
  the upper anchor), the Neck takes the rest; outside the column the old weights are kept, with a soft edge; then
  WEIGHT_SMOOTH neighbour-average passes inside the column.
"""
from __future__ import annotations

import math

import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

# anchor heights by angle t from the front (0) to the back (pi), m: a + b * (1 - cos t) / 2 + c * sin(t)^2
LOW_Z = (1.338, 0.0, 0.016)  # the shoulders' top: front and back 1.338, the sides 1.354 (the trapezius is higher there)
TOP_Z = (1.418, 0.026, 0.0)  # under the jaw (front 1.418, where the throat turns into the jaw) to the nape (1.444)
EASE = 0.12  # the share of the band at each end over which the loft eases in
SAMPLES = 72  # anchor samples around the axis
R_MARGIN = 0.010  # a vertex belongs to the column if within its anchors' larger radius plus this, m
WEIGHT_LOW = (1.318, 1.372)  # the lower bones fade out over these heights, m
WEIGHT_HEAD = (-0.030, 0.022)  # the Head fades in over these offsets from the upper anchor, m
WEIGHT_EDGE = (0.008, 0.026)  # outside the column the new weights fade to the old over these radii beyond it, m
WEIGHT_SMOOTH = 6
LOWER = ("UpperChest", "LeftShoulder", "RightShoulder")


def _ss(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def _anchor_z(spec, t):
    a, b, c = spec
    return a + b * (1.0 - math.cos(t)) / 2.0 + c * math.sin(t) ** 2


def _angle(co, cx, cy):
    return math.atan2(co.x - cx, -(co.y - cy))  # 0 the front (-Y), +pi/2 the character's left (+X)


class _Column:
    """The anchors per angle (sampled, interpolated) and the target radius."""

    def __init__(self, bm, ring):
        self.cx, self.cy = ring["centre"]
        bvh = BVHTree.FromBMesh(bm)

        def r_at(t, z):
            o = Vector((self.cx, self.cy, z))
            hit = bvh.ray_cast(o, Vector((math.sin(t), -math.cos(t), 0.0)), 0.3)
            return (hit[0] - o).length if hit[0] is not None else float("nan")

        self.rows = []
        for k in range(SAMPLES):
            t = 2 * math.pi * k / SAMPLES
            zl, zu = _anchor_z(LOW_Z, t), _anchor_z(TOP_Z, t)
            rl, ru = r_at(t, zl), r_at(t, zu)
            sl = (r_at(t, zl + 0.004) - r_at(t, zl - 0.004)) / 0.008
            su = (r_at(t, zu + 0.003) - r_at(t, zu - 0.003)) / 0.006
            self.rows.append((zl, zu, rl, ru, sl, su))

    def anchors(self, t):
        f = (t % (2 * math.pi)) / (2 * math.pi) * SAMPLES
        i = int(f) % SAMPLES
        j = (i + 1) % SAMPLES
        w = f - int(f)
        return tuple(a + w * (b - a) for a, b in zip(self.rows[i], self.rows[j]))

    def target(self, t, z):
        """(target radius, ease weight in 0..1, zl, zu, the column's radius limit) at angle t and height z."""
        zl, zu, rl, ru, sl, su = self.anchors(t)
        h = zu - zl
        d = ru - rl
        m0, m1 = sl * h, su * h
        if abs(d) < 1e-6:
            m0 = m1 = 0.0
        else:  # Fritsch-Carlson: no slope against the secant, and alpha^2 + beta^2 <= 9 (monotone, no dip)
            m0 = m0 if m0 * d > 0 else 0.0
            m1 = m1 if m1 * d > 0 else 0.0
            a, b = m0 / d, m1 / d
            s = a * a + b * b
            if s > 9.0:
                k = 3.0 / math.sqrt(s)
                m0, m1 = m0 * k, m1 * k
        u = min(1.0, max(0.0, (z - zl) / h))
        r = ((2 * u ** 3 - 3 * u ** 2 + 1) * rl + (u ** 3 - 2 * u ** 2 + u) * m0
             + (-2 * u ** 3 + 3 * u ** 2) * ru + (u ** 3 - u ** 2) * m1)
        w = _ss(0.0, EASE, u) * (1.0 - _ss(1.0 - EASE, 1.0, u))
        return r, w, zl, zu, max(rl, ru) + R_MARGIN

    def radius(self, co):
        return math.hypot(co.x - self.cx, co.y - self.cy)


def profile(bm, ring, angles=(0, 45, 90, 135, 180), zs=None):
    """The neck's radius (mm) per angle (degrees) and height, from the axis outwards: the report's before and after."""
    col = _Column(bm, ring)
    bvh = BVHTree.FromBMesh(bm)
    zs = zs or [round(1.33 + 0.01 * i, 3) for i in range(14)]
    out = {}
    for a in angles:
        t = math.radians(a)
        row = []
        for z in zs:
            o = Vector((col.cx, col.cy, z))
            hit = bvh.ray_cast(o, Vector((math.sin(t), -math.cos(t), 0.0)), 0.3)
            row.append(round((hit[0] - o).length * 1000, 1) if hit[0] is not None else None)
        out[str(a)] = row
    return {"z": zs, "r_mm": out}


def loft(bm, ring):
    """Moves the column's vertices radially onto the per-angle Hermite. Returns the measures."""
    col = _Column(bm, ring)
    moved, most, bumps_before = 0, 0.0, 0.0
    for v in bm.verts:
        co = v.co
        t = _angle(co, col.cx, col.cy)
        r = col.radius(co)
        rt, w, zl, zu, rmax = col.target(t, co.z)
        if not (zl < co.z < zu) or r > rmax or r < 1e-4 or w <= 0.0:
            continue
        k = (r + w * (rt - r)) / r
        old = co.copy()
        co.x = col.cx + (co.x - col.cx) * k
        co.y = col.cy + (co.y - col.cy) * k
        most = max(most, (co - old).length)
        bumps_before = max(bumps_before, r - rt)
        moved += 1
    bm.normal_update()
    return {"verts": moved, "max_move_mm": round(most * 1000, 2), "max_inward_mm": round(bumps_before * 1000, 2),
            "low_z": LOW_Z, "top_z": TOP_Z, "ease": EASE}


def column_weights(body, ring):
    """The column's skin weights as a smooth field of height (see the module docstring). Returns the measures."""
    me = body.data
    bm = bmesh.new()
    bm.from_mesh(me)
    col = _Column(bm, ring)
    bm.free()
    gi = {g.name: g.index for g in body.vertex_groups}
    for n in ("Neck", "Head", *LOWER):
        if n not in gi:
            gi[n] = body.vertex_groups.new(name=n).index
    gname = {i: n for n, i in gi.items()}
    old = [{gname[g.group]: g.weight for g in v.groups if g.weight > 0.0} for v in me.vertices]
    new = list(old)
    mask = [0.0] * len(me.vertices)
    for v in me.vertices:
        co = v.co
        t = _angle(co, col.cx, col.cy)
        zl, zu, rl, ru, _sl, _su = col.anchors(t)
        if co.z < WEIGHT_LOW[0] - 0.02 or co.z > zu + WEIGHT_HEAD[1] + 0.01:
            continue
        r = col.radius(co)
        rmax = max(rl, ru) if co.z < zu else ru
        m = 1.0 - _ss(rmax + WEIGHT_EDGE[0], rmax + WEIGHT_EDGE[1], r)
        m *= _ss(WEIGHT_LOW[0] - 0.02, WEIGHT_LOW[0], co.z)
        if m <= 0.0:
            continue
        o = old[v.index]
        lower = {n: w for n, w in o.items() if n in LOWER}
        ls = sum(lower.values())
        if ls < 1e-6:
            lower, ls = {"UpperChest": 1.0}, 1.0
        w_low = 1.0 - _ss(*WEIGHT_LOW, co.z)
        w_head = _ss(zu + WEIGHT_HEAD[0], zu + WEIGHT_HEAD[1], co.z) * (1.0 - w_low)
        field = {n: w_low * w / ls for n, w in lower.items()}
        field["Head"] = field.get("Head", 0.0) + w_head
        field["Neck"] = field.get("Neck", 0.0) + max(0.0, 1.0 - w_low - w_head)
        keys = set(o) | set(field)
        new[v.index] = {n: (1 - m) * o.get(n, 0.0) + m * field.get(n, 0.0) for n in keys}
        mask[v.index] = m
    # neighbour averaging inside the column (the edge vertices pull towards their old neighbours)
    nbr = [[] for _ in me.vertices]
    for e in me.edges:
        a, b = e.vertices
        nbr[a].append(b)
        nbr[b].append(a)
    for _ in range(WEIGHT_SMOOTH):
        nxt = list(new)
        for i, m in enumerate(mask):
            if m <= 0.0 or not nbr[i]:
                continue
            acc = {}
            for j in nbr[i]:
                for n, w in new[j].items():
                    acc[n] = acc.get(n, 0.0) + w / len(nbr[i])
            keys = set(acc) | set(new[i])
            nxt[i] = {n: (1 - 0.5 * m) * new[i].get(n, 0.0) + 0.5 * m * acc.get(n, 0.0) for n in keys}
        new = nxt
    changed = 0
    for i, m in enumerate(mask):
        if m <= 0.0:
            continue
        top = sorted(((w, n) for n, w in new[i].items() if w > 1e-4), reverse=True)[:4]
        s = sum(w for w, _ in top)
        for n in gi:
            body.vertex_groups[n].remove([i])
        for w, n in top:
            body.vertex_groups[n].add([i], w / s, "REPLACE")
        changed += 1
    # the report: the Neck's largest share now, and the Head's at the weld ring
    neck_max = max((new[i].get("Neck", 0.0) for i, m in enumerate(mask) if m > 0.5), default=0.0)
    ring_head = [new[v.index].get("Head", 0.0) for v in me.vertices if abs(v.co.z - ring["z"]) < 0.002
                 and col.radius(v.co) < 0.07]
    return {"vertices": changed, "neck_max": round(neck_max, 3),
            "head_at_ring_max": round(max(ring_head, default=0.0), 3), "low": WEIGHT_LOW, "head": WEIGHT_HEAD,
            "smooth": WEIGHT_SMOOTH}
