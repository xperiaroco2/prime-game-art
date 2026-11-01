"""The run fist's smooth union of the digits (art #196, Hands H1l, H1q; numpy, no bpy: alien_fist_shape.py is the
Blender side).

`Envelope`: a signed distance field in the run grip's posed space. Each digit is a plain union of round cones fitted
to its own tube; the fingers are smooth-unioned with each other over `k`, optionally with a core (each finger's chord
cone and the palm as a rounded box) over `k_core`, and the thumb last over `k_thumb`. `iso_mesh` meshes a field
(marching tetrahedra) to view it alone or to test on. `contact` (H1q, the shipped route): the morph's corrective on a
hand the bones already curled into the fist: only the gaps and valleys between touching digits go out onto the union,
the contact zones sink, the moves capped and smoothed as a field. (H1l's shrink-wrap onto a whole-fist envelope and
its "press" mode, and H1r's local index-thumb zone, were tried and dropped: art #196, H1u.)
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


class Envelope:
    """The fist's envelope. digits {name: [(centre, radius), ...]} stations root to tip dome (metres, posed space);
    thumb: the thumb's name in digits; palm: None or (centre, axes 3x3, half extents, rounding).

    The fingers smooth-unioned over k, the core (each finger's chord cone at `core` of the stations' radius, and the
    palm) over k_core, the thumb over k_thumb: one closed solid."""

    def __init__(self, digits: dict, thumb: str, palm=None, k: float = 0.01, k_core: float = 0.012,
                 k_thumb: float = 0.008, core: float = 0.9):
        self.chains = {n: [(st[i][0], st[i + 1][0], st[i][1], st[i + 1][1]) for i in range(len(st) - 1)]
                       for n, st in digits.items()}
        self.fingers = [n for n in digits if n != thumb]
        self.thumb = thumb if thumb in digits else None
        self.chords = {n: (digits[n][0][0], digits[n][-1][0], digits[n][0][1] * core,
                           digits[n][-1][1] * core) for n in self.fingers} if core > 0 else {}
        self.palm = palm
        self.k, self.k_core, self.k_thumb = k, k_core, k_thumb
        self.names = list(digits)

    def digit(self, name: str, P: np.ndarray) -> np.ndarray:
        return np.minimum.reduce([round_cone(P, *c) for c in self.chains[name]])

    def sd(self, P: np.ndarray) -> np.ndarray:
        P = np.atleast_2d(np.asarray(P, float))
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

    def grad(self, P: np.ndarray) -> np.ndarray:
        P = np.atleast_2d(np.asarray(P, float))
        g = np.empty_like(P)
        for i in range(3):
            e = np.zeros(3)
            e[i] = EPS_GRAD
            g[:, i] = (self.sd(P + e) - self.sd(P - e)) / (2 * EPS_GRAD)
        return g

    def normal(self, P: np.ndarray) -> np.ndarray:
        g = self.grad(P)
        return g / np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-12)

    def project(self, P: np.ndarray, steps: int = 8) -> np.ndarray:
        """P moved along the field's gradient onto its zero level (Newton steps, each at most 5 mm)."""
        P = np.array(P, float)
        for _ in range(steps):
            d = self.sd(P)
            if np.abs(d).max() < 1e-7:
                break
            g = self.grad(P)
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
    M = M * (cap * np.tanh(raw / cap) / np.maximum(raw, 1e-12))[:, None]
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
            c = Y[T].mean(axis=1)
            ref = env.normal(c)
            return big & (np.einsum("ij,ij->i", m, ref) < 0)
        st.update({"tris": int(len(T)), "folded": int(against(X).sum()), "folded_bones": int(against(P).sum()),
                   "flipped": int((np.einsum("ij,ij->i", nrm(X), nrm(P)) < 0).sum())})
    return X, st
