"""The clay bake (inside Blender): every clay part of a character baked into plain glTF textures, and the per-piece
clay library that bakes each piece once and hands it to every character that wears it (docs/assembly.md, "The clay
look"; ported from clay_bake.py and clay_libbake.py of D:/prime-art-raw/research/2026-10-05-faces/lab/clay_d, whose
README_bake.txt holds the measurements behind the choices).

Per part: a fresh UV map 'bake' (Smart UV Project at 75 degrees, islands at one texel density, the clay islands packed
with a margin of 3 colour-map texels; the glossy faces keep overlapping UVs and sample nothing); a base colour map
(sRGB RGBA: RGB the clay's colour, A the skin mask; a clothing part's colour is its undecimated pack part's flat
colours, selected to active, times the clay's own mottle, so colour borders stay straight), baked at 2 x and
box-filtered down; a tangent-space normal map (OpenGL +Y), its folded-triangle texels set flat; every gutter
flood-filled (push-pull) so no mip mixes an island with black. The part then wears one baked material (both maps on
'bake', roughness 0.8, specular 0.5) plus its plain glossy materials.

The library: <lib>/<body type>/<role>/<key>/ holds piece.blend (the baked object in world rest coordinates, its
vertex groups and material), tex/ and piece.json; the key (um/claylook.piece_key) names everything the piece depends
on. A character bake loads every piece it finds and bakes only the missing ones.
"""

import json
import math
import os
import time

import bpy
import numpy as np
from mathutils import Matrix

from . import claylook as L
from .clay import MASK_UV, is_clay, tris
from .util import update

SENTINEL = (1.0, 0.0, 1.0)  # magenta: no clay colour is pure magenta; a texel still magenta after a bake is unbaked
PIECE_OBJECT = "piece"


# ----------------------------------------------------------------------------------------------- areas and UVs
def _clay_polys(o, clay_only):
    idx = {i for i, s in enumerate(o.material_slots) if is_clay(s.material)}
    return [p for p in o.data.polygons if not clay_only or p.material_index in idx]


def world_area(o, clay_only=True):
    mw = o.matrix_world
    me = o.data
    a = 0.0
    for p in _clay_polys(o, clay_only):
        vs = [mw @ me.vertices[i].co for i in p.vertices]
        for k in range(1, len(vs) - 1):
            a += (vs[k] - vs[0]).cross(vs[k + 1] - vs[0]).length / 2
    return a


def uv_area(o, clay_only=True):
    uv = o.data.uv_layers.active.data
    a = 0.0
    for p in _clay_polys(o, clay_only):
        q = [uv[li].uv for li in p.loop_indices]
        for k in range(1, len(q) - 1):
            e1, e2 = q[k] - q[0], q[k + 1] - q[0]
            a += abs(e1.x * e2.y - e1.y * e2.x) / 2
    return a


def _only(o):
    for ob in bpy.context.view_layer.objects:
        ob.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    return dict(active_object=o, object=o, selected_objects=[o], selected_editable_objects=[o])


def unwrap(o, margin):
    """A fresh UV map 'bake' (the pack's overlapping palette UVs removed): Smart UV Project, islands at one density,
    the clay islands packed. Returns the clay UV use."""
    me = o.data
    keep = {}  # the face kit's mask UV survives the unwrap, after 'bake' (glTF TEXCOORD_1)
    if me.uv_layers.get(MASK_UV):
        keep[MASK_UV] = [0.0] * (2 * len(me.loops))
        me.uv_layers[MASK_UV].data.foreach_get("uv", keep[MASK_UV])
    for layer in list(me.uv_layers):
        me.uv_layers.remove(layer)
    me.uv_layers.new(name="bake")
    for name, uv in keep.items():
        me.uv_layers.new(name=name).data.foreach_set("uv", uv)
    me.uv_layers.active = me.uv_layers["bake"]
    for u in me.uv_layers:
        u.active_render = u.name == "bake"
    with bpy.context.temp_override(**_only(o)):
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_mode(type="FACE")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(L.UV_ANGLE), island_margin=0.0, area_weight=0.0,
                                 correct_aspect=True, scale_to_bounds=False)
        bpy.ops.uv.select_all(action="SELECT")
        bpy.ops.uv.average_islands_scale()
        bpy.ops.object.mode_set(mode="OBJECT")
    return pack(o, margin)


