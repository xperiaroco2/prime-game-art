"""M13b (art #196, PR #248's review minor 7): the alien kit's Godot sources parse in Godot 4.7.2, headless
(godot/alien/parse_check.gd): every shader under godot/alien/ compiles in the dummy renderer's parser (no "SHADER
ERROR", its uniforms listed; a broken shader lists none) and alien.gd, alien_talk.gd and alien_static.gd load and
reload; alien_static.gd's colour slot maths (GDScript) match tools/blender/alien_colour_geom.py within 1e-5 (PR #304's
review). Skips without Godot."""

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
sys.path.insert(0, str(ALIEN.parents[1] / "tools" / "blender"))
import alien_colour_geom as G  # noqa: E402


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
        # parse_check.gd calls set_colours with an unknown gills value on purpose (it must push_error and return {}),
        # so its "ERROR: alien_static: unknown gills" line is expected: a filter widened to every "ERROR:" line would
        # need to allow that one.
        bad = [ln for ln in self.out.splitlines()
               if "SHADER ERROR" in ln or "Parse Error" in ln or "SCRIPT ERROR" in ln or "compilation failed" in ln]
        self.assertEqual(bad, [])

    def test_colour_slot_maths(self):  # PR #304's review: the GDScript maths against Python's, not only the proof
        cs = self.d["colour_slots"]
        self.assertGreaterEqual(len(cs["cases"]), 19)
        for case in cs["cases"]:
            want = G.slot_colours(cs["bases"], case["picks"])
            self.assertEqual(sorted(want), sorted(case["uniforms"]), case["picks"])
            for k, v in want.items():
                got = case["uniforms"][k]
                for x, y in zip(v if isinstance(v, tuple) else (v,), got if isinstance(got, list) else [got]):
                    self.assertAlmostEqual(x, y, delta=1e-5, msg=(case["picks"], k))
        self.assertTrue(cs["unknown_gills_empty"])  # an unknown gill mode is an error, as in Python and JS
        with self.assertRaises(ValueError):
            G.slot_colours(cs["bases"], {"gills": "fringe"})

    def test_every_shader_parses(self):
        files = sorted(p.name for p in ALIEN.glob("*.gdshader"))
        self.assertTrue(files)
        self.assertEqual(sorted(self.d["shaders"]), files)
        for name, r in self.d["shaders"].items():
            self.assertTrue(r["loaded"], name)
            self.assertGreater(r["uniforms"], 0, f"{name}: no uniforms listed (a parse error)")

    def test_a_broken_shader_is_caught(self):  # M14 (PR #250's review): the check can fail
        code, out = _godot.godot(["--headless", "--path", str(_godot.PROJECT), "-s", "res://alien/parse_check.gd",
                                  "--", "broken"], 150)
        line = next((ln for ln in out.splitlines() if ln.startswith("PARSE_BROKEN ")), None)
        self.assertIsNotNone(line, out[-1500:])
        self.assertEqual(json.loads(line[13:])["uniforms"], 0)
        self.assertIn("SHADER ERROR", out)

    def test_jaw_weight_check(self):  # PR #251's review minor 7: alien.gd's has_jaw_weight, asked twice (cached)
        self.assertEqual(self.d["jaw_weight"], {"none": [False, False], "alpha_one": [False, False],
                                                "weighted": [True, True], "null": False})

    def test_scripts_load(self):
        for path, r in self.d["scripts"].items():
            self.assertTrue(r["loaded"] and r["can_instantiate"], path)
            self.assertEqual(r["reload"], 0, path)


if __name__ == "__main__":
    unittest.main()
