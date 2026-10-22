"""T1 "socketed head", step 2 (art #196), in headless Blender: seats step 1's Meshy face pieces into the socketed
head and exports the kit.

    blender -b --factory-startup --python-exit-code 1 --python tools/blender/alien_t1_kit.py -- \
        --raw <2026-10-22-alien-t1-sockets-3d> --out <dir> [--grid] [--mouth-w K] [--eye-k K]
        [--ref-approved PNG --ref-h2 PNG]

- Measures the head: a front depth map (rays along +Y), its recess against a blurred envelope, the two socket
  centres and rims (a sphere fitted to each socket's bowl), the mouth dish's centre and size.
- Eyes: a clean ball per socket with a painted texture (white, brown iris, pupil, catch light; alien_pilot_geom
  .eye_pixel), its origin at the ball's centre so it turns in the socket (gaze); three lid shells per side (open, half,
  closed: alien_t1_geom.LIDS), built here instead of Meshy's lids.
- Mouths (rest, smile, sad, O) and brows (sad, raised, angry): Meshy's meshes, decimated, scaled to the dish or the
  rim, turned to the skin's normal and seated (alien_t1_geom.seat_y: the back sinks behind the skin, no gap); the O's
  back ball is cut off and a dark throat disc closes the hole. Every piece is a separate object parented to the head.
- `--grid`: renders an expression (`--grid-expr`, rest) for a grid of mouth widths x eyeball scales (`--grid-mouth`,
  `--grid-eye`) front and three-quarter (grid.jpg) and stops.
- Otherwise: the expressions (alien_t1_geom.expressions) front and three-quarter, close-ups of the mouth seam and the
  eye socket, the comparison sheet with `--ref-approved` and `--ref-h2` (the 2D rows on top), t1_chameleon_kit.glb (every node, the rest
  set marked visible in the nodes' extras: glTF has no hidden flag) and t1_expressions.json.
"""
from __future__ import annotations

import argparse
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
import alien_pilot_geom as PG  # noqa: E402
import alien_t1_geom as G  # noqa: E402

EYE_SPEC = {"iris_deg": 19.0, "pupil_deg": 9.0, "sclera": (0.96, 0.95, 0.92), "iris": (0.30, 0.13, 0.05),
            "iris_rim": (0.10, 0.04, 0.02), "pupil": (0.012, 0.008, 0.008), "glint": (0.35, 0.06, 0.024)}
THROAT = (0.10, 0.05, 0.16)
PIECE_ITEMS = {"mouth_rest": "mouth_rest", "mouth_smile": "mouth_smile", "mouth_sad": "mouth_sad",
               "mouth_o": "mouth_o", "brow": "brow"}


def log(*a):
    print("T1", *a, flush=True)


# ---------------------------------------------------------------- import and measure
def import_one(path: Path, name: str):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    for o in meshes:
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
    for o in new:
        if o.type != "MESH":
            bpy.data.objects.remove(o)
    o = meshes[0]
    o.data.transform(o.matrix_world)
    o.matrix_world = Matrix.Identity(4)
    o.name = o.data.name = name
    return o


def make_bvh(o) -> BVHTree:
    return BVHTree.FromPolygons([v.co.copy() for v in o.data.vertices], [p.vertices[:] for p in o.data.polygons])


def skin_hit(bvh, x: float, z: float, y0: float = -5.0):
    loc, nrm, _, _ = bvh.ray_cast(Vector((x, y0, z)), Vector((0.0, 1.0, 0.0)))
    return (loc, nrm) if loc is not None else (None, None)


def gauss(a: np.ndarray, sigma: float) -> np.ndarray:
    r = int(3 * sigma) + 1
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    p = np.pad(a, r, mode="edge")
    p = np.apply_along_axis(lambda v: np.convolve(v, k, mode="valid"), 1, p)
    return np.apply_along_axis(lambda v: np.convolve(v, k, mode="valid"), 0, p)


