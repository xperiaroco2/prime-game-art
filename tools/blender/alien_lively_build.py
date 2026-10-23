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
4. The skin: Chest (the bust's root), Neck, Head (no bone in the face), Crest1-3 (the crest's spring chain), weights by
   height through the neck only and along the crest only (alien_lively_geom); `<name>_lively.glb`, `lively.json`.

    blender -b --python tools/blender/alien_lively_build.py -- --glb <static GLB> --albedo PNG --mask PNG
        --build <build.json> --out DIR [--name chameleon] [--neck y0,y1] [--crest-root 0.45] [--blade 0.10,0.16]
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


def main():
    ap = argparse.ArgumentParser()
    for k in ("--glb", "--albedo", "--mask", "--build", "--out"):
        ap.add_argument(k, required=True)
    ap.add_argument("--name", default="chameleon")
    ap.add_argument("--neck", default="", help="y0,y1 of the neck blend (default: from the neck's waist)")
    ap.add_argument("--crest-root", type=float, default=0.45, help="the crest root between the head centre and tip")
    ap.add_argument("--blade", default="0.10,0.16", help="the crest blade's half width: full weight, none")
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

    # ---- every texel of the triangles near the eyes gets its 3D position (a small UV rasterizer)
    hue, sat, val = hsv(alb)
    eye = mask[..., 0] < 0.5
    cen = P[I].mean(1)
    uvc = UV[I].mean(1)
    tri_eye = mask[np.clip((uvc[:, 1] * H).astype(int), 0, H - 1), np.clip((uvc[:, 0] * W).astype(int), 0, W - 1), 0] < 0.5
    posmap = np.full((H, W, 3), np.nan)
    near_any = np.nonzero(np.minimum(*(np.linalg.norm(cen - c, axis=1) for c in centres.values())) < 1.3 * r)[0]
    for t in near_any:
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
        ins = (l1 >= -0.03) & (l2 >= -0.03) & (1.0 - l1 - l2 >= -0.03)  # a slight overdraw closes the seams
        if ins.any():
            l1, l2 = l1[ins, None], l2[ins, None]
            posmap[gy[ins].astype(int), gx[ins].astype(int)] = l1 * P[I[t, 0]] + l2 * P[I[t, 1]] + (1 - l1 - l2) * P[I[t, 2]]
    has_pos = ~np.isnan(posmap[..., 0])
    hole = np.zeros((H, W), bool)
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
        # the painted iris to clear: every eye texel of this eye near the cap whose colour reads iris or pupil
        tth = np.arccos(np.clip(tdir @ rest, -1, 1))
        dark = (val[ty, tx] < PUPIL_V) | ((sat[ty, tx] > 0.25) & ((hue[ty, tx] < 0.14) | (hue[ty, tx] > 0.92)))
        sel = tth < 1.2 * e_ang
        hole[ty[sel & dark], tx[sel & dark]] = True
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
        print(f"LIVELY eye {side:+d}: iris {math.degrees(e_ang):.1f} deg (rms {e_res:.2f}), pupil "
              f"{math.degrees(p_ang):.1f} deg (rms {p_res:.2f}), axes apart {eyes['left' if side > 0 else 'right']['axes_apart_deg']}, "
              f"rest open {i0:.2f}/{p0:.2f}, limits {lim}, catch {catch}", flush=True)
    report["eyes"] = eyes

    # ---- the clean sclera: the painted irises filled from the sclera around them
    hole = dilate(hole, 3) & eye
    known = (eye & ~hole).astype(np.float64)
    filled = push_pull(alb.astype(np.float64), known)
    clean = alb.astype(np.float64).copy()
    clean[hole] = filled[hole]
    report["sclera_texels_filled"] = int(hole.sum())
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
    top = P[(y > ey) & (np.abs(P[:, 0]) < 0.08)]
    tip = top[np.argmax(top[:, 1] - top[:, 2])]  # the crest tip: high and far back
    head_c = np.array([0.0, ey, zc(ey) if ey < prof[-1][0] + 0.02 else float(P[np.abs(y - ey) < 0.01][:, 2].mean())])
    root = head_c + args.crest_root * (tip - head_c)
    for k in range(3):
        pos[f"Crest{k + 1}"] = tuple(float(v) for v in root + (tip - root) * k / 3.0)
    b0, b1 = (float(v) for v in args.blade.split(","))
    seg = tip - root
    infl, crest_n = [], 0
    for p in P:
        ch, nk, hd = G.neck_weights(float(p[1]), y0, ym, y1)
        t = float((p - root) @ seg / (seg @ seg))
        wc = G.smoothstep(0.0, 0.3, t) * (1.0 - G.smoothstep(b0, b1, abs(float(p[0])))) * hd
        crest_n += wc > 0.01
        c1, c2, c3 = G.crest_split(t)
        inf = [(j, w) for j, w in ((0, ch), (1, nk), (2, hd * (1.0 - wc)), (3, wc * c1), (4, wc * c2), (5, wc * c3))
               if w > 1e-4]
        infl.append(inf)
    (out / f"{args.name}_lively.glb").write_bytes(G.add_skin(data, pos, infl))
    report["rig"] = {"joints": {k: [round(v, 5) for v in pos[k]] for k in G.JOINTS}, "neck_y": [y0, ym, y1],
                     "waist": waist, "shoulder": shoulder, "chin_y": chin, "crest_root": root.round(5).tolist(),
                     "crest_tip": tip.round(5).tolist(), "crest_vertices": int(crest_n), "blade": [b0, b1]}
    report["sclera"] = f"{args.name}_sclera.png"
    (out / "lively.json").write_text(json.dumps(report, indent=1), encoding="utf-8", newline="\n")
    print(f"LIVELY rig neck {y0:.3f}/{ym:.3f}/{y1:.3f} waist {waist[0]:.3f} (w {waist[1]:.3f}) shoulder {shoulder[0]:.3f} "
          f"chin {chin:.3f} crest {root.round(3).tolist()} -> {tip.round(3).tolist()} ({crest_n} verts)", flush=True)


main()
