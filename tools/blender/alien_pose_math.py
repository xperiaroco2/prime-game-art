"""The photo poses on the alien (art #196): held poses in two layers, legs and arms, solved per character on its own
rest skeleton and skin, and measured (pure Python, no bpy; tools/blender/alien_poses.py is the Blender side).

A pose is data (anim_sets/alien_poses.toml): directions in the body's axes (out, fwd, up; "out" is toward the side
the bone is on, the character faces -Y), goals at landmarks of its own skin (the waist's side, the back of the head,
the front of the chest), and contacts solved on the skin (a planted foot's sole, the kneeling knee, the seat on the
floor; a palm on the hip, the heart's index tips together). A re-run on another body of the same skeleton re-poses it.

The layers: a fixed bone split (SPLIT) gives each bone to the legs or the arms. The arms are solved over the
reference legs (`Stand`, whose Spine is at rest), so their local rotations carry onto any legs. A pair is the legs'
channels plus the arms' channels, nothing else (compose).

The skin (`skin` dict, from alien_poses.py --dump): the rest vertices in armature space, each with its bone weights
(at most 4, normalised) and the bone that weighs most. The measures run linear blend skinning on it, as Godot does.
"""
from __future__ import annotations

import math
import tomllib
from pathlib import Path

import anim_edit_math as M
import alien_stride_math as S

HERE = Path(__file__).resolve().parent
DATA = HERE / "anim_sets" / "alien_poses.toml"
SIDES = ("Left", "Right")
LEG_CHAIN = ("UpperLeg", "LowerLeg", "Foot", "Toes")
FINGERS = ("Thumb", "Index", "Middle", "Ring", "Little")
PHALANX = {"Thumb": ("Metacarpal", "Proximal", "Distal"), "Index": ("Proximal", "Intermediate", "Distal")}
LEGS_PREFIX, ARMS_PREFIX = "PoseLegs_", "PoseArms_"


# --------------------------------------------------------------------------------------------- small vectors
def add(a, b): return tuple(x + y for x, y in zip(a, b))
def sub(a, b): return tuple(x - y for x, y in zip(a, b))
def mul(a, k): return tuple(x * k for x in a)
def dot(a, b): return sum(x * y for x, y in zip(a, b))
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def length(a): return math.sqrt(dot(a, a))


def norm(a):
    n = length(a)
    return mul(a, 1.0 / n) if n > 1e-12 else tuple(a)


def body(side: str, v) -> tuple:
    """(out, fwd, up) on a side -> armature axes (+X is the character's left, -Y its front, +Z up)."""
    s = 1.0 if side == "Left" else -1.0
    return (s * v[0], -v[1], v[2])


def turn_q(pitch=0.0, roll=0.0, yaw=0.0, side: str = "Left"):
    """A turn in the body's axes (degrees): pitch + leans forward, roll + toward `side`'s out, yaw + turns the front
    toward `side`'s out; applied yaw, then pitch, then roll (world-fixed axes)."""
    s = 1.0 if side == "Left" else -1.0
    q = M.q_axis_angle((0.0, 0.0, 1.0), s * yaw)
    q = M.q_mul(M.q_axis_angle((1.0, 0.0, 0.0), pitch), q)
    return M.q_mul(M.q_axis_angle((0.0, 1.0, 0.0), s * roll), q)


def rot3(q):
    return [row[:3] for row in S.m4((0.0, 0.0, 0.0), q)[:3]]


def axes_q(x, y):
    """The rotation whose columns are x (made normal to y), y and z = x cross y."""
    y = norm(y)
    x = norm(sub(x, mul(y, dot(x, y))))
    z = cross(x, y)
    return S.mat_q([[x[i], y[i], z[i]] for i in range(3)])


def frame_q(f0, n0, f, n):
    """The rotation taking the pair (f0, n0) onto (f, n) (each n made normal to its f)."""
    def m(a, b):
        a = norm(a)
        b = norm(sub(b, mul(a, dot(a, b))))
        c = cross(a, b)
        return [[a[i], b[i], c[i]] for i in range(3)]
    A, B = m(f0, n0), m(f, n)
    return S.mat_q([[sum(B[i][k] * A[j][k] for k in range(3)) for j in range(3)] for i in range(3)])


def axis(P, bone, k: int):
    """A posed bone's axis k (0 x, 1 y, 2 z) in armature space."""
    return (P[bone][0][k], P[bone][1][k], P[bone][2][k])


# ------------------------------------------------------------------------------------------------- the split
def owner(bone: str) -> str:
    """'legs' or 'arms': the layer that owns the bone (Root, Hips, Spine and the legs to the toes are the legs')."""
    if bone in ("Root", "Hips", "Spine") or any(bone.endswith(p) for p in LEG_CHAIN):
        return "legs"
    return "arms"


def split(bones) -> dict:
    return {"legs": sorted(b for b in bones if owner(b) == "legs"), "arms": sorted(b for b in bones if owner(b) == "arms")}


# --------------------------------------------------------------------------------------------- one pose's rig
class Rig:
    """One frame's pose basis on the skeleton (every bone keyed; the rest is identity)."""

    def __init__(self, skel: dict):
        self.skel = S.prepare(skel)
        self.loc = {b: (0.0, 0.0, 0.0) for b in self.skel["order"]}
        self.rot = {b: (1.0, 0.0, 0.0, 0.0) for b in self.skel["order"]}
        self._P = None

    def P(self) -> dict:
        if self._P is None:
            self._P = S.fk(self.skel, self.clip(), 0)
        return self._P

    def clip(self, n: int = 1, name: str = "") -> dict:
        return {"name": name, "fps": 24, "loc": {b: [v] * n for b, v in self.loc.items()},
                "rot": {b: [q] * n for b, q in self.rot.items()}}

    def rest(self, bone):
        return self.skel["rest"][bone]

    def head(self, bone):
        return S.pos(self.P()[bone])

    def set_world(self, bone: str, q, at=None) -> None:
        """The bone's world rotation set to q (its head kept, or moved to `at`: only a free bone, Hips)."""
        P = self.P()
        m = S.m4(at if at is not None else S.pos(P[bone]), q)
        loc, rq = S.basis_of(self.skel, {**P, bone: m}, bone)
        if at is not None:
            self.loc[bone] = loc
        self.rot[bone] = rq
        self._P = None

    def world_q(self, bone):
        return S.mat_q(self.P()[bone])

    def rest_q(self, bone):
        return S.mat_q(self.rest(bone))

    def turn_world(self, bone: str, q) -> None:
        """The bone turned by q in world axes about its head (its children follow)."""
        self.set_world(bone, M.q_mul(q, self.world_q(bone)))

    def local(self, bone: str, q) -> None:
        """The bone's basis rotation set to q (from its rest: a solve that runs again gives the same pose)."""
        self.rot[bone] = M.q_norm(q)
        self._P = None

    def length(self, a: str, b: str) -> float:
        return length(sub(S.pos(self.rest(b)), S.pos(self.rest(a))))

    def limb(self, upper: str, lower: str, d_up, d_low, ref_q=None) -> None:
        """Upper and lower bone aimed along d_up and d_low, sharing the hinge cross(d_up, d_low) as their x axis (the
        knee's and the elbow's own axis: no sideways bend); a straight limb keeps the swing of ref_q (its rest)."""
        h = cross(norm(d_up), norm(d_low))
        if length(h) < 0.02:  # straight: the hinge from the upper bone's rest swung onto d_up
            q0 = ref_q or self.rest_q(upper)
            sw = M.q_mul(S.rot_between(M.q_rotate(q0, (0.0, 1.0, 0.0)), norm(d_up)), q0)
            h = M.q_rotate(sw, (1.0, 0.0, 0.0))
        self.set_world(upper, axes_q(h, d_up))
        self.set_world(lower, axes_q(h, d_low))


