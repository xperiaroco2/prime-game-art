"""The alien's hand and wrist mesh rebuilt in place (art #196, Hands H1b; the maths in alien_hand_geom.py, the spec in
tools/blender/body_dims/hand_dims.toml, the driver alien_hand_run.py). Headless Blender:

    blender -b --factory-startup --python-exit-code 1 --python tools/blender/alien_hand_mesh.py -- dump \
        --blend <in.blend> --out <dump.json> [--bend 30]
    blender -b ... -- apply --blend <in.blend> --moves <moves.json> --out <out.blend>

- `dump`: per skinned mesh its name, vertex and face counts and a topology hash; every vertex weighted on a hand
  region bone (the LowerArm, the Hand and the five finger chains of each side): its rest position (world), its
  region weights (normalised over all its groups), its other weight, its faces' material names; the region's edges;
  the region bones' rest heads, tails and x/z axes. `--bend DEG`: the region vertices posed with each Hand bent
  +-DEG about its own x and z axes (no action), for the wrist's cross-section table.
- `apply`: moves the named vertices (world positions, by object name and index; every shape key moved by the same
  step), refuses a changed topology or an existing `--out`, saves `--out` and `<out>.json` (moved count, largest
  move, the topology hash before and after, every other vertex's largest move: 0).
- `rings` (H1c): new rows on the wrist: every skin edge of the band (`--band`, Hand lengths from the wrist) cut
  `cuts` times (bmesh: the new vertices on the old surface, their weights, UVs and shape keys interpolated, appended
  after the old ones, so every old index and position stays), then the LowerArm/Hand split smoothed across the band
  only (`smooth` rounds); `--grid c:s,...` tries variants (a `--dump-dir` dump each, with `--bend`); `--edges-out`
  / `--edges-in` carry the same cut from body A to B (by index) and to a dressed character (by rest position), so
  both bodies keep one topology. `<out>.json`: the counts, every old vertex's largest move (0) and the new weights.
- `diff --blend <before> --other <after> --out <json>`: the whole-body check, per mesh object over the old indices:
  the largest move and weight change outside the hand region (0) and the hand region's largest move.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

SIDES = ("Left", "Right")
CHAINS = {"Thumb": ("Metacarpal", "Proximal", "Distal"), "Index": ("Proximal", "Intermediate", "Distal"),
          "Middle": ("Proximal", "Intermediate", "Distal"), "Ring": ("Proximal", "Intermediate", "Distal"),
          "Little": ("Proximal", "Intermediate", "Distal")}


def region_bones() -> list:
    out = []
    for s in SIDES:
        out += [f"{s}LowerArm", f"{s}Hand"] + [f"{s}{f}{p}" for f, ps in CHAINS.items() for p in ps]
    return out


def _arm():
    return next(o for o in bpy.data.objects if o.type == "ARMATURE")


def _meshes(arm):
    return [o for o in bpy.data.objects if o.type == "MESH"
            and any(m.type == "ARMATURE" and m.object == arm for m in o.modifiers)]


def topo_hash(me) -> str:
    h = hashlib.sha256()
    h.update(str(len(me.vertices)).encode())
    for p in me.polygons:
        h.update((",".join(map(str, p.vertices)) + ";").encode())
    return h.hexdigest()[:16]


def _region(o, names: set) -> dict:
    gname = {g.index: g.name for g in o.vertex_groups}
    out = {}
    for v in o.data.vertices:
        rw, other = {}, 0.0
        for g in v.groups:
            n = gname.get(g.group)
            if g.weight <= 0 or n is None:
                continue
            if n in names:
                rw[n] = g.weight
            else:
                other += g.weight
        if rw:
            t = sum(rw.values()) + other
            out[v.index] = ({k: round(x / t, 5) for k, x in rw.items()}, round(other / t, 5))
    return out


def dump(blend: str, out: str, bend: float) -> int:
    bpy.ops.wm.open_mainfile(filepath=blend)
    return _dump_scene(blend, out, bend)


def _dump_scene(blend: str, out: str, bend: float) -> int:
    arm = _arm()
    names = set(region_bones())
    bones = {}
    for b in arm.data.bones:
        if b.name in names:
            m = arm.matrix_world @ b.matrix_local
            bones[b.name] = {"head": list(arm.matrix_world @ b.head_local), "tail": list(arm.matrix_world @ b.tail_local),
                             "x": list(m.to_3x3().col[0].normalized()), "z": list(m.to_3x3().col[2].normalized())}
    res = {"blend": blend, "bones": bones, "objects": []}
    for o in _meshes(arm):
        me, mw = o.data, o.matrix_world
        reg = _region(o, names)
        mats = [m.name if m else "" for m in me.materials]
        vmat = {}
        for p in me.polygons:
            for i in p.vertices:
                if i in reg:
                    vmat.setdefault(i, set()).add(mats[p.material_index] if p.material_index < len(mats) else "")
        idx = sorted(reg)
        edges = [list(e.vertices) for e in me.edges if e.vertices[0] in reg and e.vertices[1] in reg]
        res["objects"].append({
            "name": o.name, "verts": len(me.vertices), "faces": len(me.polygons), "topo": topo_hash(me),
            "shape_keys": len(me.shape_keys.key_blocks) if me.shape_keys else 0,
            "index": idx, "co": [[round(c, 6) for c in (mw @ me.vertices[i].co)] for i in idx],
            "w": [reg[i][0] for i in idx], "other": [reg[i][1] for i in idx],
            "mat": [sorted(vmat.get(i, ())) for i in idx], "edges": edges})
    if bend:
        if arm.animation_data:
            arm.animation_data.action = None
        res["bends"] = {}
        for s in SIDES:
            for ax in ("x", "z"):
                for sign in (1, -1):
                    for pb in arm.pose.bones:
                        pb.rotation_mode = "QUATERNION"
                        pb.location = (0, 0, 0)
                        pb.rotation_quaternion = (1, 0, 0, 0)
                    v = Vector((1, 0, 0)) if ax == "x" else Vector((0, 0, 1))
                    arm.pose.bones[f"{s}Hand"].rotation_quaternion = Matrix.Rotation(
                        sign * bend * 3.14159265 / 180, 4, v).to_quaternion()
                    bpy.context.view_layer.update()
                    dg = bpy.context.evaluated_depsgraph_get()
                    key = f"{s}_{ax}{'+' if sign > 0 else '-'}{bend:g}"
                    res["bends"][key] = {}
                    for o, ob in zip(_meshes(arm), res["objects"]):
                        ev = o.evaluated_get(dg)
                        em = ev.to_mesh()
                        mw = o.matrix_world
                        res["bends"][key][o.name] = [[round(c, 6) for c in (mw @ em.vertices[i].co)]
                                                     for i in ob["index"]]
                        ev.to_mesh_clear()
                    pbh = arm.pose.bones[f"{s}Hand"]
                    res["bends"][key]["_tail"] = list(arm.matrix_world @ pbh.tail)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(res))
    print(f"dump: {len(res['objects'])} mesh(es) -> {out}")
    return 0


def apply(blend: str, moves_path: str, out: str) -> int:
    if Path(out).exists():
        raise SystemExit(f"{out} exists: never overwritten")
    bpy.ops.wm.open_mainfile(filepath=blend)
    moves = json.loads(Path(moves_path).read_text())
    arm = _arm()
    rep = {"blend": blend, "out": out, "objects": {}}
    for o in _meshes(arm):
        mv = moves.get("objects", {}).get(o.name)
        if not mv:
            continue
        me = o.data
        before = topo_hash(me)
        old = [v.co.copy() for v in me.vertices]
        inv = o.matrix_world.inverted()
        largest = 0.0
        for i, p in mv.items():
            i = int(i)
            new = inv @ Vector(p)
            d = new - me.vertices[i].co
            largest = max(largest, d.length)
            me.vertices[i].co = new
            if me.shape_keys:
                for kb in me.shape_keys.key_blocks:
                    kb.data[i].co = kb.data[i].co + d
        me.update()
        keep = set(int(i) for i in mv)
        other = max(((me.vertices[i].co - old[i]).length for i in range(len(old)) if i not in keep), default=0.0)
        after = topo_hash(me)
        if after != before:
            raise SystemExit(f"{o.name}: topology changed")
        rep["objects"][o.name] = {"moved": len(mv), "largest_mm": round(largest * 1000, 2), "topo": after,
                                  "others_largest_mm": round(other * 1000, 4), "verts": len(me.vertices)}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    Path(out + ".json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep))
    return 0


def _skin_object(arm):
    """The skin object: the body's "Body", or the dressed character's object with the skin material."""
    ms = _meshes(arm)
    body = [o for o in ms if o.name == "Body"]
    if body:
        return body[0]
    skin = [o for o in ms if any(m and ("skin" in m.name.lower() or m.name == "M_AlienBody") for m in o.data.materials)]
    return max(skin, key=lambda o: len(o.data.vertices))


def _skin_faces(o) -> set:
    if o.name == "Body":
        return set(range(len(o.data.materials) or 1))
    return {k for k, m in enumerate(o.data.materials) if m and ("skin" in m.name.lower() or m.name == "M_AlienBody")}


def _band_edges(arm, o, lo: float, hi: float, rmax: float = 0.09) -> list:
    """The edges of the skin faces whose every vertex lies in either wrist's band: from lo to hi Hand lengths along
    the forearm's axis from the Hand bone's head, within rmax of the axis."""
    mw, me = o.matrix_world, o.data
    inband = set()
    for s in SIDES:
        lb, hb = arm.data.bones[f"{s}LowerArm"], arm.data.bones[f"{s}Hand"]
        org = arm.matrix_world @ hb.head_local
        d = ((arm.matrix_world @ lb.tail_local) - (arm.matrix_world @ lb.head_local)).normalized()
        L = ((arm.matrix_world @ hb.tail_local) - org).length
        for v in me.vertices:
            r = (mw @ v.co) - org
            t = r.dot(d)
            if lo * L <= t <= hi * L and (r - d * t).length <= rmax:
                inband.add(v.index)
    mats = _skin_faces(o)
    edges = set()
    for p in me.polygons:
        if p.material_index in mats and all(i in inband for i in p.vertices):
            for k in p.edge_keys:
                edges.add(tuple(sorted(k)))
    return sorted(edges)


def _ring_once(arm, o, pairs: list, cuts: int, smooth: int, alpha: float = 0.5) -> dict:
    """Cuts the band's edges (new rows between the old ones; positions on the old surface, weights and shape keys
    interpolated by bmesh), then smooths the LowerArm/Hand split (the Hand share of their sum) across the band only;
    every other weight and every old vertex's position is kept."""
    import bmesh
    me, mw = o.data, o.matrix_world
    old_co = [v.co.copy() for v in me.vertices]
    n0, f0 = len(me.vertices), len(me.polygons)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    edges = [bm.edges.get((bm.verts[a], bm.verts[b])) for a, b in pairs]
    missing = sum(e is None for e in edges)
    edges = [e for e in edges if e is not None]
    band_i = {v.index for e in edges for v in e.verts}
    bmesh.ops.subdivide_edges(bm, edges=edges, cuts=cuts, use_grid_fill=True, smooth=0.0)
    bm.verts.index_update()  # the old vertices keep 0..n0-1 (checked below by their positions), the new ones follow
    bm.verts.ensure_lookup_table()
    new = list(bm.verts[n0:])
    band = {bm.verts[i] for i in band_i} | set(new)
    dl = bm.verts.layers.deform.active
    gi = {g.name: g.index for g in o.vertex_groups}
    rep_sides = {}
    for s in SIDES:
        li, hi = gi[f"{s}LowerArm"], gi[f"{s}Hand"]
        t = {}
        for v in band:
            w = v[dl]
            sm = w.get(li, 0.0) + w.get(hi, 0.0)
            if sm > 1e-6:
                t[v] = w.get(hi, 0.0) / sm
        nb = {v: [e.other_vert(v) for e in v.link_edges if e.other_vert(v) in t] for v in t}
        for _ in range(smooth):
            t = {v: (1 - alpha) * x + alpha * (sum(t[u] for u in nb[v]) / len(nb[v]) if nb[v] else x)
                 for v, x in t.items()}
        for v, x in t.items():
            w = v[dl]
            sm = w.get(li, 0.0) + w.get(hi, 0.0)
            w[li], w[hi] = sm * (1 - x), sm * x
        rep_sides[s] = len(t)
    wsum = [sum(v[dl].values()) for v in new]
    bm.to_mesh(me)
    bm.free()
    me.update()
    others = max(((me.vertices[i].co - old_co[i]).length for i in range(n0)), default=0.0)
    return {"object": o.name, "verts_before": n0, "verts_after": len(me.vertices), "new_verts": len(new),
            "faces_before": f0, "faces_after": len(me.polygons), "cut_edges": len(edges), "edges_missing": missing,
            "cuts": cuts, "smooth": smooth, "smoothed": rep_sides,
            "old_verts_largest_move_mm": round(others * 1000, 4),
            "new_weight_sum": [round(min(wsum), 4), round(max(wsum), 4)] if wsum else None}


