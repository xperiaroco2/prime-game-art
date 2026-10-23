"""The alien clip edits' pure maths (tools/blender/alien_clip_edit.py, art #196 A1) and the settings file."""
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
import alien_clip_edit as E  # noqa: E402

SETTINGS = ROOT / "tools" / "blender" / "anim_sets" / "alien.toml"


def angle(q):
    return 2.0 * math.degrees(math.acos(min(1.0, abs(q[0]))))


class CapTurn(unittest.TestCase):
    def test_caps_a_fist_and_keeps_the_axis(self):
        q = E.axis_turn((0.0, 0.0, 1.0), 80.0)
        c = E.cap_turn(q, 22.0)
        self.assertAlmostEqual(angle(c), 22.0, places=6)
        self.assertAlmostEqual(c[1], 0.0)
        self.assertAlmostEqual(c[2], 0.0)
        self.assertGreater(c[3], 0.0)

    def test_leaves_a_small_turn_and_the_negative_hemisphere(self):
        q = E.axis_turn((1.0, 2.0, 0.5), 10.0)
        self.assertEqual(E.cap_turn(q, 22.0), q)
        neg = tuple(-x for x in E.axis_turn((0.0, 1.0, 0.0), 60.0))
        self.assertAlmostEqual(angle(E.cap_turn(neg, 30.0)), 30.0, places=6)
        self.assertEqual(E.cap_turn(q, 0.0), q)

    def test_axis_turn_composes(self):
        a = E.axis_turn((0.0, 0.0, 1.0), 30.0)
        self.assertAlmostEqual(angle(E.q_mul(a, a)), 60.0, places=6)


class Lift(unittest.TestCase):
    def test_no_frame_stays_under(self):
        low = [0.01, 0.0, -0.02, -0.08, -0.03, 0.0, 0.02, 0.02, 0.02]
        lift = E.lift_profile(low)
        self.assertTrue(all(z + l >= -1e-9 for z, l in zip(low, lift)))
        self.assertEqual(E.lift_profile([0.0, 0.1, 0.2]), [0.0, 0.0, 0.0])

    def test_constant_sink_lifts_evenly(self):
        self.assertTrue(all(abs(x - 0.012) < 1e-12 for x in E.lift_profile([-0.012] * 7)))


class A2Maths(unittest.TestCase):
    def test_arm_axis_signs(self):
        # the character faces -Y, its left is +X; a hand hangs along -Z
        down = (0.0, 0.0, -1.0)
        out_left = E.q_rotate(E.axis_turn((0.0, -1.0, 0.0), 1.0 * 10.0), down)  # abduct, the left arm (sign +1)
        self.assertGreater(out_left[0], 0.15)
        out_right = E.q_rotate(E.axis_turn((0.0, -1.0, 0.0), -1.0 * 10.0), down)  # the right arm (sign -1)
        self.assertLess(out_right[0], -0.15)
        fwd = E.q_rotate(E.axis_turn((1.0, 0.0, 0.0), -12.0), down)  # swing +12: about +X by a negative angle
        self.assertLess(fwd[1], -0.2)
        face = E.q_rotate(E.axis_turn((1.0, 0.0, 0.0), -10.0), (0.0, -1.0, 0.0))  # head_up: the face (-Y) goes up
        self.assertGreater(face[2], 0.15)

    def test_loop_lift_wraps(self):
        low = [-0.03, -0.01, 0.0, 0.01, 0.0, 0.0, 0.0, -0.02, -0.03]  # the last frame is the first again
        lift = E.lift_profile(low, wrap=True)
        self.assertEqual(lift[0], lift[-1])
        self.assertTrue(all(z + l >= -1e-9 for z, l in zip(low, lift)))

    def test_cut_frames(self):
        straight = [False, False, True, True, True, False, False, False]
        self.assertEqual(E.cut_frames(straight, 3), (1, 5, 1))
        self.assertIsNone(E.cut_frames([True, False, False], 3))
        self.assertIsNone(E.cut_frames([False, True, True], 3))

    def test_two_bone_keeps_lengths_and_ankle(self):
        hip, knee, ankle = (0.1, 0.0, 0.5), (0.1, -0.35, 0.35), (0.1, 0.0, 0.05)
        new_hip = (0.1, 0.0, 0.6)
        k2 = E.two_bone(hip, knee, ankle, new_hip)
        d = lambda a, b: math.dist(a, b)  # noqa: E731
        self.assertAlmostEqual(d(k2, new_hip), d(knee, hip), places=6)
        self.assertAlmostEqual(d(k2, ankle), d(ankle, knee), places=6)
        self.assertLess(k2[1], 0.0)  # the knee stays forward


class Settings(unittest.TestCase):
    def test_every_clip_reads(self):
        for clip in ("Idle_Loop", "Walk_Loop", "Jump_Air_Loop", "Jump_Start"):
            cfg = E.settings(str(SETTINGS), clip)
            self.assertTrue(set(cfg) <= set(E.KEYS))
        self.assertFalse(E.settings(str(SETTINGS), "Jump_Air_Loop")["floor"])
        self.assertEqual(E.settings(str(SETTINGS), "Idle_Loop")["abduct_deg"], 6.0)

    def test_unlisted_clip_is_untouched_and_sprint_listed(self):
        self.assertEqual(E.settings(str(SETTINGS), "Some_Other_Clip"), {})
        self.assertEqual(E.settings(str(SETTINGS), "Sprint_Fwd_Loop")["finger_cap_deg"], 50.0)


if __name__ == "__main__":
    unittest.main()
