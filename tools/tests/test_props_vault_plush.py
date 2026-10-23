"""The vault plush's committed asset (art#297): the manifest, the GLB's size, budget and maps, the mask, the report
and the material files, read without Blender or Godot. Skips the GLB checks in a checkout without its LFS files."""

from __future__ import annotations

import json
import re
import struct
import unittest
from pathlib import Path

from runner import common
from runner.commands import _manifest

ASSET = common.ROOT / "assets" / "prop" / "vault_plush"
EXPORT = ASSET / "export"
HERO_TRIANGLES = 4000  # docs/props.md: the hero class, pieces players look at up close


def lfs_pointer(path: Path) -> bool:
    return path.read_bytes()[:40].startswith(b"version https://git-lfs")


def glb_json(path: Path) -> tuple[dict, bytes]:
    data = path.read_bytes()
    magic, _, _ = struct.unpack("<4sII", data[:12])
    assert magic == b"glTF", path
    json_len = struct.unpack("<I", data[12:16])[0]
    doc = json.loads(data[20:20 + json_len])
    bin_start = 20 + json_len + 8
    return doc, data[bin_start:]


def png_size(data: bytes) -> tuple[int, int]:
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


class VaultPlushAsset(unittest.TestCase):
    def test_manifest_is_valid(self) -> None:
        data, problem = _manifest.load(ASSET / "manifest.toml")
        self.assertIsNotNone(data, problem)
        self.assertEqual(data["id"], "vault_plush")
        self.assertEqual(data["kind"], "prop")
        self.assertTrue(data["ai_generated"])
        self.assertEqual(_manifest.validate(data, "prop", "vault_plush"), [])

    def test_glb_size_budget_and_maps(self) -> None:
        glb = EXPORT / "vault_plush.glb"
        if lfs_pointer(glb):
            self.skipTest("LFS file not fetched")
        doc, binary = glb_json(glb)
        self.assertEqual(len(doc["meshes"]), 1)
        prim = doc["meshes"][0]["primitives"][0]
        pos = doc["accessors"][prim["attributes"]["POSITION"]]
        tris = doc["accessors"][prim["indices"]]["count"] // 3
        self.assertLessEqual(tris, HERO_TRIANGLES)
        self.assertGreater(tris, HERO_TRIANGLES * 0.9)
        lo, hi = pos["min"], pos["max"]
        self.assertAlmostEqual(hi[1] - lo[1], 0.30, delta=0.01)  # glTF is Y-up: 0.30 m tall
        self.assertAlmostEqual(lo[1], 0.0, delta=0.001)  # on the floor
        for axis in (0, 2):  # the footprint centred
            self.assertAlmostEqual((hi[axis] + lo[axis]) / 2, 0.0, delta=0.005)
        self.assertIn("TANGENT", prim["attributes"])  # the normal map needs them
        self.assertEqual(doc["materials"][0]["name"], "vault_plush")
        sizes = []
        for image in doc["images"]:
            view = doc["bufferViews"][image["bufferView"]]
            start = view.get("byteOffset", 0)
            sizes.append(png_size(binary[start:start + 24]))
        self.assertEqual(sorted(sizes), [(1024, 1024), (1024, 1024)])

    def test_mask_is_1024(self) -> None:
        mask = EXPORT / "vault_plush_mask.png"
        if lfs_pointer(mask):
            self.skipTest("LFS file not fetched")
        self.assertEqual(png_size(mask.read_bytes()[:24]), (1024, 1024))

    def test_report_records_a_clean_validation(self) -> None:
        report = json.loads((ASSET / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["gltf_validator"]["numErrors"], 0)
        self.assertEqual(report["gltf_validator"]["numWarnings"], 0)
        self.assertLessEqual(report["mesh"]["triangles"], HERO_TRIANGLES)

    def test_material_files_ship_together(self) -> None:
        for name in ("plush.gd", "plush.gdshader", "plush_shell.gdshader"):
            self.assertTrue((EXPORT / name).is_file(), name)
            # the copies shipped are the repo's own, so the shots tested what ships
            self.assertEqual((EXPORT / name).read_bytes(), (common.ROOT / "godot" / "plush" / name).read_bytes(), name)
        script = (EXPORT / "plush.gd").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r'preload\("([^"]+)"\)', script), ["plush.gdshader", "plush_shell.gdshader"])


if __name__ == "__main__":
    unittest.main()
