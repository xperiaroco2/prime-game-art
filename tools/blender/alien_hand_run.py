"""The hand and wrist rebuilt in place: the plain-Python driver (art #196, Hands H1b; alien_hand_geom.py the maths,
alien_hand_mesh.py the Blender dump and apply, body_dims/hand_dims.toml the spec).

    python tools/blender/alien_hand_run.py build --dump <body dump.json> --spec <hand_dims.toml> --out <dir>
        [--transfer <name>=<char dump.json> ...]
    python tools/blender/alien_hand_run.py table --dump <dump with --bend> --out <table.json>

- `build`: the moves for the body's skin (`<out>/moves_body.json`), one moves file per `--transfer` character (the
  body's moved vertices found in the character's skin objects by their rest position, within 0.1 mm), the report
  `<out>/build.json` (per side the band's extents along the arm before and after, the largest row gap, each finger's
  root and end diameter); exit 1 when a spec check fails.
- `table`: per side and bend the wrist joint's section (width, thickness, hull area, deepest fold) at rest and bent
  (the plane halfway between the forearm and the bent hand); exit 1 above the spec's `fold_max_mm` when `--spec`.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_hand_geom as G  # noqa: E402

SIDES = ("Left", "Right")
FINGERS = {"Thumb": ("Metacarpal", "Proximal", "Distal"), "Index": ("Proximal", "Intermediate", "Distal"),
           "Middle": ("Proximal", "Intermediate", "Distal"), "Ring": ("Proximal", "Intermediate", "Distal")}


def skin_objects(dump: dict) -> list:
    return [o for o in dump["objects"] if any("skin" in m.lower() or m == "M_AlienBody" for ms in o["mat"] for m in ms)
            or o["name"] == "Body"]


def side_of(dump, p, side):
    hx = dump["bones"][f"{side}Hand"]["head"][0]
    return p[0] * hx > 0


def side_frame(dump: dict, side: str):
    b = dump["bones"]
    lo, hand = b[f"{side}LowerArm"], b[f"{side}Hand"]
    return hand["head"], G.frame(G.sub(lo["tail"], lo["head"]), hand["z"]), math.dist(hand["head"], hand["tail"])


def finger_root_side(dump, pos, wts, side, f, segs, root_at) -> float:
    b = dump["bones"]
    chain = [f"{side}{f}{s}" for s in segs]
    pts = [b[chain[0]]["head"]] + [b[c]["tail"] for c in chain]
    mine = {i: pos[i] for i in pos if side_of(dump, pos[i], side)}
    share = {i: sum(wts[i].get(c, 0) for c in chain) for i in mine}
    return G.finger_root(mine, share, pts, root_at)


def band_table(pos, edges, origin, fr) -> list:
    """The section's width and thickness (mm) every 5 mm from 60 mm behind the joint to 60 mm past it."""
    rows = []
    for k in range(-12, 13):
        m = G.slice_extents(pos, edges, origin, fr, k * 0.005)
        if m:
            rows.append([k * 5, round(m[2] * 2000, 1), round(m[3] * 2000, 1)])
    return rows


def monotone_ok(rows, s_fore_mm, s_palm_mm, tol=1.5) -> bool:
    """The width falls (within tol mm) from s_fore to 0 and rises from 0 to s_palm."""
    a = [w for s, w, _ in rows if s_fore_mm <= s <= 0]
    b = [w for s, w, _ in rows if 0 <= s <= s_palm_mm]
    return all(y <= x + tol for x, y in zip(a, a[1:])) and all(y >= x - tol for x, y in zip(b, b[1:]))


