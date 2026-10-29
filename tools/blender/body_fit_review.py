"""Bodies by drawing, step D3 (art #196): the whole-body gate's sheets of fitted bodies, in headless Blender's
Workbench (alien_body_refit_review's look and numpy helpers).

    blender -b --factory-startup --python tools/blender/body_fit_review.py -- --out DIR --body A0.blend --body A1.blend
        --concept image-0.png --mm-px 1.9386 --sole-row 999 --cuts 0,748,1290,1760,2560 [--mirror 0,1,1,0]
        [--head-from alien_character.blend] [--arm-deg 66] [--tag A]

- four_<tag>.png: one row per body (front, three-quarter, side, back; arms lowered `--arm-deg` from the T, the
  concept's hang), the concept's silhouette edge in yellow over each, and the concept's own panels in the last row,
  all at one scale (ortho, 2 m frame height) with the soles on one line and the trunks centred;
- close_<tag>.png: the last body's close-ups (one flat colour, cavity on): the chest front and 3/4, the crotch from
  the front and 3/4 below, the seat from the side and 3/4 back, the neck ring with the head on (3/4 front, side,
  back), the left hand from the front and from above, the left foot from the side and 3/4 front;
- review_<tag>.json: the cells' order, the head objects linked, the cameras.

`--head-from` (once or twice): a character .blend (alien_assemble's, head and body joined in `Body`): its mesh above
its neck ring (z 1.39 m), one copy per body moved onto that body's ring (the body mesh's top loop; the ring is the
same on every body, the ADR docs/decisions/2026-10-29-neck-ring.md). The first head is on the four-side views; the
close-ups show the neck with each head.
The concept's outline is D2's own figure mask (body_dims_geom.mask, the ground flood from the border) and its panels
(body_dims_geom.panels), the masks the tables were measured on; `--sole-row` defaults to that mask's sole.
`--pair`: instead, one sheet `pair_<tag>.png` of the bodies side by side, front and side, one scale, heads on.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import alien_body_refit_review as R  # noqa: E402

FRAME_H = 2.0  # m, the four views' ortho height
CELL = (320, 560)
CLOSE = (320, 320)
VIEWS = (0, 45, 90, 180)
YELLOW = np.array([1.0, 0.85, 0.1, 1.0], np.float32)
GROUND = np.array([0.35, 0.35, 0.36, 1.0], np.float32)


def link(path: str, keep) -> list:
    with bpy.data.libraries.load(path) as (src, dst):
        dst.objects = [n for n in src.objects if keep(n)]
    objs = [o for o in dst.objects if o is not None]
    for o in objs:
        bpy.context.scene.collection.objects.link(o)
    return objs


def d2_mask(path):
    """D2's figure mask of the concept (body_dims_geom: the tables' own), as a bool array, its sole row and the
    panels' column cuts (midway between the four figures)."""
    import body_dims_geom as DG
    w, h, rows = DG.read_png(path)
    m, sole = DG.mask(rows)
    full = np.array([[(r >> x) & 1 for x in range(w)] for r in m], bool) if isinstance(m[0], int) else \
        np.array([list(r) for r in m], bool)
    ps = DG.panels(m)
    cuts = [0] + [(a[1] + b[0]) // 2 for a, b in zip(ps, ps[1:])] + [w]
    return full, sole, cuts


def concept_mask(im, cut, mirror, full):
    """One panel's figure mask (D2's) and its colours."""
    sub = im[:, cut[0]:cut[1]]
    m = full[:, cut[0]:cut[1]]
    if mirror:
        sub, m = sub[:, ::-1], m[:, ::-1]
    return m, sub


def resample(m, sub, mm_px, sole_row, body_cx_px):
    """The concept panel on the cell's grid: rows by height (the sole on the cell's ground line), columns centred on
    the trunk rows' centroid (z 0.9 to 1.2 m) matched to the body's (body_cx_px)."""
    W, H = CELL
    mpp = FRAME_H / H
    zs = FRAME_H / 2 + (H / 2 - np.arange(H) - 0.5) * mpp + (0.97 - FRAME_H / 2)
    rows = np.round(sole_row - zs * 1000 / mm_px).astype(int)
    tr = [r for r in range(int(sole_row - 1200 / mm_px), int(sole_row - 900 / mm_px)) if m[r].any()]
    cc = np.mean([np.mean(np.nonzero(m[r])[0]) for r in tr])
    cols = np.round(cc + (np.arange(W) - body_cx_px) * mpp * 1000 / mm_px).astype(int)
    ok_c = (cols >= 0) & (cols < m.shape[1])
    om = np.zeros((H, W), bool)
    oc = np.tile(GROUND, (H, W, 1))
    for i in range(H):
        if 0 <= rows[i] < m.shape[0]:
            om[i, ok_c] = m[rows[i], cols[ok_c]]
            oc[i, ok_c, :3] = sub[rows[i], cols[ok_c], :3]
    return om, oc


def edge(m):
    e = np.zeros_like(m)
    e[1:-1, 1:-1] = m[1:-1, 1:-1] & ~(m[:-2, 1:-1] & m[2:, 1:-1] & m[1:-1, :-2] & m[1:-1, 2:])
    return e


def composite(im):
    a = im[..., 3:4]
    out = im.copy()
    out[..., :3] = im[..., :3] * a + GROUND[:3] * (1 - a)
    out[..., 3] = 1.0
    return out


def body_cx(alpha):
    H = alpha.shape[0]
    mpp = FRAME_H / H
    zs = 0.97 + (H / 2 - np.arange(H) - 0.5) * mpp
    rows = [i for i in range(H) if 0.9 < zs[i] < 1.2 and (alpha[i] > 0.5).any()]
    return float(np.mean([np.mean(np.nonzero(alpha[i] > 0.5)[0]) for i in rows]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--body", action="append", required=True)
    ap.add_argument("--concept", required=True)
    ap.add_argument("--mm-px", type=float, required=True)
    ap.add_argument("--sole-row", type=int, default=-1)
    ap.add_argument("--cuts", default="")
    ap.add_argument("--pair", action="store_true")
    ap.add_argument("--mirror", default="0,1,1,0")
    ap.add_argument("--head-from", action="append", default=[])
    ap.add_argument("--arm-deg", type=float, default=66.0)
    ap.add_argument("--tag", default="A")
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    os.makedirs(a.out, exist_ok=True)
    tmp = os.path.join(a.out, f"_cells_{a.tag}")
    os.makedirs(tmp, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    groups, log = [], {"bodies": a.body, "views": VIEWS, "arm_deg": a.arm_deg, "head": [], "close": []}
    rings = []
    mat = bpy.data.materials.new("Skin")
    mat.diffuse_color = (*R.BODY_RGB, 1.0)
    for path in a.body:
        objs = link(path, lambda n: n in ("Body", "CharacterArmature"))
        arm = next(o for o in objs if o.type == "ARMATURE")
        arm.data.pose_position = "POSE"
        if arm.animation_data:
            arm.animation_data.action = None
        bpy.context.view_layer.update()
        R.rest(arm)
        R.a_pose(arm, math.radians(a.arm_deg))
        body = next(o for o in objs if o.type == "MESH")
        body.data.materials.clear()
        body.data.materials.append(mat)
        groups.append([body])
        rings.append(max((body.matrix_world @ v.co).z for v in body.data.vertices))  # the top loop: the ring
    heads = []  # per head source, one copy per body
    import bmesh
    for hf in a.head_from:  # the character's Body (head and body joined) cut at its ring (its eyes lose their
        # sockets' frames when linked alone, so they are left out)
      for j in range(len(groups)):
        objs = link(hf, lambda n: n == "Body")
        saved = {o.name: o.matrix_world.copy() for o in objs}
        head = []
        for o in objs:
            if o.type != "MESH":
                continue
            for md in [md for md in o.modifiers if md.type == "ARMATURE"]:
                o.modifiers.remove(md)
            o.parent = None
            o.matrix_world = saved[o.name]
            if o.name.startswith("Body"):
                bm = bmesh.new()
                bm.from_mesh(o.data)
                mw = saved[o.name]
                bmesh.ops.delete(bm, geom=[v for v in bm.verts if (mw @ v.co).z < 1.3895], context="VERTS")
                bm.to_mesh(o.data)
                bm.free()
                o.data.materials.clear()
                o.data.materials.append(mat)
            o.location.z += rings[j] - 1.39
            head.append(o)
        heads.append((hf, j, head))
        log["head"].append({"from": hf, "body": j, "ring_m": round(rings[j], 5), "objects": [o.name for o in head]})

    def show(j, h=0):  # body j with head source h (or none)
        for i, g in enumerate(groups):
            for o in g:
                o.hide_render = i != j
        for k, (hf, jj, hd) in enumerate(heads):
            for o in hd:
                o.hide_render = not (jj == j and k // max(1, len(groups)) == h)
    bpy.context.view_layer.update()
    sc, cam = R.setup(CELL)
    sc.render.film_transparent = True
    cim = R.load(a.concept)
    full, sole, cuts = d2_mask(a.concept)
    if a.cuts:
        cuts = [int(c) for c in a.cuts.split(",")]
    sole_row = a.sole_row if a.sole_row >= 0 else sole
    log["concept"] = {"sole_row": sole_row, "cuts": cuts, "mask": "body_dims_geom.mask"}
    if a.pair:  # the bodies side by side, front and side, one scale
        cells = []
        for ang in (0, 90):
            t = math.radians(ang)
            c = Vector((0, 0, 0.97))
            R.look(cam, c + Vector((-8 * math.sin(t), -8 * math.cos(t), 0)), c, ortho=FRAME_H)
            for j in range(len(groups)):
                show(j)
                p = os.path.join(tmp, f"pair_{ang}_{j}.png")
                R.shot(sc, p, CELL)
                R.save(composite(R.load(p)), p)
                cells.append(p)
        R.stitch(cells, 2 * len(groups), os.path.join(a.out, f"pair_{a.tag}.png"))
        for q in os.listdir(tmp):
            os.remove(os.path.join(tmp, q))
        os.rmdir(tmp)
        with open(os.path.join(a.out, f"review_pair_{a.tag}.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(log, f, indent=1)
        print("REVIEW pair", a.tag, len(groups), "bodies", flush=True)
        return 0
    mirror = [c == "1" for c in a.mirror.split(",")]
    cells = []
    concept_row = []
    for k, ang in enumerate(VIEWS):
        t = math.radians(ang)
        c = Vector((0, 0, 0.97))
        R.look(cam, c + Vector((-8 * math.sin(t), -8 * math.cos(t), 0)), c, ortho=FRAME_H)
        m, sub = concept_mask(cim, cuts[k:k + 2], mirror[k], full)
        for j, objs in enumerate(groups):
            show(j)
            p = os.path.join(tmp, f"four_{k}_{j}.png")
            R.shot(sc, p, CELL)
            im = R.load(p)
            om, oc = resample(m, sub, a.mm_px, sole_row, body_cx(im[..., 3]))
            im = composite(im)
            im[edge(om)] = YELLOW
            R.save(im, p)
            cells.append((k, j, p))
            if j == len(groups) - 1:
                q = os.path.join(tmp, f"four_{k}_c.png")
                R.save(oc, q)
                concept_row.append(q)
    order = [p for j in range(len(groups)) for k in range(len(VIEWS)) for (kk, jj, p) in cells if kk == k and jj == j]
    R.stitch(order + concept_row, len(VIEWS), os.path.join(a.out, f"four_{a.tag}.png"))

    # close-ups of the last body (with the head), one flat colour, cavity on
    last = len(groups) - 1
    show(last)
    rz = rings[last]
    sc.render.film_transparent = False
    sh = sc.display.shading
    sh.color_type, sh.show_cavity, sh.cavity_type = "MATERIAL", True, "WORLD"
    shots = [("chest_front", (0, 1.12), 0, 0, 0.85, 50), ("chest_34", (0.03, 1.12), 35, 0, 0.85, 50),
             ("crotch_front", (0, 0.74), 0, -12, 0.85, 50), ("crotch_34_low", (0.03, 0.74), 30, -20, 0.85, 50),
             ("seat_side", (0, 0.82), 90, 0, 0.95, 50), ("seat_34_back", (0.03, 0.82), 145, 0, 0.95, 50),
             ("chest_side", (0, 1.12), 90, 0, 0.85, 50)]
    for h in range(len(a.head_from)):
        shots += [(f"neck{h}_34_front", (0, rz), 35, 0, 0.6, 50, h), (f"neck{h}_side", (0, rz), 90, 0, 0.6, 50, h),
                  (f"neck{h}_34_back", (0, rz), 145, 0, 0.6, 50, h)]
    zk = rz / 1.39  # B's close-ups at her heights
    shots = [(n, (x, z * zk if not n.startswith("neck") else z), *rest) for n, (x, z), *rest in shots]
    arm = bpy.data.objects[[o.name for o in bpy.data.objects if o.type == "ARMATURE"][-1]]

    def bone(n):
        return arm.matrix_world @ arm.pose.bones[n].head

    hand = (bone("LeftHand") + bone("LeftMiddleProximal")) / 2
    foot = (bone("LeftFoot") + bone("LeftToes")) / 2
    paths = []
    for name, (x, z), az, el, dist, lens, *hh in shots:
        show(last, hh[0] if hh else 0)
        tgt = Vector((x, 0.02, z))
        t, e = math.radians(az), math.radians(el)
        loc = tgt + dist * Vector((-math.sin(t) * math.cos(e), -math.cos(t) * math.cos(e), math.sin(e)))
        R.look(cam, loc, tgt, lens=lens)
        p = os.path.join(tmp, f"close_{name}.png")
        R.shot(sc, p, CLOSE)
        paths.append(p)
        log["close"].append({"name": name, "target": list(tgt), "loc": list(loc), "lens": lens})
    for name, tgt, off in (("hand_front", hand, Vector((0.0, -0.45, 0.0))), ("hand_above", hand, Vector((0.05, -0.1, 0.45))),
                           ("foot_side", foot, Vector((0.55, 0.0, 0.05))), ("foot_34_front", foot, Vector((0.3, -0.45, 0.2))),
                           ("foot_front", foot, Vector((0.0, -0.3, 0.06))), ("foot_top", foot, Vector((0.0, -0.04, 0.3))),
                           ("foot_below", foot, Vector((0.05, -0.12, -0.27)))):
        R.look(cam, tgt + off, tgt, lens=50)
        p = os.path.join(tmp, f"close_{name}.png")
        R.shot(sc, p, CLOSE)
        paths.append(p)
        log["close"].append({"name": name, "target": list(tgt), "loc": list(tgt + off), "lens": 50})
    R.stitch(paths, 4, os.path.join(a.out, f"close_{a.tag}.png"))
    with open(os.path.join(a.out, f"review_{a.tag}.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(log, f, indent=1)
    for q in os.listdir(tmp):
        os.remove(os.path.join(tmp, q))
    os.rmdir(tmp)
    print("REVIEW", a.tag, len(groups), "bodies, head", log["head"], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
