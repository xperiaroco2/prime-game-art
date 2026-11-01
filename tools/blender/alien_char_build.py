"""A lively pilot head on the shared alien body (art #196, steps B1 to B4): one skinned character, `<head>_char.glb`.

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
   distance from the axis blends toward the ring's ellipse at its angle, the boundary flat on the cut. E1 (`--neck-band
   flare`, D3's bodies): instead the neck flares into the ring over 70 mm from it (`body_fit_geom.neck_flare_morph`,
   the ring ADR's "Join"), as the review's seat_head does; the bridge then closes the GAP at the flare's own slope.
3. Weld: joined with the body, the cut and the ring zipped by angle (`zip_loops`; the counts differ), the new row
   on the body's material with the ring's UVs.
4. Normals: the head's own corner normals kept above the band (a corner attribute through the cut and the join),
   the geometric smooth normals over the band, the bridge and the body: no lighting seam. The head's own fade in
   from the cut over NORMAL_BAND (the weld) or over the whole flare (`--neck-band flare`: the morph reshapes the
   neck up to 70 mm above the ring, so the head's pre-morph normals belong to its old neck below that;
   `alien_char_geom.normal_top`).
5. Weights: the head's Neck and Head groups are the body's; its Chest goes to UpperChest; over NECK_BLEND above the
   cut the weights blend to the ring's mean, so the neck bends as one. The spring bones (Crest1-3 or Gill*) join
   the body's armature under its Head; the eye bones move to the head's eye centres.
6. The body's material set: `<head>_body_skin` with its own albedo, mask, detail and accent (pale front B) on the
   body's UV, from the head's own colours: the head's skin and front region medians (`bases.json` body_skin and
   body_front, the colour slots' `<head>_regions.json`) with a faint low-frequency value variation, the 2D's pale
   front (B3: `throat_fade`, a soft tongue from the throat to the sternum, evaluated per texel from the rastered
   positions, so its edges follow no triangle), and over SEAM_FADE below the ring the head's
   sampled colour at the cut, so the seam has one colour. The detail map is the head's at the cut (thick skin: no
   transmission; r2's body had none, the shader's white default, so the whole body was "thin": lighter and speckled).
B2 (art #196): the body's neck flares into its shoulders (`flare_radius`, below the ring only); the bridge's
triangles face outward (`bridge_outward`; r2's were inward, culled in Godot: the dark ring) and each takes its ring
vertex's UV (one texel per triangle, no stretch across the body's UV islands); `seam` in char.json counts the open
and non-manifold edges round the seam (0 expected).
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
SEAM_REACH = 1.5  # clothes step 2: the seam's smoothing within this many ring radii of the neck's axis
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
    for _ in range(16):
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


GILL_ZETA_ON_BODY = 0.55  # A2: the axolotl's gills on the walking body (anim_bare/a2: Jog and Sprint jitter 205-267 deg/s)


def _rows(me, owned):
    """The vertices outside the gills (positions) and the corners of the faces wholly outside them (position, every
    UV layer's uv, head_n). F1: a face on the gills' border (an outside vertex beside gill ones) is the decimation's to
    collapse, so its corners are not counted; its outside vertices still must not move."""
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    lv = np.empty(len(me.loops), dtype=np.int64)
    me.loops.foreach_get("vertex_index", lv)
    cols = [co[lv]]
    for layer in me.uv_layers:
        uv = np.empty(len(me.loops) * 2)
        layer.data.foreach_get("uv", uv)
        cols.append(uv.reshape(-1, 2))
    if "head_n" in me.attributes:
        hn = np.empty(len(me.loops) * 3)
        me.attributes["head_n"].data.foreach_get("vector", hn)
        cols.append(hn.reshape(-1, 3))
    keep = ~np.asarray(owned, dtype=bool)
    start = np.empty(len(me.polygons), dtype=np.int64)
    me.polygons.foreach_get("loop_start", start)
    total = np.empty(len(me.polygons), dtype=np.int64)
    me.polygons.foreach_get("loop_total", total)
    gill_face = np.add.reduceat((~keep[lv]).astype(np.int64), start) > 0 if len(start) else np.zeros(0, dtype=bool)
    outside_loop = ~np.repeat(gill_face, total)
    return co[keep].tolist(), np.hstack(cols)[outside_loop].tolist()


def _owned(skin) -> list[bool]:
    """Each vertex: is its largest weight a Gill* group's."""
    gills = {g.index for g in skin.vertex_groups if g.name.startswith("Gill")}
    return [bool(v.groups) and max(v.groups, key=lambda g: g.weight).group in gills for v in skin.data.vertices]


def lighten_gills(skin, keep: float) -> dict:
    """M1 (art #196): collapse-decimate the faces whose vertices the Gill* groups own (each vertex's largest weight),
    down to `keep` of their triangles; every other vertex has weight 0 in the decimation group. The ratio is the
    whole mesh's, from the gills' share (G.gill_decimate_ratio).
    R1: measured, not assumed. Every vertex outside the gills must keep its position, and each corner of a face
    wholly outside them its UVs and head_n, exactly (G.missing_rows, counted since F1); the build fails if one moved. The gills' triangles after are counted
    on the result (the faces whose vertices the Gill* groups own)."""
    me = skin.data
    own = _owned(skin)
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    gill_tris = sum(len(p.vertices) - 2 for p in me.polygons if all(own[i] for i in p.vertices))
    v_before, c_before = _rows(me, own)
    vg = skin.vertex_groups.new(name="_gill_dec")
    vg.add([i for i, o in enumerate(own) if o], 1.0, "REPLACE")
    mod = skin.modifiers.new("gill_dec", "DECIMATE")
    mod.decimate_type, mod.vertex_group, mod.ratio = "COLLAPSE", vg.name, G.gill_decimate_ratio(tris, gill_tris, keep)
    select_only([skin], active=skin)
    bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=0)  # before the armature's
    bpy.ops.object.modifier_apply(modifier=mod.name)
    skin.vertex_groups.remove(skin.vertex_groups["_gill_dec"])  # (vg is stale after the apply: M1d's run read junk)
    me = skin.data
    after = sum(len(p.vertices) - 2 for p in me.polygons)
    own_a = _owned(skin)
    gill_after = sum(len(p.vertices) - 2 for p in me.polygons if all(own_a[i] for i in p.vertices))
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    _, c_after = _rows(me, [False] * len(me.vertices))
    moved = G.missing_rows(v_before, co.reshape(-1, 3).tolist())
    corners = G.missing_rows(c_before, c_after)  # F1: counts too (a multiset), not only the set of rows
    v_out_after, c_out_after = _rows(me, own_a)
    rep = {"keep": keep, "tris_before": tris, "gill_tris_before": gill_tris, "tris_after": after,
           "gill_tris_after": gill_after, "gill_keep_measured": round(gill_after / max(gill_tris, 1), 4),
           "outside_vertices": len(v_before), "outside_vertices_after": len(v_out_after), "outside_moved": moved,
           "outside_corners": len(c_before), "outside_corners_after": len(c_out_after),
           "outside_corners_changed": corners}
    if moved or corners:
        raise RuntimeError(f"lighten_gills: {moved} vertices and {corners} corners outside the gills changed {rep}")
    return rep


