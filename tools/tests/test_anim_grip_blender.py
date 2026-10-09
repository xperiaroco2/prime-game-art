"""The side grip in background Blender on the real files (art #65, #69): the MVP set's Carry_Upper_Loop and
Pickup_Package, built on the men's body by tools/blender/anim_set.py from tools/blender/anim_sets/mvp.toml. side_grip
holds the package's 0.45 m between the hands' closest vertices on every frame (+-1.5 cm) with the palms vertical;
upper_match takes the pickup's last frame to the carry's first over the idle (Body, Hips and Abdomen to the idle's);
anim_set.grip_check runs grip_ends (hands_at on the exported first and last frames) against that pose: the wrists hand
over within 0.1 cm. Skips without Blender, the men's pack or a library the clips read (raw folder)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from runner import blender, common, pins
from runner.commands import _anim, anim_review

RAW = common.raw_dir()
CFG = _anim.load_config()
LIBS = _anim.libraries(CFG)
FILES = [CFG["bodies"]["men"]["character"]] + [f for lib in LIBS.values() for f in [lib["file"], *lib["extra"]]]
HAVE = (bool((path := common.tool_path(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)) and path.is_file())
        and all((RAW / f).is_file() for f in FILES))
SET = common.ROOT / "tools" / "blender" / "anim_sets" / "mvp.toml"


@unittest.skipUnless(HAVE, "needs Blender, the Ultimate Modular men's pack and every clip library (raw folder)")
class SideGripBlenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = TemporaryDirectory()
        out = Path(cls.tmp.name) / "out"
        args = ["--set", str(SET), *anim_review.body_args(CFG, "men"), "--out", str(out),
                "--clips", "Carry_Upper_Loop,Pickup_Package", "--no-save"]
        blender.run_script("anim_set.py", args, timeout=1200)
        cls.clips = json.loads((out / "build_report.json").read_text(encoding="utf-8"))["clips"]

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def step(self, clip: str, op: str) -> dict:
        return next(s for s in self.clips[clip]["steps"] if s["op"] == op)

    def test_the_carry_holds_the_package_by_its_sides(self) -> None:
        g = self.step("Carry_Upper_Loop", "side_grip")
        self.assertEqual((g["gap_m"], g["not_found"]), (0.45, 0))
        self.assertEqual(g["frames"], g["frames_full"])  # a loop: the grip on every frame
        self.assertGreaterEqual(g["gap_after_cm"]["min"], 43.5)
        self.assertLessEqual(g["gap_after_cm"]["max"], 46.5)
        self.assertLess(g["gap_before_cm"]["max"], 5.0)  # UAL2's tray: the hands together
        for side in "LR":
            self.assertLess(abs(g["palm_up_after_deg"][side]["max"]), 1.0)  # the palms vertical
        self.assertEqual((g["hands_in_each_other_after_cm"], g["hands_in_torso_after_cm"]), (0.0, 0.0))

    def test_the_pickup_fades_into_the_grip(self) -> None:
        g = self.step("Pickup_Package", "side_grip")
        self.assertGreater(g["frames"], g["frames_full"])  # faded in before the hands' lowest point
        self.assertGreaterEqual(g["gap_after_cm"]["min"], 43.5)
        self.assertLessEqual(g["gap_after_cm"]["max"], 46.5)

    def test_upper_match_takes_the_end_to_the_carry_over_the_idle(self) -> None:
        u = self.step("Pickup_Package", "upper_match")
        self.assertEqual((u["from_clip"], u["base_clip"], u["at"]), ("Carry_Upper_Loop", "Idle_Loop", "end"))
        self.assertEqual(u["carried_by"], ["Body", "Hips", "Abdomen"])
        self.assertEqual(u["frames_faded"], 12)  # 0.4 s at 30 fps
        self.assertGreater(u["body_move_cm"], 1.0)

    def test_grip_check_hands_over_within_a_millimetre(self) -> None:
        ends = self.clips["Pickup_Package"]["grip_ends"]
        self.assertEqual(set(ends), {"first", "last", "ref"})
        last = ends["last"]
        for side in "LR":
            self.assertLessEqual(last["to_ref_cm"][side], 0.1)  # 0.08 cm on the men (art #65), 0.1 on the women
            self.assertLess(abs(last["palm_up_deg"][side]), 1.0)
        self.assertAlmostEqual(last["gap_cm"], 45.0, delta=1.5)
        self.assertAlmostEqual(ends["ref"]["gap_cm"], 45.0, delta=1.5)
        self.assertEqual((last["hands_in_each_other_cm"], last["hands_in_torso_cm"]), (0.0, 0.0))
        self.assertGreater(ends["first"]["to_ref_cm"]["L"], 5.0)  # the first frame stands in the idle, hands down


if __name__ == "__main__":
    unittest.main()
