"""Body type B, the female alien body (art #196, `docs/decisions/2026-10-29-body-types.md`): its own body on body A's
topology (the same vertices in the same order, the same faces, weights and UVs) and its own skeleton rest (the same
bone names, parents and rest orientations, other bone positions). No bpy: the maths, the target file's checks and the
ratio measure, tested in tools/tests/test_alien_body_b_geom.py; alien_body_b.py applies it in Blender.

The frame is the body file's: x lateral (the body is mirror-symmetric in x), z up from the sole, the front at -y.

1. The skeleton rest (`rest`). Each bone b gets a linear map L_b (world axes) and a new head H'_b:
   - the trunk (Root, Hips to Head, the eyes and the jaw): L = diag(1, 1, s), the height scale s about the floor;
     the heads' z mapped by `zmap` (scaled below the neck ring, moved by the ring's drop above it, so the head that
     sits on the ring keeps its size);
   - a limb bone: L = r I + (s - r) u u^T, u its unit axis: the length scaled by s, the thickness by its radial r;
     a hand, finger, foot or toe bone: L = k I (its own uniform scale, the shape kept);
   - a child's head: H'_c = H'_p + L_p (H_c - H_p), plus the arms' shift in (at the UpperArm) or the legs' shift out
     (at the UpperLeg).
   Each bone's tail is H'_b + k (tail - head), so its direction and roll, its rest orientation, are A's exactly.
2. The vertices (`deform`): the linear blend of the bones' maps p -> H'_b + L_b (p - H_b) by the vertex's own
   weights; then the trunk's width profile (x scaled about the midline by a smooth curve over A's height, times the
   vertex's weight on the mask bones); then the chest's and the seat's rounds (alien_female_geom's fields, no
   nipples); then the neck lock: from `lock_from_z` up to the ring the vertex blends to the ring's pure drop, so the
   ring's x and y stay A's and the head's fit is unchanged; then the whole body (and every bone) moved so its sole
   is at z = 0.
3. The measure (`measure`, `ratios`): shoulders, waist, hips, forearm, wrist, calf, chest and seat depth, the height,
   on A's anatomical heights scaled to the body, and B over A.
"""
from __future__ import annotations

import math
import tomllib
from pathlib import Path

import alien_female_geom as FG

TRUNK = ("Root", "Hips", "Spine", "Chest", "UpperChest", "Neck", "Head", "Jaw", "LeftEye", "RightEye")
CENTRE = ("Hips", "Spine", "Chest", "UpperChest", "Neck")
DIGITS = ("Thumb", "Index", "Middle", "Ring", "Little")
TOP = {"name", "note", "height", "arms", "legs", "profile", "chest", "seat", "mask"}
NESTED = {
    "height": {"scale", "ring_z", "lock_from_z"},
    "arms": {"shift_in_m", "shoulder_axial", "upper_radial", "lower_radial", "hand_scale"},
    "legs": {"shift_out_m", "upper_radial", "lower_radial", "foot_scale"},
    "profile": {"z", "scale"},
    "chest": {"amount_m", "z", "half_z", "x", "half_x", "ramp_m"},
    "seat": {"amount_m", "z", "half_z", "x", "half_x", "ramp_m"},
    "mask": {"bones"},
}