def main():
    ap = argparse.ArgumentParser()
    for k in ("--head", "--lively", "--lively-json", "--body", "--albedo", "--mask", "--accent", "--detail",
              "--bases", "--out"):
        ap.add_argument(k, required=True)
    ap.add_argument("--shield", action="store_true")
    ap.add_argument("--clip-edits", default="", help="A1: the alien's clip edits (anim_sets/alien.toml)")
    ap.add_argument("--no-seam-smooth", action="store_true", help="clothes step 2: the weld without the seam's "
                    "smoothing (the builds before it)")
    ap.add_argument("--neck-band", default="smooth", choices=("smooth", "flare"), help="E1: the head's neck onto "
                    "the ring: smooth, NECK_BAND's 30 mm smoothstep above the cut (the old bodies); flare, "
                    "body_fit_geom.neck_flare_morph over NECK_FLARE_BAND from the ring (D3's bodies, the ring ADR)")
    ap.add_argument("--no-flare", action="store_true", help="M1: no neck flare (a Meshy body has its own trapezius)")
    ap.add_argument("--leg-fit", default="", help="T2: the .blend of the rig the clips were made on (S4b's body): "
                    "the clips' hip keys scaled to this body's leg length and the feet's lowest point matched per frame (alien_leg_fit.py)")
    ap.add_argument("--leg-fit-mode", default="lowest", choices=("lowest", "ik"), help="T3: with --leg-fit, "
                    "'ik' puts the feet on the donor's foot paths scaled to the legs (alien_leg_fit.py)")
    ap.add_argument("--gill-ratio", type=float, default=1.0, help="M1: the gills' share of their triangles kept "
                    "(collapse decimation on the faces the Gill* groups own; 1.0: untouched)")
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
    bpy.ops.uv.smart_project(angle_limit=math.radians(80.0), island_margin=0.012, scale_to_bounds=True)
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
    # B2: the neck's flare into the shoulders (the 2D's trapezius), on the body below the ring only
    depth = float(ring_z - sh_z)
    extra = float(0.75 * shoulder_w / 2 - np.ptp(ring[:, 0]) / 2)
    armg = {g.index for g in body.vertex_groups if any(k in g.name for k in ("Shoulder", "Arm", "Hand"))}
    mw_b = np.array(body.matrix_world)
    inv_b = np.linalg.inv(mw_b)
    moved_f = 0
    for v in [] if a.no_flare else body.data.vertices:
        p = bco[v.index]
        dz = ring_z - p[2]
        if dz <= 0.0 or dz > depth * 1.4:
            continue
        rel_ = p[:2] - ring_c
        r0 = float(np.hypot(*rel_))
        if r0 < 1e-6:
            continue
        ph = G.angle(p[0], p[1], *ring_c)
        arm_w = sum(g.weight for g in v.groups if g.group in armg)
        r1 = G.flare_radius(r0, float(ring_r(ph)), dz, ph, depth, extra, arm_w)
        if r1 - r0 > 1e-6:
            q = p.copy()
            q[:2] = ring_c + rel_ * (r1 / r0)
            v.co = Vector((inv_b @ np.append(q, 1.0))[:3])
            moved_f += 1
    body.data.update()
    bco = world(body)
    rep["flare"] = {"off": a.no_flare, "depth_m": round(depth, 4), "extra_m": round(extra, 4), "moved": moved_f}
    log(f"flare {rep['flare']}")

    log("step the head")
    # the head
    bpy.ops.import_scene.gltf(filepath=a.lively)
    for o in [o for o in bpy.data.objects if o.name.startswith("Icosphere")]:
        bpy.data.objects.remove(o)
    larm = next(o for o in bpy.data.objects if o.type == "ARMATURE" and o is not arm)
    skin = next(o for o in bpy.data.objects if o.type == "MESH" and o.parent == larm)
    me = skin.data
    me.attributes.new("head_n", "FLOAT_VECTOR", "CORNER").data.foreach_set("vector", corner_normals(me).ravel())
    if a.gill_ratio < 1.0:  # M1: the gills lighter, their own corner normals (head_n) interpolated, the rest kept
        rep["gills"] = lighten_gills(skin, a.gill_ratio)
        log(f"gills {rep['gills']}")
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
    if a.neck_band == "flare":  # E1: the ring ADR's "Join", the review's seat_head: one continuous neck flare
        import body_fit_geom as F
        mm, info = F.neck_flare_morph([tuple(float(c) * 1000 for c in p) for p in sco],
                                      [tuple(e.vertices) for e in me.edges],
                                      [tuple(float(c) * 1000 for c in p) for p in ring], F.NECK_FLARE_BAND,
                                      F.NECK_FLARE_A)
        new = np.array(mm) / 1000.0
        rep["neck_flare"] = info
        band_top = ring_z + F.NECK_FLARE_BAND / 1000.0
    else:  # the old weld: a 30 mm smoothstep onto the ring's ellipse above the cut
        t = np.array([G.sstep(cut + NECK_BAND, cut, z) for z in sco[:, 2]])
        k = (r + t * (ring_r(phi) - r)) / np.maximum(r, 1e-9)
        new = sco.copy()
        new[:, 0] = ring_c[0] + rel[:, 0] * k
        new[:, 1] = ring_c[1] + rel[:, 1] * k
        band_top = cut + NECK_BAND
    # the height from which the head keeps its own normals (E1m: over the whole flare, not NORMAL_BAND's 20 mm)
    normal_top = G.normal_top(cut, NORMAL_BAND, band_top if a.neck_band == "flare" else None)
    bm = bmesh.new()
    bm.from_mesh(me)
    oid = bm.verts.layers.int.new("char_oid")
    bm.verts.index_update()
    for v in bm.verts:
        v[oid] = v.index
    dead = [f for f in bm.faces if any(sco[v.index, 2] < cut - 1e-6 for v in f.verts)]
    n0 = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=[v for v in bm.verts if sco[v[oid], 2] < band_top + 0.03], dist=1e-6)
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
    rep["neck_band"] = a.neck_band if a.neck_band == "flare" else NECK_BAND
    rep["cut_faces_deleted"] = len(dead)
    rep["band_moved"] = int(moved)
    # the gate's geometric half, measured: the farthest move of a vertex above the band's top (E1m; it was a fixed 0.0)
    rep["moved_above_band_max_m"] = round(G.moved_above(sco.tolist(), new.tolist(), band_top), 6)
    rep["normal_top_above_ring_m"] = round(normal_top - ring_z, 4)
    sco = world(skin)

    # the head's colours at the cut: albedo (sRGB) and the accent's front (B), per boundary vertex
    alb, acc, msk, det = pixels(a.albedo), pixels(a.accent), pixels(a.mask), pixels(a.detail)
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
    head_detail = np.median(sample(det, huv[cut_idx])[:, :4], axis=0)
    # the throat's pale width at the cut: the front's cut vertices' largest |x| from the axis
    fr = np.array([abs(sco[i, 0] - ring_c[0]) for i, f_ in zip(cut_idx, cut_front) if f_ > 0.5])
    top_hw = float(fr.max()) if len(fr) else 0.0
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
    bnorm = bnorm.reshape(-1, 3) @ mw_b[:3, :3].T  # world normals (the front faces -Y in the world)
    bnorm /= np.maximum(np.linalg.norm(bnorm, axis=1, keepdims=True), 1e-9)
    trunk = np.zeros(len(bme.vertices))
    tg = {body.vertex_groups[n].index for n in TRUNK if n in body.vertex_groups}
    for v in bme.vertices:
        trunk[v.index] = sum(g.weight for g in v.groups if g.group in tg)
    bphi = np.array([G.angle(p[0], p[1], *ring_c) for p in bco])
    seam = np.array([1 - G.sstep(ring_z - SEAM_FADE, ring_z, z) for z in bco[:, 2]])
    seam_rgb = np.stack([at_cut(bphi, cut_rgb[:, c]) for c in range(3)], 1)
    seam_f = at_cut(bphi, cut_front)
    skin_c = np.array(bases.get("body_skin", bases["skin"])[:3])
    front_c = np.array(bases.get("body_front", bases["front"])[:3])
    # a faint low-frequency value variation (the head's skin is never one flat colour): smooth waves 6 to 14 cm
    wv = (np.sin(bco @ np.array([41.0, 13.0, 29.0]) + 1.3) + np.sin(bco @ np.array([-17.0, 47.0, 23.0]) + 0.4)
          + np.sin(bco @ np.array([19.0, -31.0, 71.0]) + 2.1)) / 3.0
    # B3: the pale front per texel. The u1 shield (--shield) and B2's panel were per vertex and filtered by the
    # normal's direction (the panel dropped the upward-facing upper chest: r3's horizontal band); the throat's tongue
    # is evaluated per texel from the rastered position and the angle round the neck axis, so no triangle shows.
    if a.shield:
        sh = np.array([G.shield(p[0], p[2], n[1], tr) for p, n, tr in zip(bco, bnorm, trunk)])
    else:
        sh = np.zeros(len(bco))
    per = np.concatenate([bco, np.cos(bphi)[:, None], seam[:, None], seam_f[:, None], seam_rgb, wv[:, None],
                          sh[:, None]], 1)
    tex, cover = raster(bme, per, TEX)
    t = tex.reshape(-1, tex.shape[2])
    if a.shield:
        tf = t[:, 10]
    else:
        tf = np.vectorize(lambda x, z, c: G.throat_fade(x - ring_c[0], ring_z - z, c, top_hw), otypes=[float])(
            t[:, 0], t[:, 2], t[:, 3])
    tf = np.clip(tf, 0.0, 1.0)
    sw = t[:, 4:5]
    front_t = tf * sw[:, 0] + t[:, 5] * (1 - sw[:, 0])
    col = (skin_c[None] * (1 - tf[:, None]) + front_c[None] * tf[:, None]) * (1.0 + 0.018 * t[:, 9:10])
    col = col * sw + t[:, 6:9] * (1 - sw)
    albedo = col.reshape(TEX, TEX, 3)
    accent = np.stack([np.zeros_like(front_t), np.zeros_like(front_t), front_t], 1).reshape(TEX, TEX, 3)
    front = front_t
    maskv = np.tile(np.array([1.0, head_mask[1], head_mask[2]]), (len(bco), 1))
    mask, _ = raster(bme, maskv, 256)
    detail, _ = raster(bme, np.tile(head_detail, (len(bco), 1)), 256)
    save_png(detail, out / f"{head}_body_detail.png", False)
    img_alb = save_png(albedo, out / f"{head}_body_albedo.png", True)
    save_png(accent, out / f"{head}_body_accent.png", False)
    save_png(mask, out / f"{head}_body_mask.png", False)
    img_nrm = save_png(np.tile(np.array([0.5, 0.5, 1.0], np.float32), (256, 256, 1)), out / f"{head}_body_normal.png",
                       False)
    rep["body_maps"] = {"uv_cover": round(cover, 4), "skin_srgb": bases["skin"], "front_srgb": bases["front"],
                        "head_mask_at_cut": [round(float(x), 4) for x in head_mask],
                        "head_detail_at_cut": [round(float(x), 4) for x in head_detail],
                        "throat_half_width": round(top_hw, 4), "body_skin_srgb": [float(x) for x in skin_c],
                        "front_texel_share": round(float((front > 0.5).mean()), 5),
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
    b_loop = [bm.verts[nh + i] for i in ring_idx]
    b_loop = [b_loop[i] for i in np.argsort(ring_ang)]
    # the cut row in its walk order round the boundary, not by sorted angle: where it folds back on itself, sorting
    # zipped across it (r3's first chameleon build: 6 open and 8 three-face edges); its angles made monotone
    cut_set = set(cut_idx)
    walk = G.walk_loop([(e.verts[0].index, e.verts[1].index) for e in bm.edges if e.is_boundary
                        and e.verts[0].index in cut_set and e.verts[1].index in cut_set])
    wa = [G.angle(bm.verts[i].co.x, bm.verts[i].co.y, *ring_c) for i in walk]
    if sum(((wa[(k + 1) % len(wa)] - wa[k] + math.pi) % (2 * math.pi)) - math.pi for k in range(len(wa))) < 0:
        walk, wa = walk[::-1], wa[::-1]  # the walk goes round in the increasing sense
    a_loop = [bm.verts[i] for i in walk]
    a_ang = G.monotone_angles(wa)
    b_uv = [next(iter(v.link_loops))[uvl].uv.copy() for v in b_loop]
    b_ang = sorted(ring_ang)
    bmat_i = next(i for i, m in enumerate(me.materials) if m.name == f"{head}_body_skin")
    made = flipped = skipped = 0
    bridge: list = []
    for tri in G.zip_loops(a_ang, b_ang):
        vs = [(a_loop if tri[2 * q] == "a" else b_loop)[tri[2 * q + 1]] for q in range(3)]
        try:
            f = bm.faces.new(vs)
        except ValueError:
            skipped += 1
            continue
        f.material_index = bmat_i
        f.smooth = True
        f.normal_update()
        if not G.bridge_outward(f.normal, f.calc_center_median(), ring_c):
            f.normal_flip()
            flipped += 1
        # one UV for the whole triangle: its ring vertex's (the seam fade paints the ring in the cut's colour)
        jb = next(tri[2 * q + 1] for q in range(3) if tri[2 * q] == "b")
        for lp in f.loops:
            lp[uvl].uv = b_uv[jb]
        made += 1
        bridge.append(f)
    # B4: each bridge triangle wound as its outside neighbour (the head band's or the body's face across its loop
    # edge): the facing test above alone left wrongly wound edges
    rewound, bridge_ids = 0, set(bridge)
    for f in bridge:
        for e in f.edges:
            other = [x for x in e.link_faces if x is not f and x not in bridge_ids]
            if len(e.link_faces) == 2 and other and not e.is_contiguous:
                f.normal_flip()
                rewound += 1
                break
    bm.normal_update()
    # the seam closed: no open or non-manifold edge from just below the ring to just above the cut
    zone = [e for e in bm.edges if all(ring_z - 0.01 < v.co.z < cut + 0.01 for v in e.verts)]
    rep["seam"] = {"edges": len(zone), "open": sum(e.is_boundary for e in zone),
                   "non_manifold": sum(not e.is_manifold for e in zone), "flipped": flipped, "skipped": skipped,
                   "rewound": rewound, "wound": sum(e.is_manifold and not e.is_contiguous for e in zone),
                   "open_at": [[round(v.co.z - cut, 4), round(G.angle(v.co.x, v.co.y, *ring_c), 3), v.index < nh,
                                len(e.link_faces)] for e in zone if not e.is_manifold for v in e.verts][:24]}
    log(f"seam {rep['seam']}")
    if rep["seam"]["open"] or rep["seam"]["non_manifold"] or rep["seam"]["wound"]:  # B4: a seam not closed fails
        raise RuntimeError(f"the seam is not closed: {rep['seam']}")
    # clothes step 2: the sewn line softened (alien_char_geom.taubin over seam_weight's band round the bridge)
    if not a.no_seam_smooth:
        mid = (ring_z + cut) / 2
        reach = (SEAM_REACH * rep["ring"]["median_r"]) ** 2  # the neck only, never the shoulders' tops
        sv = [v for v in bm.verts if G.seam_weight(v.co.z, mid) > 0.0
              and (v.co.x - ring_c[0]) ** 2 + (v.co.y - ring_c[1]) ** 2 < reach]
        pos = {v.index: k for k, v in enumerate(sv)}
        fixed = [e.other_vert(v) for v in sv for e in v.link_edges if e.other_vert(v).index not in pos]
        extra = {u.index: len(sv) + k for k, u in enumerate(dict.fromkeys(fixed))}
        allv = sv + list(dict.fromkeys(fixed))
        nb = [[pos.get(e.other_vert(v).index, extra.get(e.other_vert(v).index)) for e in v.link_edges] for v in sv]
        nb += [[] for _ in extra]
        w = [G.seam_weight(v.co.z, mid) for v in sv] + [0.0] * len(extra)
        new = G.taubin([list(v.co) for v in allv], nb, w)
        moved = 0.0
        for v, q in zip(sv, new):
            moved = max(moved, (Vector(q) - v.co).length)
            v.co = Vector(q)
        bm.normal_update()
        rep["seam_smooth"] = {"vertices": len(sv), "max_move_m": round(moved, 5), "mid_z": round(mid, 4),
                              "band_m": list(G.SEAM_SMOOTH), "iters": G.SEAM_ITERS}
        log(f"seam smooth {rep['seam_smooth']}")
    # the normals: the head's own above the band, the geometric over the band, the bridge and the body
    cn = []
    for f in bm.faces:
        for lp in f.loops:
            geo = lp.vert.normal
            z = lp.vert.co.z
            own = Vector(lp[hn]) if hn is not None else Vector()
            w = G.sstep(cut, normal_top, z) if (lp.vert.index < nh and own.length > 0.5) else 0.0
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
    for sp in fitted["rig"].get("springs", []):  # A2: on the body a run's bob made the gills (zeta 0.28) jitter
        if sp["name"].startswith("Gill"):
            sp["zeta"] = max(float(sp["zeta"]), GILL_ZETA_ON_BODY)
    (out / f"{head}_char_lively.json").write_text(json.dumps(fitted, indent=1), encoding="utf-8", newline="\n")
    rep["springs"] = springs
    rep["bones"] = len(arm.data.bones)
    rep["heights"] = heights(skin, arm, springs)
    log(f"heights {rep['heights']}")
    me.calc_loop_triangles()
    rep["tris"] = len(me.loop_triangles)
    log(f"tris {rep['tris']} bones {rep['bones']} springs {springs}")
    if a.leg_fit:  # T2: the clips fitted to this body's legs (alien_leg_fit.py), before the clip edits
        import alien_leg_fit
        acts = [x for x in bpy.data.actions if x.name.startswith("CharacterArmature|")]
        bob = {}
        if a.clip_edits:  # B1c: a clip's leg_fit_bob (alien.toml) scales its Hips' bob before the IK
            import alien_clip_edit
            for x in acts:
                n = x.name.split("|", 1)[-1]
                bob[n] = float(alien_clip_edit.settings(a.clip_edits, n).get("leg_fit_bob", 1.0))
        rep["leg_fit"] = alien_leg_fit.fit(arm, a.leg_fit, acts, mode=a.leg_fit_mode, bob=bob)
        log(f"leg fit {json.dumps(rep['leg_fit'])}")
    if a.clip_edits:  # A1: the clips edited for the bare alien body (alien_clip_edit.py) before the export
        import alien_clip_edit
        rep["clip_edits"] = {"settings": a.clip_edits, "clips": alien_clip_edit.apply(arm, skin, a.clip_edits)}
        log(f"clip edits {json.dumps(rep['clip_edits']['clips'], default=float)}")
    select_only([arm, skin], active=arm)
    bpy.ops.export_scene.gltf(filepath=str(out / f"{head}_char.glb"), export_format="GLB", use_selection=True,
                              export_apply=False, export_yup=True, export_animations=True, export_skins=True,
                              export_morph=False, export_extras=False)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / f"{head}_char.blend"), compress=True)
    (out / "char.json").write_text(json.dumps(rep, indent=2, default=float), encoding="utf-8", newline="\n")
    log("done")


