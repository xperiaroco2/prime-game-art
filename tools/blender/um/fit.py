"""Fit work: tucked bottoms, edge extension, the shoe collar, the seam probe and the seam metrics.

Rules learned in the final test: a bottom's lower edge must be below the shoes' top edge and a top's lower edge below
the bottom's upper edge; a bottom tucked into a shoe has its faces below the collar deleted and the rest pulled inside
(an overlap must be hidden geometry, not geometry that pokes through); a thin seam is closed by extending the outer
part's edge; seams are checked with rays, in the rest pose and in each pose, not with z-extents alone.
"""

import math

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from .util import world_points

SPINE = ("Hips", "Abdomen", "Torso", "Chest")


def extend_edge(obj, drop, band=0.012, column=0.25):
    """Rest pose. Move the lowest ring of a part (vertices within band of its lowest point, torso column only) down
    by drop metres: lengthens a jacket hem or a head's neck where the seam probe sees through a sliver."""
    mw = obj.matrix_world; inv = mw.inverted(); ox = obj.parent.matrix_world.translation.x
    pts = [(v, mw @ v.co) for v in obj.data.vertices]
    col = [(v, p) for v, p in pts if abs(p.x - ox) < column]
    lo = min(p.z for v, p in col)
    n = 0
    for v, p in col:
        if p.z < lo + band:
            v.co = inv @ (p - Vector((0.0, 0.0, drop))); n += 1
    obj.data.update()
    return {"drop_m": drop, "vertices_moved": n, "edge_was_m": round(lo, 3)}


def bvh_of(items):
    """BVH of the evaluated (posed) meshes in world space; owner[i] is the role of polygon i."""
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys, owner = [], [], []
    for role, o in items:
        ev = o.evaluated_get(dg); me = ev.to_mesh()
        off = len(verts)
        verts += [ev.matrix_world @ v.co for v in me.vertices]
        for p in me.polygons:
            polys.append(tuple(i + off for i in p.vertices)); owner.append(role)
        ev.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys), owner


def inside(bvh, p):
    loc, nrm, _, _ = bvh.find_nearest(p)
    return loc is not None and (p - loc).dot(nrm) < 0


def shoe_points(shoes):
    """World points along every edge of the shoe mesh (8 per edge): a low-poly shaft has only 6 to 8 vertices round
    its top, so vertices alone leave angular sectors with no collar point."""
    mw = shoes.matrix_world; vs = shoes.data.vertices
    pts = []
    for e in shoes.data.edges:
        a, b = mw @ vs[e.vertices[0]].co, mw @ vs[e.vertices[1]].co
        pts += [a.lerp(b, k / 8) for k in range(9)]
    return pts


def collar_heights(shoe_pts, centre, sectors=16, reach=0.13):
    """Highest shoe point per angular sector around a leg axis: the shoe's top edge (collar) all the way round."""
    top = [None] * sectors
    for p in shoe_pts:
        d = Vector((p.x - centre.x, p.y - centre.y))
        if d.length > reach:
            continue
        s = int((math.atan2(d.y, d.x) + math.pi) / (2 * math.pi) * sectors) % sectors
        top[s] = p.z if top[s] is None else max(top[s], p.z)
    return top


def sector_of(p, centre, sectors=16):
    return int((math.atan2(p.y - centre.y, p.x - centre.x) + math.pi) / (2 * math.pi) * sectors) % sectors


