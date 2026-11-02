"""The lobby's pinball machine (art #374): its drawing's numbers (tools/blender/pinball_dims.toml) against the game's
table contract (prime-game 77ac43d5 scenes/pinball/pinball_table.tscn and its PinballTableSpec), the spec's own sums
(the field's front edge height, the inside width, the rails over the walls, the backbox's top, the screen inside it),
and the GLBs' node names and the table nodes' transforms when the raw build is there (skipped without it)."""

from __future__ import annotations

import json
import math
import re
import struct
import tomllib
import unittest

from runner import common

DIMS = tomllib.loads((common.ROOT / "tools" / "blender" / "pinball_dims.toml").read_text(encoding="utf-8"))
RAW = common.raw_dir() / "lobby" / "pinball"
BUILD = RAW / "v1"
CONTRACT_BODIES = ("WallLeft", "WallRight", "WallTop", "InlaneLeft", "InlaneRight", "FlipperLeft", "FlipperRight",
                   "Bumper", "Kicker", "Target")
# the contract's node origins (x, y, z in m) and yaw (deg), from pinball_table.tscn at prime-game 77ac43d5
CONTRACT = {
    "WallLeft": ((-0.33, 0.03, 0.0), 0.0), "WallRight": ((0.33, 0.03, 0.0), 0.0), "WallTop": ((0.0, 0.03, -0.63), 0.0),
    "InlaneLeft": ((-0.22, 0.03, 0.37), -41.2), "InlaneRight": ((0.22, 0.03, 0.37), 41.2),
    "FlipperLeft": ((-0.13, 0.03, 0.45), -25.0), "FlipperRight": ((0.13, 0.03, 0.45), 25.0),
    "Bumper": ((-0.1, 0.03, -0.25), 0.0), "Kicker": ((0.12, 0.03, -0.05), 0.0), "Target": ((0.0, 0.03, -0.585), 0.0),
}


def glb_json(path) -> dict:
    data = path.read_bytes()
    magic, _, _ = struct.unpack("<4sII", data[:12])
    assert magic == b"glTF", path
    length, kind = struct.unpack("<I4s", data[12:20])
    assert kind == b"JSON", path
    return json.loads(data[20:20 + length])


def yaw_of(q: list) -> float:
    """A quaternion's turn about +y in degrees (it must have no other component)."""
    x, y, z, w = q
    assert abs(x) < 1e-4 and abs(z) < 1e-4, q
    return math.degrees(2.0 * math.atan2(y, w))


