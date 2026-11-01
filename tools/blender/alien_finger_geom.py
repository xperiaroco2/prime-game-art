"""The alien's fingers and thumb rebuilt as smooth tubes (art #196, Hands H1i): plain Python, no Blender.

The engineer (2026-10-31): the fingers looked "bitten by bees", wavy and lumpy as if broken, worst on the thumb; they
should be smooth rounded tubes as on the concept. H1b's `alien_hand_geom.finger` rescaled each vertex's radius by a
Gaussian mean of the measured radius, so every bump of the source mesh stayed (only scaled), and the nearest-segment
projection onto the bone polyline jumps at the joints. Here the finger's surface is defined, not rescaled:

- the axis: the chain's joints, the corners rounded (Chaikin), resampled every 0.5 mm, a rotation-minimising frame;
- the centre: the axis plus a smooth offset (a quadratic in s fitted to the circle centres of 3 mm slices);
- the section: one ellipse per finger (1 + a cos 2t + b sin 2t, fitted to the measured radii, capped);
- the radius along it: the drawing's (hand_dims.toml [fingers]/[thumb]): the root radius held to `root_at`, a linear
  taper to the dome, a round dome at the tip (the finger's length kept: the tip stays where it is);
- each vertex placed on that surface at its own s and angle, the finger's vertices relaxed along it (Laplacian, then
  back onto it) so the rings space evenly, the knuckle blended into the palm over the spec's `ramp`;
- the weights from the bones: along the finger past the ramp each vertex's chain weights are a smooth step across
  each joint (half width `joint_blend` of the local radius).
`measure` gives the radius along the finger per angle sector and its wave (the residual from a Gaussian trend).
"""
from __future__ import annotations

import math

SECTORS = 8


def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def mul(a, k): return (a[0] * k, a[1] * k, a[2] * k)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def length(a): return math.sqrt(dot(a, a))
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def unit(a):
    n = length(a)
    return mul(a, 1.0 / n) if n > 1e-12 else (0.0, 0.0, 0.0)


def smoothstep(e0, e1, x):
    if e1 <= e0:
        return 1.0 if x >= e1 else 0.0
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


class Axis:
    """The finger's smooth axis: the joints' polyline (extended `back` m behind the first joint), corners rounded by
    Chaikin's cutting (the ends kept), resampled every `step` m; s = 0 at the first joint."""

    def __init__(self, joints, up, back=0.03, step=0.0005, rounds=5):
        d0 = unit(sub(joints[1], joints[0]))
        pts = [sub(joints[0], mul(d0, back))] + [tuple(p) for p in joints]
        for _ in range(rounds):
            nxt = [pts[0]]
            for a, b in zip(pts, pts[1:]):
                nxt += [add(mul(a, 0.75), mul(b, 0.25)), add(mul(a, 0.25), mul(b, 0.75))]
            nxt.append(pts[-1])
            pts = nxt
        cum = [0.0]
        for a, b in zip(pts, pts[1:]):
            cum.append(cum[-1] + length(sub(b, a)))
        n = max(2, int(cum[-1] / step) + 1)
        out, k = [], 0
        for i in range(n + 1):
            t = cum[-1] * i / n
            while k < len(cum) - 2 and cum[k + 1] < t:
                k += 1
            f = (t - cum[k]) / max(1e-12, cum[k + 1] - cum[k])
            out.append(add(pts[k], mul(sub(pts[k + 1], pts[k]), f)))
        self.p = out
        self.ds = cum[-1] / n
        # s of the first joint along the resampled line
        self.s0 = min(range(len(out)), key=lambda i: length(sub(out[i], joints[0]))) * self.ds
        self.t = [unit(sub(out[min(i + 1, n)], out[max(i - 1, 0)])) for i in range(n + 1)]
        u = unit(sub(up, mul(self.t[0], dot(up, self.t[0]))))
        self.u = []
        for i in range(n + 1):  # parallel transport of `up`
            u = unit(sub(u, mul(self.t[i], dot(u, self.t[i]))))
            self.u.append(u)
        self.v = [cross(t, u) for t, u in zip(self.t, self.u)]
        self.end = n * self.ds - self.s0
        self.joint_s = [self.closest(j)[0] for j in joints]

    def at(self, s):
        """(point, t, u, v) at s, interpolated."""
        x = (s + self.s0) / self.ds
        i = max(0, min(len(self.p) - 2, int(math.floor(x))))
        f = min(1.0, max(0.0, x - i)) if 0 <= x <= len(self.p) - 1 else x - i
        lerp = lambda a, b: add(a, mul(sub(b, a), f))  # noqa: E731
        return lerp(self.p[i], self.p[i + 1]), self.t[i], self.u[i], self.v[i]

    def closest(self, q):
        """(s, angle, radius) of q against the axis (the nearest sample refined on its two segments)."""
        best = min(range(len(self.p)), key=lambda i: dot(sub(q, self.p[i]), sub(q, self.p[i])))
        i = best
        t = self.t[i]
        s = i * self.ds - self.s0 + dot(sub(q, self.p[i]), t)
        p, t, u, v = self.at(s)
        r = sub(q, p)
        r = sub(r, mul(t, dot(r, t)))
        return s, math.atan2(dot(r, v), dot(r, u)), length(r)


