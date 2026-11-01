"""The lobby hall's game-ready package (art #356 step 5b, docs/lobby.md "The export"): its layout, the paths it
rewrites and refuses, the spawns, and the check's verdict on a load report. Plain Python, no Godot."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runner import lobby_export, lobby_layout  # noqa: E402
from runner.commands import _lobby_export  # noqa: E402

LAYOUT = lobby_layout.load()


class PathsTest(unittest.TestCase):
    def test_relocate(self):
        text = ('[ext_resource type="PackedScene" uid="uid://abc123" path="res://import/lobby_floor.glb" id="1"]\n'
                '[ext_resource path="res://import/ship_pkg/levels/ship/ship.tscn" id="2"]\n'
                '[ext_resource path="res://import/lobby_earth/earth_night.jpg" id="3"]\n'
                '[ext_resource path="res://import/lobby_export/lobby_env.tres" id="4"]\n'
                '[ext_resource path="res://lobby/earth_object.gdshader" id="5"]\n'
                '[ext_resource path="res://import/ship_pkg/assets/environment/ship/metal.gdshader" id="6"]\n')
        out = lobby_export.relocate(text)
        self.assertNotIn("uid://", out)
        for want in ("res://assets/environment/lobby/floor.glb", "res://levels/ship/ship.tscn",
                     "res://assets/environment/lobby/earth/earth_night.jpg",
                     "res://assets/environment/lobby/materials/lobby_env.tres",
                     "res://assets/environment/lobby/earth_object.gdshader",
                     "res://assets/environment/ship/metal.gdshader"):
            self.assertIn(want, out)
        self.assertEqual(lobby_export.leftovers(out), [])

    def test_leftovers(self):
        for text, why in (('path="res://import/lobby_floor.glb"', "an art-project import path"),
                          ('path="res://lobby/hall.gd"', "an art-project lobby path"),
                          ('[ext_resource type="Script" path="res://x.gd"]', "a script"),
                          ('path="res://assets/environment/lobby/floor.glb::Mesh_1"', "a sub-resource path"),
                          ('path="res://assets/props/x.glb"', "a path outside the package")):
            self.assertIn(why, lobby_export.leftovers(text), text)

    def test_the_level_script(self):
        ext = '[ext_resource type="Script" path="res://lobby/lobby_hall.gd" id="1_s"]\n'
        node = '[node name="LobbyHall" type="Node3D"]\nscript = ExtResource("1_s")\n'
        scene = lobby_export.relocate(ext + node)
        self.assertIn(f'path="res://{lobby_export.LEVEL_SCRIPT}"', scene)
        self.assertEqual(lobby_export.leftovers(scene, level_script=True), [])
        self.assertIn("a script", lobby_export.leftovers(scene))   # only the scene may hold it
        self.assertIn("no level script on the root",
                      lobby_export.leftovers(lobby_export.relocate(node), level_script=True))
        other = '[ext_resource type="Script" path="res://levels/lobby/x.gd" id="2_s"]\n'
        self.assertIn("a script",
                      lobby_export.leftovers(scene + other + 'script = ExtResource("2_s")\n', level_script=True))
        twice = scene + '[node name="Hall" type="Node3D"]\nscript = ExtResource("1_s")\n'
        self.assertIn("no level script on the root", lobby_export.leftovers(twice, level_script=True))

    def test_the_level_script_source(self):
        """godot/lobby/lobby_hall.gd moves with the package: no res:// path in its code; it frees ship_free on _ready
        and has the probes capture again after a frame."""
        src = (Path(__file__).resolve().parents[2] / "godot" / lobby_export.LEVEL_SCRIPT_SRC).read_text(encoding="utf-8")
        self.assertTrue(src.startswith("extends Node3D\n"))
        code = "\n".join(line for line in src.splitlines() if not line.lstrip().startswith("#"))
        self.assertNotIn("res://", code)
        for want in ("@export var ship_free: Array[NodePath]", "func _ready() -> void:", "n.free()",
                     "await get_tree().process_frame", '"ReflectionProbe"', "remove_child(probe)", "add_child(probe)",
                     'set_meta("ship_freed"', 'set_meta("probes_recaptured"'):
            self.assertIn(want, code)
        after = code.split("await get_tree().process_frame", 1)[1]   # #366: the level may leave the tree meanwhile
        self.assertRegex(after, r"^\n\tif not is_inside_tree\(\):[^\n]*\n\t\treturn\n")
        self.assertNotIn("@tool", code)        # never runs in the game's editor
        self.assertNotIn("queue_free", code)   # freed at once, before the first frame draws


class LayoutTest(unittest.TestCase):
    def test_spawns_face_the_window(self):
        sp = lobby_export.spawns(LAYOUT)
        self.assertEqual(len(sp), 10)
        self.assertEqual([s["name"] for s in sp], [f"Spawn{i}" for i in range(10)])
        self.assertTrue(all(s["yaw"] == 180.0 and s["at"][2] == LAYOUT["floor"]["spawns_z"] for s in sp))

    def test_the_package_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            pieces, built, shaders, out = tmp / "pieces", tmp / "import" / "lobby_export", tmp / "godot", tmp / "out"
            for d in (pieces, built, shaders / "lobby"):
                d.mkdir(parents=True)
            (shaders / lobby_export.LEVEL_SCRIPT_SRC).write_text("extends Node3D\n", encoding="utf-8")
            for pid in lobby_export.piece_ids(LAYOUT):
                (pieces / f"{pid}.glb").write_bytes(b"glTF" + pid.encode())
            (tmp / "import" / "lobby_vault_lobby_metal_n.png").write_bytes(b"png")
            (built / "lobby_hall.tscn").write_text(
                '[ext_resource type="Script" path="res://lobby/lobby_hall.gd" id="9_s"]\n'
                '[ext_resource path="res://import/lobby_floor.glb" id="1"]\n'
                '[ext_resource path="res://import/lobby_vault_lobby_metal_n.png" id="2"]\n'
                '[ext_resource path="res://import/ship_pkg/levels/ship/ship.tscn" id="3"]\n'
                '[node name="LobbyHall" type="Node3D"]\nscript = ExtResource("9_s")\n', encoding="utf-8")
            (built / "lobby_env.tres").write_text('[ext_resource path="res://lobby/earth_sky.gdshader" id="1"]\n',
                                                  encoding="utf-8")
            for src in lobby_export.SHADERS:
                (shaders / src).write_text("shader_type spatial;\n", encoding="utf-8")
            earth = {}
            for k in ("night", "day", "clouds"):
                earth[f"earth_{k}.jpg"] = tmp / f"earth_{k}.jpg"
                earth[f"earth_{k}.jpg"].write_bytes(b"jpg")
            summary = lobby_export.write(LAYOUT, pieces, built, shaders, earth, {"version": 4, "bytes": 1},
                                         "ship/v5/export/v4", out)
            files = set(summary["files"])
            a = lobby_export.ASSET_DIR
            for pid in lobby_export.piece_ids(LAYOUT):
                self.assertIn(f"{a}/{pid}.glb", files)
                self.assertTrue((out / f"{a}/{pid}.glb.import").is_file())
            self.assertEqual(sum(1 for f in files if f.endswith(".glb")), len(LAYOUT["pieces"]))  # each GLB once
            for f in ("earth/earth_night.jpg", "earth_sky.gdshader", "materials/lobby_env.tres",
                      "vault_lobby_metal_n.png"):
                self.assertIn(f"{a}/{f}", files)
            self.assertIn("compress/mode=2", (out / f"{a}/earth/earth_night.jpg.import").read_text(encoding="utf-8"))
            self.assertIn(lobby_export.SCENE, files)
            self.assertFalse([f for f in files if f.startswith(lobby_export.SHIP_PREFIXES)], "the ship is never copied")
            scene = (out / lobby_export.SCENE).read_text(encoding="utf-8")
            self.assertIn('"res://levels/ship/ship.tscn"', scene)
            self.assertIn(f'path="res://{lobby_export.LEVEL_SCRIPT}"', scene)
            self.assertIn(lobby_export.LEVEL_SCRIPT, files)
            self.assertEqual((out / lobby_export.LEVEL_SCRIPT).read_text(encoding="utf-8"), "extends Node3D\n")
            meta = json.loads((out / "package.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["ship"]["scene"], "res://levels/ship/ship.tscn")
            self.assertEqual(meta["level_script"], f"res://{lobby_export.LEVEL_SCRIPT}")
            self.assertEqual(meta["earth"]["credit"], "Earth imagery: NASA")
            self.assertEqual(meta["earth"]["distance"], LAYOUT["earth"]["distance"])
            self.assertEqual(len(meta["spawns"]), 10)

    def test_ship_copy_by_hash(self):
        """#366: ship_copy rewrites a file whose bytes changed at the same size, keeps an equal one untouched and copies
        a missing `.import` but never one that Godot's import rewrote."""
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = Path(tmp) / "ship", Path(tmp) / "lobby"
            (src / "a").mkdir(parents=True)
            (src / "package.json").write_text(json.dumps({"files": ["a/x.glb", "a/y.tres"]}), encoding="utf-8")
            (src / "a" / "x.glb").write_bytes(b"AAAA")
            (src / "a" / "y.tres").write_bytes(b"same")
            (src / "a" / "x.glb.import").write_text("[remap]\n", encoding="utf-8")
            self.assertEqual(_lobby_export.ship_copy(src, dst), 2)
            self.assertEqual((dst / "a" / "x.glb").read_bytes(), b"AAAA")
            self.assertTrue((dst / "a" / "x.glb.import").is_file())
            (src / "a" / "x.glb").write_bytes(b"BBBB")   # same size, other bytes
            (dst / "a" / "x.glb.import").write_text("[remap]\nrewritten\n", encoding="utf-8")
            keep = (dst / "a" / "y.tres").stat().st_mtime_ns
            _lobby_export.ship_copy(src, dst)
            self.assertEqual((dst / "a" / "x.glb").read_bytes(), b"BBBB")
            self.assertEqual((dst / "a" / "y.tres").stat().st_mtime_ns, keep)
            self.assertIn("rewritten", (dst / "a" / "x.glb.import").read_text(encoding="utf-8"))

    def test_a_leftover_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            pieces, built = tmp / "pieces", tmp / "import" / "lobby_export"
            pieces.mkdir()
            built.mkdir(parents=True)
            (tmp / "lobby").mkdir()
            for pid in lobby_export.piece_ids(LAYOUT):
                (pieces / f"{pid}.glb").write_bytes(b"glTF")
            for src in [*lobby_export.SHADERS, lobby_export.LEVEL_SCRIPT_SRC]:
                (tmp / src).write_text("x", encoding="utf-8")
            (built / "lobby_hall.tscn").write_text('[ext_resource type="Script" path="res://lobby/hall.gd"]\n',
                                                   encoding="utf-8")
            with self.assertRaises(ValueError):
                lobby_export.write(LAYOUT, pieces, built, tmp, {}, {}, "x", tmp / "out")


