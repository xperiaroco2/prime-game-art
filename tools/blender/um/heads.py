"""Head work: splitting a pack head by material regions (the bald skin head, a hairstyle, a moustache), cutting named
zones, flattening ears, straightening a collar ring, inflating hair off the skull and finding the eye centres.

Hair, brows, eyes, moustaches, beards, hats and earrings are material regions of the pack's head mesh. Men's eyes are
material "Eye"; women's eyes are "Brown" (on Formal and Medieval it also holds the brows); Punk "Red" includes a chin
goatee; King and men's Adventurer hair include beards; Casual Character "Skin_Darker" is stubble painted on the skin.
"""

import math

import bmesh
import bpy
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


def flatten_nose(head, x, eye_z, mouth_z, half_w=0.026, side_x=0.03, top_dz=0.012, bottom_dz=0.012, bulge=0.004,
                 fade=0.012, smooth=30):
    """Pushes the pack head's own nose back into the face, so that a scripted nose (the clay face kit's) sits on the
    face and not on the pack nose's tip (art #42: the kit's ball on the pack nose read as a forward cone). The faces
    lab's lab_base.flatten_nose (params_r2.json "nose_flatten"), on which every lab face was built: inside
    |x - x| < half_w (+ a fade) and between eye_z + top_dz and mouth_z + bottom_dz, every skin vertex in front of a
    smooth face surface moves back onto it. That surface at height z is the cheeks' y at x +- side_x (ray casts on the
    unchanged head) with a bulge toward the midline (bulge * (1 - (dx / side_x)^2)); then the zone is relaxed
    (smooth_patch). World space, rest pose, the face toward -Y. Returns what moved."""
    from mathutils.bvhtree import BVHTree
    me = head.data
    mw = head.matrix_world
    inv = mw.inverted()
    bvh = BVHTree.FromPolygons([mw @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
    z_top, z_bot = eye_z + top_dz, mouth_z + bottom_dz
    cheek = {}

    def cheek_y(z):
        k = round(z, 4)
        if k not in cheek:
            ys = []
            for sx in (-side_x, side_x):
                loc, _, _, _ = bvh.ray_cast(Vector((x + sx, -2.0, z)), Vector((0.0, 1.0, 0.0)))
                if loc is not None:
                    ys.append(loc.y)
            cheek[k] = sum(ys) / len(ys) if ys else None
        return cheek[k]

    moved, most = 0, 0.0
    for v in me.vertices:
        p = mw @ v.co
        dx = abs(p.x - x)
        if dx > half_w + fade or p.y > -0.08 or not (z_bot - fade < p.z < z_top + fade):
            continue
        cy = cheek_y(min(max(p.z, z_bot), z_top))
        if cy is None:
            continue
        target = cy - bulge * max(0.0, 1.0 - (dx / side_x) ** 2)
        if p.y >= target:
            continue
        sx = 1.0 if dx <= half_w else 1.0 - (dx - half_w) / fade  # full inside the box, fading over `fade` outside
        sz = 1.0
        if p.z > z_top:
            sz = 1.0 - (p.z - z_top) / fade
        elif p.z < z_bot:
            sz = 1.0 - (z_bot - p.z) / fade
        s = max(0.0, min(1.0, sx)) * max(0.0, min(1.0, sz))
        ny = p.y + (target - p.y) * s
        if abs(ny - p.y) > 1e-6:
            most = max(most, ny - p.y)
            moved += 1
            v.co = inv @ Vector((p.x, ny, p.z))
    me.update()
    smoothed = smooth_patch(head, lambda p: abs(p.x - x) <= half_w + fade and z_bot - fade < p.z < z_top + fade
                            and p.y < -0.08, iterations=smooth)
    return {"vertices_moved": moved, "largest_move_mm": round(most * 1000, 1), "smoothed_points": smoothed}


def smooth_patch(head, inside, iterations=30):
    """Relaxes the skin's y inside a zone (x and z kept): each point's y becomes its neighbours' mean, the zone's
    border held by the points outside it. The pack meshes are flat-shaded with split vertices, so points are grouped
    by position and moved together (no tearing). The faces lab's lab_base.smooth_patch. Returns the points relaxed."""
    if iterations <= 0:
        return 0
    me = head.data
    mw = head.matrix_world
    inv = mw.inverted()
    world = [mw @ v.co for v in me.vertices]
    key, groups = {}, []
    for i, p in enumerate(world):
        k = (round(p.x, 5), round(p.y, 5), round(p.z, 5))
        if k not in key:
            key[k] = len(groups)
            groups.append([])
        groups[key[k]].append(i)
    gid = {i: g for g, idx in enumerate(groups) for i in idx}
    nb = [set() for _ in groups]
    for e in me.edges:
        a, b = gid[e.vertices[0]], gid[e.vertices[1]]
        if a != b:
            nb[a].add(b)
            nb[b].add(a)
    ys = [world[idx[0]].y for idx in groups]
    free = [g for g, idx in enumerate(groups) if inside(world[idx[0]]) and nb[g]]
    for _ in range(iterations):
        new = {g: sum(ys[n] for n in nb[g]) / len(nb[g]) for g in free}
        for g, y in new.items():
            ys[g] = y
    for g in free:
        for i in groups[g]:
            p = world[i]
            me.vertices[i].co = inv @ Vector((p.x, ys[g], p.z))
    me.update()
    return len(free)


def bean_warp(head, x, eye_z, followers=(), centre_dz=-0.007, centre_y=-0.047, ax=0.086, ay=0.106, az_top=0.138,
              az_bottom=0.104, power=2.3, strength=0.85, fade_z=(0.035, 0.008), hair_k=6):
    """Reshapes the pack head into the faces lab's egg-like 'bean' head (art #42), the head every lab face was built
    on: the lab's lab_base.bean_warp (params faces/clay_head.json "bean"), run after flatten_nose and before the face
    skin is made rigid, as the lab's build_heads_r2 does.

    A space warp: every head vertex moves toward a superellipsoid (|dx/ax|^p + |dy/ay|^p + |dz/az|^p = 1, centred at
    world (x, centre_y, eye_z + centre_dz); az_top above the centre, az_bottom below it, so the chin comes up) along
    the ray from the centre, by `strength`; below the chin the share fades to nothing over fade_z (from chin -
    fade_z[0] to chin - fade_z[1], smoothstep) so the neck stays where it is. Each follower (the hair, a beard, a hat,
    an earring) moves with the skull under it: each vertex by the mean displacement of its hair_k nearest head
    vertices (inverse distance + 4 mm), so it still sits on the head. World space, rest pose, the face toward -Y.
    Returns what moved."""
    from mathutils.kdtree import KDTree
    me = head.data
    mw = head.matrix_world
    inv = mw.inverted()
    pts = [mw @ v.co for v in me.vertices]
    c = Vector((x, centre_y, eye_z + centre_dz))
    front = [p for p in pts if p.y < -0.11 and abs(p.x - x) < 0.02]
    chin = min(p.z for p in front)
    z0, z1 = chin - fade_z[0], chin - fade_z[1]
    disp, most = [], 0.0
    for p in pts:
        d = p - c
        az = az_top if d.z >= 0 else az_bottom
        f = (abs(d.x) / ax) ** power + (abs(d.y) / ay) ** power + (abs(d.z) / az) ** power
        if f < 1e-12:
            disp.append(Vector())
            continue
        target = c + d / (f ** (1.0 / power))
        w = 1.0 if p.z >= z1 else (0.0 if p.z <= z0 else (p.z - z0) / (z1 - z0))
        w = w * w * (3 - 2 * w)  # smoothstep
        dv = (target - p) * (strength * w)
        disp.append(dv)
        most = max(most, dv.length)
    for v, p, dv in zip(me.vertices, pts, disp):
        v.co = inv @ (p + dv)
    me.update()
    kd = KDTree(len(pts))
    for i, p in enumerate(pts):
        kd.insert(p, i)
    kd.balance()
    moved = {}
    for o in followers:
        if o is None:
            continue
        ow = o.matrix_world
        oinv = ow.inverted()
        for v in o.data.vertices:
            p = ow @ v.co
            near = kd.find_n(p, hair_k)
            ws = [1.0 / (dist + 0.004) for _, _, dist in near]
            dv = sum((disp[i] * w for (_, i, _), w in zip(near, ws)), Vector()) / sum(ws)
            v.co = oinv @ (p + dv)
        o.data.update()
        moved[o.name] = len(o.data.vertices)
    return {"centre": [round(k, 4) for k in c], "chin_z_before": round(chin, 4), "largest_move_mm": round(most * 1000, 1),
            "followers_moved": moved, "radii": [ax, ay, az_top, az_bottom], "power": power, "strength": strength}


def _bean_project(P, c, radii, power):
    """Points P (n x 3, world) moved along the ray from c onto the bean superellipsoid (the lab's
    clay_parts.bean_project)."""
    import numpy as np
    ax, ay, azt, azb = radii
    d = P - c
    az = np.where(d[:, 2] >= 0, azt, azb)
    f = (np.abs(d[:, 0]) / ax) ** power + (np.abs(d[:, 1]) / ay) ** power + (np.abs(d[:, 2]) / az) ** power
    f = np.maximum(f, 1e-12)
    return c + d / f[:, None] ** (1.0 / power)


def _wco(o):
    import numpy as np
    a = np.empty(len(o.data.vertices) * 3, np.float64)
    o.data.vertices.foreach_get("co", a)
    M = np.array(o.matrix_world, dtype=np.float64)
    return a.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]


def _set_wco(o, P):
    import numpy as np
    Mi = np.array(o.matrix_world.inverted(), dtype=np.float64)
    o.data.vertices.foreach_set("co", (P @ Mi[:3, :3].T + Mi[:3, 3]).astype(np.float32).ravel())
    o.data.update()


def _small_pieces(bm, max_faces):
    """The faces of the connected pieces (shared vertices) of at most max_faces faces."""
    bm.verts.index_update()
    parent = list(range(len(bm.verts)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for e in bm.edges:
        a, b = find(e.verts[0].index), find(e.verts[1].index)
        if a != b:
            parent[a] = b
    pieces = {}
    for f in bm.faces:
        pieces.setdefault(find(f.verts[0].index), []).append(f)
    return [f for fs in pieces.values() if len(fs) <= max_faces for f in fs]


def _transfer_weights(dst, src):
    """Vertex groups of src carried to dst (same rig): each dst vertex takes the barycentric blend of the weights at
    its nearest point on src (the lab's clay_parts.transfer_weights). Returns the number of groups written."""
    from mathutils.bvhtree import BVHTree
    from mathutils.interpolate import poly_3d_calc
    bm = bmesh.new()
    bm.from_mesh(src.data)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    dl = bm.verts.layers.deform.active
    mws = src.matrix_world
    vs = [mws @ v.co for v in bm.verts]
    tri = [[v.index for v in f.verts] for f in bm.faces]
    wts = [dict(v[dl]) if dl is not None else {} for v in bm.verts]
    bm.free()
    bvh = BVHTree.FromPolygons(vs, tri)
    names = [g.name for g in src.vertex_groups]
    for g in list(dst.vertex_groups):
        dst.vertex_groups.remove(g)
    groups = [dst.vertex_groups.new(name=n) for n in names]
    mwd = dst.matrix_world
    acc = {}
    for v in dst.data.vertices:
        loc, _, fi, _ = bvh.find_nearest(mwd @ v.co)
        t = tri[fi]
        bc = poly_3d_calc([vs[i] for i in t], loc)
        w = {}
        for i, b in zip(t, bc):
            for gi, x in wts[i].items():
                w[gi] = w.get(gi, 0.0) + b * x
        tot = sum(w.values())
        for gi, x in w.items():
            if x > 1e-4 and tot > 0:
                acc.setdefault(gi, []).append((v.index, x / tot))
    for gi, lst in acc.items():
        for vi, x in lst:
            groups[gi].add([vi], x, "REPLACE")
    return len(acc)


def _sphere_uv(o, c):
    """A spherical UV map about c, its seam at the back (the lab's clay_parts.sphere_uv)."""
    me = o.data
    uv = me.uv_layers[0] if me.uv_layers else me.uv_layers.new(name="UVMap")
    mw = o.matrix_world
    for poly in me.polygons:
        us = []
        for li in poly.loop_indices:
            p = mw @ me.vertices[me.loops[li].vertex_index].co - Vector(tuple(c))
            u = (math.atan2(p.x, -p.y) / (2 * math.pi)) % 1.0
            v = math.acos(max(-1.0, min(1.0, p.z / max(p.length, 1e-9)))) / math.pi
            us.append([u, 1.0 - v])
        if max(x[0] for x in us) - min(x[0] for x in us) > 0.5:
            for x in us:
                if x[0] < 0.5:
                    x[0] += 1.0
        for li, x in zip(poly.loop_indices, us):
            uv.data[li].uv = x


def clean_head(head, x, eye_z, bean, skin_mat=None, neck_dz=0.02, sphere=(64, 32), voxel_m=0.003, tris=1200,
               snap_tol=0.06, crease_band=(-0.045, 0.01), crease_passes=4, weight_blend_m=0.02, small_piece_faces=120):
    """The faces lab's clean bean head (art #42; clay_b/clay_parts.build_head, the head under every approved lab face),
    run after bean_warp and the rigid face skin. The warped pack head still carries the pack's eye holes and socket
    creases at 15 %, and the women's (and some men's) pack heads leave the crown and the back of the skull to the hair,
    so the head above the neck is REPLACED by the closed bean itself:

    1. the warped head welded, its small loose pieces (<= small_piece_faces) dropped, then cut below
       z_neck = the bean's centre z - az_bottom + neck_dz, the cut filled;
    2. united with a UV sphere (sphere: segments, rings) put onto the bean, voxel remeshed at voxel_m and decimated
       to `tris`;
    3. every vertex within |f - 1| < snap_tol of the bean put exactly on it, the crease where the neck meets the bean's
       underside softened (crease_passes neighbour means between z_neck + crease_band);
    4. the weights: the warped pack head's below the cut, the Head bone alone above it (smoothstep over
       weight_blend_m); smooth shading, a spherical UV map, one material (skin_mat, else the head's first).

    `bean` is faces/clay_head.json "bean". World space, rest pose, the face toward -Y. Returns what was done."""
    import numpy as np
    from . import clay as cl
    mw = head.matrix_world.copy()
    inv = mw.inverted()
    c = np.array([x, bean["centre_y"], eye_z + bean["centre_dz"]])
    radii = (bean["ax"], bean["ay"], bean["az_top"], bean["az_bottom"])
    power = bean["power"]
    z_neck = float(c[2] - radii[3] + neck_dz)
    info = {"z_neck": round(z_neck, 4)}
    mat = skin_mat or (head.data.materials[0] if head.data.materials else None)
    # 1. weld, drop loose bits, keep a weighted copy for the neck's weights, cut and cap (world space)
    bm = bmesh.new()
    bm.from_mesh(head.data)
    n0 = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5 / cl.wscale(head))
    info["welded_vertices"] = n0 - len(bm.verts)
    small = _small_pieces(bm, small_piece_faces)
    bmesh.ops.delete(bm, geom=small, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    info["small_pieces_removed_faces"] = len(small)
    wsrc = head.copy()
    wsrc.data = head.data.copy()
    bm.to_mesh(wsrc.data)  # welded, with its vertex groups (the deform layer travels with the bmesh)
    bm.transform(mw)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=Vector((0, 0, z_neck)), plane_no=Vector((0, 0, 1)), clear_outer=True)
    filled = bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=0)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    info["neck_caps"] = len(filled["faces"])
    bm.verts.index_update()
    nv = [tuple(v.co) for v in bm.verts]
    nf = [tuple(v.index for v in f.verts) for f in bm.faces]
    bm.free()
    # 2. the union with the bean, remeshed and decimated
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=sphere[0], v_segments=sphere[1], radius=1.0)
    bm.verts.index_update()
    Pb = _bean_project(np.array([tuple(v.co) for v in bm.verts]) * 0.1 + c, c, radii, power)
    off = len(nv)
    nv += [tuple(p) for p in Pb]
    nf += [tuple(off + v.index for v in f.verts) for f in bm.faces]
    bm.free()
    me = bpy.data.meshes.new(head.data.name + "_bean")
    me.from_pydata([tuple(inv @ Vector(p)) for p in nv], [], nf)
    me.update()
    if mat is not None:
        me.materials.append(mat)
    old = head.data
    head.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)
    for g in list(head.vertex_groups):
        head.vertex_groups.remove(g)
    rem = head.modifiers.new("bean_remesh", "REMESH")
    rem.mode = "VOXEL"
    rem.voxel_size = voxel_m / cl.wscale(head)
    rem.adaptivity = 0.0
    info["remesh_tris"] = cl.apply_modifiers(head)
    dec = head.modifiers.new("bean_decimate", "DECIMATE")
    dec.ratio = min(1.0, tris / max(1, cl.tris(head.data)))
    cl.apply_modifiers(head)
    # 3. exactly the bean where it is the bean; the neck crease softened
    Pw = _wco(head)
    d = Pw - c
    az = np.where(d[:, 2] >= 0, radii[2], radii[3])
    f = ((np.abs(d[:, 0]) / radii[0]) ** power + (np.abs(d[:, 1]) / radii[1]) ** power
         + (np.abs(d[:, 2]) / az) ** power) ** (1.0 / power)
    on = np.abs(f - 1.0) < snap_tol
    Pw[on] = _bean_project(Pw[on], c, radii, power)
    nb = [[] for _ in range(len(Pw))]
    for e in head.data.edges:
        a, b = e.vertices
        nb[a].append(b)
        nb[b].append(a)
    crease = np.where(~on & (Pw[:, 2] > z_neck + crease_band[0]) & (Pw[:, 2] < z_neck + crease_band[1]))[0]
    for _ in range(crease_passes):
        Pw[crease] = 0.5 * Pw[crease] + 0.5 * np.array([Pw[nb[i]].mean(0) if nb[i] else Pw[i] for i in crease])
    _set_wco(head, Pw)
    info["on_bean_vertices"] = int(on.sum())
    info["crease_vertices_softened"] = int(len(crease))
    # 4. the weights
    info["weights_transferred"] = _transfer_weights(head, wsrc)
    wme = wsrc.data
    bpy.data.objects.remove(wsrc, do_unlink=True)
    bpy.data.meshes.remove(wme)
    hg = head.vertex_groups.get("Head") or head.vertex_groups.new(name="Head")
    for v in head.data.vertices:
        t = min(1.0, max(0.0, (Pw[v.index, 2] - (z_neck - weight_blend_m)) / weight_blend_m))
        t = t * t * (3 - 2 * t)
        if t <= 0.0:
            continue
        for ge in list(v.groups):
            if ge.group != hg.index:
                head.vertex_groups[ge.group].add([v.index], ge.weight * (1 - t), "REPLACE")
        hw = next((ge.weight for ge in v.groups if ge.group == hg.index), 0.0)
        hg.add([v.index], hw * (1 - t) + t, "REPLACE")
    cl.smooth_shade(head.data)
    _sphere_uv(head, c)
    info["tris"] = cl.tris(head.data)
    return info