def ik_mid(root, goal, la: float, lb: float, pole):
    """The middle joint of a two-bone chain from root to goal (lengths la, lb), on the pole's side of the root-goal
    line (the goal pulled in to 99.95 % of the reach). Unlike alien_clip_edit.two_bone it takes the pole as a
    direction, not the clip's own knee."""
    dv = sub(goal, root)
    d = max(1e-6, min(length(dv), (la + lb) * 0.9995))
    ax = norm(dv)
    p = norm(sub(pole, mul(ax, dot(pole, ax))))
    x = (la * la - lb * lb + d * d) / (2.0 * d)
    h = math.sqrt(max(0.0, la * la - x * x))
    return add(add(root, mul(ax, x)), mul(p, h))


# ------------------------------------------------------------------------------------------------------ skin
def group_of(bone: str) -> str:
    """A skin bone's group: torso, head, root, or per side hand, forearm, upperarm, thigh, shin, foot."""
    if bone in ("Hips", "Spine", "Chest", "UpperChest"):
        return "torso"
    if bone == "Root":
        return "root"
    side = next((s for s in SIDES if bone.startswith(s)), None)
    if side is None:
        return "head"  # Neck, Head, Jaw, the crest
    rest = bone[len(side):]
    if rest == "Eye":
        return "head"
    for g, parts in (("thigh", ("UpperLeg",)), ("shin", ("LowerLeg",)), ("foot", ("Foot", "Toes")),
                     ("upperarm", ("Shoulder", "UpperArm")), ("forearm", ("LowerArm",))):
        if rest in parts:
            return f"{g}_{side}"
    return f"hand_{side}"


def tube_bones(group: str, bones) -> list:
    """The bones whose tubes stand for a group's volume (a bone name stands for itself)."""
    return [b for b in bones if group_of(b) == group] if group not in bones else [group]


def prepare_skin(skin: dict) -> dict:
    """The dumped skin with the index lists per group and per dominant bone."""
    if "by_group" in skin:
        return skin
    by_group, by_bone = {}, {}
    for i, d in enumerate(skin["dom"]):
        b = skin["bones"][d]
        by_group.setdefault(group_of(b), []).append(i)
        by_bone.setdefault(b, []).append(i)
    return {**skin, "by_group": by_group, "by_bone": by_bone}


def skin_mats(skel: dict, P: dict, bones: list) -> list:
    """Per skin bone the 3x4 skinning matrix P[b] rest[b]^-1."""
    out = []
    for b in bones:
        m = M.mat_mul(P[b], S.rigid_inv(skel["rest"][b]))
        out.append((m[0], m[1], m[2]))
    return out


def pose_points(skin: dict, mats: list, idx=None) -> list:
    """Linear blend skinning of the points (all, or the index list idx)."""
    pts, ws = skin["points"], skin["weights"]
    out = []
    for i in (range(len(pts)) if idx is None else idx):
        x, y, z = pts[i]
        px = py = pz = 0.0
        for b, w in ws[i]:
            r0, r1, r2 = mats[b]
            px += w * (r0[0] * x + r0[1] * y + r0[2] * z + r0[3])
            py += w * (r1[0] * x + r1[1] * y + r1[2] * z + r1[3])
            pz += w * (r2[0] * x + r2[1] * y + r2[2] * z + r2[3])
        out.append((px, py, pz))
    return out


class Posed:
    """A rig's pose applied to the skin, the groups' points made on demand."""

    def __init__(self, skel: dict, skin: dict, P: dict):
        self.skel, self.skin, self.P = skel, skin, P
        self.mats = skin_mats(skel, P, skin["bones"])
        self._g = {}

    def group(self, g: str) -> list:
        if g not in self._g:
            idx = self.skin["by_group"].get(g) if g in self.skin["by_group"] else self.skin["by_bone"].get(g, [])
            self._g[g] = pose_points(self.skin, self.mats, idx)
        return self._g[g]

    def groups(self, names) -> list:
        return [p for g in names for p in self.group(g)]

    def lowest(self, names) -> float:
        return min((p[2] for p in self.groups(names)), default=0.0)


