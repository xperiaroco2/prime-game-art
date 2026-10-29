"""The dressed character's proof in motion (art #196, clothes step 2, C1): opens clothes_dress.py's <name>_char.blend
and, per clip, measures the poke-through and shoots the contact sheet; then the close-ups at 0.8 m.

- Poke-through (each clip's "where": up to six of the vertices that poke, deepest first, with their rest place and
  strongest bone): the body vertices under the cloth at rest (nearest cloth point within --near m and behind the
  cloth's face there, and farther than --opening m from every real opening, where moving out of the cuff is no
  fault: clothes_open.opening_points, the top's collar and cuffs, the trousers' hems and the shoes' tops; the straps',
  panels' and cut edges and the hidden-face holes are no opening) are followed through every frame of each clip; a frame counts those that end up outside the
  cloth by more than --tol m and the deepest; the clip's numbers are the frame maximum (clothes_fit_geom.frame_max).
  A vertex outside by more than --exposed m whose nearest cloth point is above the chest (the UpperChest bone's head
  in that frame) on a cloth face turned up is exposed skin, not poke-through (clothes_fit_geom.exposed_skin: the
  neck over the collar's roll); the clip's frame maximum of those is exposed_skin_max.
- The top under the panels (the hybrid route: the top on the body's weights, the bib, back panel and straps on the
  fit's): the top's vertices whose normal meets the garment within --panel-reach m at rest, inside it there, are
  followed the same way against the garment alone; a frame counts those outside it by more than --tol m (poke.json's
  "top_under_panels" per clip, its "where" with the top vertex's bone). The nearest face can change in motion (a
  strap's folded lip, the bib's edge rim), so each such vertex is also followed against its own panel point: where
  its normal met the garment at rest, the same point of that face (barycentric) in each frame, and its side of
  that face's plane ("top_under_panels_tracked", with the room at rest; C1i). A sliver (thinner than
  --track-min-alt) or a face folded back against its neighbours carries no tracked point: the ray goes on past it
  (clothes_shell.track_face_ok; C1j, the one vertex per character r26 counted).
- The contact sheet: per clip (rows) the front, side and back at two moments of the clip (Workbench, the textures,
  orthographic), about 1280 px wide.
- The close-ups: in Idle's first frame, the collar and neck, the cuffs and hands, the crotch, the hems and shoes,
  each from the front three-quarter and the back three-quarter at 0.8 m (lens 50).

    blender -b --factory-startup --python tools/blender/clothes_proof.py -- --blend DRESSED.blend --name chameleon
        --out DIR [--clips Idle,Walk,...]

Writes DIR/poke.json, DIR/<name>_motion.png, DIR/<name>_closeups.png and DIR/<name>_cloth_alone.png (the cloth
alone in Idle: front, side, back). Prints CLOTHES_PROOF lines.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.geometry import normal as poly_normal
from mathutils.interpolate import poly_3d_calc
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clothes_fit_geom as F  # noqa: E402
import clothes_open as O  # noqa: E402
import clothes_shell as H  # noqa: E402

CLIPS = "Idle,Walk,Jog_Fwd,Sprint_Fwd,Strafe_Left,Crouch_Fwd,Jump_Start,Jump_Air,Talk_Upper"
PREFIX = "CharacterArmature|"


def say(*a) -> None:
    print("CLOTHES_PROOF", *a, flush=True)


def action_for(clip: str):
    names = [a for a in bpy.data.actions if a.name.startswith(PREFIX)
             and a.name[len(PREFIX):].split("_Loop")[0] == clip]
    return names[0] if names else None


def world(o) -> np.ndarray:
    dg = bpy.context.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    m = np.array(o.matrix_world)
    co = co @ m[:3, :3].T + m[:3, 3]
    ev.to_mesh_clear()
    return co


def cloth_tree(cloth, polys, cos=None) -> BVHTree:
    co = np.concatenate([cos[o.name] if cos else world(o) for o in cloth])
    return BVHTree.FromPolygons([tuple(c) for c in co], polys)


def side(tree: BVHTree, pts: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per point its signed distance from the cloth along the nearest cloth face's normal (+: outside), the height
    of that nearest cloth point and the z of that face's normal."""
    s, z, nz = np.zeros(len(pts)), np.zeros(len(pts)), np.zeros(len(pts))
    for i, p in enumerate(pts):
        loc, nor, _fi, _d = tree.find_nearest(Vector(p))
        s[i] = (Vector(p) - loc).dot(nor) if loc is not None else -1.0
        z[i] = loc.z if loc is not None else 0.0
        nz[i] = nor.z if loc is not None else 0.0
    return s, z, nz


