"""The House map's dressing (art #75b, docs/house.md "Dressing"): the rules of tools/runner/house_dressing.py on small
made-up rooms, and the ground floor's dressing files against the plan's inventory and the rooms' stations."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runner import house_dressing as hd  # noqa: E402
from runner import house_layout as hl  # noqa: E402

CAT = {
    "box1": {"size": [1.0, 1.0, 1.0], "pivot": "floor", "collision": "box"},
    "pic": {"size": [0.5, 0.03, 0.4], "pivot": "wall", "collision": "none"},
    "rug": {"size": [3.0, 2.0, 0.02], "pivot": "floor", "collision": "none"},
}


def made_up(props, fixtures=()):
    """A 6 x 4 m walled room with a west door at (0, 2), a south door at (3, 4) and a station at (4.5, 2)."""
    room = {"id": "r", "node": "R", "kind": "room", "rect": [0, 0, 6, 4], "stations": [{"name": "S", "at": [4.5, 0, 2]}]}
    level = {"level": "t", "floor_y": 0.0, "rooms": [room], "holes": [], "stairs": [],
             "doors": [{"at": [0, 2], "rooms": ["r", "x"], "kind": "door"},
                       {"at": [3, 4], "rooms": ["r", "x"], "kind": "door"}]}
    data = {"levels": [level]}
    return hd.check(data, {"r": {"file": "r.toml", "props": list(props), "fixtures": list(fixtures)}}, CAT)


class Rules(unittest.TestCase):
    def test_a_clear_room_holds(self):
        rep = made_up([{"id": "box1", "at": [5.4, 0, 0.6]}, {"id": "rug", "at": [3, 0, 2]},
                       {"id": "pic", "at": [3, 1.4, 0.1]}])
        self.assertEqual(rep["problems"], [])
        self.assertTrue(all(rep["rooms"]["r"]["reach"].values()))

    def test_a_shelf_across_the_room_cuts_the_path(self):
        rep = made_up([{"id": "shelf", "at": [1.5, 0, 2.0], "size": [0.4, 3.8, 1.0]}])
        self.assertTrue(any("cut the capsule's path" in p for p in rep["problems"]), rep["problems"])

    def test_a_rug_never_blocks(self):
        rep = made_up([{"id": "rug", "at": [1.5, 0, 2.0], "face": "E"}])
        self.assertEqual(rep["problems"], [])

    def test_the_station_keeps_one_metre(self):
        near = made_up([{"id": "box1", "at": [4.5, 0, 0.6]}])
        self.assertTrue(any("of station S" in p for p in near["problems"]), near["problems"])
        own = made_up([{"id": "box1", "at": [4.5, 0, 0.6], "station": "S"}])
        self.assertFalse(any("of station S" in p for p in own["problems"]))

    def test_bounds_overlaps_walls_and_ids(self):
        rep = made_up([{"id": "box1", "at": [0.3, 0, 0.6]},                       # through the west wall
                       {"id": "box1", "at": [5.4, 0, 0.6]}, {"id": "box1", "at": [5.4, 0.5, 1.0]},  # overlap
                       {"id": "pic", "at": [3, 1.4, 1.0]},                         # a wall prop off the wall
                       {"id": "nope", "at": [3, 0, 2]},                            # unknown
                       {"id": "pic", "at": [3, 1.0, 3.9], "face": "N"}])           # over the south door
        text = "\n".join(rep["problems"])
        for want in ("outside the room's wall faces", "overlaps", "back is not on a wall face", "unknown prop id",
                     "on the door opening"):
            self.assertIn(want, text)

    def test_turns_follow_the_kit(self):
        r = hd.resolve({"id": "box1", "at": [2, 0, 1], "size": [2.0, 1.0, 1.0], "face": "E"}, CAT)
        self.assertEqual(tuple(round(v, 3) for v in hd.footprint(r)), (1.5, 0.0, 2.5, 2.0))
        w = hd.resolve({"id": "pic", "at": [0.1, 1.4, 2], "face": "E"}, CAT)
        fp = hd.footprint(w)
        self.assertAlmostEqual(fp[0], 0.1)  # the back on the west wall's face, the front into the room
        self.assertAlmostEqual(fp[2], 0.13)
        for turn in (0, 90, 180, -90):
            self.assertEqual(hd.tf_yaw(turn, 1, 2, 3), hl._tf(turn, 1, 2, 3))

    def test_scene_nodes_instance_or_placeholder(self):
        rep = made_up([{"id": "box1", "at": [5.4, 0, 0.6]}, {"id": "shelf", "at": [3, 0, 0.5], "size": [2, 0.4, 1.8]}],
                      [{"id": "pic", "at": [3, 1.9, 0.1]}])
        sc = hl._Scene("R")
        held = hd.scene_nodes(sc, rep["rooms"]["r"]["resolved"], lambda i: "res://p_box1.glb" if i == "box1" else None)
        text = sc.text()
        self.assertEqual(held, ["shelf", "pic"])
        self.assertIn('path="res://p_box1.glb"', text)
        self.assertIn('[node name="shelf_1" type="CSGBox3D" parent="Dressing"]', text)
        self.assertIn("size = Vector3(2, 1.8, 0.4)", text)
        self.assertIn("Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 3, 0.9, 0.5)", text)  # the box's centre
        self.assertIn('[node name="pic_1" type="CSGBox3D" parent="Fixtures"]', text)
        self.assertIn("use_collision = false", text)


# The ground floor (#75b): the eight rooms, their stations' props, the room-defining props and the fixtures of the
# plan's inventory (D:/prime-art-raw/research/2026-10-10-house-plan/inventory.md sections 4 and 8).
ROOMS = {
    "wc": {"toilet", "basin"},
    "pantry": {"jar_shelf"},
    "dining_room": {"dining_table", "dining_chair", "sideboard"},
    "living_room": {"sofa", "armchair", "coffee_table", "tv_cabinet", "bookcase", "fireplace"},
    "stairs": {"console_table"},
    "kitchen": {"order_board", "assembly_island", "kitchen_counter", "kitchen_upper", "fridge", "stove", "kitchen_sink"},
    "hallway": {"coat_rack"},
    "terrace": {"terrace_table", "terrace_chair"},
}
FIXTURES = {
    "wc": {"wall_sconce": 1}, "pantry": {"bare_bulb": 1}, "dining_room": {"chandelier": 1, "wall_sconce": 2},
    "living_room": {"floor_lamp": 2, "table_lamp": 1, "wall_sconce": 2}, "stairs": {"wall_sconce": 2},
    "kitchen": {"pendant_shade": 3, "wall_sconce": 1}, "hallway": {"wall_sconce": 2, "porch_lamp": 1},
    "terrace": {"lantern": 4, "string_lights": 2, "porch_lamp": 1},
}
STATION_PROPS = {"DiningTable": {"dining_table"}, "OrderBoard": {"order_board", "assembly_island"},
                 "TerraceTable": {"terrace_table"}}


class GroundFloor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = hl.load()
        cls.files = hd.load(hl.LAYOUT_DIR / cls.data["settings"]["dressing_dir"])
        cls.rooms = {r["id"]: r for lv in cls.data["levels"] if lv["level"] == "ground" for r in lv["rooms"]}

    def test_eight_rooms(self):
        self.assertEqual(set(self.files), set(ROOMS))
        self.assertTrue(set(ROOMS) <= set(self.rooms))

    def test_room_defining_props_and_fixtures(self):
        for rid, want in ROOMS.items():
            ids = {it["id"] for it in self.files[rid].get("props", [])}
            self.assertTrue(want <= ids, f"{rid}: missing {sorted(want - ids)}")
            got: dict = {}
            for it in self.files[rid].get("fixtures", []):
                got[it["id"]] = got.get(it["id"], 0) + 1
            self.assertEqual(got, FIXTURES[rid], rid)

    def test_station_props_stand_on_their_markers(self):
        for rid in ROOMS:
            for s in self.rooms[rid].get("stations", []):
                tagged = {it["id"] for it in self.files[rid]["props"] if it.get("station") == s["name"]}
                self.assertTrue(STATION_PROPS[s["name"]] <= tagged, f"{rid} {s['name']}")
                main = next(it for it in self.files[rid]["props"] if it["id"] in STATION_PROPS[s["name"]])
                self.assertLess(abs(main["at"][0] - s["at"][0]) + abs(main["at"][2] - s["at"][2]), 1.3)

    def test_the_checks_hold(self):
        st = self.data["settings"]
        paths = hd.spec_paths(st)
        lib = [p for p in paths if p.name == "library.toml"]
        if not lib or not lib[0].is_file():
            self.skipTest("props/library.toml (#87) is not on this branch yet")
        rep = hd.check(self.data, self.files, hd.catalogue(paths))
        self.assertEqual(rep["problems"], [])


if __name__ == "__main__":
    unittest.main()