def pack(o, margin):
    """Packs o's clay islands on 'bake' with margin (a fraction of the side); the glossy faces hidden meanwhile."""
    o.data.uv_layers.active = o.data.uv_layers["bake"]
    ov = _only(o)
    gloss = {i for i, s in enumerate(o.material_slots) if not is_clay(s.material)}
    with bpy.context.temp_override(**ov):
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.reveal()
        bpy.ops.mesh.select_all(action="DESELECT")
        for i in sorted(gloss):
            o.active_material_index = i
            bpy.ops.object.material_slot_select()
        if gloss:
            bpy.ops.mesh.hide(unselected=False)
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.select_all(action="SELECT")
        bpy.ops.uv.pack_islands(rotate=True, scale=True, margin_method="FRACTION", margin=margin, shape_method="CONCAVE")
        bpy.ops.mesh.reveal()
        bpy.ops.object.mode_set(mode="OBJECT")
    o.active_material_index = 0
    return uv_area(o)


# ----------------------------------------------------------------------------------------------- Cycles
def cycles(sc, samples=L.BAKE_SAMPLES):
    """Cycles on the GPU when there is one (OptiX, then CUDA), else the CPU. Returns the device."""
    sc.render.engine = "CYCLES"
    dev = "CPU"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = kind
                prefs.get_devices()
                if any(d.type == kind for d in prefs.devices):
                    for d in prefs.devices:
                        d.use = d.type == kind
                    sc.cycles.device = "GPU"
                    dev = kind
                    break
            except Exception:  # noqa: BLE001  (a missing backend raises; try the next)
                continue
    except KeyError:
        pass
    sc.cycles.samples = samples
    sc.cycles.use_denoising = False
    sc.render.bake.margin = L.BAKE_MARGIN_PX
    sc.render.bake.margin_type = "EXTEND"
    sc.render.bake.target = "IMAGE_TEXTURES"
    return dev


def principled(mat):
    return next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")


def output_node(mat):
    return next(n for n in mat.node_tree.nodes if n.type == "OUTPUT_MATERIAL")


def new_image(name, size, data, colour=None):
    img = bpy.data.images.get(name)
    if img is not None:
        bpy.data.images.remove(img)
    img = bpy.data.images.new(name, size, size, alpha=False, float_buffer=False)
    img.colorspace_settings.name = "Non-Color" if data else "sRGB"
    img.generated_color = colour or ((0.5, 0.5, 1.0, 1.0) if data else (0.5, 0.5, 0.5, 1.0))
    return img


def sentinel(name, size):
    return new_image(name, size, False, (*SENTINEL, 1.0))


def pixels(img):
    w, h = img.size
    a = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(h, w, 4)


def unbaked(a):
    return (a[..., 0] > 0.99) & (a[..., 1] < 0.01) & (a[..., 2] > 0.99)


def set_targets(o, target, dummy):
    """Every material of o gets one active Image Texture node 'bake_target': target on clay, dummy on the rest."""
    for s in o.material_slots:
        nt = s.material.node_tree
        n = nt.nodes.get("bake_target") or nt.nodes.new("ShaderNodeTexImage")
        n.name = "bake_target"
        n.image = target if is_clay(s.material) else dummy
        nt.nodes.active = n


