"""Retargeting inside Blender: a small pack loader, action sampling with our own forward kinematics, and the
retarget of the Universal Animation Library (UAL) onto the Ultimate Modular (UM) armature, baked into actions.

Imported by retarget.py and the animation review scripts (anim_*.py); see docs/animations.md. It keeps its own small
loader (the shared Ultimate Modular loader is #17's tools/blender/um/): drop the stray Icosphere, keep only the file's
own actions (each import adds .001 copies of names already present), reset every pose bone, and leave the armature's
world scale of 100 and the importer's RootNode rotation alone (characters move through the RootNode's matrix_world).

All poses here are armature-space 4x4 matrices (Blender's pose_bone.matrix), computed by our forward kinematics from
fcurves rather than by the depsgraph, so a source can be sampled without evaluating the scene:
    pose[b] = pose[parent] @ (rest[parent]^-1 @ rest[b]) @ basis[b]
"""

from __future__ import annotations

import math
import re

import bpy
from bpy_extras import anim_utils
from mathutils import Matrix, Quaternion, Vector

FPS = 30  # the review timeline; UAL is authored at 30 fps (its clips import to whole frames only at 30)


def base_name(name: str) -> str:
    return re.sub(r"\.\d{3}$", "", name)


# ------------------------------------------------------------------------------------------------------- loading
def new_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.fps = FPS
    bpy.context.scene.render.fps_base = 1.0


def reset_pose(arm) -> None:
    if arm.animation_data:
        arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.scale = (1, 1, 1)


def load_glb(path: str) -> dict:
    """Imports a GLB at FPS frames per second. Returns {arm, root, meshes {base name: obj}, actions {name: action},
    objects}: only this file's own actions, the Icosphere removed, the pose reset."""
    scene = bpy.context.scene
    scene.render.fps = FPS
    before_obj, before_act = set(bpy.data.objects), set(bpy.data.actions)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before_obj]
    for o in [o for o in new if o.type == "MESH" and base_name(o.name) == "Icosphere"]:
        new.remove(o)
        bpy.data.objects.remove(o, do_unlink=True)
    arm = next(o for o in new if o.type == "ARMATURE")
    actions = {}
    for act in bpy.data.actions:
        if act not in before_act:
            parts = base_name(act.name).split("|")  # "CharacterArmature|Walk.001" -> "Walk"
            if len(parts) > 2 and parts[-1] == "baselayer":  # Meshy's "Armature|walking_man|baselayer"
                parts.pop()
            name = parts[-1]
            actions[name] = act
    reset_pose(arm)
    bpy.context.view_layer.update()
    meshes = {base_name(o.name): o for o in new if o.type == "MESH"}
    return {"arm": arm, "root": arm.parent, "meshes": meshes, "actions": actions, "objects": new, "path": path}


def add_toes(char: dict) -> dict:
    """Gives a loaded pack character the assembler's toe bones (um/toes.py, art #25), Toe.L and Toe.R at the ball of
    its shoes, before it is placed or posed; its pack actions play as before (they key no toe)."""
    from um import toes  # tools/blender/um, the assembler's package

    return toes.add_toe_bones(char["arm"], toes.shoes_of(char["meshes"]), list(char["meshes"].values()))


def place(char: dict, x: float = 0.0, y: float = 0.0, yaw: float = 0.0) -> None:
    """Moves a loaded character through its top object's matrix_world (the importer's RootNode carries a rotation)."""
    top = char["root"] or char["arm"]
    if "_m0" not in char:
        char["_m0"] = top.matrix_world.copy()
    top.matrix_world = Matrix.Translation((x, y, 0.0)) @ Matrix.Rotation(math.radians(yaw), 4, "Z") @ char["_m0"]
    bpy.context.view_layer.update()


# ------------------------------------------------------------------------------------------------------ the rig
def rot(m: Matrix) -> Quaternion:
    return m.to_3x3().normalized().to_quaternion()


