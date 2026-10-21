"""M12 (art #196): the red pout mouth mp1, the third mouth design. Plain Python: alien_lips_geom's size transform, the
pout's lip shape and contact layout, and their copies in alien_m12.py, alien_mouths.py, alien.gd, the shaders and
alien_talk.gd (read by pattern; no Blender, no Godot)."""
from __future__ import annotations

import importlib.util
import math
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
        # M16d (UPDATE 39): mp1's measured rest, even lips (the lower renders a little taller from the same factor),
        # never M16's swollen lower cushion (lower 1.20 over plump 1.15), shallower tubes, the lower the shallower
        self.assertLessEqual(p["lower"], p["upper"])
        self.assertLessEqual(p["plump"], 1.0)
        self.assertLessEqual(p["lower"] * p["plump"], 1.0)
        self.assertLess(p["depth"], 1.0)
        self.assertLess(p["depth_l"], 1.0)
        self.assertEqual(p["closed"], ("rest",))
        self.assertGreater(p["upper"], LP.LIP_SHAPE["upper"])  # mp1's upper lip fuller than the frog's
        # M16b (UPDATE 30): mp1's ends tucked to points, finer than the frog's, and its clear double-peaked bow;
        # M16d: the points from a longer taper (pw 1.3 over 0.32) with a softer tuck
        self.assertLess(p["corner"], LP.LIP_SHAPE["corner"])
        self.assertLess(p["pw"], 1.5)
        self.assertGreaterEqual(p["corner_share"], 0.30)
        self.assertGreaterEqual(p["bow"], 0.30)
        self.assertGreater(p["bow_peak"], 0.30)
        # M16c (UPDATE 36): mp1's long fine points, the upper lip's end over the lower's, small's dark parting
        self.assertLess(p["min_b"], 0.0011)
        self.assertLessEqual(p["corner"], 0.06)
        self.assertGreater(p["corner_over"], 0.0)
        self.assertGreater(p["corner_share"], 0.18)
        self.assertGreater(p["parting_dark"], 0.0)
        src = (Path(__file__).resolve().parents[1] / "blender" / "alien_mouths.py").read_text(encoding="utf-8")
        for key in ('lips_p.get("min_b", MIN_B)', 'lips_p.get("corner_over", 0.0)', 'lips_p.get("parting_dark")'):
            self.assertIn(key, src)  # the closed tubes read them
        for s, rp in p["ring_param"].items():  # the open rings keep M12b's bow shape
            self.assertEqual((rp["bow_w"], rp["bow_peak"], rp["bow_at"]), (0.16, 0.10, 0.24), s)
        # M13 (PR #246's review minor 3): no dead settings: every open shape is a designed ring (ring_param), so the
        # traced rings' weights (`ring`) and their corner (`ring_corner`) are not part of the pout's shape
        self.assertEqual(set(p), set(LP.LIP_SHAPE) - {"ring"} | {"size", "bow_flat", "ring_param", "mirror", "seam_fit",
                                                                         "corner_tuck", "corner_share", "corner_join",
                                                                         "min_b", "corner_over", "parting_dark", "parting",
                                                                         "depth", "depth_l", "closed"})
        self.assertEqual(set(p["ring_param"]), {"A", "E", "O"})

    def test_merged_pout(self):
        p = LP.merged_pout({"size": 0.9, "ring_param": {"O": {"hole": 0.2}}})
        self.assertEqual(p["size"], 0.9)
        self.assertEqual(p["ring_param"]["O"]["hole"], 0.2)
        self.assertEqual(LP.LIP_SHAPE_POUT["ring_param"]["O"]["hole"], 0.30)  # the default is not changed
        self.assertEqual(LP.merged_pout(None), LP.LIP_SHAPE_POUT)


