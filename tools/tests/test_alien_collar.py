"""M10b (art #196, brief UPDATE 14): the static socket collar's plain geometry (alien_lids_geom.collar_gaps,
collar_smooth, collar_section) and its wiring in alien_m6.py (read by pattern: the script needs Blender)."""
from __future__ import annotations

import importlib.util
import math
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLENDER = ROOT / "tools" / "blender"
spec = importlib.util.spec_from_file_location("alien_lids_geom", BLENDER / "alien_lids_geom.py")
LG = importlib.util.module_from_spec(spec)
spec.loader.exec_module(LG)
C = LG.COLLAR
RD, RD_REF = 0.036, 0.045


def phi(i: int) -> float:
    """The centre of azimuth bin i."""
    return -math.pi + 2.0 * math.pi * (i + 0.5) / C["bins"]


class Gaps(unittest.TestCase):
    def test_the_bare_crater_out_to_the_old_dome(self):
        pts = [(RD + 0.0005 * k, 0.0, phi(0)) for k in range(1, 30)]  # out to 14.5 mm: past M8b's dome
        g = LG.collar_gaps(pts, RD, RD_REF)
        lim = RD_REF + C["margin_mm"] / 1000.0
        self.assertAlmostEqual(g[0][0], max(s for s, _, _ in pts if s <= lim) - RD, places=6)
        self.assertTrue(all(x is None for x in g[1:]))

    def test_skin_far_behind_or_inside_the_new_outline_is_no_crater(self):
        pts = [(RD + 0.004, -C["h_back"] * RD - 0.001, phi(3)), (RD - 0.001, 0.0, phi(5))]
        g = LG.collar_gaps(pts, RD, RD_REF)
        self.assertIsNone(g[3])
        self.assertIsNone(g[5])


class Smooth(unittest.TestCase):
    def test_no_crater_keeps_an_even_rim(self):
        g = LG.collar_smooth([None] * C["bins"])
        self.assertTrue(all(abs(w - C["min_mm"] / 1000.0) < 1e-12 and h == 0.0 for w, h in g))

    def test_a_wide_bin_keeps_its_width_and_none_falls_below_the_rim(self):
        raw = [None] * C["bins"]
        raw[10] = (0.009, -0.002)
        g = LG.collar_smooth(raw)
        self.assertGreater(g[10][0], 0.009 * (2 * C["grow"] + 1) / (2 * C["smooth"] + 1) - 1e-9)
        self.assertGreaterEqual(min(w for w, _ in g), C["min_mm"] / 1000.0 - 1e-12)
        far = (10 + C["bins"] // 2) % C["bins"]
        self.assertEqual(g[far], (C["min_mm"] / 1000.0, 0.0))


class Section(unittest.TestCase):
    def test_from_inside_the_outline_to_past_the_crater_edge(self):
        for gap, h in ((0.003, 0.0), (0.009, -0.004), (0.006, 0.002)):
            (cs, ch), u, n, a, b = LG.collar_section(gap, h, RD)
            back = (cs + C["back"] * b * n[0], ch + C["back"] * b * n[1])
            inner = (back[0] - a * u[0], back[1] - a * u[1])
            outer = (back[0] + a * u[0], back[1] + a * u[1])
            self.assertAlmostEqual(inner[0], RD - C["tuck_in_mm"] / 1000.0, places=9)
            self.assertAlmostEqual(inner[1], 0.0, places=9)
            past = math.hypot(outer[0] - (RD + gap), outer[1] - h)
            self.assertAlmostEqual(past, C["tuck_mm"] / 1000.0, places=9)
            self.assertLessEqual(b, C["depth_max_mm"] / 1000.0 + 1e-12)
            self.assertGreater(n[1], 0.0)  # its depth toward the front


class Wiring(unittest.TestCase):
    src = (BLENDER / "alien_m6.py").read_text(encoding="utf-8")

    def test_named_as_a_lid_part_of_its_design(self):
        name = re.search(r'COLLAR_NAME = "([^"]+)"', self.src).group(1)
        self.assertIn("_lid_", name)  # alien.gd: the lids' material (LID_LOOK)
        self.assertTrue(name.startswith("eye_{d}_"))

    def test_the_defaults_build_the_pick_and_refuse_the_flare_first(self):
        # PR #245's review: the defaults are the pick's (--flare off --collar on), and the refusal of the collar with
        # a flare comes before any work (the blend file is opened after it)
        self.assertRegex(self.src, r'"--collar", choices=\("off", "on"\), default="on"')
        self.assertIn('p.add_argument("--flare", default="off"', self.src)
        main = self.src[self.src.index("def main("):]
        check = main.index('if a.collar == "on" and a.flare != "off":')
        self.assertLess(check, main.index("open_mainfile"))
        self.assertIn('if a.collar == "on" and k < LG.EYE_SCALE:', main)  # the full-size unit: no collar

    def test_its_ao_and_the_skins_contact_take_it(self):
        body = self.src[self.src.index("def bake_parts_ao"):self.src.index("def smooth(")]
        self.assertIn("collars()", body)
        field = self.src[self.src.index("def contact_field"):self.src.index("def main(")]
        self.assertIn("collars()", field)


if __name__ == "__main__":
    unittest.main()
