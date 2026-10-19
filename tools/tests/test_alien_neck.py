"""The alien neck's column profile (art #196, S9c): the shape-preserving cubic through the column's four points never
overshoots, holds the column's radius between its foot and its head, and the throat panel's settings stay sane.
alien_neck.py runs inside Blender; its pure functions are loaded here with stub Blender modules."""
from __future__ import annotations

import importlib.util
import math
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load():
    stubs = {}
    for name in ("bmesh", "mathutils", "mathutils.bvhtree"):
        if name not in sys.modules:
            stubs[name] = sys.modules[name] = types.ModuleType(name)
    sys.modules["mathutils"].Vector = getattr(sys.modules["mathutils"], "Vector", object)
    sys.modules["mathutils.bvhtree"].BVHTree = getattr(sys.modules["mathutils.bvhtree"], "BVHTree", object)
    try:
        spec = importlib.util.spec_from_file_location("alien_neck", ROOT / "tools" / "blender" / "alien_neck.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        for name in stubs:
            del sys.modules[name]


class AlienNeckColumn(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.n = _load()

    def curve(self, xs, ys, d0, d1, steps=200):
        ds = self.n._pchip(xs, ys, d0, d1)
        return [(x, self.n._hermite(xs, ys, ds, x)) for x in
                (xs[0] + (xs[-1] - xs[0]) * i / steps for i in range(steps + 1))]

    def test_back_profile_no_overshoot(self):
        # the back at S9c: shoulders 83.9 mm at 1.30 falling, the column 46.5 -> 45, the skull 56.5 rising
        xs, ys = [1.30, 1.36, 1.458, 1.498], [0.0839, 0.0465, 0.0450, 0.0565]
        pts = self.curve(xs, ys, -0.6, 0.9)
        for x, y in pts:
            self.assertGreaterEqual(y, min(ys) - 1e-6)
            self.assertLessEqual(y, max(ys) + 1e-6)
        col = [y for x, y in pts if xs[1] <= x <= xs[2]]
        self.assertLess(max(col) - min(col), 0.0016)  # near-parallel: the column varies by its taper only
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):  # monotone down to the column's head, then up
            if x1 <= xs[2]:
                self.assertLessEqual(y1, y0 + 1e-9)
            elif x0 >= xs[2]:
                self.assertGreaterEqual(y1, y0 - 1e-9)

    def test_end_slopes_limited(self):
        ds = self.n._pchip([0.0, 1.0, 2.0], [0.0, 1.0, 2.0], 10.0, -1.0)
        self.assertAlmostEqual(ds[0], 3.0)  # Fritsch-Carlson: at most three times the secant
        self.assertEqual(ds[-1], 0.0)  # a slope against the secant is dropped

    def test_column_radius_table(self):
        n = self.n
        angles = [a for a, _f, _h in n.COL_R]
        self.assertEqual(angles, sorted(angles))
        self.assertEqual((angles[0], angles[-1]), (0, 180))
        for a in (10, 75, 135, 170):  # symmetric left and right, the foot never thinner than the head
            f, h = n._col_r(math.radians(a))
            f2, h2 = n._col_r(math.radians(-a))
            self.assertAlmostEqual(f, f2)
            self.assertAlmostEqual(h, h2)
            self.assertGreaterEqual(f, h)
        f, h = n._col_r(math.pi)
        self.assertTrue(0.043 <= h <= 0.047)  # rf2 and u1: the nape about 45 mm behind the ring's axis

    def test_throat_panel(self):
        p = self.n.PANEL
        self.assertTrue(80.0 <= p["edge"] <= 95.0)  # the front half of the neck
        (f0, f1), (s0, s1) = p["top"]
        self.assertLess(s1, f1)  # the panel ends lower at the side than at the front (the jaw's corner)
        self.assertLess(p["jaw"]["deg"][1], p["edge"])  # the jaw's pale never shows from behind


if __name__ == "__main__":
    unittest.main()
