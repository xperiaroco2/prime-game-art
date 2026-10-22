"""Hull shape blockouts (art #263): the manta's outer shape alone, grey, untextured, under even studio light, so the
engineer can judge the SHAPE before any material, light or detail.

His decisions (2026-10-22): flat wings with sharp, swept-back tips (no upcurl); the rooms hidden inside one clean
shape (no domes, pods or pillow bulges); no tip windows in the main variants, so the wing thins to a sharp edge
beyond the tip rooms; the night build's faceted look (crisp planes and edges, the spine with the two canopy bumps
over the mouth, the mouth recess, the stern's three nozzle pods, landing legs as blocks); the span may grow.

The hull is the CONVEX HULL of a few design points (plan metres: x east, y south, h up; Blender gets (x, -y, h)),
mirrored in x, so it is one faceted shape with no local bump by construction:
    the spine     a ridge 2.6 m wide, its profile SPINE rising from the brow to a peak over the hall's crown
    the nose      a wedge with its edge NOSE across the front; the mouth recess is cut into it
    the lead edge one straight 3D line from the nose's corner to the tip, through LEAD_PIVOT in plan (ahead of the
                  tip room)
    the tip       one vertex: the lead and trail edges meet there (a variant's span and tip height)
    the trail     one straight 3D line from the tip back to the stern's corner
    the stern     a flat face with the three nozzle pods (stand-ins) sticking out
    the belly     flat at BELLY under every room's slab, rising toward every edge
then the mouth recess (and, in a window variant, the tip rooms' window sectors) cut away and coplanar facets merged.
Every room's outer surface (ship.toml: the clear sizes plus the walls, the roofs and the slabs) is sampled and must
lie inside the hull with at least SKIN of hull around it; the mouth's own opening is the only exception.

    blender -b --factory-startup --python ship_hull_blockout.py -- --out <dir> [--variants A,B,C,D]
            [--crops <dir>] [--hero <jpg>]

Writes <out>/sheet.png (the 2D's turnaround crops and hero, then one row per variant: front, side, back, top, hero
in flat grey, the variant's numbers on the row), <out>/ghost.png (each variant's top and front with the rooms as a
faint ghost), <out>/report.json (per variant: span, length, height, the wing's thickness 1 m from the tip, the
interior points closer than SKIN to the outside), <out>/blockout.blend and prints BLOCKOUT lines."""

from __future__ import annotations

import json
import math
import sys
import tomllib
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[2]
SHIP = tomllib.loads((ROOT / "layouts/ship/ship.toml").read_text(encoding="utf-8"))
RM = {r["id"]: r for r in SHIP["rooms"]}
FLOOR = SHIP["deck"]["floor_h"]                                        # 0.6
SLAB = FLOOR - SHIP["deck"]["slab_m"]                                  # 0.35: the slabs' bottoms
WALL = SHIP["deck"]["wall_m"]                                          # 0.2: a room's wall outside its clear size
ROOF = 0.12                                                            # a room's ceiling over its clear height
SKIN = 0.15                                                            # the least hull around every room
HALL_R = RM["hall"]["radius"] + WALL                                   # 4.2
HALL_RIM = FLOOR + RM["hall"]["clear_h"] + ROOF                        # 3.92
HALL_APEX = FLOOR + RM["hall"]["apex_h"] + ROOF                        # 4.52
COR_X = tuple(RM["corridor_e"]["x"])                                   # (3.7, 7.3)
COR_Y = RM["corridor_e"]["y"][1] + WALL                                # 1.7
COR_TOP = FLOOR + RM["corridor_e"]["clear_h"] + ROOF                   # 3.12
MOUTH_X = RM["mouth"]["x"][1]                                          # 1.3: the recess's half width
MOUTH_Y = RM["mouth"]["y"][0]                                          # -4.6: the opening (the recess's back plane)
MOUTH_TOP = FLOOR + RM["mouth"]["clear_h"]                             # 3.0: the recess's ceiling
TIP_X = RM["tip_e"]["centre"][0]                                       # 8.3
TIP_R = RM["tip_e"]["radius"] + WALL                                   # 2.0
TIP_RIM = FLOOR + RM["tip_e"]["clear_h"] + ROOF                        # 3.22
TIP_APEX = FLOOR + RM["tip_e"]["apex_h"] + ROOF                        # 3.52
WIN = RM["tip_e"]["window"]
WIN_HALF = math.radians(WIN["half_angle_deg"])                         # 65 deg
SILL, HEAD = FLOOR + WIN["sill_h"], FLOOR + WIN["head_h"]              # 1.6, 2.8
RAMP = SHIP["ramp"]

