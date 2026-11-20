"""The first-person hands (art#136, xperiaroco2/prime-game#1587, concept A): runs inside headless Blender.

    blender -b --factory-startup --python-exit-code 1 --python tools/blender/fp_hands_build.py -- \
        --raw <raw> --out <dir> [--preview]

Cuts the alien's forearms and hands with the striped sleeve out of the character build (fp_hands.toml [source]),
keeps the arm bones under one root `View` at the eye plus a `Crystal` bone with the `CrystalSocket` node (where the
energy crystal's origin, its tip, goes), and keys the clips of fp_hands.toml in the camera's space: the arm is a
two-bone solve from the shoulder joint to the wrist with the elbow toward [rig] elbow_*, the forearm takes a share
of the hand's twist, the fingers take grips (alien_hands.toml's and this file's), and the hits key the run fist's
morphs `fist` (the right hand) and, on a model from m41, `fist_L` (the left). Writes <out>/fp_hands.blend,
<out>/fp_hands.glb (the morphs' weights keyed per clip afterwards by alien_fist_math.key_weights) and <out>/build.json (counts, clip lengths, the crystal contact per clip). --preview
also renders Workbench frames from the eye into <out>/preview/ (quick checks; the review shots are Godot's).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import tomllib
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import alien_pose_math as PM  # noqa: E402
import alien_fist_math as F  # noqa: E402
import export_glb as EG  # noqa: E402

CFG = HERE / "fp_hands.toml"
FITTED = HERE / "fp_hands_fit.json"   # the key poses fitted to their target frames by fp_hands_fit.py (over CFG's)
HANDS = HERE / "anim_sets" / "alien_hands.toml"
SIDES = ("Right", "Left")
CHAIN = ("Shoulder", "UpperArm", "LowerArm", "Hand")
FIT_PALM_MM = 0.5    # a held palm may sink this far into the crystal's surface (a soft hand on a hard crystal)
FIT_DIGIT_MM = 1.5   # and a curled digit this far
VIEW_FOV = [50.0]   # [view] fov_deg, set by main
BEND_MAX = [20.0]   # [view] bend_max_deg, set by main
CRYSTAL_SCALE = [1.0]   # [view] crystal_scale, set by main: the held crystal's size in first person
CAP_Z = [0.30]          # [view] cap_z_m, set by main: the crystal's cap point (the top disc under the loop) above its tip
CRYSTAL_R_M = 0.065     # the crystal's half-width in the frame's measures (the cap 13.5 cm across flats, unscaled)
ASPECT = 16.0 / 9.0     # the shots' frame (1280 x 720)
THUMB_ROLLS = range(-30, 91, 15)   # fit_hold's thumb search: the thumb's roll about its length
THUMB_SWINGS = range(-40, 61, 10)  # and its swing toward the palm
CURLS = [0.05 * j for j in range(-30, 51)]   # fit_hold's curl scales per digit: opened back 1.5 to curled 2.5
EASES = {"linear": lambda u: u, "in": lambda u: u * u * u, "out": lambda u: 1.0 - (1.0 - u) ** 3,
         "inout": lambda u: u * u * (3.0 - 2.0 * u)}


def V(a) -> Vector:
    return Vector((float(a[0]), float(a[1]), float(a[2])))


def frame(y: Vector, z: Vector) -> Matrix:
    """An orthonormal 3x3 with columns (x, y, z): y along `y`, z the part of `z` square to it."""
    y = y.normalized()
    z = (z - y * z.dot(y)).normalized()
    return Matrix((y.cross(z), y, z)).transposed()


def hand_q(f, n) -> Quaternion:
    return frame(V(f), V(n)).to_quaternion()


# ------------------------------------------------------------------------------------------- poses in the view
class State:
    """One moment: per side a hand frame (wrist position, rotation of frame(f, n)), a grip {bone: quaternion}, the
    shoulder joint's shift, the morph weight and the crystal's frame (4x4 in the view, or None)."""

    def __init__(self):
        self.p, self.q, self.grip, self.shoulder = {}, {}, {}, {}
        self.fore = {}  # per side the forearm's direction (elbow to wrist) when the pose sets the wrist's bend
        self.home = {}  # a held pose's: per side the hold's own forearm direction, which a moved crystal keeps (seat_fore)
        self.fist = 0.0
        self.fist_L = 0.0   # the left hand's fist morph (fist_L, a model from m41; two fists at rest, art#136)
        self.crystal: Matrix | None = None


def fore_dir(q: Quaternion, bend) -> Vector:
    """The forearm's direction for a hand of rotation q (frame(f, n)) bent at the wrist by bend = [up, side]
    degrees: the hand's length tilted back toward its back (+up: the hand cocked up) and toward its thumb side."""
    m = q.to_matrix()
    f, n = m.col[1], m.col[2]
    x = m.col[0]
    d = Matrix.Rotation(math.radians(-float(bend[0])), 3, x) @ f
    return (Matrix.Rotation(math.radians(-float(bend[1])), 3, n) @ d).normalized()


def wrist_bend(fore: Vector, q: Quaternion) -> tuple[float, float]:
    """fore_dir's inverse: the [up, side] bend (degrees) that gives the forearm direction `fore` for a hand q."""
    m = q.to_matrix()
    a, b, c = fore.dot(m.col[0]), fore.dot(m.col[1]), fore.dot(m.col[2])
    return math.degrees(math.atan2(-c, math.hypot(a, b))), math.degrees(math.atan2(a, b))


def seat_fore(home: Vector, q: Quaternion) -> Vector:
    """A held hand carried by the crystal to the turn q keeps the hold's forearm line `home` in the view as far as its
    wrist allows: the turn about the forearm is its twist (the forearm takes it, [rig] twist_share), and the wrist bends
    toward `home` by at most [view] bend_max_deg up and sideways. A crystal rolled across the view so leaves the
    forearms coming from the frame's bottom corners instead of swinging them with the hands (the first hit grid laid
    the left forearm flat across the frame)."""
    up, side = wrist_bend(home, q)
    lim = BEND_MAX[0]
    return fore_dir(q, [max(-lim, min(lim, up)), max(-lim, min(lim, side))])




def turn_mix(qa: Quaternion, qb: Quaternion, w: float) -> Quaternion:
    """qa turned toward qb by the share w of the way (w below 0 or above 1 goes past either end)."""
    d = qa.rotation_difference(qb)
    if d.w < 0:
        d.negate()
    axis, ang = d.to_axis_angle()
    return Quaternion(axis, ang * w) @ qa


def frame_pct(p: Vector) -> tuple[float, float]:
    """Where a point of the camera's space lands in the hands' camera's frame: % across from the left, % down from
    the top ([view] fov_deg vertical, the shots' 16:9)."""
    t = math.tan(math.radians(VIEW_FOV[0]) / 2.0)
    d = max(p.y, 1e-6)
    return 50.0 + 50.0 * p.x / (d * t * ASPECT), 50.0 - 50.0 * p.z / (d * t)


def crystal_in_view(c: dict) -> dict:
    """A crystal pose set from the eye (the crystal hit's keys, Gate R's card): its cap point (CAP_Z up its axis) at
    `cap` = [% across, % down] of the hands' frame and `dist` m ahead of the eye; from upright with its front to the
    eye, its top turned `tilt` degrees toward the frame's right (about the view's axis; negative: to the left), then
    `lean` degrees away from the eye, then `yaw` degrees toward the right about the vertical (a yaw keeps the hands'
    flanks level, a tilt rolls them). Returns the {p (the tip), up, front} of crystal_matrix."""
    t = math.tan(math.radians(VIEW_FOV[0]) / 2.0)
    d = float(c["dist"])
    cap = Vector(((float(c["cap"][0]) / 50.0 - 1.0) * d * t * ASPECT, d, (1.0 - float(c["cap"][1]) / 50.0) * d * t))
    r = math.radians
    m = (Matrix.Rotation(-r(float(c.get("yaw", 0.0))), 3, "Z") @ Matrix.Rotation(-r(float(c.get("lean", 0.0))), 3, "X")
         @ Matrix.Rotation(r(float(c["tilt"])), 3, "Y"))
    up = m.col[2].normalized()
    tip = cap - up * (CAP_Z[0] * CRYSTAL_SCALE[0])
    return {"p": list(tip), "up": list(up), "front": list(-m.col[1])}


