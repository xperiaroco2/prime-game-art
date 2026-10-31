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

    def test_inward_flap_only_at_the_edges_turned_in(self):
        def flap(x, y, z, nx, ny, hw=0.12):
            return H.inward_flap(x, y, z, nx, ny, 0.968, 1.10, 0.015, 0.105, 0.03, hw, 0.025)
        self.assertTrue(flap(0.10, -0.05, 1.03, -1.0, 0.0))  # the bib's side edge, facing in
        self.assertFalse(flap(0.10, -0.05, 1.03, 1.0, 0.0))  # the same edge facing out
        self.assertFalse(flap(0.03, -0.08, 1.03, 0.0, 1.0))  # the bib's middle, whatever it faces
        self.assertFalse(flap(0.10, -0.05, 1.12, -1.0, 0.0))  # above the zone
        self.assertTrue(flap(0.11, 0.06, 0.99, -1.0, 0.0))  # the back panel's edge at the waist
        self.assertFalse(flap(0.04, 0.09, 1.08, 0.0, -1.0, hw=0.08))  # inside the narrowing V


class EdgePeel(unittest.TestCase):
    """C1j: the tracked panel point's face and the panels' edge peel."""

    def test_min_altitude_triangle_and_quad(self):
        self.assertAlmostEqual(H.min_altitude([0.03, 0.04, 0.05], 0.0006), 0.024)
        self.assertAlmostEqual(H.min_altitude([0.02, 0.01, 0.02, 0.01], 0.0002), 0.01)
        self.assertEqual(H.min_altitude([], 0.0), 0.0)

    def test_track_face_skips_a_sliver_and_a_folded_face(self):
        # the chameleon's r26 case: a 36.5 / 40.0 / 3.7 mm triangle of 19.3 mm2 (its altitude about 1 mm)
        self.assertFalse(H.track_face_ok([0.03647, 0.03999, 0.00366], 19.273e-6, [0.17, 0.99, 0.19]))
        # the axolotl's: a broad face wound against most of its neighbours
        self.assertFalse(H.track_face_ok([0.0399, 0.0314, 0.0134], 182.9e-6, [0.999, -0.42, 0.887, -0.696, -0.963,
                                                                              -0.964, -0.978, -0.941]))
        self.assertTrue(H.track_face_ok([0.01, 0.01, 0.0141], 50e-6, [0.99, 0.95, 0.9]))
        self.assertTrue(H.track_face_ok([0.01, 0.01, 0.0141], 50e-6, []))

    def test_near_panel_edge_both_sides_of_the_cut(self):
        def near(x, y, z, hw=0.12):
            return H.near_panel_edge(x, y, z, 0.96, 1.2, 0.105, 0.03, hw, 0.02)
        self.assertTrue(near(0.095, -0.06, 1.05))
        self.assertTrue(near(-0.115, -0.06, 1.05))
        self.assertFalse(near(0.05, -0.08, 1.05))  # the bib's middle
        self.assertFalse(near(0.095, -0.06, 1.25))  # above the zone
        self.assertTrue(near(0.11, 0.06, 1.0))  # the back panel's edge
        self.assertFalse(near(0.02, 0.09, 1.05, hw=0.08))  # inside the narrowing V
        self.assertFalse(near(0.11, 0.01, 1.0))  # the hip between the panels: left alone

    def test_edge_defect_only_on_an_open_edge(self):
        self.assertFalse(H.edge_defect(False, -0.9, 0.0001, 1e-7, -1.0))  # inside the cloth: never (no hole)
        self.assertTrue(H.edge_defect(True, -0.3, 0.004, 20e-6, 0.9))  # turned in
        self.assertTrue(H.edge_defect(True, 0.8, 0.0005, 20e-6, 0.9))  # a sliver
        self.assertTrue(H.edge_defect(True, 0.8, 0.004, 1e-6, 0.9))  # a crumb
        self.assertTrue(H.edge_defect(True, 0.8, 0.004, 20e-6, -0.5))  # folded back
        self.assertFalse(H.edge_defect(True, 0.8, 0.004, 20e-6, 0.9))  # a clean edge face


    def test_shirt_texel_is_light_and_grey(self):
        self.assertTrue(H.shirt_texel(0.92, 0.93, 0.95))  # the shirt's white
        self.assertFalse(H.shirt_texel(0.15, 0.2, 0.35))  # denim
        self.assertFalse(H.shirt_texel(0.9, 0.55, 0.2))  # orange top-stitching
        self.assertFalse(H.shirt_texel(0.0, 0.0, 0.0))

    def test_cleared_by_face_centres_not_vertices(self):
        # a strip of trouser faces just under the waist line beside the bib: their top vertices lie on z = 1.0 and on
        # the outer side of the bib's x-plane, but their centres are below the waist; a clearing cut killed those
        # vertices and so the faces (the second review's major); the face test keeps them
        under = [-0.016, -0.016, -0.016]  # centres' sides of the plane z = 1.0 (the trousers)
        above = [0.012, 0.03]
        self.assertEqual(H.cleared(under + above, [True] * 5, True), [False, False, False, True, True])
        self.assertEqual(H.cleared(under + above, [True] * 5, False), [True, True, True, False, False])
        self.assertEqual(H.cleared(under + above, [True] * 5, None), [False] * 5)
        self.assertEqual(H.cleared([0.02, 0.02], [False, True], True), [False, True])  # only the picked faces
        self.assertEqual(H.cleared([1e-8, -1e-8], [True, True], True), [False, False])  # on the plane: kept
        # and the garment's pick: the trousers' faces under the waist stay beside the bib and the back panel
        for x, y in ((0.13, -0.08), (-0.2, 0.0), (0.15, 0.09)):
            self.assertTrue(H.keep_face(x, y, 0.9999, 1.0, 0.105, 1.2, 0.03, 1.15, 0.12, 0.05))
            self.assertFalse(H.keep_face(x, y, 1.0001, 1.0, 0.105, 1.2, 0.03, 1.15, 0.12, 0.05))

    def test_flood_peels_only_from_an_open_edge(self):
        nbrs = [[1], [0, 2], [1, 3], [2], [5], [4]]  # a chain 0-1-2-3 and a pair 4-5
        self.assertEqual(H.flood([0], nbrs, {0, 1, 3}), {0, 1})  # 3 is not reached past 2
        self.assertEqual(H.flood([], nbrs, {4, 5}), set())  # light faces inside the cloth: no hole
        self.assertEqual(H.flood([2], nbrs, {0, 1}), set())  # a seed that is not allowed

    def test_opening_dist_of_no_openings_is_infinite(self):
        self.assertEqual(H.opening_dist(None), math.inf)
        self.assertFalse(H.opening_dist(None) < 0.04)
        self.assertEqual(H.opening_dist(0.02), 0.02)

    def test_band_end_stays_inside_the_panel(self):
        self.assertEqual(H.band_end(0.01, None), (0.01, False))
        off, on = H.band_end(0.01, 0.006)
        self.assertAlmostEqual(off, 0.004)
        self.assertFalse(on)
        self.assertEqual(H.band_end(0.003, 0.02), (0.003, False))
        off, on = H.band_end(0.01, 0.0021)  # the panel at the body: the floor, counted
        self.assertAlmostEqual(off, 0.0005)
        self.assertTrue(on)


