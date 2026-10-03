"""One clean .blend per character, the input of the glTF export (art #18), its JSON sidecar, and the inspection of a
saved file.

The saved file holds one scene named after the character with exactly: the armature <id>_rig (62 bones) and one mesh
object per part, <id>_<slot>, each parented to the armature with an Armature modifier on it; the body type's 24 own
actions under their original names ("CharacterArmature|Wave", ...), kept by a fake user, none assigned, no NLA
tracks; every pose bone at identity (the rest pose). No RootNode, no "_end" empties, no Icosphere, camera, light or
world. Materials are flat colours: the Principled base colour equals the viewport colour.

Transforms are applied (docs/assembly.md): the importer's armature carries a -90 degree X rotation and a world scale
of 100. Saving bakes the armature's world matrix into the bones and every part's world matrix into its mesh, so every
object has the identity transform, 1 Blender unit = 1 m, +Z up, the feet at z = 0; the actions' pose-bone location
keys are multiplied by the same scale (100), because a bone's local translation is measured in armature units. The
save checks this: bone positions and deformed vertices at sample frames before and after must agree.
"""

import json
import os

import bpy
from mathutils import Matrix

from . import materials
from .packs import own_action, own_actions, place, reset_pose
from .util import base_name, tris, update, world_points

FACE_ROLES = ("eyes", "brows", "mouth")
# Sample poses for the transform check: an idle, a stride and a fall (large root motion).
CHECK_POSES = (("Idle", 10), ("Walk", 6), ("Death", 20))
CHECK_TOLERANCE_M = 1e-4


def fcurves(action):
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                yield from bag.fcurves


def _sample(arm, parts, action, frame):
    """World bone heads and tails and deformed vertices with action at frame; the rig is reset afterwards."""
    ad = arm.animation_data or arm.animation_data_create()
    ad.action = action
    ad.action_slot = action.slots[0]
    bpy.context.scene.frame_set(frame)
    update()
    mw = arm.matrix_world
    pts = [mw @ pb.head for pb in arm.pose.bones] + [mw @ pb.tail for pb in arm.pose.bones]
    pts += world_points(parts.values())
    ad.action = None
    reset_pose(arm)
    update()
    return pts


def _rename_actions(acts):
    """Give the character's own actions their original names, moving any other action off those names first."""
    for act in acts:
        target = base_name(act.name)
        other = bpy.data.actions.get(target)
        if other is not None and other is not act:
            other.name = target + "~other"
        act.name = target
        if act.name != target:
            raise RuntimeError(f"could not rename action {act.name} to {target}")
        act.use_fake_user = True


def _rename_materials(parts):
    """Drop the importer's ".001" suffixes from the character's material names where its own names do not collide;
    another character's material holding a name is moved off it (that file is already written)."""
    ours = {}
    for o in parts.values():
        for s in o.material_slots:
            ours[s.material.name] = s.material
    wanted = {}
    for m in ours.values():
        wanted.setdefault(base_name(m.name), []).append(m)
    for target, mats in wanted.items():
        if len(mats) != 1 or mats[0].name == target:
            continue
        other = bpy.data.materials.get(target)
        if other is not None:
            other.name = target + "~other"
        mats[0].name = target


