"""The bodies' mm drawing (art #196, step D2): body_dims_geom's row measuring, height map and station heights on
synthetic pictures, the committed dims tables' shape and the neck ring they share, and body_drawing's canvas and
outlines. Plain Python: no Blender, no raw files."""

from __future__ import annotations

import math
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from runner import common

sys.path.insert(0, str(common.ROOT / "tools" / "blender"))
import body_dims_geom as G  # noqa: E402
import body_drawing as D  # noqa: E402
import body_dims_measure as M  # noqa: E402

DIMS = common.ROOT / "tools" / "blender" / "body_dims"
GROUND, SKIN, SUIT = (184, 183, 182), (99, 173, 169), (168, 167, 168)


def picture(w, h, shapes, bg=GROUND):
    """Rows of pixels: the ground with filled boxes (x0, y0, x1, y1, colour) painted in order."""
    rows = [[bg] * w for _ in range(h)]
    for x0, y0, x1, y1, c in shapes:
        for y in range(y0, y1):
            for x in range(x0, x1):
                rows[y][x] = c
    return rows


class TestRows(unittest.TestCase):
    def test_runs_close_small_gaps_and_drop_specks(self):
        line = bytearray(b"\x00\x01\x01\x01\x00\x00\x01\x01\x01\x00\x00\x00\x00\x01\x00\x01\x01\x01\x01")
        self.assertEqual(G.runs(line, 0, len(line)), [(1, 8), (13, 18)])
        self.assertEqual(G.runs(line, 0, len(line), gap=0), [(1, 3), (6, 8), (15, 18)])

    def test_mask_fills_a_ground_coloured_highlight_and_drops_the_grey_shadow(self):
        # a grey suit body with a ground-coloured highlight inside, teal feet, a grey shadow beside the feet
        shapes = [(40, 10, 80, 90, SUIT), (50, 30, 60, 40, GROUND), (40, 90, 80, 100, SKIN), (80, 95, 110, 100, (160, 160, 160))]
        m, sole = G.mask(picture(140, 110, shapes), foot_band=15)
        self.assertEqual(sole, 99)
        self.assertEqual(m[35][55], 1)                 # the highlight is figure (enclosed)
        self.assertEqual(m[97][95], 0)                 # the shadow is ground (no colour in the foot band)
        self.assertEqual(G.runs(m[50], 0, 140), [(40, 79)])
        self.assertEqual(sum(m[105]), 0)

    def test_panels_split_the_views(self):
        shapes = [(10, 10, 50, 60, SKIN), (80, 10, 125, 60, SKIN), (150, 10, 190, 60, SKIN)]
        m, _ = G.mask(picture(220, 70, shapes), foot_band=5)
        self.assertEqual(G.panels(m), [(10, 50), (80, 125), (150, 190)])

    def test_png_round_trip(self):
        px = bytearray()
        for y in range(5):
            for x in range(7):
                px += bytes((x * 30, y * 50, 7))
        with tempfile.TemporaryDirectory() as tmp:
            p = G.write_png(Path(tmp) / "t.png", 7, 5, px)
            w, h, rows = G.read_png(p)
        self.assertEqual((w, h), (7, 5))
        self.assertEqual(rows[4][6], (180, 200, 7))


class TestRing(unittest.TestCase):
    def test_ring_is_the_thin_line_under_the_flare_not_the_chin_shadow(self):
        # B's case: a broad dark shadow under the chin, a neck that widens past 1.25 times its narrowest width (the
        # narrow band ends there), then the drawn ring line, 2 px thin, across the widened neck above the shoulders
        dark = (60, 110, 107)
        shapes = [(70, 10, 130, 70, SKIN),                    # head
                  (85, 70, 115, 78, dark),                    # the chin's shadow (8 rows)
                  (85, 78, 115, 100, SKIN),                   # the neck, 30 px
                  (80, 100, 120, 108, SKIN),                  # the flare, 40 px (> 1.25 x 30)
                  (75, 108, 125, 118, SKIN),                  # 50 px
                  (75, 112, 125, 114, dark),                  # the ring line, rows 112 and 113
                  (50, 118, 150, 140, SKIN),                  # shoulders
                  (70, 140, 130, 250, SKIN),                  # trunk
                  (40, 140, 62, 240, SKIN), (138, 140, 160, 240, SKIN),   # arms apart from the trunk
                  (72, 250, 97, 400, SKIN), (103, 250, 128, 400, SKIN)]   # legs
        rows = picture(200, 410, shapes)
        m, sole = G.mask(rows)
        lm = G.landmarks(m, rows, sole, (0, 200))
        self.assertLess(lm["neck_band"][1], 108)          # the band ends at the flare, above the line
        self.assertIn(lm["ring"], (112, 113))
        self.assertGreaterEqual(lm["shoulder_top"], lm["ring"])


