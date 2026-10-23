"""The hull's plating (art #263 rebuild B, docs/ship.md "The hull"): the live hull of ship_hull_shape.py (DEFAULT: P
since lens step 2, the union of convex parts with its window band and roof windows cut; J before it; the module keeps
its name, its builders j_skin and j_cheeks plate whichever is live), in the night build's plated, faceted brushed silver (PR #267's skin; no scratches, no decals, no
light strips). The HULL lane owns this file.

Every outer face of the hull (its facets after the mouth cut and the openings, ship_hull_shape.surface) is cut into plates in its
own plane: rows PLATE[1] wide along the facet's span direction (plan x projected into the facet; the mouth's sides use
plan y), each row cut every PLATE[0], the rows staggered by half a plate like brickwork, so every seam lies on the
facet and the facets' edges are seams too. A plate is ship_hull._plate (v1's: its face inset INSET at the surface,
chamfered down to its outline sunk DEPTH), its silver drawn from the v1 silvers by a hash of its centre, the top and
the belly alike; a cut plate thinner than SLIVER is laid flush (no inset), so it closes its strip and only its
neighbours' chamfers draw the seam. Under the plates a dark under-skin DEPTH * 1.8 inside closes the seams. Three pieces, all in the plan frame at the origin: skin_top (the
faces looking up or sideways), skin_belly (the faces looking down), skin_mouth (the recess's back, sides and ceiling).
Flat shaded: the facets stay crisp. Lens step 3: the skin's plates follow one seam family per zone across the facets
(the block before j_skin) and the lens is shaded smooth; `plates` and `lay` (per facet) are left to the cheeks."""

from __future__ import annotations

import math
import zlib

import ship_hull as H
import ship_hull_shape as S
import ship_lib as L

PLATE = (1.8, 1.3)            # a plate's length along the facet's span direction and its row's width (metres)
INSET, DEPTH = 0.022, 0.014   # v1's seam: the chamfer's inset at the surface and its depth
SLIVER = 0.03                 # a cut plate's inradius-like width (2 area / perimeter) under which it is laid flush
TINY = 1e-6                   # a cut piece's area (m2) under which it is no piece at all (a clipping crumb)
# the outside in v1's silvers only, the belly as the top: the belly's every third plate was leg_metal once, and those
# dark plates read as holes and camouflage patches in the side view (the engineer, 2026-10-22)
MATS = {"top": H.SILVERS, "belly": H.SILVERS, "mouth": ("hull_dark",)}


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


def width(q) -> float:
    """A convex polygon's inradius-like width, 2 area / perimeter."""
    return 2 * S.area(q) / sum(math.dist(a, b) for a, b in zip(q, q[1:] + q[:1]))


def lay(q) -> tuple:
    """One plate: v1's inset and chamfer, or flush (no inset) where it is a sliver, too thin for the inset."""
    return H._plate(q, INSET if width(q) > SLIVER else 0.0, DEPTH)


def plates(poly, n, size=PLATE):
    """A convex face cut into its plates (convex polygons wound as the face), every piece of it covered."""
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
            if len(q) >= 3 and S.area(q) > TINY:
                out.append(q)   # slivers too: left open, the dark under-skin showed through as black streaks
    return out


# --- lens polish (step 3): the plates laid in rows across the facets ------------------------------------------------
# Step 2 plated every facet in its own frame, so the union's sliver facets fanned their seams out and the lens's 48 rim
# facets read as slats (a corrugated tank). Now every face belongs to a zone with one seam family: global planes whose
# rows run span-wise over the body and the fins (plan), horizontal bands and radial seams round each lens (its rim and
# its under faces), a ring of sectors round rows on its top and bottom discs. A plate is a cell of its family, cut out
# of every facet it covers: a piece's edge is a seam (inset) where a seam plane cut it, where the face ends (an opening,
# a cut) or where its neighbour bends away by more than the zone's CREASE; across a shallower facet edge it is laid
# flush, so the seams follow the rows, never a sliver. The lens's plates are shaded smooth up to CREASE["lens"] (wide
# curved plates); the body and the fins stay faceted.
CREASE = {"plan": 20.0, "lens": 30.0}   # degrees: a facet edge bending less than this is no seam in its zone
LENS_BANDS = (1.35, 2.8)                # the rim's horizontal seams: under the edge light, the window band's head
LENS_SECTOR = 36.0                      # the rim's vertical seams every this many degrees, staggered by half per band
LENS_RING = 1.5                         # the discs' inner ten-gon's apothem: rows inside it, a ring of sectors outside
LENS_R = S.P_RIM_R / math.cos(math.pi / S.P_LENS_N) + 0.02   # a face within this of a lens's centre is the lens's


def _lens_of(poly) -> int:
    for sx in (1, -1):
        if all(math.hypot(p[0] - sx * S.P_TIP[0], p[1] - S.P_TIP[1]) <= LENS_R for p in poly):
            return sx
    return 0


def _rows(poly, r, c, size=PLATE, r0=0.0, c0=0.0):
    """A convex face cut by a global plane family: rows between the planes r . p = r0 + j W, each cut by the planes
    c . p = c0 + off_j + i L (off_j half a plate on odd rows, brickwork). [((j, i), piece)]."""
    out = []
    rs = [S._dot(p, r) - r0 for p in poly]
    for j in range(math.floor(min(rs) / size[1]), math.floor(max(rs) / size[1]) + 1):
        row = S.clip(S.clip(poly, S._neg(r), -(r0 + j * size[1])), r, r0 + (j + 1) * size[1])
        if len(row) < 3:
            continue
        off = c0 + 0.5 * size[0] * (j % 2)
        cs = [S._dot(p, c) - off for p in row]
        for i in range(math.floor(min(cs) / size[0]), math.floor(max(cs) / size[0]) + 1):
            q = _clean(S.clip(S.clip(row, S._neg(c), -(off + i * size[0])), c, off + (i + 1) * size[0]))
            if len(q) >= 3 and S.area(q) > TINY:
                out.append(((j, i), q))
    return out


