"""The `bench` command's proxy character (art #212): a finished character .blend made into a heavier stand-in for the
character budgets' measurement, saved as one .blend per face-morph count. The runner calls it (tools/run.py bench
--proxy-from); by hand, background only:

  blender -b --factory-startup --python-exit-code 1 --python tools/blender/bench_proxy.py -- \
      --blend <finished>/alien_base.blend --out <dir> --tris 40000 --morphs 0,32,64 --shadow-tris 7000

Steps, on the largest skinned mesh (the body):
- its shape keys are dropped (a proxy, not a face);
- a copy decimated to --shadow-tris becomes `bench_shadow`, the low-poly shadow caster the bench switches on;
- the body is subdivided once (Catmull-Clark, the vertex groups interpolated) and decimated so the whole character
  (with every other mesh) has about --tris triangles; weights limited to 4 per vertex and normalized;
- the head (vertices whose largest weight is on Head, Jaw or an eye bone) is split off as `<body>_head`, the only mesh
  that carries face morphs, as the contract's [face] wants;
- each image is swapped for its own 2048 bake beside the .blend, matched by stem (`alien_body_col` or
  `alien_body_col.png` takes `alien_body_col_2048.png`); an image without one is kept and listed as kept;
- per count N of --morphs: N shape keys on the head, each a smooth bump of 1 to 3 mm over a random 3 cm patch (seeded),
  saved as <out>/proxy_m<N>.blend. tools/run.py export --textured makes the GLBs.

Prints BENCH_PROXY <json> with the triangle and vertex counts per mesh.
"""

import json
import math
import os
import random
import sys

HEAD_BONES = ("Head", "Jaw", "LeftEye", "RightEye")
SEED = 212


def parse(argv):
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--blend", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--tris", type=int, default=40000)
    p.add_argument("--morphs", default="0,32,64")
    p.add_argument("--shadow-tris", type=int, default=7000)
    return p.parse_args(argv)


def tris(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def apply_modifier(bpy, obj, kind, **settings):
    mod = obj.modifiers.new(name=f"bench_{kind}", type=kind)
    for k, v in settings.items():
        setattr(mod, k, v)
    with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj]):
        bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=0)
        bpy.ops.object.modifier_apply(modifier=mod.name)


def limit_weights(bpy, obj):
    with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj]):
        bpy.ops.object.vertex_group_limit_total(group_select_mode="ALL", limit=4)
        bpy.ops.object.vertex_group_normalize_all(group_select_mode="ALL", lock_active=False)


def split_head(bpy, body):
    names = {g.index: g.name for g in body.vertex_groups}
    head = set()
    for v in body.data.vertices:
        if v.groups:
            top = max(v.groups, key=lambda g: g.weight)
            if names.get(top.group) in HEAD_BONES:
                head.add(v.index)
    if not head:
        raise RuntimeError("no vertex has its largest weight on " + ", ".join(HEAD_BONES))
    for p in body.data.polygons:
        p.select = all(i in head for i in p.vertices)
    for v in body.data.vertices:
        v.select = False
    for e in body.data.edges:
        e.select = False
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_mode(type="FACE")
    bpy.ops.object.mode_set(mode="OBJECT")
    for p in body.data.polygons:
        p.select = all(i in head for i in p.vertices)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.separate(type="SELECTED")
    bpy.ops.object.mode_set(mode="OBJECT")
    new = [o for o in bpy.context.selected_objects if o is not body]
    if len(new) != 1:
        raise RuntimeError(f"the head split made {len(new)} objects")
    new[0].name = new[0].data.name = f"{body.name}_head"
    return new[0]


def stem(name):
    """A file or image name without its extension or Blender's .001 suffix, lower case."""
    name = name.replace("\\", "/").rsplit("/", 1)[-1]  # "//textures/x.png": Blender's relative path, not a UNC share
    base, ext = os.path.splitext(name)
    if ext[1:].isdigit():  # "alien_body_col.001"
        base = os.path.splitext(base)[0]
    elif ext.lower() not in (".png", ".jpg", ".jpeg", ".tga", ".exr", ".webp"):
        base = name
    return base.lower()