def tracked_side(p, face, bary, sign: float) -> float:
    """A top vertex p's side of its own panel point (C1i): the point bary of the face (its vertices, posed), along
    the face's normal, times sign (so that under the panel is negative whichever way the face is wound)."""
    q = [Vector(c) for c in face]
    at = sum((c * w for c, w in zip(q, bary)), Vector())
    return sign * (Vector(p) - at).dot(poly_normal(q))


def render_tile(sc, path: Path) -> np.ndarray:
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(str(path))
    px = np.array(img.pixels[:], dtype=np.float32).reshape(sc.render.resolution_y, sc.render.resolution_x, 4)
    bpy.data.images.remove(img)
    return px


def save_sheet(rows: list[list[np.ndarray]], path: Path) -> None:
    grid = np.concatenate([np.concatenate(r, axis=1) for r in rows[::-1]], axis=0)  # Blender's pixels start bottom
    img = bpy.data.images.new(path.stem, grid.shape[1], grid.shape[0])
    img.pixels[:] = grid.ravel()
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def look(cam, eye: Vector, target: Vector) -> None:
    cam.location = eye
    cam.rotation_euler = (target - eye).to_track_quat("-Z", "Y").to_euler()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--clips", default=CLIPS)
    ap.add_argument("--near", type=float, default=0.06)
    ap.add_argument("--tol", type=float, default=0.001)
    ap.add_argument("--opening", type=float, default=0.04, help="body vertices this near an opening are left out")
    ap.add_argument("--tile", type=int, default=213)
    ap.add_argument("--track-min-alt", type=float, default=0.0015,
                    help="a garment face thinner than this cannot carry a tracked point; nor can a folded one (m)")
    ap.add_argument("--panel-reach", type=float, default=0.04,
                    help="a top vertex whose normal meets the garment this near at rest is under a panel (m)")
    ap.add_argument("--exposed", type=float, default=0.02,
                    help="outside the cloth by more than this over an upward collar face: exposed skin (m)")
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(Path(args.blend).resolve()))
    arm = bpy.data.objects["CharacterArmature"]
    cloth = [bpy.data.objects[n] for n in ("garment", "shoes", "top") if n in bpy.data.objects]
    try:
        body = O.body_mesh(arm, cloth, args.name)
    except ValueError as e:
        say("REFUSED", e)
        return 2
    polys, off = [], 0
    for o in cloth:
        polys += [[i + off for i in p.vertices] for p in o.data.polygons]
        off += len(o.data.vertices)
    arm.animation_data_create()
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.matrix_basis.identity()
    bpy.context.view_layer.update()
    rest = world(body)
    tree = cloth_tree(cloth, polys)
    # the body vertices the cloth is meant to hide: within --near of the cloth, inside it, or outside it at rest
    # (already poking through) where the nearest cloth point is no opening
    near, s0, locs = [], [], []
    for i, p in enumerate(rest):
        loc, nor, _fi, d = tree.find_nearest(Vector(p), args.near)
        if loc is not None:
            near.append(i)
            s0.append((Vector(p) - loc).dot(nor))
            locs.append(loc)
    # a body vertex whose nearest cloth point is near a real opening (collar, cuffs, hems, the shoes' tops) leaves
    # the opening when it moves (the wrist out of the cuff): that is no poke-through, so it is counted apart
    edge_pts, open_rep = O.opening_points(cloth, arm)
    say("openings", len(edge_pts), "points:", open_rep)
    kd = O.kd_of(edge_pts)
    # inside: the body vertex by the opening; outside: its nearest cloth point by the opening (the hand beyond a cuff)
    at_open = np.array([kd.find(Vector(rest[i]) if s < 0 else loc)[2] < args.opening
                        for i, s, loc in zip(near, s0, locs)], dtype=bool)
    rest_poke = F.rest_poke([s * 1000 for s in s0], at_open.tolist(), args.tol * 1000)
    near = np.array(near)[~at_open] if len(near) else np.array(near)
    say("hidden by the cloth at rest:", len(near), "body vertices,", rest_poke, "of them outside it;",
        int(at_open.sum()), "more by an opening, left out")
    def bone_of(o, k: int) -> str:  # a poking vertex's strongest bone, to say where it is
        gs = o.data.vertices[k].groups
        return o.vertex_groups[max(gs, key=lambda g: g.weight).group].name if len(gs) else ""

    # the top under the bib, the back panel and the straps (their own weights): it must stay under them
    gar = bpy.data.objects.get("garment")
    top = bpy.data.objects.get("top")
    under, g_polys = np.zeros(0, dtype=int), []
    if gar is not None and top is not None:
        g_polys = [list(q.vertices) for q in gar.data.polygons]
        gco, tco = world(gar), world(top)
        gtree = BVHTree.FromPolygons([tuple(c) for c in gco], g_polys)
        nm = top.matrix_world.to_3x3().inverted().transposed()
        cand, dropped, track = [], 0, []
        # a sliver or a folded-back face cannot carry a tracked point (C1j: its plane swings as it bends; the r26
        # cases): the ray goes on past it to the next face
        gq = [[Vector(gco[k]) for k in vs] for vs in g_polys]
        gn = [poly_normal(q) for q in gq]
        by_vert: dict[int, list[int]] = {}
        for fi_, vs in enumerate(g_polys):
            for k in vs:
                by_vert.setdefault(k, []).append(fi_)

        def face_ok(fi_: int) -> bool:
            q = gq[fi_]
            edges = [(q[i] - q[(i + 1) % len(q)]).length for i in range(len(q))]
            area = sum(((q[i] - q[0]).cross(q[i + 1] - q[0])).length / 2 for i in range(1, len(q) - 1))
            nb = {f for k in g_polys[fi_] for f in by_vert[k]} - {fi_}
            return H.track_face_ok(edges, area, [gn[f].dot(gn[fi_]) for f in nb], args.track_min_alt)

        skipped = 0
        for v in top.data.vertices:
            p, n = Vector(tco[v.index]), (nm @ v.normal).normalized()
            hit, _hn, hfi, hd = gtree.ray_cast(p + n * 1e-4, n, args.panel_reach)
            reach = args.panel_reach
            while hit is not None and not face_ok(hfi):
                skipped += 1
                reach -= hd + 1e-4
                start = hit + n * 1e-4
                hit, _hn, hfi, hd = gtree.ray_cast(start, n, reach) if reach > 0 else (None,) * 4
                if hit is not None:
                    hd = (hit - start).length
            if hit is None:
                continue
            vs = g_polys[hfi]
            q = [Vector(gco[k]) for k in vs]
            r0 = (p - hit).dot(poly_normal(q))
            track.append((v.index, vs, poly_3d_calc(q, hit), 1.0 if r0 < 0 else -1.0, abs(r0)))
            loc, nor, _fi, _d = gtree.find_nearest(p)
            if loc is not None and (p - loc).dot(nor) < 0:
                cand.append(v.index)
            else:
                dropped += 1
        under = np.array(cand, dtype=int)
        say("top under the panels at rest:", len(under), "vertices;", dropped,
            "with the garment over them but outside its nearest face at rest, left out;", len(track), "tracked;",
            skipped, "sliver or folded faces passed")

    head = {b.name: arm.matrix_world @ b.head_local for b in arm.data.bones}
    front = 1.0 if (head["LeftToes"] - head["LeftFoot"]).y > 0 else -1.0
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "TEXTURE"
    sc.display.shading.show_cavity = True
    sc.view_settings.view_transform = "Standard"
    sc.render.film_transparent = False
    cam = bpy.data.objects.new("proof_cam", bpy.data.cameras.new("proof_cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    tmp = out / "tiles"
    tmp.mkdir(exist_ok=True)
    poke, rows = {}, []
    t = args.tile
    sc.render.resolution_x, sc.render.resolution_y = t, int(t * 1.5)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 2.05
    views = {"front": Vector((0, 4 * front, 0)), "side": Vector((4, 0, 0)), "back": Vector((0, -4 * front, 0))}
    for clip in args.clips.split(","):
        act = action_for(clip)
        if act is None:
            say("no clip", clip)
            poke[clip] = None
            continue
        arm.animation_data.action = act
        f0, f1 = (int(round(x)) for x in act.frame_range)
        frames, skin, worst, tframes, tworst, kframes, kworst = [], 0, {}, [], {}, [], {}
        for f in range(f0, max(f0 + 1, f1 + 1)):
            sc.frame_set(f)
            cos = {o.name: world(o) for o in cloth}
            ctree = cloth_tree(cloth, polys, cos)
            if len(under):
                ts = side(BVHTree.FromPolygons([tuple(c) for c in cos["garment"]], g_polys), cos["top"][under])[0]
                tbad = ts > args.tol
                tframes.append((int(tbad.sum()), float(ts[tbad].max()) if tbad.any() else 0.0))
                for j in np.nonzero(tbad)[0]:
                    tworst[int(under[j])] = max(tworst.get(int(under[j]), 0.0), float(ts[j]))
            if track:
                gp, tp = cos["garment"], cos["top"]
                ks = np.array([tracked_side(tp[k], [gp[i] for i in vs], w, sg) for k, vs, w, sg, _r in track])
                kbad = ks > args.tol
                kframes.append((int(kbad.sum()), float(ks[kbad].max()) if kbad.any() else 0.0))
                for j in np.nonzero(kbad)[0]:
                    kworst[track[j][0]] = max(kworst.get(track[j][0], 0.0), float(ks[j]))
            s, cz, cnz = side(ctree, world(body)[near]) if len(near) else (np.zeros(0),) * 3
            chest = (arm.matrix_world @ arm.pose.bones["UpperChest"].head).z
            exposed = np.array([F.exposed_skin(d, z, nz, chest, args.exposed) for d, z, nz in zip(s, cz, cnz)],
                               dtype=bool)
            bad = (s > args.tol) & ~exposed
            skin = max(skin, int(exposed.sum()))
            frames.append((int(bad.sum()), float(s[bad].max()) if bad.any() else 0.0))
            for j in np.nonzero(bad)[0]:
                worst[int(near[j])] = max(worst.get(int(near[j]), 0.0), float(s[j]))
        poke[clip] = {"action": act.name, **F.frame_max(frames), "exposed_skin_max": skin,
                      "where": [{"rest": [round(float(x), 3) for x in rest[k]], "bone": bone_of(body, k),
                                 "depth_mm": round(1000 * d, 1)}
                                for k, d in sorted(worst.items(), key=lambda kv: -kv[1])[:6]]}
        if len(under):
            tv = top.data.vertices
            poke[clip]["top_under_panels"] = {
                **F.frame_max(tframes),
                "where": [{"rest": [round(float(x), 3) for x in top.matrix_world @ tv[k].co], "bone": bone_of(top, k),
                           "depth_mm": round(1000 * d, 1)}
                          for k, d in sorted(tworst.items(), key=lambda kv: -kv[1])[:6]]}
        if track:
            tv = top.data.vertices
            rooms = sorted(r for *_x, r in track)
            poke[clip]["top_under_panels_tracked"] = {
                **F.frame_max(kframes), "vertices": len(track),
                "room_at_rest_mm_min_median": [round(1000 * rooms[0], 1), round(1000 * rooms[len(rooms) // 2], 1)],
                "where": [{"rest": [round(float(x), 3) for x in top.matrix_world @ tv[k].co], "bone": bone_of(top, k),
                           "depth_mm": round(1000 * d, 1)}
                          for k, d in sorted(kworst.items(), key=lambda kv: -kv[1])[:6]]}
        say("poke", clip, poke[clip])
        row = []
        for k in (0.25, 0.6):
            sc.frame_set(int(round(f0 + k * (f1 - f0))))
            for vname, eye in views.items():
                look(cam, Vector((0, 0, 0.95)) + eye, Vector((0, 0, 0.95)))
                row.append(render_tile(sc, tmp / f"{clip}_{k}_{vname}.png"))
        rows.append(row)
    save_sheet(rows, out / f"{args.name}_motion.png")
    # the close-ups at 0.8 m in Idle
    idle = action_for("Idle")
    arm.animation_data.action = idle
    sc.frame_set(int(idle.frame_range[0]) if idle else 1)
    cam.data.type = "PERSP"
    cam.data.lens = 50
    sc.render.resolution_x = sc.render.resolution_y = 320
    sc.display.shading.show_backface_culling = False
    bpy.context.view_layer.update()
    pose = {pb.name: arm.matrix_world @ pb.head for pb in arm.pose.bones}
    spots = {"collar": pose["Neck"] + Vector((0, 0, -0.04)), "cuff": pose["LeftHand"],
             "crotch": pose["Hips"] + Vector((0, 0, -0.08)), "hem_shoe": pose["LeftFoot"] + Vector((0, 0, 0.0))}
    crow = []
    for vname, ang in (("front34", 35.0), ("back34", 145.0), ("side", 90.0)):
        row = []
        for spot, tgt in spots.items():
            a = math.radians(ang)
            d = Vector((math.sin(a) * 0.8, math.cos(a) * 0.8 * front, 0.05))
            look(cam, tgt + d, tgt)
            row.append(render_tile(sc, tmp / f"close_{spot}_{vname}.png"))
        crow.append(row)
    save_sheet(crow, out / f"{args.name}_closeups.png")
    # the cloth alone in Idle (the body hidden): teal on the cloth here is the texture, not the body poking through
    body.hide_render = True
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 1.9
    sc.render.resolution_x, sc.render.resolution_y = 400, 600
    alone = []
    for vname, eye in views.items():
        look(cam, Vector((0, 0, 0.8)) + eye, Vector((0, 0, 0.8)))
        alone.append(render_tile(sc, tmp / f"alone_{vname}.png"))
    save_sheet([alone], out / f"{args.name}_cloth_alone.png")
    body.hide_render = False
    (out / "poke.json").write_text(json.dumps({"blend": args.blend, "under_cloth_at_rest": int(len(near)),
                                               "outside_cloth_at_rest": rest_poke,
                                               "left_out_by_an_opening": int(at_open.sum()),
                                               "openings": open_rep, "top_under_panels_at_rest": int(len(under)),
                                               "tol_m": args.tol, "clips": poke}, indent=1),
                                   encoding="utf-8", newline="\n")
    say("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
