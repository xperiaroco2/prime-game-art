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
    def test_the_throat_fade_is_a_soft_tongue_from_the_throat_to_the_sternum(self) -> None:
        hw = 0.045
        self.assertGreater(G.throat_fade(0.0, 0.01, 1.0, hw), 0.99)  # the throat's centre at the ring
        self.assertGreater(G.throat_fade(0.03, 0.01, 1.0, hw), 0.9)  # the head's throat width carried down
        self.assertEqual(G.throat_fade(0.06, 0.01, 1.0, hw), 0.0)  # the neck's sides stay skin
        self.assertGreater(G.throat_fade(0.0, 0.10, 1.0, hw), 0.4)  # still pale halfway to the sternum
        self.assertEqual(G.throat_fade(0.0, 0.23, 1.0, hw), 0.0)  # gone below the sternum
        self.assertEqual(G.throat_fade(0.0, 0.10, -1.0, hw), 0.0)  # the back
        self.assertEqual(G.throat_fade(0.0, -0.01, 1.0, hw), 0.0)  # above the ring: the head's own mask
        self.assertEqual(G.throat_fade(0.0, 0.05, 1.0, 0.0), 0.0)  # a head without a pale throat

    def test_the_throat_fade_widens_downward(self) -> None:
        edge = [max(x / 1000 for x in range(200)
                    if G.throat_fade(x / 1000, dz, 1.0, 0.045) > 0.5 * G.throat_fade(0.0, dz, 1.0, 0.045))
                for dz in (0.02, 0.08, 0.14)]
        self.assertLess(edge[0], edge[1])
        self.assertLess(edge[1], edge[2])

    def test_the_throat_fade_has_no_hard_edge(self) -> None:
        # the largest change over 2 mm anywhere on the front: a feathered mask moves by a few percent at most
        worst = 0.0
        for i in range(0, 120):
            x = i / 1000
            for j in range(-10, 260, 2):
                dz = j / 1000
                for c in (1.0, 0.6, 0.4, 0.2):
                    v = G.throat_fade(x, dz, c, 0.045)
                    worst = max(worst, abs(G.throat_fade(x + 0.002, dz, c, 0.045) - v),
                                abs(G.throat_fade(x, dz + 0.002, c, 0.045) - v))
        self.assertLess(worst, 0.35)  # the ring's 8 mm onset is the steepest step: 0.002 / 0.008 of a smoothstep

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

    def test_monotone_angles_take_a_fold_back_across_zero_as_one_turn(self) -> None:
        """B4 review (d): the walk passes angle 0, folds back across it (6.25 after 0.05) and goes on."""
        got = G.monotone_angles([3.0, 4.0, 5.0, 6.2, 0.05, 6.25, 0.3, 1.0, 2.0])
        unwrapped = [got[0]] + [g + 2 * math.pi if g < got[0] else g for g in got[1:]]
        self.assertEqual(unwrapped, sorted(unwrapped))
        self.assertLess(unwrapped[-1] - unwrapped[0], 2 * math.pi)  # one turn, not two
        # by hand: the shorter turns give 6.2 + 0.1332 = 0.05 + 2 pi (6.333), then -0.083 to 6.25, held at 6.333 by its
        # predecessor, then +0.333 from 6.25 to 0.3 + 2 pi (6.583); taken back into [0, 2 pi): 0.05, 0.05, 0.3
        self.assertEqual([round(u, 3) for u in unwrapped[4:7]], [6.333, 6.333, 6.583])
        for i, want in ((0, 3.0), (3, 6.2), (4, 0.05), (5, 0.05), (6, 0.3), (7, 1.0), (8, 2.0)):
            self.assertAlmostEqual(got[i], want, msg=f"vertex {i}")

    def test_the_default_build_paints_the_front_with_the_throat_fade(self) -> None:
        """B4 review (e): the shield only behind --shield (off by default); the default path is throat_fade."""
        src = (Path(G.__file__).parent / "alien_char_build.py").read_text(encoding="utf-8")
        self.assertIn('ap.add_argument("--shield", action="store_true")', src)
        self.assertRegex(src, r"if a\.shield:\n\s+tf = t\[:, 10\]\n\s+else:\n\s+tf = .*G\.throat_fade\(")




def _rig(thigh, shin, ankle):
    """A rig's leg heads, both sides alike: the hip at thigh + shin + ankle over the floor, straight down."""
    heads = {}
    for side, x in (("Left", 0.1), ("Right", -0.1)):
        heads[f"{side}Foot"] = (x, 0.0, ankle)
        heads[f"{side}LowerLeg"] = (x, 0.0, ankle + shin)
        heads[f"{side}UpperLeg"] = (x, 0.0, ankle + shin + thigh)
    heads["Hips"] = (0.0, 0.0, ankle + shin + thigh + 0.02)
    return heads


