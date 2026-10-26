"""The alien locomotion clip tool in headless Blender (tools/blender/alien_stride.py, art #196 option A step 1) on the
R2b chameleon build's own clips: the pure FK matches Blender's evaluated bone heads on every frame of Jog_Fwd_Loop,
before and after the edit; the edit (stride to 2.22 steps/s at 4.5 m/s, arm swing 0.75, the loop started on the left
foot) written as a new action reads back key for key; its feet stay planted within the stated bound and it covers
4.5 m/s at about rate 1. Skipped when Blender or the build is missing."""
import json
import shutil
import unittest
from pathlib import Path

from runner import blender, common, pins

ROOT = Path(__file__).resolve().parents[2]
OUT = common.OUT / "tests" / "alien_stride"
BLEND = common.raw_dir() / "research/2026-10-22-roster/design/pilot3d/anim_bare/r2b/build/chameleon/chameleon_char.blend"
HAVE_BLENDER = bool((path := common.tool_path(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)) and path.is_file())


@unittest.skipUnless(HAVE_BLENDER and BLEND.is_file(), "needs Blender and the R2b alien build (ART_RAW_DIR)")
class AlienStrideBlenderTest(unittest.TestCase):
    r: dict = {}

    @classmethod
    def setUpClass(cls) -> None:
        shutil.rmtree(OUT, ignore_errors=True)
        OUT.mkdir(parents=True)
        blender.run_script(ROOT / "tools" / "blender" / "alien_stride.py",
                           ["--blend", str(BLEND), "--out", str(OUT), "--check"], timeout=900)
        cls.r = json.loads((OUT / "check.json").read_text(encoding="utf-8"))

    def test_pure_fk_is_blenders_pose(self):
        self.assertLess(self.r["fk_vs_blender_mm"], 0.1)
        self.assertLess(self.r["edit_fk_vs_blender_mm"], 0.1)

    def test_the_written_action_reads_back(self):
        self.assertLess(self.r["readback_deg"], 0.01)
        self.assertLess(self.r["readback_mm"], 0.01)

    def test_the_proof_keeps_the_feet_and_the_speed(self):
        p = self.r["proof"]
        self.assertLessEqual(p["stride"]["planted_slide_mm"], p["stride"]["slide_bound_mm"])
        self.assertLess(p["stride"]["ankle_miss_mm"], 1.0)
        self.assertLess(abs(p["rate_at_speed"] - 1.0), 0.05)
        self.assertLess(p["cycle"]["seam_deg"], 5.0)
        self.assertEqual(p["after"]["seam_deg"], 0.0)
        self.assertEqual(p["after"]["contacts"]["Left"][0], 0)


if __name__ == "__main__":
    unittest.main()
