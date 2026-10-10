"""The jaw check's pure parts (um/jaw.py, art #42): the sight lines, reading a ray's hits and the problems."""

from __future__ import annotations

import math
import unittest

from runner.commands import _assembly

_assembly.recipe_module()  # puts tools/blender on the path
from um import jaw  # noqa: E402


def rays(head_y, blocker=None):
    """One character's measure with the same hit on every view and level."""
    return {"rays": {v: [{"dz_mm": dz, "head_y": head_y, "blocker": blocker} for dz in jaw.LEVELS_MM]
                     for v in jaw.SIGHT_DEG}}


class SightLines(unittest.TestCase):
    def test_directions(self):
        d = jaw.sight_dirs()
        self.assertEqual(set(d), {"front", "threequarter_L", "threequarter_R"})
        self.assertAlmostEqual(d["front"][1], -1.0)
        self.assertGreater(d["threequarter_L"][0], 0.0)
        self.assertLess(d["threequarter_R"][0], 0.0)
        for v in d.values():
            self.assertAlmostEqual(math.hypot(*v), 1.0)


class ReadRay(unittest.TestCase):
    def test_head_met_first(self):
        self.assertEqual(jaw.read_ray([("head", 1.93, -0.118), ("top", 2.05, -0.03)]), {"head_y": -0.118, "blocker": None})

    def test_face_parts_in_front_do_not_block(self):
        self.assertIsNone(jaw.read_ray([("face", 1.92, -0.13), ("head", 1.93, -0.118)])["blocker"])

    def test_hair_in_front_blocks(self):
        r = jaw.read_ray([("head", 1.93, -0.118), ("mask", 1.91, -0.13), ("hair", 1.90, -0.14)])
        self.assertEqual(r, {"head_y": -0.118, "blocker": "hair"})

    def test_through_a_hole(self):
        r = jaw.read_ray([("top", 2.02, -0.04), ("head", 2.08, 0.03)])
        self.assertEqual(r, {"head_y": 0.03, "blocker": "top"})

    def test_no_head(self):
        self.assertEqual(jaw.read_ray([("top", 2.02, -0.04)]), {"head_y": None, "blocker": "top"})
        self.assertEqual(jaw.read_ray([]), {"head_y": None, "blocker": None})


class Problems(unittest.TestCase):
    def test_whole_jaw(self):
        self.assertEqual(jaw.problems("m1", rays(-0.115)), [])

    def test_cut_jaw(self):
        out = jaw.problems("m4", rays(0.03))
        self.assertEqual(len(out), len(jaw.SIGHT_DEG) * len(jaw.LEVELS_MM))
        self.assertIn("cut open", out[0])

    def test_no_head(self):
        self.assertIn("cut away", jaw.problems("m4", rays(None))[0])

    def test_hair_may_cover(self):
        self.assertEqual(jaw.problems("m2", rays(-0.155, blocker="hair")), [])

    def test_covered_jaw(self):
        m = rays(-0.115)
        m["rays"]["threequarter_L"][1]["blocker"] = "mask"
        self.assertEqual(jaw.problems("m2", m), ["m2: threequarter_L view, 20 mm below the mouth: the jaw is covered by "
                                                 "the mask part"])


if __name__ == "__main__":
    unittest.main()
