"""Geometry helpers for the alien parts kit (art #196, step S2a): swept tubes, lid shells, the eyeball, the fin, the
mask UV layer. Everything is built in world space (Blender: Z up, front -Y) with bmesh and turned into objects by
`to_object`; `alien_parts.py` places and exports them.

The masks live in a second UV layer named `masks`: u = the light mask (face, throat, belly), v = the accent mask
(reddish knees, elbows, knuckles, lid rims, tips). The hue shader reads it (TEXCOORD_1 in glTF, UV2 in Godot).
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

MASKS = "masks"


NECK_RING_COUNT = 48  # S8b: the weld ring's vertices (S1's file has 24; the body's subdivided neck end has 48)
RIB_START = 0.02  # a fin rib's first ring, as a share of its length from the shared root (art #226)


def densify_ring(ring: dict, n: int = NECK_RING_COUNT) -> dict:
    """S8b: the neck ring at n vertices, so the head's loft and the body's subdivided end meet one to one (S1's 24-vertex
    ring needed a 2-to-1 join on the body side, the pleated collar). Each step doubles it: `loop` (an exact ellipse)
    gets the ellipse's points at the middle angles, `loop_below` (a measured loop) four-point midpoints."""
    out = dict(ring)
    while out["count"] < n:
        c, (ax, ay) = out["centre"], out["semi_axes"]
        m = out["count"] * 2
        loop, below = [], []
        lb = out["loop_below"]
        k0 = out["count"]
        for k in range(k0):
            loop.append(out["loop"][k])
            t = 2 * math.pi * (2 * k + 1) / m
            loop.append([round(c[0] + ax * math.sin(t), 6), round(c[1] - ay * math.cos(t), 6), out["z"]])
            below.append(lb[k])
            p0, p1, p2, p3 = (lb[(k + j) % k0] for j in (-1, 0, 1, 2))
            below.append([round((-p0[i] + 9 * p1[i] + 9 * p2[i] - p3[i]) / 16, 6) for i in range(3)])
        out.update({"count": m, "loop": loop, "loop_below": below, "densified_from": ring["count"]})
    if out["count"] != n:
        raise ValueError(f"densify_ring: {ring['count']} does not double to {n}")
    return out


def smoothstep(a: float, b: float, x: float) -> float:
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


class Built:
    """A bmesh with per-vertex mask values and material slots, turned into one object by to_object."""

    def __init__(self):
        self.bm = bmesh.new()
        self.mask = {}  # vertex -> (light, accent)
        self.mats: list[bpy.types.Material] = []

    def slot(self, mat) -> int:
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)

    def vert(self, co, light=0.0, accent=0.0):
        v = self.bm.verts.new(co)
        self.mask[v] = (light, accent)
        return v

    def face(self, vs, mi):
        f = self.bm.faces.new(vs)
        f.material_index = mi
        f.smooth = True
        return f


def to_object(b: Built, name: str, coll, origin: Matrix | None = None, recalc=True):
    """The bmesh as an object; origin (a world matrix) becomes the object's matrix with the data moved into its
    local space."""
    bm = b.bm
    if recalc:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    uv0 = bm.loops.layers.uv.new("UVMap")  # TEXCOORD_0: a front projection (no texture uses it yet)
    uv = bm.loops.layers.uv.new(MASKS)  # TEXCOORD_1: the masks
    for f in bm.faces:
        for lp in f.loops:
            lp[uv].uv = b.mask.get(lp.vert, (0.0, 0.0))
            lp[uv0].uv = (lp.vert.co.x * 4 + 0.5, lp.vert.co.z * 4 - 5.5)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in b.mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    if origin is not None:
        me.transform(origin.inverted())
        ob.matrix_world = origin
    return ob


