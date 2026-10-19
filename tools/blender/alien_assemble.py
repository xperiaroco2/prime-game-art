"""The alien parts kit's assembled character (art #196, step S3): S1c's body and S2a's head welded into one skinned
mesh, the body's colour masks written, and every face part, crest and socket under the Head bone, exported as one
game GLB with the clips.

    blender -b --factory-startup --python-exit-code 1 --python tools/blender/alien_assemble.py -- \
        --body <S1c/build/alien_body.blend> --parts <S2a/alien_head_parts.blend> --parts-json <S2a/parts.json> \
        --out <review/char/alien-parts-kit/S3>

Writes <out>/build/alien_character.blend, <out>/export/alien_character.glb and <out>/export/character.json (the node
names of every variant, the lid angles, the hues, the triangle counts and the weld and mask measures).

The choice for Godot and three.js: ONE GLB with every variant as a named node, toggled by visibility (the scene
script and the showroom show one eye design, one mouth piece and at most one crest at a time). The parts sit under
socket nodes (Eye_L, Eye_R, Mouth, Crest) that are children of the Head joint, so Godot imports them under a
BoneAttachment3D and three.js under the Head bone; no socket transform has to be applied by hand. S2a's one-GLB-per-
part export stays valid for a page that loads parts one by one.

The method:
1. Weld: the head's last 24 vertices lie on the body's neck ring (S2a, weld error 0); the two meshes are joined
   (vertex groups and UV layers by name), the coincident ring vertices merged, every custom normal cleared and the
   whole mesh shaded smooth, so the ring's normals are the average over both sides' faces: no lighting seam.
2. Masks (the `masks` UV layer, TEXCOORD_1, read by godot/alien/alien_hue.gdshader): u = light (mint), v = accent
   (coral). The head keeps S2a's masks. On the body, u is the throat and belly: within BELLY_DEG of the front around
   each height's trunk centre, on trunk-weighted skin only, its lower end an oval at the crotch; up the neck it blends
   into the head ring's own values, so the mask is continuous at the weld. v is the knees (front), the elbows (back)
   and the knuckles (the proximal finger joints and the thumb's), each a soft sphere on the skin of that limb.
3. Parts: the socket empties are bone-parented to Head; each eye design and side gets its own node (eye_<design>_<L|R>)
   holding its ball and lids, the lids at the rest angle (parts.json: the lid's local X rotation); mouth pieces under
   Mouth, crests under Crest.
4. Export: the export command's options (tools/blender/export_glb.py) with the images on (the eyeballs' textures);
   the hue material is a plain teal Principled named alien_hue, which the game replaces by name with the shader.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_glb  # noqa: E402

TRUNK = ("Hips", "Spine", "Chest", "UpperChest", "Neck", "Head")
BELLY_DEG = 50.0  # half angle of the pale front, degrees around the trunk centre
BELLY_SOFT = 9.0  # its soft edge, degrees
CROTCH_Z = (0.80, 0.915)  # the oval's bottom and the height where it reaches its full width, m
NECK_BLEND = (1.30, 1.39)  # the body mask blends into the head ring's values over these heights, m
KNEE = {"offset": (0.0, -0.045, 0.0), "r": 0.040, "soft": 0.028}  # Blender: front is -Y; the body is in a T-pose
ELBOW = {"offset": (0.0, 0.030, 0.0), "r": 0.032, "soft": 0.026}  # the elbow points back (+Y)
KNUCKLE = {"r": 0.016, "soft": 0.014}
FINGERS = ("Index", "Middle", "Ring", "Thumb")
HUES_SRGB = {  # the saturated hues of the 10-17 sheet (g-s1), picked against u1's teal: art #196 S3
    "teal": (0.17, 0.56, 0.55),
    "coral": (0.90, 0.42, 0.34),
    "violet": (0.58, 0.46, 0.82),
}
PALE_SRGB = (0.80, 0.91, 0.80)  # u1's mint belly
LIGHT_MIX = 0.88
ACCENT_SRGB = (0.89, 0.42, 0.36)
ACCENT_MIX = 0.9


def smoothstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def srgb_to_lin(c):
    return tuple(((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c)


def args():
    p = argparse.ArgumentParser(prog="alien_assemble.py")
    p.add_argument("--body", required=True)
    p.add_argument("--parts", required=True)
    p.add_argument("--parts-json", required=True)
    p.add_argument("--out", required=True)
    return p.parse_args(sys.argv[sys.argv.index("--") + 1:])


def append_all(path):
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = list(src.objects)
    for o in dst.objects:
        bpy.context.scene.collection.objects.link(o)
    return {o.name: o for o in dst.objects}


def weights(body, groups):
    """Per vertex: {group name: weight} for the named groups."""
    names = {g.index: g.name for g in body.vertex_groups if g.name in groups}
    out = []
    for v in body.data.vertices:
        out.append({names[g.group]: g.weight for g in v.groups if g.group in names})
    return out


def ring_profile(head, ring_ids, uv_name):
    """The head's mask u at its 24 ring vertices, by angle index (k at 2*pi*k/24 from the front towards +X)."""
    me = head.data
    uv = me.uv_layers[uv_name].data
    vals = {i: [] for i in ring_ids}
    for loop in me.loops:
        if loop.vertex_index in vals:
            vals[loop.vertex_index].append(uv[loop.index].uv[0])
    return [sum(vals[i]) / max(1, len(vals[i])) for i in ring_ids]


