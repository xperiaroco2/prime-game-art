"""The energy crystal's engineering drawing (art#263; the engineer, 2026-10-24: the part from different sides, in
centimetres, everything exact). Plain Python, no Blender: the front, side and top orthographic views of the model's
own edges (features.json, written by crystal_build.py before the chamfers: the folds and open edges, each with its
faces' normals; an edge is drawn when one of its faces looks at the viewer) and the dimensions from the numbers it was
built from (crystal_dims.toml). The views' frames are crystal_build.py's ORTHO frames, so a view lies exactly over
its orthographic render (ortho_<state>_<view>.png) and over the concept sheet's view cut to the same frame
(concept_<view>.png).

    $PYTHON_BIN tools/blender/crystal_drawing.py <build dir> [--out DIR]

Writes into DIR (default <build dir>/drawing): drawing.svg (ink on paper), drawing_concept.svg (over the concept's
views), drawing_model.svg (over the spent model's orthographic renders); the images are linked by relative path
(../renders/...), so the files stay beside the build.
"""
from __future__ import annotations

import argparse
import json
import math
import tomllib
from pathlib import Path

DIMS_FILE = Path(__file__).with_name("crystal_dims.toml")
# the views' frames in cm (crystal_build.py ORTHO): width, height, the frame's middle (x, z; the top view x, y)
ORTHO = {"front": (16.0, 37.0, 0.0, 17.5), "side": (16.0, 37.0, 0.0, 17.5), "top": (16.0, 16.0, 0.0, 0.0)}
TOP = 4.2                      # the title band over the views (cm)
X0 = {"front": 13.0, "side": 43.0, "top": 70.0}   # each frame's left edge on the sheet (cm)
WIDTH, HEIGHT = 90.0, 47.5
UNDERLAY = {"concept": "../renders/concept_{view}.png", "model": "../renders/ortho_spent_{view}.png"}
STYLE = {
    "paper": (".bg{fill:#f4f1e8}.e{stroke:#1e2a36}.c{stroke:#1e2a36}.d{stroke:#9b3b16;fill:#9b3b16}"
              ".t{fill:#9b3b16}.h{fill:#1e2a36}.f{stroke:#b8b2a2}"),
    "over": (".bg{fill:#0d1420}.e{stroke:#ffd27a}.c{stroke:#7fe6ff}.d{stroke:#ff8a3c;fill:#ff8a3c}"
             ".t{fill:#ffb27a}.h{fill:#e8eef5}.f{stroke:#3a4658}"),
}


class Sheet:
    def __init__(self) -> None:
        self.out: list[str] = []

    def line(self, a, b, cls: str, w: float = 0.035) -> None:
        self.out.append(f'<line x1="{a[0]:.3f}" y1="{a[1]:.3f}" x2="{b[0]:.3f}" y2="{b[1]:.3f}" class="{cls}" '
                        f'stroke-width="{w}"/>')

    def text(self, p, s: str, cls: str = "t", size: float = 0.62, anchor: str = "middle", rot: float = 0.0) -> None:
        tr = f' transform="rotate({rot:.1f} {p[0]:.3f} {p[1]:.3f})"' if rot else ""
        self.out.append(f'<text x="{p[0]:.3f}" y="{p[1]:.3f}" class="{cls}" font-size="{size}" '
                        f'text-anchor="{anchor}"{tr}>{s}</text>')

    def arrow(self, tip, toward) -> None:
        dx, dy = toward[0] - tip[0], toward[1] - tip[1]
        n = math.hypot(dx, dy) or 1.0
        ux, uy = dx / n, dy / n
        a, w = 0.42, 0.13
        pts = [tip, (tip[0] + ux * a - uy * w, tip[1] + uy * a + ux * w), (tip[0] + ux * a + uy * w, tip[1] + uy * a - ux * w)]
        self.out.append('<polygon points="' + " ".join(f"{x:.3f},{y:.3f}" for x, y in pts) + '" class="d" '
                        'stroke-width="0.01"/>')

    def dim(self, a, b, label: str, side: float = 0.0, ext_from=None) -> None:
        """A dimension from sheet point a to b, its label beside the line (side: the label's offset across it)."""
        if ext_from:
            for p, q in zip(ext_from, (a, b)):
                self.line(p, q, "d", 0.018)
        self.line(a, b, "d", 0.025)
        self.arrow(a, b)
        self.arrow(b, a)
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        vertical = abs(b[0] - a[0]) < 1e-6
        if vertical:
            self.text((mx - 0.25 + side, my), label, rot=-90.0)
        else:
            self.text((mx, my - 0.22 + side), label)


def fmt(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".") if abs(v - round(v, 1)) < 1e-9 else f"{v:.2f}"


def project(view: str, p) -> tuple:
    w, h, cx, cz = ORTHO[view]
    x0 = X0[view]
    if view == "front":
        return x0 + w / 2 + (p[0] - cx), TOP + (cz + h / 2) - p[2]
    if view == "side":
        return x0 + w / 2 + (p[1] - cx), TOP + (cz + h / 2) - p[2]
    return x0 + w / 2 + (p[0] - cx), TOP + h / 2 - (p[1] - cz)


