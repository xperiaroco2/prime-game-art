"""M19 (art #196): tools/blender/alien_mouth_fit_geom.py, the AI mouth route's fit without Blender: the lip line of a
closed form, the alignment onto our socket, the back closed into the skin, the wrap weight, the decimate ratio and the
mirror error; M20's lip line, closed jaw weight and corner sink; M20d's centre curve. Plain Python."""
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


def curved_lips(n: int = 40):
    """lips() with its groove bent: the line at height 0.4 + 0.1 x^2 (the ends higher, a smile)."""
    pts = []
    for i in range(n + 1):
        x = -1.0 + 2.0 * i / n
        seam = 0.4 + 0.1 * x * x
        for j in range(n + 1):
            z = j / n
            u = z / seam if z <= seam else (z - seam) / (1.0 - seam)
            pts.append((x, -0.3 * math.sin(math.pi * u) * (1.2 - x * x), z))
    return pts


class LipLineTest(unittest.TestCase):
    def test_follows_a_curved_groove(self):
        knots = G.lip_line(curved_lips(), columns=10, reach=0.8, bins=50)
        self.assertEqual(len(knots), 12)
        for x, z in knots[2:-2]:
            self.assertAlmostEqual(z, 0.4 + 0.1 * x * x, delta=0.035)
        self.assertLess(G.line_at(knots, 0.0), G.line_at(knots, 0.6))

    def test_symmetric_and_held_beyond_the_ends(self):
        knots = G.lip_line(curved_lips(), columns=10, reach=0.8, bins=50)
        for (xa, za), (xb, zb) in zip(knots, reversed(knots)):
            self.assertAlmostEqual(xa, -xb, places=6)
            self.assertAlmostEqual(za, zb, places=9)
        self.assertEqual(G.line_at(knots, -5.0), knots[0][1])
        self.assertEqual(G.line_at(knots, 5.0), knots[-1][1])


class JawClosedTest(unittest.TestCase):
    JAW = {"from": 0.45, "corner": 0.3}

    def test_below_moves_above_stays(self):
        knots = [(-1.0, 0.4), (1.0, 0.4)]
        self.assertAlmostEqual(G.jaw_closed((0.0, 0.0, 0.1), knots, 0.0, 1.0, 0.05, self.JAW), 1.0)
        self.assertAlmostEqual(G.jaw_closed((0.0, 0.0, 0.8), knots, 0.0, 1.0, 0.05, self.JAW), 0.0)
        self.assertAlmostEqual(G.jaw_closed((0.0, 0.0, 0.4), knots, 0.0, 1.0, 0.05, self.JAW), 0.5)

    def test_corners_fall_off(self):
        knots = [(-1.0, 0.4), (1.0, 0.4)]
        self.assertAlmostEqual(G.jaw_closed((1.0, 0.0, 0.1), knots, 0.0, 1.0, 0.05, self.JAW), 0.3)
        self.assertAlmostEqual(G.jaw_closed((0.4, 0.0, 0.1), knots, 0.0, 1.0, 0.05, self.JAW), 1.0)


class CornerSinkTest(unittest.TestCase):
    def test_zero_inside_full_at_the_corner(self):
        self.assertEqual(G.corner_sink(0.5, 0.0, 1.0, depth=0.002, start=0.6), 0.0)
        self.assertAlmostEqual(G.corner_sink(-1.0, 0.0, 1.0, depth=0.002, start=0.6), 0.002)
        mid = G.corner_sink(0.8, 0.0, 1.0, depth=0.002, start=0.6)
        self.assertTrue(0.0 < mid < 0.002)


class StretchTest(unittest.TestCase):
    def test_about_the_line_and_from_the_front(self):
        out = G.stretch([(0.5, 0.0, 1.0), (0.2, 0.4, -1.0)], 0.0, 0.0, 1.5, 1.25)
        self.assertEqual(out, [(0.5, 0.0, 1.5), (0.2, 0.5, -1.5)])

    def test_below_only(self):
        out = G.stretch_below([(0.0, 0.1, 0.3), (0.0, 0.1, -0.2)], 0.1, 2.0)
        self.assertEqual(out[0], (0.0, 0.1, 0.3))
        self.assertAlmostEqual(out[1][2], -0.5)


