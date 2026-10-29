"""Bodies by drawing, step D3 (art #196): the station fit of body A to its dims table and B's rest skeleton, in
plain Python (body_fit_geom.py's maths on body_fit_blend.py's dump; then `body_fit_blend.py apply` writes the .blend).

    python tools/blender/body_fit_run.py --dump <A0 dump.json> --out <dir>

Writes <dir>/A/fit.json (the vertices in metres, the ring's vertex indices), errors.json and errors.md beside it (the
overlay error per station, built minus table): body A is today's body (S4b) fitted to A.toml, two passes (the second
measures the first's result). Body B (D3b) is A's fitted mesh on B's rest skeleton (B1's alien_body_b_geom with
fit.toml's joints; the heights from the two tables' neck rings, the Neck and Head about B's ring by B.toml's
numbers), then the hands and feet scaled from A's by the tables' B/A ratios (`limb_scales`: the hand's length along
its bone and its width across, the foot's length in y and width in x; the mesh per axis, the bones along their own
directions), then fitted to B.toml with her chest rounds (`chest_of`) and the neck base; the shoulder chains (the
Shoulder to the fingertips) then move rigidly with the arms' mesh (`arm_shift_mm`, `arms_moved`). <dir>/B/fit.json
holds the vertices and the rest ("rest"), errors beside it. Every B bone keeps A's rest direction (`rest_turns`, at
most the contract's `[body_types.B] rest_turn_max_deg`) and B's arm mesh sits on its bones as A's does
(`arm_offsets`, within ARM_OFFSET_MAX_MM); either over its limit exits 1 (D3i, the review of art #196).
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
CONTRACT = HERE.parent.parent / "contract" / "contract.toml"
ARM_OFFSET_MAX_MM = 1.0  # B's arm mesh against its bones in y, minus A's (per arm bone; the hand's by its width scale)
ARM_BONES = ("UpperArm", "LowerArm", "Hand")


def mm(v: list) -> list:
    return [tuple(c * 1000.0 for c in p) for p in v]


def bones_mm(b: dict) -> dict:
    return {n: {"head": [c * 1000 for c in x["head"]], "tail": [c * 1000 for c in x["tail"]],
                "parent": x.get("parent")} for n, x in b.items()}


def limb_scales(table_a: dict, table_b: dict) -> dict:
    """B's hands and feet against A's, per axis, from the two tables' keys (at our size: the engineer, 2026-10-29)."""
    ka, kb = table_a["keys"], table_b["keys"]
    return {k: round(kb[k] / ka[k], 4) for k in ("hand_length", "hand_width", "foot_length", "foot_width")}


def b_target(s: dict, bones: dict, ring_a_m: float, scale: float) -> tuple[dict, dict]:
    """B1's target for B's rest with fit.toml's joints: the shifts solved from A's bones (metres); checked with
    zero shifts (B1's check allows no inward hip shift, and B's hips move about 1 mm in)."""
    t = {"name": "d3b", "note": "D3's rest for B",
         "height": {"scale": scale, "ring_z": ring_a_m, "lock_from_z": ring_a_m - 0.06},
         "arms": {"shift_in_m": 0.0, "shoulder_axial": 0.85, "upper_radial": 1.0, "lower_radial": 1.0,
                  "hand_scale": 1.0},  # the hands are scaled per axis after (`hands`)
         "legs": {"shift_out_m": 0.0, "upper_radial": 1.0, "lower_radial": 1.0, "foot_scale": scale},
         "profile": {"z": [0.5, 1.0], "scale": [1.0, 1.0]},
         "chest": {"amount_m": 0.0, "z": 1.1, "half_z": 0.1, "x": 0.05, "half_x": 0.07, "ramp_m": 0.05},
         "seat": {"amount_m": 0.0, "z": 0.8, "half_z": 0.1, "x": 0.06, "half_x": 0.1, "ramp_m": 0.05},
         "mask": {"bones": ["Hips", "Spine", "Chest", "UpperChest", "LeftUpperLeg", "RightUpperLeg"]}}
    r0 = G.rest(bones, G.check(t))
    t["arms"]["shift_in_m"] = round(r0["LeftUpperArm"]["head"][0] - s["shoulder_joint_x"] / 1000, 6)
    t["legs"]["shift_out_m"] = round(s["hip_joint_x"] / 1000 - r0["LeftUpperLeg"]["head"][0], 6)
    return t, {"shift_in_m": t["arms"]["shift_in_m"], "shift_out_m": t["legs"]["shift_out_m"]}


