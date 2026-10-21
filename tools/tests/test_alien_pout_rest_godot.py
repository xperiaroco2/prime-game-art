"""M16 (art #196, brief UPDATE 29): the pout at rest in Godot 4.7.2, headless (godot/alien/pout_rest_check.gd) on the
M16d kit (on M15's head): the closed pieces, unskinned meshes under the rigid Mouth socket, mirrored across the
body's centre plane within 0.1 mm, the rest piece shown with no motion (lip_drop, pucker, jaw_thrust 0), and the talk
at rest (before the test line and after it) the rest piece with no pucker or drop. Skips without Godot or the raw kit."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runner import common, pins  # noqa: E402
from runner.commands import _godot  # noqa: E402

HAVE_GODOT = common.tool_path(pins.GODOT_ENV, None) is not None
GLB = common.raw_dir() / "review" / "char" / "alien-parts-kit" / "M16d" / "export" / "alien_character.glb"
NAME = "alien_pout_rest_check"
TOL_MM = 0.1


@unittest.skipUnless(HAVE_GODOT and GLB.is_file(), "needs Godot and the M16d raw kit")
class PoutRestGodotTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _godot.clear_staged({NAME})
        res = _godot.stage(GLB, NAME)
        _godot.import_project()
        code, cls.out = _godot.godot(["--headless", "--path", str(_godot.PROJECT), "-s",
                                      "res://alien/pout_rest_check.gd", "--", res], 170)
        line = next((ln for ln in cls.out.splitlines() if ln.startswith("POUT_REST ")), None)
        if code != 0 or line is None:
            raise AssertionError(f"pout_rest_check.gd: exit {code}\n{cls.out[-2000:]}")
        cls.d = json.loads(line[10:])

    def test_the_closed_pieces_are_mirrored(self):
        self.assertEqual(sorted(self.d["pieces"]), ["M", "rest", "small"])
        for s, r in self.d["pieces"].items():
            self.assertGreater(r["verts"], 100, s)
            self.assertLess(r["mirror_mm"], TOL_MM, s)

    def test_rest_is_shown_still(self):
        self.assertTrue(self.d["shown"])
        for u, v in self.d["uniforms"].items():
            self.assertEqual(v, 0.0, u)

    def test_the_talk_at_rest(self):
        for t, s in self.d["talk"].items():
            self.assertEqual(s["piece"], "rest", t)
            self.assertEqual(s["pucker"], 0.0, t)
            self.assertLess(abs(s["drop"]), 1e-6, t)


if __name__ == "__main__":
    unittest.main()
