"""M12, the red pout mouth mp1 (art #196), in headless Blender. Opens a kit's export/alien_character.blend (M10b's or
later) and writes a new kit into <out>/<export-name> (never over its input) with a third mouth design, "pout":

- six 3D pieces mouth_pout_<shape> (rest, M, small, A, E, O) measured off the mp1 sheet by alien_mouths (its own pixel
  classes and open-shape scales: alien_mouths.PALETTE, SHAPE_SCALE_DESIGN) and shaped by alien_lips_geom.LIP_SHAPE_POUT
  (--lips merges over it), on the Mouth socket like the frog and overbite pieces (the same fixed mount: the rest seam
  on the socket, the face's centre line); their own material alien_lip_pout (a glossy deep red, glTF extras
  PART_AO_MARKER), the inner cup and tongue the kit's alien_mouth_inner and alien_tongue. No flipbook shells;
- with --grid SPEC (JSON {"variants": {name: lip shape over LIP_SHAPE_POUT}, "pieces": ["rest", "A", ...]}) each
  variant's pieces as extra nodes lipvar_<name>_pout_<shape> (the grid's kit only);
- the pieces' own AO (COLOR_0) baked as alien_m6.bake_parts_ao does (each piece alone with the skin);
- the pout's skin contact in Body's seventh UV layer (alien_lips_geom.CONTACT_UV_MOUTH2: glTF TEXCOORD_6, u pout, v
  free; Godot CUSTOM2), alien_hue marked with CONTACT_MARKER_MOUTH2. The frog, overbite and eye channels, the Body's
  mesh, its skin AO and texture and every other part are not touched;
- export/alien_character.glb with alien_m6's options, its .blend, character.json (nodes.mouths.pout, `m12`,
  `note_m12`) and the kit's PNGs.

    tools/runner/blender.py run_script("alien_m12.py", ["--kit", <M10b/export>, "--out", <M12>])
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_eyes as AE  # noqa: E402
import alien_eyes_geom as E  # noqa: E402
import alien_lids_geom as LG  # noqa: E402
import alien_lips_geom as LP  # noqa: E402
import alien_m6 as M6  # noqa: E402
import alien_mouths as AM  # noqa: E402
import export_glb  # noqa: E402

DESIGN = "pout"
SHEET = ("D:/prime-art-raw/2026-10-20-alien-face-sheets-2/mp1/"
         "image_to_image-image_01a15906-86c2-76fb-a3e5-4de29c5c46e8_0.png")
# The pout's lips (sRGB, Blender's Principled stand-in; Godot's alien.gd LIP_LOOK_POUT is the release look): a deep
# red-coral, glossy (a low roughness and a clear coat), as the sheet's lips.
POUT_MAT = {"color": (0.68, 0.14, 0.14), "roughness": 0.32, "coat": 0.5, "coat_roughness": 0.15, "specular": 0.5}


def log(*a):
    print("M12", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--kit", required=True, help="the input kit's export folder (M10b's)")
    p.add_argument("--out", required=True, help="the M12 folder; the kit goes into <out>/<export-name>")
    p.add_argument("--export-name", default="export")
    p.add_argument("--sheet", default=SHEET, help="the mp1 talk-shape sheet (3 x 2 panels)")
    p.add_argument("--lips", default="", help="JSON merged over alien_lips_geom.LIP_SHAPE_POUT")
    p.add_argument("--grid", default="", help="a grid spec JSON file (variants and pieces)")
    p.add_argument("--orm-sss", default="", help="the composed ORM for the SSS route check")
    p.add_argument("--no-bake", action="store_true")
    return p.parse_args(argv)


def srgb_to_lin(c):
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def pout_material():
    """alien_lip_pout: the glossy red lips (a copy of the kit's alien_lip, its node layout kept)."""
    old = bpy.data.materials.get("alien_lip_pout")
    if old is not None:
        bpy.data.materials.remove(old)
    m = bpy.data.materials["alien_lip"].copy()
    m.name = "alien_lip_pout"
    for k in list(m.keys()):
        del m[k]
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*srgb_to_lin(POUT_MAT["color"]), 1.0)
    bsdf.inputs["Roughness"].default_value = POUT_MAT["roughness"]
    bsdf.inputs["Specular IOR Level"].default_value = POUT_MAT["specular"]
    for name, key in (("Coat Weight", "coat"), ("Coat Roughness", "coat_roughness")):
        if name in bsdf.inputs:
            bsdf.inputs[name].default_value = POUT_MAT[key]
    return m