def b_rest(bones: dict, table_a: dict, table_b: dict, s: dict, verts: list | None = None,
           weights: list | None = None) -> tuple[dict, dict, list]:
    """B's rest skeleton (metres) from A's bones, data-driven: the height scale is B's ring over A's, the joints'
    x from fit.toml, the Neck's head `neck_bone_below` under B's ring and the Head's `head_bone_above` over it (the
    bones that ended at the old Neck head end at the new one), the hands and feet by `limb_scales` about the wrists
    and ankles. With A's vertices and weights (metres) B's are deformed with them (B1's `deform`); else []. The
    report holds the scale, the shifts, the limb scales and the key joints in mm."""
    ra, rb = table_a["neck_ring"], table_b["neck_ring"]
    scale = rb["z"] / ra["z"]
    t, shifts = b_target(s, bones, ra["z"] / 1000, scale)
    if verts is not None:
        vb, r0, drep = G.deform(verts, weights, bones, t)
    else:
        vb, r0, drep = [], G.rest(bones, t), {}
    rest = {n: {"head": tuple(r["head"]), "tail": tuple(r["tail"]), "parent": r["parent"]}
            for n, r in r0.items()}  # checked in b_target with zero shifts
    ring = rb["z"] / 1000
    for name, dz in (("Neck", -rb["neck_bone_below"]), ("Head", rb["head_bone_above"])):
        old = rest[name]["head"]
        rest[name]["head"] = (old[0], old[1], ring + dz / 1000)
        for n, r in rest.items():  # the bones that ended at its head on A (the parent's tail) end at the new one
            if math.dist(bones[n]["tail"], bones[name]["head"]) < 1e-6:
                r["tail"] = rest[name]["head"]
    ls = limb_scales(table_a, table_b)
    if vb:
        vb = hands(vb, weights, rest, ls["hand_length"], ls["hand_width"])
        vb = feet(vb, weights, rest, ls["foot_width"] / scale, ls["foot_length"] / scale)
    else:
        hands([], [], rest, ls["hand_length"], ls["hand_width"])
        feet([], [], rest, ls["foot_width"] / scale, ls["foot_length"] / scale)
    rep = {"height_scale": round(scale, 6), "shifts": shifts, "limb_scales": ls, "deform": drep,
           "joints_mm": {n: [round(c * 1000, 1) for c in rest[n]["head"]] for n in
                         ("LeftShoulder", "LeftUpperArm", "LeftHand", "LeftUpperLeg", "LeftFoot", "LeftToes",
                          "Neck", "Head")},
           "ring_mm": rb["z"]}
    return rest, rep, vb


def _scale_about(p, a, u, sl: float, sw: float):
    """p scaled about a: by sl along the unit axis u, by sw across it."""
    d = [p[i] - a[i] for i in range(3)]
    along = sum(d[i] * u[i] for i in range(3))
    return tuple(a[i] + sl * along * u[i] + sw * (d[i] - along * u[i]) for i in range(3))


def keep_directions(rest: dict, names: list, place) -> None:
    """The bones `names` re-placed in `rest` (in place) by the mesh's per-axis scale `place` (a point -> its new
    place), each keeping its own rest direction (the contract: B's bones turn at most rest_turn_max_deg against A's;
    D3g's per-axis scale turned the Foot 2.7 and the thumbs 2.5 degrees). Each head is `place` of its own (the joints
    stay where the mesh's are: the toe joint, the thumb's knuckles, and the forefoot's cut that `apply` takes from the
    Toes head); each tail lies along the bone's old direction, the length the scale gives it along that direction
    (`place`'s move projected on it). A chain's tail then misses its child's head by a few mm (B's Foot 8 mm, the
    thumbs 1.6); Blender's bones are unconnected here and glTF carries no tails, so only heads and directions count."""
    for n in names:
        h, t = tuple(rest[n]["head"]), tuple(rest[n]["tail"])
        d = [t[i] - h[i] for i in range(3)]
        ln = math.sqrt(sum(c * c for c in d)) or 1.0
        u = [c / ln for c in d]
        ph, pt = place(h), place(t)
        nl = sum((pt[i] - ph[i]) * u[i] for i in range(3))
        rest[n]["head"], rest[n]["tail"] = tuple(ph), tuple(ph[i] + nl * u[i] for i in range(3))


