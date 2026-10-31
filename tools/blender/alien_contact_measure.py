"""The alien clips' contact measure (art #196, B1-B1d), in Blender: per clip of a dressed (or bare) character blend,
per frame the Hips' world z and the lowest point (mm) of each skinned mesh that renders (the body, the shoes, the
garments); alien_contact.py turns the JSONs into the contact table.
Usage: blender -b --python alien_contact_measure.py -- <blend> <out.json> (through tools/runner/blender.py)"""
import bpy, sys, json
import numpy as np
argv = sys.argv[sys.argv.index("--") + 1:]
blend, out = argv[0], argv[1]
bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene
arm = next(o for o in sc.objects if o.type == "ARMATURE")
meshes = [o for o in sc.objects if o.type == "MESH" and not o.hide_render and any(m.type == "ARMATURE" for m in o.modifiers)]
res = {"blend": blend, "fps": sc.render.fps, "meshes": [o.name for o in meshes], "clips": {}}
for act in [a for a in bpy.data.actions if a.name.startswith("CharacterArmature|")]:
    clip = act.name.split("|", 1)[1]
    arm.animation_data.action = act
    if act.slots:
        arm.animation_data.action_slot = act.slots[0]
    f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
    rows = []
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        r = {"f": f, "hips": round((arm.matrix_world @ arm.pose.bones["Hips"].head).z * 1000, 2)}
        for o in meshes:
            ev = o.evaluated_get(dg); me = ev.to_mesh()
            co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", co)
            z = (co.reshape(-1, 3) @ np.array(ev.matrix_world.to_3x3()).T)[:, 2] + ev.matrix_world.translation.z
            r[o.name] = round(float(z.min()) * 1000, 2) if len(z) else None
            ev.to_mesh_clear()
        rows.append(r)
    res["clips"][clip] = rows
json.dump(res, open(out, "w"), indent=0)
print("MEASURE wrote", out, len(res["clips"]))
