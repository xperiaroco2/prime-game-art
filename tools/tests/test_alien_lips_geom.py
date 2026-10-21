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


class RestStationsTest(unittest.TestCase):  # M16 (UPDATE 29): the pout's rest mirrored, its lip line smooth
    def _stations(self):
        st = []
        for i, s in enumerate(SS):
            seam = 272 + 5 * s * s + (-4.0 if 0.1 < s < 0.25 else 0.0)  # the sheet's kink right of the centre
            st.append({"x": 229.5 + i * 2.2, "top_u": seam - 18 + 0.6 * s, "bot_u": seam - 0.5, "top_l": seam + 0.5,
                       "bot_l": seam + 24 - 0.4 * s, "open": False})
        return st

    def test_mirrored_about_the_face_centre(self):
        st = LP.mirror_stations(self._stations(), 274.0)
        n = len(st)
        for i in range(n):
            self.assertAlmostEqual(st[i]["x"] - 274.0, 274.0 - st[n - 1 - i]["x"])
            for k in ("top_u", "bot_u", "top_l", "bot_l"):
                self.assertAlmostEqual(st[i][k], st[n - 1 - i][k])
        self.assertAlmostEqual(st[-1]["x"] - st[0]["x"], 88.0)  # the measured span kept

    def test_even_fit(self):
        vals = [3.0 + 2.0 * s * s - 0.5 * s ** 4 for s in SS]
        for a, b in zip(LP.even_fit(SS, vals, 3), vals):
            self.assertAlmostEqual(a, b, places=9)
        f = LP.even_fit(SS, [s for s in SS], 3)  # an odd curve has no even part
        self.assertLess(max(abs(v) for v in f), 1e-9)

    def test_rest_stations_smooth_and_closed(self):
        p = LP.merged_pout(None)
        st = LP.rest_stations(self._stations(), 274.0, p)
        seam = [(r["bot_u"] + r["top_l"]) / 2 for r in st]
        n = len(st)
        for i in range(n):
            self.assertAlmostEqual(seam[i], seam[n - 1 - i])
            self.assertAlmostEqual(st[i]["top_l"] - st[i]["bot_u"], 1.0)  # the lips still meet
        second = [seam[i - 1] - 2 * seam[i] + seam[i + 1] for i in range(1, n - 1)]
        self.assertLess(max(abs(v) for v in second), 0.05)  # no kink left
        self.assertGreater(seam[0], seam[n // 2])  # the corners lower than the centre, as the sheet's

    def test_open_stations_keep_their_gap(self):  # M16b (PR #252 minor 2): small's parting is not smoothed away
        st = self._stations()
        n = len(st)
        gaps = {}
        for i in range(n // 2 - 3, n // 2 + 4):  # an open middle, its gap widest at the centre (px)
            g = 6.0 - abs(i - n // 2)
            st[i]["bot_u"], st[i]["top_l"], st[i]["open"] = st[i]["bot_u"] - g / 2, st[i]["top_l"] + g / 2, True
            gaps[i] = st[i]["top_l"] - st[i]["bot_u"]
        out = LP.rest_stations(st, 274.0, LP.merged_pout(None))
        seam = [(r["bot_u"] + r["top_l"]) / 2 for r in out]
        for i in range(n):
            self.assertAlmostEqual(seam[i], seam[n - 1 - i])  # the lip line still mirrored and even
            # the open run is centred, so the mirror keeps each measured gap; a closed station's lips meet
            self.assertEqual(out[i]["open"], i in gaps)
            self.assertAlmostEqual(out[i]["top_l"] - out[i]["bot_u"], gaps.get(i, 1.0))
        self.assertAlmostEqual(out[n // 2]["top_l"] - out[n // 2]["bot_u"], 7.0)  # not smoothed to the fit

    def test_without_the_keys_nothing_changes(self):
        st = self._stations()
        self.assertEqual(LP.rest_stations(st, 274.0, LP.LIP_SHAPE), st)
        for p in (LP.LIP_SHAPE_FANGS, LP.LIP_SHAPE_TONGUE):
            self.assertNotIn("mirror", p)
            self.assertNotIn("seam_fit", p)

    def test_the_open_rings_keep_m12b(self):
        for s, rp in LP.LIP_SHAPE_POUT["ring_param"].items():
            self.assertEqual((rp["upper"], rp["lower"], rp["lean"]), (0.95, 1.10, 0.25), s)

    def test_mouths_mirror_the_closed_pieces(self):
        src = MOUTHS.read_text(encoding="utf-8")
        self.assertIn("LP.rest_stations(st, m[\"hc\"], lips_p)", src)
        self.assertIn("cs, ra, rb, ns = mirrored(cs, ra, rb, ns)", src)
        self.assertIn('(rp or {}).get("lean", lips_p["lean"])', src)


if __name__ == "__main__":
    unittest.main()
