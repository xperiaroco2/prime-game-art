"""The text-to-motion locomotion candidates on the alien, their pure measures (art #196, option A step 2): the travel
direction against the facing, the hips' yaw wobble, the feet against the floor, the hands against the torso, the
crouch depth, the faults per slot and a ranking by the numbers alone. No bpy: tools/blender/alien_ttm.py bakes the
clips onto the contract skeleton (retarget_maps/smpl_contract.toml) and calls these on alien_stride_math's clip form;
tools/tests/test_alien_ttm_math.py runs them with the system Python.

Directions are yaws in the floor plane against the character's front (-Y; its left +X): 0 straight ahead, +90 to its
left, -90 to its right, 180 straight back.
"""

from __future__ import annotations

import math

import alien_stride_math as S
import anim_edit_math as M

FRONT = (0.0, -1.0, 0.0)
HAND_POINTS = ("Hand", "MiddleProximal", "MiddleDistal")  # the wrist, the knuckles, the last finger joint
TORSO_BONES = ("Spine", "Chest", "UpperChest")  # the vertices weighted most to these give the torso's section
TORSO_REF = "Chest"  # the hands are read in this bone's rest frame (the torso as if it stood at rest)
# per slot: the travel direction asked (degrees) and the game speed it plays at (m/s; prime-game's base mode)
SLOTS = {"jog": (0.0, 4.5), "strafe": (90.0, 4.5), "strafe_right": (-90.0, 4.5), "backward": (180.0, 4.5),
         "crouch": (0.0, 2.8)}
# the fault bounds: past these a number is named as a fault (and each is one unit of the ranking's score)
BOUND = {"direction_deg": 15.0, "yaw_wobble_deg": 20.0, "seam_cut_deg": 15.0, "foot_slide_mm": 30.0,
         "under_floor_mm": 15.0, "hover_mm": 25.0, "floor_drift_mm": 30.0, "hand_cm": 0.0, "rate_ratio": 1.6, "crouch_hips": 0.85}


def wrap(deg: float) -> float:
    """An angle in (-180, 180]."""
    d = math.fmod(deg + 180.0, 360.0)
    return d + 180.0 if d <= 0.0 else d - 180.0


def yaw(v) -> float:
    """A floor-plane direction's yaw against the front -Y (degrees, + toward the left +X)."""
    return math.degrees(math.atan2(v[0], -v[1]))


def unwrap(angles: list) -> list:
    out = []
    for a in angles:
        out.append(a if not out else out[-1] + wrap(a - out[-1]))
    return out


def _apply(m, v):
    return tuple(sum(m[i][k] * v[k] for k in range(3)) for i in range(3))


def facing(skel: dict, clip: dict, bone: str = "Hips") -> list:
    """The bone's front (its rest front -Y turned by its pose against its rest) as a yaw per frame, unwrapped."""
    skel = S.prepare(skel)
    rest_inv = S.rigid_inv(skel["rest"][bone])
    out = []
    for f in range(S.frames(clip) + 1):
        out.append(yaw(_apply(M.mat_mul(S.fk(skel, clip, f)[bone], rest_inv), FRONT)))
    return unwrap(out)


def direction(skel: dict, clip: dict, measure: dict) -> dict:
    """The body's travel over the ground (the hips' travel less the planted feet's ground velocity, as measure's v0)
    against the hips' mean facing: travel_deg (+ to the left), facing_deg (the mean facing against -Y) and
    yaw_wobble_deg (the facing's spread over the loop, largest less smallest)."""
    face = facing(skel, clip)
    mean = sum(face) / len(face)
    hv, g = measure["hips_m_s"], measure["ground_m_s"]
    rel = (hv[0] - g[0], hv[1] - g[1])
    moving = math.hypot(*rel) > 1e-3
    return {"travel_deg": round(wrap(yaw(rel) - mean), 2) if moving else None,
            "facing_deg": round(wrap(mean), 2), "yaw_wobble_deg": round(max(face) - min(face), 2)}


def ellipse_inside_cm(x: float, y: float, a: float, b: float) -> float:
    """How far (cm) a point lies inside an ellipse with half-axes a (x) and b (y) about the origin, along its own ray
    from the centre: the ellipse's radius that way less the point's distance (negative: outside, the clearance)."""
    rho = math.hypot(x, y)
    if rho < 1e-9:
        return min(a, b) * 100.0
    c, s = x / rho, y / rho
    r = a * b / math.sqrt((b * c) ** 2 + (a * s) ** 2)
    return (r - rho) * 100.0


