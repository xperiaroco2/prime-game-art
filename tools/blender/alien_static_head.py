"""The alien pilot's static premium heads (art #196, 2026-10-22): one Meshy head kept as Meshy sculpted it (no cut-out
and glued-back lips or lids), only decimated, with premium texture maps and a skin tint mask. Headless Blender only
(tools/runner/blender.py). Reads the raw GLBs (never writes them) and writes into --out:
- `<head>_static.glb`, `<head>_static_lod1.glb`, `<head>_static.blend`;
- `<head>_albedo.png` (baked at 4096, kept at 2048 for the contract, sRGB): Meshy's skin graded to the 2D's teal and mint (step 2a's palette ramp, the
  chameleon's crest stripes), Meshy's own painted eyes kept (sclera cleaned, iris a little richer);
- `<head>_normal.png` (2048, tangent, from the dense original; the crest-root ledge and the eyes flattened);
- `<head>_mask.png` (2048, linear): R the skin tint mask (1 skin, 0 eyes), G roughness, B subsurface and sheen weight;
- `<head>_detail.png` (2048, linear RGBA, static_v2): R the cavity (ambient occlusion of the dense original, 1 open),
  G the thinness (its inside occlusion: gills, crest, lips), B the flush region (lips, lids), A the eyes' limbal ring;
- `base_choice/`: Workbench views of this build and of step 2a's v2 build for the base-choice sheet;
- `blender_front.png`: a Cycles front render of the final material; `build.json` (counts, colour diagnosis).

    run_script("alien_static_head.py", ["--head", "chameleon", "--src", <remeshed GLB>, "--dense", <dense GLB>,
               "--ref", <step 2a v2 build.json>, "--v2", <step 2a v2 GLB>, "--view2d", <2D views dir>, "--out", <dir>])
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

TRIS = {"chameleon": 32000, "axolotl": 40000}
# static_v2: the decimation keeps more of the budget on the lips and lid rims. Blender's collapse adds
# length * (2 - w1 - w2) * factor to an edge's cost (a weight of 0 all but freezes it), so the group's weight is
# 1 - 0.9 * keep and the factor is searched: the first of KEEP_FACTORS whose result holds KEEP_GAIN times the plain
# decimation's share of vertices in the keep region (the triangle budget stays the same).
KEEP_FACTORS = (1e-4, 3e-4, 1e-3, 3e-3, 1e-2)
KEEP_GAIN = 2.4
KEEP_MAX_ADD = 0.15  # at most this much more of the vertices in the keep region (the rest of the head keeps its share)
RIM_W = 0.018
RELAX = (0.6, 5)  # the local relax of the dense original's jagged creases (lip edges, lid on eyeball): factor, iterations  # the lid-rim shell's half width in metres (the chameleon's eye radius is 3 times the axolotl's)
CAGE, RAY = 0.008, 0.03  # static_v2: the bakes' cage and ray (#288: 0.015/0.05, 0.012/0.04 reached across the lip slit)
ROUGH = {"skin": 0.42, "lips": 0.28, "eyes": 0.04, "gills": 0.5}


def log(msg):
    print(f"STATIC {msg}", flush=True)


def import_all(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    new = [o for o in bpy.data.objects if o not in before]
    meshes = []
    for o in new:
        if o.type == "MESH":
            mw = o.matrix_world.copy()
            o.parent = None
            o.data.transform(mw)
            o.matrix_world = Matrix.Identity(4)
            meshes.append(o)
    for o in new:
        if o.type != "MESH":
            bpy.data.objects.remove(o)
    return meshes


def hsv(a):
    """sRGB rows (N, 3) to hue (degrees), saturation, value."""
    mx, mn = a.max(1), a.min(1)
    d = mx - mn + 1e-6
    r, g, b = a[:, 0], a[:, 1], a[:, 2]
    h = np.where(mx == r, (g - b) / d % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60.0
    return h, np.where(mx > 0, (mx - mn) / (mx + 1e-6), 0), mx


def stats(a):
    """Median sRGB of the teal (saturated) and the light (pale) pixels of rows a."""
    h, s, v = hsv(a)
    teal = a[(s > 0.3) & (h > 140) & (h < 215) & (v > 0.25)]
    light = a[(s < 0.3) & (v > 0.7)]
    out = {}
    for name, p in (("teal", teal), ("light", light)):
        if len(p):
            m = np.median(p, axis=0)
            hh, ss, vv = hsv(m[None])
            out[name] = {"srgb": [round(float(x), 3) for x in m], "sat": round(float(ss[0]), 3),
                         "val": round(float(vv[0]), 3), "share": round(len(p) / len(a), 3)}
    return out


def fg_pixels(path):
    v = H.load_rgb(path)
    a = v.reshape(-1, 4)
    if a[:, 3].min() < 0.5:
        return a[a[:, 3] > 0.5][:, :3]
    bg = v[0, 0, :3]
    return a[np.abs(a[:, :3] - bg).max(1) > 0.08][:, :3]


def new_image(name, res, data=False, float_buffer=False):
    img = bpy.data.images.new(name, res, res, alpha=False, float_buffer=float_buffer)
    if data:
        img.colorspace_settings.name = "Non-Color"
    return img


def bake_to(low, img, kind, sources=(), **kw):
    mat = low.data.materials[0]
    node = mat.node_tree.nodes.get("bake_target") or mat.node_tree.nodes.new("ShaderNodeTexImage")
    node.name = "bake_target"
    node.image = img
    mat.node_tree.nodes.active = node
    H.select_only([*sources, low], active=low)
    common = dict(margin=16)
    if sources:
        common.update(use_selected_to_active=True, cage_extrusion=kw.pop("cage", 0.015),
                      max_ray_distance=kw.pop("ray", 0.05))
    bpy.ops.object.bake(type=kind, **common, **kw)


def save(img_or_arr, path, data=False):
    """Saves an (h, w, 3|4) float array (rows bottom-up, Blender's order) or an image as a PNG (RGBA for 4 channels)."""
    if isinstance(img_or_arr, np.ndarray):
        h, w, ch = img_or_arr.shape
        rgba = np.ones((h, w, 4), np.float32)
        rgba[..., :ch] = img_or_arr[..., :4]
        img = bpy.data.images.new(path.stem, w, h, alpha=ch == 4)
        if data:
            img.colorspace_settings.name = "Non-Color"
        img.pixels.foreach_set(np.clip(rgba, 0, 1).ravel())
    else:
        img = img_or_arr
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()
    return img


def blur(a, k=2):
    """Box blur of an (h, w) array over (2k+1)^2 texels."""
    p = np.pad(a, k, mode="edge")
    c = np.cumsum(np.cumsum(p, 0), 1)
    c = np.pad(c, ((1, 0), (1, 0)))
    n = 2 * k + 1
    return (c[n:, n:] - c[:-n, n:] - c[n:, :-n] + c[:-n, :-n]) / (n * n)


def to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def eye_dist(pos, ec, r):
    """The distance to the nearer fitted eye sphere's centre, in eye radii."""
    return np.min([np.linalg.norm(pos - np.array([ec[0] * sd, ec[1], ec[2]]), axis=-1) for sd in (1, -1)], 0) / r


def keep_weights(co, ec, r, mouth, half_w, rims=True):
    """static_v2: where the decimation keeps more of the dense original: the lips (an ellipsoid around the lip line)
    and the lid rims (a shell around each fitted eye sphere). co: (n, 3) Blender coordinates."""
    lips = ellipsoid_w(co, mouth, (half_w * 1.25, 0.09, 0.09), 0.5)
    if not rims:
        return lips
    rim = np.exp(-((eye_dist(co, ec, r) - 1.1) * r / RIM_W) ** 2)
    return np.clip(np.maximum(lips, rim), 0, 1)


def decimated(base, target, factor):
    """A symmetric collapse decimation of a copy of base to target triangles; factor > 0 uses its "keep" group."""
    o = base.copy()
    o.data = base.data.copy()
    bpy.context.scene.collection.objects.link(o)
    dec = o.modifiers.new("dec", "DECIMATE")
    dec.ratio = target / H.tris(o)
    dec.use_collapse_triangulate = True
    dec.use_symmetry = True
    dec.symmetry_axis = "X"
    if factor > 0:
        dec.vertex_group = "keep"
        dec.vertex_group_factor = factor
    H.apply_modifiers(o)
    bm = bmesh.new()  # zero-area triangles left by the collapse have no tangent (glTF-Validator: non-unit TANGENT)
    bm.from_mesh(o.data)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-6, edges=bm.edges[:])
    bm.to_mesh(o.data)
    bm.free()
    return o


