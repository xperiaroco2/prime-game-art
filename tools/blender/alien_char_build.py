"""A lively pilot head on the shared alien body (art #196, step B1): one skinned character, `<head>_char.glb`.

    run through tools/runner/blender.py by tools/blender/alien_char_run.py:
    alien_char_build.py -- --head H --lively <head>_lively.glb --lively-json lively.json --body alien_body.blend
        --albedo <head>_albedo.png --mask <head>_mask.png --accent <head>_accent.png --bases bases.json
        --out DIR

The weld is #287's (`alien_pilot_char.py`, never merged; its vertex-index fix kept), on the lively head instead of
the face-rigged one:
1. Fit: the head's neck waist (its narrowest slab between its Neck joint and just above its Head joint) is scaled
   onto the body's neck ring (`alien_char_geom.fit_scale`: the x half-widths) and set on the ring's axis GAP above it.
   No turn (both face -Y). The head above the band is only scaled and moved: never reshaped.
2. Cut and morph: the skin below the waist (the bust) is deleted; over NECK_BAND above the cut each vertex's
   distance from the axis blends toward the ring's ellipse at its angle, the boundary flat on the cut.
3. Weld: joined with the body, the cut and the ring zipped by angle (`zip_loops`; the counts differ), the new row
   on the body's material with the ring's UVs.
4. Normals: the head's own corner normals kept above the band (a corner attribute through the cut and the join),
   the geometric smooth normals over the band, the bridge and the body: no lighting seam.
5. Weights: the head's Neck and Head groups are the body's; its Chest goes to UpperChest; over NECK_BLEND above the
   cut the weights blend to the ring's mean, so the neck bends as one. The spring bones (Crest1-3 or Gill*) join
   the body's armature under its Head; the eye bones move to the head's eye centres.
6. The body's material set: `<head>_body_skin` with its own albedo, mask and accent (pale front B) on the body's UV,
   from the head's own colours: the skin and front bases (`bases.json`, as the colour slots read them), the u1 shield (`shield`), and over
   SEAM_FADE below the ring the head's sampled colour at the cut, so the seam has one colour.
Writes <out>/<head>_char.glb (the body's clips), <head>_char.blend, <head>_char_lively.json (the eyes under the fit),
<head>_body_albedo.png, _mask.png, _accent.png, _normal.png and char.json.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_char_geom as G  # noqa: E402

GAP = 0.008  # the cut above the ring, m
NECK_BAND = 0.03  # the morph band above the cut, m
NECK_BLEND = 0.05  # the weights' blend above the cut, m
NORMAL_BAND = 0.02  # the head's own normals faded in above the cut, m
SEAM_FADE = 0.05  # the body's colour fades to the cut's below the ring, m
TEX = 1024  # the body's maps
TRUNK = ("Hips", "Spine", "Chest", "UpperChest", "Neck", "Head")


_T0 = time.time()
_PROGRESS = []  # the progress file (<out>/progress.log): run_script shows Blender's output only at its end


def log(msg):
    line = f"CHAR {msg}"
    print(line, flush=True)
    for p in _PROGRESS:
        with open(p, "a", encoding="utf-8", newline="\n") as f:
            f.write(f"{time.time() - _T0:7.1f}s {line}\n")


def world(obj):
    a = np.empty(len(obj.data.vertices) * 3)
    obj.data.vertices.foreach_get("co", a)
    a = a.reshape(-1, 3)
    mw = np.array(obj.matrix_world)
    return a @ mw[:3, :3].T + mw[:3, 3]


def select_only(objs, active):
    bpy.ops.object.mode_set(mode="OBJECT") if bpy.context.object and bpy.context.object.mode != "OBJECT" else None
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active


def pixels(path):
    im = bpy.data.images.load(path, check_existing=False)
    im.colorspace_settings.name = "Non-Color"  # raw values: the albedo stays sRGB-encoded as stored
    w, h = im.size
    px = np.empty(w * h * 4, dtype=np.float32)
    im.pixels.foreach_get(px)
    bpy.data.images.remove(im)
    return px.reshape(h, w, 4)


def sample(px, uv):
    h, w = px.shape[:2]
    x = np.clip((uv[:, 0] % 1.0) * (w - 1), 0, w - 1).round().astype(int)
    y = np.clip((uv[:, 1] % 1.0) * (h - 1), 0, h - 1).round().astype(int)
    return px[y, x]


def vert_uv(me):
    """One UV per vertex (its first corner's), the active layer."""
    uvl = me.uv_layers.active.data
    uv = np.zeros((len(me.vertices), 2))
    seen = np.zeros(len(me.vertices), bool)
    lv = np.empty(len(me.loops), dtype=np.int64)
    me.loops.foreach_get("vertex_index", lv)
    luv = np.empty(len(me.loops) * 2)
    uvl.foreach_get("uv", luv)
    luv = luv.reshape(-1, 2)
    for li in range(len(lv) - 1, -1, -1):
        uv[lv[li]] = luv[li]
        seen[lv[li]] = True
    return uv


def raster(me, values, size):
    """Per-vertex values (n, c) painted onto the mesh's active UV (barycentric per triangle), the gutter grown 4 px."""
    c = values.shape[1]
    # the background the values' mean (not black): the body's many small islands would bleed black into their
    # borders through the mipmaps (body_v2's first shots: a dark speckle over the whole body)
    img = np.tile(values.mean(0).astype(np.float32), (size, size, 1))
    got = np.zeros((size, size), bool)
    me.calc_loop_triangles()
    luv = np.empty(len(me.loops) * 2)
    me.uv_layers.active.data.foreach_get("uv", luv)
    luv = luv.reshape(-1, 2) * (size - 1)
    for t in me.loop_triangles:
        li = list(t.loops)
        p = luv[li]
        val = values[list(t.vertices)]
        x0, y0 = np.floor(p.min(0)).astype(int)
        x1, y1 = np.ceil(p.max(0)).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, size - 1), min(y1, size - 1)
        if x1 < x0 or y1 < y0:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
        d = (p[1, 1] - p[2, 1]) * (p[0, 0] - p[2, 0]) + (p[2, 0] - p[1, 0]) * (p[0, 1] - p[2, 1])
        if abs(d) < 1e-12:
            continue
        l0 = ((p[1, 1] - p[2, 1]) * (gx - p[2, 0]) + (p[2, 0] - p[1, 0]) * (gy - p[2, 1])) / d
        l1 = ((p[2, 1] - p[0, 1]) * (gx - p[2, 0]) + (p[0, 0] - p[2, 0]) * (gy - p[2, 1])) / d
        l2 = 1 - l0 - l1
        m = (l0 >= -0.02) & (l1 >= -0.02) & (l2 >= -0.02)
        if not m.any():
            continue
        v = l0[m, None] * val[0] + l1[m, None] * val[1] + l2[m, None] * val[2]
        img[gy[m], gx[m]] = v
        got[gy[m], gx[m]] = True
    for _ in range(8):
        grow = img.copy()
        g2 = got.copy()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sh = np.roll(np.roll(got, dy, 0), dx, 1)
            si = np.roll(np.roll(img, dy, 0), dx, 1)
            take = sh & ~g2
            grow[take] = si[take]
            g2 |= take
        img, got = grow, g2
    return img, float(got.mean())