def view_reads(s: "State", reach: float) -> dict:
    """How a held moment reads from the eye: the cap's and the tip's place in the frame (%), the axis's tilt in the
    frame (degrees from upright, + toward the right), each palm's place (%) and depth (m), and `centre_clear`: how far
    the crystal's outline stays from the frame's middle, in % of the frame's height (below 0: it covers the middle)."""
    k = CRYSTAL_SCALE[0]
    cap, tip = s.crystal @ Vector((0.0, 0.0, CAP_Z[0] * k)), s.crystal @ Vector((0.0, 0.0, 0.0))
    (cu, cv), (tu, tv) = frame_pct(cap), frame_pct(tip)
    a = Vector(((tu - 50.0) * ASPECT, tv - 50.0))
    b = Vector(((cu - 50.0) * ASPECT, cv - 50.0))
    ab = b - a
    w = max(0.0, min(1.0, (-a).dot(ab) / max(ab.length_squared, 1e-9)))
    near = a + ab * w   # the axis's point nearest the middle, in % of the height from it
    depth = (tip.lerp(cap, w)).y
    r_pct = 100.0 * CRYSTAL_R_M * k / (2.0 * depth * math.tan(math.radians(VIEW_FOV[0]) / 2.0))
    out = {"cap_pct": [round(cu, 1), round(cv, 1)], "tip_pct": [round(tu, 1), round(tv, 1)],
           "tilt_deg": round(math.degrees(math.atan2((cu - tu) * ASPECT, tv - cv)), 1),
           "centre_clear_pct": round(near.length - r_pct, 1)}
    for side in SIDES:
        palm = s.p[side] + s.q[side].to_matrix().col[1] * reach
        u, v = frame_pct(palm)
        out[f"palm_{side[0]}"] = [round(u, 1), round(v, 1), round(palm.y, 3)]
        if side in s.fore:
            out[f"bend_{side[0]}"] = [round(x, 1) for x in wrist_bend(s.fore[side], s.q[side])]
    return out




def crystal_matrix(c: dict) -> Matrix:
    up = V(c["up"]).normalized()
    y = -V(c["front"])
    y = (y - up * y.dot(up)).normalized()
    m = Matrix((y.cross(up), y, up)).transposed().to_4x4()
    m.translation = V(c["p"])
    return m


class Poses:
    def __init__(self, cfg: dict, grips: dict):
        self.cfg, self.grips = cfg, grips
        # the held hands' fit (fit_hold): per side the palm's shift out from `r` (m) and each digit's curl scale
        self.fit = {side: {"dr": 0.0, "scale": {}, "turn": None, "roll": 0.0} for side in SIDES}

    def grip(self, name: str, side: str, scale: dict | None = None, turn=None) -> dict:
        g = dict(self.grips[name])
        if turn is not None:
            g["ThumbTurn"] = list(turn)
        for f, k in (scale or {}).items():
            vals = list(g.get(f, g.get("all", [0.0, 0.0, 0.0])))
            g[f] = [v * k for v in vals[:3]] + vals[3:]
        return {b: Quaternion(q) for b, q in PM.grip_quats(g, side).items()}

    def resolve(self, spec):
        """A hand spec: a pose's name, {p, f, n, bend}, or {mix = [a, b, w]} between two of them (w past 0 or 1
        goes beyond them: a wind-up, an overshoot)."""
        if isinstance(spec, str):
            return self.cfg["poses"][spec]["R"]
        if "mix" in spec:
            a, b, w = self.resolve(spec["mix"][0]), self.resolve(spec["mix"][1]), float(spec["mix"][2])
            q = turn_mix(hand_q(a["f"], a["n"]), hand_q(b["f"], b["n"]), w).to_matrix()
            ba, bb = a.get("bend", [0.0, 0.0]), b.get("bend", [0.0, 0.0])
            out = {"p": list(V(a["p"]).lerp(V(b["p"]), w)), "f": list(q.col[1]), "n": list(q.col[2]),
                   "bend": [ba[i] + (bb[i] - ba[i]) * w for i in range(2)]}
            if "dp" in spec:
                out["p"] = list(V(out["p"]) + V(spec["dp"]))
            return out
        return spec

    def crystal_spec(self, spec) -> dict:
        if isinstance(spec, str):
            return self.crystal_spec(self.cfg["poses"][spec]["crystal"])
        if "cap" in spec:   # set from the eye (crystal_in_view)
            return crystal_in_view(spec)
        if "mix" in spec:
            a, b, w = self.crystal_spec(spec["mix"][0]), self.crystal_spec(spec["mix"][1]), float(spec["mix"][2])
            ma, mb = crystal_matrix(a), crystal_matrix(b)
            mid = Vector((0.0, 0.0, 0.17 * CRYSTAL_SCALE[0]))
            ca, cb = ma @ mid, mb @ mid
            q = turn_mix(ma.to_quaternion(), mb.to_quaternion(), w)
            m = q.to_matrix()
            c = ca.lerp(cb, w) + (V(spec["dp"]) if "dp" in spec else Vector())
            tip = c - m @ mid
            return {"p": list(tip), "up": list(m.col[2]), "front": list(-m.col[1])}
        return spec

    def hand(self, spec) -> tuple[Vector, Quaternion]:
        spec = self.resolve(spec)
        return V(spec["p"]), hand_q(spec["f"], spec["n"])

    def on_crystal(self, h: dict, dr: float = 0.0, roll: float = 0.0) -> tuple[Vector, Vector, Vector]:
        """A hand on the crystal from where its palm touches: at height `z` on the crystal's axis, toward `toward`
        (the back of the hand faces that way, the palm the crystal), the surface `r` from the axis there, the fingers
        wrapping toward `wrap`; the wrist [rig] reach_m back from the palm's middle, which lies [rig] palm_m off the
        surface (half the hand's thickness)."""
        rig = self.cfg["rig"]
        n = V(h["toward"]).normalized()
        f = V(h["wrap"])
        f = (f - n * f.dot(n)).normalized()
        k = CRYSTAL_SCALE[0]  # the crystal's own measures grow with its first-person scale, the hand's do not
        mid0 = Vector((0.0, 0.0, float(h["z"]) * k))
        n = Matrix.Rotation(math.radians(roll), 3, f) @ n  # the hand rolled about its length (fit_hold)
        mid = mid0 + V(h["toward"]).normalized() * (float(h["r"]) * k + dr) + n * float(rig["palm_m"])
        return mid - f * float(rig["reach_m"]), f, n

    def state(self, base: str, over: dict | None = None) -> State:
        pose = dict(self.cfg["poses"][base])
        pose.update(over or {})
        s = State()
        park = self.cfg["rig"]["park_L"]
        s.p["Left"], s.q["Left"] = V(park["p"]), hand_q(park["f"], park["n"])
        s.grip["Left"] = self.grip(pose.get("grip_L", "relaxed"), "Left")
        s.grip["Right"] = self.grip(pose.get("grip_R", "relaxed"), "Right")
        for side in SIDES:
            s.shoulder[side] = V(pose.get(f"shoulder_{side[0]}", [0, 0, 0]))
        s.fist = float(pose.get("fist", 0.0))
        s.fist_L = float(pose.get("fist_L", 0.0))
        crystal = pose.get("crystal") or self.cfg["poses"]["crystal"]["crystal"]
        s.crystal = crystal_matrix(self.crystal_spec(crystal))
        if "R_c" in pose:  # the hands in the crystal's space
            for side, key in (("Right", "R_c"), ("Left", "L_c")):
                fit = self.fit[side]
                s.grip[side] = self.grip(pose.get(f"grip_{side[0]}", "relaxed"), side, fit["scale"], fit["turn"])
                p, f, n = self.on_crystal(pose[key], fit["dr"], fit["roll"])
                s.p[side] = s.crystal @ p
                s.q[side] = (s.crystal.to_3x3() @ frame(f, n)).to_quaternion()
                if "bend" in pose[key]:
                    s.fore[side] = s.home[side] = fore_dir(s.q[side], pose[key]["bend"])
            if over and "crystal" in over and s.home:   # moved off the hold: the forearms keep the hold's line
                home = self.state(base)
                for side in s.home:
                    s.home[side] = home.home[side]
                    s.fore[side] = seat_fore(s.home[side], s.q[side])
        if "R" in pose:
            s.p["Right"], s.q["Right"] = self.hand(pose["R"])
            spec = self.resolve(pose["R"])
            if "bend" in spec:
                s.fore["Right"] = fore_dir(s.q["Right"], spec["bend"])
        if "L" in pose:   # the left hand in view too (the static two-hand rest, art#136 2026-11-20): {p, f, n, bend}
            spec = pose["L"]
            s.p["Left"], s.q["Left"] = V(spec["p"]), hand_q(spec["f"], spec["n"])
            if "bend" in spec:
                s.fore["Left"] = fore_dir(s.q["Left"], spec["bend"])
        return s


