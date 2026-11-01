"""H1l, H1q (art #196): the run fist's union and contact corrective (tools/blender/alien_fist_envelope.py), checked
on synthetic shapes inside Blender for its numpy (tools/blender/alien_fist_envelope_check.py): the round cone's field,
the iso-mesh, the contact corrective's gap fill and sinking sides. Skips without Blender."""

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

    def test_the_contact_corrective_closes_a_gap_under_its_cap(self):
        c = self.d["contact"]
        self.assertGreater(c["valley_depth_before_mm"], 0.2)  # the valley's skin starts inside the union
        self.assertLess(c["valley_depth_after_mm"], 0.25 * c["valley_depth_before_mm"])  # and fills out onto it
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


if __name__ == "__main__":
    unittest.main()
