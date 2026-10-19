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
1. Weld: the head's last 48 vertices (the densified ring, S8b) lie on the body's neck ring (S2a, weld error 0); the two meshes are joined
   (vertex groups and UV layers by name), the coincident ring vertices merged, every custom normal cleared and the
   whole mesh shaded smooth, so the ring's normals are the average over both sides' faces: no lighting seam. The
   neck across the weld is then faired as one smooth surface (NECK_FAIR, S8b), so no pleated collar or crease shows;
   S9b then lofts the neck as one column from the shoulders to under the jaw and gives it a smooth weight field
   (alien_neck.py).
2. Masks (the `masks` UV layer, TEXCOORD_1, read by godot/alien/alien_hue.gdshader; the glTF export stores V
   flipped, the shader flips it back): u = light, v = accent. The head keeps S2a's masks. On the body, u is the
   throat and belly: the front half (in front of each height's midline centre, the middle of the vertices within
   MIDLINE_X of x = 0) within BELLY_HALF_W of x = 0, a panel narrowing to the throat and ending in an oval at the
   crotch (the T-pose arms lie outside it), neighbour-averaged MASK_SMOOTH times (the ring kept); up the neck it blends into the head ring's own
   values, so the mask is continuous at the weld. v is the knees (front), the elbows (back)
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
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_neck  # noqa: E402
import export_glb  # noqa: E402

from alien_face import ACCENT, EYE_AIM_IN  # noqa: E402  (S5; godot/alien/alien.gd aim_in_deg)
BELLY_HALF_W = [(0.78, 0.0), (0.80, 0.045), (0.86, 0.082), (0.95, 0.100), (1.05, 0.100), (1.15, 0.090), (1.25, 0.074),
                (1.33, 0.058), (1.40, 0.046)]  # S8b: u1's oval on the cage body (S7's read as a strip)
# the pale panel's half width in x by height (z, m): u1's throat-to-belly panel, an oval at the crotch
BELLY_SOFT = 0.04  # its soft edge, m (S8b: 0.018; S9: rf2's soft teal-to-mint blend)
# S8b: the neck across the weld faired as one smooth surface. Each vertex's distance from the ring's axis (in the ring's
# ellipse units) is replaced by a Gaussian average of its neighbours' by angle and height, so the ripple of the 24-to-48
# join and the decimated head cut (a ruffled collar of pleats) and the creases at the loft's ends go, while the neck's
# own shape (lower harmonics, its flare) stays. Full between z[1] and z[2], easing to none at z[0] and z[3] (m).
NECK_FAIR = {"z": (1.345, 1.360, 1.418, 1.445), "sigma_deg": 20.0, "sigma_z": 0.006, "r_max": 1.22}
NECK_R = 0.075  # only vertices this close to the ring's axis (the chin, from z 1.452 down to its underside, stays)
MIDLINE_X = 0.05  # the trunk centre per height: the middle of the body's vertices within this of x = 0, m
MASK_SMOOTH = 4  # neighbour-average passes over the body's light mask (the mesh is coarse: about 2 cm edges)
NECK_BLEND = (1.30, 1.39)  # the body mask blends into the head ring's values over these heights, m
KNEE = {"offset": (0.0, -0.045, 0.0), "r": 0.040, "soft": 0.028}  # Blender: front is -Y; the body is in a T-pose
ELBOW = {"offset": (0.0, 0.030, 0.0), "r": 0.032, "soft": 0.026}  # the elbow points back (+Y)
KNUCKLE = {"r": 0.011, "soft": 0.012, "dorsal": (-0.1, 0.6)}  # S9: the back of the hand only (normal z, T-pose palms down)
FINGERS = ("Index", "Middle", "Ring", "Thumb")
HUES_SRGB = {  # the saturated hues of the 10-17 sheet (g-s1), picked against u1's teal: art #196 S3
    "teal": (0.11, 0.48, 0.51),  # S9: rf2's deeper, bluer teal (S3: (0.17, 0.56, 0.55))
    "coral": (0.90, 0.42, 0.34),
    "violet": (0.58, 0.46, 0.82),
}
PALE_SRGB = {"teal": (0.86, 0.92, 0.81), "coral": (0.98, 0.84, 0.74), "violet": (0.87, 0.83, 0.96)}  # u1's mint belly
LIGHT_MIX = 0.88
ACCENT_SRGB = ACCENT  # alien_face.ACCENT, also alien_hue.gdshader's accent default
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
    """The head's mask u at its ring vertices (48), by angle index (k at 2*pi*k/n from the front towards +X)."""
    me = head.data
    uv = me.uv_layers[uv_name].data
    vals = {i: [] for i in ring_ids}
    for loop in me.loops:
        if loop.vertex_index in vals:
            vals[loop.vertex_index].append(uv[loop.index].uv[0])
    return [sum(vals[i]) / max(1, len(vals[i])) for i in ring_ids]


