"""The crystal charger's drawing (art#263's stations). Plain Python, no Blender: the front, side and top orthographic
views of the model's own edges (features.json, written by charger_build.py before the bevels: the folds and open
edges, each with its faces' normals; an edge is drawn when one of its faces looks at the viewer) with the numbers it
was built from (charger_dims.toml, from prime-game-design a53ce6f charger-drawing/drawing.js). The views' frames are
charger_build.py's ORTHO frames, so each lies exactly over its orthographic render (renders/ortho_<view>.png): a
size that is wrong shows as a line off the picture.

    $PYTHON_BIN tools/blender/charger_drawing.py <build dir> [--out DIR]

Writes into DIR (default <build dir>/drawing): drawing.svg (ink on paper) and drawing_model.svg (over the renders,
linked by relative path ../renders/...).
"""
from __future__ import annotations

import argparse
import json
import math
import tomllib
from pathlib import Path

DIMS_FILE = Path(__file__).with_name("charger_dims.toml")
# charger_build.py ORTHO: frame (cm, square), its middle (front: u, h; side: d, h; top: u, d)
ORTHO = {"front": (160.0, 0.0, 75.0), "side": (160.0, 60.0, 75.0), "top": (160.0, 0.0, 55.0)}
TOP = 22.0
X0 = {"front": 40.0, "side": 222.0, "top": 404.0}
WIDTH, HEIGHT = 590.0, 206.0
STYLE = {
    "paper": ".bg{fill:#f4f1e8}.e{stroke:#1e2a36}.d{stroke:#9b3b16;fill:#9b3b16}.t{fill:#9b3b16}.h{fill:#1e2a36}"
             ".f{stroke:#b8b2a2}.w{stroke:#2f6f9b}",
    "over": ".bg{fill:#0d1420}.e{stroke:#ffd27a}.d{stroke:#ff8a3c;fill:#ff8a3c}.t{fill:#ffb27a}.h{fill:#e8eef5}"
            ".f{stroke:#3a4658}.w{stroke:#7fe6ff}",
}


