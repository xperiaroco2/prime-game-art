"""The ship's crystal charger (art#263's stations): the drawing's numbers in charger_dims.toml, the committed asset
(manifest, the GLB's nodes, leaves, anchor, colliders and surfaces, the report's clearance checks, the look's files)
read without Blender or Godot. Skips the GLB checks in a checkout without its LFS files."""

from __future__ import annotations

import json
import math
import re
import struct
import tomllib
import unittest

from runner import common
from runner.commands import _manifest

ASSET = common.ROOT / "assets" / "prop" / "crystal_charger"
EXPORT = ASSET / "export"
DIMS = common.ROOT / "tools" / "blender" / "charger_dims.toml"
SURFACES = {"charger_bronze", "charger_bronze2", "charger_graphite", "charger_cyan", "charger_amber", "charger_lens"}  # lens C: no steel (the legs)
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
        self.assertEqual(f["top"], 142.0)  # the drawing's N.outerTop 139.7, 2.3 taller since antennas-2
        # the pedestal: prime-game-design 7f335c2 lens-room/drawing/drawing.js (C.ped, C.axis, C.back, C.open)
        self.assertEqual((f["axis_d"], f["back"], f["reach"]), (38.0, 10.0, 70.0))
        self.assertEqual(f["open"], [46.0, 50.0, 46.0])
        self.assertEqual((b["side"], b["chamfer_d"], b["front"], b["front_d"]), (44.0, 46.0, 22.0, 68.0))
        self.assertEqual((b["plinth"], b["body"]), (10.0, 86.0))
        self.assertEqual((b["deck"], b["well"], b["well_r"]), (99.1, 94.0, 24.2))  # N.top; the slot sunk in its well
        self.assertEqual((d["slot"]["collar_top"], d["slot"]["tip"]), (95.7, 95.1))
        self.assertEqual((d["button"]["h"], d["button"]["lens"], d["button"]["travel"]), (75.9, 8.0, 1.0))
        self.assertEqual(d["carrier"]["rise"], 6.0)
        # the track ring orbits the crystal at r 19 (its cyan channel's middle), carrying the inner pair
        self.assertAlmostEqual(sum(d["ring"]["light"]) / 2, 19.0, delta=0.05)
        i = d["inner"]
        rs = [r for prof in (i["column"], i["head"]) for r, _h in prof]
        self.assertGreaterEqual(min(rs), d["ring"]["r0"] - 2.5)
        self.assertAlmostEqual(max(rs), 22.8, delta=0.05)
        # antennas-2b: the slim wedge cap (the hook's top was 123.1, r2's blocky cap 121.2), its top sloping down
        # toward the crystal, cap_edge its inner face; the tip electrode half sunk in that face (its centre on it)
        self.assertAlmostEqual(max(h for prof in (i["column"], i["head"]) for _r, h in prof), 120.0, delta=0.05)
        head = i["head"]
        (ar, ah), (br, bh) = head[i["cap_edge"]], head[(i["cap_edge"] + 1) % len(head)]
        self.assertEqual(br, ar)  # an upright face toward the crystal
        self.assertLess(bh, ah)
        self.assertEqual(ar, min(r for r, _h in head))
        self.assertLess(max(h for r, h in head if r == ar), max(h for _r, h in head))  # the wedge slopes down inward
        tip_e = i["electrodes"][0]
        centre = tip_e[0] * math.cos(math.radians(i["half_deg"] / 3)) - 0.45 * tip_e[2]
        self.assertAlmostEqual(centre, ar, delta=0.02)
        self.assertTrue(bh < tip_e[1] - tip_e[2] and tip_e[1] + tip_e[2] < ah)
        self.assertNotIn("emitter", i)
        # the lip: a glowing slot parallel to the slanted edge splits it off the cap; the tip electrode on the lip
        # (its distance from the edge's line under the lip's width), the slot's core inside the faces
        lip_w, gap, ins = i["cap_lip"]
        ln = math.hypot(br - ar, bh - ah)
        n = (-(bh - ah) / ln, (br - ar) / ln)
        dist = (tip_e[0] - ar) * n[0] + (tip_e[1] - ah) * n[1]
        self.assertTrue(0.0 < dist < lip_w - gap / 2)
        self.assertTrue(0.0 < ins < 0.45 and 0.0 < gap < 1.0)
        self.assertNotIn("cap_light", i)
        # the outer pair: in front, u = r cos(half_deg); its inner edge at the drawing's 23.9, its top 142
        o = d["outer"]
        cu = math.cos(math.radians(o["half_deg"]))
        self.assertAlmostEqual(o["root"][0][0] * cu, 23.9, delta=0.1)
        # antennas-1 (the plate stack): the middle line rises from the root's top, bends inward by its turn; the
        # bend's outside reaches the top, its inside the lowest point over the inner pair
        r0, foot, hb = o["spine"]
        rad, turn = o["bend"]
        hw = o["half"][0]
        self.assertEqual(foot, max(h for _r, h in o["root"]))
        self.assertEqual(turn, 90.0)  # the tip's face upright toward the crystal
        self.assertAlmostEqual(hb + rad + hw, f["top"], delta=0.01)
        # the outer pair clears the turning ring and the inner pair
        self.assertGreater(min(min(r for r, _h in o["root"]), r0 - hw), d["ring"]["r1"] + 0.5)
        self.assertGreater(hb + rad - hw, max(h for _r, h in i["head"]) + 3.0)
        # the glow brighter toward the tip: wider gaps, the cores nearer the faces (antennas-2: at the tip partly
        # flush, filling the chamfers' V)
        self.assertLess(o["gaps"][0], o["gaps"][1])
        self.assertGreater(o["core_inset"][0], o["core_inset"][1])
        self.assertLessEqual(o["core_inset"][1], 0.35)  # r2 b1: 0.1 filled the V with wide bands
        # antennas-2: a smooth arc, not antennas-1's tight elbow (radius 9, 13 plates): the radius at least twice the
        # plates' half width, and over it at least seven plates of the 16..18
        self.assertGreaterEqual(rad, 2 * hw)
        self.assertTrue(16 <= o["plates"] <= 18)
        length = hb - foot + rad * math.radians(turn) + o["reach"]
        pitch = length / (o["plates"] + sum(o["end_plates"]) - 2)
        self.assertGreaterEqual(rad * math.radians(turn) / pitch, 7.0)
        # antennas-2b: the picked tip t2: the last plates tapering, a lit slit across the end face inside it
        self.assertEqual(o["tip"], "t2")
        t2 = o["tip_t2"]
        self.assertEqual(len(t2["taper"]), len(t2["depth"]))
        self.assertEqual(sorted(t2["taper"], reverse=True), t2["taper"])
        self.assertEqual(sorted(t2["depth"], reverse=True), t2["depth"])
        w, depth, end = t2["slit"]
        self.assertLess(w, 2 * hw * t2["taper"][-1] - 2.0)
        self.assertTrue(0.0 < depth < 1.0)
        self.assertGreater(end, 0.45)  # a closed slot: it stops short of the plate's chamfered sides
        # the tip's emitter (r2, kept as a variant) recessed in its face: a frame, a sloped wall, the floor
        frame, run, depth = o["emitter"]
        self.assertGreater(depth, 0.0)
        self.assertLess(frame + run, min(o["half"]) - 1.0)
        for key in ("cyan", "amber", "cap", "column", "strip_w"):
            self.assertNotIn(key, o)  # the flat strips and the swept claw are gone
        self.assertNotIn("amber", i)
        # the risen crystal's loop under the prongs' tops
        self.assertLess(d["slot"]["tip"] + CRYSTAL + d["carrier"]["rise"], f["top"])
        # the dome on legs is gone (lens room C)
        self.assertNotIn("legs", d)

    def test_pedestal_fits_the_alcove(self) -> None:
        # the ring clears the back panel by 4.4 (the drawing's note); the lipped plinth and slab stay inside the
        # opening's cheeks by wall_gap and inside the reach; the alcove's numbers are ship_interior_lens's
        d = dims()
        f, b = d["frame"], d["base"]
        self.assertAlmostEqual(f["axis_d"] - d["ring"]["r1"] - f["back"], 4.4, places=6)
        side_lip, _chamfer_lip, front_lip = b["lip"]
        self.assertLessEqual(b["side"] + side_lip, f["open"][0] - f["wall_gap"])
        self.assertLessEqual(b["front_d"] + front_lip, f["reach"])
        self.assertLess(b["front_d"] + 1.8 + 0.15, f["reach"])  # the button's lens with its dome
        src = (common.ROOT / "tools" / "blender" / "ship_interior_lens.py").read_text(encoding="utf-8")
        self.assertEqual(float(re.search(r"^AXIS_D = ([0-9.]+)", src, re.M).group(1)), f["axis_d"])
        self.assertEqual(float(re.search(r"^REACH = ([0-9.]+)", src, re.M).group(1)), f["reach"])

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
        self.assertEqual(len([c for c in cols if c.startswith("crystal_charger_col")]), 3)  # pedestal, 2 prongs
        self.assertEqual(len([c for c in cols if c.startswith("track_ring_col")]), 2)
        mats = {m["name"] for m in doc["materials"]}
        self.assertEqual(mats, SURFACES)
        # the pivots: the carrier on the crystal's axis at its rim, the ring at the deck (glTF: x u, y h, z d)
        self.assertEqual([round(x, 3) for x in carrier["translation"]], [0.0, round(d["carrier"]["top"] / 100, 3), ax])
        self.assertEqual([round(x, 3) for x in nodes["track_ring"]["translation"]], [0.0, round(d["base"]["well"] / 100, 3), ax])
        self.assertAlmostEqual(nodes["crystal_anchor"]["translation"][1],
                               (d["slot"]["tip"] - d["carrier"]["top"]) / 100, places=4)
        # fix1 (#323's review): the button's pivot on the centre line at the dims' h, on its lens's face (the report's
        # pivot, d 69.8 since lens C), in front of the base and inside the charger's reach; charger.gd presses it toward -Z
        report = json.loads((ASSET / "report.json").read_text(encoding="utf-8"))
        pivot = report["mesh"]["by_object"]["button"]["pivot_cm"]
        self.assertEqual(pivot[0], 0.0)
        self.assertEqual(pivot[2], d["button"]["h"])
        self.assertLess(pivot[1], report["mesh"]["size_cm"]["d"][1])
        self.assertEqual([round(x, 4) for x in nodes["button"]["translation"]],
                         [0.0, round(pivot[2] / 100, 4), round(pivot[1] / 100, 4)])
        src = (common.ROOT / "godot" / "charger" / "charger.gd").read_text(encoding="utf-8")
        self.assertIn('(look["button_rest"] as Vector3) - Vector3(0.0, 0.0, TRAVEL if on else 0.0)', src)

    def test_leaves_move_round_their_pivots(self) -> None:
        """fix2 (#323's review, minor 6): each leaf's mesh sits round its pivot the way charger.gd moves it (the GLB's
        own bounds, node-local, glTF x u, y h, z d), and charger.gd moves it by the dims' numbers: the carrier rises
        along +Y from its rim and spins round its own axis, the ring spins round its own axis, the button presses
        toward -Z, into the charger, from its lens's face."""
        glb = EXPORT / "crystal_charger.glb"
        if not glb.is_file() or lfs_pointer(glb):
            self.skipTest("no GLB (LFS)")
        d = dims()
        doc = glb_json(glb)
        nodes = {n["name"]: n for n in doc["nodes"]}

        def bounds(name: str) -> tuple[list[float], list[float]]:
            node = nodes[name]
            self.assertIn("mesh", node, name)
            self.assertNotIn("rotation", node, name)  # a turned pivot would turn its axis
            self.assertNotIn("scale", node, name)
            prims = doc["meshes"][node["mesh"]]["primitives"]
            acc = [doc["accessors"][p["attributes"]["POSITION"]] for p in prims]
            self.assertTrue(acc, name)
            return ([min(a["min"][i] for a in acc) for i in range(3)], [max(a["max"][i] for a in acc) for i in range(3)])

        # the carrier: round its axis (it spins on it), all under its rim's pivot (it rises from there), its radius
        lo, hi = bounds("carrier")
        for i in (0, 2):
            self.assertAlmostEqual(lo[i], -hi[i], places=3)
            self.assertAlmostEqual(hi[i], d["carrier"]["r"] / 100, places=3)
        self.assertLessEqual(hi[1], 0.002)
        self.assertAlmostEqual(lo[1], -d["carrier"]["h"] / 100, places=3)
        # the ring: round its axis, from the well's floor up
        lo, hi = bounds("track_ring")
        for i in (0, 2):
            self.assertAlmostEqual(lo[i], -hi[i], places=3)
        self.assertLess(lo[1], 0.0)
        self.assertGreater(hi[1], 0.0)
        # the button: round its centre across and up, its lens's face at the pivot, its body behind it (-Z): a press
        # toward -Z goes into the charger
        lo, hi = bounds("button")
        for i in (0, 1):
            self.assertAlmostEqual(lo[i], -hi[i], places=3)
            self.assertAlmostEqual(hi[i], d["button"]["lens"] / 200, places=3)
        self.assertLess(lo[2], 0.0)
        self.assertLessEqual(hi[2], 0.002)
        self.assertGreater(-lo[2], hi[2])
        # charger.gd: the travel numbers from the dims, the moves along the axes the meshes sit round
        src = (common.ROOT / "godot" / "charger" / "charger.gd").read_text(encoding="utf-8")
        rise = re.search(r"^const RISE := ([0-9.]+)", src, re.M)
        travel = re.search(r"^const TRAVEL := ([0-9.]+)", src, re.M)
        self.assertIsNotNone(rise)
        self.assertIsNotNone(travel)
        self.assertAlmostEqual(float(rise.group(1)), d["carrier"]["rise"] / 100, places=6)
        self.assertAlmostEqual(float(travel.group(1)), d["button"]["travel"] / 100, places=6)
        self.assertIn('Vector3(0.0, RISE * clampf(rise01, 0.0, 1.0), 0.0)', src)   # up, +Y
        self.assertIn("c.rotation = Vector3(0.0, angle, 0.0)", src)                 # the carrier round Y
        self.assertIn("r.rotation = Vector3(0.0, angle, 0.0)", src)                 # the ring round Y
        self.assertIn('(look["button_rest"] as Vector3) - Vector3(0.0, 0.0, TRAVEL if on else 0.0)', src)  # -Z

    def test_report_checks(self) -> None:
        if not (ASSET / "report.json").is_file():
            self.skipTest("no asset yet")
        r = json.loads((ASSET / "report.json").read_text(encoding="utf-8"))
        c = r["checks"]
        self.assertEqual(c["ring_turn"]["overlaps"], 0)
        self.assertEqual(c["carrier_rise"]["overlaps"], 0)
        self.assertEqual(c["button_pressed_overlaps"], 0)
        # lens room C: the pedestal stands on the alcove's back panel (d 10), inside its cheeks; the turning ring
        # clears the panel by 4.4
        self.assertGreaterEqual(c["wall_min_cm_body"], -0.01)
        self.assertGreaterEqual(c["cheek_min_cm_body"], 0.45)
        self.assertGreaterEqual(c["ring_turn"]["wall_min_cm"], 4.3)
        self.assertLessEqual(c["reach_cm"], 70.0)
        self.assertEqual(r["gltf_validator"]["numErrors"], 0)
        self.assertLess(r["mesh"]["triangles"], 45000)
        # the depth a player's stand counts from: ship.toml's renewer spots' depth_m (0.70 since lens C), which the
        # layout's stand and pass checks use; a deeper charger would stand the player inside its pads
        spots = {s["id"]: s for s in tomllib.loads((common.ROOT / "layouts" / "ship" / "ship.toml")
                                                   .read_text(encoding="utf-8"))["stations"]["spot"]}
        # lens room C (2026-10-28): the pedestal in the wall's alcove reaches at most 70 cm (the spots' 0.70)
        reach = r["mesh"]["size_cm"]["d"][1]
        self.assertLessEqual(reach, 70.0)
        self.assertGreater(reach, 69.0)  # the plinth's and the slab's front lips
        self.assertLessEqual(reach, spots["renewer_e"]["depth_m"] * 100)
        self.assertLessEqual(reach, spots["renewer_w"]["depth_m"] * 100)

    def test_body_inside_the_alcove(self) -> None:
        """Lens C step 4 (the review's minor 1): the committed GLB's body mesh, by its POSITION accessors' bounds
        (glTF x u, y h, z d, metres, the origin on the spot's vertex): its back on the alcove's panel (d 10), its front
        inside the reach (d 70), its sides inside the lips (u +-45.5), not the report's numbers but the file's."""
        glb = EXPORT / "crystal_charger.glb"
        if not glb.is_file() or lfs_pointer(glb):
            self.skipTest("no GLB (LFS)")
        d = dims()
        doc = glb_json(glb)
        node = next(n for n in doc["nodes"] if n["name"] == "crystal_charger")
        self.assertNotIn("rotation", node)
        self.assertNotIn("scale", node)
        self.assertEqual([round(x, 6) for x in node.get("translation", [0.0, 0.0, 0.0])], [0.0, 0.0, 0.0])
        acc = [doc["accessors"][p["attributes"]["POSITION"]] for p in doc["meshes"][node["mesh"]]["primitives"]]
        lo = [min(a["min"][i] for a in acc) for i in range(3)]
        hi = [max(a["max"][i] for a in acc) for i in range(3)]
        self.assertLessEqual(hi[2], d["frame"]["reach"] / 100 + 1e-6)
        self.assertGreaterEqual(lo[2], d["frame"]["back"] / 100 - 1e-6)
        side = (d["base"]["side"] + d["base"]["lip"][0]) / 100
        self.assertAlmostEqual(side, 0.455, places=6)
        self.assertGreaterEqual(lo[0], -side - 1e-6)
        self.assertLessEqual(hi[0], side + 1e-6)
        self.assertGreaterEqual(lo[1], -1e-6)   # nothing under the deck's floor

    def test_glow_on_the_axis(self) -> None:
        """Lens C step 4 (minor 1): charger.gd's glow light sits on the crystal's axis, axis_d out of the wall."""
        src = (common.ROOT / "godot" / "charger" / "charger.gd").read_text(encoding="utf-8")
        m = re.search(r"glow\.position = Vector3\(0\.0, ([0-9.]+), ([0-9.]+)\)", src)
        self.assertIsNotNone(m)
        self.assertAlmostEqual(float(m.group(2)), dims()["frame"]["axis_d"] / 100, places=6)

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