class RingParamTest(unittest.TestCase):
    """M12b: the open shapes as designed rings (UPDATE 19 items 1-3, 5)."""
    MEAS = {"A": {"cx": 274.0, "cy": 285.0, "W": 42.5, "hu": 19.5, "t_u": 22.0, "t_l": 24.0},
            "E": {"cx": 241.5, "cy": 278.5, "W": 56.0, "hu": 14.0, "t_u": 20.0, "t_l": 22.0},
            "O": {"cx": 209.0, "cy": 277.5, "W": 39.5, "hu": 7.0, "t_u": 27.0, "t_l": 31.0}}  # mp1's panels

    def ring(self, shape):
        p = LP.merged_pout()
        return LP.ring_param(self.MEAS[shape], p["ring_param"][shape], p, 96)

    def test_every_open_shape_is_designed(self):
        self.assertEqual(set(LP.LIP_SHAPE_POUT["ring_param"]), {"A", "E", "O"})
        self.assertEqual(LP.LIP_SHAPE.get("ring_param"), None)  # the frog and overbite trace their sheets as before

    def test_no_spikes_and_no_folds(self):
        for shape in ("A", "E", "O"):
            _c, pairs, outer0, _cw = self.ring(shape)
            for edge, pts in enumerate(([q[0] for q in pairs], outer0, [q[1] for q in pairs])):
                turns = []
                for k in range(96):
                    (ax, ay), (bx, by), (cx, cy) = pts[k - 1], pts[k], pts[(k + 1) % 96]
                    a1, a2 = math.atan2(by - ay, bx - ax), math.atan2(cy - by, cx - bx)
                    turns.append((a2 - a1 + math.pi) % (2 * math.pi) - math.pi)
                self.assertAlmostEqual(abs(sum(turns)), 2 * math.pi, places=3)  # one simple loop
                if edge < 2:  # the opening and the outline without the bow are convex: never fold
                    self.assertTrue(all(t * turns[0] >= -1e-9 for t in turns), (shape, edge))
                else:  # the outline with the bow: its sharpest turn is soft (E's traced corners turned ~90 deg)
                    self.assertLess(max(abs(t) for t in turns), math.radians(20), shape)

    def test_an_even_roll_with_round_corners(self):
        for shape, lo in (("A", 0.6), ("E", 0.55), ("O", 0.75)):
            _c, pairs, outer0, _cw = self.ring(shape)
            t = [math.hypot(o[0] - i[0], o[1] - i[1]) for (i, _o), o in zip(pairs, outer0)]
            self.assertGreater(min(t) / max(t), lo, shape)  # never a thin flap
            for k in range(96):  # no ripple: the thickness changes smoothly round the ring
                self.assertLess(abs(t[k] - t[k - 1]), 0.08 * max(t), shape)

    def test_o_is_a_small_round_hole(self):
        (cx, cy), pairs, _o0, _cw = self.ring("O")
        r = [math.hypot(i[0] - cx, i[1] - cy) for i, _o in pairs]
        self.assertLess(max(r) / min(r), 1.01)
        self.assertAlmostEqual(min(r), 0.30 * self.MEAS["O"]["W"], places=3)
        outer = [q[1] for q in pairs]
        w = max(x for x, _y in outer) - min(x for x, _y in outer)
        self.assertLess(w, 2 * self.MEAS["O"]["W"] * 1.08)  # the kiss keeps about the sheet's size (plump 1.15)

    def test_flat_bow(self):
        p = LP.merged_pout()
        self.assertEqual(LP.flat_bow(p)["bow"], 0.0)
        self.assertGreater(p["bow"], 0.0)  # the outline keeps a bow
        self.assertIs(LP.flat_bow(LP.LIP_SHAPE), LP.LIP_SHAPE)  # frog: unchanged
        q = LP.merged_pout({"ring_param": {"O": {"hole": 0.3}}})
        self.assertEqual(q["ring_param"]["O"]["hole"], 0.3)
        self.assertEqual(q["ring_param"]["O"]["corner"], 1.0)  # merged key by key
        self.assertEqual(LP.LIP_SHAPE_POUT["ring_param"]["O"]["hole"], 0.30)


