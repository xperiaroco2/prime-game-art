"""The ship in the lobby (art #356; docs/ship.md "The export"): the clearing the lobby leaves out is exactly the
pieces round the ship (ship_layout.CLEARING_BUILDERS) and the lamp groups that light only them, nothing of the ship
itself; `ship --export`'s check refuses a Clearing node that differs; the closed nose's blockout variants
(exterior.toml [closed_nose.<name>]) stay in front of the mouth and on known metals. Pure Python."""

from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

from runner import ship_layout as sl
from runner.commands import _ship_export

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import ship_hull  # noqa: E402,F401  (imports every exterior module in its order)
import ship_hull_clearing as C  # noqa: E402

LAYOUT = sl.load()
CLEARING = set(sl.clearing_ids(LAYOUT))
SHIP_OWN = ("skin_", "jaw_", "leg_", "mouth_tunnel", "hazard_stripes", "edge_light", "canopy_", "nozzle_pod",
            "pod_ring", "landing_lamp", "nav_")
SHIP_LAMPS = ("land", "edge", "rim", "key", "nav_tail", "flank", "hall", "corr", "tip", "shop")


class ShipLobbyClearingTest(unittest.TestCase):
    def test_every_clearing_builder_is_listed(self) -> None:
        builders = {n for n, f in inspect.getmembers(C, inspect.isfunction)
                    if f.__module__ == C.__name__ and not n.startswith("_")
                    and list(inspect.signature(f).parameters) == ["args", "layout"]}
        self.assertTrue(builders, "ship_hull_clearing defines its builders")
        self.assertLessEqual(builders, sl.CLEARING_BUILDERS)

    def test_the_clearing_is_outside_grounded_and_collides_with_nothing(self) -> None:
        for p in LAYOUT["pieces"]:
            if p["id"] in CLEARING:
                self.assertEqual(p["lane"], "exterior", p["id"])
                self.assertTrue(p["outside"] and p.get("grounded"), p["id"])
                self.assertFalse(p["collide"], p["id"])

    def test_nothing_of_the_ship_is_in_the_clearing(self) -> None:
        self.assertIn("ground", CLEARING)
        self.assertIn("ground_lamp", CLEARING)
        self.assertIn("party_lights", CLEARING)
        for pid in CLEARING:
            self.assertFalse(pid.startswith(SHIP_OWN), pid)
        for p in LAYOUT["pieces"]:
            if p["collide"]:
                self.assertNotIn(p["id"], CLEARING, "a colliding piece is the ship's")

    def test_the_clearing_lamps_light_only_the_clearing(self) -> None:
        poly = sl.outline(LAYOUT)
        self.assertFalse(sl.CLEARING_LAMPS & set(SHIP_LAMPS))
        rows = [lamp for lamp in LAYOUT["light"]["lamps"] if len(lamp) > 8 and lamp[8] in sl.CLEARING_LAMPS]
        self.assertGreater(len(rows), 20)
        for x, y, h, *_rest in rows:
            self.assertTrue(h <= 0.35 or not sl.inside(poly, (x, y)), f"a clearing lamp at ({x}, {y}, {h})")

    def test_the_export_check_refuses_a_wrong_clearing(self) -> None:
        clear = [pid for pid, _at, _yaw in LAYOUT["place"] if pid in CLEARING]
        nose = ("jaw_lower", "jaw_upper", "jaw_root")   # under Ship/Nose (art #263 b4), not Pieces
        ship = [pid for pid, _at, _yaw in LAYOUT["place"] if pid not in CLEARING and pid not in nose]
        good = {"clearing_ids": clear, "ship_ids": ship, "clearing_ground": True}
        self.assertEqual(_ship_export.clearing_problems(LAYOUT, good), [])
        moved = {**good, "clearing_ids": clear[1:], "ship_ids": ship + clear[:1]}
        self.assertEqual(len(_ship_export.clearing_problems(LAYOUT, moved)), 3)
        lost = {**good, "ship_ids": ship[1:] + ["jaw_lower"]}   # Pieces exactly the other placements
        self.assertEqual(len(_ship_export.clearing_problems(LAYOUT, lost)), 1)
        wrong = {**good, "clearing_ids": clear + ["ramp"], "clearing_ground": False}
        self.assertEqual(len(_ship_export.clearing_problems(LAYOUT, wrong)), 3)


if __name__ == "__main__":
    unittest.main()
