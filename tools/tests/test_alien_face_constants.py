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

    def shader_default(self, shader: str, uniform: str) -> tuple:
        text = (GD.parent / shader).read_text(encoding="utf-8")
        m = re.search(rf"^uniform (?:vec3|float) {uniform}\b[^=]*= (?:vec3\(({NUM}), ({NUM}), ({NUM})\)|({NUM}));", text, re.M)
        self.assertIsNotNone(m, f"{shader} has no default for {uniform}")
        vals = [float(x) for x in m.groups() if x is not None]
        return tuple(vals) if len(vals) > 1 else vals[0]

    def test_accent(self):  # S9 (PR #225 review): the knee, elbow and knuckle accent
        self.assertEqual(self.shader_default("alien_hue.gdshader", "accent"), self.f.ACCENT)

    def test_eye_colours(self):  # S9 (PR #225 review): the eyeball's white, its warm shade and its roughness
        self.assertEqual(self.shader_default("alien_eye.gdshader", "white"), self.f.EYE_WHITE)
        self.assertEqual(self.shader_default("alien_eye.gdshader", "shade"), self.f.EYE_SHADE)
        self.assertEqual(self.shader_default("alien_eye.gdshader", "roughness_value"), self.f.EYE_ROUGH)

    def test_lip_shader(self):  # S9: alien_lip.gdshader's default colour is the lips'
        self.assertEqual(self.shader_default("alien_lip.gdshader", "albedo"), self.f.LIP)

    def test_teal(self):  # S9: the teal and its pale tint, in alien.gd and the assembler (character.json, the GLB)
        m = self.grab(r'^\t"teal": \[(Color\([^)]*\)), (Color\([^)]*\))\]')
        asm = (ROOT / "tools" / "blender" / "alien_assemble.py").read_text(encoding="utf-8")
        hue = re.search(rf'^    "teal": \(({NUM}), ({NUM}), ({NUM})\)', asm, re.M)
        pale = re.search(rf'^PALE_SRGB = \{{"teal": \(({NUM}), ({NUM}), ({NUM})\)', asm, re.M)
        self.assertEqual(color(m.group(1)), tuple(map(float, hue.groups())))
        self.assertEqual(color(m.group(2)), tuple(map(float, pale.groups())))

    def test_rest_channel(self):  # S9b: alien_ao.py's rest-pose UV layers and alien_hue.gdshader's CUSTOM0 agree
        ao = (ROOT / "tools" / "blender" / "alien_ao.py").read_text(encoding="utf-8")
        sh = (ROOT / "godot" / "alien" / "alien_hue.gdshader").read_text(encoding="utf-8")
        self.assertRegex(ao, r'REST_UV = \("rest_xy", "rest_zn"\)')
        offset = float(re.search(rf"ngl_z \+ ({NUM})", ao).group(1))
        self.assertEqual(float(re.search(rf"m_nz = CUSTOM0\.w - ({NUM});", sh).group(1)), offset)
        threshold = float(re.search(rf"if \(CUSTOM0\.w > ({NUM})\)", sh).group(1))
        self.assertTrue(0.0 < threshold < offset - 1.0, "the flag must split absent (0) from any normal z + offset")
        self.assertIn("m_pos = CUSTOM0.xyz;", sh)
        self.assertNotIn("m_nrm", sh)  # the skinned normal no longer drives the gradient

    def test_visemes(self):
        m = self.grab(r"^const VISEMES: Array\[String\] = \[([^\]]*)\]")
        self.assertEqual(tuple(re.findall(r'"([^"]+)"', m.group(1))), self.f.VISEMES)

    def test_eye_aim(self):
        self.assertEqual(float(self.grab(rf"^var aim_in_deg: float = ({NUM})").group(1)), self.f.EYE_AIM_IN)
        # M15b: the convergence the fit sets in the GLB's rest and alien.gd turns the balls by (with splay_deg)
        self.assertEqual(float(self.grab(rf"^const AIM_CONVERGE_DEG := ({NUM})").group(1)), self.f.EYE_AIM_CONVERGE)
        fit = (ROOT / "tools" / "blender" / "alien_socket_fit.py").read_text(encoding="utf-8")
        self.assertIn("EYE_AIM_CONVERGE", fit)

    def test_blink(self):
        m = self.grab(rf'^const BLINK_MS := \{{"close": ({NUM}), "hold": ({NUM}), "open": ({NUM})\}}')
        self.assertEqual(dict(zip(("close", "hold", "open"), map(float, m.groups()))), self.f.BLINK_MS)
        m = self.grab(rf"^const BLINK_EVERY_S := Vector2\(({NUM}), ({NUM})\)")
        self.assertEqual(tuple(map(float, m.groups())), self.f.BLINK_EVERY_S)


if __name__ == "__main__":
    unittest.main()
