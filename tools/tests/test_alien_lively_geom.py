"""The static head's liveliness proof's pure formulas (art #196, lively): tools/blender/alien_lively_geom.py (the
neck and crest weights, the gaze maths and its lid clamp, the skin added to a GLB, the PNG writer)."""
from __future__ import annotations

import json
import math
import struct
import sys
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
import alien_lively_geom as G  # noqa: E402


def tiny_glb(n: int = 3) -> bytes:
    """A one-triangle-per-three-vertices GLB: POSITION only, one node, one scene."""
    pos = struct.pack(f"<{3 * n}f", *[float(i) for i in range(3 * n)])
    doc = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, "name": "m"}],
           "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
           "accessors": [{"bufferView": 0, "componentType": 5126, "count": n, "type": "VEC3"}],
           "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(pos)}],
           "buffers": [{"byteLength": len(pos)}]}
    return G.write_glb(doc, pos)


class WeightTest(unittest.TestCase):
    def test_neck_weights_sum_and_ends(self):
        for y in (-1.0, -0.5, -0.45, -0.4, 0.0):
            w = G.neck_weights(y, -0.55, -0.47, -0.39)
            self.assertAlmostEqual(sum(w), 1.0)
        self.assertEqual(G.neck_weights(-1.0, -0.55, -0.47, -0.39), (1.0, 0.0, 0.0))
        self.assertEqual(G.neck_weights(0.0, -0.55, -0.47, -0.39), (0.0, 0.0, 1.0))
        self.assertAlmostEqual(G.neck_weights(-0.47, -0.55, -0.47, -0.39)[1], 1.0)

    def test_crest_split(self):
        for t in (-0.5, 0.0, 0.2, 0.5, 0.7, 1.0, 1.5):
            self.assertAlmostEqual(sum(G.crest_split(t)), 1.0)
        self.assertEqual(G.crest_split(0.0), (1.0, 0.0, 0.0))
        self.assertEqual(G.crest_split(0.5), (0.0, 1.0, 0.0))
        self.assertEqual(G.crest_split(1.0), (0.0, 0.0, 1.0))


class GazeTest(unittest.TestCase):
    def test_frame_is_orthonormal(self):
        f, s, u = G.eye_frame((0.3, -0.1, 0.9))
        for a, b in ((f, s), (f, u), (s, u)):
            self.assertAlmostEqual(sum(x * y for x, y in zip(a, b)), 0.0)
        self.assertGreater(s[0], 0.9)  # side toward +X
        self.assertGreater(u[1], 0.9)  # up toward +Y

    def test_gaze_dir_rest_and_turns(self):
        rest = (0.1, -0.05, 1.0)
        g = G.gaze_dir(rest, 0.0, 0.0)
        n = math.sqrt(sum(c * c for c in rest))
        for a, b in zip(g, rest):
            self.assertAlmostEqual(a, b / n)
        self.assertGreater(G.gaze_dir(rest, 0.3, 0.0)[0], g[0])  # yaw toward +X
        self.assertGreater(G.gaze_dir(rest, 0.0, 0.3)[1], g[1])  # pitch up

    def test_offsets(self):
        y, p = G.gaze_offsets((1.0, 0.0, 1.0))
        self.assertAlmostEqual(y, math.pi / 4)
        self.assertAlmostEqual(p, 0.0)
        self.assertAlmostEqual(G.gaze_offsets((0.0, 1.0, 1.0))[1], math.pi / 4)

    def test_clamp_ellipse(self):
        lim = {"pos_x": 20, "neg_x": 10, "up": 0, "down": 30}
        self.assertEqual(G.clamp_gaze(0.1, 0.1, lim), (0.1, 0.0))  # no room up: the pitch goes, the yaw is clamped alone
        lim = {"pos_x": 20, "neg_x": 10, "up": 5, "down": 30}
        y, p = G.clamp_gaze(math.radians(40), 0.0, lim)
        self.assertAlmostEqual(math.degrees(y), 20)
        y, p = G.clamp_gaze(-math.radians(30), -math.radians(60), lim)
        self.assertAlmostEqual((math.degrees(y) / 10) ** 2 + (math.degrees(p) / 30) ** 2, 1.0)
        self.assertEqual(G.clamp_gaze(0.01, 0.01, lim), (0.01, 0.01))

    def test_clamp_cap(self):
        lim = {"pos_x": 40, "neg_x": 8, "up": 0, "down": 40}
        self.assertAlmostEqual(math.degrees(G.clamp_gaze(math.radians(60), 0.0, lim)[0]), 40)
        self.assertAlmostEqual(math.degrees(G.clamp_gaze(math.radians(60), 0.0, lim, cap_deg=25)[0]), 25)
        self.assertAlmostEqual(math.degrees(G.clamp_gaze(-math.radians(60), 0.0, lim, cap_deg=25)[0]), -8)
        self.assertAlmostEqual(math.degrees(G.clamp_gaze(0.0, -math.radians(60), lim, cap_deg=25)[1]), -25)

    def test_eye_offsets_invert_gaze_dir(self):
        rest = (-0.06077, -0.01519, 0.99804)  # the chameleon's left eye
        for yaw, pitch in ((0.0, 0.0), (0.3, -0.2), (-0.4, 0.1)):
            y, p = G.eye_offsets(rest, G.gaze_dir(rest, yaw, pitch))
            self.assertAlmostEqual(y, yaw)
            self.assertAlmostEqual(p, pitch)
        # straight ahead in the head's frame is a few degrees off this eye's rest gaze
        y, _ = G.eye_offsets(rest, (0.0, 0.0, 1.0))
        self.assertAlmostEqual(math.degrees(y), math.degrees(math.atan2(0.06077, 0.99804)), places=3)