def remove_old():
    for o in [o for o in bpy.data.objects if o.name.startswith((f"mouth_{DESIGN}_", f"lipvar_"))]:
        me = o.data
        bpy.data.objects.remove(o)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)


def attach(ob, mouth):
    ob.parent = mouth
    ob.matrix_parent_inverse.identity()
    ob.matrix_basis = Matrix.Identity(4)
    for p in ob.data.polygons:
        p.use_smooth = True


def pout_contact(body, rest_piece) -> dict:
    """The skin's contact field of the pout's rest lips (alien_m6.contact_field's rule: alien_lids_geom.contact of the
    rest-pose distance, smoothed) into Body's seventh UV layer CONTACT_UV_MOUTH2 (u pout, v 0; v stored flipped)."""
    name, (du, dv) = LP.CONTACT_UV_MOUTH2
    me = body.data
    if name in me.uv_layers:
        me.uv_layers.remove(me.uv_layers[name])
    if len(me.uv_layers) != 6:
        raise SystemExit(f"Body has {len(me.uv_layers)} UV layers, expected the six of alien_m6 (TEXCOORD_0..5)")
    mw = body.matrix_world
    omw = rest_piece.matrix_world
    verts = [omw @ v.co for v in rest_piece.data.vertices]
    tree = BVHTree.FromPolygons(verts, [list(p.vertices) for p in rest_piece.data.polygons])
    reach = LG.CONTACT["reach"]
    c = np.zeros(len(me.vertices))
    for i, v in enumerate(me.vertices):
        hit = tree.find_nearest(mw @ v.co, reach)
        if hit[0] is not None:
            c[i] = LG.contact(hit[3], reach)
    c = M6.smooth(me, c, LG.CONTACT["smooth"])
    lv = np.empty(len(me.loops), dtype=np.int64)
    me.loops.foreach_get("vertex_index", lv)
    layer = me.uv_layers.new(name=name)
    layer.data.foreach_set("uv", np.stack([c[lv], np.ones(len(lv))], 1).astype(np.float32).ravel())
    mat = bpy.data.materials["alien_hue"]
    for k, v in LP.CONTACT_MARKER_MOUTH2.items():
        mat[k] = v
    rep = {du: {"touched": int((c > 0.01).sum()), "full": int((c > 0.9).sum())}, "v": dv or None,
           "uv_layers": [u.name for u in me.uv_layers]}
    log("contact", json.dumps(rep))
    return rep


