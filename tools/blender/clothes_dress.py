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
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.interpolate import poly_3d_calc
from mathutils.kdtree import KDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clothes_fit_geom as F  # noqa: E402

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
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    out = Path(args.out)
    glb = out / f"{args.name}_char.glb"
    if glb.exists():
        say("REFUSED", glb, "exists")
        return 2
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(Path(args.char).resolve()))
    arm = bpy.data.objects["CharacterArmature"]
    char = next(o for o in bpy.data.objects if o.type == "MESH" and o.parent == arm)
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
    rest_diff = max(diffs[n] for n in used if n in diffs)
    rep["fit_armature_rest_diff_mm"] = round(rest_diff * 1000, 4)
    rep["other_bones_differing"] = sorted(n for n, d in diffs.items() if d > 1e-4 and n not in used)
    say("cloth bones", len(used), "rest diff mm", rep["fit_armature_rest_diff_mm"], "others differing",
        rep["other_bones_differing"])
    if missing or rest_diff > 1e-4:
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
    # the covered faces
    tree = cloth_tree(cloth)
    me = char.data
    mw = char.matrix_world
    nmat = mw.to_3x3().inverted().transposed()
    # the cloth's openings (collar, cuffs, hems, the shoes' tops): no cut reaches past them
    import bmesh
    edge = []
    for o in cloth:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        edge += [tuple(o.matrix_world @ v.co) for v in bm.verts if v.is_boundary]
        bm.free()
    ekd = KDTree(len(edge))
    for i, e in enumerate(edge):
        ekd.insert(e, i)
    ekd.balance()
    # a shoe is closed: the foot inside it (Foot and Toes, below the shoe's top opening) never shows
    shoe = next((o for o in cloth if o.name == "shoes"), None)
    top_z = None
    if shoe is not None:
        bm = bmesh.new()
        bm.from_mesh(shoe.data)
        top_z = F.shoe_top([(shoe.matrix_world @ v.co).z for v in bm.verts if v.is_boundary], args.shoe_margin)
        bm.free()
    gname = {g.index: g.name for g in char.vertex_groups}
    cov, outside, in_shoe = [], 0, 0
    for v in me.vertices:
        p = mw @ v.co
        n = (nmat @ v.normal).normalized()
        foot = sum(g.weight for g in v.groups if gname.get(g.group, "").endswith(("Foot", "Toes")))
        if F.in_shoe(foot, p.z, top_z):
            cov.append(True)
            in_shoe += 1
            continue
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
    faces = [list(p.vertices) for p in me.polygons]
    by_edge: dict[tuple[int, int], list[int]] = {}
    for fi, p in enumerate(me.polygons):
        for ek in p.edge_keys:
            by_edge.setdefault(ek, []).append(fi)
    nbrs = [sorted({j for ek in p.edge_keys for j in by_edge[ek] if j != fi}) for fi, p in enumerate(me.polygons)]
    gone = F.covered_faces(faces, cov, nbrs, erode=1)
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
    say("covered", sum(cov), "vertices,", sum(gone), "faces removed; tris", rep["tris"])
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
