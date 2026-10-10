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
    def test_the_lookout_sees_the_yard_from_the_parapet_and_not_inside(self) -> None:
        views = {tuple(v["eye"]): v for v in A.lookout(ROOF, DATA)}
        at_parapet = views[(30.0, 44.4)]
        self.assertEqual(at_parapet["see"], {"wicket": 1.0, "gates": 1.0})
        for v in views.values():
            self.assertEqual(v["house_windows"], [])

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
