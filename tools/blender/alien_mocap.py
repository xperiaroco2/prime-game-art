"""100STYLE motion capture onto the alien (art #196, the strafe pilot, step P1): picks a steady window of each chosen
BVH take (the travel straight, the hips' facing steady against it), bakes it onto a built alien character's contract
skeleton with retarget_core's Retargeter and retarget_maps/100style_contract.toml (Blender's own BVH importer), puts
its planted level on the floor, turns it to face the front (-Y), cuts one loop that starts on a left-foot contact
(alien_stride_math.cycle) and takes it in place (alien_loco_math.in_place), and renders the check sheet: per clip the
100STYLE skeleton (sticks on its bones) above the retargeted alien, the same moments of the window.

    $PYTHON_BIN tools/blender/alien_mocap.py --raw D:/prime-art-raw [--char chameleon] [--clips Neutral_BR,...]
        [--out <dir>] [--no-sheet]

Into <dir> (default <raw>/research/2026-10-22-roster/design/pilot3d/anim_bare/loco/p1): mocap.json (per clip the
window, the rest check, the numbers before and after the cut), <char>_char_100s.blend (the character with the actions
CharacterArmature|MC_<clip>, the faced window at the character's fps, and CharacterArmature|MC_<clip>_Loop, the loop
in place) and check_sheet.png. The BVH files are read as data (their numbers); the build's .blend is only read.
Without bpy the file starts Blender on itself (runner.blender, background).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

MAP = HERE / "retarget_maps" / "100style_contract.toml"
BVH_DIR = "downloads/100style/extracted/100STYLE"  # under the raw root
RAW_BASE = "research/2026-10-22-roster/design/pilot3d/anim_bare"
BUILD = "r2b/build"  # <build>/<char>/<char>_char.blend
OUT = "loco/p1"
# clip: the travel's heading against the hips' facing it should show (deg, positive toward the left), the view
CLIPS = {"Neutral_BR": (180.0, "side"), "Neutral_SR": (90.0, "front"), "Neutral_FR": (0.0, "side"),
         "Neutral_BW": (180.0, "side")}
WINDOW_S = 3.0  # the baked window (s): several cycles to cut one loop from
SPAN_S = 0.5  # the window's travel and facing read over spans of this length
LOOP_S = (0.5, 1.8)
SRC_FPS = 60.0


# ------------------------------------------------------------------------------------------- pure: the window
def _wrap(deg: float) -> float:
    return (deg + 180.0) % 360.0 - 180.0


def root_rows(path: Path) -> tuple[list, float]:
    """The BVH's root channels per frame (Xpos, Ypos, Zpos, Yrot, Xrot, Zrot; 100STYLE's order) and its fps."""
    lines = path.read_text(encoding="ascii").splitlines()
    i = next(k for k, line in enumerate(lines) if line.startswith("Frame Time"))
    fps = 1.0 / float(lines[i].split(":")[1])
    return [[float(x) for x in line.split()[:6]] for line in lines[i + 1:] if line.strip()], fps


def frame_cuts(path: Path, style: str, code: str) -> tuple[int, int]:
    """The take's usable frames (Frame_Cuts.csv: the start and stop of the motion, outside it the actor sets off)."""
    rows = [r.split(",") for r in path.read_text(encoding="utf-8").splitlines()]
    head, row = rows[0], next(r for r in rows if r[0] == style)
    return int(row[head.index(f"{code}_START")]), int(row[head.index(f"{code}_STOP")])


