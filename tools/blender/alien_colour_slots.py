"""The alien pilot's static heads (art #196, 2026-10-23): the player's colour slots in the real material, the proof.
Plain Python, outside Blender (the maths: alien_colour_geom.py; the material: godot/alien/alien_static.gdshader and
alien_static.gd's set_colours):
- `masks`: each head's accent mask in headless Blender (alien_tint_mask.py: R lips, G details, B the pale front,
  A 1 - the gills; the axolotl's smile tail now in the lips) into `<out>/maps/`;
- `sheets`: a job for godot/alien/tint_study.gd on the real shader (its heads' `"static": true`), rendered in an
  off-screen window under the study's studio and dusk lights: the eight presets (the study's E), free picks with
  deliberately bad colours (the guard rails), details off and on, the axolotl's gills on the details or the skin,
  the lips' corners close up (the old mask beside the new), and the identity check (set_colours({}) against the
  merged shader, origin/main's alien_static.gdshader, a pixel diff into `identity.json`); every cell's uniforms as
  Godot set them into `uniforms.json`, compared here with alien_colour_geom.slot_colours;
- `web`: the three.js page: the GLBs, masks and bases beside tools/web/alien_colour/{colour.js,index.html} in
  `<out>/web/`.
One run can pass 180 s: in the background, its log in a file.

    $PYTHON_BIN tools/blender/alien_colour_slots.py <masks|sheets|web|all> [--out DIR]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runner import blender  # noqa: E402
from runner.commands import _godot  # noqa: E402
import alien_colour_geom as G  # noqa: E402
import alien_static_review as R  # noqa: E402
import alien_tint_study as T  # noqa: E402  (the study's lights, framings and head entries)

BUILD = R.NEW  # static_v5
OUT = R.DESIGN / "pilot3d" / "colour_slots"
OLD_MAPS = R.DESIGN / "pilot3d" / "colour" / "maps"  # the merged study's masks (#301), for the lips' before
HEADS = T.HEADS
WEB = ROOT / "tools" / "web" / "alien_colour"
MERGED_SHADER_REF = "1aa19cd"  # origin/main when the slots began: the merged alien_static.gdshader
# free picks: the player's own colours, the bad ones on purpose (the rails must hold)
FREE = [("neon green, hot pink lips, yellow details", {"skin": "#39ff14", "lips": "#ff1493", "detail": "#ffff00"}),
        ("hot pink skin", {"skin": "#ff1493"}),
        ("pure yellow, lips the same", {"skin": "#ffff00", "lips": "#ffff00"}),
        ("navy, white lips", {"skin": "#14206e", "lips": "#ffffff", "detail": "#ffffff"}),
        ("orange, cyan details", {"skin": "#ff7a00", "detail": "#00e5ff"}),
        ("mint, rose lips, details off", {"skin": "#b8f0d0", "lips": "#c48a8c", "detail": "#ff0000",
                                          "detail_on": False})]


def bases(build: Path, maps: Path, head: str) -> dict:
    """The build's own colours: the skin from the GLB's build (base_skin_srgb), the rest the accent JSON's medians."""
    b = json.loads((build / head / "build.json").read_text(encoding="utf-8"))
    rep = json.loads((maps / f"{head}_accent.json").read_text(encoding="utf-8"))["regions"]
    return {"skin": b["base_skin_srgb"], "lips": rep["lips"]["srgb"], "detail": rep["marks"]["srgb"],
            "front": rep["front"]["srgb"]}


def masks(build: Path, out: Path) -> None:
    for h in HEADS:
        blender.run_script("alien_tint_mask.py", ["--head", h, "--build", str(build / h), "--ref",
                                                  str(R.STEP2A / h / "v2" / "build.json"), "--out", str(out / "maps"),
                                                  "--debug"])
        print(f"mask {h}: {(out / 'maps' / f'{h}_accent.json').read_text(encoding='utf-8')}", flush=True)


def label(picks: dict) -> str:
    return " ".join(f"{k[0]}{v}" if isinstance(v, str) else f"{k}={'on' if v else 'off'}" for k, v in picks.items())


