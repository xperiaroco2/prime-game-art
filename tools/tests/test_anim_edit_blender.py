"""The clip edits (tools/blender/anim_edit.py, art #33) in headless Blender on the real files: the mirror of the pack's
Walk twice is the Walk again and a raised left arm becomes a raised right arm; reverse twice, a retime round trip and a
trim keep the frames; the cycle cut finds Walk_Loop's 1.33 s period in two concatenated cycles; in_place and heading
undo a travel and a 20 degree turn; the stride warp plays UAL's Jog at 4.5 m/s with planted feet; the floor lift takes
Death01's lying frames out of the floor; the women's arm offset takes their hands out of the thighs in Idle_Loop.

This file is also the Blender side of the test: run inside Blender (`blender -b ... --python <this file> -- <out>`)
it does the edits and writes their numbers to <out>/edits.json, which the unittest reads. Skipped when Blender or the
raw files are missing."""

from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

try:
    import bpy  # noqa: F401  (inside Blender: the driver below runs)
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False

if not IN_BLENDER:
    from runner import blender, common, pins
    from runner.commands import _anim

    OUT = common.OUT / "tests" / "anim_edit"
    HAVE_BLENDER = bool((path := common.tool_path(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)) and path.is_file())
    CFG = _anim.load_config()
    FILES = [common.raw_dir() / CFG["ual"]] + [common.raw_dir() / b["character"] for b in CFG["bodies"].values()]
    HAVE_FILES = all(f.is_file() for f in FILES)

    @unittest.skipUnless(HAVE_BLENDER and HAVE_FILES, "needs Blender and the raw packs (ART_RAW_DIR)")
    class AnimEditBlenderTest(unittest.TestCase):
        r: dict = {}

        @classmethod
        def setUpClass(cls) -> None:
            shutil.rmtree(OUT, ignore_errors=True)
            OUT.mkdir(parents=True)
            blender.run_script(Path(__file__).resolve(), [str(OUT), str(FILES[0]), str(FILES[1]), str(FILES[2])],
                               timeout=900)
            cls.r = json.loads((OUT / "edits.json").read_text(encoding="utf-8"))

        def test_mirror(self) -> None:
            m = self.r["mirror"]
            self.assertLess(m["twice_mm"], 0.01)
            self.assertLess(m["twice_deg"], 0.01)
            self.assertLess(m["rest_error_mm"], 0.01)
            self.assertGreater(m["raised_right_wrist_up_m"], 0.3)  # the left arm raised 90 degrees, mirrored
            self.assertLess(abs(m["raised_left_wrist_up_m"]), 0.001)

        def test_reverse_retime_trim(self) -> None:
            t = self.r["time"]
            self.assertLess(t["reverse_twice_deg"], 1e-6)
            self.assertLess(t["retime_round_trip_deg"], 0.5)  # the upper body
            self.assertLess(t["retime_round_trip_legs_deg"], 1.5)  # the IK legs bend sharply at a foot plant
            self.assertEqual(t["retime_frames"], [40, 32, 40])
            self.assertLess(t["trim_first_deg"], 1e-3)  # the trim's first frame is the original's frame 15
            self.assertEqual(t["trim_frames"], 15)

        def test_cycle(self) -> None:
            c = self.r["cycle"]
            self.assertLessEqual(abs(c["cycle_s"] - 4 / 3), 1.5 / 30)
            self.assertLessEqual(c["raw_seam_ratio"], 1.0)
            self.assertLess(c["closed_seam_deg"], 1e-3)

        def test_in_place_and_heading(self) -> None:
            h = self.r["heading"]
            self.assertGreater(h["travel_before_m"], 1.0)
            self.assertLess(h["travel_after_m"], 0.05)
            self.assertAlmostEqual(h["dir_before_deg"], 20.0, delta=1.5)  # the walk's own sway adds a little
            self.assertLess(abs(h["dir_after_deg"]), 1.0)

        def test_stride_jog(self) -> None:
            s = self.r["stride"]
            self.assertAlmostEqual(s["ground_speed_m_s"], 4.5, delta=4.5 * 0.05)  # measured on the baked action
            self.assertLessEqual(s["slide_mean_cm_s"], 6.0)
            self.assertLessEqual(s["report"]["ik_miss_contact_mm"], 10.0)
            self.assertLessEqual(s["report"]["knee_past_straight_deg"], 2.0)
            self.assertEqual(s["report"]["cadence"], 2.857)
            self.assertAlmostEqual(s["report"]["step_m"], 1.575, places=2)

        def test_floor_lift_death(self) -> None:
            f = self.r["floor"]
            self.assertLess(f["report"]["lowest_before_cm"], -3.0)  # Death01 lies 4.9 cm deep
            self.assertGreaterEqual(f["report"]["lowest_after_cm"], -0.5)
            self.assertGreaterEqual(f["lying_lowest_cm"], -0.5)

        def test_women_arm_offset(self) -> None:
            a = self.r["arms"]
            self.assertGreater(a["hands_in_legs_before_cm"], 0.5)
            self.assertLessEqual(a["hands_in_legs_after_cm"], 0.0)
            self.assertLessEqual(a["deg"], 12.0)

        def test_steps_and_errors(self) -> None:
            e = self.r["errors"]
            self.assertEqual(e["skipped"], {"op": "mirror", "skipped": "body women"})
            self.assertIn("raw seam", e["seam"])
            self.assertIn("in-place loop", e["stride"])
            self.assertIn("unknown op", e["unknown"])


