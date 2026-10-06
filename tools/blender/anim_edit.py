"""Clip edits on our rig after the retarget (art #33; docs/animations.md, "Clip edits"): cut a loop at its best seam
and close it, take the travel out, straighten the heading, rescale a turn, trim, retime, reverse, mirror left and
right, warp the stride to a speed with the feet planted, lift a clip out of the floor, turn the arms out of the legs
and the hands apart.
One tool set serves the pack's clips and every retargeted library (UAL1, UAL2, Meshy text to motion), since it works on
the Ultimate Modular rig after the retarget.

A clip is a Frames object: one basis matrix per bone and frame on the 30 fps grid, sampled from any sampler
(rc.Sampler, anim_libs.InPlace, a layered sampler) and baked back with rc.bake. apply(frames, steps, target, body)
runs a settings file's edit steps (checked by anim_edit_math.check_steps) and reports each one in info["steps"].

Rig facts the edits rely on (the pack original after rc.add_toes, 64 bones): Root is the top bone and carries Body
(legs and spine), the IK feet Foot.L/R and the knee poles PT.L/R, so moving the whole character is a change of Root's
pose; a foot is an IK target in Root space, and moving it means re-solving UpperLeg and LowerLeg (children of Body)
with the two-bone IK; the toes are children of the feet. The armature has a world scale of 100 and its RootNode a -90
degree turn about X: world and armature space are always converted through rig.W and rig.Wi. Background Blender only.
"""

from __future__ import annotations

import copy
import math

import bpy
from mathutils import Matrix, Quaternion, Vector
from mathutils.kdtree import KDTree

import anim_edit_math as em
import anim_math as am
import anim_metrics
import retarget_core as rc

FINGERS = ("Index", "Middle", "Ring", "Pinky", "Thumb")
LEGS = [("UpperLeg.L", "LowerLeg.L", "Foot.L"), ("UpperLeg.R", "LowerLeg.R", "Foot.R")]
BODY = "Body"
CHEST = "Chest"
POS_UNIT = 0.2  # metres that count like one radian in the cycle's pose distance
VEL_FRAMES = 3.0  # the cycle's velocity term: the change over this many frames (0.1 s)
MOVING_M = 1e-4  # a bone whose basis location stays within this (m) never moves: it is kept at its rest offset


class EditError(Exception):
    """An edit step that cannot be done: an unknown op, a bad parameter, a cycle cut whose raw seam exceeds its limit,
    a stride on a clip without foot contacts."""


def is_finger(name: str) -> bool:
    return name.startswith(FINGERS)


# ------------------------------------------------------------------------------------------------------ frames
class Frames:
    """A clip on our rig: `basis` holds one {bone: basis Matrix} per frame (every bone of the rig) at `fps` (30);
    `loop` says whether it is a closed loop (its last frame equals its first); `info` carries the step reports
    (info["steps"]) and the latest measured speed and travel (info["speed_m_s"], info["travel_m"])."""

    def __init__(self, rig: rc.Rig, basis: list, fps: float = rc.FPS, loop: bool = False, info: dict | None = None):
        self.rig, self.basis, self.fps, self.loop = rig, basis, fps, loop
        self.info = copy.deepcopy(info) if info else {}
        self.info.setdefault("steps", [])

    @classmethod
    def from_sampler(cls, sampler, rig: rc.Rig, loop: bool) -> "Frames":
        """Samples frames start + i, i = 0..round(frames), so 24 fps keys land on the 30 fps grid; bones the sampler
        does not key get the identity."""
        n = int(round(sampler.frames))
        ident = Matrix.Identity(4)
        basis = []
        for i in range(n + 1):
            b = sampler.basis(sampler.start + i)
            basis.append({name: b.get(name, ident).copy() for name in rig.order})
        return cls(rig, basis, rc.FPS, loop)

    @classmethod
    def from_action(cls, action, rig: rc.Rig, loop: bool) -> "Frames":
        return cls.from_sampler(rc.Sampler(action), rig, loop)

    @property
    def frames(self) -> int:
        """The number of frame intervals (the last frame's index)."""
        return len(self.basis) - 1

    @property
    def seconds(self) -> float:
        return self.frames / self.fps

    def poses(self) -> list[dict]:
        """Armature-space pose matrices per frame (rc.fk)."""
        return [rc.fk(self.rig, b) for b in self.basis]

    def to_action(self, arm, name: str):
        """A new action with one key per frame from frame 0 (rc.bake)."""
        return rc.bake(arm, name, self.basis, 0.0)

    def copy(self, basis: list | None = None, loop: bool | None = None) -> "Frames":
        if basis is None:
            basis = [{n: m.copy() for n, m in b.items()} for b in self.basis]
        return Frames(self.rig, basis, self.fps, self.loop if loop is None else loop, self.info)