def frame(origin: Vector, forward: Vector, up_hint: Vector = Vector((0, 0, 1))) -> Matrix:
    """A world matrix whose local -Y is forward, local +Z is up (up_hint made orthogonal), local +X = Y x Z."""
    f = forward.normalized()
    u = (up_hint - f * up_hint.dot(f)).normalized()
    y = -f
    x = y.cross(u).normalized()
    m = Matrix((x, y, u)).transposed().to_4x4()
    m.translation = origin
    return m


def tube(b: Built, centres, radii_a, radii_b, normals, mi, seg=16, masks=None, caps=True):
    """A tube swept along centres; its section is an ellipse with half-axis a along the given normal (made
    orthogonal to the tangent) and b across it. masks: per centre (light, accent)."""
    n = len(centres)
    rings = []
    for i in range(n):
        t = (centres[min(i + 1, n - 1)] - centres[max(i - 1, 0)]).normalized()
        nn = (normals[i] - t * normals[i].dot(t)).normalized()
        bb = t.cross(nn).normalized()
        mk = masks[i] if masks else (0.0, 0.0)
        ring = []
        for k in range(seg):
            a = 2 * math.pi * k / seg
            ring.append(b.vert(centres[i] + nn * (radii_a[i] * math.cos(a)) + bb * (radii_b[i] * math.sin(a)), *mk))
        rings.append(ring)
    for i in range(n - 1):
        for k in range(seg):
            b.face((rings[i][k], rings[i][(k + 1) % seg], rings[i + 1][(k + 1) % seg], rings[i + 1][k]), mi)
    if caps:
        for i, ring in ((0, rings[0]), (n - 1, rings[-1])):
            c = b.vert(centres[i], *(masks[i] if masks else (0.0, 0.0)))
            for k in range(seg):
                b.face((ring[k], ring[(k + 1) % seg], c), mi)
    return rings


def sphere(b: Built, c: Vector, r: float, mi, seg=24, rings=16, mask=(0.0, 0.0), squash=(1.0, 1.0, 1.0)):
    vs = []
    top = b.vert(c + Vector((0, 0, r * squash[2])), *mask)
    bot = b.vert(c - Vector((0, 0, r * squash[2])), *mask)
    for j in range(1, rings):
        th = math.pi * j / rings
        vs.append([b.vert(c + Vector((r * squash[0] * math.sin(th) * math.cos(2 * math.pi * k / seg),
                                      r * squash[1] * math.sin(th) * math.sin(2 * math.pi * k / seg),
                                      r * squash[2] * math.cos(th))), *mask) for k in range(seg)])
    for k in range(seg):
        b.face((top, vs[0][k], vs[0][(k + 1) % seg]), mi)
        b.face((bot, vs[-1][(k + 1) % seg], vs[-1][k]), mi)
    for j in range(rings - 2):
        for k in range(seg):
            b.face((vs[j][k], vs[j + 1][k], vs[j + 1][(k + 1) % seg], vs[j][(k + 1) % seg]), mi)