def _wedge(poly, centre, g0, g1):
    """The part of a face between the vertical half-planes at plan angles g0 < g1 (radians) round centre."""
    for n in ((math.sin(g0), -math.cos(g0), 0.0), (-math.sin(g1), math.cos(g1), 0.0)):
        poly = S.clip(poly, n, n[0] * centre[0] + n[1] * centre[1])
        if len(poly) < 3:
            return []
    return _clean(poly)


def _sectors(poly, centre, a0, step):
    """[(k, piece)]: a face cut into the sectors a0 + k step .. a0 + (k + 1) step (degrees) round centre."""
    gm = math.degrees(math.atan2(sum(p[1] for p in poly) / len(poly) - centre[1],
                                 sum(p[0] for p in poly) / len(poly) - centre[0]))
    gs = [math.degrees(math.atan2(p[1] - centre[1], p[0] - centre[0])) for p in poly]
    gs = [gm + (g - gm + 180.0) % 360.0 - 180.0 for g in gs]   # unwrapped about the face's own angle
    out = []
    for k in range(math.floor((min(gs) - a0) / step), math.floor((max(gs) - a0) / step) + 1):
        q = _wedge(poly, centre, math.radians(a0 + k * step), math.radians(a0 + (k + 1) * step))
        if len(q) >= 3 and S.area(q) > TINY:
            out.append((k % round(360 / step), q))
    return out


def _lens_cells(poly, n):
    """An east lens face's plates [(cell, piece)]: the rim and the under faces in three bands with radial seams every
    LENS_SECTOR, staggered per band; the discs (and the band's sill and head) in a ring of sectors round rows."""
    c = S.P_TIP
    ax = S.p_axis_deg()
    out = []
    if abs(n[2]) < 0.75:
        hs = (-10.0, *LENS_BANDS, 10.0)
        for b, (h0, h1) in enumerate(zip(hs, hs[1:])):
            band = _clean(S.clip(S.clip(poly, S._neg(S.H), -h0), S.H, h1))
            if len(band) < 3 or S.area(band) <= TINY:
                continue
            out += [(("rim", b, k), q) for k, q in _sectors(band, c, ax + 0.5 * LENS_SECTOR * (b % 2), LENS_SECTOR)]
        return out
    lid = "top" if n[2] > 0 else "bot"
    inner = poly
    for k, q in _sectors(poly, c, ax, LENS_SECTOR):
        gm = math.radians(ax + (k + 0.5) * LENS_SECTOR)
        m = (math.cos(gm), math.sin(gm), 0.0)
        d = LENS_RING + m[0] * c[0] + m[1] * c[1]
        q = _clean(S.clip(q, S._neg(m), -d))   # the ring: beyond the ten-gon's edge
        if len(q) >= 3 and S.area(q) > TINY:
            out.append(((lid, "ring", k), q))
        if len(inner) >= 3:
            inner = S.clip(inner, m, d)
    inner = _clean(inner)
    if len(inner) >= 3 and S.area(inner) > TINY:
        a = math.radians(ax)
        u, v = (math.cos(a), math.sin(a), 0.0), (-math.sin(a), math.cos(a), 0.0)
        cc = (c[0], c[1], 0.0)
        out += [((lid, j, i), q) for (j, i), q in _rows(inner, v, u, r0=S._dot(cc, v) - 0.5 * PLATE[1],
                                                         c0=S._dot(cc, u) - 0.5 * PLATE[0])]
    return out


def _plan_cells(poly, n):
    """Rows span-wise (seams along plan x, between planes of constant y; a face looking fore or aft: horizontal
    bands), the plates' ends on planes of constant x (a face looking sideways: constant h)."""
    r = S.Y if abs(n[1]) < 0.7 else S.H
    c = S.X if abs(n[0]) < 0.7 else (S.H if r == S.Y else S.Y)
    return [((r, c, j, i), q) for (j, i), q in _rows(poly, r, c)]


def _mirror(poly):
    return [(-p[0], p[1], p[2]) for p in reversed(poly)]


def cells(poly, n):
    """A face's plates in its zone: [(cell key, piece)], the key shared by the pieces of one plate on other facets.
    The west lens is the east's mirror image."""
    sx = _lens_of(poly)
    if sx == 0 or S.p_fair_face(poly, n):   # details 3b: the fairings are plated flat, like the fins
        return [(("plan",) + key, q) for key, q in _plan_cells(poly, n)]
    if sx > 0:
        return [(("lens", 1) + key, q) for key, q in _lens_cells(poly, n)]
    return [(("lens", -1) + key, _mirror(q)) for key, q in _lens_cells(_mirror(poly), (-n[0], n[1], n[2]))]


def _off_segment(p, a, b) -> float:
    ab = S._sub(b, a)
    l2 = S._dot(ab, ab)
    t = 0.0 if l2 < 1e-12 else max(0.0, min(1.0, S._dot(S._sub(p, a), ab) / l2))
    return math.dist(p, tuple(a[k] + ab[k] * t for k in range(3)))


