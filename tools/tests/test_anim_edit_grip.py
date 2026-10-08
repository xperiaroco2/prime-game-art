"""The side grip (`side_grip {gap_m, tilt_deg, forearm_share, from_s, fade_s}`, art #65): its schema and its pure
math (the palm's normal, the roll that points it at the other hand, the grip's weights, the secant search). The edit
itself runs in Blender (the MVP's Carry_Upper_Loop and Pickup_Package). Pure Python; no Blender needed."""

from __future__ import annotations

import math
import sys
import unittest

from runner import common

sys.path.insert(0, str(common.ROOT / "tools" / "blender"))
import anim_edit_math as em  # noqa: E402
import anim_set_cfg  # noqa: E402


def close(test: unittest.TestCase, a, b, places: int = 6) -> None:
    for x, y in zip(a, b):
        test.assertAlmostEqual(x, y, places=places)


class SideGripSchemaTest(unittest.TestCase):
    def test_the_schema_takes_a_grip(self) -> None:
        self.assertEqual(em.check_steps([{"op": "side_grip", "gap_m": 0.45}]), [])
        self.assertEqual(em.check_steps([{"op": "side_grip", "gap_m": 0.45, "tilt_deg": -10, "forearm_share": 1,
                                          "from_s": 0.4, "fade_s": 0.2, "body": "women"}]), [])
        self.assertEqual(em.params({"op": "side_grip", "gap_m": 0.45}),
                         {"gap_m": 0.45, "tilt_deg": 0.0, "forearm_share": 0.5, "from_s": 0.0, "fade_s": 0.0,
                          "max_deg": 40.0, "tol_cm": 0.3})

    def test_bad_grips_are_named(self) -> None:
        self.assertTrue(any("missing 'gap_m'" in e for e in em.check_steps([{"op": "side_grip"}])))
        self.assertTrue(any("> 0" in e for e in em.check_steps([{"op": "side_grip", "gap_m": 0}])))
        self.assertTrue(any("forearm_share" in e for e in
                            em.check_steps([{"op": "side_grip", "gap_m": 0.45, "forearm_share": 1.5}])))
        self.assertTrue(any("tilt_deg" in e for e in em.check_steps([{"op": "side_grip", "gap_m": 0.45,
                                                                      "tilt_deg": 90}])))
        self.assertTrue(em.check_steps([{"op": "side_grip", "gap_m": 0.45, "from_s": -1}]))
        self.assertTrue(em.check_steps([{"op": "side_grip", "gap_m": 0.45, "grip": 1}]))

    def test_the_mvp_package_clips_grip_the_sides(self) -> None:
        cfg = anim_set_cfg.load(common.ROOT / "tools" / "blender" / "anim_sets" / "mvp.toml")
        clips = {c["name"]: c for c in cfg["clips"]}
        for name in ("Carry_Upper_Loop", "Pickup_Package"):
            grips = [s for s in clips[name]["edits"] if s["op"] == "side_grip"]
            self.assertEqual(len(grips), 1, name)
            self.assertEqual(grips[0]["gap_m"], 0.45, name)
            self.assertFalse([s for s in clips[name]["edits"] if s["op"] == "hand_spacing"], name)


class PalmTest(unittest.TestCase):
    def test_palms_down_point_down_on_both_hands(self) -> None:
        # front -Y, left +X: a left hand palm down has its index knuckle inwards (-X) and its pinky out (+X)
        left = em.palm_normal((0.2, 0, 1), (0.2, -0.1, 1), (0.18, -0.09, 1), (0.23, -0.08, 1), "L")
        right = em.palm_normal((-0.2, 0, 1), (-0.2, -0.1, 1), (-0.18, -0.09, 1), (-0.23, -0.08, 1), "R")
        close(self, left, (0, 0, -1))
        close(self, right, (0, 0, -1))

    def test_palms_up_point_up(self) -> None:
        # turned palm up the index knuckle goes out (+X on the left hand)
        left = em.palm_normal((0.2, 0, 1), (0.2, -0.1, 1), (0.22, -0.09, 1), (0.17, -0.08, 1), "L")
        close(self, left, (0, 0, 1))

    def test_the_goal_is_horizontal_towards_the_other_hand_and_tilts_up(self) -> None:
        close(self, em.grip_goal((-0.4, 0.0, 0.05)), (-1, 0, 0))
        g = em.grip_goal((0.0, 3.0, -1.0), 30)
        close(self, g, (0, math.cos(math.radians(30)), 0.5))


