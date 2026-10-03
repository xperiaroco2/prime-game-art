"""Head work: splitting a pack head by material regions (the bald skin head, a hairstyle, a moustache), cutting named
zones, flattening ears, straightening a collar ring, inflating hair off the skull and finding the eye centres.

Hair, brows, eyes, moustaches, beards, hats and earrings are material regions of the pack's head mesh. Men's eyes are
material "Eye"; women's eyes are "Brown" (on Formal and Medieval it also holds the brows); Punk "Red" includes a chin
goatee; King and men's Adventurer hair include beards; Casual Character "Skin_Darker" is stubble painted on the skin.
"""

import math

import bmesh
from mathutils import Vector

from . import zones
from .util import base_name


def filter_faces(obj, arm, keep):
    """keep(material_base_name, world_centre) -> bool; the rest of the faces are deleted."""
    me = obj.data
    names = [base_name(m.name) if m else "" for m in me.materials]
    mw = arm.matrix_world
    bm = bmesh.new(); bm.from_mesh(me)
    gone = [f for f in bm.faces if not keep(names[f.material_index], mw @ f.calc_center_median())]
    bmesh.ops.delete(bm, geom=gone, context="FACES")
    bm.to_mesh(me); bm.free()
    # drop now-unused material slots
    used = {p.material_index for p in me.polygons}
    for i in reversed(range(len(me.materials))):
        if i not in used:
            obj.active_material_index = i
            me.materials.pop(index=i)
    return len(me.polygons)


def inflate(obj, arm, s):
    """Scale hair-like parts about the skull centre by (1 + s) to keep them off coplanar skull faces."""
    if not s:
        return
    c = arm.matrix_world.inverted() @ Vector(zones.SKULL_CENTRE)
    for v in obj.data.vertices:
        v.co = c + (v.co - c) * (1.0 + s)
    obj.data.update()


def eye_centres(head, arm, eye_mats):
    """World centres {"L", "R"} of the source head's eye faces (before the head is stripped to skin)."""
    me = head.data
    idx = {i for i, m in enumerate(me.materials) if m and base_name(m.name) in eye_mats}
    pts = {"L": [], "R": []}
    for p in me.polygons:
        if p.material_index in idx:
            c = arm.matrix_world @ p.center
            if c.z < zones.EYE_Z_MAX:  # eyes only; brows sharing the material sit higher
                pts["L" if c.x > 0 else "R"].append(c)
    out = {}
    for k, v in pts.items():
        lo = Vector((min(p.x for p in v), min(p.y for p in v), min(p.z for p in v)))
        hi = Vector((max(p.x for p in v), max(p.y for p in v), max(p.z for p in v)))
        out[k] = (lo + hi) / 2
    return out


def tuck_ears(head, x_max):
    """Flatten the ears against the skull side at |x| = x_max (no holes, unlike cutting them out), so that a
    hairstyle made for smaller ears covers them. Returns how many vertices moved."""
    mw = head.matrix_world; inv = mw.inverted(); n = 0
    for v in head.data.vertices:
        p = mw @ v.co
        if abs(p.x) > x_max and zones.EAR_BOX(p):
            p.x = math.copysign(x_max, p.x); v.co = inv @ p; n += 1
    head.data.update()
    return n


def straighten_ring(head, ring_mats):
    """Turn a tapered collar ring at the bottom of a head (e.g. Sci Fi's "Black") into a straight continuation of
    the neck: each ring vertex takes the radius of the nearest-angle vertex of the lowest skin loop."""
    me = head.data; mw = head.matrix_world; inv = mw.inverted()
    names = [base_name(m.name) if m else "" for m in me.materials]
    ring = {i for p in me.polygons if names[p.material_index] in ring_mats for i in p.vertices}
    skin = [mw @ me.vertices[i].co for p in me.polygons if names[p.material_index] == "Skin" for i in p.vertices]
    zmin = min(p.z for p in skin)
    loop = [p for p in skin if p.z < zmin + 0.012]
    cx = sum(p.x for p in loop) / len(loop); cy = sum(p.y for p in loop) / len(loop)
    ang = lambda p: math.atan2(p.y - cy, p.x - cx)  # noqa: E731
    rad = lambda p: math.hypot(p.x - cx, p.y - cy)  # noqa: E731
    moved = 0.0
    for i in ring:
        p = mw @ me.vertices[i].co
        if p.z >= zmin + 0.004:
            continue
        a = ang(p)
        q = min(loop, key=lambda s: abs(math.remainder(ang(s) - a, 2 * math.pi)))
        r = rad(q) * 0.985
        np_ = Vector((cx + r * math.cos(a), cy + r * math.sin(a), p.z))
        moved = max(moved, (np_ - p).length)
        me.vertices[i].co = inv @ np_
    me.update()
    return round(moved * 1000, 1)
