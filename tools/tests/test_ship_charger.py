"""`ship --shoot --charger` (art #263, lens room C; docs/ship.md): charger_places() puts a charger on each renewer
spot with the yaw of the charger's HANDOFF table and a crystal on the axis 38 cm out at the deck + 95.1 cm,
charger_rows() merges the game's default state under a row's own keys, shoot_script() switches to charger/room.gd,
and --charger without --shoot is a usage error. Plain Python: no Blender, no Godot."""

from __future__ import annotations

import argparse
import contextlib
import io
import math
import re
import tomllib
import unittest

from runner import common
from runner import ship_layout
from runner.commands import ship as ship_cmd

LAYOUT = ship_layout.load()
HANDOFF = common.ROOT / "assets" / "prop" / "crystal_charger" / "HANDOFF.md"
DIMS = common.ROOT / "tools" / "blender" / "charger_dims.toml"


def handoff_yaws() -> dict:
    """The HANDOFF's table rows `| `renewer_e` | (x, y) | (nx, ny) | yaw |` as {spot: yaw}."""
    rows = re.findall(r"^\| `(renewer_[ew])` \| \([^)]*\) \| \([^)]*\) \| (-?[0-9.]+) \|", HANDOFF.read_text(encoding="utf-8"),
                      re.M)
    return {k: float(v) for k, v in rows}


class ChargerPlaces(unittest.TestCase):
    def setUp(self) -> None:
        self.places = ship_cmd.charger_places(LAYOUT)
        self.spots = {s["id"]: s for s in LAYOUT["stations"]["spot"]}
        self.floor = LAYOUT["deck"]["floor_h"]

    def test_one_charger_and_one_crystal_per_spot(self) -> None:
        self.assertEqual([p[0] for p in self.places], ["crystal_charger", "energy_crystal"] * 2)

    def test_yaw_matches_the_handoff(self) -> None:
        yaws = handoff_yaws()
        self.assertEqual(set(yaws), {"renewer_e", "renewer_w"})
        chargers = [p for p in self.places if p[0] == "crystal_charger"]
        for (_name, (x, h, y), yaw) in chargers:
            sid = next(k for k, s in self.spots.items() if k in yaws and
                       math.isclose(s["at"][0], x, abs_tol=1e-4) and math.isclose(s["at"][1], y, abs_tol=1e-4))
            self.assertAlmostEqual(yaw, yaws[sid], places=2)
            self.assertEqual(h, self.floor)

    def test_crystal_on_the_axis(self) -> None:
        axis = tomllib.loads(DIMS.read_text(encoding="utf-8"))["frame"]["axis_d"] / 100
        self.assertAlmostEqual(axis, 0.38)
        for k in (0, 2):
            (_c, (x, _h, y), yaw), (name, (cx, ch, cy), cyaw) = self.places[k], self.places[k + 1]
            self.assertEqual(name, "energy_crystal")
            sid = next(s for s in self.spots.values() if math.isclose(s["at"][0], x, abs_tol=1e-4))
            nx, ny = sid["normal"]
            self.assertAlmostEqual(cx, x + nx * axis, places=3)
            self.assertAlmostEqual(cy, y + ny * axis, places=3)
            self.assertAlmostEqual(ch, self.floor + 0.951, places=4)
            self.assertEqual(cyaw, yaw)


class ChargerRows(unittest.TestCase):
    def test_default_state_merged_under_the_row(self) -> None:
        views = [["a", "t", [0, 0, 0], [1, 0, 0], 60.0],
                 ["b", "t", [0, 0, 0], [1, 0, 0], 60.0, {"charge": 1.0, "ssil": False}]]
        rows = ship_cmd.charger_rows(views)
        self.assertEqual(rows[0][5], {"charger": "idle", "crystal": True, "charge": 0.0})
        self.assertEqual(rows[1][5], {"charger": "idle", "crystal": True, "charge": 1.0, "ssil": False})
        self.assertEqual(len(rows[1]), 6)

    def test_script_switch(self) -> None:
        self.assertEqual(ship_cmd.shoot_script(True), "res://charger/room.gd")
        self.assertEqual(ship_cmd.shoot_script(False), "res://ship/ship.gd")
        self.assertTrue((common.ROOT / "godot" / "charger" / "room.gd").is_file())

    def test_charger_needs_shoot(self) -> None:
        parser = argparse.ArgumentParser(prog="ship")
        ship_cmd.add_arguments(parser)
        args = parser.parse_args(["--charger"])
        with contextlib.redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit) as stop:
            ship_cmd.run(args)
        self.assertEqual(stop.exception.code, 2)
        self.assertIn("--charger only works with --shoot", err.getvalue())


if __name__ == "__main__":
    unittest.main()
