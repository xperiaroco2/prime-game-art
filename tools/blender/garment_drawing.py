"""A garment spec's drawing (art #196, Gate 1): plain Python, no Blender. From the spec (specs/<garment>_dims.toml,
garment_spec.py) and garment_spec_probe.py's rest dumps it writes, per view (front, side, back), one sheet of three
panels at one scale: the concept | the spec over the concept | the spec over her body (a flat-shaded orthographic
render of the probe, 5 px per cm), with the callouts in cm. Over the concept the spec is placed by the landmarks:
each height by its ratio between the concept's own landmark rows, across by the concept's scale from the hips.
A wrong size shows as a line off the picture. With --build it measures a build (every size on a dressed character's
probe's meshes) against the spec: spec_vs_<tag>.md and .json, and a table sheet.

    $PYTHON_BIN tools/blender/garment_drawing.py --spec specs/dungarees_dims.toml --body <char probe.json>
        --out DIR [--build <probe.json> --tag d79]
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import body_dims_geom as G
import body_drawing as D
import garment_spec as S

PX = 5                      # px per cm on her body
TOP_CM, PANEL_H = 190.0, 990
HALF_W_CM = 45.0            # her panels' half width (the T-pose arms are cut)
SPEC, OPT = (200, 30, 30), (40, 90, 200)
VIEWS = ("front", "side", "back")


# --- the render ---------------------------------------------------------------------------------------------------

def project(v, view: str):
    """(u, z, depth) in cm for a point in metres; smaller depth is nearer the camera."""
    x, y, z = v[0] * 100, v[1] * 100, v[2] * 100
    if view == "front":
        return x, z, y
    if view == "back":
        return -x, z, -y
    return y, z, -x                      # side: from her left (+x), her front (-y) on the left


def render(probe: dict, view: str, u0: float, w: int, h: int, colours: dict) -> list[list[tuple]]:
    """Flat-shaded z-buffer render of the probe's meshes; u0 the panel's left edge in cm."""
    img = [[D.PAPER] * w for _ in range(h)]
    depth = [[1e9] * w for _ in range(h)]
    light = (-0.35, 0.55, 0.76)
    for m in probe["meshes"]:
        base = colours.get(m["name"], (150, 150, 150))
        pv = [project(v, view) for v in m["vertices"]]
        for t in m["tris"]:
            a, b, c = pv[t[0]], pv[t[1]], pv[t[2]]
            nx = (b[1] - a[1]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[1] - a[1])
            ny = (b[2] - a[2]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[2] - a[2])
            nz = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            nx, ny, nz = nx / ln, ny / ln, nz / ln
            if nz > 0:                    # facing away: flip (the probe's winding is mixed after mirroring)
                nx, ny, nz = -nx, -ny, -nz
            shade = 0.35 + 0.65 * max(0.0, nx * light[0] + ny * light[1] - nz * light[2])
            col = tuple(min(255, int(ch * shade)) for ch in base)
            P = [((p[0] - u0) * PX, (TOP_CM - p[1]) * PX, p[2]) for p in (a, b, c)]
            x0, x1 = max(0, int(min(p[0] for p in P))), min(w - 1, int(max(p[0] for p in P)) + 1)
            y0, y1 = max(0, int(min(p[1] for p in P))), min(h - 1, int(max(p[1] for p in P)) + 1)
            if x0 > x1 or y0 > y1:
                continue
            (ax, ay, az), (bx, by, bz), (cx, cy, cz) = P
            den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(den) < 1e-9:
                continue
            for yy in range(y0, y1 + 1):
                py = yy + 0.5
                for xx in range(x0, x1 + 1):
                    px = xx + 0.5
                    l1 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / den
                    l2 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / den
                    l3 = 1 - l1 - l2
                    if l1 < -1e-6 or l2 < -1e-6 or l3 < -1e-6:
                        continue
                    d = l1 * az + l2 * bz + l3 * cz
                    if d < depth[yy][xx]:
                        depth[yy][xx] = d
                        img[yy][xx] = col
    return img


# --- the spec's lines in her body's cm (u across the view, z up) ------------------------------------------------------

def profile(sec: S.Sections, z: float, half: float = 11.0):
    """Her front and back (y, cm) at height z (cm), over |x| < half cm."""
    pts = [q for q in sec.at(z / 100) if abs(q[0]) * 100 < half]
    return (min(q[1] for q in pts) * 100, max(q[1] for q in pts) * 100) if pts else None


def leg_centre(sec: S.Sections, z: float) -> float:
    r = S.leg_x(sec, z / 100)
    return (r[0] + r[1]) / 2 * 100 if r else 11.2


def lines(spec: dict, sec: S.Sections, view: str, shirt: float = 0.5, legc=None) -> list[tuple]:
    """(colour, dashed, polyline [(u, z)...]) in cm for one view, and the callouts [(z, text)]."""
    d = {k: v["cm"] for k, v in spec["dims"].items()}
    out, notes = [], []

    def poly(pts, c=SPEC, dashed=False):
        out.append((c, dashed, pts))
    legc = legc or (lambda z: leg_centre(sec, z))
    bt, bb = d["bib_top_z"], d["waistband_top_z"]
    wb = bb - d["waistband_h"]
    hem, tu = d["hem_z"], d["hem_z"] + d["turnup_h"]
    kz, thz = spec["body"]["landmarks_cm"]["knee"], spec["body"]["landmarks_cm"]["crotch"] - 3
    if view in ("front", "back"):
        sg = 1 if view == "front" else -1
        tw, bw = (d["bib_top_w"], d["bib_bottom_w"]) if view == "front" else (d["back_top_w"], d["back_bottom_w"])
        top = bt if view == "front" else d["back_top_z"]
        if view == "front":
            poly([(-tw / 2, top), (tw / 2, top), (bw / 2, bb), (-bw / 2, bb), (-tw / 2, top)])
            pw, pt, pb = d["pocket_w"], d["pocket_top_z"], d["pocket_bottom_z"]
            poly([(-pw / 2, pt), (pw / 2, pt), (pw / 2, pb + 1), (0, pb), (-pw / 2, pb + 1), (-pw / 2, pt)])
            for s in (-1, 1):
                cx, r = s * d["strap_x"], d["buckle_d"] / 2
                poly([(cx + r * math.cos(a / 8 * math.pi), d["buckle_z"] + r * math.sin(a / 8 * math.pi))
                      for a in range(17)])
            notes += [(top, f"BIB TOP {top:.1f} W {tw:.1f}"), (d["pocket_top_z"], f"POCKET {pt:.1f}-{pb:.1f} W {pw:.1f}"),
                      (d["buckle_z"], f"BUCKLE {d['buckle_z']:.1f}")]
        else:
            xs = d["strap_x"] - d["strap_w"] / 2
            poly([(-tw / 2, top + 3), (-bw / 2, bb), (bw / 2, bb), (tw / 2, top + 3), (xs, top + 3), (0, top),
                  (-xs, top + 3), (-tw / 2, top + 3)])
            notes += [(top, f"BACK TOP {top:.1f} W {tw:.1f}")]
        for s in (-1, 1):
            cx, hw = s * d["strap_x"], d["strap_w"] / 2
            st = top + (3 if view == "back" else 0)
            sh = spec["body"]["landmarks_cm"]["shoulder_top"] + 1.0
            poly([(cx - hw, st), (cx - hw, sh), (cx + hw, sh), (cx + hw, st)])
        ww = d["waistband_w"]
        poly([(-ww / 2, bb), (ww / 2, bb), (ww / 2 + 0.6, wb), (-ww / 2 - 0.6, wb), (-ww / 2, bb)])
        for s in (-1, 1):
            cx, r = s * (ww / 2 - 1.4) * sg, d["side_button_d"] / 2
            if view == "front":
                poly([(cx + r * math.cos(a / 8 * math.pi), d["side_button_z"] + r * math.sin(a / 8 * math.pi))
                      for a in range(17)])
        notes += [(bb, f"BAND {bb:.1f}-{wb:.1f} W {ww:.1f}"), (d["side_button_z"], f"BUTTONS {d['side_button_z']:.1f}")
                  if view == "front" else (wb, "")]
        for s in (-1, 1):
            pts_l, pts_r = [], []
            for z, w in ((thz, d["leg_thigh_w"]), (kz, d["leg_knee_w"]), (tu, d["leg_hem_w"]), (hem, d["leg_hem_w"])):
                c = legc(z) * s * sg
                pts_l.append((c - w / 2, z))
                pts_r.append((c + w / 2, z))
            poly(pts_l)
            poly(pts_r)
            c = legc(hem) * s * sg
            poly([(c - d["leg_hem_w"] / 2, tu), (c + d["leg_hem_w"] / 2, tu)])
            poly([(c - d["leg_hem_w"] / 2, hem), (c + d["leg_hem_w"] / 2, hem)])
            poly([(c - 4, hem - d["ankle_strip_h"]), (c + 4, hem - d["ankle_strip_h"])], OPT, True)
        notes += [(thz, f"THIGH W {d['leg_thigh_w']:.1f}"), (kz, f"KNEE W {d['leg_knee_w']:.1f}"),
                  (tu, f"TURN-UP {tu:.1f}-{hem:.1f} W {d['leg_hem_w']:.1f}"),
                  (hem - d["ankle_strip_h"], f"ANKLE STRIP {d['ankle_strip_h']:.1f}")]
        return out, notes
    # side: the bib (B solid, A dashed), the back panel, the band, the straps over the shoulder, the leg's ends
    zs = [bb + i * (bt - bb) / 24 for i in range(25)]
    front = {z: profile(sec, z)[0] - shirt for z in zs}
    pk = min(zs, key=lambda z: front[z])
    b_pts = []
    for z in zs:                           # B: the chord band->top, bulging over the bust by the body's shape
        y = min(front[z] - d["bib_standoff_bust"], front[bt] - d["bib_standoff_top"] if z == bt else 1e9)
        b_pts.append((y, z))
    b_pts[-1] = (front[bt] - d["bib_standoff_top"], bt)
    yb, yp = front[bb] - 0.3, front[pk] - d["bib_standoff_bust"]
    s = (yp - yb) / (pk - bb)
    poly([(yb, bb), (yb + s * (bt - bb), bt)], OPT, True)                     # A
    poly(b_pts)                                                                 # B
    lean_a = math.degrees(math.atan2(-(s * (bt - bb)), bt - bb))
    gap_a = front[bt] - (yb + s * (bt - bb))
    zb = [bb + i * (d["back_top_z"] - bb) / 24 for i in range(25)]
    poly([(profile(sec, z)[1] + shirt + d["back_standoff"], z) for z in zb])
    sh = spec["body"]["landmarks_cm"]["shoulder_top"]
    yf, yk = front[bt] - d["bib_standoff_top"], profile(sec, d["back_top_z"])[1] + shirt + d["back_standoff"]
    poly([(yf, bt), (yf + 2, sh - 2), (0.5 * (yf + yk), sh + 1.0), (yk - 2, sh - 2), (yk, d["back_top_z"])])
    fb, bk = profile(sec, bb)
    poly([(fb - shirt - 0.3, bb), (fb - shirt - 0.3, wb)])
    poly([(bk + shirt + 0.3, bb), (bk + shirt + 0.3, wb)])
    for z in (tu, hem):
        poly([(-9, z), (9, z)])
    notes += [(bt, f"B: TOP GAP {d['bib_standoff_top']:.1f}"), (pk, f"BUST PEAK {pk:.1f} GAP {d['bib_standoff_bust']:.1f}"),
              (bt + 4, f"A DASHED: LEAN {lean_a:.1f} DEG, TOP GAP {gap_a:.1f}"),
              (bb, f"BAND {bb:.1f}"), (d["back_top_z"] - 3, f"BACK TOP {d['back_top_z']:.1f}"),
              (tu, f"TURN-UP {tu:.1f}-{hem:.1f}")]
    return out, notes


# --- placing on the concept -------------------------------------------------------------------------------------

def concept_map(spec: dict, view: str):
    """(u, z) cm -> the concept's (col, row) px: rows piecewise through the mapped landmark rows (S.concept_pairs),
    columns by px_per_cm."""
    c = spec["concept"]
    pairs = S.concept_pairs(spec)
    k = c["px_per_cm"]

    def row(z):
        for (z0, r0), (z1, r1) in zip(pairs, pairs[1:]):
            if z <= z1 or (z1, r1) == pairs[-1]:
                if z1 == z0:
                    return r0
                return r0 + (z - z0) * (r1 - r0) / (z1 - z0)
        return pairs[-1][1]

    def f(u, z):
        if view == "side":
            return c["side_mid_x"] + (u - c["side_mid_y_cm"]) * k, row(z)
        return (c["front_cx"] if view == "front" else c["back_cx"]) + u * k, row(z)
    return f


# --- the sheet --------------------------------------------------------------------------------------------------------

def draw_lines(cv, ls, tf, r=1):
    for colour, dashed, pts in ls:
        P = [tf(u, z) for u, z in pts]
        for i, (a, b) in enumerate(zip(P, P[1:])):
            if dashed:
                n = max(1, int(math.dist(a, b) / 6))
                for j in range(0, n, 2):
                    t0, t1 = j / n, min(1.0, (j + 1) / n)
                    cv.line((a[0] + t0 * (b[0] - a[0]), a[1] + t0 * (b[1] - a[1])),
                            (a[0] + t1 * (b[0] - a[0]), a[1] + t1 * (b[1] - a[1])), colour, r)
            else:
                cv.line(a, b, colour, r)


def view_sheet(spec: dict, probe: dict, sec: S.Sections, concept_rows, view: str, out: Path, what: str = "") -> Path:
    """concept | the spec over the concept | the spec over the probe's render; what names the probe (default her
    body)."""
    c = spec["concept"]
    box = c["boxes"][view]
    lm = spec["body"]["landmarks_cm"]
    f = (lm["shoulder_top"] - lm["sole"]) * PX / (c["rows"]["sole"] - c["rows"]["shoulder_top"])
    cw = int((box[2] - box[0]) * f)
    if view == "side":
        u0, bw = -45.0, 90 * PX // 1
        u0 = -35.0
        bw = 70 * PX
    else:
        u0, bw = -HALF_W_CM, int(2 * HALF_W_CM * PX)
    callw = 330
    W = 30 + cw + 30 + cw + callw + bw + callw
    cv = D.Canvas(W, PANEL_H + 90)
    oy = 60
    sole_y = oy + (TOP_CM - lm["sole"]) * PX
    oy_c = sole_y - (c["rows"]["sole"] - box[1]) * f          # the concept's sole on her sole line
    xs = [30, 30 + cw + 30, 30 + cw + 30 + cw + callw]
    cv.text(30, 12, f"{spec['garment']['id']} SPEC - {view} - concept | spec over the concept | spec over "
                     f"{what or 'her body ' + spec['body']['id']} (5 PX/CM)", k=2)
    cv.text(30, 34, "red: the spec (option B)   blue dashed: option A / the sneaker rim   cm on her body", k=2)
    for i in (0, 1):
        cv.blit(concept_rows, box, (xs[i], int(oy_c)), f, fade=0.0 if i == 0 else 0.25)
    ls, notes = lines(spec, sec, view)
    cm_to_c = concept_map(spec, view)
    if view != "side":
        zs = (lm["crotch"] - 3, lm["knee"], spec["dims"]["hem_z"]["cm"])
        offs = [o / c["px_per_cm"] for o in c["leg_cx_px"][view]]

        def legc(z):
            if z >= zs[0]:
                return offs[0]
            if z >= zs[1]:
                return offs[1] + (offs[0] - offs[1]) * (z - zs[1]) / (zs[0] - zs[1])
            return offs[2] + (offs[1] - offs[2]) * max(0.0, z - zs[2]) / (zs[1] - zs[2])
        ls_c, _ = lines(spec, sec, view, legc=legc)
    else:
        ls_c = ls

    def on_concept(u, z):
        col, row = cm_to_c(u, z)
        return xs[1] + (col - box[0]) * f, oy_c + (row - box[1]) * f
    draw_lines(cv, ls_c, on_concept, 1)
    colours = {"axolotl_char": (120, 190, 180), "Body": (120, 190, 180)}
    img = render(probe, view, u0, bw, PANEL_H, colours)
    for yy, row in enumerate(img):
        for xx, p in enumerate(row):
            if p is not D.PAPER:
                cv.dot(xs[2] + xx, oy + yy, p)

    def on_body(u, z):
        return xs[2] + (u - u0) * PX, oy + (TOP_CM - z) * PX
    draw_lines(cv, ls, on_body, 1)
    # landmark ticks on both pictures and the callouts on the right of each spec panel
    for name, z in lm.items():
        if name in S.HEIGHTS:
            for tf, x0 in ((on_concept, xs[1]), (on_body, xs[2])):
                _, y = tf(0, z)
                cv.line((x0 - 22, y), (x0 - 4, y), D.RING, 0)
                cv.text(x0 - 26 - 6 * len(name[:5]), int(y) - 4, name[:5], c=D.RING, k=1)
    used = []
    for z, text in sorted(notes, key=lambda n: -n[0]):
        if not text:
            continue
        for tf, x0, xr in ((on_concept, xs[1], xs[1] + cw), (on_body, xs[2], xs[2] + bw)):
            _, y = tf(0, z)
            ty = int(y) - 6
            while any(abs(ty - u) < 16 and x == xr for x, u in used):
                ty += 16
            used.append((xr, ty))
            cv.line((xr - 8, y), (xr + 6, ty + 6), D.DIM, 0)
            cv.text(xr + 8, ty, text, c=D.DIM, k=2 if len(text) < 26 else 1)
    return cv.save(out)


# --- measuring a build against the spec ---------------------------------------------------------------------------

def _top(pts, i: int = 2, lo: bool = False):
    """The largest (lo: smallest) coordinate i of pts, None for no points (never max() of an empty list)."""
    return None if not pts else (min if lo else max)(q[i] for q in pts)


def _span(pts, i: int = 0):
    return None if not pts else (max(q[i] for q in pts) - min(q[i] for q in pts))


def _piece_height(pieces: list[dict], q, max_h_cm: float = 15.0):
    """The height (cm) of the connected piece holding point q when it is a separate part no taller than max_h_cm;
    None when q is in no such piece (fused with the rest of the garment)."""
    for p in pieces:
        if q in p["pts_set"]:
            h = (p["hi"][2] - p["lo"][2]) * 100
            return h if h <= max_h_cm else None
    return None


def measure_build(spec: dict, probe: dict, body: S.Sections, shirt: float = 0.5, mesh: str = "garment",
                  shoes: str = "shoes") -> dict:
    """Each spec dimension measured on the dressed character's meshes (cm), or None with the reason; a part looked
    for and not there is absent (a failure). The heights it looks at come from her landmarks or the build's own
    measures; nothing is read back from the build's dress.json."""
    lm = spec["body"]["landmarks_cm"]
    g = S.Sections(probe, [mesh])
    res = {}

    def put(k, v, how, absent=False):
        res[k] = {"cm": None if v is None else round(v, 2), "how": how}
        if absent:
            res[k]["absent"] = True   # looked for on the mesh and not there: a failure, never "unmeasured"
    zw = lm["waist"] + 4.5
    front_pts = [p for p in g.pts if abs(p[0]) < 0.06 and p[1] < -0.09]
    # the band's side, forward of the side seam (y < 3 cm): a band hugging her waist at the spec's 24.5 cm is widest
    # behind the centre line, 12.2 cm off it, so "in front, over 12 cm" missed it (G3a)
    side = [p for p in g.pts if 0.11 < abs(p[0]) < 0.15 and p[1] < 0.03 and p[2] < zw / 100]
    if not front_pts or not side:
        why = f"absent: no '{mesh}' vertex " + ("in front within 6 cm of the centre" if not front_pts else
                                                f"11-15 cm off the centre, y < 3 cm, under her waist + 4.5 ({zw:.1f})")
        for k in spec["dims"]:
            put(k, None, why, absent=True)
        return res
    bt = _top(front_pts) * 100
    put("bib_top_z", bt, "highest garment vertex within 6 cm of the centre front")

    def width(z, back=False):
        pts = [q for q in g.at(z / 100) if (q[1] > 0.02 if back else q[1] < -0.07) and abs(q[0]) < 0.16]
        return _span(pts) * 100 if pts else None
    put("bib_top_w", width(bt - 1.5), "front garment section 1.5 cm under the bib top (straps included)")
    band = _top(side) * 100
    put("bib_bottom_w", width(band + 2.5), "front garment section 2.5 cm over the band's top")

    def centre(z, back=False):
        """The garment's outer y (m) at the centre (|x| < 5 cm) at height z cm: the front's least y, the back's most."""
        pts = [q for q in g.at(z / 100) if abs(q[0]) < 0.05 and (q[1] > 0 if back else q[1] < 0)]
        return _top(pts, 1, lo=not back)
    yb, yt = centre(band + 0.5), centre(bt - 0.5)
    put("bib_lean_deg", None if None in (yb, yt) else S.lean_deg(yt * 100, bt - 0.5, yb * 100, band + 0.5),
        "the garment's front at the centre: chord from the band's top + 0.5 cm to the bib top - 0.5 cm")

    def gap(z, back=False):
        a = centre(z, back)
        # her front over |x| < 11 cm, as the drawing's lean B (profile): the bust's peaks, not the cleavage (G3a)
        b = [q for q in body.at(z / 100) if abs(q[0]) < 0.11 and (q[1] > 0 if back else q[1] < 0)]
        if a is None or not b:
            return None
        return ((a - _top(b, 1)) if back else (_top(b, 1, lo=True) - a)) * 100 - shirt
    put("bib_standoff_top", gap(bt - 1.0), "her front + 0.5 cm shirt to the garment's front at the centre, 1 cm under the bib top")
    if bt > lm["bust"]:
        put("bib_standoff_bust", gap(lm["bust"]), "the same at her bust peak's height")
    else:
        put("bib_standoff_bust", None, f"absent: the bib's top ({bt:.1f}) is under her bust peak ({lm['bust']:.1f})",
            absent=True)
    hw = mesh_hardware(spec, probe, bt, band)
    pk = hw["pocket"]
    if pk:
        put("pocket_top_z", pk["top"] * 100, pk["how"] + ": its top")
        put("pocket_bottom_z", pk["bottom"] * 100, pk["how"] + ": its bottom at the centre (|x| < 1 cm)")
        put("pocket_w", pk["w"] * 100, pk["how"] + ": its width")
    else:
        for k in ("pocket_top_z", "pocket_bottom_z", "pocket_w"):
            put(k, None, "absent: no pocket on the mesh (no 'pocket' material, no piece on the bib)", absent=True)
    zc = lm["collarbone"]
    sw = [q for q in g.at(zc / 100) if q[1] < 0 and 0.05 < q[0] < 0.16]
    put("strap_w", _span(sw) * 100 if sw else None, f"her left strap's front, section at her collarbone ({zc:.1f})")
    put("strap_x", (max(q[0] for q in sw) + min(q[0] for q in sw)) / 2 * 100 if sw else None, "its centre")
    bb = hw["buckle_buttons"]
    how = f"{len(bb)} button pieces on the mesh, in front over the band's top + 5 cm"
    put("buckle_z", sum(b["z"] for b in bb) / len(bb) * 100 if bb else None, how + ": mean centre height",
        absent=not bb)
    put("buckle_d", sum(b["d"] for b in bb) / len(bb) * 100 if bb else None, how + ": mean disc diameter",
        absent=not bb)
    put("waistband_top_z", band, "highest garment vertex 11-15 cm off the centre, y < 3 cm, under her waist + 4.5 cm")
    gm = next((m for m in probe["meshes"] if m["name"] == mesh), None)
    pieces = S.mesh_pieces(gm) if gm else []
    for p in pieces:
        p["pts_set"] = set(p["pts"])
    bh = _piece_height(pieces, max(side, key=lambda q: q[2]))
    put("waistband_h", bh, "the height of the separate piece holding the band's top" if bh is not None else
        "absent: the band's top is on no separate piece 15 cm tall or less", absent=bh is None)
    t = S.trunk_x(g, (band - 1) / 100)
    put("waistband_w", (t[1] - t[0]) * 100 if t else None, "garment section 1 cm under the band's top")
    sb = hw["side_buttons"]
    how = f"{len(sb)} button pieces on the mesh, |x| over 6 cm, 10 cm under to 3 cm over the band's top"
    put("side_button_z", sum(b["z"] for b in sb) / len(sb) * 100 if sb else None, how + ": mean centre height",
        absent=not sb)
    put("side_button_d", sum(b["d"] for b in sb) / len(sb) * 100 if sb else None, how + ": mean disc diameter",
        absent=not sb)
    kt = _top([q for q in g.pts if abs(q[0]) < 0.01 and q[1] > 0.03 and band / 100 < q[2] < (zc + 3) / 100])
    kt = None if kt is None else kt * 100
    put("back_top_z", kt, "highest garment vertex within 1 cm of the centre back, over the band, under her "
        "collarbone + 3 cm", absent=kt is None)
    put("back_top_w", None if kt is None else width(kt + 1.5, back=True),
        "back garment section 1.5 cm over the back top's centre (towards its corners; straps included)")
    put("back_bottom_w", width(band + 2.5, back=True), "back garment section 2.5 cm over the band's top")
    gaps = [] if kt is None or kt - 1 <= band + 3 else [gap(band + 3 + i * (kt - 4 - band) / 4, back=True)
                                                       for i in range(5)]
    gaps = [v for v in gaps if v is not None]
    put("back_standoff", max(gaps) if gaps else None,
        "her back + 0.5 cm shirt to the garment's back at the centre: the most of 5 heights, band + 3 to back top - 1")

    def leg_w(z):
        r = S.leg_x(g, z / 100)
        return (r[1] - r[0]) * 100 if r else None
    put("leg_thigh_w", leg_w(lm["crotch"] - 3), "garment section, her left leg, 3 cm under the crotch")
    put("leg_knee_w", leg_w(lm["knee"]), "the same at the knee")
    leg = [q for q in g.pts if q[0] > 0.03 and q[2] < lm["knee"] / 100]
    low = min(leg, key=lambda q: q[2]) if leg else None
    hem = None if low is None else low[2] * 100
    put("hem_z", hem, "lowest garment vertex on her left leg (under her knee)", absent=hem is None)
    th = None if low is None else _piece_height(pieces, low)
    put("turnup_h", th, "the height of the separate piece holding the leg's lowest vertex" if th is not None else
        "absent: the leg's end is on no separate piece 15 cm tall or less", absent=th is None)
    hz = None if hem is None else hem + (th or 2.0) / 2
    hs = [] if hz is None else [q for q in g.at(hz / 100) if q[0] > 0.02]
    put("leg_hem_w", _span(hs) * 100 if hs else None,
        "her left leg's garment section at the turn-up's mid-height (2 cm over the hem without one): its outer width")
    sm = next((m for m in probe["meshes"] if m["name"] == shoes), None)
    rim = None if sm is None else _top([v for v in sm["vertices"] if v[0] > 0])
    put("ankle_strip_h", None if hem is None or rim is None else hem - rim * 100,
        f"the hem - her left '{shoes}' mesh's highest point (the bare ankle seen)" if rim is not None else f"absent: no '{shoes}' mesh",
        absent=rim is None)
    return res


