"""The hull's details (art #263, hull lane step 2; docs/ship.md "The hull's details"): the canopies sit on the skin
with a low collar and never reach into the hall, the nozzle pods and their housing stay out of the hall, the lead blade
runs from the body to the swept tip. Pure Python (tools/blender/ship_hull_detail.py needs no Blender)."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

from runner import ship_layout as sl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import ship_hull  # noqa: E402,F401  (imports the skin and the details in their order)
import ship_hull_detail as D  # noqa: E402
import ship_hull_skin as S  # noqa: E402

LAYOUT = sl.load()
HALL = next(r for r in LAYOUT["rooms"] if r["id"] == "hall")


def verts(parts):
    return [v for p in parts for v in p["verts"]]


class ShipHullDetailTest(unittest.TestCase):
    def test_the_canopies_sit_on_the_skin(self) -> None:
        for side in (1.0, -1.0):
            ts, rim, glass, deck, _outline = D._canopy_frame(side)
            collar = [deck(x, y) - D.skin_h(x, y) for x, y in rim]
            self.assertLess(sum(collar) / len(collar), 0.6, "the canopy's fairing stands tall over the skin")
            for x, y in glass:
                self.assertGreaterEqual(deck(x, y), D.skin_h(x, y), f"glass base under the skin at ({x:.2f}, {y:.2f})")
            for part in ("glass", "fairing", "glow"):
                for x, y, h in verts(D.canopy({"side": side, "part": part}, LAYOUT)):
                    sh = D.skin_h(x, y)
                    if sh is not None:
                        self.assertGreater(h, sh - 0.1, f"canopy {part} reaches under the skin at ({x:.2f}, {y:.2f})")

    def test_the_pods_and_housing_stay_out_of_the_hall(self) -> None:
        r_hall = float(HALL["radius"]) + 0.2
        pods = {"nozzle_pod_outer": (2.75, 3.5, 2.15, 1.05, 3.6), "nozzle_pod_mid": (0.0, 3.9, 2.45, 1.2, 4.0)}
        for _pid, (x0, y0, h0, r, ln) in pods.items():
            for x, y, h in verts(D.nozzle_pod({"r": r, "length": ln}, LAYOUT)):
                for sx in ((1, -1) if x0 else (1,)):
                    self.assertGreater(math.hypot(sx * x0 + x, y0 + y), r_hall, "a pod reaches into the hall")
        for x, y, h in verts(D.pod_housing({}, LAYOUT)):
            sh = D.skin_h(x, y)
            self.assertTrue(math.hypot(x, y) > r_hall or (sh is not None and h > sh - 0.1),
                            f"the housing reaches into the hall at ({x:.2f}, {y:.2f}, {h:.2f})")

    def test_the_lead_blade_runs_to_the_tip(self) -> None:
        path = D._lead_path(1.0)
        self.assertLess(path[0][0], 2.5)
        self.assertAlmostEqual(path[-1][0], S.TIP_X + max(dx for dx, _dy in S.VARIANTS["F"]["tip"]), places=3)
        xs = [p[0] for p in path]
        self.assertEqual(xs, sorted(xs), "the blade turns back on itself")


if __name__ == "__main__":
    unittest.main()