def hands(verts: list, weights: list, rest: dict, sl: float, sw: float) -> list:
    """The hands scaled about their wrists (the Hand bone's head; metres): by sl along the Hand bone, by sw across
    it, by the vertices' hand weights; the hands' bones (the Hand and its digits) with them, each along its own
    direction (`keep_directions`)."""
    axes = {}
    for side in ("Left", "Right"):
        h, t = rest[f"{side}Hand"]["head"], rest[f"{side}Hand"]["tail"]
        n = math.dist(h, t)
        axes[side] = (tuple(h), tuple((t[i] - h[i]) / n for i in range(3)))
    out = []
    for p, w in zip(verts, weights):
        f = F.hand_share(w)
        if f <= 0:
            out.append(tuple(p))
            continue
        a, u = axes["Left" if p[0] >= 0 else "Right"]
        q = _scale_about(p, a, u, sl, sw)
        out.append(tuple(p[i] + f * (q[i] - p[i]) for i in range(3)))
    for side in ("Left", "Right"):
        a, u = axes[side]
        names = [n for n in rest if n.startswith(side) and F.hand_share({n: 1.0}) > 0]
        keep_directions(rest, names, lambda p, a=a, u=u: _scale_about(p, a, u, sl, sw))
    return out


def feet(verts: list, weights: list, rest: dict, sx: float, sy: float) -> list:
    """The feet scaled about their ankles (x by sx, y by sy; metres), by the vertices' foot weights; the feet's
    bones with them, each along its own direction (`keep_directions`: the toe joint lands on the Foot bone's line,
    a few mm off the mesh's own)."""
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
        keep_directions(rest, [f"{side}Foot", f"{side}Toes"],
                        lambda p, a=a: (a[0] + sx * (p[0] - a[0]), a[1] + sy * (p[1] - a[1]), p[2]))
    return out


def arms_moved(rest: dict, dy_mm: float) -> dict:
    """The rest with the shoulder chains (the Shoulder, the upper arm to the fingertips) moved rigidly by dy_mm in y
    (the arms' mesh move, `arm_shift_mm`; metres in and out): every bone keeps its direction (D3g moved only the
    Shoulder's tail and turned it 15 degrees)."""
    out = {n: dict(r) for n, r in rest.items()}
    dy = dy_mm / 1000.0
    for n, r in out.items():
        if F.arm_share({n: 1.0}) > 0 or (n.endswith("Shoulder") and n.startswith(("Left", "Right"))):
            r["head"] = (r["head"][0], r["head"][1] + dy, r["head"][2])
            r["tail"] = (r["tail"][0], r["tail"][1] + dy, r["tail"][2])
    return out


def rest_turns(a: dict, b: dict) -> dict:
    """Per bone of A the angle (degrees) between its rest direction on A and on B (heads and tails, any one unit)."""
    out = {}
    for n, ra in a.items():
        u = [ra["tail"][i] - ra["head"][i] for i in range(3)]
        v = [b[n]["tail"][i] - b[n]["head"][i] for i in range(3)]
        c = sum(x * y for x, y in zip(u, v)) / (math.sqrt(sum(x * x for x in u)) * math.sqrt(sum(y * y for y in v)))
        out[n] = math.degrees(math.acos(max(-1.0, min(1.0, c))))
    return out


def rest_turn_max() -> float:
    """The contract's largest rest turn of a B bone against A's (degrees)."""
    return float(tomllib.loads(CONTRACT.read_text(encoding="utf-8"))["body_types"]["B"]["rest_turn_max_deg"])


def _arm_rows(weights: list) -> dict:
    """Per arm bone (both sides) the vertices weighted at least 0.9 on it."""
    return {f"{sd}{b}": [i for i, w in enumerate(weights) if w.get(f"{sd}{b}", 0.0) >= 0.9]
            for sd in ("Left", "Right") for b in ARM_BONES}


