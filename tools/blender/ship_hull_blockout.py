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
Variants E-G (the arrowhead, 2026-10-22): the tip rooms moved back into the rear corners (tip_c), the corridors
straight boxes along the diagonal from the hall's wall to them, the tip at the rear corner (tip_y), the stern moved
back (stern_y) so the top view's proportions approach the 2D's; the checks, legs and ghosts follow the rooms.
Variants H-I (the true triangle): the trail edge straight across, level with the tips; I with a pointed nose.
Every room's outer surface (ship.toml: the clear sizes plus the walls, the roofs and the slabs) is sampled and must
lie inside the hull with at least SKIN of hull around it; the mouth's own opening is the only exception.

    blender -b --factory-startup --python ship_hull_blockout.py -- --out <dir> [--variants A,B,C,D]
            [--crops <dir>] [--hero <jpg>] [--no-render]

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
    # The arrowhead (2026-10-22): the tip rooms moved back into the rear corners (the hall stays at the centre), the
    # corridors run straight along the diagonal from the hall's wall to them, the lead edge runs straight from the
    # nose to a tip at the rear corner and the trail edge near-straight from the tip in to a stern moved back.
    # Optional keys: tip_c the tip rooms' plan centre (x, y), tip_y the tip's plan y (else through LEAD_PIVOT),
    # nose_y the nose edge's y, nose_x its half width, stern_y the stern face's y (the stern block, the spine's rear and the pods move with
    # it), trail (x, h) the trail edge's stern corner.
    "E": {"half": 15.0, "tip_h": 3.25, "window": False, "tip_c": (8.3, 2.5), "tip_y": 4.4, "nose_y": -7.1,
          "stern_y": 8.8, "trail": (4.4, 2.6)},
    "F": {"half": 15.0, "tip_h": 3.25, "window": False, "tip_c": (8.3, 4.0), "tip_y": 5.7, "nose_y": -7.1,
          "stern_y": 10.2, "trail": (4.4, 2.6)},
    "G": {"half": 13.75, "tip_h": 3.3, "window": False, "tip_c": (8.3, 4.0), "tip_y": 5.4, "nose_y": -8.6,
          "stern_y": 10.2, "trail": (4.4, 2.6)},
    # The true triangle (2026-10-22): the trail edge straight across, level with the tips (a blunt back face over
    # the rear rooms, thinning out to the tips); only the nozzle pods stick out behind it. trail (x, h): the back
    # edge's corner outboard of the tip room, at stern_y - 0.2. I: the nose edge narrowed to the mouth's width plus
    # its walls and skin (nose_x), on the lead edge's line, so the nose comes to a point.
    "H": {"half": 15.0, "tip_h": 3.25, "window": False, "tip_c": (8.3, 4.0), "tip_y": 6.1, "nose_y": -7.1,
          "stern_y": 6.4, "trail": (10.6, 3.6)},
    "I": {"half": 15.0, "tip_h": 3.25, "window": False, "tip_c": (8.3, 4.0), "tip_y": 6.1, "nose_y": -7.67,
          "nose_x": MOUTH_X + WALL + SKIN, "stern_y": 6.4, "trail": (10.6, 3.6)},
    # Rounded tips on F's outline (2026-10-22): tip_r the tip's plan radius (an arc tangent to the lead and trail
    # edges, the corner pushed out along the lead edge so the span stays), tip_e the arc's half thickness about the
    # edge's height, lip the radius of a rounded lip along the arc and both edges (the edge seen end-on is a half
    # round 2 * lip thick), smooth the hull smooth-shaded (normals smooth below SMOOTH_DEG, weighted by face area).
    "J": {"half": 15.0, "tip_h": 3.25, "window": False, "tip_c": (8.3, 4.0), "tip_y": 5.7, "nose_y": -7.1,
          "stern_y": 10.2, "trail": (4.4, 2.6), "tip_r": 1.5, "tip_e": 0.15},
    "K": {"half": 15.0, "tip_h": 3.25, "window": False, "tip_c": (8.3, 4.0), "tip_y": 5.7, "nose_y": -7.1,
          "stern_y": 10.2, "trail": (4.4, 2.6), "tip_r": 3.0, "tip_e": 0.15},
    "L": {"half": 15.0, "tip_h": 3.25, "window": False, "tip_c": (8.3, 4.0), "tip_y": 5.7, "nose_y": -7.1,
          "stern_y": 10.2, "trail": (4.4, 2.6),
          "tip_r": 3.0, "lip": 0.18, "smooth": True},
}
SMOOTH_DEG = 30.0


