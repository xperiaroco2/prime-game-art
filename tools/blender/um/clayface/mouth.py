"""The clay face kit's mouths: the rolled lip outline and its states (rest, closed, a, e, o), the teeth, and the
mouth's extent and lip top that the nose and the moustache are seated against.
"""
import math

from .kit import FLOOR, LIP_H, LIP_W, MOUTHS, MOUTH_K, MOUTH_N, PROFILE, STATES, TAPER, TOOTH_SEG, TUCK
from .mesh import add_keys, data_object


def outline(M, st):
    """The cavity outline of a mouth state: half width w and the top / bottom curves z(u), u in [-1, 1]."""
    w = M["w"] * st.get("w", 1.0) * MOUTH_K
    gap = st["gap"] * MOUTH_K
    smile = (M.get("smile", 0.0) + st.get("smile", 0.0)) * MOUTH_K
    skew = (M.get("skew", 0.0) + st.get("skew", 0.0)) * MOUTH_K
    side = M.get("side_smile", 0.0) * st.get("side_k", 1.0) * MOUTH_K
    ts = st.get("top_share", M["top_share"])
    p = st.get("pow", M["pow"])
    top_h, bot_h = gap * ts, gap * (1.0 - ts)

    def base(u):
        return smile * u * u + skew * u + side * max(u, 0.0) ** 2

    def top(u):
        return base(u) + top_h * max(0.0, 1.0 - u * u) ** p

    def bot(u):
        return base(u) - bot_h * max(0.0, 1.0 - u * u) ** p

    return w, top, bot


def lipk(M, st):
    return M.get("lipk", 1.0) * st.get("lipk", 1.0)


def ring2d(M, st, mx, mz):
    """The outline points (u, x, z), their outward 2D normals and the centroid."""
    w, top, bot = outline(M, st)
    n = MOUTH_N
    us = [-math.cos(math.pi * k / n) for k in range(n + 1)]
    pts = [(u, mx + w * u, mz + top(u)) for u in us] + [(u, mx + w * u, mz + bot(u)) for u in reversed(us[1:-1])]
    N = len(pts)
    cx = sum(p[1] for p in pts) / N
    cz = sum(p[2] for p in pts) / N
    nrm = []
    for i in range(N):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % N]
        ns = []
        for p0, p1 in ((a, b), (b, c)):
            dx, dz = p1[1] - p0[1], p1[2] - p0[2]
            ln = math.hypot(dx, dz) or 1.0
            ns.append((-dz / ln, dx / ln))
        vx, vz = ns[0][0] + ns[1][0], ns[0][1] + ns[1][1]
        ln = math.hypot(vx, vz) or 1.0
        nrm.append((vx / ln, vz / ln))
    # orient outward (away from the centroid)
    if sum((p[1] - cx) * n_[0] + (p[2] - cz) * n_[1] for p, n_ in zip(pts, nrm)) < 0:
        nrm = [(-a, -b) for a, b in nrm]
    return pts, nrm, (cx, cz), (w, top, bot)


def lip_dims(M, st, u):
    k = lipk(M, st)
    return LIP_W * k * MOUTH_K * (1.0 - TAPER * abs(u) ** 4), LIP_H * k * MOUTH_K * (1.0 - TUCK * abs(u) ** 6)


def outer2d(M, st, mx, mz):
    """The lip's outer edge in the face plane: [(x, z)] (for the clearance rules)."""
    pts, nrm, _, _ = ring2d(M, st, mx, mz)
    out = []
    for (u, x, z), (nx, nz) in zip(pts, nrm):
        lw, _ = lip_dims(M, st, u)
        out.append((x + nx * lw, z + nz * lw))
    return out


def mouth_geo(ctx, M, st):
    """One mouth state: verts (world), faces, material index per face (0 lip, 1 cavity). Same topology for every
    state of every mouth."""
    pts, nrm, (cx, cz), (w, top, bot) = ring2d(M, st, ctx.mx, ctx.mz)
    N = len(pts)
    verts = []
    rings = []
    for ofs, lift in PROFILE:
        row = []
        for (u, x, z), (nx, nz) in zip(pts, nrm):
            lw, lh = lip_dims(M, st, u)
            d = ofs * lw
            if d < 0:
                d = max(d, -0.3 * max(0.0, top(u) - bot(u)))
            row.append(len(verts))
            verts.append(ctx.on(x + nx * d, z + nz * d, lift * lh))
        rings.append(row)
    for k_in, lift in ((0.18, 0.22 * LIP_H), (0.58, FLOOR + 0.0004)):  # the cavity wall and its floor (two rings, so
        row = []                                                       # the flat floor never dips under the skin)
        for (u, x, z) in pts:
            row.append(len(verts))
            verts.append(ctx.on(x + (cx - x) * k_in, z + (cz - z) * k_in, lift))
        rings.append(row)
    centre = len(verts)
    verts.append(ctx.on(cx, cz, FLOOR))
    faces, fm = [], []
    for k in range(len(rings) - 1):
        for i in range(N):
            j = (i + 1) % N
            faces.append((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]))
            fm.append(0 if k < len(PROFILE) - 1 else 1)
    last = rings[-1]
    for i in range(N):
        faces.append((last[i], last[(i + 1) % N], centre))
        fm.append(1)
    return verts, faces, fm


def _superellipse(k, n=TOOTH_SEG, e=4.0):
    t = 2 * math.pi * k / n + math.pi / n
    c, s = math.cos(t), math.sin(t)
    return math.copysign(abs(c) ** (2.0 / e), c), math.copysign(abs(s) ** (2.0 / e), s)