class BodyPlanes(unittest.TestCase):  # E1b: the cut planes from a body's own bones
    def test_the_reference_body_gets_the_defaults_but_the_cuff(self):
        pl = H.body_planes(1.028, 1.339, 0.041, (0.152, 0.065, 1.277), 0.644)
        self.assertAlmostEqual(pl["cuff_x"], 0.609)
        self.assertAlmostEqual(pl["seam_x"], 0.165)
        self.assertAlmostEqual(pl["arm_z"], 1.18)
        self.assertAlmostEqual(pl["waist"], 1.0)
        self.assertEqual(pl["arm_axis"], (0.065, 1.277))
        for a, b in zip(pl["neck"], (-0.06, 1.335, 0.09, 1.365)):
            self.assertAlmostEqual(a, b)

    def test_a_smaller_body_moves_every_plane_with_its_bones(self):  # D3's B13
        pl = H.body_planes(0.980, 1.274, 0.041, (0.129, 0.041, 1.216), 0.598)
        self.assertAlmostEqual(pl["cuff_x"], 0.563)
        self.assertAlmostEqual(pl["seam_x"], 0.142)
        self.assertAlmostEqual(pl["z_scale"], 0.294 / 0.311)
        self.assertAlmostEqual(pl["waist"], 0.980 - 0.028 * 0.294 / 0.311)
        self.assertLess(pl["arm_z"], 1.216)  # the sleeve's seam still under the arm's axis
        self.assertLess(pl["bib"][1], pl["neck"][1])
        self.assertEqual(pl["arm_axis"], (0.041, 1.216))

    def test_waist_z_sets_the_waist_alone(self):  # M2c: the m2 dungarees' band under B13's bones' waist
        pl = H.body_planes(0.980, 1.274, 0.041, (0.129, 0.041, 1.216), 0.598)
        low = H.body_planes(0.980, 1.274, 0.041, (0.129, 0.041, 1.216), 0.598, waist_z=0.93)
        self.assertAlmostEqual(low["waist"], 0.93)
        for k in pl:
            if k != "waist":
                self.assertEqual(low[k], pl[k])

    def test_a_neck_under_the_chest_is_refused(self):
        with self.assertRaises(ValueError):
            H.body_planes(1.3, 1.2, 0.04, (0.15, 0.06, 1.27), 0.64)




