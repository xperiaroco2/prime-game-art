"""The garden and the greenhouse's roof (art #80, docs/house-garden.md): the data's checks, the seeded scatter, the herb
route against the design doc, the glass roof's pieces and its gables' rafters, and the rules on made-up cases."""

from __future__ import annotations

import copy
import math
import unittest

from runner import house_garden as hg, house_layout as hl, house_outdoor as ho


class Garden(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.plot, cls.layout = hg.load(), ho.load(), hl.load()
        cls.rep = hg.build(cls.data, cls.plot, cls.layout)

    def test_the_checks_hold(self):
        self.assertEqual(self.rep["problems"], [])

    def test_the_inventory_counts(self):
        # inventory.md section 4, the garden: 14 trees, 30 bushes, 8 flower beds, 12 hedges, 3 benches, 6 post lamps,
        # 10 path lights, 2 strings, 20 stepping stones, the drop-off
        self.assertEqual(self.rep["counts"], {"garden_tree": 14, "flower_bed": 8, "bush": 30})
        ids: dict[str, int] = {}
        for p in self.rep["props"]:
            ids[p["id"]] = ids.get(p["id"], 0) + 1
        want = {"garden_dropoff": 1, "hedge": 12, "garden_bench": 3, "birdbath": 1, "wheelbarrow": 1,
                "watering_can": 1, "garden_post_lamp": 6, "path_light": 10, "string_lights": 2, "stepping_stone": 20}
        self.assertEqual(ids, want)

    def test_the_scatter_is_seeded(self):
        again, _ = hg.scatter(self.data, self.plot)
        self.assertEqual(again, self.rep["scatter"])
        other = dict(self.data, seed=self.data["seed"] + 1)
        self.assertNotEqual(hg.scatter(other, self.plot)[0], again)

    def test_the_scatter_keeps_clear(self):
        for q in self.rep["scatter"]:
            x, y = q["at"]
            for p in self.data["paths"]:
                self.assertGreaterEqual(hg.line_dist(x, y, p["line"]), p["width"] / 2 + q["radius"], q)
            for b in hg.blockers(self.data, self.plot):
                self.assertGreater(hg.rect_dist(b["rect"], x, y), q["radius"], (q, b["id"]))
            self.assertIn(q["kind"], next(s["kinds"] for s in self.data["scatter"] if s["id"] == q["id"]))

    def test_the_drop_off_station(self):
        drop = next(p for p in self.rep["props"] if p["id"] == "garden_dropoff")
        self.assertEqual(drop["at"], [62, 24])  # design doc section 6: Garden drop-off (62, 24)
        self.assertEqual(drop["station"], "GardenDropOff")

    def test_the_herb_route_matches_the_doc(self):
        rt = self.rep["route"]
        self.assertEqual((rt["doc_m"], rt["doc_s"]), (94.0, 20.9))  # design doc section 7
        self.assertLessEqual(abs(rt["time_s"] - 20.9), 1.0)
        pts = self.data["route"]["points"]
        self.assertEqual(pts[0], pts[-1])
        self.assertIn([58.8, 12], pts)  # through the greenhouse door (58, 12)

    def test_the_paths_are_painted(self):
        self.assertEqual(hg.ground_zone_problems(self.data, self.plot), [])

    def test_the_glass_roof(self):
        roof = self.rep["roof"]
        ids: dict[str, int] = {}
        for p in roof:
            ids[p["id"]] = ids.get(p["id"], 0) + 1
        # 16 x 12 m: 8 bays along each eave, 3 rows of 2 m up each slope, 8 ridge pieces, per gable 3 rows x 2 slopes
        self.assertEqual(ids, {"glass_roof_eave_2m": 16, "glass_roof_2x2": 48, "glass_roof_ridge_2m": 8,
                               "glass_gable_tri_2m_up": 6, "glass_gable_tri_2m_down": 6, "glass_gable_band_2m": 12})
        r = self.layout["spec"]["grid"]["gable_rise_per_m"]
        h0 = self.layout["spec"]["grid"]["glass_wall_h_m"]
        ridge = [p for p in roof if p["id"] == "glass_roof_ridge_2m"]
        self.assertTrue(all(math.isclose(p["h"], h0 + 6 * r) and p["y"] == 12 for p in ridge))
        for p in roof:
            if p["id"].startswith("glass_gable"):
                self.assertIn(p["x"], (58, 74))
                self.assertLessEqual(p["h"] + 2 * r, h0 + 6 * r + 1e-6)  # no gable piece over the ridge

    def test_the_gable_rafter_rule(self):
        roof = [{"id": "glass_roof_2x2", "x": 58, "y": 6, "h": 2.4, "turn": 0},
                {"id": "glass_roof_2x2", "x": 74, "y": 18, "h": 2.4, "turn": 180}]
        self.assertEqual(len(hg.gable_gaps(self.data, roof)), 2)
        closed = roof + [{"id": "glass_roof_2x2", "x": 74, "y": 6, "h": 2.4, "turn": 0},
                         {"id": "glass_roof_2x2", "x": 58, "y": 18, "h": 2.4, "turn": 180}]
        self.assertEqual(hg.gable_gaps(self.data, closed), [])


class Rules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.plot = hg.load(), ho.load()

    def test_a_prop_on_a_path_is_refused(self):
        data = copy.deepcopy(self.data)
        data["props"].append({"id": "crate", "size": [1.0, 1.0, 1.0], "at": [[56, 10]]})
        self.assertTrue(any("crate" in p and "blocks the path" in p for p in hg.check(data, self.plot)))

    def test_a_flat_prop_on_a_path_is_fine(self):
        data = copy.deepcopy(self.data)
        data["props"].append({"id": "mat", "size": [1.0, 0.02, 1.0], "at": [[56, 10]], "flat": True})
        self.assertFalse(any("mat" in p for p in hg.check(data, self.plot)))

    def test_a_long_route_fails(self):
        data = copy.deepcopy(self.data)
        data["route"]["points"] = data["route"]["points"] + [[39, 48.2], [39, 38.2]]
        self.assertFalse(hg.route(data)["ok"])

    def test_a_detached_path_is_found(self):
        data = copy.deepcopy(self.data)
        data["paths"].append({"id": "island", "paint": "worn", "width": 1.4, "line": [[48, 4], [50, 4]]})
        self.assertIn("paths: island does not join the network", hg.network_problems(data))

    def test_rect_line_distance(self):
        self.assertEqual(hg.rect_line_dist([0, 0, 1, 1], [[-1, 0.5], [2, 0.5]]), 0.0)
        self.assertAlmostEqual(hg.rect_line_dist([0, 0, 1, 1], [[3, 0], [3, 1]]), 2.0)

    def test_too_tight_a_scatter_is_reported(self):
        data = copy.deepcopy(self.data)
        data["scatter"][0]["count"] = 500
        _, probs = hg.scatter(data, self.plot)
        self.assertTrue(any("garden_tree: room for" in p for p in probs))


if __name__ == "__main__":
    unittest.main()