def circle_fit(pts2):
    """Kasa's algebraic circle fit: (cx, cy, r) of 2D points."""
    n = len(pts2)
    if n < 3:
        return 0.0, 0.0, 0.0
    sx = sum(p[0] for p in pts2); sy = sum(p[1] for p in pts2)  # noqa: E702
    sxx = sum(p[0] ** 2 for p in pts2); syy = sum(p[1] ** 2 for p in pts2); sxy = sum(p[0] * p[1] for p in pts2)  # noqa: E702
    sz = [p[0] ** 2 + p[1] ** 2 for p in pts2]
    szx = sum(z * p[0] for z, p in zip(sz, pts2)); szy = sum(z * p[1] for z, p in zip(sz, pts2)); szz = sum(sz)  # noqa: E702
    a = [[sxx, sxy, sx], [sxy, syy, sy], [sx, sy, n]]
    b = [szx, szy, szz]
    x = solve3(a, b)
    if x is None:
        return 0.0, 0.0, 0.0
    cx, cy = x[0] / 2, x[1] / 2
    return cx, cy, math.sqrt(max(0.0, x[2] + cx * cx + cy * cy))


def solve3(a, b):
    m = [row[:] + [bb] for row, bb in zip(a, b)]
    n = len(m)
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        if abs(m[p][c]) < 1e-18:
            return None
        m[c], m[p] = m[p], m[c]
        for r in range(n):
            if r != c:
                f = m[r][c] / m[c][c]
                m[r] = [x - f * y for x, y in zip(m[r], m[c])]
    return [m[i][n] / m[i][i] for i in range(n)]


def polyfit2(xs, ys):
    """y = c0 + c1 x + c2 x^2, least squares (a constant for fewer than 3 points)."""
    if len(xs) < 3:
        m = sum(ys) / len(ys) if ys else 0.0
        return [m, 0.0, 0.0]
    a = [[sum(x ** (i + j) for x in xs) for j in range(3)] for i in range(3)]
    b = [sum(y * x ** i for x, y in zip(xs, ys)) for i in range(3)]
    return solve3(a, b) or [sum(ys) / len(ys), 0.0, 0.0]


def wave(samples, lo, hi, sigma=0.008):
    """samples [(s, angle, r)] between lo and hi: each one's residual from its local trend, a weighted least-squares
    fit over its neighbours (Gaussian in s, sigma m) of r = c0 + c1 ds + c2 ds^2 + c3 cos a + c4 sin a + c5 cos 2a
    + c6 sin 2a (the taper, an off-centre axis and the section's ellipse are not waves); returns (the largest
    |residual| m away from the ends, the rows [(sector, [(s, r, trend)] sorted by s)])."""
    sel = [x for x in samples if lo <= x[0] <= hi]
    rows = {k: [] for k in range(SECTORS)}
    worst = 0.0
    for s, a, r in sel:
        ata = [[0.0] * 7 for _ in range(7)]
        atb = [0.0] * 7
        for t, b, q in sel:
            w = math.exp(-0.5 * ((t - s) / sigma) ** 2)
            if w < 1e-4:
                continue
            ds = (t - s) / sigma
            f = (1.0, ds, ds * ds, math.cos(b), math.sin(b), math.cos(2 * b), math.sin(2 * b))
            for i in range(7):
                atb[i] += w * f[i] * q
                for j in range(7):
                    ata[i][j] += w * f[i] * f[j]
        for i in range(7):
            ata[i][i] += 1e-9
        c = solve3(ata, atb)
        tr = r if c is None else (c[0] + c[3] * math.cos(a) + c[4] * math.sin(a) + c[5] * math.cos(2 * a)
                                  + c[6] * math.sin(2 * a))
        k = min(SECTORS - 1, int((a + math.pi) / (2 * math.pi) * SECTORS))
        rows[k].append((s, r, tr))
        if lo + sigma * 0.5 <= s <= hi - sigma * 0.5:  # the trend is biased at the ends
            worst = max(worst, abs(r - tr))
    return worst, [(k, sorted(v)) for k, v in rows.items()]