BELLY = SLAB - 0.18                                                    # 0.17
SPINE_X = 1.3
SPINE = [(-4.6, 4.3), (-1.0, 4.82), (1.6, 4.82), (4.6, 4.3)]          # (plan y, h): the spine's profile, peak over the hall
NOSE = (2.2, -7.1, 2.0)                                                # the nose's edge (+-x, y, h): a wedge, the mouth cut in it
LEAD_PIVOT = (TIP_X, -3.4)                                             # the lead edge passes here: 1.4 m before the room
LEAD_SLOPE = (LEAD_PIVOT[1] - NOSE[1]) / (LEAD_PIVOT[0] - NOSE[0])
TRAIL_END = (4.4, 6.1, 2.3)
STERN_Y = 6.3
STERN = [(1.4, 3.75), (3.2, 3.25), (3.2, 0.95), (1.4, 0.7)]
NOZZLES = [(-2.75, 3.85, 2.15, 1.05, 3.25), (0.0, 4.25, 2.45, 1.2, 3.65), (2.75, 3.85, 2.15, 1.05, 3.25)]
CANOPY = (2.25, -3.6, 0.95, 1.35, 0.75)                                # x, y, half axes, height over the hull
LEGS = [(4.3, -4.5), (5.0, 4.7), (11.6, 0.4)]                         # plan spots, mirrored; a leg needs 0.45 m under
VARIANTS = {   # half span, tip height, the tip rooms' windows
    "A": {"half": 13.75, "tip_h": 3.3, "window": False},
    "B": {"half": 15.0, "tip_h": 3.15, "window": False},
    "C": {"half": 16.0, "tip_h": 3.2, "window": False},
    "D": {"half": 15.0, "tip_h": 1.2, "window": True},
}
BG = np.array([0.05, 0.07, 0.1, 1.0], dtype=np.float32)


def arg(name, default=None):
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return argv[argv.index(name) + 1] if name in argv else default


def bl(p):
    return (p[0], -p[1], p[2])


def mirrored(pts):
    out = []
    for x, y, z in pts:
        out.append((x, y, z))
        if abs(x) > 1e-6:
            out.append((-x, y, z))
    return out


def ring(cx, cy, r, z, n=16, a0=0.0, a1=360.0):
    """Points on a circle circumscribing the room's circle (the chords stay outside r)."""
    rr = r / math.cos(math.pi / n)
    k = max(1, round((a1 - a0) / (360.0 / n)))
    return [(cx + rr * math.cos(math.radians(a0 + (a1 - a0) * i / k)),
             cy + rr * math.sin(math.radians(a0 + (a1 - a0) * i / k)), z) for i in range(k + 1)]


