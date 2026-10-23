"""The vault plush's mouth (art#297, step 3; the engineer, 2026-10-23, option A, then "under the nose, where the body
and the nose meet"): the crease where the muzzle meets the body closed to a shallow seam, and the smile's line along
that seam.

blender -b --factory-startup --python plush_mouth.py -- <clean full.glb> <out.glb> <smile.json> [--reach 0.007]
    [--iterations 40] [--top 0.0]

Meshy's smile was broken dark bits in a deep crease, whose shadow read as a dark wedge, a crack; it painted the smile
on one side only, so the line is found from the shape. Around the nose's axis (front to back), each angle's most
concave vertex 1.5 to 4.5 cm from the axis and below the eyes is a pick, from the left cheek under the muzzle to the
right one. The fill: every vertex within --reach metres of the smoothed picks that is still concave moves towards its
neighbours' average, --iterations times, weighted from 1 at the seam to 0 at the reach; convex vertices (the muzzle's
rim, the cheeks) never move, so nothing shrinks. The line: the picks' distance from the axis and their depth fitted as
even quartics of the angle from straight down (both sides together: symmetric and smooth), out to where the curve
rises to --top metres above the nose's middle, laid on the filled surface and resampled every 0.2 mm. Writes the
filled model to <out.glb> (with the cleanup's normal map beside it under its name) and the line to <smile.json> for
plush_paint.py. Prints one line `PLUSH_MOUTH {...}`.
"""

import json
import shutil
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
src, out, smile_json = Path(argv[0]), Path(argv[1]), Path(argv[2])
opts = dict(zip(argv[3::2], argv[4::2]))
REACH = float(opts.get("--reach", 0.007))
ITER = int(opts.get("--iterations", 40))
TOP = float(opts.get("--top", 0.0))  # the smile's corners end this far above the nose's middle

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(src))
obj = next(o for o in bpy.context.scene.objects if o.type == "MESH")
me = obj.data

bm = bmesh.new()
bm.from_mesh(me)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
bm.verts.ensure_lookup_table()
bm.normal_update()
vco = np.array([tuple(vv.co) for vv in bm.verts])
vnorm = np.array([tuple(vv.normal) for vv in bm.verts])
nbr = [[e.other_vert(vv).index for e in vv.link_edges] for vv in bm.verts]


def concavity(points):
    avg = np.array([points[n].mean(0) if n else points[i] for i, n in enumerate(nbr)])
    edge = np.array([np.linalg.norm(points[n] - points[i], axis=1).mean() if n else 1.0 for i, n in enumerate(nbr)])
    return ((avg - points) * vnorm).sum(1) / np.maximum(edge, 1e-6)


front = vco[:, 1].min()
nose = vco[vco[:, 1] < front + 0.015].mean(0)
conc = concavity(vco)
rel = vco - nose
theta = np.arctan2(rel[:, 2], rel[:, 0])
radius = np.hypot(rel[:, 0], rel[:, 2])
th = np.where(theta > np.pi / 2, theta - 2 * np.pi, theta)  # one continuous angle from the left side to the right
# the picks: below the nose up its sides to just under the eyes (1.2 cm above the nose's middle)
cand = (rel[:, 1] > 0.005) & (rel[:, 1] < 0.08) & (radius > 0.015) & (radius < 0.045) & (rel[:, 2] < 0.012) & \
    (th > -np.pi - 0.6) & (th < 0.6) & (conc > 0.08)
bins = np.linspace(-np.pi - 0.6, 0.6, 61)
picks = []
for b0, b1 in zip(bins[:-1], bins[1:]):
    sel = cand & (th >= b0) & (th < b1)
    if sel.any():
        picks.append(vco[np.nonzero(sel)[0][np.argmax(conc[sel])]])
if len(picks) < 20:
    raise SystemExit(f"PLUSH_MOUTH found the crease in only {len(picks)} of {len(bins) - 1} angles")
picks = np.array(picks)
seam = picks.copy()
for _ in range(4):
    seam[1:-1] = (seam[:-2] + 2 * seam[1:-1] + seam[2:]) / 4

# fill the crease: each vertex within the reach and still concave moves towards its neighbours' average
dist = np.full(len(vco), np.inf)
for k in range(0, len(seam), 40):
    dist = np.minimum(dist, np.linalg.norm(vco[:, None, :] - seam[None, k:k + 40, :], axis=2).min(1))
