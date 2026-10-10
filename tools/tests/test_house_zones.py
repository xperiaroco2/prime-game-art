"""The chill zone and the photo gazebo as data (layouts/house/outdoor/zones, art #81b; tools/runner/house_zones.py):
both zones pass the plan's acceptance (pieces inside, stations at the design doc's points, the 4 m opening, the
fixtures' counts, no overlaps, a free walk to every station), and the checks catch a broken layout."""

from __future__ import annotations

import copy
import math
import unittest

from runner import house_zones as hz

ZONES = {z["name"]: z for z in hz.load_all()}


class ZoneLayoutTest(unittest.TestCase):
    def test_both_zones_are_there(self) -> None:
        self.assertEqual(set(ZONES), {"chill", "photo"})

    def test_both_zones_pass(self) -> None:
        for name, z in ZONES.items():
            with self.subTest(zone=name):
                self.assertEqual(hz.check(z), [])

    def test_stations_at_the_design_docs_points(self) -> None:
        got = {it["station"]: tuple(it["at"]) for z in ZONES.values() for it in z["items"] if it.get("station")}
        self.assertEqual(got, hz.STATIONS)

    def test_the_gazebo_opens_towards_the_zone_opening(self) -> None:
        gz = ZONES["photo"]["gazebo"]
        c0, c1 = hz.gazebo_corner(gz, 0), hz.gazebo_corner(gz, 1)
        mid = ((c0[0] + c1[0]) / 2 - gz["centre"][0], (c0[1] + c1[1]) / 2 - gz["centre"][1])
        self.assertAlmostEqual(math.degrees(math.atan2(mid[1], mid[0])), 0.0, places=3)  # due east
        self.assertGreaterEqual(hz.gazebo_opening(gz), 1.4)

    def test_the_gazebo_strands_hang_between_posts(self) -> None:
        gz = ZONES["photo"]["gazebo"]
        for it in ZONES["photo"]["items"]:
            if "gazebo_edge" in it:
                k = it["gazebo_edge"]
                self.assertNotIn(k, (0,))  # never across the entrance
                span = math.dist(hz.gazebo_corner(gz, k), hz.gazebo_corner(gz, k + 1)) - gz["post"]
                self.assertAlmostEqual(span, it["w"], places=2)

    def test_placements_cover_the_gazebo(self) -> None:
        ids = [p["id"] for p in hz.placements(ZONES["photo"])]
        self.assertEqual(ids.count("gazebo_sector"), 5)
        self.assertEqual(ids.count("gazebo_sector_open"), 1)
        self.assertEqual(ids.count("gazebo_roof_sector"), 6)

    def test_the_railing_runs_round_the_zone_and_leaves_the_opening(self) -> None:
        z = ZONES["photo"]
        pieces = hz.railing_pieces(z)
        length = sum(int(p["piece"].rsplit("_", 1)[1][:-1]) for p in pieces if p["piece"].endswith("m"))
        x0, y0, w, d = z["rect"]
        op = z["opening"]
        self.assertEqual(length, 2 * (w + d) - abs(op["to"] - op["from"]))
        for p in pieces:  # every module lies on the rectangle's edge, none inside the opening
            x, y = p["at"]
            self.assertTrue(math.isclose(x, x0) or math.isclose(x, x0 + w) or math.isclose(y, y0)
                            or math.isclose(y, y0 + d), p)
            if p["piece"].endswith("m") and math.isclose(x, op["at"]):
                ux, uy = hz.turn(1.0, 0.0, p["yaw"])
                ends = sorted((y, y + uy * int(p["piece"].rsplit("_", 1)[1][:-1])))
                self.assertTrue(ends[1] <= op["from"] + 1e-6 or ends[0] >= op["to"] - 1e-6, p)
        posts = [p for p in pieces if p["piece"].endswith("_post")]
        self.assertEqual(len(posts), 1)  # the opening's north side; the south side's run ends on a corner
        placed = [p for p in hz.placements(z) if p["id"].startswith("railing_gazebo")]
        self.assertEqual(len(placed), len(pieces))


class ZoneChecksCatchTest(unittest.TestCase):
    def _item(self, z, pid):
        return next(it for it in z["items"] if it["id"] == pid)

    def test_a_moved_station(self) -> None:
        z = copy.deepcopy(ZONES["chill"])
        self._item(z, "bbq_grill")["at"] = [9.0, 50.0]
        self.assertTrue(any("station Grill" in p for p in hz.check(z)))

    def test_a_piece_outside_the_zone(self) -> None:
        z = copy.deepcopy(ZONES["chill"])
        self._item(z, "fire_pit")["at"] = [1.0, 54.5]
        self.assertTrue(any("outside the zone" in p for p in hz.check(z)))

    def test_an_overlap(self) -> None:
        z = copy.deepcopy(ZONES["chill"])
        self._item(z, "cooler_box")["at"] = [6.5, 54.5]
        self.assertTrue(any("overlap" in p for p in hz.check(z)))

    def test_a_narrow_opening(self) -> None:
        z = copy.deepcopy(ZONES["photo"])
        z["opening"]["to"] = 12.0
        self.assertTrue(any("the opening is" in p for p in hz.check(z)))

    def test_a_blocked_walk(self) -> None:
        z = copy.deepcopy(ZONES["photo"])
        z["opening"]["from"], z["opening"]["to"] = 9.0, 9.0  # the railing closes the zone
        self.assertTrue(any("no free walk" in p for p in hz.check(z)))


if __name__ == "__main__":
    unittest.main()