class LegFit(unittest.TestCase):
    def test_shorter_legs_scale_down(self):
        # T2: M1f's legs (0.774 m) on S4b's clips (0.845 m)
        fit = G.leg_fit(_rig(0.36, 0.34, 0.074), _rig(0.39, 0.37, 0.085))
        self.assertEqual(fit["leg_m"], [0.845, 0.774])
        self.assertAlmostEqual(fit["scale"], 0.774 / 0.845, places=6)

    def test_same_legs_leave_the_keys(self):
        self.assertEqual(G.leg_fit(_rig(0.4, 0.4, 0.08), _rig(0.4, 0.4, 0.08))["scale"], 1.0)

    def test_missing_leg_bone_is_refused(self):
        rig = _rig(0.4, 0.4, 0.08)
        del rig["LeftFoot"]
        with self.assertRaises(ValueError):
            G.leg_fit(rig, _rig(0.4, 0.4, 0.08))


class FootIK(unittest.TestCase):
    """T3: the feet on the donor's paths by IK (alien_leg_fit.py --leg-fit-mode ik)."""

    def test_planted_donor_foot_gives_a_planted_target(self):
        own, donor = (0.09, 0.0, 0.06), (0.1, 0.0, 0.08)
        a = G.foot_target(own, donor, (0.1, 0.3, 0.08), 0.9)
        b = G.foot_target(own, donor, (0.1, 0.3, 0.08), 0.9)
        self.assertEqual(a, b)
        for x, y in zip(a, (0.09, 0.27, 0.06)):
            self.assertAlmostEqual(x, y, places=9)

    def test_moves_scale_with_the_legs(self):
        own, donor = (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
        p = G.foot_target(own, donor, (0.0, 1.0, 0.2), 0.5)
        self.assertAlmostEqual(p[1], 0.5)
        self.assertAlmostEqual(p[2], 0.1)

    def test_knee_reaches_the_target_with_its_lengths(self):
        hip, knee, target = (0.0, 0.0, 1.0), (0.0, -0.1, 0.6), (0.0, 0.1, 0.3)
        k, ok = G.reach_knee(hip, knee, target, 0.4, 0.42)
        self.assertTrue(ok)
        self.assertAlmostEqual(math.dist(hip, k), 0.4, places=9)
        self.assertAlmostEqual(math.dist(k, target), 0.42, places=9)

    def test_knee_keeps_the_clips_side(self):
        # the clip's knee in front (-y): the solved knee stays in front, never flips behind
        hip, target = (0.0, 0.0, 1.0), (0.0, 0.0, 0.35)
        k, _ = G.reach_knee(hip, (0.0, -0.05, 0.6), target, 0.4, 0.42)
        self.assertLess(k[1], 0.0)
        k, _ = G.reach_knee(hip, (0.0, 0.05, 0.6), target, 0.4, 0.42)
        self.assertGreater(k[1], 0.0)

    def test_out_of_reach_is_reported_and_straight(self):
        hip, target = (0.0, 0.0, 1.0), (0.0, 0.0, 0.0)
        k, ok = G.reach_knee(hip, (0.0, -0.01, 0.6), target, 0.4, 0.42)
        self.assertFalse(ok)
        self.assertLess(G.knee_angle(hip, k, (0.0, 0.0, 1.0 - 0.82 * 0.9995)), 5.0)

    def test_straight_knee_uses_the_fallback_pole(self):
        hip, target = (0.0, 0.0, 1.0), (0.0, 0.0, 0.3)
        k, _ = G.reach_knee(hip, (0.0, 0.0, 0.6), target, 0.4, 0.42, fallback_pole=(0.0, -1.0, 0.0))
        self.assertLess(k[1], 0.0)
        with self.assertRaises(ValueError):
            G.reach_knee(hip, (0.0, 0.0, 0.6), target, 0.4, 0.42)

    def test_knee_angle(self):
        self.assertAlmostEqual(G.knee_angle((0, 0, 1), (0, 0, 0.5), (0, 0, 0)), 0.0, places=6)
        self.assertAlmostEqual(G.knee_angle((0, 0, 1), (0, 0, 0.5), (0, 0.5, 0.5)), 90.0, places=6)



def _trs(t=(0.0, 0.0, 0.0), yaw_deg=0.0, s=1.0):
    c, n = math.cos(math.radians(yaw_deg)) * s, math.sin(math.radians(yaw_deg)) * s
    return [[c, -n, 0.0, t[0]], [n, c, 0.0, t[1]], [0.0, 0.0, s, t[2]], [0.0, 0.0, 0.0, 1.0]]


class ChainWorld(unittest.TestCase):
    """F1: the leg fit's donor world frame from saved transforms, not from an unevaluated matrix_world."""
    I = _trs()

    def close(self, a, b):
        for ra, rb in zip(a, b):
            for x, y in zip(ra, rb):
                self.assertAlmostEqual(x, y, places=9)

    def test_root_is_its_basis(self):
        b = _trs((0.1, -2.0, 0.5), 30.0, 1.2)
        self.close(G.chain_world([(self.I, b)]), b)

    def test_parent_chain(self):
        parent, child = _trs((1.0, 0.0, 0.0), 90.0), _trs((0.0, 2.0, 0.0))
        w = G.chain_world([(self.I, parent), (self.I, child)])
        self.close(w, _trs((-1.0, 0.0, 0.0), 90.0))  # the child's +y 2 m turned onto -x by the parent
        # parented with the parent's inverse kept (Blender's Ctrl+P): the child stays where its basis puts it
        inv = _trs((0.0, 0.0, 0.0), -90.0)
        inv[0][3], inv[1][3] = 0.0, 1.0  # the inverse of a 90 deg turn about z after a 1 m move along x
        self.close(G.mat_mul(parent, inv), self.I)
        self.close(G.chain_world([(self.I, parent), (inv, child)]), child)

    def test_no_object(self):
        with self.assertRaises(ValueError):
            G.chain_world([])



class SeamSmoothTest(unittest.TestCase):
    """Clothes step 2 (art #196): the weld's seam smoothed by Taubin steps in a band round the bridge."""

    def test_weight_is_one_at_the_bridge_and_zero_outside_the_band(self) -> None:
        self.assertEqual(G.seam_weight(1.394, 1.394), 1.0)
        self.assertEqual(G.seam_weight(1.394 - G.SEAM_SMOOTH[0], 1.394), 0.0)
        self.assertEqual(G.seam_weight(1.394 + G.SEAM_SMOOTH[1] + 0.001, 1.394), 0.0)
        self.assertGreater(G.seam_weight(1.40, 1.394), G.seam_weight(1.405, 1.394))

    def test_taubin_flattens_a_step_and_keeps_pinned_points(self) -> None:
        # a ring of points with one dented point: smoothing lifts the dent, pinned points stay
        import math
        n = 24
        co = [[math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n), 0.0] for i in range(n)]
        co[0] = [0.9, 0.0, 0.0]
        nbrs = [[(i - 1) % n, (i + 1) % n] for i in range(n)]
        w = [1.0] * n
        w[12] = 0.0
        out = G.taubin(co, nbrs, w)
        self.assertGreater(out[0][0], 0.95)
        self.assertEqual(out[12], co[12])
        radii = [math.hypot(p[0], p[1]) for p in out[1:]]
        self.assertGreater(min(radii), 0.97)  # the inflating step keeps the girth
        self.assertEqual(co[0], [0.9, 0.0, 0.0])