def design_points(var):
    half, tip_h = var["half"], var["tip_h"]
    tip = (half, LEAD_PIVOT[1] + LEAD_SLOPE * (half - LEAD_PIVOT[0]), tip_h)
    pts = [(SPINE_X, y, z) for y, z in SPINE] + [NOSE, tip, TRAIL_END]
    pts += [(x, STERN_Y, z) for x, z in STERN]
    pts += ring(0.0, 0.0, HALL_R + 0.3, BELLY) + ring(TIP_X, 0.0, TIP_R + 0.25, BELLY)
    pts += [(MOUTH_X + WALL + 0.3, MOUTH_Y - 0.2, BELLY)]
    if var["window"]:   # the room's cover: the wing steps down beyond it to a tip under the sill
        pts += ring(TIP_X, 0.0, TIP_R + 0.25, TIP_RIM + 0.25, a0=-90.0, a1=90.0)
    return mirrored([p for p in pts if p[0] >= -1e-6]), tip


def interior_points():
    """(what, plan point) of every room's outer surface: walls, ceilings, crowns and slab bottoms."""
    pts = []
    for d in range(0, 360, 5):
        c, s = math.cos(math.radians(d)), math.sin(math.radians(d))
        x, y = HALL_R * c, HALL_R * s
        if not (abs(x) < MOUTH_X + WALL and y < 0):
            for h in (SLAB, 1.4, 2.6, HALL_RIM):
                pts.append(("hall wall", (x, y, h)))
        for rr in (1.0, 2.0, 3.0, 4.0):
            pts.append(("hall roof", (rr * c, rr * s, HALL_APEX - (HALL_APEX - HALL_RIM) * rr / HALL_R)))
            pts.append(("hall slab", (rr * c, rr * s, SLAB)))
    pts.append(("hall crown", (0.0, 0.0, HALL_APEX)))
    for x in (-MOUTH_X - WALL, -MOUTH_X, 0.0, MOUTH_X, MOUTH_X + WALL):
        for y in (MOUTH_Y + SKIN + 0.01, -3.9):
            for h in (SLAB, MOUTH_TOP + ROOF):
                pts.append(("mouth", (x, y, h)))
    for side in (-1, 1):
        x = COR_X[0]
        while x <= COR_X[1] + 1e-6:
            for y in (-COR_Y, COR_Y):
                for h in (SLAB, 1.7, COR_TOP):
                    pts.append(("corridor", (side * x, y, h)))
            pts.append(("corridor roof", (side * x, 0.0, COR_TOP)))
            x += 0.3
        for d in range(0, 360, 5):
            c, s = math.cos(math.radians(d)), math.sin(math.radians(d))
            for h in (SLAB, SILL, HEAD, TIP_RIM):
                pts.append(("tip wall", (side * (TIP_X + TIP_R * c), TIP_R * s, h)))
            for rr in (0.6, 1.2, 1.8):
                pts.append(("tip roof", (side * (TIP_X + rr * c), rr * s,
                                         TIP_APEX - (TIP_APEX - TIP_RIM) * rr / TIP_R)))
                pts.append(("tip slab", (side * (TIP_X + rr * c), rr * s, SLAB)))
        pts.append(("tip crown", (side * TIP_X, 0.0, TIP_APEX)))
    return pts


def mat(name, rgb):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1.0)
    return m


def new_obj(name, bm, m, coll):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = False
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def bm_from(verts, faces):
    bm = bmesh.new()
    vs = [bm.verts.new(bl(v)) for v in verts]
    for f in faces:
        bm.faces.new([vs[i] for i in f])
    return bm


def prism(poly, z0, z1):
    """A closed prism over a plan polygon (counter-clockwise or not: normals are recalculated)."""
    n = len(poly)
    v = [(x, y, z0) for x, y in poly] + [(x, y, z1) for x, y in poly]
    f = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i)
                                                                 for i in range(n)]
    return v, f


