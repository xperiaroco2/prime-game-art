"""The hands' corrective shapes (art #196, round H1): per grip and hand a shape key that gives a curled finger back the
volume plain linear skinning takes from its knuckles. Runs inside Blender (bpy).

How (settled on the h1 grid, `docs/animations.md`): the hand is posed in its grip with the arm at rest (only the
finger bones turn, so the key holds in any arm pose), the mesh is evaluated twice, with plain linear skinning (what
glTF and Godot do) and with the method (dual quaternion skinning and/or a corrective smooth limited to the fingers),
and the difference is taken back to rest space through each vertex's own blended skinning matrix. Linear skinning
of the rest mesh plus the key at weight 1 then lands on the method's posed mesh.
"""
from __future__ import annotations

import alien_pose_math as A

METHODS = ("lbs", "dqs", "cs", "dqs_cs")
FINGER_GROUP = "h1_fingers"


def hand_meshes(arm) -> list:
    import bpy
    return [o for o in bpy.data.objects if o.type == "MESH" and o.parent == arm
            and any(g.name.startswith(("LeftIndex", "RightIndex")) for g in o.vertex_groups)]


def _finger_mask(o, side: str = "") -> list:
    """Per vertex its weight on the finger bones (both hands, or one side)."""
    idx = {g.index for g in o.vertex_groups
           if any(g.name.startswith(f"{s}{f}") for s in ((side,) if side else ("Left", "Right")) for f in A.FINGERS)}
    out = []
    for v in o.data.vertices:
        out.append(sum(g.weight for g in v.groups if g.group in idx))
    return out


def set_method(arm, method: str, cs: tuple = (0.5, 5)) -> None:
    """The meshes' deform: `lbs` plain, `dqs` preserve volume, `cs` a corrective smooth on the fingers (factor,
    iterations), `dqs_cs` both."""
    for o in hand_meshes(arm):
        for m in o.modifiers:
            if m.type == "ARMATURE":
                m.use_deform_preserve_volume = method in ("dqs", "dqs_cs")
        m = o.modifiers.get("h1_cs")
        if method in ("cs", "dqs_cs"):
            if FINGER_GROUP not in o.vertex_groups:
                g = o.vertex_groups.new(name=FINGER_GROUP)
                for i, w in enumerate(_finger_mask(o)):
                    if w > 0.0:
                        g.add([i], min(1.0, w * 2.0), "REPLACE")
            if m is None:
                m = o.modifiers.new("h1_cs", "CORRECTIVE_SMOOTH")
            m.factor, m.iterations = cs
            m.rest_source, m.smooth_type, m.vertex_group = "ORCO", "LENGTH_WEIGHTED", FINGER_GROUP
            m.use_only_smooth = False
        elif m is not None:
            o.modifiers.remove(m)


def _coords(o, normals: bool = False):
    import bpy
    import numpy as np
    ev = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    if normals:
        no = np.empty(len(me.vertices) * 3, dtype=np.float64)
        me.vertices.foreach_get("normal", no)
    ev.to_mesh_clear()
    return (co.reshape(-1, 3), no.reshape(-1, 3)) if normals else co.reshape(-1, 3)


def knuckle_factor(o, side: str) -> list:
    """Per vertex 4 w1 w2 of its two largest weights where one is a finger bone of `side`: 1 on a knuckle's
    middle (half its finger bone, half the next), 0 on a phalanx's middle and off the fingers."""
    gname = {g.index: g.name for g in o.vertex_groups}
    fing = tuple(f"{side}{f}" for f in A.FINGERS)
    out = []
    for v in o.data.vertices:
        ws = sorted(((g.weight, gname.get(g.group, "")) for g in v.groups if g.weight > 0.0), reverse=True)[:2]
        t = sum(w for w, _ in ws) or 1.0
        out.append(4.0 * ws[0][0] * ws[1][0] / t / t if len(ws) == 2 and any(b.startswith(fing) for _, b in ws) else 0.0)
    return out


