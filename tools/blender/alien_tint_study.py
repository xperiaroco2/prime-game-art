"""The static premium heads' skin colour study (art #196, 2026-10-23): where the player-chosen skin colour goes.
Today one colour recolours the whole tint mask (lips, gills and crest included), so a coral or lavender head is one
hue top to bottom. Plain Python, outside Blender: `masks` makes each head's accent mask in headless Blender
(alien_tint_mask.py: lips, marks, front panel), `sheets` writes a job and renders it in an off-screen Godot window
(godot/alien/tint_study.gd, the study shader godot/alien/tint_study.gdshader). The variants, each a parameter set:
- A today's tint: everything follows the skin;
- B1, B2 the lips keep one fixed natural colour (a warm dusty rose, a deep muted teal-grey), the rest follows;
- C the lips a deeper, less saturated, slightly warmer shade of the chosen skin;
- D skin and accent as a designed pair: the lips and the marks (gills, freckles, crest stripes) take the accent;
- E curated palettes only: skin, accent and front panel designed together, saturation capped (E1 the alien teal).
Two lights: the static heads' studio (static_alive.gd's stage, AgX 0.65 + saturation 1.35) and a dusk forest (a low
warm key, a cool blue sky fill, a dim green bounce). Sheets (JPG, 1280 px wide, every cell labelled) into --out.
One run can pass 180 s: in the background, its log in a file.

    $PYTHON_BIN tools/blender/alien_tint_study.py <masks|sheets|all> [--build DIR] [--out DIR]
"""
from __future__ import annotations

import argparse
import colorsys
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runner import blender, common  # noqa: E402
from runner.commands import _godot  # noqa: E402
import alien_static_review as R  # noqa: E402  (the static heads' framings, levers and staging)

RAW = common.raw_dir()
BUILD = R.NEW  # static_v5
OUT = R.DESIGN / "pilot3d" / "colour"
V2D = RAW / "2026-10-22-alien-pilot-3d" / "views"
HEADS = ["axolotl", "chameleon"]
WINDOW = (1000, 1000)

# the player's skin choices: the build's own teal first, then alien_static.gd's PALETTE (sRGB)
SKINS = [("teal", None), ("coral", (0.93, 0.55, 0.56)), ("lavender", (0.64, 0.56, 0.92)),
         ("sunflower", (0.98, 0.78, 0.30)), ("cobalt", (0.30, 0.50, 0.90))]
LIP_FIXED = {"B1": ("dusty rose", "#c48a8c"), "B2": ("teal-grey", "#4f6d70")}
# D: skin (the same five) + an accent designed for it: analogous-deep or soft complementary, never neon
PAIRS = {"teal": "#d98a7e", "coral": "#3f7c80", "lavender": "#7a4f86", "sunflower": "#b2603e", "cobalt": "#e0a07e"}
# E: curated skin / accent / front panel (sRGB hex); saturation capped by CAP on top
PALETTES = [("alien teal", None, None, None), ("coral reef", "#e39c8c", "#a2575a", "#f5e2d8"),
            ("lilac", "#a99cd8", "#6c5896", "#ebe5f5"), ("honey", "#e2c07a", "#a9623f", "#f6eedb"),
            ("cobalt", "#6c87c6", "#d48c72", "#e2e8f5"), ("sage", "#8fb99f", "#4e7a65", "#e7f1e5"),
            ("plum", "#a07596", "#5c3a5a", "#efe0ea"), ("slate", "#7f98a8", "#c98a7e", "#e5ebee")]
CAP = {"skin": 0.48, "accent": 0.52, "front": 0.16}  # HSV saturation (sRGB)
LIGHTS = {"studio": "studio (static heads, AgX 0.65 + sat 1.35)",
          "dusk": "dusk forest (low warm key, blue sky fill, green bounce)"}


def hexc(h: str) -> tuple:
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5))


def recolour(c, base, target) -> tuple:
    """The shader's recolour_to on one colour (hue shift, saturation and value ratios), in sRGB."""
    h, s, v = colorsys.rgb_to_hsv(*c)
    bh, bs, bv = colorsys.rgb_to_hsv(*base)
    th, ts, tv = colorsys.rgb_to_hsv(*target)
    return colorsys.hsv_to_rgb((h + th - bh) % 1.0, min(1.0, s * ts / max(bs, 1e-4)), min(1.0, v * tv / max(bv, 1e-4)))


def cap(c, s_max: float) -> tuple:
    h, s, v = colorsys.rgb_to_hsv(*c)
    return colorsys.hsv_to_rgb(h, min(s, s_max), v)


