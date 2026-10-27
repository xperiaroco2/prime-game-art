"""The throat vent's gill blade, way A step 3 (art #263 station 1; docs/ship.md "Station 1"): Meshy's image-to-3D blade
(batch 2026-10-23-ship-vent-a-body, item blade1, from our own isolated blade shot) cleaned into the one rigid blade the
vent builder (ship_interior_vent.py) places seven times on the caps' pivots.

    blender -b --python ship_vent_a_blade.py -- --in <meshy.glb> --out <dir> [--tris 500] [--tex 1024]
        [--body <body dir>] [--flip-up] [--flip-out] [--max-closed DEG]

- Clean: welded, the specks (loose bits) dropped.
- Orient by the principal axes: the longest along u (Blender x), the next out of the wall (v, Blender -y), the
  thinnest up (h, z). The thick edge (the root) goes toward the wall and the flat side down (the upper bevel facet up);
  --flip-up and --flip-out override the two guesses.
- Place: the origin on the pivot, the caps' axis: the root's back NOSE_R behind it at the blade's ends, the root's
  middle on it. Scale: the length to the caps' span; the section uniformly with the calm tilt solved so that the
  calm blade's tip stands TIP_DV out of the pivot (19 cm past the frame) and its front-projected height (the slices'
  median) is COVER of the pitch (a section thicker than that even flat is squashed in h, at most to SQUASH_MIN). The GLB holds the calm
  pose about its origin; the builder turns it down by the closed angle.
- Meshy's arch along the blade cut to BOW (front_ortho's slight arch).
- The closed angle: the smallest turn down at which the median seam seen straight from the front is SEAM or less,
  below the first turn at which a blade comes within CLEAR of the next one PITCH below (both turned) and at most
  --max-closed (r4: 33, the bottom blade's tip over the frame's bottom).
- A decimated copy (--tris) with a fresh Smart UV layout, baked from the full model (albedo, roughness, metallic, a
  tangent normal), the albedo graded per channel to the body's bronze median (--body: its finish.json).

Writes <out>/blade.glb, <out>/textures/*.png, <out>/blade.json and <out>/blade.blend."""

from __future__ import annotations

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
import ship_vent_a as A  # noqa: E402

SPAN = (-0.48 + 0.012, 0.32 - 0.012)   # ship_interior_vent: the caps' rows less 12 mm each
NOSE_R = 0.03                          # the root's back behind the pivot
TIP_DV = 0.265                         # the calm tip out of the pivot (PIVOT_V 0.33 + 0.265 = 0.595 < the 0.60 depth)
PITCH = 0.15
COVER = 2.0 / 3.0                      # the calm blade's front-projected height over the pitch
SQUASH_MIN = 0.7                       # the section's least squash in h when it is thicker than COVER (--squash-min)
CLEAR = 0.004                          # the closed blades' least gap
BOW = 0.02                             # the arch kept along the blade (front_ortho: the middle up about 2 cm)
SEAM = 0.008                           # closed: the median see-through seam straight from the front (front_closed)


def arg(k, d=None):
    a = sys.argv[sys.argv.index("--") + 1:]
    return a[a.index(k) + 1] if k in a else d


def flag(k) -> bool:
    return k in sys.argv[sys.argv.index("--") + 1:]


def co(obj) -> np.ndarray:
    return np.array([v.co[:] for v in obj.data.vertices])


