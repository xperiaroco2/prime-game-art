"""The lean edit's settings (`lean {deg, bone}`, art #33): the step schema takes a number of degrees and an optional
spine bone (Torso by default). The edit itself runs in Blender (test_anim_edit_blender: the women's push leant 30
degrees). Pure Python; no Blender needed."""

from __future__ import annotations

import sys
import unittest

from runner import common

sys.path.insert(0, str(common.ROOT / "tools" / "blender"))
import anim_edit_math as em  # noqa: E402
import anim_set_cfg  # noqa: E402


class LeanStepTest(unittest.TestCase):
    def test_the_schema_takes_a_lean(self) -> None:
        self.assertEqual(em.check_steps([{"op": "lean", "deg": 30}]), [])
        self.assertEqual(em.check_steps([{"op": "lean", "deg": -10.5, "bone": "Chest", "body": "women"}]), [])
        self.assertEqual(em.params({"op": "lean", "deg": 30}), {"deg": 30, "bone": "Torso"})

    def test_bad_leans_are_named(self) -> None:
        self.assertTrue(any("missing 'deg'" in e for e in em.check_steps([{"op": "lean"}])))
        self.assertTrue(em.check_steps([{"op": "lean", "deg": "auto"}]))
        self.assertTrue(em.check_steps([{"op": "lean", "deg": 30, "bone": 3}]))
        self.assertTrue(em.check_steps([{"op": "lean", "deg": 30, "pitch": 2}]))

    def test_the_mvp_push_layer_leans(self) -> None:
        cfg = anim_set_cfg.load(common.ROOT / "tools" / "blender" / "anim_sets" / "mvp.toml")
        push = [c for c in cfg["clips"] if c["name"] == "Push_Upper_Loop"][0]
        self.assertIn({"op": "lean", "deg": 30}, push["edits"])


if __name__ == "__main__":
    unittest.main()
