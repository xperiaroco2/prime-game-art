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
import alien_fangs_geom as FG  # noqa: E402
import alien_lips_geom as LP  # noqa: E402
import alien_parts_geom as G  # noqa: E402
import alien_tongue_geom as TG  # noqa: E402
import export_glb  # noqa: E402

SHAPES = ("rest", "M", "small", "A", "E", "O")
PANEL = 512
WIN = (224, 150)  # the mouth window per panel, px (w, h); its top NOSE_GAP px under the nostrils
NOSE_GAP = 14
DEPTH_A, DEPTH_C = 0.80, 0.0012  # a lip tube's depth from its measured half-height, m
SINK = 0.30  # the share of the depth inside the skin
PUSH = {"frog": {"O": 0.007}, "overbite": {"O": 0.006, "*": 0.004},
        "pout": {"O": 0.008, "*": 0.003},
        "fangs": {"O": 0.006, "*": 0.001},
        "tongue": {"O": 0.006, "*": 0.002}}  # the lips' push out of the skin, m (O: pucker; M12: the pout stands out)
LOWER_BACK = {"overbite": -0.002}  # the overbite's lower lip sits back
MIN_B = 0.0011  # a lip's smallest half-height (the corners), m
STATIONS = 41
RING_N, RING_SEG = 96, 14  # an open mouth's ring: sections around, vertices per section
SEAM_OVERLAP = 1.5  # a closed mouth's lips overlap at the crease, px
RING_SHAPES = ("A", "E", "O")  # the wide shapes are one ring; rest, M and small two tubes
FACE_FILL = 0.86  # a mouth's half width at most this share of the face's half width at the socket: wider is squeezed
CHIN_Z = 1.443  # the lowest a lip may reach on the head (S7: the sculpted chin is at 1.437): deeper is squeezed, m
CHIN_GAP = 0.006  # with --parts-report: CHIN_Z is the report's sculpted chin plus this
# S8: the open shapes against the head. The sheets' heads are wider at the mouth than ours (our face narrows to the
# chin), so A, measured to the sheet's face width, filled the lower face and its lower lip reached the chin ("far too
# big"), and A's and E's far corners passed the cheek at three-quarter view. Each shape's size times this:
SHAPE_SCALE = {"A": 0.72, "E": 0.82, "O": 0.94}  # S8b: A and E narrower (their far corner passed the cheek); S9: A 0.77 -> 0.72 (frog A's far corner still reached the face's edge)
# S8b: an open ring hugs the face at its sides: where the skin turns away from the front (|normal x| from
# side[0] to side[1]) its lift off the skin and its width shrink by up to `keep`, so the far corner at three-quarter
# view stays inside the cheek's silhouette.
RING_SIDE = {"side": (0.30, 0.75), "keep": 0.55}
# M12 (art #196): a design's own open-shape scales (over SHAPE_SCALE) and pixel classes. mp1's red lips have blue about
# green (B - G -0.02 to -0.05), which the coral sheets' lip class (B - G < -0.035) half called tongue; its tongue
# is pinker (B - G about 0 to +0.01), so the lip/tongue split moves to -0.008 for it. Its mouth's inside is a dark
# red that grades into the lips (R 0.44 .. 0.05), which the lip class took as lip (the openings measured half their
# size, the lips too tall), so in A and E (PALETTE_SHAPE) a lip pixel needs R >= 0.50 (lip_min_r; the lips' own
# shaded edges are 0.50 .. 0.55). The closed shapes keep 0.30 (their dark crease is no opening), and so does O (its
# hole's edge drops straight from 0.4 to 0.05; at 0.50 the kiss's hole measured too big). A and E are about as wide as
# rest on the sheet, so they shrink less than the frog's.
SHAPE_SCALE_DESIGN = {"pout": {"A": 0.95, "E": 0.90, "O": 0.94}, "fangs": {"A": 1.08, "E": 0.95, "O": 0.94},
                      "tongue": {"A": 1.0, "E": 0.90, "O": 0.94}}
PALETTE = {"pout": {"tongue_bg": -0.008}}
PALETTE_SHAPE = {"pout": {"A": {"lip_min_r": 0.50}, "E": {"lip_min_r": 0.50}}}
# M12: where an open ring's dark cup ends, as a share of the lip's half width in from its axis toward the opening (0:
# under the axis, as S6..M10): the pout's cup stays under the lips' inner half.
CUP_IN = {"pout": 0.6, "fangs": 0.6, "tongue": 0.6}
# M13 (art #196): the fangs (mg2) cross the lips in every panel, so the measure fills a fang's columns (and FANG_PAD px
# either side) from the clean columns beside them (FILL_TEETH), instead of the overbite's rule (a tooth hides the lower
# lip's top edge); the fangs themselves are built by build_fangs from the measured tooth boxes (alien_fangs_geom),
# never as the overbite's boxes, and a closed fangs piece has no dark between its lips.
FILL_TEETH = {"fangs"}
FANG_PAD = 3
# M14 (art #196): the tongue (mt2) pokes out over the lower lip in every panel, hiding it: the measure refills the
# columns where the tongue covers the lower lip (FANG_PAD px wider) from the clean columns beside them, as the fangs'
# (tongue_cover); its teeth and tongue are designed (alien_tongue_geom, build_tongue_out, build_teeth), never the
# overbite's measured boxes or the measured in-mouth tongue, and an open closed-form piece (rest, small) has the dark
# between its lips.
FILL_TONGUE = {"tongue"}
RING_KEEP = {"centre": 9, "width": 5}  # S7: the open ring's centre line and lip width keep this many harmonics
NORMAL_SMOOTH = 8  # S7: passes over the skin points and normals under a lip (the decimated head's facets rippled it)
STATION_SMOOTH = 5  # S7: passes over the closed lips' measured edges (2 left ripples)
CORNER = {"share": 0.16, "join": 0.85, "tuck": 0.9}  # S7: over the last share of a closed mouth's stations the two
# lips' centres meet (join) and sink into the skin by tuck times their depth, so the corner is a soft tucked dimple
TOOTH_D, TOOTH_TUCK = 0.0055, 0.003  # a tooth's depth, and how far it runs up under the upper lip, m
# S8b: the tongue as a tongue, not a second lower lip: TONGUE_SHAPE["width"] of the measured run, a rounded
# dome with a midline groove, lifted less off the cup
TONGUE_TUCK = 0.003  # M13b: a designed tongue's base this far under the opening's lower edge, m
TONGUE_SHAPE = {"width": 0.62, "dome": 0.0034, "groove": 0.35, "lift": 0.0012}
TONGUE_SKIN_GAP = 0.0012  # M14: the hanging tongue's underside at least this far in front of the chin, m
TONGUE = (0.66, 0.30, 0.33)  # sRGB (S7: a deeper rose; the lips' near twin read as a doubled lower lip in A)
FLIP_OUT = 0.0015


