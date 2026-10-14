"""The House's per-room wall paint (Q11 = B, docs/house.md "Wall paint"): house.toml's [wall_paint], its checks, the
room scenes' metadata and what the kit's material gets (house_layout.paint_request, kit_materials.gd `paint`)."""
import copy
import json
import tempfile
import tomllib
import unittest
from pathlib import Path

from runner import house_layout as hl

TEAL, OXBLOOD, INK = "#3a6264", "#69413c", "#1f2a48"
TERRACOTTA, GREIGE = "#a3533b", "#d9d1c5"  # #152
SAND, CREAM = "#d8c7b4", "#e4d9c6"  # #152: the ceiling, the sofa body


class WallPaintTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = hl.load(hl.LAYOUT_DIR)

    def test_the_engineers_paints(self):
        """Q11 B's per-room paint with the engineer's choice of 2026-10-14 (#152) over its teal base."""
        paint = self.data["settings"]["wall_paint"]
        self.assertEqual(paint["living_room"], TERRACOTTA)
        for rid in ("kitchen", "hallway", "dining_room", "landing", "stairs"):
            self.assertEqual(paint[rid], GREIGE, rid)
        self.assertNotIn(TEAL, paint.values())
        self.assertEqual(paint["bedroom"], OXBLOOD)
        self.assertEqual(paint["guest_room"], OXBLOOD)
        self.assertEqual([r for r, h in paint.items() if h == INK], ["study"])
        self.assertEqual(hl.check_paints(self.data), [])
        self.assertEqual(paint["wc"], "#cfd5d3")  # #158: soft blue-grey
        self.assertEqual(paint["pantry"], "#d3d6c3")  # #158: pale sage
        self.assertEqual(paint["bathroom"], "#d8dfd6")  # #162: pale green-grey over the white tiles
        self.assertEqual(paint["kids_room"], "#c9d7de")  # #166: a pale sky blue beside the greige landing

    def test_checks(self):
        bad = copy.deepcopy(self.data)
        bad["settings"]["wall_paint"] = {"nowhere": TEAL, "kitchen": "teal", "terrace": TEAL}
        problems = "\n".join(hl.check_paints(bad))
        self.assertIn("no room nowhere", problems)
        self.assertIn("kitchen's paint 'teal'", problems)
        self.assertIn("terrace is open", problems)
        self.assertTrue(any("wall_paint" in p for p in hl.validate(bad)))

    def test_ceiling_and_sofa_colours(self):
        """#152: the warm sand ceiling (the kit's `ceiling` role) and the cream sofa body (`upholstery_warm`)."""
        root = Path(__file__).resolve().parents[2]
        kit = json.loads((root / "kits" / "house.json").read_text(encoding="utf-8"))
        self.assertEqual(kit["roles"]["ceiling"]["hex"].lower(), SAND)
        lib = tomllib.loads((root / "props" / "library.toml").read_text(encoding="utf-8"))
        self.assertEqual(lib["roles"]["upholstery_warm"]["hex"].lower(), CREAM)

    def test_request(self):
        req = hl.paint_request(self.data)
        self.assertEqual(req["kit_hex"], TEAL)
        rooms = {r["room"]: r for r in req["rooms"]}
        self.assertNotEqual(rooms["kitchen"]["to"], req["from"])  # greige over the kit's teal (#152)
        self.assertNotEqual(rooms["bedroom"]["to"], req["from"])
        study = next(r for lv in self.data["levels"] for r in lv["rooms"] if r["id"] == "study")
        x, y, w, d = study["rect"]
        self.assertEqual(rooms["study"]["rect"], [x, y, x + w, y + d])
        self.assertEqual(rooms["study"]["band"], [3.1, 6.3])  # the second floor: 3.2 - 0.1 to 3.2 + 3.1
        self.assertLessEqual(len(req["rooms"]), 16)  # kit_set.gdshader's MAX_PAINTS
        self.assertEqual(hl.walk_request(self.data)["paints"], req)

    def test_scenes(self):
        planned = hl.plan(self.data)
        with tempfile.TemporaryDirectory() as tmp:
            hl.write_scenes(self.data, planned, Path(tmp))
            bedroom = (Path(tmp) / "upper" / "bedroom.tscn").read_text(encoding="utf-8")
            kids = (Path(tmp) / "upper" / "kids_room.tscn").read_text(encoding="utf-8")
        head = bedroom.split("\n\n")[2]  # the root node's block (after the header and the resources)
        self.assertIn(f'metadata/wall_paint = "{OXBLOOD}"', head)
        self.assertIn('metadata/wall_paint = "#c9d7de"', kids.split("\n\n")[2])  # #166

    def test_godot_side(self):
        shader = (hl.ROOT / "godot" / "kit" / "kit_set.gdshader").read_text(encoding="utf-8")
        mats = (hl.ROOT / "godot" / "kit" / "kit_materials.gd").read_text(encoding="utf-8")
        walk = (hl.ROOT / "godot" / "house" / "walk.gd").read_text(encoding="utf-8")
        for name in ("paint_count", "paint_from", "paint_rect", "paint_band", "paint_to"):
            self.assertIn(f"uniform", shader)
            self.assertIn(name, shader)
            self.assertIn(f'"{name}"', mats)
        self.assertIn("const int MAX_PAINTS = 16;", shader)
        self.assertIn("KitMaterials.paint(", walk)


if __name__ == "__main__":
    unittest.main()