def measure(head, bvh) -> dict:
    co = np.array([v.co[:] for v in head.data.vertices])
    lo, hi = co.min(0), co.max(0)
    nx, nz = 160, 200
    xs, zs = np.linspace(lo[0], hi[0], nx), np.linspace(lo[2], hi[2], nz)
    dep = np.full((nz, nx), np.nan)
    for j, z in enumerate(zs):
        for i, x in enumerate(xs):
            loc, _ = skin_hit(bvh, x, z)
            if loc is not None:
                dep[j, i] = loc.y
    valid = ~np.isnan(dep)
    filled = np.where(valid, dep, np.nanmax(dep))
    cell = xs[1] - xs[0]
    rec = np.where(valid, filled - gauss(filled, 0.12 / cell), -1.0)
    X, Z = np.meshgrid(xs, zs)

    def blob(mask):
        r = np.where(mask & valid, rec, -1.0)
        j, i = np.unravel_index(np.argmax(r), r.shape)
        peak = r[j, i]
        near = mask & valid & (np.hypot(X - xs[i], Z - zs[j]) < 0.16) & (rec > 0.4 * peak)
        w = rec[near]
        return float((X[near] * w).sum() / w.sum()), float((Z[near] * w).sum() / w.sum()), float(peak)

    sockets = {}
    for side, sgn in (("L", 1.0), ("R", -1.0)):
        cx, cz, peak = blob((sgn * X > 0.05) & (sgn * X < 0.45) & (Z > 0.12) & (Z < 0.75))
        d = np.hypot(X - cx, Z - cz)
        rim = 0.3
        for r in np.arange(0.03, 0.3, cell):
            ring = valid & (np.abs(d - r) < cell)
            if ring.any() and rec[ring].mean() <= 0.0:
                rim = float(r)
                break
        bowl = [tuple(v) for v in co if math.hypot(v[0] - cx, v[2] - cz) < 0.75 * rim
                and abs(v[1] - dep[np.argmin(np.abs(zs - v[2])), np.argmin(np.abs(xs - v[0]))]) < 0.01]
        centre, radius = PG.fit_sphere(bowl)
        ring = valid & (np.abs(d - rim) < 1.5 * cell)
        sockets[side] = {"cx": cx, "cz": cz, "peak": peak, "rim": rim, "rim_y": float(dep[ring].mean()),
                         "bowl_centre": list(centre), "bowl_r": radius, "bowl_n": len(bowl)}
    mz = min(s["cz"] for s in sockets.values())
    # the dish: the muzzle's lips protrude, so the recess map does not find it; the centre column's front profile
    # does: the deepest valley between the nose and the chin (the hollow between the dish's upper and lower rim)
    i0 = int(np.argmin(np.abs(xs)))
    col = np.nanmean(dep[:, max(i0 - 1, 0):i0 + 2], axis=1)
    idx = np.where((zs < mz - 0.12) & (zs > mz - 0.55) & ~np.isnan(col))[0][::-1]  # top to bottom
    prof = [-float(col[j]) for j in idx]
    k, prom = PG.valley(prof)
    jv = int(idx[k])
    ju = int(idx[:k][int(np.argmax(prof[:k]))])
    jl = int(idx[k + 1:][int(np.argmax(prof[k + 1:]))])

    def lip_width(j):
        row, lim, n = dep[j], col[j] + 0.06, 0
        left = right = i0
        while right + 1 < nx and not np.isnan(row[right + 1]) and row[right + 1] < lim:
            right += 1
        while left - 1 >= 0 and not np.isnan(row[left - 1]) and row[left - 1] < lim:
            left -= 1
        return float(xs[right] - xs[left])

    dish = {"cx": 0.0, "cz": float(zs[jv]), "prominence": prom, "z_upper": float(zs[ju]), "z_lower": float(zs[jl]),
            "w": max(lip_width(ju), lip_width(jl)), "h": float(zs[ju] - zs[jl]), "y_valley": float(col[jv])}
    return {"bbox": [lo.tolist(), hi.tolist()], "sockets": sockets, "dish": dish}