def args():
    p = argparse.ArgumentParser()
    p.add_argument("--character", required=True)
    p.add_argument("--frog", required=True)
    p.add_argument("--overbite", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--parts-report", help="alien_parts.py's build_report.json: CHIN_Z from its sculpted chin")
    p.add_argument("--lips", default="", help="M8: JSON merged over alien_lips_geom.LIP_SHAPE, or m6c (the old lips)")
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


def classes(P, tongue_bg=-0.035, lip_min_r=0.30):
    """Pixel classes of a panel; tongue_bg: the blue-minus-green split between lip (below) and tongue, lip_min_r a
    lip pixel's least red (M12's pout)."""
    R, Gc, B = P[..., 0], P[..., 1], P[..., 2]
    lum = R + Gc + B
    bg = (np.abs(R - Gc) < 0.04) & (np.abs(Gc - B) < 0.04) & (R > 0.33) & (R < 0.52)
    teeth = (R > 0.68) & (Gc > 0.60) & (B > 0.42) & (R >= Gc - 0.01) & (B < Gc) & (R - Gc < 0.16)
    lip = (R > Gc + 0.15) & (R > lip_min_r) & (B - Gc < tongue_bg) & ~teeth
    tongue = (R > Gc + 0.08) & (R > 0.20) & (B - Gc >= tongue_bg) & ~teeth
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


def measure_panel(P, design="", shape=""):
    """The mouth's columns in one panel: per x (panel px) the lip edges, the opening, the tongue top, the teeth."""
    C = classes(P, **PALETTE.get(design, {}), **PALETTE_SHAPE.get(design, {}).get(shape, {}))
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
    teeth = []
    for a, b in runs([any(t[0] == x for t in teeth_cols) for x in range(int(hc) - 120, int(hc) + 121)]):
        group = [t for t in teeth_cols if int(hc) - 120 + a <= t[0] <= int(hc) - 120 + b]
        if b - a + 1 >= 4:
            teeth.append({"x0": group[0][0] - 0.5, "x1": group[-1][0] + 0.5, "y0": min(t[1] for t in group) - 0.5,
                          "y1": max(t[2] for t in group) + 0.5})
    if design in FILL_TEETH:  # M13: every edge under a fang from the clean columns beside it
        return {"hc": hc, "ny": ny, "nostril_box": nbox, "face_w_nose": r1 - l1,
                "cols": fill_teeth(cols, teeth), "teeth": teeth, "C": C}
    if design in FILL_TONGUE:  # M14: every edge under the tongue from the clean columns beside it
        cover = tongue_cover(C, cols, y0, y1)
        return {"hc": hc, "ny": ny, "nostril_box": nbox, "face_w_nose": r1 - l1,
                "cols": fill_teeth(cols, cover), "teeth": teeth, "tongue_cover": cover, "C": C}
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
    return {"hc": hc, "ny": ny, "nostril_box": nbox, "face_w_nose": r1 - l1, "cols": cols, "teeth": teeth, "C": C}


def fill_teeth(cols, teeth):
    """M13: the columns under each tooth box (FANG_PAD px wider) refilled from the nearest clean columns either side
    (all four lip edges and the opening, linearly). A fang at the mouth's very end (O's fangs sit at its sides): its
    columns up to the fang's centre take the nearest clean column's edges, the ones past it are dropped (the lips end
    under the fang)."""
    xs = sorted(cols)
    bad = {x for x in xs for t in teeth if t["x0"] - FANG_PAD <= x <= t["x1"] + FANG_PAD}
    clean = [x for x in xs if x not in bad]
    out = {}
    for x in xs:
        if x not in bad:
            out[x] = cols[x]
            continue
        lft = max((c for c in clean if c < x), default=None)
        rgt = min((c for c in clean if c > x), default=None)
        if lft is None or rgt is None:
            near = lft if rgt is None else rgt
            box = next((t for t in teeth if t["x0"] - FANG_PAD <= x <= t["x1"] + FANG_PAD), None)
            if near is None or box is None or abs(x - near) > abs((box["x0"] + box["x1"]) / 2 - near):
                continue
            lft = rgt = near
        f = (x - lft) / (rgt - lft) if rgt != lft else 0.0
        a, b = cols[lft], cols[rgt]
        rec = {k: a[k] * (1 - f) + b[k] * f for k in ("top_u", "bot_u", "top_l", "bot_l")}
        rec.update(open=a["open"] and b["open"], teeth=True)
        out[x] = rec
    return out


def tongue_cover(C, cols, y0, y1):
    """M14: the runs of columns where the tongue covers the lower lip, as fill_teeth's boxes ({"x0", "x1"}): a column
    with tongue pixels whose lip pixels below the tongue's lowest are fewer than half the lower lip's usual thickness
    (the median of the columns without tongue)."""
    xs = sorted(cols)
    thick = [cols[x]["bot_l"] - cols[x]["top_l"] for x in xs if not C["tongue"][y0:y1, x].any()]
    tl = float(np.median(thick)) if thick else 6.0
    bad = []
    for x in xs:
        tg = np.nonzero(C["tongue"][y0:y1, x])[0]
        if len(tg) < 3:
            continue
        ys = np.nonzero(C["lip"][y0:y1, x])[0]
        if int((ys > tg.max()).sum()) < 0.5 * tl:
            bad.append(x)
    return [{"x0": xs_[0] - 0.5, "x1": xs_[-1] + 0.5}
            for xs_ in ([xs[i] for i in range(a, b + 1)] for a, b in runs([x in bad for x in xs])) if len(xs_) >= 2]


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


def ring_measure(cols):
    """M12b: an open panel's scalars for alien_lips_geom.ring_param (px): the lips' outer centre cx and half width W,
    the opening's centre row cy and half height hu, each lip's thickness t_u, t_l, all at the centre columns."""
    xs = sorted(cols)
    xl, xr = xs[0] - 0.5, xs[-1] + 0.5
    cx = (xl + xr) / 2
    near = [x for x in xs if abs(x - cx) <= 4] or [min(xs, key=lambda x: abs(x - cx))]

    def med(key):
        v = sorted(cols[x][key] for x in near)
        return v[len(v) // 2]
    top_u, bot_u, top_l, bot_l = med("top_u"), med("bot_u"), med("top_l"), med("bot_l")
    return {"cx": cx, "cy": (bot_u + top_l) / 2, "W": (xr - xl) / 2, "hu": max(0.5, (top_l - bot_u) / 2),
            "t_u": bot_u - top_u + 0.5, "t_l": bot_l - top_l + 0.5}


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


def mirrored(cs, ra, rb, ns):
    """M16: a lip's stations (centres, depths, half heights, normals; corner to corner across x = 0) with each station
    the mean of itself and its mirror station mirrored (x -> -x): exactly symmetric across the face's centre line."""
    n = len(cs)

    def mx(v):
        return Vector((-v.x, v.y, v.z))
    cs2 = [(cs[i] + mx(cs[n - 1 - i])) / 2 for i in range(n)]
    ns2 = [(ns[i] + mx(ns[n - 1 - i])).normalized() for i in range(n)]
    ra2 = [(ra[i] + ra[n - 1 - i]) / 2 for i in range(n)]
    rb2 = [(rb[i] + rb[n - 1 - i]) / 2 for i in range(n)]
    return cs2, ra2, rb2, ns2


def lip_tube(b, centres, radii_a, radii_b, normals, mi, seg, lips_p, lip):
    """M8: alien_parts_geom.tube with a lip's section (alien_lips_geom.section): the front flatter by lips_p["square"]
    and its swell moved toward the lip line (the upper lip's bottom, the lower lip's top) by lips_p["lean"]."""
    n = len(centres)
    rings = []
    for i in range(n):
        t = (centres[min(i + 1, n - 1)] - centres[max(i - 1, 0)]).normalized()
        nn = (normals[i] - t * normals[i].dot(t)).normalized()
        bb = t.cross(nn).normalized()
        down = 1.0 if bb.z < 0 else -1.0  # sin > 0 along bb points down when bb.z < 0
        toward = down if lip == "u" else -down
        ring = []
        for k in range(seg):
            cn, sn = LP.section(2 * math.pi * k / seg, lips_p["lean"], lips_p["square"], toward)
            ring.append(b.vert(centres[i] + nn * (radii_a[i] * cn) + bb * (radii_b[i] * sn)))
        rings.append(ring)
    for i in range(n - 1):
        for k in range(seg):
            b.face((rings[i][k], rings[i][(k + 1) % seg], rings[i + 1][(k + 1) % seg], rings[i + 1][k]), mi)
    for i, ring in ((0, rings[0]), (n - 1, rings[-1])):
        c = b.vert(centres[i])
        for k in range(seg):
            b.face((ring[k], ring[(k + 1) % seg], c), mi)
    return rings


def build_piece(bvh, m, design, shape, world, mats, coll, origin, lips=None, name=None, fang=None, tongue=None,
                teeth=None):
    """One mouth piece from one panel's measured columns, in world space; returns the object and its measures.
    lips: an alien_lips_geom lip shape (None: LIP_SHAPE_M6C, the S6..M6c lips unchanged); name: the object's name
    (default mouth_<design>_<shape>); fang: an alien_fangs_geom shape (M13: the fangs design's two lower fangs from the
    panel's tooth boxes, build_fangs; mats["fang"] their material); tongue, teeth: alien_tongue_geom's TONGUE and
    TEETH (M14: the tongue design's tongue over the lower lip and its gappy teeth, build_tongue_out and build_teeth;
    mats["tongue_out"] the tongue's material).
    world(x_px, y_px) -> (x, z) in m. An open mouth is one ring (a torus whose section spans the lips between the
    opening's edge and the outer edge at each angle); a closed one is two tubes, upper and lower lip, meeting at
    the crease."""
    cols = m["cols"]
    if design in FILL_TONGUE and shape == "M":  # M14: M's lips pressed shut round the tongue (the sheet's seam)
        cols = {x: dict(c, open=False, bot_u=(c["bot_u"] + c["top_l"]) / 2 - 0.5, top_l=(c["bot_u"] + c["top_l"]) / 2 + 0.5)
                if c["open"] else c for x, c in cols.items()}
    xs = sorted(cols)
    xl, xr = xs[0], xs[-1]
    push = PUSH.get(design, {}).get(shape, PUSH.get(design, {}).get("*", 0.0))
    lips_p = LP.LIP_SHAPE_M6C if lips is None else lips
    back = LOWER_BACK.get(design, 0.0) + lips_p.get("lower_fwd", 0.0)  # M13b: a lip shape's lower lip forward (m)
    world = LP.scale_x(world, lips_p.get("width", 1.0))  # M8b: the mouth's width
    world = LP.scale_size(world, lips_p.get("size", 1.0), origin.translation.z)  # M12: the whole mouth's size
    st = stations(cols)
    b = G.Built()
    mi_lip = b.slot(mats["lip"])
    mi_in = b.slot(mats["inner"])
    n_open = sum(1 for x in xs if cols[x]["open"] and cols[x]["top_l"] - cols[x]["bot_u"] >= 3)
    sections = []  # (px centre, world centre on the lip's axis, depth a, normal)
    anchor = {}  # M13: where the fangs stand (build_fangs)
    rolls = []  # M14: the lower lip's sections (axis, depth, half height, normal), where the tongue lies
    meas = {"width_mm": round((world(xr + 0.5, 0)[0] - world(xl - 0.5, 0)[0]) * 1000, 1),
            "height_mm": round((world(0, min(r["top_u"] for r in st) - 0.5)[1]
                                - world(0, max(r["bot_l"] for r in st) + 0.5)[1]) * 1000, 1),
            "max_open_mm": round(max(world(0, r["bot_u"])[1] - world(0, r["top_l"])[1] for r in st) * 1000, 1)}
    rp = None
    if shape in RING_SHAPES and n_open >= 10:
        meas["form"] = "ring"
        rp = (lips_p.get("ring_param") or {}).get(shape)  # M12b: a designed ring (alien_lips_geom.ring_param)
        if rp:
            rm = ring_measure(cols)
            # M13b: the ring on the face's centre line (the fangs' refilled columns moved A's measured centre 3.5 mm
            # aside); M16b: a mirrored lip shape's too (the pout's A and O were 0.4 and 0.6 mm aside)
            if design in FILL_TEETH or lips_p.get("mirror", 0.0) > 0.0:
                x0, x1 = world(0.0, rm["cy"])[0], world(1.0, rm["cy"])[0]
                rm = dict(rm, cx=-x0 / (x1 - x0))
            (cx, cy), pairs, outer0, cwt = LP.ring_param(rm, rp, lips_p, RING_N)
        else:
            (cx, cy), pairs = ring_contours(cols)
        ins = [world(*p[0]) for p in pairs]
        outs = [world(*p[1]) for p in pairs]
        cz0 = world(cx, cy)[1]
        anchor = {"form": "O" if shape == "O" else "ring",
                  "centre": ((max(q[0] for q in outs) + min(q[0] for q in outs)) / 2, world(cx, cy)[1]),
                  "lower": sorted((q for q in ins if q[1] <= cz0), key=lambda q: q[0]),
                  "shape": shape,
                  "inner_hw": (max(q[0] for q in ins) - min(q[0] for q in ins)) / 2,
                  "outer_hw": (max(q[0] for q in outs) - min(q[0] for q in outs)) / 2,
                  "outer_hh": (max(q[1] for q in outs) - min(q[1] for q in outs)) / 2}
        anchor["upper"] = sorted((q for q in ins if q[1] > cz0), key=lambda q: q[0])  # M14: the opening's top edge
        anchor["open_h"] = max(q[1] for q in ins) - min(q[1] for q in ins)
        mid = [((i[0] + o[0]) / 2, (i[1] + o[1]) / 2) for i, o in zip(ins, outs)]
        hw = [max(MIN_B, math.hypot(o[0] - i[0], o[1] - i[1]) / 2) for i, o in zip(ins, outs)]
        if rp:  # already smooth: no low pass (it rippled E's tight ends)
            meas["ring_mm"] = [round((max(q[0] for q in outs) - min(q[0] for q in outs)) * 1000, 1),
                               round((max(q[1] for q in outs) - min(q[1] for q in outs)) * 1000, 1),
                               round((max(q[0] for q in ins) - min(q[0] for q in ins)) * 1000, 1),
                               round((max(q[1] for q in ins) - min(q[1] for q in ins)) * 1000, 1)]
            mx, mz = [q[0] for q in mid], [q[1] for q in mid]
            hw0 = [max(MIN_B, math.hypot(o[0] - i[0], o[1] - i[1]) / 2)
                   for i, o in zip(ins, (world(*q) for q in outer0))]
        else:
            mx, mz = lowpass([q[0] for q in mid], RING_KEEP["centre"]), lowpass([q[1] for q in mid], RING_KEEP["centre"])
            hw = [max(MIN_B, h) for h in lowpass(hw, RING_KEEP["width"])]
        pn = [surf(bvh, mx[k], mz[k]) for k in range(RING_N)]  # S7: the skin points' depth and normals smoothed
        py_ = circ_smooth([q[0].y for q in pn], NORMAL_SMOOTH)
        nn_ = [circ_smooth([q[1][i] for q in pn], NORMAL_SMOOTH) for i in range(3)]
        rings = []
        ring_p = dict(lips_p, w=lips_p.get("w", 0.0) * lips_p.get("ring", {}).get(shape, 1.0))
        hc = LP.centre_value([math.cos(2 * math.pi * k / RING_N) for k in range(RING_N)], hw)
        n0 = Vector([sum(c) for c in nn_]).normalized()  # M12b: the mouth's mean skin normal
        throat = []  # M12b: per angle the depth of the lips' axis off the skin (the hole's narrowest ring)
        cup = []  # M8: the lips' axis after the reshape (x, z): the dark cup ends under it, never past a thin lip
        for k in range(RING_N):
            th = 2 * math.pi * k / RING_N
            p = Vector((pn[k][0].x, py_[k], pn[k][0].z))
            n = Vector((nn_[0][k], nn_[1][k], nn_[2][k])).normalized()
            keep = rp.get("side_keep", RING_SIDE["keep"]) if rp else RING_SIDE["keep"]
            side = 1.0 - (1.0 - keep) * G.smoothstep(*RING_SIDE["side"], abs(n.x))
            if rp and rp.get("n_flat"):  # M12b: the lips stand out along the mouth's mean normal (n0), not the
                n = n.lerp(n0, rp["n_flat"]).normalized()  # skin's own: the chin's and philtrum's slopes closed O's hole
            low = G.smoothstep(-0.35, 0.35, math.sin(th))  # px y grows downward: sin > 0 is the lower lip
            tuck = 0.0
            if rp:  # M12b: the designed width as is; the depth from the width without the bow, the corners tucked
                hw_k = hw[k]
                dc = rp.get("depth_corner", lips_p["depth_corner"])
                a = (DEPTH_A * hw0[k] + DEPTH_C * (1.0 - (1.0 - dc) * cwt[k])) * side
                tuck = rp.get("tuck", 0.0) * a * cwt[k]
            else:
                # M8: the lips' width round the ring from LIP (thin corners, the bow); the opening's edge stays
                hw_k = max(MIN_B, LP.ring_width(th, hw[k], hc, low, shape, lips_p))
                a = (DEPTH_A * hw_k + DEPTH_C * LP.depth_scale(math.cos(th), ring_p)) * side
            nxt = ((mx[(k + 1) % RING_N] - mx[k - 1]), (mz[(k + 1) % RING_N] - mz[k - 1]))
            tang = Vector((nxt[0], 0.0, nxt[1]))
            radial = tang.cross(n).normalized()  # in the skin's plane, across the ring
            if radial.dot(Vector((mx[k] - world(cx, cy)[0], 0.0, mz[k] - world(cx, cy)[1]))) < 0:
                radial = -radial
            c3 = p + n * (a * (1 - SINK) + (push + back * low) * side - tuck) + radial * ((hw_k - hw[k]) * side)
            if low > 0.5:
                rolls.append((c3.copy(), a, hw_k * side, n.copy()))
            throat.append(a * (1 - SINK) + (push + back * low) * side - tuck)
            ci = (hw_k - hw[k] - CUP_IN.get(design, 0.0) * hw_k) * side  # M12: the cup ends inside the lip
            cup.append((mx[k] + radial.x * ci, mz[k] + radial.z * ci))
            ring = []
            for j in range(RING_SEG):
                ph = 2 * math.pi * j / RING_SEG
                if ring_p["w"] > 0.0:  # the swell toward the opening's edge (sin < 0 is the inner side; M16: a
                    cn, sn = LP.section(ph, (rp or {}).get("lean", lips_p["lean"]), lips_p["square"], -1.0)  # ring's own)
                else:
                    cn, sn = math.cos(ph), math.sin(ph)
                ring.append(b.vert(c3 + n * (a * cn) + radial * (hw_k * side * sn)))
            rings.append(ring)
            sections.append((((pairs[k][0][0] + pairs[k][1][0]) / 2, (pairs[k][0][1] + pairs[k][1][1]) / 2), c3, a, n, p))
        for k in range(RING_N):
            for j in range(RING_SEG):
                b.face((rings[k][j], rings[k][(j + 1) % RING_SEG], rings[(k + 1) % RING_N][(j + 1) % RING_SEG],
                        rings[(k + 1) % RING_N][j]), mi_lip)
        # the dark cup: a disc from the opening's centre out to under the lips' axis, on the skin
        cw = world(cx, cy)
        # M12b: rp["cup_lift"] lifts the cup along n0 by that share of the push, rp["cup_throat"] by that share of the
        # lips' axis depth (the hole's narrowest ring), so a pushed-out kiss (O) shows its dark cup in the hole, not
        # the lips' long lit inner wall; the cup's rim stays inside the lips (0.6 of their half width in)
        lift = Vector((0.0, 0.0, 0.0))
        if rp:
            lift = n0 * (rp.get("cup_lift", 0.0) * push + rp.get("cup_throat", 0.0) * sum(throat) / len(throat))
        # M16c (cup_even): the rim at even angles round the centre, and every cup point off the skin along the mouth's
        # mean normal n0, not the skin's own: the pout O's cup had a fan triangle 0.006 mm^2 (two points 0.06 mm
        # apart where the skin's normal turns fast near the centre), a zero tangent the glTF-Validator rejects
        even = bool(rp and rp.get("cup_even"))
        if even:
            cup = LP.star_resample(cup, cw, RING_N)

        def off(q):
            return q[0] + (n0 if even else q[1]) * 0.0012
        centre = b.vert(off(surf(bvh, *cw)) + lift)
        rows = 5
        grid = []
        for k in range(RING_N):
            col = []
            for j in range(1, rows + 1):
                f = j / rows
                col.append(b.vert(off(surf(bvh, cw[0] + (cup[k][0] - cw[0]) * f, cw[1] + (cup[k][1] - cw[1]) * f))
                                  + lift))
            grid.append(col)
        for k in range(RING_N):
            k2 = (k + 1) % RING_N
            b.face((centre, grid[k][0], grid[k2][0]), mi_in)
            for j in range(rows - 1):
                b.face((grid[k][j], grid[k][j + 1], grid[k2][j + 1], grid[k2][j]), mi_in)
    else:
        meas["form"] = "tubes"
        lips = {}
        axes = {}  # M8: per lip and station (x, z) of its axis after the reshape
        # M16: a lip shape's mirrored stations and fitted lip line (alien_lips_geom.rest_stations; the pout's)
        mirror = lips_p.get("mirror", 0.0) > 0.0
        if mirror or lips_p.get("seam_fit"):
            st = LP.rest_stations(st, m["hc"], lips_p)
            xl, xr = st[0]["x"] - 0.5, st[-1]["x"] + 0.5
        ss = [2 * (r["x"] - xl) / max(1.0, xr - xl) - 1 for r in st]  # M8: -1 .. 1 corner to corner
        for lip in ("u", "l"):
            cs, ra, rb, ns = [], [], [], []
            edges = []
            for r in st:
                if lip == "u":
                    t, bt = r["top_u"], r["bot_u"] + (0.0 if r["open"] else SEAM_OVERLAP)
                else:
                    t, bt = r["top_l"] - (0.0 if r["open"] else SEAM_OVERLAP), r["bot_l"]
                x, zt = world(r["x"], t - 0.5)
                _, zb = world(r["x"], bt + 0.5)
                edges.append((x, zt, zb, t, bt))
            # M8: the lip's thickness along it from LIP (thin corners, full centre, the bow); the lip line stays
            tops, bots = LP.closed_edges(ss, [e[1] for e in edges], [e[2] for e in edges], lip, lips_p)
            # M12b: the depth from the lip without the bow (bow_flat), so the bow notches the outline only
            t0, b0 = LP.closed_edges(ss, [e[1] for e in edges], [e[2] for e in edges], lip, LP.flat_bow(lips_p))
            axes[lip] = [(e[0], (zt + zb) / 2) for e, zt, zb in zip(edges, tops, bots)]
            if lip == "u":  # M14: the upper lip's bottom (the opening's top edge), where the upper teeth hang
                upper_edge = sorted((e[0], zb) for e, zb in zip(edges, bots))
            if lip == "l":  # M13: the lower lip's top (the crease of a closed mouth), where the fangs rise
                lo = sorted((e[0], zt) for e, zt in zip(edges, tops))
                anchor = {"form": "tubes", "lower": lo, "centre": ((lo[0][0] + lo[-1][0]) / 2, 0.0),
                          "outer_hw": (lo[-1][0] - lo[0][0]) / 2}
            for r, s, (x, _zt, _zb, t, bt), zt, zb, zt0, zb0 in zip(st, ss, edges, tops, bots, t0, b0):
                mb = lips_p.get("min_b", MIN_B)  # M16c: a lip shape's own thinnest end (the pout's finer points)
                hb = max(mb, (zt - zb) / 2)
                a = DEPTH_A * max(mb, (zt0 - zb0) / 2) + DEPTH_C * LP.depth_scale(s, lips_p)
                p, n = surf(bvh, x, (zt + zb) / 2)
                env = math.sin(math.pi * (r["x"] - xl) / max(1.0, xr - xl)) ** 0.5
                c3 = p + n * (a * (1 - SINK) + (push + (back if lip == "l" else 0.0)) * env)
                cs.append(c3)
                ra.append(a)
                rb.append(hb)
                ns.append(n)
                sections.append(((r["x"], (t + bt) / 2), c3, a, n, p))
            if mirror:  # M16: the skin under the lips is up to 0.4 mm lopsided: each station and its mirror averaged,
                # so the tube (and every later pass: smoothing, corners) is mirrored across x = 0 exactly (`sections`,
                # the teeth's and tongue's anchors, are taken before this; the pout uses neither)
                cs, ra, rb, ns = mirrored(cs, ra, rb, ns)
            lips[lip] = (cs, ra, rb, ns)
        # S7: smooth paths (the head's facets made the normals, and so the lips, ripple), and soft corners: over the
        # last CORNER share at each end both lips' centres meet and sink into the skin, so neither floats or cuts off
        nst = len(st)
        sm = {}
        for lip, (cs, ra, rb, ns) in lips.items():
            cs = [Vector(v) for v in zip(*(smooth([c[i] for c in cs], NORMAL_SMOOTH) for i in range(3)))]
            ns = [Vector(v).normalized() for v in zip(*(smooth([c[i] for c in ns], NORMAL_SMOOTH) for i in range(3)))]
            sm[lip] = [cs, list(ra), list(rb), ns]
        cn = {k: lips_p.get(f"corner_{k}", v) for k, v in CORNER.items()}  # M13b: a lip shape's own corners
        for i in range(nst):
            e = min(i, nst - 1 - i) / max(1.0, (nst - 1) * cn["share"])
            w = 1.0 - G.smoothstep(0.0, 1.0, e)
            if w <= 0.0:
                continue
            # M16c: corner_over > 0: the upper lip's end overhangs the lower's (mp1's points): the ends meet lower,
            # toward the lower lip's centre by half of it, the lower end sinks (1 + over) deeper, the upper (1 - over / 2)
            over = lips_p.get("corner_over", 0.0)
            mid = ((sm["u"][0][i] + sm["l"][0][i]) / 2).lerp(sm["l"][0][i], over / 2)
            for lip in ("u", "l"):
                cs, ra, rb, ns = sm[lip]
                c = cs[i].lerp(mid, cn["join"] * w)
                cs[i] = c - ns[i] * (cn["tuck"] * (1.0 + over if lip == "l" else 1.0 - over / 2) * ra[i] * w * w)
        for lip in ("u", "l"):
            if lips_p.get("w", 0.0) > 0.0:
                lip_tube(b, *sm[lip], mi_lip, 14, lips_p, lip)
            else:
                G.tube(b, *sm[lip], mi_lip, seg=14)
        anchor["upper"] = upper_edge
        zl_ = sorted(anchor["lower"], key=lambda q: abs(q[0] - anchor["centre"][0]))[0][1]
        zu_ = sorted(upper_edge, key=lambda q: abs(q[0] - anchor["centre"][0]))[0][1]
        anchor["open_h"] = max(0.0, zu_ - zl_)
        rolls = list(zip(*sm["l"]))
        dark = (m["teeth"] and design not in FILL_TEETH) or (design in FILL_TONGUE and n_open >= 5)
        if dark:  # the dark between the teeth and behind them, lip axis to axis (M14: any open tongue piece)
            rows = 5
            grid = []
            # M14: the tongue design's dark stops short of the corners (the lips sink into the skin there and the
            # dark, on the skin, showed as a dark dot past each corner)
            i0 = int((len(st) - 1) * cn["share"] * 0.7) if design in FILL_TONGUE else 0
            for i, r in list(enumerate(st))[i0:len(st) - i0]:
                col = []
                for j in range(rows):
                    if lips_p.get("w", 0.0) > 0.0:  # M8: between the reshaped lips' axes
                        (x, zu), (_x, zl) = axes["u"][i], axes["l"][i]
                        p, n = surf(bvh, x, zu + (zl - zu) * j / (rows - 1))
                    else:
                        y = (r["top_u"] + r["bot_u"]) / 2 + ((r["top_l"] + r["bot_l"]) / 2 - (r["top_u"] + r["bot_u"]) / 2) * j / (rows - 1)
                        p, n = surf(bvh, *world(r["x"], y))
                    col.append(b.vert(p + n * 0.0012))
                grid.append(col)
            for i in range(len(grid) - 1):
                for j in range(rows - 1):
                    b.face((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]), mi_in)
        elif lips_p.get("parting_dark") and lips_p.get("w", 0.0) > 0.0:
            # M16c (#254 minor 1): a closed piece's parting (small's open stations, the gap rest_stations keeps) shows
            # a dark strip behind it, lip axis to axis on the skin as the teeth's dark; only over the open run away
            # from the corners (parting_dark: the share of each end left out), so no dark shows past a corner
            i0 = max(1, int(round((len(st) - 1) * lips_p["parting_dark"])))
            ns_ = len(st)
            run = [i for i in range(i0, ns_ - i0) if st[i]["open"] or (mirror and st[ns_ - 1 - i]["open"])]
            if len(run) >= 2:
                run = list(range(run[0] - 1, run[-1] + 2))  # one closed station either end: the gap's ends tuck in
                rows = 3
                pos = []
                for i in run:
                    (x, zu), (_x, zl) = axes["u"][i], axes["l"][i]
                    col = []
                    for j in range(rows):
                        p, n = surf(bvh, x, zu + (zl - zu) * j / (rows - 1))
                        col.append(p + n * 0.0012)
                    pos.append(col)
                if mirror and run[0] + run[-1] == ns_ - 1:  # mirrored as the lips (the skin is 0.4 mm lopsided)
                    pos = [[(pos[i][j] + Vector((-pos[-1 - i][j].x, pos[-1 - i][j].y, pos[-1 - i][j].z))) / 2
                            for j in range(rows)] for i in range(len(pos))]
                grid = [[b.vert(q) for q in col] for col in pos]
                for i in range(len(grid) - 1):
                    for j in range(rows - 1):
                        b.face((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]), mi_in)
            meas["parting_dark"] = [len(run), round(axes["u"][run[0]][0] * 1000, 1), round(axes["u"][run[-1]][0] * 1000, 1)] if len(run) >= 2 else [0]
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
    tring = (rp or {}).get("tongue") if meas.get("form") == "ring" else None
    if design in FILL_TONGUE:  # M14: the designed tongue and teeth below
        pass
    elif tring and anchor.get("lower"):  # M13b: a designed tongue in the designed opening (the measured one was a
        # small blob in A and ragged in E: the refilled fang columns broke its run): tongue[0] of the opening's half
        # width, its top tongue[1] of the way from the lower edge up to the opening's centre, tucked under the edge
        build_tongue_ring(b, bvh, anchor, mats, tring, meas)
    elif len(tcols) >= 12 and meas.get("form") == "ring":
        mi_t = b.slot(mats["tongue"])
        tl, tr = tcols[0], tcols[-1]
        xm, half = (tl + tr) / 2, (tr - tl) / 2 * TONGUE_SHAPE["width"]  # S8b: narrower than the cup
        centre_cols = [x for x in tcols if abs(x - xm) <= half / 3]
        top = float(np.median([cols[x]["tongue_top"] for x in centre_cols]))
        base_m = float(np.median([(cols[x]["top_l"] + cols[x]["bot_l"]) / 2 for x in centre_cols]))
        n_t = 21
        bases = [(edge_at(cols, xm + (-1 + 2 * i / (n_t - 1)) * half, "top_l")
                  + edge_at(cols, xm + (-1 + 2 * i / (n_t - 1)) * half, "bot_l")) / 2 for i in range(n_t)]
        if design in FILL_TEETH:  # M13b: the refilled fang columns made the base, so the tongue's top edge, ragged
            bases = smooth(bases, 6)
        grid = []
        for i in range(n_t):
            u = -1 + 2 * i / (n_t - 1)
            xp = xm + u * half
            base = bases[i]
            yt = base - (base_m - top) * math.sqrt(max(0.0, 1 - u * u))
            col = []
            for j in range(6):
                f = j / 5
                p, n = surf(bvh, *world(xp, yt + (base - yt) * f))
                dome = TONGUE_SHAPE["dome"] * math.sqrt(max(0.0, 1 - u * u)) * math.sin(math.pi * (0.2 + 0.8 * f)) ** 0.5
                dome *= 1.0 - TONGUE_SHAPE["groove"] * math.exp(-(u / 0.2) ** 2)  # the midline groove
                col.append(b.vert(p + n * (TONGUE_SHAPE["lift"] + dome)))
            grid.append(col)
        for i in range(n_t - 1):
            for j in range(5):
                b.face((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]), mi_t)
        meas["tongue_mm"] = [round((world(tr, 0)[0] - world(tl, 0)[0]) * 1000, 1),
                             round((world(0, top)[1] - world(0, base_m)[1]) * 1000, 1)]
    if m["teeth"] and shape != "M" and design not in FILL_TEETH | FILL_TONGUE:
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
    if fang is not None:
        meas["fangs_mm"] = build_fangs(b, bvh, anchor, mats, fang, mi_lip, origin.translation.z)
    if teeth is not None and shape in teeth["shapes"] and anchor:
        meas["teeth_mm"] = build_teeth(b, anchor, sections, mats, TG.teeth_for(teeth, shape))
    if tongue is not None and anchor:
        meas["tongue_out"] = build_tongue_out(b, bvh, anchor, rolls, mats, tongue, shape)
    bmesh.ops.remove_doubles(b.bm, verts=b.bm.verts[:], dist=1e-7)
    ob = G.to_object(b, name or f"mouth_{design}_{shape}", coll, origin)
    return ob, meas, st