def pick_window(rows: list, fps: float, cuts: tuple, want_deg: float, window_s: float = WINDOW_S,
                span_s: float = SPAN_S, step: int = 6) -> dict:
    """The steadiest window of window_s seconds inside the cuts: per span its travel heading (the root's ground
    motion, 0 at the take's +Z) and the hips' facing (the Y rotation); cost = the travel's largest swing from its
    mean + the largest miss of travel - facing from want_deg (deg), less 20 per m/s of speed (a run, not a lull)."""
    n, s = int(round(window_s * fps)), int(round(span_s * fps))
    best = None
    for f0 in range(cuts[0], cuts[1] - n, step):
        heads, rels, speeds = [], [], []
        for a in range(f0, f0 + n - s + 1, s):
            p, q = rows[a], rows[a + s]
            dx, dz = q[0] - p[0], q[2] - p[2]
            speeds.append(math.hypot(dx, dz) / 100.0 / span_s)
            h = math.degrees(math.atan2(dx, dz))
            heads.append(h)
            rels.append(_wrap(h - 0.5 * (p[3] + q[3])))
        mean_h = math.degrees(math.atan2(sum(math.sin(math.radians(h)) for h in heads),
                                         sum(math.cos(math.radians(h)) for h in heads)))
        swing = max(abs(_wrap(h - mean_h)) for h in heads)
        miss = max(abs(_wrap(r - want_deg)) for r in rels)
        v = sum(speeds) / len(speeds)
        cost = swing + miss - 20.0 * v
        if best is None or cost < best["cost"]:
            best = {"start": f0, "stop": f0 + n, "cost": round(cost, 2), "swing_deg": round(swing, 1),
                    "facing_miss_deg": round(miss, 1), "speed_m_s": round(v, 3), "min_speed_m_s": round(min(speeds), 3)}
    return best


# ------------------------------------------------------------------------------------------------- Blender
def _lowest_rest(arm) -> float:
    return min(min((arm.matrix_world @ b.head_local).z, (arm.matrix_world @ b.tail_local).z) for b in arm.data.bones)


def import_bvh(path: Path) -> dict:
    """One BVH take through Blender's own importer: 0.01 (cm to m), the file's frames kept 1:1 from frame 1,
    quaternions; the armature lifted so its rest stands on the floor (floor_shift_m, as retarget_smpl's)."""
    import bpy
    from mathutils import Matrix
    before_obj, before_act = set(bpy.data.objects), set(bpy.data.actions)
    bpy.ops.import_anim.bvh(filepath=str(path), global_scale=0.01, frame_start=1, use_fps_scale=False,
                            update_scene_fps=False, update_scene_duration=False, rotate_mode="QUATERNION",
                            axis_forward="-Z", axis_up="Y", use_cyclic=False)
    new = [o for o in bpy.data.objects if o not in before_obj]
    acts = [a for a in bpy.data.actions if a not in before_act]
    if len(new) != 1 or new[0].type != "ARMATURE" or len(acts) != 1:
        raise SystemExit(f"{path}: {len(new)} objects and {len(acts)} actions, not one clip on one rig")
    arm = new[0]
    ad = arm.animation_data
    act = acts[0]
    ad.action = None
    for pb in arm.pose.bones:
        pb.location, pb.rotation_quaternion = (0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0)
    bpy.context.view_layer.update()
    h = -_lowest_rest(arm)
    arm.matrix_world = Matrix.Translation((0.0, 0.0, h)) @ arm.matrix_world
    bpy.context.view_layer.update()
    return {"arm": arm, "action": act, "floor_shift_m": h}


def sticks(arm, radius: float = 0.025):
    """A stick (a thin cylinder) on every bone of arm, parented to it, so the source skeleton renders."""
    import bpy
    from mathutils import Matrix
    made = []
    for b in arm.data.bones:
        length = b.length
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=radius, depth=length)
        o = bpy.context.active_object
        o.name = f"stick_{b.name}"
        o.data.transform(Matrix.Rotation(math.radians(-90.0), 4, "X") @ Matrix.Translation((0.0, 0.0, length / 2.0)))
        o.parent, o.parent_type, o.parent_bone = arm, "BONE", b.name
        o.matrix_parent_inverse.identity()
        o.location = (0.0, -length, 0.0)  # a bone child sits at the tail; back to the head, along the bone's +Y
        made.append(o)
    return made


