"""The ragdoll data of a character (art #115; docs/contract.md, "Ragdoll"): per simulated bone a collision shape, a mass
share and a joint, measured from the character's own GLB, which the game turns into PhysicalBone3D nodes at import
(the reference builder: godot/ragdoll/builder.gd).

Measured in plain Python from the GLB, not in Blender: the GLB's joint nodes are the frames Godot's Skeleton3D uses
(a bone's rest is its node's local transform), so the shapes need no axis conversion, and the measure runs without
Blender in about a second. Every vertex goes to the bone of its largest skin weight, then up the skeleton to the
nearest simulated bone (a finger to the hand, the toes to the foot, a shoulder to the chest); each simulated bone's
vertices, in its rest frame, give its shape: a box or a capsule along the bone's Y, from robust percentiles."""

from __future__ import annotations

import json
import math
import struct
from pathlib import Path
from typing import Any

FORMAT = "prime-ragdoll"
VERSION = 1
TOTAL_MASS_KG = 70.0
PERCENTILE = 0.02  # a shape spans the 2nd to the 98th percentile of its vertices (stray hair or cloth tips stay out)
RADIUS_PERCENTILE = 0.85  # a capsule's radius: this share of its vertices lies inside it
SHRINK = 0.92  # shapes a little inside the skin, so limbs resting on the floor do not float
# The game's physics layers (prime-game project.godot, [layer_names]): 1 world, 2 living_players, 3 downed, 4 movers.
# The ragdoll's parts are on `downed` and collide with `world` only (prime-game PR #754, KE7): never players, another
# ragdoll or a client-only object; nor with each other (their own layer is not in their mask).
COLLISION = {"layer": 3, "layer_name": "downed", "mask": [1], "mask_names": ["world"]}
# Body defaults for every PhysicalBone3D (the builder applies them); the angular damping settles the body.
MATERIAL = {"friction": 0.8, "bounce": 0.0, "linear_damp": 0.1, "angular_damp": 3.0}

# The simulated bones of the Ultimate Modular rig (the export's 64-bone names, the game keeps them until a contract
# v2), their humanoid profile names (tools/runner/commands/_humanoid.py), physical parent, shape kind, mass share
# (Dempster's segment table as Winter gives it; head and neck split; the trunk in three) and joint.
#   cone:  swing_deg (the half-angle of the cone around the bone's Y), twist_deg (either way about Y)
#   hinge: flexion about `axis` (measured), min_deg..max_deg, positive = the anatomical bend (the elbow forwards,
#          the knee backwards); the axis follows from `bend` (the model-space direction the child's tip moves in)
SIDES = (("L", "Left", 1.0), ("R", "Right", -1.0))
# The pelvis is the rig's `Body`, the parent of `Hips` (it carries the pelvis's skin with `Hips`): a parent cannot
# follow a simulated child, so `Body` is the root body and `Hips` follows it with the rest of the pelvis.
_TRUNK = [
    # bone, profile, parent, shape, share, joint
    ("Body", "Hips", None, "box", 0.142, None),
    ("Abdomen", "Spine", "Body", "box", 0.139, {"type": "cone", "swing_deg": 25.0, "twist_deg": 15.0}),
    ("Torso", "Chest", "Abdomen", "box", 0.216, {"type": "cone", "swing_deg": 25.0, "twist_deg": 15.0}),
    ("Neck", "Neck", "Torso", "capsule", 0.081, {"type": "cone", "swing_deg": 40.0, "twist_deg": 45.0}),
]
# Bones whose vertices shape another body: the head and the neck are one body, jointed at the neck's base, its shape
# fitted to the head (with the hair) alone. Measured: a 0.8 kg neck between the 15 kg chest and the 4.8 kg head let
# the head's joint swing 30 to 40 degrees past its limit at the landing.
FIT = {"Head": "Neck"}
_LIMB = [
    ("UpperArm", "UpperArm", "Torso", "capsule", 0.028, {"type": "cone", "swing_deg": 80.0, "twist_deg": 45.0}),
    ("LowerArm", "LowerArm", "UpperArm", "capsule", 0.016,
     {"type": "hinge", "min_deg": -5.0, "max_deg": 140.0, "bend": [0.0, 0.0, 1.0]}),
    ("Wrist", "Hand", "LowerArm", "box", 0.006, {"type": "cone", "swing_deg": 50.0, "twist_deg": 20.0}),
    ("UpperLeg", "UpperLeg", "Body", "capsule", 0.100, {"type": "cone", "swing_deg": 60.0, "twist_deg": 20.0}),
    ("LowerLeg", "LowerLeg", "UpperLeg", "capsule", 0.0465,
     {"type": "hinge", "min_deg": -5.0, "max_deg": 140.0, "bend": [0.0, 0.0, -1.0]}),
    ("Foot", "Foot", "LowerLeg", "box", 0.0145, {"type": "cone", "swing_deg": 30.0, "twist_deg": 10.0}),
]


