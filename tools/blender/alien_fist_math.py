"""The run fist as a morph (art #196, Hands H1j, the engineer's option C; pure Python, no bpy: alien_fist_shape.py is
the Blender side).

The loose grip (`anim_sets/alien_hands.toml` `[grips.loose]`) folds the tube fingers onto the palm, but bones alone
leave the "@" coil, holes and separate tips. The fist's shape closes them: in the loose grip's posed space each digit
is a chain of round cones fitted to its own tube (a centre and a radius per station: the root, each joint, the tip
dome's centre), the chain a plain union (a bent joint's outside stays the tube's, no knuckle bulge); the fingers are
smooth-unioned with each other (`k_mm`) and with the thumb (`k_thumb_mm`), so gaps and creases between them fill with
rounded webs while each digit keeps its own surface. Every finger vertex goes onto that surface (pushed out of it or,
when it lies within `pull_mm` outside, pulled onto it), faded by its finger weight into the palm; a vertex buried
deeper than `hide_mm` (the facing sides of two fingers) goes under the surface, so the outer skin is one sheet; a few
rounds of relaxing along the surface even out where vertices bunched. The posed moves are carried back to the rest
mesh by the inverse of each vertex's skinning: the `fist` shape key, exported as the glTF morph target "fist".

The clips key its weight with the grip (`weight_plan`): 1 where the clip's grip is the fist grip, 0 elsewhere, eased
like Blender's keys between grips; `key_weights` writes those channels into an exported GLB.
"""
from __future__ import annotations

import json
import math
import struct

Vec = tuple[float, float, float]


def _sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _mul(a: Vec, s: float) -> Vec:
    return (a[0] * s, a[1] * s, a[2] * s)


def _dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _len(a: Vec) -> float:
    return math.sqrt(_dot(a, a))


def round_cone(p: Vec, a: Vec, b: Vec, r1: float, r2: float) -> float:
    """The signed distance from p to the round cone from the sphere (a, r1) to the sphere (b, r2) (exact; |r1 - r2| <
    |b - a|; a degenerate segment is the larger sphere)."""
    ba = _sub(b, a)
    l2 = _dot(ba, ba)
    rr = r1 - r2
    if l2 <= rr * rr + 1e-18:
        return min(_len(_sub(p, a)) - r1, _len(_sub(p, b)) - r2)
    a2 = l2 - rr * rr
    il2 = 1.0 / l2
    pa = _sub(p, a)
    y = _dot(pa, ba)
    z = y - l2
    q = _sub(_mul(pa, l2), _mul(ba, y))
    x2 = _dot(q, q)
    y2 = y * y * l2
    z2 = z * z * l2
    k = math.copysign(1.0, rr) * rr * rr * x2
    if math.copysign(1.0, z) * a2 * z2 > k:
        return math.sqrt(x2 + z2) * il2 - r2
    if math.copysign(1.0, y) * a2 * y2 < k:
        return math.sqrt(x2 + y2) * il2 - r1
    return (math.sqrt(x2 * a2 * il2) + y * rr) * il2 - r1


def smin(a: float, b: float, k: float) -> float:
    """The polynomial smooth minimum (blend width k; k <= 0: the plain minimum)."""
    if k <= 0:
        return min(a, b)
    h = max(k - abs(a - b), 0.0) / k
    return min(a, b) - h * h * k * 0.25


class Fist:
    """The fist's surface: digits {name: [(centre, radius), ...] stations root to tip dome}, `thumb` the thumb's name;
    the fingers smooth-unioned in their given order with k, the thumb with k_thumb (metres)."""

    def __init__(self, digits: dict, thumb: str, k: float, k_thumb: float):
        self.chains = {n: [(st[i][0], st[i + 1][0], st[i][1], st[i + 1][1]) for i in range(len(st) - 1)]
                       for n, st in digits.items()}
        self.fingers = [n for n in digits if n != thumb]
        self.thumb = thumb if thumb in digits else None
        self.k, self.k_thumb = k, k_thumb

    def digit(self, name: str, p: Vec) -> float:
        return min(round_cone(p, a, b, r1, r2) for a, b, r1, r2 in self.chains[name])

    def sd(self, p: Vec) -> float:
        d = None
        for n in self.fingers:
            x = self.digit(n, p)
            d = x if d is None else smin(d, x, self.k)
        if self.thumb is not None:
            x = self.digit(self.thumb, p)
            d = x if d is None else smin(d, x, self.k_thumb)
        return d

    def grad(self, p: Vec, e: float = 1e-5) -> Vec:
        return tuple((self.sd(_add(p, d)) - self.sd(_sub(p, d))) / (2 * e)
                     for d in ((e, 0, 0), (0, e, 0), (0, 0, e)))

    def project(self, p: Vec, level: float = 0.0, steps: int = 6) -> Vec:
        """p moved along the field's gradient onto the iso-surface sd = level."""
        for _ in range(steps):
            d = self.sd(p) - level
            if abs(d) < 1e-6:
                break
            g = self.grad(p)
            n = _len(g)
            if n < 1e-9:
                break
            p = _sub(p, _mul(g, d / (n * n)))
        return p


