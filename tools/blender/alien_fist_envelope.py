"""The run fist by a smooth envelope (art #196, Hands H1l; numpy, no bpy: alien_fist_shape.py is the Blender side).

H1j and H1k moved each finger vertex to the nearest point of the fingers' smooth union. Inside the merge the facing
sides of two fingers had nowhere visible to go: 300-570 vertices per hand folded under the surface and creased it.
This route builds the fist's whole outer surface first and then spreads the hand's skin over it:

1. The envelope: a signed distance field in the loose grip's posed space. Each digit is a plain union of round cones
   fitted to its own tube (as H1j); the fingers are smooth-unioned with each other over `k` (the finger grooves'
   softness); a core (each finger's chord from its root to its tip dome, and the palm as a rounded box) fills the
   curl's hole and is smooth-unioned in over `k_core`; the thumb, optionally moved across the front (`thumb_shift`,
   in the hand's frame), is smooth-unioned last over `k_thumb`. `iso_mesh` meshes it (marching tetrahedra) to view
   it alone.
2. `wrap`: every finger vertex is projected onto the envelope from where it is (the shrink-wrap), then relaxed along
   the envelope: an umbrella step taken in the tangent plane and re-projected, a few hundred rounds, the region's
   rim pinned (the vertices outside it stay where the grip put them; vertices fading into the palm carry part of the
   move). The uniform umbrella spreads the bunched facing sides over the surface, so no vertex hides or folds.
3. `metrics`: triangles whose normal disagrees with the envelope's (folded), the shortest edge against the median,
   the largest distance of a vertex from the envelope (bumps).
"""
from __future__ import annotations

import numpy as np

EPS_GRAD = 1e-4  # metres: the central-difference step of the field's gradient


