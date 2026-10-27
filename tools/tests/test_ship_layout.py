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

    def test_the_footprint_is_the_hulls(self) -> None:
        width, length = sl.extent(LAYOUT)
        size = LAYOUT["size"]  # the lens blades may reach span_max_m (manager update 2, art #263)
        self.assertAlmostEqual(width, size["width_m"], delta=0.01)
        self.assertAlmostEqual(length, size["length_m"], delta=0.01)   # with the nozzles, no ramp
        lens = sl.lengths(LAYOUT)
        self.assertGreater(lens["nozzles"], lens["body"])
        self.assertGreater(lens["overall"], lens["nozzles"])

    def test_the_station_spots_are_the_design_docs(self) -> None:
        """The spots as built (gills step 8/9): the vents on the hall's back wall beside the vault's door at
        (+-1.6305, 3.2475), the console at (0, 0.6), the back sockets one chord out at (+-2.9339, 2.3119), the front sockets about (+-3.5, -2.4), the breaker boards on
        the corridors' front wall in their middle (+-6.664, -0.902; lens step 1), the renewers on the lens rooms' aft
        walls at (+-10.269, 3.237), their players 1.453 m in (fix1: the charger's reach, was 1.3)."""
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
            # gills step 8 (the engineer's option A): the vents on the hall, the back sockets one chord out
            self.assertEqual(spots[f"vent_{sid}"]["room"], "hall")
            self.assertEqual(tuple(spots[f"vent_{sid}"]["at"]), (sx * 1.6305, 3.2475))
            self.assertLess(math.dist(spots[f"socket_f{sid}"]["at"], (sx * 3.5, -2.4)), 0.15)
            self.assertEqual(tuple(spots[f"socket_{sid}"]["at"]), (sx * 2.9339, 2.3119))
            self.assertEqual(tuple(spots[f"breaker_{sid}"]["at"]), (sx * 6.6638, -0.9019))
            self.assertLess(math.dist(spots[f"breaker_{sid}"]["at"], (sx * 6.45, -0.93)), 0.25)   # asked "about"
            self.assertLess(math.dist(spots[f"renewer_{sid}"]["at"], (sx * 10.3, 3.2)), 0.06)
            stand = sl.spot_stand(LAYOUT, spots[f"renewer_{sid}"])
            self.assertAlmostEqual(stand[0], sx * 10.433, places=2)
            self.assertAlmostEqual(stand[1], 1.793, places=2)

    def test_the_hall_back_wall_is_split_into_two_equal_chords(self) -> None:
        """Gills step 8/9: the arc from the east corridor's chord end (31.164 deg) to the vault's door (77.5 deg) split
        equally at GILL_A0 (54.332): two flat chords of 1.638 m on the 16-gon's vertex circle; each spot in its
        chord's middle (on its apothem) with its normal to the hall's centre; the vents by the door, the back sockets
        outside; the west spots mirror the east."""
        import ship_interior as SI
        spots = {s["id"]: s for s in LAYOUT["stations"]["spot"]}
        hc = SI.HALL_C
        a1 = 90.0 - SI.BACK_DEG
        a0 = SI.COR_ANG + 2 * math.degrees(SI.PHI)
        self.assertAlmostEqual(SI.GILL_A0, (a0 + a1) / 2, places=6)
        for sid, (lo, hi) in (("vent_e", (SI.GILL_A0, a1)), ("socket_e", (a0, SI.GILL_A0))):
            half = math.radians(hi - lo) / 2
            self.assertAlmostEqual(2 * SI.HV * math.sin(half), 1.638, places=3)
            mid, apo = math.radians((lo + hi) / 2), SI.HV * math.cos(half)
            s = spots[sid]
            self.assertLess(math.dist(s["at"], (hc[0] + apo * math.cos(mid), hc[1] + apo * math.sin(mid))), 2e-4, sid)
            self.assertLess(math.dist(s["normal"], (-math.cos(mid), -math.sin(mid))), 2e-4, sid)
            w = spots[sid.replace("_e", "_w")]
            self.assertEqual((w["at"][0], w["at"][1]), (-s["at"][0], s["at"][1]))
            self.assertEqual((w["normal"][0], w["normal"][1]), (-s["normal"][0], s["normal"][1]))

    def test_the_back_sockets_band_is_their_own_and_clears_the_pilaster(self) -> None:
        """Gills step 9: the moved back sockets carry their own plain band (plain_width_m 1.16, narrower than
        [stations]' 1.6), and check_spots, check_units and check_bands read it; the corridor portal's pilaster foot
        (0.4 m box) stays outside the band, and the crystal socket's 0.468 m unit keeps >= 0.3 m to it."""
        st = LAYOUT["stations"]
        foot = next(p["foot"] for p in LAYOUT["pieces"] if p["id"] == "hall_pilaster")
        pil = [(at, yaw) for pid, at, yaw in LAYOUT["place"] if pid == "hall_pilaster"]
        for sid in ("socket_e", "socket_w"):
            s = next(x for x in st["spot"] if x["id"] == sid)
            self.assertEqual(s["plain_width_m"], 1.16)
            self.assertEqual(sl.plain_width(LAYOUT, s), 1.16)
            self.assertLess(s["plain_width_m"], st["plain_width_m"])
            n = sl._unit(s["normal"])
            t = (-n[1], n[0])
            near = 9.0   # the least |u| along the chord where the pilaster's foot starts, out to 0.3 m off the wall
            for at, yaw in pil:
                for k in range(-1000, 1001):
                    u = k / 1000
                    for v in (0.02, 0.15, 0.3):
                        q = (s["at"][0] + t[0] * u + n[0] * v, s["at"][1] + t[1] * u + n[1] * v)
                        lx, ly = sl.to_local(q, at, yaw)
                        if foot[0] <= lx <= foot[1] and foot[2] <= ly <= foot[3]:
                            near = min(near, abs(u))
            self.assertGreater(near, s["plain_width_m"] / 2, sid)
            self.assertGreaterEqual(near - 0.468 / 2, 0.3, sid)
        self.assertEqual([p for p in sl.check_spots(LAYOUT) if "socket" in p], [])
        # the shared 1.6 m band would cross the pilaster: the per-spot band is what lets it pass
        wide = copy.deepcopy(LAYOUT)
        for s in wide["stations"]["spot"]:
            s.pop("plain_width_m", None)
        self.assertTrue(any("socket_e: hall_pilaster" in p for p in sl.check_spots(wide)))

    def test_the_renewer_spots_reach_the_chargers_front(self) -> None:
        """fix1 (art#263, #323's review): the renewer spots' depth_m is the crystal charger's reach from the wall's face
        (its report's d max, 105.25 cm, rounded up to the mm), so the layout's own stand and pass checks put the player
        in front of its pads, not inside them."""
        import json
        from runner import common
        report = common.ROOT / "assets" / "prop" / "crystal_charger" / "report.json"
        reach = json.loads(report.read_text(encoding="utf-8"))["mesh"]["size_cm"]["d"][1] / 100
        spots = {s["id"]: s for s in LAYOUT["stations"]["spot"]}
        for sid in ("renewer_e", "renewer_w"):
            self.assertGreaterEqual(spots[sid]["depth_m"], reach)
            self.assertLess(spots[sid]["depth_m"] - reach, 0.001)

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
            # details 1: one round roof window (the oculus, 1.4 m clear) replaced the blockout's three panels
            self.assertEqual(t["oculus"], {"d": 1.4, "sides": 32})
            self.assertNotIn("roof_windows", t)
            band = t["band"]
            self.assertAlmostEqual(S.FLOOR + band["sill_h"], B.SILL)
            self.assertAlmostEqual(S.FLOOR + band["head_h"], B.HEAD)
            self.assertEqual((band["from_deg"], band["to_deg"]), (-65.0, 45.0))   # P's trail fin hides it from +45
        v = r["vault"]
        hw, y0, y1, h0, h1 = B.VAULT
        self.assertEqual((v["x"], v["y"], v["clear_h"], v["clear_h_back"]), ([-hw, hw], [y0, y1], h0, h1))
        self.assertTrue(v["closed"])
        self.assertEqual(v["door"], {"at": [0.0, 3.6], "width_m": 1.0, "room": "hall"})
        # the hull's cuts read the same rooms (ship_hull_shape derives them): the lens, its roof windows, the vault
        t = r["tip_e"]
        self.assertEqual(S.P_TIP, tuple(t["centre"]))
        self.assertEqual(S.P_ROOM_R, t["radius"])
        self.assertEqual(S.P_CLEAR, (t["clear_h"], t["clear_h_in"]))
        self.assertEqual((S.P_OCULUS_D, S.P_OCULUS_N), (t["oculus"]["d"], t["oculus"]["sides"]))
        roofs = [o for o in S.p_openings() if o[2] == "roof"]
        self.assertEqual(len(roofs), 2)   # one oculus per lens
        for planes, emit, _w in roofs:   # its sides: the cut 2.5 cm outside the clear radius (the well's lining)
            self.assertEqual(len(emit), S.P_OCULUS_N)
            for j in emit:
                (nx, ny, _nz), d = planes[j]
                c = (S.P_TIP[0] if planes[0][0][0] > 0 else -S.P_TIP[0], S.P_TIP[1])
                self.assertAlmostEqual(d - nx * c[0] - ny * c[1], S.P_OCULUS_D / 2 + 0.025, places=6)
        self.assertEqual(S.P_VAULT, (v["x"][1], *v["y"], v["clear_h"], v["clear_h_back"]))
        self.assertEqual(v["x"][0], -v["x"][1])
        # the band's cut is the interior's band as built: the asked -65..45 snapped to the wall facets 3..7 (each end
        # to a facet vertex within 1.5 deg: -65.86 and 43.91)
        import ship_interior as I
        tv, fs = I.tip_vertices(), I.tip_band_facets(1)
        self.assertEqual(fs, [3, 4, 5, 6, 7])
        self.assertEqual(S.P_BAND, (tv[fs[0]], tv[fs[-1] + 1]))
        self.assertEqual((round(S.P_BAND[0], 3), round(S.P_BAND[1], 3)), (-65.863, 43.909))
        self.assertLessEqual(abs(S.P_BAND[0] - t["band"]["from_deg"]), 1.5)
        self.assertLessEqual(abs(S.P_BAND[1] - t["band"]["to_deg"]), 1.5)
        self.assertEqual(r["tip_w"]["band"], t["band"])   # the west band is the east one mirrored (+ aft)

    def test_the_built_window_band_is_fully_visible(self) -> None:
        """lens step 2: no hull part (the body, the fins, the other lens) covers the window band as built: points 0.05 and
        0.3 m outside each lens's rim, across the built band (S.P_BAND round the lens's axis, + aft, the west mirrored),
        from the sill + 0.02 to the head - 0.02, lie inside none of P's convex parts."""
        parts = S._parts("P")
        a0, a1 = S.P_BAND
        n_a, n_h, hits, seen = 56, 7, [], 0
        for sx in (1, -1):
            for dr in (0.05, 0.3):
                for i in range(n_a + 1):
                    x, y = S.p_rim(a0 + (a1 - a0) * i / n_a, sx, S.P_RIM_R + dr)
                    for k in range(n_h + 1):
                        h = S.SILL + 0.02 + (S.HEAD - S.SILL - 0.04) * k / n_h
                        seen += 1
                        if any(all(S._dot(n, (x, y, h)) <= d + 1e-9 for n, d, _poly in fac) for fac in parts):
                            hits.append((sx, dr, round(x, 3), round(y, 3), round(h, 3)))
        self.assertEqual(seen, 2 * 2 * (n_a + 1) * (n_h + 1))
        self.assertEqual(hits, [], f"{len(hits)} band points inside a hull part, e.g. {hits[:3]}")
        # the sampler sees a part: 0.05 m inside the rim is inside the lens
        x, y = S.p_rim(0.0, 1, S.P_RIM_R - 0.05)
        self.assertTrue(any(all(S._dot(n, (x, y, 2.2)) <= d for n, d, _p in fac) for fac in parts))

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
                            for p in problems_after(lambda l: l["walk"]["points"].insert(5, [0.0, 4.85, 1.2]))))
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
        self.assertEqual((x0, x1, y0), (-1.65, 1.65, -8.1))   # the raise step 2: the tunnel's front, 1 m past the nose
        self.assertEqual(min(q[1] for q in t["points"]), -7.1)   # the room's own polygon still ends at the nose edge
        self.assertEqual(sl.tunnel(t), ((-1.65, 1.65), (-8.1, -7.1)))
        self.assertAlmostEqual(sl.room_margin(t, (0.0, -7.6)), 0.5)   # the tunnel's floor is the throat's
        self.assertEqual(LAYOUT["ramp"]["hinge"], [0.0, -8.1])
        self.assertEqual(LAYOUT["ramp"]["width_m"], x1 - x0)
        p = LAYOUT["player"]
        self.assertGreaterEqual(LAYOUT["deck"]["floor_h"] + t["clear_h"],
                                LAYOUT["deck"]["floor_h"] + p["capsule_height_m"] + p["head_margin_m"] - 1e-9)
        self.assertLess(S.skin((0.0, t["roof_y"] - 0.3, 2.5)), 0.0)                  # the open notch: no roof
        top = S.heights(0.0, t["roof_y"] + 0.15)[0]
        self.assertGreaterEqual(top - (S.FLOOR + t["clear_h"] + S.ROOF), S.SKIN)   # the design frame (the raise)
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
            layout["walk"]["points"] = [[-10.994, 1.275, 1.2], [10.994, 1.275, 1.2]]
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

    def test_every_room_has_its_skin(self) -> None:
        """rebuild B, lens step 2: the live hull (P) holds every room with at least SKIN (0.15 m) of hull and nothing pokes out."""
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

        def vault(layout):   # lens step 3 review: the vault is sampled from the layout given too
            sl.rooms(layout)["vault"]["clear_h"] = 4.0
        found = problems_after(vault)
        self.assertTrue(any("vault" in p and p.startswith("hull P") for p in found), found[:3])

    def test_a_bad_poly_and_a_walk_point_off_the_floor_are_refused(self) -> None:
        def reverse(layout):
            sl.rooms(layout)["throat"]["points"].reverse()
        self.assertTrue(any("wind the wrong way" in p for p in problems_after(reverse)))

        def dent(layout):
            sl.rooms(layout)["throat"]["points"].insert(1, [0.0, -6.5])
        self.assertTrue(any("not convex" in p for p in problems_after(dent)))

        def stray(layout):
            layout["walk"]["points"].insert(5, [-5.0, -3.5, 1.2])   # between the hall and the west corridor: no room
        self.assertTrue(any(p.startswith("walk point (-5, -3.5)") for p in problems_after(stray)))

    def test_a_low_ceiling_is_refused(self) -> None:
        def low(layout):
            sl.rooms(layout)["corridor_e"]["clear_h"] = 2.0
        self.assertTrue(any("corridor_e: clear height 2 m" in p for p in problems_after(low)))

        def low_in(layout):   # a slanted ceiling: its lower end counts
            sl.rooms(layout)["tip_e"]["clear_h_in"] = 1.9
        self.assertTrue(any("tip_e: clear height 1.9 m" in p for p in problems_after(low_in)))

        def low_vault(layout):   # a closed room: nobody walks there
            sl.rooms(layout)["vault"]["clear_h"] = 1.5
        self.assertFalse(any("vault: clear height" in p for p in problems_after(low_vault)))

    def test_the_walk_enters_every_open_room(self) -> None:
        """lens step 3 review: the walk (its points and the samples between them) enters every room but a closed one."""
        def skip_west(layout):   # the walk turns back in the hall: neither the west corridor nor the west lens
            layout["walk"]["points"] = [p for p in layout["walk"]["points"] if p[0] >= -0.01]
        found = problems_after(skip_west)
        self.assertTrue(any(p.startswith("tip_w: the walk does not enter it") for p in found), found[:3])
        self.assertTrue(any(p.startswith("corridor_w: the walk does not enter it") for p in found), found[:3])
        self.assertFalse(any(p.startswith(("tip_e", "corridor_e", "vault")) for p in found), found[:3])

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
