"""The vault plush's game mesh (art#297, step 3): the painted full model baked onto a decimated copy with new UVs.

blender -b --factory-startup --python plush_bake.py -- <painted full.glb> <albedo.png> <mask.png> <out dir>
    [--tris 4000] [--size 2048] [--blend out.blend]

Why: decimating Meshy's model in place (plush_clean.py with --tris) keeps its UVs, but the collapse moves the corners
of Meshy's many small UV islands, so some triangles sample the next island's texels: black specks by an eye and on
the belly, a dark crack under a lid (the engineer, art#297, 2026-10-23). Here the full model keeps its own UVs and
paint, a decimated copy gets a fresh Smart UV Project layout, and Cycles bakes the full model onto the copy (selected
to active): the albedo and the shader's mask as emission, the shading normal as a tangent-space normal map. Writes
into <out dir> plush_albedo.png (sRGB), plush_mask.png and plush_normal.png (linear) and plush.glb (the copy with the
baked albedo and normal, roughness 1, metallic 0: the plain-PBR fallback). Prints one line `PLUSH_BAKE {...}`.
"""

import json
import math
import sys
from pathlib import Path

import bmesh
import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
src, albedo_path, mask_path, out = Path(argv[0]), Path(argv[1]), Path(argv[2]), Path(argv[3])
opts = dict(zip(argv[4::2], argv[5::2]))
target_tris = int(opts.get("--tris", 4000))
size = int(opts.get("--size", 2048))
blend_out = opts.get("--blend")  # also save the game mesh with its packed maps as a .blend (the asset's source)
out.mkdir(parents=True, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(src))
high = next(o for o in bpy.context.scene.objects if o.type == "MESH")
high.name = "plush_full"
high_mat = high.active_material


def tri_count(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


# the game mesh: a decimated copy with one fresh UV layout
low = high.copy()
low.data = high.data.copy()
low.name = "plush"
bpy.context.scene.collection.objects.link(low)
# a GLB comes back split at every UV seam; welded first, or the collapse opens the seams into holes
bm = bmesh.new()
bm.from_mesh(low.data)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
bm.to_mesh(low.data)
bm.free()
mod = low.modifiers.new("decimate", "DECIMATE")
mod.decimate_type = "COLLAPSE"
mod.ratio = min(1.0, target_tris / max(1, tri_count(high)))
mod.use_collapse_triangulate = True
for o in bpy.context.scene.objects:
    o.select_set(o == low)
bpy.context.view_layer.objects.active = low
bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.ops.object.shade_smooth()
while low.data.uv_layers:
    low.data.uv_layers.remove(low.data.uv_layers[0])
low.data.uv_layers.new(name="UVMap")
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.004, area_weight=0.0)
bpy.ops.uv.pack_islands(margin=0.004, rotate=True)
bpy.ops.object.mode_set(mode="OBJECT")

scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 1
bake = scene.render.bake
bake.use_selected_to_active = True
bake.cage_extrusion = 0.003
bake.max_ray_distance = 0.012
bake.margin = 12

lowmat = bpy.data.materials.new("plush")
lowmat.use_nodes = True
low.data.materials.clear()
low.data.materials.append(lowmat)
target = lowmat.node_tree.nodes.new("ShaderNodeTexImage")
lowmat.node_tree.nodes.active = target


def new_image(name, colorspace):
    img = bpy.data.images.new(name, size, size, alpha=False, float_buffer=False)
    img.colorspace_settings.name = colorspace
    return img


def emit_material(image_path, colorspace):
    """A material on the full model that emits the image as it is (the bake reads it back unlit)."""
    m = bpy.data.materials.new(f"emit_{Path(image_path).stem}")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(image_path))
    tex.image.colorspace_settings.name = colorspace
    emit = nt.nodes.new("ShaderNodeEmission")
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tex.outputs["Color"], emit.inputs["Color"])
    nt.links.new(emit.outputs["Emission"], outn.inputs["Surface"])
    return m


def bake_into(img, file_name, kind, high_material):
    high.data.materials[0] = high_material
    target.image = img
    for o in scene.objects:
        o.select_set(o in (high, low))
    bpy.context.view_layer.objects.active = low
    if kind == "EMIT":
        bpy.ops.object.bake(type="EMIT")
    else:
        bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT")
    img.filepath_raw = str(out / file_name)  # by name: the imported GLB already holds images called plush_*
    img.file_format = "PNG"
    img.save()


albedo = new_image("plush_albedo", "sRGB")
bake_into(albedo, "plush_albedo.png", "EMIT", emit_material(albedo_path, "sRGB"))
mask = new_image("plush_mask", "Non-Color")
bake_into(mask, "plush_mask.png", "EMIT", emit_material(mask_path, "Non-Color"))
normal = new_image("plush_normal", "Non-Color")
bake_into(normal, "plush_normal.png", "NORMAL", high_mat)

# the plain-PBR fallback on the game mesh
nt = lowmat.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
outn = nt.nodes.new("ShaderNodeOutputMaterial")
nt.links.new(bsdf.outputs["BSDF"], outn.inputs["Surface"])
bsdf.inputs["Roughness"].default_value = 1.0
bsdf.inputs["Metallic"].default_value = 0.0
tex = nt.nodes.new("ShaderNodeTexImage")
tex.image = albedo
nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
ntex = nt.nodes.new("ShaderNodeTexImage")
ntex.image = normal
nmap = nt.nodes.new("ShaderNodeNormalMap")
nt.links.new(ntex.outputs["Color"], nmap.inputs["Color"])
nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])

bpy.data.objects.remove(high)
lowmat.name = "vault_plush"  # the full model's own material held "plush": the GLB showed "plush.001"
for o in scene.objects:
    o.select_set(o == low)
bpy.ops.export_scene.gltf(filepath=str(out / "plush.glb"), export_format="GLB", use_selection=True,
                          export_yup=True, export_image_format="AUTO", export_tangents=True)
if blend_out:
    for img in (albedo, normal, mask):
        img.pack()
    Path(blend_out).parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_out), compress=True)
co = [v.co for v in low.data.vertices]
dims = [max(c[i] for c in co) - min(c[i] for c in co) for i in range(3)]
print("PLUSH_BAKE " + json.dumps({"source": str(src), "out": str(out), "tris": tri_count(low),
                                  "verts": len(low.data.vertices), "size_m": [round(x, 4) for x in dims],
                                  "bake_size": size}))
