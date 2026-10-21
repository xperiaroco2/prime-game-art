"""M16 (art #196, brief UPDATE 29): the pout's closed pieces (rest, M, small) are mirrored across the face's centre
line within 0.1 mm, built from the current code on M10c's kit (tools/blender/alien_pout_check.py), and so are the M16
kit's own pieces. Skips without Blender or the raw kits."""

from __future__ import annotations

import json
import unittest

from runner import blender, common, pins

HAVE = bool((path := common.tool_path(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)) and path.is_file())
KITS = common.raw_dir() / "review" / "char" / "alien-parts-kit"
BASE, M16 = KITS / "M10c" / "export", KITS / "M16" / "export"
SCRIPT = common.ROOT / "tools" / "blender" / "alien_pout_check.py"
TOL_MM = 0.1


def run(kit, *extra) -> dict:
    r = blender.run_script(SCRIPT, ["--kit", str(kit), *extra], timeout=600)
    out = (r.stdout or "") + (r.stderr or "")
    line = next((ln for ln in out.splitlines() if ln.startswith("POUT_SYM ")), None)
    if line is None:
        raise AssertionError(f"alien_pout_check.py printed no POUT_SYM line\n{out[-2000:]}")
    return json.loads(line[9:])


@unittest.skipUnless(HAVE and (BASE / "alien_character.blend").is_file(), "needs Blender and M10c's raw kit")
class PoutRestBuiltTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = run(BASE)

    def test_the_closed_pieces_are_mirrored(self):
        self.assertEqual(sorted(self.d["built"]), ["M", "rest", "small"])
        for s, r in self.d["built"].items():
            self.assertEqual(r["form"], "tubes", s)
            self.assertLess(r["max_mm"], TOL_MM, s)
            self.assertAlmostEqual(r["x_mm"][0], -r["x_mm"][1], delta=TOL_MM, msg=s)

    def test_on_the_centre_line(self):
        self.assertAlmostEqual(self.d["socket_x_mm"], 0.0, delta=TOL_MM)


@unittest.skipUnless(HAVE and (M16 / "alien_character.blend").is_file(), "needs Blender and the M16 raw kit")
class PoutRestKitTest(unittest.TestCase):
    def test_the_kits_closed_pieces_are_mirrored(self):
        d = run(M16, "--kit-pieces")
        self.assertEqual(sorted(d["kit"]), ["M", "rest", "small"])
        for s, r in d["kit"].items():
            self.assertLess(r["max_mm"], TOL_MM, s)


if __name__ == "__main__":
    unittest.main()
