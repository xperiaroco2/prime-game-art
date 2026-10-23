"""The pure maths of the pilot head on the shared body (tools/blender/alien_char_geom.py, art #196 B1)."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import alien_char_geom as G  # noqa: E402


def ring(n, phase=0.0):
    return [(2 * math.pi * (k + phase) / n) % (2 * math.pi) for k in range(n)]


class ZipLoops(unittest.TestCase):
    def check(self, na, nb, pa=0.0, pb=0.0):
        a, b = ring(na, pa), ring(nb, pb)
        tris = G.zip_loops(a, b)
        self.assertEqual(len(tris), na + nb)  # a closed strip between two loops: one triangle per edge
        edges_a, edges_b = set(), set()
        for t in tris:
            vs = [(t[2 * q], t[2 * q + 1]) for q in range(3)]
            self.assertEqual(sorted(x[0] for x in vs).count("a") in (1, 2), True)
            for (la, ia), (lb, ib) in zip(vs, vs[1:] + vs[:1]):
                if la == lb == "a":
                    edges_a.add(frozenset((ia, ib)))
                if la == lb == "b":
                    edges_b.add(frozenset((ia, ib)))
            # every triangle spans a short arc: no corner further than two steps of the coarser loop from another
            angs = [(a if lo == "a" else b)[i] for lo, i in vs]
            span = max(min(abs(x - y), 2 * math.pi - abs(x - y)) for x in angs for y in angs)
            self.assertLess(span, 2 * 2 * math.pi / min(na, nb) + 1e-9)
        self.assertEqual(len(edges_a), na)  # every loop edge used once
        self.assertEqual(len(edges_b), nb)

    def test_equal(self):
        self.check(24, 24)

    def test_unequal(self):
        self.check(24, 61, 0.3, 0.7)
        self.check(73, 24, 0.5, 0.1)

    def test_too_small(self):
        with self.assertRaises(ValueError):
            G.zip_loops([0.0, 1.0], [0.0, 1.0, 2.0])


class Shield(unittest.TestCase):
    def test_inside_front(self):
        self.assertAlmostEqual(G.shield(0.0, 1.0, -1.0, 1.0), 1.0)

    def test_back_side_arm_and_legs(self):
        self.assertEqual(G.shield(0.0, 1.0, 1.0, 1.0), 0.0)  # the back
        self.assertEqual(G.shield(0.0, 1.0, -1.0, 0.0), 0.0)  # an arm (no trunk weight)
        self.assertEqual(G.shield(0.0, 0.5, -1.0, 1.0), 0.0)  # below the crotch
        self.assertEqual(G.shield(0.2, 1.0, -1.0, 1.0), 0.0)  # outside the half-width

    def test_soft_edge(self):
        hw = G.interp(G.SHIELD, 1.0)
        self.assertAlmostEqual(G.shield(hw, 1.0, -1.0, 1.0), 0.5)


class Fit(unittest.TestCase):
    def test_scale_and_ratio(self):
        self.assertAlmostEqual(G.fit_scale(0.2, 0.05), 0.25)
        self.assertAlmostEqual(G.head_ratio(0.3, 0.4), 0.75)
        with self.assertRaises(ValueError):
            G.fit_scale(0.0, 0.05)

    def test_axes_round_trip(self):
        p = (0.1, 0.2, 0.3)
        self.assertEqual(G.blender_to_gltf(G.gltf_to_blender(p)), p)
        self.assertEqual(G.gltf_to_blender((1.0, 2.0, 3.0)), (1.0, -3.0, 2.0))

    def test_fit_lively(self):
        d = {"eyes": {"left": {"centre": [0.2, 0.3, 0.4], "radius": 0.18, "rest": [0, 0, 1],
                               "front_sphere": {"centre": [0.2, 0.3, 0.4], "r": 0.17}}}, "eye_radius": 0.18}
        src, dst = (0.0, 0.05, -0.5), (0.0, 0.04, 1.4)
        f = G.fit_lively(d, 0.3, src, dst)
        e = f["eyes"]["left"]
        # glTF (0.2, 0.3, 0.4) is Blender (0.2, -0.4, 0.3): moved to (0.06, 0.04 + 0.3 * -0.45, 1.4 + 0.3 * 0.8)
        want = G.blender_to_gltf((0.06, 0.04 + 0.3 * (-0.45), 1.4 + 0.3 * 0.8))
        for x, y in zip(e["centre"], want):
            self.assertAlmostEqual(x, y, places=6)
        self.assertAlmostEqual(e["radius"], 0.054)
        self.assertAlmostEqual(e["front_sphere"]["r"], 0.051)
        self.assertEqual(e["rest"], [0, 0, 1])
        self.assertAlmostEqual(f["eye_radius"], 0.054)
        self.assertEqual(d["eyes"]["left"]["radius"], 0.18)  # the input untouched


if __name__ == "__main__":
    unittest.main()
