"""The attic and the free roof (art #77; tools/runner/house_attic.py, docs/house.md): the dressing data holds its
checks, every hiding spot is reachable for a pick-up, the roof is walkable from the dormer to its stations, the lookout
sees the fence openings and not inside the house. Pure Python."""

from __future__ import annotations

import copy
import math
import unittest

from runner import house_attic as A
from runner import house_layout as H

DATA = H.load()
ATTIC = A.load("attic")
ROOF = A.roof_zone(ATTIC, DATA)


def with_item(z: dict, **item) -> dict:
    z = copy.deepcopy(z)
    it = {"yaw": 0.0, "src": "library", "index": len(z["items"]), **item}
    if "w" not in it:
        it["w"], it["d"], it["h"] = A._library()[it["id"]]
    z["items"].append(it)
    return z


class AtticTest(unittest.TestCase):
    def test_the_data_holds_its_checks(self) -> None:
        self.assertEqual(A.check(ATTIC, DATA), [])
        self.assertEqual(A.check(ROOF, DATA), [])

    def test_the_inventory_counts(self) -> None:
        for z in (ATTIC, ROOF):
            got: dict[str, int] = {}
            for it in z["items"]:
                got[it["id"]] = got.get(it["id"], 0) + 1
            self.assertEqual(got, A.COUNTS[z["room"]])

    def test_every_spot_is_reachable_within_reach(self) -> None:
        spots = A.reach(ATTIC, DATA)
        self.assertGreaterEqual(len(spots), A.MIN_SPOTS)
        for s in spots:
            self.assertTrue(s["reachable"], s["name"])
            self.assertLessEqual(((s["stand"][0] - s["at"][0]) ** 2 + (s["stand"][1] - s["at"][1]) ** 2) ** 0.5,
                                 A.REACH_M + 1e-9)

    def test_a_spot_behind_a_wardrobe_is_found(self) -> None:
        z = copy.deepcopy(ATTIC)  # the gap between the north wardrobe (y 24.2..24.8) and the wall
        z["spots"].append({"name": "Behind", "at": [20.0, 24.15], "h": 0.0, "in": "nothing"})
        problems = A.check(z, DATA)
        self.assertTrue(any("Behind" in p and "no pick-up" in p for p in problems), problems)

    def test_a_spot_out_of_reach_up_high_is_found(self) -> None:
        z = copy.deepcopy(ATTIC)
        z["spots"].append({"name": "High", "at": [30.0, 33.0], "h": 2.5, "in": "trunk"})
        self.assertTrue(any("High" in p for p in A.check(z, DATA)))

    def test_a_prop_on_the_hatch_the_climb_out_or_too_tall_is_refused(self) -> None:
        on_hatch = A.check(with_item(ATTIC, id="crate", at=[28.0, 29.0]), DATA)
        self.assertTrue(any("hole" in p for p in on_hatch), on_hatch)
        on_stair = A.check(with_item(ATTIC, id="crate", at=[35.0, 42.0]), DATA)
        self.assertTrue(any("kept-free" in p for p in on_stair), on_stair)
        tall = A.check(with_item(ATTIC, id="tall", at=[30.0, 24.3], w=0.5, d=0.4, h=2.3), DATA)
        self.assertTrue(any("roof" in p for p in tall), tall)

    def test_the_chimneys_stand_in_the_attic(self) -> None:
        probs = A.check(with_item(ATTIC, id="crate", at=[22.0, 27.5]), DATA)  # on the north chimney (21.5..22.5, 27..28)
        self.assertTrue(any("chimney_attic" in p and "overlap" in p for p in probs), probs)

    def test_the_climb_out_stair_meets_the_sill_from_the_attic_floor(self) -> None:
        (c,) = A.climbs(DATA)
        (dm,) = A.dormers(DATA)
        self.assertAlmostEqual(c["top_h"], dm["sill"], delta=A.CLIMB_TOL)
        self.assertLess(math.dist(c["top"], dm["inner"]), 0.01)  # at the front wall's inner face, under the window
        self.assertLessEqual(c["slope"], A.MAX_SLOPE)
        self.assertGreaterEqual(c["width"], dm["opening"][0])
        self.assertEqual(A.climb_problems(ATTIC, DATA), [])
        lamp = dm["lamp"]  # the practical lamp hangs over the stair, above a climbing player's head
        self.assertTrue(34.5 <= lamp[0] <= 35.5 and 39.85 <= lamp[1] <= 42.85)
        t = (lamp[1] - 39.85) / 3.0
        self.assertGreater(lamp[2], c["top_h"] * t + A.PLAYER_H + 0.3)

    def test_a_stair_too_short_steep_or_walled_off_is_found(self) -> None:
        data = copy.deepcopy(DATA)
        data["pieces"]["stair_dormer"]["rise"] = 2.6
        self.assertTrue(any("is not its sill" in p for p in A.climb_problems(ATTIC, data)))
        data["pieces"]["stair_dormer"].update(rise=2.857, run=2.0)
        attic = next(lv for lv in data["levels"] if lv["level"] == "attic")
        next(fp for fp in attic["pieces"] if fp["piece"] == "stair_dormer")["at"][2] = 40.85  # its top stays put
        self.assertTrue(any("over 45" in p for p in A.climb_problems(ATTIC, data)))
        boxed = with_item(ATTIC, id="crate", at=[35.0, 39.2])
        self.assertTrue(any("stair's foot" in p for p in A.climb_problems(boxed, DATA)))

    def test_overlaps_and_counts_are_found(self) -> None:
        problems = A.check(with_item(ATTIC, id="trunk", at=[22.1, 24.5]), DATA)
        self.assertTrue(any("overlap" in p for p in problems))
        self.assertTrue(any("trunk: 7 placed" in p for p in problems))


