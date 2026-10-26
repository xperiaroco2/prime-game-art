"""The alien locomotion's clip tool in Blender (art #196, option A step 1): reads a built alien character's clips
(CharacterArmature|<clip> actions on the contract skeleton) into alien_stride_math's plain form, runs its edits
(measure, stride, cycle, arm_swing, mirror) and writes the result back as a new action, keyed on every frame (linear).

    $PYTHON_BIN tools/blender/alien_stride.py --blend <char.blend> [<char.blend> ...] --out <dir>
        [--measure] [--proof] [--check]

- `--measure`: the locomotion clips' own numbers per character (measure.json: v0, c0, stride, slide, seam) and the
  game's speeds against them (alien_stride_math.game_table);
- `--proof` (the first blend): Jog_Fwd_Loop retimed to the footstep beat (2.22 steps/s) at 4.5 m/s, arm swing 0.75,
  as the action CharacterArmature|Jog_Fwd_Loop_s1; proof.json and proof_sheet.png (the original's row above the
  edit's, 8 frames each, side view);
- `--check` (the first blend): the pure FK against Blender's own pose on every frame of the jog, and the written
  action read back against the edit (check.json; tools/tests/test_alien_stride_blender.py).
Without bpy the file starts Blender on itself (runner.blender, background); inside Blender it does the work.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import alien_stride_math as S  # noqa: E402

LOCO = ("Idle_Loop", "Walk_Loop", "Jog_Fwd_Loop", "Sprint_Fwd_Loop", "Crouch_Fwd_Loop")
PREFIX = "CharacterArmature|"
PROOF = {"clip": "Jog_Fwd_Loop", "cadence": 2.22, "speed": 4.5, "arm_swing": 0.75}
CELL = (160, 220)  # one sheet cell (px): 8 columns make a 1280 px sheet


def _armature():
    import bpy
    return next(o for o in bpy.data.objects if o.type == "ARMATURE")


def skeleton(arm) -> dict:
    return {"rest": {b.name: [list(r) for r in b.matrix_local] for b in arm.data.bones},
            "parent": {b.name: b.parent.name if b.parent else None for b in arm.data.bones}}


def _assign(arm, act):
    ad = arm.animation_data or arm.animation_data_create()
    ad.action = act
    if act.slots:
        ad.action_slot = act.slots[0]
    return int(round(act.frame_range[0])), int(round(act.frame_range[1]))


def sample(arm, act) -> dict:
    """The action's pose basis on every frame of its range (the evaluated values, so the clip's own interpolation)."""
    import bpy
    f0, f1 = _assign(arm, act)
    clip = {"name": act.name.split("|", 1)[-1], "fps": bpy.context.scene.render.fps, "loc": {}, "rot": {}}
    for f in range(f0, f1 + 1):
        bpy.context.scene.frame_set(f)
        for pb in arm.pose.bones:
            clip["loc"].setdefault(pb.name, []).append(tuple(pb.location))
            clip["rot"].setdefault(pb.name, []).append(tuple(pb.rotation_quaternion))
    return clip


def write(arm, clip: dict, name: str):
    """The clip as a new action PREFIX + name, keyed on every frame from 0, linear."""
    import bpy
    old = bpy.data.actions.get(PREFIX + name)
    if old is not None:
        bpy.data.actions.remove(old)
    act = bpy.data.actions.new(PREFIX + name)
    ad = arm.animation_data or arm.animation_data_create()
    ad.action = act
    for f in range(S.frames(clip) + 1):
        for pb in arm.pose.bones:
            if pb.name in clip["loc"]:
                pb.location = clip["loc"][pb.name][f]
                pb.keyframe_insert("location", frame=f)
            if pb.name in clip["rot"]:
                pb.rotation_quaternion = clip["rot"][pb.name][f]
                pb.keyframe_insert("rotation_quaternion", frame=f)
    for layer in act.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for fc in bag.fcurves:
                    for kp in fc.keyframe_points:
                        kp.interpolation = "LINEAR"
    act.use_fake_user = True
    return act


def _blender_fk_mm(arm, act, skel, clip, bones) -> float:
    """The largest distance (mm) between Blender's evaluated bone heads and the pure FK's on every frame."""
    import bpy
    f0, _ = _assign(arm, act)
    worst = 0.0
    for f in range(S.frames(clip) + 1):
        bpy.context.scene.frame_set(f0 + f)
        poses = S.fk(skel, clip, f)
        for b in bones:
            h = arm.matrix_world @ arm.pose.bones[b].head
            worst = max(worst, math.dist(tuple(h), S.pos(poses[b])) * 1000.0)
    return worst


def sheet(arm, acts, path: Path, cols: int = 8, views=None, follow: bool = False) -> None:
    """One row per action: cols frames over its loop, on a grey floor, each row seen from views[row]: "side" (from
    the character's left, the default) or "front"; with follow the camera and the floor keep the Hips over the frame's
    middle (a clip that travels, such as a text-to-motion bake). The camera and floor are made once per file."""
    import bpy
    import numpy as np
    from mathutils import Vector
    sc = bpy.context.scene
    mesh = [o for o in bpy.data.objects if o.type == "MESH" and o.parent == arm]
    zs = [(o.matrix_world @ Vector(c)).z for o in mesh for c in o.bound_box]
    height = max(zs)
    floor = bpy.data.objects.get("stride_floor")
    if floor is None:
        bpy.ops.mesh.primitive_plane_add(size=6.0, location=(0.0, 0.0, 0.0))
        floor = bpy.context.active_object
        floor.name = "stride_floor"
    floor.color = (0.55, 0.55, 0.55, 1.0)
    for o in mesh:
        o.color = (0.85, 0.62, 0.45, 1.0)
    cam = bpy.data.objects.get("stride_cam")
    if cam is None:
        cam_data = bpy.data.cameras.new("stride_cam")
        cam_data.type = "ORTHO"
        cam = bpy.data.objects.new("stride_cam", cam_data)
        sc.collection.objects.link(cam)
    cam.data.ortho_scale = height * 1.25
    tilt = math.radians(8.0)  # a little from above, so the floor reads as a band under the feet
    sc.camera = cam
    views = views or ["side"] * len(acts)

    def aim(view, x=0.0, y=0.0):
        z = height * 0.45 + 6.0 * math.tan(tilt)
        if view == "front":  # from the character's front (-Y), looking at +Y
            cam.location, cam.rotation_euler = (x, y - 6.0, z), (math.pi / 2 - tilt, 0.0, 0.0)
        else:  # from its left (+X), looking at -X
            cam.location, cam.rotation_euler = (x + 6.0, y, z), (math.pi / 2 - tilt, 0.0, math.pi / 2)
        floor.location = (x, y, 0.0)
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "OBJECT"
    sc.display.shading.show_shadows = True
    sc.render.resolution_x, sc.render.resolution_y = CELL
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    w, h = CELL
    canvas = np.ones((h * len(acts) + 4 * (len(acts) - 1), w * cols, 4), dtype=np.float32)
    tmp = path.parent / "_cell.png"
    for row, act in enumerate(acts):
        f0, f1 = _assign(arm, act)
        for c in range(cols):
            sc.frame_set(f0 + round(c * (f1 - f0) / cols))
            hips = arm.matrix_world @ arm.pose.bones["Hips"].head if follow else Vector()
            aim(views[row], hips.x, hips.y)
            sc.render.filepath = str(tmp)
            bpy.ops.render.render(write_still=True)
            img = bpy.data.images.load(str(tmp), check_existing=False)
            px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
            bpy.data.images.remove(img)
            y0 = canvas.shape[0] - (row + 1) * h - row * 4  # Blender's pixels run bottom-up: row 0 on top
            canvas[y0:y0 + h, c * w:(c + 1) * w] = px
    tmp.unlink(missing_ok=True)
    out = bpy.data.images.new("stride_sheet", canvas.shape[1], canvas.shape[0], alpha=True)
    out.pixels.foreach_set(canvas.ravel())
    out.filepath_raw = str(path)
    out.file_format = "PNG"
    out.save()


def _blender_main(argv: list[str]) -> None:
    import bpy
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--measure", action="store_true")
    ap.add_argument("--proof", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    measures = {}
    for k, blend in enumerate(args.blend):
        bpy.ops.wm.open_mainfile(filepath=blend)
        arm = _armature()
        skel = S.prepare(skeleton(arm))
        char = Path(blend).stem
        if args.measure:
            ms = {c: S.measure(skel, sample(arm, bpy.data.actions[PREFIX + c])) for c in LOCO}
            measures[char] = {"clips": ms, "game": S.game_table(ms)}
            for c, m in ms.items():
                print(f"MEASURE {char} {c} v0 {m['v0']} c0 {m['c0']} stride {m['stride_m']} slide {m['slide_mm']} "
                      f"seam {m['seam_deg']}", flush=True)
            for r in measures[char]["game"]:
                print(f"GAME {char} {r}", flush=True)
        if k or not (args.proof or args.check):
            continue
        src = bpy.data.actions[PREFIX + PROOF["clip"]]
        jog = sample(arm, src)
        edit, cyc = S.cycle(skel, jog, foot="Left")
        edit, rep = S.stride(skel, edit, cadence=PROOF["cadence"], speed=PROOF["speed"])
        edit, swing = S.arm_swing(edit, PROOF["arm_swing"])
        after = S.measure(skel, edit)
        act = write(arm, edit, PROOF["clip"] + "_s1")
        proof = {"char": char, "settings": PROOF, "stride": rep, "arm_swing": swing, "cycle": cyc, "after": after,
                 "rate_at_speed": round(PROOF["speed"] / after["v0"], 4)}
        if args.check:
            names = ["Hips"] + [f"{s}{p}" for s in S.SIDES for p in ("UpperLeg", "LowerLeg", "Foot", "Toes", "Hand")]
            back = sample(arm, act)
            check = {"fk_vs_blender_mm": round(_blender_fk_mm(arm, src, skel, jog, names), 4),
                     "edit_fk_vs_blender_mm": round(_blender_fk_mm(arm, act, skel, edit, names), 4),
                     "readback_deg": round(max(S.M.q_angle(S.M.q_norm(a), S.M.q_norm(b)) for k2 in edit["rot"]
                                               for a, b in zip(edit["rot"][k2], back["rot"][k2])), 5),
                     "readback_mm": round(max(math.dist(a, b) for k2 in edit["loc"]
                                              for a, b in zip(edit["loc"][k2], back["loc"][k2])) * 1000.0, 5),
                     "frames": [S.frames(jog), S.frames(edit)], "proof": proof}
            (out / "check.json").write_text(json.dumps(check, indent=1), encoding="utf-8", newline="\n")
            print("CHECK", {k2: v for k2, v in check.items() if k2 != "proof"}, flush=True)
        if args.proof:
            sheet(arm, [src, act], out / "proof_sheet.png")
            (out / "proof.json").write_text(json.dumps(proof, indent=1), encoding="utf-8", newline="\n")
            print("PROOF", json.dumps({"v0": [rep["before"]["v0"], after["v0"]], "c0": [rep["before"]["c0"], after["c0"]],
                                       "rate_eff": rep["rate_eff"], "scale": rep["scale"],
                                       "slide_mm": [rep["before"]["slide_mm"], after["slide_mm"]],
                                       "ankle_miss_mm": rep["ankle_miss_mm"],
                                       "foot_slide_mm": [rep["before"]["foot_slide_mm"], after["foot_slide_mm"]],
                                       "seam": cyc,
                                       "rate_at_speed": proof["rate_at_speed"]}), flush=True)
    if measures:
        (out / "measure.json").write_text(json.dumps(measures, indent=1), encoding="utf-8", newline="\n")


def main() -> int:
    sys.path.insert(0, str(HERE.parent))
    from runner import blender
    res = blender.run_script(Path(__file__).resolve(), sys.argv[1:], timeout=1800)
    print(*[x for x in (res.stdout or "").splitlines() if x.split(" ", 1)[0] in ("MEASURE", "GAME", "PROOF", "CHECK")],
          sep="\n", flush=True)
    return res.returncode


if __name__ == "__main__":
    if "bpy" in sys.modules:
        _blender_main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    else:
        sys.exit(main())
