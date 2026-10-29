"""Bodies by drawing, step D3 (art #196): the station fit of our smooth body to its mm dims table, pure maths (no
bpy; tests in tools/tests/test_body_fit_geom.py). body_fit_blend.py dumps and applies, body_fit_run.py drives.

The body's frame: x lateral, z up from the sole, the front at -y; the tables (tools/blender/body_dims/<A|B>.toml)
are in mm, the dumps in metres; everything here is mm.

The fit moves every vertex by a blend of three maps, by its weights (the arm's share `wa`, the foot's `wf`):
- the trunk (z over the crotch): per height, x about the midline to the table's front width, the front half of y
  to `front_y` and the back half to `back_y`, each about the section's middle; above the armpit x is kept (the T
  arms; the shoulder caps' outline is not comparable with the concept's hanging arms) up to the neck, whose widths
  come back over the 60 mm under the ring;
- the legs (z under the crotch): per height, each leg's x about its own section middle to the table's width (our
  legs stay vertical, the concept's splay is not copied), y as the trunk; a band around the crotch blends them; the
  feet (their weights) are kept;
- the arms (the T rest, along |x|): the table's s from the armpit to the wrist onto ours, each section scaled round
  about its middle to the table's width; the hands are kept.
A ratio of the table's (smoothed) value over the body's own at each station is smoothed again along the body, so
no station leaves a ridge. The 30 mm under the neck ring blend back to the body as it is, and the ring's vertices
stay exact. `keep_front` heights keep the body's own front (body A's belly behind the concept's arm).
"""
from __future__ import annotations

import bisect
import math
import tomllib
from pathlib import Path

ARM = ("UpperArm", "LowerArm", "Hand", "Thumb", "Index", "Middle", "Ring", "Little")
FOOT = ("Foot", "Toes")


def load_table(path: str | Path) -> dict:
    return tomllib.loads(Path(path).read_text(encoding="utf-8"))


def ramp(t: float) -> float:
    """smoothstep from 0 (t <= 0) to 1 (t >= 1)."""
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def num(v):
    return v if isinstance(v, (int, float)) else None


def interp(xs: list, ys: list, x: float) -> float:
    """Linear in sorted xs, held flat past the ends."""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    i = bisect.bisect_right(xs, x)
    x0, x1, y0, y1 = xs[i - 1], xs[i], ys[i - 1], ys[i]
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0) if x1 > x0 else y0


def smooth(xs: list, ys: list, sigma: float) -> list:
    """A Gaussian smoothing over irregular samples; None values are skipped and stay None."""
    out = []
    for x in xs if sigma > 0 else []:
        sw = sv = 0.0
        for x2, y2 in zip(xs, ys):
            if y2 is None or abs(x2 - x) > 3 * sigma:
                continue
            w = math.exp(-0.5 * ((x2 - x) / sigma) ** 2)
            sw, sv = sw + w, sv + w * y2
        out.append(sv / sw if sw > 0 else None)
    return out if sigma > 0 else list(ys)


def series(xs: list, ys: list) -> tuple[list, list]:
    """The (x, y) pairs whose y is a number, as two lists."""
    p = [(x, y) for x, y in zip(xs, ys) if y is not None]
    return [a for a, _ in p], [b for _, b in p]


def _limb(b: str) -> str:
    return b[4:] if b.startswith("Left") else b[5:] if b.startswith("Right") else ""


def arm_share(w: dict) -> float:
    """The vertex's weight on an arm's bones (the upper arm to the fingertips), at most 1."""
    return min(1.0, sum(v for b, v in w.items() if _limb(b).startswith(ARM)))


def foot_share(w: dict) -> float:
    """The vertex's weight on a foot's bones, at most 1."""
    return min(1.0, sum(v for b, v in w.items() if _limb(b) in FOOT))


