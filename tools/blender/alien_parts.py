"""The alien parts kit's head and face parts (art #196, step S2a): the Meshy head fitted to the body, two eye designs
(an eyeball and two lid shells each), two mouth designs (six replacement pieces each, teeth apart), two crests, the
hue material, one GLB per part and parts.json.

  blender -b --factory-startup --python-exit-code 1 --python tools/blender/alien_parts.py -- \
      --head <h3d1/multi_image_to_3d-model.glb> --ring <S1/build/neck_ring.json> --body <S1/build/alien_body.blend> \
      --hues <parts2/g-s1/*.png> --out <review/char/alien-parts-kit/S2a>

The method, in order:
1. Head: the Meshy bust (Blender units, 1.90 m) is scaled so that chin to skull top is HEAD_H and placed with its
   crest top at TOP_Z, its neck centred on the ring. The crest's waist is filled (an inflation along the normals,
   smoothed) toward the blade crest of the 10-17 sheet. The bust is cut below the neck, decimated to about TRIS
   (collapse, X symmetric), cut again at the neck; the cut's open edge is merged to 24 vertices at the ring's angles
   and lofted (Hermite, matching the body's tangent) down to the body's 24 ring vertices, which it ends on exactly.
   The ring's normals are set from the ring tangent and the loft direction, so the body (same rule) shades seamless.
2. Sockets: each eye socket is fitted with a sphere (front ray casts on the bowl); its centre and radius place the
   eyeball. Mouth: the face surface at the lip line; Crest: the forehead at the crest's front base.
3. Eyes, mouths, crests: alien_parts_geom; the lid angles are rotations about the lid's local X.
4. Checks: the decimation's deviation from the dense head, the ring weld, the closed lids' cover of the eyeball and
   the rim's clearance from the head, the mouths' contact with the head.
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
import alien_parts_geom as G  # noqa: E402

HEAD_H = 0.27  # chin to skull top, m: about 1/6.5 of the 1.75-1.8 m figure (u1)
TOP_Z = 1.795  # the crest's top, m
# S8: a shorter, unbroken neck. The Meshy head's own neck stalk (7.5 cm wide under the jaw) stacked on the body's neck
# (the ring is 11.3 cm wide), so the neck read long and waisted. The head sits NECK_DROP lower on the same ring, and
# its stalk is filled out toward the ring's size (NECK_FILL: full at the cut, none `top` m above it; only near the
# neck's axis, so the jaw and the face keep their shape). The Neck bone's weight reaches NECK_BLEND m up the stalk.
NECK_DROP = 0.022
NECK_FILL = {"top": 0.034, "fill": 0.97, "gate": (1.3, 2.0)}
NECK_BLEND = 0.026
COLLAR = 0.018  # m above the cut: the weld band smoothed around the neck (smooth_collar)
MESHY = {"chin": -0.22, "skull_top": 0.70, "top": 0.9497, "eye_x": 0.22, "eye_z": 0.205, "mouth_z": -0.075,
         "crest_base": 0.62, "neck_low": -0.30, "ear_z": 0.17}  # read off the probe of h3d1 (Meshy units)
TRIS = 10000
LIGHT_MIX = 0.42  # how far the light mask mixes the hue toward the pale tint
CREST = {"mid": 0.73, "width": 0.075, "push": 0.06, "smooth": 10}  # Meshy units: a bump round the crest's waist

EYES = {  # elevations in degrees (the lid edge's angle above the eye's forward axis); rho: lid radii / eyeball r
    "bored": {"pupil": 0.20, "iris": 0.44, "iris_col": (0.20, 0.12, 0.08), "catch": (6.0, 1.0),
              "upper": {"open": 30.0, "rest": 6.0, "half": -2.0, "closed": -12.0, "rho": (1.06, 1.13)},
              "lower": {"open": -40.0, "rest": -30.0, "half": -20.0, "closed": -6.0, "rho": (1.012, 1.05)}},
    "manic": {"pupil": 0.2094, "iris": 0.0, "iris_col": (0.05, 0.04, 0.05), "catch": (4.5, 4.5),
              "upper": {"open": 58.0, "rest": 50.0, "half": 18.0, "closed": -12.0, "rho": (1.05, 1.095)},
              "lower": {"open": -55.0, "rest": -50.0, "half": -28.0, "closed": -6.0, "rho": (1.012, 1.042)}},
}
LID_BEAD = {"upper": 0.10, "lower": 0.035}  # S7: the rolled rim's swell at the lid's edge, a share of the eyeball's r
# S7: the lower face made fuller (a smooth local sculpt of the faceless head, no jaw bone), so the open mouth shapes
# (A, E, O) sit inside it with little or no squeeze: the chin moves down and forward by these, m, fading out over
# CHIN_SCULPT's x half width, up to just under the mouth line and back to the neck's front.
CHIN_SCULPT = {"down": 0.013, "fwd": 0.026, "x_sigma": 0.046, "top_gap": 0.006}  # S8b: fuller (u1)  # 7 mm forward still read chinless
STATES = ("open", "rest", "half", "closed")
# The face materials (S5, sRGB; godot/alien/alien.gd FACE and alien_eye.gdshader hold the same): the stage-1 human
# faces' (faces/clay_kit.json: white (0.9, 0.86, 0.72), cavity (0.05, 0.012, 0.02), teeth (0.92, 0.9, 0.8) linear),
# soft-matte; the first test's glossy orange lips (0.86, 0.42, 0.36) and cold white eyes read "creepy".
from alien_face import ACCENT, EYE_ROUGH, EYE_SHADE, EYE_WHITE, FACE, INNER, LIP, LIP_ROUGH, TEETH, VISEMES  # noqa: E402,F401
HUE_PICKS = {  # g-s1 cells (col, row) and sample points in cell fractions: base (forehead) and light (throat)
    "teal": ((0, 0), (0.42, 0.27), (0.50, 0.75)),
    "coral": ((0, 1), (0.42, 0.27), (0.50, 0.75)),
    "violet": ((3, 1), (0.42, 0.27), (0.50, 0.75)),
}


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--head", required=True)
    p.add_argument("--ring", required=True)
    p.add_argument("--body", required=True)
    p.add_argument("--hues", required=True)
    p.add_argument("--out", required=True)
    return p.parse_args(sys.argv[sys.argv.index("--") + 1:])


def srgb_to_lin(c):
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


# --- hues and materials ------------------------------------------------------------------------------------------


def sample_hues(path):
    img = bpy.data.images.load(path)
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)[::-1]  # top row first
    cw, ch = w / 6, h / 2
    out = {}
    for name, ((col, row), base, light) in HUE_PICKS.items():
        res = []
        for fx, fy in (base, light):
            x, y = int((col + fx) * cw), int((row + fy) * ch)
            patch = px[y - 15:y + 16, x - 15:x + 16, :3].reshape(-1, 3)
            lum = patch @ np.array([0.2126, 0.7152, 0.0722])
            # the middle of the patch's brightness (40th to 60th percentile): neither the highlight nor the shade
            mid = patch[(lum >= np.percentile(lum, 40)) & (lum <= np.percentile(lum, 60))]
            res.append([round(float(v), 4) for v in mid.mean(axis=0)])
        out[name] = {"base_srgb": res[0], "light_srgb": res[1]}
    bpy.data.images.remove(img)
    # the light colour as a mix of the base toward a pale tint: the best single mix factor over the three hues
    pale = np.array([0.93, 0.95, 0.88])
    ks = []
    for v in out.values():
        b_, l_ = np.array(v["base_srgb"]), np.array(v["light_srgb"])
        d = pale - b_
        ks.append(float(np.dot(l_ - b_, d) / max(1e-6, np.dot(d, d))))
    # the sheet's throat sits in the key light's shade, so its sampled mix reads low: the light areas take a fixed
    # mix (LIGHT_MIX), the sampled ones are reported beside it
    return out, LIGHT_MIX, [round(x, 3) for x in ks]


def hue_material(k_light):
    """The Blender hue material: the object's `alien_hue` property (linear RGB) is the base; the masks UV's u mixes
    toward a pale tint (the light areas), v toward the accent. Soft matte."""
    m = bpy.data.materials.new("alien_hue")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_type = "OBJECT"
    attr.attribute_name = "alien_hue"
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = G.MASKS
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(uv.outputs["UV"], sep.inputs[0])
    mix1 = nt.nodes.new("ShaderNodeMix")
    mix1.data_type = "RGBA"
    nt.links.new(attr.outputs["Color"], mix1.inputs[6])
    mix1.inputs[7].default_value = (*srgb_to_lin((0.93, 0.95, 0.88)), 1)
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = k_light
    nt.links.new(sep.outputs["X"], mul.inputs[0])
    nt.links.new(mul.outputs[0], mix1.inputs[0])
    mix2 = nt.nodes.new("ShaderNodeMix")
    mix2.data_type = "RGBA"
    nt.links.new(mix1.outputs[2], mix2.inputs[6])
    mix2.inputs[7].default_value = (*srgb_to_lin(ACCENT), 1)
    mul2 = nt.nodes.new("ShaderNodeMath")
    mul2.operation = "MULTIPLY"
    mul2.inputs[1].default_value = 0.85
    nt.links.new(sep.outputs["Y"], mul2.inputs[0])
    nt.links.new(mul2.outputs[0], mix2.inputs[0])
    nt.links.new(mix2.outputs[2], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.62
    bsdf.inputs["Specular IOR Level"].default_value = 0.35
    bsdf.inputs["Sheen Weight"].default_value = 0.35
    bsdf.inputs["Sheen Roughness"].default_value = 0.6
    return m


def plain(name, srgb, rough=0.5, spec=0.5, image=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*srgb_to_lin(srgb), 1)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Specular IOR Level"].default_value = spec
    if image is not None:
        tex = m.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = image
        m.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    return m


def eye_image(name, d, out_dir):
    """The eyeball texture for the azimuthal UV (uv radius 0.5 = pi from the pole, the azimuth from local +X toward
    +Z, up): S5's eye, the same as godot/alien/alien_eye.gdshader at the rest lids (the game draws it with that
    shader, this texture is for Blender and the three.js page): stage 1's warm off-white, shaded warm toward the
    corners and under the rest upper lid, a dark iris with a darker edge ring, a near-black pupil, and one painted
    catch light up and toward -X (the viewer's left on both eyes)."""
    n = 512
    yy, xx = np.mgrid[0:n, 0:n]
    u, v = (xx + 0.5) / n - 0.5, (yy + 0.5) / n - 0.5  # Blender's pixel rows run bottom-up, as the uv's v
    th = np.hypot(u, v) * 2 * math.pi  # angle from the pole
    ph = np.arctan2(v, u)
    x, z, fwd = np.sin(th) * np.cos(ph), np.sin(th) * np.sin(ph), np.cos(th)  # local x, up, forward (-Y)
    deg = np.degrees
    white = np.array(srgb_to_lin(EYE_WHITE))
    shade = np.array(srgb_to_lin(EYE_SHADE))
    smooth = lambda a, b, t: np.clip((t - a) / (b - a), 0, 1) ** 2 * (3 - 2 * np.clip((t - a) / (b - a), 0, 1))
    side = deg(np.arctan2(np.abs(x), fwd))
    elev = deg(np.arctan2(z, np.maximum(fwd, 0) + 1e-4))
    up_edge, lo_edge = d["upper"]["rest"], d["lower"]["rest"]
    k = smooth(30.0, 80.0, side) * 0.55
    k = np.maximum(k, smooth(up_edge - 16.0, up_edge, elev) * 0.6)
    k = np.maximum(k, (1 - smooth(lo_edge, lo_edge + 8.0, elev)) * 0.3)[..., None]
    col = white * (1 - k) + white * shade * k
    from_axis = deg(th)
    iris_deg, pupil_deg = math.degrees(d["iris"]), math.degrees(d["pupil"])
    e = 0.9
    if d["iris"] > 0:
        a = (1 - smooth(iris_deg - e, iris_deg + e, from_axis))[..., None]
        ring = (smooth(iris_deg - 5.0, iris_deg, from_axis) * 0.45)[..., None]
        col = col * (1 - a) + np.array(srgb_to_lin(d["iris_col"])) * (1 - ring) * (1 - 0.2 * k) * a
    a = (1 - smooth(pupil_deg - e, pupil_deg + e, from_axis))[..., None]
    col = col * (1 - a) + np.array(srgb_to_lin((0.025, 0.02, 0.025))) * a
    cx, cz = (math.radians(t) for t in d["catch"])
    g = np.array([-math.tan(cx), math.tan(cz), 1.0])
    g /= np.linalg.norm(g)
    ga = deg(np.arccos(np.clip(x * g[0] + z * g[1] + fwd * g[2], -1, 1)))
    a = (1 - smooth(2.4, 3.4, ga))[..., None]
    col = col * (1 - a) + np.array(srgb_to_lin((1.0, 0.98, 0.95))) * a
    img = bpy.data.images.new(name, n, n, alpha=False, float_buffer=False)
    img.colorspace_settings.name = "sRGB"
    lin = col
    srgb = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1 / 2.4) - 0.055)
    px = np.concatenate([srgb, np.ones((n, n, 1))], axis=2).astype(np.float32)
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw = str(out_dir / f"{name}.png")
    img.file_format = "PNG"
    img.save()
    return img


