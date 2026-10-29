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


def _bisect(bm, mw, pick, co, no, outer: bool | None = True) -> None:
    """Cuts the faces pick(world centre) by the world plane (co, no); clears its positive side (outer), its negative
    (False) or nothing (None: the cut alone)."""
    inv = mw.inverted()
    faces = [f for f in bm.faces if pick(mw @ f.calc_center_median())]
    if not faces:
        return
    edges = {e for f in faces for e in f.edges}
    verts = {v for f in faces for v in f.verts}
    nl = (mw.to_3x3().transposed() @ Vector(no)).normalized()
    bmesh.ops.bisect_plane(bm, geom=list(verts) + list(edges) + faces, plane_co=inv @ Vector(co), plane_no=nl,
                           clear_outer=outer is True, clear_inner=outer is False)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")


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
    _bisect(bm, mw, front, (bib_hw, 0, 0), (1, 0, 0))
    _bisect(bm, mw, front, (-bib_hw, 0, 0), (-1, 0, 0))
    _bisect(bm, mw, front, (0, 0, bib_top), (0, 0, 1))
    dz, dx = z_apex - z_w, hw_a - hw_w
    ln = math.hypot(dz, dx)
    for sgn in (1, -1):
        _bisect(bm, mw, back, (sgn * hw_w, 0, z_w), (sgn * dz / ln, 0, -dx / ln))
    _bisect(bm, mw, back, (0, 0, z_apex), (0, 0, 1))
    side = lambda c: c.z > z_w and not (c.y < 0 and abs(c.x) < bib_hw) and not (c.y > back_y and abs(c.x) < hw_w)
    _bisect(bm, mw, side, (0, 0, z_w), (0, 0, 1))
    bm.faces.ensure_lookup_table()
    gone = [f for f in bm.faces if not H.keep_face(*(mw @ f.calc_center_median()), z_w, bib_hw + 1e-3,
                                                    bib_top + 1e-3, back_y, z_apex + 1e-3, hw_w + 1e-3, hw_a + 1e-3)]
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
    bm.to_mesh(me)
    bm.free()
    me.update()
    rep = {"faces_before": n0, "faces_after": n1, "band_faces_removed": n_band, "edge_peeled": n_peel, "waist": z_w, "bib": [bib_hw, bib_top], "back": floats(args.back)}
    say("garment cut", rep)
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
        for f in bm.faces:
            if not zone(mw @ f.calc_center_median()):
                continue
            uvs = [l[uvl].uv for l in f.loops]
            cu = sum((u for u in uvs), Vector((0.0, 0.0))) / len(uvs)
            hits = 0
            for u in [cu] + [cu.lerp(u, 0.7) for u in uvs]:
                r, g, b = px[min(h - 1, max(0, int(u.y * h))), min(w - 1, max(0, int(u.x * w))), :3]
                hits += H.shirt_texel(float(r), float(g), float(b))
            if hits >= len(uvs):
                white.append(f)
        rep["shirt_faces"] = len(white)
        if white:
            bmesh.ops.delete(bm, geom=white, context="FACES")
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


def follow_panels(top, gar, args) -> dict:
    """The top under the bib, the back panel and the trousers' waist takes their weights (the fit's), by the share
    of five rays from each vertex (its normal and four tilted by args.shell_hide_tilt) that meet the garment within
    args.shell_follow m (clothes_shell.follow_row): it moves with the panels and stays under them (C1h: the body's
    weights let it poke through the bib's sides by up to 10 mm in the clips, clothes_proof's top_under_panels)."""
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
    its normal and four rays tilted by args.shell_hide_tilt round it all meet the panel within args.shell_hide."""
    return c.z > z_full and ray_share(tree, c, n, args.shell_hide, args.shell_hide_tilt) == 1


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
    mw = gar.matrix_world
    inv = mw.inverted()
    me = gar.data
    steps = max(8, int(round((ts[-1] - ts[0]) / math.radians(args.shell_strap_step))))
    angles = [ts[0] + (ts[-1] - ts[0]) * i / steps for i in range(steps + 1)]
    n_flat = args.shell_strap_lats - 2
    lats = [(-half, -lip)] + [(-half + 2 * half * k / (n_flat - 1), 0.0) for k in range(n_flat)] + [(half, -lip)]
    ufr = H.lat_us(len(lats), args.strap_lip_u)
    rect, prep = strap_patch(gar, args, ufr)
    u0, u1, v0, v1 = rect
    rep, plans = {"patch": prep}, []
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
    for pl in plans:
        vs = []
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
                if under:  # the ends run under the Meshy bib's or back panel's bottom
                    hit = gtree.ray_cast(p + n * 1e-4, n, 0.05)[0]
                    if hit is not None:
                        off = max(top_off + 0.001, min(off, (hit - p).length - 0.002))
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
                "low_mm_min_max": [round(1000 * min(offs), 1), round(1000 * max(offs), 1)], "ends_under": sum(ends)}
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