weight = np.clip(1.0 - dist / REACH, 0.0, 1.0) ** 1.2
near = np.nonzero(weight > 0)[0]
before = vco.copy()
moved_any = np.zeros(len(vco), dtype=bool)
for _ in range(ITER):
    new = vco.copy()
    for i in near:
        if not nbr[i]:
            continue
        avg = vco[nbr[i]].mean(0)
        if np.dot(avg - vco[i], vnorm[i]) > 0:
            new[i] = vco[i] + (avg - vco[i]) * 0.6 * weight[i]
            moved_any[i] = True
    vco = new
moved = np.nonzero(moved_any)[0]
for i in moved:
    bm.verts[i].co = Vector(vco[i])
shift = np.linalg.norm(vco - before, axis=1)
bm.to_mesh(me)
bm.free()
me.update()
tree = BVHTree.FromObject(obj, bpy.context.evaluated_depsgraph_get())


def on_surface(p):
    hit = tree.find_nearest(Vector(p))
    return np.array(hit[0]) if hit[0] is not None else np.array(p)


# the line: the picks' distance from the axis and depth as even quartics of the angle from straight down, fitted twice
# (the second time without the picks far off the first fit)
rp = picks - nose
ang = np.arctan2(rp[:, 2], rp[:, 0])
u = np.where(ang > np.pi / 2, ang - 2 * np.pi, ang) + np.pi / 2  # 0 straight down, -/+ towards each side
rad = np.hypot(rp[:, 0], rp[:, 2])
A = np.stack([np.ones_like(u), u ** 2, u ** 4], axis=1)
keep = np.ones(len(u), dtype=bool)
for _ in range(2):
    fr = np.linalg.lstsq(A[keep], rad[keep], rcond=None)[0]
    fd = np.linalg.lstsq(A[keep], rp[keep, 1], rcond=None)[0]
    res_r = np.abs(A @ fr - rad)
    keep = res_r <= max(2.0 * np.median(res_r), 0.001)
us = np.linspace(-np.pi, np.pi, 2001)
Au = np.stack([np.ones_like(us), us ** 2, us ** 4], axis=1)
ok = ((Au @ fr) * np.sin(us - np.pi / 2) < TOP) & (np.abs(us) <= np.abs(u).max())
mid = len(us) // 2
if not ok[mid]:
    raise SystemExit("PLUSH_MOUTH: the fitted smile does not pass under the nose")
hi_i = mid  # from the bottom out to the first angle on each side where it would pass TOP
while hi_i + 1 < len(us) and ok[hi_i + 1]:
    hi_i += 1
lo_i = mid
while lo_i - 1 >= 0 and ok[lo_i - 1]:
    lo_i -= 1
us, Au = us[lo_i:hi_i + 1], Au[lo_i:hi_i + 1]
r_s, d_s, th_s = Au @ fr, Au @ fd, us - np.pi / 2
path = np.stack([nose[0] + r_s * np.cos(th_s), nose[1] + d_s, nose[2] + r_s * np.sin(th_s)], axis=1)
full = np.array([on_surface(p) for p in path])
# resampled every 0.2 mm along its length, so the painted thread is one stroke, never a row of dots
seg = np.linalg.norm(np.diff(full, axis=0), axis=1)
arc = np.concatenate([[0.0], np.cumsum(seg)])
full = np.stack([np.interp(np.arange(0.0, arc[-1], 0.0002), arc, full[:, k]) for k in range(3)], axis=1)

out.parent.mkdir(parents=True, exist_ok=True)
for o in bpy.context.scene.objects:
    o.select_set(o == obj)
bpy.ops.export_scene.gltf(filepath=str(out), export_format="GLB", use_selection=True, export_yup=True,
                          export_image_format="AUTO", export_tangents=True)
# the cleanup's baked normal travels beside the GLB under its name (plush_paint.py reads it from there)
shutil.copyfile(src.with_name(src.stem + "_normal.png"), out.with_name(out.stem + "_normal.png"))
smile_json.write_text(json.dumps({"line": [[round(float(c), 6) for c in p] for p in full],
                                  "reach_m": REACH, "iterations": ITER, "top_m": TOP}, indent=1) + "\n",
                      encoding="utf-8")
print("PLUSH_MOUTH " + json.dumps({
    "crease_angles": len(picks), "nose_m": [round(float(c), 4) for c in nose],
    "line_x_m": [round(float(full[:, 0].min()), 4), round(float(full[:, 0].max()), 4)],
    "line_z_m": [round(float(full[:, 2].min()), 4), round(float(full[:, 2].max()), 4)],
    "line_length_m": round(float(arc[-1]), 4), "vertices_moved": int(len(moved)),
    "max_shift_mm": round(float(shift.max()) * 1000, 2),
    "mean_shift_mm": round(float(shift[moved].mean()) * 1000, 3) if len(moved) else 0.0}))
