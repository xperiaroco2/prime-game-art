"""The bench in Godot 4.7.2 (art #212; godot/bench/bench.gd): two copies of slice_m1 in the ring, a few frames per
variant in an off-screen window; bench.json with a row per variant, the GPU named, the report and the sheet written.
Skips without Godot, a display or the GLB."""

import argparse
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runner import common, pins  # noqa: E402
from runner.commands import bench  # noqa: E402

GLB = common.ROOT / "assets" / "character" / "slice_m1" / "export" / "slice_m1.glb"
HAVE_GODOT = common.tool_path(pins.GODOT_ENV, None) is not None
HAVE_GLB = GLB.is_file() and GLB.stat().st_size > 100_000
HAVE_DISPLAY = os.name == "nt" or bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


@unittest.skipUnless(HAVE_GODOT and HAVE_GLB and HAVE_DISPLAY, "needs Godot, a display and slice_m1.glb")
class BenchTest(unittest.TestCase):
    def test_two_copies(self) -> None:
        parser = argparse.ArgumentParser()
        bench.add_arguments(parser)
        common.OUT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=common.OUT) as tmp:
            args = parser.parse_args([str(GLB), "--copies", "2", "--frames", "10", "--warmup", "5", "--out", tmp])
            self.assertEqual(bench.run(args), 0)
            record = json.loads((Path(tmp) / "bench.json").read_text(encoding="utf-8"))
            self.assertTrue((Path(tmp) / "bench.md").is_file())
            self.assertTrue((Path(tmp) / "sheet.png").is_file())
        self.assertEqual([r["id"] for r in record["rows"]], ["empty", "slice_m1_x2_auto_full", "slice_m1_x2_off_full"])
        self.assertTrue(record["adapter"])
        for row in record["rows"][1:]:
            self.assertGreater(row["gpu_ms"], 0.0)
            self.assertGreater(row["primitives"], record["rows"][0]["primitives"])
            self.assertGreater(row["frame_ms"], 0.0)
            self.assertGreaterEqual(row["process_ms"], 0.0)
            self.assertEqual(row["beyond_hand_lod"], 0)  # two copies stand within a few metres
        self.assertGreaterEqual(record["rows"][2]["primitives"], record["rows"][1]["primitives"])  # LOD0 draws the most


if __name__ == "__main__":
    unittest.main()