def morph_jaw(head, x, eye_z, bean, profile, band_dz=(-0.1201, -0.0926, -0.068), reach=0.03):
    """The lab's ONE head's jaw on the clean head (art #42; clay_c/clay_head_c.py morph_jaw, run after clean_head).
    The lab's cast head is round B's men's clean head with its jaw grown out toward the women's; the repo's clean head
    keeps each pack head's jaw, which sits behind the jaw check's 3/4 line. `profile` (faces/clay_head.json
    "jaw_morph") is the lab head's radius about the bean centre's vertical axis, sampled per dz from the bean centre
    and azimuth (from -Y toward +X), unscaled. Every vertex inside band_dz (lo, mid, hi: a smoothstep bump, 0 at lo and
    hi, 1 at mid) whose radius r is below the profile's r_l by less than `reach` moves out horizontally by
    (r_l - r) x the bump; never in. World space, rest pose, the face toward -Y. Returns what was done."""
    import numpy as np
    c = np.array([x, bean["centre_y"], eye_z + bean["centre_dz"]])
    DZ = np.array(profile["dz"], np.float64)
    AZ = np.array(profile["az_deg"], np.float64)
    R = np.array(profile["r"], np.float64)
    lo, mid, hi = band_dz
    P = _wco(head)
    d = P - c
    z = d[:, 2]
    sel = np.where((z > lo) & (z < hi))[0]
    info = {"vertices": 0, "largest_mm": 0.0}
    if not len(sel):
        return info
    zs = z[sel]
    t = np.where(zs <= mid, (zs - lo) / (mid - lo), (hi - zs) / (hi - mid))
    w = t * t * (3 - 2 * t)
    r = np.hypot(d[sel, 0], d[sel, 1])
    az = np.degrees(np.arctan2(d[sel, 0], -d[sel, 1])) % 360.0
    # bilinear in (dz, az): dz clamped to the samples, az wrapping
    fi = np.clip((zs - DZ[0]) / (DZ[1] - DZ[0]), 0.0, len(DZ) - 1.000001)
    i0 = np.floor(fi).astype(int)
    u = fi - i0
    step = AZ[1] - AZ[0]
    fj = az / step
    j0 = np.floor(fj).astype(int) % len(AZ)
    j1 = (j0 + 1) % len(AZ)
    v = fj - np.floor(fj)
    r_l = ((1 - u) * ((1 - v) * R[i0, j0] + v * R[i0, j1]) + u * ((1 - v) * R[i0 + 1, j0] + v * R[i0 + 1, j1]))
    ok = (r > 1e-6) & (r < r_l) & (r_l < r + reach)
    move = np.where(ok, (r_l - r) * w, 0.0)
    k = np.where(ok, (r + move) / np.maximum(r, 1e-6), 1.0)
    P[sel, 0] = c[0] + d[sel, 0] * k
    P[sel, 1] = c[1] + d[sel, 1] * k
    _set_wco(head, P)
    info["vertices"] = int((move > 1e-5).sum())
    info["largest_mm"] = round(float(move.max()) * 1000, 2)
    return info


