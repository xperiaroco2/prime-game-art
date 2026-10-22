"""T1 "socketed head", step 2 (art #196), in headless Blender: seats step 1's Meshy face pieces into the socketed
head and exports the kit.

    blender -b --factory-startup --python-exit-code 1 --python tools/blender/alien_t1_kit.py -- \
        --raw <2026-10-22-alien-t1-sockets-3d> --out <dir> [--grid] [--mouth-w K] [--eye-k K]
        [--ref-approved PNG --ref-h2 PNG]

- Measures the head: a front depth map (rays along +Y), its recess against a blurred envelope, the two socket
  centres and rims (a sphere fitted to each socket's bowl), the mouth dish's centre and size.
- Eyes: a clean ball per socket with a painted texture (white, brown iris, pupil, catch light; alien_pilot_geom
  .eye_pixel), its origin at the ball's centre so it turns in the socket (gaze); three lid shells per side (open, half,
  closed: alien_t1_geom.LIDS), built here instead of Meshy's lids.
- Mouths (rest, smile, sad, O) and brows (sad, raised, angry): Meshy's meshes, decimated, scaled to the dish or the
  rim, turned to the skin's normal and seated (alien_t1_geom.seat_y: the back sinks behind the skin, no gap); the O's
  back ball is cut off and a dark throat disc closes the hole. Every piece is a separate object parented to the head.
- `--fill` (step 3): fills the sockets and the mouth dish flush first (fill_recesses), then seats the eyes on that
  skin, `--eye-sink` of their radius behind it; `--eye-scale` shrinks the eyeballs and lids (0.75 in step 3);
  `--ref-step2 DIR` puts step 2's front row on the sheet instead of H2's; `--sheet`, `--glb-name` name the outputs.
- Step 3c (no recesses): `--repaint` paints the old sockets and the dish over with the skin around them before the
  fill (repaint_recesses: a harmonic fill of the vertex colours drawn back into the texture and a flattened normal
  map, saved as new PNGs in --out) and the lids wear the head's texture (skin_uv); `--lids upper` builds the upper
  lid only (a lower lid only where the lids meet, the blink: alien_t1_geom.lid_parts), so no ring circles the ball;
  `--bare SHEET` renders the filled head without pieces beside Meshy's original, plain grey, front and 3/4, and
  writes the labelled step 3c sheet (2D, `--ref-step2`'s row, this step's rows; every expression front and 3/4).
- `--grid`: renders an expression (`--grid-expr`, rest) for a grid of mouth widths x eyeball scales (`--grid-mouth`,
  `--grid-eye`) front and three-quarter (grid.jpg) and stops.
- Otherwise: the expressions (alien_t1_geom.expressions) front and three-quarter, close-ups of the mouth seam and the
  eye socket, the comparison sheet with `--ref-approved` and `--ref-h2` (the 2D rows on top), t1_chameleon_kit.glb (every node, the rest
  set marked visible in the nodes' extras: glTF has no hidden flag) and t1_expressions.json.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_pilot_geom as PG  # noqa: E402
import alien_t1_geom as G  # noqa: E402

EYE_SPEC = {"iris_deg": 19.0, "pupil_deg": 9.0, "sclera": (0.96, 0.95, 0.92), "iris": (0.30, 0.13, 0.05),
            "iris_rim": (0.10, 0.04, 0.02), "pupil": (0.012, 0.008, 0.008), "glint": (0.35, 0.06, 0.024)}
THROAT = (0.10, 0.05, 0.16)
PIECE_ITEMS = {"mouth_rest": "mouth_rest", "mouth_smile": "mouth_smile", "mouth_sad": "mouth_sad",
               "mouth_o": "mouth_o", "brow": "brow"}


def log(*a):
    print("T1", *a, flush=True)


# ---------------------------------------------------------------- import and measure
def import_one(path: Path, name: str):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    for o in meshes:
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
    for o in new:
        if o.type != "MESH":
            bpy.data.objects.remove(o)
    o = meshes[0]
    o.data.transform(o.matrix_world)
    o.matrix_world = Matrix.Identity(4)
    o.name = o.data.name = name
    return o


def make_bvh(o) -> BVHTree:
    return BVHTree.FromPolygons([v.co.copy() for v in o.data.vertices], [p.vertices[:] for p in o.data.polygons])


def skin_hit(bvh, x: float, z: float, y0: float = -5.0):
    loc, nrm, _, _ = bvh.ray_cast(Vector((x, y0, z)), Vector((0.0, 1.0, 0.0)))
    return (loc, nrm) if loc is not None else (None, None)


def gauss(a: np.ndarray, sigma: float) -> np.ndarray:
    r = int(3 * sigma) + 1
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    p = np.pad(a, r, mode="edge")
    p = np.apply_along_axis(lambda v: np.convolve(v, k, mode="valid"), 1, p)
    return np.apply_along_axis(lambda v: np.convolve(v, k, mode="valid"), 0, p)


def measure(head, bvh) -> dict:
    co = np.array([v.co[:] for v in head.data.vertices])
    lo, hi = co.min(0), co.max(0)
    nx, nz = 160, 200
    xs, zs = np.linspace(lo[0], hi[0], nx), np.linspace(lo[2], hi[2], nz)
    dep = np.full((nz, nx), np.nan)
    for j, z in enumerate(zs):
        for i, x in enumerate(xs):
            loc, _ = skin_hit(bvh, x, z)
            if loc is not None:
                dep[j, i] = loc.y
    valid = ~np.isnan(dep)
    filled = np.where(valid, dep, np.nanmax(dep))
    cell = xs[1] - xs[0]
    rec = np.where(valid, filled - gauss(filled, 0.12 / cell), -1.0)
    X, Z = np.meshgrid(xs, zs)

    def blob(mask):
        r = np.where(mask & valid, rec, -1.0)
        j, i = np.unravel_index(np.argmax(r), r.shape)
        peak = r[j, i]
        near = mask & valid & (np.hypot(X - xs[i], Z - zs[j]) < 0.16) & (rec > 0.4 * peak)
        w = rec[near]
        return float((X[near] * w).sum() / w.sum()), float((Z[near] * w).sum() / w.sum()), float(peak)

    sockets = {}
    for side, sgn in (("L", 1.0), ("R", -1.0)):
        cx, cz, peak = blob((sgn * X > 0.05) & (sgn * X < 0.45) & (Z > 0.12) & (Z < 0.75))
        d = np.hypot(X - cx, Z - cz)
        rim = 0.3
        for r in np.arange(0.03, 0.3, cell):
            ring = valid & (np.abs(d - r) < cell)
            if ring.any() and rec[ring].mean() <= 0.0:
                rim = float(r)
                break
        bowl = [tuple(v) for v in co if math.hypot(v[0] - cx, v[2] - cz) < 0.75 * rim
                and abs(v[1] - dep[np.argmin(np.abs(zs - v[2])), np.argmin(np.abs(xs - v[0]))]) < 0.01]
        centre, radius = PG.fit_sphere(bowl)
        ring = valid & (np.abs(d - rim) < 1.5 * cell)
        sockets[side] = {"cx": cx, "cz": cz, "peak": peak, "rim": rim, "rim_y": float(dep[ring].mean()),
                         "bowl_centre": list(centre), "bowl_r": radius, "bowl_n": len(bowl)}
    mz = min(s["cz"] for s in sockets.values())
    # the dish: the muzzle's lips protrude, so the recess map does not find it; the centre column's front profile
    # does: the deepest valley between the nose and the chin (the hollow between the dish's upper and lower rim)
    i0 = int(np.argmin(np.abs(xs)))
    col = np.nanmean(dep[:, max(i0 - 1, 0):i0 + 2], axis=1)
    idx = np.where((zs < mz - 0.12) & (zs > mz - 0.55) & ~np.isnan(col))[0][::-1]  # top to bottom
    prof = [-float(col[j]) for j in idx]
    k, prom = PG.valley(prof)
    jv = int(idx[k])
    ju = int(idx[:k][int(np.argmax(prof[:k]))])
    jl = int(idx[k + 1:][int(np.argmax(prof[k + 1:]))])

    def lip_width(j):
        row, lim, n = dep[j], col[j] + 0.06, 0
        left = right = i0
        while right + 1 < nx and not np.isnan(row[right + 1]) and row[right + 1] < lim:
            right += 1
        while left - 1 >= 0 and not np.isnan(row[left - 1]) and row[left - 1] < lim:
            left -= 1
        return float(xs[right] - xs[left])

    dish = {"cx": 0.0, "cz": float(zs[jv]), "prominence": prom, "z_upper": float(zs[ju]), "z_lower": float(zs[jl]),
            "w": max(lip_width(ju), lip_width(jl)), "h": float(zs[ju] - zs[jl]), "y_valley": float(col[jv])}
    return {"bbox": [lo.tolist(), hi.tolist()], "sockets": sockets, "dish": dish}


# ---------------------------------------------------------------- step 3: the recesses filled flush
def grid_at(xs, zs, a: np.ndarray, x: float, z: float) -> float:
    """a (rows z, columns x) at (x, z), bilinear."""
    fx = min(max((x - xs[0]) / (xs[1] - xs[0]), 0.0), len(xs) - 1.001)
    fz = min(max((z - zs[0]) / (zs[1] - zs[0]), 0.0), len(zs) - 1.001)
    i, j = int(fx), int(fz)
    tx, tz = fx - i, fz - j
    return float((a[j, i] * (1 - tx) + a[j, i + 1] * tx) * (1 - tz) + (a[j + 1, i] * (1 - tx) + a[j + 1, i + 1] * tx) * tz)


def muzzle_region(m: dict) -> tuple:
    """Step 3d: the whole mouth area, the head's built-in lips and their slit, as a region (cx, cz, ra, rb, fall)."""
    d = m["dish"]
    return (0.0, d["cz"], 0.62 * d["w"], 1.05 * d["h"], 1.4)


