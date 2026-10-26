"""The alien locomotion's clip tool, its pure maths (art #196, option A step 1): measure, stride, cycle, arm swing and
mirror on the contract skeleton's own clips (the names Hips, LeftUpperLeg, LeftFoot, LeftToes, ...), no bpy, so the
unit tests run it with the system Python (tools/tests/test_alien_stride_math.py). tools/blender/alien_stride.py reads
the clips out of Blender into the plain form below, runs these edits and writes the result back as a new action.

The forms (JSON-friendly):
- a skeleton: {"rest": {bone: 4x4 rest matrix in armature space (Blender's bone.matrix_local)}, "parent": {bone:
  parent or None}}; `prepare` adds the bone order (parents first) and each bone's rest relative to its parent;
- a clip: {"name", "fps", "loc": {bone: [(x, y, z) per frame]}, "rot": {bone: [(w, x, y, z) per frame]}}, the pose
  bones' basis (Blender's location and rotation_quaternion, scale 1) on frames 0..T. A loop is closed: its frame T is
  its frame 0, so T is its number of frame intervals and T / fps its cycle.
The armature space is the world here (the alien's armature object has no transform): front -Y, left +X, up +Z, the
floor at z = 0. Reused from anim_edit_math: the contact masks and windows, the ground velocity, the cadence, the
retime count and its Catmull-Rom sampling, `stride_scale`, `scale_offset`, `plant`, the loop closing, the mirror
correction and pose; from alien_clip_edit: `two_bone` (the leg solved again with the clip's own knee plane).
"""

from __future__ import annotations

import math

import anim_edit_math as M
from alien_clip_edit import two_bone

CONTACT_M = M.CONTACT_WINDOW_M  # a foot point is on the ground while within 2 cm of its lowest height in the clip
SIDES = ("Left", "Right")
LEG = ("UpperLeg", "LowerLeg", "Foot")
ARM = ("UpperArm", "LowerArm", "Hand")  # the chain `arm_swing` calms, per side
VELOCITY_TOL = (0.35, 0.35)  # a contact moves with the ground within max(0.35 m/s, 35 % of its speed)
MERGE_GAP = 2  # frames: a shorter break between two contacts of one foot is no step
SLIDE_BOUND_MM = 5.0  # `stride`: a planted foot (pivot_slide_mm) may slide this far over one contact
REFLECT_X = [[-1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
# the game's speeds (m/s) and the clip each plays (a-plan.md), with the footstep beat where the game has one (s/step)
GAME = (("walk", 4.5, "Jog_Fwd_Loop", 0.45), ("sprint", 7.0, "Sprint_Fwd_Loop", 0.32),
        ("crouch", 2.0, "Crouch_Fwd_Loop", None), ("crouch run", 2.8, "Crouch_Fwd_Loop", None),
        ("sneak", 2.0, "Jog_Fwd_Loop", None))


# ------------------------------------------------------------------------------------------------ the names
def mirror_name(name: str) -> str:
    """The contract's side rule: Left<X> <-> Right<X>; a centre bone (Hips, Spine, Head, Crest1) maps to itself."""
    if name.startswith("Left"):
        return "Right" + name[4:]
    if name.startswith("Right"):
        return "Left" + name[5:]
    return name


def mirror_pairs(names) -> dict:
    """Each bone's partner; a side bone without its partner is an error."""
    names = set(names)
    out = {}
    for n in names:
        m = mirror_name(n)
        if m not in names:
            raise ValueError(f"{n} has no mirror partner {m}")
        out[n] = m
    return out


def mirror_clip_name(name: str) -> str:
    """A clip's name with Left and Right swapped (Strafe_Left_Loop -> Strafe_Right_Loop)."""
    return name.replace("Left", "\0").replace("Right", "Left").replace("\0", "Right")


# ----------------------------------------------------------------------------------------- matrices and FK
def m4(loc, q):
    """T(loc) R(q): a pose bone's basis matrix (scale 1)."""
    w, x, y, z = M.q_norm(q)
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y), loc[0]],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x), loc[1]],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y), loc[2]],
            [0.0, 0.0, 0.0, 1.0]]


def rigid_inv(m):
    r = [[m[j][i] for j in range(3)] for i in range(3)]
    t = [-sum(r[i][k] * m[k][3] for k in range(3)) for i in range(3)]
    return [r[0] + [t[0]], r[1] + [t[1]], r[2] + [t[2]], [0.0, 0.0, 0.0, 1.0]]


