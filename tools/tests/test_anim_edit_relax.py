"""The relaxed idle's pure math (tools/blender/anim_edit_math.py, art #49) on synthetic data: the ops' schema, the
finger curls, the stance's feet and lift, the head's pitch, the feet's yaw, the knees out, and idle_ends' weights over
a clip's frames. No Blender needed; tools/tests/test_anim_edit_relax_blender.py runs the ops on the real rig."""

from __future__ import annotations

import math
import sys
import unittest

from runner import common

sys.path.insert(0, str(common.ROOT / "tools" / "blender"))
import anim_edit_math as em  # noqa: E402

CURL = {"Index": [16, 22, 12], "Middle": [20, 26, 14], "Ring": [26, 30, 16], "Pinky": [32, 34, 18], "Thumb": [12, 12]}


class RelaxStepsTest(unittest.TestCase):
    def test_the_relaxed_idle_steps_pass(self) -> None:
        steps = [{"op": "foot_turn", "bone": "Foot.R", "toe_in_deg": 40.0}, {"op": "stance", "out_cm": 2.0},
                 {"op": "shoulders", "drop_deg": 6.0}, {"op": "head_level", "target_deg": 0.0, "neck_share": 0.4},
                 {"op": "hands_relax", "curl_deg": CURL}, {"op": "hands_relax", "curl_deg": CURL, "cap": 1.5},
                 {"op": "thumb_in", "beside": "Index3", "side_cm": 1.6, "max_deg": 40},
                 {"op": "thumb_in", "from_clip": "Idle_Loop"},
                 {"op": "idle_ends", "at": "both", "from_clip": "Idle_Loop", "fade_frames": 8, "plant_cm": 1.5}]
        self.assertEqual(em.check_steps(steps), [])
        self.assertEqual(em.from_clips(steps), ["Idle_Loop", "Idle_Loop"])

    def test_bad_relax_steps_are_named(self) -> None:
        cases = [
            ({"op": "foot_turn", "bone": "Hand.R", "toe_in_deg": 40}, "bone must be a string in"),
            ({"op": "foot_turn", "bone": "Foot.R"}, "missing 'toe_in_deg'"),
            ({"op": "shoulders"}, "missing 'drop_deg'"),
            ({"op": "stance", "keep": "wide"}, "keep must be a string in"),
            ({"op": "head_level", "neck_share": 1.4}, "neck_share must be 0 to 1"),
            ({"op": "hands_relax", "curl_deg": {"Index": [10, 20]}}, "Index: 3 angles"),
            ({"op": "hands_relax", "curl_deg": {"Toe": [1, 2, 3]}}, "unknown finger 'Toe'"),
            ({"op": "hands_relax", "curl_deg": {"Thumb": [12, 200]}}, "Thumb: 2 angles of 0 to 180"),
            ({"op": "hands_relax", "curl_deg": CURL, "cap": 0}, "cap must be > 0"),
            ({"op": "thumb_in", "from_clip": "Idle_Loop", "side_cm": 2.0}, "side_cm has no effect with from_clip"),
            ({"op": "thumb_in", "from_clip": "Idle_Loop", "frame": 3}, "frame has no effect with from_clip"),
            ({"op": "thumb_in", "frame": 1.5}, "frame must be a whole number"),
            ({"op": "idle_ends", "from_clip": "Idle_Loop"}, "missing 'at'"),
            ({"op": "idle_ends", "at": "middle", "from_clip": "Idle_Loop"}, "at must be a string in"),
            ({"op": "idle_ends", "at": "start", "from_clip": "Idle_Loop", "knees_out_full_deg": 20},
             "knees_out_full_deg must be over knees_out_from_deg"),
            ({"op": "idle_ends", "at": "start", "from_clip": "Idle_Loop", "fade_frames": 0}, "fade_frames must be > 0"),
        ]
        for step, want in cases:
            found = em.check_steps([step])
            self.assertTrue(any(want in e for e in found), (step, found))

    def test_params_fill_the_lab_defaults(self) -> None:
        p = em.params({"op": "idle_ends", "at": "end", "from_clip": "Idle_Loop"})
        self.assertEqual((p["fade_frames"], p["plant_cm"], p["step_cm"]), (8, 1.5, 4.0))
        self.assertEqual((p["knees_out_deg"], p["knees_out_from_deg"], p["knees_out_full_deg"]), (25.0, 25.0, 75.0))
        p = em.params({"op": "thumb_in"})
        self.assertEqual((p["beside"], p["side_cm"], p["max_deg"], p["frame"], p["from_clip"]),
                         ("Index3", 1.6, 40.0, 0, None))


