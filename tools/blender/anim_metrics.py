"""Per-frame measures of a clip played on an Ultimate Modular character (docs/animations.md, "Measures").

Measure(char) prepares the vertex and face sets once; frame() reads the posed character (after the pose is applied
and the view layer updated); clip() sums the frames up with anim_math.
"""

from __future__ import annotations

import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import anim_math as am
from retarget_core import rot

FINGERS = ("Index", "Middle", "Ring", "Pinky")
TORSO = {"Body", "Hips", "Abdomen", "Torso", "Chest"}
HEAD = {"Head"}
LEGS = {"UpperLeg.L", "UpperLeg.R", "LowerLeg.L", "LowerLeg.R"}
SURFACE_REACH = 0.05  # metres: how far from a surface a vertex is looked for inside it


def _dominant(obj) -> list[str | None]:
    """The vertex group (bone) with the largest weight for each vertex of obj."""
    names = {g.index: g.name for g in obj.vertex_groups}
    out = []
    for v in obj.data.vertices:
        best = max(v.groups, key=lambda g: g.weight, default=None)
        out.append(names.get(best.group) if best is not None else None)
    return out


def world_points(obj) -> np.ndarray:
    """The evaluated (posed) vertices of a mesh object in world space, as an (n, 3) array."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    ev.to_mesh_clear()
    co = co.reshape(-1, 3)
    m = np.array(ev.matrix_world)
    return co @ m[:3, :3].T + m[:3, 3]


def _hull_depth(body: np.ndarray, points: np.ndarray) -> float:
    """How deep (m) the deepest of points lies inside the convex hull of body (0 when none is inside)."""
    if len(body) < 4 or not len(points):
        return 0.0
    bm = bmesh.new()
    for p in body:
        bm.verts.new(p)
    res = bmesh.ops.convex_hull(bm, input=bm.verts, use_existing_faces=False)
    centre = body.mean(axis=0)
    normals, offsets = [], []
    for f in (g for g in res["geom"] if isinstance(g, bmesh.types.BMFace)):
        f.normal_update()
        n, c = np.array(f.normal), np.array(f.calc_center_median())
        if np.dot(c - centre, n) < 0:
            n = -n
        normals.append(n)
        offsets.append(np.dot(n, c))
    bm.free()
    if not normals:
        return 0.0
    signed = points @ np.array(normals).T - np.array(offsets)  # > 0 outside a face's plane
    worst = signed.max(axis=1)
    inside = worst < 0
    return float(-worst[inside].min()) if inside.any() else 0.0


def _surface_depth(pts: dict, polys: dict, faces: dict, query: dict) -> float:
    """How deep (m) the deepest vertex of `query` ({object name: vertex indices}) lies behind the faces `faces`
    ({object name: set of polygon indices}) of the posed objects (`polys`: {object name: [vertex index tuples]}): the
    vertex's nearest face on the whole mesh, less the faces of the query's own vertices, is one of those faces and
    its normal points away from the vertex. Unlike a convex hull this follows concave shapes such as a hand with
    spread fingers or a pair of legs; testing against the whole mesh keeps the open edges where a part is cut out of
    it from counting."""
    verts, tris, wanted, base = [], [], set(), 0
    for name, chosen in faces.items():
        own = set(query.get(name, ()))
        verts.extend(Vector(p) for p in pts[name])
        for i, f in enumerate(polys[name]):
            if own and any(v in own for v in f):
                continue
            if i in chosen:
                wanted.add(len(tris))
            tris.append(tuple(base + v for v in f))
        base += len(pts[name])
    points = [pts[name][idx] for name, idx in query.items()]
    points = np.concatenate(points) if points else np.zeros((0, 3))
    if not wanted or not len(points):
        return 0.0
    tree = BVHTree.FromPolygons(verts, tris)
    worst = 0.0
    for p in points:
        q = Vector(p)
        loc, normal, index, dist = tree.find_nearest(q, SURFACE_REACH)
        # behind the face, and squarely: a point beside a convex edge also finds a face that turns away from it
        if loc is not None and index in wanted and dist > 1e-6 and (q - loc).dot(normal) < -0.7 * dist:
            worst = max(worst, dist)
    return worst


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
        side = {s: {b for b in hand if b.endswith("." + s)} for s in "LR"}
        # vertex sets by the bone that weighs most: the hands, the torso and the head (tested as convex hulls), and
        # each shoe's sole; and surfaces (faces whose vertices all belong to one set): each hand and the legs, which
        # the hands are tested against as they are (a hand through the other hand or into a thigh)
        self.sets = {"hand": {}, "torso": {}, "head": {}, "Foot.L": {}, "Foot.R": {}, "hand.L": {}, "hand.R": {}}
        self.surfaces = {"hand.L": {}, "hand.R": {}, "legs": {}}
        self.polys = {}
        for obj in self.meshes:
            dom = _dominant(obj)
            for key, bones in (("hand", hand), ("torso", TORSO), ("head", HEAD), ("Foot.L", {"Foot.L"}),
                               ("Foot.R", {"Foot.R"}), ("hand.L", side["L"]), ("hand.R", side["R"])):
                idx = [i for i, g in enumerate(dom) if g in bones]
                if idx:
                    self.sets[key][obj.name] = np.array(idx)
            self.polys[obj.name] = [tuple(f.vertices) for f in obj.data.polygons]
            for key, bones in (("hand.L", side["L"]), ("hand.R", side["R"]), ("legs", LEGS)):
                chosen = {i for i, f in enumerate(self.polys[obj.name]) if all(dom[v] in bones for v in f)}
                if chosen:
                    self.surfaces[key][obj.name] = chosen
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
        rest = {o.name: world_points(o) for o in self.meshes}  # the floor: the soles' lowest rest height
        self.floor = float(min(self._gather(rest, f"Foot.{s}")[:, 2].min() for s in "LR"))

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
            pts = {o.name: world_points(o) for o in self.meshes}
            rec["lowest_z"] = float(min(p[:, 2].min() for p in pts.values()))
            hands = self._gather(pts, "hand")
            rec["hand_depth"] = _hull_depth(self._gather(pts, "torso"), hands)
            rec["hand_head_depth"] = _hull_depth(self._gather(pts, "head"), hands)
            rec["hand_hand_depth"] = max(
                _surface_depth(pts, self.polys, self.surfaces["hand.R"], self.sets["hand.L"]),
                _surface_depth(pts, self.polys, self.surfaces["hand.L"], self.sets["hand.R"]))
            rec["hand_leg_depth"] = _surface_depth(pts, self.polys, self.surfaces["legs"], self.sets["hand"])
            rec["soles"] = {s: self._gather(pts, f"Foot.{s}") for s in "LR"}
        return rec

    def _gather(self, pts: dict, key: str) -> np.ndarray:
        parts = [pts[name][idx] for name, idx in self.sets[key].items()]
        return np.concatenate(parts) if parts else np.zeros((0, 3))

    def clip(self, frames: list[dict], fps: float, loop: bool) -> dict:
        n = len(frames)
        seconds = (n - 1) / fps
        steps = [max(am.quat_angle(frames[i]["local"][b], frames[i + 1]["local"][b]) for b in frames[i]["local"])
                 for i in range(n - 1)]
        out = {"frames": n - 1, "seconds": round(seconds, 3), "loop": loop}
        out["foot_sliding"] = am.foot_sliding({s: [f["feet"][s] for f in frames] for s in "LR"}, fps)
        if "soles" in frames[0]:
            out["sole_sliding"] = am.sole_sliding({s: _sole_series([f["soles"][s] for f in frames], fps, loop)
                                                   for s in "LR"}, self.floor)
        lows = [f["lowest_z"] for f in frames if "lowest_z" in f]
        if lows:
            out["lowest_vertex_cm"] = {"min": round(100 * min(lows), 1), "max": round(100 * max(lows), 1),
                                       "frames_below_1cm": sum(z < -0.01 for z in lows)}
        for key, name in (("hand_depth", "hands_in_torso"), ("hand_head_depth", "hands_in_head"),
                          ("hand_hand_depth", "hands_in_each_other"), ("hand_leg_depth", "hands_in_legs")):
            depths = [f[key] for f in frames if key in f]
            if depths:
                out[name] = {"max_depth_cm": round(100 * max(depths), 1),
                             "frames_over_1cm": sum(d > 0.01 for d in depths)}
        out["loop_seam"] = am.loop_seam(frames[0]["local"], frames[-1]["local"], steps)
        out["hyperextension_deg"] = {k: am.hyperextension([f[k] for f in frames])
                                     for k in ("knee.L", "knee.R", "elbow.L", "elbow.R")}
        out["flexion_deg"] = {k: am.summary([f[k] for f in frames]) for k in ("knee.L", "knee.R", "elbow.L", "elbow.R")}
        out["forearm_twist_deg"] = {s: round(max(abs(f[f"twist.{s}"]) for f in frames), 1) for s in "LR"}
        out["finger_curl_deg"] = {s: am.summary([f[f"curl.{s}"] for f in frames]) for s in "LR"}
        out["finger_joint_max_deg"] = {s: round(max(f[f"curl_max.{s}"] for f in frames), 1) for s in "LR"}
        slide = out["foot_sliding"]
        h0, h1 = frames[0]["hips"], frames[-1]["hips"]
        r0, r1 = frames[0]["root"], frames[-1]["root"]
        travel = math.hypot(h1[0] - h0[0], h1[1] - h0[1])
        out["root_motion"] = {
            "hips_travel_cm": round(100 * travel, 1),
            "root_travel_cm": round(100 * math.hypot(r1[0] - r0[0], r1[1] - r0[1]), 1),
            "in_place": travel < 0.05,
            "ground_speed_m_s": (round(slide["ground_speed_cm_s"] / 100, 2)
                                 if slide["ground_speed_cm_s"] is not None else None),
        }
        return out


def _sole_series(soles: list, fps: float, loop: bool) -> list:
    """Per frame: the height of the sole's lowest vertex and that vertex's horizontal velocity (central differences;
    a loop wraps around, its last frame being its first again; the ends of other clips use one side)."""
    n = len(soles)
    last = n - 1 if loop and n > 2 else n  # a loop's final frame repeats its first
    out = []
    for i in range(last):
        j = int(np.argmin(soles[i][:, 2]))
        if loop and n > 2:
            prev, nxt, span = soles[(i - 1) % last][j], soles[(i + 1) % last][j], 2
        else:
            a, b = max(i - 1, 0), min(i + 1, n - 1)
            prev, nxt, span = soles[a][j], soles[b][j], max(b - a, 1)
        v = (nxt - prev) * fps / span
        out.append((float(soles[i][j, 2]), (float(v[0]), float(v[1]))))
    return out