def mix(a: State, b: State, w: float, base: dict) -> State:
    s = State()
    for side in SIDES:
        s.p[side] = a.p[side].lerp(b.p[side], w)
        s.q[side] = a.q[side].slerp(b.q[side], w)
        s.shoulder[side] = a.shoulder[side].lerp(b.shoulder[side], w)
        s.grip[side] = {k: a.grip[side][k].slerp(b.grip[side][k], w) for k in a.grip[side]}
        if side in a.fore and side in b.fore:
            s.fore[side] = a.fore[side].lerp(b.fore[side], w).normalized()
    s.fist = a.fist + (b.fist - a.fist) * w
    s.fist_L = a.fist_L + (b.fist_L - a.fist_L) * w
    loc = a.crystal.translation.lerp(b.crystal.translation, w)
    rot = a.crystal.to_quaternion().slerp(b.crystal.to_quaternion(), w)
    s.crystal = Matrix.Translation(loc) @ rot.to_matrix().to_4x4()
    if "R_c" in base:  # the hands stay on the crystal: carried by the crystal's move, not mixed on their own
        rel = a.crystal.inverted()
        moved = s.crystal @ rel
        for side in SIDES:
            s.p[side] = moved @ a.p[side]
            s.q[side] = moved.to_quaternion() @ a.q[side]
            if side in a.home:
                s.home[side] = a.home[side]
                s.fore[side] = seat_fore(a.home[side], s.q[side])
            elif side in a.fore:
                s.fore[side] = (moved.to_3x3() @ a.fore[side]).normalized()
    return s


def rigid(s: State, g: Matrix, sides=SIDES, crystal=True) -> None:
    """Moves the hands of `sides` (and the crystal) by the view-space transform g."""
    gq = g.to_quaternion()
    for side in sides:
        s.p[side] = g @ s.p[side]
        s.q[side] = gq @ s.q[side]
        if side in s.fore:
            s.fore[side] = (g.to_3x3() @ s.fore[side]).normalized()
    if crystal and s.crystal is not None:
        s.crystal = g @ s.crystal


def about(pivot: Vector, rot: Matrix, move: Vector) -> Matrix:
    return Matrix.Translation(move) @ Matrix.Translation(pivot) @ rot.to_4x4() @ Matrix.Translation(-pivot)


def mirror_x(g: Matrix) -> Matrix:
    """A view-space transform mirrored across the view's middle (x to -x): the other hand's move."""
    m = Matrix.Scale(-1.0, 4, (1.0, 0.0, 0.0))
    return m @ g @ m


def euler_deg(pitch, roll, yaw) -> Matrix:
    r = math.radians
    return (Matrix.Rotation(r(yaw), 3, "Z") @ Matrix.Rotation(r(pitch), 3, "X") @ Matrix.Rotation(r(roll), 3, "Y"))


class Clip:
    def __init__(self, name: str, spec: dict, poses: Poses, run_seconds: float | None):
        self.name, self.spec, self.poses = name, spec, poses
        self.base = poses.cfg["poses"][spec["pose"]]
        self.held = "R_c" in self.base
        self.seconds = float(spec["seconds"])
        if "run" in spec and run_seconds:
            self.seconds = run_seconds
        self.loop = name.endswith("_Loop")
        self.keys = []
        for k in spec.get("keys", []):
            over = {key: v for key, v in k.items() if key not in ("t", "ease")}
            self.keys.append((float(k["t"]), EASES[k.get("ease", "inout")], poses.state(spec["pose"], over)))

    def at(self, t: float) -> State:
        if self.keys:
            if t <= self.keys[0][0]:
                return self.keys[0][2]
            for (t0, _, a), (t1, ease, b) in zip(self.keys, self.keys[1:]):
                if t <= t1:
                    return mix(a, b, ease((t - t0) / (t1 - t0)), self.base)
            return self.keys[-1][2]
        s = self.poses.state(self.spec["pose"])
        sides = SIDES if self.held else ("Right",)
        pivot = s.crystal @ Vector((0, 0, 0.17)) if self.held else s.p["Right"]
        ph = 2.0 * math.pi * t / self.seconds
        # a pose with the left hand in view too (the static two-hand rest): it moves as the right's mirror
        free_L = not self.held and "L" in self.base
        if "sway" in self.spec:
            sw = self.spec["sway"]
            c = sw.get("cycles", [1, 1, 1])
            move = Vector([sw["pos"][i] * math.sin(c[i] * ph + 1.3 * i) for i in range(3)])
            rot = euler_deg(*[sw["rot"][i] * math.sin(c[i] * ph + 0.7 + 1.1 * i) for i in range(3)])
            rigid(s, about(pivot, rot, move), sides, self.held)
            if free_L:
                rigid(s, mirror_x(about(pivot, rot, move)), ("Left",), False)
        if "run" in self.spec:
            r = self.spec["run"]
            step = math.cos(2.0 * ph)  # two steps a loop: down at each foot's contact
            move = V(r.get("lift", [0, 0, 0])) + Vector((r["side"] * math.sin(ph), r["fwd"] * step,
                                                         r["bob"] * 0.5 * step))
            rot = euler_deg(r["pitch"] * step, r["roll"] * math.sin(ph), r["yaw"] * math.sin(ph))
            rigid(s, about(pivot, rot, move), sides, self.held)
            if free_L:
                rigid(s, mirror_x(about(pivot, rot, move)), ("Left",), False)
        return s


# ------------------------------------------------------------------------------------------------ the rig
class Rig:
    def __init__(self, arm, cfg: dict):
        self.arm, self.cfg = arm, cfg
        self.A = arm.matrix_world.copy()
        self.Ai = self.A.inverted()
        self.A3i = self.Ai.to_3x3()
        self.rest = {b.name: b.matrix_local.copy() for b in arm.data.bones}
        self.parent = {b.name: b.parent.name if b.parent else None for b in arm.data.bones}
        r = self.rest
        self.la = (r["RightLowerArm"].translation - r["RightUpperArm"].translation).length
        self.lb = (r["RightHand"].translation - r["RightLowerArm"].translation).length
        fwd = self.A3i @ Vector((0, 1, 0))
        self.hand_rest_w = {s: self.A.to_3x3() @ r[f"{s}Hand"].to_3x3() for s in SIDES}
        self.hinge0 = {}
        self.short = {}  # per side the most the wrist was out of the arm's reach since the last reset (m)
        for s in SIDES:
            y0 = r[f"{s}UpperArm"].to_3x3().col[1]
            self.hinge0[s] = y0.cross((fwd - y0 * fwd.dot(y0)).normalized())

    def basis(self, child: str, child_pose: Matrix, parent_pose: Matrix) -> Matrix:
        rel = self.rest[self.parent[child]].inverted() @ self.rest[child]
        return rel.inverted() @ parent_pose.inverted() @ child_pose

    def _frames(self, head, elbow, wrist, side, H3):
        """The upper arm's and the forearm's frames for the joints head, elbow and wrist (armature space), and the
        hand's twist about the forearm that is left (radians)."""
        r = self.rest
        yu, yl = (elbow - head).normalized(), (wrist - elbow).normalized()
        flex = yl - yu * yl.dot(yu)
        hinge = yu.cross(flex.normalized()) if flex.length > 1e-6 else self.hinge0[side]
        h0 = self.hinge0[side]
        U3 = frame(yu, hinge) @ frame(r[f"{side}UpperArm"].to_3x3().col[1], h0).transposed() @ r[f"{side}UpperArm"].to_3x3()
        L03 = frame(yl, hinge) @ frame(r[f"{side}LowerArm"].to_3x3().col[1], h0).transposed() @ r[f"{side}LowerArm"].to_3x3()
        rel_h = r[f"{side}LowerArm"].to_3x3().inverted() @ r[f"{side}Hand"].to_3x3()
        q = ((L03 @ rel_h).inverted() @ H3).to_quaternion()
        twist = 2.0 * math.atan2(q.y, q.w)
        twist = (twist + math.pi) % (2 * math.pi) - math.pi
        return yu, yl, hinge, U3, L03, twist

    def solve(self, s: State) -> dict:
        """{bone: basis 4x4} for every posed bone at this moment."""
        r, rig = self.rest, self.cfg["rig"]
        out = {}
        view = r["View"]
        for side in SIDES:
            # the hand's wanted rotation: the rest hand turned so its length runs along f and its back along n
            want_w = s.q[side].to_matrix()
            rest_w = self.hand_rest_w[side]
            rot_w = want_w @ frame(rest_w.col[1], Vector((0, 0, 1))).transposed() @ rest_w
            H3 = self.A3i @ rot_w
            wrist = self.Ai @ s.p[side]
            head = self.Ai @ (V(rig[f"shoulder_{side[0]}"]) + s.shoulder[side])
            S_pose = Matrix.Translation(head - r[f"{side}UpperArm"].translation) @ r[f"{side}Shoulder"]
            if side in s.fore:
                # the viewmodel's arm: the forearm runs along the pose's own direction back from the wrist, the upper
                # arm from the elbow toward [rig] upper_* (out of the frame); the shoulder joint goes where that ends
                fa = (self.A3i @ s.fore[side]).normalized()
                elbow = wrist - fa * self.lb
                up0 = (self.A3i @ V(rig[f"upper_{side[0]}"])).normalized()
                bend = min(math.degrees(fa.angle(up0)), float(rig["elbow_max_deg"]))
                # the elbow bends at most elbow_max_deg (a near-straight arm, its crease out of view), in the plane
                # that leaves the least twist between the forearm and the upper arm (no wrung sleeve at the elbow),
                # kept near upper_*: the upper arm's direction is searched round the forearm
                e1 = fa.orthogonal().normalized()
                e2 = fa.cross(e1)
                best = None
                for k in range(24):
                    ph = 2.0 * math.pi * k / 24
                    ax = e1 * math.cos(ph) + e2 * math.sin(ph)
                    uc = Matrix.Rotation(math.radians(bend), 3, ax) @ fa
                    hc = elbow - uc * self.la
                    tw = self._frames(hc, elbow, wrist, side, H3)[5]
                    cost = abs(tw) + 0.6 * uc.angle(up0)
                    if best is None or cost < best[0]:
                        best = (cost, hc)
                head = best[1]
                S_pose = Matrix.Translation(head - r[f"{side}UpperArm"].translation) @ r[f"{side}Shoulder"]
                self.short[side] = 0.0
            else:
                d = wrist - head
                self.short[side] = max(self.short.get(side, 0.0), d.length - (self.la + self.lb) * 0.999)
                dist = min(d.length, (self.la + self.lb) * 0.999)
                dirn = d.normalized()
                pole = self.A3i @ V(rig[f"elbow_{side[0]}"])
                pole = (pole - dirn * pole.dot(dirn)).normalized()
                a = (self.la ** 2 - self.lb ** 2 + dist ** 2) / (2 * dist)
                elbow = head + dirn * a + pole * math.sqrt(max(self.la ** 2 - a * a, 0.0))
                wrist = head + dirn * dist
            yu, yl, hinge, U3, L03, twist = self._frames(head, elbow, wrist, side, H3)
            L3 = L03 @ Matrix.Rotation(twist * float(rig["twist_share"]), 3, "Y")
            U_pose = Matrix.Translation(head) @ U3.to_4x4()
            L_pose = Matrix.Translation(elbow) @ L3.to_4x4()
            H_pose = Matrix.Translation(elbow + yl * self.lb) @ H3.to_4x4()
            out[f"{side}Shoulder"] = self.basis(f"{side}Shoulder", S_pose, view)
            out[f"{side}UpperArm"] = self.basis(f"{side}UpperArm", U_pose, S_pose)
            out[f"{side}LowerArm"] = self.basis(f"{side}LowerArm", L_pose, U_pose)
            out[f"{side}Hand"] = self.basis(f"{side}Hand", H_pose, L_pose)
            for b, qq in s.grip[side].items():
                out[b] = qq.to_matrix().to_4x4()
        C_pose = self.Ai @ s.crystal @ self.A @ r["Crystal"]
        out["Crystal"] = self.basis("Crystal", C_pose, view)
        return out


