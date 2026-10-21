"""The empty ship's layout (art #263, docs/ship.md): layouts/ship/ship.toml and both lanes' placements pass
`ship --check`, and the check catches what it is for (a second exit, a station outside its room, a narrow corridor, a
piece outside the hull, a low ceiling). Pure Python: needs neither Blender, Godot nor the raw files."""

from __future__ import annotations

import copy
import unittest

from runner import ship_layout as sl
from runner.commands import ship as ship_cmd

LAYOUT = sl.load()


def problems_after(change) -> list[str]:
    layout = copy.deepcopy(LAYOUT)
    change(layout)
    return sl.check(layout)


class ShipLayoutTest(unittest.TestCase):
    def test_the_layout_is_clean(self) -> None:
        self.assertEqual(sl.check(LAYOUT), [])

    def test_the_footprint_is_about_26_by_14(self) -> None:
        width, length = sl.extent(LAYOUT)
        self.assertAlmostEqual(width, 26.0, delta=0.5)
        self.assertAlmostEqual(length, 14.0, delta=0.5)

    def test_the_station_spots_are_the_design_docs(self) -> None:
        spots = {s["id"]: tuple(s["at"]) for s in LAYOUT["stations"]["spot"]}
        self.assertEqual(spots, {"console": (0, 1), "vent_w": (-5, -1), "socket_w": (-8, -1), "panel": (-10.5, 0),
                                 "vent_e": (5, -1), "socket_e": (8, -1), "renewer": (12, 0)})

    def test_a_second_exit_is_refused(self) -> None:
        def side_hatch(layout):
            sl.rooms(layout)["corridor_e"]["exit"] = "hatch"
        self.assertTrue(any("exactly one" in p for p in problems_after(side_hatch)))

    def test_a_window_exit_is_refused(self) -> None:
        def window_exit(layout):
            sl.rooms(layout)["tip_w"]["window"]["exit"] = True
        self.assertTrue(any("glass, not an exit" in p for p in problems_after(window_exit)))

    def test_a_station_outside_its_room_is_refused(self) -> None:
        def move(layout):
            layout["stations"]["spot"][0]["at"] = [0.0, 3.3]
        self.assertTrue(any("station console" in p for p in problems_after(move)))

    def test_a_wall_station_away_from_its_wall_is_refused(self) -> None:
        def move(layout):
            next(s for s in layout["stations"]["spot"] if s["id"] == "vent_e")["at"] = [5.0, 0.0]
        self.assertTrue(any("from a wall" in p for p in problems_after(move)))

    def test_a_narrow_corridor_is_refused(self) -> None:
        def narrow(layout):
            sl.rooms(layout)["corridor_w"]["y"] = [-0.9, 0.9]
        self.assertTrue(any("wide, wants about 2.5" in p for p in problems_after(narrow)))

    def test_a_low_ceiling_is_refused(self) -> None:
        def low(layout):
            sl.rooms(layout)["corridor_e"]["clear_h"] = 2.0
        self.assertTrue(any("clear height" in p for p in problems_after(low)))

    def test_a_piece_outside_the_hull_is_refused(self) -> None:
        def stray(layout):
            layout["place"].append(["leg", [0.0, -12.0, 0.0], 0.0])
        self.assertTrue(any("stands outside the hull" in p for p in problems_after(stray)))

    def test_lanes_do_not_share_pieces(self) -> None:
        lanes = {}
        for p in LAYOUT["pieces"]:
            self.assertNotIn(p["id"], lanes, p["id"])
            lanes[p["id"]] = p["lane"]
        self.assertEqual(set(lanes.values()), {"interior", "exterior"})

    def test_the_walk_and_plan(self) -> None:
        walk = ship_cmd.walk_request(LAYOUT)
        self.assertEqual(walk["points"][0], walk["points"][-1])
        xs = [p[0] for p in walk["points"]]
        self.assertLess(min(xs), -10.0)
        self.assertGreater(max(xs), 10.0)
        plan = sl.ascii_plan(LAYOUT)
        for mark in "CVSPR=":
            self.assertIn(mark, plan)


if __name__ == "__main__":
    unittest.main()
