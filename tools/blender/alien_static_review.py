"""The alien pilot's static heads (art #196): review sheets in an off-screen Godot window (godot/alien/static_alive.gd
through the runner's _godot.window()). Plain Python, outside Blender. Round 3 (static_v3) baked the alive read into
the textures (alien_static_head.py `alive`), so the Godot levers are the baked layers' strength (`alive_mix`, against
the plain albedo), the skin specular, the scatter and transmission, the grazing sheen and the wet eyes. Sheets (JPG,
about 1280 px wide) go into <new>/<name>/ or <new>/:
- `seams`: the engineer's close-ups (the axolotl's lip corner, the chameleon's eye rim) and a wider framing; rows: the
  #288 build, step 2 (static_v3, under its own pick), this build (static_v4); columns: the full
  material, grey with the normal map, grey geometry only, the albedo;
- `grid`: one row per lever (A, S, B, E, F), four decisive strengths each (off, mid, strong, too much), the face at
  3/4, on top of the earlier rows' picks;
- `final`: the before/after, #288 against the pick under the recommended light (AgX 0.65, saturation 1.35) and under
  the showroom's AgX 0.9; rows: the front close-up, the 3/4 close-up, the full head; GPU ms into `final.json`;
- `gate`: the whole-head gate from 4 sides, #288 against this build, under
  the same light.

    $PYTHON_BIN tools/blender/alien_static_review.py <seams|grid|final|gate|all> [--old DIR] [--mid DIR] [--new DIR]
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
MID = DESIGN / "pilot3d" / "static_v3"  # static_v4: the seams' middle row is step 2 (it was step 1, static_v2)
NEW = DESIGN / "pilot3d" / "static_v4"
HDRI = RAW / "env" / "polyhaven" / "studio_small_09" / "studio_small_09_2k.hdr"  # CC0, sources/polyhaven_hdris_2k.toml
WINDOW = (1000, 1000)
BUILDS = {"axolotl": ["axolotl"], "chameleon": ["chameleon"]}  # static_v4: chameleon_heavylid dropped

# The levers, cumulative (alien_static.gdshader): PICK is the chosen strength per lever, GRID four decisive strengths
# (off, mid, strong, too much). The shader's own cavity, flush and micro grain stay off: the cavity and flush are baked
# into the albedo now, and the grain read as orange peel (step 1).
LEVERS = ["A", "S", "B", "E", "F"]
NAMES = {"A": "baked alive layers", "S": "skin specular", "B": "subsurface + transmission", "E": "grazing sheen",
         "F": "wet eyes"}
GRID = {
    "A": [{"alive_mix": 0.0}, {"alive_mix": 0.6}, {"alive_mix": 1.0}, {"alive_mix": 1.8}],
    "S": [{"specular_level": 0.45}, {"specular_level": 0.3}, {"specular_level": 0.18}, {"specular_level": 0.06}],
    "B": [{"sss": 0.0, "transmission": 0.0}, {"sss": 0.5, "transmission": 0.8},
          {"sss": 0.85, "transmission": 1.5}, {"sss": 1.0, "transmission": 2.0, "scatter_from_skin": 0.3}],
    "E": [{"fuzz": 0.0}, {"fuzz": 0.3, "fuzz_power": 2.5, "sheen": 0.3}, {"fuzz": 0.5, "fuzz_power": 2.0, "sheen": 0.3},
          {"fuzz": 0.9, "fuzz_power": 1.5, "sheen": 0.5}],
    "F": [{"eye_coat": 0.0, "limbal": 0.0}, {"eye_coat": 0.6, "eye_coat_rough": 0.05, "limbal": 0.4},
          {"eye_coat": 1.0, "eye_coat_rough": 0.02, "eye_under_rough": 0.3, "limbal": 0.8},
          {"eye_coat": 1.0, "eye_coat_rough": 0.0, "eye_under_rough": 0.5, "limbal": 1.0}],
}
PICK = {"A": GRID["A"][2], "S": GRID["S"][2], "B": GRID["B"][2], "E": GRID["E"][1], "F": GRID["F"][2]}


def picks(new: Path) -> dict:
    p = new / "pick.json"
    return {**PICK, **json.loads(p.read_text(encoding="utf-8"))} if p.exists() else dict(PICK)


def column(upto: str, pick: dict) -> dict:
    out = {}
    for k in LEVERS[:LEVERS.index(upto) + 1] if upto else []:
        out.update(pick[k])
    return out


def features(name: str) -> dict:
    """Godot-space framings from step 2a's fits (Blender Z-up, -Y front; the GLB is Y-up, +Z front)."""
    head = name.split("_")[0]
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


