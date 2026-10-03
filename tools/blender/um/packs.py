"""Loading pack GLBs cleanly: the stray Icosphere and the importer's helper empties are left out of a part's meshes,
the file's own action set is remembered, every pose bone is reset; placing and turning a character through its root.

What the importer gives (Blender 5.2.2, glTF importer): an empty "RootNode", the armature "CharacterArmature" at a
world scale of 100 with a -90 degree X rotation, its four meshes (<Name>_Head, _Body, _Legs or _Pants, _Feet) parented
to it at the same transform, 17 "<bone>_end" empties, 24 actions "CharacterArmature|<name>" (suffixed ".001", ".002",
... from the second import of a run on) on 24 NLA tracks, and the stray Icosphere. The importer leaves the rig in its
first action (Death), so every pose bone is reset to identity after loading.
"""

import math
import re

import bpy
from mathutils import Matrix

from .util import base_name, update


class Packs:
    """The two pack folders of a recipe: load(gender, file) imports one GLB."""

    def __init__(self, folders):
        self.folders = folders  # {"M": Path, "W": Path}

    def path(self, gender, fname):
        return str(self.folders[gender] / fname)

    def load(self, gender, fname):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=self.path(gender, fname))
        new = [o for o in bpy.data.objects if o not in before]
        arm = next(o for o in new if o.type == "ARMATURE")
        # the importer assigns this file's own first action; its name suffix (".012") names the file's action set
        act = arm.animation_data.action if arm.animation_data else None
        arm["action_suffix"] = re.search(r"(\.\d{3})?$", act.name).group(0) if act else ""
        reset_pose(arm)
        meshes = {base_name(o.name): o for o in new if o.type == "MESH" and not o.name.startswith("Icosphere")}
        return {"gender": gender, "file": fname, "arm": arm, "root": arm.parent, "objs": new, "meshes": meshes}


def source_label(gender, fname):
    return ("Men" if gender == "M" else "Women") + "/" + fname


def reset_pose(arm):
    if arm.animation_data:
        arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.scale = (1, 1, 1)


def own_actions(arm):
    """The 24 actions of the file this armature was imported from (its action set's suffix)."""
    suffix = arm["action_suffix"]
    pattern = re.compile(r"^CharacterArmature\|[^.]+" + re.escape(suffix) + "$")
    return [a for a in bpy.data.actions if pattern.match(a.name)]


def own_action(arm, name):
    return bpy.data.actions["CharacterArmature|" + name + arm["action_suffix"]]


ROOT0 = {}


def place(root, x=0.0, z=0.0, yaw=0.0):
    """Move a character's root empty by x, z and a yaw in degrees, from where the importer put it."""
    if root.name not in ROOT0:
        ROOT0[root.name] = root.matrix_world.copy()
    root.matrix_world = Matrix.Translation((x, 0.0, z)) @ Matrix.Rotation(math.radians(yaw), 4, "Z") @ ROOT0[root.name]
    update()


def discard(src, keep=()):
    """Delete every object a load() brought in except keep."""
    keep = set(keep)
    for o in src["objs"]:
        try:
            o.name
        except ReferenceError:
            continue
        if o not in keep:
            bpy.data.objects.remove(o, do_unlink=True)


def attach(obj, arm):
    obj.parent = arm
    for m in obj.modifiers:
        if m.type == "ARMATURE":
            m.object = arm