def job(build: Path, out: Path) -> dict:
    j = {"hdri": str(R.HDRI), "window": list(T.WINDOW), "heads": {}, "sheets": [],
         "uniforms": str(out / "uniforms.json"), "diffs": []}
    ref = out / "merged_alien_static.gdshader"
    ref.write_text(subprocess.run(["git", "-C", str(ROOT), "show", f"{MERGED_SHADER_REF}:godot/alien/"
                                   "alien_static.gdshader"], capture_output=True, text=True, check=True).stdout,
                   encoding="utf-8", newline="\n")
    for h in HEADS:
        e = R.head_entry(build, h, f"slots_{h}")
        e["params"] = R.column("F", R.picks(build))  # the static_v5 pick of the alive levers
        e.update(static=True, accent=str(out / "maps" / f"{h}_accent.png"), bases=bases(build, out / "maps", h))
        j["heads"][h] = e
        j["heads"][f"{h}_merged"] = {**e, "static": False, "accent": "", "shader_code": str(ref)}
    old = {**j["heads"]["axolotl"], "accent": str(OLD_MAPS / "axolotl_accent.png")}
    j["heads"]["axolotl_oldmask"] = old

    def cell(head, picks, light, shot, text):
        return {"head": head, "colours": picks, "light": light, "shot": shot, "label": text}

    presets = G.PRESETS
    for light in T.LIGHTS:
        lt = T.LIGHTS[light]
        for part, idx in (("a", range(4)), ("b", range(4, 8))):
            rows = [[cell(h, presets[i][1], light, shot, f"E{i + 1} {presets[i][0]}\n{h} {view}") for i in idx]
                    for h in HEADS for view, shot in T.shots(h).items()]
            j["sheets"].append({"file": str(out / light / f"presets_{part}.jpg"), "cell": [320, 320], "width": 1280,
                                "title": f"Presets E{idx[0] + 1}-E{idx[-1] + 1} (the study's E) on the real material"
                                         f"\n{lt}\nrows: axolotl front, 3/4, chameleon front, 3/4", "rows": rows})
        rows = [[cell(h, p, light, shot, f"{k + 1} {name}\n{h} {view}") for k, (name, p) in enumerate(FREE)]
                for h in HEADS for view, shot in T.shots(h).items()]
        j["sheets"].append({"file": str(out / light / "free.jpg"), "cell": [256, 256], "width": 1280,
                            "title": "Free picks, bad on purpose (the guard rails hold): " + "; ".join(
                                f"{k + 1} {label(p)}" for k, (_, p) in enumerate(FREE)) + f"\n{lt}",
                            "rows": rows})
        rows = []
        for h in HEADS:
            row = []
            for i in (1, 4, 6):
                for on in (False, True):
                    row.append(cell(h, {**presets[i][1], "detail_on": on}, light, T.shots(h)["3/4"],
                                    f"E{i + 1} details {'on' if on else 'off'}\n{h} 3/4"))
            rows.append(row)
        j["sheets"].append({"file": str(out / light / "details.jpg"), "cell": [256, 256], "width": 1280,
                            "title": f"Details off (they follow the skin) vs on (their own colour): E2, E5, E7\n{lt}",
                            "rows": rows})
        rows = []
        for i in (1, 3, 4, 6):
            row = []
            for gd in (True, False):
                for view, shot in T.shots("axolotl").items():
                    row.append(cell("axolotl", {**presets[i][1], "gills_detail": gd}, light, shot,
                                    f"E{i + 1} gills on {'details' if gd else 'skin'}\n{view}"))
            rows.append(row)
        j["sheets"].append({"file": str(out / light / "gills.jpg"), "cell": [320, 320], "width": 1280,
                            "title": f"The axolotl's gills: on the details slot (left pair, the default) or on the "
                                     f"skin (right pair)\n{lt}\nrows: E2, E4, E5, E7", "rows": rows})
    # the lips' corners close up: a strong lip colour on the build's skin; the axolotl's old mask (#301) first
    rows = []
    lip = {"lips": "#a2575a"}
    for light in T.LIGHTS:
        for head, name in (("axolotl_oldmask", "axolotl, #301 mask"), ("axolotl", "axolotl, new mask"),
                           ("chameleon", "chameleon")):
            h = head.split("_")[0]
            rows.append([cell(head, lip, light, shot, f"{name} {view}\n{light}") for view, shot in T.close(h).items()]
                        + [cell(head, presets[1][1], light, T.close(h)["3/4"], f"{name} E2 3/4\n{light}")])
    j["sheets"].append({"file": str(out / "lips.jpg"), "cell": [420, 420], "width": 1280,
                        "title": "The lips to the smile line's end: lips #a2575a on the build's skin (3/4, side), "
                                 "E2 coral reef\nrows: axolotl #301 mask, axolotl new, chameleon; studio then dusk",
                        "rows": rows})
    # the identity: set_colours({}) on the new material against the merged shader, the same levers and light
    rows = []
    for h in HEADS:
        row = []
        for view, shot in T.shots(h).items():
            for key, name in ((f"{h}_merged", "merged"), (h, "slots {}")):
                tag = f"{h}_{view.replace('/', '')}_{name.split()[0]}"
                # the same label on both: the label is drawn in the window, so it is in the grab
                row.append({**cell(key, {}, "studio", shot, f"identity\n{h} {view}"),
                            "save": str(out / "identity" / f"{tag}.png")})
            j["diffs"].append([str(out / "identity" / f"{h}_{view.replace('/', '')}_merged.png"),
                               str(out / "identity" / f"{h}_{view.replace('/', '')}_slots.png")])
        rows.append(row)
    j["sheets"].append({"file": str(out / "identity.jpg"), "cell": [320, 320], "width": 1280,
                        "title": "Identity: per pair the merged shader (left) and the slots material with no "
                                 "picks (right), studio\npixel diff in identity.json", "rows": rows})
    j["diff_out"] = str(out / "identity.json")
    return j


