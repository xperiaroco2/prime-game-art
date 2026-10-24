"""The start console's drawing (art#263's stations; the engineer, 2026-10-24: the console in cm). Plain Python, no
Blender: the front, side and top orthographic views of the model's own edges (features.json, written by
console_build.py before the chamfers: the folds and open edges of the pedestal, each with its faces' normals; an
edge is drawn when one of its faces looks at the viewer), the hologram's box (build.json) and the dimensions from
the numbers it was built from (console_dims.toml). The views' frames are console_build.py's ORTHO frames, so a view
lies exactly over its orthographic render (ortho_<view>.png) and over the concept's straight view cut and stretched
to the same frame (concept_<view>.png).

    $PYTHON_BIN tools/blender/console_drawing.py <build dir> [--out DIR]

Writes into DIR (default <build dir>/drawing): drawing.svg (ink on paper), drawing_concept.svg (over the concept's
views), drawing_model.svg (over the model's orthographic renders); the images are linked by relative path
(../renders/...), so the files stay beside the build.
"""
from __future__ import annotations

import argparse
import json
import math
import tomllib
from pathlib import Path

DIMS_FILE = Path(__file__).with_name("console_dims.toml")
# the views' frames in cm (console_build.py ORTHO): width, height, the frame's middle (u, h; the top view u, d)
ORTHO = {"front": (200.0, 190.0, 0.0, 90.0), "side": (200.0, 190.0, 0.0, 90.0), "top": (190.0, 190.0, 0.0, 0.0)}
TOP = 22.0                     # the title band over the views (cm)
X0 = {"front": 40.0, "side": 262.0, "top": 484.0}   # each frame's left edge on the sheet (cm)
WIDTH, HEIGHT = 690.0, 236.0
UNDERLAY = {"concept": "../renders/concept_{view}.png", "model": "../renders/ortho_{view}.png"}
STYLE = {
    "paper": (".bg{fill:#f4f1e8}.e{stroke:#1e2a36}.c{stroke:#1e6e96}.d{stroke:#9b3b16;fill:#9b3b16}"
              ".t{fill:#9b3b16}.h{fill:#1e2a36}.f{stroke:#b8b2a2}"),
    "over": (".bg{fill:#0d1420}.e{stroke:#ffd27a}.c{stroke:#7fe6ff}.d{stroke:#ff8a3c;fill:#ff8a3c}"
             ".t{fill:#ffb27a}.h{fill:#e8eef5}.f{stroke:#3a4658}"),
}
HIDDEN = {"front": {"core", "deck", "plates"}, "side": {"core", "deck", "plates"},
          "top": {"core", "bands", "body", "channels", "button_seat", "strips"}}


class Sheet:
    def __init__(self) -> None:
        self.out: list[str] = []

    def line(self, a, b, cls: str, w: float = 0.22, dash: str = "") -> None:
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.out.append(f'<line x1="{a[0]:.2f}" y1="{a[1]:.2f}" x2="{b[0]:.2f}" y2="{b[1]:.2f}" class="{cls}" '
                        f'stroke-width="{w}"{d}/>')

    def text(self, p, s: str, cls: str = "t", size: float = 3.4, anchor: str = "middle", rot: float = 0.0) -> None:
        tr = f' transform="rotate({rot:.1f} {p[0]:.2f} {p[1]:.2f})"' if rot else ""
        self.out.append(f'<text x="{p[0]:.2f}" y="{p[1]:.2f}" class="{cls}" font-size="{size}" '
                        f'text-anchor="{anchor}"{tr}>{s}</text>')

    def arrow(self, tip, toward) -> None:
        dx, dy = toward[0] - tip[0], toward[1] - tip[1]
        n = math.hypot(dx, dy) or 1.0
        ux, uy = dx / n, dy / n
        a, w = 2.2, 0.7
        pts = [tip, (tip[0] + ux * a - uy * w, tip[1] + uy * a + ux * w), (tip[0] + ux * a + uy * w, tip[1] + uy * a - ux * w)]
        self.out.append('<polygon points="' + " ".join(f"{x:.2f},{y:.2f}" for x, y in pts) + '" class="d" '
                        'stroke-width="0.05"/>')

    def dim(self, a, b, label: str, side: float = 0.0, ext_from=None) -> None:
        """A dimension from sheet point a to b, its label beside the line (side: the label's offset across it)."""
        if ext_from:
            for p, q in zip(ext_from, (a, b)):
                self.line(p, q, "d", 0.1)
        self.line(a, b, "d", 0.14)
        self.arrow(a, b)
        self.arrow(b, a)
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        if abs(b[0] - a[0]) < 1e-6:
            self.text((mx - 1.2 + side, my), label, rot=-90.0)
        else:
            self.text((mx, my - 1.2 + side), label)