BUTTON_MAX_CM = 3.0   # a hardware piece no larger than this (box) is a button; buckle rings are larger


def mesh_hardware(spec: dict, probe: dict, bib_top_cm: float, band_cm: float, mesh: str = "garment") -> dict:
    """The hardware and the pocket found on the build's mesh (metres): buttons are pieces of at most the spec's
    [gate2.classify] hardware_max_verts vertices (60 if none) and BUTTON_MAX_CM across, each with its centre height
    and disc diameter (S.disc_size); the buckle buttons in front over the band's top + 5 cm, the side buttons over
    6 cm off the centre within 10 cm under to 3 cm over the band's top. The pocket: the triangles of a material
    named '*pocket*', else a piece on the bib's front (centred within 4 cm, 5-25 cm wide, between the band's top and
    the bib's top, 1 cm slack) that is not the garment's largest piece; None when there is none."""
    hw_max = spec.get("gate2", {}).get("classify", {}).get("hardware_max_verts", 60)
    g = next((m for m in probe["meshes"] if m["name"] == mesh), None)
    res = {"buckle_buttons": [], "side_buttons": [], "pocket": None}
    if g is None:
        return res
    pieces = S.mesh_pieces(g)
    bt, band = bib_top_cm / 100, band_cm / 100
    for p in pieces:
        ext = max(h - lo for h, lo in zip(p["hi"], p["lo"]))
        if p["verts"] > hw_max or ext > BUTTON_MAX_CM / 100:
            continue
        d, _t, _n = S.disc_size(p["pts"])
        b = {"z": p["centre"][2], "x": p["centre"][0], "d": d}
        if p["centre"][1] < 0 and p["centre"][2] > band + 0.05:
            res["buckle_buttons"].append(b)
        elif abs(p["centre"][0]) > 0.06 and band - 0.10 <= p["centre"][2] <= band + 0.03:
            res["side_buttons"].append(b)
    pts, how = None, ""
    mi = [i for i, n in enumerate(g["materials"]) if "pocket" in n.lower()]
    if mi:
        ids = {v for t in g["tris"] if t[3] in mi for v in t[:3]}
        pts, how = [tuple(g["vertices"][i]) for i in ids], f"the '{g['materials'][mi[0]]}' triangles"
    else:
        for p in pieces[1:]:
            w = p["hi"][0] - p["lo"][0]
            if (p["centre"][1] < 0 and abs(p["centre"][0]) < 0.04 and 0.05 <= w <= 0.25
                    and p["lo"][2] >= band - 0.01 and p["hi"][2] <= bt + 0.01):
                pts, how = p["pts"], f"a {p['verts']}-vertex piece on the bib"
                break
    if pts:
        mid = [q for q in pts if abs(q[0]) < 0.01] or pts
        res["pocket"] = {"top": max(q[2] for q in pts), "bottom": min(q[2] for q in mid),
                         "w": max(q[0] for q in pts) - min(q[0] for q in pts), "how": how}
    return res