def _pct(values: list, p: float) -> float:
    v = sorted(values)
    return v[min(len(v) - 1, max(0, round(p * (len(v) - 1))))]


def torso_shape(points: list) -> dict:
    """The torso's section from its vertices (armature rest space): centre (cx, cy), half-axes a (x) and b (y) as the
    90th percentile of the vertices' distances from it, and the height band (z0, z1: the 5th and 95th percentiles)."""
    xs, ys, zs = ([p[i] for p in points] for i in range(3))
    cx, cy = _pct(xs, 0.5), _pct(ys, 0.5)
    return {"cx": cx, "cy": cy, "a": _pct([abs(x - cx) for x in xs], 0.9), "b": _pct([abs(y - cy) for y in ys], 0.9),
            "z0": _pct(zs, 0.05), "z1": _pct(zs, 0.95)}


def hands_into_torso(skel: dict, clip: dict, shape: dict, ref: str = TORSO_REF) -> dict:
    """Per side the deepest a hand point goes into the torso's section (cm; negative: its closest clearance) over the
    loop, the points read in the ref bone's rest frame and counted only within the torso's height band."""
    skel = S.prepare(skel)
    rest = skel["rest"][ref]
    out = {}
    for side in S.SIDES:
        worst = None
        for f in range(S.frames(clip) + 1):
            P = S.fk(skel, clip, f)
            back = M.mat_mul(rest, S.rigid_inv(P[ref]))
            for part in HAND_POINTS:
                x, y, z = _apply(back, S.pos(P[f"{side}{part}"]))
                x, y, z = x + back[0][3], y + back[1][3], z + back[2][3]
                if not shape["z0"] <= z <= shape["z1"]:
                    continue
                d = ellipse_inside_cm(x - shape["cx"], y - shape["cy"], shape["a"], shape["b"])
                worst = d if worst is None else max(worst, d)
        out[side] = None if worst is None else round(worst, 2)
    return out


def sole_heights(skel: dict, clip: dict, soles: dict) -> list:
    """The lowest sole point's height (m) per frame; soles {bone: [points in the bone's rest frame]}."""
    skel = S.prepare(skel)
    out = []
    for f in range(S.frames(clip) + 1):
        P = S.fk(skel, clip, f)
        out.append(min(_apply(P[b], p)[2] + P[b][2][3] for b, pts in soles.items() for p in pts))
    return out


PLANTED_PCT = 0.1  # the planted level: this percentile of each frame's lowest sole point (a run is airborne a lot)


def floor(heights: list) -> dict:
    """floor_min_mm: the lowest sole point over the loop (negative: under the floor); floor_planted_mm: the planted
    level (PLANTED_PCT of each frame's lowest sole point: 0 when the planted feet stand on the floor, above it when
    they hover); floor_median_mm: the median, for a run a little above the planted level (its flight)."""
    return {"floor_min_mm": round(min(heights) * 1000.0, 1),
            "floor_planted_mm": round(_pct(heights, PLANTED_PCT) * 1000.0, 1),
            "floor_median_mm": round(_pct(heights, 0.5) * 1000.0, 1)}


def floor_fit(heights: list) -> float:
    """The height (m) to take off the whole clip so its planted level (floor's floor_planted_mm) is the floor: the
    retarget scales the source by the hip height, and the alien's ankles sit lower over its soles than the scaled
    source's, so its feet would hover by the difference."""
    return _pct(heights, PLANTED_PCT)


def floor_drift(heights: list, fps: float, window_s: float = 1.0) -> float:
    """How far (m) the planted level wanders over a long clip: the planted level of each window_s window, the
    largest less the smallest (the source's own floor rising or sinking, or a hop that never lands)."""
    n = max(2, round(window_s * fps))
    levels = [_pct(heights[i:i + n], PLANTED_PCT) for i in range(0, len(heights) - n + 1, n)]
    return max(levels) - min(levels) if levels else 0.0


