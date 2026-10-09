"""The textured export's checks, pure Python: the GLB texture audit and its problems (runner/commands/_export.py), the
textured godot-check (runner/commands/_godot.py, _textured), and the export options of export_glb.py --textured."""

from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

from runner import common
from runner.commands import _export, _godot

sys.path.insert(0, str(common.ROOT / "tools" / "blender"))
import export_glb  # noqa: E402


def png(w: int, h: int) -> bytes:
    """The first bytes of a PNG: the signature and the IHDR chunk (all the audit reads)."""
    return _export.PNG_MAGIC + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", w, h) + bytes(5) + bytes(4)


def write_glb(path: Path, gltf: dict, binary: bytes) -> None:
    js = json.dumps(gltf).encode("utf-8")
    js += b" " * (-len(js) % 4)
    binary += bytes(-len(binary) % 4)
    total = 12 + 8 + len(js) + 8 + len(binary)
    path.write_bytes(b"glTF" + struct.pack("<II", 2, total) + struct.pack("<II", len(js), _export.JSON_CHUNK) + js
                     + struct.pack("<II", len(binary), 0x004E4942) + binary)


def character(col_px: int = 512, nrm_px: int = 1024, normal: bool = True, tangent: bool = True, surfaces: int = 2) -> dict:
    a, b = png(col_px, col_px), png(nrm_px, nrm_px)
    gltf = {
        "asset": {"version": "2.0"},
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(a)},
                        {"buffer": 0, "byteOffset": len(a), "byteLength": len(b)}],
        "images": [{"name": "top_col", "mimeType": "image/png", "bufferView": 0},
                   {"name": "top_nrm", "mimeType": "image/png", "bufferView": 1}],
        "textures": [{"source": 0}, {"source": 1}],
        "materials": [{"name": "m1_top_clay", "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}},
                       **({"normalTexture": {"index": 1}} if normal else {})},
                      {"name": "eye_white"}],
        "meshes": [{"name": "top", "primitives": [
            {"attributes": {"POSITION": 0, "TEXCOORD_0": 1, **({"TANGENT": 2} if tangent else {})}, "material": 0}]
            + [{"attributes": {"POSITION": 0}, "material": 1}] * (surfaces - 1)}],
        "nodes": [{"name": "m1_top", "mesh": 0, "skin": 0}],
    }
    return {"gltf": gltf, "bin": a + b}


class Audit(unittest.TestCase):
    def audit(self, **kw) -> dict:
        c = character(**kw)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.glb"
            write_glb(path, c["gltf"], c["bin"])
            return _export.textured_audit(path)

    def test_reads_images_materials_surfaces(self) -> None:
        a = self.audit()
        self.assertEqual([i["px"] for i in a["images"]], [[512, 512], [1024, 1024]])
        self.assertEqual(a["materials"][0], {"name": "m1_top_clay", "base": 0, "normal": 1})
        self.assertEqual(a["surfaces"], 2)
        self.assertEqual(_export.textured_check(a, 8, 1024), [])

    def test_names_each_problem(self) -> None:
        self.assertIn("over 1024", " ".join(_export.textured_check(self.audit(nrm_px=2048), 8, 1024)))
        self.assertIn("without a normal map", " ".join(_export.textured_check(self.audit(normal=False), 8, 1024)))
        self.assertIn("without UVs and tangents", " ".join(_export.textured_check(self.audit(tangent=False), 8, 1024)))
        self.assertIn("over the contract's cap", " ".join(_export.textured_check(self.audit(surfaces=9), 8, 1024)))

    def test_jpeg_size(self) -> None:
        sof = b"\xff\xd8" + b"\xff\xe0" + struct.pack(">H", 4) + b"ab" + b"\xff\xc0" + struct.pack(">HBHH", 17, 8, 300, 200)
        self.assertEqual(_export.image_size(sof + bytes(10)), (200, 300))
        self.assertEqual(_export.image_size(b"nothing"), (0, 0))


class GodotTextured(unittest.TestCase):
    CONTRACT = {"budgets": {"limits": {"texture_character_px": 1024, "surfaces_per_character_cap": 8,
                                       "surfaces_per_character_target": 6}}}

    def checks(self, materials: list[dict], surfaces: int) -> dict[str, str]:
        c = _godot.Checks()
        _godot._textured(c, {"meshes": [{"name": "m1_top", "surfaces": surfaces, "materials": materials}]}, self.CONTRACT)
        return {i["check"]: i["status"] for i in c.items}

    def test_a_baked_character_passes(self) -> None:
        good = {"name": "clay", "textured": True, "normal_mapped": True, "albedo_px": [512, 512], "normal_px": [1024, 1024]}
        got = self.checks([good, {"name": "eye_white", "textured": False, "normal_mapped": False}], 2)
        self.assertEqual(set(got.values()), {"pass"}, got)

    def test_each_failure(self) -> None:
        bad = {"name": "clay", "textured": True, "normal_mapped": False, "albedo_px": [2048, 2048]}
        got = self.checks([bad], 9)
        self.assertEqual((got["normal_maps"], got["texture_size"], got["surfaces_cap"]), ("fail", "fail", "fail"))
        self.assertEqual(self.checks([{"name": "flat", "textured": False}], 1)["textured"], "fail")


class Options(unittest.TestCase):
    def test_textured_options(self) -> None:
        self.assertEqual(export_glb.options(), export_glb.EXPORT_OPTIONS)
        o = export_glb.options(textured=True)
        self.assertEqual((o["export_image_format"], o["export_tangents"], o["export_morph"]), ("AUTO", True, True))
        self.assertEqual(set(o), set(export_glb.EXPORT_OPTIONS) | set(export_glb.TEXTURED_OPTIONS))


if __name__ == "__main__":
    unittest.main()