class Target:
    """The character the edits measure on (the donor the clips play on): char is an rc.load_glb dict with the toe
    bones added. `measure` is an anim_metrics.Measure built on first use, in the rest pose."""

    def __init__(self, char: dict):
        self.char, self.arm = char, char["arm"]
        self.rig = rc.Rig(self.arm)
        self.legs = list(LEGS)
        self.upper = "Torso"
        self._measure = None

    @property
    def measure(self) -> anim_metrics.Measure:
        if self._measure is None:
            rc.reset_pose(self.arm)
            bpy.context.view_layer.update()
            self._measure = anim_metrics.Measure(self.char)
        return self._measure

    def pose(self, basis: dict) -> None:
        rc.apply_basis(self.arm, basis)
        bpy.context.view_layer.update()

    def points(self, meshes=None) -> dict:
        """The posed meshes' world vertices by object name."""
        return {o.name: anim_metrics.world_points(o) for o in (meshes or self.char["meshes"].values())}

    def lowest(self) -> float:
        return min(float(p[:, 2].min()) for p in self.points().values())

    def upper_bones(self) -> list[str]:
        """The upper-body layer's bone filter: `upper` and every bone below it."""
        top = self.arm.data.bones[self.upper]
        return [top.name] + [b.name for b in top.children_recursive]


# ----------------------------------------------------------------------------------------------- helpers
def _resample(fr: Frames, times: list[float]) -> list[dict]:
    """Basis frames at fractional frame indices, by a Catmull-Rom spline through the neighbouring frames (wrapped
    over a closed loop's seam): locations and scales per component, rotations on the quaternion components aligned
    to one hemisphere and normalised (between two frames this is a smoothed slerp)."""
    dec = [{n: m.decompose() for n, m in b.items()} for b in fr.basis]
    last = fr.frames
    out = []
    for t in times:
        i, f = em.split_index(t, last)
        if f < 1e-9 or f > 1 - 1e-9:
            k = i if f < 0.5 else min(i + 1, last)
            out.append({n: Matrix.LocRotScale(*d) for n, d in dec[k].items()})
            continue
        w = em.catmull_rom(f)
        idx = em.neighbours(i, last, fr.loop)
        frame = {}
        for n, (l1, q1, s1) in dec[i].items():
            loc, q, sc = Vector(), Quaternion((0.0, 0.0, 0.0, 0.0)), Vector()
            for wk, k in zip(w, idx):
                lk, qk, sk = dec[k][n]
                if qk.dot(q1) < 0:
                    qk = -qk
                loc += lk * wk
                sc += sk * wk
                q = Quaternion([a + b * wk for a, b in zip(q, qk)])
            frame[n] = Matrix.LocRotScale(loc, q.normalized(), sc)
        out.append(frame)
    return out


def _close(fr: Frames) -> None:
    """Makes a loop's last frame exactly its first."""
    if fr.loop and len(fr.basis) > 1:
        fr.basis[-1] = {n: m.copy() for n, m in fr.basis[0].items()}


def _tops(rig: rc.Rig) -> list[str]:
    return [n for n in rig.order if rig.parent[n] is None]


def _move_world(fr: Frames, xforms: list) -> None:
    """Moves the whole character of each frame by a world transform (None: unchanged), through the top bone (Root)."""
    rig = fr.rig
    for B, X in zip(fr.basis, xforms):
        if X is None:
            continue
        M = rig.Wi @ X @ rig.W
        for top in _tops(rig):
            B[top] = rig.rest_rel[top].inverted() @ (M @ (rig.rest_rel[top] @ B[top]))


def _about_z(point_xy, degrees: float) -> Matrix:
    """A world rotation about the vertical through a point."""
    c = Matrix.Translation((point_xy[0], point_xy[1], 0.0))
    return c @ Matrix.Rotation(math.radians(degrees), 4, "Z") @ c.inverted()


def _world(rig: rc.Rig, P: dict, bone: str) -> Vector:
    return rig.W @ P[bone].translation


def _xy(v) -> tuple[float, float]:
    return (float(v[0]), float(v[1]))


def _turn_of(rig: rc.Rig, P: dict, bone: str) -> Quaternion:
    """A bone's world rotation relative to its rest (posed = turn @ rest, in world space)."""
    return rc.rot(rig.W @ P[bone]) @ rc.rot(rig.W @ rig.rest[bone]).inverted()


def _facing(rig: rc.Rig, P: dict) -> float:
    R = _turn_of(rig, P, BODY)
    return em.facing_yaw(tuple(R @ Vector((0.0, -1.0, 0.0))), tuple(R @ Vector((1.0, 0.0, 0.0))))


def _body_path(fr: Frames, poses=None) -> list[tuple[float, float]]:
    return [_xy(_world(fr.rig, P, BODY)) for P in (poses or fr.poses())]


def _yaws(fr: Frames, poses=None) -> list[float]:
    return em.unwrap([_facing(fr.rig, P) for P in (poses or fr.poses())])


def _feet(fr: Frames, poses=None) -> dict:
    return {foot: [tuple(_world(fr.rig, P, foot)) for P in (poses or fr.poses())] for _, _, foot in LEGS}


def _set_pose(rig: rc.Rig, B: dict, P: dict, bone: str, pose: Matrix) -> None:
    """Gives one bone a new armature-space pose by recomputing only its basis (the bones below follow it)."""
    parent = rig.parent[bone]
    par = P[parent] if parent else Matrix.Identity(4)
    B[bone] = rig.rest_rel[bone].inverted() @ par.inverted() @ pose
    P[bone] = pose


