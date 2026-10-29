"""The bodies' drawing in mm (art #196, step D2): a concept turnaround measured per pixel row into station tables, the
crystal's route (concept, drawing, then the 3D built only from the drawing; docs/props.md). No bpy: the maths, tested
in tools/tests/test_body_dims_geom.py; body_dims_measure.py writes the tables, body_drawing.py the sheets.

The picture (2560 x 1024 from the D1 batch) holds four views on a flat grey ground: front, three-quarter, side
(facing left) and back. The frame of the tables is the body file's: x lateral (mirror-symmetric), z up from the sole,
the front at -y; lengths in mm.

1. The mask (`mask`): a pixel is figure when its colour lies more than `thresh` from the ground (per row, the
   median of the two edge strips), and, in the foot band (from `foot_band` px over the sole) only when it is coloured
   (the skin's chroma), so the grey contact shadow under the feet is ground. The sole is the lowest coloured row.
2. The panels (`panels`): column groups of figure pixels, left to right.
3. The front landmarks (`landmarks`): the top, the sole, the neck ring (the drawn line: the thin dark line across
   most of the neck from the chin down to the shoulder line, `ring_line`; not the chin's broad shadow), the
   shoulders (the widest trunk row in the upper 60 % between the ring and the armpits), the armpits (the arms part from the trunk), the crotch (the legs part), the ankles and
   wrists (the narrowest limb rows in their bands), the hand's end. The concepts show no narrowing at the knees and
   elbows, so those come from the skeleton.
4. The scale (`scale`): the ring row maps to the body's ring height and the sole to z = 0 (the head is its own piece,
   so the concept's head size does not set the body's); the concept's top of head by the same scale is reported.
5. The stations (`stations`): every 10 mm of height, every 5 mm across the neck, the chest and the crotch; per
   station the trunk's front width, the back view's width (the check), the side depth and its front and back edges;
   the limbs on their own axes (`limb`), the hands and feet (`hand`, `foot`), B's chest rounds (`chest`).
"""
from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path


# ---------------------------------------------------------------------------------------------------------- the PNG
def read_png(path) -> tuple[int, int, list[list[tuple[int, int, int]]]]:
    """(width, height, rows of (r, g, b)) of an 8-bit RGB or RGBA, non-interlaced PNG."""
    data = Path(path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path}: not a PNG")
    pos, idat, w = 8, [], None
    while pos < len(data):
        n, typ = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if typ == b"IHDR":
            w, h, depth, ctype, _, _, inter = struct.unpack(">IIBBBBB", body)
            if depth != 8 or ctype not in (2, 6) or inter:
                raise ValueError(f"{path}: want 8-bit RGB/RGBA non-interlaced, got depth {depth} type {ctype}")
            ch = 3 if ctype == 2 else 4
        elif typ == b"IDAT":
            idat.append(body)
        elif typ == b"IEND":
            break
    raw = zlib.decompress(b"".join(idat))
    stride = w * ch
    prev = bytearray(stride)
    rows = []
    for y in range(h):
        f = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        if f == 1:
            for i in range(ch, stride):
                line[i] = (line[i] + line[i - ch]) & 255
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                line[i] = (line[i] + ((line[i - ch] if i >= ch else 0) + prev[i]) // 2) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                b, c = prev[i], (prev[i - ch] if i >= ch else 0)
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        prev = line
        rows.append([tuple(line[i:i + 3]) for i in range(0, stride, ch)])
    return w, h, rows


def write_png(path, w: int, h: int, pixels: bytearray) -> Path:
    """An 8-bit RGB PNG from w * h * 3 bytes."""
    raw = b"".join(b"\x00" + bytes(pixels[y * w * 3:(y + 1) * w * 3]) for y in range(h))

    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    head = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", head) + chunk(b"IDAT", zlib.compress(raw, 6))
                     + chunk(b"IEND", b""))
    return path


