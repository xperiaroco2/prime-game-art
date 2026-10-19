"""The alien parts kit's face constants (tools/blender/alien_face.py) against godot/alien/alien.gd's copies (art #196,
the PR #222 review): the face materials, the visemes, the eyeballs' inward aim and the blink timing. Plain Python: the
module is read without Blender, the GDScript by pattern."""
from __future__ import annotations

import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GD = ROOT / "godot" / "alien" / "alien.gd"
NUM = r"-?\d+(?:\.\d+)?"


def load_face():
    spec = importlib.util.spec_from_file_location("alien_face", ROOT / "tools" / "blender" / "alien_face.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def color(text: str) -> tuple:
    return tuple(float(x) for x in re.fullmatch(rf"Color\(({NUM}), ({NUM}), ({NUM})\)", text.strip()).groups())


class FaceConstants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = load_face()
        cls.gd = GD.read_text(encoding="utf-8")

    def grab(self, pattern: str) -> re.Match:
        m = re.search(pattern, self.gd, re.M)
        self.assertIsNotNone(m, f"alien.gd has no match for {pattern!r}")
        return m

    def test_lip(self):
        self.assertEqual(color(self.grab(r"^const LIP := (Color\([^)]*\))").group(1)), self.f.LIP)

    def test_face_materials(self):
        for name, (col, rough, spec) in self.f.FACE.items():
            with self.subTest(name=name):
                m = self.grab(rf'"{name}": \[(LIP|Color\([^)]*\)), ({NUM}), ({NUM})\]')
                got = self.f.LIP if m.group(1) == "LIP" else color(m.group(1))
                self.assertEqual((got, float(m.group(2)), float(m.group(3))), (col, rough, spec))

    def test_visemes(self):
        m = self.grab(r"^const VISEMES: Array\[String\] = \[([^\]]*)\]")
        self.assertEqual(tuple(re.findall(r'"([^"]+)"', m.group(1))), self.f.VISEMES)

    def test_eye_aim(self):
        self.assertEqual(float(self.grab(rf"^var aim_in_deg: float = ({NUM})").group(1)), self.f.EYE_AIM_IN)

    def test_blink(self):
        m = self.grab(rf'^const BLINK_MS := \{{"close": ({NUM}), "hold": ({NUM}), "open": ({NUM})\}}')
        self.assertEqual(dict(zip(("close", "hold", "open"), map(float, m.groups()))), self.f.BLINK_MS)
        m = self.grab(rf"^const BLINK_EVERY_S := Vector2\(({NUM}), ({NUM})\)")
        self.assertEqual(tuple(map(float, m.groups())), self.f.BLINK_EVERY_S)


if __name__ == "__main__":
    unittest.main()
