"""Fits a cleaned outfit (clothes_clean.py's cloth.blend: garment and shoes) onto the shared alien body, once, on the
base body, and carries it to a female variant (art #196, clothes step 2, C1). No vertex is moved by hand:

1. The pose. The body rests in a T-pose; the cloth is drawn arms down, legs a little apart. The armature swings each
   upper arm so the wrist points at its sleeve's cuff, each upper leg so the ankle points at its trouser hem, and
   keeps the feet flat. The garment is moved front to back so its torso's centre is the body's.
2. The fit, on the posed body: per garment vertex its signed distance from the body (BVH nearest, along the face's
   normal) becomes clothes_fit_geom.fit_distance's (a small even offset, part of the looseness kept, never inside);
   where the cloth bridges (far from the body: the crotch, under the arms) the looseness is kept whole. The
   displacements are smoothed over the cloth's edges, then a last pass puts every vertex outside the floor. Each shoe
   is moved onto its posed foot and only pushed out where the foot pokes through.
3. The weights: per cloth vertex the body's weights at its nearest posed body point (barycentric), smoothed where the
   cloth bridges, four bones at most.
4. The rest pose: each vertex's linear blend skinning is undone (clothes_fit_geom.unskin), so the cloth's bind pose is
   the body's rest pose; the armature modifier re-poses it and the error against the fitted cloth is reported.
5. The female fit (--female): each cloth vertex follows the body's per-vertex difference (base to female, same
   topology) at its nearest rest body point, smoothed, then pushed out of the female body where needed.

    blender -b --factory-startup --python tools/blender/clothes_fit.py -- --cloth CLOTH.blend --body BASE.blend
        [--female FEMALE.blend] --out DIR [--offset 0.010] [--keep 0.30] [--floor 0.005]

Writes DIR/fit_base.blend (Body, CharacterArmature, garment, shoes: skinned, at rest), DIR/fit_<female>.blend and
DIR/fit.json; never overwrites (a DIR holding fit.json is refused). Prints CLOTHES_FIT lines.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.interpolate import poly_3d_calc

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clothes_fit_geom as F  # noqa: E402

PIECES = ("garment", "shoes")


def say(*a) -> None:
    print("CLOTHES_FIT", *a, flush=True)


def smoothstep(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def evaluated_co(o) -> np.ndarray:
    dg = bpy.context.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.array([(o.matrix_world @ v.co)[:] for v in me.vertices])
    ev.to_mesh_clear()
    return co


def bvh_of(o) -> tuple[BVHTree, list[list[int]], np.ndarray]:
    """The evaluated (posed) mesh's BVH in world space, its polygons and its vertices."""
    co = evaluated_co(o)
    polys = [list(p.vertices) for p in o.data.polygons]
    return BVHTree.FromPolygons([tuple(c) for c in co], polys), polys, co


def neighbours(me) -> list[list[int]]:
    nb = [[] for _ in me.vertices]
    for e in me.edges:
        a, b = e.vertices
        nb[a].append(b)
        nb[b].append(a)
    return nb


def boundary_loops(o) -> list[dict]:
    """Every boundary loop of o (world space): its centre, size and edge count."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    seen, out = set(), []
    for e in bm.edges:
        if not e.is_boundary or e.index in seen:
            continue
        group, stack = [], [e]
        seen.add(e.index)
        while stack:
            g = stack.pop()
            group.append(g)
            for v in g.verts:
                for n in v.link_edges:
                    if n.is_boundary and n.index not in seen:
                        seen.add(n.index)
                        stack.append(n)
        pts = np.array([(o.matrix_world @ v.co)[:] for g in group for v in g.verts])
        if len(group) >= 12:
            out.append({"edges": len(group), "centre": pts.mean(axis=0), "size": np.ptp(pts, axis=0)})
    bm.free()
    return out


def side_of(arm, prefix: str) -> float:
    return math.copysign(1.0, (arm.matrix_world @ arm.data.bones[prefix + "UpperArm"].head_local).x)


def swing_bone(arm, name: str, tip: str, target: Vector) -> float:
    """Rotates pose bone name about its head so that bone tip's head points at target (armature space). Degrees."""
    pb = arm.pose.bones[name]
    bpy.context.view_layer.update()
    head = pb.head.copy()
    cur = arm.pose.bones[tip].head - head
    axis, ang = F.swing(tuple(cur), tuple(target - head))
    rot = Matrix.Rotation(ang, 4, Vector(axis))
    pb.matrix = Matrix.Translation(head) @ rot @ Matrix.Translation(-head) @ pb.matrix
    bpy.context.view_layer.update()
    return math.degrees(ang)


