"""H1p (art #196): the hands one subdivision denser (tools/blender/alien_hand_mesh.py `dense`), checked on a synthetic
rigged tube inside Blender (tools/blender/alien_hand_mesh_check.py): the faces made only of Hand and finger weights
cut into four, the wrist's LowerArm faces untouched, every old vertex in place, the new weights and UVs
interpolated. Skips without Blender."""

from __future__ import annotations

import json
import unittest

from runner import blender, common, pins

HAVE = bool((path := common.tool_path(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)) and path.is_file())
SCRIPT = common.ROOT / "tools" / "blender" / "alien_hand_mesh_check.py"


@unittest.skipUnless(HAVE, "needs Blender")
class DenseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r = blender.run_script(SCRIPT, [], timeout=600)
        out = (r.stdout or "") + (r.stderr or "")
        line = next((ln for ln in out.splitlines() if ln.startswith("DENSE_CHECK ")), None)
        if line is None:
            raise AssertionError(f"alien_hand_mesh_check.py printed no DENSE_CHECK line\n{out[-2000:]}")
        cls.d = json.loads(line[len("DENSE_CHECK "):])

    def test_the_hand_faces_are_cut_into_four(self):
        # 15 rows of 12 quads; the rows at z >= 0.07 (Hand and finger only) are 8; the rim row (0.07-0.08) keeps
        # its lower edge whole (bmesh's patterns), the 7 rows above are cut into four: 84 faces into 336
        v0, v1 = self.d["verts"]
        f0, f1 = self.d["faces"]
        self.assertEqual(v0, 16 * 12)
        self.assertGreaterEqual(f1 - f0, 84 * 3)
        self.assertGreater(v1 - v0, 84)

    def test_old_vertices_stay(self):
        self.assertEqual(self.d["old_moved_mm"], 0.0)

    def test_the_wrist_faces_are_untouched(self):
        self.assertGreater(self.d["lowerarm_faces"], 0)
        self.assertTrue(self.d["lowerarm_faces_kept"])

    def test_new_weights_and_uvs_are_interpolated(self):
        lo, hi = self.d["new_wsum"]
        self.assertAlmostEqual(lo, 1.0, places=3)
        self.assertAlmostEqual(hi, 1.0, places=3)
        self.assertGreater(self.d["index_on_new"], 0)
        self.assertEqual(self.d["uv_layers"], 1)
        umin, umax, vmin, vmax = self.d["new_uv_range"]
        self.assertGreaterEqual(umin, 0.0)
        self.assertLessEqual(umax, 1.0)
        self.assertGreater(vmin, 0.3)  # the new loops sit on the hand's rows, not at a zeroed UV


if __name__ == "__main__":
    unittest.main()