def faces_viewer(view: str, normal) -> bool:
    return {"front": -normal[1], "side": normal[0], "top": normal[2]}[view] > 1e-4


HIDDEN_FROM_ABOVE = {"crystal", "core", "skirt", "lip", "rim", "groove"}  # all under the band, which is wider


def edges(sheet: Sheet, view: str, feats: dict, d: dict) -> None:
    """The model's edges a view sees: those with a face toward the viewer, minus the parts hidden inside others (the
    core; the crystal's top inside the skirt; from above, everything under the band)."""
    z_cap = d["skirt"]["z_bottom"]
    for part, a, b, normals in feats["edges"]:
        if part == "core" or (view == "top" and part in HIDDEN_FROM_ABOVE):
            continue
        if part == "crystal" and min(a[2], b[2]) > z_cap - 0.01:
            continue
        if normals and not any(faces_viewer(view, n) for n in normals):
            continue
        sheet.line(project(view, a), project(view, b), "c" if part == "crystal" else "e")


def front_dims(s: Sheet, d: dict) -> None:
    c, sk, rim, band, dome, disc, lp = (d[k] for k in ("crystal", "skirt", "rim", "band", "dome", "disc", "loop"))
    g = d["groove"]
    v = "front"
    x_l = X0[v] - 0.8                      # the first column of heights, left of the frame
    def pz(z: float) -> float:
        return project(v, (0, 0, z))[1]
    stack = [(0.0, c["z_point_ring"], "point"), (c["z_point_ring"], c["z_body_top"], "body"),
             (c["z_body_top"], sk["z_bottom"], ""), (sk["z_bottom"], sk["z_top"], "skirt"),
             (band["z_bottom"], band["z_top"], "band"), (dome["z_bottom"], dome["z_top"], "dome"),
             (disc["z_bottom"], disc["z_top"], "disc"), (lp["z_feet"], lp["z_top"], "loop")]
    for z0, z1, name in stack:
        a, b = (x_l, pz(z0)), (x_l, pz(z1))
        s.dim(a, b, fmt(z1 - z0) if (z1 - z0) >= 1.2 else "", side=0.0)
        if (z1 - z0) < 1.2:
            s.text((x_l - 0.35, (a[1] + b[1]) / 2 + 0.2), fmt(z1 - z0), anchor="end", size=0.5)
        if name:
            s.text((x_l - 1.15, (a[1] + b[1]) / 2 + 0.2), name, cls="h", anchor="end", size=0.5)
        s.line((x_l - 0.2, pz(z0)), (X0[v] + 1.5, pz(z0)), "f", 0.012)
    s.line((x_l - 0.2, pz(lp["z_top"])), (X0[v] + 1.5, pz(lp["z_top"])), "f", 0.012)
    x_t = X0[v] - 5.4
    s.dim((x_t, pz(0.0)), (x_t, pz(lp["z_top"])), f"{fmt(lp['z_top'])} overall")
    s.text((x_l - 1.15, pz((rim["z_bottom"] + band["z_bottom"]) / 2) + 0.2),
           f"rim {fmt(rim['z_top'] - rim['z_bottom'])} + groove {fmt(g['height'])}", cls="h", anchor="end", size=0.42)
    # widths at their heights, dimension lines just above each feature
    cx = X0[v] + ORTHO[v][0] / 2
    def hd(width: float, z: float, label: str, up: float = 0.35) -> None:
        y = pz(z) - up
        s.dim((cx - width / 2, y), (cx + width / 2, y), label)
    hd(c["corners_top"], c["z_body_top"] - 1.6, f"{fmt(c['corners_top'])} across corners")
    hd(c["corners_bottom"], c["z_point_ring"] + 0.4, f"{fmt(c['corners_bottom'])} across corners")
    hd(sk["corners_bottom"], sk["z_bottom"] - 0.75, f"skirt {fmt(sk['corners_bottom'])} → {fmt(sk['corners_top'])}")
    hd(band["flats"], band["z_top"] + 0.05, f"band {fmt(band['flats'])} across flats", up=-0.05)
    hd(rim["flats"], rim["z_bottom"] - 0.05, f"rim {fmt(rim['flats'])}", up=-0.75)
    hd(dome["flats_top"], dome["z_top"] + 0.1, f"dome top {fmt(dome['flats_top'])}")
    hd(disc["flats"], disc["z_top"] + 0.15, f"disc {fmt(disc['flats'])}", up=0.0)
    hd(lp["outer_width"], lp["z_shoulder"] + 0.6, f"loop {fmt(lp['outer_width'])}")
    hd(lp["outer_top"], lp["z_top"] + 0.15, f"{fmt(lp['outer_top'])}", up=0.2)
    # the bar's width, on the loop's left leg
    xb = cx - lp["outer_width"] / 2
    yb = pz(lp["z_shoulder"]) + 0.45
    s.dim((xb, yb), (xb + lp["bar"], yb), "")
    s.text((xb - 0.25, yb + 0.2), f"bar {fmt(lp['bar'])}", anchor="end", size=0.5)