def flat_foot(arm, name: str) -> None:
    pb = arm.pose.bones[name]
    m = pb.bone.matrix_local.copy()
    m.translation = pb.head.copy()
    pb.matrix = m
    bpy.context.view_layer.update()


def deform_mats(arm) -> dict[str, list[list[float]]]:
    """Per bone its deform matrix (rest to pose, world space) as a 3x4 row list."""
    w, wi = arm.matrix_world, arm.matrix_world.inverted()
    out = {}
    for pb in arm.pose.bones:
        m = w @ pb.matrix @ pb.bone.matrix_local.inverted() @ wi
        out[pb.name] = [list(m[r]) for r in range(3)]
    return out


def body_weights(body, arm) -> list[dict[str, float]]:
    """Per body vertex its weights on the armature's deform bones."""
    deform = {b.name for b in arm.data.bones if b.use_deform}
    names = {g.index: g.name for g in body.vertex_groups if g.name in deform}
    return [{names[g.group]: g.weight for g in v.groups if g.weight > 0 and g.group in names}
            for v in body.data.vertices]


def vertex_normals(pts: np.ndarray, faces: list[list[int]]) -> np.ndarray:
    """Per vertex its area-weighted normal from faces (fan-triangulated), unit length."""
    acc = np.zeros_like(pts)
    for f in faces:
        for k in range(1, len(f) - 1):
            a, b, c = f[0], f[k], f[k + 1]
            n = np.cross(pts[b] - pts[a], pts[c] - pts[a])
            acc[a] += n
            acc[b] += n
            acc[c] += n
    ln = np.linalg.norm(acc, axis=1)
    ln[ln == 0] = 1.0
    return acc / ln[:, None]


def nearest_rows(pts: np.ndarray, tree: BVHTree, polys, bco: np.ndarray, rows: list[dict],
                 nrm: np.ndarray | None = None, reach: float = 0.10) -> tuple[list[dict], int]:
    """Per point the body's weights at its nearest body point, interpolated over that face. With nrm (the cloth's
    outward vertex normals) the nearest body face facing the same way within reach (clothes_fit_geom.pick_facing):
    the inner sleeve takes the arm, not the torso beside it. Also returns how many points took another face than
    the plain nearest."""
    out, other = [], 0
    for i, p in enumerate(pts):
        loc, _n, fi, _d = tree.find_nearest(Vector(p))
        if nrm is not None:
            cands = tree.find_nearest_range(Vector(p), reach)
            pick = F.pick_facing([(c[3], tuple(c[1]), c[2]) for c in cands], tuple(nrm[i]))
            if pick is not None and pick != fi:
                loc, fi = next(c[0] for c in cands if c[2] == pick), pick
                other += 1
        vs = polys[fi]
        bary = poly_3d_calc([Vector(bco[v]) for v in vs], loc)
        acc: dict[str, float] = {}
        for v, b in zip(vs, bary):
            for name, w in rows[v].items():
                acc[name] = acc.get(name, 0.0) + b * w
        out.append(acc)
    return out, other


def signed(pts: np.ndarray, tree: BVHTree) -> tuple[np.ndarray, np.ndarray]:
    """Per point its signed distance from the body along the nearest face's normal, and that normal."""
    s, n = np.zeros(len(pts)), np.zeros((len(pts), 3))
    for i, p in enumerate(pts):
        loc, nor, _fi, _d = tree.find_nearest(Vector(p))
        s[i] = (Vector(p) - loc).dot(nor)
        n[i] = nor[:]
    return s, n


