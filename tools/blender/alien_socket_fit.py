"""M15 (art #196, brief UPDATE 26), in headless Blender: the eye socket rebuilt for the 80 % eye unit
(alien_fit_geom.py: why, and how it differs from M9's rejected mount).

    blender -b --factory-startup --python-exit-code 1 --python tools/blender/alien_socket_fit.py -- \
        (--character <mouths/build/alien_character.blend> | --kit <a kit's export folder>) --out <dir> [--fit JSON]

- `--character`: a stage of the S chain between alien_mouths.py and alien_ao.py, so the skin's AO, the texture UV,
  the detail sculpt (its lid folds take the new ball) and the bake all see the new sockets. Writes
  <out>/build/alien_character.blend, <out>/export/character.json (the input's with `socket_m15`) and the input's PNGs.
- `--kit`: the same on a finished kit (M5's export, S9's eyes), for the depth grid: <out>/alien_character.blend and the
  kit's other files. The skin's maps stay the input's (the UVs ride with the vertices), so only the shape is new.

Per side every eye part of every design (balls, lids, wet strips) is scaled by `eye_scale` about the old centre,
turned by `toe` and moved (alien_fit_geom.place); the `Eye_<side>` node takes the new centre and turn, so the lids
hinge at the new centre and look straight ahead. The Body's skin is filled, cut and filleted (alien_fit_geom). The
mount is recorded as Body["prime_socket"] (alien_socket.MARKER, JSON with "route": "m15"): alien_m6.py then scales no
eye again and builds the slim lids (alien_lids_geom.LIDS) the socket was cut for. Checks (the run refuses): no folded
crease on the changed skin, the Mouth's and the Crest's skin unmoved (keep_mm), every ball centred on its node.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_fit_geom as F  # noqa: E402
import alien_lids_geom as LG  # noqa: E402
from alien_face import EYE_AIM_CONVERGE  # noqa: E402
from alien_parts import EYES, LID_BEAD  # noqa: E402

MARKER = "prime_socket"  # alien_socket.MARKER: alien_m6.py reads it as "the eyes are sized and placed"
DESIGNS = ("bored", "manic")


def log(*a):
    print("M15", *a, flush=True)


def world_co(o) -> np.ndarray:
    n = len(o.data.vertices)
    co = np.empty(n * 3)
    o.data.vertices.foreach_get("co", co)
    m = np.array(o.matrix_world)
    return co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]


def set_world_co(o, w: np.ndarray):
    m = np.array(o.matrix_world.inverted())
    o.data.vertices.foreach_set("co", (w @ m[:3, :3].T + m[:3, 3]).ravel())
    o.data.update()


def unit_meshes(side: str) -> list:
    return [o for o in bpy.data.objects if o.type == "MESH" and o.name.endswith(f"_{side}")
            and any(o.name.startswith(f"eye_{d}_") for d in DESIGNS)]


def set_body(body, co_new: np.ndarray, co_old: np.ndarray):
    """The Body's rest positions (and every shape key by the same move)."""
    m = np.array(body.matrix_world.inverted())
    disp_local = (co_new - co_old) @ m[:3, :3].T
    sk = body.data.shape_keys
    if sk is not None:
        for kb in sk.key_blocks:
            a = np.empty(len(kb.data) * 3)
            kb.data.foreach_get("co", a)
            kb.data.foreach_set("co", (a.reshape(-1, 3) + disp_local).ravel())
    set_world_co(body, co_new)


