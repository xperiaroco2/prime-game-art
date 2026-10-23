"""Pure maths of the pilot head on the shared alien body (art #196, step B1): standard library only, tested by
tools/tests/test_alien_char_geom.py; alien_char_build.py runs it inside Blender.

- `fit_scale`: the head's scale, its neck's narrowest half-width onto the body's neck ring (the 2D busts' head
  sits on the same slender neck as the body: matching the necks keeps the band morph near the identity and gives the
  line-up's head-to-shoulder ratio, `head_ratio` reports it).
- `zip_loops`: triangles joining two closed loops of different vertex counts, walked by angle round the axis.
- `shield`: the pale front's weight on the body (the u1 turnaround: a rounded shield from the throat to the crotch).
- `gltf_to_blender`, `blender_to_gltf`, `fit_point`, `fit_lively`: the lively head's data (glTF, Y up) under the fit.
- `sstep`: a smoothstep from a to b (either order).
"""
from __future__ import annotations

import math

# the pale front on the body, measured on u1's front view (part_0; sole row 967, 0.0019 m a pixel): the shield's
# half-width per height (z m, half-width m); 0 below the crotch and above the ring
SHIELD = [(0.80, 0.0), (0.83, 0.045), (0.88, 0.075), (0.98, 0.088), (1.10, 0.090), (1.22, 0.085), (1.30, 0.060),
          (1.33, 0.040), (1.40, 0.040)]
SHIELD_EDGE = 0.016  # the soft edge, m
FRONT_FACING = (-0.15, 0.35)  # the shield only where the normal faces the front: -n.y from 0 (side) to 1


def sstep(a: float, b: float, x: float) -> float:
    if a == b:
        return 1.0 if x >= b else 0.0
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def interp(table: list[tuple[float, float]], x: float) -> float:
    if x <= table[0][0]:
        return table[0][1]
    for (x0, y0), (x1, y1) in zip(table, table[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return table[-1][1]


def shield(x: float, z: float, ny: float, trunk: float, table=SHIELD, edge: float = SHIELD_EDGE) -> float:
    """The pale front's weight (0..1) of a body point: inside the shield's half-width at its height, facing the
    front (ny the normal's Y, the front is -Y), carried by the trunk (`trunk`: its trunk bones' weight)."""
    hw = interp(table, z)
    if hw <= 0.0:
        return 0.0
    inside = 1.0 - sstep(hw - edge * 0.5, hw + edge * 0.5, abs(x))
    return inside * sstep(FRONT_FACING[0], FRONT_FACING[1], -ny) * sstep(0.4, 0.8, trunk)


def angle(x: float, y: float, cx: float, cy: float) -> float:
    """The angle round the axis (cx, cy): 0 at the front (-Y), toward the left (+X), in [0, 2 pi)."""
    return math.atan2(x - cx, -(y - cy)) % (2.0 * math.pi)


def zip_loops(a: list[float], b: list[float]) -> list[tuple[str, int, str, int, str, int]]:
    """Triangles between two closed loops given as the angles of their vertices in loop order (both increasing
    round the axis). Each triangle is (loop, index) x 3 with loops 'a' and 'b'; the walk always advances the loop
    whose next vertex has the smaller angle, so every triangle spans a short arc and none folds over."""
    na, nb = len(a), len(b)
    if na < 3 or nb < 3:
        raise ValueError("a loop needs 3 vertices")
    # start both at the vertex nearest angle 0
    ia0 = min(range(na), key=lambda i: a[i])
    ib0 = min(range(nb), key=lambda i: b[i])

    def unwrap(seq, i0):
        out, prev, off = [], None, 0.0
        for k in range(len(seq) + 1):
            v = seq[(i0 + k) % len(seq)] + off
            if prev is not None and v < prev:
                off += 2.0 * math.pi
                v += 2.0 * math.pi
            out.append(v)
            prev = v
        return out

    ua, ub = unwrap(a, ia0), unwrap(b, ib0)
    tris = []
    i = j = 0
    while i < na or j < nb:
        adv_a = j >= nb or (i < na and ua[i + 1] <= ub[j + 1])
        if adv_a:
            tris.append(("a", (ia0 + i) % na, "a", (ia0 + i + 1) % na, "b", (ib0 + j) % nb))
            i += 1
        else:
            tris.append(("a", (ia0 + i) % na, "b", (ib0 + j + 1) % nb, "b", (ib0 + j) % nb))
            j += 1
    return tris


def fit_scale(neck_half_width: float, ring_half_width: float) -> float:
    if neck_half_width <= 0.0:
        raise ValueError("no neck")
    return ring_half_width / neck_half_width


def head_ratio(head_width: float, shoulder_width: float) -> float:
    return head_width / shoulder_width


def gltf_to_blender(p):
    return (p[0], -p[2], p[1])


def blender_to_gltf(p):
    return (p[0], p[2], -p[1])


def fit_point(p, s: float, src, dst):
    """Blender coordinates: p scaled by s about src, then src moved onto dst (no turn: both face -Y)."""
    return tuple(dst[k] + s * (p[k] - src[k]) for k in range(3))


def fit_lively(d: dict, s: float, src, dst) -> dict:
    """The lively head's lively.json under the fit (glTF coordinates in and out): every eye centre moved, every eye
    radius scaled; directions (rest, catch) and angles stay."""
    import copy
    out = copy.deepcopy(d)

    def move(p):
        q = fit_point(gltf_to_blender(p), s, src, dst)
        return [round(c, 6) for c in blender_to_gltf(q)]

    for e in out.get("eyes", {}).values():
        if "centre" in e:
            e["centre"] = move(e["centre"])
        if "radius" in e:
            e["radius"] = e["radius"] * s
        fs = e.get("front_sphere")
        if fs:
            fs["centre"] = move(fs["centre"])
            fs["r"] = fs["r"] * s
    if "eye_radius" in out:
        out["eye_radius"] = out["eye_radius"] * s
    out["fit"] = {"scale": s, "src_blender": list(src), "dst_blender": list(dst)}
    return out
