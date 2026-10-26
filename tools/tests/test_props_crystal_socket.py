"""The ship's crystal socket's committed asset (art#263's stations): the drawing's numbers in socket_dims.toml and the
geometry helpers of socket_drawing.py, the manifest, the GLB's size, surfaces, anchor and colliders, the report's
checks against the built crystal and the look's files, read without Blender or Godot. Skips the GLB checks in a
checkout without its LFS files."""

from __future__ import annotations

import hashlib
import json
import re
import struct
import sys
import tomllib
import unittest

from runner import common
from runner.commands import _manifest

sys.path.insert(0, str(common.ROOT / "tools" / "blender"))
import socket_drawing  # noqa: E402

ASSET = common.ROOT / "assets" / "prop" / "crystal_socket"
EXPORT = ASSET / "export"
DIMS = common.ROOT / "tools" / "blender" / "socket_dims.toml"
TRIANGLES = 5000  # a wall station: 2,138 at b4, 3,9xx at b5 (socket-2: blocks, two bevels, turned parts), 4,466 at b6
SURFACES = {"socket_bronze", "socket_graphite", "socket_cyan", "socket_amber", "socket_lamp", "socket_bay"}
MATERIAL_FILES = ("socket.gd", "socket_metal.gdshader", "socket_bay.gdshader")
CLAWS = ("claw_r", "claw_l")


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


