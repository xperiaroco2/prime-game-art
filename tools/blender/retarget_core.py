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
            name = base_name(act.name).split("|")[-1]  # "CharacterArmature|Walk.001" -> "Walk"
            actions[name] = act
    reset_pose(arm)
    bpy.context.view_layer.update()
    meshes = {base_name(o.name): o for o in new if o.type == "MESH"}
    return {"arm": arm, "root": arm.parent, "meshes": meshes, "actions": actions, "objects": new, "path": path}


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
        self.root_t, self.hips_t = bmap["root"][1], bmap["hips"][1]

        def hip_height(rig, names):
            return sum(rig.rest_world_pos(n).z for n in names) / len(names)

        self.src_hip = hip_height(src, bmap["height"]["source"])
        self.tgt_hip = hip_height(tgt, bmap["height"]["target"])
        self.ratio = self.tgt_hip / self.src_hip
        self.src_rest_w = {s: src.world(src.rest[s]) for s in bmap["bones"]}
        self.src_rest_rot_inv = {s: rot(m).inverted() for s, m in self.src_rest_w.items()}
        self.tgt_rest_rot_w = {t: rot(tgt.world(tgt.rest[t])) for t in self.inv}
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
        # each target foot's pivot, carried by the source foot: the pivot's rest position, scaled down to the source's
        # size and expressed in the source foot's rest frame, so heel and toe roll transfer with the foot
        self.foot_anchor = {}
        for leg in bmap["legs"]:
            foot, sf = leg["target"][2], leg["source_foot"]
            pivot = tgt.world(tgt.rest[foot]).translation / self.ratio
            self.foot_anchor[foot] = self.src_rest_w[sf].inverted() @ pivot
        self.soles = {}
        self.ik = True
        self.miss_mm = 0.0  # the largest distance (mm) by which a leg fell short of its ankle goal since the reset

    def set_soles(self, meshes) -> None:
        """Reads each target foot's heel and toe from the meshes in the rest pose (the lowest vertices weighted to the
        foot), so the toe of the rigid target foot can be kept out of the floor (the target has no toe bone)."""
        tgt = self.tgt
        for leg in self.map["legs"]:
            foot = leg["target"][2]
            pts = []
            for obj in meshes:
                group = obj.vertex_groups.get(foot)
                if group is None:
                    continue
                for v in obj.data.vertices:
                    best = max(v.groups, key=lambda g: g.weight, default=None)
                    if best is not None and best.group == group.index:
                        pts.append(obj.matrix_world @ v.co)
            if not pts:
                continue
            low = min(p.z for p in pts)
            sole = [p for p in pts if p.z < low + 0.015]
            toe = min(sole, key=lambda p: p.y)  # the front is -Y
            local = tgt.rest[foot].inverted() @ (tgt.Wi @ toe)
            self.soles[foot] = {"toe_local": local, "floor_z": toe.z, "pivot_z": tgt.world(tgt.rest[foot]).translation.z}

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
            if t in (self.root_t, self.hips_t):
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
        goal = tgt.Wi @ ((src_foot_w @ self.foot_anchor[foot]) * self.ratio)
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
        if foot in self.soles:
            self._lift_toe(P, foot)

    def _lift_toe(self, P: dict, foot: str, full: float = 0.20, fade: float = 0.10) -> None:
        """Pitches the foot about its pivot until its toe is no lower than the rest sole, while the pivot is on or
        above the floor and near it (fully up to `full` m above its rest height, fading out over the next `fade` m):
        the source rolls over its toes, the rigid target foot would push its toe into the floor instead. A pivot below
        the floor (an in-place jump without its rise) is left alone."""
        tgt, sole = self.tgt, self.soles[foot]
        pivot = tgt.W @ P[foot].translation
        toe = tgt.W @ (P[foot] @ sole["toe_local"])
        if toe.z >= sole["floor_z"] or pivot.z < sole["pivot_z"] - 0.02:
            return
        w = min(max(1.0 - (pivot.z - sole["pivot_z"] - full) / fade, 0.0), 1.0)
        r = toe - pivot
        length = r.length
        if w <= 0.0 or length < 1e-6:
            return
        now = math.asin(max(-1.0, min(1.0, r.z / length)))
        want = math.asin(max(-1.0, min(1.0, (sole["floor_z"] - pivot.z) / length)))
        axis = r.cross(Vector((0.0, 0.0, 1.0)))
        if axis.length < 1e-9:
            return
        lift = Quaternion(axis.normalized(), (want - now) * w)
        q_arm = self.tgt_Wrot_inv @ lift @ tgt.Wrot @ rot(P[foot])
        P[foot] = Matrix.Translation(P[foot].translation) @ q_arm.to_matrix().to_4x4()

    def rest_error(self) -> dict:
        """Retargets the source rest pose: the largest bone-head offset (mm, world) and rotation (degrees) from the
        target rest. Both are zero when the method is right."""
        P, basis = self.solve(fk(self.src, {}))
        off = max((self.tgt.W @ P[n].translation - self.tgt.W @ self.tgt.rest[n].translation).length for n in P)
        ang = max(min(a, 360 - a) for a in (math.degrees(rot(b).angle) for b in basis.values()))
        return {"max_offset_mm": round(off * 1000, 4), "max_rotation_deg": round(ang, 4)}

    def clip(self, action, name: str, arm=None):
        """Bakes one source action into a new action for the target armature; returns (action, frame count)."""
        sampler = Sampler(action)
        n = int(round(sampler.frames))
        self.miss_mm = 0.0
        frames = []
        for i in range(n + 1):
            _, basis = self.solve(fk(self.src, sampler.basis(sampler.start + i)))
            frames.append(basis)
        return bake(arm or self.tgt.arm, name, frames), n
