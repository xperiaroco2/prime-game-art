"""H1p (art #196): alien_hand_mesh.py's `dense` on a synthetic rigged tube inside Blender: a forearm-to-finger tube
(LeftLowerArm, the wrist's LowerArm/Hand blend, LeftHand, a Hand/LeftIndexProximal blend, LeftIndexProximal) with a
UV layer, saved, made denser, reopened. Prints DENSE_CHECK {json}: the counts, every old vertex's largest move, the
faces touching a LowerArm-weighted vertex before and after (untouched), the new vertices' weight sums and UV range."""
import json
import math
import sys
import tempfile
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_hand_mesh as M  # noqa: E402

N, RINGS, STEP, R = 12, 16, 0.01, 0.01


def weights(z):
    def ss(a, b, x):
        t = min(1.0, max(0.0, (x - a) / (b - a)))
        return t * t * (3 - 2 * t)
    h = ss(0.05, 0.07, z)
    f = ss(0.10, 0.12, z)
    return {"LeftLowerArm": 1 - h, "LeftHand": h * (1 - f), "LeftIndexProximal": f}


def scene(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ad = bpy.data.armatures.new("Arm")
    arm = bpy.data.objects.new("Armature", ad)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    for name, z0, z1 in (("LeftLowerArm", 0.0, 0.06), ("LeftHand", 0.06, 0.11), ("LeftIndexProximal", 0.11, 0.15)):
        b = ad.edit_bones.new(name)
        b.head, b.tail = (0, 0, z0), (0, 0, z1)
    bpy.ops.object.mode_set(mode="OBJECT")
    vs = [(R * math.cos(2 * math.pi * k / N), R * math.sin(2 * math.pi * k / N), j * STEP) for j in range(RINGS) for k in range(N)]
    fs = [(j * N + k, j * N + (k + 1) % N, (j + 1) * N + (k + 1) % N, (j + 1) * N + k) for j in range(RINGS - 1) for k in range(N)]
    me = bpy.data.meshes.new("Body")
    me.from_pydata(vs, [], fs)
    uv = me.uv_layers.new(name="UVMap")
    for p in me.polygons:
        j, k = divmod(p.index, N)
        for li, (dj, dk) in zip(p.loop_indices, ((0, 0), (0, 1), (1, 1), (1, 0))):
            uv.data[li].uv = ((k + dk) / N, (j + dj) / (RINGS - 1))
    me.materials.append(bpy.data.materials.new("M_AlienBody"))
    o = bpy.data.objects.new("Body", me)
    bpy.context.scene.collection.objects.link(o)
    for name in ("LeftLowerArm", "LeftHand", "LeftIndexProximal"):
        o.vertex_groups.new(name=name)
    for v in me.vertices:
        for n, w in weights(v.co.z).items():
            if w > 1e-6:
                o.vertex_groups[n].add([v.index], w, "REPLACE")
    o.modifiers.new("Armature", "ARMATURE").object = arm
    o.parent = arm
    bpy.ops.wm.save_as_mainfile(filepath=str(path))


def la_faces(o):
    la = o.vertex_groups["LeftLowerArm"].index
    hit = {v.index for v in o.data.vertices if any(g.group == la and g.weight > 0 for g in v.groups)}
    return sorted(tuple(sorted(o.data.vertices[i].co.to_tuple(6) for i in p.vertices)) for p in o.data.polygons
                  if any(i in hit for i in p.vertices))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="dense_check_"))
    src, out = tmp / "in.blend", tmp / "out.blend"
    scene(src)
    o = bpy.data.objects["Body"]
    old = [v.co.copy() for v in o.data.vertices]
    n0, f0 = len(old), len(o.data.polygons)
    la0 = la_faces(o)
    M.dense(str(src), str(out), 0.0, 1.0)
    bpy.ops.wm.open_mainfile(filepath=str(out))
    o = bpy.data.objects["Body"]
    me = o.data
    moved = max((me.vertices[i].co - old[i]).length for i in range(n0))
    wsum = [sum(g.weight for g in v.groups) for v in me.vertices[n0:]]
    la1 = la_faces(o)
    uv = me.uv_layers.active
    us = [uv.data[li].uv.copy() for p in me.polygons for li in p.loop_indices
          if any(i >= n0 for i in p.vertices)]
    rep = {"verts": [n0, len(me.vertices)], "faces": [f0, len(me.polygons)],
           "old_moved_mm": round(moved * 1000, 6), "lowerarm_faces_kept": la0 == la1, "lowerarm_faces": len(la0),
           "new_wsum": [round(min(wsum), 5), round(max(wsum), 5)] if wsum else None,
           "uv_layers": len(me.uv_layers), "new_uv_range": [round(min(u.x for u in us), 4), round(max(u.x for u in us), 4),
                                                             round(min(u.y for u in us), 4), round(max(u.y for u in us), 4)],
           "index_on_new": sum(1 for v in me.vertices[n0:] if any(g.group == o.vertex_groups["LeftIndexProximal"].index
                                                                     and g.weight > 0.5 for g in v.groups))}
    print("DENSE_CHECK " + json.dumps(rep), flush=True)


main()
