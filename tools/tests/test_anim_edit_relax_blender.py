"""The relaxed idle's clip edits (tools/blender/anim_edit.py, art #49) in headless Blender on the real rig: UAL's
Idle_Loop on the men's and women's pack originals through the MVP set's own steps (tools/blender/anim_sets/mvp.toml):
the right foot turned in to about +3.7 degrees with the ankle on its foot, the feet at hip width and planted, the
shoulders down, the head level, open hands with the thumb in, the loop closed without a pop; each op by itself on the
raw idle; the women's arm offset re-checked by its auto search on the relaxed hands; and idle_ends with the set's own
steps on the jump's take-off and landing and the raise's kneel and stand (a foot that settles, a step), and at both
ends of the raw idle played as a one-shot (planted all through, as the pickup), with and without the upper body,
turned 20 degrees as a whole (the package clips' Root) and with a foot that shuffles between the ends: the touching
frames stand exactly in the relaxed idle's first frame in the set's frame (relative to Root with match = "root"), the
ankles stay on the feet on every frame the edit weighs, no foot sinks into the floor, none slides where the clip keeps
it still, a shuffling foot is held, and the edit never lifts both feet where the clip stands.

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
                for clip, t in self.r[body]["ends"].items():
                    for end, touch in t["touching"].items():
                        after = touch["after"]
                        # the set's frame (the game's) by default; relative to Root with match = "root"
                        key = "" if t["match"] == "root" else "set_"
                        for s in "LR":
                            self.assertLess(after[f"{key}foot_{s}_cm"], 0.01, (body, clip, end))
                            self.assertLess(after[f"{key}foot_{s}_deg"], 0.05, (body, clip, end))
                        self.assertLess(after["toes_max_deg"], 0.05, (body, clip, end))  # the idle's toes
                        if t["upper"]:
                            self.assertLess(after["fingers_max_deg"], 0.05, (body, clip, end))  # the idle's curl
                            # the upper body takes the idle's own change: against the relaxed idle it stands as far
                            # as it stood from the idle before the edit (the clip's own head and arms)
                            self.assertAlmostEqual(after["upper_max_deg"], touch["before"]["upper_max_deg"],
                                                   delta=0.05, msg=(body, clip, end))
                        if not clip.startswith("Idle_turned"):
                            self.assertGreater(t["ends"][end]["R"]["turn_deg"], 30.0, (body, clip))  # turned in
                    # every frame the edit weighs keeps the ankles on the feet, no foot below its floor (its own
                    # height before the edit or the idle's standing height), none slid where the clip keeps it still
                    self.assertLess(t["edited_ankle_gap_mm_max"], 0.05, (body, clip))
                    for s in "LR":
                        self.assertLess(t["floor"][s]["below_mm_max"], 0.01, (body, clip, s))
                        self.assertLess(t["floor"][s]["slide_mm_max"], 2.0, (body, clip, s))
                    # where the clip has a foot on the floor the edit keeps one there, and lifts neither higher
                    self.assertEqual(t["air"]["airborne_frames"], [], (body, clip))
                    self.assertLess(t["air"]["hop_cm_max"], 1.0, (body, clip))
                    self.assertLess(t["foot_pulled_mm_max"], 0.05, (body, clip))  # every leg reaches its foot
                self.assertLess(self.r[body]["ends"]["Jump_Start"]["ankle_gap_mm_max"], 15.0)  # art #33's resampling
                # a foot that settles onto the floor after the touching frame is planted, not faded along the floor
                self.assertEqual(self.r[body]["ends"]["Raise_In"]["ends"]["start"]["L"]["mode"], "step", body)
                self.assertEqual(self.r[body]["ends"]["Raise_Out"]["ends"]["end"]["L"]["mode"], "step", body)
                self.assertGreater(self.r[body]["ends"]["Raise_In"]["floor"]["L"]["raised_mm_max"], 5.0, body)
                both = self.r[body]["ends"]["Idle_both"]
                self.assertEqual(both["edited_frames"], both["frames"] + 1)  # planted all through, both ends
                feet_only = self.r[body]["ends"]["Idle_both_feet"]
                self.assertFalse(feet_only["upper"])
                self.assertLess(feet_only["upper_changed_deg"], 1e-3, body)  # the arms and fingers untouched
                # a clip turned 20 degrees as a whole (the package clips' Root after art #33's heading): in the set's
                # frame its feet meet the idle's; relative to its Root they would keep the turn
                # frame its feet meet the idle's and its Root becomes the idle's (the bones under it kept: the edit's
                # own Root turn); relative to its Root they would keep the turn
                for case, key, deg, root in (("Idle_turned", "set_", 0.0, 0.0), ("Idle_turned", "", 0.0, 0.0),
                                             ("Idle_turned_root", "", 0.0, 20.0),
                                             ("Idle_turned_root", "set_", 20.0, 20.0)):
                    t = self.r[body]["ends"][case]
                    after = t["touching"]["start"]["after"]
                    self.assertAlmostEqual(t["touching"]["start"]["before"]["root_turn_deg"], 20.0, delta=0.01)
                    self.assertAlmostEqual(after["root_turn_deg"], root, delta=0.01, msg=(body, case))
                    for s in "LR":
                        self.assertAlmostEqual(after[f"{key}foot_{s}_deg"], deg, delta=0.05, msg=(body, case, key))
                turned = self.r[body]["ends"]["Idle_turned"]["reroot"]["turned_deg_max"]
                self.assertAlmostEqual(turned, 20.0, delta=0.01, msg=body)
                self.assertEqual(self.r[body]["ends"]["Idle_turned_root"]["reroot"]["turned_deg_max"], 0.0)
                # a foot that shuffles 8 cm along the floor between two ends that meet the idle is held there
                shuffle = self.r[body]["ends"]["Idle_shuffle"]
                for end in ("start", "end"):
                    self.assertEqual(shuffle["ends"][end]["R"]["mode"], "hold", body)
                    self.assertEqual(shuffle["ends"][end]["L"]["mode"], "planted", body)
                self.assertEqual(shuffle["step_lift_cm"], {"L": 0.0, "R": 0.0}, body)
                self.assertLess(shuffle["feet_travel_mm"]["R"], 0.01, body)
                self.assertEqual(self.r[body]["placed"], {"set": "idle_ends", "root": None, "reversed": "idle_ends",
                                                          "trimmed": None}, body)
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
    from mathutils import Matrix

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
        char, acts = setup(path, ["Idle_Loop", "Idle_Talking_Loop", "Jump_Start", "Jump_Land", "Fixing_Kneeling"])
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

        # idle_ends with the set's own steps: the jump's take-off starts in the idle and its landing ends in it; the
        # raise kneels down from it (a foot that settles after the touching frame, a step) and stands up into it; and
        # the raw idle played as a one-shot meets it at both ends (planted all through, as the pickup), also with the
        # feet and legs only (the package clips)
        target.clips = {"Idle_Loop": idle}
        ends = r["ends"] = {}
        legs = ae._Legs(rig)
        one_shot = ae.Frames(raw.rig, [{n: m.copy() for n, m in b.items()} for b in raw.basis], raw.fps, False, {})
        cases = [(c, ae.Frames.from_action(acts[mvp[c]["source"].split(":")[1]], rig, False), mvp[c]["edits"])
                 for c in ("Jump_Start", "Jump_Land", "Raise_In", "Raise_Out")]
        turned = one_shot.copy()  # the whole character turned 20 degrees, as the package clips' heading leaves Root
        ae._move_world(turned, [ae._about_z(ae._body_path(turned)[0], 20.0)] * len(turned.basis))
        shuffle = one_shot.copy()  # the right foot shuffles 8 cm along the floor on frames 6-11
        for f, B in enumerate(shuffle.basis):
            pose = ae._Pose(rig, B)
            pose.transform("Foot.R", Matrix.Translation((-0.016 * min(5, max(0, f - 6)), 0.0, 0.0)))
            shuffle.basis[f] = pose.B
        feet_only = {"op": "idle_ends", "at": "both", "from_clip": "Idle_Loop", "upper": False}
        cases += [("Idle_both", one_shot, [{"op": "idle_ends", "at": "both", "from_clip": "Idle_Loop"}]),
                  ("Idle_both_feet", one_shot, [feet_only]),
                  ("Idle_turned", turned, [feet_only]), ("Idle_turned_root", turned, [{**feet_only, "match": "root"}]),
                  ("Idle_shuffle", shuffle, [feet_only])]
        for clip, fr, steps in cases:
            fr = ae.apply(fr, [s for s in steps if s["op"] != "idle_ends"], target, body)
            done = ae.apply(fr, [s for s in steps if s["op"] == "idle_ends"], target, body)
            rep = done.info["steps"][-1]
            n = done.frames
            edited = set()  # every frame where either foot's weight is over 0
            for end, plan in rep["ends"].items():
                for s in "LR":
                    win = plan[s].get("window")
                    if plan[s]["mode"] in ("planted", "held", "hold"):
                        edited |= set(range(n + 1))
                    else:
                        edited |= set(range(0, max(win) + 1) if end == "start" else range(min(win), n + 1))
            gaps = [max(ae._ankle_gap(legs, ae._Pose(rig, done.basis[f]), leg) for leg in ae.LEGS) for f in edited]
            heads = {s: [rig.W @ P[f"Foot.{s}"].translation for P in done.poses()] for s in "LR"}
            ends[clip] = {**rep, "frames": n, "edited_frames": len(edited),
                          "edited_ankle_gap_mm_max": 1000 * max(gaps, default=0.0),
                          "feet_travel_mm": {s: 1000 * max((h - pts[0]).length for h in pts)
                                             for s, pts in heads.items()}}
            if not rep["upper"]:
                bones = [b for b in rig.order if b in ae.UPPER_DELTA or ae._curled(b)]
                ends[clip]["upper_changed_deg"] = max(
                    math.degrees(a[b].to_quaternion().rotation_difference(c[b].to_quaternion()).angle)
                    for a, c in zip(fr.basis, done.basis) for b in bones)
        # match = "set" places the clip in the idle's frame (the set does not recentre it); reverse and retime keep
        # that, any other later op clears it, as does match = "root"
        def placed(steps):
            fresh = ae.Frames(raw.rig, [{n: m.copy() for n, m in b.items()} for b in raw.basis], raw.fps, False, {})
            return ae.apply(fresh, steps, target, body).info.get("placed_by")

        r["placed"] = {"set": placed([feet_only]), "root": placed([{**feet_only, "match": "root"}]),
                       "reversed": placed([feet_only, {"op": "reverse"}]),
                       "trimmed": placed([feet_only, {"op": "trim", "start_s": 0.0, "end_s": 0.5}])}
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
