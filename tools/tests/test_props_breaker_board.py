"""The breaker board's committed asset (art#263's stations): the drawing's numbers in board_dims.toml, the manifest,
the GLB's nodes (the four shell leaves on their hinge axes with their colliders, the cores, lamps and beacon), its
size and surfaces, the report (a clean validation, a clean shell sweep) and the look's files, read without Blender or
Godot. Skips the GLB checks in a checkout without its LFS files."""

from __future__ import annotations

import hashlib
import json
import struct
import tomllib
import unittest

from runner import common
from runner.commands import _manifest

ASSET = common.ROOT / "assets" / "prop" / "breaker_board"
EXPORT = ASSET / "export"
DIMS = common.ROOT / "tools" / "blender" / "board_dims.toml"
COLOURS = ("red", "yellow", "green", "blue")
TRIANGLES = 30000
SURFACES = {"board_bronze", "board_graphite", "board_cyan", "board_cable", "board_core", "board_lamp",
            "board_beacon"} | {f"board_enamel_{c}" for c in COLOURS}
MATERIAL_FILES = ("board.gd", "board_metal.gdshader", "board_core.gdshader")


def lfs_pointer(path) -> bool:
    return path.read_bytes()[:40].startswith(b"version https://git-lfs")


def glb_json(path) -> dict:
    data = path.read_bytes()
    magic, _, _ = struct.unpack("<4sII", data[:12])
    assert magic == b"glTF", path
    length, kind = struct.unpack("<I4s", data[12:20])
    assert kind == b"JSON", path
    return json.loads(data[20:20 + length])


class BreakerBoardDrawing(unittest.TestCase):
    def test_dims_keep_the_drawings_numbers(self) -> None:
        # prime-game-design 6b0e83e stations-final/board-drawing/drawing.js (node: its N and D objects)
        d = tomllib.loads(DIMS.read_text(encoding="utf-8"))
        self.assertEqual(d["frame"]["width"], 160.0)
        self.assertEqual(d["frame"]["h0"], 52.0)
        self.assertAlmostEqual(d["frame"]["h1"], 131.4, delta=0.05)
        self.assertAlmostEqual(d["beacon"]["dome"]["top"], 140.4, delta=0.05)
        self.assertLess(d["beacon"]["dome"]["top"], 145.0)  # where the corridor's wall slants
        self.assertEqual(d["bays"]["u"], [-50.4, -16.8, 16.8, 50.4])
        self.assertEqual(d["bays"]["colours"], list(COLOURS))
        self.assertAlmostEqual(d["shell"]["w"], 20.4, delta=0.05)
        self.assertAlmostEqual(d["shell"]["len"], 37.2, delta=0.05)
        self.assertEqual(d["shell"]["face_d"], 31.0)  # 31 deep with every shell closed
        self.assertEqual(d["shell"]["trip_deg"], 110.0)
        self.assertAlmostEqual(d["hinge"]["h"], 67.7, delta=0.05)
        self.assertEqual(d["hinge"]["d"], 25.0)
        self.assertAlmostEqual(d["core"]["w"], 10.3, delta=0.05)
        self.assertAlmostEqual((d["core"]["h0"] + d["core"]["h1"]) / 2, 87.2, delta=0.05)
        self.assertEqual(d["core"]["d"], 18.0)
        self.assertAlmostEqual(d["lamp"]["h"], 114.6, delta=0.05)
        self.assertAlmostEqual(d["cables"]["low"], 17.8, delta=0.05)

    def test_mount_clears_the_wall(self) -> None:
        """board-2: rays on the built ship (b5b) at both spots: the wall's pillow panels stand up to 7.0 cm proud of
        the spot's face plane inside the board's outline, and the wall is vertical to 1.45 m over the deck."""
        d = tomllib.loads(DIMS.read_text(encoding="utf-8"))
        self.assertGreaterEqual(d["mount"]["d"], 7.0)
        self.assertGreater(d["mount"]["back"], 0.0)  # the mount block reaches into the wall's body: no gap
        self.assertLess(d["beacon"]["dome"]["top"], 145.0)
        s, o, sh = d["bays"]["surround"], d["bays"]["opening"], d["shell"]
        self.assertLess(sh["w"] / 2, d["bays"]["strip"]["u"][0])           # the strips clear the shell
        self.assertLess(d["bays"]["strip"]["u"][1], o["w"] / 2 - 0.5)       # and sit inside the liner
        self.assertGreater(o["h1"], d["hinge"]["h"] + sh["len"] + 0.3)      # the shell's top clears the bezel
        self.assertLess(s["h1"], d["lamp"]["h"] - d["lamp"]["ring_r"])      # the bezel clears the lamp ring
        self.assertLess(s["w"], d["bays"]["u"][1] - d["bays"]["u"][0])     # two bezels do not touch