def face_regions(m: dict, paint: bool = False, muzzle: bool = False) -> list:
    """The recesses as ellipses on the front (x, z): (cx, cz, ra, rb, fall), first the two sockets, then the dish.
    paint (step 3c): wider, over the texture's painted rims and the socket's measured recess too."""
    regions = []
    for side in G.SIDES:
        s = m["sockets"][side]
        bx, _, bz = s["bowl_centre"]
        if paint:
            regions.append((bx, bz, 1.2 * s["bowl_r"], 1.15 * s["bowl_r"], 1.3))
        else:
            regions.append((bx, bz, 1.05 * s["bowl_r"], 1.05 * s["bowl_r"], 1.4))
    d = m["dish"]
    # the dish only: a wider ellipse reached the jaw's corners, where the jaw meets the neck (a hollow too)
    if paint and muzzle:  # step 3d: the smoothed muzzle and a little past it
        _, cz, ra, rb, _ = muzzle_region(m)
        regions.append((0.0, cz, max(1.1 * ra, 0.8 * d["w"]), max(1.1 * rb, d["h"]), 1.35))
    elif paint:
        regions.append((0.0, d["cz"], 0.8 * d["w"], 1.0 * d["h"], 1.35))
        for side in G.SIDES:  # the socket's own recess, inward of the fitted bowl
            s = m["sockets"][side]
            regions.append((s["cx"], s["cz"], 1.3 * s["rim"], 1.3 * s["rim"], 1.35))
    else:
        regions.append((0.0, d["cz"], 0.6 * d["w"], 0.75 * d["h"], 1.35))
    return regions


def region_mask(regions: list, x, z, only=None):
    """1 inside a region, a smoothstep down to 0 at its `fall` (x its radii); the regions' maximum."""
    out = np.zeros_like(np.asarray(x, dtype=float))
    for cx, cz, ra, rb, fall in regions if only is None else [regions[only]]:
        t = np.clip((np.hypot((x - cx) / ra, (z - cz) / rb) - 1.0) / (fall - 1.0), 0.0, 1.0)
        out = np.maximum(out, 1.0 - t * t * (3.0 - 2.0 * t))
    return out


# ---------------------------------------------------------------- step 3c: the recesses repainted
def welded_edges(me, co: np.ndarray):
    """The mesh's edge graph with vertices at one place merged (the glTF import splits the skin at every UV seam,
    and the atlas has hundreds of islands): (inverse: vertex -> welded id, n welded, a, b both edge directions)."""
    _, inv = np.unique(np.round(co / 1e-5).astype(np.int64), axis=0, return_inverse=True)
    inv = inv.ravel()
    ev = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get("vertices", ev)
    a, b = inv[ev[0::2]], inv[ev[1::2]]
    keep = a != b
    a, b = a[keep], b[keep]
    return inv, int(inv.max()) + 1, np.concatenate([a, b]), np.concatenate([b, a])


def head_images(head) -> dict:
    """The head material's base-colour and normal-map images (None when missing)."""
    nt = head.data.materials[0].node_tree
    found = {"base": None, "normal": None}
    for n in nt.nodes:
        if n.type != "TEX_IMAGE":
            continue
        for l in n.outputs["Color"].links:
            if l.to_socket.name == "Base Color":
                found["base"] = n.image
            elif l.to_node.type == "NORMAL_MAP":
                found["normal"] = n.image
    return found