def emit(o, value_of=None, socket="Base Color"):
    """Every material of o (clay only when value_of is None) shows its Principled `socket` (or value_of(material) ->
    rgb) as emission. Returns the undo list."""
    undo = []
    for s in o.material_slots:
        m = s.material
        if m is None or m.node_tree is None or (value_of is None and not is_clay(m)):
            continue
        nt = m.node_tree
        out = output_node(m)
        old = out.inputs["Surface"].links[0].from_socket if out.inputs["Surface"].is_linked else None
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Strength"].default_value = 1.0
        if value_of is not None:
            em.inputs["Color"].default_value = (*value_of(m), 1.0)
        else:
            inp = principled(m).inputs[socket]
            if inp.is_linked:
                nt.links.new(inp.links[0].from_socket, em.inputs["Color"])
            else:
                v = inp.default_value
                em.inputs["Color"].default_value = (v, v, v, 1.0) if isinstance(v, float) else tuple(v)
        nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
        undo.append((m, em, old))
    return undo


def emit_undo(undo):
    for m, em, old in undo:
        m.node_tree.nodes.remove(em)
        if old is not None:
            m.node_tree.links.new(old, output_node(m).inputs["Surface"])


def run_bake(o, kind, src=None):
    """NORMAL or EMIT onto o's bake targets without clearing (unbaked texels keep the sentinel); with src, EMIT
    selected (src) to active (o)."""
    sel = [o] if src is None else [src, o]
    for ob in bpy.context.view_layer.objects:
        ob.select_set(False)
    if src is not None:
        src.hide_set(False)
        src.hide_render = False
    for ob in sel:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = o
    with bpy.context.temp_override(active_object=o, object=o, selected_objects=sel, selected_editable_objects=sel):
        if kind == "NORMAL":
            bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT", normal_r="POS_X", normal_g="POS_Y",
                                normal_b="POS_Z", margin=L.BAKE_MARGIN_PX, margin_type="EXTEND", use_clear=False)
        elif src is None:
            bpy.ops.object.bake(type="EMIT", margin=L.BAKE_MARGIN_PX, margin_type="EXTEND", use_clear=False)
        else:
            bpy.ops.object.bake(type="EMIT", use_selected_to_active=True, cage_extrusion=L.CAGE_M, max_ray_distance=0.0,
                                margin=L.BAKE_MARGIN_PX, margin_type="EXTEND", use_clear=False)
    if src is not None:
        src.hide_render = True


def fill_gutter(a, valid):
    """Push-pull: every invalid texel takes the mean of the valid texels round it at the finest level of a box
    pyramid that has any, so the gutters carry the islands' own colours outward to every mip level."""
    if valid.all() or not valid.any():
        return a
    wts = [valid.astype(np.float64)]
    sums = [a.astype(np.float64) * wts[0][..., None]]
    while sums[-1].shape[0] > 1 and sums[-1].shape[1] > 1:
        S, W = sums[-1], wts[-1]
        hh, ww = S.shape[0] // 2 * 2, S.shape[1] // 2 * 2
        S, W = S[:hh, :ww], W[:hh, :ww]
        sums.append(S[0::2, 0::2] + S[1::2, 0::2] + S[0::2, 1::2] + S[1::2, 1::2])
        wts.append(W[0::2, 0::2] + W[1::2, 0::2] + W[0::2, 1::2] + W[1::2, 1::2])
    filled = sums[-1] / np.maximum(wts[-1], 1e-9)[..., None]
    for S, W in zip(reversed(sums[:-1]), reversed(wts[:-1])):
        up = np.repeat(np.repeat(filled, 2, axis=0), 2, axis=1)
        if up.shape[0] < S.shape[0] or up.shape[1] < S.shape[1]:
            up = np.pad(up, ((0, S.shape[0] - up.shape[0]), (0, S.shape[1] - up.shape[1]), (0, 0)), mode="edge")
        up = up[:S.shape[0], :S.shape[1]]
        filled = np.where((W > 0)[..., None], S / np.maximum(W, 1e-9)[..., None], up)
    out = a.copy()
    out[~valid] = filled[~valid].astype(a.dtype)
    return out


