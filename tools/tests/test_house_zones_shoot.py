"""The `zones` command's Godot request (art #81b, docs/zones.md): every placed piece is a staged GLB or a sized
placeholder, every fixture carries a light per socket, the views are the zones' own and the line-up holds the zone
props. Pure Python: needs neither Godot nor the raw files."""

from __future__ import annotations

import unittest

from runner import house_zones as hz
from runner.commands import zones as zones_cmd

ZONES = hz.load_all()
REQ, STAGED = zones_cmd.request(ZONES)


class ZonesRequestTest(unittest.TestCase):
    def test_every_piece_is_a_glb_or_a_sized_placeholder(self) -> None:
        self.assertEqual(len(REQ["pieces"]), sum(len(hz.placements(z)) for z in ZONES))
        for p in REQ["pieces"]:
            with self.subTest(piece=p["id"]):
                if p["src"] in ("zones", "tasks", "kit"):
                    name = p["scene"].removeprefix("res://import/").removesuffix(".glb")
                    self.assertIn(name, STAGED)
                    self.assertEqual(STAGED[name].name, f"{p['id']}.glb")
                else:
                    self.assertEqual(len(p["size"]), 3)
                    self.assertTrue(all(v and v > 0 for v in p["size"]))

    def test_fixtures_light_every_socket(self) -> None:
        lit = [p for p in REQ["pieces"] if p["id"] in zones_cmd.LIGHTS]
        self.assertTrue(lit)
        for p in lit:
            with self.subTest(piece=p["id"]):
                self.assertTrue(p["lights"], "a fixture without light sockets")

    def test_views_and_lineup(self) -> None:
        names = [v[0] for v in REQ["views"]]
        for z in ZONES:
            for v in z["views"]:
                self.assertIn(f"{z['name']}_{v['name']}", names)
        self.assertIn("gazebo_pose", names)
        self.assertEqual({p["id"] for p in REQ["lineup"]},
                         {"deckchair", "fire_pit", "bean_bag", "cooler_box", "photo_backdrop", "tripod_camera",
                          "lantern", "string_lights_set", "string_lights_gazebo"})


if __name__ == "__main__":
    unittest.main()
