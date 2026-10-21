"""M11, the lashes eyes el2 (art #196, brief UPDATE 21), in headless Blender. Opens a kit's
export/alien_character.blend (alien_m6's or later: M10c's eyes, with or without the later mouths) and writes a new
kit into <out>/<export-name> (never over its input) with upper lashes on both eye designs:

- per design and side eye_<design>_lashes_<side>: one mesh (alien_lashes_geom: tapered curled lashes rooted on the
  upper lid's rolled rim, thicker and longer toward the temple, the last few winging out, and a thin liner along the
  roots), a child of eye_<design>_lid_upper_<side> with an identity local transform, so it turns with the lid (blink,
  half lid, surprise) and shows with its design; built from the kit's own lids (character.json m6: the lid setting,
  the corners) at the ball's radius, so it fits every eye size;
- its material alien_lash (black, glossy: a low roughness and a clear coat), glTF extras LASH_MARKER;
- with --grid FILE (JSON {"variants": {name: spec over alien_lashes_geom.LASHES}}) each variant as extra nodes
  lashvar_<name>_<design>_<side> beside it (the grid's kit only);
- a clip check: with the lids in every state (open, rest, half, closed) of each design, the lash vertices inside the
  skin (Body and the skin collars), the eyeball, the lower lid and (away from the sunk roots) the upper lid; the kit
  is refused if any lash vertex is inside (--allow-clip for a variant grid);
- export/alien_character.glb with alien_m6's options, its .blend, character.json (nodes.lashes, `m11`, `note_m11`) and
  the kit's PNGs. Nothing else in the kit changes.

    tools/runner/blender.py run_script("alien_lashes.py", ["--kit", <kit>/export, "--out", <M11>])
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
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_eyes as AE  # noqa: E402
import alien_eyes_geom as E  # noqa: E402
import alien_lashes_geom as LL  # noqa: E402
import alien_lids_geom as LG  # noqa: E402
import alien_m6 as M6  # noqa: E402
import export_glb  # noqa: E402
from alien_parts import EYES, LID_BEAD  # noqa: E402

NAME = "eye_{d}_lashes_{s}"
VAR_NAME = "lashvar_{v}_{d}_{s}"
MATERIAL = "alien_lash"
LASH_MARKER = {"prime_lashes": "m11"}  # alien.gd: the lash material's look and the toggle
LASH_LOOK = {"base": (0.010, 0.009, 0.011), "roughness": 0.28, "coat": 0.6, "coat_roughness": 0.12}
STATES = ("open", "rest", "half", "closed")


def log(*a):
    print("M11", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--kit", required=True, help="the input kit's export folder (alien_m6's or later)")
    p.add_argument("--out", required=True)
    p.add_argument("--export-name", default="export")
    p.add_argument("--lashes", default="", help="JSON over alien_lashes_geom.LASHES")
    p.add_argument("--grid", default="", help="a JSON file {\"variants\": {name: spec}}: extra lashvar_ nodes")
    p.add_argument("--orm-sss", default="", help="the skin's composed ORM for the SSS route check")
    p.add_argument("--allow-clip", action="store_true", help="report clipping lash vertices, do not refuse the kit")
    return p.parse_args(argv)


def lash_material():
    mat = bpy.data.materials.get(MATERIAL) or bpy.data.materials.new(MATERIAL)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*LASH_LOOK["base"], 1.0)
    bsdf.inputs["Roughness"].default_value = LASH_LOOK["roughness"]
    bsdf.inputs["Coat Weight"].default_value = LASH_LOOK["coat"]
    bsdf.inputs["Coat Roughness"].default_value = LASH_LOOK["coat_roughness"]
    for k, v in LASH_MARKER.items():
        mat[k] = v
    return mat


def remove_old():
    for o in list(bpy.data.objects):
        if "_lashes_" in o.name or o.name.startswith("lashvar_"):
            me = o.data
            bpy.data.objects.remove(o)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)


def temple_side(lid) -> float:
    """+1 when the lid's local +X points away from the face's centre line (the temple), else -1."""
    mid = (bpy.data.objects["Eye_L"].matrix_world.translation + bpy.data.objects["Eye_R"].matrix_world.translation) / 2
    x_axis = lid.matrix_world.to_3x3() @ Vector((1.0, 0.0, 0.0))
    out = lid.matrix_world.translation - mid
    return 1.0 if x_axis.dot(out) > 0.0 else -1.0


def make_set(name: str, lid, spec: dict, mat, lids: dict, corner: dict) -> tuple:
    d = next(dn for dn in EYES if lid.name.startswith(f"eye_{dn}_"))
    rho, bead = LG.slim(EYES[d]["upper"]["rho"], LID_BEAD["upper"], lids)
    ball = bpy.data.objects[lid.name.replace("_lid_upper_", "_ball_")]
    r = M6.ball_radius(ball)
    side = temple_side(lid)
    if d in spec["design_lift_deg"]:  # the design's own lift (alien_lashes_geom.LASHES design_lift_deg)
        spec = dict(spec, lift_deg=spec["design_lift_deg"][d])
    verts, faces, rep = LL.build(spec, rho[0], rho[1], bead, corner, side)
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(c * r for c in v) for v in verts], [], faces)
    me.update()
    for poly in me.polygons:
        poly.use_smooth = True
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    lid.users_collection[0].objects.link(ob)
    ob.parent = lid
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = Matrix.Identity(4)
    rep.update({"r_mm": round(r * 1000.0, 2), "side": side, "faces": len(faces)})
    return ob, rep, rep.pop("u")


def inside_count(tree, pts: np.ndarray, reach: float) -> tuple[int, float]:
    """How many points lie inside a closed surface (the nearest face's normal points away from them), and the least
    signed distance (negative: inside) within reach."""
    n, least = 0, reach
    for p in pts:
        hit = tree.find_nearest(Vector(p.tolist()), reach)
        if hit[0] is None:
            continue
        sd = float(np.dot(p - np.array(hit[0]), np.array(hit[1])))
        if sd < 0.0:
            n += 1
        least = min(least, sd)
    return n, least


def world_tree(objs) -> BVHTree:
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys = [], []
    for o in objs:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        mw = o.matrix_world
        base = len(verts)
        verts += [mw @ v.co for v in me.vertices]
        polys += [[base + i for i in p.vertices] for p in me.polygons]
        ev.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys)


def clip_check(sets: dict) -> dict:
    """Per design and lid state: the lash vertices inside the skin, the ball, the lower lid and (u above the root's
    first ring) the upper lid. sets: {(design, side): (object, u per vertex)}."""
    body = bpy.data.objects["Body"]
    skin = [body] + M6.skin_collars()
    out = {}
    rot0 = {o.name: o.rotation_euler.x for o in bpy.data.objects if "_lid_" in o.name}
    skin_tree = world_tree(skin)
    for d in EYES:
        for st in STATES:
            for s in ("L", "R"):
                bpy.data.objects[f"eye_{d}_lid_upper_{s}"].rotation_euler.x = -math.radians(EYES[d]["upper"][st])
                bpy.data.objects[f"eye_{d}_lid_lower_{s}"].rotation_euler.x = -math.radians(EYES[d]["lower"][st])
            bpy.context.view_layer.update()
            rep = {}
            for s in ("L", "R"):
                ob, u = sets[(d, s)]
                mw = np.array(ob.matrix_world)
                co = np.array([v.co[:] for v in ob.data.vertices])
                w = co @ mw[:3, :3].T + mw[:3, 3]
                u = np.array(u)
                lash = w[u >= 0.0]
                ball = bpy.data.objects[f"eye_{d}_ball_{s}"]
                c = np.array(ball.matrix_world.translation)
                r = M6.ball_radius(ball)
                n_skin, least = inside_count(skin_tree, w, 0.01)
                lower = world_tree([bpy.data.objects[f"eye_{d}_lid_lower_{s}"]])
                upper = world_tree([bpy.data.objects[f"eye_{d}_lid_upper_{s}"]])
                n_low, _ = inside_count(lower, w, 0.005)
                n_up, _ = inside_count(upper, w[u > 0.15], 0.005)
                rep[s] = {"skin": n_skin, "skin_least_mm": round(least * 1000.0, 2),
                          "ball": int((np.linalg.norm(w - c, axis=1) < r).sum()), "lower_lid": n_low,
                          "upper_lid": n_up, "lash_verts": int(len(lash))}
            out[f"{d}_{st}"] = rep
    for name, x in rot0.items():
        bpy.data.objects[name].rotation_euler.x = x
    bpy.context.view_layer.update()
    return out


def main():
    a = args()
    kit, out = Path(a.kit), Path(a.out)
    ex = out / a.export_name
    if ex.resolve() == kit.resolve():
        raise SystemExit("the M11 kit must not overwrite its input")
    spec = LL.merged(json.loads(a.lashes) if a.lashes else None)
    grid = json.loads(Path(a.grid).read_text(encoding="utf-8")) if a.grid else {"variants": {}}
    bpy.ops.wm.open_mainfile(filepath=str(kit / "alien_character.blend"))
    cj = json.loads((kit / "character.json").read_text(encoding="utf-8"))
    m6 = cj.get("m6", {})
    lids, corner = m6.get("lids", LG.LIDS_S9), m6.get("corner", LG.CORNER)
    body = M6.rest_pose()
    remove_old()
    mat = lash_material()
    rep = {"lashes": spec, "lids": lids, "corner": corner, "sets": {}}
    sets, nodes = {}, {}
    for d in EYES:
        for s in ("L", "R"):
            lid = bpy.data.objects[f"eye_{d}_lid_upper_{s}"]
            ob, r, u = make_set(NAME.format(d=d, s=s), lid, spec, mat, lids, corner)
            sets[(d, s)] = (ob, u)
            nodes.setdefault(d, {})[s] = ob.name
            rep["sets"][ob.name] = {k: v for k, v in r.items() if k != "lashes"}
            rep["sets"][ob.name]["lashes"] = r["lashes"]
            for vn, vs in grid["variants"].items():
                vo, vr, vu = make_set(VAR_NAME.format(v=vn, d=d, s=s), lid, LL.merged(vs), mat, lids, corner)
                sets[(d, s, vn)] = (vo, vu)
                rep.setdefault("grid", {})[vo.name] = {"verts": vr["verts"], "spec": vs}
    log("sets", json.dumps({k: [v["verts"], v["r_mm"], v["side"]] for k, v in rep["sets"].items()}))
    rep["clip"] = clip_check(sets)
    for vn in grid["variants"]:
        rep.setdefault("clip_grid", {})[vn] = clip_check({(d, s): sets[(d, s, vn)] for d in EYES for s in ("L", "R")})
    bad = {k: v for k, v in rep["clip"].items()
           if any(x["skin"] or x["ball"] or x["lower_lid"] or x["upper_lid"] for x in v.values())}
    log("clip", json.dumps(rep["clip"]))
    if "clip_grid" in rep:
        log("clip grid", json.dumps({vn: {k: {s: [x["skin"], x["ball"], x["lower_lid"], x["upper_lid"]]
                                                for s, x in v.items()} for k, v in c.items()}
                                     for vn, c in rep["clip_grid"].items()}))
    if bad and not a.allow_clip:
        raise SystemExit(f"lash vertices clip: {json.dumps(bad)}")
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
    if a.orm_sss:
        bad_sss = E.sss_orm_problems(glb.read_bytes(), "alien_hue", Path(a.orm_sss).read_bytes())
        if bad_sss:
            raise SystemExit(f"the GLB's SSS route: {bad_sss}")
        log("sss route ok")
    for f in kit.iterdir():
        if f.suffix == ".png":
            shutil.copy2(f, ex / f.name)
    cj["nodes"]["lashes"] = nodes
    cj["m11"] = rep
    cj["note_m11"] = (
        "art #196 M11: upper lashes (the el2 sheet) per eye design and side, eye_<design>_lashes_<side>, a child of "
        "eye_<design>_lid_upper_<side> (identity local transform: it turns with the lid), material alien_lash (black, "
        "glossy; extras " + json.dumps(LASH_MARKER) + "); alien.gd shows them with set_lashes(true), the default "
        "off." + (" The grid kit also has lashvar_<variant>_<design>_<side> nodes (m11.grid)." if grid["variants"] else ""))
    (ex / "character.json").write_text(json.dumps(cj, indent=1), encoding="utf-8", newline="\n")
    log("EXPORT", glb, round(glb.stat().st_size / 1e6, 2), "MB")


if __name__ == "__main__":
    main()