def body_masks(body, arm, ring, head_ring_u):
    """Writes the body's masks UV layer (u light, v accent); returns its measures."""
    me = body.data
    bones = arm.data.bones
    trunk_w = [sum(w.values()) for w in weights(body, TRUNK)]
    limb = {}
    for side in ("Left", "Right"):
        limb[f"{side}leg"] = [sum(w.values()) for w in weights(body, (f"{side}UpperLeg", f"{side}LowerLeg", f"{side}Foot"))]
        limb[f"{side}arm"] = [sum(w.values()) for w in weights(body, (f"{side}UpperArm", f"{side}LowerArm"))]
        hand = [f"{side}Hand"] + [f"{side}{f}{j}" for f in FINGERS for j in ("Proximal", "Intermediate", "Distal", "Metacarpal")]
        limb[f"{side}hand"] = [sum(w.values()) for w in weights(body, tuple(hand))]
    # each height's trunk centre (1 cm bins, trunk-weighted vertices)
    bins = {}
    for v, w in zip(me.vertices, trunk_w):
        if w > 0.8:
            bins.setdefault(int(v.co.z * 100), []).append(v.co.y)
    centre = {k: (min(ys) + max(ys)) / 2 for k, ys in bins.items()}

    def yc(z):
        k = int(z * 100)
        for d in range(0, 30):
            for kk in (k - d, k + d):
                if kk in centre:
                    return centre[kk]
        return ring["centre"][1]

    cx, cy = ring["centre"]
    n = len(head_ring_u)

    def ring_u(x, y):
        a = math.atan2(x, cy - y) % (2 * math.pi)
        f = a / (2 * math.pi) * n
        i = int(f) % n
        t = f - int(f)
        return head_ring_u[i] * (1 - t) + head_ring_u[(i + 1) % n] * t

    spots = []
    for side in ("Left", "Right"):
        knee = bones[f"{side}LowerLeg"].head_local + Vector(KNEE["offset"])
        elbow = bones[f"{side}LowerArm"].head_local + Vector(ELBOW["offset"])
        spots.append((knee, KNEE, limb[f"{side}leg"]))
        spots.append((elbow, ELBOW, limb[f"{side}arm"]))
        for f in FINGERS:
            spots.append((bones[f"{side}{f}Proximal"].head_local.copy(), KNUCKLE, limb[f"{side}hand"]))
    light = [0.0] * len(me.vertices)
    accent = [0.0] * len(me.vertices)
    for v in me.vertices:
        p = v.co
        i = v.index
        # light: the belly and throat
        ang = math.degrees(math.atan2(abs(p.x), yc(p.z) - p.y))
        width = BELLY_DEG * math.sqrt(smoothstep(CROTCH_Z[0], CROTCH_Z[1], p.z))
        u = (1.0 - smoothstep(width - BELLY_SOFT, width + BELLY_SOFT, ang)) if width > 1.0 else 0.0
        u *= smoothstep(0.45, 0.85, trunk_w[i])
        t = smoothstep(NECK_BLEND[0], NECK_BLEND[1], p.z)
        light[i] = u * (1 - t) + ring_u(p.x, p.y) * t
        a = 0.0
        for c, s, lw in spots:
            if lw[i] < 0.3:
                continue
            d = (p - c).length
            a = max(a, (1.0 - smoothstep(s["r"], s["r"] + s["soft"], d)) * smoothstep(0.3, 0.7, lw[i]))
        accent[i] = a
    if "masks" not in me.uv_layers:
        extra = [u for u in me.uv_layers if u.name != "UVMap"]
        if extra:
            extra[0].name = "masks"
        else:
            me.uv_layers.new(name="masks")
    uv = me.uv_layers["masks"].data
    for loop in me.loops:
        uv[loop.index].uv = (light[loop.vertex_index], accent[loop.vertex_index])
    return {"light_vertices": sum(1 for x in light if x > 0.5), "accent_vertices": sum(1 for x in accent if x > 0.5),
            "vertices": len(me.vertices)}


