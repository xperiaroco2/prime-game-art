"""The ship's crystal socket's drawing (art#263's stations). Plain Python, no Blender: the built numbers
(socket_dims.toml) as the front (u, h) and side (d, h) views' lines in cm, the shared geometry helpers the build uses
(load, loop, offset), and an SVG of those lines over the drawing's straight views (front-ortho.jpg, side-ortho.jpg,
placed at the drawing's own scale) and over the model's orthographic renders, so a mismatch shows.
socket_build.py draws the same lines into PNGs (overlay_<concept|model>_<view>.png) in Blender.

    $PYTHON_BIN tools/blender/socket_drawing.py <build dir> [--out DIR]

Writes DIR (default <build dir>/drawing)/drawing.svg; its images are linked by relative path (../renders/...).
"""
from __future__ import annotations

import argparse
import math
import tomllib
from pathlib import Path

DIMS_FILE = Path(__file__).with_name("socket_dims.toml")
# the views' frames in cm: width, height, the frame's middle (u or d, h - mount); socket_build.py ORTHO
ORTHO = {"front": (80.0, 100.0, 0.0, -10.0), "side": (80.0, 100.0, 10.0, -10.0)}
PX_PER_CM = 6
POLYS = ("outline", "bay", "ring", "header", "claw", "block", "collar")


def load(path: Path = DIMS_FILE) -> dict:
    """The dims with every h moved by [mount] h - drawn_at (the one number that moves the socket)."""
    d = tomllib.loads(path.read_text(encoding="utf-8"))
    s = d["mount"]["h"] - d["mount"]["drawn_at"]
    for name in POLYS:
        d[name]["pts"] = [[u, h + s] for u, h in d[name]["pts"]]
    d["outline"]["seams"] = [[u, h + s] for u, h in d["outline"].get("seams", [])]
    for name in ("outer", "bottom"):
        d["slots"][name] = [[u0, u1, h0 + s, h1 + s] for u0, u1, h0, h1 in d["slots"][name]]
    d["collar"]["window_h"] = [h + s for h in d["collar"]["window_h"]]
    for name in ("neck", "lamp_ring", "lamp"):
        d[name]["h"] = [h + s for h in d[name]["h"]]
    d["measure"]["bottom_h"] += s
    d["mount"]["tip_h"] = d["mount"]["h"] - d["mount"]["crystal"] / 2.0
    return d


def loop(half: list) -> list:
    """A right half from the centre line's top to its bottom, mirrored: the whole closed loop (u, h)."""
    half = [tuple(p) for p in half]
    return half + [(-u, h) for u, h in reversed(half[1:-1])]


def offset(pts: list, dist: float) -> list:
    """The closed loop pts moved dist outward (negative: inward), each corner along its bisector (mitred)."""
    n = len(pts)
    area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
    sign = 1.0 if area > 0 else -1.0  # the outward side of an edge: right of it on a counter-clockwise loop
    out = []
    for i in range(n):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % n]
        norms = []
        for a, b in ((p0, p1), (p1, p2)):
            dx, dy = b[0] - a[0], b[1] - a[1]
            ln = math.hypot(dx, dy) or 1.0
            norms.append((sign * dy / ln, -sign * dx / ln))
        bx, by = norms[0][0] + norms[1][0], norms[0][1] + norms[1][1]
        bl = math.hypot(bx, by) or 1.0
        bx, by = bx / bl, by / bl
        k = dist / max(0.35, bx * norms[0][0] + by * norms[0][1])
        out.append((p1[0] + bx * k, p1[1] + by * k))
    return out


def _ray(pts: list, c: tuple, a: float) -> tuple:
    """Where the ray from c at angle a (0 up, + toward +u) first leaves the closed loop pts."""
    du, dh = math.sin(a), math.cos(a)
    best = None
    n = len(pts)
    for i in range(n):
        (u0, h0), (u1, h1) = pts[i], pts[(i + 1) % n]
        eu, eh = u1 - u0, h1 - h0
        den = du * eh - dh * eu
        if abs(den) < 1e-12:
            continue
        t = ((u0 - c[0]) * eh - (h0 - c[1]) * eu) / den
        s = ((u0 - c[0]) * dh - (h0 - c[1]) * du) / den
        if t > 1e-9 and -1e-9 <= s <= 1 + 1e-9 and (best is None or t < best):
            best = t
    return (c[0] + du * best, c[1] + dh * best)


def ray_angle(p: tuple, c: tuple) -> float:
    """The angle of the ray from c through p (0 up, + toward +u), in [0, 2 pi), rounded as match() keys its rays."""
    return round(math.atan2(p[0] - c[0], p[1] - c[1]) % (2 * math.pi), 9)


def match(outer: list, inner: list, c: tuple, extra: list = ()) -> tuple:
    """Two closed loops, both star-shaped from c, resampled on the same rays (every corner of either, and the rays
    through the `extra` points: the outer blocks' seams), so a ring between them is quads of matching points:
    (outer, inner), clockwise from the top."""
    ang = sorted({ray_angle(p, c) for p in [*outer, *inner, *extra]})
    return [_ray(outer, c, a) for a in ang], [_ray(inner, c, a) for a in ang]


