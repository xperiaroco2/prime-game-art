"""The House map's light kit (tools/runner/house_lights.py, layouts/house/lights.toml, docs/house.md "Light"): the data
holds, the fixture counts are the plan's (inventory.md §8: 191), every fixture lands in its room at its type's height,
wall fixtures keep clear of doors, and the scenes carry baked lights. Pure Python."""

from __future__ import annotations

import copy
import math
import tempfile
import unittest
from pathlib import Path

from runner import house_layout as H
from runner import house_lights as L

DATA = H.load()
LIGHTS = L.load()
FIX = L.plan(LIGHTS, DATA)
ROOMS = L.rooms_by_id(DATA)


class LightData(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(L.validate(LIGHTS, DATA), [])

    def test_counts_match_the_plan(self):
        fixtures = [f for f in FIX if f["type"] != "moon"]
        self.assertEqual(len(fixtures), 191)
        by_type: dict = {}
        for f in fixtures:
            by_type[f["type"]] = by_type.get(f["type"], 0) + 1
        self.assertEqual(by_type["bare_bulb"], 28)
        self.assertEqual(by_type["cage_lamp"], 22)
        self.assertEqual(by_type["path_light"], 28)
        self.assertEqual(by_type["chandelier"], 1)

    def test_every_room_in_one_zone(self):
        zones = L.zone_rooms(LIGHTS, DATA)
        ids = [r for z in zones.values() for r in z]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), set(ROOMS))

    def test_bad_data_is_reported(self):
        bad = copy.deepcopy(LIGHTS)
        bad["rooms"]["storage"]["neon_sign"] = 2
        bad["rooms"]["nowhere"] = {"bare_bulb": 1}
        bad["zones"]["ground"]["rooms"].append("storage")
        bad["types"]["lantern"]["mount"] = "roof"
        problems = "\n".join(L.validate(bad, DATA))
        for text in ("unknown fixture type neon_sign", "rooms.nowhere", "storage is in zones", "mount 'roof'"):
            self.assertIn(text, problems)


class Placement(unittest.TestCase):
    def test_inside_the_room_at_its_height(self):
        for f in FIX:
            if f["type"] == "moon":
                continue
            lv, room = ROOMS[f["room"]]
            self.assertTrue(H.inside(room["rect"], f["x"], f["y"]), f["name"])
            self.assertAlmostEqual(f["h"], lv["floor_y"] + LIGHTS["types"][f["type"]]["h"], places=3, msg=f["name"])

    def test_wall_fixtures_on_a_wall_clear_of_doors(self):
        for f in FIX:
            if f["type"] == "moon" or LIGHTS["types"][f["type"]]["mount"] != "wall":
                continue
            lv, room = ROOMS[f["room"]]
            x, y, w, d = room["rect"]
            edge = min(abs(f["x"] - x), abs(f["x"] - x - w), abs(f["y"] - y), abs(f["y"] - y - d))
            self.assertAlmostEqual(edge, L.WALL_INSET, places=3, msg=f["name"])
            for door in lv.get("doors", []):
                if f["room"] in door["rooms"]:
                    self.assertGreaterEqual(math.dist((f["x"], f["y"]), door["at"]), L.DOOR_CLEAR - 1e-6, f["name"])

    def test_no_two_fixtures_of_a_room_on_one_spot(self):
        spots = [(f["room"], f["x"], f["h"], f["y"]) for f in FIX]
        self.assertEqual(len(spots), len(set(spots)))

    def test_colours(self):
        by = {f["name"]: f for f in FIX}
        self.assertEqual(by["storage_bare_bulb_01"]["color"], LIGHTS["colors"]["c2"])
        self.assertEqual(by["darkroom_safelight_red_01"]["color"], LIGHTS["colors"]["safelight"])
        self.assertEqual(by["greenhouse_bare_bulb_01"]["color"], LIGHTS["colors"]["green_cold"])
        self.assertEqual(by["garage_fluorescent_tube_01"]["color"], LIGHTS["colors"]["cool"])

    def test_moon_spots_outside_aimed_in(self):
        moons = [f for f in FIX if f["type"] == "moon"]
        windows = sum(len(lv.get("windows", [])) for lv in DATA["levels"])
        self.assertEqual(len(moons), sum(math.ceil(len(lv.get("windows", [])) / LIGHTS["moon"]["every"])
                                         for lv in DATA["levels"]))
        self.assertGreater(windows, 0)
        for f in moons:
            room = ROOMS[f["room"]][1]
            self.assertFalse(H.inside(room["rect"], f["x"], f["y"]), f["name"])
            self.assertTrue(H.strictly_inside(room["rect"], f["aim"][0], f["aim"][2]), f["name"])

    def test_spot_basis_points_at_its_aim(self):
        f = next(f for f in FIX if f["type"] == "moon")
        b = L._aim_basis(f)
        z = [b[2], b[5], b[8]]  # the basis's third column
        d = [f["aim"][0] - f["x"], f["aim"][1] - f["h"], f["aim"][2] - f["y"]]
        n = math.sqrt(sum(c * c for c in d))
        self.assertAlmostEqual(sum(-zc * dc / n for zc, dc in zip(z, d)), 1.0, places=6)


class Scenes(unittest.TestCase):
    def test_zone_and_level_scenes(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            s = L.write(LIGHTS, DATA, H.plan(DATA), FIX, out)
            self.assertEqual(sum(s["levels"].values()), len(FIX))
            self.assertEqual(sum(z["fixtures"] for z in s["zones"].values()), 191)
            text = (out / "zones" / "basement.tscn").read_text(encoding="utf-8")
            self.assertIn('[node name="storage_bare_bulb_01" type="OmniLight3D" parent="Lights"]', text)
            self.assertIn("light_bake_mode = 1", text)
            self.assertIn('parent="Above"', text)  # the ground floor's slabs are the basement's ceiling
            self.assertIn("res://import/house/basement/storage.tscn", text)
            self.assertNotIn("Cover_", text)  # the yard's slab is in the outer rooms' own scenes now (#108)
            self.assertTrue((out / "lights" / "ground.tscn").is_file())
            self.assertIn("SpotLight3D", (out / "zones" / "ground.tscn").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
