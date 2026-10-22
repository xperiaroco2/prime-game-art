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
                  "bones": {"LipCorner": ("in", -0.05, 0.10), "LipUpper": (0.0, 0.16, 0.12), "LipLower": (0.0, -0.05, 0.12),
                            "BrowInner": (0.0, 0.30, 0.0), "BrowOuter": (0.0, 0.30, 0.0)}},
    "talk": {"lid": (0.0, 0.0), "tilt": 0.0, "jaw": 10.0,
             "bones": {"LipCorner": (-0.03, 0.0, 0.0), "LipUpper": (0.0, 0.06, 0.0)}},
}
BROWS = ("BrowInner", "BrowOuter")


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--head", required=True)
    ap.add_argument("--blend", type=Path, required=True)
    ap.add_argument("--build", type=Path, required=True)
    ap.add_argument("--expr", type=Path, required=True)
    ap.add_argument("--view2d", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    head, out = args.head, args.out
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
    report = {"head": head, "m": m, "R": R}

    def at(x, z, d):
        return Vector((0, 0, z)) + lf * x + fr * d

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
                w[f"{side}{name}"] = (0.85 * gauss(co, brow_pts[f"{side}{name}"], 0.5 * r)
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
    sk = face_weights(skin_co)
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
    jw = H.sstep(z0 + 0.05 * m, z0 - 0.3 * m, co[:, 2])
    report["weights"]["mouth"] = assign(objs["mouth"], {"Jaw": jw})
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

    def apply_pose(spec):
        """A paired bone's move is (out from the midline, up, front) in its unit; "in" pulls the lip corners toward
        the middle (the O); the Jaw rotates open round the character's left axis."""
        reset()
        if spec.get("jaw"):
            move("Jaw", rot=(UP.cross(fr).normalized(), spec["jaw"]))
        for bname, (a, b, c) in spec["bones"].items():
            unit = R if bname in BROWS else m
            if bname in ("LipCorner", *BROWS):
                for s_, side in ((1, "Left"), (-1, "Right")):
                    a_ = -0.18 * hw / unit if a == "in" else a
                    move(f"{side}{bname}", (lf * s_ * a_ + UP * b + fr * c) * unit)
            else:
                move(bname, (UP * b + fr * c) * unit)

    deformed = {}
    for name in EXPRESSIONS[1:]:
        apply_pose(POSES[name])
        dg = bpy.context.evaluated_depsgraph_get()
        deformed[name] = {k: np.array([tuple(v.co) for v in objs[k].evaluated_get(dg).data.vertices])
                          for k in ("skin", "mouth")}
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
    lid_keys = {}
    for tag in ("L", "R"):
        k = lid_co.copy()
        up_, lo_ = build["lids"][f"upper_{tag}"], build["lids"][f"lower_{tag}"]
        ui = lid_rest_idx[f"upper_{tag}"]
        k[ui] = lid_points(f"upper_{tag}", up_, closed_to=lo_)
        lid_keys[f"blink_{tag}"] = k
        # the corrective: a blend shape is a straight line, so blink_* at 0.5 cuts the chord through the eyeball; at
        # weight 4t(1-t) with blink_* at t, blink_arc_* puts the half-closed lid back on its sphere (exact at 0.5)
        arc = lid_co.copy()
        arc[ui] = lid_co[ui] + lid_points(f"upper_{tag}", up_, closed_to=lo_, frac=0.5) - (lid_co[ui] + k[ui]) / 2
        lid_keys[f"blink_arc_{tag}"] = arc
    for name in EXPRESSIONS[1:]:
        spec = POSES[name]
        k = lid_co.copy()
        for tag in ("L", "R"):
            for kind, dfrom, tilt in (("upper", spec["lid"][0], spec["tilt"]), ("lower", spec["lid"][1], 0.0)):
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

    add_keys(objs["skin"], {n: deformed[n]["skin"] for n in EXPRESSIONS[1:]})
    add_keys(objs["mouth"], {n: deformed[n]["mouth"] for n in EXPRESSIONS[1:]})
    add_keys(objs["lids"], lid_keys)
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
    H.select_only([arm, *objs.values()], active=arm)
    bpy.ops.export_scene.gltf(filepath=str(out / f"{head}_rig.glb"), export_format="GLB", use_selection=True,
                              export_apply=False, export_yup=True, export_animations=False, export_extras=True,
                              export_skins=True, export_morph=True, export_morph_normal=True)
    report["tris"] = {k: H.tris(o) for k, o in objs.items()}

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
    cells = []
    for name in EXPRESSIONS:
        set_keys(name)
        path = out / "views" / f"rig_{name}.png"
        H.shoot(cam, face_c, tq, face_scale, path)
        cells.append(path)
    strip = []
    for i, v in enumerate((0.0, 0.5, 1.0)):
        set_keys("blink", v)
        path = out / "views" / f"rig_blink_{i}.png"
        H.shoot(cam, (eyes["L"][0] + eyes["R"][0]) / 2, fr, 2.0 * (abs(eyes["L"][0].dot(lf)) + 1.5 * R), path)
        strip.append(path)
    set_keys(None)
    for nm, d in (("side", lf), ("front", fr)):
        path = out / "views" / f"rig_{nm}.png"
        H.shoot(cam, face_c, d, face_scale * 1.15, path)
        strip.append(path)
    move("Jaw", rot=(UP.cross(fr).normalized(), 18.0))
    for pb in pose_bones:
        if "Gill" in pb.name:
            pb.rotation_mode = "XYZ"
            pb.rotation_euler = (math.radians(25.0), 0.0, 0.0)
    bpy.context.view_layer.update()
    path = out / "views" / "rig_bones.png"
    H.shoot(cam, face_c, tq, face_scale * 1.15, path)
    strip.append(path)
    reset()
    review_sheet(args, out, head, cells, strip)
    for o in objs.values():
        for kb in (o.data.shape_keys.key_blocks if o.data.shape_keys else []):
            kb.value = 0.0
    bpy.ops.wm.save_as_mainfile(filepath=str(out / f"{head}_rig.blend"), compress=True)
    (out / "rig.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8", newline="\n")
    log(f"tris {report['tris']}")
    log("done")


def review_sheet(args, out, head, cells, strip, cell=420):
    img = bpy.data.images.load(str(args.expr))
    a = H.image_array(img)
    bpy.data.images.remove(img)
    h, w = a.shape[:2]
    top = []
    for r in range(2):  # rows are bottom-up: the 2D's top row first
        for c in range(3):
            crop = a[h - (r + 1) * (h // 2): h - r * (h // 2), c * (w // 3): (c + 1) * (w // 3)]
            tmp = bpy.data.images.new("crop", crop.shape[1], crop.shape[0], alpha=True)
            tmp.pixels.foreach_set(np.ascontiguousarray(crop).ravel())
            tmp.scale(cell, cell)
            top.append(H.image_array(tmp))
            bpy.data.images.remove(tmp)
    rows3d = [H.load_rgb(p, (cell, cell)) for p in cells]
    last = [H.load_rgb(p, (cell, cell)) for p in strip]
    gap = np.ones((8, cell * 6, 4), dtype=np.float32)
    gap[..., :3] = 0.1
    sheet = np.concatenate([np.concatenate(last, axis=1), gap, np.concatenate(rows3d, axis=1), gap,
                            np.concatenate(top, axis=1)], axis=0)
    sheet[..., 3] = 1.0
    H.save_rgb(sheet, out / f"{head}_rig.png")
    small = bpy.data.images.load(str(out / f"{head}_rig.png"))
    small.scale(1280, int(1280 * sheet.shape[0] / sheet.shape[1]))
    H.save_rgb(H.image_array(small), out / f"{head}_rig_1280.png")
    bpy.data.images.remove(small)


if __name__ == "__main__":
    main()