def eyeball(name: str, r: float, mat, coll, seg=32, rings=24):
    """A UV sphere of radius r round the origin with its pole on local -Y (the pupil) and an azimuthal UV: the uv
    radius from (0.5, 0.5) is the angle from the pole over pi, times 0.5 (the whole ball, one seam point at the
    back)."""
    b = Built()
    mi = b.slot(mat)
    pole = b.vert((0, -r, 0))
    back = b.vert((0, r, 0))
    ang = {pole: (0.0, 0.0), back: (math.pi, 0.0)}
    vs = []
    for j in range(1, rings):
        th = math.pi * j / rings
        row = []
        for k in range(seg):
            ph = 2 * math.pi * k / seg
            v = b.vert((r * math.sin(th) * math.cos(ph), -r * math.cos(th), r * math.sin(th) * math.sin(ph)))
            ang[v] = (th, ph)
            row.append(v)
        vs.append(row)
    for k in range(seg):
        b.face((pole, vs[0][(k + 1) % seg], vs[0][k]), mi)
        b.face((back, vs[-1][k], vs[-1][(k + 1) % seg]), mi)
    for j in range(rings - 2):
        for k in range(seg):
            b.face((vs[j][k], vs[j][(k + 1) % seg], vs[j + 1][(k + 1) % seg], vs[j + 1][k]), mi)
    bm = b.bm
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    uvl = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        phs = [ang[lp.vert][1] for lp in f.loops]
        ref = max(phs)
        for lp in f.loops:
            th, ph = ang[lp.vert]
            if lp.vert in (pole, back):  # a pole's azimuth is the face's
                ph = sum(p for p, l2 in zip(phs, f.loops) if l2.vert not in (pole, back)) / max(1, len(phs) - 1)
            elif ref - ph > math.pi:
                ph += 2 * math.pi
            rr = 0.5 * th / math.pi
            lp[uvl].uv = (0.5 + rr * math.cos(ph), 0.5 + rr * math.sin(ph))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def lid_shell(name: str, r: float, rho_in: float, rho_out: float, upper: bool, mat, coll, t_max_deg=89.0,
              span_deg=200.0, seg_t=20, seg_p=12, rim_seg=5, rim_mask_deg=22.0, bead=0.0, bead_deg=26.0, corner=None,
              flare=None):
    """A lid: a closed shell between radii rho_in*r and rho_out*r about the origin, built with its moving edge on
    local -Y (elevation 0). Elevation p is the angle about the hinge (local X) from -Y toward +Z; the upper lid covers
    p in [0, span], the lower p in [-span, 0]; latitude t (toward the hinge) in [-t_max, t_max]. The side edges lie on
    circles about the hinge, so turning the lid about local X never moves them. The edge is a rounded rim (a half
    circle in the profile); the accent mask is 1 at the rim, fading over rim_mask_deg. Rotating the object about its
    local X by -p puts the edge at elevation p.
    bead (a share of r, S7): the rolled rim of the eye sheets eb1 and em1: the outer surface swells by bead*r over the
    last bead_deg before the edge (a smooth bulge, the inner surface unchanged, so the eyeball's clearance stays) and
    the rim's half circle spans the thicker edge. The profile's samples crowd toward the edge (quadratic), so the
    roll stays round.
    corner (M6, art #196; alien_lids_geom.CORNER's form): the swell tapers toward the hinge poles and the edge bends
    toward the other lid there, so the corners are round from the front (S7's full rim stuck out as a point). None
    builds S7's shell exactly. The profile itself is alien_lids_geom.shell_profile (per latitude when rounded).
    flare (M10, alien_lids_geom.FLARE_OFF's form): the outer surface swells behind the edge where it meets the skin."""
    import alien_lids_geom as LG
    b = Built()
    mi = b.slot(mat)
    tm = math.radians(t_max_deg)
    grid = []
    rms = []
    m = 0
    for i in range(seg_t + 1):
        t = -tm + 2 * tm * i / seg_t
        bt = LG.bead_at(bead, t, tm, corner) if corner else bead
        sh = LG.edge_shift(t, tm, upper, corner) if corner else 0.0
        prof = LG.shell_profile(rho_in, rho_out, bt, upper, span_deg, seg_p, rim_seg, bead_deg, sh, crowd=bool(bead),
                                flare=flare, t=t)
        m = len(prof)
        row = []
        for rho, p, p0 in prof:
            d = Vector((math.sin(t), -math.cos(t) * math.cos(p), math.cos(t) * math.sin(p)))
            acc = 1.0 - smoothstep(0.0, math.radians(rim_mask_deg), abs(p0))
            row.append(b.vert(d * (rho * r), 0.0, acc))
        grid.append(row)
        rms.append((rho_out + bt + rho_in) / 2 * r)  # the row's rim centre radius (the side caps' pole)
    for i in range(seg_t):
        for j in range(m):
            b.face((grid[i][j], grid[i][(j + 1) % m], grid[i + 1][(j + 1) % m], grid[i + 1][j]), mi)
    for sgn_t, row, rm in ((-1.0, grid[0], rms[0]), (1.0, grid[-1], rms[-1])):
        # side caps: a fan to the hinge pole at the shell's mid radius, which closes the small hole round the hinge
        # axis (a point on the axis stays put as the lid turns)
        cv = b.vert(Vector((sgn_t * rm, 0.0, 0.0)), 0.0, 0.0)
        for j in range(m):
            b.face((row[j], row[(j + 1) % m], cv), mi)
    return to_object(b, name, coll)


