"""Measures a cleaned outfit (clothes_clean.py's cloth.blend) against our base body (art #196, clothes step 2): the
body's lines from its armature (neck, shoulders, hips, wrists, ankles) and its mesh widths at those heights, the
cloth's widths at the same heights, and the cloth's openings (each boundary loop's centre and size: the collar, the
cuffs, the trouser hems, the shoes' tops), so the fit step knows how far it has to move the cloth. Renders a front
and a side overlay (the body grey, the cloth in its colours, see-through) as one sheet. Nothing is fitted here.

    blender -b --factory-startup --python tools/blender/clothes_measure.py -- CLOTH.blend BODY.blend OUT_DIR

Writes OUT_DIR/fit.json and OUT_DIR/overlay.png; prints CLOTHES_MEASURE lines.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clothes_geom as cg  # noqa: E402

BONES = {"neck": "neck", "shoulder": "upperarm", "wrist": "hand", "hip": "upperleg", "ankle": "foot"}


def world_co(o) -> np.ndarray:
    me = o.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    co = np.array([(o.matrix_world @ v.co)[:] for v in me.vertices])
    return co


def width(co: np.ndarray, z: float, half: float = 0.01, xmax: float = 9.0) -> float:
    sel = co[(np.abs(co[:, 2] - z) <= half) & (np.abs(co[:, 0]) <= xmax)]
    w = cg.centre_run(sel[:, 0].tolist(), gap=0.02) if len(sel) else None
    return round(w[1] - w[0], 4) if w else 0.0


def loops(o) -> list[dict]:
    bm = bmesh.new()
    bm.from_mesh(o.data)
    edges = [e for e in bm.edges if e.is_boundary]
    seen, out = set(), []
    for e in edges:
        if e.index in seen:
            continue
        group, stack = [], [e]
        seen.add(e.index)
        while stack:
            g = stack.pop()
            group.append(g)
            for v in g.verts:
                for n in v.link_edges:
                    if n.is_boundary and n.index not in seen:
                        seen.add(n.index)
                        stack.append(n)
        pts = np.array([(o.matrix_world @ v.co)[:] for g in group for v in g.verts])
        if len(group) < 12:
            continue
        c = pts.mean(axis=0)
        out.append({"piece": o.name, "edges": len(group), "centre": c.round(4).tolist(),
                    "size": (pts.max(axis=0) - pts.min(axis=0)).round(4).tolist()})
    bm.free()
    return sorted(out, key=lambda d: -d["centre"][2])


def main() -> None:
    cloth_path, body_path, out = (Path(a) for a in sys.argv[sys.argv.index("--") + 1:][:3])
    bpy.ops.wm.open_mainfile(filepath=str(cloth_path))
    cloth = [o for o in bpy.data.objects if o.type == "MESH"]
    with bpy.data.libraries.load(str(body_path)) as (src, dst):
        dst.objects = [n for n in src.objects if n in ("Body", "CharacterArmature")]
    for o in dst.objects:
        bpy.context.scene.collection.objects.link(o)
    body = next(o for o in dst.objects if o.type == "MESH")
    arm = next(o for o in dst.objects if o.type == "ARMATURE")
    bones = {}
    for key, part in BONES.items():
        hits = [b for b in arm.data.bones if part in b.name.lower().replace("_", "").replace(".", "")
                and not any(t in b.name.lower() for t in ("twist", "end", "thumb", "index", "middle", "ring",
                                                              "pinky", "finger"))]
        hits.sort(key=lambda b: abs((arm.matrix_world @ b.head_local).x))
        if hits:
            p = arm.matrix_world @ hits[-1].head_local
            bones[key] = {"bone": hits[-1].name, "head": [round(abs(p.x), 4), round(p.y, 4), round(p.z, 4)]}
    print("CLOTHES_MEASURE bones", json.dumps(bones), flush=True)
    bco = world_co(body)
    cco = {o.name: world_co(o) for o in cloth}
    allc = np.concatenate(list(cco.values()))
    garment = np.concatenate([v for k, v in cco.items() if k != "shoes"])
    shoulder_x = bones["shoulder"]["head"][0] if "shoulder" in bones else 0.25
    body_lines = {"height": float(bco[:, 2].max()), "neck": bones.get("neck", {}).get("head", [0, 0, 0])[2],
                  "shoulder_z": bones["shoulder"]["head"][2], "hip_z": bones["hip"]["head"][2],
                  "ankle_z": bones["ankle"]["head"][2],
                  "shoulder_width": 2 * shoulder_x,
                  "hip_width": width(bco, bones["hip"]["head"][2], xmax=0.4),
                  "chest_width": width(bco, bones["shoulder"]["head"][2] - 0.12, xmax=shoulder_x + 0.02),
                  "depth_chest": float(np.ptp(bco[np.abs(bco[:, 2] - (bones["shoulder"]["head"][2] - 0.12)) < 0.01][:, 1]))}
    cloth_lines = {"height": float(garment[:, 2].max()), "neck": float(garment[:, 2].max()),
                   "hip_width": width(garment, bones["hip"]["head"][2], xmax=0.4),
                   "chest_width": width(garment, bones["shoulder"]["head"][2] - 0.12, xmax=shoulder_x + 0.02),
                   "depth_chest": float(np.ptp(garment[np.abs(garment[:, 2] - (bones["shoulder"]["head"][2] - 0.12)) < 0.01][:, 1])),
                   "shoulder_width": width(garment, bones["shoulder"]["head"][2] - 0.03, xmax=0.6),
                   "ankle_z": float(garment[:, 2].min())}
    if "shoes" in cco:
        s = cco["shoes"]
        cloth_lines.update({"shoe_top": float(s[:, 2].max()), "shoe_length": float(np.ptp(s[:, 1])),
                            "shoe_span": float(np.ptp(s[:, 0]))})
    fit = {"cloth": str(cloth_path), "body": str(body_path), "bones": bones,
           "lines": cg.fit_lines(cloth_lines, body_lines),
           "cloth_only": {k: round(v, 4) for k, v in cloth_lines.items() if k not in body_lines},
           "cloth_box": [allc.min(axis=0).round(4).tolist(), allc.max(axis=0).round(4).tolist()],
           "body_box": [bco.min(axis=0).round(4).tolist(), bco.max(axis=0).round(4).tolist()],
           "openings": [d for o in cloth for d in loops(o)]}
    out.mkdir(parents=True, exist_ok=True)
    (out / "fit.json").write_text(json.dumps(fit, indent=1), encoding="utf-8")
    for k, v in fit["lines"].items():
        print("CLOTHES_MEASURE", k, v, flush=True)
    # the overlay: Workbench, orthographic, see-through
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "TEXTURE"
    sc.display.shading.show_xray = True
    sc.display.shading.xray_alpha = 0.6
    sc.render.resolution_x, sc.render.resolution_y = 640, 960
    sc.render.film_transparent = False
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 2.0
    sc.camera = cam
    shots = []
    for name, loc, rot in (("front", (0, -5, 0.95), (1.5708, 0, 0)), ("side", (5, 0, 0.95), (1.5708, 0, 1.5708))):
        cam.location, cam.rotation_euler = loc, rot
        path = out / f"overlay_{name}.png"
        sc.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(str(path))
        shots.append(np.array(img.pixels[:], dtype=np.float32).reshape(960, 640, 4))
    sheet = bpy.data.images.new("overlay", 1280, 960)
    sheet.pixels[:] = np.concatenate(shots, axis=1).ravel()
    sheet.filepath_raw = str(out / "overlay.png")
    sheet.file_format = "PNG"
    sheet.save()
    print("CLOTHES_MEASURE wrote", out, flush=True)


main()