def tooth_faces(base):
    n = TOOTH_SEG
    fp, fr, mr, bp = base, base + 1, base + 1 + n, base + 1 + 2 * n
    faces = []
    for k in range(n):
        j = (k + 1) % n
        faces.append((fp, fr + j, fr + k))
        faces.append((fr + k, fr + j, mr + j, mr + k))
        faces.append((mr + k, mr + j, bp))
    return faces


def tooth_geo(ctx, M, st, spec):
    """One tooth in one state: 2 + 2 TOOTH_SEG verts, a rounded box (superellipse outline) hanging from the top lip
    (row top), standing on the bottom lip (row bot) or two buck teeth over the lower lip (row buck). When the state
    hides teeth or the opening is too small at the tooth, it collapses to a point behind the cavity floor."""
    w, top, bot = outline(M, st)
    mx, mz = ctx.mx, ctx.mz
    x0, x1 = mx + spec["u"][0] * M["w"] * MOUTH_K, mx + spec["u"][1] * M["w"] * MOUTH_K
    row, h = spec["row"], spec["h"] * MOUTH_K
    k = lipk(M, st)
    show = spec.get("always") or st.get("teeth", True)

    def span(x):
        u = max(-1.0, min(1.0, (x - mx) / w))
        if row == "top":
            zt = top(u) + 0.0015
            zb = max(top(u) - h, bot(u) + 0.0006)
        elif row == "bot":
            zb = bot(u) - 0.0015
            zt = min(bot(u) + h, top(u) - 0.0006)
        else:
            zt = top(u) + 0.0015
            zb = top(0.0) - h
        return mz + zb, mz + zt, u

    if show:
        for x in (x0, (x0 + x1) / 2, x1):
            zb, zt, u = span(x)
            if zt - zb < 0.0034 + (0.0015 if row != "buck" else 0.0) or abs((x - mx) / w) > 0.97:
                show = False
                break
    if not show:
        zb, zt, u = span((x0 + x1) / 2)
        p = ctx.on((x0 + x1) / 2, (zb + zt) / 2, 0.0)
        return [p.copy() for _ in range(2 + 2 * TOOTH_SEG)], False
    if row == "buck":
        back, front = LIP_H * 0.2, LIP_H * k + 0.0016
    else:
        back, front = LIP_H * 0.12, LIP_H * 0.55

    def pt(s, t, lift):
        x = x0 + (x1 - x0) * (s + 1) / 2
        zb, zt, _ = span(x)
        return ctx.on(x, zb + (zt - zb) * (t + 1) / 2, lift)

    vs = [pt(0.0, 0.0, front + 0.0005)]
    vs += [pt(*[c * 0.72 for c in _superellipse(i)], front) for i in range(TOOTH_SEG)]
    vs += [pt(*_superellipse(i), (front + back) / 2 + (front - back) * 0.15) for i in range(TOOTH_SEG)]
    vs.append(pt(0.0, 0.0, back))
    return vs, True


def mouth_extent(ctx, M, half_x=None):
    """Highest and lowest z of the mouth's lip (every state); with half_x only within +-half_x of the centre line."""
    hi, lo = -math.inf, math.inf
    for st in M["states"].values():
        for x, z in outer2d(M, st, ctx.mx, ctx.mz):
            if half_x is None or abs(x - ctx.mx) <= half_x:
                hi, lo = max(hi, z), min(lo, z)
    for spec in M.get("teeth", []):
        if spec["row"] == "buck":
            lo = min(lo, ctx.mz + outline(M, M["states"]["rest"])[1](0.0) - spec["h"])
    return hi, lo


def lip_top_at(ctx, M, x):
    """The lip's highest z over every state at world x (None outside every state's lip)."""
    best = None
    for st in M["states"].values():
        pts = outer2d(M, st, ctx.mx, ctx.mz)
        n = MOUTH_N + 1
        topc = pts[:n]
        for (xa, za), (xb, zb) in zip(topc, topc[1:]):
            lo_, hi_ = min(xa, xb), max(xa, xb)
            if lo_ - 1e-9 <= x <= hi_ + 1e-9:
                t = 0.0 if hi_ - lo_ < 1e-9 else (x - xa) / (xb - xa)
                z = za + (zb - za) * t
                best = z if best is None else max(best, z)
    return best


def build_mouth(face, ctx, coll):
    h, picks, m = face.h, face.picks, face.mats
    M = MOUTHS[picks["mouth"]]
    geo = {s: mouth_geo(ctx, M, M["states"][s]) for s in STATES}
    faces, fm = geo["rest"][1], geo["rest"][2]
    o = data_object(f"{h.id}_fb_mouth", geo["rest"][0], faces, fm, [m["lip"], m["cavity"]], coll)
    add_keys(o, {f"mouth_{s}": geo[s][0] for s in STATES if s != "rest"}, None)
    face.add("mouth", o, "mouth")
    teeth_on = picks.get("teeth", True) or any(t.get("always") for t in M.get("teeth", []))
    face.meta["teeth_shown"] = {}
    if teeth_on and M.get("teeth"):
        tv = {s: [] for s in STATES}
        tf = []
        for spec in M["teeth"]:
            base = len(tv["rest"])
            for s in STATES:
                vs, shown = tooth_geo(ctx, M, M["states"][s], spec)
                tv[s] += vs
                face.meta["teeth_shown"].setdefault(s, 0)
                face.meta["teeth_shown"][s] += int(shown)
                rows = face.meta.setdefault("teeth_rows_shown", {}).setdefault(s, {})
                rows[spec["row"]] = rows.get(spec["row"], 0) + int(shown)
            tf += tooth_faces(base)
        t = data_object(f"{h.id}_fb_teeth", tv["rest"], tf, [0] * len(tf), [m["teeth"]], coll)
        add_keys(t, {f"mouth_{s}": tv[s] for s in STATES if s != "rest"}, None)
        face.add("teeth", t, "teeth")
    return M