def fmt(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


def project(view: str, p) -> tuple:
    """p: (u, d, h) cm -> the sheet's (x, y)."""
    size, cx, cy = ORTHO[view]
    x0 = X0[view]
    u, d, h = p
    if view == "front":
        return x0 + size / 2 + (u - cx), TOP + size / 2 - (h - cy)
    if view == "side":  # from -u: the wall on the left, the room to the right
        return x0 + size / 2 + (d - cx), TOP + size / 2 - (h - cy)
    return x0 + size / 2 + (u - cx), TOP + size / 2 + (d - cy)  # the wall at the top


def faces_viewer(view: str, n) -> bool:
    # Blender normals (x = u, y = -d, z = h)
    return {"front": -n[1], "side": -n[0], "top": n[2]}[view] > 1e-4


class Sheet:
    def __init__(self) -> None:
        self.out: list[str] = []

    def line(self, a, b, cls: str, w: float = 0.2, dash: str = "") -> None:
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.out.append(f'<line x1="{a[0]:.2f}" y1="{a[1]:.2f}" x2="{b[0]:.2f}" y2="{b[1]:.2f}" class="{cls}" '
                        f'stroke-width="{w}"{d}/>')

    def text(self, p, s: str, cls: str = "t", size: float = 3.0, anchor: str = "middle", rot: float = 0.0) -> None:
        tr = f' transform="rotate({rot:.1f} {p[0]:.2f} {p[1]:.2f})"' if rot else ""
        self.out.append(f'<text x="{p[0]:.2f}" y="{p[1]:.2f}" class="{cls}" font-size="{size}" '
                        f'text-anchor="{anchor}"{tr}>{s}</text>')

    def dim(self, a, b, label: str) -> None:
        self.line(a, b, "d", 0.14)
        for p in (a, b):
            self.out.append(f'<circle cx="{p[0]:.2f}" cy="{p[1]:.2f}" r="0.5" class="d"/>')
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        if abs(b[0] - a[0]) < 1e-6:
            self.text((mx - 1.2, my), label, rot=-90.0)
        else:
            self.text((mx, my - 1.2), label)


def svg(feats: dict, d: dict, mode: str) -> str:
    s = Sheet()
    over = mode == "model"
    s.out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH * 4:.0f}" '
             f'height="{HEIGHT * 4:.0f}" font-family="IBM Plex Mono, Consolas, monospace">',
             f"<style>{STYLE['over' if over else 'paper']} line{{stroke-linecap:round}} text{{paint-order:stroke;"
             f"stroke:{'#0d1420' if over else '#f4f1e8'};stroke-width:0.6}}</style>",
             f'<rect class="bg" x="0" y="0" width="{WIDTH}" height="{HEIGHT}"/>']
    for view, (size, _cx, _cy) in ORTHO.items():
        if over:
            s.out.append(f'<image href="../renders/ortho_{view}.png" x="{X0[view]}" y="{TOP}" width="{size}" '
                         f'height="{size}" preserveAspectRatio="none"/>')
        s.out.append(f'<rect x="{X0[view]}" y="{TOP}" width="{size}" height="{size}" fill="none" class="f" '
                     'stroke-width="0.2"/>')
        s.text((X0[view] + size / 2, TOP - 3.0), view.upper(), cls="h", size=4.0)
    for _part, a, b, normals in feats["edges"]:
        pa, pb = (a[0], -a[1], a[2]), (b[0], -b[1], b[2])
        for view in ORTHO:
            if normals and not any(faces_viewer(view, n) for n in normals):
                continue
            s.line(project(view, pa), project(view, pb), "e", 0.12)
    fr, t, b, lg = d["frame"], d["base"], d["button"], d["legs"]
    o, sl = d["outer"], d["slot"]
    # front: the heights on the left, the widths under
    pz = lambda h: project("front", (0, 0, h))[1]  # noqa: E731
    px = lambda u: project("front", (u, 0, 0))[0]  # noqa: E731
    x = X0["front"] + 4.0
    for h, label in ((t["bottom"], "base"), (t["widest"], "widest"), (t["lower_top"], ""), (t["deck"], "deck"),
                     (sl["collar_top"], "slot"), (fr["top"], "prongs")):
        s.dim((x, pz(0.0)), (x, pz(h)), f"{fmt(h)} {label}".strip())
        x += 3.6
    s.dim((px(-t["r_widest"]), pz(t["widest"]) + 2.0), (px(t["r_widest"]), pz(t["widest"]) + 2.0),
          f"⌀ {fmt(2 * t['r_widest'])}")
    s.dim((px(-t["r_upper"]), pz(t["lower_top"]) - 1.5), (px(t["r_upper"]), pz(t["lower_top"]) - 1.5),
          f"⌀ {fmt(2 * t['r_upper'])}")
    s.dim((px(70.0), pz(0.0)), (px(70.0), pz(b["h"])), f"{fmt(b['h'])} button")
    cu = math.cos(math.radians(o["half_deg"]))
    s.dim((px(-o["root"][0][0] * cu), pz(fr["top"]) - 3.0), (px(o["root"][0][0] * cu), pz(fr["top"]) - 3.0),
          f"{fmt(2 * o['root'][0][0] * cu)} between the outer prongs")
    # side: the wall, the axis, the depth
    py = lambda dd: project("side", (0, dd, 0))[0]  # noqa: E731
    sz = lambda h: project("side", (0, 0, h))[1]  # noqa: E731
    s.line((py(0.0), sz(-2.0)), (py(0.0), sz(150.0)), "w", 0.3)
    s.line((py(fr["axis_d"]), sz(-2.0)), (py(fr["axis_d"]), sz(fr["top"] + 4.0)), "w", 0.15, "2 1")
    s.dim((py(0.0), sz(fr["top"]) - 2.0), (py(fr["axis_d"]), sz(fr["top"]) - 2.0), f"axis {fmt(fr['axis_d'])}")
    front = fr["axis_d"] + t["r_widest"]
    s.dim((py(0.0), sz(0.0) + 4.0), (py(front), sz(0.0) + 4.0), f"{fmt(front)} to the base's front")
    s.text((py(1.0), sz(146.0)), "wall", cls="h", anchor="start", size=2.8)
    # top: the two wall facets at the spot's vertex, the legs' pads
    f = math.radians(fr["back_fold_deg"])
    for sx in (-1.0, 1.0):
        a = project("top", (0.0, 0.0, 0.0))
        b2 = project("top", (sx * 75.0, 75.0 * math.tan(f), 0.0))
        s.line(a, b2, "w", 0.3)
    for k, ang in enumerate(lg["angles"]):
        r = lg["pad_s"][k]
        p = project("top", (r * math.sin(math.radians(ang)), fr["axis_d"] + r * math.cos(math.radians(ang)), 0.0))
        s.text((p[0], p[1] + 1.0), f"pad {fmt(ang)}° r {fmt(r)}", size=2.4)
    s.text(project("top", (0.0, -3.0, 0.0)), f"the lens room's wall: two facets, {fmt(fr['back_fold_deg'])}° each "
           "side of the spot's vertex", cls="h", size=2.6)
    s.text((6.0, 8.0), "THE CRYSTAL CHARGER · cm · three views at one scale (4 px per cm in the renders)", cls="h",
           anchor="start", size=4.4)
    s.text((6.0, 14.0), "numbers: prime-game-design a53ce6f charger-drawing/drawing.js → tools/blender/"
           "charger_dims.toml; lines: the model's own edges", cls="h", anchor="start", size=2.8)
    s.out.append("</svg>")
    return "\n".join(s.out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("build", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    out = args.out or args.build / "drawing"
    out.mkdir(parents=True, exist_ok=True)
    feats = json.loads((args.build / "features.json").read_text(encoding="utf-8"))
    d = tomllib.loads(DIMS_FILE.read_text(encoding="utf-8"))
    for mode, name in (("paper", "drawing.svg"), ("model", "drawing_model.svg")):
        (out / name).write_text(svg(feats, d, mode), encoding="utf-8", newline="\n")
    print(f"CHARGER_DRAWING {out} edges {len(feats['edges'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
