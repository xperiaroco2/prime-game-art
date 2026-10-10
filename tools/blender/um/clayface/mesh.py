"""Mesh helpers of the clay face kit: the build context on the head's surface (Ctx), bmesh parts, static pieces
(subdivide, cull inside the head, decimate, lumps), shape keys, the face materials and binding to the Head bone.

Ported from the faces lab (D:/prime-art-raw/research/2026-10-05-faces/lab/clay_e/clay_face_b.py; Part, P_on, lid_rotation and lid_part from
lab_face_r2.py; bake and bind from clay_d/clay_lib.py).
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

from .. import clay as cl
from .. import facekit as fk
from .kit import FIXED, GLOSS, HAIR_RGB, LAYOUT, TINT, brow_rgb, fhair_rgb, mul, skin_key, skin_rgb

X = Vector((1.0, 0.0, 0.0))
Y = Vector((0.0, 1.0, 0.0))
Z = Vector((0.0, 0.0, 1.0))
FWD = Vector((0.0, -1.0, 0.0))


def rad(d):
    return d * math.pi / 180.0


class Part(fk.Builder):
    """fk.Builder (bmesh with material slots) plus closed prisms and polygons (lab_face_r2.Part)."""

    def prism(self, stations, mat):
        """stations: [(top_back, bottom_back, top_front, bottom_front)] world points along a strip; a closed prism."""
        mi = self.slot(mat)
        bm = self.bm
        vs = [[bm.verts.new(p) for p in st] for st in stations]
        made = []

        def quad(a, b, c, d):
            f = bm.faces.new((a, b, c, d))
            f.material_index = mi
            made.append(f)

        for i in range(len(vs) - 1):
            tb, bb, tf, bf = vs[i]
            tb1, bb1, tf1, bf1 = vs[i + 1]
            quad(tf, bf, bf1, tf1)
            quad(tb, tf, tf1, tb1)
            quad(bf, bb, bb1, bf1)
            quad(bb, tb, tb1, bb1)
        tb, bb, tf, bf = vs[0]
        quad(tb, bb, bf, tf)
        tb, bb, tf, bf = vs[-1]
        quad(tf, bf, bb, tb)
        bmesh.ops.recalc_face_normals(bm, faces=made)
        return self

    def poly(self, verts, mat, away=None):
        f = self.bm.faces.new(verts)
        f.material_index = self.slot(mat)
        f.normal_update()
        if away is not None and f.normal.dot(away) < 0:
            f.normal_flip()
        return f


def P_on(surf, x, z, lift, blend=0.5):
    """The skin point at (x, z), lifted along a blend of its normal and the face's forward direction."""
    p, n = surf.hit(x, z)
    out = (n * blend + FWD * (1.0 - blend)).normalized()
    return p + out * lift


def lid_rotation(edge_deg, tilt_deg, side):
    s = 1.0 if side == "L" else -1.0
    return (rad(-edge_deg), rad(tilt_deg * s), 0.0)


def lid_part(c, r, scale, pole, skin_mat, edge_mat, EB):
    """A lid shell round the eye centre c: the band of a hemisphere (pole up or down) in front of the eye (azimuths
    from -X through -Y to +X, plus a margin behind), its last band and its rim in edge_mat."""
    rl = r * scale
    ri = r * 1.004
    line = EB["lid_line_rad"]
    m = EB["lid_back_margin"]
    th = (math.pi - m, 2 * math.pi + m)
    seg = EB["lid_seg"]
    ld = Part()
    ld.ellipsoid(c, X, Y, pole, rl, rl, rl, skin_mat, seg=seg, rings=EB["lid_rings"], theta=th, phi=(0.0, math.pi / 2 - line))
    ld.ellipsoid(c, X, Y, pole, rl, rl, rl, edge_mat, seg=seg, rings=1, theta=th, phi=(math.pi / 2 - line, math.pi / 2))
    bm = ld.bm

    def ring_pt(s, rad_):
        t = th[0] + (th[1] - th[0]) * s / seg
        return c + (X * math.cos(t) + Y * math.sin(t)) * rad_

    outer = [bm.verts.new(ring_pt(s, rl)) for s in range(seg + 1)]
    inner = [bm.verts.new(ring_pt(s, ri)) for s in range(seg + 1)]
    for s in range(seg):
        ld.poly((outer[s], outer[s + 1], inner[s + 1], inner[s]), edge_mat, away=-pole)
    return ld


