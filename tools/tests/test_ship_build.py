"""The ship's build harness (art #263, docs/ship.md): `ship --build --only` makes one GLB per asked piece in headless
Blender, glTF-Validator passes them, and each piece's bounds hold the layout's numbers (the hall floor's radius and
deck height, the ramp from its hinge at the deck down to the ground). Skips without Blender or the validator."""

from __future__ import annotations

import json
import unittest

from runner import common, pins, ship_layout

from ._export_fixture import have, run_cli

CAN = have(pins.BLENDER_ENV, pins.BLENDER_DEFAULT) and have(pins.GLTF_VALIDATOR_ENV, pins.GLTF_VALIDATOR_DEFAULT)
OUT = common.OUT / "ship" / "test_build"


@unittest.skipUnless(CAN, f"needs Blender {pins.BLENDER} and the glTF-Validator")
class ShipBuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.code, cls.output = run_cli("ship", "--build", "--only", "hall_floor,ramp,tip_wall", "--out", str(OUT))
        cls.report = json.loads((OUT / "build_report.json").read_text(encoding="utf-8"))["pieces"]

    def test_the_build_passes(self) -> None:
        self.assertEqual(self.code, 0, self.output[-2000:])
        self.assertEqual(set(self.report), {"hall_floor", "ramp", "tip_wall"})
        for pid in self.report:
            self.assertTrue((OUT / f"{pid}.glb").is_file())

    def test_bounds_hold_the_numbers(self) -> None:
        layout = ship_layout.load()
        floor, wall = layout["deck"]["floor_h"], layout["deck"]["wall_m"]
        hall = self.report["hall_floor"]["bounds"]  # Godot's frame: (x, h, y)
        r = ship_layout.rooms(layout)["hall"]["radius"] + wall
        self.assertAlmostEqual(hall["max"][0], r, delta=0.01)
        self.assertAlmostEqual(hall["max"][1], floor, delta=0.001)
        ramp = self.report["ramp"]["bounds"]
        run = layout["ramp"]["hinge"][1] - layout["ramp"]["foot"][1]
        self.assertAlmostEqual(ramp["max"][1], floor, delta=0.001)
        self.assertAlmostEqual(ramp["min"][2], -run, delta=0.001)
        tip = self.report["tip_wall"]["bounds"]
        self.assertAlmostEqual(tip["max"][1], floor + ship_layout.rooms(layout)["tip_e"]["clear_h"], delta=0.001)


if __name__ == "__main__":
    unittest.main()
