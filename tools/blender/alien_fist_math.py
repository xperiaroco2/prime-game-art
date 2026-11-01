"""The run fist as a morph (art #196, Hands H1j, the engineer's option C; pure Python, no bpy: alien_fist_shape.py is
the Blender side).

The run grip (`anim_sets/alien_hands.toml` `[grips.runfist]`) curls the fist by its bones; the morph's shape
is the contact route's (alien_fist_envelope.contact, driven by alien_fist_shape.py). Here: `stations`, the round-cone
stations fitted to each digit's own tube, and the morph's weights.

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