def _position_groups(P, weld_m=1e-5):
    """Vertex -> group index, one group per welded position (rounded to weld_m): the pack's split (flat-shaded, UV
    seam) vertices of one corner share a group, so a move given per group keeps the mesh whole."""
    import numpy as np
    key = np.round(P / weld_m).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    return inv.reshape(-1), int(inv.max()) + 1 if len(inv) else 0


def _rays(n_el, n_az):
    import numpy as np
    els = np.linspace(-math.pi / 2, math.pi / 2, n_el)
    azs = np.linspace(0, 2 * math.pi, n_az, endpoint=False)
    return els, azs


def _grid_at(G, P, centre):
    """The grid's value (bilinear over elevation x azimuth about centre), the unit rays and radii of points P."""
    import numpy as np
    d = P - np.array(centre)
    r = np.maximum(np.linalg.norm(d, axis=1), 1e-9)
    el = np.arcsin(np.clip(d[:, 2] / r, -1, 1))
    az = np.arctan2(d[:, 0], -d[:, 1]) % (2 * math.pi)
    n_el, n_az = G.shape
    fe = (el + math.pi / 2) / math.pi * (n_el - 1)
    fa = az / (2 * math.pi) * n_az
    e0 = np.clip(np.floor(fe).astype(int), 0, n_el - 2)
    a0 = np.floor(fa).astype(int) % n_az
    a1 = (a0 + 1) % n_az
    te, ta = fe - e0, fa - np.floor(fa)
    v = G[e0, a0] * (1 - te) * (1 - ta) + G[e0, a1] * (1 - te) * ta + G[e0 + 1, a0] * te * (1 - ta) + G[e0 + 1, a1] * te * ta
    return v, d / r[:, None], r