class M2gHelpers(unittest.TestCase):  # M2g: the bib side's striped walls, the turn-ups' cut
    def test_face_samples_count_and_inside(self):
        tri = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
        c = (1 / 3, 1 / 3)
        pts = H.face_samples(c, tri)
        self.assertEqual(len(pts), 10)
        self.assertEqual(len(H.face_samples((0.5, 0.5), [(0, 0), (1, 0), (1, 1), (0, 1)])), 13)
        for x, y in pts:  # all inside the triangle
            self.assertGreaterEqual(x, -1e-9)
            self.assertGreaterEqual(y, -1e-9)
            self.assertLessEqual(x + y, 1 + 1e-9)

    def test_face_samples_catch_a_stripe(self):
        # a white band 0.55 < v < 0.75 of a unit quad: the old 5 samples (centre, corners at 0.7) miss it
        quad = [(0, 0), (1, 0), (1, 1), (0, 1)]
        old = [(0.5, 0.5)] + [(0.5 + 0.7 * (x - 0.5), 0.5 + 0.7 * (y - 0.5)) for x, y in quad]
        self.assertFalse(any(0.55 < y < 0.75 for _x, y in old))
        self.assertTrue(any(0.55 < y < 0.75 for _x, y in H.face_samples((0.5, 0.5), quad)))

    def test_cut_ramp(self):
        self.assertEqual(H.cut_ramp(0.150, 0.163, 0.002), 1.0)
        self.assertEqual(H.cut_ramp(0.170, 0.163, 0.002), 0.0)
        self.assertAlmostEqual(H.cut_ramp(0.163, 0.163, 0.002), 0.5)
        self.assertAlmostEqual(H.cut_ramp(0.1625, 0.163, 0.002), 0.75)


