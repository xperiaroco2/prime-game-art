"""The relaxed idle's clip edits (tools/blender/anim_edit.py, art #49) in headless Blender on the real rig: UAL's
Idle_Loop on the men's and women's pack originals through the MVP set's own steps (tools/blender/anim_sets/mvp.toml):
the right foot turned in to about +3.7 degrees with the ankle on its foot, the feet at hip width and planted, the
shoulders down, the head level, open hands with the thumb in, the loop closed without a pop; each op by itself on the
raw idle; the women's arm offset re-checked by its auto search on the relaxed hands; and idle_ends on the jump's
take-off and landing, whose touching frames then stand exactly in the relaxed idle's first frame.

This file is also the Blender side of the test: run inside Blender (`blender -b ... --python <this file> -- <out>`)
it does the edits and writes their numbers to <out>/relax.json, which the unittest reads. Skipped when Blender or the
raw files are missing."""

from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

IN_BLENDER = "bpy" in sys.modules  # Blender runs this file with its bpy already loaded: the driver below runs
if IN_BLENDER:
    import bpy

if not IN_BLENDER:
    from runner import blender, common, pins
    from runner.commands import _anim

    OUT = common.OUT / "tests" / "anim_edit_relax"
    HAVE_BLENDER = bool((path := common.tool_path(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)) and path.is_file())
    CFG = _anim.load_config()
    FILES = [common.raw_dir() / CFG["ual"]] + [common.raw_dir() / b["character"] for b in CFG["bodies"].values()]
    HAVE_FILES = all(f.is_file() for f in FILES)

    @unittest.skipUnless(HAVE_BLENDER and HAVE_FILES, "needs Blender and the raw packs (ART_RAW_DIR)")
    class AnimEditRelaxBlenderTest(unittest.TestCase):
        r: dict = {}

        @classmethod
        def setUpClass(cls) -> None:
            shutil.rmtree(OUT, ignore_errors=True)
            OUT.mkdir(parents=True)
            blender.run_script(Path(__file__).resolve(), [str(OUT), str(FILES[0]), str(FILES[1]), str(FILES[2])],
                               timeout=900)
            cls.r = json.loads((OUT / "relax.json").read_text(encoding="utf-8"))

        def test_the_relaxed_idle(self) -> None:
            for body, width, stagger in (("men", 27.47, 5.56), ("women", 22.85, 4.46)):  # the lab's round D
                idle = self.r[body]["idle"]
                feet = idle["feet"]
                self.assertAlmostEqual(feet["yaw_out_deg"]["R"]["min"], 3.66, delta=0.05, msg=body)
                self.assertAlmostEqual(feet["yaw_out_deg"]["R"]["max"], 3.66, delta=0.05, msg=body)
                self.assertAlmostEqual(feet["yaw_out_deg"]["L"]["first"], -5.68, delta=0.05, msg=body)
                self.assertLess(feet["ankle_gap_mm_max"], 0.05, body)  # the ankles on their feet
                self.assertAlmostEqual(feet["width_cm"], width, delta=0.05, msg=body)
                self.assertAlmostEqual(feet["stagger_cm"], stagger, delta=0.05, msg=body)
                self.assertLess(idle["feet_travel_mm"], 0.01, body)  # planted
                self.assertLess(idle["seam_mm"], 0.01, body)  # the loop closed
                self.assertEqual(idle["pops"], [], body)
                self.assertLess(max(abs(x) for x in idle["head_pitch_deg"]), 3.0, body)  # level: -2.2 to +2.3
                self.assertAlmostEqual(idle["middle2_deg"], 20.0, delta=0.01, msg=body)
                self.assertAlmostEqual(idle["thumb_turn_deg"], 22.3, delta=0.5, msg=body)
                self.assertAlmostEqual(idle["shoulder_drop_cm"], 0.6, delta=0.1, msg=body)

        def test_each_op_by_itself(self) -> None:
            for body in ("men", "women"):
                ops = self.r[body]["ops"]
                turn = ops["foot_turn"]
                self.assertGreater(turn["yaw_out_before_deg"][0], 40.0)  # UAL's idle: the right foot 44 out
                self.assertAlmostEqual(turn["yaw_out_after_deg"][0], turn["yaw_out_before_deg"][0] - 40.0, delta=0.01)
                self.assertLess(turn["ankle_gap_mm_max"], 0.05)  # not round C's swivel: 68-138 mm
                self.assertLess(ops["foot_turn_heads_moved_mm"], 0.01)  # the ankle stays
                stance = ops["stance"]
                self.assertLess(stance["width_cm"][1], stance["width_cm"][0] - 15.0)
                self.assertGreater(stance["body_lift_cm"], 2.5)
                self.assertLess(stance["ankle_gap_mm_max"], 0.05)
                self.assertAlmostEqual(ops["head_level_mean_after_deg"], 0.0, delta=0.01)
                self.assertLess(ops["shoulders"]["shoulder_rise_cm"][1], ops["shoulders"]["shoulder_rise_cm"][0])
                self.assertGreater(ops["hands_relax"]["curl_before_deg"]["Middle2"][0], 60.0)  # a fist
                self.assertEqual(ops["hands_relax"]["curl_after_deg"]["Middle2"], [20.0, 20.0])
                self.assertLessEqual(ops["talk_cap_max_deg"], 30.0 + 1e-3)  # 1.5 x Middle2's 20 (float32)

        def test_the_women_arm_offset_on_the_relaxed_hands(self) -> None:
            auto = self.r["women"]["arm_auto"]
            self.assertTrue(auto["found"])
            self.assertLessEqual(auto["hands_in_legs_after_cm"], 0.0)
            self.assertEqual(self.r["women"]["idle"]["hands_in_legs_cm"], 0.0)  # the pinned angle keeps them out

        def test_idle_ends(self) -> None:
            for body in ("men", "women"):
                for clip, end in (("Jump_Start", "start"), ("Jump_Land", "end")):
                    t = self.r[body]["ends"][clip]
                    after = t["touching"][end]["after"]
                    for s in "LR":
                        self.assertLess(after[f"foot_{s}_cm"], 0.01, (body, clip))
                        self.assertLess(after[f"foot_{s}_deg"], 0.05, (body, clip))
                    self.assertLess(after["fingers_max_deg"], 0.05, (body, clip))  # the idle's curl
                    before = t["touching"][end]["before"]
                    # the upper body takes the idle's own change: against the relaxed idle it stands as far as it stood
                    # from the idle before the edit (the clip's own head and arms)
                    self.assertAlmostEqual(after["upper_max_deg"], before["upper_max_deg"], delta=0.05, msg=(body, clip))
                    self.assertGreater(t["ends"][end]["R"]["turn_deg"], 30.0, (body, clip))  # the right foot turned in
                    self.assertLess(t["ankle_gap_mm_max"], 15.0, (body, clip))
                    self.assertLess(t["edited_ankle_gap_mm_max"], 0.05, (body, clip))
                self.assertIn("idle_ends", self.r[body]["errors"]["loop"])
                self.assertIn("not built yet", self.r[body]["errors"]["unbuilt"])


