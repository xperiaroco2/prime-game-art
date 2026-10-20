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
import alien_thumb  # noqa: E402
import export_glb  # noqa: E402
from alien_parts import EYES, LID_BEAD  # noqa: E402

CONTACT_MARKER = {"prime_contact": "custom1_designs"}  # M6c; M6's kits: "custom1_x"
PART_AO_MARKER = {"prime_part_ao": "color0_r"}  # on alien_lip (the lips and lid domes) once the parts' AO is baked
PART_AO = {"distance": 0.02, "samples": 64, "floor": 0.3, "smooth": 1}
# M10 (PR #243's review minor 1): alien_lip's custom property (glTF extras) with the lid setting and each design's rim
# reaches beyond the lid edges ({"lids": {...}, "reach_deg": {design: [upper, lower]}}, JSON); alien.gd takes the
# reaches from it, an older kit without it keeps S9's (EYE_LOOK)
LIDS_MARKER = "prime_lids"
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
    p.add_argument("--thumb", choices=("blend", "segments"), default="blend",
                   help="M10b: the thumb's skin weights (alien_thumb.py): blend (the default, a smooth split along "
                   "the thumb) or the cage's segments")
    p.add_argument("--collar", choices=("off", "on"), default="on",
                   help="M10b: the static socket collar per design and side (alien_lids_geom.COLLAR), the default; "
                   "needs --flare off; none on a unit at full size (--eye-scale >= alien_lids_geom.EYE_SCALE)")
    p.add_argument("--no-bake", action="store_true", help="skip the parts' AO bake (a quick geometry check)")
    p.add_argument("--socket", default="", help="M9 (REJECTED, M10): JSON over alien_lids_geom.SOCKET, the eye mount "
                   "applied here; refused without --opt-in-rejected-m9")
    p.add_argument("--opt-in-rejected-m9", action="store_true", help="allow --socket (M9's rejected skull change)")
    p.add_argument("--flare", default="off", help="M10: the lids' flare behind the edge (alien_lids_geom.FLARE_OFF): "
                   "off (M10b's default: the collar fills the gap), auto (the smallest that leaves no gap to the "
                   "unchanged socket skin; with --collar off), or JSON for every lid")
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


def skin_points() -> np.ndarray:
    """The Body's rest-pose vertices in world space (as contact_field reads them)."""
    body = bpy.data.objects["Body"]
    me = body.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    mw = np.array(body.matrix_world)
    return co @ mw[:3, :3].T + mw[:3, 3]


