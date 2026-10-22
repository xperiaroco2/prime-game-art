"""The alien pilot's static heads' pure formulas (art #196, static_v5): tools/blender/alien_static_geom.py is pure
Python; alien_static_head.py runs the same functions on numpy arrays and alien_static_run.py fixes the GLBs'
tangents with it."""
from __future__ import annotations

import json
import math
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
import alien_static_geom as G  # noqa: E402

EC, R = (0.2, -0.1, 1.5), 0.05  # an eye centre (x >= 0) and radius


class ShapeTest(unittest.TestCase):
    def test_smoothstep(self):
        self.assertEqual(G.smoothstep(1.0, 2.0, 0.5), 0.0)
        self.assertEqual(G.smoothstep(1.0, 2.0, 3.0), 1.0)
        self.assertAlmostEqual(G.smoothstep(1.0, 2.0, 1.5), 0.5)
        self.assertLess(G.smoothstep(0.0, 1.0, 0.25), 0.25)  # eased at the start

    def test_srgb_round_trip(self):
        for c in (0.0, 0.002, 0.04, 0.1, 0.5, 0.93, 1.0):
            self.assertAlmostEqual(G.to_srgb(G.to_linear(c)), c, places=6)
        self.assertAlmostEqual(G.to_linear(0.5), 0.2140, places=4)
        self.assertEqual(G.to_srgb(1.5), G.to_srgb(1.0))  # clipped first

    def test_eye_dist_mirrors_the_eyes(self):
        self.assertAlmostEqual(G.eye_dist(EC[0], EC[1], EC[2], EC, R), 0.0)
        self.assertAlmostEqual(G.eye_dist(-EC[0], EC[1], EC[2], EC, R), 0.0)
        self.assertAlmostEqual(G.eye_dist(EC[0], EC[1], EC[2] + R, EC, R), 1.0)
        self.assertAlmostEqual(G.eye_dist(-EC[0] - 2 * R, EC[1], EC[2], EC, R), 2.0)

    def test_ellipsoid_w(self):
        c, rad = (0.0, 0.0, 0.0), (1.0, 2.0, 3.0)
        self.assertEqual(G.ellipsoid_w(0.0, 0.0, 0.0, c, rad), 1.0)
        self.assertEqual(G.ellipsoid_w(0.0, 1.2, 0.0, c, rad), 1.0)  # inside 0.6 of the radius
        self.assertAlmostEqual(G.ellipsoid_w(0.0, 0.0, 2.4, c, rad), 0.5)
        self.assertEqual(G.ellipsoid_w(1.0, 0.0, 0.0, c, rad), 0.0)

    def test_keep_weights(self):
        mouth = (0.0, -0.2, 1.3)
        self.assertEqual(G.keep_weights(*mouth, EC, R, mouth, 0.1, 0.018), 1.0)
        rim = (EC[0], EC[1], EC[2] + 1.1 * R)
        self.assertAlmostEqual(G.keep_weights(*rim, EC, R, mouth, 0.1, 0.018), 1.0)
        self.assertEqual(G.keep_weights(*rim, EC, R, mouth, 0.1, 0.018, rims=False), 0.0)
        far = (EC[0], EC[1], EC[2] + 3 * R)
        self.assertLess(G.keep_weights(*far, EC, R, mouth, 0.1, 0.018), 0.01)


class AliveTest(unittest.TestCase):
    TEAL = (0.39, 0.77, 0.76)

    def test_k0_and_no_layers_are_the_identity(self):
        c = (0.8, 0.9, 0.85)
        self.assertEqual(G.alive_colour(c, 1.0, 1.0, 1.0, self.TEAL, k=0.0), c)
        self.assertEqual(G.alive_colour(c, 0.0, 0.0, 0.0, self.TEAL), c)

    def test_flush_moves_toward_the_teal(self):
        c = (0.8, 0.9, 0.85)
        out = G.alive_colour(c, 0.0, 1.0, 0.0, self.TEAL)
        for i in range(3):
            self.assertAlmostEqual(out[i], c[i] + 0.22 * (self.TEAL[i] - c[i]))

    def test_crease_is_a_darker_teal_of_the_same_hue(self):
        out = G.alive_colour(self.TEAL, 0.0, 0.0, 1.0, self.TEAL)
        ratios = [out[i] / self.TEAL[i] for i in range(3)]
        self.assertAlmostEqual(min(ratios), max(ratios))  # a pure darkening: no hue shift
        self.assertLess(ratios[0], 1.0)

    def test_clipped(self):
        out = G.alive_colour((1.0, 1.0, 1.0), 1.0, 1.0, 0.0, (1.5, 1.5, 1.5), k=2.0)
        self.assertTrue(all(0.0 <= v <= 1.0 for v in out))