class _Legs:
    """The two-bone leg IK on a rig (as retarget_core.Retargeter._leg_ik): the knee keeps its current bend plane,
    with a small pull towards the character's front for a nearly straight leg; the foot keeps its rotation and goes
    to the shin's end."""

    def __init__(self, rig: rc.Rig):
        self.rig = rig
        fwd = rig.Wi.to_3x3().normalized() @ Vector((0.0, -1.0, 0.0))
        self.knee_fwd = {up: rc.rot(rig.rest[up]).inverted() @ fwd for up, _, _ in LEGS}
        self.shin_end = {lo: rig.rest[lo].inverted() @ rig.rest[ft] for _, lo, ft in LEGS}
        self.hinge = {up: rc.rot(rig.W @ rig.rest[up]).inverted() @ Vector((1.0, 0.0, 0.0)) for up, _, _ in LEGS}

    def solve(self, B: dict, P: dict, leg, goal: Vector) -> float:
        """Re-solves one leg of a frame (B basis, P poses, both updated) so its ankle reaches goal (armature space);
        returns the miss in metres."""
        up, lo, ft = leg
        rig = self.rig
        H, K = P[up].translation.copy(), P[lo].translation.copy()
        A = (P[lo] @ self.shin_end[lo]).translation
        knee = K - H
        dv = goal - H
        u = dv.normalized() if dv.length > 1e-12 else (A - H).normalized()
        # the bend direction is the knee's offset from the leg's current hip-ankle line (not from the line to the
        # goal: a goal far from the ankle would turn a straight leg's knee backwards)
        u0 = (A - H).normalized()
        pole = (knee - u0 * knee.dot(u0)) / max(knee.length, 1e-12)
        f = rc.rot(P[up]) @ self.knee_fwd[up]
        pole += (f - u * f.dot(u)) * 0.05
        K2, A2, miss = em.two_bone_ik(tuple(H), tuple(K), tuple(A), tuple(goal), tuple(pole))
        K2, A2 = Vector(K2), Vector(A2)
        q1 = knee.rotation_difference(K2 - H)
        _set_pose(rig, B, P, up, Matrix.Translation(H) @ (q1 @ rc.rot(P[up])).to_matrix().to_4x4())
        q2 = (q1 @ (A - K)).rotation_difference(A2 - K2)
        _set_pose(rig, B, P, lo, Matrix.Translation(K2) @ (q2 @ q1 @ rc.rot(P[lo])).to_matrix().to_4x4())
        _set_pose(rig, B, P, ft, Matrix.Translation(A2) @ rc.rot(P[ft]).to_matrix().to_4x4())
        return miss * rig.scale

    def flexion(self, P: dict, leg) -> float:
        """The knee's signed flexion (degrees, positive = the normal bend), as anim_metrics measures it."""
        up, lo, _ = leg
        W = self.rig.W
        a, b = W @ P[up].translation, W @ P[lo].translation
        c = W @ (P[lo] @ self.shin_end[lo]).translation
        axis = rc.rot(W @ P[up]) @ self.hinge[up]
        return am.signed_angle(tuple(b - a), tuple(c - b), tuple(axis))


def _r(x, digits=2):
    return None if x is None else round(float(x), digits)


# ------------------------------------------------------------------------------------------------ the ops
def op_trim(fr: Frames, p: dict, target: Target):
    out = fr.copy(_resample(fr, em.trim_times(fr.frames, fr.fps, p["start_s"], p["end_s"])), loop=False)
    return out, {"frames": out.frames, "seconds": _r(out.seconds, 3)}


def _natural_speed(fr: Frames, given):
    """The clip's speed at 1.0x: the given natural_m_s; else the travel speed a cycle, in_place or stride step
    measured (the clip's own travel, exact); else the feet's in-place ground speed (anim_math.foot_sliding's rule)."""
    if given is not None:
        return given, "natural_m_s"
    if fr.info.get("speed_m_s"):
        return fr.info["speed_m_s"], fr.info.get("speed_from", "info")
    g = em.ground_velocity(em.contact_velocities(_feet(fr), fr.fps))
    if g is not None and math.hypot(*g) > 0.05:
        return math.hypot(*g), "feet"
    raise EditError("no natural speed: give natural_m_s (the clip neither travels nor walks on its feet)")


def op_retime(fr: Frames, p: dict, target: Target):
    rep = {}
    if p["seconds"] is not None:
        rate = fr.seconds / p["seconds"]
    elif p["rate"] is not None:
        rate = p["rate"]
    else:
        natural, how = _natural_speed(fr, p["natural_m_s"])
        rate = p["speed_m_s"] / natural
        rep.update(natural_m_s=_r(natural, 3), natural_from=how)
    m, eff = em.retime_count(fr.frames, rate)
    out = fr.copy(_resample(fr, em.retime_times(fr.frames, m)))
    _close(out)
    if out.info.get("speed_m_s"):
        out.info["speed_m_s"] *= eff
    rep.update(rate=_r(rate, 4), rate_eff=_r(eff, 4), seconds=_r(out.seconds, 3), frames=out.frames)
    return out, rep