def sink_vector(side: str, sink: float) -> Vector:
    """The eye unit's move back into the head along the socket's axis (local +Y; the eye looks down -Y)."""
    sock = bpy.data.objects[f"Eye_{side}"]
    return (sock.matrix_world.to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized() * sink


def lid_skin_local(lo, r: float, back: Vector, skin: np.ndarray, reach: float = 2.0) -> np.ndarray:
    """The skin's points near a lid in its local frame after the unit's sink, in ball radii (r: the new radius)."""
    c = np.array(lo.matrix_world.translation) + np.array(back)
    near = skin[np.linalg.norm(skin - c, axis=1) < reach * r]
    inv = np.array(lo.matrix_world.inverted())
    loc = (near - np.array(back)) @ inv[:3, :3].T + inv[:3, 3]  # the frame moves by `back`: the points by -back
    return loc / r


def flares(k: float, sink: float, lids: dict | None, spec: str) -> dict:
    """M10: per design and lid the flare (alien_lids_geom.FLARE_OFF's form) for the unit at k: "off" none, "auto" the
    smallest closing every latitude's gap on both sides (alien_lids_geom.auto_flare, the larger side's), else JSON
    {"amount", "from_deg", "to_deg"} for every lid. Measured on the kit's skin with the lids at rest. M10b: with
    "auto" both lids of a design take the larger of their two amounts (each keeps its own ramp), so the corners,
    where the lids meet, show no notch; `gap_r` is measured with that amount."""
    out = {}
    skin = skin_points() if spec == "auto" else None
    for dname, d in EYES.items():
        pts_of = {}
        for lid in ("upper", "lower"):
            if spec == "off":
                out[f"{dname}_{lid}"] = dict(LG.FLARE_OFF)
                continue
            if spec != "auto":
                out[f"{dname}_{lid}"] = dict(LG.FLARE_OFF, **json.loads(spec))
                continue
            rho, bead = LG.slim(d[lid]["rho"], LID_BEAD[lid], lids or LG.LIDS_S9)
            best, gaps = None, {}
            for side in ("L", "R"):
                ball = bpy.data.objects[f"eye_{dname}_ball_{side}"]
                r = ball_radius(ball) * k
                lo = bpy.data.objects[f"eye_{dname}_lid_{lid}_{side}"]
                pts = lid_skin_local(lo, r, sink_vector(side, sink), skin).tolist()
                pts_of[(lid, side)] = (pts, r)
                f = LG.auto_flare(pts, rho[1], bead, lid == "upper", base=LG.flare_base(d[lid]["rest"]))
                if best is None or f["amount"] > best["amount"]:
                    best = f
            out[f"{dname}_{lid}"] = dict(best, own_amount=best["amount"])
        if spec != "auto":
            continue
        shared = max(out[f"{dname}_{lid}"]["amount"] for lid in ("upper", "lower"))
        for lid in ("upper", "lower"):
            f = out[f"{dname}_{lid}"]
            f["amount"] = shared
            rho, bead = LG.slim(d[lid]["rho"], LID_BEAD[lid], lids or LG.LIDS_S9)
            gaps = {}
            for side in ("L", "R"):
                pts, r = pts_of[(lid, side)]
                fl = {k_: f[k_] for k_ in ("amount", "from_deg", "to_deg")}
                g0 = LG.lid_gap(pts, rho[1], bead, lid == "upper", None)
                g1 = LG.lid_gap(pts, rho[1], bead, lid == "upper", fl)
                gaps[side] = {"before_r": round(max(g for _, g, _ in g0), 4),
                              "after_r": round(max(g for _, g, _ in g1), 4),
                              "before_mm": round(max(g for _, g, _ in g0) * r * 1000.0, 2),
                              "bins_open_before": [t for t, g, _ in g0 if g > 0],
                              "contact_p_deg": [pp for _, _, pp in g1]}
            f["gap_r"] = gaps
    log("flare", json.dumps(out))
    return out


def ball_radius(ball) -> float:
    n = len(ball.data.vertices)
    co = np.empty(n * 3)
    ball.data.vertices.foreach_get("co", co)
    return float(np.linalg.norm(co.reshape(-1, 3), axis=1).max())


def lid_reach(lids: dict | None) -> dict:
    """M10 (PR #243's review minor 1): per design the rims' reach beyond the lid edges in degrees (upper, lower),
    alien_eyes_geom.rim_reach of the shells as built; alien.gd takes it from LIDS_MARKER."""
    out = {}
    for dname, d in EYES.items():
        out[dname] = []
        for lid in ("upper", "lower"):
            rho, bead = LG.slim(d[lid]["rho"], LID_BEAD[lid], lids or LG.LIDS_S9)
            out[dname].append(round(math.degrees(E.rim_reach(rho[0], rho[1], bead)), 2))
    return out


def rebuild_eyes(k: float, corner: dict, sink: float = 0.0, lids: dict | None = None, flare: dict | None = None) -> dict:
    """Every lid shell rebuilt with the rounded corners at k times the ball's radius (M9b: slimmed by `lids`,
    alien_lids_geom.slim; None builds S9's shells; M10: swollen behind the edge by `flare`, per "<design>_<lid>"),
    the ball's mesh scaled by k about its centre (the socket), the wet strips rebuilt."""
    wet = bpy.data.materials["alien_wet"]
    lip = bpy.data.materials["alien_lip"]
    rep = {}
    flare = flare or {}
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
                                  corner=corner, flare=flare.get(f"{dname}_{lid}"))
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
                back = sink_vector(side, sink)
                for o in [ball] + [bpy.data.objects[f"eye_{dname}_lid_{lid}_{side}"] for lid in ("upper", "lower")]:
                    mw = o.matrix_world.copy()
                    mw.translation += back
                    o.matrix_world = mw
            up_rho, up_bead = LG.slim(d["upper"]["rho"], LID_BEAD["upper"], lids or LG.LIDS_S9)
            rep[f"{dname}_{side}"] = {"r_before": round(r, 5), "r": round(r * k, 5), "sink_m": sink,
                                      "lids": lids or LG.LIDS_S9,
                                      "flare_r": {lid: (flare.get(f"{dname}_{lid}") or {}).get("amount", 0.0)
                                                  for lid in ("upper", "lower")},
                                      "overhang_upper_r": round(LG.corner_overhang(
                                          up_rho[1], up_bead, corner), 4)}
    log("eyes", json.dumps(rep))
    return rep