def orient(hi, rep: dict) -> None:
    """The principal axes onto x (length), -y (out of the wall), z (up); the root toward +y, the flat side down."""
    p = co(hi)
    c = p.mean(0)
    w, vec = np.linalg.eigh(np.cov((p - c).T))
    e = vec[:, np.argsort(w)[::-1]]          # columns: longest, middle, thinnest
    if np.linalg.det(e) < 0:
        e[:, 2] *= -1
    # rows of R: world x, -y (out), z from the axes
    R = np.stack([e[:, 0], -e[:, 1], e[:, 2]])
    m = Matrix(np.vstack([np.hstack([R, (-R @ c)[:, None]]), [0, 0, 0, 1]]).tolist())
    hi.data.transform(m)
    p = co(hi)
    # the root: the edge (in -y, "out") whose band is thicker in z
    out = -p[:, 1]
    lo, up = np.percentile(out, 8), np.percentile(out, 92)
    th = lambda sel: float(np.ptp(p[sel, 2])) if sel.any() else 0.0   # noqa: E731
    root_out = th(out >= up) > th(out <= lo)
    if flag("--flip-out"):
        root_out = not root_out
    if root_out:   # turn 180 deg about z: the root to +y (the wall), the length stays on x
        hi.data.transform(Matrix.Rotation(math.pi, 4, "Z"))
    # the flat side: the larger area of faces facing straight along z
    up_area = sum(f.area for f in hi.data.polygons if f.normal.z > 0.95)
    dn_area = sum(f.area for f in hi.data.polygons if f.normal.z < -0.95)
    flat_up = up_area > dn_area
    if flag("--flip-up"):
        flat_up = not flat_up
    if flat_up:    # turn 180 deg about y: flat side down; x and the root stay
        hi.data.transform(Matrix.Rotation(math.pi, 4, "Y"))
    rep["orient"] = {"axes_spread": np.sqrt(np.sort(w)[::-1]).round(4).tolist(), "root_was_out": bool(root_out),
                     "flat_was_up": bool(flat_up), "flat_area": [round(up_area, 5), round(dn_area, 5)]}


def debow(hi, rep: dict) -> None:
    """Meshy's arch along the blade (its middle up) cut to BOW at the game's length: the slices' median height fitted
    by a parabola in x, all but BOW of it taken out."""
    p = co(hi)
    x0, x1 = p[:, 0].min(), p[:, 0].max()
    t = (p[:, 0] - (x0 + x1) / 2) / ((x1 - x0) / 2)        # -1 .. 1 along the blade
    bins = np.clip(((t + 1) / 2 * 20).astype(int), 0, 19)
    tc = np.array([t[bins == b].mean() for b in range(20) if (bins == b).any()])
    zc = np.array([np.median(p[bins == b, 2]) for b in range(20) if (bins == b).any()])
    k, c0 = np.polyfit(tc ** 2, zc, 1)                     # z = c0 + k t^2: k < 0 an arch, its sagitta -k
    keep = BOW * (x1 - x0) / (SPAN[1] - SPAN[0])           # BOW in Meshy's units
    sag = -float(k)
    new = k + (keep if sag > 0 else -keep)                 # keep the arch's own sense, BOW deep
    for vert, ti in zip(hi.data.vertices, t):
        vert.co.z += float((new - k) * ti * ti)
    hi.data.update()
    rep["debow"] = {"sagitta_was": round(sag / (x1 - x0) * (SPAN[1] - SPAN[0]), 4), "kept": BOW,
                    "arch_up": bool(sag > 0)}