def op_reverse(fr: Frames, p: dict, target: Target):
    return fr.copy([{n: m.copy() for n, m in b.items()} for b in reversed(fr.basis)]), {}


def _cycle_features(fr: Frames, poses: list) -> list:
    rig = fr.rig
    bones = [n for n in rig.order if not is_finger(n)]
    ref = {n: fr.basis[0][n].to_quaternion() for n in bones}
    feats = []
    for B, P in zip(fr.basis, poses):
        f = []
        for n in bones:
            q = B[n].to_quaternion()
            if q.dot(ref[n]) < 0:
                q = -q
            f.extend(2.0 * c for c in q)  # about radians for small differences
        body = _world(rig, P, BODY)
        f.append(body.z / POS_UNIT)
        for _, _, foot in LEGS:
            f.extend(c / POS_UNIT for c in (_world(rig, P, foot) - body))
        feats.append(f)
    return feats


def op_cycle(fr: Frames, p: dict, target: Target):
    rig = fr.rig
    poses = fr.poses()
    feats = _cycle_features(fr, poses)
    vels = [[c * VEL_FRAMES for c in v] for v in em.central_diff(feats)]
    i, j, cost = em.best_cycle(feats, vels, fr.fps, p["min_s"], p["max_s"], p["within"])
    seams = {n: am.quat_angle(tuple(fr.basis[i][n].to_quaternion()), tuple(fr.basis[j][n].to_quaternion()))
             for n in rig.order}
    # the guard reads the bones the cut is chosen on (the fingers are reported by themselves: a hand at work changes
    # its grip from one cycle to the next)
    worst = max((n for n in seams if not is_finger(n)), key=seams.get)
    raw = seams[worst]
    rep = {"i_s": _r(i / fr.fps, 3), "j_s": _r(j / fr.fps, 3), "cycle_s": _r((j - i) / fr.fps, 3),
           "raw_seam_deg": _r(raw, 1), "raw_seam_bone": worst,
           "finger_seam_deg": _r(max([a for n, a in seams.items() if is_finger(n)] or [0.0]), 1), "cost": _r(cost, 3)}
    if raw > p["max_raw_seam_deg"]:
        raise EditError(f"the best cut {rep['i_s']}-{rep['j_s']} s has a raw seam of {raw:.1f} degrees ({worst}), "
                        f"over max_raw_seam_deg {p['max_raw_seam_deg']}: closing it would hide a bad cut")
    b0, b1 = _world(rig, poses[i], BODY), _world(rig, poses[j], BODY)
    travel = math.hypot(b1.x - b0.x, b1.y - b0.y)
    yaw_drift = em.wrap(_facing(rig, poses[j]) - _facing(rig, poses[i]))
    T = j - i
    dec = [{n: m.decompose() for n, m in fr.basis[k].items()} for k in range(i, j + 1)]
    out = [{} for _ in dec]
    for n in rig.order:
        l0, q0, s0 = dec[0][n]
        lT, qT, sT = dec[-1][n]
        delta = qT.inverted() @ q0
        if delta.w < 0:
            delta.negate()
        for k, d in enumerate(dec):
            w = k / T
            l, q, s = d[n]
            out[k][n] = Matrix.LocRotScale(l + (l0 - lT) * w, q @ Quaternion().slerp(delta, w), s + (s0 - sT) * w)
    res = fr.copy(out, loop=True)
    _close(res)
    res.info.update(speed_m_s=travel / (T / fr.fps), travel_m=travel, speed_from="cycle")
    rep.update(travel_m=_r(travel, 3), speed_m_s=_r(travel / (T / fr.fps), 3), yaw_drift_deg=_r(yaw_drift, 1),
               frames=res.frames)
    return res, rep


def op_in_place(fr: Frames, p: dict, target: Target):
    path = _body_path(fr)
    travel = math.dist(path[0], path[-1])
    if p["mode"] == "linear":
        offs = em.linear_drift(path)
        speed = travel / fr.seconds if fr.seconds > 0 else 0.0
    else:
        offs = em.path_offsets(path, fr.fps, p["smooth_s"])
        half = max(1, round(p["smooth_s"] * fr.fps / 2))
        speed = em.moving_speed(em.moving_average(path, half, odd=True), fr.fps)
    out = fr.copy()
    _move_world(out, [Matrix.Translation((-o[0], -o[1], 0.0)) for o in offs])
    _close(out)
    after = _body_path(out)
    out.info.update(speed_m_s=speed, travel_m=travel, speed_from=f"in_place {p['mode']}")
    return out, {"mode": p["mode"], "travel_m": _r(travel, 3), "speed_m_s": _r(speed, 3),
                 "max_offset_m": _r(max(math.hypot(*o) for o in offs), 3),
                 "travel_after_m": _r(math.dist(after[0], after[-1]), 3)}