class RoofTest(unittest.TestCase):
    def test_roof_top_follows_the_pitch(self) -> None:
        r = DATA["spec"]["grid"]["gable_rise_per_m"]
        self.assertAlmostEqual(A.roof_top(DATA, 41.9) - A.roof_top(DATA, 44.0), 2.1 * r)
        self.assertAlmostEqual(A.roof_top(DATA, 26.0), A.roof_top(DATA, 42.0))  # the slopes mirror about the ridge
        self.assertAlmostEqual(A.roof_top(DATA, 41.9), 3.092, places=3)  # the layout's Lookout station height

    def test_the_dormer_lets_out_onto_the_south_slope(self) -> None:
        (dm,) = A.dormers(DATA)
        self.assertEqual([round(v, 6) for v in dm["window"]], [35.0, 43.0])
        self.assertGreater(dm["sill"], A.roof_top(DATA, 43.2))  # the sill stands over the roof outside
        self.assertLess(dm["sill"], 3.2)  # and a short stair's height over the attic floor
        self.assertLess(math.dist(dm["out"], ROOF["arrive"]), 0.6)
        self.assertLessEqual(A.step_at_wall(dm, DATA), A.STEP_H)  # out over the sill and back in without a jump
        # the crouched capsule (the game adds a crouch) passes the 1.0 x 1.4 m window with its margin; a lower one fails
        self.assertGreaterEqual(dm["opening"][1], A.CLEAR_H)
        self.assertGreaterEqual(A.CLEAR_H, A.CROUCH_H + 0.1)
        self.assertGreaterEqual(dm["opening"][0], 2 * A.PLAYER_R + 0.1)
        self.assertFalse(any("capsule through" in p for p in A.check(ROOF, DATA)))
        data = copy.deepcopy(DATA)
        data["pieces"]["dormer_gable"]["window"] = [1.0, 1.25]
        self.assertTrue(any("crouched 1.2 m capsule through" in p for p in A.check(ROOF, data)))
        data["pieces"]["dormer_gable"]["window"] = [0.85, 1.4]
        self.assertTrue(any("crouched 1.2 m capsule through" in p for p in A.check(ROOF, data)))
        data = copy.deepcopy(DATA)
        data["pieces"]["dormer_gable"]["sill"] = 0.5
        self.assertTrue(any("no walking back in" in p for p in A.check(ROOF, data)))

    def test_the_open_casement_keeps_clear_of_the_climb_out(self) -> None:
        (dm,) = A.dormers(DATA)
        x0, x1 = dm["window"][0] - dm["opening"][0] / 2, dm["window"][0] + dm["opening"][0] / 2
        hinge = dm["leaf"][0] if abs(dm["leaf"][0][0] - x1) < 0.1 else dm["leaf"][-1]
        self.assertAlmostEqual(hinge[0], x1, delta=0.05)  # the world-east jamb (docs/house.md)
        lane = (dm["window"][0] - A.PLAYER_R, dm["window"][0] + A.PLAYER_R)  # the crouched capsule straight out
        self.assertTrue(all(not lane[0] < x < lane[1] for x, _ in dm["leaf"]))
        self.assertTrue(all(x >= x0 for x, _ in dm["leaf"]))

    def test_the_whole_roof_is_walkable_from_the_dormer(self) -> None:
        seen, cell = A.walkable(ROOF, DATA)
        pts = [cell(*c) for c in seen]
        for corner in ((18.5, 24.5), (41.5, 24.5), (18.5, 43.5), (41.5, 43.5), (30.0, 34.0)):
            self.assertTrue(any(math.dist(p, corner) < 0.3 for p in pts), corner)
        self.assertFalse(any(34.0 < p[0] < 36.0 and 36.0 < p[1] < 43.0 for p in pts))  # not through the dormer
        self.assertGreater(len(seen) * A.GRID ** 2, 400)

    def test_the_lookout_sees_the_wicket_and_gates_and_never_inside(self) -> None:
        view = A.lookout(ROOF, DATA)
        self.assertEqual(view[0]["eye"], [39.0, 41.9])
        self.assertTrue(all(v >= 0.5 for v in view[0]["see"].values()), view[0]["see"])
        self.assertEqual(view[0]["house_windows"], [])
        self.assertEqual(A.not_met(ROOF, view), [])

    def test_a_shortfall_fails_unless_open(self) -> None:
        z = copy.deepcopy(ROOF)
        z["lookout"]["station"] = z["lookout"]["eyes"][0] = [30.0, 24.0]  # the north eave: the roof hides the yard
        probs = A.check(z, DATA)
        self.assertTrue(any("less than half" in p for p in probs), probs)
        self.assertTrue(any("not the layout's Lookout station" in p for p in probs), probs)
        z["lookout"]["open"] = "for the engineer"
        self.assertFalse(any("less than half" in p for p in A.check(z, DATA)))

    def test_the_loot_crate_is_on_its_station(self) -> None:
        crate = next(it for it in ROOF["items"] if it["id"] == "loot_crate")
        self.assertEqual((crate["station"], crate["at"]), ("Loot", [41.0, 26.0]))

    def test_a_blocked_climb_out_is_found(self) -> None:
        z = with_item(ROOF, id="roof_box", at=[33.5, 43.5], w=1.2, d=1.4, h=1.0)  # boxes the start in
        self.assertTrue(any("out of reach" in p or "overlap" in p or "no roof" in p for p in A.check(z, DATA)))
        z = copy.deepcopy(ROOF)
        z["arrive"] = [30.0, 43.6]
        self.assertTrue(any("not outside a dormer" in p for p in A.check(z, DATA)))


