"""The alien skin's authored 4K texture set (art #196, step M3a): albedo, packed ORM and a subsurface mask, made in
headless Blender from M2's bakes (normal, AO, curvature, thickness), the `masks` UV (light, accent) and fields of the
rest pose, onto Body's texture UV `UVMap` (glTF TEXCOORD_0); then the kit exported with the set on the skin.

Runs in background Blender through the runner, never by hand and never in a window:
tools/runner/blender.py's run_script("alien_texture.py", args) with args
  --stage cage|fields|compose|export --out <M3a> --m2 <M2> [--size 4096] [--set m3a|m3c] [--settings JSON] \
      [--variants FILE --vout DIR] [--kit <the kit's export folder: character.json, mouth atlases>] \
      [--bake <the bake folder, default <out>/bake>] [--force]
--set (required by compose and export) names the texture set: its settings (alien_texture_geom.SETS: m3a the shipped
M3A, m3c M3A with M3C's changes over it), character.json's note and the images' names. compose refuses an --out whose
textures/settings.json records other settings, and export one whose textures were composed with other settings than
the set's, unless --force. M3c (the set tuned toward rf2) runs the same stages with --out <M3c> --set m3c and --bake
<M3a/bake_cage_r2> (the capped cage's bake; fields and export).

Stages (each a separate run, so none blocks long; each reads the one before from --out):
- `cage` (reads M2/high/alien_high.blend): the explicit bake cage of PR #231's minor 6. Body's copy, each vertex moved
  out along its normal by alien_texture_geom.cage_offset(clearance): 40 % of the distance to the next surface of the
  low mesh along that normal, within 0.3..2 mm and at most half of it (M2: 2 mm everywhere, which started rays inside the next finger in the
  webs and across the nostril slits). Rebakes the normal map (4K) and AO (2K) from Body_high through it into
  M3a/bake/ (curvature and thickness are copied from M2/bake/), `cage_report.json` (the changed texels, the strongly
  tilted texels before and after) and `cage_compare.png` (M2 above, M3a below, the hand webs and the nostrils).
- `fields` (reads M2/export/alien_character.blend): per-vertex region attributes of the rest pose (T-zone, mouth rim,
  flush, warm thin parts, the S9 gradient's `deep` and face warmth), then Cycles emission bakes at --size of five RGB
  fields onto UVMap (masks and AO; curvature, thickness, deep; blotch, hue and face; T-zone, mouth, warm; fine noise,
  flush, and a coverage channel), plus the pore field from the normal map's divergence. Saved as float16 .npy in
  M3a/fields/ with `fields.json` (each field's stats).
- `compose`: the textures from the fields by alien_texture_geom (albedo, roughness, the subsurface mask) with the
  settings of --set (merged with --settings, a JSON object): M3a/textures/ `albedo.png` (sRGB), `orm.png` (R occlusion,
  G roughness, B metallic 0; glTF's packing), `sss.png` (grey, half --size), each with a 1k preview; the UV gaps are
  filled by push-pull, so mip levels never bleed black. --variants FILE (a JSON file: an object of name: settings,
  each merged over the settings) writes each variant at --size into --vout/<name>/ instead (the tuning grids).
- `export` (reads M2/export/alien_character.blend): the other meshes on alien_hue (the crest parts) move to an
  untextured copy, `alien_hue_part` (alien.gd swaps both for the shader); alien_hue takes albedo
  (baseColorTexture), orm (G roughness, B metallic through Separate Color, R through the glTF Material Output group's
  Occlusion: occlusionTexture) and the bake folder's normal.png (--bake; normalTexture), all on UVMap;
  <out>/export/alien_character.glb with its .blend, character.json (the set's note, alien_texture_geom.texture_note),
  the mouth atlases and sss.png beside it.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import struct
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_lips_geom as LP  # noqa: E402
import alien_texture_geom as T  # noqa: E402
import export_glb  # noqa: E402

UV_LAYER = "UVMap"
SHOWN = ()  # alien_detail.SHOWN: no part in the AO bake (M7: no mouth piece; M9: no eye either)
BAKE = {"normal_samples": 8, "ao_samples": 64, "ao_dist": 0.05, "margin": 16, "aux": 2048}  # alien_detail.BAKE's
NOISE = {"blotch": (9.0, 2.0), "hue": (3.5, 1.0), "fine": (350.0, 1.0)}  # (scale per m, detail): about 11 cm, 29 cm, 3 mm
FIELDS = ("a", "b", "c", "d", "e")
LIGHT_SMOOTH = 8  # smooth_light's passes
SOCKET_MM = 14.0  # the eye socket region's reach past the eye parts' box, full to half of it (M3c's contact AO)
MOUNT_OUT = 1.23  # M9: the eye mount's outer radius in ball radii (S9's lids reach 1.23 r): the socket field's
# box, so it is the same for every eye design on the mount (UPDATE 8: the skin never depends on a design)
PART_MATERIAL = "alien_hue_part"  # godot/alien/alien.gd HUE_MATERIALS
CROPS_1K = ((340, 60), (880, 30), (745, 525), (945, 800), (300, 745))  # M2's web artefacts and the nostrils (1k px)


def args():
    p = argparse.ArgumentParser()
    p.add_argument("--stage", required=True, choices=("cage", "fields", "compose", "export"))
    p.add_argument("--out", required=True)
    p.add_argument("--m2", required=True, help="M2's folder: high/, bake/, export/")
    p.add_argument("--size", type=int, default=4096)
    p.add_argument("--set", default="", choices=("", *T.SETS),
                   help="compose, export (required): the texture set, alien_texture_geom.SETS; also the note's and images' name")
    p.add_argument("--force", action="store_true",
                   help="compose, export: overwrite or export an --out whose textures/settings.json records other settings")
    p.add_argument("--settings", default="", help="compose: a JSON object merged into the set's settings")
    p.add_argument("--variants", default="", help="compose: a JSON file, an object {name: settings} -> --vout/<name>/ at --size")
    p.add_argument("--vout", default="")
    p.add_argument("--kit", default="", help="export: the folder of character.json and the mouth atlases")
    p.add_argument("--bake", default="", help="fields, export: the bake folder (default <out>/bake; M3c: M3a/bake_cage_r2)")
    a = p.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    if a.stage in ("compose", "export") and not a.set:
        p.error(f"--stage {a.stage} needs --set ({'|'.join(T.SETS)}): no texture set is assumed")
    return a


def log(*a):
    print("M3", *a, flush=True)


# ---------------------------------------------------------------- images
def img_array(img):
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    return px.reshape(h, w, 4)  # Blender rows: bottom first


def load_array(path):
    img = bpy.data.images.load(str(path))
    img.colorspace_settings.name = "Non-Color"
    a = img_array(img)
    bpy.data.images.remove(img)
    return a


def save_png(arr, path, srgb=False, preview=1024):
    """arr (h, w, 3 or 1) in 0..1, Blender row order; written as an 8-bit PNG (sRGB colour space when srgb: the values
    must be sRGB-encoded already) with a `_1k` preview."""
    h, w = arr.shape[:2]
    rgba = np.ones((h, w, 4), dtype=np.float32)
    if arr.shape[2] == 1:
        rgba[..., :3] = arr
    else:
        rgba[..., :3] = arr[..., :3]
    img = bpy.data.images.new(path.stem, w, h, alpha=False, float_buffer=False)
    img.colorspace_settings.name = "sRGB" if srgb else "Non-Color"
    img.pixels.foreach_set(np.clip(rgba, 0, 1).ravel())
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()
    if preview and w > preview:
        pv = img.copy()
        pv.scale(preview, preview)
        pv.filepath_raw = str(path.with_name(path.stem + "_1k.png"))
        pv.file_format = "PNG"
        pv.save()
        bpy.data.images.remove(pv)
    bpy.data.images.remove(img)


def bake_target(body, name, size, fill=None, float_buffer=False):
    img = bpy.data.images.new(name, size, size, alpha=True, float_buffer=float_buffer)
    img.colorspace_settings.name = "Non-Color"
    if fill is not None:
        img.pixels.foreach_set(np.full(size * size * 4, fill, dtype=np.float32))
    mt = body.data.materials[0]
    nt = mt.node_tree
    node = nt.nodes.get("bake_target") or nt.nodes.new("ShaderNodeTexImage")
    node.name = "bake_target"
    node.image = img
    uvn = nt.nodes.get("bake_uv") or nt.nodes.new("ShaderNodeUVMap")
    uvn.name = "bake_uv"
    uvn.uv_map = UV_LAYER
    if not node.inputs["Vector"].is_linked:
        nt.links.new(uvn.outputs["UV"], node.inputs["Vector"])
    nt.nodes.active = node
    return img


def select_only(objs, active):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active


def cycles(sc, samples):
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    if sc.world is None:
        sc.world = bpy.data.worlds.new("w")


def crop_sheet(rows, centres, size_px, crop, out_path):
    """rows: (h, w, 3) arrays (Blender row order) -> a sheet of crop x crop px around each centre (top-left 1k
    coordinates), scaled to 256 px tiles, one row per array."""
    tile = 256
    k = size_px / 1024.0
    tiles = []
    for a in rows:
        row = []
        for cx, cy in centres:
            x0 = int(cx * k - crop / 2)
            y0 = int(size_px - cy * k - crop / 2)  # top-left y -> Blender rows
            x0 = min(max(x0, 0), size_px - crop)
            y0 = min(max(y0, 0), size_px - crop)
            c = a[y0:y0 + crop, x0:x0 + crop, :3]
            idx = (np.arange(tile) * crop // tile)
            row.append(c[idx][:, idx])
        tiles.append(row)
    g = 4
    H = len(tiles) * tile + (len(tiles) - 1) * g
    W = len(centres) * tile + (len(centres) - 1) * g
    out = np.full((H, W, 3), 0.06, dtype=np.float32)
    for i, row in enumerate(tiles):
        y0 = H - (i + 1) * tile - i * g
        for j, t in enumerate(row):
            out[y0:y0 + tile, j * (tile + g):j * (tile + g) + tile] = t
    save_png(out, out_path, preview=0)


# ---------------------------------------------------------------- the cage
def vertex_arrays(me):
    n = len(me.vertices)
    co = np.empty(n * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    nr = np.empty(n * 3, dtype=np.float64)
    me.vertex_normals.foreach_get("vector", nr)
    return co.reshape(n, 3), nr.reshape(n, 3)


def clearances(me, co, nr):
    """Per vertex the distance (mm) along its normal to the low mesh's next surface (inf: none within probe_mm)."""
    bvh = BVHTree.FromPolygons([Vector(p) for p in co], [tuple(p.vertices) for p in me.polygons])
    probe = T.CAGE["probe_mm"] / 1000.0
    out = np.full(len(co), np.inf)
    for i in range(len(co)):
        n = Vector(nr[i])
        hit = bvh.ray_cast(Vector(co[i]) + n * 2e-5, n, probe)
        if hit[0] is not None:
            out[i] = hit[3] * 1000.0
    return out


