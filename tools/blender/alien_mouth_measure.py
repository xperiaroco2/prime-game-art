"""A closed mouth's proportions in a box of an 8-bit RGB(A) PNG (M16d, art #196): a sheet panel or a Godot cell
(plain Python, not run in Blender), so a 3D mouth can be fitted to a drawn one by numbers (docs/godot.md, M16d, M16e).

    python tools/blender/alien_mouth_measure.py <png> <x0> <y0> <x1> <y1> [front|face|profile]

- front: the lip mask (red: r > g + 45 and r > b + 35), the mouth's width W (px; the longest run of lip columns), at
  the centre (|x - xc| < 0.08 W) the upper and lower lip's heights (top to the lip line, the lip line to the bottom;
  the lip line the darkest row of the lips' middle half), each / W; corner_len: from each tip to where the lips'
  total height first reaches half the centre's, / (W / 2); tip_h: the total height 1/8 W in from each tip / the
  centre's; the nostrils' spacing (dark pixels above the lips) and W / it.
- face: as front, plus the face's width (the run of non-background through the mouth's centre at the lip line) and
  W / it.
- profile: the lips' forward stand-off (px) beyond the line from the skin's front 4 px above the lips to 4 px below;
  divide by W of a front cell of the same camera.

mp1's rest (D:/prime-art-raw/2026-10-20-alien-face-sheets-2/mp1/, the 1536 x 1024 sheet's top-left panel): the box
180 200 360 320 in `face` mode gives W 92 px, upper / W 0.30, lower / W 0.30, corner 0.27, tip 0.47, W 3.8 nostril
spacings, W / face 0.58.
"""
import json
import struct
import sys
import zlib


def read_png(path):
    """An 8-bit RGB or RGBA PNG (not interlaced) as rows of bytes and the bytes per pixel."""
    with open(path, "rb") as f:
        data = f.read()
    pos, idat, w, h, bpp = 8, b"", 0, 0, 3
    while pos < len(data):
        n, typ = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        if typ == b"IHDR":
            w, h, depth, ctype = struct.unpack(">IIBB", body[:10])
            if depth != 8 or ctype not in (2, 6):
                raise ValueError(f"{path}: only 8-bit RGB or RGBA")
            bpp = 3 if ctype == 2 else 4
        elif typ == b"IDAT":
            idat += body
        pos += 12 + n
    raw = zlib.decompress(idat)
    stride = w * bpp
    rows, prev = [], bytearray(stride)
    for y in range(h):
        f = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b, c = prev[i], (prev[i - bpp] if i >= bpp else 0)
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + ((a + b) >> 1)) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line)
        prev = line
    return rows, bpp
def px(rows, bpp, x, y):
    o = x * bpp
    return rows[y][o], rows[y][o + 1], rows[y][o + 2]


def is_lip(c):
    r, g, b = c
    return r > g + 45 and r > b + 35


def is_bg(c):
    return max(c) - min(c) < 16


def lum(c):
    return 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]


