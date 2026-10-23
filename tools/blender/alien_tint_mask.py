"""The alien pilot's static heads (art #196): the skin colour study's accent mask, made in headless Blender
(tools/runner/blender.py) from a static build's saved .blend and maps (never changed). Writes into --out:
- `<head>_accent.png` (2048, linear RGBA): R the lips, G the marks (the axolotl's gills and cheek freckles, the
  chameleon's crest stripes), B the pale front panel, A 1 - the gills (the colour slots' gills on the skin); every
  channel already multiplied by the skin tint mask, so the eyes stay out;
- `<head>_accent.json`: each region's median sRGB in the build's albedo (the study's recolour bases) and its texel share.

The regions come from the object-space position baked onto the build's own UVs (an emission bake with Blender's
margin, so a region is continuous across the UV seams and the gutters) and the plain albedo's saturation:
- lips: a band round step 2a's fitted lip line (the slit), following it in plan and run on past its end to the
  mouth's corners (LIP_BAND), kept to the saturated (teal) texels: the lips are teal on a pale snout and chin, so
  the paint gives the edge, not the band;
- marks: the axolotl's gills (step 2a's gill roots, as the build's rough map has them, on its thin parts) and its
  freckles (saturated dots inside the pale cheeks); the chameleon's crest stripes (the build's own stripe formula,
  step 2a's `stripes`);
- front: the pale texels (low saturation against the skin's teal), the lips taken out.

    run_script("alien_tint_mask.py", ["--head", "axolotl", "--build", <static_v5/axolotl>, "--ref", <step 2a v2
               build.json>, "--out", <dir>])
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_pilot_head as H  # noqa: E402
import alien_static_head as S  # noqa: E402

# lips (C2): a band round the slit that follows the fitted lip line in plan (so it wraps back with the chameleon's
# lips) and runs on past the line's end along its last direction, its height tapering to nothing there: the lips go
# on past the fitted line to their corners (the axolotl's smile tips, the chameleon's lips a fifth of a metre further
# back). Per head: the band's half height round the slit (eye radii), its reach from the line in plan (m: the lip's
# bulge in front, the lining behind), the tip's length past the line's end (m) and its taper's power (the axolotl's
# smile tip is a thin line with freckles above it, the chameleon's a rounded point: both 0.5) and the tip's half height
# cap (m; None: no cap). Both heads' lips are teal paint between pale panels above and below, so the band may be
# generous: the paint gives the edge, soft and on the border. Colour slots (2026-10-23): the axolotl's smile tail (the
# thin line past the corner) stayed skin under power 1.5 and power 0.5 alone caught a cheek freckle; now power 0.5
# with the tip capped at 0.03 m, and the cheek freckles taken out of the tip.
LIP_BAND = {"axolotl": (1.1, 0.15, 0.02, 0.5, None), "chameleon": (0.75, 0.15, 0.26, 0.5, None)}
# The axolotl's smile tail (colour slots v2, 2026-10-23): a thin teal line past the lips' corner that curves up into
# the pale cheek, which neither a band nor its straight run-on followed. The lips now grow from their body (the band
# above, its tip only 0.02 m) along the surface through the connected teal texels past the corner (3D voxels of
# 1.5 texel pitches, 26 neighbours): the zone a ball of zone_r (m) round each corner, at most max_len (m) of growth,
# teal components of fewer than min_vox voxels (the freckles, if one touched the zone) out, the darkness test the
# teal paint's own value against the cheek's; the colour fades over the tail's last fade share (at most fade_max m).
# None: no growth (the chameleon's lips are whole as the band has them).
LIP_GROW = {"axolotl": {"zone_r": 0.11, "max_len": 0.10, "min_vox": 40, "fade": 0.25, "fade_max": 0.015},
            "chameleon": None}
# The axolotl's gills (v2): the whole gill, stalk and fringe, from the build's own segmented gill part
# (`<head>_gills` in the static .blend): a texel is gill where the gill part's surface is nearer than the skin's
# (soft over GILL_SOFT m); its gradient runs from the root (the nearest step 2a gill pivot, 0) to the gill's farthest
# texel (1), the details colour reaching full at GILL_RAMP[1] of the way out.
GILL_SOFT = 0.006
GILL_RAMP = (0.12, 0.7)
GILL_NEAR = 0.06  # m: a texel farther than this from the gill part is no gill (the gill part is a little larger)


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def lip_path(line, tip, ax, y, h0, power=0.5, n_tip=8, cap=None):
    """The slit's path on one side (the fitted line, x >= 0; its height a running median of 5, the fit's outliers
    out), run on past its end by tip metres in plan along its last two points' direction. Returns per texel (|x| ax,
    y): the slit's height at the nearest point of the path in plan, that point's arc length, the band's half height
    there (h0 along the line, tapering as (1 - u) ** power to 0 at the tip's end, at most cap past the line's end),
    the plan distance and the line's end's arc length."""
    k = len(line)
    zp = np.pad(line[:, 1], 2, mode="edge")
    zs = np.median(np.stack([zp[i:i + k] for i in range(5)]), 0)
    p = np.stack([line[:, 0], -line[:, 2], zs], -1)  # Blender (x, y, z)
    d = p[-1] - p[-3]
    d = d / np.linalg.norm(d[:2])  # per plan metre
    p = np.concatenate([p, [p[-1] + d * tip * j / n_tip for j in range(1, n_tip + 1)]])
    seg = np.linalg.norm(np.diff(p[:, :2], axis=0), axis=1)
    arc = np.concatenate([[0.0], np.cumsum(seg)])
    s_end = arc[k - 1]
    best = np.full(ax.shape, np.inf)
    zl, sl = np.zeros(ax.shape), np.zeros(ax.shape)
    for i in range(len(p) - 1):
        a, b = p[i], p[i + 1]
        ab = b[:2] - a[:2]
        t = np.clip(((ax - a[0]) * ab[0] + (y - a[1]) * ab[1]) / max(float(ab @ ab), 1e-12), 0.0, 1.0)
        dist = np.hypot(ax - (a[0] + t * ab[0]), y - (a[1] + t * ab[1]))
        m = dist < best
        best[m] = dist[m]
        zl[m] = (a[2] + t * (b[2] - a[2]))[m]
        sl[m] = (arc[i] + t * seg[i])[m]
    hl = h0 * np.clip(1.0 - (sl - s_end) / tip, 0.0, 1.0) ** power
    if cap is not None:
        hl = np.where(sl > s_end, np.minimum(hl, cap), hl)
    return zl, sl, hl, best, s_end


def texel_pitch(pos, ok) -> float:
    """The median 3D distance between neighbouring texels on the paint (the gutters and the seams out)."""
    d = np.linalg.norm(pos[:, 1:] - pos[:, :-1], axis=-1)
    m = ok[:, 1:] & ok[:, :-1]
    d = d[m]
    return float(np.median(d[d < np.percentile(d, 90)]))


def _cube(g, op):
    """g's 3x3x3 neighbourhood reduced by op (np.logical_or: a dilation, np.minimum: a min), one axis at a time."""
    out = g
    for ax in range(3):
        lo = [slice(None)] * 3
        hi = [slice(None)] * 3
        lo[ax], hi[ax] = slice(1, None), slice(None, -1)
        a = out.copy()
        a[tuple(lo)] = op(a[tuple(lo)], out[tuple(hi)])
        a[tuple(hi)] = op(a[tuple(hi)], out[tuple(lo)])
        out = a
    return out


