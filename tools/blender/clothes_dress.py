"""Dresses a built alien character in a fitted outfit (art #196, clothes step 2, C1): opens a game build's character
.blend (alien_loco.py's <char>_char.blend: the character mesh, CharacterArmature and its clips), appends the fitted
cloth (clothes_fit.py's fit_<body>.blend: garment and shoes, skinned, at rest) as separate skinned meshes on the
character's armature, and removes the character's body faces the cloth fully covers, so nothing pokes through (the
body source stays whole: only this build's copy loses them). Then the GLB with export_glb.py's fixed textured options
(alien_loco._export) and the dressed .blend.

- --body-from/--body-to: the character was built on one body variant (f1) and is dressed on another (f2) of the same
  topology: every character vertex that sits on a --body-from vertex (within 0.01 mm) moves by that vertex's
  difference, every other one within 3 cm of the body the difference at its nearest body face (barycentric); the
  head, which no variant moves, stays.
- Covered: a character vertex is covered when five rays from it (its normal and four tilted 40 degrees) all hit the
  cloth within --reach m; a face goes when all its vertices are covered and so are its neighbours
  (clothes_fit_geom.covered_faces, one ring of erosion), so the cut's edge stays under the cloth. A vertex up to
  --outside m outside the cloth (one ray along its reversed normal) is tested from just inside the cloth instead,
  so a shoulder or a toe that crosses the cloth at rest is cut too.
- Under the cloth for certain (clothes_fit_geom.under_cloth): a body vertex inside the cloth at rest (its nearest
  cloth face within --near m) and farther than --away m from every real opening (clothes_open.opening_points: the
  top's collar and cuffs, the trousers' hems, the shoes' tops), on no neck, head or hand bone, is cut
  without the erosion, also where a ray escapes: a clip would move it out through the cloth; on the Shoulder bones
  farther than --away-shoulder m (the skin under the straps' base, near the collar).
- The shoes: the shoes are rigid on the feet, so a foot vertex inside one is cut for certain (no erosion): below the
  shoe's lowest top less --shoe-margin, under the shoe or its toe box, or below the opening's rim where it stands
  (the rim points within --rim-reach across the floor, less --rim-margin: the rim is low on the sides and high at the
  heel and the tongue), or through the shoe's wall (clothes_fit_geom.through_shoe: outside the shoe by 1 to 30 mm,
  its nearest shoe point over 1 cm from the rim); a face with such a vertex goes when all its vertices are on the
  foot below the rim's high point where they stand (clothes_fit_geom.shoe_face), so no face of the foot's side is
  left half through the shoe's coarse faces.
- The cloth's maps (clothes_texture): every piece's albedo, roughness and normal map grown from its UV islands into
  the empty texels, so a far camera's mipmaps average cloth, not the bake's black (unless --no-fill); the garment's
  denim scaled by --denim-gain (linear R,G,B; the stripes and the orange stitching kept).

    blender -b --factory-startup --python tools/blender/clothes_dress.py -- --char CHAR.blend --fit FIT.blend
        --name chameleon --out DIR [--body-from F1.blend --body-to F2.blend] [--reach 0.12]

Writes DIR/<name>_char.blend, DIR/<name>_char.glb and DIR/dress.json; never overwrites (refused when the GLB
exists). Prints CLOTHES_DRESS lines.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.interpolate import poly_3d_calc
from mathutils.kdtree import KDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clothes_fit_geom as F  # noqa: E402
import clothes_texture as T  # noqa: E402

PIECES = ("garment", "shoes")


def say(*a) -> None:
    print("CLOTHES_DRESS", *a, flush=True)


def tris(o) -> int:
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def body_co(path: str) -> np.ndarray:
    with bpy.data.libraries.load(str(Path(path).resolve())) as (src, dst):
        dst.objects = ["Body"]
    o = dst.objects[0]
    co = np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices])
    bpy.data.objects.remove(o)
    return co


def body_polys(path: str) -> list[list[int]]:
    with bpy.data.libraries.load(str(Path(path).resolve())) as (src, dst):
        dst.objects = ["Body"]
    o = dst.objects[0]
    polys = [list(p.vertices) for p in o.data.polygons]
    bpy.data.objects.remove(o)
    return polys


def cloth_tree(objs) -> BVHTree:
    co, polys, off = [], [], 0
    for o in objs:
        co += [tuple(o.matrix_world @ v.co) for v in o.data.vertices]
        polys += [[i + off for i in p.vertices] for p in o.data.polygons]
        off += len(o.data.vertices)
    return BVHTree.FromPolygons(co, polys)


def rays(n: Vector) -> list[Vector]:
    t1 = n.cross(Vector((0, 0, 1)))
    if t1.length < 0.3:
        t1 = n.cross(Vector((1, 0, 0)))
    t1.normalize()
    t2 = n.cross(t1).normalized()
    k = math.tan(math.radians(40))
    return [n] + [(n + k * s * t).normalized() for t in (t1, t2) for s in (1, -1)]


def maps(cloth, grow: bool, gain: tuple[float, float, float]) -> dict:
    """Each cloth piece's image maps filled from its UV islands (grow) and the garment's albedo shifted by gain;
    re-packed so the .blend and the GLB carry them. Returns per image the share of texels filled."""
    rep = {}
    for o in cloth:
        me = o.data
        uv = me.uv_layers.active.data
        tri = np.array([[uv[t.loops[i]].uv[:] for i in range(3)] for t in me.loop_triangles] if me.loop_triangles
                       else [], dtype=np.float64)
        if not len(tri):
            me.calc_loop_triangles()
            tri = np.array([[uv[t.loops[i]].uv[:] for i in range(3)] for t in me.loop_triangles], dtype=np.float64)
        imgs = {n.image for s in o.material_slots if s.material and s.material.node_tree
                for n in s.material.node_tree.nodes if n.type == "TEX_IMAGE" and n.image}
        masks = {}
        for img in sorted(imgs, key=lambda i: i.name):
            w, h = img.size
            px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
            entry = {}
            if grow:
                valid = masks.setdefault((w, h), T.island_mask(tri, w, h))
                px[..., :3] = T.fill(px[..., :3], valid)
                entry["filled_share"] = round(float((~valid).mean()), 4)
            if o.name == "garment" and "diffuse" in img.name and gain != (1.0, 1.0, 1.0):
                px[..., :3] = T.shift(px[..., :3], gain)
                entry["denim_gain"] = list(gain)
            if entry:
                img.pixels[:] = px.ravel()
                img.update()
                img.pack()
                rep[img.name] = entry
                say("map", img.name, entry)
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--char", required=True)
    ap.add_argument("--fit", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--body-from", default="")
    ap.add_argument("--body-to", default="")
    ap.add_argument("--reach", type=float, default=0.12)
    ap.add_argument("--outside", type=float, default=0.03, help="a body vertex this far outside the cloth still counts")
    ap.add_argument("--opening", type=float, default=0.04, help="no outside cut this near an opening (m)")
    ap.add_argument("--shoe-margin", type=float, default=0.01, help="the foot cut stays this far below the shoe's top")
    ap.add_argument("--near", type=float, default=0.06, help="the cloth this near a body vertex at rest (m)")
    ap.add_argument("--away", type=float, default=0.08,
                    help="a body vertex inside the cloth and this far from every opening is cut for certain (m)")
    ap.add_argument("--rim-margin", type=float, default=0.004,
                    help="the foot cut stays this far below the shoe opening's rim where the vertex stands (m)")
    ap.add_argument("--rim-reach", type=float, default=0.03,
                    help="the rim points this near a foot vertex across the floor give its local rim (m)")
    ap.add_argument("--away-shoulder", type=float, default=0.04,
                    help="--away on the Shoulder bones (m): the skin under the straps' base, near the collar")
    ap.add_argument("--no-fill", action="store_true", help="leave the maps' empty texels black (the r16 build)")
    ap.add_argument("--denim-gain", default="1,1,1", help="the garment denim's linear gain R,G,B (1,1,1: as baked)")
    ap.add_argument("--strap-axis", default="0.04,1.18", help="the shoulders' axis in the side view: y,z (m)")
    ap.add_argument("--strap-width", type=float, default=0.035)
    ap.add_argument("--strap-lip", type=float, default=0.003, help="the strip's edges fold this far toward the body")
    ap.add_argument("--strap-uv", default="0.4725,0.4935,0.784,0.829",
                    help="the plain denim rectangle the straps' patch copies: u0,u1,v0,v1")
    ap.add_argument("--strap-texels", type=float, default=0.743, help="the strips' UV units per metre along")
    ap.add_argument("--shell", action="store_true",
                    help="the hybrid route (clothes_top): a shell top of the body, the Meshy garment cut to the "
                         "trousers, bib and back panel, new straps")
    ap.add_argument("--shell-off", type=float, default=0.006, help="the top's clearance off the body (m)")
    ap.add_argument("--shell-hem", type=float, default=0.95, help="the top's hem, tucked under the trousers (z, m)")
    ap.add_argument("--shell-full", type=float, default=1.02, help="the full clearance from this height up (z, m)")
    ap.add_argument("--shell-hem-off", type=float, default=0.002, help="the clearance at the hem (m)")
    ap.add_argument("--shell-gap", type=float, default=0.003, help="the top stays this far inside a kept piece (m)")
    ap.add_argument("--shell-floor", type=float, default=0.002, help="the top's least clearance (m)")
    ap.add_argument("--shell-hide", type=float, default=0.06,
                    help="a top face whose five rays (its normal and four tilted) meet a kept piece this near is "
                         "hidden under it (m)")
    ap.add_argument("--shell-hide-tilt", type=float, default=0.6, help="the four rays' tilt off the normal (tan)")
    ap.add_argument("--shell-hide-rings", type=int, default=1, help="the hidden faces kept next to a panel's edge")
    ap.add_argument("--shell-follow", type=float, default=0.04,
                    help="a top vertex whose rays meet the garment this near takes its weights by their share "
                         "(m; 0: the body's alone)")
    ap.add_argument("--shell-decimate", default="0.32,0.22",
                    help="the top's faces kept away from its openings: arms, torso (share; 1,1: no decimation)")
    ap.add_argument("--shell-protect", default="0.035,0.03,0.02",
                    help="no decimation this near the cuffs, the neck cut and the hem (m)")
    ap.add_argument("--shell-lip", type=float, default=0.0045, help="the collar's and cuffs' lip toward the body (m)")
    ap.add_argument("--shell-per-m", type=float, default=1.29, help="the top's UV units per metre in v")
    ap.add_argument("--shell-ao", type=float, default=0.45, help="how much the AO bake darkens the top (0: no bake)")
    ap.add_argument("--shell-ao-dist", type=float, default=0.06)
    ap.add_argument("--shell-ao-samples", type=int, default=24)
    ap.add_argument("--stripe", default="0.038,0.5", help="the stripes' period (m) and navy share")
    ap.add_argument("--cuff-x", type=float, default=0.625, help="the cuffs' plane |x| (T-pose, m)")
    ap.add_argument("--seam-x", type=float, default=0.165, help="the sleeves' seam plane |x| (m)")
    ap.add_argument("--arm-z", type=float, default=1.18, help="the sleeves start above this height (m)")
    ap.add_argument("--arm-axis", default="0.068,1.277", help="the T-pose arms' axis: y,z (m)")
    ap.add_argument("--neck", default="-0.06,1.335,0.09,1.365",
                    help="the crew neck's plane through its front and back points: yf,zf,yb,zb (m)")
    ap.add_argument("--neck-r", type=float, default=0.09, help="the neck cut reaches this far out in |x| (m)")
    ap.add_argument("--waist", type=float, default=1.0, help="the Meshy trousers' waistband height (m)")
    ap.add_argument("--bib", default="0.105,1.195", help="the bib's half width and top (m)")
    ap.add_argument("--back", default="0.03,1.12,0.12,0.03",
                    help="the back panel: least y, apex z, half width at the waist and at the apex (m)")
    ap.add_argument("--shell-strap-t", default="-118,20,134",
                    help="the new straps' angles round the shoulder axis: front, shoulder, back (degrees)")
    ap.add_argument("--shell-strap-x", default="0.078,0.10,0.015", help="the new straps' |x| at those angles (m)")
    ap.add_argument("--shell-strap-off", type=float, default=0.010, help="the new straps' least distance off the body")
    ap.add_argument("--shell-strap-step", type=float, default=6.0, help="degrees between the new straps' stations")
    ap.add_argument("--shell-strap-lats", type=int, default=5, help="the new straps' vertices across (lips included)")
    ap.add_argument("--shell-strap-reach", type=float, default=0.04,
                    help="the new straps clear the outermost kept surface this far along the body's normal (m)")
    ap.add_argument("--strap-lip-u", type=float, default=0.1, help="each lip's share of the strap patch's width")
    ap.add_argument("--stitch", default="0.003,0.003,0.002",
                    help="the straps' two stitch lines: inset from each edge, dash, gap (m)")
    ap.add_argument("--buckle", default="0.01,0.036",
                    help="the button's and the buckle ring's places along each strap from its front end (m)")
    ap.add_argument("--buckle-size", default="0.004,0.011,0.004,0.0035",
                    help="the ring's margin past the strap, half length, bar width, height; m")
    ap.add_argument("--button-size", default="0.0065,0.003,0.001", help="the button's radius, height, dome (m)")
    ap.add_argument("--strap-front", type=float, default=0.09,
                    help="the Meshy bib under this much of each strap's front goes (m)")
    ap.add_argument("--stitch-colour", default="0.78,0.48,0.22", help="the straps' stitching, the sketch's orange (sRGB)")
    ap.add_argument("--bronze", default="0.60,0.42,0.20,0.85,0.38",
                    help="the buckles' metal: sRGB R,G,B, metallic, roughness")
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    out = Path(args.out)
    glb = out / f"{args.name}_char.glb"
    if glb.exists():
        say("REFUSED", glb, "exists")
        return 2
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(Path(args.char).resolve()))
    arm = bpy.data.objects["CharacterArmature"]
    import clothes_open as O
    try:
        char = O.body_mesh(arm, [], args.name)
    except ValueError as e:
        say("REFUSED", e)
        return 3
    rep = {"char": args.char, "fit": args.fit, "mesh": char.name, "tris_before": tris(char)}
    with bpy.data.libraries.load(str(Path(args.fit).resolve())) as (src, dst):
        dst.objects = [n for n in src.objects if n in PIECES or n == "CharacterArmature"]
    farm = next(o for o in dst.objects if o.type == "ARMATURE")
    # the bones the cloth is weighted to must rest where the character's do (the head's own bones may differ)
    used = {g.name for o in dst.objects if o.type == "MESH" for g in o.vertex_groups
            if any(g.index == vg.group and vg.weight > 0 for v in o.data.vertices for vg in v.groups)}
    diffs = {b.name: max((farm.data.bones[b.name].head_local - b.head_local).length,
                         (farm.data.bones[b.name].tail_local - b.tail_local).length)
             for b in arm.data.bones if b.name in farm.data.bones}
    missing = sorted(used - set(diffs))
    if not used or missing:
        say("REFUSED the fit's cloth bones", sorted(used), "are not all the character's: missing", missing)
        return 3
    rest_diff = max(diffs[n] for n in used)
    rep["fit_armature_rest_diff_mm"] = round(rest_diff * 1000, 4)
    rep["other_bones_differing"] = sorted(n for n, d in diffs.items() if d > 1e-4 and n not in used)
    say("cloth bones", len(used), "rest diff mm", rep["fit_armature_rest_diff_mm"], "others differing",
        rep["other_bones_differing"])
    if rest_diff > 1e-4:
        say("REFUSED the fit's armature rest differs from the character's by", rest_diff, "m")
        return 3
    cloth = [o for o in dst.objects if o.type == "MESH"]
    for o in cloth:
        bpy.context.scene.collection.objects.link(o)
        for m in o.modifiers:
            if m.type == "ARMATURE":
                m.object = arm
        o.parent = arm
        o.matrix_parent_inverse = arm.matrix_world.inverted()
    bpy.data.objects.remove(farm)
    if args.body_from:
        a, b = body_co(args.body_from), body_co(args.body_to)
        kd = KDTree(len(a))
        for i, p in enumerate(a):
            kd.insert(p, i)
        kd.balance()
        inv = char.matrix_world.inverted()
        polys = body_polys(args.body_from)
        tree = BVHTree.FromPolygons([tuple(c) for c in a], polys)
        diff = b - a
        matched = moved = followed = 0
        for v in char.data.vertices:
            p = char.matrix_world @ v.co
            _co, i, d = kd.find(p)
            if d < 1e-5:
                matched += 1
                dv = Vector(diff[i])
            else:  # a vertex the build moved off the body (the welds, smoothing): the nearest face's difference
                loc, _n, fi, dist = tree.find_nearest(p, 0.03)
                if loc is None:
                    continue
                vs = polys[fi]
                bary = poly_3d_calc([Vector(a[k]) for k in vs], loc)
                dv = Vector(sum(w * diff[k] for k, w in zip(vs, bary)))
                followed += dv.length > 1e-7
            if dv.length > 1e-7:
                moved += 1
                v.co = inv @ (p + dv)
        char.data.update()
        rep["body_variant"] = {"from": args.body_from, "to": args.body_to, "matched": matched, "moved": moved,
                               "followed_nearest_face": followed,
                               "unmatched": len(char.data.vertices) - matched}
        say("body variant", rep["body_variant"])
    garment = next((o for o in cloth if o.name == "garment"), None)
    if args.shell and garment is not None:  # the hybrid route: our own top, bib, back and straps (clothes_top)
        import clothes_top as TOP
        args.stripe_cols = TOP.stripe_colours(garment)
        rep["garment_cut"] = TOP.cut_garment(garment, args)
        top, rep["shell"] = TOP.shell(char, arm, garment, args)
        rep["straps"] = TOP.straps(garment, char, [garment, top], args)
        cloth.append(top)
    gname = {g.index: g.name for g in char.vertex_groups}
    # the covered faces
    tree = cloth_tree(cloth)
    me = char.data
    mw = char.matrix_world
    nmat = mw.to_3x3().inverted().transposed()
    # the cloth's real openings (collar, cuffs, hems, the shoes' tops): no cut reaches past them
    import bmesh
    import clothes_open as O
    edge, rep["openings"] = O.opening_points(cloth, arm)
    say("openings", len(edge), "points:", rep["openings"])
    ekd = O.kd_of(edge)
    # a shoe is closed: the foot inside it (Foot and Toes, below the shoe's top opening) never shows
    # (each shoe its own top, by side; and any foot vertex with the shoe above it, the toes under the toe box)
    shoe = next((o for o in cloth if o.name == "shoes"), None)
    top_z = {1.0: None, -1.0: None}
    stree = None
    rim_kd, rim_pts = None, []
    if shoe is not None:
        bm = bmesh.new()
        bm.from_mesh(shoe.data)
        bz = [(shoe.matrix_world @ v.co) for v in bm.verts if v.is_boundary]
        bm.free()
        for sgn in top_z:
            top_z[sgn] = F.shoe_top([q.z for q in bz if q.x * sgn > 0], args.shoe_margin)
        # the opening's rim across the floor (x, y): each foot vertex is cut below the rim where it stands
        rim_pts = [q for q in bz if q.z > 0.05]
        rim_kd = KDTree(max(1, len(rim_pts)))
        for i, q in enumerate(rim_pts):
            rim_kd.insert((q.x, q.y, 0.0), i)
        rim_kd.balance()
        rim_kd3 = KDTree(max(1, len(rim_pts)))
        for i, q in enumerate(rim_pts):
            rim_kd3.insert(q, i)
        rim_kd3.balance()
        sv = [shoe.matrix_world @ v.co for v in shoe.data.vertices]
        stree = BVHTree.FromPolygons(sv, [list(p.vertices) for p in shoe.data.polygons])
    rep["shoe_top_z"] = {("left" if k > 0 else "right"): (None if t is None else round(t, 4)) for k, t in top_z.items()}
    up = Vector((0.0, 0.0, 1.0))
    cov, sure, outside, in_shoe, by_rim, by_wall, n_under = [], [], 0, 0, 0, 0, 0
    thru, low_foot = [False] * len(me.vertices), [False] * len(me.vertices)
    for v in me.vertices:
        p = mw @ v.co
        n = (nmat @ v.normal).normalized()
        foot = sum(g.weight for g in v.groups if gname.get(g.group, "").endswith(("Foot", "Toes")))
        toes = sum(g.weight for g in v.groups if gname.get(g.group, "").endswith("Toes"))
        top = top_z[1.0 if p.x > 0 else -1.0]
        under = foot >= 0.5 and stree is not None and stree.ray_cast(p + up * 1e-4, up, 0.15)[0] is not None
        rim = None
        if foot >= 0.5 and rim_pts:
            near_rim = [rim_pts[j].z for _c, j, _d in rim_kd.find_range((p.x, p.y, 0.0), args.rim_reach)
                        if rim_pts[j].x * p.x > 0]
            rim = F.local_rim(near_rim, args.rim_margin)
            low_foot[v.index] = bool(near_rim) and p.z < max(near_rim)
        through = False
        if foot >= 0.5 and stree is not None and rim_pts:
            sloc, snor, _sf, _sd = stree.find_nearest(p)
            if sloc is not None:
                through = F.through_shoe((p - sloc).dot(snor), rim_kd3.find(sloc)[2])
                thru[v.index] = through
        if through or F.in_shoe(foot, p.z, top, under=under, toes_weight=toes, shoe=stree is not None, rim=rim):
            cov.append(True)
            sure.append(True)
            in_shoe += 1
            by_rim += not F.in_shoe(foot, p.z, top, under=under, toes_weight=toes, shoe=stree is not None)
            by_wall += through
            continue
        top_bone = gname.get(max(v.groups, key=lambda g: g.weight).group, "") if v.groups else ""
        loc, nor, _fi, _d = tree.find_nearest(p, args.near)
        if loc is not None and F.under_cloth((p - loc).dot(nor), ekd.find(p)[2], top_bone, away=args.away,
                                              away_shoulder=args.away_shoulder):
            cov.append(True)
            sure.append(True)
            n_under += 1
            continue
        sure.append(False)
        hit = all(tree.ray_cast(p + d * 1e-4, d, args.reach)[0] is not None for d in rays(n))
        if not hit:  # the body outside the cloth (a shoulder): covered if the cloth lies within --outside behind it
            loc, _nor, _fi, t = tree.ray_cast(p, -n, args.outside)
            if loc is not None and ekd.find(loc)[2] >= args.opening:
                q = loc - n * 1e-3
                hit = all(tree.ray_cast(q + d * 1e-4, d, args.reach)[0] is not None for d in rays(n))
                outside += hit
        cov.append(hit)
    rep["covered_from_outside"] = outside
    rep["covered_in_shoes"] = in_shoe
    rep["covered_in_shoes_by_rim"] = by_rim
    rep["covered_through_shoe_walls"] = by_wall
    rep["covered_under_the_cloth"] = n_under
    faces = [list(p.vertices) for p in me.polygons]
    by_edge: dict[tuple[int, int], list[int]] = {}
    for fi, p in enumerate(me.polygons):
        for ek in p.edge_keys:
            by_edge.setdefault(ek, []).append(fi)
    nbrs = [sorted({j for ek in p.edge_keys for j in by_edge[ek] if j != fi}) for fi, p in enumerate(me.polygons)]
    gone = F.covered_faces(faces, cov, nbrs, erode=1, vert_sure=sure)
    shoe_faces = [not g and F.shoe_face([thru[k] for k in f], [low_foot[k] or sure[k] for k in f])
                  for g, f in zip(gone, faces)]
    gone = [g or x for g, x in zip(gone, shoe_faces)]
    rep["faces_removed_through_shoe_walls"] = sum(shoe_faces)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[i] for i, g in enumerate(gone) if g], context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(me)
    bm.free()
    me.update()
    rep["covered_vertices"] = sum(cov)
    rep["faces_removed"] = sum(gone)
    rep["tris"] = {"body": tris(char), **{o.name: tris(o) for o in cloth}}
    rep["tris"]["cloth"] = sum(tris(o) for o in cloth)
    rep["tris"]["total"] = rep["tris"]["body"] + rep["tris"]["cloth"]
    say("covered", sum(cov), "vertices,", in_shoe, "in the shoes (", by_rim, "by the rim,", by_wall,
        "through the walls ),", n_under,
        "under the cloth for certain,", sum(gone),
        "faces removed; tris", rep["tris"])
    rep["maps"] = maps(cloth, not args.no_fill, tuple(float(v) for v in args.denim_gain.split(",")))
    blend = out / f"{args.name}_char.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True)
    import alien_loco
    alien_loco._export(arm, glb)
    rep["glb"] = str(glb)
    rep["clips"] = sorted(a.name for a in bpy.data.actions)
    (out / "dress.json").write_text(json.dumps(rep, indent=1), encoding="utf-8", newline="\n")
    say("wrote", glb)
    return 0


if __name__ == "__main__":
    sys.exit(main())
