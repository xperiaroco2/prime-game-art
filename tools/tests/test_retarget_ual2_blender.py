"""UAL2 through the retarget in headless Blender on the real files (art #24), for both body types, with UAL1's bone map:
the UAL2 rest lands on the target rest, the carry walk keeps its feet on the floor (its legs reach the source's ankle
path within 15 mm, no vertex 1 cm under the floor) and the get-up from lying (LayToIdle) goes no deeper into the floor
than UAL2's own mannequin scaled to the target. Skipped when Blender or the raw files are missing."""

from __future__ import annotations

import json
import shutil
import unittest

from runner import blender, common, pins
from runner.commands import _anim

OUT = common.OUT / "tests" / "retarget_ual2"
HAVE_BLENDER = bool((path := common.tool_path(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)) and path.is_file())
CFG = _anim.load_config()
SOURCE = common.raw_dir() / _anim.libraries(CFG)["ual2"]["file"]
FILES = [SOURCE] + [common.raw_dir() / b["character"] for b in CFG["bodies"].values()]
HAVE_FILES = all(f.is_file() for f in FILES)


@unittest.skipUnless(HAVE_BLENDER and HAVE_FILES, "needs Blender and the raw files (ART_RAW_DIR)")
class RetargetUal2Test(unittest.TestCase):
    def test_both_body_types(self) -> None:
        for body, scale in (("men", 1.034), ("women", 1.113)):
            with self.subTest(body=body):
                out = OUT / body
                shutil.rmtree(out, ignore_errors=True)
                blender.run_script("retarget.py", [
                    "--source", str(SOURCE), "--target", str(common.raw_dir() / CFG["bodies"][body]["character"]),
                    "--out", str(out), "--clips", "A_TPose,Walk_Carry_Loop,LayToIdle", "--floor", "--prefix", "UAL2",
                ], timeout=900)
                report = json.loads((out / "retarget_report.json").read_text(encoding="utf-8"))
                self.assertLess(report["rest_check"]["max_offset_mm"], 0.01)
                self.assertLess(report["rest_check"]["max_rotation_deg"], 0.01)
                self.assertAlmostEqual(report["translation_scale"], scale, places=2)  # UAL1's hip joints exactly
                carry = report["clips"]["Walk_Carry_Loop"]
                self.assertEqual((carry["frames"], carry["action"]), (60, "UAL2|Walk_Carry_Loop"))
                self.assertLess(carry["ik_miss_mm"], 15.0)
                self.assertGreater(carry["lowest_cm"], -1.0)
                lay = report["clips"]["LayToIdle"]
                self.assertGreater(lay["lowest_cm"], lay["source_lowest_cm"], lay)


if __name__ == "__main__":
    unittest.main()