def table(spec: dict, meas: dict, tag: str) -> tuple[str, list]:
    rows = []
    for k, d in spec["dims"].items():
        m = meas.get(k, {"cm": None, "how": "not measured"})
        diff = None if m["cm"] is None else round(m["cm"] - d["cm"], 2)
        ok = False if m.get("absent") else S.within(d, m["cm"])
        rows.append((k, d["cm"], d["tol_cm"], m["cm"], diff, ok, m["how"]))
    md = [f"| dimension | spec cm | tol | {tag} cm | {tag} - spec | within | how |", "|---|---|---|---|---|---|---|"]
    for k, s, t, m, df, ok, how in rows:
        md.append(f"| {k} | {s} | {t} | {'-' if m is None else m} | {'-' if df is None else f'{df:+.2f}'} | "
                  f"{'-' if ok is None else ('yes' if ok else 'NO')} | {how} |")
    return "\n".join(md) + "\n", rows


def table_sheet(rows, tag: str, out: Path) -> Path:
    cv = D.Canvas(1500, 60 + 26 * (len(rows) + 2))
    cv.text(20, 16, f"SPEC VS {tag}: CM ON HER BODY B13 (ANGLE IN DEG FOR BIB_LEAN)", k=2)
    cols = [20, 360, 500, 580, 720, 880, 980]
    for x, h in zip(cols, ("DIMENSION", "SPEC", "TOL", tag, "DIFF", "WITHIN", "HOW")):
        cv.text(x, 44, h, k=2)
    for i, (k, s, t, m, df, ok, how) in enumerate(rows):
        y = 70 + 26 * i
        c = D.INK if ok is None else ((40, 130, 60) if ok else SPEC)
        for x, v in zip(cols, (k, s, t, "-" if m is None else m, "-" if df is None else f"{df:+.2f}",
                               "-" if ok is None else ("YES" if ok else "NO"), how[:42])):
            cv.text(x, y, str(v), c=c, k=2 if x < 980 else 1)
    return cv.save(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--body", required=True, help="garment_spec_probe.py's dump of the undressed character")
    ap.add_argument("--out", required=True)
    ap.add_argument("--build", help="the probe of a dressed build")
    ap.add_argument("--tag", default="build")
    ap.add_argument("--views", default=",".join(VIEWS))
    a = ap.parse_args()
    spec = S.load_spec(a.spec)
    bad = S.check_spec(spec)
    if bad:
        raise SystemExit("spec: " + "; ".join(bad))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    probe = S.load_probe(a.body)
    sec = S.Sections(probe, [spec["body"]["mesh"]])
    _, _, crow = G.read_png(spec["garment"]["concept"])
    for v in a.views.split(","):
        print("sheet:", view_sheet(spec, probe, sec, crow, v, out / f"sheet_{v}.png"))
    if a.build:
        meas = measure_build(spec, S.load_probe(a.build), sec)
        md, rows = table(spec, meas, a.tag)
        (out / f"spec_vs_{a.tag}.md").write_text(md, encoding="utf-8", newline="\n")
        (out / f"spec_vs_{a.tag}.json").write_text(json.dumps(meas, indent=1), encoding="utf-8", newline="\n")
        print("table:", table_sheet(rows, a.tag, out / f"spec_vs_{a.tag}.png"))
        print(md)


if __name__ == "__main__":
    main()