def keep_share(o, kw_of):
    co = np.empty(len(o.data.vertices) * 3, np.float32)
    o.data.vertices.foreach_get("co", co)
    return float((kw_of(co.reshape(-1, 3)) > 0.5).mean())


def bake_ao(low, dense, res, inside, distance):
    """The dense original's own ambient occlusion (only_local: the low mesh does not occlude it) baked onto the low
    mesh's UVs; inside: the rays go into the mesh, so 1 - it is the thinness."""
    mat = bpy.data.materials.get("ao_bake") or bpy.data.materials.new("ao_bake")
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
    ao.inside, ao.only_local, ao.samples = inside, True, 16
    ao.inputs["Distance"].default_value = distance
    emit = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(ao.outputs["AO"], emit.inputs["Color"])
    nt.links.new(emit.outputs["Emission"], nt.nodes["Material Output"].inputs["Surface"])
    dense.data.materials.clear()
    dense.data.materials.append(mat)
    img = new_image(f"ao_{int(inside)}", res, data=True, float_buffer=True)
    bake_to(low, img, "EMIT", [dense], cage=CAGE, ray=RAY)
    return H.image_array(img)[..., 0]


def ellipsoid_w(pos, centre, radii, lo=0.6):
    d = (pos - np.asarray(centre)) / np.asarray(radii)
    e = np.sqrt((d ** 2).sum(-1))
    return 1.0 - np.clip((e - lo) / (1.0 - lo), 0, 1)