def swap_images(bpy, folder):
    """Swaps each image for its own bake, <stem>_2048.png beside the .blend (the stem of its name, else of its file);
    returns the swaps and the images kept."""
    bakes = {f.lower(): f for f in os.listdir(folder) if f.lower().endswith("_2048.png")}
    swapped = []
    for img in list(bpy.data.images):
        stems = [stem(img.name)] + ([stem(img.filepath)] if img.filepath else [])
        if img.type != "IMAGE" or stems[0].endswith("_2048"):
            continue
        bake = next((bakes[f"{s}_2048.png"] for s in stems if f"{s}_2048.png" in bakes), None)
        if bake is None:
            swapped.append(f"{img.name} kept: no {stems[0]}_2048.png")
            print(f"bench_proxy: {img.name} kept, no {stems[0]}_2048.png beside the .blend")
            continue
        new = bpy.data.images.load(os.path.join(folder, bake))
        new.colorspace_settings.name = img.colorspace_settings.name
        new.pack()  # the saved proxies stand alone
        img.user_remap(new)
        new.name = img.name + "_2048"
        swapped.append(f"{img.name} -> {bake} {tuple(new.size)}")
    return swapped


def add_morphs(head, count, rng):
    head.shape_key_clear()
    if count == 0:
        return
    head.shape_key_add(name="Basis", from_mix=False)
    verts = head.data.vertices
    for k in range(count):
        key = head.shape_key_add(name=f"bench_{k:02d}", from_mix=False)
        centre = verts[rng.randrange(len(verts))].co.copy()
        radius, depth = 0.03, rng.uniform(0.001, 0.003)
        for v in verts:
            d = (v.co - centre).length
            if d < radius:
                fall = 0.5 * (1.0 + math.cos(math.pi * d / radius))
                key.data[v.index].co = v.co + v.normal * depth * fall


def main():
    import bpy

    args = parse(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    bpy.ops.wm.open_mainfile(filepath=args.blend)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    skinned = [o for o in meshes if any(m.type == "ARMATURE" for m in o.modifiers)]
    if not skinned:
        raise RuntimeError("no skinned mesh")
    body = max(skinned, key=tris)
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    body.shape_key_clear()
    others = sum(tris(o) for o in meshes if o is not body)
    before = tris(body)

    shadow = body.copy()
    shadow.data = body.data.copy()
    shadow.name = shadow.data.name = "bench_shadow"
    for col in body.users_collection:
        col.objects.link(shadow)
    apply_modifier(bpy, shadow, "DECIMATE", ratio=min(1.0, args.shadow_tris / max(1, before)))
    limit_weights(bpy, shadow)

    apply_modifier(bpy, body, "SUBSURF", levels=1, render_levels=1, subdivision_type="CATMULL_CLARK")
    want = max(1000, args.tris - others)
    if tris(body) > want:
        apply_modifier(bpy, body, "DECIMATE", ratio=want / tris(body))
    limit_weights(bpy, body)
    head = split_head(bpy, body)
    swapped = swap_images(bpy, os.path.dirname(os.path.abspath(args.blend)))

    os.makedirs(args.out, exist_ok=True)
    counts = {o.name: {"triangles": tris(o), "vertices": len(o.data.vertices)}
              for o in bpy.context.scene.objects if o.type == "MESH"}
    record = {"source": args.blend, "body_triangles_before": before, "meshes": counts, "images": swapped,
              "character_triangles": sum(c["triangles"] for n, c in counts.items() if n != "bench_shadow"),
              "blends": {}}
    for n in sorted({int(x) for x in args.morphs.split(",") if x.strip()}, reverse=True):
        add_morphs(head, n, random.Random(SEED))
        path = os.path.join(args.out, f"proxy_m{n}.blend")
        bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
        record["blends"][str(n)] = path
    print("BENCH_PROXY " + json.dumps(record))


if __name__ == "__main__":
    main()
