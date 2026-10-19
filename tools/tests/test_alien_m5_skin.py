"""M5's textured alien skin (art #196, the PR #236 review): godot/alien/alien.gd SKIN_TEX and SSS_MARKER against
alien_hue.gdshader's uniforms, the shader's texture hue against alien_texture_geom's colours, and
tools/blender/alien_eyes_geom.py's SSS mask route (the ORM's B: the 2x upscale and the GLB check). Plain Python: the
modules are read without Blender, the GDScript and the shader by pattern."""
from __future__ import annotations

import importlib.util
import json
import re
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GD = ROOT / "godot" / "alien" / "alien.gd"
SHADER = ROOT / "godot" / "alien" / "alien_hue.gdshader"
NUM = r"-?\d+(?:\.\d+)?"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / "blender" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def srgb_to_linear(c: float) -> float:  # Godot's Color.srgb_to_linear()
    return c / 12.92 if c < 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def gd_dict(text: str, name: str) -> dict:
    m = re.search(rf"^const {name} := \{{(.*?)^\}}", text, re.M | re.S)
    if m is None:
        raise AssertionError(f"alien.gd has no const {name}")
    body = re.sub(r"#[^\n]*", "", m.group(1))
    return {k: v.strip() for k, v in re.findall(r'"(\w+)":\s*([^,]+)', body)}


def glb(gltf: dict, images: list[bytes]) -> bytes:
    """A minimal GLB: the JSON chunk (with images as buffer views) and one BIN chunk."""
    bin_ = b""
    views = []
    for data in images:
        views.append({"buffer": 0, "byteOffset": len(bin_), "byteLength": len(data)})
        bin_ += data + b"\0" * (-len(data) % 4)
    g = dict(gltf, bufferViews=views, buffers=[{"byteLength": len(bin_)}],
             images=[{"bufferView": i, "mimeType": "image/png"} for i in range(len(images))],
             textures=[{"source": i} for i in range(len(images))])
    js = json.dumps(g).encode()
    js += b" " * (-len(js) % 4)
    body = struct.pack("<I4s", len(js), b"JSON") + js + struct.pack("<I4s", len(bin_), b"BIN\0") + bin_
    return struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body


