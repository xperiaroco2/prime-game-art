"""Measures a body turnaround's silhouettes per height (art #196, the A body's refit route): plain Python, the PNG
decoded with zlib (no PIL).

    $PYTHON_BIN tools/blender/alien_body_measure.py <turnaround.png> [--panels 3] [--head-m 0.494] [--out bands.json]

The picture holds the views side by side on a flat background (front | side facing left | back). Per panel and pixel
row: the runs of figure pixels (a pixel is figure when its colour lies far from the background's, the median of the
four corners). Landmarks on the front view: the top, the sole, the neck's narrowest row under the head (the ring: the
welded heads are cut at their neck's waist), the shoulders, the armpits (the arms part from the trunk), the crotch
(the legs part), the knees and ankles (the narrowest leg rows). The scale comes from the head: --head-m is the r5
head's height above its ring (`char.json` fit top_z minus the ring's z), so one pixel is head_m / (ring - top) m and
the body below the ring keeps the concept's proportions against the head, unless the whole height would pass --cap-m:
then the body below the ring is scaled down to fit (px_m; the head keeps its size). Writes the bands (z m above the sole, the
trunk's width from the front, its depth from the side, the legs' widths) and the landmarks as JSON.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
import zlib


def read_png(path):
    """(width, height, rows of (r, g, b) tuples) of an 8-bit RGB or RGBA PNG, non-interlaced."""
    data = open(path, "rb").read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(f"{path}: not a PNG")
    pos, idat, w = 8, [], None
    while pos < len(data):
        n, typ = struct.unpack(">I4s", data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + n]
        if typ == b"IHDR":
            w, h, depth, ctype, _, _, inter = struct.unpack(">IIBBBBB", chunk)
            if depth != 8 or ctype not in (2, 6) or inter:
                raise SystemExit(f"{path}: needs 8-bit RGB/RGBA, non-interlaced")
            bpp = 3 if ctype == 2 else 4
        elif typ == b"IDAT":
            idat.append(chunk)
        pos += 12 + n
    raw = zlib.decompress(b"".join(idat))
    stride = w * bpp
    rows, prev, i = [], bytearray(stride), 0
    for _ in range(h):
        f = raw[i]
        line = bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append([tuple(line[x * bpp:x * bpp + 3]) for x in range(w)])
        prev = line
    return w, h, rows


def mask_rows(w, h, rows, thresh=38):
    corners = sorted([rows[2][2], rows[2][w - 3], rows[h - 3][2], rows[h - 3][w - 3]])
    bg = tuple(sorted(c[i] for c in corners)[1] for i in range(3))
    return [[sum(abs(p[i] - bg[i]) for i in range(3)) > thresh for p in r] for r in rows], bg


def runs(line, x0, x1, min_len=3):
    out, start = [], None
    for x in range(x0, x1):
        if line[x] and start is None:
            start = x
        elif not line[x] and start is not None:
            if x - start >= min_len:
                out.append((start, x - 1))
            start = None
    if start is not None and x1 - start >= min_len:
        out.append((start, x1 - 1))
    return out


def panel(mask, x0, x1):
    h = len(mask)
    # runs of 12 px or more away from the panel's edges (the picture's vignette and noise stay out)
    rr = [[r for r in runs(mask[y], x0, x1, 12) if r[0] > x0 + 40 and r[1] < x1 - 20] for y in range(h)]
    ys = [y for y in range(h) if rr[y]]
    top, sole = ys[0], ys[-1]
    # the body's centre column: the median of the run middles over the trunk's height
    mids = sorted((r[0] + r[1]) / 2 for y in range(top + (sole - top) // 3, top + (sole - top) // 2) for r in rr[y]
                  if r[0] <= (x0 + x1) / 2 + 80 and r[1] >= (x0 + x1) / 2 - 80)
    cx = mids[len(mids) // 2] if mids else (x0 + x1) / 2

    def centre_run(y):
        best = None
        for r in rr[y]:
            if r[0] - 2 <= cx <= r[1] + 2:
                return r
            d = min(abs(r[0] - cx), abs(r[1] - cx))
            if best is None or d < best[0]:
                best = (d, r)
        return best[1] if best and best[0] < 6 else None
    return rr, top, sole, cx, centre_run


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("png")
    ap.add_argument("--panels", type=int, default=3)
    ap.add_argument("--head-m", type=float, default=0.494)
    ap.add_argument("--cap-m", type=float, default=1.95, help="the whole height's cap: the body below the ring "
                    "is scaled down to fit it (the head keeps its size)")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    w, h, rows = read_png(a.png)
    mask, bg = mask_rows(w, h, rows)
    pw = w // a.panels
    rr, top, sole, cx, crun = panel(mask, 0, pw)
    H = sole - top
    # the ring: the narrowest centre run between 15% and 40% of the height under the top
    wid = {y: (crun(y)[1] - crun(y)[0] + 1) if crun(y) else 0 for y in range(top, sole + 1)}
    ring = min(range(top + int(0.15 * H), top + int(0.40 * H)), key=lambda y: (wid[y] or 9999, -y))
    nw = wid[ring]
    # shoulders: the first row under the ring whose centre run is 2.6 times the neck's
    shoulder = next(y for y in range(ring, sole) if wid[y] > 2.6 * nw)
    # armpits: the first row under the shoulders with three runs or more (arm, trunk, arm)
    armpit = next(y for y in range(shoulder + 5, sole) if len(rr[y]) >= 3 and crun(y))
    # crotch: the first row under the armpits where the centre column is background
    crotch = next(y for y in range(armpit, sole) if not mask[y][int(round(cx))])
    sp = panel(mask, pw, 2 * pw)
    s_rr, s_top, s_sole, s_cx, s_crun = sp
    head_scale = a.head_m / (ring - top)
    scale = min(head_scale, (a.cap_m - a.head_m) / (sole - ring))

    def z(y):
        return round((sole - y) * scale, 4)

    def leg_runs(y):
        return [r for r in rr[y] if r[1] < cx or r[0] > cx]
    legw = {}
    for y in range(crotch + 3, sole + 1):
        lr = [r for r in leg_runs(y) if r[0] > cx]  # the figure's left leg (picture right)
        if lr:
            legw[y] = lr[0][1] - lr[0][0] + 1
    lower = [y for y in legw if crotch + 0.15 * (sole - crotch) < y < crotch + 0.55 * (sole - crotch)]
    knee = min(lower, key=lambda y: legw[y]) if lower else None
    ank = [y for y in legw if crotch + 0.7 * (sole - crotch) < y < sole - 0.03 * H]
    ankle = min(ank, key=lambda y: legw[y]) if ank else None
    bands = []
    for y in range(ring, sole + 1, 4):
        fr = crun(y)
        sr = s_crun(y - top + s_top)
        bands.append({"z": z(y), "row": y,
                      "width": round((fr[1] - fr[0] + 1) * scale, 4) if fr and y <= crotch else None,
                      "extent": round((max(r[1] for r in rr[y]) - min(r[0] for r in rr[y]) + 1) * scale, 4)
                      if rr[y] else None,
                      "depth": round((sr[1] - sr[0] + 1) * scale, 4) if sr else None,
                      "leg": round(legw[y] * scale, 4) if y in legw else None})
    out = {"png": a.png, "background": bg, "panel_px": pw, "head_m": a.head_m, "px_m": round(scale, 6),
           "head_px_m": round(head_scale, 6), "uncapped_height_m": round(a.head_m + (sole - ring) * head_scale, 4),
           "height_m": round(a.head_m + (sole - ring) * scale, 4),
           "rows": {"top": top, "ring": ring, "shoulder": shoulder, "armpit": armpit, "crotch": crotch,
                    "knee": knee, "ankle": ankle, "sole": sole, "side_top": s_top, "side_sole": s_sole},
           "z": {"top": z(top), "ring": z(ring), "shoulder": z(shoulder), "armpit": z(armpit), "crotch": z(crotch),
                 "knee": z(knee) if knee else None, "ankle": z(ankle) if ankle else None},
           "neck_width_ring_m": round(nw * scale, 4), "centre_x_px": cx, "bands": bands}
    text = json.dumps(out, indent=1)
    if a.out:
        open(a.out, "w", encoding="utf-8", newline="\n").write(text + "\n")
    print(json.dumps({k: out[k] for k in ("px_m", "head_px_m", "uncapped_height_m", "height_m", "rows", "z",
                                          "neck_width_ring_m")}))
    for b in bands[::6]:
        print(b)
    return 0


if __name__ == "__main__":
    sys.exit(main())
