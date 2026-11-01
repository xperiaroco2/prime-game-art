"""The loco grips solved from a drawn spec (art #196, Hands H1g; plain Python, no bpy).

H1d to H1f tuned the run's fist by angle grids and never converged (a ring, a spiral or a claw: the H1f critic, 3.1):
the alien's finger segments are about as long as they are thick, so no hand-picked angles both close the fist and
keep it off the palm. Here each grip is a spec in mm (`body_dims/hand_grips.toml`, in the Hand bone's frame) and the
angles are solved: every digit a chain of capsules (its bones' rest skin tubes, `alien_pose_math.tube`), the palm the
Hand bone's own skin points, each tip brought to its target within joint limits without going into the palm or a
neighbour, the thumb's base turned on all three axes (curl, roll, swing). Both characters' hands are solved together
(one grip serves both, as `anim_sets/alien_hands.toml` does), the left hand (the right one is its mirror,
`alien_pose_math.grip_quats`).

The Hand frame (mm, the left hand): x out of the palm (+ the palm side), y from the wrist to the knuckles, z toward
the thumb. Run:
    $PYTHON_BIN tools/blender/alien_grip_solve.py --dump A=<dump.json> --dump B=<dump.json> --out <dir> [--draw-only]
writes <dir>/solved.json (the grips in alien_hands.toml's form, the clearances and depths per character) and
<dir>/grips.png (each grip's side and front view drawn from the numbers: the palm's points, the targets, the solved
capsules).
"""
from __future__ import annotations

import argparse
import json
import math
import struct
import tomllib
import zlib
from pathlib import Path

import alien_pose_math as A
import alien_stride_math as S

HERE = Path(__file__).resolve().parent
SPEC = HERE / "body_dims" / "hand_grips.toml"
SIDE = "Left"
FING = ("Index", "Middle", "Ring")
CHAIN = {"Thumb": ("Metacarpal", "Proximal", "Distal"), "Index": ("Proximal", "Intermediate", "Distal"),
         "Middle": ("Proximal", "Intermediate", "Distal"), "Ring": ("Proximal", "Intermediate", "Distal")}


# ------------------------------------------------------------------------------------------------- geometry
def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def mul(a, k): return (a[0] * k, a[1] * k, a[2] * k)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def norm(a): return math.sqrt(dot(a, a))


def seg_point(p, a, b) -> float:
    """The distance from p to the segment ab."""
    ab = sub(b, a)
    t = dot(sub(p, a), ab) / max(1e-12, dot(ab, ab))
    t = min(1.0, max(0.0, t))
    return norm(sub(p, add(a, mul(ab, t))))


def seg_seg(p1, q1, p2, q2) -> float:
    """The least distance between the segments p1q1 and p2q2 (Ericson, Real-Time Collision Detection 5.1.9)."""
    d1, d2, r = sub(q1, p1), sub(q2, p2), sub(p1, p2)
    a, e, f = dot(d1, d1), dot(d2, d2), dot(d2, r)
    if a < 1e-12 and e < 1e-12:
        return norm(r)
    if a < 1e-12:
        s, t = 0.0, min(1.0, max(0.0, f / e))
    else:
        c = dot(d1, r)
        if e < 1e-12:
            s, t = min(1.0, max(0.0, -c / a)), 0.0
        else:
            b = dot(d1, d2)
            den = a * e - b * b
            s = min(1.0, max(0.0, (b * f - c * e) / den)) if den > 1e-12 else 0.0
            t = (b * s + f) / e
            if t < 0.0:
                t, s = 0.0, min(1.0, max(0.0, -c / a))
            elif t > 1.0:
                t, s = 1.0, min(1.0, max(0.0, (b - c) / a))
    return norm(sub(add(p1, mul(d1, s)), add(p2, mul(d2, t))))


def m_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def m_of_q(q):
    w, x, y, z = q
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y), 0.0],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x), 0.0],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y), 0.0], [0.0, 0.0, 0.0, 1.0]]