def load(path: str | Path) -> dict:
    """A body type target file, every key checked; ValueError names the first problem."""
    d = check(tomllib.loads(Path(path).read_text(encoding="utf-8")), str(path))
    if d["name"] != Path(path).stem:
        raise ValueError(f"{path}: name {d['name']!r} is not the file's stem {Path(path).stem!r}")
    return d


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def check(d: dict, name: str = "target") -> dict:
    bad = set(d) - TOP
    if bad:
        raise ValueError(f"{name}: unknown keys {sorted(bad)}")
    missing = (TOP - {"note"}) - set(d)
    if missing:
        raise ValueError(f"{name}: missing keys {sorted(missing)}")
    if not isinstance(d["name"], str) or not d["name"]:
        raise ValueError(f"{name}: name must be a non-empty string")
    for table, keys in NESTED.items():
        t = d[table]
        if not isinstance(t, dict) or set(t) != keys:
            raise ValueError(f"{name}: {table} keys {sorted(t) if isinstance(t, dict) else t}, want {sorted(keys)}")
        for k, v in t.items():
            if table == "mask":
                if not (isinstance(v, list) and v and all(isinstance(b, str) for b in v)):
                    raise ValueError(f"{name}: mask.bones must be a list of bone names")
            elif table == "profile":
                if not (isinstance(v, list) and len(v) >= 2 and all(_num(x) for x in v)):
                    raise ValueError(f"{name}: profile.{k} must be a list of at least two numbers")
            elif not _num(v):
                raise ValueError(f"{name}: {table}.{k} is not a finite number")
    for table, k in (("height", "scale"), ("arms", "shoulder_axial"), ("arms", "upper_radial"),
                     ("arms", "lower_radial"), ("arms", "hand_scale"), ("legs", "upper_radial"),
                     ("legs", "lower_radial"), ("legs", "foot_scale")):
        if not 0.7 <= d[table][k] <= 1.3:
            raise ValueError(f"{name}: {table}.{k} must be in [0.7, 1.3]")
    for k in ("shift_in_m",):
        if not 0 <= d["arms"][k] <= 0.06:
            raise ValueError(f"{name}: arms.{k} must be in [0, 0.06]")
    if not 0 <= d["legs"]["shift_out_m"] <= 0.03:
        raise ValueError(f"{name}: legs.shift_out_m must be in [0, 0.03]")
    h = d["height"]
    if not 0 < h["lock_from_z"] < h["ring_z"]:
        raise ValueError(f"{name}: height.lock_from_z must be in (0, ring_z)")
    p = d["profile"]
    if len(p["z"]) != len(p["scale"]):
        raise ValueError(f"{name}: profile.z and profile.scale differ in length")
    if any(b <= a for a, b in zip(p["z"], p["z"][1:])):
        raise ValueError(f"{name}: profile.z must rise strictly")
    if p["scale"][0] != 1.0 or p["scale"][-1] != 1.0:
        raise ValueError(f"{name}: profile.scale must start and end at 1.0 (nothing outside it moves)")
    if p["z"][-1] > h["lock_from_z"]:
        raise ValueError(f"{name}: the profile must end below height.lock_from_z")
    if any(not 0.6 <= s <= 1.4 for s in p["scale"]):
        raise ValueError(f"{name}: profile.scale must stay in [0.6, 1.4]")
    for table in ("chest", "seat"):
        t = d[table]
        if not 0 <= t["amount_m"] <= 0.05:
            raise ValueError(f"{name}: {table}.amount_m must be in [0, 0.05]")
        if any(t[k] <= 0 for k in ("half_z", "half_x", "ramp_m")):
            raise ValueError(f"{name}: {table}'s half sizes and ramp must be > 0")
        if t["z"] + t["half_z"] > h["lock_from_z"]:
            raise ValueError(f"{name}: {table}'s box reaches the neck lock")
    return d


# ---- small linear algebra on tuples ----
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _mul(m, v):
    return tuple(m[i][0] * v[0] + m[i][1] * v[1] + m[i][2] * v[2] for i in range(3))


def _norm(v):
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def axial_radial(u, axial: float, radial: float):
    """r I + (a - r) u u^T for a unit u: lengths along u scaled by a, across it by r."""
    return [[radial * (i == j) + (axial - radial) * u[i] * u[j] for j in range(3)] for i in range(3)]


def zmap(z: float, t: dict) -> float:
    """A trunk height on B: scaled about the floor below the ring, moved by the ring's drop above it."""
    s, ring = t["height"]["scale"], t["height"]["ring_z"]
    return s * z if z <= ring else z - (1.0 - s) * ring


def side(name: str) -> int:
    return 1 if name.startswith("Left") else -1 if name.startswith("Right") else 0


def kind(name: str) -> str:
    """The bone's role in the map: trunk, shoulder, upper_arm, lower_arm, hand, upper_leg, lower_leg, foot."""
    if name in TRUNK or not side(name):
        return "trunk"
    n = name[4:] if name.startswith("Left") else name[5:]
    if any(n.startswith(d) for d in DIGITS) or n == "Hand":
        return "hand"
    return {"Shoulder": "shoulder", "UpperArm": "upper_arm", "LowerArm": "lower_arm", "UpperLeg": "upper_leg",
            "LowerLeg": "lower_leg", "Foot": "foot", "Toes": "foot"}.get(n, "trunk")


def linear(name: str, bone: dict, t: dict):
    """The bone's linear map L_b (world axes)."""
    s, ar, lg = t["height"]["scale"], t["arms"], t["legs"]
    k = kind(name)
    if k == "trunk":
        return [[1.0, 0, 0], [0, 1.0, 0], [0, 0, s]]
    if k in ("hand", "foot"):
        u = ar["hand_scale"] if k == "hand" else lg["foot_scale"]
        return [[u, 0, 0], [0, u, 0], [0, 0, u]]
    d = _sub(bone["tail"], bone["head"])
    n = _norm(d)
    u = (d[0] / n, d[1] / n, d[2] / n)
    if k == "shoulder":  # the collar: shorter along its axis, then the height scale
        m = axial_radial(u, ar["shoulder_axial"], 1.0)
        return [[m[0][0], m[0][1], m[0][2]], [m[1][0], m[1][1], m[1][2]], [s * m[2][0], s * m[2][1], s * m[2][2]]]
    radial = {"upper_arm": ar["upper_radial"], "lower_arm": ar["lower_radial"], "upper_leg": lg["upper_radial"],
              "lower_leg": lg["lower_radial"]}[k]
    return axial_radial(u, s, radial)