def half_width(z):
    pts = BELLY_HALF_W
    if z <= pts[0][0]:
        return 0.0
    for (z0, w0), (z1, w1) in zip(pts, pts[1:]):
        if z <= z1:
            return w0 + (w1 - w0) * (z - z0) / (z1 - z0)
    return pts[-1][1]


def body_masks(body, arm, ring, head_ring_u):
    """Writes the body's masks UV layer (u light, v accent); returns its measures."""
    me = body.data
    bones = arm.data.bones
    limb = {}
    for side in ("Left", "Right"):
        limb[f"{side}leg"] = [sum(w.values()) for w in weights(body, (f"{side}UpperLeg", f"{side}LowerLeg", f"{side}Foot"))]
        limb[f"{side}arm"] = [sum(w.values()) for w in weights(body, (f"{side}UpperArm", f"{side}LowerArm"))]
        hand = [f"{side}Hand"] + [f"{side}{f}{j}" for f in FINGERS for j in ("Proximal", "Intermediate", "Distal", "Metacarpal")]
        limb[f"{side}hand"] = [sum(w.values()) for w in weights(body, tuple(hand))]
    # each height's trunk centre (1 cm bins, the midline strip)
    bins = {}
    for v in me.vertices:
        if abs(v.co.x) < MIDLINE_X:
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
        hw = half_width(p.z)
        u = (1.0 - smoothstep(hw - BELLY_SOFT, hw + BELLY_SOFT, abs(p.x))) if hw > 0.0 else 0.0
        u *= smoothstep(-0.005, 0.025, yc(p.z) - p.y)
        t = smoothstep(NECK_BLEND[0], NECK_BLEND[1], p.z)
        light[i] = u * (1 - t) + ring_u(p.x, p.y) * t
        a = 0.0
        for c, s, lw in spots:
            if lw[i] < 0.3:
                continue
            d = (p - c).length
            side_w = smoothstep(*s["dorsal"], v.normal.z) if "dorsal" in s else 1.0
            a = max(a, (1.0 - smoothstep(s["r"], s["r"] + s["soft"], d)) * smoothstep(0.3, 0.7, lw[i]) * side_w)
        accent[i] = a
    nbrs = [[] for _ in me.vertices]
    for e in me.edges:
        a_, b_ = e.vertices
        nbrs[a_].append(b_)
        nbrs[b_].append(a_)
    fixed = [abs(v.co.z - ring["z"]) < 0.004 for v in me.vertices]
    for _ in range(MASK_SMOOTH):
        light = [light[i] if fixed[i] or not nbrs[i] else 0.5 * light[i] + 0.5 * sum(light[j] for j in nbrs[i]) / len(nbrs[i])
                 for i in range(len(light))]
    back_lit = sum(1 for v in me.vertices if v.normal.y > 0.3 and light[v.index] > 0.2)
    if "masks" not in me.uv_layers:
        extra = [u for u in me.uv_layers if u.name != "UVMap"]
        if extra:
            extra[0].name = "masks"
        else:
            me.uv_layers.new(name="masks")
    uv = me.uv_layers["masks"].data
    for loop in me.loops:
        uv[loop.index].uv = (light[loop.vertex_index], accent[loop.vertex_index])
    return {"light_vertices": sum(1 for x in light if x > 0.5), "back_facing_light_vertices": back_lit, "accent_vertices": sum(1 for x in accent if x > 0.5),
            "vertices": len(me.vertices)}


