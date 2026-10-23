"""The vault plush's mouth (art#297, step 3; the engineer, 2026-10-23, option A): the crease under the muzzle closed to
a shallow seam, and the smile's line through it with corners curled up by the cheeks, as in the concept.

blender -b --factory-startup --python plush_mouth.py -- <clean full.glb> <out.glb> <smile.json> [--reach 0.005]
    [--iterations 12] [--curl 0.005]

Meshy's smile is broken dark bits lying in a deep crease where the muzzle meets the cheeks; the shadow in the crease
read as a dark wedge, a crack. The smile's line is found from those bits (their texels' 3D points, the median point
in each slice across the face, smoothed). The vertices within --reach metres of the line are relaxed towards their
neighbours' average, weighted from 1 at the line to 0 at the reach, so the crease's walls come together into a
shallow seam while the head and muzzle elsewhere stay as they are. The line is then laid back on the relaxed surface,
each end gets an upturned curl (--curl metres long, bending up to 80 degrees), all of it laid by rays from the front and both are written to the JSON
for plush_paint.py to draw. Prints one line `PLUSH_MOUTH {...}`.
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
CURL = float(opts.get("--curl", 0.007))
DROP = float(opts.get("--drop", 0.0015))  # the line this far below the muzzle's overhang, where the front sees it

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(src))
obj = next(o for o in bpy.context.scene.objects if o.type == "MESH")
me = obj.data
bsdf = next(n for n in obj.active_material.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
img = bsdf.inputs["Base Color"].links[0].from_node.image
w, h = img.size
px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)[..., :3]
v = px.max(-1)
s = np.where(v > 1e-4, (v - px.min(-1)) / np.maximum(v, 1e-4), 0.0)
dark = v < 0.20
white = (~dark) & (s < 0.32) & (v > 0.55)
brownish = (~dark) & (~white) & (v < 0.55)  # Meshy's velour: the nose, paws, balls

# The smile's line is the crease itself, found from the shape (Meshy painted the smile only in bits, on one side):
# around the nose's axis (front to back), below the nose, each angle's most concave vertex in a ring 1.5 to 4.5 cm
# from the axis, from the left cheek under the muzzle to the right one, smoothed.
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
nose_sel = vco[:, 1] < front + 0.015
nose = vco[nose_sel].mean(0)
conc = concavity(vco)
rel = vco - nose
theta = np.arctan2(rel[:, 2], rel[:, 0])
radius = np.hypot(rel[:, 0], rel[:, 2])
# only the lower half of the ring (the corners' curls come later), below the nose's middle: higher up the most
# concave place is an eye socket's rim
cand = (rel[:, 1] > 0.005) & (rel[:, 1] < 0.08) & (radius > 0.015) & (radius < 0.045) & (theta < -0.2) & \
    (theta > -np.pi + 0.2) & (rel[:, 2] < -0.003) & (conc > 0.08)
crease = []
bins = np.linspace(-np.pi + 0.2, -0.2, 41)
for b0, b1 in zip(bins[:-1], bins[1:]):
    sel = cand & (theta >= b0) & (theta < b1)
    if sel.any():
        i = np.nonzero(sel)[0][np.argmax(conc[sel])]
        crease.append(vco[i])
if len(crease) < 8:
    raise SystemExit(f"PLUSH_MOUTH found the crease in only {len(crease)} of 40 angles")
# one smooth, symmetric smile through the picks (the deepest point per angle jitters under the nose): z and y as even
# quadratics of x about the nose, fitted twice, the second time without the picks far off the first fit; the curve is
# snapped to the surface after the fill below
crease = np.array(crease)
cx = crease[:, 0] - nose[0]
keep = np.ones(len(crease), dtype=bool)
for _ in range(2):
    A = np.stack([cx[keep] ** 2, np.ones(keep.sum())], axis=1)
    fz = np.linalg.lstsq(A, crease[keep, 2], rcond=None)[0]
    fy = np.linalg.lstsq(A, crease[keep, 1], rcond=None)[0]
    resid = np.abs(fz[0] * cx ** 2 + fz[1] - crease[:, 2])
    keep = resid <= max(2.0 * np.median(resid), 0.001)
half = float(np.percentile(np.abs(cx), 95))
xs = np.linspace(-half, half, 200)
line = np.stack([nose[0] + xs, fy[0] * xs ** 2 + fy[1], fz[0] * xs ** 2 + fz[1]], axis=1)
# the fill follows the crease itself (the picks, smoothed); the painted line is the fitted curve
# and runs on up beside the muzzle, past the smile's ends, to just under the eyes: those picks join the fill
th = np.where(theta > np.pi / 2, theta - 2 * np.pi, theta)  # one continuous angle from the left side to the right
wide = (rel[:, 1] > 0.005) & (rel[:, 1] < 0.08) & (radius > 0.015) & (radius < 0.045) & (rel[:, 2] < 0.012) &     (th > -np.pi - 0.6) & (th < 0.6) & (conc > 0.08)
seam = []
for b0, b1 in zip(np.linspace(-np.pi - 0.6, 0.6, 61)[:-1], np.linspace(-np.pi - 0.6, 0.6, 61)[1:]):
    sel = wide & (th >= b0) & (th < b1)
    if sel.any():
        seam.append(vco[np.nonzero(sel)[0][np.argmax(conc[sel])]])
seam = np.array(seam)
for _ in range(4):
    seam[1:-1] = (seam[:-2] + 2 * seam[1:-1] + seam[2:]) / 4
pts = line
mids = crease
lo, hi = float(line[:, 0].min()), float(line[:, 0].max())

# fill the crease: each vertex within the reach and still concave moves towards its neighbours' average, weighted
# by its closeness; convex vertices (the muzzle's rim, the cheeks) never move, so nothing shrinks
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

# the line back on the relaxed surface, then a curl at each end: on along the line, bending up
tree = BVHTree.FromObject(obj, bpy.context.evaluated_depsgraph_get())


def on_surface(p):
    hit = tree.find_nearest(Vector(p))
    return np.array(hit[0]) if hit[0] is not None else np.array(p)




def from_front(p):
    """The surface the front sees at p's x and z (a ray along +Y from in front of the toy)."""
    hit = tree.ray_cast(Vector((p[0], -1.0, p[2])), Vector((0.0, 1.0, 0.0)))
    return np.array(hit[0]) if hit[0] is not None else on_surface(p)


