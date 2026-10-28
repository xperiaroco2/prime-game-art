"""The photo poses' layers in Godot (art #196): `tools/blender/alien_poses_run.py --check` runs
godot/alien/pose_layers_check.gd headless on both aliens' GLBs (the newest poses build): pose_layers.gd's two filtered
layers give every one of the 48 pairs within 0.5 cm of the Blender-composed pose, each pair holds, stop() gives the
skeleton back, the head look's slide is measured (POSES_RESULT pass). Skips without Godot or the raw build."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "blender"))

from runner import common, pins  # noqa: E402
from runner.commands import _godot  # noqa: E402,F401  (the Godot runner the driver uses)

HAVE_GODOT = common.tool_path(pins.GODOT_ENV, None) is not None
import alien_pose_math as A  # noqa: E402
import alien_poses_run as PR  # noqa: E402  (outside the try: a broken driver fails, it does not skip)

try:
    import alien_char_run as R
    HAVE_BUILD = PR.newest_step(str(R.RAW), A.load()) != ""
except OSError:  # the raw root unreadable
    HAVE_BUILD = False


@unittest.skipUnless(HAVE_GODOT, "needs Godot")
@unittest.skipUnless(HAVE_BUILD, "needs a raw poses build (alien_poses.py --glb)")
class PoseLayersCheckTest(unittest.TestCase):
    def test_the_layers_match_blender_on_both_aliens(self):
        res = subprocess.run([sys.executable, str(ROOT / "tools" / "blender" / "alien_poses_run.py"), "--check"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        out = (res.stdout or "") + (res.stderr or "")
        self.assertEqual(res.returncode, 0, out[-3000:])
        self.assertIn("POSES_RESULT pass", out)
        self.assertEqual(out.count("POSES {"), len(A.load()["set"]["chars"]), out[-3000:])


if __name__ == "__main__":
    unittest.main()