def build(dump_path: str, spec_path: str, out: str, transfers: list) -> int:
    dump = json.loads(Path(dump_path).read_text())
    spec = tomllib.loads(Path(spec_path).read_text())
    obj = skin_objects(dump)[0]
    pos = {i: p for i, p in zip(obj["index"], obj["co"])}
    wts = {i: w for i, w in zip(obj["index"], obj["w"])}
    adj = G.adjacency(None, obj["edges"])
    roots = {}
    moves, rep, ok = {}, {"dump": dump_path, "object": obj["name"], "sides": {}}, True
    for side in SIDES:
        origin, fr, L = side_frame(dump, side)
        mine = [i for i in pos if side_of(dump, pos[i], side)]
        sp = {i: pos[i] for i in mine}
        ws = {k: (spec["wrist"][k] * L if k in ("s_fore", "s_palm") else spec["wrist"][k]) for k in spec["wrist"]}
        new, r = G.wrist_band(sp, wts, adj, origin, fr, side, ws)
        after = dict(sp)
        after.update(new)
        ids = [i for i in mine if wts[i].get(f"{side}LowerArm", 0) + wts[i].get(f"{side}Hand", 0) >= 0.5
               and sum(x for k, x in wts[i].items() if "Thumb" in k) < 0.5]
        edges = [e for e in obj["edges"] if e[0] in sp and e[1] in sp]
        r["table_before"] = band_table(sp, edges, origin, fr)
        r["table_after"] = band_table(after, edges, origin, fr)
        near = 0.3 * L
        r["row_gap_before_mm"] = G.row_gaps([G.coords(sp[i], origin, fr)[0] for i in ids], -near, near)
        r["row_gap_after_mm"] = G.row_gaps([G.coords(after[i], origin, fr)[0] for i in ids], -near, near)
        r["monotone_after"] = monotone_ok(r["table_after"], ws["s_fore"] * 1000, ws["s_palm"] * 1000)
        r["row_gap_ok"] = r["row_gap_after_mm"] <= spec["wrist"]["row_gap_max_mm"]  # reported: rows need new rings
        ok &= (not spec["wrist"].get("taper_monotone")) or r["monotone_after"]
        r["fingers"] = {}
        b = dump["bones"]
        for f, segs in FINGERS.items():
            chain = [f"{side}{f}{s}" for s in segs]
            pts = [b[chain[0]]["head"]] + [b[c]["tail"] for c in chain]
            share = {i: sum(wts[i].get(c, 0) for c in chain) for i in mine}
            fp = {i: after[i] for i in mine if share[i] > 0}
            fs = dict(spec["thumb" if f == "Thumb" else "fingers"])
            fs["root_at"] *= L
            fs["ramp"] = [x * L for x in fs["ramp"]]
            if f not in roots:  # one root radius per finger for both hands (the mean of the two sides)
                roots[f] = sum(finger_root_side(dump, pos, wts, s2, f, segs, fs["root_at"]) for s2 in SIDES) / 2
            fs["root_radius"] = roots[f]
            nf, fr_ = G.finger(fp, share, pts, fs)
            after.update(nf)
            new.update(nf)
            r["fingers"][f] = fr_
        moves.update({i: [round(c, 6) for c in new[i]] for i in new})
        rep["sides"][side] = r
    Path(out).mkdir(parents=True, exist_ok=True)
    Path(out, "moves_body.json").write_text(json.dumps({"objects": {obj["name"]: {str(i): p for i, p in moves.items()}}}))
    key = {tuple(round(c, 4) for c in pos[i]): i for i in moves}
    for t in transfers:
        name, path = t.split("=", 1)
        cd = json.loads(Path(path).read_text())
        cm, found = {}, set()
        for o in skin_objects(cd):
            mv = {}
            for i, p in zip(o["index"], o["co"]):
                j = key.get(tuple(round(c, 4) for c in p))
                if j is not None:
                    mv[str(i)] = moves[j]
                    found.add(j)
            if mv:
                cm[o["name"]] = mv
        Path(out, f"moves_{name}.json").write_text(json.dumps({"objects": cm}))
        rep.setdefault("transfers", {})[name] = {"objects": {k: len(v) for k, v in cm.items()},
                                                 "body_moves_found": len(found), "body_moves": len(moves)}
    rep["moved"] = len(moves)
    rep["ok"] = bool(ok)
    Path(out, "build.json").write_text(json.dumps(rep, indent=1))
    for side, r in rep["sides"].items():
        print(side, "band", r["band"], "fore", r["fore_mm"], "wrist target", r["wrist_target_mm"], "palm", r["palm_mm"],
              "row gap", r["row_gap_before_mm"], "->", r["row_gap_after_mm"], "monotone", r["monotone_after"])
        print("  s/w/t before", r["table_before"])
        print("  s/w/t after ", r["table_after"])
        for f, fr_ in r["fingers"].items():
            print("  ", f, fr_)
    print("transfers", rep.get("transfers"), "ok", ok)
    return 0 if ok else 1


def table(dump_path: str, out: str, spec_path: str = "") -> int:
    dump = json.loads(Path(dump_path).read_text())
    objs = skin_objects(dump)
    res, worst = {}, 0.0
    for side in SIDES:
        origin, (d, u, v), L = side_frame(dump, side)
        keys = ["rest"] + sorted(k for k in dump.get("bends", {}) if k.startswith(side))
        for key in keys:
            pts = []
            if key == "rest":
                n = d
            else:
                tail = dump["bends"][key]["_tail"]
                n = G.norm(G.add(d, G.norm(G.sub(tail, origin))))
            uu = G.norm(G.sub(u, G.mul(n, G.dot(u, n))))
            vv = G.cross(n, uu)
            secs = []
            for off in (-0.015, 0.0, 0.015, 0.03):
                pts = []
                for o in objs:
                    cos = o["co"] if key == "rest" else dump["bends"][key][o["name"]]
                    pos = {i: p for i, p in zip(o["index"], cos) if p[0] * origin[0] > 0}
                    pts += G.slice_points(pos, o["edges"], G.add(origin, G.mul(n, off)), n, uu, vv, 0.07)
                secs.append(dict(G.section(pts), at_mm=round(off * 1000)))
            sec = max(secs, key=lambda x: x.get("fold_mm", 0))
            sec["joint"] = secs[1]
            sec = G.section(pts)
            res[key] = sec
            if key != "rest":
                worst = max(worst, sec.get("fold_mm", 0))
    res["worst_bent_fold_mm"] = worst
    Path(out).write_text(json.dumps(res, indent=1))
    for k, v in res.items():
        print(k, v)
    if spec_path:
        lim = tomllib.loads(Path(spec_path).read_text())["wrist"]["fold_max_mm"]
        return 0 if worst <= lim else 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="alien_hand_run.py")
    ap.add_argument("mode", choices=("build", "table"))
    ap.add_argument("--dump", required=True)
    ap.add_argument("--spec", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--transfer", action="append", default=[])
    a = ap.parse_args()
    if a.mode == "build":
        return build(a.dump, a.spec, a.out, a.transfer)
    return table(a.dump, a.out, a.spec)


if __name__ == "__main__":
    sys.exit(main())
