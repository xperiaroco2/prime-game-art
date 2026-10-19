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


# S9c: the column. S9b's loft left a cone in profile (the back 68 mm behind the ring's axis at the shoulders, 35 mm at
# the nape); u1 and rf2 have a longer column with near-parallel front and back lines, the skull's back running on into
# it and the trapezius slope starting lower. column() re-lofts each angle through a monotone piecewise cubic (PCHIP:
# no overshoot, a zero slope at the nape's turn) through four points: the shoulders' surface (zl, with its slope), the
# column's foot (za, COL_R[0]), its head (zb, COL_R[1]) and the skull or the jaw (zu, with its slope; the first height
# above the column where the surface stands COL_JOIN out of it). The front keeps S9b's straight throat: the column fades
# in between COL_FADE degrees from the front.
COL_R = [(0, 55.5, 55.5), (30, 57.0, 56.0), (60, 53.0, 50.0), (90, 48.0, 46.0), (120, 46.0, 44.5), (150, 46.0, 44.5),
         (180, 46.5, 45.0)]  # by angle from the front (degrees): the column's radius at its foot and its head, mm
COL_LOW = (1.31, -0.01, 0.04)  # zl: the shoulders' anchor (front 1.31, back 1.30, sides 1.35); _anchor_z's form
COL_FOOT = (1.33, 0.03, 0.03)  # za: where the trapezius slope ends and the column starts (back 1.36, sides 1.375)
COL_JOIN = 0.010  # zu: the first height above the column's shortest top (za + COL_MIN) where the radius is the
# column head's + this, m (a long curve into the skull, so the back of the head runs on into the neck)
COL_SEARCH = (1.52, 0.002)  # the search's highest height and step, m
COL_MIN = 0.04  # the column's shortest height before the search starts, m
COL_TOP_GAP = 0.04  # zb = zu - this (at least za + 0.03), m
COL_FADE = (25.0, 60.0)


def _pchip(xs, ys, d0, d1):
    """The slopes of a shape-preserving cubic through (xs, ys) with end slopes d0, d1 (Fritsch-Carlson limited)."""
    n = len(xs)
    h = [xs[i + 1] - xs[i] for i in range(n - 1)]
    s = [(ys[i + 1] - ys[i]) / h[i] for i in range(n - 1)]
    d = [0.0] * n
    for i in range(1, n - 1):
        if s[i - 1] * s[i] <= 0:
            d[i] = 0.0
        else:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            d[i] = (w1 + w2) / (w1 / s[i - 1] + w2 / s[i])
    for i, (dd, ss) in ((0, (d0, s[0])), (n - 1, (d1, s[-1]))):
        if dd * ss <= 0:
            d[i] = 0.0
        else:
            d[i] = dd if abs(dd) <= 3 * abs(ss) else 3 * ss
    return d


def _hermite(xs, ys, ds, x):
    x = min(xs[-1], max(xs[0], x))
    for i in range(len(xs) - 1):
        if x <= xs[i + 1]:
            break
    h = xs[i + 1] - xs[i]
    u = (x - xs[i]) / h
    return ((2 * u ** 3 - 3 * u ** 2 + 1) * ys[i] + (u ** 3 - 2 * u ** 2 + u) * h * ds[i]
            + (-2 * u ** 3 + 3 * u ** 2) * ys[i + 1] + (u ** 3 - u ** 2) * h * ds[i + 1])


def _col_r(t):
    a = abs(math.degrees(math.atan2(math.sin(t), math.cos(t))))
    for (a0, f0, h0), (a1, f1, h1) in zip(COL_R, COL_R[1:]):
        if a <= a1:
            k = (a - a0) / (a1 - a0)
            return (f0 + k * (f1 - f0)) / 1000.0, (h0 + k * (h1 - h0)) / 1000.0
    return COL_R[-1][1] / 1000.0, COL_R[-1][2] / 1000.0


