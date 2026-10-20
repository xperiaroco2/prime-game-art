"""M8, the lips shaped like lips (art #196), in headless Blender. Opens a kit's export/alien_character.blend (M6c's or
later) and writes a new kit into <out>/<export-name> (never over its input):

- every 3D mouth piece (mouth_<design>_<shape>, both designs, the six shapes) rebuilt by alien_mouths.build_piece from
  the same sheets (mf1, mo1) with an alien_lips_geom lip shape (--lips: JSON merged over LIP_SHAPE, or "m6c" for the
  old lips): the same objects, names, parent (the Mouth socket on the Head bone), materials and node layout; only
  their meshes change, so alien.gd's talk and blink logic is untouched. The flipbook shells, the eyes and the Body's
  mesh and skin AO are not touched;
- with --grid SPEC (JSON {"variants": {name: lip shape}, "pieces": ["frog_rest", ...]}) each variant's pieces as
  extra nodes lipvar_<name>_<design>_<shape> under the Mouth socket (the grid's kit only; M8's proof shows them one
  variant at a time);
- the mouth pieces' own AO (COLOR_0) rebaked as alien_m6.bake_parts_ao does (the lids' AO kept), and the Body's
  per-design contact channels recomputed from the new rest pieces (alien_m6.contact_field; the eye channels come out
  as before, the mouth channels follow the new lips);
- export/alien_character.glb with alien_m6's options, its .blend, character.json (`m8`, `note_m8`) and the kit's PNGs.

    tools/runner/blender.py run_script("alien_m8.py", ["--kit", <M6c/export>, "--out", <M8>, "--frog", <mf1 sheet>,
        "--overbite", <mo1 sheet>])
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
import alien_lips_geom as LP  # noqa: E402
import alien_m6 as M6  # noqa: E402
import alien_mouths as AM  # noqa: E402
import export_glb  # noqa: E402

DESIGNS = ("frog", "overbite")
SHEET_DEFAULT = {
    "frog": "D:/prime-art-raw/2026-10-19-alien-face-sheets/mf1/"
            "image_to_image-image_01a1543a-1b43-75c5-96ad-ab6f19272781_0.png",
    "overbite": "D:/prime-art-raw/2026-10-19-alien-face-sheets/mo1/"
                "image_to_image-image_01a1543b-80fb-7599-900a-ab28da7bd48f_0.png",
}


def log(*a):
    print("M8", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--kit", required=True, help="the input kit's export folder (M6c's)")
    p.add_argument("--out", required=True, help="the M8 folder; the kit goes into <out>/<export-name>")
    p.add_argument("--export-name", default="export")
    p.add_argument("--frog", default=SHEET_DEFAULT["frog"])
    p.add_argument("--overbite", default=SHEET_DEFAULT["overbite"])
    p.add_argument("--lips", default="", help="JSON merged over alien_lips_geom.LIP_SHAPE, or m6c")
    p.add_argument("--grid", default="", help="a grid spec JSON file (variants and pieces)")
    p.add_argument("--orm-sss", default="", help="the composed ORM for the SSS route check (default <kit>/../textures)")
    p.add_argument("--no-bake", action="store_true")
    return p.parse_args(argv)


def lip_shape(text: str) -> dict:
    if text == "m6c":
        return dict(LP.LIP_SHAPE_M6C)
    return LP.merged(json.loads(text) if text else None)


def swap_mesh(ob, new_ob) -> None:
    """ob keeps its name, parent, transform and custom properties; it takes new_ob's mesh (same local frame)."""
    old = ob.data
    name = old.name
    ob.data = new_ob.data
    bpy.data.objects.remove(new_ob)
    bpy.data.meshes.remove(old)
    ob.data.name = name


def local_diff(ob, verts_before) -> float | None:
    """The largest vertex move (m) when the vertex count is unchanged, else None."""
    if len(ob.data.vertices) != len(verts_before):
        return None
    co = np.empty(len(ob.data.vertices) * 3)
    ob.data.vertices.foreach_get("co", co)
    return float(np.abs(co.reshape(-1, 3) - verts_before).max())