# ---------------------------------------------------------------- materials
def clay_material(name: str, rgb, rough: float = 0.55):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Roughness"].default_value = rough
    return m


def srgb_to_lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def skin_colour(head, sock: dict) -> tuple:
    """The median skin colour on a ring around a socket, from the head's base-colour texture (linear)."""
    mat = head.data.materials[0]
    img = None
    for n in mat.node_tree.nodes:
        if n.type == "TEX_IMAGE" and any(l.to_socket.name == "Base Color" for l in n.outputs[0].links):
            img = n.image
    small = img.copy()
    small.scale(512, 512)
    px = np.empty(512 * 512 * 4, dtype=np.float32)
    small.pixels.foreach_get(px)
    px = px.reshape(512, 512, 4)
    uv = head.data.uv_layers.active.data
    cols = []
    for poly in head.data.polygons:
        c = poly.center
        if c.y < sock["rim_y"] + 0.05 and 1.15 * sock["rim"] < math.hypot(c.x - sock["cx"], c.z - sock["cz"]) < 1.5 * sock["rim"]:
            u, v = uv[poly.loop_indices[0]].uv
            cols.append(px[min(int(v % 1 * 512), 511), min(int(u % 1 * 512), 511), :3])
    med = np.median(np.array(cols), axis=0)
    bpy.data.images.remove(small)
    log("skin sample", len(cols), "srgb", med.round(3).tolist())
    return tuple(srgb_to_lin(float(c)) for c in med)


def eye_material() -> bpy.types.Material:
    w, h = 1024, 512
    img = bpy.data.images.new("t1_eyeball", w, h)
    px = np.zeros((h, w, 4), dtype=np.float32)
    for j in range(h):
        v = 1.0 - (j + 0.5) / h
        for i in range(0, w, 1):
            px[j, i, :3] = PG.eye_pixel(v, (i + 0.5) / w, EYE_SPEC)
    px[..., 3] = 1.0
    img.pixels.foreach_set(px.ravel())
    img.file_format = "PNG"
    img.pack()
    m = bpy.data.materials.new("t1_eyeball")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = img
    t.interpolation = "Cubic"
    nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.12
    return m


# ---------------------------------------------------------------- built pieces
def frame_axes(gaze: Vector):
    f = gaze.normalized()
    up = Vector((0, 0, 1))
    u = (up - up.dot(f) * f).normalized()
    s = f.cross(u)  # the lids use psi symmetrically, so the side axis's sign does not matter
    return f, s, u


def new_object(name: str, bm, mat, origin: Vector):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.transform(Matrix.Translation(-origin))
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    o.location = origin
    me.materials.append(mat)
    return o


def eyeball(name: str, centre: Vector, r: float, gaze: Vector, mat):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=64, radius=r)
    uvl = bm.loops.layers.uv.new("UVMap")
    for face in bm.faces:
        us = []
        for lp in face.loops:
            p = lp.vert.co.normalized()
            u = (math.atan2(p.y, p.x) / (2 * math.pi)) % 1.0
            v = math.acos(max(-1.0, min(1.0, p.z))) / math.pi
            us.append([u, 1.0 - v])
        umax = max(a[0] for a in us)
        for a in us:
            if umax - a[0] > 0.5:
                a[0] += 1.0
        for lp, a in zip(face.loops, us):
            lp[uvl].uv = a
    # local +Z -> gaze, local +X -> the head's +X (so the glint sits upper left from the front on both eyes)
    f = gaze.normalized()
    x = Vector((1, 0, 0))
    x = (x - x.dot(f) * f).normalized()
    y = f.cross(x)
    rot = Matrix((x, y, f)).transposed().to_4x4()
    bm.transform(rot)
    bm.transform(Matrix.Translation(centre))
    return new_object(name, bm, mat, centre)