def sector_prism(cx, sign, r0, r1, z0, z1, n=24):
    """The window's clear sector: from radius r0 (the glass) outward, +-WIN_HALF around the room's outward axis."""
    a = [(-WIN_HALF + 2 * WIN_HALF * i / n) for i in range(n + 1)]
    inner = [(cx + sign * r0 * math.cos(t), r0 * math.sin(t)) for t in a]
    outer = [(cx + sign * r1 * math.cos(t), r1 * math.sin(t)) for t in a]
    v, f = [], []
    for z in (z0, z1):
        v += [(x, y, z) for x, y in inner] + [(x, y, z) for x, y in outer]
    m = n + 1
    ib, ob, it, ot = 0, m, 2 * m, 3 * m
    for i in range(n):
        f.append((ib + i, ib + i + 1, ob + i + 1, ob + i))          # bottom
        f.append((it + i, ot + i, ot + i + 1, it + i + 1))          # top
        f.append((ib + i, it + i, it + i + 1, ib + i + 1))          # inner wall
        f.append((ob + i, ob + i + 1, ot + i + 1, ot + i))          # outer wall
    f.append((ib, ob, ot, it))
    f.append((ib + n, it + n, ot + n, ob + n))
    return v, f


def hull_object(name, var, coll, m, m_recess, cut_coll):
    pts, tip = design_points(var)
    bm = bmesh.new()
    for p in pts:
        bm.verts.new(bl(p))
    res = bmesh.ops.convex_hull(bm, input=bm.verts, use_existing_faces=False)
    drop = list({g for g in res["geom_interior"] + res["geom_unused"] if isinstance(g, bmesh.types.BMVert)})
    bmesh.ops.delete(bm, geom=drop, context="VERTS")
    ob = new_obj(name, bm, m, coll)
    cv, cf = prism([(-MOUTH_X, MOUTH_Y), (MOUTH_X, MOUTH_Y), (MOUTH_X, -12.0), (-MOUTH_X, -12.0)], -1.0, MOUTH_TOP)
    if var["window"]:
        for sign in (-1, 1):
            v, f = sector_prism(sign * TIP_X, sign, TIP_R + 0.2, 30.0, SILL - SKIN, 20.0)
            cf += [tuple(len(cv) + i for i in face) for face in f]
            cv += v
    cutter = new_obj(f"{name}_cut", bm_from(cv, cf), m, cut_coll)
    mod = ob.modifiers.new("cut", "BOOLEAN")
    mod.operation, mod.solver, mod.object = "DIFFERENCE", "EXACT", cutter
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    ob.modifiers.clear()
    old = ob.data
    ob.data = me
    bpy.data.meshes.remove(old)
    bpy.data.objects.remove(cutter, do_unlink=True)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.3), verts=bm.verts, edges=bm.edges)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(m_recess)
    for p in me.polygons:   # the mouth recess's faces a shade darker, so the opening reads in flat grey
        p.use_smooth = False
        if all(abs(me.vertices[i].co.x) <= MOUTH_X + 1e-3 and me.vertices[i].co.z <= MOUTH_TOP + 1e-3
               for i in p.vertices):
            p.material_index = 1
    return ob, tip


