"""M2m: the plain maths of clothes_bibmove (testable without Blender): mesh components, the bib and the
strap vertices over it, the best-fit rigid motion of the bib, the straps' slip on it. numpy (Blender has it) is
imported lazily: components and concept_ratio are plain Python, so the runner's tests check them without it."""
from __future__ import annotations


def components(n: int, polys: list[list[int]]) -> list[int]:
    """Each vertex's connected component (union-find over the faces): n labels 0..k-1, by first appearance."""
    parent = list(range(n))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for p in polys:
        r = find(p[0])
        for k in p[1:]:
            s = find(k)
            if s != r:
                parent[s] = r
    ids: dict[int, int] = {}
    return [ids.setdefault(find(i), len(ids)) for i in range(n)]


def bib_and_straps(co: "np.ndarray", main: "np.ndarray", hw: float, z_lo: float) -> tuple["np.ndarray", "np.ndarray"]:
    """The bib: the main garment piece's vertices in front (y < 0), within hw of the middle, over z_lo. The strap
    and buckle candidates: the other pieces' front vertices within hw + 3 cm, over z_lo, up to the bib's top + 5 mm
    (the caller keeps those near a bib face)."""
    import numpy as np
    front = (co[:, 1] < 0) & (co[:, 2] > z_lo)
    bib = np.nonzero(main & front & (np.abs(co[:, 0]) <= hw))[0]
    if not len(bib):
        return bib, bib
    top = co[bib, 2].max()
    on = np.nonzero(~main & front & (np.abs(co[:, 0]) <= hw + 0.03) & (co[:, 2] <= top + 0.005))[0]
    return bib, on


def rigid_fit(a: "np.ndarray", b: "np.ndarray") -> tuple["np.ndarray", "np.ndarray", "np.ndarray"]:
    """The rotation r and translation t moving points a onto b best (Kabsch, least squares) and each point's residual
    distance |r a + t - b|."""
    import numpy as np
    ca, cb = a.mean(0), b.mean(0)
    h = (a - ca).T @ (b - cb)
    u, _s, vt = np.linalg.svd(h)
    d = np.sign(np.linalg.det(vt.T @ u.T))
    r = vt.T @ np.diag([1.0, 1.0, d]) @ u.T
    t = cb - r @ ca
    res = np.linalg.norm(a @ r.T + t - b, axis=1)
    return r, t, res


def slip(co0: "np.ndarray", co: "np.ndarray", pairs, r: "np.ndarray") -> float:
    """The largest slide of a strap vertex on the bib: pairs are (strap vertex, bib face's vertex ids, barycentric
    weights) tied at rest; its offset from the tied point now, turned back by the bib's best-fit rotation r, less its
    rest offset (m)."""
    import numpy as np
    most = 0.0
    for i, ids, w in pairs:
        p0 = sum(wk * co0[k] for k, wk in zip(ids, w))
        p1 = sum(wk * co[k] for k, wk in zip(ids, w))
        d = r.T @ (co[i] - p1) - (co0[i] - p0)
        most = max(most, float(np.linalg.norm(d)))
    return most


def concept_ratio(bib_top: float, shoulder: float, band: float) -> float:
    """The bib top's height as a share of the band-to-shoulder span (0 at the waistband's line, 1 at the shoulders'
    top): the measure taken on the concept's front view and on the build alike."""
    return (bib_top - band) / (shoulder - band)