def check_uniforms(out: Path, j: dict) -> float:
    """Godot's set_colours against alien_colour_geom.slot_colours on every cell: the largest channel difference."""
    got = json.loads((out / "uniforms.json").read_text(encoding="utf-8"))
    worst = 0.0
    for rec in got:
        b = j["heads"][rec["head"]].get("bases")
        if not b:
            continue
        want = G.slot_colours(b, rec["picks"])
        for k, v in want.items():
            g = rec["uniforms"][k]
            vv = v if isinstance(v, tuple) else (v,)
            gg = g if isinstance(g, list) else [g]
            worst = max(worst, max(abs(x - y) for x, y in zip(vv, gg)))
    print(f"uniforms: {len(got)} cells, Godot vs Python max |diff| {worst:.2e}", flush=True)
    return worst


def sheets(build: Path, out: Path, only: str = "") -> int:
    for d in [*T.LIGHTS, "identity"]:
        (out / d).mkdir(parents=True, exist_ok=True)
    j = job(build, out)
    if only:  # sheets by stem (e.g. "identity"); the identity diffs only with the identity sheet
        j["sheets"] = [s for s in j["sheets"] if Path(s["file"]).stem in only.split(",")]
        if "identity" not in only.split(","):
            j["diffs"] = []
    _godot.import_project()
    path = out / "job.json"
    path.write_text(json.dumps(j, indent=1), encoding="utf-8", newline="\n")
    code, _ = _godot.window(["--path", str(_godot.PROJECT), "-s", "res://alien/tint_study.gd", "--", str(path)],
                            T.WINDOW, 900, log=out / "godot.log")
    print(f"sheets: exit {code}", flush=True)
    if code == 0 and j["diffs"]:
        print(f"identity: {(out / 'identity.json').read_text(encoding='utf-8')}", flush=True)
    if code == 0 and check_uniforms(out, j) > 2e-3:
        return 5
    return code


def web(build: Path, out: Path) -> None:
    d = out / "web"
    d.mkdir(parents=True, exist_ok=True)
    heads = {}
    for h in HEADS:
        shutil.copy2(build / h / f"{h}_static.glb", d / f"{h}_static.glb")
        shutil.copy2(out / "maps" / f"{h}_accent.png", d / f"{h}_accent.png")
        shutil.copy2(build / h / f"{h}_mask.png", d / f"{h}_mask.png")
        heads[h] = bases(build, out / "maps", h)
    (d / "heads.json").write_text(json.dumps(heads, indent=1) + "\n", encoding="utf-8", newline="\n")
    for f in ("colour.js", "index.html"):
        shutil.copy2(WEB / f, d / f)
    print(f"web: {d}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["masks", "sheets", "web", "all"])
    ap.add_argument("--build", type=Path, default=BUILD)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--only", default="", help="sheets by stem, comma-separated (default: all)")
    args = ap.parse_args()
    if args.what in ("masks", "all"):
        masks(args.build, args.out)
    if args.what in ("web", "all"):
        web(args.build, args.out)
    if args.what in ("sheets", "all"):
        return sheets(args.build, args.out, args.only)
    return 0


if __name__ == "__main__":
    sys.exit(main())