class BreakerBoardAsset(unittest.TestCase):
    def test_manifest_is_valid(self) -> None:
        data, problem = _manifest.load(ASSET / "manifest.toml")
        self.assertIsNotNone(data, problem)
        self.assertEqual(data["id"], "breaker_board")
        self.assertEqual(data["kind"], "prop")
        self.assertFalse(data["ai_generated"])  # built from code in Blender; the AI concept only a reference
        self.assertTrue(data["public_repo_ok"])
        self.assertEqual(data["licence"], "own-work")
        self.assertEqual(_manifest.validate(data, "prop", "breaker_board"), [])

    def test_glb_nodes_leaves_and_surfaces(self) -> None:
        glb = EXPORT / "breaker_board.glb"
        if lfs_pointer(glb):
            self.skipTest("LFS file not fetched")
        doc = glb_json(glb)
        nodes = {n["name"]: n for n in doc["nodes"]}
        prims = [p for m in doc["meshes"] for p in m["primitives"] if "material" in p]  # the colliders have none
        names = {doc["materials"][p["material"]]["name"] for p in prims}
        self.assertEqual(names, SURFACES)  # board.gd finds its surfaces by these names
        for k in range(4):
            self.assertIn(f"board_col{k}-convcolonly", nodes)
        u = [-0.504, -0.168, 0.168, 0.504]
        for i, c in enumerate(COLOURS):
            for part in ("shell", "core", "lamp"):
                self.assertIn(f"{part}_{c}", nodes)
            shell = nodes[f"shell_{c}"]
            # the pivot on the hinge axis (glTF Y up, +Z out of the wall), closed: no rotation
            x, y, z = shell["translation"]
            self.assertAlmostEqual(x, u[i], delta=0.001)
            self.assertAlmostEqual(y, 0.677, delta=0.001)
            self.assertAlmostEqual(z, 0.25, delta=0.001)
            self.assertNotIn("rotation", shell)
            kids = [doc["nodes"][k]["name"] for k in shell.get("children", [])]
            self.assertEqual(kids, [f"shell_{c}_col-convcolonly"])  # the collider turns with its leaf
        self.assertIn("beacon", nodes)
        tris = sum(doc["accessors"][p["indices"]]["count"] // 3 for p in prims)
        self.assertLessEqual(tris, TRIANGLES)
        self.assertNotIn("images", doc)  # no textures

    def test_shipped_glb_is_the_recorded_build(self) -> None:
        glb = EXPORT / "breaker_board.glb"
        if lfs_pointer(glb):
            self.skipTest("LFS file not fetched")
        data, _ = _manifest.load(ASSET / "manifest.toml")
        recorded = {r["file"]: r["sha256"] for r in data["raw"]}
        built = next(sha for name, sha in recorded.items() if name.endswith("/breaker_board.glb"))
        self.assertEqual(hashlib.sha256(glb.read_bytes()).hexdigest(), built)

    def test_report_records_a_clean_build(self) -> None:
        report = json.loads((ASSET / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["gltf_validator"]["numErrors"], 0)
        self.assertEqual(report["gltf_validator"]["numWarnings"], 0)
        self.assertLessEqual(report["mesh"]["triangles"], TRIANGLES)
        size = report["mesh"]["size_m"]  # Blender axes: x (u), y (d), z (h)
        self.assertAlmostEqual(size[0], 1.60, delta=0.005)
        m = report["measured_cm"]
        self.assertAlmostEqual(m["beacon_top_h"], 140.4, delta=0.1)
        self.assertAlmostEqual(m["all_closed"]["d"][1], 31.0, delta=0.1)
        self.assertAlmostEqual(m["shell_tripped"]["d"][1], 60.9, delta=0.5)  # the drawing's tripped reach
        self.assertAlmostEqual(m["shell_tripped"]["h"][0], 53.9, delta=0.5)
        self.assertAlmostEqual(m["cable_low_h"], 17.8, delta=0.1)
        for spot in ("breaker_e", "breaker_w"):  # the review and the game stand the board off the wall the same
            self.assertEqual(report["placement"][spot]["mount_d_cm"], 7.0)
        # every shell swept through its trip in tenths: no triangle crosses the body, a core, a lamp or a neighbour
        self.assertEqual(report["sweep_check"], {f"shell_{c}": {} for c in COLOURS})

    def test_shipped_look_matches_the_godot_files(self) -> None:
        for name in MATERIAL_FILES:
            shipped = (EXPORT / name).read_text(encoding="utf-8")
            self.assertEqual(shipped, (common.ROOT / "godot" / "board" / name).read_text(encoding="utf-8"), name)
        look = (EXPORT / "board.gd").read_text(encoding="utf-8")
        for name in ("set_shell", "set_on", "set_problem", "board_beacon", "board_core", "board_lamp"):
            self.assertIn(name, look)


if __name__ == "__main__":
    unittest.main()
