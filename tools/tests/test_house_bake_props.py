"""Lab props in the House's bake (#83; tools/runner/house_bake_props.py, docs/house.md "Baking with lab props")."""

import tempfile
import tomllib
import unittest
from pathlib import Path

from runner import common, house_bake as B, house_bake_props as P, house_layout, house_sky
from runner.commands import _house_bake

MAP = common.ROOT / "props" / "bake" / "kitchen_c2w.toml"


class Mapping(unittest.TestCase):
    def test_committed_map(self):
        m = P.load_map(MAP)
        self.assertEqual(m["label"], "C2-white")
        self.assertIn("fridge", m["props"])
        self.assertEqual([e["room"] for e in m["extra"]], ["kitchen", "kitchen"])
        self.assertEqual(m["extra"][0]["yaw"], 0.0)

    def test_no_map(self):
        self.assertEqual(P.load_map(None), {"label": None, "props": None, "extra": []})

    def test_problems(self):
        with self.assertRaises(ValueError) as e:
            P.check_map({"colour": 1, "props": {"Fridge": "f.glb", "stove": "s.png"},
                         "extra": [{"id": "a", "room": "k", "glb": "a.glb", "at": [0, 0]},
                                   {"id": "b", "room": "k", "glb": "b.glb", "at": [0, 0, 0]},
                                   {"id": "b", "room": "k", "glb": "b.glb", "at": [0, 0, 0]}]})
        for bit in ("unknown key colour", "props.Fridge", "props.stove", "extra[0] a", "extra id b twice"):
            self.assertIn(bit, str(e.exception))


class Swap(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        for f in ("fridge.glb", "stove.glb", "detail/strip.glb", "notes.glb"):
            (self.dir / f).parent.mkdir(parents=True, exist_ok=True)
            (self.dir / f).write_bytes(b"glTF")

    def tearDown(self):
        self.tmp.cleanup()

    def test_by_name(self):
        found = {"fridge": Path("raw/fridge.glb"), "sofa": Path("raw/sofa.glb")}
        got = P.swap(found, {"fridge", "stove", "sofa"}, self.dir, P.load_map(None))
        self.assertEqual(got["swapped"], ["fridge", "stove"])
        self.assertEqual(got["found"]["fridge"], self.dir / "fridge.glb")
        self.assertEqual(got["found"]["stove"], self.dir / "stove.glb")  # a placeholder before: a GLB now
        self.assertEqual(got["found"]["sofa"], Path("raw/sofa.glb"))
        self.assertEqual(found["fridge"], Path("raw/fridge.glb"))  # the caller's table is not changed

    def test_mapped_and_extra(self):
        m = P.check_map({"props": {"fridge": "stove.glb"},
                         "extra": [{"id": "strip", "room": "kitchen", "glb": "detail/strip.glb", "at": [1, 0.9, 0.1]}]})
        got = P.swap({}, {"fridge", "stove"}, self.dir, m)
        self.assertEqual(got["swapped"], ["fridge"])
        self.assertEqual(got["found"], {"fridge": self.dir / "stove.glb", "strip": self.dir / "detail/strip.glb"})

    def test_refusals(self):
        m = P.check_map({"props": {"bath": "fridge.glb", "fridge": "gone.glb"},
                         "extra": [{"id": "stove", "room": "kitchen", "glb": "detail/none.glb", "at": [0, 0, 0]}]})
        with self.assertRaises(ValueError) as e:
            P.swap({}, {"fridge", "stove"}, self.dir, m)
        for bit in ("props.bath: no room dresses it", "extra stove: a dressing prop id", "gone.glb", "none.glb"):
            self.assertIn(bit, str(e.exception))
        with self.assertRaises(ValueError):
            P.swap({}, {"sofa"}, self.dir, P.load_map(None))

    def test_extras_join_their_room(self):
        dressing = {"kitchen": {"room": "kitchen", "resolved": [{"kind": "props", "id": "fridge"}]}}
        extra = [{"id": "strip", "room": "kitchen", "glb": "s.glb", "at": [1.0, 0.9, 0.1], "yaw": 0.0}]
        out = P.add_extras(dressing, extra)
        self.assertEqual([r["id"] for r in out["kitchen"]["resolved"]], ["fridge", "strip"])
        self.assertEqual(len(dressing["kitchen"]["resolved"]), 1)
        with self.assertRaises(ValueError):
            P.add_extras(dressing, [{**extra[0], "room": "attic"}])


class Sheet(unittest.TestCase):
    def test_rows_match_the_preset_review(self):
        rows = P.compare_rows("ground", "high", "sheen12_shadow", "C2-white")
        shot = {r["label"] for r in B.shot_rows("ground", [{"tag": "high", "modes": ["realtime", "baked",
                                                                                      "sheen12_shadow"]}])}
        self.assertEqual([r["title"] for r in rows], ["today baked", "C2-white baked", "C2-white baked + high sheen"])
        self.assertTrue({r["row"] for r in rows} <= shot)
        self.assertEqual(len(P.compare_rows("ground", "low", None, "x")), 2)

    def test_font(self):
        self.assertTrue(all(len(v) == 14 for v in P.FONT.values()))
        self.assertEqual(P.glyph("i"), P.glyph("I"))
        rows = [bytearray(3 * 40) for _ in range(20)]
        P.draw_label(rows, "I")
        self.assertEqual(bytes(rows[6][3 * 10:3 * 11]), b"\xff\xff\xff")  # the I's top bar
        self.assertEqual(bytes(rows[0][0:3]), b"\x00\x00\x00")

    def test_downscale_and_sheet(self):
        px = [(200, 100, 0)] * 8 * 4
        tile = P.downscale(8, 4, px, 4, 2)
        self.assertEqual((len(tile), len(tile[0])), (2, 12))
        self.assertEqual(bytes(tile[1][0:3]), bytes((200, 100, 0)))
        rows = P.sheet([[tile, None]], ["x"], 4, 2)
        self.assertEqual((len(rows), len(rows[0])), (2, 24))
        self.assertEqual(rows[1][-3:], bytes((48, 48, 48)))
        self.assertEqual(P.tile_size(3), (426, 239))


class Compare(unittest.TestCase):
    def test_before_after_files(self):
        lights = tomllib.loads((common.ROOT / "layouts" / "house" / "lights.toml").read_text(encoding="utf-8"))
        data = house_layout.load()
        sheen = lights["presets"]["high"].get("sheen")
        with tempfile.TemporaryDirectory() as tmp:
            before, after = Path(tmp) / "before", Path(tmp) / "after"
            frames = [(before, "ground_high_baked", 60), (after, "ground_high_baked", 120),
                      (after, f"ground_high_{sheen}", 180)]
            for folder, row, grey in frames:
                for ci in range(3):
                    house_sky.write_png(folder / f"{row}_{ci}.png", 64, 36, [bytes([grey] * 64 * 3)] * 36)
            (after / f"ground_high_{sheen}_2.png").unlink()  # a missing frame: a grey tile
            _house_bake.compare(data, lights, ["ground"], "high", after, before, "C2-white")
            w, h, px = B.read_png(after / "before_after.png")
            tw, th = P.tile_size(3)
            self.assertEqual((w, h), (3 * tw, 3 * th))
            self.assertEqual(px[th * w + tw * 2], (120, 120, 120))  # the second row's last tile, its corner
            self.assertEqual(px[2 * th * w + w - 1], (48, 48, 48))
            md = (after / "before_after.md").read_text(encoding="utf-8")
            self.assertIn("| C2-white baked |", md)
            self.assertIn("Reference: `today baked`", md)


if __name__ == "__main__":
    unittest.main()