class Tube:
    """The finger's defined surface (module docstring)."""

    def __init__(self, axis: Axis, samples, root_at, root_r, taper, tip_s, ellipse_cap=0.15):
        self.ax = axis
        self.root_at, self.root_r = root_at, root_r
        self.r_end = root_r * (1 - taper)
        self.tip = tip_s
        self.s_c = tip_s - self.r_end
        # the centre's offset: circle centres of 3 mm slices between the root and the dome, a quadratic in s
        sl = {}
        for s, a, r in samples:
            if root_at <= s <= self.s_c:
                sl.setdefault(int(s / 0.003), []).append((r * math.cos(a), r * math.sin(a)))
        xs, cu, cv = [], [], []
        for k, p2 in sorted(sl.items()):
            if len(p2) >= 6:
                cx, cy, _ = circle_fit(p2)
                xs.append((k + 0.5) * 0.003)
                cu.append(cx)
                cv.append(cy)
        self.cu, self.cv = polyfit2(xs, cu), polyfit2(xs, cv)
        # the ellipse: r / mean r against cos 2t, sin 2t around the offset centre
        num_c = num_s = den_c = den_s = 0.0
        rel = []
        for s, a, r in samples:
            if root_at <= s <= self.s_c:
                ou, ov = self.offset(s)
                x, y = r * math.cos(a) - ou, r * math.sin(a) - ov
                rel.append((math.atan2(y, x), math.hypot(x, y), s))
        if rel:
            prof = {}
            for t, r, s in rel:
                prof.setdefault(int(s / 0.003), []).append(r)
            mean = {k: sum(v) / len(v) for k, v in prof.items()}
            for t, r, s in rel:
                q = r / mean[int(s / 0.003)] - 1
                num_c += q * math.cos(2 * t); den_c += math.cos(2 * t) ** 2  # noqa: E702
                num_s += q * math.sin(2 * t); den_s += math.sin(2 * t) ** 2  # noqa: E702
        ea, eb = (num_c / den_c if den_c else 0.0), (num_s / den_s if den_s else 0.0)
        m = math.hypot(ea, eb)
        if m > ellipse_cap:
            ea, eb = ea * ellipse_cap / m, eb * ellipse_cap / m
        self.ea, self.eb = ea, eb

    def offset(self, s):
        s = min(max(s, self.root_at), self.s_c)
        return (self.cu[0] + self.cu[1] * s + self.cu[2] * s * s, self.cv[0] + self.cv[1] * s + self.cv[2] * s * s)

    def e(self, t):
        return 1 + self.ea * math.cos(2 * t) + self.eb * math.sin(2 * t)

    def radius(self, s):
        """The section's mean radius at s (the dome's start s_c: r_end)."""
        if s <= self.root_at:
            return self.root_r
        return self.root_r + (self.r_end - self.root_r) * min(1.0, (s - self.root_at) / max(1e-6, self.s_c - self.root_at))

    def place(self, q):
        """q placed on the surface at its own s and angle about the offset centre (the dome: by its direction from
        the dome's centre)."""
        s, a, r = self.ax.closest(q)
        p, t, u, v = self.ax.at(min(s, self.s_c))
        ou, ov = self.offset(s)
        c = add(p, add(mul(u, ou), mul(v, ov)))
        d = sub(q, c)
        al = dot(d, t)
        perp = sub(d, mul(t, al))
        pl = length(perp)
        if pl < 1e-9:
            return add(c, mul(t, self.r_end)) if s > self.s_c else q
        pu = mul(perp, 1 / pl)
        ang = math.atan2(dot(pu, v), dot(pu, u))
        if s <= self.s_c:
            return add(c, mul(pu, self.radius(s) * self.e(ang)))
        dl = math.hypot(al, pl)  # the dome: an ellipsoid cap, round along the axis
        return add(c, add(mul(t, al / dl * self.r_end), mul(pu, pl / dl * self.r_end * self.e(ang))))

    def local(self, q):
        """(s, angle, radius) of q about the offset centre (the wave is measured there, not about the bone's axis)."""
        s, a, r = self.ax.closest(q)
        p, t, u, v = self.ax.at(min(s, self.s_c))
        ou, ov = self.offset(s)
        d = sub(q, add(p, add(mul(u, ou), mul(v, ov))))
        d = sub(d, mul(t, dot(d, t)))
        return s, math.atan2(dot(d, v), dot(d, u)), length(d)

    def profile_at(self, s, ang):
        """The defined radius from the axis (no offset) at s and angle: for the plots."""
        return self.radius(s) * self.e(ang)