def front(rows, bpp, box, face=False):
    x0, y0, x1, y1 = box
    cols = {}
    for x in range(x0, x1):
        ys = [y for y in range(y0, y1) if is_lip(px(rows, bpp, x, y))]
        if len(ys) >= 3:
            cols[x] = (min(ys), max(ys))
    xs = sorted(cols)
    # the longest run of neighbouring lip columns (gaps up to 2 px)
    runs, g = [], [xs[0]]
    for x in xs[1:]:
        if x - g[-1] <= 2:
            g.append(x)
        else:
            runs.append(g)
            g = [x]
    runs.append(g)
    xs = max(runs, key=len)
    xl, xr = xs[0], xs[-1]
    W = xr - xl + 1
    xc = (xl + xr) / 2
    up, lo, seams = [], [], []
    for x in xs:
        if abs(x - xc) < 0.08 * W:
            t, b = cols[x]
            m0, m1 = t + (b - t) // 4, b - (b - t) // 4
            seam = min(range(m0, m1 + 1), key=lambda y: lum(px(rows, bpp, x, y)))
            up.append(seam - t)
            lo.append(b - seam)
            seams.append(seam)
    med = lambda v: sorted(v)[len(v) // 2]
    hu, hl = med(up), med(lo)
    hc = hu + hl
    def corner(side):
        seq = xs if side < 0 else xs[::-1]
        for i, x in enumerate(seq):
            t, b = cols[x]
            if b - t >= hc / 2:
                return i / (W / 2)
        return 1.0
    def tip(side):
        x = int(round(xl + 0.125 * W)) if side < 0 else int(round(xr - 0.125 * W))
        x = min(cols, key=lambda c: abs(c - x))
        t, b = cols[x]
        return (b - t) / hc
    out = {"W": W, "xc": xc, "seam": med(seams), "upper": hu, "lower": hl, "top": min(cols[x][0] for x in xs),
           "bot": max(cols[x][1] for x in xs),
           "upper/W": round(hu / W, 3), "lower/W": round(hl / W, 3), "height/W": round(hc / W, 3),
           "lower/upper": round(hl / max(1, hu), 2),
           "corner_len": round((corner(-1) + corner(1)) / 2, 3), "tip_h": round((tip(-1) + tip(1)) / 2, 3)}
    # the nostrils: the dark pixels above the lips within 0.4 W of the centre, split left and right of it
    top = out["top"]
    dk = [(x, y) for y in range(y0, top - 2) for x in range(int(xc - 0.4 * W), int(xc + 0.4 * W))
          if lum(px(rows, bpp, x, y)) < 75 and not is_lip(px(rows, bpp, x, y))]
    lx = [x for x, _ in dk if x < xc]
    rx = [x for x, _ in dk if x > xc]
    if lx and rx:
        out["nostrils"] = round(sum(rx) / len(rx) - sum(lx) / len(lx), 1)
        out["W/nostrils"] = round(W / out["nostrils"], 2)
    if face:
        y = med(seams)
        fx = [x for x in range(len(rows[y]) // bpp) if not is_bg(px(rows, bpp, x, y))]
        # the face's span round the mouth's centre: the run of non-background containing xc
        lft, rgt = int(xc), int(xc)
        while lft - 1 >= 0 and not is_bg(px(rows, bpp, lft - 1, y)):
            lft -= 1
        while rgt + 1 < len(rows[y]) // bpp and not is_bg(px(rows, bpp, rgt + 1, y)):
            rgt += 1
        out["face_w"] = rgt - lft + 1
        out["W/face"] = round(W / (rgt - lft + 1), 3)
    return out


def profile(rows, bpp, box):
    """The face looks toward smaller x (screen left) or larger: found from the lips against the skin."""
    x0, y0, x1, y1 = box
    lip = [(x, y) for y in range(y0, y1) for x in range(x0, x1) if is_lip(px(rows, bpp, x, y))]
    top, bot = min(y for _, y in lip), max(y for _, y in lip)
    lx = [x for x, _ in lip]
    # the facing side: where the lips stand nearer the background
    def skin_front(y, left):
        rng = range(x0, x1) if left else range(x1 - 1, x0 - 1, -1)
        for x in rng:
            if not is_bg(px(rows, bpp, x, y)):
                return x
        return None
    left = (sum(lx) / len(lx)) < (x0 + x1) / 2
    ya, yb = top - 4, bot + 4
    sa, sb = skin_front(ya, left), skin_front(yb, left)
    front_x = min(lx) if left else max(lx)
    best = 0.0
    for x, y in lip:
        f = (y - ya) / (yb - ya)
        line = sa + (sb - sa) * f
        d = (line - x) if left else (x - line)
        best = max(best, d)
    return {"stand_off": round(best, 1), "lip_h_profile": bot - top, "front_x": front_x, "skin": [sa, sb]}


if __name__ == "__main__":
    png = sys.argv[1]
    box = tuple(int(v) for v in sys.argv[2:6])
    mode = sys.argv[6] if len(sys.argv) > 6 else "front"
    rows, bpp = read_png(png)
    r = profile(rows, bpp, box) if mode == "profile" else front(rows, bpp, box, face=mode == "face")
    print(json.dumps(r))
