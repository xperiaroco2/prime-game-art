"""Bodies by drawing, step D3 (art #196): the Blender side of the station fit (body_fit_geom.py does the maths,
no bpy; body_fit_run.py drives it in plain Python).

    blender -b --factory-startup --python tools/blender/body_fit_blend.py -- dump --body <alien_body.blend> --out <dump.json>
    blender -b --factory-startup --python tools/blender/body_fit_blend.py -- apply --body <alien_body.blend>
        --fit <fit.json> --out <dir>

`dump` (read only): the Body mesh's world vertices, every vertex's weights, its edges, the armature's bones (world
head, tail, parent) and the open boundary loops. `apply`: opens the source body, writes the fit's vertices and bone
rest (heads and tails; the rolls and the rest orientations kept), puts the neck ring's weights on Neck and Head only
(the ADR, docs/decisions/2026-10-29-neck-ring.md), with `--round-toes M` gives the feet a soft rounded front (no
separate toes; round_toes) and saves <dir>/alien_body.blend; an out folder holding one is
refused, the source is never saved. Then it reopens the saved file and proves it (faces, edges, groups and UVs hash
as the source's; the vertices as the fit's) into <dir>/apply.json.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from alien_body_female import mesh_hashes  # noqa: E402


def open_loops(me) -> list:
    """Open boundary loops (edges with one face) as ordered vertex index lists."""
    count: dict = {}
    for p in me.polygons:
        for ek in p.edge_keys:
            count[ek] = count.get(ek, 0) + 1
    nbr: dict = {}
    for (a, b), n in count.items():
        if n == 1:
            nbr.setdefault(a, []).append(b)
            nbr.setdefault(b, []).append(a)
    seen, out = set(), []
    for start in nbr:
        if start in seen:
            continue
        loop, prev, cur = [start], None, start
        seen.add(start)
        while True:
            nxt = [v for v in nbr[cur] if v != prev and v not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            seen.add(cur)
            loop.append(cur)
        out.append(loop)
    return out


TOE_STEP = 0.003  # m: how far a vertex inside the toes' hull creeps out per round


def round_toes(body, arm, behind: float, iters: int) -> dict:
    """The feet's soft rounded front (the D3 brief, item 3: no separate toes): per foot, the region ahead of
    `behind` m behind its Toes bone's head (low, on the foot's bones) is shrink-wrapped onto its convex hull from the
    inside: `iters` rounds of umbrella smoothing, after each every vertex inside the hull creeps out along the ray
    from the region's centre through it, at most TOE_STEP m a round (only outwards: the gaps between the toes fill
    from their floors while the outer surface stays on the hull), by a weight easing in over `behind`; then two light
    passes soften the hull's facets. (D3's find_nearest sent a gap's vertex to the nearest hull face, often the sole,
    and left the gaps; D3b's first try projected in one go and folded the gaps' floors into slits.) Rest pose, world
    space; the weights stay. Returns the moved vertices and the largest move."""
    import bmesh
    from mathutils.bvhtree import BVHTree
    me, mw = body.data, body.matrix_world
    inv = mw.inverted()
    names = [g.name for g in body.vertex_groups]
    co = [mw @ v.co for v in me.vertices]
    nbr = [[] for _ in me.vertices]
    for e in me.edges:
        a, b = e.vertices
        nbr[a].append(b)
        nbr[b].append(a)
    wt = [0.0] * len(co)
    trees = []
    for side, sg in (("Left", 1), ("Right", -1)):
        th = arm.matrix_world @ arm.data.bones[f"{side}Toes"].head_local
        reg = []
        for v in me.vertices:
            p = co[v.index]
            foot = sum(g.weight for g in v.groups if names[g.group] in (f"{side}Foot", f"{side}Toes"))
            if p.x * sg > 0 and foot > 0.2 and p.y < th.y + behind and p.z < th.z + 0.06:
                reg.append(v.index)
        bm = bmesh.new()
        for i in reg:
            bm.verts.new(co[i])
        bmesh.ops.convex_hull(bm, input=list(bm.verts))
        tree = BVHTree.FromBMesh(bm)
        c = sum((co[i] for i in reg), Vector()) / len(reg)
        for i in reg:
            t = min(1.0, max(0.0, (th.y + behind - co[i].y) / behind))
            wt[i] = t * t * (3 - 2 * t)
        trees.append((reg, tree, c, bm))
    def out_to_hull(pts):
        for reg, tree, c, _ in trees:
            for i in reg:
                d = pts[i] - c
                if d.length < 1e-6:
                    continue
                hit = tree.ray_cast(c, d.normalized(), 1.0)
                if hit[0] is not None and (hit[0] - c).length > d.length:
                    gap = (hit[0] - c).length - d.length
                    pts[i] = pts[i] + d.normalized() * min(gap, TOE_STEP) * wt[i]
        return pts

    def relax(pts, k):
        nxt = list(pts)
        for i, w in enumerate(wt):
            if w > 0 and nbr[i]:
                avg = sum((pts[j] for j in nbr[i]), Vector()) / len(nbr[i])
                nxt[i] = pts[i].lerp(avg, k * w)
        return nxt
    for _ in range(iters):
        co = out_to_hull(relax(co, 0.5))
    for _ in range(2):
        co = relax(co, 0.3)
    for _, _, _, bm in trees:
        bm.free()
    moved = [i for i, w in enumerate(wt) if w > 0]
    big = max(((mw @ me.vertices[i].co) - co[i]).length for i in moved) if moved else 0.0
    for i in moved:
        me.vertices[i].co = inv @ co[i]
    me.update()
    return {"moved": moved, "max_move_m": round(big, 5), "behind_m": behind, "iters": iters}


def new_forefoot(body, arm, table: dict, cut_behind: float) -> dict:
    """D3c item 1: per foot, the region ahead of a plane `cut_behind` m behind the Toes head is cut off and replaced
    by a new closed mitten front (body_feet_geom.forefoot) grown from the cut's loop to the foot table's length
    (from the kept heel), width and toe height; its weights from the old toes' nearest vertex (Foot and Toes only);
    then a Taubin smoothing over the front and 45 mm behind the cut, and a plain one over the ankle's front (its
    dent). Rest pose, world space. Returns per foot the numbers and the zone the proof leaves out."""
    import bmesh
    from mathutils.kdtree import KDTree
    import body_feet_geom as FG
    me, mw = body.data, body.matrix_world
    inv = mw.inverted()
    names = [g.name for g in body.vertex_groups]
    gidx = {n: i for i, n in enumerate(names)}
    bm = bmesh.new()
    bm.from_mesh(me)
    dl = bm.verts.layers.deform.verify()
    uvl = bm.loops.layers.uv.active
    shapes = list(bm.verts.layers.shape)
    for v in bm.verts:
        v.co = mw @ v.co
    out = {"shape_keys": bool(me.shape_keys)}
    for side, sg in (("Left", 1), ("Right", -1)):
        th = arm.matrix_world @ arm.data.bones[f"{side}Toes"].head_local
        fi, ti = gidx[f"{side}Foot"], gidx[f"{side}Toes"]
        def foot_w(v):
            return v[dl].get(fi, 0.0) + v[dl].get(ti, 0.0)
        reg = [v for v in bm.verts if v.co.x * sg > 0 and v.co.z < 0.25 and foot_w(v) > 0.2]
        heel_y = max(v.co.y for v in reg)
        def loops_at(y):  # how many loops a cut at y makes (edges crossing it, joined through their faces)
            cross = {e for v in reg for e in v.link_edges
                     if (e.verts[0].co.y - y) * (e.verts[1].co.y - y) < 0}
            par = {e: e for e in cross}
            def root(e):
                while par[e] is not e:
                    e = par[e]
                return e
            for e in cross:
                for f in e.link_faces:
                    for e2 in f.edges:
                        if e2 in cross:
                            par[root(e2)] = root(e)
            return len({root(e) for e in cross})
        tries = [cut_behind + 0.005 * k for k in range(9)]
        y0 = th.y + next((c for c in tries if loops_at(th.y + c) == 1), tries[-1])
        geom = list({e for v in reg for e in v.link_edges}) + list({f for v in reg for f in v.link_faces})
        bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-7, plane_co=(0, y0, 0), plane_no=(0, 1, 0))
        reg = [v for v in bm.verts if v.co.x * sg > 0 and v.co.z < 0.25 and foot_w(v) > 0.05]
        old = [v for v in reg if v.co.y < y0 - 1e-6]
        kd = KDTree(len(old))
        for k, v in enumerate(old):
            kd.insert(v.co, k)
        kd.balance()
        old_w = [(v[dl].get(fi, 0.0), v[dl].get(ti, 0.0)) for v in old]
        bmesh.ops.delete(bm, geom=old, context="VERTS")
        bm.verts.index_update()
        bm.verts.ensure_lookup_table()
        bedges = [e for e in bm.edges if e.is_boundary and all(abs(v.co.y - y0) < 1e-5 and v.co.x * sg > 0
                                                               for v in e.verts)]
        loop = FG.order_loop([(e.verts[0].index, e.verts[1].index) for e in bedges])
        a, b = bm.verts[loop[0]], bm.verts[loop[1]]
        e01 = bm.edges.get((a, b))
        f = e01.link_faces[0]
        lo = next(lp for lp in f.loops if lp.vert == a)
        if lo.link_loop_next.vert != b:  # the body's face must run B_j -> B_j+1
            loop = [loop[0]] + loop[1:][::-1]
        bv = [bm.verts[i] for i in loop]
        uv_of = {}
        for v in bv:
            ls = [lp for lp in v.link_loops]
            uv_of[v] = tuple(ls[0][uvl].uv) if (ls and uvl) else (0.0, 0.0)
        tip_y = FG.tip_from_table(heel_y, table["length"] / 1000.0)
        pts, faces = FG.forefoot([tuple(v.co) for v in bv], tip_y, table["width"] / 1000.0,
                                 table["toe_height"] / 1000.0)
        nb = len(bv)
        verts = list(bv)
        mat = f.material_index
        for p in pts[nb:]:
            nv = bm.verts.new(p)
            k = kd.find(nv.co)[1]
            wf, wtoe = old_w[k]
            tot = (wf + wtoe) or 1.0
            nv[dl][fi], nv[dl][ti] = wf / tot, wtoe / tot
            if wtoe <= 0:
                del nv[dl][ti]
            for sl in shapes:
                nv[sl] = inv @ nv.co
            verts.append(nv)
        newf = []
        for fc in faces:
            nf = bm.faces.new([verts[i] for i in fc])
            nf.smooth, nf.material_index = True, mat
            newf.append(nf)
        bm.verts.ensure_lookup_table()
        bm.verts.index_update()
        # UVs: each new vertex takes its column's boundary UV (the body is one plain clay colour)
        col_uv = [uv_of[v] for v in bv]
        vpos = {v: k for k, v in enumerate(verts)}
        nc = (len(pts) - nb - 1) // 14
        if uvl:
            for nf in newf:
                for lp in nf.loops:
                    k = vpos[lp.vert]
                    lp[uvl].uv = (col_uv[k] if k < nb else col_uv[0] if k == len(verts) - 1
                                  else col_uv[((k - nb) % nc) // (nc // nb)])
        # smoothing: the front and a 25 mm blend zone behind the cut (Taubin); the ankle's front (plain)
        allv = list(bm.verts)
        idx = {v: i for i, v in enumerate(allv)}
        P = [tuple(v.co) for v in allv]
        nbr = [[idx[e.other_vert(v)] for e in v.link_edges] for v in allv]
        newset = set(verts[nb:])
        wt = [0.0] * len(allv)
        zone = []
        for i, v in enumerate(allv):
            if v.co.x * sg <= 0 or v.co.z > 0.25 or foot_w(v) <= 0.05:
                continue
            if v in newset:
                wt[i] = 1.0
            elif v.co.y < y0 + 0.045:
                wt[i] = 1.0 - FG.smoothstep(y0 - 0.002, y0 + 0.045, v.co.y)
            if wt[i] > 0:
                zone.append(i)
        P = FG.taubin(P, nbr, wt, 12)
        ank_z = table["ankle_z"] / 1000.0
        mid_y = sum(v.co.y for v in bv) / nb
        top0 = max(v.co.z for v in bv)
        zd = 0.5 * (top0 + ank_z)
        wa = [0.0] * len(allv)
        for i, v in enumerate(allv):
            if v.co.x * sg > 0 and v.co.z < ank_z + 0.06 and v.co.y < heel_y - 0.06 and v.co.y > y0 - 0.001:
                wa[i] = (1.0 - FG.smoothstep(0.025, 0.07, abs(v.co.z - zd))) * \
                    FG.smoothstep(heel_y - 0.05, heel_y - 0.11, v.co.y)
                if wa[i] > 0 and i not in zone:
                    zone.append(i)
        P = FG.laplace(P, nbr, wa, 40, 0.5)  # the ankle front's fold (S4b's own) needs many rounds to fill
        P = FG.taubin(P, nbr, [max(a, b) for a, b in zip(wt, wa)], 6)
        for v, p in zip(allv, P):
            v.co = Vector(p)
        front = FG.front_extent([P[idx[v]] for v in verts])
        loc = [P[idx[v]] for v in verts]
        loc_f = [tuple(vpos[lp.vert] for lp in nf.loops) for nf in newf]
        out[side] = {"cut_y_m": round(y0, 5), "heel_y_m": round(heel_y, 5), "tip_y_m": round(tip_y, 5),
                     "loop": nb, "new_verts": len(pts) - nb, "new_faces": len(faces), "deleted": len(old),
                     "length_mm": round((heel_y - front["min_y"]) * 1000, 1),
                     "width_mm": round(front["width"] * 1000, 1), "top_mm": round(front["top"] * 1000, 1),
                     "sole_mm": round(front["sole"] * 1000, 1),
                     "front_dihedral_max_deg": round(FG.dihedral_max(loc, loc_f), 1),
                     "zone": len(zone), "zone_box": [min(P[i][1] for i in zone), max(P[i][2] for i in zone)]}
    for v in bm.verts:
        v.co = inv @ v.co
    bm.to_mesh(me)
    bm.free()
    me.update()
    return out


def _objs():
    return bpy.data.objects["Body"], bpy.data.objects["CharacterArmature"]


def dump(body_path: str, out: str) -> int:
    bpy.ops.wm.open_mainfile(filepath=str(Path(body_path).resolve()))
    body, arm = _objs()
    names = [g.name for g in body.vertex_groups]
    mw, aw = body.matrix_world, arm.matrix_world
    me = body.data
    d = {"blend": body_path,
         "verts": [[round(c, 6) for c in mw @ v.co] for v in me.vertices],
         "weights": [{names[g.group]: round(g.weight, 6) for g in v.groups if g.weight > 0} for v in me.vertices],
         "edges": [list(e.vertices) for e in me.edges],
         "bones": {b.name: {"head": list(aw @ b.head_local), "tail": list(aw @ b.tail_local),
                            "parent": b.parent.name if b.parent else None} for b in arm.data.bones},
         "loops": open_loops(me)}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(d), encoding="utf-8")
    print(f"DUMP {len(d['verts'])} vertices, {len(d['edges'])} edges, {len(d['bones'])} bones, "
          f"loops {[len(x) for x in d['loops']]} -> {out}", flush=True)
    return 0


def apply(body_path: str, fit_path: str, out_dir: str, toes_behind: float = 0.0, toes_iters: int = 8,
          foot_table: str = "", cut_behind: float = 0.03) -> int:
    out = Path(out_dir)
    blend = out / "alien_body.blend"
    if blend.exists():
        print(f"REFUSED: {blend} exists", flush=True)
        return 2
    fit = json.loads(Path(fit_path).read_text(encoding="utf-8"))
    bpy.ops.wm.open_mainfile(filepath=str(Path(body_path).resolve()))
    body, arm = _objs()
    hash_a = mesh_hashes(body)
    inv = body.matrix_world.inverted()
    new = fit["verts"]
    if len(new) != len(body.data.vertices):
        print("REFUSED: vertex count differs", flush=True)
        return 2
    for v, q in zip(body.data.vertices, new):
        v.co = inv @ Vector(q)
    body.data.update()
    toes = round_toes(body, arm, toes_behind, toes_iters) if toes_behind > 0 else {"moved": []}
    ring = fit.get("ring", [])
    names = {g.name: g for g in body.vertex_groups}
    for i in ring:  # weights only on Neck and Head, their sum kept at 1
        groups = {body.vertex_groups[g.group].name: g.weight for g in body.data.vertices[i].groups}
        keep = {n: groups.get(n, 0.0) for n in ("Neck", "Head")}
        tot = sum(keep.values()) or 1.0
        for n in groups:
            if n not in keep:
                names[n].remove([i])
        for n, w in keep.items():
            if w > 0 or n == "Neck" and tot == 1.0 and not any(keep.values()):
                names[n].add([i], w / tot if any(keep.values()) else 1.0, "REPLACE")
    rest = fit.get("rest")
    if rest:
        ainv = arm.matrix_world.inverted()
        bpy.context.view_layer.objects.active = arm
        for o in bpy.context.view_layer.objects:
            o.select_set(o == arm)
        bpy.ops.object.mode_set(mode="EDIT")
        for eb in arm.data.edit_bones:
            roll = eb.roll
            r = rest[eb.name]
            eb.use_connect = False
            eb.head, eb.tail = ainv @ Vector(r["head"]), ainv @ Vector(r["tail"])
            eb.roll = roll
        bpy.ops.object.mode_set(mode="OBJECT")
    feet = {}
    if foot_table:  # D3c: a new forefoot; the ring's indices are found again by position afterwards
        import tomllib
        from mathutils.kdtree import KDTree
        table = tomllib.loads(Path(foot_table).read_text(encoding="utf-8"))["foot"]
        feet = new_forefoot(body, arm, table, cut_behind)  # on the fit's rest (B: her Toes)
        vs = body.data.vertices
        kd = KDTree(len(vs))
        for v in vs:
            kd.insert(body.matrix_world @ v.co, v.index)
        kd.balance()
        ring = [kd.find(Vector(fit["verts"][i]))[1] for i in ring]
    new = [tuple(body.matrix_world @ v.co) for v in body.data.vertices]
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True)
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    body, arm = _objs()
    hash_b = mesh_hashes(body)
    mw = body.matrix_world
    err = max(math.dist(tuple(mw @ v.co), q) for v, q in zip(body.data.vertices, new))
    same = {k: hash_a[k] == hash_b[k] for k in ("faces_sha256", "edges_sha256", "groups", "uv_sha256")}
    ring_w = sorted({body.vertex_groups[g.group].name for i in ring for g in body.data.vertices[i].groups})
    res = {"source": body_path, "fit": fit_path, "blend": str(blend), "same": same, "all_same": all(same.values()),
           "weights_changed": hash_a["weights_sha256"] != hash_b["weights_sha256"], "ring_groups": ring_w,
           "saved_vs_fit_max_m": round(err, 8),
           "toes": {k: v for k, v in toes.items() if k != "moved"} | {"moved": len(toes["moved"])},
           "feet": feet}
    if feet:  # every vertex above the feet's zone (z 0.25 m: the new fronts, the blend and the ankles' smoothing)
        from mathutils.kdtree import KDTree  # is a fit vertex, unmoved

        def in_zone(p, groups):
            return p[2] < 0.25
        kd = KDTree(len(fit["verts"]))
        for i, q in enumerate(fit["verts"]):
            kd.insert(q, i)
        kd.balance()
        off = [(new[v.index]) for v in body.data.vertices if not in_zone(new[v.index], v.groups)]
        res["off_feet_verts"] = len(off)
        res["fit_vs_built_off_toes_max_m"] = round(max((kd.find(p)[2] for p in off), default=0.0), 8)
        res["same_off_feet"] = {k: res["same"][k] for k in ("groups",)}
        res["all_same"] = res["same"]["groups"]
    else:
        res["fit_vs_built_off_toes_max_m"] = round(max((math.dist(q, r) for i, (q, r) in
                                                         enumerate(zip(fit["verts"], new))
                                                         if i not in set(toes["moved"])), default=0.0), 8)
    (out / "apply.json").write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
    print("APPLY", json.dumps(res), flush=True)
    ok = res["all_same"] and err < 1e-5 and res["fit_vs_built_off_toes_max_m"] < 1e-5
    return 0 if ok and set(ring_w) <= {"Neck", "Head"} else 1


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("dump", "apply"))
    ap.add_argument("--body", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fit", default="")
    ap.add_argument("--round-toes", type=float, default=0.0, help="m behind the Toes heads: the rounded front")
    ap.add_argument("--toes-iters", type=int, default=8)
    ap.add_argument("--foot-table", default="", help="a body_dims table: its [foot] gives the new forefoot (D3c)")
    ap.add_argument("--cut-behind", type=float, default=0.03, help="m behind the Toes heads: the forefoot's cut")
    a = ap.parse_args(argv)
    return dump(a.body, a.out) if a.mode == "dump" else apply(a.body, a.fit, a.out, a.round_toes, a.toes_iters,
                                                              a.foot_table, a.cut_behind)


if __name__ == "__main__":
    sys.exit(main())
