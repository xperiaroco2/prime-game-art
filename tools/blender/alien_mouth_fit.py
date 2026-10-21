"""M19 (art #196, brief UPDATE 38): the AI mouth route. Fits AI-made lip forms (Meshy multi-image to 3D of GPT Image
views of the pout mp1's lips) onto our mouth socket. Opens a kit's export/alien_character.blend (read only) and writes
<out>/<export-name>/ (never over its input). Two modes:

- the grid (M19, without --replace): the same kit plus, per shape of --ai ({"rest": GLB, "A": GLB}), two pout
  variants as grid nodes lipvar_<variant>_pout_<shape> (the names godot/alien/m12_shots.gd's "vgrid" shows):
  `aia` (the AI mesh itself) and `aib` (a copy of our piece whose lip vertices follow the aligned AI surface by
  wrap_weight, a Shrinkwrap to the nearest surface point; the parts under the skin and our cup stay, and the AI form
  it targets has no cup joined yet); with --also KEY=BLEND, that kit's own mouth_pout_<shape> as
  lipvar_<KEY>_pout_<shape>;
- --replace (M20, brief UPDATE 42, the hybrid pout the engineer picked): the AI forms of the closed shapes ({"rest":
  GLB, "M": GLB, "small": GLB}) become the kit's own mouth_pout_rest / _M / _small (the parametric pieces removed;
  the open shapes A, E, O stay ours); the skin's pout contact (Body's TEXCOORD_6.u, alien_m12.mouth2_contact) is
  rebuilt from the new rest; each piece's AO and its jaw weight (COLOR_0.a; G.jaw_closed below the lip line); the
  provenance of each piece (ai_generated, the Meshy task, the batch files, from the generation.json beside each GLB)
  in character.json's `m20`. M20b (brief UPDATE 44, PR #260's review): each form put on its own best mirror plane
  before the mirror (centre_plane), mirrored at full resolution and then decimated symmetrically, its middle band and
  lip line smoothed in depth (smooth_bands), the lower lip's central groove filled (fill_cleft); the skin's pout contact rebuilt with the skin under the form touching it
  (closed_contact); M's width and depth (FIT["xy_scale"]).

The fit of an `aia` form (both modes): imported, aligned (alien_mouth_fit_geom.align: one uniform scale to our
piece's lip width, centred on x = 0; a closed shape by its lip line (seam_z) on ours, an open one by its box's middle
height, which on M19's A left the AI ring 79.5 mm tall against our 71.2), its flat back seated on the skin
(FIT["seat"] "back"); its mirror error measured, then decimated to FIT["budget_tris"] and made symmetric (its -x half
mirrored; a second pass when the mirror took it over the budget); its back pushed under the skin and curved under
(taper_back; --replace adds corner_sink at the thin ends); on A the deep front-facing floor of its opening removed
and our dark cup joined; on small the deep front-facing faces of its parting get alien_mouth_inner. Our materials
(alien_lip_pout, alien_mouth_inner) on every variant; the kit's other pieces and the Body's other layers untouched.
alien_mouths.py and alien_lips_geom.py are only read (through alien_m12). Report: <out>/<export-name>/fit.json; log
lines "M19 ..." / "M20 ...".

    tools/runner/blender.py run_script("alien_mouth_fit.py", ["--kit", <kit/export>, "--out", <M20>, "--replace",
                                       "--ai", '{"rest": "...glb", "M": "...glb", "small": "...glb"}'])
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_eyes as AE  # noqa: E402
import alien_m6 as M6  # noqa: E402
import alien_m12 as M12  # noqa: E402
import alien_mouth_fit_geom as G  # noqa: E402
import export_glb  # noqa: E402

LIP = "alien_lip_pout"
CLOSED = ("rest", "M", "small")  # the closed shapes, aligned by their lip line (M20: the kit's AI pieces)
INNER = "alien_mouth_inner"
WRAP_ROUNDS = 3  # aib: shrinkwrap rounds with a relax between
OPENING = (0.32, 0.30)  # aia's A: the floor is looked for within these shares of the width and height round the centre
INNER_DEPTH = 0.45  # aia's A: a front-facing face deeper than this share of the form's depth is the opening's floor


def log(*a):
    print("M19", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--kit", required=True, help="the input kit's export folder (M15's or later)")
    p.add_argument("--out", required=True, help="the output folder; the kit goes into <out>/<export-name>")
    p.add_argument("--export-name", default="export")
    p.add_argument("--ai", required=True, help='JSON {"rest": GLB, "A": GLB}: the AI forms per pout shape')
    p.add_argument("--also", action="append", default=[], help="KEY=BLEND: that kit's pout pieces as lipvar_KEY_*")
    p.add_argument("--fit", default="", help="JSON merged over alien_mouth_fit_geom.FIT")
    p.add_argument("--no-bake", action="store_true")
    p.add_argument("--replace", action="store_true", help="M20: the AI forms become the kit's closed pout pieces")
    p.add_argument("--orm-sss", default="", help="--replace: the skin's orm_sss.png for the GLB's SSS route check")
    return p.parse_args(argv)


def local_co(ob) -> np.ndarray:
    """The mesh's own coordinates: the Mouth socket's space for a piece (parented with an identity basis), and the
    frame alien_mouth_fit_geom names (x across, -y the front, z up) for a form before it is attached."""
    return np.array([tuple(v.co) for v in ob.data.vertices])


def lip_mask(ob) -> np.ndarray:
    """Per vertex: whether a face of a lip material uses it."""
    m = np.zeros(len(ob.data.vertices), dtype=bool)
    for f in ob.data.polygons:
        if ob.material_slots[f.material_index].material.name.startswith("alien_lip"):
            m[list(f.vertices)] = True
    return m


def import_form(path: Path, name: str):
    """The AI GLB's meshes joined into one object with its transforms applied (world space, Blender's axes)."""
    before = set(bpy.data.objects)
    res = bpy.ops.import_scene.gltf(filepath=str(path))
    if res != {"FINISHED"}:
        raise SystemExit(f"import {path}: {res}")
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    if not meshes:
        raise SystemExit(f"{path}: no mesh")
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.parent = None
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for o in new:
        if o is not ob and o.name in bpy.data.objects:
            bpy.data.objects.remove(o)
    ob.name = name
    ob.data.materials.clear()
    for a in list(ob.data.attributes):
        if a.name.startswith("COLOR") or a.domain == "CORNER" and a.data_type == "BYTE_COLOR":
            ob.data.attributes.remove(a)
    return ob


def set_points(ob, pts) -> None:
    ob.data.vertices.foreach_set("co", np.asarray(pts, dtype=np.float32).ravel())
    ob.data.update()


def skin_depth(bvh, sock, x: float, z: float, near_y: float):
    """The skin's depth (the socket's y) at the socket's (x, z): the first Body hit of a ray from in front of the
    face along the socket's +y (the socket leans with the face, about 14 degrees)."""
    o = sock @ Vector((x, near_y - 0.2, z))
    d = (sock.to_3x3() @ Vector((0, 1, 0))).normalized()
    hit = bvh.ray_cast(o, d, 0.5)
    return None if hit[0] is None else (sock.inverted() @ hit[0]).y


