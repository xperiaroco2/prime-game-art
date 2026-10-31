"""Her front bib in motion, the measure's maths (tools/blender/clothes_bibmove_geom.py; art #196, M2m)."""
import sys
import unittest
from pathlib import Path

try:
    import numpy as np
except ImportError:  # the runner's Python is standard library only: the numpy parts run where numpy is
    np = None

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import clothes_bibmove_geom as G  # noqa: E402


def turn(deg: float):
    a = np.radians(deg)
    return np.array([[np.cos(a), -np.sin(a), 0.0], [np.sin(a), np.cos(a), 0.0], [0.0, 0.0, 1.0]])


class Components(unittest.TestCase):
    def test_two_pieces(self):
        lab = G.components(7, [[0, 1, 2], [2, 3], [4, 5, 6]])
        self.assertEqual(lab[0], lab[3])
        self.assertEqual(lab[4], lab[6])
        self.assertNotEqual(lab[0], lab[4])


@unittest.skipUnless(np is not None, "numpy is not installed")
class BibAndStraps(unittest.TestCase):
    def test_front_main_piece_and_others_over_it(self):
        co = np.array([[0.0, -0.1, 1.1], [0.05, -0.1, 1.2], [0.0, 0.1, 1.1], [0.2, -0.1, 1.1],
                       [0.06, -0.11, 1.15], [0.06, -0.11, 1.3], [0.0, -0.1, 0.9]])
        main = np.array([True, True, True, True, False, False, True])
        bib, on = G.bib_and_straps(co, main, 0.09, 1.0)
        self.assertEqual(bib.tolist(), [0, 1])
        self.assertEqual(on.tolist(), [4])  # 5 is over the bib's top


@unittest.skipUnless(np is not None, "numpy is not installed")
class RigidFit(unittest.TestCase):
    def test_a_turned_moved_panel_has_no_bend(self):
        a = np.random.default_rng(1).normal(size=(30, 3))
        b = a @ turn(25).T + np.array([0.1, -0.2, 0.3])
        r, t, res = G.rigid_fit(a, b)
        self.assertLess(res.max(), 1e-9)
        self.assertTrue(np.allclose(r, turn(25)))

    def test_a_fold_shows(self):
        a = np.array([[x, 0.0, z] for x in (0.0, 0.1, 0.2) for z in (0.0, 0.1, 0.2)])
        b = a.copy()
        b[a[:, 2] > 0.15, 1] += 0.02  # the top row bent out 2 cm
        self.assertGreater(G.rigid_fit(a, b)[2].max(), 0.005)


@unittest.skipUnless(np is not None, "numpy is not installed")
class Slip(unittest.TestCase):
    def setUp(self):
        self.co0 = np.array([[0.0, 0.0, 0.0], [0.1, 0.0, 0.0], [0.0, 0.0, 0.1], [0.03, -0.01, 0.03]])
        self.pairs = [(3, [0, 1, 2], [0.4, 0.3, 0.3])]

    def test_moving_with_the_bib_is_no_slip(self):
        co = self.co0 @ turn(30).T + 0.05
        r = G.rigid_fit(self.co0[:3], co[:3])[0]
        self.assertLess(G.slip(self.co0, co, self.pairs, r), 1e-9)

    def test_sliding_on_it_is(self):
        co = self.co0.copy()
        co[3, 2] += 0.01
        self.assertAlmostEqual(G.slip(self.co0, co, self.pairs, np.eye(3)), 0.01)


class ConceptRatio(unittest.TestCase):
    def test_share_of_the_span(self):
        self.assertAlmostEqual(G.concept_ratio(1.2, 1.4, 1.0), 0.5)
        self.assertAlmostEqual(G.concept_ratio(336.0, 290.0, 443.0), 107 / 153)  # image rows grow downward


if __name__ == "__main__":
    unittest.main()