def exit_point(tree: BVHTree, p: Vector, d: Vector, reach: float = 0.15):
    """Where a ray from p (inside the body) along d leaves the body: the first hit whose face faces along d
    (clothes_fit_geom.first_exit), as (location, normal), or None within reach."""
    hits, o, gone = [], p.copy(), 0.0
    for _ in range(8):
        loc, nor, _fi, dist = tree.ray_cast(o, d, reach - gone)
        if loc is None:
            break
        gone += dist
        hits.append((gone, float(nor.dot(d)), loc, nor))
        o = loc + d * 1e-5
    k = F.first_exit([(h[0], h[1]) for h in hits])
    return None if k is None else (hits[k][2], hits[k][3])


def push_out(pts: np.ndarray, tree: BVHTree, floor, faces=None) -> tuple[np.ndarray, int]:
    """Every point closer to the body than floor (m, a number or one per point) moved out along the face normal.
    With faces (the cloth's), a point inside the body leaves it along the cloth's own outward normal instead: a
    point deeper than half the limb has its nearest face on the limb's far side, and the plain push would carry the
    sleeve's front through the arm to its back (r7: the left elbow 37 mm through a sleeve folded behind it)."""
    s, n = signed(pts, tree)
    fl = np.broadcast_to(np.asarray(floor, dtype=float), s.shape)
    bad = s < fl
    pts = pts.copy()
    deep = np.zeros(len(pts), dtype=bool)
    if faces is not None and (s < 0).any():
        nrm = vertex_normals(pts, faces)
        if float(np.mean(np.sum(nrm * n, axis=1))) < 0:  # the cloth's faces wound inward
            nrm = -nrm
        for i in np.where(s < 0)[0]:
            hit = exit_point(tree, Vector(pts[i]), Vector(nrm[i]))
            if hit is not None:
                pts[i] = np.array(hit[0] + hit[1] * float(fl[i]))
                deep[i] = True
    rest = bad & ~deep
    pts[rest] += (fl[rest] - s[rest])[:, None] * n[rest]
    return pts, int(bad.sum())


def fit_piece(pts: np.ndarray, nb, tree, offset: float, keep: float, floor: float, bridge: tuple[float, float],
              iters: int, faces=None) -> tuple[np.ndarray, dict]:
    s0, _ = signed(pts, tree)
    if faces is not None:  # out of the body first, along the cloth's normal, so no fit step pulls a deep point through
        pts, _ = push_out(pts, tree, 0.0, faces)
    s, n = signed(pts, tree)
    target = np.array([F.fit_distance(si, offset, keep + (1.0 - keep) * smoothstep((si - bridge[0]) /
                                                                              (bridge[1] - bridge[0])), floor)
                       for si in s])
    disp = ((target - s)[:, None] * n).tolist()
    disp = np.array(F.smooth(disp, nb, iters, 0.5))
    out = pts + disp
    out, pushed = push_out(out, tree, floor, faces)
    s2, _ = signed(out, tree)
    return out, {"s_before_mm": [round(float(np.percentile(s0, q)) * 1000, 1) for q in (5, 50, 95)],
                 "s_after_mm": [round(float(np.percentile(s2, q)) * 1000, 1) for q in (5, 50, 95)],
                 "inside_before": int((s0 < 0).sum()), "inside_after": int((s2 < 0).sum()), "pushed": pushed,
                 "moved_max_mm": round(float(np.linalg.norm(out - pts, axis=1).max()) * 1000, 1)}


def split_long(o, max_len: float, rounds: int = 4) -> dict:
    """Splits o's edges longer than max_len at their middles (clothes_fit_geom.long_edges), a few rounds, and
    triangulates. Flat faces split flat, so the surface and its UVs (the baked texture) stay as they were."""
    before = len(o.data.polygons)
    done = 0
    for _ in range(rounds):
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.edges.ensure_lookup_table()
        idx = F.long_edges([e.calc_length() for e in bm.edges], max_len)
        if idx:
            bmesh.ops.subdivide_edges(bm, edges=[bm.edges[i] for i in idx], cuts=1, use_grid_fill=False)
            bmesh.ops.triangulate(bm, faces=bm.faces[:])
            bm.to_mesh(o.data)
            done += len(idx)
        bm.free()
        if not idx:
            break
    o.data.update()
    return {"max_edge_m": max_len, "edges_split": done, "tris_before": before, "tris_after": len(o.data.polygons)}


