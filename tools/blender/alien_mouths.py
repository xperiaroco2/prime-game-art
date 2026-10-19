"""The alien parts kit's mouths rebuilt from their GPT talk-shape sheets (art #196, step S6): per design (frog,
overbite) the six replacement pieces (rest, M, small, A, E, O) measured off the sheet's six panels, and a flipbook
test: the six panels' mouths as one texture atlas on a thin face shell, one shell per shape.

    blender -b --factory-startup --python-exit-code 1 --python tools/blender/alien_mouths.py -- \
        --character <S3/build/alien_character.blend> --frog <mf1 sheet.png> --overbite <mo1 sheet.png> --out <S6>

Writes <out>/build/alien_character.blend, <out>/export/alien_character.glb with character.json (S3's, with the new
mouth nodes), <out>/export/mouth_flip_<design>.png (the atlases), <out>/measure/ (the measured profiles drawn over
each panel, measure.png), <out>/ref/<design>_<shape>.png (each panel's crop for the side-by-side) and profiles.json.

The method:
1. The sheets (1536 x 1024, 3 x 2 panels of 512 px, the panel order rest, M, small, A, E, O) are read as sRGB. Each
   pixel is classed: lip (coral: R well above G, B clearly below G), tongue (pink: R above G, B about G), teeth
   (cream: bright, R >= G > B), dark (the mouth's inside), background (neutral grey). Per panel the head's centre is
   the silhouette's middle at the nostril row, the nostrils (dark slits) the vertical anchor.
2. Per pixel column across the mouth: the upper lip's top and bottom, the lower lip's top and bottom and the opening
   between them; a closed column is split at its crease (the darkest row). Columns behind a tooth are interpolated.
3. Sheet to head: one scale K (m per px) from the face's width at the rest mouth's row (the head's front silhouette
   there, against the sheet's), corrected per panel by the face's width at the nostril row; the rest mouth's seam
   lands on the Mouth socket, every other panel keeps its offset from its nostrils. The head is rigid and its lower
   face shorter and narrower than the sheet's (whose jaw drops and cheeks stretch), so two squeezes keep a shape on
   the face: below the seam toward CHIN_Z when the lower lip would pass it, and in x when the mouth is wider than
   FACE_FILL of the face (both reported per shape).
4. Pieces: rest, M and small are two tubes (an ellipse of half-height b, the measured one, and depth
   a = DEPTH_A * b + DEPTH_C) along the measured centre lines, pushed out of the skin along its normal, overlapping at
   a closed crease. A, E and O are one ring: per angle around the opening the section spans the lips from the
   opening's edge to the outer edge (the same depth rule), so the corners close smoothly. The inner cup (dark) spans
   the opening on the skin, the tongue (where the panel shows one) is an arch on it to its measured top, and the
   overbite's two teeth are each panel's own boxes, in front of a lip they hang over. So the teeth belong to each
   overbite piece (none in M), and the separate teeth node is gone.
5. Flipbook: each panel's mouth window (the same place on the face in every panel) is cut out, its alpha the lips,
   the opening, tongue and teeth (the skin clear), into a 3 x 2 atlas; each shape is a shell of the head's surface
   over that window, 0.6 mm out, its UVs on its cell.
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
import alien_parts_geom as G  # noqa: E402
import export_glb  # noqa: E402

SHAPES = ("rest", "M", "small", "A", "E", "O")
PANEL = 512
WIN = (224, 150)  # the mouth window per panel, px (w, h); its top NOSE_GAP px under the nostrils
NOSE_GAP = 14
DEPTH_A, DEPTH_C = 0.80, 0.0012  # a lip tube's depth from its measured half-height, m
SINK = 0.30  # the share of the depth inside the skin
PUSH = {"frog": {"O": 0.007}, "overbite": {"O": 0.006, "*": 0.004}}  # the lips' push out of the skin, m (O: pucker)
LOWER_BACK = {"overbite": -0.002}  # the overbite's lower lip sits back
MIN_B = 0.0011  # a lip's smallest half-height (the corners), m
STATIONS = 41
RING_N, RING_SEG = 96, 14  # an open mouth's ring: sections around, vertices per section
SEAM_OVERLAP = 1.5  # a closed mouth's lips overlap at the crease, px
RING_SHAPES = ("A", "E", "O")  # the wide shapes are one ring; rest, M and small two tubes
FACE_FILL = 0.86  # a mouth's half width at most this share of the face's half width at the socket: wider is squeezed
CHIN_Z = 1.443  # the lowest a lip may reach on the head (S7: the sculpted chin is at 1.437): deeper is squeezed, m
RING_KEEP = {"centre": 9, "width": 5}  # S7: the open ring's centre line and lip width keep this many harmonics
NORMAL_SMOOTH = 8  # S7: passes over the skin points and normals under a lip (the decimated head's facets rippled it)
STATION_SMOOTH = 5  # S7: passes over the closed lips' measured edges (2 left ripples)
CORNER = {"share": 0.16, "join": 0.85, "tuck": 0.9}  # S7: over the last share of a closed mouth's stations the two
# lips' centres meet (join) and sink into the skin by tuck times their depth, so the corner is a soft tucked dimple
TOOTH_D, TOOTH_TUCK = 0.0055, 0.003  # a tooth's depth, and how far it runs up under the upper lip, m
TONGUE = (0.66, 0.30, 0.33)  # sRGB (S7: a deeper rose; the lips' near twin read as a doubled lower lip in A)
FLIP_OUT = 0.0015


def args():
    p = argparse.ArgumentParser()
    p.add_argument("--character", required=True)
    p.add_argument("--frog", required=True)
    p.add_argument("--overbite", required=True)
    p.add_argument("--out", required=True)
    return p.parse_args(sys.argv[sys.argv.index("--") + 1:])


def srgb_to_lin(c):
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def load_rgb(path):
    im = bpy.data.images.load(path)
    w, h = im.size
    a = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(h, w, 4)[::-1, :, :3].copy()  # top-down rows, sRGB


def save_rgba(arr, path, name):
    h, w = arr.shape[:2]
    rgba = np.ones((h, w, 4), np.float32)
    rgba[..., :arr.shape[2]] = arr
    im = bpy.data.images.new(name, w, h, alpha=True)
    im.pixels.foreach_set(rgba[::-1].ravel())
    im.filepath_raw = str(path)
    im.file_format = "PNG"
    im.save()
    return im


def classes(P):
    R, Gc, B = P[..., 0], P[..., 1], P[..., 2]
    lum = R + Gc + B
    bg = (np.abs(R - Gc) < 0.04) & (np.abs(Gc - B) < 0.04) & (R > 0.33) & (R < 0.52)
    teeth = (R > 0.68) & (Gc > 0.60) & (B > 0.42) & (R >= Gc - 0.01) & (B < Gc) & (R - Gc < 0.16)
    lip = (R > Gc + 0.15) & (R > 0.30) & (B - Gc < -0.035) & ~teeth
    tongue = (R > Gc + 0.08) & (R > 0.20) & (B - Gc >= -0.035) & ~teeth
    dark = (lum < 0.60) & (R >= Gc - 0.02) & ~lip
    return {"bg": bg, "teeth": teeth, "lip": lip, "tongue": tongue, "dark": dark, "lum": lum}


def width_at(bg, y):
    xs = np.nonzero(~bg[int(y), 40:PANEL - 40])[0] + 40
    return float(xs.min()), float(xs.max())


def nostrils(C, hc):
    x0, x1 = int(hc) - 26, int(hc) + 26
    band = C["lip"][230:420, int(hc) - 10:int(hc) + 11].any(axis=1)
    y0, y1 = 212, min(275, 230 + int(np.argmax(band)) - 4)
    m = C["lum"][y0:y1, x0:x1] < 0.95
    m &= ~C["lip"][y0:y1, x0:x1]
    ys, xs = np.nonzero(m)
    if len(ys) < 8:
        raise RuntimeError("no nostrils found")
    return float(ys.mean() + y0), [int(xs.min() + x0), int(xs.max() + x0), int(ys.min() + y0), int(ys.max() + y0)]


def runs(mask):
    out, start = [], None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(mask) - 1))
    return out


def measure_panel(P):
    """The mouth's columns in one panel: per x (panel px) the lip edges, the opening, the tongue top, the teeth."""
    C = classes(P)
    # the head centre: first a rough one at a mid-face row, then at the nostril row
    l0, r0 = width_at(C["bg"], 250)
    ny, nbox = nostrils(C, (l0 + r0) / 2)
    l1, r1 = width_at(C["bg"], ny)
    hc = (l1 + r1) / 2
    ny, nbox = nostrils(C, hc)
    y0, y1 = int(ny) + NOSE_GAP, min(PANEL - 1, int(ny) + NOSE_GAP + 160)
    cols = {}
    teeth_cols = []
    for x in range(int(hc) - 120, int(hc) + 121):
        lipc = C["lip"][y0:y1, x]
        tc = C["teeth"][y0:y1, x]
        trun = max(runs(tc), key=lambda r: r[1] - r[0], default=None)  # the tooth itself, not lip highlights
        if trun is not None and trun[1] - trun[0] + 1 >= 3:
            teeth_cols.append((x, trun[0] + y0, trun[1] + y0))
        else:
            trun = None
        ys = np.nonzero(lipc)[0]
        if len(ys) < 3:
            continue
        top, bot = int(ys.min()), int(ys.max())
        gaps = [(a, b) for a, b in runs(~lipc[top:bot + 1]) if b - a + 1 >= 1]
        gaps = [(a + top, b + top) for a, b in gaps]
        best = max(gaps, key=lambda g: g[1] - g[0], default=None)
        rec = {"top_u": top + y0, "bot_l": bot + y0, "teeth": trun is not None}
        if best is not None and best[1] - best[0] + 1 >= 3:
            rec["bot_u"], rec["top_l"] = best[0] - 0.5 + y0, best[1] + 0.5 + y0
            rec["open"] = True
            # a tooth that reaches the lower lip hides that lip's top edge
            rec["hide_l"] = trun is not None and best[1] - trun[1] <= 2
            seg = slice(best[0] + y0, best[1] + 1 + y0)
            tg = runs(C["tongue"][seg, x])
            tg = [t for t in tg if t[1] - t[0] + 1 >= 3]
            if tg:
                rec["tongue_top"] = tg[0][0] + best[0] + y0
        else:
            mid = slice(top + (bot - top) // 4, bot - (bot - top) // 4 + 1)
            lum = C["lum"][y0:y1, x][mid]
            seam = (top + (bot - top) // 4 + int(np.argmin(lum))) + y0 if len(lum) else (top + bot) / 2 + y0
            rec["bot_u"], rec["top_l"] = seam - 0.5, seam + 0.5
            rec["open"] = False
        cols[x] = rec
    # a tooth over the lower lip hides its top edge: interpolate that edge from the nearest clean columns (a tooth
    # counts as the opening, so the upper lip's bottom edge is the tooth's visible top)
    xs = sorted(cols)
    hid = [x for x in xs if cols[x].get("hide_l")]
    if hid:  # and the gap between the two teeth
        for x in xs:
            if hid[0] <= x <= hid[-1]:
                cols[x]["hide_l"] = True
    clean = [x for x in xs if not cols[x].get("hide_l")]
    for x in xs:
        if cols[x].get("hide_l") and clean:
            lft = max((c for c in clean if c < x), default=None)
            rgt = min((c for c in clean if c > x), default=None)
            if lft is None or rgt is None:
                continue
            f = (x - lft) / (rgt - lft)
            cols[x]["top_l"] = cols[lft]["top_l"] * (1 - f) + cols[rgt]["top_l"] * f
    teeth = []
    for a, b in runs([any(t[0] == x for t in teeth_cols) for x in range(int(hc) - 120, int(hc) + 121)]):
        group = [t for t in teeth_cols if int(hc) - 120 + a <= t[0] <= int(hc) - 120 + b]
        if b - a + 1 >= 4:
            teeth.append({"x0": group[0][0] - 0.5, "x1": group[-1][0] + 0.5, "y0": min(t[1] for t in group) - 0.5,
                          "y1": max(t[2] for t in group) + 0.5})
    return {"hc": hc, "ny": ny, "nostril_box": nbox, "face_w_nose": r1 - l1, "cols": cols, "teeth": teeth, "C": C}


def smooth(vals, n=2):
    v = list(vals)
    for _ in range(n):
        v = [v[0]] + [(v[i - 1] + 2 * v[i] + v[i + 1]) / 4 for i in range(1, len(v) - 1)] + [v[-1]]
    return v


def surf(bvh, x, z):
    hit = bvh.ray_cast(Vector((x, -1.0, z)), Vector((0, 1, 0)))
    if hit[0] is None:  # past the front silhouette: toward the head's axis instead
        o = Vector((x * 1.6, -0.25, z))
        hit = bvh.ray_cast(o, (Vector((0, 0.0, z)) - o).normalized())
    if hit[0] is None:
        raise RuntimeError(f"no face at x={x:.3f} z={z:.3f}")
    n = hit[1] if hit[1].y < 0 else -hit[1]
    return hit[0], n


def stations(cols):
    """STATIONS samples across the mouth's columns (px), each with its four lip edges, smoothed."""
    xs = sorted(cols)
    xl, xr = xs[0], xs[-1]
    st = []
    for i in range(STATIONS):
        xp = xl + 0.5 + (xr - xl - 1.0) * i / (STATIONS - 1)
        a_ = max((c for c in xs if c <= xp), default=xs[0])
        b_ = min((c for c in xs if c >= xp), default=xs[-1])
        f = 0.0 if b_ == a_ else (xp - a_) / (b_ - a_)
        rec = {k: cols[a_][k] * (1 - f) + cols[b_][k] * f for k in ("top_u", "bot_u", "top_l", "bot_l")}
        rec["x"] = xp
        rec["open"] = cols[a_]["open"] or cols[b_]["open"]
        st.append(rec)
    for k in ("top_u", "bot_u", "top_l", "bot_l"):
        for r, v in zip(st, smooth([r[k] for r in st], STATION_SMOOTH)):
            r[k] = v
    return st


def edge_at(cols, x, key):
    xs = sorted(cols)
    a_ = max((c for c in xs if c <= x), default=xs[0])
    b_ = min((c for c in xs if c >= x), default=xs[-1])
    f = 0.0 if b_ == a_ else (x - a_) / (b_ - a_)
    return cols[a_][key] * (1 - f) + cols[b_][key] * f


def ring_contours(cols):
    """The lips of an open mouth as one ring: per angle (in the outline's normalised frame) the inner contour (the
    opening's edge) and the outer contour (the lips' outer edge), px. Returns the centre and [(inner, outer)] pairs."""
    xs = sorted(cols)
    xl, xr = xs[0] - 0.5, xs[-1] + 0.5

    def inside(x, y, a, b):
        if x < xl or x > xr:
            return False
        return edge_at(cols, x, a) - 0.5 <= y <= edge_at(cols, x, b) + 0.5

    def in_open(x, y):
        if x < xl or x > xr:
            return False
        return edge_at(cols, x, "bot_u") <= y <= edge_at(cols, x, "top_l")
    ox = [x for x in xs if cols[x]["open"] and cols[x]["top_l"] - cols[x]["bot_u"] >= 2]
    cx = (ox[0] + ox[-1]) / 2
    cy = (edge_at(cols, cx, "bot_u") + edge_at(cols, cx, "top_l")) / 2
    hx = max(cx - xl, xr - cx)
    hy = max(max(cy - cols[x]["top_u"], cols[x]["bot_l"] - cy) for x in xs)
    pairs = []
    for k in range(RING_N):
        th = 2 * math.pi * k / RING_N
        dx, dy = math.cos(th) * hx, math.sin(th) * hy
        t, ti, to = 0.0, None, None
        while t < 1.4:
            x, y = cx + dx * t, cy + dy * t
            if ti is None and not in_open(x, y):
                ti = t
            if ti is not None:
                if inside(x, y, "top_u", "bot_l"):
                    to = t
                else:
                    break
            t += 0.002
        ti = ti or 0.0
        to = max(to or ti, ti + 0.004)
        pairs.append(((cx + dx * ti, cy + dy * ti), (cx + dx * to, cy + dy * to)))
    return (cx, cy), pairs


def lowpass(vals, keep):
    """A closed sequence with only its first `keep` Fourier harmonics: a smooth curve through the measured one."""
    f = np.fft.rfft(np.asarray(vals, float))
    f[keep + 1:] = 0
    return [float(v) for v in np.fft.irfft(f, len(vals))]


def circ_smooth(vals, n):
    v = list(vals)
    for _ in range(n):
        v = [(v[i - 1] + 2 * v[i] + v[(i + 1) % len(v)]) / 4 for i in range(len(v))]
    return v


def build_piece(bvh, m, design, shape, world, mats, coll, origin):
    """One mouth piece from one panel's measured columns, in world space; returns the object and its measures.
    world(x_px, y_px) -> (x, z) in m. An open mouth is one ring (a torus whose section spans the lips between the
    opening's edge and the outer edge at each angle); a closed one is two tubes, upper and lower lip, meeting at
    the crease."""
    cols = m["cols"]
    xs = sorted(cols)
    xl, xr = xs[0], xs[-1]
    push = PUSH.get(design, {}).get(shape, PUSH.get(design, {}).get("*", 0.0))
    back = LOWER_BACK.get(design, 0.0)
    st = stations(cols)
    b = G.Built()
    mi_lip = b.slot(mats["lip"])
    mi_in = b.slot(mats["inner"])
    n_open = sum(1 for x in xs if cols[x]["open"] and cols[x]["top_l"] - cols[x]["bot_u"] >= 3)
    sections = []  # (px centre, world centre on the lip's axis, depth a, normal)
    meas = {"width_mm": round((world(xr + 0.5, 0)[0] - world(xl - 0.5, 0)[0]) * 1000, 1),
            "height_mm": round((world(0, min(r["top_u"] for r in st) - 0.5)[1]
                                - world(0, max(r["bot_l"] for r in st) + 0.5)[1]) * 1000, 1),
            "max_open_mm": round(max(world(0, r["bot_u"])[1] - world(0, r["top_l"])[1] for r in st) * 1000, 1)}
    if shape in RING_SHAPES and n_open >= 10:
        meas["form"] = "ring"
        (cx, cy), pairs = ring_contours(cols)
        ins = [world(*p[0]) for p in pairs]
        outs = [world(*p[1]) for p in pairs]
        mid = [((i[0] + o[0]) / 2, (i[1] + o[1]) / 2) for i, o in zip(ins, outs)]
        hw = [max(MIN_B, math.hypot(o[0] - i[0], o[1] - i[1]) / 2) for i, o in zip(ins, outs)]
        mx, mz = lowpass([q[0] for q in mid], RING_KEEP["centre"]), lowpass([q[1] for q in mid], RING_KEEP["centre"])
        hw = [max(MIN_B, h) for h in lowpass(hw, RING_KEEP["width"])]
        pn = [surf(bvh, mx[k], mz[k]) for k in range(RING_N)]  # S7: the skin points' depth and normals smoothed
        py_ = circ_smooth([q[0].y for q in pn], NORMAL_SMOOTH)
        nn_ = [circ_smooth([q[1][i] for q in pn], NORMAL_SMOOTH) for i in range(3)]
        rings = []
        for k in range(RING_N):
            th = 2 * math.pi * k / RING_N
            p = Vector((pn[k][0].x, py_[k], pn[k][0].z))
            n = Vector((nn_[0][k], nn_[1][k], nn_[2][k])).normalized()
            a = DEPTH_A * hw[k] + DEPTH_C
            low = G.smoothstep(-0.35, 0.35, math.sin(th))  # px y grows downward: sin > 0 is the lower lip
            c3 = p + n * (a * (1 - SINK) + push + back * low)
            nxt = ((mx[(k + 1) % RING_N] - mx[k - 1]), (mz[(k + 1) % RING_N] - mz[k - 1]))
            tang = Vector((nxt[0], 0.0, nxt[1]))
            radial = tang.cross(n).normalized()  # in the skin's plane, across the ring
            if radial.dot(Vector((mx[k] - world(cx, cy)[0], 0.0, mz[k] - world(cx, cy)[1]))) < 0:
                radial = -radial
            ring = []
            for j in range(RING_SEG):
                ph = 2 * math.pi * j / RING_SEG
                ring.append(b.vert(c3 + n * (a * math.cos(ph)) + radial * (hw[k] * math.sin(ph))))
            rings.append(ring)
            sections.append((((pairs[k][0][0] + pairs[k][1][0]) / 2, (pairs[k][0][1] + pairs[k][1][1]) / 2), c3, a, n, p))
        for k in range(RING_N):
            for j in range(RING_SEG):
                b.face((rings[k][j], rings[k][(j + 1) % RING_SEG], rings[(k + 1) % RING_N][(j + 1) % RING_SEG],
                        rings[(k + 1) % RING_N][j]), mi_lip)
        # the dark cup: a disc from the opening's centre out to under the lips' axis, on the skin
        cw = world(cx, cy)
        centre = b.vert(surf(bvh, *cw)[0] + surf(bvh, *cw)[1] * 0.0012)
        rows = 5
        grid = []
        for k in range(RING_N):
            col = []
            for j in range(1, rows + 1):
                f = j / rows
                p, n = surf(bvh, cw[0] + (mx[k] - cw[0]) * f, cw[1] + (mz[k] - cw[1]) * f)
                col.append(b.vert(p + n * 0.0012))
            grid.append(col)
        for k in range(RING_N):
            k2 = (k + 1) % RING_N
            b.face((centre, grid[k][0], grid[k2][0]), mi_in)
            for j in range(rows - 1):
                b.face((grid[k][j], grid[k][j + 1], grid[k2][j + 1], grid[k2][j]), mi_in)
    else:
        meas["form"] = "tubes"
        lips = {}
        for lip in ("u", "l"):
            cs, ra, rb, ns = [], [], [], []
            for r in st:
                if lip == "u":
                    t, bt = r["top_u"], r["bot_u"] + (0.0 if r["open"] else SEAM_OVERLAP)
                else:
                    t, bt = r["top_l"] - (0.0 if r["open"] else SEAM_OVERLAP), r["bot_l"]
                x, zt = world(r["x"], t - 0.5)
                _, zb = world(r["x"], bt + 0.5)
                hb = max(MIN_B, (zt - zb) / 2)
                a = DEPTH_A * hb + DEPTH_C
                p, n = surf(bvh, x, (zt + zb) / 2)
                env = math.sin(math.pi * (r["x"] - xl) / max(1.0, xr - xl)) ** 0.5
                c3 = p + n * (a * (1 - SINK) + (push + (back if lip == "l" else 0.0)) * env)
                cs.append(c3)
                ra.append(a)
                rb.append(hb)
                ns.append(n)
                sections.append(((r["x"], (t + bt) / 2), c3, a, n, p))
            lips[lip] = (cs, ra, rb, ns)
        # S7: smooth paths (the head's facets made the normals, and so the lips, ripple), and soft corners: over the
        # last CORNER share at each end both lips' centres meet and sink into the skin, so neither floats or cuts off
        nst = len(st)
        sm = {}
        for lip, (cs, ra, rb, ns) in lips.items():
            cs = [Vector(v) for v in zip(*(smooth([c[i] for c in cs], NORMAL_SMOOTH) for i in range(3)))]
            ns = [Vector(v).normalized() for v in zip(*(smooth([c[i] for c in ns], NORMAL_SMOOTH) for i in range(3)))]
            sm[lip] = [cs, list(ra), list(rb), ns]
        for i in range(nst):
            e = min(i, nst - 1 - i) / max(1.0, (nst - 1) * CORNER["share"])
            w = 1.0 - G.smoothstep(0.0, 1.0, e)
            if w <= 0.0:
                continue
            mid = (sm["u"][0][i] + sm["l"][0][i]) / 2
            for lip in ("u", "l"):
                cs, ra, rb, ns = sm[lip]
                c = cs[i].lerp(mid, CORNER["join"] * w)
                cs[i] = c - ns[i] * (CORNER["tuck"] * ra[i] * w * w)
        for lip in ("u", "l"):
            G.tube(b, *sm[lip], mi_lip, seg=14)
        if m["teeth"]:  # the dark between the teeth and behind them, from lip axis to lip axis
            rows = 5
            grid = []
            for r in st:
                col = []
                for j in range(rows):
                    y = (r["top_u"] + r["bot_u"]) / 2 + ((r["top_l"] + r["bot_l"]) / 2 - (r["top_u"] + r["bot_u"]) / 2) * j / (rows - 1)
                    p, n = surf(bvh, *world(r["x"], y))
                    col.append(b.vert(p + n * 0.0012))
                grid.append(col)
            for i in range(len(grid) - 1):
                for j in range(rows - 1):
                    b.face((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]), mi_in)
    # the tongue: where the panel shows one, an arch from the lower lip's axis up to its measured top, on the cup
    tcols = [x for x in xs if "tongue_top" in cols[x]]
    if tcols:  # the longest run of neighbouring columns (gaps up to 3 px)
        groups, g = [], [tcols[0]]
        for x in tcols[1:]:
            if x - g[-1] <= 3:
                g.append(x)
            else:
                groups.append(g)
                g = [x]
        groups.append(g)
        tcols = max(groups, key=len)
    if len(tcols) >= 12 and meas.get("form") == "ring":
        mi_t = b.slot(mats["tongue"])
        tl, tr = tcols[0], tcols[-1]
        xm, half = (tl + tr) / 2, (tr - tl) / 2
        centre_cols = [x for x in tcols if abs(x - xm) <= half / 3]
        top = float(np.median([cols[x]["tongue_top"] for x in centre_cols]))
        base_m = float(np.median([(cols[x]["top_l"] + cols[x]["bot_l"]) / 2 for x in centre_cols]))
        n_t = 21
        grid = []
        for i in range(n_t):
            u = -1 + 2 * i / (n_t - 1)
            xp = xm + u * half
            base = (edge_at(cols, xp, "top_l") + edge_at(cols, xp, "bot_l")) / 2
            yt = base - (base_m - top) * math.sqrt(max(0.0, 1 - u * u))
            col = []
            for j in range(6):
                f = j / 5
                p, n = surf(bvh, *world(xp, yt + (base - yt) * f))
                dome = 0.0028 * math.sqrt(max(0.0, 1 - u * u)) * math.sin(math.pi * (0.2 + 0.8 * f) / 1.0) ** 0.5
                col.append(b.vert(p + n * (0.0020 + dome)))
            grid.append(col)
        for i in range(n_t - 1):
            for j in range(5):
                b.face((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]), mi_t)
        meas["tongue_mm"] = [round((world(tr, 0)[0] - world(tl, 0)[0]) * 1000, 1),
                             round((world(0, top)[1] - world(0, base_m)[1]) * 1000, 1)]
    if m["teeth"] and shape != "M":
        mi_te = b.slot(mats["teeth"])
        meas["teeth_mm"] = []
        for t in m["teeth"]:
            x0, zt = world(t["x0"], t["y0"])
            x1, zb = world(t["x1"], t["y1"])
            zt += TOOTH_TUCK
            xc, zc = (x0 + x1) / 2, (zt + zb) / 2
            p, n = surf(bvh, xc, zc)
            # its front: just in front of the upper lip's axis, and in front of any lip it hangs over
            tx, ty = (t["x0"] + t["x1"]) / 2, t["y1"]
            near = min(sections, key=lambda s: (s[0][0] - tx) ** 2 + (s[0][1] - ty) ** 2)
            upper = [s for s in sections if s[0][1] < (t["y0"] + t["y1"]) / 2]
            up = min(upper, key=lambda s: abs(s[0][0] - tx)) if upper else near
            front = (up[1] - p).dot(n) + 0.0015
            if t["y0"] - 1 <= near[0][1] <= t["y1"] + 3:  # it hangs over that lip (the overbite's rest): in front of it
                front = max(front, (near[1] - p).dot(n) + near[2] + 0.0005)
            c = p + n * (front - TOOTH_D / 2)
            bm = bmesh.new()
            bmesh.ops.create_cube(bm, size=1.0)
            bmesh.ops.bevel(bm, geom=bm.edges[:], offset=0.30, segments=3, affect="EDGES", profile=0.5)
            rot = G.frame(Vector(), n).to_3x3()
            for v in bm.verts:
                v.co = c + rot @ Vector((v.co.x * (x1 - x0), v.co.y * TOOTH_D, v.co.z * (zt - zb)))
            for f in bm.faces:
                b.face([b.vert(v.co) for v in f.verts], mi_te)
            bm.free()
            meas["teeth_mm"].append([round((x1 - x0) * 1000, 1), round((zt - TOOTH_TUCK - zb) * 1000, 1)])
    bmesh.ops.remove_doubles(b.bm, verts=b.bm.verts[:], dist=1e-7)
    ob = G.to_object(b, f"mouth_{design}_{shape}", coll, origin)
    return ob, meas, st