def rings(blend: str, out: str, edges_in: str, edges_out: str, grid: str, dump_dir: str, bend: float,
          lo: float, hi: float) -> int:
    from mathutils import kdtree
    if out and Path(out).exists():
        raise SystemExit(f"{out} exists: never overwritten")
    reps = {}
    variants = [tuple(int(x) for x in g.split(":")) for g in grid.split(",")]
    for cuts, smooth in variants:
        bpy.ops.wm.open_mainfile(filepath=blend)
        arm = _arm()
        o = _skin_object(arm)
        mw = o.matrix_world
        if edges_in:
            ein = json.loads(Path(edges_in).read_text())
            if len(o.data.vertices) == ein["verts"] and o.name == ein["object"]:
                pairs = [tuple(e) for e in ein["index"]]
            else:  # a dressed character: its vertices found by the body's rest positions, within 0.1 mm
                kd = kdtree.KDTree(len(o.data.vertices))
                for v in o.data.vertices:
                    kd.insert(mw @ v.co, v.index)
                kd.balance()
                pairs = []
                for ca, cb in ein["co"]:
                    (pa, ia, da), (pb, ib, db) = kd.find(Vector(ca)), kd.find(Vector(cb))
                    if da <= 1e-4 and db <= 1e-4:
                        pairs.append(tuple(sorted((ia, ib))))
        else:
            pairs = _band_edges(arm, o, lo, hi)
        if edges_out:
            Path(edges_out).parent.mkdir(parents=True, exist_ok=True)
            Path(edges_out).write_text(json.dumps({"object": o.name, "verts": len(o.data.vertices), "index": pairs,
                                                   "co": [[[round(c, 6) for c in (mw @ o.data.vertices[i].co)]
                                                           for i in e] for e in pairs]}))
        r = _ring_once(arm, o, pairs, cuts, smooth)
        r["pairs"] = len(pairs)
        tag = f"c{cuts}s{smooth}"
        reps[tag] = r
        print("RINGS", tag, json.dumps(r), flush=True)
        if out:  # saved before the dump, which poses the bones and unlinks the action
            if len(variants) != 1:
                raise SystemExit("--out needs one variant")
            Path(out).parent.mkdir(parents=True, exist_ok=True)
            bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
            Path(out + ".json").write_text(json.dumps(r, indent=1))
        if dump_dir:
            _dump_scene(out or blend, str(Path(dump_dir) / f"{tag}.json"), bend)
    return 0


