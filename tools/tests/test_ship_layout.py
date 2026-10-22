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
PENDING = LAYOUT["hull"].get("pending")   # lens step 1: the rooms are P's, the live hull still J (step 2 drops it)


def problems_after(change) -> list[str]:
    layout = copy.deepcopy(LAYOUT)
    change(layout)
    return sl.check(layout)


class ShipLayoutTest(unittest.TestCase):
    def test_the_layout_is_clean(self) -> None:
        self.assertEqual(sl.check(LAYOUT), [])

    @unittest.skipIf(PENDING, f"[hull] pending: {PENDING}")
    def test_the_footprint_is_the_hulls(self) -> None:
        width, length = sl.extent(LAYOUT)
        size = LAYOUT["size"]  # the lens blades may reach span_max_m (manager update 2, art #263)
        self.assertAlmostEqual(width, size["width_m"], delta=0.01)
        self.assertAlmostEqual(length, size["length_m"], delta=0.01)   # with the nozzles, no ramp
        lens = sl.lengths(LAYOUT)
        self.assertGreater(lens["nozzles"], lens["body"])
        self.assertGreater(lens["overall"], lens["nozzles"])

    def test_the_station_spots_are_the_design_docs(self) -> None:
        """The spots as built (rebuild F): the vents on the throat's slanted walls at (+-2.409, -4.791), the console
        at (0, 0.6), the back sockets at (+-1.8, 3.112), the front sockets about (+-3.5, -2.4), the breaker boards on
        the corridors' front wall in their middle (+-6.664, -0.902; lens step 1), the renewers on the lens rooms' aft
        walls at (+-10.269, 3.237), their players 1.3 m in."""
        spots = {s["id"]: s for s in LAYOUT["stations"]["spot"]}
        # rebuild C: the vents on the throat's slanted walls (asked (+-2.3, -5.8)), four sockets (the front two beside
        # the throat, asked (+-3.5, -3.0)). rebuild E: the inside 0.4 m forward of step A (the hall's full rim), the
        # spots with it; the front sockets asked (+-3.5, -2.4). rebuild F: the vents on the line between the throat
        # wall's modules 2 and 3 (3/5 of the wall from the mouth), their plain band on those two plain modules
        self.assertEqual(set(spots), {"console", "vent_e", "vent_w", "socket_e", "socket_w", "socket_fe", "socket_fw",
                                      "breaker_e", "breaker_w", "renewer_e", "renewer_w"})
        self.assertEqual(tuple(spots["console"]["at"]), (0.0, 0.6))
        for sx in (1, -1):
            sid = "e" if sx > 0 else "w"
            self.assertEqual(spots[f"vent_{sid}"]["room"], "throat")
            (mx, my), (kx, ky) = S.TH_PTS[1], S.TH_PTS[2]
            self.assertLess(math.dist(spots[f"vent_{sid}"]["at"], (sx * (mx + 0.6 * (kx - mx)), my + 0.6 * (ky - my))),
                            1e-3)
            self.assertLess(math.dist(spots[f"socket_f{sid}"]["at"], (sx * 3.5, -2.4)), 0.15)
            self.assertEqual(tuple(spots[f"socket_{sid}"]["at"]), (sx * 1.8, 3.112))
            self.assertEqual(tuple(spots[f"breaker_{sid}"]["at"]), (sx * 6.6638, -0.9019))
            self.assertLess(math.dist(spots[f"breaker_{sid}"]["at"], (sx * 6.45, -0.93)), 0.25)   # asked "about"
            self.assertLess(math.dist(spots[f"renewer_{sid}"]["at"], (sx * 10.3, 3.2)), 0.06)
            stand = sl.spot_stand(LAYOUT, spots[f"renewer_{sid}"])
            self.assertAlmostEqual(stand[0], sx * 10.415, places=2)
            self.assertAlmostEqual(stand[1], 1.945, places=2)

    def test_the_rooms_are_5a_mirrored(self) -> None:
        r = sl.rooms(LAYOUT)
        self.assertEqual((r["hall"]["radius"], tuple(r["hall"]["centre"])), (4.0, (0.0, -0.4)))   # rebuild E
        for sx, sid in ((1, "e"), (-1, "w")):
            self.assertEqual((r[f"tip_{sid}"]["radius"], tuple(r[f"tip_{sid}"]["centre"])), (2.0, (sx * 10.5, 1.2)))
            cor = r[f"corridor_{sid}"]   # lens step 1: straight, hall centre to lens centre, 8.66 deg aft
            self.assertEqual((cor["shape"], cor["width"], cor["clear_h"]), ("strip", 3.0, 2.4))
            self.assertEqual(cor["axis"], [[0.0, -0.4], r[f"tip_{sid}"]["centre"]])
            self.assertAlmostEqual(math.degrees(math.atan2(1.6, 10.5)), 8.664, places=3)

    def test_the_lens_rooms_and_the_vault_are_ps(self) -> None:
        """lens step 1: the lens rooms, their slanted ceilings, window band and roof windows and the vault are the
        hull P's design numbers (tools/blender/ship_hull_blockout.py), which its blockout measured with 0.15 m of
        skin round the rooms and 0.18 m round the vault (<raw>/ship/v2/blockout6/report.json)."""
        import ship_hull_blockout as B
        r = sl.rooms(LAYOUT)
        for sx, sid in ((1, "e"), (-1, "w")):
            t = r[f"tip_{sid}"]
            self.assertEqual((sx * t["centre"][0], t["centre"][1]), B.RAY_TIP)
            self.assertEqual(t["radius"], B.RAY_ROOM_R)
            self.assertEqual((t["clear_h"], t["clear_h_in"]), (B.RAY_CLEAR_OUT, B.RAY_CLEAR_IN))
            self.assertEqual([tuple(w) for w in t["roof_windows"]], B.RAY_PANELS)
            self.assertEqual(tuple(t["roof_window_m"]), B.RAY_PANEL[:2])
            band = t["band"]
            self.assertAlmostEqual(LAYOUT["deck"]["floor_h"] + band["sill_h"], B.SILL)
            self.assertAlmostEqual(LAYOUT["deck"]["floor_h"] + band["head_h"], B.HEAD)
            self.assertEqual((band["from_deg"], band["to_deg"]), (-65.0, 45.0))   # P's trail fin hides it from +45
        v = r["vault"]
        hw, y0, y1, h0, h1 = B.VAULT
        self.assertEqual((v["x"], v["y"], v["clear_h"], v["clear_h_back"]), ([-hw, hw], [y0, y1], h0, h1))
        self.assertTrue(v["closed"])
        self.assertEqual(v["door"], {"at": [0.0, 3.6], "width_m": 1.0, "room": "hall"})

    def test_the_vault_is_closed(self) -> None:
        """lens step 1: the vault's door is no exit and needs no link or walk; a link to it, an exit in it, a walk
        point in it, a door off the hall's wall or a vault inside the hall's wall are refused."""
        self.assertNotIn("vault", [p for r in LAYOUT["rooms"] for p in r.get("links", [])])
        self.assertLess(sl.in_rooms(LAYOUT, (0.0, 4.85)), 0.0)   # not walkable floor
        self.assertTrue(any("vault: a closed room has no exit" in p
                            for p in problems_after(lambda l: sl.rooms(l)["hall"]["links"].append("vault"))))
        self.assertTrue(any("exactly one" in p or "closed room has no exit" in p
                            for p in problems_after(lambda l: sl.rooms(l)["vault"].update(exit="hatch"))))
        self.assertTrue(any("walk point (0, 4.85)" in p
                            for p in problems_after(lambda l: l["walk"]["points"].insert(5, [0.0, 4.85, 0.6]))))
        self.assertTrue(any("its door (0, 3.1) is not on hall's wall" in p
                            for p in problems_after(lambda l: sl.rooms(l)["vault"]["door"].update(at=[0.0, 3.1]))))
        self.assertTrue(any("vault: " in p and "inside hall's wall" in p
                            for p in problems_after(lambda l: sl.rooms(l)["vault"].update(y=[3.6, 5.6]))))

    def test_the_window_band(self) -> None:
        """lens step 1: the band on the outer side, under the ceiling and off the renewer's plain wall."""
        r = sl.rooms(LAYOUT)
        axis, a0, a1 = sl.band_angles(LAYOUT, r["tip_e"])
        self.assertAlmostEqual(axis, 8.664, places=3)
        self.assertEqual((round(a0, 3), round(a1, 3)), (round(axis - 65.0, 3), round(axis + 45.0, 3)))
        _axis, b0, b1 = sl.band_angles(LAYOUT, r["tip_w"])   # mirrored: + aft in the west too
        self.assertEqual((round(b0, 3), round(b1, 3)), (round(180.0 - axis - 45.0, 3), round(180.0 - axis + 65.0, 3)))
        self.assertTrue(any("renewer_e: its plain wall overlaps tip_e's window band" in p
                            for p in problems_after(lambda l: sl.rooms(l)["tip_e"]["band"].update(to_deg=80.0))))
        self.assertTrue(any("tip_w: its window band's sill" in p
                            for p in problems_after(lambda l: sl.rooms(l)["tip_w"]["band"].update(head_h=2.4))))

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
            layout["place"].append(["tip_trunk", [3.505, -2.403, 0.0], 29.745])   # rebuild E: on a front socket
        self.assertTrue(any("socket_fe: tip_trunk sticks out" in p for p in problems_after(trunk)))

    def test_a_vent_on_the_throat_jamb_is_refused(self) -> None:
        """rebuild F: no plain wall piece under a wall spot's band is refused (rebuild E's vents stood half on the
        hull's jamb, forward of the throat's interior wall modules)."""
        def back(layout):
            next(s for s in layout["stations"]["spot"] if s["id"] == "vent_e")["at"] = [2.0991, -5.7339]
        self.assertTrue(any("vent_e: no plain wall piece under its band" in p for p in problems_after(back)))

    def test_a_walk_cutting_a_corner_is_refused(self) -> None:
        """rebuild F: the walk between two deck points is sampled; straight from one tip room to the other it passes
        behind the hall, through the hull."""
        def cut(layout):
            layout["walk"]["points"] = [[-10.994, 1.275, 0.6], [10.994, 1.275, 0.6]]
        self.assertTrue(any("the walk from (-10.994, 1.275) to (10.994, 1.275) leaves" in p for p in problems_after(cut)))

    def test_a_cable_bay_on_a_breaker_wall_is_refused(self) -> None:
        def bay(layout):
            layout["place"].append(["cor_channel", [6.4377, 0.581, 0.0], -8.6641])   # on the axis at the board
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
            sl.rooms(layout)["tip_e"]["centre"] = [11.0, 1.2]
        self.assertTrue(any("tip_e: outer wall at 13.00" in p for p in problems_after(move)))

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
            next(s for s in layout["stations"]["spot"] if s["id"] == "breaker_e")["at"] = [6.4377, 0.581]
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

    @unittest.skipIf(PENDING, f"[hull] pending: {PENDING}")
    def test_every_room_has_its_skin(self) -> None:
        """rebuild B, lens step 2: the live hull (P) holds every room with at least SKIN (0.15 m) of hull and nothing pokes out."""
        least, bad = S.clearance(LAYOUT["hull"]["shape"])
        self.assertEqual(bad, [])
        self.assertGreaterEqual(least, S.SKIN)

    @unittest.skipIf(PENDING, f"[hull] pending: {PENDING}")
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

    @unittest.skipIf(PENDING, f"[hull] pending: {PENDING}")
    def test_every_room_is_checked_from_the_layout_given(self) -> None:
        """rebuild D: the skin check samples every room of the checked layout on its own, the west ones too (it used
        to read ship.toml once and mirror the east rooms): a west tip room or corridor raised in a copy fails."""
        def tip_w(layout):
            sl.rooms(layout)["tip_w"]["clear_h"] = 3.4
        found = problems_after(tip_w)
        self.assertTrue(any(p.startswith("hull P: tip wall tip_w") for p in found), found[:3])
        self.assertFalse(any("tip_e" in p for p in found))

        def corridor_w(layout):
            sl.rooms(layout)["corridor_w"]["clear_h"] = 3.4
        found = problems_after(corridor_w)
        self.assertTrue(any("corridor_w" in p and p.startswith("hull P") for p in found), found[:3])
        self.assertFalse(any("corridor_e" in p for p in found))

        def throat(layout):
            sl.rooms(layout)["throat"]["clear_h"] = 3.6
        self.assertTrue(any(p.startswith("hull P: throat") for p in problems_after(throat)))

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

    @unittest.skipIf(PENDING, f"[hull] pending: {PENDING}")
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
