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
        s = dict(G.M3A, hue_sat=1.0, pale_sat=1.0)
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
        """M3a: the narrowed edge; below it no grey fringe."""
        flat = G.albedo(field(), G.M3A)
        self.assertEqual(G.albedo(field(accent=0.15), G.M3A), flat)
        full = G.albedo(field(accent=1.0), G.M3A)
        self.assertGreater(full[0], 3 * flat[0])  # coral

    def test_accent_edge_is_soft_and_never_grey(self):
        """M3c: the kit's whole soft edge, red rising steadily, and the half-way texel keeps more chroma than the plain
        mix (no dusty band)."""
        reds = [G.albedo(field(accent=a))[0] for a in (0.0, 0.15, 0.3, 0.5, 0.7, 1.0)]
        self.assertEqual(reds, sorted(reds))
        self.assertGreater(reds[1], reds[0])
        plain = dict(G.TEX, accent_keep=0.0)
        self.assertGreater(G.chroma(G.albedo(field(accent=0.5))), G.chroma(G.albedo(field(accent=0.5), plain)))

    def test_concave_darker_and_bluer_convex_paler(self):
        flat = G.albedo(field())
        cave = G.albedo(field(curv=0.3))
        bump = G.albedo(field(curv=0.7))
        self.assertLess(lum(cave), lum(flat))
        self.assertGreater(cave[2] / cave[0], flat[2] / flat[0])  # bluer
        self.assertGreater(lum(bump), lum(flat))

    def test_ao_scales_the_albedo_by_its_strength(self):
        """A closed AO texel keeps 1 - `ao` of the albedo (M3a 0.5, M3c 0.4; the contact lift leaves 0 at 0)."""
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


class M3cTest(unittest.TestCase):
    """M3c's tuning helpers: the contact AO, the accent's chroma, the texture's own pale."""

    def test_contact_ao_only_lifts(self):
        s = dict(G.TEX, contact=0.0, socket_contact=1.0, contact_hi=0.6)
        for ao in (0.0, 0.2, 0.5, 0.6, 0.9, 1.0):
            self.assertEqual(G.contact_ao(ao, 0.0, s), ao)  # outside the sockets: unchanged
            lifted = G.contact_ao(ao, 1.0, s)
            self.assertGreaterEqual(lifted, ao)
            self.assertLessEqual(lifted, 1.0)
        self.assertEqual(G.contact_ao(0.0, 1.0, s), 0.0)  # the contact itself stays dark
        self.assertEqual(G.contact_ao(0.7, 1.0, s), 1.0)  # the wide ring goes
        self.assertAlmostEqual(G.contact_ao(0.3, 0.5, s), 0.3 + (0.5 - 0.3) * 0.5)

    def test_contact_everywhere(self):
        s = dict(G.TEX, contact=0.5, socket_contact=0.0, contact_hi=0.5)
        self.assertAlmostEqual(G.contact_ao(0.25, 0.0, s), 0.375)
        s["socket_contact"] = 1.0
        self.assertAlmostEqual(G.contact_ao(0.25, 1.0, s), 0.5)  # the weights add up to at most 1

    def test_socket_lifts_the_albedo(self):
        s = dict(G.TEX, socket_contact=1.0, socket_cavity=1.0, contact_hi=0.6)
        ring = field(ao=0.6, curv=0.4)
        self.assertGreater(lum(G.albedo(dict(ring, socket=1.0), s)), lum(G.albedo(ring, s)))
        self.assertAlmostEqual(lum(G.albedo(dict(ring, socket=1.0), s)), lum(G.albedo(field(), s)), places=6)

    def test_keep_chroma(self):
        teal, coral = G.lin3(G.TEAL_SRGB), G.lin3(G.ACCENT_SRGB)
        t = 0.5
        mixed = [G.mix(a, b, t) for a, b in zip(teal, coral)]
        kept = G.keep_chroma(mixed, teal, coral, t, 1.0)
        self.assertGreater(G.chroma(kept), G.chroma(mixed))
        self.assertAlmostEqual(lum(kept), lum(mixed), places=6)  # about its own luminance
        self.assertLessEqual(G.chroma(kept), 2.0 * G.chroma(mixed) + 1e-9)  # the cap
        self.assertEqual(G.keep_chroma(mixed, teal, coral, t, 0.0), tuple(mixed))  # k 0: the plain mix
        same = G.keep_chroma(list(teal), teal, coral, 0.0, 1.0)  # t 0: the skin unchanged
        for a, b in zip(same, teal):
            self.assertAlmostEqual(a, b, places=4)

    def test_chosen_pale_is_mint(self):
        """The chosen pale is greener than red and its blue near its red (rf2's mint), never yellow-olive."""
        p = G.TEX["pale_srgb"]
        self.assertGreater(p[1] - p[0], 0.08)
        self.assertGreaterEqual(p[2], p[0] - 0.02)
        pale = [G.linear_to_srgb(c) for c in G.albedo(field(light=1.0, face=1.0), G.TEX)]
        self.assertGreater(pale[1] - pale[0], 0.05)

    def test_chosen_roughness_is_soft(self):
        """rf2's soft sheen: the skin's base roughness 0.65..0.75 (M3a's 0.52 read as an orange peel at 0.6 m)."""
        self.assertGreaterEqual(G.TEX["rough"], 0.65)
        self.assertLessEqual(G.TEX["rough"], 0.75)
        self.assertGreaterEqual(G.roughness(field(curv=0.7)), 0.6)