class RelaxMathTest(unittest.TestCase):
    def test_finger_curls_and_the_cap(self) -> None:
        c = em.finger_curls(CURL)
        self.assertEqual(len(c), 14)  # 4 fingers x 3 segments, the thumb's 2
        self.assertEqual((c["Index2"], c["Middle3"], c["Pinky4"], c["Thumb3"]), (16.0, 26.0, 18.0, 12.0))
        self.assertNotIn("Index1", c)
        self.assertEqual(em.curl_goal(80.0, 20.0, None), 20.0)  # the idle: the curl
        self.assertEqual(em.curl_goal(80.0, 20.0, 1.5), 30.0)  # the talk: a fist comes down to 1.5 x the curl
        self.assertEqual(em.curl_goal(12.0, 20.0, 1.5), 12.0)  # and an open gesture stays
        self.assertEqual(em.smoothstep(-1), 0.0)
        self.assertEqual(em.smoothstep(0.5), 0.5)
        self.assertEqual(em.smoothstep(2), 1.0)

    def test_stance_feet_and_lift(self) -> None:
        hips = {"L": (0.1175, 0.0, 0.92), "R": (-0.1175, 0.0, 0.92)}
        feet = {"L": (0.24, -0.20, 0.022), "R": (-0.24, 0.25, 0.023)}  # wide and staggered
        offset = {"L": (0.001, -0.06, -0.9), "R": (-0.001, -0.06, -0.9)}
        t = em.stance_targets(hips, offset, {"L": 0.022, "R": 0.023}, 0.02)
        self.assertAlmostEqual(t["L"][0], 0.1175 + 0.001 + 0.02)
        self.assertAlmostEqual(t["R"][0], -0.1175 - 0.001 - 0.02)
        self.assertAlmostEqual(t["L"][1], -0.06)
        self.assertEqual((t["L"][2], t["R"][2]), (0.022, 0.023))  # each foot keeps its height
        lift = em.stance_lift(hips, feet, t)
        self.assertGreater(lift, 0.0)  # the narrower stance stands taller
        mean = sum(math.dist(t[s], (hips[s][0], hips[s][1], hips[s][2] + lift)) for s in "LR") / 2
        self.assertAlmostEqual(mean, sum(math.dist(feet[s], hips[s]) for s in "LR") / 2, places=9)

    def test_head_pitch_and_level(self) -> None:
        self.assertAlmostEqual(em.pitch_of((0.0, -1.0, 0.0)), 0.0)
        self.assertAlmostEqual(em.pitch_of((0.0, -1.0, -1.0)), -45.0)
        self.assertAlmostEqual(em.head_fix([-14.9, -10.5, -12.73]), 12.71, places=2)
        self.assertAlmostEqual(em.head_fix([1.0, 3.0], 5.0), 3.0)

    def test_yaw_out_is_positive_toe_out_on_both_sides(self) -> None:
        def toe(deg_ccw):  # a toe 0.1 m from the foot, turned counter-clockwise from -Y
            a = math.radians(deg_ccw)
            return (0.1 * math.sin(a), -0.1 * math.cos(a), 0.0)

        self.assertAlmostEqual(em.yaw_out((0, 0, 0), toe(0), "L"), 0.0)
        self.assertAlmostEqual(em.yaw_out((0, 0, 0), toe(30), "L"), 30.0)  # the left toe to +X: out
        self.assertAlmostEqual(em.yaw_out((0, 0, 0), toe(30), "R"), -30.0)  # the right toe to +X: in
        self.assertAlmostEqual(em.yaw_out((0, 0, 0), toe(-44), "R"), 44.0)  # UAL's idle: the right foot 44 out

    def test_knees_out_and_reach(self) -> None:
        self.assertEqual(em.knees_out(20, 25, 25, 75), 0.0)
        self.assertAlmostEqual(em.knees_out(50, 25, 25, 75), 12.5)
        self.assertEqual(em.knees_out(90, 25, 25, 75), 25.0)
        self.assertEqual(em.knees_out(90, 25, 25, 75, 0.5), 12.5)
        self.assertAlmostEqual(em.reach_lift((0, 0, 0.9), (0, 0, 0.0), 1.0), 0.1)  # straight down: 10 cm more
        self.assertAlmostEqual(em.reach_lift((0, 0, 0.9), (0.6, 0, 0.0), 1.0), 0.8 - 0.9)  # 10 cm out of reach
        self.assertEqual(em.reach_lift((0, 0, 0.9), (1.2, 0, 0.0), 1.0), 0.0)

    def test_planted_until(self) -> None:
        track = [(0.0, 0.0, 0.0)] * 5 + [(0.0, 0.01 * k, 0.0) for k in range(1, 6)]
        self.assertEqual(em.planted_until(track, 0, 1, 0.015), 5)  # 1 cm at frame 5, 2 cm at frame 6
        self.assertEqual(em.planted_until(track, 9, -1, 0.015), 8)
        self.assertEqual(em.planted_until([(0, 0, 0)] * 4, 3, -1, 0.015), 0)