def deeper(c) -> tuple:
    """C: a deeper, less saturated, slightly warmer shade: value x0.74, saturation x0.72, the hue 0.035 turns toward
    red-orange (0.03)."""
    h, s, v = colorsys.rgb_to_hsv(*c)
    d = ((0.03 - h + 0.5) % 1.0) - 0.5
    h = (h + max(-0.035, min(0.035, d))) % 1.0
    return colorsys.hsv_to_rgb(h, s * 0.72, v * 0.74)


def variant(name: str, i: int, reg: dict) -> tuple[str, dict]:
    """The label and shader parameters of variant name's i-th colour on a head (reg: the accent JSON's medians)."""
    base = tuple(reg["skin"])
    lip, mark, front = tuple(reg["lips"]), tuple(reg["marks"]), tuple(reg["front"])
    if name == "E":
        label, skin_h, acc_h, front_h = PALETTES[i]
        if skin_h is None:  # E1: the build's own colours, untouched
            skin, lip_t, mark_t, front_t = base, lip, mark, front
        else:
            skin, acc = cap(hexc(skin_h), CAP["skin"]), cap(hexc(acc_h), CAP["accent"])
            lip_t, mark_t, front_t = acc, acc, cap(hexc(front_h), CAP["front"])
        params = {"skin_color": skin, "lip_base": lip, "lip_color": lip_t, "mark_base": mark, "mark_color": mark_t,
                  "front_base": front, "front_color": front_t}
        if skin_h is not None:
            params["front_sat_max"] = round(CAP["front"] * 1.4, 4)
    else:
        label, s = SKINS[i]
        skin = base if s is None else s
        params = {"skin_color": skin, "lip_base": base, "lip_color": skin, "mark_base": base, "mark_color": skin,
                  "front_base": base, "front_color": skin}  # A: every region follows the skin
        if name in LIP_FIXED:
            params.update(lip_base=lip, lip_color=hexc(LIP_FIXED[name][1]))
        elif name == "C":
            params.update(lip_base=lip, lip_color=deeper(recolour(lip, base, skin)))
        elif name == "D":
            acc = hexc(PAIRS[label])
            params.update(lip_base=lip, lip_color=acc, mark_base=mark, mark_color=acc)
            label = f"{label} + accent"
    return label, {k: [round(x, 4) for x in v] if isinstance(v, tuple) else v for k, v in params.items()}


TITLES = {"A": "A  today: everything follows the skin colour",
          "B1": "B1  lips fixed warm dusty rose, the rest follows the skin",
          "B2": "B2  lips fixed deep muted teal-grey, the rest follows the skin",
          "C": "C  lips a deeper, less saturated, warmer shade of the skin",
          "D": "D  skin + a designed accent (lips, gills, freckles, crest stripes)",
          "E": "E  curated palettes: skin / accent / front, saturation capped"}


def regions(out: Path, head: str) -> dict:
    rep = json.loads((out / "maps" / f"{head}_accent.json").read_text(encoding="utf-8"))
    return {k: v["srgb"] for k, v in rep["regions"].items()}


def shots(head: str) -> dict:
    """The face, wider than the static review's close-up so the gills and the crest show."""
    face = R.features(head)["face"]
    w = face["width"] * 2.5  # C2: 2.0 cut the axolotl's far gills and the chameleon's crest at 3/4
    t = face["target"]  # on the face's front: turned round a point a fifth of the width behind it, a little higher
    f = {"target": [0.0, t[1] + 0.08 * w, t[2] - 0.2 * w], "width": w}
    return {"front": {**f, "yaw": 0.0, "pitch": 3.0}, "3/4": {**f, "yaw": 38.0, "pitch": 3.0}}


def close(head: str) -> dict:
    """The lips' close-ups: the mouth at 3/4 and from the side."""
    face = R.features(head)["face"]
    w = face["width"] * 1.15
    t = face["target"]
    f = {"target": [0.0, t[1] - 0.12 * w, t[2] - 0.15 * w], "width": w}
    return {"3/4": {**f, "yaw": 40.0, "pitch": 3.0}, "side": {**f, "yaw": 70.0, "pitch": 3.0}}


