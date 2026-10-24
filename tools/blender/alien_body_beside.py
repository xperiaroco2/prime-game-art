"""H2 (art #196, bodies_a): alien bodies and a raw target side by side at one scale and one light, T-posed at rest:
four views (front, three-quarter, side, back) of every body in a row, one row per view, in beside.png.

    blender -b --python alien_body_beside.py -- --out DIR --blend A.blend --blend B.blend --glb raw.glb

Each .blend's `Body` (on its armature at rest) and each GLB's meshes (centred in x, the sole moved to z = 0, as
alien_cage.py's Wrap reads a target) are shot alone with the same orthographic camera, in the given order (the
.blends first). Workbench, the review script's look."""
import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import alien_body_refit_review as R  # noqa: E402


def main():
    p = argparse.ArgumentParser(prog="alien_body_beside.py")
    p.add_argument("--out", required=True)
    p.add_argument("--blend", action="append", default=[])
    p.add_argument("--glb", action="append", default=[])
    a = p.parse_args(sys.argv[sys.argv.index("--") + 1:])
    os.makedirs(a.out, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    groups = []
    for path in a.blend:
        with bpy.data.libraries.load(path) as (src, dst):
            dst.objects = [n for n in src.objects if n in ("Body", "CharacterArmature")]
        objs = [o for o in dst.objects if o is not None]
        for o in objs:
            bpy.context.scene.collection.objects.link(o)
            if o.type == "ARMATURE":
                o.data.pose_position = "REST"
        groups.append([o for o in objs if o.type == "MESH"])
    for path in a.glb:
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=path)
        new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
        bpy.context.view_layer.update()
        pts = [o.matrix_world @ v.co for o in new for v in o.data.vertices]
        cx = 0.5 * (min(q.x for q in pts) + max(q.x for q in pts))
        lo = min(q.z for q in pts)
        for o in new:
            o.matrix_world = o.matrix_world.copy()
            o.matrix_world.translation -= Vector((cx, 0.0, lo))
        groups.append(new)
    bpy.context.view_layer.update()
    for k, objs in enumerate(groups):
        for o in objs:
            for m in o.data.materials:
                if m:
                    m.diffuse_color = (*R.BODY_RGB, 1.0)
            if not o.data.materials:
                mat = bpy.data.materials.new("Skin")
                mat.diffuse_color = (*R.BODY_RGB, 1.0)
                o.data.materials.append(mat)
    sc, cam = R.setup((320, 560))
    gm = bpy.data.materials.new("Ground")
    gm.diffuse_color = (0.42, 0.42, 0.42, 1.0)
    bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
    bpy.context.active_object.data.materials.append(gm)
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    top = max((o.evaluated_get(deps).matrix_world @ v.co).z for objs in groups for o in objs
              for v in o.evaluated_get(deps).to_mesh().vertices)
    paths = []
    for k, ang in enumerate((0, 45, 90, 180)):
        t = math.radians(ang)
        cams = []
        for j in range(len(groups)):  # each body alone at the origin, the same camera for all
            for i, objs in enumerate(groups):
                for o in objs:
                    o.hide_render = i != j
            c = Vector((0, 0, top / 2))
            R.look(cam, c + Vector((-8 * math.sin(t), -8 * math.cos(t), 0)), c, ortho=top * 1.08)
            cams.append(R.shot(sc, os.path.join(a.out, f"_beside_{k}_{j}.png"), (420, 640)))
        paths += cams
    R.stitch(paths, len(groups), os.path.join(a.out, "beside.png"))
    for q in paths:
        os.remove(q)
    print("BESIDE done", len(groups), "bodies", flush=True)


if __name__ == "__main__":
    main()
