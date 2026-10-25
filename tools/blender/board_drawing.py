"""The breaker board's drawing check (art#263's stations). Plain Python, no Blender: the built numbers (build.json's
measured_cm, read off the model's own vertices by board_build.py) against the drawing's (prime-game-design 6b0e83e,
stations-final/board-drawing/drawing.js, its N and D objects, copied below), and the front and side views in cm: the
picked sheet's straight views at the drawing's scale (board_dims.toml [measure]), the drawing's boxes (cyan, dashed)
and the built model's boxes (orange) over them, so a mismatch shows as two outlines apart. board_build.py's
drawing_front.png and drawing_side.png show the whole model the same way (its ink and outlines over the views).

    $PYTHON_BIN tools/blender/board_drawing.py <build dir> [--out DIR]

Writes into DIR (default <build dir>/drawing): compare.json (every number: drawing, built, delta) and drawing.svg
(the images linked by relative path, ../../ref/...); prints each number off by more than TOLERANCE_CM.
"""
from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path

DIMS = tomllib.loads(Path(__file__).with_name("board_dims.toml").read_text(encoding="utf-8"))
TOLERANCE_CM = 0.5
# drawing.js's numbers (node drawing.js at prime-game-design 6b0e83e), the ones the build is held to
DRAWING = {
    "width": 160.0, "frame_h0": 52.0, "frame_h1": 131.4, "beacon_top": 140.4, "depth_on": 31.0,
    "trip_out": 60.9, "trip_low": 53.9, "hinge_h": 67.7, "hinge_d": 25.0, "shell_w": 20.4, "shell_top": 104.9,
    "core_w": 10.3, "core_h0": 78.5, "core_h1": 95.9, "core_d": 18.0, "lamp_h": 114.6, "lamp_ring": 9.7,
    "lamp_front_d": 30.0, "cable_low": 17.8, "u0": -50.4, "u1": -16.8, "u2": 16.8, "u3": 50.4,
}
REF = "../../ref/{view}-ortho.jpg"
IMG_W, IMG_H = 1536, 1024


def built(m: dict) -> dict:
    """The same keys from the model's measured bounds."""
    sh, core, lamp = m["shells"], m["cores"], m["lamps"]
    out = {
        "width": m["frame"]["u"][1] - m["frame"]["u"][0], "frame_h0": m["frame"]["h"][0],
        "frame_h1": m["frame"]["h"][1], "beacon_top": m["beacon"]["h"][1], "depth_on": m["all_closed"]["d"][1],
        "trip_out": m["shell_tripped"]["d"][1], "trip_low": m["shell_tripped"]["h"][0], "hinge_h": m["hinges"][0][2],
        "hinge_d": m["hinges"][0][1], "shell_w": sh[0]["u"][1] - sh[0]["u"][0], "shell_top": sh[0]["h"][1],
        "core_w": core[0]["u"][1] - core[0]["u"][0], "core_h0": core[0]["h"][0], "core_h1": core[0]["h"][1],
        "core_d": (core[0]["d"][0] + core[0]["d"][1]) / 2, "lamp_h": (lamp[0]["h"][0] + lamp[0]["h"][1]) / 2,
        "lamp_ring": DIMS["lamp"]["ring_r"] * 2, "lamp_front_d": lamp[0]["d"][1], "cable_low": m["cable_low_h"],
    }
    for i, s in enumerate(sh):
        out[f"u{i}"] = (s["u"][0] + s["u"][1]) / 2
    return {k: round(v, 2) for k, v in out.items()}


def rect(x0, y0, x1, y1, cls: str) -> str:
    return (f'<rect x="{min(x0, x1):.2f}" y="{min(y0, y1):.2f}" width="{abs(x1 - x0):.2f}" '
            f'height="{abs(y1 - y0):.2f}" class="{cls}"/>')


