"""The alien 3D pilot, step 2a (art #196): tools/blender/alien_pilot_geom.py, the pure geometry the head build uses
(sphere fit, clusters, the lip line's valley, lid shells, the eye texture, the colour grade). Plain Python."""
from __future__ import annotations

import importlib.util
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("alien_pilot_geom", ROOT / "tools" / "blender" / "alien_pilot_geom.py")
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)


class PilotGeomTest(unittest.TestCase):
    def test_fit_sphere_recovers_a_cap(self):
        c, r = (0.3, -0.2, 0.5), 0.15
        pts = []
        for i in range(12):
            for j in range(1, 6):
                th, ph = math.radians(10 * j), 2 * math.pi * i / 12
                pts.append((c[0] + r * math.sin(th) * math.cos(ph), c[1] - r * math.cos(th),
                            c[2] + r * math.sin(th) * math.sin(ph)))
        centre, radius = G.fit_sphere(pts)
        for a, b in zip(centre, c):
            self.assertAlmostEqual(a, b, places=6)
        self.assertAlmostEqual(radius, r, places=6)

    def test_clusters_split_by_link(self):
        pts = [(0, 0, 0), (0.1, 0, 0), (0.2, 0, 0), (5, 0, 0), (5.1, 0, 0)]
        self.assertEqual([sorted(g) for g in G.clusters(pts, 0.15)], [[0, 1, 2], [3, 4]])

    def test_valley_finds_the_lip_line(self):
        # chin, lower lip, the groove, upper lip, nose base: the groove is the most prominent valley
        prof = [0.1, 0.5, 0.9, 0.95, 0.85, 0.97, 0.92, 0.6]
        self.assertEqual(G.valley(prof)[0], 4)
        self.assertEqual(G.valley([1, 2, 3, 4])[0], -1)

    def test_lid_shell_points_lie_on_the_sphere(self):
        axes = G.frame((0, -1, 0))
        rows = G.lid_grid(math.radians(8), math.radians(100), math.radians(90), 8, 4)
        self.assertEqual((len(rows), len(rows[0])), (5, 9))
        for a, b in rows[0]:
            p = G.shell_point((1, 2, 3), axes, 0.2, a, b)
            self.assertAlmostEqual(math.dist(p, (1, 2, 3)), 0.2, places=9)
        top = G.shell_point((0, 0, 0), axes, 1.0, 0.0, math.radians(90))
        self.assertAlmostEqual(top[2], 1.0, places=9)
        front = G.shell_point((0, 0, 0), axes, 1.0, 0.0, 0.0)
        self.assertAlmostEqual(front[1], -1.0, places=9)

    def test_eye_pixel_rings(self):
        spec = {"iris_deg": 27.0, "pupil_deg": 12.0, "sclera": (0.9, 0.9, 0.9), "iris": (0.4, 0.2, 0.1),
                "iris_rim": (0.2, 0.1, 0.0), "pupil": (0.0, 0.0, 0.0)}
        self.assertEqual(G.eye_pixel(5 / 180, 0.3, spec), (0.0, 0.0, 0.0))
        self.assertEqual(G.eye_pixel(0.5, 0.3, spec), (0.9, 0.9, 0.9))
        self.assertAlmostEqual(G.eye_pixel(12.5 / 180, 0.3, spec)[0], 0.4, places=2)

    def test_grade_keeps_hue_and_lifts_luminance(self):
        have, want = (0.24, 0.56, 0.54), (0.45, 0.73, 0.71)
        g = G.grade_gains(have, want)
        lum = G.luminance([have[i] * g[i] for i in range(3)])
        self.assertGreater(lum, G.luminance(have) * 1.2)
        self.assertLess(max(g) / min(g), 1.3)  # mostly one gain: the mint stays mint


if __name__ == "__main__":
    unittest.main()