def lid_shell(name: str, centre: Vector, axes, r_in: float, t0: float, state: str, mat):
    """Upper and lower lid of one state as one closed shell pair, subdivided (the free edge rolls)."""
    bm = bmesh.new()
    n_psi, n_phi, psi_half = 36, 28, math.radians(86.0)
    for upper in (True, False):
        edge, root = G.lid_span(state, upper)
        rin = r_in * (1.0 if upper else 0.985)
        grid_in, grid_out = [], []
        for j in range(n_phi + 1):
            # rows packed toward the free edge
            t = (j / n_phi) ** 1.6
            phi = edge + (root - edge) * t
            th = G.lid_thickness(phi, edge, t0)
            ri, ro = [], []
            for i in range(n_psi + 1):
                psi = -psi_half + 2 * psi_half * i / n_psi
                d = Vector(G.lid_dir(axes, math.radians(phi), psi))
                ri.append(bm.verts.new(centre + d * rin))
                ro.append(bm.verts.new(centre + d * (rin + th)))
            grid_in.append(ri)
            grid_out.append(ro)
        for j in range(n_phi):
            for i in range(n_psi):
                bm.faces.new((grid_out[j][i], grid_out[j][i + 1], grid_out[j + 1][i + 1], grid_out[j + 1][i]))
                bm.faces.new((grid_in[j][i], grid_in[j + 1][i], grid_in[j + 1][i + 1], grid_in[j][i + 1]))
        for j in (0, n_phi):
            for i in range(n_psi):
                bm.faces.new((grid_in[j][i], grid_in[j][i + 1], grid_out[j][i + 1], grid_out[j][i]))
        for i in (0, n_psi):
            for j in range(n_phi):
                bm.faces.new((grid_in[j][i], grid_out[j][i], grid_out[j + 1][i], grid_in[j + 1][i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = new_object(name, bm, mat, centre)
    mod = o.modifiers.new("subd", "SUBSURF")
    mod.levels = mod.render_levels = 2
    apply_modifiers(o)
    return o


def apply_modifiers(o):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    old = o.data
    o.modifiers.clear()
    o.data = me
    bpy.data.meshes.remove(old)


# ---------------------------------------------------------------- seated Meshy pieces
def decimate(o, ratio: float):
    mod = o.modifiers.new("dec", "DECIMATE")
    mod.ratio = ratio
    apply_modifiers(o)


def seat(o, bvh, width: float, x: float, z: float, bury: float, sink: float, tilt: float = 0.0):
    """Scales o (centred, facing -Y) to width, turns it by tilt about +Y, turns its front to the skin's normal at
    (x, z), sinks `bury` of its depth behind the skin there, then pulls its back behind the skin (G.seat_y)."""
    me = o.data
    co = np.array([v.co[:] for v in me.vertices])
    me.transform(Matrix.Translation(Vector(-(co.min(0) + co.max(0)) / 2)))
    k = width / float(np.ptp(co[:, 0]))
    depth = float(np.ptp(co[:, 1])) * k
    loc, nrm = skin_hit(bvh, x, z)
    n = nrm.normalized()
    if n.y > 0:
        n = -n
    align = Vector((0, -1, 0)).rotation_difference(n).to_matrix().to_4x4()
    me.transform(Matrix.Diagonal((k, k, k, 1.0)))
    me.transform(Matrix.Rotation(tilt, 4, "Y"))
    me.transform(align)
    me.transform(Matrix.Translation(loc - n * (depth * (0.5 - bury))))
    me.update()
    frac = (co[:, 1] - co[:, 1].min()) / max(float(np.ptp(co[:, 1])), 1e-9)
    moved = 0
    for v in me.vertices:
        w = G.seat_weight(v.normal.y, float(frac[v.index]))
        if w <= 0.0:
            continue
        hit, _ = skin_hit(bvh, v.co.x, v.co.z)
        y = G.seat_y(v.co.y, hit.y if hit is not None else None, w, sink)
        if y != v.co.y:
            v.co.y = y
            moved += 1
    me.update()
    return {"k": k, "depth": depth, "moved": moved, "at": list(loc), "frac": frac}


def float_gap(o, bvh, frac) -> float:
    """The largest distance a seated piece's back vertex stays in front of the skin (0 = none floats)."""
    worst = 0.0
    for v in o.data.vertices:
        if v.index >= len(frac) or G.seat_weight(v.normal.y, float(frac[v.index])) < 0.99:
            continue
        hit, _ = skin_hit(bvh, v.co.x, v.co.z)
        if hit is not None:
            worst = max(worst, hit.y - v.co.y)
    return worst


def cut_back(o, keep_frac: float):
    """Deletes the vertices of o (centred, facing -Y) behind keep_frac of its depth: the O mouth's back ball."""
    co = np.array([v.co[:] for v in o.data.vertices])
    y_cut = co[:, 1].min() + keep_frac * np.ptp(co[:, 1])
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y > y_cut], context="VERTS")
    bm.to_mesh(o.data)
    bm.free()


def throat(name: str, o, bvh, mat):
    """A dark disc behind the O's hole, just in front of the skin, joined into o."""
    co = np.array([v.co[:] for v in o.data.vertices])
    cx, cz = (co[:, 0].min() + co[:, 0].max()) / 2, (co[:, 2].min() + co[:, 2].max()) / 2
    r = 0.30 * np.ptp(co[:, 0])
    bm = bmesh.new()
    ring = []
    for a in range(48):
        t = 2 * math.pi * a / 48
        x, z = cx + r * math.cos(t), cz + r * 0.95 * math.sin(t)
        hit, _ = skin_hit(bvh, x, z)
        y = (hit.y if hit is not None else co[:, 1].max()) - 0.004
        ring.append(bm.verts.new((x, y, z)))
    hit, _ = skin_hit(bvh, cx, cz)
    mid = bm.verts.new((cx, hit.y - 0.004, cz))
    for a in range(48):
        bm.faces.new((mid, ring[(a + 1) % 48], ring[a]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    disc = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(disc)
    me.materials.append(mat)  # join maps it to a second slot of o
    bpy.ops.object.select_all(action="DESELECT")
    disc.select_set(True)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.join()


# ---------------------------------------------------------------- the kit
def build(raw: Path, mouth_w: float, eye_k: float, cache: dict | None = None) -> dict:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    head = import_one(raw / "head" / "multi_image_to_3d-model.glb", "head")
    bvh = make_bvh(head)
    m = measure(head, bvh)
    log("measure", json.dumps(m["sockets"]), json.dumps(m["dish"]))
    skin = skin_colour(head, m["sockets"]["L"])
    clay = clay_material("t1_clay", skin, 0.5)
    lips = clay_material("t1_lips", tuple(c * 0.85 for c in skin), 0.45)
    dark = clay_material("t1_throat", THROAT, 0.6)
    eye_mat = eye_material()
    kit = {"head": head}
    for side in G.SIDES:
        s = m["sockets"][side]
        c = Vector(s["bowl_centre"])
        r = s["bowl_r"] * eye_k
        sgn = 1.0 if side == "L" else -1.0
        gaze = Vector((sgn * 0.12, -1.0, 0.0)).normalized()
        kit[f"eye_{side}"] = eyeball(f"eye_{side}", c, r, gaze, eye_mat)
        axes = frame_axes(gaze)
        for st in G.LID_STATES:
            kit[f"lid_{side}_{st}"] = lid_shell(f"lid_{side}_{st}", c, axes, r * 1.025, r * 0.055, st, clay)
    d = m["dish"]
    seats = {}
    for mouth in G.MOUTHS:
        name = f"mouth_{mouth}"
        o = import_one(raw / name / "image_to_3d-model.glb", name)
        decimate(o, 0.35)
        if mouth == "o":
            cut_back(o, 0.42)
        o.data.materials.clear()
        o.data.materials.append(lips)
        w = d["w"] * mouth_w * (0.8 if mouth == "o" else 1.0)
        seats[name] = seat(o, bvh, w, 0.0, d["cz"], 0.35, 0.006)
        if mouth == "o":
            throat("throat", o, bvh, dark)
            o = bpy.context.view_layer.objects.active
            o.name = name
        kit[name] = o
    for side in G.SIDES:
        s = m["sockets"][side]
        sgn = 1.0 if side == "L" else -1.0
        for pose in G.BROW_POSES:
            name = f"brow_{side}_{pose}"
            o = import_one(raw / "brow" / "image_to_3d-model.glb", name)
            decimate(o, 0.25)
            o.data.materials.clear()
            o.data.materials.append(clay)
            p = G.BROWS[pose]
            c, r = s["bowl_centre"], s["bowl_r"] * eye_k
            seats[name] = seat(o, bvh, G.BROW_WIDTH * r, c[0] - sgn * 0.08 * r, c[2] + r * (G.BROW_BASE + p["lift"]),
                               0.4, 0.004, G.brow_tilt_rad(side, pose))
            kit[name] = o
    gaps = {n: round(float_gap(kit[n], bvh, seats[n]["frac"]), 4) for n in seats}
    log("seats", json.dumps({k: {"k": round(v["k"], 3), "moved": v["moved"]} for k, v in seats.items()}))
    log("float gaps", json.dumps(gaps))
    for n, o in kit.items():
        if n != "head":
            mw = o.matrix_world.copy()
            o.parent = head
            o.matrix_parent_inverse = Matrix.Identity(4)
            o.matrix_world = mw
    return {"kit": kit, "measure": m, "gaps": gaps}


# ---------------------------------------------------------------- render
def setup_render(w: int, h: int, samples: int):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    try:
        pr = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA", "HIP", "ONEAPI"):
            try:
                pr.compute_device_type = kind
                pr.get_devices()
                gpus = [d for d in pr.devices if d.type == kind]
                if gpus:
                    for d in pr.devices:
                        d.use = d.type == kind
                    sc.cycles.device = "GPU"
                    log("render device", kind)
                    break
            except TypeError:
                continue
    except Exception as e:  # noqa: BLE001 - CPU is the fallback
        log("render device CPU", e)
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    world = bpy.data.worlds.new("w")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.085, 0.085, 0.09, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
    sc.world = world
    for name, loc, power, size in (("key", (-2.6, -3.2, 2.8), 420.0, 2.8), ("fill", (3.0, -2.4, 0.6), 140.0, 3.5),
                                   ("rim", (1.8, 3.0, 2.6), 300.0, 2.0)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy, ld.size = power, size
        lo = bpy.data.objects.new(name, ld)
        sc.collection.objects.link(lo)
        lo.location = loc
        lo.rotation_euler = (Vector((0, 0, 0.2)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


def camera(name: str, target: Vector, yaw_deg: float, pitch_deg: float, height: float, lens: float = 85.0):
    cd = bpy.data.cameras.new(name)
    cd.lens, cd.sensor_fit, cd.sensor_height = lens, "VERTICAL", 24.0
    dist = (height / 2) / math.tan(math.atan(12.0 / lens))
    a, p = math.radians(yaw_deg), math.radians(pitch_deg)
    loc = target + Vector((dist * math.sin(a) * math.cos(p), -dist * math.cos(a) * math.cos(p), dist * math.sin(p)))
    co = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(co)
    co.location = loc
    co.rotation_euler = (target - loc).to_track_quat("-Z", "Y").to_euler()
    return co


def show(kit: dict, nodes, gaze_deg: float = 0.0, rest: dict | None = None):
    for n, o in kit.items():
        o.hide_render = n not in nodes
    for side in G.SIDES:
        e = kit[f"eye_{side}"]
        e.matrix_world = Matrix.Translation(rest[side].to_translation()) @ Matrix.Rotation(
            math.radians(gaze_deg), 4, "Z") @ Matrix.Translation(-rest[side].to_translation()) @ rest[side]


def render(path: Path, cam):
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.filepath = str(path)
    sc.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)


# ---------------------------------------------------------------- sheets (numpy)
def load_rgb(path: Path) -> np.ndarray:
    img = bpy.data.images.load(str(path))
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)[::-1, :, :3]  # top row first


def resize(a: np.ndarray, w: int, h: int) -> np.ndarray:
    k = max(1, int(min(a.shape[0] / h, a.shape[1] / w)))
    if k > 1:
        hh, ww = a.shape[0] // k * k, a.shape[1] // k * k
        a = a[:hh, :ww].reshape(hh // k, k, ww // k, k, 3).mean(axis=(1, 3))
    ys = np.clip(((np.arange(h) + 0.5) * a.shape[0] / h - 0.5).round().astype(int), 0, a.shape[0] - 1)
    xs = np.clip(((np.arange(w) + 0.5) * a.shape[1] / w - 0.5).round().astype(int), 0, a.shape[1] - 1)
    return a[ys][:, xs]


def save_jpg(a: np.ndarray, path: Path):
    h, w = a.shape[:2]
    img = bpy.data.images.new("sheet", w, h)
    px = np.ones((h, w, 4), dtype=np.float32)
    px[..., :3] = a[::-1]
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw = str(path)
    img.file_format = "JPEG"
    img.save(quality=90)
    bpy.data.images.remove(img)


def sheet(cells: list, cols: int, cw: int, ch: int, path: Path):
    rows = (len(cells) + cols - 1) // cols
    out = np.full((rows * ch, cols * cw, 3), 0.18, dtype=np.float32)
    for n, a in enumerate(cells):
        if a is None:
            continue
        r, c = divmod(n, cols)
        out[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw] = resize(a, cw, ch)
    save_jpg(out, path)


# ---------------------------------------------------------------- main
def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--grid", action="store_true")
    floats = lambda t: [float(x) for x in t.split(",")]  # noqa: E731
    ap.add_argument("--grid-mouth", type=floats, default=[0.85, 1.0, 1.15], help="mouth widths (x the dish's)")
    ap.add_argument("--grid-eye", type=floats, default=[0.95, 1.05, 1.15], help="eyeball scales (x the bowl's)")
    ap.add_argument("--grid-expr", default="rest")
    ap.add_argument("--mouth-w", type=float, default=1.45)
    ap.add_argument("--eye-k", type=float, default=1.15)
    ap.add_argument("--ref-approved", type=Path, help="the approved 2D expressions (3 x 2: rest smile sad / angry surprised talk)")
    ap.add_argument("--ref-h2", type=Path, help="H2's ch_expr4 (2 x 2: rest smile / sad surprised)")
    ap.add_argument("--samples", type=int, default=48)
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    if a.grid:
        cells = []
        for mw in a.grid_mouth:
            for ek in a.grid_eye:
                b = build(a.raw, mw, ek)
                kit, m = b["kit"], b["measure"]
                rest = {s: kit[f"eye_{s}"].matrix_world.copy() for s in G.SIDES}
                setup_render(320, 320, 24)
                tgt = Vector((0.0, -0.4, (m["dish"]["cz"] + m["sockets"]["L"]["cz"]) / 2 + 0.05))
                show(kit, G.expressions()[a.grid_expr]["nodes"], 0.0, rest)
                for view, yaw in (("f", 0.0), ("q", 35.0)):
                    p = a.out / f"grid_m{mw}_e{ek}_{view}.png"
                    render(p, camera(f"c{view}", tgt, yaw, 4.0, 1.25))
                    cells.append(load_rgb(p))
                log("grid", mw, ek, json.dumps(b["gaps"]))
        sheet(cells, 2 * len(a.grid_eye), 1280 // (2 * len(a.grid_eye)), 1280 // (2 * len(a.grid_eye)), a.out / "grid.jpg")
        return
    b = build(a.raw, a.mouth_w, a.eye_k)
    kit, m = b["kit"], b["measure"]
    rest = {s: kit[f"eye_{s}"].matrix_world.copy() for s in G.SIDES}
    setup_render(512, 512, a.samples)
    sL = m["sockets"]["L"]
    tgt = Vector((0.0, 0.0, 0.0))
    cams = {"front": camera("front", tgt, 0.0, 3.0, 2.05), "q": camera("q", tgt, 35.0, 3.0, 2.05)}
    exprs = G.expressions()
    shots = {}
    for e, spec in exprs.items():
        show(kit, spec["nodes"], spec["gaze_deg"], rest)
        for view in (("front", "q") if e in ("rest", "smile", "sad", "surprised", "angry") else ("front",)):
            p = a.out / f"{e}_{view}.png"
            render(p, cams[view])
            shots[(e, view)] = p
    bpy.context.scene.render.resolution_x = bpy.context.scene.render.resolution_y = 768
    show(kit, exprs["rest"]["nodes"], 0.0, rest)
    close = {"mouth": camera("cm", Vector((0.0, -0.45, m["dish"]["cz"])), 55.0, -8.0, 0.55),
             "socket": camera("cs", Vector((sL["cx"], sL["rim_y"], sL["cz"])), 42.0, 10.0, 0.6)}
    for k, c in close.items():
        render(a.out / f"close_{k}.png", c)
    sheet([load_rgb(a.out / f"close_{k}.png") for k in close], 2, 640, 640, a.out / "step2_closeups.jpg")
    if a.ref_approved and a.ref_h2:
        approved = load_rgb(a.ref_approved)
        h2 = load_rgb(a.ref_h2)
        ah, aw = approved.shape[0] // 2, approved.shape[1] // 3
        ap_cells = [approved[r * ah:(r + 1) * ah, c * aw:(c + 1) * aw] for r, c in ((0, 0), (0, 1), (0, 2), (1, 1), (1, 0))]
        hh, hw = h2.shape[0] // 2, h2.shape[1] // 2
        h2_cells = [h2[r * hh:(r + 1) * hh, c * hw:(c + 1) * hw] for r, c in ((0, 0), (0, 1), (1, 0), (1, 1))] + [None]
        five = ("rest", "smile", "sad", "surprised", "angry")
        cells = ap_cells + h2_cells + [load_rgb(shots[(e, "front")]) for e in five] + \
            [load_rgb(shots[(e, "q")]) for e in five] + \
            [load_rgb(shots[("gaze_left", "front")]), load_rgb(shots[("gaze_right", "front")]),
             load_rgb(shots[("blink", "front")]), load_rgb(a.out / "close_mouth.png"),
             load_rgb(a.out / "close_socket.png")]
        sheet(cells, 5, 256, 256, a.out / "step2_compare.jpg")
    # the kit GLB: every node, the rest set marked visible
    show(kit, set(kit), 0.0, rest)
    for n, o in kit.items():
        o["prime_visible_rest"] = n in exprs["rest"]["nodes"]
    for o in list(bpy.data.objects):
        if o.type in ("CAMERA", "LIGHT"):
            bpy.data.objects.remove(o)
    glb = a.out / "t1_chameleon_kit.glb"
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format="GLB", use_visible=False, export_extras=True,
                              export_apply=False, export_yup=True, export_image_format="AUTO",
                              export_materials="EXPORT")
    centres = {s: list(rest[s].to_translation()) for s in G.SIDES}
    doc = {"glb": glb.name, "nodes": G.node_names(), "rest": "rest", "expressions": exprs,
           "gaze": {"nodes": ["eye_L", "eye_R"], "axis": "the head's up axis (glTF +Y)",
                    "pivot": "each eye node's origin (the ball's centre)", "eye_centres_blender": centres},
           "visibility": "glTF has no hidden flag: every node is in the file; nodes' extras.prime_visible_rest "
                         "marks the rest set", "measure": m, "float_gaps": b["gaps"]}
    (a.out / "t1_expressions.json").write_text(json.dumps(doc, indent=1), encoding="utf-8", newline="\n")
    log("done", glb)


if __name__ == "__main__":
    main()
