"""The M8 clearing's ground package (prime-game#1704, art #263): plain checks, no Blender or Godot."""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "review"))

import clearing_ground_looks as looks  # noqa: E402

ASSET = ROOT / "assets" / "environment" / "clearing_ground"


class ClearingGroundPackage(unittest.TestCase):
    def test_shader_is_the_review_shader(self):
        # the package ships exactly the shader the engineer picked from
        self.assertEqual((ASSET / "export" / "clearing_ground.gdshader").read_bytes(),
                         (ROOT / "godot" / "clearing" / "ground.gdshader").read_bytes())

    def test_material_is_the_pad_at_the_ship(self):
        tres = (ASSET / "export" / "clearing_ground.tres").read_text(encoding="utf-8")
        self.assertIn('path="res://assets/environment/clearing/clearing_ground.gdshader"', tres)
        self.assertIn("shader_parameter/pad = true", tres)
        m = re.search(r"shader_parameter/centre = Vector2\(([-\d.]+), ([-\d.]+)\)", tres)
        self.assertIsNotNone(m)
        self.assertEqual((float(m[1]), float(m[2])), (looks.SHIP_AT[0], looks.SHIP_AT[2]))
        self.assertEqual(looks.GAME_DIR, "res://assets/environment/clearing/")
        self.assertNotIn("sampler2D", (ASSET / "export" / "clearing_ground.gdshader").read_text(encoding="utf-8"))

    def test_package_json_lists_the_files(self):
        meta = json.loads((ASSET / "package.json").read_text(encoding="utf-8"))
        names = sorted(f["file"] for f in meta["files"])
        self.assertEqual(names, sorted(f"export/{n}" for n in looks.PKG_FILES))
        for f in meta["files"]:
            self.assertTrue((ASSET / f["file"]).is_file(), f["file"])
            self.assertEqual(f["game_path"], looks.GAME_DIR + Path(f["file"]).name)

    def test_report_matches_the_files(self):
        import hashlib
        report = json.loads((ASSET / "report.json").read_text(encoding="utf-8"))
        for rel, info in report["files"].items():
            data = (ASSET / rel).read_bytes()
            self.assertEqual(info["sha256"], hashlib.sha256(data).hexdigest(), rel)
        self.assertIn("package", report["gpu_ms"])
        self.assertEqual(set(report["package_vs_pad"]), set(report["gpu_ms"]["package"]))   # every view compared
        for view, d in report["package_vs_pad"].items():
            self.assertLess(d["mean_abs"], 1.0, view)   # the box's top draws as the review's plane

    def test_handoff_names_the_cost_and_the_swap(self):
        text = (ASSET / "HANDOFF.md").read_text(encoding="utf-8")
        self.assertIn("levels/kit/greybox_floor_garden.tres", text)
        self.assertIn("levels/clearing/rooms/ground.tscn", text)
        self.assertIn("GPU", text)


if __name__ == "__main__":
    unittest.main()