def plan() -> list[dict[str, Any]]:
    """The simulated bones in build order (every parent before its children)."""
    out = [{"bone": b, "profile": p, "parent": par, "shape": s, "mass_share": m, "joint": j} for b, p, par, s, m, j in _TRUNK]
    for s, side, _ in SIDES:
        for b, p, par, shape, m, j in _LIMB:
            parent = par if par in ("Torso", "Body") else f"{par}.{s}"
            out.append({"bone": f"{b}.{s}", "profile": f"{side}{p}", "parent": parent, "shape": shape, "mass_share": m,
                        "joint": dict(j) if j else None})
    return out


# ---- the GLB ---------------------------------------------------------------------------------------------------------

_COMPONENTS = {5120: "b", 5121: "B", 5122: "h", 5123: "H", 5125: "I", 5126: "f"}
_WIDTH = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
_NORM = {5121: 255.0, 5123: 65535.0, 5120: 127.0, 5122: 32767.0}


def read_glb(path: Path) -> tuple[dict[str, Any], bytes]:
    data = path.read_bytes()
    if data[:4] != b"glTF":
        raise ValueError(f"{path} is not a GLB")
    length = struct.unpack_from("<I", data, 12)[0]
    gltf = json.loads(data[20:20 + length])
    at = 20 + length
    blob = b""
    if at + 8 <= len(data):
        blen = struct.unpack_from("<I", data, at)[0]
        blob = data[at + 8:at + 8 + blen]
    return gltf, blob


def accessor(gltf: dict[str, Any], blob: bytes, index: int) -> list[tuple[float, ...]]:
    acc = gltf["accessors"][index]
    if "sparse" in acc or "bufferView" not in acc:
        raise ValueError(f"accessor {index}: sparse or empty accessors are not read")
    view = gltf["bufferViews"][acc["bufferView"]]
    code, width = _COMPONENTS[acc["componentType"]], _WIDTH[acc["type"]]
    size = struct.calcsize("<" + code)
    stride = view.get("byteStride") or size * width
    start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    fmt = "<" + code * width
    scale = _NORM.get(acc["componentType"]) if acc.get("normalized") else None
    out = []
    for i in range(acc["count"]):
        v = struct.unpack_from(fmt, blob, start + i * stride)
        out.append(tuple(x / scale for x in v) if scale else v)
    return out


# ---- 4x4 matrices (row-major lists; points are columns) ------------------------------------------------------------