def head_entry(d: Path, name: str, key: str) -> dict:
    build = json.loads((d / name / "build.json").read_text(encoding="utf-8"))
    detail, plain = d / name / f"{name}_detail.png", d / name / f"{name}_albedo_plain.png"
    return {"glb": _godot.stage(d / name / f"{name}_static.glb", key), "mask": str(d / name / f"{name}_mask.png"),
            "detail": str(detail) if detail.exists() else "", "plain": str(plain) if plain.exists() else "",
            "base": build["base_skin_srgb"]}


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
    ap.add_argument("what", choices=["seams", "grid", "final", "gate", "all"])
    ap.add_argument("--old", type=Path, default=OLD)
    ap.add_argument("--mid", type=Path, default=MID)
    ap.add_argument("--new", type=Path, default=NEW)
    ap.add_argument("--heads", default="axolotl,chameleon")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    heads = args.heads.split(",")
    job = {"hdri": str(HDRI), "window": list(WINDOW), "heads": {}, "sheets": []}
    pick = picks(args.new)
    final = column("F", pick)
    for h in heads:
        job["heads"][f"{h}_old"] = head_entry(args.old, h, f"alive_{h}_old")
        job["heads"][f"{h}_mid"] = head_entry(args.mid, h, f"alive_{h}_mid")
        for n in BUILDS[h]:
            job["heads"][f"{n}_new"] = head_entry(args.new, n, f"alive_{n}_new")
    todo = ["seams", "grid", "final", "gate"] if args.what == "all" else [args.what]
    for h in heads:
        f = features(h)
        d = args.new / h
        if "seams" in todo:
            keys = [(f"{h}_old", {}), (f"{h}_mid", final)] + [(f"{n}_new", final) for n in BUILDS[h]]
            for fr in ("close", "wide"):
                rows = [[{"head": key, "params": prm, "debug": m, "tone": "showroom", "shot": f[fr]}
                         for m in (0, 1, 2, 3)] for key, prm in keys]
                job["sheets"].append({"file": str(d / f"seams_{fr}{args.tag}.jpg"), "cell": [320, 320], "rows": rows})
        if "grid" in todo:
            face34 = dict(f["face"], yaw=35.0)
            rows = []
            for lever in LEVERS:
                base = column(LEVERS[LEVERS.index(lever) - 1], pick) if lever != LEVERS[0] else {}
                rows.append([{"head": f"{h}_new", "params": {**base, **v}, "shot": face34} for v in GRID[lever]])
            job["sheets"].append({"file": str(d / f"grid{args.tag}.jpg"), "cell": [320, 360], "rows": rows})
        if "final" in todo:
            cols = [(f"{h}_old", {}, "pick"), (f"{h}_new", final, "pick"), (f"{h}_old", {}, "showroom"),
                    (f"{h}_new", final, "showroom")]
            rows = []
            for name, shot in (("front", dict(f["face"], yaw=0.0)), ("q34", dict(f["face"], yaw=35.0)),
                               ("full", {"target": "box", "yaw": 30.0})):
                rows.append([{"head": key, "params": prm, "tone": tone, "shot": shot, "gpu": name == "full"}
                             for key, prm, tone in cols])
            job["sheets"].append({"file": str(d / f"final{args.tag}.jpg"), "cell": [320, 380], "rows": rows})
    if "gate" in todo:
        rows = []
        for h in heads:
            for key, params in [(f"{h}_old", {})] + [(f"{n}_new", final) for n in BUILDS[h]]:
                rows.append([{"head": key, "params": params, "shot": {"target": "box", "yaw": y}}
                             for y in (0.0, 35.0, 90.0, 180.0)])
        job["sheets"].append({"file": str(args.new / f"gate{args.tag}.jpg"), "cell": [320, 380], "rows": rows})
    return run(job, args.new, args.what + args.tag)


if __name__ == "__main__":
    sys.exit(main())