def _heading_numbers(fr: Frames) -> dict:
    poses = fr.poses()
    path = _body_path(fr, poses)
    times = [k / fr.fps for k in range(len(path))]
    d, speed = em.lsq_direction(path, times)
    facing = em.circular_mean(_yaws(fr, poses))
    moving = speed * fr.seconds > 0.02
    travel_dir = em.yaw_of(d) if moving else None
    return {"travel_dir_deg": _r(travel_dir, 1), "facing_mean_deg": _r(facing, 1),
            "crab_deg": _r(em.wrap(facing - travel_dir), 1) if moving else None, "path": path, "yaw_dir": d,
            "moving": moving}


def op_heading(fr: Frames, p: dict, target: Target):
    before = _heading_numbers(fr)
    if p["travel"] is not None:
        if not before["moving"]:
            raise EditError("heading by travel: the clip does not travel (under 2 cm)")
        theta = em.wrap(em.TRAVEL_YAW[p["travel"]] - em.yaw_of(before["yaw_dir"]))
    else:
        yaws = _yaws(fr)
        val = {"start": yaws[0], "end": yaws[-1], "mean": em.circular_mean(yaws)}[p["facing"]]
        theta = em.wrap(-val)
    out = fr.copy()
    X = _about_z(before["path"][0], theta)
    _move_world(out, [X] * len(out.basis))
    after = _heading_numbers(out)
    rep = {"turned_deg": _r(theta, 1), "travel_dir_deg_before": before["travel_dir_deg"]}
    rep.update({k: after[k] for k in ("travel_dir_deg", "facing_mean_deg", "crab_deg")})
    return out, rep


def op_turn(fr: Frames, p: dict, target: Target):
    poses = fr.poses()
    yaws = _yaws(fr, poses)
    path = _body_path(fr, poses)
    corr = em.turn_correction(yaws, p["total_deg"])
    out = fr.copy()
    _move_world(out, [_about_z(b, c) for b, c in zip(path, corr)])
    after = _yaws(out)
    return out, {"net_before_deg": _r(yaws[-1] - yaws[0], 1), "net_after_deg": _r(after[-1] - after[0], 1),
                 "peak_before_deg": _r(max(yaws, key=lambda y: abs(y - yaws[0])) - yaws[0], 1)}


def _moving_bones(fr: Frames) -> set:
    scale = fr.rig.scale
    return {n for n in fr.rig.order if any(b[n].translation.length * scale > MOVING_M for b in fr.basis)}


def op_mirror(fr: Frames, p: dict, target: Target):
    rig = fr.rig
    S = rig.Wi @ Matrix.Diagonal((-1.0, 1.0, 1.0, 1.0)) @ rig.W
    pairs = em.mirror_pairs(rig.order)
    C = {b: (S @ rig.rest[m]).inverted() @ rig.rest[b] for b, m in pairs.items()}
    moving = _moving_bones(fr)
    keep_loc = {b for b, m in pairs.items() if b in moving or m in moving}
    dropped = 0.0

    def mirror(P):
        nonlocal dropped
        B = rc.basis_from_pose(rig, {b: S @ P[m] @ C[b] for b, m in pairs.items()})
        for b, m in B.items():
            if b not in keep_loc:
                dropped = max(dropped, m.translation.length * rig.scale)
                m.translation = Vector((0.0, 0.0, 0.0))
        return B

    rest = mirror(rc.fk(rig, {}))
    rest_mm = max(m.translation.length * rig.scale for m in rest.values()) * 1000
    rest_deg = max(min(a, 360 - a) for a in (math.degrees(m.to_quaternion().angle) for m in rest.values()))
    dropped = 0.0
    out = fr.copy([mirror(P) for P in fr.poses()])
    return out, {"rest_error_mm": _r(rest_mm, 4), "rest_error_deg": _r(rest_deg, 4),
                 "asymmetry_mm": _r(dropped * 1000, 3)}