def place(hi, rep: dict) -> None:
    """The pivot at the origin, the length on the caps' span, the section scaled and the calm tilt solved."""
    p = co(hi)
    x0, x1 = p[:, 0].min(), p[:, 0].max()
    ends = (p[:, 0] < x0 + 0.06 * (x1 - x0)) | (p[:, 0] > x1 - 0.06 * (x1 - x0))
    v = -p[:, 1]
    back = v[ends].min()                                    # the root's back at the ends
    near = ends & (v < back + 0.15 * np.ptp(v))
    hz = float(np.median(p[near, 2]))                       # the root's middle height
    sx = (SPAN[1] - SPAN[0]) / (x1 - x0)
    # pivot: x centre, v = back + NOSE_R (in unit-section units: scaled below), h = hz
    piv = np.array([(x0 + x1) / 2, 0.0, hz])
    q = p - piv
    q[:, 1] = -(v - back)                                   # v from the root's back
    q[:, 0] *= sx

    def tilt(a, s):  # the section turned tip down by a about the pivot (NOSE_R in front of the back), scaled by s
        vv = q[:, 1] * -s - NOSE_R
        hh = q[:, 2] * s
        c, sn = math.cos(-a), math.sin(-a)
        return vv * c - hh * sn, vv * sn + hh * c

    mid = np.abs(q[:, 0]) < 0.8 * np.abs(q[:, 0]).max()
    bins = ((q[mid, 0] - q[mid, 0].min()) / np.ptp(q[mid, 0]) * 16).astype(int).clip(0, 15)

    def ratio(a):    # the slices' median front-projected height (the middle 80 %) over the tip's reach, at scale 1
        vv, hh = tilt(a, 1.0)
        hm = hh[mid]
        return float(np.median([np.ptp(hm[bins == b]) for b in range(16) if (bins == b).any()])) / float(vv.max())

    want = COVER * PITCH / TIP_DV
    squash = 1.0
    q0 = q[:, 2].copy()
    if arg("--calm-tilt"):   # step 4: the calm tilt forced (the concept's claws), the squash solved for COVER at it
        a = math.radians(float(arg("--calm-tilt")))
        lo_s, hi_s = float(arg("--squash-min", SQUASH_MIN)), 1.0
        q[:, 2] = q0 * lo_s
        if ratio(a) > want:
            squash = lo_s
        else:
            for _ in range(30):
                squash = (lo_s + hi_s) / 2
                q[:, 2] = q0 * squash
                lo_s, hi_s = (squash, hi_s) if ratio(a) < want else (lo_s, squash)
        q[:, 2] = q0 * squash
    elif ratio(0.0) > want:   # thicker than COVER even flat: the section squashed in h (at most to SQUASH_MIN)
        squash = max(SQUASH_MIN, want / ratio(0.0))
        q[:, 2] *= squash
    lo, hi_a = 0.0, math.radians(70)
    if arg("--calm-tilt"):
        pass
    elif ratio(lo) > want:
        a = 0.0
    else:
        for _ in range(40):
            m_ = (lo + hi_a) / 2
            lo, hi_a = (m_, hi_a) if ratio(m_) < want else (lo, m_)
        a = (lo + hi_a) / 2
    # the section scale: the tip at TIP_DV (NOSE_R fixed behind the pivot)
    s = 1.0
    for _ in range(30):
        vv, hh = tilt(a, s)
        s *= TIP_DV / float(vv.max())
    vv, hh = tilt(a, s)
    new = np.stack([q[:, 0], -vv, hh], 1)
    for vert, c_ in zip(hi.data.vertices, new):
        vert.co = Vector(c_.tolist())
    hi.data.update()
    rep["place"] = {"length_scale": round(float(sx), 4), "section_scale": round(float(s), 4),
                    "calm_tilt_deg": round(math.degrees(a), 2), "h_squash": round(squash, 3),
                    "front_height": round(ratio(a) * TIP_DV, 4), "cover": round(ratio(a) * TIP_DV / PITCH, 3),
                    "tip_dv": round(float(vv.max()), 4), "back_dv": round(float(vv.min()), 4),
                    "h": [round(float(hh.min()), 4), round(float(hh.max()), 4)]}