def alpha_mask(m, y0, y1, x0, x1):
    C = m["C"]
    a = (C["lip"] | C["tongue"] | C["teeth"]).astype(np.float32)
    for x, r in m["cols"].items():  # the opening between the lips
        a[int(math.floor(r["top_u"])):int(math.ceil(r["bot_l"])) + 1, x] = 1.0
    a = a[y0:y1, x0:x1]
    # one pixel out, then two box blurs: a soft edge
    d = a.copy()
    d[1:, :] = np.maximum(d[1:, :], a[:-1, :])
    d[:-1, :] = np.maximum(d[:-1, :], a[1:, :])
    d[:, 1:] = np.maximum(d[:, 1:], a[:, :-1])
    d[:, :-1] = np.maximum(d[:, :-1], a[:, 1:])
    for _ in range(2):
        p = np.pad(d, 1, mode="edge")
        d = sum(p[i:i + d.shape[0], j:j + d.shape[1]] for i in range(3) for j in range(3)) / 9.0
    return d


def flip_shell(bvh, name, world, win, cell, mat, coll, origin):
    """A shell of the head's surface over the panel window win (x0, y0, w, h in px; world maps px to the head),
    FLIP_OUT out, its UVs on cell (col, row) of the 3 x 2 atlas."""
    x0, y0, w, h = win
    nx, nz = 41, 31
    b = G.Built()
    mi = b.slot(mat)
    uvs, grid = [], []
    for i in range(nx):
        col = []
        for j in range(nz):
            p, n = surf(bvh, *world(x0 - 0.5 + w * i / (nx - 1), y0 - 0.5 + h * j / (nz - 1)))
            col.append(b.vert(p + n * FLIP_OUT))
            uvs.append(((cell[0] + i / (nx - 1)) / 3.0, 1.0 - (cell[1] + j / (nz - 1)) / 2.0))
        grid.append(col)
    for i in range(nx - 1):
        for j in range(nz - 1):
            b.face((grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]), mi)
    ob = G.to_object(b, name, coll, origin, recalc=False)
    uv = ob.data.uv_layers["UVMap"]
    for lp in ob.data.loops:
        uv.data[lp.index].uv = uvs[lp.vertex_index]
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def plain(name, srgb, rough, spec):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*srgb_to_lin(srgb), 1)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Specular IOR Level"].default_value = spec
    return m