# --- the head ----------------------------------------------------------------------------------------------------


def load_head(path):
    bpy.ops.import_scene.gltf(filepath=path)
    obs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    ob = obs[0]
    ob.data.transform(ob.matrix_world)
    ob.matrix_world = Matrix.Identity(4)
    for o in list(bpy.context.scene.objects):
        if o is not ob:
            bpy.data.objects.remove(o)
    ob.name = ob.data.name = "alien_head"
    ob.data.materials.clear()
    return ob


def inflate_crest(me):
    """Fill the crest's waist (Meshy units): push along the normals by a bump round C["mid"] (the tip and the skull
    keep their form), then smooth there."""
    C = CREST
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.normal_update()
    region = []
    for v in bm.verts:
        z = v.co.z
        w = math.exp(-((z - C["mid"]) / C["width"]) ** 2)
        if w > 0.02:
            v.co += v.normal * C["push"] * w
            region.append(v)
    for _ in range(C["smooth"]):
        bmesh.ops.smooth_vert(bm, verts=region, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bm.to_mesh(me)
    bm.free()
    return len(region)


def bisect(me, z, keep_above=True):
    bm = bmesh.new()
    bm.from_mesh(me)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-6, plane_co=(0, 0, z), plane_no=(0, 0, 1),
                           clear_inner=keep_above, clear_outer=not keep_above)
    bm.to_mesh(me)
    bm.free()