def _blender_main(argv: list[str]) -> None:
    """Inside Blender: the relaxed idle on both bodies' pack originals, numbers to relax.json."""
    import math
    import os

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
    import anim_edit as ae
    import anim_libs
    import anim_set
    import anim_set_cfg as asc
    import retarget_core as rc
    import retarget_map

    out_dir, ual, men, women = argv
    mvp = asc.clips(anim_set.load_set("anim_sets/mvp.toml"))
    res = {}

    def setup(path, names):
        rc.new_scene()
        bmap = retarget_map.load()
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

    def steps_of(name, body):
        return [s for s in mvp[name]["edits"] if s.get("body", body) == body]

    for body, path in (("men", men), ("women", women)):
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        char, acts = setup(path, ["Idle_Loop", "Idle_Talking_Loop", "Jump_Start", "Jump_Land"])
        target = ae.Target(char)
        target.measure  # noqa: B018 (in the rest pose)
        rig = target.rig
        raw, _ = anim_set.close_open_loop(ae.Frames.from_action(acts["Idle_Loop"], rig, True))
        r = res[body] = {}

        # the MVP's own steps (the women's arm offsets included)
        idle = ae.apply(raw, steps_of("Idle_Loop", body), target, body)
        poses = idle.poses()
        heads = [[rig.W @ P[n].translation for n in rig.order] for P in poses]
        feet = {s: [rig.W @ P[f"Foot.{s}"].translation for P in poses] for s in "LR"}
        rep = {s["op"]: s for s in idle.info["steps"] if "skipped" not in s}
        r["idle"] = {
            "feet": ae.feet_numbers(idle),
            "feet_travel_mm": 1000 * max((p - pts[0]).length for pts in feet.values() for p in pts),
            "seam_mm": 1000 * max((a - b).length for a, b in zip(heads[0], heads[-1])),
            "pops": rc.pops(rig, poses, True),
            "head_pitch_deg": rep["head_level"]["pitch_after_deg"],
            "middle2_deg": math.degrees(idle.basis[0]["Middle2.R"].to_quaternion().angle),
            "thumb_turn_deg": rep["thumb_in"]["L"]["turn_deg"],
            "shoulder_drop_cm": rep["shoulders"]["shoulder_rise_cm"][0] - rep["shoulders"]["shoulder_rise_cm"][1],
            "hands_in_legs_cm": max(ae._Arms(idle, target, "forward").measure(k, 0.0, "legs")["depth"]
                                    for k in range(0, len(idle.basis), 3)) * 100,
        }
        rc.reset_pose(target.arm)

        # each op by itself on the raw idle
        ops = r["ops"] = {}
        turned = ae.apply(raw, [{"op": "foot_turn", "bone": "Foot.R", "toe_in_deg": 40.0}], target, body)
        ops["foot_turn"] = turned.info["steps"][0]
        ops["foot_turn_heads_moved_mm"] = 1000 * max(
            (rig.W @ a["Foot.R"].translation - rig.W @ b["Foot.R"].translation).length
            for a, b in zip(raw.poses(), turned.poses()))
        ops["stance"] = ae.apply(raw, [{"op": "stance"}], target, body).info["steps"][0]
        ops["shoulders"] = ae.apply(raw, [{"op": "shoulders", "drop_deg": 6.0}], target, body).info["steps"][0]
        level = ae.apply(raw, [{"op": "head_level"}], target, body)
        pitches = [ae._head_pitch(ae._Pose(rig, B)) for B in level.basis]
        ops["head_level_mean_after_deg"] = sum(pitches) / len(pitches)
        curl = next(s for s in mvp["Idle_Loop"]["edits"] if s["op"] == "hands_relax")["curl_deg"]
        ops["hands_relax"] = ae.apply(raw, [{"op": "hands_relax", "curl_deg": curl}], target, body).info["steps"][0]
        talk, _ = anim_set.close_open_loop(ae.Frames.from_action(acts["Idle_Talking_Loop"], rig, True))
        capped = ae.apply(talk, [{"op": "hands_relax", "curl_deg": curl, "cap": 1.5}], target, body)
        ops["talk_cap_max_deg"] = max(math.degrees(B["Middle2.L"].to_quaternion().angle) for B in capped.basis)

        # the women's arm offset re-checked on the relaxed hands: the steps up to the hands, then auto
        if body == "women":
            steps = steps_of("Idle_Loop", body)
            k = max(i for i, s in enumerate(steps) if s["op"] == "arm_offset")
            probe = ae.apply(raw, [s for i, s in enumerate(steps) if i != k]
                             + [{"op": "arm_offset", "abduct_deg": "auto"}], target, body)
            r["arm_auto"] = probe.info["steps"][-1]

        # idle_ends on the jump: the take-off starts in the idle, the landing ends in it
        target.clips = {"Idle_Loop": idle}
        ends = r["ends"] = {}
        legs = ae._Legs(rig)
        for clip, end in (("Jump_Start", "start"), ("Jump_Land", "end")):
            fr = ae.Frames.from_action(acts[clip], rig, False)
            fr = ae.apply(fr, [s for s in mvp[clip]["edits"] if s["op"] != "idle_ends"], target, body)
            done = ae.apply(fr, [{"op": "idle_ends", "at": end, "from_clip": "Idle_Loop"}], target, body)
            rep = done.info["steps"][-1]
            plan = rep["ends"][end]
            edited = [f for f in range(done.frames + 1)
                      if any(plan[s]["mode"] in ("planted", "held") or (plan[s].get("window") and min(plan[s]["window"])
                             <= f <= max(plan[s]["window"])) for s in "LR")]
            gaps = [max(ae._ankle_gap(legs, ae._Pose(rig, done.basis[f]), leg) for leg in ae.LEGS) for f in edited]
            ends[clip] = {**rep, "edited_ankle_gap_mm_max": 1000 * max(gaps, default=0.0)}
        errors = r["errors"] = {}
        for key, fr, tgt_clips in (("loop", raw, {"Idle_Loop": idle}), ("unbuilt", fr, {})):
            target.clips = tgt_clips
            try:
                ae.apply(fr, [{"op": "idle_ends", "at": "start", "from_clip": "Idle_Loop"}], target, body)
                errors[key] = "no error"
            except ae.EditError as e:
                errors[key] = str(e)

    with open(os.path.join(out_dir, "relax.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, default=str)


if IN_BLENDER and __name__ == "__main__":
    _blender_main(sys.argv[sys.argv.index("--") + 1:])
elif __name__ == "__main__":
    unittest.main()
