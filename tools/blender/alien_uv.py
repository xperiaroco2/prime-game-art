"""The alien skin's texture UV (art #196, step M2): a clean layout of `Body` for a 4K texture set, written into the
mesh's first UV layer `UVMap` (glTF TEXCOORD_0; it held nothing used). The other channels stay as they are: `masks`
(TEXCOORD_1), the AO colour (COLOR_0), `rest_xy` and `rest_zn` (TEXCOORD_2/3).

  blender -b --factory-startup --python-exit-code 1 --python tools/blender/alien_uv.py -- \
      --character <ao/build/alien_character.blend> --out <M2/uv>

The method (alien_detail_geom.py holds the parts and settings):
1. Each face's part is the part (`part_of_bone`) of the bone weighing most on most of its vertices, then UV
   ["smooth_labels"] passes of a neighbour majority remove stray faces. The torso is split front and back by its
   depth's middle line per centimetre of height (moved 1 cm back, so the line runs down the flanks under the arms and
   over the back of the shoulders); a hand into its two sides by the T-pose normal's z (palm and back).
2. Seams: every edge between two parts, and each tube part's lengthwise cut (BRANCH_SIDE): the edges between faces
   whose angles around the part's axis lie either side of the cut (`crosses_branch`). The head's axis is vertical
   through its centre (the cut up the nape and along the crest blade's back), an arm's runs from its UpperArm to its
   Hand bone (the cut underneath), a leg's from its UpperLeg to its Foot bone (the cut on the inner side).
3. Angle-based unwrap, then each island scaled to the same texel density times DENSITY of its part, and packed with
   rotation and a margin of UV["margin_px"] at UV["size"] px.
Writes build/alien_character.blend, build_report.json (islands, texel density per part in px/cm at 4K, stretch,
overlaps) and uv_layout.png (the islands coloured per part).
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
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_detail_geom as G  # noqa: E402

UV_LAYER = "UVMap"


def args():
    p = argparse.ArgumentParser()
    p.add_argument("--character", required=True)
    p.add_argument("--out", required=True)
    return p.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])


def vertex_parts(body):
    names = {g.index: g.name for g in body.vertex_groups}
    out = []
    for v in body.data.vertices:
        best, bw = "Hips", -1.0
        for g in v.groups:
            if g.weight > bw:
                best, bw = names[g.group], g.weight
        out.append(G.part_of_bone(best))
    return out


def face_labels(bm, vparts):
    labels = []
    for f in bm.faces:
        cnt = {}
        for v in f.verts:
            cnt[vparts[v.index]] = cnt.get(vparts[v.index], 0) + 1
        labels.append(max(cnt.items(), key=lambda kv: kv[1])[0])
    for _ in range(G.UV["smooth_labels"]):
        new = labels[:]
        for f in bm.faces:
            cnt = {}
            for e in f.edges:
                for g in e.link_faces:
                    if g is not f:
                        cnt[labels[g.index]] = cnt.get(labels[g.index], 0) + 1
            if cnt:
                top, n = max(cnt.items(), key=lambda kv: kv[1])
                if top != labels[f.index] and n > len(f.edges) / 2:
                    new[f.index] = top
        labels = new
    return labels


def torso_mid(bm, labels):
    """Per centimetre of height, the middle of the torso's depth at x = 0 (y), moved 1 cm back."""
    zs, ys = {}, {}
    for f in bm.faces:
        if labels[f.index] != "torso":
            continue
        c = f.calc_center_median()
        if abs(c.x) < 0.04:
            k = int(c.z * 100)
            zs.setdefault(k, []).append(c.y)
    for k, vals in zs.items():
        ys[k] = 0.5 * (min(vals) + max(vals)) + 0.01
    keys = sorted(ys)
    return lambda z: ys[min(keys, key=lambda k: abs(k - z * 100))]


def merge_small(bm, labels):
    """Each connected piece of a label under UV["min_island"] faces takes its neighbours' commonest label (the strays
    a dominant-weight label leaves along a part's edge). Returns the number of faces moved."""
    moved = 0
    for _ in range(4):
        seen = [False] * len(bm.faces)
        changed = 0
        for f0 in bm.faces:
            if seen[f0.index]:
                continue
            lab = labels[f0.index]
            comp, stack, border = [], [f0], {}
            seen[f0.index] = True
            while stack:
                f = stack.pop()
                comp.append(f)
                for e in f.edges:
                    for g in e.link_faces:
                        if labels[g.index] == lab:
                            if not seen[g.index]:
                                seen[g.index] = True
                                stack.append(g)
                        else:
                            border[labels[g.index]] = border.get(labels[g.index], 0) + 1
            if len(comp) < G.UV["min_island"] and border:
                to = max(border.items(), key=lambda kv: kv[1])[0]
                for f in comp:
                    labels[f.index] = to
                changed += len(comp)
        moved += changed
        if not changed:
            break
    return moved


