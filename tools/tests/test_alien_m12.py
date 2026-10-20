"""M12 (art #196): the red pout mouth mp1, the third mouth design. Plain Python: alien_lips_geom's size transform, the
pout's lip shape and contact layout, and their copies in alien_m12.py, alien_mouths.py, alien.gd, the shaders and
alien_talk.gd (read by pattern; no Blender, no Godot)."""
from __future__ import annotations

import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BL = ROOT / "tools" / "blender"
GA = ROOT / "godot" / "alien"
VISEMES = {"rest", "M", "small", "A", "E", "O"}


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, BL / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


LP = load("alien_lips_geom")


def uniforms(path: Path) -> set[str]:
    return set(re.findall(r"^(?:instance )?uniform \w+ (\w+)", path.read_text(encoding="utf-8"), re.M))


def gd_dict_keys(text: str, name: str) -> set[str]:
    m = re.search(r"const %s := \{(.*?)\}\n" % name, text, re.S)
    if m is None:
        raise AssertionError(f"no const {name}")
    return set(re.findall(r'"(\w+)":', m.group(1)))


class SizeTest(unittest.TestCase):
    def test_identity_at_one(self):
        w = lambda x, y: (x * 0.001, 1.47 - y * 0.001)  # noqa: E731
        self.assertIs(LP.scale_size(w, 1.0, 1.47), w)

    def test_scales_about_the_centre_line_and_the_socket(self):
        w = lambda x, y: (x * 0.001, 1.47 - y * 0.001)  # noqa: E731
        s = LP.scale_size(w, 0.9, 1.47)
        self.assertAlmostEqual(s(20, 0)[0], 0.018)
        self.assertAlmostEqual(s(0, 0)[1], 1.47)  # the seam stays on the socket
        self.assertAlmostEqual(s(0, 30)[1], 1.47 - 0.027)


class PoutShapeTest(unittest.TestCase):
    def test_the_sheets_fullness_and_a_clearer_bow(self):
        p = LP.LIP_SHAPE_POUT
        self.assertGreater(p["lower"], p["upper"])  # the lower lip the bigger cushion
        self.assertGreater(p["upper"], LP.LIP_SHAPE["upper"])  # mp1's upper lip fuller than the frog's
        self.assertGreater(p["corner"], LP.LIP_SHAPE["corner"])  # a little rounder ends
        self.assertEqual(set(p), set(LP.LIP_SHAPE) | {"size", "ring_corner"})
        # the open rings' corners fuller than the closed lips' ends, and only for the pout
        th = 0.0
        thin = LP.ring_width(th, 1.0, 1.0, 0.5, "E", dict(p, ring_corner=p["corner"]))
        self.assertGreater(LP.ring_width(th, 1.0, 1.0, 0.5, "E", p), thin)

    def test_merged_pout(self):
        p = LP.merged_pout({"size": 0.95, "ring": {"O": 0.3}})
        self.assertEqual(p["size"], 0.95)
        self.assertEqual(p["ring"], {"A": 1.0, "E": 1.0, "O": 0.3})
        self.assertEqual(LP.LIP_SHAPE_POUT["ring"]["O"], 0.5)  # the default is not changed
        self.assertEqual(LP.merged_pout(None), LP.LIP_SHAPE_POUT)


class LayoutTest(unittest.TestCase):
    def test_the_contact_layer_and_its_channel(self):
        self.assertEqual(LP.CONTACT_UV_MOUTH2, ("contact_mouth2", ("pout", "")))
        gd = (GA / "alien.gd").read_text(encoding="utf-8")
        m = re.search(r'const CONTACT_CHANNEL2 := \{([^}]*)\}', gd)
        self.assertIsNotNone(m)
        self.assertEqual({k: int(v) for k, v in re.findall(r'"(\w+)": (\d+)', m.group(1))}, {"pout": 0})
        self.assertIn('set_shader_parameter("contact_pick2"', gd)
        hue = (GA / "alien_hue.gdshader").read_text(encoding="utf-8")
        self.assertIn("uniform vec2 contact_pick2 = vec2(0.0);", hue)  # off by default: older kits unchanged
        self.assertIn("CUSTOM2.xy", hue)

    def test_the_kit_step_writes_the_seventh_layer(self):
        src = (BL / "alien_m12.py").read_text(encoding="utf-8")
        self.assertIn("LP.CONTACT_UV_MOUTH2", src)
        self.assertIn("len(me.uv_layers) != 6", src)  # TEXCOORD_6 only after the six of alien_m6
        self.assertIn("LP.CONTACT_MARKER_MOUTH2", src)