def repaint_recesses(head, m: dict, out: Path, iters: int = 4000, muzzle: bool = False, tag: str = "3c") -> dict:
    """Paints the old sockets and the mouth hollow over with the skin around them (step 3c). The atlas is cut into
    many small islands, so the fill runs on the mesh, not on the image: every vertex inside the paint regions
    (face_regions(paint=True)) gets the harmonic fill of the vertex colours on the regions' border (Jacobi on the
    edge graph: the teal top and the pale front run on smoothly, no ring, no baked shading), then each touched
    triangle is drawn back into the texture in UV space (1.5 px past its edges, over the islands' gutters), blended
    by the region weight. The normal map is flattened under the same weight. The images are saved as new PNGs."""
    me = head.data
    imgs = head_images(head)
    base = imgs["base"]
    W, H = base.size
    px = np.empty(W * H * 4, dtype=np.float32)
    base.pixels.foreach_get(px)
    px = px.reshape(H, W, 4)
    nv = len(me.vertices)
    co = np.empty(nv * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(nv, 3)
    regions = face_regions(m, paint=True, muzzle=muzzle)
    wv = np.where(co[:, 1] < 0.0, region_mask(regions, co[:, 0], co[:, 2]), 0.0)
    nl = len(me.loops)
    lv = np.empty(nl, dtype=np.int64)
    me.loops.foreach_get("vertex_index", lv)
    luv = np.empty(nl * 2)
    me.uv_layers.active.data.foreach_get("uv", luv)
    luv = luv.reshape(nl, 2)
    vuv = np.zeros((nv, 2))
    vuv[lv] = luv
    tx = np.clip((vuv[:, 0] % 1.0 * W).astype(int), 0, W - 1)
    ty = np.clip((vuv[:, 1] % 1.0 * H).astype(int), 0, H - 1)
    col_v = px[ty, tx, :3].astype(np.float64)
    inv, nw, a, b = welded_edges(me, co)
    cnt = np.bincount(inv, minlength=nw)
    col = np.stack([np.bincount(inv, weights=col_v[:, k], minlength=nw) for k in range(3)], 1) / cnt[:, None]
    cow = np.stack([np.bincount(inv, weights=co[:, k], minlength=nw) for k in range(3)], 1) / cnt[:, None]
    ww = np.zeros(nw)
    np.maximum.at(ww, inv, wv)
    free = ww > 0.0
    # the muzzle's front is pale mint: the dish's core is held at the chin's pale colour (the dish's border alone is
    # mostly the teal cheeks', which painted the whole muzzle teal)
    d = m["dish"]
    chin = (~free) & (cow[:, 1] < 0.0) & (np.abs(cow[:, 0]) < 0.12) & (cow[:, 2] < d["z_lower"] - 0.06) &         (cow[:, 2] > d["z_lower"] - 0.25)
    pale = np.median(col[chin], axis=0) if chin.any() else col[~free].mean(0)
    dish_core = region_mask(regions[2:3], cow[:, 0], cow[:, 2]) > 0.6
    col[dish_core & free] = pale
    free = free & ~dish_core
    keep = free[a]
    a, b = a[keep], b[keep]  # the free vertices' neighbours (both directions are in a, b already)
    deg = np.bincount(a, minlength=nw).astype(float)
    fill = col.copy()
    fill[free] = col[~free & (np.bincount(b, minlength=nw) > 0)].mean(0) if (~free).any() else col[free].mean(0)
    for _ in range(iters):
        s = np.stack([np.bincount(a, weights=fill[b, k], minlength=nw) for k in range(3)], 1)
        fill[free] = s[free] / np.maximum(deg[free], 1.0)[:, None]
    fill = fill[inv]  # back to the split vertices
    blend = np.clip(wv * 2.5, 0.0, 1.0)  # full paint over most of the fall, a short blend at its outer edge
    nrm_img = imgs["normal"]
    if nrm_img is not None:
        npx = np.empty(W * H * 4, dtype=np.float32)
        nrm_img.pixels.foreach_get(npx)
        npx = npx.reshape(H, W, 4)
    flat = np.array([0.5, 0.5, 1.0], dtype=np.float32)
    drawn = 0
    for poly in me.polygons:
        vids = list(poly.vertices)
        if not (wv[vids] > 0.0).any() or len(vids) != 3:
            continue
        li = list(poly.loop_indices)
        P = luv[li] * (W, H)
        lo = np.floor(P.min(0) - 2).astype(int)
        hi = np.ceil(P.max(0) + 2).astype(int)
        xs = np.arange(max(lo[0], 0), min(hi[0], W - 1) + 1)
        ys = np.arange(max(lo[1], 0), min(hi[1], H - 1) + 1)
        if not len(xs) or not len(ys):
            continue
        X, Y = np.meshgrid(xs + 0.5, ys + 0.5)
        (x0, y0), (x1, y1), (x2, y2) = P
        area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if abs(area) < 1e-9:
            continue
        l0 = ((x1 - X) * (y2 - Y) - (x2 - X) * (y1 - Y)) / area
        l1 = ((x2 - X) * (y0 - Y) - (x0 - X) * (y2 - Y)) / area
        l2 = 1.0 - l0 - l1
        # signed distance to each edge in pixels: inside the triangle or within 1.5 px of it
        ed = [np.hypot(x2 - x1, y2 - y1), np.hypot(x0 - x2, y0 - y2), np.hypot(x1 - x0, y1 - y0)]
        hgt = [abs(area) / max(e, 1e-9) for e in ed]
        inside = (l0 * hgt[0] > -1.5) & (l1 * hgt[1] > -1.5) & (l2 * hgt[2] > -1.5)
        if not inside.any():
            continue
        L = np.clip(np.stack([l0, l1, l2], -1), 0.0, None)
        L /= np.maximum(L.sum(-1, keepdims=True), 1e-9)
        c = L @ fill[vids]
        k = (L @ blend[vids])[..., None]
        jj, ii = np.nonzero(inside)
        gy, gx = ys[jj], xs[ii]
        px[gy, gx, :3] = px[gy, gx, :3] * (1.0 - k[jj, ii]) + c[jj, ii] * k[jj, ii]
        if nrm_img is not None:
            npx[gy, gx, :3] = npx[gy, gx, :3] * (1.0 - k[jj, ii]) + flat * k[jj, ii]
        drawn += 1
    saved = {}
    for key, img, arr in (("base", base, px), ("normal", nrm_img, npx if nrm_img is not None else None)):
        if img is None:
            continue
        img.pixels.foreach_set(arr.ravel())
        path = out / f"t1_head_{key}_{tag}.png"
        img.save(filepath=str(path))
        img.pack()
        saved[key] = path.name
    return {"vertices": int(free.sum()), "pale_srgb": [round(float(c), 3) for c in pale], "triangles": drawn,
            "iters": iters, "images": saved,
            "normal_map": nrm_img is not None}


def skin_uv(o, head, bvh):
    """Gives o the head's UVs at its nearest skin point, so a piece using the head's material continues its colours
    exactly (the step 3c lids)."""
    from mathutils.geometry import barycentric_transform
    me, hm = o.data, head.data
    huv = hm.uv_layers.active.data
    uvl = me.uv_layers.new(name=hm.uv_layers.active.name)
    cache = {}
    mw = Matrix.Translation(o.location)  # new_object: a plain offset; matrix_world updates lazily
    for poly in me.polygons:
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index
            if vi not in cache:
                p = mw @ me.vertices[vi].co
                loc, _, fi, _ = bvh.find_nearest(p)
                hp = hm.polygons[fi]
                vs = [hm.vertices[i].co for i in hp.vertices[:3]]
                uvs = [Vector((*huv[j].uv, 0.0)) for j in list(hp.loop_indices)[:3]]
                cache[vi] = barycentric_transform(loc, *vs, *uvs).to_2d()
            uvl.data[li].uv = cache[vi]


def radial_map(bvh, C: Vector, na: int = 220, ne: int = 200):
    """The outer radius R(elevation, azimuth) of the head seen from C (nan where a ray misses)."""
    az = np.linspace(-1.9, 1.9, na)  # 0 = straight ahead (-Y), + toward +X
    el = np.linspace(-1.1, 1.3, ne)
    R = np.full((ne, na), np.nan)
    for j, e in enumerate(el):
        for i, a in enumerate(az):
            d = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
            loc, _, _, _ = bvh.ray_cast(C + d * 5.0, -d)
            if loc is not None:
                R[j, i] = (loc - C).length
    return az, el, R


def grid_at_v(xs, zs, a: np.ndarray, x: np.ndarray, z: np.ndarray) -> np.ndarray:
    """grid_at for arrays of points."""
    fx = np.clip((x - xs[0]) / (xs[1] - xs[0]), 0.0, len(xs) - 1.001)
    fz = np.clip((z - zs[0]) / (zs[1] - zs[0]), 0.0, len(zs) - 1.001)
    i, j = fx.astype(int), fz.astype(int)
    tx, tz = fx - i, fz - j
    return (a[j, i] * (1 - tx) + a[j, i + 1] * tx) * (1 - tz) + (a[j + 1, i] * (1 - tx) + a[j + 1, i + 1] * tx) * tz


def thin_plate_fill(R: np.ndarray, free: np.ndarray, hx: np.ndarray, hz: float, iters: int = 30000,
                    tol: float = 1e-9) -> np.ndarray:
    """R with its free cells replaced by the smoothest surface through the rest (a thin plate: the sum of the
    squared Laplacians is least), by conjugate gradients on the free cells' window; hx: the column step per row."""
    js, is_ = np.nonzero(free)
    j0, j1 = max(int(js.min()) - 3, 0), min(int(js.max()) + 4, R.shape[0])
    i0, i1 = max(int(is_.min()) - 3, 0), min(int(is_.max()) + 4, R.shape[1])
    sub = R[j0:j1, i0:i1].copy()
    sub = np.where(np.isnan(sub), np.nanmean(sub), sub)
    f = free[j0:j1, i0:i1]
    cx = ((hz / hx[j0:j1]) ** 2)[:, None]  # the steps' ratio; the vertical weight is 1

    def lap(u):  # the 5-point Laplacian on the window's inner cells, 0 on its border
        out = np.zeros_like(u)
        out[1:-1, 1:-1] = (cx[1:-1] * (u[1:-1, :-2] + u[1:-1, 2:] - 2.0 * u[1:-1, 1:-1])
                           + u[:-2, 1:-1] + u[2:, 1:-1] - 2.0 * u[1:-1, 1:-1])
        return out

    def lap_t(v):  # its transpose (v is 0 on the border)
        q = np.pad(v, 1)
        cq = np.pad(cx, ((1, 1), (0, 0)), mode="edge")
        return (cq[1:-1] * (q[1:-1, :-2] + q[1:-1, 2:]) - 2.0 * cx * v + q[:-2, 1:-1] + q[2:, 1:-1] - 2.0 * v)

    def op(x):
        u = np.zeros_like(sub)
        u[f] = x
        return lap_t(lap(u))[f]

    fixed = np.where(f, 0.0, sub)
    rhs = -lap_t(lap(fixed))[f]
    x = sub[f].copy()
    r = rhs - op(x)
    d = r.copy()
    rr = float(r @ r)
    stop = tol * max(float(rhs @ rhs), 1e-30)
    for _ in range(iters):
        if rr <= stop:
            break
        Ad = op(d)
        alpha = rr / float(d @ Ad)
        x += alpha * d
        r -= alpha * Ad
        rr2 = float(r @ r)
        d = r + (rr2 / rr) * d
        rr = rr2
    u = fixed.copy()
    u[f] = x
    out = R.copy()
    out[j0:j1, i0:i1] = u
    return out


def smooth_muzzle(head, m: dict, centre=(0.0, 0.1, 0.1), deep: float = 0.1, relax: int = 30) -> dict:
    """Step 3d: the head's built-in lips and the slit between them become a smooth, flush muzzle. In the radial map
    the muzzle region (muzzle_region) is replaced by a thin plate through the skin around it (the muzzle's curve
    runs on, lips and slit are gone); every front vertex there moves along its ray onto it, the slit's walls too
    (up to `deep` behind the outer skin; deeper is the neck under the jaw), then the moved vertices are relaxed
    over the surface `relax` times (the slit's folded walls spread out) and put back on it. The rest is untouched."""
    C = Vector(centre)
    az, el, R = radial_map(make_bvh(head), C)
    valid = ~np.isnan(R)
    A, E = np.meshgrid(az, el)
    Rf = np.where(valid, R, 0.0)
    PX, PY, PZ = (C.x + Rf * np.sin(A) * np.cos(E), C.y - Rf * np.cos(A) * np.cos(E), C.z + Rf * np.sin(E))
    reg = [muzzle_region(m)]
    y0 = m["dish"]["y_valley"]

    def front(y):  # the muzzle's front only: the jaw's sides and the neck under it match the region's x, z too
        t = np.clip((y - (y0 + 0.06)) / 0.08, 0.0, 1.0)
        return 1.0 - t * t * (3.0 - 2.0 * t)

    wg = np.where(valid & (PY < 0.0), region_mask(reg, PX, PZ) * front(PY), 0.0)
    # only the cells joined to the muzzle's centre: the region's x, z also match the neck and the jaw's far sides
    comp = np.zeros_like(wg, dtype=bool)
    i0 = int(np.argmin(np.abs(az)))
    comp[int(np.argmax(wg[:, i0])), i0] = True  # the seed: straight ahead, the region's core
    comp &= wg > 0.0
    for _ in range(400):
        grown = comp.copy()
        grown[1:] |= comp[:-1]
        grown[:-1] |= comp[1:]
        grown[:, 1:] |= comp[:, :-1]
        grown[:, :-1] |= comp[:, 1:]
        grown &= wg > 0.0
        if (grown == comp).all():
            break
        comp = grown
    if not comp.any():
        raise RuntimeError("the muzzle's centre is outside its region")
    T = thin_plate_fill(R, comp, (az[1] - az[0]) * np.cos(el), float(el[1] - el[0]))
    T = np.where(valid, T, 0.0)
    me = head.data
    nv = len(me.vertices)
    co = np.empty(nv * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(nv, 3)
    c = np.array(centre)

    def polar(q):
        p = q - c
        r = np.linalg.norm(p, axis=1)
        return p, r, np.arctan2(p[:, 0], -p[:, 1]), np.arcsin(np.clip(p[:, 2] / r, -1.0, 1.0))

    _, rv, a, e = polar(co)
    inside = (co[:, 1] < 0.0) & (a >= az[0]) & (a <= az[-1]) & (e >= el[0]) & (e <= el[-1])
    k = np.where(inside, region_mask(reg, co[:, 0], co[:, 2]) * front(co[:, 1]), 0.0)
    k = k * np.clip(grid_at_v(az, el, comp.astype(float), a, e), 0.0, 1.0)
    behind = grid_at_v(az, el, Rf, a, e) - rv
    t = np.clip((behind - 0.6 * deep) / (0.4 * deep), 0.0, 1.0)
    k = k * (1.0 - t * t * (3.0 - 2.0 * t))
    inv, nw, ea, eb = welded_edges(me, co)
    cnt = np.bincount(inv, minlength=nw)
    pos = np.stack([np.bincount(inv, weights=co[:, j], minlength=nw) for j in range(3)], 1) / cnt[:, None]
    wk = np.zeros(nw)
    np.maximum.at(wk, inv, k)
    deg = np.maximum(np.bincount(ea, minlength=nw), 1)
    mov = wk > 0.0

    def onto(q):  # the radius: the thin plate blended with the old outer skin by the weight
        qp, qr, qa, qe = polar(q)
        r = (1.0 - wk) * grid_at_v(az, el, Rf, qa, qe) + wk * grid_at_v(az, el, T, qa, qe)
        return c + qp / qr[:, None] * r[:, None]

    start = pos.copy()
    pos[mov] = onto(pos)[mov]
    for _ in range(relax):
        mean = np.stack([np.bincount(ea, weights=pos[eb, j], minlength=nw) for j in range(3)], 1) / deg[:, None]
        pos[mov] = (pos + 0.5 * wk[:, None] * (mean - pos))[mov]
        pos[mov] = onto(pos)[mov]
    me.vertices.foreach_set("co", pos[inv].ravel())
    me.update()
    shift = np.linalg.norm(pos - start, axis=1)
    return {"moved": int(mov.sum()), "max_shift": round(float(shift.max()), 4),
            "max_behind": round(float(behind[k > 0].max()) if (k > 0).any() else 0.0, 4),
            "region": [round(float(v), 4) for v in reg[0]], "cells": int(comp.sum()), "relax": relax}


def fill_recesses(head, bvh, m: dict, centre=(0.0, 0.1, 0.1), sigma: float = 0.05, iters: int = 100,
                  tol: float = 0.08, max_rise: float = 0.3, dish_rise: float = 0.06, flush: bool = False,
                  relax: int = 12) -> dict:
    """Fills the eye sockets and the mouth dish flush, radially from a point inside the head: the outer radius map
    R(azimuth, elevation) is closed (env = max(env, blur(env)) repeated: hollows rise to a smooth surface, convex skin
    stays where it is), applied only inside soft masks around the two sockets and the dish; the vertices there move
    outward along their ray onto it (a front-only move left the sockets' side walls visible from three-quarter). The
    rest of the head is untouched.
    flush (step 3c): the sockets' undercut walls rise too (left behind, they folded into a dark crease along the old
    rim), and the moved skin's radius is relaxed `relax` times toward its neighbours' (no step, no crease)."""
    C = Vector(centre)
    az, el, R = radial_map(bvh, C)
    valid = ~np.isnan(R)
    inner = float(np.nanmin(R))
    env = np.where(valid, R, inner)
    step = float(az[1] - az[0])
    for _ in range(iters):
        env = np.maximum(env, gauss(env, sigma / step))
    A, E = np.meshgrid(az, el)
    Rf = np.where(valid, R, 0.0)
    PX, PY, PZ = (C.x + Rf * np.sin(A) * np.cos(E), C.y - Rf * np.cos(A) * np.cos(E), C.z + Rf * np.sin(E))
    regions = face_regions(m)
    d = m["dish"]

    def mask(x, z, only=None):
        return region_mask(regions, x, z, only)

    w = np.where(valid & (PY < 0.0), mask(PX, PZ), 0.0)
    moved, worst = 0, 0.0
    soft = {}  # step 3c: vertex -> how much its radius relaxes
    for v in head.data.vertices:
        p = v.co - C
        rv = p.length
        e = math.asin(max(-1.0, min(1.0, p.z / rv)))
        a = math.atan2(p.x, -p.y)
        if not (az[0] <= a <= az[-1] and el[0] <= e <= el[-1]):
            continue
        # the vertex itself must lie in a region too: under the jaw a ray's outer skin is the chin, not the neck
        k = grid_at(az, el, w, a, e) * float(mask(v.co.x, v.co.z)) if v.co.y < 0.0 else 0.0
        socket = float(max(mask(v.co.x, v.co.z, 0), mask(v.co.x, v.co.z, 1))) > 0.0
        if not socket:  # the dish is shallow: no lift below the lower lip (the jaw's corners grew tabs) nor over cap
            k *= G.smoothstep(d["z_lower"] - 0.08, d["z_lower"] - 0.02, v.co.z)
        if k <= 0.0:
            continue
        target = grid_at(az, el, env, a, e)
        behind = grid_at(az, el, Rf, a, e) - rv  # how far under the outer skin (undercuts inside a socket)
        if not (flush and socket):
            k *= 1.0 - G.smoothstep(0.5 * tol, tol, behind)
        if flush:
            soft[v.index] = k
        if rv < target and k > 0.0:
            dr = k * min(target - rv, max_rise if socket else dish_rise)
            v.co = C + p * ((rv + dr) / rv)
            moved += 1
            worst = max(worst, dr)
    if flush and soft:
        me = head.data
        nv = len(me.vertices)
        co = np.empty(nv * 3)
        me.vertices.foreach_get("co", co)
        co = co.reshape(nv, 3)
        inv, nw, a, b = welded_edges(me, co)
        co = co - np.array(centre)
        deg = np.maximum(np.bincount(a, minlength=nw), 1)
        wv = np.zeros(nv)
        wv[list(soft)] = np.clip(np.array(list(soft.values())) * 2.0, 0.0, 1.0)
        wk = np.zeros(nw)
        np.maximum.at(wk, inv, wv)
        rad_v = np.linalg.norm(co, axis=1)
        dirs = co / rad_v[:, None]
        rad = np.bincount(inv, weights=rad_v, minlength=nw) / np.bincount(inv, minlength=nw)
        for _ in range(relax):
            mean = np.bincount(a, weights=rad[b], minlength=nw) / deg
            rad = rad + wk * (np.maximum(mean, rad) - rad)  # relax outward only: hollows close, skin never sinks
        me.vertices.foreach_set("co", (dirs * rad[inv][:, None] + np.array(centre)).ravel())
    head.data.update()
    return {"moved": moved, "max_rise": round(worst, 4), "sigma": sigma, "iters": iters, "centre": list(centre)}


# ---------------------------------------------------------------- materials
def clay_material(name: str, rgb, rough: float = 0.55):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Roughness"].default_value = rough
    return m


def srgb_to_lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def skin_colour(head, sock: dict) -> tuple:
    """The median skin colour on a ring around a socket, from the head's base-colour texture (linear)."""
    mat = head.data.materials[0]
    img = None
    for n in mat.node_tree.nodes:
        if n.type == "TEX_IMAGE" and any(l.to_socket.name == "Base Color" for l in n.outputs[0].links):
            img = n.image
    small = img.copy()
    small.scale(512, 512)
    px = np.empty(512 * 512 * 4, dtype=np.float32)
    small.pixels.foreach_get(px)
    px = px.reshape(512, 512, 4)
    uv = head.data.uv_layers.active.data
    cols = []
    for poly in head.data.polygons:
        c = poly.center
        if c.y < sock["rim_y"] + 0.05 and 1.15 * sock["rim"] < math.hypot(c.x - sock["cx"], c.z - sock["cz"]) < 1.5 * sock["rim"]:
            u, v = uv[poly.loop_indices[0]].uv
            cols.append(px[min(int(v % 1 * 512), 511), min(int(u % 1 * 512), 511), :3])
    med = np.median(np.array(cols), axis=0)
    bpy.data.images.remove(small)
    log("skin sample", len(cols), "srgb", med.round(3).tolist())
    return tuple(srgb_to_lin(float(c)) for c in med)


def eye_material() -> bpy.types.Material:
    w, h = 1024, 512
    img = bpy.data.images.new("t1_eyeball", w, h)
    px = np.zeros((h, w, 4), dtype=np.float32)
    for j in range(h):
        v = 1.0 - (j + 0.5) / h
        for i in range(0, w, 1):
            px[j, i, :3] = PG.eye_pixel(v, (i + 0.5) / w, EYE_SPEC)
    px[..., 3] = 1.0
    img.pixels.foreach_set(px.ravel())
    img.file_format = "PNG"
    img.pack()
    m = bpy.data.materials.new("t1_eyeball")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = img
    t.interpolation = "Cubic"
    nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.12
    return m


# ---------------------------------------------------------------- built pieces
def frame_axes(gaze: Vector):
    f = gaze.normalized()
    up = Vector((0, 0, 1))
    u = (up - up.dot(f) * f).normalized()
    s = f.cross(u)  # the lids use psi symmetrically, so the side axis's sign does not matter
    return f, s, u


def new_object(name: str, bm, mat, origin: Vector):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.transform(Matrix.Translation(-origin))
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    o.location = origin
    me.materials.append(mat)
    return o


def eyeball(name: str, centre: Vector, r: float, gaze: Vector, mat):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=64, radius=r)
    uvl = bm.loops.layers.uv.new("UVMap")
    for face in bm.faces:
        us = []
        for lp in face.loops:
            p = lp.vert.co.normalized()
            u = (math.atan2(p.y, p.x) / (2 * math.pi)) % 1.0
            v = math.acos(max(-1.0, min(1.0, p.z))) / math.pi
            us.append([u, 1.0 - v])
        umax = max(a[0] for a in us)
        for a in us:
            if umax - a[0] > 0.5:
                a[0] += 1.0
        for lp, a in zip(face.loops, us):
            lp[uvl].uv = a
    # local +Z -> gaze, local +X -> the head's +X (so the glint sits upper left from the front on both eyes)
    f = gaze.normalized()
    x = Vector((1, 0, 0))
    x = (x - x.dot(f) * f).normalized()
    y = f.cross(x)
    rot = Matrix((x, y, f)).transposed().to_4x4()
    bm.transform(rot)
    bm.transform(Matrix.Translation(centre))
    return new_object(name, bm, mat, centre)


def lid_shell(name: str, centre: Vector, axes, r_in: float, t0: float, state: str, mat, mode: str = "ring"):
    """The lids of one state (G.lid_parts: upper and lower, or the upper only) as closed shells, subdivided (the free
    edge rolls)."""
    bm = bmesh.new()
    n_psi, n_phi, psi_half = 36, 28, math.radians(86.0)
    for upper in G.lid_parts(state, mode):
        edge, root = G.lid_span(state, upper)
        rin = r_in * (1.0 if upper else 0.985)
        grid_in, grid_out = [], []
        for j in range(n_phi + 1):
            # rows packed toward the free edge
            t = (j / n_phi) ** 1.6
            phi = edge + (root - edge) * t
            th = G.lid_thickness(phi, edge, t0)
            ri, ro = [], []
            for i in range(n_psi + 1):
                psi = -psi_half + 2 * psi_half * i / n_psi
                d = Vector(G.lid_dir(axes, math.radians(phi), psi))
                ri.append(bm.verts.new(centre + d * rin))
                ro.append(bm.verts.new(centre + d * (rin + th)))
            grid_in.append(ri)
            grid_out.append(ro)
        for j in range(n_phi):
            for i in range(n_psi):
                bm.faces.new((grid_out[j][i], grid_out[j][i + 1], grid_out[j + 1][i + 1], grid_out[j + 1][i]))
                bm.faces.new((grid_in[j][i], grid_in[j + 1][i], grid_in[j + 1][i + 1], grid_in[j][i + 1]))
        for j in (0, n_phi):
            for i in range(n_psi):
                bm.faces.new((grid_in[j][i], grid_in[j][i + 1], grid_out[j][i + 1], grid_out[j][i]))
        for i in (0, n_psi):
            for j in range(n_phi):
                bm.faces.new((grid_in[j][i], grid_out[j][i], grid_out[j + 1][i], grid_in[j + 1][i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = new_object(name, bm, mat, centre)
    mod = o.modifiers.new("subd", "SUBSURF")
    mod.levels = mod.render_levels = 2
    apply_modifiers(o)
    return o


def apply_modifiers(o):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    old = o.data
    o.modifiers.clear()
    o.data = me
    bpy.data.meshes.remove(old)


# ---------------------------------------------------------------- seated Meshy pieces
def decimate(o, ratio: float):
    mod = o.modifiers.new("dec", "DECIMATE")
    mod.ratio = ratio
    apply_modifiers(o)


def seat(o, bvh, width: float, x: float, z: float, bury: float, sink: float, tilt: float = 0.0):
    """Scales o (centred, facing -Y) to width, turns it by tilt about +Y, turns its front to the skin's normal at
    (x, z), sinks `bury` of its depth behind the skin there, then pulls its back behind the skin (G.seat_y)."""
    me = o.data
    co = np.array([v.co[:] for v in me.vertices])
    me.transform(Matrix.Translation(Vector(-(co.min(0) + co.max(0)) / 2)))
    k = width / float(np.ptp(co[:, 0]))
    depth = float(np.ptp(co[:, 1])) * k
    loc, nrm = skin_hit(bvh, x, z)
    n = nrm.normalized()
    if n.y > 0:
        n = -n
    align = Vector((0, -1, 0)).rotation_difference(n).to_matrix().to_4x4()
    me.transform(Matrix.Diagonal((k, k, k, 1.0)))
    me.transform(Matrix.Rotation(tilt, 4, "Y"))
    me.transform(align)
    me.transform(Matrix.Translation(loc - n * (depth * (0.5 - bury))))
    me.update()
    frac = (co[:, 1] - co[:, 1].min()) / max(float(np.ptp(co[:, 1])), 1e-9)
    moved = 0
    for v in me.vertices:
        w = G.seat_weight(v.normal.y, float(frac[v.index]))
        if w <= 0.0:
            continue
        hit, _ = skin_hit(bvh, v.co.x, v.co.z)
        y = G.seat_y(v.co.y, hit.y if hit is not None else None, w, sink)
        if y != v.co.y:
            v.co.y = y
            moved += 1
    me.update()
    return {"k": k, "depth": depth, "moved": moved, "at": list(loc), "frac": frac}


def float_gap(o, bvh, frac) -> float:
    """The largest distance a seated piece's back vertex stays in front of the skin (0 = none floats)."""
    worst = 0.0
    for v in o.data.vertices:
        if v.index >= len(frac) or G.seat_weight(v.normal.y, float(frac[v.index])) < 0.99:
            continue
        hit, _ = skin_hit(bvh, v.co.x, v.co.z)
        if hit is not None:
            worst = max(worst, hit.y - v.co.y)
    return worst


def cut_back(o, keep_frac: float):
    """Deletes the vertices of o (centred, facing -Y) behind keep_frac of its depth: the O mouth's back ball."""
    co = np.array([v.co[:] for v in o.data.vertices])
    y_cut = co[:, 1].min() + keep_frac * np.ptp(co[:, 1])
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y > y_cut], context="VERTS")
    bm.to_mesh(o.data)
    bm.free()


def throat(name: str, o, bvh, mat):
    """A dark disc behind the O's hole, just in front of the skin, joined into o."""
    co = np.array([v.co[:] for v in o.data.vertices])
    cx, cz = (co[:, 0].min() + co[:, 0].max()) / 2, (co[:, 2].min() + co[:, 2].max()) / 2
    r = 0.30 * np.ptp(co[:, 0])
    bm = bmesh.new()
    ring = []
    for a in range(48):
        t = 2 * math.pi * a / 48
        x, z = cx + r * math.cos(t), cz + r * 0.95 * math.sin(t)
        hit, _ = skin_hit(bvh, x, z)
        y = (hit.y if hit is not None else co[:, 1].max()) - 0.004
        ring.append(bm.verts.new((x, y, z)))
    hit, _ = skin_hit(bvh, cx, cz)
    mid = bm.verts.new((cx, hit.y - 0.004, cz))
    for a in range(48):
        bm.faces.new((mid, ring[(a + 1) % 48], ring[a]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    disc = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(disc)
    me.materials.append(mat)  # join maps it to a second slot of o
    bpy.ops.object.select_all(action="DESELECT")
    disc.select_set(True)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.join()


# ---------------------------------------------------------------- the kit
def build(raw: Path, mouth_w: float, eye_k: float, cache: dict | None = None, fill: bool = False,
          eye_scale: float = 1.0, eye_sink: float = 0.3, lids: str = "ring", repaint: Path | None = None,
          muzzle: bool = False, tag: str = "3c") -> dict:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    head = import_one(raw / "head" / "multi_image_to_3d-model.glb", "head")
    bvh = make_bvh(head)
    m = measure(head, bvh)
    filled = painted = smoothed = None
    if repaint is not None:  # before the fill: the regions are the old sockets' and dish's places
        painted = repaint_recesses(head, m, repaint, muzzle=muzzle, tag=tag)
        log("repaint", json.dumps(painted))
    if fill:
        filled = fill_recesses(head, bvh, m, flush=repaint is not None,
                               dish_rise=0.15 if repaint is not None else 0.06)
        log("fill", json.dumps(filled))
        if muzzle:  # step 3d: the built-in lips and slit smoothed into a flush muzzle
            smoothed = smooth_muzzle(head, m)
            log("muzzle", json.dumps(smoothed))
        bvh = make_bvh(head)
    log("measure", json.dumps(m["sockets"]), json.dumps(m["dish"]))
    skin = skin_colour(head, m["sockets"]["L"])
    clay = clay_material("t1_clay", skin, 0.5)
    lips = clay_material("t1_lips", tuple(c * 0.85 for c in skin), 0.45)
    dark = clay_material("t1_throat", THROAT, 0.6)
    eye_mat = eye_material()
    kit = {"head": head}
    for side in G.SIDES:
        s = m["sockets"][side]
        c = Vector(s["bowl_centre"])
        r = s["bowl_r"] * eye_k * eye_scale
        sgn = 1.0 if side == "L" else -1.0
        if fill:  # the ball sits on the flush skin, eye_sink of its radius behind it along the skin's normal
            loc, nrm = skin_hit(bvh, c.x, c.z)
            n = nrm.normalized() if nrm.y < 0 else -nrm.normalized()
            c = loc - n * (eye_sink * r)
        s["eye_centre"], s["eye_r"] = list(c), r  # the brows sit above this ball
        gaze = Vector((sgn * 0.12, -1.0, 0.0)).normalized()
        kit[f"eye_{side}"] = eyeball(f"eye_{side}", c, r, gaze, eye_mat)
        axes = frame_axes(gaze)
        for st in G.LID_STATES:
            lid_mat = head.data.materials[0] if repaint is not None else clay
            lid = lid_shell(f"lid_{side}_{st}", c, axes, r * 1.025, r * 0.055, st, lid_mat, lids)
            if repaint is not None:  # the lid wears the skin it covers: the head's texture at its nearest point
                skin_uv(lid, head, bvh)
            kit[f"lid_{side}_{st}"] = lid
    d = m["dish"]
    seats = {}
    for mouth in G.MOUTHS:
        name = f"mouth_{mouth}"
        o = import_one(raw / name / "image_to_3d-model.glb", name)
        decimate(o, 0.35)
        if mouth == "o":
            cut_back(o, 0.42)
        o.data.materials.clear()
        o.data.materials.append(lips)
        w = d["w"] * mouth_w * (0.8 if mouth == "o" else 1.0)
        seats[name] = seat(o, bvh, w, 0.0, d["cz"], 0.35, 0.006)
        if mouth == "o":
            throat("throat", o, bvh, dark)
            o = bpy.context.view_layer.objects.active
            o.name = name
        kit[name] = o
    for side in G.SIDES:
        s = m["sockets"][side]
        sgn = 1.0 if side == "L" else -1.0
        for pose in G.BROW_POSES:
            name = f"brow_{side}_{pose}"
            o = import_one(raw / "brow" / "image_to_3d-model.glb", name)
            decimate(o, 0.25)
            o.data.materials.clear()
            o.data.materials.append(clay)
            p = G.BROWS[pose]
            c, r = s["eye_centre"], s["eye_r"]
            # the brow keeps its step 2 length (eye_scale shrinks the eyes only); it sits above the ball it has
            seats[name] = seat(o, bvh, G.BROW_WIDTH * s["bowl_r"] * eye_k, c[0] - sgn * 0.08 * r,
                               c[2] + r * (G.BROW_BASE + p["lift"]),
                               0.4, 0.004, G.brow_tilt_rad(side, pose))
            kit[name] = o
    gaps = {n: round(float_gap(kit[n], bvh, seats[n]["frac"]), 4) for n in seats}
    log("seats", json.dumps({k: {"k": round(v["k"], 3), "moved": v["moved"]} for k, v in seats.items()}))
    log("float gaps", json.dumps(gaps))
    for n, o in kit.items():
        if n != "head":
            mw = o.matrix_world.copy()
            o.parent = head
            o.matrix_parent_inverse = Matrix.Identity(4)
            o.matrix_world = mw
    return {"kit": kit, "measure": m, "gaps": gaps, "fill": filled, "repaint": painted, "muzzle": smoothed}


# ---------------------------------------------------------------- render
def setup_render(w: int, h: int, samples: int):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    try:
        pr = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA", "HIP", "ONEAPI"):
            try:
                pr.compute_device_type = kind
                pr.get_devices()
                gpus = [d for d in pr.devices if d.type == kind]
                if gpus:
                    for d in pr.devices:
                        d.use = d.type == kind
                    sc.cycles.device = "GPU"
                    log("render device", kind)
                    break
            except TypeError:
                continue
    except Exception as e:  # noqa: BLE001 - CPU is the fallback
        log("render device CPU", e)
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    world = bpy.data.worlds.new("w")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.085, 0.085, 0.09, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
    sc.world = world
    for name, loc, power, size in (("key", (-2.6, -3.2, 2.8), 420.0, 2.8), ("fill", (3.0, -2.4, 0.6), 140.0, 3.5),
                                   ("rim", (1.8, 3.0, 2.6), 300.0, 2.0)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy, ld.size = power, size
        lo = bpy.data.objects.new(name, ld)
        sc.collection.objects.link(lo)
        lo.location = loc
        lo.rotation_euler = (Vector((0, 0, 0.2)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


def camera(name: str, target: Vector, yaw_deg: float, pitch_deg: float, height: float, lens: float = 85.0):
    cd = bpy.data.cameras.new(name)
    cd.lens, cd.sensor_fit, cd.sensor_height = lens, "VERTICAL", 24.0
    dist = (height / 2) / math.tan(math.atan(12.0 / lens))
    a, p = math.radians(yaw_deg), math.radians(pitch_deg)
    loc = target + Vector((dist * math.sin(a) * math.cos(p), -dist * math.cos(a) * math.cos(p), dist * math.sin(p)))
    co = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(co)
    co.location = loc
    co.rotation_euler = (target - loc).to_track_quat("-Z", "Y").to_euler()
    return co


def show(kit: dict, nodes, gaze_deg: float = 0.0, rest: dict | None = None):
    for n, o in kit.items():
        o.hide_render = n not in nodes
    for side in G.SIDES:
        e = kit[f"eye_{side}"]
        e.matrix_world = Matrix.Translation(rest[side].to_translation()) @ Matrix.Rotation(
            math.radians(gaze_deg), 4, "Z") @ Matrix.Translation(-rest[side].to_translation()) @ rest[side]


def render(path: Path, cam):
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.filepath = str(path)
    sc.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)


# ---------------------------------------------------------------- sheets (numpy)
def load_rgb(path: Path) -> np.ndarray:
    img = bpy.data.images.load(str(path))
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)[::-1, :, :3]  # top row first


def resize(a: np.ndarray, w: int, h: int) -> np.ndarray:
    k = max(1, int(min(a.shape[0] / h, a.shape[1] / w)))
    if k > 1:
        hh, ww = a.shape[0] // k * k, a.shape[1] // k * k
        a = a[:hh, :ww].reshape(hh // k, k, ww // k, k, 3).mean(axis=(1, 3))
    ys = np.clip(((np.arange(h) + 0.5) * a.shape[0] / h - 0.5).round().astype(int), 0, a.shape[0] - 1)
    xs = np.clip(((np.arange(w) + 0.5) * a.shape[1] / w - 0.5).round().astype(int), 0, a.shape[1] - 1)
    return a[ys][:, xs]


def save_jpg(a: np.ndarray, path: Path):
    h, w = a.shape[:2]
    img = bpy.data.images.new("sheet", w, h)
    px = np.ones((h, w, 4), dtype=np.float32)
    px[..., :3] = a[::-1]
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw = str(path)
    img.file_format = "JPEG"
    img.save(quality=90)
    bpy.data.images.remove(img)


def sheet(cells: list, cols: int, cw: int, ch: int, path: Path):
    rows = (len(cells) + cols - 1) // cols
    out = np.full((rows * ch, cols * cw, 3), 0.18, dtype=np.float32)
    for n, a in enumerate(cells):
        if a is None:
            continue
        r, c = divmod(n, cols)
        out[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw] = resize(a, cw, ch)
    save_jpg(out, path)


_GLYPHS = {"Q": ("010", "101", "101", "110", "011"), "J": ("001", "001", "001", "101", "010"),
           "/": ("001", "001", "010", "100", "100"), ".": ("000", "000", "000", "000", "010"),
           ",": ("000", "000", "000", "010", "100"), "(": ("010", "100", "100", "100", "010"),
           ")": ("010", "001", "001", "001", "010")}


def stamp(a: np.ndarray, text: str, x: int, y: int, px: int = 3, rgb=(0.92, 0.92, 0.92)):
    """Writes text in the 3 x 5 block font (prop_geom's, a few glyphs added) into a (top row first) at (x, y)."""
    from prop_geom import _FONT
    font = {**_FONT, **_GLYPHS}
    for i, ch in enumerate(text.upper()):
        for r, row in enumerate(font.get(ch, font[" "])):
            for c, bit in enumerate(row):
                if bit == "1":
                    x0, y0 = x + (i * 4 + c) * px, y + r * px
                    a[y0:y0 + px, x0:x0 + px] = rgb


def labelled_sheet(rows: list, cols: int, cw: int, ch: int, path: Path, band: int = 22):
    """rows: (label, cells); each row a label band above its cells (None = an empty cell)."""
    out = np.full((len(rows) * (ch + band), cols * cw, 3), 0.18, dtype=np.float32)
    for r, (label, cells) in enumerate(rows):
        y = r * (ch + band)
        out[y:y + band] = 0.08
        stamp(out, label, 6, y + (band - 15) // 2)
        for c, a in enumerate(cells[:cols]):
            if a is not None:
                out[y + band:y + band + ch, c * cw:(c + 1) * cw] = resize(a, cw, ch)
    save_jpg(out, path)


def grey_material() -> bpy.types.Material:
    return clay_material("t1_grey", (0.42, 0.42, 0.42), 0.6)


def bare_proof(kit: dict, raw: Path, out: Path, cams: dict, sheet_path: Path, tag: str = "3c"):
    """The geometry alone: the filled head without pieces beside the original Meshy head, plain grey, front and
    three-quarter, the same light (step 3c)."""
    head = kit["head"]
    grey = grey_material()
    for o in kit.values():
        o.hide_render = o is not head
    mats = list(head.data.materials)
    head.data.materials.clear()
    head.data.materials.append(grey)
    shots = {}
    for view, cam in cams.items():
        shots[("filled", view)] = p = out / f"bare_filled_{view}.png"
        render(p, cam)
    head.hide_render = True
    orig = import_one(raw / "head" / "multi_image_to_3d-model.glb", "head_meshy")
    orig.data.materials.clear()
    orig.data.materials.append(grey)
    for view, cam in cams.items():
        shots[("meshy", view)] = p = out / f"bare_meshy_{view}.png"
        render(p, cam)
    bpy.data.objects.remove(orig)
    head.hide_render = False
    head.data.materials.clear()
    for mt in mats:
        head.data.materials.append(mt)
    cells = [load_rgb(shots[k]) for k in (("meshy", "front"), ("meshy", "q"), ("filled", "front"), ("filled", "q"))]
    labelled_sheet([(f"GREY, NO TEXTURE, NO PIECES. LEFT - MESHY HEAD FRONT, 3/4. RIGHT - STEP {tag.upper()} HEAD "
                     "FRONT, 3/4",
                     cells)], 4, 320, 320, sheet_path)


# ---------------------------------------------------------------- main
def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--grid", action="store_true")
    floats = lambda t: [float(x) for x in t.split(",")]  # noqa: E731
    ap.add_argument("--grid-mouth", type=floats, default=[0.85, 1.0, 1.15], help="mouth widths (x the dish's)")
    ap.add_argument("--grid-eye", type=floats, default=[0.95, 1.05, 1.15], help="eyeball scales (x the bowl's)")
    ap.add_argument("--grid-expr", default="rest")
    ap.add_argument("--mouth-w", type=float, default=1.45)
    ap.add_argument("--eye-k", type=float, default=1.15)
    ap.add_argument("--ref-approved", type=Path, help="the approved 2D expressions (3 x 2: rest smile sad / angry surprised talk)")
    ap.add_argument("--ref-h2", type=Path, help="H2's ch_expr4 (2 x 2: rest smile / sad surprised)")
    ap.add_argument("--samples", type=int, default=48)
    ap.add_argument("--fill", action="store_true", help="step 3: fill the sockets and the mouth dish flush")
    ap.add_argument("--eye-scale", type=float, default=1.0, help="eyeballs and lids x this (step 3: 0.75)")
    ap.add_argument("--eye-sink", type=float, default=0.3, help="with --fill: the ball's centre this x r behind the skin")
    ap.add_argument("--ref-step2", type=Path, help="step 2's render folder: its front row replaces H2's row")
    ap.add_argument("--sheet", type=Path, help="the comparison sheet's path (default <out>/step2_compare.jpg)")
    ap.add_argument("--glb-name", default="t1_chameleon_kit.glb")
    ap.add_argument("--lids", choices=G.LID_MODES, default="ring", help="step 3c: upper (no ring around the ball)")
    ap.add_argument("--repaint", action="store_true", help="step 3c: paint the old sockets and dish with the skin")
    ap.add_argument("--muzzle", action="store_true", help="step 3d: the built-in lips and slit smoothed flush")
    ap.add_argument("--tag", default="3c", help="the step's name in labels and texture names (3d)")
    ap.add_argument("--bare", type=Path, help="step 3c: the grey geometry proof sheet's path")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    if a.grid:
        cells = []
        for mw in a.grid_mouth:
            for ek in a.grid_eye:
                b = build(a.raw, mw, ek)
                kit, m = b["kit"], b["measure"]
                rest = {s: kit[f"eye_{s}"].matrix_world.copy() for s in G.SIDES}
                setup_render(320, 320, 24)
                tgt = Vector((0.0, -0.4, (m["dish"]["cz"] + m["sockets"]["L"]["cz"]) / 2 + 0.05))
                show(kit, G.expressions()[a.grid_expr]["nodes"], 0.0, rest)
                for view, yaw in (("f", 0.0), ("q", 35.0)):
                    p = a.out / f"grid_m{mw}_e{ek}_{view}.png"
                    render(p, camera(f"c{view}", tgt, yaw, 4.0, 1.25))
                    cells.append(load_rgb(p))
                log("grid", mw, ek, json.dumps(b["gaps"]))
        sheet(cells, 2 * len(a.grid_eye), 1280 // (2 * len(a.grid_eye)), 1280 // (2 * len(a.grid_eye)), a.out / "grid.jpg")
        return
    b = build(a.raw, a.mouth_w, a.eye_k, fill=a.fill, eye_scale=a.eye_scale, eye_sink=a.eye_sink, lids=a.lids,
              repaint=a.out if a.repaint else None, muzzle=a.muzzle, tag=a.tag)
    kit, m = b["kit"], b["measure"]
    rest = {s: kit[f"eye_{s}"].matrix_world.copy() for s in G.SIDES}
    setup_render(512, 512, a.samples)
    sL = m["sockets"]["L"]
    tgt = Vector((0.0, 0.0, 0.0))
    cams = {"front": camera("front", tgt, 0.0, 3.0, 2.05), "q": camera("q", tgt, 35.0, 3.0, 2.05)}
    exprs = G.expressions()
    shots = {}
    for e, spec in exprs.items():
        show(kit, spec["nodes"], spec["gaze_deg"], rest)
        for view in (("front", "q") if a.bare or e in ("rest", "smile", "sad", "surprised", "angry") else ("front",)):
            p = a.out / f"{e}_{view}.png"
            render(p, cams[view])
            shots[(e, view)] = p
    bpy.context.scene.render.resolution_x = bpy.context.scene.render.resolution_y = 768
    show(kit, exprs["rest"]["nodes"], 0.0, rest)
    close = {"mouth": camera("cm", Vector((0.0, -0.45, m["dish"]["cz"])), 55.0, -8.0, 0.55),
             "socket": camera("cs", Vector((sL["cx"], sL["rim_y"], sL["cz"])), 42.0, 10.0, 0.6)}
    for k, c in close.items():
        render(a.out / f"close_{k}.png", c)
    sheet([load_rgb(a.out / f"close_{k}.png") for k in close], 2, 640, 640, a.out / "step2_closeups.jpg")
    five = ("rest", "smile", "sad", "surprised", "angry")
    if a.bare:  # step 3c: the grey proof and the labelled sheet
        bare_proof(kit, a.raw, a.out, cams, a.bare, a.tag)
    if a.muzzle and a.bare and a.ref_approved and a.ref_step2:  # step 3d: 2D, the step before's front, this step
        approved = load_rgb(a.ref_approved)
        ah, aw = approved.shape[0] // 2, approved.shape[1] // 3
        ap_cells = [approved[r * ah:(r + 1) * ah, c * aw:(c + 1) * aw] for r, c in ((0, 0), (0, 1), (0, 2), (1, 1), (1, 0))]
        tg = a.tag.upper()
        rows = [("2D APPROVED - REST, SMILE, SAD, SURPRISED, ANGRY", ap_cells),
                ("STEP 3C FRONT (BEFORE) - BUILT-IN LIPS AND SLIT UNDER THE MOUTH",
                 [load_rgb(a.ref_step2 / f"{e}_front.png") for e in five]),
                (f"STEP {tg} FRONT - SMOOTH FLUSH MUZZLE, SAME MOUTH PIECES", [load_rgb(shots[(e, "front")]) for e in five]),
                (f"STEP {tg} 3/4", [load_rgb(shots[(e, "q")]) for e in five]),
                (f"CLOSE-UPS - STEP {tg} MOUTH, STEP 3C MOUTH, STEP {tg} EYE. STEP {tg} BLINK FRONT, 3/4",
                 [load_rgb(a.out / "close_mouth.png"), load_rgb(a.ref_step2 / "close_mouth.png"),
                  load_rgb(a.out / "close_socket.png"), load_rgb(shots[("blink", "front")]),
                  load_rgb(shots[("blink", "q")])])]
        labelled_sheet(rows, 5, 256, 256, a.sheet or a.out / f"step{a.tag}_compare.jpg")
    elif a.bare and a.ref_approved and a.ref_step2:
        approved = load_rgb(a.ref_approved)
        ah, aw = approved.shape[0] // 2, approved.shape[1] // 3
        ap_cells = [approved[r * ah:(r + 1) * ah, c * aw:(c + 1) * aw] for r, c in ((0, 0), (0, 1), (0, 2), (1, 1), (1, 0))]
        g3 = ("gaze_left", "gaze_right", "blink")
        rows = [("2D APPROVED - REST, SMILE, SAD, SURPRISED, ANGRY", ap_cells),
                ("STEP 3B FRONT (BEFORE)", [load_rgb(a.ref_step2 / f"{e}_front.png") for e in five]),
                ("STEP 3C FRONT - NO RECESSES, UPPER LIDS, REPAINTED SKIN", [load_rgb(shots[(e, "front")]) for e in five]),
                ("STEP 3C 3/4", [load_rgb(shots[(e, "q")]) for e in five]),
                ("STEP 3C FRONT - GAZE LEFT, GAZE RIGHT, BLINK. CLOSE-UPS - MOUTH, EYE",
                 [load_rgb(shots[(e, "front")]) for e in g3] + [load_rgb(a.out / "close_mouth.png"),
                                                                load_rgb(a.out / "close_socket.png")]),
                ("STEP 3C 3/4 - GAZE LEFT, GAZE RIGHT, BLINK. STEP 3B CLOSE-UPS - MOUTH, EYE",
                 [load_rgb(shots[(e, "q")]) for e in g3] + [load_rgb(a.ref_step2 / "close_mouth.png"),
                                                            load_rgb(a.ref_step2 / "close_socket.png")])]
        labelled_sheet(rows, 5, 256, 256, a.sheet or a.out / "step3c_compare.jpg")
    elif a.ref_approved and (a.ref_h2 or a.ref_step2):
        approved = load_rgb(a.ref_approved)
        ah, aw = approved.shape[0] // 2, approved.shape[1] // 3
        ap_cells = [approved[r * ah:(r + 1) * ah, c * aw:(c + 1) * aw] for r, c in ((0, 0), (0, 1), (0, 2), (1, 1), (1, 0))]
        if a.ref_step2:  # step 3: step 2's front row instead of H2's
            h2_cells = [load_rgb(a.ref_step2 / f"{e}_front.png") for e in five]
        else:
            h2 = load_rgb(a.ref_h2)
            hh, hw = h2.shape[0] // 2, h2.shape[1] // 2
            h2_cells = [h2[r * hh:(r + 1) * hh, c * hw:(c + 1) * hw] for r, c in ((0, 0), (0, 1), (1, 0), (1, 1))] + [None]
        cells = ap_cells + h2_cells + [load_rgb(shots[(e, "front")]) for e in five] + \
            [load_rgb(shots[(e, "q")]) for e in five] + \
            [load_rgb(shots[("gaze_left", "front")]), load_rgb(shots[("gaze_right", "front")]),
             load_rgb(shots[("blink", "front")]), load_rgb(a.out / "close_mouth.png"),
             load_rgb(a.out / "close_socket.png")]
        sheet(cells, 5, 256, 256, a.sheet or a.out / "step2_compare.jpg")
    # the kit GLB: every node, the rest set marked visible
    show(kit, set(kit), 0.0, rest)
    for n, o in kit.items():
        o["prime_visible_rest"] = n in exprs["rest"]["nodes"]
    for o in list(bpy.data.objects):
        if o.type in ("CAMERA", "LIGHT"):
            bpy.data.objects.remove(o)
    glb = a.out / a.glb_name
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format="GLB", use_visible=False, export_extras=True,
                              export_apply=False, export_yup=True, export_image_format="AUTO",
                              export_materials="EXPORT")
    centres = {s: list(rest[s].to_translation()) for s in G.SIDES}
    doc = {"glb": glb.name, "nodes": G.node_names(), "rest": "rest", "expressions": exprs,
           "gaze": {"nodes": ["eye_L", "eye_R"], "axis": "the head's up axis (glTF +Y)",
                    "pivot": "each eye node's origin (the ball's centre)", "eye_centres_blender": centres},
           "visibility": "glTF has no hidden flag: every node is in the file; nodes' extras.prime_visible_rest "
                         "marks the rest set", "measure": m, "float_gaps": b["gaps"], "fill": b["fill"],
           "lids": a.lids, "repaint": b["repaint"], "muzzle": b["muzzle"]}
    (a.out / "t1_expressions.json").write_text(json.dumps(doc, indent=1), encoding="utf-8", newline="\n")
    log("done", glb)


if __name__ == "__main__":
    main()
