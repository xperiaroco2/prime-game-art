"""The alien's hand shapes in every loco clip, their check and their review sheets (art #196, Hands H1; the maths in
alien_hands_math.py, the data in anim_sets/alien_hands.toml). Headless Blender:

    blender -b --factory-startup --python-exit-code 1 --python tools/blender/alien_hands.py -- --blend <in.blend> \
        [--apply <dir> --name <char> [--glb]] [--check <dir>] [--sheet <png> --rows <spec> [--sketch <png>]]
        [--video <dir> --before <before.blend> [--clips Walk,Jog_Fwd] [--side Left]]

- `--apply`: every action's finger channels (the five chains of both hands) are removed and keyed with the clip's
  grips (`alien_hands_math.clip_plan`; skipped actions untouched); every other channel stays. Saves
  `<dir>/<name>_char.blend` (refused when it exists), `<dir>/hands.json` (per action its entry, grips and frames) and,
  with `--glb`, `<dir>/<name>_char.glb` with alien_loco's textured export.
- `--check`: the skin dump (`alien_poses._dump`), per grip and hand the finger collisions at rest and past the rest
  pose's floor, and per clip the worst of its grips: `<dir>/collisions.json`, `<dir>/collisions.md`.
- `--sheet`: the left hand (`--side Right`: the right) at 0.8 m (lens 85) from outside, the palm side, the thumb side and the other side, one row
  per spec item (`grip:<name>`: the rest pose with the grip; `clip:<name>@<share>`: the clip at that share of its
  frames; `rest`); flat colour with cavity; `--sketch` puts the sketch's hands beside the first row.
- `--video` (H1c): per clip one cycle with the camera following the hand from the front and from its side, each frame
  the `--before` character's two views beside the `--blend`'s; `<dir>/<clip>_<side>.mp4` (24 fps, three cycles).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import alien_cage_review as R  # noqa: E402
import alien_hands_math as H  # noqa: E402
import alien_pose_math as A  # noqa: E402
import numpy as np  # noqa: E402

VIEWS = ("outside", "palm", "thumb side", "other side")
DIST, LENS = 0.8, 85


def _arm():
    return next(o for o in bpy.data.objects if o.type == "ARMATURE")


def _bag(act):
    """The action's channelbag for its first slot (Blender 5's layered actions), made when missing."""
    from bpy_extras import anim_utils
    slot = act.slots[0]
    bag = anim_utils.action_get_channelbag_for_slot(act, slot)
    if bag is None:
        raise SystemExit(f"{act.name}: no channelbag for its first slot")
    return bag


def apply(cfg: dict, arm) -> dict:
    """Every action's finger channels replaced by its grips; returns the report."""
    report = {}
    names = set(H.finger_bones("Left") + H.finger_bones("Right"))
    for pb in arm.pose.bones:
        if pb.name in names:
            pb.rotation_mode = "QUATERNION"
    for act in bpy.data.actions:
        entry = H.clip_plan(cfg, act.name)
        if entry is None:
            report[act.name] = {"skipped": True}
            continue
        pat, plan = entry
        f0, f1 = (int(round(x)) for x in act.frame_range)
        fc = _bag(act).fcurves
        gone = [c for c in fc if c.data_path.startswith('pose.bones["')
                and c.data_path.split('"')[1] in names]
        for c in gone:
            fc.remove(c)
        for side, rows in plan.items():
            for bone, keys in H.keyed(cfg, rows, side, (f0, f1)).items():
                if bone not in arm.pose.bones:
                    continue
                qs, prev = [], None
                for fr, q in keys:  # neighbouring keys on one hemisphere: the short way between grips
                    if prev is not None and sum(x * y for x, y in zip(prev, q)) < 0:
                        q = tuple(-x for x in q)
                    qs.append((fr, q))
                    prev = q
                path = f'pose.bones["{bone}"].rotation_quaternion'
                for i in range(4):
                    c = fc.new(path, index=i, group_name=bone)
                    c.keyframe_points.add(len(qs))
                    for k, (fr, q) in zip(c.keyframe_points, qs):
                        k.co = (fr, q[i])
                        k.interpolation = "BEZIER"
                    c.update()
        report[act.name] = {"entry": pat, "frames": [f0, f1], "removed_channels": len(gone),
                            "grips": {s: [[r[0], r[1]] for r in rows] for s, rows in plan.items()}}
    return report