# ------------------------------------------------------------------------------------------- the cut-out
def arm_bones(names) -> set:
    keep = {"View", "Crystal"}
    for n in names:
        for side in SIDES:
            if n.startswith(side) and (any(n == side + c for c in CHAIN) or
                                       any(n.startswith(side + f) for f in PM.FINGERS)):
                keep.add(n)
    return keep


def cut(cfg: dict, raw: Path) -> tuple:
    src = cfg["source"]
    bpy.ops.wm.open_mainfile(filepath=str(raw / src["char"]))
    run_seconds = None
    for act in bpy.data.actions:
        if act.name.endswith("Jog_Fwd_Loop"):
            fps = bpy.context.scene.render.fps / bpy.context.scene.render.fps_base
            run_seconds = round((act.frame_range[1] - act.frame_range[0]) / fps, 4)
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    body = next(o for o in bpy.data.objects if o.type == "MESH" and o.data.shape_keys and "fist" in o.data.shape_keys.key_blocks)
    top = bpy.data.objects.get("top")   # the striped top: none on a build from the rig seed (fp_hand_model.py)
    if not src.get("sleeve", True) and "body_removed" in bpy.data.objects:
        # the bare arm: the skin the build took off under the clothes (body_removed, skinned to the same rig with the
        # same materials) joined back onto the body, the seam welded
        rem = bpy.data.objects["body_removed"]
        rem.hide_set(False)
        rem.hide_render = False
        bpy.ops.object.select_all(action="DESELECT")
        rem.select_set(True)
        body.select_set(True)
        bpy.context.view_layer.objects.active = body
        bpy.ops.object.join()
        bm = bmesh.new()
        bm.from_mesh(body.data)
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0005)
        bm.to_mesh(body.data)
        bm.free()
    for o in list(bpy.data.objects):
        if o not in (arm, body, top):
            bpy.data.objects.remove(o, do_unlink=True)
    for a in list(bpy.data.actions):
        bpy.data.actions.remove(a)
    for o in [x for x in (arm, body, top) if x is not None]:
        if o.animation_data:
            o.animation_data_clear()
    arm.matrix_world = Matrix.Identity(4)
    bpy.context.view_layer.update()  # the meshes' world matrices follow their armature parent before they are read
    to_arm = {o.name: o.matrix_world.copy() for o in (body, top) if o is not None}
    stats = {}
    if top is not None:
        tv = [to_arm[top.name] @ v.co for v in top.data.vertices]
        cuff = {s: max(abs(p.x) for p in tv if (p.x < 0) == (s == "Right")) for s in SIDES}
        skin_from = {s: cuff[s] - float(src["skin_inside_cuff_m"]) for s in SIDES}
        stats["cuff_m"] = {s: round(cuff[s], 4) for s in SIDES}
    elif src.get("sleeve", True):
        raise SystemExit("fp_hands.toml [source] sleeve = true needs the character's striped top, and the source has none")
    # the sleeve from a little above the elbow: a viewmodel shows no upper arm
    elbow = {sd: abs((arm.matrix_world @ arm.data.bones[f"{sd}LowerArm"].head_local).x) for sd in SIDES}
    sleeve_from = {sd: elbow[sd] - float(src["sleeve_above_elbow_m"]) for sd in SIDES}
    stats["sleeve_from_m"] = {sd: round(v, 4) for sd, v in sleeve_from.items()}
    bare = not src.get("sleeve", True)
    if bare:  # the bare arm (the engineer, 2026-11-11): the skin from above the elbow, no garment; a sleeve comes later
        skin_from = sleeve_from   # from the worn outfit's own mesh
    for o, edge in [(o, e) for o, e in ((body, skin_from), (top, sleeve_from)) if o is not None]:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        M = to_arm[o.name]
        gone = [v for v in bm.verts if abs((M @ v.co).x) < edge["Right" if (M @ v.co).x < 0 else "Left"]]
        before = len(bm.verts)
        bmesh.ops.delete(bm, geom=gone, context="VERTS")
        bmesh.ops.triangulate(bm, faces=bm.faces[:])  # the exporter's tangents need triangles (ngons in the source)
        bm.to_mesh(o.data)
        bm.free()
        stats[o.name] = {"verts_before": before, "verts": len(o.data.vertices), "tris": sum(len(p.vertices) - 2 for p in o.data.polygons)}
    if "View" in arm.data.bones:   # a rig from the seed has its View bone at the eye already
        eye = arm.data.bones["View"].head_local.copy()
    else:
        eye = (arm.data.bones["LeftEye"].head_local + arm.data.bones["RightEye"].head_local) / 2
    eye.x = 0.0
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones
    keep = arm_bones([b.name for b in eb])
    view = eb.get("View") or eb.new("View")
    view.head, view.tail = eye, eye + Vector((0, -0.1, 0))
    crystal = eb.get("Crystal") or eb.new("Crystal")
    crystal.head, crystal.tail, crystal.parent = eye, eye + Vector((0, 0, 0.1)), view
    for b in list(eb):
        if b.name not in keep:
            eb.remove(b)
    for side in SIDES:
        eb[f"{side}Shoulder"].parent = view
    view.use_deform = crystal.use_deform = False
    bpy.ops.object.mode_set(mode="OBJECT")
    names = {b.name for b in arm.data.bones}
    if bare and top is not None:
        bpy.data.objects.remove(top, do_unlink=True)
        top = None
    for o in [x for x in (body, top) if x is not None]:
        for g in list(o.vertex_groups):
            if g.name not in names:
                o.vertex_groups.remove(g)
        unweighted = sum(1 for v in o.data.vertices if not any(g.weight > 0 for g in v.groups))
        stats[o.name]["unweighted"] = unweighted
    # the eye to the origin, the character's front (-y) to the view's (+y)
    arm.matrix_world = Matrix.Rotation(math.pi, 4, "Z") @ Matrix.Translation(-eye)
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
    sock = bpy.data.objects.new("CrystalSocket", None)
    bpy.context.scene.collection.objects.link(sock)
    sock.empty_display_type, sock.empty_display_size = "ARROWS", 0.05
    sock.parent, sock.parent_type, sock.parent_bone = arm, "BONE", "Crystal"
    bpy.context.view_layer.update()
    sock.matrix_parent_inverse = Matrix.Identity(4)
    sock.matrix_world = Matrix.Identity(4)
    sock.scale = (CRYSTAL_SCALE[0],) * 3   # the held crystal's first-person size: a child of the socket takes it
    body.name = "FPArms"
    if top is not None:
        top.name = "FPSleeves"
    arm.name = "FPRig"
    arm.data.name = "FPRig"
    stats["eye_m"] = [round(x, 4) for x in eye]
    stats["run_seconds_from_jog"] = run_seconds
    return arm, body, top, sock, run_seconds, stats