def op_stride(fr: Frames, p: dict, target: Target):
    if not fr.loop:
        raise EditError("stride needs an in-place loop (a looping clip, or a cycle step first)")
    rig, n = fr.rig, fr.frames
    poses = fr.poses()
    feet = _feet(fr, poses)
    g = em.ground_velocity(em.contact_velocities(feet, fr.fps))
    if g is None or math.hypot(*g) < 1e-6:
        raise EditError("stride: the feet have no contact frames that move (not an in-place locomotion loop)")
    v_feet = math.hypot(*g)
    d = (g[0] / v_feet, g[1] / v_feet)  # the ground axis: the way the planted feet move under the body
    v0 = p["natural_m_s"] or v_feet
    windows = sum(len(em.contact_windows(em.contact_mask([q[2] for q in pts[:n]]), cyclic=True))
                  for pts in feet.values())
    if not windows:
        raise EditError("stride: no contact windows")
    c0 = em.natural_cadence(windows, fr.seconds)
    m, r_eff = em.stride_rate(n, c0, cadence=p["cadence"], rate=p["rate"])
    out = fr.copy(_resample(fr, em.retime_times(n, m)))
    _close(out)
    s = em.stride_scale(p["speed_m_s"], r_eff, v0)
    fit = em.stride_fit(s, p["warn"], p["fail"])
    poses = out.poses()
    legs = _Legs(rig)
    ground = (d[0] * p["speed_m_s"], d[1] * p["speed_m_s"])
    goals = {}
    for _, _, foot in LEGS:
        track, heights = [], []
        for P in poses[:m]:
            body, f = _world(rig, P, BODY), _world(rig, P, foot)
            o = em.scale_offset((f.x - body.x, f.y - body.y), d, s)
            track.append((body.x + o[0], body.y + o[1]))
            heights.append(f.z)
        wins = em.contact_windows(em.contact_mask(heights), cyclic=True)
        if p["plant"]:
            track = em.plant(track, wins, ground, out.fps, blend=2, cyclic=True)
        contact = set(k for w in wins for k in w)
        goals[foot] = [(Vector((x, y, z)), k in contact) for k, ((x, y), z) in enumerate(zip(track, heights))]
    miss, miss_contact = 0.0, 0.0
    for k in range(m):
        B, P = out.basis[k], poses[k]
        for leg in LEGS:
            goal, on = goals[leg[2]][k]
            e = legs.solve(B, P, leg, rig.Wi @ goal)
            miss = max(miss, e)
            if on:
                miss_contact = max(miss_contact, e)
    _close(out)
    poses = out.poses()
    knees = [legs.flexion(P, leg) for P in poses for leg in LEGS]
    slide = am.foot_sliding(_feet(out, poses), out.fps)
    cadence = c0 * r_eff
    out.info.update(speed_m_s=p["speed_m_s"], speed_from="stride")
    return out, {
        "speed_m_s": p["speed_m_s"], "rate": _r(r_eff, 4), "scale": _r(s, 3), "natural_m_s": _r(v0, 3),
        "natural_cadence": _r(c0, 3), "cadence": _r(cadence, 3), "step_m": _r(p["speed_m_s"] / cadence, 3),
        "cycle_s": _r(out.seconds, 3), "ground_axis": [_r(d[0], 3), _r(d[1], 3)],
        "ik_miss_contact_mm": _r(miss_contact * 1000, 1), "ik_miss_mm": _r(miss * 1000, 1),
        "knee_past_straight_deg": am.hyperextension(knees), "fit": fit,
        "ground_speed_after_m_s": _r((slide["ground_speed_cm_s"] or 0.0) / 100, 3),
        "slide_mean_cm_s": slide["slide_mean_cm_s"], "slide_max_cm_s": slide["slide_max_cm_s"],
    }


def _lows(fr: Frames, target: Target, feet: bool = True) -> list[float]:
    """The lowest vertex height per frame; feet=False leaves out the shoes (the vertices weighted most to a Foot or
    Toe bone), which a lift of the hips cannot take out of the floor."""
    skip = {}
    if not feet:
        meas = target.measure
        for key in ("Foot.L", "Foot.R"):
            for name, idx in meas.sets[key].items():
                skip.setdefault(name, []).extend(int(i) for i in idx)
    lows = []
    for B in fr.basis:
        target.pose(B)
        low = float("inf")
        for name, pts in target.points().items():
            z = pts[:, 2]
            if name in skip:
                z = z.copy()
                z[skip[name]] = float("inf")
            low = min(low, float(z.min()))
        lows.append(low)
    rc.reset_pose(target.arm)
    return lows


def op_floor(fr: Frames, p: dict, target: Target):
    rig, n = fr.rig, fr.frames
    i0 = max(0, round(p["from_s"] * fr.fps))
    i1 = n if p["to_s"] is None else min(n, round(p["to_s"] * fr.fps))
    if i1 < i0:
        raise EditError(f"floor: the window {p['from_s']}-{p['to_s']} s is outside the clip ({fr.seconds:.2f} s)")
    fade = round(p["fade_s"] * fr.fps)
    min_depth = p["min_depth_cm"] / 100

    def depths(lows):
        return [(-z if -z > min_depth else 0.0) if i0 <= k <= i1 else 0.0 for k, z in enumerate(lows)]

    feet = p["mode"] != "hips"  # a hips lift leaves the shoes where they are: they are measured by themselves
    lows = _lows(fr, target, feet)
    before = min(lows[i0:i1 + 1])
    out = fr.copy()
    total = [0.0] * (n + 1)
    legs = _Legs(rig)
    if p["mode"] == "settle":  # a floating clip brought down onto the floor (art #33): Root moves, as a lift
        drop = em.settle_profile(lows, i0, i1, fade)
        out = fr.copy()
        _move_world(out, [Matrix.Translation((0.0, 0.0, -h)) if h else None for h in drop])
        _close(out)
        after = _lows(out, target)
        return out, {"mode": "settle", "lowest_before_cm": _r(100 * before, 2),
                     "lowest_after_cm": _r(100 * min(after[i0:i1 + 1]), 2), "max_drop_cm": _r(100 * max(drop), 2),
                     "highest_low_after_cm": _r(100 * max(after[i0:i1 + 1]), 2),
                     "window_s": [_r(i0 / fr.fps, 3), _r(i1 / fr.fps, 3)]}
    rounds = 1 if p["mode"] == "lift" else 3
    for _ in range(rounds):
        lift = em.floor_profile(depths(lows), i0, i1, fade)
        if max(lift) <= 0:
            break
        total = [a + b for a, b in zip(total, lift)]
        if p["mode"] == "lift":
            _move_world(out, [Matrix.Translation((0.0, 0.0, h)) if h else None for h in lift])
        else:
            up = rig.Wi.to_3x3() @ Vector((0.0, 0.0, 1.0))
            for B, h in zip(out.basis, lift):
                if not h:
                    continue
                P = rc.fk(rig, B)
                planted = {leg[2]: P[leg[2]].translation.copy() for leg in LEGS}
                _set_pose(rig, B, P, BODY, Matrix.Translation(up * h) @ P[BODY])
                P = rc.fk(rig, B)
                for leg in LEGS:
                    legs.solve(B, P, leg, planted[leg[2]])
        _close(out)
        prev, lows = min(lows[i0:i1 + 1]), _lows(out, target, feet)
        if min(lows[i0:i1 + 1]) >= -min_depth or min(lows[i0:i1 + 1]) <= prev + 1e-4:
            break  # out of the floor, or no better
    rep = {"mode": p["mode"], "lowest_before_cm": _r(100 * before, 2),
           "lowest_after_cm": _r(100 * min(lows[i0:i1 + 1]), 2), "max_lift_cm": _r(100 * max(total), 2),
           "window_s": [_r(i0 / fr.fps, 3), _r(i1 / fr.fps, 3)]}
    if not feet:
        rep["shoes_lowest_after_cm"] = _r(100 * min(_lows(out, target)[i0:i1 + 1]), 2)
    return out, rep


