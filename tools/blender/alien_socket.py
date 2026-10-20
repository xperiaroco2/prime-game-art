"""M9, one standard eye mount (art #196), in headless Blender: the eye units smaller and nested in the head, the Body's
sockets re-sculpted to them (alien_lids_geom.SOCKET; the why is there).

    blender -b --factory-startup --python-exit-code 1 --python tools/blender/alien_socket.py -- \
        --character <mouths/build/alien_character.blend> --out <s/socket> [--socket JSON]

A stage of the S chain between alien_mouths.py and alien_ao.py, so the skin's AO, the texture UV, the detail sculpt
and its bake all see the new sockets. Per side, with C the socket's centre (S9's ball centre, the `Eye_<side>` node)
and r0 its ball's radius:
- every eye part of every design (ball, lids, wet strips) is scaled by `scale` about C and moved by
  alien_lids_geom.eye_offset (`sink` back, `inward` toward the midline); the `Eye_<side>` node moves with it, so the
  lids still hinge at the ball's centre and a new design authored in the socket's frame lands on the mount;
- the Body's skin follows: each vertex toward C' + scale (p - C) by socket_weight of its distance from C (in r0), then
  the soft rim (rim_bump) along the direction from C', on the socket's front half.
The mount is recorded as Body["prime_socket"] (JSON; alien_m6.py then scales no eye again). Checks: no face folds
over (a face normal turned past 90 degrees), the Mouth socket's skin and the crest's base unmoved (under 0.2 mm),
both designs' balls centred on their socket. Writes <out>/build/alien_character.blend, <out>/export/character.json
(the input's with `socket_m9`) and the mouths' atlases beside it; the next stage (alien_ao.py) exports the GLB.

alien_m6.py imports apply() for a variant grid on a finished kit (`--socket JSON`).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_lids_geom as LG  # noqa: E402

MARKER = "prime_socket"
DESIGNS = ("bored", "manic")
KEEP_MM = 0.2  # the Mouth socket's and the crest's skin may move at most this much


def log(*a):
    print("SOCKET", *a, flush=True)


def eye_parts(side: str) -> list:
    return [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("eye_") and o.name.endswith(f"_{side}")
            and any(o.name.startswith(f"eye_{d}_") for d in DESIGNS)]


def world_co(o) -> np.ndarray:
    n = len(o.data.vertices)
    co = np.empty(n * 3)
    o.data.vertices.foreach_get("co", co)
    m = np.array(o.matrix_world)
    co = co.reshape(-1, 3)
    return co @ m[:3, :3].T + m[:3, 3]


def set_world_co(o, w: np.ndarray):
    m = np.array(o.matrix_world.inverted())
    o.data.vertices.foreach_set("co", (w @ m[:3, :3].T + m[:3, 3]).ravel())
    o.data.update()


def face_normals(co: np.ndarray, tris: np.ndarray) -> np.ndarray:
    a, b, c = co[tris[:, 0]], co[tris[:, 1]], co[tris[:, 2]]
    n = np.cross(b - a, c - a)
    return n / np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]


def apply(spec: dict) -> dict:
    """The mount on the open file (the armature at REST for the call): returns the report; refuses a second mount."""
    s = LG.set_socket(spec)
    body = bpy.data.objects["Body"]
    if MARKER in body.keys():
        raise SystemExit(f"Body already carries a mount: {body[MARKER]}")
    me = body.data
    co0 = world_co(body)
    me.calc_loop_triangles()
    tris = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("vertices", tris)
    tris = tris.reshape(-1, 3)
    n0 = face_normals(co0, tris)
    disp = np.zeros_like(co0)
    k = s["scale"]
    sides = {}
    for side, sx in (("L", 1.0), ("R", -1.0)):
        sock = bpy.data.objects[f"Eye_{side}"]
        c = np.array(sock.matrix_world.translation)
        fwd = np.array((sock.matrix_world.to_3x3() @ Vector((0.0, -1.0, 0.0))).normalized())
        r0s = []
        for d in DESIGNS:
            ball = bpy.data.objects[f"eye_{d}_ball_{side}"]
            w = world_co(ball)
            if np.linalg.norm(np.array(ball.matrix_world.translation) - c) > 1e-4:
                raise SystemExit(f"{ball.name}: not centred on {sock.name}")
            r0s.append(float(np.linalg.norm(w - c, axis=1).max()))
        r0 = r0s[0]
        if abs(r0s[1] - r0) > 0.03 * r0:
            raise SystemExit(f"the designs' balls differ on {side}: {r0s}")
        off = np.array(LG.eye_offset(tuple(fwd), sx, s["sink"], s["inward"]))
        dist = np.linalg.norm(co0 - c, axis=1) / r0
        wt = LG.socket_weight(dist, s["inner"], s["outer"])
        disp += wt[:, None] * (c + off + k * (co0 - c) - co0)
        lid_r = max(float(np.linalg.norm(world_co(bpy.data.objects[f"eye_{d}_lid_upper_{side}"]) - c, axis=1).max())
                    for d in DESIGNS)
        sides[side] = {"c": c, "fwd": fwd, "off": off, "r0": r0, "lid_r": lid_r}
    co1 = co0 + disp
    for side, v in sides.items():  # the soft rim round the smaller eye, on the socket's front half
        c1 = v["c"] + v["off"]
        q = co1 - c1
        ql = np.maximum(np.linalg.norm(q, axis=1), 1e-9)
        dd = ql / (k * v["lid_r"])
        front = LG.clamp01(((q @ v["fwd"]) / ql + 0.3) / 0.5)
        co1 = co1 + (q / ql[:, None]) * (s["rim"] * LG.rim_bump(dd, s["rim_at"], s["rim_w"]) * front)[:, None]
    n1 = face_normals(co1, tris)
    flip = (n0 * n1).sum(1) < 0.0
    # a fold inside a new ball (the bowl's floor, never seen) is reported; one on visible skin refuses the mount
    cen = co1[tris].mean(1)
    hidden = np.zeros(len(tris), dtype=bool)
    for v in sides.values():
        hidden |= np.linalg.norm(cen - (v["c"] + v["off"]), axis=1) < 0.98 * k * v["r0"]
    folds, folds_hidden = int((flip & ~hidden).sum()), int((flip & hidden).sum())
    moved = np.linalg.norm(co1 - co0, axis=1)
    keep = {}
    for name in ("Mouth", "Crest"):
        p = np.array(bpy.data.objects[name].matrix_world.translation)
        near = np.linalg.norm(co0 - p, axis=1) < 0.03
        keep[name] = round(float(moved[near].max() * 1000) if near.any() else 0.0, 3)
    if folds or max(keep.values()) > KEEP_MM:
        where = cen[flip & ~hidden][:4].round(4).tolist()
        raise SystemExit(f"the mount folds {folds} visible faces (at {where}) or moves the mouth/crest skin {keep} mm")
    set_world_co(body, co1)
    rep_light = raise_light(me, co1, sides, k, s)
    # the eye parts: world targets first, then the nodes moved, then the meshes written in their new frames
    rep = {"socket": s, "folds": folds, "folds_inside_ball": folds_hidden, "keep_mm": keep,
           "moved_max_mm": round(float(moved.max() * 1000), 2), "moved_verts": int((moved > 1e-4).sum()),
           "light": rep_light}
    for side, v in sides.items():
        c, off = v["c"], v["off"]
        parts = eye_parts(side)
        targets = {o.name: c + off + k * (world_co(o) - c) for o in parts}
        sock = bpy.data.objects[f"Eye_{side}"]
        mw = sock.matrix_world.copy()
        mw.translation = Vector(tuple(c + off))
        sock.matrix_world = mw
        bpy.context.view_layer.update()
        for o in parts:
            set_world_co(o, targets[o.name])
        c1 = c + off
        for d in DESIGNS:
            ball = bpy.data.objects[f"eye_{d}_ball_{side}"]
            if np.linalg.norm(np.array(ball.matrix_world.translation) - c1) > 1e-5:
                raise SystemExit(f"{ball.name}: did not move with {sock.name}")
        rep[side] = {"centre_before": c.round(4).tolist(), "centre": c1.round(4).tolist(), "offset_mm":
                     (off * 1000).round(2).tolist(), "ball_r": round(k * v["r0"], 4), "lid_r": round(k * v["lid_r"], 4)}
    rep.update(measure(body, sides, k))
    body[MARKER] = json.dumps(s, sort_keys=True)
    log("mount", json.dumps(rep))
    return rep


def raise_light(me, co1: np.ndarray, sides: dict, k: float, s: dict) -> dict:
    """M9b: the `masks` light (u, per loop) raised round each mounted eye to alien_lids_geom.eye_light (never
    lowered), so the skin round the eye is the pale face's and no crown teal sits on the socket's slope."""
    if not s["light_out"]:
        return {"raised_verts": 0}
    me.update()
    nr = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("normal", nr)
    nr = nr.reshape(-1, 3) @ np.linalg.inv(np.array(bpy.data.objects["Body"].matrix_world)[:3, :3])
    nr /= np.maximum(np.linalg.norm(nr, axis=1, keepdims=True), 1e-12)
    floor = np.zeros(len(co1))
    for v in sides.values():
        q = co1 - (v["c"] + v["off"])
        ql = np.maximum(np.linalg.norm(q, axis=1), 1e-9)
        floor = np.maximum(floor, LG.eye_light(ql / (k * v["r0"]), nr @ v["fwd"], s["light_in"], s["light_out"]))
    uv = np.empty(len(me.loops) * 2)
    me.uv_layers["masks"].data.foreach_get("uv", uv)
    lv = np.empty(len(me.loops), dtype=np.int64)
    me.loops.foreach_get("vertex_index", lv)
    u0 = uv[0::2].copy()
    uv[0::2] = np.maximum(u0, floor[lv])
    me.uv_layers["masks"].data.foreach_set("uv", uv)
    me.update()
    up = uv[0::2] - u0
    return {"raised_verts": int(len(np.unique(lv[up > 0.01]))), "raised_mean": round(float(up[up > 0.01].mean()), 3)
            if (up > 0.01).any() else 0.0}


def measure(body, sides: dict, k: float) -> dict:
    """The front silhouette (the eye's outer x against the head's at the eye's height) and the ball's front against
    the face beside it (a front ray on the skin 1.25 lid radii out, toward the midline and above)."""
    from mathutils.bvhtree import BVHTree
    co = world_co(body)
    tree = BVHTree.FromPolygons([Vector(p) for p in co], [list(p.vertices) for p in body.data.polygons])
    out = {}
    for side, v in sides.items():
        c1 = v["c"] + v["off"]
        band = co[np.abs(co[:, 2] - c1[2]) < 0.004]
        head_x = float(np.abs(band[:, 0]).max())
        lid_x = max(float(np.abs(world_co(bpy.data.objects[f"eye_{d}_lid_upper_{side}"])[:, 0]).max()) for d in DESIGNS)
        ball_front = float(c1[1] - k * v["r0"])
        face = {}
        for name, dx, dz in (("inner", -np.sign(c1[0]), 0.0), ("above", 0.0, 1.0), ("below", 0.0, -1.0)):
            o = Vector((c1[0] + dx * 1.25 * k * v["lid_r"], -0.5, c1[2] + dz * 1.25 * k * v["lid_r"]))
            hit = tree.ray_cast(o, Vector((0, 1, 0)), 1.0)
            face[name] = round((hit[0].y - ball_front) * 1000, 1) if hit[0] is not None else None
        out[f"measure_{side}"] = {"head_half_w": round(head_x, 4), "lid_outer_x": round(lid_x, 4),
                                  "inside_mm": round((head_x - lid_x) * 1000, 1), "ball_front_y": round(ball_front, 4),
                                  "face_behind_ball_front_mm": face}
    return out


def args():
    p = argparse.ArgumentParser()
    p.add_argument("--character", required=True, help="alien_mouths.py's build/alien_character.blend")
    p.add_argument("--out", required=True)
    p.add_argument("--socket", default="", help="JSON over alien_lids_geom.SOCKET (a grid's variant)")
    return p.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])


def main():
    a = args()
    out = Path(a.out)
    (out / "build").mkdir(parents=True, exist_ok=True)
    (out / "export").mkdir(parents=True, exist_ok=True)
    src = Path(a.character).parent.parent / "export"
    bpy.ops.wm.open_mainfile(filepath=a.character)
    body = bpy.data.objects["Body"]
    arm = body.find_armature()
    if arm is not None:
        arm.data.pose_position = "REST"
    bpy.context.view_layer.update()
    rep = apply(json.loads(a.socket) if a.socket else {})
    if arm is not None:
        arm.data.pose_position = "POSE"
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "build" / "alien_character.blend"))
    cj = json.loads((src / "character.json").read_text(encoding="utf-8"))
    cj["socket_m9"] = rep
    (out / "export" / "character.json").write_text(json.dumps(cj, indent=1), encoding="utf-8", newline="\n")
    for f in src.iterdir():
        if f.suffix == ".png":
            shutil.copy2(f, out / "export" / f.name)
    (out / "build_report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8", newline="\n")
    log("SAVED", out / "build" / "alien_character.blend")


if __name__ == "__main__":
    main()
