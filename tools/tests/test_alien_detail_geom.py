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

    def test_sculpt_m2_is_the_shipped_sculpt(self):
        s = G.sculpt("m2")
        self.assertEqual(s["creases"], G.CREASES)
        self.assertEqual(s["grain"], G.GRAIN)
        self.assertEqual(s["soften"]["passes"], 0)  # no soften: M2's recipe rebuilds M2
        self.assertEqual(s["curvature"], {"smooth": 2, "scale": 120.0, "jaw_smooth": 0})  # M2's curv_smooth, curv_scale
        s["creases"]["neck_front"]["depth"] = 9.0  # a fresh copy: the module's settings stay
        self.assertNotEqual(G.CREASES["neck_front"]["depth"], 9.0)

    def test_sculpt_merges_and_refuses_typos(self):
        s = G.sculpt("m2", {"creases": {"neck_front": {"depth": 0.0}}, "grain": {"face": 0.3}})
        self.assertEqual(s["creases"]["neck_front"], dict(G.CREASES["neck_front"], depth=0.0))
        self.assertEqual(s["grain"]["face"], 0.3)
        for bad in ({"creases": {"neck_frnt": {"depth": 0}}}, {"creases": {"neck_front": {"dept": 0}}},
                    {"grain": {"pores": 1}}, {"soften": {"pass": 3}}, {"jaw": {}}):
            with self.assertRaises(KeyError, msg=bad):
                G.sculpt("m2", bad)
        with self.assertRaises(KeyError):
            G.sculpt("m9")

    def test_m2b_is_softer_than_m2(self):
        m2, m2b = G.sculpt("m2"), G.sculpt("m2b")
        for name in ("neck_front", "neck_back", "lid_fold"):  # the rings and the brow grooves (#196, v27)
            self.assertLess(m2b["creases"][name]["depth"], 0.5 * m2["creases"][name]["depth"], name)
        g, g2 = m2["grain"], m2b["grain"]
        self.assertLess(g2["pore_mm"], g["pore_mm"])  # finer
        self.assertLess(g2["pore_depth_mm"] * g2["face"], 0.5 * g["pore_depth_mm"] * g["face"])  # weaker on the face
        self.assertGreater(g2["pore_depth_mm"], 0.0)  # a faint even grain stays
        self.assertGreater(m2b["soften"]["passes"], 0)  # the jaw's ridge and fold relaxed
        self.assertGreater(m2b["curvature"]["smooth"], m2["curvature"]["smooth"])  # no ragged cavity line
        for name, c in m2b["creases"].items():
            self.assertLessEqual(c["depth"] * c["lines"], G.MAX_DISP_MM, name)

    def test_m6c_is_m2b_with_m2s_grain(self):
        # the engineer on v28 (#196): M2b's neck and creases, M3c's (M2's) fine grain back
        m2, m2b, m6c = G.sculpt("m2"), G.sculpt("m2b"), G.sculpt("m6c")
        self.assertEqual(m6c["grain"], m2["grain"])
        for part in ("creases", "soften", "curvature"):
            self.assertEqual(m6c[part], m2b[part], part)

    def test_soften_stays_inside_the_bake_rays(self):
        # the capped cage starts rays at most CAGE max_mm out and they run CAGE ray_mm: they reach ray - max inside the
        # low mesh; the relaxed jaw plus the deepest crease must stay within that
        cage = re.search(r'^CAGE = \{"max_mm": ([0-9.]+),.*"ray_mm": ([0-9.]+)',
                         (ROOT / "tools" / "blender" / "alien_texture_geom.py").read_text(encoding="utf-8"), re.M)
        inside = float(cage.group(2)) - float(cage.group(1))
        self.assertLessEqual(G.sculpt("m2b")["soften"]["max_mm"], inside)

    def test_edge_weight(self):
        self.assertEqual(G.edge_weight(0.5, 0.15, 0.5), 0.0)  # flat
        self.assertEqual(G.edge_weight(1.0, 0.15, 0.5), 1.0)  # a sharp ridge
        self.assertEqual(G.edge_weight(0.0, 0.15, 0.5), 1.0)  # a sharp fold, the same
        self.assertAlmostEqual(G.edge_weight(0.6, 0.15, 0.5), G.edge_weight(0.4, 0.15, 0.5))
        self.assertLess(G.edge_weight(0.6, 0.15, 0.5), G.edge_weight(0.7, 0.15, 0.5))

    def test_finger_k_matches_the_cage(self):
        cage = (ROOT / "tools" / "blender" / "alien_cage.py").read_text(encoding="utf-8")
        detail = (ROOT / "tools" / "blender" / "alien_detail.py").read_text(encoding="utf-8")
        k = lambda s: float(re.search(r"^FINGER_K = ([0-9.]+)", s, re.M).group(1))  # noqa: E731
        self.assertEqual(k(cage), k(detail))


if __name__ == "__main__":
    unittest.main()