def _blender_main(argv: list[str]) -> None:
    """Inside Blender: the edits on the men's and women's pack originals and UAL clips, numbers to edits.json."""
    import math
    import os

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
    from mathutils import Matrix, Quaternion, Vector

    import anim_edit as ae
    import anim_libs
    import anim_math as am
    import retarget_core as rc
    import retarget_map

    out_dir, ual, men, women = argv
    rc.new_scene()
    bmap = retarget_map.load()
    res = {}

    def setup(path, names):
        char = rc.load_glb(path)
        rc.add_toes(char)
        before = set(bpy.data.objects)
        src = anim_libs.load(ual, {}, None, bmap["hips"][0])
        rt = rc.Retargeter(rc.Rig(src["arm"]), rc.Rig(char["arm"]), bmap)
        rt.set_soles(char["meshes"].values())
        acts = {n: rt.clip(src["actions"][n], f"UAL|{n}", char["arm"], src["samplers"][n])[0] for n in names}
        for o in set(bpy.data.objects) - before:
            bpy.data.objects.remove(o, do_unlink=True)
        rc.reset_pose(char["arm"])
        bpy.context.view_layer.update()
        return char, acts

    def angle(a, b, bones=None):
        """The largest bone rotation between two frames (degrees), from the quaternions' chord: exact near zero,
        where acos of mathutils' single-precision dot product reads 0.05 degrees for equal rotations."""
        worst = 0.0
        for n in bones or a:
            qa, qb = a[n].to_quaternion(), b[n].to_quaternion()
            chord = min((qa - qb).magnitude, (qa + qb).magnitude)
            worst = max(worst, math.degrees(4 * math.asin(min(1.0, chord / 2))))
        return worst

    def offset_mm(fr_a, fr_b):
        rig = fr_a.rig
        return max((rig.W @ pa[n].translation - rig.W @ pb[n].translation).length * 1000
                   for pa, pb in zip(fr_a.poses(), fr_b.poses()) for n in pa)

    char, acts = setup(men, ["Walk_Loop", "Jog_Fwd_Loop", "Death01"])
    target = ae.Target(char)
    rig = target.rig
    walk = ae.Frames.from_action(char["actions"]["Walk"], rig, True)

    # mirror: twice is the original; a raised left arm becomes a raised right arm
    once = ae.apply(walk, [{"op": "mirror"}], target, "men")
    twice = ae.apply(once, [{"op": "mirror"}], target, "men")
    raised = {n: Matrix.Identity(4) for n in rig.order}
    up = rc.rot(rig.rest["UpperArm.L"]).inverted() @ (rig.Wi.to_3x3().normalized() @ Vector((0.0, -1.0, 0.0)))
    raised["UpperArm.L"] = Quaternion(up, math.radians(-90)).to_matrix().to_4x4()
    arm = ae.Frames(rig, [raised])
    rest_p = rc.fk(rig, {})
    lift = {s: (rig.W @ arm.poses()[0][f"Wrist.{s}"].translation).z - (rig.W @ rest_p[f"Wrist.{s}"].translation).z
            for s in "LR"}
    if lift["L"] < 0:  # the test pose turned the arm down: turn it up instead
        raised["UpperArm.L"] = Quaternion(up, math.radians(90)).to_matrix().to_4x4()
    m_arm = ae.apply(ae.Frames(rig, [raised]), [{"op": "mirror"}], target, "men").poses()[0]
    res["mirror"] = {
        "twice_mm": offset_mm(walk, twice), "twice_deg": max(angle(a, b) for a, b in zip(walk.basis, twice.basis)),
        "rest_error_mm": once.info["steps"][0]["rest_error_mm"],
        "raised_right_wrist_up_m": (rig.W @ m_arm["Wrist.R"].translation).z - (rig.W @ rest_p["Wrist.R"].translation).z,
        "raised_left_wrist_up_m": (rig.W @ m_arm["Wrist.L"].translation).z - (rig.W @ rest_p["Wrist.L"].translation).z,
    }

    # reverse twice, a retime round trip (UAL's Walk_Loop, keyed at 30 fps: the pack's 24 fps keys sampled at 30 fps
    # bend at every key, which no resampling at other times keeps), a trim
    upper = target.upper_bones()
    legs = [n for n in rig.order if n not in upper and not n.startswith("Toe.")]
    rev2 = ae.apply(walk, [{"op": "reverse"}, {"op": "reverse"}], target, "men")
    wl = ae.Frames.from_action(acts["Walk_Loop"], rig, True)
    fast = ae.apply(wl, [{"op": "retime", "rate": 1.25}], target, "men")
    back = ae.apply(fast, [{"op": "retime", "seconds": wl.seconds}], target, "men")
    trim = ae.apply(walk, [{"op": "trim", "start_s": 0.5, "end_s": 1.0}], target, "men")
    res["time"] = {
        "reverse_twice_deg": max(angle(a, b) for a, b in zip(walk.basis, rev2.basis)),
        # the toe bones flick up to 28 degrees a frame where the retarget's floor clamp lifts them: no resampling
        # keeps that, so they are measured by themselves
        "retime_round_trip_deg": max(angle(a, b, upper) for a, b in zip(wl.basis, back.basis)),
        "retime_round_trip_legs_deg": max(angle(a, b, legs) for a, b in zip(wl.basis, back.basis)),
        "retime_round_trip_toes_deg": max(angle(a, b, ["Toe.L", "Toe.R"]) for a, b in zip(wl.basis, back.basis)),
        "retime_frames": [wl.frames, fast.frames, back.frames],
        "trim_first_deg": angle(trim.basis[0], walk.basis[15]), "trim_frames": trim.frames,
    }

    # cycle: two Walk_Loop cycles from frame 7, cut back to one
    two = ae.Frames(rig, wl.basis[7:] + wl.basis[1:] + wl.basis[1:8], loop=False)
    cyc = ae.apply(two, [{"op": "cycle", "min_s": 1.0, "max_s": 2.0}], target, "men")
    rep = cyc.info["steps"][0]
    steps = [angle(a, b) for a, b in zip(wl.basis, wl.basis[1:])]
    res["cycle"] = {"cycle_s": rep["cycle_s"], "raw_seam_ratio": rep["raw_seam_deg"] / max(sorted(steps)[len(steps) // 2], 1e-6),
                    "closed_seam_deg": angle(cyc.basis[0], cyc.basis[-1]), "report": rep}

    # in place and heading: the walk given 3 m/s of travel turned 20 degrees to the left
    trav = wl.copy()
    walk_xf = [Matrix.Rotation(math.radians(20), 4, "Z") @ Matrix.Translation((0.0, -3.0 * k / 30, 0.0))
               for k in range(len(trav.basis))]
    ae._move_world(trav, walk_xf)
    trav.loop = False
    head = ae.apply(trav, [{"op": "heading", "travel": "forward"}], target, "men")
    flat = ae.apply(trav, [{"op": "in_place", "mode": "linear"}], target, "men")
    hp = [rig.W @ P["Body"].translation for P in flat.poses()]
    res["heading"] = {"dir_before_deg": head.info["steps"][0]["travel_dir_deg_before"],
                      "dir_after_deg": head.info["steps"][0]["travel_dir_deg"],
                      "travel_before_m": flat.info["steps"][0]["travel_m"],
                      "travel_after_m": math.hypot(hp[-1].x - hp[0].x, hp[-1].y - hp[0].y)}

    # stride: UAL's Jog at 4.5 m/s and 2.8 steps/s, measured again on the baked action
    jog = ae.apply(ae.Frames.from_action(acts["Jog_Fwd_Loop"], rig, True),
                   [{"op": "stride", "speed_m_s": 4.5, "cadence": 2.8}], target, "men")
    act = jog.to_action(char["arm"], "edit|Jog_4.5")
    s = rc.Sampler(act)
    feet = {f: [] for f in ("Foot.L", "Foot.R")}
    for i in range(int(round(s.frames)) + 1):
        P = rc.fk(rig, s.basis(s.start + i))
        for f in feet:
            feet[f].append(tuple(rig.W @ P[f].translation))
    slide = am.foot_sliding(feet, 30)
    res["stride"] = {"report": jog.info["steps"][0], "ground_speed_m_s": slide["ground_speed_cm_s"] / 100,
                     "slide_mean_cm_s": slide["slide_mean_cm_s"]}

    # floor: Death01 lifted out of the floor from 1.2 s
    death = ae.apply(ae.Frames.from_action(acts["Death01"], rig, False),
                     [{"op": "floor", "mode": "lift", "from_s": 1.2}], target, "men")
    lows = ae._lows(death, target)
    res["floor"] = {"report": death.info["steps"][0], "lying_lowest_cm": 100 * min(lows[round(1.45 * 30):])}

    # steps for another body are skipped; errors name their step
    res["errors"] = {"skipped": ae.apply(walk, [{"op": "mirror", "body": "women"}], target, "men").info["steps"][0]}
    for key, fr, steps in (("seam", two, [{"op": "cycle", "min_s": 0.3, "max_s": 0.5, "max_raw_seam_deg": 0.01}]),
                           ("stride", ae.Frames.from_action(acts["Death01"], rig, False),
                            [{"op": "stride", "speed_m_s": 4.5, "cadence": 2.8}]),
                           ("unknown", walk, [{"op": "explode"}])):
        try:
            ae.apply(fr, steps, target, "men")
            res["errors"][key] = "no error"
        except ae.EditError as e:
            res["errors"][key] = str(e)

    # the women's arms out of the thighs in Idle_Loop
    for o in list(bpy.data.objects):
        if o.type in ("MESH", "ARMATURE", "EMPTY") and o.name != "floor":
            bpy.data.objects.remove(o, do_unlink=True)
    char, acts = setup(women, ["Idle_Loop"])
    target = ae.Target(char)
    idle = ae.apply(ae.Frames.from_action(acts["Idle_Loop"], target.rig, True),
                    [{"op": "arm_offset", "abduct_deg": "auto", "body": "women"}], target, "women")
    res["arms"] = idle.info["steps"][0]

    with open(os.path.join(out_dir, "edits.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, default=str)


if IN_BLENDER and __name__ == "__main__":
    _blender_main(sys.argv[sys.argv.index("--") + 1:])
elif __name__ == "__main__":
    unittest.main()
