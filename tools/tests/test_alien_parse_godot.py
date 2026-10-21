"""M13b (art #196, PR #248's review minor 7): the alien kit's Godot sources parse in Godot 4.7.2, headless
(godot/alien/parse_check.gd): every shader under godot/alien/ compiles in the dummy renderer's parser (no "SHADER
ERROR", its uniforms listed; a broken shader lists none) and alien.gd and alien_talk.gd load and reload. Skips without
Godot."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runner import common, pins  # noqa: E402
from runner.commands import _godot  # noqa: E402

HAVE_GODOT = common.tool_path(pins.GODOT_ENV, None) is not None
ALIEN = Path(__file__).resolve().parents[2] / "godot" / "alien"


@unittest.skipUnless(HAVE_GODOT, "needs Godot")
class AlienParseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        code, cls.out = _godot.godot(["--headless", "--path", str(_godot.PROJECT), "-s", "res://alien/parse_check.gd"],
                                     150)
        line = next((ln for ln in cls.out.splitlines() if ln.startswith("PARSE ")), None)
        if code != 0 or line is None:
            raise AssertionError(f"parse_check.gd: exit {code}\n{cls.out[-2000:]}")
        cls.d = json.loads(line[6:])

    def test_no_error_lines(self):
        bad = [ln for ln in self.out.splitlines()
               if "SHADER ERROR" in ln or "Parse Error" in ln or "SCRIPT ERROR" in ln or "compilation failed" in ln]
        self.assertEqual(bad, [])

    def test_every_shader_parses(self):
        files = sorted(p.name for p in ALIEN.glob("*.gdshader"))
        self.assertTrue(files)
        self.assertEqual(sorted(self.d["shaders"]), files)
        for name, r in self.d["shaders"].items():
            self.assertTrue(r["loaded"], name)
            self.assertGreater(r["uniforms"], 0, f"{name}: no uniforms listed (a parse error)")

    def test_scripts_load(self):
        for path, r in self.d["scripts"].items():
            self.assertTrue(r["loaded"] and r["can_instantiate"], path)
            self.assertEqual(r["reload"], 0, path)


if __name__ == "__main__":
    unittest.main()
