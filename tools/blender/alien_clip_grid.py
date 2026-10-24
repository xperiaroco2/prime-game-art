"""A variant grid over one alien clip's edit (art #196, A3: the crouch rebuilt): opens a built character's .blend
(alien_char_run.py's <head>_char.blend, its clips already edited by anim_sets/alien.toml), and for every combination
of the extra settings applies alien_clip_edit's edits once more on a copy of the clip, measures it and renders it
(Workbench, a side and a three-quarter view of the clip's middle frame), then puts the original back.

    $PYTHON_BIN tools/blender/alien_clip_grid.py --blend <head>_char.blend --clip Crouch_Idle_Loop --out <dir>
        [--hips 0,6,12] [--chest 0,10,20] [--knees 0,8] [--head 0]

The values are added on top of the build's own edit (hips_up_cm, chest_up_deg, knees_in_deg, head_up_deg), each
variant with floor = true, floor_reach = 0. Writes <out>/grid.json (per variant: the settings, the face's height
over the front knee, the trunk's angle from vertical, the lowest and highest-lowest skinned vertex, the hands'
nearest distance to the legs, the feet's drift) and <out>/grid.jpg (variants in rows of six, each a side | 3/4 pair,
in grid.json's order). Long (Blender): run it in the background.
"""
from __future__ import annotations

import itertools
import json
import math
import sys
from pathlib import Path

CELL = (200, 260)


