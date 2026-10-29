"""The cloth maps' fill and the denim's shift (tools/blender/clothes_texture.py, art #196) in headless Blender's
numpy on small synthetic maps: the UV islands' mask, the push-pull fill (the islands' texels unchanged, the empty ones
take the nearest island's colour, no black left), and the denim's gain (the denim lighter by the gain in linear,
the neutral stripes and the orange stitching unchanged).

This file is also the Blender side of the test: run inside Blender (`blender -b ... --python <this file> -- <out>`)
it writes its numbers to <out>/texture.json, which the unittest reads. Skipped when Blender is missing."""

from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

IN_BLENDER = "bpy" in sys.modules

if IN_BLENDER:
    import numpy as np

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
    import clothes_texture as T

    def blender_side(out: Path) -> None:
        r = {}
        # one triangle and one square island on a 16 x 16 map
        tris = np.array([[[0.0, 0.0], [0.5, 0.0], [0.0, 0.5]],
                         [[0.75, 0.75], [1.0, 0.75], [1.0, 1.0]], [[0.75, 0.75], [1.0, 1.0], [0.75, 1.0]]])
        mask = T.island_mask(tris, 16, 16, grow=0)
        r["mask_count"] = int(mask.sum())
        r["mask_corners"] = [bool(mask[0, 0]), bool(mask[15, 15]), bool(mask[8, 8]), bool(mask[15, 0])]
        px = np.zeros((16, 16, 3), np.float32)
        px[mask] = [0.2, 0.3, 0.6]
        px[12:, 12:][mask[12:, 12:]] = [0.9, 0.1, 0.1]
        filled = T.fill(px, mask)
        r["kept"] = bool(np.array_equal(filled[mask], px[mask]))
        r["min_filled"] = float(filled[~mask].sum(-1).min())
        r["near_tri"] = filled[1, 7].astype(np.float64).round(4).tolist()  # beside the blue triangle
        r["near_square"] = filled[13, 10].astype(np.float64).round(4).tolist()  # beside the red square
        denim = np.array([[0.090, 0.122, 0.176]], np.float32)  # the r16 legs' stored sRGB
        stripe = np.array([[0.10, 0.10, 0.11]], np.float32)
        white = np.array([[0.92, 0.92, 0.93]], np.float32)
        orange = np.array([[0.75, 0.45, 0.20]], np.float32)
        r["weights"] = [float(T.denim_weight(c)[0]) for c in (denim, stripe, white, orange)]
        gain = (2.0, 2.0, 2.0)
        r["denim_lin_ratio"] = (T.to_linear(T.shift(denim, gain).astype(np.float64)) / T.to_linear(denim.astype(np.float64)))[0].round(4).tolist()
        r["others_same"] = [bool(np.allclose(T.shift(c, gain), c, atol=1e-6)) for c in (stripe, white, orange)]
        # the moved helpers (C1h): free_rect, blur, stripe_image, vertex_normals
        used = np.zeros((20, 30), bool)
        used[:, :10] = True
        r["free_rect"] = T.free_rect(used, 5, 4, 2)  # 2 past the used columns and 2 off the edges
        r["free_rect_none"] = T.free_rect(np.zeros((6, 6), bool), 5, 5, 1) is None
        a = np.zeros((9, 9), np.float32)
        a[4, 4] = 9.0
        b = T.blur(a, 1)
        r["blur"] = [round(float(b[4, 4]), 4), round(float(b.sum()), 4), round(float(b[0, 0]), 4)]
        img = T.stripe_image((0.0, 0.0, 0.5), (1.0, 1.0, 1.0), 0.1, 0.5, 1.0, {"torso": (0.25, 0.5)},
                             {"torso": 0.0}, (40, 20))
        r["stripes"] = [round(float(img[0, 20, 0]), 3), round(float(img[1, 20, 0]), 3), round(float(img[0, 2, 0]), 3)]
        pts = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [5, 5, 5]], np.float64)
        r["normals"] = T.vertex_normals(pts, [[0, 1, 2, 3]]).round(4).tolist()
        (out / "texture.json").write_text(json.dumps(r), encoding="utf-8")

    blender_side(Path(sys.argv[sys.argv.index("--") + 1]))

else:
    from runner import blender, common, pins

    OUT = common.OUT / "tests" / "clothes_texture"
    HAVE_BLENDER = bool((path := common.tool_path(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)) and path.is_file())

    @unittest.skipUnless(HAVE_BLENDER, "needs Blender")
    class ClothesTextureBlenderTest(unittest.TestCase):
        r: dict = {}

        @classmethod
        def setUpClass(cls) -> None:
            shutil.rmtree(OUT, ignore_errors=True)
            OUT.mkdir(parents=True)
            blender.run_script(Path(__file__).resolve(), [str(OUT)], timeout=300)
            cls.r = json.loads((OUT / "texture.json").read_text(encoding="utf-8"))

        def test_mask(self) -> None:
            self.assertEqual(self.r["mask_corners"], [True, True, False, False])
            self.assertGreater(self.r["mask_count"], 16 + 20)  # the square's 16 texels and the triangle's half of 64

        def test_fill(self) -> None:
            self.assertTrue(self.r["kept"])
            self.assertGreater(self.r["min_filled"], 0.5)  # no black texel left
            self.assertEqual(self.r["near_tri"], [0.2, 0.3, 0.6])
            self.assertEqual(self.r["near_square"], [0.9, 0.1, 0.1])

        def test_moved_helpers(self) -> None:
            self.assertEqual(self.r["free_rect"], [2, 12])
            self.assertTrue(self.r["free_rect_none"])
            self.assertEqual(self.r["blur"], [1.0, 9.0, 0.0])  # the peak spread over 3 x 3, the sum kept
            self.assertEqual(self.r["stripes"], [1.0, 0.0, 1.0])  # white, then navy from the island's edge; white outside
            self.assertEqual(self.r["normals"][:4], [[0.0, 0.0, 1.0]] * 4)
            self.assertEqual(self.r["normals"][4], [0.0, 0.0, 0.0])

        def test_denim_shift(self) -> None:
            self.assertEqual(self.r["weights"], [1.0, 0.0, 0.0, 0.0])
            for v in self.r["denim_lin_ratio"]:
                self.assertAlmostEqual(v, 2.0, delta=0.01)
            self.assertEqual(self.r["others_same"], [True, True, True])


if __name__ == "__main__" and not IN_BLENDER:
    unittest.main()
