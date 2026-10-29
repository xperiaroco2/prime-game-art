"""The dungarees' upper body as our own clean pieces, inside Blender (art #196, clothes step 2, C1f): clothes_dress.py
--shell calls cut_garment, shell and straps in that order (the maths: clothes_shell.py; the route: docs/clothes.md).

- cut_garment: the Meshy garment keeps the trousers below the waistband, the bib and the back panel; their edges are
  cut by planes (bmesh bisect), so they are straight, not a row of whole faces.
- shell: the striped top, a copy of the body's torso and arm faces moved out along their normals, cut at the crew
  neck, the wrists and the hem, a rolled lip at the collar and cuffs, the body's own weights; its stripes and a soft
  cotton normal map are made here, darkened by an ambient-occlusion bake (Cycles) where it fits.
- straps: two strips about 3.5 cm wide from the bib's top corners over the shoulders down to the back panel's V,
  over the shell and the bib, weighted like the body under them; their UVs on the garment's plain denim.
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


def _bisect(bm, mw, pick, co, no, outer=True) -> None:
    """Cuts the faces pick(world centre) by the world plane (co, no); clears its positive side (outer) or negative."""
    inv = mw.inverted()
    faces = [f for f in bm.faces if pick(mw @ f.calc_center_median())]
    if not faces:
        return
    edges = {e for f in faces for e in f.edges}
    verts = {v for f in faces for v in f.verts}
    nl = (mw.to_3x3().transposed() @ Vector(no)).normalized()
    bmesh.ops.bisect_plane(bm, geom=list(verts) + list(edges) + faces, plane_co=inv @ Vector(co), plane_no=nl,
                           clear_outer=outer, clear_inner=not outer)
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
    front = lambda c: c.y < 0 and c.z > z_w - 0.01
    back = lambda c: c.y > back_y and c.z > z_w - 0.01
    _bisect(bm, mw, front, (bib_hw, 0, 0), (1, 0, 0))
    _bisect(bm, mw, front, (-bib_hw, 0, 0), (-1, 0, 0))
    _bisect(bm, mw, front, (0, 0, bib_top), (0, 0, 1))
    dz, dx = z_apex - z_w, hw_a - hw_w
    ln = math.hypot(dz, dx)
    for sgn in (1, -1):
        _bisect(bm, mw, back, (sgn * hw_w, 0, z_w), (sgn * dz / ln, 0, -dx / ln))
    _bisect(bm, mw, back, (0, 0, z_apex), (0, 0, 1))
    side = lambda c: c.z > z_w - 0.01 and not (c.y < 0 and abs(c.x) < bib_hw) and not (c.y > back_y and abs(c.x) < hw_w)
    _bisect(bm, mw, side, (0, 0, z_w), (0, 0, 1))
    bm.faces.ensure_lookup_table()
    gone = [f for f in bm.faces if not H.keep_face(*(mw @ f.calc_center_median()), z_w, bib_hw + 1e-3,
                                                    bib_top + 1e-3, back_y, z_apex + 1e-3, hw_w + 1e-3, hw_a + 1e-3)]
    bmesh.ops.delete(bm, geom=gone, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    n1 = len(bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.update()
    rep = {"faces_before": n0, "faces_after": n1, "waist": z_w, "bib": [bib_hw, bib_top], "back": floats(args.back)}
    say("garment cut", rep)
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
    lum = cols @ np.array([0.2126, 0.7152, 0.0722])
    cut = np.median(lum)
    return np.median(cols[lum < cut], axis=0), np.median(cols[lum >= cut], axis=0)


def stripe_image(navy, white, period, duty, per_m) -> np.ndarray:
    """The top's albedo (linear, h x w x 3): per island, rows of navy and white from its edge (V0), per_m UV units
    per metre in v."""
    lin_n, lin_w = T.to_linear(np.asarray(navy)), T.to_linear(np.asarray(white))
    out = np.empty((IMG_H, IMG_W, 3), dtype=np.float32)
    out[:] = lin_w
    cols = np.arange(IMG_W) / IMG_W
    for name, (u0, wd) in ISLANDS.items():
        lo = u0 - 0.008 if name == H.TORSO else u0 - 0.005
        hi = u0 + wd + (0.02 if name == H.TORSO else 0.008)
        sel = (cols >= lo) & (cols < hi)
        for r in range(IMG_H):
            d0, d1 = (r / IMG_H - V0[name]) / per_m, ((r + 1) / IMG_H - V0[name]) / per_m
            c = H.stripe_cover(d0, d1, period, duty) if d1 > 0 else 0.0
            out[r, sel] = c * lin_n + (1 - c) * lin_w
    return out


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
    offs, reduced, hidden = {}, 0, {}
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
        reduced += d < want - 1e-6
        offs[v.index] = d
        hidden[v] = hit is not None and hit < args.shell_hide and p.z > z_full
        v.co = inv @ (p + n * d)
    # under the bib and the back panel nobody sees the top: its faces go there, args.shell_hide_rings rings in from
    # the panels' edges (the tucked hem stays whole)
    hid = {f for f in bm.faces if all(hidden[v] for v in f.verts)}
    for _ in range(args.shell_hide_rings):
        hid = {f for f in hid if all(g in hid for v in f.verts for g in v.link_faces)}
    rep["faces_hidden_under_the_panels"] = len(hid)
    bmesh.ops.delete(bm, geom=list(hid), context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    rep["verts_offset"] = len(offs)
    rep["verts_nearer_for_the_bib"] = reduced
    rep["offset_mm_min_median"] = [round(1000 * min(offs.values()), 2),
                                   round(1000 * sorted(offs.values())[len(offs) // 2], 2)]
    # the openings: hem, cuffs, the crew neck
    _bisect(bm, mw, lambda c: True, (0, 0, z_hem), (0, 0, 1), outer=False)
    for sgn in (1, -1):
        _bisect(bm, mw, lambda c: True, (sgn * args.cuff_x, 0, 0), (sgn, 0, 0))
    yf, zf, yb, zb = floats(args.neck)
    nco, nno = H.neck_plane(yf, zf, yb, zb)
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
    say("shell", rep)
    return top, rep


def material(top, gar, args, rep) -> dict:
    """The top's material: the stripes (the Meshy top's own navy and white) times a soft AO bake, a cotton normal map
    (fine knit ribs and the AO's folds), roughness 0.9."""
    navy, white = args.stripe_cols
    period, duty = floats(args.stripe)
    lin = stripe_image(navy, white, period, duty, args.shell_per_m)
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
        except Exception as e:  # noqa: BLE001 - the stripes stand without the AO
            out["ao_failed"] = str(e)[:200]
    shade = 1.0 - args.shell_ao * (1.0 - ao)
    rgb = T.to_srgb(lin * shade[..., None])
    alb.pixels[:] = np.concatenate([rgb, np.ones((IMG_H, IMG_W, 1), np.float32)], axis=2).ravel()
    alb.update()
    alb.pack()
    # the normal map: fine ribs across u (about 2 mm) and the AO as a soft height (the folds)
    xs = np.arange(IMG_W, dtype=np.float32)
    hgt = 0.15 * np.sin(2 * np.pi * xs / 3.0)[None, :] + 6.0 * blur(ao, 6)
    gy, gx = np.gradient(hgt)
    n = np.stack([-gx, -gy, np.ones_like(hgt)], axis=2)
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    nrm.pixels[:] = np.concatenate([0.5 + 0.5 * n, np.ones((IMG_H, IMG_W, 1), np.float32)], axis=2).ravel()
    nrm.update()
    nrm.pack()
    return out


def blur(a: np.ndarray, r: int) -> np.ndarray:
    k = np.ones(2 * r + 1, dtype=np.float32) / (2 * r + 1)
    a = np.apply_along_axis(lambda m: np.convolve(np.pad(m, r, mode="edge"), k, mode="valid"), 0, a)
    return np.apply_along_axis(lambda m: np.convolve(np.pad(m, r, mode="edge"), k, mode="valid"), 1, a)


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


def straps(gar, char, keep_objs, args) -> dict:
    """Two new strips (see the module) appended to the garment mesh."""
    btree = tree_of([char])
    bco = [char.matrix_world @ v.co for v in char.data.vertices]
    bpolys = [list(p.vertices) for p in char.data.polygons]
    gname = {g.index: g.name for g in char.vertex_groups}
    bw = [{gname[g.group]: g.weight for g in v.groups if g.group in gname} for v in char.data.vertices]
    ktree = tree_of(keep_objs)
    y0, z0 = floats(args.strap_axis)
    ts = [math.radians(t) for t in floats(args.shell_strap_t)]
    xs_k = floats(args.shell_strap_x)
    u0, u1, v0, v1 = floats(args.strap_uv)
    half, lip = args.strap_width / 2, args.strap_lip
    mw = gar.matrix_world
    inv = mw.inverted()
    me = gar.data
    steps = max(8, int(round((ts[-1] - ts[0]) / math.radians(args.strap_step))))
    angles = [ts[0] + (ts[-1] - ts[0]) * i / steps for i in range(steps + 1)]
    lats = [(-half, -lip), (-half, 0.0), (-half / 2, 0.0), (0.0, 0.0), (half / 2, 0.0), (half, 0.0), (half, -lip)]
    rep, plans = {}, []
    for sgn in (1, -1):
        locs, nors, offs = [], [], []
        for t in angles:
            a = Vector((sgn * H.strap_x(t, ts, xs_k), y0, z0))
            d = Vector((0.0, math.sin(t), math.cos(t)))
            loc, nor, _i, _d = btree.ray_cast(a, d, 0.4)
            if loc is None:
                loc, nor, _i, _d = btree.find_nearest(a + d * 0.15)
            nor = nor if nor.dot(d) > 0 else -nor
            hit = ktree.ray_cast(loc + nor * 1e-4, nor, 0.05)[0]
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
                uvs.append((u0 + (u1 - u0) * k / (len(lats) - 1), S.mirror_v(along[i], v0, v1, args.strap_texels)))
        plans.append({"grid": grid, "uvs": uvs, "rows": len(ct), "cols": len(lats), "nt": nt})
        rep["left" if sgn > 0 else "right"] = {
            "stations": len(ct), "length_m": round(along[-1], 4), "off_mm_min_max": [round(1000 * min(offs), 1),
                                                                                    round(1000 * max(offs), 1)],
            "front": [round(v, 3) for v in ct[0]], "back": [round(v, 3) for v in ct[-1]]}
    bm = bmesh.new()
    bm.from_mesh(me)
    uv = bm.loops.layers.uv.active
    dl = bm.verts.layers.deform.verify()
    gi = {g.name: g.index for g in gar.vertex_groups}
    new_faces = []
    for pl in plans:
        vs = []
        for q in pl["grid"]:
            v = bm.verts.new(inv @ q)
            loc, _n, fi, _d = btree.find_nearest(q)
            row: dict[str, float] = {}
            for k, w in zip(bpolys[fi], poly_3d_calc([bco[k] for k in bpolys[fi]], loc)):
                for b, x in bw[k].items():
                    row[b] = row.get(b, 0.0) + w * x
            for b, x in F.limit(row).items():
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
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    me.update()
    rep["strip_tris"] = 2 * len(new_faces)
    say("straps", rep)
    return rep
