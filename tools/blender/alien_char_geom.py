"""Pure maths of the pilot head on the shared alien body (art #196, step B1): standard library only, tested by
tools/tests/test_alien_char_geom.py; alien_char_build.py runs it inside Blender.

- `fit_scale`: the head's scale, its neck's narrowest half-width onto the body's neck ring (the 2D busts' head
  sits on the same slender neck as the body: matching the necks keeps the band morph near the identity and gives the
  line-up's head-to-shoulder ratio, `head_ratio` reports it).
- `zip_loops`: triangles joining two closed loops of different vertex counts, walked by angle round the axis.
- `shield`: the u1 shield (`--shield`, off by default); `throat_fade`: the default pale front (B3, a tongue from the
  throat to the sternum, per texel).
- `walk_loop`, `monotone_angles`, `bridge_outward`: the seam's bridge in walk order, its angles, its facing.
- `gltf_to_blender`, `blender_to_gltf`, `fit_point`, `fit_lively`: the lively head's data (glTF, Y up) under the fit.
- `sstep`: a smoothstep from a to b (either order).
- `leg_fit`, `leg_fit_scale` (T2): the clips' hip keys fitted to a body's own leg length (`--leg-fit`), the scale a
  build recorded in its char.json.
"""
from __future__ import annotations

import math

# the pale front on the body, measured on u1's front view (part_0; sole row 967, 0.0019 m a pixel): the shield's
# half-width per height (z m, half-width m); 0 below the crotch and above the ring
SHIELD = [(0.80, 0.0), (0.83, 0.045), (0.88, 0.075), (0.98, 0.088), (1.10, 0.090), (1.22, 0.085), (1.30, 0.060),
          (1.33, 0.040), (1.40, 0.040)]
SHIELD_EDGE = 0.016  # the soft edge, m
FRONT_FACING = (-0.15, 0.35)  # the shield only where the normal faces the front: -n.y from 0 (side) to 1


# T2 (art #196): the alien rig's leg bones under slice_math's names (its leg length: thigh, shin, ankle height)
LEG_NAMES = {f"{side}{bone}": f"{bone}.{s}" for side, s in (("Left", "L"), ("Right", "R"))
             for bone in ("UpperLeg", "LowerLeg", "Foot")}


def leg_fit(own: dict, donor: dict) -> dict:
    """The leg fit of a body whose legs differ from the rig its clips were made on (T2: the axolotl on M1f's body,
    the clips S4b's): own and donor are the rigs' rest heads (bone name: (x, y, z), z up, the floor at 0). Returns
    leg_m [donor, own] and scale (own / donor), the factor for the clips' Root and Hips location keys
    (slice_math.scales_with_legs), so the hips' bob and travel are in proportion to the legs that carry them."""
    import slice_math
    legs = [slice_math.leg_length({LEG_NAMES[k]: v for k, v in rig.items() if k in LEG_NAMES}) for rig in (donor, own)]
    if legs[0] <= 0:
        raise ValueError(f"the donor's leg length is {legs[0]} m")
    return {"leg_m": [round(legs[0], 4), round(legs[1], 4)], "scale": round(legs[1] / legs[0], 6)}


def leg_fit_scale(char: dict) -> float:
    """The leg scale a character build applied to its clips (char.json "leg_fit"; 1.0 for a build without it), which
    alien_loco.py applies to the loops it appends from other files (step 2's, P1's: made on the S4b rig)."""
    return float((char.get("leg_fit") or {}).get("scale", 1.0))


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


# B3 (art #196): the 2D's pale front is a soft tongue from the throat down to the sternum, not a panel: its half-width
# the head's own throat width at the cut, widening by THROAT_WIDEN per metre down; the sides feathered over
# THROAT_FEATHER of the half-width each way (no hard edge), the bottom faded out over THROAT_FADE (dz m below the
# ring), the front picked by the angle round the neck axis (THROAT_FRONT on cos(phi)), not by the normal's direction
THROAT_WIDEN = 0.3
THROAT_FEATHER = (0.7, 1.25)
THROAT_FADE = (0.03, 0.22)
THROAT_FRONT = (0.15, 0.6)


def throat_fade(x: float, dz: float, cos_phi: float, top_hw: float) -> float:
    """The pale front's weight (0..1) of a body point dz m below the neck ring, x m from the front centre line,
    cos_phi the cosine of its angle round the neck axis (1 the front, -1 the back), under the throat's half-width
    top_hw at the cut. Continuous everywhere: every factor is a smoothstep."""
    if top_hw <= 0.0:
        return 0.0
    hw = top_hw + THROAT_WIDEN * max(dz, 0.0)
    side = 1.0 - sstep(THROAT_FEATHER[0] * hw, THROAT_FEATHER[1] * hw, abs(x))
    down = sstep(-0.004, 0.004, dz) * (1.0 - sstep(THROAT_FADE[0], THROAT_FADE[1], dz))
    return side * down * sstep(THROAT_FRONT[0], THROAT_FRONT[1], cos_phi)