def faces_of(o) -> list[list[int]]:
    return [list(p.vertices) for p in o.data.polygons]


def set_co(o, pts: np.ndarray) -> None:
    inv = o.matrix_world.inverted()
    for v, p in zip(o.data.vertices, pts):
        v.co = inv @ Vector(p)
    o.data.update()


def write_groups(o, rows: list[dict], arm) -> None:
    o.vertex_groups.clear()
    groups = {b.name: o.vertex_groups.new(name=b.name) for b in arm.data.bones if b.use_deform}
    for i, row in enumerate(rows):
        for b, w in row.items():
            groups[b].add([i], w, "REPLACE")
    mod = next((m for m in o.modifiers if m.type == "ARMATURE"), None) or o.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    o.parent = arm
    o.matrix_parent_inverse = arm.matrix_world.inverted()


def split_shoes(o) -> list[np.ndarray]:
    """The shoes' vertex indices per side (loose parts grouped by the sign of x)."""
    co = np.array([v.co[:] for v in o.data.vertices])
    return [np.where(co[:, 0] * sgn > 0)[0] for sgn in (1.0, -1.0)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cloth", required=True)
    ap.add_argument("--body", required=True)
    ap.add_argument("--female", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--offset", type=float, default=0.010)
    ap.add_argument("--keep", type=float, default=0.30)
    ap.add_argument("--floor", type=float, default=0.005)
    ap.add_argument("--bridge", default="0.045,0.09", help="from..to m: the looseness kept whole beyond to")
    ap.add_argument("--smooth", type=int, default=12)
    ap.add_argument("--floor-arm", type=float, default=0.008, help="the floor on the sleeves (m)")
    ap.add_argument("--clear-iters", type=int, default=3, help="rounds of the clearance in rest and fitted pose")
    ap.add_argument("--max-edge", type=float, default=0.04, help="the garment's edges split to this length (m)")
    ap.add_argument("--hug", type=float, default=0.006, help="the female's chest: the bib's clearance there (m)")
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    out = Path(args.out)
    if (out / "fit.json").exists():
        say("REFUSED", out / "fit.json", "exists")
        return 2
    out.mkdir(parents=True, exist_ok=True)
    bridge = tuple(float(x) for x in args.bridge.split(","))
    bpy.ops.wm.open_mainfile(filepath=str(Path(args.body).resolve()))
    body, arm = bpy.data.objects["Body"], bpy.data.objects["CharacterArmature"]
    with bpy.data.libraries.load(str(Path(args.cloth).resolve())) as (src, dst):
        dst.objects = [n for n in src.objects if n in PIECES]
    cloth = {o.name: o for o in dst.objects}
    for o in cloth.values():
        bpy.context.scene.collection.objects.link(o)
        o.data = o.data.copy()
        o.data.transform(o.matrix_world)
        o.matrix_world = Matrix()
    rep = {"cloth": str(args.cloth), "body": str(args.body), "args": vars(args)}
    aw = arm.matrix_world
    head = {b.name: aw @ b.head_local for b in arm.data.bones}
    front = 1.0 if (head["LeftToes"] - head["LeftFoot"]).y > 0 else -1.0
    rep["body_front_y"] = front
    # the cloth's front from its shoes: each shoe's top opening sits toward the heel (B read -y as imported)
    cfront = -1.0
    if "shoes" in cloth:
        sco = np.array([v.co[:] for v in cloth["shoes"].data.vertices])
        tops = [lp for lp in boundary_loops(cloth["shoes"]) if lp["centre"][2] > 0.05]
        if tops:
            cfront = float(np.sign((sco[:, 1].min() + sco[:, 1].max()) / 2 - np.mean([lp["centre"][1] for lp in tops])))
    rep["cloth_front_y"] = cfront
    say("front: body", front, "cloth", cfront)
    if front != cfront:  # turn the cloth to the body's front
        for o in cloth.values():
            o.data.transform(Matrix.Rotation(math.pi, 4, "Z"))
    g = cloth["garment"]
    # front to back: the garment's torso centre onto the body's (B saw it 4 cm behind)
    bco, gco = evaluated_co(body), evaluated_co(g)

    def mid_y(co):
        sel = co[(co[:, 2] > 0.95) & (co[:, 2] < 1.15) & (np.abs(co[:, 0]) < 0.08)]
        return (sel[:, 1].min() + sel[:, 1].max()) / 2

    dy = mid_y(bco) - mid_y(gco)
    g.data.transform(Matrix.Translation((0, dy, 0)))
    rep["garment_shift_y_m"] = round(float(dy), 4)
    # 0. the coarse cloth split where its edges are long (the sleeves): a flat face cannot wrap the arm, the arm
    # shows through between its vertices however far they are pushed out (r6: the left elbow 47 mm through)
    rep["split"] = split_long(g, args.max_edge)
    say("split", rep["split"])
    # 1. the pose
    loops = boundary_loops(g)
    rep["loops"] = [{"edges": lp["edges"], "centre": lp["centre"].round(4).tolist(), "size": lp["size"].round(4).tolist()}
                    for lp in loops]
    pose = {}
    for prefix in ("Left", "Right"):
        sgn = side_of(arm, prefix)
        cuffs = [lp for lp in loops if 0.45 < lp["centre"][2] < 1.15 and lp["centre"][0] * sgn > 0.14]
        hems = [lp for lp in loops if lp["centre"][2] < 0.40 and lp["centre"][0] * sgn > 0.0]
        if not cuffs or not hems:
            say("REFUSED no cuff or hem found for", prefix)
            return 3
        cuff = min(cuffs, key=lambda lp: lp["centre"][2])["centre"]
        hem = min(hems, key=lambda lp: lp["centre"][2])["centre"]
        inv = aw.inverted()
        pose[prefix + "UpperArm"] = round(swing_bone(arm, prefix + "UpperArm", prefix + "Hand", inv @ Vector(cuff)), 2)
        tgt = Vector((hem[0], hem[1], hem[2]))  # the drawn stance: a hem may stand ahead of the other
        pose[prefix + "UpperLeg"] = round(swing_bone(arm, prefix + "UpperLeg", prefix + "Foot", inv @ tgt), 2)
        flat_foot(arm, prefix + "Foot")
    rep["pose_deg"] = pose
    say("pose", pose)
    tree, polys, pco = bvh_of(body)
    # 2. the fit
    gpts = evaluated_co(g)
    fitted = {}
    fitted["garment"], rep["garment_fit"] = fit_piece(gpts, neighbours(g.data), tree, args.offset, args.keep,
                                                      args.floor, bridge, args.smooth, faces_of(g))
    say("garment", rep["garment_fit"])
    if "shoes" in cloth:
        s = cloth["shoes"]
        spts = evaluated_co(s)
        rows = body_weights(body, arm)
        rep["shoe_moves_m"] = {}
        for prefix in ("Left", "Right"):
            sgn = side_of(arm, prefix)
            foot = [i for i, r in enumerate(rows) if r.get(prefix + "Foot", 0) + r.get(prefix + "Toes", 0) > 0.5]
            fp = pco[foot]
            idx = np.where(spts[:, 0] * sgn > 0)[0]
            sp = spts[idx]
            # big enough for the foot (toe room 3 cm, 2 cm across), then its toe end 1.5 cm ahead of the toes
            k = max(1.0, (np.ptp(fp[:, 1]) + 0.03) / np.ptp(sp[:, 1]), (np.ptp(fp[:, 0]) + 0.02) / np.ptp(sp[:, 0]))
            base = np.array([(sp[:, 0].min() + sp[:, 0].max()) / 2, (sp[:, 1].min() + sp[:, 1].max()) / 2,
                             sp[:, 2].min()])
            sp = base + (sp - base) * k
            toe_f, toe_s = (fp[:, 1].max(), sp[:, 1].max()) if front > 0 else (fp[:, 1].min(), sp[:, 1].min())
            move = np.array([(fp[:, 0].min() + fp[:, 0].max() - sp[:, 0].min() - sp[:, 0].max()) / 2,
                             toe_f + front * 0.015 - toe_s, fp[:, 2].min() - 0.004 - sp[:, 2].min()])
            spts[idx] = sp + move
            rep["shoe_moves_m"][prefix] = {"scale": round(float(k), 4), "move": move.round(4).tolist()}
        sfit, pushed = push_out(spts, tree, args.floor, faces_of(s))
        sfit = pts_s = np.array(F.smooth((sfit - spts).tolist(), neighbours(s.data), 4, 0.5)) + spts
        sfit, pushed2 = push_out(pts_s, tree, args.floor, faces_of(s))
        fitted["shoes"] = sfit
        rep["shoes_fit"] = {"pushed": pushed, "pushed_after_smooth": pushed2}
        say("shoes", rep["shoe_moves_m"], rep["shoes_fit"])
    # 3. the weights, 4. back to rest
    rows = body_weights(body, arm)
    mats = deform_mats(arm)
    rep["weights"] = {}
    weights, floors = {}, {}
    for name, o in cloth.items():
        pts = fitted[name]
        faces = [list(p.vertices) for p in o.data.polygons]
        nrm = vertex_normals(pts, faces)
        _s_n, n_n = signed(pts, tree)
        if float(np.mean(np.sum(nrm * n_n, axis=1))) < 0:  # the cloth's faces wound inward
            nrm = -nrm
        cr, other = nearest_rows(pts, tree, polys, pco, rows, nrm)
        s_now, _ = signed(pts, tree)
        # only where the cloth truly bridges (the fit's --bridge: the crotch, under the arms); a loose sleeve keeps
        # the body's own weights, else its shoulder and elbow blend across the joint and the arm pokes through
        bridge_mask = [smoothstep((si - bridge[0]) / (bridge[1] - bridge[0])) for si in s_now]
        keys = sorted({b for r in cr for b in r})
        vals = [[r.get(b, 0.0) for b in keys] for r in cr]
        nb = neighbours(o.data)
        vals = F.smooth(vals, nb, 2, 0.3)
        vals = F.smooth(vals, nb, 20, 0.6, mask=bridge_mask)
        cr = [F.limit(dict(zip(keys, v))) for v in vals]
        if name == "shoes":  # a shoe is stiff: its Foot and Toes only, never the shin
            for prefix in ("Left", "Right"):
                for i in np.where(pts[:, 0] * side_of(arm, prefix) > 0)[0]:
                    cr[i] = F.rigid(cr[i], (prefix + "Foot", prefix + "Toes"), prefix + "Foot")
        arm_w = np.array([sum(w for b, w in r.items() if b.endswith(("UpperArm", "LowerArm"))) for r in cr])
        floors[name] = np.where(arm_w > 0.5, args.floor_arm, args.floor)
        weights[name] = cr
        rest = np.array([F.unskin(tuple(p), r, mats) for p, r in zip(pts, cr)])
        set_co(o, rest)
        write_groups(o, cr, arm)
        rep["weights"][name] = {"bones": len(keys), "bridged": int(sum(m > 0.5 for m in bridge_mask)),
                                "unweighted": sum(1 for r in cr if not r), "took_facing_face": other,
                                "arm_floor_vertices": int((arm_w > 0.5).sum())}
    bpy.context.view_layer.update()
    rep["reskin_error_mm"] = {n: round(float(np.linalg.norm(evaluated_co(o) - fitted[n], axis=1).max()) * 1000, 3)
                              for n, o in cloth.items()}
    say("reskin error mm", rep["reskin_error_mm"])
    # 4b. the clearance in both poses: the weights are the body's, but blended over a face they are not its vertex
    # weights, so the rested cloth can cross the rest body (the shoulders, the toes). Push out in rest, re-check in
    # the fitted pose (a push there is unskinned back), a few rounds.
    fitted_pose = {pb.name: pb.matrix_basis.copy() for pb in arm.pose.bones}
    rep["clearance"] = []
    for it in range(args.clear_iters):
        for pb in arm.pose.bones:
            pb.matrix_basis = Matrix()
        bpy.context.view_layer.update()
        rtree = bvh_of(body)[0]
        rnd = {}
        for name, o in cloth.items():
            new, n_rest = push_out(evaluated_co(o), rtree, floors[name], faces_of(o))
            set_co(o, new)
            rnd[name] = {"rest": n_rest}
        for pb in arm.pose.bones:
            pb.matrix_basis = fitted_pose[pb.name]
        bpy.context.view_layer.update()
        ptree = bvh_of(body)[0]
        mats = deform_mats(arm)
        for name, o in cloth.items():
            posed = evaluated_co(o)
            new, n_fit = push_out(posed, ptree, floors[name], faces_of(o))
            moved = np.where(np.linalg.norm(new - posed, axis=1) > 1e-7)[0]
            if len(moved):
                restc = np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices])
                for i in moved:
                    restc[i] = F.unskin(tuple(new[i]), weights[name][i], mats)
                set_co(o, restc)
            rnd[name]["fitted"] = n_fit
        bpy.context.view_layer.update()
        rep["clearance"].append(rnd)
        say("clearance round", it, rnd)
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix()
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "fit_base.blend"), compress=True)
    say("wrote", out / "fit_base.blend")
    # 5. the female fit
    if args.female:
        base_rest = np.array([(body.matrix_world @ v.co)[:] for v in body.data.vertices])
        with bpy.data.libraries.load(str(Path(args.female).resolve())) as (src, dst2):
            dst2.objects = ["Body"]
        fem = dst2.objects[0]
        fco = np.array([(fem.matrix_world @ v.co)[:] for v in fem.data.vertices])
        if fco.shape != base_rest.shape:
            say("REFUSED the female body's vertices differ from the base's")
            return 4
        diff = fco - base_rest
        btree = BVHTree.FromPolygons([tuple(c) for c in base_rest], polys)
        set_co(body, fco)
        ftree = BVHTree.FromPolygons([tuple(c) for c in fco], polys)
        rep["female"] = {"body": str(args.female), "body_moved_max_mm": round(float(np.linalg.norm(diff, axis=1).max()) * 1000, 1)}
        for name, o in cloth.items():
            pts = np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices])
            d = []
            for p in pts:
                loc, _n, fi, _dd = btree.find_nearest(Vector(p))
                vs = polys[fi]
                bary = poly_3d_calc([Vector(base_rest[v]) for v in vs], loc)
                d.append(sum(b * diff[v] for v, b in zip(vs, bary)).tolist())
            d = np.array(F.smooth(d, neighbours(o.data), 6, 0.5))
            new, pushed = push_out(pts + d, ftree, floors[name], faces_of(o))
            hugged = 0
            if name == "garment":  # the bib and the top follow the chest the female shape adds (art #196)
                fd = []
                for p in new:
                    loc, _n, fi, _dd = ftree.find_nearest(Vector(p))
                    vs = polys[fi]
                    bary = poly_3d_calc([Vector(fco[v]) for v in vs], loc)
                    fd.append(float(sum(b * diff[v][1] for v, b in zip(vs, bary)) * front))
                w = np.array([F.hug_weight(x) for x in fd])
                s_f, n_f = signed(new, ftree)
                disp = (-(w * np.maximum(0.0, s_f - args.hug)))[:, None] * n_f
                disp = np.array(F.smooth(disp.tolist(), neighbours(o.data), 4, 0.5))
                hugged = int((w > 0.5).sum())
                new, pushed2 = push_out(new + disp, ftree, floors[name], faces_of(o))
                pushed += pushed2
                rep["female"]["hug_pull_max_mm"] = round(float(np.linalg.norm(disp, axis=1).max()) * 1000, 1)
            set_co(o, new)
            mv = np.linalg.norm(new - pts, axis=1)
            rep["female"][name] = {"moved": int((mv > 1e-4).sum()), "max_mm": round(float(mv.max()) * 1000, 1),
                                   "pushed": pushed, "hugged": hugged}
        bpy.data.objects.remove(fem)
        say("female", rep["female"])
        stem = Path(args.female).parent.name
        bpy.ops.wm.save_as_mainfile(filepath=str(out / f"fit_{stem}.blend"), compress=True)
        rep["female"]["blend"] = str(out / f"fit_{stem}.blend")
        say("wrote", out / f"fit_{stem}.blend")
    rep["tris"] = {n: sum(len(p.vertices) - 2 for p in o.data.polygons) for n, o in cloth.items()}
    (out / "fit.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8", newline="\n")
    say("done", rep["tris"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
