"""Gate 2's motion numbers (art #196; docs/clothes.md, "Gate 2"): opens a dressed character's .blend and, per clip
and frame, measures the garment against its own rest pose. garment_gate2.py writes the config (parts in metres from
the spec's [gate2] section, resolved on the build's measures) and reads the result.

- The pieces: the garment's connected pieces, each a 'strap' (it goes over the shoulder: over classify.over_z with
  points in front and behind), 'hardware' (at most classify.hardware_max_verts vertices: buckles, buttons) or
  'panel'. A part is the vertices of the named classes inside its box (|x|, y and z ranges).
- The reference: reference_clip's first frame (the spec's [gate2] reference_clip, the stand), else her rest; the
  parts are chosen at rest.
- A part may keep only pieces of a vertex count (piece_verts): the band's ring, not the yoke inside it.
- Slip at a join: each vertex of the moving part within reach of the other part's faces is tied at rest to its
  nearest point (face, barycentric); per frame its offset from that point, turned back by the other part's best-fit
  rotation, less its rest offset (clothes_bibmove_geom.slip), mm.
- Flatness: the part's largest distance from its rest shape moved rigidly onto it (Kabsch), mm: change from rest,
  so a bend the spec draws (lean B's) is allowed and only a new bend counts. A flat entry with fit = "smooth" (G3n)
  measures folds instead: the largest distance from a smooth fit of the part's own motion (a polynomial of degree deg,
  default 3, garment_gate2_geom.smooth_residual), so the part may bend with her trunk but not crease; the rigid
  value is kept beside it (flat_rigid_mm).
- Where (G3n): per vs_skin stretch the largest edge beyond her skin in the frame of the clip's worst p95 (its rest
  midpoint, cm, the frame and its %), stretch_at.
- Stretch: the part's edges' |length / rest - 1|, the largest and the 95th percentile, %. A stretch entry with
  vs_skin judges the stretch beyond her skin's at the same place in the same frame (garment_gate2_geom.skin_excess):
  each vertex of the part tied at the reference to its nearest point of her skin (cfg skin: the body and its hidden
  body_removed, the skin under the cloth), followed by its face and barycentric weights (G3e).
- Laps (G3f, the manager's option (a)): a plate's lower strip lies over a band and may slide on it, hidden. Per frame
  the strip is moved back into the band's reference frame (the band's rigid fit) and measured: the least overlap of
  its lowest row under the band's top (garment_gate2_geom.lap_overlap), the deepest any strip vertex goes inside the
  band's outer face (a ray from outside toward the band's axis) and the edge's largest gap off it, mm.

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

lift_key = G.lift_key

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


def select(co, cls_of_vert, part: dict, piece_n=None) -> np.ndarray:
    """The part's vertices: its classes inside its box; with piece_verts [lo, hi] only pieces of lo..hi vertices
    (the band's ring apart from the yoke inside it and the bib's foot over it)."""
    ok = np.isin(cls_of_vert, part["classes"])
    if part.get("piece_verts") is not None and piece_n is not None:
        lo, hi = part["piece_verts"]
        ok &= (piece_n >= lo) & (piece_n <= hi)
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
    rep = {"blend": cfg["blend"], "blend_sha256": G.file_sha256(cfg["blend"]), "pieces": [
        {"verts": n, "class": c, "z_max": round(s[0], 4), "y": [round(s[1], 4), round(s[2], 4)]}
        for n, c, s in zip(sizes, classes, spans)], "parts": {}, "clips": {}}
    piece_n = np.array(sizes)[comp]
    parts = {name: select(co0, cls_of_vert, p, piece_n) for name, p in cfg["parts"].items()}
    # the reference the motion is measured from: her rest (the T-pose) or a clip's first frame (the stand the game
    # shows: from the T-pose to arms down every panel and strap moves, which is no fault of the garment)
    ref, sc = co0, bpy.context.scene
    rc = cfg.get("reference_clip")
    if rc:
        act = action_for(rc)
        if act is None:
            raise SystemExit(f"no reference clip {rc}")
        arm.animation_data.action = act
        sc.frame_set(int(round(act.frame_range[0])))
        ref = world(gar)
        rep["reference"] = f"{rc} frame {int(round(act.frame_range[0]))}"
    else:
        rep["reference"] = "rest"
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
            tree = BVHTree.FromPolygons([tuple(c) for c in ref], tris)
            for i in parts[j["moving"]]:
                loc, _n, fi, _d = tree.find_nearest(ref[i], j["reach_m"])
                if loc is not None:
                    ids = tris[fi]
                    pairs.append((int(i), ids, list(poly_3d_calc([ref[k] for k in ids], loc))))
        ties[j["name"]] = pairs
        rep["parts"]["join: " + j["name"]] = {"tied": len(pairs)}
    # the laps (G3f): the band's top row and outer face at the reference, the strip's lowest row and its vertices
    # level with the band
    laps = {}
    for lp in cfg.get("laps", []):
        band, strip = parts[lp["on"]], parts[lp["plate"]]
        if len(band) < 3 or not len(strip):
            laps[lp["name"]] = None
            continue
        bz = co0[band, 2]
        top = band[bz >= bz.max() - 1e-4]
        sz = co0[strip, 2]
        edge = strip[sz <= sz.min() + 0.002]
        level = strip[(sz <= bz.max() + 1e-3) & (sz >= bz.min() - 1e-3)]
        on = set(band.tolist())
        tris = [t for t in tri_all if all(k in on for k in t)]
        laps[lp["name"]] = {"top": top, "edge": edge, "level": level, "band": band,
                            "tree": BVHTree.FromPolygons([tuple(c) for c in ref], tris),
                            "centre": ref[band].mean(0)}
        rep["parts"]["lap: " + lp["name"]] = {"band_top": len(top), "edge": len(edge), "level": len(level)}
    # her skin under the parts judged against it (vs_skin): each vertex's nearest skin point at the reference
    skin_parts = list(dict.fromkeys([st["part"] for st in cfg["stretch"] if st.get("vs_skin")] +
                                    [lf["part"] for lf in cfg.get("lifts", []) if not lf.get("on")]))   # G3j: lifts
    skin_objs = [bpy.data.objects[n] for n in cfg.get("skin", []) if n in bpy.data.objects] if skin_parts else []
    for o in skin_objs:
        o.hide_viewport = False
        o.hide_set(False)
    skin_tie, skin_polys = {}, []
    if skin_objs:
        off = 0
        for o in skin_objs:
            skin_polys += [[k + off for k in p.vertices] for p in o.data.polygons]
            off += len(o.data.vertices)
        skin_tris = [t for p in skin_polys for t in ([p] if len(p) == 3 else [[p[0], p[k], p[k + 1]] for k in range(1, len(p) - 1)])]
        bpy.context.view_layer.update()
        sref = np.concatenate([world(o) for o in skin_objs])
        stree = BVHTree.FromPolygons([tuple(c) for c in sref], skin_tris)
        for name in skin_parts:
            tie = {}
            for i in parts[name]:
                loc, _n, fi, _d = stree.find_nearest(ref[i], 0.2)
                if loc is not None:
                    ids = skin_tris[fi]
                    tie[int(i)] = (ids, list(poly_3d_calc([sref[k] for k in ids], loc)))
            skin_tie[name] = tie
            rep["parts"]["skin under: " + name] = {"tied": len(tie)}
    rep["skin"] = [o.name for o in skin_objs]

    # G3l: a lift off another part of the garment (on): each vertex tied to the nearest face of that part at the
    # garment's rest, where the build lays it on that part, within reach_mm, and judged since that rest, not since the
    # reference clip: the straps' back ends (Chest) over the back panel (Spine) lie 6-10 mm off it at rest and already
    # 29 mm in Idle's first frame (G3l B), so a lift since Idle would hide the stand's own gap; judged either way (sunk
    # under it or off it), as the size of the change
    on_tie = {}
    for lf in cfg.get("lifts", []):
        if not lf.get("on"):
            continue
        on = set(parts[lf["on"]].tolist())
        otris = [t for t in tri_all if all(k in on for k in t)]
        tie, near = {}, None
        if otris:
            otree = BVHTree.FromPolygons([tuple(c) for c in co0], otris)
            for i in parts[lf["part"]]:
                loc, _n, fi, d_ = otree.find_nearest(tuple(co0[i]))
                if loc is None:
                    continue
                near = d_ if near is None else min(near, d_)
                if d_ <= lf.get("reach_mm", 25.0) / 1000:
                    tie[int(i)] = (otris[fi], list(poly_3d_calc([co0[k] for k in otris[fi]], loc)))
        on_tie[lift_key(lf)] = tie
        rep["parts"]["lift: " + lift_key(lf)] = {"tied": len(tie), "of": len(parts[lf["part"]]), "faces": len(otris),
                                                 "nearest_mm": None if near is None else round(1000 * near, 1)}

    def skin_points(sco, name):
        out = {}
        for i, (ids, w) in skin_tie[name].items():
            out[i] = sum(sco[k] * x for k, x in zip(ids, w))
        return out
    say("pieces", json.dumps(rep["pieces"]))
    say("parts", json.dumps(rep["parts"]))
    for clip in cfg["clips"]:
        act = action_for(clip)
        if act is None:
            rep["clips"][clip] = None
            continue
        arm.animation_data.action = act
        f0, f1 = (int(round(x)) for x in act.frame_range)
        res = {"frames": 0, "slip_mm": {}, "flat_mm": {}, "stretch_pct": {}, "stretch_p95_pct": {},
               "skin_excess_pct": {}, "skin_excess_p95_pct": {}, "lap_mm": {}, "lap_through_mm": {}, "lap_gap_mm": {},
               "lift_mm": {}, "lift_at": {}, "flat_rigid_mm": {}, "stretch_at": {}}
        sc.frame_set(f0)
        sref0 = None
        for f in range(f0, max(f0 + 1, f1 + 1), max(1, cfg.get("every", 1))):
            sc.frame_set(f)
            co = world(gar)
            res["frames"] += 1
            fits = {}
            for name in {j["on"] for j in cfg["joins"]} | {fl["part"] for fl in cfg["flat"]}:
                ids = parts[name]
                if len(ids) >= 3:
                    fits[name] = B.rigid_fit(ref[ids], co[ids])
            for j in cfg["joins"]:
                pairs, fit = ties[j["name"]], fits.get(j["on"])
                v = 1000 * B.slip(ref, co, pairs, fit[0]) if pairs and fit else None
                old = res["slip_mm"].get(j["name"])
                res["slip_mm"][j["name"]] = v if old is None else max(old, v)
            for name, L in laps.items():
                if L is None:
                    continue
                r_, t_, _res = B.rigid_fit(ref[L["band"]], co[L["band"]])
                ov = G.lap_overlap(ref[L["top"]], G.to_frame(r_, t_, co[L["edge"]]))
                deep, gap = 0.0, None
                c = L["centre"]
                edge = set(L["edge"].tolist())
                for i, p in zip(L["level"].tolist(), G.to_frame(r_, t_, co[L["level"]])):
                    d = np.array([p[0] - c[0], p[1] - c[1], 0.0])
                    if np.linalg.norm(d) < 1e-6:
                        continue
                    d /= np.linalg.norm(d)
                    hit = L["tree"].ray_cast(tuple(p + 0.3 * d), tuple(-d), 0.6)[0]
                    if hit is None:
                        continue
                    g = float(np.dot(p - np.array(hit), d))
                    deep = max(deep, -g)
                    if i in edge:
                        gap = g if gap is None else max(gap, g)
                for key, v, worst in (("lap_mm", ov, min), ("lap_through_mm", deep, max), ("lap_gap_mm", gap, max)):
                    v = None if v is None else 1000 * v
                    old = res[key].get(name)
                    res[key][name] = v if old is None else (old if v is None else worst(old, v))
            for fl in cfg["flat"]:
                fit = fits.get(fl["part"])
                v = 1000 * float(fit[2].max()) if fit else None
                if fl.get("fit") == "smooth":   # G3n: folds, off a smooth fit of its own motion
                    old = res["flat_rigid_mm"].get(fl["part"])
                    res["flat_rigid_mm"][fl["part"]] = v if old is None else max(old, v)
                    ids = parts[fl["part"]]
                    v = 1000 * max(G.smooth_residual(ref[ids], co[ids], int(fl.get("deg", 3)))) if len(ids) >= 30 else None
                old = res["flat_mm"].get(fl["part"])
                res["flat_mm"][fl["part"]] = v if old is None else max(old, v)
            if skin_tie:
                sco = np.concatenate([world(o) for o in skin_objs])
                if sref0 is None:   # her skin at the reference (the reference clip's first frame, else this frame)
                    sref0 = sref
            for lf in cfg.get("lifts", []):   # G3j: a part off her skin under it since the reference (the flap)
                key = lift_key(lf)
                if lf.get("on"):   # G3l: off another part of the garment
                    tie = on_tie.get(key)
                    v, at = G.skin_lift(co0, co, co0, co, tie, where=True, both=True) if tie else (None, None)
                else:
                    tie = skin_tie.get(lf["part"])
                    v, at = G.skin_lift(ref, co, sref0, sco, tie, where=True) if tie else (None, None)
                v = None if v is None else 1000 * v
                old = res["lift_mm"].get(key)
                if v is not None and (old is None or v > old):   # where: its reference point (cm) and the frame
                    res["lift_at"][key] = [round(100 * float(x), 1) for x in ref[at]] + [f]
                res["lift_mm"][key] = v if old is None else (old if v is None else max(old, v))
            for st in cfg["stretch"]:
                if st.get("vs_skin") and skin_tie.get(st["part"]):
                    tie = skin_tie[st["part"]]
                    e = [(i, j) for i, j in edges[st["part"]].tolist() if i in tie and j in tie]
                    s0, s1 = skin_points(sref0, st["part"]), skin_points(sco, st["part"])
                    mx, p95, at = G.skin_excess(ref, co, s0, s1, e, where=True) if e else (None, None, None)
                    best = res["skin_excess_p95_pct"].get(st["part"])
                    if at is not None and p95 is not None and (best is None or p95 > best):
                        mid = (ref[at[0]] + ref[at[1]]) / 2
                        res["stretch_at"][st["part"]] = [round(100 * float(x), 1) for x in mid] + [f, round(mx, 1)]
                    for key, v in (("skin_excess_pct", mx), ("skin_excess_p95_pct", p95)):
                        old = res[key].get(st["part"])
                        res[key][st["part"]] = v if old is None else (old if v is None else max(old, v))
                mx, p95 = G.stretch(ref, co, edges[st["part"]])   # None for a part with no edges
                for key, v in (("stretch_pct", mx), ("stretch_p95_pct", p95)):
                    old = res[key].get(st["part"])
                    res[key][st["part"]] = v if old is None else (old if v is None else max(old, v))
        for k in ("slip_mm", "flat_mm", "stretch_pct", "stretch_p95_pct", "skin_excess_pct", "skin_excess_p95_pct",
                  "lap_mm", "lap_through_mm", "lap_gap_mm", "lift_mm", "flat_rigid_mm"):
            res[k] = {n: (None if v is None else round(v, 2)) for n, v in res[k].items()}
        rep["clips"][clip] = res
        say("clip", clip, json.dumps(res))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(rep, indent=1), encoding="utf-8", newline="\n")
    say("wrote", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