def tip_c(var):
    return var.get("tip_c", (TIP_X, 0.0))


def stern_shift(var):
    return var.get("stern_y", STERN_Y) - STERN_Y


def corridor_frame(var):
    """The corridor's axis from the hall's centre to the east tip room's: (unit along, unit across, s0, s1), the box
    running from s0 (inside the hall's wall) to s1 (inside the tip room's wall), as COR_X does on the x axis."""
    cx, cy = tip_c(var)
    d = math.hypot(cx, cy)
    u = (cx / d, cy / d)
    return u, (-u[1], u[0]), COR_X[0], d - (TIP_X - COR_X[1])
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


def _unit(x, y):
    n = math.hypot(x, y)
    return x / n, y / n


def rounded_tip(var, nose, tip, trail, n=10):
    """The tip as a plan arc of radius tip_r tangent to the lead edge (nose -> corner) and the trail edge (corner ->
    trail): the corner is pushed out along the lead edge until the arc reaches x = half again. Each arc point is a
    pair at its height +- tip_e or, with lip, a half round of radius lip whose outer face is the outline, and the lip
    runs on along both edges. Returns (points, the arc's outermost point)."""
    r, half = var["tip_r"], var["half"]
    vx, vy = tip[0], tip[1]
    for _ in range(6):
        a, b = _unit(vx - nose[0], vy - nose[1]), _unit(trail[0] - vx, trail[1] - vy)
        u1, u2 = (-a[0], -a[1]), b
        th = math.acos(max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1])))
        d = r / math.tan(th / 2)
        bis = _unit(u1[0] + u2[0], u1[1] + u2[1])
        c = (vx + bis[0] * r / math.sin(th / 2), vy + bis[1] * r / math.sin(th / 2))
        t1, t2 = (vx + u1[0] * d, vy + u1[1] * d), (vx + u2[0] * d, vy + u2[1] * d)
        p1, p2 = math.atan2(t1[1] - c[1], t1[0] - c[0]), math.atan2(t2[1] - c[1], t2[0] - c[0])
        sweep = (p2 - p1 + math.pi) % (2 * math.pi) - math.pi     # the short way round, through the corner's side
        arc = [(c[0] + r * math.cos(p1 + sweep * k / n), c[1] + r * math.sin(p1 + sweep * k / n)) for k in range(n + 1)]
        gap = half - max(x for x, _ in arc)
        if abs(gap) < 1e-4:
            break
        vx, vy = vx + gap, vy + gap * a[1] / a[0]
    lead_len, trail_len = math.hypot(vx - nose[0], vy - nose[1]), math.hypot(trail[0] - vx, trail[1] - vy)
    h1 = nose[2] + (tip[2] - nose[2]) * (lead_len - d) / lead_len
    h2 = tip[2] + (trail[2] - tip[2]) * d / trail_len
    edge = []   # (plan x, y, h, outward unit)
    for k, (x, y) in enumerate(arc):
        edge.append((x, y, h1 + (h2 - h1) * k / n, _unit(x - c[0], y - c[1])))
    out = []
    lip = var.get("lip")
    if lip:
        na, nb = (a[1], -a[0]), (b[1], -b[0])     # the lead edge's outward normal (forward), the trail edge's (back)
        for f in (0.15, 0.35, 0.55, 0.75, 0.9):
            x, y = nose[0] + (t1[0] - nose[0]) * f, nose[1] + (t1[1] - nose[1]) * f
            edge.append((x, y, nose[2] + (h1 - nose[2]) * f, na))
            x, y = t2[0] + (trail[0] - t2[0]) * f, t2[1] + (trail[1] - t2[1]) * f
            edge.append((x, y, h2 + (trail[2] - h2) * f, nb))
        for x, y, h, (ox, oy) in edge:
            for deg in range(-90, 91, 30):
                g = math.radians(deg)
                out.append((x - ox * lip * (1 - math.cos(g)), y - oy * lip * (1 - math.cos(g)), h + lip * math.sin(g)))
    else:
        e = var.get("tip_e", 0.15)
        for x, y, h, _ in edge:
            out += [(x, y, h + e), (x, y, h - e)]
    far = max(edge, key=lambda q: q[0])
    return out, (far[0], far[1], far[2])


