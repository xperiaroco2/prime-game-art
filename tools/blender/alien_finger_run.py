"""The fingers rebuilt as smooth tubes: the plain-Python driver (art #196, Hands H1i; alien_finger_geom.py the maths,
alien_hand_mesh.py the Blender dump and apply, body_dims/hand_dims.toml the spec).

    python tools/blender/alien_finger_run.py measure --dump <dump.json>... --spec <hand_dims.toml> --out <dir>
    python tools/blender/alien_finger_run.py build --dump <dump.json> --spec <hand_dims.toml> --out <dir>

- `measure`: per dump, side and digit the radius along the finger per angle sector, its wave (the largest residual
  from an 8 mm Gaussian trend between the root and the dome) and where the worst residuals sit against the joints;
  `<out>/measure.json`.
- `build`: per side the thumb and the three fingers rebuilt (alien_finger_geom.tube_finger; one root radius per digit,
  the mean of both sides), the chain weights redone from the bones past the ramp (`[fingers] joint_blend`);
  `<out>/moves_body.json` (positions and weights, for alien_hand_mesh.py apply), `<out>/build.json` (per digit the
  wave before and after, the largest move, the weights' largest change) and `<out>/profile_<side>.png` (per digit the
  radius along it per sector, before | after, the residual magnified 5x below); exit 1 when a wave stays above
  `wave_max_mm` or a vertex with a LowerArm weight moved.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_finger_geom as F  # noqa: E402
import alien_hand_geom as G  # noqa: E402
from alien_grip_solve import Canvas  # noqa: E402

SIDES = ("Left", "Right")
DIGITS = {"Thumb": ("Metacarpal", "Proximal", "Distal"), "Index": ("Proximal", "Intermediate", "Distal"),
          "Middle": ("Proximal", "Intermediate", "Distal"), "Ring": ("Proximal", "Intermediate", "Distal")}
COLOURS = [(200, 40, 40), (220, 130, 20), (170, 170, 0), (40, 160, 40), (20, 150, 170), (40, 70, 210),
           (130, 50, 190), (200, 60, 150)]


def skin(dump):
    objs = [o for o in dump["objects"] if any("skin" in m.lower() or m == "M_AlienBody" for ms in o["mat"] for m in ms)]
    return max(objs or dump["objects"], key=lambda o: len(o["index"]))


def side_of(dump, p, side):
    return p[0] * dump["bones"][f"{side}Hand"]["head"][0] > 0


def chain(dump, side, digit):
    b = dump["bones"]
    names = [f"{side}{digit}{s}" for s in DIGITS[digit]]
    return names, [b[names[0]]["head"]] + [b[n]["tail"] for n in names], b[names[0]]["z"]


def spec_of(spec, digit, L):
    s = dict(spec["thumb" if digit == "Thumb" else "fingers"])
    s["root_at"] *= L
    s["ramp"] = [x * L for x in s["ramp"]]
    return s


def hand_len(dump, side):
    h = dump["bones"][f"{side}Hand"]
    return math.dist(h["head"], h["tail"])


def digit_samples(dump, obj, side, digit, L, spec):
    names, joints, up = chain(dump, side, digit)
    ax = F.Axis(joints, up)
    out = []
    for i, p, w in zip(obj["index"], obj["co"], obj["w"]):
        if side_of(dump, p, side) and sum(w.get(n, 0) for n in names) >= 0.5:
            out.append((i, ax.closest(p)))
    return ax, out


def root_radius(samples, root_at):
    rs = sorted(r for _, (s, a, r) in samples if root_at <= s <= root_at + 0.012)
    return rs[len(rs) // 2] if rs else 0.0


def measure(dumps, spec_path, out):
    spec = tomllib.loads(Path(spec_path).read_text())
    rep = {}
    for path in dumps:
        dump = json.loads(Path(path).read_text())
        obj = skin(dump)
        r = rep[Path(path).stem] = {}
        for side in SIDES:
            L = hand_len(dump, side)
            for digit in DIGITS:
                sp = spec_of(spec, digit, L)
                ax, smp = digit_samples(dump, obj, side, digit, L, sp)
                tip = max(s for _, (s, a, rr) in smp)
                r_end = root_radius(smp, sp["root_at"]) * (1 - sp["taper"])
                worst, rows = F.wave([x for _, x in smp], sp["root_at"], tip - r_end - 0.002)
                peaks = sorted(((abs(rr - tr), s) for _, prof in rows for s, rr, tr in prof
                                if sp["root_at"] + 0.004 <= s <= tip - r_end - 0.006), reverse=True)[:5]
                r[f"{side}{digit}"] = {"wave_mm": round(worst * 1000, 2), "verts": len(smp),
                                       "joints_mm": [round(x * 1000, 1) for x in ax.joint_s],
                                       "peaks_at_mm": [[round(s * 1000, 1), round(d * 1000, 2)] for d, s in peaks]}
        print(Path(path).stem, {k: v["wave_mm"] for k, v in r.items()})
    Path(out).mkdir(parents=True, exist_ok=True)
    Path(out, "measure.json").write_text(json.dumps(rep, indent=1))
    return 0


def panel(cv, x0, y0, w, h, rows, tube, title, lo, hi):
    """A profile panel: radius (mm) along s per sector; the residual from the trend magnified 10x below."""
    cv.line((x0, y0), (x0 + w, y0), (180, 180, 180))
    cv.line((x0, y0 + h), (x0 + w, y0 + h), (180, 180, 180))
    cv.text(x0 + 4, y0 + 4, title)
    sx = lambda s: x0 + 10 + (s - lo) / max(1e-6, hi - lo) * (w - 20)  # noqa: E731
    sy = lambda r: y0 + h * 0.62 - (r * 1000 - 12) * 12  # noqa: E731  12 px per mm about 12 mm
    ry = lambda d: y0 + h * 0.85 - d * 1000 * 60  # noqa: E731  the residual: 60 px per mm (0.3 mm = 18 px)
    for g in (-0.3, 0.3):
        cv.line((x0 + 10, ry(g / 1000)), (x0 + w - 10, ry(g / 1000)), (230, 200, 200))
    cv.line((x0 + 10, ry(0)), (x0 + w - 10, ry(0)), (210, 210, 210))
    for k, prof in rows:
        c = COLOURS[k % len(COLOURS)]
        for s, r, tr in prof:
            if lo <= s <= hi:
                cv.dot(sx(s), sy(r), c, 1)
                cv.dot(sx(s), ry(r - tr), c, 1)


def build(dump_path, spec_path, out):
    dump = json.loads(Path(dump_path).read_text())
    spec = tomllib.loads(Path(spec_path).read_text())
    obj = skin(dump)
    pos = {i: tuple(p) for i, p in zip(obj["index"], obj["co"])}
    wts = {i: w for i, w in zip(obj["index"], obj["w"])}
    other = {i: x for i, x in zip(obj["index"], obj["other"])}
    adj = G.adjacency(None, obj["edges"])
    blend = spec["fingers"].get("joint_blend", 0.5)
    wave_max = spec["fingers"].get("wave_max_mm", 0.3)
    roots = {}
    for digit in DIGITS:
        rr = []
        for side in SIDES:
            L = hand_len(dump, side)
            rr.append(root_radius(digit_samples(dump, obj, side, digit, L, spec_of(spec, digit, L))[1],
                                  spec_of(spec, digit, L)["root_at"]))
        roots[digit] = sum(rr) / len(rr)
    after = dict(pos)
    neww, rep, ok = {}, {"dump": dump_path, "object": obj["name"], "digits": {}}, True
    plots = {}
    for side in SIDES:
        L = hand_len(dump, side)
        for digit in DIGITS:
            names, joints, up = chain(dump, side, digit)
            sp = spec_of(spec, digit, L)
            share = {i: sum(wts[i].get(n, 0) for n in names) for i in pos if side_of(dump, pos[i], side)}
            fp = {i: after[i] for i in share if share[i] > 0}
            new, tube, r = F.tube_finger(fp, share, adj, joints, up, sp, roots[digit])
            after.update(new)
            # the weights from the bones past the ramp, on the vertices weighted on this chain only
            wch = 0.0
            for i in new:
                s, a, rad = tube.ax.closest(new[i])
                if share[i] >= 0.999 and other[i] < 1e-3 and s >= sp["ramp"][1]:
                    w = F.joint_weights(s, tube.ax.joint_s, names, tube.radius(s), blend)
                    wch = max([wch] + [abs(w.get(n, 0) - wts[i].get(n, 0)) for n in names])
                    neww[i] = w
            r["weights_largest_change"] = round(wch, 3)
            ok &= r["wave_after_mm"] <= wave_max
            rep["digits"][f"{side}{digit}"] = r
            mine = [i for i in fp if share[i] >= 0.5]
            hi = tube.s_c - 0.002
            plots[(side, digit)] = (F.wave([tube.local(pos[i]) for i in mine], sp["root_at"], hi)[1],
                                    F.wave([tube.local(after[i]) for i in mine], sp["root_at"], hi)[1],
                                    tube, sp["root_at"], hi, r)
            print(side, digit, r, flush=True)
    moved = {i: after[i] for i in pos if math.dist(after[i], pos[i]) > 1e-7}
    arm = [i for i in moved if any("LowerArm" in k for k in wts[i])]
    rep["lowerarm_moved"] = len(arm)
    ok &= not arm
    rep["moved"], rep["reweighted"], rep["ok"] = len(moved), len(neww), bool(ok)
    Path(out).mkdir(parents=True, exist_ok=True)
    Path(out, "moves_body.json").write_text(json.dumps({
        "objects": {obj["name"]: {str(i): [round(c, 6) for c in p] for i, p in moved.items()}},
        "weights": {obj["name"]: {str(i): {k: round(x, 5) for k, x in w.items()} for i, w in neww.items()}}}))
    Path(out, "build.json").write_text(json.dumps(rep, indent=1))
    for side in SIDES:
        W, Hh = 560, 230
        cv = Canvas(2 * W + 30, len(DIGITS) * (Hh + 20) + 40)
        cv.text(10, 10, f"{side} hand: radius along the finger per sector (top) and its residual x5 (bottom, red lines 0.3 mm)")
        for row, digit in enumerate(DIGITS):
            before, aft, tube, lo, hi, r = plots[(side, digit)]
            y = 40 + row * (Hh + 20)
            panel(cv, 10, y, W, Hh, before, tube, f"{digit} before bump {r['wave_before_mm']} mm", lo, hi)
            panel(cv, 20 + W, y, W, Hh, aft, tube, f"{digit} after bump {r['wave_after_mm']} mm", lo, hi)
        cv.save(Path(out, f"profile_{side}.png"))
    print("moved", len(moved), "reweighted", len(neww), "lowerarm moved", len(arm), "ok", ok)
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(prog="alien_finger_run.py")
    ap.add_argument("mode", choices=("measure", "build"))
    ap.add_argument("--dump", nargs="+", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.mode == "measure":
        return measure(a.dump, a.spec, a.out)
    return build(a.dump[0], a.spec, a.out)


if __name__ == "__main__":
    sys.exit(main())
