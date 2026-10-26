"""The head follows the aim (art #196, H1; F1): `tools/blender/alien_headlook_run.py --check` runs
godot/alien/head_look_check.gd headless on both aliens' GLBs (the newest loco build) and exits 0: the head bone's
facing inside and at the clamps, a middle bone's share, the defaults' clamp, no drift, the clips, the smoothing and
body_follow()'s cases (HEADLOOK_RESULT pass). Skips without Godot or the raw build."""

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
try:
    import alien_headlook_run as H  # noqa: E402

    HAVE_BUILD = all((H.BUILD / c / f"{c}_char.glb").is_file() for c in H.CHARS)
except Exception:  # the raw root unset or unreadable
    HAVE_BUILD = False


@unittest.skipUnless(HAVE_GODOT, "needs Godot")
@unittest.skipUnless(HAVE_BUILD, "needs the raw loco build (alien_loco.py)")
class HeadLookCheckTest(unittest.TestCase):
    def test_the_check_passes_on_both_aliens(self):
        res = subprocess.run([sys.executable, str(ROOT / "tools" / "blender" / "alien_headlook_run.py"), "--check"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        out = (res.stdout or "") + (res.stderr or "")
        self.assertEqual(res.returncode, 0, out[-3000:])
        self.assertIn("HEADLOOK_RESULT pass", out)
        self.assertEqual(out.count("\nHEADLOOK {") + out.startswith("HEADLOOK {"), len(H.CHARS), out[-3000:])


if __name__ == "__main__":
    unittest.main()