def lines(d: dict) -> dict:
    """The built numbers as the two views' lines: {"front": [(name, [(u, h), ...], closed)], "side": [...]}."""
    dp = d["depth"]
    front = [("outline", loop(d["outline"]["pts"]), True),
             ("outer", offset(loop(d["outline"]["pts"]), -d["outline"]["inset"]), True),
             ("bay", loop(d["bay"]["pts"]), True), ("ring", loop(d["ring"]["pts"]), True),
             ("strip", offset(loop(d["bay"]["pts"]), d["ring"]["strip"]), True),
             ("header", loop(d["header"]["pts"]), True), ("block", loop(d["block"]["pts"]), True),
             ("collar", loop(d["collar"]["pts"]), True)]
    claw = [tuple(p) for p in d["claw"]["pts"]]
    front += [("claw", claw, True), ("claw", [(-u, h) for u, h in claw], True)]
    for u0, u1, h0, h1 in d["slots"]["outer"] + [[-b, -a, c, e] for a, b, c, e in d["slots"]["outer"]] + d["slots"]["bottom"]:
        front.append(("slot", [(u0, h0), (u1, h0), (u1, h1), (u0, h1)], True))
    for name in ("neck", "lamp_ring", "lamp"):
        r, (h0, h1) = d[name]["ru"], d[name]["h"]
        front.append((name, [(-r, h0), (r, h0), (r, h1), (-r, h1)], True))
    hs = [p[1] for p in d["outline"]["pts"]]
    bottom, top = min(hs), max(hs)

    def col(name: str, d0: float, d1: float, h0: float, h1: float) -> tuple:
        return (name, [(d0, h0), (d1, h0), (d1, h1), (d0, h1)], True)

    hh = [p[1] for p in d["header"]["pts"]]
    ch = [p[1] for p in d["claw"]["pts"]]
    kh = [p[1] for p in d["collar"]["pts"]]
    bh = [p[1] for p in d["block"]["pts"]]
    rh = [p[1] for p in d["ring"]["pts"]]
    side = [col("plate", 0.0, dp["plate"], bottom, top), col("outer", dp["plate"], dp["layer"], bottom + 0.8, top - 0.8),
            col("ring", dp["layer"], max(dp["ring"], dp["lip"]), min(rh), max(rh)), col("header", dp["plate"], dp["header"], min(hh), max(hh)),
            col("claw", dp["claw"][0], dp["claw"][1], min(ch), max(ch)), col("block", dp["plate"], dp["front"], min(bh), max(bh)),
            col("collar", dp["collar"][0], dp["collar"][1], min(kh), max(kh)), ("bay", [(dp["bay"], min(kh)), (dp["bay"], max(hh))], False)]
    for name in ("neck", "lamp_ring", "lamp"):
        c, r, (h0, h1) = d[name].get("d", d["neck"]["d"]), d[name]["rd"], d[name]["h"]
        side.append(col(name, c - r, c + r, h0, h1))
    a, m = d["mount"]["axis_d"], d["mount"]
    side.append(("axis", [(a, m["tip_h"]), (a, m["tip_h"] + m["crystal"])], False))
    front.append(("axis", [(0.0, m["tip_h"]), (0.0, m["tip_h"] + m["crystal"])], False))
    return {"front": front, "side": side}


def frame(d: dict, view: str) -> tuple:
    """The view's frame in cm: (left, top) of its picture, width, height."""
    w, h, cx, ch = ORTHO[view]
    return cx - w / 2, d["mount"]["h"] + ch + h / 2, w, h


def svg(d: dict, under: dict) -> str:
    """The lines over each view's pictures: per view one column per underlay (concept, model)."""
    cols = []
    for view in ("front", "side"):
        for kind, href in under.items():
            cols.append((view, kind, href.format(view=view)))
    w, h = ORTHO["front"][0], ORTHO["front"][1]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
           f'viewBox="0 0 {len(cols) * (w + 4)} {h + 10}" width="{len(cols) * (w + 4) * 8}" height="{(h + 10) * 8}">',
           '<rect width="100%" height="100%" fill="#0d1420"/>']
    for i, (view, kind, href) in enumerate(cols):
        x0 = i * (w + 4)
        left, top, fw, fh = frame(d, view)
        out.append(f'<g transform="translate({x0} 8)"><image xlink:href="{href}" width="{fw}" height="{fh}"/>')
        out.append(f'<text x="1" y="-2" font-size="3" fill="#e8eef5">{view} over the {kind}</text>')
        for name, pts, closed in lines(d)[view]:
            colour = {"axis": "#7fe6ff", "slot": "#ffb347", "bay": "#ff8a3c"}.get(name, "#ffd27a")
            p = " ".join(f"{u - left:.2f},{top - hh:.2f}" for u, hh in pts)
            tag = "polygon" if closed else "polyline"
            out.append(f'<{tag} points="{p}" fill="none" stroke="{colour}" stroke-width="0.18"/>')
        out.append("</g>")
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("build", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    out = a.out or a.build / "drawing"
    out.mkdir(parents=True, exist_ok=True)
    d = load()
    text = svg(d, {"concept": "../renders/concept_{view}.png", "model": "../renders/ortho_{view}.png"})
    (out / "drawing.svg").write_text(text, encoding="utf-8", newline="\n")
    print(f"SOCKET drawing {out / 'drawing.svg'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