def cage_offsets(me, clr, offset=T.cage_offset):
    """Per vertex the cage's offset (m) from its clearance (mm), then a min-biased smoothing over the edges: the offset
    never grows where the clearance is short."""
    off = np.array([offset(c) for c in clr]) / 1000.0
    e = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get("vertices", e)
    e = e.reshape(-1, 2)
    for _ in range(2):
        nb = off.copy()
        np.minimum.at(nb, e[:, 0], off[e[:, 1]])
        np.minimum.at(nb, e[:, 1], off[e[:, 0]])
        off = np.minimum(off, 0.5 * (off + nb))
    return off


def stage_cage(a, out):
    m2 = Path(a.m2)
    bpy.ops.wm.open_mainfile(filepath=str(m2 / "high" / "alien_high.blend"))
    sc = bpy.context.scene
    body, hi = bpy.data.objects["Body"], bpy.data.objects["Body_high"]
    body.find_armature().data.pose_position = "REST"
    bpy.context.view_layer.update()
    me = body.data
    co, nr = vertex_arrays(me)
    t = time.time()
    clr = clearances(me, co, nr)
    off = cage_offsets(me, clr)
    short = int((clr < T.CAGE["max_mm"] / T.CAGE["share"]).sum())
    log(f"cage clearance {time.time() - t:.0f}s; vertices with a short clearance {short}; offset mm min "
        f"{off.min() * 1000:.2f} mean {off.mean() * 1000:.2f}")
    cage = body.copy()
    cage.data = me.copy()
    cage.name = cage.data.name = "Body_cage"
    for m in list(cage.modifiers):
        cage.modifiers.remove(m)
    cage.parent = None
    cage.matrix_world = body.matrix_world.copy()
    sc.collection.objects.link(cage)
    cage.data.vertices.foreach_set("co", (co + nr * off[:, None]).astype(np.float32).ravel())
    for attr in ("visible_camera", "visible_diffuse", "visible_glossy", "visible_transmission",
                 "visible_volume_scatter", "visible_shadow"):
        setattr(cage, attr, False)
    bdir = out / "bake"
    bdir.mkdir(parents=True, exist_ok=True)
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    for o in meshes:
        o.hide_render = not (o is body or o is hi or o is cage or o.name.startswith(SHOWN))
    rep = {"cage": T.CAGE, "short_clearance_vertices": short,
           "offset_mm": {"min": round(float(off.min() * 1000), 3), "mean": round(float(off.mean() * 1000), 3)}}

    def bake(kind, name, size, samples, **kw):
        cycles(sc, samples)
        img = bake_target(body, name, size)
        select_only((hi, body), body)
        t0 = time.time()
        res = bpy.ops.object.bake(type=kind, use_selected_to_active=True, use_cage=True, cage_object=cage.name,
                                  max_ray_distance=T.CAGE["ray_mm"] / 1000.0, margin=BAKE["margin"],
                                  margin_type="EXTEND", use_clear=True, uv_layer=UV_LAYER, **kw)
        if res != {"FINISHED"}:
            raise SystemExit(f"bake {kind}: {res}")
        img.filepath_raw = str(bdir / f"{name}.png")
        img.file_format = "PNG"
        img.save()
        pv = img.copy()
        pv.scale(1024, 1024)
        pv.filepath_raw = str(bdir / f"{name}_1k.png")
        pv.save()
        arr = img_array(img)
        log(f"baked {name} {size}px {time.time() - t0:.0f}s")
        return arr

    new_n = bake("NORMAL", "normal", a.size, BAKE["normal_samples"], normal_space="TANGENT")
    sc.world.light_settings.distance = BAKE["ao_dist"]
    new_ao = bake("AO", "ao", BAKE["aux"], BAKE["ao_samples"])
    old_n = load_array(m2 / "bake" / "normal.png")
    old_ao = load_array(m2 / "bake" / "ao.png")
    for f in ("curvature", "thickness"):
        for suffix in (".png", "_1k.png"):
            shutil.copy2(m2 / "bake" / f"{f}{suffix}", bdir / f"{f}{suffix}")
    dn = np.abs(new_n[..., :3] - old_n[..., :3]).max(-1)
    tilt = lambda arr: int((arr[..., 2] < 0.75).sum())  # noqa: E731  (nz < 0.5: over 60 degrees)
    rep["normal"] = {"changed_texels_over_0.05": int((dn > 0.05).sum()), "changed_texels_over_0.2": int((dn > 0.2).sum()),
                     "tilted_over_60deg_m2": tilt(old_n), "tilted_over_60deg_m3a": tilt(new_n)}
    da = np.abs(new_ao[..., 0] - old_ao[..., 0])
    rep["ao"] = {"changed_texels_over_0.05": int((da > 0.05).sum()), "mean_m2": round(float(old_ao[..., 0].mean()), 4),
                 "mean_m3a": round(float(new_ao[..., 0].mean()), 4)}
    crop_sheet([old_n, new_n], CROPS_1K, a.size, 640, bdir / "cage_compare.png")
    (bdir / "cage_report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8", newline="\n")
    log("CAGE " + json.dumps(rep))