class PinballSpec(unittest.TestCase):
    def test_contract_numbers(self) -> None:
        k = DIMS["contract"]
        self.assertEqual(k["field"], [72.0, 130.0])
        self.assertEqual(k["ball_r"], 3.0)
        self.assertEqual(k["wall_side"], [6.0, 10.0, 130.0])
        self.assertEqual(k["wall_top"], [72.0, 10.0, 6.0])
        self.assertEqual(k["flipper"], [8.5, 5.0, 2.0])
        self.assertEqual((k["flipper_swing_deg"], k["flipper_speed_deg_s"]), (50.0, 1500.0))
        for name, ((x, y, z), yaw) in CONTRACT.items():
            got = {"WallLeft": (-k["wall_side_x"], 0.0), "WallRight": (k["wall_side_x"], 0.0),
                   "WallTop": (0.0, k["wall_top_z"]), "InlaneLeft": (-k["inlane_at"][0], k["inlane_at"][1]),
                   "InlaneRight": k["inlane_at"], "FlipperLeft": (-k["flipper_at"][0], k["flipper_at"][1]),
                   "FlipperRight": k["flipper_at"], "Bumper": k["bumper_at"], "Kicker": k["kicker_at"],
                   "Target": (0.0, k["target_z"])}[name]
            self.assertAlmostEqual(got[0] / 100, x, places=4, msg=name)
            self.assertAlmostEqual(got[1] / 100, z, places=4, msg=name)
            self.assertAlmostEqual(k["body_y"] / 100, y, places=4, msg=name)

    def test_contract_copy_matches(self) -> None:
        """The raw folder's copy of pinball_table.tscn holds the origins above (skipped without the raw folder)."""
        tscn = RAW / "ref" / "pinball_table.tscn"
        if not tscn.is_file():
            self.skipTest(f"no {tscn}")
        text = tscn.read_text(encoding="utf-8")
        for name, ((x, y, z), yaw) in CONTRACT.items():
            m = re.search(rf'\[node name="{name}"[^\]]*parent="\."\]\ntransform = Transform3D\(([^)]*)\)', text)
            self.assertIsNotNone(m, name)
            v = [float(c) for c in m.group(1).split(",")]
            self.assertEqual(v[9:], [x, y, z], name)
            self.assertAlmostEqual(math.degrees(math.atan2(v[2], v[0])), yaw, delta=0.1, msg=name)

    def test_spec_sums(self) -> None:
        k, t, b, bb = DIMS["contract"], DIMS["table"], DIMS["body"], DIMS["backbox"]
        self.assertEqual(b["outer_w"] / 2 - b["wall_t"], k["field"][0] / 2, "the inside is the contract's field")
        self.assertLessEqual(b["rail_in"], k["wall_side_x"] - k["wall_side"][0] / 2, "the rails cover the walls")
        self.assertGreater(t["glass_y"], k["body_y"] + k["wall_side"][1] / 2, "the glass clears the walls")
        self.assertGreater(b["front_z"], k["field"][1] / 2)
        self.assertLess(b["back_z"], -k["field"][1] / 2)
        self.assertAlmostEqual(bb["y"][1], 190.0, delta=5.0)
        sw, sh = bb["screen"]
        self.assertLess(sw, bb["w"])
        self.assertLess(bb["screen_y"] + sh / 2, bb["y"][1] - bb["cap_h"])
        self.assertGreater(bb["screen_y"] - sh / 2, bb["medallion_y"] + bb["medallion_r"][0])
        self.assertGreaterEqual(sh, 3 * 9.0, "room for three text lines of about 9 cm")
        tilt = math.radians(t["tilt_deg"])
        far = t["front_y"] + k["field"][1] * math.sin(tilt)
        self.assertLess(far, bb["y"][0] + 1.0, "the field's far end stays under the backbox")
        self.assertEqual(DIMS["markers"]["closeup_down_deg"], 55.0)
        self.assertEqual(DIMS["markers"]["closeup_fov"], 50.0)


class PinballGlbs(unittest.TestCase):
    def setUp(self) -> None:
        if not (BUILD / "pinball.glb").is_file() or not (BUILD / "pinball_table.glb").is_file():
            self.skipTest(f"no raw build in {BUILD}")

    def test_cabinet_names(self) -> None:
        names = {n.get("name") for n in glb_json(BUILD / "pinball.glb")["nodes"]}
        self.assertTrue({"pinball", "TableMount", "CloseUp", "Display"} <= names, names)

    def test_table_nodes(self) -> None:
        g = glb_json(BUILD / "pinball_table.glb")
        nodes = {n["name"]: n for n in g["nodes"]}
        self.assertTrue(set(CONTRACT_BODIES) | {"Playfield", "Glass", "BallStart", "Drain"} <= set(nodes), set(nodes))
        for name, ((x, y, z), yaw) in CONTRACT.items():
            n = nodes[name]
            self.assertIn("mesh", n, name)
            for a, b in zip(n.get("translation", [0, 0, 0]), (x, y, z)):
                self.assertAlmostEqual(a, b, places=4, msg=name)
            self.assertAlmostEqual(yaw_of(n.get("rotation", [0, 0, 0, 1])), yaw, delta=0.15, msg=name)


if __name__ == "__main__":
    unittest.main()
