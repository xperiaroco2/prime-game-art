"""Bodies by drawing, step D3 (art #196): the station fit of body A to its dims table and B's rest skeleton, in
plain Python (body_fit_geom.py's maths on body_fit_blend.py's dump; then `body_fit_blend.py apply` writes the .blend).

    python tools/blender/body_fit_run.py --dump <A0 dump.json> --out <dir>

Writes <dir>/A/fit.json (the vertices in metres, the ring's vertex indices), errors.json and errors.md beside it (the
overlay error per station, built minus table): body A is today's body (S4b) fitted to A.toml, two passes (the second
measures the first's result). <dir>/B/rest.json is B's rest skeleton (B1's alien_body_b_geom with fit.toml's joints;
the heights from the two tables' neck rings, the Neck and Head about B's ring by B.toml's numbers, the feet by
fit.toml's scales). B's mesh is not built here yet: B.toml is being re-measured (the D3 brief's update of
2026-10-29), so D3b fits B's mesh with the fixed table (`chest_of` and the fit's `chest` are its chest rounds).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import alien_body_b_geom as G  # noqa: E402
import body_fit_geom as F  # noqa: E402

DIMS = HERE / "body_dims"


def mm(v: list) -> list:
    return [tuple(c * 1000.0 for c in p) for p in v]


def bones_mm(b: dict) -> dict:
    return {n: {"head": [c * 1000 for c in x["head"]], "tail": [c * 1000 for c in x["tail"]],
                "parent": x.get("parent")} for n, x in b.items()}


def b_target(s: dict, bones: dict, ring_a_m: float, scale: float) -> tuple[dict, dict]:
    """B1's target for B's rest with fit.toml's joints: the shifts solved from A's bones (metres); checked with
    zero shifts (B1's check allows no inward hip shift, and B's hips move about 1 mm in)."""
    t = {"name": "d3b", "note": "D3's rest for B",
         "height": {"scale": scale, "ring_z": ring_a_m, "lock_from_z": ring_a_m - 0.06},
         "arms": {"shift_in_m": 0.0, "shoulder_axial": 0.85, "upper_radial": 1.0, "lower_radial": 1.0,
                  "hand_scale": s["hand_scale"]},
         "legs": {"shift_out_m": 0.0, "upper_radial": 1.0, "lower_radial": 1.0, "foot_scale": scale},
         "profile": {"z": [0.5, 1.0], "scale": [1.0, 1.0]},
         "chest": {"amount_m": 0.0, "z": 1.1, "half_z": 0.1, "x": 0.05, "half_x": 0.07, "ramp_m": 0.05},
         "seat": {"amount_m": 0.0, "z": 0.8, "half_z": 0.1, "x": 0.06, "half_x": 0.1, "ramp_m": 0.05},
         "mask": {"bones": ["Hips", "Spine", "Chest", "UpperChest", "LeftUpperLeg", "RightUpperLeg"]}}
    r0 = G.rest(bones, G.check(t))
    t["arms"]["shift_in_m"] = round(r0["LeftUpperArm"]["head"][0] - s["shoulder_joint_x"] / 1000, 6)
    t["legs"]["shift_out_m"] = round(s["hip_joint_x"] / 1000 - r0["LeftUpperLeg"]["head"][0], 6)
    return t, {"shift_in_m": t["arms"]["shift_in_m"], "shift_out_m": t["legs"]["shift_out_m"]}


def b_rest(bones: dict, table_a: dict, table_b: dict, s: dict) -> tuple[dict, dict]:
    """B's rest skeleton (metres) from A's bones, data-driven: the height scale is B's ring over A's, the joints'
    x from fit.toml, the Neck's head `neck_bone_below` under B's ring and the Head's `head_bone_above` over it (the
    bones that ended at the old Neck head end at the new one), the hands by `hand_scale`, the feet by their scales
    about the ankles. The report holds the scale, the shifts and the key joints in mm."""
    ra, rb = table_a["neck_ring"], table_b["neck_ring"]
    scale = rb["z"] / ra["z"]
    t, shifts = b_target(s, bones, ra["z"] / 1000, scale)
    rest = {n: {"head": tuple(r["head"]), "tail": tuple(r["tail"]), "parent": r["parent"]}
            for n, r in G.rest(bones, t).items()}  # checked in b_target with zero shifts
    ring = rb["z"] / 1000
    for name, dz in (("Neck", -rb["neck_bone_below"]), ("Head", rb["head_bone_above"])):
        old = rest[name]["head"]
        rest[name]["head"] = (old[0], old[1], ring + dz / 1000)
        for n, r in rest.items():  # the bones that ended at its head on A (the parent's tail) end at the new one
            if math.dist(bones[n]["tail"], bones[name]["head"]) < 1e-6:
                r["tail"] = rest[name]["head"]
    feet([], [], rest, s["foot_scale_x"] / scale, s["foot_scale_y"] / scale)
    rep = {"height_scale": round(scale, 6), "shifts": shifts,
           "joints_mm": {n: [round(c * 1000, 1) for c in rest[n]["head"]] for n in
                         ("LeftShoulder", "LeftUpperArm", "LeftHand", "LeftUpperLeg", "LeftFoot", "LeftToes",
                          "Neck", "Head")},
           "ring_mm": rb["z"]}
    return rest, rep


def feet(verts: list, weights: list, rest: dict, sx: float, sy: float) -> list:
    """The feet scaled about their ankles (x by sx, y by sy; metres), by the vertices' foot weights; the feet's
    bones with them."""
    out = []
    for p, w in zip(verts, weights):
        f = F.foot_share(w)
        if f <= 0:
            out.append(tuple(p))
            continue
        a = rest["LeftFoot" if p[0] >= 0 else "RightFoot"]["head"]
        q = (a[0] + sx * (p[0] - a[0]), a[1] + sy * (p[1] - a[1]), p[2])
        out.append(tuple(p[i] + f * (q[i] - p[i]) for i in range(3)))
    for side in ("Left", "Right"):
        a = tuple(rest[f"{side}Foot"]["head"])
        for n in (f"{side}Foot", f"{side}Toes"):
            for k in ("head", "tail"):
                p = rest[n][k]
                rest[n][k] = (a[0] + sx * (p[0] - a[0]), a[1] + sy * (p[1] - a[1]), p[2])
    return out


def chest_of(table: dict, s: dict) -> dict:
    """The chest rounds' settings: the table's chest keys, its side front, fit.toml's spread across x."""
    c, t = table["chest"], table["trunk"]
    front = F.Profile(t["z"], [F.num(v) for v in t["front_y"]], sigma=4.0)
    return {"under_z": c["under_z"], "top_z": c["top_z"], "under_f": front(c["under_z"]), "top_f": front(c["top_z"]),
            "front": front, "centre_x": c["centre_x"], "sigma_x": s["chest_sigma_x"], "floor": s["chest_floor"]}