def job(build: Path, out: Path) -> dict:
    j = {"hdri": str(R.HDRI), "window": list(WINDOW), "heads": {}, "sheets": []}
    reg = {h: regions(out, h) for h in HEADS}
    for h in HEADS:
        e = R.head_entry(build, h, f"tint_{h}")
        e["accent"] = str(out / "maps" / f"{h}_accent.png")
        e["params"] = R.column("F", R.picks(build))  # the static_v5 pick of the alive levers
        j["heads"][h] = e
    for light in LIGHTS:
        sets = [("A", range(5)), ("B1", range(5)), ("B2", range(5)), ("C", range(5)), ("D", range(5)),
                ("E", range(4)), ("E", range(4, 8))]
        for k, (name, idx) in enumerate(sets):
            rows = []
            for h in HEADS:
                for view, shot in shots(h).items():
                    row = []
                    for i in idx:
                        label, params = variant(name, i, reg[h])
                        tag = f"{name}{i + 1}" if name == "E" else name
                        row.append({"head": h, "params": params, "light": light, "shot": shot,
                                    "label": f"{tag} {label}\n{h} {view}"})
                    rows.append(row)
            stem = name if name != "E" else f"E{'a' if k == 5 else 'b'}"
            j["sheets"].append({"file": str(out / light / f"{stem}.jpg"), "cell": [256, 256], "width": 1280,
                                "title": f"{TITLES[name]}\n{LIGHTS[light]}\nrows: axolotl front, 3/4, "
                                         f"chameleon front, 3/4", "rows": rows})
        # the one-page summary: the 2D target, A, and the best of B to E, for three skins
        rows = []
        for h in HEADS:
            for i, (ei, label) in enumerate([(0, "teal"), (1, "coral"), (2, "lavender")]):
                row = [{"image": str(V2D / h / "front.png"), "label": f"2D target\n{h}"}]
                for name, tag in (("A", "A"), ("B1", "B1"), ("C", "C"), ("D", "D"), ("E", f"E{ei + 1}")):
                    lab, params = variant(name, ei if name == "E" else i, reg[h])
                    row.append({"head": h, "params": params, "light": light, "shot": shots(h)["3/4"],
                                "label": f"{tag} {lab}"})
                rows.append(row)
        j["sheets"].append({"file": str(out / light / "summary.jpg"), "cell": [214, 214], "width": 1280,
                            "title": f"Summary: 2D target | A today | B1 rose lips | C deeper lips | D pair | E\n"
                                     f"{LIGHTS[light]}\nrows: teal, coral, lavender (E: its own palettes)",
                            "rows": rows})
    # C2: the lips whole to their corners, B1's rose against the teal skin, close up
    rows = []
    for light in LIGHTS:
        row = []
        for h in HEADS:
            for view, shot in close(h).items():
                lab, params = variant("B1", 0, reg[h])
                row.append({"head": h, "params": params, "light": light, "shot": shot,
                            "label": f"B1 {lab}\n{h} {view} ({light})"})
        rows.append(row)
    j["sheets"].append({"file": str(out / "lips_b1.jpg"), "cell": [320, 320], "width": 1280,
                        "title": "The lips' accent mask to the mouth's corners: B1 rose lips on the teal skin\n"
                                 "rows: studio, dusk", "rows": rows})
    # the accent mask itself (R lips, G marks, B front), emitted
    rows = []
    for h in HEADS:
        row = []
        for view, yaw in (("front", 0.0), ("3/4", 35.0), ("side", 90.0), ("back", 180.0)):
            row.append({"head": h, "params": {}, "debug": 4, "light": "studio",
                        "shot": {"target": "box", "yaw": yaw, "pitch": 3.0},
                        "label": f"accent mask {view}\n{h}"})
        rows.append(row)
    j["sheets"].append({"file": str(out / "mask.jpg"), "cell": [320, 320], "width": 1280,
                        "title": "The accent mask, emitted: red the lips, green the marks\n(gills, freckles, crest "
                                 "stripes), blue the pale front panel", "rows": rows})
    return j


def masks(build: Path, out: Path) -> None:
    for h in HEADS:
        blender.run_script("alien_tint_mask.py", ["--head", h, "--build", str(build / h), "--ref",
                                                  str(R.STEP2A / h / "v2" / "build.json"), "--out", str(out / "maps")])
        print(f"mask {h}: {(out / 'maps' / f'{h}_accent.json').read_text(encoding='utf-8')}", flush=True)


def sheets(build: Path, out: Path, only: str) -> int:
    j = job(build, out)
    if only:
        j["sheets"] = [s for s in j["sheets"] if Path(s["file"]).stem in only.split(",")
                       or f"{Path(s['file']).parent.name}/{Path(s['file']).stem}" in only.split(",")]
    for light in LIGHTS:
        (out / light).mkdir(parents=True, exist_ok=True)
    _godot.import_project()
    path = out / "job.json"
    path.write_text(json.dumps(j, indent=1), encoding="utf-8", newline="\n")
    code, _ = _godot.window(["--path", str(_godot.PROJECT), "-s", "res://alien/tint_study.gd", "--", str(path)],
                            WINDOW, 900, log=out / "godot.log")
    print(f"sheets: exit {code}", flush=True)
    return code


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["masks", "sheets", "all"])
    ap.add_argument("--build", type=Path, default=BUILD)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--only", default="", help="sheets by stem or light/stem, comma-separated (default: all)")
    args = ap.parse_args()
    if args.what in ("masks", "all"):
        masks(args.build, args.out)
    if args.what in ("sheets", "all"):
        return sheets(args.build, args.out, args.only)
    return 0


if __name__ == "__main__":
    sys.exit(main())
