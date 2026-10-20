"""M8 (art #196): tools/blender/alien_lips_geom.py, the lips' profile along each lip (thin corners, full centre, the
upper lip's bow, the lower lip's cushion), the section's swell toward the lip line, and alien_mouths.py's use of it
(the old lips unchanged at w = 0). Plain Python: the modules are read without Blender, alien_mouths.py by pattern."""
from __future__ import annotations

import importlib.util
import math
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MOUTHS = ROOT / "tools" / "blender" / "alien_mouths.py"
M8 = ROOT / "tools" / "blender" / "alien_m8.py"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / "blender" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


LP = load("alien_lips_geom")
SS = [-1 + 2 * i / 40 for i in range(41)]


class TaperTest(unittest.TestCase):
    def test_full_in_the_middle_fine_at_the_corners(self):
        p = LP.LIP_SHAPE
        self.assertAlmostEqual(LP.taper(0.0, p), 1.0)
        self.assertAlmostEqual(LP.taper(1.0, p), p["corner"])
        self.assertAlmostEqual(LP.taper(-1.0, p), p["corner"])
        vals = [LP.taper(s, p) for s in SS[20:]]
        self.assertTrue(all(a >= b for a, b in zip(vals, vals[1:])), "the lip thins steadily toward its corner")
        self.assertLess(p["corner"], 0.3, "a fine point at the corners, not a cap")

    def test_the_bow_dips_at_the_centre_only(self):
        p = LP.LIP_SHAPE
        self.assertLess(LP.bow(0.0, p), -0.8 * p["bow"])
        self.assertGreater(LP.bow(p["bow_at"], p), 0.0)
        self.assertAlmostEqual(LP.bow(0.8, p), 0.0, places=6)


class ClosedEdgesTest(unittest.TestCase):
    def setUp(self):
        # a uniform roll as the old lips: 4 mm thick end to end, upper lip 0..+4 mm over the line at 0
        self.top_u = [0.004] * 41
        self.bot_u = [0.0] * 41
        self.top_l = [0.0] * 41
        self.bot_l = [-0.004] * 41

    def test_w0_is_the_m6c_lips(self):
        p = LP.LIP_SHAPE_M6C
        self.assertEqual(LP.closed_edges(SS, self.top_u, self.bot_u, "u", p), (self.top_u, self.bot_u))
        self.assertEqual(LP.closed_edges(SS, self.top_l, self.bot_l, "l", p), (self.top_l, self.bot_l))
        self.assertEqual(LP.depth_scale(0.9, p), 1.0)
        self.assertEqual(LP.ring_width(0.3, 0.004, 0.004, 0.5, "A", p), 0.004)

    def test_the_lip_line_stays_and_the_outer_edge_moves(self):
        p = LP.LIP_SHAPE
        t, b = LP.closed_edges(SS, self.top_u, self.bot_u, "u", p)
        self.assertEqual(b, self.bot_u, "the upper lip's bottom (the lip line) is kept")
        t2, b2 = LP.closed_edges(SS, self.top_l, self.bot_l, "l", p)
        self.assertEqual(t2, self.top_l, "the lower lip's top (the lip line) is kept")
        hu = [x - y for x, y in zip(t, b)]
        hl = [x - y for x, y in zip(t2, b2)]
        self.assertLess(hu[0], 0.3 * max(hu), "the upper lip ends fine")
        self.assertLess(hl[-1], 0.3 * max(hl), "the lower lip ends fine")
        self.assertGreater(max(hl), max(hu), "the lower lip is the fuller")
        self.assertLess(hu[20], max(hu), "the bow: the upper lip is a little lower at its very centre")

    def test_corners_sink(self):
        p = LP.LIP_SHAPE
        self.assertAlmostEqual(LP.depth_scale(0.0, p), 1.0)
        self.assertAlmostEqual(LP.depth_scale(1.0, p), p["depth_corner"])

    def test_ring_corners_thin_and_o_less(self):
        p = LP.LIP_SHAPE
        corner_a = LP.ring_width(0.0, 0.004, 0.004, 0.5, "A", p)
        corner_o = LP.ring_width(0.0, 0.004, 0.004, 0.5, "O", p)
        self.assertLess(corner_a, 0.002)
        self.assertGreater(corner_o, corner_a, "the O's pucker stays round")
        low = LP.ring_width(math.pi / 2, 0.004, 0.004, 1.0, "A", p)
        up = LP.ring_width(-math.pi / 2, 0.004, 0.004, 0.0, "A", p)
        self.assertGreater(low, up, "the lower lip of an open mouth is the fuller")


