"""The jaw nose, blockout b1 (art #263, docs/ship.md "The jaw nose"): the three poses, the open deck on the ground at
the ramp's slope (under 30 deg), the head room under the upper jaw, the check refusing a wrong pose, and the
builders' solids (closed meshes, the passage kept clear, the deck in its plane). Plain Python, no Blender."""

from __future__ import annotations

import copy
import math
import sys
import unittest
from pathlib import Path

from runner import ship_layout as sl
from runner.commands import ship as ship_cmd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import ship_hull  # noqa: E402,F401  (imports every exterior module in its order)
import ship_hull_jaw as J  # noqa: E402

LAYOUT = sl.load()


class ShipJawPoseTest(unittest.TestCase):
    def test_three_poses_and_the_default(self) -> None:
        j = LAYOUT["jaw"]
        self.assertEqual(j["pose"], "open")            # the game and the walk get the open ramp
        self.assertEqual(sl.jaw_deg(LAYOUT, "closed"), {"jaw_lower": 0.0, "jaw_upper": 0.0})
        lo = {p: sl.jaw_deg(LAYOUT, p)["jaw_lower"] for p in sl.JAW_POSES}
        up = {p: sl.jaw_deg(LAYOUT, p)["jaw_upper"] for p in sl.JAW_POSES}
        self.assertTrue(lo["open"] < lo["half"] < lo["closed"] == 0.0)       # the lower jaw goes down
        self.assertTrue(0.0 == up["closed"] < up["half"] < up["open"] <= 5.0)  # the upper lifts a little
        self.assertEqual(sl.check_jaw(LAYOUT), [])

    def test_the_open_ramp(self) -> None:
        o = sl.jaw_numbers(LAYOUT, "open")
        ramp = LAYOUT["ramp"]
        run = ramp["hinge"][1] - ramp["foot"][1]
        self.assertAlmostEqual(o["length"], math.hypot(run, 1.2), delta=0.01)
        self.assertAlmostEqual(o["slope_deg"], math.degrees(math.atan2(1.2, run)), delta=0.05)
        self.assertLess(o["slope_deg"], 30.0)
        self.assertAlmostEqual(o["tip_h"], 0.0, delta=0.02)
        self.assertAlmostEqual(o["tip_y"], ramp["foot"][1], delta=0.05)
        c = sl.jaw_numbers(LAYOUT, "closed")
        self.assertAlmostEqual(c["tip_h"], LAYOUT["jaw"]["seam_h"], delta=1e-6)   # closed: the deck meets the seam

    def test_head_room_open(self) -> None:
        pl = LAYOUT["player"]
        self.assertGreaterEqual(sl.jaw_numbers(LAYOUT, "open")["head_room"],
                                pl["capsule_height_m"] + pl["head_margin_m"])

    def test_the_check_refuses(self) -> None:
        bad = copy.deepcopy(LAYOUT)
        bad["jaw"]["pose"] = "ajar"
        self.assertEqual(len(sl.check_jaw(bad)), 1)
        steep = copy.deepcopy(LAYOUT)
        steep["jaw"]["lower_deg"]["open"] = -50.0      # the deck through the ground, too steep
        self.assertTrue(any("ground" in p for p in sl.check_jaw(steep)))
        low = copy.deepcopy(LAYOUT)
        low["jaw"]["upper_deg"]["open"] = -6.0         # the roof down on the walkers' heads
        self.assertTrue(any("head room" in p or "over the deck" in p for p in sl.check_jaw(low)))

    def test_the_placements_carry_the_pose(self) -> None:
        rows = {r[0]: r for r in ship_cmd.places(LAYOUT)}
        self.assertEqual(rows["jaw_lower"][3], LAYOUT["jaw"]["lower_deg"]["open"])
        self.assertEqual(rows["jaw_upper"][3], LAYOUT["jaw"]["upper_deg"]["open"])
        self.assertEqual(len(rows["jaw_root"]), 3)
        self.assertEqual(rows["jaw_lower"][1], [0.0, 1.2, -8.1])      # Godot (x, h, y): at its hinge
        self.assertEqual(sorted(ship_cmd.jaw_request(LAYOUT)), sorted(sl.JAW_POSES))
        pieces = {p["id"]: p for p in LAYOUT["pieces"]}
        for pid in ("jaw_lower", "jaw_upper", "jaw_root"):
            self.assertTrue(pieces[pid]["collide"] and pieces[pid]["outside"] and pieces[pid]["grounded"], pid)
        for gone in ("ramp", "ramp_lights", "hazard_stripes", "mouth_tunnel"):
            self.assertNotIn(gone, pieces)


class ShipJawBuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parts = {f.__name__: {p["name"]: p for p in f({}, LAYOUT)} for f in (J.jaw_upper, J.jaw_lower, J.jaw_root)}

    def test_every_solid_is_there_and_closed(self) -> None:
        want = {"jaw_upper": {"upper_cheek_e", "upper_cheek_w", "upper_roof_fore", "upper_roof_mid", "upper_roof_aft",
                              "seam_glow"},
                "jaw_lower": {"lower_cheek_e", "lower_cheek_w", "lower_body", "deck_ribs", "deck_edges"},
                "jaw_root": {"root_e", "root_w", "root_under"}}
        for pid, names in want.items():
            self.assertEqual(set(self.parts[pid]), names, pid)
            for name, part in self.parts[pid].items():
                edges = {}
                for f in part["faces"]:
                    for a, b in zip(f, f[1:] + f[:1]):
                        key = tuple(sorted((part["verts"][a], part["verts"][b])))
                        edges[key] = edges.get(key, 0) + 1
                if name.startswith(("upper_", "lower_", "root_")):   # a closed convex solid: each edge twice
                    self.assertGreaterEqual(len(part["faces"]), 4, name)
                    self.assertTrue(all(n == 2 for n in edges.values()), name)

    def test_the_passage_stays_clear(self) -> None:
        """Closed or open, nothing of a jaw's cheeks or the root stands inside the mouth's 3.3 m."""
        lo, up = LAYOUT["jaw"]["lower_hinge"], LAYOUT["jaw"]["upper_hinge"]
        for pid, o in (("jaw_lower", lo), ("jaw_upper", up), ("jaw_root", (0, 0, 0))):
            for name, part in self.parts[pid].items():
                if "cheek" in name or name in ("root_e", "root_w"):
                    xs = [abs(v[0] + o[0]) for v in part["verts"]]
                    self.assertGreaterEqual(min(xs), J.MOUTH_X - 1e-6, name)

    def test_the_deck_lies_in_its_plane(self) -> None:
        j = J.jaw(LAYOUT)
        o = j["lower_hinge"]
        body = self.parts["jaw_lower"]["lower_body"]
        top = [(v[0] + o[0], v[1] + o[1], v[2] + o[2]) for v in body["verts"]]
        on = [p for p in top if abs(p[2] - (j["floor_h"] + j["deck_slope"] * (o[1] - p[1]))) < 1e-6]
        self.assertTrue(any(abs(p[1] - j["tip_y"]) < 1e-6 for p in on))        # its front edge at the tip
        self.assertTrue(any(abs(p[1] - o[1]) < 1e-6 and abs(p[2] - j["floor_h"]) < 1e-6 for p in on))  # flush at the hinge
        self.assertLessEqual(max(p[2] for p in top), j["seam_h"] + 1e-6)


if __name__ == "__main__":
    unittest.main()