class SkinTest(unittest.TestCase):
    def test_add_skin_round_trip(self):
        pos = {name: (0.0, 0.1 * k, 0.0) for k, name in enumerate(G.JOINTS)}
        infl = [[(0, 0.3), (1, 0.7)], [(2, 1.0)], [(2, 0.5), (3, 0.25), (4, 0.15), (5, 0.07), (1, 0.03)]]
        doc, binary = G.read_glb(G.add_skin(tiny_glb(), pos, infl))
        self.assertEqual(doc["nodes"][0]["skin"], 0)
        skin = doc["skins"][0]
        self.assertEqual([doc["nodes"][j]["name"] for j in skin["joints"]], list(G.JOINTS))
        self.assertIn(skin["joints"][0], doc["scenes"][0]["nodes"])
        self.assertEqual(doc["nodes"][skin["joints"][2]]["translation"], [0.0, 0.1, 0.0])  # Head relative to Neck
        attrs = doc["meshes"][0]["primitives"][0]["attributes"]
        for key in ("JOINTS_0", "WEIGHTS_0"):
            view = doc["bufferViews"][doc["accessors"][attrs[key]]["bufferView"]]
            self.assertEqual(view["byteOffset"] % 4, 0)
        wv = doc["bufferViews"][doc["accessors"][attrs["WEIGHTS_0"]]["bufferView"]]
        w = struct.unpack_from("<12f", binary, wv["byteOffset"])
        for k in range(3):
            self.assertAlmostEqual(sum(w[4 * k:4 * k + 4]), 1.0, places=6)
        jv = doc["bufferViews"][doc["accessors"][attrs["JOINTS_0"]]["bufferView"]]
        j = struct.unpack_from("<12H", binary, jv["byteOffset"])
        self.assertEqual(j[8:12], (2, 3, 4, 5))  # the four largest kept, the smallest dropped
        self.assertEqual(doc["buffers"][0]["byteLength"], len(binary))

    def test_refuses_a_count_mismatch(self):
        with self.assertRaises(ValueError):
            G.add_skin(tiny_glb(), {n: (0.0, 0.0, 0.0) for n in G.JOINTS}, [[(0, 1.0)]])

    def test_normalise_weights_float32_sum(self):
        w = G.normalise_weights([0.1, 0.2, 0.3, 0.4000001])
        self.assertAlmostEqual(sum(w), 1.0, places=6)


class PngTest(unittest.TestCase):
    def test_png_bytes(self):
        data = G.png_bytes(2, 1, bytes([255, 0, 0, 0, 255, 0]))
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        w, h = struct.unpack(">II", data[16:24])
        self.assertEqual((w, h), (2, 1))
        idat = data.index(b"IDAT")
        size = struct.unpack(">I", data[idat - 4:idat])[0]
        self.assertEqual(zlib.decompress(data[idat + 4:idat + 4 + size]), b"\0" + bytes([255, 0, 0, 0, 255, 0]))


