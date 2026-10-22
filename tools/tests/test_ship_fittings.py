"""The hull's fittings (art #263, details 2; docs/ship.md "Details 2"): the tail's portholes stand where no room or pod
lies behind the skin, every fitting sits flat on one facet of the live hull, the counts and the sides are as asked.
Plain Python, no Blender."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

from runner import ship_layout as sl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import ship_hull  # noqa: E402,F401  (imports the skin and the details in their order)
import ship_hull_detail as D  # noqa: E402
import ship_hull_fittings as F  # noqa: E402
import ship_hull_shape as S  # noqa: E402

LAYOUT = sl.load()
POD_NOSE_Y = 9.6


def _flat(o, n, radius, side="top", tol=0.01):
    """Every point `radius` round o in the facet lies on the hull within tol (one facet, no bend under the fitting)."""
    u, v = F.frame(n)
    k = 0 if side == "top" else 1
    for i in range(12):
        a = 2 * math.pi * i / 12
        p = [o[j] + radius * (math.cos(a) * u[j] + math.sin(a) * v[j]) for j in range(3)]
        if abs(S.heights(p[0], p[1])[k] - p[2]) > tol:
            return False
    return True


class ShipFittingsTest(unittest.TestCase):
    def test_the_portholes_lie_on_the_tails_flanks_over_no_room(self) -> None:
        spots = F.porthole_spots()
        self.assertEqual(len(spots), 6)
        east = sorted(o for o, _n in spots if o[0] > 0)
        west = sorted((-x, y, h) for (x, y, h), _n in spots if x < 0)
        self.assertEqual(len(east), 3)
        for a, b in zip(east, west):
            self.assertAlmostEqual(math.dist(a, b), 0.0, places=6)
        rooms = S._room_points(sl.rooms(LAYOUT))
        for o, n in spots:
            self.assertGreater(abs(n[0]), 0.6, f"{o}: not on a flank")   # the steep side face, looking outward
            self.assertTrue(_flat(o, n, F.PORT_R[2] + 0.02), o)
            near = min(math.hypot(p[0] - o[0], p[1] - o[1]) for _what, p in rooms)
            self.assertGreater(near, 1.0, f"porthole at {o} over a room ({near:.2f} m)")
            self.assertLess(o[1] + F.PORT_R[2], POD_NOSE_Y - 0.5, "a porthole over a pod")
            self.assertGreater(o[1] - F.PORT_R[2], S.P_TIP[1] + S.P_RIM_R, "a porthole beside a lens")
        self.assertTrue(all(abs(o[0]) > S.P_VAULT[0] + 1.0 for o, _n in spots))   # the vault's box stays clear
        self.assertAlmostEqual(2 * F.PORT_R[0], 0.35, delta=0.02)

    def test_the_vents_mast_dome_and_hatches(self) -> None:
        vents = F.vent_spots()
        self.assertEqual(len(vents), 2)
        self.assertAlmostEqual(vents[0][0][0], -vents[1][0][0])
        for o, n in vents:
            self.assertGreater(n[2], 0.95, "a vent off the tail's top")
            self.assertLess(o[1] + F.VENT[0] / 2, POD_NOSE_Y, "a vent over a pod")
            self.assertGreater(o[1], POD_NOSE_Y - 2.0, "a vent far ahead of the pods")
            self.assertTrue(_flat(o, n, F.VENT[1] / 2 + 0.02), o)
        canopy_y = D.CANOPY["y"]
        for x, y in ((F.MAST[0], F.MAST[1]), (F.DOME[0], F.DOME[1])):
            self.assertEqual(x, 0.0)
            self.assertGreater(y, canopy_y, "the mast and dome stand behind the canopies")
            self.assertLess(y, 0.0, "the mast and dome stand on the hump's front, over the hall")
        hatches = F.hatch_spots()
        self.assertEqual([h[0] for h in hatches].count("top"), 2)
        self.assertEqual([h[0] for h in hatches].count("bottom"), 1)
        for side, o, n, length, width in hatches:
            self.assertTrue(_flat(o, n, math.hypot(length, width) / 2 + 0.02, side), o)
            self.assertLess(n[2], -0.9) if side == "bottom" else self.assertGreater(n[2], 0.9)
        tops = sorted(o[0] for side, o, *_r in hatches if side == "top")
        self.assertAlmostEqual(tops[0], -tops[1])
        self.assertGreater(tops[1], 4.5, "a fin hatch on the body")

    def test_the_hazard_stripes_and_the_pieces(self) -> None:
        parts = {p["name"]: p for p in F.hazard_stripes({}, LAYOUT)}
        yel = parts["hazard_yellow"]
        self.assertEqual(len(yel["faces"]) % 6, 0)
        n = len(yel["faces"]) // 6
        self.assertGreater(n, 30)
        hinge = LAYOUT["ramp"]["hinge"][1]
        mouth = [v for v in yel["verts"] if abs(v[2] - LAYOUT["deck"]["floor_h"]) < 0.02 and v[1] > hinge]
        self.assertTrue(mouth and all(v[1] < hinge + 0.13 for v in mouth))
        ramp = [v for v in yel["verts"] if v[1] < hinge - 0.01]
        hw = LAYOUT["ramp"]["width_m"] / 2
        self.assertTrue(ramp and all(hw - 0.125 < abs(v[0]) < hw + 0.005 for v in ramp))
        pieces = {p["id"]: p for p in LAYOUT["pieces"]}
        for pid in ("portholes", "tail_vents", "hump_sensors", "service_hatches", "hazard_stripes"):
            self.assertIn(pid, pieces)
        self.assertTrue(pieces["hazard_stripes"].get("outside"))
        self.assertEqual(LAYOUT["light"]["mats"]["ext_porthole"]["l"], 0.0)


if __name__ == "__main__":
    unittest.main()
