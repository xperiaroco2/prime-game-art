"""Test B (art #196, brief UPDATE 53): the mouth sculpted into the head. A muzzle grows out of the lower face and the
AI rest lips (M20's `mouth_pout_rest`) become its front edge, welded into the skin (Body): one mesh, one surface, no
seam. The eyes stay separate parts; nothing at or above the nose line moves (the gate, checked here on the vertices
and normals: 0.0000). Talking is a jaw: Body's morph target `jaw` turns the lower lip and chin about a hinge by
JAW["deg"] (8 degrees = its weight 8 / 14), and `O` rounds the opening; behind the parting a dark mouth.

  blender -b --factory-startup --python-exit-code 1 --python tools/blender/alien_muzzle.py -- \
      --kit <M20d/export> --out <TB> [--export-name export] [--params JSON]

The method (alien_muzzle_geom for the pure parts):
1. The lower face's faces (below the nose line's gate, in front of the throat) subdivided `cuts` times, smoothly.
2. Each of their vertices moved along -y to the muzzle: the skin swelled forward (geom.swell) united with the lips'
   front (a ray from the front onto the AI rest) by a smooth union, so the lips grow out of the skin in a fillet.
3. An iso-line cut where the lips stand lip_t0_mm in front of the swelled skin: the faces inside take the lips'
   material (alien_lip_pout) along a clean edge; outside, the skin's (alien_hue). Same vertices: no seam.
4. A second iso-line cut along the lip line (the groove between the lips, where the AI form's jaw weight crosses 0.5),
   then that edge path split from corner to corner: the parting. Each side rolls inward (three rings, the first lip,
   then alien_mouth_inner), and a dark inward-facing bag sits behind it.
5. The morph targets: `jaw` (each vertex turned by its jaw weight times JAW["deg"] about the hinge) and `O`.
6. The skin's crease shade: a Cycles AO bake of Body alone; in the edited region it becomes the lips' COLOR_0 (part
   AO) and the skin's pout contact channel (TEXCOORD_6.u). The rest-pose layers rewritten in place.
The kit's other mouth pieces stay in the GLB (hide them); show the pout design for its contact channel.
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
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_ao as AOM  # noqa: E402
import alien_eyes as AE  # noqa: E402
import alien_m6 as M6  # noqa: E402
import alien_muzzle_geom as G  # noqa: E402
import export_glb  # noqa: E402

LIP = "alien_lip_pout"
INNER = "alien_mouth_inner"
SKIN = "alien_hue"
REGION = {"x": 0.072, "z_lo": 1.385, "y_back": -0.015, "gate_below_mm": 3.0}
CUTS = 4
GRID_STEP = 0.00025  # the lips' front sampled on this grid (m): the outline's depth and the lip line
PIN_FADE = 0.004  # the muzzle's move fades to 0 within this distance of the region's pinned border (m)
WALL = [(0.0015, 0.0003, LIP), (0.0035, 0.0008, LIP), (0.009, 0.003, INNER)]  # per ring: back, inward (m), material
BAG = {"ry": 0.016, "rz": 0.015, "rx_share": 1.08, "front": 0.75}
O_SHAPE = {"deg": 6.0, "pinch": 0.30, "push_mm": 3.0, "r": 0.034, "lift_mm": 1.5}
AO_BAKE = {"samples": 64, "distance": 0.06, "floor": 0.18}
TALK_S = 6.0  # the talk proof's length (s): a simple amplitude curve (geom.talk_curve) drives the jaw
CREASE = {"raw_hi": 0.82, "span": 0.40}  # pout contact = (raw_hi - raw AO) / span, clamped, on the skin


def log(*a):
    print("TB", *a, flush=True)


def args():
    p = argparse.ArgumentParser()
    p.add_argument("--kit", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--export-name", default="export")
    p.add_argument("--params", default="", help='JSON {"muzzle": {...}, "jaw": {...}, "cuts": n}')
    return p.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])


def world_mesh(ob):
    mw = ob.matrix_world
    co = np.array([mw @ v.co for v in ob.data.vertices])
    polys = [list(p.vertices) for p in ob.data.polygons]
    return co, polys


def jaw_alpha(ob) -> np.ndarray:
    """The AI form's per-vertex jaw weight (COLOR_0's alpha: 1 below its lip line)."""
    me = ob.data
    at = me.color_attributes["ao"]
    col = np.empty(len(at.data) * 4, dtype=np.float32)
    at.data.foreach_get("color", col)
    a = col.reshape(-1, 4)[:, 3].astype(float)
    if at.domain == "POINT":
        return a
    lv = np.empty(len(me.loops), dtype=np.int64)
    me.loops.foreach_get("vertex_index", lv)
    s = np.bincount(lv, weights=a, minlength=len(me.vertices))
    c = np.bincount(lv, minlength=len(me.vertices)).clip(1)
    return s / c


class Lips:
    """The AI rest's front seen along +y: lip_y(x, z) (nan: no lip) and its jaw weight there."""

    def __init__(self, ob):
        self.co, polys = world_mesh(ob)
        self.alpha = jaw_alpha(ob)
        self.polys = polys
        self.bvh = BVHTree.FromPolygons([Vector(c) for c in self.co], polys)
        lo, hi = self.co.min(0), self.co.max(0)
        self.lo, self.hi = lo, hi
        st = GRID_STEP
        self.xs = np.round(np.arange(lo[0] - 0.002, hi[0] + 0.002, st), 6)
        self.zs = np.arange(lo[2] - 0.002, hi[2] + 0.002, st)
        self.dep = np.full((len(self.zs), len(self.xs)), np.nan)
        self.alp = np.full_like(self.dep, np.nan)
        for j, x in enumerate(self.xs):
            for i, z in enumerate(self.zs):
                self.dep[i, j], self.alp[i, j] = self.front(float(x), float(z))
        self.din = G.chamfer(np.isfinite(self.dep)) * st

    def inside(self, x: float, z: float) -> float:
        """0..1: how deep (x, z) lies inside the lips' outline seen from the front (geom.INSIDE_MM)."""
        j = int(round((x - self.xs[0]) / GRID_STEP))
        i = int(round((z - self.zs[0]) / GRID_STEP))
        if not (0 <= i < len(self.zs) and 0 <= j < len(self.xs)):
            return 0.0
        a, b = G.INSIDE_MM
        return float(G.smoothstep(a / 1000.0, b / 1000.0, self.din[i, j]))

    def front(self, x: float, z: float):
        hit, _n, fi, _d = self.bvh.ray_cast(Vector((x, -1.0, z)), Vector((0.0, 1.0, 0.0)), 2.0)
        if hit is None:
            return math.nan, math.nan
        vs = self.polys[fi]
        d = np.linalg.norm(self.co[vs] - np.array(hit), axis=1) + 1e-6
        return hit.y, float(np.sum(self.alpha[vs] / d) / np.sum(1 / d))