class M2hHelpers(unittest.TestCase):  # M2h: the turn-ups' relax
    def test_relax_weight(self):
        self.assertEqual(H.relax_weight(0.10, 0.20, 0.03), 1.0)
        self.assertEqual(H.relax_weight(0.20, 0.20, 0.03), 0.0)
        self.assertEqual(H.relax_weight(0.25, 0.20, 0.03), 0.0)
        self.assertAlmostEqual(H.relax_weight(0.185, 0.20, 0.03), 0.5)
        self.assertTrue(0.0 < H.relax_weight(0.19, 0.20, 0.03) < 0.5)

    def test_loop_nbrs_stay_on_the_loop(self):
        edges = [(0, 1), (1, 2), (2, 0), (2, 7), (7, 8)]  # a hem loop 0-1-2 and an open run up the leg 2-7-8
        got = H.loop_nbrs(edges, {0, 1, 2})
        self.assertEqual({k: sorted(v) for k, v in got.items()}, {0: [1, 2], 1: [0, 2], 2: [0, 1]})
        self.assertEqual(H.loop_nbrs([], {4}), {4: []})


class PlainDenim(unittest.TestCase):
    """E1h: the plain denim patch's mirrored repeat, cylinder coordinates and boxes."""

    def test_mirror_tile_turns_every_other_copy(self):
        got = [H.mirror_tile(i, 3) for i in range(8)]
        self.assertEqual(got, [(0, False), (1, False), (2, False), (2, True), (1, True), (0, True),
                               (0, False), (1, False)])

    def test_mirror_tile_neighbours_differ_by_at_most_one_texel(self):
        idx = [H.mirror_tile(i, 5)[0] for i in range(30)]
        self.assertTrue(all(abs(a - b) <= 1 for a, b in zip(idx, idx[1:])))

    def test_cyl_coords_arc_from_the_reference_and_height(self):
        s, t = H.cyl_coords(0.2, 0.015, 0.9, 0.015, 0.0, 0.2)  # the left side, a quarter turn from the front
        self.assertAlmostEqual(s, 0.2 * math.pi / 2)
        self.assertAlmostEqual(t, 0.9)
        s0, _ = H.cyl_coords(0.0, -0.185, 0.9, 0.015, 0.0, 0.2)
        self.assertAlmostEqual(s0, 0.0)

    def test_cyl_coords_wrap_round_the_back(self):
        a_ref = math.pi * 0.95
        s1, _ = H.cyl_coords(0.01, 0.2, 1.0, 0.0, a_ref, 0.1)
        s2, _ = H.cyl_coords(-0.01, 0.2, 1.0, 0.0, a_ref, 0.1)
        self.assertLess(abs(s1 - s2), 0.03)  # both sides of the back centre stay together

    def test_in_box_mirrored_in_x(self):
        box = (0.1, 0.2, -0.1, 0.1, 0.8, 1.0)
        self.assertTrue(H.in_box(0.15, 0.0, 0.9, box))
        self.assertTrue(H.in_box(-0.15, 0.0, 0.9, box))
        self.assertFalse(H.in_box(0.05, 0.0, 0.9, box))
        self.assertFalse(H.in_box(0.15, 0.0, 1.1, box))


