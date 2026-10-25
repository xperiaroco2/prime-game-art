"""The static head's liveliness proof (art #196, lively), inside headless Blender for numpy and its BVH only: the
merged static GLB is never re-exported, its bytes stay as they are and a minimal skin is added beside them.

1. The painted eyes: every eye triangle is sampled densely (15 points each) against the albedo and the tint mask (R 0
   on the eyes); each sample is pupil, iris, sclera or skin. The iris and the pupil are fitted as caps on the build's
   eye sphere (a linear least squares on their edge samples, edges next to the lids left out); the iris colour is a
   radial profile of its samples' medians; a painted catch light is measured inside the cap.
2. The clean sclera: the iris and pupil texels (dilated) are painted out with a push-pull fill from the sclera
   texels around them; `<name>_sclera.png`, the whole albedo with the eyes white, so the shader's own iris can move.
3. The lid clamp: for a grid of gaze offsets the iris and pupil discs are tested with rays from outside the eye
   sphere: a direction is open when its ray meets an eye triangle first. The allowed offsets keep the rest's open
   share; their reach along each axis is the clamp ellipse's limits.
4. The eye pit (2026-10-23): Meshy dented each eyeball at its painted pupil (1 to 2 % of the radius); the old
   iris's travel region (TRAVEL) is projected onto a sphere fitted to the eyeball's open front, faded out toward
   the lids (no vertex a lid or socket triangle shares moves), normals turned with the geometry; `eye_residual.png`.
   The sclera fill takes only real sclera texels (the eye mask's R < 0.5 also holds the atlas's black gutter, which
   the first fill pulled in: a dark disc, read as a pit), and the painted catch light goes with the iris.
5. The skin: Chest (the bust's root), Neck, Head (no bone in the face), Crest1-3 (the crest's spring chain), weights by
   height through the neck only and along the crest only (alien_lively_geom); `<name>_lively.glb`, `lively.json`.

    blender -b --python tools/blender/alien_lively_build.py -- --glb <static GLB> --albedo PNG --mask PNG
        --build <build.json> --out DIR [--name chameleon] [--no-pit-fix] [--neck y0,y1] [--crest-root 0.45] [--blade 0.10,0.16]
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
from mathutils.kdtree import KDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_lively_geom as G  # noqa: E402

TRAVEL = math.radians(42.0)  # the eye pit fix: the iris's travel (the 25-degree gaze cap + the iris + a margin)
FADE = math.radians(58.0)  # and its fade-out
LID_TEAL_V = 0.45  # v4: a teal texel this bright or brighter is lid skin, left as it is; darker is old pupil
GUTTER_PX = 4  # v4: the eye islands' gutter ring filled with the sclera
MOVE_CAP = 0.035  # v4: no eyeball vertex moves more than this share of the eye radius (the dent is at most 3 %)
ROOM_SHARE = 0.5  # nor more than half its distance to the nearest lid or socket triangle
PUPIL_V = 0.12  # the pupil: darker than this (0.22 took the iris's dark inner ring: a pupil too big at rest)
BARY = [(i / 4, j / 4) for i in range(5) for j in range(5 - i)]  # 15 points per triangle
RIM_LAMBDA, RIM_MU = 0.5, -0.53  # A3b: the rim's Taubin steps (lambda 0.5 cancels the alternate in-out step)
RIM_CAP = 0.08  # A3b: no rim vertex slides further than this share of the eye radius (the corners stay)
RIM_WELD_DEG = 45.0  # A3b: a rim position's copies share one normal when they are this close (a fold stays split)


def accessor(doc, binary, i):
    a = doc["accessors"][i]
    v = doc["bufferViews"][a["bufferView"]]
    n = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[a["type"]]
    dt = {5126: np.float32, 5125: np.uint32, 5123: np.uint16, 5121: np.uint8}[a["componentType"]]
    size = np.dtype(dt).itemsize * n
    stride = v.get("byteStride", size)
    start = v.get("byteOffset", 0) + a.get("byteOffset", 0)
    raw = np.frombuffer(bytes(binary), np.uint8, count=stride * (a["count"] - 1) + size, offset=start)
    rows = np.lib.stride_tricks.as_strided(raw, (a["count"], size), (stride, 1))
    return np.frombuffer(rows.copy().tobytes(), dt).reshape(a["count"], n).astype(np.float64 if dt == np.float32 else np.int64)


def load_png(path):
    img = bpy.data.images.load(str(path))
    img.colorspace_settings.name = "Non-Color"  # the stored values as they are
    w, h = img.size
    a = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(h, w, 4)[::-1, :, :3].copy()  # rows top first, like glTF's UV v


def hsv(c):
    mx, mn = c.max(-1), c.min(-1)
    d = mx - mn
    s = np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0.0)
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    dd = np.maximum(d, 1e-6)
    h = np.where(mx == r, ((g - b) / dd) % 6.0, np.where(mx == g, (b - r) / dd + 2.0, (r - g) / dd + 4.0)) / 6.0
    return np.where(d > 1e-6, h, 0.0), s, mx


def dilate(m, k):
    for _ in range(k):
        p = np.pad(m, 1)
        m = p[1:-1, 1:-1] | p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
    return m


def blur(c):
    p = np.pad(c, ((1, 1), (1, 1), (0, 0)), mode="edge")
    return sum(p[i:i + c.shape[0], j:j + c.shape[1]] for i in range(3) for j in range(3)) / 9.0


def push_pull(col, w):
    """Fills where w == 0 from the weighted colours around (a push-pull pyramid, bilinear-ish upsampling)."""
    if min(w.shape) <= 2:
        s = w.sum()
        return np.broadcast_to((col * w[..., None]).sum((0, 1)) / max(s, 1e-6), col.shape).copy()
    h2, w2 = w.shape[0] // 2, w.shape[1] // 2
    cw = (col * w[..., None])[:h2 * 2, :w2 * 2]
    ww = w[:h2 * 2, :w2 * 2]
    cs = cw[0::2, 0::2] + cw[1::2, 0::2] + cw[0::2, 1::2] + cw[1::2, 1::2]
    ws = ww[0::2, 0::2] + ww[1::2, 0::2] + ww[0::2, 1::2] + ww[1::2, 1::2]
    coarse = push_pull(np.where(ws[..., None] > 0, cs / np.maximum(ws, 1e-6)[..., None], 0.0), np.minimum(ws, 1.0))
    up = blur(np.repeat(np.repeat(coarse, 2, 0), 2, 1))
    up = np.pad(up, ((0, w.shape[0] - up.shape[0]), (0, w.shape[1] - up.shape[1]), (0, 0)), mode="edge")
    a = np.clip(w, 0.0, 1.0)[..., None]
    return col * a + up * (1.0 - a)


def fit_cap(dirs):
    """(axis, angle) of the circle on the unit sphere through the directions: dirs . (axis / cos angle) = 1."""
    x, *_ = np.linalg.lstsq(dirs, np.ones(len(dirs)), rcond=None)
    n = np.linalg.norm(x)
    axis = x / n
    ang = math.acos(min(1.0, 1.0 / n))
    resid = np.degrees(np.arccos(np.clip(dirs @ axis, -1, 1))) - math.degrees(ang)
    return axis, ang, float(np.sqrt((resid ** 2).mean()))


def ring(axis, ang, n):
    f, s, u = (np.array(v) for v in G.eye_frame(tuple(axis)))
    return [f * math.cos(ang) + (s * math.cos(p) + u * math.sin(p)) * math.sin(ang)
            for p in np.linspace(0, 2 * math.pi, n, endpoint=False)]


def classify_eyeball(P, I, UV, alb, tri_eye, centres, r):
    """The eyeball triangles, one classification for eyeball_fix and the sclera fill (PR #303 review, minor 3): the
    mask's eye triangles, and the painted iris's triangles the mask calls skin (warm and saturated, near an eye)."""
    H, W = alb.shape[:2]
    uvc = UV[I].mean(1)
    th_, ts_, tv_ = hsv(alb[np.clip((uvc[:, 1] * H).astype(int), 0, H - 1), np.clip((uvc[:, 0] * W).astype(int), 0, W - 1)])
    iris_tri = (ts_ > 0.25) & (tv_ > 0.15) & ((th_ < 0.14) | (th_ > 0.92))
    near_t = np.minimum(*(np.linalg.norm(P[I].mean(1) - c, axis=1) for c in centres.values())) < 1.05 * r
    return tri_eye | (iris_tri & near_t)


def eyeball_fix(P, N, T, I, UV, alb, eyeball, centres, r, bead=False):
    """The eye pit: per eye, its eyeball vertices (every triangle of theirs an eye triangle) near the painted iris
    projected onto the sphere fitted to the eyeball's open front (G.pit_weight: full inside TRAVEL, none from FADE,
    faded in from the lid-shared vertices). bead (the axolotl's all-dark bead, no gaze): nothing is moved, the
    sphere is fitted to the whole eyeball. Then every eyeball vertex gets that sphere's radial normal (the faceted
    sclera under the upper lids, PR #303 review minor 2), faded in over 6 % of r from the lid line, and every TANGENT
    whose normal changed is made orthogonal to it again. Returns the new positions, normals and tangents, the report
    and the heat map's inputs."""
    H, W = alb.shape[:2]
    hue, sat, val = hsv(alb[np.clip((UV[:, 1] * H).astype(int), 0, H - 1), np.clip((UV[:, 0] * W).astype(int), 0, W - 1)])
    ve, vs = np.zeros(len(P), bool), np.zeros(len(P), bool)
    np.logical_or.at(ve, I[eyeball].ravel(), True)
    np.logical_or.at(vs, I[~eyeball].ravel(), True)
    shared = ve & vs
    P1 = P.copy()
    rep, views = {"eye_vertices": int(ve.sum()), "lid_shared_vertices": int(shared.sum())}, {}
    for side, c in centres.items():
        key = "left" if side > 0 else "right"
        near = np.linalg.norm(P - c, axis=1) < 1.3 * r
        sel = np.nonzero(ve & ~vs & near & (P[:, 0] * side > 0))[0]
        d = P[sel] - c
        dn = d / np.linalg.norm(d, axis=1)[:, None]
        # the painted iris's vertices: warm and saturated (a vertex on an island's edge can read the black gutter,
        # so dark alone is no sign), refined once to those within 30 degrees of their mean direction
        painted = (sat[sel] > 0.25) & (val[sel] > 0.15) & ((hue[sel] < 0.14) | (hue[sel] > 0.92))
        if bead:
            painted = np.ones(len(sel), bool)  # the bead's front: the whole eyeball
        if painted.sum() < 8:
            raise SystemExit(f"LIVELY pit: only {int(painted.sum())} painted iris vertices on the {key} eye")
        rest0 = dn[painted].mean(0)
        rest0 /= np.linalg.norm(rest0)
        painted &= dn @ rest0 > math.cos(math.radians(30))
        rest0 = dn[painted].mean(0)
        rest0 /= np.linalg.norm(rest0)
        th = np.arccos(np.clip(dn @ rest0, -1, 1))
        ia = float(np.percentile(th[painted], 90))
        # the sphere: fitted to the whole open front of the eyeball (60 degrees about the old iris), so the region the
        # procedural iris travels (the 25-degree gaze cap plus the iris, TRAVEL) is made that sphere, faded out to FADE
        ring = th < math.radians(60) if not bead else np.ones(len(sel), bool)
        if ring.sum() < 12:
            raise SystemExit(f"LIVELY pit: only {int(ring.sum())} sclera ring vertices on the {key} eye (iris {math.degrees(ia):.1f} deg)")
        cl, rl = G.fit_sphere(P[sel][ring].tolist())
        cl = np.array(cl)
        lid = P[shared & near]
        gap = np.sqrt(((P[sel][:, None, :] - lid[None, :, :]) ** 2).sum(-1)).min(1) if len(lid) else np.full(len(sel), 1.0)
        w = np.array([G.pit_weight(float(t), TRAVEL, FADE, float(g), 0.01 * r, 0.06 * r) for t, g in zip(th, gap)])
        # v4: each move capped at MOVE_CAP and at ROOM_SHARE of the vertex's distance to the nearest lid or socket
        # triangle of this eye (its surface, not only the shared vertices: v3's pull crossed one lid triangle)
        lid_t = np.nonzero(~eyeball & (np.linalg.norm(P[I].mean(1) - c, axis=1) < 1.4 * r))[0]
        lid_bvh = BVHTree.FromPolygons([Vector(v) for v in P], [tuple(int(x) for x in I[t]) for t in lid_t],
                                       all_triangles=True)
        room = np.array([lid_bvh.find_nearest(Vector(p))[3] for p in P[sel]])
        full = np.abs(np.linalg.norm(P[sel] - cl, axis=1) - rl)
        w0 = w
        w = np.array([G.capped_weight(float(k), float(f), float(m), ROOM_SHARE, MOVE_CAP * r) for k, f, m in zip(w, full, room)])
        if bead:
            w = np.zeros(len(sel))
        moved = np.array([G.project_on_sphere(tuple(p), tuple(cl), rl, float(k)) for p, k in zip(P[sel], w)])
        P1[sel] = moved

        def resid(Q):
            return (np.linalg.norm(Q - cl, axis=1) - rl) / rl * 100.0
        r0, r1 = resid(P[sel]), resid(moved)
        bins = {}
        for name, a, b in (("pupil", 0.0, 0.65 * ia), ("iris", 0.65 * ia, ia), ("travel", ia, TRAVEL),
                           ("fade", TRAVEL, FADE), ("outside", FADE, math.pi)):
            m = (th >= a) & (th < b)
            if m.any():
                bins[name] = {"vertices": int(m.sum()), "before_median_pct": round(float(np.median(r0[m])), 3),
                              "before_min_pct": round(float(r0[m].min()), 3),
                              "after_median_pct": round(float(np.median(r1[m])), 3),
                              "after_min_pct": round(float(r1[m].min()), 3)}
        mv = np.linalg.norm(moved - P[sel], axis=1)
        close = gap < 0.02 * r
        rep[key] = {"rest0": rest0.round(5).tolist(), "iris_angle0_deg": round(math.degrees(ia), 2),
                    "ring_sphere": {"centre": cl.round(5).tolist(), "r": round(rl, 5),
                                    "rms_pct": round(float(np.sqrt((r0[ring] ** 2).mean())), 3)},
                    "residual": bins, "moved": int((mv > 1e-7).sum()), "max_move_mm": round(float(mv.max()) * 1000, 3),
                    "lid_fade_share": round(float((w < 0.999)[th < TRAVEL].mean()), 4), "max_move_near_lid_mm": round(float(mv[close].max()) * 1000 if close.any() else 0.0, 4),
                    "min_gap_of_moved_mm": round(float(gap[mv > 1e-7].min()) * 1000, 3) if (mv > 1e-7).any() else None,
                    "capped": int((w < w0 - 1e-9).sum()), "capped_in_travel": int(((w < w0 - 1e-9) & (th < TRAVEL)).sum()),
                    "min_room_left_mm": round(float((room - mv)[mv > 1e-7].min()) * 1000, 3) if (mv > 1e-7).any() else None}
        views[key] = (sel, rest0, cl, rl, ia, r0, r1, gap)
    # the normals: each vertex's original normal turned by its welded position's change of the geometric normal
    weld = np.unique(np.round(P * 1e5).astype(np.int64), axis=0, return_inverse=True)[1].ravel()

    def geo_normals(Q):
        fn = np.cross(Q[I[:, 1]] - Q[I[:, 0]], Q[I[:, 2]] - Q[I[:, 0]])
        acc = np.zeros((weld.max() + 1, 3))
        for k in range(3):
            np.add.at(acc, weld[I[:, k]], fn)
        acc /= np.maximum(np.linalg.norm(acc, axis=1), 1e-12)[:, None]
        return acc[weld]
    g0, g1 = geo_normals(P), geo_normals(P1)
    touched = np.isin(I, np.nonzero(np.linalg.norm(P1 - P, axis=1) > 0)[0]).any(1)
    ch_w = np.isin(weld, np.unique(weld[np.unique(I[touched].ravel())]))
    N1 = N.copy()
    N1[ch_w] = N[ch_w] + (g1[ch_w] - g0[ch_w])
    N1[ch_w] /= np.linalg.norm(N1[ch_w], axis=1)[:, None]
    rep["normals_turned"] = int(ch_w.sum())
    # the faceted sclera: the eyeball's own vertices take the sphere's radial normal, faded in from the lid line
    radial_n = np.zeros(len(P), bool)
    for key, (sel, _r0, cl, rl, _ia, _a, _b, gap) in views.items():
        rad = P1[sel] - cl
        rad /= np.linalg.norm(rad, axis=1)[:, None]
        k = np.array([G.smoothstep(0.0, 0.06 * r, float(g)) for g in gap])[:, None]
        n = N1[sel] * (1.0 - k) + rad * k
        N1[sel] = n / np.linalg.norm(n, axis=1)[:, None]
        radial_n[sel[k[:, 0] > 0]] = True
        rep[key]["radial_normals"] = int((k[:, 0] > 0).sum())
    changed = np.abs(N1 - N).max(1) > 1e-7
    T1 = T.copy()
    for i in np.nonzero(changed)[0]:
        T1[i] = G.orthogonal_tangent(tuple(N1[i]), tuple(T[i]))
    rep["tangents_reorthogonalised"] = int(changed.sum())
    rep["max_abs_n_dot_t_after"] = round(float(np.abs((N1 * T1[:, :3]).sum(1)).max()), 6)
    rep["lid_vertices_moved"] = int((np.linalg.norm(P1 - P, axis=1)[vs] > 0).sum())
    mv = np.linalg.norm(P1 - P, axis=1)[mv_any := np.linalg.norm(P1 - P, axis=1) > 0]
    rep["move_mm"] = ({"p50": round(float(np.median(mv)) * 1000, 3), "p99": round(float(np.percentile(mv, 99)) * 1000, 3),
                       "over_5mm": int((mv > 0.005).sum())} if len(mv) else {"p50": 0.0, "p99": 0.0, "over_5mm": 0})
    # the lid gap: eyeball triangles that cross a lid or socket triangle near the eyes (neighbours sharing a vertex
    # or a welded position left out), before and after
    near_t = np.minimum(*(np.linalg.norm(P[I].mean(1) - c, axis=1) for c in centres.values())) < 1.4 * r
    eb, lt = np.nonzero(eyeball & near_t)[0], np.nonzero(~eyeball & near_t)[0]

    def crossings(Q):
        verts = [Vector(v) for v in Q]
        te = BVHTree.FromPolygons(verts, [tuple(int(x) for x in I[t]) for t in eb], all_triangles=True)
        tl = BVHTree.FromPolygons(verts, [tuple(int(x) for x in I[t]) for t in lt], all_triangles=True)
        n = 0
        for i, j in te.overlap(tl):
            if not set(weld[I[eb[i]]].tolist()) & set(weld[I[lt[j]]].tolist()):
                n += 1
        return n
    rep["lid_crossings"] = {"before": crossings(P), "after": crossings(P1)}
    return P1, N1, T1, rep, views


def rim_smooth(P, N, T, I, eyeball, centres, r, iters):
    """A3b: the eye rim smoothed along itself. The rim is every welded edge with an eyeball triangle on one side and a
    lid or socket triangle on the other (near an eye); Meshy left it a sawtooth (the shared vertices step in and out
    by one triangle), so the crease drew a dark line with a light band and the eye mask, which follows the triangles,
    drew white sclera teeth on the lid. Each rim vertex with two rim neighbours moves by `iters` Taubin steps (lambda,
    mu: a 1D smoothing along the loop that does not shrink it; the alternate in-out step is cancelled by the first),
    each capped at RIM_CAP of the eye radius from the start and followed by a projection onto the surface as it was (the lid and eyeball triangles near the eye), so the
    vertex slides along the head, not off it: the shape stays, only the seam between the two moves. Junctions and ends
    of the rim stay put. The normals of the triangles round a moved vertex turn with their geometric normal (as in
    eyeball_fix), and every rim position's copies take one normal (the seam welded; a fold, copies over RIM_WELD_DEG apart, stays split). A3d: a triangle round a moved vertex whose geometric normal
    flips (dot <= 0) or whose area drops under 10 % scales the whole step back (halved and re-projected, down to 1/64;
    still one: the build fails); the count goes into the report (bad_triangles) and pit_geometry. Returns P, N, T and
    the report."""
    weld = np.unique(np.round(P * 1e5).astype(np.int64), axis=0, return_inverse=True)[1].ravel()
    nw = int(weld.max()) + 1
    near_t = np.minimum(*(np.linalg.norm(P[I].mean(1) - c, axis=1) for c in centres.values())) < 1.4 * r
    E = np.concatenate([I[:, [0, 1]], I[:, [1, 2]], I[:, [2, 0]]])
    tri = np.tile(np.arange(len(I)), 3)
    we = np.sort(weld[E], axis=1)
    keep = near_t[tri] & (we[:, 0] != we[:, 1])
    we, tri = we[keep], tri[keep]
    uk, inv = np.unique(we[:, 0].astype(np.int64) * nw + we[:, 1], return_inverse=True)
    inv = inv.ravel()
    has_e, has_l = np.zeros(len(uk), bool), np.zeros(len(uk), bool)
    np.logical_or.at(has_e, inv, eyeball[tri])
    np.logical_or.at(has_l, inv, ~eyeball[tri])
    rim_k = uk[has_e & has_l]
    a, b = rim_k // nw, rim_k % nw
    nodes = np.unique(np.concatenate([a, b]))
    idx = {int(n): k for k, n in enumerate(nodes)}
    nbr = [[] for _ in nodes]
    for x, y in zip(a, b):
        nbr[idx[int(x)]].append(idx[int(y)])
        nbr[idx[int(y)]].append(idx[int(x)])
    free = np.array([len(n) == 2 for n in nbr])
    nb = np.array([n if len(n) == 2 else [k, k] for k, n in enumerate(nbr)])
    Qw = np.zeros((nw, 3))
    Qw[weld] = P
    S0 = Qw[nodes].copy()
    S = S0.copy()
    surf_t = np.nonzero(near_t)[0]
    bvh = BVHTree.FromPolygons([Vector(v) for v in P], [tuple(int(x) for x in I[t]) for t in surf_t], all_triangles=True)

    def zigzag(Q):  # each free rim vertex's distance from its neighbours' midpoint (the sawtooth's size)
        return np.linalg.norm(Q[free] - Q[nb[free]].mean(1), axis=1)
    z0 = zigzag(S0)
    for _ in range(iters):
        for f in (RIM_LAMBDA, RIM_MU):
            S = S + f * (S[nb].mean(1) - S) * free[:, None]
        d = S - S0
        dl = np.linalg.norm(d, axis=1)
        S = S0 + d * np.minimum(1.0, RIM_CAP * r / np.maximum(dl, 1e-12))[:, None]
        S[free] = np.array([tuple(bvh.find_nearest(Vector(p))[0]) for p in S[free]])
    on = np.isin(weld, nodes)

    def place(Sx):  # the mesh with the rim nodes at Sx (every copy of a welded position moved together)
        Q = P.copy()
        pos = np.zeros((nw, 3))
        pos[nodes] = Sx
        Q[on] = pos[weld[on]]
        return Q

    def bad_tris(Q):  # A3d: triangles round a moved vertex whose geometric normal flips or whose area drops under 10 %
        t = np.isin(I, np.nonzero(np.linalg.norm(Q - P, axis=1) > 0)[0]).any(1)
        f0 = np.cross(P[I[t, 1]] - P[I[t, 0]], P[I[t, 2]] - P[I[t, 0]])
        f1 = np.cross(Q[I[t, 1]] - Q[I[t, 0]], Q[I[t, 2]] - Q[I[t, 0]])
        a0, a1 = np.linalg.norm(f0, axis=1), np.linalg.norm(f1, axis=1)
        ok = a0 > 1e-12  # a triangle degenerate before cannot flip
        return int((ok & (((f0 * f1).sum(1) <= 0) | (a1 < 0.1 * a0))).sum())
    bad_first = bad_tris(place(S))
    bad, scale, S_full = bad_first, 1.0, S
    while bad > 0 and scale > 1.0 / 64:  # the step scaled back (halved, then re-projected) until no triangle folds
        scale *= 0.5
        S = S0 + (S_full - S0) * scale
        S[free] = np.array([tuple(bvh.find_nearest(Vector(p))[0]) for p in S[free]])
        bad = bad_tris(place(S))
    if bad > 0:
        raise SystemExit(f"LIVELY rim: {bad} triangles still flip or collapse at 1/64 of the step")
    z1 = zigzag(S)
    P1 = place(S)
    mv = np.linalg.norm(S - S0, axis=1)

    def geo_normals(Q):
        fn = np.cross(Q[I[:, 1]] - Q[I[:, 0]], Q[I[:, 2]] - Q[I[:, 0]])
        acc = np.zeros((nw, 3))
        for k in range(3):
            np.add.at(acc, weld[I[:, k]], fn)
        acc /= np.maximum(np.linalg.norm(acc, axis=1), 1e-12)[:, None]
        return acc[weld]
    moved_v = np.nonzero(np.linalg.norm(P1 - P, axis=1) > 0)[0]
    touched = np.isin(I, moved_v).any(1)
    ch_w = np.isin(weld, np.unique(weld[np.unique(I[touched].ravel())]))
    g0, g1 = geo_normals(P), geo_normals(P1)
    N1 = N.copy()
    N1[ch_w] = N[ch_w] + (g1[ch_w] - g0[ch_w])
    N1[ch_w] /= np.linalg.norm(N1[ch_w], axis=1)[:, None]
    acc = np.zeros((nw, 3))
    np.add.at(acc, weld[on], N1[on])
    acc /= np.maximum(np.linalg.norm(acc, axis=1), 1e-12)[:, None]
    ang = np.zeros(len(P))
    ang[on] = np.degrees(np.arccos(np.clip((N1[on] * acc[weld[on]]).sum(1), -1, 1)))
    folded = np.zeros(nw, bool)
    np.logical_or.at(folded, weld[on], ang[on] > RIM_WELD_DEG)
    weld_on = on & ~folded[weld]
    split = float(ang[weld_on].max()) if weld_on.any() else 0.0
    N1[weld_on] = acc[weld[weld_on]]
    changed = np.abs(N1 - N).max(1) > 1e-7
    T1 = T.copy()
    for i in np.nonzero(changed)[0]:
        T1[i] = G.orthogonal_tangent(tuple(N1[i]), tuple(T[i]))

    def side_stats(m):
        return {"rim_vertices": int(m.sum()), "max_move_mm": round(float(mv[m].max()) * 1000, 3) if m.any() else 0.0,
                "p50_move_mm": round(float(np.median(mv[m])) * 1000, 3) if m.any() else 0.0}
    rep = {"iters": iters, "rim_edges": int(len(rim_k)), "rim_vertices": int(len(nodes)), "fixed": int((~free).sum()),
           "max_move_mm": round(float(mv.max()) * 1000, 3), "p50_move_mm": round(float(np.median(mv)) * 1000, 3),
           "zigzag_mm": {"before_p50": round(float(np.median(z0)) * 1000, 3), "before_max": round(float(z0.max()) * 1000, 3),
                         "after_p50": round(float(np.median(z1)) * 1000, 3), "after_max": round(float(z1.max()) * 1000, 3)},
           "normal_split_welded_deg": round(split, 2), "folds_left_split": int(folded.sum()),
           "normals_changed": int(changed.sum()),
           "bad_triangles": {"at_full_step": bad_first, "after": bad, "step_scale": scale},
           "max_abs_n_dot_t_after": round(float(np.abs((N1 * T1[:, :3]).sum(1)).max()), 6)}
    for side, c in centres.items():
        rep["left" if side > 0 else "right"] = side_stats(np.linalg.norm(S0 - c, axis=1) < 1.5 * r)
    return P1, N1, T1, rep


RIM_CUT_SNAPS = 40  # R1: at most this many rounds of snapping slivers through a corner (the build fails beyond)
RIM_CUT_RINGS = 2  # R1: the cut's band, rings of triangles round the rim (1: a lid tooth two triangles deep stays)
RIM_CUT_MAX_AREA_PCT = 3.0  # R2: the largest net change of an eye's eyeball area by the cut (%): a fair curve through a
# one-triangle sawtooth gives as much area to the lid as it takes, so the net stays near 0 (the test's sawtooth discs);
# R1's chameleon cut (v8cut_r1e's settings) changes one eye by 4.15 % and fails here: its trimmed fit is biased


def rim_graph(P, I, cls, near_t):
    """R1: the eye rim of a triangle class (cls: True an eyeball triangle) as a graph of welded positions: the welded
    edges of the triangles near the eyes with an eyeball triangle on one side and a lid one on the other. Returns the
    weld (per vertex its position id), the rim's position ids and each one's rim neighbours (indices into them)."""
    weld = np.unique(np.round(P * 1e5).astype(np.int64), axis=0, return_inverse=True)[1].ravel()
    nw = int(weld.max()) + 1
    E = np.concatenate([I[:, [0, 1]], I[:, [1, 2]], I[:, [2, 0]]])
    tri = np.tile(np.arange(len(I)), 3)
    we = np.sort(weld[E], axis=1)
    keep = near_t[tri] & (we[:, 0] != we[:, 1])
    we, tri = we[keep], tri[keep]
    uk, inv = np.unique(we[:, 0].astype(np.int64) * nw + we[:, 1], return_inverse=True)
    inv = inv.ravel()
    has_e, has_l = np.zeros(len(uk), bool), np.zeros(len(uk), bool)
    np.logical_or.at(has_e, inv, cls[tri])
    np.logical_or.at(has_l, inv, ~cls[tri])
    rim_k = uk[has_e & has_l]
    a, b = rim_k // nw, rim_k % nw
    nodes = np.unique(np.concatenate([a, b]))
    idx = {int(n): k for k, n in enumerate(nodes)}
    nbr = [[] for _ in nodes]
    for x, y in zip(a, b):
        nbr[idx[int(x)]].append(idx[int(y)])
        nbr[idx[int(y)]].append(idx[int(x)])
    return weld, nodes, nbr


def zigzag_stats(Q, nbr):
    """R1: the rim's sawtooth as rim_smooth measures it (each rim position with two rim neighbours: its distance from
    their midpoint, mm) and the positions where the rim is no simple loop (one or three or more rim neighbours)."""
    free = np.array([len(n) == 2 for n in nbr])
    nb = np.array([n if len(n) == 2 else [k, k] for k, n in enumerate(nbr)])
    z = np.linalg.norm(Q[free] - Q[nb[free]].mean(1), axis=1) if free.any() else np.zeros(1)
    return {"nodes": int(len(nbr)), "junctions": int((~free).sum()), "p50_mm": round(float(np.median(z)) * 1000, 3),
            "max_mm": round(float(z.max()) * 1000, 3)}


def tri_areas(P, I):
    """R2: each triangle's area."""
    return 0.5 * np.linalg.norm(np.cross(P[I[:, 1]] - P[I[:, 0]], P[I[:, 2]] - P[I[:, 0]]), axis=1)


def tri_side(P, I, centres):
    """R2: each triangle's eye, 1 (left) or -1 (right), by the nearer eye centre."""
    c = P[I].mean(1)
    return np.where(np.linalg.norm(c - centres[1], axis=1) < np.linalg.norm(c - centres[-1], axis=1), 1, -1)


def edge_faults(P, I):
    """R1: the welded edges with one triangle (open) and with three or more (non-manifold)."""
    weld = np.unique(np.round(P * 1e5).astype(np.int64), axis=0, return_inverse=True)[1].ravel()
    nw = int(weld.max()) + 1
    we = np.sort(weld[np.concatenate([I[:, [0, 1]], I[:, [1, 2]], I[:, [2, 0]]])], axis=1)
    we = we[we[:, 0] != we[:, 1]]
    _, cnt = np.unique(we[:, 0].astype(np.int64) * nw + we[:, 1], return_counts=True)
    return {"open": int((cnt == 1).sum()), "non_manifold": int((cnt > 2).sum())}


def rim_cut(A, I, eyeball, centres, r, order):
    """R1: the eyeball/lid boundary cut along one smooth curve per eye. Meshy's boundary steps in and out by one
    triangle (the sawtooth), and the eye mask, which follows the triangles, drew white sclera teeth on the lid's lip;
    moving the rim's vertices folded triangles (A3b, A3d). Here no vertex moves:
    - the curve: per eye, the rim's positions seen head-on (projected onto the plane fitted to them, polar about
      their centroid: the radius against the azimuth), fitted by a periodic Fourier series up to `order`
      (G.fourier_fit_trimmed, a junction's spur left out). The first trial measured the angle from the eye centre's
      axis instead: the chameleon's opening spans 28 to 117 degrees about it, so order 6 left 4 mm (median) off;
    - the band: the triangles near the eye within RIM_CUT_RINGS rings of a rim position. Each band position gets g,
      its radius in that view minus the curve's (under 0 inside the opening). A position on the band's border keeps
      its class's side: where the curve says the other side, g is 0 and the cut runs through it (`clamped`), so the
      new boundary never leaves the band;
    - the cut: every band triangle split along g's zero line (G.cut_triangle; a quad by its better diagonal), each
      piece an eyeball triangle inside, a lid one outside. A piece under G.RIM_CUT_MIN_SHARE of its parent's area or
      turned over snaps the cut through the parent's corner nearest the cut (`snapped`, g 0 there), until none is left.
      The new vertices sit on their edges (the surface as it was) and take every attribute by interpolation along the
      edge (normals renormalised, tangents made orthogonal again, their sign kept); one per edge and side of a seam.
    A is the primitive's attributes by name (numpy rows). Returns A, I, the class, the band's new triangles' indices
    and the report (the zigzag before and after, the curve's residual, the largest move: 0, the snaps' distance from
    the curve, the bad pieces: 0, the open and non-manifold edges before and after)."""
    P = A["POSITION"]
    near_t = np.minimum(*(np.linalg.norm(P[I].mean(1) - c, axis=1) for c in centres.values())) < 1.4 * r
    weld, nodes, nbr = rim_graph(P, I, eyeball, near_t)
    nw = int(weld.max()) + 1
    Qw = np.zeros((nw, 3))
    Qw[weld] = P
    rep = {"order": order, "zigzag_before": zigzag_stats(Qw[nodes], nbr), "edges_before": edge_faults(P, I)}
    pe, pl = np.zeros(nw, bool), np.zeros(nw, bool)
    for k in range(3):
        np.logical_or.at(pe, weld[I[near_t, k]], eyeball[near_t])
        np.logical_or.at(pl, weld[I[near_t, k]], ~eyeball[near_t])
    mixed = pe & pl
    band = near_t & mixed[weld[I]].any(1)
    for _ in range(RIM_CUT_RINGS - 1):
        grown = np.zeros(nw, bool)
        grown[weld[I[band]].ravel()] = True
        band = near_t & grown[weld[I]].any(1)
    bw = np.unique(weld[I[band]].ravel())
    border = np.zeros(nw, bool)
    border[weld[I[~band]].ravel()] = True
    side_w = np.where(np.linalg.norm(Qw - centres[1], axis=1) < np.linalg.norm(Qw - centres[-1], axis=1), 1, -1)
    gw = np.zeros(nw)
    curves = {}
    for s, c in centres.items():
        key = "left" if s > 0 else "right"
        mine = nodes[side_w[nodes] == s]
        m0 = Qw[mine].mean(0)
        F = np.linalg.svd(Qw[mine] - m0)[2][2]
        F = F if F @ (m0 - c) > 0 else -F
        _f, S, U = (np.array(v) for v in G.eye_frame(tuple(F)))

        def angles(Q, m0=m0, S=S, U=U):  # the radius about the centroid in the rim's plane, and the azimuth
            q = Q - m0
            return np.hypot(q @ S, q @ U), np.arctan2(q @ U, q @ S)
        th, ph = angles(Qw[mine])
        coef, kept = G.fourier_fit_trimmed(ph.tolist(), th.tolist(), order)

        def curve(ph_, coef=coef):
            return np.array([G.fourier_eval(coef, float(p)) for p in ph_])
        curves[s] = (angles, curve)
        res = np.abs(th - curve(ph))
        b_s = bw[side_w[bw] == s]
        tb, pb = angles(Qw[b_s])
        gw[b_s] = tb - curve(pb)
        rep[key] = {"rim_positions": int(len(mine)), "fit_kept": int(sum(kept)),
                    "radius_mm": [round(float(th.min()) * 1000, 1), round(float(th.max()) * 1000, 1)],
                    "rim_off_curve_mm": {"p50": round(float(np.median(res)) * 1000, 3),
                                         "p90": round(float(np.percentile(res, 90)) * 1000, 3),
                                         "max": round(float(res.max()) * 1000, 3)},
                    "p50_mm_by_order": {}}
        for o in (2, 4, 8, 12):  # the fit's order against the rim's spread about it (a diagnostic)
            co, _k = G.fourier_fit_trimmed(ph.tolist(), th.tolist(), o)
            rep[key]["p50_mm_by_order"][o] = round(float(np.median(np.abs(th - curve(ph, co)))) * 1000, 3)
    forced = bw[border[bw] & ~mixed[bw]]
    wrong = gw[forced] * np.where(pe[forced], -1.0, 1.0) < 0
    g_fit = gw.copy()
    gw[forced[wrong]] = 0.0
    bt = np.nonzero(band)[0]
    n_par = np.cross(P[I[bt, 1]] - P[I[bt, 0]], P[I[bt, 2]] - P[I[bt, 0]])
    a_par = np.linalg.norm(n_par, axis=1)

    def at(t, ref):
        if ref[0] == "v":
            return P[I[t, ref[1]]]
        return P[I[t, ref[1]]] * (1 - ref[3]) + P[I[t, ref[2]]] * ref[3]

    def quality(j, t, tr):  # the piece's share of its parent's area, -1 turned over
        pa, pb_, pc = (at(t, x) for x in tr)
        n = np.cross(pb_ - pa, pc - pa)
        if a_par[j] <= 1e-14:
            return 1.0
        return np.linalg.norm(n) / a_par[j] if (n @ n_par[j]) > 0 else -1.0

    def pieces_of(j, t):
        out_, worst = [], 1.0
        for poly, side in G.cut_triangle(tuple(gw[weld[I[t]]])):
            opts = [[poly]] if len(poly) == 3 else [[[poly[0], poly[1], poly[2]], [poly[0], poly[2], poly[3]]],
                                                     [[poly[0], poly[1], poly[3]], [poly[1], poly[2], poly[3]]]]
            best = max(opts, key=lambda tris: min(quality(j, t, tr) for tr in tris))
            out_ += [(tr, side) for tr in best]
            worst = min(worst, min(quality(j, t, tr) for tr in best))
        return out_, worst
    snapped = set()
    for _ in range(RIM_CUT_SNAPS):
        cut, zero = [], set()
        for j, t in enumerate(bt):
            pcs, worst = pieces_of(j, t)
            cut.append(pcs)
            if worst < G.RIM_CUT_MIN_SHARE:
                cand = [(x[3], x[1]) for tr, _s in pcs for x in tr if x[0] == "e"]
                cand += [(1 - x[3], x[2]) for tr, _s in pcs for x in tr if x[0] == "e"]
                zero.add(int(weld[I[t, min(cand)[1]]]))
        if not zero:
            break
        gw[list(zero)] = 0.0
        snapped |= zero
    else:
        raise SystemExit(f"LIVELY rim cut: slivers left after {RIM_CUT_SNAPS} rounds of snapping")
    bad = sum(int(quality(j, t, tr) < G.RIM_CUT_MIN_SHARE) for j, t in enumerate(bt) for tr, _s in cut[j])
    # the new vertices: one per edge (its two vertex indices), every attribute interpolated along it
    new_key, rows = {}, []
    tris_new, cls_new = [], []
    nv = len(P)
    lid_to_eye = eye_to_lid = 0
    for j, t in enumerate(bt):
        for tr, side in cut[j]:
            ids = []
            for x in tr:
                if x[0] == "v":
                    ids.append(int(I[t, x[1]]))
                    continue
                i0, i1, tt = int(I[t, x[1]]), int(I[t, x[2]]), float(x[3])
                if i0 > i1:
                    i0, i1, tt = i1, i0, 1.0 - tt
                if (i0, i1) not in new_key:
                    new_key[(i0, i1)] = nv + len(rows)
                    rows.append((i0, i1, tt))
                ids.append(new_key[(i0, i1)])
            tris_new.append(ids)
            c_new = bool(eyeball[t]) if side == 0 else side < 0
            cls_new.append(c_new)
            lid_to_eye += int(c_new and not eyeball[t])
            eye_to_lid += int(eyeball[t] and not c_new)
    lo = np.array([rw[0] for rw in rows], dtype=np.int64)
    hi = np.array([rw[1] for rw in rows], dtype=np.int64)
    tt = np.array([rw[2] for rw in rows])[:, None]
    B = {}
    for name, X in A.items():
        Xn = X[lo] * (1 - tt) + X[hi] * tt
        if name == "NORMAL":
            Xn = Xn / np.linalg.norm(Xn, axis=1)[:, None]
        B[name] = Xn
    if "TANGENT" in B:
        T = B["TANGENT"]
        T[:, 3] = A["TANGENT"][lo, 3]
        for k in range(len(T)):
            T[k] = G.orthogonal_tangent(tuple(B["NORMAL"][k]), tuple(T[k]))
    A1 = {name: np.concatenate([X, B[name]]) for name, X in A.items()}
    I1 = np.concatenate([I[~band], np.array(tris_new, dtype=I.dtype).reshape(-1, 3)])
    cls1 = np.concatenate([eyeball[~band], np.array(cls_new, bool)])
    band1 = np.arange(int((~band).sum()), len(I1))
    P1 = A1["POSITION"]
    near1 = np.minimum(*(np.linalg.norm(P1[I1].mean(1) - c, axis=1) for c in centres.values())) < 1.4 * r
    weld1, nodes1, nbr1 = rim_graph(P1, I1, cls1, near1)
    Q1 = np.zeros((int(weld1.max()) + 1, 3))
    Q1[weld1] = P1
    off = []
    for s, (angles, curve) in curves.items():
        q = Q1[nodes1]
        sel = np.linalg.norm(q - centres[s], axis=1) < np.linalg.norm(q - centres[-s], axis=1)
        th, ph = angles(q[sel])
        off.append(np.abs(th - curve(ph)))
    off = np.concatenate(off)
    sn = np.array(sorted(snapped | set(int(x) for x in forced[wrong])), dtype=np.int64)
    rep.update({"zigzag_after": zigzag_stats(Q1[nodes1], nbr1), "edges_after": edge_faults(P1, I1),
                "band_triangles": int(len(bt)), "pieces": int(len(tris_new)), "new_vertices": int(len(rows)),
                "pieces_lid_to_eye": lid_to_eye, "pieces_eye_to_lid": eye_to_lid,
                "clamped": int(wrong.sum()), "snapped": int(len(snapped)), "max_move_mm": 0.0,
                "cut_off_curve_mm": {"p50": round(float(np.median(off)) * 1000, 3), "max": round(float(off.max()) * 1000, 3)},
                "snaps_off_curve_mm": ({"p50": round(float(np.median(np.abs(g_fit[sn]))) * 1000, 3),
                                        "max": round(float(np.abs(g_fit[sn]).max() * 1000), 3)} if len(sn) else None),
                "bad_triangles": bad, "eyeball_triangles": {"before": int(eyeball.sum()), "after": int(cls1.sum())}})
    # R2: the eye opening's change, each eye's eyeball area (the cut's eyeball triangles against the class before)
    rep["eyeball_area"] = {}
    for s, key in ((1, "left"), (-1, "right")):
        a0 = tri_areas(P, I[eyeball & (tri_side(P, I, centres) == s)]).sum()
        a1 = tri_areas(P1, I1[cls1 & (tri_side(P1, I1, centres) == s)]).sum()
        rep["eyeball_area"][key] = {"before": round(float(a0) * 1e6, 3), "after": round(float(a1) * 1e6, 3),
                                    "change_pct": round(float(100 * (a1 - a0) / max(a0, 1e-12)), 3)}
        rep[key]["trimmed"] = rep[key]["rim_positions"] - rep[key]["fit_kept"]
    worst = max(abs(v["change_pct"]) for v in rep["eyeball_area"].values())
    if bad or rep["edges_after"] != rep["edges_before"] or worst > RIM_CUT_MAX_AREA_PCT:
        raise SystemExit(f"LIVELY rim cut: {bad} bad pieces, edges {rep['edges_before']} -> {rep['edges_after']}, "
                         f"eyeball area change {worst} % (bound {RIM_CUT_MAX_AREA_PCT})")
    return A1, I1, cls1, band1, rep


LIP_RINGS = 3  # R2: the lid's lip, rings of welded positions outside the rim that the lip smoothing moves
LIP_CAP = 0.04  # R2: no lip position moves further than this share of the eye radius
LIP_FLIP_DOT = 0.5  # R2: a lip triangle whose normal turns further than 60 degrees fails the build


def lip_smooth(A, I, cls, centres, r, steps, mode):
    """R2: the lid's lip round each eye smoothed, the white fringe under the eye: Meshy's lid edge steps in and out by
    a triangle, and the steps' upper faces catch the key light, a light serrated line along the lower lid (the rim
    sheet's geometry-only column; the cut left the mask's edge straight). The lid positions within LIP_RINGS rings of
    the rim move (welded, every copy alike); the rim itself and the eyeball stay, so the cut's curve and the eye opening
    are kept.
    - mode "normals": the positions kept, the lip's normals averaged over their welded neighbours `steps` times;
    - mode "taubin": `steps` Taubin steps (RIM_LAMBDA, RIM_MU) of the lip's positions over the lid's welded edges, each
      move capped at LIP_CAP of the radius, then the lip's normals from its faces (area-weighted), half-blended on the
      outer ring so the shading meets the untouched lid without a seam.
    Tangents are made orthogonal again. Returns A (new arrays) and the report (moved positions, largest move, the
    largest normal turn of a lip triangle; the build fails when one turns past LIP_FLIP_DOT)."""
    P, N = A["POSITION"], A["NORMAL"]
    near_t = np.minimum(*(np.linalg.norm(P[I].mean(1) - c, axis=1) for c in centres.values())) < 1.4 * r
    weld, nodes, _nbr = rim_graph(P, I, cls, near_t)
    nw = int(weld.max()) + 1
    lid_t = near_t & ~cls
    E = np.concatenate([I[lid_t][:, [0, 1]], I[lid_t][:, [1, 2]], I[lid_t][:, [2, 0]]])
    we = weld[E]
    we = np.unique(np.sort(we[we[:, 0] != we[:, 1]], axis=1), axis=0)
    ring = np.full(nw, 1 << 20)
    ring[nodes] = 0
    for _ in range(LIP_RINGS):
        a, b = ring[we[:, 0]].copy(), ring[we[:, 1]].copy()
        np.minimum.at(ring, we[:, 0], b + 1)
        np.minimum.at(ring, we[:, 1], a + 1)
    fixed = np.zeros(nw, bool)  # the eyeball's and the far head's positions never move
    fixed[weld[I[cls | ~near_t]].ravel()] = True
    free = (ring > 0) & (ring <= LIP_RINGS) & ~fixed
    deg = np.bincount(we.ravel(), minlength=nw).astype(float)

    def lap(X):
        acc = np.zeros_like(X)
        np.add.at(acc, we[:, 0], X[we[:, 1]])
        np.add.at(acc, we[:, 1], X[we[:, 0]])
        return acc / np.maximum(deg, 1)[:, None] - X
    Qw = np.zeros((nw, 3))
    Qw[weld] = P
    Nw = np.zeros((nw, 3))
    np.add.at(Nw, weld, N)
    Nw /= np.maximum(np.linalg.norm(Nw, axis=1), 1e-12)[:, None]
    Q0 = Qw.copy()
    if mode == "taubin":
        for _ in range(steps):
            for f in (RIM_LAMBDA, RIM_MU):
                d = lap(Qw)
                Qw[free] += f * d[free]
        mv = Qw - Q0
        m = np.linalg.norm(mv, axis=1)
        Qw = Q0 + mv * np.minimum(1.0, LIP_CAP * r / np.maximum(m, 1e-12))[:, None]
        P1 = Qw[weld]
        fn = np.cross(P1[I[:, 1]] - P1[I[:, 0]], P1[I[:, 2]] - P1[I[:, 0]])
        acc = np.zeros((nw, 3))
        for k in range(3):
            np.add.at(acc, weld[I[lid_t, k]], fn[lid_t])
        Nf = acc / np.maximum(np.linalg.norm(acc, axis=1), 1e-12)[:, None]
        w = np.where(ring == LIP_RINGS, 0.5, 1.0)[:, None]
        Nn = Nw * (1 - w) + Nf * w
    else:
        P1 = P.copy()
        Nn = Nw.copy()
        for _ in range(steps):
            d = lap(Nn)
            Nn[free] += 0.5 * d[free]
            Nn /= np.maximum(np.linalg.norm(Nn, axis=1), 1e-12)[:, None]
    Nn /= np.maximum(np.linalg.norm(Nn, axis=1), 1e-12)[:, None]
    hit = free[weld]
    N1 = N.copy()
    N1[hit] = Nn[weld[hit]]
    aff = free[weld[I]].any(1)
    n0 = np.cross(P[I[:, 1]] - P[I[:, 0]], P[I[:, 2]] - P[I[:, 0]])[aff]
    n1 = np.cross(P1[I[:, 1]] - P1[I[:, 0]], P1[I[:, 2]] - P1[I[:, 0]])[aff]
    dots = np.sum(n0 * n1, 1) / np.maximum(np.linalg.norm(n0, axis=1) * np.linalg.norm(n1, axis=1), 1e-24)
    out = dict(A)
    out["POSITION"], out["NORMAL"] = P1, N1
    if "TANGENT" in A:
        T = A["TANGENT"].copy()
        for k in np.nonzero(hit)[0]:
            T[k] = G.orthogonal_tangent(tuple(N1[k]), tuple(T[k]))
        out["TANGENT"] = T
    turn = np.degrees(np.arccos(np.clip(np.sum(N[hit] * N1[hit], 1), -1, 1)))
    rep = {"mode": mode, "steps": steps, "rings": LIP_RINGS, "positions": int(free.sum()), "vertices": int(hit.sum()),
           "max_move_mm": round(float(np.linalg.norm(Qw - Q0, axis=1).max()) * 1000, 3),
           "normal_turn_deg": {"p50": round(float(np.median(turn)), 2) if len(turn) else 0.0,
                               "max": round(float(turn.max()), 2) if len(turn) else 0.0},
           "min_face_dot": round(float(dots.min()), 4) if len(dots) else 1.0}
    if rep["min_face_dot"] < LIP_FLIP_DOT:
        raise SystemExit(f"LIVELY lip smooth: a lip triangle turned (face dot {rep['min_face_dot']})")
    return out, rep


def rim_mask(mask, UV, I, cls, band):
    """R1: the eye mask repainted on the rim cut's triangles, so its edge is the cut's: each texel a band triangle
    covers takes its class's median mask texel (taken where the mask already agrees) when the mask says the other
    class; then two rings of uncovered gutter round a changed texel take the change (the texture filter reads them)."""
    H, W = mask.shape[:2]
    cls_map = np.full((H, W), -1, np.int8)

    def cover(tris, fill):
        for t in tris:
            uv = UV[I[t]] * [W, H]
            x0, y0 = np.maximum(np.floor(uv.min(0)).astype(int), 0)
            x1, y1 = np.minimum(np.ceil(uv.max(0)).astype(int), [W - 1, H - 1])
            (ax_, ay_), (bx, by), (cx, cy) = uv
            den = (by - cy) * (ax_ - cx) + (cx - bx) * (ay_ - cy)
            if x1 < x0 or y1 < y0 or abs(den) < 1e-12:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            l1 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / den
            l2 = ((cy - ay_) * (gx - cx) + (ax_ - cx) * (gy - cy)) / den
            ins = (l1 >= 0) & (l2 >= 0) & (1.0 - l1 - l2 >= 0)
            fill(t, gy[ins].astype(int), gx[ins].astype(int))

    def put(t, yy, xx):
        cls_map[yy, xx] = 1 if cls[t] else 0
    cover(band, put)
    eye = mask[..., 0] < 0.5
    to_eye, to_skin = (cls_map == 1) & ~eye, (cls_map == 0) & eye
    out = mask.copy()
    for m, keep in ((to_eye, (cls_map == 1) & eye), (to_skin, (cls_map == 0) & ~eye)):
        if m.any() and keep.any():
            out[m] = np.median(mask[keep], 0)
    changed = to_eye | to_skin
    rep = {"to_eye": int(to_eye.sum()), "to_skin": int(to_skin.sum()), "gutter": 0}
    ys, xs = np.nonzero(changed)
    if not len(ys):
        return out, rep
    y0, y1, x0, x1 = ys.min() - 3, ys.max() + 3, xs.min() - 3, xs.max() + 3
    uvt = UV[I] * [W, H]
    hit = np.nonzero((uvt[:, :, 0].max(1) >= x0) & (uvt[:, :, 0].min(1) <= x1 + 1)
                     & (uvt[:, :, 1].max(1) >= y0) & (uvt[:, :, 1].min(1) <= y1 + 1))[0]
    cov = np.zeros((H, W), bool)

    def mark(_t, yy, xx):
        cov[yy, xx] = True
    cover(hit, mark)
    for _ in range(2):
        grow = dilate(changed, 1) & ~cov & ~changed
        add = np.zeros((H, W), bool)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                src = np.roll(np.roll(changed, dy, 0), dx, 1)
                val = np.roll(np.roll(out, dy, 0), dx, 1)
                m = grow & src & ~add
                out[m] = val[m]
                add |= m
        rep["gutter"] += int(add.sum())
        changed = changed | add
    return out, rep


def residual_view(path, P, I, views, size=640):
    """eye_residual.png (1280 x 1280): per eye (rows: left, right) its eyeball seen along the old iris's axis, before
    (left column) and after (right) the fix, each surface point coloured by its distance from the ring sphere in % of
    the radius (blue a dent, red a bulge, white 0, saturated at 3 %); circles at the old iris (black) and the fix's
    full and zero weight (TRAVEL and FADE, grey)."""
    img = np.full((2 * size, 2 * size, 3), 40, np.uint8)
    for row, key in enumerate(("left", "right")):
        sel, rest0, cl, rl, ia, r0, r1, _gap = views[key]
        f, s, u = (np.array(v) for v in G.eye_frame(tuple(rest0)))
        idx = -np.ones(len(P), int)
        idx[sel] = np.arange(len(sel))
        tris = I[(idx[I] >= 0).all(1)]
        span = math.sin(FADE + math.radians(6)) * rl * 1.05
        Q = P[sel] - cl
        for col, res in enumerate((r0, r1)):
            x = (Q @ s / span * 0.5 + 0.5) * (size - 1)
            y = (0.5 - Q @ u / span * 0.5) * (size - 1)
            z = Q @ f
            zb = np.full((size, size), -np.inf)
            for t in tris:
                a, b, c = idx[t]
                if min(z[a], z[b], z[c]) <= 0:
                    continue
                xs, ys = np.array([x[a], x[b], x[c]]), np.array([y[a], y[b], y[c]])
                x0, x1 = max(int(xs.min()), 0), min(int(xs.max()) + 1, size - 1)
                y0, y1 = max(int(ys.min()), 0), min(int(ys.max()) + 1, size - 1)
                den = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
                if x1 < x0 or y1 < y0 or abs(den) < 1e-9:
                    continue
                gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
                l1 = ((ys[1] - ys[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gy - ys[2])) / den
                l2 = ((ys[2] - ys[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gy - ys[2])) / den
                l3 = 1 - l1 - l2
                ins = (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
                zz = l1 * z[a] + l2 * z[b] + l3 * z[c]
                rr = np.clip((l1 * res[a] + l2 * res[b] + l3 * res[c]) / 3.0, -1, 1)
                yy, xx = gy.astype(int), gx.astype(int)
                ok = ins & (zz > zb[yy, xx])
                zb[yy[ok], xx[ok]] = zz[ok]
                v = rr[ok][:, None]
                colr = np.where(v < 0, (1 + v) * np.array([255, 255, 255]) + (-v) * np.array([30, 80, 255]),
                                (1 - v) * np.array([255, 255, 255]) + v * np.array([255, 40, 30]))
                img[row * size + yy[ok], col * size + xx[ok]] = colr.astype(np.uint8)
            for ang, shade in ((ia, 0), (TRAVEL, 120), (FADE, 120)):
                rad = math.sin(ang) * rl / span * 0.5 * (size - 1)
                for t in np.linspace(0, 2 * math.pi, 900):
                    px, py = int(size / 2 + rad * math.cos(t)), int(size / 2 + rad * math.sin(t))
                    if 0 <= px < size and 0 <= py < size:
                        img[row * size + py, col * size + px] = shade
        img[row * size:(row + 1) * size, size - 1:size + 1] = 0
    G.write_png(path, 2 * size, 2 * size, img.tobytes())


def main():
    ap = argparse.ArgumentParser()
    for k in ("--glb", "--albedo", "--mask", "--build", "--out"):
        ap.add_argument(k, required=True)
    ap.add_argument("--name", default="chameleon")
    ap.add_argument("--kind", choices=("painted", "bead"), default="painted",
                    help="painted: a painted iris on a white eyeball (the chameleon, a moving iris); bead: an all-dark"
                         " bead with a painted catch light (the axolotl: no gaze, the catch light fixed to the light)")
    ap.add_argument("--gills", default="", help="a build.json with pivots.<name>_gills (Blender x, y, z): six gill"
                                                " stalks on springs instead of the crest")
    ap.add_argument("--detail", default="", help="the head's detail PNG (G the thinness): the gills' weights")
    ap.add_argument("--gill-swing", type=float, default=15.0, help="the gills' largest spring swing tested (degrees): the cap, lowered 1 degree at a time until none pokes")
    ap.add_argument("--gill-lift", choices=G.GILL_LIFTS, default="centre",
                    help="the gill weights' lift: beyond the root's distance from the head's centre (AL4) or the height over the skull proxy's surface (AL6)")
    ap.add_argument("--neck", default="", help="y0,y1 of the neck blend (default: from the neck's waist)")
    ap.add_argument("--crest-root", type=float, default=0.45, help="the crest root between the head centre and tip")
    ap.add_argument("--blade", default="0.10,0.16", help="the crest blade's half width: full weight, none")
    ap.add_argument("--no-pit-fix", action="store_true", help="the v2 build: the eyeballs as sculpted, the old fill")
    ap.add_argument("--sclera-normal-map", type=float, default=None,
                    help="A3b: controller.sclera_normal_map, the normal map's strength on the eye texels (none: the"
                         " controller's 1.0); 0 drops the old iris's concentric rings, which live in the normal map")
    ap.add_argument("--rim-smooth", type=int, default=0,
                    help="A3b: Taubin steps along the eye rim (rim_smooth; 0: the rim as Meshy left it, the v6 builds)")
    ap.add_argument("--rim-cut", type=int, default=0,
                    help="R1: the eye rim cut along one smooth curve per eye, this Fourier order (rim_cut; 0: no cut);"
                         " writes <name>_mask.png, the eye mask repainted on the cut, and lively.json's mask")
    ap.add_argument("--lip-smooth", type=int, default=0,
                    help="R2: with --rim-cut, the lid's lip smoothed this many steps (lip_smooth; 0: as cut)")
    ap.add_argument("--lip-mode", choices=("normals", "taubin"), default="taubin",
                    help="R2: lip_smooth's mode: the normals alone, or Taubin steps of the positions and the normals")
    ap.add_argument("--skull-margin", type=float, default=0.06,
                    help="the crest weight fades in over this distance below the crest root's radius from the head centre")
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    if args.rim_cut > 0 and args.no_pit_fix:  # R2: the cut runs inside the pit fix; without it it did nothing
        raise SystemExit("LIVELY --rim-cut needs the pit fix: drop --no-pit-fix or --rim-cut")
    if args.lip_smooth > 0 and args.rim_cut <= 0:
        raise SystemExit("LIVELY --lip-smooth needs --rim-cut")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    data = Path(args.glb).read_bytes()
    doc, binary = G.read_glb(data)
    prim = doc["meshes"][doc["nodes"][0]["mesh"]]["primitives"][0]
    P = accessor(doc, binary, prim["attributes"]["POSITION"])
    UV = accessor(doc, binary, prim["attributes"]["TEXCOORD_0"])
    I = accessor(doc, binary, prim["indices"]).reshape(-1, 3)
    alb, mask = load_png(args.albedo), load_png(args.mask)
    H, W = mask.shape[:2]
    if alb.shape != mask.shape:
        raise SystemExit("LIVELY the albedo and mask sizes differ")
    fit = json.loads(Path(args.build).read_text(encoding="utf-8"))["eye_fit"]
    r = fit["r"]
    centres = {+1: np.array([abs(fit["x"]), fit["z"], -fit["y"]]), -1: np.array([-abs(fit["x"]), fit["z"], -fit["y"]])}
    report = {"name": args.name, "glb": Path(args.glb).name, "vertices": len(P), "eye_radius": r}
    cen = P[I].mean(1)
    uvc = UV[I].mean(1)
    tri_eye = mask[np.clip((uvc[:, 1] * H).astype(int), 0, H - 1), np.clip((uvc[:, 0] * W).astype(int), 0, W - 1), 0] < 0.5
    bead = args.kind == "bead"
    eyeball = classify_eyeball(P, I, UV, alb, tri_eye, centres, r)
    views = {}

    # ---- the eye pit: the eyeballs' dent at the painted pupil projected out (the GLB's positions and normals patched)
    if not args.no_pit_fix:
        N = accessor(doc, binary, prim["attributes"]["NORMAL"])
        T = accessor(doc, binary, prim["attributes"]["TANGENT"])
        P, N1, T1, pit, views = eyeball_fix(P, N, T, I, UV, alb, eyeball, centres, r, bead=bead)
        if args.rim_smooth > 0:
            P, N1, T1, rim = rim_smooth(P, N1, T1, I, eyeball, centres, r, args.rim_smooth)
            report["rim"] = rim
            print(f"LIVELY rim: {json.dumps(rim)}", flush=True)
        if args.rim_cut > 0:  # R1: new vertices and triangles, so every attribute and the indices are rewritten
            A = {k: accessor(doc, binary, i) for k, i in prim["attributes"].items()}
            A.update(POSITION=P, NORMAL=N1, TANGENT=T1)
            A, I, eyeball, band_new, cut = rim_cut(A, I, eyeball, centres, r, args.rim_cut)
            if args.lip_smooth > 0:  # R2: the lid's lip, the white fringe under the eye
                A, cut["lip"] = lip_smooth(A, I, eyeball, centres, r, args.lip_smooth, args.lip_mode)
                print(f"LIVELY lip: {json.dumps(cut['lip'])}", flush=True)
            P, N1, T1, UV = A["POSITION"], A["NORMAL"], A["TANGENT"], A["TEXCOORD_0"]
            for k, i in prim["attributes"].items():
                G.replace_accessor(doc, binary, i, A[k].tolist())
            G.replace_accessor(doc, binary, prim["indices"], I.ravel().tolist(), 5125)
            binary = G.compact_buffers(doc, binary)  # R2: no old views left (UNUSED_OBJECT)
            mask, cut["mask"] = rim_mask(mask, UV, I, eyeball, band_new)
            tri_eye = eyeball.copy()  # the eye triangles from here on: the cut's classes
            G.write_png(out / f"{args.name}_mask.png", W, H, (np.clip(mask, 0, 1) * 255 + 0.5).astype(np.uint8).tobytes())
            report["mask"] = f"{args.name}_mask.png"
            report["vertices_after_cut"] = len(P)
            report["rim_cut"] = cut
            print(f"LIVELY rim cut: {json.dumps(cut)}", flush=True)
        else:
            G.write_vec3(doc, binary, prim["attributes"]["POSITION"], P.tolist())
            G.write_vec3(doc, binary, prim["attributes"]["NORMAL"], N1.tolist())
            G.write_floats(doc, binary, prim["attributes"]["TANGENT"], T1.tolist())
        data = G.write_glb(doc, binary)
        cen = P[I].mean(1)
        residual_view(out / "eye_residual.png", P, I, views)
        if args.rim_smooth > 0:
            pit["rim_bad_triangles"] = rim["bad_triangles"]  # A3d: flipped or collapsed (under 10 %) round the rim
        if args.rim_cut > 0:
            pit["rim_bad_triangles"] = cut["bad_triangles"]  # R1: the cut's pieces turned over or under 10 % of their parent
        report["pit_geometry"] = pit
        for k in ("left", "right"):
            print(f"LIVELY pit {k}: " + json.dumps({n: (b["before_median_pct"], b["after_median_pct"], b["before_min_pct"],
                                                        b["after_min_pct"]) for n, b in pit[k]["residual"].items()})
                  + f" moved {pit[k]['moved']} max {pit[k]['max_move_mm']} mm near lid {pit[k]['max_move_near_lid_mm']} mm,"
                  f" capped {pit[k]['capped']} ({pit[k]['capped_in_travel']} in travel), room left {pit[k]['min_room_left_mm']} mm,"
                  f" lid vertices moved {pit['lid_vertices_moved']}, lid crossings {pit['lid_crossings']}, move {pit['move_mm']},"
                  f" radial normals {pit[k]['radial_normals']}, tangents {pit['tangents_reorthogonalised']}"
                  f" (|n.t| max {pit['max_abs_n_dot_t_after']})", flush=True)

    # ---- every texel of the triangles near the eyes gets its 3D position (a small UV rasterizer)
    hue, sat, val = hsv(alb)
    eye = mask[..., 0] < 0.5
    posmap = np.full((H, W, 3), np.nan)
    # strict coverage (no overdraw) of every triangle: what the GPU samples; the rest of the atlas is gutter
    cov_any, cov_eye = np.zeros((H, W), bool), np.zeros((H, W), bool)
    near = np.minimum(*(np.linalg.norm(cen - c, axis=1) for c in centres.values())) < 1.3 * r
    near_e, near_l = np.zeros((H, W), bool), np.zeros((H, W), bool)
    for t in range(len(I)):
        uv = UV[I[t]] * [W, H]
        x0, y0 = np.maximum(np.floor(uv.min(0)).astype(int), 0)
        x1, y1 = np.minimum(np.ceil(uv.max(0)).astype(int), [W - 1, H - 1])
        (ax_, ay_), (bx, by), (cx, cy) = uv
        den = (by - cy) * (ax_ - cx) + (cx - bx) * (ay_ - cy)
        if x1 < x0 or y1 < y0 or abs(den) < 1e-12:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        l1 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / den
        l2 = ((cy - ay_) * (gx - cx) + (ax_ - cx) * (gy - cy)) / den
        strict = (l1 >= 0) & (l2 >= 0) & (1.0 - l1 - l2 >= 0)
        cov_any[gy[strict].astype(int), gx[strict].astype(int)] = True
        if eyeball[t]:
            cov_eye[gy[strict].astype(int), gx[strict].astype(int)] = True
        if not near[t]:
            continue
        (near_e if eyeball[t] else near_l)[gy[strict].astype(int), gx[strict].astype(int)] = True
        ins = (l1 >= -0.03) & (l2 >= -0.03) & (1.0 - l1 - l2 >= -0.03)  # a slight overdraw closes the seams
        if ins.any():
            l1, l2 = l1[ins, None], l2[ins, None]
            posmap[gy[ins].astype(int), gx[ins].astype(int)] = l1 * P[I[t, 0]] + l2 * P[I[t, 1]] + (1 - l1 - l2) * P[I[t, 2]]
    has_pos = ~np.isnan(posmap[..., 0])
    # A3b: the eye mask against the triangles near the eyes: the lid texels it calls eye (sclera drawn on the lid) and
    # the eyeball texels it calls skin; near 0 both, the mask's edge is the triangles' edge and moves with the rim
    report["mask_vs_triangles"] = {"lid_texels": int(near_l.sum()), "lid_called_eye": int((near_l & ~near_e & eye).sum()),
                                   "eye_texels": int(near_e.sum()), "eye_called_skin": int((near_e & ~near_l & ~eye).sum())}
    print(f"LIVELY mask vs triangles: {json.dumps(report['mask_vs_triangles'])}", flush=True)
    hole0 = np.zeros((H, W), bool)
    side_of = np.zeros((H, W), np.int8)
    theta_of = np.full((H, W), np.inf)
    meds, angs = [], {}
    eyes = {}
    for side, c in centres.items():
        # the lid clamp's and the texels' visibility: rays from outside the eye sphere toward its centre
        occ = np.nonzero(np.linalg.norm(cen - c, axis=1) < 2.2 * r)[0]
        verts = [Vector(v) for v in P]
        bvh = BVHTree.FromPolygons(verts, [tuple(int(x) for x in I[t]) for t in occ], all_triangles=True)
        occ_eye = tri_eye[occ]

        def open_(q):
            hit = bvh.ray_cast(Vector(c + q * 2.5 * r), Vector(-q))
            return hit[2] is not None and bool(occ_eye[hit[2]])

        mine = eye & has_pos & (np.nan_to_num(posmap[..., 0]) * side > 0)
        mine &= np.linalg.norm(np.nan_to_num(posmap) - c, axis=-1) < 1.3 * r
        ty, tx = np.nonzero(mine)
        tdir = posmap[ty, tx] - c
        tdir /= np.linalg.norm(tdir, axis=1)[:, None]
        tvis = np.array([open_(q) for q in tdir])
        iy, ix, dirs = ty[tvis], tx[tvis], tdir[tvis]
        vis = np.zeros((H, W), bool)
        vis[iy, ix] = True
        colour = alb[iy, ix]
        key = "left" if side > 0 else "right"
        if bead:  # the axolotl: an all-dark bead; its painted catch light is measured and painted out
            hh, ss, vv = hsv(colour)
            dark = vv < 0.45
            bright = (vv > 0.6) & (ss < 0.35)
            centre = np.array(views[key][2]) if key in views else c
            bd = posmap[iy, ix] - centre
            bd /= np.linalg.norm(bd, axis=1)[:, None]
            catch = None
            if bright.sum() >= 4:
                cd = bd[bright].mean(0)
                cd /= np.linalg.norm(cd)
                ang = np.arccos(np.clip(bd[bright] @ cd, -1, 1))
                catch = {"dir": cd.round(5).tolist(), "angle": round(float(np.percentile(ang, 90)), 5),
                         "colour": np.median(colour[bright], 0).round(4).tolist(), "texels": int(bright.sum())}
                sel = (np.arccos(np.clip(tdir @ cd, -1, 1)) < 1.8 * catch["angle"] + 0.03) & cov_eye[ty, tx] & (val[ty, tx] > 0.45)
                hole0[ty[sel], tx[sel]] = True
            fd = bd[dark].mean(0)
            fd /= np.linalg.norm(fd)
            meds.append(np.median(colour[dark], 0))
            share = {"dark": round(float(dark.mean()), 4), "bright": round(float(bright.mean()), 4),
                     "mid": round(float((~dark & ~bright).mean()), 4)}
            eyes[key] = {"centre": centre.round(5).tolist(), "radius": round(float(views[key][3]), 5) if key in views else r,
                         "build_eye_fit": {"centre": c.round(5).tolist(), "r": r}, "rest": fd.round(5).tolist(),
                         "bead_colour": np.median(colour[dark], 0).round(4).tolist(), "catch": catch, "shares": share,
                         "limits_deg": {"pos_x": 0, "neg_x": 0, "up": 0, "down": 0}}
            report.setdefault("texels", {})[key] = {"eye": int(len(ty)), "visible": int(tvis.sum()), **share}
            print(f"LIVELY bead {key}: visible {int(tvis.sum())} texels, shares {share}, catch {catch}", flush=True)
            continue
        pupil = vis & (val < PUPIL_V)
        iris = vis & ~pupil & (sat > 0.25) & ((hue < 0.14) | (hue > 0.92))
        sclera = vis & ~pupil & ~iris
        rim = dilate(~vis, 3)  # the lid edges and the islands' borders: no edge samples there
        iris_edge = (iris | pupil) & dilate(sclera, 2) & ~rim
        pupil_edge = pupil & dilate(iris, 2) & ~rim
        e_ax, e_ang, e_res = fit_cap(dirs[iris_edge[iy, ix]])
        p_ax, p_ang, p_res = fit_cap(dirs[pupil_edge[iy, ix]])
        rest = (e_ax + p_ax) / np.linalg.norm(e_ax + p_ax)
        theta = np.arccos(np.clip(dirs @ rest, -1, 1))
        # the painted iris to clear: every texel the GPU samples of this eye within 1.6 iris angles whose colour
        # reads iris (warm), pupil or its dark ring (dark, not the lids' teal line) or the painted catch light
        tth = np.arccos(np.clip(tdir @ rest, -1, 1))
        smed = np.median(colour[sclera[iy, ix]], 0)
        meds.append(smed)
        h_, s_, v_ = hue[ty, tx], sat[ty, tx], val[ty, tx]
        d_alb = np.linalg.norm(alb[ty, tx] - smed, axis=1)
        # the lids' teal: bright only (v4: the old pupil's dark texels at the lid line read a teal cast, v3 left
        # them and they showed as a dotted dark line under the upper lid once the iris moved away)
        teal = (h_ > 0.35) & (h_ < 0.65) & (s_ > 0.15) & (v_ >= LID_TEAL_V)
        paint = ((((h_ < 0.14) | (h_ > 0.92)) & (s_ > 0.12) & (d_alb > 0.06)) | ((v_ < 0.5) & ~teal)
                 | ((v_ > 0.985) & (s_ < 0.1)))
        if args.no_pit_fix:  # the v2 selection
            paint = (v_ < PUPIL_V) | ((s_ > 0.25) & ((h_ < 0.14) | (h_ > 0.92)))
            sel = (tth < 1.2 * e_ang) & paint
        else:
            sel = (tth < 1.6 * e_ang) & cov_eye[ty, tx] & paint
        hole0[ty[sel], tx[sel]] = True
        side_of[ty, tx] = side
        theta_of[ty, tx] = tth
        angs[side] = (e_ang, p_ang)
        report.setdefault("texels", {})["left" if side > 0 else "right"] = {
            "eye": int(len(ty)), "visible": int(tvis.sum()), "pupil": int(pupil.sum()), "iris": int(iris.sum()),
            "sclera": int(sclera.sum())}
        # the iris's radial profile (its own class only), the pupil's colour, the sclera's median
        on_iris = iris[iy, ix] & (theta < e_ang * 1.05)
        bins = []
        edges = np.linspace(p_ang, e_ang, 9)
        for k in range(8):
            sel = on_iris & (theta >= edges[k]) & (theta < edges[k + 1])
            bins.append(np.median(colour[sel], 0).round(4).tolist() if sel.sum() >= 5 else None)
        for k in range(8):  # gaps take the nearest filled bin
            if bins[k] is None:
                bins[k] = next(bins[j] for j in sorted(range(8), key=lambda j: abs(j - k)) if bins[j] is not None)
        bright = (theta < e_ang) & (hsv(colour)[2] > 0.8) & (hsv(colour)[1] < 0.25)
        catch = None
        if bright.sum() > 0.005 * max(1, (theta < e_ang).sum()):
            cd = dirs[bright].mean(0)
            catch = {"dir": (cd / np.linalg.norm(cd)).round(5).tolist(), "share": round(float(bright.mean()), 5)}

        def shares(g):
            disc = [g] + ring(g, e_ang * 0.5, 8) + ring(g, e_ang * 0.9, 12)
            pup = [g] + ring(g, p_ang * 1.1, 8)
            return np.mean([open_(q) for q in disc]), np.mean([open_(q) for q in pup])

        i0, p0 = shares(rest)
        steps = np.arange(-40, 41, 2)
        allowed = np.zeros((len(steps), len(steps)), bool)
        for yi, py in enumerate(steps):
            for xi, yx in enumerate(steps):
                g = np.array(G.gaze_dir(tuple(rest), math.radians(yx), math.radians(py)))
                si, sp = shares(g)
                allowed[yi, xi] = si >= 0.9 * i0 - 1e-6 and sp >= min(0.9 * p0, 0.75)
        mid = len(steps) // 2

        def reach(dy, dx):
            k = 0
            while 0 <= mid + (k + 1) * dy < len(steps) and 0 <= mid + (k + 1) * dx < len(steps) and \
                    allowed[mid + (k + 1) * dy, mid + (k + 1) * dx]:
                k += 1
            return 2 * k
        lim = {"pos_x": reach(0, 1), "neg_x": reach(0, -1), "up": reach(1, 0), "down": reach(-1, 0)}
        eyes["left" if side > 0 else "right"] = {
            "centre": c.round(5).tolist(), "radius": r, "rest": rest.round(5).tolist(),
            "iris_angle": round(e_ang, 5), "pupil_angle": round(p_ang, 5),
            "iris_fit": {"axis": e_ax.round(5).tolist(), "rms_deg": round(e_res, 3),
                         "edge_samples": int(iris_edge[iy, ix].sum())},
            "pupil_fit": {"axis": p_ax.round(5).tolist(), "rms_deg": round(p_res, 3),
                          "edge_samples": int(pupil_edge[iy, ix].sum())},
            "axes_apart_deg": round(math.degrees(math.acos(min(1.0, float(e_ax @ p_ax)))), 2),
            "iris_profile": bins, "pupil_colour": np.median(colour[pupil[iy, ix] & (theta < p_ang)], 0).round(4).tolist(),
            "sclera_colour": np.median(colour[sclera[iy, ix]], 0).round(4).tolist(), "catch": catch,
            "open_at_rest": {"iris": round(float(i0), 3), "pupil": round(float(p0), 3)}, "limits_deg": lim,
            "allowed_rows_pitch_up": ["".join("#" if x else "." for x in row) for row in allowed[::-1]]}
        if key in views:  # the sphere fitted to the eyeball's open front (eyeball_fix) beside the shader's eye sphere
            eyes[key]["front_sphere"] = {"centre": np.round(views[key][2], 5).tolist(), "r": round(float(views[key][3]), 5)}
        print(f"LIVELY eye {side:+d}: iris {math.degrees(e_ang):.1f} deg (rms {e_res:.2f}), pupil "
              f"{math.degrees(p_ang):.1f} deg (rms {p_res:.2f}), axes apart {eyes['left' if side > 0 else 'right']['axes_apart_deg']}, "
              f"rest open {i0:.2f}/{p0:.2f}, limits {lim}, catch {catch}", flush=True)
    report["eyes"] = eyes

    # ---- the clean sclera: the painted irises filled from real sclera texels only (the eye mask also holds the
    # atlas's black gutter, which the first fill pulled in: a dark disc where the iris was, read as a pit); the
    # gutter beside the old iris filled too, so the texture filter never bleeds a dark rim
    smed = np.mean(meds, 0)
    teal_all = (hue > 0.35) & (hue < 0.65) & (sat > 0.15)
    if bead:  # the catch light painted out from the bead's own dark texels
        hole = dilate(hole0, 2) & cov_eye
        known = cov_eye & ~hole & (val < 0.45)
    elif args.no_pit_fix:  # the v2 fill, kept for a before/after
        hole = dilate(hole0, 3) & eye
        known = eye & ~hole
    else:
        lid_teal = teal_all & (val >= LID_TEAL_V)
        hole = (dilate(hole0, 3) & ~(cov_any & ~cov_eye) & ~(cov_eye & lid_teal)) | (dilate(hole0, 8) & ~cov_any)
        # v4: the black gutter around every eye island (not beside a lid or skin island) filled with the sclera too,
        # so the texture filter draws no grey seam line along the islands' edges
        cov_skin = cov_any & ~cov_eye
        hole |= dilate(cov_eye, GUTTER_PX) & ~cov_any & ~dilate(cov_skin, GUTTER_PX)
        known = cov_eye & ~hole & (np.linalg.norm(alb - smed, axis=-1) < 0.06)
    clean = alb.astype(np.float64).copy()
    filled = push_pull(alb.astype(np.float64), known.astype(np.float64))
    clean[hole] = filled[hole]
    report["sclera_texels_filled"] = int(hole.sum())
    # the check: every sampled eye texel's distance from the sclera median, by its angle from the rest gaze
    dist = np.linalg.norm(clean - smed, axis=-1)
    ghost = {"sclera_median": smed.round(4).tolist(), "filled": int(hole.sum()), "gutter_filled": int((hole & ~cov_any).sum())}
    # the eye islands' outline: gutter texels next to a sampled eye texel (what the filter mixes in at a seam)
    rim = dilate(cov_eye, 1) & ~cov_any
    ghost["eye_rim"] = {"texels": int(rim.sum()), "dark": int((rim & (clean.max(-1) < 0.5)).sum()),
                        "median": round(float(np.median(dist[rim])), 4) if rim.any() else None}
    for side, (e_ang, p_ang) in angs.items():
        m0 = cov_eye & (side_of == side)
        g = {}
        for name, a, b in (("pupil", 0, p_ang), ("iris", p_ang, e_ang), ("iris_edge", e_ang, 1.6 * e_ang),
                           ("sclera", 1.6 * e_ang, math.radians(60)), ("back", math.radians(60), 9.0)):
            m = m0 & (theta_of >= a) & (theta_of < b)
            if m.any():
                dm = dist[m]
                g[name] = {"texels": int(m.sum()), "median": round(float(np.median(dm)), 4),
                           "p99": round(float(np.percentile(dm, 99)), 4), "max": round(float(dm.max()), 4),
                           "over_0.06": int((dm > 0.06).sum()), "over_0.06_teal": int((m & (dist > 0.06) & teal_all).sum()),
                           "white_catch": int((m & (clean.min(-1) > 0.985)).sum())}
        ghost["left" if side > 0 else "right"] = g
        print(f"LIVELY ghost {'left' if side > 0 else 'right'}: " + json.dumps(
            {k: (v["median"], v["p99"], v["over_0.06"], v["over_0.06_teal"], v["white_catch"]) for k, v in g.items()}), flush=True)
    print(f"LIVELY eye rim: {json.dumps(ghost['eye_rim'])}", flush=True)
    report["sclera_ghost"] = ghost
    G.write_png(out / f"{args.name}_sclera.png", W, H, (np.clip(clean, 0, 1) * 255 + 0.5).astype(np.uint8).tobytes())

    # ---- the rig: the neck's waist, the shoulders, the chin, the crest
    y = P[:, 1]
    ymin, ey = float(y.min()), float(centres[1][1])
    ys = np.arange(ymin + 0.01, ey, 0.02)
    prof = []
    for yb in ys:
        s = P[np.abs(y - yb) < 0.01]
        prof.append((float(yb), float(np.ptp(s[:, 0])) if len(s) else 0.0, float((s[:, 2].min() + s[:, 2].max()) / 2) if len(s) else 0.0,
                     float(np.ptp(s[:, 2]) / 2) if len(s) else 0.0))
    cand = [p for p in prof if ymin + 0.3 * (ey - ymin) <= p[0] <= ey - 1.2 * r and p[1] > 0]
    waist = min(cand, key=lambda p: p[1])
    below = [p for p in prof if p[0] < waist[0] and p[1] > 1.6 * waist[1]]
    shoulder = max(below, key=lambda p: p[0]) if below else prof[0]
    front = P[(y > waist[0]) & (P[:, 2] > waist[2] + 1.3 * waist[3])]
    chin = float(front[:, 1].min()) if len(front) else ey
    span = waist[0] - shoulder[0]
    if args.neck:
        y0, y1 = (float(v) for v in args.neck.split(","))
    else:
        y0, y1 = waist[0] - 0.5 * span, min(waist[0] + 0.5 * span, chin - 0.01)
    ym = (y0 + y1) / 2

    def zc(yy):
        return min(prof, key=lambda p: abs(p[0] - yy))[2]
    pos = {"Chest": (0.0, ymin, zc(shoulder[0])), "Neck": (0.0, y0, zc(y0)), "Head": (0.0, ym, zc(ym))}
    head_c = np.array([0.0, ey, zc(ey) if ey < prof[-1][0] + 0.02 else float(P[np.abs(y - ey) < 0.01][:, 2].mean())])
    if args.gills:
        rig = gill_rig(args, data, P, UV, I, pos, y0, ym, y1, head_c, out)
        report["rig"] = {"joints": {k: [round(v, 5) for v in pos[k]] for k in G.GILL_JOINTS}, "neck_y": [y0, ym, y1],
                         "waist": waist, "shoulder": shoulder, "chin_y": chin, **rig}
    else:
        top = P[(y > ey) & (np.abs(P[:, 0]) < 0.08)]
        tip = top[np.argmax(top[:, 1] - top[:, 2])]  # the crest tip: high and far back
        root = head_c + args.crest_root * (tip - head_c)
        for k in range(3):
            pos[f"Crest{k + 1}"] = tuple(float(v) for v in root + (tip - root) * k / 3.0)
        b0, b1 = (float(v) for v in args.blade.split(","))
        seg = tip - root
        # the skull: a sphere about the head centre through the crest root; only what stands out of it is crest (the
        # axis test alone also caught a strip of the back of the skull behind the root)
        r_root = float(np.linalg.norm(root - head_c))
        infl, crest_n, crest_w = [], 0, []
        for p in P:
            ch, nk, hd = G.neck_weights(float(p[1]), y0, ym, y1)
            t = float((p - root) @ seg / (seg @ seg))
            wc = G.smoothstep(0.0, 0.3, t) * (1.0 - G.smoothstep(b0, b1, abs(float(p[0])))) * hd
            wc *= G.smoothstep(r_root - args.skull_margin, r_root, float(np.linalg.norm(p - head_c)))
            crest_w.append(wc)
            crest_n += wc > 0.01
            c1, c2, c3 = G.crest_split(t)
            inf = [(j, w) for j, w in ((0, ch), (1, nk), (2, hd * (1.0 - wc)), (3, wc * c1), (4, wc * c2), (5, wc * c3))
                   if w > 1e-4]
            infl.append(inf)
        (out / f"{args.name}_lively.glb").write_bytes(G.add_skin(data, pos, infl))
        crest_view(out / "crest_weights.png", P, np.array(crest_w), head_c, r_root - args.skull_margin)
        report["rig"] = {"joints": {k: [round(v, 5) for v in pos[k]] for k in G.JOINTS}, "neck_y": [y0, ym, y1],
                         "waist": waist, "shoulder": shoulder, "chin_y": chin, "crest_root": root.round(5).tolist(),
                         "crest_tip": tip.round(5).tolist(), "crest_vertices": int(crest_n), "blade": [b0, b1],
                         "skull_radius": round(r_root - args.skull_margin, 5),
                         "crest_weight_inside_skull": round(float(max([w for w, p in zip(crest_w, P)
                                                                        if np.linalg.norm(p - head_c) <= r_root - args.skull_margin]
                                                                       or [0.0])), 6)}
        report["rig"]["springs"] = [{"name": "crest", "bones": ["Crest1", "Crest2", "Crest3"], "hz": 2.2, "zeta": 0.3,
                                     "lag": 0.09, "max_deg": 30.0}]  # AL2: an explicit cap (v4's largest swing 11.6, never clamped); 0 is no swing
    # AL5: the axolotl's head limits lowered (v4's 40 / 24: the neck stretched looking up, the far eye swivelled away),
    # the pitch spread evenly over Neck and Head, a slight roll into the turn
    report["controller"] = ({"gaze": "none", "head_hz": 2.2, "yaw_deg": 30.0, "pitch_deg": 12.0, "pitch_up_deg": 12.0,
                             "pitch_down_deg": 18.0, "neck_share": 0.4, "pitch_neck_share": 0.5, "tilt": 0.15}
                            if bead else {"gaze": "iris", "head_hz": 1.6, "yaw_deg": 35.0, "pitch_deg": 20.0, "neck_share": 0.4})
    if args.sclera_normal_map is not None:  # A3b: the rings of the sculpted iris are in the normal map, not the geometry
        report["controller"]["sclera_normal_map"] = args.sclera_normal_map
    # AL6 (PR #306 review major 3): the chameleon's grey facets under the upper lids are not in its normal map: they
    # stay with it off (controller.sclera_normal_map 0, eyes_pit_v6) and in grey geometry alone, so no build sets it
    report["sclera"] = f"{args.name}_sclera.png"
    (out / "lively.json").write_text(json.dumps(report, indent=1), encoding="utf-8", newline="\n")
    print(f"LIVELY rig neck {y0:.3f}/{ym:.3f}/{y1:.3f} waist {waist[0]:.3f} (w {waist[1]:.3f}) shoulder {shoulder[0]:.3f} "
          f"chin {chin:.3f} " + json.dumps({k: v for k, v in report["rig"].items() if k in ("crest_vertices", "gill_swing_deg")}),
          flush=True)


def gill_rig(args, data, P, UV, I, pos, y0, ym, y1, head_c, out):
    """The axolotl's six gill stalks (2026-10-23, AL1): one bone each at its root (step 2a's pivots, Blender x, y, z
    -> glTF x, z, -y), its axis the mean of its thin vertices; weights by G.stalk_weight (none at the root, none on the
    thick skull), times the head's. The poke test: each stalk's weighted vertices turned by +-swing about the head's
    yaw and pitch axes through the root as the controllers turn them (G.spring_matrix, the four axis ends and four
    corners); a moved vertex (any weight over G.TEST_W, AL6) ending inside the skull is a poke (see below); the swing is
    lowered by 1 degree from --gill-swing until none pokes (rig.gill_swing_deg, the controller's cap; none: refused). Writes <name>_lively.glb and gill_weights.png; returns the rig report (pos gets the gill joints)."""
    piv = json.loads(Path(args.gills).read_text(encoding="utf-8"))["pivots"][f"{args.name}_gills"]
    thin = load_png(args.detail)[..., 1]
    Ht, Wt = thin.shape
    tv = thin[np.clip((UV[:, 1] * Ht).astype(int), 0, Ht - 1), np.clip((UV[:, 0] * Wt).astype(int), 0, Wt - 1)]
    names = list(G.GILLS)
    roots = {}
    for name in names:
        bx, by, bz = piv[f"gill_{name[4:]}"]
        roots[name] = np.array([bx, bz, -by])
    R = np.array([roots[n] for n in names])
    near = np.argmin(np.linalg.norm(P[:, None, :] - R[None], axis=-1), axis=1)
    # AL3: a vertex belongs to the stalk it is reached from first along the mesh (gill_labels), not the nearest root:
    # by the nearest root a fin's tip leaning toward the next stalk's root went to that stalk and tore at 15 degrees
    near, reached = gill_labels(P, I, R, near)
    dist = np.linalg.norm(P - R[near], axis=1)
    rep, W = {"gills": {}}, np.zeros((len(P), len(names)))
    stalk = np.zeros(len(P), bool)  # every stalk's geometry out of the skull, the thick base too (not the skull)
    hd = np.array([G.neck_weights(float(v), y0, ym, y1)[2] for v in P[:, 1]])
    # AL4: the weights live on the welded vertices (a UV seam's copies read the detail map apart: the thickest copy
    # alone would hold the others still), the thinness is the copies' largest
    weld, edges = weld_edges(P, I)
    nw = int(weld.max()) + 1
    tvw = np.zeros(nw)
    np.maximum.at(tvw, weld, tv)
    rad = np.linalg.norm(P - head_c, axis=1)
    lab_w = np.zeros(nw, int)
    lab_w[weld] = near
    first = np.full(nw, -1)
    first[weld[::-1]] = np.arange(len(P))[::-1]
    rep["gill_weight_rule"] = {"lift_in": G.LIFT_IN, "lift_full": G.LIFT_FULL, "smooth_passes": G.SMOOTH_PASSES,
                               "smooth_alpha": G.SMOOTH_ALPHA}
    stalks = {}
    for k, name in enumerate(names):
        cand = (near == k) & (tv > 0.5) & (dist < 0.45)
        if cand.sum() < 20:
            raise SystemExit(f"LIVELY gill {name}: only {int(cand.sum())} thin vertices near its root")
        ax = (P[cand] - roots[name]).mean(0)
        ax /= np.linalg.norm(ax)
        sp = (P[cand] - roots[name]) @ ax
        length = float(np.percentile(sp, 98))
        own = (near == k) & (dist < 1.3 * length)
        snap = float(np.linalg.norm(P - roots[name], axis=1).min())
        # the stalk: near its root, farther from the head's centre than the skull there (the root's depth and 2 cm)
        stalk |= own & (np.linalg.norm(P - head_c, axis=1) > np.linalg.norm(roots[name] - head_c) + snap + 0.02)
        stalks[name] = (ax, length, own, snap)
    # AL6: the skull proxy built before the weights (no thin vertex, no stalk vertex), so the skull's own weight is
    # measured on it (PR #306 review minor 4); with --gill-lift skull the lift is the height over its surface (AL5:
    # the distance from the head's centre read 0 far out on fins that hang back toward the head)
    thick_v = (tvw[weld] <= 0.25) & ~stalk
    skull0_t = [tuple(int(x) for x in t) for t in I if thick_v[t].all()]
    skull0 = BVHTree.FromPolygons([Vector(v) for v in P], skull0_t, all_triangles=True)
    anyown = np.zeros(len(P), bool)
    for _ax, _l, own, _s in stalks.values():
        anyown |= own
    # AL7: both lifts are weighed, so the poke test compares them like for like on the same skull (PR #306
    # re-review); the rig is the --gill-lift one
    skull_v = np.zeros(len(P), bool)
    skull_v[np.array(skull0_t, int).ravel()] = True
    hgt = np.zeros(len(P))
    for i in np.nonzero(anyown)[0]:
        hgt[i] = skull0.find_nearest(Vector(P[i]))[3]
    rep["gill_lift"] = args.gill_lift

    def weights(mode):
        Wm = np.zeros((len(P), len(names)))
        for k, name in enumerate(names):
            ax, length, own, snap = stalks[name]
            s_ = (P - roots[name]) @ ax
            # AL4: the ramp along the stalk, gated by thinness or by the vertex's lift over the skull at the root (the
            # stalk's thick core and the fins the detail map reads thick moved not at all beside fringe weighted 1.0:
            # the v3 tear, 99 mm), then smoothed inside this stalk alone, the zeros (skull, root band) pinned; AL6:
            # skull takes the height over the skull proxy instead of the distance from the head's centre beyond the root's
            r0 = float(rad[int(np.argmin(np.linalg.norm(P - roots[name], axis=1)))])
            lift = hgt if mode == "skull" else rad - r0
            # AL7: centre_pinned is the centre lift with the skull proxy's root bulge pinned at 0 (no skull moves)
            pin = skull_v if mode == "centre_pinned" else np.zeros(len(P), bool)
            w0 = [G.stalk_weight_lifted(float(s_[i]), length, float(tvw[j]), float(lift[i])) if own[i] and not pin[i]
                  else 0.0 for j, i in enumerate(first)]
            ws = G.smooth_within(w0, edges, lab_w.tolist(), k, [v == 0.0 for v in w0])
            Wm[:, k] = np.array(ws)[weld] * hd
        tot = Wm.sum(1)
        over = tot > 1.0
        Wm[over] /= tot[over][:, None]
        return Wm

    lifts = {mode: weights(mode) for mode in G.GILL_LIFTS}
    W = lifts[args.gill_lift]
    for k, name in enumerate(names):
        ax, length, own, snap = stalks[name]
        pos[name] = tuple(float(v) for v in roots[name])
        rep["gills"][name] = {"root": roots[name].round(5).tolist(), "axis": ax.round(4).tolist(), "length": round(length, 4),
                              "vertices": int((W[:, k] > 0.01).sum()), "root_to_mesh_mm": round(snap * 1000, 2)}
    # the head the gills must not poke into: AL7, the skull proxy built before the weights (skull0_t: no thin and no
    # stalk vertex), posed with its own weights at each swing corner. AL2 to AL6 tested against the triangles with no
    # vertex weighted over 0.01, which dropped the root bulge (178 weighted vertices on the axolotl): a hole where the
    # pokes would be, and a skull that differed between the lifts (PR #306 re-review, major). AL2: the old test
    # (behind the nearest triangle's plane) misread a hole's edges; the skull is a star about head_c: a point is inside
    # when it is nearer head_c than the skull's outermost surface along the same ray, by more than POKE_TOL (and, AL3,
    # behind the nearest skull triangle). AL2: the stalks' thick static bases are no skull either (else their
    # triangles stand beyond the moving filaments along the rays and read as "inside")
    cv = Vector(head_c)

    def tests(bvh):
        def skull_r(p):
            d = Vector(p) - cv
            far = d.length + 0.5
            d.normalize()
            o, r = cv, 0.0
            for _ in range(16):  # the outermost crossing along the ray
                loc, _n, _i, dist = bvh.ray_cast(o, d, far)
                if loc is None:
                    break
                r = (loc - cv).length
                o = loc + d * 1e-5
            return r

        def inside_star(pts):
            return np.array([np.linalg.norm(pp - head_c) < skull_r(pp) - G.POKE_TOL for pp in pts], bool)

        # AL3: the star test alone is no proof. Its 40 "pokes" at 15 degrees (gill_pokes_diag.json) were all stalk-base
        # vertices 4 to 16 mm off the skull at rest, every one in front of its nearest skull triangle: near a stalk's
        # root the skull is no star about head_c (the ray crosses the rim of the bulge the stalk grows from). A poke is
        # inside by both tests: the star's, and more than POKE_TOL behind the nearest skull triangle
        def behind(pp):
            near, nrm, _i, _d = bvh.find_nearest(Vector(pp))
            return near is not None and (Vector(pp) - near).dot(nrm) < -G.POKE_TOL

        def inside(pts):  # behind first (a nearest-point query), the star's ray casts only where behind
            pts = np.asarray(pts)
            b = np.array([behind(pp) for pp in pts], bool)
            out_ = np.zeros(len(pts), bool)
            if b.any():
                out_[np.nonzero(b)[0]] = inside_star(pts[b])
            return out_
        return skull_r, inside_star, inside, behind

    skull_r, inside_star, inside, behind = tests(skull0)

    def corner_pose(Wm, k, swing, y, p):  # the whole mesh, stalk k alone turned to a corner as its bone turns it
        q = P - roots[names[k]]
        rq = q @ np.array(G.spring_matrix(math.radians(swing) * y, math.radians(swing) * p)).T
        return P + Wm[:, k][:, None] * (rq - q)

    def corner_inside(Wm, k, Pp):  # the inside test against the skull proxy posed as Pp (the rest one if unweighted)
        if not (Wm[skull_v, k] > 0.0).any():
            return inside
        return tests(BVHTree.FromPolygons([Vector(v) for v in Pp], skull0_t, all_triangles=True))[2]

    # AL6 (PR #306 review major 2): every moved vertex weighted over G.TEST_W is tested, the root band and the
    # vertices near the skull at rest too; only the vertices already inside the skull at rest are left out, and
    # counted; AL7: the proxy's own vertices (the root bulge) are the skull itself and move with it, so not tested
    skull_idx = np.nonzero(skull_v)[0]
    skull_kd = KDTree(len(skull_idx))
    for j in skull_idx:
        skull_kd.insert(Vector(P[j]), int(j))
    skull_kd.balance()
    skull_edge = float(max(np.linalg.norm(P[a_] - P[b_]) for t in skull0_t for a_, b_ in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0]))))

    def scan(Wm):
        test, rest_inside, buried = {}, {}, {}
        for k, name in enumerate(names):
            m = np.nonzero((Wm[:, k] > G.TEST_W) & ~skull_v)[0]
            # AL7: a vertex behind its nearest skull triangle at rest whose distance to the skull is larger than its
            # own reach at the top swing (the largest of the 8 corners) plus the posed bulge's (this gill's skull
            # vertices' largest move) cannot cross the skull's surface, so it stays on the side it is on: no poke; it
            # is left out and counted. With the root bulge in the skull, the centre rig's one poke at every swing
            # from 2 to 15 degrees was GillR2's vertex 7862 (weight 0.065), 7.25 mm under the skull at rest, moving
            # 0.16 to 1.56 mm while the star test's crossing near the bulge's rim flipped (AL3's flaw). Every vertex
            # behind at rest, however near the surface, left out 5744 (tried, not kept)
            top = min(args.gill_swing, G.SPRING_MAX_DEG)
            moves = [np.linalg.norm(corner_pose(Wm, k, top, y, p) - P, axis=1) for y, p in G.SWING_CORNERS]
            reach = np.max([mv[m] for mv in moves], axis=0)
            skull_reach = float(max(mv[skull_v].max(initial=0.0) for mv in moves))
            moves_max = np.max(moves, axis=0)
            bur = np.zeros(len(m), bool)
            for t, pp in enumerate(P[m]):
                nr, nrm, _i, gap = skull0.find_nearest(Vector(pp))
                if nr is None or (Vector(pp) - nr).dot(nrm) >= 0 or gap <= reach[t] + G.POKE_TOL:
                    continue
                # only the skull points whose rest place lies within this vertex's reach plus the bulge's largest move
                # can meet it (a triangle's point moves no more than its corners), so the bulge's move there counts
                near_s = [j for _c, j, _d in skull_kd.find_range(pp, reach[t] + skull_reach + skull_edge)]
                local = max((float(moves_max[j]) for j in near_s), default=0.0)
                bur[t] = gap > reach[t] + local + G.POKE_TOL
            at_rest = inside(P[m]) | bur
            buried[name] = int((bur & ~inside(P[m])).sum())
            test[k] = m[~at_rest]
            rest_inside[name] = int(at_rest.sum())

        rows = {}

        def pokes(swing):
            n = 0
            for k in range(len(names)):
                m = test[k]
                for y, p in G.SWING_CORNERS:
                    Pp = corner_pose(Wm, k, swing, y, p)
                    mm = m[np.linalg.norm(Pp[m] - P[m], axis=1) > G.MOVED_EPS]
                    hit = mm[corner_inside(Wm, k, Pp)(Pp[mm])]
                    n += len(hit)
                    for i in hit[:40]:  # AL7 diag: the poke, its weight, its rest gap and the nearest bulge's weight
                        nr, nrm, _t, gap = skull0.find_nearest(Vector(P[i]))
                        j = int(np.argmin(np.where(skull_v, np.linalg.norm(P - P[i], axis=1), 9.0)))
                        rows.setdefault(f"{swing:g}", []).append({
                            "gill": names[k], "corner": [y, p], "v": int(i), "w": round(float(Wm[i, k]), 3),
                            "tv": round(float(tv[i]), 3), "rest_gap_mm": round(gap * 1000 * (1 if (Vector(P[i]) - nr).dot(nrm) >= 0 else -1), 2),
                            "nearest_skull_v_w": round(float(Wm[j, k]), 3), "moved_mm": round(float(np.linalg.norm(Pp[i] - P[i])) * 1000, 2)})
            return n
        swing, counts = min(args.gill_swing, G.SPRING_MAX_DEG), {}
        while swing > 0:
            counts[f"{swing:g}"] = pokes(swing)
            if counts[f"{swing:g}"] == 0:
                break
            swing -= 1.0
        return {"test": test, "rest_inside": rest_inside, "swing": max(swing, 0.0), "counts": counts, "pokes": pokes,
                "rows": rows, "buried": buried}

    res = {mode: scan(Wm) for mode, Wm in lifts.items()}
    for mode, x in res.items():
        print(f"LIVELY gill pokes {mode}: cap {x['swing']:g} by swing {x['counts']} inside at rest "
              f"{sum(x['rest_inside'].values())}", flush=True)
    (out / "gill_pokes_posed.json").write_text(json.dumps({m_: x["rows"] for m_, x in res.items()}, indent=1),
                                               encoding="utf-8", newline="\n")
    r = res[args.gill_lift]
    test, rest_inside, swing, counts = r["test"], r["rest_inside"], r["swing"], r["counts"]
    rep["skull_proxy"] = {"triangles": len(skull0_t), "posed": "the root bulge with its own weights at each corner (AL7)",
                          "max_r": round(float(np.linalg.norm(P[skull_v] - head_c, axis=1).max()), 4)}
    rep["gill_poke_tested"] = {n: int(len(test[k])) for k, n in enumerate(names)}
    rep["gill_poke_excluded_inside_at_rest"] = rest_inside
    rep["gill_pokes_by_lift"] = {mode: {"swing_deg": x["swing"], "pokes_by_swing": x["counts"],
                                        "inside_at_rest": sum(x["rest_inside"].values()),
                                        "of_which_buried_only": sum(x["buried"].values()),
                                        "tested": sum(len(t) for t in x["test"].values())} for mode, x in res.items()}
    for other in (m_ for m_ in res if m_ != args.gill_lift):  # the other lifts at this rig's cap, like for like
        if swing > 0 and f"{swing:g}" not in res[other]["counts"]:
            rep["gill_pokes_by_lift"][other]["pokes_at_rig_cap"] = res[other]["pokes"](swing)
    # the diag (the star test alone, against the rest skull proxy: the bulge unposed) at the top swing
    poke_diag(out, names, test, W, P, roots, head_c, skull0, skull_r, inside_star, min(args.gill_swing, G.SPRING_MAX_DEG))
    if swing <= 0:
        dump = []
        for k, name in enumerate(names):
            m = test[k]
            for y, p in G.SWING_CORNERS:
                Pp = corner_pose(W, k, 1.0, y, p)
                hit = corner_inside(W, k, Pp)(Pp[m])
                for i, pp in zip(m[hit], Pp[m][hit]):
                    dump.append({"gill": name, "v": int(i), "rest": P[i].round(4).tolist(), "tv": round(float(tv[i]), 3),
                                 "w": round(float(W[i, k]), 3), "r": round(float(np.linalg.norm(pp - head_c)), 4),
                                 "skull_r": round(skull_r(pp), 4)})
        (out / "gill_pokes.json").write_text(json.dumps({"head_c": head_c.round(4).tolist(), "pokes_1deg": dump[:400],
                                                        "n": len(dump)}, indent=1), encoding="utf-8", newline="\n")
        raise SystemExit(f"LIVELY gills poke into the head at every swing tested: {counts}")
    rep["gill_swing_deg"] = float(swing)
    rep["gill_labels_reached"] = round(reached, 4)
    rep["gill_stretch_mm"] = gill_stretch(P, I, W, roots, names, swing, diag=(tv, near, out))
    print(f"LIVELY gill labels reached {reached:.4f}, stretch {rep['gill_stretch_mm']} mm at {swing:g} degrees", flush=True)
    rep["gill_pokes_by_swing"] = counts
    # the skull proxy's own vertices (the triangles with no thin and no stalk vertex, built before the weights) must
    # stay still; AL6: AL4's "thick" share (0.9998) is gone, the stalks' thick cores move by design
    # AL7: the root bulge (the skull proxy's vertices within a stalk's own reach) carries weight by design and is
    # posed in the poke test; the open skull (the rest of the proxy) must carry none
    wsum = W.sum(1)
    bulge_v, open_v = skull_v & anyown, skull_v & ~anyown
    rep["gill_weight_on_root_bulge"] = round(float(wsum[bulge_v].max(initial=0.0)), 6)
    rep["gill_weight_on_open_skull"] = round(float(wsum[open_v].max(initial=0.0)), 6)
    rep["skull_proxy_pre_weights"] = {"triangles": len(skull0_t), "vertices": int(skull_v.sum()),
                                      "root_bulge_vertices": int(bulge_v.sum()),
                                      "vertices_weighted_over_0.01": int((wsum[skull_v] > 0.01).sum())}
    infl = []
    for i in range(len(P)):
        ch, nk, h = G.neck_weights(float(P[i, 1]), y0, ym, y1)
        g = W[i]
        inf = [(j, w) for j, w in ((0, ch), (1, nk), (2, h * (1.0 - g.sum()))) if w > 1e-4]
        inf += [(3 + k, float(g[k])) for k in range(len(names)) if g[k] > 1e-4]
        infl.append(inf)
    (out / f"{args.name}_lively.glb").write_bytes(G.add_skin(data, pos, infl, joints=G.GILL_JOINTS, parents=G.GILL_PARENTS))
    crest_view(out / "gill_weights.png", P, np.clip(W.sum(1), 0, 1), head_c, 0.0)
    hz = (2.3, 2.0, 1.8, 2.4, 2.1, 1.9)  # each stalk its own rate, so they never swing in step
    rep["springs"] = [{"name": n, "bones": [n], "hz": hz[k], "zeta": 0.28, "lag": 0.11, "max_deg": rep["gill_swing_deg"]}
                      for k, n in enumerate(names)]
    print(f"LIVELY gills: lift {args.gill_lift} swing {rep['gill_swing_deg']} pokes {counts} tested {rep['gill_poke_tested']} "
          f"inside at rest {rest_inside} root bulge {rep['gill_weight_on_root_bulge']} open skull {rep['gill_weight_on_open_skull']} " + json.dumps(
        {n: (g["vertices"], g["length"], g["root_to_mesh_mm"]) for n, g in rep["gills"].items()}), flush=True)
    return rep


def weld_edges(P, I):
    """The vertices welded by position (1e-5 m) and the welded mesh's unique edges: (weld index per vertex, edges)."""
    key = np.round(P / 1e-5).astype(np.int64)
    _u, weld = np.unique(key, axis=0, return_inverse=True)
    weld = weld.reshape(-1)
    T = weld[np.asarray(I).reshape(-1, 3)]
    E = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]])
    E = np.unique(np.sort(E[E[:, 0] != E[:, 1]], axis=1), axis=0)
    return weld, [(int(a), int(b)) for a, b in E]


