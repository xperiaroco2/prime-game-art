"""The hull as built (art #263 rebuild B, docs/ship.md "The hull"): variant J of the blockouts (ship_hull_shape.py),
the engineer's pick, in the night build's plated, faceted brushed silver (PR #267's skin; no scratches, no decals, no
light strips). The HULL lane owns this file.

Every outer face of J (the convex hull's facets after the mouth cut, ship_hull_shape.surface) is cut into plates in its
own plane: rows PLATE[1] wide along the facet's span direction (plan x projected into the facet; the mouth's sides use
plan y), each row cut every PLATE[0], the rows staggered by half a plate like brickwork, so every seam lies on the
facet and the facets' edges are seams too. A plate is ship_hull._plate (v1's: its face inset INSET at the surface,
chamfered down to its outline sunk DEPTH), its silver drawn from the v1 sets by a hash of its centre; under the plates a
dark under-skin DEPTH * 1.8 inside closes the seams. Three pieces, all in the plan frame at the origin: skin_top (the
faces looking up or sideways), skin_belly (the faces looking down), skin_mouth (the recess's back, sides and ceiling).
Flat shaded: the facets stay crisp."""

from __future__ import annotations

import math

import ship_hull as H
import ship_hull_shape as S
import ship_lib as L

PLATE = (1.8, 1.3)            # a plate's length along the facet's span direction and its row's width (metres)
INSET, DEPTH = 0.022, 0.014   # v1's seam: the chamfer's inset at the surface and its depth
SLIVER = 0.03                 # a cut plate's least inradius-like width (2 area / perimeter) to be a plate at all
MATS = {"top": H.SILVERS, "belly": ("ext_silver_c", "ext_silver_c", "leg_metal"), "mouth": ("hull_dark",)}


def _basis(n):
    """Two unit axes in the plane of normal n: e1 plan x projected into it (plan y where the face looks along x)."""
    a = S.X if abs(n[0]) < 0.9 else S.Y
    e1 = S._unit3(S._sub(a, tuple(n[k] * S._dot(a, n) for k in range(3))))
    return e1, S._cross(n, e1)


def _clean(poly):
    out = []
    for p in poly:
        if not out or math.dist(p, out[-1]) > 1e-4:
            out.append(p)
    if len(out) > 1 and math.dist(out[0], out[-1]) <= 1e-4:
        out.pop()
    return out


def plates(poly, n, size=PLATE):
    """A convex face cut into its plates (convex polygons wound as the face)."""
    e1, e2 = _basis(n)
    us, vs = [S._dot(p, e1) for p in poly], [S._dot(p, e2) for p in poly]
    out = []
    for j in range(math.floor(min(vs) / size[1]), math.floor(max(vs) / size[1]) + 1):
        row = S.clip(S.clip(poly, S._neg(e2), -j * size[1]), e2, (j + 1) * size[1])
        if len(row) < 3:
            continue
        off = 0.5 * size[0] * (j % 2)
        for i in range(math.floor((min(us) - off) / size[0]), math.floor((max(us) - off) / size[0]) + 1):
            q = _clean(S.clip(S.clip(row, S._neg(e1), -(off + i * size[0])), e1, off + (i + 1) * size[0]))
            if len(q) >= 3 and 2 * S.area(q) / sum(math.dist(a, b) for a, b in zip(q, q[1:] + q[:1])) > SLIVER:
                out.append(q)   # a sliver thinner than SLIVER stays open: the dark under-skin shows, a wider seam
    return out


def j_skin(args: dict, layout: dict) -> list:
    """One part of the hull J (args part: top, belly or mouth): its plates by material and the dark under-skin."""
    kind = args["part"]
    mats = MATS[kind]
    groups: dict = {}
    under = []
    for poly, n, k in S.surface(S.DEFAULT):
        if k != kind:
            continue
        for q in plates(poly, n):
            c = [sum(x[i] for x in q) / len(q) for i in range(3)]
            mat = mats[int(H._hash(round(c[0], 1), round(c[1], 1), round(c[2], 1)) * len(mats)) % len(mats)]
            groups.setdefault(mat, []).append(H._plate(q, INSET, DEPTH))
        under.append(([H._add(x, n, -DEPTH * 1.8) for x in poly], [tuple(range(len(poly)))]))
    parts = [L.part(f"skin_{kind}_{mat}", *L.merge(*g), mat, solid=False) for mat, g in sorted(groups.items())]
    parts.append(L.part(f"skin_{kind}_seam", *L.merge(*under), "ext_seam", solid=False))
    return parts


j_skin = H._outward(j_skin)


def j_cheeks(args: dict, layout: dict) -> list:
    """rebuild C: the mouth's cheeks, the throat walls' outer faces where J's belly rises over the deck (under the nose,
    forward of the hall): plates in the walls' outer planes from the slab's bottom up to the belly, so the throat
    reads as a mouth cut into the nose and no wall stands bare under it."""
    (mx, my), (kx, ky) = S.TH_PTS[1], S.TH_PTS[2]
    ln = math.hypot(kx - mx, ky - my)
    d = ((kx - mx) / ln, (ky - my) / ln)
    groups: dict = {}
    for sx in (1, -1):
        n = (sx * d[1], -d[0], 0.0)                     # outward
        pts = []
        for i in range(25):
            s = ln * i / 24
            x, y = sx * (mx + d[0] * s) + n[0] * S.WALL, my + d[1] * s + n[1] * S.WALL
            hb = S.heights(x, y)
            if hb and hb[1] > S.SLAB + 0.01:
                pts.append((x, y, hb[1]))
        for (x0, y0, b0), (x1, y1, b1) in zip(pts, pts[1:]):
            q = [(x0, y0, S.SLAB - 0.01), (x1, y1, S.SLAB - 0.01), (x1, y1, b1), (x0, y0, b0)]
            if S._dot(S._newell(q), n) < 0:
                q.reverse()
            for p in plates(q, n):
                groups.setdefault("ext_silver_c", []).append(H._plate(p, INSET, DEPTH))
    return [L.part(f"cheeks_{mat}", *L.merge(*g), mat, solid=False) for mat, g in sorted(groups.items())]


j_cheeks = H._outward(j_cheeks)
