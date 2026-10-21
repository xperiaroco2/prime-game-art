"""M15b (art #196, PR #253 review minor 2): the eyeballs' aim on a kit whose units look straight ahead. alien_m6.py
writes the units' own outward look (`splay_deg`) into alien_lip's LIDS_MARKER; alien.gd turns the balls in by
AIM_CONVERGE_DEG plus it, or by aim_in_deg on a kit without it; alien_socket_fit.py sets the same turn in the GLB's
rest. Plain Python: the Blender and GDScript sources are read by pattern, the angle formula is checked on its own."""
from __future__ import annotations

import math
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
M6 = (ROOT / "tools" / "blender" / "alien_m6.py").read_text(encoding="utf-8")
FIT = (ROOT / "tools" / "blender" / "alien_socket_fit.py").read_text(encoding="utf-8")
GD = (ROOT / "godot" / "alien" / "alien.gd").read_text(encoding="utf-8")


def body(src: str, start: str, end: str) -> str:
    return src[src.index(start):src.index(end, src.index(start))]


def outward(fx: float, fy: float, sx: float) -> float:
    """alien_m6.eye_splay's and alien_socket_fit._in_deg's angle: a forward (fx, fy) (the face looks along -Y)
    against straight ahead, positive toward its side's temple (sx +1 left, -1 right)."""
    return math.degrees(math.atan2(sx * fx, -fy))


class SplayFormula(unittest.TestCase):
    def test_the_formula_is_the_one_in_both_scripts(self):
        self.assertIn("math.degrees(math.atan2(sx * f.x, -f.y))", body(M6, "def eye_splay", "def ball_radius"))
        self.assertIn("math.degrees(math.atan2(sx * fs.x, -fs.y))", body(FIT, "def _in_deg", "def rest_aim"))

    def test_straight_ahead_is_zero_and_the_temple_is_positive(self):
        self.assertAlmostEqual(outward(0.0, -1.0, 1.0), 0.0)
        a = math.radians(7.9)
        self.assertAlmostEqual(outward(math.sin(a), -math.cos(a), 1.0), 7.9)  # left eye, looking to +X (its temple)
        self.assertAlmostEqual(outward(-math.sin(a), -math.cos(a), -1.0), 7.9)  # the right eye's mirror
        self.assertAlmostEqual(outward(-math.sin(a), -math.cos(a), 1.0), -7.9)  # left eye turned toward the nose


class SplayWiring(unittest.TestCase):
    def test_alien_m6_writes_the_splay_into_the_lids_marker(self):
        self.assertRegex(M6, r'rep\["splay_deg"\] = eye_splay\(\)')
        self.assertRegex(M6, r'"splay_deg": rep\["splay_deg"\]')

    def test_alien_gd_reads_it_and_falls_back_to_aim_in_deg(self):
        fn = body(GD, "func rest_aim_deg", "\n\n")
        self.assertIn("AIM_CONVERGE_DEG + _splay_deg if _has_splay else aim_in_deg", fn)
        read = body(GD, "func _read_lid_reach", "\n\n")
        self.assertIn("_has_splay = true", read)
        self.assertRegex(read, r'has\("splay_deg"\)')

    def test_alien_gd_resets_it_for_each_kit(self):
        setup = body(GD, "func setup(", "character = root")
        for line in ("_lid_reach = {}", "_has_splay = false", "_splay_deg = 0.0"):
            self.assertIn(line, setup)

    def test_the_balls_turn_by_it(self):
        self.assertRegex(GD, r"var aim: float = rest_aim_deg\(\) if face_look == \"s5\" else 0\.0")
        self.assertNotRegex(GD, r"\S\t+\S")  # no tab inside a line (PR #253 review minor 1)

    def test_the_fit_sets_the_same_rest_in_the_glb(self):
        self.assertIn("from alien_face import EYE_AIM_CONVERGE", FIT)
        self.assertIn("want = EYE_AIM_CONVERGE + splay", body(FIT, "def rest_aim", "def measure"))
        self.assertIn('aim[d] = rest_aim(ball, sock, side)', FIT)


if __name__ == "__main__":
    unittest.main()