# -------------------------------------------------------------------------------------------- keying
def key_clip(rig: Rig, clip: Clip, fps: int) -> tuple:
    arm = rig.arm
    act = bpy.data.actions.new(clip.name)
    act.use_fake_user = True
    bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"  # sampled every frame: no Bezier overshoot
    arm.animation_data_create()
    arm.animation_data.action = act
    n = max(1, round(clip.seconds * fps))
    prev = {}
    fist = []
    for i in range(n + 1):
        t = clip.seconds * i / n
        s = clip.at(t if not (clip.loop and i == n) else 0.0)
        fist.append((i / n, s.fist, s.fist_L))
        for b, m in rig.solve(s).items():
            pb = arm.pose.bones[b]
            loc, q, _ = m.decompose()
            if b in prev and prev[b].dot(q) < 0:
                q = -q
            prev[b] = q
            pb.location, pb.rotation_quaternion = loc, q
            pb.keyframe_insert("location", frame=i, group=b)
            pb.keyframe_insert("rotation_quaternion", frame=i, group=b)
    act.use_frame_range = True
    act.frame_start, act.frame_end = 0, n
    return act, n, fist


def set_frame(arm, act, frame_no: int, body=None, fist=None) -> None:
    arm.animation_data.action = act
    bpy.context.scene.frame_set(frame_no)
    if body is not None and fist is not None:   # fist: the right's weight, or (right, left)
        w, wl = fist if isinstance(fist, tuple) else (fist, 0.0)
        kb = body.data.shape_keys.key_blocks
        kb["fist"].value = w
        if "fist_L" in kb:
            kb["fist_L"].value = wl


# -------------------------------------------------------------------------------------- the crystal check
def load_crystal(path: Path, sock):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    new = [o for o in bpy.data.objects if o not in before]
    roots = [o for o in new if o.parent is None]
    for o in roots:
        o.parent = sock
        o.matrix_parent_inverse = Matrix.Identity(4)
        o.matrix_basis = Matrix.Identity(4)  # the GLB's own root: the crystal's tip at the socket
    return new, [o for o in new if o.type == "MESH"]


PALM = ("Hand", "ThumbMetacarpal")   # the palm with the thumb's mound
THUMB = ("ThumbProximal", "ThumbDistal")


def hand_points(body, side: str, only: tuple | None = None) -> list:
    dg = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(dg)
    me = ev.to_mesh()
    groups = {g.index: g.name for g in body.vertex_groups}
    pts = []
    for v, vo in zip(me.vertices, body.data.vertices):
        best = max(vo.groups, key=lambda g: g.weight, default=None)
        if best is None:
            continue
        name = groups[best.group]
        if not name.startswith(side):
            continue
        part = name[len(side):]
        hit = (part == "Hand" or any(part.startswith(f) for f in PM.FINGERS)) if only is None else (
            any(part.startswith(o) for o in only))
        if hit:
            pts.append(ev.matrix_world @ v.co)
    ev.to_mesh_clear()
    return pts


class Solid:
    """The crystal's outer surface in the socket's space (every mesh but the glowing core inside the shell), for
    inside/outside tests of the hand's points."""

    def __init__(self, meshes, sock):
        dg = bpy.context.evaluated_depsgraph_get()
        inv = sock.matrix_world.inverted()
        verts, polys = [], []
        self.skipped = []
        for o in meshes:
            core = {i for i, m in enumerate(o.data.materials) if m and "core" in m.name.lower()}
            self.skipped += [o.data.materials[i].name for i in sorted(core)]
            ev = o.evaluated_get(dg)
            me = ev.to_mesh()
            off = len(verts)
            verts += [inv @ ev.matrix_world @ v.co for v in me.vertices]
            polys += [[off + i for i in p.vertices] for p in me.polygons if p.material_index not in core]
            ev.to_mesh_clear()
        self.tree, self.sock = BVHTree.FromPolygons(verts, polys), sock


def contact(body, solid: "Solid", side: str, only: tuple | None = None) -> tuple[float, float]:
    """(deepest point of the hand, or of one part, inside the crystal; nearest gap) in mm."""
    inv = solid.sock.matrix_world.inverted()
    deep, gap = 0.0, 1e9
    for p in hand_points(body, side, only):
        p = inv @ p
        loc, nrm, _, dist = solid.tree.find_nearest(p)
        if loc is None:
            continue
        if (p - loc).dot(nrm) < 0:
            deep = max(deep, dist)
            gap = 0.0
        else:
            gap = min(gap, dist)
    return round(deep * 1000, 1), round(gap * 1000, 1)


def hold_report(poses: Poses, body, solid: "Solid", base: str = "crystal") -> dict:
    """How a hold reads, per side, in the posed rig: `palm_touch` the share of the palm's points (PALM) within 4 mm of
    the crystal's surface; `wrist_z_mm` the wrist's height in the camera's space (both hands at one height);
    `back_to_eye` the cosine between the back of the hand's normal and the way to the eye (the backs up toward it);
    in the crystal's space (y away from the eye, z up its length, mm, its first-person scale) the fingertips' mean
    `tips_y` (above 0: round its back) and the thumb tip's `thumb_y` and `thumb_z` (on a near face, up)."""
    inv = solid.sock.matrix_world.inverted()
    k = CRYSTAL_SCALE[0]
    s = poses.state(base)
    out = {}
    for side in SIDES:
        near = [p for p in (inv @ q for q in hand_points(body, side, PALM))]
        touch = 0
        for p in near:
            loc, nrm, _, dist = solid.tree.find_nearest(p)
            touch += loc is not None and dist <= 0.004
        tips = [inv @ q for q in hand_points(body, side, ("IndexDistal", "MiddleDistal", "RingDistal"))]
        thumb = [inv @ q for q in hand_points(body, side, ("ThumbDistal",))]
        n = s.q[side].to_matrix().col[2]
        palm = s.p[side] + s.q[side].to_matrix().col[1] * float(poses.cfg["rig"]["reach_m"])
        mean = lambda pts, i: round(sum(p[i] for p in pts) / max(len(pts), 1) * 1000 * k, 1)
        out[side] = {"palm_touch": round(touch / max(len(near), 1), 3), "wrist_z_mm": round(s.p[side].z * 1000, 1),
                     "back_to_eye": round(n.dot(-palm.normalized()), 3), "back_up": round(n.z, 3), "tips_y": mean(tips, 1),
                     "thumb_y": mean(thumb, 1), "thumb_z": mean(thumb, 2)}
    return out


def pose_now(rig: Rig, s: State) -> None:
    for b, m in rig.solve(s).items():
        loc, q, _ = m.decompose()
        pb = rig.arm.pose.bones[b]
        pb.location, pb.rotation_quaternion = loc, q
    bpy.context.view_layer.update()