class PlaneTest(unittest.TestCase):
    """M20b: the AI form's own mirror plane found and put on x = 0 before the mirror (PR #260's review major 1)."""

    def form(self):  # a lopsided-free form: a symmetric cloud about x = 0
        return [(sx * x, y, z) for x in (0.004, 0.011, 0.019) for y in (0.0, 0.003, 0.006) for z in (-0.01, 0.0, 0.012)
                for sx in (-1.0, 1.0)] + [(0.0, 0.002, 0.004)]

    def test_reflect_and_to_plane_are_consistent(self):
        p = (0.01, 0.002, 0.3)
        self.assertEqual(G.reflect(p, 0.0, 0.0), (-0.01, 0.002, 0.3))
        q = G.reflect(G.reflect(p, 0.003, 2.0), 0.003, 2.0)
        for a, b in zip(p, q):
            self.assertAlmostEqual(a, b)
        x, y, z = G.to_plane([G.reflect(p, 0.003, 2.0)], 0.003, 2.0)[0]
        x0, y0, z0 = G.to_plane([p], 0.003, 2.0)[0]
        self.assertAlmostEqual(x, -x0)
        self.assertAlmostEqual(y, y0)

    def test_finds_a_shifted_turned_plane(self):
        a = math.radians(2.0)
        moved = [(x * math.cos(a) - y * math.sin(a) + 0.003, x * math.sin(a) + y * math.cos(a), z) for x, y, z in self.form()]

        def nearest(q):
            return min(math.dist(q, r) for r in moved)

        x0, yaw, err = G.best_plane(moved, nearest, span=0.005, step=0.0005, yaws=(-2.0, 0.0, 2.0))
        self.assertAlmostEqual(x0, 0.003, delta=1e-4)
        self.assertEqual(yaw, 2.0)
        self.assertLess(err, 1e-4)
        back = G.to_plane(moved, x0, yaw)
        self.assertLess(G.mirror_error(back), 3e-4)


class ContactDistanceTest(unittest.TestCase):
    def test_inside_touches(self):
        self.assertEqual(G.contact_distance(0.0035, True), 0.0)
        self.assertEqual(G.contact_distance(0.0035, False, 0.001), 0.0025)
        self.assertEqual(G.contact_distance(0.0005, False, 0.001), 0.0)


class CentreTest(unittest.TestCase):
    """M20d (brief UPDATE 49): smooth_centre's even curve and the contact margin's range."""

    def test_the_curve_through_both_points(self):
        self.assertAlmostEqual(G.centre_target(0.002, 0.0096, 0.0035, 0.0088, 0.002), 0.0096)
        self.assertAlmostEqual(G.centre_target(0.002, 0.0096, 0.0035, 0.0088, 0.0035), 0.0088)
        f = lambda x: 0.01 - 80.0 * x * x  # an even front, the centre the deepest
        self.assertAlmostEqual(G.centre_target(0.002, f(0.002), 0.0035, f(0.0035), 0.0), f(0.0))
        self.assertAlmostEqual(G.centre_target(0.002, f(0.002), 0.0035, f(0.0035), 0.001), f(0.001))

    def test_a_notch_lies_behind_the_curve(self):
        # M20c's rest 3 mm under the lip line (mm): x = 0 at 11.5, +-2 at 9.6, +-3.5 at 8.8: about 1.5 mm behind
        self.assertGreater(0.0115 - G.centre_target(0.002, 0.0096, 0.0035, 0.0088, 0.0), 0.0014)

    def test_the_contact_margin_keeps_the_halo(self):
        # PR #262's fresh review major: 2 mm narrowed the halo (the skin under the lower lip paler); 3.5-5 mm
        self.assertGreaterEqual(G.FIT["contact_margin"], 0.0035)
        self.assertLessEqual(G.FIT["contact_margin"], 0.005)
        self.assertLessEqual(G.FIT["centre_band"], G.FIT["centre_ref"][0])  # no step at the band's edge
        self.assertLess(G.FIT["centre_ref"][0], G.FIT["centre_ref"][1])


if __name__ == "__main__":
    unittest.main()