class LayoutTest(unittest.TestCase):
    def test_the_contact_layer_and_its_channel(self):
        self.assertEqual(LP.CONTACT_UV_MOUTH2, ("contact_mouth2", ("pout", "fangs")))
        gd = (GA / "alien.gd").read_text(encoding="utf-8")
        m = re.search(r'const CONTACT_CHANNEL2 := \{([^}]*)\}', gd)
        self.assertIsNotNone(m)
        self.assertEqual({k: int(v) for k, v in re.findall(r'"(\w+)": (\d+)', m.group(1))}, {"pout": 0, "fangs": 1})
        self.assertIn('set_shader_parameter("contact_pick2"', gd)
        hue = (GA / "alien_hue.gdshader").read_text(encoding="utf-8")
        self.assertIn("uniform vec2 contact_pick2 = vec2(0.0);", hue)  # off by default: older kits unchanged
        self.assertIn("CUSTOM2.xy", hue)
        # M14 (PR #251's review minor 7): the tongue's channel, TEXCOORD_7 = CUSTOM2.zw, picked by contact_pick3
        self.assertEqual(LP.CONTACT_UV_MOUTH3, ("contact_mouth3", ("tongue", "")))
        m3 = re.search(r'const CONTACT_CHANNEL3 := \{([^}]*)\}', gd)
        self.assertIsNotNone(m3)
        self.assertEqual({k: int(v) for k, v in re.findall(r'"(\w+)": (\d+)', m3.group(1))}, {"tongue": 0})
        self.assertIn('set_shader_parameter("contact_pick3"', gd)
        self.assertIn("uniform vec2 contact_pick3 = vec2(0.0);", hue)
        self.assertIn("clamp(CUSTOM2.zw, 0.0, 1.0) * contact_pick3", hue)
        self.assertEqual(LP.CONTACT_MARKER_MOUTH3, {"prime_contact_mouth3": "custom2_zw"})

    def test_the_kit_step_writes_the_seventh_layer(self):
        src = (BL / "alien_m12.py").read_text(encoding="utf-8")
        self.assertIn("LP.CONTACT_UV_MOUTH2", src)
        self.assertIn("len(me.uv_layers) != 6", src)  # TEXCOORD_6 only after the six of alien_m6
        self.assertIn("LP.CONTACT_MARKER_MOUTH2", src)
        # PR #246's review minor 7: the AO marker only on a baked kit
        bake = src.index("if not a.no_bake:")
        self.assertGreater(src.index("M6.PART_AO_MARKER.items()"), bake)
        self.assertEqual(src.count("M6.PART_AO_MARKER"), 1)


class MouthsTest(unittest.TestCase):
    def test_the_pout_palette_and_scales(self):
        src = (BL / "alien_mouths.py").read_text(encoding="utf-8")
        self.assertIn('PALETTE = {"pout": {"tongue_bg": -0.008}}', src)
        self.assertIn('PALETTE_SHAPE = {"pout": {"A": {"lip_min_r": 0.50}, "E": {"lip_min_r": 0.50}}}', src)
        self.assertIn('CUP_IN = {"pout": 0.6, "fangs": 0.6, "tongue": 0.6}', src)  # frog and overbite: 0, their cups unchanged
        self.assertNotIn("CORNER_CLOSE", src)  # PR #246's review minor 3: no dead pout settings
        m = re.search(r'SHAPE_SCALE_DESIGN = \{"pout": \{([^}]*)\}', src)
        self.assertIsNotNone(m)
        self.assertEqual(set(re.findall(r'"(\w)":', m.group(1))), {"A", "E", "O"})
        self.assertIn('"pout": {"O": 0.008, "*": 0.003}', src)  # the pout stands out of the skin
        self.assertIn('LP.scale_size(world, lips_p.get("size", 1.0), origin.translation.z)', src)


class GodotLookTest(unittest.TestCase):
    def test_pout_look_and_motion_are_uniforms(self):
        gd = (GA / "alien.gd").read_text(encoding="utf-8")
        motion = GA / "alien_mouth_motion.gdshaderinc"
        lip = uniforms(GA / "alien_lip.gdshader") | uniforms(motion)
        self.assertFalse(gd_dict_keys(gd, "LIP_LOOK_POUT") - lip)
        self.assertFalse(gd_dict_keys(gd, "FANG_LOOK") - lip)
        self.assertTrue({"lip_drop", "pucker", "jaw_thrust"} <= lip)
        inc = motion.read_text(encoding="utf-8")
        for u in ("lip_drop", "pucker", "jaw_thrust"):  # off for every other part
            self.assertIn(f"instance uniform float {u} = 0.0;", inc)
        for shader in ("alien_lip.gdshader", "alien_mouth_part.gdshader"):  # the lips, fangs, cup and tongue move
            text = (GA / shader).read_text(encoding="utf-8")
            self.assertIn('#include "res://alien/alien_mouth_motion.gdshaderinc"', text)
            self.assertIn("VERTEX = mouth_motion(tongue_motion(VERTEX, UV2.x), COLOR.a);", text)  # M13b: the jaw weight in the alpha; M14 the tongue flop
        self.assertIn('const MOUTH_DESIGNS: Array[String] = ["frog", "overbite", "pout", "fangs", "tongue"]', gd)
        self.assertIn('const MOVING_PARTS: Array[String] = ["alien_mouth_inner", "alien_tongue"]', gd)

    def test_listen_ends_a_line(self):  # PR #246's review minor 6
        gd = (GA / "alien.gd").read_text(encoding="utf-8")
        body = gd[gd.index("func listen("):gd.index("func stop_listening(")]
        self.assertIn("_line = []", body)


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
        for d in ("frog", "overbite", "pout", "fangs"):
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
