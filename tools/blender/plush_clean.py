"""The vault plush's cleanup (art#297, step 2): a raw Meshy GLB to a game-ready hand-held prop.

blender -b --factory-startup --python plush_clean.py -- <raw.glb> <out.glb> [--height 0.30] [--tris 4000]
    [--bake-size 2048]

Joins the model, drops loose specks, scales it to --height metres with its lowest point on the floor and its
footprint centred (front to -Y, as Meshy delivers it), decimates a copy to --tris triangles (the props' `hero`
class, docs/props.md), bakes the dense model's shading normals (its own normal map included) onto the copy's UVs in
Cycles, and writes the copy with the base colour, the roughness and the baked normal map; metallic 0 and no
emission (Meshy's metallic and emission maps are dropped: a plush has neither). Prints one JSON line `PLUSH_CLEAN
{...}` with the counts and sizes.
"""

import json
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
src, out = Path(argv[0]), Path(argv[1])
opts = dict(zip(argv[2::2], argv[3::2]))
height = float(opts.get("--height", 0.30))
target_tris = int(opts.get("--tris", 4000))
bake_size = int(opts.get("--bake-size", 2048))
SPECK = 0.005  # a loose part with less than this share of the vertices is a speck

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(src))
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
for o in bpy.context.scene.objects:
    o.select_set(o.type == "MESH")
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1:
    bpy.ops.object.join()
high = bpy.context.view_layer.objects.active
bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
for o in [o for o in bpy.context.scene.objects if o.type != "MESH"]:
    bpy.data.objects.remove(o)


def tri_count(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


# Specks: loose parts far smaller than the toy.
bm = bmesh.new()
bm.from_mesh(high.data)
# Meshy's GLB is split at every UV seam; weld first (UVs live on the loops, so they survive), or every patch counts
# as a loose part.
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
bm.verts.ensure_lookup_table()
seen, parts = set(), []
for v in bm.verts:
    if v.index in seen:
        continue
    stack, part = [v], []
    seen.add(v.index)
    while stack:
        cur = stack.pop()
        part.append(cur)
        for e in cur.link_edges:
            w = e.other_vert(cur)
            if w.index not in seen:
                seen.add(w.index)
                stack.append(w)
    parts.append(part)
total = len(bm.verts)
specks = [p for p in parts if len(p) < SPECK * total]
bmesh.ops.delete(bm, geom=[v for p in specks for v in p], context="VERTS")
bm.to_mesh(high.data)
bm.free()

# Real size: the lowest point on the floor, the footprint centred, uniform scale to the height.
co = [high.matrix_world @ v.co for v in high.data.vertices]
lo = Vector((min(c.x for c in co), min(c.y for c in co), min(c.z for c in co)))
hi = Vector((max(c.x for c in co), max(c.y for c in co), max(c.z for c in co)))
s = height / (hi.z - lo.z)
centre = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
for v in high.data.vertices:
    v.co = (v.co - centre) * s
high.data.update()
high.name = "plush_high"
source_tris = tri_count(high)

# The game mesh: a decimated copy; collapse keeps the UVs, so Meshy's base colour still fits.
low = high.copy()
low.data = high.data.copy()
low.name = "plush"
bpy.context.scene.collection.objects.link(low)
mod = low.modifiers.new("decimate", "DECIMATE")
mod.decimate_type = "COLLAPSE"
mod.ratio = min(1.0, target_tris / max(1, tri_count(high)))
mod.use_collapse_triangulate = True
bpy.context.view_layer.objects.active = low
bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.ops.object.shade_smooth()

# The source material's textures, by the socket they feed.
mat = high.active_material
tex = {}
for link in mat.node_tree.links:
    node = link.from_node
    while node.type not in {"TEX_IMAGE"} and node.inputs and node.inputs[0].links:
        node = node.inputs[0].links[0].from_node
    if node.type == "TEX_IMAGE":
        tex.setdefault(link.to_socket.name if link.to_node.type == "BSDF_PRINCIPLED" else link.to_node.type, node.image)

# Bake the dense model's shading normals onto the low copy.
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 1
normal_img = bpy.data.images.new("plush_normal", bake_size, bake_size, alpha=False, float_buffer=False)
normal_img.colorspace_settings.name = "Non-Color"
lowmat = mat.copy()
lowmat.name = "plush"
low.data.materials.clear()
low.data.materials.append(lowmat)
nt = lowmat.node_tree
bake_node = nt.nodes.new("ShaderNodeTexImage")
bake_node.image = normal_img
nt.nodes.active = bake_node
for o in scene.objects:
    o.select_set(o in (high, low))
bpy.context.view_layer.objects.active = low
bpy.ops.object.bake(type="NORMAL", use_selected_to_active=True, cage_extrusion=0.004, max_ray_distance=0.02,
                    normal_space="TANGENT", margin=8)
normal_img.filepath_raw = str(out.with_name(out.stem + "_normal.png"))
normal_img.file_format = "PNG"
normal_img.save()

# The low material: base colour, roughness, the baked normal; metallic 0, no emission.
for node in list(nt.nodes):
    nt.nodes.remove(node)
bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
outn = nt.nodes.new("ShaderNodeOutputMaterial")
nt.links.new(bsdf.outputs["BSDF"], outn.inputs["Surface"])
bsdf.inputs["Metallic"].default_value = 0.0
if "Base Color" in tex:
    n = nt.nodes.new("ShaderNodeTexImage")
    n.image = tex["Base Color"]
    nt.links.new(n.outputs["Color"], bsdf.inputs["Base Color"])
rough = tex.get("Roughness") or tex.get("Metallic")
if rough is not None:
    n = nt.nodes.new("ShaderNodeTexImage")
    n.image = rough
    n.image.colorspace_settings.name = "Non-Color"
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(n.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])  # glTF packs roughness in G
else:
    bsdf.inputs["Roughness"].default_value = 0.9
n = nt.nodes.new("ShaderNodeTexImage")
n.image = normal_img
nm = nt.nodes.new("ShaderNodeNormalMap")
nt.links.new(n.outputs["Color"], nm.inputs["Color"])
nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])

bpy.data.objects.remove(high)
for o in scene.objects:
    o.select_set(o == low)
out.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.export_scene.gltf(filepath=str(out), export_format="GLB", use_selection=True, export_apply=True,
                          export_yup=True, export_image_format="AUTO", export_tangents=True)

co = [v.co for v in low.data.vertices]
size = [max(c[i] for c in co) - min(c[i] for c in co) for i in range(3)]
print("PLUSH_CLEAN " + json.dumps({
    "source": str(src), "out": str(out), "source_tris": source_tris, "specks_removed": len(specks), "parts": len(parts),
    "tris": tri_count(low), "verts": len(low.data.vertices), "size_m": [round(x, 4) for x in size],
    "scale": round(s, 5), "textures": sorted(tex), "bake_size": bake_size}))