def bake(o, keep=("ARMATURE",)):
    """Applies every modifier except `keep` (disabled while evaluating) on the rest mesh; vertex groups survive."""
    off = []
    for m in o.modifiers:
        if m.type in keep and m.show_viewport:
            m.show_viewport = False
            off.append(m)
    d = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(d), preserve_all_data_layers=True, depsgraph=d)
    for m in list(o.modifiers):
        if m.type not in keep:
            o.modifiers.remove(m)
    for m in off:
        m.show_viewport = True
    old = o.data
    o.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)
    cl.smooth_shade(o.data)
    return cl.tris(o.data)


def bind(o, arm, weights=None):
    """Parents o to the armature keeping its world placement, with an Armature modifier first in the stack; weights
    {bone: [w per vertex]}, else the Head bone alone at 1.0."""
    mw = o.matrix_world.copy()
    o.parent = arm
    o.matrix_parent_inverse = arm.matrix_world.inverted()
    o.matrix_world = mw
    if weights is None:
        weights = {"Head": [1.0] * len(o.data.vertices)}
    for bone, ws in weights.items():
        vg = o.vertex_groups.get(bone) or o.vertex_groups.new(name=bone)
        for i, w in enumerate(ws):
            if w > 1e-4:
                vg.add([i], float(w), "REPLACE")
    if not any(m.type == "ARMATURE" for m in o.modifiers):
        m = o.modifiers.new("arm", "ARMATURE")
        m.object = arm
        o.modifiers.move(len(o.modifiers) - 1, 0)
    return o



def set_rgb(mat, rgb):
    nt = mat.node_tree
    n = nt.nodes.get("clay_rgb") if nt else None
    if n is not None:
        n.outputs[0].default_value = (*rgb, 1.0)
    elif nt and nt.nodes.get("Principled BSDF"):
        nt.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*rgb, 1.0)
    mat.diffuse_color = (*rgb, 1.0)


class Ctx:
    """What a face is built against: the head's surface (rest pose, facing -Y) and the layout points."""

    def __init__(self, h):
        self.h = h
        self.x = h.x
        self.eye_z = h.eye_z()
        self.ez = self.eye_z + LAYOUT["eye_dz"]
        self.mx, self.mz = h.x, self.ez - LAYOUT["eye_mouth"]
        self.surf = fk.Surface(h.parts["head"])
        self.bvh = self.surf.bvh
        far = Vector((h.x, -1.0, self.ez))
        loc, nrm, _, _ = self.bvh.find_nearest(far)
        self.sign = 1.0 if (far - loc).dot(nrm) > 0 else -1.0

    def on(self, x, z, lift, blend=0.5):
        """A point on the skin at (x, z), lifted; past the head's edge it steps toward the centre line until it hits
        (counted in self.pulled_in)."""
        for _ in range(16):
            try:
                return P_on(self.surf, x, z, lift, blend)
            except RuntimeError:
                x = self.x + (x - self.x) * 0.93
                self.pulled_in = getattr(self, "pulled_in", 0) + 1
        return P_on(self.surf, x, z, lift, blend)

    def depth_inside(self, p):
        """How far p is inside the head skin (positive inside), by the nearest point and its normal."""
        loc, nrm, _, _ = self.bvh.find_nearest(p)
        if loc is None:
            return -1.0
        return -(p - loc).dot(nrm) * self.sign


def bm_object(name, bm, mats, coll):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    cl.smooth_shade(me)
    return o


def data_object(name, verts, faces, fmats, mats, coll):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.update()
    for m in mats:
        me.materials.append(m)
    mi = np.array(fmats, dtype=np.int32)
    me.polygons.foreach_set("material_index", mi)
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    cl.smooth_shade(me)
    return o


def add_keys(o, states, basis):
    """Shape keys from {key: [Vector or tuple] per vertex} (same order as the mesh's vertices); basis is the mesh."""
    o.shape_key_add(name="Basis", from_mix=False)
    n = len(o.data.vertices)
    for k, vs in states.items():
        if k == basis:
            continue
        assert len(vs) == n, (o.name, k, len(vs), n)
        kb = o.shape_key_add(name=k, from_mix=False)
        kb.data.foreach_set("co", np.array([tuple(v) for v in vs], dtype=np.float32).ravel())
        kb.value = 0.0
    o.data.update()


