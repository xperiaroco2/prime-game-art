"""The M3b review (art #196): Meshy's retexture results on the alien kit's Body, beside the look target rf2 and the M2
look, in Blender (Eevee, AgX) under light D. Background Blender only, through the runner's helper:

  blender -b --factory-startup --python-exit-code 1 --python tools/blender/alien_retexture_review.py -- \
      --character <M2/export/alien_character.blend> --rf2 <rf2.png> --out <M3b/review> \
      --item <raw>/2026-10-19-alien-retexture/rt-rf2 [--item ...] [--body-ref <u1 front.png>] \
      [--images <S9/parts/export>] [--normal m2|meshy|none] [--m2-normal <M2/bake/normal.png>] [--tile 256]
  ... --make-fake <DIR>   writes a fake item (a UV checker as base colour, flat PBR maps, a generation.json shaped
                          like the client's) into DIR first and reviews it: the check that the textures land on UVMap

An item folder is a `meshy run` result: its generation.json lists the downloaded files with their result key
(`texture_urls.0.base_color`, `.roughness`, `.metallic`, `.normal`). The textures go on Body's `UVMap` (TEXCOORD_0,
which the retexture input sent with enable_original_uv): base colour (sRGB), roughness and metallic (non-colour), and
the normal map chosen by --normal: `m2` (default) our own detail bake, M2/bake/normal.png, as M3's recipe keeps it;
`meshy` the item's own; `none`. Nothing else of the kit changes (eyes, mouth, pose: the Idle clip's first frame).

Light D (docs/godot.md, "Light D"; look_presets.json `lights`): key, fill, back and rim as sun lamps from the same
directions (Godot's model space +Y up, front +Z, turned into Blender's: (x, y, z) -> (x, -z, y)), each at its Godot
energy times --light-scale (default 1: at pi, the first try, the M2 look washed out to near white under AgX), with the
same specular and shadow flags; a dim grey world. It approximates the Godot stage; it does not reproduce it.

Writes per shot and column `<shot>_<column>.png` (columns: m2, then each item's folder name) and `sheet.png`: one row per
shot (the face at three-quarters, 0.5 m; the face from the front, 0.5 m; the full body at 1.5 m), the first column the
reference (rf2 for the face rows, --body-ref or rf2 for the body row), then M2, then the items; and `sheet.json` with
the inputs and their sha256.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_detail_review as m2r  # noqa: E402  (look, render, load, sheet and the M2 skin)

# Light D in Godot's model space (docs/godot.md): at, energy, specular, shadow; all look at (0, 0.9, 0).
LIGHT_D = {"key": ((-2.0, 3.2, 3.0), 3.0, 0.6, True), "fill": ((3.0, 1.6, 2.0), 0.12, 0.0, False),
           "back": ((0.5, 2.5, -3.0), 0.30, 0.0, False), "rim": ((0.7, 1.6, -2.8), 3.0, 0.5, False)}
MAPS = ("base_color", "roughness", "metallic", "normal")


def args():
    p = argparse.ArgumentParser()
    p.add_argument("--character", required=True)
    p.add_argument("--rf2", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--item", action="append", default=[], help="a downloaded retexture item folder (repeatable)")
    p.add_argument("--make-fake", default="", help="write a fake item into this folder first and review it")
    p.add_argument("--body-ref", default="", help="the body row's reference image (default rf2)")
    p.add_argument("--images", default="", help="the folder of the eye textures (alien_parts.py's export/)")
    p.add_argument("--normal", choices=("m2", "meshy", "none"), default="m2")
    p.add_argument("--m2-normal", default="", help="default: <character>/../../bake/normal.png")
    p.add_argument("--tile", type=int, default=256)
    p.add_argument("--light-scale", type=float, default=1.0, help="Blender sun strength per unit of Godot energy")
    return p.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])


def godot_to_blender(v):
    x, y, z = v
    return Vector((x, -z, y))


def fit(path: Path, px: int):
    """An image letterboxed into a px square (the whole picture, unlike m2r.load's centre crop), as RGBA rows."""
    im = bpy.data.images.load(str(path))
    w, h = im.size
    s = px / max(w, h)
    nw, nh = max(1, round(w * s)), max(1, round(h * s))
    im.scale(nw, nh)
    a = np.array(im.pixels[:], dtype=np.float32).reshape(nh, nw, 4)
    out = np.empty((px, px, 4), dtype=np.float32)
    out[...] = a[0, 0]  # the image's own corner colour (its backdrop)
    y0, x0 = (px - nh) // 2, (px - nw) // 2
    out[y0:y0 + nh, x0:x0 + nw] = a
    return out


def light_d(sc, scale):
    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = 32
    try:
        sc.eevee.use_shadows = True
        sc.eevee.use_raytracing = True
    except AttributeError:
        pass
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "None"
    sc.render.film_transparent = False
    w = bpy.data.worlds.new("dim")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.20, 0.21, 0.23, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35
    sc.world = w
    target = godot_to_blender((0, 0.9, 0))
    for name, (at, energy, spec, shadow) in LIGHT_D.items():
        ld = bpy.data.lights.new(f"D_{name}", "SUN")
        ld.energy = energy * scale
        ld.specular_factor = spec
        ld.use_shadow = shadow
        ld.angle = math.radians(3.0)
        lo = bpy.data.objects.new(f"D_{name}", ld)
        sc.collection.objects.link(lo)
        pos = godot_to_blender(at)
        lo.location = pos
        lo.rotation_euler = (target - pos).to_track_quat("-Z", "Y").to_euler()
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    return cam


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def item_maps(folder: Path) -> dict[str, Path]:
    """The item's texture files by map, from its generation.json (`files`: name and result key)."""
    state = json.loads((folder / "generation.json").read_text(encoding="utf-8"))
    if state.get("status") != "done":
        raise SystemExit(f"{folder}: generation.json status is {state.get('status')!r}, not done")
    found = {}
    for f in state.get("files", []):
        head, _, tail = str(f.get("key", "")).rpartition(".")
        if head.startswith("texture_urls") and tail in MAPS:
            found.setdefault(tail, folder / f["name"])
    if "base_color" not in found:
        raise SystemExit(f"{folder}: no texture_urls.*.base_color among the downloaded files")
    return found


def make_fake(folder: Path, px: int = 1024) -> None:
    """A fake retexture item: an 8 x 8 UV checker (two teals, with a pale cross at each cell's centre so that a flip
    shows) as base colour, flat roughness 0.5, metallic 0 and a flat normal; a generation.json like the client's."""
    folder.mkdir(parents=True, exist_ok=True)
    y, x = np.mgrid[0:px, 0:px] / px
    cell = ((np.floor(x * 8) + np.floor(y * 8)) % 2)[..., None]
    rgb = np.where(cell > 0, [0.10, 0.45, 0.48], [0.20, 0.62, 0.60])
    fx, fy = (x * 8) % 1, (y * 8) % 1
    cross = ((np.abs(fx - 0.5) < 0.04) & (fy > 0.5)) | ((np.abs(fy - 0.5) < 0.04) & (fx > 0.5))  # an L: flips show
    rgb = np.where(cross[..., None], [0.92, 0.88, 0.80], rgb)
    images = {"base_color": rgb, "roughness": np.full((px, px, 3), 0.5), "metallic": np.zeros((px, px, 3)),
              "normal": np.broadcast_to([0.5, 0.5, 1.0], (px, px, 3))}
    files = []
    for name, arr in images.items():
        a = np.concatenate([arr, np.ones((px, px, 1))], axis=2).astype(np.float32)
        im = bpy.data.images.new(f"fake_{name}", px, px, alpha=False, float_buffer=False)
        if name != "base_color":
            im.colorspace_settings.name = "Non-Color"
        im.pixels.foreach_set(a.ravel())
        path = folder / f"retexture-texture_urls.0.{name}.png"
        im.filepath_raw = str(path)
        im.file_format = "PNG"
        im.save()
        files.append({"name": path.name, "stage": "retexture", "key": f"texture_urls.0.{name}",
                      "bytes": path.stat().st_size, "sha256": sha256(path)})
    state = {"batch": "fake", "item": folder.name, "kind": "retexture", "status": "done", "files": files,
             "note": "a fake item written by alien_retexture_review.py --make-fake (no Meshy call)"}
    (folder / "generation.json").write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8")


def textured_material(name: str, maps: dict[str, Path], normal: Path | None) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    uvm = nt.nodes.new("ShaderNodeUVMap")
    uvm.uv_map = "UVMap"

    def tex(path: Path, colour: bool):
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = bpy.data.images.load(str(path), check_existing=True)
        node.image.colorspace_settings.name = "sRGB" if colour else "Non-Color"
        nt.links.new(uvm.outputs["UV"], node.inputs["Vector"])
        return node

    nt.links.new(tex(maps["base_color"], True).outputs["Color"], bsdf.inputs["Base Color"])
    for key, socket in (("roughness", "Roughness"), ("metallic", "Metallic")):
        if key in maps:
            nt.links.new(tex(maps[key], False).outputs["Color"], bsdf.inputs[socket])
    if normal is not None:
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.space = "TANGENT"
        nm.uv_map = "UVMap"
        nt.links.new(tex(normal, False).outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def main():
    a = args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    items = [Path(p) for p in a.item]
    if a.make_fake:
        make_fake(Path(a.make_fake))
        items.append(Path(a.make_fake))
    if not items:
        raise SystemExit("no --item (or --make-fake) to review")
    maps = {it.name: item_maps(it) for it in items}
    m2_normal = Path(a.m2_normal) if a.m2_normal else Path(a.character).resolve().parent.parent / "bake" / "normal.png"
    if a.normal == "m2" and not m2_normal.is_file():
        raise SystemExit(f"no M2 normal map at {m2_normal} (set --m2-normal)")

    bpy.ops.wm.open_mainfile(filepath=str(Path(a.character).resolve()))
    sc = bpy.context.scene
    for o in [o for o in sc.objects if o.type == "LIGHT" or o.type == "CAMERA"]:
        bpy.data.objects.remove(o, do_unlink=True)
    body = bpy.data.objects["Body"]
    arm = body.find_armature()
    for im in bpy.data.images:  # the eye textures live beside the parts build (alien_parts.py's export/)
        if im.source == "FILE" and not im.has_data and a.images and (Path(a.images) / f"{im.name}.png").is_file():
            im.filepath = str(Path(a.images) / f"{im.name}.png")
            im.reload()
    for o in bpy.data.objects:
        if o.type == "MESH" and o is not body:
            o.hide_render = not o.name.startswith(("eye_bored_", "mouth_frog_rest"))
    idle = next((ac for ac in bpy.data.actions if ac.name.lower().split("|")[-1].startswith("idle")), None)
    if idle is not None:
        arm.animation_data_create()
        arm.animation_data.action = idle
        if hasattr(arm.animation_data, "action_slot") and idle.slots:
            arm.animation_data.action_slot = idle.slots[0]
        sc.frame_set(int(idle.frame_range[0]))
    bpy.context.view_layer.update()
    cam = light_d(sc, a.light_scale)

    m2_mat = body.data.materials[0]
    m2r.skin(body)  # the M2 look: the mask mix, half the AO, roughness 0.55, the M2 normal map
    mats = {"m2": m2_mat}
    for name, mp in maps.items():
        normal = {"m2": m2_normal, "meshy": mp.get("normal"), "none": None}[a.normal]
        mats[name] = textured_material(f"retexture_{name}", mp, normal)

    mw, pb = arm.matrix_world, arm.pose.bones
    head = mw @ pb["Head"].head
    eyes = [o for o in bpy.data.objects if o.name.startswith("eye_bored_ball_")]
    eye_c = sum((o.matrix_world.translation for o in eyes), Vector()) / max(len(eyes), 1) if eyes else head
    face_c = Vector((head.x, eye_c.y, eye_c.z - 0.02))
    a34 = math.radians(35)
    shots = {
        "face34": (face_c + Vector((0, 0, -0.06)), (math.sin(a34), -math.cos(a34), 0.08), 0.5, 30),
        "face_front": (face_c, (0, -1, 0.05), 0.5, 40),
        "body": (Vector((0, 0, 0.88)), (0.35, -1, 0.0), 1.5, 28),
    }
    T = a.tile * 2  # rendered at twice the tile, scaled down in the sheet
    for shot, (t, d, dist, lens) in shots.items():
        m2r.look(cam, t, d, dist, lens)
        for col, mat in mats.items():
            body.data.materials[0] = mat
            m2r.render(sc, out / f"{shot}_{col}.png", T)
        print(f"M3b shot {shot}", flush=True)
    body.data.materials[0] = m2_mat

    tile = a.tile
    rf2 = m2r.load(Path(a.rf2), tile)
    body_ref = fit(Path(a.body_ref), tile) if a.body_ref else rf2
    rows = []
    for shot in shots:
        ref = body_ref if shot == "body" else rf2
        rows.append([ref] + [m2r.load(out / f"{shot}_{col}.png", tile) for col in mats])
    m2r.sheet(rows, out / "sheet.png")
    record = {"character": str(Path(a.character).resolve()), "rf2": a.rf2, "rf2_sha256": sha256(a.rf2),
              "body_ref": a.body_ref, "normal": a.normal, "m2_normal": str(m2_normal) if a.normal == "m2" else "",
              "columns": ["reference"] + list(mats), "rows": list(shots),
              "light": f"D (sun lamps, Blender strength = Godot energy x {a.light_scale})",
              "items": {n: {k: {"file": str(p), "sha256": sha256(p)} for k, p in mp.items()} for n, mp in maps.items()}}
    (out / "sheet.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    print("M3b SHEET " + str(out / "sheet.png"), flush=True)


if __name__ == "__main__":
    main()