def mat_q(m):
    """The rotation part of a 4x4 (or 3x3) matrix as a unit quaternion (Shepherd's method)."""
    tr = m[0][0] + m[1][1] + m[2][2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        q = (0.25 * s, (m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s, (m[1][0] - m[0][1]) / s)
    elif m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2
        q = ((m[2][1] - m[1][2]) / s, 0.25 * s, (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s)
    elif m[1][1] > m[2][2]:
        s = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2
        q = ((m[0][2] - m[2][0]) / s, (m[0][1] + m[1][0]) / s, 0.25 * s, (m[1][2] + m[2][1]) / s)
    else:
        s = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2
        q = ((m[1][0] - m[0][1]) / s, (m[0][2] + m[2][0]) / s, (m[1][2] + m[2][1]) / s, 0.25 * s)
    return M.q_norm(q)


def pos(m):
    return (m[0][3], m[1][3], m[2][3])


def prepare(skel: dict) -> dict:
    """The skeleton with "order" (parents first) and "rel" (each bone's rest relative to its parent's)."""
    if "order" in skel:
        return skel
    parent, rest = skel["parent"], skel["rest"]
    order, seen = [], set()

    def visit(b):
        if b in seen:
            return
        if parent[b] is not None:
            visit(parent[b])
        seen.add(b)
        order.append(b)
    for b in sorted(parent):
        visit(b)
    rel = {b: rest[b] if parent[b] is None else M.mat_mul(rigid_inv(rest[parent[b]]), rest[b]) for b in order}
    return {**skel, "order": order, "rel": rel}


def frames(clip: dict) -> int:
    """The clip's number of frame intervals T (its frames are 0..T)."""
    return len(next(iter(clip["rot"].values()))) - 1


def fk(skel: dict, clip: dict, f: int) -> dict:
    """Every bone's pose matrix in armature space on frame f: P[b] = P[parent] rel[b] basis[b]."""
    skel = prepare(skel)
    out = {}
    for b in skel["order"]:
        basis = m4(clip["loc"][b][f] if b in clip["loc"] else (0.0, 0.0, 0.0),
                   clip["rot"][b][f] if b in clip["rot"] else (1.0, 0.0, 0.0, 0.0))
        p = skel["parent"][b]
        out[b] = M.mat_mul(skel["rel"][b] if p is None else M.mat_mul(out[p], skel["rel"][b]), basis)
    return out


def basis_of(skel: dict, poses: dict, bone: str):
    """(loc, quaternion): the basis that puts bone at poses[bone] under its parent's poses[parent]."""
    p = skel["parent"][bone]
    m = M.mat_mul(rigid_inv(skel["rel"][bone]), poses[bone] if p is None else M.mat_mul(rigid_inv(poses[p]),
                                                                                         poses[bone]))
    return pos(m), mat_q(m)


def tracks(skel: dict, clip: dict, bones) -> dict:
    """{bone: [its head's position per frame 0..T]}."""
    out = {b: [] for b in bones}
    for f in range(frames(clip) + 1):
        poses = fk(skel, clip, f)
        for b in bones:
            out[b].append(pos(poses[b]))
    return out


def copy_clip(clip: dict, **over) -> dict:
    return {**clip, "loc": {b: list(v) for b, v in clip["loc"].items()},
            "rot": {b: list(v) for b, v in clip["rot"].items()}, **over}


def rot_between(u, v):
    """The shortest rotation taking direction u to direction v."""
    cx = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    w = math.sqrt(M._v_dot(u, u) * M._v_dot(v, v)) + M._v_dot(u, v)
    if w < 1e-12:  # opposite: half a turn about any axis normal to u
        a = (0.0, -u[2], u[1]) if abs(u[0]) < 0.9 else (-u[1], u[0], 0.0)
        return M.q_norm((0.0, *a))
    return M.q_norm((w, *cx))


# ------------------------------------------------------------------------------------------------ measuring
def _foot_points(side: str):
    return f"{side}Foot", f"{side}Toes"


def _xy(track):
    return [(p[0], p[1]) for p in track]


def _mask(track, window):
    return M.contact_mask([p[2] for p in track], window)


def foot_contacts(points: dict, fps: float, window: float = CONTACT_M, cyclic: bool = True) -> tuple:
    """(the ground velocity, {point: contact mask}) for foot points {name: [(x, y, z) per frame]} (one cycle when
    cyclic): the ground velocity is anim_edit_math's median contact velocity; a point is in contact while it is low
    (within `window` of its lowest, contact_mask) and moves with the ground (its horizontal velocity within
    VELOCITY_TOL of the ground's): a low swing (a crouch's shuffle, a sprint's low recovery) is not a contact."""
    ext = {k: [v[-1], *v, v[0]] for k, v in points.items()} if cyclic else points  # the seam's frames counted too
    g = M.ground_velocity(M.contact_velocities(ext, fps, window)) or (0.0, 0.0)
    lim = max(VELOCITY_TOL[0], VELOCITY_TOL[1] * math.hypot(*g))
    masks = {}
    for name, tr in points.items():
        low, n, out = _mask(tr, window), len(tr), []
        for i in range(n):
            a, b = ((tr[(i - 1) % n], tr[(i + 1) % n]) if cyclic else (tr[max(i - 1, 0)], tr[min(i + 1, n - 1)]))
            span = 2 if cyclic else max(min(i + 1, n - 1) - max(i - 1, 0), 1)
            v = ((b[0] - a[0]) * fps / span, (b[1] - a[1]) * fps / span)
            out.append(low[i] and math.hypot(v[0] - g[0], v[1] - g[1]) <= lim)
        masks[name] = out
    return g, masks


def slide_mm(track: list, mask: list, velocity, fps: float) -> float:
    """The largest horizontal stray (mm) of a foot point inside its contact windows (one cycle, frames 0..T-1) from the
    straight line at the ground's velocity through each window's middle (plant's line): 0 for a planted point."""
    worst = 0.0
    for win in M.contact_windows(mask, cyclic=True):
        if len(win) == len(track):  # always on the ground (an idle): its stray from its own mean
            cx = sum(track[i][0] for i in win) / len(win)
            cy = sum(track[i][1] for i in win) / len(win)
            worst = max(worst, *(math.hypot(track[i][0] - cx, track[i][1] - cy) for i in win))
            continue
        mid = (len(win) - 1) / 2
        a, b = track[win[int(math.floor(mid))]], track[win[int(math.ceil(mid))]]
        anchor = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        for k, i in enumerate(win):
            t = (k - mid) / fps
            worst = max(worst, math.hypot(track[i][0] - anchor[0] - velocity[0] * t,
                                          track[i][1] - anchor[1] - velocity[1] * t))
    return worst * 1000.0


def _walk(win, ref, goal_ref, ankle, toe, mask_a, mask_t, step) -> list:
    """The ankle's goals (xy) over one contact window `win` (frame indices into the cycle) from its goal on win[ref]:
    between two frames the point in contact on both (the ankle, else the toes, else the one down on the first) moves
    with the ground by `step` (m per frame), the rest of the foot following the clip's own foot geometry, so the
    heel-to-toe roll hands the plant from the ankle to the toes without a slide."""
    out = {ref: goal_ref}
    for d in (1, -1):
        goal, k = goal_ref, ref
        while 0 <= k + d < len(win):
            i0, i1 = win[k], win[k + d]
            on_ankle = (mask_a[i0] and mask_a[i1]) or (mask_a[i0] and not (mask_t[i0] and mask_t[i1]))
            piv = ankle if on_ankle else toe
            p = M._v_add(goal, M._v_sub(piv[i0], ankle[i0]))
            p = (p[0] + d * step[0], p[1] + d * step[1])
            goal = M._v_add(p, M._v_sub(ankle[i1], piv[i1]))
            k += d
            out[k] = goal
    return [out[k] for k in range(len(win))]


def fill_gaps(mask: list, gap: int = None, cyclic: bool = True) -> list:
    """A contact mask with its breaks of at most `gap` frames between two contacts filled (one contact that flickers
    off for a frame is one step, not two)."""
    gap = MERGE_GAP if gap is None else gap
    n, out = len(mask), list(mask)
    if all(mask) or not any(mask):
        return out
    i = 0
    while i < n:
        if mask[i] or (not cyclic and i == 0):
            i += 1
            continue
        j = i
        while j < n and not mask[j]:
            j += 1
        before = mask[i - 1] if i > 0 else (cyclic and mask[-1])
        after = mask[j] if j < n else (cyclic and mask[0])
        if j - i <= gap and before and after and (cyclic or (i > 0 and j < n)):
            for k in range(i, j):
                out[k] = True
        i = j
    if cyclic and not mask[0] and not mask[-1]:  # a break over the seam
        lo = next(k for k in range(n) if mask[k])
        hi = next(k for k in range(n - 1, -1, -1) if mask[k])
        if lo + (n - 1 - hi) <= gap:
            for k in list(range(lo)) + list(range(hi + 1, n)):
                out[k] = True
    return out


def _windows(mask_a, mask_t) -> list | None:
    """One foot's contact windows (the ankle or the toes down, breaks of MERGE_GAP frames filled, cyclic); None for
    a foot that never lifts."""
    wins = M.contact_windows(fill_gaps([a or t for a, t in zip(mask_a, mask_t)]), cyclic=True)
    return None if len(wins) == 1 and len(wins[0]) == len(mask_a) else wins


def plant_foot(ankle, toe, ankle_s, mask_a, mask_t, velocity, fps: float, blend: int = 2) -> list:
    """anim_edit_math's plant for a foot that rolls: each contact window's ankle goals walked (_walk) from the middle
    of the ankle's own frames at its scaled place `ankle_s`, the `blend` frames around a window drawn toward the
    window's line by (blend + 1 - j) / (blend + 1). Tracks: (x, y) per frame of one cycle (0..T-1)."""
    T = len(ankle)
    step = (velocity[0] / fps, velocity[1] / fps)
    weight, target = [0.0] * T, list(ankle_s)
    for win in _windows(mask_a, mask_t) or []:
        own = [k for k, i in enumerate(win) if mask_a[i]]
        ref = own[len(own) // 2] if own else len(win) // 2
        goals = _walk(win, ref, ankle_s[win[ref]], ankle, toe, mask_a, mask_t, step)
        for k, i in enumerate(win):
            weight[i], target[i] = 1.0, goals[k]
        for j in range(1, blend + 1):
            w = (blend + 1 - j) / (blend + 1)
            for idx, base, sgn in ((win[0] - j, goals[0], -1), (win[-1] + j, goals[-1], 1)):
                idx %= T
                if w > weight[idx]:
                    weight[idx], target[idx] = w, (base[0] + sgn * j * step[0], base[1] + sgn * j * step[1])
    return [M.lerp(ankle_s[i], target[i], weight[i]) if weight[i] else tuple(ankle_s[i]) for i in range(T)]


def pivot_slide_mm(ankle, toe, mask_a, mask_t, velocity, fps: float) -> float:
    """How far (mm) a foot slides over its contacts: per window the ankle against _walk's goals from its first frame
    (the point in contact moving with the ground, the roll handing it from the ankle to the toes); 0 for a foot
    that never lifts (its drift is in slide_mm)."""
    step = (velocity[0] / fps, velocity[1] / fps)
    worst = 0.0
    for win in _windows(mask_a, mask_t) or []:
        goals = _walk(win, 0, ankle[win[0]], ankle, toe, mask_a, mask_t, step)
        worst = max(worst, *(math.hypot(ankle[i][0] - g[0], ankle[i][1] - g[1]) for i, g in zip(win, goals)))
    return worst * 1000.0


def seam_deg(clip: dict, i: int = 0, j: int | None = None) -> float:
    """The largest turn of any bone between frames i and j (the loop's seam: 0 for a closed loop)."""
    j = frames(clip) if j is None else j
    return max(M.q_angle(M.q_norm(v[i]), M.q_norm(v[j])) for v in clip["rot"].values())


def measure(skel: dict, clip: dict, window: float = CONTACT_M) -> dict:
    """A loop's own numbers from its FK feet: the ground velocity under the planted feet (anim_edit_math's median
    contact velocity), the hips' travel, v0 = the body's speed over the ground (m/s), the contact windows per foot
    (a heel or toe within 2 cm of its lowest), c0 = the windows of both feet per second (steps/s), the stride (m per
    step), the feet's slide (mm), the seam (degrees). A foot that never leaves the ground (an idle) has one window and
    the clip no cadence (c0 None): its slide is its drift from its own mean."""
    T = frames(clip)
    fps = float(clip["fps"])
    cycle_s = T / fps
    names = [p for s in SIDES for p in _foot_points(s)]
    tr = tracks(skel, clip, names + ["Hips"])
    cyc = {k: v[:-1] for k, v in tr.items()}
    g, mk = foot_contacts({k: cyc[k] for k in names}, fps, window)
    hips = tr["Hips"]
    hv = ((hips[-1][0] - hips[0][0]) / cycle_s, (hips[-1][1] - hips[0][1]) / cycle_s)
    rel = (hv[0] - g[0], hv[1] - g[1])
    v0 = math.hypot(*rel)
    wins, planted = {}, False
    for s in SIDES:
        a, t = (mk[p] for p in _foot_points(s))
        w = M.contact_windows(fill_gaps([x or y for x, y in zip(a, t)]), cyclic=True)
        wins[s] = [x[0] for x in w]
        planted |= len(w) == 1 and len(w[0]) == T
    n = sum(len(v) for v in wins.values())
    c0 = None if planted or n == 0 else M.natural_cadence(n, cycle_s)
    return {"clip": clip["name"], "fps": fps, "intervals": T, "cycle_s": round(cycle_s, 4),
            "ground_m_s": [round(x, 4) for x in g], "hips_m_s": [round(x, 4) for x in hv],
            "v0": round(v0, 4), "c0": None if c0 is None else round(c0, 4),
            "stride_m": None if not c0 else round(v0 / c0, 4), "contacts": wins,
            "slide_mm": {p: round(slide_mm(cyc[p], mk[p], g, fps), 2) for p in names},
            "foot_slide_mm": {s: round(pivot_slide_mm(*(_xy(cyc[p]) for p in _foot_points(s)),
                                                      *(mk[p] for p in _foot_points(s)), g, fps), 2)
                              for s in SIDES},
            "seam_deg": round(seam_deg(clip), 3)}


def game_table(measures: dict) -> list[dict]:
    """At each of the game's speeds the clip's rate (speed / v0), the cadence the player sees (rate x c0) and its step
    interval beside the footstep beat."""
    rows = []
    for what, speed, clip, beat in GAME:
        m = measures.get(clip)
        if not m or not m["v0"] or not m["c0"]:
            continue
        rate = speed / m["v0"]
        cad = rate * m["c0"]
        rows.append({"what": what, "speed": speed, "clip": clip, "rate": round(rate, 3), "cadence": round(cad, 3),
                     "step_s": round(1.0 / cad, 3), "beat_s": beat,
                     "beat_cadence": None if beat is None else round(1.0 / beat, 3)})
    return rows


# --------------------------------------------------------------------------------------------------- retime
def retime(clip: dict, rate: float) -> tuple[dict, float]:
    """A closed loop played `rate` times as fast on the same frame grid (anim_edit_math's whole-frame count and its
    Catmull-Rom sampling over the seam). Returns (the clip, the effective rate)."""
    T = frames(clip)
    T2, r = M.retime_count(T, rate)
    out = copy_clip(clip, loc={}, rot={})
    for t in M.retime_times(T, T2)[:-1]:
        i, f = M.split_index(t, T)
        idx = M.neighbours(i, T, closed=True)
        w = M.catmull_rom(f)
        for b, v in clip["loc"].items():
            out["loc"].setdefault(b, []).append(tuple(sum(wk * v[k][c] for wk, k in zip(w, idx)) for c in range(3)))
        for b, v in clip["rot"].items():
            ref = v[i]
            qs = [M.q_hemi(v[k], ref) for k in idx]
            out["rot"].setdefault(b, []).append(M.q_norm(tuple(sum(wk * q[c] for wk, q in zip(w, qs))
                                                               for c in range(4))))
    for ch in (out["loc"], out["rot"]):
        for b in ch:
            ch[b].append(ch[b][0])
    return out, r


# --------------------------------------------------------------------------------------------------- stride
def stride(skel: dict, clip: dict, cadence: float | None = None, rate: float | None = None,
           speed: float | None = None, scale: float | None = None, window: float = CONTACT_M,
           blend: int = 2, bend_min_deg: float | None = None, widen_m: float = 0.0) -> tuple[dict, dict]:
    """A loop's cadence and stride length changed with its feet kept planted:
    1. retimed to `cadence` steps/s (or by `rate`; neither: unchanged);
    2. the stride scaled by `scale`, or by anim_edit_math's stride_scale so the loop covers `speed` m/s at rate 1
       (neither: 1): the hips' travel along the ground axis (a root-motion clip's) and each ankle's offset from the
       hips along it (scale_offset), each ankle's contact windows then laid on a straight line at the new ground
       velocity (plant);
    3. each leg solved again per frame (two_bone: the hip kept, the knee in the clip's own knee plane), the foot keeping
       its world rotation, the toes following it; `widen_m`: each ankle moved this far outward across the travel axis
       on every frame (a constant, so a planted foot stays planted: knees that cross get room); `bend_min_deg`: on
       the swing frames (the foot off the ground) a leg straighter than this knee bend has its ankle drawn toward
       the hip until the knee bends that much (no locked knee at a kick's extension; planted frames left as solved).
    Returns (the clip, the report: before and after, the scale, the effective rate, the planted ankles' slide)."""
    skel = prepare(skel)
    m0 = measure(skel, clip, window)
    r = 1.0
    if cadence is not None or rate is not None:
        if rate is None:
            if not m0["c0"]:
                raise ValueError(f"{clip['name']}: no cadence to retime from")
            rate = cadence / m0["c0"]
        clip, r = retime(clip, rate)
    if scale is None:
        scale = 1.0 if speed is None else M.stride_scale(speed, r, m0["v0"])
    fps = float(clip["fps"])
    g = m0["ground_m_s"]
    rel = (m0["hips_m_s"][0] - g[0], m0["hips_m_s"][1] - g[1])
    n = math.hypot(*rel)
    d = (rel[0] / n, rel[1] / n) if n > 1e-9 else (0.0, -1.0)  # the travel axis (forward: -Y)
    g2 = (g[0] * r * scale, g[1] * r * scale)
    T = frames(clip)
    out = copy_clip(clip)
    # the hips' travel along d scaled (its linear trend over the loop; an in-place clip has none)
    hips0 = [pos(fk(skel, clip, f)["Hips"]) for f in range(T + 1)]
    trend = ((hips0[-1][0] - hips0[0][0]) / T, (hips0[-1][1] - hips0[0][1]) / T)
    along = trend[0] * d[0] + trend[1] * d[1]
    for f in range(T + 1):
        poses = fk(skel, out, f)
        k = (scale - 1.0) * along * f
        poses["Hips"] = M.mat_mul([[1, 0, 0, k * d[0]], [0, 1, 0, k * d[1]], [0, 0, 1, 0], [0, 0, 0, 1]],
                                  poses["Hips"])
        out["loc"]["Hips"][f], q = basis_of(skel, poses, "Hips")
        out["rot"]["Hips"][f] = M.q_hemi(q, out["rot"]["Hips"][f])
    posed = [fk(skel, out, f) for f in range(T + 1)]
    report = {"before": m0, "rate_asked": rate, "rate_eff": round(r, 4), "intervals": [m0["intervals"], T],
              "scale": round(scale, 4), "fit": M.stride_fit(scale), "ground_after_m_s": [round(x, 4) for x in g2],
              "ankle_miss_mm": 0.0, "slide_bound_mm": SLIDE_BOUND_MM}
    for side in SIDES:
        u, lo, ft = (f"{side}{x}" for x in LEG)
        ank = [pos(p[ft]) for p in posed]
        hip = [pos(p["Hips"]) for p in posed]
        toe = [pos(p[f"{side}Toes"]) for p in posed]
        pts = []
        for a, h in zip(ank, hip):
            o = M.scale_offset((a[0] - h[0], a[1] - h[1]), d, scale)
            pts.append((h[0] + o[0], h[1] + o[1]))
        _, mk = foot_contacts({"a": ank[:-1], "t": toe[:-1]}, fps, window)
        flat = plant_foot(_xy(ank[:-1]), _xy(toe[:-1]), pts[:-1], mk["a"], mk["t"], g2, fps, blend)
        # the end frame is the start a loop on: a loop that travels (a root-motion bake) carries its feet with it
        flat.append((flat[0][0] + hip[-1][0] - hip[0][0], flat[0][1] + hip[-1][1] - hip[0][1]))
        if widen_m:
            u0 = pos(posed[0][u])
            side_x = (u0[0] - hip[0][0]) * -d[1] + (u0[1] - hip[0][1]) * d[0]  # the leg's side across the axis
            w = math.copysign(widen_m, side_x)
            flat = [(x - w * d[1], y + w * d[0]) for x, y in flat]
        down = fill_gaps([a or t for a, t in zip(mk["a"], mk["t"])])
        moved = 0.0
        for f in range(T + 1):
            P = posed[f]
            H, K, A = pos(P[u]), pos(P[lo]), pos(P[ft])
            goal = (flat[f][0], flat[f][1], A[2])
            if bend_min_deg is not None and not down[f % T]:
                floored = _knee_floor(H, K, A, goal, bend_min_deg)
                moved = max(moved, _len(M._v_sub(floored, goal)))
                goal = floored
            delta = M._v_sub(goal, A)
            K2 = M._v_add(two_bone(H, K, A, M._v_sub(H, delta)), delta)
            du = rot_between(M._v_sub(K, H), M._v_sub(K2, H))
            dl = rot_between(M.q_rotate(du, M._v_sub(A, K)), M._v_sub(goal, K2))
            new = dict(P)
            new[u] = m4(H, M.q_mul(du, mat_q(P[u])))
            new[lo] = m4(K2, M.q_mul(dl, M.q_mul(du, mat_q(P[lo]))))
            new[ft] = m4(goal, mat_q(P[ft]))
            for b in (u, lo, ft):
                out["loc"][b][f], q = basis_of(skel, new, b)
                out["rot"][b][f] = M.q_hemi(q, out["rot"][b][f])
        after = tracks(skel, out, [ft])[ft]
        miss = max(math.hypot(a[0] - p[0], a[1] - p[1]) for f, (a, p) in enumerate(zip(after, flat))
                   if bend_min_deg is None or down[f % T]) * 1000.0  # the planted frames (the floor moves the rest)
        report["ankle_miss_mm"] = round(max(report["ankle_miss_mm"], miss), 3)
        report.setdefault("knee_floor_mm", {})[side] = round(moved * 1000.0, 1)
    report["after"] = measure(skel, out, window)
    report["planted_slide_mm"] = max(report["after"]["foot_slide_mm"].values())
    return out, report


def _knee_floor(H, K, A, goal, bend_min_deg: float):
    """The ankle goal of a leg (hip H, knee K, ankle A: its thigh and shin lengths) drawn toward the hip along their
    line until the knee bends at least bend_min_deg (0: straight): the least move that bends the knee."""
    la, lb = _len(M._v_sub(K, H)), _len(M._v_sub(A, K))
    reach = math.sqrt(la * la + lb * lb + 2.0 * la * lb * math.cos(math.radians(bend_min_deg)))
    v = M._v_sub(goal, H)
    if _len(v) <= reach:
        return goal
    return M._v_add(H, tuple(c * reach / _len(v) for c in v))


def _len(v) -> float:
    return math.sqrt(sum(c * c for c in v))


def _angle(u, v) -> float:
    n = _len(u) * _len(v)
    return 0.0 if n < 1e-12 else math.degrees(math.acos(max(-1.0, min(1.0, sum(a * b for a, b in zip(u, v)) / n))))


def knee_bend(skel: dict, clip: dict) -> dict:
    """Per leg the knee's bend over the loop (degrees between the thigh and the shin; 0 = a locked straight knee):
    the least over all frames and over its swing frames (the foot off the ground), and the frame of the least."""
    skel = prepare(skel)
    T = frames(clip)
    out = {}
    tr = tracks(skel, clip, [f"{s}{x}" for s in SIDES for x in LEG] + [f"{s}Toes" for s in SIDES])
    _, mk = foot_contacts({f"{s}{p}": tr[f"{s}{p}"][:-1] for s in SIDES for p in ("Foot", "Toes")},
                          float(clip["fps"]))
    for s in SIDES:
        down = fill_gaps([a or t for a, t in zip(mk[f"{s}Foot"], mk[f"{s}Toes"])])
        bends = [_angle(M._v_sub(tr[f"{s}LowerLeg"][f], tr[f"{s}UpperLeg"][f]),
                        M._v_sub(tr[f"{s}Foot"][f], tr[f"{s}LowerLeg"][f])) for f in range(T)]
        swing = [b for b, d in zip(bends, down) if not d] or bends
        f0 = min(range(T), key=lambda f: bends[f])
        out[s] = {"min_deg": round(bends[f0], 1), "min_frame": f0, "swing_min_deg": round(min(swing), 1)}
    return out


HONEST_HEIGHT_M = 0.01  # honest_slide: a foot point is down while within 1 cm of its lowest height in the loop ...
HONEST_SPEED_M_S = 0.5  # ... and moving under 0.5 m/s against the ground (absolute, whatever the clip's speed)


def honest_slide(skel: dict, clip: dict, ground=None, height: float = HONEST_HEIGHT_M,
                 speed: float = HONEST_SPEED_M_S) -> dict:
    """The planted feet's slide from the per-frame foot heights and speeds alone (no gap filling, no tolerance that
    grows with the clip's speed, so a swing frame never joins a contact), per foot point (ankle, toes):
    - drift_mm: in each run of planted frames (within `height` of the point's lowest, under `speed` m/s against the
      ground, cyclic) the point's horizontal stray from the run's first frame after the ground's travel is taken
      off (`ground`, m/s; default the measure's ground velocity);
    - skate_m_s: the fastest the point moves against the ground on any frame within `height` of its lowest (a heel
      or toe that skims the floor while it lands or lifts).
    Per foot the worst of its two points, and the number of planted runs."""
    skel = prepare(skel)
    T = frames(clip)
    fps = float(clip["fps"])
    if ground is None:
        ground = measure(skel, clip)["ground_m_s"]
    step = (ground[0] / fps, ground[1] / fps)
    names = [p for s in SIDES for p in _foot_points(s)]
    tr = tracks(skel, clip, names)
    out = {}
    for s in SIDES:
        drift = skate = 0.0
        runs = 0
        for p in _foot_points(s):
            t = tr[p][:-1]
            lowest = min(q[2] for q in t)

            def slip(i):  # the speed against the ground around frame i (central difference, cyclic)
                a, b = t[(i - 1) % T], t[(i + 1) % T]
                return math.hypot(b[0] - a[0] - 2 * step[0], b[1] - a[1] - 2 * step[1]) * fps / 2.0
            low = [q[2] <= lowest + height for q in t]
            for i in range(T):
                if low[i]:
                    skate = max(skate, slip(i))
            for win in M.contact_windows([low[i] and slip(i) <= speed for i in range(T)], cyclic=True):
                if len(win) < 2:
                    continue
                runs += 1
                a = t[win[0]]
                for k, i in enumerate(win):
                    drift = max(drift, math.hypot(t[i][0] - a[0] - k * step[0], t[i][1] - a[1] - k * step[1]))
        out[s] = {"drift_mm": round(drift * 1000.0, 1), "skate_m_s": round(skate, 3), "runs": runs}
    return out


def hand_clearance(skel: dict, clip: dict) -> dict:
    """Per hand its least distance (m) over the loop from the torso's axis (the segment Hips to Neck): a hand that
    swings into the belly or the ribs comes close to it."""
    skel = prepare(skel)
    T = frames(clip)
    tr = tracks(skel, clip, ["Hips", "Neck", "LeftHand", "RightHand"])
    out = {}
    for s in SIDES:
        best = math.inf
        for f in range(T):
            a, b, h = tr["Hips"][f], tr["Neck"][f], tr[f"{s}Hand"][f]
            ab = M._v_sub(b, a)
            t = max(0.0, min(1.0, sum(x * y for x, y in zip(M._v_sub(h, a), ab)) / max(sum(x * x for x in ab), 1e-12)))
            best = min(best, _len(M._v_sub(h, M._v_add(a, tuple(c * t for c in ab)))))
        out[s] = round(best, 4)
    return out


def _q_conj(q):
    return (q[0], -q[1], -q[2], -q[3])


def arms_from(clip: dict, donor: dict, k: float = 1.0, w: float = 1.0, sides=SIDES,
              phase: float = 0.0) -> tuple[dict, dict]:
    """The arms (UpperArm, LowerArm, Hand per side) given another loop's swing: the donor sampled over the clip's
    frames (both loops start on the same foot's contact, so the swing keeps its phase to the feet), each bone's
    pose = the donor's swing about its own mean, scaled by k, on a held pose blended from the clip's mean (w 0) to
    the donor's mean (w 1); `phase`: the donor sampled that fraction of its loop later (0.5: the swing against the
    other foot, a backpedal's counter-swing, P3). Returns (clip, per bone the largest swing from the mean before and
    after, degrees)."""
    out = copy_clip(clip)
    T, Td = frames(clip), frames(donor)
    ident = (1.0, 0.0, 0.0, 0.0)
    rep = {}
    for s in sides:
        for part in ARM:
            b = f"{s}{part}"
            own, dv = clip["rot"][b], donor["rot"][b]
            m_own, m_d = q_mean(own[:-1]), q_mean(dv[:-1])
            hold = M.q_slerp(m_own, M.q_hemi(m_d, m_own), w)
            inv = _q_conj(m_d)
            new = []
            for f in range(T + 1):
                u = (f * Td / T + phase * Td) % Td
                i = min(int(u), Td - 1)
                q = M.q_slerp(M.q_norm(dv[i]), M.q_hemi(M.q_norm(dv[i + 1]), dv[i]), u - i)
                delta = M.q_mul(M.q_hemi(M.q_norm(q), m_d), inv)
                delta = M.q_slerp(ident, M.q_hemi(M.q_norm(delta), ident), k)
                new.append(M.q_hemi(M.q_norm(M.q_mul(delta, hold)), own[f]))
            new[T] = new[0]
            out["rot"][b] = new
            mean = q_mean(new[:-1])
            rep[b] = [round(max(M.q_angle(m_own, M.q_norm(q)) for q in own), 2),
                      round(max(M.q_angle(mean, q) for q in new), 2)]
    return out, {"k": k, "w": w, "phase": phase, "swing_deg": rep}


# ---------------------------------------------------------------------------------------------------- cycle
def _features(clip: dict, bones) -> list:
    ref = {b: M.q_norm(clip["rot"][b][0]) for b in bones}
    return [[c for b in bones for c in M.q_hemi(M.q_norm(clip["rot"][b][f]), ref[b])] for f in range(frames(clip) + 1)]


def _close(clip: dict, i: int, j: int, skel: dict | None = None) -> dict:
    """Frames i..j as a closed loop: each channel's residual spread over it (close_quats, close_vectors), the Root's
    and the Hips' horizontal travel kept (only what is left beside its linear trend is closed). The travel is
    horizontal in armature space: a bone's basis location turns by its rest rotation (skel; a Blender bone's Y axis
    runs along it, so the alien's Hips carry the travel on their basis x and z), the bones above it at rest."""
    out = copy_clip(clip)
    for b, v in clip["rot"].items():
        out["rot"][b] = M.close_quats(v[i:j + 1])
    for b, v in clip["loc"].items():
        seg = v[i:j + 1]
        if b in ("Root", "Hips"):
            r = skel["rest"][b] if skel else [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
            to_arm = [[r[a][c] for c in range(3)] for a in range(3)]
            seg = [tuple(sum(to_arm[a][c] * p[c] for c in range(3)) for a in range(3)) for p in seg]
            n = len(seg) - 1
            tr = [((seg[-1][0] - seg[0][0]) * k / n, (seg[-1][1] - seg[0][1]) * k / n, 0.0) for k in range(n + 1)]
            res = M.close_vectors([M._v_sub(p, x) for p, x in zip(seg, tr)])
            arm = [M._v_add(p, x) for p, x in zip(res, tr)]
            out["loc"][b] = [tuple(sum(to_arm[c][a] * p[c] for c in range(3)) for a in range(3)) for p in arm]
        else:
            out["loc"][b] = M.close_vectors(seg)
    return out


def cycle(skel: dict, clip: dict, foot: str = "Left", min_s: float | None = None, max_s: float | None = None,
          window: float = CONTACT_M, loop: bool | None = None) -> tuple[dict, dict]:
    """The best loop of a clip, starting and ending on `foot`'s contact (the first frame of one of its contact
    windows). A loop (`loop`; None: a name ending in _Loop) keeps its length: its seam (its last frame against its
    first) spread over it, then turned to start there. Any other clip: the cut (i, j) with
    i a contact start, j - i between min_s and max_s, whose poses and velocities (the legs and trunk) differ least
    (anim_edit_math's best_cycle cost), its residual spread over the cycle (close_quats, close_vectors; the hips'
    horizontal travel kept). Returns (the closed loop, the report: the cut and the seam before closing, degrees)."""
    skel = prepare(skel)
    T = frames(clip)
    fps = float(clip["fps"])
    pts = tracks(skel, clip, _foot_points(foot))
    seam0 = seam_deg(clip)
    if loop if loop is not None else clip["name"].endswith("_Loop"):  # a loop: closed, started on the foot's contact
        _, mk = foot_contacts({p: pts[p][:-1] for p in _foot_points(foot)}, fps, window)
        a, t = (mk[p] for p in _foot_points(foot))
        wins = M.contact_windows(fill_gaps([x or y for x, y in zip(a, t)]), cyclic=True)
        c = wins[0][0] if wins else 0
        out = _close(clip, 0, T, skel)
        h0, h1 = (pos(fk(skel, out, f)["Hips"]) for f in (0, T))
        travel = (h1[0] - h0[0], h1[1] - h0[1])  # a loop that travels (a root-motion bake) keeps going after the turn
        for ch in (out["loc"], out["rot"]):
            for b, v in ch.items():
                ch[b] = v[c:-1] + v[:c] + [v[c]]
        if "Hips" in out["loc"] and math.hypot(*travel) > 1e-9:
            for f in range(T - c, T + 1):  # the frames from before the start and the end (start 0: the end), a loop on
                poses = fk(skel, out, f)
                poses["Hips"] = M.mat_mul([[1, 0, 0, travel[0]], [0, 1, 0, travel[1]], [0, 0, 1, 0], [0, 0, 0, 1]],
                                          poses["Hips"])
                out["loc"]["Hips"][f] = basis_of(skel, poses, "Hips")[0]
        return out, {"closed": True, "start": c, "intervals": T, "seam_deg": round(seam0, 3),
                     "travel_m": [round(x, 4) for x in travel]}
    _, mk = foot_contacts(pts, fps, window, cyclic=False)
    a, t = (mk[p] for p in _foot_points(foot))
    mask = fill_gaps([x or y for x, y in zip(a, t)], cyclic=False)
    starts = [i for i in range(T + 1) if mask[i] and (i == 0 or not mask[i - 1])]
    bones = [b for b in clip["rot"] if not any(k in b for k in ("Index", "Middle", "Ring", "Little", "Thumb"))]
    feats = _features(clip, bones)
    vels = M.central_diff(feats)
    min_s = min_s if min_s is not None else 0.5
    max_s = max_s if max_s is not None else T / fps
    best = None
    for i in starts:  # best_cycle on the two-frame window [i, j]: its cost, the start held on a contact
        lo, hi = max(1, round(min_s * fps)), round(max_s * fps)
        for j in range(i + lo, min(i + hi, T) + 1):
            _, _, c = M.best_cycle([feats[i], feats[j]], [vels[i], vels[j]], 1.0, 1, 1)
            if best is None or c < best[2]:
                best = (i, j, c)
    if best is None:
        raise ValueError(f"{clip['name']}: no {foot} contact with a cycle of {min_s}-{max_s} s after it")
    i, j, cost = best
    seam = seam_deg(clip, i, j)
    out = _close(clip, i, j, skel)
    return out, {"closed": False, "start": i, "end": j, "intervals": j - i, "cost": round(cost, 5),
                 "seam_deg": round(seam, 3), "seam_after_deg": round(seam_deg(out), 3)}


# ------------------------------------------------------------------------------------------------ arm swing
def q_mean(qs: list):
    """The normalised sum of quaternions on the first one's hemisphere (close to the mean rotation for a swing)."""
    ref = M.q_norm(qs[0])
    acc = [0.0] * 4
    for q in qs:
        q = M.q_hemi(M.q_norm(q), ref)
        acc = [a + c for a, c in zip(acc, q)]
    return M.q_norm(tuple(acc))


def arm_swing(clip: dict, k: float, sides=SIDES) -> tuple[dict, dict]:
    """The arm chain (UpperArm, LowerArm, Hand per side) slerped toward its own mean pose over the loop: k = 1 leaves
    the clip, 0 holds the mean, between scales each bone's swing about it. Returns (clip, the largest swing per bone
    from the mean before and after, degrees)."""
    out = copy_clip(clip)
    rep = {}
    for s in sides:
        for part in ARM:
            b = f"{s}{part}"
            v = clip["rot"][b]
            mean = q_mean(v[:-1])
            new = [M.q_hemi(M.q_slerp(mean, M.q_norm(q), k), q) for q in v]
            out["rot"][b] = new
            rep[b] = [round(max(M.q_angle(mean, M.q_norm(q)) for q in v), 2),
                      round(max(M.q_angle(mean, q) for q in new), 2)]
    return out, {"k": k, "swing_deg": rep}


# --------------------------------------------------------------------------------------------------- mirror
def mirror(skel: dict, clip: dict) -> dict:
    """A clip mirrored across the body's middle (X = 0): bone b takes its partner's pose reflected (anim_edit_math's
    mirror_correction and mirror_pose with S = the X reflection), so a left clip becomes a right one and the root's
    travel flips on X; the name's Left and Right swap."""
    skel = prepare(skel)
    pairs = mirror_pairs(skel["order"])
    rest = skel["rest"]
    C = {b: M.mirror_correction(REFLECT_X, rest[b], rest[pairs[b]]) for b in skel["order"]}
    out = copy_clip(clip, name=mirror_clip_name(clip["name"]))
    for f in range(frames(clip) + 1):
        P = fk(skel, clip, f)
        Q = {b: M.mirror_pose(REFLECT_X, P[pairs[b]], C[b]) for b in skel["order"]}
        for b in skel["order"]:
            loc, q = basis_of(skel, Q, b)
            if b in out["loc"]:
                out["loc"][b][f] = loc
            if b in out["rot"]:
                prev = out["rot"][b][f - 1] if f else clip["rot"][pairs[b]][0]
                out["rot"][b][f] = M.q_hemi(q, prev)
    return out


# ----------------------------------------------------------------------------------------------- orient warp
# the counter-twist above the Hips (strafe pilot, art #196): each bone's share of the hips' yaw turned back, from the
# hips up; the shares sum to 1, so the Neck's child (the Head) faces the aim again
ORIENT_SPLIT = (("Spine", 0.2), ("Chest", 0.25), ("UpperChest", 0.3), ("Neck", 0.25))
UP = (0.0, 0.0, 1.0)


def _yaw(q, deg: float):
    """A world rotation turned by deg about the vertical (positive: counter-clockwise seen from above)."""
    return M.q_mul(M.q_axis_angle(UP, deg), q)


def heading_deg(v) -> float:
    """The heading of a horizontal vector, degrees, 0 at the front (-Y), positive toward the left (+X)."""
    return math.degrees(math.atan2(v[0], -v[1]))


def hips_facing_deg(skel: dict, clip: dict, f: int) -> float:
    """The hips' heading on frame f (heading_deg of their forward: the hip joints' left-right line x up)."""
    P = fk(skel, clip, f)
    lr = M._v_sub(pos(P["LeftUpperLeg"]), pos(P["RightUpperLeg"]))
    return heading_deg((lr[1] * UP[2] - lr[2] * UP[1], lr[2] * UP[0] - lr[0] * UP[2]))


def bone_heading_deg(skel: dict, clip: dict, f: int, bone: str) -> float:
    """A bone's heading on frame f: its rest front (-Y in armature space) carried by its pose's turn from the rest."""
    skel = prepare(skel)
    P = fk(skel, clip, f)
    q = M.q_mul(mat_q(P[bone]), M.q_conj(mat_q(skel["rest"][bone])))
    return heading_deg(M.q_rotate(q, (0.0, -1.0, 0.0)))


def orient_warp(skel: dict, clip: dict, hip_yaw: float, travel_deg: float = 0.0, split=ORIENT_SPLIT,
                feet_yaw: float | None = None) -> tuple[dict, dict]:
    """The hips turned toward the travel with the chest and head kept on the aim (orientation warping, the strafe
    pilot): per frame
    1. the Hips turned by `hip_yaw` degrees about the vertical (positive: counter-clockwise seen from above, the
       front -Y toward the left +X), their position turned by `travel_deg` about the vertical through the origin;
    2. the chain above them counter-twisted: each bone of `split` ((bone, share), ...) ends turned by hip_yaw x (1 -
       the shares up to it), so with shares summing to 1 the Neck and the Head keep their own world rotation (on the
       aim); bones missing from the skeleton are skipped; everything else follows its parent;
    3. each foot re-planted: the ankle's goal is the clip's own ankle turned by `travel_deg` about the vertical through
       the origin (the feet travel along the clip's own direction turned by travel_deg: 0 keeps it, a forward run
       into a left strafe is 90), shifted by one constant per foot, the loop's mean of its hip joint's place (turned
       with the hips) less that joint turned by travel_deg: the foot stays under its own hip joint, so the leg keeps
       its reach where hip_yaw and travel_deg differ, and a constant keeps a planted foot planted; the foot's world
       rotation turned by `feet_yaw` (default hip_yaw: the toes point with the hips), the leg solved again with
       `two_bone` (the knee in its own plane), the toes following the foot.
    hip_yaw = travel_deg = 0 gives the clip back; hip_yaw = travel_deg = d with split () turns the whole clip by d.
    Returns (the clip, the report: the asked yaws, the split, the hips' and head's heading change measured on frame
    0, the ankles' largest miss, mm)."""
    skel = prepare(skel)
    feet_yaw = hip_yaw if feet_yaw is None else feet_yaw
    chain, left = {}, hip_yaw
    for b, share in split:
        left -= hip_yaw * share
        if b in skel["parent"]:
            chain[b] = left
    Rt = M.q_axis_angle(UP, travel_deg)
    out = copy_clip(clip)
    T = frames(clip)
    miss = 0.0
    orig, turned = [], []
    for f in range(T + 1):
        P = fk(skel, clip, f)
        orig.append(P)
        new = dict(P)
        new["Hips"] = m4(M.q_rotate(Rt, pos(P["Hips"])), _yaw(mat_q(P["Hips"]), hip_yaw))
        out["loc"]["Hips"][f], q = basis_of(skel, new, "Hips")
        out["rot"]["Hips"][f] = M.q_hemi(q, clip["rot"]["Hips"][f])
        for b, yaw in chain.items():  # the rotation part only: the chain keeps its own basis locations
            new[b] = m4(pos(P[b]), _yaw(mat_q(P[b]), yaw))
            out["rot"][b][f] = M.q_hemi(basis_of(skel, new, b)[1], clip["rot"][b][f])
        turned.append(fk(skel, out, f))  # the legs carried by the turned hips
    n = max(T, 1)
    shift = {s: tuple(sum(M._v_sub(pos(turned[f][f"{s}UpperLeg"]), M.q_rotate(Rt, pos(orig[f][f"{s}UpperLeg"])))[i]
                          for f in range(n)) / n for i in range(3)) for s in SIDES}
    for f in range(T + 1):
        P, Q = orig[f], turned[f]
        for side in SIDES:
            u, lo, ft = (f"{side}{x}" for x in LEG)
            H, K, A = pos(Q[u]), pos(Q[lo]), pos(Q[ft])
            goal = M._v_add(M.q_rotate(Rt, pos(P[ft])), (shift[side][0], shift[side][1], 0.0))
            delta = M._v_sub(goal, A)
            K2 = M._v_add(two_bone(H, K, A, M._v_sub(H, delta)), delta)
            du = rot_between(M._v_sub(K, H), M._v_sub(K2, H))
            dl = rot_between(M.q_rotate(du, M._v_sub(A, K)), M._v_sub(goal, K2))
            leg = dict(Q)
            leg[u] = m4(H, M.q_mul(du, mat_q(Q[u])))
            leg[lo] = m4(K2, M.q_mul(dl, M.q_mul(du, mat_q(Q[lo]))))
            leg[ft] = m4(goal, _yaw(mat_q(P[ft]), feet_yaw))
            for b in (u, lo, ft):
                q = basis_of(skel, leg, b)[1]
                out["rot"][b][f] = M.q_hemi(q, clip["rot"][b][f])
            got = pos(fk(skel, out, f)[ft])
            miss = max(miss, _len(M._v_sub(got, goal)))
    rep = {"hip_yaw": hip_yaw, "travel_deg": travel_deg, "feet_yaw": feet_yaw, "split": [list(s) for s in split],
           "hips_turn_deg": round(_wrap(hips_facing_deg(skel, out, 0) - hips_facing_deg(skel, clip, 0)), 3),
           "ankle_miss_mm": round(miss * 1000.0, 3),
           "feet_shift_mm": {k: [round(v[0] * 1000.0, 1), round(v[1] * 1000.0, 1)] for k, v in shift.items()}}
    if "Head" in skel["parent"]:
        rep["head_turn_deg"] = round(_wrap(bone_heading_deg(skel, out, 0, "Head")
                                           - bone_heading_deg(skel, clip, 0, "Head")), 3)
    return out, rep


def _wrap(deg: float) -> float:
    return (deg + 180.0) % 360.0 - 180.0


# ------------------------------------------------------------------ the strafe pilot, step P2: facing, pitch, head
LATERAL = (1.0, 0.0, 0.0)  # the character's left-right axis (it faces -Y): a turn about it pitches the front
HEAD_SPLIT = (("Neck", 0.5), ("Head", 0.5))  # `level_head`: the lift shared by the neck and the head


def _mean_deg(values) -> float:
    """The circular mean of angles in degrees."""
    s = sum(math.sin(math.radians(v)) for v in values)
    c = sum(math.cos(math.radians(v)) for v in values)
    return math.degrees(math.atan2(s, c))


def bone_front(skel: dict, poses: dict, bone: str):
    """A bone's rest front (-Y in armature space) carried by its pose's turn from the rest, in armature space."""
    q = M.q_mul(mat_q(poses[bone]), M.q_conj(mat_q(skel["rest"][bone])))
    return M.q_rotate(q, (0.0, -1.0, 0.0))


def pitch_of(v) -> float:
    """A direction's pitch above the horizontal, degrees (positive: up)."""
    return math.degrees(math.atan2(v[2], math.hypot(v[0], v[1])))


def travel_heading_deg(m: dict) -> float:
    """The heading of a measured clip's travel (measure's hips minus ground velocity: an in-place loop's feet move
    against it), 0 at the front, positive toward the left."""
    g, h = m["ground_m_s"], m["hips_m_s"]
    return heading_deg((h[0] - g[0], h[1] - g[1]))


def facing(skel: dict, clip: dict) -> dict:
    """Over the loop (circular means, degrees; headings 0 at the front -Y, positive toward the left): the hips' heading,
    the head's heading and its largest miss from its mean, the head's front pitch (positive: up; the eyes look level
    at 0) and the upper chest's front pitch (negative: the trunk leaning forward)."""
    skel = prepare(skel)
    T = frames(clip)
    hips, head, hp, cp = [], [], [], []
    for f in range(T):
        P = fk(skel, clip, f)
        lr = M._v_sub(pos(P["LeftUpperLeg"]), pos(P["RightUpperLeg"]))
        hips.append(heading_deg((lr[1] * UP[2] - lr[2] * UP[1], lr[2] * UP[0] - lr[0] * UP[2])))
        hf = bone_front(skel, P, "Head")
        head.append(heading_deg(hf))
        hp.append(pitch_of(hf))
        cp.append(pitch_of(bone_front(skel, P, "UpperChest")))
    hm = _mean_deg(head)
    return {"hips_yaw_deg": round(_mean_deg(hips), 2), "head_yaw_deg": round(hm, 2),
            "head_yaw_swing_deg": round(max(abs(_wrap(h - hm)) for h in head), 2),
            "head_pitch_deg": round(sum(hp) / len(hp), 2), "head_pitch_range_deg": [round(min(hp), 2), round(max(hp), 2)],
            "chest_pitch_deg": round(sum(cp) / len(cp), 2)}


def pitch(skel: dict, clip: dict, deg: float, split) -> dict:
    """The chain of `split` ((bone, share), ...) pitched about the character's left-right axis: each bone's world
    rotation turned by deg x (the shares up to it), positive leaning the front down (a forward lean), negative lifting
    it; the bones below and their places kept, every child following. Returns the clip."""
    skel = prepare(skel)
    out = copy_clip(clip)
    for f in range(frames(clip) + 1):
        P = fk(skel, clip, f)
        new, turn = dict(P), 0.0
        for b, share in split:
            turn += deg * share
            if b not in skel["parent"]:
                continue
            new[b] = m4(pos(P[b]), M.q_mul(M.q_axis_angle(LATERAL, turn), mat_q(P[b])))
            out["rot"][b][f] = M.q_hemi(basis_of(skel, new, b)[1], clip["rot"][b][f])
    return out


def level_head(skel: dict, clip: dict, target_deg: float = 0.0, split=HEAD_SPLIT, passes: int = 2) -> tuple[dict, dict]:
    """The neck and head lifted (or lowered) by one constant so the head's front pitch, its mean over the loop, comes
    to `target_deg` (0: the eyes look level ahead): the crouch's eyes on the way ahead, not on the floor. Returns (the
    clip, the report: the head's pitch before and after, the turn applied)."""
    before = facing(skel, clip)
    out, turn = clip, 0.0
    for _ in range(passes):
        miss = facing(skel, out)["head_pitch_deg"] - target_deg
        turn += miss
        out = pitch(skel, clip, turn, split)
    after = facing(skel, out)
    return out, {"target_deg": target_deg, "turn_deg": round(turn, 2), "split": [list(s) for s in split],
                 "head_pitch_before_deg": before["head_pitch_deg"], "head_pitch_after_deg": after["head_pitch_deg"],
                 "range_before_deg": before["head_pitch_range_deg"], "range_after_deg": after["head_pitch_range_deg"]}


# ------------------------------------------------------------------------------------------- the strafe pilot P3
def _down_masks(skel: dict, clip: dict) -> dict:
    """Per foot its planted frames 0..T-1 (heel or toe within the contact window, short gaps filled; knee_bend's)."""
    tr = tracks(skel, clip, [f"{s}{p}" for s in SIDES for p in ("Foot", "Toes")])
    _, mk = foot_contacts({k: v[:-1] for k, v in tr.items()}, float(clip["fps"]))
    return {s: fill_gaps([a or t for a, t in zip(mk[f"{s}Foot"], mk[f"{s}Toes"])]) for s in SIDES}


def _bump(mask: list) -> list:
    """Per frame a raised-cosine weight over each cyclic run of True frames: 1 in the run's middle, 0 outside it."""
    T = len(mask)
    w = [0.0] * T
    for run in M.contact_windows(mask, cyclic=True):
        n = len(run)
        for k, i in enumerate(run):
            w[i] = 0.5 - 0.5 * math.cos(2.0 * math.pi * (k + 0.5) / n) if n > 1 else 1.0
    return w


def lift_hips(skel: dict, clip: dict, lift_m: float = 0.0, bob_m: float = 0.0, flight_m: float = 0.0
              ) -> tuple[dict, dict]:
    """The hips' height changed with the feet kept where they are (P3): per frame the Hips raised by lift_m (a
    constant: + straightens the legs, - bends them) less bob_m on the single-support frames (a raised cosine over each
    run with one foot down: the hips dip at mid-stance), each leg solved again on its own ankle and foot rotation
    (two_bone, the knee in its own plane, the toes following the foot); then the whole body raised by flight_m on
    the frames with both feet down or both up (a raised cosine over each run): the handover turned into a short
    flight, both feet off the floor. Returns (the clip, the report: the asked values, the hips' height range before
    and after, mm, and the frames with neither foot within 1 cm of its lowest before and after)."""
    skel = prepare(skel)
    T = frames(clip)
    down = _down_masks(skel, clip)
    single = [down["Left"][f] != down["Right"][f] for f in range(T)]
    dip = _bump(single)
    hand = _bump([not s for s in single])
    out = copy_clip(clip)
    for f in range(T + 1):
        P = fk(skel, clip, f)
        dz = lift_m - bob_m * dip[f % T]
        new = dict(P)
        new["Hips"] = M.mat_mul([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, dz], [0, 0, 0, 1]], P["Hips"])
        for side in SIDES:
            u, lo, ft = (f"{side}{x}" for x in LEG)
            H, K, A = pos(P[u]), pos(P[lo]), pos(P[ft])
            H2 = (H[0], H[1], H[2] + dz)
            K2 = two_bone(H, K, A, H2)
            du = rot_between(M._v_sub(K, H), M._v_sub(K2, H2))
            dl = rot_between(M.q_rotate(du, M._v_sub(A, K)), M._v_sub(A, K2))
            new[u] = m4(H2, M.q_mul(du, mat_q(P[u])))
            new[lo] = m4(K2, M.q_mul(dl, M.q_mul(du, mat_q(P[lo]))))
            new[ft] = m4(A, mat_q(P[ft]))
        if flight_m:
            rise = flight_m * hand[f % T]
            new["Hips"] = M.mat_mul([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, rise], [0, 0, 0, 1]], new["Hips"])
            for side in SIDES:
                for b in (f"{side}{x}" for x in LEG):
                    new[b] = M.mat_mul([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, rise], [0, 0, 0, 1]], new[b])
        for b in ["Hips"] + [f"{s}{x}" for s in SIDES for x in LEG]:
            out["loc"][b][f], q = basis_of(skel, new, b)
            out["rot"][b][f] = M.q_hemi(q, out["rot"][b][f])
    hz0 = [p[2] for p in tracks(skel, clip, ["Hips"])["Hips"][:-1]]
    hz1 = [p[2] for p in tracks(skel, out, ["Hips"])["Hips"][:-1]]
    return out, {"lift_m": lift_m, "bob_m": bob_m, "flight_m": flight_m,
                 "hips_bob_mm": [round((max(hz0) - min(hz0)) * 1000.0, 1), round((max(hz1) - min(hz1)) * 1000.0, 1)],
                 "airborne": [airborne_frames(skel, clip), airborne_frames(skel, out)]}


def _honest_down(skel: dict, clip: dict, ground=None, height: float = HONEST_HEIGHT_M,
                 speed: float = HONEST_SPEED_M_S) -> tuple[dict, dict, tuple]:
    """honest_slide's planted frames per foot point (within `height` of its lowest, under `speed` m/s against the
    ground, frames 0..T-1): (masks by point, tracks by point 0..T, the ground's step per frame)."""
    skel = prepare(skel)
    T = frames(clip)
    fps = float(clip["fps"])
    if ground is None:
        ground = measure(skel, clip)["ground_m_s"]
    step = (ground[0] / fps, ground[1] / fps)
    tr = tracks(skel, clip, [p for s in SIDES for p in _foot_points(s)])
    masks = {}
    for p, v in tr.items():
        t = v[:-1]
        lowest = min(q[2] for q in t)
        masks[p] = [t[i][2] <= lowest + height and math.hypot(t[(i + 1) % T][0] - t[(i - 1) % T][0] - 2 * step[0],
                                                               t[(i + 1) % T][1] - t[(i - 1) % T][1] - 2 * step[1])
                    * fps / 2.0 <= speed for i in range(T)]
    return masks, tr, step


def airborne_frames(skel: dict, clip: dict) -> int:
    """The frames of the loop with neither foot planted (no ankle or toe down by honest_slide's test): a run's
    flight."""
    masks, _, _ = _honest_down(skel, clip)
    return sum(not any(m[f] for m in masks.values()) for f in range(frames(clip)))


def _pin_run(run: list[int], masks: dict, tr: dict, step: tuple, pa: str, pt: str) -> dict:
    """pin_feet's correction (x, y) per frame of one contact run: the point that is down (the ankle pa first, else
    the toe pt) held where it started, carried by the ground's `step` per frame. A point that becomes the anchor
    starts at its own place on the run's first frame, else at its place moved by the previous frame's correction, so
    the correction is continuous when the anchor switches (P5: it fell to 0 there, ~21 mm in one frame)."""
    out: dict[int, tuple[float, float]] = {}
    anchor, k0, q0 = None, 0, (0.0, 0.0)
    for k, f in enumerate(run):
        pnt = pa if masks[pa][f] else pt
        q = tr[pnt][f]
        if pnt != anchor:
            cp = out[run[k - 1]] if k else (0.0, 0.0)
            anchor, k0, q0 = pnt, k, (q[0] + cp[0], q[1] + cp[1])
        out[f] = (q0[0] + (k - k0) * step[0] - q[0], q0[1] + (k - k0) * step[1] - q[1])
    return out


def pin_feet(skel: dict, clip: dict, passes: int = 2, decay: int = 2) -> tuple[dict, dict]:
    """The planted feet pinned to the ground by honest_slide's own test (P3: the backpedal's left foot drifted 21 mm
    after the stride, whose contact test differs): per foot, over each cyclic run of frames with its ankle or toe
    down, the ankle moved so the point that is down (the ankle first, else the toe) stays where it was on its first
    down frame of the run, carried by the ground (_pin_run: an anchor switch inside a run keeps the correction
    continuous); the correction fades out over `decay` frames after the run; the leg solved
    again (two_bone, the foot's world rotation kept). Returns (the clip, the honest drift before and after)."""
    skel = prepare(skel)
    T = frames(clip)
    before = honest_slide(skel, clip)
    out = clip
    for _ in range(passes):
        masks, tr, step = _honest_down(skel, out)
        corr, hold = {}, {}
        for side in SIDES:
            pa, pt = _foot_points(side)
            down = [masks[pa][f] or masks[pt][f] for f in range(T)]
            c = [None] * T
            h = [None] * T  # (the held foot rotation, weight): flat on the ground while its heel and toe are both down
            for run in M.contact_windows([masks[pa][f] and masks[pt][f] for f in range(T)], cyclic=True):
                q0 = mat_q(fk(skel, out, run[0])[f"{side}{LEG[2]}"])
                for f in run:
                    h[f] = (q0, 1.0)
                for d in range(1, decay + 1):
                    g = (run[-1] + d) % T
                    if h[g] is None:
                        h[g] = (q0, 1.0 - d / (decay + 1.0))
            hold[side] = h
            for run in M.contact_windows(down, cyclic=True):
                for f, x in _pin_run(run, masks, tr, step, pa, pt).items():
                    c[f] = x
                last = c[run[-1]]
                for d in range(1, decay + 1):
                    g = (run[-1] + d) % T
                    if c[g] is None and not down[g]:
                        w = 1.0 - d / (decay + 1.0)
                        c[g] = (last[0] * w, last[1] * w)
            corr[side] = [x or (0.0, 0.0) for x in c]
        held = copy_clip(out)  # first the held foot rotations (about the ankle), then the ankles moved
        for f in range(T + 1):
            P = fk(skel, out, f)
            new = dict(P)
            for side in SIDES:
                ft = f"{side}{LEG[2]}"
                if hold[side][f % T] is not None:
                    q0, w = hold[side][f % T]
                    q = mat_q(P[ft])
                    new[ft] = m4(pos(P[ft]), M.q_slerp(q, M.q_hemi(q0, q), w))
                    held["rot"][ft][f] = M.q_hemi(basis_of(skel, new, ft)[1], out["rot"][ft][f])
        out = held
        masks, tr, step = _honest_down(skel, out)
        for side in SIDES:  # the corrections again on the held feet
            pa, pt = _foot_points(side)
            for run in M.contact_windows([masks[pa][f] or masks[pt][f] for f in range(T)], cyclic=True):
                for f, x in _pin_run(run, masks, tr, step, pa, pt).items():
                    corr[side][f] = x
        new_clip = copy_clip(out)
        for f in range(T + 1):
            P = fk(skel, out, f)
            new = dict(P)
            for side in SIDES:
                u, lo, ft = (f"{side}{x}" for x in LEG)
                H, K, A = pos(P[u]), pos(P[lo]), pos(P[ft])
                cx, cy = corr[side][f % T]
                goal = (A[0] + cx, A[1] + cy, A[2])
                delta = M._v_sub(goal, A)
                K2 = M._v_add(two_bone(H, K, A, M._v_sub(H, delta)), delta)
                du = rot_between(M._v_sub(K, H), M._v_sub(K2, H))
                dl = rot_between(M.q_rotate(du, M._v_sub(A, K)), M._v_sub(goal, K2))
                new[u] = m4(H, M.q_mul(du, mat_q(P[u])))
                new[lo] = m4(K2, M.q_mul(dl, M.q_mul(du, mat_q(P[lo]))))
                new[ft] = m4(goal, mat_q(P[ft]))
                for b in (u, lo, ft):
                    new_clip["loc"][b][f], q = basis_of(skel, new, b)
                    new_clip["rot"][b][f] = M.q_hemi(q, out["rot"][b][f])
        out = new_clip
    after = honest_slide(skel, out)
    return out, {"drift_mm": {s: [before[s]["drift_mm"], after[s]["drift_mm"]] for s in SIDES}}


def arms_in(skel: dict, clip: dict, deg: float) -> dict:
    """Each upper arm turned `deg` toward the body (negative: away) about the chest's front axis through its shoulder
    joint, every frame; the forearm and hand follow. A flaring elbow brought in (the side runs, P3). Returns the clip."""
    skel = prepare(skel)
    out = copy_clip(clip)
    for f in range(frames(clip) + 1):
        P = fk(skel, clip, f)
        front = bone_front(skel, P, "UpperChest")
        new = dict(P)
        for side, sign in (("Left", -1.0), ("Right", 1.0)):  # the left arm (+X) comes in turning about -front
            b = f"{side}UpperArm"
            new[b] = m4(pos(P[b]), M.q_mul(M.q_axis_angle(front, sign * deg), mat_q(P[b])))
            out["rot"][b][f] = M.q_hemi(basis_of(skel, new, b)[1], clip["rot"][b][f])
    return out


def leg_spacing(skel: dict, clip: dict) -> dict:
    """The legs' room (m), least over the loop: the ankles' and the knees' signed distance along the hips' left-right
    axis (left joint minus right; negative: the legs cross), and the ankles' distance across the travel on the frames
    they pass each other (along the travel within 0.10 m)."""
    skel = prepare(skel)
    T = frames(clip)
    m = measure(skel, clip)
    g = m["ground_m_s"]
    n = math.hypot(*g) or 1.0
    d = (-g[0] / n, -g[1] / n)  # the travel (the ground runs back under the feet)
    tr = tracks(skel, clip, [f"{s}{x}" for s in SIDES for x in LEG])
    ank = knee = math.inf
    passing = []
    for f in range(T):
        lr = M._v_sub(tr["LeftUpperLeg"][f], tr["RightUpperLeg"][f])
        ln = math.hypot(lr[0], lr[1]) or 1.0
        ax = (lr[0] / ln, lr[1] / ln)
        da = M._v_sub(tr["LeftFoot"][f], tr["RightFoot"][f])
        dk = M._v_sub(tr["LeftLowerLeg"][f], tr["RightLowerLeg"][f])
        ank = min(ank, da[0] * ax[0] + da[1] * ax[1])
        knee = min(knee, dk[0] * ax[0] + dk[1] * ax[1])
        if abs(da[0] * d[0] + da[1] * d[1]) < 0.10:
            passing.append(abs(da[0] * -d[1] + da[1] * d[0]))
    return {"ankle_min_m": round(ank, 3), "knee_min_m": round(knee, 3),
            "pass_lateral_m": round(min(passing), 3) if passing else None}


def elbow_bend(skel: dict, clip: dict) -> dict:
    """Per arm the elbow's bend (degrees between the upper arm and the forearm; 0 straight): mean, least, most."""
    skel = prepare(skel)
    T = frames(clip)
    tr = tracks(skel, clip, [f"{s}{x}" for s in SIDES for x in ARM])
    out = {}
    for s in SIDES:
        b = [_angle(M._v_sub(tr[f"{s}LowerArm"][f], tr[f"{s}UpperArm"][f]),
                    M._v_sub(tr[f"{s}Hand"][f], tr[f"{s}LowerArm"][f])) for f in range(T)]
        out[s] = [round(sum(b) / T, 1), round(min(b), 1), round(max(b), 1)]
    return out


# ------------------------------------------------------------------------------------------- P4: the backpedal
def even_steps(skel: dict, clip: dict, foot: str = "Left") -> tuple[dict, dict]:
    """A loop starting on `foot`'s contact retimed so the other foot's contact starts half a cycle on (P4: the
    backpedal take's steps were 6 and 8 of 14 frames): each frame u samples the clip at u - a sin^2(pi u / T), with
    a = T/2 - (the other contact's start), a smooth monotonic warp (|a| < T / pi) that keeps frames 0 and T, on the
    same frame grid (Catmull-Rom over the seam, as `retime`). Returns (the clip, the report: the other foot's contact
    starts before and after, frames of T)."""
    T = frames(clip)
    other = "Right" if foot == "Left" else "Left"
    before = measure(skel, clip)["contacts"][other]
    start = min(before, key=lambda s: abs(s - T / 2.0)) if before else T / 2.0
    a = T / 2.0 - start
    if abs(a) >= T / math.pi:
        raise ValueError(f"even_steps: the other contact at {start} of {T} is too far from half to warp smoothly")
    out = copy_clip(clip, loc={}, rot={})
    for u in range(T):
        t = (u - a * math.sin(math.pi * u / T) ** 2) % T
        i, fr = M.split_index(t, T)
        idx = M.neighbours(i, T, closed=True)
        w = M.catmull_rom(fr)
        for b, v in clip["loc"].items():
            out["loc"].setdefault(b, []).append(tuple(sum(wk * v[k][c] for wk, k in zip(w, idx)) for c in range(3)))
        for b, v in clip["rot"].items():
            qs = [M.q_hemi(v[k], v[i]) for k in idx]
            out["rot"].setdefault(b, []).append(M.q_norm(tuple(sum(wk * q[c] for wk, q in zip(w, qs))
                                                               for c in range(4))))
    for ch in (out["loc"], out["rot"]):
        for b in ch:
            ch[b].append(ch[b][0])
    return out, {"other": other, "start_before": before, "start_after": measure(skel, out)["contacts"][other],
                 "frames": T}


def _norm(v):
    n = _len(v)
    return tuple(c / n for c in v) if n > 1e-12 else v


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _body_axes(skel: dict, P: dict):
    """(front, left, up) of the trunk on one pose: the UpperChest's front laid level, world up, left = up x front."""
    fr = bone_front(skel, P, "UpperChest")
    front = _norm((fr[0], fr[1], 0.0))
    up = (0.0, 0.0, 1.0)
    return front, _cross(up, front), up


def arms_carry(skel: dict, clip: dict, side_m: float = 0.17, front_m: float = 0.14, dz_m: float = 0.0,
               swing_m: float = 0.06, rise: float = 0.35, out_deg: float = 15.0) -> tuple[dict, dict]:
    """A running carriage for the arms (P4, the backpedal): each wrist (the Hand bone's head) put on a target in the
    trunk's own frame and the arm solved again as two bones (its own upper arm and forearm lengths). The target: the
    Spine's head (the waist) + side_m outward + front_m forward + dz_m up, swung +-swing_m forward (and rise times
    that up) against the same-side ankle's fore-aft place under the hips (the hand forward while its leg is back);
    the elbow in the plane through the shoulder, the wrist and a pole pointing back and out_deg outward (elbows near
    the ribs, behind the trunk). The hand keeps its pose on the forearm. Returns (the clip, the report: the asked
    values and `arm_carriage`'s numbers)."""
    skel = prepare(skel)
    T = frames(clip)
    P0 = fk(skel, clip, 0)
    lens = {s: (_len(M._v_sub(pos(P0[f"{s}LowerArm"]), pos(P0[f"{s}UpperArm"]))),
                _len(M._v_sub(pos(P0[f"{s}Hand"]), pos(P0[f"{s}LowerArm"])))) for s in SIDES}
    # the swing's phase: each ankle's place along the trunk's front relative to the hips, scaled to -1..1
    lead = {s: [] for s in SIDES}
    for f in range(T):
        P = fk(skel, clip, f)
        front = _body_axes(skel, P)[0]
        for s in SIDES:
            lead[s].append(M._v_dot(M._v_sub(pos(P[f"{s}Foot"]), pos(P["Hips"])), front))
    for s in SIDES:
        m = sum(lead[s]) / T
        amp = max(abs(x - m) for x in lead[s]) or 1.0
        lead[s] = [(x - m) / amp for x in lead[s]]
    out = copy_clip(clip)
    o = math.radians(out_deg)
    for f in range(T + 1):
        P = fk(skel, clip, f)
        front, left, up = _body_axes(skel, P)
        waist = pos(P["Spine"])
        new = dict(P)
        for s, sign in (("Left", 1.0), ("Right", -1.0)):
            ua, la, hd = (f"{s}{x}" for x in ARM)
            S0, E0, W0 = pos(P[ua]), pos(P[la]), pos(P[hd])
            sw = -swing_m * lead[s][f % T]
            W = tuple(waist[c] + sign * side_m * left[c] + (front_m + sw) * front[c] + (dz_m + rise * sw) * up[c]
                      for c in range(3))
            a, b = lens[s]
            v = M._v_sub(W, S0)
            d = min(max(_len(v), abs(a - b) + 1e-4), a + b - 1e-4)
            u = _norm(v)
            W = M._v_add(S0, tuple(c * d for c in u))
            pole = tuple(-front[c] * math.cos(o) + sign * left[c] * math.sin(o) for c in range(3))
            p = _norm(M._v_sub(pole, tuple(c * M._v_dot(pole, u) for c in u)))
            x = (a * a - b * b + d * d) / (2.0 * d)
            h = math.sqrt(max(a * a - x * x, 0.0))
            E = tuple(S0[c] + x * u[c] + h * p[c] for c in range(3))
            du = rot_between(M._v_sub(E0, S0), M._v_sub(E, S0))
            dl = rot_between(M.q_rotate(du, M._v_sub(W0, E0)), M._v_sub(W, E))
            new[ua] = m4(S0, M.q_mul(du, mat_q(P[ua])))
            new[la] = m4(E, M.q_mul(dl, M.q_mul(du, mat_q(P[la]))))
            new[hd] = m4(W, M.q_mul(dl, M.q_mul(du, mat_q(P[hd]))))
        for b in (f"{s}{x}" for s in SIDES for x in ARM):
            loc, q = basis_of(skel, new, b)
            if b in out["loc"]:
                out["loc"][b][f] = loc
            out["rot"][b][f] = M.q_hemi(q, clip["rot"][b][f])
    return out, {"side_m": side_m, "front_m": front_m, "dz_m": dz_m, "swing_m": swing_m, "rise": rise,
                 "out_deg": out_deg, **arm_carriage(skel, out)}


def arm_carriage(skel: dict, clip: dict) -> dict:
    """The arms' carriage numbers (P4), per side: the elbow bend (mean, least, most), the hand's least distance from
    the torso axis (`hand_clearance`), its least distance outward from the trunk's midline plane (negative: it
    crossed), the wrist's height over the waist (the Spine's head; least, most) and its place in front of it (least,
    most), the elbow's least distance from the torso axis, m."""
    skel = prepare(skel)
    T = frames(clip)
    hands = hand_clearance(skel, clip)
    elbows = elbow_bend(skel, clip)
    out = {}
    for s, sign in (("Left", 1.0), ("Right", -1.0)):
        mid, hz, hf, el = [], [], [], []
        for f in range(T):
            P = fk(skel, clip, f)
            front, left, up = _body_axes(skel, P)
            waist, W, E = pos(P["Spine"]), pos(P[f"{s}Hand"]), pos(P[f"{s}LowerArm"])
            r = M._v_sub(W, waist)
            mid.append(sign * M._v_dot(r, left))
            hz.append(M._v_dot(r, up))
            hf.append(M._v_dot(r, front))
            a, b = pos(P["Hips"]), pos(P["Neck"])
            ab = M._v_sub(b, a)
            t = max(0.0, min(1.0, M._v_dot(M._v_sub(E, a), ab) / max(M._v_dot(ab, ab), 1e-12)))
            el.append(_len(M._v_sub(E, M._v_add(a, tuple(c * t for c in ab)))))
        out[s] = {"elbow_deg": elbows[s], "hand_axis_m": hands[s], "midline_m": round(min(mid), 3),
                  "wrist_dz_m": [round(min(hz), 3), round(max(hz), 3)],
                  "wrist_front_m": [round(min(hf), 3), round(max(hf), 3)], "elbow_axis_m": round(min(el), 3)}
    return out