class Edges:
    """The surface's face edges in a grid: which faces meet a point on an edge, and at what angle."""
    CELL = 0.5

    def __init__(self, surf):
        self.normals = [S._unit3(n) for _p, n, _k in surf]
        self.grid: dict = {}
        for i, (poly, _n, _k) in enumerate(surf):
            for a, b in zip(poly, poly[1:] + poly[:1]):
                steps = max(1, math.ceil(math.dist(a, b) / (0.5 * self.CELL)))
                for key in {self._key([a[k] + (b[k] - a[k]) * t / steps for k in range(3)]) for t in range(steps + 1)}:
                    self.grid.setdefault(key, []).append((i, a, b))

    def _key(self, p):
        return tuple(math.floor(p[k] / self.CELL) for k in range(3))

    def bend(self, i, m):
        """(m lies on face i's own outline, the largest angle in degrees to another face meeting it there or None)."""
        own, best, seen = False, None, set()
        kx, ky, kz = self._key(m)
        for key in ((kx + a, ky + b, kz + c) for a in (-1, 0, 1) for b in (-1, 0, 1) for c in (-1, 0, 1)):
            for j, a, b in self.grid.get(key, ()):
                if (j, a, b) in seen or _off_segment(m, a, b) > 2e-4:
                    continue
                seen.add((j, a, b))
                if j == i:
                    own = True
                    continue
                ang = math.degrees(math.acos(max(-1.0, min(1.0, S._dot(self.normals[i], self.normals[j])))))
                best = ang if best is None else max(best, ang)
        return own, best

    def normals_at(self, p) -> list:
        """The distinct normals (over 1 degree apart) of the faces whose outline holds point p."""
        out, kx, ky, kz = [], *self._key(p)
        for key in ((kx + a, ky + b, kz + c) for a in (-1, 0, 1) for b in (-1, 0, 1) for c in (-1, 0, 1)):
            for j, a, b in self.grid.get(key, ()):
                if _off_segment(p, a, b) <= 2e-4 and all(S._dot(self.normals[j], m) < MITER_SAME for m in out):
                    out.append(self.normals[j])
        return out


MITER_SAME = math.cos(math.radians(1.0))
MITER_MAX = 2.0   # a miter at most this long (a 120 degree fold); sharper folds keep the capped miter


def miter(normals, own) -> tuple:
    """fix 2 (art #263, items 4 and 6): the direction a point on a fold sinks along: the faces' mean normal a (of the
    distinct normals meeting there), scaled so the face's own plane sinks by exactly 1 (m . own = 1). Every face at
    the point sinks along the one line a, so their sunk outlines and under-skins meet on the fold (for two faces m
    is the exact miter, m . n = 1 for both); each face sinking along its own normal parted them on a valley fold,
    and the seam's groove opened a slot to the hull's inside (the dark lines and slivers by the lens rooms). Capped
    at MITER_MAX long (folds sharper than 120 degrees). At a corner of three faces the exact point under all three."""
    ns = [own] + [n for n in normals if S._dot(n, own) < MITER_SAME]
    if len(ns) == 1:
        return own
    if len(ns) == 3:   # a corner of three faces: the point under all three planes by 1, where it is not too far
        a, b, c = ns
        bc, ca, ab = S._cross(b, c), S._cross(c, a), S._cross(a, b)
        det = S._dot(a, bc)
        if abs(det) > 1e-3:
            m = tuple((bc[t] + ca[t] + ab[t]) / det for t in range(3))
            if S._dot(m, m) <= MITER_MAX ** 2:
                return m
    a = S._unit3(tuple(sum(n[t] for n in ns) for t in range(3)))
    return tuple(a[t] / max(S._dot(a, own), 1.0 / MITER_MAX) for t in range(3))


def seams(q, i, edges, zone) -> list:
    """Per edge of piece q (of surface face i): True where it is a seam (inset), False where it is laid flush."""
    out = []
    for a, b in zip(q, q[1:] + q[:1]):
        own, bend = edges.bend(i, tuple(0.5 * (a[k] + b[k]) for k in range(3)))
        out.append((not own) or bend is None or bend > CREASE[zone])
    return out


CORNER_CAP = 0.3  # a plate corner moves at most CORNER_CAP * the shorter of its two edges (lay_seams)
SEAM_CAP = 0.6    # details 3d: a sliding seam corner moves at most SEAM_CAP of its seam edge along it (_slide_cap)
SLIDE_MAX = 3.0   # details 3c: a seam corner slides at most SLIDE_MAX * INSET along its flush edge (a needle or a
                  # near-straight corner, sin under 1 / SLIDE_MAX)


def _corner(q, flags, j):
    """Corner j of piece q where a seam meets a flush edge: (the slide's direction along the flush edge, the slide
    that keeps the groove INSET wide: INSET / sin of the corner's angle, up to SLIDE_MAX * INSET); else None."""
    k = len(q)
    a, b, c = q[j - 1], q[j], q[(j + 1) % k]
    if flags[j - 1] == flags[j]:
        return None
    d1, d2 = S._unit3(S._sub(b, a)), S._unit3(S._sub(c, b))
    x = S._cross(d1, d2)
    sin = math.sqrt(S._dot(x, x))
    way = d2 if flags[j - 1] else tuple(-t for t in d1)
    return way, INSET / max(sin, 1.0 / SLIDE_MAX)


def _slide_cap(q, flags, j) -> float:
    """details 3d: how far seam corner j of piece q may slide along its flush edge: CORNER_CAP of that edge, and its
    part along the seam (s * |cos|) at most SEAM_CAP of the seam edge, so with the seam's other corner (CORNER_CAP
    at most) the plate neither runs past its edges nor folds over. (Capping by CORNER_CAP of the shorter edge
    pinched the groove of 186 corners of 25 to 155 deg in groups with a short member; the flush edge alone folded a
    piece over.)"""
    k = len(q)
    a, b, c = q[j - 1], q[j], q[(j + 1) % k]
    (s0, s1), (f0, f1) = ((a, b), (b, c)) if flags[j - 1] else ((b, c), (a, b))
    cos = abs(S._dot(S._unit3(S._sub(s1, s0)), S._unit3(S._sub(f1, f0))))
    return min(CORNER_CAP * math.dist(f0, f1), SEAM_CAP * math.dist(s0, s1) / max(cos, 1e-9))


