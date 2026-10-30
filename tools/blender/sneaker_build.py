"""The code-built canvas sneakers inside Blender (art #196, S1): clothes_dress.py --sneakers puts them in place of
the fit's Meshy shoes. The maths (the foot's frame, the outline, the opening, the rings, the tongue, eyelets, laces
and bow, the bend's weights, the toes' cap) is sneaker_geom.py's; here:
- `feet`: each foot's points (the body's vertices mostly on Foot and Toes) and the two bones' heads at rest;
- `shoes`: one mesh "shoes" for the pair, each shoe built in its own foot's frame from both feet's measures (so the
  pair is symmetric), weighted Foot behind the ball and Toes past it (a short blend), skinned on the armature;
- `material`: one surface, "sneaker_canvas": a 2048x1024 albedo painted per UV zone (the canvas with a fine weave,
  the rubber sole with its foxing stripe, the cream stitching along the sole and the collar, the white laces, the
  silver eyelets), a normal map (the weave, the stitches, the band, the sole's tread), roughness 0.85;
- `clearance`: the foot's vertices against the built shoe (signed distance along the shoe's normal);
- `cap_toes`: every action's Toes rotation keys capped (sneaker_geom.cap_quat) from the anim set's [toes_cap].
"""
from __future__ import annotations

import math
import sys
import tomllib
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sneaker_geom as G  # noqa: E402

IMG_W, IMG_H = 2048, 1024
CANVAS = (0.89, 0.86, 0.77)  # sRGB, off-white canvas (E1j: a warmer cream, so the whiter rubber reads apart)
RUBBER = (0.985, 0.983, 0.975)
STRIPE = (0.13, 0.17, 0.33)  # the foxing's thin navy stripe
EDGE = (0.70, 0.71, 0.73)  # the outsole's grey bottom edge
EDGE_TOP = (0.80, 0.80, 0.80)  # the rubber's top edge, where the canvas starts
STITCH = (0.78, 0.75, 0.67)
LACE = (0.955, 0.945, 0.92)
EYELET = (0.20, 0.21, 0.24)  # dark metal: the eyelets read as dots on the canvas, as on the concept
TREAD = (0.80, 0.78, 0.73)
STRIPE_MM = 2.4  # the stripe's height


SECT_Z = 0.2  # E1: the collar's section points: any Foot, Toes or LowerLeg weight under this height (m)


def feet(body, arm, min_w: float = 0.5) -> dict:
    """Per side ("Left", "Right") the foot's world points at rest (Foot + Toes weight min_w and over: the outline),
    the section points (E1: any Foot, Toes or LowerLeg weight under SECT_Z: the collar and the rim) and the Foot and
    Toes heads."""
    gn = {g.index: g.name for g in body.vertex_groups}
    out = {}
    for side in ("Left", "Right"):
        names = (side + "Foot", side + "Toes")
        legs = names + (side + "LowerLeg",)
        pts = [tuple(body.matrix_world @ v.co) for v in body.data.vertices
               if sum(g.weight for g in v.groups if gn.get(g.group, "") in names) >= min_w]
        sect = [p for p in (tuple(body.matrix_world @ v.co) for v in body.data.vertices
                            if any(g.weight > 0.0 and gn.get(g.group, "") in legs for g in v.groups)) if p[2] < SECT_Z]
        if len(pts) < 50:
            raise ValueError(f"{side}: only {len(pts)} foot vertices")
        bones = {n: tuple(arm.matrix_world @ arm.data.bones[n].head_local) for n in names}
        out[side] = {"pts": pts, "sect": sect, "foot": bones[names[0]], "toes": bones[names[1]]}
    return out