def shift_hips(skel: dict, clip: dict, dz: float) -> dict:
    """The clip with the whole body moved dz metres up (the Hips' basis location; the Hips hang under a Root at rest)."""
    skel = S.prepare(skel)
    r = skel["rest"]["Hips"]
    d = tuple(r[2][k] * dz for k in range(3))  # the rest rotation's transpose applied to (0, 0, dz)
    out = S.copy_clip(clip)
    out["loc"]["Hips"] = [(x + d[0], y + d[1], z + d[2]) for x, y, z in clip["loc"]["Hips"]]
    return out


def loop_bounds(c0: float | None, default: tuple) -> tuple:
    """The loop length bounds (s) for a gait of c0 steps/s: one cycle of two steps, give or take a quarter."""
    if not c0:
        return default
    period = 2.0 / c0
    return round(period * 0.75, 3), round(period * 1.3, 3)


def hips_height(skel: dict, clip: dict) -> float:
    """The hips' mean height over the loop against their rest height."""
    skel = S.prepare(skel)
    zs = [p[2] for p in S.tracks(skel, clip, ["Hips"])["Hips"]]
    return round(sum(zs) / len(zs) / skel["rest"]["Hips"][2][3], 3)


def faults(c: dict, slot: str) -> tuple[list, float]:
    """The named faults of one candidate's numbers in a slot and its score (the sum of each number over its bound;
    lower is better; a fault adds at least 1)."""
    want, speed = SLOTS[slot]
    out, score = [], 0.0

    def add(value, bound, text):
        nonlocal score
        r = value / bound
        score += r
        if r > 1.0:
            out.append(text)

    if c.get("c0") is None or c.get("travel_deg") is None:
        return ["no steps or no travel found"], 99.0
    err = abs(wrap(c["travel_deg"] - want))
    r = err / BOUND["direction_deg"]  # the slot's whole point: past its bound it counts squared
    add(err * max(1.0, r), BOUND["direction_deg"], f"travels {err:.0f} deg off the slot's {want:.0f}")
    add(c["yaw_wobble_deg"], BOUND["yaw_wobble_deg"], f"hips yaw wobble {c['yaw_wobble_deg']:.0f} deg")
    add(c["seam_cut_deg"], BOUND["seam_cut_deg"], f"loop cut seam {c['seam_cut_deg']:.0f} deg spread")
    slide = max(c["foot_slide_mm"].values())
    add(slide, BOUND["foot_slide_mm"], f"foot slide {slide:.0f} mm")
    add(max(0.0, -c["floor_min_mm"]), BOUND["under_floor_mm"], f"a foot {-c['floor_min_mm']:.0f} mm under the floor")
    add(max(0.0, c["floor_planted_mm"]), BOUND["hover_mm"], f"planted feet hover {c['floor_planted_mm']:.0f} mm")
    add(c.get("floor_drift_mm", 0.0), BOUND["floor_drift_mm"],
        f"the source's floor drifts {c.get('floor_drift_mm', 0.0):.0f} mm over the clip")
    if c["steps_in_loop"] != 2:
        out.append(f"the loop holds {c['steps_in_loop']} steps, not 2")
        score += 1.0
    hand = max(v for v in c["hands_cm"].values() if v is not None) if any(
        v is not None for v in c["hands_cm"].values()) else -99.0
    if hand > BOUND["hand_cm"]:
        out.append(f"a hand {hand:.1f} cm into the torso")
        score += 1.0 + hand
    if not c["v0"]:
        return out + ["no travel"], score + 99.0
    rate = speed / c["v0"]
    r = abs(math.log(rate)) / math.log(BOUND["rate_ratio"])
    score += r
    if r > 1.0:
        out.append(f"rate {rate:.2f} at {speed} m/s")
    if slot == "crouch" and c["hips_height"] > BOUND["crouch_hips"]:
        out.append(f"hips at {c['hips_height']:.2f} of rest: not a crouch")
        score += 1.0 + (c["hips_height"] - BOUND["crouch_hips"]) * 10.0
    return out, round(score, 3)


def rank(cands: dict) -> dict:
    """{slot: [(name, score, faults), ...] best first} from {name: numbers with "slot"}."""
    out = {}
    for name, c in cands.items():
        f, s = faults(c, c["slot"])
        out.setdefault(c["slot"], []).append((name, s, f))
    return {k: sorted(v, key=lambda x: x[1]) for k, v in out.items()}