class SkinTex(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gd = GD.read_text(encoding="utf-8")
        cls.sh = SHADER.read_text(encoding="utf-8")
        cls.uniforms = set(re.findall(r"^(?:instance )?uniform \w+ (\w+)", cls.sh, re.M))
        cls.e = load("alien_eyes_geom")
        cls.t = load("alien_texture_geom")

    def vec3_default(self, uniform: str) -> tuple:
        m = re.search(rf"^uniform vec3 {uniform}\b[^=]*= vec3\(({NUM}), ({NUM}), ({NUM})\);", self.sh, re.M)
        self.assertIsNotNone(m, f"the shader has no vec3 default for {uniform}")
        return tuple(float(x) for x in m.groups())

    def test_tex_hue_and_pale_are_the_texture_colours_linear(self):
        for uniform, srgb in (("tex_hue", self.t.TEAL_SRGB), ("tex_pale", self.t.PALE_SRGB)):
            with self.subTest(uniform=uniform):
                for got, want in zip(self.vec3_default(uniform), (srgb_to_linear(c) for c in srgb)):
                    self.assertAlmostEqual(got, want, delta=2e-4)

    def test_alien_gd_teal_is_the_texture_teal(self):  # alien.gd sets tex_hue and tex_pale from HUES["teal"]
        m = re.search(rf'"teal": \[Color\(({NUM}), ({NUM}), ({NUM})\), Color\(({NUM}), ({NUM}), ({NUM})\)\]', self.gd)
        self.assertIsNotNone(m)
        vals = tuple(float(x) for x in m.groups())
        self.assertEqual(vals[:3], self.t.TEAL_SRGB)
        self.assertEqual(vals[3:], self.t.PALE_SRGB)

    def test_every_skin_tex_key_is_a_uniform(self):
        for k in gd_dict(self.gd, "SKIN_TEX"):
            with self.subTest(key=k):
                self.assertIn(k, self.uniforms)
        shared = re.search(r"^const SKIN_TEX_SHARED := \[([^\]]*)\]", self.gd, re.M)
        self.assertIsNotNone(shared)
        keys = re.findall(r'"(\w+)"', shared.group(1))
        self.assertTrue(keys)
        tex = gd_dict(self.gd, "SKIN_TEX")
        for k in keys:
            with self.subTest(shared=k):
                self.assertIn(k, tex)
                self.assertIn(k, self.uniforms)

    def test_sss_marker_matches_the_build(self):
        m = re.search(r'^const SSS_MARKER := \{"(\w+)": "(\w+)"\}', self.gd, re.M)
        self.assertIsNotNone(m)
        self.assertEqual({m.group(1): m.group(2)}, self.e.SSS_MARKER)

    def test_mask_comes_from_the_orm_blue(self):
        self.assertIn("float mask = orm.b;", self.sh)
        self.assertNotRegex(self.sh, r"\bt\.a\b")


class Upscale2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e = load("alien_eyes_geom")

    def test_taps_sum_to_one(self):
        self.assertAlmostEqual(sum(w for _, _, w in self.e.UPSCALE2_TAPS), 1.0)

    def test_constant_stays_constant(self):
        up = self.e.upscale2([[0.3] * 4 for _ in range(3)])
        self.assertEqual((len(up), len(up[0])), (6, 8))
        for row in up:
            for v in row:
                self.assertAlmostEqual(v, 0.3)

    def test_ramp_is_bilinear_at_quarter_texels(self):
        # source texel x sits at output coordinate 2x + 0.5; output texel X samples source x = (X - 0.5) / 2
        grid = [[float(x) for x in range(6)] for _ in range(4)]
        up = self.e.upscale2(grid)
        for X in range(1, 11):  # inside the edges
            self.assertAlmostEqual(up[3][X], (X - 0.5) / 2.0, msg=f"X {X}")

    def test_edges_clamp(self):
        up = self.e.upscale2([[0.0, 1.0]])
        self.assertAlmostEqual(up[0][0], 0.0)
        self.assertAlmostEqual(up[0][3], 1.0)
        self.assertAlmostEqual(up[0][1], 0.25)
        self.assertAlmostEqual(up[0][2], 0.75)


class SssOrmRoute(unittest.TestCase):
    ORM = b"\x89PNG\r\n\x1a\n" + b"orm with the mask in B"

    @classmethod
    def setUpClass(cls):
        cls.e = load("alien_eyes_geom")

    def material(self, **kw) -> dict:
        m = {"name": "alien_hue", "occlusionTexture": {"index": 1}, "extras": dict(self.e.SSS_MARKER),
             "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}, "metallicRoughnessTexture": {"index": 1},
                                      "metallicFactor": 0}}
        m.update(kw)
        return m

    def check(self, m: dict, orm: bytes | None = None) -> list[str]:
        b = glb({"materials": [m]}, [b"\x89PNG albedo", orm or self.ORM])
        return self.e.sss_orm_problems(b, "alien_hue", self.ORM)

    def test_good(self):
        self.assertEqual(self.check(self.material()), [])
        self.assertEqual(self.e.glb_texture_png(glb({"materials": [self.material()]}, [b"a", self.ORM]),
                                                "alien_hue", "metallicRoughnessTexture"), self.ORM)

    def test_metallic_factor_must_be_zero(self):
        m = self.material()
        del m["pbrMetallicRoughness"]["metallicFactor"]  # glTF's default is 1: a metal skin in plain viewers
        self.assertIn("metallicFactor is not 0", self.check(m))

    def test_rebuilt_image_is_caught(self):  # the exporter's unhappy path rebuilds the image without B
        bad = self.check(self.material(), orm=b"\x89PNG rebuilt")
        self.assertIn("metallicRoughnessTexture is not the ORM with the mask", bad)
        self.assertIn("occlusionTexture is not the ORM with the mask", bad)

    def test_marker_required(self):
        self.assertTrue(any("extras" in p for p in self.check(self.material(extras={}))))

    def test_missing_material(self):
        self.assertEqual(self.e.sss_orm_problems(glb({"materials": []}, [b"a"]), "alien_hue", self.ORM),
                         ["no material alien_hue"])


if __name__ == "__main__":
    unittest.main()