def view(name: str, m: dict, x_off: float) -> str:
    """One view in cm: x across the sheet, y down (y = 160 - h). Front: x = u; side: x = -d (the corridor left)."""
    fr = DIMS["measure"]
    if name == "front":
        k = (fr["front"]["x1"] - fr["front"]["x0"]) / DIMS["frame"]["width"]
        cx = (fr["front"]["x0"] + fr["front"]["x1"]) / 2
        img_x, img_y = -cx / k, 160 - (DIMS["frame"]["h0"] + fr["front"]["bot"] / k)
        X = (lambda b: (b["u"][0], b["u"][1]))  # noqa: E731
    else:
        k = (fr["side"]["bot"] - fr["side"]["top"]) / (DIMS["frame"]["h1"] - DIMS["frame"]["h0"])
        img_x, img_y = -fr["side"]["wall"] / k, 160 - (DIMS["frame"]["h0"] + fr["side"]["bot"] / k)
        X = (lambda b: (-b["d"][1], -b["d"][0]))  # noqa: E731
    o = [f'<g transform="translate({x_off} 0)">',
         f'<image href="{REF.format(view=name)}" x="{img_x:.2f}" y="{img_y:.2f}" width="{IMG_W / k:.2f}" '
         f'height="{IMG_H / k:.2f}" opacity="0.85"/>']
    boxes = [m["body"], m["beacon"], *m["shells"], *m["cores"], *m["lamps"], m["shell_tripped"]]
    for b in boxes:
        x0, x1 = X(b)
        o.append(rect(x0, 160 - b["h"][0], x1, 160 - b["h"][1], "built"))
    d = DRAWING
    if name == "front":
        o.append(rect(-80, 160 - d["frame_h0"], 80, 160 - d["frame_h1"], "drawn"))
        for i in range(4):
            u = d[f"u{i}"]
            o.append(rect(u - d["shell_w"] / 2, 160 - d["hinge_h"], u + d["shell_w"] / 2, 160 - d["shell_top"], "drawn"))
            o.append(rect(u - d["core_w"] / 2, 160 - d["core_h0"], u + d["core_w"] / 2, 160 - d["core_h1"], "drawn"))
    else:
        o.append(rect(0, 160 - d["frame_h0"], -21, 160 - d["frame_h1"], "drawn"))
        o.append(rect(-22, 160 - d["hinge_h"], -d["depth_on"], 160 - d["shell_top"], "drawn"))
        o.append(rect(-25, 160 - d["trip_low"], -d["trip_out"], 160 - d["hinge_h"], "drawn"))
    o.append(f'<text x="0" y="8" class="t">{name}</text></g>')
    return "".join(o)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("build", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    out = a.out or a.build / "drawing"
    out.mkdir(parents=True, exist_ok=True)
    m = json.loads((a.build / "build.json").read_text(encoding="utf-8"))["measured_cm"]
    b = built(m)
    rows = {k: {"drawing": DRAWING[k], "built": b[k], "delta": round(b[k] - DRAWING[k], 2)} for k in DRAWING}
    (out / "compare.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8", newline="\n")
    off = [k for k, r in rows.items() if abs(r["delta"]) > TOLERANCE_CM]
    for k in off:
        print(f"BOARD drawing mismatch {k}: drawing {rows[k]['drawing']} built {rows[k]['built']}", flush=True)
    print(f"BOARD drawing: {len(rows) - len(off)}/{len(rows)} numbers within {TOLERANCE_CM} cm", flush=True)
    table = "".join(f'<text x="10" y="{180 + i * 4.2:.1f}" class="r">{k}: drawing {r["drawing"]}, built {r["built"]}'
                    f'{" (off)" if k in off else ""}</text>' for i, (k, r) in enumerate(rows.items()))
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="-110 0 340 280" width="1700" height="1400">'
           '<style>.built{fill:none;stroke:#ff8a3c;stroke-width:0.35}.drawn{fill:none;stroke:#7fe6ff;'
           'stroke-width:0.35;stroke-dasharray:1.2 0.8}.t{fill:#fff;font:4px sans-serif}.r{fill:#222;'
           'font:3px monospace}</style><rect x="-110" y="0" width="340" height="280" fill="#f4f1e8"/>'
           + view("front", m, 0.0) + view("side", m, 175.0) + table + "</svg>")
    (out / "drawing.svg").write_text(svg, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