# B2: the neck's flare into the shoulders (the 2D busts' trapezius): a concave fillet surface round the neck axis,
# r_ring + side(phi) * extra * (dz / depth)^2, that the body's skin is pushed out to (never in), only on the trunk's
# skin, untouched at the ring (FLARE_TOP) and faded out below the shoulders' top (FLARE_FADE times depth)
FLARE_TOP = 0.012
FLARE_FADE = (0.9, 1.3)
FLARE_SIDE = (0.35, 0.45)  # the fillet's share at the front and the back (the sides 1)
FLARE_SOFT = 0.012  # the smooth max's width, m


def flare_side(phi: float) -> float:
    """The fillet's share at angle phi round the neck (0 the front, pi the back, pi/2 the sides): 1 at the sides."""
    front, back = FLARE_SIDE
    c, s = math.cos(phi), math.sin(phi)
    b = (front + back) / 2 + (front - back) / 2 * c
    return b + (1.0 - b) * s * s


def smax(a: float, b: float, k: float) -> float:
    h = max(k - abs(a - b), 0.0) / k
    return max(a, b) + h * h * k * 0.25


def flare_radius(r: float, r_ring: float, dz: float, phi: float, depth: float, extra: float, arm: float) -> float:
    """A body vertex's new distance from the neck axis: r pushed out to the fillet at its depth dz below the ring
    (depth: the ring to the shoulders' top; extra: the fillet's growth there at the sides), weighted off near the
    ring, below the shoulders and on the arms' skin (`arm` their weight)."""
    if dz <= 0.0 or depth <= 0.0:
        return r
    target = r_ring + flare_side(phi) * extra * (dz / depth) ** 2
    w = sstep(0.0, FLARE_TOP, dz) * (1.0 - sstep(FLARE_FADE[0] * depth, FLARE_FADE[1] * depth, dz)) * (1.0 - min(arm, 1.0))
    return r + w * (smax(r, target, FLARE_SOFT) - r)


def bridge_outward(normal, centre, axis) -> bool:
    """Whether a seam triangle's normal points away from the neck axis (axis: its (x, y) centre): the bridge's
    triangles are drawn single-sided in Godot, an inward one is a hole (r2's dark ring)."""
    return normal[0] * (centre[0] - axis[0]) + normal[1] * (centre[1] - axis[1]) > 0.0


def walk_loop(edges: list[tuple[int, int]]) -> list[int]:
    """The vertices of one closed loop in walk order from its edges (any order, either direction); ValueError when
    the edges are not one simple closed loop (a branch, an open end, two loops)."""
    nb: dict[int, list[int]] = {}
    for i, j in edges:
        nb.setdefault(i, []).append(j)
        nb.setdefault(j, []).append(i)
    if not nb or any(len(v) != 2 for v in nb.values()):
        raise ValueError("not a simple loop: a vertex without exactly two loop edges")
    start = min(nb)
    order, prev, cur = [start], None, start
    while True:
        nxt = nb[cur][0] if nb[cur][0] != prev else nb[cur][1]
        if nxt == start:
            break
        order.append(nxt)
        prev, cur = cur, nxt
    if len(order) != len(nb):
        raise ValueError("not one loop: more than one ring of edges")
    return order


def monotone_angles(angles: list[float]) -> list[float]:
    """A loop's angles round the axis in walk order (the walk going round in the increasing sense) made
    non-decreasing: each step is unwrapped as the shorter turn, so a fold back across angle 0 (B4 review:
    [..., 6.2, 0.05, 6.25, 0.3, ...]) and a step forward across it both stay one turn; where the cut row folds back
    on itself (r3's first chameleon build: two cut vertices out of angle order, so zipping by sorted angle left open
    and three-face edges) a vertex takes its predecessor's angle. The result is in [0, 2 pi), starting at the first
    vertex's angle, the last vertices held just short of one full turn, for zip_loops."""
    if not angles:
        return []
    tau = 2.0 * math.pi
    unwrapped = [angles[0]]
    for prev, a in zip(angles, angles[1:]):
        unwrapped.append(unwrapped[-1] + ((a - prev + math.pi) % tau) - math.pi)
    out: list[float] = []
    for v in unwrapped:
        out.append(max(v, out[-1]) if out else v)
    end = out[0] + tau
    return [(v if v < end else end - 1e-9) % tau for v in out]


def gill_decimate_ratio(tris: int, gill_tris: int, keep: float) -> float:
    """M1 (art #196): the whole mesh's collapse ratio that keeps `keep` of the gills' triangles when only the gills
    may collapse (the decimate modifier's ratio counts every face)."""
    if not 0.0 < keep <= 1.0 or tris <= 0 or not 0 <= gill_tris <= tris:
        raise ValueError("keep in (0, 1], 0 <= gill_tris <= tris")
    return (tris - gill_tris * (1.0 - keep)) / tris