class RollTest(unittest.TestCase):
    def test_a_palm_up_left_hand_rolls_a_quarter_in(self) -> None:
        # forearm along -Y (elbow to wrist), palm up, the other hand at -X: right-handed about -Y, +Z goes to -X
        self.assertAlmostEqual(em.roll_angle((0, 0, 1), (-1, 0, 0), (0, -1, 0)), 90.0, places=6)
        # the right hand rolls the other way
        self.assertAlmostEqual(em.roll_angle((0, 0, 1), (1, 0, 0), (0, -1, 0)), -90.0, places=6)

    def test_the_roll_ignores_the_part_along_the_forearm(self) -> None:
        self.assertAlmostEqual(em.roll_angle((0, -0.5, 1), (-1, -0.7, 0), (0, -1, 0)), 90.0, places=6)
        self.assertAlmostEqual(em.roll_angle((1, 0, 0), (1, 0, 0), (0, 0, 1)), 0.0, places=6)
        self.assertEqual(em.roll_angle((0, -1, 0), (1, 0, 0), (0, -1, 0)), 0.0)


class WeightsAndSearchTest(unittest.TestCase):
    def test_the_weights_hold_from_the_start_and_fade_in(self) -> None:
        self.assertEqual(em.grip_weights(4, 30), [1.0] * 4)
        w = em.grip_weights(31, 30, from_s=0.5, fade_s=0.2)
        self.assertEqual(w[:9], [0.0] * 9)
        self.assertTrue(all(a <= b for a, b in zip(w, w[1:])))
        self.assertTrue(0.0 < w[12] < 1.0)
        self.assertEqual(w[15:], [1.0] * 16)
        self.assertEqual(em.grip_weights(3, 30, from_s=1 / 30), [0.0, 1.0, 1.0])

    def test_the_secant_finds_a_gap(self) -> None:
        calls = []

        def gap(a):
            calls.append(a)
            return 0.30 + 0.01 * a + 0.0001 * a * a

        x, y, ok = em.secant(gap, 0.45, 0.0, 2.0, 0.001, -40, 40)
        self.assertTrue(ok)
        self.assertAlmostEqual(y, 0.45, delta=0.001)
        self.assertLess(len(calls), 8)

    def test_the_secant_clamps_and_reports_a_miss(self) -> None:
        x, y, ok = em.secant(lambda a: 0.01 * a, 1.0, 0.0, 2.0, 0.001, -40, 40)
        self.assertFalse(ok)
        self.assertEqual(x, 40)
        self.assertAlmostEqual(y, 0.4)

    def test_the_spread(self) -> None:
        self.assertEqual(em.spread([2.0, 1.0, 3.0]), {"min": 1.0, "mean": 2.0, "max": 3.0})
        self.assertEqual(em.spread([]), {"min": None, "mean": None, "max": None})


if __name__ == "__main__":
    unittest.main()


class UpperMatchTest(unittest.TestCase):
    """upper_match (art #65's review): the lift's end takes the carry's upper layer, so the hands hand over."""

    def test_the_schema_takes_a_match(self) -> None:
        self.assertEqual(em.check_steps([{"op": "upper_match", "from_clip": "Carry_Upper_Loop"}]), [])
        self.assertEqual(em.params({"op": "upper_match", "from_clip": "Carry_Upper_Loop"}),
                         {"from_clip": "Carry_Upper_Loop", "frame": 0, "at": "end", "fade_s": 0.3, "base_clip": None})
        self.assertTrue(em.check_steps([{"op": "upper_match"}]))
        self.assertTrue(em.check_steps([{"op": "upper_match", "from_clip": "X", "at": "middle"}]))
        self.assertTrue(em.check_steps([{"op": "upper_match", "from_clip": "X", "frame": -1}]))
        self.assertEqual(em.from_clips([{"op": "upper_match", "from_clip": "Carry_Upper_Loop", "base_clip": "Idle_Loop"}]),
                         ["Carry_Upper_Loop", "Idle_Loop"])

    def test_the_weights_are_full_on_the_touching_frame_only(self) -> None:
        w = em.end_weights(25, 24.0, "end", 0.25)
        self.assertEqual(w[-1], 1.0)
        self.assertTrue(all(x == 0.0 for x in w[:19]))  # 6 frames or more from the end: 0.25 s and beyond
        self.assertTrue(all(0.0 < x < 1.0 for x in w[19:24]))
        self.assertEqual(w[19:], sorted(w[19:]))
        self.assertEqual(em.end_weights(25, 24.0, "start", 0.25), w[::-1])

    def test_no_fade_takes_the_touching_frame_alone(self) -> None:
        self.assertEqual(em.end_weights(4, 24.0, "end", 0.0), [0.0, 0.0, 0.0, 1.0])
        self.assertEqual(em.end_weights(4, 24.0, "start", 0.0), [1.0, 0.0, 0.0, 0.0])
