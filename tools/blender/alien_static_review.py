"""The alien pilot's static heads, round 2 (art #196, static_v2): review sheets in an off-screen Godot window
(godot/alien/static_alive.gd through the runner's _godot.window()). Plain Python, outside Blender. Sheets (JPG, about
1280 px wide) go into <out>/<head>/ or <out>/:
- `seams`: the engineer's close-ups (the axolotl's lip corner, the chameleon's eye rim) and a wider framing; rows: the
  #288 build, then this build; columns: the full material, grey with the normal map, grey geometry only, the albedo;
- `grid`: one row per "alive" lever (B to F), four variants each, the face at 3/4, on top of the ladder's earlier picks;
- `ladder`: the cumulative ladder A..F (A = the #288 material) and F under the showroom's AgX 0.9; rows: the front
  close-up, the 3/4 close-up, the full head; GPU ms per column into `ladder.json`;
- `gate`: the whole-head gate, both heads from 4 sides, #288 against this build, under the same light.

    $PYTHON_BIN tools/blender/alien_static_review.py <seams|grid|ladder|gate|all> [--old DIR] [--new DIR] [--heads ...]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from runner import common  # noqa: E402
from runner.commands import _godot  # noqa: E402

RAW = common.raw_dir()
DESIGN = RAW / "research" / "2026-10-22-roster" / "design"
STEP2A = DESIGN / "pilot3d" / "step2a"
OLD = DESIGN / "pilot3d" / "static"
NEW = DESIGN / "pilot3d" / "static_v2"
HDRI = RAW / "env" / "polyhaven" / "studio_small_09" / "studio_small_09_2k.hdr"  # CC0, sources/polyhaven_hdris_2k.toml
WINDOW = (1000, 1000)

# The "alive" ladder, cumulative: each lever's parameters (alien_static.gdshader); PICK is the tuned set per lever
# (from the grid), GRID the variants tried per lever.
LEVERS = ["B", "C", "D", "E", "F"]
NAMES = {"A": "#288", "B": "subsurface + transmission", "C": "micro grain + roughness breakup",
         "D": "cavity colour + flush", "E": "grazing sheen", "F": "wet eyes"}
GRID = {
    "B": [{"sss": 0.4, "transmission": 0.6}, {"sss": 0.6, "transmission": 1.0},
          {"sss": 0.6, "transmission": 1.0, "scatter_from_skin": 0.0}, {"sss": 0.85, "transmission": 1.5}],
    "C": [{"micro_strength": 0.08, "micro_scale": 140.0, "rough_breakup": 0.06},
          {"micro_strength": 0.15, "micro_scale": 140.0, "rough_breakup": 0.1},
          {"micro_strength": 0.15, "micro_scale": 260.0, "rough_breakup": 0.1},
          {"micro_strength": 0.3, "micro_scale": 90.0, "rough_breakup": 0.15}],
    "D": [{"cavity": 0.5, "flush": 0.3}, {"cavity": 0.8, "flush": 0.5},
          {"cavity": 0.8, "cavity_warm": -0.04, "flush": 0.5}, {"cavity": 1.0, "flush": 0.8}],
    "E": [{"fuzz": 0.2, "fuzz_power": 3.0, "sheen": 0.2}, {"fuzz": 0.4, "fuzz_power": 3.0, "sheen": 0.3},
          {"fuzz": 0.4, "fuzz_power": 2.0, "sheen": 0.3}, {"fuzz": 0.7, "fuzz_power": 2.5, "sheen": 0.4}],
    "F": [{"eye_coat": 0.6, "eye_coat_rough": 0.05, "eye_under_rough": 0.25, "limbal": 0.3},
          {"eye_coat": 1.0, "eye_coat_rough": 0.02, "eye_under_rough": 0.3, "limbal": 0.5},
          {"eye_coat": 1.0, "eye_coat_rough": 0.02, "eye_under_rough": 0.45, "limbal": 0.6},
          {"eye_coat": 1.0, "eye_coat_rough": 0.0, "eye_under_rough": 0.3, "limbal": 0.8}],
}
# the pick from grid.jpg (2026-10-22, both heads alike): B the strongest scatter, C the second (the fourth reads as
# pores), D the full cavity colour and flush, E the softer grazing sheen, F the sharpest wet coat and darkest ring
PICK = {"B": GRID["B"][3], "C": GRID["C"][1], "D": GRID["D"][3], "E": GRID["E"][2], "F": GRID["F"][3]}


def picks(new: Path) -> dict:
    p = new / "pick.json"
    return {**PICK, **json.loads(p.read_text(encoding="utf-8"))} if p.exists() else dict(PICK)


def column(upto: str, pick: dict) -> dict:
    out = {}
    for k in LEVERS[:LEVERS.index(upto) + 1] if upto != "A" else []:
        out.update(pick[k])
    return out


def features(head: str) -> dict:
    """Godot-space framings from step 2a's fits (Blender Z-up, -Y front; the GLB is Y-up, +Z front)."""
    ref = json.loads((STEP2A / head / "v2" / "build.json").read_text(encoding="utf-8"))
    e = ref["eye_fit"]
    ex, ey, ez, r = abs(e["x"]), e["z"], -e["y"], e["r"]
    line = ref["lip_line"]["line"]  # already (x, up, front)
    cx, cy, cz = line[-1]
    my, mz = line[0][1], line[0][2]
    if head == "axolotl":
        close = {"target": [-cx + 0.02, cy, cz + 0.01], "yaw": -25.0, "pitch": 4.0, "width": 0.16}
        wide = {"target": [0.0, my, mz], "yaw": -15.0, "pitch": 4.0, "width": 0.62}
    else:
        close = {"target": [ex + 0.6 * r, ey - 0.1 * r, ez + 0.7 * r], "yaw": 30.0, "pitch": 4.0, "width": 1.2 * r}
        wide = {"target": [ex, ey, ez + 0.8 * r], "yaw": 20.0, "pitch": 4.0, "width": 3.2 * r}
    face = {"target": [0.0, (ey + my) / 2, (ez + max(ez + r, mz)) / 2], "width": 1.9 * max(ex + r, cx)}
    return {"close": close, "wide": wide, "face": face}


