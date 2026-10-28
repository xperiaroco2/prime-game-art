"""`ship --charger-cycle DIR` (art #263, lens room C; docs/ship.md): the argument parses, the Godot script exists and
runs in ship.gd's off-screen "shoot" mode, and cycle_view() puts the eye at the player's eye height 1.5 m in front of
the east charger's front, looking back at its axis. Plain Python: no Blender, no Godot."""

from __future__ import annotations

import argparse
import math
import unittest
from pathlib import Path

from runner import common
from runner import ship_layout
from runner.commands import ship as ship_cmd

LAYOUT = ship_layout.load()


class ChargerCycle(unittest.TestCase):
    def test_argument_parses(self) -> None:
        parser = argparse.ArgumentParser(prog="ship")
        ship_cmd.add_arguments(parser)
        args = parser.parse_args(["--charger-cycle", "x/cycle"])
        self.assertEqual(args.charger_cycle, Path("x/cycle"))
        self.assertIsNone(parser.parse_args([]).charger_cycle)

    def test_script_exists_and_runs_as_a_shoot(self) -> None:
        path = common.ROOT / "godot" / ship_cmd.CYCLE_SCRIPT.removeprefix("res://")
        self.assertTrue(path.is_file(), path)
        text = path.read_text(encoding="utf-8")
        self.assertIn('extends "res://charger/room.gd"', text)
        self.assertIn("func _shoot()", text)   # ship.gd's "shoot" mode opens the off-screen window
        self.assertIn("func step(dt: float)", text)

    def test_video_settings(self) -> None:
        c = ship_cmd.CHARGER_CYCLE
        self.assertEqual((c["size"], c["fps"], c["max_mb"]), ((1280, 720), 30, 15))

    def test_eye_in_front_of_the_east_charger(self) -> None:
        spot = next(s for s in LAYOUT["stations"]["spot"] if s["id"] == "renewer_e")
        reach = spot["depth_m"]
        floor = LAYOUT["deck"]["floor_h"]
        eye, look = ship_cmd.cycle_view(LAYOUT)
        (x, y), (nx, ny) = spot["at"], spot["normal"]
        out = (eye[0] - x) * nx + (eye[1] - y) * ny          # along the spot's normal, into the room
        side = (eye[0] - x) * -ny + (eye[1] - y) * nx         # across it
        self.assertAlmostEqual(out - reach, 1.5, places=2)   # 1.5 m in front of the charger's front
        self.assertAlmostEqual(side, 0.0, places=3)
        self.assertAlmostEqual(eye[2] - floor, 1.6, places=3)
        self.assertGreater(eye[2], look[2])                   # looking down at the charger
        self.assertLess(math.hypot(look[0] - x, look[1] - y), reach)


if __name__ == "__main__":
    unittest.main()