def fin(b: Built, root: Vector, out: Vector, up: Vector, mi, ribs, thick=0.0035, rib_r=0.0022, cup=0.25, seg=10):
    """A fin ear: a membrane fan from a root point between rib rays (angle in degrees from out toward up, length),
    with a scalloped edge, a thickness, raised rib tubes and a cup (bend out of its plane). Accent mask grows to the
    edge."""
    out, up = out.normalized(), (up - out * up.dot(out)).normalized()
    nrm = out.cross(up).normalized()

    def at(a, bb):
        ln = math.hypot(a, bb)
        return root + out * a + up * bb + nrm * (cup * ln * ln / 0.07)

    edge = []  # the outline from the first rib's tip to the last, scalloped between ribs
    for k in range(len(ribs)):
        a0, l0 = ribs[k]
        edge.append((a0, l0))
        if k + 1 < len(ribs):
            a1, l1 = ribs[k + 1]
            for j in range(1, seg):
                f = j / seg
                aa = a0 + (a1 - a0) * f
                ll = (l0 + (l1 - l0) * f) * (1 - 0.22 * math.sin(math.pi * f))
                edge.append((aa, ll))
    lmax = max(l for _, l in ribs)
    rings = 6
    top, bot = [], []
    for k, (ang, ln) in enumerate(edge):
        rt, rb = [], []
        for j in range(rings + 1):
            f = j / rings
            a = math.radians(ang)
            x, z = math.cos(a) * ln * f, math.sin(a) * ln * f
            p = at(x, z)
            th = thick * (1 - 0.6 * f) + 0.0006
            acc = smoothstep(0.35, 1.0, f * ln / lmax)
            rt.append(b.vert(p + nrm * th / 2, 0.0, acc))
            rb.append(b.vert(p - nrm * th / 2, 0.0, acc))
        top.append(rt)
        bot.append(rb)
    for k in range(len(edge) - 1):
        for j in range(rings):
            b.face((top[k][j], top[k + 1][j], top[k + 1][j + 1], top[k][j + 1]), mi)
            b.face((bot[k][j + 1], bot[k + 1][j + 1], bot[k + 1][j], bot[k][j]), mi)
    for k in range(len(edge) - 1):  # the outer rim
        b.face((top[k][rings], top[k + 1][rings], bot[k + 1][rings], bot[k][rings]), mi)
    for k in (0, len(edge) - 1):  # the two side edges
        for j in range(rings):
            b.face((top[k][j], top[k][j + 1], bot[k][j + 1], bot[k][j]), mi)
    for ang, ln in ribs:  # ribs: raised tubes on both faces
        a = math.radians(ang)
        # Each rib starts RIB_START along its ray, not at the root: from one shared root point every rib's start cap
        # had the same centre and the same two points on the membrane's normal, so two edges per fin were shared by
        # six cap faces (non-manifold, art #226). The root sits inside the head, so the start does not show.
        fs = [RIB_START + (1 - RIB_START) * i / 10 for i in range(11)]
        cs = [at(math.cos(a) * ln * f, math.sin(a) * ln * f) for f in fs]
        rr = [rib_r * (1 - 0.55 * i / 10) for i in range(11)]
        tube(b, cs, rr, rr, [nrm] * 11, mi, seg=8,
             masks=[(0.0, smoothstep(0.35, 1.0, i / 10 * ln / lmax)) for i in range(11)])