def rest(bones: dict, t: dict) -> dict:
    """B's rest: per bone its new head and tail (the same direction), its linear map and its old head.
    bones: {name: {"head", "tail", "parent"}} in world space (A)."""
    out: dict = {}

    def place(n: str) -> None:
        if n in out:
            return
        b = bones[n]
        p = b["parent"]
        if p is None or kind(n) == "trunk":
            h = (b["head"][0], b["head"][1], zmap(b["head"][2], t))
        else:
            place(p)
            pb, po = bones[p], out[p]
            h = _add(po["head"], _mul(po["L"], _sub(b["head"], pb["head"])))
            k = kind(n)
            if k == "upper_arm":
                h = (h[0] - side(n) * t["arms"]["shift_in_m"], h[1], h[2])
            elif k == "upper_leg":
                h = (h[0] + side(n) * t["legs"]["shift_out_m"], h[1], h[2])
        L = linear(n, b, t)
        d = _sub(b["tail"], b["head"])
        n0 = _norm(d)
        k_len = _norm(_mul(L, d)) / n0 if n0 > 0 else 1.0
        out[n] = {"head": h, "tail": _add(h, (k_len * d[0], k_len * d[1], k_len * d[2])), "L": L,
                  "old_head": tuple(b["head"]), "parent": b["parent"]}

    for n in bones:
        place(n)
    return out


def profile_scale(z: float, prof: dict) -> float:
    """The trunk's x scale at A's height z: smoothstep between the control points, 1.0 outside them."""
    zs, ss = prof["z"], prof["scale"]
    if z <= zs[0] or z >= zs[-1]:
        return 1.0
    for (z0, s0), (z1, s1) in zip(zip(zs, ss), zip(zs[1:], ss[1:])):
        if z <= z1:
            return s0 + (s1 - s0) * FG.ramp((z - z0) / (z1 - z0))
    return 1.0


def _female(t: dict) -> dict:
    """alien_female_geom's field table with only the chest and the seat (the widths are the profile's)."""
    lo, hi = 0.0, t["height"]["lock_from_z"]
    zero = {"amount_m": 0.0, "z": (lo + hi) / 2, "half_z": (hi - lo) / 4, "ref_x": 1.0}
    return {"chest": t["chest"], "seat": t["seat"], "hips": zero, "waist": zero,
            "limits": {"still_above_z": hi, "still_below_z": lo, "max_delta_m": 0.05}}


def deform(verts: list, weights: list, bones: dict, t: dict) -> tuple[list, dict, dict]:
    """(B's vertices, B's rest from `rest`, the report). verts: A's world points; weights: per vertex {bone: w}."""
    r = rest(bones, t)
    chain = [(bones[n]["head"][2], -bones[n]["head"][1]) for n in CENTRE]
    ft = _female(t)
    mask = set(t["mask"]["bones"])
    h = t["height"]
    drop = -(1.0 - h["scale"]) * h["ring_z"]
    out = []
    for p, w in zip(verts, weights):
        tot = sum(v for b, v in w.items() if b in r)
        q = [0.0, 0.0, 0.0]
        if tot > 0:
            for b, v in w.items():
                if b in r:
                    rb = r[b]
                    m = _add(rb["head"], _mul(rb["L"], _sub(p, rb["old_head"])))
                    for i in range(3):
                        q[i] += v / tot * m[i]
        else:
            q = [p[0], p[1], zmap(p[2], t)]
        mw = min(1.0, sum(v for b, v in w.items() if b in mask))
        q[0] *= 1.0 + mw * (profile_scale(p[2], t["profile"]) - 1.0)
        c = FG.centre_f(p[2], chain)
        dx, df = FG.delta(p[0], -p[1] - c, p[2], mw, ft)
        q[1] -= df
        lk = FG.ramp((p[2] - h["lock_from_z"]) / (h["ring_z"] - h["lock_from_z"]))
        if lk > 0:
            ring = (p[0], p[1], p[2] + drop)
            q = [(1 - lk) * q[i] + lk * ring[i] for i in range(3)]
        out.append(tuple(q))
    lift = -min(q[2] for q in out)
    out = [(q[0], q[1], q[2] + lift) for q in out]
    for b in r.values():
        b["head"] = (b["head"][0], b["head"][1], b["head"][2] + lift)
        b["tail"] = (b["tail"][0], b["tail"][1], b["tail"][2] + lift)
    moves = [math.dist(a, b) for a, b in zip(verts, out)]
    return out, r, {"lift_m": round(lift, 6), "max_move_m": round(max(moves), 5),
                    "mean_move_m": round(sum(moves) / len(moves), 5)}


