"""The alien skin's texture UV parts and detail sculpt settings (art #196, M2): tools/blender/alien_detail_geom.py is
pure Python; alien_detail.py's numpy formulas follow it, and its finger constant must match alien_cage.py's."""
from __future__ import annotations

import math
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
import alien_detail_geom as G  # noqa: E402


class PartsTest(unittest.TestCase):
    def test_bones_to_parts(self):
        cases = {"Head": "head", "Neck": "head", "Hips": "torso", "UpperChest": "torso", "LeftShoulder": "torso",
                 "LeftUpperArm": "arm_L", "RightLowerArm": "arm_R", "LeftHand": "hand_L", "RightIndexDistal": "hand_R",
                 "LeftThumbMetacarpal": "hand_L", "LeftUpperLeg": "leg_L", "RightLowerLeg": "leg_R",
                 "LeftFoot": "foot_L", "RightToes": "foot_R", "Root": "torso"}
        for bone, part in cases.items():
            self.assertEqual(G.part_of_bone(bone), part, bone)

    def test_every_part_has_a_density(self):
        for p in ("head", "torso_front", "torso_back", "arm_L", "hand_R_a", "hand_L_b", "leg_R", "foot_L", "foot_L_sole"):
            self.assertGreater(G.density(p), 0.0, p)
        self.assertGreater(G.DENSITY["head"], G.DENSITY["torso"])  # the face and hands are weighted up
        self.assertGreater(G.DENSITY["hand"], G.DENSITY["torso"])

    def test_branch_cut(self):
        self.assertTrue(G.crosses_branch(3.0, -3.0))  # either side of the cut (+-pi)
        self.assertFalse(G.crosses_branch(0.2, -0.2))  # either side of the seen side (0)
        self.assertFalse(G.crosses_branch(1.0, 2.0))
        self.assertFalse(G.crosses_branch(-3.1, -3.0))

    def test_margin_fits_mips(self):
        self.assertGreaterEqual(G.UV["margin_px"] * 2048 / G.UV["size"], 8)  # still 8 px at 2K


class CreaseTest(unittest.TestCase):
    def test_profile(self):
        self.assertAlmostEqual(G.crease(0.0, 1.0), -1.0)
        self.assertAlmostEqual(G.crease(1.0, 1.0), 0.0)
        self.assertGreater(G.crease(math.sqrt(3.0), 1.0), 0.2)  # the shoulder
        self.assertLess(abs(G.crease(8.0, 1.0)), 1e-6)

    def test_no_volume_change(self):  # the profile integrates to zero across the line
        h = 0.001
        total = sum(G.crease(-10 + i * h, 1.0) for i in range(int(20 / h))) * h
        self.assertLess(abs(total), 1e-3)

    def test_silhouette_kept(self):
        for name, c in G.CREASES.items():
            worst = c["depth"] * c["lines"]
            self.assertLessEqual(worst, G.MAX_DISP_MM, name)
            self.assertGreater(c["width"], 0.0, name)
        self.assertLessEqual(G.MAX_DISP_MM, 3.0)  # "within a few millimetres"
        self.assertLess(G.GRAIN["pore_depth_mm"] + G.GRAIN["peel_depth_mm"], 0.2)

    def test_line_offsets(self):
        self.assertEqual(G.line_offsets(1, 5.0), [0.0])
        self.assertEqual(G.line_offsets(3, 1.6), [-1.6, 0.0, 1.6])

    def test_finger_k_matches_the_cage(self):
        cage = (ROOT / "tools" / "blender" / "alien_cage.py").read_text(encoding="utf-8")
        detail = (ROOT / "tools" / "blender" / "alien_detail.py").read_text(encoding="utf-8")
        k = lambda s: float(re.search(r"^FINGER_K = ([0-9.]+)", s, re.M).group(1))  # noqa: E731
        self.assertEqual(k(cage), k(detail))


if __name__ == "__main__":
    unittest.main()
