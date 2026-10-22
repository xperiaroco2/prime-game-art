"""The hull's details on the hull J (art #263 rebuild B; docs/ship.md "The hull's details"): the canopies sit on the
hull with a low collar, the nozzle pods stay out of the hall and end where J's do, and no blade, stripe, tip window,
pod housing, hatch, seam line or scratch is left. Plain Python, no Blender."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

from runner import ship_layout as sl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import ship_hull  # noqa: E402,F401  (imports the skin and the details in their order)
import ship_hull_detail as D  # noqa: E402
import ship_hull_shape as S  # noqa: E402

LAYOUT = sl.load()
HALL = next(r for r in LAYOUT["rooms"] if r["id"] == "hall")


def verts(parts):
    return [v for p in parts for v in p["verts"]]


class ShipHullDetailTest(unittest.TestCase):
    def test_the_canopies_sit_on_the_hull(self) -> None:
        for side in (-1.0, 1.0):
            for part in ("glass", "fairing", "glow"):
                for x, y, h in verts(D.canopy({"side": side, "part": part}, LAYOUT)):
                    top = D.skin_h(x, y)
                    if top is not None:
                        self.assertGreater(h, top - 0.1, f"canopy {part} under the hull at ({x:.2f}, {y:.2f})")
            glass = verts(D.canopy({"side": side, "part": "glass"}, LAYOUT))
            self.assertLess(max(h for _x, _y, h in glass) - D.skin_h(side * D.CANOPY["x"], D.CANOPY["y"]), 0.95)

    def test_the_pods_stay_out_of_the_hall_and_end_as_js(self) -> None:
        pods = {p["id"]: p for p in LAYOUT["pieces"] if p["builder"] in ("nozzle_pod", "pod_ring")}
        build = {"nozzle_pod": D.nozzle_pod, "pod_ring": D.pod_ring}
        hx, hy = HALL["centre"]
        ends = []
        for pid, at, yaw in LAYOUT["place"]:
            if pid in pods:
                c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
                for x, y, _h in verts(build[pods[pid]["builder"]](pods[pid]["args"], LAYOUT)):
                    px, py = at[0] + c * x - s * y, at[1] + s * x + c * y   # every vertex where it is placed
                    self.assertGreater(math.hypot(px - hx, py - hy), HALL["radius"] + 0.2, f"{pid} in the hall")
            if pid in pods and pods[pid]["builder"] == "nozzle_pod":
                ends.append(at[1] + float(pods[pid]["args"]["length"]) + LAYOUT["hull"]["pod_tail_m"])
        self.assertEqual(len(ends), 3)
        self.assertAlmostEqual(max(ends), max(S.pod_ends()), delta=0.01)
        self.assertAlmostEqual(min(ends), min(S.pod_ends()), delta=0.01)

    def test_the_pod_tail_is_the_builders(self) -> None:
        ring = verts(D.pod_ring({"r": 1.05, "length": 3.25}, LAYOUT))
        self.assertAlmostEqual(max(y for _x, y, _h in ring) - 3.25, LAYOUT["hull"]["pod_tail_m"], delta=0.01)

    def test_no_strips_windows_hatches_seams_or_scratches(self) -> None:
        builders = {p["builder"] for p in LAYOUT["pieces"]}
        for gone in ("lead_blade", "smooth_stripes", "smooth_window", "window_frame", "pod_housing", "hatches",
                     "seam_lines", "hull_skin", "smooth_skin"):
            self.assertNotIn(gone, builders)
            self.assertFalse(hasattr(D, gone), gone)


if __name__ == "__main__":
    unittest.main()