def _blender_main(argv: list[str]) -> None:
    import argparse
    import tempfile

    import bpy
    import numpy as np
    from mathutils import Vector

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import alien_clip_edit as E

    ap = argparse.ArgumentParser()
    for k, d in (("--blend", None), ("--clip", "Crouch_Idle_Loop"), ("--out", None), ("--hips", "0,6,12"),
                 ("--chest", "0,10,20"), ("--knees", "0,8"), ("--head", "0")):
        ap.add_argument(k, default=d, required=d is None)
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=a.blend)
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    skins = [o for o in bpy.data.objects if o.type == "MESH" and o.find_armature() == arm]
    skin = max(skins, key=lambda o: len(o.data.vertices))
    name = f"CharacterArmature|{a.clip}"
    orig = bpy.data.actions[name]
    orig.name = name + "__orig"
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "SINGLE"
    sc.render.resolution_x, sc.render.resolution_y = CELL
    sc.render.film_transparent = False
    cam_data = bpy.data.cameras.new("grid_cam")
    cam = bpy.data.objects.new("grid_cam", cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 2.0
    floats = [float(x) for x in a.hips.split(",")], [float(x) for x in a.chest.split(",")], \
        [float(x) for x in a.knees.split(",")], [float(x) for x in a.head.split(",")]
    variants, cells = [], []
    pb = arm.pose.bones
    for dh, dc, dk, dhd in itertools.product(*floats):
        act = orig.copy()
        act.name = name
        cfg = {"floor": True, "floor_reach": 0}
        if dh or dk:
            cfg.update(hips_up_cm=dh or 0.001, knees_in_deg=dk)
        if dc:
            cfg["chest_up_deg"] = dc
        if dhd:
            cfg["head_up_deg"] = dhd
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False, encoding="utf-8") as f:
            f.write(f"[clips.{a.clip}]\n" + "".join(
                f"{k} = {str(v).lower() if isinstance(v, bool) else v}\n" for k, v in cfg.items()))
        rep = E.apply(arm, skin, f.name)[a.clip]
        f0, f1 = E._assign(arm, act)
        m = {"extra": {"hips_cm": dh, "chest_deg": dc, "knees_deg": dk, "head_deg": dhd}, "edit": {
            k: v for k, v in rep.items() if k in ("hips_up", "floor")}}
        face, trunk, hands, feet = [], [], [], {"LeftFoot": [], "RightFoot": []}
        for fr in range(f0, f1 + 1, 2):
            sc.frame_set(fr)
            mw = arm.matrix_world
            P = {b: mw @ pb[b].head for b in ("Hips", "Neck", "Head", "LeftLowerLeg", "RightLowerLeg", "LeftFoot",
                                               "RightFoot", "LeftUpperLeg", "RightUpperLeg", "LeftHand", "RightHand")}
            face.append(P["Head"].z - max(P["LeftLowerLeg"].z, P["RightLowerLeg"].z))
            t = P["Neck"] - P["Hips"]
            trunk.append(math.degrees(math.acos(max(-1.0, min(1.0, t.z / t.length)))))

            def seg_d(p, s0, s1):
                d = s1 - s0
                u = max(0.0, min(1.0, (p - s0).dot(d) / max(1e-9, d.length_squared)))
                return (p - (s0 + d * u)).length
            hands.append(min(seg_d(P[h], P[s + "UpperLeg"], P[s + "LowerLeg"]) for h in ("LeftHand", "RightHand")
                             for s in ("Left", "Right")))
            hands[-1] = min(hands[-1], min(seg_d(P[h], P[s + "LowerLeg"], P[s + "Foot"])
                                           for h in ("LeftHand", "RightHand") for s in ("Left", "Right")))
            for b in feet:
                feet[b].append(P[b])
        m["face_over_knee_cm"] = round(min(face) * 100, 1)
        m["trunk_from_vertical_deg"] = [round(min(trunk), 1), round(max(trunk), 1)]
        m["hands_to_legs_min_cm"] = round(min(hands) * 100, 1)
        m["feet_drift_cm"] = round(max(max((p - v[0]).length for p in v) for v in feet.values()) * 100, 1)
        m["lowest_cm"] = rep.get("floor", {}).get("lowest_after_cm")
        m["float_cm"] = rep.get("floor", {}).get("highest_low_after_cm")
        sc.frame_set((f0 + f1) // 2)
        centre = arm.matrix_world @ pb["Hips"].head
        imgs = []
        for yaw in (90.0, 35.0):  # the left side, the three-quarter front (the character faces -Y)
            r = math.radians(yaw)
            cam.location = Vector((centre.x + 4 * math.sin(r), centre.y - 4 * math.cos(r), 0.75))
            cam.rotation_euler = (math.radians(90), 0.0, r)
            sc.render.filepath = str(out / f"_cell_{len(variants)}_{int(yaw)}.png")
            bpy.ops.render.render(write_still=True)
            im = bpy.data.images.load(sc.render.filepath)
            px = np.array(im.pixels[:]).reshape(CELL[1], CELL[0], 4)
            imgs.append(px)
            bpy.data.images.remove(im)
            Path(sc.render.filepath).unlink()
        cells.append(np.concatenate(imgs, axis=1))
        variants.append(m)
        print("GRID " + json.dumps(m), flush=True)
        arm.animation_data.action = None
        bpy.data.actions.remove(act)
    orig.name = name
    cols = 6
    rows = (len(cells) + cols - 1) // cols
    h, w = cells[0].shape[:2]
    sheet = np.ones((rows * h, cols * w, 4))
    for i, c in enumerate(cells):
        r, col = divmod(i, cols)
        sheet[(rows - 1 - r) * h:(rows - r) * h, col * w:(col + 1) * w] = c  # Blender's pixels run bottom-up
        sheet[(rows - 1 - r) * h:(rows - r) * h, col * w:col * w + 2] = (0.2, 0.2, 0.2, 1.0)
    img = bpy.data.images.new("grid", cols * w, rows * h)
    img.pixels = sheet.ravel()
    img.filepath_raw = str(out / "grid.png")
    img.file_format = "PNG"
    img.save()
    (out / "grid.json").write_text(json.dumps({"blend": a.blend, "clip": a.clip, "order": "rows of six, each a side "
                                               "| 3/4 pair", "variants": variants}, indent=1), encoding="utf-8")
    print("GRID done", flush=True)


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "tools"))
    from runner import blender
    res = blender.run_script(Path(__file__).resolve(), sys.argv[1:], timeout=3600)
    print(*[x for x in (res.stdout or "").splitlines() if x.startswith("GRID")], sep="\n", flush=True)
    return 0


if __name__ == "__main__":
    if "--" in sys.argv:  # inside Blender
        _blender_main(sys.argv[sys.argv.index("--") + 1:])
    else:
        sys.exit(main())