def apply(spec: dict, debug: bool = False) -> dict:
    """The fit on the open file (the armature at REST): returns the report; refuses a second mount."""
    s = F.set_fit(spec)
    body = bpy.data.objects["Body"]
    if MARKER in body.keys():
        raise SystemExit(f"Body already carries a mount: {body[MARKER]}")
    me = body.data
    co0 = world_co(body)
    n = len(co0)
    edges = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get("vertices", edges)
    edges = edges.reshape(-1, 2)
    me.calc_loop_triangles()
    tris = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("vertices", tris)
    tris = tris.reshape(-1, 3)
    lap = F.Lap(n, edges)
    k = s["eye_scale"]
    reach = F.lid_reach(EYES, LID_BEAD, LG.LIDS)
    keep_pts = {nm: np.array(bpy.data.objects[nm].matrix_world.translation) for nm in ("Mouth", "Crest")}
    near_keep = np.zeros(n, dtype=bool)
    for p in keep_pts.values():
        near_keep |= np.linalg.norm(co0 - p, axis=1) < 0.035
    sides, free = {}, np.zeros(n, dtype=bool)
    got = {}
    for side in ("L", "R"):
        sock = bpy.data.objects[f"Eye_{side}"]
        c = np.array(sock.matrix_world.translation)
        fwd = np.array((sock.matrix_world.to_3x3() @ Vector((0.0, -1.0, 0.0))).normalized())
        got[side] = (c, fwd, float(np.linalg.norm(world_co(bpy.data.objects[f"eye_bored_ball_{side}"]) - c,
                                                  axis=1).max()))
    # M15b (PR #253 review, minor 6): S2a's two sockets differ by about 0.3 mm and a few hundredths of a degree, so the
    # two cuts came out unlike (one crescent shelf); the new mount is placed from their mirrored mean, so both sockets'
    # centres, axes and spheres are exact mirrors (the units still move from their own centres)
    mir = np.array((-1.0, 1.0, 1.0))
    c_m = (got["L"][0] + got["R"][0] * mir) / 2.0
    f_m = (got["L"][1] + got["R"][1] * mir) / 2.0
    f_m /= np.linalg.norm(f_m)
    r_m = (got["L"][2] + got["R"][2]) / 2.0
    for side, sx in (("L", 1.0), ("R", -1.0)):
        c, fwd, _r = got[side]
        r0 = r_m
        c1, _rz, f1 = F.place(c_m if sx > 0 else c_m * mir, f_m if sx > 0 else f_m * mir, sx, s)
        rz = F.place(c, fwd, sx, s)[1]  # the unit's own turn (its own axis straightened)
        R = k * r0 * reach + s["gap"]
        ex, ey = F.frame(f1, sx)
        own = co0[:, 0] * sx > 0.010
        fr = own & ~near_keep & (co0[:, 2] > c[2] - s["free_below"]) & ((np.linalg.norm(co0 - c, axis=1) < s["free_r"] * r0)
                                 | (np.linalg.norm(co0 - c1, axis=1) < R + s["free_margin"]))
        free |= fr
        sides[side] = {"c": c, "fwd": fwd, "c1": c1, "rz": rz, "a": f1, "ex": ex, "ey": ey, "r0": r0, "R": R,
                       "own": own, "x_sign": sx}
    P = F.fair_fill(co0, lap, free, s["fill_iters"])
    rep = {"fit": s, "lid_reach_r": round(reach, 4), "free_verts": int(free.sum()),
           "fill_converged": {k: [it, f"{g:.1e}"] for k, (it, g) in F.LAST.items()}}
    region_all = lap.neighbours(lap.neighbours(free))
    for side, v in sides.items():
        region = region_all & v["own"]
        tc = F.crossing_angles(P, edges, region, v["c1"], v["a"], v["ex"], v["ey"], v["R"])
        ins = region & F.opening(P, v["c1"], v["a"], v["ex"], v["ey"], tc, v["R"])
        if (ins & ~free).any():
            raise SystemExit(f"fit {side}: the socket's sphere reaches {int((ins & ~free).sum())} fixed vertices; "
                             "raise free_margin")
        band = free & v["own"] & F.rim_band(P, v["c1"], v["a"], v["ex"], v["ey"], tc, s["fillet"], v["R"])
        P[ins] = F.bowl_map(P[ins], v["c1"], v["a"], v["ex"], v["ey"], v["R"], tc)
        P = F.fillet(P, lap, band, v["c1"], v["R"], s["fillet_passes"])
        v["rho_c_mm"] = [round(float(np.degrees(tc.min())), 1), round(float(np.degrees(tc.max())), 1)]
        v["inside_verts"] = int(ins.sum())
    moved = np.linalg.norm(P - co0, axis=1)
    keep = {nm: round(float(moved[np.linalg.norm(co0 - p, axis=1) < 0.03].max() * 1000), 3)
            for nm, p in keep_pts.items()}
    changed_tri = (moved[tris] > 1e-5).any(1)
    fp = F.folds(P, tris, changed_tri)
    f0 = F.folds(co0, tris, changed_tri)  # creases the input already had there (the cage's own) are not the fit's
    if len(f0) and len(fp):
        fp = fp[np.linalg.norm(fp[:, None, :] - f0[None, :, :], axis=2).min(1) > 0.004]
    rep["folds_before"] = int(len(f0))
    hid = np.zeros(len(fp), dtype=bool)
    for v in sides.values():
        hid |= F.hidden(fp, v["c1"], v["a"], k * v["r0"], v["R"])
    nf, nh = int((~hid).sum()), int(hid.sum())
    rep["folds_where"] = [[round(float((p_ - sides["L" if p_[0] > 0 else "R"]["c1"]) @ sides["L" if p_[0] > 0 else "R"][ax]) * 1000, 1)
                           for ax in ("ex", "ey", "a")] for p_ in fp[~hid][:12]]
    if (nf or max(keep.values()) > s["keep_mm"]) and not debug:
        raise SystemExit(f"fit: {nf} folded edges on the seen skin (at {rep['folds_where']} mm, ex/ey/a), or the "
                         f"mouth/crest skin moved {keep} mm")
    set_body(body, P, co0)
    rep.update({"folds": nf, "folds_hidden": nh, "keep_mm": keep, "moved_max_mm": round(float(moved.max() * 1000), 2),
                "moved_verts": int((moved > 1e-4).sum())})
    # the eye units: world targets first, then the node placed, then the meshes written in their new frames
    for side, v in sides.items():
        c, c1, rz = v["c"], v["c1"], v["rz"]
        parts = unit_meshes(side)
        targets = {o.name: c1 + (k * (world_co(o) - c)) @ rz.T for o in parts}
        sock = bpy.data.objects[f"Eye_{side}"]
        mw = np.array(sock.matrix_world)
        new = np.eye(4)
        new[:3, :3] = rz @ mw[:3, :3]
        new[:3, 3] = c1
        sock.matrix_world = Matrix(new.tolist())
        bpy.context.view_layer.update()
        for o in parts:
            set_world_co(o, targets[o.name])
        aim = {}
        for d in DESIGNS:
            ball = bpy.data.objects[f"eye_{d}_ball_{side}"]
            if np.linalg.norm(np.array(ball.matrix_world.translation) - c1) > 1e-5:
                raise SystemExit(f"{ball.name}: did not move with {sock.name}")
            aim[d] = rest_aim(ball, sock, side)
        v["aim"] = aim
        rep[side] = {"centre_before": c.round(4).tolist(), "centre": c1.round(4).tolist(),
                     "move_mm": ((c1 - c) * 1000).round(2).tolist(), "toe_deg": round(float(np.degrees(
                         F.toe_angle(tuple(v["fwd"]), s["toe"]))), 2), "ball_r": round(k * v["r0"], 4),
                     "socket_R": round(v["R"], 4), "opening_deg": v["rho_c_mm"], "inside_verts": v["inside_verts"],
                     "ball_aim_in_deg": v["aim"]}
    rep.update(measure(body, sides, k))
    body[MARKER] = json.dumps({"route": "m15", **s}, sort_keys=True)
    log("fit", json.dumps(rep))
    return rep