def corner_slides(pieces) -> list:
    """details 3c: per piece {corner index: slide} for its seam corners on a flush edge. The corners at one point
    sliding one way (the pieces on both sides of a facet fold, along the fold) share one slide, the largest one wanted
    (each keeps its groove at least INSET wide: 3b's slide of INSET whatever the angle tapered an acute corner's groove
    to INSET * sin), so they end at one point and leave no wedge. Details 3d: one cap per group, the smallest of
    its members' _slide_cap, so no member stops short of the others (3c's lay_seams capped each piece on its own at
    0.3 of its shorter edge: 450 groups ended over 0.1 mm apart, up to 6.5 cm, the black wedges at seam corners)."""
    groups: dict = {}
    caps: dict = {}
    at = []
    for idx, (_k, _z, _c, _i, q, flags) in enumerate(pieces):
        fl = flags if width(q) > SLIVER else [False] * len(q)
        for j in range(len(q)):
            cr = _corner(q, fl, j)
            if cr:
                key = (tuple(round(t, 4) for t in q[j]), tuple(round(t, 2) for t in cr[0]))
                groups.setdefault(key, []).append(cr[1])
                cap = _slide_cap(q, fl, j)
                caps[key] = min(caps.get(key, cap), cap)
                at.append((idx, j, key))
    slide = {key: min(max(g), caps[key]) for key, g in groups.items()}
    out = [{} for _ in pieces]
    for idx, j, key in at:
        out[idx][j] = slide[key]
    return out


def lay_seams(q, flags, slides=None, miters=None):
    """One plate piece: v1's inset and chamfer on its seam edges only; a flush edge keeps its outline and has no
    chamfer (the plate goes on over the next facet). A sliver is laid flush all round. slides: {corner: how far a
    seam corner slides along its flush edge} (corner_slides; else INSET). miters: per corner the sink's direction
    (skin_miters; else the face's normal)."""
    if width(q) <= SLIVER:
        flags = [False] * len(q)
    n = S._unit3(S._newell(q))
    k = len(q)
    top = []
    for i in range(k):
        a, b, c = q[i - 1], q[i], q[(i + 1) % k]
        o1, o2 = (INSET if flags[i - 1] else 0.0), (INSET if flags[i] else 0.0)
        if not o1 and not o2:
            top.append(tuple(b))
            continue
        d1, d2 = S._unit3(S._sub(b, a)), S._unit3(S._sub(c, b))
        m1, m2 = S._cross(n, d1), S._cross(n, d2)   # the edges' inward normals in the face
        den = S._dot(d1, m2)
        s = (slides or {}).get(i, INSET)
        if o1 and not o2:   # details 3b: a seam ending on a flush edge slides along it, the pieces on either side of a
            x = tuple(d2[t] * s for t in range(3))   # fold by one slide to one point (3b: INSET; per facet INSET / sin
        elif o2 and not o1:  # left black wedges past the groove); 3c: corner_slides keeps the groove's width
            x = tuple(-d1[t] * s for t in range(3))
        elif abs(den) < 1e-6:
            x = tuple(m1[t] * max(o1, o2) for t in range(3))
        else:
            beta = (o2 - o1 * S._dot(m1, m2)) / den
            x = tuple(m1[t] * o1 + d1[t] * beta for t in range(3))
        cap = CORNER_CAP * min(math.dist(a, b), math.dist(b, c))
        ln = math.sqrt(S._dot(x, x))
        if ln > cap and not (slides and i in slides):   # 3d: a corner_slides slide is capped per group already
            x = tuple(t * cap / ln for t in x)
        top.append(tuple(b[t] + x[t] for t in range(3)))
    verts = top + [H._add(p, (miters[i] if miters else n), -DEPTH) for i, p in enumerate(q)]
    faces = [tuple(range(k))] + [((i + 1) % k, i, k + i, k + (i + 1) % k) for i in range(k) if flags[i]]
    used = sorted({x for f in faces for x in f})
    remap = {old: new for new, old in enumerate(used)}
    return [verts[x] for x in used], [tuple(remap[x] for x in f) for f in faces]


_SKIN: dict = {}


def skin_pieces(name: str = S.DEFAULT) -> list:
    """Every outer face's plate pieces: [(kind, zone, cell, face index, piece, seam flags)], cached per hull."""
    if name not in _SKIN:
        surf = S.surface(name)
        edges = Edges(surf)
        out = []
        for i, (poly, n, kind) in enumerate(surf):
            for cell, q in cells(poly, n):
                zone = "lens" if cell[0] == "lens" else "plan"
                out.append((kind, zone, cell, i, q, seams(q, i, edges, zone)))
        _SKIN[name] = out
    return _SKIN[name]


_SLIDES: dict = {}


def skin_slides(name: str = S.DEFAULT) -> list:
    """corner_slides of skin_pieces(name), cached per hull."""
    if name not in _SLIDES:
        _SLIDES[name] = corner_slides(skin_pieces(name))
    return _SLIDES[name]


_MITERS: dict = {}