def fmt(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def project(view: str, p) -> tuple:
    w, h, cx, cz = ORTHO[view]
    x0 = X0[view]
    if view == "front":
        return x0 + w / 2 + (p[0] - cx), TOP + (cz + h / 2) - p[2]
    if view == "side":  # from -X: the front (-Y) to the right
        return x0 + w / 2 + (-p[1] - cx), TOP + (cz + h / 2) - p[2]
    return x0 + w / 2 + (p[0] - cx), TOP + h / 2 - p[1] + cz


def faces_viewer(view: str, normal) -> bool:
    return {"front": -normal[1], "side": -normal[0], "top": normal[2]}[view] > 1e-4


def edges(sheet: Sheet, view: str, feats: dict) -> None:
    for part, a, b, normals in feats["edges"]:
        if part in HIDDEN[view]:
            continue
        if normals and not any(faces_viewer(view, n) for n in normals):
            continue
        sheet.line(project(view, a), project(view, b), "e", 0.16)


def holo_box(s: Sheet, view: str, box: list) -> None:
    (x0, y0, z0), (x1, y1, z1) = box
    corners = {"front": [(x0, 0, z0), (x1, 0, z0), (x1, 0, z1), (x0, 0, z1)],
               "side": [(0, y0, z0), (0, y1, z0), (0, y1, z1), (0, y0, z1)],
               "top": [(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)]}[view]
    pts = [project(view, c) for c in corners]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        s.line(a, b, "c", 0.18, "2 1.5")


def front_dims(s: Sheet, d: dict, holo: list) -> None:
    v = "front"
    pl, bo, ri, bt, st, ch, ho = (d[k] for k in ("plinth", "body", "rim", "button", "strips", "channels", "hologram"))
    pz = lambda z: project(v, (0, 0, z))[1]  # noqa: E731
    px = lambda x: project(v, (x, 0, 0))[0]  # noqa: E731
    x_l = X0[v] - 4.0
    stack = [(0.0, pl["h_top"], "plinth"), (pl["h_top"], bo["h0"], ""), (bo["h0"], bo["h1"], "body"),
             (bo["h1"], ri["h0"], ""), (ri["h0"], ri["h1"], "rim")]
    for z0, z1, name in stack:
        s.dim((x_l, pz(z0)), (x_l, pz(z1)), fmt(z1 - z0) if z1 - z0 > 5 else "")
        if name:
            s.text((x_l - 5.0, (pz(z0) + pz(z1)) / 2 + 1.0), name, cls="h", anchor="end", size=3.0)
        s.line((x_l - 1.0, pz(z0)), (px(-62.0), pz(z0)), "f", 0.08)
    s.line((x_l - 1.0, pz(ri["h1"])), (px(-62.0), pz(ri["h1"])), "f", 0.08)
    x_t = X0[v] - 22.0
    s.dim((x_t, pz(0.0)), (x_t, pz(ri["h1"])), f"{fmt(ri['h1'])} the rim's top")
    x_b = X0[v] + 14.0
    s.dim((x_b, pz(0.0)), (x_b, pz(bt["h"])), f"{fmt(bt['h'])} button")
    s.line((x_b, pz(bt["h"])), (px(-8.0), pz(bt["h"])), "d", 0.08)
    x_h = X0[v] + ORTHO[v][0] - 10.0
    s.dim((x_h, pz(0.0)), (x_h, pz(ho["disc_h"])), f"{fmt(ho['disc_h'])} the hologram's hall")
    s.line((x_h, pz(ho["disc_h"])), (px(0.0), pz(ho["disc_h"])), "c", 0.1, "1 1")

    def hd(width: float, z: float, label: str, up: float = 2.0) -> None:
        s.dim((px(-width / 2), pz(z) - up), (px(width / 2), pz(z) - up), label)
    hd(2 * pl["r_top"], -9.0, f"plinth ⌀ {fmt(2 * pl['r_top'])} ({fmt(2 * pl['r_bottom'])} at the floor)", up=0.0)
    hd(2 * bo["r_bottom"], bo["h0"] + 6.0, f"body ⌀ {fmt(2 * bo['r_bottom'])}", up=0.0)
    hd(2 * bo["r_top"], bo["h1"] - 8.0, f"⌀ {fmt(2 * bo['r_top'])}", up=0.0)
    hd(2 * ri["r"], ri["h_face1"], f"rim ⌀ {fmt(2 * ri['r'])}", up=-3.6)
    hd(2 * ri["r_top"], ri["h1"] + 3.0, f"⌀ {fmt(2 * ri['r_top'])}", up=0.0)
    (x0, _y0, _z0), (x1, _y1, z1) = holo
    s.dim((px(x0), pz(z1) - 3.0), (px(x1), pz(z1) - 3.0), f"hologram {fmt(x1 - x0)} span (the hull 1:16.3)")
    u0, u1 = st["u"][0][0], st["u"][-1][1]
    s.text((px(0.0), pz(st["h1"]) - 1.0), f"strips {fmt(st['h0'])}…{fmt(st['h1'])}", size=2.6)
    s.text((px((u0 + u1) / 2), pz(ch["h0"]) + 5.5), f"cyan strips u ±{fmt(ch['u'][0])}…{fmt(ch['u'][1])}, "
           f"h {fmt(ch['h0'])}…{fmt(ch['h1'])}", size=2.6)


def side_dims(s: Sheet, d: dict, holo: list) -> None:
    v = "side"
    bt, ho = d["button"], d["hologram"]
    pz = lambda z: project(v, (0, 0, z))[1]  # noqa: E731
    py = lambda y: project(v, (0, y, 0))[0]  # noqa: E731
    (_x0, y0, z0), (_x1, y1, z1) = holo
    s.dim((py(y1), pz(z1) - 3.0), (py(y0), pz(z1) - 3.0), f"hologram {fmt(y1 - y0)} long, nose down "
          f"{fmt(ho['tilt'])}° to the button")
    s.text((py(-60.0) + 2.0, pz(bt["h"]) - 9.0), f"button {fmt(bt['proud'])} proud, collar ⌀ {fmt(bt['collar'])}",
           anchor="start", size=2.8)
    s.text((py(0.0), pz(-9.0)), "the button →", cls="h", size=3.0)


def top_dims(s: Sheet, d: dict, holo: list) -> None:
    v = "top"
    e = d["emitter"]
    cx, cy = project(v, (0, 0, 0))
    r = e["ring"] / 2
    s.dim((cx - r, cy + 4.0), (cx + r, cy + 4.0), f"ring ⌀ {fmt(e['ring'])}")
    s.dim((cx - e["core"] / 2, cy - 4.0), (cx + e["core"] / 2, cy - 4.0), f"core ⌀ {fmt(e['core'])}")
    (x0, y0, _z0), (x1, y1, _z1) = holo
    s.text((cx, TOP + ORTHO[v][1] - 3.0), f"hologram {fmt(x1 - x0)} × {fmt(y1 - y0)} · the button ↓, toward the "
           "ship's mouth", cls="h", size=3.0)


def svg(feats: dict, build: dict, d: dict, mode: str) -> str:
    s = Sheet()
    over = mode != "paper"
    head = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH * 4:.0f}" '
            f'height="{HEIGHT * 4:.0f}" font-family="IBM Plex Mono, Consolas, monospace">',
            f"<style>{STYLE['over' if over else 'paper']} line{{stroke-linecap:round}} text{{paint-order:stroke;"
            f"stroke:{'#0d1420' if over else '#f4f1e8'};stroke-width:0.6;stroke-linejoin:round}}</style>",
            f'<rect class="bg" x="0" y="0" width="{WIDTH}" height="{HEIGHT}"/>']
    for view, (w, h, _cx, _cz) in ORTHO.items():
        x0 = X0[view]
        if over:
            head.append(f'<image href="{UNDERLAY[mode].format(view=view)}" x="{x0}" y="{TOP}" width="{w}" '
                        f'height="{h}" preserveAspectRatio="none" opacity="{0.85 if mode == "concept" else 1.0}"/>')
        head.append(f'<rect x="{x0}" y="{TOP}" width="{w}" height="{h}" fill="none" class="f" stroke-width="0.2"/>')
    s.out = head
    holo = build["hologram"]["bounds_cm"]
    for view in ORTHO:
        edges(s, view, feats)
        holo_box(s, view, holo)
        s.text((X0[view] + ORTHO[view][0] / 2, TOP - 3.0), view.upper(), cls="h", size=4.0)
    front_dims(s, d, holo)
    side_dims(s, d, holo)
    top_dims(s, d, holo)
    s.text((6.0, 8.0), "THE START CONSOLE · all sizes in cm · the three views at one scale (4 px per cm in the renders)",
           cls="h", anchor="start", size=4.6)
    s.text((6.0, 14.0), "the numbers: prime-game-design stations-final/console-drawing (drawing.js) → "
           "tools/blender/console_dims.toml; the lines: the model's own edges; dashed: the hologram's box",
           cls="h", anchor="start", size=3.0)
    s.out.append("</svg>")
    return "\n".join(s.out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("build", type=Path, help="console_build.py's --out folder (features.json, build.json, renders/)")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    out = args.out or args.build / "drawing"
    out.mkdir(parents=True, exist_ok=True)
    feats = json.loads((args.build / "features.json").read_text(encoding="utf-8"))
    build = json.loads((args.build / "build.json").read_text(encoding="utf-8"))
    d = tomllib.loads(DIMS_FILE.read_text(encoding="utf-8"))
    for mode, name in (("paper", "drawing.svg"), ("concept", "drawing_concept.svg"), ("model", "drawing_model.svg")):
        (out / name).write_text(svg(feats, build, d, mode), encoding="utf-8")
    print(f"CONSOLE_DRAWING {out} edges {len(feats['edges'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