def nearest_gap(A: list, B: list, reach: float = 0.06, cell: float = 0.02) -> float:
    """The least distance between two point sets (a hash grid of B; over `reach` the result is `reach`)."""
    grid = {}
    for p in B:
        grid.setdefault((int(math.floor(p[0] / cell)), int(math.floor(p[1] / cell)), int(math.floor(p[2] / cell))),
                        []).append(p)
    k = int(math.ceil(reach / cell))
    best = reach * reach
    for p in A:
        cx, cy, cz = (int(math.floor(c / cell)) for c in p)
        for i in range(cx - k, cx + k + 1):
            for j in range(cy - k, cy + k + 1):
                for m in range(cz - k, cz + k + 1):
                    for q in grid.get((i, j, m), ()):
                        d = (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2
                        if d < best:
                            best = d
    return math.sqrt(best)


# ---------------------------------------------------------------------------------------- the body's volumes
TUBE_SLICES, TUBE_SECTORS = 8, 12
HEAD_BACK_UP = 0.6  # the back of the skull's landmark: this far from the Head bone's head up to the eyes
THIGH_SKIP = 3  # of the thigh tube's slices from the hip, not counted when skin goes into a thigh (measure)


def tube(skel: dict, skin: dict, bone: str) -> dict | None:
    """A bone's generalised cylinder from the rest points it dominates: along its axis (local y) TUBE_SLICES slices
    over the points' extent, per slice TUBE_SECTORS sectors around it, each the second-largest radius in it (the
    surface; an empty sector the slice's median). Its volume and centroid too (the centre of mass's masses)."""
    idx = skin["by_bone"].get(bone, [])
    if len(idx) < 12:
        return None
    inv = S.rigid_inv(skel["rest"][bone])
    loc = []
    for i in idx:
        x, y, z = skin["points"][i]
        loc.append(tuple(inv[r][0] * x + inv[r][1] * y + inv[r][2] * z + inv[r][3] for r in range(3)))
    y0, y1 = min(p[1] for p in loc), max(p[1] for p in loc)
    dy = max(1e-4, (y1 - y0) / TUBE_SLICES)
    bins = [[[] for _ in range(TUBE_SECTORS)] for _ in range(TUBE_SLICES)]
    for x, y, z in loc:
        s = min(TUBE_SLICES - 1, int((y - y0) / dy))
        a = int(((math.atan2(z, x) + math.pi) / (2 * math.pi)) * TUBE_SECTORS) % TUBE_SECTORS
        bins[s][a].append(math.hypot(x, z))
    radius = []
    for row in bins:
        filled = sorted(sorted(b)[-2] if len(b) > 1 else b[0] for b in row if b)
        med = filled[len(filled) // 2] if filled else 0.0
        radius.append([(sorted(b)[-2] if len(b) > 1 else b[0]) if b else med for b in row])
    vol = sum(r * r * math.pi / TUBE_SECTORS * dy for row in radius for r in row)
    c = tuple(sum(p[k] for p in loc) / len(loc) for k in range(3))
    return {"bone": bone, "y0": y0, "dy": dy, "radius": radius, "volume": vol, "centroid_local": c}


def tube_depths(t: dict, P: dict, pts: list, first: int = 0) -> list:
    """Per point how deep it is inside the posed tube (m; 0 when outside); `first`: its slices from that one on (the
    ones before skipped)."""
    inv = S.rigid_inv(P[t["bone"]])
    out = []
    y0, dy = t["y0"], t["dy"]
    for p in pts:
        y = inv[1][0] * p[0] + inv[1][1] * p[1] + inv[1][2] * p[2] + inv[1][3]
        s = (y - y0) / dy
        if s < first or s >= TUBE_SLICES:
            out.append(0.0)
            continue
        x = inv[0][0] * p[0] + inv[0][1] * p[1] + inv[0][2] * p[2] + inv[0][3]
        z = inv[2][0] * p[0] + inv[2][1] * p[1] + inv[2][2] * p[2] + inv[2][3]
        a = int(((math.atan2(z, x) + math.pi) / (2 * math.pi)) * TUBE_SECTORS) % TUBE_SECTORS
        out.append(max(0.0, t["radius"][int(s)][a] - math.hypot(x, z)))
    return out


def tube_depth(t: dict, P: dict, pts: list, first: int = 0) -> float:
    """The deepest any point goes inside the posed tube (m; 0 when none is inside)."""
    return max(tube_depths(t, P, pts, first), default=0.0)


# ------------------------------------------------------------------------------------------------ the model
class Model:
    """A character: its skeleton, skin, tubes and landmarks, and the pose data."""

    def __init__(self, skel: dict, skin: dict, data: dict):
        self.skel = S.prepare(skel)
        self.data = data
        self.skin = prepare_skin(skin)
        self.tubes = {b: t for b in skin["bones"] if (t := tube(self.skel, self.skin, b)) is not None}
        r = Rig(self.skel)
        self.leg_len = r.length("LeftUpperLeg", "LeftLowerLeg") + r.length("LeftLowerLeg", "LeftFoot")
        self.hand_len = r.length("LeftHand", "LeftMiddleProximal") + sum(
            r.length(a, b) for a, b in (("LeftMiddleProximal", "LeftMiddleIntermediate"),
                                        ("LeftMiddleIntermediate", "LeftMiddleDistal")))
        self.rest_posed = Posed(self.skel, self.skin, r.P())
        self.marks = self._landmarks()

    def _landmarks(self) -> dict:
        """Rest skin points the arms reach for: per side the waist's side (the torso's outermost point at the Spine's
        head height), the back of the skull (HEAD_BACK_UP), the chest's front (the UpperChest's middle)."""
        rp = self.rest_posed
        torso = rp.groups(["torso"])
        headp = rp.group("head")
        out = {}
        zs = S.pos(self.skel["rest"]["Spine"])[2]
        zc = (S.pos(self.skel["rest"]["UpperChest"])[2] + S.pos(self.skel["rest"]["Neck"])[2]) / 2
        ze = S.pos(self.skel["rest"]["LeftEye"])[2]
        zh = S.pos(self.skel["rest"]["Head"])[2]
        for side in SIDES:
            s = 1.0 if side == "Left" else -1.0
            band = [p for p in torso if abs(p[2] - zs) < 0.02 and p[0] * s > 0]
            out[f"waist_{side}"] = max(band, key=lambda p: p[0] * s)
            # the skull's back, not a crest's: HEAD_BACK_UP of the way from the Head bone up to the eyes (round 2: the
            # chameleon's crest at the eyes' height put the wrists 32 cm behind the head, the arms straight up)
            zb = zh + HEAD_BACK_UP * (ze - zh)
            back = [p for p in headp if abs(p[2] - zb) < 0.015 and abs(p[0]) < 0.02]
            out["head_back"] = max(back, key=lambda p: p[1])
            # the brow over the eye: the head's most forward skin a little above the eye, at the eye's side
            eye = S.pos(self.skel["rest"][f"{side}Eye"])
            brow = [p for p in headp if abs(p[2] - (eye[2] + 0.025)) < 0.015 and abs(p[0] - eye[0] * 0.7) < 0.02]
            out[f"brow_{side}"] = min(brow, key=lambda p: p[1])
        front = [p for p in torso if abs(p[2] - zc) < 0.02 and abs(p[0]) < 0.03]
        out["chest_front"] = min(front, key=lambda p: p[1])
        return {k: tuple(round(c, 5) for c in v) for k, v in out.items()}

    # ------------------------------------------------------------------------------------------- the legs
    def legs(self, name: str) -> Rig:
        spec = self.data["legs"][name]
        r = Rig(self.skel)
        L = self.leg_len
        hips0 = r.head("Hips")
        h = spec.get("hips", {})
        sh = h.get("shift", [0.0, 0.0])  # (+X the character's left, fwd) in leg lengths
        at = (hips0[0] + sh[0] * L, hips0[1] - sh[1] * L, hips0[2] - h.get("drop", 0.0) * L)
        r.set_world("Hips", M.q_mul(turn_q(*h.get("turn", (0, 0, 0))), r.rest_q("Hips")), at=at)
        sp = spec.get("spine", {})
        if sp.get("turn"):
            r.turn_world("Spine", turn_q(*sp["turn"]))
        if sp.get("level"):  # p3: the Spine counter-turned so the chest's up is the world's (`level` of the way):
            # the arms' directions are in the chest's axes, so a level chest keeps their meaning in the world on
            # every legs pose (a horizontal arm stays horizontal, an arm up stays up)
            F = M.q_mul(r.world_q("UpperChest"), M.q_conj(r.rest_q("UpperChest")))
            u = M.q_rotate(F, (0.0, 0.0, 1.0))
            ang = math.degrees(math.acos(max(-1.0, min(1.0, u[2]))))
            if ang > 0.01:
                r.turn_world("Spine", M.q_axis_angle(norm(cross(u, (0.0, 0.0, 1.0))), ang * sp["level"]))
        legs = {side: spec.get(side) or spec.get("both") or {"mode": "plant"} for side in SIDES}
        for _ in range(4):  # free legs, the fit (the knee, the seat onto the floor), then the planted feet
            for side, leg in legs.items():
                if leg["mode"] in ("fk", "kneel"):
                    self._leg_fk(r, side, leg)
            low = Posed(self.skel, self.skin, r.P()).lowest(h["fit"]) if h.get("fit") else 0.0
            if abs(low) > 1e-4:
                r.set_world("Hips", r.world_q("Hips"), at=add(r.head("Hips"), (0.0, 0.0, -low)))
                for side, leg in legs.items():
                    if leg["mode"] in ("fk", "kneel"):
                        self._leg_fk(r, side, leg)
            for side, leg in legs.items():
                if leg["mode"] == "plant":
                    self._leg_plant(r, side, leg)
            if not h.get("fit") or abs(Posed(self.skel, self.skin, r.P()).lowest(h["fit"])) < 5e-4:
                break
        return r

    def _foot(self, r: Rig, side: str, leg: dict) -> None:
        """The foot's world rotation: its rest turned by toe-out yaw, then pitch (+ the toes up), then roll."""
        q = turn_q(pitch=-leg.get("foot_pitch", 0.0), roll=leg.get("foot_roll", 0.0), yaw=leg.get("toe_out", 0.0),
                   side=side)
        if leg.get("foot"):
            ft = r.rest_q(f"{side}Foot")
            f0 = M.q_rotate(ft, (0.0, 1.0, 0.0))
            n0 = M.q_rotate(ft, (1.0, 0.0, 0.0))
            r.set_world(f"{side}Foot", M.q_mul(frame_q(f0, n0, body(side, leg["foot"]), n0), ft))
        else:
            r.set_world(f"{side}Foot", M.q_mul(q, r.rest_q(f"{side}Foot")))
        if leg.get("toes"):
            r.local(f"{side}Toes", M.q_axis_angle((1.0, 0.0, 0.0), leg["toes"]))

    def _leg_plant(self, r: Rig, side: str, leg: dict) -> None:
        """A planted foot: the ankle's goal at its rest place moved by `ankle` (out, fwd in leg lengths), the foot
        turned, the ankle's height solved so the foot's skin just meets the floor; the knee toward `knee`."""
        L = self.leg_len
        up, lo = f"{side}UpperLeg", f"{side}LowerLeg"
        la, lb = r.length(up, lo), r.length(lo, f"{side}Foot")
        a0 = S.pos(self.skel["rest"][f"{side}Foot"])
        off = body(side, (*leg.get("ankle", (0.0, 0.0)), 0.0))
        goal = (a0[0] + off[0] * L, a0[1] + off[1] * L, a0[2])
        pole = body(side, leg.get("knee", (0.0, 1.0, 0.0)))
        for _ in range(3):
            hip = r.head(up)
            knee = ik_mid(hip, goal, la, lb, pole)
            r.limb(up, lo, sub(knee, hip), sub(goal, knee))
            self._foot(r, side, leg)
            low = Posed(self.skel, self.skin, r.P()).lowest([f"foot_{side}"])
            goal = (goal[0], goal[1], goal[2] - low)
            if abs(low) < 1e-4:
                break

    def _leg_fk(self, r: Rig, side: str, leg: dict) -> None:
        """A free leg by directions (thigh, shin, foot); `kneel`: the shin's pitch solved so the ball of the foot is
        at its rest height (the toes bent onto the floor)."""
        up, lo = f"{side}UpperLeg", f"{side}LowerLeg"
        thigh = body(side, leg["thigh"])
        if leg["mode"] == "kneel":
            lo_, hi_ = -30.0, 80.0
            for _ in range(18):  # the shin's pitch: the foot's lowest skin (the ball) just on the floor
                a = (lo_ + hi_) / 2
                shin = body(side, (leg.get("shin_out", 0.0), -math.cos(math.radians(a)), math.sin(math.radians(a))))
                r.limb(up, lo, thigh, shin)
                self._foot(r, side, leg)
                if Posed(self.skel, self.skin, r.P()).lowest([f"foot_{side}"]) > 0.0:
                    hi_ = a
                else:
                    lo_ = a
            ball = r.head(f"{side}Toes")
            # the toes laid flat, pointing on along the floor from the ball
            fdir = norm(sub(ball, r.head(f"{side}Foot")))
            flat = norm((fdir[0], fdir[1], 0.0))
            t0 = r.world_q(f"{side}Toes")
            r.set_world(f"{side}Toes", M.q_mul(S.rot_between(M.q_rotate(t0, (0.0, 1.0, 0.0)), flat), t0))
        else:
            r.limb(up, lo, thigh, body(side, leg["shin"]))
            self._foot(r, side, leg)

    # ------------------------------------------------------------------------------------------- the arms
    def arms(self, name: str, ref: Rig | None = None, legs: str = "") -> Rig:
        """The arms' pose over the reference legs (Stand): chest, neck and head turns, then per arm FK directions or
        a goal at a landmark (two-bone IK, then the contact solved on the skin), the hand's frame and the fingers.
        `ref`, `legs`: a per-legs variant's legs (Model.variants); on `thigh_hand`'s legs the hip hand rests on the
        thigh (round 3)."""
        spec = self.data["arms"][name]
        r = ref or self.legs(self.data["reference_legs"])
        for b in ("Chest", "UpperChest", "Neck", "Head"):
            if spec.get(b):
                r.turn_world(b, turn_q(*spec[b]))
        for side in SIDES:
            arm = spec.get(side) or spec.get("both")
            if arm is None:
                continue
            if ref is not None and arm.get("variant"):  # a per-legs variant's own settings (the hip hand's fingers)
                arm = {**arm, **arm["variant"]}
            if ref is not None and legs in arm.get("legs_variant", {}):  # q3: one legs pose's own settings on top
                arm = {**arm, **arm["legs_variant"][legs]}  # (the akimbo fist higher where the thighs rise to the waist)
            if arm.get("shoulder"):
                r.turn_world(f"{side}Shoulder", turn_q(*arm["shoulder"], side=side))
            if arm["mode"] == "fk":
                self._arm_fk(r, side, arm)
            elif ref is not None and arm.get("clear") and thigh_side(self.data, legs, side):
                self._arm_thigh(r, side, arm, legs)
            else:
                self._arm_goal(r, side, arm)
        for c in spec.get("contacts", []):
            if c.get("solve") == "meet":
                self._meet(r, spec, c)
        return r

    def _chest(self, r: Rig):
        """The chest's frame change from rest (the arms' directions are in the chest's axes)."""
        return M.q_mul(r.world_q("UpperChest"), M.q_conj(r.rest_q("UpperChest")))

    def _hand(self, r: Rig, side: str, arm: dict) -> None:
        F = self._chest(r)
        hq = r.rest_q(f"{side}Hand")
        f0 = M.q_rotate(hq, (0.0, 1.0, 0.0))
        n0 = (0.0, 0.0, -1.0)  # the T pose's palms face down
        if arm["fingers_dir"] == "forearm":  # a straight wrist (p3: the fists): the hand along the forearm
            f = norm(sub(r.head(f"{side}Hand"), r.head(f"{side}LowerArm")))
        else:
            f = M.q_rotate(F, body(side, arm["fingers_dir"]))
        n = M.q_rotate(F, body(side, arm["palm"]))
        if arm.get("hand_roll"):  # the palm turned about the fingers' direction (+ the thumb side toward out)
            n = M.q_rotate(M.q_axis_angle(f, arm["hand_roll"] * (1.0 if side == "Left" else -1.0)), n)
        r.set_world(f"{side}Hand", M.q_mul(frame_q(f0, n0, f, n), hq))
        # half the hand's twist about the forearm carried by the forearm (no wrapped wrist)
        lo = f"{side}LowerArm"
        ax = norm(sub(r.head(f"{side}Hand"), r.head(lo)))
        rel = M.q_mul(r.world_q(f"{side}Hand"), M.q_conj(M.q_mul(r.world_q(lo), M.q_mul(
            M.q_conj(r.rest_q(lo)), hq))))
        tw = 2.0 * math.degrees(math.atan2(dot(rel[1:], ax), rel[0]))
        tw = (tw + 180.0) % 360.0 - 180.0
        k = arm.get("forearm_twist", 0.5)
        hand_q = r.world_q(f"{side}Hand")
        r.turn_world(lo, M.q_axis_angle(ax, tw * k))
        r.set_world(f"{side}Hand", hand_q)
        self._fingers(r, side, arm.get("grip", "flat"))

    def _fingers(self, r: Rig, side: str, grip: str) -> None:
        """A hand shape of the library (`[grips]`, p3): per finger the curl of its three bones about their own x;
        `ThumbTurn` [roll, swing] (degrees) turns the thumb's base about its length (y) and toward the palm (z) before
        its curl (the left hand's; the right's mirrored), so a fist's thumb lies over the index and a flat hand's beside
        it (a curl alone turns it about one axis only, p1)."""
        g = self.data["grips"][grip]
        r.grips = {**getattr(r, "grips", {}), side: grip}  # h1: the clip's corrective shapes follow its grips
        for f in FINGERS:
            names = PHALANX.get(f, PHALANX["Index"])
            curl = g.get(f, g.get("all", [0.0, 0.0, 0.0]))
            for i, (ph, deg) in enumerate(zip(names, curl)):
                q = M.q_axis_angle((1.0, 0.0, 0.0), deg)
                if i == 0 and g.get("spread") and f != "Thumb":
                    k = {"Index": -1.0, "Middle": -0.3, "Ring": 0.4, "Little": 1.0}[f]
                    # q3 (`mirror` in the grip): mirrored like the thumb's turn (one sign drew the left hand's fingers
                    # apart, the right's together); a flag, so the check still composes older builds' data as built
                    k *= -1.0 if g.get("mirror") and side == "Right" else 1.0
                    q = M.q_mul(M.q_axis_angle((0.0, 0.0, 1.0), g["spread"] * k), q)
                if i == 0 and (g.get(f"{f}Spread") or g.get(f"{f}Twist")):
                    # h1 (each finger on its own): the base turned toward the thumb side (+Spread, about z) and about
                    # its length (+Twist, about y), the left hand's degrees, mirrored on the right
                    k = 1.0 if side == "Left" else -1.0
                    q = M.q_mul(M.q_axis_angle((0.0, 0.0, 1.0), g.get(f"{f}Spread", 0.0) * k),
                                M.q_mul(M.q_axis_angle((0.0, 1.0, 0.0), g.get(f"{f}Twist", 0.0) * k), q))
                if i == 0 and f == "Thumb" and g.get("ThumbTurn"):
                    roll, swing = (v * (1.0 if side == "Left" else -1.0) for v in g["ThumbTurn"])  # mirrored
                    q = M.q_mul(M.q_axis_angle((0.0, 0.0, 1.0), swing), M.q_mul(M.q_axis_angle((0.0, 1.0, 0.0), roll), q))
                r.local(f"{side}{f}{ph}", q)

    def _arm_fk(self, r: Rig, side: str, arm: dict) -> None:
        F = self._chest(r)
        r.limb(f"{side}UpperArm", f"{side}LowerArm", M.q_rotate(F, body(side, arm["upper"])),
               M.q_rotate(F, body(side, arm["lower"])))
        self._hand(r, side, arm)

    def _arm_goal(self, r: Rig, side: str, arm: dict, goal=None) -> None:
        """The wrist at a landmark (+ `offset` in hand lengths, chest axes), the elbow toward `elbow`; then the gap
        between the hand and the `touch` group closed to `gap_cm` along `push` (three passes on the skin)."""
        F = self._chest(r)
        up, lo = f"{side}UpperArm", f"{side}LowerArm"
        la, lb = r.length(up, lo), r.length(lo, f"{side}Hand")
        if goal is None:
            mark = self.marks.get(f"{arm['at']}_{side}", self.marks.get(arm["at"]))
            goal = add(mark, mul(body(side, arm.get("offset", (0, 0, 0))), self.hand_len))
            goal = add(r.head("UpperChest"), M.q_rotate(F, sub(goal, S.pos(self.skel["rest"]["UpperChest"]))))
        pole = M.q_rotate(F, body(side, arm.get("elbow", (1.0, -0.3, 0.0))))
        push = norm(M.q_rotate(F, body(side, arm.get("push", (-1.0, 0.0, 0.0)))))
        # `clear` moves the wrist up the chest, or along `clear_dir` (chest axes: back along the hip's side)
        lift = norm(M.q_rotate(F, body(side, arm.get("clear_dir", (0.0, 0.0, 1.0)))))
        clear = [t for g in arm.get("clear", ()) for t in tube_bones(g.format(side=side), self.tubes)]
        n = arm.get("passes", 9)  # p3: the akimbo fist's variants take more passes to settle (clear, then touch)
        for it in range(n):
            sh = r.head(up)
            el = ik_mid(sh, goal, la, lb, pole)
            r.limb(up, lo, sub(el, sh), sub(goal, el))
            self._hand(r, side, arm)
            if not (arm.get("touch") or clear) or it == n - 1:
                break
            pz = Posed(self.skel, self.skin, r.P())
            # `clear`: the hand out of those groups (a raised thigh) by moving the wrist up the body, then touch again
            cd = max((tube_depth(self.tubes[t], r.P(), pz.group(f"hand_{side}"), THIGH_SKIP if "UpperLeg" in t else 0)
                      for t in clear), default=0.0)
            if cd > 0.002:
                goal = add(goal, mul(lift, cd + 0.004))
                continue
            if not arm.get("touch"):
                break
            # the skin that touches: the whole hand, or `touch_by` (the palm's own bone: a thumb kept off the body)
            by = arm.get("touch_by", "hand_{side}").format(side=side)
            gap = nearest_gap(pz.group(by), pz.groups(arm["touch"]), reach=0.15)
            depth = max(tube_depth(self.tubes[b], r.P(), pz.group(by))
                        for b in tube_bones(arm["touch"][0], self.tubes))
            # inside the volume: back out by the depth; outside: in by the gap (the point sets' gap is never 0)
            # (a depth counts only where the skins touch: a small bone's tube misreads from afar)
            move = -depth if depth > 0.003 and gap < 0.005 else gap - arm.get("gap_cm", 0.3) / 100.0
            if abs(move) < 0.002:
                break
            goal = add(goal, mul(push, move))
        r._goal = getattr(r, "_goal", {})
        r._goal[side] = goal

    def _arm_thigh(self, r: Rig, side: str, arm: dict, legs: str) -> None:
        """The hip hand on a deep legs pose (round 3: Squat, Sit): the hand rests on the top of its thigh by the hip
        crease, the fingers forward along the thigh (`fingers_add` on top, chest axes), the palm down, the elbow out
        and back; the wrist starts `lift` hand lengths over the thigh's top skin `along` of the way from the hip to
        the knee (per legs pose: Sit's thighs rise steeply, its crease is under the belly), then the touch closes the gap to
        the thigh's skin along `push` (`[thigh_hand]` in the TOML)."""
        th = self.data["thigh_hand"]
        hip, knee = r.head(f"{side}UpperLeg"), r.head(f"{side}LowerLeg")
        d = norm(sub(knee, hip))
        p = add(hip, mul(sub(knee, hip), th["along"][legs]))
        pz = Posed(self.skel, self.skin, r.P())
        ring = [q for q in pz.group(f"thigh_{side}") if abs(dot(sub(q, p), d)) < 0.02]
        top = max(ring, key=lambda q: q[2]) if ring else p
        goal = add(top, (0.0, 0.0, th.get("lift", 0.3) * self.hand_len))
        F = self._chest(r)
        dl = body(side, M.q_rotate(M.q_conj(F), d))  # the thigh's direction in (out, fwd, up) of the chest
        fd = norm(add(dl, tuple(th.get("fingers_add", (0.0, 0.0, 0.0)))))
        a = {**arm, "fingers_dir": fd, "touch": [f"thigh_{side}"], "touch_by": "hand_{side}", "clear": []}
        a.update({k: v for k, v in th.items() if k in ("palm", "elbow", "grip", "push", "gap_cm", "hand_roll")})
        self._arm_goal(r, side, a, goal=goal)

    def variants(self, legs: dict, arms: dict) -> dict:
        """Per-legs variants of the arms poses with a `clear` arm (the hip hand), "<Arms>__<Legs>": solved over those
        legs (not the reference's) where the shared clip's hand goes into a clear group beyond the hand limit; the
        layers play the variant with those legs (pose_layers.gd). Nothing else gets a per-pair clip."""
        lim = self.data["limits"].get("through_hand_cm", self.data["limits"]["through_cm"]) / 100.0
        out = {}
        for am, spec in self.data["arms"].items():
            arms_ = [spec.get(s) or spec.get("both") for s in SIDES]
            groups = {(g.format(side=s), s) for a, s in zip(arms_, SIDES) if a for g in a.get("clear", ())}
            if not groups or am not in arms:
                continue
            for lg in legs:
                if lg == self.data["reference_legs"]:
                    continue
                if spec.get("per_legs") or any(thigh_side(self.data, lg, s) for _, s in groups):
                    # round 3: the hand on the thigh, always; p3: `per_legs`, a variant on every legs pose (the fist
                    # akimbo: the shared clip's fist goes into the waist or off it where the legs lean the Spine)
                    out[f"{am}{VARIANT}{lg}"] = self.arms(am, ref=self.legs(lg), legs=lg)
                    continue
                P = compose(legs[lg], arms[am]).P()
                pz = Posed(self.skel, self.skin, P)
                d = max(tube_depth(self.tubes[t], P, pz.group(f"hand_{s}"), THIGH_SKIP if "UpperLeg" in t else 0)
                        for g, s in groups for t in tube_bones(g, self.tubes))
                if d > lim:
                    out[f"{am}{VARIANT}{lg}"] = self.arms(am, ref=self.legs(lg), legs=lg)
        return out

    def _meet(self, r: Rig, spec: dict, c: dict) -> None:
        """Two hands moved together along the body's left-right axis until c's two bones' skin meet (gap_cm)."""
        for _ in range(8):
            pz = Posed(self.skel, self.skin, r.P())
            a = pz.group(c["a"])
            b = pz.group(c["b"])
            # the signed gap across the body's left-right axis (a is the left hand's: crossed hands read negative)
            X = M.q_rotate(self._chest(r), (1.0, 0.0, 0.0))
            gap = min(dot(p, X) for p in a) - max(dot(p, X) for p in b)
            move = (gap - c.get("gap_cm", 0.2) / 100.0) / 2.0
            if abs(move) < 0.0015:
                break
            move = max(-0.03, min(0.03, move))  # small steps: no elbow flipping over the midline
            for side in SIDES:
                arm = spec.get(side) or spec.get("both")
                g = r._goal[side]
                self._arm_goal(r, side, {**arm, "touch": None}, goal=add(g, body(side, (-move, 0.0, 0.0))))


# ---------------------------------------------------------------------------------------------- pairs and clips
VARIANT = "__"  # an arms pose's per-legs variant: "<Arms>__<Legs>" (Model.variants)


def thigh_side(data: dict, legs: str, side: str) -> bool:
    """Whether the hip hand of `side` rests on its thigh on these legs (`[thigh_hand]`: its `legs`, and `sides`
    per legs pose where only one thigh is raised: s11, OneLeg's right knee up, Kneel's left)."""
    th = data.get("thigh_hand", {})
    return legs in th.get("legs", ()) and side in th.get("sides", {}).get(legs, SIDES)


def arms_for(arms: dict, am: str, lg: str) -> "Rig":
    """The arms rig a pair plays: the per-legs variant when there is one, else the arms pose's own."""
    return arms.get(f"{am}{VARIANT}{lg}", arms[am])


def compose(legs: Rig, arms: Rig) -> Rig:
    """A pair: the legs' channels on the legs' bones, the arms' on the arms' (SPLIT), nothing else."""
    r = Rig(legs.skel)
    for b in r.skel["order"]:
        src = legs if owner(b) == "legs" else arms
        r.loc[b], r.rot[b] = src.loc[b], src.rot[b]
    return r


def layer_clip(r: Rig, layer: str, name: str, frames: int = 2) -> dict:
    """A held clip of one layer: its bones keyed with identical keys on every frame (a loop the game holds)."""
    bones = [b for b in r.skel["order"] if owner(b) == layer]
    return {"name": name, "fps": 24, "loc": {b: [r.loc[b]] * frames for b in bones},
            "rot": {b: [r.rot[b]] * frames for b in bones}}


def load(path: Path = DATA) -> dict:
    return tomllib.loads(Path(path).read_text(encoding="utf-8"))


def merged(base: dict, over: dict) -> dict:
    """`base` with `over`'s tables merged in, key by key (a value that is not a table replaces)."""
    out = dict(base)
    for k, v in over.items():
        out[k] = merged(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def for_char(data: dict, char: str | None) -> dict:
    """The pose data for one character: its `[chars.<char>]` table merged over the shared one (round 3: the
    axolotl's wider head gets its own hands-behind-the-head settings)."""
    return merged(data, data.get("chars", {}).get(char or "", {}))


# ------------------------------------------------------------------------------------------------ measures
def hull(pts: list) -> list:
    """The convex hull of 2D points (monotone chain, counter-clockwise)."""
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts

    def half(seq):
        h = []
        for p in seq:
            while len(h) >= 2 and ((h[-1][0] - h[-2][0]) * (p[1] - h[-2][1]) -
                                   (h[-1][1] - h[-2][1]) * (p[0] - h[-2][0])) <= 0:
                h.pop()
            h.append(p)
        return h
    lo, hi = half(pts), half(reversed(pts))
    return lo[:-1] + hi[:-1]


def inside_margin(poly: list, p) -> float:
    """The signed distance from p to the convex polygon's edge (+ inside)."""
    if len(poly) < 3:
        return -min((math.dist(p, q) for q in poly), default=1e9)
    best = 1e9
    for i, a in enumerate(poly):
        b = poly[(i + 1) % len(poly)]
        e = (b[0] - a[0], b[1] - a[1])
        n = math.hypot(*e) or 1e-12
        best = min(best, ((e[0]) * (p[1] - a[1]) - (e[1]) * (p[0] - a[0])) / n)
    return best


def centre_of_mass(model: Model, P: dict):
    """The tubes' volumes at their posed centroids."""
    tot, acc = 0.0, [0.0, 0.0, 0.0]
    for b, t in model.tubes.items():
        c = t["centroid_local"]
        m = P[b]
        w = tuple(m[i][0] * c[0] + m[i][1] * c[1] + m[i][2] * c[2] + m[i][3] for i in range(3))
        tot += t["volume"]
        for k in range(3):
            acc[k] += t["volume"] * w[k]
    return tuple(a / tot for a in acc)


def palm_centre(P: dict, side: str) -> tuple:
    """The palm's centre: halfway from the wrist to the middle finger's knuckle."""
    return mul(add(S.pos(P[f"{side}Hand"]), S.pos(P[f"{side}MiddleProximal"])), 0.5)


def knuckles(P: dict, side: str) -> tuple:
    """A fist's knuckles: the four fingers' base knuckles' centre (p3: the akimbo fist's knuckles press into the
    waist, so its palm's centre stands a fist's depth off it)."""
    return mul(tuple(map(sum, zip(*(S.pos(P[f"{side}{f}Proximal"]) for f in FINGERS[1:])))), 0.25)


def mark_posed(model: Model, P: dict, mark: str) -> tuple:
    """A rest landmark (Model.marks) carried by the Spine's pose (the waist's side rides on the Spine)."""
    m = M.mat_mul(P["Spine"], S.rigid_inv(model.skel["rest"]["Spine"]))
    x, y, z = model.marks[mark]
    return tuple(m[i][0] * x + m[i][1] * y + m[i][2] * z + m[i][3] for i in range(3))


# a's skin shares a joint with b (the groin, the armpit, the knee's back): only how much deeper it goes than at rest
REST_BASED = ("thigh", "upperarm", "shin")
# per part the joint its kept skin is measured from, the next joint, and the share skipped (through_keep)
KEEP_FROM = {"thigh": ("UpperLeg", "LowerLeg", 0.3), "upperarm": ("UpperArm", "LowerArm", 0.5),
             "shin": ("LowerLeg", "Foot", 0.3)}
# a thigh into the torso reads the belly's tubes, not the pelvis's: the Hips tube is the thigh's own joint (its flare
# read 5.4 cm on OneLeg's straight standing leg, s5), the belly in Squat, Sit and Kneel is the Spine's and up
THIGH_TORSO_SKIP = ("Hips",)


def through_keep(P: dict, a: str, pts: list) -> list:
    """Which of a's posed points the through check reads: a thigh beyond its groin (the hip's 30 %: the belly's
    contact in Squat and Sit is the thigh's front from there on), an upper arm's elbow half (the armpit's skin is
    shared), a shin beyond its knee's 30 % (the knee's back folds into the thigh's end in every bent knee: s5's
    calibration read 3.2-5.8 cm there and 0 beyond on all six legs poses); every point of the other groups."""
    part = a.split("_")[0]
    if part not in KEEP_FROM:
        return [True] * len(pts)
    side = a.split("_")[1]
    j0, j1, k = KEEP_FROM[part]
    o, e = S.pos(P[side + j0]), S.pos(P[side + j1])
    ax = sub(e, o)
    cut = k * dot(ax, ax)
    return [dot(sub(p, o), ax) > cut for p in pts]


def through_depth(model: Model, P: dict, pz: Posed, a: str, b: str) -> float:
    """How deep a's skin goes into b's volume (m): the deepest point inside b's tubes; for a REST_BASED group the
    depth beyond the same point's at rest (0 on the rest pose by construction, so the groin, armpit and knee skin
    the tubes share at rest does not read). Into a thigh: its hip third skipped (THIGH_SKIP: the buttock and groin
    skin that skinning folds into the pelvis when the thigh rises; the torso's check covers a hand there)."""
    pts = pz.groups([a])
    keep = through_keep(P, a, pts)
    sel = [p for p, k in zip(pts, keep) if k]
    first = THIGH_SKIP if b.startswith("thigh") else 0
    based = a.split("_")[0] in REST_BASED
    if based:
        rp = model.rest_posed
        rest = [p for p, k in zip(rp.groups([a]), keep) if k]
    worst = 0.0
    for t in tube_bones(b, model.tubes):
        if a.startswith("thigh") and b == "torso" and t in THIGH_TORSO_SKIP:
            continue
        dep = tube_depths(model.tubes[t], P, sel, first)
        if based:
            base = tube_depths(model.tubes[t], rp.P, rest, first)
            dep = [x - y for x, y in zip(dep, base)]
        worst = max(worst, max(dep, default=0.0))
    return worst


def flat_feet(data: dict, pz: Posed, legs: str) -> dict:
    """A planted foot without `foot_pitch`: its heel's (the Foot bone's skin) and ball's (Toes) lowest points, the
    higher of the two (cm): a foot on one corner reads its other end's height."""
    out = {}
    spec = data["legs"][legs]
    for side in SIDES:
        leg = spec.get(side) or spec.get("both")
        if leg and leg.get("mode") == "plant" and not leg.get("foot_pitch"):
            out[side] = round(max(abs(pz.lowest([f"{side}Foot"])), abs(pz.lowest([f"{side}Toes"]))) * 100.0, 2)
    return out


TOUCH_CM = 0.5  # a hand's or forearm's through reading counts only where its skin is within this of the other's


def measure(model: Model, r: Rig, legs: str, arms: str, variant: bool = False) -> dict:
    """A pair's numbers: the floor (cm), the centre of mass over the support (cm inside the hull of the skin within
    1 cm of the floor), the deepest skin-through-skin per checked pair of groups (cm), the contacts' gaps (cm), the
    hands' distance to their landmarks (cm: a `mark` contact, the palm's centre to the posed landmark)."""
    d = model.data
    P = r.P()
    pz = Posed(model.skel, model.skin, P)
    allp = pz.groups(list(model.skin["by_group"]))
    low = min(p[2] for p in allp)
    sup = [(p[0], p[1]) for p in allp if p[2] < low + d["limits"]["support_cm"] / 100.0]
    poly = hull(sup)
    com = centre_of_mass(model, P)
    margin = inside_margin(poly, (com[0], com[1]))
    through, proxy = {}, {}
    for a, b in d["limits"]["through_pairs"]:
        v = round(through_depth(model, P, pz, a, b) * 100.0, 2)
        # round 3: a hand or forearm reads through only where its skin touches b's (gap under TOUCH_CM); a depth
        # with a skin gap is the tube's own bulge beyond the skin (the skull's back under the crest: 0.5-0.7 cm
        # "through" with a 1 cm gap), reported in `proxy_cm`
        if v > 0 and a.startswith(("hand", "forearm")) and nearest_gap(pz.group(a), pz.groups([b]), reach=0.05) * 100.0 > TOUCH_CM:
            proxy[f"{a}>{b}"], v = v, 0.0
        through[f"{a}>{b}"] = v
    contacts, marks, mark_lim = {}, {}, {}
    cs = d["arms"][arms].get("contacts", [])
    if variant and legs in d.get("thigh_hand", {}).get("legs", ()):  # the hip hand on the thigh: its contact is the
        hip = [f"hand_{s}" for s in SIDES  # thigh's skin (gap and through), not the waist's mark nor the torso
               if (d["arms"][arms].get(s) or d["arms"][arms].get("both") or {}).get("clear") and thigh_side(d, legs, s)]
        cs = [c for c in cs if not (c["a"] in hip and (c.get("mark") or c.get("b") == "torso"))]
        cs += [{"a": h, "b": f"thigh_{h.split('_')[1]}"} for h in hip]
    for c in cs + d["legs"][legs].get("contacts", []):
        if c.get("measure") is False:  # a solve's helper (the hands' meet): its own contacts are measured
            continue
        if c.get("mark"):  # the palm's centre to a landmark carried by the Spine (the hip hand on the waist's side)
            at = knuckles if c.get("by") == "knuckles" else palm_centre  # p3: a fist's knuckles
            if c.get("mark_cm"):  # the contact's own limit (p3: the akimbo fist rides above the waist's mark), per
                # legs pose where it has one (q4, review 1: `legs_mark_cm`, the fist lifted up the waist's side on
                # the legs whose thighs rise to it; the others keep the tight one)
                mark_lim[f"{c['a']}@{c['mark']}"] = c.get("legs_mark_cm", {}).get(legs, c["mark_cm"])
            marks[f"{c['a']}@{c['mark']}"] = round(length(sub(at(P, c["a"].split("_")[1]),
                                                              mark_posed(model, P, c["mark"]))) * 100, 2)
            continue
        contacts[f"{c['a']}~{c['b']}"] = round(nearest_gap(pz.group(c["a"]), pz.groups([c["b"]]), reach=0.3) * 100, 2)
    floor = {g: round(pz.lowest([g]) * 100.0, 2) for g in d["legs"][legs].get("floor", [])}
    flat = flat_feet(d, pz, legs)
    lim = d["limits"]
    fails = []
    for k, v in flat.items():
        if v > lim["flat_cm"]:
            fails.append(f"flat {k} foot {v} cm")
    for k, v in floor.items():
        if abs(v) > lim["floor_cm"]:
            fails.append(f"touch {k} {v} cm")
    if abs(low * 100) > lim["floor_cm"]:
        fails.append(f"floor {low * 100:.2f} cm")
    if legs in lim["balance_legs"] and margin * 100 < lim["com_margin_cm"]:
        fails.append(f"com {margin * 100:.1f} cm")
    for k, v in through.items():
        if v > (lim.get("through_hand_cm", lim["through_cm"]) if k.startswith(("hand", "forearm")) else lim["through_cm"]):
            fails.append(f"through {k} {v} cm")
    for k, v in proxy.items():  # review 3: a depth with a skin gap still fails past its own limit (a hand deep in b
        if v > lim.get("proxy_hand_cm", lim["through_cm"]):  # with no vertex of b's skin within TOUCH_CM)
            fails.append(f"through (no touch) {k} {v} cm")
    for k, v in marks.items():  # a per-legs variant rides off the waist to clear the thigh: its own, looser limit;
        # a contact's own limit wins outright (q4: it was max()-ed with variant_mark_cm, 10 cm on Stand's variant)
        if v > (mark_lim[k] if k in mark_lim else lim.get("variant_mark_cm", lim["mark_cm"]) if variant else lim["mark_cm"]):
            fails.append(f"mark {k} {v} cm")
    for k, v in contacts.items():
        if v > lim["contact_gap_cm"]:
            fails.append(f"gap {k} {v} cm")
    return {"pair": f"{legs}+{arms}", "floor_cm": round(low * 100, 2), "com_margin_cm": round(margin * 100, 2),
            "support_pts": len(sup), "com": [round(c, 4) for c in com], "touch_cm": floor, "flat_cm": flat, "through_cm": through, "proxy_cm": proxy, "contacts_cm": contacts,
            "marks_cm": marks, "fails": fails}


# --------------------------------------------------------------------------------------------- silhouettes
# A mask is a flat outline seen from one facing: a list of rows, each an int bitset (the leftmost pixel the highest
# bit of a row `w` pixels wide). Every pair is shot by the same camera fixed on the character's ground spot (Root at
# the origin, the floor at 0), not re-aligned per pose: where a pose moves the feet and hips (Sit, Kneel, Lunge) a
# legs difference includes that shift.
FACINGS = ("front", "left", "right", "back")


def mask_diff(a: list, b: list) -> float:
    """The outline difference 1 - IoU of two masks of one size (0: the same outline, 1: no overlap)."""
    inter = sum((x & y).bit_count() for x, y in zip(a, b))
    union = sum((x | y).bit_count() for x, y in zip(a, b))
    return 1.0 - inter / union if union else 0.0


def hflip(rows: list, w: int) -> list:
    """A mask mirrored left to right."""
    return [int(format(r, f"0{w}b")[::-1], 2) for r in rows]


def silhouette_table(masks: dict, legs: list, arms: list, w: int, lopsided: tuple = ()) -> dict:
    """How well each part reads per facing. masks[(leg, arm, facing)] -> rows.

    legs: per facing and per two leg poses, the outline difference of the pairs that differ only in the legs: the
    least over the arm poses (the worst case, and its arm) and the mean. arms: the same per two arm poses over the leg
    poses. lr: per pair, the left facing against the mirrored right facing (a symmetric pose reads near 0: its left and
    right outlines are mirror images up to perspective). `lopsided` only labels the pairs whose facing should be
    told apart; nothing fails on it (a limit would not separate them: s11's unlisted Squat+Plane reads 0.18, the
    listed Stand+Salute 0.07; p3 replaced Salute by Victory)."""
    out = {"legs": {}, "arms": {}, "lr": {}}
    for face in FACINGS:
        for kind, parts, others in (("legs", legs, arms), ("arms", arms, legs)):
            rows = []
            for i, p in enumerate(parts):
                for q in parts[i + 1:]:
                    ds = []
                    for o in others:
                        a = masks[(p, o, face)] if kind == "legs" else masks[(o, p, face)]
                        b = masks[(q, o, face)] if kind == "legs" else masks[(o, q, face)]
                        ds.append((mask_diff(a, b), o))
                    lo = min(ds)
                    rows.append({"a": p, "b": q, "min": round(lo[0], 3), "at": lo[1],
                                 "mean": round(sum(d for d, _ in ds) / len(ds), 3)})
            out[kind][face] = sorted(rows, key=lambda r: r["min"])
    for lg in legs:
        for am in arms:
            d = mask_diff(masks[(lg, am, "left")], hflip(masks[(lg, am, "right")], w))
            out["lr"][f"{lg}+{am}"] = {"diff": round(d, 3), "lopsided": lg in lopsided or am in lopsided}
    return out
