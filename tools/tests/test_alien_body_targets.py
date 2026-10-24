"""The alien body's refit targets (art #196, the A body's refit route). alien_body.py runs inside Blender; its targets
loader is checked here with stub Blender modules: u1.toml holds the numbers S1/S1c were built with (S4a/S4b's cage
takes S1c's skeleton and neck ring), chameleon_a.toml keeps the standard neck ring and the height cap, and the
measuring script decodes a PNG with zlib alone."""
from __future__ import annotations

import importlib.util
import struct
import sys
import tempfile
import types
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLENDER = ROOT / "tools" / "blender"
TARGETS = BLENDER / "alien_body_targets"


def _load(name):
    stubs = [n for n in ("bmesh", "bpy", "mathutils") if n not in sys.modules]
    for n in stubs:
        sys.modules[n] = types.ModuleType(n)
    for cls in ("Vector", "Matrix"):
        if not hasattr(sys.modules["mathutils"], cls):
            setattr(sys.modules["mathutils"], cls, object)
    try:
        spec = importlib.util.spec_from_file_location(f"{name}_t", BLENDER / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        for n in stubs:
            del sys.modules[n]


class Targets(unittest.TestCase):
    def setUp(self):
        self.ab = _load("alien_body")

    def test_u1_holds_s1c_numbers(self):
        ab = self.ab
        self.assertEqual(ab.apply_targets(TARGETS / "u1.toml"), "u1")
        self.assertEqual(ab.BANDS[0], (0.783, 0.304, 0.198))
        self.assertEqual(ab.BANDS[6], (1.200, None, 0.218))
        self.assertEqual(len(ab.BANDS), 10)
        self.assertEqual(ab.LENGTH["thigh"], 0.753)
        self.assertEqual(ab.LENGTH["neck_01"], 1.25)
        self.assertEqual(ab.RADIUS, {"upperarm": 0.042, "lowerarm": 0.031, "thigh": 0.066, "calf": 0.054})
        self.assertEqual((ab.FINGERS, ab.FINGER_LEN, ab.FINGER_THICK, ab.HAND_SCALE), (4, 0.8, 1.55, 1.12))
        self.assertEqual((ab.RING_Z, ab.NECK, ab.TRUNK_Z, ab.BELLY), (1.39, (0.059, 0.055), (0.70, 1.22), 0.03))
        self.assertEqual(ab.TOE_CENTRES, [-2 / 3, 0.0, 2 / 3])
        self.assertEqual((ab.TOE_SEMI, ab.NOTCHES, ab.NOTCH_W, ab.TOE_SPLAY), (1 / 3, [-1 / 3, 1 / 3], 0.1, 0.0))
        self.assertEqual(ab.NECK_FLARE, 0.0)
        for h in (0.6, 0.8, 1.25, 1.29, 1.36):
            self.assertAlmostEqual(ab.Z(h), h)

    def test_chameleon_keeps_the_ring_and_the_cap(self):
        ab = self.ab
        ab.apply_targets(TARGETS / "u1.toml")
        neck_u1 = ab.NECK
        self.assertEqual(ab.apply_targets(TARGETS / "chameleon_a.toml"), "chameleon_a")
        self.assertEqual(ab.NECK, neck_u1)  # the welded heads are scaled from the ring's x extent
        self.assertEqual(ab.FINGERS, 5)
        self.assertLessEqual(ab.RING_Z + 0.494, 1.95 + 1e-9)  # the r5 head stands 0.494 m above its ring
        self.assertAlmostEqual(ab.Z(1.39), ab.RING_Z)
        zs = [ab.Z(h / 100) for h in range(0, 200)]
        self.assertEqual(zs, sorted(zs))
        self.assertEqual(len(ab.TOE_CENTRES), 2)
        self.assertGreater(ab.NECK_FLARE, ab.NECK[0])
        self.assertLess(ab.NECK_FLARE_Z, ab.RING_Z)


class Measure(unittest.TestCase):
    def test_png_decode_with_filters(self):
        me = _load("alien_body_measure")
        w, h = 5, 4
        rows = [[(x * 40, y * 50, 200) for x in range(w)] for y in range(h)]
        raw = b""
        prev = [0] * (w * 3)
        for y, r in enumerate(rows):
            line = [c for p in r for c in p]
            f = y % 3  # none, sub, up
            if f == 0:
                enc = line
            elif f == 1:
                enc = [(line[i] - (line[i - 3] if i >= 3 else 0)) & 255 for i in range(len(line))]
            else:
                enc = [(line[i] - prev[i]) & 255 for i in range(len(line))]
            raw += bytes([f] + enc)
            prev = line

        def chunk(t, d):
            return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
        png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
               + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.png"
            p.write_bytes(png)
            W, H, got = me.read_png(str(p))
        self.assertEqual((W, H), (w, h))
        self.assertEqual(got, rows)


if __name__ == "__main__":
    unittest.main()