def fair_neck(verts, ring):
    """S8b: NECK_FAIR on the welded neck. Returns the largest radial ripple (mm) before and after (each vertex's
    distance from its neighbourhood's average radius) and the largest move."""
    F = NECK_FAIR
    cx, cy = ring["centre"]
    ax, ay = ring["semi_axes"]
    z0, z1, z2, z3 = F["z"]
    sg, sz = math.radians(F["sigma_deg"]), F["sigma_z"]
    rn = lambda c: math.hypot((c.x - cx) / ax, (c.y - cy) / ay)  # noqa: E731
    band = [v for v in verts if z0 < v.co.z < z3 and math.hypot(v.co.x - cx, v.co.y - cy) < NECK_R
            and rn(v.co) < F["r_max"]]
    pts = [(math.atan2(v.co.x - cx, -(v.co.y - cy)), v.co.z, rn(v.co)) for v in band]

    def target(t, z):
        acc = wsum = 0.0
        for t2, z2_, r2 in pts:
            dt = (t2 - t + math.pi) % (2 * math.pi) - math.pi
            dz = z2_ - z
            if abs(dz) > 3 * sz or abs(dt) > 3 * sg:
                continue
            w = math.exp(-(dt / sg) ** 2 - (dz / sz) ** 2)
            acc += w * r2
            wsum += w
        return acc / wsum

    def ripple():
        return 1000 * max(abs(r - target(t, z)) for t, z, r in pts if z1 <= z <= z2) * (ax + ay) / 2  # the full zone

    before = ripple()
    goal = [target(t, z) for t, z, _ in pts]
    most = 0.0
    for v, (t, z, r), g in zip(band, pts, goal):
        w = _smoothstep(z0, z1, z) * (1.0 - _smoothstep(z2, z3, z))
        k = (r + w * (g - r)) / r if r > 1e-6 else 1.0
        old = v.co.copy()
        v.co.x = cx + (v.co.x - cx) * k
        v.co.y = cy + (v.co.y - cy) * k
        most = max(most, (v.co - old).length)
    pts = [(t, z, rn(v.co)) for v, (t, z, _) in zip(band, pts)]
    return {"verts": len(band), "ripple_before_mm": round(before, 2), "ripple_after_mm": round(ripple(), 2),
            "max_move_mm": round(most * 1000, 2), **F}


def _smoothstep(a, b, x):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def weld(body, head, ring):
    """Joins the head into the body, merges the coincident ring vertices, fairs the neck across the weld
    (fair_neck), clears custom normals, shades smooth."""
    ring_c = ring["centre"]
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
    # the neck: one smooth surface across the weld (no pleats, no crease at the loft's ends)
    fair = fair_neck(bm.verts, ring)
    neck_moved_mm = fair["max_move_mm"]
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
    return {"merged": merged, "open_edges_at_neck": open_neck, "neck_smooth_max_mm": round(neck_moved_mm, 2), "neck_fair": fair,
            "vertices": len(me.vertices),
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
                if piece == "ball":  # S5's rest aim, so Blender and three.js show what alien.gd sets (absolutely)
                    o.matrix_world = o.matrix_world @ Matrix.Rotation(math.radians(-EYE_AIM_IN if side == "L"
                                                                                  else EYE_AIM_IN), 4, "Z")
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
    rep["weld"] = weld(body, head, ring)
    # S9b: the neck as one column from the shoulders to under the jaw (alien_neck.py), its shape and its weights
    bm = bmesh.new()
    bm.from_mesh(body.data)
    before = alien_neck.profile(bm, ring)
    rep["neck_loft"] = alien_neck.loft(bm, ring)
    rep["neck_profile"] = {"before": before, "after": alien_neck.profile(bm, ring)}
    bm.to_mesh(body.data)
    bm.free()
    body.data.update()
    rep["neck_weights"] = alien_neck.column_weights(body, ring)
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