def symmetrize(ob) -> None:
    """The -x half mirrored onto +x (the plane x = 0)."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.symmetrize(bm, input=bm.verts[:] + bm.edges[:] + bm.faces[:], direction="X", dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def decimate_and_mirror(ob, budget: int) -> dict:
    """Made symmetric at full resolution, then decimated toward the budget with the modifier's own X symmetry and
    mirrored once more, so both halves match exactly (M20b: decimating first and mirroring the coarse result cut a
    ragged row of slivers along x = 0, the seam down the lower lip of PR #260's review). A pass that ends over the
    budget is repeated on the result."""
    raw = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    symmetrize(ob)
    tris, passes = sum(len(p.vertices) - 2 for p in ob.data.polygons), 0
    while tris > budget and passes < 3:
        ratio = G.decimate_ratio(tris, int(budget * 0.97))
        mod = ob.modifiers.new("dec", "DECIMATE")
        mod.ratio = ratio
        mod.use_collapse_triangulate = True
        mod.use_symmetry, mod.symmetry_axis = True, "X"
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.modifier_apply(modifier=mod.name)
        symmetrize(ob)
        tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
        passes += 1
    return {"raw_tris": raw, "passes": passes, "tris": tris, "budget": budget}


def centre_plane(pts) -> tuple[list, dict]:
    """M20b: the aligned form's points moved so its own best mirror plane (G.best_plane, scored on every k-th point
    against the whole form) is x = 0. Returns the points and the plane found."""
    kd = KDTree(len(pts))
    for i, q in enumerate(pts):
        kd.insert(q, i)
    kd.balance()
    sample = pts[::max(1, len(pts) // G.FIT["plane_sample"])]
    before = sum(kd.find(G.reflect(q, 0.0, 0.0))[2] for q in sample) / len(sample)
    x0, yaw, err = G.best_plane(sample, lambda q: kd.find(q)[2])
    return G.to_plane(pts, x0, yaw), {"x0_mm": round(x0 * 1000, 2), "yaw": yaw,
                                      "mean_mm_before": round(before * 1000, 3), "mean_mm": round(err * 1000, 3)}


def smooth_bands(form) -> dict:
    """M20b: the band |x| < FIT["mid_band"] (the mirror's join) and the lip line's band (+-line_band_z round
    G.lip_line, the middle 85 % of the width, front-facing; the decimation's thin facets there caught the light as
    specks) smoothed in depth (y) only, so neither the silhouette, the bow's dip nor the line's height changes."""
    me = form.data
    co = local_co(form)
    hw = float(co[:, 0].max() - co[:, 0].min()) / 2
    knots = G.lip_line([tuple(q) for q in co])
    mid = [i for i, q in enumerate(co) if abs(q[0]) < G.FIT["mid_band"]]
    line = [i for i, q in enumerate(co) if abs(q[0]) < 0.85 * hw and me.vertices[i].normal.y < 0
            and abs(q[2] - G.line_at(knots, q[0])) < G.FIT["line_band_z"]]
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    for ids, n in ((mid, G.FIT["mid_smooth"]), (line, G.FIT["line_smooth"])):
        vs = [bm.verts[i] for i in ids]
        for _k in range(n):
            bmesh.ops.smooth_vert(bm, verts=vs, factor=0.5, use_axis_x=False, use_axis_y=True, use_axis_z=False)
    bm.to_mesh(me)
    bm.free()
    me.update()
    return {"mid_verts": len(mid), "line_verts": len(line)}


def mirror_pairs(ob) -> np.ndarray:
    """M20b: per vertex the index of its mirror (-x, y, z), taken right after the mirror while it is exact."""
    co = local_co(ob)
    kd = KDTree(len(co))
    for i, q in enumerate(co):
        kd.insert(q, i)
    kd.balance()
    return np.array([kd.find((-q[0], q[1], q[2]))[1] for q in co])


def mirror_snap(ob, pairs) -> float:
    """M20b: each vertex averaged with its partner's mirror across the body's centre plane (world x = 0, not the
    socket's: the Mouth socket rolls 0.24 degrees, 0.33 mm at the corners), so the piece is mirrored as the
    parametric pieces were; returns the largest move (m). The piece is on its socket already."""
    mw = np.array(ob.matrix_world)
    co = local_co(ob)
    w = co @ mw[:3, :3].T + mw[:3, 3]
    m = w[pairs] * np.array([-1.0, 1.0, 1.0])
    new = ((w + m) / 2 - mw[:3, 3]) @ np.linalg.inv(mw[:3, :3]).T
    set_points(ob, new)
    return float(np.linalg.norm(new - co, axis=1).max())


def fill_cleft(form, clamp: bool = True) -> dict:
    """M20b: the AI lower lip's central groove filled (measured on M20's rest: the front 0.8-1.4 mm further back at
    x = 0 than at +-2-3 mm, a cleft down the lower lip that read as a seam; mp1's lower lip is one smooth cushion).
    A front-facing vertex below the lip line within FIT["cleft_band"] of x = 0 comes forward toward the lip's front
    at the band's edge at its own height (a ray along +y), never back, by a smoothstep weight from the edge to x = 0.
    M20c (PR #260's last review, minor 1): a vertex deeper than FIT["cleft_most"] comes forward by cleft_most
    (`clamp`, rest and M; skipping it left a dimple at the top of the lower lip's centre); small skips it (its
    parting, 11 mm deep)."""
    me = form.data
    co = local_co(form)
    tree = BVHTree.FromPolygons([tuple(q) for q in co], [list(p.vertices) for p in me.polygons])
    knots = G.lip_line([tuple(q) for q in co])
    band, front = G.FIT["cleft_band"], float(co[:, 1].min()) - 0.02
    moved, most, clamped = 0, 0.0, 0
    for i, v in enumerate(me.vertices):
        x, y, z = co[i]
        if abs(x) >= band or v.normal.y > -0.3 or z > G.line_at(knots, x) - 0.001:
            continue
        hit = tree.ray_cast(Vector((band, front, z)), Vector((0, 1, 0)), 0.2)
        if hit[0] is None or hit[0].y >= y:
            continue  # never back
        depth = y - hit[0].y
        if depth > G.FIT["cleft_most"]:
            if not clamp:
                continue  # deeper than a groove is small's parting (it moved 11 mm without the cap)
            depth, clamped = G.FIT["cleft_most"], clamped + 1
        d = depth * G.smoothstep(band, 0.0, abs(x))
        co[i, 1] = y - d
        moved, most = moved + 1, max(most, d)
    set_points(form, co)
    return {"moved": moved, "clamped": clamped, "most_mm": round(most * 1000, 2)}


def closed_contact(body, piece) -> dict:
    """M20b: the skin's pout contact (Body's CONTACT_UV_MOUTH2 u) from a closed AI rest: alien_m12.contact_field's
    rule, but a skin point inside the form (under the lips, where its back went 3-4 mm under the skin) touches it
    (G.contact_distance), so the shadow is full where the lips meet the skin (PR #260: `full` 0)."""
    me = body.data
    mw, omw = body.matrix_world, piece.matrix_world
    tree = BVHTree.FromPolygons([omw @ v.co for v in piece.data.vertices],
                                [list(p.vertices) for p in piece.data.polygons])
    reach = M12.LG.CONTACT["reach"]
    c = np.zeros(len(me.vertices))
    for i, v in enumerate(me.vertices):
        p = mw @ v.co
        hit = tree.find_nearest(p, reach)
        if hit[0] is not None:
            c[i] = M12.LG.contact(G.contact_distance(hit[3], (p - hit[0]).dot(hit[1]) < 0.0), reach)
    # M20c (PR #260's last review, minor 2: full 72, a pale band under the lower lip at 3/4): the smoothing spreads
    # the shadow out but never lightens a touching point (one under the form or within contact_margin of it)
    c = np.maximum(M6.smooth(me, c, M12.LG.CONTACT["smooth"]), np.where(c >= G.FIT["contact_keep"], 1.0, 0.0))
    layer = me.uv_layers[M12.LP.CONTACT_UV_MOUTH2[0]]
    lv = np.empty(len(me.loops), dtype=np.int64)
    me.loops.foreach_get("vertex_index", lv)
    uv = np.empty(len(me.loops) * 2, dtype=np.float32)
    layer.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    uv[:, 0] = c[lv]
    layer.data.foreach_set("uv", uv.ravel())
    return {"touched": int((c > 0.01).sum()), "full": int((c > 0.9).sum()), "inside_touches": True}


def align_form(form, ours, shape: str, bvh, sock) -> dict:
    """form (world) aligned onto our piece `ours` (world): a closed shape by the lip line, A by the lips' centre
    height. Our lip line is looked for on the lip vertices in front of the skin only (M20: the parts tucked under
    the skin put the parametric rest's line 5 mm low, M and small's at the right height)."""
    oc = local_co(ours)[lip_mask(ours)]
    olo, ohi = G.bbox(map(tuple, oc))
    front = [tuple(q) for q in oc if (lambda sy: sy is None or q[1] < sy)(skin_depth(bvh, sock, q[0], q[2], olo[1]))]
    fc = local_co(form)
    flo, fhi = G.bbox(map(tuple, fc))
    if shape in CLOSED and G.FIT["closed_align"] == "centre":  # M20: the visible lips' middle height on ours
        flo_v, fhi_v = G.bbox(front)
        oline, fline = (flo_v[2] + fhi_v[2]) / 2, (flo[2] + fhi[2]) / 2
    elif shape in CLOSED:
        oline, fline = G.seam_z(front), G.seam_z([tuple(p) for p in fc])
    else:
        oline, fline = (olo[2] + ohi[2]) / 2, (flo[2] + fhi[2]) / 2
    s, t = G.align(flo, fhi, fline, ohi[0] - olo[0], oline, olo[1])
    pts = G.apply(map(tuple, fc), s, t)
    kz = G.FIT["z_scale"].get(shape, 1.0) if shape in CLOSED else 1.0
    if kz != 1.0:  # M20: the AI lips' fullness toward mp1's (the height about the line, the depth half as much)
        pts = G.stretch(pts, oline, olo[1], kz, 1.0 + G.FIT["y_follow"] * (kz - 1.0))
        if G.FIT["lower_scale"] != 1.0:  # the lower lip alone a little fuller (mp1: lower = upper)
            pts = G.stretch_below(pts, G.seam_z(pts), G.FIT["lower_scale"])
    kx, ky = G.FIT["xy_scale"].get(shape, (1.0, 1.0)) if shape in CLOSED else (1.0, 1.0)
    if (kx, ky) != (1.0, 1.0):  # M20b minor 4: M wider and flatter in depth (pressed), as mp1's M
        f0 = min(p[1] for p in pts)
        pts = [(x * kx, f0 + (y - f0) * ky, z) for x, y, z in pts]
    pts, plane = centre_plane(pts)  # M20b: on its own mirror plane before the mirror
    seat = None
    if G.FIT["seat"] == "back":  # the form's flat back on the skin at the lip line's centre, so only it sticks out
        sy = skin_depth(bvh, sock, 0.0, oline, olo[1])
        if sy is not None:
            seat = sy + G.FIT["seat_sink"] - max(p[1] for p in pts)
            pts = [(x, y + seat, z) for x, y, z in pts]
    set_points(form, pts)
    lo2, hi2 = G.bbox(map(tuple, local_co(form)))
    return {"scale": round(s, 6), "ours_mm": [round((ohi[i] - olo[i]) * 1000, 1) for i in range(3)],
            "form_mm": [round((hi2[i] - lo2[i]) * 1000, 1) for i in range(3)], "line_z": round(oline, 5),
            "seat_mm": None if seat is None else round(seat * 1000, 2), "z_scale": kz, "xy_scale": [kx, ky],
            "plane": plane}


def close_form(form, bvh, sock, corners: bool = False) -> dict:
    """The form's back pushed under the skin and curved under (taper_back), then the moved band smoothed; corners
    (M20): the thin ends' back goes corner_sink deeper, so its glossy rim does not show where it meets the skin."""
    me = form.data
    co = local_co(form)
    lo, hi = co.min(0), co.max(0)
    centre = ((lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2)
    depth = float(hi[1] - lo[1])
    moved = set()
    hw = float(hi[0] - lo[0]) / 2
    for i, v in enumerate(me.vertices):
        sy = skin_depth(bvh, sock, co[i, 0], co[i, 2], lo[1])
        sink = G.FIT["sink"] + (G.corner_sink(co[i, 0], centre[0], hw) if corners else 0.0)
        q = G.taper_back(tuple(co[i]), v.normal.y, sy, centre, depth, sink=sink)
        if q != tuple(co[i]):
            co[i] = q
            moved.add(i)
    set_points(form, co)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    band = {bm.verts[i] for i in moved}
    band |= {e.other_vert(v) for v in list(band) for e in v.link_edges}
    for _k in range(G.FIT["smooth"]):
        bmesh.ops.smooth_vert(bm, verts=list(band), factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bm.to_mesh(me)
    bm.free()
    me.update()
    return {"back_moved": len(moved), "depth_mm": round(depth * 1000, 1)}


def form_materials(form, shape: str, mats: dict) -> dict:
    """Our lip material on the form; on A the deep front-facing floor of its opening removed (cup_from_ours fills it);
    on small (M20) the deep front-facing faces of its parting painted alien_mouth_inner (a dark slit, no hole)."""
    me = form.data
    me.materials.clear()
    me.materials.append(mats[LIP])
    me.materials.append(mats[INNER])
    inner = 0
    if shape not in ("rest", "M"):
        co = local_co(form)
        lo, hi = co.min(0), co.max(0)
        depth, w, h = hi[1] - lo[1], hi[0] - lo[0], hi[2] - lo[2]
        cx, cz = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2
        knots = G.lip_line([tuple(q) for q in co]) if shape == "small" else None
        tree = BVHTree.FromPolygons([tuple(p) for p in co], [list(p.vertices) for p in me.polygons])
        for f in me.polygons:
            f.select = False  # the import and the mirror leave faces selected
        for f in me.polygons:
            c = f.center
            if knots is not None:  # small: only round its parting, never the lips' outer rims
                if abs(c.x - cx) > G.FIT["slit_reach"] * w / 2 or abs(c.z - G.line_at(knots, c.x)) > G.FIT["slit_band"] * h:
                    continue
            elif abs(c.x - cx) > OPENING[0] * w or abs(c.z - cz) > OPENING[1] * h:
                continue
            hit = tree.ray_cast(Vector((c.x, lo[1] - 0.01, c.z)), Vector((0, 1, 0)), 1.0)
            deep = G.FIT["slit_depth"] if shape == "small" else INNER_DEPTH
            if hit[2] == f.index and (c.y - lo[1]) > deep * depth:  # seen from the front, deep
                f.select = True
                inner += 1
        if shape == "small":
            for f in me.polygons:
                if f.select:
                    f.material_index = 1
                    f.select = False
            for f in me.polygons:
                f.use_smooth = True
            return {"slit_faces": inner}
        # the floor goes: our own cup and tongue (cup_from_ours) show through the opening, dark and clean-edged
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.delete(bm, geom=[q for q in bm.faces if q.select], context="FACES")
        bm.to_mesh(me)
        bm.free()
        me.update()
    for f in me.polygons:
        f.use_smooth = True
    return {"floor_faces_removed": inner}


def cup_from_ours(form, ours) -> int:
    """aia's A: our piece's dark cup and tongue (every face not of a lip material) joined into the form, behind its
    opening (both are in the socket's space with an identity basis). Returns the faces added."""
    cup = ours.copy()
    cup.data = ours.data.copy()
    bpy.context.scene.collection.objects.link(cup)
    bm = bmesh.new()
    bm.from_mesh(cup.data)
    mats = [sl.material.name for sl in cup.material_slots]
    bmesh.ops.delete(bm, geom=[q for q in bm.faces if mats[q.material_index].startswith("alien_lip")], context="FACES")
    bm.to_mesh(cup.data)
    bm.free()
    n = len(cup.data.polygons)
    for o in bpy.context.view_layer.objects:
        o.select_set(o is cup or o is form)
    bpy.context.view_layer.objects.active = form
    bpy.ops.object.join()
    return n


def to_socket(ob, mouth) -> None:
    """A form whose coordinates are already the socket's, parented with an identity basis (alien_m12.attach)."""
    M12.attach(ob, mouth)
    bpy.context.view_layer.update()


def wrap_ours(ours, form, bvh, sock, name: str):
    """aib: a copy of our piece whose lip vertices follow the AI form (wrap_weight), the rest kept."""
    ob = ours.copy()
    ob.data = ours.data.copy()
    ob.name = ob.data.name = name
    bpy.context.scene.collection.objects.link(ob)
    co = local_co(ob)
    lips = lip_mask(ob)
    vg = ob.vertex_groups.new(name="m19_wrap")
    wsum = 0.0
    for i, v in enumerate(ob.data.vertices):
        if not lips[i]:
            continue
        sy = skin_depth(bvh, sock, co[i, 0], co[i, 2], co[:, 1].min())
        w = G.wrap_weight(v.normal.y, sy is not None and co[i, 1] > sy)
        if w > 0:
            vg.add([i], w, "REPLACE")
            wsum += w
    bpy.context.view_layer.objects.active = ob
    for o in bpy.context.view_layer.objects:
        o.select_set(o is ob)
    for k in range(WRAP_ROUNDS):  # wrap, relax, wrap again: the tubes follow the form without folding
        mod = ob.modifiers.new(f"wrap{k}", "SHRINKWRAP")
        mod.target = form
        mod.wrap_method = "NEAREST_SURFACEPOINT"  # PROJECT (along the normals, WRAP_LIMIT) folded more: M19 round 3
        mod.vertex_group = "m19_wrap"  # a name: the group reference dangles once a modifier is applied
        bpy.ops.object.modifier_apply(modifier=mod.name)
        if k < WRAP_ROUNDS - 1:
            sm = ob.modifiers.new(f"relax{k}", "SMOOTH")
            sm.factor, sm.iterations, sm.vertex_group = 0.5, 4, "m19_wrap"
            bpy.ops.object.modifier_apply(modifier=sm.name)
    if "m19_wrap" in ob.vertex_groups:
        ob.vertex_groups.remove(ob.vertex_groups["m19_wrap"])
    after = local_co(ob)
    d = np.linalg.norm(after - co, axis=1)
    return ob, {"wrapped": round(wsum, 1), "moved_max_mm": round(float(d.max()) * 1000, 2),
                "moved_mean_mm": round(float(d[lips].mean()) * 1000, 2)}


def also_pieces(key: str, blend: Path, shapes, mouth, mats) -> list:
    with bpy.data.libraries.load(str(blend), link=False) as (src, dst):
        dst.objects = [f"mouth_pout_{s}" for s in shapes if f"mouth_pout_{s}" in src.objects]
    out = []
    for ob in dst.objects:
        if ob is None:
            continue
        shape = ob.name.split("_")[-1].split(".")[0]
        ob.name = ob.data.name = f"lipvar_{key}_pout_{shape}"
        bpy.context.scene.collection.objects.link(ob)
        for slot in ob.material_slots:
            base = slot.material.name.split(".")[0]
            if base in mats:
                slot.material = mats[base]
        M12.attach(ob, mouth)
        out.append(ob)
    return out


def fit_form(path: Path, ours, shape: str, bvh, sock, mouth, mats, corners: bool = False):
    """An AI form aligned, measured, cleaned, painted and closed into the skin, on the Mouth socket."""
    form = import_form(path, f"m19_form_{shape}")
    r = {"align": align_form(form, ours, shape, bvh, sock)}
    # PR #256's review minor 4: the mirror error of the aligned form before it is made symmetric (every 4th point)
    pts = [tuple(q) for q in local_co(form)]
    r["mirror_mm_before"] = round(G.mirror_error(pts[::4]) * 1000, 2)
    r["clean"] = decimate_and_mirror(form, G.FIT["budget_tris"])
    pairs = mirror_pairs(form) if shape in CLOSED else None
    r["materials"] = form_materials(form, shape, mats)  # before the close: the floor by the form's own depth
    r["close"] = close_form(form, bvh, sock, corners=corners)
    if shape in CLOSED:
        r["cleft"] = fill_cleft(form, clamp=shape != "small")
        r["bands"] = smooth_bands(form)
    to_socket(form, mouth)
    if shape in CLOSED:
        r["mirror_snap_mm"] = round(mirror_snap(form, pairs) * 1000, 3)
    return form, r


def provenance(path: Path) -> dict:
    """The AI piece's record from the Meshy generation.json beside its GLB (docs/manifest.md's fields)."""
    g = json.loads((path.parent / "generation.json").read_text(encoding="utf-8"))
    task = next(iter(g["tasks"].values()))
    return {"ai_generated": True, "service": "meshy", "model": g.get("model_version"), "kind": g.get("kind"),
            "task_id": task.get("id"), "credits": task.get("consumed_credits"), "batch": g.get("batch"),
            "batch_file": "batches/" + g.get("batch_file", ""), "item": g.get("item"), "licence": g.get("licence"),
            "approval_ref": (g.get("approval") or {}).get("ref"), "glb": path.as_posix(),
            "glb_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "inputs": [i.get("provenance") for i in g.get("inputs", [])]}


def jaw_closed(ob) -> dict:
    """The jaw weight of a one-piece closed form into COLOR_0's alpha (alien_m12.jaw_weights' channel; the colour
    stays the grey AO): G.jaw_closed below the form's own lip line (G.lip_line of its lip faces)."""
    me = ob.data
    co = local_co(ob)
    lp = [tuple(q) for q in co[lip_mask(ob)]]
    knots = G.lip_line(lp)
    lo, hi = G.bbox(lp)
    cx, hw = (lo[0] + hi[0]) / 2, (hi[0] - lo[0]) / 2
    g = np.array([G.jaw_closed(tuple(q), knots, cx, hw, G.FIT["jaw_band"], M12.JAW) for q in co])
    n = len(me.vertices)
    if "ao" not in me.color_attributes:
        at = me.color_attributes.new("ao", "FLOAT_COLOR", "POINT")
        at.data.foreach_set("color", np.ones(n * 4, dtype=np.float32))
        me.color_attributes.active_color = at
        me.color_attributes.render_color_index = me.color_attributes.find("ao")
    col = np.empty(n * 4, dtype=np.float32)
    me.color_attributes["ao"].data.foreach_get("color", col)
    col = col.reshape(-1, 4)
    col[:, 1] = col[:, 0]
    col[:, 3] = g
    me.color_attributes["ao"].data.foreach_set("color", col.astype(np.float32).ravel())
    return {"moving": round(float((g > 0.5).mean()), 3), "max": round(float(g.max()), 3),
            "line_mm": [[round(x * 1000, 1), round(z * 1000, 1)] for x, z in knots]}


def replace_main(a, kit: Path, ex: Path, ai: dict) -> None:
    """M20: the AI forms as the kit's closed pout pieces (see the module's docstring)."""
    if set(ai) - set(CLOSED):
        raise SystemExit(f"--replace takes the closed shapes {CLOSED}, got {sorted(ai)}")
    bpy.ops.wm.open_mainfile(filepath=str(kit / "alien_character.blend"))
    cj = json.loads((kit / "character.json").read_text(encoding="utf-8"))
    body = M6.rest_pose()
    bvh = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    mouth = bpy.data.objects["Mouth"]
    sock = mouth.matrix_world.copy()
    mats = {n: bpy.data.materials[n] for n in (LIP, INNER)}
    rep = {"kit": str(kit), "fit": dict(G.FIT), "shapes": {}}
    new = []
    for shape in CLOSED:
        if shape not in ai:
            continue
        name = f"mouth_pout_{shape}"
        ours = bpy.data.objects[name]
        hidden = ours.hide_render
        form, r = fit_form(ai[shape], ours, shape, bvh, sock, mouth, mats, corners=True)
        r["ours_tris"] = sum(len(q.vertices) - 2 for q in ours.data.polygons)
        old = ours.data
        bpy.data.objects.remove(ours)
        bpy.data.meshes.remove(old)
        form.name = form.data.name = name
        form.hide_render = hidden
        lo, hi = G.bbox(map(tuple, local_co(form)))
        r["mm"] = [round((hi[i] - lo[i]) * 1000, 1) for i in range(3)]
        r["provenance"] = provenance(ai[shape])
        log(shape, json.dumps({k: v for k, v in r.items() if k != "provenance"}))
        rep["shapes"][shape] = r
        new.append(form)
    bpy.context.view_layer.update()
    rep["contact"] = M12.mouth2_contact(body)  # the skin's pout contact from the new rest
    if "mouth_pout_rest" in bpy.data.objects:  # M20b: with the skin under the closed form touching it
        rep["contact"]["pout"] = closed_contact(body, bpy.data.objects["mouth_pout_rest"])
        log("contact pout", json.dumps(rep["contact"]["pout"]))
    if not a.no_bake:
        rep["parts_ao"] = M6.bake_parts_ao(body, eyes=False, pieces=new)
    rep["jaw"] = {o.name: jaw_closed(o) for o in new}
    log("jaw", json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "line_mm"} for k, v in rep["jaw"].items()}))
    arm = body.find_armature()
    if arm is not None:  # back to POSE: in REST the exporter bakes every clip as the rest pose
        arm.data.pose_position = "POSE"
    bpy.context.view_layer.update()
    ex.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(ex / "alien_character.blend"))
    opts = dict(export_glb.options(False), export_image_format="AUTO", export_vertex_color="ACTIVE",
                export_tangents=True, export_extras=True)
    glb = ex / "alien_character.glb"
    res = bpy.ops.export_scene.gltf(filepath=str(glb), **opts)
    if res != {"FINISHED"}:
        raise SystemExit(f"export: {res}")
    AE.check_images(glb)
    if a.orm_sss:
        bad = M12.E.sss_orm_problems(glb.read_bytes(), "alien_hue", Path(a.orm_sss).read_bytes())
        if bad:
            raise SystemExit(f"the GLB's SSS route: {bad}")
        log("sss route ok")
    for f in kit.iterdir():
        if f.suffix == ".png":
            shutil.copy2(f, ex / f.name)
    cj["m20"] = rep
    cj["note_m20"] = (
        "art #196 M20 (the hybrid pout): mouth_pout_rest, mouth_pout_M and mouth_pout_small are AI-made forms "
        "(Meshy multi-image to 3D, meshy-7.1, of our GPT Image views of the mp1 sheet's lips; ai_generated = true, the "
        "task ids and batch files per shape in m20.shapes.<shape>.provenance), fitted onto the Mouth socket by "
        "tools/blender/alien_mouth_fit.py --replace: one closed piece each (no separate upper and lower tube), "
        "alien_lip_pout, small's parting alien_mouth_inner; COLOR_0 the baked AO and its alpha the jaw weight (below "
        "the lip line 1, above 0, the corners less); the skin's pout contact (TEXCOORD_6.u) from the new rest. The "
        "open shapes A, E, O are ours (alien_mouths).")
    (ex / "character.json").write_text(json.dumps(cj, indent=1), encoding="utf-8", newline="\n")
    (ex / "fit.json").write_text(json.dumps(rep, indent=1), encoding="utf-8", newline="\n")
    log("EXPORT", glb, round(glb.stat().st_size / 1e6, 2), "MB")


def main():
    a = args()
    if a.fit:
        G.FIT.update(json.loads(a.fit))
    kit, out = Path(a.kit), Path(a.out)
    ex = out / a.export_name
    if ex.resolve() == kit.resolve():
        raise SystemExit("the new kit must not overwrite its input")
    ai = {k: Path(v) for k, v in json.loads(a.ai).items()}
    if a.replace:
        replace_main(a, kit, ex, ai)
        return
    bpy.ops.wm.open_mainfile(filepath=str(kit / "alien_character.blend"))
    body = M6.rest_pose()
    bvh = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    mouth = bpy.data.objects["Mouth"]
    sock = mouth.matrix_world.copy()
    mats = {n: bpy.data.materials[n] for n in (LIP, INNER, "alien_lip")}
    rep = {"kit": str(kit), "ai": {k: str(v) for k, v in ai.items()}, "fit": dict(G.FIT), "shapes": {}}
    new = []
    for shape, path in ai.items():
        ours = bpy.data.objects[f"mouth_pout_{shape}"]
        form, r = fit_form(path, ours, shape, bvh, sock, mouth, mats)
        # aib targets the AI lips alone (PR #256's review minor 1: with our cup joined first, A's corners crumpled)
        wb, r["aib"] = wrap_ours(ours, form, bvh, sock, f"lipvar_aib_pout_{shape}")
        if shape not in CLOSED:
            r["cup_faces"] = cup_from_ours(form, ours)
        lo, hi = G.bbox(map(tuple, local_co(form)))
        r["aia_mm"] = [round((hi[i] - lo[i]) * 1000, 1) for i in range(3)]
        form.name = form.data.name = f"lipvar_aia_pout_{shape}"
        r["verts"] = {"aia": len(form.data.vertices), "aib": len(wb.data.vertices), "ours": len(ours.data.vertices)}
        log(shape, json.dumps(r))
        rep["shapes"][shape] = r
        new += [form, wb]
    for spec in a.also:
        key, blend = spec.split("=", 1)
        got = also_pieces(key, Path(blend), list(ai), mouth, mats)
        log("also", key, [o.name for o in got])
        rep.setdefault("also", {})[key] = [o.name for o in got]
        new += got
    bpy.context.view_layer.update()
    baked = [o for o in new if "_aia_" in o.name or "_aib_" in o.name]  # an --also kit's pieces keep their own
    if not a.no_bake:
        rep["parts_ao"] = M6.bake_parts_ao(body, eyes=False, pieces=baked)
    rep["jaw"] = {o.name: M12.jaw_weights(o) for o in baked}
    log("jaw", json.dumps(rep["jaw"]))
    arm = body.find_armature()
    if arm is not None:
        arm.data.pose_position = "POSE"
    bpy.context.view_layer.update()
    ex.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(ex / "alien_character.blend"))
    opts = dict(export_glb.options(False), export_image_format="AUTO", export_vertex_color="ACTIVE",
                export_tangents=True, export_extras=True)
    glb = ex / "alien_character.glb"
    res = bpy.ops.export_scene.gltf(filepath=str(glb), **opts)
    if res != {"FINISHED"}:
        raise SystemExit(f"export: {res}")
    AE.check_images(glb)
    for f in kit.iterdir():
        if f.suffix == ".png" or f.name == "character.json":
            shutil.copy2(f, ex / f.name)
    (ex / "fit.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    log("EXPORT", glb, round(glb.stat().st_size / 1e6, 2), "MB")


if __name__ == "__main__":
    main()