def fit_hold(rig: Rig, poses: Poses, body, solid: Solid, base: str = "crystal", roll_span: float | None = None,
             seat_by: tuple = PALM) -> dict:
    """Seats each held hand on the crystal in the pose `base`: the palm moves out along the back of the hand from
    `r` until it is no more than FIT_PALM_MM inside the crystal's surface, then each digit curls (its grip's curls
    scaled) as far as it goes with at most FIT_DIGIT_MM inside: the fingers close round the crystal and stop on it.
    Per side `fallback` lists where the fit did not find its answer and took a default or stopped on its search's
    edge (the hold is still built: the run prints them as warnings without failing)."""
    out = {}
    for side in SIDES:
        fit = poses.fit[side]
        fit["scale"] = {f: 0.0 for f in PM.FINGERS}
        seat = None
        r0 = fit["roll"]
        rolls = range(-45, 46, 9) if roll_span is None else [r0 + d for d in range(-int(roll_span), int(roll_span) + 1, 5)]
        for roll in rolls:  # the roll about the hand's length that lets the palm sit closest (about the fitted one)
            fit["roll"] = float(roll)
            for k in range(0, 61):
                fit["dr"] = -0.010 + 0.0015 * k
                pose_now(rig, poses.state(base))
                if contact(body, solid, side, seat_by)[0] <= FIT_PALM_MM:
                    break
            if seat is None or fit["dr"] < seat[0] - 1e-9:
                seat = (fit["dr"], float(roll))
        fit["dr"], fit["roll"] = seat
        fallback = []
        if len(rolls) > 1 and fit["roll"] in (float(min(rolls)), float(max(rolls))):
            fallback.append(f"roll {fit['roll']:g} on its search's edge ({min(rolls):g} to {max(rolls):g})")
        gaps = {}
        # the thumb first finds a turn (roll about its length, swing toward the palm) that lies on the crystal
        # without entering it, at half its grip's curl: the nearest to the surface of those within FIT_DIGIT_MM
        fit["scale"]["Thumb"] = 0.5
        best_turn = None
        # a pinned thumb (the pose's thumb_pin = {turn, curl}, art#136 round 2): the approved hold's own fit, kept
        # while the hand's model changes under it (m29's eased thumb weights moved the search to curl x2.5)
        pin = poses.cfg["poses"][base].get("thumb_pin")
        for roll in ([] if pin else THUMB_ROLLS):
            for swing in THUMB_SWINGS:
                fit["turn"] = [roll, swing]
                pose_now(rig, poses.state(base))
                deep, gap = contact(body, solid, side, ("ThumbMetacarpal",) + THUMB)  # its base turns with it
                if deep <= FIT_DIGIT_MM and (best_turn is None or gap < best_turn[0]):
                    best_turn = (gap, [roll, swing])
        fit["turn"] = list(pin["turn"]) if pin else (best_turn[1] if best_turn else None)
        if pin:
            pass
        elif fit["turn"] is None:
            fallback.append(f"thumb turn: none within {FIT_DIGIT_MM} mm, the grip's own")
        elif fit["turn"][0] in (THUMB_ROLLS[0], THUMB_ROLLS[-1]) or fit["turn"][1] in (THUMB_SWINGS[0], THUMB_SWINGS[-1]):
            fallback.append(f"thumb turn {fit['turn']} on its search's edge (roll {THUMB_ROLLS[0]} to "
                            f"{THUMB_ROLLS[-1]}, swing {THUMB_SWINGS[0]} to {THUMB_SWINGS[-1]})")
        for f in PM.FINGERS:
            if f != "Thumb" and not hand_points(body, side, (f,)):
                # a digit the model does not have (four digits since m40: the rig's Little carries no skin): nothing
                # to seat, so it stays at its grip's rest instead of curling to the search's edge with no surface
                fit["scale"][f] = 0.0
                continue
            if pin and f == "Thumb":
                fit["scale"][f] = float(pin["curl"])
                pose_now(rig, poses.state(base))
                gaps[f] = contact(body, solid, side, THUMB)
                continue
            # from opened (negative: the digit straightened back past its rest) to curled 2.5 times the grip: the
            # most curl that stays within FIT_DIGIT_MM of the surface
            best = None
            for c in CURLS:
                fit["scale"][f] = c
                pose_now(rig, poses.state(base))
                deep = contact(body, solid, side, THUMB if f == "Thumb" else (f,))[0]
                if deep > FIT_DIGIT_MM:
                    if best is not None:
                        break
                    continue
                best = fit["scale"][f]
            fit["scale"][f] = best if best is not None else -1.5
            if best is None:
                fallback.append(f"{f}: no curl within {FIT_DIGIT_MM} mm, opened to the default -1.5")
            elif abs(best - CURLS[0]) < 1e-9 or abs(best - CURLS[-1]) < 1e-9:
                fallback.append(f"{f}: curl {best:.2f} on its search's edge ({CURLS[0]:.2f} to {CURLS[-1]:.2f})")
            pose_now(rig, poses.state(base))
            gaps[f] = contact(body, solid, side, THUMB if f == "Thumb" else (f,))
        pose_now(rig, poses.state(base))
        deep, gap = contact(body, solid, side)
        if contact(body, solid, side, seat_by)[0] > FIT_PALM_MM:
            fallback.append(f"palm not seated within {FIT_PALM_MM} mm: {fit['dr'] * 1000:.1f} mm out, the search's end")
        out[side] = {"palm_shift_mm": round(fit["dr"] * 1000, 1), "roll_deg": fit["roll"], "thumb_turn": fit["turn"],
                     "fallback": fallback, "curl_scale": {f: round(v, 2) for f, v in fit["scale"].items()},
                     "deepest_mm": deep, "gap_mm": gap, "digits_mm": gaps}
    pose_now(rig, poses.state(base))
    for side, r in hold_report(poses, body, solid, base).items():
        out[side]["reads"] = r
    return out


def hold_grid(out: Path, rig: Rig, poses: Poses, body, solid: "Solid", crystal_objs, variants: list,
              roll_span) -> None:
    """--hold-grid: each variant's hold (keys over [poses.crystal] R_c, mirrored onto L_c: `toward` and `wrap` with x
    negated, `bend`'s second value negated; `roll` a start roll; `grip` the grip of both), seated by fit_hold, its
    numbers into grid/grid.json and a Workbench render from the eye into grid/<name>.png, and grid/sheet.png."""
    base = dict(poses.cfg["poses"]["crystal"])
    (out / "grid").mkdir(parents=True, exist_ok=True)
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "TEXTURE"
    sc.display.shading.show_cavity = True
    sc.render.resolution_x, sc.render.resolution_y = 640, 360
    cam_data = bpy.data.cameras.new("eye")
    cam_data.sensor_fit = "VERTICAL"
    cam_data.angle_y = math.radians(float(VIEW_FOV[0]))
    cam_data.clip_start = 0.02
    cam = bpy.data.objects.new("eye", cam_data)
    sc.collection.objects.link(cam)
    cam.rotation_euler = (math.radians(90), 0, 0)
    sc.camera = cam
    res, files = {}, []
    for v in variants:
        pose = dict(base)
        r = dict(base["R_c"])
        r.update({k: x for k, x in v.items() if k in ("z", "toward", "r", "wrap", "bend")})
        l = dict(r)
        l["toward"] = [-r["toward"][0], *r["toward"][1:]]
        l["wrap"] = [-r["wrap"][0], *r["wrap"][1:]]
        if "bend" in r:
            l["bend"] = [r["bend"][0], -r["bend"][1]]
        pose["R_c"], pose["L_c"] = r, l
        if "grip" in v:
            pose["grip_R"] = pose["grip_L"] = v["grip"]
        poses.cfg["poses"]["grid"] = pose
        for side in SIDES:
            poses.fit[side]["roll"] = float(v.get("roll", 30.0)) * (1 if side == "Right" else -1)
        fit = fit_hold(rig, poses, body, solid, base="grid", roll_span=v.get("roll_span", roll_span),
                       seat_by=tuple(v.get("seat", PALM)))
        res[v["name"]] = {"variant": v, "fit": fit}
        sc.render.filepath = str(out / "grid" / f"{v['name']}.png")
        bpy.ops.render.render(write_still=True)
        files.append(out / "grid" / f"{v['name']}.png")
        print("FP_GRID " + json.dumps({v["name"]: {sd: {**f["reads"], "roll": f["roll_deg"], "dr_mm": f["palm_shift_mm"],
                                                         "deep": f["deepest_mm"]} for sd, f in fit.items()}}), flush=True)
        (out / "grid" / "grid.json").write_text(json.dumps(res, indent=1), encoding="utf-8")   # after each: a long grid
    sheet(out / "grid" / "sheet.png", files, cols=3, w=640, h=360)


def thumb_reads(rig: Rig, body, side: str = "Right") -> dict:
    """The free hand's thumb against its index (the rest card: the thumb along the index's side and below it, its tip
    forward at about the index's middle joint, a small gap): the thumb tip's offset from the index's middle joint in
    the hand's frame (mm: `fwd` along the fingers, `out` past the index's side, `normal` off the fingers' plane), and the
    nearest gap between the thumb's skin (proximal, distal) and the index's (mm; about 0: touching or through)."""
    from mathutils.kdtree import KDTree
    pb = rig.arm.pose.bones
    w = rig.arm.matrix_world
    tip, joint = w @ pb[f"{side}ThumbDistal"].tail, w @ pb[f"{side}IndexIntermediate"].head
    fwd = (joint - w @ pb[f"{side}Hand"].head).normalized()
    across = (w @ pb[f"{side}IndexProximal"].head - w @ pb[f"{side}LittleProximal"].head)
    across = (across - fwd * across.dot(fwd)).normalized()   # toward the index's side
    normal = fwd.cross(across).normalized()   # off the fingers' plane (its sign read from the side view)
    d = tip - joint
    idx = hand_points(body, side, ("Index",))
    kd = KDTree(len(idx))
    for k, v in enumerate(idx):
        kd.insert(v, k)
    kd.balance()
    gap = min(kd.find(v)[2] for v in hand_points(body, side, ("ThumbProximal", "ThumbDistal")))
    tip_pts = hand_points(body, side, ("ThumbDistal",))
    tip_gap = min(kd.find(v)[2] for v in tip_pts)
    # the thumb tip's gap to the palm and the other fingers (the Hand group and Middle..Little): a gap near 0 is a
    # thumb pressed into them (an unsigned distance: through reads as touching too)
    rest = hand_points(body, side, ("Hand", "Middle", "Ring", "Little"))
    kr = KDTree(len(rest))
    for k, v in enumerate(rest):
        kr.insert(v, k)
    kr.balance()
    palm_gap = min(kr.find(v)[2] for v in tip_pts)
    # the thumb's swing out from the index's line: the thumb (its proximal's head to its tip) against the index's
    # proximal phalanx, in the fingers' plane (fwd, across), and its rise off that plane (+ along `normal`)
    th = tip - w @ pb[f"{side}ThumbProximal"].head
    ix = (w @ pb[f"{side}IndexIntermediate"].head) - (w @ pb[f"{side}IndexProximal"].head)
    def ang(a):
        return math.degrees(math.atan2(a.dot(across), a.dot(fwd)))
    rise = math.degrees(math.asin(max(-1.0, min(1.0, th.normalized().dot(normal)))))
    return {"tip_vs_index_joint_mm": {"fwd": round(d.dot(fwd) * 1000, 1), "out": round(d.dot(across) * 1000, 1),
                                      "normal": round(d.dot(normal) * 1000, 1)},
            "thumb_index_gap_mm": round(gap * 1000, 1), "thumb_tip_index_gap_mm": round(tip_gap * 1000, 1),
            "thumb_tip_palm_gap_mm": round(palm_gap * 1000, 1),
            "thumb_swing_deg": round(ang(th) - ang(ix), 1), "thumb_rise_deg": round(rise, 1)}