def sections(verts: list, edges: list, keep, axis: int, stations: list) -> list:
    """Per station the points where the kept edges cross the plane coordinate[axis] = station."""
    st = sorted(stations)
    out = {s: [] for s in st}
    for a, b in edges:
        if not keep(a, b):
            continue
        p, q = verts[a], verts[b]
        lo, hi = (p, q) if p[axis] <= q[axis] else (q, p)
        if hi[axis] - lo[axis] <= 1e-9:
            continue
        i = bisect.bisect_left(st, lo[axis])
        while i < len(st) and st[i] <= hi[axis]:
            s = st[i]
            t = (s - lo[axis]) / (hi[axis] - lo[axis])
            out[s].append(tuple(lo[k] + t * (hi[k] - lo[k]) for k in range(3)))
            i += 1
    return [out[s] for s in stations]


def map_y(y: float, c: float, f0: float, b0: float, f1: float, b1: float) -> float:
    """The front half (y < c) from f0 to f1, the back half from b0 to b1, both about c."""
    if y < c:
        return c + (y - c) * (f1 - c) / (f0 - c) if f0 < c else y
    return c + (y - c) * (b1 - c) / (b0 - c) if b0 > c else y


class Profile:
    """A smoothed function of one coordinate from station samples."""

    def __init__(self, xs: list, ys: list, sigma: float = 6.0, default: float = 1.0):
        xs, ys = series(xs, ys)
        self.xs, self.ys = (xs, smooth(xs, ys, sigma)) if xs else ([0.0], [default])

    def __call__(self, x: float) -> float:
        return interp(self.xs, self.ys, x)


def measure(verts: list, edges: list, wa: list, frame: dict) -> dict:
    """The body's own silhouette at the frame's stations: the trunk (half width, front, back), each leg (inner and
    outer |x|, front, back) and the arms (along |x|: z low and high, y front and back)."""
    zc = frame["crotch"]
    body = lambda a, b: wa[a] < 0.5 and wa[b] < 0.5  # noqa: E731
    tz = [z for z in frame["trunk_z"] if z > zc + 1.0]
    tr = {}
    for z, pts in zip(tz, sections(verts, edges, body, 2, tz)):
        if pts:
            tr[z] = (max(abs(p[0]) for p in pts), min(p[1] for p in pts), max(p[1] for p in pts))
    lz = [z for z in frame["leg_z"] if z < zc - 1.0]
    lg = {}
    for z, pts in zip(lz, sections(verts, edges, body, 2, lz)):
        pts = [p for p in pts if p[0] > 0]
        if pts:
            lg[z] = (min(p[0] for p in pts), max(p[0] for p in pts), min(p[1] for p in pts), max(p[1] for p in pts))
    left = lambda a, b: wa[a] >= 0.5 and wa[b] >= 0.5 and verts[a][0] > 0  # noqa: E731
    au = frame["arm_u"]
    ar = {}
    for u, pts in zip(au, sections(verts, edges, left, 0, au)):
        if pts:
            ar[u] = (min(p[2] for p in pts), max(p[2] for p in pts), min(p[1] for p in pts), max(p[1] for p in pts))
    return {"trunk": tr, "legs": lg, "arms": ar}


def frame_of(table: dict, bones: dict, armpit_u: float) -> dict:
    """The fit's landmarks on the body (mm) and its stations, from the table and the body's bones."""
    hm = table["height_map"]
    crotch = hm["body_z"][1]
    to_body = lambda zc: interp(hm["concept_z"], hm["body_z"], zc)  # noqa: E731
    ring = table["neck_ring"]["z"]
    arm = table["arms"]
    wrist_u = bones["LeftHand"]["head"][0]
    s0, s1 = arm["s_armpit"], arm["s_wrist"]
    s_to_u = lambda s: armpit_u + (s - s0) / (s1 - s0) * (wrist_u - armpit_u)  # noqa: E731
    return {"crotch": crotch, "armpit": to_body(table["keys"]["armpit_z"]), "ring": ring, "wrist_u": wrist_u,
            "armpit_u": armpit_u, "ankle": bones["LeftFoot"]["head"][2],
            "trunk_z": list(table["trunk"]["z"]), "leg_z": list(table["legs"]["z"]),
            "arm_s": list(arm["s"]), "arm_u": [s_to_u(s) for s in arm["s"]],
            "keep_front": table.get("fit", {}).get("keep_front", [])}