# ---------------------------------------------------------------------------------------------------------- the mask
def _median(vals):
    s = sorted(vals)
    return s[len(s) // 2]


def chroma(p) -> int:
    return max(p) - min(p)


def _grow(r: int, k: int, full: int) -> int:
    for _ in range(k):
        r = r | (r << 1) | (r >> 1)
    return r & full


def mask(rows, thresh: int = 9, strip: int = 10, chroma_min: int = 20, foot_band: int = 70, close: int = 2):
    """Figure masks (a list of bytearrays, 1 = figure) and the sole row (the lowest coloured row).

    A pixel is ground when its colour lies within `thresh` of the row's ground; the figure is everything the ground
    flood from the picture's border does not reach, so a highlight inside the figure that matches the ground stays
    figure. The flood runs on the figure grown by `close` px (no leak through a thin gap), the result shrunk back."""
    h, w = len(rows), len(rows[0])
    full = (1 << w) - 1
    fig = []
    sole_rows = []
    for y in range(h):
        row = rows[y]
        bg = [_median([row[x][k] for x in list(range(2, 2 + strip)) + list(range(w - 2 - strip, w - 2))])
              for k in range(3)]
        bits = 0
        col = 0
        for x, p in enumerate(row):
            if max(abs(p[0] - bg[0]), abs(p[1] - bg[1]), abs(p[2] - bg[2])) > thresh:
                bits |= 1 << x
            if chroma(p) >= chroma_min:
                col += 1
        fig.append(bits)
        sole_rows.append(col)
    sole = max(y for y in range(h) if sole_rows[y] >= 6)
    for y in range(h):
        if y > sole:
            fig[y] = 0
        elif y > sole - foot_band:
            c = 0
            for x, p in enumerate(rows[y]):
                if chroma(p) >= chroma_min:
                    c |= 1 << x
            fig[y] &= c
    grown = [_grow(fig[y], close, full) for y in range(h)]
    grown = [grown[y] | (grown[y - 1] if y else 0) | (grown[y + 1] if y + 1 < h else 0) for y in range(h)]
    free = [full & ~g for g in grown]
    edge = 1 | (1 << (w - 1))
    reach = [free[y] if y in (0, h - 1) else free[y] & edge for y in range(h)]
    changed = True
    while changed:
        changed = False
        for order in (range(h), range(h - 1, -1, -1)):
            for y in order:
                r = reach[y] | (reach[y - 1] if y else 0) | (reach[y + 1] if y + 1 < h else 0)
                r &= free[y]
                while True:
                    n = (r | (r << 1) | (r >> 1)) & free[y]
                    if n == r:
                        break
                    r = n
                if r != reach[y]:
                    reach[y] = r
                    changed = True
    ground = [_grow(reach[y], close, full) for y in range(h)]
    ground = [ground[y] | (ground[y - 1] if y else 0) | (ground[y + 1] if y + 1 < h else 0) for y in range(h)]
    out = []
    for y in range(h):
        bits = full & ~ground[y] if y <= sole else 0
        out.append(bytearray((bits >> x) & 1 for x in range(w)))
    return out, sole


def runs(line, x0: int, x1: int, min_len: int = 3, gap: int = 2) -> list[tuple[int, int]]:
    """Runs [a, b] (inclusive) of figure pixels in line[x0:x1], gaps up to `gap` px closed, runs under min_len dropped."""
    out, a, last = [], None, None
    for x in range(x0, x1):
        if line[x]:
            if a is None:
                a = x
            elif x - last - 1 > gap:
                out.append((a, last))
                a = x
            last = x
    if a is not None:
        out.append((a, last))
    return [(a, b) for a, b in out if b - a + 1 >= min_len]


def panels(m, min_col: int = 2, min_gap: int = 20) -> list[tuple[int, int]]:
    """Column ranges [x0, x1) of the figures, left to right."""
    w = len(m[0])
    occ = [sum(m[y][x] for y in range(len(m))) >= min_col for x in range(w)]
    out, a, gapn = [], None, 0
    for x in range(w):
        if occ[x]:
            if a is None:
                a = x
            gapn = 0
            last = x
        elif a is not None:
            gapn += 1
            if gapn > min_gap:
                out.append((a, last + 1))
                a = None
    if a is not None:
        out.append((a, last + 1))
    return [p for p in out if p[1] - p[0] > 30]


def run_at(rs, x):
    """The run holding column x, or the nearest one."""
    best = None
    for r in rs:
        if r[0] <= x <= r[1]:
            return r
        d = min(abs(x - r[0]), abs(x - r[1]))
        if best is None or d < best[0]:
            best = (d, r)
    return best[1] if best else None


def luminance(p) -> float:
    return 0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2]


