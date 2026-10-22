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
ROUGH = {"skin": 0.5, "lips": 0.3, "eyes": 0.04, "gills": 0.55}  # static_v3: the skin satin (0.42 read as vinyl)
# static_v3: the normal map and the cavity come from a smoothed copy of the dense original (a Laplacian relax,
# factor and iterations): its millimetre noise was the orange-peel grain over the whole head in static_v2
DENSE_SMOOTH = (0.5, 24)
# static_v3: a spike (the axolotl's upper-lip peak) is a convex vertex standing out of its neighbours' plane by more
# than DESPIKE[0] of its mean edge length and more than DESPIKE[1] times its neighbours' own median (a local outlier:
# a smoothly rounded lip, whose neighbours stand out alike, is never touched); it moves to its neighbours' mean, near
# the lips and lid rims only
DESPIKE = (0.08, 3.0)
# static_v3: per head, whether the decimation keeps more of the budget on the lid rims (the chameleon's default
# keeps #288's plain rims: the denser rims kept the dense original's heavier, lower lids; `--rims on` builds that
# alternative)
RIMS = {"chameleon": False, "axolotl": True}
SPEC_LEVEL = 0.3  # static_v3: Principled's Specular IOR Level (0.5 = glTF's default 0.04 reflectance)
# static_v3: weight, roughness, tint; the glTF exporter writes the tint alone as sheenColorFactor, so the weight is 1
# and the tint carries the strength
SHEEN = (1.0, 0.45, (0.25, 0.32, 0.31))
# static_v4: per head, the lid flush and the lid rims' rougher band (static_v3's chameleon read a dark ring round
# both eyes, bruises or bags, and heavier lids than #288's: both off there), and the eye zone (in eye radii, from
# full to none) the crease colour never reaches
LID_FLUSH = {"chameleon": 0.0, "axolotl": 0.7}
RIM_ROUGH = {"chameleon": 0.0, "axolotl": 0.7}
EYE_CLEAR = {"chameleon": (1.9, 2.4), "axolotl": None}
CREASE_K = 8  # static_v4: the crease's neighbourhood, a box of 2k+1 texels of the 2048 maps
# static_v4: the upper lip's border (the axolotl's bump at x = +-0.15 left by static_v3's despike): a low vertex
# there standing out of the smoothed dense original moves onto it (outward only: the lip border's concave crease
# keeps its depth), then onto the low mesh relaxed there; the slit and LIP_GAP metres above it are left alone
LIP_GAP = (0.006, 0.016)
LIP_RELAX = (0.5, 6)  # the band's own relax for the second snap: factor, iterations
# static_v4: the colour bakes' cage and ray per head (the normal, cavity and thinness bakes keep CAGE, RAY). The
# chameleon's iris sat higher on the eyeball with round 2's short ray than with #288's 0.015/0.05, so its upper lid
# cut the iris and read heavier and lower (the grey geometry was the same)
COLOUR_CAGE = {"chameleon": (0.015, 0.05), "axolotl": (CAGE, RAY)}


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def despike(o, region, thresh=DESPIKE, iters=8):
    """Moves each convex spike vertex in region (a per-vertex bool) to its neighbours' mean, up to iters passes.
    Returns the moved vertices' indices. Concave points (the lip slit) are never touched."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.verts.ensure_lookup_table()
    moved = set()
    idx = np.nonzero(region)[0]
    near = set(int(u.index) for i in idx for e in bm.verts[int(i)].link_edges for u in e.verts)

    def stand(v):
        nb = [e.other_vert(v) for e in v.link_edges]
        if v.is_boundary or len(nb) < 3:
            return 0.0, Vector()
        lap = sum((u.co for u in nb), Vector()) / len(nb) - v.co
        el = sum((u.co - v.co).length for u in nb) / len(nb)
        return -lap.dot(v.normal) / max(el, 1e-9), lap

    for _ in range(iters):
        bm.normal_update()
        out = {i: stand(bm.verts[i]) for i in near}
        hits = []
        for i in idx:
            v = bm.verts[int(i)]
            sv, lap = out[int(i)]
            nbo = [max(out[u.index][0], 0.0) for e in v.link_edges for u in e.verts if u is not v]
            if sv > thresh[0] and sv > thresh[1] * max(float(np.median(nbo)), 0.01):
                hits.append((v, lap))
        for v, lap in hits:
            v.co += lap
            moved.add(v.index)
        if not hits:
            break
    bm.to_mesh(o.data)
    bm.free()
    return sorted(moved)


def lip_snap(o, smooth, weight):
    """static_v4: moves each low vertex with weight > 0 that stands out of the smoothed dense original (smooth, the
    same space) inward along its normal by weight times its outward distance; a vertex inside it is never moved.
    Returns the count moved and the largest move in metres."""
    from mathutils.bvhtree import BVHTree
    bvh = BVHTree.FromObject(smooth, bpy.context.evaluated_depsgraph_get())
    moved, most = 0, 0.0
    for i in np.nonzero(weight > 0.02)[0]:
        v = o.data.vertices[int(i)]
        hit = bvh.find_nearest(v.co)
        if hit[0] is None:
            continue
        out = (v.co - hit[0]).dot(v.normal)
        if out <= 0:
            continue
        step = float(weight[i]) * out
        v.co = v.co - v.normal * step
        moved, most = moved + 1, max(most, step)
    o.data.update()
    return moved, most


def alive(albedo, skin, pos, cav, thin, lips, ed, gills, head, ec, r, mouth_z, teal, k=1.0):
    """static_v3: the "alive" read baked into the albedo (it shows in a browser's glTF viewer as well as in Godot).
    static_v4: no large-scale drift any more (it read as dirty greenish blotches on the axolotl's forehead and back),
    and every colour added is the skin's own teal, never a hue shift (a shifted or saturated pale skin read
    green-grey at the lip corner): the 2D's teal top of the axolotl's head (a smooth gradient), the narrow creases
    (nostrils, lip corners, gill roots: the cavity below its own neighbourhood, never a wide patch) a little toward a
    deeper teal, and a flush toward the teal on the lips, the nostrils, the thin parts' roots and (per head,
    LID_FLUSH) the lids. The chameleon's eyes and sockets get no crease colour (EYE_CLEAR). k scales every change
    (0 = the plain albedo). Returns the albedo and the layers' weights."""
    a = albedo.copy()
    x, z = np.abs(pos[..., 0]), pos[..., 2]
    span = ec[2] - mouth_z
    tl = np.clip(np.asarray(teal, np.float32), 0, 1)
    top = np.zeros(skin.shape, np.float32)
    if head == "axolotl":  # the 2D: teal forehead and crown down to the eyes, teal cheeks outside the eyes
        top = smoothstep(ec[2] - 0.33 * span, ec[2] + 0.55 * span, z)
        side = smoothstep(ec[0] + 0.3 * r, ec[0] + 1.8 * r, x) * smoothstep(mouth_z, mouth_z + 0.6 * span, z)
        top = np.maximum(top, 0.8 * side) * skin
        lum = a.mean(-1, keepdims=True) / max(float(np.mean(tl)), 1e-3)
        a = a + min(0.85 * k, 1.0) * top[..., None] * (np.clip(tl * (0.75 + 0.25 * lum), 0, 1) - a)
    # the crease: how far the cavity sits below its skin neighbourhood's mean (a normalised box blur, so the islands'
    # edges and the eyes never count), from its 90th to its 99.5th percentile on the skin
    sk = (skin > 0.9).astype(np.float32)
    hp = np.clip(blur(cav * sk, CREASE_K) / np.maximum(blur(sk, CREASE_K), 1e-3) - cav, 0, None) * sk
    q = hp[sk > 0]
    crease = smoothstep(float(np.percentile(q, 90)), float(np.percentile(q, 99.5)), hp)
    if EYE_CLEAR.get(head):
        crease = crease * smoothstep(*EYE_CLEAR[head], ed)
    lid = np.clip((1.55 - ed) / 0.45, 0, 1) * (ed > 0.98)
    nose = ellipsoid_w(np.stack([pos[..., 0], np.zeros_like(z), z], -1), (0.0, 0.0, (ec[2] + mouth_z) / 2),
                       (0.6 * ec[0], 1.0, 0.45 * span), 0.3) * (pos[..., 1] < ec[1])
    roots = np.clip(4 * thin * (1 - thin), 0, 1)
    flush = np.clip(np.maximum.reduce([lips, LID_FLUSH[head] * lid, 0.9 * nose * np.clip(2.5 * blur(crease, 6), 0, 1),
                                       0.7 * roots, 0.6 * gills * (1 - gills) * 4]), 0, 1) * skin
    crease = crease * skin
    deep = tl * 0.72  # the teal's own hue and saturation, darker
    a = a + (k * 0.22 * flush)[..., None] * (tl - a)
    a = a + (k * 0.3 * crease)[..., None] * (deep - a)
    return np.clip(a, 0, 1), {"top": top, "crease": crease, "flush": flush}


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
    ap.add_argument("--name", default="", help="the build's file and object name (default: the head)")
    ap.add_argument("--rims", choices=["auto", "on", "off"], default="auto",
                    help="keep more of the budget on the lid rims (auto: RIMS per head)")
    ap.add_argument("--alive", type=float, default=1.0, help="the baked alive layers' strength (0: off)")
    ap.add_argument("--colour-cage", default="", help="the colour bakes' cage,ray in metres (default: COLOUR_CAGE)")
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    if args.albedo_res > args.res or args.res % args.albedo_res or args.res % 2:
        ap.error(f"--albedo-res {args.albedo_res} must divide --res {args.res} (an even size)")
    head, out = args.head, Path(args.out)
    nm = args.name or head
    rims_on = RIMS[head] if args.rims == "auto" else args.rims == "on"
    cc = tuple(float(x) for x in args.colour_cage.split(",")) if args.colour_cage else COLOUR_CAGE[head]
    out.mkdir(parents=True, exist_ok=True)
    (out / "base_choice").mkdir(exist_ok=True)
    ref = json.loads(Path(args.ref).read_text(encoding="utf-8"))
    eye = ref["eye_fit"]
    ec, r = np.array([abs(eye["x"]), eye["y"], eye["z"]]), eye["r"]
    report = {"head": head, "name": nm, "rims": rims_on, "alive": args.alive, "colour_cage": list(cc),
              "eye_fit": {k: eye[k] for k in ("x", "y", "z", "r")}}
    bpy.ops.wm.read_factory_settings(use_empty=True)

    src = H.import_glb(Path(args.src))
    src.name = f"{head}_src"
    dense = H.import_glb(Path(args.dense))
    dense.name = f"{head}_dense"
    # static_v3: the bakes' smoothed source (the orange peel): the decimation still takes the dense original's shape
    dense_s = dense.copy()
    dense_s.data = dense.data.copy()
    bpy.context.scene.collection.objects.link(dense_s)
    dense_s.name = f"{head}_dense_smooth"
    H.weld(dense_s)
    sm_d = dense_s.modifiers.new("relax", "SMOOTH")
    sm_d.factor, sm_d.iterations = DENSE_SMOOTH
    H.apply_modifiers(dense_s)
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
    low.name = f"{nm}_static"
    low.data.name = f"{nm}_static"
    for m in list(low.modifiers):
        low.modifiers.remove(m)
    low.data.materials.clear()
    H.weld(low)
    # static_v2: more of the budget on the lips and lid rims (#288's long sliver triangles there streaked the shading
    # and stepped the lid rims)
    fp = ref["lip_line"]["front_point"]
    kw_of = lambda c, rims=rims_on: keep_weights(c, ec, r, (0.0, fp[1] + 0.25 * r, fp[2]), ref["lip_line"]["half_width"], rims)  # noqa: E731
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
    low.name = f"{nm}_static"
    low.data.name = f"{nm}_static"
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
    # static_v3: the spikes left near the lips and lid rims (the axolotl's upper-lip peak) moved into their
    # neighbours' plane
    low.data.vertices.foreach_get("co", co)
    spikes = despike(low, keep_weights(co.reshape(-1, 3), ec, r, (0.0, fp[1] + 0.25 * r, fp[2]),
                                       ref["lip_line"]["half_width"], True) > 0.05)
    report["despiked"] = {"count": len(spikes),
                          "where": [[round(float(c), 3) for c in low.data.vertices[i].co] for i in spikes[:40]]}
    log(f"despiked {len(spikes)} vertices")
    # static_v4: the upper lip's border onto the smoothed dense original (LIP_GAP above the slit, in the lips' region)
    low.data.vertices.foreach_get("co", co)
    c3 = co.reshape(-1, 3)
    line = np.asarray(ref["lip_line"]["line"], np.float64)  # (x, up, front)
    slit = np.interp(np.abs(c3[:, 0]), line[:, 0], line[:, 1])
    lw = kw_of(c3, False) * smoothstep(LIP_GAP[0], LIP_GAP[1], c3[:, 2] - slit)
    n_snap, d_snap = lip_snap(low, dense_s, lw)
    # the bump is in the smoothed original too (its first try moved 1.3 mm at most and left it): a second pass onto a
    # copy of the low mesh relaxed in the same band (LIP_RELAX, outward only again)
    band = low.copy()
    band.data = low.data.copy()
    bpy.context.scene.collection.objects.link(band)
    bg = band.vertex_groups.get("relax") or band.vertex_groups.new(name="relax")
    bg.remove(list(range(len(band.data.vertices))))
    for i in np.nonzero(lw > 0.02)[0]:
        bg.add([int(i)], float(lw[i]), "REPLACE")
    for m in list(band.modifiers):
        band.modifiers.remove(m)
    sm_b = band.modifiers.new("band", "SMOOTH")
    sm_b.vertex_group = "relax"
    sm_b.factor, sm_b.iterations = LIP_RELAX
    H.apply_modifiers(band)
    n2, d2 = lip_snap(low, band, lw)
    bpy.data.objects.remove(band)
    n_snap, d_snap = n_snap + n2, max(d_snap, d2)
    report["lip_snap"] = {"count": n_snap, "max_m": round(d_snap, 5)}
    log(f"lip border: {n_snap} vertices moved, at most {d_snap * 1000:.2f} mm")
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
    bake_to(low, raw_img, "DIFFUSE", [src], pass_filter={"COLOR"}, cage=cc[0], ray=cc[1])
    stops = H.palette_stops(fg, tex)
    H.grade_source(smat, stops, ref.get("stripes") if cfg.get("stripes") else None)
    grade_img = new_image(f"{head}_graded", res)
    bake_to(low, grade_img, "DIFFUSE", [src], pass_filter={"COLOR"}, cage=cc[0], ray=cc[1])
    nres = res // 2
    nrm_img = new_image(f"{head}_normal_raw", nres, data=True)
    bake_to(low, nrm_img, "NORMAL", [dense_s], normal_space="TANGENT", cage=CAGE, ray=RAY)
    pos_img = new_image(f"{head}_pos", nres, data=True, float_buffer=True)
    nt = bake_mat.node_tree
    geo_node = nt.nodes.new("ShaderNodeNewGeometry")
    emit = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(geo_node.outputs["Position"], emit.inputs["Color"])
    nt.links.new(emit.outputs["Emission"], nt.nodes["Material Output"].inputs["Surface"])
    bake_to(low, pos_img, "EMIT")
    scene.cycles.samples = 4
    cav = blur(bake_ao(low, dense_s, nres, False, 0.05), 1)
    thick = blur(bake_ao(low, dense_s, nres, True, 0.06), 2)
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
    # v2: the lid rims rougher (static_v4: per head, RIM_ROUGH) (#288's sharp streaks along the rim)
    ed = eye_dist(pos, ec, r)
    rough = rough + (0.62 - rough) * RIM_ROUGH[head] * np.exp(-((ed - 1.12) * r / (0.8 * RIM_W)) ** 2)
    rough = rough * mask + ROUGH["eyes"] * (1 - mask)
    sss = mask * (1 - 0.2 * lips)
    m_rgb = np.stack([mask, rough, sss], -1)
    # the detail map (static_v2): cavity, thinness, flush, limbal ring
    ring = blur(iris.astype(np.float32), 4)
    limbal = np.clip(4 * ring * (1 - ring), 0, 1) * (ring > 0.25) * (1 - mask)
    flushw = np.maximum(lips, LID_FLUSH[head] * np.clip((1.45 - ed) / 0.35, 0, 1)) * mask
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
    # static_v3: the lips' normal detail fully flat (0.8 in static_v2 left the upper lip's spike and light line)
    fw_n = np.maximum(fw[::2, ::2], 1.0 * kw_of(pos_n.reshape(-1, 3), False).reshape(nres, nres))
    nrm = nrm * (1 - fw_n[..., None]) + flat * fw_n[..., None]
    f = res // args.albedo_res
    if f > 1:  # baked at --res, kept at the contract's 2048 (godot-check texture_size): a supersampled albedo,
        # averaged in linear light
        albedo = to_srgb(to_linear(albedo).reshape(args.albedo_res, f, args.albedo_res, f, 3).mean((1, 3)))
    m_half = m_rgb.reshape(nres, 2, nres, 2, 3).mean((1, 3))
    # static_v3: the alive layers baked into the albedo and the roughness (at the maps' 2048, from the position bake)
    if albedo.shape[0] != nres:
        raise SystemExit(f"--albedo-res {args.albedo_res} must be half of --res {res} for the alive layers")
    skin2 = m_half[..., 0]
    teal = stats(albedo[skin2 > 0.95].reshape(-1, 3))["teal"]["srgb"]
    plain = albedo
    albedo, lay = alive(plain, skin2, pos_n, cav, thin, half(lips), eye_dist(pos_n, ec, r), half(gills), head, ec, r,
                        fp[2], teal, args.alive)
    m_half[..., 1] = np.clip(m_half[..., 1] + args.alive * 0.08 * lay["crease"] * skin2, 0.03, 1)
    report["alive_layers"] = {k: round(float(v.mean()), 4) for k, v in lay.items()}
    save(plain, out / f"{nm}_albedo_plain.png")  # Godot's grid only (alive_mix), not in the GLB
    alb_img = save(albedo, out / f"{nm}_albedo.png")
    nrm_out = save(nrm, out / f"{nm}_normal.png", data=True)
    # the eyes' clear coat (glTF KHR_materials_clearcoat reads R): 1 on the eyes
    coat_img = save(np.stack([1 - skin2, np.zeros_like(skin2), np.zeros_like(skin2)], -1), out / f"{nm}_coat.png",
                    data=True)
    coat_img.colorspace_settings.name = "Non-Color"
    mask_img = save(m_half, out / f"{nm}_mask.png", data=True)
    save(detail, out / f"{nm}_detail.png", data=True)
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
    for o in (src, dense, dense_s):
        o.hide_render = True
    mat = bpy.data.materials.new(f"{nm}_static_skin")
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
    # static_v3: glTF extensions a browser's viewer renders (three.js): the eyes' wet clear coat from the coat map
    # (KHR_materials_clearcoat), a soft sheen at grazing angles (KHR_materials_sheen) and a lower skin specular
    # (KHR_materials_specular) against the vinyl gloss
    t_coat = nt.nodes.new("ShaderNodeTexImage")
    t_coat.image = coat_img
    sep_c = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(t_coat.outputs["Color"], sep_c.inputs["Color"])
    nt.links.new(sep_c.outputs["Red"], bsdf.inputs["Coat Weight"])
    bsdf.inputs["Coat Roughness"].default_value = 0.03
    bsdf.inputs["Specular IOR Level"].default_value = SPEC_LEVEL
    bsdf.inputs["Sheen Weight"].default_value = SHEEN[0]
    bsdf.inputs["Sheen Roughness"].default_value = SHEEN[1]
    bsdf.inputs["Sheen Tint"].default_value = (*SHEEN[2], 1.0)
    nt.nodes.active = t_alb
    low.data.materials.clear()
    low.data.materials.append(mat)
    low["base_skin_srgb"] = report["base_skin_srgb"]
    low["tint_mask"] = f"{nm}_mask.png"

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
    lod.name = f"{nm}_static_lod1"
    d1 = lod.modifiers.new("dec", "DECIMATE")
    d1.ratio = 0.45
    d1.use_symmetry = True
    H.apply_modifiers(lod)
    report["tris_lod1"] = H.tris(lod)
    for o, name in ((low, f"{nm}_static.glb"), (lod, f"{nm}_static_lod1.glb")):
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
               out / f"{nm}_base_choice.png")
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
    bpy.ops.wm.save_as_mainfile(filepath=str(out / f"{nm}_static.blend"), compress=True)
    (out / "build.json").write_text(json.dumps(report, indent=2), encoding="utf-8", newline="\n")
    log(f"done tris={report['tris']} lod1={report['tris_lod1']} base={report['base_skin_srgb']}")


if __name__ == "__main__":
    main()
