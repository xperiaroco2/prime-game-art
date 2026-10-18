"""The slice character's clips on a skeleton with its own proportions (tools/blender/slice_math.py, art #207): the 2 mm
rest guard by default, `--own-proportions` accepting any difference, the leg length and its scale, which F-curves
scale, the rest orientations' report, and the flag's way from `slice` to slice_actions.py and into HANDOFF.md.
Synthetic data; no Blender needed."""

from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path

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
        r["UpperLeg.R"] = (-0.1, 0.0, 0.94)  # the right hip joint 4 cm higher: that leg 0.94 m, the left 0.90 m
        self.assertAlmostEqual(sm.leg_length(r), 0.92)

    def test_the_ankle_height_counts_with_the_shin(self) -> None:
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

    def test_slice_actions_receives_it(self) -> None:
        """The command line slice builds parses in slice_actions.py's own parser, with and without the flag."""
        from runner.commands import slice_char

        for flag, eye in ((True, 1.6), (False, None)):
            argv = slice_char.actions_args(Path("c.blend"), Path("a.blend"), ["Idle", "Jog_Fwd"], Path("o.blend"),
                                           Path("o.json"), eye, flag)
            a = sm.arguments(argv)
            self.assertEqual((a.own_proportions, a.eye_height, a.clips), (flag, eye, "Idle,Jog_Fwd"))


class RestTurn(unittest.TestCase):
    def test_the_largest_turn_outside_the_toes(self) -> None:
        self.assertEqual(sm.rest_turn({"Hips": 1.5, "Wrist.L": 55.1, "Toe.L": 80.0}), (55.1, "Wrist.L"))
        self.assertEqual(sm.rest_turn({"Toe.L": 3.0}), (0.0, ""))


class SizeNote(unittest.TestCase):
    INFO = {"height_m": 1.806, "feet_y_m": 0.0}

    def test_the_handoff_records_the_flag_and_the_leg_scale(self) -> None:
        from runner.commands import slice_char

        report = {"own_proportions": True, "leg_m": [0.9, 0.72], "leg_scale": 0.8, "rest_max_mm": 214.0,
                  "rest_worst": "Head", "rest_turn_max_deg": 55.1, "rest_turn_worst": "Wrist.L"}
        text = slice_char.size_note(self.INFO, 1.6, report)
        for part in ("`slice --own-proportions`", "214.0 mm", "`Head`", "55.1 degrees", "`Wrist.L`",
                     "0.720 m against the donor's 0.900 m", "scaled by 0.8000"):
            self.assertIn(part, text)
        same = slice_char.size_note(self.INFO, None, {"own_proportions": False, "leg_scale": 1.0})
        self.assertIn("no `--own-proportions`; leg scale 1", same)
        self.assertEqual(slice_char.size_note(self.INFO, None), "Rest height 1.806 m, feet at +0.000 m.")


if __name__ == "__main__":
    unittest.main()
