"""The basement (art #78): the doors at the plan's positions, the intended dead ends, the outdoor stairs' foot, the
pillars, the inventory's fixtures and task props, and the sight lines (tools/runner/house_basement.py)."""

from __future__ import annotations

import copy
import unittest
from collections import Counter

from runner import house_basement as B
from runner import house_dressing as hd
from runner import house_layout as H

DATA = H.load()
DRESSING = hd.load(H.LAYOUT_DIR / DATA["settings"].get("dressing_dir", "dressing"))
CAT = hd.catalogue(hd.spec_paths(DATA["settings"]))
LEVEL = next(lv for lv in DATA["levels"] if lv["level"] == "basement")
ROOMS = [r["id"] for r in LEVEL["rooms"]]

# inventory.md section 3: the doors and each room's light fixtures
DOORS = {(30, 28), (22, 34), (40, 28), (40, 38), (49, 42), (46, 22), (58, 31)}
FIXTURES = {
    "storage": {"bare_bulb": 12, "cage_lamp": 2},
    "darkroom": {"safelight_red": 6, "bare_bulb": 3},
    "corridor": {"cage_lamp": 4},
    "boiler_room": {"cage_lamp": 3, "bare_bulb": 2},
    "generator_hall": {"industrial_pendant": 10, "cage_lamp": 4},
    "pump_room": {"cage_lamp": 3},
    "switch_room": {"cage_lamp": 2, "bare_bulb": 1},
    "passage": {"cage_lamp": 3},
}
# the stations' task props (props/tasks.toml) and the procedural room props of #82, per room
TASK_PROPS = {
    "storage": {"bun_shelf": 2, "meat_freezer": 1, "wine_rack": 1, "delivery_box_stack": 3, "wall_switch": 1,
                "car_parts_shelf": 1},
    "darkroom": {"photo_board": 1, "enlarger": 2, "tray_table": 2},
    "boiler_room": {"wall_switch": 1, "boiler": 1},
    "generator_hall": {"generator": 1, "cable_drum": 3},
    "pump_room": {"wall_switch": 1, "pump": 1, "water_tank": 1},
    "switch_room": {"wall_switch": 1, "switchboard": 3},
}


def counts(rid: str, kind: str) -> Counter:
    return Counter(it["id"] for it in DRESSING.get(rid, {}).get(kind, []))


class BasementLayout(unittest.TestCase):
    def test_the_seven_doors_sit_at_the_plan_positions(self) -> None:
        self.assertEqual({tuple(d["at"]) for d in LEVEL["doors"]}, DOORS)

    def test_the_intended_dead_ends_have_one_door_and_no_stairs(self) -> None:
        self.assertEqual(B.dead_ends(DATA), {rid: (1, 0) for rid in B.DEAD_ENDS})

    def test_a_second_door_on_a_dead_end_is_caught(self) -> None:
        data = copy.deepcopy(DATA)
        lv = next(L for L in data["levels"] if L["level"] == "basement")
        lv["doors"].append({"at": [40, 44], "rooms": ["boiler_room", "generator_hall"], "kind": "door"})
        self.assertEqual(B.dead_ends(data)["boiler_room"], (2, 0))

    def test_the_outdoor_stairs_land_in_the_passage(self) -> None:
        st = next(s for L in DATA["levels"] for s in L.get("stairs", []) if s["id"] == "outdoor_stairs")
        self.assertTrue(st.get("placeholder"))
        self.assertEqual(H.check_stairs(DATA), [])
        passage = next(r for r in LEVEL["rooms"] if r["id"] == "passage")
        sh = hd.shell(LEVEL, passage, DATA["levels"])
        feet = [f["name"] for f in sh["feet"]]
        self.assertEqual(feet, ["outdoor_stairs foot"])
        # every flight and the landing lie inside the passage
        for part in [st] + st["below"]:
            x, y, w, d = part["rect"]
            px, py, pw, pd = passage["rect"]
            self.assertTrue(px <= x and x + w <= px + pw and py <= y and y + d <= py + pd, part)

    def test_the_hall_pillars_keep_clear_of_the_generator(self) -> None:
        pillars = [p for p in LEVEL["pieces"] if p["piece"] == "pillar_concrete" and p["room"] == "generator_hall"]
        self.assertEqual(len(pillars), 4)
        hall = next(r for r in LEVEL["rooms"] if r["id"] == "generator_hall")
        gen = next(s for s in hall["stations"] if s["name"] == "Generator")
        gx, gy = hall["rect"][0] + gen["at"][0], hall["rect"][1] + gen["at"][2]
        for p in pillars:
            self.assertGreaterEqual(max(abs(p["at"][0] - gx), abs(p["at"][2] - gy)), 4, p)

    def test_pillars_block_the_capsule(self) -> None:
        hall = next(r for r in LEVEL["rooms"] if r["id"] == "generator_hall")
        boxes = hd.shell(LEVEL, hall, DATA["levels"])["stairs"]
        self.assertIn((3.8, 3.8, 4.2, 4.2), [tuple(round(v, 3) for v in b) for b in boxes])


class BasementDressing(unittest.TestCase):
    def test_every_room_is_dressed_and_holds(self) -> None:
        self.assertEqual(sorted(r for r in DRESSING if r in ROOMS), sorted(ROOMS))
        for room in LEVEL["rooms"]:
            rep = hd.check_room(LEVEL, room, DRESSING[room["id"]], CAT, DATA["levels"])
            self.assertEqual(rep["problems"], [], room["id"])
            self.assertTrue(all(rep["reach"].values()), room["id"])

    def test_the_55_fixtures_follow_the_inventory(self) -> None:
        got = {rid: dict(counts(rid, "fixtures")) for rid in ROOMS}
        self.assertEqual(got, FIXTURES)
        self.assertEqual(sum(sum(v.values()) for v in got.values()), 55)

    def test_the_task_and_room_props_are_placed(self) -> None:
        for rid, want in TASK_PROPS.items():
            got = counts(rid, "props")
            for pid, n in want.items():
                self.assertEqual(got[pid], n, f"{rid}: {pid}")

    def test_each_switch_belongs_to_its_station(self) -> None:
        for rid, name in (("storage", "SwitchA"), ("boiler_room", "SwitchB"), ("pump_room", "SwitchC"),
                          ("switch_room", "SwitchD")):
            sw = [it for it in DRESSING[rid]["props"] if it["id"] == "wall_switch"]
            self.assertEqual([it.get("station") for it in sw], [name])

    def test_switches_are_in_sight_from_their_doors(self) -> None:
        rows = B.switch_sight(DATA, DRESSING, CAT)
        self.assertEqual(len(rows), 5)  # storage has two doors
        for r in rows:
            self.assertGreater(r["clear"], 0.3, r)

    def test_the_hall_reads_from_the_passage(self) -> None:
        rows = B.hall_sight(DATA, DRESSING, CAT)
        self.assertEqual(len(rows), 13)
        for r in rows:
            self.assertGreaterEqual(r["clear"], 0.5, r)

    def test_a_tall_prop_on_a_sight_line_blocks_it(self) -> None:
        dressing = copy.deepcopy(DRESSING)
        dressing["pump_room"]["props"].append({"id": "metal_shelving", "at": [7.5, 0, 3.5]})
        row = next(r for r in B.switch_sight(DATA, dressing, CAT) if "SwitchC" in r["line"])
        self.assertLessEqual(row["clear"], 0.0)


if __name__ == "__main__":
    unittest.main()