class TestHeights(unittest.TestCase):
    def test_zmap_pins_the_landmarks_and_inverts(self):
        to_b, to_c = G.zmap([(0.0, 0.0), (739.0, 745.0), (1390.0, 1390.0)])
        self.assertAlmostEqual(to_b(739.0), 745.0)
        self.assertAlmostEqual(to_b(369.5), 372.5)
        for z in (0.0, 100.0, 745.0, 1000.0, 1390.0):
            self.assertAlmostEqual(to_b(to_c(z)), z)

    def test_station_heights_every_cm_and_half_cm_in_the_fine_bands(self):
        zs = G.station_heights(100.0, [(40.0, 52.0)])
        self.assertEqual(zs[:5], [0.0, 10.0, 20.0, 30.0, 40.0])
        self.assertIn(45.0, zs)
        self.assertIn(50.0, zs)
        self.assertNotIn(55.0, zs)
        self.assertEqual(zs[-1], 100.0)

    def test_scale_maps_the_ring_and_sole(self):
        lm = {"top": 26, "ring": 282, "sole": 999}
        sc = G.scale(lm, 1390.0)
        self.assertAlmostEqual(G.z_of(282, lm, sc), 1390.0)
        self.assertAlmostEqual(G.z_of(999, lm, sc), 0.0)
        self.assertAlmostEqual(G.y_of(695.0, lm, sc), (282 + 999) / 2)

    def test_fit_line(self):
        a, b = G.fit_line([(1 + 0.5 * y, y) for y in range(10)])
        self.assertAlmostEqual(a, 1.0)
        self.assertAlmostEqual(b, 0.5)


class TestTables(unittest.TestCase):
    def load(self, name):
        return tomllib.loads((DIMS / f"{name}.toml").read_text(encoding="utf-8"))

    def test_both_tables_hold_every_section(self):
        for name in ("A", "B"):
            d = self.load(name)
            for key in ("body", "keys", "landmarks_concept", "skeleton", "height_map", "neck_ring", "trunk", "legs",
                        "arms", "hand", "foot", "chest"):
                self.assertIn(key, d, f"{name}: {key}")
            t = d["trunk"]
            n = len(t["z"])
            self.assertTrue(all(len(t[k]) == n for k in G.TRUNK_KEYS), name)
            steps = [b - a for a, b in zip(t["z"], t["z"][1:])]
            self.assertLessEqual(max(steps), 10.0 + 1e-6, name)
            self.assertTrue(any(abs(s - 5.0) < 1e-6 for s in steps), name)
            self.assertEqual(t["z"][-1], d["neck_ring"]["z"], name)
            self.assertEqual(d["hand"]["digits"], 4)

    def test_one_neck_ring_for_both_bodies(self):
        a, b = self.load("A")["neck_ring"], self.load("B")["neck_ring"]
        for key in ("vertices", "centre_y", "half_x", "half_y", "tilt_deg", "head_bone_above", "neck_bone_below"):
            self.assertEqual(a[key], b[key], key)
        self.assertAlmostEqual(b["z"] / a["z"], 0.953, places=3)

    def test_b_is_shorter_and_has_the_chest(self):
        a, b = self.load("A"), self.load("B")
        drop = a["keys"]["height_top"] - b["keys"]["height_top"]
        self.assertGreater(drop, 50.0)
        self.assertTrue(b["chest"]["rounds"])
        self.assertFalse(a["chest"]["rounds"])
        self.assertGreater(b["chest"]["projection"], 5.0)
        self.assertLess(b["keys"]["waist_w"], a["keys"]["waist_w"])

    def test_toml_writer_round_trips(self):
        doc = {"t": {"a": 1, "b": 2.5, "c": None, "d": "x", "e": [float(i) for i in range(40)], "f": [1.0, None]}}
        back = tomllib.loads(M.to_toml(doc, "# head"))["t"]
        self.assertEqual(back["a"], 1)
        self.assertEqual(back["c"], "-")
        self.assertEqual(back["e"], [float(i) for i in range(40)])
        self.assertEqual(back["f"], [1.0, "-"])


class TestDrawing(unittest.TestCase):
    def test_font_has_every_label_glyph(self):
        for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,-:/()=+ %":
            self.assertIn(ch, D.FONT)
            self.assertEqual(len(D.FONT[ch]), 10, ch)

    def test_text_and_lines_ink_the_canvas(self):
        cv = D.Canvas(60, 20)
        end = cv.text(1, 1, "A1", D.INK, 1)
        self.assertEqual(end, 13)
        inked = sum(1 for i in range(0, len(cv.px), 3) if tuple(cv.px[i:i + 3]) == D.INK)
        self.assertEqual(inked, 16 + 10)   # "A" has 16 pixels in the 5 x 7 table, "1" 10
        cv.line((0, 19), (59, 19), D.DIM)
        self.assertEqual(tuple(cv.px[(19 * 60 + 30) * 3:(19 * 60 + 30) * 3 + 3]), D.DIM)

    def test_outlines_are_mirrored_and_reach_the_ring(self):
        d = tomllib.loads((DIMS / "B.toml").read_text(encoding="utf-8"))
        ol = D.outlines(d)
        right, left = ol["front"][0], ol["front"][1]
        self.assertEqual([(-x, z) for x, z in right], left)
        self.assertAlmostEqual(max(z for _, z in right), d["neck_ring"]["z"])
        self.assertTrue(all(math.isfinite(y) for pl in ol["side"] for y, _ in pl))


if __name__ == "__main__":
    unittest.main()