def arm_shift_mm(before: list, after: list, weights: list) -> float:
    """The arms' mean move in y over the vertices weighted at least 0.9 on an arm bone (`before` and `after` in mm):
    what the fit did to the arms' mesh, every pass and refit together (D3g summed only the reported passes' arm_dy,
    -35.4 mm against the mesh's -14.9, and left B's arm bones about 20 mm in front of her arms)."""
    idx = [i for v in _arm_rows(weights).values() for i in v]
    return sum(after[i][1] - before[i][1] for i in idx) / max(1, len(idx))


def arm_offsets(verts: list, weights: list, bones: dict) -> dict:
    """Per arm bone the mean (y, z) of its vertices (weighted at least 0.9 on it) minus its middle's; one unit."""
    out = {}
    for n, idx in _arm_rows(weights).items():
        if idx:
            b = bones[n]
            out[n] = tuple(sum(verts[i][k] for i in idx) / len(idx) - (b["head"][k] + b["tail"][k]) / 2
                           for k in (1, 2))
    return out


def chest_of(table: dict, s: dict) -> dict:
    """The chest rounds' settings: the table's chest keys, its side front, fit.toml's spread across x."""
    c, t = table["chest"], table["trunk"]
    front = F.Profile(t["z"], [F.num(v) for v in t["front_y"]], sigma=4.0)
    return {"under_z": c["under_z"], "top_z": c["top_z"], "under_f": front(c["under_z"]), "top_f": front(c["top_z"]),
            "front": front, "centre_x": c["centre_x"], "sigma_x": s["chest_sigma_x"], "floor": s["chest_floor"]}