class CrystalSocketDrawing(unittest.TestCase):
    def test_dims_keep_the_drawings_numbers(self) -> None:
        # prime-game-design ea27a81 stations-final/socket-drawing/drawing.js (node: its N object)
        d = tomllib.loads(DIMS.read_text(encoding="utf-8"))
        hs = [h for _u, h in d["outline"]["pts"]]
        us = [u for u, _h in d["outline"]["pts"]]
        self.assertAlmostEqual(max(us) * 2, 46.7, delta=0.1)  # the frame's width
        self.assertAlmostEqual(min(hs), 87.4, delta=0.05)  # the frame's bottom
        self.assertAlmostEqual(d["lamp"]["h"][1] - min(hs), 87.5, delta=0.1)  # tall with the lamp
        self.assertAlmostEqual(d["lamp"]["h"][1], 174.8, delta=0.05)
        self.assertAlmostEqual(d["lamp"]["ru"] * 2, 7.7, delta=0.05)
        self.assertAlmostEqual(d["lamp"]["d"] - d["lamp"]["rd"], 8.0, delta=0.05)
        self.assertAlmostEqual(d["lamp"]["d"] + d["lamp"]["rd"], 14.4, delta=0.05)
        self.assertAlmostEqual(d["neck"]["ru"] * 2, 11.3, delta=0.05)
        dp = d["depth"]
        self.assertEqual((dp["plate"], dp["layer"], dp["front"], dp["claw"][1], dp["bay"]), (6.7, 12.2, 21.1, 22.2, 9.5))
        self.assertLessEqual(max(max(v) if isinstance(v, list) else v for v in dp.values()), 30.0)  # <= 30 out
        self.assertEqual(d["mount"]["h"], 140.0)  # MOUNT: the one number (the engineer may lower it to 120)
        self.assertEqual(d["mount"]["axis_d"], 17.0)
        self.assertEqual(d["mount"]["crystal"], 34.9)
        bay = d["bay"]["pts"]
        self.assertAlmostEqual(max(u for u, _h in bay) * 2, 28.9, delta=0.1)  # the bay at its top
        self.assertAlmostEqual(bay[7][0] * 2, 20.1, delta=0.1)  # by the collar
        coll = d["collar"]["pts"]
        self.assertAlmostEqual(max(u for u, _h in coll) * 2, 14.4, delta=0.05)

    def test_claws_hold_the_built_crystals_cap(self) -> None:
        d = socket_drawing.load()
        cap = tomllib.loads((common.ROOT / "tools" / "blender" / "crystal_dims.toml").read_text(encoding="utf-8"))
        flats = d["mount"]["cap_built"]  # the built cap at its band (13.5 across flats, its rims 13.62)
        z0, z1 = d["mount"]["cap"][:2]
        jaw = min(u for u, h in d["claw"]["pts"] if h < d["mount"]["tip_h"] + z1)  # the jaw beside the cap's band
        self.assertTrue(0.0 < jaw - flats / 2 <= 0.05, jaw)  # touching, clear by under half a millimetre
        low = min(h for _u, h in d["claw"]["pts"])
        self.assertGreaterEqual(d["mount"]["tip_h"] + z1 - low, 1.0)  # the jaws reach a centimetre down the band
        self.assertGreater(low, d["mount"]["tip_h"] + z0)
        band = cap["band"]  # the socket's cap numbers are the built crystal's
        self.assertEqual(d["mount"]["cap"], [band["z_bottom"], band["z_top"], band["flats"]])
        self.assertEqual(d["mount"]["crystal"], cap["loop"]["z_top"])

    def test_mount_moves_everything_by_one_number(self) -> None:
        text = DIMS.read_text(encoding="utf-8").replace("h = 140.0 ", "h = 120.0 ", 1)
        tmp = common.OUT / "test_socket_dims.toml"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(text, encoding="utf-8")
        a, b = socket_drawing.load(), socket_drawing.load(tmp)
        tmp.unlink()
        self.assertAlmostEqual(b["mount"]["tip_h"], a["mount"]["tip_h"] - 20.0)
        for name in socket_drawing.POLYS:
            for p, q in zip(a[name]["pts"], b[name]["pts"]):
                self.assertAlmostEqual(q[1], p[1] - 20.0)
        self.assertAlmostEqual(b["lamp"]["h"][1], a["lamp"]["h"][1] - 20.0)

    def test_claws_open_round_the_drawings_hinge(self) -> None:
        # prime-game-design 1df9a42 drawing.js: HINGE [590, 268] px, OPEN 35 (a placeholder), PULL 15
        d = socket_drawing.load()
        k = d["claw"]
        self.assertAlmostEqual(k["hinge"][0], (590 - 511.5) / 14.613, delta=0.01)
        self.assertAlmostEqual(k["hinge"][1], 87.38 + (1370 - 268) / 14.613, delta=0.02)
        self.assertEqual((k["open_drawn"], k["pull"]), (35.0, 15.0))
        self.assertTrue(0.0 < k["open"] <= k["open_drawn"])
        # the right claw's tip turns up and outward; the hinge stays
        tip = max(k["pts"], key=lambda p: (p[0], -p[1]))
        (u, h), (hu, hh) = socket_drawing.swing([tip, k["hinge"]], k["hinge"], k["open"])
        self.assertGreater(u, tip[0])
        self.assertGreater(h, tip[1])
        self.assertAlmostEqual(hu, k["hinge"][0])
        self.assertAlmostEqual(hh, k["hinge"][1])
        # the arm's plate in front of the lip and the neck block, the finger behind it beside the cap
        dp = d["depth"]
        self.assertGreater(dp["claw_plate"], max(dp["lip"], dp["ring"], dp["strip"]))
        self.assertLess(max(u for u, _h in d["header"]["pts"]), k["hinge"][0] - k["knuckle"])
        # the game's look opens them by the same angle and pulls by the same length
        look = (common.ROOT / "godot" / "socket" / "socket.gd").read_text(encoding="utf-8")
        self.assertEqual(float(re.search(r"CLAW_OPEN_DEG := ([\d.]+)", look).group(1)), k["open"])
        self.assertEqual(float(re.search(r"PULL_CM := ([\d.]+)", look).group(1)), k["pull"])

    def test_clip_cuts_a_square_in_two(self) -> None:
        sq = [(0.0, 10.0), (10.0, 10.0), (10.0, 0.0), (0.0, 0.0)]
        up = socket_drawing.clip(sq, (0.0, 5.0), (10.0, 5.0), True, 1.0)
        down = socket_drawing.clip(sq, (0.0, 5.0), (10.0, 5.0), False, 1.0)
        self.assertEqual(sorted({round(h, 6) for _u, h in up}), [5.5, 10.0])
        self.assertEqual(sorted({round(h, 6) for _u, h in down}), [0.0, 4.5])

    def test_offset_moves_a_clockwise_loop_outward(self) -> None:
        sq = socket_drawing.loop([[0.0, 10.0], [10.0, 10.0], [10.0, 0.0], [0.0, 0.0]])
        out = socket_drawing.offset(sq, 1.0)
        self.assertEqual([tuple(round(c, 6) for c in p) for p in out],
                         [(0.0, 11.0), (11.0, 11.0), (11.0, -1.0), (0.0, -1.0), (-11.0, -1.0), (-11.0, 11.0)])