class SetTest(unittest.TestCase):
    """The texture sets (alien_texture.py --set): M3C only changes M3A's keys, and M3A still gives the shipped M3a
    set's numbers (golden values from main's alien_texture_geom.TEX at eaf3ee9, PR #233)."""

    GOLDEN = (  # (fields over FLAT, linear albedo, roughness) under M3A
        ({}, (0.001, 0.2015761, 0.2331089), 0.52),
        (dict(light=1.0, face=1.0, ao=0.6, flush=0.5), (0.4869792, 0.6075353, 0.3592964), 0.52),
        (dict(accent=0.5, curv=0.3, hue=0.7, blotch=-0.4), (0.2630038, 0.138205, 0.1386884), 0.58),
        (dict(deep=0.8, thick=0.2, warm=1.0, curv=0.62, tzone=0.2, mouth=0.1, fine=-0.5, pore=0.4, socket=1.0),
         (0.0007714, 0.1748964, 0.1949269), 0.4005),
    )

    def test_m3c_changes_only_m3a_keys(self):
        self.assertLessEqual(set(G.M3C), set(G.M3A))
        self.assertEqual(G.SETS["m3a"], G.M3A)
        self.assertEqual(G.SETS["m3c"], {**G.M3A, **G.M3C})

    def test_m3a_is_pinned(self):
        for over, alb, rough in self.GOLDEN:
            f = field(**over)
            for a, b in zip(G.albedo(f, G.M3A), alb):
                self.assertAlmostEqual(a, b, places=6)
            self.assertAlmostEqual(G.roughness(f, G.M3A), rough, places=6)

    def test_settings_diff(self):
        self.assertEqual(G.settings_diff(G.M3A, dict(G.M3A)), [])
        recorded = {k: list(v) if isinstance(v, tuple) else v for k, v in G.M3A.items()}  # as settings.json holds it
        self.assertEqual(G.settings_diff(recorded, G.M3A), [])
        old = {k: v for k, v in G.M3A.items() if k not in G.M3C}  # M3a's settings.json: before M3c's keys
        self.assertEqual(G.settings_diff(old, G.M3A), [])
        self.assertEqual(G.settings_diff(old, G.SETS["m3c"]), sorted(k for k in G.M3C if G.M3C[k] != G.M3A[k]))


    def test_note_from_the_settings(self):
        m3a, m3c = G.texture_note("m3a", G.SETS["m3a"]), G.texture_note("m3c", G.SETS["m3c"])
        self.assertIn("art #196 M3A:", m3a)
        self.assertIn("and 0.5 of the AO baked in)", m3a)
        self.assertNotIn("contact", m3a)
        self.assertIn("roughness about 0.52", m3a)
        self.assertIn("0.4 of the AO baked in (the AO lifted toward its contact shade, ao / 0.55: by 0.45 everywhere, "
                      "fully round the eyes)", m3c)
        self.assertIn("blurred (32 texels at 4K)", m3c)
        self.assertIn("roughness about 0.66", m3c)


class RoughnessTest(unittest.TestCase):
    def test_base_and_gloss(self):
        self.assertAlmostEqual(G.roughness(field()), G.TEX["rough"])
        self.assertLess(G.roughness(field(curv=0.8)), G.TEX["rough"])  # glossier convex
        self.assertLess(G.roughness(field(tzone=1.0), G.M3A), G.M3A["rough"])  # M3c: no T-zone
        self.assertLess(G.roughness(field(mouth=1.0)), G.TEX["rough"] - 0.1)
        self.assertGreater(G.roughness(field(curv=0.2)), G.TEX["rough"])  # rougher in the creases

    def test_clamped(self):
        lo = G.roughness(field(curv=1.0, tzone=1.0, mouth=1.0, fine=-1.0))
        hi = G.roughness(field(curv=0.0, fine=1.0, pore=1.0))
        self.assertGreaterEqual(lo, G.TEX["rough_min"])
        self.assertLessEqual(hi, G.TEX["rough_max"])


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

    def test_eyeballs_carry_their_image(self):  # M4: alien_eye_<design> has S9's 512 px eye image back
        g = self.gltf([{"name": "alien_eye_bored", "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}}},
                       {"name": "alien_eye_manic", "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}}},
                       {"name": "alien_wet", "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}}}])
        self.assertEqual(G.unexpected_images(g), {"alien_wet": ["albedo"]})

    def test_extension_textures_count(self):
        g = self.gltf([{"name": "alien_lip", "extensions": {"KHR_materials_sheen": {"sheenColorTexture": {"index": 0}}}}])
        self.assertEqual(G.unexpected_images(g), {"alien_lip": ["albedo"]})


if __name__ == "__main__":
    unittest.main()