def _blender_main(argv: list[str]) -> None:
    import bpy
    import alien_loco_math as L
    import alien_stride_math as S
    import alien_ttm_math as T
    import anim_libs
    import retarget_core as rc
    import retarget_map
    import retarget_smpl
    from alien_stride import PREFIX, _armature, sample, sheet, skeleton, write
    from alien_ttm import _cut, body_shape
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--char", default="chameleon")
    ap.add_argument("--clips", default=",".join(CLIPS))
    ap.add_argument("--out", default="")
    ap.add_argument("--no-sheet", action="store_true")
    a = ap.parse_args(argv)
    raw = Path(a.raw)
    out = Path(a.out) if a.out else raw / RAW_BASE / OUT
    out.mkdir(parents=True, exist_ok=True)
    blend = raw / RAW_BASE / BUILD / a.char / f"{a.char}_char.blend"
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    bpy.context.preferences.filepaths.save_version = 0
    arm = _armature()
    fps = bpy.context.scene.render.fps
    skel = S.prepare(skeleton(arm))
    shape, soles = body_shape(arm, skel)
    bmap = retarget_map.load(MAP)
    meshes = [o for o in arm.children if o.type == "MESH"]
    bvh_root = raw / BVH_DIR
    report = {"blend": str(blend), "fps": fps, "map": bmap["title"], "clips": {}}
    rows_for_sheet = []
    for name in a.clips.split(","):
        style, code = name.split("_", 1)
        want, view = CLIPS[name]
        path = bvh_root / style / f"{name}.bvh"
        rows, src_fps = root_rows(path)
        win = pick_window(rows, src_fps, frame_cuts(bvh_root / "Frame_Cuts.csv", style, code), want)
        src = import_bvh(path)
        srig = rc.Rig(src["arm"])
        sampler = anim_libs.Shifted(src["action"], "Hips", retarget_smpl.floor_offset(srig, src["floor_shift_m"],
                                                                                      "Hips"))
        rt = rc.Retargeter(srig, rc.Rig(arm), bmap)
        rt.set_soles(meshes)
        rest = rt.rest_error()
        n = int(math.floor((win["stop"] - win["start"]) / src_fps * fps + 1e-6))
        f_src = [sampler.start + win["start"] + k * src_fps / fps for k in range(n + 1)]
        frames = [rt.solve(rc.fk(srig, sampler.basis(f)))[1] for f in f_src]
        act = rc.bake(arm, PREFIX + "MC_" + name + "_raw", frames)
        clip = sample(arm, act)
        bpy.data.actions.remove(act)
        dz = T.floor_fit(T.sole_heights(skel, clip, soles))
        clip = T.shift_hips(skel, clip, -dz)
        face = math.degrees(math.atan2(*[sum(f(math.radians(S.hips_facing_deg(skel, clip, i)))
                                             for i in range(S.frames(clip))) for f in (math.sin, math.cos)]))
        clip, turn = S.orient_warp(skel, clip, -face, -face, split=())  # the whole window turned to face -Y
        clip["name"] = "MC_" + name
        write(arm, clip, clip["name"])
        whole = S.measure(skel, clip)
        loop, cyc = _cut(skel, clip, T.loop_bounds(whole["c0"], LOOP_S))
        loop, inplace = L.in_place(skel, loop)
        dz2 = T.floor_fit(T.sole_heights(skel, loop, soles))
        loop = T.shift_hips(skel, loop, -dz2)
        loop["name"] = f"MC_{name}_Loop"
        write(arm, loop, loop["name"])
        m = S.measure(skel, loop)
        rep = {"bvh": str(path.relative_to(raw)).replace("\\", "/"), "source_fps": src_fps,
               "source_frames": len(rows), "source_s": round(len(rows) / src_fps, 2), "window": win,
               "rest_check": rest, "ik_miss_mm": round(rt.miss_mm, 2), "translation_scale": round(rt.ratio, 4),
               "floor_shift_m": round(src["floor_shift_m"], 4), "floor_fit_mm": round((dz + dz2) * 1000.0, 1),
               "facing_turn_deg": round(-face, 2), "turn_report": turn,
               "window_v0": whole["v0"], "window_c0": whole["c0"], "window_frames": S.frames(clip),
               "loop": {"frames": S.frames(loop), "cycle_s": round(S.frames(loop) / fps, 3), "v0": m["v0"],
                        "c0": m["c0"], "stride_m": m["stride_m"], "cut": cyc, "in_place": inplace,
                        **T.direction(skel, loop, m), "foot_slide_mm": m["foot_slide_mm"],
                        "honest": S.honest_slide(skel, loop), "knee": S.knee_bend(skel, loop),
                        "hands": S.hand_clearance(skel, loop)}}
        report["clips"][name] = rep
        print("CLIP", name, json.dumps({"window": [win["start"], win["stop"]], "speed": win["speed_m_s"],
                                        "v0": m["v0"], "c0": m["c0"], "frames": S.frames(loop),
                                        "travel": rep["loop"].get("travel_deg"), "rest": rest}), flush=True)
        if not a.no_sheet and name in ("Neutral_BR", "Neutral_SR"):
            # drawn as the file plays it: the floor shift off (the shift is for the retarget's rest only) and the
            # same turn about z as the clip's
            src["arm"].location = (0.0, 0.0, 0.0)
            src["arm"].rotation_euler = (0.0, 0.0, math.radians(-face))
            src["action"].use_frame_range = True
            src["action"].frame_start = sampler.start + win["start"]
            src["action"].frame_end = sampler.start + win["start"] + n * src_fps / fps
            rows_for_sheet.append((name, view, src, bpy.data.actions[PREFIX + "MC_" + name]))
        else:
            bpy.data.objects.remove(src["arm"], do_unlink=True)
    sheets = []
    if rows_for_sheet:
        import numpy as np
        for name, view, src, act in rows_for_sheet:
            made = sticks(src["arm"])
            for who, rig, hide in (("source", src["arm"], meshes), ("alien", arm, made)):
                for o in hide:
                    o.hide_render = True
                for o in (made if who == "source" else meshes):
                    o.hide_render = False
                if who == "source":  # posed at the window's start, so the sheet's camera reads its standing height
                    src["arm"].animation_data.action = src["action"]
                    bpy.context.scene.frame_set(int(src["action"].frame_start))
                p = out / f"_check_{name}_{who}.png"
                sheet(rig, [src["action"] if who == "source" else act], p, views=[view], follow=True)
                sheets.append(p)
            for o in made:
                o.hide_render = True
        imgs = []
        for p in sheets:
            img = bpy.data.images.load(str(p), check_existing=False)
            imgs.append(np.array(img.pixels[:], dtype=np.float32).reshape(img.size[1], img.size[0], 4))
            bpy.data.images.remove(img)
            p.unlink()
        gap = np.ones((4, imgs[0].shape[1], 4), dtype=np.float32)
        stack = []
        for im in imgs:  # Blender's pixels run bottom-up: the first row goes last
            stack[:0] = [im, gap]
        canvas = np.concatenate(stack[:-1], axis=0)
        img = bpy.data.images.new("check_sheet", canvas.shape[1], canvas.shape[0], alpha=True)
        img.pixels.foreach_set(canvas.ravel())
        img.filepath_raw = str(out / "check_sheet.png")
        img.file_format = "PNG"
        img.save()
        report["sheet"] = {"path": str(out / "check_sheet.png"),
                           "rows": [f"{n} {w}" for n, _, _, _ in rows_for_sheet for w in ("source", "alien")]}
        for _, _, src, _ in rows_for_sheet:
            bpy.data.objects.remove(src["arm"], do_unlink=True)
        for o in [o for o in bpy.data.objects if o.name.startswith(("stick_", "stride_"))]:
            bpy.data.objects.remove(o, do_unlink=True)
    for act in [x for x in bpy.data.actions if not x.name.startswith(PREFIX)]:
        bpy.data.actions.remove(act)  # the BVH takes
    for act in bpy.data.actions:
        act.use_fake_user = True
    arm.animation_data.action = None
    saved = out / f"{a.char}_char_100s.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(saved), copy=True, compress=True)
    report["saved_blend"] = str(saved)
    (out / "mocap.json").write_text(json.dumps(report, indent=1), encoding="utf-8", newline="\n")
    print("DONE", saved, flush=True)


def main() -> int:
    sys.path.insert(0, str(HERE.parent))
    from runner import blender
    res = blender.run_script(Path(__file__).resolve(), sys.argv[1:], timeout=1800)
    print(*[x for x in (res.stdout or "").splitlines() if x.split(" ", 1)[0] in ("CLIP", "DONE")], sep="\n",
          flush=True)
    if res.returncode:
        print((res.stdout or "")[-3000:], (res.stderr or "")[-3000:], sep="\n", flush=True)
    return res.returncode


if __name__ == "__main__":
    if "bpy" in sys.modules:
        _blender_main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    else:
        sys.exit(main())
