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
        # E1: a degenerate body face (zero normal) is skipped; a cloth vertex without a normal picks nothing
        self.assertEqual(F.pick_facing([(0.001, (0.0, 0.0, 0.0), 3), (0.02, (0.0, 0.0, 1.0), 4)], (0.0, 0.0, 1.0)), 4)
        self.assertIsNone(F.pick_facing([(0.01, (0.0, 0.0, 1.0), 1)], (0.0, 0.0, 0.0)))
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
        self.assertTrue(F.in_shoe(1.0, 0.12, 0.08, rim=0.126))   # by the heel: under the rim's high point
        self.assertFalse(F.in_shoe(1.0, 0.12, 0.08, rim=0.085))  # the ankle over the side's low rim shows
        self.assertFalse(F.in_shoe(0.3, 0.05, 0.10, rim=0.12))   # mostly shin

    def test_through_shoe(self):
        self.assertTrue(F.through_shoe(0.016, 0.03))    # the foot's side 16 mm through the shoe's side
        self.assertFalse(F.through_shoe(-0.004, 0.03))  # inside the shoe
        self.assertFalse(F.through_shoe(0.0005, 0.03))  # within the tolerance
        self.assertFalse(F.through_shoe(0.008, 0.005))  # by the rim: the ankle over the opening
        self.assertFalse(F.through_shoe(0.05, 0.03))    # far off the shoe: no foot of this shoe

    def test_local_rim(self):
        self.assertAlmostEqual(F.local_rim([0.13, 0.125, 0.14], 0.004), 0.121)
        self.assertIsNone(F.local_rim([]))  # the toe box: no opening above
        with self.assertRaises(ValueError):
            F.local_rim([0.1], -0.001)

    def test_sure_faces_skip_the_erosion(self):
        faces = [[0, 1], [1, 2], [2, 3]]
        nbrs = [[1], [0, 2], [1]]
        cov = [False, True, True, True]
        self.assertEqual(F.covered_faces(faces, cov, nbrs, erode=1), [False, False, True])
        sure = [False, True, True, False]
        self.assertEqual(F.covered_faces(faces, cov, nbrs, erode=1, vert_sure=sure), [False, True, True])
        self.assertEqual(F.covered_faces(faces, [False] * 4, nbrs, erode=1, vert_sure=sure), [False, True, False])


class UnderCloth(unittest.TestCase):
    def test_hidden_for_certain(self):
        self.assertTrue(F.under_cloth(-0.005, 0.15, "UpperChest"))    # the upper back, 15 cm from the collar
        self.assertFalse(F.under_cloth(0.002, 0.15, "UpperChest"))    # outside the cloth at rest
        self.assertFalse(F.under_cloth(-0.005, 0.05, "Chest"))        # by an opening
        self.assertFalse(F.under_cloth(-0.005, 0.15, "RightHand"))    # leaves the cuff when the wrist bends
        self.assertFalse(F.under_cloth(-0.005, 0.15, "Neck"))         # the neck over the collar
        # the skin under a strap's base: 5 cm from the collar, cut on a Shoulder bone only with its own limit
        self.assertFalse(F.under_cloth(-0.005, 0.05, "LeftShoulder"))
        self.assertTrue(F.under_cloth(-0.005, 0.05, "LeftShoulder", away_shoulder=0.04))
        self.assertFalse(F.under_cloth(-0.005, 0.03, "RightShoulder", away_shoulder=0.04))
        self.assertFalse(F.under_cloth(-0.005, 0.05, "Chest", away_shoulder=0.04))

    def test_shoe_face(self):
        self.assertTrue(F.shoe_face([True, False, False], [True, True, True]))    # half through the shoe's side
        self.assertFalse(F.shoe_face([False, False, False], [True, True, True]))  # inside the shoe: kept
        self.assertFalse(F.shoe_face([True, False, False], [True, True, False]))  # reaches over the rim
        with self.assertRaises(ValueError):
            F.shoe_face([True], [True, True])


class ExposedSkin(unittest.TestCase):
    def test_the_neck_over_the_collar(self):
        self.assertTrue(F.exposed_skin(0.079, 1.337, 0.83, 1.126))   # the neck 79 mm over the collar's top roll
        self.assertTrue(F.exposed_skin(0.066, 1.256, 0.38, 1.100))   # in a jump, the collar lower
        self.assertFalse(F.exposed_skin(0.015, 1.337, 0.83, 1.126))  # shallow: a real crossing at the collar
        self.assertFalse(F.exposed_skin(0.022, 1.170, 0.05, 1.126))  # the upper back between the straps: sideways
        self.assertFalse(F.exposed_skin(0.030, 0.740, 0.60, 1.126))  # the crotch: below the chest
        with self.assertRaises(ValueError):
            F.exposed_skin(0.05, 1.39, 0.8, 1.13, deep=-0.01)


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


class DeepExit(unittest.TestCase):
    def test_short_way_out_only(self):
        self.assertTrue(F.deep_exit(0.015, 0.025))    # the elbow: 15 mm to the back, 25 mm out the front
        self.assertTrue(F.deep_exit(0.005, 0.035))    # a forearm crossed at a slant
        self.assertFalse(F.deep_exit(0.002, 0.04))    # past twice the depth and the slack
        self.assertFalse(F.deep_exit(0.002, 0.08))    # a collar fold: across the whole neck
        self.assertFalse(F.deep_exit(0.04, 0.06))     # never past 5 cm


class BoundaryVerts(unittest.TestCase):
    def test_open_edges(self):
        self.assertEqual(F.boundary_verts([[0, 1, 2], [0, 2, 3]]), {0, 1, 2, 3})  # a quad of two triangles: its rim
        tet = [[0, 1, 2], [0, 3, 1], [1, 3, 2], [2, 3, 0]]
        self.assertEqual(F.boundary_verts(tet), set())  # closed
        self.assertEqual(F.boundary_verts(tet[:3]), {0, 2, 3})  # the missing face's rim


class AnkleKept(unittest.TestCase):  # E1b: the collar's shards
    def test_open_skin_just_over_the_rim_is_kept(self):
        self.assertTrue(F.ankle_kept(0.10, 0.09, 0.02))
        self.assertTrue(F.ankle_kept(0.09, 0.09, 0.02))  # on the rim itself

    def test_under_the_rim_or_far_over_it_is_left_to_the_other_rules(self):
        self.assertFalse(F.ankle_kept(0.08, 0.09, 0.02))
        self.assertFalse(F.ankle_kept(0.14, 0.09, 0.02))

    def test_no_rim_near_or_off(self):
        self.assertFalse(F.ankle_kept(0.10, None, 0.02))
        self.assertFalse(F.ankle_kept(0.10, 0.09, 0.08))
        self.assertFalse(F.ankle_kept(0.10, 0.09, 0.02, keep=0.0))


class AnkleRide(unittest.TestCase):  # E1b: the skin under the collar rides with the shoe
    def test_under_the_rim_all_over_the_band_none(self):
        self.assertEqual(F.ankle_ride(0.08, 0.09), 1.0)
        self.assertEqual(F.ankle_ride(0.085, 0.09), 1.0)
        self.assertEqual(F.ankle_ride(0.115, 0.09), 0.0)
        self.assertAlmostEqual(F.ankle_ride(0.1, 0.09), 0.5)

    def test_no_band_refused(self):
        with self.assertRaises(ValueError):
            F.ankle_ride(0.1, 0.09, band=0.0)


if __name__ == "__main__":
    unittest.main()