def _bvh(o):
    from mathutils.bvhtree import BVHTree
    P = _wco(o)
    return BVHTree.FromPolygons([Vector(tuple(p)) for p in P], [tuple(q.vertices) for q in o.data.polygons])


def lift_grid(o, head, centre, clear=0.004, depth=0.03, n_az=72, n_el=45):
    """The lab's scalp lift (clay_b/clay_parts.lift_grid): how far a hair must move out, per direction from the skull
    centre, so that its innermost surface (ignoring what lies deeper than `depth` inside the head: hidden) clears the
    clean bean head by `clear`; dilated by one cell and smoothed. Returns (grid, head radius grid)."""
    import numpy as np
    hb, ob = _bvh(head), _bvh(o)
    c = Vector(tuple(centre))
    N = np.zeros((n_el, n_az))
    RH = np.full((n_el, n_az), np.nan)
    els, azs = _rays(n_el, n_az)
    for i, el in enumerate(els):
        for j, az in enumerate(azs):
            d = Vector((math.cos(el) * math.sin(az), -math.cos(el) * math.cos(az), math.sin(el)))
            h = hb.ray_cast(c, d, 0.5)
            if h[0] is None:
                continue
            rh = (h[0] - c).length
            RH[i, j] = rh
            start = max(0.0, rh - depth)
            t = ob.ray_cast(c + d * start, d, 0.5)
            if t[0] is None:
                continue
            ri = start + t[3]
            if ri < rh + clear:
                N[i, j] = rh + clear - ri
    P = np.pad(N, ((1, 1), (0, 0)), mode="edge")
    M = np.max(np.stack([N, np.roll(N, 1, 1), np.roll(N, -1, 1), P[:-2], P[2:]]), axis=0)
    P = np.pad(M, ((1, 1), (0, 0)), mode="edge")
    G = (2 * M + np.roll(M, 1, 1) + np.roll(M, -1, 1) + P[:-2] + P[2:]) / 6.0
    return G, np.nan_to_num(RH, nan=0.0)


