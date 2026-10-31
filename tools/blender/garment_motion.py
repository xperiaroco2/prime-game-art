"""Gate 2's motion numbers (art #196; docs/clothes.md, "Gate 2"): opens a dressed character's .blend and, per clip
and frame, measures the garment against its own rest pose. garment_gate2.py writes the config (parts in metres from
the spec's [gate2] section, resolved on the build's measures) and reads the result.

- The pieces: the garment's connected pieces, each a 'strap' (it goes over the shoulder: over classify.over_z with
  points in front and behind), 'hardware' (at most classify.hardware_max_verts vertices: buckles, buttons) or
  'panel'. A part is the vertices of the named classes inside its box (|x|, y and z ranges).
- Slip at a join: each vertex of the moving part within reach of the other part's faces is tied at rest to its
  nearest point (face, barycentric); per frame its offset from that point, turned back by the other part's best-fit
  rotation, less its rest offset (clothes_bibmove_geom.slip), mm.
- Flatness: the part's largest distance from its rest shape moved rigidly onto it (Kabsch), mm: change from rest,
  so a bend the spec draws (lean B's) is allowed and only a new bend counts.
- Stretch: the part's edges' |length / rest - 1|, the largest and the 95th percentile, %.

blender -b --python garment_motion.py -- --config CONFIG.json --out OUT.json
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
import clothes_bibmove_geom as B  # noqa: E402
import garment_gate2_geom as G  # noqa: E402

PREFIX = "CharacterArmature|"


def say(*a) -> None:
    print("GARMENT_MOTION", *a, flush=True)


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


def select(co, cls_of_vert, part: dict) -> np.ndarray:
    ok = np.isin(cls_of_vert, part["classes"])
    ax = np.abs(co[:, 0])
    ok &= (ax >= part["x_abs"][0]) & (ax <= part["x_abs"][1])
    ok &= (co[:, 1] >= part["y"][0]) & (co[:, 1] <= part["y"][1])
    ok &= (co[:, 2] >= part["z"][0]) & (co[:, 2] <= part["z"][1])
    return np.nonzero(ok)[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    bpy.ops.wm.open_mainfile(filepath=str(Path(cfg["blend"]).resolve()))
    arm = bpy.data.objects[cfg.get("armature", "CharacterArmature")]
    gar = bpy.data.objects[cfg.get("garment", "garment")]
    arm.animation_data_create()
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.matrix_basis.identity()
    bpy.context.view_layer.update()
    co0 = world(gar)
    polys = [list(p.vertices) for p in gar.data.polygons]
    comp = np.array(B.components(len(co0), polys))
    ncomp = int(comp.max()) + 1
    sizes = np.bincount(comp, minlength=ncomp).tolist()
    spans = []
    for k in range(ncomp):
        p = co0[comp == k]
        spans.append((float(p[:, 2].max()), float(p[:, 1].min()), float(p[:, 1].max()), 0.0))
    cl = cfg["classify"]
    classes = G.classify(sizes, spans, cl["over_z"], cl["hardware_max_verts"])
    cls_of_vert = np.array([classes[k] for k in comp])
    rep = {"blend": cfg["blend"], "pieces": [
        {"verts": n, "class": c, "z_max": round(s[0], 4), "y": [round(s[1], 4), round(s[2], 4)]}
        for n, c, s in zip(sizes, classes, spans)], "parts": {}, "clips": {}}
    parts = {name: select(co0, cls_of_vert, p) for name, p in cfg["parts"].items()}
    tri_all = [t for p in polys for t in ([p] if len(p) == 3 else [[p[0], p[i], p[i + 1]] for i in range(1, len(p) - 1)])]
    edges = {}
    for name, ids in parts.items():
        s = set(ids.tolist())
        e = {(min(a, b), max(a, b)) for p in polys for a, b in zip(p, p[1:] + p[:1]) if a in s and b in s}
        edges[name] = np.array(sorted(e), dtype=int).reshape(-1, 2)
        rep["parts"][name] = {"verts": len(ids), "edges": len(e),
                              "z_cm": [round(float(co0[ids, 2].min()) * 100, 2), round(float(co0[ids, 2].max()) * 100, 2)]
                              if len(ids) else None}
    ties = {}
    for j in cfg["joins"]:
        on = set(parts[j["on"]].tolist())
        tris = [t for t in tri_all if all(k in on for k in t)]
        pairs = []
        if tris:
            tree = BVHTree.FromPolygons([tuple(c) for c in co0], tris)
            for i in parts[j["moving"]]:
                loc, _n, fi, _d = tree.find_nearest(co0[i], j["reach_m"])
                if loc is not None:
                    ids = tris[fi]
                    pairs.append((int(i), ids, list(poly_3d_calc([co0[k] for k in ids], loc))))
        ties[j["name"]] = pairs
        rep["parts"]["join: " + j["name"]] = {"tied": len(pairs)}
    say("pieces", json.dumps(rep["pieces"]))
    say("parts", json.dumps(rep["parts"]))
    sc = bpy.context.scene
    for clip in cfg["clips"]:
        act = action_for(clip)
        if act is None:
            rep["clips"][clip] = None
            continue
        arm.animation_data.action = act
        f0, f1 = (int(round(x)) for x in act.frame_range)
        res = {"frames": 0, "slip_mm": {}, "flat_mm": {}, "stretch_pct": {}, "stretch_p95_pct": {}}
        for f in range(f0, max(f0 + 1, f1 + 1), max(1, cfg.get("every", 1))):
            sc.frame_set(f)
            co = world(gar)
            res["frames"] += 1
            fits = {}
            for name in {j["on"] for j in cfg["joins"]} | {fl["part"] for fl in cfg["flat"]}:
                ids = parts[name]
                if len(ids) >= 3:
                    fits[name] = B.rigid_fit(co0[ids], co[ids])
            for j in cfg["joins"]:
                pairs, fit = ties[j["name"]], fits.get(j["on"])
                v = 1000 * B.slip(co0, co, pairs, fit[0]) if pairs and fit else None
                old = res["slip_mm"].get(j["name"])
                res["slip_mm"][j["name"]] = v if old is None else max(old, v)
            for fl in cfg["flat"]:
                fit = fits.get(fl["part"])
                v = 1000 * float(fit[2].max()) if fit else None
                old = res["flat_mm"].get(fl["part"])
                res["flat_mm"][fl["part"]] = v if old is None else max(old, v)
            for st in cfg["stretch"]:
                mx, p95 = G.stretch(co0, co, edges[st["part"]])
                res["stretch_pct"][st["part"]] = max(res["stretch_pct"].get(st["part"], 0.0), mx)
                res["stretch_p95_pct"][st["part"]] = max(res["stretch_p95_pct"].get(st["part"], 0.0), p95)
        for k in ("slip_mm", "flat_mm", "stretch_pct", "stretch_p95_pct"):
            res[k] = {n: (None if v is None else round(v, 2)) for n, v in res[k].items()}
        rep["clips"][clip] = res
        say("clip", clip, json.dumps(res))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(rep, indent=1), encoding="utf-8", newline="\n")
    say("wrote", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