class ShellTest(unittest.TestCase):
    def test_no_gable_windows_on_the_free_roof(self) -> None:
        ps = next(lv for lv in H.plan(DATA)["levels"] if lv["level"] == "attic")["pieces"]["attic"]
        self.assertFalse([p for p in ps if p["id"] == "gable_band_2m_window"])  # the 0.7 m band cannot hold one
        self.assertFalse(H.validate(DATA) or H.plan(DATA)["problems"])

    def test_a_gable_window_off_a_band_is_refused(self) -> None:
        data = copy.deepcopy(DATA)
        rf = next(lv for lv in data["levels"] if lv["level"] == "attic")["roofs"][0]
        rf["windows"] = [[18, 32.5]]
        self.assertTrue(any("gable window" in p for p in H.plan(data)["problems"]))


class ShootTest(unittest.TestCase):
    def test_the_shoot_request(self) -> None:
        import tempfile
        from pathlib import Path

        from runner.commands import attic as cmd

        with tempfile.TemporaryDirectory() as tmp:
            req, staged, missing = cmd.shoot_request([], Path(tmp))
            self.assertTrue((Path(tmp) / "house.tscn").is_file())
        names = [v[0] for v in req["views"]]
        self.assertEqual(names[:len(cmd.VIEWS)], [v[0] for v in cmd.VIEWS])
        self.assertEqual(names[len(cmd.VIEWS):], [f"lookout_{k + 1}" for k in range(len(ROOF["lookout"]["eyes"]))])
        self.assertNotIn("lineup_at", req)  # zones.gd's line-up is the zones' only
        self.assertEqual(len(req["lamps"]), len(cmd.LAMPS))
        dressing = [p for p in req["pieces"] if p["zone"] in ("attic", "roof")]
        self.assertEqual(len(dressing), len(ATTIC["items"]) + len(ROOF["items"]))
        for p in dressing:
            want = cmd.F if p["zone"] == "attic" else cmd.F + A.roof_top(DATA, p["pos"][2])
            self.assertAlmostEqual(p["pos"][1], want)
            self.assertTrue(("scene" in p) != ("size" in p), p)
        self.assertEqual([p["id"] for p in req["pieces"] if p["zone"] == "spots"], [s["name"] for s in ATTIC["spots"]])
        self.assertEqual({p["id"] for p in req["pieces"] if p["zone"] == "yard"}, set(ROOF["lookout"]["see"]))
        self.assertIn("kit_dormer_gable", set(staged) | {f"kit_{m}" for m in missing})
        self.assertTrue(all(n.startswith(("kit_", "prop_")) for n in staged))


if __name__ == "__main__":
    unittest.main()