def bvh_of(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    t = BVHTree.FromBMesh(bm)
    bm.free()
    return t


RAY = Vector((0.0123, 0.0071, 1.0)).normalized()


def inside(bvh, p):
    hits, o = 0, Vector(p)
    for _ in range(40):
        loc = bvh.ray_cast(o, RAY)[0]
        if loc is None:
            break
        hits += 1
        o = loc + RAY * 1e-4
    return hits % 2 == 1


def vertical(bvh, x, y):
    """(top, bottom) of the hull over plan (x, y), None where the ray misses."""
    hit = bvh.ray_cast(Vector((x, -y, 50.0)), Vector((0, 0, -1)))[0]
    low = bvh.ray_cast(Vector((x, -y, -50.0)), Vector((0, 0, 1)))[0]
    return (hit.z, low.z) if hit is not None and low is not None else None


def thickness_at(bvh, x):
    best = 0.0
    for k in range(-500, 501):
        tb = vertical(bvh, x, k * 0.02)
        if tb:
            best = max(best, tb[0] - tb[1])
    return best


def measure(hull, bvh, details):
    bad, least = [], 9.0
    for what, (x, y, h) in interior_points():
        p = Vector(bl((x, y, h)))
        d = bvh.find_nearest(p)[3]
        ins = inside(bvh, p)
        least = min(least, d if ins else -d)
        if not ins or d < SKIN - 1e-4:
            bad.append(f"{what} ({x:+.2f}, {y:+.2f}, h {h:.2f}): {'inside' if ins else 'OUTSIDE'}, skin {d:.3f}")
    hv = [hull.matrix_world @ v.co for v in hull.data.vertices]
    allv = list(hv)
    for ob in details:
        allv += [ob.matrix_world @ v.co for v in ob.data.vertices]
    xmax = max(v.x for v in hv)
    plan_y = [-v.y for v in allv if v.z > 0.05]
    return {
        "span_m": round(xmax - min(v.x for v in hv), 3),
        "length_m": round(max(plan_y) - min(-v.y for v in hv), 3),
        "height_m": round(max(v.z for v in allv), 3),
        "hull_top_m": round(max(v.z for v in hv), 3),
        "belly_m": round(min(v.z for v in hv), 3),
        "wing_thickness_1m_from_tip_m": round(thickness_at(bvh, xmax - 1.0), 3),
        "wing_thickness_2m_from_tip_m": round(thickness_at(bvh, xmax - 2.0), 3),
        "least_skin_m": round(least, 3),
        "pokes": bad,
        "hull_faces": len(hull.data.polygons),
    }


def details(name, var, bvh, coll, m_dark, m_glass, m_ramp):
    obs = []
    n = 12
    for k, (x, y, h, r, ln) in enumerate(NOZZLES):
        ring_ = [(x + r * math.cos(2 * math.pi * a / n + math.pi / n), h + r * math.sin(2 * math.pi * a / n + math.pi / n))
                 for a in range(n)]
        v = [(px, y + t, pz) for t in (0.0, ln) for px, pz in ring_]
        f = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))] + [(a, (a + 1) % n, n + (a + 1) % n, n + a)
                                                                     for a in range(n)]
        obs.append(new_obj(f"{name}_pod{k}", bm_from(v, f), m_dark, coll))
    cx, cy, ax, ay, ch = CANOPY
    for side in (-1, 1):
        x0 = side * cx
        tops = [t[0] for t in (vertical(bvh, x0 + ax * u, cy + ay * w) for u in (-1, 0, 1) for w in (-1, 0, 1)) if t]
        base, apex = min(tops) - 0.05, max(tops) + ch
        rings, segs = 3, 10
        v = []
        for i in range(rings + 1):
            t = math.pi / 2 * i / rings
            for a in range(segs):
                g = 2 * math.pi * a / segs
                v.append((x0 + ax * math.cos(t) * math.cos(g), cy + ay * math.cos(t) * math.sin(g),
                          base + (apex - base) * math.sin(t)))
        f = [tuple(range(segs - 1, -1, -1))]
        for i in range(rings):
            for a in range(segs):
                f.append((i * segs + a, i * segs + (a + 1) % segs, (i + 1) * segs + (a + 1) % segs,
                          (i + 1) * segs + a))
        bm = bm_from(v, f)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
        obs.append(new_obj(f"{name}_canopy{side}", bm, m_dark, coll))
    hx, hy = RAMP["hinge"]
    fx, fy = RAMP["foot"]
    w, t = RAMP["width_m"] / 2, RAMP["thickness_m"]
    v = [(-w, hy, FLOOR), (w, hy, FLOOR), (w, fy, 0.0), (-w, fy, 0.0),
         (-w, hy, FLOOR - t), (w, hy, FLOOR - t), (w, fy + 0.6, 0.0), (-w, fy + 0.6, 0.0)]
    f = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    obs.append(new_obj(f"{name}_ramp", bm_from(v, f), m_ramp, coll))
    for lx, ly in LEGS:
        for side in (-1, 1):
            x = side * min(lx, var["half"] - 2.4) if lx > 10 else side * lx
            tb = vertical(bvh, x, ly)
            if not tb or tb[1] < 0.45:
                continue
            bot = tb[1]
            for (hw, z0, z1) in ((0.45, 0.0, 0.14), (0.18, 0.14, bot + 0.2)):
                v, f = prism([(x - hw, ly - hw), (x + hw, ly - hw), (x + hw, ly + hw), (x - hw, ly + hw)], z0, z1)
                obs.append(new_obj(f"{name}_leg{side}_{lx}", bm_from(v, f), m_dark, coll))
    if var["window"]:
        for sign in (-1, 1):
            nn = 24
            a = [(-WIN_HALF + 2 * WIN_HALF * i / nn) for i in range(nn + 1)]
            r = TIP_R + 0.21
            v = [(sign * TIP_X + sign * r * math.cos(t), r * math.sin(t), z) for z in (SILL, HEAD) for t in a]
            f = [(i, i + 1, nn + 2 + i, nn + 1 + i) for i in range(nn)]
            obs.append(new_obj(f"{name}_glass{sign}", bm_from(v, f), m_glass, coll))
    return obs