class SectionTest(unittest.TestCase):
    def test_plain_ellipse_at_no_lean(self):
        for k in range(14):
            ph = 2 * math.pi * k / 14
            cn, sn = LP.section(ph, 0.0, 1.0, 1.0)
            self.assertAlmostEqual(cn, math.cos(ph))
            self.assertAlmostEqual(sn, math.sin(ph))

    def test_swell_toward_the_line(self):
        toward = LP.section(math.pi / 4, 0.3, 1.0, 1.0)[0]
        away = LP.section(-math.pi / 4, 0.3, 1.0, 1.0)[0]
        self.assertGreater(toward, away)


class MergeTest(unittest.TestCase):
    def test_merged_keeps_ring_keys(self):
        m = LP.merged({"corner": 0.3, "ring": {"O": 0.0}})
        self.assertEqual(m["corner"], 0.3)
        self.assertEqual(m["ring"]["A"], LP.LIP_SHAPE["ring"]["A"])
        self.assertEqual(m["ring"]["O"], 0.0)
        self.assertEqual(LP.LIP_SHAPE["ring"]["O"], 0.35, "merged() does not change the pick")


class WidthTest(unittest.TestCase):
    def test_scale_x_narrows_about_the_centre_and_keeps_heights(self):
        def world(x, y):
            return (x - 100.0) * 0.001, 1.5 - y * 0.001
        self.assertIs(LP.scale_x(world, 1.0), world, "width 1 is the measured mouth itself")
        w = LP.scale_x(world, 0.72)
        for x, y in ((40.0, 10.0), (100.0, 30.0), (170.0, 5.0)):
            self.assertAlmostEqual(w(x, y)[0], 0.72 * world(x, y)[0])
            self.assertEqual(w(x, y)[1], world(x, y)[1])

    def test_the_pick_is_narrower_and_m6c_keeps_its_width(self):
        self.assertLess(LP.LIP_SHAPE["width"], 1.0)
        self.assertGreater(LP.LIP_SHAPE["width"], 0.5)
        self.assertNotIn("width", LP.LIP_SHAPE_M6C, "the old lips keep the measured width")
        self.assertEqual(LP.merged({"width": 1.0})["width"], 1.0)

    def test_build_piece_scales_every_x(self):
        src = MOUTHS.read_text(encoding="utf-8")
        i = src.index("def build_piece(")
        body = src[i:src.index("\ndef ", i + 1)]
        j = body.index('world = LP.scale_x(world, lips_p.get("width", 1.0))')
        doc_end = body.index('"""', body.index('"""') + 3)
        self.assertLess(j, body.index("world(", doc_end), "the width applies before the first use of world")


class UseTest(unittest.TestCase):
    def test_mouths_use_the_profile_and_keep_names(self):
        src = MOUTHS.read_text(encoding="utf-8")
        self.assertIn("LP.closed_edges(", src)
        self.assertIn("LP.ring_width(", src)
        self.assertIn('name or f"mouth_{design}_{shape}"', src)
        self.assertRegex(src, r'if __name__ == "__main__":\n    main\(\)')

    def test_m8_keeps_the_nodes(self):
        src = M8.read_text(encoding="utf-8")
        self.assertIn("swap_mesh(ob, new)", src)
        self.assertIn('bpy.data.objects[f"mouth_{design}_{shape}"]', src)
        self.assertTrue(re.search(r"bake_parts_ao\(body, eyes=False", src), "the lids' AO is not rebaked")


if __name__ == "__main__":
    unittest.main()
