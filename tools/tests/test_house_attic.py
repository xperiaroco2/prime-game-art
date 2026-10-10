"""The attic and the roof deck (art #77; tools/runner/house_attic.py, docs/house.md): the dressing data holds its
checks, every hiding spot is reachable for a pick-up, the lookout sees the fence openings and not inside the house; the
gable windows and the cornice brackets land where the layout says. Pure Python."""

from __future__ import annotations

import copy
import unittest

from runner import house_attic as A
from runner import house_layout as H

DATA = H.load()
ATTIC = A.load("attic")
ROOF = A.load("roof")


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
        z = copy.deepcopy(ATTIC)  # the gap between the north wardrobe (y 26.2..26.8) and the wall
        z["spots"].append({"name": "Behind", "at": [22.0, 26.15], "h": 0.0, "in": "nothing"})
        problems = A.check(z, DATA)
        self.assertTrue(any("Behind" in p and "no pick-up" in p for p in problems), problems)

    def test_a_spot_out_of_reach_up_high_is_found(self) -> None:
        z = copy.deepcopy(ATTIC)
        z["spots"].append({"name": "High", "at": [30.0, 33.0], "h": 2.5, "in": "trunk"})
        self.assertTrue(any("High" in p for p in A.check(z, DATA)))

    def test_a_prop_on_the_hatch_or_too_tall_is_refused(self) -> None:
        on_hatch = A.check(with_item(ATTIC, id="crate", at=[28.0, 29.0]), DATA)
        self.assertTrue(any("hole" in p for p in on_hatch), on_hatch)
        tall = A.check(with_item(ATTIC, id="tall", at=[30.0, 26.3], w=0.5, d=0.4, h=2.3), DATA)
        self.assertTrue(any("roof" in p for p in tall), tall)

    def test_overlaps_and_counts_are_found(self) -> None:
        problems = A.check(with_item(ATTIC, id="trunk", at=[24.1, 26.5]), DATA)
        self.assertTrue(any("overlap" in p for p in problems))
        self.assertTrue(any("trunk: 7 placed" in p for p in problems))


class RoofTest(unittest.TestCase):
    def test_the_lookout_reports_the_doc_station_honestly_and_never_sees_inside(self) -> None:
        views = {tuple(v["eye"]): v for v in A.lookout(ROOF, DATA)}
        self.assertEqual(tuple(ROOF["lookout"]["station"]), (30.0, 42.5))  # the design doc's point, the layout's marker
        self.assertEqual(views[(30.0, 42.5)]["see"], {"wicket": 0.0, "gates": 0.0})  # the parapet hides both
        self.assertEqual(views[(30.0, 44.2)]["see"], {"wicket": 1.0, "gates": 1.0})  # the alternative only
        for v in views.values():
            self.assertEqual(v["house_windows"], [])

    def test_the_station_shortfall_fails_unless_open_for_the_engineer(self) -> None:
        rep = A.report(DATA)["roof"]
        self.assertEqual(len(rep["not_met"]), 2, rep["not_met"])
        self.assertTrue(rep["open"])
        z = copy.deepcopy(ROOF)
        del z["lookout"]["open"]
        probs = A.check(z, DATA)
        self.assertTrue(any("0 % of the wicket from its station" in p for p in probs), probs)
        z["lookout"]["eyes"] = list(reversed(z["lookout"]["eyes"]))  # the alternative cannot stand in for the station
        self.assertIn("the lookout's station is not its first eye", A.check(z, DATA))

    def test_the_lookout_station_is_the_layouts_marker(self) -> None:
        z = copy.deepcopy(ROOF)
        z["lookout"]["station"] = z["lookout"]["eyes"][0] = [30.0, 44.2]
        probs = A.check(z, DATA)
        self.assertTrue(any("not the layout's Lookout station" in p for p in probs), probs)

    def test_the_loot_crate_is_on_its_station(self) -> None:
        crate = next(it for it in ROOF["items"] if it["id"] == "loot_crate")
        self.assertEqual((crate["station"], crate["at"]), ("Loot", [41.5, 25.0]))

    def test_a_blocked_roof_door_is_found(self) -> None:
        z = with_item(ROOF, id="roof_water_tank", at=[41.9, 33.0], w=1.5, d=1.5, h=1.8)
        z["clear"] = []
        self.assertTrue(any("out of reach" in p or "outside" in p for p in A.check(z, DATA)))


