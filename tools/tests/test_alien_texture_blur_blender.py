"""The accent's masked blur (art #196, M3c), alien_texture_geom.blur on numpy arrays in background Blender's Python
(the runner's Python has no numpy): nothing leaks across the mask's edge either way, a constant stays constant, and
on one island far from its edge the blur keeps the mean. Skips without Blender."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from runner import blender, common, pins

HAVE = bool((path := common.tool_path(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)) and path.is_file())
GEOM = common.ROOT / "tools" / "blender"

SCRIPT = '''
import json, sys
import numpy as np
sys.path.insert(0, sys.argv[sys.argv.index("--") + 1])
import alien_texture_geom as T
out = sys.argv[sys.argv.index("--") + 2]
n, r = 96, 4
mask = np.zeros((n, n), bool)
mask[8:56, 8:56] = True                      # the island
spot = np.zeros((n, n), np.float32)
spot[28:36, 28:36] = 1.0                     # a spot far (20 texels) from its edge
outside = np.where(mask, 0.0, 1e6).astype(np.float32)  # huge values outside the island
res = {}
b = T.blur(spot + outside, mask, r, np)
res["inside_max"] = float(b[mask].max())
res["outside_kept"] = bool((b[~mask] == (spot + outside)[~mask]).all())
res["mean_before"] = float(spot[mask].mean())
res["mean_after"] = float(b[mask].mean())
res["peak_after"] = float(b[32, 32])
c = T.blur(np.full((n, n), 0.25, np.float32) + outside, mask, r, np)
res["const_range"] = [float(c[mask].min()), float(c[mask].max())]
res["r0_same"] = bool((T.blur(spot, mask, 0, np) == spot).all())
open(out, "w").write(json.dumps(res))
'''


@unittest.skipUnless(HAVE, "needs Blender")
class BlurBlenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = TemporaryDirectory()
        d = Path(cls.tmp.name)
        script = d / "blur_check.py"
        script.write_text(SCRIPT, encoding="utf-8", newline="\n")
        blender.run_script(script, [str(GEOM), str(d / "out.json")], timeout=300)
        cls.res = json.loads((d / "out.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_no_leak_across_the_mask(self) -> None:
        self.assertLessEqual(self.res["inside_max"], 1.0 + 1e-5)  # the outside's 1e6 never reaches in
        self.assertTrue(self.res["outside_kept"])
        self.assertTrue(self.res["r0_same"])

    def test_constant_stays(self) -> None:
        lo, hi = self.res["const_range"]
        self.assertAlmostEqual(lo, 0.25, places=5)
        self.assertAlmostEqual(hi, 0.25, places=5)

    def test_mean_kept_on_one_island(self) -> None:
        self.assertAlmostEqual(self.res["mean_after"], self.res["mean_before"], places=5)
        self.assertLess(self.res["peak_after"], 0.9)  # it did blur


if __name__ == "__main__":
    unittest.main()