# ------------------------------------------------------------------------------------------- arms and hands
class _Arms:
    """Turns both upper arms of a clip by a signed angle about an axis through each shoulder joint (positive: the hand
    moves outwards, away from the body's midline), recomputing only UpperArm's basis, and measures the result."""

    def __init__(self, fr: Frames, target: Target, axis: str):
        self.fr, self.target, self.rig = fr, target, fr.rig
        self.poses = fr.poses()
        rig = self.rig
        self.axes, self.sign = [], {}
        reach = {"L": 0.0, "R": 0.0}
        for P in self.poses:
            R = _turn_of(rig, P, CHEST)
            if axis == "forward":
                ax = R @ Vector((0.0, -1.0, 0.0))
            else:
                ax = Vector((0.0, 0.0, 1.0))
            out = R @ Vector((1.0, 0.0, 0.0))
            self.axes.append(ax.normalized())
            for side, k in (("L", 1.0), ("R", -1.0)):
                r = _world(rig, P, f"Wrist.{side}") - _world(rig, P, f"UpperArm.{side}")
                reach[side] += ax.cross(r).dot(out * k)
        self.sign = {s: (1.0 if v >= 0 else -1.0) for s, v in reach.items()}
        self.arm_m = sum((_world(rig, self.poses[0], f"Wrist.{s}") - _world(rig, self.poses[0], f"UpperArm.{s}")).length
                         for s in "LR") / 2

    def frame(self, k: int, deg: float) -> dict:
        rig = self.rig
        B = {n: m.copy() for n, m in self.fr.basis[k].items()}
        if abs(deg) < 1e-9:
            return B
        P = self.poses[k]
        for side in "LR":
            ua = f"UpperArm.{side}"
            q = rig.Wrot.inverted() @ Quaternion(self.axes[k], math.radians(deg * self.sign[side])) @ rig.Wrot
            pose = Matrix.Translation(P[ua].translation) @ (q @ rc.rot(P[ua])).to_matrix().to_4x4()
            parent = rig.parent[ua]
            B[ua] = rig.rest_rel[ua].inverted() @ P[parent].inverted() @ pose
        return B

    def measure(self, k: int, deg: float, what: str) -> dict:
        """Poses frame k turned by deg and measures: "legs" (the hands' depth in the legs, m) or "hands" (the hands'
        depth in each other and the gap between their closest vertices, m)."""
        meas = self.target.measure
        self.target.pose(self.frame(k, deg))
        pts = self.target.points(meas.meshes)
        if what == "legs":
            return {"depth": anim_metrics._surface_depth(pts, meas.polys, meas.surfaces["legs"], meas.sets["hand"])}
        depth = max(anim_metrics._surface_depth(pts, meas.polys, meas.surfaces["hand.R"], meas.sets["hand.L"]),
                    anim_metrics._surface_depth(pts, meas.polys, meas.surfaces["hand.L"], meas.sets["hand.R"]))
        left = meas._gather(pts, "hand.L")
        right = meas._gather(pts, "hand.R")
        gap = 0.0
        if len(left) and len(right):
            tree = KDTree(len(left))
            for i, q in enumerate(left):
                tree.insert(q, i)
            tree.balance()
            gap = min(tree.find(q)[2] for q in right)
        return {"depth": depth, "gap": gap}

    def apply(self, deg: float) -> Frames:
        out = self.fr.copy([self.frame(k, deg) for k in range(len(self.fr.basis))])
        _close(out)
        return out


