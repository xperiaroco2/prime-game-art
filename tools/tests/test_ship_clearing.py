"""The clearing round the ship (art #263, hull lane step 3; docs/ship.md "The clearing"): the dirt path runs from the
ramp's foot and stays clear of plants, logs and posts, the party string hangs over the path at head-clearing height,
every clearing placement stands on the ground's facets, and the walk's outside points stay clear. Pure Python
(tools/blender/ship_hull_clearing.py needs no Blender)."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

from runner import ship_layout as sl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import ship_hull  # noqa: E402,F401  (imports every exterior module in its order)
import ship_hull_clearing as C  # noqa: E402

LAYOUT = sl.load()
PLANTS = ("tuft", "bush", "log", "stump", "pine", "rock", "party_post")


def path_d(x: float, y: float) -> float:
    return min(math.hypot(x - p[0], y - p[1]) for p in (C.path_point(i / 300)[0] for i in range(301)))


class ShipClearingTest(unittest.TestCase):
    def test_the_path_starts_at_the_ramps_foot(self) -> None:
        (x, y), _d = C.path_point(0.0)
        self.assertAlmostEqual(x, 0.0, places=6)
        self.assertGreater(y, -10.0, "the path starts north of the ramp's foot")
        (x1, y1), _d = C.path_point(1.0)
        self.assertGreater(math.hypot(x1, y1), 35.0, "the path reaches the treeline")

    def test_the_path_is_clear(self) -> None:
        for pid, (x, y, _h), _yaw in LAYOUT["place"]:
            if pid.startswith(PLANTS):
                self.assertGreater(path_d(x, y), 0.9 if pid == "party_post" else 1.1, f"{pid} on the path at ({x}, {y})")

    def test_the_string_clears_heads_over_the_path(self) -> None:
        wire = C.party_lights({}, LAYOUT)[0]
        for x, y, h in wire["verts"]:
            if path_d(x, y) < 1.0:
                self.assertGreater(h - C.ground_h(x, y), 1.95, f"the party string hangs low at ({x:.1f}, {y:.1f})")

    def test_the_clearing_stands_on_the_ground(self) -> None:
        self.assertEqual(C.ground_h(10.0, -5.0), 0.0)
        for pid, (x, y, h), _yaw in LAYOUT["place"]:
            if pid.startswith(PLANTS):
                self.assertAlmostEqual(h, C.ground_h(x, y) if math.hypot(x, y) > 16 else 0.0, delta=0.011,
                                       msg=f"{pid} floats or sinks at ({x}, {y})")

    def test_the_walks_outside_points_are_clear(self) -> None:
        for wx, wy, wh in LAYOUT["walk"]["points"]:
            if wh > 0.0:
                continue
            for pid, (x, y, _h), _yaw in LAYOUT["place"]:
                if pid.startswith(("bush", "log", "stump", "pine", "rock", "party_post")):
                    self.assertGreater(math.hypot(x - wx, y - wy), 1.5, f"{pid} blocks the walk at ({wx}, {wy})")


if __name__ == "__main__":
    unittest.main()