# ---------------------------------------------------------------- the fields
def ss(a, b, x):
    return T.smoothstep(a, b, x, np)


def group_weights(obj, prefixes):
    me = obj.data
    idx = {g.index: g.name for g in obj.vertex_groups}
    out = np.zeros(len(me.vertices))
    for v in me.vertices:
        for g in v.groups:
            name = idx[g.group]
            for p, k in prefixes.items():
                if p in name:
                    out[v.index] += g.weight * k
                    break
    return out


def bbox(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    lo = np.array([min(p[i] for p in pts) for i in range(3)])
    hi = np.array([max(p[i] for p in pts) for i in range(3)])
    return lo, hi


def put_attr(me, name, values):
    if name in me.attributes:
        me.attributes.remove(me.attributes[name])
    at = me.attributes.new(name, "FLOAT", "POINT")
    at.data.foreach_set("value", np.asarray(values, dtype=np.float32))


def smooth_light(body, w):
    """The light mask (`masks` u, per vertex) with LIGHT_SMOOTH neighbour-average passes, blended in by w (the head
    and neck weight): on the decimated head's irregular triangles the pale panel's edge behind the jaw broke into
    pale specks (a vertex in, its neighbours out); the cage body's even quads keep their designed edges."""
    me = body.data
    n = len(me.vertices)
    uv = np.empty(len(me.loops) * 2, dtype=np.float64)
    me.uv_layers["masks"].data.foreach_get("uv", uv)
    lv = np.empty(len(me.loops), dtype=np.int64)
    me.loops.foreach_get("vertex_index", lv)
    light = np.bincount(lv, uv[0::2], n) / np.maximum(np.bincount(lv, None, n), 1)
    e = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get("vertices", e)
    e = e.reshape(-1, 2)
    deg = np.bincount(e.ravel(), None, n)
    sm = light.copy()
    for _ in range(LIGHT_SMOOTH):
        acc = np.bincount(e[:, 0], sm[e[:, 1]], n) + np.bincount(e[:, 1], sm[e[:, 0]], n)
        sm = 0.5 * sm + 0.5 * acc / np.maximum(deg, 1)
    return light + (sm - light) * np.clip(w, 0, 1)


def region_attrs(body):
    """The per-vertex fields of the rest pose (Blender axes: z up, the character faces -y), in world space: the face
    parts' boxes (bbox) are world space, so Body's vertices and normals go through its matrix_world too (identity in
    M2's export .blend, measured on 2026-10-19; a moved Body would otherwise shift every region)."""
    me = body.data
    co, nr = vertex_arrays(me)
    mw = np.array(body.matrix_world, dtype=np.float64)
    co = co @ mw[:3, :3].T + mw[:3, 3]
    nr = nr @ np.linalg.inv(mw[:3, :3])  # the normals by the inverse transpose
    nr /= np.maximum(np.linalg.norm(nr, axis=1, keepdims=True), 1e-12)
    x, y, z = co.T
    front = ss(0.2, 0.7, -nr[:, 1])
    eyes = [bbox(bpy.data.objects[f"eye_bored_ball_{s}"]) for s in ("L", "R")]
    ez = float(np.mean([(lo[2] + hi[2]) / 2 for lo, hi in eyes]))
    # M9b: the mouth mount (alien_lips_geom.MOUTH_MOUNT on the Mouth node), never one mouth piece's box, so every
    # mouth design and width sits on the same rim, flush and cheeks
    node = np.array(bpy.data.objects["Mouth"].matrix_world.translation, dtype=np.float64)
    c, mw, mh, _front = LP.mouth_mount(tuple(node))
    mc = np.array(c)
    head_w = group_weights(body, {"Head": 1.0})
    top = float(z[head_w > 0.5].max())
    # the T-zone: a strip down the face's middle from the forehead to above the mouth, and a forehead patch
    strip = np.exp(-(x / 0.018) ** 2) * ss(mc[2] + 0.004, mc[2] + 0.03, z) * (1 - ss(ez + 0.05, ez + 0.10, z))
    patch = np.exp(-((x / 0.035) ** 2 + ((z - (ez + 0.045)) / 0.03) ** 2))
    tzone = front * np.maximum(strip, patch)
    # the mouth's rim: the skin within about 8 mm of the rest mouth's outline
    d = np.sqrt(((x - mc[0]) / (mw + 0.008)) ** 2 + ((z - mc[2]) / (mh + 0.008)) ** 2)
    mouth = front * (1 - ss(0.85, 1.35, d)) * (y < mc[1] + 0.03)
    # the flush: round the mouth, wider, and two soft cheek patches beside and above its corners
    dw = np.sqrt(((x - mc[0]) / (mw + 0.03)) ** 2 + ((z - mc[2]) / (mh + 0.025)) ** 2)
    cheeks = sum(np.exp(-(((x - s * (mw + 0.006)) / 0.022) ** 2 + ((z - (mc[2] + 0.022)) / 0.02) ** 2)) for s in (-1, 1))
    flush = front * np.clip(np.maximum(1 - ss(0.6, 1.3, dw), cheeks), 0, 1) * (y < mc[1] + 0.04)
    # the warm thin parts: the fingers, the crest blade, the neck
    fingers = group_weights(body, {"Distal": 1.0, "Intermediate": 1.0, "Proximal": 0.8, "Metacarpal": 0.4})
    crest = head_w * ss(top - 0.11, top - 0.05, z)
    neck = group_weights(body, {"Neck": 0.7})
    warm = np.clip(fingers + crest + neck, 0, 1)
    # the S9 gradient (alien_hue.gdshader, alien.gd SKIN deep_top 0.6, deep_back 1.0) and the face's warmth ramp
    deep = np.clip(0.6 * ss(1.50, 1.85, z) + 1.0 * ss(-0.3, 0.9, nr[:, 1]) * ss(1.0, 1.4, z), 0, 1)
    face = ss(1.38, 1.50, z)
    light = smooth_light(body, head_w + group_weights(body, {"Neck": 1.0}))
    # the eye sockets (M3c): the skin within SOCKET_MM of each eye mount's box (M9: the ball's x MOUNT_OUT), for the AO:
    # the distance to the box, full within half of SOCKET_MM, none past it (an ellipsoid round the box reached
    # less far at the box's corners, the outer lid corners)
    socket = np.zeros(len(co))
    for side in ("L", "R"):
        lo, hi = bbox(bpy.data.objects[f"eye_bored_ball_{side}"])  # M9: the mount's ball, never a design's lids
        c, half = (lo + hi) / 2, MOUNT_OUT * (hi - lo) / 2
        d = np.linalg.norm(np.maximum(np.abs(co - c) - half, 0.0), axis=1)
        socket = np.maximum(socket, 1 - ss(0.5 * SOCKET_MM, SOCKET_MM, d * 1000.0))
    vals = {"f_tzone": tzone, "f_mouth": mouth, "f_flush": flush, "f_warm": warm, "f_deep": deep, "f_face": face,
            "f_light": light, "f_socket": socket}
    for k, v in vals.items():
        put_attr(me, k, v)
    log("regions", json.dumps({k: [round(float(v.min()), 3), round(float(v.mean()), 4), round(float(v.max()), 3)]
                               for k, v in vals.items()}), f"eye z {ez:.3f} mouth {mc.round(3).tolist()} top {top:.3f}")


def field_material(body, a):
    """A bake material on Body: an emission whose colour is a Combine Color of three named sources (set per pass)."""
    mt = bpy.data.materials.new("m3a_fields")
    mt.use_nodes = True
    nt = mt.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    comb = nt.nodes.new("ShaderNodeCombineColor")
    comb.name = "comb"
    nt.links.new(comb.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], outn.inputs["Surface"])
    src = {}
    uvm = nt.nodes.new("ShaderNodeUVMap")
    uvm.uv_map = "masks"
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(uvm.outputs["UV"], sep.inputs["Vector"])
    src["accent"] = sep.outputs["Y"]  # v accent (Blender's v, unflipped); the light mask: f_light (smoothed u)
    uv0 = nt.nodes.new("ShaderNodeUVMap")
    uv0.uv_map = UV_LAYER
    for k, f in (("ao", "ao"), ("curv", "curvature"), ("thick", "thickness")):
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(str(bake_dir(a) / f"{f}.png"))
        tex.image.colorspace_settings.name = "Non-Color"
        tex.interpolation = "Cubic"
        tex.extension = "EXTEND"
        nt.links.new(uv0.outputs["UV"], tex.inputs["Vector"])
        src[k] = tex.outputs["Color"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    for k, (scale, detail) in NOISE.items():
        nz = nt.nodes.new("ShaderNodeTexNoise")
        nz.noise_dimensions = "3D"
        nz.inputs["Scale"].default_value = scale
        nz.inputs["Detail"].default_value = detail
        nz.inputs["Roughness"].default_value = 0.5
        nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
        src[k] = nz.outputs["Fac"]
    for k in ("tzone", "mouth", "flush", "warm", "deep", "face", "light", "socket"):
        at = nt.nodes.new("ShaderNodeAttribute")
        at.attribute_type = "GEOMETRY"
        at.attribute_name = f"f_{k}"
        src[k] = at.outputs["Fac"]
    body.data.materials[0] = mt
    return mt, comb, src


def out_dir(a):
    return Path(a.out)


def bake_dir(a):
    """The bake the fields and the export read: --bake, or <out>/bake (M3a's own)."""
    return Path(a.bake) if a.bake else out_dir(a) / "bake"


PASSES = {"a": ("light", "accent", "ao"), "b": ("curv", "thick", "deep"), "c": ("blotch", "hue", "face"),
          "d": ("tzone", "mouth", "warm"), "e": ("fine", "flush", "socket")}  # M3a's fields had "one" for "socket"


def stage_fields(a, out):
    m2 = Path(a.m2)
    bpy.ops.wm.open_mainfile(filepath=str(m2 / "export" / "alien_character.blend"))
    sc = bpy.context.scene
    body = bpy.data.objects["Body"]
    arm = body.find_armature()
    arm.data.pose_position = "REST"
    bpy.context.view_layer.update()
    region_attrs(body)
    mt, comb, src = field_material(body, a)
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = o is not body
    cycles(sc, 1)
    fdir = out / "fields"
    fdir.mkdir(parents=True, exist_ok=True)
    stats = {}
    for key, names in PASSES.items():
        for i, n in enumerate(names):
            s = src[n]
            if s.type == "RGBA":  # an image: its first channel
                sp = mt.node_tree.nodes.new("ShaderNodeSeparateColor")
                mt.node_tree.links.new(s, sp.inputs["Color"])
                s = sp.outputs[0]
            mt.node_tree.links.new(s, comb.inputs[i])
        img = bake_target(body, f"field_{key}", a.size, fill=-1.0, float_buffer=True)
        select_only((body,), body)
        t0 = time.time()
        res = bpy.ops.object.bake(type="EMIT", margin=BAKE["margin"], margin_type="EXTEND", use_clear=False,
                                  uv_layer=UV_LAYER)
        if res != {"FINISHED"}:
            raise SystemExit(f"bake field {key}: {res}")
        arr = img_array(img)[..., :3]
        cov = arr[..., 0] > -0.5
        if key == "a":
            np.save(fdir / "coverage.npy", cov)
        for i, n in enumerate(names):
            v = arr[..., i][cov]
            stats[n] = {"min": round(float(v.min()), 4), "p1": round(float(np.percentile(v, 1)), 4),
                        "p50": round(float(np.percentile(v, 50)), 4), "p99": round(float(np.percentile(v, 99)), 4),
                        "max": round(float(v.max()), 4)}
        np.save(fdir / f"field_{key}.npy", arr.astype(np.float16))
        bpy.data.images.remove(img)
        log(f"field {key} {names} {time.time() - t0:.0f}s coverage {cov.mean():.3f}")
    # the pores: the normal map's divergence (OpenGL +Y; Blender rows go up in v)
    nm = load_array(bake_dir(a) / "normal.png")
    if nm.shape[0] != a.size:
        raise SystemExit("the normal map's size differs from --size")
    nx, ny = nm[..., 0] * 2 - 1, nm[..., 1] * 2 - 1
    div = np.zeros_like(nx)
    div[:, 1:-1] += (nx[:, 2:] - nx[:, :-2]) / 2
    div[1:-1, :] += (ny[2:, :] - ny[:-2, :]) / 2
    cov = np.load(fdir / "coverage.npy")
    neg = -div[cov]
    gain = 1.0 / max(float(np.percentile(neg, 99.0)), 1e-4)
    pore = T.micro_pore(div, gain, np)
    np.save(fdir / "pore.npy", pore.astype(np.float16))
    stats["pore"] = {"gain": round(gain, 2), "mean": round(float(pore[cov].mean()), 4)}
    (fdir / "fields.json").write_text(json.dumps({"passes": PASSES, "noise": NOISE, "stats": stats}, indent=1),
                                      encoding="utf-8", newline="\n")
    log("FIELDS " + json.dumps(stats))


# ---------------------------------------------------------------- compose
def push_pull(arr, mask):
    """Fills arr's texels outside mask (h, w) with the average of the nearest covered texels, coarse to fine."""
    levels = []
    a, m = arr * mask[..., None], mask.astype(np.float32)
    while a.shape[0] > 4:
        levels.append((a, m))
        h, w = a.shape[0] // 2, a.shape[1] // 2
        a = a[:h * 2, :w * 2].reshape(h, 2, w, 2, -1).sum((1, 3))
        m = m[:h * 2, :w * 2].reshape(h, 2, w, 2).sum((1, 3))
    filled = a / np.maximum(m, 1e-6)[..., None]
    for a, m in reversed(levels):
        up = np.repeat(np.repeat(filled, 2, 0), 2, 1)[:a.shape[0], :a.shape[1]]
        own = a / np.maximum(m, 1e-6)[..., None]
        filled = np.where((m > 0)[..., None], own, up)
    return filled


def down(arr, k):
    if k == 1:
        return arr.astype(np.float32)
    h, w = arr.shape[0] // k, arr.shape[1] // k
    sh = (h, k, w, k) + arr.shape[2:]
    return arr.astype(np.float32).reshape(sh).mean((1, 3))


def load_fields(out, size):
    fdir = out / "fields"
    f = {}
    first = np.load(fdir / "field_a.npy", mmap_mode="r")
    k = first.shape[0] // size
    for key, names in PASSES.items():
        arr = np.load(fdir / f"field_{key}.npy")
        for i, n in enumerate(names):
            f[n] = down(arr[..., i], k)
        del arr
    f["pore"] = down(np.load(fdir / "pore.npy"), k)
    if "socket" not in json.loads((fdir / "fields.json").read_text(encoding="utf-8"))["passes"]["e"]:
        f["socket"] = np.zeros_like(f["pore"])  # M3a's fields: a constant 1 in the socket's channel, not a socket
    cov = down(np.load(fdir / "coverage.npy").astype(np.float32), k) > 0.5
    # the noises (0..1 around 0.5) as -1..1 by their own spread
    for n in ("blotch", "hue", "fine"):
        v = f[n][cov]
        med, spread = float(np.median(v)), float(np.percentile(v, 97) - np.percentile(v, 3))
        f[n] = np.clip((f[n] - med) / max(spread / 2, 1e-4), -1, 1)
    return f, cov


def compose(f, cov, s, tdir, size):
    tdir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    if s["accent_blur"]:
        f = dict(f, accent=T.blur(f["accent"], cov, max(int(round(s["accent_blur"] * size / 4096)), 1), np))
    r, g, b = T.albedo(f, s, np)
    alb = np.stack([r, g, b], -1)
    alb = push_pull(alb, cov)
    # the numpy twin of alien_texture_geom.linear_to_srgb (save_png clips to 0..1)
    enc = np.where(alb <= 0.0031308, alb * 12.92, 1.055 * np.power(np.clip(alb, 0, 1), 1 / 2.4) - 0.055)
    save_png(enc, tdir / "albedo.png", srgb=True)
    rough = T.roughness(f, s, np)
    # glTF's packing: R occlusion, G roughness, B metallic 0
    ao = T.contact_ao(f["ao"], f.get("socket", 0.0), s, np)  # the albedo's AO before its strength
    orm = push_pull(np.stack([ao, rough, np.zeros_like(rough)], -1), cov)
    save_png(orm, tdir / "orm.png")
    sss = push_pull(T.sss_mask(f, s, np)[..., None], cov)
    save_png(down(sss, 2), tdir / "sss.png")
    st = {"albedo_srgb_mean": enc[cov].mean(0).round(3).tolist(),
          "roughness": [round(float(np.percentile(rough[cov], p)), 3) for p in (1, 50, 99)],
          "sss_mean": round(float(sss[..., 0][cov].mean()), 3)}
    (tdir / "settings.json").write_text(json.dumps({"size": size, "settings": s, "stats": st}, indent=1),
                                        encoding="utf-8", newline="\n")
    log(f"composed {tdir.name} {size}px {time.time() - t0:.0f}s {json.dumps(st)}")


def check_settings(a, tdir, s, what):
    """Fails unless --force when tdir's settings.json records settings other than s (a missing file passes for
    compose, fails for export)."""
    path = tdir / "settings.json"
    if not path.is_file():
        if what == "export":
            raise SystemExit(f"export: no {path}: compose the set first")
        return
    diff = T.settings_diff(json.loads(path.read_text(encoding="utf-8"))["settings"], s)
    if diff and not a.force:
        raise SystemExit(f"{what}: {path} records other settings than --set {a.set}'s (keys {', '.join(diff)}); "
                         "pick the set that made it, another --out, or --force")
    if diff:
        log(f"{what}: --force over {path} (keys {', '.join(diff)})")


def set_settings(a):
    """--set's settings with --settings merged over them."""
    base = dict(T.SETS[a.set])
    if a.settings:
        base.update(json.loads(a.settings))
    return base


def stage_compose(a, out):
    base = set_settings(a)
    if not a.variants:
        check_settings(a, out / "textures", base, "compose")
    f, cov = load_fields(out, a.size)
    if a.variants:
        for name, over in json.loads(Path(a.variants).read_text(encoding="utf-8")).items():
            s = dict(base)
            s.update(over)
            compose(f, cov, s, Path(a.vout) / name, a.size)
    else:
        compose(f, cov, base, out / "textures", a.size)


# ---------------------------------------------------------------- export
def gltf_output_group():
    """The glTF exporter's custom output node group, with the Occlusion input."""
    ng = bpy.data.node_groups.get("glTF Material Output")
    if ng is None:
        ng = bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
        ng.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
        ng.interface.new_socket("Thickness", in_out="INPUT", socket_type="NodeSocketFloat")
    return ng


def texture_skin(body, tdir, normal_png, tag):
    """alien_hue takes the texture set; returns the material."""
    mt = body.data.materials[0]
    nt = mt.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    uvn = nt.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = UV_LAYER

    def tex(path, name, colour):
        img = bpy.data.images.load(str(path))
        img.name = name
        img.colorspace_settings.name = "sRGB" if colour else "Non-Color"
        node = nt.nodes.new("ShaderNodeTexImage")
        node.name = name
        node.image = img
        nt.links.new(uvn.outputs["UV"], node.inputs["Vector"])
        return node

    for lk in list(bsdf.inputs["Base Color"].links):
        nt.links.remove(lk)
    alb = tex(tdir / "albedo.png", "alien_skin_albedo", True)
    nt.links.new(alb.outputs["Color"], bsdf.inputs["Base Color"])
    orm = tex(tdir / "orm.png", "alien_skin_orm", False)
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(orm.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    grp = nt.nodes.new("ShaderNodeGroup")
    grp.node_tree = gltf_output_group()
    nt.links.new(sep.outputs["Red"], grp.inputs["Occlusion"])
    nm_tex = nt.nodes.get("skin_normal")
    if nm_tex is not None and normal_png is not None:
        img = bpy.data.images.load(str(normal_png))
        img.colorspace_settings.name = "Non-Color"
        img.name = f"alien_skin_normal_{tag}"
        nm_tex.image = img
    body.data.uv_layers.active = body.data.uv_layers[UV_LAYER]
    return mt


def strip_images(mt):
    """Removes a material's image and normal map nodes (their links go with them): the crest parts' copy of the
    skin must not carry M2's normal map, which they would sample through their own UVs."""
    nt = mt.node_tree
    gone = [n.name for n in nt.nodes if n.type in ("TEX_IMAGE", "NORMAL_MAP")]
    for name in gone:
        nt.nodes.remove(nt.nodes[name])
    return gone


def glb_json(path):
    """The JSON chunk of a GLB."""
    b = Path(path).read_bytes()
    n, kind = struct.unpack_from("<I4s", b, 12)
    if b[:4] != b"glTF" or kind != b"JSON":
        raise SystemExit(f"{path}: not a GLB")
    return json.loads(b[20:20 + n])


def check_images(glb):
    """Fails the stage when a material other than alien_hue and the mouth flipbooks references an image."""
    g = glb_json(glb)
    bad = T.unexpected_images(g)
    if bad:
        raise SystemExit(f"export: images on materials that must have none: {json.dumps(bad)}")
    log("images per material", json.dumps(T.image_materials(g)))


def stage_export(a, out):
    check_settings(a, out / "textures", set_settings(a), "export")
    m2 = Path(a.m2)
    bpy.ops.wm.open_mainfile(filepath=str(m2 / "export" / "alien_character.blend"))
    body = bpy.data.objects["Body"]
    skin = body.data.materials[0]
    part = skin.copy()  # the crest parts get an untextured copy: their UVs are not Body's UVMap
    part.name = PART_MATERIAL
    log("removed from " + PART_MATERIAL, strip_images(part))
    parts = []
    for o in bpy.data.objects:
        if o is not body and o.type == "MESH":
            for slot in o.material_slots:
                if slot.material is skin:
                    slot.material = part
                    parts.append(o.name)
    log("parts on " + PART_MATERIAL, parts)
    texture_skin(body, out / "textures", bake_dir(a) / "normal.png", a.set)
    ex = out / "export"
    ex.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(ex / "alien_character.blend"))
    opts = dict(export_glb.options(False), export_image_format="AUTO", export_vertex_color="ACTIVE", export_tangents=True)
    res = bpy.ops.export_scene.gltf(filepath=str(ex / "alien_character.glb"), **opts)
    if res != {"FINISHED"}:
        raise SystemExit(f"export: {res}")
    check_images(ex / "alien_character.glb")
    src = Path(a.kit) if a.kit else m2 / "export"
    for f in src.iterdir():
        if f.suffix == ".png":
            shutil.copy2(f, ex / f.name)
    shutil.copy2(out / "textures" / "sss.png", ex / "alien_skin_sss.png")
    cj = json.loads((src / "character.json").read_text(encoding="utf-8"))
    cj[f"note_{a.set}_textures"] = T.texture_note(a.set, set_settings(a))
    (ex / "character.json").write_text(json.dumps(cj, indent=1), encoding="utf-8", newline="\n")
    log("EXPORT " + str(ex / "alien_character.glb"))


def main():
    a = args()
    out = Path(a.out)
    {"cage": stage_cage, "fields": stage_fields, "compose": stage_compose, "export": stage_export}[a.stage](a, out)


if __name__ == "__main__":
    main()