def nose_line(bm, lips_top: float) -> dict:
    """The nostrils' lowest point: vertices within |x| 2-18 mm, up to 45 mm above the lips, at the front, that lie
    behind the mean of their neighbours by more than 0.4 mm (a dimple)."""
    zs = []
    for v in bm.verts:
        x, y, z = v.co
        if 0.002 < abs(x) < 0.018 and lips_top < z < lips_top + 0.045 and y < -0.05:
            nb = [e.other_vert(v).co for e in v.link_edges]
            if nb and v.co.y - sum(c.y for c in nb) / len(nb) > 0.0004:
                zs.append(z)
    zs.sort()
    return {"z": zs[0] if zs else lips_top + 0.012, "count": len(zs), "found": bool(zs)}


def in_region(co, z_top: float) -> bool:
    return abs(co.x) < REGION["x"] and REGION["z_lo"] < co.z < z_top and co.y < REGION["y_back"]


def gate_snapshot(bm, z_gate: float) -> np.ndarray:
    bm.normal_update()
    rows = [tuple(v.co) + tuple(v.normal) for v in bm.verts if v.co.z >= z_gate]
    a = np.array(rows).reshape(-1, 6)
    return a[np.lexsort(a[:, :3].T[::-1])]


def subdivide_region(bm, z_top: float, cuts: int):
    """The region's faces subdivided `cuts` times (smoothly). bmesh.ops reallocates the mesh (every Python reference
    goes stale, and the order changes): the old region vertices are found again by position (they do not move). Returns the
    region's vertices and its pinned border (the vertices that also belong to a face outside)."""
    bm.verts.ensure_lookup_table()
    faces = [f for f in bm.faces if all(in_region(v.co, z_top) for v in f.verts)]
    fset = set(faces)
    edges = {e for f in faces for e in f.edges}
    border = [(e.verts[0].co.copy(), e.verts[1].co.copy()) for e in edges
              if any(lf not in fset for lf in e.link_faces)]
    idx = sorted({v.index for f in faces for v in f.verts})
    pos = {i: bm.verts[i].co.copy() for i in idx}
    res = bmesh.ops.subdivide_edges(bm, edges=list(edges), cuts=cuts, use_grid_fill=True, smooth=1.0)
    new = {g for g in res["geom_inner"] + res["geom_split"] if isinstance(g, bmesh.types.BMVert)}
    kd = KDTree(len(bm.verts))
    allv = list(bm.verts)
    for i, v in enumerate(allv):
        kd.insert(v.co, i)
    kd.balance()
    found = [kd.find(pos[i]) for i in idx]
    if max(f[2] for f in found) > 1e-6:  # the smooth subdivision nudges a few by < 0.4 um
        raise SystemExit("subdivide: an old region vertex moved")
    region = {allv[f[1]] for f in found} | new
    pinned = {v for v in region if any(not all(u in region for u in f.verts) for f in v.link_faces)}
    # new vertices on the region's border back onto their straight edge: the faces outside keep their shape
    for v in pinned & new:
        best = None
        for a, b in border:
            ab = b - a
            t = max(0.0, min(1.0, (v.co - a).dot(ab) / ab.length_squared))
            p = a + ab * t
            d = (v.co - p).length
            if best is None or d < best[0]:
                best = (d, p)
        v.co = best[1]
    return region, pinned