def op_arm_offset(fr: Frames, p: dict, target: Target):
    arms = _Arms(fr, target, "forward")
    frames = range(len(fr.basis))
    before = [arms.measure(k, 0.0, "legs")["depth"] for k in frames]
    found = True
    if p["abduct_deg"] == "auto":
        bad = [k for k, x in enumerate(before) if x > 0]
        if not bad:
            deg = 0.0
        else:
            check = sorted({k + o for k in bad for o in (-1, 0, 1) if 0 <= k + o < len(before)})

            def ok(a):
                return all(arms.measure(k, a, "legs")["depth"] <= 0 for k in check)

            deg, found = em.search_angle(ok, 0.0, p["max_deg"], 0.5)
            if found:  # the margin: the hands' closest point moves margin_cm further out
                deg = min(p["max_deg"], deg + math.degrees(p["margin_cm"] / 100 / max(arms.arm_m, 0.1)))
    else:
        deg = float(p["abduct_deg"])
    after = [arms.measure(k, deg, "legs")["depth"] for k in frames]
    rc.reset_pose(target.arm)
    return arms.apply(deg), {
        "deg": _r(deg, 2), "found": found, "hands_in_legs_before_cm": _r(100 * max(before), 2),
        "hands_in_legs_after_cm": _r(100 * max(after), 2), "frames_in_legs_before": sum(x > 0 for x in before),
        "frames_in_legs_after": sum(x > 0 for x in after)}


def op_hand_spacing(fr: Frames, p: dict, target: Target):
    arms = _Arms(fr, target, "vertical")
    n = len(fr.basis)
    if p["at"] == "end":
        sample = [n - 1]
    elif p["at"] == "mean":
        step = max(1, n // 16)
        sample = list(range(0, n, step))
    else:
        sample = list(range(n))

    def stats(deg, frames, mean=p["at"] == "mean"):
        ms = [arms.measure(k, deg, "hands") for k in frames]
        gaps = [m["gap"] for m in ms]
        gap = sum(gaps) / len(gaps) if mean else min(gaps)
        return {"gap": gap, "depth": max(m["depth"] for m in ms)}

    before = stats(0.0, sample)
    found = True
    if p["deg"] != "auto":
        deg = float(p["deg"])
    elif p["gap_m"] is not None:
        deg, found = em.search_angle(lambda a: stats(a, sample)["gap"] >= p["gap_m"], -p["max_deg"], p["max_deg"],
                                     0.25)
    else:
        want = p["min_gap_cm"] / 100

        def good(k, deg):
            m = arms.measure(k, deg, "hands")
            return m["depth"] <= 0 and m["gap"] >= want

        if p["at"] == "mean":
            def ok(a):
                s = stats(a, sample)
                return s["depth"] <= 0 and s["gap"] >= want
        else:  # the frames that fail at 0 degrees and their neighbours
            check = sorted({k + o for k in sample if not good(k, 0.0) for o in (-1, 0, 1) if 0 <= k + o < n})

            def ok(a):
                return all(good(k, a) for k in check)

        deg, found = em.search_angle(ok, 0.0, p["max_deg"], 0.5)
    after = stats(deg, sample)
    every = after if p["at"] == "all" else stats(deg, range(n), mean=False)  # over every frame
    rc.reset_pose(target.arm)
    return arms.apply(deg), {
        "deg": _r(deg, 2), "found": found, "at": p["at"], "gap_before_cm": _r(100 * before["gap"], 2),
        "gap_after_cm": _r(100 * after["gap"], 2), "hands_in_each_other_before_cm": _r(100 * before["depth"], 2),
        "hands_in_each_other_after_cm": _r(100 * every["depth"], 2), "min_gap_after_cm": _r(100 * every["gap"], 2)}


OPS = {"trim": op_trim, "retime": op_retime, "reverse": op_reverse, "cycle": op_cycle, "in_place": op_in_place,
       "heading": op_heading, "turn": op_turn, "mirror": op_mirror, "stride": op_stride, "floor": op_floor,
       "arm_offset": op_arm_offset, "hand_spacing": op_hand_spacing}
assert set(OPS) == set(em.OPS)


def apply(frames: Frames, steps: list, target: Target, body: str) -> Frames:
    """Runs the edit steps in order on a copy of frames; a step whose `body` is another body type is skipped. Each
    step's report (with its op) is appended to info["steps"]; a failing step raises EditError naming it."""
    errors = em.check_steps(steps)
    if errors:
        raise EditError("; ".join(errors))
    cur = frames.copy()
    for k, step in enumerate(steps):
        op = step["op"]
        if step.get("body", body) != body:
            cur.info["steps"].append({"op": op, "skipped": f"body {step['body']}"})
            continue
        try:
            cur, rep = OPS[op](cur, em.params(step), target)
        except (EditError, ValueError) as e:
            raise EditError(f"step {k + 1} ({op}): {e}") from e
        cur.info["steps"].append({"op": op, **rep})
    rc.reset_pose(target.arm)
    bpy.context.view_layer.update()
    return cur