class ShellTest(unittest.TestCase):
    def planned(self, name: str) -> dict:
        return next(lv for lv in H.plan(DATA)["levels"] if lv["level"] == name)

    def test_the_gable_window_pair(self) -> None:
        wins = [p for p in self.planned("attic")["pieces"]["attic"] if p["id"] == "gable_band_2m_window"]
        self.assertEqual(sorted((p["x"], p["turn"]) for p in wins), [(20.0, -90), (40.0, 90)])
        self.assertTrue(all(p["h"] == DATA["spec"]["grid"]["knee_h_m"] for p in wins))
        self.assertFalse(H.validate(DATA) or H.plan(DATA)["problems"])
        self.assertFalse([p for p in next(lv for lv in DATA["levels"] if lv["level"] == "attic").get("placeholders", [])
                          if p["name"].startswith("GableWindow")])

    def test_a_gable_window_off_a_band_is_refused(self) -> None:
        data = copy.deepcopy(DATA)
        rf = next(lv for lv in data["levels"] if lv["level"] == "attic")["roofs"][0]
        rf["windows"] = [[20, 32.5]]
        self.assertTrue(any("gable window" in p for p in H.plan(data)["problems"]))

    def test_the_window_fits_its_band(self) -> None:
        g, p = DATA["spec"]["grid"], DATA["pieces"]["gable_band_2m_window"]
        op = H.kit_geom().openings(g)[p["opening"]]
        self.assertLess(op["y1"], float(p["height"]))
        self.assertEqual(p["height"], DATA["pieces"]["gable_band_2m"]["height"])

    def test_cornice_brackets_ring_the_house_and_reach_out(self) -> None:
        br = [p for p in self.planned("roof")["pieces"]["roof"] if p["id"] == "cornice_bracket"]
        self.assertEqual(len(br), 2 * (12 + 10))
        self.assertTrue(all(p["h"] == -DATA["spec"]["grid"]["roof_slab_m"] for p in br))
        for p in br:
            ax, az = H.axes(p["turn"])  # the bracket reaches along its local +Z: out of the footprint
            out = (p["x"] + az[0], p["y"] + az[1])
            self.assertFalse(18 < out[0] < 42 and 24 < out[1] < 44, p)


if __name__ == "__main__":
    unittest.main()


class ShootTest(unittest.TestCase):
    def test_the_shoot_request(self) -> None:
        import tempfile
        from pathlib import Path

        from runner.commands import attic as cmd

        with tempfile.TemporaryDirectory() as tmp:
            req, staged, missing = cmd.shoot_request([], Path(tmp))
            self.assertTrue((Path(tmp) / "house.tscn").is_file())
        names = [v[0] for v in req["views"]]
        self.assertEqual(names[:6], [v[0] for v in cmd.VIEWS])
        self.assertEqual(names[6:], [f"lookout_{k + 1}" for k in range(len(ROOF["lookout"]["eyes"]))])
        self.assertNotIn("lineup_at", req)  # zones.gd's line-up is the zones' only
        self.assertEqual(len(req["lamps"]), len(cmd.LAMPS))
        dressing = [p for p in req["pieces"] if p["zone"] in ("attic", "roof")]
        self.assertEqual(len(dressing), len(ATTIC["items"]) + len(ROOF["items"]))
        for p in dressing:
            self.assertEqual(p["pos"][1], cmd.F)
            self.assertTrue(("scene" in p) != ("size" in p), p)
        self.assertEqual([p["id"] for p in req["pieces"] if p["zone"] == "spots"], [s["name"] for s in ATTIC["spots"]])
        self.assertEqual({p["id"] for p in req["pieces"] if p["zone"] == "yard"}, set(ROOF["lookout"]["see"]))
        self.assertIn("kit_gable_band_2m_window", set(staged) | {f"kit_{m}" for m in missing})
        self.assertTrue(all(n.startswith(("kit_", "prop_")) for n in staged))
