"""The empty ship's layout (art #263, docs/ship.md): layouts/ship/ship.toml and both lanes' placements pass
`ship --check`, and the check catches what it is for (a second exit, a station outside its room, a narrow corridor, a
piece outside the hull, a low ceiling, a trunk on a plain wall spot, a blocked pass, a tip room's outer wall moved). Pure Python: needs neither Blender, Godot nor the raw files."""

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
        size = LAYOUT["size"]  # the lens blades may reach span_max_m (manager update 2, art #263)
        self.assertTrue(26.0 - 0.5 <= width <= size.get("span_max_m", 26.5) + 1e-6, width)
        self.assertTrue(14.0 - 0.5 <= length <= size.get("length_max_m", 14.5) + 1e-6, length)  # with the nozzles, no ramp
        lens = sl.lengths(LAYOUT)
        self.assertGreater(lens["nozzles"], lens["body"])
        self.assertGreater(lens["overall"], lens["nozzles"])

    def test_the_station_spots_are_the_design_docs(self) -> None:
        """5a mirrored: the vents and sockets on the hall wall at about (+-2.6, -+2.6), the breaker boards on the
        corridors' front wall at x +-5.25, the renewers' players at (+-8.8, 0), the console at (0, 1)."""
        spots = {s["id"]: s for s in LAYOUT["stations"]["spot"]}
        self.assertEqual(set(spots), {"console", "vent_e", "vent_w", "socket_e", "socket_w", "breaker_e", "breaker_w",
                                      "renewer_e", "renewer_w"})
        self.assertEqual(tuple(spots["console"]["at"]), (0.0, 1.0))
        for sx in (1, -1):
            sid = "e" if sx > 0 else "w"
            for kind, sy in (("vent", -1), ("socket", 1)):
                x, y = spots[f"{kind}_{sid}"]["at"]
                self.assertAlmostEqual(x, sx * 2.6, delta=0.1)
                self.assertAlmostEqual(y, sy * 2.6, delta=0.1)
            self.assertEqual(tuple(spots[f"breaker_{sid}"]["at"]), (sx * 5.25, -1.5))
            stand = sl.spot_stand(LAYOUT, spots[f"renewer_{sid}"])
            self.assertAlmostEqual(stand[0], sx * 8.8, places=6)

    def test_the_rooms_are_5a_mirrored(self) -> None:
        r = sl.rooms(LAYOUT)
        self.assertEqual((r["hall"]["radius"], tuple(r["hall"]["centre"])), (4.0, (0.0, 0.0)))
        for sx, sid in ((1, "e"), (-1, "w")):
            self.assertEqual((r[f"tip_{sid}"]["radius"], r[f"tip_{sid}"]["centre"][0]), (1.8, sx * 8.3))
            self.assertEqual(r[f"corridor_{sid}"]["y"], [-1.5, 1.5])

    def test_a_trunk_on_a_plain_spot_is_refused(self) -> None:
        def trunk(layout):
            layout["place"].append(["hall_trunk", [2.75, -2.75, 0.0], 45.0])
        self.assertTrue(any("vent_e: hall_trunk sticks out" in p for p in problems_after(trunk)))

    def test_a_cable_bay_on_a_breaker_wall_is_refused(self) -> None:
        def bay(layout):
            layout["place"].append(["cor_channel", [5.25, 0.0, 0.0], 0.0])
        self.assertTrue(any("breaker_e: cor_channel sticks out" in p for p in problems_after(bay)))

    def test_a_blocked_pass_is_refused(self) -> None:
        def block(layout):
            spot = next(s for s in layout["stations"]["spot"] if s["id"] == "socket_e")
            x, y = sl.spot_stand(layout, spot)
            layout["stations"]["spot"][0]["at"] = [x - 0.8, y - 0.8]
        self.assertTrue(any("socket_e: the pass behind it crosses console" in p for p in problems_after(block)))

    def test_a_tip_room_moved_out_is_refused(self) -> None:
        def move(layout):
            sl.rooms(layout)["tip_e"]["centre"] = [9.0, 0.0]
        self.assertTrue(any("tip_e: outer wall at 10.80" in p for p in problems_after(move)))

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
            layout["stations"]["spot"][0]["at"] = [0.0, 3.8]
        self.assertTrue(any("station console" in p for p in problems_after(move)))

    def test_a_wall_station_away_from_its_wall_is_refused(self) -> None:
        def move(layout):
            next(s for s in layout["stations"]["spot"] if s["id"] == "breaker_e")["at"] = [5.25, 0.0]
        self.assertTrue(any("from the wall" in p for p in problems_after(move)))

    def test_a_narrow_corridor_is_refused(self) -> None:
        def narrow(layout):
            sl.rooms(layout)["corridor_w"]["y"] = [-0.9, 0.9]
        self.assertTrue(any("wide, wants about 3" in p for p in problems_after(narrow)))

    def test_a_low_ceiling_is_refused(self) -> None:
        def low(layout):
            sl.rooms(layout)["corridor_e"]["clear_h"] = 2.0
        self.assertTrue(any("clear height" in p for p in problems_after(low)))

    def test_a_piece_outside_the_hull_is_refused(self) -> None:
        def stray(layout):
            layout["place"].append(["hatches_e", [0.0, -12.0, 0.0], 0.0])  # a piece kept inside the hull
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
        self.assertLess(min(xs), -8.5)   # into both tip rooms (r 1.8 at x +-8.3)
        self.assertGreater(max(xs), 8.5)
        plan = sl.ascii_plan(LAYOUT)
        for mark in "CVSBR=":
            self.assertIn(mark, plan)


if __name__ == "__main__":
    unittest.main()