def srgb_to_lin(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(np.asarray(c, dtype=np.float64), 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def is_skin(mat):
    return mat is not None and mat.name.split(".")[0].lower().endswith("skin")


def clay_rgb(m):
    n = m.node_tree.nodes.get("clay_rgb") if m and m.node_tree else None
    return n


# ----------------------------------------------------------------------------------------------- colour and mask
def bake_colour(o, name, csize, dummy, src=None):
    """The base colour (RGB, sRGB) and skin mask (A) as one RGBA image at csize, gutters filled. With src (a static
    pack part at the same place): pack colour x the clay mottle, the pack's skin in this part's clay skin tone, the
    mask from the pack's skin faces; otherwise the clay's own colour and skin. Returns (image, info)."""
    info = {"colour_source": "pack part x clay mottle" if src is not None else "clay material",
            "colour_supersample": L.COLOUR_SS}
    t0 = time.time()
    big = csize * L.COLOUR_SS
    if src is not None:
        mot = sentinel(name + "_mottle", big)
        keep = {}
        for s in o.material_slots:
            n = clay_rgb(s.material)
            if n is not None and s.material.name not in keep:
                keep[s.material.name] = tuple(n.outputs[0].default_value)
                n.outputs[0].default_value = (L.GREY, L.GREY, L.GREY, 1.0)
        set_targets(o, mot, dummy)
        undo = emit(o)
        run_bake(o, "EMIT")
        emit_undo(undo)
        for s in o.material_slots:
            if s.material and s.material.name in keep:
                clay_rgb(s.material).outputs[0].default_value = keep[s.material.name]
        tone = next((tuple(clay_rgb(s.material).outputs[0].default_value[:3]) for s in o.material_slots
                     if is_skin(s.material) and clay_rgb(s.material) is not None), None)
        info["source_skin_tone"] = [round(x, 4) for x in tone] if tone else None
        orig = list(src.data.materials)
        skin_slot = [is_skin(m) for m in orig]
        emats = []
        for i, m in enumerate(orig):
            rgb = tone if (tone and skin_slot[i]) else (tuple(m.diffuse_color[:3]) if m else (0.5, 0.5, 0.5))
            em = bpy.data.materials.new(f"{name}_src{i}")
            em.use_nodes = True
            nt = em.node_tree
            nt.nodes.clear()
            e = nt.nodes.new("ShaderNodeEmission")
            e.inputs["Color"].default_value = (*rgb, 1.0)
            nt.links.new(e.outputs["Emission"], nt.nodes.new("ShaderNodeOutputMaterial").inputs["Surface"])
            src.data.materials[i] = em
            emats.append((em, e))
        pcol = sentinel(name + "_packcol", big)
        set_targets(o, pcol, dummy)
        run_bake(o, "EMIT", src=src)
        A, B = pixels(mot), pixels(pcol)
        valid = ~unbaked(A)
        miss = valid & unbaked(B)  # clay texels the source rays did not reach: the clay's own colour there
        info["source_missed_texels"] = int(miss.sum())
        rgb = lin_to_srgb(srgb_to_lin(B[..., :3]) * (srgb_to_lin(A[..., :3]) / L.GREY))
        if miss.any():
            own = sentinel(name + "_own", big)
            set_targets(o, own, dummy)
            undo = emit(o)
            run_bake(o, "EMIT")
            emit_undo(undo)
            rgb[miss] = pixels(own)[..., :3][miss]
            bpy.data.images.remove(own)
        for (em, e), sk in zip(emats, skin_slot):
            e.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0) if sk else (0.0, 0.0, 0.0, 1.0)
        pm = sentinel(name + "_packmask", big)
        set_targets(o, pm, dummy)
        run_bake(o, "EMIT", src=src)
        M = pixels(pm)
        mask = np.where(unbaked(M), 0.0, M[..., 0])
        for i, m in enumerate(orig):
            src.data.materials[i] = m
        for em, _ in emats:
            bpy.data.materials.remove(em)
        for im in (mot, pcol, pm):
            bpy.data.images.remove(im)
    else:
        col = sentinel(name + "_rgb", big)
        set_targets(o, col, dummy)
        undo = emit(o)
        run_bake(o, "EMIT")
        emit_undo(undo)
        A = pixels(col)
        valid = ~unbaked(A)
        rgb = A[..., :3].astype(np.float64)
        bpy.data.images.remove(col)
        mk = sentinel(name + "_mask", big)
        set_targets(o, mk, dummy)
        undo = emit(o, value_of=lambda m: (1.0, 1.0, 1.0) if is_skin(m) else (0.0, 0.0, 0.0))
        run_bake(o, "EMIT")
        emit_undo(undo)
        M = pixels(mk)
        mask = np.where(unbaked(M), 0.0, M[..., 0])
        bpy.data.images.remove(mk)
    info["colour_mask_bake_s"] = round(time.time() - t0, 2)
    rgba = np.concatenate([rgb, mask[..., None]], axis=2)
    k = L.COLOUR_SS
    if k > 1:  # box filter down: each texel the mean of its valid sub-texels
        wv = valid.astype(np.float64).reshape(csize, k, csize, k).sum(axis=(1, 3))
        acc = (rgba * valid[..., None]).reshape(csize, k, csize, k, 4).sum(axis=(1, 3))
        rgba = acc / np.maximum(wv, 1e-9)[..., None]
        valid = wv > 0
    rgba = fill_gutter(rgba.astype(np.float32), valid)
    info["gutter_filled_texels"] = int((~valid).sum())
    info["skin_mask_texels"] = int((rgba[..., 3][valid] > 0.5).sum())
    img = bpy.data.images.new(name + "_col", csize, csize, alpha=True, float_buffer=False)
    img.colorspace_settings.name = "sRGB"
    img.alpha_mode = "CHANNEL_PACKED"  # the alpha is the skin mask, not coverage
    img.pixels.foreach_set(np.clip(rgba, 0.0, 1.0).ravel())
    img.update()
    return img, info


def bake_normal(o, name, size, dummy):
    nrm = new_image(name + "_nrm", size, True, (0.0, 0.0, 0.0, 1.0))
    set_targets(o, nrm, dummy)
    t0 = time.time()
    run_bake(o, "NORMAL")
    N = pixels(nrm)
    valid = N[..., 2] > 0.25
    n = N[..., :3] * 2.0 - 1.0
    bad = valid & (n[..., 2] < L.NORMAL_MIN_Z)  # folded, back-facing pack triangles: set flat
    n[~valid | bad] = (0.0, 0.0, 1.0)
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6)
    N[..., :3] = n * 0.5 + 0.5
    N[..., 3] = 1.0
    N = fill_gutter(N, valid)
    nrm.pixels.foreach_set(N.ravel())
    nrm.update()
    return nrm, {"normal_texels_set_flat": int(bad.sum()), "normal_bake_s": round(time.time() - t0, 2)}