def build_tongue_ring(b, bvh, anchor, mats, tring, meas):
    """M13b: a designed ring's tongue (the fangs design): an arch on the skin from the opening's lower edge (tucked
    TONGUE_TUCK under it) up to tring[1] of the way to the opening's centre height, tring[0] of the opening's half
    width wide, domed and grooved as TONGUE_SHAPE."""
    lo = anchor["lower"]
    cx, cz = anchor["centre"]

    def z_at(x):
        if x <= lo[0][0]:
            return lo[0][1]
        for (x0, z0), (x1, z1) in zip(lo, lo[1:]):
            if x0 <= x <= x1:
                return z0 + (z1 - z0) * (x - x0) / max(1e-9, x1 - x0)
        return lo[-1][1]
    mi_t = b.slot(mats["tongue"])
    half = tring[0] * anchor["inner_hw"]
    zc = z_at(cx)
    h = tring[1] * (cz - zc)
    n_t = 21
    grid = []
    for i in range(n_t):
        u = -1 + 2 * i / (n_t - 1)
        x = cx + u * half
        zb = z_at(x) - TONGUE_TUCK
        zt = max(zb, zc + h * math.sqrt(max(0.0, 1 - u * u)) - TONGUE_TUCK * (1 - math.sqrt(max(0.0, 1 - u * u))))
        col = []
        for j in range(6):
            f = j / 5
            pt, n = surf(bvh, x, zt + (zb - zt) * f)
            dome = TONGUE_SHAPE["dome"] * math.sqrt(max(0.0, 1 - u * u)) * math.sin(math.pi * (0.2 + 0.8 * f)) ** 0.5
            dome *= 1.0 - TONGUE_SHAPE["groove"] * math.exp(-(u / 0.2) ** 2)
            col.append(b.vert(pt + n * (TONGUE_SHAPE["lift"] + dome)))
        grid.append(col)
    for i in range(n_t - 1):
        for j in range(5):
            b.face((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]), mi_t)
    meas["tongue_mm"] = [round(2 * half * 1000, 1), round((h + TONGUE_TUCK) * 1000, 1)]