JOINTS = {"Thumb": ("Proximal", "Distal"), "Index": ("Proximal", "Intermediate", "Distal"),
          "Middle": ("Proximal", "Intermediate", "Distal"), "Ring": ("Proximal", "Intermediate", "Distal")}


def _joint_edges(arm, o, half: float, rmax: float) -> tuple:
    """The skin faces' edges whose every vertex lies within `half` (m) of a finger or thumb joint along its bone and
    within rmax of the bone's axis (the joint: the bone's head; its axis the bone's own), both hands."""
    mw, me = o.matrix_world, o.data
    inband, per = set(), {}
    cos = [mw @ v.co for v in me.vertices]
    for s in SIDES:
        for f, segs in JOINTS.items():
            for seg in segs:
                b = arm.data.bones[f"{s}{f}{seg}"]
                org = arm.matrix_world @ b.head_local
                d = ((arm.matrix_world @ b.tail_local) - org).normalized()
                n = 0
                for i, c in enumerate(cos):
                    r = c - org
                    t = r.dot(d)
                    if -half <= t <= half and (r - d * t).length <= rmax:
                        inband.add(i)
                        n += 1
                per[f"{s}{f}{seg}"] = n
    mats = _skin_faces(o)
    edges = set()
    for p in me.polygons:
        if p.material_index in mats and all(i in inband for i in p.vertices):
            for k in p.edge_keys:
                edges.add(tuple(sorted(k)))
    return sorted(edges), per