def surface_grow(pos, seed, cand, vs, max_steps, min_vox):
    """Grows the seed texels through the candidate texels connected on the surface: both splatted into 3D voxels of
    vs metres; candidate components (26 neighbours) under min_vox voxels dropped; returns per texel the growth's
    step count (vs metres a step; -1: not reached, 0: the seed) and the dropped components' sizes."""
    zone = seed | cand
    p = pos[zone]
    lo = p.min(0) - vs
    idx = np.floor((p - lo) / vs).astype(np.int64)
    shape = tuple(idx.max(0) + 2)
    flat = np.ravel_multi_index(idx.T, shape)
    gs = np.zeros(shape, bool)
    gc = np.zeros(shape, bool)
    gs.flat[flat[seed[zone]]] = True
    gc.flat[flat[cand[zone]]] = True
    gc &= ~gs
    # the candidates' components: a label propagated as the min over the neighbours until stable
    big = np.iinfo(np.int64).max
    lab = np.where(gc, np.arange(gc.size).reshape(shape), big)
    for _ in range(4 * max(shape)):
        m = np.where(gc, _cube(lab, np.minimum), big)
        if np.array_equal(m, lab):
            break
        lab = m
    ids, counts = np.unique(lab[gc], return_counts=True)
    small = ids[counts < min_vox]
    gc &= ~np.isin(lab, small)
    dist = np.full(shape, -1, np.int32)
    dist[gs] = 0
    front = gs
    for k in range(1, max_steps + 1):
        nb = _cube(front, np.logical_or) & gc & (dist < 0)
        if not nb.any():
            break
        dist[nb] = k
        front = nb
    out = np.full(seed.shape, -1, np.int32)
    out[zone] = dist.flat[flat]
    out[seed] = 0
    out[~(seed | cand)] = -1
    return out, sorted(int(c) for c in counts[counts < min_vox])