def gill_labels(P, I, R, near):
    """Each vertex's gill by a multi-source Dijkstra over the mesh's edges (vertices welded by position, so UV
    seams do not cut it) from the vertex nearest each root; vertices no front reaches keep near (the nearest root).
    Returns (labels, the share reached)."""
    import heapq
    key = np.round(P / 1e-5).astype(np.int64)
    _u, weld = np.unique(key, axis=0, return_inverse=True)
    weld = weld.reshape(-1)
    n = int(weld.max()) + 1
    Q = np.zeros((n, 3))
    Q[weld] = P
    adj = [[] for _ in range(n)]
    for t in np.asarray(I).reshape(-1, 3):
        a, b, c = (int(weld[x]) for x in t)
        for u, v in ((a, b), (b, c), (c, a)):
            if u != v:
                adj[u].append(v)
                adj[v].append(u)
    best = np.full(n, np.inf)
    lab = np.full(n, -1)
    heap = []
    for k, r in enumerate(R):
        s0 = int(np.argmin(np.linalg.norm(Q - r, axis=1)))
        best[s0], lab[s0] = 0.0, k
        heap.append((0.0, s0, k))
    heapq.heapify(heap)
    while heap:
        d, u, k = heapq.heappop(heap)
        if d > best[u]:
            continue
        for v in adj[u]:
            nd = d + float(np.sqrt(((Q[u] - Q[v]) ** 2).sum()))
            if nd < best[v]:
                best[v], lab[v] = nd, k
                heapq.heappush(heap, (nd, v, k))
    out = lab[weld]
    ok = out >= 0
    return np.where(ok, out, near), float(ok.mean())


