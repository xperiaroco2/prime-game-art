"""T1 socketed head, step 2 (art #196): the kit's node names, expression table, lid shells, brow tilt and seat rule."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import alien_t1_geom as G  # noqa: E402


class ExpressionTests(unittest.TestCase):
    def test_every_expression_uses_known_nodes_once(self):
        names = set(G.node_names())
        for name, spec in G.expressions().items():
            self.assertTrue(set(spec["nodes"]) <= names, name)
            self.assertEqual(len(spec["nodes"]), len(set(spec["nodes"])), name)

    def test_one_mouth_and_one_lid_per_eye(self):
        for name, spec in G.expressions().items():
            nodes = spec["nodes"]
            self.assertEqual(sum(n.startswith("mouth_") for n in nodes), 1, name)
            for s in G.SIDES:
                self.assertIn(f"eye_{s}", nodes)
                self.assertEqual(sum(n.startswith(f"lid_{s}_") for n in nodes), 1, name)
                self.assertLessEqual(sum(n.startswith(f"brow_{s}_") for n in nodes), 1, name)

    def test_brief_expressions(self):
        e = G.expressions()
        self.assertIn("mouth_o", e["surprised"]["nodes"])
        self.assertIn("lid_L_open", e["surprised"]["nodes"])
        self.assertIn("brow_R_angry", e["angry"]["nodes"])
        self.assertIn("lid_R_half", e["angry"]["nodes"])
        self.assertGreater(e["gaze_left"]["gaze_deg"], 0)
        self.assertEqual(e["gaze_left"]["gaze_deg"], -e["gaze_right"]["gaze_deg"])
        self.assertFalse(any(n.startswith("brow_") for n in e["rest"]["nodes"]))

    def test_every_node_is_used(self):
        used = {n for spec in G.expressions().values() for n in spec["nodes"]}
        self.assertEqual(used, set(G.node_names()))


class LidTests(unittest.TestCase):
    axes = ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))

    def test_lid_dir_is_unit_and_edge_is_a_plane(self):
        phi = math.radians(G.LIDS["half"]["upper"])
        pts = [G.lid_dir(self.axes, phi, math.radians(p)) for p in (-80, -30, 0, 30, 80)]
        for p in pts:
            self.assertAlmostEqual(math.sqrt(sum(c * c for c in p)), 1.0, places=9)
        # a plane through the side axis: z / -y is the same everywhere on the edge
        ratios = {round(p[2] / -p[1], 9) for p in pts}
        self.assertEqual(len(ratios), 1)

    def test_states_close_in_order(self):
        self.assertGreater(G.LIDS["open"]["upper"], G.LIDS["half"]["upper"])
        self.assertGreater(G.LIDS["half"]["upper"], G.LIDS["closed"]["upper"])
        self.assertGreater(G.LIDS["closed"]["upper"], G.LIDS["closed"]["lower"])  # they overlap: no slit
        self.assertEqual(G.lid_span("half", True)[0], G.LIDS["half"]["upper"])
        self.assertLess(G.lid_span("half", False)[1], 0)

    def test_thickness_swells_at_the_edge(self):
        self.assertAlmostEqual(G.lid_thickness(20.0, 20.0, 1.0, bead=1.0), 2.0)
        self.assertLess(G.lid_thickness(90.0, 20.0, 1.0), 1.01)


class SeatTests(unittest.TestCase):
    def test_back_vertex_in_front_of_skin_is_sunk(self):
        self.assertAlmostEqual(G.seat_y(-0.5, -0.4, 1.0, 0.01), -0.39)

    def test_inside_or_front_vertices_stay(self):
        self.assertEqual(G.seat_y(-0.3, -0.4, 1.0, 0.01), -0.3)
        self.assertEqual(G.seat_y(-0.5, -0.4, 0.0, 0.01), -0.5)
        self.assertEqual(G.seat_y(-0.5, None, 1.0, 0.01), -0.5)

    def test_back_weight(self):
        self.assertEqual(G.back_weight(-1.0), 0.0)
        self.assertEqual(G.back_weight(1.0), 1.0)

    def test_brow_tilt_mirrors(self):
        self.assertAlmostEqual(G.brow_tilt_rad("L", "sad"), -G.brow_tilt_rad("R", "sad"))
        self.assertGreater(G.brow_tilt_rad("L", "sad"), 0)
        self.assertLess(G.brow_tilt_rad("L", "angry"), 0)


if __name__ == "__main__":
    unittest.main()