def decimate(ob, tris):
    n = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    mod = ob.modifiers.new("dec", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = min(1.0, tris / n)
    mod.use_symmetry = True
    mod.symmetry_axis = "X"
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    ob.modifiers.remove(mod)
    old = ob.data
    ob.data = me
    bpy.data.meshes.remove(old)
    return n


def boundary_loop(bm):
    edges = [e for e in bm.edges if e.is_boundary]
    vs = {v for e in edges for v in e.verts}
    return list(vs)


def ang_of(co, c):
    """The ring angle: 0 at the front (-Y), growing toward +X."""
    return math.atan2(co.x - c[0], -(co.y - c[1])) % (2 * math.pi)


def weld_neck(ob, ring, z_cut):
    """Cut at z_cut, merge the open edge to 24 vertices at the ring's angles, loft down to the ring; returns the
    ring's vertex indices and the loft's per-vertex Head weight."""
    me = ob.data
    bisect(me, z_cut)
    bm = bmesh.new()
    bm.from_mesh(me)
    n = ring["count"]
    rv = [Vector(p) for p in ring["loop"]]
    rb = [Vector(p) for p in ring["loop_below"]]
    for _ in range(3):  # enough boundary vertices that every ring angle gets some
        bnd = [e for e in bm.edges if e.is_boundary]
        if len(bnd) >= 3 * n:
            break
        bmesh.ops.subdivide_edges(bm, edges=bnd, cuts=1)
    bv = boundary_loop(bm)
    c = (sum(v.co.x for v in bv) / len(bv), sum(v.co.y for v in bv) / len(bv))
    # the cut's outline at each ring angle (the boundary polyline, read by angle)
    bv.sort(key=lambda v: ang_of(v.co, c))
    angs = [ang_of(v.co, c) for v in bv]
    targets = []
    for k in range(n):
        a = 2 * math.pi * k / n
        j = min(range(len(bv)), key=lambda i: abs((angs[i] - a + math.pi) % (2 * math.pi) - math.pi))
        targets.append(bv[j].co.copy())
    clusters = [[] for _ in range(n)]
    for v, a in zip(bv, angs):
        clusters[int(round(a / (2 * math.pi / n))) % n].append(v)
    empty = [k for k in range(n) if not clusters[k]]
    if empty:
        raise RuntimeError(f"neck cut: no boundary vertex near ring angles {empty}")
    for k in range(n):
        bmesh.ops.pointmerge(bm, verts=clusters[k], merge_co=targets[k])
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=1e-5)
    bm.verts.ensure_lookup_table()
    top = []
    for k in range(n):
        top.append(min(bm.verts, key=lambda v: (v.co - targets[k]).length))
    # even out the first two rows above the merged edge (the merge leaves long slivers)
    near = set()
    for v in top:
        for e in v.link_edges:
            o = e.other_vert(v)
            if o not in top:
                near.add(o)
    for _ in range(4):
        bmesh.ops.smooth_vert(bm, verts=list(near), factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    # the tangent at the cut: the head's own neck direction, from the row above
    tan_top = []
    for v in top:
        ups = [e.other_vert(v).co for e in v.link_edges if e.other_vert(v).co.z > v.co.z + 1e-4]
        d = (v.co - (sum(ups, Vector()) / len(ups))) if ups else Vector((0, 0, -1))
        tan_top.append(d.normalized())
    L = z_cut - ring["z"]
    steps = 5
    loops = [top]
    head_w = {}
    for s in range(1, steps + 1):
        t = s / steps
        row = []
        for k in range(n):
            p0, p1 = top[k].co, rv[k]
            m0 = tan_top[k] * L * 1.2
            m1 = (rb[k] - rv[k]).normalized() * L * 1.2
            h00, h10, h01, h11 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t, -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
            p = p0 * h00 + m0 * h10 + p1 * h01 + m1 * h11
            if s == steps:
                p = rv[k].copy()
            row.append(bm.verts.new(p))
        loops.append(row)
    for a, b in zip(loops, loops[1:]):
        for k in range(n):
            f = bm.faces.new((a[k], b[k], b[(k + 1) % n], a[(k + 1) % n]))
            f.smooth = True
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.verts.index_update()
    for s, row in enumerate(loops):
        for v in row:
            head_w[v.index] = 1.0 - 0.7 * (s / steps)  # Head 0.3 at the ring, 1.0 at the cut
    ring_idx = [v.index for v in loops[-1]]
    bm.to_mesh(me)
    bm.free()
    return ring_idx, head_w


def set_ring_normals(ob, ring, ring_idx):
    """Custom normals on the ring: (ring tangent) x (loft direction), outward; the body uses the same rule."""
    me = ob.data
    rv = [Vector(p) for p in ring["loop"]]
    rb = [Vector(p) for p in ring["loop_below"]]
    n = len(rv)
    want = {}
    for k, vi in enumerate(ring_idx):
        tg = rv[(k + 1) % n] - rv[k - 1]
        upd = rv[k] - rb[k]
        nr = tg.cross(upd).normalized()
        c = Vector((ring["centre"][0], ring["centre"][1], ring["z"]))
        if nr.dot(rv[k] - c) < 0:
            nr = -nr
        want[vi] = nr
    me.calc_normals_split() if hasattr(me, "calc_normals_split") else None
    normals = []
    for lp in me.loops:
        normals.append(want.get(lp.vertex_index, Vector((0, 0, 0))))
    # zero means "keep the auto normal"; Blender treats a zero custom normal as the default
    me.normals_split_custom_set(normals)
    return {k: list(v) for k, v in want.items()}


def head_masks(ob, eye_z, chin_z):
    """The light mask: the face below the brow and the throat's front, by the smoothed normal and the height."""
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.normal_update()
    smooth = {}
    for v in bm.verts:
        n = v.normal.copy()
        for e in v.link_edges:
            n += e.other_vert(v).normal
        smooth[v.index] = n.normalized()
    uv = bm.loops.layers.uv.new(G.MASKS)
    top = max(v.co.z for v in bm.verts)
    vals = {}
    for v in bm.verts:
        n = smooth[v.index]
        front = G.smoothstep(0.15, 0.75, -n.y)
        face = front * (1 - G.smoothstep(eye_z + 0.005, eye_z + 0.04, v.co.z))
        throat = G.smoothstep(-0.1, 0.6, -n.y) * (1 - G.smoothstep(chin_z - 0.01, chin_z + 0.02, v.co.z))
        sides = G.smoothstep(0.75, 0.95, abs(n.x))
        light = max(face, throat) * (1 - 0.6 * sides)
        acc = 0.65 * G.smoothstep(top - 0.06, top - 0.005, v.co.z)  # the crest's tip blushes
        vals[v] = (light, acc)
    for f in bm.faces:
        for lp in f.loops:
            lp[uv].uv = vals[lp.vert]
    bm.to_mesh(me)
    bm.free()


def sculpt_chin(me, ring, chin, mz, z_cut):
    """S7: a fuller lower face. Each head vertex under the mouth line moves down and forward by CHIN_SCULPT, weighted
    by a Gaussian in x, by its height (full at and under the chin, none from top_gap under the mouth line up, so the
    Mouth socket stays) and by how far in front of the neck it is (none behind the neck ring's front, so the loft and
    the weld stay). Returns the measures."""
    C = CHIN_SCULPT
    ny = ring["centre"][1] - ring["semi_axes"][1]  # the neck ring's front (front is -Y)
    band = [v.co.y for v in me.vertices if abs(v.co.x) < 0.012 and abs(v.co.z - chin) < 0.012]
    if not band:
        raise RuntimeError(f"sculpt_chin: no head vertex within 12 mm of the midline at the chin's height z {chin:.4f}: "
                           "is MESHY['chin'] still the head's chin?")
    yf = min(band)  # the chin's front
    top = mz - C["top_gap"]
    d = Vector((0.0, -C["fwd"], -C["down"]))
    n, most = 0, 0.0
    for v in me.vertices:
        p = v.co
        if p.z > top or p.z < z_cut + 0.001:
            continue
        fz = 1.0 if p.z <= chin else 1.0 - G.smoothstep(chin, top, p.z)
        fy = G.smoothstep(ny, yf + 0.012, p.y) if ny > yf + 0.012 else 0.0
        w = fz * fy * math.exp(-(p.x / C["x_sigma"]) ** 2)
        if w > 1e-4:
            v.co = p + d * w
            n += 1
            most = max(most, w)
    me.update()
    return {"moved_verts": n, "max_weight": round(most, 3), "chin_front_y": round(yf, 4), "neck_front_y": round(ny, 4),
            "top_z": round(top, 4), **C}


def fill_neck(me, ring, z_cut):
    """S8: the head's neck stalk filled out toward the ring's size: each vertex's offset from the ring's axis scaled
    in x and y, by (fill * ring semi-axis / the stalk's half size at the cut) at and under the cut, easing to 1 at
    NECK_FILL["top"] above it, and only within the stalk (its offset in stalk half sizes under gate[0], none past
    gate[1]: the jaw and the face stay). Returns the measures."""
    F = NECK_FILL
    cx, cy = ring["centre"]
    band = [v.co for v in me.vertices if abs(v.co.z - z_cut) < 0.003]
    hx = max(abs(c.x - cx) for c in band)
    hy = (max(c.y for c in band) - min(c.y for c in band)) / 2
    ky, kx = (F["fill"] * ring["semi_axes"][1] / hy, F["fill"] * ring["semi_axes"][0] / hx)
    g0, g1 = F["gate"]
    n = 0
    for v in me.vertices:
        p = v.co
        if p.z > z_cut + F["top"]:
            continue
        t = 1.0 - G.smoothstep(z_cut, z_cut + F["top"], p.z)
        d = math.hypot((p.x - cx) / hx, (p.y - cy) / hy)
        g = 1.0 - G.smoothstep(g0, g1, d)
        if t * g > 1e-4:
            p.x = cx + (p.x - cx) * (1 + (kx - 1) * t * g)
            p.y = cy + (p.y - cy) * (1 + (ky - 1) * t * g)
            n += 1
    me.update()
    return {"stalk_half_m": [round(hx, 4), round(hy, 4)], "scale_at_cut": [round(kx, 3), round(ky, 3)], "moved": n,
            **F}


def smooth_collar(me, ring, z_cut, ring_idx, passes=8):
    """S8: the weld band's circumferential ripple evened out. Each head vertex between the ring and COLLAR m above
    the cut keeps its angle and height; its distance from the ring's axis (in the ring's ellipse units) is averaged
    with its neighbours' at about the same height, so the decimated cut's waviness does not show as a ruffled collar.
    The ring row stays fixed. Returns the largest radial change (m)."""
    cx, cy = ring["centre"]
    ax, ay = ring["semi_axes"]
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    fixed = set(ring_idx)
    band = [v for v in bm.verts if v.co.z < z_cut + COLLAR and v.index not in fixed]
    rn = lambda c: math.hypot((c.x - cx) / ax, (c.y - cy) / ay)  # noqa: E731
    most = 0.0
    before = {v: v.co.copy() for v in band}
    for _ in range(4):  # first the pleats across the band: a plain relax in x and y (the heights stay)
        bmesh.ops.smooth_vert(bm, verts=band, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=False)
    for _ in range(passes):
        new = {}
        for v in band:
            nb = [e.other_vert(v) for e in v.link_edges if abs(e.other_vert(v).co.z - v.co.z) < 0.003]
            if not nb:
                continue
            new[v] = (rn(v.co) + sum(rn(o.co) for o in nb)) / (1 + len(nb))
        for v, r in new.items():
            r0 = rn(v.co)
            if r0 < 1e-6:
                continue
            k = r / r0
            old = v.co.copy()
            v.co.x = cx + (v.co.x - cx) * k
            v.co.y = cy + (v.co.y - cy) * k
    most = max((v.co - before[v]).length for v in band)
    bm.to_mesh(me)
    bm.free()
    return round(most * 1000, 2)


def smart_uv(ob):
    me = ob.data
    if "UVMap" not in me.uv_layers:
        me.uv_layers.new(name="UVMap")
    me.uv_layers.active = me.uv_layers["UVMap"]
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.01)
    bpy.ops.object.mode_set(mode="OBJECT")
    # the masks layer stays the second layer
    me.uv_layers.active_index = 0
    for i, l in enumerate(me.uv_layers):
        l.active_render = i == 0