def design_points(var):
    half, tip_h = var["half"], var["tip_h"]
    tip_y = var.get("tip_y", LEAD_PIVOT[1] + LEAD_SLOPE * (half - LEAD_PIVOT[0]))
    tip = (half, tip_y, tip_h)
    ds = stern_shift(var)
    spine = SPINE[:-1] + [(SPINE[-1][0] + ds, SPINE[-1][1])]
    tx, th = var.get("trail", (TRAIL_END[0], TRAIL_END[2]))
    nose = (var.get("nose_x", NOSE[0]), var.get("nose_y", NOSE[1]), NOSE[2])
    trail = (tx, TRAIL_END[1] + ds, th)
    pts = [(SPINE_X, y, z) for y, z in spine] + [nose, trail]
    if "tip_r" in var:
        edge, tip = rounded_tip(var, nose, tip, trail)
        pts += edge
    else:
        pts.append(tip)
    pts += [(x, STERN_Y + ds, z) for x, z in STERN]
    cx, cy = tip_c(var)
    pts += ring(0.0, 0.0, HALL_R + 0.3, BELLY) + ring(cx, cy, TIP_R + 0.25, BELLY)
    pts += [(MOUTH_X + WALL + 0.3, MOUTH_Y - 0.2, BELLY)]
    if var["window"]:   # the room's cover: the wing steps down beyond it to a tip under the sill
        pts += ring(TIP_X, 0.0, TIP_R + 0.25, TIP_RIM + 0.25, a0=-90.0, a1=90.0)
    return mirrored([p for p in pts if p[0] >= -1e-6]), tip


def interior_points(var):
    """(what, plan point) of every room's outer surface: walls, ceilings, crowns and slab bottoms; the tip rooms and
    the corridors where the variant puts them."""
    pts = []
    tcx, tcy = tip_c(var)
    u, n, s0, s1 = corridor_frame(var)
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
        s = s0
        while s <= s1 + 1e-6:
            for w in (-COR_Y, COR_Y):
                for h in (SLAB, 1.7, COR_TOP):
                    pts.append(("corridor", (side * (s * u[0] + w * n[0]), s * u[1] + w * n[1], h)))
            for w in (-COR_Y, 0.0, COR_Y):
                pts.append(("corridor roof", (side * (s * u[0] + w * n[0]), s * u[1] + w * n[1], COR_TOP)))
            s += 0.3
        for d in range(0, 360, 5):
            c, s = math.cos(math.radians(d)), math.sin(math.radians(d))
            for h in (SLAB, SILL, HEAD, TIP_RIM):
                pts.append(("tip wall", (side * (tcx + TIP_R * c), tcy + TIP_R * s, h)))
            for rr in (0.6, 1.2, 1.8):
                pts.append(("tip roof", (side * (tcx + rr * c), tcy + rr * s,
                                         TIP_APEX - (TIP_APEX - TIP_RIM) * rr / TIP_R)))
                pts.append(("tip slab", (side * (tcx + rr * c), tcy + rr * s, SLAB)))
        pts.append(("tip crown", (side * tcx, tcy, TIP_APEX)))
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
    if var.get("smooth"):   # smooth normals, sharp edges above SMOOTH_DEG, weighted by face area; no subdivision
        for p in me.polygons:
            p.use_smooth = True
        me.set_sharp_from_angle(angle=math.radians(SMOOTH_DEG))
        wn = ob.modifiers.new("wn", "WEIGHTED_NORMAL")
        wn.mode, wn.weight, wn.keep_sharp = "FACE_AREA", 50, True
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
    for k in range(-700, 701):
        tb = vertical(bvh, x, k * 0.02)
        if tb:
            best = max(best, tb[0] - tb[1])
    return best