def run_fit(name: str, verts_mm: list, weights: list, edges: list, bones: dict, ring: list, s: dict,
            chest: dict | None) -> tuple[list, dict]:
    table = F.load_table(DIMS / f"{name}.toml")
    table["fit"] = {"keep_front": s.get("keep_front", [])}
    fr = F.frame_of(table, bones, 0.0)
    au = F.armpit_u(verts_mm, edges, weights, fr["armpit"] - 5.0)
    v, reps = verts_mm, []
    before = F.errors(v, weights, edges, table, bones, au, chest)
    for _ in range(2):
        v, rep = F.fit(v, weights, edges, table, bones, au, ring, chest)
        reps.append(rep)
    err = F.errors(v, weights, edges, table, bones, au, chest)
    err["before"] = before["summary"]
    err["passes"] = reps
    return v, err


def table_md(name: str, err: dict) -> str:
    lines = [f"# Body {name}: overlay error per station (built minus table, mm)", "",
             "| region.measure | stations | worst | at | mean abs | before: worst at | over target |",
             "|---|---|---|---|---|---|---|"]
    for k, v in err["summary"].items():
        b = err["before"].get(k, {})
        lines.append(f"| {k} | {v['n']} | {v['worst']} | {v['at']} | {v['mean_abs']} | {b.get('worst', '-')} at "
                     f"{b.get('at', '-')} | {', '.join(str(x) for x in v['over']) or 'none'} |")
    lines += ["", "Targets: 5 mm on the trunk, 3 mm on the limbs. Stations left alone by rule are in errors.json "
              "(`rule`): the neck taper, the shoulders over the armpit (T arms), the kept front, the feet.", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    d = json.loads(Path(a.dump).read_text(encoding="utf-8"))
    settings = tomllib.loads((DIMS / "fit.toml").read_text(encoding="utf-8"))
    out = Path(a.out)
    ring, weights, edges, bones_m = d["loops"][0], d["weights"], d["edges"], d["bones"]
    va, ea = run_fit("A", mm(d["verts"]), weights, edges, bones_mm(bones_m), ring, settings["A"], None)
    o = out / "A"
    o.mkdir(parents=True, exist_ok=True)
    fit = {"verts": [[round(c / 1000, 7) for c in p] for p in va], "ring": ring, "rest": None}
    (o / "fit.json").write_text(json.dumps(fit), encoding="utf-8")
    (o / "errors.json").write_text(json.dumps(ea, indent=1), encoding="utf-8", newline="\n")
    (o / "errors.md").write_text(table_md("A", ea), encoding="utf-8", newline="\n")
    print(table_md("A", ea))
    rest, rep = b_rest(bones_m, F.load_table(DIMS / "A.toml"), F.load_table(DIMS / "B.toml"), settings["B"])
    o = out / "B"
    o.mkdir(parents=True, exist_ok=True)
    rest_out = {n: {"head": list(r["head"]), "tail": list(r["tail"]), "parent": r["parent"]} for n, r in rest.items()}
    (o / "rest.json").write_text(json.dumps({"rest": rest_out, "report": rep}, indent=1), encoding="utf-8",
                                 newline="\n")
    print("B_REST", json.dumps(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
