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


class Settings(unittest.TestCase):
    def test_every_clip_reads(self):
        for clip in ("Idle_Loop", "Walk_Loop", "Jump_Air_Loop", "Jump_Start"):
            cfg = E.settings(str(SETTINGS), clip)
            self.assertTrue(set(cfg) <= set(E.KEYS))
        self.assertFalse(E.settings(str(SETTINGS), "Jump_Air_Loop")["floor"])
        self.assertEqual(E.settings(str(SETTINGS), "Idle_Loop")["abduct_deg"], 6.0)


if __name__ == "__main__":
    unittest.main()