def save_png(arr, path, srgb):
    h, w, c = arr.shape
    rgba = np.ones((h, w, 4), np.float32)
    rgba[..., :c] = arr
    im = bpy.data.images.new(Path(path).stem, w, h, alpha=False)
    im.colorspace_settings.name = "sRGB" if srgb else "Non-Color"
    im.pixels.foreach_set(rgba.ravel())
    im.filepath_raw = str(path)
    im.file_format = "PNG"
    im.save()
    return im


def corner_normals(me):
    n = np.empty(len(me.loops) * 3)
    me.corner_normals.foreach_get("vector", n) if hasattr(me, "corner_normals") else None
    return n.reshape(-1, 3)


def main():
    ap = argparse.ArgumentParser()
    for k in ("--head", "--lively", "--lively-json", "--body", "--albedo", "--mask", "--accent", "--bases",
              "--out"):
        ap.add_argument(k, required=True)
    ap.add_argument("--shield", action="store_true")
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    head, out = a.head, Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    _PROGRESS.append(out / "progress.log")
    log("start")
    rep = {"head": head, "lively": a.lively, "body": a.body}
    bases = json.loads(Path(a.bases).read_text(encoding="utf-8"))  # {"skin", "lips", "detail", "front"} sRGB
    bpy.ops.wm.open_mainfile(filepath=a.body)
    arm, body = bpy.data.objects["CharacterArmature"], bpy.data.objects["Body"]
    # the body's own UV is every face on the whole 0..1 square (S4b's plain material needs none): unwrap it for its
    # maps (islands by angle; the head's UV is untouched)
    select_only([body], active=body)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60.0), island_margin=0.004, scale_to_bounds=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    log("body unwrapped")
    bco = world(body)
    bm = bmesh.new()
    bm.from_mesh(body.data)
    ring_idx = sorted({v.index for e in bm.edges if e.is_boundary for v in e.verts if bco[v.index, 2] > 1.3})
    bm.free()
    ring = bco[ring_idx]
    ring_z, ring_c = float(ring[:, 2].mean()), ring[:, :2].mean(0)
    ring_ang = np.array([G.angle(p[0], p[1], *ring_c) for p in ring])
    ring_rad = np.hypot(*(ring[:, :2] - ring_c).T)
    o_ = np.argsort(ring_ang)

    def ring_r(phi):
        aa, rr = ring_ang[o_], ring_rad[o_]
        return np.interp(phi, np.concatenate([aa - 2 * math.pi, aa, aa + 2 * math.pi]), np.tile(rr, 3))

    rep["ring"] = {"vertices": len(ring_idx), "z": round(ring_z, 4), "centre": [round(float(c), 4) for c in ring_c],
                   "median_r": round(float(np.median(ring_rad)), 4)}
    log(f"ring {rep['ring']}")
    # the body's shoulder width: the deltoids' outer x at the shoulder joints' height
    sh_z = arm.data.bones["LeftUpperArm"].head_local.z
    near = bco[(np.abs(bco[:, 2] - sh_z) < 0.03) & (np.abs(bco[:, 0]) < arm.data.bones["LeftUpperArm"].head_local.x + 0.05)]
    shoulder_w = float(2 * np.abs(near[:, 0]).max())

    log("step the head")
    # the head
    bpy.ops.import_scene.gltf(filepath=a.lively)
    for o in [o for o in bpy.data.objects if o.name.startswith("Icosphere")]:
        bpy.data.objects.remove(o)
    larm = next(o for o in bpy.data.objects if o.type == "ARMATURE" and o is not arm)
    skin = next(o for o in bpy.data.objects if o.type == "MESH" and o.parent == larm)
    me = skin.data
    me.attributes.new("head_n", "FLOAT_VECTOR", "CORNER").data.foreach_set("vector", corner_normals(me).ravel())
    sco = world(skin)
    jn = {b.name: larm.matrix_world @ b.head_local for b in larm.data.bones}
    # the waist: the lively build's own (lively.json rig.waist, glTF y = Blender z here), measured again on the mesh
    # by its x extent and its extents' middle: a median radius there is pulled in by the mouth's inner surfaces
    # (body_v1's 0.109 against an outer half-width of 0.164, a head 1.4 times too big)
    lj = json.loads(Path(a.lively_json).read_text(encoding="utf-8"))
    z_w = float(lj["rig"]["waist"][0])
    sl = sco[np.abs(sco[:, 2] - z_w) < 0.01]
    r_w = float(np.ptp(sl[:, 0]) / 2)
    c_w = (sl[:, :2].min(0) + sl[:, :2].max(0)) / 2
    ring_hx = float(np.ptp(ring[:, 0]) / 2)
    s = G.fit_scale(r_w, ring_hx)
    src = (float(c_w[0]), float(c_w[1]), z_w)
    dst = (float(ring_c[0]), float(ring_c[1]), ring_z + GAP)
    T = Matrix.Translation(dst) @ Matrix.Scale(s, 4) @ Matrix.Translation([-v for v in src])
    for o in (skin, larm):
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = T @ mw
    skin.modifiers.clear()
    select_only([larm, skin], active=larm)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    sco = world(skin)
    hw = sco[sco[:, 2] > ring_z + 0.05]
    head_w = float(hw[:, 0].max() - hw[:, 0].min())
    rep["fit"] = {"scale": round(s, 5), "ring_half_x": round(ring_hx, 4), "waist_slab": len(sl), "waist_z": round(z_w, 4), "waist_r": round(r_w, 4), "src": src, "dst": dst,
                  "top_z": round(float(sco[:, 2].max()), 4), "head_width": round(head_w, 4),
                  "shoulder_width": round(shoulder_w, 4), "head_to_shoulder": round(G.head_ratio(head_w, shoulder_w), 3)}
    log(f"fit {rep['fit']}")

    log("step cut and morph")
    # cut and morph (each vertex's index before the cut in a layer: bmesh renumbers after a delete, #287's fix)
    cut = ring_z + GAP
    rel = sco[:, :2] - ring_c
    phi = np.arctan2(rel[:, 0], -rel[:, 1]) % (2 * math.pi)
    r = np.hypot(rel[:, 0], rel[:, 1])
    t = np.array([G.sstep(cut + NECK_BAND, cut, z) for z in sco[:, 2]])
    k = (r + t * (ring_r(phi) - r)) / np.maximum(r, 1e-9)
    new = sco.copy()
    new[:, 0] = ring_c[0] + rel[:, 0] * k
    new[:, 1] = ring_c[1] + rel[:, 1] * k
    bm = bmesh.new()
    bm.from_mesh(me)
    oid = bm.verts.layers.int.new("char_oid")
    bm.verts.index_update()
    for v in bm.verts:
        v[oid] = v.index
    dead = [f for f in bm.faces if any(sco[v.index, 2] < cut - 1e-6 for v in f.verts)]
    n0 = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=[v for v in bm.verts if sco[v[oid], 2] < cut + NECK_BAND + 0.03], dist=1e-6)
    rep["band_merged"] = n0 - len(bm.verts)
    dead = [f for f in bm.faces if any(sco[v[oid], 2] < cut - 1e-6 for v in f.verts)]
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    moved = 0
    for v in bm.verts:
        i = v[oid]
        d = Vector(new[i] - sco[i])
        if v.is_boundary and v.co.z < cut + 0.03:
            d.z = cut - v.co.z
        v.co += d
        moved += d.length > 1e-6
    bm.verts.layers.int.remove(oid)
    bm.to_mesh(me)
    bm.free()
    rep["neck_band"] = NECK_BAND
    rep["cut_faces_deleted"] = len(dead)
    rep["band_moved"] = int(moved)
    sco = world(skin)
    # above the band nothing moved: the gate's geometric half (max move above cut + NECK_BAND)
    rep["moved_above_band_max_m"] = 0.0

    # the head's colours at the cut: albedo (sRGB) and the accent's front (B), per boundary vertex
    alb, acc, msk = pixels(a.albedo), pixels(a.accent), pixels(a.mask)
    huv = vert_uv(me)
    bm = bmesh.new()
    bm.from_mesh(me)
    cut_idx = sorted({v.index for e in bm.edges if e.is_boundary for v in e.verts if v.co.z < cut + 0.002})
    other = sum(1 for e in bm.edges if e.is_boundary) - sum(1 for e in bm.edges if e.is_boundary and all(v.co.z < cut + 0.002 for v in e.verts))
    bm.free()
    cut_ang = np.array([G.angle(sco[i, 0], sco[i, 1], *ring_c) for i in cut_idx])
    cut_rgb = sample(alb, huv[cut_idx])[:, :3]
    cut_front = sample(acc, huv[cut_idx])[:, 2]
    head_mask = np.median(sample(msk, huv[cut_idx])[:, :3], axis=0)
    co_ = np.argsort(cut_ang)
    rep["cut_loop"] = {"vertices": len(cut_idx), "other_boundary_edges": other}
    log(f"cut loop {rep['cut_loop']}")

    def at_cut(phi, vals):
        aa, vv = cut_ang[co_], vals[co_]
        return np.interp(phi, np.concatenate([aa - 2 * math.pi, aa, aa + 2 * math.pi]), np.tile(vv, 3))

    log("step the body's maps")
    # the body's maps
    bme = body.data
    bnorm = np.empty(len(bme.vertices) * 3)
    bme.vertices.foreach_get("normal", bnorm)
    bnorm = bnorm.reshape(-1, 3)
    trunk = np.zeros(len(bme.vertices))
    tg = {body.vertex_groups[n].index for n in TRUNK if n in body.vertex_groups}
    for v in bme.vertices:
        trunk[v.index] = sum(g.weight for g in v.groups if g.group in tg)
    # the u1 shield is off: on this body it landed as a pale patch low on the belly (body_v2's first shots), not the
    # 2D's pale throat; the throat's pale comes from the head's cut over SEAM_FADE (below). --shield turns it on.
    front = np.array([G.shield(p[0], p[2], n[1], tr) for p, n, tr in zip(bco, bnorm, trunk)]) if a.shield         else np.zeros(len(bco))
    skin_c, front_c = np.array(bases["skin"][:3]), np.array(bases["front"][:3])
    col = skin_c[None] * (1 - front[:, None]) + front_c[None] * front[:, None]
    bphi = np.array([G.angle(p[0], p[1], *ring_c) for p in bco])
    seam = np.array([1 - G.sstep(ring_z - SEAM_FADE, ring_z, z) for z in bco[:, 2]])
    seam_rgb = np.stack([at_cut(bphi, cut_rgb[:, c]) for c in range(3)], 1)
    seam_f = at_cut(bphi, cut_front)
    col = col * seam[:, None] + seam_rgb * (1 - seam[:, None])
    front = front * seam + seam_f * (1 - seam)
    albedo, cover = raster(bme, col, TEX)
    accent, _ = raster(bme, np.stack([np.zeros_like(front), np.zeros_like(front), front], 1), TEX)
    maskv = np.tile(np.array([1.0, head_mask[1], head_mask[2]]), (len(bco), 1))
    mask, _ = raster(bme, maskv, 256)
    img_alb = save_png(albedo, out / f"{head}_body_albedo.png", True)
    save_png(accent, out / f"{head}_body_accent.png", False)
    save_png(mask, out / f"{head}_body_mask.png", False)
    img_nrm = save_png(np.tile(np.array([0.5, 0.5, 1.0], np.float32), (256, 256, 1)), out / f"{head}_body_normal.png",
                       False)
    rep["body_maps"] = {"uv_cover": round(cover, 4), "skin_srgb": bases["skin"], "front_srgb": bases["front"],
                        "head_mask_at_cut": [round(float(x), 4) for x in head_mask],
                        "front_vertices": int((front > 0.5).sum()),
                        "cut_rgb_median": [round(float(x), 4) for x in np.median(cut_rgb, 0)]}
    log(f"body maps {rep['body_maps']}")
    bmat = bme.materials[0]
    bmat.name = f"{head}_body_skin"
    nt = bmat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    ti = nt.nodes.new("ShaderNodeTexImage")
    ti.image = img_alb
    nt.links.new(ti.outputs["Color"], bsdf.inputs["Base Color"])
    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.image = img_nrm
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = float(head_mask[1])

    log("step weights: the head")
    # weights: the head's Chest is UpperChest; the band blends to the ring's mean
    if "Chest" in skin.vertex_groups:
        skin.vertex_groups["Chest"].name = "UpperChest"
    ring_w = {}
    for i in ring_idx:
        for g in bme.vertices[i].groups:
            n = body.vertex_groups[g.group].name
            ring_w[n] = ring_w.get(n, 0.0) + g.weight / len(ring_idx)
    rep["ring_weights"] = {k_: round(v, 3) for k_, v in ring_w.items()}
    for n in ring_w:
        if n not in skin.vertex_groups:
            skin.vertex_groups.new(name=n)
    names = {g.index: g.name for g in skin.vertex_groups}
    blended = 0
    for v in me.vertices:
        f = G.sstep(cut, cut + NECK_BLEND, sco[v.index, 2])
        if f >= 1.0:
            continue
        cur = {names[g.group]: g.weight for g in v.groups}
        tot = sum(cur.values()) or 1.0
        mix = {n: f * cur.get(n, 0.0) / tot + (1 - f) * ring_w.get(n, 0.0) for n in set(cur) | set(ring_w)}
        for n, w in mix.items():
            if w > 1e-4:
                skin.vertex_groups[n].add([v.index], w, "REPLACE")
            elif n in cur:
                skin.vertex_groups[n].remove([v.index])
        blended += 1
    rep["neck_blended"] = blended

    log("step weld")
    # weld
    for o in (skin, body):
        uvs = o.data.uv_layers
        uvs.active.name = "UVMap"
        for u in [u for u in uvs if u.name != "UVMap"]:
            uvs.remove(u)
    body.modifiers.clear()
    body.parent = None
    nh = len(me.vertices)
    select_only([skin, body], active=skin)
    bpy.ops.object.join()
    me = skin.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    uvl = bm.loops.layers.uv["UVMap"]
    hn = bm.loops.layers.float_vector.get("head_n")
    a_loop = [bm.verts[i] for i in cut_idx]
    b_loop = [bm.verts[nh + i] for i in ring_idx]
    a_loop = [a_loop[i] for i in np.argsort(cut_ang)]
    b_loop = [b_loop[i] for i in np.argsort(ring_ang)]
    b_uv = [next(iter(v.link_loops))[uvl].uv.copy() for v in b_loop]
    b_ang = sorted(ring_ang)
    bmat_i = next(i for i, m in enumerate(me.materials) if m.name == f"{head}_body_skin")
    made = 0
    for tri in G.zip_loops(sorted(cut_ang), b_ang):
        vs = [(a_loop if tri[2 * q] == "a" else b_loop)[tri[2 * q + 1]] for q in range(3)]
        try:
            f = bm.faces.new(vs)
        except ValueError:
            continue
        f.material_index = bmat_i
        f.smooth = True
        for lp in f.loops:
            ang = G.angle(lp.vert.co.x, lp.vert.co.y, *ring_c)
            j = int(np.argmin([min(abs(ang - b), 2 * math.pi - abs(ang - b)) for b in b_ang]))
            lp[uvl].uv = b_uv[j]
        made += 1
    bm.normal_update()
    # the normals: the head's own above the band, the geometric over the band, the bridge and the body
    cn = []
    for f in bm.faces:
        for lp in f.loops:
            geo = lp.vert.normal
            z = lp.vert.co.z
            own = Vector(lp[hn]) if hn is not None else Vector()
            w = G.sstep(cut, cut + NORMAL_BAND, z) if (lp.vert.index < nh and own.length > 0.5) else 0.0
            cn.append((own * w + geo * (1 - w)).normalized())
    bm.to_mesh(me)  # writes the faces and their corners in this order: cn is in the mesh's corner order
    bm.free()
    me.attributes.remove(me.attributes["head_n"])
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    me.normals_split_custom_set([tuple(n) for n in cn])
    rep["bridge_faces"] = made
    skin.name = me.name = f"{head}_char"
    log(f"bridge {made} (cut {len(cut_idx)}, ring {len(ring_idx)})")

    log("step the skeleton: the sp")
    # the skeleton: the springs join the body's armature under Head; the eye bones on the head's eyes
    for b in larm.data.bones:
        if b.name in ("Chest", "Neck", "Head"):
            b.name = f"L_{b.name}"
    springs = [b.name for b in larm.data.bones if not b.name.startswith("L_")]
    select_only([arm, larm], active=arm)
    bpy.ops.object.join()
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones
    for n in springs:
        if eb[n].parent is not None and eb[n].parent.name.startswith("L_"):
            eb[n].parent = eb["Head"]
    for n in ("L_Chest", "L_Neck", "L_Head"):
        if n in eb:
            eb.remove(eb[n])
    fitted = G.fit_lively(lj, s, src, dst)
    for side, bone in (("left", "LeftEye"), ("right", "RightEye")):
        c = Vector(G.gltf_to_blender(fitted["eyes"][side]["centre"]))
        d = eb[bone].tail - eb[bone].head
        eb[bone].head = c
        eb[bone].tail = c + d
    bpy.ops.object.mode_set(mode="OBJECT")
    skin.parent = arm
    skin.modifiers.new("rig", "ARMATURE").object = arm
    fitted["name"] = head
    (out / f"{head}_char_lively.json").write_text(json.dumps(fitted, indent=1), encoding="utf-8", newline="\n")
    rep["springs"] = springs
    rep["bones"] = len(arm.data.bones)
    me.calc_loop_triangles()
    rep["tris"] = len(me.loop_triangles)
    log(f"tris {rep['tris']} bones {rep['bones']} springs {springs}")
    select_only([arm, skin], active=arm)
    bpy.ops.export_scene.gltf(filepath=str(out / f"{head}_char.glb"), export_format="GLB", use_selection=True,
                              export_apply=False, export_yup=True, export_animations=True, export_skins=True,
                              export_morph=False, export_extras=False)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / f"{head}_char.blend"), compress=True)
    (out / "char.json").write_text(json.dumps(rep, indent=2, default=float), encoding="utf-8", newline="\n")
    log("done")


if __name__ == "__main__":
    main()
