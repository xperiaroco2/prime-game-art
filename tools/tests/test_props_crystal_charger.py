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
SURFACES = {"charger_bronze", "charger_graphite", "charger_cyan", "charger_amber", "charger_lens", "charger_steel"}
LEAVES = {"carrier", "track_ring", "button", "crystal_anchor"}
CRYSTAL = 34.9  # the built crystal, its tip to its loop's top (prime-game-art#316)


def lfs_pointer(path) -> bool:
    return path.read_bytes()[:40].startswith(b"version https://git-lfs")


def glb_json(path) -> dict:
    data = path.read_bytes()
    magic, _, _ = struct.unpack("<4sII", data[:12])
    assert magic == b"glTF", path
    length, kind = struct.unpack("<I4s", data[12:20])
    assert kind == b"JSON", path
    return json.loads(data[20:20 + length])


def dims() -> dict:
    return tomllib.loads(DIMS.read_text(encoding="utf-8"))


class ChargerDrawing(unittest.TestCase):
    def test_dims_keep_the_drawings_numbers(self) -> None:
        # prime-game-design a53ce6f stations-final/charger-drawing/drawing.js (node: its N object)
        d = dims()
        f, b = d["frame"], d["base"]
        self.assertEqual((f["top"], f["wall_gap"]), (139.7, 2.0))
        self.assertEqual((b["bottom"], b["widest"]), (60.0, 72.8))  # charger-3: a skirt 4.8 under N.baseBottom 64.8
        self.assertAlmostEqual(b["r_widest"] * 2, 100.4, delta=0.05)
        self.assertAlmostEqual(b["r_deck_edge"] * 2, 82.0, delta=0.05)  # N.tierTop: the upper tier's top edge
        self.assertEqual((b["deck"], b["well"]), (99.1, 94.0))  # N.top: the deck; the slot sunk in its well (charger-3)
        self.assertEqual((d["slot"]["collar_top"], d["slot"]["tip"]), (95.7, 95.1))
        self.assertEqual((d["button"]["h"], d["button"]["lens"], d["button"]["travel"]), (75.9, 8.0, 1.0))
        self.assertEqual(d["carrier"]["rise"], 6.0)
        # the track ring orbits the crystal at r 19 (its cyan channel's middle), carrying the inner pair
        self.assertAlmostEqual(sum(d["ring"]["light"]) / 2, 19.0, delta=0.05)
        i = d["inner"]
        rs = [r for prof in (i["column"], i["head"]) for r, _h in prof]
        self.assertGreaterEqual(min(rs), d["ring"]["r0"] - 2.5)
        self.assertAlmostEqual(max(rs), 22.8, delta=0.05)
        self.assertAlmostEqual(max(h for prof in (i["column"], i["head"]) for _r, h in prof), 123.1, delta=0.05)
        # the outer pair: in front, u = r cos(half_deg); its inner edge at the drawing's 23.9, its top 139.7
        o = d["outer"]
        cu = math.cos(math.radians(o["half_deg"]))
        self.assertAlmostEqual(o["root"][0][0] * cu, 23.9, delta=0.1)
        self.assertAlmostEqual(max(h for _r, h in o["cap"]), f["top"], delta=0.01)
        # the outer pair clears the turning ring and the inner pair
        self.assertGreater(min(r for prof in (o["root"], o["column"]) for r, _h in prof), d["ring"]["r1"] + 0.5)
        self.assertGreater(min(h for _r, h in o["cap"]), max(h for _r, h in i["head"]) + 3.0)
        # the risen crystal's loop under the prongs' tops
        self.assertLess(d["slot"]["tip"] + CRYSTAL + d["carrier"]["rise"], f["top"])
        # four legs, the pistons lengthened 27 cm (N.legLift): their tops under the base's skirt (charger-3: 60)
        self.assertEqual(len(d["legs"]["angles"]) * 2, 4)
        self.assertAlmostEqual(d["legs"]["hip"][1], b["bottom"], delta=0.5)

    def test_base_clears_the_wall(self) -> None:
        # round and uncut: the widest circle stays wall_gap off the lens room's two facets at the spot's vertex
        d = dims()
        f = d["frame"]
        gap = f["axis_d"] * math.cos(math.radians(f["back_fold_deg"])) - d["base"]["r_widest"]
        self.assertGreaterEqual(gap, f["wall_gap"])

    def test_back_fold_is_the_lens_rooms_facet(self) -> None:
        # the spot sits on a vertex of the lens room's 12-sided wall: half a facet's angle either side
        d = dims()
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
        d = dims()
        ax = d["frame"]["axis_d"] / 100
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
        self.assertEqual(len([c for c in cols if c.startswith("crystal_charger_col")]), 7)  # base, 2 prongs, 4 legs
        self.assertEqual(len([c for c in cols if c.startswith("track_ring_col")]), 2)
        mats = {m["name"] for m in doc["materials"]}
        self.assertEqual(mats, SURFACES)
        # the pivots: the carrier on the crystal's axis at its rim, the ring at the deck (glTF: x u, y h, z d)
        self.assertEqual([round(x, 3) for x in carrier["translation"]], [0.0, round(d["carrier"]["top"] / 100, 3), ax])
        self.assertEqual([round(x, 3) for x in nodes["track_ring"]["translation"]], [0.0, round(d["base"]["well"] / 100, 3), ax])
        self.assertAlmostEqual(nodes["crystal_anchor"]["translation"][1],
                               (d["slot"]["tip"] - d["carrier"]["top"]) / 100, places=4)

    def test_report_checks(self) -> None:
        if not (ASSET / "report.json").is_file():
            self.skipTest("no asset yet")
        r = json.loads((ASSET / "report.json").read_text(encoding="utf-8"))
        c = r["checks"]
        self.assertEqual(c["ring_turn"]["overlaps"], 0)
        self.assertEqual(c["carrier_rise"]["overlaps"], 0)
        self.assertEqual(c["button_pressed_overlaps"], 0)
        self.assertGreaterEqual(c["wall_min_cm_body"], 1.9)  # the base and the back legs' pads off the facets
        self.assertGreaterEqual(c["ring_turn"]["wall_min_cm"], 1.9)
        self.assertEqual(r["gltf_validator"]["numErrors"], 0)
        self.assertLess(r["mesh"]["triangles"], 45000)
        # the depth a player's stand counts from: the pass behind them was measured at 1.04 m (2.17 m free, pass_m 1.6)
        self.assertLessEqual(r["mesh"]["size_cm"]["d"][1], 106.0)

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