def weld(body, head):
    """Joins the head into the body, merges the coincident ring vertices, clears custom normals, shades smooth."""
    nb = len(body.data.vertices)
    bpy.ops.object.select_all(action="DESELECT")
    head.select_set(True)
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    me = body.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    before = len(bm.verts)
    head_verts = [v for v in bm.verts if v.index >= nb]
    body_ring = [v for v in bm.verts if v.index < nb and abs(v.co.z - 1.39) < 0.01]
    bmesh.ops.remove_doubles(bm, verts=head_verts + body_ring, dist=1e-5)
    merged = before - len(bm.verts)
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    with bpy.context.temp_override(object=body, active_object=body, selected_editable_objects=[body]):
        if me.has_custom_normals:
            bpy.ops.mesh.customdata_custom_splitnormals_clear()
    me.update()
    # the boundary left open after the weld (should be none at the neck)
    bm = bmesh.new()
    bm.from_mesh(me)
    open_neck = sum(1 for e in bm.edges if e.is_boundary and all(1.3 < v.co.z < 1.5 for v in e.verts))
    bm.free()
    return {"merged": merged, "open_edges_at_neck": open_neck, "vertices": len(me.vertices),
            "triangles": sum(len(p.vertices) - 2 for p in me.polygons)}


def set_parent(o, parent, bone=None):
    mw = o.matrix_world.copy()
    o.parent = parent
    if bone:
        o.parent_type = "BONE"
        o.parent_bone = bone
    else:
        o.parent_type = "OBJECT"
    o.matrix_parent_inverse.identity()
    bpy.context.view_layer.update()
    o.matrix_world = mw
    bpy.context.view_layer.update()


def plain_hue(mat, srgb):
    """The export's stand-in: a plain Principled named alien_hue in the base hue (the game swaps in the shader)."""
    nt = mat.node_tree
    nt.nodes.clear()
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf.inputs["Base Color"].default_value = (*srgb_to_lin(srgb), 1.0)
    bsdf.inputs["Roughness"].default_value = 0.62
    nt.links.new(bsdf.outputs["BSDF"], outn.inputs["Surface"])


