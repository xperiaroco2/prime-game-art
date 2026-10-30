"""The lobby hall's layout check (art #356, docs/lobby.md): plain Python, no Blender, no Godot. The ship's footprint
comes from the hull's outline (ship_hull_shape, plain Python) and a fixture of art #263's build report (the pods' and
the tail's bounds as built in ship/v5); a last test reads the real report when the raw folder has it."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runner import common, lobby_layout  # noqa: E402

# ship/v5's build report, the bounds the footprint reads (Godot frame (x, h, y) at each piece's origin)
REPORT = {"nozzle_pod_outer": {"bounds": {"min": [-1.4626, -0.8626, 0.0], "max": [1.4626, 2.0626, 5.065]}},
          "nozzle_pod_mid": {"bounds": {"min": [-1.6686, -1.0686, 0.0], "max": [1.6686, 2.2686, 5.365]}},
          "skin_top": {"bounds": {"min": [-13.0555, 1.5124, -7.1], "max": [13.0555, 5.42, 12.7]}}}
PLACE = [["nozzle_pod_outer", [-3.0, 9.6, 2.0], 0.0], ["nozzle_pod_outer", [3.0, 9.6, 2.0], 0.0],
         ["nozzle_pod_mid", [0.0, 9.6, 2.55], 0.0]]


class LobbyLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.layout = lobby_layout.load()
        cls.outline = lobby_layout.hull_outline(cls.layout["ship"]["hull"])

    def fp(self, layout: dict) -> list:
        return lobby_layout.footprint(layout, self.outline, REPORT, PLACE)

    def test_accepts_the_layout(self) -> None:
        self.assertEqual(lobby_layout.check(self.layout, self.fp(self.layout)), [])

    def test_the_engineers_numbers(self) -> None:
        n = lobby_layout.ship_numbers(self.layout, self.fp(self.layout))
        self.assertAlmostEqual(n["nose_z"], -24.1, places=2)
        self.assertAlmostEqual(n["aft_z"], -2.04, delta=0.01)
        self.assertAlmostEqual(n["middle_z"], -13.07, delta=0.01)
        r, cz = lobby_layout.arc(self.layout)
        self.assertAlmostEqual(lobby_layout.arc_z(self.layout, 0.0), 16.0)
        self.assertAlmostEqual(lobby_layout.arc_z(self.layout, 20.0), 10.0)
        self.assertAlmostEqual(r, 36.333, places=3)

    def test_refuses_a_ship_on_the_spawns(self) -> None:
        layout = copy.deepcopy(self.layout)
        layout["ship"]["origin"] = [0.0, 0.0, -12.0]   # 5 m south: the pods end at z +2.96, past the spawns
        problems = lobby_layout.check(layout, self.fp(layout))
        self.assertTrue(any(p.startswith("spawn x") and "from the ship" in p for p in problems), problems)

    def test_refuses_a_ship_near_a_wall(self) -> None:
        layout = copy.deepcopy(self.layout)
        layout["ship"]["origin"] = [5.0, 0.0, -17.0]
        problems = lobby_layout.check(layout, self.fp(layout))
        self.assertTrue(any(p.startswith("ship:") and "from E" in p for p in problems), problems)

    def test_refuses_a_door_on_a_pilaster(self) -> None:
        layout = copy.deepcopy(self.layout)
        layout["door"]["doors"][0] = ["D1", "W", 0.0]   # on the pilaster under the rib at z 0
        problems = lobby_layout.check(layout, self.fp(layout))
        self.assertTrue(any(p.startswith("D1: on the pilaster") for p in problems), problems)

    def test_refuses_the_drawings_wide_pilaster(self) -> None:
        layout = copy.deepcopy(self.layout)
        layout["hall"]["pilaster_w"] = 1.2   # the drawing's glyph: 0.1 m into D1 and D2
        problems = lobby_layout.check(layout, self.fp(layout))
        self.assertTrue(any(p.startswith("D1: on the pilaster at 0.0") for p in problems), problems)

    def test_refuses_a_door_on_the_arch_and_a_corner(self) -> None:
        layout = copy.deepcopy(self.layout)
        layout["door"]["doors"][2] = ["D3", "N", -3.0]
        layout["door"]["doors"][3] = ["D4", "N", 19.5]
        problems = lobby_layout.check(layout, self.fp(layout))
        self.assertTrue(any(p == "D3: on the arch" for p in problems), problems)
        self.assertTrue(any(p.startswith("D4: within") for p in problems), problems)

    def test_refuses_a_walk_point_under_the_ship(self) -> None:
        layout = copy.deepcopy(self.layout)
        layout["walk"]["points"] = [*layout["walk"]["points"], [0.0, -13.0]]
        problems = lobby_layout.check(layout, self.fp(layout))
        self.assertTrue(any("under the ship" in p for p in problems), problems)

    def test_refuses_a_placement_without_a_piece(self) -> None:
        layout = copy.deepcopy(self.layout)
        layout["place"].append(["balcony", [0.0, 0.0, 0.0], 0.0])
        self.assertIn("place: no piece 'balcony'", lobby_layout.check(layout, self.fp(layout)))

    def test_refuses_an_unknown_look_variant(self) -> None:
        layout = copy.deepcopy(self.layout)
        layout["look"]["variant"] = "V9"
        self.assertTrue(any("variant V9" in p for p in lobby_layout.check(layout)))

    def test_refuses_a_bad_variant_colour_and_grid_view(self) -> None:
        layout = copy.deepcopy(self.layout)
        layout["look"]["variants"]["V2"]["base"] = [0.3, 1.4, 0.2]
        layout["review"]["grid"] = ["corner_nw", "nowhere"]
        problems = lobby_layout.check(layout)
        self.assertTrue(any("look V2: base" in p for p in problems), problems)
        self.assertTrue(any("grid: nowhere" in p for p in problems), problems)

    def test_three_variants_and_the_views(self) -> None:
        self.assertEqual(sorted(self.layout["look"]["variants"]), ["V1", "V2", "V3"])
        names = [v[0] for v in self.layout["review"]["views"]]
        for want in ("corner_nw", "c_back", "spawn_eye", "spawn_ship", "door_d3", "arch", "rib", "floor_ring"):
            self.assertIn(want, names)
        spawn = next(v for v in self.layout["review"]["views"] if v[0] == "spawn_eye")
        self.assertGreater(spawn[3][2], spawn[2][2])   # the spawns face the window (+z)

    def test_plan_draws_the_hall(self) -> None:
        plan = lobby_layout.ascii_plan(self.layout, self.fp(self.layout))
        for mark in ("A", "S", "s", "o", "W", "D", "#", "|"):
            self.assertIn(mark, plan)

    def test_the_built_report(self) -> None:
        path = common.raw_dir() / self.layout["ship"]["pieces_dir"] / "build_report.json"
        if not path.is_file():
            self.skipTest(f"no {path}")
        from runner.commands import lobby
        place, drop, report, ship = lobby.ship_scene(self.layout)
        fp = lobby_layout.footprint(self.layout, self.outline, report, place)
        self.assertEqual(lobby_layout.check(self.layout, fp), [])
        kept = {p[0] for p in place}
        self.assertFalse(kept & set(drop))
        self.assertIn("skin_top", kept)


if __name__ == "__main__":
    unittest.main()
