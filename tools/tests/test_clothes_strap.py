"""The strap rebuild's and the sleeve smoothing's pure maths (tools/blender/clothes_strap.py; art #196, C1e)."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import clothes_strap as S  # noqa: E402


def arc_path(n=21, r=0.1, x=0.1, y0=0.04, z0=1.2):
    """A half circle over the shoulder in the side view, front (-y) to back (+y), its normals outward."""
    ts = [-math.pi / 2 + math.pi * i / (n - 1) for i in range(n)]
    cs = [(x, y0 + r * math.sin(t), z0 + r * math.cos(t)) for t in ts]
    ns = [(0.0, math.sin(t), math.cos(t)) for t in ts]
    return ts, cs, ns


class Path_(unittest.TestCase):
    def test_angle(self):
        self.assertAlmostEqual(S.angle(0.04, 1.3, 0.04, 1.2), 0.0)
        self.assertLess(S.angle(-0.05, 1.2, 0.04, 1.2), 0.0)  # the front is negative

    def test_bins_take_the_median_x(self):
        pts = [(0.10, -0.05, 1.21), (0.12, -0.05, 1.215), (0.5, -0.05, 1.212), (0.11, 0.04, 1.33)]
        bins = S.bin_angles(pts, 0.04, 1.2, -math.pi / 2, math.pi / 2, math.radians(10))
        self.assertEqual(len(bins), 2)
        self.assertAlmostEqual(bins[0][1], 0.12)  # the outlier at 0.5 does not pull the median far
        self.assertAlmostEqual(bins[1][1], 0.11)

    def test_fill_between_and_beyond(self):
        xs = S.fill_bins([(0.0, 1.0), (1.0, 3.0)], [-1.0, 0.5, 2.0])
        self.assertEqual(xs, [1.0, 2.0, 3.0])
        with self.assertRaises(ValueError):
            S.fill_bins([], [0.0])

    def test_smooth_keeps_the_ends_and_flattens(self):
        v = S.smooth_open([0.0, 1.0, 0.0, 1.0, 0.0], 20)
        self.assertEqual((v[0], v[-1]), (0.0, 0.0))
        self.assertLess(max(v), 0.3)


class Frame(unittest.TestCase):
    def test_sides_point_across(self):
        _t, cs, ns = arc_path()
        for s in S.frames(cs, ns):
            self.assertAlmostEqual(abs(s[0]), 1.0, places=6)  # the strip's width runs along x

    def test_coords(self):
        _t, cs, ns = arc_path()
        sides = S.frames(cs, ns)
        al = S.arcs(cs)
        self.assertAlmostEqual(al[-1], math.pi * 0.1, places=2)
        s, lat, h = S.strip_coords((0.11, 0.04, 1.305), cs, sides, ns, al)
        self.assertAlmostEqual(s, al[-1] / 2, places=3)
        self.assertAlmostEqual(abs(lat), 0.01, places=4)
        self.assertAlmostEqual(h, 0.005, places=3)
        s, _lat, _h = S.strip_coords((0.1, -0.2, 1.2), cs, sides, ns, al)
        self.assertLess(s, 0.0)  # beyond the front end


class Delete(unittest.TestCase):
    def test_rules(self):
        self.assertEqual(S.strip_delete((0.1, 0.0, 0.0), 0.3, 0.0175, outer=False), "core")
        self.assertIsNone(S.strip_delete((0.1, 0.02, 0.0), 0.3, 0.0175, outer=False))  # the shirt beside it stays
        self.assertEqual(S.strip_delete((0.1, 0.02, 0.0), 0.3, 0.0175, outer=True), "flap")
        self.assertIsNone(S.strip_delete((0.1, 0.05, 0.0), 0.3, 0.0175, outer=True))  # beyond reach
        self.assertIsNone(S.strip_delete((0.001, 0.0, 0.0), 0.3, 0.0175, outer=False))  # past the front end
        self.assertIsNone(S.strip_delete((0.1, 0.0, 0.08), 0.3, 0.0175, outer=False))  # far above the strip


class Grid(unittest.TestCase):
    def test_quads(self):
        q = S.strip_quads(3, 4)
        self.assertEqual(len(q), 6)
        self.assertEqual(q[0], [0, 1, 5, 4])
        self.assertEqual(max(max(f) for f in q), 11)

    def test_mirror(self):
        self.assertAlmostEqual(S.mirror_v(0.0, 0.2, 0.3, 1.0), 0.2)
        self.assertAlmostEqual(S.mirror_v(0.1, 0.2, 0.3, 1.0), 0.3)
        self.assertAlmostEqual(S.mirror_v(0.15, 0.2, 0.3, 1.0), 0.25)
        self.assertAlmostEqual(S.mirror_v(0.2, 0.2, 0.3, 1.0), 0.2)
        with self.assertRaises(ValueError):
            S.mirror_v(0.1, 0.3, 0.3, 1.0)


class Smooth(unittest.TestCase):
    def test_moves_along_the_normal_only(self):
        pos = [(0.0, 0.0, 0.0), (1.0, 0.3, 0.5), (2.0, 0.0, 0.0)]
        ns = [(0.0, 0.0, 1.0)] * 3
        out = S.normal_step(pos, ns, [[1], [0, 2], [1]], 1.0, pinned={0, 2})
        self.assertEqual(out[0], pos[0])
        self.assertEqual(out[1][:2], (1.0, 0.3))  # no slide across the surface
        self.assertAlmostEqual(out[1][2], 0.0)

    def test_clearance(self):
        self.assertTrue(S.keep_clearance(0.006, 0.005, 0.004))
        self.assertFalse(S.keep_clearance(0.006, 0.003, 0.004))
        self.assertTrue(S.keep_clearance(0.002, 0.002, 0.004))  # never worse than it was
        self.assertFalse(S.keep_clearance(0.002, 0.001, 0.004))


class Back(unittest.TestCase):
    def test_follow_run(self):
        self.assertAlmostEqual(S.follow_run([0.08, 0.1, 0.11, 0.3], 0.1), 0.095)
        self.assertIsNone(S.follow_run([0.3], 0.1))  # nothing near the strap
        self.assertIsNone(S.follow_run([0.07, 0.1, 0.135], 0.1, max_width=0.06))  # the bib: too wide

    def test_clamp_move(self):
        self.assertEqual(S.clamp_move((0, 0, 0), (0, 0, 0.005), 0.01), (0, 0, 0.005))
        self.assertAlmostEqual(S.clamp_move((0, 0, 0), (0, 0, 0.05), 0.01)[2], 0.01)


if __name__ == "__main__":
    unittest.main()
