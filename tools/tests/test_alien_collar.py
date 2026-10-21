"""M10b (art #196, brief UPDATE 14): the static socket collar's plain geometry (alien_lids_geom.collar_gaps,
collar_smooth, collar_section) and its wiring in alien_m6.py (read by pattern: the script needs Blender); M10c (brief
UPDATE 16): the skin collar (fillet_section, the deep crater, the skin's material and layers)."""
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
        # M10c: the default is the skin collar; M10b's coral ring stays behind --collar on
        self.assertRegex(self.src, r'"--collar", choices=\("off", "on", "skin"\), default="skin"')
        self.assertIn('p.add_argument("--flare", default="off"', self.src)
        main = self.src[self.src.index("def main("):]
        check = main.index('if a.collar != "off" and a.flare != "off":')
        self.assertLess(check, main.index("open_mainfile"))
        self.assertIn('if a.collar != "off" and k < LG.EYE_SCALE:', main)  # the full-size unit: no collar
        self.assertIn('build_collars(k, lids) if a.collar == "on" else build_skin_collars(k, lids, opts)', main)

    def test_its_ao_and_the_skins_contact_take_it(self):
        body = self.src[self.src.index("def bake_parts_ao"):self.src.index("def smooth(")]
        self.assertIn("collars()", body)
        field = self.src[self.src.index("def contact_field"):self.src.index("def main(")]
        self.assertIn("collars()", field)

    def test_the_skin_collar_is_skin(self):
        # M10c: no `_lid_` in its name (alien.gd would give it the lids' coral), the Body's material and layers
        name = re.search(r'SKIN_COLLAR_NAME = "([^"]+)"', self.src).group(1)
        self.assertNotIn("_lid_", name)
        self.assertTrue(name.startswith("eye_{d}_"))  # m10_shots' gate hides it with the parts
        build = self.src[self.src.index("def build_skin_collars"):self.src.index("def skin_collar_layers")]
        self.assertIn('bpy.data.materials["alien_hue"]', build)
        self.assertIn("sphere=False", build)  # M8b's whole crater, however deep
        layers = self.src[self.src.index("def skin_collar_layers"):self.src.index("def mouth_pieces")]
        self.assertIn("normals_split_custom_set_from_vertices", layers)
        self.assertEqual(re.search(r"SKIN_LAYERS = (\([^)]*\))", self.src).group(1),
                         '("UVMap", "masks", "rest_xy", "rest_zn")')
        field = self.src[self.src.index("def contact_field"):self.src.index("def main(")]
        self.assertIn("skin_collars()", field)

    def test_alien_gd_gives_a_hue_surface_the_skin(self):
        gd = (ROOT / "godot" / "alien" / "alien.gd").read_text(encoding="utf-8")
        self.assertIn('const HUE_MATERIALS := ["alien_hue", "alien_hue_part"]', gd)
        self.assertIn('if m.name.contains("_lid_"):', gd)  # why the skin collar's name has no `_lid_`


S = LG.COLLAR_SKIN


class SkinGaps(unittest.TestCase):
    def test_deep_skin_under_the_old_dome_counts_without_the_sphere(self):
        pts = [(RD + 0.005, -0.022, phi(4)), (RD + 0.012, -0.020, phi(4))]  # 22 mm behind, out past M8b's dome
        coral = LG.collar_gaps(pts, RD, RD_REF)
        self.assertIsNone(coral[4])
        skin = LG.collar_gaps(pts, RD, RD_REF, dict(C, sphere=False, h_back=S["h_back"]))
        self.assertAlmostEqual(skin[4][0], 0.005, places=9)  # the second is past rd_ref + margin
        self.assertAlmostEqual(skin[4][1], -0.022, places=9)
        too_deep = LG.collar_gaps([(RD + 0.005, -S["h_back"] * RD - 0.001, phi(4))], RD, RD_REF,
                                  dict(C, sphere=False, h_back=S["h_back"]))
        self.assertIsNone(too_deep[4])


class Fillet(unittest.TestCase):
    def check(self, gap, h, n):
        front, normals, back = LG.fillet_section(gap, h, n, RD)
        self.assertEqual(len(front), S["front"] + 1)
        self.assertEqual(len(normals), len(front))
        self.assertEqual(len(back), 2)
        ln = math.hypot(*n)
        nu = (n[0] / ln, n[1] / ln)
        # leaves under the skin, past the edge and tangent to it: the first normal is the skin's
        p0 = front[0]
        self.assertLess((p0[0] - RD - gap) * nu[0] + (p0[1] - h) * nu[1], 0.0)
        self.assertAlmostEqual(normals[0][0] * nu[0] + normals[0][1] * nu[1], 1.0, places=6)
        # ends inside the dome (hidden by it)
        self.assertLess(math.hypot(*front[-1]), RD)
        self.assertAlmostEqual(front[-1][0], RD - S["tuck_in_mm"] / 1000.0, places=9)
        for (a, b) in normals:
            self.assertAlmostEqual(math.hypot(a, b), 1.0, places=6)
        return front

    def test_the_section_from_the_skin_into_the_dome(self):
        for gap, h, n in ((0.009, -0.002, (0.0, 1.0)), (0.005, 0.0, (0.0, 1.0)), (0.009, 0.002, (0.5, 0.8)), (0.006, -0.022, (-0.3, 0.95)),
                          (0.004, -0.010, (0.9, 0.3))):
            self.check(gap, h, n)

    def test_no_crater_stays_at_the_outline(self):
        # no crater: every point drawn into P3, inside the dome; a narrow one part of the way
        front, _, back = LG.fillet_section(0.0, 0.0, (0.0, 1.0), RD)
        self.assertLess(max(math.hypot(*p) for p in front + back), RD)
        wide = LG.fillet_section(S["shrink_mm"] / 1000.0, -0.002, (0.0, 1.0), RD)[0]
        half = LG.fillet_section(S["shrink_mm"] / 2000.0, -0.002, (0.0, 1.0), RD)[0]
        p3 = wide[-1]
        self.assertAlmostEqual(half[-1][0], p3[0], places=9)
        self.assertLess(math.dist(half[0], p3), math.dist(wide[0], p3))


if __name__ == "__main__":
    unittest.main()