def ghost_rooms(coll, m):
    def cyl(name, cx, r, h0, h1, n=32):
        v = [(cx + r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n), h) for h in (h0, h1)
             for k in range(n)]
        f = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))] + [(k, (k + 1) % n, n + (k + 1) % n, n + k)
                                                                     for k in range(n)]
        new_obj(name, bm_from(v, f), m, coll)
    cyl("g_hall", 0.0, HALL_R, SLAB, HALL_APEX)
    new_obj("g_mouth", bm_from(*prism([(-MOUTH_X - WALL, MOUTH_Y), (MOUTH_X + WALL, MOUTH_Y),
                                        (MOUTH_X + WALL, -3.7), (-MOUTH_X - WALL, -3.7)], SLAB, MOUTH_TOP + ROOF)),
            m, coll)
    for side in (-1, 1):
        x0, x1 = sorted((side * COR_X[0], side * COR_X[1]))
        new_obj(f"g_cor{side}", bm_from(*prism([(x0, -COR_Y), (x1, -COR_Y), (x1, COR_Y), (x0, COR_Y)], SLAB,
                                                COR_TOP)), m, coll)
        cyl(f"g_tip{side}", side * TIP_X, TIP_R, SLAB, TIP_APEX)


VIEWS = {   # name: (location, rotation, ortho scale or None for perspective) in Blender coordinates (y north)
    "front": ((0.0, 60.0, 2.8), (math.pi / 2, 0.0, math.pi), 34.0),
    "side": ((-60.0, -0.25, 2.8), (math.pi / 2, 0.0, -math.pi / 2), 18.0),
    "back": ((0.0, -60.0, 2.8), (math.pi / 2, 0.0, 0.0), 34.0),
    "top": ((0.0, -0.25, 60.0), (0.0, 0.0, 0.0), 34.0),
    "hero": ((-21.0, 25.0, 11.0), None, None),
}
HERO_AIM = Vector((-1.2, -1.0, 1.6))
CROPS = {"front": "turnaround_1_front.png", "side": "turnaround_2_side.png", "back": "turnaround_3_back.png",
         "top": "turnaround_4_top.png"}