def skin_miters(name: str = S.DEFAULT) -> tuple:
    """fix 2: (per piece of skin_pieces(name) its corners' miters, per surface face its corners' miters), cached."""
    if name not in _MITERS:
        surf = S.surface(name)
        edges = Edges(surf)
        memo: dict = {}

        def at(p, i):
            key = (tuple(round(t, 5) for t in p), i)
            if key not in memo:
                memo[key] = miter(edges.normals_at(p), edges.normals[i])
            return memo[key]
        pieces = [[at(p, i) for p in q] for (_k, _z, _c, i, q, _f) in skin_pieces(name)]
        faces = [[at(p, i) for p in poly] for i, (poly, _n, _k) in enumerate(surf)]
        _MITERS[name] = (pieces, faces)
    return _MITERS[name]


def cell_mat(cell, mats) -> str:
    """A plate's silver, one per cell (all its pieces alike, so a lens plate is one smooth mesh)."""
    return mats[zlib.crc32(repr(cell).encode()) % len(mats)]


def j_skin(args: dict, layout: dict) -> list:
    """One part of the hull (args part: top, belly or mouth): its plates by material and zone (the lens's shaded
    smooth up to CREASE["lens"]) and the dark under-skin."""
    kind = args["part"]
    mats = MATS[kind]
    groups: dict = {}
    pieces = skin_pieces(S.DEFAULT)
    p_miters, f_miters = skin_miters(S.DEFAULT)
    for (k, zone, cell, _i, q, flags), slides, mit in zip(pieces, skin_slides(S.DEFAULT), p_miters):
        if k == kind:
            groups.setdefault((zone, cell_mat(cell, mats)), []).append(lay_seams(q, flags, slides, mit))
    # fix 2: the under-skin's corners sink along the folds' miters, so neighbouring faces' under-skins meet
    under = [([H._add(x, m, -DEPTH * 1.8) for x, m in zip(poly, mits)], [tuple(range(len(poly)))])
             for (poly, n, k), mits in zip(S.surface(S.DEFAULT), f_miters) if k == kind]
    parts = []
    for (zone, mat), g in sorted(groups.items()):
        p = L.part(f"skin_{kind}_{mat}" + ("_lens" if zone == "lens" else ""), *L.merge(*g), mat, solid=False)
        if zone == "lens":
            p["smooth_deg"] = CREASE["lens"]
        parts.append(p)
    parts.append(L.part(f"skin_{kind}_seam", *L.merge(*under), "ext_seam", solid=False))
    return parts


j_skin = H._outward(j_skin)


JAMB_OUT, JAMB_LIFT = 0.035, 0.004   # details 3b: the jamb's top strip past the wall's outer face, over the skin
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
                groups.setdefault(MATS["mouth"][0], []).append(lay(p))
    # rebuild E: the jambs. Forward of the roof line the throat's walls stood as pale interior modules with flat tops
    # at 2.05 m, free under the open notch (the "cheeks" of the D shots). Here each wall is the hull's own side of the
    # cut instead: a solid in the wall's thickness from the slab up to J's top over it (one convex face, as every
    # section of the convex hull), its inner face in the hull's plates, its top and front edge in hull_silver
    s_roof = (S.TH_ROOF_Y - my) / d[1]
    edge = []
    for sx in (1, -1):
        n = (sx * d[1], -d[0], 0.0)                     # outward
        inner, outer = [], []
        for i in range(33):
            s = 0.02 + (s_roof - 0.02) * i / 32   # 2 cm in from the nose edge (heights() is None on it)
            x, y = sx * (mx + d[0] * s), my + d[1] * s
            # details 3b: the top runs JAMB_OUT past the wall over the skin's seam chamfer (its groove read as a dark
            # band under a chewed edge), JAMB_LIFT over the skin (no z-fighting)
            xo, yo = x + n[0] * (S.WALL + JAMB_OUT), max(y + n[1] * (S.WALL + JAMB_OUT), my + 0.02)   # not past the nose
            inner.append((x, y, S.heights(x, y)[0] + JAMB_LIFT))
            outer.append((xo, yo, (S.heights(xo, yo) or S.heights(x, y))[0] + JAMB_LIFT))
        face = [(inner[0][0], inner[0][1], S.SLAB - 0.01), (inner[-1][0], inner[-1][1], S.SLAB - 0.01)]
        face += [inner[k] for k in range(len(inner) - 1, -1, -1)]
        inward = S._neg(n)
        if S._dot(S._newell(face), inward) < 0:
            face.reverse()
        top = inner[::-1]
        for p in plates(face, inward):
            # details 3b: a plate's edge on the jamb's top is laid flush (its insets chewed the edge against the sky)
            flags = [not any(_off_segment(a, u, w) < 1e-4 and _off_segment(b, u, w) < 1e-4
                             for u, w in zip(top, top[1:])) for a, b in zip(p, p[1:] + p[:1])]
            c = [sum(x[i] for x in p) / len(p) for i in range(3)]
            mat = MATS["top"][int(H._hash(round(c[0], 1), round(c[1], 1), round(c[2], 1)) * len(MATS["top"])) %
                              len(MATS["top"])]
            groups.setdefault(mat, []).append(lay_seams(p, flags))
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


# --- the raise step 2 (art#263, 2026-10-23): the entry tunnel ---------------------------------------------------------
TUN_OUT = 0.25                # the hood's side wall past the throat wall's inner face (the wall's 0.2 and 5 cm over
#                               the cheeks, which sit 3 cm proud of the wall)
TUN_TOP = S.TH_TOP + 0.15     # the hood's roof: the throat's roof and its least skin
TUN_FILL = 0.012              # the fill over the nose's top inside the notch (the jambs' tops lie 4 mm over it)
TUN_SINK = 0.03               # the raise step 3: the fill's least depth under the hood where the hood stands higher