def tube_finger(pos: dict, share: dict, adj: dict, joints, up, spec: dict, root_r: float, relax_rounds: int = 8):
    """One finger (or thumb) rebuilt: pos {i: rest point} of the side's vertices with any weight on the chain, share
    {i: chain weight}, adj {i: neighbours}; joints the chain's heads and the last tail; spec (m): root_at, taper, ramp.
    Returns (new positions, the tube, report)."""
    ax = Axis(joints, up)
    mine = [i for i in pos if share[i] >= 0.5]
    pr = {i: ax.closest(pos[i]) for i in pos}
    tip = max(pr[i][0] for i in mine)
    samples = [pr[i] for i in mine]
    tube = Tube(ax, samples, spec["root_at"], root_r, spec["taper"], tip)
    r0, r1 = spec["ramp"]
    k = {i: smoothstep(r0, r1, pr[i][0]) * min(1.0, share[i] / 0.6) for i in pos}
    full = {i for i in pos if k[i] >= 0.999}
    new = {i: tube.place(pos[i]) for i in pos if k[i] > 0}
    cur = dict(pos)
    cur.update(new)
    for _ in range(relax_rounds):  # even rings: the full vertices to their neighbours' centroid, back on the surface
        nxt = {}
        for i in full:
            nb = [cur[j] for j in adj.get(i, ()) if j in cur]
            if len(nb) < 3:
                continue
            c = mul(tuple(map(sum, zip(*nb))), 1.0 / len(nb))
            nxt[i] = tube.place(add(mul(cur[i], 0.5), mul(c, 0.5)))
        cur.update(nxt)
    for i in new:
        if i in full:
            new[i] = cur[i]
        else:
            new[i] = add(pos[i], mul(sub(new[i], pos[i]), k[i]))
    hi = tube.s_c - 0.002
    before = wave([tube.local(pos[i]) for i in mine], spec["root_at"], hi)[0]
    after = wave([tube.local(new.get(i, pos[i])) for i in mine], spec["root_at"], hi)[0]
    after_full = wave([tube.local(new[i]) for i in mine if i in full], spec["root_at"], hi)[0]
    worst = max((length(sub(new[i], pos[i])) for i in new), default=0.0)
    rep = {"verts": len(new), "full": len(full), "root_mm": round(root_r * 2000, 1), "end_mm": round(tube.r_end * 2000, 1),
           "tip_s_mm": round(tip * 1000, 1), "ellipse": [round(tube.ea, 3), round(tube.eb, 3)],
           "wave_before_mm": round(before * 1000, 2), "wave_after_mm": round(after * 1000, 2),
           "wave_after_full_mm": round(after_full * 1000, 2), "partial": sorted(round(k[i], 2) for i in mine if i not in full)[:6],
           "largest_move_mm": round(worst * 1000, 2)}
    return new, tube, rep


def joint_weights(s, joint_s, bones, r, blend):
    """The chain weights at s: each joint's (joint_s[1:-1]) step from one bone to the next over +-blend*r."""
    out = []
    for j in range(len(bones)):  # the share of bone j: entered at its joint, left at the next
        a = 1.0 if j == 0 else smoothstep(joint_s[j] - blend * r, joint_s[j] + blend * r, s)
        b = smoothstep(joint_s[j + 1] - blend * r, joint_s[j + 1] + blend * r, s) if j + 1 < len(bones) else 0.0
        out.append(max(0.0, a - b))
    t = sum(out)
    return {bn: x / t for bn, x in zip(bones, out) if x > 1e-4}