def _in_deg(ball, sock, side: str) -> tuple[float, float]:
    """(the ball's inward turn against its socket's forward, the socket's own outward look), degrees, about world up."""
    sx = 1.0 if side == "L" else -1.0
    fs = sock.matrix_world.to_3x3() @ Vector((0.0, -1.0, 0.0))
    fb = ball.matrix_world.to_3x3() @ Vector((0.0, -1.0, 0.0))
    splay = math.degrees(math.atan2(sx * fs.x, -fs.y))
    return splay - math.degrees(math.atan2(sx * fb.x, -fb.y)), splay


def rest_aim(ball, sock, side: str) -> list:
    """M15b (PR #253 review, major 1): the ball's turn in the GLB's rest. The assembler turned each ball EYE_AIM_IN in
    against S2a's sockets (8 degrees outward); the fit straightens the unit and kept that turn, so Blender and three.js
    showed the eyes crossed. The ball (its iris on its own forward, a sphere about its node) is turned about its up
    axis to EYE_AIM_CONVERGE plus the unit's remaining outward look, what alien.gd sets (AIM_CONVERGE_DEG +
    splay_deg). Returns [before, after] in degrees."""
    before, splay = _in_deg(ball, sock, side)
    want = EYE_AIM_CONVERGE + splay
    for _ in range(2):  # the second pass only trims a tilt of the up axis
        cur, _s = _in_deg(ball, sock, side)
        turn = math.radians(cur - want) * (1.0 if side == "L" else -1.0)
        ball.matrix_world = ball.matrix_world @ Matrix.Rotation(turn, 4, "Z")
        bpy.context.view_layer.update()
    after, _s = _in_deg(ball, sock, side)
    if abs(after - want) > 0.05:
        raise SystemExit(f"{ball.name}: rest aim {after:.2f} degrees, wanted {want:.2f}")
    return [round(before, 2), round(after, 2)]