def deviation(dense_bvh, ob, z_min, height):
    pts = [v.co for v in ob.data.vertices if v.co.z > z_min]
    d = []
    for p in pts:
        hit = dense_bvh.find_nearest(p)
        if hit[0] is not None:
            d.append(hit[3])
    d = np.array(d)
    return {"mean_pct": round(float(d.mean()) / height * 100, 3), "p95_pct": round(float(np.percentile(d, 95)) / height * 100, 3),
            "max_pct": round(float(d.max()) / height * 100, 3), "mean_mm": round(float(d.mean()) * 1000, 2),
            "max_mm": round(float(d.max()) * 1000, 2), "verts": len(d)}


def fit_sphere(pts):
    A = np.c_[2 * pts, np.ones(len(pts))]
    b = (pts ** 2).sum(axis=1)
    x, *_ = np.linalg.lstsq(A, b, rcond=None)
    c = x[:3]
    return c, math.sqrt(x[3] + c.dot(c))


def socket_fit(bvh, guess, rg):
    """A sphere through the socket bowl: front rays over the socket, the points behind the rim, two passes."""
    pts = []
    for i in range(41):
        for j in range(41):
            x = guess.x + rg * (i / 20 - 1)
            z = guess.z + rg * (j / 20 - 1)
            hit = bvh.ray_cast(Vector((x, guess.y - 1.0, z)), Vector((0, 1, 0)))
            if hit[0] is not None:
                pts.append(tuple(hit[0]))
    pts = np.array(pts)
    rim = pts[:, 1].min()
    bowl = pts[pts[:, 1] > rim + 0.35 * rg]
    c, r = fit_sphere(bowl)
    for _ in range(2):
        d = np.linalg.norm(bowl - c, axis=1)
        bowl = bowl[np.abs(d - r) < 0.15 * r]
        c, r = fit_sphere(bowl)
    resid = float(np.abs(np.linalg.norm(bowl - c, axis=1) - r).mean())
    centroid = bowl.mean(axis=0)
    return Vector(c), r, Vector(centroid), {"points": int(len(bowl)), "resid_mm": round(resid * 1000, 2)}