def _tun_frame():
    """The mouth's line: (mouth x, mouth y, roof line y, tunnel front y, plan dx/dy of the walls aft of the mouth, k
    the across-to-plan-x factor there)."""
    (mx, my), (kx, ky) = S.TH_PTS[1], S.TH_PTS[2]
    return mx, my, S.TH_ROOF_Y, S.TH["tunnel_y"], (kx - mx) / (ky - my), math.hypot(kx - mx, ky - my) / (ky - my)


def _tun_w(y):
    """The throat wall's inner face (plan x, east) at y and its k: straight in the tunnel, slanted aft of the mouth."""
    mx, my, _r, _t, sl, k = _tun_frame()
    return (mx, 1.0) if y <= my else (mx + sl * (y - my), k)


def _tun_prof(y):
    """The hood's cross-section at y, east half, (x, h) from the bottom outside up over the roof to the centre: the
    throat's profile (walls vertical to the bend, the chamfer in, the ceiling) offset 0.25 m out, its chamfer parallel
    to the inside's (0.55 in over 0.85 up)."""
    w, k = _tun_w(y)
    return [(w + TUN_OUT * k, S.SLAB - 0.01), (w + TUN_OUT * k, S.FLOOR + S.TH_CH[0] + 0.074),
            (w - 0.427 * k, TUN_TOP), (0.0, TUN_TOP)]


def _tun_h(x, y):
    """The hood's top at plan (x, y) (its roof or chamfer), None past its side."""
    p = _tun_prof(y)
    ax = abs(x)
    if ax <= p[2][0]:
        return TUN_TOP
    if ax <= p[1][0]:
        return p[2][1] + (p[1][1] - p[2][1]) * (ax - p[2][0]) / (p[1][0] - p[2][0])
    return None


def _face(q, n):
    """A face wound so its Newell normal points along n (the side it is seen from)."""
    return q if S._dot(S._newell(q), n) > 0 else list(reversed(q))


def _quad(q, n):
    return (_face(q, n), [tuple(range(len(q)))])


