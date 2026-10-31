"""Gate 2's plain maths (art #196; docs/clothes.md, "Gate 2"), testable without Blender: the spec's expressions, the
concept's garment mask (a colour rule, a vertical opening that drops the shirt's stripes, a closing, the largest
pieces), the build's silhouette raster, the overlap, the stations' edges, the motion numbers' verdicts. Masks are
bytearrays of w x h (1 = garment). Plain Python throughout
(the stretch takes numpy arrays too), so the runner's tests import and run all of it."""
from __future__ import annotations

import math
import re

def file_sha256(path) -> str:
    """A file's SHA-256 (hex): the build id that ties a probe, a motion result and the videos to one build."""
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --- the spec's expressions --------------------------------------------------------------------------------------

_TERM = re.compile(r"\s*([+-]?)\s*([A-Za-z_][A-Za-z0-9_]*|[0-9]*\.?[0-9]+)")


def resolve(expr, build: dict, spec_dims: dict, landmarks: dict) -> float:
    """A spec height or size in cm: a number, or names and numbers added and subtracted ('waistband_top_z+1',
    'waistband_top_z-waistband_h'). A name is the build's measured value if it has one, else the spec's cm, else her
    landmark; 'spec:NAME' always the spec's cm."""
    if isinstance(expr, (int, float)):
        return float(expr)
    text, pos, total = str(expr).replace("spec:", "spec__"), 0, 0.0
    while pos < len(text):
        m = _TERM.match(text, pos)
        if not m or m.end() == pos:
            raise ValueError(f"cannot read {expr!r} at {text[pos:]!r}")
        sign, tok = (-1.0 if m.group(1) == "-" else 1.0), m.group(2)
        if tok[0].isdigit() or tok[0] == ".":
            v = float(tok)
        elif tok.startswith("spec__"):
            v = float(spec_dims[tok[6:]]["cm"])
        elif build.get(tok, {}).get("cm") is not None:
            v = float(build[tok]["cm"])
        elif tok in spec_dims:
            v = float(spec_dims[tok]["cm"])
        elif tok in landmarks:
            v = float(landmarks[tok])
        else:
            raise ValueError(f"{expr!r}: no build measure, spec size or landmark {tok!r}")
        total += sign * v
        pos = m.end()
    return total


# --- masks -------------------------------------------------------------------------------------------------------

def colour_mask(rows, box, rule: dict) -> tuple[int, int, bytearray]:
    """The pixels of rows (r, g, b) inside box [x0, y0, x1, y1] that pass the rule: blue over red by b_minus_r, blue
    over green by b_minus_g (denim; the teal skin has more green than blue), no channel over max (the grey
    background, the white shoes)."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    br, bg, mx = rule.get("b_minus_r", 25), rule.get("b_minus_g", 12), rule.get("max", 205)
    out = bytearray(w * h)
    for y in range(h):
        row = rows[y0 + y]
        for x in range(w):
            p = row[x0 + x]
            r, g, b = p[0], p[1], p[2]
            if b - r >= br and b - g >= bg and max(r, g, b) <= mx:
                out[y * w + x] = 1
    return w, h, out


def _run_1d(vals: bytearray, n: int, start: int, step: int, rad: int, need_all: bool) -> list[int]:
    """Erode (need_all) or dilate one line of n cells by rad, with a prefix sum."""
    pre = [0] * (n + 1)
    for i in range(n):
        pre[i + 1] = pre[i] + vals[start + i * step]
    out = [0] * n
    for i in range(n):
        a, b = max(0, i - rad), min(n, i + rad + 1)
        s = pre[b] - pre[a]
        out[i] = 1 if (s == b - a if need_all else s > 0) else 0
    return out


def morph(mask: bytearray, w: int, h: int, rx: int, ry: int, erode: bool) -> bytearray:
    """A rectangular (2 rx + 1) x (2 ry + 1) erosion or dilation, separable: rows, then columns."""
    m = bytearray(mask)
    if rx:
        for y in range(h):
            m[y * w:(y + 1) * w] = bytes(_run_1d(m, w, y * w, 1, rx, erode))
    if ry:
        for x in range(w):
            col = _run_1d(m, h, x, w, ry, erode)
            for y in range(h):
                m[y * w + x] = col[y]
    return m


def opening(mask, w, h, rx, ry):
    return morph(morph(mask, w, h, rx, ry, True), w, h, rx, ry, False)


def closing(mask, w, h, rx, ry):
    return morph(morph(mask, w, h, rx, ry, False), w, h, rx, ry, True)


def components(mask: bytearray, w: int, h: int) -> list[list[int]]:
    """The 4-connected pieces of a mask, each a list of pixel indices, largest first."""
    seen = bytearray(len(mask))
    out = []
    for i in range(len(mask)):
        if mask[i] and not seen[i]:
            seen[i] = 1
            stack, piece = [i], []
            while stack:
                k = stack.pop()
                piece.append(k)
                x, y = k % w, k // w
                for nb, ok in ((k - 1, x > 0), (k + 1, x < w - 1), (k - w, y > 0), (k + w, y < h - 1)):
                    if ok and mask[nb] and not seen[nb]:
                        seen[nb] = 1
                        stack.append(nb)
            out.append(piece)
    return sorted(out, key=len, reverse=True)


def keep_large(mask: bytearray, w: int, h: int, share: float) -> bytearray:
    """Only the pieces at least `share` of the largest one's size."""
    pieces = components(mask, w, h)
    out = bytearray(len(mask))
    if pieces:
        for p in pieces:
            if len(p) >= share * len(pieces[0]):
                for k in p:
                    out[k] = 1
    return out