def heights(skin, arm, springs: list[str]) -> dict:
    """B4 review (b), measured, nothing rescaled: the rest heights above the feet (m, Blender Z up, the lowest vertex
    as 0) of the whole character, the body without the head (the vertices with no Head, eye or spring weight), the
    skull (mostly Head-weighted vertices), the springs' crest or gills (mostly spring-weighted vertices) and the eye
    bones, for the 1.80 m capsule."""
    names = {g.index: g.name for g in skin.vertex_groups}
    mw = skin.matrix_world
    zs: dict[str, list[float]] = {"all": [], "body": [], "skull": [], "springs": []}
    for v in skin.data.vertices:
        z = (mw @ v.co).z
        w = {names[g.group]: g.weight for g in v.groups if g.weight > 0.0}
        sw = sum(x for n, x in w.items() if n in springs)
        hw = w.get("Head", 0.0) + w.get("LeftEye", 0.0) + w.get("RightEye", 0.0)
        zs["all"].append(z)
        if sw >= 0.5:
            zs["springs"].append(z)
        elif hw >= 0.5:
            zs["skull"].append(z)
        if sw == 0.0 and hw == 0.0:
            zs["body"].append(z)
    low = min(zs["all"])
    out = {f"{k}_top_m": round(max(v) - low, 4) for k, v in zs.items() if v}
    for b in ("LeftEye", "RightEye"):
        out[f"{b}_m"] = round((arm.matrix_world @ arm.data.bones[b].head_local).z - low, 4)
    out["capsule_m"] = 1.80
    out["over_capsule_m"] = round(out["all_top_m"] - 1.80, 4)
    return out


if __name__ == "__main__":
    main()