def finger_rings(blend: str, out: str, half_mm: float, rmax_mm: float, smooth: float) -> int:
    """H1g: new rows around every finger and thumb joint (the H1f critic: ~3 rings over a 90-100 degree bend showed
    as polygons in Godot): each face across a joint cut once along both directions (two new rings across the joint
    and twice the vertices around it), the new vertices rounded onto the surface (bmesh's `smooth`), their weights
    interpolated by bmesh; every old vertex keeps its index, position and weights."""
    import bmesh
    if Path(out).exists():
        raise SystemExit(f"{out} exists: never overwritten")
    bpy.ops.wm.open_mainfile(filepath=blend)
    arm = _arm()
    o = _skin_object(arm)
    me = o.data
    pairs, per = _joint_edges(arm, o, half_mm / 1000.0, rmax_mm / 1000.0)
    old_co = [v.co.copy() for v in me.vertices]
    n0, f0 = len(me.vertices), len(me.polygons)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    edges = [e for e in (bm.edges.get((bm.verts[a], bm.verts[b])) for a, b in pairs) if e is not None]
    bmesh.ops.subdivide_edges(bm, edges=edges, cuts=1, use_grid_fill=True, smooth=smooth)
    bm.verts.index_update()
    dl = bm.verts.layers.deform.active
    wsum = [sum(v[dl].values()) for v in bm.verts[n0:]] if dl else []
    bm.to_mesh(me)
    bm.free()
    me.update()
    moved = max(((me.vertices[i].co - old_co[i]).length for i in range(n0)), default=0.0)
    rep = {"object": o.name, "verts_before": n0, "verts_after": len(me.vertices), "new_verts": len(me.vertices) - n0,
           "faces_before": f0, "faces_after": len(me.polygons), "cut_edges": len(edges), "half_mm": half_mm,
           "rmax_mm": rmax_mm, "smooth": smooth, "band_verts_per_joint": per,
           "old_verts_largest_move_mm": round(moved * 1000, 4),
           "new_weight_sum": [round(min(wsum), 4), round(max(wsum), 4)] if wsum else None}
    print("FINGER_RINGS", json.dumps(rep), flush=True)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    Path(out + ".json").write_text(json.dumps(rep, indent=1))
    return 0