def cull_inside(o, ctx, margin=0.0015, keep_side=None):
    """Deletes the faces whose every vertex is more than margin inside the head (they never show)."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    mw = o.matrix_world
    deep = {v.index: ctx.depth_inside(mw @ v.co) > margin for v in bm.verts}
    dead = [f for f in bm.faces if all(deep[v.index] for v in f.verts)]
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()
    return len(dead)


def decimate_to(o, target):
    t = cl.tris(o.data)
    if t > target:
        d = o.modifiers.new("dec", "DECIMATE")
        d.ratio = target / t
        bake(o, keep=())
    return cl.tris(o.data)


def static_piece(ctx, name, bm, mats, coll, sub=1, target=None, lumps=None, cull=True):
    """A rigid piece: subdivided (baked), lumps, the parts inside the head culled, decimated to target."""
    o = bm_object(name, bm, mats, coll)
    if lumps:
        cl.lump(o, *lumps)
    if sub:
        s = o.modifiers.new("round", "SUBSURF")
        s.levels = s.render_levels = sub
        bake(o, keep=())
    culled = cull_inside(o, ctx) if cull else 0
    if target:
        decimate_to(o, target)
    cl.smooth_shade(o.data)
    return o, culled


def blob_bm(c, half, seg=14, rings=8, rot=None, capsule=0.0, dent=None, outer=1.0):
    """An ellipsoid blob. Fixer 2: dent = (depth m, radius as a share of the half sizes, centre z as a share of half z):
    a thumb dent pressed into the outer face (+x times outer), depth x (1 - r^2)^2 (a smooth bowl, 0 at its rim)."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0)
    for v in bm.verts:
        q = Vector((v.co.x * half[0], v.co.y * half[1], v.co.z * half[2]))
        if dent and v.co.x * outer > 0.0:
            r2 = (v.co.y / dent[1]) ** 2 + ((v.co.z - dent[2]) / dent[1]) ** 2
            if r2 < 1.0:
                q.x -= outer * dent[0] * (1.0 - r2) ** 2
        if capsule and abs(v.co.y) > 1e-6:
            q.y += math.copysign(capsule, v.co.y)
        if rot is not None:
            q = rot @ q
        v.co = c + q
    return bm


def materials(h, skin, hair_rgb=None, brow_colour=None):
    """Per character: the head's skin material (lids, ears), nose, lip, crease, brow, facial hair; shared: white,
    pupil, cavity, teeth (glossy except the cavity). brow_colour: the brow's own colour (round D), None = BROW_RGB."""
    h.fb_brow_colour = tuple(brow_colour) if brow_colour is not None else None
    if hair_rgb:
        h.fb_hair_rgb = tuple(hair_rgb)
    elif not hasattr(h, "fb_hair_rgb"):
        h.fb_hair_rgb = hair_colour(h)
    if getattr(h, "fb_mats", None):
        return h.fb_mats
    m = {"skin": h.skin}
    for k in ("nose", "lip", "crease", "brow", "fhair"):
        m[k] = bpy.data.materials.get(f"{h.id}_fb_{k}") or bpy.data.materials.new(f"{h.id}_fb_{k}")
        cl.clay(m[k], (0.5, 0.5, 0.5))
    for k, rgb in FIXED.items():
        mat = bpy.data.materials.get("fb_" + k)
        if mat is None:
            mat = bpy.data.materials.new("fb_" + k)
            if k == "cavity":
                cl.gloss(mat, rgb, rough=0.85, spec=0.2)
            else:
                cl.gloss(mat, rgb, rough=GLOSS[k], spec=0.5)
        m[k] = mat
    h.fb_mats = m
    apply_skin(h, m, skin)
    return m


def hair_colour(h):
    hp = h.parts.get("hair")
    if hp is not None:
        for s in hp.material_slots:
            if s.material and not s.material.name.endswith("_skin"):
                return tuple(s.material.diffuse_color[:3])
    return HAIR_RGB


def apply_skin(h, m, skin):
    rgb = skin_rgb(skin)
    key = skin_key(skin)
    set_rgb(m["skin"], rgb)
    set_rgb(m["nose"], mul(rgb, TINT["nose"][key]))
    set_rgb(m["lip"], mul(rgb, TINT["lip"][key]))
    set_rgb(m["crease"], mul(rgb, TINT["crease"][key]))
    set_rgb(m["brow"], brow_rgb(key, brow=getattr(h, "fb_brow_colour", None)))
    set_rgb(m["fhair"], fhair_rgb(getattr(h, "fb_hair_rgb", HAIR_RGB)))


def drop_piece(face, name):
    o = face.pieces.pop(name)
    face.cat.pop(name, None)
    me = o.data
    bpy.data.objects.remove(o, do_unlink=True)
    if me.users == 0:
        bpy.data.meshes.remove(me)


def piece_coords(o, key=None):
    me = o.data
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32)
    if key is None or me.shape_keys is None or key not in me.shape_keys.key_blocks:
        me.vertices.foreach_get("co", co)
    else:
        me.shape_keys.key_blocks[key].data.foreach_get("co", co)
    M = np.array(o.matrix_world, dtype=np.float64)
    w = co.reshape(-1, 3).astype(np.float64) @ M[:3, :3].T + M[:3, 3]
    return [Vector(p) for p in w]
