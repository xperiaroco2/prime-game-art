"""M6, the eyes and lips sized, rounded and integrated (art #196), in headless Blender. Opens a kit's
export/alien_character.blend (M5's: M3c's skin, M4's eyes, the SSS mask in the ORM's B) and writes a new kit into
<out>/export (never over its input):

- the skin's texture set from --skin-tex (a folder with albedo.png, orm.png and the 2K sss.png, as M3c's and M2b's
  `textures/`) and optionally --skin-normal (the 4K tangent-space normal map); the ORM's B gets the SSS mask again
  (alien_eyes.sss_into_orm), so the next step can swap in another composed set with one argument;
- the eye units: every lid shell rebuilt with rounded corners (alien_parts_geom.lid_shell `corner`,
  alien_lids_geom.CORNER or --corner JSON merged over it) and the ball, lids and wet strips scaled together about the
  socket (the ball's centre) by --eye-scale (alien_lids_geom.EYE_SCALE); the wet strips are rebuilt on the new rims;
- the lids' and lips' own occlusion: Cycles bakes AO into a grey colour attribute `ao` (glTF COLOR_0) on every lid
  shell and 3D mouth piece, each design and piece alone with the skin (the lids at rest), so the folds (the lip line,
  the mouth's corners, the rim's underside, where a part meets the skin) are deeper; godot/alien/alien_lip.gdshader
  turns it into a deeper, warmer coral (plain viewers multiply it into the base colour);
- the skin's contact field: per Body vertex and per design the distance to the nearest rest lid or rest lip
  surface as alien_lids_geom.contact(), smoothed, one channel per design (M6c) in a fifth and sixth UV layer
  (alien_lids_geom.CONTACT_UVS: glTF TEXCOORD_4 = (bored, manic), TEXCOORD_5 = (frog, overbite); Godot CUSTOM1);
  alien_hue gets the custom property CONTACT_MARKER (glTF extras), so alien.gd turns the textured skin's contact
  shade on only for such a kit and picks the shown designs' channels;
- export/alien_character.glb (M5's options with extras), its .blend, character.json (`note_m6`, `m6` settings), the
  PNGs beside the kit's GLB; the image check and the SSS route check as M4 and M5.

Runs in background Blender through the runner, never by hand and never in a window:
tools/runner/blender.py's run_script("alien_m6.py", ["--kit", <M5/export>, "--out", <M6>, "--skin-tex",
<M3c/textures>, "--skin-normal", <M3a/bake_cage_r2/normal.png>]).
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_eyes as AE  # noqa: E402
import alien_eyes_geom as E  # noqa: E402
import alien_lids_geom as LG  # noqa: E402
import alien_parts_geom as G  # noqa: E402
import alien_socket  # noqa: E402
import export_glb  # noqa: E402
from alien_parts import EYES, LID_BEAD  # noqa: E402

CONTACT_MARKER = {"prime_contact": "custom1_designs"}  # M6c; M6's kits: "custom1_x"
PART_AO_MARKER = {"prime_part_ao": "color0_r"}  # on alien_lip (the lips and lid domes) once the parts' AO is baked
PART_AO = {"distance": 0.02, "samples": 64, "floor": 0.3, "smooth": 1}
LID_SEG_T = 32  # S7: 20 rows across the lid; the rounded corners need more near the poles
DESIGNS_MOUTH = ("frog", "overbite")
VISEMES = ("rest", "M", "small", "A", "E", "O")


def log(*a):
    print("M6", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--kit", required=True, help="the input kit's export folder (M5's)")
    p.add_argument("--out", required=True, help="the M6 folder; the kit goes into <out>/<export-name>")
    p.add_argument("--export-name", default="export")
    p.add_argument("--skin-tex", required=True, help="a texture set folder: albedo.png, orm.png, sss.png (2K)")
    p.add_argument("--skin-normal", default="", help="the skin's normal map (4K); default: the kit's")
    p.add_argument("--eye-scale", type=float, default=LG.EYE_SCALE)
    p.add_argument("--eye-sink", type=float, default=LG.EYE_SINK, help="m back into the head along the socket axis")
    p.add_argument("--corner", default="", help="JSON merged over alien_lids_geom.CORNER")
    p.add_argument("--lids", default="", help="M9b: JSON over alien_lids_geom.LIDS (the slim shells' thin, rim); "
                   "the default on a mounted kit is LIDS, on an older kit S9's shells")
    p.add_argument("--no-bake", action="store_true", help="skip the parts' AO bake (a quick geometry check)")
    p.add_argument("--socket", default="", help="M9: JSON over alien_lids_geom.SOCKET, the eye mount applied here "
                   "(a variant grid on a kit without one; a chain-built kit carries Body['prime_socket'] already)")
    return p.parse_args(argv)


def skin_nodes():
    mat = bpy.data.materials["alien_hue"]
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    alb = next(lk.from_node for lk in bsdf.inputs["Base Color"].links)
    sep = next(lk.from_node for lk in bsdf.inputs["Roughness"].links if lk.from_node.type == "SEPARATE_COLOR")
    orm = next(lk.from_node for lk in sep.inputs["Color"].links if lk.from_node.type == "TEX_IMAGE")
    nm = next(lk.from_node for lk in bsdf.inputs["Normal"].links)
    nrm = next(lk.from_node for lk in nm.inputs["Color"].links if lk.from_node.type == "TEX_IMAGE")
    if alb.type != "TEX_IMAGE":
        raise SystemExit(f"alien_hue's base colour is not an image node: {alb.type}")
    return alb, orm, nrm


def load_image(path: Path, name: str, colour: bool):
    if not path.is_file():
        raise SystemExit(f"no image {path}")
    img = bpy.data.images.load(str(path), check_existing=False)
    img.name = name
    img.colorspace_settings.name = "sRGB" if colour else "Non-Color"
    return img


def swap_skin(a, out: Path) -> dict:
    """The skin's texture set from --skin-tex (and --skin-normal), the SSS mask into the new ORM's B."""
    tex = Path(a.skin_tex)
    alb, orm, nrm = skin_nodes()
    before = {"albedo": alb.image.filepath, "orm": orm.image.filepath, "normal": nrm.image.filepath}
    alb.image = load_image(tex / "albedo.png", "alien_skin_albedo", True)
    orm.image = load_image(tex / "orm.png", "alien_skin_orm", False)
    if a.skin_normal:
        nrm.image = load_image(Path(a.skin_normal), "alien_skin_normal", False)
    sss = tex / "sss.png"
    if not sss.is_file():
        raise SystemExit(f"no SSS mask {sss}")
    tmp = out / "textures" / "_sss_in"
    tmp.mkdir(parents=True, exist_ok=True)
    shutil.copy2(sss, tmp / "alien_skin_sss.png")
    orm_png = AE.sss_into_orm(tmp, out)
    shutil.copy2(sss, out / "textures" / "alien_skin_sss.png")
    shutil.rmtree(tmp)
    rep = {"skin_tex": tex.as_posix(), "skin_normal": a.skin_normal or nrm.image.filepath, "before": before,
           "orm_sss": orm_png.as_posix()}
    log("skin", json.dumps(rep))
    return rep


def rebuild_eyes(k: float, corner: dict, sink: float = 0.0, lids: dict | None = None) -> dict:
    """Every lid shell rebuilt with the rounded corners at k times the ball's radius (M9b: slimmed by `lids`,
    alien_lids_geom.slim; None builds S9's shells), the ball's mesh scaled by k about
    its centre (the socket), the wet strips rebuilt."""
    wet = bpy.data.materials["alien_wet"]
    lip = bpy.data.materials["alien_lip"]
    rep = {}
    for dname, d in EYES.items():
        for side in ("L", "R"):
            ball = bpy.data.objects[f"eye_{dname}_ball_{side}"]
            n = len(ball.data.vertices)
            co = np.empty(n * 3)
            ball.data.vertices.foreach_get("co", co)
            co = co.reshape(-1, 3)
            off = float(np.linalg.norm(co.mean(0)))
            r = float(np.linalg.norm(co, axis=1).max())
            if off > 0.02 * r:
                raise SystemExit(f"{ball.name}: its mesh is not centred on its origin ({off:.5f} m)")
            ball.data.vertices.foreach_set("co", (co * k).ravel())
            ball.data.update()
            for lid in ("upper", "lower"):
                lo = bpy.data.objects[f"eye_{dname}_lid_{lid}_{side}"]
                if (lo.matrix_world.translation - ball.matrix_world.translation).length > 1e-5:
                    raise SystemExit(f"{lo.name}: not hinged at the ball's centre")
                rho, bead = LG.slim(d[lid]["rho"], LID_BEAD[lid], lids or LG.LIDS_S9)
                tmp = G.lid_shell(lo.name + "_m6", r * k, rho[0], rho[1], lid == "upper", lip,
                                  lo.users_collection[0], seg_t=LID_SEG_T, seg_p=18, rim_seg=8, bead=bead,
                                  corner=corner)
                old = lo.data
                name = old.name
                new = tmp.data
                lo.data = new
                bpy.data.objects.remove(tmp)
                bpy.data.meshes.remove(old)
                new.name = name
                for ch in list(lo.children):
                    if ch.name.startswith(f"eye_{dname}_wet_"):
                        me = ch.data
                        bpy.data.objects.remove(ch)
                        bpy.data.meshes.remove(me)
                AE.wet_strip(f"eye_{dname}_wet_{lid}_{side}", lo, r * k, rho, bead, lid == "upper",
                             wet, lo.users_collection[0], corner=corner)
            if sink:  # back into the head along the socket's axis (local +Y; the eye looks down -Y), so the
                # smaller domes still meet the socket's skin (at 93 % without it the socket's rim showed as a dark gap)
                sock = bpy.data.objects[f"Eye_{side}"]
                back = (sock.matrix_world.to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized() * sink
                for o in [ball] + [bpy.data.objects[f"eye_{dname}_lid_{lid}_{side}"] for lid in ("upper", "lower")]:
                    mw = o.matrix_world.copy()
                    mw.translation += back
                    o.matrix_world = mw
            up_rho, up_bead = LG.slim(d["upper"]["rho"], LID_BEAD["upper"], lids or LG.LIDS_S9)
            rep[f"{dname}_{side}"] = {"r_before": round(r, 5), "r": round(r * k, 5), "sink_m": sink,
                                      "lids": lids or LG.LIDS_S9,
                                      "overhang_upper_r": round(LG.corner_overhang(
                                          up_rho[1], up_bead, corner), 4)}
    log("eyes", json.dumps(rep))
    return rep


def mouth_pieces():
    return [bpy.data.objects[f"mouth_{d}_{v}"] for d in DESIGNS_MOUTH for v in VISEMES
            if f"mouth_{d}_{v}" in bpy.data.objects]


def rest_pose():
    body = bpy.data.objects["Body"]
    arm = body.find_armature()
    if arm is not None:
        arm.data.pose_position = "REST"
    bpy.context.view_layer.update()  # the lids are at rest in the kit (alien_parts.py placed them so)
    return body


def bake_parts_ao(body, eyes: bool = True, pieces=None) -> dict:
    """AO into a grey colour attribute `ao` on every lid shell and 3D mouth piece: per eye design its four lids at
    once, per mouth piece the piece alone, each with the skin (and the default other parts hidden). M8: eyes=False
    leaves the lids' AO as it is; pieces (objects) replaces the twelve mouth pieces (M8's grid variants too)."""
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = PART_AO["samples"]
    if sc.world is None:
        sc.world = bpy.data.worlds.new("w")
    sc.world.light_settings.distance = PART_AO["distance"]
    groups = [([bpy.data.objects[f"eye_{d}_lid_{lid}_{s}"] for lid in ("upper", "lower") for s in ("L", "R")],
               {f"eye_{d}_ball_{s}" for s in ("L", "R")}) for d in EYES] if eyes else []  # the balls occlude too
    groups += [([o], set()) for o in (mouth_pieces() if pieces is None else pieces)]
    hide0 = {o.name: o.hide_render for o in bpy.data.objects}
    rep = {}
    for grp, also in groups:
        names = {o.name for o in grp} | also
        for o in bpy.data.objects:
            if o.type == "MESH":
                o.hide_render = not (o is body or o.name in names)
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        for o in grp:
            me = o.data
            if "ao" in me.color_attributes:
                me.color_attributes.remove(me.color_attributes["ao"])
            at = me.color_attributes.new("ao", "FLOAT_COLOR", "POINT")
            me.color_attributes.active_color = at
            me.color_attributes.render_color_index = me.color_attributes.find("ao")
            o.select_set(True)
        bpy.context.view_layer.objects.active = grp[0]
        res = bpy.ops.object.bake(type="AO", target="VERTEX_COLORS")
        if res != {"FINISHED"}:
            raise SystemExit(f"bake {sorted(names)}: {res}")
        for o in grp:
            me = o.data
            n = len(me.vertices)
            col = np.empty(n * 4, dtype=np.float32)
            me.color_attributes["ao"].data.foreach_get("color", col)
            v = PART_AO["floor"] + (1 - PART_AO["floor"]) * col.reshape(-1, 4)[:, 0].astype(np.float64)
            v = smooth(me, v, PART_AO["smooth"])
            me.color_attributes["ao"].data.foreach_set("color", np.stack([v, v, v, np.ones(n)], 1).astype(np.float32).ravel())
            rep[o.name] = [round(float(v.min()), 3), round(float(v.mean()), 3)]
    for o in bpy.data.objects:
        if o.name in hide0:
            o.hide_render = hide0[o.name]
    lip = bpy.data.materials["alien_lip"]  # godot/alien/alien.gd takes LIP_LOOK only with this marker
    for k2, v2 in PART_AO_MARKER.items():
        lip[k2] = v2
    log("parts ao (min, mean)", json.dumps(rep))
    return rep


def smooth(me, v, passes: int):
    n = len(me.vertices)
    ed = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get("vertices", ed)
    ed = ed.reshape(-1, 2)
    deg = np.bincount(ed.ravel(), minlength=n).astype(float)
    deg[deg == 0] = 1
    for _ in range(passes):
        s = np.zeros(n)
        np.add.at(s, ed[:, 0], v[ed[:, 1]])
        np.add.at(s, ed[:, 1], v[ed[:, 0]])
        v = 0.5 * v + 0.5 * s / deg
    return v


def contact_field(body) -> dict:
    """The skin's contact field, one channel per design (M6c): per Body vertex alien_lids_geom.contact() of its
    rest-pose distance to the nearest rest lid of each eye design and the rest lips of each mouth design, in the UV
    layers alien_lids_geom.CONTACT_UVS (Body's fifth and sixth: glTF TEXCOORD_4 = (bored, manic), TEXCOORD_5 = (frog,
    overbite); Godot CUSTOM1). The glTF exporter writes 1 - v, so v is stored flipped here (as alien_ao.py's rest
    coordinates)."""
    groups = {d: [bpy.data.objects[f"eye_{d}_lid_{lid}_{s}"] for lid in ("upper", "lower") for s in ("L", "R")]
              for d in EYES}
    groups.update({d: [bpy.data.objects[f"mouth_{d}_rest"]] for d in DESIGNS_MOUTH})
    me = body.data
    mw = body.matrix_world
    reach = LG.CONTACT["reach"]
    n = len(me.vertices)
    co = [mw @ v.co for v in me.vertices]
    fields = {}
    for d, parts in groups.items():
        verts, polys = [], []
        for o in parts:
            omw = o.matrix_world
            base = len(verts)
            verts += [omw @ v.co for v in o.data.vertices]
            polys += [[base + i for i in p.vertices] for p in o.data.polygons]
        tree = BVHTree.FromPolygons(verts, polys)
        c = np.zeros(n)
        for i, p in enumerate(co):
            hit = tree.find_nearest(p, reach)
            if hit[0] is not None:
                c[i] = LG.contact(hit[3], reach)
        fields[d] = smooth(me, c, LG.CONTACT["smooth"])
    for name in LG.CONTACT_UVS:
        if name in me.uv_layers:
            me.uv_layers.remove(me.uv_layers[name])
    if len(me.uv_layers) != 4:
        raise SystemExit(f"Body has {len(me.uv_layers)} UV layers, expected UVMap, masks, rest_xy, rest_zn")
    lv = np.empty(len(me.loops), dtype=np.int64)
    me.loops.foreach_get("vertex_index", lv)
    for name, (du, dv) in LG.CONTACT_UVS.items():
        layer = me.uv_layers.new(name=name)
        layer.data.foreach_set("uv", np.stack([fields[du][lv], 1.0 - fields[dv][lv]], 1).astype(np.float32).ravel())
    mat = bpy.data.materials["alien_hue"]
    for k2, v2 in CONTACT_MARKER.items():
        mat[k2] = v2
    rep = {d: {"touched": int((c > 0.01).sum()), "full": int((c > 0.9).sum())} for d, c in fields.items()}
    rep["uv_layers"] = [u.name for u in me.uv_layers]
    log("contact", json.dumps(rep))
    return rep


def main():
    a = args()
    kit, out = Path(a.kit), Path(a.out)
    ex = out / a.export_name
    if ex.resolve() == kit.resolve():
        raise SystemExit("the M6 kit must not overwrite its input")
    corner = dict(LG.CORNER, **(json.loads(a.corner) if a.corner else {}))
    bpy.ops.wm.open_mainfile(filepath=str(kit / "alien_character.blend"))
    cj = json.loads((kit / "character.json").read_text(encoding="utf-8"))
    # the composed ORM (with the SSS mask) of the default build goes to <out>/textures, another's to <out>/skin_<name>
    skin_root = out if a.export_name == "export" else out / f"skin_{a.export_name}"
    rep = {"eye_scale": a.eye_scale, "eye_sink": a.eye_sink, "corner": corner, "skin": swap_skin(a, skin_root)}
    body = rest_pose()
    k, sink = a.eye_scale, a.eye_sink
    if a.socket:  # M9's grid: the mount on this kit (refused if it has one)
        rep["socket"] = alien_socket.apply(json.loads(a.socket))
    if alien_socket.MARKER in body.keys():  # M9: the mount sized and placed the eyes; rebuild the lids at that size
        k, sink = 1.0, 0.0
        rep["socket_mount"] = json.loads(body[alien_socket.MARKER])
    # M9b: the slim shells on the mount (an unmounted kit keeps S9's shells unless --lids asks)
    lids = LG.set_lids(json.loads(a.lids)) if a.lids else (LG.LIDS if "socket_mount" in rep else None)
    rep["lids"] = lids or LG.LIDS_S9
    rep["eye_scale"], rep["eye_sink"] = k, sink
    rep["eyes"] = rebuild_eyes(k, corner, sink, lids)
    bpy.context.view_layer.update()
    rep["contact"] = contact_field(body)
    if not a.no_bake:
        rep["parts_ao"] = bake_parts_ao(body)
    arm = body.find_armature()
    if arm is not None:  # back to POSE: in REST the exporter bakes every clip as the rest pose (a T-pose)
        arm.data.pose_position = "POSE"
    bpy.context.view_layer.update()
    ex.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(ex / "alien_character.blend"))
    opts = dict(export_glb.options(False), export_image_format="AUTO", export_vertex_color="ACTIVE",
                export_tangents=True, export_extras=True)
    res = bpy.ops.export_scene.gltf(filepath=str(ex / "alien_character.glb"), **opts)
    if res != {"FINISHED"}:
        raise SystemExit(f"export: {res}")
    glb = ex / "alien_character.glb"
    AE.check_images(glb)
    bad = E.sss_orm_problems(glb.read_bytes(), "alien_hue", Path(rep["skin"]["orm_sss"]).read_bytes())
    if bad:
        raise SystemExit(f"the GLB's SSS route: {bad}")
    log("sss route ok")
    for f in kit.iterdir():
        if f.suffix == ".png" and f.name != "alien_skin_sss.png":
            shutil.copy2(f, ex / f.name)
    shutil.copy2(skin_root / "textures" / "alien_skin_sss.png", ex / "alien_skin_sss.png")
    cj["m6"] = rep
    cj["note_m6"] = (
        "art #196 M6: the eye units scaled by m6.eye_scale about their sockets (ball, lids and wet strips), the lid "
        "shells' corners rounded (m6.corner: the rolled rim tapers toward the hinge poles, the edges bend toward each "
        "other), the lid shells and 3D mouth pieces carry their own baked AO (COLOR_0, grey; "
        "godot/alien/alien_lip.gdshader deepens the coral there), and Body carries the skin's contact field near the "
        "rest lids and lips, one channel per design, in a fifth and sixth UV layer (glTF TEXCOORD_4 = bored, manic; "
        "TEXCOORD_5 = frog, overbite; Godot CUSTOM1.xyzw), marked by alien_hue's "
        "extras " + json.dumps(CONTACT_MARKER) + " (alien_hue.gdshader's contact shade on the textured skin).")
    (ex / "character.json").write_text(json.dumps(cj, indent=1), encoding="utf-8", newline="\n")
    log("EXPORT", glb, round(glb.stat().st_size / 1e6, 2), "MB")


if __name__ == "__main__":
    main()
