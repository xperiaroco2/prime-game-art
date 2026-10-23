"""The static heads' skin colour study (art #196, 2026-10-23): tools/blender/alien_tint_study.py's colour math, plain
Python (the shader's recolour_to on one colour, the saturation cap, variant C's deeper lip shade) and the variants'
parameter sets."""
from __future__ import annotations

import colorsys
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
import alien_tint_study as T  # noqa: E402

REG = {"skin": [0.376, 0.804, 0.804], "lips": [0.376, 0.796, 0.796], "marks": [0.322, 0.726, 0.729],
       "front": [0.82, 0.93, 0.88]}


class TintStudyTest(unittest.TestCase):
    def close(self, a, b, tol=1e-3):
        for x, y in zip(a, b):
            self.assertAlmostEqual(x, y, delta=tol)

    def test_recolour_identity_and_target(self):
        base = tuple(REG["skin"])
        self.close(T.recolour(base, base, base), base)
        coral = (0.93, 0.55, 0.56)
        self.close(T.recolour(base, base, coral), coral)  # the base itself lands on the target

    def test_cap(self):
        h, s, v = colorsys.rgb_to_hsv(*T.cap((0.98, 0.78, 0.30), 0.48))
        self.assertLessEqual(s, 0.48 + 1e-6)
        self.close(T.cap((0.8, 0.8, 0.8), 0.1), (0.8, 0.8, 0.8))

    def test_deeper_is_darker_greyer_warmer(self):
        teal = (0.38, 0.80, 0.80)
        h0, s0, v0 = colorsys.rgb_to_hsv(*teal)
        h1, s1, v1 = colorsys.rgb_to_hsv(*T.deeper(teal))
        self.assertLess(v1, v0)
        self.assertLess(s1, s0)
        d0 = abs(((0.03 - h0 + 0.5) % 1.0) - 0.5)
        d1 = abs(((0.03 - h1 + 0.5) % 1.0) - 0.5)
        self.assertLess(d1, d0)  # nearer red-orange

    def test_variant_a_follows_the_skin(self):
        for i in range(5):
            _, p = T.variant("A", i, REG)
            for k in ("lip", "mark", "front"):
                self.assertEqual(p[f"{k}_base"], [round(x, 4) for x in REG["skin"]])
                self.assertEqual(p[f"{k}_color"], p["skin_color"])

    def test_variants_b_d_e(self):
        _, p = T.variant("B1", 1, REG)
        self.assertEqual(p["lip_base"], REG["lips"])
        self.close(p["lip_color"], T.hexc(T.LIP_FIXED["B1"][1]), 1e-4)
        self.assertEqual(p["mark_color"], p["skin_color"])
        label, p = T.variant("D", 2, REG)
        self.assertIn("lavender", label)
        self.assertEqual(p["lip_color"], p["mark_color"])
        _, p = T.variant("E", 0, REG)  # E1: the build's own colours
        self.assertEqual(p["skin_color"], REG["skin"])
        self.assertEqual(p["front_color"], REG["front"])
        for i in range(1, len(T.PALETTES)):
            _, p = T.variant("E", i, REG)
            self.assertLessEqual(colorsys.rgb_to_hsv(*p["skin_color"])[1], T.CAP["skin"] + 1e-3)
            self.assertLessEqual(colorsys.rgb_to_hsv(*p["front_color"])[1], T.CAP["front"] + 1e-3)


if __name__ == "__main__":
    unittest.main()