def head_entry(d: Path, head: str, name: str) -> dict:
    build = json.loads((d / head / "build.json").read_text(encoding="utf-8"))
    detail = d / head / f"{head}_detail.png"
    return {"glb": _godot.stage(d / head / f"{head}_static.glb", name), "mask": str(d / head / f"{head}_mask.png"),
            "detail": str(detail) if detail.exists() else "", "base": build["base_skin_srgb"]}


def run(job: dict, out: Path, tag: str) -> int:
    out.mkdir(parents=True, exist_ok=True)
    _godot.import_project()
    path = out / f"job_{tag}.json"
    path.write_text(json.dumps(job, indent=1), encoding="utf-8", newline="\n")
    code, _ = _godot.window(["--path", str(_godot.PROJECT), "-s", "res://alien/static_alive.gd", "--", str(path)],
                            WINDOW, 900, log=out / f"godot_{tag}.log")
    print(f"{tag}: exit {code}", flush=True)
    return code


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["seams", "grid", "ladder", "gate", "all"])
    ap.add_argument("--old", type=Path, default=OLD)
    ap.add_argument("--new", type=Path, default=NEW)
    ap.add_argument("--heads", default="axolotl,chameleon")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    heads = args.heads.split(",")
    new_ok = all((args.new / h / f"{h}_static.glb").exists() for h in heads)
    job = {"hdri": str(HDRI), "window": list(WINDOW), "heads": {}, "sheets": []}
    pick = picks(args.new)
    final = column("F", pick)
    for h in heads:
        job["heads"][f"{h}_old"] = head_entry(args.old, h, f"alive_{h}_old")
        if new_ok:
            job["heads"][f"{h}_new"] = head_entry(args.new, h, f"alive_{h}_new")
    todo = ["seams", "grid", "ladder", "gate"] if args.what == "all" else [args.what]
    for h in heads:
        f = features(h)
        d = args.new / h
        d.mkdir(parents=True, exist_ok=True)
        if "seams" in todo:
            for fr in ("close", "wide"):
                rows = []
                for key in [f"{h}_old"] + ([f"{h}_new"] if new_ok else []):
                    rows.append([{"head": key, "debug": m, "tone": "showroom", "shot": f[fr]} for m in (0, 1, 2, 3)])
                job["sheets"].append({"file": str(d / f"seams_{fr}{args.tag}.jpg"), "cell": [320, 320], "rows": rows})
        if "grid" in todo and new_ok:
            rows = []
            face34 = dict(f["face"], yaw=35.0)
            for lever in LEVERS:
                base = column(LEVERS[LEVERS.index(lever) - 1], pick) if lever != "B" else {}
                rows.append([{"head": f"{h}_new", "params": {**base, **v}, "shot": face34} for v in GRID[lever]])
            job["sheets"].append({"file": str(d / f"grid{args.tag}.jpg"), "cell": [320, 360], "rows": rows})
        if "ladder" in todo and new_ok:
            cols = [("A", f"{h}_old", "pick"), *[(c, f"{h}_new", "pick") for c in ["A", *LEVERS]], ("F", f"{h}_new", "showroom")]
            rows = []
            for name, shot in (("front", dict(f["face"], yaw=0.0)), ("q34", dict(f["face"], yaw=35.0)),
                               ("full", {"target": "box", "yaw": 30.0})):
                rows.append([{"head": key, "params": column(c, pick), "tone": tone, "shot": shot, "gpu": name == "full"}
                             for c, key, tone in cols])
            job["sheets"].append({"file": str(d / f"ladder{args.tag}.jpg"), "cell": [300, 360], "width": 2120,
                                  "rows": rows})
    if "gate" in todo and new_ok:
        rows = []
        for h in heads:
            for key, params in ((f"{h}_old", {}), (f"{h}_new", final)):
                rows.append([{"head": key, "params": params, "shot": {"target": "box", "yaw": y}}
                             for y in (0.0, 35.0, 90.0, 180.0)])
        job["sheets"].append({"file": str(args.new / f"gate{args.tag}.jpg"), "cell": [320, 380], "rows": rows})
    return run(job, args.new, args.what + args.tag)


if __name__ == "__main__":
    sys.exit(main())
