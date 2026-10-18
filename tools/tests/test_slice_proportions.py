"""The slice character's clips on a skeleton with its own proportions (tools/blender/slice_math.py, art #207): the 2 mm
rest guard by default, `--own-proportions` accepting any difference, the leg length and its scale, which F-curves
scale, and the flag's way from `slice` to slice_actions.py. Synthetic data; no Blender needed."""

from __future__ import annotations

import argparse
import sys
import unittest

from runner import common

sys.path.insert(0, str(common.ROOT / "tools" / "blender"))
import slice_math as sm  # noqa: E402


def rig(hips: float, thigh: float, shin: float, ankle: float) -> dict[str, tuple[float, float, float]]:
    """Rest heads of a straight-legged rig (z up): the hips at `hips`, the knees and ankles below them."""
    out = {"Root": (0.0, 0.0, 0.0), "Hips": (0.0, 0.0, hips)}
    for side, x in (("L", 0.1), ("R", -0.1)):
        top = ankle + shin + thigh
        out[f"UpperLeg.{side}"] = (x, 0.0, top)
        out[f"LowerLeg.{side}"] = (x, 0.0, ankle + shin)
        out[f"Foot.{side}"] = (x, 0.0, ankle)
        out[f"Toe.{side}"] = (x, -0.12, 0.02)
    return out


class RestCheck(unittest.TestCase):
    def test_the_2_mm_guard_is_the_default(self) -> None:
        err, worst, refusal = sm.rest_check({"Hips": 0.0015, "Head": 0.001})
        self.assertIsNone(refusal)
        self.assertEqual((round(err, 4), worst), (0.0015, "Hips"))
        err, worst, refusal = sm.rest_check({"Hips": 0.0015, "Head": 0.214})
        self.assertEqual(worst, "Head")
        self.assertIn("214.00 mm at Head", refusal)
        self.assertIn("--own-proportions", refusal)

    def test_the_toes_are_only_reported(self) -> None:
        self.assertIsNone(sm.rest_check({"Hips": 0.0, "Toe.L": 0.03, "Toe.R": 0.03})[2])

    def test_own_proportions_accepts_and_reports_any_difference(self) -> None:
        err, worst, refusal = sm.rest_check({"Hips": 0.127, "Head": 0.214}, own_proportions=True)
        self.assertIsNone(refusal)
        self.assertEqual((err, worst), (0.214, "Head"))


class LegScale(unittest.TestCase):
    def test_leg_length_is_thigh_shin_and_ankle_height(self) -> None:
        self.assertAlmostEqual(sm.leg_length(rig(0.95, 0.42, 0.40, 0.08)), 0.90)

    def test_the_scale_is_the_leg_ratio(self) -> None:
        donor = rig(0.95, 0.42, 0.40, 0.08)  # 0.90 m legs
        alien = rig(0.80, 0.33, 0.33, 0.06)  # 0.72 m legs, its own pelvis
        self.assertAlmostEqual(sm.leg_scale(alien, donor), 0.8)
        self.assertAlmostEqual(sm.leg_scale(donor, donor), 1.0)

    def test_the_legs_average_both_sides(self) -> None:
        r = rig(0.95, 0.42, 0.40, 0.08)
        r["Foot.R"] = (-0.1, 0.0, 0.10)  # the right ankle 2 cm higher: its shin 2 cm shorter, its height 2 cm more
        self.assertAlmostEqual(sm.leg_length(r), 0.90)

    def test_a_rig_without_legs_is_refused(self) -> None:
        r = rig(0.95, 0.42, 0.40, 0.08)
        del r["LowerLeg.R"]
        with self.assertRaisesRegex(ValueError, "LowerLeg.R"):
            sm.leg_length(r)

    def test_only_the_root_hips_and_object_locations_scale(self) -> None:
        self.assertTrue(sm.scales_with_legs('pose.bones["Hips"].location'))
        self.assertTrue(sm.scales_with_legs('pose.bones["Root"].location'))
        self.assertTrue(sm.scales_with_legs("location"))
        self.assertFalse(sm.scales_with_legs('pose.bones["Hips"].rotation_quaternion'))
        self.assertFalse(sm.scales_with_legs('pose.bones["Foot.L"].location'))
        self.assertFalse(sm.scales_with_legs('pose.bones["Hips.001"].location'))


class SliceFlag(unittest.TestCase):
    def test_slice_takes_own_proportions_off_by_default(self) -> None:
        from runner.commands import slice_char

        parser = argparse.ArgumentParser()
        slice_char.add_arguments(parser)
        self.assertFalse(parser.parse_args([]).own_proportions)
        self.assertTrue(parser.parse_args(["--own-proportions"]).own_proportions)

    def test_slice_actions_passes_it_on(self) -> None:
        text = (common.ROOT / "tools" / "runner" / "commands" / "slice_char.py").read_text(encoding="utf-8")
        self.assertIn('["--own-proportions"] if args.own_proportions', text)
        script = (common.ROOT / "tools" / "blender" / "slice_actions.py").read_text(encoding="utf-8")
        self.assertIn('"--own-proportions", action="store_true"', script)
        self.assertIn("slice_math.rest_check(rest, a.own_proportions)", script)


if __name__ == "__main__":
    unittest.main()
