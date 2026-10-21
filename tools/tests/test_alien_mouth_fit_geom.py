"""M19 (art #196): tools/blender/alien_mouth_fit_geom.py, the AI mouth route's fit without Blender: the lip line of a
closed form, the alignment onto our socket, the back closed into the skin, the wrap weight, the decimate ratio and the
mirror error. Plain Python."""
from __future__ import annotations

import importlib.util
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load():
    spec = importlib.util.spec_from_file_location("alien_mouth_fit_geom",
                                                  ROOT / "tools" / "blender" / "alien_mouth_fit_geom.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


G = load()


def lips(seam: float = 0.4, n: int = 40):
    """Two stacked half-cylinder lips (x across, z up, the front toward -y) meeting in a groove at seam x height 1."""
    pts = []
    for i in range(n + 1):
        x = -1.0 + 2.0 * i / n
        for j in range(n + 1):
            z = j / n
            # the front bulges out (-y) in each lip's middle and comes back to y = 0 at the groove and the ends
            if z <= seam:
                u = z / seam
            else:
                u = (z - seam) / (1.0 - seam)
            pts.append((x, -0.3 * math.sin(math.pi * u) * (1 - x * x), z))
    return pts


class SeamTest(unittest.TestCase):
    def test_groove_found(self):
        for seam in (0.35, 0.45, 0.6):
            self.assertAlmostEqual(G.seam_z(lips(seam)), seam, delta=0.03)

    def test_flat_refused(self):
        with self.assertRaises(ValueError):
            G.seam_z([(0, 0, 0), (1, 0, 0)])


class AlignTest(unittest.TestCase):
    def test_width_centre_line_front(self):
        pts = [(2.0 + 0.5 * x, 1.0 + y, 3.0 + z) for x, y, z in lips()]  # 1.0 wide, centred at x 2
        lo, hi = G.bbox(pts)
        line = G.seam_z(pts)
        s, t = G.align(lo, hi, line, 0.078, 0.01, -0.12)
        out = G.apply(pts, s, t)
        olo, ohi = G.bbox(out)
        self.assertAlmostEqual(ohi[0] - olo[0], 0.078, places=9)
        self.assertAlmostEqual((ohi[0] + olo[0]) / 2, 0.0, places=9)
        self.assertAlmostEqual(olo[1], -0.12, places=9)
        self.assertAlmostEqual(G.seam_z(out), 0.01, delta=0.002)

    def test_zero_width_refused(self):
        with self.assertRaises(ValueError):
            G.align((0, 0, 0), (0, 1, 1), 0.5, 0.07, 0.0, 0.0)


class BackTest(unittest.TestCase):
    def test_back_goes_under_the_skin(self):
        self.assertAlmostEqual(G.close_back(-0.10, 1.0, -0.09, 0.003), -0.087)

    def test_front_and_buried_stay(self):
        self.assertEqual(G.close_back(-0.10, -1.0, -0.09), -0.10)  # front-facing
        self.assertEqual(G.close_back(-0.05, 1.0, -0.09), -0.05)  # already behind the skin
        self.assertEqual(G.close_back(-0.10, 1.0, None), -0.10)  # no skin found


class TaperTest(unittest.TestCase):
    def test_moved_vertex_comes_in(self):
        x, y, z = G.taper_back((0.04, -0.10, 0.02), 1.0, -0.09, (0.0, 0.0), 0.02, 0.003, 0.35)
        self.assertAlmostEqual(y, -0.087)
        k = 1 - 0.35 * 0.013 / 0.02
        self.assertAlmostEqual(x, 0.04 * k)
        self.assertAlmostEqual(z, 0.02 * k)

    def test_at_most_half_and_unmoved_stays(self):
        x, _y, _z = G.taper_back((0.04, -0.20, 0.0), 1.0, -0.09, (0.0, 0.0), 0.01, 0.003, 1.0)
        self.assertAlmostEqual(x, 0.02)
        self.assertEqual(G.taper_back((0.04, -0.10, 0.02), -1.0, -0.09, (0.0, 0.0), 0.02), (0.04, -0.10, 0.02))


class WrapTest(unittest.TestCase):
    def test_front_full_back_none(self):
        self.assertEqual(G.wrap_weight(-1.0, False), 1.0)
        self.assertEqual(G.wrap_weight(1.0, False), 0.0)
        self.assertEqual(G.wrap_weight(-1.0, True), 0.0)
        mid = G.wrap_weight(-0.1, False)
        self.assertTrue(0.0 < mid < 1.0)


class BudgetMirrorTest(unittest.TestCase):
    def test_ratio(self):
        self.assertAlmostEqual(G.decimate_ratio(200000, 6000), 0.03)
        self.assertEqual(G.decimate_ratio(3000, 6000), 1.0)
        with self.assertRaises(ValueError):
            G.decimate_ratio(0)

    def test_mirror(self):
        sym = [(x * 0.01, 0.0, z * 0.01) for x in range(-5, 6) for z in range(3)]
        self.assertAlmostEqual(G.mirror_error(sym), 0.0, places=12)
        bent = sym + [(0.052, 0.0, 0.0)]
        self.assertAlmostEqual(G.mirror_error(bent), 0.002, places=9)


if __name__ == "__main__":
    unittest.main()
