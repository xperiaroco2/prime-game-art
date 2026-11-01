"""H1l (art #196): the run fist's envelope route (tools/blender/alien_fist_envelope.py), checked on synthetic shapes
inside Blender for its numpy (tools/blender/alien_fist_envelope_check.py): the round cone's field, the iso-mesh, the
shrink-wrap and the relax's metrics (folded triangles, bumps, the slit, a pinned rim). Skips without Blender."""

from __future__ import annotations

import json
import unittest

from runner import blender, common, pins

HAVE = bool((path := common.tool_path(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)) and path.is_file())
SCRIPT = common.ROOT / "tools" / "blender" / "alien_fist_envelope_check.py"


@unittest.skipUnless(HAVE, "needs Blender")
class EnvelopeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r = blender.run_script(SCRIPT, [], timeout=600)
        out = (r.stdout or "") + (r.stderr or "")
        line = next((ln for ln in out.splitlines() if ln.startswith("ENVELOPE_CHECK ")), None)
        if line is None:
            raise AssertionError(f"alien_fist_envelope_check.py printed no ENVELOPE_CHECK line\n{out[-2000:]}")
        cls.d = json.loads(line[len("ENVELOPE_CHECK "):])

    def test_the_round_cone_is_exact(self):
        self.assertLess(self.d["cone_err_mm"], 0.01)

    def test_the_iso_mesh_is_closed_outward_and_on_the_field(self):
        iso = self.d["iso"]
        self.assertGreater(iso["tris"], 1000)
        self.assertEqual(iso["open_edges"], 0)
        self.assertGreater(iso["volume_cm3"], 20.0)  # faces out: a positive volume (two 8 mm tubes, 50 mm long)
        self.assertLess(iso["off_mm"], 0.2)  # 1.5 mm cells: the linear interpolation's error

    def test_the_merged_envelope_fills_the_gap(self):
        self.assertGreater(self.d["iso"]["groove_mm"], 0.0)  # the point between the tubes is inside

    def test_a_merged_envelope_folds_the_facing_sides(self):
        # why the press mode exists: on one merged solid the two tubes' facing sides must fold, relax or not
        self.assertGreater(self.d["wrap"]["bare"]["folded"], 0)
        self.assertGreater(self.d["wrap"]["relaxed"]["folded"], 0)

    def test_the_pressed_envelope_wraps_with_no_fold(self):
        pr = self.d["press"]
        self.assertEqual(pr["bare"]["folded"], 0)
        self.assertEqual(pr["relaxed"]["folded"], 0)
        self.assertLess(pr["relaxed"]["bump_mm"], 0.3)
        self.assertLess(pr["relaxed"]["sag_mm"], pr["bare"]["sag_mm"])  # the relax evens the facets out
        self.assertGreater(pr["slit_mm"], 0.2)  # the two tubes stay apart: a slit, no merge
        self.assertLess(pr["slit_mm"], 1.5)

    def test_a_turned_triangle_counts_as_folded(self):
        self.assertEqual(self.d["press"]["flip_folded"], 1)

    def test_a_pinned_rim_stays(self):
        self.assertEqual(self.d["pinned_moved_mm"], 0.0)

    def test_the_contact_corrective_closes_a_gap_under_its_cap(self):
        c = self.d["contact"]
        self.assertGreater(c["valley_up_mm"], 0.3)  # the valley between the two tubes fills outward
        self.assertLessEqual(c["move_max_mm"], 4.0 + 1e-6)  # the cap
        self.assertLessEqual(c["raw_max_mm"], 8.0)
        self.assertEqual(c["folded"], 0)
        self.assertEqual(c["flipped"], 0)

    def test_the_contact_corrective_lets_touching_sides_sink(self):
        c = self.d["contact_touch"]
        self.assertGreater(c["inside"], 0)
        self.assertGreater(c["buried"], 0)
        self.assertEqual(c["inside_on_shell"], 0)  # never projected onto the outer shell
        self.assertLess(c["inside_max_move_mm"], 4.0)

    def test_the_contact_local_zone_has_its_own_cap(self):
        c = self.d["contact_local"]
        self.assertGreater(c["local_verts"], 0)
        self.assertLessEqual(c["far_max_mm"], 1.5 + 1e-6)  # outside the zone: the global cap
        self.assertGreater(c["zone_max_mm"], 1.5)  # inside it: past the global cap
        self.assertLessEqual(c["zone_max_mm"], 4.0 + 1e-6)  # under its own
        self.assertEqual(c["folded"], 0)
        self.assertEqual(c["flipped"], 0)


if __name__ == "__main__":
    unittest.main()
