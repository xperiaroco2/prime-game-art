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

    def test_the_pods_stay_out_of_the_hall_and_end_as_ps(self) -> None:
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
        # lens step 2 (P, a union of parts): no hole in the top over the throat's covered part: every plan point
        # there lies under a top face
        tops = [poly for poly, n, kind in surf if kind == "top" and n[2] > 0.05]
        (mx, my), (kx, ky) = S.TH_PTS[1], S.TH_PTS[2]
        for i in range(1, 10):
            y = S.TH_ROOF_Y + (ky - S.TH_ROOF_Y) * i / 10
            xw = mx + (kx - mx) * (y - my) / (ky - my) + S.WALL
            for j in range(-4, 5):
                x = xw * j / 5
                self.assertTrue(any(sl.inside([(q[0], q[1]) for q in poly], (x, y)) for poly in tops),
                                f"no top face over ({x:.2f}, {y:.2f})")

    def test_the_outside_is_all_silver_and_every_strip_plated(self) -> None:
        # the engineer, 2026-10-22: the belly's leg_metal plates and the open slivers (the dark under-skin through
        # them) read as black patches and streaks; the top and the belly are in v1's silvers only, and every piece of
        # every facet is a plate (a sliver laid flush), so no outer facet shows the under-skin
        silvers = {"hull_silver", "ext_silver_b", "ext_silver_c"}
        for kind in ("top", "belly"):
            self.assertLessEqual(set(J.MATS[kind]), silvers, kind)
            mats = {p["mat"] for p in J.j_skin({"part": kind}, LAYOUT) if not p["name"].endswith("_seam")}
            self.assertLessEqual(mats, silvers, kind)
        slivers = 0
        for poly, n, kind in S.surface():
            if kind not in ("top", "belly"):
                continue
            qs = J.plates(poly, n)
            self.assertAlmostEqual(sum(S.area(q) for q in qs), S.area(poly), delta=1e-4 + 1e-3 * S.area(poly))
            for q in qs:
                if J.width(q) <= J.SLIVER:   # a sliver is laid flush: its face is its outline, no inset to flip
                    slivers += 1
                    self.assertEqual(J.lay(q)[0][:len(q)], [tuple(x) for x in q])
        self.assertGreater(slivers, 0)   # the cut makes slivers on J: they are laid, not left open

    def test_the_plates_run_in_rows_across_the_facets(self) -> None:
        # lens polish: every face is covered by its cells' pieces; a piece's edge is flush only on a facet edge whose
        # neighbour bends less than the zone's crease; the lens's rim has its three bands and seams every 36 deg; a lens
        # plate's pieces share one silver and the lens parts are shaded smooth
        surf = S.surface()
        pieces = J.skin_pieces()
        area: dict = {}
        for _k, _zone, _cell, i, q, flags in pieces:
            area[i] = area.get(i, 0.0) + S.area(q)
            self.assertEqual(len(flags), len(q))
        for i, (poly, _n, _kind) in enumerate(surf):
            self.assertAlmostEqual(area.get(i, 0.0), S.area(poly), delta=1e-4 + 1e-3 * S.area(poly))
        edges = J.Edges(surf)
        for _k, zone, _cell, i, q, flags in pieces[::7]:
            for (a, b), seam in zip(zip(q, q[1:] + q[:1]), flags):
                if not seam:
                    own, bend = edges.bend(i, tuple(0.5 * (a[t] + b[t]) for t in range(3)))
                    self.assertTrue(own)
                    self.assertLessEqual(bend, J.CREASE[zone])
        rim = {c[3] for _k, z, c, *_ in pieces if z == "lens" and c[2] == "rim"}
        self.assertEqual(rim, {0, 1, 2})
        self.assertLessEqual(len({c[4] for _k, z, c, *_ in pieces if z == "lens" and c[2] == "rim"}), 10)
        self.assertLess(len({p[2] for p in pieces}), len(pieces) / 4)   # plates span facets: fewer cells than pieces
        parts = J.j_skin({"part": "top"}, LAYOUT)
        lens = [p for p in parts if p["name"].endswith("_lens")]
        self.assertTrue(lens)
        self.assertTrue(all(p["smooth_deg"] == J.CREASE["lens"] for p in lens))

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