def check(cfg: dict, arm, out: Path, used: dict) -> dict:
    import alien_poses as P
    dump = P._dump(arm)
    (out / "dump.json").write_text(json.dumps(dump), encoding="utf-8", newline="\n")
    rows = {}
    for side in A.SIDES:
        floor = H.collisions(dump["skel"], dump["skin"], cfg, "", side)
        rows[f"rest/{side}"] = floor
        for g in cfg["grips"]:
            r = H.collisions(dump["skel"], dump["skin"], cfg, g, side)
            r["excess_cm"] = H.excess(r, floor)
            rows[f"{g}/{side}"] = r
    clips = {}
    for act, e in used.items():
        if e.get("skipped"):
            continue
        clips[H.game_name(act)] = {s: {"grips": sorted({g for _, g in e["grips"][s]}),
                                       "worst_cm": max(rows[f"{g}/{s}"]["worst_cm"] for _, g in e["grips"][s]),
                                       "excess_cm": max(rows[f"{g}/{s}"]["excess_cm"] for _, g in e["grips"][s])}
                                   for s in A.SIDES}
    res = {"grips": rows, "clips": clips}
    (out / "collisions.json").write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
    lines = ["# Finger collisions (cm; alien_hands_math.collisions)", "", "## Per grip", "",
             "| grip/hand | into finger T/I/M/R | into palm T/I/M/R | tip into base T/I/M/R | gap I-M, M-R | past rest |",
             "|---|---|---|---|---|---|"]
    for k, r in rows.items():
        f = lambda d: " / ".join(str(d[x]) for x in H.DIGITS)  # noqa: E731
        lines.append(f"| {k} | {f(r['into_finger_cm'])} | {f(r['into_palm_cm'])} | {f(r['self_cm'])} | "
                     f"{' , '.join(str(v) for v in r['gap_cm'].values())} | {r.get('excess_cm', '-')} |")
    lines += ["", "## Per clip", ""] + H.table(clips)
    (out / "collisions.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return res


def _hand_axes(arm, side: str = "Left"):
    """The hand's palm normal and thumb side in its bone's local axes (from the T-pose rest: -Z, -Y)."""
    b = arm.data.bones[f"{side}Hand"]
    inv = (arm.matrix_world.to_3x3() @ b.matrix_local.to_3x3()).inverted()
    return inv @ Vector((0.0, 0.0, -1.0)), inv @ Vector((0.0, -1.0, 0.0))


def _look(cam, loc: Vector, target: Vector, up: Vector) -> None:
    fwd = (target - loc).normalized()
    right = fwd.cross(up).normalized()
    upv = right.cross(fwd)
    m = Matrix((right, upv, -fwd)).transposed()
    cam.matrix_world = Matrix.Translation(loc) @ m.to_4x4()
    cam.data.type, cam.data.lens, cam.data.clip_start = "PERSP", LENS, 0.01


def _pose_rest(arm) -> None:
    if arm.animation_data:
        arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)


def sheet(cfg: dict, arm, spec: str, png: Path, sketch: str = "", res: int = 320, side: str = "Left") -> list:
    import alien_closeups as C
    sc, cam = R.setup((res, res))
    sc.display.shading.show_cavity = True
    sc.display.shading.cavity_type = "WORLD"
    palm_l, thumb_l = _hand_axes(arm, side)
    tmp = png.parent / f"_cells_{png.stem}"
    tmp.mkdir(parents=True, exist_ok=True)
    rows, log = [], []
    for item in spec.split(","):
        kind, _, val = item.partition(":")
        _pose_rest(arm)
        if kind == "grip":
            for b, q in H.grip_pose(cfg, val, side).items():
                if b in arm.pose.bones:
                    arm.pose.bones[b].rotation_mode = "QUATERNION"
                    arm.pose.bones[b].rotation_quaternion = q
        elif kind == "clip":
            name, _, share = val.partition("@")
            act = C.action(name)
            f0, f1 = act.frame_range
            C.play(arm, act, int(round(f0 + float(share or 0) * (f1 - f0))))
        bpy.context.view_layer.update()
        pb = arm.pose.bones[f"{side}Hand"]
        rot = (arm.matrix_world @ pb.matrix).to_3x3().normalized()
        length = rot @ Vector((0.0, 1.0, 0.0))
        palm, thumb = (rot @ palm_l).normalized(), (rot @ thumb_l).normalized()
        c = arm.matrix_world @ ((pb.head + arm.pose.bones[f"{side}MiddleIntermediate"].head) / 2)
        row = []
        for view, d in zip(VIEWS, (-palm, palm, thumb, -thumb)):
            _look(cam, c + d * DIST, c, -length)
            p = str(tmp / f"{len(rows)}_{view.replace(' ', '_')}.png")
            R.shot(sc, p)
            row.append(R.load(p))
        log.append({"item": item, "target": list(c)})
        rows.append(row)
    if sketch:
        img = bpy.data.images.load(sketch)
        w, h = img.size
        s = res / h
        img.scale(max(1, int(w * s)), res)
        w2, h2 = img.size
        a = np.array(img.pixels[:], dtype=np.float32).reshape(h2, w2, 4)[::-1]
        bpy.data.images.remove(img)
        rows[0] = [a] + rows[0]
    R.grid(rows, str(png))
    for f in tmp.iterdir():
        os.remove(f)
    tmp.rmdir()
    return log


