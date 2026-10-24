"""A3b (art #196, A3's left item): alien_lively.gd's pile-up guard and motion filter in Godot 4.7.2, headless
(godot/alien/lively_check.gd, a minimal Chest-Neck-Head rig): a clip that stops posing Neck and Head leaves the head
where a clip re-posing them every step does (no pile-up); the measured yaw rate and acceleration are the same at 30
and 120 fps and with an uneven step, and a reset_motion() before a teleport kicks nothing. Skips without Godot."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runner import common, pins  # noqa: E402
from runner.commands import _godot  # noqa: E402

HAVE_GODOT = common.tool_path(pins.GODOT_ENV, None) is not None
RATE, ACCEL = 2.0, 3.0  # lively_check.gd's


@unittest.skipUnless(HAVE_GODOT, "needs Godot")
class LivelyMotionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        code, out = _godot.godot(["--headless", "--path", str(_godot.PROJECT), "-s", "res://alien/lively_check.gd"], 120)
        line = next((ln for ln in out.splitlines() if ln.startswith("LIVELYCHK ")), None)
        if code != 0 or line is None:
            raise AssertionError(f"lively_check.gd: exit {code}\n{out[-2000:]}")
        cls.d = json.loads(line[len("LIVELYCHK "):])

    def test_a_held_clip_does_not_pile_the_turn_up(self):
        p = self.d["pileup"]
        self.assertGreater(p["reposed_yaw_deg"], 15.0)  # the head did turn toward the target
        self.assertAlmostEqual(p["held_yaw_deg"], p["reposed_yaw_deg"], delta=0.1)
        self.assertLess(p["apart_deg"], 0.1)

    def test_the_yaw_rate_is_frame_rate_free(self):
        r = self.d["rate"]
        for fps in ("30", "120"):
            self.assertAlmostEqual(r[fps], RATE, delta=0.02 * RATE, msg=fps)
        self.assertAlmostEqual(r["30"], r["120"], delta=0.01 * RATE)

    def test_the_acceleration_is_frame_rate_free(self):
        a = self.d["accel"]
        for k in ("30", "120", "uneven"):
            self.assertAlmostEqual(a[k][0], ACCEL, delta=0.03 * ACCEL, msg=k)
            self.assertLess(abs(a[k][1]) + abs(a[k][2]), 0.05, k)

    def test_a_reset_before_a_teleport_kicks_nothing(self):
        self.assertLess(self.d["accel"]["after_teleport_max"], 0.5)


if __name__ == "__main__":
    unittest.main()