# ------------------------------------------------------------------------------------------------------ landmarks
def ring_line(rows, rr: dict, cx: int, y0: int, y1: int, reach: int = 2, sag: int = 3, t: float = 6.0,
              min_score: float = 20.0) -> int:
    """The drawn neck ring line's row from row y0 to y1 + sag + reach: a thin dark line across most of the neck.

    Per column of the run at cx (its middle 80 %) a pixel's thin-line contrast is how much darker it is than both
    pixels `reach` rows above and below (a broad shadow, like the chin's, scores little; a 1 to 3 px line a lot). The
    line sags a little (the ring's front arc seen from above), so a row's score takes each column's best contrast
    within `sag` rows: the mean contrast times the share of columns over `t`. At the best row, the ring is the median
    of the columns' own darkest rows near it. The window's end is y1 + sag + reach, so a line near y1 is scored over
    all its sag. A best score under min_score (no line drawn) raises ValueError."""
    def lum(y, x):
        return luminance(rows[y][x])

    def s(y, x):
        return min(lum(y - reach, x), lum(y + reach, x)) - lum(y, x)

    def cols(y):
        r = run_at(rr[y], cx)
        q = (r[1] - r[0] + 1) // 10
        return range(r[0] + q, r[1] - q + 1)

    def score(y):
        best = [max(s(y + d, x) for d in range(-sag, sag + 1)) for x in cols(y)]
        if not best:
            return 0.0
        return sum(max(0.0, b) for b in best) / len(best) * sum(1 for b in best if b > t) / len(best)
    yb = max(range(y0, y1 + sag + reach + 1), key=score)
    if score(yb) < min_score:
        raise ValueError(f"no drawn ring line between rows {y0} and {y1 + sag + reach} "
                         f"(best score {score(yb):.1f} at row {yb}, want {min_score})")
    at = []
    for x in cols(yb):
        y = max(range(yb - sag, yb + sag + 1), key=lambda y: s(y, x))
        if s(y, x) > t:
            at.append(y)
    return _median(at) if at else yb


def back_hidden(rows, sb: dict, y0: int, y1: int, win: int = 30, rise: float = 6.0, run: int = 3):
    """The side view's rows (first, last) between rows y0 (the armpits) and y1 (the crotch) where the hanging arm,
    not the body, forms the back edge, or None.

    Where the back shows behind the arm, the row's luminance inward from the back edge (its last `win` px, the edge
    pixel left out) has a valley, the crease between the arm and the back, at least 2 px in, with the back's strip
    `rise` brighter behind it; where the arm forms the edge its shading only darkens to the rim. The band starts at
    the first `run` rows without the valley and stops at the next `run` rows with it (the seat showing behind the
    arm again); its last row is the one where the back edge stands furthest forward: under it the edge turns back,
    the seat coming out from behind the arm."""
    def valley(y):
        e = sb[y]
        L = [luminance(rows[y][x]) for x in range(e - win, e - 1)]
        i = min(range(len(L)), key=lambda i: L[i])
        return len(L) - 1 - i >= 2 and max(L[i:]) - L[i] >= rise
    ys = [y for y in range(y0, y1 + 1) if y in sb]
    vis = {y: valley(y) for y in ys}

    def streak(y, want):
        return all(y + j in vis and vis[y + j] == want for j in range(run))
    a = next((y for y in ys if streak(y, False)), None)
    if a is None:
        return None
    stop = next((y for y in ys if y > a and streak(y, True)), ys[-1] + 1)
    b = max((y for y in ys if a <= y < stop), key=lambda y: (-sb[y], y))
    return a, b


