"""The alien skin's authored texture formulas (art #196, M3a): tools/blender/alien_texture_geom.py is pure Python;
alien_texture.py runs the same functions on numpy arrays. The colour constants must match the kit's."""
from __future__ import annotations

import math
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
import alien_texture_geom as G  # noqa: E402

FLAT = {"light": 0.0, "accent": 0.0, "ao": 1.0, "curv": 0.5, "thick": 1.0, "deep": 0.0, "face": 0.0, "blotch": 0.0,
        "hue": 0.0, "warm": 0.0, "flush": 0.0, "pore": 0.0, "tzone": 0.0, "mouth": 0.0, "fine": 0.0}


def field(**kw):
    f = dict(FLAT)
    f.update(kw)
    return f


def lum(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


class ColourTest(unittest.TestCase):
    def test_srgb_round_trip(self):
        for c in (0.0, 0.02, 0.11, 0.5, 0.92, 1.0):
            self.assertAlmostEqual(G.linear_to_srgb(G.srgb_to_linear(c)), c, places=6)

    def test_constants_match_the_kit(self):
        asm = (ROOT / "tools" / "blender" / "alien_assemble.py").read_text(encoding="utf-8")
        self.assertIn(f'"teal": {G.TEAL_SRGB}', asm)
        self.assertIn(f'"teal": {G.PALE_SRGB}', asm)
        self.assertIn(f"LIGHT_MIX = {G.LIGHT_MIX}", asm)
        self.assertIn(f"ACCENT_MIX = {G.ACCENT_MIX}", asm)
        face = (ROOT / "tools" / "blender" / "alien_face.py").read_text(encoding="utf-8")
        self.assertIn(f"ACCENT = {G.ACCENT_SRGB}", face)
        shader = (ROOT / "godot" / "alien" / "alien_hue.gdshader").read_text(encoding="utf-8")
        m = re.search(r"deep_mul = vec3\(([^)]*)\)", shader)
        self.assertEqual(tuple(float(x) for x in m.group(1).split(",")), G.DEEP_MUL)
        m = re.search(r"warm_mul = vec3\(([^)]*)\)", shader)
        self.assertEqual(tuple(float(x) for x in m.group(1).split(",")), G.WARM_MUL)

    def test_part_material_is_swapped_by_alien_gd(self):
        src = (ROOT / "tools" / "blender" / "alien_texture.py").read_text(encoding="utf-8")
        name = re.search(r'PART_MATERIAL = "([^"]+)"', src).group(1)
        gd = (ROOT / "godot" / "alien" / "alien.gd").read_text(encoding="utf-8")
        hue = re.search(r"const HUE_MATERIALS := \[([^]]*)\]", gd).group(1)
        self.assertIn(f'"{name}"', hue)
        self.assertIn('"alien_hue"', hue)


class AlbedoTest(unittest.TestCase):
    def test_flat_inputs_give_the_kit_colours(self):
        s = dict(G.TEX, hue_sat=1.0, pale_sat=1.0)
        teal = G.albedo(field(), s)
        for a, b in zip(teal, G.lin3(G.TEAL_SRGB)):
            self.assertAlmostEqual(a, b, places=6)
        pale = G.albedo(field(light=1.0), s)
        expect = [G.mix(t, p, G.LIGHT_MIX) for t, p in zip(G.lin3(G.TEAL_SRGB), G.lin3(G.PALE_SRGB))]
        for a, b in zip(pale, expect):
            self.assertAlmostEqual(a, b, places=6)

    def test_saturation_keeps_luminance(self):
        c = G.lin3(G.PALE_SRGB)
        s = G.saturate(c, 1.6)
        self.assertAlmostEqual(lum(s), lum(c), places=6)
        self.assertGreater(max(s) - min(s), max(c) - min(c))
        self.assertEqual(G.saturate(c, 1.0), c)

    def test_accent_edge_is_narrowed(self):
        flat = G.albedo(field())
        self.assertEqual(G.albedo(field(accent=0.15)), flat)  # below the edge: no grey fringe
        full = G.albedo(field(accent=1.0))
        self.assertGreater(full[0], 3 * flat[0])  # coral

    def test_concave_darker_and_bluer_convex_paler(self):
        flat = G.albedo(field())
        cave = G.albedo(field(curv=0.3))
        bump = G.albedo(field(curv=0.7))
        self.assertLess(lum(cave), lum(flat))
        self.assertGreater(cave[2] / cave[0], flat[2] / flat[0])  # bluer
        self.assertGreater(lum(bump), lum(flat))

    def test_ao_is_half_strength(self):
        flat = G.albedo(field())
        dark = G.albedo(field(ao=0.0))
        for a, b in zip(dark, flat):
            self.assertAlmostEqual(a, b * (1 - G.TEX["ao"]), places=6)

    def test_thin_warm_parts_are_warmer(self):
        flat = G.albedo(field(thick=0.2))
        warm = G.albedo(field(thick=0.2, warm=1.0))
        self.assertGreater(warm[0] / warm[2], flat[0] / flat[2])
        self.assertEqual(G.albedo(field(thick=0.2)), G.albedo(field(thick=1.0)))  # thinness alone tints nothing

    def test_hue_drift_is_warm_and_cool_and_small(self):
        w, c, flat = G.albedo(field(hue=1.0)), G.albedo(field(hue=-1.0)), G.albedo(field())
        self.assertGreater(w[0] / w[2], flat[0] / flat[2])
        self.assertLess(c[0] / c[2], flat[0] / flat[2])
        self.assertLess(abs(lum(w) / lum(flat) - 1), 0.1)

    def test_range(self):
        for kw in (dict(curv=0.0, ao=0.0, pore=1.0), dict(curv=1.0, light=1.0, flush=1.0, warm=1.0, thick=0.0),
                   dict(accent=1.0, blotch=1.0, hue=1.0)):
            for ch in G.albedo(field(**kw)):
                self.assertGreaterEqual(ch, 0.0)
                self.assertLessEqual(ch, 1.0)


class RoughnessTest(unittest.TestCase):
    def test_base_and_gloss(self):
        self.assertAlmostEqual(G.roughness(field()), G.TEX["rough"])
        self.assertLess(G.roughness(field(curv=0.8)), G.TEX["rough"])  # glossier convex
        self.assertLess(G.roughness(field(tzone=1.0)), G.TEX["rough"])
        self.assertLess(G.roughness(field(mouth=1.0)), G.roughness(field(tzone=1.0)) + 0.05)
        self.assertGreater(G.roughness(field(curv=0.2)), G.TEX["rough"])  # rougher in the creases

    def test_clamped(self):
        lo = G.roughness(field(curv=1.0, tzone=1.0, mouth=1.0, fine=-1.0))
        hi = G.roughness(field(curv=0.0, fine=1.0, pore=1.0))
        self.assertGreaterEqual(lo, G.TEX["rough_min"])
        self.assertLessEqual(hi, G.TEX["rough_max"])

    def test_orm_packing(self):
        self.assertEqual(G.orm(0.8, 0.55), (0.8, 0.55, 0.0))


class MaskTest(unittest.TestCase):
    def test_sss(self):
        self.assertEqual(G.sss_mask(field(thick=1.0)), 0.0)
        self.assertGreater(G.sss_mask(field(thick=0.2)), G.sss_mask(field(thick=0.6)))
        self.assertLessEqual(G.sss_mask(field(thick=0.0, warm=1.0)), 1.0)

    def test_pores(self):
        self.assertEqual(G.micro_pore(0.05), 0.0)  # a bump
        self.assertGreater(G.micro_pore(-0.05), 0.0)  # a pit
        self.assertEqual(G.micro_pore(-10.0), 1.0)


class CageTest(unittest.TestCase):
    def test_offset(self):
        c = G.CAGE
        self.assertEqual(G.cage_offset(math.inf), c["max_mm"])
        self.assertEqual(G.cage_offset(100.0), c["max_mm"])
        self.assertAlmostEqual(G.cage_offset(2.0), c["share"] * 2.0)
        self.assertAlmostEqual(G.cage_offset(0.6), c["min_mm"])  # the floor, at exactly half the gap
        self.assertEqual(G.cage_offset(0.7), c["min_mm"])
        self.assertLess(G.cage_offset(1.0), 1.0)  # never past the middle of a gap
        self.assertLess(c["max_mm"], c["ray_mm"])

    def test_narrow_gaps(self):
        # below 2 * min_mm the floor gives way to half the gap: the rays never start past its middle
        self.assertAlmostEqual(G.cage_offset(0.2), 0.1)
        self.assertAlmostEqual(G.cage_offset(0.5), 0.25)
        for clr in (0.05, 0.2, 0.5, 0.59, 0.6, 1.0, 3.0, 10.0):
            self.assertLessEqual(G.cage_offset(clr), 0.5 * clr + 1e-12)


class ImageCheckTest(unittest.TestCase):
    """The export's check that only the skin and the flipbook mouths reference images."""

    @staticmethod
    def gltf(materials):
        return {"images": [{"name": "albedo"}, {"name": "normal"}, {"name": "mouth_flip_frog"}],
                "textures": [{"source": 0}, {"source": 1}, {"source": 2}], "materials": materials}

    def test_allowed(self):
        g = self.gltf([
            {"name": "alien_hue", "normalTexture": {"index": 1},
             "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}}},
            {"name": "alien_mouth_flip_frog", "pbrMetallicRoughness": {"baseColorTexture": {"index": 2}}},
            {"name": "alien_hue_part", "pbrMetallicRoughness": {"baseColorFactor": [1, 1, 1, 1]}},
        ])
        self.assertEqual(G.unexpected_images(g), {})
        self.assertEqual(G.image_materials(g), {"alien_hue": ["albedo", "normal"],
                                                "alien_mouth_flip_frog": ["mouth_flip_frog"]})

    def test_part_with_a_normal_map_fails(self):
        g = self.gltf([{"name": "alien_hue_part", "normalTexture": {"index": 1}}])
        self.assertEqual(G.unexpected_images(g), {"alien_hue_part": ["normal"]})

    def test_extension_textures_count(self):
        g = self.gltf([{"name": "alien_lip", "extensions": {"KHR_materials_sheen": {"sheenColorTexture": {"index": 0}}}}])
        self.assertEqual(G.unexpected_images(g), {"alien_lip": ["albedo"]})


if __name__ == "__main__":
    unittest.main()