def flip_material(name, image):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = image
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    bsdf.inputs["Roughness"].default_value = 0.55
    bsdf.inputs["Specular IOR Level"].default_value = 0.3
    if hasattr(m, "surface_render_method"):
        m.surface_render_method = "BLENDED"
    else:
        m.blend_method = "BLEND"
    return m


def overlay(P, m, y0, x0):
    """The panel's window with the measured edges drawn: upper lip red, lower lip blue, opening yellow, teeth green."""
    img = P[y0:y0 + WIN[1], x0:x0 + WIN[0]].copy()

    def dot(x, y, c):
        yi, xi = int(round(y)) - y0, int(round(x)) - x0
        if 0 <= yi < img.shape[0] and 0 <= xi < img.shape[1]:
            img[yi, xi] = c
    for x, r in m["cols"].items():
        dot(x, r["top_u"], (1, 0, 0))
        dot(x, r["bot_u"], (1, 1, 0) if r["open"] else (1, 0, 1))
        dot(x, r["top_l"], (1, 1, 0) if r["open"] else (1, 0, 1))
        dot(x, r["bot_l"], (0, 0.3, 1))
        if "tongue_top" in r:
            dot(x, r["tongue_top"], (1, 1, 1))
    for t in m["teeth"]:
        for x in range(int(t["x0"] + 0.5), int(t["x1"] + 0.5)):
            dot(x, t["y0"], (0, 1, 0))
            dot(x, t["y1"], (0, 1, 0))
    return img