def turn_deg(a: dict, b: dict) -> float:
    """The angle between two bones' directions (tail - head), degrees."""
    u, v = _sub(a["tail"], a["head"]), _sub(b["tail"], b["head"])
    c = sum(x * y for x, y in zip(u, v)) / (_norm(u) * _norm(v))
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


# ---- the measure ----
def heaviest(w: dict) -> str:
    return max(w.items(), key=lambda kv: kv[1])[0] if w else ""


def _radius(verts, weights, bones, name, lo, hi, q=0.5):
    """The q-quantile distance from the bone's axis of the vertices heaviest on it, between lo and hi of its length."""
    b = bones[name]
    hd, d = b["head"], _sub(b["tail"], b["head"])
    n = _norm(d)
    u = (d[0] / n, d[1] / n, d[2] / n)
    rs = []
    for p, w in zip(verts, weights):
        if heaviest(w) != name:
            continue
        v = _sub(p, hd)
        a = sum(x * y for x, y in zip(v, u))
        if lo * n <= a <= hi * n:
            rs.append(_norm(_sub(v, (a * u[0], a * u[1], a * u[2]))))
    rs.sort()
    return rs[int(q * (len(rs) - 1))] if rs else float("nan")


def _band(verts, weights, z0, z1, skip=("Arm", "Hand", "Shoulder") + DIGITS):
    return [p for p, w in zip(verts, weights) if z0 <= p[2] <= z1 and not any(k in heaviest(w) for k in skip)]


def measure(verts: list, weights: list, bones: dict, s: float = 1.0) -> dict:
    """The body's proportions; heights are A's anatomical heights times s (B's height scale)."""
    out = {"height_m": max(p[2] for p in verts)}
    ua = bones["LeftUpperArm"]
    out["shoulder_joints_m"] = bones["LeftUpperArm"]["head"][0] - bones["RightUpperArm"]["head"][0]
    out["shoulders_m"] = 2 * (ua["head"][0] + _radius(verts, weights, bones, "LeftUpperArm", 0.0, 0.25, 0.9))
    waist = []
    for i in range(16):
        z = s * (0.95 + 0.01 * i)
        sl = _band(verts, weights, z - 0.006, z + 0.006)
        if sl:
            waist.append(2 * max(abs(p[0]) for p in sl))
    out["waist_m"] = min(waist)
    hips = _band(verts, weights, s * 0.80, s * 0.90)
    out["hips_m"] = 2 * max(abs(p[0]) for p in hips)
    out["upper_arm_r_m"] = _radius(verts, weights, bones, "LeftUpperArm", 0.3, 0.7)
    out["forearm_r_m"] = _radius(verts, weights, bones, "LeftLowerArm", 0.2, 0.5)
    out["wrist_r_m"] = _radius(verts, weights, bones, "LeftLowerArm", 0.85, 1.0)
    out["thigh_r_m"] = _radius(verts, weights, bones, "LeftUpperLeg", 0.3, 0.6)
    out["calf_r_m"] = _radius(verts, weights, bones, "LeftLowerLeg", 0.15, 0.45, 0.8)
    for key, z in (("chest", 1.14), ("seat", 0.84)):
        sl = _band(verts, weights, s * z - 0.006, s * z + 0.006)
        out[f"{key}_depth_m"] = max(p[1] for p in sl) - min(p[1] for p in sl)
    out["waist_to_hips"] = out["waist_m"] / out["hips_m"]
    return {k: round(v, 4) for k, v in out.items()}


TARGETS = {"shoulders_m": (0.80, 0.85), "waist_m": (0.75, 0.81), "hips_m": (1.08, 1.15), "forearm_r_m": (0.82, 0.88),
           "wrist_r_m": (0.82, 0.88), "calf_r_m": (0.82, 0.88), "height_m": (0.93, 0.97)}


def ratios(a: dict, b: dict) -> dict:
    """B over A per measure, with the brief's target window where it gives one."""
    out = {}
    for k in a:
        r = b[k] / a[k] if a[k] else float("nan")
        row = {"a": a[k], "b": b[k], "ratio": round(r, 3)}
        if k in TARGETS:
            lo, hi = TARGETS[k]
            row["target"] = [lo, hi]
            row["met"] = lo <= r <= hi
        out[k] = row
    return out
