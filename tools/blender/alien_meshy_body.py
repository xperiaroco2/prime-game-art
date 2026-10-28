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

M1b (art #196), each only when its key is in the target file (`axolotl_m1b.toml`; M1's file has none), after step 5:
6. `degenerate`: the ring's near-coincident vertices merged and the slivers dissolved (the weld's bridge took their
   wrong normals: the small grey triangles on the seam).
7. `arm_thicken`: the arms scaled about their section centres (front width by the profile, the depth by its power).
8. `smooth_rest`: spots smoothed in the rest pose (the knees' inner notch), mirrored.
9. `fingers`: the finger bones moved onto Meshy's own fingers (each free finger found by cuts swept down the hand,
   its straight centre line, the joints by the old proportions and the thinnest slice near them, the rolls kept)
   and the hand weighted afresh: a finger's vertices by its own chain only, the palm by the chains' lines.
10. `bends`: the joints' weights replaced by rings across each joint (the child's share a smoothstep along the
   child bone), faded out at the band's ends and the limb's radius.
M1c (art #196, `axolotl_m1c.toml`: M1b's keys and these; M1's and M1b's files have none):
8b. `notch`: the knee's inner notch found by its concavity in a box (each side) and smoothed about it.
9b. `fingers.thumb_falloff`: the palm's share for the thumb by its distance from the thumb's line alone (a soft
   thenar into the palm); `fingers.base_band` / `base_smooth`: the free fingers' vertices near their web smoothed with
   the palm (the ring's strip and the middle's gap at their bases).
M2b (art #196, `chameleon_m2b.toml`; the older files have none):
2b. `smooth.mu`: Taubin's step back after each pass (the volume kept).
7b. `seat`: the seat's depth behind the line from the thigh's back to the small of the back scaled down.
8c. `smooth_rest.boxes` (with `margin`, `mu`): soft boxes on both sides, the open ring held (the weld unchanged).
9c. `fingers.shape`: the free fingers slimmer and their tips smaller about their slices' centres, the thumb shorter
   (its centre line scaled about its web), before the bones are placed on them.
M1d (art #196, `axolotl_m1d.toml`; the older files have none):
8d. `bust_round`: each breast's tip (its most pointed vertex) rounded by a heightfield blur, the volume kept.
7c. `arm_thicken.widths`: the arms toward target front widths; 9d. `fingers.shape.thumb_thick`: the thumb thicker.
--from-body <alien_body.blend>: steps 6 to 10 only, on a body this script built before (M1's).
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
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_meshy_body_geom as M  # noqa: E402
import alien_meshy_fix_geom as F  # noqa: E402


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


def laplace(co: np.ndarray, edges: np.ndarray, w: np.ndarray, npv: np.ndarray, mu: float = 0.0) -> np.ndarray:
    """A Laplacian of factor 0.5 * w per pass on the vertices with w > 0 (the others are the boundary), each vertex for
    its own pass count npv. M2b: mu < 0 adds Taubin's step back after each pass (factor mu * w): the volume kept;
    mu a number or one per vertex."""
    passes = int(npv.max()) if len(npv) else 0
    on = w > 0
    e = edges[on[edges[:, 0]] | on[edges[:, 1]]]
    n = len(co)
    deg = np.bincount(e.ravel(), minlength=n).astype(float)
    def mean(c_):
        avg = np.zeros_like(c_)
        for k in range(3):
            avg[:, k] = (np.bincount(e[:, 0], c_[e[:, 1], k], n) + np.bincount(e[:, 1], c_[e[:, 0], k], n))
        return np.where(deg[:, None] > 0, avg / np.maximum(deg, 1.0)[:, None], c_)
    mu_v = np.broadcast_to(np.asarray(mu, dtype=float), (n,))[:, None]
    for k_ in range(passes):
        on_k = (npv > k_)[:, None]
        co = co + 0.5 * w[:, None] * on_k * (mean(co) - co)
        if np.any(mu_v):
            co = co + mu_v * w[:, None] * on_k * (mean(co) - co)
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


# M1b (art #196): the fixes, each only when its key is in the target file
def read_weights(obj) -> tuple[np.ndarray, list[str]]:
    names = [g.name for g in obj.vertex_groups]
    W = np.zeros((len(obj.data.vertices), len(names)))
    for v in obj.data.vertices:
        for g in v.groups:
            W[v.index, g.group] = g.weight
    return W, names


def write_weights(obj, W: np.ndarray, limit: int = 4):
    """W (vertices x groups) into the groups: each vertex's `limit` largest, normalised, weights under 1e-4 out."""
    keep = np.argsort(-W, axis=1)[:, :limit]
    W2 = np.zeros_like(W)
    rows = np.arange(len(W))[:, None]
    W2[rows, keep] = W[rows, keep]
    W2[W2 < 1e-4] = 0.0
    W2 /= np.maximum(W2.sum(1, keepdims=True), 1e-12)
    for c, vg in enumerate(obj.vertex_groups):
        vg.remove(list(range(len(W))))
        for i in np.where(W2[:, c] > 0)[0]:
            vg.add([int(i)], float(W2[i, c]), "REPLACE")


def edge_array(me) -> np.ndarray:
    e = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get("vertices", e)
    return e.reshape(-1, 2)


def slivers(bm, area=1e-7) -> int:
    return sum(1 for f in bm.faces if f.calc_area() < area)


def fix_degenerate(mb, cfg, rep):
    """The ring's vertices closer than ring_merge merged, then every edge under dist collapsed (bmesh)."""
    bm = bmesh.new()
    bm.from_mesh(mb.data)
    ring = [v for v in bm.verts if any(e.is_boundary for e in v.link_edges)]
    re_ = [e for e in bm.edges if e.is_boundary]
    r0 = {"slivers": slivers(bm), "ring_vertices": len(ring),
          "ring_edge_min_mm": round(min(e.calc_length() for e in re_) * 1000, 3)}
    bmesh.ops.remove_doubles(bm, verts=ring, dist=cfg["ring_merge"])
    bmesh.ops.dissolve_degenerate(bm, dist=cfg["dist"], edges=bm.edges[:])
    re_ = [e for e in bm.edges if e.is_boundary]
    r1 = {"slivers": slivers(bm), "ring_vertices": len({v for e in re_ for v in e.verts}),
          "ring_edge_min_mm": round(min(e.calc_length() for e in re_) * 1000, 3), "open_edges": len(re_),
          "non_manifold": sum(1 for e in bm.edges if len(e.link_faces) > 2)}
    bm.to_mesh(mb.data)
    bm.free()
    mb.data.update()
    rep["degenerate"] = {"before": r0, "after": r1}
    log(f"degenerate {rep['degenerate']}")


def fix_arms(arm, mb, cfg, rep):
    """Each arm's vertices (|x| past from_x, above band_z) scaled about the arm's section centre at their |x|: z
    (the front view's width in the A pose) by the profile, y by the profile to `y_power`."""
    co = get_co(mb.data)
    out = {}
    for s, pre in ((1.0, "Left"), (-1.0, "Right")):
        sel = (co[:, 0] * s > cfg["from_x"]) & (co[:, 2] > cfg["band_z"])
        hx = abs(arm.data.bones[f"{pre}Hand"].head_local.x)
        xs = np.arange(cfg["from_x"], hx + 1e-9, 0.01)
        mid = smooth3(smooth3(slab_mid(co, sel, np.abs(co[:, 0]), xs, cfg["slab"], (1, 2))))

        def ext(c_):
            return [float(np.ptp(c_[sel & (np.abs(np.abs(c_[:, 0]) - x) < cfg["slab"]), 2])) for x in xs[::4]]
        before = ext(co)
        meas = None
        if "widths" in cfg:  # M1d: toward target front widths (mm) over their range, measured per 1 cm
            meas = smooth3(np.array([float(np.ptp(co[sel & (np.abs(np.abs(co[:, 0]) - x) < cfg["slab"]), 2]))
                                     if (sel & (np.abs(np.abs(co[:, 0]) - x) < cfg["slab"])).any() else 0.0
                                     for x in xs]))
            tgt = [[w[0], w[1] / 1000.0] for w in cfg["widths"]]
        for i in np.where(sel)[0]:
            x = abs(co[i, 0])
            k = F.profile(cfg["profile"], x)
            if meas is not None:
                kw = F.width_factor(x, list(xs), list(meas), tgt, *cfg.get("width_clamp", [1.0, 2.0]))
                k = k if kw is None else kw
            if k == 1.0:
                continue
            cy, cz = np.interp(x, xs, mid[:, 0]), np.interp(x, xs, mid[:, 1])
            co[i, 1] = cy + (co[i, 1] - cy) * k ** cfg["y_power"]
            co[i, 2] = cz + (co[i, 2] - cz) * k
        out[pre] = {"x": [round(float(x), 2) for x in xs[::4]], "z_mm_before": [round(v * 1000) for v in before],
                    "z_mm_after": [round(v * 1000) for v in ext(co)]}
    set_co(mb.data, co)
    waist = co[(np.abs(co[:, 2] - cfg["waist_z"]) < 0.004) & (np.abs(co[:, 0]) < 0.25)]
    out["waist_m"] = round(float(np.ptp(waist[:, 0])), 4)
    rep["arm_thicken"] = out
    log(f"arms {out}")


def fix_smooth_rest(mb, cfg, rep):
    """Soft spheres [|x|, y, z, r, passes] smoothed on both sides (a Laplacian, the rest pose)."""
    co = get_co(mb.data)
    w, npv = np.zeros(len(co)), np.zeros(len(co), dtype=int)
    for x, y, z, r, n in cfg["spheres"]:
        for sx in (x, -x):
            ws = np.array([M.soft_sphere(p, (sx, y, z), r) for p in co])
            npv = np.where(ws > 0, np.maximum(npv, n), npv)
            w = np.maximum(w, ws)
    # M2b: soft boxes [|x|0, |x|1, y0, y1, z0, z1, passes(, mu)] (both sides, margin m), the open ring held (the
    # weld's ring and so his head's scale unchanged), Taubin's mu (a box's own eighth value wins: 0 a plain Laplacian)
    ax = np.abs(co)
    ax[:, 1:] = co[:, 1:]
    mu = np.full(len(co), float(cfg.get("mu", 0.0)))
    for b in cfg.get("boxes", []):
        ws = np.array([M.soft_box(p, b[:6], cfg.get("margin", 0.02)) for p in ax])
        npv = np.where(ws > 0, np.maximum(npv, b[6]), npv)
        w = np.maximum(w, ws)
        if len(b) > 7:
            mu = np.where(ws > 0, b[7], mu)
    if "boxes" in cfg:  # (M1b's spheres-only files: as they were built)
        bm = bmesh.new()
        bm.from_mesh(mb.data)
        ring = [v.index for v in bm.verts if any(e.is_boundary for e in v.link_edges)]
        bm.free()
        w[ring] = 0.0
    co2 = laplace(co, edge_array(mb.data), w, npv, mu)
    rep["smooth_rest_mm"] = round(float(np.linalg.norm(co2 - co, axis=1).max()) * 1000, 2)
    rep["smooth_rest_vertices"] = int((w > 0).sum())
    set_co(mb.data, co2)


def fix_seat(mb, cfg, rep):
    """M2b: the seat's depth behind its base line scaled (rest pose): the base line runs from the back's furthest y at
    z[0] (the thigh under the seat) to that at z[1] (the small of the back), over |x| < x (the back's outermost
    within it); each vertex behind it moved by F.seat_y, weighted by smoothsteps in z (fade_z) and |x| (fade_x)."""
    co = get_co(mb.data)
    z0, z1 = cfg["z"]

    def back(z):
        s_ = co[(np.abs(co[:, 2] - z) < 0.005) & (np.abs(co[:, 0]) > 0.02) & (np.abs(co[:, 0]) < cfg["x"])]
        return float(s_[:, 1].max())
    y0, y1 = back(z0), back(z1)
    before = max(back(z) - (y0 + (y1 - y0) * (z - z0) / (z1 - z0)) for z in np.arange(z0, z1, 0.01))
    n_ = 0
    for i in range(len(co)):
        x, y, z = abs(co[i, 0]), co[i, 1], co[i, 2]
        if not (z0 < z < z1 and x < cfg["x"] and y > 0):
            continue
        w = (F.sstep(z0, z0 + cfg["fade_z"], z) * (1.0 - F.sstep(z1 - cfg["fade_z"], z1, z))
             * (1.0 - F.sstep(cfg["x"] - cfg["fade_x"], cfg["x"], x)))
        y2 = F.seat_y(y, y0 + (y1 - y0) * (z - z0) / (z1 - z0), w, cfg["depth"], cfg["ramp"])
        n_ += y2 != y
        co[i, 1] = y2
    set_co(mb.data, co)
    after = max(back(z) - (y0 + (y1 - y0) * (z - z0) / (z1 - z0)) for z in np.arange(z0, z1, 0.01))
    rep["seat"] = {"base_y": [round(y0, 4), round(y1, 4)], "depth_mm_before": round(before * 1000, 1),
                   "depth_mm_after": round(after * 1000, 1), "vertices": int(n_)}
    log(f"seat {rep['seat']}")


def fix_bust_round(mb, cfg, rep):
    """M1d: each breast's tip rounded (rest pose): the apex, the most forward vertex (least y) in the box
    [|x|0, |x|1, z0, z1] (pick "point": the front-facing vertex standing out most from its neighbours; `at`: the
    vertex nearest the given point per side); its direction n, the mean normal within r of it; the front-facing vertices (normal . n over
    `front`) within `blend` (m) of the apex as heights along n over the plane across n, blurred by a Gaussian of
    `sigma` (F.height_smooth: the volume kept), the blur's share 1 within r and down to 0 at `blend` by a smoothstep,
    and faded in over 0.2 of the facing; then lifted by the blend's shares so the volume stays (F.keep_volume). Reports each tip's radius of curvature (F.tip_radius within r) before and
    after, the apex's move and the volume's change."""
    me = mb.data
    co = get_co(me)
    nrm = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("normal", nrm)
    nrm = nrm.reshape(-1, 3)
    area = np.zeros(len(co))
    for p in me.polygons:
        for v in p.vertices:
            area[v] += p.area / len(p.vertices)
    out = {}
    x0, x1, z0, z1 = cfg["box"]
    E = edge_array(me)
    deg = np.maximum(np.bincount(E.ravel(), minlength=len(co)), 1).astype(float)
    nb = np.zeros_like(co)
    np.add.at(nb, E[:, 0], co[E[:, 1]])
    np.add.at(nb, E[:, 1], co[E[:, 0]])
    bulge = ((co - nb / deg[:, None]) * nrm).sum(1)  # > 0: the vertex stands out of its neighbours (a point)
    for _ in range(2):
        avg = np.zeros(len(co))
        np.add.at(avg, E[:, 0], bulge[E[:, 1]])
        np.add.at(avg, E[:, 1], bulge[E[:, 0]])
        bulge = 0.5 * bulge + 0.5 * avg / deg
    for s, side in ((1.0, "Left"), (-1.0, "Right")):
        inb = np.where((co[:, 0] * s > x0) & (co[:, 0] * s < x1) & (co[:, 2] > z0) & (co[:, 2] < z1)
                       & (nrm[:, 1] < -0.5))[0]
        # the apex: the most forward vertex, or (pick "point") the most pointed, the read nipple's spot
        if "at" in cfg:  # the read point given, [x, y, z] per side (left first): its nearest vertex in the box
            a = int(inb[np.argmin(np.linalg.norm(co[inb] - np.array(cfg["at"][0 if s > 0 else 1]), axis=1))])
        else:
            a = int(inb[np.argmax(bulge[inb])] if cfg.get("pick") == "point" else inb[np.argmin(co[inb, 1])])
        A = co[a].copy()
        near = np.linalg.norm(co - A, axis=1) < cfg["r"]
        n = nrm[near].mean(0)
        n /= np.linalg.norm(n)
        u = np.cross(n, [0.0, 0.0, 1.0])
        u /= np.linalg.norm(u)
        v = np.cross(n, u)
        rel = co - A
        h = rel @ n
        uv = np.stack([rel @ u, rel @ v], 1)
        rr = np.linalg.norm(uv, axis=1)
        face = nrm @ n
        idx = np.where((np.linalg.norm(rel, axis=1) < cfg["blend"] + 3 * cfg["sigma"]) & (face > cfg["front"]))[0]
        hs = np.array(F.height_smooth(uv[idx].tolist(), h[idx].tolist(), area[idx].tolist(), cfg["sigma"]))
        w = np.array([(1.0 - F.sstep(cfg["r"], cfg["blend"], float(rr[i]))) * F.sstep(cfg["front"], cfg["front"] + 0.2,
                                                                                       float(face[i])) for i in idx])
        dh = np.array(F.keep_volume((w * (hs - h[idx])).tolist(), w.tolist(), area[idx].tolist()))
        rho0 = F.tip_radius(rr[idx].tolist(), h[idx].tolist(), cfg["r"])
        co[idx] += dh[:, None] * n
        h2 = h[idx] + dh
        top = int(idx[np.argmax(h2)])
        rho1 = F.tip_radius(np.linalg.norm(uv[idx] - uv[top], axis=1).tolist(), (h2 - h2.max()).tolist(), cfg["r"])
        out[side] = {"apex": [round(float(c), 4) for c in A], "n": [round(float(c), 3) for c in n],
                     "vertices": int((w > 0).sum()), "radius_mm_before": round(rho0 * 1000, 1),
                     "radius_mm_after": round(rho1 * 1000, 1), "apex_move_mm": round(float(-dh[idx == a].sum()) * 1000
                                                                                    if (idx == a).any() else 0.0, 2),
                     "volume_change_cm3": round(float((area[idx] * dh).sum()) * 1e6, 2),
                     "max_move_mm": round(float(np.abs(dh).max()) * 1000, 2)}
    set_co(me, co)
    me.update()
    rep["bust_round"] = out
    log(f"bust_round {out}")


def fix_notch(mb, cfg, rep):
    """M1c: the knee's notch found where it is (the most concave vertex in the box, each side: its offset from its
    neighbours' mean along its normal, smoothed depth_smooth times; only vertices whose normal faces the midline by at
    least `medial`) and smoothed in a soft sphere about it (box [|x|0, |x|1, y0, y1, z0, z1], r, passes; rest
    pose)."""
    co = get_co(mb.data)
    E = edge_array(mb.data)
    nb = np.zeros_like(co)
    deg = np.bincount(E.ravel(), minlength=len(co)).astype(float)
    np.add.at(nb, E[:, 0], co[E[:, 1]])
    np.add.at(nb, E[:, 1], co[E[:, 0]])
    nb /= np.maximum(deg, 1)[:, None]
    nrm = np.array([v.normal for v in mb.data.vertices])
    depth = ((nb - co) * nrm).sum(1)  # > 0: the vertex lies inward of its neighbours (a dent)
    for _ in range(cfg.get("depth_smooth", 2)):  # one decimated vertex is noise: the dent's mean over its ring
        avg = np.zeros(len(co))
        np.add.at(avg, E[:, 0], depth[E[:, 1]])
        np.add.at(avg, E[:, 1], depth[E[:, 0]])
        depth = 0.5 * depth + 0.5 * avg / np.maximum(deg, 1)
    x0, x1, y0, y1, z0, z1 = cfg["box"]
    w, npv, found = np.zeros(len(co)), np.zeros(len(co), dtype=int), []
    for s in (1.0, -1.0):
        inb = np.where((co[:, 0] * s >= x0) & (co[:, 0] * s <= x1) & (co[:, 1] >= y0) & (co[:, 1] <= y1)
                       & (co[:, 2] >= z0) & (co[:, 2] <= z1) & (nrm[:, 0] * s <= -cfg.get("medial", 0.0)))[0]
        c = np.array(F.notch_pick([(float(depth[i]), tuple(co[i])) for i in inb]))
        found.append([round(float(v), 4) for v in c] + [round(float(depth[inb].max()) * 1000, 2)])
        ws = np.array([M.soft_sphere(p, c, cfg["r"]) for p in co])
        npv = np.where(ws > 0, np.maximum(npv, cfg["passes"]), npv)
        w = np.maximum(w, ws)
    co2 = laplace(co, E, w, npv)
    rep["notch"] = {"found_xyz_depth_mm": found, "moved_mm": round(float(np.linalg.norm(co2 - co, axis=1).max()) * 1000, 2)}
    set_co(mb.data, co2)
    log(f"notch {rep['notch']}")


def finger_slices(pts, seg, c, d, step):
    """Cross-sections of a finger across its line (c, d) every `step`: the points where its edges (seg: [k, 2, 3],
    the finger's own edges) cross each plane; [(s, centre xyz, thickness along the palm normal)]. The decimated mesh's
    vertices alone are too sparse for a 2 mm slab."""
    e2 = np.array([0.0, 0.0, 1.0]) - d * d[2]
    e2 /= np.linalg.norm(e2)
    e1 = np.cross(d, e2)
    s = (pts - c) @ d
    sa, sb = (seg[:, 0] - c) @ d, (seg[:, 1] - c) @ d
    out = []
    for s0 in np.arange(s.min() + step / 2, s.max(), step):
        x = (sa - s0) * (sb - s0) < 0
        t = ((s0 - sa[x]) / (sb[x] - sa[x]))[:, None]
        q = seg[x, 0] + t * (seg[x, 1] - seg[x, 0])
        if len(q) < 3:
            continue
        a, b = (q - c) @ e1, (q - c) @ e2
        out.append((float(s0), c + s0 * d + e1 * (a.min() + a.max()) / 2 + e2 * (b.min() + b.max()) / 2,
                    float(np.ptp(b))))
    return out


def fix_fingers(arm, mb, cfg, rep, W, names):
    """The finger bones onto Meshy's fingers and the hands weighted afresh (the module's step 9)."""
    co = get_co(mb.data)
    adj: dict = {}
    E = edge_array(mb.data)
    for a_, b_ in E:
        adj.setdefault(int(a_), []).append(int(b_))
        adj.setdefault(int(b_), []).append(int(a_))
    gi = {n: k for k, n in enumerate(names)}
    plan, out = {}, {}
    shaped = False
    for s, side in ((1.0, "Left"), (-1.0, "Right")):
        wx = abs(arm.data.bones[f"{side}Hand"].head_local.x)
        hand = [i for i in range(len(co)) if co[i, 0] * s > wx]
        label, stop = F.label_fingers({i: abs(co[i, 0]) for i in hand}, adj, cfg["step"], cfg["min_part"])
        tips = list(stop)
        # each chain's tip: the free tip nearest its old fingertip (greedy over all pairs)
        pairs = sorted((float(np.linalg.norm(co[t] - np.array(arm.data.bones[F.chain_names(side, f)[-1]].tail_local))),
                        f, t) for f in F.FINGERS for t in tips)
        own, used = {}, set()
        for _, f, t in pairs:
            if f not in own and t not in used:
                own[f] = t
                used.add(t)
        if len(own) != 5:
            raise RuntimeError(f"{side}: {len(tips)} free fingers found, {sorted(own)} matched")
        chains = {}
        for f, t in own.items():
            idx = np.array([i for i, l_ in label.items() if l_ == t])
            pts = co[idx]
            inn = np.zeros(len(co), dtype=bool)
            inn[idx] = True
            seg = co[E[inn[E[:, 0]] & inn[E[:, 1]]]]
            c0, d0 = (np.array(v) for v in F.fit_line(pts.tolist()))
            if float((co[t] - c0) @ d0) < 0:
                d0 = -d0
            sl = finger_slices(pts, seg, c0, d0, cfg["slice"])
            n_ = len(sl)
            lo = int(n_ * 0.15)
            cen = [list(x[1]) for x in sl[lo:max(int(n_ * 0.9), lo + 2)]]
            c, d = (np.array(v) for v in F.fit_line(cen))
            if float((co[t] - c) @ d) < 0:
                d = -d
            sl = finger_slices(pts, seg, c, d, cfg["slice"])
            if "shape" in cfg:  # M2b: slimmer, smaller tips, the thumb shorter; then measured again
                shp = cfg["shape"]
                sv = (pts - c) @ d
                s_base, s_tip = float(sv.min()), float(sv.max())
                ss = np.array([x[0] for x in sl])
                cs = smooth3(smooth3(np.array([x[1] for x in sl])))
                cb = cs[0]
                ln = 1.0 - shp.get("thumb_shorten", 0.0) if f == "Thumb" else 1.0
                for j, i in enumerate(idx):
                    cen_s = [float(np.interp(sv[j], ss, cs[:, k])) for k in range(3)]
                    k_ = (F.thumb_radial(sv[j], s_base, shp) if f == "Thumb" and "thumb_thick" in shp
                          else F.finger_radial(sv[j], s_base, s_tip, shp))  # M1d: the thumb thicker
                    co[i] = F.finger_point(co[i], cen_s, cb, k_, ln)
                pts = co[idx]
                seg = co[E[inn[E[:, 0]] & inn[E[:, 1]]]]
                sl = finger_slices(pts, seg, c, d, cfg["slice"])
                shaped = True
            thick = [(a_, b_) for a_, _, b_ in sl]
            sv = (pts - c) @ d
            s_base, s_tip = float(sv.min()), float(sv.max())
            bn = F.chain_names(side, f)
            bones = [arm.data.bones[n] for n in bn]
            lens = [b.length for b in bones]
            end = s_tip - cfg["tip_inset"]
            if f == "Thumb":
                s_root = F.along(bones[0].head_local, c, d)  # the metacarpal's head stays where it is
                s1 = s_base - cfg["thumb_mcp_back"]
                s2 = F.pick_crease(thick, s1 + (end - s1) * lens[1] / (lens[1] + lens[2]), cfg["crease_window"])
                js = [s_root, s1, s2]
                heads = [np.array(bones[0].head_local), c + s1 * d, c + s2 * d]
                half = cfg["thumb_half"]
            else:
                s1 = F.along(bones[0].head_local, c, d)
                s2 = F.pick_crease(thick, s1 + lens[0] * (end - s1) / sum(lens), cfg["crease_window"])
                s3 = F.pick_crease(thick, s2 + lens[1] * (end - s2) / (lens[1] + lens[2]), cfg["crease_window"])
                js = [s1, s2, s3]
                heads = [c + s1 * d, c + s2 * d, c + s3 * d]
                half = cfg["half"]
            tails = heads[1:] + [c + end * d]
            chains[f] = {"idx": idx, "c": c, "d": d, "js": js, "half": half, "bones": bn, "s_base": s_base,
                         "sigma": cfg["thumb_sigma"] if f == "Thumb" else cfg["sigma"]}
            for n, h, t_ in zip(bn, heads, tails):
                plan[n] = (h, t_, np.array(arm.data.bones[n].matrix_local.to_3x3().col[2]))
            out[f"{side}{f}"] = {"verts": int(len(idx)), "web": round(s_base, 4), "tip": round(s_tip, 4),
                                 "joints": [round(j, 4) for j in js],
                                 "moved_mm": [round(float(np.linalg.norm(h - np.array(arm.data.bones[n].head_local))) * 1000, 1)
                                              for n, h in zip(bn, heads)],
                                 "dir": [round(float(v), 3) for v in d]}
        # the weights: a free finger's vertices by its own chain; the palm by every chain, owned by the lines by their
        # inverse squared distance (a Gaussian's ratios turn into steps far from the lines: the first build's thumb ribbon)
        hgroups = [gi[f"{side}Hand"]] + [gi[n] for ch in chains.values() for n in ch["bones"]]
        lab = {int(i): f for f, ch in chains.items() for i in ch["idx"]}
        for i in hand:
            tot = W[i, hgroups].sum()
            if tot < 1e-6:
                continue
            p = co[i]
            new = np.zeros(len(names))
            fs = [lab[i]] if i in lab else list(chains)
            g = np.array([F.ownership(F.off_line(p, chains[f]["c"], chains[f]["d"]), chains[f]["sigma"]) for f in fs])
            if i in lab:
                g = np.ones(1)
            elif "thumb_falloff" in cfg:  # M1c: the thumb's share first, by its distance alone (a soft thenar)
                t = F.thumb_share(F.off_line(p, chains["Thumb"]["c"], chains["Thumb"]["d"]), cfg["thumb_falloff"])
                fs = [f for f in chains if f != "Thumb"]
                g_o, h = F.split_palm([F.ownership(F.off_line(p, chains[f]["c"], chains[f]["d"]), chains[f]["sigma"])
                                       for f in fs], F.ownership(cfg["palm_r"], 0.0), t)
                fs, g = fs + ["Thumb"], np.array(g_o + [t])
                new[gi[f"{side}Hand"]] += h
            else:  # the palm's own pull (pure Hand): far from every line the hand holds it
                g = g / (g.sum() + F.ownership(cfg["palm_r"], 0.0))
                new[gi[f"{side}Hand"]] += 1.0 - g.sum()
            for f, o in zip(fs, g):
                ch = chains[f]
                cw = F.chain_weights(F.along(p, ch["c"], ch["d"]), ch["js"], ch["half"])
                for n, w_ in zip([f"{side}Hand"] + ch["bones"], cw):
                    new[gi[n]] += o * w_
            W[i, hgroups] = 0.0
            W[i] += new * tot
        # the palm's weights smoothed along its edges (the free fingers' held): no step at the webs; M1c: the free
        # fingers' vertices within base_band of their web smoothed with it (the ring's strip, the middle's gap)
        band = cfg.get("base_band", 0.0)
        base = {i for i in lab if F.in_base_band(F.along(co[i], chains[lab[i]]["c"], chains[lab[i]]["d"]),
                                                 chains[lab[i]]["s_base"], band)} if band > 0 else set()
        out[f"{side}_base_band_verts"] = len(base)
        palm = np.array([i for i in hand if (i not in lab or i in base) and W[i, hgroups].sum() > 1e-6])
        on = np.zeros(len(co), dtype=bool)
        on[palm] = True
        e = E[on[E[:, 0]] | on[E[:, 1]]]
        deg = np.maximum(np.bincount(e.ravel(), minlength=len(co)), 1)[:, None]
        tot = W[:, hgroups].sum(1, keepdims=True)
        for _ in range(cfg.get("base_smooth", cfg["palm_smooth"])):
            Wh = W[:, hgroups]
            avg = np.zeros_like(Wh)
            np.add.at(avg, e[:, 0], Wh[e[:, 1]])
            np.add.at(avg, e[:, 1], Wh[e[:, 0]])
            avg /= deg
            avg *= tot / np.maximum(avg.sum(1, keepdims=True), 1e-12)
            W[np.ix_(palm, hgroups)] = 0.5 * Wh[palm] + 0.5 * avg[palm]
    if shaped:
        set_co(mb.data, co)
    # the bones (edit mode): heads, tails, the rolls kept
    select_only([arm], arm)
    bpy.ops.object.mode_set(mode="EDIT")
    for n, (h, t_, oz) in plan.items():
        eb = arm.data.edit_bones[n]
        eb.head, eb.tail = Vector(h), Vector(t_)
        eb.align_roll(Vector(F.keep_roll_z(list(oz), list(t_ - h))))
    bpy.ops.object.mode_set(mode="OBJECT")
    rep["fingers"] = out
    log(f"fingers {out}")


def fix_bends(arm, mb, cfg, W, names, rep):
    """Each joint's ring (the module's step 10) on both sides."""
    co = get_co(mb.data)
    gi = {n: k for k, n in enumerate(names)}
    out = {}
    for j in cfg:
        for s, side in ((1.0, "Left"), (-1.0, "Right")):
            cb = arm.data.bones[f"{side}{j['child']}"]
            J, T_ = np.array(cb.head_local), np.array(cb.tail_local)
            d = (T_ - J) / np.linalg.norm(T_ - J)
            fam = {cb.name, *[c.name for c in cb.children_recursive]}
            parent = j["parent"] if j["parent"] in gi else f"{side}{j['parent']}"
            m = j["margin"]
            wmax = max(j["width"], j.get("inside_width", 0.0))
            n_ = 0
            for i in np.where(co[:, 0] * s > 0.0)[0]:
                p = co[i] - J
                u = float(p @ d)
                r = float(np.linalg.norm(p - u * d))
                if abs(u) > wmax + m or r > j["radius"]:
                    continue
                off = j.get("offset", 0.0) + j.get("tilt", 0.0) * (co[i, 1] - J[1])
                wd = j["width"]
                if "inside" in j:  # the bend's inside (where LBS pinches): a wider band
                    t = F.sstep(0.0, 0.6 * j["radius"], float((p - u * d) @ np.array(j["inside"])))
                    wd += (j["inside_width"] - wd) * t
                blend = (1.0 - F.sstep(wd, wd + m, abs(u))) * (1.0 - F.sstep(j["radius"] - j["fade"], j["radius"], r))
                if "mid_x" in j:
                    blend *= F.sstep(j["mid_x"][0], j["mid_x"][1], abs(co[i, 0]))
                if blend <= 0.0:
                    continue
                wv = {names[k]: W[i, k] for k in np.where(W[i] > 0)[0]}
                nw = F.ring_blend(wv, fam, parent, cb.name, F.ring_share(u, wd, off), blend)
                W[i] = 0.0
                for g_, v in nw.items():
                    W[i, gi[g_]] = v
                n_ += 1
            out[f"{side}{j['child']}"] = n_
    rep["bends"] = out
    log(f"bends {out}")


def fixes(arm, mb, T, rep):
    if not any(k in T for k in M.KEYS_M1B | M.KEYS_M1C | M.KEYS_M2B | M.KEYS_M1D):
        return
    arm.data.pose_position = "REST"
    bpy.context.view_layer.update()
    if "degenerate" in T:
        fix_degenerate(mb, T["degenerate"], rep)
    if "arm_thicken" in T:
        fix_arms(arm, mb, T["arm_thicken"], rep)
    if "seat" in T:
        fix_seat(mb, T["seat"], rep)
    if "smooth_rest" in T:
        fix_smooth_rest(mb, T["smooth_rest"], rep)
    if "notch" in T:
        fix_notch(mb, T["notch"], rep)
    if "bust_round" in T:
        fix_bust_round(mb, T["bust_round"], rep)
    W, names = read_weights(mb)
    if "fingers" in T:
        fix_fingers(arm, mb, T["fingers"], rep, W, names)
    if "bends" in T:
        fix_bends(arm, mb, T["bends"], W, names, rep)
    write_weights(mb, W)
    rep["weights_m1b"] = {"unweighted": sum(1 for v in mb.data.vertices if not v.groups),
                          "max_groups": max(len(v.groups) for v in mb.data.vertices)}
    for p in mb.data.polygons:
        p.use_smooth = True
    arm.data.pose_position = "POSE"
    bm = bmesh.new()
    bm.from_mesh(mb.data)
    bnd = [e for e in bm.edges if e.is_boundary]
    rep["body_m1b"] = {"tris": tris(mb.data), "vertices": len(mb.data.vertices), "open_edges": len(bnd),
                       "non_manifold": sum(1 for e in bm.edges if len(e.link_faces) > 2), "parts": len(islands(bm)),
                       "slivers": slivers(bm)}
    bm.free()
    log(f"m1b body {rep['body_m1b']} weights {rep['weights_m1b']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--raw", default="D:/prime-art-raw")
    ap.add_argument("--hi", action="store_true", help="no final collapse (the before/after's before)")
    ap.add_argument("--from-body", default="", help="M1b: only the fixes, on a body built before")
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    T = M.load(a.targets)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    raw = Path(a.raw)
    rep = {"targets": T["name"], "hi": a.hi}
    if a.from_body:
        bpy.ops.wm.open_mainfile(filepath=a.from_body)
        rep["from_body"] = a.from_body
        finish(bpy.data.objects["CharacterArmature"], bpy.data.objects["Body"], T, rep, out,
               Path(a.from_body).parent / "neck_ring.json")
        return
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
    co2 = laplace(co, edges, w, npv, sm.get("mu", 0.0))
    mv = np.linalg.norm(co2 - co, axis=1)
    rep['smoothed_by_spot_mm'] = [round(float(mv[[M.soft_sphere(p, s_[:3], s_[3]) > 0 for p in co]].max()) * 1000, 1) for s_ in sm['spheres']] + [round(float(mv[[M.soft_box(p, b_[:6], sm['margin']) > 0 for p in co]].max()) * 1000, 1) for b_ in sm['boxes']]
    rep["smoothed"] = {"vertices": int((w > 0).sum()), "passes": passes,
                       "max_move_mm": round(float(np.linalg.norm(co2 - co, axis=1).max()) * 1000, 1)}
    co = co2
    log(f"smoothed {rep['smoothed']}")

    # 3. onto the skeleton (M2: the whole surface first moved along y by `shift_y`; the spots above stay in the GLB's frame)
    if "shift_y" in T:
        co[:, 1] += T["shift_y"]
        rep["shift_y"] = T["shift_y"]
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
    if ws:  # M2: none for a chest without a push
        w = np.max(ws, 0)
        npv = np.max([np.where(wi > 0, sp[4], 0) for wi, sp in zip(ws, sa["spheres"])], 0)
        co2 = laplace(co, edges, w, npv)
    else:
        co2 = co.copy()
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
    # the toes (M2): the vertices ahead of each Toes bone's head and their mean weight on it
    W_, names_ = read_weights(mb)
    toes = {}
    for pre in ("Left", "Right"):
        bn = arm.data.bones.get(f"{pre}Toes")
        if bn is None or f"{pre}Toes" not in names_:
            continue
        hx = bn.head_local
        ahead = (co[:, 1] < hx.y - 0.02) & (co[:, 2] < 0.10) & (co[:, 0] * hx.x > 0)
        toes[pre] = {"vertices": int(ahead.sum()),
                     "mean_weight": round(float(W_[ahead, names_.index(f"{pre}Toes")].mean()), 3) if ahead.any() else None}
    rep["toes"] = toes
    log(f"weights {rep['weights']} hand {rep['hand']} toes {toes}")
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
    finish(arm, mb, T, rep, out, rig_path.parent / "neck_ring.json")


def finish(arm, mb, T, rep, out, ring_json):
    fixes(arm, mb, T, rep)
    if ring_json.exists():
        shutil.copyfile(ring_json, out / "neck_ring.json")
    (out / "body.json").write_text(json.dumps(rep, indent=1), encoding="utf-8", newline="\n")
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "alien_body.blend"))
    log(f"saved {out / 'alien_body.blend'}")


if __name__ == "__main__":
    main()
