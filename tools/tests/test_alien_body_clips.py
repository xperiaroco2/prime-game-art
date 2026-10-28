"""The full-body clip frames' driver (tools/blender/alien_body_clips.py, art #196 T3): its arguments and clip list."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import alien_body_clips as B  # noqa: E402


class Rows(unittest.TestCase):
    def test_rows_keep_their_order(self):
        self.assertEqual(B.rows_arg("r2b=loco/f3/build,t3=loco/t3/build"),
                         [("r2b", "loco/f3/build"), ("t3", "loco/t3/build")])

    def test_malformed_rows_are_refused(self):
        for bad in ("", "r2b", "=loco/f3/build", "r2b=", "r2b=a,t3"):
            with self.assertRaises(ValueError):
                B.rows_arg(bad)


class Clips(unittest.TestCase):
    def test_the_six_clips_of_the_brief(self):
        self.assertEqual([c["label"] for c in B.CLIPS], ["idle", "walk", "run", "crouch", "jump", "strafe"])
        self.assertTrue(all(0.0 <= c["phase"] < 1.0 for c in B.CLIPS))


if __name__ == "__main__":
    unittest.main()