def round_cone(P: np.ndarray, a, b, r1: float, r2: float) -> np.ndarray:
    """The exact signed distance from points P (N, 3) to the round cone from the sphere (a, r1) to the sphere
    (b, r2); a degenerate one (|r1 - r2| >= |b - a|) is the union of its two spheres."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    ba = b - a
    l2 = float(ba @ ba)
    rr = r1 - r2
    pa = P - a
    if l2 <= rr * rr + 1e-18:
        return np.minimum(np.linalg.norm(pa, axis=1) - r1, np.linalg.norm(P - b, axis=1) - r2)
    a2 = l2 - rr * rr
    il2 = 1.0 / l2
    y = pa @ ba
    z = y - l2
    q = pa * l2 - np.outer(y, ba)
    x2 = np.einsum("ij,ij->i", q, q)
    y2 = y * y * l2
    z2 = z * z * l2
    k = (1.0 if rr >= 0 else -1.0) * rr * rr * x2
    out = (np.sqrt(np.maximum(x2 * a2 * il2, 0.0)) + y * rr) * il2 - r1
    c2 = np.where(y >= 0, 1.0, -1.0) * a2 * y2 < k
    out = np.where(c2, np.sqrt(x2 + y2) * il2 - r1, out)
    c1 = np.where(z >= 0, 1.0, -1.0) * a2 * z2 > k
    return np.where(c1, np.sqrt(x2 + z2) * il2 - r2, out)


def smin(a: np.ndarray, b: np.ndarray, k: float) -> np.ndarray:
    """The polynomial smooth minimum over a blend width k (k <= 0: the plain minimum)."""
    if k <= 0:
        return np.minimum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - h * h * k * 0.25


def rounded_box(P: np.ndarray, centre, axes, half, r: float) -> np.ndarray:
    """A box (centre, rows of `axes` its unit axes, `half` its half extents) with its edges rounded by r (the
    rounding is inside the half extents)."""
    loc = (P - np.asarray(centre, float)) @ np.asarray(axes, float).T
    q = np.abs(loc) - (np.asarray(half, float) - r)
    return np.linalg.norm(np.maximum(q, 0.0), axis=1) + np.minimum(q.max(axis=1), 0.0) - r


def smax(a: np.ndarray, b: np.ndarray, k: float) -> np.ndarray:
    """The polynomial smooth maximum over k."""
    return -smin(-a, -b, k)


class Envelope:
    """The fist's envelope. digits {name: [(centre, radius), ...]} stations root to tip dome (metres, posed space);
    thumb: the thumb's name in digits; palm: None or (centre, axes 3x3, half extents, rounding).

    mode "merge" (the brief's smooth union): the fingers smooth-unioned over k, the core (each finger's chord cone at
    `core` of the stations' radius, and the palm) over k_core, the thumb over k_thumb: one closed solid.
    mode "press": every digit stays its own solid, inflated by `inflate` (a share of its radii) with its own chord
    core smooth-unioned over k_core (its curl filled), then clipped against each other digit at their bisector less
    half the `gap`, and against the palm by the gap, the clip's lip rounded over `lip`: the fingers pressed together
    with a thin slit between them. Each digit's skin then maps onto its own solid and need not fold; on a merged
    solid the facing sides of two fingers must fold (in each cross-section a closed loop cannot cover an arc once)."""

    def __init__(self, digits: dict, thumb: str, palm=None, k: float = 0.01, k_core: float = 0.012,
                 k_thumb: float = 0.008, core: float = 0.9, mode: str = "merge", inflate: float = 1.0,
                 gap: float = 0.0004, lip: float = 0.003):
        if mode not in ("merge", "press"):
            raise ValueError(f"envelope mode {mode!r}")
        sc = inflate if mode == "press" else 1.0
        self.chains = {n: [(st[i][0], st[i + 1][0], st[i][1] * sc, st[i + 1][1] * sc) for i in range(len(st) - 1)]
                       for n, st in digits.items()}
        self.fingers = [n for n in digits if n != thumb]
        self.thumb = thumb if thumb in digits else None
        self.chords = {n: (digits[n][0][0], digits[n][-1][0], digits[n][0][1] * core * sc,
                           digits[n][-1][1] * core * sc) for n in self.fingers} if core > 0 else {}
        self.palm = palm
        self.k, self.k_core, self.k_thumb = k, k_core, k_thumb
        self.mode, self.gap, self.lip = mode, gap, lip
        self.names = list(digits)

    def digit(self, name: str, P: np.ndarray) -> np.ndarray:
        return np.minimum.reduce([round_cone(P, *c) for c in self.chains[name]])

    def parts(self, P: np.ndarray) -> dict:
        """press: {digit: its clipped field}."""
        P = np.atleast_2d(np.asarray(P, float))
        f = {}
        for n in self.names:
            x = self.digit(n, P)
            if n in self.chords:
                x = smin(x, round_cone(P, *self.chords[n]), self.k_core)
            f[n] = x
        palm = rounded_box(P, *self.palm) if self.palm is not None else None
        out = {}
        for n in self.names:
            others = [f[m] for m in self.names if m != n]
            c = f[n]
            if others:
                c = smax(c, (f[n] - np.minimum.reduce(others)) * 0.5 + self.gap * 0.5, self.lip)
            if palm is not None and n != self.thumb:  # the thumb lies across the fingers, its root in the palm
                c = smax(c, self.gap - palm, self.lip)
            out[n] = c
        return out

    def sd(self, P: np.ndarray, owner: np.ndarray | None = None) -> np.ndarray:
        """The field; press with owner (N,) indices into self.names: each point's own digit's field."""
        P = np.atleast_2d(np.asarray(P, float))
        if self.mode == "press":
            parts = self.parts(P)
            d = np.minimum.reduce(list(parts.values()))
            if owner is not None:
                for k, n in enumerate(self.names):
                    m = owner == k
                    d[m] = parts[n][m]
            return d
        d = None
        for n in self.fingers:
            x = self.digit(n, P)
            d = x if d is None else smin(d, x, self.k)
        core = [round_cone(P, *c) for c in self.chords.values()]
        if self.palm is not None:
            core.append(rounded_box(P, *self.palm))
        if core:
            c = np.minimum.reduce(core)
            d = c if d is None else smin(d, c, self.k_core)
        if self.thumb is not None:
            x = self.digit(self.thumb, P)
            d = x if d is None else smin(d, x, self.k_thumb)
        return d

    def grad(self, P: np.ndarray, owner: np.ndarray | None = None) -> np.ndarray:
        P = np.atleast_2d(np.asarray(P, float))
        g = np.empty_like(P)
        for i in range(3):
            e = np.zeros(3)
            e[i] = EPS_GRAD
            g[:, i] = (self.sd(P + e, owner) - self.sd(P - e, owner)) / (2 * EPS_GRAD)
        return g

    def normal(self, P: np.ndarray, owner: np.ndarray | None = None) -> np.ndarray:
        g = self.grad(P, owner)
        return g / np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-12)

    def project(self, P: np.ndarray, steps: int = 8, owner: np.ndarray | None = None) -> np.ndarray:
        """P moved along the field's gradient onto its zero level (Newton steps, each at most 5 mm)."""
        P = np.array(P, float)
        for _ in range(steps):
            d = self.sd(P, owner)
            if np.abs(d).max() < 1e-7:
                break
            g = self.grad(P, owner)
            gg = np.maximum(np.einsum("ij,ij->i", g, g), 1e-12)
            step = g * (d / gg)[:, None]
            n = np.linalg.norm(step, axis=1, keepdims=True)
            P -= step * np.minimum(1.0, 0.005 / np.maximum(n, 1e-12))
        return P


# the Kuhn split of a cube into six tetrahedra around its diagonal 0-6 (consistent across neighbouring cubes)
_CORNERS = np.array([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)])
_TETS = ((0, 5, 1, 6), (0, 1, 2, 6), (0, 2, 3, 6), (0, 3, 7, 6), (0, 7, 4, 6), (0, 4, 5, 6))


