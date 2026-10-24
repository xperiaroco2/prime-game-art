"""The start console's committed asset (art#263's stations): the drawing's numbers in console_dims.toml, the
manifest, the GLB's size, surfaces and UVs, the report and the look's files, read without Blender or Godot. Skips
the GLB checks in a checkout without its LFS files."""

from __future__ import annotations

import hashlib
import json
import struct
import tomllib
import unittest

from runner import common
from runner.commands import _manifest

ASSET = common.ROOT / "assets" / "prop" / "start_console"
EXPORT = ASSET / "export"
DIMS = common.ROOT / "tools" / "blender" / "console_dims.toml"
TRIANGLES = 60000  # the whole console: 55,661 at build2, the hologram's lines and shell 44k of them (0.14 ms GPU)
SURFACES = {"console_bronze", "console_graphite", "console_cyan", "console_button", "console_stage", "console_lamp",
            "console_holo_line", "console_holo_shell", "console_beam"}
MATERIAL_FILES = ("console.gd", "console_metal.gdshader", "console_signal.gdshader", "console_holo.gdshader")


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


class StartConsoleDrawing(unittest.TestCase):
    def test_dims_keep_the_drawings_numbers(self) -> None:
        # prime-game-design stations-final/console-drawing/drawing.js (node: its N object), the engineer's sizes
        d = tomllib.loads(DIMS.read_text(encoding="utf-8"))
        self.assertAlmostEqual(d["plinth"]["r_top"] * 2, 120.0, delta=0.1)
        self.assertAlmostEqual(d["plinth"]["h_top"], 15.25, delta=0.05)
        self.assertAlmostEqual(d["body"]["r_bottom"] * 2, 110.8, delta=0.1)
        self.assertAlmostEqual(d["body"]["r_top"] * 2, 105.2, delta=0.1)
        self.assertAlmostEqual(d["body"]["h0"], 19.67, delta=0.05)
        self.assertAlmostEqual(d["body"]["h1"], 91.64, delta=0.05)
        self.assertAlmostEqual(d["rim"]["r"] * 2, 111.5, delta=0.1)
        self.assertAlmostEqual(d["rim"]["r_top"] * 2, 103.3, delta=0.1)
        self.assertAlmostEqual(d["rim"]["h0"], 93.28, delta=0.05)
        self.assertAlmostEqual(d["rim"]["h1"], 109.34, delta=0.05)
        self.assertAlmostEqual(d["button"]["h"], 81.4, delta=0.05)  # the drawing's 85.41, lowered 4 cm on review
        self.assertAlmostEqual(d["button"]["collar"], 15.57, delta=0.05)
        self.assertAlmostEqual(d["button"]["proud"], 4.42, delta=0.05)
        self.assertEqual(len(d["strips"]["u"]), 3)
        self.assertAlmostEqual(d["emitter"]["ring"], 82.78, delta=0.05)
        self.assertAlmostEqual(d["emitter"]["core"], 19.75, delta=0.05)
        self.assertAlmostEqual(d["hologram"]["span"], 159.84, delta=0.05)
        self.assertAlmostEqual(d["hologram"]["disc_h"], 145.74, delta=0.05)
        self.assertEqual(d["hologram"]["tilt"], 12.0)
        self.assertEqual(d["measure"]["lift"], 40.0)


class StartConsoleAsset(unittest.TestCase):
    def test_manifest_is_valid(self) -> None:
        data, problem = _manifest.load(ASSET / "manifest.toml")
        self.assertIsNotNone(data, problem)
        self.assertEqual(data["id"], "start_console")
        self.assertEqual(data["kind"], "prop")
        self.assertFalse(data["ai_generated"])  # built from code in Blender: no generator touched it
        self.assertEqual(data["licence"], "own-work")
        self.assertEqual(_manifest.validate(data, "prop", "start_console"), [])

    def test_glb_size_surfaces_and_uvs(self) -> None:
        glb = EXPORT / "start_console.glb"
        if lfs_pointer(glb):
            self.skipTest("LFS file not fetched")
        doc = glb_json(glb)
        self.assertEqual(len(doc["meshes"]), 1)
        prims = doc["meshes"][0]["primitives"]
        names = {doc["materials"][p["material"]]["name"] for p in prims}
        self.assertEqual(names, SURFACES)  # console.gd finds its surfaces by these names
        tris = sum(doc["accessors"][p["indices"]]["count"] // 3 for p in prims)
        self.assertLessEqual(tris, TRIANGLES)
        lo = [min(doc["accessors"][p["attributes"]["POSITION"]]["min"][i] for p in prims) for i in range(3)]
        hi = [max(doc["accessors"][p["attributes"]["POSITION"]]["max"][i] for p in prims) for i in range(3)]
        self.assertAlmostEqual(lo[1], 0.0, delta=0.001)  # glTF is Y-up: the origin on the floor
        self.assertAlmostEqual(hi[0] - lo[0], 1.598, delta=0.03)  # the hologram's span, the drawing's 159.8 cm
        self.assertTrue(1.65 < hi[1] < 1.85, hi[1])  # the hologram's top over the rim's 1.093 m
        for p in prims:  # UV0 carries the chamfer flag and the index or brightness the shaders read
            self.assertIn("TEXCOORD_0", p["attributes"])
        self.assertNotIn("images", doc)  # no textures

    def test_shipped_glb_is_the_recorded_build(self) -> None:
        glb = EXPORT / "start_console.glb"
        if lfs_pointer(glb):
            self.skipTest("LFS file not fetched")
        data, _ = _manifest.load(ASSET / "manifest.toml")
        recorded = {r["file"]: r["sha256"] for r in data["raw"]}
        built = next(sha for name, sha in recorded.items() if name.endswith("/start_console.glb"))  # <tag>/
        self.assertEqual(hashlib.sha256(glb.read_bytes()).hexdigest(), built)

    def test_report_records_a_clean_validation_and_the_size(self) -> None:
        report = json.loads((ASSET / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["gltf_validator"]["numErrors"], 0)
        self.assertEqual(report["gltf_validator"]["numWarnings"], 0)
        ped = report["mesh"]["pedestal_size_m"]  # Blender axes: x, y, z
        self.assertAlmostEqual(ped[0], 1.20, delta=0.01)
        self.assertAlmostEqual(ped[2], 1.105, delta=0.01)  # the emitter's collar, a little over the rim's 109.3
        self.assertEqual(report["mesh"]["hologram"]["lamps"], 8)

    def test_shipped_look_matches_the_godot_files(self) -> None:
        for name in MATERIAL_FILES:
            shipped = (EXPORT / name).read_text(encoding="utf-8")
            self.assertEqual(shipped, (common.ROOT / "godot" / "console" / name).read_text(encoding="utf-8"), name)
        look = (EXPORT / "console.gd").read_text(encoding="utf-8")
        for surface in SURFACES:  # every surface has its material in the look
            self.assertIn(f'"{surface}"', look)


if __name__ == "__main__":
    unittest.main()
