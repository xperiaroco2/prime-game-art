"""The thumb's rigid skin weights (art #196, M10b): alien_thumb.rigid on single vertices, and alien_m6 applying it."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLENDER = ROOT / "tools" / "blender"
spec = importlib.util.spec_from_file_location("alien_thumb_m10b", BLENDER / "alien_thumb.py")
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)


class RigidThumbTest(unittest.TestCase):
    def test_segments_collapse_onto_the_metacarpal_and_the_hand(self):
        w = {"LeftThumbMetacarpal": 0.2, "LeftThumbProximal": 0.5, "LeftThumbDistal": 0.3}
        out = T.rigid(w, "Left")
        self.assertEqual(set(out), {"LeftThumbMetacarpal", "LeftHand"})
        self.assertAlmostEqual(out["LeftThumbMetacarpal"], T.METACARPAL)
        self.assertAlmostEqual(out["LeftHand"], T.HAND)

    def test_the_root_keeps_its_hand_share_and_the_total(self):
        w = {"LeftHand": 0.6, "LeftThumbMetacarpal": 0.4}
        out = T.rigid(w, "Left")
        self.assertAlmostEqual(sum(out.values()), 1.0)
        self.assertAlmostEqual(out["LeftHand"], 0.6 + T.HAND * 0.4)
        self.assertAlmostEqual(out["LeftThumbMetacarpal"], T.METACARPAL * 0.4)

    def test_other_groups_and_the_other_side_are_untouched(self):
        w = {"LeftIndexProximal": 0.1, "RightThumbDistal": 0.5, "LeftThumbDistal": 0.4}
        out = T.rigid(w, "Left")
        self.assertEqual(out["LeftIndexProximal"], 0.1)
        self.assertEqual(out["RightThumbDistal"], 0.5)
        self.assertNotIn("LeftThumbDistal", out)
        self.assertEqual(T.rigid({"LeftHand": 1.0}, "Left"), {"LeftHand": 1.0})

    def test_the_shares_add_up(self):
        self.assertAlmostEqual(T.METACARPAL + T.HAND, 1.0)
        self.assertGreater(T.METACARPAL, T.HAND)

    def test_alien_m6_applies_it_by_default(self):
        src = (BLENDER / "alien_m6.py").read_text(encoding="utf-8")
        self.assertIn('"--thumb", choices=("rigid", "segments"), default="rigid"', src)
        self.assertIn("alien_thumb.apply(body)", src)


if __name__ == "__main__":
    unittest.main()