def mat(t=(0.0, 0.0, 0.0), q=(0.0, 0.0, 0.0, 1.0), s=(1.0, 1.0, 1.0)) -> list[list[float]]:
    x, y, z, w = q
    r = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
         [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
         [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
    return [[r[i][0] * s[0], r[i][1] * s[1], r[i][2] * s[2], t[i]] for i in range(3)] + [[0.0, 0.0, 0.0, 1.0]]


def mul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def apply(m: list[list[float]], p) -> tuple[float, float, float]:
    return tuple(m[i][0] * p[0] + m[i][1] * p[1] + m[i][2] * p[2] + m[i][3] for i in range(3))


def rigid_inverse(m: list[list[float]]) -> list[list[float]]:
    """The inverse of a rotation (with near-unit scale) and translation."""
    r = [[m[j][i] for j in range(3)] for i in range(3)]
    t = [-sum(r[i][k] * m[k][3] for k in range(3)) for i in range(3)]
    return [r[i] + [t[i]] for i in range(3)] + [[0.0, 0.0, 0.0, 1.0]]


def _node_mat(node: dict[str, Any]) -> list[list[float]]:
    if "matrix" in node:
        m = node["matrix"]
        return [[m[c * 4 + r] for c in range(4)] for r in range(4)]
    return mat(node.get("translation", (0, 0, 0)), node.get("rotation", (0, 0, 0, 1)), node.get("scale", (1, 1, 1)))


def _norm(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _pct(values: list[float], q: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))]


# ---- the measure -----------------------------------------------------------------------------------------------------

def skeleton(gltf: dict[str, Any]) -> dict[str, Any]:
    """The skin's bones: name, skeleton parent (None for a top bone) and the rest pose in skeleton space (the skin's
    joints' common parent node, which Godot's Skeleton3D sits on)."""
    skin = gltf["skins"][0]
    joints = skin["joints"]
    nodes = gltf["nodes"]
    parent_of = {c: i for i, n in enumerate(nodes) for c in n.get("children", [])}
    rest = {j: _node_mat(nodes[j]) for j in joints}
    glob: dict[int, list[list[float]]] = {}

    def g(j: int) -> list[list[float]]:
        if j not in glob:
            p = parent_of.get(j)
            glob[j] = mul(g(p), rest[j]) if p in rest else rest[j]
        return glob[j]

    names = [nodes[j]["name"] for j in joints]
    parents = {nodes[j]["name"]: (nodes[parent_of[j]]["name"] if parent_of.get(j) in rest else None) for j in joints}
    return {"joints": joints, "names": names, "parents": parents, "global": {nodes[j]["name"]: g(j) for j in joints}}


def vertices(gltf: dict[str, Any], blob: bytes, skel: dict[str, Any]) -> list[tuple[tuple[float, float, float], str]]:
    """Every skinned vertex at rest in skeleton space, with the bone of its largest weight."""
    names = skel["names"]
    ibm = accessor(gltf, blob, gltf["skins"][0]["inverseBindMatrices"])
    skin_m = [mul(skel["global"][n], [[m[c * 4 + r] for c in range(4)] for r in range(4)]) for n, m in zip(names, ibm)]
    out = []
    for node in gltf["nodes"]:
        if "mesh" not in node or node.get("skin") != 0:
            continue
        for prim in gltf["meshes"][node["mesh"]]["primitives"]:
            att = prim["attributes"]
            if "JOINTS_0" not in att:
                continue
            pos = accessor(gltf, blob, att["POSITION"])
            js = accessor(gltf, blob, att["JOINTS_0"])
            ws = accessor(gltf, blob, att["WEIGHTS_0"])
            for p, j, w in zip(pos, js, ws):
                total = sum(w) or 1.0
                acc = [0.0, 0.0, 0.0]
                for k in range(4):
                    if w[k] > 0:
                        q = apply(skin_m[j[k]], p)
                        for i in range(3):
                            acc[i] += q[i] * w[k] / total
                best = max(range(4), key=lambda k: w[k])
                out.append((tuple(acc), names[j[best]]))
    return out


def owner(bone: str, parents: dict[str, str | None], simulated: set[str]) -> str | None:
    """The simulated bone a bone follows: itself or its nearest simulated ancestor; None above the hips."""
    b: str | None = bone
    while b is not None and b not in simulated:
        b = parents.get(b)
    return b


def _box(local: list[tuple[float, float, float]]) -> tuple[list[float], list[float]]:
    lo = [_pct([p[i] for p in local], PERCENTILE) for i in range(3)]
    hi = [_pct([p[i] for p in local], 1 - PERCENTILE) for i in range(3)]
    centre = [(lo[i] + hi[i]) / 2 for i in range(3)]
    size = [(hi[i] - lo[i]) * SHRINK for i in range(3)]
    return centre, size


def _capsule(local: list[tuple[float, float, float]]) -> tuple[list[float], float, float]:
    centre, size = _box(local)
    radial = [math.hypot(p[0] - centre[0], p[2] - centre[2]) for p in local]
    radius = _pct(radial, RADIUS_PERCENTILE) * SHRINK
    height = max(size[1], 2 * radius + 0.01)
    return centre, radius, height


def measure(glb: Path, asset: str | None = None) -> dict[str, Any]:
    """The ragdoll data of a character GLB on the Ultimate Modular rig."""
    gltf, blob = read_glb(glb)
    skel = skeleton(gltf)
    bones = plan()
    simulated = {b["bone"] for b in bones}
    missing = sorted(simulated - set(skel["names"]))
    if missing:
        raise ValueError(f"{glb.name} lacks the simulated bones {', '.join(missing)}")
    parents = dict(skel["parents"])
    # The rig's feet hang from Root (an IK-style rig), not from the lower legs: they belong to the lower legs' chain.
    for s, _, _ in SIDES:
        parents[f"Foot.{s}"] = f"LowerLeg.{s}"
    owners = simulated | set(FIT)
    points: dict[str, list] = {b: [] for b in owners}
    unowned: dict[str, int] = {}
    for p, bone in vertices(gltf, blob, skel):
        o = owner(bone, parents, owners)
        if o is None:
            unowned[bone] = unowned.get(bone, 0) + 1
        else:
            points[o].append(p)
    allp = [p for ps in points.values() for p in ps]
    lo = [min(p[i] for p in allp) for i in range(3)]
    hi = [max(p[i] for p in allp) for i in range(3)]
    for b in bones:
        g = skel["global"][b["bone"]]
        inv = rigid_inverse(g)
        fitted = [k for k, v in FIT.items() if v == b["bone"]]
        local = [apply(inv, p) for p in (points[fitted[0]] if fitted else points[b["bone"]])]
        if fitted:
            b["fit"] = fitted[0]
        if len(local) < 8:
            raise ValueError(f"{b['bone']}: only {len(local)} vertices")
        b["vertices"] = len(local)
        if b["shape"] == "box":
            centre, size = _box(local)
            b["size"] = [round(x, 4) for x in size]
        else:
            centre, radius, height = _capsule(local)
            b["radius"], b["height"] = round(radius, 4), round(height, 4)
        b["offset"] = [round(x, 4) for x in centre]
        b["rotation"] = [0.0, 0.0, 0.0, 1.0]
        b["mass_kg"] = round(b["mass_share"] * TOTAL_MASS_KG, 3)
        b["skeleton_parent"] = skel["parents"][b["bone"]]
        j = b["joint"]
        if j is None:
            continue
        j["anchor"] = [0.0, 0.0, 0.0]
        if b["bone"].startswith("Foot."):
            # The ankle: the foot's own head lies at the heel on the ground; the joint sits where the lower leg's
            # capsule ends, expressed in the foot's frame.
            leg = next(x for x in bones if x["bone"] == b["parent"])
            tip = [leg["offset"][0], leg["offset"][1] + leg["height"] / 2 - leg["radius"], leg["offset"][2]]
            ankle = apply(skel["global"][leg["bone"]], tip)
            j["anchor"] = [round(x, 4) for x in apply(inv, ankle)]
        if j["type"] == "hinge":
            bend = j.pop("bend")
            yb = _norm([g[i][1] for i in range(3)])
            axis_w = _norm(_cross(yb, bend))
            axis = _norm([sum(inv[i][k] * axis_w[k] for k in range(3)) for i in range(3)])
            j["axis"] = [round(x, 4) for x in axis]
    followers = {n: owner(n, parents, simulated) for n in skel["names"] if n not in simulated}
    return {
        "format": FORMAT, "version": VERSION, "asset": asset or glb.stem, "glb": glb.name,
        "units": "metres, kilograms, degrees; shapes and anchors in the bone's rest frame (Y along the bone)",
        "rotation": "a quaternion [x, y, z, w] in the bone's rest frame",
        "hinge": "flexion about `axis` (in the bone's frame), positive is the anatomical bend; limits from the start pose",
        "cone": "swing_deg: the half-angle around the bone's Y; twist_deg: either way about Y; from the start pose",
        "total_mass_kg": TOTAL_MASS_KG, "collision": COLLISION, "material": MATERIAL,
        "bounds": {"min": [round(x, 4) for x in lo], "max": [round(x, 4) for x in hi]},
        "bones": bones,
        "followers": {k: v for k, v in sorted(followers.items())},
        "unweighted_or_above_hips": unowned,
    }


# ---- the check -------------------------------------------------------------------------------------------------------

def check(data: dict[str, Any], skeleton_names: list[str] | None = None) -> list[str]:
    """The data's schema and values; returns the problems (empty when it passes)."""
    bad = []
    if data.get("format") != FORMAT or data.get("version") != VERSION:
        bad.append(f"format {data.get('format')} {data.get('version')}, want {FORMAT} {VERSION}")
    bones = data.get("bones", [])
    names = [b.get("bone") for b in bones]
    if len(set(names)) != len(names):
        bad.append("a bone is listed twice")
    seen: set[str] = set()
    lo, hi = data.get("bounds", {}).get("min"), data.get("bounds", {}).get("max")
    share = 0.0
    for b in bones:
        n = b.get("bone")
        if skeleton_names is not None and n not in skeleton_names:
            bad.append(f"{n}: not in the skeleton")
        if b.get("parent") is not None and b["parent"] not in seen:
            bad.append(f"{n}: its parent {b['parent']} is not listed before it")
        seen.add(n)
        share += b.get("mass_share", 0)
        if not 0 < b.get("mass_share", 0) < 0.5:
            bad.append(f"{n}: mass share {b.get('mass_share')}")
        if b.get("shape") == "box":
            dims = b.get("size", [])
            if len(dims) != 3 or min(dims) <= 0:
                bad.append(f"{n}: box size {dims}")
            half = max(dims) / 2 if dims else 0
        elif b.get("shape") == "capsule":
            r, h = b.get("radius", 0), b.get("height", 0)
            if r <= 0 or h < 2 * r:
                bad.append(f"{n}: capsule radius {r} height {h}")
            half = h / 2
        else:
            bad.append(f"{n}: shape {b.get('shape')}")
            half = 0
        if half > 0.6:
            bad.append(f"{n}: a shape {2 * half:.2f} m long")
        q = b.get("rotation", [])
        if len(q) != 4 or abs(math.sqrt(sum(x * x for x in q)) - 1) > 1e-3:
            bad.append(f"{n}: rotation {q} is not a unit quaternion")
        j = b.get("joint")
        if b.get("parent") is None:
            if j is not None:
                bad.append(f"{n}: the root body has a joint")
            continue
        if not j:
            bad.append(f"{n}: no joint")
            continue
        if j.get("type") == "cone":
            if not (0 < j.get("swing_deg", 0) <= 90 and 0 <= j.get("twist_deg", -1) <= 90):
                bad.append(f"{n}: cone limits {j}")
        elif j.get("type") == "hinge":
            if not (-30 <= j.get("min_deg", 1) <= 0 < j.get("max_deg", 0) <= 160):
                bad.append(f"{n}: hinge limits {j}")
            if abs(math.sqrt(sum(x * x for x in j.get("axis", [0, 0, 0]))) - 1) > 1e-3:
                bad.append(f"{n}: hinge axis {j.get('axis')}")
        elif j.get("type") != "pin":
            bad.append(f"{n}: joint type {j.get('type')}")
        if len(j.get("anchor", [])) != 3:
            bad.append(f"{n}: joint anchor {j.get('anchor')}")
    if abs(share - 1.0) > 0.01:
        bad.append(f"the mass shares sum to {share:.3f}")
    if lo is None or hi is None:
        bad.append("no bounds")
    return bad


def shapes_in_bounds(data: dict[str, Any], skel_global: dict[str, list[list[float]]], margin: float = 0.03) -> list[str]:
    """Every shape's centre lies inside the body's rest bounds (plus margin)."""
    lo, hi = data["bounds"]["min"], data["bounds"]["max"]
    bad = []
    for b in data["bones"]:
        c = apply(skel_global[b["bone"]], b["offset"])
        if any(c[i] < lo[i] - margin or c[i] > hi[i] + margin for i in range(3)):
            bad.append(f"{b['bone']}: shape centre {tuple(round(x, 3) for x in c)} outside the body")
    return bad


def write(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8", newline="\n")


def sha256(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()