class EyePitTest(unittest.TestCase):
    """The eye pit's fix (art #196): the eyeball's sphere fit and the projection of the old iris onto it."""

    def sphere_points(self, c, r, n=40):
        pts = []
        for i in range(n):
            z = -1.0 + 2.0 * (i + 0.5) / n
            a = i * 2.399963  # the golden angle: spread points
            s = math.sqrt(1.0 - z * z)
            pts.append((c[0] + r * s * math.cos(a), c[1] + r * s * math.sin(a), c[2] + r * z))
        return pts

    def test_fit_sphere_exact(self):
        c, r = G.fit_sphere(self.sphere_points((0.265, 0.266, 0.355), 0.186))
        for got, want in zip(c, (0.265, 0.266, 0.355)):
            self.assertAlmostEqual(got, want, places=9)
        self.assertAlmostEqual(r, 0.186, places=9)

    def test_fit_sphere_cap_only(self):
        # a cap of 60 degrees about +Z (the visible sclera ring the build fits) still gives the sphere
        pts = [p for p in self.sphere_points((0.0, 0.0, 0.0), 1.0, 400) if p[2] > 0.5]
        c, r = G.fit_sphere(pts)
        self.assertAlmostEqual(r, 1.0, places=9)
        self.assertAlmostEqual(math.dist(c, (0.0, 0.0, 0.0)), 0.0, places=9)

    def test_fit_sphere_degenerate(self):
        with self.assertRaises(ValueError):
            G.fit_sphere([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 1.0, 0.0)])

    def test_pit_weight(self):
        self.assertEqual(G.pit_weight(0.1, 0.3, 0.5, 1.0, 0.1, 0.2), 1.0)
        self.assertEqual(G.pit_weight(0.6, 0.3, 0.5, 1.0, 0.1, 0.2), 0.0)
        self.assertEqual(G.pit_weight(0.1, 0.3, 0.5, 0.05, 0.1, 0.2), 0.0)  # next to the lid: never moved
        self.assertAlmostEqual(G.pit_weight(0.4, 0.3, 0.5, 1.0, 0.1, 0.2), 0.5)
        self.assertAlmostEqual(G.pit_weight(0.1, 0.3, 0.5, 0.15, 0.1, 0.2), 0.5)

    def test_capped_weight(self):
        self.assertEqual(G.capped_weight(1.0, 0.002, 1.0, 0.5, 0.004), 1.0)  # a small move: untouched
        self.assertAlmostEqual(G.capped_weight(1.0, 0.014, 1.0, 0.5, 0.004), 0.004 / 0.014)  # the absolute cap
        self.assertAlmostEqual(G.capped_weight(1.0, 0.004, 0.002, 0.5, 0.004), 0.25)  # half the room to the lid
        self.assertEqual(G.capped_weight(0.3, 0.004, 0.0, 0.5, 0.004), 0.0)  # touching a lid: never moved
        self.assertEqual(G.capped_weight(0.0, 0.01, 1.0, 0.5, 0.004), 0.0)
        self.assertEqual(G.capped_weight(0.7, 0.0, 1.0, 0.5, 0.004), 0.7)  # already on the sphere

    def test_project_on_sphere(self):
        dent = (0.0, 0.0, 0.97)  # 3 % of the radius inside the unit sphere
        self.assertEqual(G.project_on_sphere(dent, (0.0, 0.0, 0.0), 1.0, 0.0), dent)
        full = G.project_on_sphere(dent, (0.0, 0.0, 0.0), 1.0, 1.0)
        self.assertAlmostEqual(full[2], 1.0)
        half = G.project_on_sphere(dent, (0.0, 0.0, 0.0), 1.0, 0.5)
        self.assertAlmostEqual(half[2], 0.985)
        self.assertAlmostEqual(half[0], 0.0)

    def test_colour_distance(self):
        self.assertAlmostEqual(G.colour_distance((1.0, 1.0, 1.0), (0.0, 0.0, 0.0)), math.sqrt(3.0))
        self.assertEqual(G.colour_distance((0.5, 0.4, 0.3), (0.5, 0.4, 0.3)), 0.0)


if __name__ == "__main__":
    unittest.main()
