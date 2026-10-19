"""M4, the modern eyes (art #196): the parts kit's eyes after M3a, in headless Blender. Opens a kit's
export/alien_character.blend and writes a new kit beside it (never over it):

- the wet line: per lid a thin strip `eye_<design>_wet_<upper|lower>_<L|R>`, a child of its lid node (so it turns with
  the lid), from the ball just beyond the lid's rolled rim up under the rim (alien_eyes_geom.wet_profile), material
  `alien_wet` (godot/alien/alien_wet.gdshader in Godot; a clear glossy, half-transparent Principled here);
- the eyeballs' materials `alien_eye_<design>` get a clear coat (glTF KHR_materials_clearcoat: a wet sheen for Blender
  and the three.js page; Godot draws the eye with godot/alien/alien_eye.gdshader, whose cornea, iris depth, contact
  shadow and sclera falloff are per pixel and need no mesh);
- export/alien_character.glb (the M3a export options), its .blend, character.json (`nodes.eyes.<design>.<side>` gets
  `wet_upper`, `wet_lower`; `note_m4_eyes`), the PNGs beside the kit's GLB copied.

Runs in background Blender through the runner, never by hand and never in a window:
tools/runner/blender.py's run_script("alien_eyes.py", ["--kit", <M3a/export>, "--out", <M4>, "--eye-images",
<S9/parts/export>]).

M5 (art #196): `--sss-orm` also writes the skin's ORM again with the subsurface mask in its B channel (glTF's
metallic, unused: `<out>/textures/orm_sss.png`, 4K RGB: the kit's R occlusion and G roughness unchanged, the 2K
`alien_skin_sss.png` beside the kit upscaled into B), multiplies Metallic by 0 (metallicFactor 0: plain viewers
stay non-metal)
and marks `alien_hue` with the glTF extras {"prime_sss": "orm_b"}. The exporter copies a PNG file's bytes as they are
when one image fills a texture with its channels in place (its "happy path"), so the mask reaches the GLB; the build
checks it there (alien_eyes_geom.sss_orm_problems). godot/alien/alien.gd takes the textured skin only for that marker.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import struct
import sys
from pathlib import Path

import bpy
import bmesh

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_eyes_geom as E  # noqa: E402
import alien_texture_geom as T  # noqa: E402
import export_glb  # noqa: E402
from alien_parts import EYES, LID_BEAD  # noqa: E402

WET_SRGB = (0.98, 0.92, 0.90)
WET_ALPHA = 0.55
COAT = {"weight": 1.0, "roughness": 0.08}


def log(*a):
    print("M4", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--kit", required=True, help="the input kit's export folder (alien_character.blend, character.json)")
    p.add_argument("--out", required=True, help="the M4 folder; the kit goes into <out>/export")
    p.add_argument("--eye-images", required=True, help="the parts build's export folder (alien_eye_<design>.png)")
    p.add_argument("--sss-orm", action="store_true",
                   help="M5: the kit's alien_skin_sss.png into the ORM's B (<out>/textures/orm_sss.png)")
    return p.parse_args(argv)


def check_images(glb: Path):
    """M3a's export check on the new GLB: only the skin, the flipbook mouths and the eyeballs (alien_texture_geom's
    IMAGE_MATERIALS, IMAGE_MATERIAL_PREFIXES) may reference an image; anything else fails the build."""
    b = glb.read_bytes()
    n, kind = struct.unpack_from("<I4s", b, 12)
    if b[:4] != b"glTF" or kind != b"JSON":
        raise SystemExit(f"{glb}: not a GLB")
    g = json.loads(b[20:20 + n])
    bad = T.unexpected_images(g)
    if bad:
        raise SystemExit(f"export: images on materials that must have none: {json.dumps(bad)}")
    log("images per material", json.dumps(T.image_materials(g)))


def wet_material():
    m = bpy.data.materials.new("alien_wet")
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*[c ** 2.2 for c in WET_SRGB], 1)
    bsdf.inputs["Roughness"].default_value = 0.08
    bsdf.inputs["Alpha"].default_value = WET_ALPHA
    m.surface_render_method = "BLENDED"
    m.use_backface_culling = True
    return m


def restore_eye_image(mat, bsdf, dname: str, folder: str, ex: Path):
    """The eyeball's 512 px texture (alien_parts.eye_image) back on its material, packed into the .blend: the M3a GLB's
    alien_eye_<design> had lost its baseColorTexture (the image file was not beside the kit's .blend, so the export
    left it out and plain glTF viewers drew a white ball). A copy goes beside the new GLB."""
    src = Path(folder) / f"alien_eye_{dname}.png"
    if not src.is_file():
        raise SystemExit(f"no eye image {src}")
    img = bpy.data.images.load(str(src), check_existing=False)
    img.name = f"alien_eye_{dname}"
    img.pack()
    tex = next((n for n in mat.node_tree.nodes if n.type == "TEX_IMAGE"), None)
    if tex is None:
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = img
    mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    ex.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, ex / src.name)
    log(dname, "eye image", src, img.size[:])


def sss_into_orm(kit: Path, out: Path) -> Path:
    """M5: alien_hue's ORM image with the kit's SSS mask (2K grey, white = thin) in its B channel (glTF's metallic,
    unused), written as a 4K RGB PNG into <out>/textures/orm_sss.png and put on the ORM node. R (occlusion) and G
    (roughness) are copied unchanged (8-bit in, 8-bit out, checked); the mask is upscaled by two with
    alien_eyes_geom.UPSCALE2_TAPS. Separate Color's B drives Metallic through a multiply by 0, so the exporter
    writes metallicFactor 0 and copies the PNG as it is; the material gets the SSS_MARKER custom property (glTF
    extras)."""
    import numpy as np
    mat = bpy.data.materials["alien_hue"]
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    sep = next(lk.from_node for lk in bsdf.inputs["Roughness"].links if lk.from_node.type == "SEPARATE_COLOR")
    node = next(lk.from_node for lk in sep.inputs["Color"].links if lk.from_node.type == "TEX_IMAGE")
    src = node.image
    w, h = src.size
    rgba = np.empty(w * h * 4, dtype=np.float32)
    src.pixels.foreach_get(rgba)
    rgba = rgba.reshape(h, w, 4)
    sp = kit / "alien_skin_sss.png"
    if not sp.is_file():
        raise SystemExit(f"no SSS mask {sp}")
    simg = bpy.data.images.load(str(sp), check_existing=False)
    simg.colorspace_settings.name = "Non-Color"
    sw, sh = simg.size
    if (w, h) != (2 * sw, 2 * sh):
        raise SystemExit(f"SSS mask {sw}x{sh} is not half the ORM's {w}x{h}")
    m = np.empty(sw * sh * 4, dtype=np.float32)
    simg.pixels.foreach_get(m)
    pad = np.pad(m.reshape(sh, sw, 4)[..., 0], 1, mode="edge")
    up = np.empty((h, w), dtype=np.float32)
    for dy in (0, 1):
        for dx in (0, 1):
            sy, sx = E.upscale2_step(dy), E.upscale2_step(dx)
            acc = np.zeros((sh, sw), dtype=np.float32)
            for ky, kx, wt in E.UPSCALE2_TAPS:
                oy, ox = 1 + ky * sy, 1 + kx * sx
                acc += wt * pad[oy:oy + sh, ox:ox + sw]
            up[dy::2, dx::2] = acc
    rgba[..., 2] = np.clip(up, 0.0, 1.0)
    rgba[..., 3] = 1.0
    tdir = out / "textures"
    tdir.mkdir(parents=True, exist_ok=True)
    path = tdir / "orm_sss.png"
    img = bpy.data.images.new("alien_skin_orm_sss_tmp", w, h, alpha=False, float_buffer=False)
    img.colorspace_settings.name = "Non-Color"
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    new = bpy.data.images.load(str(path), check_existing=False)
    new.name = "alien_skin_orm_sss"
    new.colorspace_settings.name = "Non-Color"
    back = np.empty(w * h * 4, dtype=np.float32)
    new.pixels.foreach_get(back)
    back = back.reshape(h, w, 4)
    drg = float(np.abs(back[..., :2] - rgba[..., :2]).max()) * 255.0
    db = float(np.abs(back[..., 2] - rgba[..., 2]).max()) * 255.0
    if drg > 0.5 or db > 0.6:
        raise SystemExit(f"orm_sss.png round trip: rg {drg:.2f}, b {db:.2f} (of 255)")
    node.image = new
    # B keeps driving Metallic, through a multiply by 0: the exporter reads that as metallicFactor 0 and keeps the
    # image on its happy path (an unlinked Metallic made it rebuild the image without B)
    for lk in list(bsdf.inputs["Metallic"].links):
        nt.links.remove(lk)
    mul = nt.nodes.new("ShaderNodeMath")
    mul.name = "sss_metallic_off"
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = 0.0
    nt.links.new(sep.outputs["Blue"], mul.inputs[0])
    nt.links.new(mul.outputs["Value"], bsdf.inputs["Metallic"])
    for k, v in E.SSS_MARKER.items():
        mat[k] = v
    log("orm + sss", path, (w, h), "from", src.filepath, "sss mean", round(float(up.mean()), 3),
        "round trip rg", round(drg, 3))
    return path


def wet_strip(name: str, lid, r: float, rho: tuple, bead: float, upper: bool, mat, coll):
    """The strip in the lid's own frame, parented to the lid with an identity local transform. UV: u across the lid
    (its latitude, 0 to 1), v from the ball's side (0) to the lid's edge (1)."""
    prof = E.wet_profile(rho[0], rho[1], bead, upper)
    tm = math.radians(E.WET["t_max_deg"])
    n_t = E.WET["seg_t"]
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    grid = []
    for i in range(n_t + 1):
        t = -tm + 2 * tm * i / n_t
        grid.append([bm.verts.new(tuple(r * c for c in E.lid_point(rh, p, t))) for rh, p in prof])
    m = len(prof)
    for i in range(n_t):
        for j in range(m - 1):
            quad = (grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1])
            if not upper:
                quad = quad[::-1]
            f = bm.faces.new(quad)
            for lp in f.loops:
                ii = i + (1 if lp.vert in (grid[i + 1][j], grid[i + 1][j + 1]) else 0)
                jj = j + (1 if lp.vert in (grid[i][j + 1], grid[i + 1][j + 1]) else 0)
                lp[uv].uv = (ii / n_t, jj / (m - 1))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    # the faces face away from the ball (outward): flip any whose normal points in
    me.update()
    flip = sum(1 for poly in me.polygons if poly.normal.dot(poly.center) < 0)
    if flip > len(me.polygons) // 2:
        for poly in me.polygons:
            poly.flip()
    me.materials.append(mat)
    for poly in me.polygons:
        poly.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.parent = lid
    ob.matrix_parent_inverse.identity()
    ob.matrix_basis.identity()
    return ob


def main():
    a = args()
    kit, out = Path(a.kit), Path(a.out)
    ex = out / "export"
    if ex.resolve() == kit.resolve():
        raise SystemExit("the M4 kit must not overwrite its input")
    bpy.ops.wm.open_mainfile(filepath=str(kit / "alien_character.blend"))
    cj = json.loads((kit / "character.json").read_text(encoding="utf-8"))
    wet = wet_material()
    made = []
    for dname, d in EYES.items():
        mat = bpy.data.materials[f"alien_eye_{dname}"]
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Coat Weight"].default_value = COAT["weight"]
        bsdf.inputs["Coat Roughness"].default_value = COAT["roughness"]
        restore_eye_image(mat, bsdf, dname, a.eye_images, ex)
        for side in ("L", "R"):
            ball = bpy.data.objects[f"eye_{dname}_ball_{side}"]
            r = max(v.co.length for v in ball.data.vertices)
            node = cj["nodes"]["eyes"][dname][side]
            for lid in ("upper", "lower"):
                lo = bpy.data.objects[f"eye_{dname}_lid_{lid}_{side}"]
                name = f"eye_{dname}_wet_{lid}_{side}"
                ob = wet_strip(name, lo, r, d[lid]["rho"], LID_BEAD[lid], lid == "upper", wet, lo.users_collection[0])
                node[f"wet_{lid}"] = name
                made.append((name, len(ob.data.polygons)))
            log(dname, side, "r", round(r, 5))
    log("wet strips", made)
    orm_png = sss_into_orm(kit, out) if a.sss_orm else None
    ex.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(ex / "alien_character.blend"))
    opts = dict(export_glb.options(False), export_image_format="AUTO", export_vertex_color="ACTIVE", export_tangents=True)
    if a.sss_orm:
        opts["export_extras"] = True  # alien_hue's SSS_MARKER
    res = bpy.ops.export_scene.gltf(filepath=str(ex / "alien_character.glb"), **opts)
    if res != {"FINISHED"}:
        raise SystemExit(f"export: {res}")
    check_images(ex / "alien_character.glb")
    if orm_png is not None:
        bad = E.sss_orm_problems((ex / "alien_character.glb").read_bytes(), "alien_hue", orm_png.read_bytes())
        if bad:
            raise SystemExit(f"the GLB's SSS route: {bad}")
        log("sss route ok: metallicRoughness and occlusion = orm_sss.png, metallicFactor 0, extras", E.SSS_MARKER)
    for f in kit.iterdir():
        if f.suffix == ".png":
            shutil.copy2(f, ex / f.name)
    cj["note_m4_eyes"] = (
        "art #196 M4: the eyes. Each lid has a wet line, eye_<design>_wet_<upper|lower>_<side> (material alien_wet; "
        "nodes.eyes.<design>.<side>.wet_upper/wet_lower), a child of its lid node with an identity transform: it turns "
        "with the lid. Godot: godot/alien/alien_wet.gdshader (alpha from the UV: u across the lid, faded at the corners, "
        "v from the ball's side 0 to the lid's edge 1; faded out as the lids close) and alien_eye.gdshader's M4 eye on "
        "alien_eye_<design> (an optical cornea with refraction and iris depth, the lids' contact shadow, the sclera's "
        "falloff, a view-space catch light). The eyeball materials carry a clear coat (KHR_materials_clearcoat) for "
        "plain glTF viewers; their 512 px texture is S9's.")
    if a.sss_orm:
        cj["note_m5_sss"] = (
            "art #196 M5: alien_hue's ORM (occlusionTexture R, metallicRoughnessTexture G) carries the subsurface mask "
            "in its B channel (white = thin: fingers, ears; the kit's 2K alien_skin_sss.png upscaled), with "
            "metallicFactor 0, so plain viewers stay non-metal; the material's glTF extras " + json.dumps(E.SSS_MARKER)
            + " mark it. godot/alien/alien.gd takes the textured skin (alien_hue.gdshader `textured`: the albedo, the "
            "ORM with that mask, the normal map on Body's UVMap, no COLOR_0 multiply) only for a material with it.")
    (ex / "character.json").write_text(json.dumps(cj, indent=1), encoding="utf-8", newline="\n")
    log("EXPORT", ex / "alien_character.glb")


if __name__ == "__main__":
    main()