def iso_mesh(sd, lo, hi, h: float, chunk: int = 200000) -> tuple[np.ndarray, np.ndarray]:
    """The zero level of the field sd (a function of (N, 3) points) inside the box lo..hi on a grid of step h, by
    marching tetrahedra: welded vertices (V, 3) and triangles (T, 3), each facing up the field's gradient (out)."""
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    n = np.maximum(np.ceil((hi - lo) / h).astype(int) + 1, 2)
    axes = [lo[i] + h * np.arange(n[i]) for i in range(3)]
    G = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 3)
    F = np.concatenate([sd(G[i:i + chunk]) for i in range(0, len(G), chunk)])
    F = np.where(F == 0.0, 1e-12, F)
    gid = np.arange(len(G)).reshape(n)
    cubes = [gid[c[0]:n[0] - 1 + c[0], c[1]:n[1] - 1 + c[1], c[2]:n[2] - 1 + c[2]].ravel() for c in _CORNERS]
    keys, tris = [], []
    lone_rest = ((1, 2, 3), (0, 2, 3), (0, 1, 3), (0, 1, 2))
    for t in _TETS:
        idx = np.stack([cubes[c] for c in t], axis=1)
        inside = F[idx] < 0
        cnt = inside.sum(axis=1)
        idx = idx[(cnt > 0) & (cnt < 4)]
        inside = inside[(cnt > 0) & (cnt < 4)]
        cnt = inside.sum(axis=1)
        for want in (1, 3):
            sel = cnt == want
            if not sel.any():
                continue
            lone = np.argmax(inside[sel] if want == 1 else ~inside[sel], axis=1)
            rest = np.array(lone_rest)[lone]
            L = idx[sel][np.arange(sel.sum()), lone]
            e = [np.stack([L, idx[sel][np.arange(sel.sum()), rest[:, j]]], axis=1) for j in range(3)]
            keys.append(np.stack(e, axis=1))
        sel = cnt == 2
        if sel.any():
            ins = inside[sel]
            order = np.argsort(~ins, axis=1, kind="stable")  # the two inside corners first
            ii = idx[sel][np.arange(sel.sum())[:, None], order]
            a, b, c, d = ii[:, 0], ii[:, 1], ii[:, 2], ii[:, 3]
            ac, ad, bd, bc = (np.stack(p, axis=1) for p in ((a, c), (a, d), (b, d), (b, c)))
            keys.append(np.stack([ac, ad, bd], axis=1))
            keys.append(np.stack([ac, bd, bc], axis=1))
    E = np.concatenate(keys)  # (T, 3, 2) grid-vertex pairs
    E = np.sort(E, axis=2)
    flat = E[:, :, 0].astype(np.int64) * len(G) + E[:, :, 1]
    uniq, inv = np.unique(flat.ravel(), return_inverse=True)
    i0, i1 = uniq // len(G), uniq % len(G)
    t = F[i0] / (F[i0] - F[i1])
    V = G[i0] + (G[i1] - G[i0]) * t[:, None]
    T = inv.reshape(-1, 3)
    T = T[(T[:, 0] != T[:, 1]) & (T[:, 1] != T[:, 2]) & (T[:, 0] != T[:, 2])]
    nrm = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])  # slivers kept: the mesh stays closed
    cen = V[T].mean(axis=1)
    g = np.stack([(sd(cen + e) - sd(cen - e)) for e in np.eye(3) * EPS_GRAD], axis=1)
    flip = np.einsum("ij,ij->i", nrm, g) < 0
    T[flip] = T[flip][:, ::-1]
    return V, T


