"""The garden's plants (props/plants.toml, tools/blender/plant_geom.py, docs/house-garden.md "The plants"): the mapping
file is clean, every plant the garden places has a build, every plant builds under the vegetation budget at about its
size, a tree's crown leaves the head room over the paths at the garden's smallest scale and it collides with its trunk
only. Pure Python, no Blender."""

from __future__ import annotations

import json
import sys
import unittest

from runner import common, house_garden as hg
from runner.commands import _props

sys.path.insert(0, str(common.ROOT / "tools" / "blender"))
import plant_geom  # noqa: E402
import prop_geom  # noqa: E402

LIB = _props.load(common.ROOT / "props" / "plants.toml")
KIT = json.loads((common.ROOT / LIB["kit_spec"]).read_text(encoding="utf-8"))
SPEC = prop_geom.lib_spec(LIB, KIT)
HEAD_ROOM_M = 2.2  # look.md: a tree's canopy over a path stays above this
SIZE_TOLERANCE = 0.2  # metres a built plant may miss its inventory size by on an axis (a lumpy crown)


class Plants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.built = {p["id"]: plant_geom.build(p, SPEC) for p in LIB["prop"]}

    def test_the_mapping_file_is_clean(self):
        self.assertEqual(_props.check(LIB, _props.sources_index(), KIT), [])
        self.assertTrue((common.ROOT / "tools" / "blender" / LIB["script"]).is_file())

    def test_every_plant_the_garden_places_is_built(self):
        data = hg.load()
        want = {f"{s['id']}_{k}" for s in data["scatter"] for k in s["kinds"]}
        want |= {p["id"] for p in data["props"] if p.get("src") == "garden"}
        self.assertEqual(want - set(self.built), set())

    def test_budget_and_size(self):
        hi = LIB["budgets"]["vegetation"][1]
        for p in LIB["prop"]:
            d = self.built[p["id"]]
            with self.subTest(p["id"]):
                self.assertLessEqual(d["triangles"], hi)
                self.assertTrue(all(abs(e) <= SIZE_TOLERANCE for e in prop_geom.size_error(d, p)),
                                prop_geom.size_error(d, p))
                self.assertEqual(len(d["colliders"]), 1)

    def test_a_tree_leaves_head_room_and_collides_with_its_trunk(self):
        smallest = min(next(s for s in hg.load()["scatter"] if s["id"] == "garden_tree")["scales"])
        for p in LIB["prop"]:
            if p["shape"] != "garden_tree":
                continue
            d = self.built[p["id"]]
            m = d["meshes"][0]
            crown = {i for f, r in zip(m["faces"], m["roles"]) if r != p["roles"][0] for i in f}
            low = min(m["verts"][i][1] for i in crown)
            col = d["collision_bounds_m"]
            with self.subTest(p["id"]):
                self.assertGreaterEqual(low * min(smallest, 1.0), HEAD_ROOM_M)
                self.assertLessEqual(col["max"][1], low + 1e-6)
                self.assertLess(col["max"][0] - col["min"][0], 0.4)


if __name__ == "__main__":
    unittest.main()
