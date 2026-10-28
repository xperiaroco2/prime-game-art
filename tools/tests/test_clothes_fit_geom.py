"""The clothes fit's pure maths (tools/blender/clothes_fit_geom.py; art #196 clothes step 2, C1)."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import clothes_fit_geom as F  # noqa: E402


def rot_z(a, t=(0.0, 0.0, 0.0)):
    c, s = math.cos(a), math.sin(a)
    return [[c, -s, 0.0, t[0]], [s, c, 0.0, t[1]], [0.0, 0.0, 1.0, t[2]]]


class Swing(unittest.TestCase):
    def test_arm_down(self):
        axis, ang = F.swing((1, 0, 0), (1, 0, -1))
        self.assertAlmostEqual(ang, math.pi / 4)
        self.assertAlmostEqual(axis[1], 1.0)  # about +y: +x turns toward -z

    def test_parallel_and_opposite(self):
        self.assertEqual(F.swing((0, 0, 2), (0, 0, 1))[1], 0.0)
        with self.assertRaises(ValueError):
            F.swing((1, 0, 0), (-1, 0, 0))


class FitDistance(unittest.TestCase):
    def test_loose_comes_in_but_stays_loose(self):
        self.assertAlmostEqual(F.fit_distance(0.04, 0.01, 0.25, 0.005), 0.0175)

    def test_inside_goes_out(self):
        self.assertEqual(F.fit_distance(-0.02, 0.01, 0.25, 0.005), 0.005)
        self.assertEqual(F.fit_distance(0.007, 0.01, 0.25, 0.005), 0.007)

    def test_monotone(self):
        xs = [i / 1000 for i in range(-30, 80)]
        ys = [F.fit_distance(x, 0.01, 0.3, 0.004) for x in xs]
        self.assertEqual(ys, sorted(ys))

    def test_bad(self):
        with self.assertRaises(ValueError):
            F.fit_distance(0.0, 0.01, 1.5, 0.0)
        with self.assertRaises(ValueError):
            F.fit_distance(0.0, 0.01, 0.5, 0.02)


class Smooth(unittest.TestCase):
    def test_spike_spreads_and_mask(self):
        nb = [[1], [0, 2], [1]]
        out = F.smooth([[0.0], [3.0], [0.0]], nb, 1, 0.5)
        self.assertEqual([round(v[0], 6) for v in out], [1.5, 1.5, 1.5])
        held = F.smooth([[0.0], [3.0], [0.0]], nb, 5, 0.5, mask=[0.0, 1.0, 0.0])
        self.assertEqual(held[0], [0.0])

    def test_lonely_vertex_kept(self):
        self.assertEqual(F.smooth([[2.0, 1.0]], [[]], 3, 1.0), [[2.0, 1.0]])

    def test_bad_alpha(self):
        with self.assertRaises(ValueError):
            F.smooth([[0.0]], [[]], 1, 1.5)


class Weights(unittest.TestCase):
    def test_limit(self):
        row = F.limit({"a": 0.5, "b": 0.2, "c": 0.1, "d": 0.1, "e": 0.1, "f": 0.0})
        self.assertEqual(len(row), 4)
        self.assertAlmostEqual(sum(row.values()), 1.0)
        self.assertEqual(F.limit({"a": 0.0}), {})


class Skinning(unittest.TestCase):
    def test_invert(self):
        m = rot_z(0.7, (0.1, -0.2, 0.3))
        p = (0.3, 0.4, 0.5)
        q = F.apply(F.invert(m), F.apply(m, p))
        for a, b in zip(p, q):
            self.assertAlmostEqual(a, b)
        with self.assertRaises(ValueError):
            F.invert([[0.0] * 4 for _ in range(3)])

    def test_unskin_round_trip(self):
        mats = {"a": rot_z(0.3), "b": rot_z(-0.5, (0.0, 0.1, 0.0))}
        row = {"a": 0.25, "b": 0.75}
        rest = (0.2, -0.1, 0.4)
        posed = F.apply(F.blend(row, mats), rest)
        for x, y in zip(rest, F.unskin(posed, row, mats)):
            self.assertAlmostEqual(x, y)

    def test_no_weight_is_identity(self):
        self.assertEqual(F.unskin((1.0, 2.0, 3.0), {}, {}), (1.0, 2.0, 3.0))


class Covered(unittest.TestCase):
    def test_erode(self):
        faces = [[0, 1], [1, 2], [2, 3]]
        nbrs = [[1], [0, 2], [1]]
        cov = [True, True, True, True]
        self.assertEqual(F.covered_faces(faces, cov, nbrs, erode=0), [True, True, True])
        self.assertEqual(F.covered_faces(faces, cov, nbrs, erode=1), [True, True, True])
        cov[0] = False
        self.assertEqual(F.covered_faces(faces, cov, nbrs, erode=1), [False, False, True])

    def test_frame_max(self):
        r = F.frame_max([(0, 0.0), (5, 0.002), (3, 0.004)])
        self.assertEqual((r["max_count"], r["max_depth_m"], r["worst_frame"]), (5, 0.004, 1))
        self.assertEqual(F.frame_max([])["frames"], 0)


class Facing(unittest.TestCase):
    def test_inner_sleeve_takes_the_arm(self):
        # the torso's side faces +x (outward), nearer; the arm's inner side faces -x, like the sleeve's inner side
        cands = [(0.02, (1.0, 0.0, 0.0), 7), (0.03, (-1.0, 0.0, 0.0), 9)]
        self.assertEqual(F.pick_facing(cands, (-1.0, 0.0, 0.0)), 9)
        self.assertEqual(F.pick_facing(cands, (1.0, 0.0, 0.0)), 7)

    def test_none_and_bad(self):
        self.assertIsNone(F.pick_facing([(0.01, (0.0, 0.0, 1.0), 1)], (0.0, 0.0, -1.0)))
        self.assertIsNone(F.pick_facing([], (0.0, 0.0, 1.0)))
        with self.assertRaises(ValueError):
            F.pick_facing([], (0.0, 0.0, 1.0), 2.0)


class Rigid(unittest.TestCase):
    def test_foot_and_toes_only(self):
        r = F.rigid({"LeftFoot": 0.3, "LeftToes": 0.1, "LeftLowerLeg": 0.6}, ("LeftFoot", "LeftToes"), "LeftFoot")
        self.assertAlmostEqual(r["LeftFoot"], 0.75)
        self.assertAlmostEqual(r["LeftToes"], 0.25)
        self.assertNotIn("LeftLowerLeg", r)

    def test_default_and_bad(self):
        self.assertEqual(F.rigid({"LeftLowerLeg": 1.0}, ("LeftFoot",), "LeftFoot"), {"LeftFoot": 1.0})
        with self.assertRaises(ValueError):
            F.rigid({}, ("LeftFoot",), "LeftToes")


class Hug(unittest.TestCase):
    def test_ramp(self):
        self.assertEqual(F.hug_weight(0.0), 0.0)
        self.assertEqual(F.hug_weight(-0.02), 0.0)
        self.assertEqual(F.hug_weight(0.02), 1.0)
        self.assertTrue(0.0 < F.hug_weight(0.006) < 1.0)
        self.assertLess(F.hug_weight(0.005), F.hug_weight(0.007))
        with self.assertRaises(ValueError):
            F.hug_weight(0.01, 0.01, 0.01)


class Shoe(unittest.TestCase):
    def test_top_skips_the_sole(self):
        # the sole's open edge at 0.01 m is no top; the opening's lowest point 0.11 m less the margin
        self.assertAlmostEqual(F.shoe_top([0.01, 0.12, 0.11, 0.13], 0.01), 0.10)
        self.assertIsNone(F.shoe_top([0.0, 0.02]))
        self.assertIsNone(F.shoe_top([]))
        with self.assertRaises(ValueError):
            F.shoe_top([0.1], -0.01)

    def test_in_shoe(self):
        self.assertTrue(F.in_shoe(1.0, 0.05, 0.10))
        self.assertFalse(F.in_shoe(1.0, 0.12, 0.10))   # the ankle above the top shows
        self.assertFalse(F.in_shoe(0.3, 0.05, 0.10))   # mostly shin
        self.assertFalse(F.in_shoe(1.0, 0.05, None))   # no shoe
        self.assertTrue(F.in_shoe(1.0, 0.12, 0.10, under=True))   # a toe under the toe box, above the top's low point
        self.assertFalse(F.in_shoe(0.3, 0.05, 0.10, under=True))
        self.assertTrue(F.in_shoe(1.0, 0.12, 0.10, toes_weight=0.9))  # a toe through the toe box's coarse faces
        self.assertFalse(F.in_shoe(1.0, 0.05, None, toes_weight=0.9))  # no shoe: the bare toes show
        self.assertTrue(F.in_shoe(1.0, 0.05, None, toes_weight=0.9, shoe=True))  # a shoe without a top found


class RestPoke(unittest.TestCase):
    def test_counts_outside_away_from_openings(self):
        self.assertEqual(F.rest_poke([-5.0, 0.5, 2.0, 3.0], [False, False, False, True]), 1)
        self.assertEqual(F.rest_poke([], []), 0)
        with self.assertRaises(ValueError):
            F.rest_poke([1.0], [])


class LongEdges(unittest.TestCase):
    def test_split_only_the_long(self):
        self.assertEqual(F.long_edges([0.01, 0.05, 0.04, 0.081], 0.04), [1, 3])
        self.assertEqual(F.long_edges([], 0.04), [])
        with self.assertRaises(ValueError):
            F.long_edges([0.1], 0.0)


class FirstExit(unittest.TestCase):
    def test_the_first_leaving_face(self):
        self.assertEqual(F.first_exit([(0.02, 0.9)]), 0)               # out through the near side
        self.assertEqual(F.first_exit([(0.01, -0.5), (0.03, 0.7)]), 1)  # an entering face first (a fold), then out
        self.assertIsNone(F.first_exit([(0.01, -0.2)]))
        self.assertIsNone(F.first_exit([]))


if __name__ == "__main__":
    unittest.main()
