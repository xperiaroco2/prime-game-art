"""M2m: does her front bib move with its straps? Opens a dressed character's .blend and, per clip and frame, measures
(clothes_bibmove_geom has the plain maths):
- the bib's bend: its vertices' largest distance from the rest bib moved rigidly onto them (best fit), mm; a flat,
  stiff panel stays near 0, a fold or a crease shows;
- the strap-bib slip: each strap or buckle vertex over the bib is tied at rest to its nearest bib point (face and
  barycentric weights); per frame its offset from that point, taken back into the bib's rest frame by the best-fit
  rotation, less its rest offset: how far the strap slides on the plate, mm;
- the bib top's and the straps' motion over the clip (the range of their mean point relative to the Hips bone), mm:
  the straps moving while the plate stays is the bug this measures.
At rest it also reports the heights the concept is measured against: the bib's top, the shoulders' top, the armpit,
the neck's base, the waistband's buttons, the bones.

blender -b --python clothes_bibmove.py -- --blend CHAR.blend --out OUT.json [--clips Idle,Walk,...] [--bib-hw 0.09]
    [--z-lo 1.03] [--every 1]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils.bvhtree import BVHTree
from mathutils.interpolate import poly_3d_calc

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clothes_bibmove_geom as G  # noqa: E402

CLIPS = "Idle,Walk,Jog_Fwd,Sprint_Fwd,Strafe_Left,Crouch_Fwd,Jump_Start,Jump_Air,Talk_Upper"
PREFIX = "CharacterArmature|"


def say(*a) -> None:
    print("CLOTHES_BIBMOVE", *a, flush=True)


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
    ev.to_mesh_clear()
    m = np.array(o.matrix_world)
    return co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]


def heights(arm, body, gar_co, bib, comps_main) -> dict:
    """The rest heights the concept is measured against (world z, m)."""
    mw = np.array(arm.matrix_world)
    bones = {}
    for b in ("Hips", "Spine", "Chest", "UpperChest", "Neck", "LeftShoulder", "LeftUpperArm"):
        if b in arm.data.bones:
            h = mw[:3, :3] @ np.array(arm.data.bones[b].head_local) + mw[:3, 3]
            bones[b] = round(float(h[2]), 4)
    bco = np.array([body.matrix_world @ v.co for v in body.data.vertices])
    gname = {g.index: g.name for g in body.vertex_groups}
    wt = [{gname[g.group]: g.weight for g in v.groups if g.group in gname} for v in body.data.vertices]
    ax = np.abs(bco[:, 0])
    sh = bco[(ax > 0.10) & (ax < 0.14) & (np.abs(bco[:, 1]) < 0.06)]
    up = [k for k, w in enumerate(wt) if w.get("LeftUpperArm", 0) + w.get("RightUpperArm", 0) > 0.5 and ax[k] < 0.16]
    nk = [k for k, w in enumerate(wt) if w.get("Neck", 0) > 0.5 and bco[k, 1] < 0]
    top = gar_co[bib][np.abs(gar_co[bib, 0]) < 0.05]
    return {"bones": bones, "bib_top": round(float(top[:, 2].max()), 4),
            "shoulder_top": round(float(sh[:, 2].max()), 4) if len(sh) else None,
            "armpit": round(float(bco[up, 2].min()), 4) if up else None,
            "neck_base_front": round(float(bco[nk, 2].min()), 4) if nk else None}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--clips", default=CLIPS)
    ap.add_argument("--bib-hw", type=float, default=0.09, help="the bib's half width measured (m)")
    ap.add_argument("--z-lo", type=float, default=1.03, help="the bib measured from this height up (m)")
    ap.add_argument("--reach", type=float, default=0.025, help="a strap vertex this near the bib sits on it (m)")
    ap.add_argument("--every", type=int, default=1, help="every n-th frame")
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    bpy.ops.wm.open_mainfile(filepath=str(Path(args.blend).resolve()))
    arm = bpy.data.objects["CharacterArmature"]
    gar = bpy.data.objects["garment"]
    body = next(o for o in bpy.data.objects if o.type == "MESH" and o.name not in ("garment", "shoes", "top")
                and any(m.type == "ARMATURE" for m in o.modifiers) and len(o.data.vertices) > 5000)
    arm.animation_data_create()
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.matrix_basis.identity()
    bpy.context.view_layer.update()
    co0 = world(gar)
    polys = [list(p.vertices) for p in gar.data.polygons]
    comp = np.array(G.components(len(co0), polys))
    main_c = np.bincount(comp).argmax()
    bib, on = G.bib_and_straps(co0, comp == main_c, args.bib_hw, args.z_lo)
    bset = set(bib.tolist())
    tris = [p for p in polys if all(k in bset for k in p)]
    tree = BVHTree.FromPolygons([tuple(c) for c in co0], tris)
    pairs = []  # (strap vertex, bib vertex ids, barycentric weights)
    for i in on:
        loc, _n, fi, d = tree.find_nearest(co0[i], args.reach)
        if loc is None:
            continue
        ids = tris[fi]
        pairs.append((int(i), ids, list(poly_3d_calc([co0[k] for k in ids], loc))))
    top_ids = bib[co0[bib, 2] > co0[bib, 2].max() - 0.02]
    rep = {"blend": args.blend, "bib_verts": len(bib), "strap_verts_on_bib": len(pairs),
           "heights": heights(arm, body, co0, bib, None), "clips": {}}
    say("rest", json.dumps(rep["heights"]), "bib", len(bib), "pairs", len(pairs))
    hips = arm.pose.bones["Hips"]
    sc = bpy.context.scene
    for clip in args.clips.split(","):
        act = action_for(clip)
        if act is None:
            rep["clips"][clip] = None
            continue
        arm.animation_data.action = act
        f0, f1 = (int(round(x)) for x in act.frame_range)
        bend, slip, tops, straps_p = [], [], [], []
        for f in range(f0, max(f0 + 1, f1 + 1), max(1, args.every)):
            sc.frame_set(f)
            co = world(gar)
            r, t, res = G.rigid_fit(co0[bib], co[bib])
            bend.append(float(res.max()))
            slip.append(G.slip(co0, co, pairs, r) if pairs else 0.0)
            hm = np.array(arm.matrix_world @ hips.matrix)
            inv = np.linalg.inv(hm)
            tops.append((inv[:3, :3] @ co[top_ids].mean(0) + inv[:3, 3]))
            if pairs:
                straps_p.append(inv[:3, :3] @ co[[p[0] for p in pairs]].mean(0) + inv[:3, 3])
        rng = lambda ps: round(1000 * float(np.ptp(np.array(ps), axis=0).max()), 1) if ps else None
        rep["clips"][clip] = {"frames": len(bend), "bend_max_mm": round(1000 * max(bend), 2),
                              "slip_max_mm": round(1000 * max(slip), 2),
                              "bib_top_range_mm": rng(tops), "straps_range_mm": rng(straps_p)}
        say("clip", clip, json.dumps(rep["clips"][clip]))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(rep, indent=1), encoding="utf-8")
    say("wrote", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
