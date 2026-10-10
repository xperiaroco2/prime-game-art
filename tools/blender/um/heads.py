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
