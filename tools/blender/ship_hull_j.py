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


CHEEK_OUT = S.WALL + 0.03   # rebuild D: the cheeks 3 cm proud of the wall modules' backs (in their plane they z-fought:
#                             the modules' pale backs showed through as boards beside the mouth)


def j_cheeks(args: dict, layout: dict) -> list:
    """rebuild C: the mouth's cheeks, the throat walls' outer faces where J's belly rises over the deck (under the nose,
    forward of the hall): plates in the walls' outer planes from the slab's bottom up to the belly, so the throat
    reads as a mouth cut into the nose and no wall stands bare under it. rebuild D: in the mouth's dark plates
    (MATS["mouth"], skin_mouth's), so with the notch's cut faces above them each side reads as one dark face up to
    the nose's sloped top (the pale silver read as a board standing beside the mouth)."""
    (mx, my), (kx, ky) = S.TH_PTS[1], S.TH_PTS[2]
    ln = math.hypot(kx - mx, ky - my)
    d = ((kx - mx) / ln, (ky - my) / ln)
    groups: dict = {}
    for sx in (1, -1):
        n = (sx * d[1], -d[0], 0.0)                     # outward
        pts = []
        for i in range(25):
            s = ln * i / 24
            x, y = sx * (mx + d[0] * s) + n[0] * CHEEK_OUT, my + d[1] * s + n[1] * CHEEK_OUT
            hb = S.heights(x, y)
            if hb and hb[1] > S.SLAB + 0.01:
                pts.append((x, y, hb[1]))
        for (x0, y0, b0), (x1, y1, b1) in zip(pts, pts[1:]):
            q = [(x0, y0, S.SLAB - 0.01), (x1, y1, S.SLAB - 0.01), (x1, y1, b1), (x0, y0, b0)]
            if S._dot(S._newell(q), n) < 0:
                q.reverse()
            for p in plates(q, n):
                groups.setdefault(MATS["mouth"][0], []).append(H._plate(p, INSET, DEPTH))
    # rebuild E: the jambs. Forward of the roof line the throat's walls stood as pale interior modules with flat tops
    # at 2.05 m, free under the open notch (the "cheeks" of the D shots). Here each wall is the hull's own side of the
    # cut instead: a solid in the wall's thickness from the slab up to J's top over it (one convex face, as every
    # section of the convex hull), its inner face in the hull's plates, its top and front edge in hull_silver
    s_roof = (S.TH_ROOF_Y - my) / d[1]
    edge = []
    for sx in (1, -1):
        n = (sx * d[1], -d[0], 0.0)                     # outward
        inner, outer = [], []
        for i in range(17):
            s = 0.02 + (s_roof - 0.02) * i / 16   # 2 cm in from the nose edge (heights() is None on it)
            x, y = sx * (mx + d[0] * s), my + d[1] * s
            xo, yo = x + n[0] * (S.WALL - 0.01), max(y + n[1] * (S.WALL - 0.01), my + 0.02)   # not past the nose edge
            inner.append((x, y, S.heights(x, y)[0]))
            outer.append((xo, yo, S.heights(xo, yo)[0]))
        face = [(inner[0][0], inner[0][1], S.SLAB - 0.01), (inner[-1][0], inner[-1][1], S.SLAB - 0.01)]
        face += [inner[k] for k in range(len(inner) - 1, -1, -1)]
        inward = S._neg(n)
        if S._dot(S._newell(face), inward) < 0:
            face.reverse()
        for p in plates(face, inward):
            c = [sum(x[i] for x in p) / len(p) for i in range(3)]
            mat = MATS["top"][int(H._hash(round(c[0], 1), round(c[1], 1), round(c[2], 1)) * len(MATS["top"])) %
                              len(MATS["top"])]
            groups.setdefault(mat, []).append(H._plate(p, INSET, DEPTH))
        for (a0, b0), (a1, b1) in zip(zip(inner, outer), zip(inner[1:], outer[1:])):   # the top, along the slope
            q = [a0, a1, b1, b0]
            edge.append((q, [(0, 1, 2, 3) if S._dot(S._newell(q), S.H) > 0 else (3, 2, 1, 0)]))
        q = [(inner[0][0], inner[0][1], S.SLAB - 0.01), (outer[0][0], outer[0][1], S.SLAB - 0.01), outer[0], inner[0]]
        edge.append((q, [(0, 1, 2, 3) if S._dot(S._newell(q), (0.0, -1.0, 0.0)) > 0 else (3, 2, 1, 0)]))   # front
    parts = [L.part(f"cheeks_{mat}", *L.merge(*g), mat, solid=False) for mat, g in sorted(groups.items())]
    parts.append(L.part("jamb_edge", *L.merge(*edge), "hull_silver", solid=False))
    parts.append(L.part("jamb_cap", *L.merge(*jamb_caps()), MATS["mouth"][0], solid=False))
    return parts


CAP_BACK = 0.01   # rebuild F: the jamb's aft cap this far aft of the roof line, behind the arch's face and the lintel


def jamb_caps() -> list:
    """rebuild F: the hole at the mouth's upper corners. The notch (cutters) is cut WALL beyond the throat's walls up
    to J's top; at the roof line its back face (the lintel) closes it only above TH_TOP, and the throat's covered part
    behind closes only its own profile (walls vertical to the chamfer, the chamfer in to the ceiling). Between that
    profile's chamfer and the notch's side, under the lintel, the hull's hollow stood open: sky and pines through its
    one-sided skin. Each side's cap closes it in the plane CAP_BACK aft of the roof line, from the slab up past
    TH_TOP (under the lintel) and from the walls' inner face out past the notch's side (into the hull's hollow); its
    inner edge follows the throat's inner profile, so the arch (its face on the roof line) hides the seam. Both
    windings: no light through it either way. [(verts, faces)] in plan coordinates."""
    (mx, my), (kx, ky) = S.TH_PTS[1], S.TH_PTS[2]
    ln = math.hypot(kx - mx, ky - my)
    d = ((kx - mx) / ln, (ky - my) / ln)
    k = 1.0 / d[1]                                       # an across distance as a plan x offset at fixed y
    y = S.TH_ROOF_Y + CAP_BACK
    xi = mx + d[0] * (y - my) / d[1]                     # the walls' inner face
    xo = xi + S.WALL * k + 0.02                          # past the notch's side plane
    ch_h, ch_in = S.TH_CH
    h_ch, h_ceil, h_top = S.FLOOR + ch_h, S.FLOOR + S.TH["clear_h"], S.TH_TOP + 0.03
    x_ceil = xi - ch_in * k
    out = []
    for sx in (1, -1):
        for poly in ([(xi, S.SLAB - 0.01), (xo, S.SLAB - 0.01), (xo, h_ch), (xi, h_ch)],
                     [(xi, h_ch), (xo, h_ch), (xo, h_top), (x_ceil, h_top), (x_ceil, h_ceil)]):
            q = [(sx * x, y, h) for x, h in poly]
            n = len(q)
            out.append((q, [tuple(range(n))]))
            out.append(([(a, b + 0.002, c) for a, b, c in q], [tuple(range(n - 1, -1, -1))]))   # the back, 2 mm aft
    return out


j_cheeks = H._outward(j_cheeks)
