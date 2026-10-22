"""The hull's details on the smooth skin (art #263 v2, hull lane step 2; docs/ship.md "The hull's details"): the
canopies sit on the skin with a low collar, the nozzle pods and their housing stay out of the hall, the lead blade runs
along the lead edge to the curled tip, the stripes and the tip window's glass sit on the skin, and no hatch, seam line
or scratch is placed. Pure Python (tools/blender/ship_hull_detail.py needs no Blender)."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

from runner import ship_layout as sl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import ship_hull  # noqa: E402,F401  (imports the skin and the details in their order)
import ship_hull_detail as D  # noqa: E402
import ship_hull_smooth as SM  # noqa: E402

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
        pods = {"nozzle_pod_outer": (2.75, 3.85, 2.15, 1.05, 3.25), "nozzle_pod_mid": (0.0, 4.25, 2.45, 1.2, 3.65)}
        for _pid, (x0, y0, h0, r, ln) in pods.items():
            for x, y, h in verts(D.nozzle_pod({"r": r, "length": ln}, LAYOUT)):
                for sx in ((1, -1) if x0 else (1,)):
                    self.assertGreater(math.hypot(sx * x0 + x, y0 + y), r_hall, "a pod reaches into the hall")
        for x, y, h in verts(D.pod_housing({}, LAYOUT)):
            sh = D.skin_h(x, y)
            self.assertTrue(math.hypot(x, y) > r_hall or (sh is not None and h > sh - 0.1),
                            f"the housing reaches into the hall at ({x:.2f}, {y:.2f}, {h:.2f})")

    def test_the_layouts_stern_numbers_are_the_builders(self) -> None:
        """ship.toml hull.trail_y and pod_tail_m, which `ship --check` measures the length with, equal the geometry."""
        hull = LAYOUT["hull"]
        for ln in (3.6, 4.0):
            tail = max(max(y for _x, y, _h in verts(build({"r": 1.1, "length": ln}, LAYOUT))) - ln
                       for build in (D.nozzle_pod, D.pod_ring))
            self.assertAlmostEqual(tail, hull["pod_tail_m"], places=3)
        housing = max(y for _x, y, _h in verts(D.pod_housing({}, LAYOUT)))
        trail = max(SM.trail(x / 20, SM.VARIANTS[SM.DEFAULT]) for x in range(int(SM.SPAN_X * 20) + 1))
        self.assertAlmostEqual(hull["trail_y"], max(housing, trail), places=3)

    def test_the_lead_blade_runs_to_the_tip(self) -> None:
        var = SM.VARIANTS[SM.DEFAULT]
        path = D._lead_path(1.0)
        self.assertLess(path[0][0], 3.0)
        self.assertGreater(path[-1][0], SM.SPAN_X - 0.3)
        xs = [p[0] for p in path]
        self.assertEqual(xs, sorted(xs), "the blade turns back on itself")
        for x, y, h in path:
            self.assertAlmostEqual(y, SM.lead(x, var), places=6)
            self.assertAlmostEqual(h, SM.heights(x, y, var)[0], delta=0.05, msg=f"the blade leaves the edge at x {x:.2f}")

    def test_the_stripes_and_window_sit_on_the_skin(self) -> None:
        var = SM.VARIANTS[SM.DEFAULT]
        for side in (1.0, -1.0):
            for v, _f in D.stripe_bars(side):
                outer = v[:len(v) // 2]
                for x, y, h in outer:
                    top, bot = SM.heights(x, y, var)
                    self.assertTrue(h > top - 0.01 or h < bot + 0.01 or y < SM.lead(x, var),
                                    f"a stripe sinks into the skin at ({x:.2f}, {y:.2f}, {h:.2f})")
            glass = next(p for p in D.smooth_window({"side": side}, LAYOUT) if p["name"] == "window_glass")
            for x, y, h in glass["verts"]:
                self.assertGreater(side * x, SM.TIP_X)
                self.assertTrue(SM.SILL - 0.1 < h < SM.HEAD + 0.1, f"window glass at h {h:.2f}")

    def test_no_hatches_seams_or_scratches(self) -> None:
        builders = {p["builder"] for p in LAYOUT["pieces"] if p.get("lane") == "exterior"} or             {p["builder"] for p in LAYOUT["pieces"]}
        for gone in ("hatches", "seam_lines", "hull_skin", "skin_stripes", "tip_window"):
            self.assertNotIn(gone, builders)


if __name__ == "__main__":
    unittest.main()
