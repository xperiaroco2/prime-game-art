"""The empty ship's layout (art #263, docs/ship.md): layouts/ship/ship.toml and both lanes' placements pass
`ship --check`, and the check catches what it is for (a second exit, a station outside its room, a narrow corridor, a
piece outside the hull, a low ceiling, a trunk on a plain wall spot, a blocked pass, a tip room's outer wall moved). Pure Python: needs neither Blender, Godot nor the raw files."""

from __future__ import annotations

import copy
import math
import sys
from pathlib import Path
import unittest

from runner import ship_layout as sl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import ship_hull_shape as S  # noqa: E402
from runner.commands import ship as ship_cmd

LAYOUT = sl.load()


def problems_after(change) -> list[str]:
    layout = copy.deepcopy(LAYOUT)
    change(layout)
    return sl.check(layout)


class ShipLayoutTest(unittest.TestCase):
    def test_the_layout_is_clean(self) -> None:
        self.assertEqual(sl.check(LAYOUT), [])

    def test_the_footprint_is_js_30_by_18_9(self) -> None:
        width, length = sl.extent(LAYOUT)
        size = LAYOUT["size"]  # the lens blades may reach span_max_m (manager update 2, art #263)
        self.assertAlmostEqual(width, size["width_m"], delta=0.01)
        self.assertAlmostEqual(length, size["length_m"], delta=0.01)   # with the nozzles, no ramp
        lens = sl.lengths(LAYOUT)
        self.assertGreater(lens["nozzles"], lens["body"])
        self.assertGreater(lens["overall"], lens["nozzles"])

    def test_the_station_spots_are_the_design_docs(self) -> None:
        """5a mirrored: the vents on the hall wall at about (+-2.6, -2.6), the console at (0, 1). rebuild A (variant
        J): the sockets moved back off the diagonal corridors' openings to (+-1.80, 3.51), the breaker boards on the
        corridors' front wall at (+-6.03, 1.24), the renewers' players 0.5 m past the tip rooms' centres on the axis."""
        spots = {s["id"]: s for s in LAYOUT["stations"]["spot"]}
        # rebuild C: the inside 1 m forward; the vents on the throat's slanted walls (asked (+-2.3, -5.8)), four
        # sockets (the front two beside the throat, asked (+-3.5, -3.0)); each snapped onto its wall by under 0.15 m
        self.assertEqual(set(spots), {"console", "vent_e", "vent_w", "socket_e", "socket_w", "socket_fe", "socket_fw",
                                      "breaker_e", "breaker_w", "renewer_e", "renewer_w"})
        self.assertEqual(tuple(spots["console"]["at"]), (0.0, 0.0))
        for sx in (1, -1):
            sid = "e" if sx > 0 else "w"
            self.assertEqual(spots[f"vent_{sid}"]["room"], "throat")
            self.assertLess(math.dist(spots[f"vent_{sid}"]["at"], (sx * 2.3, -5.8)), 0.15)
            self.assertLess(math.dist(spots[f"socket_f{sid}"]["at"], (sx * 3.5, -3.0)), 0.15)
            self.assertEqual(tuple(spots[f"socket_{sid}"]["at"]), (sx * 1.8, 2.512))
            self.assertEqual(tuple(spots[f"breaker_{sid}"]["at"]), (sx * 6.03, 0.241))
            stand = sl.spot_stand(LAYOUT, spots[f"renewer_{sid}"])
            self.assertAlmostEqual(stand[0], sx * 8.751, places=2)
            self.assertAlmostEqual(stand[1], 3.217, places=2)

    def test_the_rooms_are_5a_mirrored(self) -> None:
        r = sl.rooms(LAYOUT)
        self.assertEqual((r["hall"]["radius"], tuple(r["hall"]["centre"])), (4.0, (0.0, -1.0)))   # rebuild C
        for sx, sid in ((1, "e"), (-1, "w")):
            self.assertEqual((r[f"tip_{sid}"]["radius"], tuple(r[f"tip_{sid}"]["centre"])), (1.8, (sx * 8.3, 3.0)))
            cor = r[f"corridor_{sid}"]   # rebuild A: straight and diagonal, hall centre to tip room centre
            self.assertEqual((cor["shape"], cor["width"]), ("strip", 3.0))
            self.assertEqual(cor["axis"], [[0.0, -1.0], r[f"tip_{sid}"]["centre"]])

    def test_the_throat_opens_at_the_nose_with_head_room_under_its_roof(self) -> None:
        """rebuild C: the throat from the mouth (+-1.65 at J's nose edge, y -7.1) to the hall's wall; its roof from
        roof_y aft with 0.15 m of hull over it (the clearance holds), the front an open notch; the ramp from the
        mouth to the ground; four sockets in the hall."""
        t = sl.rooms(LAYOUT)["throat"]
        (x0, x1), y0 = sl.exit_edge(t)
        self.assertEqual((x0, x1, y0), (-1.65, 1.65, -7.1))
        self.assertEqual(LAYOUT["ramp"]["hinge"], [0.0, -7.1])
        self.assertEqual(LAYOUT["ramp"]["width_m"], x1 - x0)
        p = LAYOUT["player"]
        self.assertGreaterEqual(LAYOUT["deck"]["floor_h"] + t["clear_h"],
                                LAYOUT["deck"]["floor_h"] + p["capsule_height_m"] + p["head_margin_m"] - 1e-9)
        self.assertLess(S.skin((0.0, t["roof_y"] - 0.3, 2.5)), 0.0)                  # the open notch: no roof
        top = S.heights(0.0, t["roof_y"] + 0.15)[0]
        self.assertGreaterEqual(top - (LAYOUT["deck"]["floor_h"] + t["clear_h"] + S.ROOF), S.SKIN)
        self.assertEqual(len([s for s in LAYOUT["stations"]["spot"] if s["id"].startswith("socket")]), 4)

    def test_a_trunk_on_a_plain_spot_is_refused(self) -> None:
        def trunk(layout):
            layout["place"].append(["hall_trunk", [3.505, -3.003, 0.0], 29.745])   # rebuild C: on a front socket
        self.assertTrue(any("socket_fe: hall_trunk sticks out" in p for p in problems_after(trunk)))

    def test_a_cable_bay_on_a_breaker_wall_is_refused(self) -> None:
        def bay(layout):
            layout["place"].append(["cor_channel", [5.380, 1.592, 0.0], -25.7307])   # on the axis at the board
        self.assertTrue(any("breaker_e: cor_channel sticks out" in p for p in problems_after(bay)))

    def test_a_blocked_pass_is_refused(self) -> None:
        def block(layout):
            spot = next(s for s in layout["stations"]["spot"] if s["id"] == "socket_e")
            x, y = sl.spot_stand(layout, spot)
            n = sl._unit(spot["normal"])
            layout["stations"]["spot"][0]["at"] = [x + 1.2 * n[0], y + 1.2 * n[1]]
        self.assertTrue(any("socket_e: the pass behind it crosses console" in p for p in problems_after(block)))

    def test_a_tip_room_moved_out_is_refused(self) -> None:
        def move(layout):
            sl.rooms(layout)["tip_e"]["centre"] = [9.0, 4.0]
        self.assertTrue(any("tip_e: outer wall at 10.80" in p for p in problems_after(move)))

    def test_a_second_exit_is_refused(self) -> None:
        def side_hatch(layout):
            sl.rooms(layout)["corridor_e"]["exit"] = "hatch"
        self.assertTrue(any("exactly one" in p for p in problems_after(side_hatch)))

    def test_a_station_outside_its_room_is_refused(self) -> None:
        def move(layout):
            layout["stations"]["spot"][0]["at"] = [0.0, 3.8]
        self.assertTrue(any("station console" in p for p in problems_after(move)))

    def test_a_wall_station_away_from_its_wall_is_refused(self) -> None:
        def move(layout):
            next(s for s in layout["stations"]["spot"] if s["id"] == "breaker_e")["at"] = [5.380, 1.592]
        self.assertTrue(any("from the wall" in p for p in problems_after(move)))

    def test_a_narrow_corridor_is_refused(self) -> None:
        def narrow(layout):
            sl.rooms(layout)["corridor_w"]["width"] = 1.8
        self.assertTrue(any("wide, wants about 3" in p for p in problems_after(narrow)))

    def test_the_hull_rows_are_the_shapes(self) -> None:
        """[hull] core and plate are ship_hull_shape.outline_rows() of [hull] shape (regenerate them when it changes)."""
        core, plate = S.outline_rows(LAYOUT["hull"]["shape"])
        self.assertEqual(LAYOUT["hull"]["core"], core)
        self.assertEqual(LAYOUT["hull"]["plate"], plate)

    def test_every_room_has_its_skin(self) -> None:
        """rebuild B: J holds every room with at least SKIN (0.15 m) of hull and nothing pokes out."""
        least, bad = S.clearance(LAYOUT["hull"]["shape"])
        self.assertEqual(bad, [])
        self.assertGreaterEqual(least, S.SKIN)

    def test_a_poke_is_found(self) -> None:
        """A room point outside the hull counts as a poke (negative skin), one inside the throat's open notch too; and
        `check()` reports a room pushed out through the hull (the east tip room's roof raised 1.6 m)."""
        self.assertLess(S.skin((15.5, 6.4, 3.0)), 0.0)
        self.assertLess(S.skin((0.0, -6.0, 1.5)), 0.0)   # rebuild C: in the throat's open notch
        self.assertGreater(S.skin((0.0, 0.0, 2.0)), 1.0)

        def tall(layout):
            r = sl.rooms(layout)["tip_e"]
            r["clear_h"], r["apex_h"] = 4.1, 4.4
        found = problems_after(tall)
        self.assertTrue(any("POKES OUT" in p and "tip_e" in p for p in found), found[:3])

    def test_every_room_is_checked_from_the_layout_given(self) -> None:
        """rebuild D: the skin check samples every room of the checked layout on its own, the west ones too (it used
        to read ship.toml once and mirror the east rooms): a west tip room or corridor raised in a copy fails."""
        def tip_w(layout):
            sl.rooms(layout)["tip_w"]["clear_h"] = 3.4
        found = problems_after(tip_w)
        self.assertTrue(any(p.startswith("hull J: tip wall tip_w") for p in found), found[:3])
        self.assertFalse(any("tip_e" in p for p in found))

        def corridor_w(layout):
            sl.rooms(layout)["corridor_w"]["clear_h"] = 3.4
        found = problems_after(corridor_w)
        self.assertTrue(any("corridor_w" in p and p.startswith("hull J") for p in found), found[:3])
        self.assertFalse(any("corridor_e" in p for p in found))

        def throat(layout):
            sl.rooms(layout)["throat"]["clear_h"] = 3.6
        self.assertTrue(any(p.startswith("hull J: throat") for p in problems_after(throat)))

    def test_a_bad_poly_and_a_walk_point_off_the_floor_are_refused(self) -> None:
        def reverse(layout):
            sl.rooms(layout)["throat"]["points"].reverse()
        self.assertTrue(any("wind the wrong way" in p for p in problems_after(reverse)))

        def dent(layout):
            sl.rooms(layout)["throat"]["points"].insert(1, [0.0, -6.5])
        self.assertTrue(any("not convex" in p for p in problems_after(dent)))

        def stray(layout):
            layout["walk"]["points"].insert(5, [-5.0, -3.5, 0.6])   # between the hall and the west corridor: no room
        self.assertTrue(any(p.startswith("walk point (-5, -3.5)") for p in problems_after(stray)))

    def test_a_low_ceiling_is_refused(self) -> None:
        def low(layout):
            sl.rooms(layout)["corridor_e"]["clear_h"] = 2.0
        self.assertTrue(any("clear height" in p for p in problems_after(low)))

    def test_a_piece_outside_the_hull_is_refused(self) -> None:
        def stray(layout):
            layout["place"].append(["canopy_glass_e", [0.0, -12.0, 0.0], 0.0])  # a piece kept inside the hull
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