def landmarks(m, rows, sole: int, panel: tuple[int, int]) -> dict:
    """The front view's landmark rows and the centre column (see the module doc)."""
    x0, x1 = panel
    top = min(y for y in range(len(m)) if any(m[y][x0:x1]))
    H = sole - top
    rr = {y: runs(m[y], x0, x1) for y in range(top, sole + 1)}
    mids = []
    for y in range(top + int(0.45 * H), top + int(0.55 * H)):
        r = max(rr[y], key=lambda r: r[1] - r[0])
        mids.append((r[0] + r[1]) / 2)
    cx = int(round(sum(mids) / len(mids)))

    def width(y):
        r = run_at(rr[y], cx)
        return r[1] - r[0] + 1 if r and r[0] <= cx <= r[1] else 0

    # the crotch: the highest row under mid-height with ground at the centre between two leg runs
    crotch = next(y for y in range(top + int(0.35 * H), sole) if not m[y][cx]
                  and any(r[1] < cx for r in rr[y]) and any(r[0] > cx for r in rr[y]))
    # the armpits: the highest row under the head where an arm run stands apart on both sides of the trunk
    head_end = top + int(0.12 * H)

    def parted(y):
        t = run_at(rr[y], cx)
        return t and any(r[1] < t[0] for r in rr[y]) and any(r[0] > t[1] for r in rr[y])
    armpit = next(y for y in range(head_end, crotch) if parted(y) and parted(y + 1) and parted(y + 2))
    # the neck: the narrowest trunk rows between the head and the armpits (the band; its top row is the chin's end)
    band = range(top + int(0.10 * H), armpit)
    ymin = min(band, key=width)
    nmin = width(ymin)
    n0 = n1 = ymin
    while n0 - 1 in band and width(n0 - 1) <= 1.25 * nmin:
        n0 -= 1
    while n1 + 1 in band and width(n1 + 1) <= 1.25 * nmin:
        n1 += 1
    # the ring: the drawn line from the chin (the band's top) down to the shoulder line (a first estimate: the first
    # row past half the way from the neck's width to the widest trunk row above the armpits), not only inside the
    # band: a neck may widen before the line (B), and the chin's shadow is broad, the line thin (`ring_line`)
    wsh = max(width(y) for y in range(ymin, armpit))
    s_end = next(y for y in range(ymin, armpit) if width(y) >= (nmin + wsh) / 2)
    ring = ring_line(rows, rr, cx, n0, s_end)
    shoulder = max(range(ring, ring + int(0.6 * (armpit - ring)) + 1), key=width)
    # the shoulder line: the first row under the ring past half the way from the neck to the shoulders' width
    half = (nmin + width(shoulder)) / 2
    shoulder_top = next(y for y in range(ring, armpit) if width(y) >= half)
    # legs: the left (image) leg run, the one ending nearest left of the centre
    def leg(y, side):
        rs = [r for r in rr[y] if (r[1] < cx if side < 0 else r[0] > cx)]
        if not rs:
            return None
        return max(rs, key=lambda r: r[1]) if side < 0 else min(rs, key=lambda r: r[0])
    lw = {y: (lambda r: r[1] - r[0] + 1 if r else 0)(leg(y, -1)) for y in range(crotch, sole + 1)}
    L = sole - crotch
    ankle = min(range(crotch + int(0.70 * L), crotch + int(0.93 * L)), key=lambda y: lw[y])
    # arms: the outermost run on the image left, from the armpit down to its end
    def arm(y):
        if y < crotch:
            t = run_at(rr[y], cx)
            inner = t[0] if t and t[0] <= cx <= t[1] else cx
        else:
            lg = leg(y, -1)
            inner = lg[0] - 2 if lg else cx
        rs = [r for r in rr[y] if r[1] < inner]
        return (min(r[0] for r in rs), max(r[1] for r in rs)) if rs else None
    ay = []
    for y in range(armpit, sole):
        if not arm(y):
            break
        ay.append(y)
    hand_end = max(ay)
    A = hand_end - armpit
    aw = {y: (lambda r: r[1] - r[0] + 1 if r else 0)(arm(y)) for y in ay}
    wrist = min((y for y in ay if armpit + 0.55 * A <= y <= armpit + 0.85 * A), key=lambda y: aw[y])
    return {"top": top, "sole": sole, "cx": cx, "ring": ring, "neck_band": [n0, n1], "shoulder_top": shoulder_top,
            "shoulder": shoulder, "armpit": armpit, "wrist": wrist, "hand_end": hand_end,
            "crotch": crotch, "ankle": ankle}