def _snapshot() -> dict:
    arm = _arm()
    names = set(region_bones())
    out = {}
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        gname = {g.index: g.name for g in o.vertex_groups}
        mw = o.matrix_world
        co = [mw @ v.co for v in o.data.vertices]
        w = [{gname.get(g.group, "?"): g.weight for g in v.groups if g.weight > 0} for v in o.data.vertices]
        hand = [any(k in names for k in x) for x in w]
        out[o.name] = {"co": co, "w": w, "hand": hand, "faces": len(o.data.polygons),
                       "keys": len(o.data.shape_keys.key_blocks) if o.data.shape_keys else 0}
    out["_action"] = arm.animation_data.action.name if arm.animation_data and arm.animation_data.action else ""
    out["_actions"] = len(bpy.data.actions)
    return out


def diff(before: str, after: str, out: str) -> int:
    """The whole-body check: per mesh object of `before`, over its vertex indices, the largest move and weight change
    outside the hand region (no weight on a hand region bone in either file) and inside it; new vertices counted."""
    bpy.ops.wm.open_mainfile(filepath=before)
    a = _snapshot()
    bpy.ops.wm.open_mainfile(filepath=after)
    b = _snapshot()
    rep = {"before": before, "after": after, "actions": [a["_actions"], b["_actions"]], "objects": {}}
    for name, x in a.items():
        if name.startswith("_"):
            continue
        y = b.get(name)
        if y is None:
            rep["objects"][name] = "missing"
            continue
        n = len(x["co"])
        out_mv = out_w = in_mv = 0.0
        for i in range(min(n, len(y["co"]))):
            mv = (y["co"][i] - x["co"][i]).length
            if x["hand"][i] or y["hand"][i]:
                in_mv = max(in_mv, mv)
                continue
            out_mv = max(out_mv, mv)
            ks = set(x["w"][i]) | set(y["w"][i])
            out_w = max([out_w] + [abs(x["w"][i].get(k, 0) - y["w"][i].get(k, 0)) for k in ks])
        rep["objects"][name] = {"verts": [n, len(y["co"])], "faces": [x["faces"], y["faces"]],
                                "shape_keys": [x["keys"], y["keys"]], "outside_hand_largest_move_mm":
                                round(out_mv * 1000, 4), "outside_hand_largest_weight_change": round(out_w, 6),
                                "hand_largest_move_mm": round(in_mv * 1000, 2)}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(rep, indent=1))
    print("DIFF", json.dumps(rep))
    return 0


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1:]
    ap = argparse.ArgumentParser(prog="alien_hand_mesh.py")
    ap.add_argument("mode", choices=("dump", "apply", "rings", "finger-rings", "diff"))
    ap.add_argument("--blend", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--moves", default="")
    ap.add_argument("--bend", type=float, default=0.0)
    ap.add_argument("--other", default="", help="diff: the file after (--blend the file before)")
    ap.add_argument("--edges-in", default="", help="rings: the band's edges from another build (by index, else by position)")
    ap.add_argument("--edges-out", default="", help="rings: write the band's edges (index pairs and positions)")
    ap.add_argument("--grid", default="1:8", help="rings: cuts:smoothing-rounds variants, comma separated")
    ap.add_argument("--dump-dir", default="", help="rings: a dump per variant (with --bend)")
    ap.add_argument("--band", default="-0.75,0.62", help="rings: the band from,to in Hand lengths from the wrist")
    ap.add_argument("--spec", default="", help="rings: hand_dims.toml; its [rings] band, cuts and smooth win")
    ap.add_argument("--joint-half-mm", type=float, default=9.0, help="finger-rings: the band each side of a joint")
    ap.add_argument("--joint-rmax-mm", type=float, default=26.0, help="finger-rings: the band's reach from the bone")
    ap.add_argument("--joint-smooth", type=float, default=1.0, help="finger-rings: bmesh's smooth of the new vertices")
    a = ap.parse_args(argv)
    if a.mode == "finger-rings":
        return finger_rings(a.blend, a.out, a.joint_half_mm, a.joint_rmax_mm, a.joint_smooth)
    if a.spec:
        import tomllib
        rg = tomllib.loads(Path(a.spec).read_text())["rings"]
        a.band, a.grid = ",".join(str(x) for x in rg["band"]), f"{rg['cuts']}:{rg['smooth']}"
    if a.mode == "diff":
        return diff(a.blend, a.other, a.out)
    if a.mode == "rings":
        lo, hi = (float(x) for x in a.band.split(","))
        return rings(a.blend, a.out, a.edges_in, a.edges_out, a.grid, a.dump_dir, a.bend, lo, hi)
    if a.mode == "dump":
        return dump(a.blend, a.out, a.bend)
    return apply(a.blend, a.moves, a.out)


if __name__ == "__main__":
    sys.exit(main())
