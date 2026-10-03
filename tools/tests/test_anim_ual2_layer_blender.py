"""The layered clip of the animation review in headless Blender on the real files (art #24): the carry idle
"ual:Idle_Loop|ual2:Walk_Carry_Loop" keeps Idle_Loop's hips and legs (the same knee flexion, in place, no foot
sliding), takes Walk_Carry_Loop's upper body (its elbow flexion, not Idle_Loop's) and loops cleanly. Measures only, on
the men's body type. Skipped when Blender or the raw files are missing."""

from __future__ import annotations

import json
import shutil
import unittest

from runner import blender, common, pins
from runner.commands import _anim, anim_review

OUT = common.OUT / "tests" / "anim_ual2_layer"
HAVE_BLENDER = bool((path := common.tool_path(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)) and path.is_file())
CFG = _anim.load_config()
FILES = [common.raw_dir() / lib["file"] for lib in _anim.libraries(CFG).values()]
FILES.append(common.raw_dir() / CFG["bodies"]["men"]["character"])
HAVE_FILES = all(f.is_file() for f in FILES)
BASE, UPPER = "ual:Idle_Loop", "ual2:Walk_Carry_Loop"
LAYERED = f"{BASE}|{UPPER}"


@unittest.skipUnless(HAVE_BLENDER and HAVE_FILES, "needs Blender and the raw files (ART_RAW_DIR)")
class LayeredClipTest(unittest.TestCase):
    def test_the_carry_idle_layers_the_upper_body_over_the_idle(self) -> None:
        shutil.rmtree(OUT, ignore_errors=True)
        blender.run_script("anim_review.py", [
            "clips", *anim_review.body_args(CFG, "men"), "--out", str(OUT), "--clips", f"{BASE},{UPPER},{LAYERED}",
            "--tag", "_t", "--no-video", "--no-strips"], timeout=1800)
        m = json.loads((OUT / "metrics" / "men_t.json").read_text(encoding="utf-8"))
        base, upper, layered = m[BASE], m[UPPER], m[LAYERED]
        self.assertTrue(layered["loop"])
        self.assertEqual(layered["seconds"], base["seconds"])  # the base clip sets the length
        self.assertLess(layered["loop_seam"]["seam_deg"], 1.0)
        self.assertTrue(layered["root_motion"]["in_place"])
        self.assertLess(layered["foot_sliding"]["slide_max_cm_s"], 1.0)
        for knee in ("knee.L", "knee.R"):  # the legs are the idle's
            for stat in ("min", "max", "mean"):
                self.assertAlmostEqual(layered["flexion_deg"][knee][stat], base["flexion_deg"][knee][stat], delta=0.2)
        for elbow in ("elbow.L", "elbow.R"):  # the arms are the carry's
            got, want, idle = (x["flexion_deg"][elbow]["mean"] for x in (layered, upper, base))
            self.assertLess(abs(got - want), 5.0, (elbow, got, want))
            self.assertGreater(abs(got - idle), 10.0, (elbow, got, idle))


if __name__ == "__main__":
    unittest.main()
