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
        cls.code, cls.output = run_cli("ship", "--build", "--only", "ramp,skin_top,skin_belly", "--out", str(OUT))
        cls.report = json.loads((OUT / "build_report.json").read_text(encoding="utf-8"))["pieces"]

    def test_the_build_passes(self) -> None:
        self.assertEqual(self.code, 0, self.output[-2000:])
        self.assertEqual(set(self.report), {"ramp", "skin_top", "skin_belly"})
        for pid in self.report:
            self.assertTrue((OUT / f"{pid}.glb").is_file())

    def test_bounds_hold_the_numbers(self) -> None:
        """The exterior's numbers survive the build (Godot's frame (x, h, y)): the ramp as wide as the mouth and as
        long as its run, the hull's tips at the span, its belly under the slabs and its nose short of the
        ramp's foot."""
        layout = ship_layout.load()
        ramp = self.report["ramp"]["bounds"]
        run = layout["ramp"]["hinge"][1] - layout["ramp"]["foot"][1]
        self.assertAlmostEqual(ramp["max"][0] - ramp["min"][0], layout["ramp"]["width_m"], delta=0.01)
        self.assertAlmostEqual(ramp["min"][2], -run, delta=0.05)
        top, belly = self.report["skin_top"]["bounds"], self.report["skin_belly"]["bounds"]
        # rebuild B (the hull J): the tips at the span, the spine's peak 4.82, the belly 0.17 (its under-skin 0.025
        # lower) under the slabs; the nose short of the ramp's foot
        half = layout["size"]["span_max_m"] / 2
        self.assertAlmostEqual(top["max"][0], half, delta=0.05)
        self.assertAlmostEqual(-top["min"][0], half, delta=0.05)
        self.assertTrue(4.78 <= top["max"][1] <= 4.85, top["max"][1])
        self.assertTrue(0.14 <= belly["min"][1] <= 0.18, belly["min"][1])
        self.assertGreater(top["min"][2], layout["ramp"]["foot"][1])

if __name__ == "__main__":
    unittest.main()