def _z_at(pts, x):
    if x <= pts[0][0]:
        return pts[0][1]
    for (x0, z0), (x1, z1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return z0 + (z1 - z0) * (x - x0) / max(1e-9, x1 - x0)
    return pts[-1][1]


def build_tongue_out(b, bvh, anchor, rolls, mats, tp, shape):
    """M14: the tongue design's tongue (alien_tongue_geom) on a piece being built, lying on its lower lip: at the
    tongue's x (tp["shapes"][shape]["x"] of the lips' outer half width off their centre) the nearest lower-lip
    section gives the roll (its axis, depth and half height: an ellipse); the spine wraps over it, and every station
    below the lip stays its half thickness plus TONGUE_SKIN_GAP in front of the skin (the chin). Returns its x, width,
    length past the lip's top, the tip below the lip and the push off the chin (mm)."""
    tp = TG.shape_params(tp, shape)  # M14b: the shape's width (O's narrower than its hole)
    sp = dict(tp["shapes"][shape])
    cx = anchor["centre"][0]
    x0 = cx + sp["x"] * anchor["outer_hw"]
    c3, a, hb, _n = min(rolls, key=lambda r: abs(r[0].x - x0))
    ra = a + tp["thick"] / 2 + tp["clear"]
    rb = hb + tp["thick"] / 2 + tp["clear"]
    sp2d, s_top = TG.spine2d((ra, rb), tp, sp)
    pts = TG.world_spine(sp2d, s_top, x0, c3.y, c3.z, sp)
    ss = [q[2] for q in sp2d]
    push = 0.0
    out = []
    for (x, y, z), s in zip(pts, ss):  # in front of the chin: never closer than the gap to the skin
        if z < c3.z - hb and s > s_top:
            sy = surf(bvh, x, z)[0].y
            push = max(push, (y + tp["thick"] / 2 + TONGUE_SKIN_GAP) - sy)
        out.append((x, y - push, z))
    verts, faces, flop = TG.tongue_mesh(out, ss, s_top, tp, sp)
    verts, lifted = drape(b, verts, tp)
    mi_t = b.slot(mats["tongue_out"])
    bv = [b.vert(Vector(v), light=w) for v, w in zip(verts, flop)]
    for f in faces:
        b.face([bv[i] for i in f], mi_t)
    return {"x": round(x0 * 1000, 1), "width": round(tp["width"] * 1000, 1),
            "out": round((ss[-1] - s_top) * 1000, 1), "tip_below_lip": round((c3.z - hb - out[-1][2]) * 1000, 1),
            "chin_push": round(push * 1000, 2), "drape_mm": round(lifted * 1000, 2)}


def drape(b, verts, tp, reach=0.008, most=0.006):
    """M14: the tongue's sections lifted where its underside would cut into the piece's lips (the roll is an ellipse,
    the lip is not, and a wide tongue crosses a lip that rises toward the corners): per underside vertex a ray down
    from `reach` above it onto the lip faces; the lift (at most `most`) moves the vertex and its mirror on the top
    together (the thickness kept), smoothed round each section and along the tongue. M14b (PR #251's review: a white
    rim and a crumpled highlight at 3/4 where it crosses the lip): tp["drape"]'s `passes` of smoothing, and the
    section's sides (|cos| toward 1) aimed `sink` into the lip, so its edge meets the lip without a gap. Returns the
    vertices and the largest lift (m)."""
    dr = tp.get("drape", {"sink": 0.0, "passes": 6})
    mi_lip = next(i for i, m in enumerate(b.mats) if m.name.startswith("alien_lip"))
    lipf = [f for f in b.bm.faces if f.material_index == mi_lip]
    lv = list({v for f in lipf for v in f.verts})
    idx = {v: i for i, v in enumerate(lv)}
    tree = BVHTree.FromPolygons([v.co.copy() for v in lv], [[idx[v] for v in f.verts] for f in lipf])
    K = TG.AROUND
    n_ring = (len(verts) - 2) // K
    lift = [[0.0] * K for _ in range(n_ring)]
    for r in range(n_ring):
        for k in range(K):
            if math.sin(2 * math.pi * k / K) > -0.05:
                continue
            x, y, z = verts[r * K + k]
            hit = tree.ray_cast(Vector((x, y, z + reach)), Vector((0.0, 0.0, -1.0)), reach + 0.004)
            if hit[0] is not None:
                side = abs(math.cos(2 * math.pi * k / K)) ** 2
                d = min(most, max(0.0, hit[0].z + tp["clear"] - dr["sink"] * side - z))
                lift[r][k] = max(lift[r][k], d)
                lift[r][(K - k) % K] = max(lift[r][(K - k) % K], d)
    # smooth round each section and along the tongue (column by column it crumpled the root)
    for r in range(n_ring):  # M14b: the section's two side vertices (no underside partner) as their neighbours, so
        # the side does not stay down while the top and underside rise (that crease was the 3/4 view's white rim)
        lift[r][0] = max(lift[r][0], lift[r][K - 1], lift[r][1])
        lift[r][K // 2] = max(lift[r][K // 2], lift[r][K // 2 + 1], lift[r][K // 2 - 1])
    for _ in range(dr["passes"]):
        lift = [[(lift[r][k - 1] + 2 * lift[r][k] + lift[r][(k + 1) % K]) / 4 for k in range(K)] for r in range(n_ring)]
        lift = [[(lift[max(0, r - 1)][k] + 2 * lift[r][k] + lift[min(n_ring - 1, r + 1)][k]) / 4 for k in range(K)]
                for r in range(n_ring)]
    out = list(verts)
    for r in range(n_ring):
        for k in range(K):
            x, y, z = out[r * K + k]
            out[r * K + k] = (x, y, z + lift[r][k])
    return out, max(max(row) for row in lift)


def build_teeth(b, anchor, sections, mats, tt):
    """M14: the tongue design's gappy teeth (alien_tongue_geom.tooth_boxes, tooth_mesh) on a piece being built, from
    its opening's edges (anchor upper/lower) and the lips' axes (sections). Returns per tooth [x, w, visible h,
    centre z off the opening's middle] mm."""
    edges = {"upper": anchor["upper"], "lower": anchor["lower"]}
    cx = anchor["centre"][0]
    zmid = (_z_at(edges["upper"], cx) + _z_at(edges["lower"], cx)) / 2

    def edge_y(lip, x, z):
        cand = [s for s in sections if (s[1].z > zmid) == (lip == "upper")] or sections
        s = min(cand, key=lambda s: (s[1].x - x) ** 2 + (s[1].z - z) ** 2)
        return s[1].y - tt["front"] * s[2]
    boxes = TG.tooth_boxes(lambda lip, x: _z_at(edges[lip], cx + x), edge_y, anchor.get("open_h", 0.0), tt, cx)
    mi_te = b.slot(mats.get("tooth", mats["teeth"]))
    out = []
    for t in boxes:
        verts, faces = TG.tooth_mesh(t["centre"], t["w"], t["d"], t["h"], t["tilt"], tt["round"])
        bv = [b.vert(Vector(v)) for v in verts]
        for f in faces:
            b.face([bv[i] for i in f], mi_te)
        out.append([round(t["centre"][0] * 1000, 1), round(t["w"] * 1000, 1), t["visible_mm"],
                    round((t["centre"][2] - zmid) * 1000, 1)])  # M14b: its centre's height off the opening's middle
    return out


# M14 (PR #250's review): fang_roots lives in alien_fangs_geom (plain Python, unit-tested); the name stays here.
fang_roots = FG.fang_roots


def build_fangs(b, bvh, anchor, mats, p, mi_lip, z0=0.0):
    """M13: the fangs design's two lower fangs (alien_fangs_geom) on a piece being built: p["length"] long, rising
    from their roots (fang_roots; p["root"] of the length below them, behind the lower lip). The axis stands in front
    of the lips' front at each height (a ray cast on the piece's lip faces; between the lips the front is
    interpolated, past them the skin's): before the upper lip, never in it. Returns per fang [x, root z, length, base
    width, tip width] in mm (x off the centre line, z off the socket)."""
    if not anchor:
        return []
    mi_f = b.slot(mats["fang"])
    lipf = [f for f in b.bm.faces if f.material_index == mi_lip]
    vs = list({v for f in lipf for v in f.verts})
    idx = {v: i for i, v in enumerate(vs)}
    tree = BVHTree.FromPolygons([v.co.copy() for v in vs], [[idx[v] for v in f.verts] for f in lipf])
    out = []
    for x, z_root in FG.fang_roots(anchor, p):
        z_base = z_root - p["root"] * p["length"]
        z_tip = z_base + p["length"]
        side = 1.0 if x > 0 else -1.0
        n = FG.ROWS
        zs = [z_base + p["length"] * i / n for i in range(n + 1)]
        xs = [x - side * p["curve"] * p["length"] * (i / n) ** 2 for i in range(n + 1)]
        fronts, skin = [], []
        for xi, zi in zip(xs, zs):
            hit = tree.ray_cast(Vector((xi, -1.0, zi)), Vector((0.0, 1.0, 0.0)))
            fronts.append(hit[0].y if hit[0] is not None else None)
            skin.append(surf(bvh, xi, zi)[0].y)
        radii = [FG.radius_at(i / n, p) for i in range(n + 1)]
        ys = FG.axis_depths(zs, fronts, skin, radii, p, z_root, straight=anchor["form"] == "O")
        verts, faces = FG.mesh(FG.spine(x, z_base, z_tip, ys, p, side), p)
        bv = [b.vert(Vector(v)) for v in verts]
        for f in faces:
            b.face([bv[i] for i in f], mi_f)
        out.append([round(x * 1000, 1), round((z_root - z0) * 1000, 1), round(p["length"] * 1000, 1),
                    round(2 * p["radius"] * 1000, 1), round(2 * p["radius"] * p["tip"] * 1000, 1)])
    return out


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


def shape_scale(design, shape):
    """An open shape's size against its panel: SHAPE_SCALE, or the design's own (M12)."""
    return SHAPE_SCALE_DESIGN.get(design, SHAPE_SCALE).get(shape, 1.0)


def shape_frames(sheet, face_w_m, z_sock, chin_z, design=""):
    """One design's sheet measured: the six panels (measure_panel) and per shape its sheet-to-head mapping. Returns
    (the panels' measures, the design's report, {shape: {"hc", "ny", "kp", "squeeze", "sx", "world"}}), world(x_px,
    y_px) -> (x, z) in m round the Mouth socket (main's step 3)."""
    ms = []
    for k, shape in enumerate(SHAPES):
        px, py = (k % 3) * PANEL, (k // 3) * PANEL
        ms.append(measure_panel(sheet[py:py + PANEL, px:px + PANEL], design, shape))
    r0 = ms[0]
    xs = sorted(r0["cols"])
    seam_rows = [(r0["cols"][x]["bot_u"] + r0["cols"][x]["top_l"]) / 2 for x in xs if abs(x - r0["hc"]) < 30]
    seam_y = sum(seam_rows) / len(seam_rows)
    off = seam_y - r0["ny"]
    fl, fr = width_at(r0["C"]["bg"], seam_y)
    K = face_w_m / (fr - fl)
    drep = {"K_mm_per_px": round(K * 1000, 4), "rest_seam_below_nostrils_px": round(off, 1),
            "face_w_px_at_rest_seam": fr - fl, "shapes": {}}
    frames = {}
    for k, shape in enumerate(SHAPES):
        m = ms[k]
        kp = K * max(0.94, min(1.06, r0["face_w_nose"] / m["face_w_nose"])) * shape_scale(design, shape)
        hc, ny = m["hc"], m["ny"]
        seam = ny + off
        low = max(r["bot_l"] for r in m["cols"].values()) + 0.5
        z_low = z_sock - (low - seam) * kp
        squeeze = 1.0 if z_low >= chin_z else (z_sock - chin_z) / (z_sock - z_low)
        half = max(abs(x - hc) for x in m["cols"]) + 0.5
        sx = min(1.0, FACE_FILL * face_w_m / 2 / (half * kp))

        def world(x, y, hc=hc, kp=kp, seam=seam, squeeze=squeeze, sx=sx):
            dz = (y - seam) * kp
            return (x - hc) * kp * sx, z_sock - (dz * squeeze if dz > 0 else dz)
        frames[shape] = {"hc": hc, "ny": ny, "kp": kp, "squeeze": squeeze, "sx": sx, "world": world}
    return ms, drep, frames


def face_width(bvh, z_sock):
    """The head's front silhouette width at the socket's height (m)."""
    hw = []
    for sx in (1, -1):
        best = 0.0
        for j in range(60):
            h = bvh.ray_cast(Vector((sx * 0.5, -0.12 + 0.004 * j, z_sock)), Vector((-sx, 0, 0)))
            if h[0] is not None:
                best = max(best, abs(h[0].x))
        hw.append(best)
    return hw[0] + hw[1]


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
    face_w_m = face_width(bvh, z_sock)
    chin_z = CHIN_Z
    if a.parts_report:
        chin_z = json.loads(Path(a.parts_report).read_text(encoding="utf-8"))["chin_z_sculpted"] + CHIN_GAP
    rep = {"socket": [round(x, 5) for x in sock.translation], "face_w_at_socket_m": round(face_w_m, 4), "designs": {},
           "chin_z": round(chin_z, 4), "shape_scale": SHAPE_SCALE}
    nodes = {}
    profiles = {}
    meas_imgs = []
    lips = LP.LIP_SHAPE_M6C if a.lips == "m6c" else LP.merged(json.loads(a.lips) if a.lips else None)
    rep["lips"] = lips
    for design in ("frog", "overbite"):
        sheet = load_rgb(getattr(a, design))
        ms, drep, frames = shape_frames(sheet, face_w_m, z_sock, chin_z, design)
        atlas = np.zeros((WIN[1] * 2, WIN[0] * 3, 4), np.float32)
        flip_rects, flip_wins, worlds = {}, {}, {}
        for k, shape in enumerate(SHAPES):
            m = ms[k]
            f = frames[shape]
            hc, ny, kp, squeeze, sx, world = f["hc"], f["ny"], f["kp"], f["squeeze"], f["sx"], f["world"]
            ob, meas, st = build_piece(bvh, m, design, shape, world, mats, coll, sock, lips=lips)
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


if __name__ == "__main__":
    main()