def iso_cut(bm, faces, val: dict) -> dict:
    """Splits every edge of `faces` (triangles) whose ends' values differ in sign at the crossing and joins the two
    crossings inside each face: an edge path along the zero line. Returns {new vert: (a, b, t)}."""
    for v in list(val):
        if abs(val[v]) < 1e-9:
            val[v] = 1e-9
    edges = {e for f in faces for e in f.edges}
    made = {}
    for e in edges:
        a, b = e.verts
        if a not in val or b not in val or (val[a] > 0) == (val[b] > 0):
            continue
        t = G.iso_t(val[a], val[b])
        _ne, nv = bmesh.utils.edge_split(e, a, t)
        made[nv] = (a, b, t)
        val[nv] = 0.0
    for f in list(faces):
        if not f.is_valid:
            continue
        nvs = [v for v in f.verts if v in made]
        if len(nvs) == 2 and not any(e for e in nvs[0].link_edges if e.other_vert(nvs[0]) is nvs[1]):
            bmesh.utils.face_split(f, nvs[0], nvs[1])
    return made


def main():
    a = args()
    kit = Path(a.kit)
    ex = Path(a.out) / a.export_name
    prm = json.loads(a.params) if a.params else {}
    MZ = dict(G.MUZZLE, **prm.get("muzzle", {}))
    JW = dict(G.JAW, **prm.get("jaw", {}))
    cuts = int(prm.get("cuts", CUTS))
    bpy.ops.wm.open_mainfile(filepath=str(kit / "alien_character.blend"))
    cj = json.loads((kit / "character.json").read_text(encoding="utf-8"))
    body = M6.rest_pose()
    lips_ob = bpy.data.objects["mouth_pout_rest"]
    lips = Lips(lips_ob)
    mouth_z = bpy.data.objects["Mouth"].matrix_world.translation.z
    rep = {"kit": str(kit), "muzzle": MZ, "jaw": JW, "cuts": cuts, "lips_bbox_mm": [
        [G.mm(c) for c in lips.lo], [G.mm(c) for c in lips.hi]]}
    me = body.data
    mats = {m.name: i for i, m in enumerate(me.materials)}
    for name in (LIP, INNER):
        if name not in mats:
            me.materials.append(bpy.data.materials[name])
            mats[name] = len(me.materials) - 1
    bm = bmesh.new()
    bm.from_mesh(me)
    jl = bm.verts.layers.float.new("tb_jaw")  # the jaw weight (a layer: Python vertex references go stale)
    tl = bm.verts.layers.float.new("tb_taper")  # the jaw's share near the lip line (geom.jaw_taper)
    ll = bm.verts.layers.float.new("tb_lift")  # the upper lip's rise at the full jaw (m)
    nl = nose_line(bm, float(lips.hi[2]))
    z_gate = nl["z"] - 0.001
    z_top = z_gate - REGION["gate_below_mm"] / 1000.0
    rep["nose"] = {"nostril_low_z": round(nl["z"], 4), "dimples": nl["count"], "found": nl["found"],
                   "gate_z": round(z_gate, 4), "region_top_z": round(z_top, 4)}
    log("nose", json.dumps(rep["nose"]))
    before = gate_snapshot(bm, z_gate)
    rv, pinned = subdivide_region(bm, z_top, cuts)
    bm.verts.ensure_lookup_table()
    log("region verts", len(rv), "pinned", len(pinned), "bm verts", len(bm.verts))
    kp = KDTree(len(pinned))
    for i, v in enumerate(pinned):
        kp.insert(v.co, i)
    kp.balance()
    fade = {v: (0.0 if v in pinned else float(G.smoothstep(0.0, PIN_FADE, kp.find(v.co)[2]))) for v in rv}
    # 2. the muzzle: y0 the smooth skin, then the union with the lips
    y0 = {v: v.co.y for v in rv}
    lipd = {}

    def place(v):
        ly, al = lips.front(v.co.x, v.co.z)
        s = float(G.swell(v.co.x, v.co.z, mouth_z, z_top - 0.001, MZ))
        y, stand = G.surface_y(y0[v], ly - MZ["ride"] * s, s, lips.inside(v.co.x, v.co.z), MZ)
        f = fade.get(v, 1.0)
        v.co.y = float(y0[v] + (y - y0[v]) * f)
        lipd[v] = (float(stand) if f > 0.999 else -1.0, al)

    for v in rv:
        place(v)
    # 3. the lips' border: an iso-line where the lips stand lip_t0 in front of the swelled skin
    region_faces = [f for f in bm.faces if all(v in rv for v in f.verts)]
    bmesh.ops.triangulate(bm, faces=region_faces)
    region_faces = [f for f in bm.faces if all(v in rv for v in f.verts)]
    t0 = MZ["lip_t0_mm"] / 1000.0
    val = {v: (lipd[v][0] - t0 if math.isfinite(lipd[v][0]) else -1.0) for v in rv}
    made = iso_cut(bm, region_faces, val)
    for nv, (va, vb, t) in made.items():
        rv.add(nv)
        y0[nv] = y0[va] + (y0[vb] - y0[va]) * t
        fade[nv] = fade[va] + (fade[vb] - fade[va]) * t
        place(nv)
    region_faces = [f for f in bm.faces if all(v in rv for v in f.verts)]
    lipf = set()
    for f in region_faces:
        m = sum(val.get(v, -1.0) for v in f.verts) / len(f.verts)
        f.material_index = mats[LIP] if m > 0 else mats[SKIN]
        if m > 0:
            lipf.add(f)
    rep["border_verts"] = len(made)
    rep["lip_faces"] = len(lipf)
    # 4. the lip line from the AI form's groove, then the parting
    xs = np.round(np.arange(-0.040, 0.0401, 0.0005), 5)
    jj = [int(np.argmin(np.abs(lips.xs - x))) for x in xs]
    zl = G.smooth_symmetric(xs, G.lip_line(xs, lips.zs, lips.dep[:, jj], lips.alp[:, jj]))
    okx = xs[np.isfinite(zl)]
    half = float(np.abs(okx).max()) if len(okx) else 0.03
    x_s = half - 0.002
    rep["lip_line"] = {"half_width_mm": G.mm(half), "slit_half_mm": G.mm(x_s),
                       "z_centre": round(float(np.interp(0.0, xs[np.isfinite(zl)], zl[np.isfinite(zl)])), 4)}
    log("lip line", json.dumps(rep["lip_line"]))
    xf, zf = xs[np.isfinite(zl)], zl[np.isfinite(zl)]

    def zline(x):
        return float(np.interp(x, xf, zf))

    bmesh.ops.triangulate(bm, faces=[f for f in lipf if f.is_valid])
    lipf = {f for f in bm.faces if f.material_index == mats[LIP] and all(v in rv for v in f.verts)}
    cutf = [f for f in lipf if all(abs(v.co.x) <= x_s for v in f.verts)]
    sval = {v: v.co.z - zline(v.co.x) for f in cutf for v in f.verts}
    made2 = iso_cut(bm, cutf, sval)
    for nv, (va, vb, t) in made2.items():
        rv.add(nv)
        y0[nv] = y0[va] + (y0[vb] - y0[va]) * t
        fade[nv] = fade[va] + (fade[vb] - fade[va]) * t
        place(nv)
    on = set(made2)
    slit = [e for e in bm.edges if e.verts[0] in on and e.verts[1] in on and len(e.link_faces) == 2
            and all(f.material_index == mats[LIP] for f in e.link_faces)]
    rep["slit_edges"] = len(slit)
    log("slit edges", len(slit), "on-line verts", len(on))
    bmesh.ops.split_edges(bm, edges=slit)
    bm.verts.ensure_lookup_table()

    def side(f):
        c = sum((v.co for v in f.verts), Vector()) / len(f.verts)
        return c.z - zline(c.x)

    # the parting's two chains: boundary edges along the line
    upper, lower = [], []
    for e in bm.edges:
        if e.is_boundary and all(abs(v.co.z - zline(v.co.x)) < 3e-4 and abs(v.co.x) <= x_s + 1e-4 for v in e.verts):
            (upper if side(e.link_faces[0]) > 0 else lower).append(e)
    rep["chains"] = [len(upper), len(lower)]
    log("chains", len(upper), len(lower))
    lower_verts = {v for e in lower for v in e.verts}
    upper_verts = {v for e in upper for v in e.verts}
    # 4b. the rolls inward
    dl = bm.verts.layers.deform.active
    wall_faces = {"upper": [], "lower": []}
    for name, chain, sgn in (("upper", upper, 1.0), ("lower", lower, -1.0)):
        edges = chain
        for back, inward, mat in WALL:
            res = bmesh.ops.extrude_edge_only(bm, edges=edges)
            nv = [g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)]
            nf = [g for g in res["geom"] if isinstance(g, bmesh.types.BMFace)]
            for v in nv:
                tp = max(0.0, 1.0 - (v.co.x / x_s) ** 2) ** 0.35
                v.co.y += back * tp
                v.co.z += sgn * inward * tp
                rv.add(v)
                y0[v] = v.co.y
                v[jl] = 0.0 if name == "upper" else 1.0
            for f in nf:
                f.material_index = mats[mat]
                f.normal_update()
                if (f.normal.z > 0) == (name == "upper"):
                    f.normal_flip()
            wall_faces[name] += nf
            edges = [g for g in res["geom"] if isinstance(g, bmesh.types.BMEdge) and g.is_boundary
                     and all(v in nv for v in g.verts)]
    # 5a. the jaw weight on the skin and lips
    walls = {v for fs in wall_faces.values() for f in fs for v in f.verts}
    for v in rv:
        if v in walls or v in lower_verts or v in upper_verts:
            continue
        sd = v.co.z - zline(max(-half, min(half, v.co.x)))
        v[jl] = float(G.jaw_weight(v.co.x, v.co.y, sd, x_s, JW))
    for v in rv:
        if v in walls or v in lower_verts or v in upper_verts or abs(v.co.x) > 0.06:
            continue
        sd = v.co.z - zline(max(-half, min(half, v.co.x)))
        v[tl] = float(G.jaw_taper(v.co.x, sd, x_s, JW))
        v[ll] = float(G.lip_lift(v.co.x, sd, x_s, JW)) if v.co.y < -0.06 else 0.0
    for v in lower_verts:
        v[jl] = 1.0
        v[tl] = float(G.jaw_taper(v.co.x, 0.0, x_s, JW))
    for v in upper_verts:
        v[jl] = 0.0
        v[ll] = float(G.lip_lift(v.co.x, 0.0, x_s, JW))
    for name, fs in wall_faces.items():
        for f in fs:
            for v in f.verts:
                if name == "lower":
                    v[tl] = float(G.jaw_taper(v.co.x, 0.0, x_s, JW))
                else:
                    v[ll] = float(G.lip_lift(v.co.x, 0.0, x_s, JW))
    corner = [v for v in rv if v in lower_verts and v in upper_verts]
    for v in corner:  # the parting's two ends (shared by both chains) stay with the head, half way
        v[jl] = 0.5
    # 4c. the bag behind the parting
    zc = zline(0.0)
    yc = min(v.co.y for v in lower_verts | upper_verts if abs(v.co.x) < 0.004) + BAG["ry"] * BAG["front"]
    m = Matrix.Translation((0.0, yc, zc - 0.002)) @ Matrix.Diagonal((x_s * BAG["rx_share"], BAG["ry"], BAG["rz"], 1.0))
    sph = bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=14, radius=1.0, matrix=m)
    bag = sph["verts"]
    bag_faces = list({f for v in bag for f in v.link_faces})
    bmesh.ops.reverse_faces(bm, faces=bag_faces)
    kd = KDTree(len(rv))
    rvl = [v for v in rv if v.is_valid]
    for i, v in enumerate(rvl):
        kd.insert(v.co, i)
    kd.balance()
    for v in bag:
        _c, i, _d = kd.find(v.co)
        v[dl].clear()
        for g, w in rvl[i][dl].items():
            v[dl][g] = w
        v[jl] = float(1.0 - G.smoothstep(zc - 0.004, zc + 0.004, v.co.z))
        rv.add(v)
    for f in bag_faces:
        f.material_index = mats[INNER]
        f.smooth = True
    for fs in wall_faces.values():
        for f in fs:
            f.smooth = True
    rep["bag"] = {"centre_mm": [0.0, G.mm(yc), G.mm(zc - 0.002)], "r_mm": [G.mm(x_s * BAG["rx_share"]),
                  G.mm(BAG["ry"]), G.mm(BAG["rz"])]}
    # the gate before writing back
    after = gate_snapshot(bm, z_gate)
    if before.shape != after.shape:
        raise SystemExit(f"gate: {before.shape[0]} vertices above the nose line before, {after.shape[0]} after")
    gd = np.abs(before - after).max(0)
    rep["gate"] = {"verts": int(before.shape[0]), "max_move_mm": round(float(gd[:3].max()) * 1000, 4),
                   "max_normal": round(float(gd[3:].max()), 5)}
    log("gate", json.dumps(rep["gate"]))
    if gd[:3].max() > 0.0:
        raise SystemExit(f"gate: a vertex above the nose line moved {gd[:3].max()}")
    bm.to_mesh(me)
    bm.free()
    me.update()
    n = len(me.vertices)
    jw = np.empty(n)
    me.attributes["tb_jaw"].data.foreach_get("value", jw)
    me.attributes.remove(me.attributes["tb_jaw"])
    taper = np.ones(n)
    lift = np.zeros(n)
    if "tb_taper" in me.attributes:
        me.attributes["tb_taper"].data.foreach_get("value", taper)
        me.attributes["tb_lift"].data.foreach_get("value", lift)
        me.attributes.remove(me.attributes["tb_taper"])
        me.attributes.remove(me.attributes["tb_lift"])
    taper = np.where(taper == 0.0, 1.0, taper)  # a vertex never set keeps the whole turn
    co = np.empty(n * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    # 5b. the morph targets
    body.shape_key_add(name="Basis", from_mix=False)
    kj = body.shape_key_add(name="jaw", from_mix=False)
    pj = G.rot_x(co, JW["hinge_y"], JW["hinge_z"], jw * taper * JW["deg"])
    pj[:, 2] += lift
    kj.data.foreach_set("co", pj.ravel())
    ko = body.shape_key_add(name="O", from_mix=False)
    po = G.rot_x(co, JW["hinge_y"], JW["hinge_z"], jw * taper * O_SHAPE["deg"])
    r = np.sqrt(co[:, 0] ** 2 + (co[:, 2] - zc) ** 2)
    g = (1.0 - G.smoothstep(0.4 * O_SHAPE["r"], O_SHAPE["r"], r)) * (co[:, 1] < -0.03)
    po[:, 0] -= co[:, 0] * O_SHAPE["pinch"] * g
    po[:, 1] -= O_SHAPE["push_mm"] / 1000.0 * g
    up = (1.0 - jw) * (co[:, 2] > zc - 0.0005) * g
    po[:, 2] += O_SHAPE["lift_mm"] / 1000.0 * up * (1.0 - G.smoothstep(0.0, 0.6 * O_SHAPE["r"], np.abs(co[:, 0])))
    ko.data.foreach_set("co", po.ravel())
    rep["morphs"] = {"jaw_verts": int((jw > 1e-4).sum()), "jaw_drop_mm": G.mm(np.abs(pj - co).max()),
                     "O_move_mm": G.mm(np.linalg.norm(po - co, axis=1).max())}
    log("morphs", json.dumps(rep["morphs"]))
    deg = G.deg_from_amp(G.talk_curve(np.arange(0.0, TALK_S, 1.0 / 30.0)), JW["deg"])
    rep["talk"] = [round(float(d) / JW["deg"], 4) for d in deg]  # the jaw morph's weight per frame at 30 fps
    # 6. the crease shade
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = AO_BAKE["samples"]
    if sc.world is None:
        sc.world = bpy.data.worlds.new("w")
    sc.world.light_settings.distance = AO_BAKE["distance"]
    old_ao = np.empty(n * 4, dtype=np.float32)
    me.color_attributes["ao"].data.foreach_get("color", old_ao)
    raw = M6._bake_ao([body], {"Body"})["Body"]
    region = co[:, 2] < z_top
    region &= (np.abs(co[:, 0]) < REGION["x"]) & (co[:, 1] < REGION["y_back"]) & (co[:, 2] > REGION["z_lo"])
    ring = cj.get("report", {}).get("ring")
    v_ao = AO_BAKE["floor"] + (1 - AO_BAKE["floor"]) * raw
    if ring:
        v_ao = v_ao + AOM.JAW_LIFT["lift"] * AOM.jaw_mask(co, ring) * (1 - v_ao)
    new = old_ao.reshape(-1, 4).copy()
    new[region, 0:3] = v_ao[region, None]
    me.color_attributes["ao"].data.foreach_set("color", new.astype(np.float32).ravel())
    crease = np.clip((CREASE["raw_hi"] - raw) / CREASE["span"], 0.0, 1.0)
    lv = np.empty(len(me.loops), dtype=np.int64)
    me.loops.foreach_get("vertex_index", lv)
    uv = np.empty(len(me.loops) * 2, dtype=np.float32)
    me.uv_layers["contact_mouth2"].data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    sel = region[lv]
    uv[sel, 0] = crease[lv][sel]
    me.uv_layers["contact_mouth2"].data.foreach_set("uv", uv.ravel())
    rep["crease"] = {"region_verts": int(region.sum()), "contact_max": round(float(crease[region].max()), 3),
                     "contact_mean": round(float(crease[region].mean()), 3)}
    # the rest-pose layers in place (alien_ao.rest_coords' values; their order stays)
    nr = np.empty(n * 3)
    me.vertex_normals.foreach_get("vector", nr)
    nr = nr.reshape(-1, 3)
    vals = {"rest_xy": (co[:, 0], co[:, 2]), "rest_zn": (-co[:, 1], -nr[:, 1] + 2.0)}
    for name, (u, w) in vals.items():
        d = np.stack([u[lv], 1.0 - w[lv]], 1).astype(np.float32).ravel()
        me.uv_layers[name].data.foreach_set("uv", d)
    me.update()
    rep["body"] = {"verts": n, "tris": sum(len(p.vertices) - 2 for p in me.polygons)}
    log("body", json.dumps(rep["body"]))
    arm = body.find_armature()
    if arm is not None:
        arm.data.pose_position = "POSE"
    bpy.context.view_layer.update()
    ex.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(ex / "alien_character.blend"))
    opts = dict(export_glb.options(False), export_image_format="AUTO", export_vertex_color="ACTIVE",
                export_tangents=True, export_extras=True, export_morph=True,
                export_morph_normal=True, export_morph_tangent=True)
    glb = ex / "alien_character.glb"
    res = bpy.ops.export_scene.gltf(filepath=str(glb), **opts)
    if res != {"FINISHED"}:
        raise SystemExit(f"export: {res}")
    AE.check_images(glb)
    for f in kit.iterdir():
        if f.suffix == ".png":
            shutil.copy2(f, ex / f.name)
    cj["tb"] = rep
    cj["note_tb"] = ("art #196 Test B: the pout's AI rest lips welded into Body as a muzzle (one mesh; the lips are "
                     "Body's alien_lip_pout faces, the parting's rolls and the bag alien_mouth_inner); Body's morph "
                     "targets `jaw` (14 degrees) and `O`; hide every mouth_* piece and show the pout design for its "
                     "contact channel (TEXCOORD_6.u, the muzzle's crease).")
    (ex / "character.json").write_text(json.dumps(cj, indent=1), encoding="utf-8", newline="\n")
    (ex / "tb.json").write_text(json.dumps(rep, indent=1), encoding="utf-8", newline="\n")
    log("EXPORT", glb, round(glb.stat().st_size / 1e6, 2), "MB")


if __name__ == "__main__":
    main()