class FlatBib(unittest.TestCase):  # E1i: her bib a flat, stiff panel over the chest
    def test_chain_row_by_height(self):
        knots = [(1.10, "UpperChest"), (0.95, "Hips"), (1.00, "Spine"), (1.05, "Chest")]
        self.assertEqual(H.chain_row(0.90, knots), {"Hips": 1.0})
        self.assertEqual(H.chain_row(1.20, knots), {"UpperChest": 1.0})
        mid = H.chain_row(1.075, knots)
        self.assertAlmostEqual(mid["Chest"], 0.5)
        self.assertAlmostEqual(mid["UpperChest"], 0.5)
        for z in (0.93, 0.97, 1.0, 1.02, 1.06, 1.09, 1.15):
            self.assertAlmostEqual(sum(H.chain_row(z, knots).values()), 1.0)
            self.assertLessEqual(len(H.chain_row(z, knots)), 2)
        # monotone: the upper bone's share only grows with height between two knots
        ups = [H.chain_row(1.05 + 0.005 * k, knots).get("UpperChest", 0.0) for k in range(11)]
        self.assertEqual(ups, sorted(ups))
        self.assertEqual(H.chain_row(1.0, []), {})

    def test_hull_bridges_the_dip_under_the_bust(self):
        # (z, y), front at smaller y: waist, belly, under the bust (behind), the bust's apex, the upper chest, the top
        prof = [(0.95, -0.10), (1.00, -0.11), (1.04, -0.09), (1.08, -0.14), (1.10, -0.12), (1.11, -0.11)]
        hull = H.front_hull(prof)
        self.assertEqual(hull[0], (0.95, -0.10))
        self.assertIn((1.08, -0.14), hull)
        self.assertNotIn((1.04, -0.09), hull)
        self.assertNotIn((1.00, -0.11), hull)  # in front of the waist, but behind the taut line to the apex
        for z, y in prof:
            self.assertLessEqual(H.hull_at(hull, z), y + 1e-12)

    def test_hull_of_a_straight_or_concave_profile_keeps_its_points(self):
        line = [(0.0, 0.0), (0.5, -0.05), (1.0, -0.1)]
        self.assertEqual(H.front_hull(line), [(0.0, 0.0), (1.0, -0.1)])
        bulge = [(0.0, 0.0), (0.5, -0.2), (1.0, 0.0)]
        self.assertEqual(H.front_hull(bulge), bulge)

    def test_hull_same_height_keeps_the_front_point(self):
        self.assertEqual(H.front_hull([(0.0, -0.1), (0.0, -0.2), (1.0, 0.0)]), [(0.0, -0.2), (1.0, 0.0)])

    def test_hull_at_interpolates_and_clamps(self):
        hull = [(0.0, 0.0), (1.0, -0.1), (2.0, 0.1)]
        self.assertAlmostEqual(H.hull_at(hull, 0.5), -0.05)
        self.assertAlmostEqual(H.hull_at(hull, 1.5), 0.0)
        self.assertEqual(H.hull_at(hull, -1.0), 0.0)
        self.assertEqual(H.hull_at(hull, 3.0), 0.1)

    def test_ease(self):
        self.assertEqual(H.ease(0.9, 1.0, 0.05), 0.0)
        self.assertEqual(H.ease(1.06, 1.0, 0.05), 1.0)
        self.assertAlmostEqual(H.ease(1.025, 1.0, 0.05), 0.5)
        self.assertEqual(H.ease(1.01, 1.0, 0.0), 1.0)


class PanelFit(unittest.TestCase):  # M2d: the flat back panel's depth
    def test_keeps_the_round_and_drops_a_narrow_fold(self):
        pts = []
        for i in range(-10, 11):
            dx = i * 0.005
            for dz in (-0.01, 0.0, 0.01):
                y = 0.12 - 2.0 * dx * dx + 0.1 * dz
                if abs(dx) < 0.006:
                    y += 0.004  # the fold
                pts.append((dx, dz, y))
        self.assertAlmostEqual(H.panel_fit(pts), 0.12, delta=0.004 / 3)  # two thirds of the fold gone at its middle

    def test_exact_on_a_quadratic(self):
        pts = [(dx * 0.01, dz * 0.01, 0.1 + 0.2 * dx * 0.01 - 3.0 * (dx * 0.01) ** 2 + 0.5 * dz * 0.01)
               for dx in range(-3, 4) for dz in (-1, 0, 1)]
        self.assertAlmostEqual(H.panel_fit(pts), 0.1, places=9)

    def test_mean_when_degenerate(self):
        self.assertAlmostEqual(H.panel_fit([(0.0, 0.0, 0.1), (0.0, 0.0, 0.2)]), 0.15)
        self.assertAlmostEqual(H.panel_fit([(0.0, 0.0, 0.1)] * 8), 0.1)
        with self.assertRaises(ValueError):
            H.panel_fit([])


