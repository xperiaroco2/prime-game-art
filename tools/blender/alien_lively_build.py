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
    ap.add_argument("--neck", default="", help="y0,y1 of the neck blend (default: from the neck's waist)")
    ap.add_argument("--crest-root", type=float, default=0.45, help="the crest root between the head centre and tip")
    ap.add_argument("--blade", default="0.10,0.16", help="the crest blade's half width: full weight, none")
    ap.add_argument("--no-pit-fix", action="store_true", help="the v2 build: the eyeballs as sculpted, the old fill")
    ap.add_argument("--skull-margin", type=float, default=0.06,
                    help="the crest weight fades in over this distance below the crest root's radius from the head centre")
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
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
        G.write_vec3(doc, binary, prim["attributes"]["POSITION"], P.tolist())
        G.write_vec3(doc, binary, prim["attributes"]["NORMAL"], N1.tolist())
        G.write_floats(doc, binary, prim["attributes"]["TANGENT"], T1.tolist())
        data = G.write_glb(doc, binary)
        cen = P[I].mean(1)
        residual_view(out / "eye_residual.png", P, I, views)
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
        ins = (l1 >= -0.03) & (l2 >= -0.03) & (1.0 - l1 - l2 >= -0.03)  # a slight overdraw closes the seams
        if ins.any():
            l1, l2 = l1[ins, None], l2[ins, None]
            posmap[gy[ins].astype(int), gx[ins].astype(int)] = l1 * P[I[t, 0]] + l2 * P[I[t, 1]] + (1 - l1 - l2) * P[I[t, 2]]
    has_pos = ~np.isnan(posmap[..., 0])
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
    report["controller"] = ({"gaze": "none", "head_hz": 2.2, "yaw_deg": 40.0, "pitch_deg": 24.0, "neck_share": 0.4}
                            if bead else {"gaze": "iris", "head_hz": 1.6, "yaw_deg": 35.0, "pitch_deg": 20.0, "neck_share": 0.4})
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
    corners); a moved vertex outside the root band ending inside the skull is a poke (see below); the swing is
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
    for k, name in enumerate(names):
        cand = (near == k) & (tv > 0.5) & (dist < 0.45)
        if cand.sum() < 20:
            raise SystemExit(f"LIVELY gill {name}: only {int(cand.sum())} thin vertices near its root")
        ax = (P[cand] - roots[name]).mean(0)
        ax /= np.linalg.norm(ax)
        sp = (P[cand] - roots[name]) @ ax
        length = float(np.percentile(sp, 98))
        own = (near == k) & (dist < 1.3 * length)
        s_ = (P - roots[name]) @ ax
        W[:, k] = np.array([G.stalk_weight(float(a), length, float(t)) if o else 0.0 for a, t, o in zip(s_, tv, own)]) * hd
        pos[name] = tuple(float(v) for v in roots[name])
        snap = float(np.linalg.norm(P - roots[name], axis=1).min())
        # the stalk: near its root, farther from the head's centre than the skull there (the root's depth and 2 cm)
        stalk |= own & (np.linalg.norm(P - head_c, axis=1) > np.linalg.norm(roots[name] - head_c) + snap + 0.02)
        rep["gills"][name] = {"root": roots[name].round(5).tolist(), "axis": ax.round(4).tolist(), "length": round(length, 4),
                              "vertices": int((W[:, k] > 0.01).sum()), "root_to_mesh_mm": round(snap * 1000, 2)}
    tot = W.sum(1)
    over = tot > 1.0
    W[over] /= tot[over][:, None]
    # the head the gills must not poke into: its thick triangles (the skull and face, none of the thin gill fins and
    # stalk roots). AL2: the old test (behind the nearest triangle's plane) read thousands of pokes even at 2 degrees:
    # beside the hole the dropped root triangles leave, the nearest point is a hole edge whose plane says nothing. Now
    # the skull is a star about head_c: a point is inside when it is nearer head_c than the skull's outermost surface
    # along the same ray, by more than POKE_TOL; the root band (vertices within ROOT_BAND of the skull at rest, the
    # stalks' bases that touch it by construction, and those inside it at rest) is left out; only moved vertices count.
    # AL2: the stalks' thick static bases are no skull either (else their triangles stand beyond the moving filaments
    # along the rays and read as "inside")
    gill_v = (W.sum(1) > 0.01) | (tv > 0.25) | stalk
    body_t = [tuple(int(x) for x in t) for t in I if not gill_v[t].any()]
    bvh = BVHTree.FromPolygons([Vector(v) for v in P], body_t, all_triangles=True)
    cv = Vector(head_c)

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
    # vertices (weight 0.35 to 0.54) 4 to 16 mm off the skull at rest, every one in front of its nearest skull
    # triangle (0.3 to 7 mm off it): near a stalk's root the skull is no star about head_c (the ray crosses the rim of
    # the bulge the stalk grows from, 1.5 to 19 mm further out). A poke is now inside by both tests: the star's, and
    # more than POKE_TOL behind the nearest skull triangle (which alone misread the hole edges, AL2)
    def behind(pp):
        near, nrm, _i, _d = bvh.find_nearest(Vector(pp))
        return near is not None and (Vector(pp) - near).dot(nrm) < -G.POKE_TOL

    def inside(pts):
        star = inside_star(pts)
        return np.array([bool(a) and behind(pp) for a, pp in zip(star, pts)], bool)

    test = {}
    for k in range(len(names)):
        m = np.nonzero(W[:, k] > G.ROOT_W)[0]  # the weight's root band left out: the stalk's base (see G.ROOT_W)
        gap = np.array([(Vector(P[i]) - bvh.find_nearest(Vector(P[i]))[0]).length for i in m])
        keep = m[(gap > G.ROOT_BAND) & ~inside(P[m])]
        test[k] = keep
    rep["skull_proxy"] = {"triangles": len(body_t), "max_r": round(float(max(np.linalg.norm(P[list(t)] - head_c, axis=1).max()
                                                                       for t in body_t)), 4)}
    rep["gill_poke_tested"] = {n: int(len(test[k])) for k, n in enumerate(names)}

    def pokes(swing):
        n = 0
        for k, name in enumerate(names):
            m = test[k]
            q = P[m] - roots[name]
            for y, p in G.SWING_CORNERS:
                rq = q @ np.array(G.spring_matrix(math.radians(swing) * y, math.radians(swing) * p)).T
                d = W[m, k][:, None] * (rq - q)
                moved = np.linalg.norm(d, axis=1) > 0.0005
                n += int(inside(P[m][moved] + d[moved]).sum())
        return n
    poke_diag(out, names, test, W, P, roots, head_c, bvh, skull_r, inside_star, min(args.gill_swing, G.SPRING_MAX_DEG))
    swing, counts = min(args.gill_swing, G.SPRING_MAX_DEG), {}
    while swing > 0:
        counts[f"{swing:g}"] = pokes(swing)
        if counts[f"{swing:g}"] == 0:
            break
        swing -= 1.0
    if swing <= 0:
        dump = []
        for k, name in enumerate(names):
            m = test[k]
            q = P[m] - roots[name]
            for y, p in G.SWING_CORNERS:
                rq = q @ np.array(G.spring_matrix(math.radians(1.0) * y, math.radians(1.0) * p)).T
                p2 = P[m] + W[m, k][:, None] * (rq - q)
                for i, pp in zip(m[inside(p2)], p2[inside(p2)]):
                    dump.append({"gill": name, "v": int(i), "rest": P[i].round(4).tolist(), "tv": round(float(tv[i]), 3),
                                 "w": round(float(W[i, k]), 3), "r": round(float(np.linalg.norm(pp - head_c)), 4),
                                 "skull_r": round(skull_r(pp), 4)})
        (out / "gill_pokes.json").write_text(json.dumps({"head_c": head_c.round(4).tolist(), "pokes_1deg": dump[:400],
                                                        "n": len(dump)}, indent=1), encoding="utf-8", newline="\n")
        raise SystemExit(f"LIVELY gills poke into the head at every swing tested: {counts}")
    rep["gill_swing_deg"] = float(swing)
    rep["gill_labels_reached"] = round(reached, 4)
    rep["gill_stretch_mm"] = gill_stretch(P, I, W, roots, names, swing)
    print(f"LIVELY gill labels reached {reached:.4f}, stretch {rep['gill_stretch_mm']} mm at {swing:g} degrees", flush=True)
    rep["gill_pokes_by_swing"] = counts
    rep["gill_weight_on_thick"] = round(float(W.sum(1)[tv < 0.25].max(initial=0.0)), 6)
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
    print(f"LIVELY gills: swing {rep['gill_swing_deg']} pokes {counts} thick {rep['gill_weight_on_thick']} " + json.dumps(
        {n: (g["vertices"], g["length"], g["root_to_mesh_mm"]) for n, g in rep["gills"].items()}), flush=True)
    return rep


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


def gill_stretch(P, I, W, roots, names, swing):
    """The tear measure (AL3): the largest change of an edge's length (mm) when the gills sit at opposite cap corners
    (even gills at a corner, odd ones at its opposite, and the other way), the worst of the 8 corners; a fin split
    between two stalks tears here."""
    E = np.asarray(I).reshape(-1, 3)
    E = np.concatenate([E[:, [0, 1]], E[:, [1, 2]], E[:, [2, 0]]])
    E = E[(W[E[:, 0]].sum(1) > 0.01) | (W[E[:, 1]].sum(1) > 0.01)]
    rest = np.linalg.norm(P[E[:, 0]] - P[E[:, 1]], axis=1)
    worst = 0.0
    for y, p in G.SWING_CORNERS:
        for flip in (1, -1):
            Q = P.copy()
            for k, name in enumerate(names):
                sg = flip if k % 2 == 0 else -flip
                q = P - roots[name]
                rq = q @ np.array(G.spring_matrix(math.radians(swing) * y * sg, math.radians(swing) * p * sg)).T
                Q += W[:, k][:, None] * (rq - q)
            worst = max(worst, float(np.abs(np.linalg.norm(Q[E[:, 0]] - Q[E[:, 1]], axis=1) - rest).max()))
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


main()