# M10b: the static socket collar per design and side (alien_lids_geom.COLLAR; brief UPDATE 14): a thin coral ring
# that fills the gap between the smaller lid domes and the unchanged socket, built on the eye units as rebuilt (scaled,
# sunk). Use it with --flare off.
COLLAR_NAME = "eye_{d}_lid_collar_{s}"  # "_lid_": alien.gd and the page give it the lids' material (LID_LOOK)


def collars() -> list:
    """The kit's collar objects (none on a kit built without --collar)."""
    return [bpy.data.objects[n] for n in (COLLAR_NAME.format(d=d, s=s) for d in EYES for s in ("L", "R"))
            if n in bpy.data.objects]


def build_collars(k: float, lids: dict | None) -> dict:
    """The collars (COLLAR_NAME) on the kit's eye units as rebuilt at k (M8b's: LG.EYE_SCALE); per side the bare
    crater measured round the dome as a front view sees it: per azimuth bin's centre and every ds_mm of s a ray down
    the eye's axis onto the Body (its first hit; the vertices alone were too sparse, a third of the bins had none)."""
    from mathutils import Matrix
    c = LG.COLLAR
    body = bpy.data.objects["Body"]
    bmw = body.matrix_world
    tree = BVHTree.FromPolygons([bmw @ v.co for v in body.data.vertices],
                                [list(pl.vertices) for pl in body.data.polygons])
    lip = bpy.data.materials["alien_lip"]
    rep = {}
    for dname, d in EYES.items():
        rho_out = max(LG.slim(d[lid]["rho"], LID_BEAD[lid], lids or LG.LIDS_S9)[0][1] for lid in ("upper", "lower"))
        for side in ("L", "R"):
            ball = bpy.data.objects[f"eye_{dname}_ball_{side}"]
            cen = np.array(ball.matrix_world.translation)
            rd = ball_radius(ball) * rho_out
            rd_ref = rd * LG.EYE_SCALE / k  # M8b's dome, which the socket was shaped round
            R = bpy.data.objects[f"Eye_{side}"].matrix_world.to_3x3().normalized()
            fw, ax, az = (np.array(R @ Vector(v)).ravel() for v in ((0, -1, 0), (1, 0, 0), (0, 0, 1)))
            hits = []
            down = Vector((-fw).tolist())
            n_s = int((rd_ref + c["margin_mm"] / 1000.0 - rd) / (c["ds_mm"] / 1000.0)) + 2
            for i in range(c["bins"]):
                p = -math.pi + 2.0 * math.pi * (i + 0.5) / c["bins"]
                radial = math.cos(p) * ax + math.sin(p) * az
                for j in range(n_s):
                    s_ = rd + (j + 0.5) * c["ds_mm"] / 1000.0
                    hit = tree.ray_cast(Vector((cen + 1.5 * rd_ref * fw + s_ * radial).tolist()), down, 3.0 * rd_ref)
                    if hit[0] is not None:
                        hits.append((s_, float(np.dot(np.array(hit[0]) - cen, fw)), p))
            raw = LG.collar_gaps(hits, rd, rd_ref)
            gaps = LG.collar_smooth(raw)
            n, m = c["bins"], c["seg"]
            b = G.Built()
            mi = b.slot(lip)
            rings = []
            for i in range(n):
                p = -math.pi + 2.0 * math.pi * (i + 0.5) / n
                radial = math.cos(p) * ax + math.sin(p) * az
                (cs, ch), u, nn, ea, eb = LG.collar_section(gaps[i][0], gaps[i][1], rd)
                ring = []
                for j in range(m):
                    t = 2.0 * math.pi * j / m
                    ps = cs + ea * math.cos(t) * u[0] + eb * math.sin(t) * nn[0]
                    hs = ch + ea * math.cos(t) * u[1] + eb * math.sin(t) * nn[1]
                    co = cen + hs * fw + ps * radial
                    ring.append(b.vert(Vector(co.tolist()), 0.0, 1.0))
                rings.append(ring)
            for i in range(n):
                r0, r1 = rings[i], rings[(i + 1) % n]
                for j in range(m):
                    b.face((r0[j], r1[j], r1[(j + 1) % m], r0[(j + 1) % m]), mi)
            name = COLLAR_NAME.format(d=dname, s=side)
            old = bpy.data.objects.get(name)
            if old is not None:
                bpy.data.objects.remove(old)
            ob = G.to_object(b, name, ball.users_collection[0], origin=Matrix(ball.matrix_world))
            par = ball.parent
            if par is not None:  # a sibling of the ball: shown with its design (alien.gd's eye_<design>_<side>)
                mw = ob.matrix_world.copy()
                ob.parent = par
                if ball.parent_type == "BONE":
                    ob.parent_type, ob.parent_bone = "BONE", ball.parent_bone
                ob.matrix_world = mw
            known = [g for g in raw if g is not None]
            gw = [g[0] for g in gaps]
            rep[f"{dname}_{side}"] = {"rd_mm": round(rd * 1000.0, 2), "rd_ref_mm": round(rd_ref * 1000.0, 2),
                                      "parent": par.name if par else None,
                                      "gap_mm_max": round(max(gw) * 1000.0, 2),
                                      "gap_mm_mean": round(sum(gw) / n * 1000.0, 2),
                                      "gap_mm_min": round(min(gw) * 1000.0, 2),
                                      "h_edge_mm": [round(min(g[1] for g in gaps) * 1000.0, 2),
                                                    round(max(g[1] for g in gaps) * 1000.0, 2)],
                                      "bins_with_skin": len(known), "verts": len(ob.data.vertices)}
    log("collar", json.dumps(rep))
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
    groups = [([bpy.data.objects[f"eye_{d}_lid_{lid}_{s}"] for lid in ("upper", "lower") for s in ("L", "R")]
               + [o for o in collars() if o.name.startswith(f"eye_{d}_")],  # M10b: a design's collars with its lids
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
              + [o for o in collars() if o.name.startswith(f"eye_{d}_")] for d in EYES}  # M10b: and its collars
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
    if a.collar == "on" and a.flare != "off":  # PR #245's review: refused before any work
        raise SystemExit("--collar on needs --flare off (the collar fills the gap the flare closed); "
                         "with a flare, pass --collar off")
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
    if a.thumb == "blend":  # M10b: the thumb's smooth split (the Idle thumb read swollen; the fist kept its curl)
        rep["thumb"] = alien_thumb.apply(body)
        log("thumb", json.dumps(rep["thumb"]))
    k, sink = a.eye_scale, a.eye_sink
    if a.socket:  # M9's grid: the mount on this kit (refused if it has one); rejected since M10
        if not a.opt_in_rejected_m9:
            raise SystemExit(alien_socket.REJECTED.replace("alien_socket.py", "alien_m6.py --socket"))
        rep["socket"] = alien_socket.apply(json.loads(a.socket))
    if alien_socket.MARKER in body.keys():  # M9: the mount sized and placed the eyes; rebuild the lids at that size
        k, sink = 1.0, 0.0
        rep["socket_mount"] = json.loads(body[alien_socket.MARKER])
    # M9b: the slim shells on the mount (an unmounted kit keeps S9's shells unless --lids asks)
    lids = LG.set_lids(json.loads(a.lids)) if a.lids else (LG.LIDS if "socket_mount" in rep else None)
    rep["lids"] = lids or LG.LIDS_S9
    rep["eye_scale"], rep["eye_sink"] = k, sink
    rep["flare"] = flares(k, sink, lids, a.flare)
    rep["eyes"] = rebuild_eyes(k, corner, sink, lids, rep["flare"])
    rep["lid_reach_deg"] = lid_reach(lids)
    if a.collar == "on" and k < LG.EYE_SCALE:  # a full-size unit is M8b's as it was: no gap, no collar
        rep["collar"] = build_collars(k, lids)
    bpy.data.materials["alien_lip"][LIDS_MARKER] = json.dumps(  # PR #243's minor 1: alien.gd's rim reaches
        {"lids": lids or LG.LIDS_S9, "reach_deg": rep["lid_reach_deg"]}, sort_keys=True)
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