def inside(bvh, p):
    hit = bvh.find_nearest(p)
    if hit[0] is None:
        return False, 1.0
    d = (p - hit[0])
    s = 1.0 if d.dot(hit[1]) >= 0 else -1.0
    return s < 0, s * d.length


# --- mouths ------------------------------------------------------------------------------------------------------

MOUTHS = {
    # w: half width (m); lips: (half height b, out a) per lip; line: corner drop; open: (up, low) at centre;
    # prof: opening profile exponent; push: pucker (m); sink: share of the lip below the skin
    "frog": {"w": 0.054, "up": (0.0095, 0.0095), "lo": (0.0125, 0.0120), "line": 0.0050, "bow": 0.0014,
             "sink": 0.35, "push_up": 0.0, "push_lo": 0.0,
             "shapes": {"rest": {}, "M": {"w": 0.94, "b": 0.78, "a": 0.72, "sink": 0.52, "line": 0.002},
                        "small": {"w": 0.96, "open": (0.0015, 0.0045)},
                        "A": {"w": 0.88, "open": (0.003, 0.021), "prof": 0.7},
                        "E": {"w": 1.07, "open": (0.0025, 0.0075), "prof": 0.25, "line": 0.0},
                        "O": {"w": 0.56, "open": (0.006, 0.010), "prof": 0.5, "push": 0.007, "b": 1.1, "a": 1.15}}},
    "overbite": {"w": 0.046, "up": (0.0105, 0.0110), "lo": (0.0075, 0.0070), "line": 0.0035, "bow": 0.0015,
                 "sink": 0.35, "push_up": 0.005, "push_lo": -0.002,
                 "shapes": {"rest": {"open": (0.0, 0.0085)}, "M": {"w": 0.95, "open": (0.0, 0.0), "b": 0.85},
                            "small": {"open": (0.0005, 0.010)},
                            "A": {"w": 0.9, "open": (0.002, 0.022), "prof": 0.7},
                            "E": {"w": 1.08, "open": (0.001, 0.010), "prof": 0.25, "line": 0.0},
                            "O": {"w": 0.6, "open": (0.004, 0.013), "prof": 0.5, "push": 0.006, "b": 1.1}}},
}


def surf(bvh, x, z):
    hit = bvh.ray_cast(Vector((x, -1.0, z)), Vector((0, 1, 0)))
    if hit[0] is None:
        raise RuntimeError(f"no face at x={x:.3f} z={z:.3f}")
    n = hit[1]
    if n.y > 0:
        n = -n
    return hit[0], n


def lip_curves(d, sh, z0):
    """Per s in [-1, 1]: the lip centre heights, radii and pushes of one viseme."""
    w = d["w"] * sh.get("w", 1.0)
    ou, ol = sh.get("open", (0.0, 0.0))
    pe = sh.get("prof", 1.0)
    line = sh.get("line", d["line"])
    kb, ka = sh.get("b", 1.0), sh.get("a", 1.0)
    push = sh.get("push", 0.0)
    sink = sh.get("sink", d["sink"])
    out = []
    N = 25
    for i in range(N):
        s = -1 + 2 * i / (N - 1)
        env = max(0.0, 1 - s * s)
        taper = 0.28 + 0.72 * env ** 0.45
        g = env ** pe if pe > 0 else 1.0
        zl = z0 - line * s * s
        bu, au = d["up"][0] * kb * taper, d["up"][1] * ka * taper
        bl, al = d["lo"][0] * kb * taper, d["lo"][1] * ka * taper
        bow = -d["bow"] * math.exp(-(s / 0.16) ** 2) * (1 if ou < 0.003 else 0.3)
        zu = zl + bu * 0.82 + ou * g + bow
        zo = zl - bl * 0.82 - ol * g
        pu = (d["push_up"] + push * env) * env ** 0.3
        pl = (d["push_lo"] + push * env) * env ** 0.3
        out.append({"s": s, "x": s * w, "zu": zu, "zl": zo, "bu": bu, "au": au, "bl": bl, "al": al, "pu": pu,
                    "pl": pl, "sink": sink + 0.25 * (1 - env)})
    return out


def build_mouth(bvh, d, name, z0, mats, coll, origin, teeth=False):
    sh = d["shapes"][name.split("_")[-1]]
    cur = lip_curves(d, sh, z0)
    b = G.Built()
    mi_lip = b.slot(mats["lip"])
    mi_in = b.slot(mats["inner"])
    for lip in ("u", "l"):
        cs, ra, rb_, ns = [], [], [], []
        for q in cur:
            z = q["zu"] if lip == "u" else q["zl"]
            a, bb = (q["au"], q["bu"]) if lip == "u" else (q["al"], q["bl"])
            p, n = surf(bvh, q["x"], z)
            cs.append(p + n * (a * (1 - q["sink"]) + (q["pu"] if lip == "u" else q["pl"])))
            ra.append(a)
            rb_.append(bb)
            ns.append(n)
        G.tube(b, cs, ra, rb_, ns, mi_lip, seg=12)
    gap = max(q["zu"] - q["bu"] * 0.55 - (q["zl"] + q["bl"] * 0.55) for q in cur)
    if gap > 0.0005 or sh.get("open", (0, 0))[1] > 0:  # the dark inner cup between the lips, tucked under them
        rows = 5
        grid = []
        for q in cur:
            top = q["zu"] - q["bu"] * 0.35
            bot = q["zl"] + q["bl"] * 0.35
            if top < bot:
                top = bot = (top + bot) / 2
            col = []
            for j in range(rows):
                f = j / (rows - 1)
                z = top + (bot - top) * f
                p, n = surf(bvh, q["x"], z)
                pu = q["pu"] + (q["pl"] - q["pu"]) * f
                col.append(b.vert(p + n * (0.0012 + max(0.0, pu) * 0.6)))
            grid.append(col)
        for i in range(len(grid) - 1):
            for j in range(rows - 1):
                b.face((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]), mi_in)
    ob = G.to_object(b, f"mouth_{name}", coll, origin)
    return ob, cur