def measure(body, sides: dict, k: float) -> dict:
    """The front silhouette (the lids' outer x against the head's at the eye's height, past the socket) and the
    profile (the ball's front against the face's midline at the eye's height)."""
    co = world_co(body)
    out = {}
    for side, v in sides.items():
        c1 = v["c1"]
        lid = np.concatenate([world_co(bpy.data.objects[f"eye_{d}_lid_upper_{side}"]) for d in DESIGNS])
        lid_x = float(np.abs(lid[:, 0]).max())
        band = co[(np.abs(co[:, 2] - c1[2]) < 0.004) & (co[:, 1] > c1[1])]
        head_x = float(np.abs(band[:, 0]).max())
        mid = co[(np.abs(co[:, 2] - c1[2]) < 0.004) & (np.abs(co[:, 0]) < 0.004)]
        ball_front = float(c1[1] - k * v["r0"])
        out[f"measure_{side}"] = {"head_half_w_mm": round(head_x * 1000, 1), "lid_outer_x_mm": round(lid_x * 1000, 1),
                                  "inside_front_mm": round((head_x - lid_x) * 1000, 1),
                                  "ball_front_y": round(ball_front, 4),
                                  "behind_midline_mm": round((ball_front - float(mid[:, 1].min())) * 1000, 1)}
    return out


def args():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--character", help="alien_mouths.py's build/alien_character.blend (the chain's stage)")
    g.add_argument("--kit", help="a finished kit's folder (alien_character.blend, character.json): the depth grid")
    p.add_argument("--out", required=True)
    p.add_argument("--fit", default="", help="JSON over alien_fit_geom.FIT")
    p.add_argument("--debug", action="store_true", help="save even with folds (a look at them; never a kit)")
    return p.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])


def main():
    a = args()
    out = Path(a.out)
    if a.kit:
        src = Path(a.kit)
        out.mkdir(parents=True, exist_ok=True)
        if src.resolve() == out.resolve():
            raise SystemExit("fit: the output must not be the input kit")
        blend = src / "alien_character.blend"
    else:
        src = Path(a.character).parent.parent / "export"
        (out / "build").mkdir(parents=True, exist_ok=True)
        (out / "export").mkdir(parents=True, exist_ok=True)
        blend = Path(a.character)
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    body = bpy.data.objects["Body"]
    arm = body.find_armature()
    if arm is not None:
        arm.data.pose_position = "REST"
    bpy.context.view_layer.update()
    rep = apply(json.loads(a.fit) if a.fit else {}, a.debug)
    if arm is not None:
        arm.data.pose_position = "POSE"
    bpy.context.view_layer.update()
    target = out / "alien_character.blend" if a.kit else out / "build" / "alien_character.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(target))
    cj = json.loads((src / "character.json").read_text(encoding="utf-8"))
    cj["socket_m15"] = rep
    exp = out if a.kit else out / "export"
    (exp / "character.json").write_text(json.dumps(cj, indent=1), encoding="utf-8", newline="\n")
    for f in src.iterdir():
        if f.is_file() and f.suffix == ".png":
            shutil.copy2(f, exp / f.name)
    (out / "build_report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8", newline="\n")
    log("SAVED", target)


if __name__ == "__main__":
    main()