def mouth_tunnel(args: dict, layout: dict) -> list:
    """The raise step 2 (the engineer, 2026-10-23: "extend the entrance"): the mouth run 1 m forward past the nose as
    a short tunnel (ship.toml throat tunnel_y), and its hood over J's notch. Inside: the throat's profile (walls
    vertical to the bend, the chamfer in, the ceiling) from the tunnel's front back to the throat's roof line, the
    walls in the jambs' plates (the jambs are the walls aft of the nose), the chamfers and ceiling plated, a cyan strip
    along each bend, frame ribs at the front and the nose, a grated floor with two amber floor lights. Outside: the
    hood, the throat's profile offset 0.25 m out, in the hull's plated silver, from the tunnel's front aft until the
    nose's top rises over it (the hull's closed skin cuts it: the penetration is the join, both sides); inside the
    notch, where the nose's top stands over the hood, a fill at the nose's own top (+12 mm) closes the notch, so no
    pit, lintel or jamb end sticks out (bug 2). The front: a dark portal frame round the opening, a chrome lip. Plan
    coordinates in the design frame (ship_build lifts the piece)."""
    mx, my, yr, y0, _sl, _k = _tun_frame()
    bend, cin = S.TH_CH
    h_b, h_c = S.FLOOR + bend, S.FLOOR + S.TH["clear_h"]
    ye = yr + 0.04                                    # 4 cm past the roof line: under the throat's arch (yr + 0.1)
    ys = [y0, my] + [my + (ye - my) * i / 8 for i in range(1, 9)]
    groups: dict = {}       # the hood's (outside) faces by material
    in_groups: dict = {}    # the raise step 3: the tunnel's inside faces by material (their own piece, the inside layer)

    def plate_into(q, n, mats=MATS["top"], into=groups):
        for p in plates(_face(q, n), n):
            c = [sum(x[i] for x in p) / len(p) for i in range(3)]
            m = mats[int(H._hash(round(c[0], 1), round(c[1], 1), round(c[2], 1)) * len(mats)) % len(mats)]
            into.setdefault(m, []).append(lay(p))

    def flat(q, n, mat, into=groups):
        into.setdefault(mat, []).append(_quad(q, n))

    def inner(y, e=0.0):
        w, k = _tun_w(y)
        w += e * k
        return [(w, S.FLOOR - 0.01), (w, h_b), (w - cin * k, h_c + e), (0.0, h_c + e)]

    def centre(q):
        return tuple(sum(p[j] for p in q) / len(q) for j in range(3))

    for sx in (1, -1):
        for ya, yb in zip(ys, ys[1:]):
            fwd = yb <= my + 1e-9
            e = 0.0 if fwd else 0.003                 # aft of the nose 3 mm behind the throat's own faces
            pa, pb = inner(ya, e), inner(yb, e)
            for i in range(3):
                if not fwd and i == 0:                # the jambs are the walls there: a 10 cm strip under the bend
                    q = [(sx * (pa[1][0] - 0.005), ya, h_b - 0.1), (sx * (pb[1][0] - 0.005), yb, h_b - 0.1),
                         (sx * (pb[1][0] - 0.005), yb, h_b), (sx * (pa[1][0] - 0.005), ya, h_b)]
                    flat(q, (-sx, 0.0, 0.0), "hull_silver", in_groups)
                    continue
                q = [(sx * pa[i][0], ya, pa[i][1]), (sx * pb[i][0], yb, pb[i][1]),
                     (sx * pb[i + 1][0], yb, pb[i + 1][1]), (sx * pa[i + 1][0], ya, pa[i + 1][1])]
                n = S._unit3(S._sub((0.0, (ya + yb) / 2, h_c - 1.0), centre(q)))
                plate_into(q, n, MATS["top"] if i == 0 else ("ext_silver_c", "ext_silver_b"), in_groups)
            # the hood's side, chamfer and roof, each a plated strip (hidden where the nose stands over it)
            pa, pb = _tun_prof(ya), _tun_prof(yb)
            for i in range(3):
                q = [(sx * pa[i][0], ya, pa[i][1]), (sx * pb[i][0], yb, pb[i][1]),
                     (sx * pb[i + 1][0], yb, pb[i + 1][1]), (sx * pa[i + 1][0], ya, pa[i + 1][1])]
                c = centre(q)
                plate_into(q, S._unit3(S._sub(c, (0.0, c[1], S.FLOOR + 1.0))))
            # its underside beside the floor: the walls' thickness at the slab's bottom
            q = [(sx * _tun_w(ya)[0], ya, S.SLAB - 0.01), (sx * _tun_w(yb)[0], yb, S.SLAB - 0.01),
                 (sx * pb[0][0], yb, S.SLAB - 0.01), (sx * pa[0][0], ya, S.SLAB - 0.01)]
            flat(q, (0.0, 0.0, -1.0), "hull_dark")
    flat([(-mx, y0, S.SLAB - 0.01), (mx, y0, S.SLAB - 0.01), (mx, my, S.SLAB - 0.01), (-mx, my, S.SLAB - 0.01)],
         (0.0, 0.0, -1.0), "hull_dark")                # under the tunnel's floor
    # the fill: inside the notch, where the nose's top (+TUN_FILL) stands over the hood. The raise step 3 (bug 4): one
    # connected grid a side, every vertex at the nose's top + TUN_FILL or TUN_SINK under the hood, whichever is higher,
    # so it runs under the hood's roof and chamfers without a cell's step (no cell left out) and never lies within
    # millimetres of the hood (that read as fine bands from above)
    fv, ff, nj, cols = [], [], 60, 28

    def fill_h(x, y):
        hs, hood = S.heights(x, y), _tun_h(x, y)
        if hs is None or hood is None:
            return None
        return max(hs[0] + TUN_FILL, hood - TUN_SINK)
    yf = ye

    def wf(y):
        return _tun_w(y)[0] + 0.02
    ys_f = [my + (yf - my) * j / nj for j in range(nj + 1)]
    for sx in (1, -1):
        idx = {}
        for j, y in enumerate(ys_f):
            w = wf(y)
            for i in range(cols + 1):
                x = sx * w * i / cols
                h = fill_h(x, y)
                if h is not None:
                    idx[j, i] = len(fv)
                    fv.append((x, y, h))
        for j in range(nj):
            for i in range(cols):
                q = [idx.get(k) for k in ((j, i), (j, i + 1), (j + 1, i + 1), (j + 1, i))]
                if None not in q:   # wound up (the plan frame's Newell), as _quad(q, up) winds
                    up = S._dot(S._newell([fv[k] for k in q]), (0.0, 0.0, 1.0)) > 0
                    ff.append(tuple(q) if up else tuple(reversed(q)))
        for j in range(nj):                            # its sides, down into the jambs
            ya, yb = ys_f[j], ys_f[j + 1]
            xa, xb = sx * wf(ya), sx * wf(yb)
            ha, hb = S.heights(xa, ya), S.heights(xb, yb)
            ga, gb = _tun_h(xa, ya), _tun_h(xb, yb)
            if ha and hb and ga and gb and max(ha[0] - ga, hb[0] - gb) + TUN_FILL > -TUN_SINK:
                q = _face([(xa, ya, min(ga, ha[0]) - 0.05), (xb, yb, min(gb, hb[0]) - 0.05),
                           (xb, yb, fill_h(xb, yb)), (xa, ya, fill_h(xa, ya))], (sx, 0.0, 0.0))
                ff.append(tuple(range(len(fv), len(fv) + 4)))
                fv += q
    xe = wf(yf)                                        # its end, aft of the lintel, into the hull
    end = [(-xe, yf, TUN_TOP - 0.3), (xe, yf, TUN_TOP - 0.3)]
    end += [(x, yf, fill_h(x, yf) or TUN_TOP) for x in (xe * (1 - 2 * i / 28) for i in range(29))]
    fill_part = L.part("tunnel_fill", *L.merge((fv, ff), _quad(end, (0.0, 1.0, 0.0))), "hull_silver", solid=False)
    # the front: the portal between the opening and the hood's outline, its edge back to the hood, a chrome lip
    po, pi = _tun_prof(y0), inner(y0)
    outline = [(-p[0], p[1]) for p in po[:-1]] + [(p[0], p[1]) for p in reversed(po[:-1])]
    opening = [(-p[0], p[1]) for p in pi[:-1]] + [(p[0], p[1]) for p in reversed(pi[:-1])]
    yf = y0 - 0.06
    portal, lip = [], []
    for a, b, c, d in _portal_quads(opening, outline):
        portal.append(_quad([(a[0], yf, a[1]), (b[0], yf, b[1]), (c[0], yf, c[1]), (d[0], yf, d[1])], (0.0, -1.0, 0.0)))
    for (xa, ha), (xb, hb) in zip(outline, outline[1:]):
        q = [(xa, yf, ha), (xb, yf, hb), (xb, y0 + 0.01, hb), (xa, y0 + 0.01, ha)]
        c = centre(q)
        portal.append(_quad(q, S._unit3(S._sub(c, (0.0, c[1], S.FLOOR + 1.0)))))
    for (xa, ha), (xb, hb) in zip(opening, opening[1:]):
        c = ((xa + xb) / 2, (ha + hb) / 2)
        nn = S._unit3((-c[0], 0.0, (h_c - 1.0) - c[1]))
        q = [(xa + nn[0] * 0.004, yf, ha + nn[2] * 0.004), (xb + nn[0] * 0.004, yf, hb + nn[2] * 0.004),
             (xb + nn[0] * 0.004, y0 + 0.08, hb + nn[2] * 0.004), (xa + nn[0] * 0.004, y0 + 0.08, ha + nn[2] * 0.004)]
        lip.append(_quad(q, nn))
    # frame ribs (the throat's bands) just inside the front and at the nose; the cyan strips along the bends
    ribs, strips, lamps, halos, bezels = [], [], [], [], []
    for yy in (y0 + 0.16, my):
        p = inner(yy)
        prof = [(-x, h) for x, h in p[1:]] + [(x, h) for x, h in reversed(p[1:])]
        for (xa, ha), (xb, hb) in zip(prof, prof[1:]):
            if math.dist((xa, ha), (xb, hb)) < 1e-6:
                continue
            c = ((xa + xb) / 2, (ha + hb) / 2)
            nn = S._unit3((-c[0], 0.0, (h_c - 1.0) - c[1]))
            a0, b0 = (xa + nn[0] * 0.006, ha + nn[2] * 0.006), (xb + nn[0] * 0.006, hb + nn[2] * 0.006)
            a1, b1 = (xa + nn[0] * 0.035, ha + nn[2] * 0.035), (xb + nn[0] * 0.035, hb + nn[2] * 0.035)
            ribs.append(_quad([(a1[0], yy - 0.05, a1[1]), (b1[0], yy - 0.05, b1[1]), (b1[0], yy + 0.05, b1[1]),
                               (a1[0], yy + 0.05, a1[1])], nn))
            for s in (-1, 1):
                ribs.append(_quad([(a0[0], yy + s * 0.05, a0[1]), (b0[0], yy + s * 0.05, b0[1]),
                                   (b1[0], yy + s * 0.05, b1[1]), (a1[0], yy + s * 0.05, a1[1])], (0.0, float(s), 0.0)))
    for sx in (1, -1):
        for ya, yb in zip(ys, ys[1:]):
            yb = min(yb, ye - 0.06)
            wa, wb = _tun_w(ya)[0] - 0.008, _tun_w(yb)[0] - 0.008
            strips.append(_quad([(sx * wa, ya, h_b - 0.03), (sx * wb, yb, h_b - 0.03), (sx * wb, yb, h_b),
                                 (sx * wa, ya, h_b)], (-sx, 0.0, 0.0)))
        x = sx * (mx - 0.30)                           # the throat's floor lights, 0.3 m off the wall, along it
        yc = (y0 + my) / 2
        bezels.append(L.box(x - 0.07, x + 0.07, yc - 0.22, yc + 0.22, S.FLOOR - 0.002, S.FLOOR + 0.006))
        halos.append(L.box(x - 0.055, x + 0.055, yc - 0.165, yc + 0.165, S.FLOOR + 0.006, S.FLOOR + 0.008))
        lamps.append(L.box(x - 0.032, x + 0.032, yc - 0.15, yc + 0.15, S.FLOOR + 0.008, S.FLOOR + 0.011))
    if args.get("part") == "hood":   # the raise step 3: the outside (the outside layer): the hood, fill, portal, lip
        parts = [L.part(f"tunnel_{m}", *L.merge(*g), m, solid=False) for m, g in sorted(groups.items())]
        return parts + [fill_part,
                        L.part("tunnel_portal", *L.merge(*portal), "ext_frame", solid=False),
                        L.part("tunnel_lip", *L.merge(*lip), "ext_chrome", solid=False)]
    # the inside (the inside layer, lit by the throat's strips): walls, chamfers, ceiling, ribs, strips, floor
    parts = [L.part(f"tunnel_{m}", *L.merge(*g), m, solid=False) for m, g in sorted(in_groups.items())]
    parts += [L.part("tunnel_ribs", *L.merge(*ribs), "ext_frame", solid=False),
              L.part("tunnel_strips", *L.merge(*strips), "int_cyan", solid=False),
              L.part("tunnel_slab", *L.box(-mx, mx, y0, my + 0.002, S.SLAB, S.FLOOR - 0.012), "hull_dark"),
              L.part("tunnel_grate", *L.box(-mx + 0.05, mx - 0.05, y0 + 0.02, my, S.FLOOR - 0.012, S.FLOOR - 0.002),
                     "floor_grate"),
              L.part("tunnel_bezels", *L.merge(*bezels), "int_silver_c"),
              L.part("tunnel_halos", *L.merge(*halos), "int_halo"),
              L.part("tunnel_lamps", *L.merge(*lamps), "int_amber")]
    return parts


def _portal_quads(opening, outline, m=24):
    """The portal's face between the opening and the outline ((x, h) from the west bottom over the top to the east
    bottom), each resampled by arc length to m segments: quads between matched points."""
    def resample(poly):
        d = [0.0]
        for a, b in zip(poly, poly[1:]):
            d.append(d[-1] + math.dist(a, b))
        out = []
        for i in range(m + 1):
            t = d[-1] * i / m
            k = min(max(j for j in range(len(d)) if d[j] <= t + 1e-9), len(poly) - 2)
            s = (t - d[k]) / max(d[k + 1] - d[k], 1e-9)
            out.append((poly[k][0] + (poly[k + 1][0] - poly[k][0]) * s, poly[k][1] + (poly[k + 1][1] - poly[k][1]) * s))
        return out
    a, b = resample(opening), resample(outline)
    return [(a[i], a[i + 1], b[i + 1], b[i]) for i in range(m)]


mouth_tunnel = H._outward(mouth_tunnel)