def _video_frames(arm, side: str, clips: list, out: Path, res: int) -> dict:
    """Per clip one cycle of frames, the camera following the hand: from the front (-Y) and the hand's side."""
    import alien_closeups as C
    sc, cam = R.setup((res, res))
    sc.display.shading.show_cavity = True
    sc.display.shading.cavity_type = "WORLD"
    sx = 1.0 if side == "Left" else -1.0
    made = {}
    for name in clips:
        act = C.action(name)
        f0, f1 = (int(round(x)) for x in act.frame_range)
        cells = []
        for f in range(f0, f1):
            C.play(arm, act, f)
            bpy.context.view_layer.update()
            pb = arm.pose.bones[f"{side}Hand"]
            c = arm.matrix_world @ ((pb.head + arm.pose.bones[f"{side}MiddleIntermediate"].head) / 2)
            row = []
            for view, d in (("front", Vector((0.0, -1.0, 0.0))), ("side", Vector((sx, 0.0, 0.0)))):
                _look(cam, c + d * DIST, c, Vector((0.0, 0.0, 1.0)))
                p = out / f"{name}_{view}_{f - f0:04d}.png"
                R.shot(sc, str(p))
                row.append(str(p))
            cells.append(row)
        made[name] = cells
    return made


def video(cfg: dict, before: str, after: str, side: str, clips: list, out: Path, res: int = 360) -> list:
    """`--video`: per clip an MP4, each frame [before front | before side || after front | after side]."""
    import encode_clips as E
    tmp = out / "_frames"
    cells = {}
    for tag, blend in (("before", before), ("after", after)):
        bpy.ops.wm.open_mainfile(filepath=str(Path(blend).resolve()))
        d = tmp / tag
        d.mkdir(parents=True, exist_ok=True)
        cells[tag] = _video_frames(_arm(), side, clips, d, res)
    made = []
    for name in clips:
        fd = tmp / f"{name}_{side}"
        fd.mkdir(parents=True, exist_ok=True)
        n = min(len(cells["before"][name]), len(cells["after"][name]))
        for k in range(n):
            b, a = cells["before"][name][k], cells["after"][name][k]
            R.grid([[R.load(b[0]), R.load(b[1]), R.load(a[0]), R.load(a[1])]], str(fd / f"{k:04d}.png"))
        mp4 = out / f"{name}_{side}.mp4"
        E.encode(str(fd), str(mp4), 24, 3)
        made.append(str(mp4))
        for im in list(bpy.data.images):
            bpy.data.images.remove(im)
    return made


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", required=True)
    ap.add_argument("--hands", default=str(H.DATA))
    ap.add_argument("--apply")
    ap.add_argument("--name", default="")
    ap.add_argument("--glb", action="store_true")
    ap.add_argument("--check")
    ap.add_argument("--sheet")
    ap.add_argument("--rows", default="rest,grip:relaxed")
    ap.add_argument("--sketch", default="")
    ap.add_argument("--side", choices=("Left", "Right"), default="Left", help="the sheet's hand")
    ap.add_argument("--video", help="a folder: per clip an MP4 of the hand, --before | --blend, front and side")
    ap.add_argument("--before", default="", help="--video: the before character's .blend")
    ap.add_argument("--clips", default="Walk,Jog_Fwd", help="--video: the clips")
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    cfg = H.load(Path(a.hands))
    if a.video:
        out = Path(a.video)
        if out.exists():
            raise SystemExit(f"{out} exists")
        out.mkdir(parents=True)
        for m in video(cfg, a.before, a.blend, a.side, a.clips.split(","), out):
            print("HANDS video", m, flush=True)
        return 0
    bpy.ops.wm.open_mainfile(filepath=str(Path(a.blend).resolve()))
    arm = _arm()
    used = {}
    if a.apply:
        out = Path(a.apply)
        blend = out / f"{a.name}_char.blend"
        if blend.exists():
            raise SystemExit(f"{blend} exists: never over a raw build")
        out.mkdir(parents=True, exist_ok=True)
        used = apply(cfg, arm)
        (out / "hands.json").write_text(json.dumps({"source": a.blend, "hands": a.hands, "actions": used}, indent=1),
                                        encoding="utf-8", newline="\n")
        bpy.ops.wm.save_as_mainfile(filepath=str(blend))
        if a.glb:
            import alien_loco as L
            L._export(arm, out / f"{a.name}_char.glb")
            bpy.ops.wm.open_mainfile(filepath=str(blend))
            arm = _arm()
        print("HANDS apply", blend, sum(1 for e in used.values() if not e.get("skipped")), "actions", flush=True)
    else:
        used = {act.name: {"entry": p[0], "grips": p[1]} if (p := H.clip_plan(cfg, act.name)) else {"skipped": True}
                for act in bpy.data.actions}
    if a.check:
        out = Path(a.check)
        out.mkdir(parents=True, exist_ok=True)
        res = check(cfg, arm, out, used)
        worst = max((r.get("excess_cm", 0.0) for r in res["grips"].values()), default=0.0)
        print("HANDS check", out / "collisions.md", "worst past rest cm", worst, flush=True)
    if a.sheet:
        png = Path(a.sheet)
        if png.exists():
            raise SystemExit(f"{png} exists")
        png.parent.mkdir(parents=True, exist_ok=True)
        log = sheet(cfg, arm, a.rows, png, a.sketch, side=a.side)
        png.with_suffix(".json").write_text(json.dumps(log, indent=1), encoding="utf-8", newline="\n")
        print("HANDS sheet", png, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