def pixels(path, w, h):
    img = bpy.data.images.load(str(path))
    sw, sh = img.size
    s = min(w / sw, h / sh)
    if abs(s - 1.0) > 1e-6:
        img.scale(max(1, int(sw * s)), max(1, int(sh * s)))
    iw, ih = img.size
    buf = np.empty(iw * ih * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    cell = np.zeros((h, w, 4), dtype=np.float32)
    cell[...] = BG
    y0, x0 = (h - ih) // 2, (w - iw) // 2
    cell[y0:y0 + ih, x0:x0 + iw] = buf.reshape(ih, iw, 4)
    bpy.data.images.remove(img)
    return cell


def over_bg(cell):
    a = cell[..., 3:4]
    out = cell * a + BG * (1 - a)
    out[..., 3] = 1.0
    return out


def save(arr, path):
    img = bpy.data.images.new(Path(path).stem, arr.shape[1], arr.shape[0])
    img.pixels.foreach_set(np.ascontiguousarray(arr, dtype=np.float32).ravel())
    img.filepath_raw, img.file_format = str(path), "PNG"
    img.save()
    bpy.data.images.remove(img)


def set_view(cam, view):
    loc, rot, scale = VIEWS[view]
    cam.location = loc
    if scale is None:
        cam.data.type, cam.data.lens = "PERSP", 35.0
        cam.rotation_euler = (HERO_AIM - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    else:
        cam.data.type, cam.data.ortho_scale = "ORTHO", scale
        cam.rotation_euler = rot


def render(scene, path):
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def label_scene():
    sc = bpy.data.scenes.new("labels")
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "FLAT"
    sc.display.shading.color_type = "SINGLE"
    sc.display.shading.single_color = (1.0, 1.0, 1.0)
    sc.render.film_transparent = True
    sc.render.resolution_percentage = 100
    sc.world = bpy.data.worlds.new("lw")
    cam = bpy.data.objects.new("lcam", bpy.data.cameras.new("lcam"))
    cam.data.type = "ORTHO"
    sc.collection.objects.link(cam)
    sc.camera = cam
    cu = bpy.data.curves.new("ltext", "FONT")
    cu.size, cu.align_y = 0.17, "CENTER"
    tx = bpy.data.objects.new("ltext", cu)
    sc.collection.objects.link(tx)
    return sc


def label(sc, text, w, h, path):
    cam, tx = sc.objects["lcam"], sc.objects["ltext"]
    sc.render.resolution_x, sc.render.resolution_y = w, h
    cam.data.ortho_scale = w / 100.0
    cam.location = (w / 200.0, h / 200.0, 10.0)
    tx.data.body = text
    tx.location = (0.12, h / 200.0, 0.0)
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True, scene=sc.name)
    a = pixels(path, w, h)[..., 3:4]
    out = BG * (1 - a) + np.array([0.92, 0.92, 0.92, 1.0], dtype=np.float32) * a
    out[..., 3] = 1.0
    return out


def main():
    out = Path(arg("--out"))
    cells = out / "cells"
    cells.mkdir(parents=True, exist_ok=True)
    crops = Path(arg("--crops", "D:/prime-art-raw/ship/v1/meshy_in"))
    hero_2d = Path(arg("--hero", "D:/prime-game-design/ideas/ship-components/2d/hero.jpg"))
    names = arg("--variants", ",".join(VARIANTS)).split(",")
    scene = bpy.context.scene
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light, sh.color_type = "STUDIO", "MATERIAL"
    sh.show_cavity = False
    sh.show_specular_highlight = False
    sh.show_object_outline = False
    sh.show_shadows = False
    scene.world = bpy.data.worlds.new("bg")
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.data.clip_end = 300.0
    scene.collection.objects.link(cam)
    scene.camera = cam
    ghost = bpy.data.collections.new("rooms")
    scene.collection.children.link(ghost)
    ghost_rooms(ghost, mat("room", (1.0, 1.0, 1.0)))
    cut_coll = bpy.data.collections.new("cutters")
    scene.collection.children.link(cut_coll)
    cut_coll.hide_render = True
    grey = mat("grey", (0.6, 0.6, 0.6))
    dark = mat("dark", (0.42, 0.42, 0.44))
    glass = mat("glass", (0.1, 0.12, 0.16))
    ramp = mat("ramp", (0.34, 0.34, 0.35))
    report, colls = {}, {}
    for name in names:
        var = VARIANTS[name]
        coll = bpy.data.collections.new(f"v{name}")
        scene.collection.children.link(coll)
        hull, tip = hull_object(f"hull_{name}", var, coll, grey, ramp, cut_coll)
        bvh = bvh_of(hull)
        obs = details(name, var, bvh, coll, dark, glass, ramp)
        meas = measure(hull, bvh, [o for o in obs if "ramp" not in o.name])
        meas["tip"] = [round(v, 3) for v in tip]
        meas["variant"] = var
        report[name] = meas
        colls[name] = coll
        print(f"BLOCKOUT {name}: {len(meas['pokes'])} interior points with less than {SKIN} m of skin"
              + (f", e.g. {meas['pokes'][:6]}" if meas["pokes"] else ""))
        print(f"BLOCKOUT {name} measures: " + json.dumps({k: v for k, v in meas.items() if k != "pokes"}))
    order = ("front", "side", "back", "top", "hero")
    W, H = 320, 180
    shots, ghosts = {}, {}
    for name in names:
        for c in colls.values():
            c.hide_render = True
        colls[name].hide_render = False
        ghost.hide_render = True
        shots[name] = {}
        for view in order:
            set_view(cam, view)
            scene.render.resolution_x, scene.render.resolution_y = (W, H)
            render(scene, cells / f"{name}_{view}.png")
            shots[name][view] = over_bg(pixels(cells / f"{name}_{view}.png", W, H))
        ghosts[name] = {}
        for view in ("top", "front"):
            set_view(cam, view)
            scene.render.resolution_x, scene.render.resolution_y = (640, 360)
            colls[name].hide_render, ghost.hide_render = False, True
            render(scene, cells / f"{name}_{view}_big.png")
            solid = over_bg(pixels(cells / f"{name}_{view}_big.png", 640, 360))
            colls[name].hide_render, ghost.hide_render = True, False
            render(scene, cells / "_mask.png")
            mask = pixels(cells / "_mask.png", 640, 360)[..., 3:4] * 0.3
            g = solid * (1 - mask) + np.array([1.0, 0.45, 0.1, 1.0], dtype=np.float32) * mask
            g[..., 3] = 1.0
            ghosts[name][view] = g
        colls[name].hide_render, ghost.hide_render = True, True
    lsc = label_scene()
    lab = cells / "_label.png"
    top_down = [label(lsc, "2D turnaround (approved): front, side, back, top; hero", 5 * W, 28, lab),
                np.concatenate([pixels(crops / CROPS[v], W, H) for v in order[:4]] + [pixels(hero_2d, W, H)], axis=1)]
    gl = []
    for name in names:
        m = report[name]
        text = (f"{name}{'  (tip windows)' if VARIANTS[name]['window'] else ''}   span {m['span_m']:.1f} m   "
                f"length {m['length_m']:.1f} m   height {m['height_m']:.2f} m   "
                f"wing 1 m from tip {m['wing_thickness_1m_from_tip_m']:.2f} m   least skin {m['least_skin_m']:.2f} m"
                f"   pokes {len(m['pokes'])}")
        top_down.append(label(lsc, text, 5 * W, 28, lab))
        top_down.append(np.concatenate([shots[name][v] for v in order], axis=1))
        gl.append(label(lsc, text.split("   wing")[0] + "   (rooms ghosted orange)", 1280, 28, lab))
        gl.append(np.concatenate([ghosts[name]["top"], ghosts[name]["front"]], axis=1))
    save(np.concatenate(top_down[::-1], axis=0), out / "sheet.png")
    save(np.concatenate(gl[::-1], axis=0), out / "ghost.png")
    for p in (lab, cells / "_mask.png"):
        p.unlink(missing_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    bpy.data.scenes.remove(lsc)
    for c in colls.values():
        c.hide_render = False
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "blockout.blend"))
    print(f"BLOCKOUT sheet {out / 'sheet.png'} ghost {out / 'ghost.png'}")


if __name__ == "__main__":
    main()
