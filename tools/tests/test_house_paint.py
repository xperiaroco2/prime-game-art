"""The House's per-room wall paint (Q11 = B, docs/house.md "Wall paint"): house.toml's [wall_paint], its checks, the
room scenes' metadata and what the kit's material gets (house_layout.paint_request, kit_materials.gd `paint`)."""
import copy
import tempfile
import unittest
from pathlib import Path

from runner import house_layout as hl

TEAL, OXBLOOD, INK = "#3a6264", "#69413c", "#1f2a48"


class WallPaintTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = hl.load(hl.LAYOUT_DIR)

    def test_q11_b(self):
        paint = self.data["settings"]["wall_paint"]
        for rid in ("kitchen", "hallway", "living_room", "dining_room", "landing", "stairs"):
            self.assertEqual(paint[rid], TEAL, rid)
        self.assertEqual(paint["bedroom"], OXBLOOD)
        self.assertEqual(paint["guest_room"], OXBLOOD)
        self.assertEqual([r for r, h in paint.items() if h == INK], ["study"])
        self.assertEqual(hl.check_paints(self.data), [])
        self.assertIsNone(hl.wall_paint(self.data, "pantry"))  # not listed: the kit's own

    def test_checks(self):
        bad = copy.deepcopy(self.data)
        bad["settings"]["wall_paint"] = {"nowhere": TEAL, "kitchen": "teal", "terrace": TEAL}
        problems = "\n".join(hl.check_paints(bad))
        self.assertIn("no room nowhere", problems)
        self.assertIn("kitchen's paint 'teal'", problems)
        self.assertIn("terrace is open", problems)
        self.assertTrue(any("wall_paint" in p for p in hl.validate(bad)))

    def test_request(self):
        req = hl.paint_request(self.data)
        self.assertEqual(req["kit_hex"], TEAL)
        rooms = {r["room"]: r for r in req["rooms"]}
        self.assertEqual(rooms["kitchen"]["to"], req["from"])  # teal is the kit's paint
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
            pantry = (Path(tmp) / "ground" / "pantry.tscn").read_text(encoding="utf-8")
        head = bedroom.split("\n\n")[2]  # the root node's block (after the header and the resources)
        self.assertIn(f'metadata/wall_paint = "{OXBLOOD}"', head)
        self.assertNotIn("wall_paint", pantry)

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
