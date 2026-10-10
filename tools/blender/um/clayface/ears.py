"""The clay face kit's ears: one small clay ear with a thumb dent, and the ears_hide and ears_tuck shape keys that
the worn hair's ear flag sets (faces/clay_hair.json).
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from .. import clay as cl
from .kit import EARS, EAR_HIDE, EAR_POS, EAR_SEG, EAR_TUCK
from .mesh import add_keys, bake, blob_bm, bm_object, cull_inside, static_piece


def build_ears(face, ctx, coll, spec=None):
    """Round C: the one small ear (EARS["small"]) on both sides, its centre `sink` inside the head's side at EAR_POS.
    Round D: spec (default EARS["small"]; EAR_VARIANTS for the B | C | D sheet) and the shape key ears_hide."""
    h = face.h
    E = dict(spec or EARS["small"])
    y, z = E.get("y", EAR_POS["y"]), ctx.eye_z + E.get("dz", EAR_POS["dz"])
    bm = bmesh.new()
    centres = {}
    shifts = {}
    bowls = {}
    for s in (1.0, -1.0):
        start = Vector((ctx.x + s * 0.4, y, z))
        loc, nrm, _, _ = ctx.bvh.ray_cast(start, Vector((-s, 0.0, 0.0)))
        xs = loc.x if loc is not None else ctx.x + s * 0.082
        c = Vector((xs - s * E["sink"], y, z))
        centres[s] = c
        # fixer: ears_tuck for this side: about the root (the skin point under the ear's centre) scaled, and the root
        # moved back and down along the side's surface
        y2, z2 = y + EAR_TUCK["back"], z - EAR_TUCK["down"]
        loc2, _n2, _, _ = ctx.bvh.ray_cast(Vector((ctx.x + s * 0.4, y2, z2)), Vector((-s, 0.0, 0.0)))
        xs2 = loc2.x if loc2 is not None else xs
        shifts[s] = (Vector((xs, y, z)), Vector((xs2, y2, z2)))
        out = E.get("out", 0.0)  # round D: round B's "out" (the ear turned out about z by out deg, its centre pushed out)
        rot = Matrix.Rotation(math.radians(-s * out), 3, "Z") if out else None
        if out:
            c = c + Vector((s * E["half"][0] * 0.25 * min(1.0, out / 28.0), 0.0, 0.0))
        seg, rings = EAR_SEG if E.get("dent") else (10, 6)
        part = blob_bm(c, E["half"], seg=seg, rings=rings, rot=rot)
        if E.get("dent"):  # the dent's centre on the undented surface, the ear's outward axis, its frame (pressed later)
            R3 = rot if rot is not None else Matrix.Identity(3)
            bowls[s] = (c.copy(), R3 @ Vector((s, 0.0, 0.0)), c + R3 @ Vector((s * E["half"][0], 0.0, E["dent"][2] * E["half"][2])), R3)
        tmp = bpy.data.meshes.new("tmp")
        part.to_mesh(tmp)
        part.free()
        bm.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
    # round C: 64 triangles for both ears (round B 110): the worst-case face (toothy, potato, big eyes, brush+goatee)
    # was 2,045 triangles with 110 + 140 for the ears and brows; the budget is under 2,000
    if not bowls:
        o, culled = static_piece(ctx, f"{h.id}_fb_ears", bm, [face.mats["skin"]], coll, sub=1, target=E.get("tris", 64),
                                 lumps=tuple(E.get("lumps", (0.0006, 60.0, 20))))
    else:
        # fixer 2: static_piece's steps with the thumb dent (dent= above), pressed into the subdivided ear and again
        # into the decimated one
        o = bm_object(f"{h.id}_fb_ears", bm, [face.mats["skin"]], coll)
        cl.lump(o, *tuple(E.get("lumps", (0.0006, 60.0, 20))))
        sm = o.modifiers.new("round", "SUBSURF")
        sm.levels = sm.render_levels = 1
        bake(o, keep=())
        culled = cull_inside(o, ctx)
        dep, rad, zo = E["dent"]
        hx, hy, hz = E["half"]
        mw0 = o.matrix_world
        inv0 = mw0.inverted()
        def press():
            """Every outer-face vertex inside the dent's rim (r < 1) no higher, along the ear's outward axis, than the
            rim's own height minus a parabolic bowl: rim - B (1 - r^2); a concave bowl with a crease at its rim."""
            mw0 = o.matrix_world
            inv0 = mw0.inverted()
            n = {"L": 0, "R": 0}
            for v in o.data.vertices:
                p = mw0 @ v.co
                s_ = 1.0 if p.x > ctx.x else -1.0
                c0, ax, _apex, R3 = bowls[s_]
                q = R3.inverted() @ (p - c0)
                if q.x * s_ <= 0.0:
                    continue
                r2 = (q.y / hy / rad) ** 2 + ((q.z / hz - zo) / rad) ** 2
                if r2 >= 1.0:
                    continue
                uy, uz = q.y / hy, q.z / hz
                if r2 > 1e-4:  # the dome's height at the rim point in this vertex's direction from the dent's centre
                    k = 1.0 / math.sqrt(r2)
                    rim = hx * math.sqrt(max(0.0, 1.0 - (uy * k) ** 2 - (zo + (uz - zo) * k) ** 2))
                else:
                    rim = hx * math.sqrt(max(0.0, 1.0 - rad * rad - zo * zo))
                want = rim - dep * (1.0 - r2)
                h = q.x * s_
                if h > want:
                    v.co = inv0 @ (p - ax * (h - want))
                    n["L" if s_ > 0 else "R"] += 1
            o.data.update()
            return n

        pressed = press()
        t = cl.tris(o.data)
        if t > E.get("tris", 64):
            dm = o.modifiers.new("dec", "DECIMATE")
            dm.ratio = E.get("tris", 64) / t
            bake(o, keep=())
        face.meta["ear_dent_vertices_final"] = press()  # the decimated ear pressed again (the bowl's floor kept)
        cl.smooth_shade(o.data)
        face.meta["ear_dent_vertices_dense"] = pressed
    face.meta["ears_culled_faces"] = culled
    if bowls:  # fixer 2: the bowl's depth as built (after the lumps, subdivision and decimation), unscaled
        from mathutils.bvhtree import BVHTree as _BVH
        mw0 = o.matrix_world
        vv = [mw0 @ v.co for v in o.data.vertices]
        tree = _BVH.FromPolygons(vv, [tuple(p.vertices) for p in o.data.polygons])
        bd = {}
        dep_, rad_, zo_ = E["dent"]
        for s_, (c0, ax, apex, R3) in bowls.items():
            rims = []
            for p in vv:
                if (p.x - ctx.x) * s_ <= 0:
                    continue
                q = R3.inverted() @ (p - c0)
                r2 = (q.y / E["half"][1] / rad_) ** 2 + ((q.z / E["half"][2] - zo_) / rad_) ** 2
                if q.x * s_ > 0 and 0.8 <= r2 <= 1.5:
                    rims.append((p - c0).dot(ax))
            rim = sum(rims) / len(rims) if rims else None
            hit = tree.ray_cast(apex + ax * 0.02, -ax)[0]
            bd["L" if s_ > 0 else "R"] = round((rim - (hit - c0).dot(ax)) * 1000.0, 2) if rim is not None and hit is not None else None
        face.meta["ear_bowl_mm"] = bd  # the mean rim height (vertices at 0.9 to 1.2 of the dent's radius) above the centre
    # round D: ears_hide folds each ear to EAR_HIDE["shrink"] of its size about its centre moved EAR_HIDE["inward"]
    # further into the head (every vertex inside the skin: face.meta["ears_hidden_min_depth_mm"] > 0)
    mw = o.matrix_world
    inv = mw.inverted()
    hid, depth, back = [], [], []
    for v in o.data.vertices:
        p = mw @ v.co
        s = 1.0 if p.x > ctx.x else -1.0
        c = centres[s]
        ci = c - Vector((s * EAR_HIDE["inward"], 0.0, 0.0))
        q = ci + (p - c) * EAR_HIDE["shrink"]
        depth.append(ctx.depth_inside(q))
        hid.append(inv @ q)
        r0, r1 = shifts[s]
        back.append(inv @ (r1 + (p - r0) * EAR_TUCK["scale"]))
    add_keys(o, {"ears_hide": hid, "ears_tuck": back}, None)
    face.meta["ears_tuck_root_move_mm"] = {("L" if s > 0 else "R"): [round(x * 1000, 2) for x in (v[1] - v[0])] for s, v in shifts.items()}
    face.meta["ears_hidden_min_depth_mm"] = round(min(depth) * 1000, 2)
    # units (the critic: 2.5 here against head.json's 4.47 read as a contradiction): the kit's numbers are UNSCALED (before
    # the head's x1.3); head.json "stands_out_mm" is measured on the baked x1.3 head with its clay lumps
    face.meta["ear"] = {"units": "mm, unscaled (before the head's x1.3 bake)", "half_mm": [round(v * 1000, 1) for v in E["half"]],
                        "tris": cl.tris(o.data),
                        "out_of_skin_mm": round((E["half"][0] - E["sink"]) * 1000, 1),
                        "out_of_skin_mm_x1.3": round((E["half"][0] - E["sink"]) * 1300, 2)}
    return face.add("ears", o, "ear")