def m_pt(m, p):
    return tuple(m[r][0] * p[0] + m[r][1] * p[1] + m[r][2] * p[2] + m[r][3] for r in range(3))


def m_ax(m, k):
    return (m[0][k], m[1][k], m[2][k])


# --------------------------------------------------------------------------------------------- the hand model
class Hand:
    """One character's left hand in its Hand bone's rest frame (mm): per digit bone its rest matrix relative to its
    parent, its capsule's length and radius; the palm's points; per finger the crease line's y."""

    def __init__(self, dump: dict, spec: dict, name: str = ""):
        self.name = name
        skel, skin = dump["skel"], A.prepare_skin(dump["skin"])
        self.skel, self.skin = skel, skin
        rest, parent = skel["rest"], skel["parent"]
        inv = S.rigid_inv(rest[f"{SIDE}Hand"])
        mm = [[1000.0 if (r < 3 and c == 3) else 1.0 for c in range(4)] for r in range(4)]

        def in_hand(m):
            h = m_mul(inv, m)
            return [[h[r][c] * mm[r][c] for c in range(4)] for r in range(4)]
        self.rest = {}
        self.rel = {}
        self.cap = {}
        for f, segs in CHAIN.items():
            for i, s in enumerate(segs):
                b = f"{SIDE}{f}{s}"
                self.rest[b] = in_hand(rest[b])
                pb = parent[b]
                pm = in_hand(rest[pb]) if pb != f"{SIDE}Hand" else [[float(r == c) for c in range(4)] for r in range(4)]
                self.rel[b] = m_mul(_rigid_inv_mm(pm), self.rest[b])
        cfg = spec["hand"]
        for f, segs in CHAIN.items():
            rad = []
            for i, s in enumerate(segs):
                b = f"{SIDE}{f}{s}"
                t = A.tube(skel, skin, b)
                vals = sorted(r for row in t["radius"] for r in row if r > 0) if t else []
                rad.append(1000 * vals[len(vals) // 2] if vals else None)
                if i + 1 < len(segs):
                    nxt = self.rest[f"{SIDE}{f}{segs[i + 1]}"]
                    ln = norm(sub(m_ax(nxt, 3), m_ax(self.rest[b], 3)))
                else:  # the tip: the skin's extent along the bone, less the dome's radius (the capsule's cap)
                    ln = 1000 * (t["y0"] + t["dy"] * A.TUBE_SLICES) if t else 25.0
                self.cap[b] = [ln, None]
            known = [r for r in rad if r]
            for i, s in enumerate(segs):  # an empty tube (a short segment): its neighbours' mean
                r = rad[i] or (sum(known) / len(known))
                self.cap[f"{SIDE}{f}{s}"][1] = r * cfg["radius_scale"]
            last = self.cap[f"{SIDE}{f}{segs[-1]}"]
            last[0] = max(4.0, last[0] - last[1])
        pts = []  # the palm's skin: the Hand bone's points and the thenar's (the thumb's metacarpal, at rest)
        for bone in cfg["palm_bones"]:
            for i in skin["by_bone"].get(f"{SIDE}{bone}", []):
                pts.append(mul(m_pt(inv, skin["points"][i]), 1000.0))
        self.palm_raw = pts
        self.palm_all = pts + surface(pts, cfg)
        g = cfg["palm_grid_mm"]  # thinned to one point per grid cell (the solve's speed; the check uses all)
        cells = {}
        for p in pts:
            cells.setdefault(tuple(int(math.floor(c / g)) for c in p), p)
        self.palm = list(cells.values())
        self.crease = {}
        for f in FING:
            z = self.rest[f"{SIDE}{f}Proximal"][2][3]
            side = [p for p in pts if p[0] > cfg["palm_side_x_mm"] and abs(p[2] - z) < cfg["crease_band_mm"]]
            self.crease[f] = max(p[1] for p in side) if side else self.rest[f"{SIDE}{f}Proximal"][1][3]

    def pose(self, grip: dict) -> dict:
        """The digits' posed matrices in the hand frame (mm) for a grip of alien_hands.toml's form."""
        q = A.grip_quats(grip, SIDE)
        out = {}
        for f, segs in CHAIN.items():
            pm = [[float(r == c) for c in range(4)] for r in range(4)]
            for s in segs:
                b = f"{SIDE}{f}{s}"
                pm = m_mul(m_mul(pm, self.rel[b]), m_of_q(q.get(b, (1.0, 0.0, 0.0, 0.0))))
                out[b] = pm
        return out

    def capsules(self, P: dict) -> dict:
        """{bone: (head, end, radius)} of the posed digits."""
        out = {}
        for b, (ln, r) in self.cap.items():
            h = m_ax(P[b], 3)
            out[b] = (h, add(h, mul(m_ax(P[b], 1), ln)), r)
        return out


def surface(pts: list, cfg: dict) -> list:
    """The palm's skin between its sparse vertices (about 10 mm apart): a height field x(y, z) over the palm-side
    points, every `surface_step_mm` where at least three points lie within `surface_reach_mm`, the inverse-distance
    mean of their x."""
    side = [p for p in pts if p[0] > cfg["palm_side_x_mm"]]
    if not side:
        return []
    st, rc = cfg["surface_step_mm"], cfg["surface_reach_mm"]
    out = []
    y = min(p[1] for p in side)
    while y <= max(p[1] for p in side):
        z = min(p[2] for p in side)
        while z <= max(p[2] for p in side):
            near = [(math.hypot(p[1] - y, p[2] - z), p[0]) for p in side if abs(p[1] - y) < rc and abs(p[2] - z) < rc]
            near = [(d, x) for d, x in near if d < rc]
            if len(near) >= 3:
                w = [1.0 / max(1.0, d) ** 2 for d, _ in near]
                out.append((sum(wi * x for wi, (_, x) in zip(w, near)) / sum(w), y, z))
            z += st
        y += st
    return out


def _rigid_inv_mm(m):
    r = [[m[c][k] for c in range(3)] for k in range(3)]
    t = [-sum(r[k][c] * m[c][3] for c in range(3)) for k in range(3)]
    return [[*r[0], t[0]], [*r[1], t[1]], [*r[2], t[2]], [0.0, 0.0, 0.0, 1.0]]


def palm_clear(hand: Hand, cap, pts=None):
    """A capsule's least clearance to the palm's points (mm; < 0 inside) and the nearest point."""
    a, b, r = cap
    best, bp = 1e9, None
    for p in (hand.palm if pts is None else pts):
        d = seg_point(p, a, b)
        if d < best:
            best, bp = d, p
    return best - r, bp


def cap_clear(c1, c2) -> float:
    return seg_seg(c1[0], c1[1], c2[0], c2[1]) - c1[2] - c2[2]


# ---------------------------------------------------------------------------------------------- the grips
def grip_of(name: str, x: dict, nd: int | None = None) -> dict:
    """The solve's variables as an alien_hands.toml grip (`nd`: rounded to so many decimals)."""
    rd = (lambda v: v) if nd is None else (lambda v: round(v, nd))  # noqa: E731
    g = {"mirror": True}
    for f in FING:
        g[f] = [rd(v) for v in x[f]]
    t = x["Thumb"]
    g["Thumb"] = [rd(t[0]), rd(t[1]), rd(t[2])]
    g["ThumbTurn"] = [rd(t[3]), rd(t[4])]
    g["Little"] = list(g["Ring"][:3])  # unweighted bones (four digits), kept with the ring finger
    return g


def targets(hand: Hand, gs: dict, name: str, P0=None) -> dict:
    """Per finger the tip's target point (mm) from the spec: loose, on the palm (`tip_before_crease_mm` toward the
    wrist from the finger's crease, on the finger's line); relaxed, the spec's tip relative to the knuckle."""
    out = {}
    for f in FING:
        k = m_ax(hand.rest[f"{SIDE}{f}Proximal"], 3)
        if name == "loose":
            out[f] = (None, hand.crease[f] - gs["tip_before_crease_mm"][f], k[2])
        else:
            d = gs["tips"][f]
            out[f] = (k[0] + d[0], k[1] + d[1], k[2] + d[2])
    return out


def energy_finger(hands, gs, name, f, xs, prev, tg) -> tuple:
    """A finger's cost on every hand (mm^2) and its readings."""
    lim = gs["limits"][f] if f in gs["limits"] else gs["limits"]["finger"]
    e, info = 0.0, []
    for h in hands:
        x = dict(prev[h.name])
        x[f] = xs
        P = h.pose(grip_of(name, {**_fill(x), f: xs}))
        caps = h.capsules(P)
        b = [f"{SIDE}{f}{s}" for s in CHAIN[f]]
        r = {}
        cl_i, _ = palm_clear(h, caps[b[1]])
        cl_d, near = palm_clear(h, caps[b[2]])
        e += gs["w_pen"] * (min(0.0, cl_i) ** 2 + min(0.0, cl_d) ** 2)
        e += gs["w_pen"] * min(0.0, cap_clear(caps[b[0]], caps[b[2]]) - gs["self_clear_mm"]) ** 2
        t = tg[h.name][f]
        tip = caps[b[2]][1]
        if name == "loose":
            lo, hi = gs["tip_clear_mm"]
            e += gs["w_contact"] * (max(0.0, lo - cl_d) ** 2 + max(0.0, cl_d - hi) ** 2)
            band = gs["tip_band_mm"]  # the contact anywhere within the band around the target, pulled to it lightly
            dy = near[1] - t[1]
            e += gs["w_target"] * (10.0 * max(0.0, abs(dy) - band) ** 2 + 0.1 * dy * dy + 0.25 * (near[2] - t[2]) ** 2)
        else:
            e += gs["w_target"] * dot(sub(tip, t), sub(tip, t))
        r.update(palm_int=cl_i, palm_tip=cl_d, contact=near, tip=tip)
        for g in FING:
            if g == f or not x.get(g):
                continue
            ob = [f"{SIDE}{g}{s}" for s in CHAIN[g]]
            gap = min(cap_clear(caps[a], caps[c]) for a in b for c in ob)
            if abs(FING.index(g) - FING.index(f)) == 1:
                lo, hi = gs["gap_mm"]
                e += gs["w_gap"] * (max(0.0, lo - gap) ** 2 + max(0.0, gap - hi) ** 2)
            e += gs["w_pen"] * min(0.0, gap) ** 2
            r[f"gap_{g}"] = gap
        info.append(r)
    e += gs["w_side"] * xs[3] ** 2 + gs["w_smooth"] * max(0.0, xs[2] - xs[1]) ** 2
    if "shape" in gs:  # a knuckle-led curl: the middle joint and the tip in the spec's shares of the joint before
        e += gs["w_shape"] * ((xs[1] - gs["shape"][0] * xs[0]) ** 2 + (xs[2] - gs["shape"][1] * xs[1]) ** 2)
    return e + _limit(xs, lim), info


def energy_thumb(hands, gs, name, xs, prev, tg) -> tuple:
    lim = gs["limits"]["Thumb"]
    e, info = 0.0, []
    th = [f"{SIDE}Thumb{s}" for s in CHAIN["Thumb"]]
    for h in hands:
        x = {**prev[h.name], "Thumb": xs}
        caps = h.capsules(h.pose(grip_of(name, x)))
        r = {}
        for b in th[2:]:  # the distal only: the proximal's root lies in the thenar (the palm's own thumb skin)
            cl, _ = palm_clear(h, caps[b])
            e += gs["w_pen"] * min(0.0, cl) ** 2
            r[f"palm_{b[len(SIDE):]}"] = cl
        fingers = [f"{SIDE}{f}{s}" for f in FING for s in CHAIN[f]]
        worst = min(cap_clear(caps[a], caps[c]) for a in th[1:] for c in fingers)
        e += gs["w_pen"] * min(0.0, worst) ** 2
        r["fingers"] = worst
        pad = caps[th[2]]
        tip = pad[1]
        if name == "loose":
            lo, hi = gs["thumb_clear_mm"]
            for g in gs["thumb_pad_on"]:
                c = cap_clear(pad, caps[f"{SIDE}{g}"])
                e += gs["w_contact"] * (max(0.0, lo - c) ** 2 + max(0.0, c - hi) ** 2)
                r[g] = c
            mz = h.rest[f"{SIDE}MiddleProximal"][2][3] + gs["thumb_tip_short_mm"]
            e += gs["w_target"] * max(0.0, mz - tip[2]) ** 2
            r["tip_z_past_middle"] = tip[2] - mz
        else:
            ip = m_ax(h.pose(grip_of(name, x))[f"{SIDE}IndexProximal"], 3)
            ri = h.cap[f"{SIDE}IndexProximal"][1]
            d = gs["thumb_beside"]
            t = (ip[0] + d[0], ip[1] + d[1], ip[2] + ri + pad[2] + d[2])
            e += gs["w_target"] * dot(sub(tip, t), sub(tip, t))
            c = min(cap_clear(pad, caps[f"{SIDE}Index{s}"]) for s in CHAIN["Index"])
            lo, hi = gs["thumb_clear_mm"]
            e += gs["w_contact"] * (max(0.0, lo - c) ** 2 + max(0.0, c - hi) ** 2)
            r["index"] = c
            r["tip_from_target"] = norm(sub(tip, t))
        r["tip"] = tip
        info.append(r)
    e += gs["w_thumb_rest"] * sum((v - s) ** 2 for v, s in zip(xs, gs["starts"]["Thumb"][0]))
    return e + _limit(xs, lim), info


def _limit(xs, lim) -> float:
    return sum(1e4 * (max(0.0, lo - v) + max(0.0, v - hi)) ** 2 for v, (lo, hi) in zip(xs, lim))


def _fill(x: dict) -> dict:
    out = dict(x)
    for f in FING:
        out.setdefault(f, [0.0, 0.0, 0.0, 0.0])
    out.setdefault("Thumb", [0.0, 0.0, 0.0, 0.0, 0.0])
    return out


def nelder_mead(fun, x0: list, step: float = 8.0, iters: int = 400, tol: float = 1e-4) -> tuple:
    """A plain Nelder-Mead minimiser (the limits are penalties in `fun`)."""
    n = len(x0)
    pts = [list(x0)] + [[x0[j] + (step if j == i else 0.0) for j in range(n)] for i in range(n)]
    vals = [fun(p) for p in pts]
    for _ in range(iters):
        order = sorted(range(n + 1), key=lambda i: vals[i])
        pts, vals = [pts[i] for i in order], [vals[i] for i in order]
        if abs(vals[-1] - vals[0]) < tol * (1 + abs(vals[0])):
            break
        c = [sum(p[j] for p in pts[:-1]) / n for j in range(n)]
        xr = [c[j] + (c[j] - pts[-1][j]) for j in range(n)]
        fr = fun(xr)
        if fr < vals[0]:
            xe = [c[j] + 2 * (c[j] - pts[-1][j]) for j in range(n)]
            fe = fun(xe)
            pts[-1], vals[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < vals[-2]:
            pts[-1], vals[-1] = xr, fr
        else:
            xc = [c[j] + 0.5 * (pts[-1][j] - c[j]) for j in range(n)]
            fc = fun(xc)
            if fc < vals[-1]:
                pts[-1], vals[-1] = xc, fc
            else:
                pts = [pts[0]] + [[pts[0][j] + 0.5 * (p[j] - pts[0][j]) for j in range(n)] for p in pts[1:]]
                vals = [vals[0]] + [fun(p) for p in pts[1:]]
    i = min(range(n + 1), key=lambda k: vals[k])
    return pts[i], vals[i]


def solve(hands: list, spec: dict, name: str) -> dict:
    """One grip solved on every hand: the fingers from the index out, each against the ones before, then the thumb;
    a few restarts from the spec's starts, the best kept."""
    gs = {**spec["solve"], **spec["grips"][name]}
    tg = {h.name: targets(h, gs, name) for h in hands}
    prev = {h.name: {} for h in hands}
    x = {}
    for f in FING:
        best = None
        for x0 in gs["starts"][f]:
            xs, v = nelder_mead(lambda p: energy_finger(hands, gs, name, f, p, prev, tg)[0], list(x0), iters=gs["iters"])
            xs, v = nelder_mead(lambda p: energy_finger(hands, gs, name, f, p, prev, tg)[0], xs, step=2.0,
                                iters=gs["iters"])
            if best is None or v < best[1]:
                best = (xs, v)
        x[f] = best[0]
        for h in hands:
            prev[h.name][f] = best[0]
    best = None
    for x0 in gs["starts"]["Thumb"]:
        xs, v = nelder_mead(lambda p: energy_thumb(hands, gs, name, p, prev, tg)[0], list(x0), iters=gs["iters"])
        xs, v = nelder_mead(lambda p: energy_thumb(hands, gs, name, p, prev, tg)[0], xs, step=2.0, iters=gs["iters"])
        if best is None or v < best[1]:
            best = (xs, v)
    x["Thumb"] = best[0]
    return {"grip": grip_of(name, x, 1), "x": x, "targets": {h: {f: t for f, t in tg[h].items()} for h in tg}}


def report(hands: list, spec: dict, name: str, grip: dict) -> dict:
    """The solved grip's clearances (mm; < 0 inside) per hand, from the capsules and every palm point."""
    out = {}
    for h in hands:
        caps = h.capsules(h.pose(grip))
        r = {"palm": {}, "neighbours": {}, "thumb": {}}
        for f in FING:
            b = [f"{SIDE}{f}{s}" for s in CHAIN[f]]
            cl, near = palm_clear(h, caps[b[2]], h.palm_all)
            r["palm"][f] = {"intermediate": round(palm_clear(h, caps[b[1]], h.palm_all)[0], 2), "tip": round(cl, 2),
                            "contact_y": round(near[1], 1), "crease_y": round(h.crease[f], 1),
                            "before_crease": round(h.crease[f] - near[1], 1)}
        for a, c in (("Index", "Middle"), ("Middle", "Ring")):
            r["neighbours"][f"{a}-{c}"] = round(min(cap_clear(caps[f"{SIDE}{a}{s}"], caps[f"{SIDE}{c}{t}"])
                                                    for s in CHAIN[a] for t in CHAIN[c]), 2)
        th = [f"{SIDE}Thumb{s}" for s in CHAIN["Thumb"]]
        fingers = [f"{SIDE}{f}{s}" for f in FING for s in CHAIN[f]]
        r["thumb"]["into_fingers"] = round(min(cap_clear(caps[a], caps[c]) for a in th[1:] for c in fingers), 2)
        r["thumb"]["palm"] = round(palm_clear(h, caps[th[2]], h.palm_all)[0], 2)
        for g in ("IndexIntermediate", "MiddleIntermediate"):
            r["thumb"][g] = round(cap_clear(caps[th[2]], caps[f"{SIDE}{g}"]), 2)
        r["thumb"]["tip_z"] = round(caps[th[2]][1][2], 1)
        r["middle_z"] = round(h.rest[f"{SIDE}MiddleProximal"][2][3], 1)
        out[h.name] = r
    return out


# ------------------------------------------------------------------------------------------------ the drawing
FONT = {"0": "111101101101111", "1": "010110010010111", "2": "111001111100111", "3": "111001111001111",
        "4": "101101111001001", "5": "111100111001111", "6": "111100111101111", "7": "111001001001001",
        "8": "111101111101111", "9": "111101111001111", "-": "000000111000000", ".": "000000000000010",
        " ": "000000000000000", "A": "010101111101101", "B": "110101110101110", "C": "111100100100111",
        "D": "110101101101110", "E": "111100110100111", "F": "111100110100100", "G": "111100101101111",
        "H": "101101111101101", "I": "111010010010111", "K": "101101110101101", "L": "100100100100111",
        "M": "101111111101101", "N": "110101101101101", "O": "111101101101111", "P": "111101111100100",
        "R": "110101110101101", "S": "111100111001111", "T": "111010010010010", "U": "101101101101111",
        "W": "101101111111101", "X": "101101010101101", "Y": "101101010010010", "Z": "111001010100111",
        "/": "001001010100100", "=": "000111000111000", "+": "000010111010000", ":": "000010000010000"}
COL = {"Thumb": (214, 96, 40), "Index": (40, 120, 214), "Middle": (40, 170, 90), "Ring": (150, 70, 190)}


class Canvas:
    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.px = bytearray([250, 250, 246] * w * h)

    def dot(self, x: float, y: float, c, r: int = 0) -> None:
        xi, yi = int(round(x)), int(round(y))
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy <= r * r and 0 <= xi + dx < self.w and 0 <= yi + dy < self.h:
                    k = 3 * ((yi + dy) * self.w + xi + dx)
                    self.px[k:k + 3] = bytes(c)

    def line(self, a, b, c, r: int = 0) -> None:
        n = int(max(abs(b[0] - a[0]), abs(b[1] - a[1]))) + 1
        for i in range(n + 1):
            t = i / n
            self.dot(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, c, r)

    def circle(self, x, y, rad, c) -> None:
        n = max(12, int(rad * 6))
        for i in range(n):
            a = 2 * math.pi * i / n
            self.dot(x + rad * math.cos(a), y + rad * math.sin(a), c)

    def text(self, x: int, y: int, s: str, c=(30, 30, 30), k: int = 2) -> None:
        for ch in s.upper():
            g = FONT.get(ch, FONT[" "])
            for i, bit in enumerate(g):
                if bit == "1":
                    for dy in range(k):
                        for dx in range(k):
                            self.dot(x + (i % 3) * k + dx, y + (i // 3) * k + dy, c)
            x += 4 * k

    def save(self, path: Path) -> None:
        raw = b"".join(b"\x00" + bytes(self.px[3 * y * self.w:3 * (y + 1) * self.w]) for y in range(self.h))
        def chunk(t, d):
            return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", self.w, self.h, 8, 2, 0, 0, 0))
                         + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def draw(hand: Hand, spec: dict, results: dict, path: Path, px_mm: float = 2.4) -> None:
    """Per grip a side view (y right, x down: the palm below) and a front view (from the fingertips: z right, x down)
    of one hand: the palm's points grey, the crease lines blue, the targets red crosses, the solved capsules
    outlined in each digit's colour, a 10 mm grid."""
    views = [("side", 1, 0, (-20, 230), (-45, 95)), ("front", 2, 0, (-75, 105), (-45, 95))]
    cell_w = [int((v[3][1] - v[3][0]) * px_mm) for v in views]
    cell_h = int((views[0][4][1] - views[0][4][0]) * px_mm)
    W, Hh = sum(cell_w) + 30, (cell_h + 40) * len(results) + 20
    cv = Canvas(W, Hh)
    for gi, (name, res) in enumerate(results.items()):
        caps = hand.capsules(hand.pose(res["grip"]))
        tg = res["targets"][hand.name]
        x0 = 10
        top = 20 + gi * (cell_h + 40)
        for vi, (vn, ia, ib, (u0, u1), (v0, v1)) in enumerate(views):
            def P(p):
                return (x0 + (p[ia] - u0) * px_mm, top + 16 + (p[ib] - v0) * px_mm)
            for g in range(int(u0 // 10) * 10, int(u1) + 1, 10):
                cv.line((x0 + (g - u0) * px_mm, top + 16), (x0 + (g - u0) * px_mm, top + 16 + (v1 - v0) * px_mm), (226, 226, 222))
            for g in range(int(v0 // 10) * 10, int(v1) + 1, 10):
                cv.line((x0, top + 16 + (g - v0) * px_mm), (x0 + (u1 - u0) * px_mm, top + 16 + (g - v0) * px_mm),
                        (226, 226, 222))
            for p in hand.palm_all:
                cv.dot(*P(p), (175, 175, 175))
            for p in hand.palm_raw:
                cv.dot(*P(p), (110, 110, 110), 1)
            if vn == "side":
                for f in FING:
                    cy = hand.crease[f]
                    cv.line(P((v0, cy, 0)), P((v1, cy, 0)), (90, 140, 230))
            for b, (a, e, r) in caps.items():
                f = next(k for k in CHAIN if b.startswith(SIDE + k))
                n = 10
                for i in range(n + 1):
                    q = add(a, mul(sub(e, a), i / n))
                    cv.circle(*P(q), r * px_mm, COL[f])
                cv.line(P(a), P(e), tuple(int(c * 0.6) for c in COL[f]), 1)
            for f, t in tg.items():
                if t[0] is None:  # a loose target: on the palm (the y and z; x where the palm's surface is)
                    side = [p for p in hand.palm_all if p[0] > spec["hand"]["palm_side_x_mm"]]
                    near = min(side, key=lambda p: (p[1] - t[1]) ** 2 + (p[2] - t[2]) ** 2)
                    t = near
                c = P(t)
                cv.line((c[0] - 6, c[1] - 6), (c[0] + 6, c[1] + 6), (220, 30, 30), 1)
                cv.line((c[0] - 6, c[1] + 6), (c[0] + 6, c[1] - 6), (220, 30, 30), 1)
            cv.text(x0 + 4, top, f"{name} {vn}  {hand.name}  10 MM GRID")
            x0 += cell_w[vi] + 10
    cv.save(path)


# ------------------------------------------------------------------------------------------------------ main
def load_spec(path: Path = SPEC) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dump", action="append", required=True, help="<name>=<dump.json> (alien_hands.py --check's)")
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--out", required=True)
    ap.add_argument("--grips", default="loose,relaxed")
    ap.add_argument("--draw-only", action="store_true", help="the targets on the current grips, no solve")
    ap.add_argument("--current", default="", help="--draw-only: alien_hands.toml whose grips are drawn")
    a = ap.parse_args(argv)
    spec = load_spec(Path(a.spec))
    hands = []
    for d in a.dump:
        n, _, p = d.partition("=")
        hands.append(Hand(json.loads(Path(p).read_text(encoding="utf-8")), spec, n))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    res = {}
    for name in a.grips.split(","):
        gs = {**spec["solve"], **spec["grips"][name]}
        if a.draw_only:
            cur = tomllib.loads(Path(a.current).read_text(encoding="utf-8"))["grips"][name]
            res[name] = {"grip": cur, "targets": {h.name: targets(h, gs, name) for h in hands}}
        else:
            res[name] = solve(hands, spec, name)
            print("SOLVED", name, json.dumps(res[name]["grip"]), flush=True)
        res[name]["report"] = report(hands, spec, name, res[name]["grip"])
        print("REPORT", name, json.dumps(res[name]["report"]), flush=True)
    meta = {h.name: {"crease_y": {f: round(v, 1) for f, v in h.crease.items()},
                     "capsules": {b: [round(v, 1) for v in c] for b, c in h.cap.items()},
                     "palm_points": len(h.palm_all)} for h in hands}
    (out / "solved.json").write_text(json.dumps({"hands": meta, "grips": {k: {kk: vv for kk, vv in v.items() if kk != "x"}
                                                                          for k, v in res.items()}}, indent=1,
                                                default=lambda o: None), encoding="utf-8", newline="\n")
    for h in hands:
        draw(h, spec, res, out / f"grips_{h.name}.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