def build_teeth(bvh, d, z0, mat, coll, origin):
    cur = lip_curves(d, d["shapes"]["rest"], z0)
    q = cur[len(cur) // 2]
    b = G.Built()
    mi = b.slot(mat)
    tw, th, td = 0.0095, 0.0135, 0.005
    for sx in (-1, 1):
        x = sx * 0.0060
        ztop = q["zu"] - q["bu"] * 0.25
        zc = ztop - th / 2
        p, n = surf(bvh, x, zc)
        c = p + n * (td / 2 + 0.0004 + q["pu"] * 0.5)
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=0.32, segments=3, affect="EDGES", profile=0.5)
        for v in bm.verts:
            lv = Vector((v.co.x * tw, v.co.y * td, v.co.z * th))
            v.co = c + G.frame(Vector(), n).to_3x3() @ lv
        for f in bm.faces:
            vs = [b.vert(v.co) for v in f.verts]
            b.face(vs, mi)
        bm.free()
    bmesh.ops.remove_doubles(b.bm, verts=b.bm.verts[:], dist=1e-7)
    return G.to_object(b, "mouth_overbite_teeth", coll, origin)


# --- main --------------------------------------------------------------------------------------------------------


def main():
    a = parse_args()
    out = Path(a.out)
    (out / "export").mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    coll = scene.collection
    rep = {}
    ring = G.densify_ring(json.loads(Path(a.ring).read_text(encoding="utf-8")))
    rep["ring"] = {"count": ring["count"],"z": ring["z"], "centre": ring["centre"], "semi_axes": ring["semi_axes"]}
    hues, k_light, ks = sample_hues(a.hues)
    rep["hues"] = {"samples": hues, "light_mix": k_light, "light_mix_per_hue": ks}

    # the body's Head and Neck bones
    with bpy.data.libraries.load(a.body, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n == "CharacterArmature"]
    arm = dst.objects[0]
    bones = {n: list(arm.matrix_world @ arm.data.bones[n].head_local) for n in ("Neck", "Head")}
    rep["bones"] = bones
    bpy.data.objects.remove(arm)

    # 1. the head
    ob = load_head(a.head)
    me = ob.data
    rep["meshy_tris"] = len(me.polygons)
    rep["crest_region_verts"] = inflate_crest(me)
    s = HEAD_H / (MESHY["skull_top"] - MESHY["chin"])
    # the neck's centre at the Meshy neck_low level
    band = [v.co for v in me.vertices if abs(v.co.z - MESHY["neck_low"]) < 0.01]
    ncx = (min(p.x for p in band) + max(p.x for p in band)) / 2
    ncy = (min(p.y for p in band) + max(p.y for p in band)) / 2
    top_z = TOP_Z - NECK_DROP
    T = Matrix.Translation((ring["centre"][0] - ncx * s, ring["centre"][1] - ncy * s, top_z - MESHY["top"] * s))
    me.transform(T @ Matrix.Scale(s, 4))
    W = lambda zm: top_z - (MESHY["top"] - zm) * s  # noqa: E731  Meshy height -> world height
    chin = W(MESHY["chin"])
    z_cut = min(W(MESHY["neck_low"]), chin - 0.02)
    rep["scale"] = round(s, 5)
    rep["chin_z"] = round(chin, 4)
    rep["neck_cut_z"] = round(z_cut, 4)
    nb = [v.co for v in me.vertices if abs(v.co.z - z_cut) < 0.003]
    rep["head_neck_at_cut_m"] = [round(max(p.x for p in nb) - min(p.x for p in nb), 4),
                                 round(max(p.y for p in nb) - min(p.y for p in nb), 4)]
    rep["ring_size_m"] = [round(2 * ring["semi_axes"][0], 4), round(2 * ring["semi_axes"][1], 4)]
    bisect(me, z_cut - 0.01)
    rep["neck_fill"] = fill_neck(me, ring, z_cut)
    rep["neck_drop"] = NECK_DROP
    dense = me.copy()
    dense_bvh = BVHTree.FromPolygons([v.co.copy() for v in dense.vertices], [tuple(p.vertices) for p in dense.polygons])
    rep["dense_tris"] = sum(len(p.vertices) - 2 for p in dense.polygons)
    decimate(ob, TRIS)
    ring_idx, head_w = weld_neck(ob, ring, z_cut)
    rep["collar_smooth_max_mm"] = smooth_collar(ob.data, ring, z_cut, ring_idx)
    # triangulate for an exact count
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.to_mesh(ob.data)
    bm.free()
    me = ob.data
    for p in me.polygons:
        p.use_smooth = True
    rep["head_tris"] = len(me.polygons)
    rep["deviation"] = deviation(dense_bvh, ob, z_cut + 0.005, HEAD_H)
    rep["chin_sculpt"] = sculpt_chin(me, ring, chin, W(MESHY["mouth_z"]), z_cut)
    chin -= CHIN_SCULPT["down"]
    rep["chin_z_sculpted"] = round(chin, 4)
    rv = [Vector(p) for p in ring["loop"]]
    rep["ring_weld_max_mm"] = round(max((me.vertices[i].co - rv[k]).length for k, i in enumerate(ring_idx)) * 1000, 4)
    eye_w = W(MESHY["eye_z"])
    while me.uv_layers:
        me.uv_layers.remove(me.uv_layers[0])
    smart_uv(ob)
    head_masks(ob, eye_w, chin)
    # reorder UV layers: UVMap first, masks second
    names = [l.name for l in me.uv_layers]
    rep["uv_layers"] = names
    vg_h = ob.vertex_groups.new(name="Head")
    vg_n = ob.vertex_groups.new(name="Neck")
    # the Neck's share: the loft 0.7 at the ring to 0.4 at the cut, then fading out NECK_BLEND up the stalk (only
    # near the neck's axis, as NECK_FILL), so a turn or a nod bends the whole neck instead of kinking at the cut
    cx, cy = ring["centre"]
    hx, hy = rep["neck_fill"]["stalk_half_m"]
    g0, g1 = NECK_FILL["gate"]
    for v in me.vertices:
        if v.index in head_w:
            w = 0.3 + (head_w[v.index] - 0.3) * (0.3 / 0.7)
        else:
            w = 0.6 + 0.4 * G.smoothstep(z_cut, z_cut + NECK_BLEND, v.co.z)
            g = 1.0 - G.smoothstep(g0, g1, math.hypot((v.co.x - cx) / hx, (v.co.y - cy) / hy))
            w = 1.0 - (1.0 - w) * g
        vg_h.add([v.index], w, "REPLACE")
        if w < 1.0:
            vg_n.add([v.index], 1.0 - w, "REPLACE")
    rep["ring_normals"] = len(set_ring_normals(ob, ring, ring_idx))
    bvh = BVHTree.FromObject(ob, bpy.context.evaluated_depsgraph_get())
    zs = [v.co.z for v in me.vertices]
    rep["head_z_range"] = [round(min(zs), 4), round(max(zs), 4)]

    # 2. sockets
    sockets = {}
    rg = 0.1 * s
    for side, sx in (("L", 1), ("R", -1)):
        guess = Vector((sx * MESHY["eye_x"] * s + T.translation.x, -0.4, eye_w))
        c, r, cen, info = socket_fit(bvh, guess, rg)
        fwd = (c - cen).normalized()
        fwd = (fwd + Vector((0, -1, 0))).normalized()
        sockets[f"Eye_{side}"] = G.frame(c, fwd)
        rep[f"socket_{side}"] = {"centre": [round(x, 4) for x in c], "r": round(r, 4), "forward": [round(x, 3) for x in fwd], **info}
    mz = W(MESHY["mouth_z"])
    mp, mn = surf(bvh, 0.0, mz)
    sockets["Mouth"] = G.frame(mp, mn)
    cz = W(MESHY["crest_base"])
    cp, cn = surf(bvh, 0.0, cz)
    sockets["Crest"] = G.frame(cp, Vector((0, -1, 0)))
    for name, m in sockets.items():
        e = bpy.data.objects.new(name, None)
        e.empty_display_type = "ARROWS"
        e.empty_display_size = 0.03
        e.matrix_world = m
        coll.objects.link(e)
        e.parent = ob
    r_eye = 0.97 * (rep["socket_L"]["r"] + rep["socket_R"]["r"]) / 2
    rep["eyeball_r"] = round(r_eye, 4)

    # materials
    hue = hue_material(k_light)
    hue_lin = {k: srgb_to_lin(v["base_srgb"]) for k, v in hues.items()}
    mats = {"hue": hue, **{k: plain(f"alien_{n}", *FACE[f"alien_{n}"])
                           for k, n in (("lip", "lip"), ("inner", "mouth_inner"), ("teeth", "teeth"))}}
    ob.data.materials.append(hue)
    ob["alien_hue"] = hue_lin["teal"]

    # 3. eyes: one set per design and side, parented to the socket empties
    parts = {"eyes": {}, "mouths": {}, "crests": {}}
    for dname, d in EYES.items():
        img = eye_image(f"alien_eye_{dname}", d, out / "export")
        em = plain(f"alien_eye_{dname}", (1, 1, 1), EYE_ROUGH, 0.35, img)
        lids = {}
        for side in ("L", "R"):
            sm = sockets[f"Eye_{side}"]
            ball = G.eyeball(f"eye_{dname}_ball_{side}", r_eye, em, coll, seg=24, rings=18)
            ball.matrix_world = sm
            for lid in ("upper", "lower"):
                L_ = d[lid]
                # S7: the lids in the lips' material (S5, the eye sheets' coral domes) with the sheets' rolled rim
                o = G.lid_shell(f"eye_{dname}_lid_{lid}_{side}", r_eye, L_["rho"][0], L_["rho"][1], lid == "upper",
                                mats["lip"], coll, seg_p=18, rim_seg=8, bead=LID_BEAD[lid])
                o.matrix_world = sm @ Matrix.Rotation(math.radians(-L_["rest"]), 4, "X")
                o["states"] = {st: -L_[st] for st in STATES}
                lids[lid] = {st: -L_[st] for st in STATES}
        parts["eyes"][dname] = {"glb": f"export/eye_{dname}.glb", "eyeball_r": round(r_eye, 4),
                                "lid_rot_x_deg": lids, "lid_rho": {k: d[k]["rho"] for k in ("upper", "lower")},
                                "pupil_deg": round(math.degrees(d["pupil"]), 1), "iris_deg": round(math.degrees(d["iris"]), 1)}

    # 4. mouths
    for dname, d in MOUTHS.items():
        names = []
        for v in VISEMES:
            o, cur = build_mouth(bvh, d, f"{dname}_{v}", mz, mats, coll, sockets["Mouth"])
            names.append(o.name)
        entry = {"pieces": names, "glb": [f"export/{n}.glb" for n in names]}
        if dname == "overbite":
            t = build_teeth(bvh, d, mz, mats["teeth"], coll, sockets["Mouth"])
            entry["teeth"] = t.name
        parts["mouths"][dname] = entry

    # 5. crests
    b = G.Built()
    mi = b.slot(hue)
    crest = sockets["Crest"]
    for sx in (-1, 1):
        root = cp + Vector((sx * 0.024, 0.012, -0.004))
        pts, rr = [], []
        for i in range(17):
            f = i / 16
            pts.append(root + Vector((sx * (0.035 * f + 0.02 * f * f), -0.012 * f, 0.13 * f - 0.015 * f * f)))
            rr.append(0.0052 * (1 - 0.45 * f) if f > 0.05 else 0.0075)
        G.tube(b, pts, rr, rr, [Vector((0, -1, 0))] * len(pts), mi, seg=12)
        G.sphere(b, pts[-1] + (pts[-1] - pts[-2]).normalized() * 0.008, 0.0125, mi, mask=(0.0, 1.0))
    ant = G.to_object(b, "crest_antennae", coll, crest)
    ant["alien_hue"] = hue_lin["teal"]
    b = G.Built()
    mi = b.slot(hue)
    ez = W(MESHY["ear_z"])
    for sx in (-1, 1):
        hit = bvh.ray_cast(Vector((sx * 0.5, rep["socket_L"]["centre"][1] + 0.06, ez + 0.01)), Vector((-sx, 0, 0)))
        root = hit[0] - Vector((sx * 0.004, 0, 0))
        outd = Vector((sx, 0.2, 0.1))
        G.fin(b, root, outd, Vector((0, 0.25, 1)), mi, [(85, 0.13), (50, 0.155), (15, 0.12)], cup=0.004)
    fins = G.to_object(b, "crest_fins", coll, crest)
    fins["alien_hue"] = hue_lin["teal"]
    parts["crests"] = {"antennae": {"glb": "export/crest_antennae.glb"}, "fins": {"glb": "export/crest_fins.glb"}}

    for o in coll.objects:
        if o.type == "MESH" and o is not ob:
            mw = o.matrix_world.copy()
            o.parent = ob
            o.matrix_world = mw

    # 6. checks
    rep["checks"] = checks(ob, bvh, sockets, r_eye, parts)

    # 7. export, json, blend
    exports(ob, sockets, parts, out, hue_lin)
    gl = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0), (0, 0, 0, 1)))
    sj = {}
    for name, m in sockets.items():
        mg = gl @ m @ gl.inverted()
        q = mg.to_quaternion()
        sj[name] = {"blender_matrix": [list(r) for r in m], "gltf_translation": list(mg.translation),
                    "gltf_rotation_xyzw": [q.x, q.y, q.z, q.w],
                    "head_bone_offset_gltf": list(mg.translation - (gl @ Vector(bones["Head"])))}
    doc = {"note": "art #196 S2a: head and face parts. Blender frame: Z up, front -Y; glTF: (x, z, -y). Parts are "
                   "in their socket's local space (local -Y = forward, +Z = up). Lid states: set the lid node's local "
                   "X rotation to the angle (degrees); the GLB holds the rest state.",
           "head": {"glb": "export/alien_head.glb", "tris": rep["head_tris"], "ring_vertices_ordered": ring_idx,
                    "weights": "Head/Neck vertex groups in alien_head_parts.blend: ring Neck 0.7 / Head 0.3, Head 1.0 "
                               "at the loft's top"},
           "bones_blender": bones, "sockets": sj, "hues_srgb": {k: v["base_srgb"] for k, v in hues.items()},
           "hue_light_mix": k_light, "blink_ms": {"close": 60, "hold": 40, "open": 100, "every_s": [2, 6]}, **parts}
    (out / "parts.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    (out / "build_report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    bpy.data.meshes.remove(dense)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "alien_head_parts.blend"))
    print("REPORT", json.dumps({k: v for k, v in rep.items() if k not in ("hues",)}, indent=None)[:3000])