def shoes(body, arm, params: G.Params | None = None):
    """The pair as one skinned mesh object "shoes" (parented to arm, an armature modifier) and a report."""
    params = params or G.Params()
    ft = feet(body, arm)
    frames = {s: G.frame(d["foot"], d["toes"], d["pts"]) for s, d in ft.items()}
    measures = {s: G.measure(frames[s], d["pts"], d["foot"], d["toes"], d["sect"]) for s, d in ft.items()}
    foot = G.merge(measures["Left"], measures["Right"])
    sh = G.build(foot, params)
    verts, faces, uvs, groups = [], [], [], []
    for side in ("Left", "Right"):
        fr = frames[side]
        base = len(verts)
        verts += [fr.world(q) for q in sh.verts]
        for f, uv in zip(sh.faces, sh.uvs):
            if fr.mirrored():
                f, uv = f[::-1], uv[::-1]
            faces.append(tuple(base + i for i in f))
            uvs.append(uv)
        groups += [(side, G.toes_weight(q[0], foot.ball_u, params.blend)) for q in sh.verts]
    me = bpy.data.meshes.new("shoes")
    me.from_pydata(verts, [], faces)
    me.update()
    uvl = me.uv_layers.new(name="UVMap")
    k = 0
    for poly, uv in zip(me.polygons, uvs):
        for li, c in zip(poly.loop_indices, uv):
            uvl.data[li].uv = c
        k += 1
    for poly in me.polygons:
        poly.use_smooth = True
    ob = bpy.data.objects.new("shoes", me)
    bpy.context.scene.collection.objects.link(ob)
    vg = {n: ob.vertex_groups.new(name=n) for n in ("LeftFoot", "LeftToes", "RightFoot", "RightToes")}
    for i, (side, wt) in enumerate(groups):
        if wt < 1.0:
            vg[side + "Foot"].add([i], 1.0 - wt, "REPLACE")
        if wt > 0.0:
            vg[side + "Toes"].add([i], wt, "REPLACE")
    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    ob.parent = arm
    ob.matrix_parent_inverse = arm.matrix_world.inverted()
    rep = {"tris_pair": 2 * sh.tris, "tris_shoe": sh.tris, "verts_pair": len(verts), **sh.info,
           "foot": {"length_m": round(foot.length, 4), "width_m": round(foot.width, 4), "ball_u": round(foot.ball_u, 4),
                    "ankle_u": round(foot.ankle_u, 4), "ankle_z": round(foot.ankle_z, 4),
                    "points": {s: len(d["pts"]) for s, d in ft.items()},
                    "section_points": {s: len(d["sect"]) for s, d in ft.items()}},
           "params": {k_: getattr(params, k_) for k_ in params.__dataclass_fields__}}
    rep["material"] = material(ob, sh)
    rep["clearance"] = clearance(ob, ft)
    return ob, rep


