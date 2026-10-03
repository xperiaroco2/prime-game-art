"""The rest-pose rebind: parts authored on another file's rest pose re-expressed in the target rig's rest pose.

The packs' rest poses differ: the men's Adventurer is bound 180 degrees off (its parts land at z -3.8 m if parented
raw) and Hoodie Character's rest is 6 to 7 mm lower. rebind() moves Adventurer_Body by 5.6 m and is exact (0) when the
rests already match.
"""

from mathutils import Vector


def rebind(obj, src_arm, dst_arm):
    """Re-express a skinned mesh, authored on src_arm's rest pose, in dst_arm's rest pose (linear blend skinning
    with the target rest as the pose). Identity when both rests match. Returns the largest move in metres."""
    if src_arm.data == dst_arm.data:
        return 0.0
    mats = {}
    for vg in obj.vertex_groups:
        if vg.name in src_arm.data.bones and vg.name in dst_arm.data.bones:
            mats[vg.index] = dst_arm.data.bones[vg.name].matrix_local @ src_arm.data.bones[vg.name].matrix_local.inverted()
    moved = 0.0
    for v in obj.data.vertices:
        acc, ws = Vector((0, 0, 0)), 0.0
        for g in v.groups:
            m = mats.get(g.group)
            if m is not None and g.weight > 1e-5:
                acc += (m @ v.co) * g.weight
                ws += g.weight
        if ws > 0:
            nv = acc / ws
            moved = max(moved, (nv - v.co).length)
            v.co = nv
    obj.data.update()
    return moved * dst_arm.matrix_world.to_scale().x
