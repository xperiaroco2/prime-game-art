"""The bodies' new forefoot and neck join (art #196, step D3c): body_feet_geom's profile, rings, mitten front (closed,
consistently wound, to the table's length, width and toe height, the cut's loop unmoved), its smoothing and loop
order; body_fit_geom's neck_join (one smooth slope into the ring, a vertical tangent, no overshoot) and the front and
back's smoothing under the armpit. Plain Python: no Blender, no raw files."""

from __future__ import annotations

import math
import sys
import unittest

from runner import common

sys.path.insert(0, str(common.ROOT / "tools" / "blender"))
import body_feet_geom as FG  # noqa: E402
import body_fit_geom as F  # noqa: E402


def cut_loop(n=32, cx=0.117, y=-0.056, w=0.145, h=0.068):
    """A rounded foot section (m): flat-ish below, a dome above, in order."""
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n
        z = h / 2 + h / 2 * math.sin(a)
        pts.append((cx + w / 2 * math.cos(a), y, max(0.0, z if z > 0.004 else 0.0)))
    return pts


class ProfileTest(unittest.TestCase):
    def test_outline_ends_and_peak(self):
        self.assertAlmostEqual(FG.outline(0.0, 1.0, 2.0, 0.4, 2.2), 1.0)
        self.assertAlmostEqual(FG.outline(0.4, 1.0, 2.0, 0.4, 2.2), 2.0)
        self.assertAlmostEqual(FG.outline(1.0, 1.0, 2.0, 0.4, 2.2), 0.0)
        vals = [FG.outline(t / 100, 1.0, 2.0, 0.4, 2.2) for t in range(101)]
        peak = vals.index(max(vals))
        self.assertTrue(all(a <= b + 1e-12 for a, b in zip(vals[:peak], vals[1:peak + 1])))
        self.assertTrue(all(a >= b - 1e-12 for a, b in zip(vals[peak:], vals[peak + 1:])))

    def test_ring_ts_denser_at_the_tip(self):
        ts = FG.ring_ts(14)
        self.assertEqual(len(ts), 14)
        gaps = [b - a for a, b in zip(ts, ts[1:])]
        self.assertTrue(all(g > 0 for g in gaps))
        self.assertGreater(gaps[0], gaps[-1])
        self.assertLess(ts[-1], 1.0)


class ToeShareTest(unittest.TestCase):
    def test_ahead_of_the_toe_joint_is_toes(self):
        self.assertEqual(FG.toe_share(-0.10, -0.05, 0.0), 1.0)  # well ahead (the front at -y)
        self.assertEqual(FG.toe_share(0.0, -0.05, 0.3), 0.3)  # behind: the nearest old vertex's share
        self.assertAlmostEqual(FG.toe_share(-0.05, -0.05, 0.0), 0.5)
        self.assertEqual(FG.toe_share(-0.10, -0.05, 1.0), 1.0)


