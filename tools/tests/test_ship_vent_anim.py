"""The throat vent's animation controller (art #263, vents-anim1; docs/ship.md "Station 1", "The animation"): the
constants at the top of `godot/ship/vent_anim.gd` keep the blades in their safe range (vents-b2: the first cut 46.4
deg from calm, so + / - 20 deg; the top blade never above calm, its crest under the header sill), the calm pose is the
builder's (`ship_interior_vent.CLOSED_DEG`), the timings are the brief's (a breath every 3-4 s, the slam 0.12-0.2 s)
and the runner offers `--vent-anim`. Pure Python: reads the script as text (the clip itself: `ship --motion DIR`)."""

from __future__ import annotations

import ast
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
sys.path.insert(0, str(ROOT / "tools"))

import ship_interior_vent as v  # noqa: E402

SCRIPT = ROOT / "godot" / "ship" / "vent_anim.gd"
SAFE_DEG = 20.0


def consts() -> dict:
    out = {}
    for m in re.finditer(r"^const (\w+) := (.+?)(?:\s+#.*)?$", SCRIPT.read_text(encoding="utf-8"), re.M):
        try:
            out[m.group(1)] = ast.literal_eval(m.group(2).strip())
        except (ValueError, SyntaxError):
            pass
    return out


class VentAnimTest(unittest.TestCase):
    def setUp(self) -> None:
        self.c = consts()

    def test_calm_is_the_builders(self) -> None:
        self.assertEqual(self.c["CALM_DEG"], v.CLOSED_DEG)
        self.assertEqual(self.c["SLATS"], v.SLATS)

    def test_blades_within_the_safe_range(self) -> None:
        c = self.c
        kicks = [k[1] for k in c["COUGH"]]
        self.assertLessEqual(max(kicks), SAFE_DEG)
        self.assertGreaterEqual(c["CALM_DEG"] - c["BREATH_DEG"], 0.0)   # a breath never closes past shut
        self.assertLessEqual(c["BOUNCE_DEG"] + c["TREMBLE_DEG"] * 2, c["CALM_DEG"])
        self.assertLessEqual(c["COUGH_TOP"], 0.0)                        # the top blade never rises above calm
        self.assertGreaterEqual(c["CALM_DEG"] + c["COUGH_TOP"] * max(kicks), 0.0)
        self.assertEqual(c["COUGH"][0], [0.0, 0.0])
        self.assertEqual(c["COUGH"][-1][1], 0.0)                          # ends at calm: the breath takes over
        self.assertAlmostEqual(c["COUGH"][-1][0], c["COUGH_S"])
        times = [k[0] for k in c["COUGH"]]
        self.assertEqual(times, sorted(times))

    def test_timings(self) -> None:
        c = self.c
        self.assertTrue(3.0 <= c["BREATH_PERIOD_S"] <= 4.0)
        self.assertTrue(0.12 <= c["SLAM_S"] <= 0.2)
        self.assertGreater(c["DEMO_HOLD"][1] - c["DEMO_HOLD"][0], 4.0)
        self.assertGreaterEqual(c["DEMO_PROBLEM_S"], 6.0)
        self.assertTrue(20.0 <= c["DEMO_S"] <= 25.0)

    def test_runner_offers_the_clip(self) -> None:
        from runner.commands import ship
        self.assertEqual(ship.VENT_ANIM["size"], (1280, 720))
        self.assertLessEqual(ship.VENT_ANIM["max_mb"], 15)
        self.assertEqual(ship.MOTION["seconds"], self.c["DEMO_S"])
        text = (ROOT / "tools" / "runner" / "commands" / "ship.py").read_text(encoding="utf-8")
        self.assertIn('"--vent-anim"', text)


if __name__ == "__main__":
    unittest.main()