def main():
    a = args()
    kit, out = Path(a.kit), Path(a.out)
    ex = out / a.export_name
    if ex.resolve() == kit.resolve():
        raise SystemExit("the M12 kit must not overwrite its input")
    bpy.ops.wm.open_mainfile(filepath=str(kit / "alien_character.blend"))
    cj = json.loads((kit / "character.json").read_text(encoding="utf-8"))
    s6 = cj.get("report_s6", {})
    body = M6.rest_pose()
    bvh = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    mouth = bpy.data.objects["Mouth"]
    sock = mouth.matrix_world.copy()
    z_sock = sock.translation.z
    face_w = AM.face_width(bvh, z_sock)
    chin_z = s6.get("chin_z", AM.CHIN_Z)
    lips = LP.merged_pout(json.loads(a.lips) if a.lips else None)
    grid = json.loads(Path(a.grid).read_text(encoding="utf-8")) if a.grid else {"variants": {}, "pieces": []}
    rep = {"socket": [round(x, 5) for x in sock.translation], "face_w_at_socket_m": round(face_w, 4),
           "chin_z": chin_z, "sheet": a.sheet, "lips": lips, "pieces": {}}
    remove_old()
    coll = bpy.context.scene.collection
    mats = {"lip": pout_material(), "inner": bpy.data.materials["alien_mouth_inner"],
            "teeth": bpy.data.materials["alien_teeth"], "tongue": bpy.data.materials["alien_tongue"]}
    sheet = AM.load_rgb(a.sheet)
    ms, drep, frames = AM.shape_frames(sheet, face_w, z_sock, chin_z, DESIGN)
    rep["measure"] = {k: v for k, v in drep.items() if k != "shapes"}
    pieces, extra = [], []
    for k, shape in enumerate(AM.SHAPES):
        f = frames[shape]
        ob, meas, _st = AM.build_piece(bvh, ms[k], DESIGN, shape, f["world"], mats, coll, sock, lips=lips)
        attach(ob, mouth)
        meas.update({"verts": len(ob.data.vertices), "squeeze": round(f["squeeze"], 3), "sx": round(f["sx"], 3)})
        rep["pieces"][ob.name] = meas
        pieces.append(ob)
        if shape not in grid["pieces"]:
            continue
        for vname, vl in grid["variants"].items():
            vo, vm, _s = AM.build_piece(bvh, ms[k], DESIGN, shape, f["world"], mats, coll, sock,
                                        lips=LP.merged_pout(vl), name=f"lipvar_{vname}_{DESIGN}_{shape}")
            attach(vo, mouth)
            rep.setdefault("grid", {})[vo.name] = {kk: vm[kk] for kk in ("width_mm", "height_mm", "max_open_mm")}
            extra.append(vo)
    log("rings", json.dumps({k: v["ring_mm"] for k, v in rep["pieces"].items() if "ring_mm" in v}))  # M12b: w, h, hole w, h
    log("pieces", json.dumps({k: [v["width_mm"], v["height_mm"], v["max_open_mm"], v["form"], v["verts"]]
                              for k, v in rep["pieces"].items()}))
    if extra:
        log("grid", json.dumps(rep["grid"]))
    bpy.context.view_layer.update()
    rep["contact"] = pout_contact(body, bpy.data.objects[f"mouth_{DESIGN}_rest"])
    if not a.no_bake:
        rep["parts_ao"] = M6.bake_parts_ao(body, eyes=False, pieces=pieces + extra)
    for k2, v2 in M6.PART_AO_MARKER.items():
        mats["lip"][k2] = v2
    arm = body.find_armature()
    if arm is not None:  # back to POSE: in REST the exporter bakes every clip as the rest pose
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
    orm = Path(a.orm_sss) if a.orm_sss else kit.parent / "textures" / "orm_sss.png"
    if orm.is_file():
        bad = E.sss_orm_problems(glb.read_bytes(), "alien_hue", orm.read_bytes())
        if bad:
            raise SystemExit(f"the GLB's SSS route: {bad}")
        log("sss route ok")
    else:
        log("no", orm, "- the SSS route check skipped")
    for f in kit.iterdir():
        if f.suffix == ".png":
            shutil.copy2(f, ex / f.name)
    cj["nodes"].setdefault("mouths", {})[DESIGN] = {v: f"mouth_{DESIGN}_{v}" for v in AM.SHAPES}
    cj["m12"] = rep
    cj["note_m12"] = (
        "art #196 M12: a third mouth design, pout (the red pout lips of the mp1 sheet): mouth_pout_<shape> on the Mouth "
        "socket (the fixed mount), material alien_lip_pout (glossy deep red; COLOR_0 its baked AO, extras "
        "prime_part_ao), no flipbook shells; the skin's pout contact in Body's seventh UV layer contact_mouth2 (glTF "
        "TEXCOORD_6: u pout, v free; Godot CUSTOM2), alien_hue extras " + json.dumps(LP.CONTACT_MARKER_MOUTH2) + "." +
        (" The grid kit also has lipvar_<variant>_pout_<shape> nodes (m12.grid)." if extra else ""))
    (ex / "character.json").write_text(json.dumps(cj, indent=1), encoding="utf-8", newline="\n")
    log("EXPORT", glb, round(glb.stat().st_size / 1e6, 2), "MB")


if __name__ == "__main__":
    main()
