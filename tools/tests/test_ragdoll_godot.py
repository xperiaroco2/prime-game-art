"""The ragdoll proof in Godot 4.7.2 on Jolt Physics (art #115; godot/ragdoll/fall.gd): slice_m1's bodies built from
its ragdoll data by the reference builder fall from the standing pose at 3 m/s, headless; no NaN, the joints within
their limits, at rest on the floor in time, no explosion, the downed layer passing a player through, the sockets
following their bones. Skips without Godot or the GLB."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runner import common, pins  # noqa: E402
from runner.commands import ragdoll  # noqa: E402

ASSET = common.ROOT / "assets" / "character" / "slice_m1"
GLB = ASSET / "export" / "slice_m1.glb"
DATA = ASSET / "export" / "slice_m1.ragdoll.json"
HAVE_GODOT = common.tool_path(pins.GODOT_ENV, None) is not None
HAVE_GLB = GLB.is_file() and GLB.stat().st_size > 100_000


@unittest.skipUnless(HAVE_GODOT and HAVE_GLB, "needs Godot and slice_m1.glb")
class FallTest(unittest.TestCase):
    def test_the_fall(self) -> None:
        common.OUT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=common.OUT) as tmp:
            report = ragdoll.fall(GLB, DATA, Path(tmp), False)
        self.assertEqual(report["failures"], [], report["worst"])
        self.assertEqual((report["bodies"], report["joints"]), (16, 15))
        self.assertEqual(report["physics_engine"], "Jolt Physics")
        self.assertLess(report["worst"]["socket_m"], 0.002)
        self.assertGreaterEqual(report["rest_s"], 0.0)


if __name__ == "__main__":
    unittest.main()