class VerdictTest(unittest.TestCase):
    def good(self) -> dict:
        sp = lobby_export.spawns(LAYOUT)
        free = ["Ship/Clearing", "Ship/Environment", "Ship/Lights/Moon", "Ship/Lights/Key"]
        return {"bounds": {}, "colliders": {p["id"]: 1 for p in LAYOUT["pieces"]},
                "scripts": [f"LobbyHall res://{lobby_export.LEVEL_SCRIPT}"], "root": "LobbyHall",
                "level_script": {"path": f"res://{lobby_export.LEVEL_SCRIPT}", "ship_free": free, "ship_freed": 4,
                                 "probes_recaptured": 5, "probes_total": 5},
                "meta": {"size_m": "", "camera_far_m": ""},
                "groups": ["Hall", "Ship", "Earth", "Environment", "Lights", "Probes", "Markers"],
                "spawns": [{"name": s["name"], "at": s["at"], "forward": [0.0, 0.0, 1.0]} for s in sp],
                "ship": {"scene": "res://levels/ship/ship.tscn", "at": LAYOUT["ship"]["origin"], "clearing_visible": False,
                         "clearing_processing": False, "clearing_present": False, "environment_present": False,
                         "environments": 0, "suns": 0, "suns_visible": 0,
                         "jaws": {"jaw_lower": 0.0, "jaw_upper": 0.0}, "colliders_on": 700, "colliders_off": 20,
                         "off_layer": 0, "meshes": 900, "lights_visible": 0},
                "earth": {"far_mode": 1.0, "textures": [f"res://{lobby_export.EARTH_DIR}/earth_night.jpg 4096x2048"]},
                "lights": 50, "probes": 8,
                "walk": {"arrived": True, "reached": 22, "of": 22, "stuck": [0, 0, 0], "seconds": 60.0, "min_y": 0.0}}

    def test_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "build_report.json").write_text(json.dumps({"pieces": {}}), encoding="utf-8")
            self.assertEqual(_lobby_export.problems(LAYOUT, Path(tmp), self.good(), []), [])
            for change in (("clearing_visible", True), ("suns_visible", 2), ("off_layer", 3),
                           ("scene", "res://assets/environment/lobby/ship.tscn")):
                got = copy.deepcopy(self.good())
                got["ship"][change[0]] = change[1]
                self.assertTrue(_lobby_export.problems(LAYOUT, Path(tmp), got, []), change)
            got = self.good()
            got["ship"]["jaws"]["jaw_lower"] = -34.37
            self.assertTrue(_lobby_export.problems(LAYOUT, Path(tmp), got, []))
            got = self.good()
            got["spawns"][3]["forward"] = [0.0, 0.0, -1.0]
            self.assertTrue(_lobby_export.problems(LAYOUT, Path(tmp), got, []))
            for change in (("clearing_present", True), ("environment_present", True), ("suns", 1), ("environments", 1)):
                got = copy.deepcopy(self.good())
                got["ship"][change[0]] = change[1]
                self.assertTrue(_lobby_export.problems(LAYOUT, Path(tmp), got, []), change)

    def test_verdict_on_the_level_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "build_report.json").write_text(json.dumps({"pieces": {}}), encoding="utf-8")
            for key, value in (("ship_freed", 3), ("probes_recaptured", -1), ("probes_recaptured", 4),
                               ("ship_free", ["Ship/Clearing"]), ("ship_free", [])):
                got = copy.deepcopy(self.good())
                got["level_script"][key] = value
                self.assertTrue(_lobby_export.problems(LAYOUT, Path(tmp), got, []), (key, value))
            for scripts in ([], [f"LobbyHall res://{lobby_export.LEVEL_SCRIPT}", "Hall res://x.gd"]):
                got = copy.deepcopy(self.good())
                got["scripts"] = scripts
                self.assertTrue(_lobby_export.problems(LAYOUT, Path(tmp), got, []), scripts)


if __name__ == "__main__":
    unittest.main()