def column(bm, ring):
    """S9c: the near-parallel column (see COL_R). Moves vertices radially, like loft(). Returns the measures."""
    cx, cy = ring["centre"]
    bvh = BVHTree.FromBMesh(bm)

    def r_at(t, z):
        o = Vector((cx, cy, z))
        hit = bvh.ray_cast(o, Vector((math.sin(t), -math.cos(t), 0.0)), 0.4)
        return (hit[0] - o).length if hit[0] is not None else float("nan")

    rows = []
    for k in range(SAMPLES):
        t = 2 * math.pi * k / SAMPLES
        ra, rb = _col_r(t)
        zl, za = _anchor_z(COL_LOW, t), _anchor_z(COL_FOOT, t)
        z = za + COL_MIN
        while z < COL_SEARCH[0] and not r_at(t, z) >= rb + COL_JOIN:
            z += COL_SEARCH[1]
        zu = z
        zb = max(za + 0.03, zu - COL_TOP_GAP)
        rl, ru = r_at(t, zl), r_at(t, zu)
        sl = (r_at(t, zl + 0.004) - r_at(t, zl - 0.004)) / 0.008
        su = (r_at(t, zu + 0.003) - r_at(t, zu - 0.003)) / 0.006
        xs, ys = [zl, za, zb, zu], [rl, ra, rb, ru]
        rows.append((xs, ys, _pchip(xs, ys, sl, su), max(rl, ru, ra) + R_MARGIN))
    moved, most, out_most = 0, 0.0, 0.0
    for v in bm.verts:
        co = v.co
        t = _angle(co, cx, cy)
        f = _ss(*COL_FADE, abs(math.degrees(t)))
        if f <= 0.0:
            continue
        # interpolate the target between the two nearest sampled angles
        fk = (t % (2 * math.pi)) / (2 * math.pi) * SAMPLES
        i, j, w = int(fk) % SAMPLES, (int(fk) + 1) % SAMPLES, fk - int(fk)
        r = math.hypot(co.x - cx, co.y - cy)
        tr, ws = 0.0, 0.0
        for idx, wt in ((i, 1 - w), (j, w)):
            xs, ys, ds, rmax = rows[idx]
            if not (xs[0] < co.z < xs[-1]) or r > rmax:
                break
            u = (co.z - xs[0]) / (xs[-1] - xs[0])
            ease = _ss(0.0, EASE, u) * (1.0 - _ss(1.0 - EASE, 1.0, u))
            tr += wt * _hermite(xs, ys, ds, co.z)
            ws += wt * ease
        else:
            if r < 1e-4:
                continue
            g = f * ws
            k = (r + g * (tr - r)) / r
            old = co.copy()
            co.x = cx + (co.x - cx) * k
            co.y = cy + (co.y - cy) * k
            d = (co - old).length
            most = max(most, d)
            if tr > r:
                out_most = max(out_most, d)
            moved += 1
    bm.normal_update()
    back = rows[SAMPLES // 2]
    side = rows[SAMPLES // 4]
    return {"verts": moved, "max_move_mm": round(most * 1000, 2), "max_outward_mm": round(out_most * 1000, 2),
            "back_z": [round(x, 3) for x in back[0]], "back_r_mm": [round(x * 1000, 1) for x in back[1]],
            "side_z": [round(x, 3) for x in side[0]], "side_r_mm": [round(x * 1000, 1) for x in side[1]],
            "col_r": COL_R, "fade_deg": COL_FADE}


# S9c: the pale throat panel; S9d: its edge as one clean line in profile, from the jaw down the neck and the chest.
# S9c lightened the neck's front by angle around the ring's axis and the jaw's underside by its normal; in profile its
# top edge bulged behind the jaw (the voxel head's normals), a pale wedge showed at the jaw's corner from behind, and at
# the shoulders it met the belly panel's narrow x half width (about 15 % of the chest's depth in profile) with a step.
# S9d: the panel is a cut in profile. A vertex is pale in front of the line y_e(z) (Blender: front is -Y; soft by
# PANEL["soft"]):
# - the chest and belly (up to PANEL["chest_top"]): the front PANEL["depth"] share of the trunk's depth at that height
#   (its front and back at x = 0, measured on the mesh), u1's side view;
# - the neck (from PANEL["neck"][0] to [1]): the ring's axis plus PANEL["neck_y"] (the edge down the side of the neck,
#   about 88 degrees from the front at the column's 46 to 50 mm);
# - under the jaw: a shape-preserving cubic from the neck's line to the head mask's own edge in profile
#   (PANEL["jaw_y"] at PANEL["jaw_z"], with zero slopes at both ends, so it runs on into both as one line), then the cut
#   fades out over PANEL["top"] where the head's mask takes over (the cheek's pale under the eye).
# The cut lives between PANEL["z"] (in from the belly's oval) and PANEL["top"], within PANEL["cap"] of x = 0 (the
# shoulders and the jaw stay teal in front view), off the arms and legs (their weights). It only lightens (the max with
# the old masks), then PANEL["smooth"] neighbour passes inside it.
PANEL = {"depth": 0.40, "chest_top": 1.30, "neck": (1.345, 1.430), "neck_y": 0.002, "jaw_z": 1.535, "jaw_y": -0.026,
         "soft": 0.012, "z": (0.94, 1.04), "top": (1.535, 1.565),
         "cap": [(0.95, 0.10), (1.05, 0.105), (1.15, 0.115), (1.25, 0.115), (1.29, 0.107), (1.32, 0.080), (1.345, 0.068),
                 (1.38, 0.075), (1.42, 0.12), (1.46, 0.20)],
         "cap_soft": 0.016, "limbs": (0.2, 0.5), "smooth": 5}
# S9d's variant grid (S9d/var/shots2): the cap at the chest 0.100, 0.115 (chosen) or 0.130 m at depth 0.40; the
# Idle arm hides the chest's side in profile, so the cap sets the front view (u1's panel with teal sides) and the
# depth the trapezius and the neck. jaw_y and jaw_z: near the head mask's own edge in profile under the eye (y -0.022 at
# z 1.53-1.55, measured; a little forward of it, so less of the cheek peeks out from behind), so the line runs from the neck's side diagonally up to the cheek, as in u1's side view.
LIMBS = ("UpperArm", "LowerArm", "Hand", "Index", "Middle", "Ring", "Thumb", "Little")  # the legs: PANEL["z"], the cap


def _lerp_pts(pts, z):
    if z <= pts[0][0]:
        return pts[0][1]
    for (z0, w0), (z1, w1) in zip(pts, pts[1:]):
        if z <= z1:
            return w0 + (w1 - w0) * (z - z0) / (z1 - z0)
    return pts[-1][1]


def trunk_depth(verts, half=0.03, smooth=2):
    """The trunk's front and back (min and max y of the vertices within `half` of x = 0) per 1 cm bin, averaged over
    +-`smooth` bins: {bin: (front, back)}."""
    raw = {}
    for co in verts:
        if abs(co.x) < half:
            k = int(round(co.z * 100))
            f, b = raw.get(k, (co.y, co.y))
            raw[k] = (min(f, co.y), max(b, co.y))
    out = {}
    for k in raw:
        near = [raw[kk] for kk in range(k - smooth, k + smooth + 1) if kk in raw]
        out[k] = (sum(f for f, _ in near) / len(near), sum(b for _, b in near) / len(near))
    return out


def panel_line(ring, depth_of):
    """y_e(z): the panel's edge in profile (see PANEL). depth_of(z) -> (front, back) of the trunk."""
    P = PANEL
    cy = ring["centre"][1]
    neck_y = cy + P["neck_y"]
    ct, (n0, n1) = P["chest_top"], P["neck"]
    xs, ys = [n1, P["jaw_z"]], [neck_y, P["jaw_y"]]
    ds = _pchip(xs, ys, 0.0, 0.0)

    def chest(z):
        f, b = depth_of(z)
        return f + P["depth"] * (b - f)

    def y_e(z):
        if z <= ct:
            return chest(z)
        if z < n0:  # from the chest's line at chest_top to the neck's
            t = _ss(ct, n0, z)
            return chest(ct) * (1 - t) + neck_y * t
        if z <= n1:
            return neck_y
        return _hermite(xs, ys, ds, z)
    return y_e


def throat_panel(body, ring):
    """Lightens the masks' u (the light mask) in front of the panel's line in profile. Returns the measures."""
    P = PANEL
    me = body.data
    n = len(me.vertices)
    depth = trunk_depth([v.co for v in me.vertices])

    def depth_of(z):
        k = int(round(z * 100))
        for d in range(0, 20):
            for kk in (k - d, k + d):
                if kk in depth:
                    return depth[kk]
        raise ValueError(f"no trunk section near z {z}")
    y_e = panel_line(ring, depth_of)
    gid = {g.index for g in body.vertex_groups if any(name in g.name for name in LIMBS)}
    p = [0.0] * n
    for v in me.vertices:
        co = v.co
        if co.z < P["z"][0] or co.z > P["top"][1]:
            continue
        limb = sum(g.weight for g in v.groups if g.group in gid)
        cap = _lerp_pts(P["cap"], co.z)
        zone = _ss(*P["z"], co.z) * (1.0 - _ss(*P["top"], co.z))
        cut = 1.0 - _ss(-P["soft"], P["soft"], co.y - y_e(co.z))
        p[v.index] = (zone * cut * (1.0 - _ss(cap - P["cap_soft"], cap + P["cap_soft"], abs(co.x)))
                      * (1.0 - _ss(*P["limbs"], limb)))
    uv = me.uv_layers["masks"].data
    old = [None] * n
    for lp in me.loops:
        if old[lp.vertex_index] is None:
            old[lp.vertex_index] = uv[lp.index].uv[0]
    old = [x if x is not None else 0.0 for x in old]
    u = [max(o, q) for o, q in zip(old, p)]
    nbr = [[] for _ in range(n)]
    for e in me.edges:
        a_, b_ = e.vertices
        nbr[a_].append(b_)
        nbr[b_].append(a_)
    for _ in range(P["smooth"]):
        u = [u[i] if p[i] <= 0.0 or not nbr[i] else 0.5 * u[i] + 0.5 * sum(u[j] for j in nbr[i]) / len(nbr[i])
             for i in range(n)]
    for lp in me.loops:
        uv[lp.index].uv[0] = u[lp.vertex_index]
    changed = sum(1 for o, x in zip(old, u) if abs(o - x) > 0.02)
    # the edge in profile: per height, the largest y of a side-facing vertex (x > 0.02) still pale (u > 0.5)
    edge = {}
    for zz in (1.00, 1.10, 1.20, 1.25, 1.30, 1.34, 1.38, 1.42, 1.45, 1.48, 1.51):
        pale = [v.co.y for v in me.vertices if abs(v.co.z - zz) < 0.005 and v.co.x > 0.02 and u[v.index] > 0.5]
        f, b = depth_of(zz)
        wide = [v.co.x for v in me.vertices if abs(v.co.z - zz) < 0.005 and v.co.y < 0.0 and u[v.index] > 0.5]
        edge[f"{zz:.2f}"] = {"y_e": round(y_e(zz), 4), "pale_max_y": round(max(pale), 4) if pale else None,
                             "pale_max_x": round(max(wide), 4) if wide else None,
                             "front": round(f, 4), "back": round(b, 4)}
    return {"changed_vertices": changed, "edge_in_profile": edge, **{k: v for k, v in P.items()}}