def side_dims(s: Sheet, d: dict) -> None:
    c, lp, band = d["crystal"], d["loop"], d["band"]
    v = "side"
    cx = X0[v] + ORTHO[v][0] / 2
    def pz(z: float) -> float:
        return project(v, (0, 0, z))[1]
    flats = c["corners_top"] * math.cos(math.radians(30.0))
    y = pz(c["z_body_top"] - 1.6) - 0.35
    s.dim((cx - flats / 2, y), (cx + flats / 2, y), f"{fmt(flats)} across flats")
    y = pz(lp["z_top"]) - 0.4
    s.dim((cx - lp["depth"] / 2, y), (cx + lp["depth"] / 2, y), f"loop depth {fmt(lp['depth'])}")
    y = pz(band["z_top"]) + 0.0
    s.dim((cx - band["flats"] / 2, y), (cx + band["flats"] / 2, y), f"{fmt(band['flats'])}")
    s.text((cx, pz(-0.3) + 1.1), "the crystal and the skirt show a corner here", cls="h", size=0.45)


def top_dims(s: Sheet, d: dict) -> None:
    band, disc, lp = d["band"], d["disc"], d["loop"]
    v = "top"
    cx, cy = project(v, (0, 0, 0))
    half = band["flats"] / 2
    s.dim((cx - half, cy + half + 0.9), (cx + half, cy + half + 0.9), f"band {fmt(band['flats'])} across flats",
          ext_from=[(cx - half, cy + half), (cx + half, cy + half)])
    s.dim((cx + half + 0.9, cy - half), (cx + half + 0.9, cy + half), fmt(band["flats"]),
          ext_from=[(cx + half, cy - half), (cx + half, cy + half)])
    s.dim((cx - disc["flats"] / 2, cy - half - 0.9), (cx + disc["flats"] / 2, cy - half - 0.9),
          f"disc {fmt(disc['flats'])}", ext_from=[(cx - disc["flats"] / 2, cy - disc["flats"] / 2),
                                                 (cx + disc["flats"] / 2, cy - disc["flats"] / 2)])
    s.text((cx, cy + half + 2.3), f"lens ⌀{fmt(disc['lens'])} · windows {fmt(band['window'][0])} × "
           f"{fmt(band['window'][1])} on the diagonal faces · loop {fmt(lp['outer_width'])} × {fmt(lp['depth'])}",
           cls="h", size=0.45)
    s.text((cx, cy + half + 3.0), "front ↓", cls="h", size=0.5)


def svg(feats: dict, d: dict, mode: str) -> str:
    s = Sheet()
    over = mode != "paper"
    style = STYLE["over" if over else "paper"]
    head = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH * 20:.0f}" '
            f'height="{HEIGHT * 20:.0f}" font-family="IBM Plex Mono, Consolas, monospace">',
            f"<style>{style} line{{stroke-linecap:round}} text{{paint-order:stroke;stroke:{'#0d1420' if over else '#f4f1e8'};"
            f"stroke-width:0.12;stroke-linejoin:round}}</style>",
            f'<rect class="bg" x="0" y="0" width="{WIDTH}" height="{HEIGHT}"/>']
    for view, (w, h, cx, cz) in ORTHO.items():
        x0, y0 = X0[view], TOP
        if over:
            href = UNDERLAY[mode].format(view=view)
            head.append(f'<image href="{href}" x="{x0}" y="{y0}" width="{w}" height="{h}" preserveAspectRatio="none"/>')
        head.append(f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="none" class="f" stroke-width="0.03"/>')
    s.out = head
    for view in ORTHO:
        edges(s, view, feats, d)
        x0 = X0[view]
        s.text((x0 + ORTHO[view][0] / 2, TOP - 0.55), view.upper(), cls="h", size=0.7)
    front_dims(s, d)
    side_dims(s, d)
    top_dims(s, d)
    s.text((1.0, 1.4), "ENERGY CRYSTAL · all sizes in cm · views at one scale (16 px per cm in the renders)",
           cls="h", anchor="start", size=0.75)
    s.text((1.0, 2.4), "from prime-game-design cartridge-v2/crystal-views.jpg; the numbers: tools/blender/"
           "crystal_dims.toml; the lines: the model's own edges", cls="h", anchor="start", size=0.48)
    s.out.append("</svg>")
    return "\n".join(s.out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("build", type=Path, help="crystal_build.py's --out folder (features.json, renders/)")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    out = args.out or args.build / "drawing"
    out.mkdir(parents=True, exist_ok=True)
    feats = json.loads((args.build / "features.json").read_text(encoding="utf-8"))
    d = tomllib.loads(DIMS_FILE.read_text(encoding="utf-8"))
    for mode, name in (("paper", "drawing.svg"), ("concept", "drawing_concept.svg"), ("model", "drawing_model.svg")):
        (out / name).write_text(svg(feats, d, mode), encoding="utf-8")
    print(f"CRYSTAL_DRAWING {out} edges {len(feats['edges'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
