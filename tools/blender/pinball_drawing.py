"""The lobby's pinball machine's drawing (art #374, Gate 1), as the energy crystal's (crystal_drawing.py). Plain
Python, no Blender: the front, side and top orthographic views of the model's own feature edges (features.json,
written by pinball_build.py before the chamfers, in the cabinet frame in cm, each edge with its faces' normals; an
edge is drawn when one of its faces looks at the viewer) and the dimensions from the numbers it was built from
(pinball_dims.toml). The views' frames are pinball_build.py's ORTHO frames (build.json), so a view lies exactly over
its orthographic render (renders/ortho_<view>.png).

    $PYTHON_BIN tools/blender/pinball_drawing.py <build dir> [--out DIR]

Writes into DIR (default <build dir>/drawing): drawing.svg (ink on paper), drawing_model.svg (over the model's
orthographic renders, embedded) and drawing_concept.svg (the drawing beside the concept: the concept is one 3/4
perspective picture with no straight views, so nothing can lie over it exactly; the 3/4 shot beside it is in the
Godot sheet). Views: front from the player (h = -x, v = y), side from +x (h = -z: the player on the right), top
(h = -x, v = z: the player at the bottom).
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import tomllib
from pathlib import Path

DIMS_FILE = Path(__file__).with_name("pinball_dims.toml")
TOP = 30.0                                           # the title band (cm on the sheet)
GAP = 45.0                                           # between the views, room for the dimensions
STYLE = {
    "paper": (".bg{fill:#f4f1e8}.e{stroke:#1e2a36}.d{stroke:#9b3b16;fill:#9b3b16}.t{fill:#9b3b16}.h{fill:#1e2a36}"
              ".f{stroke:#b8b2a2}.m{stroke:#1f7f8f;fill:#1f7f8f}"),
    "over": (".bg{fill:#0d1420}.e{stroke:#ffd27a}.d{stroke:#ff8a3c;fill:#ff8a3c}.t{fill:#ffb27a}.h{fill:#e8eef5}"
             ".f{stroke:#3a4658}.m{stroke:#7fe6ff;fill:#7fe6ff}"),
}


def fmt(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


class Sheet:
    def __init__(self, ortho: dict) -> None:
        self.out: list[str] = []
        self.ortho = ortho
        self.x0 = {}
        x = GAP
        for view in ("front", "side", "top"):
            self.x0[view] = x
            x += ortho[view][0] + GAP
        self.width = x
        self.height = TOP + max(o[1] for o in ortho.values()) + 25.0

    def p(self, view: str, q) -> tuple:
        """A cabinet-frame point (cm) on the sheet."""
        w, h, ch, cv = self.ortho[view]
        hv = {"front": (-q[0], q[1]), "side": (-q[2], q[1]), "top": (-q[0], q[2])}[view]
        return self.x0[view] + w / 2 + (hv[0] - ch), TOP + h / 2 - (hv[1] - cv)

    def line(self, a, b, cls: str = "e", w: float = 0.25) -> None:
        self.out.append(f'<line x1="{a[0]:.2f}" y1="{a[1]:.2f}" x2="{b[0]:.2f}" y2="{b[1]:.2f}" class="{cls}" '
                        f'stroke-width="{w}"/>')

    def text(self, p, s: str, cls: str = "t", size: float = 3.6, anchor: str = "middle", rot: float = 0.0) -> None:
        tr = f' transform="rotate({rot:.1f} {p[0]:.2f} {p[1]:.2f})"' if rot else ""
        self.out.append(f'<text x="{p[0]:.2f}" y="{p[1]:.2f}" class="{cls}" font-size="{size}" '
                        f'text-anchor="{anchor}"{tr}>{s}</text>')

    def dim(self, a, b, label: str, off: float = 0.0) -> None:
        self.line(a, b, "d", 0.2)
        for tip, other in ((a, b), (b, a)):
            dx, dy = other[0] - tip[0], other[1] - tip[1]
            n = math.hypot(dx, dy) or 1.0
            ux, uy = dx / n, dy / n
            pts = [tip, (tip[0] + ux * 2.4 - uy * 0.8, tip[1] + uy * 2.4 + ux * 0.8),
                   (tip[0] + ux * 2.4 + uy * 0.8, tip[1] + uy * 2.4 - ux * 0.8)]
            self.out.append('<polygon class="d" points="' + " ".join(f"{x:.2f},{y:.2f}" for x, y in pts) + '"/>')
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        if abs(b[0] - a[0]) < 1e-6:
            self.text((mx - 1.4 + off, my), label, rot=-90.0)
        else:
            self.text((mx, my - 1.3 + off), label)


def faces_viewer(view: str, n) -> bool:
    return {"front": -n[2], "side": n[0], "top": n[1]}[view] > 1e-3


def edges(s: Sheet, feats: list) -> None:
    for view in ("front", "side", "top"):
        for a, b, normals in feats:
            if normals and not any(faces_viewer(view, n) for n in normals):
                continue
            s.line(s.p(view, a), s.p(view, b), "e", 0.18)


def dims(s: Sheet, d: dict, build: dict) -> None:
    k, t, b, bb, mk, pl = (d[x] for x in ("contract", "table", "body", "backbox", "markers", "placement"))
    tilt = math.radians(t["tilt_deg"])
    h_c = t["front_y"] + k["field"][1] / 2 * math.sin(tilt)
    z_c = t["field_z"]
    def tfp(x: float, y: float, z: float) -> tuple:   # the table frame (cm) -> the cabinet frame (cm)
        return (-x, h_c + y * math.cos(tilt) - z * math.sin(tilt), z_c - y * math.sin(tilt) - z * math.cos(tilt))
    cb = build["cabinet"]["bounds_cm"]
    # front: the overall height, the width, the field's front edge height, the screen
    v = "front"
    xl = s.p(v, (cb["max"][0], 0, 0))[0] - 10.0
    s.dim((xl, s.p(v, (0, 0, 0))[1]), (xl, s.p(v, (0, bb["y"][1], 0))[1]), f"{fmt(bb['y'][1])} overall")
    s.dim((xl + 6, s.p(v, (0, 0, 0))[1]), (xl + 6, s.p(v, (0, t["front_y"], 0))[1]), f"field front {fmt(t['front_y'])}")
    y = s.p(v, (0, bb["y"][1], 0))[1] - 6.0
    s.dim((s.p(v, (b["outer_w"] / 2, 0, 0))[0], y), (s.p(v, (-b["outer_w"] / 2, 0, 0))[0], y), f"{fmt(b['outer_w'])}")
    sw, sh = bb["screen"]
    y = s.p(v, (0, bb["screen_y"] + sh / 2, 0))[1] - 3.0
    s.dim((s.p(v, (sw / 2, 0, 0))[0], y), (s.p(v, (-sw / 2, 0, 0))[0], y), f"screen {fmt(sw)}")
    x = s.p(v, (-sw / 2, 0, 0))[0] + 4.0
    s.dim((x, s.p(v, (0, bb["screen_y"] - sh / 2, 0))[1]), (x, s.p(v, (0, bb["screen_y"] + sh / 2, 0))[1]), fmt(sh))
    y = s.p(v, (0, -6.0, 0))[1]
    s.dim((s.p(v, (cb["max"][0], 0, 0))[0], y), (s.p(v, (cb["min"][0], 0, 0))[0], y),
          f"{fmt(cb['max'][0] - cb['min'][0])} at the feet", off=8.0)
    # side: the depth, the tilt, the field's far end, the backbox, CloseUp and the player's spot
    v = "side"
    front, far = tfp(0, 0, k["field"][1] / 2), tfp(0, 0, -k["field"][1] / 2)
    s.line(s.p(v, front), s.p(v, far), "m", 0.35)
    s.text(s.p(v, tfp(0, 4, 10)), f"field {fmt(k['field'][1])} long, {fmt(t['tilt_deg'])}° (far end up)", "h", 3.2)
    xf = s.p(v, far)[0] - 4.0
    s.dim((xf, s.p(v, (0, 0, 0))[1]), (xf, s.p(v, far)[1]), f"far end {fmt(far[1])}")
    y = s.p(v, (0, 0, 0))[1] + 10.0
    s.dim((s.p(v, (0, 0, cb["min"][2]))[0], y), (s.p(v, (0, 0, cb["max"][2]))[0], y),
          f"{fmt(cb['max'][2] - cb['min'][2])} deep")
    y = s.p(v, (0, bb["y"][1], 0))[1] - 4.0
    s.dim((s.p(v, (0, 0, bb["z"][0]))[0], y), (s.p(v, (0, 0, bb["z"][1]))[0], y), fmt(bb["z"][1] - bb["z"][0]))
    xb = s.p(v, (0, 0, bb["z"][1]))[0] - 5.0
    s.dim((xb, s.p(v, (0, bb["y"][0], 0))[1]), (xb, s.p(v, (0, bb["y"][1], 0))[1]), fmt(bb["y"][1] - bb["y"][0]))
    tm = (0, h_c, z_c)
    a = math.radians(mk["closeup_down_deg"])
    cam = (0, h_c + mk["closeup_dist"] * math.sin(a), z_c - mk["closeup_dist"] * math.cos(a))
    s.line(s.p(v, tm), s.p(v, cam), "m", 0.3)
    s.text(s.p(v, (0, cam[1] + 4, cam[2])), f"CloseUp {fmt(mk['closeup_dist'])} at {fmt(mk['closeup_down_deg'])}°",
           "h", 3.0)
    s.text(s.p(v, (0, h_c + 5, z_c)), "TableMount", "h", 3.0)
    spot = pl["spot"][2] - pl["origin"][2]
    s.line(s.p(v, (0, 0, spot)), s.p(v, (0, 165, spot)), "m", 0.3)
    s.text(s.p(v, (0, 170, spot)), f"player {fmt(cb['min'][2] - spot)} from the front", "h", 3.0)
    s.text(s.p(v, (0, bb["screen_y"], bb["z"][0] - 3)), "Display", "h", 3.0, anchor="start")
    # top: the contract's field and its bodies (the model's lines), the outer width and length
    v = "top"
    corners = [tfp(sx * k["field"][0] / 2, 0, sz * k["field"][1] / 2) for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    for i in range(4):
        s.line(s.p(v, corners[i]), s.p(v, corners[(i + 1) % 4]), "m", 0.35)
    y = s.p(v, corners[2])[1] + 6.0
    s.dim((s.p(v, corners[2])[0], y), (s.p(v, corners[3])[0], y), f"field {fmt(k['field'][0])}")
    x = s.p(v, (cb["min"][0], 0, 0))[0] + 6.0
    s.dim((x, s.p(v, corners[2])[1]), (x, s.p(v, corners[1])[1]), f"{fmt(k['field'][1] * math.cos(tilt))} (130 tilted)")
    s.text((s.p(v, (0, 0, cb["min"][2]))[0], s.p(v, (0, 0, cb["min"][2]))[1] + 14.0), "player ↓", "h", 3.4)


def svg(feats: list, d: dict, build: dict, mode: str, folder: Path, concept: Path) -> str:
    s = Sheet({k: tuple(v) for k, v in build["ortho"].items()})
    extra = 330.0 if mode == "concept" else 0.0
    over = mode == "model"
    head = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {s.width + extra:.0f} {s.height:.0f}" '
            f'width="{(s.width + extra) * 4:.0f}" height="{s.height * 4:.0f}" font-family="Consolas, monospace">',
            f"<style>{STYLE['over' if over else 'paper']} line{{stroke-linecap:round}}</style>",
            f'<rect class="bg" x="0" y="0" width="{s.width + extra:.0f}" height="{s.height:.0f}"/>']
    for view, (w, h, _ch, _cv) in s.ortho.items():
        x0 = s.x0[view]
        if over:
            data = base64.b64encode((folder / "renders" / f"ortho_{view}.png").read_bytes()).decode()
            head.append(f'<image href="data:image/png;base64,{data}" x="{x0}" y="{TOP}" width="{w}" height="{h}" '
                        'preserveAspectRatio="none"/>')
        head.append(f'<rect x="{x0}" y="{TOP}" width="{w}" height="{h}" fill="none" class="f" stroke-width="0.3"/>')
        head.append(f'<text x="{x0 + w / 2}" y="{TOP - 4}" class="h" font-size="5" text-anchor="middle">'
                    f'{view.upper()}</text>')
    if mode == "concept" and concept.is_file():
        data = base64.b64encode(concept.read_bytes()).decode()
        head.append(f'<image href="data:image/png;base64,{data}" x="{s.width}" y="{TOP}" width="300" height="200"/>')
        head.append(f'<text x="{s.width + 150}" y="{TOP - 4}" class="h" font-size="5" text-anchor="middle">CONCEPT '
                    '(3/4, no straight views)</text>')
    s.out = head
    edges(s, feats)
    dims(s, d, build)
    s.text((GAP, 10.0), "PINBALL MACHINE · all sizes in cm · cabinet frame: the player at -z, the backbox at +z",
           "h", 5.0, anchor="start")
    s.text((GAP, 18.0), "numbers: tools/blender/pinball_dims.toml (the concept fitted to the contract's 72 × 130 field); "
           "lines: the model's own edges; teal: the contract's field, TableMount, CloseUp, the player", "h", 3.2,
           anchor="start")
    s.out.append("</svg>")
    return "\n".join(s.out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("build", type=Path, help="pinball_build.py's --out folder (build.json, features.json, renders/)")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    out = args.out or args.build / "drawing"
    out.mkdir(parents=True, exist_ok=True)
    feats = json.loads((args.build / "features.json").read_text(encoding="utf-8"))
    build = json.loads((args.build / "build.json").read_text(encoding="utf-8"))
    d = tomllib.loads(DIMS_FILE.read_text(encoding="utf-8"))
    concept = args.build.parent / "ref" / "concept_p2.png"
    for mode, name in (("paper", "drawing.svg"), ("model", "drawing_model.svg"), ("concept", "drawing_concept.svg")):
        (out / name).write_text(svg(feats, d, build, mode, args.build, concept), encoding="utf-8", newline="\n")
    print(f"PINBALL_DRAWING {out} edges {len(feats)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