def main():
    a = args()
    kit, out = Path(a.kit), Path(a.out)
    ex = out / a.export_name
    if ex.resolve() == kit.resolve():
        raise SystemExit("the M8 kit must not overwrite its input")
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
    rep = {"socket": [round(x, 5) for x in sock.translation], "face_w_at_socket_m": round(face_w, 4),
           "chin_z": chin_z, "s6_socket": s6.get("socket"), "s6_face_w": s6.get("face_w_at_socket_m")}
    lips = lip_shape(a.lips)
    rep["lips"] = lips
    grid = json.loads(Path(a.grid).read_text(encoding="utf-8")) if a.grid else {"variants": {}, "pieces": []}
    coll = bpy.context.scene.collection
    mats = {"lip": bpy.data.materials["alien_lip"], "inner": bpy.data.materials["alien_mouth_inner"],
            "teeth": bpy.data.materials["alien_teeth"], "tongue": bpy.data.materials["alien_tongue"]}
    extra = []
    rep["pieces"] = {}
    for design in DESIGNS:
        sheet = AM.load_rgb(getattr(a, design))
        ms, _drep, frames = AM.shape_frames(sheet, face_w, z_sock, chin_z)
        for k, shape in enumerate(AM.SHAPES):
            f = frames[shape]
            ob = bpy.data.objects[f"mouth_{design}_{shape}"]
            if ob.parent is not mouth or (ob.matrix_world.translation - sock.translation).length > 1e-6:
                raise SystemExit(f"{ob.name}: not on the Mouth socket")
            co = np.empty(len(ob.data.vertices) * 3)
            ob.data.vertices.foreach_get("co", co)
            before = co.reshape(-1, 3)
            new, meas, _st = AM.build_piece(bvh, ms[k], design, shape, f["world"], mats, coll, sock, lips=lips,
                                            name=f"_m8_{design}_{shape}")
            swap_mesh(ob, new)
            moved = local_diff(ob, before)
            meas["verts"] = len(ob.data.vertices)
            meas["moved_max_mm"] = None if moved is None else round(moved * 1000, 3)
            rep["pieces"][ob.name] = meas
            for vname, vlips in grid["variants"].items():
                if f"{design}_{shape}" not in grid["pieces"]:
                    continue
                vo, _m, _s = AM.build_piece(bvh, ms[k], design, shape, f["world"], mats, coll, sock,
                                            lips=lip_shape(json.dumps(vlips)) if vlips != "m6c" else lip_shape("m6c"),
                                            name=f"lipvar_{vname}_{design}_{shape}")
                vo.parent = mouth
                vo.matrix_parent_inverse.identity()
                vo.matrix_basis = Matrix.Identity(4)
                extra.append(vo)
    for o in bpy.data.objects:
        if o.name.startswith(("mouth_", "lipvar_")):
            for p in o.data.polygons:
                p.use_smooth = True
    log("pieces", json.dumps({k: [v.get("verts"), v.get("moved_max_mm"), v.get("form")]
                              for k, v in rep["pieces"].items()}))
    bpy.context.view_layer.update()
    rep["contact"] = M6.contact_field(body)
    if not a.no_bake:
        rep["parts_ao"] = M6.bake_parts_ao(body, eyes=False, pieces=M6.mouth_pieces() + extra)
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
    cj["m8"] = rep
    cj["note_m8"] = (
        "art #196 M8: the 3D mouth pieces rebuilt with alien_lips_geom's lip shape (m8.lips): each lip thin at its "
        "corners and fullest in the middle, the upper lip thinner with a soft bow, the lower a fuller cushion, the "
        "swell toward the lip line, the corners tucked; the same nodes, materials and socket; their AO (COLOR_0) "
        "rebaked and Body's mouth contact channels (TEXCOORD_5) recomputed." +
        (" The grid kit also has lipvar_<variant>_<design>_<shape> nodes (m8.grid)." if extra else ""))
    if extra:
        rep["grid"] = grid
    (ex / "character.json").write_text(json.dumps(cj, indent=1), encoding="utf-8", newline="\n")
    log("EXPORT", glb, round(glb.stat().st_size / 1e6, 2), "MB")


if __name__ == "__main__":
    main()
