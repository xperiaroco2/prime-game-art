"""The eyes' pupils (art #42): the textured export's palette texture for a part coloured by a colour attribute
(export_glb.palette_layout) and godot-check's eye_pupils check on inspect.gd's albedo tones."""

from __future__ import annotations

import sys
import unittest

from runner import common
from runner.commands import _godot

sys.path.insert(0, str(common.ROOT / "tools" / "blender"))

import export_glb  # noqa: E402

WHITE, PUPIL = (0.92, 0.92, 0.9), (0.01, 0.01, 0.012)


class Palette(unittest.TestCase):
    def test_two_colours_two_blocks(self):
        side, uv, pixels = export_glb.palette_layout([WHITE, PUPIL, WHITE, PUPIL], block=16)
        self.assertEqual(side, 32)
        self.assertEqual(len(uv), 2)
        self.assertEqual(len(pixels), side * side * 4)
        for colour, (u, v) in uv.items():
            x, y = int(u * side), int(v * side)
            px = pixels[(y * side + x) * 4:(y * side + x) * 4 + 3]
            for got, want in zip(px, colour):
                self.assertAlmostEqual(got, export_glb.linear_to_srgb(want), places=6)

    def test_uv_at_block_centres_and_distinct(self):
        colours = [(i / 10, 0.0, 0.0) for i in range(5)]
        side, uv, _ = export_glb.palette_layout(colours, block=8)
        self.assertEqual(side, 32)  # 3 columns of 8 px -> 24 -> 32
        self.assertEqual(len(set(uv.values())), 5)
        for u, v in uv.values():
            self.assertAlmostEqual((u * side - 4) % 8, 0.0)
            self.assertAlmostEqual((v * side - 4) % 8, 0.0)

    def test_near_equal_colours_merge(self):
        _, uv, _ = export_glb.palette_layout([(0.5, 0.5, 0.5), (0.500001, 0.5, 0.5)])
        self.assertEqual(len(uv), 1)

    def test_srgb(self):
        self.assertAlmostEqual(export_glb.linear_to_srgb(0.0), 0.0)
        self.assertAlmostEqual(export_glb.linear_to_srgb(1.0), 1.0)
        self.assertAlmostEqual(export_glb.linear_to_srgb(0.214), 0.5, places=2)

    def test_no_colours(self):
        with self.assertRaises(ValueError):
            export_glb.palette_layout([])


def dump(tones: dict | None) -> dict:
    mat = {"name": "fb_eye"}
    if tones is not None:
        mat["tones"] = tones
    return {"meshes": [{"name": "m1_eyes", "rest_bounds": {"min": [0, 0, 0], "max": [1, 1, 1]}, "materials": [mat]}]}


class EyePupils(unittest.TestCase):
    def test_blank_white_eyes_fail(self):
        good, detail = _godot.eye_pupils(dump({"vertices": 400, "white": 400, "black": 0, "image": False,
                                                "uses_vertex_colours": False, "has_vertex_colours": True}))
        self.assertFalse(good)
        self.assertIn("COLOR_0 present, not used as albedo", detail)
        self.assertIn("no pupils", detail)

    def test_palette_eyes_pass(self):
        good, detail = _godot.eye_pupils(dump({"vertices": 400, "white": 300, "black": 90, "image": True,
                                                "uses_vertex_colours": False, "has_vertex_colours": False}))
        self.assertTrue(good)
        self.assertIn("from the texture", detail)

    def test_a_speck_is_no_pupil(self):
        good, _ = _godot.eye_pupils(dump({"vertices": 1000, "white": 990, "black": 5}))
        self.assertFalse(good)

    def test_missing_part_or_tones(self):
        self.assertFalse(_godot.eye_pupils({"meshes": []})[0])
        self.assertFalse(_godot.eye_pupils(dump(None))[0])


if __name__ == "__main__":
    unittest.main()