class ForefootTest(unittest.TestCase):
    def build(self, n=32):
        loop = cut_loop(n)
        pts, faces = FG.forefoot(loop, -0.176, 0.1667, 0.0872)
        return loop, pts, faces

    def test_table_numbers_and_the_cut_unmoved(self):
        loop, pts, faces = self.build()
        self.assertEqual(pts[:len(loop)], [tuple(p) for p in loop])
        ext = FG.front_extent(pts)
        self.assertAlmostEqual(ext["min_y"], -0.176, places=6)
        self.assertAlmostEqual(ext["width"], 0.1667, delta=0.002)
        self.assertAlmostEqual(ext["top"], 0.0872, delta=0.002)
        self.assertGreaterEqual(ext["sole"], -1e-9)  # nothing sinks under the floor

    def test_closed_and_consistently_wound(self):
        loop, pts, faces = self.build()
        n = len(loop)
        directed = {}
        for f in faces:
            for i, a in enumerate(f):
                e = (a, f[(i + 1) % len(f)])
                self.assertNotIn(e, directed, "an edge runs the same way twice: a flipped face")
                directed[e] = 1
        for (a, b) in list(directed):
            on_cut = a < n and b < n
            if not on_cut:
                self.assertIn((b, a), directed, "an open edge off the cut: a hole")
        cut_edges = [(a, b) for (a, b) in directed if a < n and b < n]
        self.assertEqual(len(cut_edges), n)  # the front meets the cut's every edge once
        for j in range(n):  # opposite the body's face along the cut (B_j -> B_j+1)
            self.assertIn(((j + 1) % n, j), directed)

    def test_doubles_a_sparse_cut_and_not_a_dense_one(self):
        _, pts32, _ = self.build(32)
        _, pts48, _ = self.build(48)
        self.assertEqual(len(pts32), 32 + 14 * 64 + 1)
        self.assertEqual(len(pts48), 48 + 14 * 48 + 1)

    def test_smoothing_keeps_the_front_and_evens_it(self):
        loop, pts, faces = self.build()
        n = len(loop)
        nbr = FG.neighbours(len(pts), faces)
        wt = [0.0] * n + [1.0] * (len(pts) - n)
        sm = FG.taubin(pts, nbr, wt, 12)
        self.assertEqual(sm[:n], pts[:n])
        self.assertLess(FG.dihedral_max(sm, faces), 60.0)  # no fold
        self.assertLess(abs(FG.front_extent(sm)["min_y"] - FG.front_extent(pts)["min_y"]), 0.01)

    def test_laplace_fills_a_dent(self):
        pts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (1.0, -0.5, 0.0)]
        nbr = [[1], [0, 2], [1], []]
        out = FG.laplace([(0, 0, 0), (1, -0.4, 0), (2, 0, 0), pts[3]], nbr, [0, 1, 0, 0], 20)
        self.assertAlmostEqual(out[1][1], 0.0, places=4)

    def test_order_loop(self):
        self.assertEqual(sorted(FG.order_loop([(1, 2), (3, 1), (2, 3)])), [1, 2, 3])
        with self.assertRaises(ValueError):
            FG.order_loop([(0, 1), (1, 2), (2, 0), (5, 6), (6, 7), (7, 5)])
        with self.assertRaises(ValueError):
            FG.order_loop([(0, 1), (1, 2)])

    def test_tip_from_table(self):
        self.assertAlmostEqual(FG.tip_from_table(0.122, 0.2985), -0.1765)


class NeckJoinTest(unittest.TestCase):
    def test_one_smooth_slope_into_the_ring(self):
        ring = 1390.0
        zs = [1200.0 + 5 * i for i in range(39)]
        vals = [-60.0 - 0.3 * (ring - z) for z in zs]  # the fit's front, well ahead of the ring's
        out = F.neck_join(zs, vals, ring, -52.8, 60.0)
        for z, v, o in zip(zs, vals, out):
            if z <= ring - 60:
                self.assertEqual(o, v)
        self.assertAlmostEqual(out[-1], -52.8)
        band = [o for z, o in zip(zs, out) if z >= ring - 60]
        self.assertTrue(all(a <= b + 1e-9 for a, b in zip(band, band[1:])))  # monotone: no ridge, no lip
        self.assertLess(abs(out[-1] - out[-2]), 0.5)  # a vertical tangent at the ring

    def test_no_overshoot_against_the_slope(self):
        ring = 1390.0
        zs = [1300.0 + 5 * i for i in range(19)]
        vals = [-40.0 - 0.5 * (z - 1300) for z in zs]  # a slope away from the ring's value
        out = F.neck_join(zs, vals, ring, -52.8, 60.0)
        band = [o for z, o in zip(zs, out) if z >= ring - 60]
        self.assertTrue(all(min(band[0], -52.8) - 1e-9 <= o <= max(band[0], -52.8) + 1e-9 for o in band))

    def test_front_and_back_smoothing_under_the_armpit(self):
        widths, fronts = F.trunk_sigma(1390.0, 1150.0), F.trunk_sigma(1390.0, 1150.0, at_armpit=False)
        self.assertEqual(widths(900.0), F.SIGMA)
        self.assertEqual(fronts(900.0), F.SIGMA)
        self.assertAlmostEqual(widths(1150.0), F.SIGMA_NECK)
        self.assertAlmostEqual(fronts(1150.0), F.SIGMA_FB_ARMPIT)
        self.assertAlmostEqual(fronts(1385.0), F.SIGMA_NECK)  # the neck band still narrows both


if __name__ == "__main__":
    unittest.main()