# the whole smile is drawn as the front sees it, in x and z, then laid on the surface by rays from the front (a curl
# crawling over the surface climbed the crease's wall and doubled the line, the critic, 2026-10-23): the fitted curve
# DROP below the overhang, and at each end a curl that turns from the curve's own direction to 80 degrees up
flat = line[:, [0, 2]] - np.array([0.0, DROP])
curls = []
for end, prev in ((flat[0], flat[3]), (flat[-1], flat[-4])):
    tangent = (end - prev) / np.linalg.norm(end - prev)
    up = np.array([0.0, 1.0])
    q = end.copy()
    curl = []
    steps = 14
    for k in range(1, steps + 1):
        ang = np.radians(80.0) * k / steps
        d = tangent * np.cos(ang) + up * np.sin(ang)
        q = q + d / np.linalg.norm(d) * CURL / steps
        curl.append(q.copy())
    curls.append(np.array(curl))
flat = np.concatenate([curls[0][::-1], flat, curls[1]])
full = np.array([from_front(np.array([q[0], 0.0, q[1]])) for q in flat])
# resampled every 0.2 mm along its length, so the painted thread is one stroke, never a row of dots
seg = np.linalg.norm(np.diff(full, axis=0), axis=1)
arc = np.concatenate([[0.0], np.cumsum(seg)])
fine = np.arange(0.0, arc[-1], 0.0002)
full = np.stack([np.interp(fine, arc, full[:, k]) for k in range(3)], axis=1)

out.parent.mkdir(parents=True, exist_ok=True)
for o in bpy.context.scene.objects:
    o.select_set(o == obj)
bpy.ops.export_scene.gltf(filepath=str(out), export_format="GLB", use_selection=True, export_yup=True,
                          export_image_format="AUTO", export_tangents=True)
# the cleanup's baked normal travels beside the GLB under its name (plush_paint.py reads it from there)
shutil.copyfile(src.with_name(src.stem + "_normal.png"), out.with_name(out.stem + "_normal.png"))
smile_json.write_text(json.dumps({"line": [[round(float(c), 6) for c in p] for p in full],
                                  "reach_m": REACH, "iterations": ITER, "curl_m": CURL, "drop_m": DROP}, indent=1) + "\n",
                      encoding="utf-8")
print("PLUSH_MOUTH " + json.dumps({
    "crease_angles": len(mids), "nose_m": [round(float(c), 4) for c in nose], "x_range_m": [round(float(lo), 4), round(float(hi), 4)],
    "line_z_m": [round(float(full[:, 2].min()), 4), round(float(full[:, 2].max()), 4)],
    "seam_angles": len(seam), "vertices_moved": int(len(moved)), "max_shift_mm": round(float(shift.max()) * 1000, 2),
    "mean_shift_mm": round(float(shift[moved].mean()) * 1000, 3) if len(moved) else 0.0}))