def tris(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def main():
    a = args()
    out = Path(a.out)
    (out / "build").mkdir(parents=True, exist_ok=True)
    (out / "export").mkdir(parents=True, exist_ok=True)
    pj = json.loads(Path(a.parts_json).read_text(encoding="utf-8"))
    bpy.ops.wm.open_mainfile(filepath=a.body)
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    body = bpy.data.objects["Body"]
    for pb in arm.pose.bones:
        pb.location = (0.0, 0.0, 0.0)
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)
    if arm.animation_data:
        arm.animation_data.action = None
    ring = json.loads((Path(a.body).parent / "neck_ring.json").read_text(encoding="utf-8"))
    objs = append_all(a.parts)
    bpy.context.view_layer.update()  # the appended objects' world matrices, before any is re-parented
    head = objs["alien_head"]
    rep = {"ring": {"z": ring["z"], "centre": ring["centre"]}}
    head_ring_u = ring_profile(head, pj["head"]["ring_vertices_ordered"], "masks")
    rep["head_ring_light"] = [round(x, 3) for x in head_ring_u]
    rep["body_masks"] = body_masks(body, arm, ring, head_ring_u)

    # the materials: the body takes the head's alien_hue
    hue = bpy.data.materials["alien_hue"]
    body.data.materials.clear()
    body.data.materials.append(hue)
    for p in body.data.polygons:
        p.material_index = 0

    # sockets and parts, re-parented before the head object goes
    sockets = {k: objs[k] for k in ("Eye_L", "Eye_R", "Mouth", "Crest")}
    for s in sockets.values():
        set_parent(s, arm, "Head")
    nodes = {"eyes": {}, "mouths": {}, "crests": []}
    for design in ("bored", "manic"):
        nodes["eyes"][design] = {}
        for side in ("L", "R"):
            e = bpy.data.objects.new(f"eye_{design}_{side}", None)
            bpy.context.scene.collection.objects.link(e)
            e.parent = sockets[f"Eye_{side}"]  # the socket's own frame: identity local transform
            e.matrix_parent_inverse.identity()
            e.matrix_basis.identity()
            bpy.context.view_layer.update()
            names = {}
            for piece in ("ball", "lid_upper", "lid_lower"):
                o = objs[f"eye_{design}_{piece}_{side}"]
                set_parent(o, e)
                names[piece] = o.name
            nodes["eyes"][design][side] = {"node": e.name, **names}
    for name, o in objs.items():
        if name.startswith("mouth_"):
            set_parent(o, sockets["Mouth"])
        elif name.startswith("crest_"):
            set_parent(o, sockets["Crest"])
            nodes["crests"].append(name)
    for design in ("frog", "overbite"):
        nodes["mouths"][design] = {v: f"mouth_{design}_{v}" for v in ("rest", "M", "small", "A", "E", "O")}
    nodes["mouths"]["overbite_teeth"] = "mouth_overbite_teeth"
    nodes["crests"].sort()
    rep["part_triangles"] = {n: tris(o) for n, o in objs.items() if o.type == "MESH" and n != "alien_head"}
    rep["head_triangles"] = tris(head)
    rep["weld"] = weld(body, head)
    body.name = "Body"
    for o in bpy.data.objects:  # the lid's local X angle in its eye node, as parts.json gives it
        if "_lid_" in o.name:
            o.rotation_mode = "XYZ"
    lid_check = {}
    for design, sides in nodes["eyes"].items():
        for side, d in sides.items():
            for lid in ("ball", "lid_upper", "lid_lower"):
                o = bpy.data.objects[d[lid]]
                lid_check[d[lid]] = [round(math.degrees(x), 2) for x in o.rotation_euler]
    rep["lid_local_euler_deg"] = lid_check
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "build" / "alien_character.blend"))

    plain_hue(hue, HUES_SRGB["teal"])
    opts = dict(export_glb.options(False), export_image_format="AUTO")
    glb = out / "export" / "alien_character.glb"
    res = bpy.ops.export_scene.gltf(filepath=str(glb), **opts)
    if res != {"FINISHED"}:
        raise SystemExit(f"export: {res}")
    character = {
        "note": "art #196 S3: one GLB, every variant a named node under the Head joint's socket nodes; show one eye "
                "design (both sides), one mouth piece (plus the teeth with every overbite piece), at most one crest. "
                "Lids: set the lid node's local X rotation (glTF and Blender agree on X) to lid_rot_x_deg.",
        "glb": "export/alien_character.glb",
        "sockets": list(sockets),
        "nodes": nodes,
        "lid_rot_x_deg": {d: pj["eyes"][d]["lid_rot_x_deg"] for d in ("bored", "manic")},
        "default_lid_state": "rest",
        "blink_ms": pj["blink_ms"],
        "hues_srgb": HUES_SRGB,
        "pale_srgb": PALE_SRGB, "light_mix": LIGHT_MIX, "accent_srgb": ACCENT_SRGB, "accent_mix": ACCENT_MIX,
        "materials": {"alien_hue": "replace with godot/alien/alien_hue.gdshader, instance uniform hue"},
        "clips": sorted(x.name.split("|")[-1] for x in bpy.data.actions),
        "report": rep,
    }
    (out / "export" / "character.json").write_text(json.dumps(character, indent=1), encoding="utf-8", newline="\n")
    print("ASSEMBLE", json.dumps(rep))


main()