def closed_angle(obj, rep: dict) -> None:
    """The closed turn (the module's docstring) and the seams calm and closed."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=bm.faces)

    def tree(a, dz, grow=0.0):
        b = bm.copy()
        if grow:
            for vert in b.verts:
                vert.co += vert.normal * grow
        b.transform(Matrix.Translation((0, 0, dz)) @ Matrix.Rotation(a, 4, "X"))
        t = BVHTree.FromBMesh(b)
        b.free()
        return t

    p = co(obj)
    mid = np.abs(p[:, 0]) < 0.8 * np.abs(p[:, 0]).max()
    bins = ((p[mid, 0] - p[mid, 0].min()) / np.ptp(p[mid, 0]) * 16).astype(int).clip(0, 15)

    def seam(deg):   # straight from the front, per slice: the upper blade's lowest h less the lower one's highest
        a = math.radians(deg)
        z = p[mid, 1] * math.sin(a) + p[mid, 2] * math.cos(a)
        return float(np.median([z[bins == b].min() - (z[bins == b].max() - PITCH) for b in range(16)
                                if (bins == b).any()]))

    first_cut = None
    for step in range(0, 71):
        a = math.radians(step)   # rotation about Blender x by +a turns the tip (-y) down
        if tree(a, 0.0, CLEAR / 2).overlap(tree(a, -PITCH, CLEAR / 2)):
            first_cut = step
            break
    top = (first_cut - 1) if first_cut is not None else 70
    if arg("--max-closed"):   # the bottom blade's closed tip must stay over the frame's bottom (vent_motion.gd)
        top = min(top, float(arg("--max-closed")))
    close = next((d / 2 for d in range(0, int(2 * top) + 1) if seam(d / 2) <= SEAM), float(top))
    rep["closed"] = {"first_cut_deg": first_cut, "closed_deg": close, "front_seam_m": round(seam(close), 4),
                     "calm_seam_m": round(seam(0.0), 4)}
    bm.free()


def grade(img, body_dir: Path | None, rep: dict) -> None:
    if not body_dir:
        return
    fin = json.loads((body_dir / "finish.json").read_text(encoding="utf-8"))
    target = np.array(fin["bronze"]["after"], np.float32)
    w, h = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
    rgb = px[..., :3]
    used = rgb.max(-1) > 0.02
    bronze = used & (rgb[..., 0] > rgb[..., 1]) & (rgb[..., 1] > rgb[..., 2])
    cur = np.median(rgb[bronze], 0) if bronze.any() else np.median(rgb[used], 0)
    gain = np.clip(target / np.maximum(cur, 1e-4), 0.5, 3.0)
    px[..., :3] = np.where(used[..., None], np.clip(rgb * gain, 0, 1), rgb)
    img.pixels[:] = px.ravel()
    img.save()
    rep["grade"] = {"before": cur.round(3).tolist(), "target": target.round(3).tolist(), "gain": gain.round(3).tolist()}


def bake(hi, out: Path, tris: int, size: int, body_dir, rep: dict):
    (out / "textures").mkdir(parents=True, exist_ok=True)
    low = hi.copy()
    low.data = hi.data.copy()
    low.name = low.data.name = "blade"
    bpy.context.scene.collection.objects.link(low)
    for o in bpy.context.scene.objects:
        o.select_set(o is low)
    bpy.context.view_layer.objects.active = low
    mod = low.modifiers.new("dec", "DECIMATE")
    mod.ratio = min(1.0, tris / max(1, sum(len(p.vertices) - 2 for p in low.data.polygons)))
    bpy.ops.object.modifier_apply(modifier=mod.name)
    tri = low.modifiers.new("tri", "TRIANGULATE")
    bpy.ops.object.modifier_apply(modifier=tri.name)
    while low.data.uv_layers:
        low.data.uv_layers.remove(low.data.uv_layers[0])
    low.data.uv_layers.new(name="UVMap")
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(50), island_margin=0.01)
    bpy.ops.object.mode_set(mode="OBJECT")
    for poly in low.data.polygons:
        poly.use_smooth = False
    low.data.materials.clear()
    rep["game_tris"] = len(low.data.polygons)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 4
    mat = bpy.data.materials.new("vent_a_blade")
    mat.use_nodes = True
    low.data.materials.append(mat)
    nt = mat.node_tree
    imgs = {}
    for key, cs in (("albedo", "sRGB"), ("rough", "Non-Color"), ("metal", "Non-Color"), ("normal", "Non-Color")):
        img = bpy.data.images.new(f"vent_a_blade_{key}", size, size, alpha=False)
        img.colorspace_settings.name = cs
        imgs[key] = img
    tex = nt.nodes.new("ShaderNodeTexImage")
    nt.nodes.active = tex
    for o in sc.objects:
        o.select_set(o in (hi, low))
    sc.view_layers[0].objects.active = low
    bk = sc.render.bake
    bk.use_selected_to_active, bk.cage_extrusion, bk.max_ray_distance, bk.margin = True, 0.01, 0.03, 8

    def run(kind, img, **kw):
        tex.image = img
        bpy.ops.object.bake(type=kind, **kw)
        img.filepath_raw = str(out / "textures" / f"{img.name}.png")
        img.file_format = "PNG"
        img.save()

    run("DIFFUSE", imgs["albedo"], pass_filter={"COLOR"})
    run("ROUGHNESS", imgs["rough"])
    run("NORMAL", imgs["normal"], normal_space="TANGENT")
    for m in hi.data.materials:   # metallic: each material emits its metallic channel for one EMIT bake
        if not (m and m.use_nodes):
            continue
        bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        outn = next((n for n in m.node_tree.nodes if n.type == "OUTPUT_MATERIAL"), None)
        if not (bsdf and outn):
            continue
        em = m.node_tree.nodes.new("ShaderNodeEmission")
        src = bsdf.inputs["Metallic"]
        if src.links:
            m.node_tree.links.new(src.links[0].from_socket, em.inputs["Color"])
        else:
            em.inputs["Color"].default_value = (src.default_value,) * 3 + (1.0,)
        m.node_tree.links.new(em.outputs[0], outn.inputs["Surface"])
    run("EMIT", imgs["metal"])
    grade(imgs["albedo"], body_dir, rep)
    nt.nodes.clear()
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(bsdf.outputs[0], outn.inputs["Surface"])

    def node(img):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = img
        return t
    nt.links.new(node(imgs["albedo"]).outputs[0], bsdf.inputs["Base Color"])
    nt.links.new(node(imgs["rough"]).outputs[0], bsdf.inputs["Roughness"])
    nt.links.new(node(imgs["metal"]).outputs[0], bsdf.inputs["Metallic"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(node(imgs["normal"]).outputs[0], nm.inputs["Color"])
    nt.links.new(nm.outputs[0], bsdf.inputs["Normal"])
    return low


SEAM_MAT = "int_halo__vent_seam"         # the lit seam's strip (the heat state; the game darkens it calm)


def seam_strip(low, rep: dict):
    """Step 4 (front_closed's lit seams): a thin emissive strip on the blade's lower edge, its own material SEAM_MAT.
    Per slice along u the blade's lowest point in the closed pose; the strip 2 mm in front of it, from 6 mm below to
    4 mm above, facing the front in the closed pose, turned back into the calm pose the GLB holds."""
    a = math.radians(rep["closed"]["closed_deg"])
    p = co(low)
    rx = Matrix.Rotation(a, 4, "X")
    q = np.array([(rx @ Vector(v.tolist()))[:] for v in p])
    x0, x1 = p[:, 0].min() + 0.01, p[:, 0].max() - 0.01
    n = 16
    pts = []
    for i in range(n + 1):
        x = x0 + (x1 - x0) * i / n
        near = np.abs(q[:, 0] - x) < (x1 - x0) / n
        k = np.argmin(q[near, 2])
        y, z = q[near][k, 1], q[near][k, 2]
        pts.append((x, y - 0.002, z))
    back = rx.inverted()
    verts, faces = [], []
    for x, y, z in pts:
        verts += [(back @ Vector((x, y, z - 0.006)))[:], (back @ Vector((x, y, z + 0.004)))[:]]
    for i in range(n):   # facing -y (the front, the tip's side)
        faces.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
    me = bpy.data.meshes.new("blade_seam")
    me.from_pydata(verts, [], faces)
    me.update()
    if me.polygons[0].normal.y > 0:
        for f in me.polygons:
            f.flip()
    me.uv_layers.new(name="UVMap")
    m = bpy.data.materials.new(SEAM_MAT)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (1.0, 0.3, 0.02, 1.0)
    b.inputs["Emission Color"].default_value = (1.0, 0.3, 0.02, 1.0)
    b.inputs["Emission Strength"].default_value = 8.0
    b.inputs["Roughness"].default_value = 0.6
    me.materials.append(m)
    ob = bpy.data.objects.new("blade_seam", me)
    bpy.context.scene.collection.objects.link(ob)
    rep["seam_strip"] = {"tris": 2 * n, "material": SEAM_MAT, "closed_low_h": round(float(min(z for _, _, z in pts)), 4)}
    return ob


def main() -> None:
    src, out = Path(arg("--in")), Path(arg("--out"))
    body = Path(arg("--body")) if arg("--body") else None
    out.mkdir(parents=True, exist_ok=True)
    rep: dict = {"source": src.as_posix()}
    hi = A.load(src)
    A.clean(hi, rep)
    orient(hi, rep)
    debow(hi, rep)
    place(hi, rep)
    rep["full_tris"] = sum(len(p.vertices) - 2 for p in hi.data.polygons)
    low = bake(hi, out, int(arg("--tris", 500)), int(arg("--tex", 1024)), body, rep)
    closed_angle(low, rep)
    strip = seam_strip(low, rep)
    p = co(low)
    rep["bounds"] = {"min": p.min(0).round(4).tolist(), "max": p.max(0).round(4).tolist()}
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "blade.blend"))
    for o in bpy.context.scene.objects:
        o.select_set(o is low or o is strip)
    bpy.ops.export_scene.gltf(filepath=str(out / "blade.glb"), export_format="GLB", use_selection=True,
                              export_yup=True, export_apply=True, export_materials="EXPORT")
    (out / "blade.json").write_text(json.dumps(rep, indent=1), encoding="utf-8", newline="\n")
    print("VENTBLADE " + json.dumps(rep))


if __name__ == "__main__":
    main()
