"""The ship's crystal charger (art#263's stations): the drawing's numbers in charger_dims.toml, the committed asset
(manifest, the GLB's nodes, leaves, anchor, colliders and surfaces, the report's clearance checks, the look's files)
read without Blender or Godot. Skips the GLB checks in a checkout without its LFS files."""

from __future__ import annotations

import json
import math
import struct
import tomllib
import unittest

from runner import common
from runner.commands import _manifest

ASSET = common.ROOT / "assets" / "prop" / "crystal_charger"
EXPORT = ASSET / "export"
DIMS = common.ROOT / "tools" / "blender" / "charger_dims.toml"
SURFACES = {"charger_bronze", "charger_graphite", "charger_cyan", "charger_amber", "charger_lens"}
LEAVES = {"carrier", "track_ring", "button", "crystal_anchor"}


def lfs_pointer(path) -> bool:
    return path.read_bytes()[:40].startswith(b"version https://git-lfs")


def glb_json(path) -> dict:
    data = path.read_bytes()
    magic, _, _ = struct.unpack("<4sII", data[:12])
    assert magic == b"glTF", path
    length, kind = struct.unpack("<I4s", data[12:20])
    assert kind == b"JSON", path
    return json.loads(data[20:20 + length])


class ChargerDrawing(unittest.TestCase):
    def test_dims_keep_the_drawings_numbers(self) -> None:
        # prime-game-design 5458033 stations-final/charger-drawing/drawing.js (node: its N object)
        d = tomllib.loads(DIMS.read_text(encoding="utf-8"))
        f, t = d["frame"], d["tiers"]
        self.assertEqual((f["width"], f["depth"], f["top"], f["axis_d"], f["wall_gap"]), (120.0, 89.5, 130.1, 27.3, 2.0))
        self.assertEqual((t["widest"], t["widest_top"], t["rim"], t["bevel"], t["deck"]), (26.3, 51.3, 60.7, 82.9, 85.0))
        self.assertAlmostEqual(t["r_widest"] * 2, 108.4, delta=0.05)
        self.assertEqual((d["button"]["h"], d["button"]["travel"], d["carrier"]["rise"]), (72.0, 1.0, 6.0))
        self.assertEqual((d["ring"]["r0"], d["ring"]["r1"]), (16.5, 24.5))
        self.assertEqual(d["foot"]["angles"], [-75.0, 0.0, 75.0])
        # the depth: the axis plus the feet's reach is the front foot's face, inside the spot's 90 cm
        self.assertAlmostEqual(f["axis_d"] + d["foot"]["reach"], f["depth"], delta=0.05)
        self.assertLessEqual(f["depth"], 90.0)
        # the risen crystal's loop under the prongs' tops (the built crystal is 34.9 cm from its tip)
        self.assertLess(d["slot"]["tip"] + 34.9 + d["carrier"]["rise"], f["top"])

    def test_back_fold_is_the_lens_rooms_facet(self) -> None:
        # the spot sits on a vertex of the lens room's 12-sided wall: half a facet's angle either side
        d = tomllib.loads(DIMS.read_text(encoding="utf-8"))
        ship = tomllib.loads((common.ROOT / "layouts" / "ship" / "ship.toml").read_text(encoding="utf-8"))
        room = next(r for r in ship["rooms"] if r["id"] == "tip_e")
        cor = next(r for r in ship["rooms"] if r["id"] == "corridor_e")
        r_tip = room["radius"] + 0.05
        door = math.degrees(math.asin((cor["width"] / 2 + 0.03) / r_tip))
        self.assertAlmostEqual(d["frame"]["back_fold_deg"], (360.0 - 2 * door) / 12 / 2, delta=0.01)


class ChargerAsset(unittest.TestCase):
    def test_manifest_valid(self) -> None:
        if not (ASSET / "manifest.toml").is_file():
            self.skipTest("no asset yet")
        m = tomllib.loads((ASSET / "manifest.toml").read_text(encoding="utf-8"))
        self.assertEqual(_manifest.validate(m, "prop", "crystal_charger"), [])
        self.assertFalse(m["ai_generated"])
        self.assertTrue(m["public_repo_ok"])

    def test_glb_nodes_leaves_colliders(self) -> None:
        glb = EXPORT / "crystal_charger.glb"
        if not glb.is_file() or lfs_pointer(glb):
            self.skipTest("no GLB (LFS)")
        doc = glb_json(glb)
        nodes = {n["name"]: n for n in doc["nodes"]}
        self.assertIn("crystal_charger", nodes)
        self.assertTrue(LEAVES <= set(nodes), set(nodes))
        body = nodes["crystal_charger"]
        kids = {doc["nodes"][i]["name"] for i in body.get("children", [])}
        self.assertTrue({"carrier", "track_ring", "button"} <= kids, kids)
        carrier = nodes["carrier"]
        self.assertIn("crystal_anchor", {doc["nodes"][i]["name"] for i in carrier.get("children", [])})
        cols = [n for n in nodes if n.endswith("-convcolonly")]
        self.assertGreaterEqual(len([c for c in cols if c.startswith("crystal_charger_col")]), 6)
        self.assertEqual(len([c for c in cols if c.startswith("track_ring_col")]), 2)
        mats = {m["name"] for m in doc["materials"]}
        self.assertEqual(mats, SURFACES)
        # the pivots: the carrier on the crystal's axis at its top, the ring at the deck (glTF: x u, y h, z d)
        self.assertEqual([round(x, 3) for x in carrier["translation"]], [0.0, 0.845, 0.273])
        self.assertEqual([round(x, 3) for x in nodes["track_ring"]["translation"]], [0.0, 0.85, 0.273])
        self.assertAlmostEqual(nodes["crystal_anchor"]["translation"][1], -0.02, places=4)

    def test_report_checks(self) -> None:
        if not (ASSET / "report.json").is_file():
            self.skipTest("no asset yet")
        r = json.loads((ASSET / "report.json").read_text(encoding="utf-8"))
        c = r["checks"]
        self.assertEqual(c["ring_turn"]["overlaps"], 0)
        self.assertEqual(c["carrier_rise"]["overlaps"], 0)
        self.assertGreaterEqual(c["wall_min_cm_body"], 1.9)
        self.assertGreaterEqual(c["ring_turn"]["wall_min_cm"], 1.9)
        self.assertEqual(r["gltf_validator"]["numErrors"], 0)
        self.assertLessEqual(r["mesh"]["size_cm"]["d"][1], 90.0)

    def test_look_files(self) -> None:
        if not (EXPORT / "charger.gd").is_file():
            self.skipTest("no asset yet")
        metal = (common.ROOT / "godot" / "console" / "console_metal.gdshader").read_bytes()
        self.assertEqual((EXPORT / "console_metal.gdshader").read_bytes(), metal)  # shared, not forked
        src = (common.ROOT / "godot" / "charger" / "charger.gd").read_text(encoding="utf-8")
        want = src.replace('preload("res://console/console_metal.gdshader")', 'preload("console_metal.gdshader")')
        self.assertEqual((EXPORT / "charger.gd").read_text(encoding="utf-8"), want)


if __name__ == "__main__":
    unittest.main()
