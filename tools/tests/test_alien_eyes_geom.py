"""The M4 eyes' pure parts (art #196): tools/blender/alien_eyes_geom.py (the wet line's profile, the cornea's
optics) and its agreement with godot/alien/alien_eye.gdshader's defaults."""
from __future__ import annotations

import math
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
import alien_eyes_geom as E  # noqa: E402

# alien_parts.EYES' lid radii and LID_BEAD (bored and manic), as (rho_in, rho_out, bead, upper)
LIDS = [(1.06, 1.13, 0.10, True), (1.012, 1.05, 0.035, False), (1.05, 1.095, 0.10, True), (1.012, 1.042, 0.035, False)]


class WetLineTest(unittest.TestCase):
    def test_the_strip_stays_between_the_ball_and_the_lid(self):
        for rho_in, rho_out, bead, upper in LIDS:
            rm, hw = E.rim(rho_in, rho_out, bead)
            for rho, p in E.wet_profile(rho_in, rho_out, bead, upper):
                self.assertGreater(rho, 1.0, "never inside the ball")
                self.assertLessEqual(rho, rm, "never past the rim's middle (the strip lies beyond the lid's edge)")
                if p == 0.0:
                    self.assertLess(rho, rho_in, "at the edge, under the lid's inner surface")
                under = E.rim_lower_surface(abs(p), rm, hw)
                if under is not None:
                    self.assertLess(rho, under, "under the rim, below its surface")

    def test_it_runs_from_beyond_the_rim_to_the_lid_edge(self):
        for rho_in, rho_out, bead, upper in LIDS:
            prof = E.wet_profile(rho_in, rho_out, bead, upper)
            rm, hw = E.rim(rho_in, rho_out, bead)
            reach = hw / rm
            self.assertAlmostEqual(abs(prof[0][1]), reach + math.radians(E.WET["beyond_deg"]))
            self.assertEqual(prof[-1][1], 0.0)
            sgn = 1.0 if upper else -1.0
            self.assertTrue(all(sgn * p <= 0.0 for _, p in prof), "on the open eye's side of the edge")

    def test_lid_point_matches_lid_shell(self):
        # lid_shell: d = (sin t, -cos t cos p, cos t sin p) times rho
        x, y, z = E.lid_point(1.1, 0.3, -0.2)
        self.assertAlmostEqual(math.hypot(x, y, z), 1.1)
        self.assertAlmostEqual(y, -1.1 * math.cos(-0.2) * math.cos(0.3))


class CorneaTest(unittest.TestCase):
    def test_the_sphere_meets_the_limbus_and_the_apex(self):
        for lim, bulge in ((27.0, 0.12), (21.0, 0.12), (30.0, 0.05)):
            zc, rc = E.cornea_sphere(lim, bulge)
            self.assertAlmostEqual(zc + rc, 1.0 + bulge)
            a = math.radians(lim)
            self.assertAlmostEqual(math.hypot(math.sin(a), math.cos(a) - zc), rc)

    def test_the_cornea_magnifies_and_keeps_the_order(self):
        c = dict(E.CORNEA)
        xs = [math.sin(math.radians(d)) for d in (2.0, 6.0, 11.5, 20.0, 25.0)]
        rhos = [E.front_rho(x, c) for x in xs]
        self.assertEqual(rhos, sorted(rhos), "monotone: the pupil stays inside the iris")
        for x, r in zip(xs, rhos):
            self.assertLess(r, x, "a convex cornea magnifies: the plane radius is smaller than it looks")
            self.assertGreater(r, 0.5 * x)

    def test_refract_bends_toward_the_normal(self):
        n = (math.sin(0.3), 0.0, math.cos(0.3))
        r = E.refract((0.0, 0.0, -1.0), n, 1.0 / 1.336)
        self.assertAlmostEqual(math.hypot(*r), 1.0)
        self.assertGreater(r[0], -0.3 / 1.336 * 2)
        self.assertLess(r[0], 0.0, "bent toward the axis' side of the normal")


class ShaderDefaultsTest(unittest.TestCase):
    def test_the_shader_defaults_match_the_module(self):
        text = (ROOT / "godot" / "alien" / "alien_eye.gdshader").read_text(encoding="utf-8")

        def uniform(name: str) -> float:
            m = re.search(rf"uniform float {name}\b[^=]*=\s*([0-9.]+);", text)
            self.assertIsNotNone(m, name)
            return float(m.group(1))

        for k in ("limbus_deg", "bulge", "iris_depth", "ior"):
            self.assertAlmostEqual(uniform(k), E.CORNEA[k], msg=k)


if __name__ == "__main__":
    unittest.main()