def tuck_cull(bottom, shoes, arm, margin=0.012, slack=0.006):
    """Rest pose. Per leg: if the bottom's shin vertices just under the shoe's collar are mostly inside the shoe, the
    bottom is tucked in, and every bottom face below the collar (per angular sector) minus margin is deleted. Those
    faces are hidden when they stay inside, and poke through the shoe wherever the shoe is slimmer (w1_ivy's boots)."""
    bvh, _ = bvh_of([("shoes", shoes)])
    fpts = shoe_points(shoes)
    me = bottom.data; mw = bottom.matrix_world; inv = mw.inverted()
    bpts = [mw @ v.co for v in me.vertices]
    res, kill = {}, set()
    for side, sgn in (("L", 1.0), ("R", -1.0)):
        c = arm.matrix_world @ arm.data.bones["Foot." + side].head_local
        top = collar_heights([p for p in fpts if p.x * sgn > 0], c)
        lo = min(t for t in top if t is not None)
        leg = [i for i, p in enumerate(bpts) if p.x * sgn > 0 and Vector((p.x - c.x, p.y - c.y)).length < 0.13]
        band = [i for i in leg if top[sector_of(bpts[i], c)] is not None
                and top[sector_of(bpts[i], c)] - 0.06 < bpts[i].z < top[sector_of(bpts[i], c)] - 0.01]
        ins = sum(1 for i in band if inside(bvh, bpts[i]))
        tucked = bool(band) and ins / len(band) > 0.5
        res[side] = {"collar_m": [round(lo, 3), round(max(t for t in top if t is not None), 3)], "band_vertices": len(band),
                     "inside_fraction": round(ins / len(band), 2) if band else None, "tucked": tucked}
        if tucked:
            kill |= {i for i in leg if top[sector_of(bpts[i], c)] is not None and bpts[i].z < top[sector_of(bpts[i], c)] - margin}
            # what stays below the collar (faces straddling the cut) is pulled at least `slack` inside the shoe, so
            # that the pose's slightly different skinning of trouser and shoe does not push it back out
            pulled = 0
            for i in leg:
                t = top[sector_of(bpts[i], c)]
                if i in kill or t is None or bpts[i].z >= t - 0.002:
                    continue
                loc, nrm, _, _ = bvh.find_nearest(bpts[i])
                if (bpts[i] - loc).dot(nrm) > -slack:
                    me.vertices[i].co = inv @ (loc - nrm * slack); pulled += 1
            res[side]["vertices_pulled_in"] = pulled
    bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
    gone = [f for f in bm.faces if all(v.index in kill for v in f.verts)]
    before = len(bm.faces)
    bmesh.ops.delete(bm, geom=gone, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.to_mesh(me); bm.free(); me.update()
    res["faces_removed"] = len(gone); res["faces_before"] = before; res["margin_m"] = margin; res["slack_m"] = slack
    return res


def zspan(obj):
    """Lowest and highest z (m) of the part's torso-column vertices (|x - rig x| < 0.25) in the current pose."""
    ox = obj.parent.matrix_world.translation.x
    pts = [p for p in world_points([obj]) if abs(p.x - ox) < 0.25]
    return min(p.z for p in pts), max(p.z for p in pts)


def seam_overlaps(head, top, bottom, shoes):
    """Rest-pose overlap in mm at the neck, waist and ankle seams (negative = a gap you can see through)."""
    h, t, b, f = zspan(head), zspan(top), zspan(bottom), zspan(shoes)
    return {"neck_mm": round((t[1] - h[0]) * 1000, 1), "waist_mm": round((b[1] - t[0]) * 1000, 1),
            "ankle_mm": round((f[1] - b[0]) * 1000, 1)}


def rest_edges(arm, parts):
    """Rest-pose seam heights the probe aims at: head, top and bottom spans, each foot bone and shoe collar."""
    h, t, b = zspan(parts["head"]), zspan(parts["top"]), zspan(parts["bottom"])
    edges = {"head_lo": h[0], "top_hi": t[1], "top_lo": t[0], "bottom_hi": b[1], "bottom_lo": b[0]}
    fpts = shoe_points(parts["shoes"])
    for side, sgn in (("L", 1.0), ("R", -1.0)):
        c = arm.matrix_world @ arm.data.bones["Foot." + side].head_local
        edges["foot_" + side] = c.z
        top = [x for x in collar_heights([p for p in fpts if p.x * sgn > 0], c) if x is not None]
        edges["collar_" + side] = max(top); edges["collar_lo_" + side] = min(top)
    return edges


def bone_ray_points(arm, bone, z_rest):
    """Points on a bone's rest axis at world rest height z (extrapolated), mapped to the current pose, plus a
    function giving the posed world direction for an angle around the bone axis."""
    mw = arm.matrix_world; b = arm.data.bones[bone]; pb = arm.pose.bones[bone]
    h, t = mw @ b.head_local, mw @ b.tail_local
    k = (z_rest - h.z) / (t.z - h.z) if abs(t.z - h.z) > 1e-6 else 0.0
    p_rest = h.lerp(t, k)
    local = b.matrix_local.inverted() @ (mw.inverted() @ p_rest)
    p = mw @ (pb.matrix @ local)
    rot = (mw.to_3x3() @ pb.matrix.to_3x3())
    return p, lambda a: (rot @ Vector((math.cos(a), 0.0, math.sin(a)))).normalized()


def probe(arm, parts, rest_edges, tucked, dirs=36, step=0.004):
    """Horizontal-ish rays aimed at the bone axis around each seam, in the current pose. A ray that first hits a
    back face, or nothing, looks through a gap (see_through). At a tucked ankle, a ray whose first hit is the
    bottom with the shoe surface within 15 mm behind it is a poke-through."""
    items = list(parts.items())
    bvh, owner = bvh_of(items)
    fbvh, _ = bvh_of([("shoes", parts["shoes"])])
    out = {}
    e = rest_edges
    bands = {"neck": ("Neck", min(e["head_lo"], e["top_hi"]) - 0.01, max(e["head_lo"], e["top_hi"]) + 0.01),
             "waist": (None, min(e["top_lo"], e["bottom_hi"]) - 0.01, max(e["top_lo"], e["bottom_hi"]) + 0.01)}
    for side in ("L", "R"):
        if tucked.get(side):
            bands["ankle_" + side] = ("LowerLeg." + side, e["foot_" + side] + 0.05, e["collar_lo_" + side] - 0.004)  # where the shoe must be outermost
        else:
            bands["ankle_" + side] = ("LowerLeg." + side, min(e["bottom_lo"], e["collar_" + side]) - 0.01,
                                      max(e["bottom_lo"], e["collar_" + side]) + 0.01)
    for name, (bone, z0, z1) in bands.items():
        n = st = poke = 0
        ex = {}
        z = z0
        while z <= z1 + 1e-9:
            bn = bone
            if bn is None:  # the spine bone whose rest span holds z
                spans = [(s, (arm.matrix_world @ arm.data.bones[s].head_local).z, (arm.matrix_world @ arm.data.bones[s].tail_local).z) for s in SPINE]
                bn = next((s for s, a, b in spans if a <= z < b), min(spans, key=lambda s: min(abs(z - s[1]), abs(z - s[2])))[0])
            c, dirf = bone_ray_points(arm, bn, z)
            for j in range(dirs):
                d = dirf(2 * math.pi * j / dirs)
                o = c - d * 0.5
                loc, nrm, idx, dist = bvh.ray_cast(o, d, 0.55)
                n += 1
                if loc is None or nrm.dot(d) > 0:
                    st += 1
                    key = "miss" if loc is None else "back:" + owner[idx]
                    ex.setdefault(key, []).append((round(z, 3), round(360.0 * j / dirs)))
                elif name.startswith("ankle") and tucked.get(name[-1]) and owner[idx] == "bottom":
                    floc, _, _, fdist = fbvh.ray_cast(o, d, 0.55)
                    if floc is not None and fdist - dist < 0.015:
                        poke += 1
                        ex.setdefault("poke", []).append((round(z, 3), round(360.0 * j / dirs)))
            z += step
        out[name] = {"rays": n, "see_through": st}
        if ex:  # where they are: kind -> (rest height, angle round the bone; 0 = the bone's +X side) samples
            out[name]["where"] = {k: v[:: max(1, len(v) // 6)][:6] for k, v in ex.items()}
        if name.startswith("ankle") and tucked.get(name[-1]):
            out[name]["poke_through"] = poke
    return out


def seam_gaps(part, others):
    """Distance (mm, posed) from each open-edge vertex of part to the nearest surface of the other parts."""
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys = [], []
    for o in others:
        ev = o.evaluated_get(dg); me = ev.to_mesh()
        off = len(verts)
        verts += [ev.matrix_world @ v.co for v in me.vertices]
        polys += [tuple(i + off for i in p.vertices) for p in me.polygons]
        ev.to_mesh_clear()
    bvh = BVHTree.FromPolygons(verts, polys)
    ev = part.evaluated_get(dg); me = ev.to_mesh()
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=2e-6)  # flat-shaded imports split every vertex; weld first
    bverts = {v for e in bm.edges if e.is_boundary for v in e.verts}
    d = []
    for v in bverts:
        p = ev.matrix_world @ v.co
        hit = bvh.find_nearest(p)
        d.append(hit[3] * 1000 if hit[0] is not None else 999.0)
    bm.free(); ev.to_mesh_clear()
    d.sort()
    if not d:
        return {"open_vertices": 0}
    return {"open_vertices": len(d), "median_mm": round(d[len(d) // 2], 1), "p95_mm": round(d[int(len(d) * 0.95)], 1),
            "max_mm": round(d[-1], 1)}