def _lin(c):
    c = np.asarray(c, dtype=np.float32)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def paint(sh: G.Shoe) -> tuple[np.ndarray, np.ndarray]:
    """The albedo (sRGB, h x w x 3) and the height (h x w) of the atlas from the shell's UV rows."""
    H, W = IMG_H, IMG_W
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    v = (yy + 0.5) / H  # Blender's image rows run up, as UV v
    u = (xx + 0.5) / W
    rgb = np.empty((H, W, 3), np.float32)
    hgt = np.zeros((H, W), np.float32)
    rows = sh.uv_rows
    mm = rows["scale"] / 1000.0  # UV per mm along u
    mmv = rows["scale_v"] / 1000.0  # and along v
    sx0, sy0, sw, shh = G.ATLAS["shell"]
    shell = v < sy0 + shh
    join = rows["join"]
    sole = shell & (v < join)
    canvas = shell & ~sole
    rgb[:] = CANVAS
    rgb[sole] = RUBBER
    # the foxing band: the dark stripe between the band rows, a raised rubber ridge round it
    sv = rows["sole_v"]
    b0, b1 = sv[rows["band_rows"][0]], sv[rows["band_rows"][1]]
    mid, half = (b0 + b1) / 2, (b1 - b0) / 2
    stripe = sole & (np.abs(v - mid) < 0.5 * STRIPE_MM * mmv)
    rgb[stripe] = STRIPE
    rgb[sole & (v < sv[1] - 0.5 * mmv)] = EDGE  # the outsole's edge under the wall
    rgb[sole & (v > join - 1.0 * mmv)] = EDGE_TOP  # the rubber's top edge (round the toe cap): a fine grey line
    hgt += np.where(sole, 0.6 * np.clip(1 - np.abs(v - mid) / max(half, 1e-6), 0, 1), 0)
    # the rubber's faint vertical ribs on the sole's wall below the band
    hgt += np.where(sole & (v < b0), 0.12 * np.sin(2 * np.pi * u / (1.6 * mm)), 0)
    # the canvas: a plain weave of 1.6 mm, the threads' tone varying a little
    wu, wv = np.sin(2 * np.pi * u / (1.6 * mm)), np.sin(2 * np.pi * v / (1.6 * mmv))
    weave = 0.5 * (wu * np.sign(wv) * 0.5 + wv * np.sign(wu) * 0.5)
    hgt += np.where(canvas, 0.7 * weave, 0)
    rng = np.random.default_rng(7)
    tone = np.repeat(np.repeat(rng.normal(0, 1, (H // 2 + 1, W // 2 + 1)), 2, 0), 2, 1)[:H, :W].astype(np.float32)
    rgb[canvas] *= (1 + 0.012 * tone[canvas] + 0.02 * weave[canvas])[:, None]

    def stitch_row(vc, dash=2.6, gap=1.4, width=0.45):
        """A dashed stitch line centred on vc (a scalar or per-texel UV v)."""
        on = (np.mod(u / mm, dash + gap) < dash) & (np.abs(v - vc) < width * mmv)
        return on & canvas
    # two rows above the sole, one under the collar's rim (per column), one round the toe cap's top
    st = stitch_row(join + 3.0 * mmv) | stitch_row(join + 5.5 * mmv)
    rim_v = np.interp(u[0], rows["rim_u"], rows["rim"], period=1.0)[None, :]
    st |= stitch_row(rim_v - 4.5 * mmv)
    # E1j: the rubber toe cap over the upper's front (a U from above), its edge a fine grey line and a lip in the
    # normal map; the eyelet stays' stitched edge, 13 mm under the slot's rim
    cap_v = np.interp(u[0], rows["rim_u"], rows["cap"], period=1.0)[None, :]
    cap = canvas & (v < cap_v) & (cap_v > join + 1.5 * mmv)
    rgb[cap] = RUBBER
    capedge = canvas & (np.abs(v - cap_v) < 0.6 * mmv) & (cap_v > join + 1.5 * mmv)
    rgb[capedge] = EDGE_TOP
    hgt += np.where(cap, 1.0, 0)
    stay_u = np.zeros(len(rows["rim_u"]), np.float32)
    stay_u[rows["stay_cols"]] = 1.0
    on_stay = np.interp(u[0], rows["rim_u"], stay_u, period=1.0)[None, :] > 0.5
    st |= stitch_row(rim_v - 13.0 * mmv) & on_stay
    rgb[st] = STITCH
    hgt += np.where(st, 1.2, 0)
    # the sole's bottom: tread diamonds, a little darker
    bx, by, bw, bh = G.ATLAS["bottom"]
    bot = (u >= bx) & (u < bx + bw) & (v >= by) & (v < by + bh)
    rgb[bot] = TREAD
    a, b = np.sin(2 * np.pi * (u + v) / 0.012), np.sin(2 * np.pi * (u - v) / 0.012)
    hgt += np.where(bot, 0.6 * np.maximum(np.abs(a), np.abs(b)), 0)
    # the tongue: canvas; the laces: white with a fine rib along; the eyelets: silver
    for key, col in (("tongue", CANVAS), ("lace", LACE), ("eyelet", EYELET)):
        x, y, w, h = G.ATLAS[key]
        m = (u >= x) & (u < x + w) & (v >= y) & (v < y + h)
        rgb[m] = col
        if key == "tongue":
            hgt += np.where(m, 0.35 * np.sin(2 * np.pi * u / 0.0025) * np.sign(np.sin(2 * np.pi * v / 0.005)), 0)
        if key == "lace":
            hgt += np.where(m, 0.3 * np.sin(2 * np.pi * u / 0.006), 0)
    return np.clip(rgb, 0, 1), hgt


def material(ob, sh: G.Shoe) -> dict:
    rgb, hgt = paint(sh)
    mat = bpy.data.materials.new("sneaker_canvas")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = 0.85
    for key in ("Specular IOR Level", "Specular"):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = 0.3
            break
    alb = bpy.data.images.new("sneaker_diffuse", IMG_W, IMG_H, alpha=False)
    nrm = bpy.data.images.new("sneaker_normal", IMG_W, IMG_H, alpha=False)
    nrm.colorspace_settings.name = "Non-Color"
    ta, tn = nt.nodes.new("ShaderNodeTexImage"), nt.nodes.new("ShaderNodeTexImage")
    ta.image, tn.image = alb, nrm
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(ta.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    ob.data.materials.append(mat)
    ones = np.ones((IMG_H, IMG_W, 1), np.float32)
    alb.pixels[:] = np.concatenate([rgb.astype(np.float32), ones], axis=2).ravel()
    alb.update()
    alb.pack()
    gy, gx = np.gradient(hgt)
    n = np.stack([-gx, -gy, np.ones_like(hgt)], axis=2)
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    nrm.pixels[:] = np.concatenate([0.5 + 0.5 * n, ones], axis=2).ravel()
    nrm.update()
    nrm.pack()
    return {"albedo_px": [IMG_W, IMG_H], "canvas_srgb": [round(c * 255) for c in CANVAS],
            "rubber_srgb": [round(c * 255) for c in RUBBER], "stripe_srgb": [round(c * 255) for c in STRIPE]}


def clearance(ob, ft: dict) -> dict:
    """The foot's vertices against the shoe at rest: per side the signed distance to the nearest shoe point along
    its normal (negative: the foot is outside the shoe); only points under the opening's height count."""
    me = ob.data
    vs = [ob.matrix_world @ v.co for v in me.vertices]
    tree = BVHTree.FromPolygons(vs, [list(p.vertices) for p in me.polygons])
    rep = {}
    for side, d in ft.items():
        ds = []
        for p in d["pts"]:
            q = Vector(p)
            loc, nor, _i, dist = tree.find_nearest(q, 0.2)
            if loc is None:
                continue
            ds.append(-(q - loc).dot(nor))  # inside the shell (behind its outward normal): positive
        ds.sort()
        if not ds:
            continue
        rep[side] = {"n": len(ds), "outside_1mm": sum(x < -0.001 for x in ds), "min_mm": round(ds[0] * 1000, 1),
                     "p5_mm": round(ds[len(ds) // 20] * 1000, 1), "median_mm": round(ds[len(ds) // 2] * 1000, 1)}
    return rep


def toes_cap(anim_set: str) -> dict | None:
    """The [toes_cap] table of an anim set's settings (tools/blender/anim_sets/<set>.toml), or None."""
    p = Path(anim_set)
    if not p.is_file():
        p = Path(__file__).resolve().parent / "anim_sets" / f"{anim_set}.toml"
    with open(p, "rb") as fh:
        return tomllib.load(fh).get("toes_cap")


def _fcurves(act) -> list:
    out = []
    for layer in getattr(act, "layers", ()):
        for strip in layer.strips:
            for bag in getattr(strip, "channelbags", ()):
                out += list(bag.fcurves)
    return out


def cap_toes(cap: dict) -> dict:
    """Every action's Toes bend capped: each key of the bones' rotation_quaternion curves (the four curves' keys at
    one frame) turned about its own axis by sneaker_geom.cap_quat; the handles move with their key. Returns per
    action the largest bend before and after (degrees)."""
    bones, mx, knee = cap["bones"], float(cap["max_deg"]), float(cap["knee_deg"])
    rep = {}
    for act in bpy.data.actions:
        fcs = _fcurves(act)
        before = after = 0.0
        for b in bones:
            path = f'pose.bones["{b}"].rotation_quaternion'
            cs = [next((c for c in fcs if c.data_path == path and c.array_index == i), None) for i in range(4)]
            if not all(cs) or len({len(c.keyframe_points) for c in cs}) != 1:
                continue
            for k in range(len(cs[0].keyframe_points)):
                kp = [c.keyframe_points[k] for c in cs]
                q = tuple(p.co[1] for p in kp)
                new = G.cap_quat(q, mx, knee)
                w = min(1.0, abs(q[0]) / (math.sqrt(sum(x * x for x in q)) or 1.0))
                before = max(before, math.degrees(2 * math.acos(w)))
                after = max(after, math.degrees(2 * math.acos(min(1.0, new[0]))))
                if q[0] < 0:
                    new = tuple(-x for x in new)
                for p, val in zip(kp, new):
                    d = val - p.co[1]
                    p.co[1] += d
                    p.handle_left[1] += d
                    p.handle_right[1] += d
            for c in cs:
                c.update()
        if before:
            rep[act.name] = [round(before, 1), round(after, 1)]
    return rep
