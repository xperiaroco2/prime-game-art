"""The energy crystal's committed asset (art#263's station props): the manifest, the GLB's size, budget, surfaces and
UVs, the report and the material files, read without Blender or Godot. Skips the GLB checks in a checkout without
its LFS files."""

from __future__ import annotations

import hashlib
import json
import re
import struct
import unittest

from runner import common
from runner.commands import _manifest

ASSET = common.ROOT / "assets" / "prop" / "energy_crystal"
EXPORT = ASSET / "export"
HERO_TRIANGLES = 4000  # docs/props.md: the hero class, pieces players look at up close
SURFACES = {"crystal_shell", "crystal_core", "crystal_bronze", "crystal_graphite", "crystal_light"}
MATERIAL_FILES = ("crystal.gd", "crystal_shell.gdshader", "crystal_core.gdshader", "crystal_metal.gdshader")


def lfs_pointer(path) -> bool:
    return path.read_bytes()[:40].startswith(b"version https://git-lfs")


def glb_json(path) -> dict:
    """The GLB's JSON chunk (the first chunk after the 12-byte header)."""
    data = path.read_bytes()
    magic, _, _ = struct.unpack("<4sII", data[:12])
    assert magic == b"glTF", path
    length, kind = struct.unpack("<I4s", data[12:20])
    assert kind == b"JSON", path
    return json.loads(data[20:20 + length])


class EnergyCrystalAsset(unittest.TestCase):
    def test_manifest_is_valid(self) -> None:
        data, problem = _manifest.load(ASSET / "manifest.toml")
        self.assertIsNotNone(data, problem)
        self.assertEqual(data["id"], "energy_crystal")
        self.assertEqual(data["kind"], "prop")
        self.assertFalse(data["ai_generated"])  # built from code in Blender: no generator touched it
        self.assertEqual(data["licence"], "own-work")
        self.assertEqual(_manifest.validate(data, "prop", "energy_crystal"), [])

    def test_glb_size_budget_and_surfaces(self) -> None:
        glb = EXPORT / "energy_crystal.glb"
        if lfs_pointer(glb):
            self.skipTest("LFS file not fetched")
        doc = glb_json(glb)
        self.assertEqual(len(doc["meshes"]), 1)
        prims = doc["meshes"][0]["primitives"]
        names = {doc["materials"][p["material"]]["name"] for p in prims}
        self.assertEqual(names, SURFACES)  # crystal.gd finds its surfaces by these names
        tris = sum(doc["accessors"][p["indices"]]["count"] // 3 for p in prims)
        self.assertLessEqual(tris, HERO_TRIANGLES)
        lo = [min(doc["accessors"][p["attributes"]["POSITION"]]["min"][i] for p in prims) for i in range(3)]
        hi = [max(doc["accessors"][p["attributes"]["POSITION"]]["max"][i] for p in prims) for i in range(3)]
        self.assertAlmostEqual(hi[1], 0.349, delta=0.002)  # glTF is Y-up: the drawing's 34.9 cm to the loop's top
        self.assertTrue(0.0 <= lo[1] < 0.004, lo[1])  # the origin at the drawing's tip; the chamfer blunts the point
        for axis in (0, 2):  # centred
            self.assertAlmostEqual((hi[axis] + lo[axis]) / 2, 0.0, delta=0.002)
        for p in prims:  # UV0 carries the chamfer flag and the facet value the shaders read
            self.assertIn("TEXCOORD_0", p["attributes"])
        self.assertNotIn("images", doc)  # no textures

    def test_shipped_glb_is_the_recorded_build(self) -> None:
        glb = EXPORT / "energy_crystal.glb"
        if lfs_pointer(glb):
            self.skipTest("LFS file not fetched")
        data, _ = _manifest.load(ASSET / "manifest.toml")
        recorded = {r["file"]: r["sha256"] for r in data["raw"]}
        built = next(sha for name, sha in recorded.items() if name.endswith("/energy_crystal.glb"))  # <tag>/
        self.assertEqual(hashlib.sha256(glb.read_bytes()).hexdigest(), built)

    def test_report_records_a_clean_validation(self) -> None:
        report = json.loads((ASSET / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["gltf_validator"]["numErrors"], 0)
        self.assertEqual(report["gltf_validator"]["numWarnings"], 0)
        self.assertLessEqual(report["mesh"]["triangles"], HERO_TRIANGLES)
        self.assertEqual(report["mesh"]["budget_class"], "hero")
        glb = EXPORT / "energy_crystal.glb"
        if not lfs_pointer(glb):
            doc = glb_json(glb)
            prims = doc["meshes"][0]["primitives"]
            self.assertEqual(report["mesh"]["triangles"],
                             sum(doc["accessors"][p["indices"]]["count"] // 3 for p in prims))

    def test_material_files_ship_together(self) -> None:
        for name in MATERIAL_FILES:
            self.assertTrue((EXPORT / name).is_file(), name)
            # the copies shipped are the repo's own, so the shots tested what ships
            self.assertEqual((EXPORT / name).read_bytes(), (common.ROOT / "godot" / "crystal" / name).read_bytes(),
                             name)
        script = (EXPORT / "crystal.gd").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r'^const \w+ := preload\("([^"]+)"\)', script, re.M),  # the usage comment too has one
                         ["crystal_shell.gdshader", "crystal_core.gdshader", "crystal_metal.gdshader"])
        for name in SURFACES:  # the script maps every surface the GLB has
            self.assertIn(f'"{name}"', script)


if __name__ == "__main__":
    unittest.main()