def edges_of(tris: np.ndarray) -> np.ndarray:
    """The unique undirected edges (E, 2) of triangles (T, 3)."""
    e = np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]])
    return np.unique(np.sort(e, axis=1), axis=0)


def _folded(env: Envelope, X: np.ndarray, T: np.ndarray, owner: np.ndarray | None) -> np.ndarray:
    """(T,) bool: the triangle's normal against the envelope's at its centre (its first vertex's digit); slivers of
    no area are not counted."""
    a, b, c = X[T[:, 0]], X[T[:, 1]], X[T[:, 2]]
    n = np.cross(b - a, c - a)
    ot = None if owner is None else np.asarray(owner)[T[:, 0]]
    big = np.linalg.norm(n, axis=1) > 2e-12  # over 1e-6 mm^2: a degenerate sliver has no side to fold to
    return big & (np.einsum("ij,ij->i", n, env.normal((a + b + c) / 3, ot)) < 0)


def wrap(env: Envelope, P: np.ndarray, weight: np.ndarray, edges: np.ndarray, rounds: int = 300, lam: float = 0.5,
         start: np.ndarray | None = None, owner: np.ndarray | None = None,
         tris: np.ndarray | None = None) -> tuple[np.ndarray, dict]:
    """The hand's skin shrink-wrapped onto the envelope and relaxed along it. P (N, 3) the posed vertices of the hand
    (the region and its rim); weight (N,) 0..1 how far each follows the envelope (0: pinned, the rim; between: fading
    into the palm); edges (E, 2) the mesh's edges among them; start: P moved first (the thumb's shift), else P;
    owner (N,): each vertex's digit (press: it follows its own digit's solid); tris (T, 3): the fold guard's.

    The relax is a spring step towards each edge's posed length, taken in the envelope's tangent plane and
    re-projected: squeezed vertices spread, stretched ones gather, and the skin keeps its triangles' shapes (a uniform
    umbrella instead slides a pinned tube's skin towards its rim and folds it). A step that would turn a triangle over
    against the envelope is undone for that triangle's vertices (the guard), so the relax never adds a fold.
    Returns (the final positions (N, 3), stats)."""
    P = np.asarray(P, float)
    w = np.asarray(weight, float)
    free = w > 0
    S = P if start is None else np.asarray(start, float)
    X = S.copy()
    own = None if owner is None else np.asarray(owner)[free]
    X[free] = env.project(S[free], 12, own)
    deg = np.bincount(edges.ravel(), minlength=len(P)).astype(float)
    i, j = edges[:, 0], edges[:, 1]
    L0 = np.linalg.norm(P[j] - P[i], axis=1)
    T = None
    if tris is not None:
        T = np.asarray(tris)[free[np.asarray(tris)].any(axis=1)]
    undone = 0
    for _ in range(rounds):
        E = P + (X - P) * w[:, None]
        dv = E[j] - E[i]
        dl = np.maximum(np.linalg.norm(dv, axis=1), 1e-12)
        f = dv * ((dl - L0) / dl)[:, None] * 0.5
        acc = np.zeros_like(P)
        np.add.at(acc, i, f)
        np.add.at(acc, j, -f)
        d = (acc / np.maximum(deg, 1)[:, None])[free]
        nrm = env.normal(X[free], own)
        d -= nrm * np.einsum("ij,ij->i", d, nrm)[:, None]
        Xn = X.copy()
        Xn[free] = env.project(X[free] + lam * d, 3, own)
        if T is not None:
            was = _folded(env, P + (X - P) * w[:, None], T, owner)
            for _ in range(20):  # undoing a vertex can turn over a neighbouring triangle: until none
                bad = _folded(env, P + (Xn - P) * w[:, None], T, owner) & ~was
                if not bad.any():
                    break
                back = np.unique(T[bad])
                Xn[back] = X[back]
                undone += int(bad.sum())
        X = Xn
    out = P + (X - P) * w[:, None]
    full = w >= 0.999
    keep = np.linalg.norm(out[j] - out[i], axis=1) / np.maximum(L0, 1e-12)
    return out, {"verts": int(free.sum()), "full": int(full.sum()), "guard_undone": undone,
                 "max_move_mm": round(float(np.linalg.norm(out - P, axis=1).max()) * 1000, 2),
                 "edge_keep_min": round(float(keep[(w[i] > 0) | (w[j] > 0)].min()), 3),
                 "off_surface_mm": round(float(np.abs(env.sd(out[full], None if owner is None else
                                                             np.asarray(owner)[full])).max()) * 1000, 4)
                 if full.any() else 0.0}