def measure(hull, bvh, details, var):
    bad, least = [], 9.0
    for what, (x, y, h) in interior_points(var):
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
    ds = stern_shift(var)
    tcx, tcy = tip_c(var)
    for k, (x, y, h, r, ln) in enumerate(NOZZLES):
        y += ds
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
        if lx > 10:   # the wing leg: outboard of the tip room, level with it
            lx, ly = min(tcx + (lx - TIP_X), var["half"] - 2.4), tcy + ly
        elif ly > 0:  # the rear leg moves back with the stern
            ly += ds
        for side in (-1, 1):
            x = side * lx
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


def ghost_rooms(name, var, coll, m):
    def cyl(gname, cx, cy, r, h0, h1, n=32):
        v = [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n), h) for h in (h0, h1)
             for k in range(n)]
        f = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))] + [(k, (k + 1) % n, n + (k + 1) % n, n + k)
                                                                     for k in range(n)]
        new_obj(gname, bm_from(v, f), m, coll)
    cyl(f"g{name}_hall", 0.0, 0.0, HALL_R, SLAB, HALL_APEX)
    new_obj(f"g{name}_mouth", bm_from(*prism([(-MOUTH_X - WALL, MOUTH_Y), (MOUTH_X + WALL, MOUTH_Y),
                                               (MOUTH_X + WALL, -3.7), (-MOUTH_X - WALL, -3.7)], SLAB,
                                              MOUTH_TOP + ROOF)), m, coll)
    tcx, tcy = tip_c(var)
    u, n, s0, s1 = corridor_frame(var)
    for side in (-1, 1):
        box = [(side * (s * u[0] + w * n[0]), s * u[1] + w * n[1]) for s, w in
               ((s0, -COR_Y), (s1, -COR_Y), (s1, COR_Y), (s0, COR_Y))]
        new_obj(f"g{name}_cor{side}", bm_from(*prism(box, SLAB, COR_TOP)), m, coll)
        cyl(f"g{name}_tip{side}", side * tcx, tcy, TIP_R, SLAB, TIP_APEX)


VIEWS = {   # name: (location, rotation, ortho scale or None for perspective) in Blender coordinates (y north)
    "front": ((0.0, 60.0, 2.8), (math.pi / 2, 0.0, math.pi), 34.0),
    "side": ((-60.0, -1.5, 2.8), (math.pi / 2, 0.0, -math.pi / 2), 23.0),
    "back": ((0.0, -60.0, 2.8), (math.pi / 2, 0.0, 0.0), 34.0),
    "top": ((0.0, -1.5, 60.0), (0.0, 0.0, 0.0), 40.0),
    "hero": ((-24.0, 28.0, 13.0), None, None),
}
HERO_AIM = Vector((-1.2, -2.0, 1.6))
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