def fill_holes(mask: bytearray, w: int, h: int) -> bytearray:
    """The mask with every empty pixel not connected (4-way) to the box's border filled: a pocket's stitching, a
    seam, a highlight inside the garment."""
    outside = bytearray(len(mask))
    stack = [i for i in list(range(w)) + list(range(w * (h - 1), w * h)) + list(range(0, w * h, w))
             + list(range(w - 1, w * h, w)) if not mask[i]]
    for i in stack:
        outside[i] = 1
    while stack:
        k = stack.pop()
        x, y = k % w, k // w
        for nb, ok in ((k - 1, x > 0), (k + 1, x < w - 1), (k - w, y > 0), (k + w, y < h - 1)):
            if ok and not mask[nb] and not outside[nb]:
                outside[nb] = 1
                stack.append(nb)
    return bytearray(0 if o else 1 for o in outside)


def concept_mask(rows, box, rule: dict) -> tuple[int, int, bytearray]:
    """The concept's garment in one view's box: the colour rule, an opening of open_ry rows (the shirt's navy stripes
    are thinner, the denim is not), a closing of close_r (seams, stitching, buckles), the pieces over keep_share of
    the largest, the holes inside them filled."""
    w, h, m = colour_mask(rows, box, rule)
    ry = rule.get("open_ry", 4)
    if ry:
        m = opening(m, w, h, 0, ry)
    cr = rule.get("close_r", 3)
    if cr:
        m = closing(m, w, h, cr, cr)
    m = keep_large(m, w, h, rule.get("keep_share", 0.02))
    return w, h, fill_holes(m, w, h) if rule.get("fill_holes", True) else m


def fill_rows(mask: bytearray, w: int, h: int) -> bytearray:
    """Each row's span from its first to its last garment pixel filled: the concept's side arm and hand cover the
    garment's side, so their holes inside the outline count as garment (art #196, G3c)."""
    out = bytearray(mask)
    for y in range(h):
        row = mask[y * w:(y + 1) * w]
        if 1 in row:
            a, b = row.index(1), w - 1 - row[::-1].index(1)
            out[y * w + a:y * w + b + 1] = b"\x01" * (b - a + 1)
    return out


def raster(tris, w: int, h: int, depth: list | None = None, owner: bytearray | None = None, tag: int = 1) -> bytearray:
    """Triangles in pixel coordinates filled into a w x h mask (pixel centres, either winding). With depth (a list of
    w x h floats, smaller nearer) and owner, each point is (x, y, d): a pixel goes to the nearest triangle, owner
    holds its tag (the visible silhouette: a garment behind her body is not seen)."""
    m = bytearray(w * h) if owner is None else owner
    for a, b, c in tris:
        x0, x1 = max(0, int(min(a[0], b[0], c[0]))), min(w - 1, int(max(a[0], b[0], c[0])) + 1)
        y0, y1 = max(0, int(min(a[1], b[1], c[1]))), min(h - 1, int(max(a[1], b[1], c[1])) + 1)
        area = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        if area == 0 or x0 > x1 or y0 > y1:
            continue
        for y in range(y0, y1 + 1):
            py = y + 0.5
            for x in range(x0, x1 + 1):
                px = x + 0.5
                e0 = (b[0] - a[0]) * (py - a[1]) - (b[1] - a[1]) * (px - a[0])
                e1 = (c[0] - b[0]) * (py - b[1]) - (c[1] - b[1]) * (px - b[0])
                e2 = (a[0] - c[0]) * (py - c[1]) - (a[1] - c[1]) * (px - c[0])
                if (e0 >= 0 and e1 >= 0 and e2 >= 0) or (e0 <= 0 and e1 <= 0 and e2 <= 0):
                    i = y * w + x
                    if depth is None:
                        m[i] = tag
                        continue
                    d = (e1 * a[2] + e2 * b[2] + e0 * c[2]) / area   # barycentric: e1 is a's weight x area
                    if d < depth[i]:
                        depth[i] = d
                        m[i] = tag
    return m


