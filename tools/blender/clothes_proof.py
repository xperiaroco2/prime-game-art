"""The dressed character's proof in motion (art #196, clothes step 2, C1): opens clothes_dress.py's <name>_char.blend
and, per clip, measures the poke-through and shoots the contact sheet; then the close-ups at 0.8 m.

- Poke-through: the body vertices under the cloth at rest (nearest cloth point within --near m and behind the
  cloth's face there, and farther than --opening m from every opening, where moving out of the cuff is no fault) are
  followed through every frame of each clip; a frame counts those that end up outside the
  cloth by more than --tol m and the deepest; the clip's numbers are the frame maximum (clothes_fit_geom.frame_max).
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
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clothes_fit_geom as F  # noqa: E402

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


def cloth_tree(cloth, polys) -> BVHTree:
    co = np.concatenate([world(o) for o in cloth])
    return BVHTree.FromPolygons([tuple(c) for c in co], polys)


def side(tree: BVHTree, pts: np.ndarray) -> np.ndarray:
    """Per point its signed distance from the cloth along the nearest cloth face's normal (+: outside)."""
    s = np.zeros(len(pts))
    for i, p in enumerate(pts):
        loc, nor, _fi, _d = tree.find_nearest(Vector(p))
        s[i] = (Vector(p) - loc).dot(nor) if loc is not None else -1.0
    return s


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
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(Path(args.blend).resolve()))
    arm = bpy.data.objects["CharacterArmature"]
    cloth = [bpy.data.objects[n] for n in ("garment", "shoes") if n in bpy.data.objects]
    body = next(o for o in bpy.data.objects if o.type == "MESH" and o.parent == arm and o not in cloth)
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
    near, s0 = [], []
    for i, p in enumerate(rest):
        loc, nor, _fi, d = tree.find_nearest(Vector(p), args.near)
        if loc is not None:
            sd = (Vector(p) - loc).dot(nor)
            if sd < 0:
                near.append(i)
                s0.append(sd)
    # a body vertex whose nearest cloth point is near an opening (collar, cuffs, hems, the shoes' tops) leaves the
    # opening when it moves (the wrist out of the cuff): that is no poke-through, so it is counted apart
    import bmesh
    edge_pts = []
    for o in cloth:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        edge_pts += [tuple(o.matrix_world @ v.co) for v in bm.verts if v.is_boundary]
        bm.free()
    from mathutils.kdtree import KDTree
    kd = KDTree(len(edge_pts))
    for i, p in enumerate(edge_pts):
        kd.insert(p, i)
    kd.balance()
    at_open = np.array([kd.find(Vector(rest[i]))[2] < args.opening for i in near], dtype=bool)
    near = np.array(near)[~at_open] if len(near) else np.array(near)
    say("under the cloth at rest:", len(near), "body vertices;", int(at_open.sum()), "more by an opening, left out")
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
        frames = []
        for f in range(f0, max(f0 + 1, f1 + 1)):
            sc.frame_set(f)
            ctree = cloth_tree(cloth, polys)
            s = side(ctree, world(body)[near]) if len(near) else np.zeros(0)
            bad = s > args.tol
            frames.append((int(bad.sum()), float(s[bad].max()) if bad.any() else 0.0))
        poke[clip] = {"action": act.name, **F.frame_max(frames)}
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
                                               "tol_m": args.tol, "clips": poke}, indent=1),
                                   encoding="utf-8", newline="\n")
    say("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