def axes(arm):
    mw = arm.matrix_world
    b = arm.data.bones
    h = lambda n: mw @ b[n].head_local  # noqa: E731
    out = {}
    for s, name in (("_L", "Left"), ("_R", "Right")):
        a0, a1 = h(f"{name}UpperArm"), h(f"{name}Hand")
        out["arm" + s] = (a0, (a1 - a0).normalized(), Vector((0, 0, 1)))  # the cut at -up: underneath
        l0, l1 = h(f"{name}UpperLeg"), h(f"{name}Foot")
        out["leg" + s] = (l0, (l1 - l0).normalized(), Vector((math.copysign(1.0, l0.x), 0, 0)))  # the cut inside
    return out


def angle(c, axis):
    o, d, ref = axis
    r = c - o
    r = r - d * r.dot(d)
    e2 = (ref - d * ref.dot(d)).normalized()
    e1 = d.cross(e2)
    return math.atan2(r.dot(e1), r.dot(e2))


def main():
    a = args()
    out = Path(a.out)
    (out / "build").mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=a.character)
    body = bpy.data.objects["Body"]
    arm = body.find_armature()
    arm.data.pose_position = "REST"
    me = body.data
    vparts = vertex_parts(body)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    labels = face_labels(bm, vparts)
    mid = torso_mid(bm, labels)
    head_c = [f.calc_center_median() for f in bm.faces if labels[f.index] == "head"]
    hc = sum(head_c, Vector()) / len(head_c)
    ax = axes(arm)
    ax["head"] = (Vector((0, hc.y, 0)), Vector((0, 0, 1)), Vector((0, -1, 0)))  # the cut at +y: the back
    for s, name in (("_L", "Left"), ("_R", "Right")):  # the foot's upper: from the ankle to the sole up the heel
        ax["foot" + s] = (arm.matrix_world @ arm.data.bones[f"{name}Foot"].head_local, Vector((0, 0, 1)), Vector((0, -1, 0)))
    theta = [0.0] * len(bm.faces)
    nz = [f.normal.z for f in bm.faces]  # the hands' sides by a smoothed normal (a raw one leaves flaps that fold)
    for _ in range(G.UV["hand_smooth"]):
        nz = [(nz[f.index] + sum(nz[g.index] for e in f.edges for g in e.link_faces if g is not f))
              / (1 + sum(1 for e in f.edges for g in e.link_faces if g is not f)) if labels[f.index].startswith("hand")
              else nz[f.index] for f in bm.faces]
    for f in bm.faces:
        lab = labels[f.index]
        c = f.calc_center_median()
        if lab == "torso":
            labels[f.index] = "torso_front" if c.y < mid(c.z) else "torso_back"
        elif lab.startswith("hand"):
            labels[f.index] = lab + ("_a" if nz[f.index] >= 0 else "_b")
        elif lab.startswith("foot") and f.normal.z < -G.UV["sole_nz"]:
            labels[f.index] = lab + "_sole"
    merged = merge_small(bm, labels)
    for f in bm.faces:
        if labels[f.index] in ax:
            theta[f.index] = angle(f.calc_center_median(), ax[labels[f.index]])
    seams = 0
    for e in bm.edges:
        e.seam = False
        if len(e.link_faces) != 2:
            continue
        f1, f2 = e.link_faces
        l1, l2 = labels[f1.index], labels[f2.index]
        if l1 != l2 or (l1 in ax and G.crosses_branch(theta[f1.index], theta[f2.index])):
            e.seam = True
            seams += 1
    bm.to_mesh(me)
    bm.free()
    me.uv_layers.active = me.uv_layers[UV_LAYER]
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.context.scene.tool_settings.use_uv_select_sync = True
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.unwrap(method=G.UV["method"], fill_holes=True, margin=0.0)
    bpy.ops.object.mode_set(mode="OBJECT")
    # each island to the same density, times its part's
    lab = np.array([sorted(set(labels)).index(x) for x in labels])
    names = sorted(set(labels))
    uv = np.empty(len(me.loops) * 2)
    me.uv_layers[UV_LAYER].data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    ls = np.empty(len(me.polygons), dtype=np.int64)
    me.polygons.foreach_get("loop_start", ls)
    lt = np.empty(len(me.polygons), dtype=np.int64)
    me.polygons.foreach_get("loop_total", lt)
    area3 = np.empty(len(me.polygons))
    me.polygons.foreach_get("area", area3)
    loop_face = np.repeat(np.arange(len(me.polygons)), lt)

    def uv_areas(uv):
        s = np.zeros(len(me.polygons))
        nxt = np.arange(len(me.loops)) + 1
        last = ls + lt - 1
        nxt[last] = ls
        cr = uv[:, 0] * uv[nxt, 1] - uv[nxt, 0] * uv[:, 1]
        np.add.at(s, loop_face, cr)
        return 0.5 * s

    au = np.abs(uv_areas(uv))
    for i, n in enumerate(names):
        fm = lab == i
        k = G.density(n) * math.sqrt(area3[fm].sum() / max(au[fm].sum(), 1e-12))
        lm = fm[loop_face]
        c = uv[lm].mean(0)
        uv[lm] = c + (uv[lm] - c) * k
    me.uv_layers[UV_LAYER].data.foreach_set("uv", uv.ravel())
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(udim_source="CLOSEST_UDIM", rotate=True, scale=True, margin_method="FRACTION",
                            margin=G.UV["margin_px"] / G.UV["size"], shape_method="CONCAVE")
    bpy.ops.mesh.select_all(action="DESELECT")
    overlap = None
    try:
        bpy.ops.uv.select_overlap()
        bpy.ops.object.mode_set(mode="OBJECT")
        sel = [p.index for p in me.polygons if p.select]
        overlap = {"faces": len(sel), "by_part": {}}
        for i in sel:
            overlap["by_part"][labels[i]] = overlap["by_part"].get(labels[i], 0) + 1
    except Exception as ex:  # noqa: BLE001
        print("M2 select_overlap:", ex)
        bpy.ops.object.mode_set(mode="OBJECT")
    for p in me.polygons:
        p.select = False
    uv = np.empty(len(me.loops) * 2)
    me.uv_layers[UV_LAYER].data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    sa = uv_areas(uv)
    au = np.abs(sa)
    size = G.UV["size"]
    parts = {}
    for i, n in enumerate(names):
        fm = lab == i
        dens = math.sqrt(au[fm].sum() * size * size / area3[fm].sum()) / 100.0
        ratio = np.sqrt(au[fm] / np.maximum(area3[fm], 1e-12)) * size / 100.0 / dens
        parts[n] = {"faces": int(fm.sum()), "area_cm2": round(float(area3[fm].sum() * 1e4), 1),
                    "px_per_cm": round(dens, 1), "uv_share": round(float(au[fm].sum()), 4),
                    "stretch_p5_p95": [round(float(np.percentile(ratio, 5)), 2), round(float(np.percentile(ratio, 95)), 2)]}
    flipped = int((sa < 0).sum())
    rep = {"uv_layer": UV_LAYER, "gltf": "TEXCOORD_0", "settings": G.UV, "density": G.DENSITY, "seam_edges": seams, "stray_faces_merged": merged,
           "islands": len(names), "parts": parts, "uv_used": round(float(au.sum()), 4),
           "faces_flipped": flipped, "faces_overlapping": overlap,
           "in_unit_square": bool(uv.min() >= 0 and uv.max() <= 1),
           "uv_layers": [u.name for u in me.uv_layers]}
    me.uv_layers.active = me.uv_layers[UV_LAYER]
    arm.data.pose_position = "POSE"
    layout(me, uv, lab, len(names), out / "uv_layout.png")
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "build" / "alien_character.blend"))
    (out / "build_report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8", newline="\n")
    print("M2 UV " + json.dumps(rep))


