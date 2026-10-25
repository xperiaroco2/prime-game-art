"""Pure formulas of the static head's liveliness proof (art #196, lively): the neck and crest weights, the gaze
offsets and their lid clamp, a minimal skin written into an existing GLB, and a plain PNG writer. No Blender import:
tools/tests/test_alien_lively_geom.py runs them with the standard library; alien_lively_build.py calls the same
functions (the weights on plain floats per vertex). godot/alien/alien_lively.gd and the web module
(`lively/web/lively.js`) repeat the gaze maths (eye_frame, gaze_dir, eye_offsets, clamp_gaze with its 25-degree
`cap_deg`) line for line.
"""
from __future__ import annotations

import json
import math
import struct
import zlib
from array import array
from pathlib import Path

GLB_MAGIC = 0x46546C67
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942
# the joints, in skin order; parents by index (-1: the skin's root)
JOINTS = ("Chest", "Neck", "Head", "Crest1", "Crest2", "Crest3")
PARENTS = (-1, 0, 1, 2, 3, 4)
# the axolotl (2026-10-23, AL1): one bone per gill stalk, each a child of Head (L the head's left, +X; 1 the top)
GILLS = ("GillL1", "GillL2", "GillL3", "GillR1", "GillR2", "GillR3")
GILL_JOINTS = ("Chest", "Neck", "Head") + GILLS
GILL_PARENTS = (-1, 0, 1) + (2,) * len(GILLS)
# the gill poke test (AL2): a moved gill vertex is a poke when it ends more than POKE_TOL inside the skull (metres),
# by both inside tests (AL3); the swing is tested at the controllers' four axis ends and four corners (yaw, pitch
# signs), both clamped at the same cap. AL6 (PR #306 review): every gill vertex weighted over TEST_W that moves more
# than MOVED_EPS (metres) is tested; only those already inside the skull at rest are left out (and counted). AL2 to
# AL5 also left out the root band (weights under 0.35) and the vertices within 3 mm of the skull at rest, the
# likeliest to poke.
POKE_TOL = 0.001
TEST_W = 0.01
# the gill weights' lifts (alien_lively_build.py --gill-lift; AL7: every build weighs and poke-tests all of them)
GILL_LIFTS = ("centre", "skull", "centre_pinned")
MOVED_EPS = 1e-5
SWING_CORNERS = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
SPRING_MAX_DEG = 15.0  # the gills' cap at most (the measured limit when lower)


