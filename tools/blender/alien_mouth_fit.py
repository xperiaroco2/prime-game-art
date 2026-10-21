"""M19 (art #196, brief UPDATE 38): the AI mouth route test. Fits AI-made lip forms (Meshy multi-image to 3D of GPT
Image views of the pout mp1's lips) onto our mouth socket and writes a grid kit with the variants beside our pieces.

Opens a kit's export/alien_character.blend (M15's or later, read only) and writes <out>/<export-name>/ (never over its
input): the same kit plus, per shape of --ai ({"rest": GLB, "A": GLB}), two pout variants as grid nodes
lipvar_<variant>_pout_<shape> (the names godot/alien/m12_shots.gd's "vgrid" shows):
- `aia` (the AI mesh itself): imported, aligned (alien_mouth_fit_geom.align: one uniform scale to our piece's lip
  width, centred on x = 0, its lip line on ours, its front on ours), decimated to FIT["budget_tris"], made symmetric
  (its -x half mirrored), its back pushed under the skin (close_back); on the A shape the deep front-facing floor of
  its opening gets our dark alien_mouth_inner;
- `aib` (our topology on the AI form): a copy of our piece whose lip vertices follow the aligned AI surface by
  wrap_weight (a Shrinkwrap to the nearest surface point; the parts under the skin and our cup stay);
- with --also KEY=BLEND, that kit's own mouth_pout_<shape> as lipvar_<KEY>_pout_<shape> (M16c's pieces beside).
Every variant gets our materials (alien_lip_pout, alien_mouth_inner), its own parts AO and jaw weights (alien_m6,
alien_m12's rules); the kit's own pieces, the Body and its contact layers are untouched. alien_mouths.py and
alien_lips_geom.py are only read (through alien_m12). Report: <out>/<export-name>/fit.json; log lines "M19 ...".

    tools/runner/blender.py run_script("alien_mouth_fit.py", ["--kit", <M15/export>, "--out", <M19>,
                                       "--ai", '{"rest": "...glb", "A": "...glb"}'])
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_eyes as AE  # noqa: E402
import alien_m6 as M6  # noqa: E402
import alien_m12 as M12  # noqa: E402
import alien_mouth_fit_geom as G  # noqa: E402
import export_glb  # noqa: E402

LIP = "alien_lip_pout"
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


def decimate_and_mirror(ob, budget: int) -> dict:
    tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    ratio = G.decimate_ratio(tris, budget)  # the mirror keeps the count: one half cut, the other copied
    mod = ob.modifiers.new("dec", "DECIMATE")
    mod.ratio = ratio
    mod.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.symmetrize(bm, input=bm.verts[:] + bm.edges[:] + bm.faces[:], direction="X", dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return {"raw_tris": tris, "ratio": round(ratio, 4), "tris": sum(len(p.vertices) - 2 for p in ob.data.polygons)}


def align_form(form, ours, shape: str, bvh, sock) -> dict:
    """form (world) aligned onto our piece `ours` (world): rest by the lip line, A by the lips' centre height."""
    oc = local_co(ours)[lip_mask(ours)]
    olo, ohi = G.bbox(map(tuple, oc))
    fc = local_co(form)
    flo, fhi = G.bbox(map(tuple, fc))
    if shape == "rest":
        oline, fline = G.seam_z([tuple(p) for p in oc]), G.seam_z([tuple(p) for p in fc])
    else:
        oline, fline = (olo[2] + ohi[2]) / 2, (flo[2] + fhi[2]) / 2
    s, t = G.align(flo, fhi, fline, ohi[0] - olo[0], oline, olo[1])
    pts = G.apply(map(tuple, fc), s, t)
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
            "seat_mm": None if seat is None else round(seat * 1000, 2)}


def close_form(form, bvh, sock) -> dict:
    """The form's back pushed under the skin and curved under (taper_back), then the moved band smoothed."""
    me = form.data
    co = local_co(form)
    lo, hi = co.min(0), co.max(0)
    centre = ((lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2)
    depth = float(hi[1] - lo[1])
    moved = set()
    for i, v in enumerate(me.vertices):
        sy = skin_depth(bvh, sock, co[i, 0], co[i, 2], lo[1])
        q = G.taper_back(tuple(co[i]), v.normal.y, sy, centre, depth)
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
    """Our lip material on the form; on A the deep front-facing floor of its opening removed (cup_from_ours fills it)."""
    me = form.data
    me.materials.clear()
    me.materials.append(mats[LIP])
    me.materials.append(mats[INNER])
    inner = 0
    if shape != "rest":
        co = local_co(form)
        lo, hi = co.min(0), co.max(0)
        depth, w, h = hi[1] - lo[1], hi[0] - lo[0], hi[2] - lo[2]
        cx, cz = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2
        tree = BVHTree.FromPolygons([tuple(p) for p in co], [list(p.vertices) for p in me.polygons])
        for f in me.polygons:
            f.select = False  # the import and the mirror leave faces selected
        for f in me.polygons:
            c = f.center
            if abs(c.x - cx) > OPENING[0] * w or abs(c.z - cz) > OPENING[1] * h:
                continue
            hit = tree.ray_cast(Vector((c.x, lo[1] - 0.01, c.z)), Vector((0, 1, 0)), 1.0)
            if hit[2] == f.index and (c.y - lo[1]) > INNER_DEPTH * depth:  # seen from the front, deep
                f.select = True
                inner += 1
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


def main():
    a = args()
    if a.fit:
        G.FIT.update(json.loads(a.fit))
    kit, out = Path(a.kit), Path(a.out)
    ex = out / a.export_name
    if ex.resolve() == kit.resolve():
        raise SystemExit("the new kit must not overwrite its input")
    ai = {k: Path(v) for k, v in json.loads(a.ai).items()}
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
        form = import_form(path, f"m19_form_{shape}")
        r = {"align": align_form(form, ours, shape, bvh, sock)}
        r["clean"] = decimate_and_mirror(form, G.FIT["budget_tris"])
        r["mirror_mm"] = round(G.mirror_error([tuple(p) for p in local_co(form)]) * 1000, 3)
        r["materials"] = form_materials(form, shape, mats)  # before the close: the floor by the form's own depth
        r["close"] = close_form(form, bvh, sock)
        to_socket(form, mouth)
        if shape != "rest":
            r["cup_faces"] = cup_from_ours(form, ours)
        wb, r["aib"] = wrap_ours(ours, form, bvh, sock, f"lipvar_aib_pout_{shape}")
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