def overlap(a: bytearray, b: bytearray, rows: tuple[int, int] | None = None, w: int = 0) -> dict:
    """Intersection over union of two masks, and each one's share outside the other; rows (r0, r1) and the width w
    limit it to those rows."""
    if rows:
        a, b = a[rows[0] * w:(rows[1] + 1) * w], b[rows[0] * w:(rows[1] + 1) * w]
    both = sum(1 for p, q in zip(a, b) if p and q)
    na, nb = sum(a), sum(b)
    union = na + nb - both
    return {"iou": round(both / union, 4) if union else 0.0, "a_px": na, "b_px": nb, "both_px": both,
            "a_only": round((na - both) / na, 4) if na else 0.0, "b_only": round((nb - both) / nb, 4) if nb else 0.0}


def edges(mask: bytearray, w: int, h: int, row: int, c0: int, c1: int):
    """The first and last garment column on a row inside [c0, c1], or None."""
    if not 0 <= row < h:
        return None
    cols = [x for x in range(max(0, c0), min(w, c1 + 1)) if mask[row * w + x]]
    return (cols[0], cols[-1]) if cols else None


def top_row(mask: bytearray, w: int, h: int, c0: int, c1: int, r0: int, r1: int, bottom: bool = False):
    """The highest (or lowest) garment row inside the columns [c0, c1] and rows [r0, r1], or None."""
    rng = range(min(h - 1, r1), max(0, r0) - 1, -1) if bottom else range(max(0, r0), min(h, r1 + 1))
    for y in rng:
        if any(mask[y * w + x] for x in range(max(0, c0), min(w, c1 + 1))):
            return y
    return None


# --- motion ------------------------------------------------------------------------------------------------------

def stretch(rest, now, edges_ij, min_len: float = 0.003) -> tuple[float | None, float | None]:
    """The largest and the 95th percentile (linear, as numpy's default) |length / rest length - 1| of the edges (i, j)
    longer than min_len at rest, in %; (None, None) when there is no such edge: an empty part is never a pass.
    Plain Python: rest and now are lists of points or numpy arrays."""
    rest = rest.tolist() if hasattr(rest, "tolist") else rest
    now = now.tolist() if hasattr(now, "tolist") else now
    edges_ij = edges_ij.tolist() if hasattr(edges_ij, "tolist") else edges_ij
    r = []
    for i, j in edges_ij:
        l0 = math.dist(rest[i], rest[j])
        if l0 > min_len:
            r.append(abs(math.dist(now[i], now[j]) / l0 - 1.0) * 100)
    if not r:
        return None, None
    r.sort()
    k = 0.95 * (len(r) - 1)
    f = int(k)
    p95 = r[f] + (r[min(f + 1, len(r) - 1)] - r[f]) * (k - f)
    return r[-1], p95


def classify(sizes: list[int], spans: list[tuple[float, float, float, float]], over_z: float, hw_max: int) -> list[str]:
    """Each garment piece's class from its vertex count and rest span (z max, y min, y max, unused): 'strap' if it
    reaches over over_z with points both in front (y < -2 cm) and behind (y > 2 cm), it goes over the shoulder,
    whatever its size; else 'hardware' if it has at most hw_max vertices; else 'panel'."""
    out = []
    for n, (zmax, ymin, ymax, _) in zip(sizes, spans):
        if zmax > over_z and ymin < -0.02 and ymax > 0.02:
            out.append("strap")
        elif n <= hw_max:
            out.append("hardware")
        else:
            out.append("panel")
    return out


def verdict(value, tol, smaller_is_better: bool = True):
    """True when value is within tol (<= tol, or >= tol for a minimum), None when unmeasured."""
    if value is None:
        return None
    return value <= tol if smaller_is_better else value >= tol
