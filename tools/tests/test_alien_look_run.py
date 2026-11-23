"""The plain-Python parts of the recovered aliens' look driver (tools/blender/alien_look_run.py, art #393): the GLB's
embedded images, the PNG reader under every row filter, the body mask and the median."""
import json
import struct
import sys
import unittest
import zlib
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import alien_look_run as L  # noqa: E402


def paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if pa <= pb and pa <= pc else b if pb <= pc else c


def encode(rows, ch, filters):
    """A PNG of the pixel rows (lists of channel bytes), each row under its own filter type."""
    w = len(rows[0]) // ch
    raw, prev = b"", [0] * (w * ch)
    for row, f in zip(rows, filters):
        out = []
        for x, v in enumerate(row):
            a = row[x - ch] if x >= ch else 0
            c = prev[x - ch] if x >= ch else 0
            pred = [0, a, prev[x], (a + prev[x]) // 2, paeth(a, prev[x], c)][f]
            out.append((v - pred) & 255)
        raw += bytes([f]) + bytes(out)
        prev = row

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
    ihdr = struct.pack(">IIBBBBB", w, len(rows), 8, 2 if ch == 3 else 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


ROWS = [[(x * 37 + y * 91 + c * 13) % 256 for x in range(6) for c in range(3)] for y in range(5)]


class Png(unittest.TestCase):
    def test_every_filter(self):
        for ch in (3, 4):
            rows = [[(v * 7 + k) % 256 for k, v in enumerate(r[:4 * ch])] for r in ROWS]
            w, h, got_ch, px = L.png_pixels(encode(rows, ch, [0, 1, 2, 3, 4]))
            self.assertEqual((w, h, got_ch), (4, 5, ch))
            self.assertEqual(px, bytes(v for r in rows for v in r))

    def test_body_mask_skin_only(self):
        # two skin texels (R >= 128) with G 100 and 120, one eye texel (R 0) with G 250: the eye stays out
        png = encode([[200, 100, 30, 255, 120, 30, 0, 250, 250]], 3, [0])
        bm = L.body_mask(png)
        self.assertEqual(bm[0], 1.0)
        self.assertAlmostEqual(bm[1], 100 / 255)  # the lower median of two
        self.assertAlmostEqual(bm[2], 30 / 255)

    def test_median_rgb(self):
        png = encode([[10, 20, 30, 50, 60, 70, 90, 100, 110]], 3, [1])
        self.assertEqual([round(v * 255) for v in L.median_rgb(png)], [50, 60, 70])


class Glb(unittest.TestCase):
    def test_images_by_name(self):
        a, b = b"first-image", b"second"
        gltf = {"asset": {"version": "2.0"}, "buffers": [{"byteLength": 20}],
                "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(a)},
                                {"buffer": 0, "byteOffset": 12, "byteLength": len(b)}],
                "images": [{"name": "x_mask", "bufferView": 0, "mimeType": "image/png"},
                           {"bufferView": 1, "mimeType": "image/png"}]}
        js = json.dumps(gltf).encode()
        js += b" " * (-len(js) % 4)
        binary = a + b"\0" + b + b"\0\0"
        data = (struct.pack("<III", 0x46546C67, 2, 28 + len(js) + len(binary)) + struct.pack("<I4s", len(js), b"JSON")
                + js + struct.pack("<I4s", len(binary), b"BIN\0") + binary)
        with TemporaryDirectory() as d:
            p = Path(d) / "t.glb"
            p.write_bytes(data)
            self.assertEqual(L.glb_images(p), {"x_mask": a, "image_1": b})

    def test_alive_params_are_the_static_v5_pick(self):
        p = L.alive_params()
        self.assertEqual(p["transmission"], 1.5)
        self.assertEqual(p["specular_level"], 0.18)
        self.assertEqual(p["limbal"], 0.8)


if __name__ == "__main__":
    unittest.main()
