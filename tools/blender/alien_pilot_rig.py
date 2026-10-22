"""The alien 3D pilot, step 2b-1 (art #196): the face rig of one built pilot head (alien_pilot_head.py's .blend and
build.json, read, never written). Writes into --out:

- a face skeleton under `Head` (the contract's Head, Jaw, LeftEye and RightEye names): Jaw, LipUpper, LipLower
  (under the Jaw), Left/RightLipCorner, Left/RightBrowInner and BrowOuter, Left/RightLidUpper and LidLower (at the eye
  centres), and for the axolotl a three-bone chain per gill stalk (`LeftGill1_1`..`_3`, from the `pivots` extras' roots
  toward each stalk's tip) for 2b-2's SpringBoneSimulator3D;
- skin weights by position (no heat weights): the jaw below the lip line inside an ellipsoid round the chin, the lip
  bones round their centres on their own side of the line, the corners round the corners, the brows above the eyes,
  the Head the rest; the lids, eyes, mouth cup and gill stalks rigid to their bones (the gills along the chain);
- blend shapes on every mesh they move, the same name on each: `blink_L` and `blink_R` (the upper lid rebuilt
  stretched down to the lower lid's edge: a spherical shell, so nothing pokes through) and the expressions `smile`,
  `sad`, `angry`, `surprised` (mouth O) and `talk` (open), each a bone pose baked into the skin and mouth plus its own
  lid shape (the lids rebuilt at other edge angles and tilted round the gaze);
- `<head>_rig.glb` (skin, morphs, no animations: Godot imports morph targets as blend shapes by name), `rig.json`
  (bones, weights per bone, shape keys), `<head>_rig.blend` and the review sheet `<head>_rig_1280.png`: the 2D
  expression sheet's six cells above the 3D's six (rest, smile, sad / angry, surprised, talk in the 2D's order, the
  2D's 3/4 view), then a front blink strip (open, half, closed), the side and front at rest and a bone check (the
  jaw open and, for the axolotl, the gills bent).

Runs only through tools/runner/blender.py (blender -b): run_script("alien_pilot_rig.py", ["--head", h, "--blend",
<head>.blend, "--build", build.json, "--expr", <2D expression sheet>, "--view2d", <2D views>, "--out", <dir>]).
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
from mathutils.kdtree import KDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_pilot_geom as G  # noqa: E402
import alien_pilot_head as H  # noqa: E402

UP = Vector((0.0, 0.0, 1.0))
EXPRESSIONS = ("rest", "smile", "sad", "angry", "surprised", "talk")  # the 2D sheet's order, row by row
# per expression: lid edge changes in degrees (upper, lower), the upper lid's tilt round the gaze (positive: the inner
# corner down, angry; negative: sad), and the bone moves in mouth units m (lips) or eye radii R (brows):
# (bone, move along (left/out, up, front), jaw degrees)
POSES = {
    "smile": {"lid": (0.0, 16.0), "tilt": 0.0,
              "bones": {"LipCorner": (0.15, 0.50, -0.20), "LipUpper": (0.0, 0.06, 0.0), "LipLower": (0.0, 0.06, 0.0),
                        "BrowInner": (0.0, 0.08, 0.0), "BrowOuter": (0.0, 0.08, 0.0)}},
    "sad": {"lid": (-14.0, 0.0), "tilt": -18.0,
            "bones": {"LipCorner": (0.0, -0.40, -0.05), "LipLower": (0.0, 0.05, 0.14),
                      "BrowInner": (-0.05, 0.30, 0.0), "BrowOuter": (0.0, -0.12, 0.0)}},
    "angry": {"lid": (-20.0, 8.0), "tilt": 24.0,
              "bones": {"LipCorner": (-0.04, -0.20, 0.0), "LipUpper": (0.0, -0.04, 0.0), "LipLower": (0.0, 0.06, 0.06),
                        "BrowInner": (-0.12, -0.35, 0.06), "BrowOuter": (0.0, 0.08, 0.0)}},
    "surprised": {"lid": (30.0, -8.0), "tilt": 0.0, "jaw": 14.0,
                  "bones": {"LipCorner": ("in", -0.05, 0.25), "LipUpper": (0.0, 0.16, 0.12), "LipLower": (0.0, -0.05, 0.12),
                            "BrowInner": (0.0, 0.30, 0.0), "BrowOuter": (0.0, 0.30, 0.0)}},
    "talk": {"lid": (0.0, 0.0), "tilt": 0.0, "jaw": 10.0,
             "bones": {"LipCorner": (-0.03, 0.0, 0.0), "LipUpper": (0.0, 0.06, 0.0)}},
}
BROWS = ("BrowInner", "BrowOuter")
# per head (2b-1b): the lips (the chameleon's swept lip mesh: vertical radius in mouth units, fullness = depth radius
# over vertical radius; None keeps the skin's lips), the expression amounts picked from the variant grid (a factor on
# every bone move, jaw angle, lid angle and corrective of the pose), the brows' weight sigma and move unit in eye radii,
# the cheeks' lift for the smile and the knit between the brows for the angry face (corrective deltas, in mouth units
# and eye radii), the mouth lining cleared behind the slit ("lining": the half width's fraction, the half height in
# lip radii (chameleon) or mouth units, the depth behind the line in mouth units) and the blink's flattening of the closed eye along the gaze (a fraction of
# its front bulge, so the closed lid sits close like skin)
RIGCFG = {
    # picked from the 2b-1b grids (v2/<head>_grid_*.png); "lid": the lids' own factor where it differs (his heavy
    # lids already droop enough at 1, more covers the iris; her small lids need more to show at all)
    "chameleon": {"lips": {"radius": 0.42, "full": 1.2},
                  "amount": {"smile": 1.75, "sad": 1.75, "angry": 1.75, "surprised": 1.75, "talk": 1.75},
                  "lid": {"sad": 1.0, "angry": 1.0}, "brow": (0.75, 1.0), "cheek": 0.35, "knit": 0.25,
                  "blink_flat": 0.55, "lining": (0.97, 1.5, 0.1),
                  "o": 0.6, "pucker": 0.15, "tongue": 0.35, "blend": 0.7, "tube_smooth": 30},
    # 2b-2: her own swept lip band (thin, flush with the skin: "prot" in mouth units), her tongue added by the rig
    "axolotl": {"lips": {"radius": 0.24, "full": 1.0, "prot": 0.0, "draw": 2.4},
                "amount": {"smile": 2.2, "sad": 2.5, "angry": 2.5, "surprised": 1.75, "talk": 1.75},
                "lining": (0.9, 1.5, 0.1), "o": 0.6, "pucker": 0.1, "tongue": 0.3, "blend": 0.5, "add_tongue": True,
                "tube_smooth": 0,
                "lid": {"sad": 2.2, "angry": 2.0, "surprised": 1.0}, "brow": (1.5, 2.2), "cheek": 0.35, "knit": 0.25,
                "blink_flat": 0.6},
}
GRID_LIPS = ({"radius": 0.30, "full": 1.0}, {"radius": 0.36, "full": 1.1}, {"radius": 0.42, "full": 1.2},
             {"radius": 0.36, "full": 1.4})
GRID_AMOUNTS = (1.0, 1.75, 2.5)
# 2b-2's mouth grid, one row per variant: the O's squeeze ("o": the fraction of each point's distance from the midline
# taken off round the mouth), the tongue's lift in talk (mouth units), the lip flank's blend into the skin and, for the
# axolotl, her lip band's radius
GRID_MOUTH = {"chameleon": ({"o": 0.3, "tongue": 0.15, "blend": 0.3}, {"o": 0.45, "tongue": 0.25, "blend": 0.5},
                            {"o": 0.6, "tongue": 0.35, "blend": 0.7}),
              "axolotl": ({"o": 0.3, "tongue": 0.15, "lips_r": 0.16}, {"o": 0.45, "tongue": 0.25, "lips_r": 0.22},
                          {"o": 0.6, "tongue": 0.35, "lips_r": 0.28})}
TONGUE = "tongue"  # the tongue's material name part: its vertices in the joined mouth object


def log(msg):
    print(f"RIG {msg}", flush=True)


def islands(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    seen, out = set(), []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack, isl = [v], []
        seen.add(v.index)
        while stack:
            u = stack.pop()
            isl.append(u.index)
            for e in u.link_edges:
                o = e.other_vert(u)
                if o.index not in seen:
                    seen.add(o.index)
                    stack.append(o)
        out.append(isl)
    bm.free()
    return out


def coords(obj):
    a = np.empty(len(obj.data.vertices) * 3)
    obj.data.vertices.foreach_get("co", a)
    return a.reshape(-1, 3)


def lip_core(x, s, L):
    """The swept lip's cross-section at x along the mouth (s 1: the upper lip, -1: the lower): the core's height and
    depth and the ellipse's vertical and depth radii. Both lips kiss at the fitted lip line; they taper toward the
    corners and tuck back into the cheeks there."""
    hw = L["hw"]
    xc = np.clip(x, -hw, hw)
    u = np.sqrt(np.clip(1 - (xc / hw) ** 2, 0, 1))
    zl, dl = np.polyval(L["kz"], xc), np.polyval(L["kd"], xc)
    taper = 0.18 + 0.82 * u ** 0.6
    rz, rd = L["rz"] * taper, L["rd"] * taper
    front = dl + (L["prot"][s] + (L["full"] - 1) * L["rz"]) * taper - (1 - u) * 0.6 * L["rd"]
    return zl + s * rz, front - rd, rz, rd


def build_lips(head, objs, L, lf, fr, n_st=48, n_ring=24):
    """The chameleon's lips (2b-1b): Meshy's lip zone and the slit's cut row (a jagged row of folded triangles that
    read as stitches, and as teeth with the mouth open) are replaced by a separate swept mesh, two rolled lips of clean
    quad rings along the mouth, in the lips' sampled colour. The skin inside a lip's ellipse is drawn into it (a smooth
    radial remap of 1.6 ellipse radii onto 0.8, no step at the border), the faces then wholly inside and the lining
    between the lips (the slit row) deleted: the open mouth shows the dark cup and the tongue."""
    skin = objs["skin"]
    img = H.base_image(skin.active_material)
    samples = []
    for s in (1, -1):
        for k in (-0.4, -0.15, 0.15, 0.4):
            czz, cdep, rz, rd = (float(v) for v in lip_core(np.array([k * L["hw"]]), s, L))
            samples.append(H.sample_skin(skin, img, Vector((0, 0, czz)) + lf * k * L["hw"] + fr * (cdep + rd)))
    rgb = tuple(float(c) for c in np.median(np.array(samples), axis=0))
    co = coords(skin)
    x, z, d = co @ np.array(lf), co[:, 2], co @ np.array(fr)
    inx = np.abs(x) < L["hw"] * 1.02
    new, e_after, side = co.copy(), np.full(len(co), 9.0), np.zeros(len(co), dtype=np.int32)
    for s in (1, -1):
        czz, cdep, rz, rd = lip_core(x, s, L)
        e = np.hypot((z - czz) / rz, (d - cdep) / rd)
        D = L.get("draw", 1.6)  # the skin drawn in from D ellipse radii (2b-2: hers wider, over her painted band)
        sel = inx & (e < D) & (e < e_after)
        t = np.clip((e - 0.8) / (D - 0.8), 0, 1)
        e2 = np.where(e < 0.8, e, 0.8 + (D - 0.8) * t * t * (2 - t))
        k = e2 / np.maximum(e, 1e-9)
        nz, nd = czz + (z - czz) * k, cdep + (d - cdep) * k
        moved = co + np.outer(nz - z, UP) + np.outer(nd - d, fr)
        new[sel] = moved[sel]
        side[sel] = s
        e_after = np.where(sel, e2, np.minimum(e_after, e))
    zl, dl = np.polyval(L["kz"], np.clip(x, -L["hw"], L["hw"])), np.polyval(L["kd"], np.clip(x, -L["hw"], L["hw"]))
    gap = (np.abs(x) < 0.97 * L["hw"]) & (np.abs(z - zl) < 0.8 * L["rz"]) & (d < dl) & (d > dl - 1.6 * L["m"])
    gone = (e_after < 0.98) | gap
    skin.data.vertices.foreach_set("co", new.ravel())
    att = skin.data.attributes.new("lip_side", "INT", "POINT")  # read back by the weights, after the deletion
    att.data.foreach_set("value", side)
    skin.data.update()
    above = z >= zl
    lipzone = np.abs(x) < 1.02 * L["hw"]
    bm = bmesh.new()
    bm.from_mesh(skin.data)
    bm.faces.ensure_lookup_table()

    def doomed(f):
        ix = [v.index for v in f.verts]
        if all(gone[i] for i in ix):
            return True
        sides = {int(side[i]) for i in ix}
        if {1, -1} <= sides:  # drawn into both lips: it would hang across the open mouth
            return True
        return bool(sides - {0}) and any(lipzone[i] for i in ix) and len({bool(above[i]) for i in ix}) == 2

    dead = [f for f in bm.faces if doomed(f)]
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    bm.to_mesh(skin.data)
    bm.free()
    skin.data.update()
    # the swept mesh: rings round each lip's core, denser toward the corners, a pole closing each end
    xs = L["hw"] * np.sin(np.linspace(-1, 1, n_st) * math.pi / 2)
    verts, faces, uvs = [], [], []
    th = np.arange(n_ring) * 2 * math.pi / n_ring
    for s in (1, -1):
        base = len(verts)
        czz, cdep, rz, rd = lip_core(xs, s, L)
        for i in range(n_st):
            for j in range(n_ring):
                # the flank away from the line (o 1 at its top) runs out into the skin as a tail, outward and back:
                # a soft crease where lip meets skin instead of a round tube glued on (2b-2)
                o = max(0.0, s * math.sin(th[j]))
                verts.append(lf * float(xs[i]) + UP * float(czz[i] + rz[i] * math.sin(th[j]) * (1 + 0.8 * L["blend"] * o ** 3))
                             + fr * float(cdep[i] + rd[i] * math.cos(th[j]) - 0.6 * L["blend"] * rd[i] * o ** 2))
                uvs.append((i / (n_st - 1), j / n_ring))
        for i in range(n_st - 1):
            for j in range(n_ring):
                j1 = (j + 1) % n_ring
                faces.append((base + i * n_ring + j, base + i * n_ring + j1, base + (i + 1) * n_ring + j1,
                              base + (i + 1) * n_ring + j))
        for i, sg in ((0, -1), (n_st - 1, 1)):
            pole = len(verts)
            verts.append(lf * float(xs[i] + sg * 0.6 * rz[i]) + UP * float(czz[i]) + fr * float(cdep[i]))
            uvs.append((0.5, 0.5))
            for j in range(n_ring):
                faces.append((base + i * n_ring + j, base + i * n_ring + (j + 1) % n_ring, pole))
    me = bpy.data.meshes.new(f"{head}_lips")
    me.from_pydata([tuple(v) for v in verts], [], faces)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    uvl = me.uv_layers.new(name="UVMap").data
    for loop in me.loops:
        uvl[loop.index].uv = uvs[loop.vertex_index]
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    bsdf = next((n for n in skin.active_material.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    rough = (float(bsdf.inputs["Roughness"].default_value) if bsdf and not bsdf.inputs["Roughness"].is_linked
             else 0.5)  # the skin's own shading (2b-2): the lips read as skin, not as a glossier tube
    me.materials.append(H.principled(f"{head}_lips", rgb=rgb, rough=rough))
    obj = bpy.data.objects.new(f"{head}_lips", me)
    bpy.context.collection.objects.link(obj)
    return obj, {"radius": L["radius"], "full": L["full"], "blend": L["blend"], "rough": round(rough, 3), "srgb": [round(c, 4) for c in rgb],
                 "skin_moved": int((e_after < L.get("draw", 1.6)).sum()), "skin_faces_deleted": len(dead), "tris": H.tris(obj)}


def slit_sides(skin, x, dz, hw, m):
    """Which lip each vertex round the slit belongs to by the cut, not by its height: the vertices within 0.9 half
    widths and a mouth unit of the line split into connected pieces (the cut parts them; the corners, where the outer
    skin joins them, are left out), each piece the side of its median height against the line (1 upper, -1 lower)."""
    zone = (np.abs(x) < 0.9 * hw) & (np.abs(dz) < 1.0 * m)
    me = skin.data
    ed = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get("vertices", ed)
    ed = ed.reshape(-1, 2)
    ed = ed[zone[ed[:, 0]] & zone[ed[:, 1]]]
    parent = np.arange(len(x))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b in ed:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    roots = np.array([find(i) for i in range(len(x))])
    side = np.zeros(len(x), dtype=np.int32)
    for r in np.unique(roots[zone]):
        idx = np.nonzero(zone & (roots == r))[0]
        below = float((dz[idx] < 0).mean())
        if len(idx) > 40 and 0.2 < below < 0.8:  # a piece across the line: the cut did not part it, keep the height
            continue
        side[idx] = 1 if below < 0.5 else -1
    return side


def clear_lining(skin, lf, fr, kz, kd, hw, m, spec, unit):
    """The mouth's lining behind the slit (2b-1b): Meshy's slit is cut along a jagged path whose folded rows read as
    teeth, or as dark blobs at the corners, once the mouth opens. Faces wholly inside the volume behind the line (the
    half width's fraction spec[0], spec[1] units up and down, from spec[2] to 2 mouth units behind it), or with a vertex
    inside it and vertices on both sides of the line, are deleted: the open mouth shows the dark cup behind."""
    co = coords(skin)
    x, z, d = co @ np.array(lf), co[:, 2], co @ np.array(fr)
    xc = np.clip(x, -hw, hw)
    zl, dl = np.polyval(kz, xc), np.polyval(kd, xc)
    inner = ((np.abs(x) < spec[0] * hw) & (np.abs(z - zl) < spec[1] * unit) & (d < dl - spec[2] * m)
             & (d > dl - 2.0 * m))
    above = z >= zl
    bm = bmesh.new()
    bm.from_mesh(skin.data)
    dead = []
    for f in bm.faces:
        ix = [v.index for v in f.verts]
        if all(inner[i] for i in ix) or (any(inner[i] for i in ix) and len({bool(above[i]) for i in ix}) == 2):
            dead.append(f)
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    bm.to_mesh(skin.data)
    bm.free()
    skin.data.update()
    return len(dead)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--head", required=True)
    ap.add_argument("--blend", type=Path, required=True)
    ap.add_argument("--build", type=Path, required=True)
    ap.add_argument("--expr", type=Path, required=True)
    ap.add_argument("--view2d", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--grid", action="store_true", help="the variant grids (lips, expression amounts), no export")
    ap.add_argument("--grid-mouth", action="store_true", help="2b-2's mouth grid (GRID_MOUTH), no export")
    ap.add_argument("--suffix", default="", help="the review sheet's name suffix, e.g. _v2")
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    args.out.mkdir(parents=True, exist_ok=True)
    rc = RIGCFG[args.head]
    if args.grid_mouth:  # rows: per variant the mouth at rest and smiling (3/4), talking and surprised (front)
        rows = []
        for over in GRID_MOUTH[args.head]:
            lips = dict(rc["lips"], radius=over["lips_r"]) if "lips_r" in over else rc["lips"]
            rows.append(rig(args, lips, rc["amount"], final=False, cells="mouth", over=over))
        H.save_rgb(np.concatenate(rows[::-1], axis=0), args.out / f"{args.head}_grid_mouth.png")
        return
    if not args.grid:
        rig(args, rc["lips"], rc["amount"], final=True)
        return
    rows = []
    if rc["lips"]:
        for lips in GRID_LIPS:  # rows: per variant the mouth at rest (3/4 and front), talking and surprised
            rows.append(rig(args, lips, rc["amount"], final=False, cells="lips"))
        H.save_rgb(np.concatenate(rows[::-1], axis=0), args.out / f"{args.head}_grid_lips.png")
    cols = [rig(args, rc["lips"], {e: f for e in EXPRESSIONS[1:]}, final=False, cells="expr") for f in GRID_AMOUNTS]
    # one row per expression: the 2D cell, then the amounts left to right
    top = crops_2d(args.expr, 320)
    grid = [np.concatenate([top[i + 1], *[c[i] for c in cols]], axis=1) for i in range(len(EXPRESSIONS) - 1)]
    H.save_rgb(np.concatenate(grid[::-1], axis=0), args.out / f"{args.head}_grid_expr.png")


def rig(args, lips, amounts, final, cells=None, over=None):
    """One rig of the head from its build: with final, the GLB, rig.json, the .blend and the review sheet; else the
    grid cells (`lips`: one row of mouth close-ups; `expr`: the five expressions' 3/4 cells) as arrays."""
    head, out = args.head, args.out
    rc = {**RIGCFG[head], **(over or {})}
    bpy.ops.wm.open_mainfile(filepath=str(args.blend))
    build = json.loads(args.build.read_text(encoding="utf-8"))
    cfg = H.HEADS[head]
    fr = Vector(build["front"])
    lf = UP.cross(fr)  # the character's left
    m = cfg.get("mouth_scale") or build["eye_fit"]["r"]
    line = build["lip_line"]
    pts = np.array(line["line"], dtype=float)
    hw = float(line["half_width"])
    z0, d0 = float(pts[0, 1]), float(pts[0, 2])
    kz = np.polyfit(np.concatenate([-pts[:0:-1, 0], pts[:, 0]]), np.concatenate([pts[:0:-1, 1], pts[:, 1]]), 4)
    kd = np.polyfit(np.concatenate([-pts[:0:-1, 0], pts[:, 0]]), np.concatenate([pts[:0:-1, 2], pts[:, 2]]), 4)
    eyes = {t: (Vector(e["centre"]), e["radius"]) for t, e in build["eyes"].items()}
    R = eyes["L"][1]
    objs = {k: bpy.data.objects.get(f"{head}_{k}") for k in ("skin", "eyes", "lids", "mouth", "gills")}
    objs = {k: o for k, o in objs.items() if o is not None}
    for o in list(bpy.data.objects):
        if o.type != "MESH" or o not in objs.values():
            if o.type in ("MESH", "ARMATURE"):
                bpy.data.objects.remove(o)
    H.select_only(list(objs.values()))
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)  # local == world from here on
    report = {"head": head, "m": m, "R": R, "amount": amounts}

    def at(x, z, d):
        return Vector((0, 0, z)) + lf * x + fr * d

    if lips:
        tube = build.get("lip_tube")  # the chameleon's fitted protrusions; the axolotl's band sits flush ("prot")
        prot = ({1: tube["upper"]["protrusion"], -1: tube["lower"]["protrusion"]} if tube
                else {1: lips.get("prot", 0.0) * m, -1: lips.get("prot", 0.0) * m})
        L = dict(lips, hw=hw, kz=kz, kd=kd, m=m, rz=lips["radius"] * m, rd=lips["radius"] * lips["full"] * m,
                 prot=prot, blend=rc.get("blend", 0.0))
        objs["lips"], report["lips"] = build_lips(head, objs, L, lf, fr)
        log(f"lips {report['lips']}")
    report["lining_faces_deleted"] = clear_lining(objs["skin"], lf, fr, kz, kd, hw, m, rc["lining"],
                                                  lips["radius"] * m if lips else m)
    log(f"lining faces deleted {report['lining_faces_deleted']}")
    if rc.get("add_tongue") and not any(TONGUE in (mt.name if mt else "") for mt in objs["mouth"].data.materials):
        # 2b-2: her tongue (the 2D's pink one in talk), as the head build makes his: a flat ellipsoid on the cup's floor
        tongue = H.sphere_mesh("tongue", at(0, z0 - 0.32 * m, d0 - 0.55 * m), G.frame(tuple(fr)), 1.0, n_a=20, n_p=10)
        tongue.data.transform(Matrix.Diagonal((hw * 0.45, 0.42 * m, 0.14 * m, 1.0)))
        tongue.data.materials.append(H.principled(f"{head}_tongue", rgb=H.TONGUE_RGB, rough=0.45))
        H.select_only([objs["mouth"], tongue], active=objs["mouth"])
        bpy.ops.object.join()
        report["tongue_added"] = True

    # ------------------------------------------------------------------ the skeleton
    skin_co = coords(objs["skin"])
    zh = z0 - 1.5 * m
    slab = skin_co[np.abs(skin_co[:, 2] - zh) < 0.08 * m]
    neck = Vector(slab.mean(0)) if len(slab) else at(0, zh, d0 - 2 * m)
    neck.x = 0.0
    top = float(skin_co[:, 2].max())
    corner_x = float(pts[-1, 0])
    corner = {s: at(s * corner_x, float(np.polyval(kz, corner_x)), float(np.polyval(kd, corner_x))) for s in (1, -1)}
    bones = {"Head": (neck, Vector((neck.x, neck.y, top)), None),
             "Jaw": (at(0, z0 + 0.6 * m, d0 - 2.2 * m), at(0, z0 - 1.2 * m, d0 - 0.2 * m), "Head"),
             "LipUpper": (at(0, z0 + 0.25 * m, d0 - 0.4 * m), at(0, z0 + 0.25 * m, d0 - 0.1 * m), "Head"),
             "LipLower": (at(0, z0 - 0.25 * m, d0 - 0.4 * m), at(0, z0 - 0.25 * m, d0 - 0.1 * m), "Jaw")}
    kd_skin = KDTree(len(skin_co))
    for i, c in enumerate(skin_co):
        kd_skin.insert(c, i)
    kd_skin.balance()
    brow_pts = {}
    for t, s, side in (("L", 1, "Left"), ("R", -1, "Right")):
        c, r = eyes[t]
        bones[f"{side}LipCorner"] = (corner[s], corner[s] + fr * 0.3 * m, "Head")
        for name, sx in (("BrowInner", -0.45), ("BrowOuter", 0.45)):
            probe = c + (fr * 0.55 + UP * 0.9 + lf * s * sx).normalized() * 1.6 * r
            p, _, _ = kd_skin.find(probe)
            brow_pts[f"{side}{name}"] = Vector(p)
            bones[f"{side}{name}"] = (Vector(p), Vector(p) + fr * 0.3 * r, "Head")
        bones[f"{side}Eye"] = (c, c + fr * r, "Head")
        bones[f"{side}LidUpper"] = (c, c + (fr + UP * 0.6).normalized() * r, "Head")
        bones[f"{side}LidLower"] = (c, c + (fr - UP * 0.6).normalized() * r, "Head")
    gill_chain = {}
    if "gills" in objs:
        gco = coords(objs["gills"])
        roots = {n: Vector(p) for n, p in json.loads(objs["gills"]["pivots"]).items()}
        for isl in islands(objs["gills"].data):
            pts_i = gco[isl]
            name = min(roots, key=lambda n: float(np.min(np.linalg.norm(pts_i - np.array(roots[n]), axis=1))))
            gill_chain.setdefault(name, []).extend(isl)
        for name, idx in gill_chain.items():
            root = roots[name]
            far = gco[idx][np.argmax(np.linalg.norm(gco[idx] - np.array(root), axis=1))]
            tip = Vector(far)
            side = "Left" if name[5] == "L" else "Right"
            for k in range(3):
                bones[f"{side}Gill{name[6:]}_{k + 1}"] = (root.lerp(tip, k / 3), root.lerp(tip, (k + 1) / 3),
                                                         "Head" if k == 0 else f"{side}Gill{name[6:]}_{k}")
    arm_data = bpy.data.armatures.new(f"{head}_rig")
    arm = bpy.data.objects.new(f"{head}_rig", arm_data)
    bpy.context.collection.objects.link(arm)
    H.select_only([arm])
    bpy.ops.object.mode_set(mode="EDIT")
    for name, (h_, t_, _) in bones.items():
        eb = arm_data.edit_bones.new(name)
        eb.head, eb.tail = h_, t_
        eb.roll = 0.0
    for name, (_, _, parent) in bones.items():
        if parent:
            arm_data.edit_bones[name].parent = arm_data.edit_bones[parent]
            arm_data.edit_bones[name].use_connect = "Gill" in name and not name.endswith("_1")
    bpy.ops.object.mode_set(mode="OBJECT")
    report["bones"] = len(bones)
    log(f"bones {len(bones)}")

    # ------------------------------------------------------------------ weights
    def zl_dl(x):
        xc = np.clip(x, -hw, hw)
        return np.polyval(kz, xc), np.polyval(kd, xc)

    def gauss(p, c, sig):
        return np.exp(-np.sum((p - np.array(c)) ** 2, axis=1) / (2 * sig * sig))

    def face_weights(co):
        x, z = co @ np.array(lf), co[:, 2]
        d = co @ np.array(fr)
        zl, dl = zl_dl(x)
        below = H.sstep(0.05 * m, -0.25 * m, z - zl)
        above = 1 - below
        jaw_c = at(0, z0 - 0.6 * m, d0 - 1.0 * m)
        rel = (co - np.array(jaw_c))
        e = np.sqrt((rel @ np.array(lf) / (hw + 0.6 * m)) ** 2 + (rel @ np.array(fr) / (1.8 * m)) ** 2
                    + (rel[:, 2] / (1.4 * m)) ** 2)
        w = {"Jaw": below * (1 - H.sstep(0.55, 1.0, e))}
        lipzone = H.sstep(dl - 0.9 * m, dl - 0.3 * m, d) * (1 - H.sstep(0.85 * hw, 1.2 * hw, np.abs(x)))
        band = lambda s: np.exp(-((z - zl - s * 0.3 * m) / (0.35 * m)) ** 2)  # noqa: E731
        xs = np.exp(-(x / (0.55 * hw)) ** 2)
        w["LipUpper"] = 0.8 * above * band(1) * xs * lipzone
        w["LipLower"] = 0.8 * below * band(-1) * xs * lipzone
        for s, side in ((1, "Left"), (-1, "Right")):
            w[f"{side}LipCorner"] = 0.9 * gauss(co, corner[s], 0.4 * m) * H.sstep(-0.2 * m, 0.4 * m, (co @ np.array(lf)) * s)
            for name in BROWS:
                c, r = eyes["L" if s == 1 else "R"]
                w[f"{side}{name}"] = (0.85 * gauss(co, brow_pts[f"{side}{name}"], rc["brow"][0] * r)
                                      * H.sstep(c.z + 0.4 * r, c.z + 0.8 * r, z))
        return w

    def assign(obj, weights):
        mod = obj.modifiers.new("rig", "ARMATURE")
        mod.object = arm
        obj.parent = arm
        total = np.zeros(len(obj.data.vertices))
        for name, w in weights.items():
            total += w
        scale = np.where(total > 1.0, 1.0 / np.maximum(total, 1e-9), 1.0)
        rest = 1.0 - np.minimum(total, 1.0)
        weights = {k: v * scale for k, v in weights.items()}
        weights["Head"] = weights.get("Head", 0) + rest
        counts = {}
        for name, w in weights.items():
            idx = np.nonzero(w > 1e-3)[0]
            if not len(idx):
                continue
            vg = obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
            for i in idx:
                vg.add([int(i)], float(w[i]), "REPLACE")
            counts[name] = int(len(idx))
        return counts

    report["weights"] = {}
    # every vertex round the slit weighted on its own lip's side of the line: the side the cut puts it on (the slit is
    # cut along a jagged path, so the height against the fitted line puts some of the lining on the wrong lip and the
    # open mouth stretched those faces into a row of teeth), else the lip it was drawn into
    ev = skin_co.copy()
    zl_, _ = zl_dl(skin_co @ np.array(lf))
    side = slit_sides(objs["skin"], skin_co @ np.array(lf), skin_co[:, 2] - zl_, hw, m)
    if "lip_side" in objs["skin"].data.attributes:
        drawn = np.empty(len(skin_co), dtype=np.int32)
        objs["skin"].data.attributes["lip_side"].data.foreach_get("value", drawn)
        side = np.where(side == 0, drawn, side)
        objs["skin"].data.attributes.remove(objs["skin"].data.attributes["lip_side"])
    report["slit_sides"] = {"upper": int((side > 0).sum()), "lower": int((side < 0).sum())}
    ev[:, 2] = np.where(side > 0, np.maximum(skin_co[:, 2], zl_ + 0.15 * m),
                        np.where(side < 0, np.minimum(skin_co[:, 2], zl_ - 0.3 * m), skin_co[:, 2]))
    # 2b-2: past the lip corners Meshy's slit runs on; both its edges weighted as if on the line, so the open mouth
    # never parts them into flaps (the painted lip colour showing as fins beside the O)
    xa, dzs = np.abs(skin_co @ np.array(lf)), skin_co[:, 2] - zl_
    past = (side == 0) & (xa > 0.9 * hw) & (xa < 1.5 * hw) & (np.abs(dzs) < 0.5 * m)
    ev[:, 2] = np.where(past, zl_ + dzs * H.sstep(0.15 * m, 0.5 * m, np.abs(dzs)), ev[:, 2])
    report["slit_past_corners"] = int(past.sum())
    sk = face_weights(ev)
    report["weights"]["skin"] = assign(objs["skin"], sk)
    n_skin = len(skin_co)
    co = coords(objs["eyes"])
    left = (co @ np.array(lf)) > 0
    report["weights"]["eyes"] = assign(objs["eyes"], {"LeftEye": left * 1.0, "RightEye": (~left) * 1.0})
    co = coords(objs["lids"])
    lw = {f"{s}{k}": np.zeros(len(co)) for s in ("Left", "Right") for k in ("LidUpper", "LidLower")}
    for isl in islands(objs["lids"].data):
        p = co[isl].mean(0)
        side = "Left" if p @ np.array(lf) > 0 else "Right"
        c = eyes["L" if side == "Left" else "R"][0]
        lw[f"{side}{'LidUpper' if p[2] > c.z else 'LidLower'}"][isl] = 1.0
    report["weights"]["lids"] = assign(objs["lids"], lw)
    co = coords(objs["mouth"])
    # the cup and tongue follow the face (corners, lips), not the jaw alone: no cup showing at moved corners
    report["weights"]["mouth"] = assign(objs["mouth"], face_weights(co))
    if "lips" in objs:
        co = coords(objs["lips"])
        zl_, _ = zl_dl(co @ np.array(lf))
        # by tube, never by height: the upper lip's bottom ring lies on the line itself, and a height test split it
        # vertex by vertex between the lips (a row of teeth with the mouth open); build_lips writes the upper first
        upper = np.arange(len(co)) < len(co) // 2
        ev = co.copy()  # the upper lip weighted as if above the line, the lower as if below: no jaw in the upper lip
        ev[:, 2] = np.where(upper, np.maximum(co[:, 2], zl_ + 0.15 * m), np.minimum(co[:, 2], zl_ - 0.3 * m))
        report["weights"]["lips"] = assign(objs["lips"], face_weights(ev))
    if "gills" in objs:
        gw = {}
        gco = coords(objs["gills"])
        for name, idx in gill_chain.items():
            side = "Left" if name[5] == "L" else "Right"
            b1, b3 = bones[f"{side}Gill{name[6:]}_1"], bones[f"{side}Gill{name[6:]}_3"]
            root, tip = np.array(b1[0]), np.array(b3[1])
            u = tip - root
            t = np.clip((gco[idx] - root) @ u / float(u @ u), 0, 1)
            s = t * 3 - 0.5
            for k in range(3):
                wk = np.clip(1 - np.abs(s - k), 0, 1)
                if k == 0:
                    wk = np.where(s < 0, 1.0, wk)
                if k == 2:
                    wk = np.where(s > 2, 1.0, wk)
                full = gw.setdefault(f"{side}Gill{name[6:]}_{k + 1}", np.zeros(len(gco)))
                full[idx] = wk
        report["weights"]["gills"] = assign(objs["gills"], gw)
    log(f"weights {report['weights']['skin']}")

    # ------------------------------------------------------------------ poses baked into blend shapes
    pose_bones = arm.pose.bones

    def reset():
        for pb in pose_bones:
            pb.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()

    def move(name, delta=Vector(), rot=None):
        pb = pose_bones[name]
        cur = pb.matrix.copy()
        hd = cur.to_translation()
        mat = Matrix.Translation(delta) @ Matrix.Translation(hd)
        if rot is not None:
            mat = mat @ Matrix.Rotation(math.radians(rot[1]), 4, rot[0])
        pb.matrix = mat @ Matrix.Translation(-hd) @ cur
        bpy.context.view_layer.update()

    def apply_pose(spec, f=1.0):
        """A paired bone's move is (out from the midline, up, front) in its unit; "in" pulls the lip corners toward
        the middle (the O); the Jaw rotates open round the character's left axis."""
        reset()
        if spec.get("jaw"):
            move("Jaw", rot=(UP.cross(fr).normalized(), spec["jaw"] * f))
        for bname, (a, b, c) in spec["bones"].items():
            a = a if a == "in" else a * f
            b, c = b * f, c * f
            unit = R * rc["brow"][1] if bname in BROWS else m
            if bname in ("LipCorner", *BROWS):
                for s_, side in ((1, "Left"), (-1, "Right")):
                    a_ = -0.28 * f * hw / unit if a == "in" else a
                    move(f"{side}{bname}", (lf * s_ * a_ + UP * b + fr * c) * unit)
            else:
                move(bname, (UP * b + fr * c) * unit)

    # correctives (2b-1b), added to the posed shapes: the smile's cheeks lifted and puffed between the eye and the
    # corner; the angry face's knit, the skin between the brows pulled down and forward into one smooth fold
    cheek_c, cheek_s = {}, {}
    for t, s_ in (("L", 1), ("R", -1)):
        c, r = eyes[t]
        bottom = c - UP * 1.05 * r
        p, _, _ = kd_skin.find(bottom.lerp(corner[s_], 0.45) + fr * r)
        cheek_c[t], cheek_s[t] = np.array(p), 0.35 * (bottom - corner[s_]).length
    knit_c = np.array(kd_skin.find((brow_pts["LeftBrowInner"] + brow_pts["RightBrowInner"]) / 2 + fr * R)[0])

    mouth_co = coords(objs["mouth"])
    tongue_v = np.zeros(len(mouth_co), dtype=bool)
    for poly in objs["mouth"].data.polygons:
        mt = objs["mouth"].data.materials[poly.material_index] if objs["mouth"].data.materials else None
        if mt is not None and TONGUE in mt.name:
            tongue_v[list(poly.vertices)] = True
    report["tongue_vertices"] = int(tongue_v.sum())

    def corrective(name, part, co, cur, f):
        """co: the part's rest positions, cur: posed. 2b-2: the surprised O squeezes the mouth round toward the
        midline (rings rounded, corners in) and puckers it forward; talk lifts the tongue into view (half of it in the
        O)."""
        dlt = np.zeros_like(co)
        if name == "surprised":
            x = cur @ np.array(lf)
            g = np.exp(-(x / (1.3 * hw)) ** 2 - ((cur[:, 2] - (z0 - 0.3 * m)) / (1.8 * m)) ** 2)
            g = g * H.sstep(zl_dl(co @ np.array(lf))[1] - 1.6 * m, zl_dl(co @ np.array(lf))[1] - 0.6 * m,
                            co @ np.array(fr))
            dlt += -np.outer(x * rc["o"] * g, np.array(lf)) + np.outer(g, np.array(fr)) * rc["pucker"] * m
        if part == "mouth" and name in ("talk", "surprised") and tongue_v.any():
            k = 1.0 if name == "talk" else 0.5
            dlt[tongue_v] += np.array(UP + fr * 0.5) * rc["tongue"] * m * k
        if name == "smile":
            for t in ("L", "R"):
                dlt += np.outer(gauss(co, cheek_c[t], cheek_s[t]), np.array(UP * 0.8 + fr * 0.35)) * rc["cheek"] * m * f
        if name == "angry":
            g = gauss(co, knit_c, 0.9 * R * rc["brow"][1])
            dlt += np.outer(g, np.array(-UP * 0.6 + fr * 0.5)) * rc["knit"] * R * rc["brow"][1] * f
        return dlt

    parts = [k for k in ("skin", "mouth", "lips") if k in objs]

    def smooth_tubes(dlt, n_st=48, n_ring=24, passes=8):
        """The swept lips' per-vertex moves averaged along each tube's stations ([1, 2, 1] / 4, the ends reflected),
        each pole taking its end ring's mean."""
        out_ = dlt.copy()
        blk = n_st * n_ring + 2
        for b in range(len(dlt) // blk):
            r = dlt[b * blk: b * blk + n_st * n_ring].reshape(n_st, n_ring, 3)
            for _ in range(passes):
                pad = np.concatenate([r[:1], r, r[-1:]], axis=0)
                r = 0.25 * pad[:-2] + 0.5 * pad[1:-1] + 0.25 * pad[2:]
            out_[b * blk: b * blk + n_st * n_ring] = r.reshape(-1, 3)
            out_[b * blk + n_st * n_ring] = r[0].mean(0)
            out_[b * blk + n_st * n_ring + 1] = r[-1].mean(0)
        return out_
    rest = {k: coords(objs[k]) for k in parts}
    deformed = {}
    for name in EXPRESSIONS[1:]:
        f = amounts.get(name, 1.0)
        apply_pose(POSES[name], f)
        dg = bpy.context.evaluated_depsgraph_get()
        deformed[name] = {}
        for k in parts:
            ev = np.array([tuple(v.co) for v in objs[k].evaluated_get(dg).data.vertices])
            deformed[name][k] = ev + corrective(name, k, rest[k], ev, f)
        if "lips" in objs and rc.get("tube_smooth"):  # 2b-2: smoothed along each tube (no kink at the corners)
            deformed[name]["lips"] = rest["lips"] + smooth_tubes(deformed[name]["lips"] - rest["lips"],
                                                                 passes=rc["tube_smooth"])
    reset()

    # the lids: rebuilt at the pose's edge angles, matched to the joined lids by their rest positions
    lid_co = coords(objs["lids"])
    kd_lid = KDTree(len(lid_co))
    for i, c in enumerate(lid_co):
        kd_lid.insert(c, i)
    kd_lid.balance()
    worst = 0.0

    def lid_points(key, params, d_from=0.0, closed_to=None, tilt=0.0, frac=1.0):
        p = dict(params)
        p.pop("centre"), p.pop("axes")
        c, axes = Vector(params["centre"]), tuple(tuple(a) for a in params["axes"])
        if closed_to is not None:  # frac of the way from the rest edge to 2 degrees past the lower lid's edge
            for k in ("beta_from", "corner", "corner_outer"):
                if p.get(k) is not None and closed_to.get(k) is not None:
                    p[k] = p[k] + frac * (closed_to[k] - 2.0 - p[k])
        else:
            lim = p["beta_to"] - 8.0 if p["beta_to"] > p["beta_from"] else p["beta_to"] + 8.0
            p["beta_from"] = float(min(p["beta_from"] + d_from, lim) if lim > p["beta_from"] else max(p["beta_from"] + d_from, lim))
        o = H.lid_mesh(f"tmp_{key}", Vector((0, 0, 0)), axes, **p)
        pts_ = np.array([tuple(v.co) for v in o.data.vertices])
        bpy.data.objects.remove(o)
        if tilt:
            side = 1 if c.dot(lf) > 0 else -1
            ang = math.radians(tilt)
            rot = Matrix.Rotation(ang, 3, fr)
            if (rot @ (-lf * side)).z > 0:  # the inner corner goes down for a positive tilt
                rot = Matrix.Rotation(-ang, 3, fr)
            pts_ = pts_ @ np.array(rot).T
        return pts_ + np.array(c)

    lid_rest_idx = {}
    for key, params in build["lids"].items():
        rest_pts = lid_points(key, params)
        idx = []
        for p in rest_pts:
            _, i, dist = kd_lid.find(p)
            idx.append(i)
            worst = max(worst, dist)
        lid_rest_idx[key] = np.array(idx)
    report["lid_match_worst"] = worst
    log(f"lid rebuild matched, worst {worst:.2e}")
    def flatten(pts_, tag, k):
        """The front bulge pressed back toward the eye's centre along the gaze (k: the fraction)."""
        c = np.array(eyes[tag][0])
        a = np.maximum((pts_ - c) @ np.array(fr), 0.0)
        return pts_ - np.outer(a * k, np.array(fr))

    flat = rc["blink_flat"]
    lid_keys = {}
    for tag in ("L", "R"):
        k = lid_co.copy()
        up_, lo_ = build["lids"][f"upper_{tag}"], build["lids"][f"lower_{tag}"]
        ui = lid_rest_idx[f"upper_{tag}"]
        k[ui] = flatten(lid_points(f"upper_{tag}", up_, closed_to=lo_), tag, flat)
        li = lid_rest_idx[f"lower_{tag}"]
        k[li] = flatten(lid_co[li], tag, flat)
        lid_keys[f"blink_{tag}"] = k
        # the corrective: a blend shape is a straight line, so blink_* at 0.5 cuts the chord through the eyeball; at
        # weight 4t(1-t) with blink_* at t, blink_arc_* puts the half-closed lid back on its sphere (exact at 0.5)
        arc = lid_co.copy()
        arc[ui] = lid_co[ui] + flatten(lid_points(f"upper_{tag}", up_, closed_to=lo_, frac=0.5), tag, flat / 2)             - (lid_co[ui] + k[ui]) / 2
        lid_keys[f"blink_arc_{tag}"] = arc
    for name in EXPRESSIONS[1:]:
        spec, f = POSES[name], rc.get("lid", {}).get(name, amounts.get(name, 1.0))
        k = lid_co.copy()
        for tag in ("L", "R"):
            for kind, dfrom, tilt in (("upper", spec["lid"][0] * f, spec["tilt"] * f), ("lower", spec["lid"][1] * f, 0.0)):
                key = f"{kind}_{tag}"
                if dfrom or tilt:
                    k[lid_rest_idx[key]] = lid_points(key, build["lids"][key], d_from=dfrom, tilt=tilt)
        lid_keys[name] = k

    def add_keys(obj, keys):
        if obj.data.shape_keys is None:
            obj.shape_key_add(name="Basis", from_mix=False)
        for name, pts_ in keys.items():
            kb = obj.shape_key_add(name=name, from_mix=False)
            kb.data.foreach_set("co", np.ascontiguousarray(pts_, dtype=np.float32).ravel())
            kb.value = 0.0

    for k in parts:
        add_keys(objs[k], {n: deformed[n][k] for n in EXPRESSIONS[1:]})
    add_keys(objs["lids"], lid_keys)
    eye_co = coords(objs["eyes"])
    side_l = (eye_co @ np.array(lf)) > 0
    eye_keys = {}
    for tag, sel in (("L", side_l), ("R", ~side_l)):
        k = eye_co.copy()
        k[sel] = flatten(eye_co[sel], tag, flat)
        eye_keys[f"blink_{tag}"] = k
    add_keys(objs["eyes"], eye_keys)
    report["shape_keys"] = {k: [b.name for b in o.data.shape_keys.key_blocks[1:]] for k, o in objs.items()
                            if o.data.shape_keys}
    report["max_shift"] = {n: round(float(np.max(np.linalg.norm(deformed[n]["skin"] - skin_co, axis=1))), 4)
                           for n in EXPRESSIONS[1:]}
    log(f"shape keys {report['shape_keys']}")
    log(f"max skin shift {report['max_shift']}")

    # ------------------------------------------------------------------ export
    # the lids had no UVs: with blend shapes Godot generates tangents and errors without them ("UVs are required to
    # generate tangents"); a planar projection per eye, unused by the lid's flat material
    lids_me = objs["lids"].data
    if not lids_me.uv_layers:
        uvl = lids_me.uv_layers.new(name="UVMap").data
        for loop in lids_me.loops:
            p = lids_me.vertices[loop.vertex_index].co
            c = eyes["L"][0] if p.dot(lf) > 0 else eyes["R"][0]
            uvl[loop.index].uv = (0.5 + 0.4 * (p - c).dot(lf) / R, 0.5 + 0.4 * (p.z - c.z) / R)
    report["tris"] = {k: H.tris(o) for k, o in objs.items()}
    if final:
        H.select_only([arm, *objs.values()], active=arm)
        bpy.ops.export_scene.gltf(filepath=str(out / f"{head}_rig.glb"), export_format="GLB", use_selection=True,
                                  export_apply=False, export_yup=True, export_animations=False, export_extras=True,
                                  export_skins=True, export_morph=True, export_morph_normal=True)

    # ------------------------------------------------------------------ review
    def set_keys(name, value=1.0):
        for o in objs.values():
            if o.data.shape_keys:
                for kb in o.data.shape_keys.key_blocks[1:]:
                    if name == "blink" and kb.name.startswith("blink_"):
                        kb.value = 4 * value * (1 - value) if "arc" in kb.name else value
                    else:
                        kb.value = value if kb.name == name else 0.0
        bpy.context.view_layer.update()

    cam = H.setup_render(420)
    lo, hi = H.bounds(list(objs.values()))
    view = H.load_rgb(args.view2d / "front.png")
    (out / "views").mkdir(exist_ok=True)
    H.match_exposure(cam, (lo + hi) / 2, fr, max(hi.x - lo.x, hi.y - lo.y, hi.z - lo.z) * 1.3, out, view)
    # the 2D cells' framing: the whole head (crest, gills) and the neck's top
    head_lo = z0 - 2.4 * m
    width = max(abs(float(v.co.dot(lf))) for o in objs.values() for v in o.data.vertices if v.co.z > head_lo) * 2
    face_c = Vector((0.0, 0.0, (top + head_lo) / 2)) + fr * eyes["L"][0].dot(fr) * 0.5
    face_scale = max(top - head_lo, width) * 1.2
    tq = (fr + lf).normalized()
    mouth_c, mouth_s = at(0, z0 - 0.25 * m, d0), hw * 3.0

    def shots(specs, size):
        arrs = []
        for i, (key, value, centre, d, scale) in enumerate(specs):
            set_keys(key, value)
            path = out / "views" / f"rig_cell_{i}.png"
            H.shoot(cam, centre, d, scale, path)
            arrs.append(H.load_rgb(path, (size, size)))
        set_keys(None)
        return arrs

    mouth = [("rest", 1.0, mouth_c, tq, mouth_s), ("talk", 1.0, mouth_c, fr, mouth_s),
             ("surprised", 1.0, mouth_c, fr, mouth_s)]
    if cells == "lips":
        return np.concatenate(shots([("rest", 1.0, mouth_c, fr, mouth_s), *mouth], 320), axis=1)
    if cells == "mouth":
        return np.concatenate(shots([("rest", 1.0, mouth_c, tq, mouth_s), ("smile", 1.0, mouth_c, tq, mouth_s),
                                     ("talk", 1.0, mouth_c, fr, mouth_s), ("surprised", 1.0, mouth_c, fr, mouth_s)],
                                    320), axis=1)
    if cells == "expr":
        return shots([(n, 1.0, face_c, tq, face_scale) for n in EXPRESSIONS[1:]], 320)
    row3d = shots([(n, 1.0, face_c, tq, face_scale) for n in EXPRESSIONS], 420)
    eyes_c, eyes_s = (eyes["L"][0] + eyes["R"][0]) / 2, 2.0 * (abs(eyes["L"][0].dot(lf)) + 1.5 * R)
    strip = shots([("blink", v, eyes_c, fr, eyes_s) for v in (0.0, 0.5, 1.0)] + mouth, 420)
    review_sheet(args, out, head, row3d, strip)
    for o in objs.values():
        for kb in (o.data.shape_keys.key_blocks if o.data.shape_keys else []):
            kb.value = 0.0
    bpy.ops.wm.save_as_mainfile(filepath=str(out / f"{head}_rig.blend"), compress=True)
    (out / "rig.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8", newline="\n")
    log(f"tris {report['tris']}")
    log("done")


def crops_2d(path, cell):
    """The 2D expression sheet's six cells (2 rows of 3) in the sheet's order, each cell x cell."""
    img = bpy.data.images.load(str(path))
    a = H.image_array(img)
    bpy.data.images.remove(img)
    h, w = a.shape[:2]
    out = []
    for r in range(2):  # rows are bottom-up: the 2D's top row first
        for c in range(3):
            crop = a[h - (r + 1) * (h // 2): h - r * (h // 2), c * (w // 3): (c + 1) * (w // 3)]
            tmp = bpy.data.images.new("crop", crop.shape[1], crop.shape[0], alpha=True)
            tmp.pixels.foreach_set(np.ascontiguousarray(crop).ravel())
            tmp.scale(cell, cell)
            out.append(H.image_array(tmp))
            bpy.data.images.remove(tmp)
    return out


def review_sheet(args, out, head, rows3d, strip, cell=420):
    """The 2D expressions above the 3D's (both in the 2D's order), then the blink strip (open, half, closed) and the
    mouth close-ups (rest in 3/4, talking and surprised from the front)."""
    top = crops_2d(args.expr, cell)
    gap = np.ones((8, cell * 6, 4), dtype=np.float32)
    gap[..., :3] = 0.1
    sheet = np.concatenate([np.concatenate(strip, axis=1), gap, np.concatenate(rows3d, axis=1), gap,
                            np.concatenate(top, axis=1)], axis=0)
    sheet[..., 3] = 1.0
    full = out / f"{head}_rig{args.suffix}.png"
    H.save_rgb(sheet, full)
    small = bpy.data.images.load(str(full))
    small.scale(1280, int(1280 * sheet.shape[0] / sheet.shape[1]))
    H.save_rgb(H.image_array(small), out / f"{head}_rig_1280{args.suffix}.png")
    bpy.data.images.remove(small)


if __name__ == "__main__":
    main()
