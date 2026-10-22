"""The alien 3D pilot, step 2a (art #196): one Meshy head (step 1's remeshed, textured GLB) turned into game parts in
headless Blender. Reads the raw GLB (never writes it) and writes into --out:

- the skin: Meshy's fused shell, its UV seams welded, decimated to the budget (`skin_tris`), a new UV atlas and a
  2048 px colour and normal bake from the raw model (colour through a palette ramp from the 2D turnaround's teal and
  mint, `palette_stops`; the chameleon's crest stripes painted in during the bake);
- a real lip parting: a thin slit cut along the lip line (the deepest valley between the lips in the front profile,
  tracked from the middle to the corners), its edges rolled back into the mouth as a lining, an open mouth cup behind
  it (dark, its inside facing the slit) and, for the chameleon (his 2D shows one), a simple tongue;
- eyeballs (sclera, iris, pupil, a catch light in a generated texture; the axolotl's are black beads) at the painted
  eyes' fitted spheres, and upper and lower lids as solid spherical shells at the 2D's rest pose;
- chameleon: the skull widened above the mouth, the eyes larger and bulging, the lips thicker and wider, and the
  crest root's ledge above each eye smoothed (a Laplacian smooth inside a soft region, its strength `--smooth`);
- axolotl: the six gill stalks cut off the head at their roots (their holes filled), fanned out from the head; the raised rim around each eye softened;
- the parts joined into one mesh per kind, `<head>_skin`, `<head>_eyes`, `<head>_lids`, `<head>_mouth` and
  `<head>_gills`, with each piece's pivot (eye centres, gill roots) in the custom property `pivots` (glTF extras);
- step 2b-1's polish: the chameleon's lips rebuilt as two rolled tubes (`lip_tube`) with their textures flattened
  (`flatten_lips`) and his lids' outer corners opened (`lid_corner_outer`); the axolotl's pale front as a positional
  mask over the ramp (`pale_front`) and a white catch light on her beads (`catch_light`); each lid's parameters in
  `build.json` (`lids`) for the rig (alien_pilot_rig.py);
- `<head>.glb` and `<head>_lod1.glb` (skin and gills decimated further), `<head>.blend`, `build.json` (tri counts,
  eye fits, the lip line, gains), review renders `views/` (front, side, back, 3/4) and `smooth_grid.png` (the smooth
  region's weights and three strengths, close up, both sides).

Runs only through tools/runner/blender.py (blender -b): run_script("alien_pilot_head.py", ["--head", "chameleon",
"--src", <raw GLB>, "--view2d", <2D front.png>, "--out", <dir>]).
"""
from __future__ import annotations

import argparse
import heapq
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_pilot_geom as G  # noqa: E402

HEADS = {
    "chameleon": {
        "eye_mask": "white", "eye_scale": 1.3, "eye_out": 0.2, "widen": 0.10, "lips": 0.18, "lip_widen": 0.10,
        "tongue": True, "stripes": True, "skin_tris": 30000,
        # lids: (free edge, root) in degrees above the gaze; the 2D's heavy upper lid covers the top third
        "lid_upper": (10.0, 100.0), "lid_lower": (-62.0, -100.0), "lid_thick": 0.16, "lid_alpha": 130.0,
        "lid_corner": {"upper": -12.0, "lower": -14.0},
        # the outer corner opened (2b): more white from the side, as the 2D's side view shows
        "lid_corner_outer": {"upper": 6.0, "lower": -32.0},
        "eye_spec": {"iris_deg": 27.0, "pupil_deg": 12.0, "sclera": (1.0, 1.0, 0.98), "iris": (0.40, 0.19, 0.08),
                     "iris_rim": (0.16, 0.07, 0.03), "pupil": (0.02, 0.01, 0.01), "glint": (0.89, 0.075, 0.035)},
        "eye_rough": 0.08,
        # the lips: a volume-keeping Laplacian smooth (iterations, lambda) on the raw and the work mesh before the cut;
        # the mouth cup's half width in lip half widths, and the lips' parting at rest in mouth units (0: closed)
        "lip_smooth": (40, 1.0), "lip_post": (12, 0.5),
        # 2b: the lips rebuilt as two rolled tubes along the lip line (radius in mouth units), no Meshy creases
        "lip_tube": {"radius": 0.3}, "cup_x": 0.72, "lip_gap": 0.0, "lip_from": "profile",
        # the ledge at the crest's root above each eye, seen from the side: (side offset, back, up) in eye radii
        "smooth_region": {"kind": "ledge", "centre": (0.4, 1.5, 1.0), "radii": (1.3, 2.0, 1.3)},
        "smooth": (150, 0.9),
    },
    "axolotl": {
        "eye_mask": "dark", "eye_scale": 1.12, "eye_out": 0.0, "widen": 0.0, "lips": 0.0, "lip_widen": 0.0,
        "tongue": False, "stripes": False, "skin_tris": 20000, "gill_tris": 2000,
        "lid_upper": (52.0, 100.0), "lid_lower": (-58.0, -100.0), "lid_thick": 0.06, "lid_alpha": 110.0, "mouth_scale": 0.15,
        "eye_spec": {"iris_deg": 70.0, "pupil_deg": 30.0, "sclera": (0.05, 0.035, 0.035), "iris": (0.05, 0.03, 0.03),
                     "iris_rim": (0.04, 0.03, 0.03), "pupil": (0.01, 0.01, 0.01), "glint": (0.89, 0.12, 0.05)},
        "eye_rough": 0.06,
        # 2b: the 2D's near-white front (face below the eyes, throat, chest) over the ramp, and a white catch light
        "pale_front": {"rgb": (0.86, 0.97, 0.91), "strength": 0.9, "facing": (0.35, 0.8), "lip_band": (0.5, 0.8)}, "catch_light": 10.0,
        # her lip band overhangs the mouth line, so the line comes from the texture's darker painted smile
        "lip_smooth": (0, 0.0), "cup_x": 0.8, "lip_gap": 0.06, "lip_from": "texture",
        "smooth_region": {"kind": "ring", "inner": 0.8, "peak": (1.1, 1.45), "outer": 2.0},
        "smooth": (30, 0.8),
    },
}
MOUTH_RGB = (0.16, 0.05, 0.06)
TONGUE_RGB = (0.80, 0.42, 0.45)
LOD_RATIO = 0.35


def srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def log(msg: str) -> None:
    print(f"PILOT {msg}", flush=True)


# ---------------------------------------------------------------------------------------------- import and analysis
def import_glb(path: Path) -> bpy.types.Object:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    new = [o for o in bpy.data.objects if o not in before]
    mesh = [o for o in new if o.type == "MESH"][0]
    mw = mesh.matrix_world.copy()
    mesh.parent = None
    mesh.data.transform(mw)
    mesh.matrix_world = Matrix.Identity(4)
    for o in new:
        if o is not mesh:
            bpy.data.objects.remove(o)
    return mesh


def base_image(mat: bpy.types.Material) -> bpy.types.Image:
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    node = bsdf.inputs["Base Color"].links[0].from_node
    while node.type != "TEX_IMAGE":
        node = next(i.links[0].from_node for i in node.inputs if i.is_linked)
    return node.image


def image_array(img: bpy.types.Image) -> np.ndarray:
    w, h = img.size
    a = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(h, w, 4)


def face_colours(me: bpy.types.Mesh, pix: np.ndarray) -> np.ndarray:
    """sRGB colour of each triangle at its UV centroid."""
    uv = np.empty(len(me.loops) * 2, dtype=np.float32)
    me.uv_layers.active.data.foreach_get("uv", uv)
    starts = np.empty(len(me.polygons), dtype=np.int64)
    me.polygons.foreach_get("loop_start", starts)
    uv = uv.reshape(-1, 2)
    c = (uv[starts] + uv[starts + 1] + uv[starts + 2]) / 3.0
    h, w = pix.shape[:2]
    xs = np.clip((c[:, 0] % 1.0 * w).astype(int), 0, w - 1)
    ys = np.clip((c[:, 1] % 1.0 * h).astype(int), 0, h - 1)
    return pix[ys, xs, :3]


def weld(obj: bpy.types.Object) -> None:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bm.to_mesh(obj.data)
    bm.free()


def find_eyes(obj, pix, mask_kind, front, left):
    me = obj.data
    n = len(me.polygons)
    cen = np.empty(n * 3, dtype=np.float32)
    me.polygons.foreach_get("center", cen)
    cen = cen.reshape(-1, 3)
    col = face_colours(me, pix)
    if mask_kind == "white":
        mask = (col.min(1) > 0.72) & (col.max(1) - col.min(1) < 0.08)
    else:
        mask = col.max(1) < 0.13
    mid = (cen.max(0) + cen.min(0)) / 2
    mask &= (cen - mid) @ np.array(front) > 0
    idx = np.nonzero(mask)[0]
    pts = [tuple(map(float, cen[i])) for i in idx]
    edge = float(np.sqrt(np.mean([p.area for p in me.polygons]) * 2.3))
    groups = G.clusters(pts, 2.5 * edge)
    eyes = {}
    for side in (1, -1):
        cands = [g for g in groups if np.mean([pts[i][0] for i in g]) * side * left[0] > 0]
        big = len(cands[0]) if cands else 0
        cands = [g for g in cands if len(g) >= 0.3 * big]
        best = max(cands, key=lambda g: np.mean([pts[i][2] for i in g]))
        fit_pts = [pts[i] for i in best]
        centre, radius = G.fit_sphere(fit_pts)
        centroid = np.mean(fit_pts, axis=0)
        spread = float(np.max(np.linalg.norm(np.array(fit_pts) - centroid, axis=1)))
        if not (0.6 * spread < radius < 3.0 * spread):
            radius = spread * 1.1
            centre = tuple(centroid - np.array(front) * radius * 0.5)
        eyes["L" if side == 1 else "R"] = {"centre": centre, "radius": radius, "faces": len(best), "spread": spread}
    # one symmetric pair (the head is symmetric about x = 0)
    cl, cr = eyes["L"]["centre"], eyes["R"]["centre"]
    x = (abs(cl[0]) + abs(cr[0])) / 2
    y, z = (cl[1] + cr[1]) / 2, (cl[2] + cr[2]) / 2
    r = (eyes["L"]["radius"] + eyes["R"]["radius"]) / 2
    return {"x": x, "y": y, "z": z, "r": r, "edge": edge, "raw": eyes}


