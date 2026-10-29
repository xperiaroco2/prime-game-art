"""The ship's outside light layer (art #263, docs/ship.md "The light layer"): the navigation lamps' placement (port
red on x < 0, starboard green on x > 0, white on the centre line aft), the landing lights on the belly with their
spots, the edge light's own glow lighting nothing, and the blink flag. Pure Python: needs neither Blender, Godot
nor the raw files."""

from __future__ import annotations

import math
import sys
import tomllib
import unittest
from pathlib import Path

from runner import ship_layout as sl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import ship_hull  # noqa: E402,F401  (imports the skin and the details, which add their materials)
import ship_hull_fittings  # noqa: E402,F401
import ship_hull_shape as S  # noqa: E402
import ship_lib as L  # noqa: E402

LAYOUT = sl.load()
EXT = tomllib.loads((sl.common.ROOT / LAYOUT["exterior"]).read_text(encoding="utf-8"))
LAMPS = LAYOUT["light"]["lamps"]
ROOT = Path(__file__).resolve().parents[2]


def placed(pid: str) -> list:
    return [(at, yaw) for p, at, yaw in EXT["place"] if p == pid]


def group(name: str) -> list:
    return [lamp for lamp in LAMPS if len(lamp) > 8 and lamp[8] == name]


class ShipLightTest(unittest.TestCase):
    def test_side_nav_lamps_off_together(self) -> None:
        """fix 2 (the engineer, 2026-10-23: "not needed yet"): the red and green lamps are off, their placements,
        pieces and lights alike (commented rows, NAV SIDE); the white tail lamp stays."""
        pieces = {p["id"] for p in EXT["pieces"]}
        states = {pid in pieces or bool(placed(pid)) for pid in ("nav_red", "nav_green")} | {bool(group("nav"))}
        self.assertEqual(len(states), 1, "the side nav lamps are half off: placements, pieces and lights go together")
        self.assertEqual(len(placed("nav_white")), 1)
        self.assertEqual(len(group("nav_tail")), 1)

    def test_ramp_pools_clear_of_the_ramp(self) -> None:
        """fix 2: no ground lamp's pool reaches the ramp (the engineer's walk: the pools cut into its edge)."""
        rp = LAYOUT["ramp"]
        half, y0, y1 = rp["width_m"] / 2, min(rp["hinge"][1], rp["foot"][1]), max(rp["hinge"][1], rp["foot"][1])
        for lamp in group("pool"):
            if y0 - lamp[4] < lamp[1] < y1 + lamp[4]:
                dx = abs(lamp[0]) - half
                dy = max(0.0, y0 - lamp[1], lamp[1] - y1)
                self.assertGreater(math.hypot(max(dx, 0.0), dy), lamp[4] + 0.05,
                                   f"the pool at ({lamp[0]}, {lamp[1]}) reaches the ramp")
        for (x, y, _h), _ in placed("ground_lamp"):
            if y0 - 0.5 < y < y1 + 0.5:
                self.assertGreater(abs(x) - 0.2, half + 1.0, f"the ground lamp at ({x}, {y}) stands at the ramp")

    @unittest.skipUnless(placed("nav_red"), "the side nav lamps are off (fix 2)")
    def test_nav_lamps_port_red_starboard_green_white_aft(self) -> None:
        (red, red_yaw), = placed("nav_red")
        (green, green_yaw), = placed("nav_green")
        (white, _), = placed("nav_white")
        self.assertLess(red[0], 0.0, "the red (port) lamp is not on the west")
        self.assertGreater(green[0], 0.0, "the green (starboard) lamp is not on the east")
        self.assertAlmostEqual(red[0], -green[0], places=3)
        self.assertAlmostEqual(red[1], green[1], places=3)
        self.assertAlmostEqual(white[0], 0.0, places=6, msg="the white lamp is off the centre line")
        self.assertGreater(white[1], max(red[1], green[1]) + 8.0, "the white lamp is not aft")
        cx, cy = S.P_TIP
        for (x, y, h), yaw in ((red, red_yaw), (green, green_yaw)):
            self.assertAlmostEqual(math.hypot(abs(x) - cx, y - cy), S.P_RIM_R, delta=0.01, msg="off the lens rim")
            self.assertLess(y, cy, "not on the lens rim's forward side")
            self.assertLess(h + 0.085, S.P_LENS_EDGE[0] - 0.045, "the housing reaches the edge light's channel")
            out = (math.cos(math.radians(yaw)), -math.sin(math.radians(yaw)))   # the lamp's +x in plan
            n = ((abs(x) - cx) * math.copysign(1, x), y - cy)
            self.assertGreater(out[0] * n[0] + out[1] * n[1], 0.99 * math.hypot(*n), "the lamp does not face out")
        top, _bottom = S.heights(white[0], white[1])
        self.assertAlmostEqual(white[2], top, delta=0.03, msg="the white lamp is not on the tail's top")

    @unittest.skipUnless(placed("nav_red"), "the side nav lamps are off (fix 2)")
    def test_nav_lamps_have_their_lights(self) -> None:
        nav, tail = group("nav"), group("nav_tail")
        self.assertEqual((len(nav), len(tail)), (2, 1))
        for pid, lamp in (("nav_red", min(nav, key=lambda q: q[0])), ("nav_green", max(nav, key=lambda q: q[0])),
                          ("nav_white", tail[0])):
            (at, _), = placed(pid)
            at = (at[0], at[1], at[2] + LAYOUT["deck"].get("lift_m", 0.0))   # the raise: the piece is lifted, its light is real
            self.assertLess(math.dist(at, lamp[:3]), 0.6, f"{pid}'s light is not at its lamp")
            self.assertLessEqual(lamp[4], 2.0, f"{pid}'s light is not a tiny one")
        red, green = sorted(nav)
        self.assertGreater(red[5], red[6], "the port light is not red")
        self.assertGreater(green[6], green[5], "the starboard light is not green")

    def test_landing_lights_on_the_belly_with_spots(self) -> None:
        lamps = placed("landing_lamp")
        spots = group("land")
        self.assertEqual(len(lamps), 6)
        self.assertEqual(len(spots), 6)
        for (x, y, h), _ in lamps:
            _top, bottom = S.heights(x, y)
            self.assertAlmostEqual(h, bottom, delta=0.01, msg=f"landing lamp ({x}, {y}) not on the belly")
            spot = min(spots, key=lambda q: math.hypot(q[0] - x, q[1] - y))
            self.assertLess(math.hypot(spot[0] - x, spot[1] - y), 0.2)
            self.assertLess(spot[2], h + LAYOUT["deck"].get("lift_m", 0.0) - 0.09, "the spot is not under the lens")
            self.assertGreater(spot[10], 0.0, "not a spot")
        old = [(0.0, -1.5), (-5.0, 0.0), (5.0, 0.0)]   # details 1: the three orange belly pools' spots, at h 0.2
        back = [q for q in group("pool") if abs(q[2] - 0.2) < 0.05 and any(math.hypot(q[0] - x, q[1] - y) < 0.1
                                                                             for x, y in old)]
        self.assertFalse(back, "the old belly pools are back")

    def test_edge_glow_lights_nothing_its_pools_are_spots(self) -> None:
        self.assertEqual(LAYOUT["light"]["mats"]["glow_edge"].get("cull"), "inside", "the edge glow lights the hull")
        edge = group("edge")
        self.assertEqual(len(edge), 6)
        for lamp in edge:
            self.assertGreater(lamp[10], 0.0)
            self.assertLess(lamp[2], 1.5 + LAYOUT["deck"].get("lift_m", 0.0), "an edge pool's spot above the edge (the fins' hot spots)")

    def test_family_materials_take_their_familys_row_and_light_nothing(self) -> None:
        """details 3b (ship.gd _entry): a material named "<family>__<x>" without its own [light.mats] row takes its
        family's row, so every such material (the portholes' glow bands ext_porthole__gNN) has its family there, and
        it keeps l 0: the glow lights nothing."""
        mats = LAYOUT["light"]["mats"]
        family = [m for m in L.MATERIALS if "__" in m]
        self.assertTrue(any(m.startswith("ext_porthole__g") for m in family), family)
        for m in family:
            row = mats.get(m, mats.get(m.split("__", 1)[0]))
            self.assertIsNotNone(row, f"{m}: no [light.mats] row of its own or of its family")
            self.assertEqual(row.get("l"), 0, f"{m}: its [light.mats] row lights the hull (l {row.get('l')})")
        gd = (ROOT / "godot" / "ship" / "ship.gd").read_text(encoding="utf-8")
        self.assertIn('mats.get(mat_name.get_slice("__", 0), {})', gd)

    def test_nav_blink_flag(self) -> None:
        gd = (ROOT / "godot" / "ship" / "ship.gd").read_text(encoding="utf-8")
        self.assertIn("var nav_blink: bool = true", gd)
        py = (ROOT / "tools" / "runner" / "commands" / "ship.py").read_text(encoding="utf-8")
        self.assertEqual(py.count('"nav_blink": False'), 5,
                         "shots, the video, the vent's clip, the gills' clip and the charger's cycle show a static glow")


if __name__ == "__main__":
    unittest.main()
