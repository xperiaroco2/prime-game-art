"""Per-frame measures of a clip played on an Ultimate Modular character (docs/animations.md, "Measures").

Measure(char) prepares the vertex and face sets once; frame() reads the posed character (after the pose is applied
and the view layer updated); clip() sums the frames up with anim_math.
"""

from __future__ import annotations

import math

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import anim_math as am
from retarget_core import rot

FINGERS = ("Index", "Middle", "Ring", "Pinky")
TORSO = {"Body", "Hips", "Abdomen", "Torso", "Chest", "Neck", "Head"}
INSIDE_REACH_M = 0.15  # a hand point counts only against torso surface this close (the nearest-normal sign test)


def _dominant(obj) -> list[str | None]:
    """The vertex group (bone) with the largest weight for each vertex of obj."""
    names = {g.index: g.name for g in obj.vertex_groups}
    out = []
    for v in obj.data.vertices:
        best = max(v.groups, key=lambda g: g.weight, default=None)
        out.append(names.get(best.group) if best is not None else None)
    return out


class Measure:
    def __init__(self, char: dict):
        self.char, self.arm = char, char["arm"]
        self.meshes = list(char["meshes"].values())
        bones = self.arm.data.bones
        self.rest = {b.name: b.matrix_local.copy() for b in bones}
        W = self.arm.matrix_world
        Wr = rot(W)
        hand = {f"{f}{k}.{s}" for f in FINGERS for k in (1, 2, 3, 4) for s in "LR"}
        hand |= {f"Thumb{k}.{s}" for k in (1, 2, 3) for s in "LR"} | {"Wrist.L", "Wrist.R"}
        self.hand_idx, self.torso_faces = {}, {}
        for obj in self.meshes:
            dom = _dominant(obj)
            idx = [i for i, g in enumerate(dom) if g in hand]
            if idx:
                self.hand_idx[obj.name] = np.array(idx)
            faces = [tuple(p.vertices) for p in obj.data.polygons if all(dom[i] in TORSO for i in p.vertices)]
            if faces:
                self.torso_faces[obj.name] = faces
        # hinge axes in each parent bone's rest frame: knees bend about the world X axis (the shin goes back), the
        # left elbow about -Z and the right about +Z (the forearm comes forward from the T-pose)
        def local_axis(bone, axis):
            return rot(W @ self.rest[bone]).inverted() @ Vector(axis)

        self.hinges = {
            "knee.L": ("UpperLeg.L", "LowerLeg.L", local_axis("UpperLeg.L", (1, 0, 0))),
            "knee.R": ("UpperLeg.R", "LowerLeg.R", local_axis("UpperLeg.R", (1, 0, 0))),
            "elbow.L": ("UpperArm.L", "LowerArm.L", local_axis("UpperArm.L", (0, 0, -1))),
            "elbow.R": ("UpperArm.R", "LowerArm.R", local_axis("UpperArm.R", (0, 0, 1))),
        }
        self.child_end = {  # the far end of each lower limb: the next joint's rest offset, carried by the bone
            "LowerLeg.L": self.rest["LowerLeg.L"].inverted() @ self.rest["Foot.L"],
            "LowerLeg.R": self.rest["LowerLeg.R"].inverted() @ self.rest["Foot.R"],
            "LowerArm.L": self.rest["LowerArm.L"].inverted() @ self.rest["Wrist.L"],
            "LowerArm.R": self.rest["LowerArm.R"].inverted() @ self.rest["Wrist.R"],
        }
        self.twist_rest = {
            s: rot(self.rest[f"LowerArm.{s}"]).inverted() @ rot(self.rest[f"Wrist.{s}"]) for s in "LR"
        }
        self._Wr = Wr

    def _world_points(self, obj) -> np.ndarray:
        dg = bpy.context.evaluated_depsgraph_get()
        ev = obj.evaluated_get(dg)
        me = ev.to_mesh()
        co = np.empty(len(me.vertices) * 3, dtype=np.float64)
        me.vertices.foreach_get("co", co)
        ev.to_mesh_clear()
        co = co.reshape(-1, 3)
        m = np.array(ev.matrix_world)
        return co @ m[:3, :3].T + m[:3, 3]

    def frame(self, with_mesh: bool = True) -> dict:
        arm, W = self.arm, self.arm.matrix_world
        P = {pb.name: pb.matrix.copy() for pb in arm.pose.bones}
        rec = {"feet": {s: tuple(W @ P[f"Foot.{s}"].translation) for s in "LR"},
               "hips": tuple(W @ P["Body"].translation), "root": tuple(W @ P["Root"].translation)}
        for name, (upper, lower, axis_local) in self.hinges.items():
            a = W @ P[upper].translation
            b = W @ P[lower].translation
            c = W @ (P[lower] @ self.child_end[lower]).translation
            axis = rot(W @ P[upper]) @ axis_local
            rec[name] = am.signed_angle(tuple(b - a), tuple(c - b), tuple(axis))
        for s in "LR":
            rel = self.twist_rest[s].inverted() @ (rot(P[f"LowerArm.{s}"]).inverted() @ rot(P[f"Wrist.{s}"]))
            rec[f"twist.{s}"] = am.twist_angle(tuple(rel), (0.0, 1.0, 0.0))
            joints = [math.degrees(rot(arm.pose.bones[f"{f}{k}.{s}"].matrix_basis).angle) for f in FINGERS
                      for k in (2, 3, 4)]
            joints = [min(j, 360 - j) for j in joints]
            rec[f"curl.{s}"] = sum(joints) / len(joints)
            rec[f"curl_max.{s}"] = max(joints)
        rec["local"] = {pb.name: tuple(rot(pb.matrix_basis)) for pb in arm.pose.bones}
        if with_mesh:
            pts = {o.name: self._world_points(o) for o in self.meshes}
            rec["lowest_z"] = float(min(p[:, 2].min() for p in pts.values()))
            rec["hand_depth"] = self._hand_depth(pts)
        return rec

    def _hand_depth(self, pts: dict) -> float:
        """The deepest hand vertex inside the torso and head surface (m; 0 when none is inside)."""
        verts, polys = [], []
        for name, faces in self.torso_faces.items():
            off = len(verts)
            verts += [Vector(p) for p in pts[name]]
            polys += [tuple(i + off for i in f) for f in faces]
        if not polys:
            return 0.0
        bvh = BVHTree.FromPolygons(verts, polys)
        deepest = 0.0
        for name, idx in self.hand_idx.items():
            for p in pts[name][idx]:
                v = Vector(p)
                loc, normal, _, dist = bvh.find_nearest(v, INSIDE_REACH_M)
                if loc is not None and (v - loc).dot(normal) < 0:
                    deepest = max(deepest, dist)
        return deepest

    @staticmethod
    def clip(frames: list[dict], fps: float, loop: bool) -> dict:
        n = len(frames)
        seconds = (n - 1) / fps
        steps = [max(am.quat_angle(frames[i]["local"][b], frames[i + 1]["local"][b]) for b in frames[i]["local"])
                 for i in range(n - 1)]
        out = {"frames": n - 1, "seconds": round(seconds, 3), "loop": loop}
        out["foot_sliding"] = am.foot_sliding({s: [f["feet"][s] for f in frames] for s in "LR"}, fps)
        lows = [f["lowest_z"] for f in frames if "lowest_z" in f]
        if lows:
            out["lowest_vertex_cm"] = {"min": round(100 * min(lows), 1), "max": round(100 * max(lows), 1),
                                       "frames_below_1cm": sum(z < -0.01 for z in lows)}
        depths = [f["hand_depth"] for f in frames if "hand_depth" in f]
        if depths:
            out["hands_in_torso"] = {"max_depth_cm": round(100 * max(depths), 1),
                                     "frames_over_1cm": sum(d > 0.01 for d in depths)}
        out["loop_seam"] = am.loop_seam(frames[0]["local"], frames[-1]["local"], steps)
        out["hyperextension_deg"] = {k: am.hyperextension([f[k] for f in frames])
                                     for k in ("knee.L", "knee.R", "elbow.L", "elbow.R")}
        out["flexion_deg"] = {k: am.summary([f[k] for f in frames]) for k in ("knee.L", "knee.R", "elbow.L", "elbow.R")}
        out["forearm_twist_deg"] = {s: round(max(abs(f[f"twist.{s}"]) for f in frames), 1) for s in "LR"}
        out["finger_curl_deg"] = {s: am.summary([f[f"curl.{s}"] for f in frames]) for s in "LR"}
        out["finger_joint_max_deg"] = {s: round(max(f[f"curl_max.{s}"] for f in frames), 1) for s in "LR"}
        h0, h1 = frames[0]["hips"], frames[-1]["hips"]
        r0, r1 = frames[0]["root"], frames[-1]["root"]
        travel = math.hypot(h1[0] - h0[0], h1[1] - h0[1])
        out["root_motion"] = {
            "hips_travel_cm": round(100 * travel, 1),
            "root_travel_cm": round(100 * math.hypot(r1[0] - r0[0], r1[1] - r0[1]), 1),
            "in_place": travel < 0.05,
            "ground_speed_m_s": (round(out["foot_sliding"]["ground_speed_cm_s"] / 100, 2)
                                 if out["foot_sliding"]["ground_speed_cm_s"] is not None else None),
        }
        return out