def scale(lm: dict, ring_z_mm: float) -> dict:
    """mm per pixel with the ring row at ring_z_mm and the sole at 0; the concept's top of head by that scale."""
    mm_px = ring_z_mm / (lm["sole"] - lm["ring"])
    return {"mm_px": mm_px, "ring_z": ring_z_mm, "top_z": (lm["sole"] - lm["top"]) * mm_px}


def z_of(y: float, lm: dict, sc: dict) -> float:
    return (lm["sole"] - y) * sc["mm_px"]


def y_of(z: float, lm: dict, sc: dict) -> float:
    return lm["sole"] - z / sc["mm_px"]


def station_heights(top_mm: float, fine: list[tuple[float, float]], step: float = 10.0, fine_step: float = 5.0):
    """Station heights from 0 to top_mm every `step`, every `fine_step` inside the fine bands [(lo, hi)]."""
    zs = set()
    z = 0.0
    while z <= top_mm + 1e-9:
        zs.add(round(z, 1))
        z += step
    for lo, hi in fine:
        z = math.ceil(lo / fine_step) * fine_step
        while z <= min(hi, top_mm) + 1e-9:
            zs.add(round(z, 1))
            z += fine_step
    zs.add(round(top_mm, 1))
    return sorted(zs)


# ------------------------------------------------------------------------------------------------- the height map
def zmap(pairs: list[tuple[float, float]]):
    """A piecewise-linear map from concept z to body z through landmark pairs [(concept, body)], and its inverse."""
    pairs = sorted(pairs)

    def f(z, a=0, b=1):
        for (c0, b0), (c1, b1) in zip(pairs, pairs[1:]):
            lo, hi = (c0, c1) if a == 0 else (b0, b1)
            if z <= hi or (c1, b1) == pairs[-1]:
                t = (z - lo) / (hi - lo)
                return (b0 + t * (b1 - b0)) if a == 0 else (c0 + t * (c1 - c0))
        raise ValueError(z)
    return (lambda z: f(z, 0)), (lambda z: f(z, 1))


def lerp_rows(table: dict, y: float):
    """A row measure (a dict row -> number or None) at a fractional row, linear between the rows around it."""
    y0 = math.floor(y)
    a, b = table.get(y0), table.get(y0 + 1)
    if a is None or b is None:
        return a if b is None else b
    return a + (y - y0) * (b - a)


def panel_rows(m, panel: tuple[int, int]) -> dict:
    """Per row of a panel: its runs, the panel's top and sole rows."""
    x0, x1 = panel
    ys = [y for y in range(len(m)) if any(m[y][x0:x1])]
    return {"top": min(ys), "sole": max(ys), "runs": {y: runs(m[y], x0, x1) for y in ys}}


def centre_col(pr: dict) -> int:
    """The panel's centre column: the widest run's middle over the rows from 45 % to 55 % of its height."""
    H = pr["sole"] - pr["top"]
    mids = []
    for y in range(pr["top"] + int(0.45 * H), pr["top"] + int(0.55 * H)):
        if not pr["runs"][y]:
            continue
        r = max(pr["runs"][y], key=lambda r: r[1] - r[0])
        mids.append((r[0] + r[1]) / 2)
    return int(round(sum(mids) / len(mids)))


