"""The dungarees' upper body as our own clean pieces, inside Blender (art #196, clothes step 2, C1f): clothes_dress.py
--shell calls cut_garment, shell and straps in that order (the maths: clothes_shell.py; the route: docs/clothes.md).

- cut_garment: the Meshy garment keeps the trousers below the waistband, the bib and the back panel; their edges are
  cut by planes (bmesh bisect), so they are straight, not a row of whole faces.
- shell: the striped top, a copy of the body's torso and arm faces moved out along their normals, cut at the crew
  neck, the wrists and the hem, a rolled lip at the collar and cuffs, the body's own weights; its stripes and a soft
  cotton normal map are made here, darkened by an ambient-occlusion bake (Cycles) where it fits.
- straps: two strips about 3.5 cm wide from the bib's top corners over the shoulders down to the back panel's V,
  over the shell and the bib, weighted like the body under them; their UVs on a free patch of the garment's texture,
  a copy of its plain denim with two dashed stitch lines in the sketch's orange; at each front end a bronze buckle
  ring and a button (real geometry, a metal material, weighted with the strap), the Meshy bib under the
  strap's front goes (its broken buckle hardware), the hardware's faces beside it take plain denim.
- The shell's faces hidden under the bib and the back panel go (five rays each), and the rest is decimated away from
  the openings (the weights then re-read from the body under each vertex), so the dressed character keeps its budget.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.interpolate import poly_3d_calc
from mathutils.kdtree import KDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clothes_fit_geom as F  # noqa: E402
import clothes_shell as H  # noqa: E402
import clothes_strap as S  # noqa: E402
import clothes_texture as T  # noqa: E402

ALLOWED = ("Hips", "Spine", "Chest", "UpperChest", "Neck", "LeftShoulder", "RightShoulder", "LeftUpperArm",
           "RightUpperArm", "LowerArm", "UpperLeg")
IMG_W, IMG_H = 2048, 1024
ISLANDS = {H.TORSO: (0.01, 0.56), H.LEFT: (0.59, 0.19), H.RIGHT: (0.80, 0.19)}
V0 = {H.TORSO: 0.06, H.LEFT: 0.01, H.RIGHT: 0.01}


def say(*a) -> None:
    print("CLOTHES_DRESS", *a, flush=True)


def floats(s: str) -> list[float]:
    return [float(v) for v in s.split(",")]


def tree_of(objs) -> BVHTree:
    co, polys, off = [], [], 0
    for o in objs:
        co += [tuple(o.matrix_world @ v.co) for v in o.data.vertices]
        polys += [[i + off for i in p.vertices] for p in o.data.polygons]
        off += len(o.data.vertices)
    return BVHTree.FromPolygons(co, polys)


def _bisect(bm, mw, pick, co, no, outer: bool | None = True, dist: float = 1e-5) -> int:
    """Cuts the faces pick(world centre) by the world plane (co, no), then deletes those of them whose centres lie
    on its positive side (outer), its negative side (False) or none (None: the cut alone); returns how many went.
    The cut itself clears nothing (C1k): bisect_plane's clear kills vertices, and with them every face round them,
    picked or not (clothes_shell.cleared)."""
    inv = mw.inverted()
    tag = bm.faces.layers.int.new("c1k_pick")  # first: a new layer leaves earlier face references stale
    faces = [f for f in bm.faces if pick(mw @ f.calc_center_median())]
    if not faces:
        bm.faces.layers.int.remove(tag)
        return 0
    for f in faces:
        f[tag] = 1  # the halves of a cut face keep it
    edges = {e for f in faces for e in f.edges}
    verts = {v for f in faces for v in f.verts}
    nl = (mw.to_3x3().transposed() @ Vector(no)).normalized()
    bmesh.ops.bisect_plane(bm, geom=list(verts) + list(edges) + faces, plane_co=inv @ Vector(co), plane_no=nl,
                           dist=dist)
    gone = []
    if outer is not None:
        cand = [f for f in bm.faces if f[tag]]
        sides = [H.plane_side(tuple(mw @ f.calc_center_median()), co, no) for f in cand]
        gone = [f for f, g in zip(cand, H.cleared(sides, [True] * len(cand), outer)) if g]
        bmesh.ops.delete(bm, geom=gone, context="FACES")
    bm.faces.layers.int.remove(tag)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    return len(gone)


def cut_garment(gar, args) -> dict:
    z_w = args.waist
    bib_hw, bib_top = floats(args.bib)
    back_y, z_apex, hw_w, hw_a = floats(args.back)
    mw = gar.matrix_world
    me = gar.data
    bm = bmesh.new()
    bm.from_mesh(me)
    n0 = len(bm.faces)
    # the waist first, all round and without clearing: then the bib's and the back V's planes act only above it, so
    # beside them the trousers' top edge is the straight cut at z_w, not the bottoms of faces crossing it
    _bisect(bm, mw, lambda c: True, (0, 0, z_w), (0, 0, 1), outer=None)
    front = lambda c: c.y < 0 and c.z > z_w
    back = lambda c: c.y > back_y and c.z > z_w
    # the panels' planes cut only (C1k): a clearing cut killed the waist line's vertices beside the panels and with
    # them the trousers' faces under it (the sawtooth); keep_face below is the only deletion, by face centres
    _bisect(bm, mw, front, (bib_hw, 0, 0), (1, 0, 0), outer=None)
    _bisect(bm, mw, front, (-bib_hw, 0, 0), (-1, 0, 0), outer=None)
    _bisect(bm, mw, front, (0, 0, bib_top), (0, 0, 1), outer=None)
    dz, dx = z_apex - z_w, hw_a - hw_w
    ln = math.hypot(dz, dx)
    for sgn in (1, -1):
        _bisect(bm, mw, back, (sgn * hw_w, 0, z_w), (sgn * dz / ln, 0, -dx / ln), outer=None)
    _bisect(bm, mw, back, (0, 0, z_apex), (0, 0, 1), outer=None)
    bm.faces.ensure_lookup_table()
    e = 1e-5  # the cuts' own tolerance: a face outside a plane has its centre beyond it
    gone = [f for f in bm.faces if not H.keep_face(*(mw @ f.calc_center_median()), z_w, bib_hw + e,
                                                    bib_top + e, back_y, z_apex + e, hw_w + e, hw_a + e)]
    bmesh.ops.delete(bm, geom=gone, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    band_h, lap = floats(args.waistband)
    n_band = 0
    if band_h > 0:  # the Meshy band beside the bib goes (its layered side opening: shards); waistband() rebuilds it
        hb = band_h - lap
        _bisect(bm, mw, lambda c: H.in_waist_band(c.x, c.y, c.z, z_w, hb + 0.03, bib_hw, back_y, hw_w),
                (0, 0, z_w - hb), (0, 0, 1), outer=None)
        # its ends straight up and down at the bib's and the back panel's edges
        low = lambda c: z_w - hb - 0.03 < c.z <= z_w
        for sgn in (1, -1):
            _bisect(bm, mw, lambda c: low(c) and c.y < 0, (sgn * bib_hw, 0, 0), (sgn, 0, 0), outer=None)
            _bisect(bm, mw, lambda c: low(c) and c.y > back_y, (sgn * hw_w, 0, 0), (sgn, 0, 0), outer=None)
        band = [f for f in bm.faces if H.in_waist_band(*(mw @ f.calc_center_median()), z_w, hb, bib_hw, back_y, hw_w)]
        # and the panels' edge flaps beside it that face the body (Meshy's layered side opening, the dark shards)
        nm3 = mw.to_3x3().inverted().transposed()
        for f in bm.faces:
            c = mw @ f.calc_center_median()
            n = (nm3 @ f.normal).normalized()
            if H.inward_flap(c.x, c.y, c.z, n.x, n.y, z_w - hb, z_w + args.band_flaps, args.band_axis_y,
                             bib_hw, back_y, H.back_halfwidth(c.z, z_w, z_apex, hw_w, hw_a), 0.025):
                band.append(f)
        band = list(set(band))
        n_band = len(band)
        bmesh.ops.delete(bm, geom=band, context="FACES")
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    n_peel = peel_edges(bm, gar, args, z_w - (band_h - lap if band_h > 0 else 0.0) - 0.01, bib_hw, bib_top, back_y,
                        z_apex, hw_w, hw_a)
    n1 = len(bm.faces)
    # the trousers' top edge beside the panels (C1k): its open edge's lowest and highest vertex, 1 cm and more off
    # the panels' side zones; a straight cut reads one height (z_w less the band's removal)
    zs = []
    for v in bm.verts:
        if not v.is_boundary:
            continue
        p = mw @ v.co
        if not z_w - 0.1 < p.z < z_w + 1e-4:
            continue
        hw = H.back_halfwidth(min(p.z, z_w), z_w, z_apex, hw_w, hw_a)
        if (p.y < 0 and abs(abs(p.x) - bib_hw) < 0.01 + args.edge_zone) or (
                p.y > back_y and abs(abs(p.x) - hw) < 0.01 + args.edge_zone):
            continue
        zs.append(p.z)
    bm.to_mesh(me)
    bm.free()
    me.update()
    rep = {"faces_before": n0, "faces_after": n1, "band_faces_removed": n_band, "edge_peeled": n_peel, "waist": z_w,
           "bib": [bib_hw, bib_top], "back": floats(args.back),
           "waist_edge_z_min_max": [round(min(zs), 4), round(max(zs), 4)] if zs else None,
           "waist_edge_verts": len(zs)}
    say("garment cut", rep)
    return rep


def fill_holes(gar, args) -> dict:
    """E1g: the garment's small holes under the waist (closed open-edge loops of at most args.fill_holes edges, Meshy's
    gaps round the front pockets: dark divots where the removed body left nothing behind) are filled; each new face's
    corners take their vertex's UV from the cloth round it, so the fill shows the denim next to it. E1i2: with
    args.fill_holes_above, up to that height over the waist (the chameleon's bib pocket: white holes in Jog where the
    top and the body under the bib are removed)."""
    mw = gar.matrix_world
    bm = bmesh.new()
    bm.from_mesh(gar.data)
    # loose bits first (a lone triangle 45 mm off A's hip, d18): islands of at most 4 faces under the waist go; their
    # own edges would read as holes below
    comp, bits = {}, []
    for f in bm.faces:
        if f in comp:
            continue
        st, grp = [f], [f]
        comp[f] = True
        while st:  # the whole component: a partial flood would leave pieces of a large one looking small
            g = st.pop()
            for e in g.edges:
                for h in e.link_faces:
                    if h not in comp:
                        comp[h] = True
                        st.append(h)
                        grp.append(h)
        if len(grp) <= 4 and all((mw @ g.calc_center_median()).z < args.waist for g in grp):
            bits.extend(grp)
    if bits:
        bmesh.ops.delete(bm, geom=bits, context="FACES")
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    seen, holes = set(), []
    for e in bm.edges:
        if e in seen or not e.is_boundary:
            continue
        st, grp = [e], []
        seen.add(e)
        while st:
            x = st.pop()
            grp.append(x)
            for v in x.verts:
                for y in v.link_edges:
                    if y.is_boundary and y not in seen:
                        seen.add(y)
                        st.append(y)
        vs = {v for x in grp for v in x.verts}
        closed = all(sum(1 for y in v.link_edges if y.is_boundary) == 2 for v in vs) and len(vs) == len(grp)
        above = getattr(args, "fill_holes_above", None)
        z_cap = args.waist - 0.005 if above is None else args.waist + above  # E1i2: the bib pocket's holes too
        if closed and len(grp) <= args.fill_holes and max((mw @ v.co).z for v in vs) < z_cap:
            holes.append(grp)
    up = [[round(c, 3) for c in sum((mw @ v.co for x in g for v in x.verts), Vector()) / (2 * len(g))]
          for g in holes if max((mw @ v.co).z for x in g for v in x.verts) >= args.waist - 0.005]
    uvl = bm.loops.layers.uv.active
    vuv = {}
    if uvl is not None:
        for g in holes:
            for x in g:
                for v in x.verts:
                    ls = [l[uvl].uv.copy() for l in v.link_loops]
                    vuv[v] = sum(ls, Vector((0.0, 0.0))) / len(ls) if ls else Vector((0.0, 0.0))
    new = bmesh.ops.holes_fill(bm, edges=[x for g in holes for x in g], sides=args.fill_holes)["faces"]
    if new:
        bmesh.ops.recalc_face_normals(bm, faces=new)
        if uvl is not None:
            for f in new:
                for l in f.loops:
                    if l.vert in vuv:
                        l[uvl].uv = vuv[l.vert]
    bm.to_mesh(gar.data)
    bm.free()
    gar.data.update()
    rep = {"holes": len(holes), "faces": len(new), "loose_faces_removed": len(bits)}
    if up:
        rep["over_the_waist"] = up
    say("holes filled", rep)
    return rep


def despike(gar, char, args) -> dict:
    """E1g: the trousers' spikes (A's and B's hip sides, d16): a garment vertex under the waist that stands more than
    args.despike m out of its neighbours' mean, along the body's outward normal, goes to that mean (args.despike_rounds
    passes). Smooth cloth and its corners stand far less out, so only the spikes' tips move."""
    from mathutils.bvhtree import BVHTree as _B
    if args.despike <= 0:
        return {}
    dg = bpy.context.evaluated_depsgraph_get()
    btree = _B.FromObject(char, dg)
    cw, gw = char.matrix_world, gar.matrix_world
    cinv, ginv = cw.inverted(), gw.inverted()
    cn = cw.to_3x3().inverted().transposed()
    me = gar.data
    nbrs = [[] for _ in me.vertices]
    for e in me.edges:
        a, b = e.vertices
        nbrs[a].append(b)
        nbrs[b].append(a)
    moved = set()
    for _ in range(args.despike_rounds):
        pts = [gw @ v.co for v in me.vertices]
        out = []
        for i, p in enumerate(pts):
            if p.z > args.waist or len(nbrs[i]) < 2:
                continue
            m = sum((pts[j] for j in nbrs[i]), Vector()) / len(nbrs[i])
            loc, n, _i, _d = btree.find_nearest(cinv @ p)
            n = (cn @ n).normalized()
            if F.spike_out(tuple(p - m), tuple(n), args.despike):
                out.append((i, m))
        for i, m in out:
            me.vertices[i].co = ginv @ m
            moved.add(i)
        if not out:
            break
    me.update()
    rep = {"verts": len(moved)}
    say("despike", rep)
    return rep


