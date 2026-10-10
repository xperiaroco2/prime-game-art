"""The garden proof's request (art #80, docs/house-garden.md "The proof"): the house scene replaces the grey stand-ins,
the glass roof, props and plants are all placed, every path and the herb route are walked, the ray test covers the
greenhouse, and the pictures the brief asks for are there. Pure Python; the Godot run is `garden --proof`."""

from __future__ import annotations

import unittest
from pathlib import Path

from runner import house_garden as hg, house_garden_scene as hs, house_layout as hl, house_outdoor as ho
from runner.commands import garden as garden_cmd


class GardenScene(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.plot, cls.layout = hg.load(), ho.load(), hl.load()
        cls.rep = hg.build(cls.data, cls.plot, cls.layout)
        plan = ho.plan(cls.plot)
        cls.doc = {"fence": plan["fence"]["pieces"], "openings": plan["openings"], "stairs": plan["stairs"],
                   "props": plan["props"]}  # outdoor.json's keys (house_outdoor.write)
        cls.room = garden_cmd.greenhouse(cls.layout)
        cls.req = hs.request(cls.plot, cls.doc, Path("build"), None, cls.rep, cls.data, cls.room)

    def test_the_house_replaces_the_stand_ins(self):
        ids = {b["id"] for b in self.req["blocks"]}
        self.assertFalse(ids & hs.COVERED)
        self.assertEqual(self.req["house"], hs.HOUSE)

    def test_everything_is_placed(self):
        self.assertEqual(len(self.req["roof"]), len(self.rep["roof"]))
        self.assertTrue(all(r[0] in self.req["pieces"] for r in self.req["roof"]))
        self.assertEqual(len(self.req["props"]), len(self.rep["props"]))
        self.assertEqual(sum(len(v) for v in self.req["plants"].values()), len(self.rep["scatter"]))
        self.assertTrue(all(res.startswith("res://import/plant_") for res in self.req["plants"]))

    def test_flat_and_small_kinds_cast_no_shadow(self):
        off = set(self.req["no_shadow"])
        placed = {p[0] for p in self.req["props"]} | set(self.req["plants"])
        self.assertTrue(off <= placed)
        self.assertIn("res://import/prop_stepping_stone.glb", off)
        self.assertTrue(any(r.startswith("res://import/plant_flower_bed_") for r in off))
        self.assertFalse(any("garden_tree" in r or "hedge" in r for r in off))

    def test_every_path_and_the_route_are_walked(self):
        walks = self.req["walks"]
        for p in self.data["paths"]:
            self.assertIn(p["id"], walks)
        self.assertIn("route_herb", walks)
        self.assertTrue(all(w["must_pass"] for w in walks.values()))

    def test_the_rays_cover_the_greenhouse(self):
        self.assertEqual(self.req["rays"]["rect"], [float(v) for v in self.room["rect"]])
        x, y, w, d = self.room["rect"]
        cx, _, cz = self.req["rays"]["control"]
        self.assertFalse(x <= cx <= x + w and y <= cz <= y + d)

    def test_the_pictures(self):
        names = {v[0] for v in self.req["views"]}
        self.assertTrue({"dropoff", "greenhouse_in", "top_down"} <= names)
        self.assertTrue(any(n.startswith("path_") for n in names))
        for v in self.req["views"]:
            if v[0] not in ("top_down", "greenhouse_in"):
                self.assertAlmostEqual(v[2][1], hs.EYE)


if __name__ == "__main__":
    unittest.main()