# ------------------------------------------------------------------------------------------------------- the gills
def cut_gills(obj, eye, front):
    """Splits the gill stalks off the skin (faces outside the head's ellipsoid, at its sides), fills the holes;
    returns the stalks as (bmesh-free) objects with their root points."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    fr = Vector(front)
    mid = [v.co for v in bm.verts if abs(v.co.x) < 0.03 * eye["r"] * 10 and abs(v.co.z - eye["z"]) < 0.4 * eye["r"]]
    depths = [c.dot(fr) for c in mid]
    yf, yb = max(depths), min(depths)
    cy = (yf + yb) / 2
    ry = (yf - yb) / 2
    side = [v.co for v in bm.verts if abs(v.co.z - eye["z"]) < 0.5 * eye["r"] and v.co.dot(fr) > cy]
    rx = max(abs(c.x) for c in side)
    top = max(v.co.z for v in bm.verts if abs(v.co.x) < 0.5 * eye["r"])
    cz = eye["z"]
    rz = top - cz
    centre = Vector((0.0, 0.0, cz)) + fr * cy

    def outside(co):
        d = co - centre
        e = math.sqrt((d.x / rx) ** 2 + (d.dot(fr) / ry) ** 2 + (d.z / rz) ** 2)
        return e > 1.12 and abs(co.x) > 0.45 * rx and co.z > cz - 0.5 * rz

    flag = {v.index: outside(v.co) for v in bm.verts}
    gill_faces = [f for f in bm.faces if all(flag[v.index] for v in f.verts)]
    # connected groups of gill faces (flood fill over shared edges)
    seen, groups = set(), []
    gset = set(gill_faces)
    for f in gill_faces:
        if f in seen:
            continue
        stack, grp = [f], []
        seen.add(f)
        while stack:
            g = stack.pop()
            grp.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h in gset and h not in seen:
                        seen.add(h)
                        stack.append(h)
        groups.append(grp)
    groups.sort(key=len, reverse=True)
    big = [g for g in groups if len(g) >= 0.04 * len(gill_faces)][:6]
    small = [g for g in groups if not any(g is b for b in big)]
    cents = [sum((f.calc_center_median() for f in g), Vector()) / len(g) for g in big]
    for g in small:
        c = sum((f.calc_center_median() for f in g), Vector()) / len(g)
        k = min(range(len(big)), key=lambda i: (cents[i] - c).length)
        big[k].extend(g)
    layer = bm.faces.layers.int.get("pilot_part") or bm.faces.layers.int.new("pilot_part")
    order = sorted(range(len(big)), key=lambda i: (-math.copysign(1, cents[i].x * 1.0), -cents[i].z))
    names = {}
    for rank, i in enumerate(order):
        sidec = "L" if cents[i].x > 0 else "R"
        k = sum(1 for j in order[:rank] if (cents[j].x > 0) == (cents[i].x > 0)) + 1
        names[i] = (f"gill_{sidec}{k}", 10 + rank)
        for f in big[i]:
            f[layer] = 10 + rank
    bm.to_mesh(obj.data)
    bm.free()
    info = {"head_centre": list(centre), "radii": [rx, ry, rz], "gill_faces": len(gill_faces),
            "groups": len(groups), "stalks": len(big), "names": [names[i][0] for i in order]}
    # split each stalk into its own object, the skin keeps the rest; fill the skin's holes
    parts = {}
    for i in order:
        name, part = names[i]
        parts[name] = split_part(obj, lambda p, part=part: p == part, name, keep_boundary_sink=centre)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    layer = bm.faces.layers.int["pilot_part"]
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f[layer] >= 10], context="FACES")
    holes = [e for e in bm.edges if e.is_boundary]
    res = bmesh.ops.holes_fill(bm, edges=holes, sides=0)
    bmesh.ops.triangulate(bm, faces=res["faces"])
    bm.to_mesh(obj.data)
    bm.free()
    info["holes_filled"] = len(res["faces"])
    return parts, info, centre


def split_part(obj, pred, name, keep_boundary_sink=None):
    """A new object holding the faces of obj whose pilot_part satisfies pred (obj keeps everything)."""
    me = obj.data.copy()
    bm = bmesh.new()
    bm.from_mesh(me)
    layer = bm.faces.layers.int["pilot_part"]
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if not pred(f[layer])], context="FACES")
    root = None
    if keep_boundary_sink is not None:
        ring = [e for e in bm.edges if e.is_boundary]
        rv = {v for e in ring for v in e.verts}
        if rv:
            root = sum((v.co for v in rv), Vector()) / len(rv)
            ext = bmesh.ops.extrude_edge_only(bm, edges=ring)
            for v in [g for g in ext["geom"] if isinstance(g, bmesh.types.BMVert)]:
                v.co += (keep_boundary_sink - v.co).normalized() * 0.03
    bm.to_mesh(me)
    bm.free()
    new = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(new)
    new["root"] = list(root) if root is not None else None
    return new


# ------------------------------------------------------------------------------------------------- the lip line
def lip_line(obj, eye, front, m):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    fr = Vector(front)
    r, edge = m, eye["edge"]
    near = [v for v in bm.verts if abs(v.co.x) < max(0.15 * r, 2 * edge)
            and eye["z"] - 4.5 * r < v.co.z < eye["z"] - 0.8 * r]
    p = max(near, key=lambda v: v.co.dot(fr)).co.copy()
    log(f"lip front point {tuple(round(c, 4) for c in p)} from {len(near)} points")
    zbin = max(0.04 * r, 0.6 * edge)
    xbin = max(0.15 * r, 2.5 * edge)
    cand = [v for v in bm.verts if v.normal.dot(fr) > -0.3 and v.co.dot(fr) > p.dot(fr) - 1.4 * r
            and abs(v.co.z - p.z) < 1.2 * r]
    line = []
    for sign in (1, -1):
        zc, win, k = p.z, 0.6 * r, 0
        while True:
            x0 = sign * k * xbin
            sel = [v for v in cand if abs(v.co.x - x0) < xbin / 2 and abs(v.co.z - zc) < win]
            if len(sel) < 6:
                log(f"lip line x={x0:.3f}: {len(sel)} points, stop")
                break
            nb = int(2 * win / zbin) + 1
            prof = [None] * nb
            for v in sel:
                i = min(int((v.co.z - (zc - win)) / zbin), nb - 1)
                d = v.co.dot(fr)
                prof[i] = d if prof[i] is None else max(prof[i], d)
            filled = [x for x in prof if x is not None]
            if len(filled) < 5:
                break
            last = filled[0]
            for i in range(nb):
                prof[i] = last = prof[i] if prof[i] is not None else last
            i, prom = G.valley(prof)
            if i < 0 or prom < 0.015 * r:
                log(f"lip line x={x0:.3f}: valley {i} prominence {prom:.4f} of {len(filled)} bins, stop; "
                    f"profile {[round(x, 3) for x in prof]}")
                break
            zg = zc - win + (i + 0.5) * zbin
            line.append((x0, zg, prof[i]))
            zc, win, k = zg, 0.35 * r, k + 1
            if k > 60:
                break
    bm.free()
    line = sorted({(round(x, 6), z, d) for x, z, d in line})
    half = {}
    for x, z, d in line:
        half.setdefault(round(abs(x), 6), []).append((z, d))
    sym = sorted((x, sum(z for z, _ in v) / len(v), sum(d for _, d in v) / len(v)) for x, v in half.items())
    return {"front_point": list(p), "line": sym, "half_width": sym[-1][0] if sym else 0.0}


def lip_line_texture(obj, pix, eye, front, m):
    """The lip line as the texture paints it (the axolotl: her lip band overhangs the mouth, so the depth profile has
    no valley): per x bin from the middle outward, the height of the darkest front-facing faces near the last one."""
    me = obj.data
    n = len(me.polygons)
    cen = np.empty(n * 3, dtype=np.float32)
    me.polygons.foreach_get("center", cen)
    cen = cen.reshape(-1, 3)
    nrm = np.empty(n * 3, dtype=np.float32)
    me.polygons.foreach_get("normal", nrm)
    nrm = nrm.reshape(-1, 3)
    lum = face_colours(me, pix) @ np.array([0.3, 0.59, 0.11])
    fr = np.array(front)
    depth = cen @ fr
    near = (np.abs(cen[:, 0]) < max(0.15 * m, 2 * eye["edge"])) & (cen[:, 2] < eye["z"] - 0.8 * m) &         (cen[:, 2] > eye["z"] - 4.5 * m)
    i0 = np.nonzero(near)[0][np.argmax(depth[near])]
    p = cen[i0]
    log(f"lip front point (texture) {tuple(round(float(c), 4) for c in p)}")
    ok = (nrm @ fr > 0.3) & (depth > p @ fr - 1.4 * m)
    xbin = max(0.15 * m, 2.5 * eye["edge"])
    line = []
    for sign in (1, -1):
        lo, hi, k = p[2] - 0.45 * m, p[2] + 0.5 * m, 0
        while k <= 60:
            x0 = sign * k * xbin
            sel = ok & (np.abs(cen[:, 0] - x0) < xbin / 2) & (cen[:, 2] > lo) & (cen[:, 2] < hi)
            idx = np.nonzero(sel)[0]
            if len(idx) < 6:
                log(f"lip line (texture) x={x0:.3f}: {len(idx)} faces, stop")
                break
            order = idx[np.argsort(lum[idx])]
            dark = order[:max(3, len(order) // 10)]
            contrast = (float(np.median(lum[idx])) - float(lum[dark].mean())) / max(float(np.median(lum[idx])), 1e-3)
            if contrast < 0.035 or abs(x0) > 0.9 * eye["x"]:
                log(f"lip line (texture) x={x0:.3f}: contrast {contrast:.3f}, stop")
                break
            zg = float(np.median(cen[dark, 2]))
            if k and abs(zg - line[-1][1]) > 0.25 * m:
                log(f"lip line (texture) x={x0:.3f}: jump to z={zg:.4f}, stop")
                break
            band = idx[np.abs(cen[idx, 2] - zg) < 0.1 * m]
            d = float(depth[band].max()) if len(band) else float(depth[dark].max())
            line.append((x0, zg, d))
            lo, hi, k = zg - 0.3 * m, zg + 0.3 * m, k + 1
    half = {}
    for x, z, d in line:
        half.setdefault(round(abs(x), 6), []).append((z, d))
    sym = sorted((x, sum(z for z, _ in v) / len(v), sum(d for _, d in v) / len(v)) for x, v in half.items())
    # the last bins fade out at the corners: keep the run while it stays continuous
    return {"front_point": [float(c) for c in p], "line": sym, "half_width": sym[-1][0] if sym else 0.0,
            "from": "texture"}


def smooth_lips(objs, line, front, m, iterations, lam):
    """A volume-keeping Laplacian smooth inside a soft ellipsoid around the lips (Meshy's lip surface is noisy), on
    the raw model (the bake's source, so the normal map does not bring the lumps back) and the work mesh alike."""
    fr = Vector(front)
    zg0, d0 = line["line"][0][1], line["line"][0][2]
    centre = (0.0, d0 - 0.3 * m, zg0)
    radii = (line["half_width"] * 1.3, 0.9 * m, 0.9 * m)
    counts = {}
    for obj in objs:
        vg = obj.vertex_groups.new(name="lips")
        n = 0
        for v in obj.data.vertices:
            w = G.ellipsoid_weight((v.co.x, v.co.dot(fr), v.co.z), centre, radii)
            if w > 1e-3:
                vg.add([v.index], w, "REPLACE")
                n += 1
        mod = obj.modifiers.new("lips", "LAPLACIANSMOOTH")
        mod.iterations = iterations
        mod.lambda_factor = lam
        mod.lambda_border = 0.0
        mod.use_volume_preserve = True
        mod.use_normalized = True
        mod.vertex_group = "lips"
        apply_modifiers(obj)
        obj.vertex_groups.clear()
        counts[obj.name] = n
    return counts


def line_at(line, x):
    ax = abs(x)
    pts = line["line"]
    if ax <= pts[0][0]:
        return pts[0][1], pts[0][2]
    for (x0, z0, d0), (x1, z1, d1) in zip(pts, pts[1:]):
        if ax <= x1:
            t = (ax - x0) / (x1 - x0)
            return z0 + t * (z1 - z0), d0 + t * (d1 - d0)
    return pts[-1][1], pts[-1][2]


def smile_line(obj, tex_line, eye, front, m, half=0.75, rise=0.18, n=12):
    """A smooth smile for the bisect cut: its middle height from the texture's line, its half width (in the eyes'
    half spacing) and its corners' rise (in half widths) measured on the 2D front view; the depth per sample is the
    skin's most forward vertex there."""
    z0 = tex_line["line"][0][1]
    hw = half * eye["x"]
    fr = Vector(front)
    vs = [v.co for v in obj.data.vertices if abs(v.co.z - z0) < 1.5 * m and v.co.dot(fr) > tex_line["line"][0][2] - m]
    line = []
    for i in range(n + 1):
        x = hw * i / n
        z = z0 + rise * hw * (x / hw) ** 2
        near = [c.dot(fr) for c in vs if abs(c.x - x) < 0.08 * hw and abs(c.z - z) < 0.15 * m]
        line.append((x, z, max(near) if near else tex_line["line"][0][2]))
    return {"front_point": tex_line["front_point"], "line": line, "half_width": hw, "from": "texture+smile",
            "texture_line": tex_line["line"]}


def part_lips(obj, line, eye, front, m, gap=0.0, cut="path"):
    """Splits the skin along the lip line (the shortest edge path from corner to corner hugging the line, its edges
    split: the lips touch at rest but are apart) and rolls each lip's new edge back into the mouth as a lining
    (pilot_part 1), the upper one up and the lower one down."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    fr = Vector(front)
    edge = eye["edge"]
    w = line["half_width"]

    def off(v):
        return abs(v.co.z - line_at(line, v.co.x)[0])

    region = {v for v in bm.verts if abs(v.co.x) <= w * 1.02 and off(v) < 4 * edge
              and v.co.dot(fr) > line_at(line, v.co.x)[1] - 0.5 * m}

    def nearest(x):
        zg, d = line_at(line, x)
        p = Vector((x, 0.0, zg)) + fr * d
        return min(region, key=lambda v: (v.co - p).length)

    if cut == "bisect":
        # a clean curve: warp the region so the smile is flat, cut it with a plane, unwarp
        z0 = line["line"][0][1]
        faces = [f for f in bm.faces if all(v in region for v in f.verts)]
        verts = {v for f in faces for v in f.verts}
        for v in verts:
            v.co.z -= line_at(line, v.co.x)[0] - z0
        res = bmesh.ops.bisect_plane(bm, geom=[*faces, *{e for f in faces for e in f.edges}, *verts],
                                     plane_co=(0.0, 0.0, z0), plane_no=(0.0, 0.0, 1.0), dist=1e-6)
        new = {g for g in res["geom_cut"] if isinstance(g, bmesh.types.BMVert)}
        for v in verts | new:
            v.co.z += line_at(line, v.co.x)[0] - z0
        path = [g for g in res["geom_cut"] if isinstance(g, bmesh.types.BMEdge)
                and all(abs(x.co.x) <= w * 0.97 for x in g.verts)]
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
        region |= new
        return finish_lips(bm, obj, path, line, front, m, gap, off, edge, w)
    start, goal = nearest(-w * 0.97), nearest(w * 0.97)
    best, prev, heap = {start: 0.0}, {}, [(0.0, 0, start)]
    tick = 1
    while heap:
        c, _, v = heapq.heappop(heap)
        if v is goal:
            break
        if c > best.get(v, math.inf):
            continue
        for e in v.link_edges:
            u = e.other_vert(v)
            if u not in region:
                continue
            nc = c + e.calc_length() * (1 + 30 * (off(u) + off(v)) / 2 / edge)
            if nc < best.get(u, math.inf):
                best[u], prev[u] = nc, (v, e)
                heapq.heappush(heap, (nc, tick, u))
                tick += 1
    if goal not in prev:
        bm.free()
        return {"path_edges": 0}
    path, v = [], goal
    while v is not start:
        v, e = prev[v]
        path.append(e)
    return finish_lips(bm, obj, path, line, front, m, gap, off, edge, w)


def finish_lips(bm, obj, path, line, front, m, gap, off, edge, w):
    fr = Vector(front)
    bmesh.ops.split_edges(bm, edges=path)
    ring = [e for e in bm.edges if e.is_boundary and all(abs(x.co.x) <= w * 1.05 and off(x) < 4 * edge for x in e.verts)]
    layer = bm.faces.layers.int.get("pilot_part") or bm.faces.layers.int.new("pilot_part")
    sides = {"upper": [], "lower": []}
    for e in ring:
        f = e.link_faces[0]
        mid = (e.verts[0].co + e.verts[1].co) / 2
        sides["upper" if f.calc_center_median().z > mid.z else "lower"].append(e)
    if gap:
        for name, edges in sides.items():
            sign = 1.0 if name == "upper" else -1.0
            for v in {x for e in edges for x in e.verts}:
                v.co.z += sign * gap * m * (1.0 - min(abs(v.co.x) / w, 1.0) ** 2)
    for name, edges in sides.items():
        if not edges:
            continue
        ext = bmesh.ops.extrude_edge_only(bm, edges=edges)
        for f in [x for x in ext["geom"] if isinstance(x, bmesh.types.BMFace)]:
            f[layer] = 1
        sign = 1.0 if name == "upper" else -1.0
        for v in [x for x in ext["geom"] if isinstance(x, bmesh.types.BMVert)]:
            corner = 1.0 - min(abs(v.co.x) / w, 1.0) ** 2
            v.co -= fr * 0.5 * m
            v.co.z += sign * 0.12 * m * corner
    bm.normal_update()
    bm.to_mesh(obj.data)
    bm.free()
    return {"path_edges": len(path), "upper_edges": len(sides["upper"]), "lower_edges": len(sides["lower"])}


# ---------------------------------------------------------------------------------------------- mesh helpers
def apply_modifiers(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    old = obj.data
    obj.modifiers.clear()
    obj.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)


def tris(obj) -> int:
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def decimate(obj, target):
    t = tris(obj)
    if t > target:
        m = obj.modifiers.new("dec", "DECIMATE")
        m.ratio = target / t
        m.use_collapse_triangulate = True
        apply_modifiers(obj)


def select_only(objs, active=None):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or objs[0]


def smart_uv(obj):
    select_only([obj])
    while obj.data.uv_layers:
        obj.data.uv_layers.remove(obj.data.uv_layers[0])
    obj.data.uv_layers.new(name="UVMap")
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.003)
    bpy.ops.object.mode_set(mode="OBJECT")


def ensure_part_layer(obj, value=0):
    if "pilot_part" not in obj.data.attributes:
        a = obj.data.attributes.new("pilot_part", "INT", "FACE")
        a.data.foreach_set("value", [value] * len(obj.data.polygons))


# ------------------------------------------------------------------------------------------------- materials
def principled(name, rgb=None, rough=0.5, image=None, normal=None):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = 0.0
    if rgb is not None:
        bsdf.inputs["Base Color"].default_value = (*[srgb_to_linear(c) for c in rgb], 1.0)
        mat.diffuse_color = (*[srgb_to_linear(c) for c in rgb], 1.0)  # Workbench's colour for the review views
    if image is not None:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = image
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    if normal is not None:
        ntex = nt.nodes.new("ShaderNodeTexImage")
        ntex.image = normal
        nmap = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(ntex.outputs["Color"], nmap.inputs["Color"])
        nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def grade_source(mat, gains, stripes, pale=None):
    """Inserts the colour grade (and the crest stripes) between Meshy's base colour image and its BSDF."""
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    for name in ("Metallic",):
        for link in list(bsdf.inputs[name].links):
            nt.links.remove(link)
        bsdf.inputs[name].default_value = 0.0
    src_socket = bsdf.inputs["Base Color"].links[0].from_socket
    # the palette ramp: Meshy's luminance (linear) to the 2D's colours (gains: the stops, see palette_stops)
    bw = nt.nodes.new("ShaderNodeRGBToBW")
    nt.links.new(src_socket, bw.inputs["Color"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    stops = gains
    while len(els) < len(stops):
        els.new(0.5)
    for el, (pos, rgb) in zip(els, stops):
        el.position = pos
        el.color = (*[srgb_to_linear(c) for c in rgb], 1.0)
    nt.links.new(bw.outputs["Val"], ramp.inputs["Fac"])
    out = ramp.outputs["Color"]
    if stripes:
        tc = nt.nodes.new("ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(tc.outputs["Object"], sep.inputs[0])
        axis = "X" if abs(stripes["front"][0]) > 0.5 else "Y"
        dy = math_node(nt, "SUBTRACT", sep.outputs[axis], stripes["c_depth"])
        dyb = math_node(nt, "MULTIPLY", dy, -stripes["front_sign"])  # toward the back is positive
        dz = math_node(nt, "SUBTRACT", sep.outputs["Z"], stripes["c_z"])
        ang = math_node(nt, "ARCTAN2", dz, dyb)
        wave = math_node(nt, "SINE", math_node(nt, "MULTIPLY", ang, stripes["k"]))
        band = nt.nodes.new("ShaderNodeMapRange")
        band.interpolation_type = "SMOOTHSTEP"
        nt.links.new(wave, band.inputs["Value"])
        band.inputs["From Min"].default_value, band.inputs["From Max"].default_value = -0.25, 0.25
        mask = nt.nodes.new("ShaderNodeMapRange")
        mask.interpolation_type = "SMOOTHSTEP"
        nt.links.new(sep.outputs["Z"], mask.inputs["Value"])
        mask.inputs["From Min"].default_value, mask.inputs["From Max"].default_value = stripes["z_lo"], stripes["z_hi"]
        fac = math_node(nt, "MULTIPLY", band.outputs["Result"], mask.outputs["Result"])
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        nt.links.new(fac, mix.inputs["Factor"])
        a_in, b_in = [x for x in mix.inputs if x.type == "RGBA"][:2]
        nt.links.new(out, a_in)
        b_in.default_value = (0.70, 0.80, 0.80, 1.0)
        out = next(x for x in mix.outputs if x.type == "RGBA")
    nt.links.new(out, bsdf.inputs["Base Color"])


def map_range(nt, value, lo, hi):
    n = nt.nodes.new("ShaderNodeMapRange")
    n.clamp = True
    nt.links.new(value, n.inputs["Value"])
    n.inputs["From Min"].default_value, n.inputs["From Max"].default_value = lo, hi
    return n.outputs["Result"]


def mix_rgb(nt, blend, fac, a, b):
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = blend
    sockets = [x for x in mix.inputs if x.type == "RGBA"][:2]
    for sock, val in ((mix.inputs["Factor"], fac), *zip(sockets, (a, b))):
        if isinstance(val, (int, float, tuple)):
            sock.default_value = val
        else:
            nt.links.new(val, sock)
    return next(x for x in mix.outputs if x.type == "RGBA")


def pale_front(mat, pale, line, m):
    """The axolotl's pale front (2b): a positional two-tone mask over the graded ramp, the object-space normal facing
    the front times the height below the eyes, mixing toward the 2D's near-white mint; the source's luminance against
    the mint stop's keeps its freckles and shading. The lips stay teal as in the 2D: a band of lip_band (inner,
    outer) mouth units round the lip line (a quadratic in x fitted to it) is left out inside its half width."""
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    out = bsdf.inputs["Base Color"].links[0].from_socket
    lum = next(n for n in nt.nodes if n.type == "RGBTOBW").outputs["Val"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    nt.links.new(tc.outputs["Normal"], dot.inputs[0])
    dot.inputs[1].default_value = pale["front"]
    facing = map_range(nt, dot.outputs["Value"], *pale["facing"])
    below = map_range(nt, sep.outputs["Z"], pale["z_top"], pale["z_full"])
    fac = math_node(nt, "MULTIPLY", math_node(nt, "MULTIPLY", facing, below), pale["strength"])
    if line and line.get("line"):
        pts = np.array(line["line"], dtype=float)
        k = float(np.polyfit(pts[:, 0] ** 2, pts[:, 1], 1)[0])
        zl = math_node(nt, "ADD", math_node(nt, "MULTIPLY", math_node(nt, "MULTIPLY", sep.outputs["X"], sep.outputs["X"]), k),
                       float(pts[0, 1]))
        dz = math_node(nt, "ABSOLUTE", math_node(nt, "SUBTRACT", sep.outputs["Z"], zl))
        inner, outer = pale["lip_band"]
        off_band = map_range(nt, dz, inner * m, outer * m)
        hw = float(line["half_width"])
        off_x = map_range(nt, math_node(nt, "ABSOLUTE", sep.outputs["X"]), hw, 1.25 * hw)
        fac = math_node(nt, "MULTIPLY", fac, math_node(nt, "MAXIMUM", off_band, off_x))
    shade = math_node(nt, "MINIMUM", math_node(nt, "MAXIMUM", math_node(nt, "DIVIDE", lum, pale["lum"]), 0.75), 1.1)
    tint = mix_rgb(nt, "MULTIPLY", 1.0, (*[srgb_to_linear(c) for c in pale["rgb"]], 1.0), shade)
    nt.links.new(mix_rgb(nt, "MIX", fac, out, tint), bsdf.inputs["Base Color"])


def palette_stops(fg, tex):
    """The ramp's stops: (position in Meshy's linear luminance, the 2D's sRGB colour) for black, dark teal, teal and
    mint. The 2D's teal: its saturated pixels' median; its mint: its light pixels' median; Meshy's luminance of each
    from the same rules on its texture."""
    def lum_lin(a):
        lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
        return lin @ np.array([0.2126, 0.7152, 0.0722])

    def teal(a):
        return a[(a[:, 1] - a[:, 0] > 0.25) & (a.max(1) > 0.25)]

    def mint(a):
        return a[(a[:, 0] > 0.4) & (a[:, 1] > 0.6) & (a[:, 1] - a[:, 0] > 0.02) & (a[:, 1] - a[:, 0] < 0.25)]

    def bright_half(a):
        return a[a.max(1) >= np.median(a.max(1))]

    # the brighter half of each: the 2D is a shaded render, its medians sit in the shadow side (step 2a read grey)
    def top(a, q):
        return a[a.max(1) >= np.quantile(a.max(1), q)]

    # the pale front (face, throat, chest): the brightest third of the 2D's light pixels, the two-tone's light side
    t2, m2 = np.median(bright_half(teal(fg)), axis=0), np.median(top(mint(fg), 0.67), axis=0)
    t2 = np.clip(t2.mean() + (t2 - t2.mean()) * 1.2, 0, 1)
    m2 = np.clip(m2.mean() + (m2 - m2.mean()) * 1.1, 0, 1)
    lt, lm = float(np.median(lum_lin(teal(tex)))), float(np.median(lum_lin(mint(tex))))
    dark = tuple(float(c) * 0.45 for c in t2)
    return [(0.0, (0.02, 0.03, 0.03)), (lt * 0.3, dark), (lt, tuple(map(float, t2))), (lm, tuple(map(float, m2))),
            (min(1.0, lm * 1.6), tuple(min(1.0, float(c) * 1.05) for c in m2))]


def math_node(nt, op, a, b=None):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    for i, x in enumerate((a, b)):
        if x is None:
            continue
        if isinstance(x, (int, float)):
            n.inputs[i].default_value = float(x)
        else:
            nt.links.new(x, n.inputs[i])
    return n.outputs[0]


def bake(src, target, out_dir, res, head):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 4
    colour = bpy.data.images.new(f"{head}_colour", res, res, alpha=False)
    normal = bpy.data.images.new(f"{head}_normal", res, res, alpha=False)
    normal.colorspace_settings.name = "Non-Color"
    mat = bpy.data.materials.new(f"{head}_bake")
    mat.use_nodes = True
    target.data.materials.clear()
    target.data.materials.append(mat)
    node = mat.node_tree.nodes.new("ShaderNodeTexImage")
    mat.node_tree.nodes.active = node
    select_only([src, target], active=target)
    common = dict(use_selected_to_active=True, cage_extrusion=0.02, max_ray_distance=0.06, margin=8)
    node.image = colour
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, **common)
    node.image = normal
    bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT", **common)
    for img, name in ((colour, "colour"), (normal, "normal")):
        img.filepath_raw = str(out_dir / f"{head}_{name}.png")
        img.file_format = "PNG"
        img.save()
    return colour, normal


# --------------------------------------------------------------------------------------------- eyes, lids, mouth
def sphere_mesh(name, centre, axes, radius, n_a=32, n_p=16, polar_max=math.pi, inward=False):
    """A lat-long sphere around the gaze axis: UV u = azimuth / 2 pi, v = polar angle / pi (0 at the gaze pole).
    The object's origin is the centre."""
    f, s, u = (Vector(a) for a in axes)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    rings = []
    for j in range(1, n_p):
        th = polar_max * j / n_p
        rings.append([bm.verts.new(radius * (math.cos(th) * f + math.sin(th) * (math.cos(2 * math.pi * a / n_a) * u
                                                                                  + math.sin(2 * math.pi * a / n_a) * s)))
                      for a in range(n_a)])
    pole = bm.verts.new(radius * f)
    for a in range(n_a):
        b = (a + 1) % n_a
        face = bm.faces.new((pole, rings[0][a], rings[0][b]))
        uvs = [((a + 0.5) / n_a, 0.0), (a / n_a, 1 / n_p * polar_max / math.pi), ((a + 1) / n_a, 1 / n_p * polar_max / math.pi)]
        for loop, uv in zip(face.loops, uvs):
            loop[uvl].uv = uv
    for j in range(len(rings) - 1):
        v0, v1 = (j + 1) / n_p * polar_max / math.pi, (j + 2) / n_p * polar_max / math.pi
        for a in range(n_a):
            b = (a + 1) % n_a
            face = bm.faces.new((rings[j][a], rings[j + 1][a], rings[j + 1][b], rings[j][b]))
            for loop, uv in zip(face.loops, ((a / n_a, v0), (a / n_a, v1), ((a + 1) / n_a, v1), ((a + 1) / n_a, v0))):
                loop[uvl].uv = uv
    if polar_max >= math.pi - 1e-6:
        back = bm.verts.new(-radius * f)
        for a in range(n_a):
            b = (a + 1) % n_a
            face = bm.faces.new((back, rings[-1][b], rings[-1][a]))
            for loop, uv in zip(face.loops, (((a + 0.5) / n_a, 1.0), ((a + 1) / n_a, (n_p - 1) / n_p), (a / n_a, (n_p - 1) / n_p))):
                loop[uvl].uv = uv
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if inward:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    obj.location = centre
    for p in me.polygons:
        p.use_smooth = True
    return obj


def eye_image(name, spec, size=256):
    img = bpy.data.images.new(name, size, size, alpha=False)
    px = np.zeros((size, size, 4), dtype=np.float32)
    for r in range(size):
        v = (r + 0.5) / size
        for c in range(size):
            px[r, c, :3] = G.eye_pixel(v, (c + 0.5) / size, spec)
    px[..., 3] = 1.0
    img.pixels.foreach_set(px.ravel())
    return img


def lid_mesh(name, centre, axes, radius, beta_from, beta_to, alpha_half, thick, rim_rows=6, corner=None,
             corner_outer=None, outer_sign=1):
    """A lid: a shell over the ball from its free edge (beta_from) to its root, thinning to nothing toward its two ends
    and its root so it melts onto the ball and into the skin. The free edge is a rolled rim: a half circle of rim_rows
    rows from the outer surface round to the inner one, bulging past the edge toward the opening."""
    rows = G.lid_grid(math.radians(beta_from), math.radians(beta_to), math.radians(alpha_half), 32, 7)
    nb, na = len(rows), len(rows[0])
    if corner is not None:
        # an almond opening: the free edge bends toward corner (degrees) at the eye's corners (|alpha| >= 95 degrees),
        # where the upper and lower lids meet, instead of a level brim around the ball
        # corner_outer: the outer corner's own angle (alpha's sign outer_sign points to the outer corner)
        b0, b1 = math.radians(beta_from), math.radians(beta_to)
        for j, row in enumerate(rows):
            for i, (a, _) in enumerate(row):
                bc = math.radians(corner_outer if corner_outer is not None and a * outer_sign > 0 else corner)
                e = b0 + (bc - b0) * G.smoothstep(0.0, math.radians(95.0), abs(a))
                row[i] = (a, e + (b1 - e) * j / (nb - 1))
    bm = bmesh.new()

    def t(i, j):
        a = abs(rows[j][i][0]) / math.radians(alpha_half)
        return thick * (1 - G.smoothstep(0.55, 1.0, a)) * (1 - G.smoothstep(0.5, 1.0, j / (nb - 1)))

    inner = [[bm.verts.new(G.shell_point((0, 0, 0), axes, radius, *rows[j][i])) for i in range(na)] for j in range(nb)]
    outer = [[bm.verts.new(G.shell_point((0, 0, 0), axes, radius + t(i, j), *rows[j][i])) for i in range(na)]
             for j in range(nb)]
    toward_edge = -1.0 if beta_to > beta_from else 1.0  # the direction of beta past the free edge
    rims = [outer[0]]
    for k in range(1, rim_rows):
        phi = math.pi * k / rim_rows
        rims.append([bm.verts.new(G.shell_point(
            (0, 0, 0), axes, radius + t(i, 0) * 0.5 * (1 + math.cos(phi)), rows[0][i][0],
            rows[0][i][1] + toward_edge * math.sin(phi) * t(i, 0) * 0.5 / radius)) for i in range(na)])
    rims.append(inner[0])
    for j in range(nb - 1):
        for i in range(na - 1):
            bm.faces.new((outer[j][i], outer[j][i + 1], outer[j + 1][i + 1], outer[j + 1][i]))
            bm.faces.new((inner[j][i], inner[j + 1][i], inner[j + 1][i + 1], inner[j][i + 1]))
    for a, b in zip(rims, rims[1:]):
        for i in range(na - 1):
            bm.faces.new((b[i], b[i + 1], a[i + 1], a[i]))
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.normal_update()
    top = max(bm.faces, key=lambda f: f.calc_center_median().length)
    if top.normal.dot(top.calc_center_median()) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    obj.location = centre
    for p in me.polygons:
        p.use_smooth = True
    return obj


def delete_inside(obj, centre, radius):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    c = Vector(centre)
    dead = [f for f in bm.faces if all((v.co - c).length < radius for v in f.verts)]
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    bm.to_mesh(obj.data)
    bm.free()
    return len(dead)


# ---------------------------------------------------------------------------------------------- the smooth region
def smooth_weights(obj, eye_c, r, spec, front, left):
    """The vertex group "smooth": soft weights around each eye (eye_c: the left eye's centre after any widening)."""
    fr, lf = Vector(front), Vector(left)
    ws = []
    for v in obj.data.vertices:
        co = v.co
        w = 0.0
        for side in (1, -1):
            c = Vector((abs(eye_c.x) * side * lf.x, eye_c.y, eye_c.z))
            if spec["kind"] == "ledge":
                a, b, u = spec["centre"]
                cc = c + lf * side * a * r - fr * b * r + Vector((0, 0, u * r))
                rr = spec["radii"]
                d = co - cc
                e = math.sqrt((d.dot(lf) / (rr[0] * r)) ** 2 + (d.dot(fr) / (rr[1] * r)) ** 2 + (d.z / (rr[2] * r)) ** 2)
                w = max(w, 1 - G.smoothstep(0.3, 1.0, e))
            else:
                d = (co - c).length / r
                w = max(w, G.smoothstep(spec["inner"], spec["peak"][0], d) * (1 - G.smoothstep(spec["peak"][1], spec["outer"], d)))
        ws.append(w)
    vg = obj.vertex_groups.get("smooth") or obj.vertex_groups.new(name="smooth")
    for i, w in enumerate(ws):
        if w > 1e-3:
            vg.add([i], w, "REPLACE")
    return ws


def add_smooth(obj, iterations, lam):
    m = obj.modifiers.get("smooth") or obj.modifiers.new("smooth", "SMOOTH")
    m.iterations = max(iterations, 1)
    m.factor = lam if iterations else 0.0
    m.vertex_group = "smooth"
    m.show_viewport = m.show_render = iterations > 0
    return m


# ------------------------------------------------------------------------------------------------- rendering
def setup_render(res):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light = "STUDIO"
    sh.color_type = "TEXTURE"
    sh.show_specular_highlight = True
    sh.show_cavity = False
    scene.render.resolution_x = scene.render.resolution_y = res
    scene.render.film_transparent = False
    if scene.world is None:
        scene.world = bpy.data.worlds.new("w")
    scene.world.color = (0.17, 0.17, 0.17)
    scene.view_settings.view_transform = "Standard"
    cam = bpy.data.objects.get("pilot_cam")
    if cam is None:
        cam = bpy.data.objects.new("pilot_cam", bpy.data.cameras.new("pilot_cam"))
        scene.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    scene.camera = cam
    return cam


def shoot(cam, centre, direction, scale, path):
    d = Vector(direction).normalized()
    cam.location = Vector(centre) + d * 10.0
    z = d
    x = Vector((0.0, 0.0, 1.0)).cross(z).normalized()
    y = z.cross(x)
    cam.rotation_euler = Matrix((x, y, z)).transposed().to_euler()
    cam.data.ortho_scale = scale
    cam.data.clip_end = 30.0
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def bounds(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def load_rgb(path, size=None):
    img = bpy.data.images.load(str(path))
    if size:
        img.scale(*size)
    a = image_array(img)
    bpy.data.images.remove(img)
    return a


def save_rgb(arr, path):
    h, w = arr.shape[:2]
    img = bpy.data.images.new(path.stem, w, h, alpha=True)
    img.pixels.foreach_set(np.ascontiguousarray(arr, dtype=np.float32).ravel())
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


# --------------------------------------------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--head", required=True, choices=sorted(HEADS))
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--view2d", type=Path, required=True, help="the 2D turnaround's cut views: front.png, side.png, back.png")
    ap.add_argument("--expr", type=Path, required=True, help="the 2D expression sheet (its top-left cell is a 3/4 view)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--res", type=int, default=2048)
    ap.add_argument("--smooth", default=None, help="iterations,lambda of the smooth region (default per head)")
    ap.add_argument("--prev-views", type=Path, default=None, help="an earlier build's views/ for a middle row")
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    cfg = HEADS[args.head]
    head = args.head
    out = args.out
    (out / "views").mkdir(parents=True, exist_ok=True)
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    report = {"head": head, "src": args.src.as_posix()}

    src = import_glb(args.src)
    src.name = f"{head}_src"
    weld(src)  # UVs live on the loops: welding keeps them, and the lip smooth below needs one connected surface
    work = src.copy()
    work.data = src.data.copy()
    work.name = f"{head}_skin"
    bpy.context.collection.objects.link(work)
    weld(work)
    pix = image_array(base_image(src.active_material))

    # front: the eyes are on the front; Meshy faces glTF +Z, Blender -Y
    lo, hi = bounds([src])
    front = (0.0, -1.0, 0.0)
    left = (1.0, 0.0, 0.0)  # the character's left (up x front)
    eye = find_eyes(work, pix, cfg["eye_mask"], front, left)
    if eye["y"] > (lo.y + hi.y) / 2:
        front, left = (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0)
        eye = find_eyes(work, pix, cfg["eye_mask"], front, left)
    report.update(front=front, height=hi.z - lo.z, eye_fit=eye)
    log(f"eyes x={eye['x']:.4f} y={eye['y']:.4f} z={eye['z']:.4f} r={eye['r']:.4f} edge={eye['edge']:.4f}")
    fr, lf = Vector(front), Vector(left)

    # colour grade: the 2D's median foreground colour against the texture's
    view = load_rgb(args.view2d / "front.png")
    corner = view[2, 2, :3]
    fg = view[..., :3][(np.abs(view[..., :3] - corner).max(-1) > 0.08) & (view[..., 3] > 0.5)]
    tex = pix[..., :3][pix[..., :3].max(-1) > 0.05]
    want, have = np.median(fg, axis=0), np.median(tex, axis=0)
    gains = palette_stops(fg, tex)
    report["grade"] = {"stops": gains}
    log(f"palette stops {gains}")
    stripes = None
    if cfg["stripes"]:
        depth_axis = 1 if abs(front[1]) > 0.5 else 0
        fs = front[depth_axis]
        c_depth = (Vector((eye["x"], eye["y"], eye["z"])) - fr * 1.2 * eye["r"])[depth_axis]
        stripes = {"front": front, "front_sign": fs, "c_depth": c_depth, "c_z": eye["z"] + 0.5 * eye["r"], "k": 11.0,
                   "z_lo": eye["z"] + 0.9 * eye["r"], "z_hi": eye["z"] + 1.6 * eye["r"]}
        report["stripes"] = stripes
    pale = None
    if cfg.get("pale_front"):
        pale = dict(cfg["pale_front"], front=front, lum=gains[3][0], z_top=eye["z"] - 0.4 * eye["r"],
                    z_full=eye["z"] - 1.6 * eye["r"])
        report["pale_front"] = pale
    grade_source(src.active_material, gains, stripes)

    ensure_part_layer(work, 0)
    gills, gill_info, head_centre = {}, None, None
    if head == "axolotl":
        gills, gill_info, head_centre = cut_gills(work, eye, front)
        report["gills"] = gill_info
        log(f"gills {gill_info['stalks']} stalks from {gill_info['groups']} groups, holes filled {gill_info['holes_filled']}")
    m = cfg.get("mouth_scale") or eye["r"]
    if cfg["lip_from"] == "texture":
        line = lip_line_texture(work, pix, eye, front, m)
    else:
        line = lip_line(work, eye, front, m)
    report["lip_line"] = line
    log(f"lip line {len(line['line'])} bins, half width {line['half_width']:.4f}")
    if line["line"] and cfg["lip_smooth"][0]:
        report["lip_smooth"] = {"iterations": cfg["lip_smooth"][0], "lambda": cfg["lip_smooth"][1],
                                "vertices": smooth_lips([src, work], line, front, m, *cfg["lip_smooth"])}
        log(f"lip smooth {report['lip_smooth']}")
    if line["line"]:
        if cfg["lip_from"] == "texture":
            line = smile_line(work, line, eye, front, m)
            report["lip_line"] = line
        report["lip_cut"] = part_lips(work, line, eye, front, m, cfg["lip_gap"],
                                      "bisect" if cfg["lip_from"] == "texture" else "path")
        log(f"lip cut {report['lip_cut']}")

    if pale:
        pale_front(src.active_material, pale, line, m)
    # budget, one atlas for skin and gills, the bake
    decimate(work, cfg["skin_tris"])
    for g in gills.values():
        ensure_part_layer(g, 0)
        decimate(g, cfg.get("gill_tris", 2000))
    parts = [work, *gills.values()]
    if gills:
        roots = {n: (Vector(g["root"]) if g.get("root") else None) for n, g in gills.items()}
        select_only(parts, active=work)
        bpy.ops.object.join()
    smart_uv(work)
    colour, normal = bake(src, work, out, args.res, head)
    gill_objs = []
    for name, part_val in ((n, 10 + i) for i, n in enumerate(gill_info["names"] if gill_info else [])):
        g = split_part(work, lambda p, part_val=part_val: p == part_val, name)
        root = roots[name]
        g.data.transform(Matrix.Translation(-root))
        g.location = root
        g["root"] = list(root)
        gill_objs.append(g)
    if gill_objs:
        bm = bmesh.new()
        bm.from_mesh(work.data)
        layer = bm.faces.layers.int["pilot_part"]
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f[layer] >= 10], context="FACES")
        bm.to_mesh(work.data)
        bm.free()

    skin_mat = principled(f"{head}_skin", rough=0.55, image=colour, normal=normal)
    mouth_mat = principled(f"{head}_mouth", rgb=MOUTH_RGB, rough=0.7)
    gill_mat = principled(f"{head}_gill", rough=0.55, image=colour, normal=normal)
    gill_mat.use_backface_culling = False  # glTF doubleSided: the thin fronds show from both sides
    for o in [work, *gill_objs]:
        o.data.materials.clear()
        o.data.materials.append(skin_mat if o is work else gill_mat)
    work.data.materials.append(mouth_mat)
    parts_attr = np.empty(len(work.data.polygons), dtype=np.int32)
    work.data.attributes["pilot_part"].data.foreach_get("value", parts_attr)
    work.data.polygons.foreach_set("material_index", (parts_attr == 1).astype(np.int32))
    for o in [work, *gill_objs]:
        for p in o.data.polygons:
            p.use_smooth = True

    # reshape (after the bake, so the texture follows): widen the skull, thicken the lips
    r = eye["r"]
    zg0 = line["line"][0][1] if line["line"] else eye["z"] - 2.5 * r

    def widen(co):
        if cfg["widen"]:
            w = G.smoothstep(zg0 + 0.3 * r, eye["z"], co.z)
            co = co.copy()
            co.x *= 1 + cfg["widen"] * w
        return co

    me = work.data
    lining = set()
    for p in me.polygons:
        if parts_attr[p.index] == 1:
            lining.update(p.vertices)
    for v in me.vertices:
        co = widen(v.co)
        if cfg["lips"] and line["line"]:
            zg, d = line_at(line, co.x)
            lc = Vector((0, 0, zg0)) + fr * (line["line"][0][2] - 0.3 * m)
            w = G.ellipsoid_weight((co.x, co.dot(fr), co.z), (0.0, lc.dot(fr), zg0),
                                   (line["half_width"] * 1.2, 0.9 * m, 0.85 * m))
            if w > 0 and v.index not in lining:
                ax = Vector((co.x, 0.0, zg0)) + fr * lc.dot(fr)
                rad = co - ax
                rad.x = 0.0
                disp = rad.normalized() * cfg["lips"] * m * w  # radial from the lips' core: smooth, no mesh noise
                disp.z *= G.smoothstep(0.0, 0.35 * m, abs(co.z - zg))
                co = co + disp
                co.x *= 1 + cfg["lip_widen"] * w
        v.co = co
    eye_c = widen(Vector((eye["x"], eye["y"], eye["z"])))
    report["eye_centre_after_widen"] = list(eye_c)

    # the smooth region (the chameleon's crest-root ledge; the axolotl's eye rim) and its variant grid
    smooth_weights(work, eye_c, r, cfg["smooth_region"], front, left)
    it, lam = cfg["smooth"] if args.smooth is None else (int(args.smooth.split(",")[0]), float(args.smooth.split(",")[1]))
    report["smooth"] = {"iterations": it, "lambda": lam, "region": cfg["smooth_region"]}
    cam = setup_render(400)
    grid_rows = []
    kind = cfg["smooth_region"]["kind"]
    for side in (1, -1):
        if kind == "ledge":
            c = Vector((side * eye_c.x * lf.x, eye_c.y, eye_c.z)) - fr * 0.6 * r + Vector((0, 0, 1.3 * r))
            view_dir = lf * side
        else:
            c = Vector((side * eye_c.x * lf.x, eye_c.y, eye_c.z))
            view_dir = (fr + lf * side * 0.6).normalized()
        cells = []
        for k, (vi, vl) in enumerate(((0, 0.0), (0, 0.0), (30, 0.9), (it, lam), (200, 0.9))):
            add_smooth(work, vi, vl)
            if k == 0:  # the weights, as a colour attribute
                wa = np.zeros((len(me.vertices), 4), dtype=np.float32)
                vg = work.vertex_groups["smooth"].index
                for v in me.vertices:
                    w = next((g.weight for g in v.groups if g.group == vg), 0.0)
                    wa[v.index] = (0.2 + 0.8 * w, 0.3 * (1 - w), 0.3 * (1 - w), 1.0)
                ca = me.color_attributes.new("w", "FLOAT_COLOR", "POINT")
                ca.data.foreach_set("color", wa.ravel())
                me.color_attributes.active_color = ca
                bpy.context.scene.display.shading.color_type = "VERTEX"
            path = out / "views" / f"smooth_{side}_{k}.png"
            shoot(cam, c, view_dir, 4.5 * r, path)
            if k == 0:
                me.color_attributes.remove(me.color_attributes["w"])
                bpy.context.scene.display.shading.color_type = "TEXTURE"
            cells.append(load_rgb(path))
        grid_rows.append(np.concatenate(cells, axis=1))
    save_rgb(np.concatenate(grid_rows[::-1], axis=0), out / "smooth_grid.png")
    add_smooth(work, it, lam)
    apply_modifiers(work)
    work.vertex_groups.clear()
    if cfg.get("lip_tube") and line["line"]:
        report["lip_tube"], lip_w = lip_tube(work, line, front, m, lining, cfg["lip_tube"])
        log(f"lip tube {report['lip_tube']}")
        report["lip_texture_flattened_px"] = flatten_lips(work, lip_w, colour, normal)
        log(f"lip textures flattened over {report['lip_texture_flattened_px']} px")
    if cfg.get("lip_post") and line["line"]:
        vg = work.vertex_groups.new(name="lips_post")
        n_post = 0
        lc_d = line["line"][0][2] - 0.3 * m
        for v in work.data.vertices:
            if v.index in lining:
                continue
            w = G.ellipsoid_weight((v.co.x, v.co.dot(fr), v.co.z), (0.0, lc_d, zg0),
                                   (line["half_width"] * 1.35, 1.0 * m, 0.9 * m))
            w *= G.smoothstep(0.03 * m, 0.15 * m, abs(v.co.z - line_at(line, v.co.x)[0]))
            if w > 1e-3:
                vg.add([v.index], w, "REPLACE")
                n_post += 1
        mod = work.modifiers.new("lips_post", "SMOOTH")
        mod.iterations, mod.factor = cfg["lip_post"]
        mod.vertex_group = "lips_post"
        apply_modifiers(work)
        work.vertex_groups.clear()
        report["lip_post"] = {"iterations": cfg["lip_post"][0], "factor": cfg["lip_post"][1], "vertices": n_post}
        log(f"lip post smooth {report['lip_post']}")

    # eyes and lids
    gaze = (fr + lf * 0.0).normalized()
    eye_objs = []
    eye_img = eye_image(f"{head}_eye", cfg["eye_spec"])
    eye_img.filepath_raw = str(out / f"{head}_eye.png")
    eye_img.file_format = "PNG"
    eye_img.save()
    eye_mat = principled(f"{head}_eye", rough=cfg["eye_rough"], image=eye_img)
    lid_rgb = None
    R = r * cfg["eye_scale"]
    deleted = 0
    for side, tag in ((1, "L"), (-1, "R")):
        c = Vector((side * abs(eye_c.x) * (1 if lf.x > 0 else -1), eye_c.y, eye_c.z)) if abs(lf.x) > 0.5 else eye_c
        c = c + lf * side * cfg["eye_out"] * R
        axes = G.frame(tuple(gaze))
        if lid_rgb is None:
            samples = [sample_skin(work, colour, c + Vector((0, 0, 1.25 * R)) + fr * 0.3 * R + lf * k * R)
                       for k in (-0.4, -0.2, 0.0, 0.2, 0.4)]
            lid_rgb = tuple(float(x) for x in np.median(np.array(samples), axis=0))
        deleted += delete_inside(work, c, R * 0.995)
        ball = sphere_mesh(f"eye_{tag}", c, axes, R)
        ball.data.materials.append(eye_mat)
        eye_objs.append(ball)
        if cfg.get("catch_light"):
            # a tiny white cap on the bead, its every UV on the texture's white glint: the eye reads alive and
            # godot-check's eye_pupils finds its near-white vertices
            gdir = (fr + Vector((0, 0, 0.38)) + lf * 0.22).normalized()
            cap = sphere_mesh(f"glint_{tag}", c, G.frame(tuple(gdir)), R * 1.004, n_a=10, n_p=4,
                              polar_max=math.radians(cfg["catch_light"]))
            gu, gv, _ = cfg["eye_spec"]["glint"]
            for loop_uv in cap.data.uv_layers.active.data:
                loop_uv.uv = (gu, gv)
            cap.data.materials.append(eye_mat)
            eye_objs.append(cap)
        probe = Vector(G.shell_point((0, 0, 0), axes, 1.0, math.radians(90.0), 0.0))
        outer_sign = 1 if probe.dot(lf * side) > 0 else -1
        for kind_, (b0, b1) in (("upper", cfg["lid_upper"]), ("lower", cfg["lid_lower"])):
            params = dict(radius=R * 1.03, beta_from=b0, beta_to=b1, alpha_half=cfg["lid_alpha"],
                          thick=cfg["lid_thick"] * R, corner=cfg.get("lid_corner", {}).get(kind_),
                          corner_outer=cfg.get("lid_corner_outer", {}).get(kind_), outer_sign=outer_sign)
            lid = lid_mesh(f"lid_{kind_}_{tag}", c, axes, **params)
            report.setdefault("lids", {})[f"{kind_}_{tag}"] = dict(params, centre=list(c), axes=[list(a) for a in axes])
            eye_objs.append(lid)
        report.setdefault("eyes", {})[tag] = {"centre": list(c), "radius": R}
    lid_mat = principled(f"{head}_lid", rgb=lid_rgb, rough=0.55)
    for o in eye_objs:
        if o.name.startswith("lid_"):
            o.data.materials.append(lid_mat)
    report["skin_faces_inside_eyes_deleted"] = deleted
    report["lid_srgb"] = lid_rgb

    # the mouth cup behind the slit (its inside faces the slit) and the tongue
    mouth_objs = []
    if line["line"]:
        hw = line["half_width"] * (1 + cfg["lip_widen"])
        d0 = line["line"][0][2]
        r = m
        mc = Vector((0, 0, zg0 - 0.1 * r)) + fr * (d0 - 0.85 * r)
        cup = sphere_mesh("mouth_cup", mc, G.frame(tuple(-fr)), 1.0, n_a=24, n_p=10, polar_max=math.radians(120),
                          inward=True)
        cup.scale = (1, 1, 1)
        cx = hw * cfg["cup_x"]
        cup.data.transform(Matrix.Diagonal((cx if abs(lf.x) > 0.5 else 0.6 * r, 0.6 * r if abs(fr.y) > 0.5 else cx,
                                            0.55 * r, 1.0)))
        cup.data.materials.append(mouth_mat)
        mouth_objs.append(cup)
        if cfg["tongue"]:
            tc = Vector((0, 0, zg0 - 0.32 * r)) + fr * (d0 - 0.55 * r)
            tongue = sphere_mesh("tongue", tc, G.frame(tuple(fr)), 1.0, n_a=20, n_p=10)
            tongue.data.transform(Matrix.Diagonal((hw * 0.5, 0.42 * r, 0.14 * r, 1.0)))
            tongue.data.materials.append(principled(f"{head}_tongue", rgb=TONGUE_RGB, rough=0.45))
            mouth_objs.append(tongue)

    report["mouth_pushed_in"] = push_inside(mouth_objs, work, m) if mouth_objs else 0
    log(f"mouth vertices pushed inside the skin: {report['mouth_pushed_in']}")

    # fan the gills out from the head about their roots
    fan = []
    for g in gill_objs:
        root = Vector(g["root"])
        cen = sum((g.matrix_world @ v.co for v in g.data.vertices), Vector()) / len(g.data.vertices)
        d = (cen - root).normalized()
        n = (root - head_centre).normalized()
        axis = d.cross(n)
        if axis.length > 1e-4:
            g.rotation_mode = "QUATERNION"
            g.rotation_quaternion = Matrix.Rotation(math.radians(12.0), 4, axis.normalized()).to_quaternion()
            g.rotation_mode = "XYZ"
        fan.append(g.name)
    report["gills_fanned_deg"] = 12.0 if fan else 0.0

    # the gills' geometry along their length (spring bones in 2b bend them by weights): vertices per tenth of each
    # stalk from root to tip; every tenth well filled means no retopology is needed for the bend
    report["gill_length_bins"] = {}
    for g in gill_objs:
        pts = np.array([tuple(v.co) for v in g.data.vertices])  # local: the origin is the root
        tip = pts[np.argmax(np.linalg.norm(pts, axis=1))]
        t = pts @ tip / float(tip @ tip)
        report["gill_length_bins"][g.name] = np.histogram(np.clip(t, 0, 1), bins=10, range=(0, 1))[0].tolist()
    if gill_objs:
        log(f"gill vertices per tenth of the length, fewest: "
            f"{min(min(b) for b in report['gill_length_bins'].values())}")

    # one mesh per part kind, so the character stays within the contract's 8 surfaces; each joined part keeps its
    # pieces' pivots (eye centres, gill roots) as a custom property, exported as glTF extras for the 2b rig
    def join(objs, name):
        pivots = {o.name: [round(float(c), 6) for c in (o["root"] if o.get("root") else o.location)] for o in objs}
        select_only(objs)
        bpy.ops.object.join()
        o = bpy.context.view_layer.objects.active
        o.name = o.data.name = name
        o["pivots"] = json.dumps(pivots)
        if "root" in o:
            del o["root"]
        return o, pivots

    groups = [(f"{head}_eyes", [o for o in eye_objs if o.name.startswith(("eye_", "glint_"))]),
              (f"{head}_lids", [o for o in eye_objs if o.name.startswith("lid_")]),
              (f"{head}_gills", gill_objs), (f"{head}_mouth", mouth_objs)]
    joined = {}
    report["pivots"] = {}
    for name, objs in groups:
        if objs:
            joined[name], report["pivots"][name] = join(objs, name)
    gill_objs = [joined[f"{head}_gills"]] if f"{head}_gills" in joined else []
    final = [work, *joined.values()]
    for o in final:
        o.data.attributes.get("pilot_part") and o.data.attributes.remove(o.data.attributes["pilot_part"])
    bpy.data.objects.remove(src)
    report["tris"] = {o.name: tris(o) for o in final}
    report["tris_total"] = sum(report["tris"].values())
    log(f"tris {report['tris_total']} {report['tris']}")

    export(final, out / f"{head}.glb")
    # LOD1: skin and gills decimated further, the eye parts as they are
    lod = []
    for o in final:
        c = o.copy()
        c.data = o.data.copy()
        c.name = f"{o.name}_lod1"
        bpy.context.collection.objects.link(c)
        if o is work or o in gill_objs:
            decimate(c, max(int(tris(o) * LOD_RATIO), 200))
        lod.append(c)
    report["tris_lod1"] = sum(tris(o) for o in lod)
    export(lod, out / f"{head}_lod1.glb")
    for o in lod:
        bpy.data.objects.remove(o)
    log(f"lod1 tris {report['tris_lod1']}")

    # review views: front, side (the character's left, profile facing left as in the 2D), back, 3/4
    cam = setup_render(640)
    lo, hi = bounds(final)
    centre = (lo + hi) / 2
    scale = max(hi.x - lo.x, hi.y - lo.y, hi.z - lo.z) * 1.3
    report["review_exposure"] = match_exposure(cam, centre, fr, scale, out, view)
    log(f"review exposure {report['review_exposure']}")
    for name, d in (("front", fr), ("side", lf), ("back", -fr), ("threequarter", (fr + lf).normalized())):
        shoot(cam, centre, d, scale, out / "views" / f"{name}.png")
    compare_sheet(args, out, head)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / f"{head}.blend"), compress=True)
    (out / "build.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8", newline="\n")
    log("done")


def lum_lin(a):
    lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    return lin @ np.array([0.2126, 0.7152, 0.0722])


def match_exposure(cam, centre, fr, scale, out, view):
    """Sets the review renders' exposure so the 3D's front view has the 2D front view's median foreground brightness,
    and the background the 2D's grey: the colours are compared at the same exposure."""
    corner = view[2, 2, :3]
    fg2 = view[..., :3][(np.abs(view[..., :3] - corner).max(-1) > 0.08) & (view[..., 3] > 0.5)]
    target = float(np.median(lum_lin(fg2)))
    scene = bpy.context.scene
    scene.view_settings.exposure = 0.0
    bg = 0.17
    scene.world.color = (bg, bg, bg)
    path = out / "views" / "exposure_probe.png"
    shoot(cam, centre, fr, scale, path)
    a = load_rgb(path)[..., :3]
    bg_s = a[2, 2]
    have = float(np.median(lum_lin(a[np.abs(a - bg_s).max(-1) > 0.05])))
    ev = float(np.clip(math.log2(target / max(have, 1e-4)), -1.0, 2.5))
    scene.view_settings.exposure = ev
    corner_lin = [srgb_to_linear(float(c)) for c in corner]
    scene.world.color = tuple(c / 2 ** ev for c in corner_lin)
    return {"ev": round(ev, 3), "target_lum": round(target, 4), "had_lum": round(have, 4)}


def compare_sheet(args, out, head, cell=640):
    """2D on top (front, side, back from the turnaround; the expression sheet's first cell for 3/4), the new 3D below
    (front, side, back, 3/4): <head>_compare.png (4 x 640 px) and <head>_compare_1280.png."""
    top = [load_rgb(args.view2d / f"{n}.png", (cell, cell)) for n in ("front", "side", "back")]
    img = bpy.data.images.load(str(args.expr))
    a = image_array(img)
    bpy.data.images.remove(img)
    h, w = a.shape[:2]
    crop = a[h - h // 2:, : w // 3]  # rows are bottom-up: the top-left cell
    tmp = bpy.data.images.new("crop", crop.shape[1], crop.shape[0], alpha=True)
    tmp.pixels.foreach_set(np.ascontiguousarray(crop).ravel())
    tmp.scale(cell, cell)
    top.append(image_array(tmp))
    bpy.data.images.remove(tmp)
    names = ("front", "side", "back", "threequarter")
    bottom = [load_rgb(out / "views" / f"{n}.png", (cell, cell)) for n in names]
    gap = np.ones((8, cell * 4, 4), dtype=np.float32)
    gap[..., :3] = 0.1
    rows = [np.concatenate(bottom, axis=1), gap]  # rows are bottom-up
    if args.prev_views and all((args.prev_views / f"{n}.png").exists() for n in names):
        rows += [np.concatenate([load_rgb(args.prev_views / f"{n}.png", (cell, cell)) for n in names], axis=1), gap]
    sheet = np.concatenate([*rows, np.concatenate(top, axis=1)], axis=0)
    sheet[..., 3] = 1.0
    save_rgb(sheet, out / f"{head}_compare.png")
    small = bpy.data.images.load(str(out / f"{head}_compare.png"))
    small.scale(1280, int(1280 * sheet.shape[0] / sheet.shape[1]))
    save_rgb(image_array(small), out / f"{head}_compare_1280.png")
    bpy.data.images.remove(small)


def sstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def lip_tube(obj, line, front, m, lining, spec):
    """The chameleon's lips rebuilt (2b): two rolled tubes along the lip line, the upper above it and the lower below,
    kissing at it. The line's height and depth are even quartics fitted to its bins (no bin noise); each tube's radius
    is spec radius x m, tapering to a fifth at the corners; its front reaches the lip's measured protrusion (the 95th
    percentile in the middle third). Every lip vertex moves toward its point on the tube's circle at the same angle
    round the tube's core, fading out toward the skin above or below, behind the tube (the lining rolling back into the
    mouth) and past the corners: Meshy's lip creases are replaced by a clean rolled shape. The lining's slit edge moves
    with the lips (left out, its jagged row stayed and read as teeth between the tubes; first 2b-1 build)."""
    me = obj.data
    fr = np.array(front, dtype=float)
    pts = np.array(line["line"], dtype=float)
    hw = float(line["half_width"])
    xs = np.concatenate([-pts[:0:-1, 0], pts[:, 0]])
    cz = np.polyfit(xs, np.concatenate([pts[:0:-1, 1], pts[:, 1]]), 4)
    cd = np.polyfit(xs, np.concatenate([pts[:0:-1, 2], pts[:, 2]]), 4)
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    free = np.ones(len(co), dtype=bool)
    x, z = co[:, 0], co[:, 2]
    d = co @ fr
    xc = np.clip(x, -hw, hw)
    zl, dl = np.polyval(cz, xc), np.polyval(cd, xc)
    taper = 0.2 + 0.8 * np.sqrt(np.clip(1 - (xc / hw) ** 2, 0, 1))
    r0 = spec["radius"] * m
    r = r0 * taper
    new = co.copy()
    report = {"radius": round(r0, 5)}
    for side, s in (("upper", 1.0), ("lower", -1.0)):
        sel = free & ((z - zl) * s >= 0)
        near = sel & (np.abs(x) < 0.33 * hw) & (np.abs(z - zl) < 2.0 * r0)
        p = float(np.percentile(d[near] - dl[near], 95)) if near.any() else r0
        p = max(p, 0.6 * r0)
        cdep, czz = dl + p * taper - r, zl + s * r
        dz, dd = z - czz, d - cdep
        th = np.arctan2(s * dz, dd)  # 0: the front; positive away from the slit
        dist = np.hypot(dz, dd)
        w = (1 - sstep(math.radians(55), math.radians(115), th)) * (1 - sstep(math.radians(100), math.radians(150), -th))
        w *= (1 - sstep(1.5 * r, 2.6 * r, dist)) * (1 - sstep(0.85 * hw, 1.1 * hw, np.abs(x))) * sel
        tgt_d, tgt_z = cdep + r * np.cos(th), czz + s * r * np.sin(th)
        new[:, 2] += w * (tgt_z - z)
        new += fr[None, :] * (w * (tgt_d - d))[:, None]
        report[side] = {"protrusion": round(p, 5), "moved": int((w > 0.01).sum())}
        wmax = w if side == "upper" else np.maximum(wmax, w)
    me.vertices.foreach_set("co", new.ravel())
    me.update()
    return report, wmax


def flatten_lips(obj, weights, colour, normal, keep=0.15):
    """Meshy's lip creases live in the baked textures too (2a's smooths and 2b's tube left them showing): over the
    lips' weights (rasterised in UV space, grown by 3 px) the normal map goes flat and the colour to the lips' median,
    keeping `keep` of the old colour. Both images are saved again."""
    me = obj.data
    me.calc_loop_triangles()
    uv = np.empty(len(me.loops) * 2)
    me.uv_layers.active.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    h, w_ = colour.size[1], colour.size[0]
    acc = np.zeros((h, w_), dtype=np.float32)
    for lt in me.loop_triangles:
        ws = weights[list(lt.vertices)]
        if ws.max() < 0.02:
            continue
        t = uv[list(lt.loops)] * (w_, h) - 0.5
        x0, y0 = np.floor(t.min(0)).astype(int)
        x1, y1 = np.ceil(t.max(0)).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, w_ - 1), min(y1, h - 1)
        if x1 < x0 or y1 < y0:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
        (ax, ay), (bx, by), (cx, cy) = t
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12:
            continue
        l1 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / den
        l2 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / den
        l3 = 1 - l1 - l2
        inside = (l1 >= -0.05) & (l2 >= -0.05) & (l3 >= -0.05)
        val = np.clip(l1 * ws[0] + l2 * ws[1] + l3 * ws[2], 0, 1) * inside
        acc[y0:y1 + 1, x0:x1 + 1] = np.maximum(acc[y0:y1 + 1, x0:x1 + 1], val)
    for _ in range(3):
        grown = acc.copy()
        grown[1:] = np.maximum(grown[1:], acc[:-1])
        grown[:-1] = np.maximum(grown[:-1], acc[1:])
        grown[:, 1:] = np.maximum(grown[:, 1:], acc[:, :-1])
        grown[:, :-1] = np.maximum(grown[:, :-1], acc[:, 1:])
        acc = grown
    a = acc[..., None]
    npx = image_array(normal)
    npx[..., :3] = npx[..., :3] * (1 - a) + np.array([0.5, 0.5, 1.0]) * a
    normal.pixels.foreach_set(npx.ravel())
    cpx = image_array(colour)
    core = acc > 0.6
    if core.any():
        med = np.median(cpx[core][:, :3], axis=0)
        cpx[..., :3] = cpx[..., :3] * (1 - a * (1 - keep)) + med * a * (1 - keep)
        colour.pixels.foreach_set(cpx.ravel())
    for img in (colour, normal):
        img.save()
    return int((acc > 0.02).sum())


def push_inside(objs, skin, m):
    """Moves every vertex of objs that lies outside the skin (its lip lining aside) to just inside it: the mouth cup and
    tongue never show through the cheeks at the lip corners (step 2a's black blobs)."""
    bm = bmesh.new()
    bm.from_mesh(skin.data)
    layer = bm.faces.layers.int.get("pilot_part")
    if layer is not None:
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f[layer] == 1], context="FACES")
    bm.normal_update()
    bvh = BVHTree.FromBMesh(bm)
    moved = 0
    for o in objs:
        mw, inv = o.matrix_world, o.matrix_world.inverted()
        for v in o.data.vertices:
            co = mw @ v.co
            loc, nrm, _, _ = bvh.find_nearest(co)
            if loc is not None and (co - loc).dot(nrm) > -0.04 * m:
                v.co = inv @ (loc - nrm * 0.04 * m)
                moved += 1
    bm.free()
    return moved


def sample_skin(obj, image, point):
    """The skin's baked colour (sRGB) at the face nearest point."""
    bvh = BVHTree.FromObject(obj, bpy.context.evaluated_depsgraph_get())
    loc, _, idx, _ = bvh.find_nearest(point)
    poly = obj.data.polygons[idx]
    uv = obj.data.uv_layers.active.data
    u = sum(uv[i].uv[0] for i in poly.loop_indices) / poly.loop_total
    v = sum(uv[i].uv[1] for i in poly.loop_indices) / poly.loop_total
    pix = image_array(image)
    h, w = pix.shape[:2]
    return tuple(float(c) for c in pix[min(int(v * h), h - 1), min(int(u * w), w - 1), :3])


def export(objs, path):
    select_only(objs)
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=True, export_apply=True,
                              export_yup=True, export_animations=False, export_extras=True)


if __name__ == "__main__":
    main()
