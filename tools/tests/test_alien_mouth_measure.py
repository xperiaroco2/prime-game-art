"""M16e (art #196, PR #258 minor 3): tools/blender/alien_mouth_measure.py, the mouth's proportions in a PNG box,
on a drawn test mouth (two red lips with a dark lip line on a grey face, two dark nostrils above)."""
from __future__ import annotations

import importlib.util
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("alien_mouth_measure",
                                              ROOT / "tools" / "blender" / "alien_mouth_measure.py")
MM = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MM)

BG, SKIN, LIP, LINE, DARK = (110, 110, 110), (120, 180, 150), (220, 90, 80), (120, 40, 40), (20, 30, 25)


def drawn(path: Path) -> None:
    """A 200 x 160 PNG: the face 40..160 wide; the lips x 60..139 (W 80), the upper 70..89, the lower 91..114 with the
    lip line at row 90; the lips taper linearly over the last 20 px each side; nostrils at x 88 and 112, rows 50..55."""
    w, h = 200, 160
    rows = []
    for y in range(h):
        line = bytearray()
        for x in range(w):
            c = BG
            if 40 <= x < 160:
                c = SKIN
            if x in (88, 112) and 50 <= y < 56:
                c = DARK
            if 60 <= x < 140:
                k = min(1.0, min(x - 60, 139 - x) / 20 + 0.25)
                top, bot = 90 - 20 * k, 90 + 24 * k
                if top <= y <= bot:
                    c = LINE if y == 90 else LIP
            line += bytes(c)
        rows.append(b"\x00" + bytes(line))
    def chunk(t, body):
        return struct.pack(">I", len(body)) + t + body + struct.pack(">I", zlib.crc32(t + body))
    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))
    path.write_bytes(data)


class MouthMeasure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.png = Path(cls.tmp.name) / "mouth.png"
        drawn(cls.png)
        cls.rows, cls.bpp = MM.read_png(str(cls.png))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_front(self):
        r = MM.front(self.rows, self.bpp, (0, 30, 200, 140), face=True)
        self.assertEqual(r["W"], 80)
        self.assertEqual(r["seam"], 90)
        self.assertAlmostEqual(r["upper/W"], 20 / 80, places=2)
        self.assertAlmostEqual(r["lower/W"], 24 / 80, places=2)
        self.assertAlmostEqual(r["nostrils"], 24.0, places=1)
        self.assertEqual(r["face_w"], 120)
        self.assertAlmostEqual(r["W/face"], 80 / 120, places=2)
        self.assertGreater(r["corner_len"], 0.1)
        self.assertLess(r["tip_h"], 1.0)


if __name__ == "__main__":
    unittest.main()