def hit_grid(out: Path, rig: Rig, poses: Poses, body, solid: "Solid", variants: list, crystal_objs=()) -> None:
    """--hit-grid: each variant is one moment rendered from the eye (Workbench, hitgrid/<name>.png and sheet.png) with
    its numbers in hitgrid/grid.json. A variant: `name`; `pose` (default "crystal"); a crystal pose from the eye
    (`cap`, `dist`, `tilt`, `lean`, `yaw`: crystal_in_view), the hold carried to it as Crystal_Hit's keys carry it,
    read from the eye (view_reads) with each hand's deepest point inside the crystal and the wrists out of reach;
    `grips` = {grip: {field: value}} over [grips] for this moment (the rest grip's thumb grid); `R`: the right hand's
    {p, f, n} over the pose's (the rest grid: the free hand's place in the view); `thumb_view`: a second
    render from the eye magnified on the right hand, hitgrid/<name>_zoom.png, one from its thumb's side,
    hitgrid/<name>_thumb.png, and the thumb's reads against its index
    (thumb_reads). A pose without the crystal hides it."""
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "TEXTURE"
    sc.display.shading.show_cavity = True
    sc.render.resolution_x, sc.render.resolution_y = 640, 360
    cam_data = bpy.data.cameras.new("eye")
    cam_data.sensor_fit = "VERTICAL"
    cam_data.angle_y = math.radians(float(VIEW_FOV[0]))
    cam_data.clip_start = 0.02
    cam = bpy.data.objects.new("eye", cam_data)
    sc.collection.objects.link(cam)
    side_data = bpy.data.cameras.new("thumb_side")
    side_data.sensor_fit = "VERTICAL"
    side_data.angle_y = math.radians(35.0)
    side_data.clip_start = 0.01
    side_cam = bpy.data.objects.new("thumb_side", side_data)
    sc.collection.objects.link(side_cam)
    cam.rotation_euler = (math.radians(90), 0, 0)
    d = out / "hitgrid"
    d.mkdir(parents=True, exist_ok=True)
    reach = float(poses.cfg["rig"]["reach_m"])
    keep = {k: dict(v) for k, v in poses.grips.items()}
    res, files = {}, []
    for v in variants:
        base = v.get("pose", "crystal")
        for g, fields in v.get("grips", {}).items():
            poses.grips[g] = {**keep[g], **fields}
        spec = {k: x for k, x in v.items() if k in ("cap", "dist", "tilt", "lean", "yaw")}
        over = {"crystal": spec} if spec else {}
        if "R" in v:   # the free hand's place in the view (the rest grid, run p1): {p, f, n} over the pose's R
            over["R"] = v["R"]
        s = poses.state(base, over or None)
        held = "R_c" in poses.cfg["poses"][base]
        for o in crystal_objs:
            o.hide_render = not held
        rig.short = {}
        pose_now(rig, s)
        r = view_reads(s, reach) if held else {}
        if held:
            r["deepest_mm"] = {sd: contact(body, solid, sd)[0] for sd in SIDES}
        r["out_of_reach_mm"] = {k: round(max(x, 0.0) * 1000, 1) for k, x in rig.short.items()}
        sc.camera = cam
        sc.render.filepath = str(d / f"{v['name']}.png")
        bpy.ops.render.render(write_still=True)
        files.append(d / f"{v['name']}.png")
        if v.get("thumb_view"):
            r.update(thumb_reads(rig, body))
            pb, w = rig.arm.pose.bones, rig.arm.matrix_world
            mid = (w @ pb["RightIndexProximal"].head).lerp(w @ pb["RightThumbDistal"].tail, 0.5)
            out_dir = (w @ pb["RightIndexProximal"].head) - (w @ pb["RightLittleProximal"].head)
            fwd = ((w @ pb["RightIndexIntermediate"].head) - (w @ pb["RightHand"].head)).normalized()
            palm = fwd.cross((out_dir - fwd * out_dir.dot(fwd)).normalized())   # thumb_reads' `normal`: the palm side
            # from the eye magnified, from the thumb's side, and from in front of the fingertips and below them, on
            # the palm's side (the gap between the thumb and the index seen across)
            for tag, place, ang in (("zoom", Vector(), 14.0), ("thumb", mid + out_dir.normalized() * 0.35
                                                              + Vector((0.0, -0.08, 0.06)), 35.0),
                                    ("front", mid + fwd * 0.25 + palm * 0.2, 30.0)):
                side_cam.location = place
                side_data.angle_y = math.radians(ang)
                side_cam.rotation_euler = (mid - place).to_track_quat("-Z", "Z").to_euler()
                sc.camera = side_cam
                sc.render.filepath = str(d / f"{v['name']}_{tag}.png")
                bpy.ops.render.render(write_still=True)
                files.append(d / f"{v['name']}_{tag}.png")
        poses.grips.update({k: dict(x) for k, x in keep.items()})
        res[v["name"]] = {"variant": v, "reads": r}
        print("FP_HIT " + json.dumps({v["name"]: r}), flush=True)
        (d / "grid.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    for o in crystal_objs:
        o.hide_render = False
    sheet(d / "sheet.png", files, cols=3, w=640, h=360)


# ------------------------------------------------------------------------------------------ preview
def preview(out: Path, arm, body, clips, crystal_objs, held) -> None:
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "TEXTURE"
    sc.display.shading.show_cavity = True
    sc.render.resolution_x, sc.render.resolution_y = 960, 540
    sc.render.film_transparent = False
    cam_data = bpy.data.cameras.new("eye")
    cam_data.sensor_fit = "VERTICAL"
    cam_data.angle_y = math.radians(float(VIEW_FOV[0]))
    cam_data.clip_start = 0.02
    cam = bpy.data.objects.new("eye", cam_data)
    sc.collection.objects.link(cam)
    cam.rotation_euler = (math.radians(90), 0, 0)
    side = bpy.data.objects.new("side", cam_data.copy())
    sc.collection.objects.link(side)
    side.data.angle_y = math.radians(40)
    side.location = (1.6, 0.35, -0.2)
    side.rotation_euler = (math.radians(90), 0, math.radians(90))
    (out / "preview").mkdir(parents=True, exist_ok=True)
    for name, (act, n, fist) in clips.items():
        for o in crystal_objs:
            o.hide_render = name not in held
        for j in range(6):
            i = round(n * j / 5) if not name.endswith("_Loop") else round(n * j / 6)
            set_frame(arm, act, i, body, fist[i][1:])
            for c, tag in ((cam, "eye"), (side, "side")):
                sc.camera = c
                sc.render.filepath = str(out / "preview" / f"{name}_{tag}_{j}.png")
                bpy.ops.render.render(write_still=True)
        for tag in ("eye", "side"):
            sheet(out / "preview" / f"_{name}_{tag}.png", [out / "preview" / f"{name}_{tag}_{j}.png" for j in range(6)])


def sheet(path: Path, files: list, cols: int = 3, w: int = 480, h: int = 270, crop=None) -> None:
    """The frames side by side (3 x 2 at w x h each), for a quick look; `crop` [x0, y0, x1, y1] (shares of each
    frame, from its top left) shows only that part of every frame, larger (the rest grid's hand region)."""
    import numpy as np
    rows = (len(files) + cols - 1) // cols
    big = np.zeros((rows * h, cols * w, 4), dtype=np.float32)
    for k, f in enumerate(files):
        im = bpy.data.images.load(str(f))
        if crop:
            W0, H0 = im.size
            full = np.array(im.pixels[:], dtype=np.float32).reshape(H0, W0, 4)
            x0, x1 = int(crop[0] * W0), int(crop[2] * W0)
            y0, y1 = H0 - int(crop[3] * H0), H0 - int(crop[1] * H0)   # Blender's rows start at the bottom
            part = full[y0:y1, x0:x1]
            bpy.data.images.remove(im)
            im = bpy.data.images.new("crop", x1 - x0, y1 - y0)
            im.pixels = part.ravel()
        im.scale(w, h)
        px = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)
        r, c = rows - 1 - k // cols, k % cols  # Blender's pixels start at the bottom row
        big[r * h:(r + 1) * h, c * w:(c + 1) * w] = px
        bpy.data.images.remove(im)
    img = bpy.data.images.new(path.stem, cols * w, rows * h)
    img.pixels = big.ravel()
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()