class Rig:
    """An armature's rest data in armature space and in world space (at the time of construction)."""

    def __init__(self, arm):
        self.arm = arm
        self.W = arm.matrix_world.copy()
        self.Wi = self.W.inverted()
        self.Wrot = rot(self.W)
        self.scale = self.W.to_scale().x
        bones = arm.data.bones
        self.rest = {b.name: b.matrix_local.copy() for b in bones}
        self.parent = {b.name: (b.parent.name if b.parent else None) for b in bones}
        self.rest_rel = {
            n: (self.rest[p].inverted() @ self.rest[n]) if p else self.rest[n].copy() for n, p in self.parent.items()
        }
        depth = {}
        for b in bones:
            d, q = 0, b.parent
            while q:
                d, q = d + 1, q.parent
            depth[b.name] = d
        self.order = sorted(self.rest, key=lambda n: depth[n])

    def world(self, m: Matrix) -> Matrix:
        return self.W @ m

    def rest_world_pos(self, name: str) -> Vector:
        return self.W @ self.rest[name].translation


def fk(rig: Rig, basis: dict) -> dict:
    """Armature-space pose matrices from local basis matrices (missing bones: identity)."""
    pose = {}
    ident = Matrix.Identity(4)
    for n in rig.order:
        p = rig.parent[n]
        local = rig.rest_rel[n] @ basis.get(n, ident)
        pose[n] = pose[p] @ local if p else local
    return pose


def basis_from_pose(rig: Rig, pose: dict) -> dict:
    out = {}
    for n in rig.order:
        p = rig.parent[n]
        parent = pose[p] if p else Matrix.Identity(4)
        out[n] = rig.rest_rel[n].inverted() @ parent.inverted() @ pose[n]
    return out


# ------------------------------------------------------------------------------------------------------ actions
def fcurves_of(action):
    slot = action.slots[0]
    bag = anim_utils.action_get_channelbag_for_slot(action, slot)
    return list(bag.fcurves) if bag else []


class Sampler:
    """Evaluates an action's pose-bone channels at any (fractional) frame, without the depsgraph."""

    PATH = re.compile(r'pose\.bones\["(.+)"\]\.(location|rotation_quaternion|scale)')

    def __init__(self, action):
        self.action = action
        self.start, self.end = (float(x) for x in action.frame_range)
        self.channels: dict[str, dict[str, list]] = {}
        for fc in fcurves_of(action):
            m = self.PATH.fullmatch(fc.data_path)
            if not m:
                continue
            chans = self.channels.setdefault(m.group(1), {})
            size = 4 if m.group(2) == "rotation_quaternion" else 3
            chans.setdefault(m.group(2), [None] * size)[fc.array_index] = fc

    @property
    def frames(self) -> float:
        return self.end - self.start

    @property
    def seconds(self) -> float:
        return self.frames / FPS

    def basis(self, frame: float) -> dict:
        out = {}
        for bone, chans in self.channels.items():
            def val(key, i, default):
                fcs = chans.get(key)
                return fcs[i].evaluate(frame) if fcs and fcs[i] is not None else default

            loc = Vector([val("location", i, 0.0) for i in range(3)])
            q = Quaternion([val("rotation_quaternion", i, 1.0 if i == 0 else 0.0) for i in range(4)])
            q = q.normalized() if q.magnitude > 1e-9 else Quaternion()
            sc = Vector([val("scale", i, 1.0) for i in range(3)])
            out[bone] = Matrix.LocRotScale(loc, q, sc)
        return out


def apply_basis(arm, basis: dict) -> None:
    """Poses an armature (with no action) from basis matrices; bones not given go to identity."""
    if arm.animation_data:
        arm.animation_data.action = None
    ident = Matrix.Identity(4)
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.matrix_basis = basis.get(pb.name, ident)