def bake(arm, model: A.Model, rig_apply, side: str, grip: str, method: str, name: str = "",
         cs: tuple = (0.5, 5), fat_cm: float = 0.0) -> dict:
    """Adds (or replaces) the shape key `name` (default `h1_<grip>_<side>`) on every hand mesh; returns per mesh the
    vertices moved, the largest move (cm) and the check's error (cm: linear skinning plus the key against the
    method's mesh). `rig_apply(rig)` poses the armature (alien_poses._apply)."""
    import bpy
    import numpy as np
    from mathutils import Matrix
    name = name or f"h1_{grip}_{side}"
    r = A.Rig(model.skel)
    model._fingers(r, side, grip)
    rig_apply(r)
    meshes = hand_meshes(arm)
    for o in meshes:  # a key of this name from before off, so the evaluations below do not include it
        k = o.data.shape_keys.key_blocks.get(name) if o.data.shape_keys else None
        if k is not None:
            o.shape_key_remove(k)
    set_method(arm, "lbs")
    lin = {o.name: _coords(o) for o in meshes}
    set_method(arm, method, cs)
    goal = {}
    for o in meshes:
        co, no = _coords(o, normals=True)
        if fat_cm:  # the knuckles' lost volume pushed back out along the posed normals
            co = co + no * (np.array(knuckle_factor(o, side))[:, None] * fat_cm / 100.0)
        goal[o.name] = co
    set_method(arm, "lbs")
    # per bone the skinning matrix in armature space
    B = {pb.name: np.array(pb.matrix @ pb.bone.matrix_local.inverted()) for pb in arm.pose.bones}
    out = {}
    for o in meshes:
        mask = _finger_mask(o, side)
        to_arm = np.array(arm.matrix_world.inverted() @ o.matrix_world)
        to_obj = np.linalg.inv(to_arm)
        gname = {g.index: g.name for g in o.vertex_groups}
        d = goal[o.name] - lin[o.name]
        delta = np.zeros_like(d)
        for i, v in enumerate(o.data.vertices):
            if mask[i] <= 0.0 or not np.any(np.abs(d[i]) > 1e-7):
                continue
            ws = [(g.weight, gname[g.group]) for g in v.groups if gname.get(g.group) in B and g.weight > 0.0]
            t = sum(w for w, _ in ws)
            S = sum((w / t) * B[b] for w, b in ws)
            M3 = (to_obj @ S @ to_arm)[:3, :3]
            delta[i] = np.linalg.solve(M3, d[i])
        if o.data.shape_keys is None:
            o.shape_key_add(name="Basis", from_mix=False)
        k = o.shape_key_add(name=name, from_mix=False)
        base = np.empty(len(o.data.vertices) * 3, dtype=np.float64)
        o.data.shape_keys.key_blocks["Basis"].data.foreach_get("co", base)
        k.data.foreach_set("co", (base.reshape(-1, 3) + delta).ravel())
        k.value = 1.0
        bpy.context.view_layer.update()
        err = float(np.abs(_coords(o) - goal[o.name]).max()) * 100.0
        k.value = 0.0
        moved = int(np.count_nonzero(np.linalg.norm(delta, axis=1) > 1e-6))
        out[o.name] = {"key": name, "moved": moved, "max_cm": round(float(np.linalg.norm(d, axis=1).max()) * 100, 3),
                       "check_cm": round(err, 4)}
    return out


def clear(arm, prefix: str = "h1_") -> None:
    for o in hand_meshes(arm):
        if o.data.shape_keys:
            for k in [k for k in o.data.shape_keys.key_blocks if k.name.startswith(prefix)]:
                o.shape_key_remove(k)


def set_weights(arm, weights: dict) -> None:
    """Shape key values by name (missing keys: 0)."""
    for o in hand_meshes(arm):
        if o.data.shape_keys:
            for k in o.data.shape_keys.key_blocks:
                if k.name.startswith("h1_"):
                    k.value = float(weights.get(k.name, 0.0))


def key_clip(arm, act, weights: dict, frames: int) -> int:
    """The pose clip `act` also keys every `h1_` shape key of the hand meshes (the clip's grips at `weights`, the rest
    0) on frames 0..frames, in a slot of the same action, so the glTF animation carries them as morph-target weights
    beside the bones. Returns the number of keys keyed."""
    n = 0
    for o in hand_meshes(arm):
        key = o.data.shape_keys
        if key is None:
            continue
        ad = key.animation_data or key.animation_data_create()
        ad.action = act
        if getattr(ad, "action_slot", None) is None and hasattr(ad, "action_suitable_slots"):
            ad.action_slot = ad.action_suitable_slots[0] if ad.action_suitable_slots else act.slots.new(
                id_type="KEY", name=key.name)
        for kb in key.key_blocks:
            if not kb.name.startswith("h1_"):
                continue
            for f in range(frames + 1):
                kb.value = float(weights.get(kb.name, 0.0))
                kb.keyframe_insert("value", frame=f)
            n += 1
            kb.value = 0.0
        ad.action = None
    return n


def grip_weights(grips: dict, keyed) -> dict:
    """A clip's shape weights from its hands' grips ({side: grip}): 1 for each keyed grip's key."""
    return {f"h1_{g}_{s}": 1.0 for s, g in grips.items() if g in keyed}
