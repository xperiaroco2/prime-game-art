"""Small helpers shared by the Blender-side modules."""

import bpy

from .glb import base_name  # noqa: F401  (re-exported: a name without its ".001" suffix)


def update():
    bpy.context.view_layer.update()


def tris(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def world_points(objs):
    """World positions of the evaluated (posed) vertices of objs."""
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in objs:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        pts += [ev.matrix_world @ v.co for v in me.vertices]
        ev.to_mesh_clear()
    return pts


def relink(obj, coll):
    """Move obj into coll only."""
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll.objects.link(obj)