def bake(arm, name: str, frames: list[dict], start: float = 0.0):
    """A new action with one key per frame (frame start + i) for every bone in frames[i] (basis matrices)."""
    act = bpy.data.actions.new(name)
    slot = act.slots.new(id_type="OBJECT", name=arm.name)
    bag = act.layers.new("Layer").strips.new(type="KEYFRAME").channelbags.new(slot)
    bones = list(frames[0])
    for bone in bones:
        locs, quats, scales, prev = [], [], [], None
        for m in (f[bone] for f in frames):
            loc, q, sc = m.decompose()
            if prev is not None and prev.dot(q) < 0:
                q = -q  # keep neighbouring quaternions on one hemisphere, so interpolation takes the short way
            prev = q
            locs.append(loc), quats.append(q), scales.append(sc)
        for key, values, size in (("location", locs, 3), ("rotation_quaternion", quats, 4), ("scale", scales, 3)):
            for i in range(size):
                fc = bag.fcurves.new(f'pose.bones["{bone}"].{key}', index=i, group_name=bone)
                fc.keyframe_points.add(len(values))
                co = []
                for k, v in enumerate(values):
                    co += [start + k, v[i]]
                fc.keyframe_points.foreach_set("co", co)
                fc.keyframe_points.foreach_set("interpolation", [2] * len(values))  # LINEAR
                fc.update()
    act.use_fake_user = True
    return act


