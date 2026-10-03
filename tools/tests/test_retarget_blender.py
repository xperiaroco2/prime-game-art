"""The retarget in headless Blender on the real files, for both body types: the source rest lands exactly on the
target rest, a walk keeps its feet on the floor (its legs reach the source's ankle path and no vertex goes 1 cm under
the floor), and a fall (Death01, the pelvis turned about 100 degrees) goes no deeper into the floor than the source's
own mesh scaled to the target, plus 3 cm. Skipped when Blender or the raw packs are missing."""

from __future__ import annotations

import json
import shutil
import unittest

from runner import blender, common, pins
from runner.commands import _anim

OUT = common.OUT / "tests" / "retarget"
HAVE_BLENDER = bool((path := common.tool_path(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)) and path.is_file())
CFG = _anim.load_config()
FILES = [common.raw_dir() / CFG["ual"]] + [common.raw_dir() / b["character"] for b in CFG["bodies"].values()]
HAVE_FILES = all(f.is_file() for f in FILES)


@unittest.skipUnless(HAVE_BLENDER and HAVE_FILES, "needs Blender and the raw packs (ART_RAW_DIR)")
class RetargetTest(unittest.TestCase):
    def run_retarget(self, body: str) -> dict:
        out = OUT / body
        shutil.rmtree(out, ignore_errors=True)
        blender.run_script("retarget.py", ["--source", str(FILES[0]),
                                           "--target", str(common.raw_dir() / CFG["bodies"][body]["character"]),
                                           "--out", str(out), "--clips", "A_TPose,Walk_Loop,Death01", "--floor"],
                           timeout=900)
        return json.loads((out / "retarget_report.json").read_text(encoding="utf-8"))

    def test_both_body_types(self) -> None:
        for body, scale in (("men", 1.034), ("women", 1.113)):
            with self.subTest(body=body):
                report = self.run_retarget(body)
                self.assertLess(report["rest_check"]["max_offset_mm"], 0.01)
                self.assertLess(report["rest_check"]["max_rotation_deg"], 0.01)
                self.assertAlmostEqual(report["translation_scale"], scale, places=2)
                self.assertEqual(report["clips"]["Walk_Loop"]["frames"], 40)
                self.assertLess(report["clips"]["Walk_Loop"]["ik_miss_mm"], 10.0)
                self.assertEqual(report["clips"]["A_TPose"]["ik_miss_mm"], 0.0)
                self.assertGreater(report["clips"]["Walk_Loop"]["lowest_cm"], -1.0)
                death = report["clips"]["Death01"]
                self.assertGreater(death["lowest_cm"], death["source_lowest_cm"] - 3.0, death)


if __name__ == "__main__":
    unittest.main()
