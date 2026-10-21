"""M12 and M13, the new mouth designs (art #196), in headless Blender: one run adds every new mouth onto a kit, so the
manager can chain eyes -> mouths. Opens a kit's export/alien_character.blend (M10b's or later; an M12 kit too) and
writes a new kit into <out>/<export-name> (never over its input) with the designs of --designs (default both):

- "pout" (M12, the red pout lips of the mp1 sheet) and "fangs" (M13, the mg2 sheet: thin, wide, soft coral lips with
  two lower fangs): six 3D pieces mouth_<design>_<shape> (rest, M, small, A, E, O) measured off the design's sheet by
  alien_mouths (its own pixel classes and open-shape scales) and shaped by alien_lips_geom.LIP_SHAPE_POUT /
  LIP_SHAPE_FANGS (--lips / --lips-fangs merge over them; the fangs' shape alien_fangs_geom.FANG, --fang), on the
  Mouth socket like the frog and overbite pieces (the same fixed mount). The pout's lips are alien_lip_pout (a glossy
  deep red), the fangs' the kit's alien_lip and their fangs alien_fang (ivory); the inner cup and tongue the kit's
  alien_mouth_inner and alien_tongue. No flipbook shells;
- with --grid SPEC (JSON {"design": "pout"|"fangs", "variants": {name: lip shape over the design's, for the fangs
  with an optional "fang" over FANG}, "pieces": ["rest", "A", ...]}) each variant's pieces as extra nodes
  lipvar_<name>_<design>_<shape> (the grid's kit only);
- the pieces' own AO (COLOR_0.r) baked as alien_m6.bake_parts_ao does (each piece alone with the skin; the new
  materials get PART_AO_MARKER only then), and (M13) the jaw weight in COLOR_0.a (jaw_weights: the lower lip, tongue
  and fangs 1, the upper lip 0, less toward the corners; M13b: in COLOR_0's alpha, the colour stays the grey AO) that
  godot/alien/alien_mouth_motion.gdshaderinc moves (the talk's bounce, pucker and jaw thrust) on every pout and fangs
  piece in the kit;
- the new designs' skin contact in Body's seventh UV layer (alien_lips_geom.CONTACT_UV_MOUTH2: glTF TEXCOORD_6, u
  pout, v fangs; Godot CUSTOM2), alien_hue marked with CONTACT_MARKER_MOUTH2. The frog, overbite and eye channels,
  the Body's mesh, its skin AO and texture and every other part are not touched;
- export/alien_character.glb with alien_m6's options, its .blend, character.json (nodes.mouths.<design>, `m12` the
  pout's report, `m13` the fangs', their notes) and the kit's PNGs.

    tools/runner/blender.py run_script("alien_m12.py", ["--kit", <M10b/export>, "--out", <M13>])
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
import alien_fangs_geom as FG  # noqa: E402
import alien_lids_geom as LG  # noqa: E402
import alien_lips_geom as LP  # noqa: E402
import alien_m6 as M6  # noqa: E402
import alien_mouths as AM  # noqa: E402
import export_glb  # noqa: E402

SHEET = ("D:/prime-art-raw/2026-10-20-alien-face-sheets-2/mp1/"
         "image_to_image-image_01a15906-86c2-76fb-a3e5-4de29c5c46e8_0.png")
SHEET_FANGS = ("D:/prime-art-raw/2026-10-20-alien-face-sheets-2/mg2/"
               "image_to_image-image_01a15908-9f6b-7219-a4df-4ca6606c5c8c_0.png")
# The new designs in build order; their contact channels are CONTACT_UV_MOUTH2's (u pout, v fangs).
DESIGNS = ("pout", "fangs")
# The pout's lips (sRGB, Blender's Principled stand-in; Godot's alien.gd LIP_LOOK_POUT is the release look): a deep
# red-coral, glossy (a low roughness and a clear coat), as the sheet's lips.
POUT_MAT = {"color": (0.68, 0.14, 0.14), "roughness": 0.32, "coat": 0.5, "coat_roughness": 0.15, "specular": 0.5}
# M13: the fangs (sRGB, Blender's stand-in; Godot's alien.gd FANG_LOOK is the release look): ivory, a soft satin.
FANG_MAT = {"color": (0.90, 0.82, 0.64), "roughness": 0.38, "coat": 0.25, "coat_roughness": 0.3, "specular": 0.45}
# M13: the jaw weight (COLOR_0.a since M13b) toward the mouth's corners: full to `from` of the lips' half width, `corner` at the
# corners (the corners stay on the face as the lower jaw moves); round an open ring, the lower half by the opening's
# centre height over `band` of its half height either side.
JAW = {"from": 0.45, "corner": 0.3, "band": 0.5}


def log(*a):
    print("M12", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--kit", required=True, help="the input kit's export folder (M10b's or later)")
    p.add_argument("--out", required=True, help="the output folder; the kit goes into <out>/<export-name>")
    p.add_argument("--export-name", default="export")
    p.add_argument("--designs", default=",".join(DESIGNS), help="the new designs to build, comma-separated")
    p.add_argument("--sheet", default=SHEET, help="the mp1 talk-shape sheet (3 x 2 panels)")
    p.add_argument("--sheet-fangs", default=SHEET_FANGS, help="the mg2 talk-shape sheet (3 x 2 panels)")
    p.add_argument("--lips", default="", help="JSON merged over alien_lips_geom.LIP_SHAPE_POUT")
    p.add_argument("--lips-fangs", default="", help="JSON merged over alien_lips_geom.LIP_SHAPE_FANGS")
    p.add_argument("--fang", default="", help="JSON merged over alien_fangs_geom.FANG")
    p.add_argument("--grid", default="", help="a grid spec JSON file (design, variants and pieces)")
    p.add_argument("--orm-sss", default="", help="the composed ORM for the SSS route check")
    p.add_argument("--no-bake", action="store_true")
    return p.parse_args(argv)


def srgb_to_lin(c):
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def lip_material(name, look):
    """A copy of the kit's alien_lip (its node layout kept, its extras dropped) in `look`'s colour and finish: the
    pout's alien_lip_pout (POUT_MAT), the fangs' alien_fang (FANG_MAT)."""
    old = bpy.data.materials.get(name)
    if old is not None:
        bpy.data.materials.remove(old)
    m = bpy.data.materials["alien_lip"].copy()
    m.name = name
    for k in list(m.keys()):
        del m[k]
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*srgb_to_lin(look["color"]), 1.0)
    bsdf.inputs["Roughness"].default_value = look["roughness"]
    bsdf.inputs["Specular IOR Level"].default_value = look["specular"]
    for name2, key in (("Coat Weight", "coat"), ("Coat Roughness", "coat_roughness")):
        if name2 in bsdf.inputs:
            bsdf.inputs[name2].default_value = look[key]
    return m


def remove_old(designs):
    for o in [o for o in bpy.data.objects if o.name.startswith(tuple(f"mouth_{d}_" for d in designs) + ("lipvar_",))]:
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


def jaw_weights(ob) -> dict:
    """M13: the jaw weight per vertex into COLOR_0's alpha (the `ao` attribute, made white if the AO was not baked;
    M13b, PR #248's review minor 4: the alpha, not g, so the colour stays the grey AO and a viewer that uses vertex
    colour as albedo does not tint the mouth; the pieces are opaque, so the alpha is no transparency): which part of
    the piece moves with the lower jaw (godot/alien/alien_mouth_motion.gdshaderinc). Per connected island: a closed
    piece's upper lip tube 0 and lower lip tube 1; round an open ring (lips and cup) a smooth step at the opening's
    centre height (JAW["band"] of its half height either side); the tongue and the fangs 1. Times JAW's falloff
    toward the mouth's corners (the corners stay put), per vertex on the fangs too (M13b, minor 6: a fang moved
    rigidly at its mean x while the lip under it moved at its own, so they could part under the bounce and thrust)."""
    me = ob.data
    n = len(me.vertices)
    mw = ob.matrix_world
    co = np.array([tuple(mw @ v.co) for v in me.vertices])
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for e in me.edges:
        a, b = find(e.vertices[0]), find(e.vertices[1])
        if a != b:
            parent[a] = b
    isl = np.array([find(i) for i in range(n)])
    vmat = np.full(n, "", dtype=object)
    for f in me.polygons:
        nm = ob.material_slots[f.material_index].material.name
        for v in f.vertices:
            vmat[v] = nm
    kind = {r: vmat[isl == r][0] for r in set(isl.tolist())}
    lipr = [r for r, k in kind.items() if k.startswith("alien_lip")]
    lipv = np.isin(isl, lipr)
    xc = float((co[lipv, 0].max() + co[lipv, 0].min()) / 2)
    hw = float((co[lipv, 0].max() - co[lipv, 0].min()) / 2) or 1.0

    def env(x):
        u = np.clip((np.abs(x - xc) / hw - JAW["from"]) / (1.0 - JAW["from"]), 0.0, 1.0)
        return 1.0 - (1.0 - JAW["corner"]) * u * u * (3 - 2 * u)
    cupr = [r for r, k in kind.items() if k == "alien_mouth_inner"]
    if len(lipr) == 1:  # an open ring: by the opening's centre height
        ref = np.isin(isl, cupr) if cupr else lipv
        zc = float(co[ref, 2].mean())
        h = max(1e-4, float(co[ref, 2].max() - co[ref, 2].min()) / 2)
        g = np.clip(0.5 + 0.5 * (zc - co[:, 2]) / (JAW["band"] * h), 0.0, 1.0)
        g = g * g * (3 - 2 * g)
    else:  # two tubes: the upper one stays, the lower one (and anything else) moves
        top = max(lipr, key=lambda r: co[isl == r, 2].mean())
        g = np.where(isl == top, 0.0, 1.0)
    g = g * env(co[:, 0])
    for r, k in kind.items():
        sel = isl == r
        if k in ("alien_tongue", "alien_fang"):
            g[sel] = env(co[sel, 0])
    if "ao" not in me.color_attributes:
        at = me.color_attributes.new("ao", "FLOAT_COLOR", "POINT")
        at.data.foreach_set("color", np.ones(n * 4, dtype=np.float32))
        me.color_attributes.active_color = at
        me.color_attributes.render_color_index = me.color_attributes.find("ao")
    col = np.empty(n * 4, dtype=np.float32)
    me.color_attributes["ao"].data.foreach_get("color", col)
    col = col.reshape(-1, 4)
    col[:, 1] = col[:, 0]  # an M13 kit's jaw weight in g back to the grey AO
    col[:, 3] = g
    me.color_attributes["ao"].data.foreach_set("color", col.astype(np.float32).ravel())
    return {"moving": round(float((g > 0.5).mean()), 3), "max": round(float(g.max()), 3)}


def contact_field(body, piece):
    """The skin's contact field of a design's rest lips (alien_m6.contact_field's rule: alien_lids_geom.contact of the
    rest-pose distance, smoothed); zeros without the piece."""
    me = body.data
    c = np.zeros(len(me.vertices))
    if piece is None:
        return c
    mw = body.matrix_world
    omw = piece.matrix_world
    verts = [omw @ v.co for v in piece.data.vertices]
    tree = BVHTree.FromPolygons(verts, [list(p.vertices) for p in piece.data.polygons])
    reach = LG.CONTACT["reach"]
    for i, v in enumerate(me.vertices):
        hit = tree.find_nearest(mw @ v.co, reach)
        if hit[0] is not None:
            c[i] = LG.contact(hit[3], reach)
    return M6.smooth(me, c, LG.CONTACT["smooth"])


def mouth2_contact(body) -> dict:
    """The new designs' contact into Body's seventh UV layer CONTACT_UV_MOUTH2 (u pout, v fangs; v stored flipped),
    each from its rest piece in the kit (the ones this run built, or the input kit's)."""
    name, chans = LP.CONTACT_UV_MOUTH2
    me = body.data
    if name in me.uv_layers:
        me.uv_layers.remove(me.uv_layers[name])
    if len(me.uv_layers) != 6:
        raise SystemExit(f"Body has {len(me.uv_layers)} UV layers, expected the six of alien_m6 (TEXCOORD_0..5)")
    fields = [contact_field(body, bpy.data.objects.get(f"mouth_{d}_rest")) for d in chans]
    lv = np.empty(len(me.loops), dtype=np.int64)
    me.loops.foreach_get("vertex_index", lv)
    layer = me.uv_layers.new(name=name)
    layer.data.foreach_set("uv", np.stack([fields[0][lv], 1.0 - fields[1][lv]], 1).astype(np.float32).ravel())
    mat = bpy.data.materials["alien_hue"]
    for k, v in LP.CONTACT_MARKER_MOUTH2.items():
        mat[k] = v
    rep = {d: {"touched": int((c > 0.01).sum()), "full": int((c > 0.9).sum())} for d, c in zip(chans, fields)}
    rep["uv_layers"] = [u.name for u in me.uv_layers]
    log("contact", json.dumps(rep))
    return rep


def build_design(design, a, bvh, face_w, z_sock, chin_z, sock, mouth, coll, grid, mats):
    """One design's six pieces (and the grid's variants when the grid is this design's): (report, pieces, extra)."""
    if design == "pout":
        merge, over, sheet_path = LP.merged_pout, a.lips, a.sheet
    else:
        merge, over, sheet_path = LP.merged_fangs, a.lips_fangs, a.sheet_fangs
    lips = merge(json.loads(over) if over else None)
    fang = FG.merged(json.loads(a.fang) if a.fang else None) if design == "fangs" else None
    rep = {"sheet": sheet_path, "lips": lips, "fang": fang, "pieces": {}}
    sheet = AM.load_rgb(sheet_path)
    ms, drep, frames = AM.shape_frames(sheet, face_w, z_sock, chin_z, design)
    rep["measure"] = {k: v for k, v in drep.items() if k != "shapes"}
    gd = grid if grid.get("design", "pout") == design else {"variants": {}, "pieces": []}
    pieces, extra = [], []
    for k, shape in enumerate(AM.SHAPES):
        f = frames[shape]
        ob, meas, _st = AM.build_piece(bvh, ms[k], design, shape, f["world"], mats, coll, sock, lips=lips, fang=fang)
        attach(ob, mouth)
        meas.update({"verts": len(ob.data.vertices), "squeeze": round(f["squeeze"], 3), "sx": round(f["sx"], 3)})
        rep["pieces"][ob.name] = meas
        pieces.append(ob)
        if shape not in gd["pieces"]:
            continue
        for vname, vl in gd["variants"].items():
            vl = dict(vl)
            vf = FG.merged(dict(fang or {}, **vl.pop("fang", {}))) if design == "fangs" else None
            vo, vm, _s = AM.build_piece(bvh, ms[k], design, shape, f["world"], mats, coll, sock,
                                        lips=merge(dict(json.loads(over) if over else {}, **vl)),
                                        name=f"lipvar_{vname}_{design}_{shape}", fang=vf)
            attach(vo, mouth)
            rep.setdefault("grid", {})[vo.name] = {kk: vm.get(kk) for kk in ("width_mm", "height_mm", "max_open_mm",
                                                                              "fangs_mm")}
            extra.append(vo)
    log(design, "rings", json.dumps({k: v["ring_mm"] for k, v in rep["pieces"].items() if "ring_mm" in v}))
    log(design, "pieces", json.dumps({k: [v["width_mm"], v["height_mm"], v["max_open_mm"], v["form"], v["verts"]]
                                       for k, v in rep["pieces"].items()}))
    if design == "fangs":
        log(design, "fangs", json.dumps({k: v.get("fangs_mm") for k, v in rep["pieces"].items()}))
    if extra:
        log(design, "grid", json.dumps(rep["grid"]))
    return rep, pieces, extra


def main():
    a = args()
    kit, out = Path(a.kit), Path(a.out)
    ex = out / a.export_name
    if ex.resolve() == kit.resolve():
        raise SystemExit("the new kit must not overwrite its input")
    designs = [d for d in a.designs.split(",") if d]
    if not designs or set(designs) - set(DESIGNS):
        raise SystemExit(f"--designs: some of {DESIGNS}")
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
    grid = json.loads(Path(a.grid).read_text(encoding="utf-8")) if a.grid else {"variants": {}, "pieces": []}
    remove_old(designs)
    coll = bpy.context.scene.collection
    base = {"inner": bpy.data.materials["alien_mouth_inner"], "teeth": bpy.data.materials["alien_teeth"],
            "tongue": bpy.data.materials["alien_tongue"]}
    mats = {}
    if "pout" in designs:
        mats["pout"] = dict(base, lip=lip_material("alien_lip_pout", POUT_MAT))
    if "fangs" in designs:
        mats["fangs"] = dict(base, lip=bpy.data.materials["alien_lip"], fang=lip_material("alien_fang", FANG_MAT))
    reps, pieces, extra = {}, [], []
    for d in designs:
        r, p, e = build_design(d, a, bvh, face_w, z_sock, chin_z, sock, mouth, coll, grid, mats[d])
        r.update({"socket": [round(x, 5) for x in sock.translation], "face_w_at_socket_m": round(face_w, 4),
                  "chin_z": chin_z})
        reps[d] = r
        pieces += p
        extra += e
    bpy.context.view_layer.update()
    contact = mouth2_contact(body)
    for d in designs:
        reps[d]["contact"] = contact
    if not a.no_bake:
        ao = M6.bake_parts_ao(body, eyes=False, pieces=pieces + extra)
        for d in designs:
            reps[d]["parts_ao"] = {k: v for k, v in ao.items() if f"_{d}_" in k}
            # the part's AO marker only on a baked kit (PR #246's review minor 7): with it alien.gd reads COLOR_0.r
            for key in ("lip", "fang"):
                if key in mats[d] and mats[d][key].name != "alien_lip":
                    for k2, v2 in M6.PART_AO_MARKER.items():
                        mats[d][key][k2] = v2
    # M13b (PR #248's review minor 3): every piece of every new design in the kit, not only this run's (with
    # --designs fangs on an M12 kit the pout's pieces kept a grey g, so its upper lip moved by its AO)
    moving = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith(
        tuple(f"mouth_{d}_" for d in DESIGNS) + ("lipvar_",))]
    jaw = {o.name: jaw_weights(o) for o in moving}
    log("jaw", json.dumps({k: v for k, v in jaw.items() if k.startswith("mouth_")}))
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
    marker = json.dumps(LP.CONTACT_MARKER_MOUTH2)
    for d in designs:
        cj["nodes"].setdefault("mouths", {})[d] = {v: f"mouth_{d}_{v}" for v in AM.SHAPES}
    if "pout" in reps:
        cj["m12"] = reps["pout"]
        cj["note_m12"] = (
            "art #196 M12: a third mouth design, pout (the red pout lips of the mp1 sheet): mouth_pout_<shape> on the "
            "Mouth socket (the fixed mount), material alien_lip_pout (glossy deep red; extras prime_part_ao when "
            "baked), COLOR_0 the baked AO (grey) and (M13b) its alpha the jaw weight; no flipbook shells; the skin's pout "
            "contact in Body's seventh UV layer contact_mouth2 (glTF TEXCOORD_6: u pout, v fangs; Godot CUSTOM2), "
            "alien_hue extras " + marker + "." +
            (" The grid kit also has lipvar_<variant>_pout_<shape> nodes (m12.grid)." if reps["pout"].get("grid")
             else ""))
    if "fangs" in reps:
        cj["m13"] = reps["fangs"]
        cj["note_m13"] = (
            "art #196 M13: a fourth mouth design, fangs (the mg2 sheet: thin, wide, soft coral lips with two lower "
            "fangs): mouth_fangs_<shape> on the Mouth socket, its lips the kit's alien_lip, its two fangs alien_fang "
            "(ivory; extras prime_part_ao when baked), COLOR_0 the baked AO (grey) and its alpha the jaw weight; no "
            "flipbook shells; the skin's fangs contact in TEXCOORD_6's v (Godot CUSTOM2.y), alien_hue extras "
            + marker + "." +
            (" The grid kit also has lipvar_<variant>_fangs_<shape> nodes (m13.grid)." if reps["fangs"].get("grid")
             else ""))
    (ex / "character.json").write_text(json.dumps(cj, indent=1), encoding="utf-8", newline="\n")
    log("EXPORT", glb, round(glb.stat().st_size / 1e6, 2), "MB")


if __name__ == "__main__":
    main()