def targets(table: dict, frame: dict) -> dict:
    """The table's values as smoothed profiles over the body's coordinates."""
    t, lg, ar = table["trunk"], table["legs"], table["arms"]
    half = [num(w) / 2 if num(w) is not None else None for w in t["front_w"]]
    tw = [None if z <= frame["crotch"] + 1 or frame["armpit"] + 5 < z < frame["ring"] - 90 else h
          for z, h in zip(t["z"], half)]
    sel = [s <= ar["s_wrist"] for s in ar["s"]]
    return {"trunk_half": Profile(t["z"], tw, default=0.0),
            "trunk_front": Profile(t["z"], [num(v) for v in t["front_y"]]),
            "trunk_back": Profile(t["z"], [num(v) for v in t["back_y"]]),
            "leg_half": Profile(lg["z"], [num(v) / 2 if num(v) else None for v in lg["width"]]),
            "leg_front": Profile(lg["z"], [num(v) for v in lg["front_y"]]),
            "leg_back": Profile(lg["z"], [num(v) for v in lg["back_y"]]),
            "arm_w": Profile([u for u, k in zip(frame["arm_u"], sel) if k],
                             [num(w) for w, k in zip(ar["width"], sel) if k])}


def keep_front(z: float, zones: list, edge: float = 30.0) -> float:
    """1 inside a keep_front zone [z0, z1], easing to 0 over `edge` mm outside it."""
    k = 0.0
    for z0, z1 in zones:
        if edge <= 0:
            k = max(k, 1.0 if z0 <= z <= z1 else 0.0)
            continue
        k = max(k, ramp((z - (z0 - edge)) / edge) * ramp(((z1 + edge) - z) / edge))
    return k


def ratios(m: dict, tg: dict, frame: dict, chest=None) -> dict:
    """The maps' smoothed profiles: per trunk height the x ratio, the front and back (now, then the target); per leg
    height the half-width ratio, its middle, front and back; per arm u the width ratio and the section's middle."""
    tz = sorted(m["trunk"])
    rx = [tg["trunk_half"](z) / m["trunk"][z][0] if m["trunk"][z][0] > 0 else 1.0 for z in tz]
    kf = [keep_front(z, frame["keep_front"]) for z in tz]
    f1 = [tg["trunk_front"](z) for z in tz]
    if chest is not None:
        f1 = [f + chest_excess(z, chest) for z, f in zip(tz, f1)]
    f1 = [m["trunk"][z][1] * k + f * (1 - k) for z, f, k in zip(tz, f1, kf)]
    lz = sorted(m["legs"])
    lr = [tg["leg_half"](z) / ((m["legs"][z][1] - m["legs"][z][0]) / 2) for z in lz]
    lf1 = [tg["leg_front"](z) for z in lz]
    lk = [keep_front(z, frame["keep_front"]) for z in lz]
    lf1 = [m["legs"][z][2] * k + f * (1 - k) for z, f, k in zip(lz, lf1, lk)]
    au = sorted(m["arms"])
    ak = [tg["arm_w"](u) / (m["arms"][u][1] - m["arms"][u][0]) for u in au]
    p = lambda xs, ys: Profile(xs, ys, sigma=6.0)  # noqa: E731
    return {"rx": p(tz, rx), "f0": p(tz, [m["trunk"][z][1] for z in tz]), "b0": p(tz, [m["trunk"][z][2] for z in tz]),
            "f1": p(tz, f1), "b1": p(tz, [tg["trunk_back"](z) for z in tz]),
            "lr": p(lz, lr), "lc": p(lz, [(m["legs"][z][0] + m["legs"][z][1]) / 2 for z in lz]),
            "lf0": p(lz, [m["legs"][z][2] for z in lz]), "lb0": p(lz, [m["legs"][z][3] for z in lz]),
            "lf1": p(lz, lf1), "lb1": p(lz, [tg["leg_back"](z) for z in lz]),
            "ak": p(au, ak), "ayc": p(au, [(m["arms"][u][2] + m["arms"][u][3]) / 2 for u in au]),
            "azc": p(au, [(m["arms"][u][0] + m["arms"][u][1]) / 2 for u in au])}


