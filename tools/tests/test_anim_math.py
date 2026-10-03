"""The animation measures in tools/blender/anim_math.py, on synthetic data; no Blender needed."""

from __future__ import annotations

import math
import sys
import unittest

from runner import common

sys.path.insert(0, str(common.ROOT / "tools" / "blender"))
import anim_math as am  # noqa: E402

FPS = 30


def planted_then_lifted(speed: float, frames: int = 30, x0: float = 0.0) -> list[tuple[float, float, float]]:
    """A foot moving back at `speed` m/s on the floor for the first half, then lifted 10 cm."""
    return [(x0, -speed * i / FPS, 0.02 if i < frames // 2 else 0.12) for i in range(frames)]


def qmul(a, b):
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return (w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2, w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2, w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2)


def about(axis, degrees):
    h = math.radians(degrees) / 2
    return (math.cos(h), *(math.sin(h) * c for c in axis))


class FootSlidingTest(unittest.TestCase):
    def test_a_planted_foot_does_not_slide(self) -> None:
        r = am.foot_sliding({"L": planted_then_lifted(0.0), "R": planted_then_lifted(0.0, x0=0.2)}, FPS)
        self.assertEqual(r["raw_max_cm_s"], 0.0)
        self.assertEqual(r["slide_max_cm_s"], 0.0)
        self.assertGreater(r["contact_frames"], 20)

    def test_an_in_place_walk_moves_the_ground_not_the_feet(self) -> None:
        r = am.foot_sliding({"L": planted_then_lifted(1.2), "R": planted_then_lifted(1.2, x0=0.2)}, FPS)
        self.assertAlmostEqual(r["ground_speed_cm_s"], 120.0, places=0)
        self.assertAlmostEqual(r["raw_mean_cm_s"], 120.0, places=0)
        self.assertLess(r["slide_max_cm_s"], 0.5)

    def test_a_skating_foot_slides(self) -> None:
        skate = [(0.0, 0.3 * math.sin(i / 3), 0.02) for i in range(30)]
        r = am.foot_sliding({"L": skate, "R": planted_then_lifted(0.0, x0=0.2)}, FPS)
        self.assertGreater(r["slide_max_cm_s"], 200.0)

    def test_a_foot_high_above_its_lowest_point_is_not_in_contact(self) -> None:
        swing = [(0.0, i * 0.1, 0.02 if i == 0 else 0.5) for i in range(10)]
        r = am.foot_sliding({"L": swing}, FPS)
        self.assertEqual(r["contact_frames"], 1)
        self.assertIsNone(r["slide_max_cm_s"])


class AngleTest(unittest.TestCase):
    def test_quat_angle(self) -> None:
        q = about((1, 0, 0), 30)
        self.assertAlmostEqual(am.quat_angle((1, 0, 0, 0), q), 30.0, places=6)
        self.assertAlmostEqual(am.quat_angle(q, tuple(-c for c in q)), 0.0, places=6)

    def test_twist_ignores_swing(self) -> None:
        q = qmul(about((1, 0, 0), 30), about((0, 1, 0), 40))
        self.assertAlmostEqual(am.twist_angle(q, (0.0, 1.0, 0.0)), 40.0, places=6)
        self.assertAlmostEqual(am.twist_angle(about((0, 1, 0), 40), (0.0, -1.0, 0.0)), -40.0, places=6)

    def test_signed_angle_and_hyperextension(self) -> None:
        down, back = (0.0, 0.0, -1.0), (0.0, math.sin(0.5), -math.cos(0.5))
        self.assertAlmostEqual(am.signed_angle(down, back, (1.0, 0.0, 0.0)), math.degrees(0.5), places=6)
        self.assertAlmostEqual(am.signed_angle(back, down, (1.0, 0.0, 0.0)), -math.degrees(0.5), places=6)
        self.assertEqual(am.hyperextension([30.0, 2.0, -7.25]), 7.2)
        self.assertEqual(am.hyperextension([5.0, 40.0]), 0.0)

    def test_loop_seam(self) -> None:
        first = {"a": (1.0, 0.0, 0.0, 0.0)}
        last = {"a": about((1, 0, 0), 10)}
        r = am.loop_seam(first, last, [2.0, 2.0, 3.0])
        self.assertEqual(r["seam_deg"], 10.0)
        self.assertEqual(r["seam_ratio"], 5.0)
        self.assertIsNone(am.loop_seam(first, first, [])["seam_ratio"])


if __name__ == "__main__":
    unittest.main()