def save_character(cid, arm, parts, rc, rep, out_dir):
    """Writes <out_dir>/<cid>.blend and <cid>.json; returns the sidecar. Changes the character in place: call it last."""
    root = arm.parent
    place(root)  # back where the importer put it: at the origin, facing -Y
    if arm.animation_data:
        for track in list(arm.animation_data.nla_tracks):
            arm.animation_data.nla_tracks.remove(track)
        arm.animation_data.action = None
    reset_pose(arm)
    arm.data.pose_position = "POSE"
    update()
    acts = own_actions(arm)
    if len(acts) != 24:
        raise RuntimeError(f"{cid}: {len(acts)} own actions, not 24")
    checks = [(own_action(arm, a), f) for a, f in CHECK_POSES]
    before = [_sample(arm, parts, a, f) for a, f in checks]

    # bake the transforms: meshes first (their world matrices hang off the armature's), then the bones
    scale = arm.matrix_world.to_scale()
    if max(scale) - min(scale) > 1e-4:
        raise RuntimeError(f"{cid}: the armature's scale {tuple(scale)} is not uniform")
    for o in parts.values():
        o.data.transform(o.matrix_world)
        o.data.update()
    m = arm.matrix_world.copy()
    arm.parent = None
    arm.data.transform(m)
    arm.matrix_basis = Matrix.Identity(4)
    for o in parts.values():
        o.matrix_parent_inverse = Matrix.Identity(4)
        o.matrix_basis = Matrix.Identity(4)
    for act in acts:
        for fc in fcurves(act):
            if fc.data_path.endswith(".location"):
                for k in fc.keyframe_points:
                    k.co.y *= scale.x
                    k.handle_left.y *= scale.x
                    k.handle_right.y *= scale.x
                fc.update()
    update()
    after = [_sample(arm, parts, a, f) for a, f in checks]
    error = max((p - q).length for b, a in zip(before, after) for p, q in zip(b, a))
    if error > CHECK_TOLERANCE_M:
        raise RuntimeError(f"{cid}: applying the transforms moved the posed character by {error * 1000:.3f} mm")

    bpy.data.objects.remove(root, do_unlink=True)
    for key in ("seam_edges", "tucked", "action_suffix"):
        if key in arm:
            del arm[key]
    synced = 0.0
    for role, o in parts.items():
        for slot in o.material_slots:
            skin = base_name(slot.material.name).endswith("_skin")
            synced = max(synced, materials.sync_principled(slot.material, scripted=role in FACE_ROLES and not skin))
    _rename_actions(acts)
    _rename_materials(parts)

    scene = bpy.data.scenes.new(cid)
    scene.render.fps = bpy.context.scene.render.fps
    coll = bpy.data.collections.new(cid)
    scene.collection.children.link(coll)
    for o in [arm] + list(parts.values()):
        coll.objects.link(o)
    update()

    pts = world_points(parts.values())
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    sidecar = {
        "id": cid,
        "body_type": rc["gender"],
        "blend": cid + ".blend",
        "units": "metres; Blender +Z up, front -Y (glTF +Y up, front +Z after the exporter's default conversion)",
        "fps": scene.render.fps,
        "armature": {"object": arm.name, "bones": len(arm.data.bones), "source": rep["skeleton"]},
        "transforms": "identity on every object (applied when saved)",
        "transform_check_max_error_m": round(error, 7),
        "principled_synced_max_change": round(synced, 4),
        "bounds_m": {"min": [round(v, 4) for v in lo], "max": [round(v, 4) for v in hi]},
        "height_m": round(hi[2] - lo[2], 3),
        "feet_z_m": round(lo[2], 4),
        "parts": {},
        "triangles_total": 0,
        "actions": {a.name: {"frame_start": int(a.frame_range[0]), "frame_end": int(a.frame_range[1])} for a in sorted(acts, key=lambda a: a.name)},
    }
    for role, o in parts.items():
        src = rep["parts"].get(role, {})
        sidecar["parts"][role] = {
            "object": o.name,
            "triangles": tris(o),
            "vertices": len(o.data.vertices),
            "vertex_groups": len(o.vertex_groups),
            "source": (src.get("file", "") + " " + src.get("object", "")).strip() if not src.get("scripted") else "scripted face kit: " + src["style"],
            "materials": [{"name": s.material.name, "rgb": [round(c, 4) for c in s.material.diffuse_color[:3]]} for s in o.material_slots],
        }
    sidecar["triangles_total"] = sum(p["triangles"] for p in sidecar["parts"].values())
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, cid + ".blend")
    bpy.data.libraries.write(path, {scene, *acts}, path_remap="NONE", fake_user=True, compress=True)
    with open(os.path.join(out_dir, cid + ".json"), "w", encoding="utf-8") as fh:
        json.dump(sidecar, fh, indent=1)
    print("SAVED", path)
    return sidecar