def run_fit(name: str, verts_mm: list, weights: list, edges: list, bones: dict, ring: list, s: dict,
            chest: dict | None, base: list | None = None) -> tuple[list, dict]:
    table = F.load_table(DIMS / f"{name}.toml")
    wa = [F.arm_share(w) for w in weights]
    table["fit"] = {"keep_front": s.get("keep_front", []), "neck_base": s.get("neck_base"),
                    "arm_follow": s.get("arm_follow", False), "girdle": s.get("girdle"),
                    "arm_low": min(p[2] for p, a in zip(verts_mm, wa) if a >= 0.5)}
    fr = F.frame_of(table, bones, 0.0)
    au = F.armpit_u(verts_mm, edges, weights, fr["armpit"] - 5.0)
    v, reps, dys = verts_mm, [], []
    before = F.errors(v, weights, edges, table, bones, au, chest)
    for _ in range(2):
        v, rep = F.fit(v, weights, edges, table, bones, au, ring, chest)
        reps.append(rep)
        dys.append(rep["arm_dy_mm"])
    if s.get("shoulder_lift"):  # D3d: B's shoulder tops toward her concept's slope, after the station passes
        v, lift = F.shoulder_lift(v, ring, table, s["shoulder_lift"], edges=edges)
        reps.append({"shoulder_lift": lift})
    rl = s.get("relax")
    if rl and base is not None:  # D3f: the moves diffused over the mesh (the regions' hard edges); the ring, hands
        # and feet keep theirs. The diffusion also blurs the fit's sizes, so `refits` rounds of one station pass (its
        # small corrections) and a shorter diffusion (`rounds_after`) follow.
        fixed = set(ring) | {i for i, w in enumerate(weights) if F.hand_share(w) > 0 or F.foot_share(w) > 0.5}
        v = F.relax_moves(base, v, edges, fixed, rl["rounds"], rl.get("lam", 0.5))
        for _ in range(rl.get("refits", 0)):
            v, rep = F.fit(v, weights, edges, table, bones, au, ring, chest)
            dys.append(rep["arm_dy_mm"])
            v = F.relax_moves(base, v, edges, fixed, rl["rounds_after"], rl.get("lam", 0.5))
        reps.append({"relax": rl})
    if s.get("neck_tangent"):  # D3f: the body leaves the ring at the seated head's tangent (no turtleneck flare)
        v, nt = F.neck_tangent(v, weights, ring, s["neck_tangent"])
        reps.append({"neck_tangent": nt})
    sr = s.get("shoulder_round")
    if sr:  # D3g: B's girdle corner (the diagonal from the neck base to each armpit, her boxy deltoid) rounded
        rz = table["neck_ring"]["z"]
        keep = set(ring)
        share = {i: w for i, p in enumerate(v) if i not in keep and F.hand_share(weights[i]) == 0
                 and (w := F.shoulder_share(p, rz, sr)) > 0}
        v = F.taubin(v, edges, share, sr["rounds"], mu=sr.get("mu", -0.53))  # mu 0: plain rounds, a corner shrinks
        reps.append({"shoulder_round": {**sr, "vertices": len(share)}})
    if chest is not None and s.get("chest_trim"):  # D3e: the rounds' apex to the table
        mid = F.errors(v, weights, edges, table, bones, au, chest)
        v = F.chest_trim(v, weights, mid["rows"]["trunk"], chest)
    err = F.errors(v, weights, edges, table, bones, au, chest)
    err["before"] = before["summary"]
    err["passes"] = reps
    err["arm_dy_fit_mm"] = [round(x, 3) for x in dys]  # every F.fit call's, the refits' too
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
              "(`rule`): the neck taper, the shoulders over the armpit (T arms), B's neck base (the ring row down to the "
              "shoulder line), the kept front, the feet, the arm root.", ""]
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
    va, ea = run_fit("A", mm(d["verts"]), weights, edges, bones_mm(bones_m), ring, settings["A"], None,
                     mm(d["verts"]))
    o = out / "A"
    o.mkdir(parents=True, exist_ok=True)
    fit = {"verts": [[round(c / 1000, 7) for c in p] for p in va], "ring": ring, "rest": None}
    (o / "fit.json").write_text(json.dumps(fit), encoding="utf-8")
    (o / "errors.json").write_text(json.dumps(ea, indent=1), encoding="utf-8", newline="\n")
    (o / "errors.md").write_text(table_md("A", ea), encoding="utf-8", newline="\n")
    print(table_md("A", ea))
    sb = settings["B"]
    tb = F.load_table(DIMS / "B.toml")
    va_m = [tuple(c / 1000 for c in p) for p in va]
    rest, rep, vb = b_rest(bones_m, F.load_table(DIMS / "A.toml"), tb, sb, va_m, weights)
    rest_out = {n: {"head": list(r["head"]), "tail": list(r["tail"]), "parent": r["parent"]} for n, r in rest.items()}
    vb_mm = mm(vb)
    vbf, eb = run_fit("B", vb_mm, weights, edges, bones_mm(rest_out), ring, sb, chest_of(tb, sb),
                     mm(d["verts"]))
    rep["arm_dy_fit_mm"] = round(sum(eb["arm_dy_fit_mm"]), 3)
    rep["arm_dy_mm"] = round(arm_shift_mm(vb_mm, vbf, weights), 3)
    rest_out = arms_moved(rest_out, rep["arm_dy_mm"])
    turns = rest_turns(bones_m, rest_out)
    worst = max(turns, key=turns.get)
    rep["rest_turn_max_deg"], rep["rest_turn_worst"] = round(turns[worst], 4), worst
    oa, ob = arm_offsets(va, weights, bones_mm(bones_m)), arm_offsets(vbf, weights, bones_mm(rest_out))
    sw = {n: rep["limb_scales"]["hand_width"] if n.endswith("Hand") else 1.0 for n in ob}  # the hand's own scale
    rep["arm_offset_vs_a_mm"] = {n: [round(ob[n][k] - sw[n] * oa[n][k], 2) for k in (0, 1)] for n in ob}
    off_y = max(abs(v[0]) for v in rep["arm_offset_vs_a_mm"].values())
    ok = turns[worst] <= rest_turn_max() and off_y <= ARM_OFFSET_MAX_MM
    rep["ok"] = ok
    eb["b_rest"] = rep
    o = out / "B"
    o.mkdir(parents=True, exist_ok=True)
    fit = {"verts": [[round(c / 1000, 7) for c in p] for p in vbf], "ring": ring, "rest": rest_out}
    (o / "fit.json").write_text(json.dumps(fit), encoding="utf-8")
    (o / "rest.json").write_text(json.dumps({"rest": rest_out, "report": rep}, indent=1), encoding="utf-8",
                                 newline="\n")
    (o / "errors.json").write_text(json.dumps(eb, indent=1), encoding="utf-8", newline="\n")
    (o / "errors.md").write_text(table_md("B", eb), encoding="utf-8", newline="\n")
    print(table_md("B", eb))
    print("B_REST", json.dumps(rep))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