class NormalBandTest(unittest.TestCase):
    """E1m: the flared neck's normals fade over the flare, and the gate's move above the band is measured."""

    def test_weld_keeps_the_normal_band(self):
        self.assertAlmostEqual(G.normal_top(1.0, 0.02), 1.02)

    def test_flare_fades_over_the_whole_flare(self):
        ring, cut = 1.0, 1.008
        top = G.normal_top(cut, 0.02, ring + 0.07)
        self.assertAlmostEqual(top, 1.07)
        # 28 mm above the ring (the old switch) the head's own normals are not yet in full
        self.assertLess(G.sstep(cut, top, ring + 0.028), 0.5)
        self.assertEqual(G.sstep(cut, top, top), 1.0)
        self.assertEqual(G.sstep(cut, top, cut), 0.0)

    def test_flare_never_shorter_than_the_band(self):
        self.assertAlmostEqual(G.normal_top(1.0, 0.02, 1.005), 1.02)

    def test_moved_above(self):
        src = [(0, 0, 0.5), (0, 0, 1.2), (0, 0, 1.5)]
        dst = [(0.3, 0, 0.5), (0, 0.004, 1.2), (0, 0, 1.5)]
        self.assertAlmostEqual(G.moved_above(src, dst, 1.0), 0.004)
        self.assertEqual(G.moved_above(src, src, 1.0), 0.0)
        self.assertEqual(G.moved_above([], [], 1.0), 0.0)


if __name__ == "__main__":
    unittest.main()