def spring_matrix(yaw: float, pitch: float) -> list[list[float]]:
    """The 3 x 3 rotation the controllers give a spring bone (radians): Godot's Quaternion.from_euler(Vector3(-pitch,
    yaw, 0)) and three.js's Euler(-pitch, yaw, 0, "YXZ"), both Ry(yaw) * Rx(-pitch); a column vector's turn."""
    cy, sy, cx, sx = math.cos(yaw), math.sin(yaw), math.cos(-pitch), math.sin(-pitch)
    ry = ((cy, 0.0, sy), (0.0, 1.0, 0.0), (-sy, 0.0, cy))
    rx = ((1.0, 0.0, 0.0), (0.0, cx, -sx), (0.0, sx, cx))
    return [[sum(ry[i][k] * rx[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


# AL3: the bead's glint at a head turn: how far past its rest angle from the bead's front it may slide (radians);
# alien_lively.gd CATCH_MARGIN, lively.js CATCH_MARGIN; the shaders' clamp is glint_dir
CATCH_MARGIN = 0.12


def catch_reach(rest, catch_dir, margin: float = CATCH_MARGIN) -> float:
    """How far from the posed bead front the glint may sit (radians): the rest angle between the bead's front and the
    catch light's direction, plus margin (alien_lively.gd catch_reach, lively.js catchReach)."""
    r, d = _norm(rest), _norm(catch_dir)
    return math.acos(max(-1.0, min(1.0, sum(a * b for a, b in zip(r, d))))) + margin


def glint_dir(front, catch_dir, reach: float) -> tuple[float, float, float]:
    """The glint's direction from the eye centre (alien_static.gdshader and lively.js): the fixed catch direction,
    turned toward the posed bead front until it is at most reach from it (reach 0: unclamped)."""
    f, d = _norm(front), _norm(catch_dir)
    c = max(-1.0, min(1.0, sum(a * b for a, b in zip(f, d))))
    if reach <= 0.0 or math.acos(c) <= reach:
        return d
    perp = _norm(tuple(b - a * c for a, b in zip(f, d)))
    return _norm(tuple(a * math.cos(reach) + p * math.sin(reach) for a, p in zip(f, perp)))


def smoothstep(e0: float, e1: float, x: float) -> float:
    t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


def neck_weights(y: float, y0: float, ym: float, y1: float) -> tuple[float, float, float]:
    """(chest, neck, head) by height: the chest below y0, the head above y1, the neck a hat peaking at ym."""
    chest = 1.0 - smoothstep(y0, ym, y)
    head = smoothstep(ym, y1, y)
    return chest, max(0.0, 1.0 - chest - head), head


def crest_split(t: float) -> tuple[float, float, float]:
    """The crest weight's share per crest bone at t (0 the crest root, 1 its tip): each bone owns its third, blended
    linearly between neighbours' centres."""
    tt = min(max(t * 3.0 - 0.5, 0.0), 2.0)
    k = min(int(tt), 1)
    f = tt - k
    w = [0.0, 0.0, 0.0]
    w[k] = 1.0 - f
    w[k + 1] = f
    return w[0], w[1], w[2]


def _norm(v):
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / n for c in v)


def eye_frame(rest: tuple[float, float, float]) -> tuple[tuple, tuple, tuple]:
    """(fwd, side, up) of an eye: fwd its rest gaze, side toward +X (the head's left), up toward +Y."""
    f = _norm(rest)
    s = _norm((f[2], 0.0, -f[0]))  # cross(+Y, fwd)
    u = (f[1] * s[2] - f[2] * s[1], f[2] * s[0] - f[0] * s[2], f[0] * s[1] - f[1] * s[0])  # cross(fwd, side)
    return f, s, _norm(u)


def gaze_offsets(t: tuple[float, float, float]) -> tuple[float, float]:
    """(yaw, pitch) in radians of a direction in the head's frame (+Z forward, +Y up, yaw positive toward +X)."""
    return math.atan2(t[0], t[2]), math.atan2(t[1], math.hypot(t[0], t[2]))


def gaze_dir(rest: tuple[float, float, float], yaw: float, pitch: float) -> tuple[float, float, float]:
    """The eye's gaze turned from its rest gaze by (yaw, pitch)."""
    f, s, u = eye_frame(rest)
    a, b = math.tan(yaw), math.tan(pitch)
    return _norm(tuple(f[i] + a * s[i] + b * u[i] for i in range(3)))


def eye_offsets(rest: tuple[float, float, float], t: tuple[float, float, float]) -> tuple[float, float]:
    """(yaw, pitch) in radians of a direction t in the eye's rest frame (eye_frame): gaze_dir's inverse, so
    gaze_dir(rest, *eye_offsets(rest, t)) points along t. The lid limits are measured in this frame."""
    f, s, u = eye_frame(rest)
    a = sum(t[i] * f[i] for i in range(3))
    return math.atan2(sum(t[i] * s[i] for i in range(3)), a), math.atan2(sum(t[i] * u[i] for i in range(3)), a)


def clamp_gaze(yaw: float, pitch: float, lim: dict, cap_deg: float | None = None) -> tuple[float, float]:
    """(yaw, pitch) pulled inside the lid ellipse: lim holds the degrees the lids allow toward +X (`pos_x`), -X
    (`neg_x`), up and down, each capped at cap_deg (the controllers' EYE_LIMIT, 25) when given; each quadrant is an
    ellipse through its two limits."""
    cap = math.inf if cap_deg is None else cap_deg
    ly = math.radians(min(lim["pos_x"] if yaw >= 0.0 else lim["neg_x"], cap))
    lp = math.radians(min(lim["up"] if pitch >= 0.0 else lim["down"], cap))
    if ly <= 0.0 or lp <= 0.0:
        return (min(max(yaw, -ly), ly) if ly > 0 else 0.0), (min(max(pitch, -lp), lp) if lp > 0 else 0.0)
    e = (yaw / ly) ** 2 + (pitch / lp) ** 2
    if e <= 1.0:
        return yaw, pitch
    k = 1.0 / math.sqrt(e)
    return yaw * k, pitch * k


def fit_sphere(points) -> tuple[tuple[float, float, float], float]:
    """(centre, radius) of the least-squares sphere through the points (the algebraic fit: 2 c . p + d = |p|^2,
    r^2 = d + |c|^2), solved by its 4 x 4 normal equations. At least four points not on one plane."""
    a = [[0.0] * 5 for _ in range(4)]
    for p in points:
        row = (2.0 * p[0], 2.0 * p[1], 2.0 * p[2], 1.0)
        b = p[0] * p[0] + p[1] * p[1] + p[2] * p[2]
        for i in range(4):
            for j in range(4):
                a[i][j] += row[i] * row[j]
            a[i][4] += row[i] * b
    for k in range(4):  # Gauss-Jordan with partial pivoting
        piv = max(range(k, 4), key=lambda i: abs(a[i][k]))
        if abs(a[piv][k]) < 1e-15:
            raise ValueError("degenerate points: no sphere")
        a[k], a[piv] = a[piv], a[k]
        for i in range(4):
            if i != k:
                f = a[i][k] / a[k][k]
                for j in range(k, 5):
                    a[i][j] -= f * a[k][j]
    x = [a[i][4] / a[i][i] for i in range(4)]
    c = (x[0], x[1], x[2])
    return c, math.sqrt(max(0.0, x[3] + c[0] * c[0] + c[1] * c[1] + c[2] * c[2]))


def pit_weight(theta: float, inner: float, outer: float, gap: float, gap_in: float, gap_out: float) -> float:
    """How far an eyeball vertex is projected onto its fitted sphere (the old iris's pit, art #196 eye pit): 1 inside
    `inner` (its angle from the rest gaze), fading to 0 at `outer`, times a fade-in over its distance `gap` to the
    nearest vertex a lid or socket triangle shares (0 below gap_in), so the lid line never moves."""
    return (1.0 - smoothstep(inner, outer, theta)) * smoothstep(gap_in, gap_out, gap)


def capped_weight(w: float, full_move: float, room: float, share: float, cap: float) -> float:
    """The pit weight w lowered so the vertex's move (w times full_move, its distance to the sphere) stays within
    cap and within share of its room, its distance to the nearest lid or socket triangle (the eye pit v4: a pull
    toward the sphere never reaches a lid, so no eyeball triangle crosses one)."""
    if w <= 0.0 or full_move <= 0.0:
        return max(w, 0.0)
    return min(w, max(0.0, min(cap, share * room)) / full_move)


def project_on_sphere(p, c, r: float, w: float) -> tuple[float, float, float]:
    """p moved the share w of the way to its radial projection on the sphere (c, r)."""
    d = [p[i] - c[i] for i in range(3)]
    n = math.sqrt(sum(x * x for x in d))
    if n < 1e-12:
        return tuple(p)
    return tuple(p[i] + w * (c[i] + d[i] / n * r - p[i]) for i in range(3))


def colour_distance(a, b) -> float:
    """The RGB distance of two colours (0..1 channels): the sclera ghost's measure."""
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def read_glb(data: bytes) -> tuple[dict, bytearray]:
    magic, _version, _length = struct.unpack_from("<III", data, 0)
    if magic != GLB_MAGIC:
        raise ValueError("not a GLB")
    jlen, jtype = struct.unpack_from("<II", data, 12)
    if jtype != JSON_CHUNK:
        raise ValueError("no JSON chunk first")
    doc = json.loads(data[20:20 + jlen])
    off = 20 + jlen
    blen, btype = struct.unpack_from("<II", data, off)
    if btype != BIN_CHUNK:
        raise ValueError("no BIN chunk")
    return doc, bytearray(data[off + 8:off + 8 + blen])


def write_glb(doc: dict, binary: bytes | bytearray) -> bytes:
    js = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    js += b" " * (-len(js) % 4)
    b = bytes(binary) + b"\0" * (-len(binary) % 4)
    total = 12 + 8 + len(js) + 8 + len(b)
    return (struct.pack("<III", GLB_MAGIC, 2, total) + struct.pack("<II", len(js), JSON_CHUNK) + js
            + struct.pack("<II", len(b), BIN_CHUNK) + b)


def _append_view(doc: dict, binary: bytearray, payload: bytes, target: int | None) -> int:
    binary.extend(b"\0" * (-len(binary) % 4))
    view = {"buffer": 0, "byteOffset": len(binary), "byteLength": len(payload)}
    if target is not None:
        view["target"] = target
    binary.extend(payload)
    doc["bufferViews"].append(view)
    doc["buffers"][0]["byteLength"] = len(binary)
    return len(doc["bufferViews"]) - 1


def normalise_weights(w: list[float]) -> list[float]:
    """Four weights summing to 1 in float32 (glTF's validator checks the sum), the largest absorbing the rest."""
    s = sum(w)
    w = [x / s for x in w] if s > 0 else [1.0, 0.0, 0.0, 0.0]
    f = [struct.unpack("<f", struct.pack("<f", x))[0] for x in w]
    big = max(range(4), key=lambda i: f[i])
    f[big] = struct.unpack("<f", struct.pack("<f", 1.0 - sum(f[i] for i in range(4) if i != big)))[0]
    return f


def add_skin(data: bytes, positions: dict[str, tuple[float, float, float]],
             influences: list[list[tuple[int, float]]], mesh_node: int = 0,
             joints: tuple[str, ...] = JOINTS, parents: tuple[int, ...] = PARENTS) -> bytes:
    """A GLB with a skin of `joints` (global rest positions, no rotation; `parents` by index, -1 the root, a parent
    before its children) on mesh_node's mesh: per vertex up to four (joint index, weight) pairs, in the mesh's single
    primitive's vertex order. Everything else is kept byte for byte; joint nodes are appended, the root joint added to
    the scene. The chameleon's JOINTS are the default; the axolotl's are GILL_JOINTS."""
    JOINTS, PARENTS = joints, parents  # noqa: N806 (the names below)
    if len(PARENTS) != len(JOINTS) or any(p >= k for k, p in enumerate(PARENTS)):
        raise ValueError("one parent per joint, each before its child")
    doc, binary = read_glb(data)
    prim = doc["meshes"][doc["nodes"][mesh_node]["mesh"]]["primitives"]
    count = doc["accessors"][prim[0]["attributes"]["POSITION"]]["count"]
    if len(prim) != 1 or len(influences) != count:
        raise ValueError(f"one primitive with {count} vertices expected, got {len(prim)} and {len(influences)}")
    if "skin" in doc["nodes"][mesh_node]:
        raise ValueError("the mesh node is skinned already")
    first = len(doc["nodes"])
    for k, name in enumerate(JOINTS):
        p = positions[name]
        parent = positions[JOINTS[PARENTS[k]]] if PARENTS[k] >= 0 else (0.0, 0.0, 0.0)
        node = {"name": name, "translation": [p[i] - parent[i] for i in range(3)]}
        kids = [first + j for j in range(len(JOINTS)) if PARENTS[j] == k]
        if kids:
            node["children"] = kids
        doc["nodes"].append(node)
    joints, weights = array("H"), array("f")
    for inf in influences:
        inf = sorted(inf, key=lambda jw: -jw[1])[:4]
        inf += [(0, 0.0)] * (4 - len(inf))
        w = normalise_weights([x for _, x in inf])
        joints.extend(j for j, _ in inf)
        weights.extend(w)
    ibm = array("f")
    for name in JOINTS:
        p = positions[name]
        ibm.extend([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, -p[0], -p[1], -p[2], 1])
    acc = doc["accessors"]
    jv = _append_view(doc, binary, joints.tobytes(), 34962)
    acc.append({"bufferView": jv, "componentType": 5123, "count": count, "type": "VEC4"})
    prim[0]["attributes"]["JOINTS_0"] = len(acc) - 1
    wv = _append_view(doc, binary, weights.tobytes(), 34962)
    acc.append({"bufferView": wv, "componentType": 5126, "count": count, "type": "VEC4"})
    prim[0]["attributes"]["WEIGHTS_0"] = len(acc) - 1
    iv = _append_view(doc, binary, ibm.tobytes(), None)
    acc.append({"bufferView": iv, "componentType": 5126, "count": len(JOINTS), "type": "MAT4"})
    doc.setdefault("skins", []).append({"name": "lively", "joints": list(range(first, first + len(JOINTS))),
                                        "inverseBindMatrices": len(acc) - 1, "skeleton": first})
    doc["nodes"][mesh_node]["skin"] = len(doc["skins"]) - 1
    doc["scenes"][doc.get("scene", 0)]["nodes"].append(first)
    return write_glb(doc, binary)


def read_vec3(doc: dict, binary: bytes | bytearray, i: int) -> list[tuple[float, float, float]]:
    """Accessor i's float32 VEC3 rows (tightly packed or strided)."""
    a = doc["accessors"][i]
    v = doc["bufferViews"][a["bufferView"]]
    if a["componentType"] != 5126 or a["type"] != "VEC3":
        raise ValueError("a float VEC3 accessor expected")
    stride = v.get("byteStride", 12)
    start = v.get("byteOffset", 0) + a.get("byteOffset", 0)
    return [struct.unpack_from("<3f", binary, start + k * stride) for k in range(a["count"])]


def write_floats(doc: dict, binary: bytearray, i: int, rows) -> None:
    """Writes float32 VEC3 or VEC4 rows (sequences of numbers) into accessor i's tightly packed bytes, and its min and
    max with them when the accessor has them (POSITION must)."""
    a = doc["accessors"][i]
    v = doc["bufferViews"][a["bufferView"]]
    n = {"VEC3": 3, "VEC4": 4}.get(a["type"], 0)
    if not n or v.get("byteStride", 4 * n) != 4 * n or a["componentType"] != 5126:
        raise ValueError("LIVELY interleaved or non-float VEC3/VEC4: cannot patch")
    rows = [tuple(float(c) for c in r) for r in rows]
    if len(rows) != a["count"] or any(len(r) != n for r in rows):
        raise ValueError(f"{a['count']} rows of {n} expected")
    start = v.get("byteOffset", 0) + a.get("byteOffset", 0)
    payload = struct.pack(f"<{n * len(rows)}f", *[c for r in rows for c in r])
    binary[start:start + len(payload)] = payload
    if "min" in a:
        f = list(struct.iter_unpack(f"<{n}f", payload))
        a["min"] = [min(r[j] for r in f) for j in range(n)]
        a["max"] = [max(r[j] for r in f) for j in range(n)]


def write_vec3(doc: dict, binary: bytearray, i: int, rows) -> None:
    """write_floats for a VEC3 accessor (POSITION, NORMAL)."""
    if doc["accessors"][i]["type"] != "VEC3":
        raise ValueError("a VEC3 accessor expected")
    write_floats(doc, binary, i, rows)


def orthogonal_tangent(n, t):
    """A TANGENT (x, y, z, w) made orthogonal to the normal n again: t - n (n . t), normalised, w kept (glTF wants
    them orthogonal; the sclera's new radial normals turned n under the old t)."""
    nn = _norm(n)
    d = sum(nn[i] * t[i] for i in range(3))
    o = [t[i] - nn[i] * d for i in range(3)]
    if math.sqrt(sum(c * c for c in o)) < 1e-9:  # t along n: any perpendicular
        o = list(_norm((nn[2], 0.0, -nn[0]) if abs(nn[1]) < 0.9 else (0.0, nn[2], -nn[1])))
    x, y, z = _norm(o)
    return (x, y, z, float(t[3]) if len(t) > 3 else 1.0)


def stalk_weight(s: float, length: float, thin: float, in_: float = 0.08, full: float = 0.45) -> float:
    """A gill stalk's bone weight at s along its axis from the root (metres) of a stalk `length` long, on a vertex
    of thinness `thin` (the detail map's G, 1 thin): none at the root and on the skull (thick), full from `full` of
    the length; the root's first `in_` of the length bends nothing."""
    return smoothstep(in_ * length, full * length, s) * smoothstep(0.25, 0.5, thin)


# AL4: a gill stalk's own geometry by its height over the skull: a vertex further from the head's centre than the
# stalk's root on the skull (its pivot's distance from the centre plus the pivot's depth under the mesh) by LIFT_IN
# starts to move, by LIFT_FULL it may move fully (metres); the detail map's thinness no longer gates it there
LIFT_IN = 0.005
LIFT_FULL = 0.06
SMOOTH_PASSES = 24
SMOOTH_ALPHA = 0.5


def stalk_weight_lifted(s: float, length: float, thin: float, lift: float, in_: float = 0.08, full: float = 0.45) -> float:
    """A gill stalk's bone weight (AL4): the ramp along the stalk (G.stalk_weight's, none in the root's first `in_`
    of the length, full from `full`) times the larger of the vertex's thinness gate and its lift over the skull
    (`lift` metres beyond the root's skull radius, LIFT_IN to LIFT_FULL). By thinness alone (AL1 to AL3) the
    stalk's thick core and the fin vertices the detail map reads thick stayed at 0 out on the stalk beside fully
    weighted fringe (99 mm of edge stretch at the cap); the skull itself (thick, no lift) still never moves."""
    gate = max(smoothstep(0.25, 0.5, thin), smoothstep(LIFT_IN, LIFT_FULL, lift))
    return smoothstep(in_ * length, full * length, s) * gate


def smooth_within(values: list[float], edges: list[tuple[int, int]], labels: list[int], label: int,
                  pinned: list[bool], passes: int = SMOOTH_PASSES, alpha: float = SMOOTH_ALPHA) -> list[float]:
    """Laplacian smoothing of one stalk's weights (AL4): each pass moves every vertex of `label` that is not pinned
    by `alpha` toward the mean of its neighbours of the same label (edges to other labels never count, so no weight
    crosses to a neighbouring stalk; vertices of other labels keep their value). Pinned vertices (the skull, the
    root band) keep theirs. Returns the new list."""
    nb: dict[int, list[int]] = {}
    for a, b in edges:
        if a != b and labels[a] == label and labels[b] == label:
            nb.setdefault(a, []).append(b)
            nb.setdefault(b, []).append(a)
    w = list(values)
    for _ in range(passes):
        nxt = list(w)
        for i, js in nb.items():
            if not pinned[i]:
                m = sum(w[j] for j in js) / len(js)
                nxt[i] = (1.0 - alpha) * w[i] + alpha * m
        w = nxt
    return w


def png_bytes(width: int, height: int, rgb: bytes) -> bytes:
    """An 8-bit RGB PNG (rows top first, filter 0)."""
    stride = width * 3
    raw = b"".join(b"\0" + rgb[y * stride:(y + 1) * stride] for y in range(height))

    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def write_png(path: Path, width: int, height: int, rgb: bytes) -> None:
    Path(path).write_bytes(png_bytes(width, height, rgb))


# R1: the eye rim cut along one smooth curve (alien_lively_build.rim_cut). A cut piece under this share of its parent
# triangle's area is a sliver: the cut is snapped through the nearest corner instead (no vertex moves).
RIM_CUT_MIN_SHARE = 0.10


def _fourier_row(p: float, order: int) -> list[float]:
    row = [1.0]
    for k in range(1, order + 1):
        row += [math.cos(k * p), math.sin(k * p)]
    return row


def fourier_eval(coef, p: float) -> float:
    """a0 + sum over k of a_k cos(k p) + b_k sin(k p), the coefficients as fourier_fit returns them."""
    return sum(c * x for c, x in zip(coef, _fourier_row(p, (len(coef) - 1) // 2)))


def fourier_fit(phi, val, order: int) -> list[float]:
    """The least squares periodic fit of val against the angle phi up to `order` (a0, a1, b1, ..., aK, bK): the
    normal equations solved by Gaussian elimination with partial pivoting. Needs more points than 2 order + 1."""
    m = 2 * order + 1
    if len(phi) <= m:
        raise ValueError(f"{m + 1} points at least for order {order}")
    A = [[0.0] * (m + 1) for _ in range(m)]
    for p, v in zip(phi, val):
        row = _fourier_row(p, order)
        for i in range(m):
            ri = row[i]
            for j in range(m):
                A[i][j] += ri * row[j]
            A[i][m] += ri * v
    for c in range(m):
        piv = max(range(c, m), key=lambda i: abs(A[i][c]))
        A[c], A[piv] = A[piv], A[c]
        if abs(A[c][c]) < 1e-12:
            raise ValueError("the angles do not span the fit (singular)")
        for i in range(m):
            if i != c:
                f = A[i][c] / A[c][c]
                A[i] = [a - f * b for a, b in zip(A[i], A[c])]
    return [A[i][m] / A[i][i] for i in range(m)]


def fourier_fit_trimmed(phi, val, order: int, k: float = 3.0, rounds: int = 3) -> tuple[list[float], list[bool]]:
    """fourier_fit, then `rounds` times refitted without the points whose residual is over k times the median absolute
    residual (a junction's spur, a stray rim edge). Returns the coefficients and which points the last fit kept."""
    keep = [True] * len(phi)
    coef = fourier_fit(phi, val, order)
    for _ in range(rounds):
        res = [abs(v - fourier_eval(coef, p)) for p, v in zip(phi, val)]
        med = sorted(res)[len(res) // 2]
        new = [x <= max(k * med, 1e-12) for x in res]
        if new == keep or sum(new) <= 2 * order + 1:
            break
        keep = new
        coef = fourier_fit([p for p, w in zip(phi, keep) if w], [v for v, w in zip(val, keep) if w], order)
    return coef, keep


def cut_triangle(g) -> list[tuple[list, int]]:
    """A triangle cut along the zero line of a value g given at its three corners (linear over the triangle): the
    pieces in the parent's winding, each a polygon (3 or 4 refs) and its side (-1 where g < 0, +1 where g > 0, 0 for
    a triangle all on the line). A ref is ("v", k), corner k, or ("e", k, m, t), the point t of the way from corner k
    to corner m (g there 0). A corner with g == 0 is on the line: the cut runs through it."""
    g = [float(x) for x in g]
    s = [(x > 0) - (x < 0) for x in g]
    if not any(s):
        return [([("v", 0), ("v", 1), ("v", 2)], 0)]
    if all(x >= 0 for x in s) or all(x <= 0 for x in s):
        return [([("v", 0), ("v", 1), ("v", 2)], max(s) if max(s) > 0 else min(s))]

    def x(k, m):
        return ("e", k, m, g[k] / (g[k] - g[m]))
    if 0 in s:  # one corner on the line, the other two on either side: two triangles through it
        z = s.index(0)
        b, c = (z + 1) % 3, (z + 2) % 3
        return [([("v", z), ("v", b), x(b, c)], s[b]), ([("v", z), x(b, c), ("v", c)], s[c])]
    a = next(k for k in range(3) if s.count(s[k]) == 1)  # the corner alone on its side
    b, c = (a + 1) % 3, (a + 2) % 3
    return [([("v", a), x(a, b), x(a, c)], s[a]), ([x(a, b), ("v", b), ("v", c), x(a, c)], s[b])]


def replace_accessor(doc: dict, binary: bytearray, i: int, rows, component: int = 5126) -> None:
    """Accessor i rewritten with new rows (any count): a new tightly packed buffer view appended (float32, or uint32
    indices with component 5125), its count, and its min and max when it had them. The old view stays unused."""
    a = doc["accessors"][i]
    n = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[a["type"]]
    flat = [c for r in rows for c in (r if n > 1 else (r,))]
    if len(flat) % n:
        raise ValueError(f"rows of {n} expected")
    fmt = "f" if component == 5126 else "I"
    payload = struct.pack(f"<{len(flat)}{fmt}", *[float(c) if fmt == "f" else int(c) for c in flat])
    a["bufferView"] = _append_view(doc, binary, payload, 34963 if component == 5125 else 34962)
    a["byteOffset"] = 0
    a["componentType"] = component
    a["count"] = len(flat) // n
    a.pop("sparse", None)
    if "min" in a:
        a["min"] = [min(flat[j::n]) for j in range(n)]
        a["max"] = [max(flat[j::n]) for j in range(n)]