def gill_region(low, pos, ok, roots):
    """The whole gills (stalk and fringe) on the static head's texels and their root-to-tip gradient: a texel is gill
    where the build's segmented gill part is nearer than its skin part; the gradient is the texel's distance from its
    nearest gill root over that gill's farthest texel's."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    head = low.name.split("_")[0]
    dg = bpy.context.evaluated_depsgraph_get()
    tg = BVHTree.FromObject(bpy.data.objects[f"{head}_gills"], dg)
    ts = BVHTree.FromObject(bpy.data.objects[f"{head}_skin"], dg)
    rx = min(abs(p[0]) for p in roots.values())
    rz = min(p[2] for p in roots.values())
    test = ok & (np.abs(pos[..., 0]) > rx - 0.2) & (pos[..., 2] > rz - 0.2)
    pts = pos[test]
    d_g = np.empty(len(pts))
    d_s = np.empty(len(pts))
    for i, q in enumerate(pts):
        v = Vector(q)
        hg, hs = tg.find_nearest(v), ts.find_nearest(v)
        d_g[i] = hg[3] if hg[0] is not None else 1e9
        d_s[i] = hs[3] if hs[0] is not None else 1e9
    w = np.zeros(pos.shape[:2], np.float32)
    w[test] = smoothstep(-GILL_SOFT, GILL_SOFT, d_s - d_g) * (d_g < GILL_NEAR)  # on the gill part, never a speck
    rp = np.array(list(roots.values()), np.float64)
    near = np.linalg.norm(pts[:, None, :] - rp[None], axis=-1)
    which = near.argmin(1)
    dr = near.min(1)
    t = np.zeros(len(pts))
    lens = {}
    for k, name in enumerate(roots):
        m = (which == k) & (w[test] > 0.5)
        if m.any():
            L = float(np.percentile(dr[m], 99))
            lens[name] = round(L, 3)
            sel = which == k
            t[sel] = np.clip(dr[sel] / L, 0, 1)
    g = np.zeros_like(w)
    g[test] = smoothstep(GILL_RAMP[0], GILL_RAMP[1], t)
    stats = {"fit_median_m": round(float(np.median(np.minimum(d_g, d_s))), 4), "lengths_m": lens,
             "share": round(float((w > 0.5).sum()) / float(ok.sum()), 4)}
    return w, g, stats


def load(path: Path) -> np.ndarray:
    img = bpy.data.images.load(str(path))
    img.colorspace_settings.name = "Non-Color"  # the stored values (sRGB for the albedo), never converted
    return H.image_array(img)


def debug(path: Path, pos, col, lips, line, fp, r, over=None, centre=None, half=0.36, yaws=(0.0, 40.0, 90.0)) -> None:
    """The mouth's texels splatted into three views (a z-buffer per view), 400 px each: front, 3/4 (40 deg), side;
    lips (a weight) drawn in over (default red) on the albedo."""
    size = 400
    ok = col.sum(-1) > 0.05
    p, c = pos[ok], col[ok].copy()
    tint = np.array([0.6, 0.0, 0.0]) if over is None else over[ok]
    c = c * (1 - 0.6 * lips[ok, None]) + tint * lips[ok, None]
    pl = np.concatenate([line * [1, 1, 1], line * [-1, 1, 1]])  # (x, up, front) both sides
    lp = np.stack([pl[:, 0], -pl[:, 2], pl[:, 1]], -1)
    centre = np.array([0.0, fp[1] + 0.12, fp[2]]) if centre is None else np.asarray(centre, np.float64)
    views = []
    for yaw in yaws:
        a = np.radians(yaw)
        def proj(q):
            d = q - centre
            u = d[:, 0] * np.cos(a) + d[:, 1] * np.sin(a)  # screen right
            depth = -d[:, 0] * np.sin(a) + d[:, 1] * np.cos(a)  # away from the camera
            return ((u / half + 1) * size / 2).astype(int), ((d[:, 2] / half + 1) * size / 2).astype(int), depth
        img = np.full((size, size, 3), 0.3, np.float32)
        zb = np.full((size, size), np.inf)
        ui, vi, dep = proj(p)
        m = (ui >= 0) & (ui < size) & (vi >= 0) & (vi < size)
        idx = np.nonzero(m)[0]
        idx = idx[np.argsort(-dep[idx])]
        img[vi[idx], ui[idx]] = c[idx]
        zb[vi[idx], ui[idx]] = dep[idx]
        lu, lv, ld = proj(lp)
        for uu, vv, dd in zip(lu, lv, ld):
            if 0 <= uu < size and 0 <= vv < size and dd <= zb[vv, uu] + 0.02:
                img[max(vv - 1, 0):vv + 2, max(uu - 1, 0):uu + 2] = (1.0, 1.0, 0.0)
        views.append(img)
    S.save(np.concatenate(views, 1), path, data=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    for a in ("--head", "--build", "--ref", "--out"):
        ap.add_argument(a, required=True)
    ap.add_argument("--debug", action="store_true", help="also <head>_lips_debug.png: the mouth seen from the front,"
                    " 3/4 and the side, the lips red over the albedo times the cavity, the lip line yellow")
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    head, build, out = args.head, Path(args.build), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ref = json.loads(Path(args.ref).read_text(encoding="utf-8"))
    eye = ref["eye_fit"]
    r = eye["r"]
    bpy.ops.wm.open_mainfile(filepath=str(build / f"{head}_static.blend"))
    low = bpy.data.objects[f"{head}_static"]
    for o in list(bpy.data.objects):
        if o is not low:
            o.hide_render = True
    mat = bpy.data.materials.new(f"{head}_posbake")
    mat.use_nodes = True
    low.data.materials.clear()
    low.data.materials.append(mat)
    nt = mat.node_tree
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    emit = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(geo.outputs["Position"], emit.inputs["Color"])
    nt.links.new(emit.outputs["Emission"], nt.nodes["Material Output"].inputs["Surface"])
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 1
    plain = load(build / f"{head}_albedo_plain.png")[..., :3]
    albedo = load(build / f"{head}_albedo.png")[..., :3]
    skin = load(build / f"{head}_mask.png")[..., 0]
    thin = load(build / f"{head}_detail.png")[..., 1]  # the thinness (1 thin: gills, crest, lips)
    n = plain.shape[0]
    pos_img = S.new_image(f"{head}_pos", n, data=True, float_buffer=True)
    S.bake_to(low, pos_img, "EMIT")
    pos = H.image_array(pos_img)[..., :3]
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    hue, sat, val = (a.reshape(n, n) for a in S.hsv(plain.reshape(-1, 3)))
    teal_s = float(np.median(sat[(skin > 0.95) & (sat > 0.3)]))
    lit = smoothstep(0.12, 0.25, val)  # the paint, not the black gutters between the UV islands
    teal = smoothstep(0.45 * teal_s, 0.7 * teal_s, sat) * lit  # 1 on the teal, 0 on the pale panel
    pale = (1.0 - smoothstep(0.45 * teal_s, 0.7 * teal_s, sat)) * smoothstep(0.45, 0.6, val)  # the pale panel is light

    # lips: the slit's band, the lip line's half width, in front of the face, on the teal paint only
    line = np.asarray(ref["lip_line"]["line"], np.float64)  # (x, up, front)
    line = line[np.argsort(line[:, 0])]
    fp = ref["lip_line"]["front_point"]
    band_h, reach, tip, power, tip_cap = LIP_BAND[head]
    zl, sl, hl, dh, s_end = lip_path(line, tip, np.abs(x), y, band_h * r, power, cap=tip_cap)
    band = 1.0 - smoothstep(0.8 * hl, np.maximum(hl, 1e-4), np.abs(z - zl))
    near = 1.0 - smoothstep(0.8 * reach, reach, dh)
    slit = np.interp(np.abs(x), line[:, 0], line[:, 1])  # the freckles' face band below
    roots = (ref.get("pivots") or {}).get(f"{head}_gills") or {}
    freckle_raw = np.zeros_like(teal)
    if roots:  # the cheek freckles: teal dots inside the pale cheeks, between the lips and the eyes, on the front
        cheeks = smoothstep(0.55, 0.75, S.blur(pale.astype(np.float32), 6))
        face = (1.0 - smoothstep(eye["y"] + 0.5 * r, eye["y"] + 2.0 * r, y)) \
            * smoothstep(slit + 0.6 * r, slit + 1.2 * r, z) * (1.0 - smoothstep(eye["z"], eye["z"] + 0.8 * r, z))
        freckle_raw = teal * cheeks * face
    past = (sl > s_end).astype(np.float32)  # the tip: never a freckle
    body = band * near * teal * (1.0 - freckle_raw * past)
    grow_cfg = LIP_GROW.get(head)
    grow_stats = None
    unreached = np.zeros_like(body)
    if grow_cfg:  # the smile tail: the lips grown from their body along the connected teal past the corner
        ok = lit > 0.5
        pitch = texel_pitch(pos, ok)
        vs = 1.5 * pitch
        pale_v = float(np.median(val[(pale > 0.9) & (skin > 0.95)]))
        teal_v = float(np.median(val[(teal > 0.9) & (skin > 0.95)]))
        dark = val < 0.5 * (pale_v + teal_v)  # the paint's darkness against the cheek
        end = line[-1]
        zone = np.zeros_like(ok)
        for sx in (1.0, -1.0):
            c3 = np.array([sx * end[0], -end[2], end[1]])
            zone |= np.linalg.norm(pos - c3, axis=-1) < grow_cfg["zone_r"]
        seed = (body > 0.5) & (skin > 0.5) & zone
        cand = (teal > 0.5) & dark & zone & (skin > 0.5) & ~seed
        steps, dropped = surface_grow(pos, seed, cand, vs, int(grow_cfg["max_len"] / vs), grow_cfg["min_vox"])
        dm = steps * vs
        tail = np.zeros_like(body)
        grow_stats = {"pitch_m": round(pitch, 5), "voxel_m": round(vs, 5), "pale_v": round(pale_v, 3),
                      "teal_v": round(teal_v, 3), "dropped": dropped[:20], "sides": {}}
        for sx, name in ((1.0, "L"), (-1.0, "R")):
            m = (steps > 0) & (np.sign(x) == sx)
            if not m.any():
                grow_stats["sides"][name] = None
                continue
            L = float(dm[m].max())
            fade = min(grow_cfg["fade"] * L, grow_cfg["fade_max"])
            tail[m] = 1.0 - smoothstep(L - fade, L, dm[m])
            grow_stats["sides"][name] = {"length_m": round(L, 4), "fade_m": round(fade, 4), "texels": int(m.sum()),
                                         "hit_max": bool(L >= grow_cfg["max_len"] - 2 * vs)}
        body = np.maximum(body, tail * teal)
        unreached = (cand & (steps < 0)).astype(np.float32)
        print(f"GROW {head} {json.dumps(grow_stats)}", flush=True)
    lips = S.blur(body.astype(np.float32), 1) * skin

    # marks
    marks = np.zeros_like(lips)
    gills = np.zeros_like(lips)
    gill_grad = np.zeros_like(lips)
    gill_stats = None
    if roots:  # the whole gills, stalk and fringe (the build's segmented gill part), and their root-to-tip gradient
        gills, gill_grad, gill_stats = gill_region(low, pos, lit > 0.5, roots)
        print(f"GILLS {head} {json.dumps(gill_stats)}", flush=True)
        freckles = freckle_raw * (1.0 - lips) * (1.0 - gills)
        marks = np.maximum(gills * gill_grad, freckles)  # G: the gradient on the gills (the default mode)
    st = ref.get("stripes")
    if st:  # the crest stripes: alien_pilot_head.grade_source's formula
        axis = 0 if abs(st["front"][0]) > 0.5 else 1
        dyb = (pos[..., axis] - st["c_depth"]) * -st["front_sign"]
        ang = np.arctan2(z - st["c_z"], dyb)
        wave = np.sin(ang * st["k"])
        marks = smoothstep(-0.25, 0.25, wave) * smoothstep(st["z_lo"], st["z_hi"], z)
    marks = S.blur(marks.astype(np.float32), 1) * skin * (1.0 - lips)
    front_w = S.blur(pale.astype(np.float32), 1) * skin * (1.0 - lips) * (1.0 - marks)
    gill_w = S.blur(gills.astype(np.float32), 1) * skin * (1.0 - lips)
    front_w = front_w * (1.0 - gill_w)
    acc = np.stack([lips, marks, front_w, 1.0 - gill_w], -1)  # A: 1 - the whole gills (stalk and fringe)
    S.save(acc, out / f"{head}_accent.png", data=True)
    if args.debug:
        cav = load(build / f"{head}_detail.png")[..., 0]
        col = plain * cav[..., None] ** 3 * lit[..., None]
        debug(out / f"{head}_lips_debug.png", pos, col, lips, line, fp, r)
        if grow_cfg:  # each corner close up: the lips red, the teal candidates the growth did not reach green
            over = np.where(unreached[..., None] > 0.5, np.array([0.0, 0.7, 0.0]), np.array([0.7, 0.0, 0.0]))
            end = line[-1]
            for sx, nm in ((1.0, "L"), (-1.0, "R")):
                debug(out / f"{head}_corner{nm}_debug.png", pos, col, np.maximum(lips, unreached), line, fp, r,
                      over=over, centre=(sx * end[0], -end[2], end[1]), half=0.06,
                      yaws=(0.0, 40.0 * sx, 90.0 * sx))
        if roots:  # the gills: blue at the root, red at the tip, over the whole gill
            over = np.stack([gill_grad, 0.15 * np.ones_like(gill_grad), 1.0 - gill_grad], -1)
            debug(out / f"{head}_gills_debug.png", pos, col, gill_w, line, fp, r, over=over,
                  centre=(0.0, 0.1, 0.45), half=0.75, yaws=(0.0, 60.0, 90.0))

    report = {"head": head, "teal_sat": round(teal_s, 4), "regions": {}, "lip_growth": grow_stats,
              "gills": gill_stats}
    core = skin > 0.95
    base = albedo[core & (teal > 0.9) & (lips < 0.1) & (marks < 0.1)]
    for name, w in (("skin", None), ("lips", lips), ("marks", marks), ("front", front_w)):
        px = base if w is None else albedo[core & (w > 0.8)]
        report["regions"][name] = {"srgb": [round(float(v), 4) for v in np.median(px, axis=0)] if len(px) else None,
                                   "share": round(len(px) / float(core.sum()), 4)}
    (out / f"{head}_accent.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"TINT {head} {json.dumps(report)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
