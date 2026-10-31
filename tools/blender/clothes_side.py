"""The cloth's signed side at a point, robust where faces tie (art #196, M2i; shared by clothes_dress.py and, since
M2j, clothes_proof.py). Runs inside Blender (mathutils); the sign's maths is clothes_fit_geom.tie_side, unit-tested.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from mathutils import Vector
from mathutils import geometry as mgeo
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clothes_fit_geom as F  # noqa: E402


class ClothSide:
    """M2i: the cloth's nearest point and a signed distance that does not hang on the face a BVH query returns. On
    an edge or vertex several faces tie; the side comes from all of them (clothes_fit_geom.tie_side). M2h's d57 and
    d59 changed the garment far from the crotch (the crumbs, the cuffs), the tree's face order moved, the query
    returned the other face of the seat's seam, and the crotch's kept skin and its pokes changed (9 to 14 mm)."""

    def __init__(self, objs, tol: float = 1e-6, co=None, polys=None, edge_check: bool = False):
        """objs: the cloth's mesh objects (their world coordinates); or co and polys given directly (the proof's
        posed cloth per frame). edge_check (M2j, the proof's speed): a nearest point well inside the BVH's face
        (farther than tol from each of its edges) is no tie, so its plain side is kept without the tie search."""
        if co is None:
            self.co, self.polys = [], []
            off = 0
            for o in objs:
                self.co += [o.matrix_world @ v.co for v in o.data.vertices]
                self.polys += [[i + off for i in p.vertices] for p in o.data.polygons]
                off += len(o.data.vertices)
        else:
            self.co, self.polys = [Vector(c) for c in co], [list(q) for q in polys]
        self.edge_check = edge_check
        self.tree = BVHTree.FromPolygons([tuple(c) for c in self.co], self.polys)
        self.vf: list[list[int]] = [[] for _ in self.co]
        for fi, p in enumerate(self.polys):
            for k in p:
                self.vf[k].append(fi)
        self.tol, self.flips = tol, 0
        self._n: dict[int, Vector] = {}

    def normal(self, fi: int) -> Vector:
        if fi not in self._n:
            self._n[fi] = mgeo.normal([self.co[k] for k in self.polys[fi]])
        return self._n[fi]

    def face_dist(self, p: Vector, fi: int) -> float:
        """The distance from p to polygon fi (a fan of triangles)."""
        ids = self.polys[fi]
        best = math.inf
        for j in range(1, len(ids) - 1):
            q = mgeo.closest_point_on_tri(p, self.co[ids[0]], self.co[ids[j]], self.co[ids[j + 1]])
            best = min(best, (p - q).length)
        return best

    def angle_at(self, fi: int, q: Vector) -> float:
        """The corner angle of polygon fi at its vertex nearest q (the pseudo-normal's weight at a vertex tie)."""
        ids = self.polys[fi]
        k = min(range(len(ids)), key=lambda j: (self.co[ids[j]] - q).length)
        a, b, c = self.co[ids[k - 1]], self.co[ids[k]], self.co[ids[(k + 1) % len(ids)]]
        e1, e2 = a - b, c - b
        return e1.angle(e2, 0.0) if e1.length > 0 and e2.length > 0 else 0.0

    def inside_face(self, q: Vector, fi: int) -> bool:
        """Whether q lies farther than tol from every edge of polygon fi (no other face can tie there)."""
        ids = self.polys[fi]
        for j in range(len(ids)):
            a, b = self.co[ids[j]], self.co[ids[(j + 1) % len(ids)]]
            t, _f = mgeo.intersect_point_line(q, a, b)
            if (q - t).length <= self.tol:
                return False
        return True

    def find(self, p: Vector, dist: float):
        """(loc, normal, face, signed distance +out) of the nearest cloth within dist, or four Nones. On a tie the
        normal is the tied faces' pseudo-normal (the skin pull moves along it: one face's normal at the seat's seam
        moved the crotch's skin sideways along the seam, still within 1 mm of the cloth)."""
        loc, nor, fi, d = self.tree.find_nearest(p, dist)
        if loc is None:
            return None, None, None, None
        u = p - loc
        plain = u.dot(nor)
        if self.edge_check and self.inside_face(loc, fi):
            return loc, nor, fi, plain
        cand = {f for k in self.polys[fi] for f in self.vf[k]}
        tied = [f for f in cand if self.face_dist(p, f) <= d + self.tol]
        if len(tied) < 2:
            return loc, nor, fi, plain
        near_v = min((self.co[k] for f in tied for k in self.polys[f]), key=lambda c: (c - loc).length)
        on_vertex = (near_v - loc).length <= self.tol
        ws = [self.angle_at(f, loc) if on_vertex else 1.0 for f in tied]
        s = F.tie_side(tuple(u), d, [tuple(self.normal(f)) for f in tied], ws)
        pn = Vector(F.pseudo_normal([tuple(self.normal(f)) for f in tied], ws))
        if s == 0.0 or pn.length < 1e-9:
            return loc, nor, fi, plain
        self.flips += (s > 0) != (plain > 0)
        return loc, pn.normalized(), fi, s