def save_png(img, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    img.filepath = path
    img.source = "FILE"
    img.reload()


def baked_material(name, col, nrm, rgb):
    """A plain glTF material: baseColorTexture and a tangent-space normalTexture on 'bake', roughness and specular
    constant."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(p.outputs["BSDF"], out.inputs["Surface"])
    uvn = nt.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = "bake"
    tc = nt.nodes.new("ShaderNodeTexImage")
    tc.name = "base_color"
    tc.image = col
    nt.links.new(uvn.outputs["UV"], tc.inputs["Vector"])
    nt.links.new(tc.outputs["Color"], p.inputs["Base Color"])
    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.name = "normal"
    tn.image = nrm
    nt.links.new(uvn.outputs["UV"], tn.inputs["Vector"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.space = "TANGENT"
    nm.uv_map = "bake"
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], p.inputs["Normal"])
    p.inputs["Roughness"].default_value = L.ROUGHNESS
    p.inputs["Metallic"].default_value = 0.0
    p.inputs["Specular IOR Level"].default_value = L.SPECULAR_LEVEL
    mat.diffuse_color = (*rgb, 1.0)
    mat.roughness = L.ROUGHNESS
    mat["look"] = "baked"
    return mat


def swap_to_baked(o, baked):
    """The part's clay slots become one baked material (slot 0); its glossy slots stay, after it."""
    me = o.data
    old = [s.material for s in o.material_slots]
    idx = [p.material_index for p in me.polygons]
    me.materials.clear()
    me.materials.append(baked)
    remap = {}
    for i, m in enumerate(old):
        if is_clay(m):
            remap[i] = 0
        else:
            if m not in list(me.materials):
                me.materials.append(m)
            remap[i] = list(me.materials).index(m)
    me.polygons.foreach_set("material_index", [remap[i] for i in idx])
    me.update()


def bake_part(o, name, tex_dir, density, src=None):
    """Bakes one clay part into <tex_dir>/<name>_{col,nrm}.png and gives it its baked material. Returns its info."""
    t0 = time.time()
    dummy = new_image(name + "_dummy", 8, False)
    area = world_area(o)
    margin = L.MARGIN_START
    frac = unwrap(o, margin)
    packs = [(round(margin, 4), round(frac, 3))]
    for _ in range(3):  # the margin in colour-map texels at the size this packing gives
        csize = L.colour_size(L.pick_size(area, frac, density))
        need = L.margin_needed(csize)
        if need <= margin * 1.0001:
            break
        margin = need
        frac = pack(o, margin)
        packs.append((round(margin, 4), round(frac, 3)))
    size = L.pick_size(area, frac, density)
    csize = L.colour_size(size)
    t1 = time.time()
    col, info = bake_colour(o, name, csize, dummy, src=src)
    nrm, ninfo = bake_normal(o, name, size, dummy)
    info.update(ninfo)
    pc, pn = os.path.join(tex_dir, name + "_col.png"), os.path.join(tex_dir, name + "_nrm.png")
    save_png(col, pc)
    save_png(nrm, pn)
    rgb = srgb_to_lin(pixels(col)[..., :3].reshape(-1, 3).mean(0)).tolist()
    for s in o.material_slots:
        n = s.material.node_tree.nodes.get("bake_target") if s.material and s.material.node_tree else None
        if n is not None:
            s.material.node_tree.nodes.remove(n)
    clay_slots = [s.material.name for s in o.material_slots if is_clay(s.material)]
    plain = [s.material.name for s in o.material_slots if not is_clay(s.material)]
    swap_to_baked(o, baked_material(name + "_clay", col, nrm, rgb))
    bpy.data.images.remove(dummy)
    dens = L.texel_density(size, frac, area)
    info.update({
        "triangles": tris(o.data), "clay_area_m2": round(area, 4), "uv_used": round(frac, 3), "normal_px": size,
        "colour_px": csize, "density_target_px_m": density, "normal_px_per_m": round(dens, 1),
        "normal_mm_per_texel": round(1000 / dens, 2), "clay_slots": clay_slots, "plain_slots": plain,
        "surfaces": len(o.material_slots), "pack_margin": round(margin, 4), "packs": packs,
        "png_bytes": {"col": os.path.getsize(pc), "nrm": os.path.getsize(pn)},
        "unwrap_s": round(t1 - t0, 2), "bake_s": round(time.time() - t1, 2), "seconds": round(time.time() - t0, 2),
    })
    return info


# ----------------------------------------------------------------------------------------------- the library
def piece_dir(lib, gender, role, key):
    return os.path.join(lib, gender, role, key)


def write_piece(o, folder, meta):
    """The baked part as a world-space object 'piece' (no parent, no modifiers) in <folder>/piece.blend, with
    piece.json."""
    cp = o.copy()
    cp.data = o.data.copy()
    cp.data.transform(o.matrix_world, shape_keys=True)
    cp.parent = None
    cp.matrix_world = Matrix.Identity(4)
    for m in list(cp.modifiers):
        cp.modifiers.remove(m)
    cp.name = PIECE_OBJECT
    path = os.path.join(folder, "piece.blend")
    bpy.data.libraries.write(path, {cp}, path_remap="ABSOLUTE", fake_user=False, compress=True)
    me = cp.data
    bpy.data.objects.remove(cp, do_unlink=True)
    bpy.data.meshes.remove(me)
    with open(os.path.join(folder, "piece.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1)


def load_piece(o, folder, arm):
    """Replaces part o's mesh, vertex groups and materials with the library piece in <folder>; o keeps its name,
    parent and Armature modifier. Returns the piece's json."""
    with bpy.data.libraries.load(os.path.join(folder, "piece.blend"), link=False) as (src, dst):
        dst.objects = [PIECE_OBJECT]
    pc = dst.objects[0]
    me = pc.data
    me.transform(o.matrix_world.inverted(), shape_keys=True)
    old = o.data
    o.data = me
    me.name = old.name
    if old.users == 0:
        bpy.data.meshes.remove(old)
    o.vertex_groups.clear()
    for g in pc.vertex_groups:
        o.vertex_groups.new(name=g.name)
    bpy.data.objects.remove(pc, do_unlink=True)
    with open(os.path.join(folder, "piece.json"), encoding="utf-8") as fh:
        return json.load(fh)


def bake_character(cid, arm, parts, sources, keys, gender, lib, cfg, samples=L.BAKE_SAMPLES):
    """The character bake from the library: each part (rest position, at the origin, after the clay pass) is loaded
    from <lib>/<gender>/<role>/<keys[role]>/ when that piece exists, else baked and written there. Returns the report
    (per part: hit or baked, the piece's numbers, seconds)."""
    arm.data.pose_position = "REST"
    update()
    t0 = time.time()
    dev = cycles(bpy.context.scene, samples)
    rep = {"device": dev, "samples": samples, "library": lib.replace("\\", "/"), "parts": {}}
    for role, o in parts.items():
        t = time.time()
        folder = piece_dir(lib, gender, role, keys[role])
        if not any(is_clay(s.material) for s in o.material_slots):  # glossy only (eyes): nothing to bake
            rep["parts"][role] = {"from": "plain", "key": None, "seconds": 0.0, "piece": {}, "triangles": tris(o.data),
                                  "surfaces": len(o.material_slots)}
            continue
        if os.path.isfile(os.path.join(folder, "piece.json")):
            meta = load_piece(o, folder, arm)
            how = "library"
        else:
            os.makedirs(folder, exist_ok=True)
            info = bake_part(o, f"{role}_{keys[role]}", os.path.join(folder, "tex"),
                             cfg["density"].get(role, L.DEFAULT_DENSITY), src=sources.get(role))
            meta = {"key": keys[role], "role": role, "gender": gender, "first_character": cid, "bake": info,
                    "bake_version": L.BAKE_VERSION}
            write_piece(o, folder, meta)
            how = "baked"
        for s in o.material_slots:  # the character's own name on its baked material
            if s.material and s.material.get("look") == "baked":
                s.material.name = f"{cid}_{role}_clay"
        rep["parts"][role] = {"from": how, "key": keys[role], "seconds": round(time.time() - t, 2),
                              "piece": meta.get("bake", {}), "triangles": tris(o.data),
                              "surfaces": len(o.material_slots)}
        print("CLAYBAKE", cid, role, how, keys[role], rep["parts"][role]["seconds"], "s", flush=True)
    update()
    rep["seconds"] = round(time.time() - t0, 2)
    rep["surfaces"] = sum(p["surfaces"] for p in rep["parts"].values())
    return rep