def metrics(env: Envelope, X: np.ndarray, tris: np.ndarray, full: np.ndarray,
            owner: np.ndarray | None = None) -> dict:
    """On the triangles whose three vertices fully follow the envelope (full (N,) bool): folded (the triangle's
    normal against the envelope's at its centre), the shortest edge over the median, the largest distance of a
    vertex from the envelope (bumps) and of a triangle's centre (the facets' sag). press with owner: a triangle is
    measured on its first vertex's digit."""
    T = tris[full[tris].all(axis=1)]
    if not len(T):
        return {"tris": 0, "folded": 0, "min_edge_ratio": 0.0, "bump_mm": 0.0, "sag_mm": 0.0}
    a, b, c = X[T[:, 0]], X[T[:, 1]], X[T[:, 2]]
    n = np.cross(b - a, c - a)
    cen = (a + b + c) / 3
    ot = None if owner is None else np.asarray(owner)[T[:, 0]]
    folded = int(_folded(env, X, T, owner).sum())
    el = np.linalg.norm(X[edges_of(T)[:, 0]] - X[edges_of(T)[:, 1]], axis=1)
    vs = np.unique(T)
    return {"tris": int(len(T)), "folded": folded, "min_edge_ratio": round(float(el.min() / np.median(el)), 3),
            "edge_p1_ratio": round(float(np.percentile(el, 1) / np.median(el)), 3),
            "bump_mm": round(float(np.abs(env.sd(X[vs], None if owner is None else np.asarray(owner)[vs])).max()) * 1000, 4),
            "sag_mm": round(float(np.abs(env.sd(cen, ot)).max()) * 1000, 3)}