def seat_wrap(gar, char, args) -> dict:
    """The seat re-laid on the body (E1f): the female fit folded the cloth over her seat into flared shards round the
    back pockets (the dark shards at the back waist), geometry in the bind pose. Behind the side seams, under the
    waistband and down args.seat_wrap m, each garment vertex goes to its nearest body point plus a smoothed offset
    (its own distance there, clamped to args.seat_clear and smoothed over the cloth's edges), and the surface is
    relaxed along the body round its folds (faces turned more than args.seat_fold off the body's normal, two rings
    out; args.seat_relax rounds: Laplacian, then back onto the offset surface), which unfolds them; clothes_fit_geom.seat_weight eases it out at the zone's borders and where the cloth bridges. No face goes
    and no vertex is added, so the weights stay the fit's."""
    from mathutils.bvhtree import BVHTree as _B
    dg = bpy.context.evaluated_depsgraph_get()
    btree = _B.FromObject(char, dg)
    cw, gw = char.matrix_world, gar.matrix_world
    cinv, ginv = cw.inverted(), gw.inverted()
    cn = cw.to_3x3().inverted().transposed()
    lo, hi = floats(args.seat_clear)
    z_lo, z_hi = args.waist - args.seat_wrap, args.waist - 0.01
    me = gar.data
    nbrs = [[] for _ in me.vertices]
    for e in me.edges:
        a, b = e.vertices
        nbrs[a].append(b)
        nbrs[b].append(a)

    def near(p):  # world point -> (body point, outward normal, distance), all world
        loc, n, _i, d = btree.find_nearest(cinv @ p)
        return cw @ loc, (cn @ n).normalized(), (cw @ loc - p).length

    pts = [gw @ v.co for v in me.vertices]
    w, off = [], []
    for p in pts:
        loc, n, d = near(p)
        s = (p - loc).dot(n)
        w.append(F.seat_weight(p.y, p.z, d, z_lo, z_hi, args.seat_y0, y1=args.seat_y1) if s > -0.01 else 0.0)
        off.append([min(hi, max(lo, s))])
    moved = [i for i, x in enumerate(w) if x > 0]
    if not moved:
        return {"verts": 0}
    off = F.smooth(off, nbrs, args.seat_smooth, 0.5, mask=[1.0 if x > 0 else 0.0 for x in w])
    # the relax only round the folds (faces turned off the body's normal, two rings out): sliding smooth cloth along
    # the body smears its texture (d15, the chameleon's back)
    gn = gw.to_3x3().inverted().transposed()
    fold = [0.0] * len(pts)
    for f in me.polygons:
        if not any(w[i] > 0 for i in f.vertices):
            continue
        _loc, n, _d = near(gw @ f.center)
        if (gn @ f.normal).normalized().dot(n) < args.seat_fold:
            for i in f.vertices:
                fold[i] = 1.0
    for _ in range(2):
        fold = [max([fold[i]] + [fold[j] for j in nbrs[i]]) for i in range(len(fold))]
    if args.seat_open_rings > 0:  # E1g: the relax only near the cloth's open edges (the flaps), not Meshy's relief
        ekey = {tuple(sorted(e.vertices)): 0 for e in me.edges}
        for f in me.polygons:
            for k in f.edge_keys:
                ekey[tuple(sorted(k))] += 1
        seeds = sorted({i for k, c in ekey.items() if c == 1 for i in k if w[i] > 0})
        fold = [a * b for a, b in zip(fold, F.near_rings(seeds, nbrs, args.seat_open_rings))]
    relax = [a * b for a, b in zip(w, fold)]
    relax_set = {i for i, x in enumerate(relax) if x > 0}
    cur = [list(p) for p in pts]
    for i in moved:  # E1g: off the relax, along the body's normal only, so the UVs keep their layout
        if i not in relax_set:
            loc, n, _d = near(pts[i])
            q = pts[i] + n * (off[i][0] - (pts[i] - loc).dot(n))
            cur[i] = list(pts[i].lerp(q, w[i]))
    for _ in range(args.seat_relax if relax_set else 0):
        cur = F.smooth(cur, nbrs, 1, 0.5, mask=relax)
        for i in relax_set:
            loc, n, _d = near(Vector(cur[i]))
            q = loc + n * off[i][0]
            cur[i] = list(Vector(pts[i]).lerp(q, w[i]))
    shift = [(Vector(cur[i]) - pts[i]).length for i in moved]
    for i in moved:
        me.vertices[i].co = ginv @ Vector(cur[i])
    me.update()
    rep = {"verts": len(moved), "full": sum(x > 0.999 for x in w), "relaxed": sum(x > 0 for x in relax), "shift_mm_median_max":
           [round(1000 * sorted(shift)[len(shift) // 2], 1), round(1000 * max(shift), 1)], "z": [round(z_lo, 4),
                                                                                                 round(z_hi, 4)]}
    say("seat wrap", rep)
    return rep


def peel_edges(bm, gar, args, z_lo: float, bib_hw: float, bib_top: float, back_y: float, z_apex: float,
               hw_w: float, hw_a: float) -> dict:
    """The panels' ragged side edges (C1j): along the bib's and the back panel's side edges (within args.edge_zone of
    the cut, from the waistband's foot up to args.band_flaps above the waist: r27 peeled up to the bib's top, and
    beside the buckle that opened the bib over the chest), args.edge_peel passes each peel the
    faces on an open edge that are turned toward the body, slivers, crumbs or folded back
    (clothes_shell.edge_defect: the wedges, flaps and slivers Meshy's layered side opening leaves); then the loose
    bits there (args.edge_island faces or fewer, all in the zone) go. Faces inside the cloth stay (no hole opens),
    except those mostly of the shirt Meshy baked into the denim (clothes_shell.shirt_texel: the white wedges), which
    show the top behind them."""
    if args.edge_peel <= 0:
        return {}
    mw = gar.matrix_world
    nm3 = mw.to_3x3().inverted().transposed()

    def zone(c) -> bool:
        hw = H.back_halfwidth(c.z, args.waist, z_apex, hw_w, hw_a)
        z_hi = min(bib_top if c.y < 0 else z_apex, args.waist + args.band_flaps) + 0.005
        return H.near_panel_edge(c.x, c.y, c.z, z_lo, z_hi, bib_hw, back_y, hw, args.edge_zone)

    rep = {"passes": []}
    # the shirt Meshy baked into the denim along the edges (the white wedges): faces mostly of its texels
    diff = garment_maps(gar).get("diffuse")
    uvl = bm.loops.layers.uv.active
    if diff is not None and uvl is not None:
        px = pixels(diff)
        h, w = px.shape[:2]
        white = []
        smin = getattr(args, "shirt_min", 0.0)
        stop = getattr(args, "shirt_top", 0.0)

        def shirt_zone(c) -> bool:  # M2g: the striped side walls beside the buckle sit above the peel's zone
            if stop <= 0:
                return zone(c)
            hw = H.back_halfwidth(c.z, args.waist, z_apex, hw_w, hw_a)
            z_hi = min(bib_top if c.y < 0 else z_apex, args.waist + stop) + 0.005
            return H.near_panel_edge(c.x, c.y, c.z, z_lo, z_hi, bib_hw, back_y, hw, args.edge_zone)

        for f in bm.faces:
            if not shirt_zone(mw @ f.calc_center_median()):
                continue
            uvs = [l[uvl].uv for l in f.loops]
            cu = sum((u for u in uvs), Vector((0.0, 0.0))) / len(uvs)
            pts = H.face_samples(cu, uvs) if smin > 0 else [cu] + [cu.lerp(u, 0.7) for u in uvs]
            hits = 0
            for u in pts:
                r, g, b = px[min(h - 1, max(0, int(u[1] * h))), min(w - 1, max(0, int(u[0] * w))), :3]
                hits += H.shirt_texel(float(r), float(g), float(b))
            if (hits >= max(1, math.ceil(smin * len(pts) - 1e-9))) if smin > 0 else hits >= len(uvs):
                white.append(f)
        # only from an open edge inward (C1k, the review's minor 2): the bib's own light stitching inside the cloth
        # stays, no hole opens
        bm.faces.index_update()
        allowed = {f.index for f in white}
        nbrs = [[g.index for e in f.edges for g in e.link_faces if g is not f] for f in bm.faces]
        seeds = [f.index for f in white if any(len(e.link_faces) != 2 for e in f.edges)]
        bm.faces.ensure_lookup_table()
        peel = [bm.faces[i] for i in H.flood(seeds, nbrs, allowed)]
        rep["shirt_faces"] = len(peel)
        rep["shirt_faces_inside_kept"] = len(white) - len(peel)
        if peel:
            bmesh.ops.delete(bm, geom=peel, context="FACES")
    for _ in range(args.edge_peel):
        bm.normal_update()
        gone = []
        for f in bm.faces:
            c = mw @ f.calc_center_median()
            if not zone(c):
                continue
            open_edge = any(len(e.link_faces) != 2 for e in f.edges)
            if not open_edge:
                continue
            n = (nm3 @ f.normal).normalized()
            ox, oy = c.x, c.y - args.band_axis_y
            ln = math.hypot(ox, oy)
            out = (n.x * ox + n.y * oy) / ln if ln > 1e-9 else 0.0
            q = [mw @ v.co for v in f.verts]
            edges = [(q[i] - q[(i + 1) % len(q)]).length for i in range(len(q))]
            area = sum(((q[i] - q[0]).cross(q[i + 1] - q[0])).length / 2 for i in range(1, len(q) - 1))
            nb = [g for e in f.edges for g in e.link_faces if g is not f]
            fold = sum(g.normal.dot(f.normal) for g in nb) / len(nb) if nb else -1.0
            if H.edge_defect(True, out, H.min_altitude(edges, area), area, fold, inward=args.edge_inward):
                gone.append(f)
        rep["passes"].append(len(gone))
        if not gone:
            break
        bmesh.ops.delete(bm, geom=gone, context="FACES")
    # the loose bits along the edges
    seen, bits = set(), []
    for f in bm.faces:
        if f in seen or not zone(mw @ f.calc_center_median()):
            continue
        comp, stack, small = [], [f], True
        seen_local = {f}
        while stack and small:
            g = stack.pop()
            comp.append(g)
            if len(comp) > args.edge_island or not zone(mw @ g.calc_center_median()):
                small = False
                break
            for e in g.edges:
                for h in e.link_faces:
                    if h not in seen_local:
                        seen_local.add(h)
                        stack.append(h)
        seen.update(comp)
        if small:
            bits.extend(comp)
    if bits:
        bmesh.ops.delete(bm, geom=list(set(bits)), context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    rep["islands_faces"] = len(set(bits))
    rep["total"] = sum(rep["passes"]) + rep["islands_faces"] + rep.get("shirt_faces", 0)
    return rep


def stripe_colours(gar) -> tuple[np.ndarray, np.ndarray]:
    """The Meshy top's navy and white (stored sRGB), from its sleeves: the darker and the lighter half's medians."""
    me = gar.data
    img = next(n.image for sl in gar.material_slots if sl.material and sl.material.node_tree
               for n in sl.material.node_tree.nodes if n.type == "TEX_IMAGE" and n.image and "diffuse" in n.image.name)
    w, h = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)[..., :3]
    uvl = me.uv_layers.active.data
    cols = []
    for p in me.polygons:
        c = gar.matrix_world @ p.center
        if c.z > 1.2 and 0.25 < abs(c.x) < 0.55:
            u = sum(uvl[li].uv.x for li in p.loop_indices) / p.loop_total
            v = sum(uvl[li].uv.y for li in p.loop_indices) / p.loop_total
            cols.append(px[min(h - 1, int(v * h)), min(w - 1, int(u * w))])
    cols = np.array(cols)
    if len(cols) < 2:
        raise ValueError(f"no sleeve faces of {gar.name} to sample the stripes' colours from (z > 1.2, |x| 0.25-0.55)")
    lum = cols @ np.array([0.2126, 0.7152, 0.0722])
    cut = np.median(lum)
    dark, light = cols[lum < cut], cols[lum >= cut]
    if not len(dark):  # one colour only: the stripes take it twice
        dark = light
    return np.median(dark, axis=0), np.median(light, axis=0)


def shell(char, arm, keep, args) -> tuple[object, dict]:
    """The striped top (see the module): returns the new object "top" and its numbers."""
    rep: dict = {}
    gname = {g.index: g.name for g in char.vertex_groups}
    top = char.copy()
    top.data = char.data.copy()
    top.name = top.data.name = "top"
    bpy.context.scene.collection.objects.link(top)
    if top.data.shape_keys:
        top.shape_key_clear()
    mw = char.matrix_world
    inv = mw.inverted()
    nmat = mw.to_3x3().inverted().transposed()
    me = top.data
    ktree = tree_of([keep]) if keep is not None else None
    z_hem, z_full = args.shell_hem, args.shell_full
    ok = []
    for v in me.vertices:
        b = gname.get(max(v.groups, key=lambda g: g.weight).group, "") if v.groups else ""
        ok.append(any(b.endswith(k) for k in ALLOWED))
    offs, reduced, pulled = {}, 0, 0
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    drop = [f for f in bm.faces if not all(ok[v.index] for v in f.verts)
            or (mw @ f.calc_center_median()).z < z_hem - 0.03]
    bmesh.ops.delete(bm, geom=drop, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.normal_update()
    for v in bm.verts:
        p = mw @ v.co
        n = (nmat @ v.normal).normalized()
        want = H.taper(p.z, z_hem, z_full, args.shell_hem_off, args.shell_off)
        hit = None
        if ktree is not None:
            loc = ktree.ray_cast(p + n * 1e-4, n, 0.05)[0]
            hit = None if loc is None else (loc - p).length
        d = H.clearance(want, hit, args.shell_gap, args.shell_floor)
        if ktree is not None and args.shell_under > 0 and p.z > args.waist:
            # under the bib and the back panel nobody sees the top: in toward the body, so the panels have room
            share = ray_share(ktree, p, n, args.shell_hide, args.shell_hide_tilt)
            pulled += share > 0
            d = H.under_offset(d, share, args.shell_under)
        reduced += d < want - 1e-6
        offs[v.index] = d
        v.co = inv @ (p + n * d)
    bm.normal_update()
    # under the bib and the back panel nobody sees the top: a face goes when its normal and four rays tilted round it
    # all meet the kept garment within args.shell_hide, args.shell_hide_rings rings in from the panels' edges (the
    # tucked hem stays whole)
    hid = {f for f in bm.faces if ktree is not None and hidden_face(ktree, mw @ f.calc_center_median(),
                                                                    (nmat @ f.normal).normalized(), z_full, args)}
    for _ in range(args.shell_hide_rings):
        hid = {f for f in hid if all(g in hid for v in f.verts for g in v.link_faces)}
    rep["faces_hidden_under_the_panels"] = len(hid)
    bmesh.ops.delete(bm, geom=list(hid), context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    rep["verts_offset"] = len(offs)
    rep["verts_nearer_for_the_bib"] = reduced
    rep["verts_pulled_in_under_the_panels"] = pulled
    rep["offset_mm_min_median"] = [round(1000 * min(offs.values()), 2),
                                   round(1000 * sorted(offs.values())[len(offs) // 2], 2)]
    yf, zf, yb, zb = floats(args.neck)
    nco, nno = H.neck_plane(yf, zf, yb, zb)
    bm.to_mesh(me)
    bm.free()
    me.update()
    rep["decimate"] = decimate(top, char, nco, nno, zf, args)
    bm = bmesh.new()
    bm.from_mesh(me)
    # the openings: hem, cuffs, the crew neck
    _bisect(bm, mw, lambda c: True, (0, 0, z_hem), (0, 0, 1), outer=False)
    for sgn in (1, -1):
        _bisect(bm, mw, lambda c: True, (sgn * args.cuff_x, 0, 0), (sgn, 0, 0))
    _bisect(bm, mw, lambda c: abs(c.x) < args.neck_r and c.z > zf - 0.06, nco, nno)
    bm.normal_update()
    # the rolled lip at the collar and the cuffs: the open edge folded in toward the body
    edges = []
    for e in bm.edges:
        if not e.is_boundary:
            continue
        m = mw @ ((e.verts[0].co + e.verts[1].co) / 2)
        if abs(H.plane_side(tuple(m), nco, nno)) < 0.003 or abs(abs(m.x) - args.cuff_x) < 0.003:
            edges.append(e)
    rim = {v: (nmat @ v.normal).normalized() for e in edges for v in e.verts}
    kd = KDTree(len(rim))
    rim_list = list(rim.items())
    for i, (v, _n) in enumerate(rim_list):
        kd.insert(v.co, i)
    kd.balance()
    res = bmesh.ops.extrude_edge_only(bm, edges=edges)
    new = [g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)]
    for v in new:
        _c, i, _d = kd.find(v.co)
        _ov, n = rim_list[i]
        p = mw @ v.co
        v.co = inv @ (p - n * args.shell_lip)
    rep["lip_edges"] = len(edges)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    # the set-in sleeve's seam (C1k, the review's nit): cut at |x| = seam_x above arm_z and at z = arm_z beyond it,
    # so each face lies wholly on one side and the seam H.region draws by face centres runs straight
    for sgn in (1, -1):
        _bisect(bm, mw, lambda c: c.z > args.arm_z - 0.03, (sgn * args.seam_x, 0, 0), (sgn, 0, 0), outer=None)
        _bisect(bm, mw, lambda c, s=sgn: s * c.x > args.seam_x - 0.03, (0, 0, args.arm_z), (0, 0, 1), outer=None)
    # UVs
    uv = bm.loops.layers.uv.active
    axis_y, axis_z = floats(args.arm_axis)
    for f in bm.faces:
        c = mw @ f.calc_center_median()
        reg = H.region(c.x, c.z, args.seam_x, args.arm_z)
        u0, wd = ISLANDS[reg]
        pts = [mw @ lp.vert.co for lp in f.loops]
        if reg == H.TORSO:
            uvs = [H.torso_uv(p.x, p.y, p.z, axis_y - 0.04, u0, wd, V0[reg], args.shell_per_m, zf) for p in pts]
        else:
            uvs = [H.arm_uv(p.x, p.y, p.z, args.cuff_x, axis_y, axis_z, u0, wd, V0[reg], args.shell_per_m)
                   for p in pts]
        us = H.unwrap([a for a, _b in uvs], u0, wd)
        for lp, uu, (_a, vv) in zip(f.loops, us, uvs):
            lp[uv].uv = (uu, vv)
        f.material_index = 0
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    me.update()
    me.materials.clear()
    rep["tris"] = sum(len(p.vertices) - 2 for p in me.polygons)
    rep["material"] = material(top, keep, args, rep)
    rep["follow"] = follow_panels(top, keep, args)
    say("shell", rep)
    return top, rep


def follow_panels(top, gar, args, zmax: float | None = None) -> dict:
    """The top under the bib, the back panel and the trousers' waist takes their weights (the fit's), by the share
    of five rays from each vertex (its normal and four tilted by args.shell_hide_tilt) that meet the garment within
    args.shell_follow m (clothes_shell.follow_row): it moves with the panels and stays under them (C1h: the body's
    weights let it poke through the bib's sides by up to 10 mm in the clips, clothes_proof's top_under_panels).
    zmax (M2e): only the top's vertices up to this height (run again after straps() built the waistband: the first
    run met no band at the hip sides, where cut_garment had cut Meshy's, so the top's rows there kept the body's
    Spine weights and came out through the band by 10 to 23 mm in Jog and Crouch)."""
    if args.shell_follow <= 0 or gar is None:
        return {}
    tree = tree_of([gar])
    src = body_weights(gar)
    mw = top.matrix_world
    nm = mw.to_3x3().inverted().transposed()
    groups = {g.name: g for g in top.vertex_groups}
    names = {g.index: g.name for g in top.vertex_groups}
    full = part = 0
    for v in top.data.vertices:
        p = mw @ v.co
        if zmax is not None and p.z > zmax:
            continue
        share = ray_share(tree, p, (nm @ v.normal).normalized(), args.shell_follow, args.shell_hide_tilt)
        if not share:
            continue
        own = {names[g.group]: g.weight for g in v.groups if g.group in names}
        row = H.follow_row(own, weight_row(src, p), share)
        for g in list(v.groups):
            top.vertex_groups[g.group].remove([v.index])
        for b, x in row.items():
            if b not in groups:
                groups[b] = top.vertex_groups.new(name=b)
            groups[b].add([v.index], x, "REPLACE")
        full += share == 1
        part += share < 1
    return {"verts_following_fully": full, "verts_following_in_part": part}


def hidden_face(tree, c, n, z_full, args) -> bool:
    """Whether a shell face (centre c, outward normal n, world) lies under a kept panel: above the full clearance,
    its normal and four rays tilted by args.shell_hide_tilt round it all meet the panel within args.shell_hide. E1h:
    with args.shell_hide_above, from that height over the waist on (the shirt came through the bib pocket's bottom in
    Jog, between the waist and the full clearance)."""
    above = getattr(args, "shell_hide_above", None)
    z_gate = z_full if above is None else min(z_full, args.waist + above)  # E1h: lower under the bib's pocket
    return c.z > z_gate and ray_share(tree, c, n, args.shell_hide, args.shell_hide_tilt) == 1


def ray_share(tree, p, n, reach: float, tilt: float) -> float:
    """The share of five rays from p (its normal n and four tilted round it by tilt, tan) that meet tree within
    reach: 1 deep under a panel, partial at its edge, 0 in the open."""
    side = Vector((n.y, -n.x, 0.0))
    side = side.normalized() if side.length > 1e-6 else Vector((1.0, 0.0, 0.0))
    up = n.cross(side).normalized()
    dirs = [n] + [(n + tilt * d).normalized() for d in (side, -side, up, -up)]
    return sum(tree.ray_cast(p + d * 1e-4, d, reach)[0] is not None for d in dirs) / len(dirs)


def body_weights(char):
    """The body's surface and weights, for weighting a new vertex like the body under it (weight_row)."""
    gname = {g.index: g.name for g in char.vertex_groups}
    return {"tree": tree_of([char]), "co": [char.matrix_world @ v.co for v in char.data.vertices],
            "polys": [list(p.vertices) for p in char.data.polygons],
            "w": [{gname[g.group]: g.weight for g in v.groups if g.group in gname} for v in char.data.vertices]}


def weight_row(body, q) -> dict:
    """The body's weights at its point nearest q (barycentric over the face), at most four bones."""
    loc, _n, fi, _d = body["tree"].find_nearest(q)
    row = {}
    vs = body["polys"][fi]
    for k, w in zip(vs, poly_3d_calc([body["co"][k] for k in vs], loc)):
        for b, x in body["w"][k].items():
            row[b] = row.get(b, 0.0) + w * x
    return F.limit(row)


def near_seam(c, reg, args, zf, share: float = 0.06, band: float = 0.025) -> bool:
    """Whether a face centre c lies near a UV seam of the top, where a big face would take the next island's stripes:
    the torso's back centre and each sleeve's underside (within share of the island's width), or the set-in sleeve
    seam between the torso and the arms (within band m)."""
    u0, wd = ISLANDS[reg]
    axis_y, axis_z = floats(args.arm_axis)
    if reg == H.TORSO:
        u = H.torso_uv(c.x, c.y, c.z, axis_y - 0.04, u0, wd, V0[reg], args.shell_per_m, zf)[0]
    else:
        u = H.arm_uv(c.x, c.y, c.z, args.cuff_x, axis_y, axis_z, u0, wd, V0[reg], args.shell_per_m)[0]
    f = (u - u0) / wd
    sleeve = ((abs(abs(c.x) - args.seam_x) < band and c.z > args.arm_z - band)
              or (abs(c.x) > args.seam_x - band and abs(c.z - args.arm_z) < band))
    return f < share or f > 1 - share or sleeve


def decimate(top, char, nco, nno, zf, args) -> dict:
    """Fewer faces on the top away from its openings (args.shell_decimate: the arms' and the torso's share kept),
    mirrored in x, by Blender's collapse decimation of the selected faces; every vertex of a decimated face then takes
    the body's weights under it (weight_row)."""
    r_arm, r_torso = floats(args.shell_decimate)
    p_cuff, p_neck, p_hem = floats(args.shell_protect)
    me = top.data
    mw = top.matrix_world
    out = {"tris_before": sum(len(p.vertices) - 2 for p in me.polygons)}
    if r_arm >= 1 and r_torso >= 1:
        return out
    for o in bpy.context.view_layer.objects:
        o.select_set(o == top)
    bpy.context.view_layer.objects.active = top
    picked = 0
    body = body_weights(char)
    groups = top.vertex_groups
    for want, ratio in ((False, r_arm), (True, r_torso)):
        if ratio >= 1:
            continue
        bpy.ops.object.mode_set(mode="EDIT")
        ebm = bmesh.from_edit_mesh(me)
        for f in ebm.faces:
            c = mw @ f.calc_center_median()
            reg = H.region(c.x, c.z, args.seam_x, args.arm_z)
            far = (abs(c.x) < args.cuff_x - p_cuff and H.plane_side(tuple(c), nco, nno) < -p_neck
                   and c.z > args.shell_hem + p_hem and not near_seam(c, reg, args, zf))
            f.select_set(far and (reg == H.TORSO) == want)
        ebm.select_flush(True)
        bmesh.update_edit_mesh(me)
        bpy.ops.mesh.decimate(ratio=ratio, use_symmetry=True, symmetry_axis="X")
        bpy.ops.object.mode_set(mode="OBJECT")
        # the indices change with each pass: re-weight this pass's vertices now
        here = sorted({k for p in me.polygons if p.select for k in p.vertices})
        for vi in here:
            v = me.vertices[vi]
            for g in list(v.groups):
                groups[g.group].remove([vi])
            for b, x in weight_row(body, mw @ v.co).items():
                (groups.get(b) or groups.new(name=b)).add([vi], x, "REPLACE")
        picked += len(here)
    out["tris_after"] = sum(len(p.vertices) - 2 for p in me.polygons)
    out["reweighted_verts"] = picked
    return out


def material(top, gar, args, rep) -> dict:
    """The top's material: the stripes (the Meshy top's own navy and white) times a soft AO bake, a cotton normal map
    (fine knit ribs and the AO's folds), roughness 0.9."""
    navy, white = args.stripe_cols
    period, duty = floats(args.stripe)
    lin = T.stripe_image(navy, white, period, duty, args.shell_per_m, ISLANDS, V0, (IMG_W, IMG_H))
    mat = bpy.data.materials.new("top_cotton")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = 0.9
    for key in ("Specular IOR Level", "Specular"):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = 0.25
            break
    alb = bpy.data.images.new("top_diffuse", IMG_W, IMG_H, alpha=False)
    nrm = bpy.data.images.new("top_normal", IMG_W, IMG_H, alpha=False)
    nrm.colorspace_settings.name = "Non-Color"
    ta = nt.nodes.new("ShaderNodeTexImage")
    ta.image = alb
    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.image = nrm
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(ta.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    top.data.materials.append(mat)
    ao = np.ones((IMG_H, IMG_W), dtype=np.float32)
    out = {"navy_srgb": [round(float(x) * 255) for x in navy], "white_srgb": [round(float(x) * 255) for x in white],
           "stripe_period_m": period, "navy_share": duty}
    if args.shell_ao > 0:
        try:
            ao = bake_ao(top, ta, alb, args)
            me = top.data
            me.calc_loop_triangles()
            uvl = me.uv_layers.active.data
            tri = np.array([[uvl[t.loops[i]].uv[:] for i in range(3)] for t in me.loop_triangles], dtype=np.float64)
            inside = T.island_mask(tri, IMG_W, IMG_H)
            out["ao_in_islands_p10_median"] = [round(float(np.percentile(ao[inside], 10)), 3),
                                               round(float(np.median(ao[inside])), 3)]
            out["island_share"] = round(float(inside.mean()), 3)
            # outside the islands the bake is black: fill it from the islands, and across the torso's back seam
            # take the other side's texels, so the mips and the normal map see no edge there
            ao = T.fill(ao[..., None], inside)[..., 0]
            u0, wd = ISLANDS[H.TORSO]
            for dst, src in H.seam_wrap_cols(round((u0 - 0.008) * IMG_W), round(u0 * IMG_W),
                                             round((u0 + wd) * IMG_W), round((u0 + wd + 0.02) * IMG_W)):
                ao[:, dst] = ao[:, src]
        except Exception as e:  # noqa: BLE001 - the stripes stand without the AO
            out["ao_failed"] = str(e)[:200]
    shade = 1.0 - args.shell_ao * (1.0 - ao)
    rgb = T.to_srgb(lin * shade[..., None])
    alb.pixels[:] = np.concatenate([rgb, np.ones((IMG_H, IMG_W, 1), np.float32)], axis=2).ravel()
    alb.update()
    alb.pack()
    # the normal map: fine ribs across u (about 2 mm) and the AO as a soft height (the folds)
    xs = np.arange(IMG_W, dtype=np.float32)
    hgt = 0.15 * np.sin(2 * np.pi * xs / 3.0)[None, :] + 6.0 * T.blur(ao, 6)
    gy, gx = np.gradient(hgt)
    n = np.stack([-gx, -gy, np.ones_like(hgt)], axis=2)
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    nrm.pixels[:] = np.concatenate([0.5 + 0.5 * n, np.ones((IMG_H, IMG_W, 1), np.float32)], axis=2).ravel()
    nrm.update()
    nrm.pack()
    return out


def bake_ao(top, node, img, args) -> np.ndarray:
    """Cycles' ambient occlusion on the top's UVs, at rest, everything else in the scene occluding."""
    scn = bpy.context.scene
    arm = top.parent
    old = arm.data.pose_position if arm else None
    if arm:
        arm.data.pose_position = "REST"
    scn.render.engine = "CYCLES"
    scn.cycles.device = "CPU"
    scn.cycles.samples = args.shell_ao_samples
    if scn.world is None:
        scn.world = bpy.data.worlds.new("World")
    scn.world.light_settings.distance = args.shell_ao_dist
    aoimg = bpy.data.images.new("top_ao", IMG_W, IMG_H, alpha=False)
    aoimg.colorspace_settings.name = "Non-Color"
    node.image = aoimg
    top.active_material.node_tree.nodes.active = node
    for o in bpy.context.view_layer.objects:
        o.select_set(o == top)
    bpy.context.view_layer.objects.active = top
    bpy.ops.object.bake(type="AO", margin=8, use_clear=True)
    a = np.array(aoimg.pixels[:], dtype=np.float32).reshape(IMG_H, IMG_W, 4)[..., 0]
    node.image = img
    bpy.data.images.remove(aoimg)
    if arm:
        arm.data.pose_position = old
    return np.clip(a, 0.0, 1.0)


def last_hit(tree, p, d, reach):
    """The farthest surface of tree along the ray p + t d within reach (the Meshy hardware can be a few layers)."""
    far, q, left = None, p + d * 1e-4, reach
    for _ in range(12):
        loc = tree.ray_cast(q, d, left)[0]
        if loc is None:
            break
        far = loc
        left -= (loc - q).length
        q = loc + d * 1e-4
        if left <= 0:
            break
    return far


def garment_maps(gar) -> dict:
    """The garment's images by kind: diffuse, normal, roughness."""
    out = {}
    for sl in gar.material_slots:
        if sl.material and sl.material.node_tree:
            for n in sl.material.node_tree.nodes:
                if n.type == "TEX_IMAGE" and n.image:
                    for kind in ("diffuse", "normal", "roughness"):
                        if kind in n.image.name:
                            out[kind] = n.image
    return out


def pixels(img) -> np.ndarray:
    w, h = img.size
    return np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)


def strap_patch(gar, args, ufr) -> tuple[tuple[float, float, float, float], dict]:
    """A free patch of the garment's texture as the straps' own: a copy of its plain denim (args.strap_uv: the
    diffuse, normal and roughness texels) with two dashed stitch lines along v in the sketch's orange, args.stitch's
    inset from the strap's edges. Returns its UV rectangle (u0, u1, v0, v1), half a texel in, and its numbers; the
    plain rectangle itself when no room is free."""
    u0, u1, v0, v1 = floats(args.strap_uv)
    maps = garment_maps(gar)
    dif = maps.get("diffuse")
    if dif is None:
        return (u0, u1, v0, v1), {"patch": "none: no diffuse map"}
    w, h = dif.size
    me = gar.data
    me.calc_loop_triangles()
    uvl = me.uv_layers.active.data
    tri = np.array([[uvl[t.loops[k]].uv[:] for k in range(3)] for t in me.loop_triangles], dtype=np.float64)
    used = T.island_mask(tri, w, h, grow=1)
    x0, x1, y0, y1 = int(u0 * w), int(np.ceil(u1 * w)), int(v0 * h), int(np.ceil(v1 * h))
    pw, ph = x1 - x0, y1 - y0
    at = T.free_rect(used, pw, ph, 6)
    if at is None:
        return (u0, u1, v0, v1), {"patch": "none free: the plain rectangle"}
    ry, rx = at
    inset, dash, gap = floats(args.stitch)
    px0 = pixels(dif)
    col = floats(args.stitch_colour)
    for kind, img in maps.items():
        iw, ih = img.size
        px = px0 if img is dif else pixels(img)
        sx, sy = iw / w, ih / h
        a0, a1, b0, b1 = int(x0 * sx), int(x0 * sx) + int(pw * sx), int(y0 * sy), int(y0 * sy) + int(ph * sy)
        c0, r0 = int(rx * sx), int(ry * sy)
        px[r0:r0 + (b1 - b0), c0:c0 + (a1 - a0)] = px[b0:b1, a0:a1]
        if img is dif:
            width = args.strap_width
            fl, fr = ufr[1], ufr[-2]
            cols = [fl + (fr - fl) * inset / width, fr - (fr - fl) * inset / width]
            per_px = args.strap_texels * h  # texels per metre along the strap
            mask = np.array(H.stitch_mask(pw, ph, cols, max(1, round(dash * per_px)), max(1, round(gap * per_px))))
            blk = px[r0:r0 + ph, c0:c0 + pw, :3]
            blk[mask] = col
        img.pixels[:] = px.ravel()
        img.update()
    rect = ((rx + 0.5) / w, (rx + pw - 0.5) / w, (ry + 0.5) / h, (ry + ph - 0.5) / h)
    return rect, {"patch_px": [int(rx), int(ry), pw, ph], "stitch_srgb": [round(255 * c) for c in col],
                  "stitch_u": [round(c, 3) for c in cols]}


def bronze_material(args):
    r, g, b, metal, rough = floats(args.bronze)
    mat = bpy.data.materials.new("buckle_bronze")
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    lin = T.to_linear(np.array([r, g, b]))
    bsdf.inputs["Base Color"].default_value = (float(lin[0]), float(lin[1]), float(lin[2]), 1.0)
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Roughness"].default_value = rough
    return mat


def buckles(bm, gar, body, plans, args, uv, dl, gi) -> dict:
    """At each strap's front end a bronze ring over the strap (args.buckle's second place) and a domed button at the
    tab's end (its first), on a new metal material; every vertex of a piece takes the body's weights under the strap's
    station there, so it rides with the strap, rigid."""
    mat = bronze_material(args)
    gar.data.materials.append(mat)
    mi = len(gar.data.materials) - 1
    inv = gar.matrix_world.inverted()
    at_button, at_ring = floats(args.buckle)
    margin, half_l, bar, height = floats(args.buckle_size)
    r, bh, dome = floats(args.button_size)
    n_tris, pieces = 0, []
    for pl in plans:
        ct, sides, nt, along = pl["ct"], pl["sides"], pl["nt"], pl["along"]
        for kind, s_at in (("button", at_button), ("ring", at_ring)):
            i = min(range(len(along)), key=lambda k: abs(along[k] - s_at))
            i = max(1, min(len(ct) - 2, i))
            c = Vector(ct[i])
            t = (Vector(ct[i + 1]) - Vector(ct[i - 1])).normalized()
            sv = Vector(sides[i])
            sv = (sv - t * sv.dot(t)).normalized()
            nv = t.cross(sv).normalized()
            if nv.dot(Vector(nt[i])) < 0:
                nv = -nv
            if kind == "ring":
                vs, fs = H.buckle_ring(tuple(c), tuple(t), tuple(sv), tuple(nv), args.strap_width / 2 + margin, half_l,
                                       bar, 0.0005, 0.0005 + height, 0.003)
            else:
                vs, fs = H.button(tuple(c), tuple(t), tuple(sv), tuple(nv), r, 0.0005, 0.0005 + bh, dome, 10)
            row = weight_row(body, c - nv * pl["offs"][i])
            bv = []
            for q in vs:
                v = bm.verts.new(inv @ Vector(q))
                for b, x in row.items():
                    if b not in gi:
                        gi[b] = gar.vertex_groups.new(name=b).index
                    v[dl][gi[b]] = x
                bv.append(v)
            faces = []
            for f in fs:
                fa = bm.faces.new([bv[k] for k in f])
                fa.material_index = mi
                fa.smooth = kind == "button"
                for loop in fa.loops:
                    loop[uv].uv = (0.0, 0.0)
                faces.append(fa)
            bm.normal_update()
            if kind == "ring":
                bmesh.ops.recalc_face_normals(bm, faces=faces)
            else:
                for fa in faces:
                    if (fa.calc_center_median() - (inv @ c)).dot(fa.normal) < 0:
                        fa.normal_flip()
            n_tris += sum(len(f) - 2 for f in fs)
            pieces.append({"kind": kind, "at": [round(x, 3) for x in c], "along_m": round(along[i], 3)})
    return {"tris": n_tris, "pieces": pieces, "material": mat.name}


def clear_strap_fronts(bm, gar, plans, rect, args) -> dict:
    """Under each strap's front part (args.strap_front m from its end) the Meshy bib goes where the strap covers it
    (args.strap_width / 2 less 2 mm across; its broken buckle hardware lies there in layers), and next to it the faces
    with the hardware's warm or near-black texels take the patch's plain denim (its middle, away from the stitches)."""
    dif = garment_maps(gar).get("diffuse")
    px = pixels(dif)[..., :3] if dif is not None else None
    mw = gar.matrix_world
    uv = bm.loops.layers.uv.active
    half = args.strap_width / 2
    mid = ((rect[0] + rect[1]) / 2, (rect[2] + rect[3]) / 2)
    fronts = []
    for pl in plans:
        for i, a in enumerate(pl["along"]):
            if a <= args.strap_front and 0 < i < len(pl["ct"]) - 1:
                t = (Vector(pl["ct"][i + 1]) - Vector(pl["ct"][i - 1])).normalized()
                fronts.append((Vector(pl["ct"][i]), t, Vector(pl["sides"][i]), Vector(pl["nt"][i]), a))
    gone, recoloured = [], 0
    if not fronts:
        say("strap fronts: no station within", args.strap_front, "m of a strap's front end; nothing cleared")
        return {"faces_cleared_under_the_fronts": 0, "hardware_faces_to_denim": 0}
    # E1g: first cut along each strap front's side lines and its end, so the faces that go below leave a straight
    # edge under the strap's own edge, not a jagged notch beside it (the axolotl's left strap front, d16)
    n_cut = 0
    for pl in plans:
        st = [fr for fr in fronts if any((fr[0] - Vector(q)).length < 1e-9 for q in pl["ct"])]
        if not st:
            continue
        ct = sum((fr[0] for fr in st), Vector()) / len(st)
        sd = sum((fr[2] for fr in st), Vector()).normalized()
        tg = sum((fr[1] for fr in st), Vector()).normalized()
        nt = sum((fr[3] for fr in st), Vector()).normalized()
        reach = max(fr[4] for fr in st) / 2 + 0.03

        def box(c, ct=ct, tg=tg, nt=nt, reach=reach):
            d = c - ct
            return c.y < 0 and c.z >= 1.05 and abs(d.dot(tg)) < reach and -0.05 < d.dot(nt) < 0.012

        for sgn in (1, -1):
            n_cut += 1
            _bisect(bm, mw, box, tuple(ct + sd * sgn * (half - 0.002)), tuple(sd * sgn), outer=None)
        end = min(st, key=lambda fr: fr[4])
        _bisect(bm, mw, box, tuple(end[0] - end[1] * (end[4] - 0.004)), tuple(end[1]), outer=None)
    bm.faces.ensure_lookup_table()
    for f in bm.faces:
        c = mw @ f.calc_center_median()
        if c.y >= 0 or c.z < 1.05:
            continue
        best = min(fronts, key=lambda fr: (c - fr[0]).length)
        d = c - best[0]
        lat, up = abs(d.dot(best[2])), d.dot(best[3])
        if lat < half - 0.002 and best[4] + d.dot(best[1]) > 0.004 and abs(d.dot(best[1])) < 0.02 and -0.04 < up < 0.002:
            gone.append(f)
            continue
        if px is not None and lat < half + 0.008 and -0.04 < up < 0.01:
            h, w = px.shape[:2]
            u = sum(lp[uv].uv.x for lp in f.loops) / len(f.loops)
            v = sum(lp[uv].uv.y for lp in f.loops) / len(f.loops)
            col = px[min(h - 1, int(v * h)), min(w - 1, int(u * w))]
            if col[0] > 1.3 * col[2] or float(col @ np.array([0.2126, 0.7152, 0.0722])) < 0.03:
                for lp in f.loops:
                    lp[uv].uv = mid
                recoloured += 1
    bmesh.ops.delete(bm, geom=gone, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    return {"faces_cleared_under_the_fronts": len(gone), "hardware_faces_to_denim": recoloured}


def straps(gar, char, keep_objs, args) -> dict:
    """Two new strips (see the module) appended to the garment mesh, their stitched patch, the buckles."""
    body = body_weights(char)
    btree = body["tree"]
    ktree = tree_of(keep_objs)
    y0, z0 = floats(args.strap_axis)
    ts = [math.radians(t) for t in floats(args.shell_strap_t)]
    xs_k = floats(args.shell_strap_x)
    half, lip = args.strap_width / 2, args.strap_lip
    t_back = ts[-1]
    if getattr(args, "strap_back_z", None) is not None:  # E1d: the back ends reach under the back panel's apex
        for k in range(80):
            t = ts[-1] + math.radians(k)
            loc = btree.ray_cast(Vector((xs_k[-1], y0, z0)), Vector((0.0, math.sin(t), math.cos(t))), 0.4)[0]
            if loc is None or loc.z <= args.strap_back_z or t > math.radians(175):
                break
            t_back = t
        ts = ts[:-1] + [max(ts[-1], t_back)]
    dz_bib = getattr(args, "bib_raise_dz", 0.0)
    if dz_bib > 0:  # E1i: the bib was raised (flat_bib), so the straps' fronts end that much higher on it
        def front_z(t):
            loc = btree.ray_cast(Vector((xs_k[0], y0, z0)), Vector((0.0, math.sin(t), math.cos(t))), 0.4)[0]
            return None if loc is None else loc.z
        z_f0 = front_z(ts[0])
        t_f = ts[0]
        for k in range(1, 61):
            z = front_z(ts[0] + math.radians(k))
            if z_f0 is None or z is None:
                break
            t_f = ts[0] + math.radians(k)
            if z >= z_f0 + dz_bib:
                break
        ts = [t_f] + ts[1:]
    mw = gar.matrix_world
    inv = mw.inverted()
    me = gar.data
    steps = max(8, int(round((ts[-1] - ts[0]) / math.radians(args.shell_strap_step))))
    angles = [ts[0] + (ts[-1] - ts[0]) * i / steps for i in range(steps + 1)]
    n_flat = args.shell_strap_lats - 2
    lats = [(-half, -lip)] + [(-half + 2 * half * k / (n_flat - 1), 0.0) for k in range(n_flat)] + [(half, -lip)]
    ufr = H.lat_us(len(lats), args.strap_lip_u)
    rect, prep = strap_patch(gar, args, ufr)
    args.patch_rect = rect  # E1h: plain_denim leaves the straps' and band's patch alone
    u0, u1, v0, v1 = rect
    rep, plans = {"patch": prep, "front_angle_deg": round(math.degrees(ts[0]), 1),
                  "back_angle_deg": round(math.degrees(ts[-1]), 1)}, []
    for sgn in (1, -1):
        locs, nors, offs = [], [], []
        for t in angles:
            a = Vector((sgn * H.strap_x(t, ts, xs_k), y0, z0))
            d = Vector((0.0, math.sin(t), math.cos(t)))
            loc, nor, _i, _d = btree.ray_cast(a, d, 0.4)
            if loc is None:
                loc, nor, _i, _d = btree.find_nearest(a + d * 0.15)
            nor = nor if nor.dot(d) > 0 else -nor
            hit = last_hit(ktree, loc, nor, args.shell_strap_reach)
            extra = 0.0015 if sgn > 0 else 0.0
            offs.append(max(args.shell_strap_off, ((hit - loc).length + 0.002) if hit is not None else 0.0) + extra)
            locs.append(loc)
            nors.append(nor)
        offs = S.smooth_open(offs, 3)
        offs = [max(a, b) for a, b in zip(offs, S.smooth_open(offs, 3))]
        cs = [loc + nor * o for loc, nor, o in zip(locs, nors, offs)]
        cx = [S.smooth_open([c[k] for c in cs], 3) for k in range(3)]
        ct = [(cx[0][i], cx[1][i], cx[2][i]) for i in range(len(cs))]
        nx = [S.smooth_open([n[k] for n in nors], 3) for k in range(3)]
        nt = [tuple(Vector((nx[0][i], nx[1][i], nx[2][i])).normalized()) for i in range(len(cs))]
        sides = S.frames(ct, nt)
        along = S.arcs(ct)
        grid, uvs = [], []
        for i, (c, s, n) in enumerate(zip(ct, sides, nt)):
            for k, (lat, hgt) in enumerate(lats):
                q = Vector(c) + Vector(s) * lat
                loc, nor, _i, _d = btree.find_nearest(q)
                nor = nor if nor.dot(Vector(n)) > 0 else -nor
                grid.append(loc + nor * (offs[i] + hgt))
                uvs.append((u0 + (u1 - u0) * ufr[k], S.mirror_v(along[i], v0, v1, args.strap_texels)))
        plans.append({"grid": grid, "uvs": uvs, "rows": len(ct), "cols": len(lats), "nt": nt, "ct": ct,
                      "sides": sides, "along": along, "offs": offs})
        rep["left" if sgn > 0 else "right"] = {
            "stations": len(ct), "length_m": round(along[-1], 4), "off_mm_min_max": [round(1000 * min(offs), 1),
                                                                                    round(1000 * max(offs), 1)],
            "front": [round(v, 3) for v in ct[0]], "back": [round(v, 3) for v in ct[-1]]}
    gtree = tree_of([gar])  # the garment alone (cut, the Meshy band gone): the trousers under the waistband
    bm = bmesh.new()
    bm.from_mesh(me)
    rep["fronts"] = clear_strap_fronts(bm, gar, plans, rect, args)
    uv = bm.loops.layers.uv.active
    dl = bm.verts.layers.deform.verify()
    gi = {g.name: g.index for g in gar.vertex_groups}
    new_faces = []
    grids = []  # M2e: each strip's vertices, for back_join
    for pl in plans:
        vs = []
        grids.append(vs)
        for q in pl["grid"]:
            v = bm.verts.new(inv @ q)
            for b, x in weight_row(body, q).items():
                if b not in gi:
                    gi[b] = gar.vertex_groups.new(name=b).index
                v[dl][gi[b]] = x
            vs.append(v)
        faces = []
        for quad in S.strip_quads(pl["rows"], pl["cols"]):
            f = bm.faces.new([vs[k] for k in quad])
            f.smooth = True
            for loop, k in zip(f.loops, quad):
                loop[uv].uv = pl["uvs"][k]
            faces.append(f)
        bm.normal_update()
        mid = faces[(pl["rows"] // 2) * (pl["cols"] - 1) + (pl["cols"] - 1) // 2]
        if (mw.to_3x3() @ mid.normal).dot(Vector(pl["nt"][pl["rows"] // 2])) < 0:
            for f in faces:
                f.normal_flip()
        new_faces += faces
    rep["strip_tris"] = 2 * len(new_faces)
    rep["buckles"] = buckles(bm, gar, body, plans, args, uv, dl, gi)
    rep["waistband"] = waistband(bm, gar, body, gtree, rect, args, uv, dl, gi)
    bm.normal_update()
    bm.verts.index_update()
    args.strap_grids = [{"ids": [v.index for v in vs], "rows": pl["rows"], "cols": pl["cols"],
                         "hgts": [h for _l, h in lats], "nt": pl["nt"], "along": pl["along"],
                         "extra": 0.0015 if k == 0 else 0.0} for k, (vs, pl) in enumerate(zip(grids, plans))]
    bm.to_mesh(me)
    bm.free()
    me.update()
    say("straps", rep)
    return rep


def waistband(bm, gar, body, gtree, rect, args, uv, dl, gi) -> dict:
    """The built waistband (C1i), in place of the Meshy band cut_garment removed beside the bib: per side a strip
    args.waistband's height tall from just under the bib's side edge round the hip to just under the back panel's,
    stations every args.band_step degrees round the waist's centre. Each column lies on the body's surface (rays from
    the centre at its height) offset out: at the lower edge the trousers' own clearance under it (it laps over their
    cut edge, its lip folded onto them), cinched at the upper edge to args.band_cinch out of the tucked top, which it
    rolls in to (the ledge); at its ends it stays 2 mm under the Meshy it runs under. Its UVs are the straps'
    stitched patch (the top-stitching along it), its weights the trousers' nearest vertices'
    (clothes_shell.blend_rows), and a bronze button sits on it args.band_button beyond each bib edge."""
    band_h, lap = floats(args.waistband)
    if band_h <= 0:
        return {}
    z_w = args.waist
    bib_hw, _bib_top = floats(args.bib)
    back_y, _z_apex, hw_w, _hw_a = floats(args.back)
    btree = body["tree"]
    mw = gar.matrix_world
    inv = mw.inverted()
    z0 = z_w - band_h
    lats = H.band_lats(band_h, args.band_lip, 0.0, args.shell_strap_lats - 2)
    nl = len(lats)
    ufr = H.lat_us(nl, args.strap_lip_u)
    u0, u1, v0, v1 = rect
    top_off = H.taper(z_w, args.shell_hem, args.shell_full, args.shell_hem_off, args.shell_off)
    high0 = top_off + args.band_cinch
    # the trousers' vertices below the band, for the weights
    bm.verts.ensure_lookup_table()
    low_vs = [v for v in bm.verts if z0 - 0.07 < (mw @ v.co).z < z0 - 0.003 and v.link_faces]
    kd = KDTree(len(low_vs))
    for i, v in enumerate(low_vs):
        kd.insert(mw @ v.co, i)
    kd.balance()
    gname = {g.index: g.name for g in gar.vertex_groups}
    bronze = next((i for i, m in enumerate(gar.data.materials) if m and m.name.startswith("buckle_bronze")), None)
    rep: dict = {"height_m": band_h, "lap_m": lap, "top_offset_mm": round(1000 * top_off, 1)}
    tris = 0
    for sgn in (1, -1):
        cols = []  # per station: (angle, [(body point, normal) per lat], whether it runs under a panel)
        steps = int(round(180 / args.band_step))
        for i in range(steps + 1):
            a = math.radians(-90 + 180 * i / steps)
            d = Vector((sgn * math.cos(a), math.sin(a), 0.0))
            col = []
            for hgt, _dn in lats:
                o = Vector((0.0, args.band_axis_y, z0 + hgt))
                loc, nor, _f, _d = btree.ray_cast(o, d, 0.4)
                if loc is None:
                    break
                col.append((loc, nor if nor.dot(d) > 0 else -nor))
            if len(col) < nl:
                continue
            q = col[nl // 2][0]
            front, back = q.y < 0, q.y > back_y
            if (front and abs(q.x) < bib_hw - args.band_over) or (back and abs(q.x) < hw_w - args.band_over):
                continue
            cols.append((a, col, (front and abs(q.x) < bib_hw) or (back and abs(q.x) < hw_w)))
        if len(cols) < 3:
            say("waistband: too few stations on side", sgn)
            continue
        lows, ends = [], []
        for _a, col, under in cols:
            p, n = col[1]  # the lower edge's body point
            m = p - Vector((0, 0, 0.008))
            loc = gtree.ray_cast(m + n * 1e-4, n, 0.05)[0]
            lows.append((loc - m).length + 0.0015 if loc is not None else None)
            ends.append(under)
        known = sorted(x for x in lows if x is not None)
        fill = known[len(known) // 2] if known else 0.012
        lows = S.smooth_open([x if x is not None else fill for x in lows], 3)
        grid, uvs, offs = [], [], []
        n_pulled = n_on = 0
        along = [0.0]
        for k in range(1, len(cols)):
            along.append(along[-1] + (cols[k][1][-2][0] - cols[k - 1][1][-2][0]).length)
        for k, (_a, col, under) in enumerate(cols):
            low = max(lows[k], high0)
            for j, ((hgt, dn), (p, n)) in enumerate(zip(lats, col)):
                off = H.band_offset(hgt / band_h, low, high0) + dn
                if j == nl - 1:
                    off = top_off + 0.001  # the ledge: rolled in to the tucked top
                if j == 0:
                    p = p - Vector((0, 0, 0.002))
                if under:  # the ends run under the Meshy bib's or back panel's bottom, 2 mm inside it (C1k)
                    hit = gtree.ray_cast(p + n * 1e-4, n, 0.05)[0]
                    off, on_panel = H.band_end(off, (hit - p).length if hit is not None else None)
                    n_pulled += hit is not None and off < top_off + 0.001
                    n_on += on_panel
                grid.append(p + n * off)
                uvs.append((u0 + (u1 - u0) * ufr[j], S.mirror_v(along[k], v0, v1, args.strap_texels)))
            offs.append(low)
        verts = []
        for q in grid:
            v = bm.verts.new(inv @ q)
            near = [(low_vs[i], dd) for _c, i, dd in kd.find_n(q, 4)]
            row = H.blend_rows([({gname[g]: w for g, w in v2[dl].items() if g in gname}, dd) for v2, dd in near])
            for b, x in row.items():
                if b not in gi:
                    gi[b] = gar.vertex_groups.new(name=b).index
                v[dl][gi[b]] = x
            verts.append(v)
        faces = []
        for quad in S.strip_quads(len(cols), nl):
            f = bm.faces.new([verts[k] for k in quad])
            f.smooth = True
            for loop, k in zip(f.loops, quad):
                loop[uv].uv = uvs[k]
            faces.append(f)
        bm.normal_update()
        mid = faces[(len(cols) // 2) * (nl - 1) + (nl - 1) // 2]
        n_mid = cols[len(cols) // 2][1][nl // 2][1]
        if (mw.to_3x3() @ mid.normal).dot(n_mid) < 0:
            for f in faces:
                f.normal_flip()
        tris += 2 * len(faces)
        side = {"stations": len(cols), "length_m": round(along[-1], 3),
                "low_mm_min_max": [round(1000 * min(offs), 1), round(1000 * max(offs), 1)], "ends_under": sum(ends),
                "end_points_inside_the_top": n_pulled, "end_points_on_the_panel": n_on}
        if args.band_button > 0 and bronze is not None:
            want = bib_hw + args.band_button
            fronts = [i for i in range(1, len(cols) - 1) if cols[i][1][nl // 2][0].y < 0]
            if fronts:
                k = min(fronts, key=lambda i: abs(abs(cols[i][1][nl // 2][0].x) - want))
                mid_k = k * nl + nl // 2
                c = Vector(grid[mid_k])
                t = (Vector(grid[mid_k + nl]) - Vector(grid[mid_k - nl])).normalized()
                nv = cols[k][1][nl // 2][1]
                sv = nv.cross(t).normalized()
                r, bh, dome = floats(args.button_size)
                vs, fs = H.button(tuple(c), tuple(t), tuple(sv), tuple(nv), r, 0.0005, 0.0005 + bh, dome, 10)
                row = {g: w for g, w in verts[mid_k][dl].items()}
                bv = []
                for q in vs:
                    v = bm.verts.new(inv @ Vector(q))
                    for g, x in row.items():
                        v[dl][g] = x
                    bv.append(v)
                for f in fs:
                    fa = bm.faces.new([bv[i] for i in f])
                    fa.material_index = bronze
                    fa.smooth = True
                    for loop in fa.loops:
                        loop[uv].uv = (0.0, 0.0)
                    fa.normal_update()
                    if (fa.calc_center_median() - (inv @ c)).dot(fa.normal) < 0:
                        fa.normal_flip()
                tris += sum(len(f) - 2 for f in fs)
                side["button"] = [round(x, 3) for x in c]
        rep["left" if sgn > 0 else "right"] = side
    rep["tris"] = tris
    say("waistband", rep)
    return rep


def late_islands(gar, args) -> dict:
    """M2h: the bib side wall's dark crumbs beside the buckle (1 to 4 faces each, left loose by the shirt peel, above
    the peel's zone) go at the end, after the body's cover test and the skin's follow: d57 dropped them in the peel and
    the crotch's skin, whose tilted cover rays had met them, came back and poked 9 to 13 mm. A crumb is a piece of
    args.edge_island faces or fewer, all of the garment's denim slots, every face centre between the waist and
    args.island_top over it (the buckles and buttons are larger, the band button lower)."""
    top = args.waist + args.island_top
    mw = gar.matrix_world
    dif = garment_maps(gar).get("diffuse")
    den = {i for i, sl in enumerate(gar.material_slots) if sl.material and sl.material.node_tree and any(
        n.type == "TEX_IMAGE" and n.image is dif for n in sl.material.node_tree.nodes)}
    bm = bmesh.new()
    bm.from_mesh(gar.data)
    seen, bits, n = set(), [], 0
    for f in bm.faces:
        if f in seen:
            continue
        comp, stack = [], [f]
        seen.add(f)
        while stack:
            g = stack.pop()
            comp.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h not in seen:
                        seen.add(h)
                        stack.append(h)
        if len(comp) <= args.edge_island and all(
                g.material_index in den and args.waist < (mw @ g.calc_center_median()).z <= top for g in comp):
            bits.extend(comp)
            n += 1
    if bits:
        bmesh.ops.delete(bm, geom=bits, context="FACES")
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
        bm.to_mesh(gar.data)
        gar.data.update()
    bm.free()
    rep = {"pieces": n, "faces": len(bits)}
    say("late islands", rep)
    return rep


def turnup_relax(gar, args) -> dict:
    """M2h: the turn-ups' geometry, Meshy's one trouser surface folded out at each hem (bind pose). args.turnup_relax
    "z_top,rounds,alpha[,outward]": per leg (|x| over 3 cm, under z_top) the hem loop (the lowest open edges, within 3 cm of the
    lowest) goes onto one level, its median height (the jagged bottom edge), and its radius round the leg's axis is
    relaxed along the loop; then every other vertex of the leg under z_top has its radius alone relaxed over its edge
    neighbours (clothes_fit_geom.smooth, rounds at alpha), easing out over the top 3 cm (clothes_shell.relax_weight):
    the fold's in-and-out teeth over the light cuff. Heights stay (the cuff's colour is cut at one height by
    plain_denim's 8th value, so its line stays straight), but the hem's, under the cut in the light. Runs after the
    body's cover test and the skin's follow (d59 ran it before them: the body's cut changed and the crotch poked 9 to
    14 mm). Other open edges (a stray hole) stay. No weight changes."""
    vals = floats(args.turnup_relax)
    z_top, rounds, alpha = vals[:3]
    rounds = int(rounds)
    outward = len(vals) > 3 and vals[3] > 0  # M2i: no vertex comes in toward the leg's axis (d60, d64: the cuff came
    # in over the calf's skin at the back, 13 mm at rest and 25 to 30 mm in motion); the dips go out to the teeth
    me, mw = gar.data, gar.matrix_world
    inv = mw.inverted()
    co = [mw @ v.co for v in me.vertices]
    nb = [[] for _ in co]
    for e in me.edges:
        a, b = e.vertices
        nb[a].append(b)
        nb[b].append(a)
    use: dict[tuple, int] = {}
    for p in me.polygons:
        for ek in p.edge_keys:
            use[ek] = use.get(ek, 0) + 1
    open_e = [ek for ek, n in use.items() if n == 1]
    open_v = {i for ek in open_e for i in ek}
    rep = {}
    for sgn, side in ((1.0, "left"), (-1.0, "right")):
        leg = [i for i, c in enumerate(co) if c.x * sgn > 0.03 and c.z < z_top]
        hem0 = [i for i in leg if i in open_v]
        if len(leg) < 20 or not hem0:
            rep[side] = {"skipped": "no leg"}
            continue
        zl = min(co[i].z for i in hem0)
        hem = {i for i in hem0 if co[i].z < zl + 0.03}
        hz = float(np.median([co[i].z for i in hem]))
        ring = [co[i] for i in leg if co[i].z > hz]
        ax = (sum(c.x for c in ring) / len(ring), sum(c.y for c in ring) / len(ring))

        def cyl(c):
            dx, dy = c.x - ax[0], c.y - ax[1]
            return math.atan2(dy, dx), math.hypot(dx, dy)

        th = {i: cyl(co[i])[0] for i in leg}
        # the hem loop: one level, its radius relaxed along the loop
        ln = H.loop_nbrs(open_e, hem)
        hl = sorted(hem)
        loc = {i: k for k, i in enumerate(hl)}
        r_h = F.smooth([[cyl(co[i])[1]] for i in hl], [[loc[j] for j in ln[i]] for i in hl], rounds, alpha)
        rz = {i: [r_h[loc[i]][0], hz] for i in hl}
        z_span = [round(min(co[i].z for i in hem), 4), round(max(co[i].z for i in hem), 4)]
        # the rest of the leg under z_top: radius and height over the edge neighbours (any vertex, fixed outside)
        ids = sorted(set(leg) | {j for i in leg for j in nb[i]})
        at = {i: k for k, i in enumerate(ids)}
        vals = [[rz[i][0]] if i in rz else [cyl(co[i])[1]] for i in ids]
        mask = [0.0 if (i in hem or i in open_v or i not in th) else H.relax_weight(co[i].z, z_top, 0.03) for i in ids]
        out = F.smooth(vals, [[at[j] for j in nb[i] if j in at] for i in ids], rounds, alpha, mask)
        moved = 0.0
        for i in leg:
            r, z = out[at[i]][0], (rz[i][1] if i in rz else co[i].z)
            t = th[i]
            if outward:
                r = H.outward_only(r, cyl(co[i])[1])
            p = Vector((ax[0] + r * math.cos(t), ax[1] + r * math.sin(t), z))
            moved = max(moved, (p - co[i]).length)
            me.vertices[i].co = inv @ p
        rep[side] = {"verts": len(leg), "hem_verts": len(hem), "hem_z": round(hz, 4), "hem_z_was": z_span,
                     "axis": [round(ax[0], 4), round(ax[1], 4)], "moved_most_mm": round(1000 * moved, 1)}
    me.update()
    say("turnup relax", rep)
    return rep


def cuff_ring(gar, char, shoe, args) -> dict:
    """M2j: each trouser leg's turn-up built, as the waistband and straps are (Meshy's folded band was jagged and its
    fold's faces faced in over the calf: d67's 24 mm pokes stayed with the tied-face side). args.cuff_ring
    "z_top,height,thick,clear,stations[,lap[,most]]" (bind pose, m): per leg (|x| over 3 cm) the Meshy leg is cut on one
    level plane lap under z_top (a bisect: a clean edge, no per-face sawtooth) and everything under it goes; a
    closed rolled band (clothes_shell.cuff_profile), stations round the leg's axis, takes its place from z_top down
    height: its outer wall thick out of the leg's cloth just over it (and out of the shoe where they overlap, by
    at most most more), its
    inner wall just inside the leg at the top, narrowing to clear off the ankle's skin at the bottom (the opening
    shows no skin edge), the leg's cut edge between the walls under the roll. The leg's remaining vertices under
    z_top + 2 cm are held between the walls. Weights: the cut leg's nearest four vertices' (the shin's, as the old
    cuff's). UVs: the nearest old vertex's (plain_denim re-lays and tints them; its box's cut height should be
    z_top). Material: the leg's."""
    vals = floats(args.cuff_ring)
    z_top, height, thick, clear = vals[:4]
    n_st = int(vals[4])
    lap = vals[5] if len(vals) > 5 else 0.008
    most = vals[6] if len(vals) > 6 else 0.010  # the shoe pushes the outer wall out by at most this (d69: 90 mm)
    z_bot, z_cut = z_top - height, z_top - lap
    dg = bpy.context.evaluated_depsgraph_get()
    btree = BVHTree.FromObject(char, dg)
    stree = tree_of([shoe]) if shoe is not None else None
    mw = gar.matrix_world
    inv = mw.inverted()
    nm = mw.to_3x3().transposed()  # world -> local for a plane's normal (no shear)
    rep: dict = {"z_top": z_top, "height": height, "thick": thick, "clear": clear, "stations": n_st, "z_cut": z_cut}
    tris = 0
    for sgn, side in ((1.0, "left"), (-1.0, "right")):
        gt = tree_of([gar])
        bm = bmesh.new()
        bm.from_mesh(gar.data)
        dl = bm.verts.layers.deform.verify()
        uvl = bm.loops.layers.uv.active
        gname = {g.index: g.name for g in gar.vertex_groups}
        gi = {g.name: g.index for g in gar.vertex_groups}
        bm.verts.ensure_lookup_table()
        wco = {v: mw @ v.co for v in bm.verts}
        leg = [v for v in bm.verts if wco[v].x * sgn > 0.03 and wco[v].z < z_top + 0.12]
        above = [wco[v] for v in leg if z_top + 0.03 < wco[v].z < z_top + 0.10]
        old = [v for v in leg if z_bot - 0.03 < wco[v].z < z_top + 0.03 and v.link_faces]
        if len(above) < 8 or len(old) < 8:
            rep[side] = {"skipped": "no leg"}
            bm.free()
            continue
        ax = sum(above, Vector()) / len(above)
        # per station: the leg's cloth radius just over the cuff (the innermost hit), the skin's at the top and the
        # bottom, the shoe's outermost over the cuff's lower part
        r_leg, r_skin_t, r_skin_b, r_shoe, dirs = [], [], [], [], []
        for k in range(n_st):
            a = 2 * math.pi * k / n_st
            d = Vector((math.cos(a), math.sin(a), 0.0))
            dirs.append(d)
            o = Vector((ax.x, ax.y, z_top + 0.01))
            hit = gt.ray_cast(o, d, 0.25)[0]
            r_leg.append((hit - o).length if hit is not None else None)
            for z, acc in ((z_cut - 0.004, r_skin_t), (z_bot + 0.004, r_skin_b)):
                o = Vector((ax.x, ax.y, z))
                h = btree.ray_cast(o, d, 0.25)[0]
                acc.append((h - o).length if h is not None else None)
            far = 0.0
            if stree is not None:
                for z in (z_bot + 0.002, z_bot + 0.008, z_bot + 0.016):
                    o = Vector((ax.x, ax.y, z))
                    oo = o
                    for _n in range(6):
                        h = stree.ray_cast(oo, d, 0.25)[0]
                        if h is None:
                            break
                        if (h - o).length < 0.12:
                            far = max(far, (h - o).length)
                        oo = h + d * 1e-4
            r_shoe.append(far)
        known = sorted(r for r in r_leg if r is not None)
        if not known:
            rep[side] = {"skipped": "no leg hit"}
            bm.free()
            continue
        med = known[len(known) // 2]
        r_leg = H.circ_smooth([r if r is not None else med for r in r_leg], 2)
        r_out = H.circ_smooth([r + thick + min(max(0.0, sh + 0.003 - r - thick), most)
                               for r, sh in zip(r_leg, r_shoe)], 2)
        profs = []
        for k in range(n_st):
            ri_t = r_leg[k] - 0.003
            if r_skin_t[k] is not None:
                ri_t = max(ri_t, r_skin_t[k] + clear)
            ri_t = min(ri_t, r_out[k] - 0.004)
            ri_b = r_skin_b[k] + clear if r_skin_b[k] is not None else ri_t
            ri_b = max(0.005, min(ri_b, ri_t))
            profs.append(H.cuff_profile(r_out[k], ri_t, ri_b, z_top, z_bot))
        # the old leg's weights and UVs for the ring, by its nearest vertices (before the cut)
        kd = KDTree(len(old))
        for i, v in enumerate(old):
            kd.insert(wco[v], i)
        kd.balance()
        rows = [{gname[g]: w for g, w in v[dl].items() if g in gname} for v in old]
        uv_of = [v.link_loops[0][uvl].uv.copy() if v.link_loops else Vector((0.0, 0.0)) for v in old]
        mats: dict[int, int] = {}
        for v in old:
            for f in v.link_faces:
                mats[f.material_index] = mats.get(f.material_index, 0) + 1
        mat = max(mats, key=mats.get) if mats else 0
        # the cut: one plane, everything of this leg under it goes
        geom = list({e for v in leg for e in v.link_edges}) + list({f for v in leg for f in v.link_faces}) + leg
        bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-6, plane_co=inv @ Vector((0, 0, z_cut)),
                               plane_no=(nm @ Vector((0, 0, 1))).normalized(), clear_inner=True)
        gone = [f for f in bm.faces if all((mw @ v.co).z < z_cut + 1e-5 and (mw @ v.co).x * sgn > 0.03
                                           for v in f.verts)]
        bmesh.ops.delete(bm, geom=gone, context="FACES")
        loose = [v for v in bm.verts if not v.link_faces and (mw @ v.co).x * sgn > 0.03 and (mw @ v.co).z < z_top]
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
        # the leg's rest under z_top + 2 cm held between the walls
        held = 0
        for v in bm.verts:
            p = mw @ v.co
            if p.x * sgn <= 0.03 or p.z >= z_top + 0.02:
                continue
            dx, dy = p.x - ax.x, p.y - ax.y
            r = math.hypot(dx, dy)
            k = int(round((math.atan2(dy, dx) % (2 * math.pi)) / (2 * math.pi) * n_st)) % n_st
            hi_r = r_out[k] - 0.0025
            lo_r = profs[k][0][0] + 0.0015
            r2 = min(max(r, lo_r), hi_r) if lo_r < hi_r else (lo_r + hi_r) / 2
            if abs(r2 - r) > 1e-6 and r > 1e-6:
                v.co = inv @ Vector((ax.x + dx * r2 / r, ax.y + dy * r2 / r, p.z))
                held += 1
        # the ring
        npr = len(profs[0])
        grid = []
        for k in range(n_st):
            for r, z in profs[k]:
                q = Vector((ax.x, ax.y, z)) + dirs[k] * r
                v = bm.verts.new(inv @ q)
                near = kd.find_n(q, 4)
                row = H.blend_rows([(rows[i], max(dd, 1e-5)) for _c, i, dd in near])
                for b, x in row.items():
                    if b not in gi:
                        gi[b] = gar.vertex_groups.new(name=b).index
                    v[dl][gi[b]] = x
                grid.append((v, uv_of[near[0][1]]))
        faces = []
        for k in range(n_st):
            k2 = (k + 1) % n_st
            for j in range(npr):
                j2 = (j + 1) % npr
                ids = [k * npr + j, k2 * npr + j, k2 * npr + j2, k * npr + j2]
                f = bm.faces.new([grid[i][0] for i in ids])
                f.smooth = True
                f.material_index = mat
                for loop, i in zip(f.loops, ids):
                    loop[uvl].uv = grid[i][1]
                faces.append(f)
        bm.normal_update()
        f0 = faces[3]  # the outer wall's face: it must face away from the axis
        c0 = mw @ f0.calc_center_median()
        if (mw.to_3x3() @ f0.normal).dot(Vector((c0.x - ax.x, c0.y - ax.y, 0.0))) < 0:
            for f in faces:
                f.normal_flip()
        tris += 2 * len(faces)
        rep[side] = {"axis": [round(ax.x, 4), round(ax.y, 4)], "faces_left_under_cut": len(gone), "leg_held": held,
                     "r_out_mm_min_max": [round(1000 * min(r_out), 1), round(1000 * max(r_out), 1)],
                     "r_leg_mm_min_max": [round(1000 * min(r_leg), 1), round(1000 * max(r_leg), 1)],
                     "opening_mm_min_max": [round(1000 * min(p[-1][0] for p in profs), 1),
                                            round(1000 * max(p[-1][0] for p in profs), 1)],
                     "shoe_over_leg_stations": sum(1 for r, sh in zip(r_leg, r_shoe) if sh + 0.003 > r + thick)}
        bm.to_mesh(gar.data)
        bm.free()
        gar.data.update()
    rep["tris"] = tris
    say("cuff ring", rep)
    return rep


def plain_denim(gar, args) -> dict:
    """E1h: plain denim texels over the garment's areas whose own texels are wrong (Meshy's layered hip opening: a
    glossy, streaked patch; the axolotl's seat and front pockets: stretched stitch texels). Each box of args.plain
    ("x0,x1,y0,y1,z0,z1" for |x|, ';' between boxes; bind pose, m) on each side is one region: its denim faces (not
    the straps' and band's patch, not the bronze) are re-laid in UV on a vertical cylinder round the waist's axis
    (args.band_axis_y) at the garment's median texel density, into a free window of the maps that is filled with
    the plain denim rectangle args.strap_uv repeated mirrored (diffuse, roughness and normal; the normal's x or y
    turned over in a mirrored copy); one window for all the regions, as its texels are the same pattern everywhere.
    No vertex moves. Returns per region its faces and size, the window and the density."""
    boxes = [tuple(floats(b)) for b in args.plain.split(";") if b.strip()]
    tints = [b[6] if len(b) > 6 else 0.0 for b in boxes]  # M2f: a 7th value, the box's mix toward args.light_denim
    # M2g: an 8th value, a height: the tint only below it, by texel row (the turn-up's light cuff cut in a straight
    # line over the faces, not face by face), the box's regions laid on one height scale
    cuts = [b[7] if len(b) > 7 else -1.0 for b in boxes]
    # M2g: a 9th value, a gain on the window's diffuse (0 or 1: none): the back bib's flat panel faces away from the
    # light and read darker than its straps and the trousers, though its texels are the straps' own (d55: medians equal)
    gains = [b[8] if len(b) > 8 and b[8] > 0 else 1.0 for b in boxes]
    boxes = [b[:6] for b in boxes]
    rep = {"regions": []}
    maps = garment_maps(gar)
    dif = maps.get("diffuse")
    if not boxes or dif is None:
        rep["skipped"] = "no boxes" if not boxes else "no diffuse map"
        return rep
    w, h = dif.size
    me = gar.data
    mw = gar.matrix_world
    uvl = me.uv_layers.active.data
    own = getattr(args, "patch_rect", None)
    den_slot = {i for i, s in enumerate(gar.material_slots) if s.material and s.material.node_tree and any(
        n.type == "TEX_IMAGE" and n.image is dif for n in s.material.node_tree.nodes)}
    co = [mw @ v.co for v in me.vertices]

    def uv_c(p):
        return sum((Vector(uvl[k].uv) for k in p.loop_indices), Vector((0.0, 0.0))) / len(p.loop_indices)

    def ours(p):
        if own is None:
            return False
        c = uv_c(p)
        return own[0] - 1e-3 <= c.x <= own[1] + 1e-3 and own[2] - 1e-3 <= c.y <= own[3] + 1e-3

    regions = {}
    dens = []
    for p in me.polygons:
        c = sum((co[v] for v in p.vertices), Vector()) / len(p.vertices)
        hit = next((k for k, b in enumerate(boxes) if H.in_box(c.x, c.y, c.z, b)), None)
        if p.material_index in den_slot and not ours(p) and hit is not None:
            regions.setdefault((hit, 1 if c.x > 0 else -1), []).append(p.index)
            continue
        if p.material_index in den_slot and not ours(p):
            uv = [Vector(uvl[k].uv) for k in p.loop_indices]
            q = [co[v] for v in p.vertices]
            a3 = sum((q[i] - q[0]).cross(q[i + 1] - q[0]).length / 2 for i in range(1, len(q) - 1))
            a2 = sum(abs((uv[i] - uv[0]).cross(uv[i + 1] - uv[0])) / 2 for i in range(1, len(uv) - 1))
            if a3 > 1e-9 and a2 > 0:
                dens.append(math.sqrt(a2 * w * h / a3))
    d0 = float(np.median(dens)) * args.plain_density if dens else 0.0
    rep["texels_per_m"] = round(d0, 1)
    u0, u1, v0, v1 = floats(args.strap_uv)
    sx0, sx1, sy0, sy1 = int(u0 * w) + 1, int(u1 * w) - 1, int(v0 * h) + 1, int(v1 * h) - 1
    sw, sh = sx1 - sx0, sy1 - sy0
    me.calc_loop_triangles()
    pad = 4
    pxs = {k: pixels(img) for k, img in maps.items()}
    plan = []
    for (bi, side), fids in sorted(regions.items()):
        vids = sorted({v for i in fids for v in me.polygons[i].vertices})
        cen = sum((co[v] for v in vids), Vector()) / len(vids)
        a_ref = math.atan2(cen.x, -(cen.y - args.band_axis_y))
        radius = float(np.median([math.hypot(co[v].x, co[v].y - args.band_axis_y) for v in vids]))
        st = {v: H.cyl_coords(co[v].x, co[v].y, co[v].z, args.band_axis_y, a_ref, radius) for v in vids}
        lo = (min(a for a, _ in st.values()), min(b for _, b in st.values()))
        hi = (max(a for a, _ in st.values()), max(b for _, b in st.values()))
        plan.append((bi, side, fids, st, lo, hi))
    # one window of plain denim serves every region: it is the same repeated patch, so the regions share its texels;
    # when no window that size is free, the density steps down (the grain a little coarser) up to three times
    fset = {i for _b, _s, fids, *_r in plan for i in fids}
    tri = np.array([[uvl[t.loops[k]].uv[:] for k in range(3)] for t in me.loop_triangles
                    if t.polygon_index not in fset], dtype=np.float64)
    used = T.island_mask(tri, w, h, grow=1)
    at = None
    if not plan:  # no region found a denim face: report and skip instead of max() over an empty plan
        rep["skipped"] = "no region has denim faces"
        say("plain denim", rep)
        return rep
    light = floats(args.light_denim) if any(tints) else None  # 8-bit maps: pixels hold sRGB values
    d_base = d0
    for tint, cut, gain in sorted(set((tints[bi], cuts[bi], gains[bi]) for bi, *_r in plan)):
        group = [pl for pl in plan if (tints[pl[0]], cuts[pl[0]], gains[pl[0]]) == (tint, cut, gain)]
        glo = 0.0
        if cut >= 0:  # one height scale: a window row is one height in every region of the group
            glo = min(lo[1] for *_r, lo, _hi in group)
            ghi = max(hi[1] for *_r, _lo, hi in group)
            group = [(bi, side, fids, st, (lo[0], glo), (hi[0], ghi)) for bi, side, fids, st, lo, hi in group]
        d0 = d_base
        at = place = None
        for _ in range(4):
            pw = max(int(math.ceil((hi[0] - lo[0]) * d0)) for *_r, lo, hi in group) + 2 * pad
            ph = max(int(math.ceil((hi[1] - lo[1]) * d0)) for *_r, lo, hi in group) + 2 * pad
            at = T.free_rect(used, pw, ph, 6)
            if at is not None:
                break
            d0 *= 0.85
        key = ("" if tint == 0 else f"_tint{tint:g}") + ("" if cut < 0 else f"_cut{cut:g}") + (
            "" if gain == 1.0 else f"_gain{gain:g}")
        rep["texels_per_m_used" + key] = round(d0, 1)
        rep["window_px" + key] = None if at is None else [int(at[1]), int(at[0]), pw, ph]
        for bi, side, fids, st, lo, hi in group:
            rep["regions"].append({"box": bi, "side": side, "faces": len(fids), "tint": tint, "cut": cut,
                                   "size_mm": [round(1000 * (hi[0] - lo[0])), round(1000 * (hi[1] - lo[1]))]})
        if at is None:
            rep["window_px" + key] = "none free: left as it was"
            continue
        ry, rx = at
        used[ry:ry + ph, rx:rx + pw] = True
        ix = [H.mirror_tile(i, sw) for i in range(pw)]
        iy = [H.mirror_tile(j, sh) for j in range(ph)]
        for kind, img in maps.items():
            iw, ih = img.size
            fx, fy = iw / w, ih / h
            px = pxs[kind]
            cols = np.array([int((sx0 + i) * fx) for i, _m in ix])
            rows = np.array([int((sy0 + j) * fy) for j, _m in iy])
            blk = px[np.ix_(rows, cols)].copy()
            if kind == "normal":
                mx = np.array([m for _i, m in ix])
                my = np.array([m for _j, m in iy])
                blk[:, mx, 0] = 1.0 - blk[:, mx, 0]
                blk[my, :, 1] = 1.0 - blk[my, :, 1]
            if kind == "diffuse" and tint > 0:  # the denim's reverse side: its grain kept, lighter and bluer
                lum = blk[..., :3].mean(axis=2, keepdims=True)
                grain = lum / max(1e-6, float(lum.mean()))
                tt = tint
                if cut >= 0:  # per row: rows under the cut light, over it dark, a 2 mm blend
                    tt = tint * np.array([H.cut_ramp(glo + (j - pad) / d0, cut, 0.002) for j in range(ph)])[:, None, None]
                blk[..., :3] = (1 - tt) * blk[..., :3] + tt * np.array(light)[None, None, :] * grain
            if kind == "diffuse" and gain != 1.0:
                blk[..., :3] = np.clip(blk[..., :3] * gain, 0.0, 1.0)
            r0, c0 = int(ry * fy), int(rx * fx)
            tw, th = int(pw * fx), int(ph * fy)
            ys = (np.arange(th) / fy).astype(int).clip(0, ph - 1)
            xs = (np.arange(tw) / fx).astype(int).clip(0, pw - 1)
            px[r0:r0 + th, c0:c0 + tw] = blk[np.ix_(ys, xs)]
        for bi, side, fids, st, lo, hi in group:
            for i in fids:
                p = me.polygons[i]
                for li, v in zip(p.loop_indices, p.vertices):
                    s_, t_ = st[v]
                    uvl[li].uv = ((rx + pad + (s_ - lo[0]) * d0) / w, (ry + pad + (t_ - lo[1]) * d0) / h)
    say("plain denim", rep)
    for kind, img in maps.items():
        img.pixels[:] = pxs[kind].ravel()
        img.update()
    me.update()
    return rep


def flat_back(gar, char, args) -> dict:
    """M2d: the back panel's top as one stiff panel (her bib's treatment, E1i): Meshy's panel has a vertical fold at
    its apex. args.flat_back "blend,radius,band,clear": each back vertex over the waist (y > 0, |x| within the panel's
    widest half width + 1 cm) takes the depth clothes_shell.panel_fit gives from the vertices within radius in x and
    band in z (a quadratic across, so the back's round stays and the fold goes) less all layers' mean within 1 cm
    (so a hem's layer keeps its offset), eased in over blend m above the waist
    (the band stays), never nearer the body's back than clear; the outline (x, z) and the UVs stay. Its weights go to
    clothes_shell.chain_row along args.bib_chain by the same ease, so it moves as one piece with the spine."""
    blend, rad, band, clear = floats(args.flat_back)
    z_w = args.waist
    _y0, _apex, hw_w, hw_a = floats(args.back)
    me = gar.data
    mw = gar.matrix_world
    inv = mw.inverted()
    co = [mw @ v.co for v in me.vertices]
    ids = [i for i, p in enumerate(co) if p.y > 0 and p.z > z_w + 1e-4 and abs(p.x) <= max(hw_w, hw_a) + 0.01]
    if not ids:
        return {"skipped": "no back panel vertices"}
    kd = KDTree(len(ids))
    for k, i in enumerate(ids):
        kd.insert((co[i].x, 0.0, co[i].z), k)
    kd.balance()
    # the body's back surface: per vertex the most backward body point within 1 cm in x and z
    cm = char.matrix_world
    bpts = [cm @ v.co for v in char.data.vertices]
    bpts = [p for p in bpts if p.y > 0 and p.z > z_w - 0.02]
    bkd = KDTree(max(1, len(bpts)))
    for k, p in enumerate(bpts):
        bkd.insert((p.x, 0.0, p.z), k)
    bkd.balance()
    knots = chain_knots(char, getattr(args, "bib_chain", ""))
    names = {g.index: g.name for g in gar.vertex_groups}
    groups = {g.name: g for g in gar.vertex_groups}
    new_co, rows, most, floor_hit = {}, [], 0.0, 0
    for k, i in enumerate(ids):
        p = co[i]
        w = H.ease(p.z, z_w, blend)
        if w <= 0:
            continue
        nb = [(co[ids[j]].x - p.x, co[ids[j]].z - p.z, co[ids[j]].y) for _c, j, _d in kd.find_range((p.x, 0.0, p.z), rad)
              if abs(co[ids[j]].z - p.z) <= band]
        # every layer moves alike (a hem's or a pocket's layer keeps its own offset): by the fit less the mean of
        # all layers within 1 cm
        lm = [co[ids[j]].y for _c, j, _d in kd.find_range((p.x, 0.0, p.z), 0.01)]
        y = p.y + H.panel_fit(nb) - sum(lm) / len(lm)
        under = [bpts[j].y for _c, j, _d in bkd.find_range((p.x, 0.0, p.z), 0.01)]
        if under and y < max(under) + clear:
            y = max(under) + clear
            floor_hit += 1
        d = w * (y - p.y)
        new_co[i] = Vector((p.x, p.y + d, p.z))
        most = max(most, abs(d))
        if knots:
            own = {names[g.group]: g.weight for g in me.vertices[i].groups if g.group in names}
            rows.append((i, H.follow_row(own, H.chain_row(p.z, knots), w)))
    for i, q in new_co.items():
        me.vertices[i].co = inv @ q
    for i, row in rows:
        v = me.vertices[i]
        for g in list(v.groups):
            gar.vertex_groups[g.group].remove([i])
        for b, x in row.items():
            if b not in groups:
                groups[b] = gar.vertex_groups.new(name=b)
            groups[b].add([i], x, "REPLACE")
    me.update()
    return {"verts": len(ids), "moved": len(new_co), "max_move_mm": round(1000 * most, 1), "at_clear": floor_hit,
            "reweighted": len(rows)}


def chain_knots(char, spec: str) -> list[tuple[float, str]]:
    """E1i2: the knots of clothes_shell.chain_row from spec "Bone,Bone,..." (up the spine): each bone's mid height in
    the bind pose (world), from char's armature; empty spec or no armature: []."""
    names = [b for b in spec.split(",") if b.strip()]
    arm = next((m.object for m in char.modifiers if m.type == "ARMATURE" and m.object), None)
    if not names or arm is None:
        return []
    out = []
    for b in names:
        bone = arm.data.bones[b.strip()]
        out.append(((arm.matrix_world @ ((bone.head_local + bone.tail_local) / 2)).z, b.strip()))
    return out


def flat_bib(gar, char, args) -> dict:
    """E1i: the bib as a flat, stiff panel (the concept): her fit made the bib follow each breast, so the denim bent
    over her chest, and its top sat under the bust. args.flat_bib "blend,curve,radius,clear":
    - args.bib_raise "dz,b0,b1" (optional) first raises the bib: everything over the waist + b1 goes up dz, the band
      from waist + b0 to waist + b1 stretches (its texels are re-laid plain: a --plain box is added), so the top
      edge and the pocket sit over the bust as on the concept; args.bib's top and args.bib_raise_dz follow (the
      straps' fronts move up with it);
    - then each bib vertex (front, |x| within the bib, over the waist) moves forward only, by the offset between the
      bib's smoothed surface S (every layer's mean within radius in x and z, averaged twice: every layer moves alike,
      so the pocket keeps its own layer over it) and the target T(x, z) = hull(z) + c * x^2 (a cylinder across,
      which stiff denim can take; curve < 0: c fitted to the belly's rows just over the eased band), where hull is
      the front hull (clothes_shell.front_hull) per 1 cm of height of the smaller of S - c x^2 and the body's front
      less clear - c x^2: the taut line from the waistband over the chest's most forward points to the top edge.
      The move eases in over blend m above the waist (clothes_shell.ease), so the waistband stays;
    - each moved vertex's weights blend toward the mean over its 3 cm row of the body's weights under the panel (the
      panel moves as one with the chest, no fold); E1i2: with args.bib_chain "Hips,Spine,Chest,UpperChest" toward
      clothes_shell.chain_row at its height instead (the rows' means folded the raised top under the bust in Jog).
    No face is added or removed; the UVs stay (but the stretched band's)."""
    blend, curve, rad, clear = floats(args.flat_bib)
    z_w = args.waist
    bib_hw, bib_top = floats(args.bib)
    me = gar.data
    mw = gar.matrix_world
    inv = mw.inverted()
    co = [mw @ v.co for v in me.vertices]
    ids = [i for i, p in enumerate(co) if p.y < 0 and abs(p.x) <= bib_hw + 1e-3 and p.z > z_w - 1e-4]
    if not ids:
        return {"skipped": "no bib vertices"}
    rep = {}
    dz, b0, b1 = floats(args.bib_raise) if getattr(args, "bib_raise", "") else (0.0, 0.0, 0.0)
    if dz > 0:
        for i in ids:
            z = co[i].z
            if z >= z_w + b1:
                z += dz
            elif z > z_w + b0:
                z += dz * (z - z_w - b0) / (b1 - b0)
            co[i] = Vector((co[i].x, co[i].y, z))
        bib_top += dz
        args.bib = f"{bib_hw:.4f},{bib_top:.4f}"
        args.bib_raise_dz = dz
        box = f"0,{bib_hw + 0.002:.4f},-0.4,0,{z_w + b0 - 0.002:.4f},{z_w + b1 + dz + 0.002:.4f}"
        args.plain = ";".join(b for b in (args.plain, box) if b)
        rep["raised"] = {"dz": dz, "band_z": [round(z_w + b0, 4), round(z_w + b1 + dz, 4)], "bib_top": bib_top,
                         "plain_box": box}
    kd = KDTree(len(ids))
    for k, i in enumerate(ids):
        kd.insert((co[i].x, 0.0, co[i].z), k)
    kd.balance()
    ys = np.array([co[i].y for i in ids])
    near = [[k for _c, k, _d in kd.find_range((co[i].x, 0.0, co[i].z), rad)] for i in ids]
    base = np.array([np.mean(ys[n]) for n in near])  # every layer's mean: each layer then moves alike
    s = np.array([np.mean(base[n]) for n in near])
    xs = np.array([co[i].x for i in ids])
    zs = np.array([co[i].z for i in ids])
    fit_c = None
    if curve < 0:  # the curve across from the belly's rows over the eased band (a + c x^2, least squares)
        m = (zs > z_w + blend) & (zs < z_w + blend + 0.04)
        if m.sum() >= 6:
            fit_c = float(np.linalg.lstsq(np.stack([np.ones(int(m.sum())), xs[m] ** 2], 1), s[m], rcond=None)[0][1])
        curve = max(0.0, fit_c or 0.0)
    bins = {}
    for z, r in zip(zs, s - curve * xs * xs):
        b = int(math.floor((z - z_w) / 0.01))
        bins[b] = min(bins.get(b, r), r)
    cm = char.matrix_world
    body_prof = {}
    for v in char.data.vertices:
        p = cm @ v.co
        if p.y < 0 and abs(p.x) <= bib_hw + 0.01 and z_w + blend <= p.z <= bib_top + 0.01:
            b = int(math.floor((p.z - z_w) / 0.01))
            r = p.y - clear - curve * p.x * p.x
            body_prof[b] = min(body_prof.get(b, r), r)
            if b in bins:
                bins[b] = min(bins[b], r)
    prof = [(min(max(z_w + 0.01 * (b + 0.5), zs.min()), zs.max()), r) for b, r in sorted(bins.items())]
    hull = H.front_hull(prof)
    body = body_weights(char)
    rows = []
    for k, i in enumerate(ids):
        w = H.ease(zs[k], z_w, blend)
        d = w * min(0.0, H.hull_at(hull, zs[k]) + curve * xs[k] ** 2 - s[k])
        co[i] = co[i] + Vector((0.0, d, 0.0))
        rows.append((w, weight_row(body, co[i]) if w > 0 else {}))
    moves = [(mw @ me.vertices[i].co - co[i]).length for i in ids]
    bib_set = set(ids)
    areas0 = {p.index: p.area for p in me.polygons if all(v in bib_set for v in p.vertices)}
    groups = {g.name: g for g in gar.vertex_groups}
    names = {g.index: g.name for g in gar.vertex_groups}
    new_rows = []
    knots = chain_knots(char, getattr(args, "bib_chain", ""))
    if knots:
        rep["chain_knots"] = [(round(z, 4), b) for z, b in knots]
    for k, i in enumerate(ids):
        w = rows[k][0]
        if w <= 0:
            continue
        if knots:  # E1i2: by height alone, so the panel moves as one stiff piece with the spine (no fold)
            own = {names[g.group]: g.weight for g in me.vertices[i].groups if g.group in names}
            new_rows.append((i, H.follow_row(own, H.chain_row(co[i].z, knots), w)))
            continue
        mean: dict[str, float] = {}
        near_z = [kk for kk in range(len(ids)) if abs(zs[kk] - zs[k]) < 0.015 and rows[kk][0] > 0]
        for kk in near_z:
            for b, x in rows[kk][1].items():
                mean[b] = mean.get(b, 0.0) + x / len(near_z)
        own = {names[g.group]: g.weight for g in me.vertices[i].groups if g.group in names}
        new_rows.append((i, H.follow_row(own, mean, w)))
    for i in ids:
        me.vertices[i].co = inv @ co[i]
    for i, row in new_rows:
        v = me.vertices[i]
        for g in list(v.groups):
            gar.vertex_groups[g.group].remove([i])
        for b, x in row.items():
            if b not in groups:
                groups[b] = gar.vertex_groups.new(name=b)
            groups[b].add([i], x, "REPLACE")
    me.update()
    ratio = sorted(me.polygons[f].area / a for f, a in areas0.items() if a > 1e-9)
    pick = lambda q: round(ratio[min(len(ratio) - 1, int(q * len(ratio)))], 3) if ratio else None
    rep.update({"verts": len(ids), "moved": sum(m > 1e-5 for m in moves), "curve": round(curve, 3),
                "curve_fit": fit_c, "max_move_mm": round(1000 * max(moves), 1),
                "hull_zy": [(round(z, 3), round(y, 4)) for z, y in hull],
                "body_front_zy": [(round(z_w + 0.01 * (b + 0.5), 3), round(r + clear, 4))
                                  for b, r in sorted(body_prof.items())],
                "area_ratio_p1_p50_p99": [pick(0.01), pick(0.5), pick(0.99)], "faces": len(ratio)})
    say("flat bib", rep)
    return rep


def back_join(gar, args) -> dict:
    """M2e: the straps' back ends glued onto the back panel, so its top moves as one piece (the Jog close-up's
    crumpled top: the built straps reached args.strap_back_below under the panel's apex 12 to 15 mm off it, crossed
    over its top, and took the body's weights under them (UpperChest, the shoulders) where the panel had the spine
    chain's, so in motion their square ends stood off it as loose flaps). args.back_join "blend,gap": each strap
    vertex with the panel under it (a ray in along its row's normal from 3 cm out, the panel being the garment's
    back faces over the waist, the straps, band and buckles left out) lies gap (plus its lip's own height, the left
    strap's 1.5 mm over the right kept) outside the panel and takes the panel face's weights (its corners by
    nearness); the rows in front of that run take its first row's move and weights eased out over blend m along
    the strap (clothes_shell.join_rows). The panel and the straps' outline stay; nothing else moves."""
    blend, gap = floats(args.back_join)
    grids = getattr(args, "strap_grids", None)
    if not grids:
        return {"skipped": "no straps"}
    _y0, z_apex, hw_w, hw_a = floats(args.back)
    z_top = max(z_apex, getattr(args, "back_bib_top", z_apex))  # M2f: the built back bib reaches higher
    me = gar.data
    mw = gar.matrix_world
    inv = mw.inverted()
    co = [mw @ v.co for v in me.vertices]
    strap = {i for g in grids for i in g["ids"]}
    # (bmesh reuses deleted vertices' slots, so the strips' indices are not all past the Meshy garment's)
    panel = [list(p.vertices) for p in me.polygons
             if not any(i in strap for i in p.vertices)
             and all(co[i].y > 0 and args.waist - 0.01 < co[i].z < z_top + 0.03
                     and abs(co[i].x) < max(hw_w, hw_a) + 0.02 for i in p.vertices)]
    if not panel:
        return {"skipped": "no back panel faces"}
    tree = BVHTree.FromPolygons(co, panel)
    names = {g.index: g.name for g in gar.vertex_groups}
    groups = {g.name: g for g in gar.vertex_groups}
    rows_w = [{names[g.group]: g.weight for g in v.groups if g.group in names and g.weight > 0} for v in me.vertices]
    rep = {"glued_rows": [], "eased_rows": [], "moved_most_mm": 0.0, "verts": 0}
    for g in grids:
        nr, nc = g["rows"], g["cols"]
        moves, wts = [], []  # per row: per column (move along n, weights) or None
        for r in range(nr):
            n = Vector(g["nt"][r])
            row_m, row_w = [], []
            for c in range(nc):
                i = g["ids"][r * nc + c]
                p = co[i]
                loc, _nor, fi, _d = tree.ray_cast(p + n * 0.03, -n, 0.06)
                if loc is None:
                    row_m.append(None)
                    row_w.append(None)
                    continue
                want = gap + g["hgts"][c] + g["extra"]
                row_m.append((loc + n * max(0.0005, want) - p).dot(n))
                ids = panel[fi]
                row_w.append(F.blend_rows([rows_w[k] for k in ids], [1.0 / max(1e-4, (co[k] - loc).length) for k in ids]))
            # M2f: a lip column past the panel's edge (the built back bib narrows down) takes its nearest hit's move
            # and weights; a row counts when its flat columns all hit
            ok = all(m is not None for m in row_m[1:-1]) if nc > 2 else all(m is not None for m in row_m)
            if ok:
                for c in (0, nc - 1):
                    if row_m[c] is None:
                        src = 1 if c == 0 else nc - 2
                        row_m[c], row_w[c] = row_m[src] - g["hgts"][src] + g["hgts"][c], row_w[src]
            moves.append(row_m if ok else None)
            wts.append(row_w if ok else None)
        plan = H.join_rows([None if m is None else 0.0 for m in moves], g["along"], blend)
        glued = eased = 0
        for r, (share, src) in enumerate(plan):
            if src is None or share <= 0:
                continue
            glued += src == r
            eased += src != r
            n = Vector(g["nt"][r])
            for c in range(nc):
                i = g["ids"][r * nc + c]
                m = share * moves[src][c]
                me.vertices[i].co = inv @ (co[i] + n * m)
                rep["moved_most_mm"] = max(rep["moved_most_mm"], round(1000 * abs(m), 1))
                row = H.follow_row(rows_w[i], wts[src][c], share)
                v = me.vertices[i]
                for gg in list(v.groups):
                    gar.vertex_groups[gg.group].remove([i])
                for b, x in row.items():
                    if b not in groups:
                        groups[b] = gar.vertex_groups.new(name=b)
                    groups[b].add([i], x, "REPLACE")
                rep["verts"] += 1
        rep["glued_rows"].append(glued)
        rep["eased_rows"].append(eased)
    me.update()
    return rep


def _quad_fit(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """Least-squares y = a + b x + c x^2 (fewer than 3 points: their mean, flat)."""
    if len(xs) < 3:
        m = sum(ys) / max(1, len(ys))
        return m, 0.0, 0.0
    a = np.vstack([np.ones(len(xs)), np.array(xs), np.array(xs) ** 2]).T
    sol = np.linalg.lstsq(a, np.array(ys), rcond=None)[0]
    return float(sol[0]), float(sol[1]), float(sol[2])


def back_bib(gar, char, args) -> dict:
    """M2f: her back bib to the approved turnaround's back view, in place of Meshy's low V panel (it ended at the
    shoulder blades' foot and the straps met in a lump at the waistband: from behind she read as jeans with
    suspenders). args.back_bib "z_c,z_v,hw_b,hw_t,x_v,off,border": Meshy's back panel over the waist goes; a new
    stiff panel (clothes_shell.back_bib_grid's outline: sides from half width hw_b at the waist to hw_t at the top
    corners' height z_c, the V top down to z_v) is built from rays at the body's back, each row one quadratic across
    (the spine's groove bridged, as stiff denim does) at least off clear of the body, its rows under the waist tucked
    2 mm under the Meshy band, its sides and top folded args.strap_lip toward the body; one piece with the spine
    (clothes_shell.chain_row along args.bib_chain). Its border faces carry a 'bib_border' UV (across, along) and a
    'bib_kind' face flag for back_bib_uv, which lays the straps' stitched patch on them once straps() has made it;
    the inner faces get plain texels from a --plain box. The straps' back ends are aimed at its top corners
    (clothes_dress: strap_back_z)."""
    z_c, z_v, hw_b, hw_t, x_v, off, border = floats(args.back_bib)
    z_w = args.waist
    back_y = floats(args.back)[0]
    z0 = z_w - 0.008
    g = H.back_bib_grid(z0, z_c, z_v, hw_b, hw_t, x_v, border)
    mw = gar.matrix_world
    inv = mw.inverted()
    me = gar.data
    bm = bmesh.new()
    bm.from_mesh(me)
    gone = [f for f in bm.faces if (lambda c: c.y > back_y and c.z > z_w + 1e-4)(mw @ f.calc_center_median())]
    mats = [f.material_index for f in gone]
    mat = max(set(mats), key=mats.count) if mats else 0
    bmesh.ops.delete(bm, geom=gone, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    gco = [mw @ v.co for v in bm.verts]
    gtree = BVHTree.FromPolygons(gco, [[v.index for v in f.verts] for f in bm.faces]) if bm.faces else None
    bm.verts.index_update()
    body = body_weights(char)
    btree = body["tree"]
    pts, nc, nr = g["points"], g["cols"], g["rows"]
    d = Vector((0.0, -1.0, 0.0))

    def hit_y(tree, x, z):
        if tree is None:
            return None
        loc = tree.ray_cast(Vector((x, 0.5, z)), d, 1.0)[0]
        return None if loc is None else loc.y
    by = [hit_y(btree, x, z) for x, z in pts]
    known = [y for y in by if y is not None]
    if not known:
        bm.free()
        return {"skipped": "no body behind the panel"}
    by = [y if y is not None else max(known) for y in by]
    ys = [0.0] * len(pts)
    tucked = 0
    for r in range(nr):
        ids = range(r * nc, (r + 1) * nc)
        z_r = max(pts[i][1] for i in ids)
        if z_r <= z_w + 1e-4:  # under the band: tucked 2 mm under the Meshy band, never nearer the body than 2 mm
            for i in ids:
                gy = hit_y(gtree, *pts[i])
                ys[i] = max(by[i] + 0.002, gy - 0.002 if gy is not None else by[i] + off)
                tucked += 1
            continue
        a, b, c = _quad_fit([pts[i][0] for i in ids], [by[i] + off for i in ids])
        fit = [a + b * pts[i][0] + c * pts[i][0] ** 2 for i in ids]
        lift = max(0.0, max(by[i] + off - f for i, f in zip(ids, fit)))
        for i, f in zip(ids, fit):
            ys[i] = f + lift
    for _ in range(2):  # smooth up each column (the free rows), never nearer the body than off
        prev = ys[:]
        for r in range(1, nr - 1):
            for c in range(nc):
                i = r * nc + c
                if pts[i][1] <= z_w + 1e-4 or pts[(r - 1) * nc + c][1] <= z_w + 1e-4:
                    continue
                ys[i] = max(by[i] + off, (prev[i - nc] + 2 * prev[i] + prev[i + nc]) / 4)
    knots = chain_knots(char, getattr(args, "bib_chain", ""))
    dl = bm.verts.layers.deform.verify()
    gi = {gg.name: gg.index for gg in gar.vertex_groups}
    vs = []
    for i, (x, z) in enumerate(pts):
        y = ys[i]
        if g["edge"][i]:
            y = max(by[i] + 0.002, y - args.strap_lip)
        v = bm.verts.new(inv @ Vector((x, y, z)))
        row = H.chain_row(z, knots) if knots else weight_row(body, Vector((x, by[i], z)))
        for bname, wt in row.items():
            if bname not in gi:
                gi[bname] = gar.vertex_groups.new(name=bname).index
            v[dl][gi[bname]] = wt
        vs.append(v)
    uv = bm.loops.layers.uv.active
    bord = bm.loops.layers.uv.new("bib_border")
    kind = bm.faces.layers.int.new("bib_kind")
    pu0, pu1, pv0, pv1 = floats(args.strap_uv)
    centre = ((pu0 + pu1) / 2, (pv0 + pv1) / 2)
    faces = []
    for q, k, buv in zip(g["faces"], g["kind"], g["border_uv"]):
        f = bm.faces.new([vs[j] for j in q])
        f.smooth = True
        f.material_index = mat
        f[kind] = {"inner": 0, "side": 1, "top": 2}[k]
        for n, loop in enumerate(f.loops):
            loop[uv].uv = centre
            loop[bord].uv = buv[n] if buv else (0.0, 0.0)
        faces.append(f)
    bm.normal_update()
    mid = faces[len(faces) // 2]
    if (mw.to_3x3() @ mid.normal).y < 0:
        for f in faces:
            f.normal_flip()
    bm.to_mesh(me)
    bm.free()
    me.update()
    args.back_bib_top = z_c
    gap = [ys[i] - by[i] for i in range(len(pts))]
    rep = {"meshy_faces_removed": len(gone), "verts": len(pts), "tris": 2 * len(faces), "tucked_verts": tucked,
           "off_body_mm_min_max": [round(1000 * min(gap), 1), round(1000 * max(gap), 1)],
           "outline": {"z0": z0, "z_c": z_c, "z_v": z_v, "hw_b": hw_b, "hw_t": hw_t, "x_v": x_v}}
    say("back bib", rep)
    return rep


def back_bib_uv(gar, args) -> dict:
    """M2f: back_bib's border faces take the straps' stitched patch (args.patch_rect, made by straps()): across the
    border from its lip (u at the patch's edge) inward as on a strap of args.strap_width, along it mirrored like the
    straps (clothes_strap.mirror_v); then the helper UV map and face flag go (not exported)."""
    me = gar.data
    rect = getattr(args, "patch_rect", None)
    if "bib_border" not in me.uv_layers or "bib_kind" not in me.attributes:
        return {"skipped": "no back bib"}
    n = 0
    if rect is not None:
        u0, u1, v0, v1 = rect
        lip_u = args.strap_lip_u
        uvl = me.uv_layers.active.data
        bl = me.uv_layers["bib_border"].data
        kinds = me.attributes["bib_kind"].data
        for p in me.polygons:
            if kinds[p.index].value <= 0:
                continue
            n += 1
            for li in p.loop_indices:
                a, s = bl[li].uv
                fr = 0.0 if a <= 1e-6 else lip_u + (1 - 2 * lip_u) * min(1.0, a / args.strap_width)
                uvl[li].uv = (u0 + (u1 - u0) * fr, S.mirror_v(s + 1.0, v0, v1, args.strap_texels))
    me.uv_layers.remove(me.uv_layers["bib_border"])
    me.attributes.remove(me.attributes["bib_kind"])
    me.update()
    return {"border_faces": n, "patch": list(rect) if rect else None}
