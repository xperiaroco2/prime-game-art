"""The clothes step 2 (art #196): tools/blender/clothes_geom.py, the pure maths of the view cutter, the skin test
and the fit numbers. Plain Python."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("clothes_geom", ROOT / "tools" / "blender" / "clothes_geom.py")
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)


class ClothesGeomTest(unittest.TestCase):
    def test_spans_join_small_gaps_and_drop_specks(self):
        occ = [False] * 5 + [True] * 50 + [False] * 3 + [True] * 20 + [False] * 30 + [True] * 5 + [False] * 40
        occ += [True] * 60
        self.assertEqual(G.spans(occ, min_gap=8, min_width=40), [(5, 78), (153, 213)])

    def test_spans_empty(self):
        self.assertEqual(G.spans([False] * 10), [])

    def test_common_square_holds_every_box_with_margin(self):
        side = G.common_square([(0, 0, 300, 880), (10, 5, 330, 870)], margin=0.05)
        self.assertEqual(side, 968)

    def test_place_centres_across_and_keeps_the_ground(self):
        self.assertEqual(G.place((100, 50, 400, 950), 1000, 960), (350, 60))
        x, y = G.place((7, 3, 108, 803), 1000, 960)
        self.assertEqual(y + 800, 960)

    def test_skin_colours(self):
        for rgb in [(0.27, 0.62, 0.58), (0.62, 0.82, 0.74), (0.18, 0.45, 0.43)]:  # teal, mint, shaded teal
            self.assertTrue(G.is_skin(*rgb), rgb)

    def test_cloth_colours(self):
        for rgb in [(0.16, 0.22, 0.38), (0.95, 0.95, 0.93), (0.12, 0.14, 0.26), (0.45, 0.08, 0.14),
                    (0.90, 0.88, 0.80), (0.45, 0.52, 0.62), (0.05, 0.06, 0.06),
                    (0.12, 0.20, 0.23)]:  # the last: dark denim near the skin's hue
            self.assertFalse(G.is_skin(*rgb), rgb)

    def test_majority(self):
        self.assertTrue(G.majority([True, True, False]))
        self.assertFalse(G.majority([True, False]))
        self.assertFalse(G.majority([]))

    def test_band(self):
        self.assertEqual(G.band([0.1, -0.3, 0.25, 0.9], -0.5, 0.5), (-0.3, 0.25))
        self.assertIsNone(G.band([2.0], 0.0, 1.0))

    def test_fit_lines(self):
        out = G.fit_lines({"height": 1.9, "hip": 0.4, "x": 1}, {"height": 2.0, "hip": 0.4})
        self.assertEqual(out["height"], {"cloth": 1.9, "body": 2.0, "diff": -0.1, "ratio": 0.95})
        self.assertEqual(sorted(out), ["height", "hip"])

    def test_centre_run_leaves_out_the_arms(self):
        xs = [-0.30, -0.29, -0.15 + 0.001, -0.10, -0.05, 0.0, 0.06, 0.12, 0.16, 0.27, 0.31]
        self.assertEqual(G.centre_run(xs, gap=0.06), (-0.149, 0.16))
        self.assertIsNone(G.centre_run([]))

    def test_centre_run_default_gap_spans_a_decimated_torso(self):
        # vertices 4-5 cm apart across the torso (B's 2 cm gap stopped after one step); the arm 9 cm off stays out
        xs = [-0.30, -0.24, -0.165, -0.12, -0.07, -0.02, 0.03, 0.08, 0.125, 0.17, 0.26]
        self.assertEqual(G.CENTRE_GAP, 0.06)
        self.assertEqual(G.centre_run(xs), (-0.165, 0.17))

    def test_span(self):
        self.assertEqual(G.span([]), 0.0)
        self.assertAlmostEqual(G.span([0.1, -0.2, 0.05]), 0.3)

    def test_skin_mask_matches_is_skin(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy is not installed")
        import random
        rnd = random.Random(7)
        rgb = [(rnd.random(), rnd.random(), rnd.random()) for _ in range(4000)]
        rgb += [(0.2, 0.6, 0.55), (0.12, 0.15, 0.2), (0.9, 0.9, 0.9), (0.0, 0.0, 0.0)]
        got = G.skin_mask(np.array(rgb)).tolist()
        self.assertEqual(got, [G.is_skin(*c) for c in rgb])


if __name__ == "__main__":
    unittest.main()