def fit_line(pts: list[tuple[float, float]]) -> tuple[float, float]:
    """Least squares x = a + b y."""
    n = len(pts)
    my = sum(p[1] for p in pts) / n
    mx = sum(p[0] for p in pts) / n
    syy = sum((p[1] - my) ** 2 for p in pts)
    b = sum((p[1] - my) * (p[0] - mx) for p in pts) / syy if syy else 0.0
    return mx - b * my, b


# --------------------------------------------------------------------------------------------------- the stations
TRUNK_KEYS = ("z", "z_concept", "front_w", "back_w", "depth", "front_y", "back_y")
LEG_KEYS = ("z", "s", "width", "depth", "centre_x", "front_y", "back_y")
ARM_KEYS = ("s", "width", "centre_x", "z")


def _w(r):
    return None if r is None else r[1] - r[0] + 1


def measure(path, ring_z: float, crotch_z: float, hips_mid_y: float, fine: dict | None = None) -> dict:
    """Everything the tables hold, from one concept picture (see the module doc).

    ring_z, crotch_z: the body's neck ring and crotch heights (mm; the landmarks the height map pins); hips_mid_y:
    the body's mid-depth at the crotch + 60 mm (mm), where the side profile is aligned."""
    w, h, rows = read_png(path)
    m, sole = mask(rows)
    ps = panels(m)
    if len(ps) != 4:
        raise ValueError(f"{path}: {len(ps)} figures, want 4 (front, three-quarter, side, back)")
    lm = landmarks(m, rows, sole, ps[0])
    sc = scale(lm, ring_z)
    k = sc["mm_px"]
    to_body, to_concept = zmap([(0.0, 0.0), (z_of(lm["crotch"], lm, sc), crotch_z), (ring_z, ring_z)])
    cx = lm["cx"]
    front = {y: runs(m[y], *ps[0]) for y in range(lm["top"], sole + 1)}
    side, back = panel_rows(m, ps[2]), panel_rows(m, ps[3])
    bcx = centre_col(back)
    # each view's own sole; the same px scale (one orthographic-like picture)
    def srow(z, pr):
        return pr["sole"] - z / k

    def trunk_run(y):
        r = run_at(front.get(y, []), cx)
        return r if r and r[0] <= cx <= r[1] else None

    fw = {y: _w(trunk_run(y)) for y in front}
    bw = {}
    for y, rs in back["runs"].items():
        r = run_at(rs, bcx)
        bw[y] = _w(r) if r and r[0] <= bcx <= r[1] else None
    # the side: the widest run per row; across the hands' rows (the hand's end - 15 mm to the wrist + 25 mm) the
    # hand hangs in front, so the front edge there is bridged linearly (`bridged`), and the tables write those rows'
    # front_y and depth as "-" (side_hidden_z, in body z); under the armpits the hanging arm forms the back edge
    # (`back_hidden`), and those rows' back_y and depth are "-" (side_back_hidden_z)
    sf, sb = {}, {}
    for y, rs in side["runs"].items():
        if not rs:
            continue
        r = max(rs, key=lambda r: r[1] - r[0])
        sf[y], sb[y] = r[0], r[1]
    sf_raw = dict(sf)
    bh = back_hidden(rows, sb, round(srow(z_of(lm["armpit"], lm, sc), side)),
                     round(srow(z_of(lm["crotch"], lm, sc), side)))
    hand_lo = srow(z_of(lm["hand_end"], lm, sc) - 15, side)
    hand_hi = srow(z_of(lm["wrist"], lm, sc) + 25, side)
    a, b = math.floor(hand_hi), math.ceil(hand_lo)
    bridged = set()
    if a in sf and b in sf:
        for y in range(a + 1, b):
            sf[y] = sf[a] + (y - a) / (b - a) * (sf[b] - sf[a])
            bridged.add(y)

    def front_edge(ys):
        """The side's front edge at a fractional row, None where a row it reads is bridged."""
        if math.floor(ys) in bridged or math.ceil(ys) in bridged:
            return None
        return sy(lerp_rows(sf, ys))

    def back_edge(ys):
        """The side's back edge at a fractional row, None where a row it reads is the arm's (`back_hidden`)."""
        if bh and (bh[0] <= math.floor(ys) <= bh[1] or bh[0] <= math.ceil(ys) <= bh[1]):
            return None
        return sy(lerp_rows(sb, ys))
    # align the side: its mid-depth at the crotch + 60 mm onto the body's, on the edges as drawn (that row may lie
    # inside the hand's bridged rows)
    ya = srow(to_concept(crotch_z + 60), side)
    mid = (lerp_rows(sf_raw, ya) + lerp_rows(sb, ya)) / 2

    def sy(px):
        return None if px is None else hips_mid_y + (px - mid) * k

    fine = fine or {}
    zs = station_heights(ring_z, list(fine.values()))
    trunk = {key: [] for key in TRUNK_KEYS}
    crotch_c = z_of(lm["crotch"], lm, sc)
    hid_f, hid_b = [], []   # the station heights whose side edge reads a hidden row (the tables' hidden bands)
    for z in zs:
        zc = to_concept(z)
        yf, ys, yb = y_of(zc, lm, sc), srow(zc, side), srow(zc, back)
        f = lerp_rows(fw, yf) if zc >= crotch_c else None
        bb = lerp_rows(bw, yb) if zc >= crotch_c else None
        # under the crotch the side view holds the legs and feet (the legs' own table): "-" as for the widths
        fy, by = (front_edge(ys), back_edge(ys)) if zc >= crotch_c else (None, None)
        if zc >= crotch_c:
            hid_f += [z] if fy is None else []
            hid_b += [z] if by is None else []
        dp = by - fy if fy is not None and by is not None else None
        for key, v in zip(TRUNK_KEYS, (z, zc, f and f * k, bb and bb * k, dp, fy, by)):
            trunk[key].append(None if v is None else round(v, 1))
    # the head over the neck in the side view (a big head reaches down past the ring at its chin and nape): the side
    # values in the top 60 mm whose depth passes 1.3 times the neck's (60 to 120 mm under the ring) are dropped
    neck = [dp for z, dp in zip(trunk["z"], trunk["depth"]) if ring_z - 120 <= z <= ring_z - 60 and dp is not None]
    if neck:
        for i, z in enumerate(trunk["z"]):
            if z > ring_z - 60 and trunk["depth"][i] is not None and trunk["depth"][i] > 1.3 * min(neck):
                trunk["depth"][i] = trunk["front_y"][i] = trunk["back_y"][i] = None
    # the legs: the image-left leg run (the body's right leg; the body is symmetric) and its mirror averaged
    def leg(y, side_):
        rs = [r for r in front.get(y, []) if (r[1] < cx if side_ < 0 else r[0] > cx)]
        if not rs:
            return None
        return max(rs, key=lambda r: r[1]) if side_ < 0 else min(rs, key=lambda r: r[0])
    lpts = []
    for y in range(lm["crotch"] + 5, lm["ankle"] + 1):
        l, r = leg(y, -1), leg(y, 1)
        if l and r:
            lpts.append((((cx - (l[0] + l[1]) / 2) + ((r[0] + r[1]) / 2 - cx)) / 2, y))
    la, lb = fit_line(lpts)
    lcos = math.cos(math.atan(lb))
    legs = {key: [] for key in LEG_KEYS}
    hip = None
    for z in zs:
        zc = to_concept(z)
        if zc >= crotch_c:
            continue
        yf = round(y_of(zc, lm, sc))
        l, r = leg(yf, -1), leg(yf, 1)
        if not l or not r:
            continue
        wdt = (_w(l) + _w(r)) / 2 * k * (lcos if zc >= z_of(lm["ankle"], lm, sc) else 1.0)
        cxo = ((cx - (l[0] + l[1]) / 2) + ((r[0] + r[1]) / 2 - cx)) / 2 * k
        ys = srow(zc, side)
        fy, by = front_edge(ys), back_edge(ys)
        hid_f += [z] if fy is None else []
        hid_b += [z] if by is None else []
        hip = hip or z
        dp = by - fy if fy is not None and by is not None else None
        for key, v in zip(LEG_KEYS, (z, (crotch_z - z) / lcos, wdt, dp, cxo, fy, by)):
            legs[key].append(None if v is None else round(v, 1))
    # the arms: the outermost run on each side below the armpit, the axis fitted from the armpit to the wrist
    def arm(y, side_):
        if y < lm["crotch"]:
            t = run_at(front[y], cx)
            inner = (t[0] if side_ < 0 else t[1]) if t and t[0] <= cx <= t[1] else cx
        else:
            lg = leg(y, side_)
            inner = (lg[0] - 2 if side_ < 0 else lg[1] + 2) if lg else cx
        rs = [r for r in front[y] if (r[1] < inner if side_ < 0 else r[0] > inner)]
        if not rs:
            return None
        return (min(r[0] for r in rs), max(r[1] for r in rs))
    pts, arow = [], {}
    for y in range(lm["armpit"], lm["hand_end"] + 1):
        l, r = arm(y, -1), arm(y, 1)
        if not l or not r:
            continue
        off = ((cx - (l[0] + l[1]) / 2) + ((r[0] + r[1]) / 2 - cx)) / 2
        arow[y] = (off, (_w(l) + _w(r)) / 2)
        if y <= lm["wrist"]:
            pts.append((off, y))
    a0, b0 = fit_line(pts)
    ang = math.atan(b0)
    cos = math.cos(ang)
    # s = 0 where the axis meets the shoulder line (the shoulder_top row); 10 mm stations down the axis
    y_start = lm["shoulder_top"]
    arms = {key: [] for key in ARM_KEYS}
    s = 0.0
    y_first = min(arow)
    while True:
        y = y_start + s * cos / k
        if y > lm["hand_end"]:
            break
        if y >= y_first and round(y) in arow:
            off, wd = arow[round(y)]
            for key, v in zip(ARM_KEYS, (s, wd * k * cos, off * k, to_body(z_of(y, lm, sc)))):
                arms[key].append(round(v, 1))
        s += 10.0
    s_wrist = (lm["wrist"] - y_start) / cos * k
    s_end = (lm["hand_end"] - y_start) / cos * k
    s_armpit = (lm["armpit"] - y_start) / cos * k
    return {"path": str(path), "size": [w, h], "panels": ps, "landmarks": lm, "scale": sc, "side": {k_: side[k_] for k_ in ("top", "sole")},
            "back": {"top": back["top"], "sole": back["sole"], "cx": bcx}, "side_mid_px": mid,
            "crotch_concept": round(crotch_c, 1), "trunk": trunk, "legs": legs, "arms": arms,
            "side_hidden_z": [min(hid_f), max(hid_f)] if hid_f else None,
            "side_back_hidden_z": [min(hid_b), max(hid_b)] if hid_b else None,
            "side_back_hidden_rows": list(bh) if bh else None,
            "leg_axis": {"angle_deg": round(math.degrees(math.atan(lb)), 2), "a_px": la, "b": lb},
            "arm_axis": {"angle_deg": round(math.degrees(ang), 2), "s_armpit": round(s_armpit, 1),
                         "s_wrist": round(s_wrist, 1), "s_end": round(s_end, 1), "a_px": a0, "b": b0},
            "_mask": m, "_rows": rows, "_front": front, "_side": side, "_sf": sf, "_sb": sb, "_arm": arm,
            "_leg": leg}
