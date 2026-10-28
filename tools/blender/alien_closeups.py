"""Close-up review sheets of a built alien character (art #196, clothes step 2): the neck joint and the hands, in
headless Blender's Workbench (alien_cage_review.py's cameras and numpy sheets), on a character build's
<char>_char.blend (alien_char_build.py, alien_loco.py).

    blender -b --factory-startup --python-exit-code 1 --python tools/blender/alien_closeups.py -- \
        --blend <char>_char.blend --tag <name> --out <dir> [--res 384]

- neck_<tag>.png: the joint where the head meets the neck at 1.9 m (lens 70) and 0.8 m (lens 50), 3/4 front, side
  and 3/4 back (the character's left), in an Idle frame and with the head turned 40 degrees away from the camera
  side (the Head bone on top of the Idle pose); one row per pose and distance, the texture colours (seams and colour
  steps) beside one flat colour (creases and bands);
- hands_<tag>.png: the left hand at 0.45 m from outside and from the front, in Idle, Jog_Fwd, Jump_Start and
  Talk_Upper, each at its first and middle frame (a relaxed and a curled hand), texture colours;
- closeups_<tag>.json: the cells' order, frames and camera places.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_cage_review as R  # noqa: E402

HAND_CLIPS = ("Idle", "Jog_Fwd", "Jump_Start", "Talk_Upper")
AZIMUTHS = (("34front", 45.0), ("side", 90.0), ("34back", 135.0))
DISTANCES = ((1.9, 70.0), (0.8, 50.0))
TURN_DEG = -40.0  # about the armature's up: away from the +x (the character's left) camera side


def action(name: str):
    """The clip's action: CharacterArmature|<name>_Loop, CharacterArmature|<name> or <name>(_Loop)."""
    for n in (f"CharacterArmature|{name}_Loop", f"CharacterArmature|{name}", f"{name}_Loop", name):
        if n in bpy.data.actions:
            return bpy.data.actions[n]
    raise SystemExit(f"no action for {name}: {sorted(a.name for a in bpy.data.actions)[:12]} ...")


def play(arm, act, frame: int) -> None:
    arm.animation_data_create()
    arm.animation_data.action = act
    if getattr(act, "slots", None) and len(act.slots):
        arm.animation_data.action_slot = act.slots[0]
    bpy.context.scene.frame_set(frame)


def freeze_turned(arm, deg: float) -> None:
    """Holds the current pose without its action, the Head bone turned deg about the armature's up at its head."""
    basis = {pb.name: pb.matrix_basis.copy() for pb in arm.pose.bones}
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.matrix_basis = basis[pb.name]
    bpy.context.view_layer.update()
    hb = arm.pose.bones["Head"]
    m = hb.matrix.copy()
    piv = m.to_translation()
    rot = Matrix.Translation(piv) @ Matrix.Rotation(math.radians(deg), 4, "Z") @ Matrix.Translation(-piv)
    hb.matrix = rot @ m
    bpy.context.view_layer.update()


def world(arm, bone: str, tail: bool = False) -> Vector:
    pb = arm.pose.bones[bone]
    return arm.matrix_world @ (pb.tail if tail else pb.head)


def front_sign(arm) -> float:
    return 1.0 if (world(arm, "LeftToes") - world(arm, "LeftFoot")).y > 0 else -1.0


def place(sign: float, az: float, dist: float, up: float = 0.08) -> Vector:
    """A camera offset at azimuth az from the front toward +x, a little above."""
    a = math.radians(az)
    return Vector((math.sin(a) * dist, sign * math.cos(a) * dist, up * dist))


def shade(sc, texture: bool) -> None:
    sh = sc.display.shading
    sh.color_type = "TEXTURE" if texture else "SINGLE"
    sh.show_cavity = not texture


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--res", type=int, default=384)
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tmp = out / f"_cells_{args.tag}"
    tmp.mkdir(exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(Path(args.blend).resolve()))
    sc, cam = R.setup((args.res, args.res))
    sc.display.shading.cavity_type = "WORLD"
    arm = bpy.data.objects["CharacterArmature"]
    sign = front_sign(arm)
    idle = action("Idle")
    f_idle = int(idle.frame_range[0])
    log = {"blend": str(Path(args.blend).resolve()), "front_sign_y": sign, "neck": [], "hands": []}
    rows = []
    for pose in ("idle", "turn"):
        play(arm, idle, f_idle)
        if pose == "turn":
            freeze_turned(arm, TURN_DEG)
        target = (world(arm, "Neck") + world(arm, "Head")) / 2
        for dist, lens in DISTANCES:
            row = []
            for texture in (True, False):
                shade(sc, texture)
                for name, az in AZIMUTHS:
                    loc = target + place(sign, az, dist)
                    R.look(cam, loc, target, lens=lens)
                    p = str(tmp / f"neck_{pose}_{dist}_{name}_{int(texture)}.png")
                    R.shot(sc, p)
                    row.append(R.load(p))
                    log["neck"].append({"pose": pose, "dist_m": dist, "lens": lens, "view": name,
                                        "texture": texture, "frame": f_idle, "target": list(target)})
            rows.append(row)
        if pose == "turn":
            for pb in arm.pose.bones:
                pb.matrix_basis = Matrix.Identity(4)
    R.grid(rows, str(out / f"neck_{args.tag}.png"))
    shade(sc, True)
    rows = []
    for clip in HAND_CLIPS:
        act = action(clip)
        f0, f1 = (int(x) for x in act.frame_range)
        row = []
        for frame in (f0, (f0 + f1) // 2):
            play(arm, act, frame)
            c = (world(arm, "LeftHand") + world(arm, "LeftMiddleProximal")) / 2
            fwd = Vector((0.0, sign, 0.0))
            for name, off in (("outside", Vector((1.0, 0.35 * sign, 0.25))), ("front", fwd + Vector((0.2, 0, 0.2)))):
                loc = c + off.normalized() * 0.45
                R.look(cam, loc, c, lens=50)
                p = str(tmp / f"hand_{clip}_{frame}_{name}.png")
                R.shot(sc, p)
                row.append(R.load(p))
                log["hands"].append({"clip": act.name, "frame": frame, "view": name, "target": list(c)})
        rows.append(row)
    R.grid(rows, str(out / f"hands_{args.tag}.png"))
    (out / f"closeups_{args.tag}.json").write_text(json.dumps(log, indent=1), encoding="utf-8", newline="\n")
    for f in tmp.iterdir():
        os.remove(f)
    tmp.rmdir()
    print("CLOSEUPS", out / f"neck_{args.tag}.png", out / f"hands_{args.tag}.png", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