# ---------------------------------------------------------------------------------------------- main
def main(argv) -> None:
    ap = argparse.ArgumentParser(prog="fp_hands_build.py")
    ap.add_argument("--raw")
    ap.add_argument("--out")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--hold-grid", default="", help="a JSON list of hold variants: grid/ and stop (hold_grid)")
    ap.add_argument("--hit-grid", default="", help="a JSON list of crystal poses from the eye: hitgrid/ and stop")
    ap.add_argument("--override", default="", help="a JSON object merged over fp_hands.toml's tables (a review variant)")
    ap.add_argument("--sheets", help="only compose key-frame sheets: a JSON {sheet path: [frame PNGs]}")
    a = ap.parse_args(argv)
    if a.sheets:
        for path, files in json.loads(Path(a.sheets).read_text(encoding="utf-8")).items():
            if isinstance(files, dict):   # {files, cols, w, h}: a grid sheet (the rest grid's, the reference first)
                sheet(Path(path), [Path(f) for f in files["files"]], cols=int(files.get("cols", 3)),
                      w=int(files.get("w", 640)), h=int(files.get("h", 360)), crop=files.get("crop"))
                continue
            sheet(Path(path), [Path(f) for f in files], w=640, h=360)
        return
    raw, out = Path(a.raw), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    cfg = tomllib.loads(CFG.read_text(encoding="utf-8"))
    if a.override:   # a review variant: each table's keys replaced by the JSON's (two levels: [poses.idle] R, ...)
        for top, tables in json.loads(Path(a.override).read_text(encoding="utf-8")).items():
            for name, fields in tables.items():
                if isinstance(fields, dict) and isinstance(cfg.get(top, {}).get(name), dict):
                    cfg[top][name].update(fields)
                else:
                    cfg.setdefault(top, {})[name] = fields
    hands = tomllib.loads(HANDS.read_text(encoding="utf-8"))
    grips = dict(hands.get("grips", {}))
    grips.update(cfg.get("grips", {}))
    VIEW_FOV[0] = float(cfg["view"]["fov_deg"])
    CRYSTAL_SCALE[0] = float(cfg["view"].get("crystal_scale", 1.0))
    CAP_Z[0] = float(cfg["view"].get("cap_z_m", CAP_Z[0]))
    BEND_MAX[0] = float(cfg["view"]["bend_max_deg"])
    fitted = json.loads(FITTED.read_text(encoding="utf-8")) if FITTED.exists() else {}
    for name, fields in fitted.get("poses", {}).items():
        if cfg["poses"].get(name, {}).get("keep"):   # set from the eye in the toml: the old fit never replaces it
            continue
        cfg["poses"].setdefault(name, {}).update(fields)
    arm, body, top, sock, run_seconds, stats = cut(cfg, raw)
    fps = int(cfg["rig"]["fps"])
    sc = bpy.context.scene
    sc.render.fps, sc.render.fps_base = fps, 1.0
    rig = Rig(arm, cfg)
    poses = Poses(cfg, grips)
    for side, roll in fitted.get("hold_roll", {}).items():
        poses.fit[side]["roll"] = float(roll)
    pose_now(rig, poses.state("crystal"))
    crystal_objs, crystal_meshes = load_crystal(HERE.parents[1] / cfg["source"]["crystal"], sock)
    bpy.context.view_layer.update()
    solid = Solid(crystal_meshes, sock)
    stats["solid_skips"] = solid.skipped
    if a.hold_grid:
        hold_grid(out, rig, poses, body, solid, crystal_objs, json.loads(Path(a.hold_grid).read_text(encoding="utf-8")),
                  15 if "hold_roll" in fitted else None)
        return
    stats["hold_fit"] = fit_hold(rig, poses, body, solid, roll_span=15 if "hold_roll" in fitted else None)
    if a.hit_grid:
        hit_grid(out, rig, poses, body, solid, json.loads(Path(a.hit_grid).read_text(encoding="utf-8")), crystal_objs)
        return
    clips, plans, report = {}, {}, {}
    for name, spec in cfg["clips"].items():
        clip = Clip(name, spec, poses, run_seconds)
        rig.short = {}
        act, n, fist = key_clip(rig, clip, fps)
        clips[name] = (act, n, fist)
        plans[name] = fist
        report[name] = {"seconds": round(clip.seconds, 4), "frames": n + 1, "loop": clip.loop,
                        "hit_s": spec.get("hit"), "holds_crystal": clip.held,
                        "out_of_reach_mm": {k: round(max(v, 0.0) * 1000, 1) for k, v in rig.short.items()}}
        if clip.held and clip.keys:   # a held hit's keys as read from the eye (view_reads)
            report[name]["keys_from_eye"] = {f"{t:g}": view_reads(st, float(cfg["rig"]["reach_m"]))
                                             for t, _, st in clip.keys}
    held = {n for n, r in report.items() if r["holds_crystal"]}
    socket = {}
    for name, (act, n, fist) in clips.items():
        set_frame(arm, act, 0)
        bpy.context.view_layer.update()
        socket[name] = [round(x, 5) for x in sock.matrix_world.translation]
    stats["socket_in_view"] = socket
    for name, (act, n, fist) in clips.items():
        worst = {s: [0.0, 1e9] for s in SIDES}
        step = max(1, n // 30)
        frames = sorted(set(list(range(0, n + 1, step)) + [n]))
        for i in frames:
            set_frame(arm, act, i, body, fist[i][1:])
            if name in held:
                for s in SIDES:
                    deep, gap = contact(body, solid, s)
                    worst[s] = [max(worst[s][0], deep), min(worst[s][1], gap)]
        if name in held:
            report[name]["crystal_contact_mm"] = {s: {"deepest_inside": worst[s][0], "nearest_gap": worst[s][1]} for s in SIDES}
    if a.preview:
        preview(out, arm, body, clips, crystal_objs, held)
    for o in crystal_objs:
        bpy.data.objects.remove(o, do_unlink=True)
    for o in list(bpy.data.objects):
        if o.type == "CAMERA":
            bpy.data.objects.remove(o, do_unlink=True)
    two = "fist_L" in body.data.shape_keys.key_blocks
    for k in ("fist", "fist_L") if two else ("fist",):
        body.data.shape_keys.key_blocks[k].value = 0.0
    arm.animation_data.action = clips["Idle_Loop"][0]
    sc.frame_set(0)
    bpy.ops.object.select_all(action="DESELECT")
    for o in [x for x in (arm, body, top, sock) if x is not None]:
        o.select_set(True)
    for _ in range(3):  # the character's unused head maps, actions and meshes: the .blend keeps only the hands
        bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "fp_hands.blend"), compress=True)
    glb = out / "fp_hands.glb"
    opts = {**EG.options(textured=True), "use_selection": True, "export_morph": True, "export_morph_animation": False}
    if bpy.ops.export_scene.gltf(filepath=str(glb), **opts) != {"FINISHED"}:
        raise SystemExit("the glTF exporter failed")
    EG.fix_zero_tangents(str(glb))
    if two:   # the targets in the mesh's order: fist, then fist_L
        got = F.key_weights(str(glb), ["fist", "fist_L"],
                            {n: {"fist": [(sh, w) for sh, w, _ in p], "fist_L": [(sh, wl) for sh, _, wl in p]}
                             for n, p in plans.items()})
    else:
        got = F.key_weights(str(glb), "fist", {n: [(sh, w) for sh, w, _ in p] for n, p in plans.items()})
    stats["fist_weights"] = got
    stats["clips"] = report
    stats["arm_lengths_m"] = [round(rig.la, 4), round(rig.lb, 4)]
    stats["vm_fov"] = VIEW_FOV[0]
    stats["crystal_scale"] = CRYSTAL_SCALE[0]
    stats["fitted_from"] = fitted.get("source")
    (out / "build.json").write_text(json.dumps(stats, indent=1), encoding="utf-8")
    print("FP_HANDS " + json.dumps(stats))


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