def layout(me, uv, lab, n, path, px=1024):
    """The islands filled in a colour per part (face centroids splatted densely) with the edges in dark grey."""
    img = np.full((px, px, 3), 0.08)
    rng = np.random.default_rng(3)
    cols = rng.uniform(0.3, 0.95, (n, 3))
    tris = []
    for p in me.polygons:
        lp = list(p.loop_indices)
        for k in range(1, len(lp) - 1):
            tris.append((lp[0], lp[k], lp[k + 1], lab[p.index]))
    t = np.array(tris)
    w = rng.dirichlet((1, 1, 1), size=(len(t), 12))
    pts = (w[..., 0:1] * uv[t[:, 0]][:, None] + w[..., 1:2] * uv[t[:, 1]][:, None] + w[..., 2:3] * uv[t[:, 2]][:, None])
    ij = np.clip((pts * px).astype(int), 0, px - 1)
    img[ij[..., 1].ravel(), ij[..., 0].ravel()] = np.repeat(cols[t[:, 3]], 12, axis=0)
    s = np.linspace(0, 1, 6)[:, None]
    lp0 = []
    for p in me.polygons:
        lp = list(p.loop_indices)
        lp0 += [(lp[k], lp[(k + 1) % len(lp)]) for k in range(len(lp))]
    lp0 = np.array(lp0)
    seg = uv[lp0[:, 0]][:, None] * (1 - s) + uv[lp0[:, 1]][:, None] * s
    ij = np.clip((seg * px).astype(int), 0, px - 1)
    img[ij[..., 1].ravel(), ij[..., 0].ravel()] *= 0.55
    im = bpy.data.images.new("uv_layout", px, px, alpha=False)
    rgba = np.concatenate([img, np.ones((px, px, 1))], 2).astype(np.float32)
    im.pixels.foreach_set(rgba.ravel())
    im.filepath_raw = str(path)
    im.file_format = "PNG"
    im.save()


if __name__ == "__main__":
    main()