def contact(env: Envelope, P: np.ndarray, weight: np.ndarray, owner: np.ndarray, edges: np.ndarray,
            tris: np.ndarray | None = None, cap: float = 0.009, bury: float = 0.0005, hide: float = 0.003,
            smooth: int = 12, lam: float = 0.5) -> tuple[np.ndarray, dict]:
    """H1q: the run fist's small corrective on a hand the bones already curled into a fist; its only job is
    tube-against-tube contact. P (N, 3) the bone-curled vertices (the region and its rim); weight (N,) 0..1 (0: the
    pinned rim); owner (N,) each vertex's digit, an index into env.names; env a "merge" envelope of the fitted digits
    (smooth-unioned over env.k, the thumb over env.k_thumb; no palm, no chords); edges (E, 2), tris (T, 3) among P.

    - The contact zones sink: a vertex inside a neighbouring digit by more than `bury` (the finger sides that touch,
      a curled finger on another) or deeper than `hide` inside the union (a bent joint's inner crease) keeps its
      posed place inside the volume; it is never projected onto an outer shell.
    - Every other vertex inside the union (a side gap between neighbouring fingers, the valley between two knuckles,
      a knuckle top the skinning flattened) goes out onto it along the union's gradient.
    - The moves are capped (each move's length to cap * tanh(length / cap)) and smoothed as a field: `smooth`
      Laplacian rounds of step `lam` on the moves themselves, not on the positions, the rim held at zero, so no
      neighbour pair differs sharply; then faded by the weight.

    Returns (X (N, 3), stats): folded counts the triangles of full weight outside the contact zones whose normal
    is against the union's (the bones alone: folded_bones), flipped those the corrective turned over against
    their bone-curled normal."""
    P = np.asarray(P, float)
    w = np.asarray(weight, float)
    owner = np.asarray(owner)
    n = len(P)
    free = w > 0
    D = np.stack([env.digit(m, P) for m in env.names], axis=1)
    Do = D.copy()
    Do[np.arange(n), owner] = np.inf
    near = Do.min(axis=1) if D.shape[1] > 1 else np.full(n, np.inf)
    U = env.sd(P)
    buried = (near < -bury) | (U < -hide)
    go = free & ~buried & (U < 0)
    M = np.zeros_like(P)
    if go.any():
        M[go] = env.project(P[go], 12) - P[go]
    raw = np.linalg.norm(M, axis=1)
    M *= (cap * np.tanh(raw / cap) / np.maximum(raw, 1e-12))[:, None]
    i, j = edges[:, 0], edges[:, 1]
    deg = np.maximum(np.bincount(edges.ravel(), minlength=n), 1).astype(float)
    for _ in range(smooth):
        acc = np.zeros_like(M)
        np.add.at(acc, i, M[j])
        np.add.at(acc, j, M[i])
        M = np.where(free[:, None], M + lam * (acc / deg[:, None] - M), 0.0)
    X = P + M * w[:, None]
    mv = np.linalg.norm(X - P, axis=1)
    st = {"verts": int(free.sum()), "moved": int((mv > 1e-6).sum()), "buried": int((free & buried).sum()),
          "raw_max_mm": round(float(raw.max()) * 1000, 2) if n else 0.0,
          "max_move_mm": round(float(mv.max()) * 1000, 2) if n else 0.0,
          "step_max_mm": round(float(np.linalg.norm((X - P)[j] - (X - P)[i], axis=1).max()) * 1000, 3)
          if len(edges) else 0.0}
    if tris is not None:
        T = np.asarray(tris)
        T = T[(w[T] >= 0.999).all(axis=1) & ~buried[T].any(axis=1)]

        def nrm(Y):
            return np.cross(Y[T[:, 1]] - Y[T[:, 0]], Y[T[:, 2]] - Y[T[:, 0]])

        def against(Y):
            m = nrm(Y)
            big = np.linalg.norm(m, axis=1) > 2e-12
            return big & (np.einsum("ij,ij->i", m, env.normal(Y[T].mean(axis=1))) < 0)
        st.update({"tris": int(len(T)), "folded": int(against(X).sum()), "folded_bones": int(against(P).sum()),
                   "flipped": int((np.einsum("ij,ij->i", nrm(X), nrm(P)) < 0).sum())})
    return X, st