def set_view(cam, view, tip=None):
    if view == "tipzoom":   # a three-quarter close-up of the east wing tip, from ahead, outboard and above
        aim = Vector(bl(tip)) + Vector((-0.8, 0.0, 0.0))
        cam.location = aim + Vector((6.0, 9.0, 8.0))
        cam.data.type, cam.data.lens = "PERSP", 35.0
        cam.rotation_euler = (aim - cam.location).to_track_quat("-Z", "Y").to_euler()
        return
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
    m_room = mat("room", (1.0, 1.0, 1.0))
    ghost = {}
    for name in names:   # each variant's rooms where it puts them
        ghost[name] = bpy.data.collections.new(f"rooms_{name}")
        scene.collection.children.link(ghost[name])
        ghost_rooms(name, VARIANTS[name], ghost[name], m_room)
        ghost[name].hide_render = True
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
        meas = measure(hull, bvh, [o for o in obs if "ramp" not in o.name], var)
        meas["tip"] = [round(v, 3) for v in tip]
        meas["variant"] = var
        meas["tip_radius_m"] = var.get("tip_r", 0.0)
        meas["edge_thickness_m"] = round(2 * var["lip"] if "lip" in var else 2 * var.get("tip_e", 0.0), 3)
        report[name] = meas
        colls[name] = coll
        print(f"BLOCKOUT {name}: {len(meas['pokes'])} interior points with less than {SKIN} m of skin"
              + (f", e.g. {meas['pokes'][:6]}" if meas["pokes"] else ""))
        print(f"BLOCKOUT {name} measures: " + json.dumps({k: v for k, v in meas.items() if k != "pokes"}))
    if "--no-render" in sys.argv:   # the numbers alone (a quick fit check)
        (out / "report.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
        return
    order = ("front", "side", "back", "top", "hero", "tipzoom")
    W, H = 320, 180
    shots, ghosts = {}, {}
    for name in names:
        for c in colls.values():
            c.hide_render = True
        colls[name].hide_render = False
        shots[name] = {}
        for view in order:
            set_view(cam, view, report[name]["tip"])
            scene.render.resolution_x, scene.render.resolution_y = (W, H)
            render(scene, cells / f"{name}_{view}.png")
            shots[name][view] = over_bg(pixels(cells / f"{name}_{view}.png", W, H))
        ghosts[name] = {}
        for view in ("top", "front"):
            set_view(cam, view)
            scene.render.resolution_x, scene.render.resolution_y = (640, 360)
            colls[name].hide_render, ghost[name].hide_render = False, True
            render(scene, cells / f"{name}_{view}_big.png")
            solid = over_bg(pixels(cells / f"{name}_{view}_big.png", 640, 360))
            colls[name].hide_render, ghost[name].hide_render = True, False
            render(scene, cells / "_mask.png")
            mask = pixels(cells / "_mask.png", 640, 360)[..., 3:4] * 0.3
            g = solid * (1 - mask) + np.array([1.0, 0.45, 0.1, 1.0], dtype=np.float32) * mask
            g[..., 3] = 1.0
            ghosts[name][view] = g
        colls[name].hide_render, ghost[name].hide_render = True, True
    lsc = label_scene()
    lab = cells / "_label.png"
    blank = np.zeros((H, W, 4), dtype=np.float32)
    blank[...] = BG
    top_down = [label(lsc, "2D turnaround (approved): front, side, back, top; hero   (last column: a close-up of the"
                      " east wing tip)", 6 * W, 28, lab),
                np.concatenate([pixels(crops / CROPS[v], W, H) for v in order[:4]] + [pixels(hero_2d, W, H), blank],
                               axis=1)]
    gl = []
    for name in names:
        m = report[name]
        var = VARIANTS[name]
        tag = "  (tip windows)" if var["window"] else ""
        if "tip_r" in var:
            tag += f"  tip r {var['tip_r']:.1f} m, edge {m['edge_thickness_m']:.2f} m" + (", smooth" if var.get("smooth")
                                                                                         else "")
        elif "tip_c" in var:
            tag += "  tip rooms at ({:.1f}, {:.1f})".format(*var["tip_c"])
        elif len(names) > 1 and any("tip_c" in VARIANTS[o] for o in names):
            tag += "  (last round, reference)"
        text = (f"{name}{tag}   span {m['span_m']:.1f} m   "
                f"length {m['length_m']:.1f} m   height {m['height_m']:.2f} m   "
                f"wing 1 m from tip {m['wing_thickness_1m_from_tip_m']:.2f} m   least skin {m['least_skin_m']:.2f} m"
                f"   pokes {len(m['pokes'])}")
        top_down.append(label(lsc, text, 6 * W, 28, lab))
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