# ---------------------------------------------------------------------------------------------------- retarget
class Retargeter:
    """Retargets source poses onto the target rig with a checked bone map (retarget_map.load)."""

    def __init__(self, src: Rig, tgt: Rig, bmap: dict):
        self.src, self.tgt, self.map = src, tgt, bmap
        self.inv = {t: s for s, t in bmap["bones"].items()}
        # a source without a root bone (Meshy's rig) leaves the target root at rest: its hips carry the root motion
        self.root_t = bmap["root"][1] if bmap.get("root") else None
        self.hips_s, self.hips_t = bmap["hips"][0], bmap["hips"][1]

        def hip_height(rig, names):
            return sum(rig.rest_world_pos(n).z for n in names) / len(names)

        self.src_hip = hip_height(src, bmap["height"]["source"])
        self.tgt_hip = hip_height(tgt, bmap["height"]["target"])
        self.ratio = self.tgt_hip / self.src_hip
        # positions scale about each rig's own origin, so the rigs may stand anywhere when the retargeter is built
        self.src_o, self.tgt_o = src.W.translation.copy(), tgt.W.translation.copy()
        self.src_rest_w = {s: src.world(src.rest[s]) for s in bmap["bones"]}
        self.src_rest_rot_inv = {s: rot(m).inverted() for s, m in self.src_rest_w.items()}
        self.tgt_rest_rot_w = {t: rot(tgt.world(tgt.rest[t])) for t in self.inv}
        # [align] (art #25): target bones whose rest direction is turned onto the source bone's before the transfer,
        # where the two rests differ by more than the motion can carry (Meshy's upper arms rest 10-15 degrees below
        # ours: without it, an arm hanging at the side on Meshy's rig stands that far out on ours)
        self.aligned = {}
        for t in bmap.get("align", []):
            child = next(c for c in tgt.order if tgt.parent[c] == t and c in self.inv)
            d_s = src.rest_world_pos(self.inv[child]) - src.rest_world_pos(self.inv[t])
            d_t = tgt.rest_world_pos(child) - tgt.rest_world_pos(t)
            turn = d_t.rotation_difference(d_s)
            self.tgt_rest_rot_w[t] = turn @ self.tgt_rest_rot_w[t]
            self.aligned[t] = round(math.degrees(turn.angle), 2)
        self.tgt_Wrot_inv = tgt.Wrot.inverted()
        self.follow_off = {t: tgt.rest[c].inverted() @ tgt.rest[t] for t, c in bmap["follow"].items()}
        fwd = tgt.Wi.to_3x3().normalized() @ Vector((0.0, -1.0, 0.0))  # the target's front, in its armature space
        self.knee_fwd = {
            leg["target"][0]: rot(tgt.rest[leg["target"][0]]).inverted() @ fwd for leg in bmap["legs"]
        }
        late = set(bmap["follow"])  # followers (and what hangs from them) come after the bones that carry them
        for n in tgt.order:
            if tgt.parent[n] in late:
                late.add(n)
        self.order = [n for n in tgt.order if n not in late] + [n for n in tgt.order if n in late]
        # the bones below each IK foot (the toe bones of art #25), re-attached after the IK moves the foot
        self.foot_kids = {}
        for leg in bmap["legs"]:
            kids = {leg["target"][2]}
            for n in tgt.order:
                if tgt.parent[n] in kids:
                    kids.add(n)
            self.foot_kids[leg["target"][2]] = [n for n in tgt.order if n in kids and n != leg["target"][2]]
        # each target foot's pivot, carried by the source foot: the pivot's rest position, scaled down to the source's
        # size and expressed in the source foot's rest frame, so heel and toe roll transfer with the foot
        self.foot_anchor = {}
        for leg in bmap["legs"]:
            foot, sf = leg["target"][2], leg["source_foot"]
            pivot = self.to_src(tgt.world(tgt.rest[foot]).translation)
            self.foot_anchor[foot] = self.src_rest_w[sf].inverted() @ pivot
        # the target hips bone (Body) is carried the same way by the source pelvis: the two rigs put their pelvis
        # pivots in different places (UAL's pelvis head is 5 cm behind its hip joints, the Ultimate Modular Body head
        # 10 cm below its own), so moving Body by the pelvis head's displacement swings the hip joints about the wrong
        # pivot once the pelvis turns (a fall or a roll pushed the body 13-17 cm into the floor)
        hips_rest = self.to_src(tgt.world(tgt.rest[self.hips_t]).translation)
        self.hip_anchor = self.src_rest_w[self.hips_s].inverted() @ hips_rest
        self.soles = {}
        self.ik = True
        self.miss_mm = 0.0  # the largest distance (mm) by which a leg fell short of its ankle goal since the reset

    def to_src(self, p: Vector) -> Vector:
        """A target world position at the source's size (scaled about the rigs' origins)."""
        return (p - self.tgt_o) / self.ratio + self.src_o

    def to_tgt(self, p: Vector) -> Vector:
        """A source world position at the target's size (scaled about the rigs' origins)."""
        return (p - self.src_o) * self.ratio + self.tgt_o

    def set_soles(self, meshes) -> None:
        """Reads the sole of each target foot, and of each mapped toe bone below it, from the meshes in the rest pose,
        so a foot or a toe can be kept out of the floor. A foot's sole is the vertices weighted most to it or to a bone
        below it kept at rest (the whole rigid shoe when its toe bone is not mapped); a mapped toe's sole is its own
        vertices. Each keeps its frontmost low vertex (the toe of a rigid shoe, the ball of a shoe with a mapped toe,
        the tip for a toe bone) in its bone's rest frame."""
        for leg in self.map["legs"]:
            foot = leg["target"][2]
            kids = self.foot_kids[foot]
            rigid = {foot} | {k for k in kids if k not in self.inv}
            self._sole(foot, rigid, meshes)
            for k in kids:
                if k in self.inv:
                    self._sole(k, {k}, meshes)

    def _sole(self, bone: str, groups: set, meshes) -> None:
        tgt = self.tgt
        pts = []
        for obj in meshes:
            names = {g.index: g.name for g in obj.vertex_groups}
            if not groups & set(names.values()):
                continue
            for v in obj.data.vertices:
                best = max(v.groups, key=lambda g: g.weight, default=None)
                if best is not None and names.get(best.group) in groups:
                    pts.append(obj.matrix_world @ v.co)
        if not pts:
            return
        low = min(p.z for p in pts)
        sole = [p for p in pts if p.z < low + 0.015]
        toe = min(sole, key=lambda p: p.y)  # the front is -Y
        local = tgt.rest[bone].inverted() @ (tgt.Wi @ toe)
        self.soles[bone] = {"toe_local": local, "floor_z": toe.z, "pivot_z": tgt.world(tgt.rest[bone]).translation.z}

    def solve(self, src_pose: dict) -> tuple[dict, dict]:
        """Target armature-space poses and basis matrices for one source pose (armature space of the source)."""
        S = {s: self.src.world(src_pose[s]) for s in self.map["bones"]}
        tgt, P = self.tgt, {}
        for t in self.order:
            p = tgt.parent[t]
            fk_m = (P[p] @ tgt.rest_rel[t]) if p else tgt.rest_rel[t].copy()
            s = self.inv.get(t)
            if s is None:
                P[t] = fk_m
                continue
            q_world = rot(S[s]) @ self.src_rest_rot_inv[s] @ self.tgt_rest_rot_w[t]
            q_arm = self.tgt_Wrot_inv @ q_world
            if t == self.hips_t:
                pos = tgt.Wi @ self.to_tgt(S[s] @ self.hip_anchor)
            elif t == self.root_t:
                delta = S[s].translation - self.src_rest_w[s].translation
                pos = tgt.Wi @ (tgt.world(tgt.rest[t]).translation + delta * self.ratio)
            elif t in self.follow_off:
                pos = (P[self.map["follow"][t]] @ self.follow_off[t]).translation
            else:
                pos = fk_m.translation
            P[t] = Matrix.Translation(pos) @ q_arm.to_matrix().to_4x4()
        if self.ik:
            for leg in self.map["legs"]:
                self._leg_ik(P, leg, S[leg["source_foot"]])
        return P, basis_from_pose(tgt, P)

    def _leg_ik(self, P: dict, leg: dict, src_foot_w: Matrix) -> None:
        upper, lower, foot = leg["target"]
        tgt = self.tgt
        sf = leg["source_foot"]
        goal = tgt.Wi @ self.to_tgt(src_foot_w @ self.foot_anchor[foot])
        H, K = P[upper].translation.copy(), P[lower].translation.copy()
        A = (P[lower] @ self.follow_off[foot]).translation
        L1, L2 = (K - H).length, (A - K).length
        dv = goal - H
        d = min(max(dv.length, abs(L1 - L2) + 1e-7), (L1 + L2) * (1 - 1e-6))
        u = dv.normalized()
        knee = K - H
        pole = (knee - u * knee.dot(u)) / max(L1, 1e-9)
        fwd = rot(P[upper]) @ self.knee_fwd[upper]
        pole += (fwd - u * fwd.dot(u)) * 0.05  # a steady bend direction when the leg is nearly straight
        n = pole.normalized()
        a = (L1 * L1 - L2 * L2 + d * d) / (2 * d)
        h = math.sqrt(max(L1 * L1 - a * a, 0.0))
        K2, A2 = H + u * a + n * h, H + u * d
        self.miss_mm = max(self.miss_mm, (A2 - goal).length * tgt.scale * 1000)
        q1 = knee.rotation_difference(K2 - H)
        P[upper] = Matrix.Translation(H) @ (q1 @ rot(P[upper])).to_matrix().to_4x4()
        shin = q1 @ (A - K)
        q2 = shin.rotation_difference(A2 - K2)
        P[lower] = Matrix.Translation(K2) @ (q2 @ q1 @ rot(P[lower])).to_matrix().to_4x4()
        P[foot] = Matrix.Translation((P[lower] @ self.follow_off[foot]).translation) @ rot(P[foot]).to_matrix().to_4x4()
        w = self._lift_weight(P, foot) if foot in self.soles else 0.0
        if w > 0.0:
            self._lift(P, foot, w)
        # the bones below the foot follow it again: a mapped toe keeps its world rotation (the source's ball), so it
        # stays level while the heel rises (the shoe bends); an unmapped one is carried at its rest
        for k in self.foot_kids[foot]:
            fk_k = P[tgt.parent[k]] @ tgt.rest_rel[k]
            P[k] = Matrix.Translation(fk_k.translation) @ rot(P[k]).to_matrix().to_4x4() if k in self.inv else fk_k
            if k in self.inv and k in self.soles and w > 0.0:
                self._lift(P, k, w)

    def _lift_weight(self, P: dict, foot: str, full: float = 0.20, fade: float = 0.10) -> float:
        """How much the floor clamp acts on a foot (and its toe): fully while the foot pivot is up to `full` m above
        its rest height, fading out over the next `fade` m; not at all when the pivot is below the floor (an in-place
        jump without its rise)."""
        sole = self.soles[foot]
        pivot = self.tgt.W @ P[foot].translation
        if pivot.z < sole["pivot_z"] - 0.02:
            return 0.0
        return min(max(1.0 - (pivot.z - sole["pivot_z"] - full) / fade, 0.0), 1.0)

    def _lift(self, P: dict, bone: str, w: float) -> None:
        """Pitches a foot or a toe bone about its head until its sole's front point is no lower than the rest sole,
        by the weight w: the source rolls over its toes, where a rigid target foot (or a toe tipped past the
        floor) would push its front into the floor instead."""
        tgt, sole = self.tgt, self.soles[bone]
        pivot = tgt.W @ P[bone].translation
        toe = tgt.W @ (P[bone] @ sole["toe_local"])
        if toe.z >= sole["floor_z"]:
            return
        r = toe - pivot
        length = r.length
        if length < 1e-6:
            return
        now = math.asin(max(-1.0, min(1.0, r.z / length)))
        want = math.asin(max(-1.0, min(1.0, (sole["floor_z"] - pivot.z) / length)))
        axis = r.cross(Vector((0.0, 0.0, 1.0)))
        if axis.length < 1e-9:
            return
        lift = Quaternion(axis.normalized(), (want - now) * w)
        q_arm = self.tgt_Wrot_inv @ lift @ tgt.Wrot @ rot(P[bone])
        P[bone] = Matrix.Translation(P[bone].translation) @ q_arm.to_matrix().to_4x4()

    def rest_error(self) -> dict:
        """Retargets the source rest pose: the largest bone-head offset (mm, world) and rotation (degrees) from the
        target rest. Both are zero when the method is right."""
        P, basis = self.solve(fk(self.src, {}))
        moved = set(self.aligned)  # an aligned bone and everything below it leave the target rest by design
        for n in self.tgt.order:
            if self.tgt.parent[n] in moved:
                moved.add(n)
        off = max((self.tgt.W @ P[n].translation - self.tgt.W @ self.tgt.rest[n].translation).length
                  for n in P if n not in moved)
        ang = max(min(a, 360 - a) for n, a in ((n, math.degrees(rot(b).angle)) for n, b in basis.items())
                  if n not in moved)
        out = {"max_offset_mm": round(off * 1000, 4), "max_rotation_deg": round(ang, 4)}
        if self.aligned:
            out["aligned_deg"] = dict(self.aligned)
        return out

    def clip(self, action, name: str, arm=None, sampler=None):
        """Bakes one source action (or a sampler of it, such as an in-place one) into a new action for the target
        armature; returns (action, frame count)."""
        sampler = sampler or Sampler(action)
        n = int(round(sampler.frames))
        self.miss_mm = 0.0
        frames = []
        for i in range(n + 1):
            _, basis = self.solve(fk(self.src, sampler.basis(sampler.start + i)))
            frames.append(basis)
        return bake(arm or self.tgt.arm, name, frames), n
