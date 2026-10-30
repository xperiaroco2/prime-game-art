"""The jaw nose in the walk and the package (art #263 b4; docs/ship.md "The jaw nose"): the capsule walk's outside
points lie on the ground in front of the open ramp's tip and run up its centre line; `ship --export`'s Ship/Nose
request (the jaw's pieces, the open pose, the "open" clip's keys from the jaw video's swing) and the check that
refuses a Nose without its pieces, clips or poses; export_scene.gd builds the Nose with its AnimationPlayer. Pure
Python."""

from __future__ import annotations

import unittest

from runner import common, ship_layout as sl
from runner.commands import _ship_export, ship as ship_cmd

LAYOUT = sl.load()


class ShipNoseWalkTest(unittest.TestCase):
    def test_the_walk_starts_in_front_of_the_open_tip_on_its_centre_line(self) -> None:
        tip_y = sl.jaw_numbers(LAYOUT, "open")["tip_y"]
        pts = LAYOUT["walk"]["points"]
        for p in (pts[0], pts[1], pts[-1], pts[-2]):
            self.assertEqual((p[0], p[2]), (0.0, 0.0), p)   # on the ground, on the ramp's centre line
            self.assertLess(p[1], tip_y - 0.5, p)           # in front of the tip, clear of the capsule's reach
        self.assertEqual(pts[2], [0.0, -6.6, 1.2])          # then up the deck into the throat
        self.assertEqual(pts[-3], [0.0, -6.6, 1.2])


class ShipNosePackageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.want = ship_cmd.nose_request(LAYOUT)

    def test_the_request_holds_the_jaw_and_a_swing_from_closed_to_open(self) -> None:
        w = self.want
        self.assertEqual(sorted(w["pieces"]), ["jaw_lower", "jaw_root", "jaw_upper"])
        self.assertEqual(sorted(w["moving"]), ["jaw_lower", "jaw_upper"])
        self.assertEqual(w["open"], {k: v for k, v in sl.jaw_deg(LAYOUT, "open").items()})
        self.assertEqual(w["keys"][0], [0.0, sl.jaw_deg(LAYOUT, "closed")])
        self.assertEqual(w["keys"][-1], [w["seconds"], w["open"]])
        times = [k[0] for k in w["keys"]]
        self.assertEqual(times, sorted(times))
        self.assertAlmostEqual(w["seconds"], 2.5)

    def got(self) -> dict:
        w = self.want
        poses = {"default": dict(w["open"]), "open": dict(w["open"]), "RESET": dict(w["open"]), "close": dict(w["closed"])}
        return {"nose": {"pieces": list(w["pieces"]), "clips": ["open", "close", "RESET"],
                         "lengths": {"open": 2.5, "close": 2.5, "RESET": 0.001}, "poses": poses}}

    def test_the_check_takes_a_whole_nose(self) -> None:
        self.assertEqual(_ship_export.nose_problems(LAYOUT, self.got()), [])

    def test_the_check_refuses_a_nose_without_its_parts_clips_or_poses(self) -> None:
        self.assertEqual(_ship_export.nose_problems(LAYOUT, {}), ["no Ship/Nose"])
        g = self.got()
        g["nose"]["pieces"].remove("jaw_root")
        g["nose"]["clips"].remove("close")
        g["nose"]["poses"]["close"]["jaw_lower"] = -10.0
        g["nose"]["poses"]["default"]["jaw_upper"] = 0.0
        self.assertEqual(len(_ship_export.nose_problems(LAYOUT, g)), 4)

    def test_export_scene_builds_the_nose_and_its_clips(self) -> None:
        src = (common.ROOT / "godot" / "ship" / "export_scene.gd").read_text(encoding="utf-8")
        for needle in ('nose.name = "Nose"', 'add_animation("open"', 'add_animation("close"', 'add_animation("RESET"',
                       'rotation:x', 'remove_meta("pieces")', "n.name != GROUND"):
            self.assertIn(needle, src)


if __name__ == "__main__":
    unittest.main()
