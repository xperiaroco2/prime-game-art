"""A garment's spec (`specs/<garment>_dims.toml`, art #196, Gate 1): its loader, the ratio maths and the body's
landmarks. Plain Python, no Blender (garment_spec_probe.py dumps the meshes; garment_drawing.py draws).

A spec's sizes are design ratios to body landmarks, so the same spec reads on the concept and on her body:
- a height: `between = [a, b]`, `ratio = t`: the landmark a's height plus t of the way to b's
  (t below 0 or over 1 extends past them);
- a size: `of = w`, `ratio = t`: t times the landmark size w (a width, depth or span);
- a fixed size: `ratio` absent, `cm` alone (hardware, seams: they do not scale with the body).
Each dimension also states `cm`, its value on the spec's body; `check_spec` refuses a file where `cm` and the ratio
on the body's landmarks (the spec's [body.landmarks_cm]) disagree by more than 0.1 cm, so a number never lives in
one form only.
"""
from __future__ import annotations

import json
import math
import tomllib
from pathlib import Path

HEIGHTS = ("sole", "ankle", "knee", "crotch", "waist", "bust", "armpit", "collarbone", "shoulder_top")
SIZES = ("waist_w", "hip_w", "bust_w", "chest_w", "shoulder_w", "thigh_w", "knee_w", "ankle_w", "bust_d",
         "torso_span", "hip_z_span")
KINDS = ("height", "size", "fixed")
AGREE_CM = 0.1


class SpecError(ValueError):
    pass


def kind(d: dict) -> str:
    if "between" in d:
        return "height"
    if "of" in d:
        return "size"
    return "fixed"


def at_ratio(lm: dict, d: dict) -> float:
    """The dimension's value (the landmarks' unit) on a body or picture with landmarks lm."""
    k = kind(d)
    if k == "height":
        a, b = d["between"]
        return lm[a] + d["ratio"] * (lm[b] - lm[a])
    if k == "size":
        return d["ratio"] * lm[d["of"]]
    return d["cm"]


def ratio_of(lm: dict, d: dict, value: float) -> float:
    """The ratio a measured value has in the dimension's terms (the inverse of at_ratio)."""
    k = kind(d)
    if k == "height":
        a, b = d["between"]
        span = lm[b] - lm[a]
        if abs(span) < 1e-9:
            raise SpecError(f"landmarks {a} and {b} coincide")
        return (value - lm[a]) / span
    if k == "size":
        if abs(lm[d["of"]]) < 1e-9:
            raise SpecError(f"landmark {d['of']} is zero")
        return value / lm[d["of"]]
    return value / d["cm"]


def load_spec(path) -> dict:
    """The spec file, validated: every dimension has cm and tol_cm, a known landmark and a ratio unless fixed."""
    spec = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    for key in ("garment", "body", "dims"):
        if key not in spec:
            raise SpecError(f"{path}: no [{key}]")
    lm = spec["body"].get("landmarks_cm", {})
    for name in HEIGHTS + SIZES:
        if name not in lm:
            raise SpecError(f"{path}: body.landmarks_cm has no {name}")
    for name, d in spec["dims"].items():
        for f in ("what", "cm", "tol_cm"):
            if f not in d:
                raise SpecError(f"{path}: dims.{name} has no {f}")
        k = kind(d)
        if k == "height":
            if len(d["between"]) != 2 or any(x not in HEIGHTS for x in d["between"]):
                raise SpecError(f"{path}: dims.{name}.between must be two of {HEIGHTS}")
        if k == "size" and d["of"] not in SIZES:
            raise SpecError(f"{path}: dims.{name}.of must be one of {SIZES}")
        if k != "fixed" and "ratio" not in d:
            raise SpecError(f"{path}: dims.{name} has no ratio")
        if d["tol_cm"] <= 0:
            raise SpecError(f"{path}: dims.{name}.tol_cm must be positive")
    return spec


def check_spec(spec: dict) -> list[str]:
    """Dimensions whose cm and ratio disagree on the spec's own body (empty when the file is consistent)."""
    lm = spec["body"]["landmarks_cm"]
    bad = []
    for name, d in spec["dims"].items():
        v = at_ratio(lm, d)
        if abs(v - d["cm"]) > AGREE_CM:
            bad.append(f"{name}: cm {d['cm']} but ratio {d.get('ratio')} gives {v:.2f}")
    return bad


def within(d: dict, measured_cm: float | None) -> bool | None:
    return None if measured_cm is None else abs(measured_cm - d["cm"]) <= d["tol_cm"]