if __name__ == "__main__":
    unittest.main()


class JoinRows(unittest.TestCase):
    def test_the_back_run_glued_and_eased_out_in_front(self):
        hits = [None, 0.004, None, None, -0.008, -0.01]
        along = [0.0, 0.01, 0.02, 0.03, 0.04, 0.05]
        out = H.join_rows(hits, along, 0.02)
        self.assertEqual(out[4], (1.0, 4))
        self.assertEqual(out[5], (1.0, 5))
        self.assertEqual(out[3][1], 4)
        self.assertAlmostEqual(out[3][0], 0.5)
        self.assertEqual(out[2], (0.0, None))  # 2 cm in front: eased out
        self.assertEqual(out[1], (0.0, None))  # a stray hit up the strap is not glued

    def test_no_panel_under_the_end(self):
        self.assertEqual(H.join_rows([0.01, None], [0.0, 0.01], 0.03), [(0.0, None), (0.0, None)])


class BackBib(unittest.TestCase):  # M2f: her back bib's grid
    def test_outline(self):
        g = H.back_bib_grid(0.92, 1.15, 1.10, 0.075, 0.10, 0.06, 0.012, cols=6, rows=4)
        nc, nr, pts = g["cols"], g["rows"], g["points"]
        self.assertEqual((nc, nr), (9, 6))
        self.assertEqual(len(g["faces"]), (nc - 1) * (nr - 1))
        # the bottom corners at hw_b, the top corners at hw_t and z_c, the V's tip at x 0, z_v
        self.assertAlmostEqual(pts[0][0], -0.075)
        self.assertAlmostEqual(pts[0][1], 0.92)
        self.assertAlmostEqual(pts[(nr - 1) * nc + nc - 1][0], 0.10)
        self.assertAlmostEqual(pts[(nr - 1) * nc + nc - 1][1], 1.15)
        tip = pts[(nr - 1) * nc + nc // 2]
        self.assertAlmostEqual(tip[0], 0.0)
        self.assertAlmostEqual(tip[1], 1.10)
        # the border's inner line one border in from the side, one border under the top
        self.assertAlmostEqual(pts[1][0], -0.075 + 0.012)
        self.assertAlmostEqual(pts[(nr - 2) * nc + nc // 2][1], 1.10 - 0.012)
        # the lip: the sides and the top edge only
        self.assertTrue(g["edge"][0] and g["edge"][(nr - 1) * nc + 3] and not g["edge"][nc + 3])
        # every row rises; mirrored across
        for r in range(nr - 1):
            for c in range(nc):
                self.assertLess(pts[r * nc + c][1], pts[(r + 1) * nc + c][1])
        for k in range(nc):
            self.assertAlmostEqual(pts[k][0], -pts[nc - 1 - k][0])

    def test_border_uv(self):
        g = H.back_bib_grid(0.92, 1.15, 1.10, 0.075, 0.10, 0.06, 0.012, cols=6, rows=4)
        kinds = g["kind"]
        self.assertEqual(kinds.count("side"), 2 * (g["rows"] - 1))
        self.assertEqual(kinds.count("top"), g["cols"] - 3)
        for k, uv in zip(kinds, g["border_uv"]):
            if k == "inner":
                self.assertIsNone(uv)
            else:
                self.assertEqual(sorted({round(a, 4) for a, _ in uv}), [0.0, 0.012])

    def test_bad(self):
        with self.assertRaises(ValueError):
            H.back_bib_grid(0.92, 1.15, 1.10, 0.075, 0.10, 0.06, 0.012, cols=5)
        with self.assertRaises(ValueError):
            H.back_bib_grid(0.92, 1.05, 1.10, 0.075, 0.10, 0.06, 0.012)
