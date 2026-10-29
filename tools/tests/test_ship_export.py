"""The ship's game-ready package (`ship --export DIR`, art #335, docs/ship.md "The export"): the station spots with
the game's names and facings, the paths moved from the art project to the package, nothing a game asset may not hold,
and the package's files. Pure Python; the last test reads a written package when the raw folder has one (else it
skips)."""

from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from runner import common, ship_export as X, ship_layout as sl

LAYOUT = sl.load()
PACKAGE = common.raw_dir() / LAYOUT["raw_dir"] / "export" / "v1"
SCENE_TEXT = """[gd_scene load_steps=4 format=3 uid="uid://b1abc"]

[ext_resource type="PackedScene" uid="uid://c2def" path="res://import/ship_hall_floor.glb" id="1_a"]
[ext_resource type="Shader" path="res://ship/metal.gdshader" id="2_b"]
[ext_resource type="Material" uid="uid://d3" path="res://import/ship_export/metal_hull_silver.tres" id="3_c"]

[node name="Ship" type="Node3D"]
"""


class StationsTest(unittest.TestCase):
    def test_every_spot_has_a_name_a_package_and_a_facing(self) -> None:
        spots = X.stations(LAYOUT)
        self.assertEqual(len(spots), len(LAYOUT["stations"]["spot"]))
        self.assertEqual(len({s["name"] for s in spots}), len(spots))
        by = {s["spot"]: s for s in spots}
        self.assertEqual(by["console"]["name"], "Console")
        self.assertEqual(by["console"]["package"], "start_console")
        self.assertEqual(by["console"]["yaw"], 180.0)
        self.assertEqual(by["socket_fw"]["name"], "SocketFW")
        self.assertEqual(by["vent_e"]["package"], "ship:th_wall_e")
        self.assertEqual(by["renewer_w"]["package"], "crystal_charger")
        self.assertEqual(by["breaker_e"]["package"], "breaker_board")

    def test_a_wall_spot_faces_its_normal_on_the_deck(self) -> None:
        floor = LAYOUT["deck"]["floor_h"]
        for s, spot in zip(X.stations(LAYOUT), LAYOUT["stations"]["spot"]):
            self.assertEqual(s["at"][1], floor)
            if "normal" in spot:  # +Z turned by yaw about Y is (sin, cos): the normal (plan x, y = Godot x, z)
                yaw = math.radians(s["yaw"])
                self.assertAlmostEqual(math.sin(yaw), spot["normal"][0], places=3)
                self.assertAlmostEqual(math.cos(yaw), spot["normal"][1], places=3)

    def test_the_vents_spots_agree_with_their_pieces_placement(self) -> None:
        place = {pid: yaw for pid, _at, yaw in LAYOUT["place"]}
        for s in X.stations(LAYOUT):
            if s["kind"] == "vent":
                self.assertAlmostEqual(s["yaw"], place[s["package"].split(":")[1]], places=1)


class RelocateTest(unittest.TestCase):
    def test_paths_move_to_the_package_and_uids_go(self) -> None:
        text = X.relocate(SCENE_TEXT)
        self.assertIn('path="res://assets/environment/ship/hall_floor.glb"', text)
        self.assertIn('path="res://assets/environment/ship/metal.gdshader"', text)
        self.assertIn('path="res://assets/environment/ship/materials/metal_hull_silver.tres"', text)
        self.assertNotIn("uid=", text)
        self.assertEqual(X.leftovers(text), [])

    def test_leftovers_are_caught(self) -> None:
        self.assertIn("an art-project import path", X.leftovers(SCENE_TEXT))
        self.assertIn("a script", X.leftovers('[ext_resource type="Script" path="res://a.gd" id="1"]'))
        self.assertIn("a script", X.leftovers("[node name=\"A\" type=\"Node\"]\nscript = ExtResource(\"1\")\n"))
        self.assertIn("a sub-resource path", X.leftovers('[ext_resource path="res://a.glb::Mesh_1" id="1"]'))
        # lens room C: the console's shader the lens bronze uses left the package's scene unloadable
        self.assertIn("a path outside the package",
                      X.leftovers('[ext_resource type="Shader" path="res://console/other.gdshader" id="1"]'))

    def test_the_lens_bronze_shader_moves_into_the_package(self) -> None:
        text = X.relocate('[ext_resource type="Shader" path="res://console/console_metal.gdshader" id="9_c"]\n')
        self.assertIn('path="res://assets/environment/ship/console_metal.gdshader"', text)
        self.assertEqual(X.leftovers(text), [])
        for src in X.SHADERS:
            self.assertTrue((Path(__file__).resolve().parents[2] / "godot" / src).is_file(), src)


class WriteTest(unittest.TestCase):
    def test_the_package_lists_every_file_with_its_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            pieces, built, shaders, out = tmp / "pieces", tmp / "built", tmp / "shaders", tmp / "out"
            for d in (pieces, built, shaders):
                d.mkdir()
            for p in LAYOUT["pieces"]:
                (pieces / f"{p['id']}.glb").write_bytes(b"glb")
            for src in X.SHADERS:
                (shaders / src).parent.mkdir(parents=True, exist_ok=True)
                (shaders / src).write_text("shader_type spatial;\n", encoding="utf-8")
            (built / "ship.tscn").write_text(SCENE_TEXT, encoding="utf-8")
            (built / "metal_hull_silver.tres").write_text('[gd_resource uid="uid://x"]\n', encoding="utf-8")
            summary = X.write(LAYOUT, pieces, built, shaders, out)
            files = summary["files"]
            self.assertIn(X.SCENE, files)
            self.assertIn(f"{X.MATERIAL_DIR}/metal_hull_silver.tres", files)
            self.assertEqual(sum(1 for f in files if f.endswith(".glb")), len({p["id"] for p in LAYOUT["pieces"]}))
            self.assertTrue((out / f"{X.ASSET_DIR}/{LAYOUT['pieces'][0]['id']}.glb.import").is_file())
            self.assertNotIn("res://import/", (out / X.SCENE).read_text(encoding="utf-8"))
            written = json.loads((out / "package.json").read_text(encoding="utf-8"))
            self.assertEqual(written["spawn"]["node"], "Markers/Spawn")
            self.assertEqual(len(written["stations"]), len(LAYOUT["stations"]["spot"]))

    def test_a_missing_piece_or_a_script_stops_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            with self.assertRaisesRegex(ValueError, "not built"):
                X.write(LAYOUT, tmp, tmp, tmp, tmp / "out")


@unittest.skipUnless((PACKAGE / "package.json").is_file(), f"no package in {PACKAGE.as_posix()} (ship --export)")
class WrittenPackageTest(unittest.TestCase):
    def test_the_written_scene_holds_only_package_paths(self) -> None:
        summary = json.loads((PACKAGE / "package.json").read_text(encoding="utf-8"))
        text = (PACKAGE / X.SCENE).read_text(encoding="utf-8")
        self.assertEqual(X.leftovers(text), [])
        for path in set(__import__("re").findall(r'path="res://([^"]+)"', text)):
            self.assertIn(path, summary["files"], path)
        for s in summary["stations"]:
            self.assertTrue(f'[node name="{s["name"]}" type="Marker3D" parent="Stations"' in text, s["name"])


if __name__ == "__main__":
    unittest.main()
