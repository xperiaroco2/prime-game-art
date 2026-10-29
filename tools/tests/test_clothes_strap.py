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


    def test_smooth_keeps_the_ends_and_flattens(self):
        v = S.smooth_open([0.0, 1.0, 0.0, 1.0, 0.0], 20)
        self.assertEqual((v[0], v[-1]), (0.0, 0.0))
        self.assertLess(max(v), 0.3)


class Frame(unittest.TestCase):
    def test_sides_point_across(self):
        _t, cs, ns = arc_path()
        for s in S.frames(cs, ns):
            self.assertAlmostEqual(abs(s[0]), 1.0, places=6)  # the strip's width runs along x


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


if __name__ == "__main__":
    unittest.main()