def glb(normals, tangents, interleaved):
    """A one-primitive GLB with NORMAL and TANGENT, tight views or one interleaved view (byteStride 28)."""
    n = len(normals)
    if interleaved:
        blob = b"".join(struct.pack("<3f4f", *nr, *tg) for nr, tg in zip(normals, tangents))
        views = [{"buffer": 0, "byteOffset": 0, "byteLength": len(blob), "byteStride": 28}]
        acc = [{"bufferView": 0, "byteOffset": 0, "componentType": 5126, "count": n, "type": "VEC3"},
               {"bufferView": 0, "byteOffset": 12, "componentType": 5126, "count": n, "type": "VEC4"}]
    else:
        nb = b"".join(struct.pack("<3f", *v) for v in normals)
        tb = b"".join(struct.pack("<4f", *v) for v in tangents)
        blob = nb + tb
        views = [{"buffer": 0, "byteOffset": 0, "byteLength": len(nb)},
                 {"buffer": 0, "byteOffset": len(nb), "byteLength": len(tb)}]
        acc = [{"bufferView": 0, "componentType": 5126, "count": n, "type": "VEC3"},
               {"bufferView": 1, "componentType": 5126, "count": n, "type": "VEC4"}]
    doc = {"asset": {"version": "2.0"}, "buffers": [{"byteLength": len(blob)}], "bufferViews": views,
           "accessors": acc, "meshes": [{"primitives": [{"attributes": {"NORMAL": 0, "TANGENT": 1}}]}]}
    js = json.dumps(doc).encode()
    js += b" " * (-len(js) % 4)
    blob += b"\0" * (-len(blob) % 4)
    body = struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(blob), 0x004E4942) + blob
    return struct.pack("<III", 0x46546C67, 2, 12 + len(body)) + body


def read_back(data, interleaved, n):
    jlen = struct.unpack_from("<I", data, 12)[0]
    b = 20 + jlen + 8
    if interleaved:
        return [struct.unpack_from("<4f", data, b + 28 * k + 12) for k in range(n)]
    return [struct.unpack_from("<4f", data, b + 12 * n + 16 * k) for k in range(n)]


class FixTangentsTest(unittest.TestCase):
    NORMALS = [(0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)]
    TANGENTS = [(1.0, 0.0, 0.0, -1.0), (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0, 0.0)]

    def check(self, interleaved):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.glb"
            p.write_bytes(glb(self.NORMALS, self.TANGENTS, interleaved))
            size = p.stat().st_size
            self.assertEqual(G.fix_tangents(p), 2)
            data = p.read_bytes()
            self.assertEqual(len(data), size)
            out = read_back(data, interleaved, 3)
            self.assertEqual(out[0], self.TANGENTS[0])  # a good tangent is left alone
            for t, nr in zip(out[1:], self.NORMALS[1:]):
                self.assertAlmostEqual(math.sqrt(t[0] ** 2 + t[1] ** 2 + t[2] ** 2), 1.0, places=6)
                self.assertAlmostEqual(t[0] * nr[0] + t[1] * nr[1] + t[2] * nr[2], 0.0, places=6)
                self.assertEqual(t[3], 1.0)
            if interleaved:  # the normals between the tangents are untouched
                jlen = struct.unpack_from("<I", data, 12)[0]
                for k, nr in enumerate(self.NORMALS):
                    self.assertEqual(struct.unpack_from("<3f", data, 20 + jlen + 8 + 28 * k), nr)
            self.assertEqual(G.fix_tangents(p), 0)  # idempotent

    def test_tight_views(self):
        self.check(False)

    def test_interleaved_view(self):
        self.check(True)


if __name__ == "__main__":
    unittest.main()