def gill_stretch(P, I, W, roots, names, swing, diag=None):
    """The tear measure (AL3): the largest change of an edge's length (mm) when the gills sit at opposite cap corners
    (even gills at a corner, odd ones at its opposite, and the other way), the worst of the 8 corners; a fin split
    between two stalks tears here."""
    E = np.asarray(I).reshape(-1, 3)
    E = np.concatenate([E[:, [0, 1]], E[:, [1, 2]], E[:, [2, 0]]])
    E = E[(W[E[:, 0]].sum(1) > 0.01) | (W[E[:, 1]].sum(1) > 0.01)]
    rest = np.linalg.norm(P[E[:, 0]] - P[E[:, 1]], axis=1)
    worst, worst_ch, worst_corner = 0.0, np.zeros(len(E)), None
    for y, p in G.SWING_CORNERS:
        for flip in (1, -1):
            Q = P.copy()
            for k, name in enumerate(names):
                sg = flip if k % 2 == 0 else -flip
                q = P - roots[name]
                rq = q @ np.array(G.spring_matrix(math.radians(swing) * y * sg, math.radians(swing) * p * sg)).T
                Q += W[:, k][:, None] * (rq - q)
            ch = np.abs(np.linalg.norm(Q[E[:, 0]] - Q[E[:, 1]], axis=1) - rest)
            if float(ch.max()) > worst:
                worst, worst_ch, worst_corner = float(ch.max()), ch, (y, p, flip)
    if diag is not None:
        tv, lab, out = diag
        top = np.argsort(-worst_ch)[:60]
        rows = []
        for e in top:
            a, b = (int(x) for x in E[e])
            rows.append({"mm": round(float(worst_ch[e]) * 1000, 2), "rest_mm": round(float(rest[e]) * 1000, 2),
                         "v": [a, b], "label": [names[int(lab[a])], names[int(lab[b])]],
                         "tv": [round(float(tv[a]), 3), round(float(tv[b]), 3)],
                         "w": [{names[k]: round(float(W[i, k]), 3) for k in range(len(names)) if W[i, k] > 1e-3} for i in (a, b)],
                         "rest": [P[a].round(4).tolist(), P[b].round(4).tolist()]})
        (out / "gill_stretch.json").write_text(json.dumps({"worst_mm": round(worst * 1000, 2), "corner": worst_corner,
                                                          "edges": rows}, indent=1), encoding="utf-8", newline="\n")
        mark = np.zeros(len(P))
        for e in np.nonzero(worst_ch > 0.005)[0]:
            mark[E[e]] = 1.0
        crest_view(out / "gill_stretch.png", P, mark, Q[0] * 0 + P.mean(0), 0.0)
    return round(worst * 1000, 2)


