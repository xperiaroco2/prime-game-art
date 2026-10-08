"""An animation set built in background Blender (tools/blender/anim_set.py, art #33): a small set of a UAL loop, a
pack one-shot retimed, its mirror and a one-shot placed after it is built on the men's donor, saved as a character the
export accepts and read back: the actions are the exported clips alone, at 30 fps, an open UAL loop is closed one
frame longer, the retime, the mirror and the placement are in the report. Skips without Blender, the Ultimate
Modular pack or UAL1 (raw folder)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from runner import blender, common, pins
from runner.commands import _anim, anim_review

RAW = common.raw_dir()
CFG = _anim.load_config()
HAVE = (bool((path := common.tool_path(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)) and path.is_file())
        and (RAW / CFG["bodies"]["men"]["character"]).is_file() and (RAW / CFG["ual"]).is_file())

SET = """title = "test"
fps = 30
stem = "test_set"
upper = "Torso"
[[clips]]
name = "Idle_Loop"
source = "ual:Idle_Loop"
loop = true
[[clips]]
name = "Punch_Left"
source = "pack:Punch_Right"
loop = false
export = false
edits = [{ op = "mirror" }]
[[clips]]
name = "Knife_Swing"
source = "pack:Sword_Slash"
loop = false
edits = [{ op = "retime", seconds = 0.45 }]
[[clips]]
name = "Punch_After"
source = "pack:Punch_Right"
loop = false
export = false
place_after = "Knife_Swing"
"""

READ_BACK = """import bpy, json, sys
bpy.ops.wm.open_mainfile(filepath=sys.argv[sys.argv.index("--") + 1])
s = bpy.context.scene
out = {"fps": s.render.fps, "objects": sorted((o.type, o.parent.name if o.parent else None) for o in s.objects),
       "actions": {a.name: list(a.frame_range) for a in bpy.data.actions},
       "assigned": [o.name for o in s.objects if o.animation_data and o.animation_data.action]}
print("READBACK " + json.dumps(out))
"""


@unittest.skipUnless(HAVE, "needs Blender, the Ultimate Modular men's pack and UAL1 (raw folder)")
class AnimSetBuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = TemporaryDirectory()
        root = Path(cls.tmp.name)
        (root / "test_set.toml").write_text(SET, encoding="utf-8")
        args = ["--set", str(root / "test_set.toml"), *anim_review.body_args(CFG, "men"), "--out", str(root / "out")]
        blender.run_script("anim_set.py", args, timeout=1800)
        cls.report = json.loads((root / "out" / "build_report.json").read_text(encoding="utf-8"))
        (root / "read.py").write_text(READ_BACK, encoding="utf-8")
        run = blender.run_script(str(root / "read.py"), [str(root / "out" / "test_set_men.blend")], timeout=600)
        line = next(x for x in run.stdout.splitlines() if x.startswith("READBACK "))
        cls.saved = json.loads(line[len("READBACK "):])

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_the_saved_character_holds_the_exported_clips_alone(self) -> None:
        self.assertEqual(sorted(self.saved["actions"]), ["Idle_Loop", "Knife_Swing"])
        self.assertEqual(self.saved["fps"], 30)
        self.assertEqual(self.saved["assigned"], [])
        types = {t for t, _ in self.saved["objects"]}
        self.assertEqual(types, {"ARMATURE", "MESH"})
        self.assertEqual({p for t, p in self.saved["objects"] if t == "MESH"}, {"CharacterArmature"})
        self.assertLess(self.report["saved"]["transform_check_max_error_mm"], 0.1)

    def test_the_report(self) -> None:
        clips = self.report["clips"]
        self.assertEqual(self.report["exported"], ["Idle_Loop", "Knife_Swing"])
        self.assertEqual(clips["Knife_Swing"]["frames"], 14)  # 0.45 s rounds to whole frames: 0.467
        self.assertEqual(clips["Knife_Swing"]["steps"][0]["op"], "retime")
        self.assertLess(clips["Punch_Left"]["steps"][0]["rest_error_mm"], 0.01)
        self.assertEqual(self.report["upper_bones"][0], "Torso")
        self.assertIn("Head", self.report["upper_bones"])
        self.assertNotIn("UpperLeg.L", self.report["upper_bones"])

    def test_a_clip_placed_after_another_stands_on_its_feet(self) -> None:
        placed = self.report["clips"]["Punch_After"]  # art #49: moved to Knife_Swing's last feet, not recentred
        self.assertEqual((placed["placed_by"], placed["recentred_m"]), ("place_after", 0.0))
        self.assertEqual(placed["place_after"]["clip"], "Knife_Swing")
        self.assertLess(placed["place_after"]["feet_seam_cm"]["mean_offset"], 0.01)

    def test_an_open_ual_loop_is_closed_one_frame_longer(self) -> None:
        idle = self.report["clips"]["Idle_Loop"]
        self.assertTrue(idle["loop"])
        self.assertEqual(idle["source_open_seam"]["frames_added"], 1)
        self.assertEqual(self.saved["actions"]["Idle_Loop"], [0.0, float(idle["frames"])])
        self.assertLess(idle["travel_left_m"], 0.05)


if __name__ == "__main__":
    unittest.main()