def chest_line(z: float, chest: dict) -> float:
    """The front line under the chest rounds: linear from the crease to the upper chest (y, mm)."""
    z0, z1, f0, f1 = chest["under_z"], chest["top_z"], chest["under_f"], chest["top_f"]
    return f0 + (f1 - f0) * (z - z0) / (z1 - z0)


def chest_excess(z: float, chest: dict) -> float:
    """How far the table's front comes ahead of the line under the rounds (mm, >= 0)."""
    if not chest["under_z"] < z < chest["top_z"]:
        return 0.0
    return max(0.0, chest_line(z, chest) - chest["front"](z))


def round_x(ax: float, cx: float, sigma: float, floor: float) -> float:
    """The rounds' share across x: 1 at their centres, `floor` and up between them, falling to 0 outside."""
    b = math.exp(-0.5 * ((ax - cx) / sigma) ** 2)
    return floor + (1.0 - floor) * b if ax < cx else b


def fit(verts: list, weights: list, edges: list, table: dict, bones: dict, armpit_u: float, ring_idx: list,
        chest: dict | None = None) -> tuple[list, dict]:
    """One pass of the station fit (mm in, mm out); the report holds the maps' ranges."""
    wa = [arm_share(w) for w in weights]
    wf = [foot_share(w) for w in weights]
    fr = frame_of(table, bones, armpit_u)
    m = measure(verts, edges, wa, fr)
    tg = targets(table, fr)
    r = ratios(m, tg, fr, chest)
    zc, za, ring = fr["crotch"], fr["armpit"], fr["ring"]
    ring_set = set(ring_idx)
    out = []
    for i, (p, a, f) in enumerate(zip(verts, wa, wf)):
        if i in ring_set:
            out.append(tuple(p))
            continue
        x, y, z = p
        # the trunk; x kept above the armpit, the neck's widths back over the 60 mm under the ring
        wx = 1.0 - ramp((z - za) / 40.0) * (1.0 - ramp((z - (ring - 60.0)) / 25.0))
        tx = x * (1.0 + wx * (r["rx"](z) - 1.0))
        c = (r["f0"](z) + r["b0"](z)) / 2
        ty = map_y(y, c, r["f0"](z), r["b0"](z), r["f1"](z), r["b1"](z))
        if chest is not None:
            ty -= chest_excess(z, chest) * round_x(abs(x), chest["centre_x"], chest["sigma_x"], chest["floor"]) \
                * ramp((c - y) / max(1.0, c - r["f0"](z)) * 1.6 - 0.3)
        # a leg
        ax, sg = abs(x), 1.0 if x >= 0 else -1.0
        lc = r["lc"](z)
        lx = sg * (lc + (ax - lc) * r["lr"](z))
        lcy = (r["lf0"](z) + r["lb0"](z)) / 2
        ly = map_y(y, lcy, r["lf0"](z), r["lb0"](z), r["lf1"](z), r["lb1"](z))
        t = ramp((z - (zc - 30.0)) / 40.0)
        bx, by = (1 - t) * lx + t * tx, (1 - t) * ly + t * ty
        keep = f * (1 - t)  # the feet as they are
        bx, by = (1 - keep) * bx + keep * x, (1 - keep) * by + keep * y
        bz = z
        # an arm
        if a > 0:
            k = r["ak"](ax)
            k = 1.0 + (k - 1.0) * ramp((ax - (fr["armpit_u"] - 40.0)) / 50.0) * (1.0 - ramp((ax - fr["wrist_u"]) / 40.0))
            yc, zcen = r["ayc"](ax), r["azc"](ax)
            amx, amy, amz = x, yc + (y - yc) * k, zcen + (z - zcen) * k
            bx, by, bz = (1 - a) * bx + a * amx, (1 - a) * by + a * amy, (1 - a) * bz + a * amz
        lock = ramp((z - (ring - 30.0)) / 30.0)
        out.append(((1 - lock) * bx + lock * x, (1 - lock) * by + lock * y, (1 - lock) * bz + lock * z))
    moves = [math.dist(p, q) for p, q in zip(verts, out)]
    return out, {"max_move_mm": round(max(moves), 2), "mean_move_mm": round(sum(moves) / len(moves), 2),
                 "frame": {k: v for k, v in fr.items() if not isinstance(v, list)}}