def poke_diag(out, names, test, W, P, roots, head_c, bvh, skull_r, inside, swing):
    """AL3: why the gills "poke": every star-test poke (inside: the star test alone) at the top swing (each gill,
    each of the 8 corners) with its rest gap to the skull proxy, the moved point's nearest skull point (gap, and whether it lies behind that triangle: a real
    contact), the outermost crossing the star test compared against (its distance from the point: a far crossing is a
    test flaw, the ray meeting another part of the body), into gill_pokes_diag.json; gill_pokes_diag.png: per gill
    its worst corner as a cross-section (the skull proxy's vertices within 2 cm of the plane through the root, the
    stalk's axis and the head's centre, grey; the stalk at rest blue; the poking points moved red, at rest cyan,
    their crossings yellow), 6 panels of 420 px."""
    rows, worst = [], {}
    cv = Vector(head_c)
    for k, name in enumerate(names):
        m = test[k]
        q = P[m] - roots[name]
        for y, p in G.SWING_CORNERS:
            rq = q @ np.array(G.spring_matrix(math.radians(swing) * y, math.radians(swing) * p)).T
            d = W[m, k][:, None] * (rq - q)
            moved = np.linalg.norm(d, axis=1) > 0.0005
            p2 = P[m] + d
            hit = moved & inside(p2)
            worst.setdefault(name, (0, None))
            if hit.sum() > worst[name][0]:
                worst[name] = (int(hit.sum()), (y, p), m[hit], p2[hit])
            for i, pp in zip(m[hit], p2[hit]):
                near, nrm, _i, gap = bvh.find_nearest(Vector(pp))
                behind = (Vector(pp) - near).dot(nrm) < 0
                dr = (Vector(pp) - cv).normalized()
                rr = skull_r(pp)
                cross = cv + dr * rr
                rows.append({"gill": name, "corner": [y, p], "v": int(i), "w": round(float(W[i, k]), 3),
                             "rest_gap_mm": round((Vector(P[i]) - bvh.find_nearest(Vector(P[i]))[0]).length * 1000, 1),
                             "moved_mm": round(float(np.linalg.norm(pp - P[i])) * 1000, 1),
                             "gap_mm": round(gap * 1000, 1), "behind_nearest": bool(behind),
                             "depth_mm": round((rr - float(np.linalg.norm(pp - head_c))) * 1000, 1),
                             "crossing_from_point_mm": round((cross - Vector(pp)).length * 1000, 1),
                             "crossing": [round(c, 4) for c in cross]})
    real = [r for r in rows if r["behind_nearest"] and r["gap_mm"] < 5.0]
    summary = {"swing_deg": swing, "pokes": len(rows), "behind_nearest_within_5mm": len(real),
               "crossing_from_point_mm": {"min": min((r["crossing_from_point_mm"] for r in rows), default=None),
                                          "median": float(np.median([r["crossing_from_point_mm"] for r in rows])) if rows else None},
               "gap_mm": {"min": min((r["gap_mm"] for r in rows), default=None),
                          "median": float(np.median([r["gap_mm"] for r in rows])) if rows else None},
               "rest_gap_mm_min": min((r["rest_gap_mm"] for r in rows), default=None),
               "by_gill": {n: sum(r["gill"] == n for r in rows) for n in names},
               "worst_corner": {n: list(v[1]) if v[1] else None for n, v in worst.items()}}
    (out / "gill_pokes_diag.json").write_text(json.dumps({"summary": summary, "pokes": rows}, indent=1),
                                              encoding="utf-8", newline="\n")
    print("LIVELY gill poke diag: " + json.dumps(summary), flush=True)
    size = 420
    img = np.full((2 * size, 3 * size, 3), 40, np.uint8)
    for k, name in enumerate(names):
        r0 = roots[name]
        m_all = np.nonzero(W[:, k] > 0.01)[0]
        ax = (P[m_all] - r0).mean(0)
        ax /= np.linalg.norm(ax)
        rad = r0 - head_c
        nrm = np.cross(ax, rad)
        nrm /= np.linalg.norm(nrm)
        u = ax
        v = np.cross(nrm, u)
        ctr = r0 + ax * 0.12
        span = 0.42
        if worst[name][1] is not None:  # zoomed on the pokes (8 cm)
            ctr, span = worst[name][3].mean(0), 0.08

        def to_px(pts):
            d = pts - ctr
            return ((d @ u / span + 0.5) * (size - 1)).astype(int), ((0.5 - d @ v / span) * (size - 1)).astype(int)
        ox, oy = (k % 3) * size, (k // 3) * size
        sk = np.nonzero((np.abs((P - r0) @ nrm) < 0.02) & (W.sum(1) <= 0.01) & (np.linalg.norm(P - ctr, axis=1) < span))[0]
        hits = [bvh.find_nearest(Vector(P[i])) for i in sk]
        sk = sk[np.array([h[3] < 0.0015 for h in hits], bool)] if len(sk) else sk
        layers = [(P[sk], (150, 150, 150), 0), (P[m_all], (60, 110, 230), 0)]
        if worst[name][1] is not None:
            _n, _c, idx, moved = worst[name]
            cross = np.array([head_c + (pp - head_c) / np.linalg.norm(pp - head_c) * skull_r(pp) for pp in moved])
            layers += [(P[idx], (0, 230, 230), 1), (moved, (255, 40, 40), 1), (cross, (255, 230, 0), 1)]
        for pts, col, big in layers:
            if not len(pts):
                continue
            x, y = to_px(pts)
            for dx in range(-big, big + 1):
                for dy in range(-big, big + 1):
                    ok = (x + dx >= 0) & (x + dx < size) & (y + dy >= 0) & (y + dy < size)
                    img[oy + y[ok] + dy, ox + x[ok] + dx] = col
        img[oy:oy + size, ox] = (90, 90, 90)
        img[oy, ox:ox + size] = (90, 90, 90)
    G.write_png(out / "gill_pokes_diag.png", 3 * size, 2 * size, img.tobytes())


def crest_view(path, P, w, head_c, r_skull, size=640):
    """The crest weights' proof (1280 x 640): the head from its right side (-X, the face to the right)
    and from behind (-Z), every vertex a
    dot, grey shaded by depth, red by its crest weight, the skull sphere's outline in blue."""
    img = np.full((size, 2 * size, 3), 60, np.uint8)
    lo = P.min(0) - 0.05
    span = float((P.max(0) - P.min(0)).max()) + 0.1
    for k, (u, v, dpt, sgn) in enumerate(((2, 1, 0, -1.0), (0, 1, 2, -1.0))):
        zb = np.full((size, size), -np.inf)
        cu = ((P[:, u] - lo[u]) / span * (size - 1)).astype(int) if k == 0 else             ((-P[:, u] - (-P[:, u]).min() + 0.05) / span * (size - 1)).astype(int)
        cv = (size - 1 - (P[:, v] - lo[v]) / span * (size - 1)).astype(int)
        z = P[:, dpt] * sgn
        zn = (z - z.min()) / (np.ptp(z) or 1.0)
        for i in np.argsort(z):
            for du in (0, 1):
                for dv in (0, 1):
                    x, y = cu[i] + du, cv[i] + dv
                    if 0 <= x < size and 0 <= y < size and z[i] >= zb[y, x]:
                        zb[y, x] = z[i]
                        g = 70 + 150 * zn[i]
                        img[y, x + k * size] = (g + (255 - g) * w[i], g * (1 - w[i]), g * (1 - w[i]))
        # the skull sphere's outline (its silhouette in this view)
        cx = (head_c[u] - lo[u]) / span * (size - 1) if k == 0 else (-head_c[u] - (-P[:, u]).min() + 0.05) / span * (size - 1)
        cy = size - 1 - (head_c[v] - lo[v]) / span * (size - 1)
        rr = r_skull / span * (size - 1)
        for a in np.linspace(0, 2 * math.pi, 720):
            x, y = int(cx + rr * math.cos(a)), int(cy + rr * math.sin(a))
            if 0 <= x < size and 0 <= y < size:
                img[y, x + k * size] = (60, 120, 255)
    G.write_png(path, 2 * size, size, img.tobytes())


if __name__ == "__main__":  # R2: test_alien_lively_cut imports the module
    main()