class CrystalSocketAsset(unittest.TestCase):
    def test_manifest_is_valid(self) -> None:
        data, problem = _manifest.load(ASSET / "manifest.toml")
        self.assertIsNotNone(data, problem)
        self.assertEqual(data["id"], "crystal_socket")
        self.assertEqual(data["kind"], "prop")
        self.assertFalse(data["ai_generated"])  # built from code in Blender: no generator touched it
        self.assertTrue(data["public_repo_ok"])
        self.assertEqual(data["licence"], "own-work")
        self.assertEqual(_manifest.validate(data, "prop", "crystal_socket"), [])

    def test_glb_surfaces_size_anchor_and_colliders(self) -> None:
        glb = EXPORT / "crystal_socket.glb"
        if lfs_pointer(glb):
            self.skipTest("LFS file not fetched")
        doc = glb_json(glb)
        nodes = {n["name"]: n for n in doc["nodes"]}
        body = doc["meshes"][nodes["crystal_socket"]["mesh"]]
        self.assertEqual({doc["materials"][p["material"]]["name"] for p in body["primitives"]}, SURFACES)
        # socket-3: the claws are leaves on their hinges, closed (no rotation), each with its own collider
        placed = [(body["primitives"], [0.0, 0.0, 0.0])]
        for name in CLAWS:
            claw = nodes[name]
            self.assertNotIn("rotation", claw)
            self.assertAlmostEqual(abs(claw["translation"][0]), 0.0537, delta=1e-4)
            self.assertAlmostEqual(claw["translation"][1], 1.6279, delta=1e-4)
            kids = [doc["nodes"][i]["name"] for i in claw.get("children", [])]
            self.assertTrue(any(k.startswith("crystal_socket_col") and k.endswith("-convcolonly") for k in kids), kids)
            placed.append((doc["meshes"][claw["mesh"]]["primitives"], claw["translation"]))
        self.assertGreater(nodes["claw_r"]["translation"][0], 0.0)
        prims = [p for ps, _t in placed for p in ps]
        self.assertLessEqual(sum(doc["accessors"][p["indices"]]["count"] // 3 for p in prims), TRIANGLES)
        lo = [min(doc["accessors"][p["attributes"]["POSITION"]]["min"][i] + t[i] for ps, t in placed for p in ps)
              for i in range(3)]
        hi = [max(doc["accessors"][p["attributes"]["POSITION"]]["max"][i] + t[i] for ps, t in placed for p in ps)
              for i in range(3)]
        self.assertAlmostEqual(lo[2], 0.0, delta=0.0005)  # glTF +Z out of the wall: the back on the wall's face
        self.assertAlmostEqual(hi[2], 0.222, delta=0.002)  # the claws' tips, 22.2 cm
        self.assertAlmostEqual(hi[0] - lo[0], 0.467, delta=0.002)
        self.assertAlmostEqual(lo[1], 0.874, delta=0.002)
        self.assertAlmostEqual(hi[1], 1.748, delta=0.002)
        self.assertNotIn("images", doc)
        anchor = nodes["crystal_anchor"]
        self.assertNotIn("rotation", anchor)  # no tilt: the crystal slides out along +Z
        t = anchor["translation"]
        self.assertAlmostEqual(t[0], 0.0, delta=1e-5)
        self.assertAlmostEqual(t[1], 1.2255, delta=1e-4)  # the crystal's tip: its middle at MOUNT 140
        self.assertAlmostEqual(t[2], 0.17, delta=1e-5)
        cols = [n for n in nodes if n.endswith("-convcolonly")]
        self.assertGreaterEqual(len(cols), 4)
        self.assertTrue(all(n.startswith("crystal_socket_col") for n in cols))

    def test_shipped_glb_is_the_recorded_build(self) -> None:
        glb = EXPORT / "crystal_socket.glb"
        if lfs_pointer(glb):
            self.skipTest("LFS file not fetched")
        data, _ = _manifest.load(ASSET / "manifest.toml")
        recorded = {r["file"]: r["sha256"] for r in data["raw"]}
        built = next(sha for name, sha in recorded.items() if name.endswith("/crystal_socket.glb"))
        self.assertEqual(hashlib.sha256(glb.read_bytes()).hexdigest(), built)

    def test_report_records_clean_validation_and_checks(self) -> None:
        report = json.loads((ASSET / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["gltf_validator"]["numErrors"], 0)
        self.assertEqual(report["gltf_validator"]["numWarnings"], 0)
        c = report["checks"]
        # fix2 (#321's review, minor 8): every number present and every sweep and list as long as the build makes
        # it, so a check that never ran fails here instead of passing as clean
        for key in ("claw_gap_cm", "tip_gap_cm", "header_clear_cm", "swing_clear_deg", "open_deg", "open_gap_cm"):
            self.assertIsInstance(c.get(key), (int, float), key)
        self.assertEqual(len(c["pull_out_pairs_per_2cm"]), 15)       # 2 .. 30 cm out
        self.assertEqual(len(c["open_pull_pairs_per_2cm"]), 16)      # 0 .. 30 cm out, the claws open
        self.assertEqual(len(c["swing_pairs_per_deg"]), 41)          # 0 .. 40 degrees
        self.assertTrue(set(c["parts"]) >= {"plate", "claws", "collar"}, c.get("parts"))  # the parts checked
        self.assertTrue(0.0 <= c["claw_gap_cm"] <= 0.06, c["claw_gap_cm"])
        self.assertTrue(0.0 <= c["tip_gap_cm"] <= 0.6, c["tip_gap_cm"])
        self.assertGreater(c["header_clear_cm"], 0.0)
        self.assertEqual(c["crystal_vs_socket_pairs"], 0)
        self.assertEqual(c["crystal_vs_colliders_pairs"], 0)
        self.assertEqual(set(c["pull_out_pairs_per_2cm"]), {0})  # it slides straight out
        self.assertEqual(c["parts_touching_nothing"], [])
        self.assertEqual(c["coplanar_overlaps"], [])
        # socket-3: the claws swing clear of the frame to past their open angle, clear of the crystal, and the
        # crystal slides out past them open
        # the sweep met the frame (one that met nothing proves nothing: socket_build.swing() records None then), and
        # the clear angle is the last one before it
        first = next((i for i, n in enumerate(c["swing_pairs_per_deg"]) if n), None)
        self.assertIsNotNone(first, "the claws' sweep met nothing up to 40 degrees: the check did not run")
        self.assertEqual(c["swing_clear_deg"], first - 1)
        self.assertGreaterEqual(c["swing_clear_deg"], c["open_deg"])
        self.assertEqual(c["closed_vs_body_pairs"], 0)
        self.assertEqual(c["open_vs_body_pairs"], 0)
        self.assertEqual(c["open_vs_crystal_pairs"], 0)
        self.assertGreater(c["open_gap_cm"], 0.0)
        self.assertEqual(set(c["open_pull_pairs_per_2cm"]), {0})

    def test_shipped_look_matches_the_godot_files(self) -> None:
        for name in MATERIAL_FILES:
            shipped = (EXPORT / name).read_text(encoding="utf-8")
            self.assertEqual(shipped, (common.ROOT / "godot" / "socket" / name).read_text(encoding="utf-8"), name)
        # the stations share one metal: the socket's is the console's
        self.assertEqual((common.ROOT / "godot" / "socket" / "socket_metal.gdshader").read_text(encoding="utf-8"),
                         (common.ROOT / "godot" / "console" / "console_metal.gdshader").read_text(encoding="utf-8"))
        look = (EXPORT / "socket.gd").read_text(encoding="utf-8")
        for surface in SURFACES:
            self.assertIn(f'"{surface}"', look)
        # fix2 (#321's review, minor 9): apply() closes the claws on every call, just before the state
        apply = look[look.index("static func apply("):look.index("static func set_claws(")]
        self.assertRegex(apply, r'set_claws\(look, 0\.0\)[^\n]*\n\tset_state\(look, "charged"\)')


if __name__ == "__main__":
    unittest.main()