# --- the body's landmarks from a probe (garment_spec_probe.py) ---------------------------------------------------

def load_probe(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


class Sections:
    """Plane sections of meshes: z = c (the points where triangle edges cross it), bucketed by 1 cm of height."""

    def __init__(self, probe: dict, names=None) -> None:
        self.buckets: dict[int, list] = {}
        self.pts = []
        for m in probe["meshes"]:
            if names is not None and m["name"] not in names:
                continue
            vs = m["vertices"]
            self.pts.extend(tuple(v) for v in vs)
            for t in m["tris"]:
                tri = (vs[t[0]], vs[t[1]], vs[t[2]])
                lo, hi = min(v[2] for v in tri), max(v[2] for v in tri)
                for k in range(int(math.floor(lo * 100)), int(math.floor(hi * 100)) + 1):
                    self.buckets.setdefault(k, []).append(tri)

    def at(self, z: float) -> list[tuple[float, float, float]]:
        return [q for piece in self.pieces(z) for q in piece]

    def pieces(self, z: float) -> list[list[tuple[float, float, float]]]:
        """The section's connected pieces: each crossed triangle joins its two crossing points. The plane is moved
        up 12 microns so that no vertex (the probe rounds them to 0.1 mm) lies on it."""
        z += 1.2e-5
        key, parent, pts = {}, [], []

        def node(q):
            k = (round(q[0], 6), round(q[1], 6))
            if k not in key:
                key[k] = len(pts)
                pts.append(q)
                parent.append(len(parent))
            return key[k]

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        for tri in self.buckets.get(int(math.floor(z * 100)), ()):
            cross = []
            for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
                if (a[2] - z) * (b[2] - z) < 0:
                    lo, hi = (a, b) if (a[0], a[1], a[2]) < (b[0], b[1], b[2]) else (b, a)
                    t = (z - lo[2]) / (hi[2] - lo[2])
                    cross.append(node((lo[0] + t * (hi[0] - lo[0]), lo[1] + t * (hi[1] - lo[1]), z)))
            if len(cross) == 2:
                parent[find(cross[0])] = find(cross[1])
        groups = {}
        for i, q in enumerate(pts):
            groups.setdefault(find(i), []).append(q)
        return list(groups.values())


def points(probe: dict, names=None) -> "Sections":
    return Sections(probe, names)


def intervals(vals: list[float], gap: float = 0.012) -> list[tuple[float, float]]:
    """Sorted values merged into runs wherever neighbours are closer than gap."""
    out = []
    for v in sorted(vals):
        if out and v - out[-1][1] <= gap:
            out[-1][1] = v
        else:
            out.append([v, v])
    return [tuple(r) for r in out]


def slab(pts, z: float, h: float = 0.006):
    """The section at z (pts a Sections), or the points within h/2 of z (a plain list)."""
    if isinstance(pts, Sections):
        return pts.at(z)
    return [p for p in pts if abs(p[2] - z) <= h / 2]


def clusters(sec, gap: float = 0.03) -> list[list]:
    """A section's points grouped into pieces (points closer than gap in x and y are one piece)."""
    cell = {}
    for i, q in enumerate(sec):
        cell.setdefault((int(q[0] // gap), int(q[1] // gap)), []).append(i)
    parent = list(range(len(sec)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for (cx, cy), idx in cell.items():
        near = [j for dx in (-1, 0, 1) for dy in (-1, 0, 1) for j in cell.get((cx + dx, cy + dy), ())]
        for i in idx:
            for j in near:
                if j > i and (sec[i][0] - sec[j][0]) ** 2 + (sec[i][1] - sec[j][1]) ** 2 <= gap * gap:
                    parent[find(i)] = find(j)
    groups = {}
    for i in range(len(sec)):
        groups.setdefault(find(i), []).append(sec[i])
    return list(groups.values())


def _pieces(pts, z: float):
    return pts.pieces(z) if isinstance(pts, Sections) else [slab(pts, z)]


def trunk_x(pts, z: float):
    """The x range of the section's piece that spans x = 0 (the trunk), or None (between the legs)."""
    for c in _pieces(pts, z):
        lo, hi = min(q[0] for q in c), max(q[0] for q in c)
        if lo < -0.01 and hi > 0.01:
            return lo, hi
    return None


def leg_x(pts, z: float, side: float = 1.0):
    """The x range of one leg's piece at z (side +1 her left, x > 0), or None."""
    cs = [(min(q[0] for q in c), max(q[0] for q in c)) for c in _pieces(pts, z)]
    cs = [r for r in cs if (r[0] + r[1]) / 2 * side > 0.02 and r[1] - r[0] > 0.03]
    return min(cs, key=lambda r: abs((r[0] + r[1]) / 2 - side * 0.11)) if cs else None


def body_landmarks(probe: dict, body: str) -> dict:
    """Her landmarks in cm, measured on the rest mesh and bones (x lateral, z up from the sole, front at -y)."""
    pts = points(probe, [body])
    bones = probe["bones"]
    lm = {"sole": min(p[2] for p in pts.pts)}
    lm["ankle"] = bones["LeftFoot"]["head"][2]
    lm["knee"] = bones["LeftLowerLeg"]["head"][2]
    lm["collarbone"] = bones["LeftShoulder"]["head"][2]
    zs = [i / 1000 for i in range(600, 1000, 2)]
    lm["crotch"] = max(z for z in zs if trunk_x(pts, z) is None)
    # armpit: the highest z under the arm's axis where the trunk's run and the arm's run are apart
    arm_z = bones["LeftUpperArm"]["head"][2]
    z = arm_z
    while z > arm_z - 0.3:
        t = trunk_x(pts, z)
        if t and t[1] < 0.3:
            break
        z -= 0.002
    lm["armpit"] = z
    torso = [p for p in pts.pts if abs(p[0]) < 0.15 and lm["crotch"] + 0.1 < p[2] < lm["armpit"] + 0.06]
    bust = min(torso, key=lambda p: p[1])
    lm["bust"] = bust[2]
    lm["bust_y"] = bust[1]
    wz = [i / 1000 for i in range(int(lm["crotch"] * 1000) + 120, int(lm["bust"] * 1000) - 40, 3)]
    widths = {z: (lambda r: r[1] - r[0])(trunk_x(pts, z)) for z in wz if trunk_x(pts, z)}
    lm["waist"] = min(widths, key=widths.get)
    lm["waist_w"] = widths[lm["waist"]]
    hz = [i / 1000 for i in range(int(lm["crotch"] * 1000) + 10, int(lm["waist"] * 1000), 3)]
    hw = {z: (lambda r: r[1] - r[0])(trunk_x(pts, z)) for z in hz if trunk_x(pts, z)}
    lm["hip_z"] = max(hw, key=hw.get)
    lm["hip_w"] = hw[lm["hip_z"]]
    lm["bust_w"] = (lambda r: r[1] - r[0])(trunk_x(pts, lm["bust"]))
    lm["chest_w"] = (lambda r: r[1] - r[0])(trunk_x(pts, lm["armpit"] - 0.03))
    # shoulder_top: where the strap runs over the shoulder, 3 cm outside the neck: the height at which the trunk's
    # half width falls under the neck's (3 cm above the Neck bone) plus 3 cm
    neck_z = bones["Neck"]["head"][2] + 0.03
    nx = max(abs(v) for v in trunk_x(pts, neck_z))
    lm["neck_half_w"] = nx
    z = lm["collarbone"]
    while z < neck_z and max(abs(v) for v in trunk_x(pts, z)) > nx + 0.03:
        z += 0.002
    lm["shoulder_top"] = z
    lm["shoulder_w"] = 2 * bones["LeftUpperArm"]["head"][0]
    lm["thigh_w"] = (lambda r: r[1] - r[0])(leg_x(pts, lm["crotch"] - 0.03))
    lm["knee_w"] = (lambda r: r[1] - r[0])(leg_x(pts, lm["knee"]))
    lm["ankle_w"] = (lambda r: r[1] - r[0])(leg_x(pts, lm["ankle"] + 0.04))
    lm["bust_d"] = max(p[1] for p in slab(pts, lm["bust"]) if abs(p[0]) < 0.12) - lm["bust_y"]
    lm["torso_span"] = lm["shoulder_top"] - lm["waist"]
    lm["hip_z_span"] = lm["waist"] - lm["crotch"]
    return {k: round(v * 100, 2) for k, v in lm.items()}


def mm_line(lm: dict) -> str:
    return ", ".join(f"{k} {v}" for k, v in lm.items())


def lean_deg(top_y: float, top_z: float, bottom_y: float, bottom_z: float) -> float:
    """A panel's lean in side view, degrees from vertical; positive: its top stands forward (toward -y)."""
    return math.degrees(math.atan2(bottom_y - top_y, top_z - bottom_z))
