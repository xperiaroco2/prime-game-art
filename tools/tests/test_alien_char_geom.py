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



class B2(unittest.TestCase):
    def test_the_panel_is_the_throat_at_the_ring_and_flares_into_the_chest(self) -> None:
        self.assertGreater(G.front_panel(0.03, 0.0, -1.0, 1.0, 0.035), 0.5)
        self.assertLess(G.front_panel(0.06, 0.0, -1.0, 1.0, 0.035), 0.01)  # the neck's sides stay skin
        self.assertGreater(G.front_panel(0.075, 0.13, -1.0, 1.0, 0.035), 0.5)  # the chest panel is wider
        self.assertEqual(G.front_panel(0.0, 0.40, -1.0, 1.0, 0.035), 0.0)  # faded out below the chest
        self.assertEqual(G.front_panel(0.0, 0.10, 1.0, 1.0, 0.035), 0.0)  # the back
        self.assertEqual(G.front_panel(0.0, 0.10, -1.0, 0.0, 0.035), 0.0)  # the arms' skin
        self.assertEqual(G.front_panel(0.0, -0.01, -1.0, 1.0, 0.035), 0.0)  # above the ring

    def test_the_flare_only_pushes_out_and_leaves_the_ring(self) -> None:
        self.assertEqual(G.flare_radius(0.055, 0.055, 0.0, 1.5, 0.09, 0.08, 0.0), 0.055)
        out = G.flare_radius(0.056, 0.055, 0.08, math.pi / 2, 0.09, 0.08, 0.0)
        self.assertGreater(out, 0.10)  # the side: the trapezius
        front = G.flare_radius(0.056, 0.055, 0.08, 0.0, 0.09, 0.08, 0.0)
        self.assertLess(front, out)  # the throat flares less
        self.assertEqual(G.flare_radius(0.3, 0.055, 0.08, math.pi / 2, 0.09, 0.08, 0.0), 0.3)  # the shoulder: kept
        self.assertEqual(G.flare_radius(0.056, 0.055, 0.2, math.pi / 2, 0.09, 0.08, 0.0), 0.056)  # below the fade
        self.assertEqual(G.flare_radius(0.056, 0.055, 0.08, math.pi / 2, 0.09, 0.08, 1.0), 0.056)  # the arm
        for dz in (0.001, 0.02, 0.05, 0.09, 0.11):
            self.assertGreaterEqual(G.flare_radius(0.056, 0.055, dz, 1.0, 0.09, 0.08, 0.3), 0.056)

    def test_the_flare_sides(self) -> None:
        self.assertAlmostEqual(G.flare_side(0.0), G.FLARE_SIDE[0])
        self.assertAlmostEqual(G.flare_side(math.pi), G.FLARE_SIDE[1])
        self.assertAlmostEqual(G.flare_side(math.pi / 2), 1.0)

    def test_a_bridge_triangle_faces_away_from_the_axis(self) -> None:
        self.assertTrue(G.bridge_outward((0.0, -1.0, 0.0), (0.0, -0.05), (0.0, 0.0)))
        self.assertFalse(G.bridge_outward((0.0, 1.0, 0.0), (0.0, -0.05), (0.0, 0.0)))

    def test_zip_loops_winds_its_triangles_inward(self) -> None:
        # r2's hole: zip_loops' (a_i, a_i+1, b_j) order, a the upper loop, turns clockwise seen from outside, so the
        # build flips every triangle by bridge_outward
        n = 8
        ang = [2 * math.pi * k / n for k in range(n)]
        pa = [(math.sin(t), -math.cos(t), 1.0) for t in ang]
        pb = [(math.sin(t), -math.cos(t), 0.0) for t in ang]
        tri = G.zip_loops(ang, ang)[0]
        p = [(pa if tri[2 * q] == "a" else pb)[tri[2 * q + 1]] for q in range(3)]
        u = [p[1][k] - p[0][k] for k in range(3)]
        v = [p[2][k] - p[0][k] for k in range(3)]
        nrm = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        c = [sum(q[k] for q in p) / 3 for k in range(3)]
        self.assertFalse(G.bridge_outward(nrm, c, (0.0, 0.0)))


    def test_walk_loop_orders_a_ring_and_refuses_a_branch(self) -> None:
        order = G.walk_loop([(3, 1), (0, 2), (1, 0), (2, 3)])
        self.assertEqual(sorted(order), [0, 1, 2, 3])
        self.assertEqual(len(order), 4)
        with self.assertRaises(ValueError):
            G.walk_loop([(0, 1), (1, 2), (2, 0), (2, 3)])
        with self.assertRaises(ValueError):
            G.walk_loop([(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3)])

    def test_monotone_angles_hold_a_fold_back(self) -> None:
        got = G.monotone_angles([6.0, 0.2, 0.5, 0.45, 1.0, 3.0, 5.5])
        unwrapped = [got[0]] + [g + 2 * math.pi if g < got[0] else g for g in got[1:]]
        self.assertEqual(unwrapped, sorted(unwrapped))
        self.assertAlmostEqual(got[3], 0.5 + 6.0 - 6.0)  # the fold-back vertex takes its predecessor's angle


if __name__ == "__main__":
    unittest.main()
