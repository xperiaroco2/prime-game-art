"""The floor settle (anim_edit_math.settle_profile, `floor {mode = "settle"}`, art #33): a clip that floats above the
floor is brought down onto it, frame by frame, and no frame goes under it. Pure Python; no Blender needed."""

from __future__ import annotations

import math
import sys
import unittest

from runner import common

sys.path.insert(0, str(common.ROOT / "tools" / "blender"))
import anim_edit_math as em  # noqa: E402


class SettleTest(unittest.TestCase):
    def test_a_floating_clip_comes_down_and_never_under_the_floor(self) -> None:
        heights = [0.05 + 0.03 * math.sin(k / 3.0) for k in range(40)]  # 2 to 8 cm up
        drop = em.settle_profile(heights, 0, 39, 6)
        after = [h - d for h, d in zip(heights, drop)]
        self.assertGreaterEqual(min(after), -1e-12)
        self.assertLess(min(after), 0.005)  # down onto the floor where it was lowest
        self.assertLess(max(after), 0.03)  # and the rest follows within the smoothing

    def test_frames_on_or_under_the_floor_stay(self) -> None:
        heights = [0.04] * 10 + [-0.01] * 5 + [0.04] * 10
        drop = em.settle_profile(heights, 0, 24, 6)
        self.assertTrue(all(d >= 0 for d in drop))
        self.assertEqual(drop[12], 0.0)
        self.assertAlmostEqual(drop[0], 0.04)

    def test_the_window_fades_out(self) -> None:
        drop = em.settle_profile([0.05] * 30, 10, 19, 4)
        self.assertEqual(drop[0], 0.0)
        self.assertAlmostEqual(drop[15], 0.05)
        self.assertTrue(0.0 < drop[8] < 0.05)

    def test_the_step_schema_takes_settle(self) -> None:
        self.assertEqual(em.check_steps([{"op": "floor", "mode": "settle"}]), [])
        self.assertTrue(em.check_steps([{"op": "floor", "mode": "sink"}]))


if __name__ == "__main__":
    unittest.main()