class MouthsTest(unittest.TestCase):
    def test_the_pout_palette_and_scales(self):
        src = (BL / "alien_mouths.py").read_text(encoding="utf-8")
        self.assertIn('PALETTE = {"pout": {"tongue_bg": -0.008}}', src)
        self.assertIn('PALETTE_SHAPE = {"pout": {"A": {"lip_min_r": 0.50}, "E": {"lip_min_r": 0.50}}}', src)
        self.assertIn('CUP_IN = {"pout": 0.6}', src)  # frog and overbite: 0, their cups unchanged
        m = re.search(r'SHAPE_SCALE_DESIGN = \{"pout": \{([^}]*)\}\}', src)
        self.assertIsNotNone(m)
        self.assertEqual(set(re.findall(r'"(\w)":', m.group(1))), {"A", "E", "O"})
        self.assertIn('"pout": {"O": 0.008, "*": 0.003}', src)  # the pout stands out of the skin
        self.assertIn('LP.scale_size(world, lips_p.get("size", 1.0), origin.translation.z)', src)


class GodotLookTest(unittest.TestCase):
    def test_pout_look_and_motion_are_uniforms(self):
        gd = (GA / "alien.gd").read_text(encoding="utf-8")
        lip = uniforms(GA / "alien_lip.gdshader")
        self.assertFalse(gd_dict_keys(gd, "LIP_LOOK_POUT") - lip)
        self.assertTrue({"lip_drop", "pucker"} <= lip)
        shader = (GA / "alien_lip.gdshader").read_text(encoding="utf-8")
        self.assertIn("instance uniform float lip_drop = 0.0;", shader)  # off for every other part
        self.assertIn("instance uniform float pucker = 0.0;", shader)
        self.assertIn('const MOUTH_DESIGNS: Array[String] = ["frog", "overbite", "pout"]', gd)


class TalkDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = (GA / "alien_talk.gd").read_text(encoding="utf-8")
        block = re.search(r"const LINE := \[(.*?)\n\]", cls.src, re.S).group(1)
        cls.words = [(int(t), [(s, int(ms)) for s, ms in re.findall(r'\["(\w+)", (\d+)\]', ph)])
                     for t, ph in re.findall(r"\[(\d+), \[(.*?)\]\],", block)]
        cls.line_ms = float(re.search(r"const LINE_MS := ([\d.]+)", cls.src).group(1))

    def test_styles(self):
        self.assertEqual(gd_dict_keys(self.src, "OPEN") , VISEMES)
        for d in ("frog", "overbite", "pout"):
            self.assertIn(f'"{d}": {{"lag_ms"', self.src)

    def test_a_voice_like_rhythm(self):
        self.assertGreaterEqual(len(self.words), 10)
        end = 0
        for t, phases in self.words:
            self.assertGreaterEqual(t - end, 50, f"word at {t} ms starts too soon")
            self.assertLessEqual(t - end, 800)
            for s, ms in phases:
                self.assertIn(s, VISEMES)
                self.assertTrue(40 <= ms <= 300, (t, s, ms))
            end = t + sum(ms for _s, ms in phases)
        self.assertLess(end, self.line_ms)
        gaps = [b[0] - (a[0] + sum(ms for _s, ms in a[1])) for a, b in zip(self.words, self.words[1:])]
        self.assertGreaterEqual(sum(g >= 350 for g in gaps), 2)  # sentence pauses, not one even beat


if __name__ == "__main__":
    unittest.main()