def stations(points: list[Vec], axis_a: Vec, axis_b: Vec, ts: list[float], band: float,
             near_n: int = 24, reach: float = 0.03) -> list[tuple[Vec, float]]:
    """Per share t of the segment a -> b: the centre (the mean of the points near the plane through a + t(b - a),
    projected into it) and the radius (their mean distance from that centre). The points near the plane: those within
    band of it, or the near_n nearest (a sparse tip), of the points within reach of the axis."""
    ab = _sub(axis_b, axis_a)
    ln = _len(ab)
    u = _mul(ab, 1.0 / ln)
    rows = []
    for p in points:
        pa = _sub(p, axis_a)
        s = _dot(pa, u)
        if _len(_sub(pa, _mul(u, s))) <= reach:
            rows.append((s, p))
    out = []
    for t in ts:
        s0 = t * ln
        near = [p for s, p in rows if abs(s - s0) <= band]
        if len(near) < near_n:
            near = [p for _, p in sorted(rows, key=lambda r: abs(r[0] - s0))[:near_n]]
        if len(near) < 4:
            raise ValueError(f"only {len(near)} vertices near share {t} of the segment")
        c = _mul(tuple(sum(p[i] for p in near) for i in range(3)), 1.0 / len(near))
        c = _sub(c, _mul(u, _dot(_sub(c, axis_a), u) - s0))
        r = sum(_len(_sub(_sub(p, c), _mul(u, _dot(_sub(p, c), u)))) for p in near) / len(near)
        out.append((c, r))
    return out


def fist_moves(posed: dict, weight: dict, fist: Fist, nbr: dict, pull: float, hide: float, relax: int = 4,
               lam: float = 0.3, own: set | None = None) -> tuple[dict, dict]:
    """The posed moves {vertex: move} onto the fist's surface. posed {vertex: point}; weight {vertex: 0..1} (the finger
    weight's fade into the palm); own: the vertices of the fitted digit segments (only they are pulled in; any other
    vertex is only pushed out); nbr {vertex: neighbours}. Returns (moves, stats)."""
    own = set(posed) if own is None else own
    level, w, new = {}, {}, {}
    for i, p in posed.items():
        d = fist.sd(p)
        lv = -min(max(0.0, -d - hide) * 0.5, hide)  # buried deep: kept under the surface
        fade = 1.0 if d <= 0 else (max(0.0, 1.0 - d / pull) if i in own else 0.0)
        wi = weight.get(i, 0.0) * fade
        if wi <= 0.0 or (d > 0 and d < 1e-6):
            continue
        level[i], w[i] = lv, wi
        q = fist.project(p, lv)
        new[i] = _add(p, _mul(_sub(q, p), wi))
    # relax along the surface where the projection moved vertices (the merged webs), the fully weighted ones only
    free = [i for i in new if w[i] >= 0.999 and _len(_sub(new[i], posed[i])) > 3e-4 and nbr.get(i)]
    for _ in range(relax):
        cur = dict(new)
        for i in free:
            ns = nbr[i]
            m = _mul(tuple(sum(cur.get(j, posed[j])[k] for j in ns) for k in range(3)), 1.0 / len(ns))
            new[i] = fist.project(_add(cur[i], _mul(_sub(m, cur[i]), lam)), level[i])
    moves = {i: _sub(q, posed[i]) for i, q in new.items() if _len(_sub(q, posed[i])) > 1e-6}
    vis = [i for i in new if level[i] == 0.0 and w[i] >= 0.999]
    stats = {"moved": len(moves), "hidden": sum(1 for i in level if level[i] < 0),
             "max_move_mm": round(max((_len(m) for m in moves.values()), default=0.0) * 1000, 2),
             "surface_err_mm": round(max((abs(fist.sd(new[i])) for i in vis), default=0.0) * 1000, 3),
             "lump_mm": round(lump(moves, nbr) * 1000, 3)}
    return moves, stats


def lump(moves: dict, nbr: dict) -> float:
    """The largest umbrella (a vertex's move against its neighbours' mean move): a lump or a dent in the move field."""
    worst = 0.0
    for i, m in moves.items():
        ns = nbr.get(i) or ()
        if not ns:
            continue
        z = (0.0, 0.0, 0.0)
        mean = _mul(tuple(sum(moves.get(j, z)[k] for j in ns) for k in range(3)), 1.0 / len(ns))
        worst = max(worst, _len(_sub(m, mean)))
    return worst


def smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def weight_plan(plan: dict, fist_grip: str, lead: float = 1.0) -> list[tuple[float, float]]:
    """A clip's fist weight keys [(share, weight)] from its grip plan ({side: [(share, grip), ...]}): 1 where the grip
    is the fist grip, else 0. Both hands share the one morph, so their keys must agree. lead (0 < lead <= 1, H1m): the
    morph runs ahead of the grip, reaching 1 at that share of each ramp into the fist grip and leaving 1 only at
    (1 - lead) of each ramp out of it, so the half-curled fingers already carry the fist's shape (no mid-blend ring)."""
    if not 0.0 < lead <= 1.0:
        raise ValueError(f"fist lead {lead} not in (0, 1]")
    sides = list(plan.values())
    rows = [[(s, 1.0 if g == fist_grip else 0.0) for s, g in r] for r in sides]
    if any(r != rows[0] for r in rows[1:]):
        raise ValueError(f"the hands' fist keys differ: {rows}")
    keys = rows[0]
    if lead >= 1.0:
        return keys
    out = [keys[0]]
    for (s0, w0), (s1, w1) in zip(keys, keys[1:]):
        if w1 > w0:
            out.append((round(s0 + lead * (s1 - s0), 6), w1))
        elif w1 < w0:
            out.append((round(s1 - lead * (s1 - s0), 6), w0))
        out.append((s1, w1))
    return out


def weight_at(keys: list[tuple[float, float]], share: float) -> float:
    """The weight at a share of the clip: held before the first and after the last key, eased between keys as
    Blender's auto-clamped Bézier keys between two grips are (a smoothstep)."""
    if share <= keys[0][0]:
        return keys[0][1]
    for (s0, w0), (s1, w1) in zip(keys, keys[1:]):
        if share <= s1:
            return w0 + (w1 - w0) * smoothstep((share - s0) / (s1 - s0) if s1 > s0 else 1.0)
    return keys[-1][1]


def _glb(path) -> tuple[dict, bytearray]:
    with open(path, "rb") as fh:
        data = fh.read()
    jlen = struct.unpack_from("<I", data, 12)[0]
    gltf = json.loads(data[20:20 + jlen].decode("utf-8"))
    blen = struct.unpack_from("<I", data, 20 + jlen)[0]
    return gltf, bytearray(data[28 + jlen:28 + jlen + blen])


def _write_glb(path, gltf: dict, bin_: bytearray) -> None:
    while len(bin_) % 4:
        bin_.append(0)
    gltf["buffers"][0]["byteLength"] = len(bin_)
    js = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    js += b" " * (-len(js) % 4)
    out = struct.pack("<III", 0x46546C67, 2, 28 + len(js) + len(bin_))
    out += struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(bin_), 0x004E4942) + bytes(bin_)
    with open(path, "wb") as fh:
        fh.write(out)


def key_weights(path, morph: str, plans: dict, default: float = 0.0) -> dict:
    """Into the GLB at path: on every mesh whose morph targets are exactly [morph] (glTF extras.targetNames), a
    `weights` channel per animation: the weight per sample time of that animation's densest input (its frames),
    from plans {animation name: [(share, weight)]}, else `default` held. Fails if any other mesh has targets or no
    mesh has the morph. Returns {animation: [min, max]}."""
    gltf, bin_ = _glb(path)
    nodes = []
    for ni, node in enumerate(gltf.get("nodes", [])):
        if "mesh" not in node:
            continue
        me = gltf["meshes"][node["mesh"]]
        names = (me.get("extras") or {}).get("targetNames")
        has = any(pr.get("targets") for pr in me["primitives"])
        if not has:
            continue
        if names != [morph]:
            raise ValueError(f"{path}: mesh {me.get('name')} has morph targets {names}, only [{morph!r}] is allowed")
        me["weights"] = [0.0]
        nodes.append(ni)
    if not nodes:
        raise ValueError(f"{path}: no mesh carries the morph {morph!r}")
    out = {}
    for an in gltf.get("animations", []):
        if any(c["target"].get("path") == "weights" for c in an["channels"]):
            raise ValueError(f"{path}: {an.get('name')} already has a weights channel")
        inp = max((s["input"] for s in an["samplers"]), key=lambda a: gltf["accessors"][a]["count"])
        acc = gltf["accessors"][inp]
        bv = gltf["bufferViews"][acc["bufferView"]]
        o = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
        times = struct.unpack_from(f"<{acc['count']}f", bin_, o)
        t0, t1 = times[0], times[-1]
        keys = plans.get(an.get("name"), [(0.0, default)])
        ws = [weight_at(keys, (t - t0) / (t1 - t0) if t1 > t0 else 0.0) for t in times]
        while len(bin_) % 4:
            bin_.append(0)
        off = len(bin_)
        bin_ += struct.pack(f"<{len(ws)}f", *ws)
        gltf["bufferViews"].append({"buffer": 0, "byteOffset": off, "byteLength": 4 * len(ws)})
        gltf["accessors"].append({"bufferView": len(gltf["bufferViews"]) - 1, "componentType": 5126,
                                  "count": len(ws), "type": "SCALAR", "min": [min(ws)], "max": [max(ws)]})
        an["samplers"].append({"input": inp, "output": len(gltf["accessors"]) - 1, "interpolation": "LINEAR"})
        for ni in nodes:
            an["channels"].append({"sampler": len(an["samplers"]) - 1, "target": {"node": ni, "path": "weights"}})
        out[an.get("name")] = [round(min(ws), 4), round(max(ws), 4)]
    _write_glb(path, gltf, bin_)
    return out