def main():
    a = args()
    out = Path(a.out)
    for sub in ("build", "export", "measure", "ref"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=a.character)
    body = bpy.data.objects["Body"]
    bvh = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    mouth = bpy.data.objects["Mouth"]
    sock = mouth.matrix_world.copy()
    z_sock = sock.translation.z
    old = [o for o in bpy.data.objects if o.name.startswith("mouth_")]
    for o in old:
        bpy.data.objects.remove(o)
    coll = bpy.context.scene.collection
    mats = {"lip": bpy.data.materials["alien_lip"], "inner": bpy.data.materials["alien_mouth_inner"],
            "teeth": bpy.data.materials["alien_teeth"], "tongue": plain("alien_tongue", TONGUE, 0.5, 0.4)}
    # the head's front silhouette half width at the socket's height
    hw = []
    for sx in (1, -1):
        best = 0.0
        for j in range(60):
            h = bvh.ray_cast(Vector((sx * 0.5, -0.12 + 0.004 * j, z_sock)), Vector((-sx, 0, 0)))
            if h[0] is not None:
                best = max(best, abs(h[0].x))
        hw.append(best)
    face_w_m = hw[0] + hw[1]
    rep = {"socket": [round(x, 5) for x in sock.translation], "face_w_at_socket_m": round(face_w_m, 4), "designs": {}}
    nodes = {}
    profiles = {}
    meas_imgs = []
    for design in ("frog", "overbite"):
        sheet = load_rgb(getattr(a, design))
        ms = []
        for k, shape in enumerate(SHAPES):
            px, py = (k % 3) * PANEL, (k // 3) * PANEL
            ms.append(measure_panel(sheet[py:py + PANEL, px:px + PANEL]))
        r0 = ms[0]
        xs = sorted(r0["cols"])
        seam_rows = [(r0["cols"][x]["bot_u"] + r0["cols"][x]["top_l"]) / 2 for x in xs if abs(x - r0["hc"]) < 30]
        seam_y = sum(seam_rows) / len(seam_rows)
        off = seam_y - r0["ny"]
        fl, fr = width_at(r0["C"]["bg"], seam_y)
        K = face_w_m / (fr - fl)
        drep = {"K_mm_per_px": round(K * 1000, 4), "rest_seam_below_nostrils_px": round(off, 1),
                "face_w_px_at_rest_seam": fr - fl, "shapes": {}}
        atlas = np.zeros((WIN[1] * 2, WIN[0] * 3, 4), np.float32)
        flip_rects, flip_wins, worlds = {}, {}, {}
        for k, shape in enumerate(SHAPES):
            m = ms[k]
            kp = K * max(0.94, min(1.06, r0["face_w_nose"] / m["face_w_nose"]))
            hc, ny = m["hc"], m["ny"]
            seam = ny + off
            low = max(r["bot_l"] for r in m["cols"].values()) + 0.5
            z_low = z_sock - (low - seam) * kp
            squeeze = 1.0 if z_low >= CHIN_Z else (z_sock - CHIN_Z) / (z_sock - z_low)

            half = max(abs(x - hc) for x in m["cols"]) + 0.5
            sx = min(1.0, FACE_FILL * face_w_m / 2 / (half * kp))

            def world(x, y, hc=hc, kp=kp, seam=seam, squeeze=squeeze, sx=sx):
                dz = (y - seam) * kp
                return (x - hc) * kp * sx, z_sock - (dz * squeeze if dz > 0 else dz)
            ob, meas, st = build_piece(bvh, m, design, shape, world, mats, coll, sock)
            meas["below_seam_squeeze"] = round(squeeze, 3)
            meas["width_squeeze"] = round(sx, 3)
            worlds[shape] = world
            ob.parent = mouth
            ob.matrix_parent_inverse.identity()
            ob.matrix_basis = Matrix.Identity(4)
            # the flipbook cell: the window under the nostrils, centred on the head
            y0 = int(round(ny)) + NOSE_GAP
            x0 = int(round(hc)) - WIN[0] // 2
            px, py = (k % 3) * PANEL, (k // 3) * PANEL
            P = sheet[py:py + PANEL, px:px + PANEL]
            crop = P[y0:y0 + WIN[1], x0:x0 + WIN[0]]
            al = alpha_mask(m, y0, y0 + WIN[1], x0, x0 + WIN[0])
            cy, cx = (k // 3) * WIN[1], (k % 3) * WIN[0]
            atlas[cy:cy + WIN[1], cx:cx + WIN[0], :3] = crop
            atlas[cy:cy + WIN[1], cx:cx + WIN[0], 3] = al
            flip_wins[shape] = (x0, y0, WIN[0], WIN[1])
            xa, za = world(x0 - 0.5, y0 - 0.5)
            xb, zb = world(x0 + WIN[0] - 0.5, y0 + WIN[1] - 0.5)
            zb_lin = za - WIN[1] * kp  # the camera frames the window unsqueezed, as the sheet shows it
            flip_rects[shape] = [round(v, 5) for v in (xa, xb, zb_lin, za)]
            img = save_rgba(crop, out / "ref" / f"{design}_{shape}.png", f"ref_{design}_{shape}")
            bpy.data.images.remove(img)
            meas_imgs.append(overlay(P, m, y0, x0))
            meas.update({"K_mm_per_px": round(kp * 1000, 4), "nostril_y": round(ny, 1), "head_cx": round(hc, 1),
                         "face_w_nose_px": m["face_w_nose"], "teeth_px": m["teeth"],
                         "verts": len(ob.data.vertices), "tris": sum(len(p.vertices) - 2 for p in ob.data.polygons)})
            drep["shapes"][shape] = meas
            profiles[f"{design}_{shape}"] = {"cols": {str(x): r for x, r in m["cols"].items()}, "teeth": m["teeth"],
                                             "hc": hc, "ny": ny, "K": kp}
        img = save_rgba(atlas, out / "export" / f"mouth_flip_{design}.png", f"mouth_flip_{design}")
        img.pack()
        fm = flip_material(f"alien_mouth_flip_{design}", img)
        for k, shape in enumerate(SHAPES):
            ob = flip_shell(bvh, f"mouthflip_{design}_{shape}", worlds[shape], flip_wins[shape], (k % 3, k // 3), fm,
                            coll, sock)
            ob.parent = mouth
            ob.matrix_parent_inverse.identity()
            ob.matrix_basis = Matrix.Identity(4)
        drep["flip_rects_m"] = flip_rects
        rep["designs"][design] = drep
        nodes[design] = {v: f"mouth_{design}_{v}" for v in SHAPES}
        nodes[f"flip_{design}"] = {v: f"mouthflip_{design}_{v}" for v in SHAPES}
    # the measure sheet: 3 columns (rest M small / A E O) x 4 rows (frog 2, overbite 2), 2x
    rows = []
    for i in range(0, 12, 3):
        rows.append(np.concatenate(meas_imgs[i:i + 3], 1))
    sheet_img = np.concatenate(rows, 0).repeat(2, 0).repeat(2, 1)
    im = save_rgba(sheet_img, out / "measure" / "measure.png", "measure")
    bpy.data.images.remove(im)
    (out / "profiles.json").write_text(json.dumps(profiles, indent=0), encoding="utf-8", newline="\n")
    for o in bpy.data.objects:
        if o.name.startswith(("mouth_", "mouthflip_")):
            for p in o.data.polygons:
                p.use_smooth = True
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "build" / "alien_character.blend"))
    opts = dict(export_glb.options(False), export_image_format="AUTO")
    glb = out / "export" / "alien_character.glb"
    res = bpy.ops.export_scene.gltf(filepath=str(glb), **opts)
    if res != {"FINISHED"}:
        raise SystemExit(f"export: {res}")
    cj = json.loads((Path(a.character).parent.parent / "export" / "character.json").read_text(encoding="utf-8"))
    cj["nodes"]["mouths"] = nodes
    cj["note_s6"] = ("art #196 S6: the mouth pieces rebuilt from the GPT sheets mf1 and mo1; the overbite's teeth are "
                     "inside each overbite piece (no mouth_overbite_teeth node). mouthflip_<design>_<shape>: the "
                     "flipbook test, one face shell per shape on the atlas mouth_flip_<design>.png (alpha blend); "
                     "show either one 3D piece or one flip shell.")
    cj["report_s6"] = rep
    (out / "export" / "character.json").write_text(json.dumps(cj, indent=1), encoding="utf-8", newline="\n")
    (out / "build_report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8", newline="\n")
    print("MOUTHS " + json.dumps(rep))


main()
