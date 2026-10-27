"""The Meshy body route (art #196, pilot M1): a skinned alien body from the Meshy surface as it is, beside the cage
route (`alien_cage.py`), which wraps a cage round the skeleton and projects it onto the Meshy form.

    blender -b --factory-startup --python-exit-code 1 --python tools/blender/alien_meshy_body.py -- \
        --targets tools/blender/alien_meshy_targets/axolotl_m1.toml --out <dir> [--raw D:/prime-art-raw] [--hi]

1. Opens the rig body (`rig_body`: its armature, clips and skinned body; H5 v1 for the axolotl) and imports the Meshy
   GLB (`meshy`, T-pose, the sole put on z 0), collapsed to about `decimate_pre` triangles.
2. Smooths the spots (`smooth`: the nipples, the navel, the crotch; a Laplacian in soft spheres and boxes).
3. Moves it onto the skeleton (`alien_meshy_body_geom`): the heights by `wrap_z`; the legs' section centres onto
   their bones (the foot with its ankle); the hands scaled about the wrist (`hand`); the arms' x by `arm_x` and their
   section centres onto the arm bones; the neck narrowed to `ring_half_x` at `ring_z`.
4. Pushes the chest forward (`bust`), smooths its apexes again (`smooth_after`), cuts the head off at `ring_z` (a planar ring, the only open loop) and drops
   the loose bits; without --hi collapses the body to about `body_tris`, the ring's vertices kept.
5. Transfers the rig body's skin weights (nearest face, interpolated), smooths them but the fingers'
   (`weight_smooth`), normalises them (at most 4 per vertex) and replaces the rig body: `Body` under `CharacterArmature`, the rig body's material.
Writes <out>/alien_body.blend (what alien_char_run.py --body takes), <out>/neck_ring.json (the rig body's, copied)
and <out>/body.json (the numbers). --hi: no final collapse (the before of the before/after renders).
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_meshy_body_geom as M  # noqa: E402


def log(msg):
    print(f"M1 {msg}", flush=True)


def tris(me) -> int:
    return sum(len(p.vertices) - 2 for p in me.polygons)


def get_co(me) -> np.ndarray:
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)


def set_co(me, co: np.ndarray):
    me.vertices.foreach_set("co", co.astype(np.float32).ravel())
    me.update()


def select_only(objs, active):
    bpy.ops.object.mode_set(mode="OBJECT") if bpy.context.object and bpy.context.object.mode != "OBJECT" else None
    for o in bpy.context.view_layer.objects:
        o.select_set(o in objs)
    bpy.context.view_layer.objects.active = active


def collapse(obj, ratio: float, group: str = ""):
    mod = obj.modifiers.new("collapse", "DECIMATE")
    # no symmetry: her Meshy pose is not symmetric (the legs 2 to 4 cm apart in y), and a symmetric collapse snaps one
    # side onto the other's mirror (shards on her left calf and foot in the first build)
    mod.decimate_type, mod.ratio = "COLLAPSE", ratio
    if group:
        mod.vertex_group = group
    select_only([obj], obj)
    bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=0)
    bpy.ops.object.modifier_apply(modifier=mod.name)


def laplace(co: np.ndarray, edges: np.ndarray, w: np.ndarray, npv: np.ndarray) -> np.ndarray:
    """A Laplacian of factor 0.5 * w per pass on the vertices with w > 0 (the others are the boundary), each vertex for
    its own pass count npv."""
    passes = int(npv.max()) if len(npv) else 0
    on = w > 0
    e = edges[on[edges[:, 0]] | on[edges[:, 1]]]
    n = len(co)
    deg = np.bincount(e.ravel(), minlength=n).astype(float)
    for k_ in range(passes):
        avg = np.zeros_like(co)
        for k in range(3):
            avg[:, k] = (np.bincount(e[:, 0], co[e[:, 1], k], n) + np.bincount(e[:, 1], co[e[:, 0], k], n))
        avg = np.where(deg[:, None] > 0, avg / np.maximum(deg, 1.0)[:, None], co)
        co = co + (0.5 * w * (npv > k_))[:, None] * (avg - co)
    return co


def smooth_weights(obj, skip, factor: float, repeat: int, zone=None):
    """Each vertex group but those whose name holds one of `skip` blended toward its neighbours' mean (along the
    mesh's edges), `repeat` times; weights under 1e-4 leave the group. zone: [x0, x1, y0, y1, z0, z1] (|x|, the rig
    frame): only the vertices inside move."""
    me = obj.data
    n = len(me.vertices)
    e = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get("vertices", e)
    e = e.reshape(-1, 2)
    W = np.zeros((n, len(obj.vertex_groups)))
    for v in me.vertices:
        for g in v.groups:
            W[v.index, g.group] = g.weight
    cols = [g.index for g in obj.vertex_groups if not any(f in g.name for f in skip)]
    deg = np.maximum(np.bincount(e.ravel(), minlength=n).astype(float), 1.0)
    on = np.ones(n)
    if zone is not None:
        co = get_co(me)
        on = np.array([1.0 if M.soft_box((abs(p[0]), p[1], p[2]), zone, 0.0) > 0 else 0.0 for p in co])
    for _ in range(repeat):
        for c in cols:
            avg = (np.bincount(e[:, 0], W[e[:, 1], c], n) + np.bincount(e[:, 1], W[e[:, 0], c], n)) / deg
            W[:, c] += factor * on * (avg - W[:, c])
    for c in cols:
        vg = obj.vertex_groups[c]
        vg.remove([int(i) for i in np.where(W[:, c] <= 1e-4)[0]])
        for i in np.where(W[:, c] > 1e-4)[0]:
            vg.add([int(i)], float(W[i, c]), "REPLACE")


def slab_mid(co, mask, axis_vals, at, half, cols):
    """Per station `at` the middle of the extents (cols) of the masked vertices within `half` of it along axis_vals."""
    out = []
    for a in at:
        s = co[mask & (np.abs(axis_vals - a) < half)]
        out.append([float((s[:, c].min() + s[:, c].max()) / 2) if len(s) else math.nan for c in cols])
    return np.array(out)


def smooth3(a: np.ndarray) -> np.ndarray:
    b = a.copy()
    b[1:-1] = (a[:-2] + 2 * a[1:-1] + a[2:]) / 4
    return b


def bone_line(arm, names, axis):
    """The bones' heads (and the last one's tail) along `axis` (0 x, 2 z): (positions sorted, xyz)."""
    pts = [arm.data.bones[n].head_local for n in names] + [arm.data.bones[names[-1]].tail_local]
    pts = sorted([tuple(p) for p in pts], key=lambda p: p[axis])
    return np.array([p[axis] for p in pts]), np.array(pts)


def islands(bm) -> list[list]:
    seen, out = set(), []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, isl = [f], []
        seen.add(f.index)
        while stack:
            g = stack.pop()
            isl.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index)
                        stack.append(h)
        out.append(isl)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--raw", default="D:/prime-art-raw")
    ap.add_argument("--hi", action="store_true", help="no final collapse (the before/after's before)")
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    T = M.load(a.targets)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    raw = Path(a.raw)
    rep = {"targets": T["name"], "hi": a.hi}
    rig_path = raw / T["rig_body"]
    bpy.ops.wm.open_mainfile(filepath=str(rig_path))
    arm, rig = bpy.data.objects["CharacterArmature"], bpy.data.objects["Body"]
    rig.name = "RigBody"
    mat = rig.data.materials[0] if rig.data.materials else None
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(raw / T["meshy"]))
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    select_only(meshes, meshes[0])
    if len(meshes) > 1:
        bpy.ops.object.join()
    mb = bpy.context.view_layer.objects.active
    mb.parent = None
    for o in new:
        if o is not mb:
            bpy.data.objects.remove(o)
    select_only([mb], mb)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    me = mb.data
    co = get_co(me)
    co[:, 2] -= co[:, 2].min()
    set_co(me, co)
    me.materials.clear()
    while len(me.uv_layers) > 1:
        me.uv_layers.remove(me.uv_layers[-1])
    for ca in list(me.color_attributes):
        me.color_attributes.remove(ca)
    rep["meshy_tris"] = tris(me)
    collapse(mb, M.pre_ratio(rep["meshy_tris"], T["decimate_pre"]))
    me = mb.data
    rep["pre_tris"] = tris(me)
    log(f"imported {rep['meshy_tris']} -> {rep['pre_tris']} tris")

    # 2. the spots smoothed (Meshy frame)
    co = get_co(me)
    edges = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get("vertices", edges)
    edges = edges.reshape(-1, 2)
    sm = T["smooth"]
    w, npv = np.zeros(len(co)), np.zeros(len(co), dtype=int)
    spots = [([M.soft_sphere(p, (x, y, z), r) for p in co], n) for x, y, z, r, n in sm["spheres"]]
    spots += [([M.soft_box(p, b[:6], sm["margin"]) for p in co], b[6]) for b in sm["boxes"]]
    for ws, n in spots:
        ws = np.array(ws)
        npv = np.where(ws > 0, np.maximum(npv, n), npv)
        w = np.maximum(w, ws)
    passes = int(npv.max())
    co2 = laplace(co, edges, w, npv)
    mv = np.linalg.norm(co2 - co, axis=1)
    rep['smoothed_by_spot_mm'] = [round(float(mv[[M.soft_sphere(p, s_[:3], s_[3]) > 0 for p in co]].max()) * 1000, 1) for s_ in sm['spheres']] + [round(float(mv[[M.soft_box(p, b_[:6], sm['margin']) > 0 for p in co]].max()) * 1000, 1) for b_ in sm['boxes']]
    rep["smoothed"] = {"vertices": int((w > 0).sum()), "passes": passes,
                       "max_move_mm": round(float(np.linalg.norm(co2 - co, axis=1).max()) * 1000, 1)}
    co = co2
    log(f"smoothed {rep['smoothed']}")

    # 3. onto the skeleton
    wz = T["wrap_z"]
    ax = np.abs(co[:, 0])
    side = np.where(co[:, 0] >= 0, 1.0, -1.0)
    zr = np.array([M.z_to_rig(wz, z) for z in co[:, 2]])
    new_co = co.copy()
    new_co[:, 2] = zr
    # legs
    legs = {}
    zs = np.arange(T["leg_station_z"][0], T["leg_station_z"][1] + 1e-9, 0.02)
    for s, pre in ((1.0, "Left"), (-1.0, "Right")):
        mask = (co[:, 0] * s > 0.01) & (co[:, 2] < T["leg_fade_z"][1] + 0.02)
        mid = slab_mid(co, mask, co[:, 2], zs, 0.006, (0, 1))
        bz, bp = bone_line(arm, [f"{pre}UpperLeg", f"{pre}LowerLeg"], 2)
        zsr = np.array([M.z_to_rig(wz, z) for z in zs])
        tx, ty = np.interp(zsr, bz, bp[:, 0]), np.interp(zsr, bz, bp[:, 1])
        d = smooth3(np.stack([tx - mid[:, 0], ty - mid[:, 1]], 1))
        legs[pre] = {"z": [round(float(z), 2) for z in zs[::5]], "dx_mm": [round(float(v) * 1000) for v in d[::5, 0]],
                     "dy_mm": [round(float(v) * 1000) for v in d[::5, 1]]}
        sel = (side == s) & (co[:, 2] < T["leg_fade_z"][1])
        zq = np.maximum(co[sel, 2], T["foot_z"])
        wl = np.array([1.0 - M.sstep(T["leg_fade_z"][0], T["leg_fade_z"][1], z) for z in co[sel, 2]])
        new_co[sel, 0] += wl * np.interp(zq, zs, d[:, 0])
        new_co[sel, 1] += wl * np.interp(zq, zs, d[:, 1])
    rep["legs"] = legs
    # hands (Meshy frame, about each wrist's centre), then the arms
    hd = T["hand"]
    arms = {}
    xs = np.arange(T["arm_station_x"][0], T["arm_station_x"][1] + 1e-9, 0.02)
    am = T["arm_x"] + [[T["arm_x"][-1][0] + 1.0, T["arm_x"][-1][1] + 1.0]]
    for s, pre in ((1.0, "Left"), (-1.0, "Right")):
        mask = (side == s) & (co[:, 2] > 1.2) & (co[:, 2] < 1.45)  # under the gills
        wc = slab_mid(co, mask, ax, [hd["wrist"]], 0.006, (1, 2))[0]
        sel = np.where(mask & (ax > hd["wrist"]))[0]
        hco = co.copy()
        for i in sel:
            f = M.hand_factor(ax[i], hd["wrist"], hd["scale"], hd["blend"])
            hco[i, 0] = s * M.hand_x(ax[i], hd["wrist"], hd["scale"], hd["blend"])
            hco[i, 1] = wc[0] + (co[i, 1] - wc[0]) * f
            hco[i, 2] = wc[1] + (co[i, 2] - wc[1]) * f
        hz_r = np.array([M.z_to_rig(wz, z) for z in hco[sel, 2]])
        mid = slab_mid(co, mask, ax, xs, 0.006, (1, 2))
        bx, bp = bone_line(arm, [f"{pre}UpperArm", f"{pre}LowerArm", f"{pre}Hand"], 0)
        bxa = np.abs(bx)
        o_ = np.argsort(bxa)
        xr = np.array([M.interp([p[0] for p in am], [p[1] for p in am], x) for x in xs])
        ty, tz = np.interp(xr, bxa[o_], bp[o_, 1]), np.interp(xr, bxa[o_], bp[o_, 2])
        d = smooth3(np.stack([ty - mid[:, 0], tz - np.array([M.z_to_rig(wz, z) for z in mid[:, 1]])], 1))
        arms[pre] = {"x": [round(float(x), 2) for x in xs[::4]], "dy_mm": [round(float(v) * 1000) for v in d[::4, 0]],
                     "dz_mm": [round(float(v) * 1000) for v in d[::4, 1]], "wrist_centre": [round(float(v), 4) for v in wc]}
        allsel = np.where(side == s)[0]
        for i in allsel:
            x = ax[i]
            if x <= T["arm_blend_x"][0] or co[i, 2] <= T["arm_band_z"][0]:  # the legs and the trunk's side stay
                continue
            wx = M.sstep(T["arm_blend_x"][0], T["arm_blend_x"][1], x)
            wzb = M.sstep(T["arm_band_z"][0], T["arm_band_z"][1], co[i, 2])
            wa = wx * max(wzb, wx)
            if wa <= 0.0:
                continue
            hx, hz = (abs(hco[i, 0]), hz_r[np.searchsorted(sel, i)]) if (x > hd["wrist"] and co[i, 2] > 1.2) else (x, zr[i])
            hy = hco[i, 1]
            xq = min(max(x, xs[0]), xs[-1])
            new_co[i, 0] = s * (x + wa * (M.interp([p[0] for p in am], [p[1] for p in am], hx) - x))
            new_co[i, 1] = co[i, 1] + wa * (hy - co[i, 1] + np.interp(xq, xs, d[:, 0]))
            new_co[i, 2] = zr[i] + wa * (hz - zr[i] + np.interp(xq, xs, d[:, 1]))
    rep["arms"] = arms
    # the neck narrowed onto the ring's half-width
    rz = T["ring_z"]
    sl = new_co[(np.abs(new_co[:, 2] - rz) < 0.004) & (np.abs(new_co[:, 0]) < 0.15)]
    hx0 = float(np.ptp(sl[:, 0]) / 2)
    c = (sl[:, :2].min(0) + sl[:, :2].max(0)) / 2
    k = T["ring_half_x"] / hx0
    nsel = (new_co[:, 2] > T["neck_scale_from_z"]) & (np.hypot(new_co[:, 0] - c[0], new_co[:, 1] - c[1]) < 0.15)
    for i in np.where(nsel)[0]:
        f = M.neck_factor(new_co[i, 2], T["neck_scale_from_z"], rz, k) if new_co[i, 2] < rz else k
        new_co[i, :2] = c + (new_co[i, :2] - c) * f
    rep["neck"] = {"half_x_before": round(hx0, 4), "scale": round(k, 4), "centre": [round(float(v), 4) for v in c]}
    set_co(me, new_co)
    log(f"mapped: legs {legs} arms {arms} neck {rep['neck']}")

    # 4. the chest, the cut, the loose bits
    me.update()
    nrm = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("normal", nrm)
    nrm = nrm.reshape(-1, 3)
    co = get_co(me)
    b = T["bust"]
    push = np.array([M.bust_push(p, n, b["centre"], b["push"], b["radius"]) for p, n in zip(co, nrm)])
    co[:, 1] -= push
    set_co(me, co)
    rep["bust"] = {"moved": int((push > 0).sum()), "max_mm": round(float(push.max()) * 1000, 1)}
    # the chest's apexes smoothed again after the push (rig frame): the push's peak sits on them and points them
    sa = T["smooth_after"]
    ws = [np.array([M.soft_sphere(p, sp[:3], sp[3]) for p in co]) for sp in sa["spheres"]]
    w = np.max(ws, 0)
    npv = np.max([np.where(wi > 0, sp[4], 0) for wi, sp in zip(ws, sa["spheres"])], 0)
    co2 = laplace(co, edges, w, npv)
    rep["smoothed_after_mm"] = round(float(np.linalg.norm(co2 - co, axis=1).max()) * 1000, 1)
    co = co2
    set_co(me, co)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, rz), plane_no=(0, 0, 1),
                           clear_outer=True, dist=1e-5)
    bm.faces.ensure_lookup_table()
    isl = sorted(islands(bm), key=len, reverse=True)
    drop = [f for i in isl[1:] for f in i]
    rep["loose_dropped_faces"] = len(drop)
    bmesh.ops.delete(bm, geom=drop, context="FACES")
    loose_v = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose_v, context="VERTS")
    bm.to_mesh(me)
    bm.free()
    me.update()
    rep["cut_tris"] = tris(me)
    if not a.hi:
        bm = bmesh.new()
        bm.from_mesh(me)
        ring = {v.index for e in bm.edges if e.is_boundary for v in e.verts}
        bm.free()
        vg = mb.vertex_groups.new(name="_dec")
        vg.add([i for i in range(len(me.vertices)) if i not in ring], 1.0, "REPLACE")
        collapse(mb, M.body_ratio(rep["cut_tris"], T["body_tris"]), vg.name)
        mb.vertex_groups.remove(mb.vertex_groups["_dec"])
        me = mb.data
    for p in me.polygons:
        p.use_smooth = True
    if me.has_custom_normals:
        select_only([mb], mb)
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    # the checks: open loops, non-manifold edges, parts
    bm = bmesh.new()
    bm.from_mesh(me)
    bnd = [e for e in bm.edges if e.is_boundary]
    zs_b = [v.co.z for e in bnd for v in e.verts]
    rep["body"] = {"tris": tris(me), "vertices": len(me.vertices),
                   "open_edges": len(bnd), "open_edges_below_ring": sum(1 for e in bnd if min(v.co.z for v in e.verts) < rz - 0.002),
                   "non_manifold": sum(1 for e in bm.edges if len(e.link_faces) > 2),
                   "parts": len(islands(bm)), "ring_z": [round(min(zs_b), 4), round(max(zs_b), 4)] if zs_b else None}
    bm.verts.ensure_lookup_table()
    ring_v = {v.index for e in bnd for v in e.verts}
    rco = np.array([bm.verts[i].co[:] for i in sorted(ring_v)]) if ring_v else np.zeros((0, 3))
    bm.free()
    if len(rco):
        rep["ring"] = {"vertices": len(rco), "half_x": round(float(np.ptp(rco[:, 0]) / 2), 4),
                       "half_y": round(float(np.ptp(rco[:, 1]) / 2), 4),
                       "centre": [round(float(v), 4) for v in (rco[:, :2].min(0) + rco[:, :2].max(0)) / 2]}
    log(f"body {rep['body']} ring {rep.get('ring')} bust {rep['bust']}")

    # 5. the weights from the rig body
    arm.data.pose_position = "REST"
    bpy.context.view_layer.update()
    select_only([mb, rig], rig)
    bpy.ops.object.data_transfer(use_reverse_transfer=False, data_type="VGROUP_WEIGHTS",
                                 vert_mapping="POLYINTERP_NEAREST", layers_select_src="ALL", layers_select_dst="NAME",
                                 use_create=True)
    select_only([mb], mb)
    bpy.ops.object.vertex_group_clean(group_select_mode="ALL", limit=0.01)
    bpy.ops.object.vertex_group_limit_total(group_select_mode="ALL", limit=4)
    bpy.ops.object.vertex_group_normalize_all(lock_active=False)
    # the joints' weights smoothed (not the fingers': each finger bends alone), then normalised again
    ws_ = T["weight_smooth"]
    fingers = ("Thumb", "Index", "Middle", "Ring", "Little")
    smooth_weights(mb, fingers, ws_["factor"], ws_["repeat"])
    for z in ws_["zones"]:  # the joints that still pinched (the knees, the hips' front, the shoulders)
        smooth_weights(mb, fingers, ws_["factor"], z[6], z[:6])
    bpy.ops.object.vertex_group_limit_total(group_select_mode="ALL", limit=4)
    bpy.ops.object.vertex_group_normalize_all(lock_active=False)
    unw = sum(1 for v in mb.data.vertices if not v.groups)
    rep["weights"] = {"groups": len(mb.vertex_groups), "unweighted": unw}
    # the hands against their finger bones (rig frame): the fingertips' bones and the hand's y extent there
    co = get_co(mb.data)
    fing = {}
    for f in ("Thumb", "Index", "Middle", "Ring", "Little"):
        bn = arm.data.bones.get(f"Left{f}Distal")
        if bn:
            fing[f] = [round(v, 3) for v in bn.tail_local]
    hand = co[co[:, 0] > arm.data.bones["LeftHand"].head_local.x]
    rep["hand"] = {"finger_tips": fing, "mesh_x_max": round(float(hand[:, 0].max()), 3) if len(hand) else None,
                   "mesh_y": [round(float(hand[:, 1].min()), 3), round(float(hand[:, 1].max()), 3)] if len(hand) else None,
                   "mesh_z": [round(float(hand[:, 2].min()), 3), round(float(hand[:, 2].max()), 3)] if len(hand) else None,
                   "kept": "meshy" if T["keep_hands"] else "none"}
    log(f"weights {rep['weights']} hand {rep['hand']}")
    bpy.data.objects.remove(rig)
    mb.name = mb.data.name = "Body"
    if mat:
        mb.data.materials.append(mat)
    mb.parent = arm
    mod = mb.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    arm.data.pose_position = "POSE"
    if mb.data.uv_layers:
        mb.data.uv_layers[0].name = "UVMap"
    else:
        mb.data.uv_layers.new(name="UVMap")
    ring_json = rig_path.parent / "neck_ring.json"
    if ring_json.exists():
        shutil.copyfile(ring_json, out / "neck_ring.json")
    (out / "body.json").write_text(json.dumps(rep, indent=1), encoding="utf-8", newline="\n")
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "alien_body.blend"))
    log(f"saved {out / 'alien_body.blend'}")


if __name__ == "__main__":
    main()