def checks(head, bvh, sockets, r, parts):
    res = {}
    dg = bpy.context.evaluated_depsgraph_get()
    for dname in EYES:
        for side in ("L", "R"):
            sm = sockets[f"Eye_{side}"]
            ball = bpy.data.objects[f"eye_{dname}_ball_{side}"]
            lids = [bpy.data.objects[f"eye_{dname}_lid_{l}_{side}"] for l in ("upper", "lower")]
            out_pts = []
            for v in ball.data.vertices:
                p = ball.matrix_world @ v.co
                ins, sd = inside(bvh, p)
                if not ins:
                    out_pts.append((p, (p - sm.translation).normalized()))
            st_res = {}
            for st in STATES:
                for lo, ln in zip(lids, ("upper", "lower")):
                    lo.matrix_world = sm @ Matrix.Rotation(math.radians(EYES[dname][ln][st] * -1), 4, "X")
                dg.update()
                lb = [BVHTree.FromPolygons([lo.matrix_world @ v.co for v in lo.data.vertices],
                                           [tuple(p.vertices) for p in lo.data.polygons]) for lo in lids]
                bare = 0
                for p, n in out_pts:
                    if not any(t.ray_cast(p + n * 1e-4, n, 0.3 * r)[0] is not None for t in lb):
                        bare += 1
                # the rim: the lid vertices nearest the moving edge (accent 1): inside the head while the eyeball
                # beside them is outside counts as a cut
                cut, rim_n, min_clear = 0, 0, 9.0
                for lo in lids:
                    uv = lo.data.uv_layers[G.MASKS].data
                    rim = set()
                    for lp in lo.data.loops:
                        if uv[lp.index].uv[1] > 0.99:
                            rim.add(lp.vertex_index)
                    for vi in rim:
                        p = lo.matrix_world @ lo.data.vertices[vi].co
                        ins, sd = inside(bvh, p)
                        rim_n += 1
                        dirn = (p - sm.translation).normalized()
                        ball_pt = sm.translation + dirn * r
                        b_in, _ = inside(bvh, ball_pt)
                        if ins and not b_in:
                            cut += 1
                        if not ins:
                            min_clear = min(min_clear, sd)
                st_res[st] = {"eyeball_outside_verts": len(out_pts), "uncovered": bare, "rim_verts": rim_n,
                              "rim_cuts_head": cut, "rim_min_clear_mm": round(min_clear * 1000, 2)}
            for lo, ln in zip(lids, ("upper", "lower")):
                lo.matrix_world = sm @ Matrix.Rotation(math.radians(-EYES[dname][ln]["rest"]), 4, "X")
            res[f"eye_{dname}_{side}"] = st_res
    # mouths: each piece's vertices against the head: how deep the deepest sits, how far the farthest floats
    for dname, e in parts["mouths"].items():
        for n in e["pieces"]:
            o = bpy.data.objects[n]
            sds = []
            for v in o.data.vertices:
                p = o.matrix_world @ v.co
                sds.append(inside(bvh, p)[1])
            sds = np.array(sds)
            # contact: the lip tubes cross the skin (some vertices inside) and the cup floats 1.2 mm off it
            res[n] = {"min_mm": round(float(sds.min()) * 1000, 2), "max_mm": round(float(sds.max()) * 1000, 2),
                      "inside_share": round(float((sds < 0).mean()), 3), "tris": len(o.data.polygons)}
    return res