def _track(frames, moves_from=None, speed=0.02):
    """A foot planted at the origin, moving along -Y from frame moves_from (None: planted all through)."""
    return [(0.0, -speed * max(0, f - moves_from) if moves_from is not None else 0.0, 0.0) for f in range(frames + 1)]


class IdleEndWeightsTest(unittest.TestCase):
    def test_a_start_whose_foot_steps_off(self) -> None:
        n = 20
        w = em.idle_end_weights(n, ("start",), {"L": _track(n), "R": _track(n, 6)}, 8, 0.015, 0.04)
        self.assertEqual(w["upper"][0], 1.0)
        self.assertEqual(w["upper"][8], 0.0)
        self.assertGreater(w["upper"][4], 0.0)
        r = w["ends"]["start"]["R"]
        self.assertEqual(r["mode"], "fade")
        self.assertEqual(r["planted_to"], 6)  # it has moved 2 cm by frame 7
        self.assertEqual(r["window"], [6, 14])
        self.assertEqual(w["feet"]["R"][6], 1.0)
        self.assertEqual(w["feet"]["R"][14], 0.0)
        # the left foot stays planted all through, and the far end meets another clip: it steps over 8 frames where
        # the right foot moves least (its first 8 frames: it has not moved yet)
        left = w["ends"]["start"]["L"]
        self.assertEqual(left["mode"], "step")
        self.assertEqual(left["window"], [0, 8])
        self.assertAlmostEqual(max(w["lift"]["L"]), 0.04, places=3)
        self.assertEqual(w["feet"]["L"][0], 1.0)
        self.assertEqual(w["feet"]["L"][8], 0.0)
        self.assertEqual(max(w["lift"]["R"]), 0.0)

    def test_both_ends_hold_a_planted_foot(self) -> None:
        n = 24
        w = em.idle_end_weights(n, ("start", "end"), {"L": _track(n), "R": _track(n)}, 8, 0.015, 0.04)
        for e in ("start", "end"):
            self.assertEqual(w["ends"][e]["L"]["mode"], "planted")
        self.assertEqual(w["feet"]["L"], [1.0] * (n + 1))
        self.assertEqual(w["upper"][0], 1.0)
        self.assertEqual(w["upper"][n], 1.0)
        self.assertEqual(w["upper"][n // 2], 0.0)
        # along the clip, the start's numbers give way to the end's
        self.assertEqual(em.end_mix(w["w"], "L", 0, n), [("start", 1.0), ("end", 0.0)])
        mid = dict(em.end_mix(w["w"], "L", n // 2, n))
        self.assertAlmostEqual(mid["start"], 0.5)
        self.assertEqual(dict(em.end_mix(w["w"], "L", n, n))["end"], 1.0)

    def test_an_end_landing_on_its_last_frames_is_held(self) -> None:
        n = 9  # a landing: the foot comes down on frame 8 and is still on frame 9
        track = [(0.0, 0.0, 0.3 - 0.0375 * f) for f in range(8)] + [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0)]
        w = em.idle_end_weights(n, ("end",), {"L": track, "R": track}, 8, 0.015, 0.04)
        self.assertEqual(w["ends"]["end"]["L"]["planted_to"], 8)
        self.assertEqual(w["ends"]["end"]["L"]["mode"], "fade")
        self.assertEqual(w["ends"]["end"]["L"]["window"], [0, 8])
        self.assertEqual(w["feet"]["L"][0], 0.0)
        short = em.idle_end_weights(2, ("end",), {"L": track[-3:], "R": track[-3:]}, 8, 0.015, 0.04)
        self.assertEqual(short["ends"]["end"]["L"]["mode"], "held")  # fewer than 2 frames left: held all through
        self.assertEqual(short["feet"]["L"], [1.0, 1.0, 1.0])


if __name__ == "__main__":
    unittest.main()