def armpit_u(verts: list, edges: list, weights: list, z: float) -> float:
    """Our armpit along |x|: the trunk's half width (arms left out) at the armpit's height."""
    wa = [arm_share(w) for w in weights]
    pts = sections(verts, edges, lambda a, b: wa[a] < 0.5 and wa[b] < 0.5, 2, [z])[0]
    return max(abs(p[0]) for p in pts)


def errors(verts: list, weights: list, edges: list, table: dict, bones: dict, au: float,
           chest: dict | None = None) -> dict:
    """The overlay error (built minus table, mm) per station: trunk front width, front and back; legs width, front
    and back; arms width. Stations the fit leaves alone by rule are marked, not counted."""
    wa = [arm_share(w) for w in weights]
    fr = frame_of(table, bones, au)
    m = measure(verts, edges, wa, fr)
    t, lg, ar = table["trunk"], table["legs"], table["arms"]
    rows = {"trunk": [], "legs": [], "arms": []}
    ring = fr["ring"]
    for z, w, f, b in zip(t["z"], t["front_w"], t["front_y"], t["back_y"]):
        if z not in m["trunk"]:
            continue
        x0, f0, b0 = m["trunk"][z]
        rule = "neck taper" if z > ring - 30 else "shoulders (T arms)" if fr["armpit"] + 5 < z < ring - 60 \
            else "kept front" if keep_front(z, fr["keep_front"], 0.0) > 0 else ""
        rows["trunk"].append({"z": z, "w": _e(2 * x0, w), "front": None if rule == "kept front" else _e(f0, f),
                              "back": _e(b0, b), "rule": rule if rule != "kept front" else "front kept",
                              "w_skip": rule in ("neck taper", "shoulders (T arms)")})
    for z, w, f, b in zip(lg["z"], lg["width"], lg["front_y"], lg["back_y"]):
        if z not in m["legs"]:
            continue
        xi, xo, f0, b0 = m["legs"][z]
        rule = "foot (kept)" if z < fr["ankle"] + 65 else ""
        kf = keep_front(z, fr["keep_front"], 0.0) > 0
        rows["legs"].append({"z": z, "w": _e(xo - xi, w), "front": None if kf else _e(f0, f), "back": _e(b0, b),
                             "rule": rule or ("front kept" if kf else "")})
    for s, u, w in zip(fr["arm_s"], fr["arm_u"], ar["width"]):
        if u not in m["arms"] or s > ar["s_wrist"]:
            continue
        z0, z1, _, _ = m["arms"][u]
        rows["arms"].append({"s": s, "u": round(u, 1), "w": _e(z1 - z0, w), "rule": ""})
    return {"rows": rows, "summary": summarise(rows), "frame": {k: v for k, v in fr.items() if not isinstance(v, list)}}


def _e(built: float, want) -> float | None:
    want = num(want)
    return None if want is None else round(built - want, 1)


TARGET = {"trunk": 5.0, "legs": 3.0, "arms": 3.0}


def summarise(rows: dict) -> dict:
    """Per region and measure the worst counted error, its station and the stations over the target."""
    out = {}
    for reg, rs in rows.items():
        for key in ("w", "front", "back"):
            vals = [(r.get(key), r.get("z", r.get("s"))) for r in rs
                    if r.get(key) is not None and not r.get("rule") and not (key == "w" and r.get("w_skip"))]
            if not vals:
                continue
            worst = max(vals, key=lambda v: abs(v[0]))
            over = [st for v, st in vals if abs(v) > TARGET[reg]]
            out[f"{reg}.{key}"] = {"worst": worst[0], "at": worst[1], "n": len(vals), "over": over,
                                   "mean_abs": round(sum(abs(v) for v, _ in vals) / len(vals), 2)}
    return out
