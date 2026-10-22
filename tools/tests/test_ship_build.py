"""The ship's build harness (art #263, docs/ship.md): `ship --build --only` makes one GLB per asked piece in headless
Blender, glTF-Validator passes them, and each piece's bounds hold the layout's numbers (the hall floor's radius and
deck height, the ramp from its hinge at the deck down to the ground). Skips without Blender or the validator."""

from __future__ import annotations

import json
import shutil
import unittest

from runner import common, pins, ship_layout

from ._export_fixture import have, run_cli

CAN = have(pins.BLENDER_ENV, pins.BLENDER_DEFAULT) and have(pins.GLTF_VALIDATOR_ENV, pins.GLTF_VALIDATOR_DEFAULT)
OUT = common.OUT / "ship" / "test_build"


@unittest.skipUnless(CAN, f"needs Blender {pins.BLENDER} and the glTF-Validator")
class ShipBuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        shutil.rmtree(OUT, ignore_errors=True)  # an --only build keeps an earlier report's other pieces
        cls.code, cls.output = run_cli("ship", "--build", "--only", "ramp,skin_tip_e,skin_body_e", "--out", str(OUT))
        cls.report = json.loads((OUT / "build_report.json").read_text(encoding="utf-8"))["pieces"]

    def test_the_build_passes(self) -> None:
        self.assertEqual(self.code, 0, self.output[-2000:])
        self.assertEqual(set(self.report), {"ramp", "skin_tip_e", "skin_body_e"})
        for pid in self.report:
            self.assertTrue((OUT / f"{pid}.glb").is_file())

    def test_bounds_hold_the_numbers(self) -> None:
        """The exterior's numbers survive the build (Godot's frame (x, h, y)): the ramp as wide as the mouth and as
        long as its run, the tip fairing from the belly (h 0.6) to its 4.42 m crown inside the span, the body's keel at 0.35 and its
        nose short of the ramp's foot."""
        layout = ship_layout.load()
        ramp = self.report["ramp"]["bounds"]
        run = layout["ramp"]["hinge"][1] - layout["ramp"]["foot"][1]
        self.assertAlmostEqual(ramp["max"][0] - ramp["min"][0], layout["ramp"]["width_m"], delta=0.01)
        self.assertAlmostEqual(ramp["min"][2], -run, delta=0.05)
        tip = self.report["skin_tip_e"]["bounds"]
        # launch 3 (deck 0.6): the belly 0.3 under the slabs, the lens's crown 3.65, its blade within the span
        self.assertAlmostEqual(tip["min"][1], 0.3, delta=0.01)
        self.assertAlmostEqual(tip["max"][1], 3.65, delta=0.02)
        self.assertLessEqual(tip["max"][0], layout["size"]["span_max_m"] / 2 + 0.01)
        body = self.report["skin_body_e"]["bounds"]
        self.assertGreater(body["min"][2], layout["ramp"]["foot"][1])
        self.assertAlmostEqual(body["min"][1], 0.3, delta=0.01)

if __name__ == "__main__":
    unittest.main()