def _identity(mat):
    return all(abs(mat[i][j] - (1.0 if i == j else 0.0)) < 1e-6 for i in range(4) for j in range(4))


def inspect(path):
    """Opens a saved character .blend (replacing the session) and describes it; problems lists what breaks the rules
    of a saved character (see the module docstring)."""
    bpy.ops.wm.open_mainfile(filepath=path)
    objs = list(bpy.data.objects)
    arms = [o for o in objs if o.type == "ARMATURE"]
    out = {"file": os.path.basename(path), "scenes": [s.name for s in bpy.data.scenes], "objects": {}, "actions": {},
           "cameras": len(bpy.data.cameras), "lights": len(bpy.data.lights), "worlds": len(bpy.data.worlds),
           "images": len(bpy.data.images), "problems": []}
    bad = out["problems"].append
    if len(arms) != 1:
        bad(f"{len(arms)} armatures, not 1")
    arm = arms[0] if arms else None
    for o in objs:
        info = {"type": o.type, "parent": o.parent.name if o.parent else None, "identity": _identity(o.matrix_world)}
        if o.type == "MESH":
            mods = [(m.type, m.object.name if getattr(m, "object", None) else None) for m in o.modifiers]
            info.update({"triangles": tris(o), "vertex_groups": len(o.vertex_groups), "modifiers": mods,
                         "materials": [s.material.name if s.material else None for s in o.material_slots]})
            if arm is None or o.parent is not arm or mods != [("ARMATURE", arm.name)]:
                bad(f"{o.name}: not parented to the armature with one Armature modifier on it")
            for s in o.material_slots:
                if s.material is None:
                    bad(f"{o.name}: an empty material slot")
                    continue
                bsdf = next((n for n in s.material.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None) if s.material.node_tree else None
                if bsdf is None or max(abs(a - b) for a, b in zip(bsdf.inputs["Base Color"].default_value[:3], s.material.diffuse_color[:3])) > 1e-4:
                    bad(f"{o.name}: material {s.material.name}'s Principled base colour is not its viewport colour")
        elif o.type == "ARMATURE":
            info["bones"] = len(o.data.bones)
            ad = o.animation_data
            info["action"] = ad.action.name if ad and ad.action else None
            info["nla_tracks"] = len(ad.nla_tracks) if ad else 0
            moved = [pb.name for pb in o.pose.bones if pb.location.length > 1e-6 or abs(pb.rotation_quaternion.w - 1) > 1e-6 or (pb.scale - pb.scale.__class__((1, 1, 1))).length > 1e-6]
            info["posed_bones"] = len(moved)
            if info["action"] or info["nla_tracks"] or moved:
                bad(f"{o.name}: not in the rest pose with no action (action {info['action']}, {info['nla_tracks']} NLA tracks, {len(moved)} posed bones)")
        else:
            bad(f"{o.name}: a {o.type} object (only the armature and the parts belong here)")
        if not info["identity"]:
            bad(f"{o.name}: its transform is not the identity")
        out["objects"][o.name] = info
    for a in bpy.data.actions:
        out["actions"][a.name] = {"frame_range": [int(a.frame_range[0]), int(a.frame_range[1])], "fake_user": a.use_fake_user}
        if not a.name.startswith("CharacterArmature|") or base_name(a.name) != a.name:
            bad(f"action {a.name}: not an original pack action name")
    if len(out["actions"]) != 24:
        bad(f"{len(out['actions'])} actions, not 24")
    for kind in ("cameras", "lights", "worlds"):
        if out[kind]:
            bad(f"{out[kind]} {kind}")
    if arm is not None:
        dg = bpy.context.evaluated_depsgraph_get()
        zs = []
        for o in objs:
            if o.type == "MESH":
                ev = o.evaluated_get(dg); me = ev.to_mesh()
                zs += [(ev.matrix_world @ v.co).z for v in me.vertices]
                ev.to_mesh_clear()
        out["feet_z_m"] = round(min(zs), 4)
        out["height_m"] = round(max(zs) - min(zs), 3)
    return out
