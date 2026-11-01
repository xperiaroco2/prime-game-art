"""The dungarees' Gate 2 rough build to the spec (art #196, G3a; docs/clothes.md, "The dungarees' Gate 2 build").

Opens the dressed character M2 left (d79: her body B13, the shirt `top`, the sneakers `shoes`, the Meshy `garment`)
and replaces the garment with one built to `specs/dungarees_dims.toml`; every size comes from the spec's cm (and
the approved drawing's shapes, garment_drawing.lines), measured against her undressed rest (--ref, the spec's probe):

- the trousers: the Meshy garment's largest piece kept between the cuff (cut inside it, --leg-cut) and --rise-cut;
  over the cut a yoke extruded from the cut's loop up inside the waistband (her body + --yoke-ease), the trousers'
  own ease eased into it; weights from the trousers' to the band's;
- the waistband: a closed ring, the spec's top and height, her trunk + the shirt + [build] band_ease_cm, on one bone
  (--band-bone, Spine): a stiff ring that cannot stretch;
- the bib: a 2 mm plate, the spec's top, widths and lean B (the forward envelope of her front + the shirt + the
  bust gap, the top edge at its own gap): straight across, one bend over the bust; on one bone (--panel-bone, Chest),
  so it moves as one piece; its lower edge goes [build] plate_lap_cm down over the band (G3f, the manager's option
  (a)), clear of it, so a Spine-against-Chest twist slides it over the band, hidden (G3d's seam blend, [build]
  seam_blend_cm, eased its lowest cm from the band's weights to Chest's and squeezed them: 0 since G3f);
- the back panel: the same at the back, its top the drawing's shallow V (the centre at back_top_z, the corners 3 cm
  higher at back_top_w);
- the straps: 3.8 cm ribbons at x = +-strap_x laid by rays over the bib, her shirt and the back panel; their ends
  carry the bib's and the back panel's weights exactly, the middle --strap-sh-share of her shoulder's (default 0: the
  whole strap rides Chest; no arm bones);
- the pocket (a `pocket` material plate on the bib), the buckle buttons and rings, the side buttons on the band,
  the turn-ups (rigid rings on the lower leg, the spec's hem, height and width).

The bare ankle: d79's body had its leg skin removed inside the old trousers down to 14 cm; the faces of its hidden
`body_removed` between --ankle-restore heights are joined back into the body, so the strip under the raised hem is
her skin. Saves OUT/axolotl_char.blend and OUT/axolotl_char.glb (alien_loco._export) and OUT/build.json.

    tools/runner/blender.py's run_script("dungarees_build.py", ["--spec", S, "--dressed", D79.blend,
        "--ref", <spec probe char.json>, "--out", DIR])
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import garment_spec as S  # noqa: E402

ARM_WORDS = ("UpperArm", "LowerArm", "Hand", "Thumb", "Index", "Middle", "Ring", "Little", "Head", "Jaw", "Eye", "Gill")
TRUNK = ("Hips", "Spine", "Chest", "UpperChest")
SHIRT = 0.005          # the spec's shirt (garment_drawing: front = her body - 0.5 cm)


def smooth01(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def mix(a: dict, b: dict, t: float) -> dict:
    out = {k: (1 - t) * a.get(k, 0.0) + t * b.get(k, 0.0) for k in set(a) | set(b)}
    return norm({k: v for k, v in out.items() if v > 1e-4})


def norm(w: dict, keep=None) -> dict:
    if keep is not None:
        w = {k: v for k, v in w.items() if any(k == n or k.startswith(n) for n in keep)}
    s = sum(w.values())
    return {k: v / s for k, v in w.items()} if s > 0 else {}


def no_arms(w: dict) -> dict:
    return norm({k: v for k, v in w.items() if not any(a in k for a in ARM_WORDS)})


class Weights:
    """Vertex weights by nearest vertex of a skinned mesh (its rest = mesh coordinates)."""

    def __init__(self, obj, *more) -> None:
        objs = [obj, *(o for o in more if o is not None)]   # G3k: her kept skin and body_removed, the skin under the cloth
        self.w = []
        self.kd = KDTree(sum(len(o.data.vertices) for o in objs))
        for o in objs:
            names = {g.index: g.name for g in o.vertex_groups}
            mw = o.matrix_world
            for v in o.data.vertices:
                self.kd.insert(mw @ v.co, len(self.w))
                self.w.append({names[g.group]: g.weight for g in v.groups if g.weight > 1e-4 and g.group in names})
        self.kd.balance()

    def at(self, p) -> dict:
        return dict(self.w[self.kd.find(Vector(p))[1]])

    def mean(self, pts, keep=None) -> dict:
        acc = {}
        for p in pts:
            for k, v in norm(self.at(p), keep).items():
                acc[k] = acc.get(k, 0.0) + v
        return norm(acc)


class Ref:
    """Her undressed rest (the spec's probe): rays for her front, back and radius at a height."""

    def __init__(self, probe: dict, name: str) -> None:
        m = next(x for x in probe["meshes"] if x["name"] == name)
        self.bvh = BVHTree.FromPolygons([Vector(v) for v in m["vertices"]], [t[:3] for t in m["tris"]])

    def front(self, z: float, half: float, back: bool = False, x0: float = 0.0):
        best, n = None, max(1, int(round(2 * half / 0.004)))
        for i in range(n + 1):
            x = x0 - half + i * 2 * half / n
            o, d = (Vector((x, 1.0, z)), Vector((0, -1, 0))) if back else (Vector((x, -1.0, z)), Vector((0, 1, 0)))
            hit = self.bvh.ray_cast(o, d, 2.0)[0]
            if hit is not None:
                best = hit.y if best is None else (max(best, hit.y) if back else min(best, hit.y))
        return best

    def radius(self, z: float, th: float, cy: float, far: float = 0.5):
        d = Vector((math.cos(th), math.sin(th), 0.0))
        o = Vector((0.0, cy, z)) + d * far
        hit = self.bvh.ray_cast(o, -d, far)[0]
        return None if hit is None else (hit - Vector((0.0, cy, z))).length


def envelope(pts, front: bool = True):
    """The convex chain of (z, y) points in front of all (front: the least y) or behind all (back: the most y)."""
    pts = sorted(pts)
    sg = 1 if front else -1
    hull = []
    for p in pts:
        while len(hull) >= 2:
            (z1, y1), (z2, y2) = hull[-2], hull[-1]
            cross = (z2 - z1) * (p[1] - y1) - (y2 - y1) * (p[0] - z1)
            if sg * cross <= 0:      # keep the chain convex towards the outside
                hull.pop()
            else:
                break
        hull.append(p)
    return hull


def chain_y(hull, z: float) -> float:
    for (z1, y1), (z2, y2) in zip(hull, hull[1:]):
        if z1 <= z <= z2:
            return y1 + (y2 - y1) * (z - z1) / (z2 - z1) if z2 > z1 else y1
    return hull[0][1] if z < hull[0][0] else hull[-1][1]


def smooth_rows(rows, plate: float, deg: int = 2):
    """The back panel's rows across (G3f): per row a polynomial in x of degree deg fitted (least squares) to the row's
    outer points, the coefficients averaged over the rows +-2 (weights 1 2 3 2 1), then the row lifted (y up: behind
    her) by the most any of its points stood behind the curve, so it never cuts into her back; the inner face plate in
    front. G3g: deg 4 follows her sides' turn, where the quadratic's lift left the panel's edges off her (3/4 views)."""
    import numpy as np
    coef = []
    for row in rows:
        x = np.array([p.x for p, _q in row])
        y = np.array([p.y for p, _q in row])
        coef.append(np.polyfit(x, y, deg))
    coef = np.array(coef)
    k = np.array([1.0, 2.0, 3.0, 2.0, 1.0])
    out = []
    for j, row in enumerate(rows):
        lo, hi = max(0, j - 2), min(len(rows), j + 3)
        w = k[lo - j + 2:hi - j + 2]
        c = (coef[lo:hi] * w[:, None]).sum(0) / w.sum()
        x = np.array([p.x for p, _q in row])
        y = np.array([p.y for p, _q in row])
        f = np.polyval(c, x)
        f += max(0.0, float((y - f).max()))
        out.append([(Vector((p.x, fy, p.z)), Vector((p.x, fy - plate, p.z))) for (p, _q), fy in zip(row, f.tolist())])
    return out


class Builder:
    """One bmesh for the whole garment; per vertex its weights and per face its material."""

    def __init__(self) -> None:
        self.bm = bmesh.new()
        self.W: dict = {}

    def vert(self, co, w):
        v = self.bm.verts.new(Vector(co))
        self.W[v] = w
        return v

    def face(self, vs, mat):
        f = self.bm.faces.new(vs)
        f.material_index = mat
        return f

    def slab(self, rows, w_of, mat, closed_u=False):
        """A closed plate from rows of outer/inner point pairs: rows[j][i] = (outer, inner)."""
        nu = len(rows[0])
        O = [[self.vert(rows[j][i][0], w_of(rows[j][i][0])) for i in range(nu)] for j in range(len(rows))]
        I = [[self.vert(rows[j][i][1], w_of(rows[j][i][1])) for i in range(nu)] for j in range(len(rows))]
        us = range(nu) if closed_u else range(nu - 1)
        for j in range(len(rows) - 1):
            for i in us:
                k = (i + 1) % nu
                self.face([O[j][i], O[j][k], O[j + 1][k], O[j + 1][i]], mat)
                self.face([I[j][i], I[j + 1][i], I[j + 1][k], I[j][k]], mat)
        for i in us:                                    # the bottom and top rims
            k = (i + 1) % nu
            self.face([O[0][i], I[0][i], I[0][k], O[0][k]], mat)
            self.face([O[-1][i], O[-1][k], I[-1][k], I[-1][i]], mat)
        if not closed_u:                                # the side rims
            for j in range(len(rows) - 1):
                self.face([O[j][0], O[j + 1][0], I[j + 1][0], I[j][0]], mat)
                self.face([O[j][-1], I[j][-1], I[j + 1][-1], O[j + 1][-1]], mat)
        return O, I

    def disc(self, centre, axis, d, depth, w, mat, segs=12):
        axis = Vector(axis).normalized()
        a = axis.orthogonal().normalized()
        b = axis.cross(a)
        ring = lambda off: [self.vert(Vector(centre) + axis * off + (a * math.cos(2 * math.pi * i / segs) +
                                       b * math.sin(2 * math.pi * i / segs)) * d / 2, w) for i in range(segs)]
        lo, hi = ring(0.0), ring(-depth)
        self.face(lo[::-1], mat)
        self.face(hi, mat)
        for i in range(segs):
            k = (i + 1) % segs
            self.face([lo[i], lo[k], hi[k], hi[i]], mat)


def _spread(top, co, got: dict, fade: float):
    """The distance along the shirt's edges from the covered vertices (a Dijkstra) within fade, and each one's source."""
    import heapq
    nbr = {}
    for e in top.data.edges:
        i, j = e.vertices
        nbr.setdefault(i, []).append(j)
        nbr.setdefault(j, []).append(i)
    dist = {i: 0.0 for i in got}
    src = {i: i for i in got}
    heap = [(0.0, i) for i in got]
    heapq.heapify(heap)
    while heap:
        dd, i = heapq.heappop(heap)
        if dd > dist.get(i, 1e9) or dd > fade:
            continue
        for j in nbr.get(i, []):
            nd = dd + (co[i] - co[j]).length
            if nd < dist.get(j, 1e9) and nd <= fade:
                dist[j], src[j] = nd, src[i]
                heapq.heappush(heap, (nd, j))
    return dist, src


def shirt_follow(top, B, skip_vs, fade: float, reach: float = 0.04, near: float = 0.015, low_z: float = -1.0,
                 low_skip=frozenset(), strap_vs=frozenset(), strap_reach: float = 0.0, strap_fade: float = 0.0,
                 keep=frozenset()) -> dict:
    """The shirt under the dungarees takes their weights (G3e, art #196: on her body's weights it came through the band
    and the plates, 8 mm in Idle, 35 mm in Jump_Start, the band's pale stripes): each shirt vertex whose normal meets the
    garment within reach, or that lies within near of it (not a strap, which lies over her shoulder's skin) takes the garment's weights there (the
    hit face's, by area); the shirt round them eases back to its own over fade (m, along the shirt's edges).
    G3i: with strap_reach > 0 a strap (strap_vs, its vertices) gives its weights only to the shirt directly under it
    (its normal meets the strap within strap_reach; the near rule never takes a strap), eased back over strap_fade, and
    never to the shirt's vertices in keep (the collar's band): in G3h every shirt vertex within 3 cm of a strap took it
    whole, the collar and the front between the straps on Chest and her shoulder's bone, and her neck came through."""
    from mathutils.interpolate import poly_3d_calc
    B.bm.faces.ensure_lookup_table()
    B.bm.faces.index_update()
    gfaces = list(B.bm.faces)
    tree = BVHTree.FromBMesh(B.bm)
    # G3f: under low_z (the band's top) a shirt vertex never takes a plate's lap (low_skip: their vertices); there it
    # reached the bib's lap on Chest past the yoke and came out through the yoke in Jog (h1: 3-7 vertices, 2-5 mm)
    keep_f = [f for f in gfaces if not any(x in low_skip for x in f.verts)]
    B.bm.verts.index_update()
    low_tree = BVHTree.FromPolygons([v.co for v in B.bm.verts], [[x.index for x in f.verts] for f in keep_f])
    mw = top.matrix_world
    nm = mw.to_3x3().inverted().transposed()
    names = {g.index: g.name for g in top.vertex_groups}
    own = [{names[g.group]: g.weight for g in v.groups if g.group in names and g.weight > 1e-4} for v in top.data.vertices]
    co = [mw @ v.co for v in top.data.vertices]
    on_strap = (lambda f: any(x in strap_vs for x in f.verts)) if strap_reach > 0 else (lambda f: False)
    got, got_s = {}, {}
    for v in top.data.vertices:
        n = (nm @ v.normal).normalized()
        low = co[v.index].z < low_z
        tr = low_tree if low else tree
        hit, _hn, fi, d = tr.ray_cast(co[v.index] + n * 1e-4, n, reach)
        f = None if hit is None else (keep_f[fi] if low else gfaces[fi])
        strap = f is not None and on_strap(f)
        if strap and (d > strap_reach or v.index in keep):
            hit, f, strap = None, None, False
        if hit is None:   # the shirt's hem turned down (f06: 1-3 hem vertices 1-2.5 mm out in Sprint and Jump_Start)
            hit, _hn, fi, _d = tr.find_nearest(co[v.index], near)
            f = None if hit is None else (keep_f[fi] if low else gfaces[fi])
            if f is not None and on_strap(f):
                continue
        if hit is None:
            continue
        if f.material_index == 2 or any(x in skip_vs for x in f.verts):
            continue
        w = poly_3d_calc([x.co for x in f.verts], hit)
        acc = {}
        for x, k in zip(f.verts, w):
            for g, val in B.W.get(x, {}).items():
                acc[g] = acc.get(g, 0.0) + k * val
        (got_s if strap else got)[v.index] = norm(acc)
    dist, src = _spread(top, co, got, fade)
    dist_s, src_s = _spread(top, co, got_s, strap_fade) if got_s else ({}, {})
    groups = {g.name: g for g in top.vertex_groups}
    changed = 0
    # G3k: the shirt directly under a strap takes the strap's weights whole, the shirt directly under a plate the
    # plate's; between them the plates' fade first, the straps' over it. Before G3k the plates' 5.5 cm fade came last:
    # it pulled the two shirt vertices under each strap's back run (+-10.2, 11.8, 123.0 cm) to the back panel's Spine
    # (0.69) while the strap rode her shoulder (0.72), and in every clip they stood 29-73 mm through the strap
    for i in set(dist) | (set(dist_s) - set(keep)):
        w = own[i]
        if i in dist and i not in got_s:
            w = mix(w, got[src[i]], 1.0 if i in got else 1 - smooth01(dist[i] / fade))
        if i in dist_s and i not in keep and i not in got:
            w = mix(w, got_s[src_s[i]], 1.0 if i in got_s else 1 - smooth01(dist_s[i] / strap_fade))
        w = norm(w)
        for g in groups.values():
            g.remove([i])
        for g, val in w.items():
            if g not in groups:
                groups[g] = top.vertex_groups.new(name=g)
            groups[g].add([i], val, "REPLACE")
        changed += 1
    return {"covered": len(got), "covered_by_straps": len(got_s), "faded": changed - len(got) - len(got_s),
            "shirt_verts": len(co), "fade_m": fade, "strap_reach_m": strap_reach, "strap_fade_m": strap_fade,
            "kept": len(keep)}


def collar_band(top, width: float) -> set:
    """The shirt's vertices within width (m, along its edges) of its collar: its highest boundary loop (G3i)."""
    if width <= 0:
        return set()
    import heapq
    mw = top.matrix_world
    co = [mw @ v.co for v in top.data.vertices]
    count = {}
    for p in top.data.polygons:
        vs = list(p.vertices)
        for i in range(len(vs)):
            e = (min(vs[i], vs[i - 1]), max(vs[i], vs[i - 1]))
            count[e] = count.get(e, 0) + 1
    nb, edge_nb = {}, {}
    for e in top.data.edges:
        i, j = e.vertices
        nb.setdefault(i, []).append(j)
        nb.setdefault(j, []).append(i)
    for (i, j), c in count.items():
        if c == 1:
            edge_nb.setdefault(i, []).append(j)
            edge_nb.setdefault(j, []).append(i)
    seen, loops = set(), []
    for s0 in edge_nb:
        if s0 in seen:
            continue
        loop, stack = [], [s0]
        while stack:
            v = stack.pop()
            if v not in seen:
                seen.add(v)
                loop.append(v)
                stack += edge_nb[v]
        loops.append(loop)
    ring = max(loops, key=lambda L: sum(co[i].z for i in L) / len(L))
    dist = {i: 0.0 for i in ring}
    heap = [(0.0, i) for i in ring]
    while heap:
        dd, i = heapq.heappop(heap)
        if dd > dist.get(i, 1e9):
            continue
        for j in nb.get(i, []):
            nd = dd + (co[i] - co[j]).length
            if nd <= width and nd < dist.get(j, 1e9):
                dist[j] = nd
                heapq.heappush(heap, (nd, j))
    return set(dist)


def shirt_trim(top, z_cut: float) -> dict:
    """The shirt's faces reaching under z_cut (m, world, at rest) removed (G3g; f1 removed only those wholly under it
    and kept the hem's vertices at 90.3 and 92 cm, still out): its lowest few cm lie inside the
    trousers' yoke, a closed ring under the band, never seen; there the yoke folds at her hip crease and the hem came
    out through it (k50: 3-7 vertices 1-5 mm in Jog, Sprint, Strafe and the jumps; moving it in made it worse)."""
    if z_cut <= 0:
        return {"z_cut_m": 0.0, "faces": 0}
    mw = top.matrix_world
    bm = bmesh.new()
    bm.from_mesh(top.data)
    gone = [f for f in bm.faces if any((mw @ v.co).z < z_cut for v in f.verts)]
    bmesh.ops.delete(bm, geom=gone, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.to_mesh(top.data)
    bm.free()
    top.data.update()
    return {"z_cut_m": z_cut, "faces": len(gone), "verts": len(loose), "shirt_verts": len(top.data.vertices)}


def shirt_hem_in(top, inset: float, h: float) -> dict:
    """The shirt's hem drawn in by inset (m) toward its middle, eased to nothing h over its lowest point (G3f: its
    hem at 89.5 cm came out through the yoke in Sprint and Jump_Start, 1-2 vertices 1.3-2.5 mm)."""
    if inset <= 0:
        return {"inset_m": 0.0, "verts": 0}
    me = top.data
    zmin = min(v.co.z for v in me.vertices)
    ring = [v.co for v in me.vertices if v.co.z < zmin + h]
    cx, cy = sum(p.x for p in ring) / len(ring), sum(p.y for p in ring) / len(ring)
    keys = me.shape_keys.key_blocks if me.shape_keys else []
    moved = 0
    for v in me.vertices:
        t = 1 - smooth01((v.co.z - zmin) / h)
        if t <= 0:
            continue
        off = Vector((cx - v.co.x, cy - v.co.y, 0.0))   # in toward its middle, not up: the hem keeps its height
        if off.length < 1e-6:
            continue
        off = off.normalized() * inset * t
        v.co += off
        for kb in keys:
            kb.data[v.index].co += off
        moved += 1
    return {"inset_m": inset, "h_m": h, "verts": moved, "hem_z_m": round(zmin, 4)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--dressed", required=True, help="d79's dressed .blend (body, top, shoes, garment, body_removed)")
    ap.add_argument("--ref", required=True, help="the spec's probe of her undressed rest (char.json)")
    ap.add_argument("--ref-mesh", default="axolotl_char")
    ap.add_argument("--out", required=True)
    ap.add_argument("--rise-cut", type=float, default=0.88, help="the trousers kept under this height (m)")
    ap.add_argument("--leg-cut", type=float, default=0.215, help="the legs kept over this (inside the turn-up)")
    ap.add_argument("--yoke-ease", type=float, default=0.0045, help="the yoke's top off her body (inside the band)")
    ap.add_argument("--yoke-rows", type=int, default=9)
    ap.add_argument("--yoke-into-band", type=float, default=0.005, help="the yoke's top over the band's bottom (m)")
    ap.add_argument("--ankle-restore", default="0.125,0.215",
                    help="body_removed faces between these heights rejoin (to --leg-cut: her skin inside the turn-up)")
    ap.add_argument("--plate", type=float, default=0.002, help="the bib's and back panel's thickness (m)")
    ap.add_argument("--panel-bone", default="Chest",
                    help="the bib, pocket, back panel and the straps' ends on this bone alone (rigid); '' = her blend")
    ap.add_argument("--band-bone", default="Spine", help="the waistband on this bone alone (rigid); '' = her blend")
    ap.add_argument("--strap-top-cm", type=float, default=None,
                    help="the strap's top over her trapezius follows her shoulder: over this arc length (cm) round "
                         "its highest point a smooth gradient from the panel bone to her shoulder's weights (G3e; "
                         "default the spec's [build] strap_top_cm, 0: off)")
    ap.add_argument("--strap-top-share", type=float, default=1.0, help="her shoulder's share at the strap's top")
    ap.add_argument("--back-band-share", type=float, default=None,
                    help="the band bone's share in the back panel's one blend (default the spec's [build] "
                         "back_band_share, 0: Chest alone)")
    ap.add_argument("--lap-clear-cm", type=float, default=None, help="default the spec's [build] plate_lap_clear_cm")
    ap.add_argument("--no-shirt-follow", action="store_true",
                    help="keep the shirt's own weights under the dungarees (G3e: it takes theirs, so it stays under)")
    ap.add_argument("--strap-back-on-chest", type=int, default=None,
                    help="1: the straps' back rows on the bib's weights (default the spec's [build] strap_back_on_chest)")
    ap.add_argument("--strap-inner-mm", type=float, default=None,
                    help="the strap's inner face off the shirt (default the spec's [build] strap_inner_mm, else 0.5)")
    ap.add_argument("--shirt-follow-straps", type=int, default=None,
                    help="1: the shirt under the straps takes their weights (default the spec's [build] shirt_follow_straps)")
    ap.add_argument("--strap-skin-z-cm", type=float, default=None,
                    help="the strap's rows at or over this height take her skin's weights (default the spec's [build] "
                         "strap_skin_z_cm, 0: off)")
    ap.add_argument("--strap-skin-blend-cm", type=float, default=None,
                    help="eased back to the row's own over this arc (default the spec's strap_skin_blend_cm)")
    ap.add_argument("--strap-back-join-cm", type=float, default=None,
                    help="the straps' back ends join the back panel: on its weights, eased from her skin's over this "
                         "arc below the skin rows (default the spec's [build] strap_back_join_cm, 0: off, on Chest)")
    ap.add_argument("--strap-skin-whole", type=int, default=None,
                    help="1: her skin's weights under the straps from her whole skin, body_removed too (default the "
                         "spec's [build] strap_skin_whole, else 1; 0: her kept skin alone, G3j)")
    ap.add_argument("--back-corner-chest", type=float, default=None,
                    help="the back panel's top takes this share of the bib's weights (Chest), the straps' back ends "
                         "the panel's there (default the spec's [build] back_corner_chest, 0: off)")
    ap.add_argument("--back-corner-fade-cm", type=float, default=None,
                    help="that share eased in over the panel's top this many cm under its corners (0: the whole panel, "
                         "rigid; default the spec's [build] back_corner_fade_cm)")
    ap.add_argument("--strap-skin-drop", default=None,
                    help="bones (name parts, comma-separated) her skin's weights lose there (default the spec's "
                         "strap_skin_drop)")
    ap.add_argument("--strap-sh-share", type=float, default=0.0,
                    help="the straps' middle: this share of her shoulder's weights, the rest the panel bone's (0: the "
                         "whole strap rides the panel bone, G3c c01: stretch 0, pokes 0 in every clip; 1.0: 16-57 %%)")
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    spec = S.load_spec(a.spec)
    d = {k: v["cm"] / 100 for k, v in spec["dims"].items()}
    bk = {k: (v / 100 if isinstance(v, (int, float)) else v) for k, v in spec["build"].items() if k.endswith("_cm")}
    lm = {k: v / 100 for k, v in spec["body"]["landmarks_cm"].items()}
    ref = Ref(json.loads(Path(a.ref).read_text(encoding="utf-8")), a.ref_mesh)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rep: dict = {"spec": a.spec, "dressed": a.dressed, "ref": a.ref}

    bpy.ops.wm.open_mainfile(filepath=a.dressed)
    arm = bpy.data.objects["CharacterArmature"]
    arm.data.pose_position = "REST"
    bpy.context.view_layer.update()
    body, top, gar = bpy.data.objects["axolotl_char"], bpy.data.objects["top"], bpy.data.objects["garment"]
    # G3k: her skin's weights under the straps from her whole skin, the part the dress removed under the cloth too: on
    # the kept skin alone the strap's back run at 123 cm took her shoulder's (the nearest kept skin 51 mm off, over it)
    # and stood 15-23 mm off her upper back in the runs
    whole = a.strap_skin_whole if a.strap_skin_whole is not None else spec["build"].get("strap_skin_whole", True)
    shirt_w = Weights(top)
    body_w = Weights(body, bpy.data.objects.get("body_removed")) if whole else Weights(body)
    rep["strap_skin_whole"] = bool(whole)

    # --- the bare ankle: her skin back under the raised hem ---------------------------------------------------
    lo_z, hi_z = (float(x) for x in a.ankle_restore.split(","))
    rem = bpy.data.objects.get("body_removed")
    if rem is not None:
        rbm = bmesh.new()
        rbm.from_mesh(rem.data)
        mw = rem.matrix_world
        keep = [f for f in rbm.faces if all(lo_z <= (mw @ v.co).z <= hi_z for v in f.verts)]
        rest = [f for f in rbm.faces if f not in set(keep)]
        dup = rem.copy()
        dup.data = rem.data.copy()
        bpy.context.scene.collection.objects.link(dup)
        dbm = rbm.copy()
        bmesh.ops.delete(dbm, geom=[f for f in dbm.faces if f.index not in {k.index for k in keep}], context="FACES")
        bmesh.ops.delete(dbm, geom=[v for v in dbm.verts if not v.link_faces], context="VERTS")
        dbm.to_mesh(dup.data)
        bmesh.ops.delete(rbm, geom=keep, context="FACES")
        bmesh.ops.delete(rbm, geom=[v for v in rbm.verts if not v.link_faces], context="VERTS")
        rbm.to_mesh(rem.data)
        n_before = len(body.data.vertices)
        with bpy.context.temp_override(active_object=body, object=body, selected_objects=[body, dup],
                                       selected_editable_objects=[body, dup]):
            bpy.ops.object.join()
        bbm = bmesh.new()
        bbm.from_mesh(body.data)
        band = [v for v in bbm.verts if lo_z - 0.01 <= v.co.z <= hi_z + 0.01]
        r = bmesh.ops.remove_doubles(bbm, verts=band, dist=0.0002)
        bbm.to_mesh(body.data)
        rep["ankle_restore"] = {"faces": len(keep), "body_verts": [n_before, len(body.data.vertices)],
                                "between_m": [lo_z, hi_z], "left_in_body_removed": len(rest)}
        del r

    # --- the trousers: the Meshy piece between the cuff and the rise cut -------------------------------------
    gnames = {g.index: g.name for g in gar.vertex_groups}
    tb = bmesh.new()
    tb.from_mesh(gar.data)
    dl = tb.verts.layers.deform.verify()
    tb.verts.ensure_lookup_table()
    parent = {v: v for v in tb.verts}

    def find(v):
        while parent[v] is not v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v
    for e in tb.edges:
        ra, rb = find(e.verts[0]), find(e.verts[1])
        if ra is not rb:
            parent[ra] = rb
    sizes = {}
    for v in tb.verts:
        sizes[find(v)] = sizes.get(find(v), 0) + 1
    main_root = max(sizes, key=sizes.get)
    bmesh.ops.delete(tb, geom=[v for v in tb.verts if find(v) is not main_root], context="VERTS")
    rep["trousers_source_verts"] = len(tb.verts)
    old = KDTree(len(tb.verts))
    old_w = []
    for i, v in enumerate(tb.verts):
        old.insert(v.co, i)
        old_w.append({gnames[g]: w for g, w in v[dl].items() if g in gnames and w > 1e-4})
    old.balance()
    geom = tb.verts[:] + tb.edges[:] + tb.faces[:]
    bmesh.ops.bisect_plane(tb, geom=geom, plane_co=(0, 0, a.rise_cut), plane_no=(0, 0, 1), clear_outer=True)
    geom = tb.verts[:] + tb.edges[:] + tb.faces[:]
    bmesh.ops.bisect_plane(tb, geom=geom, plane_co=(0, 0, a.leg_cut), plane_no=(0, 0, 1), clear_inner=True)
    B = Builder()
    vmap = {}
    for v in tb.verts:
        w = {gnames[g]: x for g, x in v[dl].items() if g in gnames and x > 1e-4}
        if not w:
            w = old_w[old.find(v.co)[1]]
        vmap[v] = B.vert(v.co, no_arms(w))   # d79: an arm weight leaked into the hips
    for f in tb.faces:
        B.face([vmap[v] for v in f.verts], 0)
    trousers_verts = set(vmap.values())

    # --- the waistband: a stiff ring ----------------------------------------------------------------------------
    bt, bbz = d["bib_top_z"], d["waistband_top_z"]
    wbz = bbz - d["waistband_h"]
    zc = (bbz + wbz) / 2
    fy, by = ref.front(zc, 0.05), ref.front(zc, 0.05, back=True)
    cy = (fy + by) / 2
    band_samples = []
    nth = 64
    ths = [-math.pi / 2 + 2 * math.pi * i / nth for i in range(nth)]
    rows = []
    for z in (wbz, wbz + d["waistband_h"] / 2, bbz):
        row = []
        for th in ths:
            r0 = ref.radius(z, th, cy)
            p = Vector((math.cos(th), math.sin(th), 0)) * (r0 + SHIRT + bk["band_ease_cm"]) + Vector((0, cy, z))
            q = Vector((math.cos(th), math.sin(th), 0)) * (r0 + SHIRT) + Vector((0, cy, z))
            row.append((p, q))
            band_samples.append(q)
        rows.append(row)
    w_band = shirt_w.mean(band_samples, keep=("Hips", "Spine", "Chest"))
    if a.band_bone:   # G3b: a blend of bones bends when they twist (Jog, Strafe: 2-8 % stretch); one bone is rigid
        w_band = {a.band_bone: 1.0}
    B.slab(rows, lambda p: w_band, 0, closed_u=True)
    rep["waistband"] = {"weights": w_band, "top_m": bbz, "bottom_m": wbz,
                        "front_w_m": max(r[0].x for r in rows[2]) - min(r[0].x for r in rows[2])}

    # --- the yoke: the trousers' cut loop extruded up inside the band --------------------------------------------
    loop = [v for v in trousers_verts if abs(v.co.z - a.rise_cut) < 1e-4 and any(e.is_boundary for e in v.link_edges)]
    loop_set = set(loop)
    edges = [e for e in B.bm.edges if e.is_boundary and all(v in loop_set for v in e.verts)]
    ztop = wbz + a.yoke_into_band
    col = {v: v for v in loop}
    cut_cy = (ref.front(a.rise_cut, 0.05) + ref.front(a.rise_cut, 0.05, back=True)) / 2
    base = {}
    for v in loop:
        th = math.atan2(v.co.y - cut_cy, v.co.x)
        r_cut = (Vector((v.co.x, v.co.y - cut_cy, 0))).length
        rb = ref.radius(a.rise_cut, th, cut_cy) or r_cut
        base[v] = (th, r_cut - rb, B.W[v])
    cur = edges
    yoke_n = yoke_lost = 0
    for k in range(1, a.yoke_rows + 1):
        t = k / a.yoke_rows
        s = smooth01(t)
        z = a.rise_cut + t * (ztop - a.rise_cut)
        zcy = (ref.front(z, 0.05) + ref.front(z, 0.05, back=True)) / 2
        res = bmesh.ops.extrude_edge_only(B.bm, edges=cur)
        new_v = [g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)]
        cur = [g for g in res["geom"] if isinstance(g, bmesh.types.BMEdge) and g.is_boundary]
        for nv in new_v:
            src = min((e.other_vert(nv) for e in nv.link_edges if e.other_vert(nv) in col),
                      key=lambda o: (o.co - nv.co).length, default=None)
            if src is None:
                yoke_lost += 1
                continue
            col[nv] = col[src]
            th, ease, w0 = base[col[nv]]
            rb = ref.radius(z, th, zcy)
            if rb is None:
                rb = ref.radius(a.rise_cut, th, cut_cy)
            r = rb + (1 - s) * ease + s * a.yoke_ease
            nv.co = Vector((math.cos(th) * r, zcy + math.sin(th) * r, z))
            B.W[nv] = mix(w0, w_band, s)
            yoke_n += 1
    rep["yoke"] = {"loop_verts": len(loop), "loop_edges": len(edges), "verts": yoke_n, "top_m": ztop,
                   "from_m": a.rise_cut}
    if yoke_lost:
        raise SystemExit(f"the yoke: {yoke_lost} new vertices with no column under them (no weights, no place)")

    # --- the lap (G3f, the manager's option (a)): the plates' lower edges go down over the band by plate_lap_cm, on
    # Chest whole, so a Chest-against-Spine twist slides them over the band, hidden; each plate vertex level with the
    # band (and over the plate's lowest plate_lap_blend_cm above it, eased off) stands plate_lap_clear_cm off the band
    # and the yoke under it (a ray from in front or behind meets the garment built so far: the band, then the yoke)
    lap = bk.get("plate_lap_cm", 0.0)
    lap_clr, lap_up = bk.get("plate_lap_clear_cm", 0.002), bk.get("plate_lap_blend_cm", 0.03)
    if a.lap_clear_cm is not None:
        lap_clr = a.lap_clear_cm / 100
    n_lap = max(1, int(round(lap / 0.01))) if lap > 0 else 0
    lap_zs = [bbz - lap + k * lap / n_lap for k in range(n_lap)]
    under = BVHTree.FromBMesh(B.bm)
    lap_moved = [0.0]

    def lap_y(x, y, z, front=True, hug=False):
        """The outer face's y at (x, z): pushed off the band (and the yoke) in front of it (behind it at the back).
        hug (G3g, the back): also drawn in onto it, so the lap lies on the band all round its turn (its lower corners
        stood off her side in the 3/4 views where the across curve passed behind the band)."""
        if lap <= 0 or z > bbz + lap_up:
            return y
        zq = min(z, bbz - 0.001)
        sg = 1 if front else -1
        hit = under.ray_cast(Vector((x, -sg * 1.0, zq)), Vector((0, sg, 0)), 2.0)[0]
        if hit is None:
            return y
        need = hit.y - sg * (a.plate + lap_clr)
        push = sg * (y - need) if hug else max(0.0, sg * (y - need))
        if z > bbz:
            push *= 1 - smooth01((z - bbz) / lap_up)
        lap_moved[0] = max(lap_moved[0], abs(push))
        return y - sg * push

    # --- the bib: lean B -----------------------------------------------------------------------------------------
    zs = lap_zs + [bbz + i * (bt - bbz) / 48 for i in range(49)]
    hwf = bk["body_half_w_cm"]["front"] / 100      # her front over |x| < this (garment_drawing measures the same)
    pts = []
    for z in zs[n_lap:]:
        # the drawing's lean B (garment_drawing.lines): her front over |x| < 11 cm + the shirt + the bust gap
        pts.append((z, ref.front(z, hwf) - SHIRT - d["bib_standoff_bust"]))
    pts[-1] = (bt, min(pts[-1][1], ref.front(bt, hwf) - SHIRT - d["bib_standoff_top"]))
    hull = envelope(pts, front=True)
    bib_y = lambda z: chain_y(hull, z)
    nb = 17
    rows = []
    bib_samples = []
    for z in zs:
        hw = d["bib_bottom_w"] / 2 + (d["bib_top_w"] - d["bib_bottom_w"]) / 2 * max(0.0, z - bbz) / (bt - bbz)
        row = []
        for i in range(nb):
            x = -hw + 2 * hw * i / (nb - 1)
            y = lap_y(x, bib_y(max(z, bbz)), z)
            row.append((Vector((x, y, z)), Vector((x, y + a.plate, z))))
            bib_samples.append(Vector((x, 0.0, z)))
        rows.append(row)
    if not n_lap:     # its foot on the band's top (no lap): just over it
        rows[0] = [(p + Vector((0, 0, 0.0002)), q + Vector((0, 0, 0.0002))) for p, q in rows[0]]
    bib_samples = [Vector((p.x, ref.front(p.z, 0.004) + 0.006, p.z)) for p in bib_samples[::5]]
    w_bib = shirt_w.mean(bib_samples, keep=TRUNK)
    if a.panel_bone:  # G3b: rigid, so flat in every clip (b02's blend bent 9-13 mm in Jog and Strafe)
        w_bib = {a.panel_bone: 1.0}
    seam = bk["seam_blend_cm"]

    def seam_w(w_top):
        """The plate's weights: the band's at the band's top, eased to w_top over the seam blend (G3d: on one bone
        a Spine-against-Chest twist opened the plates' lower corners off the band)."""
        return lambda p: w_top if seam <= 0 or p.z >= bbz + seam else mix(w_band, w_top, smooth01((p.z - bbz) / seam))
    plate_vs = set()
    for r_ in B.slab(rows, seam_w(w_bib), 0):
        plate_vs.update(v for row_ in r_ for v in row_)
    rep["lap"] = {"cm": round(lap * 100, 2), "rows": n_lap, "clear_cm": round(lap_clr * 100, 2),
                  "bib_pushed_mm": round(lap_moved[0] * 1000, 2)}
    rep["bib"] = {"weights": w_bib, "hull": [[round(z * 100, 2), round(y * 100, 2)] for z, y in hull],
                  "top_y_cm": round(bib_y(bt) * 100, 2), "band_y_cm": round(bib_y(bbz) * 100, 2)}

    # --- the pocket ------------------------------------------------------------------------------------------------
    pw, pt, pb = d["pocket_w"], d["pocket_top_z"], d["pocket_bottom_z"]
    rows = []
    for j in range(15):
        row = []
        for i in range(11):
            x = -pw / 2 + pw * i / 10
            zb = pb + 0.01 * abs(x) / (pw / 2)
            z = zb + (pt - zb) * j / 14
            y = bib_y(z)
            row.append((Vector((x, y - 0.0015, z)), Vector((x, y - 0.0003, z))))
        rows.append(row)
    B.slab(rows, lambda p: w_bib, 1)

    # --- the back panel: the drawing's shallow V -------------------------------------------------------------------
    kt = d["back_top_z"]
    # G3g: the back's own lap (on the band's bone it never slides, so it ends at the band's foot: a 5 cm lap hung
    # 1 cm under it like a second belt)
    blap = bk.get("back_lap_cm", lap)
    bn_lap = max(1, int(round(blap / 0.01))) if blap > 0 else 0
    blap_zs = [bbz - blap + k * blap / bn_lap for k in range(bn_lap)]
    corner = kt + 0.03                                   # garment_drawing.lines: the corners 3 cm over the V
    xs_in = d["strap_x"] - d["strap_w"] / 2
    zb_ = [bbz + i * (corner - bbz) / 48 for i in range(49)]
    pts = [(z, ref.front(z, bk["body_half_w_cm"]["back"] / 100, back=True) + SHIRT + d["back_standoff"]) for z in zb_]
    bhull = envelope(pts, front=False)
    back_y = lambda z: chain_y(bhull, z)
    nk = int(spec["build"].get("back_cols", 25))
    rows = []
    back_samples = []
    across = bool(spec["build"].get("back_follows_across", False))
    foot = 0.0 if bn_lap else 0.0002
    lap_moved[0] = 0.0
    for j in range(bn_lap + 25):
        v = (j - bn_lap) / 24
        row = []
        for i in range(nk):
            u = -1 + 2 * i / (nk - 1)
            xt = u * d["back_top_w"] / 2
            ax = abs(xt)
            top_z = kt + 0.03 * min(1.0, ax / xs_in)   # the drawing's shallow V
            z = blap_zs[j] if j < bn_lap else bbz + foot + v * (top_z - bbz - foot)
            hw = d["back_bottom_w"] / 2 + (d["back_top_w"] - d["back_bottom_w"]) / 2 * max(0.0, z - bbz) / (corner - bbz)
            x = u * hw
            y = back_y(max(z, bbz))
            if across:   # G3e: her back under this column (+ the shirt + the standoff), never behind the flat plate
                yb = ref.front(z, 0.01, back=True, x0=x)
                y = min(y, yb + SHIRT + d["back_standoff"]) if yb is not None else y
            row.append((Vector((x, y, z)), Vector((x, y - a.plate, z))))
            if j >= bn_lap and (j - bn_lap) % 4 == 0 and i % 4 == 0:
                back_samples.append(Vector((x, ref.front(z, 0.004, back=True) - 0.006, z)))
        rows.append(row)
    if across:   # one bend down each column and none inward across a row: the plate bridges her spine's hollow
        follow = spec["build"].get("back_column", "hull") == "follow"
        for i in range(nk):
            if follow:   # G3g: down each column her back smoothed (a running max over +-2 rows, then a mean over +-3),
                # never in front of her: the hull bridged her waist's hollow and stood the panel's sides 15-31 mm off
                ys = [rows[j][i][0].y for j in range(len(rows))]
                mx_ = [max(ys[max(0, j - 2):j + 3]) for j in range(len(ys))]
                sm_ = [sum(mx_[max(0, j - 3):j + 4]) / len(mx_[max(0, j - 3):j + 4]) for j in range(len(ys))]
                col_y = [max(y_, s_) for y_, s_ in zip(ys, sm_)]
            else:
                col_ = envelope([(rows[j][i][0].z, rows[j][i][0].y) for j in range(len(rows))], front=False)
            for j in range(len(rows)):
                p_ = rows[j][i][0]
                y = col_y[j] if follow else max(p_.y, chain_y(col_, p_.z))
                rows[j][i] = (Vector((p_.x, y, p_.z)), Vector((p_.x, y - a.plate, p_.z)))
        # G3f: across each row a smooth curve, not the convex hull's facets and its ridge at the spine (G3e's
        # close-ups): a quadratic in x fitted to the row, its coefficients smoothed over the neighbouring rows, then
        # lifted so it is nowhere in front of her back (+ the shirt + the standoff) under it
        rows = smooth_rows(rows, a.plate, int(spec["build"].get("back_fit_deg", 2)))
        rep["back_across"] = {"cols": nk, "profile": "quadratic per row, lifted"}
    hug = bool(spec["build"].get("back_lap_hug", False))
    rows = [[(Vector((p.x, lap_y(p.x, p.y, p.z, front=False, hug=hug), p.z)),
              Vector((p.x, lap_y(p.x, p.y, p.z, front=False, hug=hug) - a.plate, p.z))) for p, _q in row] for row in rows]
    # G3g: how far the panel's inner face stands off her shirt at its side edges (the 3/4 views' corners), per height
    eg = []
    for row in rows[bn_lap::4]:
        for p, q in (row[0], row[-1]):
            yb = ref.front(p.z, 0.004, back=True, x0=p.x)
            if yb is not None:
                eg.append([round(p.z * 100, 1), round(p.x * 100, 1), round((q.y - yb - SHIRT) * 1000, 1)])
    rep["back_edge_gap_mm"] = eg
    rep["lap"]["back_pushed_mm"] = round(lap_moved[0] * 1000, 2)
    rep["lap"]["back_cm"], rep["lap"]["back_rows"] = round(blap * 100, 2), bn_lap
    w_back = shirt_w.mean(back_samples, keep=TRUNK)
    if a.panel_bone:
        w_back = {a.panel_bone: 1.0}
    band_share = spec["build"].get("back_band_share", 0.0) if a.back_band_share is None else a.back_band_share
    if band_share > 0:   # G3f: one blend for the whole panel (every vertex the same matrix: still flat), so its lap
        w_back = mix(w_back, w_band, band_share)   # rises less over the band as she bends forward (h1 on Chest: -39 mm)
    rep["back_band_share"] = band_share
    # G3l: the sliding join. The panel's top takes cc of the bib's weights (Chest), eased in over fade cm under its
    # corners (0: the whole panel, one blend, still rigid), and the straps' back ends over it take the panel's weights
    # at their height: on Chest over the panel's Spine they hovered 16-22 mm off it (G3k), joined on Spine they stretched
    cc = a.back_corner_chest if a.back_corner_chest is not None else spec["build"].get("back_corner_chest", 0.0)
    cf = (a.back_corner_fade_cm if a.back_corner_fade_cm is not None else spec["build"].get("back_corner_fade_cm", 0.0)) / 100

    def w_panel(z):
        if cc <= 0:
            return w_back
        t = 1.0 if cf <= 0 else smooth01((z - (corner - cf)) / cf)
        return norm(mix(w_back, w_bib, cc * t)) if t > 0 else w_back
    sw_back = seam_w(w_back)

    def w_back_at(p):
        if cc <= 0:
            return sw_back(p)
        t = 1.0 if cf <= 0 else smooth01((p.z - (corner - cf)) / cf)
        return norm(mix(sw_back(p), w_bib, cc * t)) if t > 0 else sw_back(p)
    for r_ in B.slab(rows, w_back_at, 0):
        plate_vs.update(v for row_ in r_ for v in row_)
    rep["back_corner"] = {"chest_share": cc, "fade_cm": round(cf * 100, 2),
                          "corner_weights": {k: round(v, 3) for k, v in w_panel(corner).items()}}
    rep["back_panel"] = {"weights": w_back, "hull": [[round(z * 100, 2), round(y * 100, 2)] for z, y in bhull],
                         "corner_m": corner}

    # --- the straps: ribbons laid by rays over the plates and her shirt --------------------------------------------
    B.bm.faces.ensure_lookup_table()
    B.bm.verts.ensure_lookup_table()
    plates = BVHTree.FromBMesh(B.bm)
    tm = top.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    tops = BVHTree.FromPolygons([top.matrix_world @ v.co for v in tm.vertices], [tuple(p.vertices) for p in tm.polygons])
    rep["straps"] = {}
    strap_vs = set()
    z0, y0 = bk["strap_ray_origin_cm"]["z"] / 100, bk["strap_ray_origin_cm"]["y"] / 100
    far = 0.4
    phis = [math.radians(-4 + i * (178 + 4) / 72) for i in range(73)]
    for sd in (1, -1):
        xc = sd * d["strap_x"]
        xs = [xc + d["strap_w"] * (k / 4 - 0.5) for k in range(5)]
        dirs = [Vector((0, -math.cos(p), math.sin(p))) for p in phis]
        radii = []
        for x in xs:
            rr = []
            for dv in dirs:
                # outward from inside her chest: every surface the ray crosses, then the outermost of the first
                # layer (skin, shirt, plate within 3 cm of each other); a ray in from outside met her head (b02)
                c = Vector((x, y0, z0))
                ds = []
                for tree in (plates, tops, ref.bvh):
                    t0 = 0.0
                    while t0 < far:
                        h = tree.ray_cast(c + dv * t0, dv, far - t0)[0]
                        if h is None:
                            break
                        t = (h - c).length
                        ds.append(t)
                        t0 = t + 1e-4
                ds.sort()
                r_ = None
                for t in ds:
                    if r_ is None or t - r_ < 0.03:
                        r_ = t
                    else:
                        break
                rr.append(r_)
            radii.append(rr)
        prof = [max(r[i] for r in radii if r[i] is not None) for i in range(len(phis))]
        # bridge the step at the bib's top edge: a running maximum then a mean, never under the surface
        mx = [max(prof[max(0, i - 3):i + 4]) for i in range(len(prof))]
        sm = [sum(mx[max(0, i - 2):i + 3]) / len(mx[max(0, i - 2):i + 3]) for i in range(len(mx))]
        prof = [max(p, s) for p, s in zip(prof, sm)]
        # G3g: each row tilted across to her shoulder's slope, not level at its highest column: a line in x through
        # the columns' own (smoothed) radii, lifted onto the highest; level, the strap's outer edge stood off her
        # shoulder where it crosses to the front and a slit showed between its inner edge and the shirt by her neck
        tilt = bool(spec["build"].get("strap_tilt", False))
        col_r = []
        for rr in radii:
            c_ = [r if r is not None else p for r, p in zip(rr, prof)]
            m_ = [max(c_[max(0, i - 3):i + 4]) for i in range(len(c_))]
            col_r.append([sum(m_[max(0, i - 2):i + 3]) / len(m_[max(0, i - 2):i + 3]) for i in range(len(m_))])
        ks = [k / 4 - 0.5 for k in range(5)]
        row_r = []
        for i in range(len(phis)):
            if not tilt:
                row_r.append([prof[i]] * 5)
                continue
            rs = [max(col_r[k][i], radii[k][i] or 0.0) for k in range(5)]
            mr = sum(rs) / 5
            b_ = sum(k * (r - mr) for k, r in zip(ks, rs)) / sum(k * k for k in ks)
            ln = [mr + b_ * k for k in ks]
            lift = max(r - l for r, l in zip(rs, ln))
            row_r.append([l + lift for l in ln])
        sh_pt = Vector((xc, y0, z0)) + dirs[len(dirs) // 2] * prof[len(dirs) // 2]
        w_sh = no_arms(shirt_w.at(sh_pt))
        if a.strap_sh_share < 1.0:
            w_sh = mix({a.panel_bone or "UpperChest": 1.0}, w_sh, a.strap_sh_share)
        # the spec: the straps' outer edges flush with the bib's top corners (bib_top_w / 2 - strap_w / 2 on the bib),
        # at strap_x from her collarbone up: eased between the bib's top and her collarbone
        x_bib = sd * (d["bib_top_w"] / 2 - d["strap_w"] / 2)
        # G3h: the strap's inner face off the shirt (0.5 mm let the shirt through as her shoulder moved), its 1.7 mm kept
        inner = (a.strap_inner_mm if a.strap_inner_mm is not None else spec["build"].get("strap_inner_mm", 0.5)) / 1000
        rows = []
        for i, dv in enumerate(dirs):
            c = Vector((0, y0, z0))
            zr = (c + dv * prof[i]).z
            dx = 0.0 if phis[i] > math.pi / 2 else (x_bib - xc) * (1 - smooth01((zr - bt) / (lm["collarbone"] - bt)))
            row = [(c + Vector((x + dx, 0, 0)) + dv * (row_r[i][k] + inner + 0.0017), c + Vector((x + dx, 0, 0)) + dv * (row_r[i][k] + inner))
                   for k, x in enumerate(xs)]
            rows.append(row)
        pz = [(Vector((0, y0, z0)) + dv * prof[i]) for i, dv in enumerate(dirs)]
        i_front = max(i for i, p in enumerate(pz) if phis[i] < math.pi / 2 and p.z <= bt)
        i_back = min(i for i, p in enumerate(pz) if phis[i] > math.pi / 2 and p.z <= corner)
        i_mid = len(dirs) // 2

        # G3h: the straps' back rows on the bib's weights, so the whole strap rides one bone but its top: on the back
        # panel's (Spine since G3g) it spanned Spine to Chest over her shoulder and stretched 5.8-95 % beyond her skin
        sboc = a.strap_back_on_chest
        if sboc is None:
            sboc = spec["build"].get("strap_back_on_chest", False)
        # G3k: the back ends join the back panel they lie on (its weights, Spine), eased from her skin's over join_cm
        # below the skin rows: on Chest over the panel's Spine they stood 17-23 mm off it in the runs (44 mm off her)
        join = a.strap_back_join_cm if a.strap_back_join_cm is not None else spec["build"].get("strap_back_join_cm", 0.0)
        w_sb = w_back if join > 0 else (w_bib if sboc else w_back)
        if cc > 0 and join <= 0:   # G3l: the back ends ride the panel under them (its weights at their height)
            w_sb = w_panel(corner)

        def w_of_row(i):
            if i <= i_front:
                return w_bib
            if i >= i_back:
                return w_panel(pz[i].z) if (cc > 0 and join <= 0) else w_sb
            if i <= i_mid:
                return mix(w_bib, w_sh, smooth01((i - i_front) / (i_mid - i_front)))
            return mix(w_sh, w_sb, smooth01((i - i_mid) / (i_back - i_mid)))
        row_w = [w_of_row(i) for i in range(len(rows))]
        # G3e: the strap's top over her trapezius follows her shoulder (on Chest alone it arched off it in Jog): over
        # top_cm of arc round its highest point a smooth gradient from the row's weights to her shoulder's there
        i_top = max(range(len(pz)), key=lambda i: pz[i].z)
        arc = [0.0]
        for i in range(1, len(pz)):
            arc.append(arc[-1] + (pz[i] - pz[i - 1]).length)
        top_cm = a.strap_top_cm if a.strap_top_cm is not None else spec["build"].get("strap_top_cm", 0.0)
        top_pt = pz[i_top] + Vector((xc, 0, 0))   # pz runs at x = 0: the strap's own top is at x = xc
        w_top = no_arms(shirt_w.at(top_pt))
        n_top = 0
        # G3i: behind its top the strap follows her skin under each row over back_cm of arc (on Chest it stood 30-50 mm
        # off her upper back by the neck as she leaned in the runs, a flap over her shoulder seen from the front)
        back_cm = spec["build"].get("strap_top_back_cm", 0.0)
        n_back = 0
        if top_cm > 0 and w_top:
            half = top_cm / 200
            for i in range(i_front + 1, i_back):
                t = 1 - abs(arc[i] - arc[i_top]) / half
                if back_cm > 0 and i > i_top:
                    tb = 1 - (arc[i] - arc[i_top]) / (back_cm / 100)
                    w_row = no_arms(shirt_w.at(pz[i] + Vector((xc, 0, 0))))
                    if tb > 0 and w_row:
                        row_w[i] = norm(mix(row_w[i], w_row, a.strap_top_share * smooth01(tb)))
                        n_back += 1
                        continue
                if t > 0:
                    row_w[i] = norm(mix(row_w[i], w_top, a.strap_top_share * smooth01(t)))
                    n_top += 1
        # G3j: over her shoulder (the rows at or over skin_z, front top to back top) every strap vertex takes her skin's
        # weights under it, eased back to the row's own (Chest) over blend_cm of arc on the front run to the bib and on
        # the back run (on Chest the front-top rows let her shoulder skin 20-40 mm through the shirt, the back-top
        # rows stood 27-51 mm off her back by the neck: a flap); her Neck and Head never (G3i's strap_top_back_cm
        # took them: 7-64 % beyond her skin)
        skin_z = a.strap_skin_z_cm if a.strap_skin_z_cm is not None else spec["build"].get("strap_skin_z_cm", 0.0)
        skin_bl = a.strap_skin_blend_cm if a.strap_skin_blend_cm is not None else spec["build"].get("strap_skin_blend_cm", 4.0)
        drop = a.strap_skin_drop.split(",") if a.strap_skin_drop is not None else             spec["build"].get("strap_skin_drop", ["Neck", "Head", "Jaw", "Eye", "Gill"])
        drop = [w for w in drop if w]
        share = [0.0] * len(rows)
        core = [i for i in range(i_front + 1, i_back) if skin_z > 0 and pz[i].z >= skin_z / 100]
        if core:
            i0, i1 = min(core), max(core)
            for i in range(i_front + 1, len(rows) if join > 0 else i_back):
                gap = arc[i0] - arc[i] if i < i0 else (arc[i] - arc[i1] if i > i1 else 0.0)
                bl = join if (join > 0 and i > i1) else skin_bl
                share[i] = smooth01(1 - gap / (bl / 100)) if bl > 0 else float(gap == 0.0)

        def skin_at(q):
            acc = {}
            for co, idx, dist in body_w.kd.find_n(q, 6):
                for k, v in body_w.w[idx].items():
                    if not any(x in k for x in drop):
                        acc[k] = acc.get(k, 0.0) + v / max(dist, 1e-4)
            return norm(acc)
        lookup = {}
        top_skin = None
        for i, row in enumerate(rows):
            for p, q in row:
                w = row_w[i]
                if share[i] > 0:
                    ws = skin_at(q)
                    w = norm(mix(w, ws, share[i])) if ws else w
                    if i == i_top and top_skin is None:
                        top_skin = ws
                lookup[(round(p.x, 6), round(p.y, 6), round(p.z, 6))] = w
                lookup[(round(q.x, 6), round(q.y, 6), round(q.z, 6))] = w
        tr = [[(r[k][0], r[k][1]) for k in range(5)] for r in rows]
        so, si = B.slab(tr, lambda p: lookup[(round(p.x, 6), round(p.y, 6), round(p.z, 6))], 0)
        strap_vs.update(v for r_ in so + si for v in r_)
        rep["straps"]["left" if sd > 0 else "right"] = {
            "front_end_z_m": round(pz[0].z, 4), "back_end_z_m": round(pz[-1].z, 4), "shoulder_weights": w_sh,
            "bib_rows": i_front + 1, "back_rows": len(rows) - i_back, "back_on_chest": bool(sboc),
            "inner_mm": round(inner * 1000, 2),
            "top_back": {"cm": back_cm, "rows": n_back, "rows_to_back": i_back - i_top},
            "back_join_cm": join, "back_weights": {k: round(v, 3) for k, v in w_sb.items()},
            "skin": {"z_cm": skin_z, "blend_cm": skin_bl, "drop": drop, "core_rows": len(core),
                     "blend_rows": sum(1 for x in share if 0 < x < 1),
                     "core_z_cm": [round(pz[min(core)].z * 100, 2), round(pz[max(core)].z * 100, 2)] if core else None,
                     "top_weights": {k: round(v, 3) for k, v in (top_skin or {}).items()}},
            "top": {"cm": top_cm, "share": a.strap_top_share, "rows": n_top, "weights": w_top,
                    "at_cm": [round(c * 100, 2) for c in top_pt]}}
        # the buckle: a ring round the strap at the bib's top edge and its button on the strap
        yb = bib_y(d["buckle_z"]) - 0.0022 - 0.0005
        B.disc((x_bib, yb, d["buckle_z"]), (0, 1, 0), d["buckle_d"], 0.003, w_bib, 2)
        yr = bib_y(bt - 0.006) - 0.0025
        ring = bk["buckle_ring_cm"]
        hw, hh, bar = d["strap_w"] / 2 + ring["pad"] / 100, ring["half_h"] / 100, ring["bar"] / 100
        quad = lambda x0, x1, z0_, z1_: [(x0, z0_), (x1, z0_), (x1, z1_), (x0, z1_)]
        outer = quad(x_bib - hw, x_bib + hw, bt - 0.006 - hh, bt - 0.006 + hh)
        inner = quad(x_bib - hw + bar, x_bib + hw - bar, bt - 0.006 - hh + bar, bt - 0.006 + hh - bar)
        ov = [[B.vert((x, yr - dy, z), w_bib) for x, z in outer] for dy in (0.0, 0.002)]
        iv = [[B.vert((x, yr - dy, z), w_bib) for x, z in inner] for dy in (0.0, 0.002)]
        for k in range(4):
            m = (k + 1) % 4
            B.face([ov[1][k], ov[1][m], iv[1][m], iv[1][k]], 2)
            B.face([ov[0][k], iv[0][k], iv[0][m], ov[0][m]], 2)
            B.face([ov[0][k], ov[0][m], ov[1][m], ov[1][k]], 2)
            B.face([iv[0][k], iv[1][k], iv[1][m], iv[0][m]], 2)
    tm = None

    # --- the side buttons on the band, at its ends (garment_drawing.lines: ww/2 - 1.4) ----------------------------
    for sd in (1, -1):
        x = sd * (d["waistband_w"] / 2 - 0.014)
        bvh = BVHTree.FromBMesh(B.bm)
        hit = bvh.ray_cast(Vector((x, -1.0, d["side_button_z"])), Vector((0, 1, 0)), 2.0)
        y = hit[0].y if hit[0] is not None else ref.front(d["side_button_z"], 0.01) - 0.008
        nrm = hit[1] if hit[0] is not None else Vector((0, -1, 0))
        B.disc(Vector((x, y, d["side_button_z"])) + nrm * 0.0005, -nrm, d["side_button_d"], 0.003, w_band, 2)

    # --- the turn-ups: rigid rings on the lower legs ------------------------------------------------------------
    hem, th_ = d["hem_z"], d["turnup_h"]
    rep["turnups"] = {}
    for sd, side in ((1, "Left"), (-1, "Right")):
        sl = [v.co for v in trousers_verts if v.is_valid and sd * v.co.x > 0.02 and a.leg_cut <= v.co.z <= a.leg_cut + 0.02]
        cx = (max(p.x for p in sl) + min(p.x for p in sl)) / 2
        cyl = (max(p.y for p in sl) + min(p.y for p in sl)) / 2
        ax = (max(p.x for p in sl) - min(p.x for p in sl)) / 2
        ay = (max(p.y for p in sl) - min(p.y for p in sl)) / 2
        ox = d["leg_hem_w"] / 2
        oy = max(ay + bk["turnup_wall_cm"], ay + (ox - ax))
        w_cuff = {f"{side}LowerLeg": 1.0}
        rows = []
        n = 32
        for z in (hem, hem + th_ * 0.5, hem + th_):
            row = []
            for i in range(n):
                t = 2 * math.pi * i / n
                c, s = math.cos(t), math.sin(t)
                wall = bk["turnup_wall_cm"]
                row.append((Vector((cx + ox * c, cyl + oy * s, z)), Vector((cx + (ox - wall) * c, cyl + (oy - wall) * s, z))))
            rows.append(row)
        B.slab(rows, lambda p: w_cuff, 0, closed_u=True)
        rep["turnups"][side] = {"centre_cm": [round(cx * 100, 2), round(cyl * 100, 2)], "leg_half_cm": [round(ax * 100, 2), round(ay * 100, 2)],
                                "ring_half_cm": [round(ox * 100, 2), round(oy * 100, 2)]}

    bmesh.ops.recalc_face_normals(B.bm, faces=B.bm.faces[:])
    if not a.no_shirt_follow:
        # G3h: the shirt under the straps takes their weights too (on its own, with her upper arms' share, it came 14-49 mm
        # through the straps' fronts at her collarbone in every clip: poke.json's top_under_panels_tracked)
        sfs = a.shirt_follow_straps
        if sfs is None:
            sfs = spec["build"].get("shirt_follow_straps", False)
        # G3i: a strap gives its weights only to the shirt directly under it, eased back over a short fade, never to
        # the collar's band (G3h: the collar and the front between the straps took them whole, her neck came through)
        keep = collar_band(top, bk.get("collar_keep_cm", 0.0)) if sfs else set()
        rep["shirt_follow"] = shirt_follow(top, B, set() if sfs else strap_vs, bk.get("shirt_follow_fade_cm", 0.03),
                                           near=bk.get("shirt_follow_near_cm", 0.015), low_z=bbz, low_skip=plate_vs,
                                           strap_vs=strap_vs if sfs else frozenset(),
                                           strap_reach=bk.get("strap_follow_reach_cm", 0.0),
                                           strap_fade=bk.get("strap_follow_fade_cm", 0.0), keep=keep)
        rep["shirt_trim"] = shirt_trim(top, bk.get("shirt_trim_z_cm", 0.0))   # then its new hem drawn in
        rep["shirt_hem"] = shirt_hem_in(top, bk.get("shirt_hem_in_cm", 0.0), bk.get("shirt_hem_h_cm", 0.015))
    for f in B.bm.faces:   # G3f: every cloth face smooth, the rims kept sharp by angle (flat faces striped the curves)
        f.smooth = f.material_index != 2
    me = bpy.data.meshes.new("garment")
    B.bm.verts.index_update()
    vlist = list(B.bm.verts)
    B.bm.to_mesh(me)
    me.set_sharp_from_angle(angle=math.radians(float(spec["build"].get("sharp_deg", 40))))
    mats = []
    for name, col_ in (("denim_plain", (0.20, 0.33, 0.55, 1)), ("pocket_denim", (0.18, 0.30, 0.50, 1)),
                       ("hardware_metal", (0.55, 0.45, 0.28, 1))):
        m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        m.use_nodes = True
        m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = col_
        m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.85 if name != "hardware_metal" else 0.4
        mats.append(m)
    for m in mats:
        me.materials.append(m)
    old_me = gar.data
    gar.data = me
    gar.vertex_groups.clear()
    groups = {}
    for i, v in enumerate(vlist):
        for g, w in B.W.get(v, {}).items():
            if g not in groups:
                groups[g] = gar.vertex_groups.new(name=g)
            groups[g].add([i], w, "REPLACE")
    bpy.data.meshes.remove(old_me)
    missing = [i for i, v in enumerate(vlist) if not B.W.get(v)]
    rep["garment"] = {"verts": len(me.vertices), "tris": sum(len(p.vertices) - 2 for p in me.polygons),
                      "groups": sorted(groups), "verts_without_weights": len(missing)}
    if missing:   # no_arms() of an arm-only weight is {}: a vertex no bone moves
        raise SystemExit(f"the garment: {len(missing)} vertices without weights (first {missing[:5]})")
    arm.data.pose_position = "POSE"
    bpy.context.view_layer.update()
    blend = out / "axolotl_char.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    h = hashlib.sha256(blend.read_bytes()).hexdigest()
    rep["blend"], rep["blend_sha256"] = str(blend), h
    import alien_loco
    alien_loco._export(arm, out / "axolotl_char.glb")
    (out / "build.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    print("DUNGAREES_BUILD " + json.dumps({k: rep[k] for k in ("garment", "waistband", "yoke")}, default=str))


if __name__ == "__main__":
    main()
