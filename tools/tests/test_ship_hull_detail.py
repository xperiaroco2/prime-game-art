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
import ship_hull_j as J  # noqa: E402
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


    def test_the_throats_covered_part_cuts_only_the_belly(self) -> None:
        # rebuild F: the room cut takes J's belly out of the throat's covered part (between the walls' outer faces,
        # roof line to the hall's corners) and leaves every top facet whole (a sliver of it once went: a hole)
        cut = S.cutters()
        sides, ky = cut["notch"][:2], S.TH_PTS[2][1]
        surf = S.surface()
        for poly, _n, kind in surf:
            if kind != "belly":
                continue
            c = [sum(p[i] for p in poly) / len(poly) for i in range(3)]
            inside = all(S._dot(n, c) <= d for n, d in sides) and S.TH_ROOF_Y <= c[1] <= ky and c[2] > S.SLAB
            self.assertFalse(inside, f"a belly facet in the throat at ({c[0]:.2f}, {c[1]:.2f}, {c[2]:.2f})")
        whole = 0.0
        for n, _d, poly in S.facets():
            if n[2] >= -0.05:
                whole += sum(S.area(b) for a in S._subtract(poly, cut["notch"]) for b in S._subtract(a, cut["belly"]))
        top = sum(S.area(p) for p, _n, kind in surf if kind == "top")
        self.assertAlmostEqual(top, whole, delta=1e-6)

    def test_the_jamb_caps(self) -> None:
        caps = J.jamb_caps()
        self.assertEqual(len(caps), 8)
        (mx, my), (kx, ky) = S.TH_PTS[1], S.TH_PTS[2]
        k = 1.0 / ((ky - my) / math.hypot(kx - mx, ky - my))
        y = S.TH_ROOF_Y + J.CAP_BACK
        xi = mx + (kx - mx) * (y - my) / (ky - my)
        xo = xi + S.WALL * k + 0.02
        x_ceil = xi - S.TH_CH[1] * k   # the upper cap's inner edge follows the chamfer in to the ceiling
        for side in (1, -1):
            mine = [(v, f) for v, f in caps if all(side * x > 0 for x, _y, _h in v)]
            self.assertEqual(len(mine), 4)
            normals = []
            for v, faces in mine:
                lo = xi if len(v) == 4 else x_ceil   # the lower cap: walls' inner face to past the notch's side
                for x, _y, _h in v:
                    self.assertGreaterEqual(side * x, lo - 1e-9)
                    self.assertLessEqual(side * x, xo + 1e-9)
                normals.append(S._newell([v[i] for i in faces[0]])[1])
            self.assertEqual(sorted(n > 0 for n in normals), [False, False, True, True], "both windings per side")

if __name__ == "__main__":
    unittest.main()