def square(path, n):
    """An image as an (n, n, 3) array, rows top-down: its centre square, nearest-sampled."""
    a = np.flipud(H.load_rgb(path))[..., :3]
    h, w = a.shape[:2]
    k = min(h, w)
    a = a[(h - k) // 2:(h - k) // 2 + k, (w - k) // 2:(w - k) // 2 + k]
    idx = (np.arange(n) * k / n).astype(int)
    return a[idx][:, idx]


def base_sheet(rows, path, n=320):
    """Rows of image paths (top first) as one sheet, n px cells, 4 px gaps."""
    cols = max(len(r) for r in rows)
    sheet = np.full((len(rows) * (n + 4), cols * (n + 4), 3), 0.2, np.float32)
    for i, row in enumerate(rows):
        for j, p in enumerate(row):
            if p and Path(p).exists():
                sheet[i * (n + 4):i * (n + 4) + n, j * (n + 4):j * (n + 4) + n] = square(p, n)
    save(np.flipud(sheet), path)


def main():
    ap = argparse.ArgumentParser()
    for a in ("--head", "--src", "--dense", "--ref", "--v2", "--view2d", "--roster", "--out"):
        ap.add_argument(a, required=True)
    ap.add_argument("--res", type=int, default=4096, help="the colour bake's size (the normal, mask: half)")
    ap.add_argument("--albedo-res", type=int, default=2048, help="the saved albedo's size (contract: 2048)")
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    if args.albedo_res > args.res or args.res % args.albedo_res or args.res % 2:
        ap.error(f"--albedo-res {args.albedo_res} must divide --res {args.res} (an even size)")
    head, out = args.head, Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "base_choice").mkdir(exist_ok=True)
    ref = json.loads(Path(args.ref).read_text(encoding="utf-8"))
    eye = ref["eye_fit"]
    ec, r = np.array([abs(eye["x"]), eye["y"], eye["z"]]), eye["r"]
    report = {"head": head, "eye_fit": {k: eye[k] for k in ("x", "y", "z", "r")}}
    bpy.ops.wm.read_factory_settings(use_empty=True)

    src = H.import_glb(Path(args.src))
    src.name = f"{head}_src"
    dense = H.import_glb(Path(args.dense))
    dense.name = f"{head}_dense"
    lo_s, hi_s = H.bounds([src])
    lo_d, hi_d = H.bounds([dense])
    off = max((lo_s - lo_d).length, (hi_s - hi_d).length)
    report["src_vs_dense_bounds"] = round(off, 5)
    geo = dense if off < 0.02 else src
    log(f"bounds offset src/dense {off:.4f}; geometry from {geo.name}")
    height = hi_s.z - lo_s.z

    # ---- the low mesh: Meshy's sculpt decimated, nothing cut
    low = geo.copy()
    low.data = geo.data.copy()
    bpy.context.scene.collection.objects.link(low)
    low.name = f"{head}_static"
    low.data.name = f"{head}_static"
    for m in list(low.modifiers):
        low.modifiers.remove(m)
    low.data.materials.clear()
    H.weld(low)
    # static_v2: more of the budget on the lips and lid rims (#288's long sliver triangles there streaked the shading
    # and stepped the lid rims)
    fp = ref["lip_line"]["front_point"]
    kw_of = lambda c, rims=True: keep_weights(c, ec, r, (0.0, fp[1] + 0.25 * r, fp[2]), ref["lip_line"]["half_width"], rims)  # noqa: E731
    co = np.empty(len(low.data.vertices) * 3, np.float32)
    low.data.vertices.foreach_get("co", co)
    kw = kw_of(co.reshape(-1, 3))
    vg = low.vertex_groups.new(name="keep")
    vg.add(list(range(len(kw))), 1.0, "REPLACE")
    for i in np.nonzero(kw > 0.02)[0]:
        vg.add([int(i)], float(1.0 - 0.9 * kw[i]), "REPLACE")
    plain = decimated(low, TRIS[head], 0)
    s0 = keep_share(plain, kw_of)
    tries = {"plain": round(s0, 4)}
    chosen = plain
    for factor in KEEP_FACTORS:
        o = decimated(low, TRIS[head], factor)
        sh = keep_share(o, kw_of)
        tries[str(factor)] = [round(sh, 4), H.tris(o)]
        log(f"keep factor {factor}: share {sh:.4f} (plain {s0:.4f}) tris {H.tris(o)}")
        if abs(H.tris(o) - TRIS[head]) > 0.03 * TRIS[head]:
            bpy.data.objects.remove(o)
            break
        if chosen is not plain:
            bpy.data.objects.remove(chosen)
        chosen = o
        if sh >= min(KEEP_GAIN * s0, s0 + KEEP_MAX_ADD):
            break
    if chosen is not plain:
        bpy.data.objects.remove(plain)
    report["keep_search"] = tries
    bpy.data.objects.remove(low)
    low = chosen
    low.name = f"{head}_static"
    low.data.name = f"{head}_static"
    cfg = H.HEADS[head]
    ledge = cfg["smooth_region"] if cfg.get("smooth_region", {}).get("kind") == "ledge" else None
    # the dense original's own crease is jagged where the lips meet the skin (kept denser, it showed more): a local
    # relax of the lips, their normal-map detail flattened below. Not on the lid rims: relaxed, the chameleon's lids
    # read heavier and lower than #288's in the whole-head gate (the rims keep the denser decimation and rougher mask)
    co = np.empty(len(low.data.vertices) * 3, np.float32)
    low.data.vertices.foreach_get("co", co)
    sw = kw_of(co.reshape(-1, 3), False)
    rg = low.vertex_groups.new(name="relax")
    for i in np.nonzero(sw > 0.02)[0]:
        rg.add([int(i)], float(sw[i]), "REPLACE")
    sm = low.modifiers.new("relax", "SMOOTH")
    sm.vertex_group = "relax"
    sm.factor, sm.iterations = RELAX
    H.apply_modifiers(low)
    for p in low.data.polygons:
        p.use_smooth = True
    report["tris"] = H.tris(low)
    log(f"low {report['tris']} tris")
    H.smart_uv(low)
    bake_mat = bpy.data.materials.new(f"{head}_bakemat")
    bake_mat.use_nodes = True
    low.data.materials.append(bake_mat)

    # ---- bakes: Meshy's colour as is, the graded colour, the normal, the position
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 1
    smat = src.data.materials[0]
    tex_img = H.base_image(smat)
    tex = H.image_array(tex_img)[..., :3].reshape(-1, 3)
    fg = fg_pixels(Path(args.view2d) / "front.png")
    res = args.res
    raw_img = new_image(f"{head}_raw", res)
    bake_to(low, raw_img, "DIFFUSE", [src], pass_filter={"COLOR"}, cage=CAGE, ray=RAY)
    stops = H.palette_stops(fg, tex)
    H.grade_source(smat, stops, ref.get("stripes") if cfg.get("stripes") else None)
    grade_img = new_image(f"{head}_graded", res)
    bake_to(low, grade_img, "DIFFUSE", [src], pass_filter={"COLOR"}, cage=CAGE, ray=RAY)
    nres = res // 2
    nrm_img = new_image(f"{head}_normal_raw", nres, data=True)
    bake_to(low, nrm_img, "NORMAL", [dense], normal_space="TANGENT", cage=CAGE, ray=RAY)
    pos_img = new_image(f"{head}_pos", nres, data=True, float_buffer=True)
    nt = bake_mat.node_tree
    geo_node = nt.nodes.new("ShaderNodeNewGeometry")
    emit = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(geo_node.outputs["Position"], emit.inputs["Color"])
    nt.links.new(emit.outputs["Emission"], nt.nodes["Material Output"].inputs["Surface"])
    bake_to(low, pos_img, "EMIT")
    scene.cycles.samples = 4
    cav = blur(bake_ao(low, dense, nres, False, 0.05), 1)
    thick = blur(bake_ao(low, dense, nres, True, 0.06), 2)
    scene.cycles.samples = 1
    log("bakes done")

    # ---- compose: grade the skin, keep the painted eyes, the mask
    raw = H.image_array(raw_img)[..., :3]
    graded = H.image_array(grade_img)[..., :3]
    nrm = H.image_array(nrm_img)[..., :3]
    pos_n = H.image_array(pos_img)[..., :3]
    pos = np.repeat(np.repeat(pos_n, 2, 0), 2, 1)
    side = np.where(pos[..., :1] >= 0, 1.0, -1.0)
    eye_c = np.concatenate([ec[0] * side, np.full_like(side, ec[1]), np.full_like(side, ec[2])], -1)
    in_eye = np.linalg.norm(pos - eye_c, axis=-1) < 1.08 * r
    h, s, v = (x.reshape(raw.shape[:2]) for x in hsv(raw.reshape(-1, 3)))
    skin_like = (h > 140) & (h < 215) & (s > 0.2) & (v > 0.18)
    fixed = in_eye & ~skin_like
    mask = 1.0 - blur(fixed.astype(np.float32), 2)
    eye_px = raw.copy()
    sclera = fixed & (s < 0.25) & (v > 0.5)
    eye_px[sclera] = eye_px[sclera] * 0.15 + np.array([0.96, 0.96, 0.94]) * 0.85  # v2: less of Meshy's grey top
    iris = fixed & (s >= 0.25)
    g = eye_px[iris].mean(1, keepdims=True)
    eye_px[iris] = np.clip(g + (eye_px[iris] - g) * 1.15, 0, 1)
    albedo = graded * mask[..., None] + eye_px * (1 - mask[..., None])
    # saturation matched to the 2D: the palette ramp's stops come from the 2D's brighter pixels, which its shading
    # washes toward white, so the albedo's teal was less saturated than the 2D's own (the pale fault, part 1)
    ref2d, now = stats(fg), stats(albedo[mask > 0.95].reshape(-1, 3))
    at, al = now["teal"]["sat"], now["light"]["sat"]
    kt = float(np.clip(ref2d["teal"]["sat"] / at, 0.6, 1.5))
    kl = float(np.clip(ref2d["light"]["sat"] / al, 0.6, 1.5))
    mx = albedo.max(-1, keepdims=True)
    sa = (mx - albedo.min(-1, keepdims=True)) / (mx + 1e-6)
    k = kl + (kt - kl) * np.clip((sa - al) / max(at - al, 1e-3), 0, 1)
    k = 1 + (k - 1) * mask[..., None]
    albedo = np.clip(mx - (mx - albedo) * k, 0, 1)
    report["saturation_gain"] = {"teal": round(kt, 3), "light": round(kl, 3)}
    log(f"saturation gain teal {kt:.3f} light {kl:.3f}")
    base = np.median(albedo[(mask > 0.95) & skin_like & (s > 0.3)], axis=0)
    report["base_skin_srgb"] = [round(float(x), 4) for x in base]
    # roughness and the subsurface weight by region
    lips = ellipsoid_w(pos, (0.0, fp[1] + 0.25 * r, fp[2]), (ec[0] * 1.3, 0.55 * r, 0.6 * r))
    gills = np.zeros(mask.shape, np.float32)
    roots = (ref.get("pivots") or {}).get(f"{head}_gills") or {}
    if roots:
        rx = min(abs(p[0]) for p in roots.values())
        rz = min(p[2] for p in roots.values())
        gills = np.clip((np.abs(pos[..., 0]) - rx + 0.02) / 0.06, 0, 1) * np.clip((pos[..., 2] - rz + 0.1) / 0.1, 0, 1)
    rough = ROUGH["skin"] + (ROUGH["lips"] - ROUGH["skin"]) * lips
    rough = rough + (ROUGH["gills"] - rough) * gills
    # v2: the lid rims rougher (#288's sharp streaks along the rim)
    ed = eye_dist(pos, ec, r)
    rough = rough + (0.62 - rough) * 0.7 * np.exp(-((ed - 1.12) * r / (0.8 * RIM_W)) ** 2)
    rough = rough * mask + ROUGH["eyes"] * (1 - mask)
    sss = mask * (1 - 0.2 * lips)
    m_rgb = np.stack([mask, rough, sss], -1)
    # the detail map (static_v2): cavity, thinness, flush, limbal ring
    ring = blur(iris.astype(np.float32), 4)
    limbal = np.clip(4 * ring * (1 - ring), 0, 1) * (ring > 0.25) * (1 - mask)
    flushw = np.maximum(lips, 0.7 * np.clip((1.45 - ed) / 0.35, 0, 1)) * mask
    thin = np.clip((1 - thick - 0.15) / 0.6, 0, 1)
    half = lambda x: x.reshape(nres, 2, nres, 2).mean((1, 3))  # noqa: E731
    detail = np.stack([np.clip(cav, 0, 1), thin, half(flushw), half(limbal)], -1)
    # the normal: flat on the painted eyes (a wet, smooth ball) and in the crest-root ledge region
    flat = np.array([0.5, 0.5, 1.0])
    fw = (1 - mask) * 0.85
    if ledge:
        a, b, u = ledge["centre"]
        lw = np.zeros(mask.shape, np.float32)
        for sd in (1, -1):
            cc = (ec[0] * sd + sd * a * r, ec[1] + b * r, ec[2] + u * r)
            lw = np.maximum(lw, ellipsoid_w(pos, cc, [x * r for x in ledge["radii"]], 0.3))
        fw = np.maximum(fw, lw)
    fw_n = np.maximum(fw[::2, ::2], 0.8 * kw_of(pos_n.reshape(-1, 3), False).reshape(nres, nres))
    nrm = nrm * (1 - fw_n[..., None]) + flat * fw_n[..., None]
    f = res // args.albedo_res
    if f > 1:  # baked at --res, kept at the contract's 2048 (godot-check texture_size): a supersampled albedo,
        # averaged in linear light
        albedo = to_srgb(to_linear(albedo).reshape(args.albedo_res, f, args.albedo_res, f, 3).mean((1, 3)))
    alb_img = save(albedo, out / f"{head}_albedo.png")
    nrm_out = save(nrm, out / f"{head}_normal.png", data=True)
    m_half = m_rgb.reshape(nres, 2, nres, 2, 3).mean((1, 3))
    mask_img = save(m_half, out / f"{head}_mask.png", data=True)
    save(detail, out / f"{head}_detail.png", data=True)
    alb_img.colorspace_settings.name = "sRGB"
    nrm_out.colorspace_settings.name = "Non-Color"
    mask_img.colorspace_settings.name = "Non-Color"

    # ---- colour diagnosis: the 2D, Meshy's texture, step 2a's v2 bake, this albedo
    v2_png = Path(args.v2).with_name(f"{head}_colour.png")
    diag = {"2d_front": stats(fg), "meshy_texture": stats(tex), "this_albedo": stats(albedo[(m_half[..., 0] if f > 1 else mask) > 0.95].reshape(-1, 3))}
    if v2_png.exists():
        diag["v2_colour_png"] = stats(H.load_rgb(v2_png)[..., :3].reshape(-1, 3)[::7])
    report["colour_diag"] = diag
    log(f"colour {json.dumps(diag)}")

    # ---- the material
    for o in (src, dense):
        o.hide_render = True
    mat = bpy.data.materials.new(f"{head}_static_skin")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    t_alb = nt.nodes.new("ShaderNodeTexImage")
    t_alb.image = alb_img
    t_msk = nt.nodes.new("ShaderNodeTexImage")
    t_msk.image = mask_img
    t_nrm = nt.nodes.new("ShaderNodeTexImage")
    t_nrm.image = nrm_out
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nmap = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(t_alb.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(t_msk.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    nt.links.new(t_nrm.outputs["Color"], nmap.inputs["Color"])
    nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Subsurface Weight"].default_value = 0.12
    bsdf.inputs["Subsurface Scale"].default_value = 0.02
    bsdf.inputs["Sheen Weight"].default_value = 0.15
    nt.nodes.active = t_alb
    low.data.materials.clear()
    low.data.materials.append(mat)
    low["base_skin_srgb"] = report["base_skin_srgb"]
    low["tint_mask"] = f"{head}_mask.png"

    # the crest-root ledge smoothed after the bakes (the maps follow the UVs; a smooth before them left the colour
    # bake's rays short of the source there), its normal detail flattened above
    if ledge:
        H.smooth_weights(low, Vector(ec), r, ledge, (0.0, -1.0, 0.0), (1.0, 0.0, 0.0))
        H.add_smooth(low, *cfg["smooth"])
        H.apply_modifiers(low)

    # ---- LOD1 and export
    lod = low.copy()
    lod.data = low.data.copy()
    scene.collection.objects.link(lod)
    lod.name = f"{head}_static_lod1"
    d1 = lod.modifiers.new("dec", "DECIMATE")
    d1.ratio = 0.45
    d1.use_symmetry = True
    H.apply_modifiers(lod)
    report["tris_lod1"] = H.tris(lod)
    for o, name in ((low, f"{head}_static.glb"), (lod, f"{head}_static_lod1.glb")):
        H.select_only([o])
        bpy.ops.export_scene.gltf(filepath=str(out / name), export_format="GLB", use_selection=True,
                                  export_apply=True, export_yup=True, export_animations=False, export_extras=True,
                                  export_tangents=True)
    lod.hide_render = True

    # ---- review: the base-choice views (Workbench, texture colour) of this build and of v2
    cam = H.setup_render(640)
    lo, hi = H.bounds([low])
    centre = (lo + hi) / 2
    scale = (hi - lo).length * 0.62
    views = {"front": (0, -1, 0), "side": (1, 0, 0), "back": (0, 1, 0), "q34": (0.6, -0.8, 0)}
    for k, d in views.items():
        H.shoot(cam, centre, d, scale, out / "base_choice" / f"a_{k}.png")
    v2 = import_all(Path(args.v2))
    low.hide_render = True
    for k, d in views.items():
        H.shoot(cam, centre, d, scale, out / "base_choice" / f"b_{k}.png")
    for o in v2:
        o.hide_render = True
    bc = out / "base_choice"
    v2d = Path(args.view2d)
    base_sheet([[v2d / "front.png", v2d / "side.png", v2d / "back.png", Path(args.roster)],
                [bc / f"a_{k}.png" for k in views], [bc / f"b_{k}.png" for k in views]],
               out / f"{head}_base_choice.png")
    low.hide_render = False
    # Cycles front render of the final material, a plain grey studio
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 512, 640
    scene.view_settings.view_transform = "Standard"
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.45, 0.46, 0.48, 1)
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.9
    sun = bpy.data.objects.new("key", bpy.data.lights.new("key", "SUN"))
    sun.data.energy = 2.2
    sun.data.angle = math.radians(3)
    sun.rotation_euler = (math.radians(50), 0, math.radians(-35))
    scene.collection.objects.link(sun)
    cam.data.type = "PERSP"
    cam.data.lens = 85
    d = Vector((0, -1, 0.08)).normalized()
    cam.location = centre + d * height * 2.7
    cam.rotation_euler = (math.radians(90 - 4.6), 0, 0)
    scene.render.filepath = str(out / "blender_front.png")
    bpy.ops.render.render(write_still=True)
    bpy.context.preferences.filepaths.save_version = 0  # no .blend1 backups in the raw outputs
    bpy.ops.wm.save_as_mainfile(filepath=str(out / f"{head}_static.blend"), compress=True)
    (out / "build.json").write_text(json.dumps(report, indent=2), encoding="utf-8", newline="\n")
    log(f"done tris={report['tris']} lod1={report['tris_lod1']} base={report['base_skin_srgb']}")


if __name__ == "__main__":
    main()
