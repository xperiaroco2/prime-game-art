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
           blend: int = 2) -> tuple[dict, dict]:
    """A loop's cadence and stride length changed with its feet kept planted:
    1. retimed to `cadence` steps/s (or by `rate`; neither: unchanged);
    2. the stride scaled by `scale`, or by anim_edit_math's stride_scale so the loop covers `speed` m/s at rate 1
       (neither: 1): the hips' travel along the ground axis (a root-motion clip's) and each ankle's offset from the
       hips along it (scale_offset), each ankle's contact windows then laid on a straight line at the new ground
       velocity (plant);
    3. each leg solved again per frame (two_bone: the hip kept, the knee in the clip's own knee plane), the foot keeping
       its world rotation, the toes following it.
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
        for f in range(T + 1):
            P = posed[f]
            H, K, A = pos(P[u]), pos(P[lo]), pos(P[ft])
            goal = (flat[f][0], flat[f][1], A[2])
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
        miss = max(math.hypot(a[0] - p[0], a[1] - p[1]) for a, p in zip(after, flat)) * 1000.0
        report["ankle_miss_mm"] = round(max(report["ankle_miss_mm"], miss), 3)
    report["after"] = measure(skel, out, window)
    report["planted_slide_mm"] = max(report["after"]["foot_slide_mm"].values())
    return out, report


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