def export_selected(objs, path):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=True, export_yup=True,
                              export_apply=True, export_texcoords=True, export_normals=True, export_materials="EXPORT",
                              export_animations=False, export_skins=False, export_extras=False)


def exports(head, sockets, parts, out, hue_lin):
    """One GLB per part. The head in body space with its socket empties; every other part in its socket's space.
    For the export the hue material is swapped for a plain one (base teal) named alien_hue, which S3 replaces with
    the shader."""
    hue = bpy.data.materials["alien_hue"]
    plain_hue = plain("alien_hue_export", (0.0, 0.0, 0.0))
    plain_hue.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*hue_lin["teal"], 1)
    plain_hue.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.62
    swapped = []
    for o in bpy.data.objects:
        if o.type == "MESH":
            for i, m in enumerate(o.data.materials):
                if m is hue:
                    o.data.materials[i] = plain_hue
                    swapped.append((o, i))
    hue.name = "alien_hue_blender"
    plain_hue.name = "alien_hue"
    ex = out / "export"
    keep = {o: (o.parent, o.matrix_world.copy()) for o in bpy.data.objects}

    def local(objs, socket):
        inv = sockets[socket].inverted()
        for o in objs:
            mw = o.matrix_world.copy()
            o.parent = None
            o.matrix_world = inv @ mw

    def restore():
        for o, (p, mw) in keep.items():
            o.parent = p
            o.matrix_world = mw

    empties = [bpy.data.objects[n] for n in sockets]
    export_selected([head] + empties, ex / "alien_head.glb")
    for dname in EYES:
        objs = [bpy.data.objects[f"eye_{dname}_{p}_L"] for p in ("ball", "lid_upper", "lid_lower")]
        local(objs, "Eye_L")
        for o in objs:
            o.name = o.name[:-2]
        export_selected(objs, ex / f"eye_{dname}.glb")
        for o in objs:
            o.name = o.name + "_L"
        restore()
    for dname, e in parts["mouths"].items():
        for n in e["pieces"] + ([e["teeth"]] if "teeth" in e else []):
            o = bpy.data.objects[n]
            local([o], "Mouth")
            export_selected([o], ex / f"{n}.glb")
            restore()
    for n in ("crest_antennae", "crest_fins"):
        o = bpy.data.objects[n]
        local([o], "Crest")
        export_selected([o], ex / f"{n}.glb")
        restore()
    for o, i in swapped:
        o.data.materials[i] = hue
    plain_hue.name = "alien_hue_export"
    hue.name = "alien_hue"


if __name__ == "__main__":
    main()