def lift_by(o, G, RH, centre, depth=0.03):
    """The lab's lift_by: every vertex moves out along its ray from the centre by the lift grid (a hair's shell moves as
    one: its thickness and its split vertices kept); vertices deeper than `depth` inside the head stay (hidden). Returns
    the largest lift in mm."""
    import numpy as np
    P = _wco(o)
    lift, dn, r = _grid_at(G, P, centre)
    rh, _, _ = _grid_at(RH, P, centre)
    lift = np.where(r < rh - depth, 0.0, lift)
    _set_wco(o, P + dn * lift[:, None])
    return round(float(lift.max()) * 1000, 1) if len(lift) else 0.0


def push_out(o, head, clear=0.004, reach=0.035, passes=4, keep=0.85):
    """Hair, a hat or a beard that sinks into the clean bean head, or lies closer than `clear`, moves out along the
    head's surface normal at its nearest point until it clears it; vertices deeper than `reach` stay (hidden inside the
    head). The move is spread to neighbours (keep x the largest neighbour's move). The lab's clay_parts.push_out, with
    which round B fitted every hair and hat on the clean head (HAIR_CLEAR, HAT_CLEAR 4 mm), after its clay pass had
    welded the part: here the part is not welded yet, so the move is found and spread per welded position group
    (_position_groups), never per split vertex, or the pack's flat-shaded hair tears into shards. Returns what moved."""
    import numpy as np
    from mathutils.bvhtree import BVHTree
    hm = head.matrix_world
    bvh = BVHTree.FromPolygons([hm @ v.co for v in head.data.vertices], [tuple(p.vertices) for p in head.data.polygons])
    P = _wco(o)
    grp, n = _position_groups(P)
    Q = np.zeros((n, 3))
    Q[grp] = P
    D = np.zeros_like(Q)
    for i, p in enumerate(Q):
        loc, nrm, _, _ = bvh.find_nearest(Vector(tuple(p)))
        if loc is None:
            continue
        sd = (Vector(tuple(p)) - loc).dot(nrm)
        if -reach < sd < clear:
            D[i] = np.array(nrm) * (clear - sd)
    nb = [set() for _ in range(n)]
    for e in o.data.edges:
        a, b = grp[e.vertices[0]], grp[e.vertices[1]]
        if a != b:
            nb[a].add(b)
            nb[b].add(a)
    nb = [list(x) for x in nb]
    for _ in range(passes):
        L = np.linalg.norm(D, axis=1)
        new = D.copy()
        for i, nn in enumerate(nb):
            if nn:
                j = nn[int(np.argmax(L[nn]))]
                if keep * L[j] > L[i]:
                    new[i] = keep * D[j]
        D = new
    _set_wco(o, P + D[grp])
    L = np.linalg.norm(D, axis=1)
    return {"vertices_pushed": int((L[grp] > 1e-5).sum()), "position_groups": n,
            "largest_push_mm": round(float(L.max()) * 1000, 1) if n else 0.0}
