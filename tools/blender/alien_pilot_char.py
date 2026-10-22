"""The alien 3D pilot, step 2b-2 (art #196): one rigged pilot head (alien_pilot_rig.py's <head>_rig.blend, read,
never written) welded onto the shared alien body (the parts kit's alien_body.blend: `Body` skinned to
`CharacterArmature`, the contract skeleton with the clips, its neck ending in the open 48-vertex neck ring), one
skinned character, `<head>_char.glb`.

The method:
1. Fit: the head turned to the body's front (-Y) and scaled so its eyes sit at the body skeleton's eye height
   (EYE_Z); the neck's waist (its narrowest slab below the face) set on the ring's axis just above the ring.
2. Cut and morph: the head's skin below the waist is deleted (the bust's shoulders); over NECK_BAND above the cut
   each vertex's distance from the ring's axis blends toward the ring's ellipse at its angle, so the cut's boundary
   lies on the ring's own shape.
3. Weld: the skin and the body joined (the skin active: its blend shapes kept, the body's rows at their rest), the
   boundary and the ring bridged with one row of faces (bmesh bridge_loops), custom normals cleared and every face
   smooth: no lighting seam.
4. Skeleton: the head's face bones join the body's armature under its Head (the body's own Jaw and eyes replaced by
   the head's, at the head's joints); the head's skin over NECK_BLEND above the cut takes Neck weight from the ring's
   0.7 down to 0, so turning the Head bone bends the neck smoothly instead of at a seam.
5. The body's plain material takes the head's neck colour (median of samples round the cut): the game replaces it by
   name with the hue shader anyway.

Writes <out>/<head>_char.glb (the body's clips included), <head>_char.blend and char.json. Runs only through
tools/runner/blender.py: run_script("alien_pilot_char.py", ["--head", h, "--rig", <head>_rig.blend, "--build",
build.json, "--body", alien_body.blend, "--out", <dir>]).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_pilot_head as H  # noqa: E402

EYE_Z = 1.608  # the body skeleton's LeftEye/RightEye joint height, m
GAP = 0.008  # the cut above the ring (the ring's own step), m
NECK_BAND = 0.05  # the morph band above the cut, m
NECK_BLEND = 0.07  # the Neck weight's fade above the cut, m
NECK_RING_W = 0.7  # the ring's Neck weight (neck_ring.json)
REPLACED = ("Jaw", "LeftEye", "RightEye")  # the body's bones the head brings its own of


def log(msg):
    print(f"CHAR {msg}", flush=True)


def world(obj):
    mw = np.array(obj.matrix_world)
    a = np.empty(len(obj.data.vertices) * 3)
    obj.data.vertices.foreach_get("co", a)
    a = a.reshape(-1, 3)
    return a @ mw[:3, :3].T + mw[:3, 3]


def main():
    ap = argparse.ArgumentParser()
    for k in ("--head", "--rig", "--build", "--body", "--out"):
        ap.add_argument(k, required=True)
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    head, out = a.head, Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    build = json.loads(Path(a.build).read_text(encoding="utf-8"))
    rep = {"head": head}
    bpy.ops.wm.open_mainfile(filepath=a.body)
    arm, body = bpy.data.objects["CharacterArmature"], bpy.data.objects["Body"]
    rep["body_transforms_identity"] = bool(np.allclose(np.array(arm.matrix_world), np.eye(4))
                                           and np.allclose(np.array(body.matrix_world), np.eye(4)))
    # the ring: the body's top boundary loop
    bco = world(body)
    bm = bmesh.new()
    bm.from_mesh(body.data)
    ring_idx = sorted({v.index for e in bm.edges if e.is_boundary for v in e.verts if bco[v.index, 2] > 1.3})
    bm.free()
    ring = bco[ring_idx]
    ring_z, ring_c = float(ring[:, 2].mean()), ring[:, :2].mean(0)
    ang = np.arctan2(ring[:, 0] - ring_c[0], -(ring[:, 1] - ring_c[1]))  # 0 at the front, toward the left (+X)
    rad = np.hypot(*(ring[:, :2] - ring_c).T)
    order = np.argsort(ang)
    ang_s, rad_s = ang[order], rad[order]

    def ring_r(phi):
        return np.interp(phi, np.concatenate([ang_s - 2 * math.pi, ang_s, ang_s + 2 * math.pi]),
                         np.tile(rad_s, 3))

    rep["ring"] = {"vertices": len(ring_idx), "z": round(ring_z, 4), "centre": [round(float(c), 4) for c in ring_c],
                   "mean_r": round(float(rad.mean()), 4)}
    log(f"ring {rep['ring']}")

    # the head: appended from its rig
    with bpy.data.libraries.load(a.rig, link=False) as (src, dst):
        dst.objects = list(src.objects)
    objs = [o for o in dst.objects if o is not None and o.type in ("MESH", "ARMATURE")]
    for o in objs:
        bpy.context.collection.objects.link(o)
    parm = next(o for o in objs if o.type == "ARMATURE")
    meshes = [o for o in objs if o.type == "MESH" and o.parent == parm]
    skin = next(o for o in meshes if o.name.startswith(f"{head}_skin"))
    sco = world(skin)
    fr = Vector(build["front"])
    eyes_z = float(np.mean([e["centre"][2] for e in build["eyes"].values()]))
    neck = parm.data.bones["Head"].head_local
    m = float(json.loads((Path(a.rig).parent / "rig.json").read_text(encoding="utf-8"))["m"])
    # the waist: the narrowest slab between 3 mouth units below the neck joint and the joint
    best = None
    for zz in np.arange(neck.z - 3.0 * m, neck.z + 1e-9, 0.05 * m):
        sl = sco[np.abs(sco[:, 2] - zz) < 0.03 * m]
        if len(sl) < 12:
            continue
        c = sl[:, :2].mean(0)
        r = float(np.median(np.hypot(*(sl[:, :2] - c).T)))
        if best is None or r < best[1]:
            best = (float(zz), r, c)
    z_w, r_w, c_w = best
    s = (EYE_Z - ring_z - GAP) / (eyes_z - z_w)
    theta = math.atan2(fr.x, -fr.y)  # turns fr onto -Y
    T = (Matrix.Translation((ring_c[0], ring_c[1], ring_z + GAP)) @ Matrix.Scale(s, 4)
         @ Matrix.Rotation(theta, 4, "Z") @ Matrix.Translation((-c_w[0], -c_w[1], -z_w)))
    rep["fit"] = {"scale": round(s, 5), "waist_z": round(z_w, 4), "waist_r_scaled": round(r_w * s, 4),
                  "turn_deg": round(math.degrees(theta), 2)}
    for o in meshes:
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = T @ mw
    parm.matrix_world = T @ parm.matrix_world
    H.select_only([parm, *meshes], active=parm)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    sco = world(skin)
    rep["fit"]["top_z"] = round(float(max(world(o)[:, 2].max() for o in meshes)), 4)
    log(f"fit {rep['fit']}")

    # cut below the waist; the band above it morphed onto the ring's shape
    cut = ring_z + GAP
    rel = sco[:, :2] - ring_c
    phi = np.arctan2(rel[:, 0], -rel[:, 1])
    r = np.hypot(rel[:, 0], rel[:, 1])
    t = H.sstep(cut + NECK_BAND, cut, sco[:, 2])
    k = (r + t * (ring_r(phi) - r)) / np.maximum(r, 1e-9)
    new = sco.copy()
    new[:, 0] = ring_c[0] + rel[:, 0] * k
    new[:, 1] = ring_c[1] + rel[:, 1] * k
    bm = bmesh.new()
    bm.from_mesh(skin.data)
    keys = list(bm.verts.layers.shape.values())
    dead = [f for f in bm.faces if any(sco[v.index, 2] < cut - 1e-6 for v in f.verts)]
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.verts.ensure_lookup_table()
    for v in bm.verts:  # every shape key moved by the basis' morph (the band is below the face: no key moves it)
        i = v.index  # the indices before the deletion: no index_update since
        d = Vector(new[i] - sco[i])
        if v.is_boundary and v.co.z < cut + 0.03:
            d.z = cut - v.co.z  # the boundary flat on the cut
        v.co += d
        for ly in keys:
            v[ly] += d
    bm.to_mesh(skin.data)
    bm.free()
    skin.data.update()
    rep["cut_faces_deleted"] = len(dead)
    pg = skin.vertex_groups.new(name="PilotSkin")
    pg.add(list(range(len(skin.data.vertices))), 1.0, "REPLACE")

    # the neck colour for the body's plain material
    img = H.base_image(skin.active_material)
    samples = []
    for k_ in range(8):
        p = 2 * math.pi * k_ / 8
        rr = float(ring_r(np.array([p]))[0])
        pt = Vector((ring_c[0] + 1.05 * rr * math.sin(p), ring_c[1] - 1.05 * rr * math.cos(p), cut + 0.03))
        samples.append(H.sample_skin(skin, img, pt))
    rgb = tuple(float(c) for c in np.median(np.array(samples), axis=0))
    bmat = body.data.materials[0]
    bsdf = next((n for n in bmat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None) if bmat.use_nodes else None
    if bsdf is not None and not bsdf.inputs["Base Color"].is_linked:
        bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    rep["body_rgb"] = [round(c, 4) for c in rgb]

    # weld: join (the skin active), bridge the cut and the ring
    body.modifiers.clear()
    body.parent = None
    H.select_only([skin, body], active=skin)
    bpy.ops.object.join()
    co = world(skin)
    bm = bmesh.new()
    bm.from_mesh(skin.data)
    bm.verts.ensure_lookup_table()
    bound = [e for e in bm.edges if e.is_boundary and all(v.co.z < cut + 0.03 and v.co.z > ring_z - 0.01
                                                          and np.hypot(v.co.x - ring_c[0], v.co.y - ring_c[1]) < 0.12
                                                          for v in e.verts)]
    rep["boundary_edges"] = {"ring": sum(1 for e in bound if e.verts[0].co.z < ring_z + 0.004),
                             "cut": sum(1 for e in bound if e.verts[0].co.z >= ring_z + 0.004)}
    res = bmesh.ops.bridge_loops(bm, edges=bound)
    mat_i = next(i for i, mt in enumerate(skin.data.materials) if mt == bmat)
    for f in res["faces"]:
        f.material_index = mat_i
        f.smooth = True
    bm.to_mesh(skin.data)
    bm.free()
    rep["bridge"] = {"edges": len(bound), "faces": len(res["faces"])}
    log(f"bridge {rep['bridge']} boundary {rep['boundary_edges']}")
    H.select_only([skin], active=skin)
    if skin.data.has_custom_normals:
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    skin.data.polygons.foreach_set("use_smooth", [True] * len(skin.data.polygons))
    skin.name = skin.data.name = f"{head}_body"

    # the skeleton: the head's face bones under the body's Head
    H.select_only([arm], active=arm)
    bpy.ops.object.mode_set(mode="EDIT")
    for n in REPLACED:
        if n in arm.data.edit_bones:
            arm.data.edit_bones.remove(arm.data.edit_bones[n])
    bpy.ops.object.mode_set(mode="OBJECT")
    parm.data.bones["Head"].name = "PilotHead"
    H.select_only([arm, parm], active=arm)
    bpy.ops.object.join()
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones
    for b in list(eb):
        if b.parent is not None and b.parent.name == "PilotHead":
            b.parent = eb["Head"]
    eb.remove(eb["PilotHead"])
    bpy.ops.object.mode_set(mode="OBJECT")
    for o in meshes:
        if o.name not in bpy.data.objects:
            continue
        for md in o.modifiers:
            if md.type == "ARMATURE":
                md.object = arm
        if not any(md.type == "ARMATURE" for md in o.modifiers):
            o.modifiers.new("rig", "ARMATURE").object = arm
        o.parent = arm
    for o in [o for o in bpy.data.objects if o.type == "MESH" and o.parent == arm]:
        for g in o.vertex_groups:  # renaming the bone renamed its vertex groups: back onto the body's Head
            if g.name == "PilotHead":
                g.name = "Head"

    # the neck weights above the cut: the ring's Neck share fading out
    co = world(skin)
    pidx = skin.vertex_groups["PilotSkin"].index
    neck_g = skin.vertex_groups.get("Neck") or skin.vertex_groups.new(name="Neck")
    nw = NECK_RING_W * (1 - H.sstep(cut, cut + NECK_BLEND, co[:, 2]))
    n_set = 0
    for v in skin.data.vertices:
        if not any(g.group == pidx for g in v.groups) or nw[v.index] < 1e-3:
            continue
        for g in v.groups:
            if g.group != pidx:
                g.weight *= 1 - nw[v.index]
        neck_g.add([v.index], float(nw[v.index]), "ADD")
        n_set += 1
    skin.vertex_groups.remove(skin.vertex_groups["PilotSkin"])
    rep["neck_weighted"] = n_set
    parts = [o for o in bpy.data.objects if o.type == "MESH" and o.parent == arm]
    rep["tris"] = {o.name: H.tris(o) for o in parts}
    rep["tris_total"] = sum(rep["tris"].values())
    rep["bones"] = len(arm.data.bones)
    log(f"tris {rep['tris_total']} bones {rep['bones']}")
    H.select_only([arm, *parts], active=arm)
    bpy.ops.export_scene.gltf(filepath=str(out / f"{head}_char.glb"), export_format="GLB", use_selection=True,
                              export_apply=False, export_yup=True, export_animations=True, export_skins=True,
                              export_morph=True, export_morph_normal=True, export_extras=False)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / f"{head}_char.blend"), compress=True)
    (out / "char.json").write_text(json.dumps(rep, indent=2), encoding="utf-8", newline="\n")
    log("done")


if __name__ == "__main__":
    main()
