"""The dungarees' shell top, panels and straps: pure maths (tools/blender/clothes_shell.py; art #196, C1f)."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import clothes_shell as H  # noqa: E402


class Regions(unittest.TestCase):
    def test_arm_beyond_the_seam_above_the_armpit(self):
        self.assertEqual(H.region(0.3, 1.27, 0.165, 1.18), H.LEFT)
        self.assertEqual(H.region(-0.3, 1.27, 0.165, 1.18), H.RIGHT)
        self.assertEqual(H.region(0.1, 1.27, 0.165, 1.18), H.TORSO)
        self.assertEqual(H.region(0.17, 1.0, 0.165, 1.18), H.TORSO)  # the hip below the armpit


class Uvs(unittest.TestCase):
    def test_torso_front_centre_mid_island_and_v_by_height(self):
        u, v = H.torso_uv(0.0, -0.1, 1.2, 0.02, 0.0, 0.5, 0.1, 2.0, 1.35)
        self.assertAlmostEqual(u, 0.25)
        self.assertAlmostEqual(v, 0.1 + 0.15 * 2.0)
        ub, _ = H.torso_uv(0.0, 0.2, 1.2, 0.02, 0.0, 0.5, 0.1, 2.0, 1.35)
        self.assertTrue(ub < 1e-9 or ub > 0.5 - 1e-9)  # the back centre is the seam

    def test_arm_v_up_from_the_cuff_both_sides(self):
        for sgn in (1, -1):
            _, v = H.arm_uv(sgn * 0.5, 0.07, 1.3, 0.625, 0.068, 1.277, 0.6, 0.2, 0.0, 2.0)
            self.assertAlmostEqual(v, 0.125 * 2.0)
        u_top, _ = H.arm_uv(0.5, 0.068, 1.32, 0.625, 0.068, 1.277, 0.6, 0.2, 0.0, 2.0)
        self.assertAlmostEqual(u_top, 0.7)  # the top of the arm in the island's middle

    def test_unwrap_keeps_a_face_whole_across_the_seam(self):
        self.assertEqual(H.unwrap([0.1, 0.12, 0.11], 0.0, 0.5), [0.1, 0.12, 0.11])
        us = H.unwrap([0.49, 0.01, 0.495], 0.0, 0.5)
        self.assertAlmostEqual(us[1], 0.51)
        self.assertLess(max(us) - min(us), 0.05)


class Stripes(unittest.TestCase):
    def test_white_first_then_navy_even_widths(self):
        p = 0.04
        self.assertEqual(H.stripe_cover(0.005, 0.005, p, 0.5), 0.0)  # white at the edge
        self.assertEqual(H.stripe_cover(0.025, 0.025, p, 0.5), 1.0)
        self.assertAlmostEqual(H.stripe_cover(0.0, p, p, 0.5), 0.5)
        self.assertAlmostEqual(H.stripe_cover(0.0, 10 * p, p, 0.5), 0.5)

    def test_box_filter_at_an_edge(self):
        self.assertAlmostEqual(H.stripe_cover(0.019, 0.021, 0.04, 0.5), 0.5)
        self.assertAlmostEqual(H.stripe_cover(0.021, 0.019, 0.04, 0.5), 0.5)  # either order


class Offsets(unittest.TestCase):
    def test_clearance_inside_the_bib_never_below_the_floor(self):
        self.assertEqual(H.clearance(0.006, None, 0.003, 0.002), 0.006)
        self.assertAlmostEqual(H.clearance(0.006, 0.007, 0.003, 0.002), 0.004)
        self.assertEqual(H.clearance(0.006, 0.003, 0.003, 0.002), 0.002)
        self.assertEqual(H.clearance(0.006, 0.05, 0.003, 0.002), 0.006)

    def test_taper_to_the_hem(self):
        self.assertEqual(H.taper(1.1, 0.95, 1.02, 0.002, 0.006), 0.006)
        self.assertEqual(H.taper(0.9, 0.95, 1.02, 0.002, 0.006), 0.002)
        self.assertAlmostEqual(H.taper(0.985, 0.95, 1.02, 0.002, 0.006), 0.004)


class Panels(unittest.TestCase):
    ARGS = dict(z_waist=1.0, bib_hw=0.105, bib_top=1.195, back_y=0.03, z_apex=1.12, back_hw_waist=0.12,
                back_hw_apex=0.03)

    def test_trousers_bib_and_back_kept_the_rest_goes(self):
        k = lambda x, y, z: H.keep_face(x, y, z, **self.ARGS)
        self.assertTrue(k(0.2, 0.0, 0.9))  # the trousers
        self.assertTrue(k(0.05, -0.08, 1.15))  # the bib
        self.assertFalse(k(0.15, -0.08, 1.15))  # beside the bib: the old top
        self.assertFalse(k(0.05, -0.06, 1.25))  # above the bib
        self.assertTrue(k(0.1, 0.12, 1.01))  # the back panel at the waist
        self.assertFalse(k(0.1, 0.12, 1.10))  # outside the V
        self.assertTrue(k(0.0, 0.12, 1.11))
        self.assertFalse(k(0.0, 0.12, 1.13))  # above the apex
        self.assertFalse(k(0.17, 0.01, 1.05))  # the side above the waistband

    def test_back_halfwidth_narrows(self):
        self.assertEqual(H.back_halfwidth(0.95, 1.0, 1.12, 0.12, 0.03), 0.12)
        self.assertAlmostEqual(H.back_halfwidth(1.06, 1.0, 1.12, 0.12, 0.03), 0.075)
        self.assertEqual(H.back_halfwidth(1.2, 1.0, 1.12, 0.12, 0.03), 0.0)


class Straps(unittest.TestCase):
    def test_strap_x_piecewise_and_held(self):
        ts, xs = [-1.5, 0.5, 2.2], [0.085, 0.1, 0.015]
        self.assertEqual(H.strap_x(-2.0, ts, xs), 0.085)
        self.assertAlmostEqual(H.strap_x(-0.5, ts, xs), 0.0925)
        self.assertAlmostEqual(H.strap_x(1.35, ts, xs), 0.0575)
        self.assertEqual(H.strap_x(3.0, ts, xs), 0.015)


class Neck(unittest.TestCase):
    def test_neck_plane_up_and_through_both_points(self):
        co, no = H.neck_plane(-0.06, 1.33, 0.09, 1.36)
        self.assertAlmostEqual(math.hypot(*no), 1.0)
        self.assertGreater(no[2], 0.9)
        self.assertAlmostEqual(H.plane_side((0.0, 0.09, 1.36), co, no), 0.0)
        self.assertGreater(H.plane_side((0.0, 0.0, 1.40), co, no), 0.0)  # the neck above: cut away
        self.assertLess(H.plane_side((0.1, 0.0, 1.30), co, no), 0.0)  # the shoulder below: kept


class Finish(unittest.TestCase):
    def test_lat_us_lips_then_an_even_flat_top(self):
        self.assertEqual(H.lat_us(5, 0.1), [0.0, 0.1, 0.5, 0.9, 1.0])
        with self.assertRaises(ValueError):
            H.lat_us(3, 0.1)

    def test_stitch_mask_two_dashed_columns(self):
        m = H.stitch_mask(41, 8, [0.2, 0.8], 3, 2)
        on = {x for row in m for x, v in enumerate(row) if v}
        self.assertEqual(on, {8, 32})
        self.assertEqual([m[r][8] for r in range(8)], [True, True, True, False, False, True, True, True])

    def test_seam_wrap_takes_the_other_side(self):
        pairs = H.seam_wrap_cols(18, 20, 120, 123)
        self.assertEqual(pairs[:2], [(18, 118), (19, 119)])
        self.assertEqual(pairs[2:], [(120, 20), (121, 21), (122, 22)])

    def test_buckle_ring_closed_with_its_sizes(self):
        t, s, n = (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, -1.0, 0.0)
        vs, qs = H.buckle_ring((0.1, -0.05, 1.16), t, s, n, 0.0215, 0.011, 0.004, 0.0005, 0.0035, 0.003)
        self.assertEqual((len(vs), len(qs)), (32, 32))
        xs = [v[0] for v in vs]
        self.assertAlmostEqual(max(xs) - min(xs), 0.043)
        ys = [v[1] for v in vs]
        self.assertAlmostEqual(min(ys), -0.05 - 0.0035)  # out along n
        edges = {}
        for q in qs:
            for a, b in zip(q, q[1:] + q[:1]):
                edges[frozenset((a, b))] = edges.get(frozenset((a, b)), 0) + 1
        self.assertEqual(set(edges.values()), {2})  # a closed ring: each edge in two quads

    def test_button_dome_on_top(self):
        t, s, n = (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, -1.0, 0.0)
        vs, fs = H.button((0.0, 0.0, 0.0), t, s, n, 0.0065, 0.0005, 0.003, 0.001, 10)
        self.assertEqual((len(vs), len(fs)), (21, 20))
        self.assertAlmostEqual(vs[-1][1], -0.004)
        self.assertEqual(sum(len(f) - 2 for f in fs), 30)



class Openings(unittest.TestCase):
    def test_edge_loops_split_runs_longest_first(self):
        edges = [(0, 1), (1, 2), (2, 0), (5, 6), (6, 7), (7, 8), (8, 5), (10, 11)]
        self.assertEqual(H.edge_loops(edges), [[5, 6, 7, 8], [0, 1, 2], [10, 11]])
        self.assertEqual(H.edge_loops([]), [])

    def test_the_collar_not_the_hole_beside_it(self):
        neck = (0.0, 0.02, 1.40)
        loops = [((0.0, 0.01, 1.35), 0.62),  # the collar
                 ((0.09, 0.03, 1.30), 0.20),  # a hidden-face hole under the strap, near the neck
                 ((0.0, -0.1, 1.10), 0.90),  # the bib's hole: long, but far
                 ((0.0, 0.0, 0.95), 1.80)]  # the tucked hem
        self.assertEqual(H.pick_openings(loops, neck, 0.15), [0])

    def test_both_layers_of_a_hem_and_none_when_far(self):
        ankle = (0.1, 0.0, 0.08)
        loops = [((0.1, 0.0, 0.15), 0.40), ((0.1, 0.0, 0.16), 0.36), ((0.1, -0.05, 0.2), 0.05)]
        self.assertEqual(H.pick_openings(loops, ankle, 0.3), [0, 1])
        self.assertEqual(H.pick_openings(loops, (0.0, 0.0, 1.4), 0.15), [])

    def test_every_piece_has_its_joints(self):
        self.assertEqual(H.OPENINGS["top"], ("Neck", "LeftHand", "RightHand"))
        for joints in H.OPENINGS.values():
            for jn in joints:
                self.assertIn(jn, H.OPENING_REACH)



class Follow(unittest.TestCase):
    def test_share_blends_and_normalises(self):
        own, panel = {"Chest": 1.0}, {"Chest": 0.5, "Spine": 0.5}
        self.assertEqual(H.follow_row(own, panel, 0.0), {"Chest": 1.0})
        self.assertEqual(H.follow_row(own, panel, 1.0), {"Chest": 0.5, "Spine": 0.5})
        half = H.follow_row(own, panel, 0.5)
        self.assertAlmostEqual(half["Chest"], 0.75)
        self.assertAlmostEqual(half["Spine"], 0.25)
        self.assertEqual(H.follow_row(own, panel, 2.0), H.follow_row(own, panel, 1.0))  # clamped

    def test_four_bones_at_most(self):
        own = {"A": 0.3, "B": 0.3, "C": 0.2, "D": 0.2}
        panel = {"E": 0.9, "A": 0.1}
        row = H.follow_row(own, panel, 0.5)
        self.assertEqual(len(row), 4)
        self.assertAlmostEqual(sum(row.values()), 1.0)
        self.assertIn("E", row)

class WaistBand(unittest.TestCase):
    """C1i: the band the built waistband replaces, the top pulled in under the panels, the strip's lats."""

    def band(self, x, y, z):
        return H.in_waist_band(x, y, z, 1.0, 0.04, 0.105, 0.03, 0.12)

    def test_band_is_the_sides_below_the_waist_only(self):
        self.assertTrue(self.band(0.14, 0.0, 0.98))  # the hip's side
        self.assertTrue(self.band(0.11, -0.05, 0.99))  # the front just beside the bib
        self.assertTrue(self.band(0.13, 0.08, 0.97))  # the back beside the panel
        self.assertFalse(self.band(0.05, -0.08, 0.98))  # under the bib
        self.assertFalse(self.band(0.05, 0.09, 0.98))  # under the back panel
        self.assertFalse(self.band(0.14, 0.0, 1.01))  # above the waistband line
        self.assertFalse(self.band(0.14, 0.0, 0.95))  # the trousers below the band

    def test_under_offset_pulls_in_by_share_never_out(self):
        self.assertAlmostEqual(H.under_offset(0.006, 1.0, 0.0015), 0.0015)
        self.assertAlmostEqual(H.under_offset(0.006, 0.0, 0.0015), 0.006)
        self.assertAlmostEqual(H.under_offset(0.006, 0.4, 0.0015), 0.0042)
        self.assertAlmostEqual(H.under_offset(0.001, 1.0, 0.0015), 0.001)
        self.assertAlmostEqual(H.under_offset(0.006, 3.0, 0.0015), 0.0015)

    def test_band_lats_lip_flat_ledge(self):
        lats = H.band_lats(0.038, 0.003, 0.004, 3)
        self.assertEqual(lats, [(0.0, -0.003), (0.0, 0.0), (0.019, 0.0), (0.038, 0.0), (0.038, -0.004)])
        with self.assertRaises(ValueError):
            H.band_lats(0.038, 0.003, 0.004, 1)

    def test_band_offset_runs_low_to_high(self):
        self.assertAlmostEqual(H.band_offset(0.0, 0.015, 0.009), 0.015)
        self.assertAlmostEqual(H.band_offset(1.0, 0.015, 0.009), 0.009)
        self.assertAlmostEqual(H.band_offset(0.5, 0.015, 0.009), 0.012)
        self.assertAlmostEqual(H.band_offset(2.0, 0.015, 0.009), 0.009)

    def test_blend_rows_weights_by_nearness(self):
        row = H.blend_rows([({"Hips": 1.0}, 0.01), ({"Spine": 1.0}, 0.03)])
        self.assertAlmostEqual(row["Hips"], 0.75)
        self.assertAlmostEqual(row["Spine"], 0.25)
        self.assertEqual(H.blend_rows([]), {})
        many = H.blend_rows([({b: 1.0}, 0.01 * (i + 1)) for i, b in enumerate("ABCDEF")])
        self.assertEqual(sorted(many), ["A", "B", "C", "D"])
        self.assertAlmostEqual(sum(many.values()), 1.0)


if __name__ == "__main__":
    unittest.main()
