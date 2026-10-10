"""How full the House's rooms read (art #104 pass 2, tools/runner/house_fill.py): the measures on made-up rooms, and
the dressed rooms against main's numbers."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runner import house_dressing as hd  # noqa: E402
from runner import house_fill as hf  # noqa: E402
from runner import house_layout as hl  # noqa: E402

CAT = {"case": {"size": [2.0, 0.4, 2.0], "pivot": "floor", "collision": "box", "class": "room"},
       "cup": {"size": [0.1, 0.1, 0.1], "pivot": "floor", "collision": "none", "class": "clutter"},
       "upper": {"size": [1.0, 0.35, 0.7], "pivot": "wall", "collision": "box", "class": "room"},
       "stool": {"size": [0.4, 0.4, 0.6], "pivot": "floor", "collision": "box", "class": "dressing"}}
LEVEL = {"level": "t", "floor_y": 0.0, "doors": [], "windows": [], "holes": [], "stairs": [],
         "rooms": [{"id": "box", "kind": "room", "rect": [0, 0, 4, 5]}]}
ROOM = LEVEL["rooms"][0]


def measure(props: list) -> dict:
    return hf.metrics(LEVEL, ROOM, {"props": props}, CAT, [LEVEL])


class Measures(unittest.TestCase):
    def test_an_empty_room(self) -> None:
        m = measure([])
        self.assertAlmostEqual(m["free_wall_m"], 18.0, places=2)  # along the grid lines
        self.assertEqual((m["wall_pct"], m["floor_pct"], m["heights"], m["stories"]), (0.0, 0.0, "", []))

    def test_a_case_against_the_north_wall(self) -> None:
        m = measure([{"id": "case", "at": [1.2, 0, 0.3], "face": "S"}])
        self.assertAlmostEqual(m["lined_m"], 2.0, places=2)
        self.assertAlmostEqual(m["floor_pct"], 4.0, delta=0.6)  # 0.8 of 20 m2
        self.assertIn("T", m["heights"])

    def test_off_the_wall_loose_and_clutter_do_not_line(self) -> None:
        m = measure([{"id": "case", "at": [2.0, 0, 2.5], "face": "S"},  # the room's middle
                     {"id": "stool", "at": [1.0, 0, 0.3]}, {"id": "cup", "at": [3.0, 0, 0.2]}])
        self.assertEqual(m["lined_m"], 0.0)

    def test_a_wall_cabinet_lines_and_a_door_is_not_wall(self) -> None:
        lv = dict(LEVEL, doors=[{"at": [2, 0], "rooms": ["box"], "kind": "door"}])
        m = hf.metrics(lv, ROOM, {"props": [{"id": "upper", "at": [0.7, 1.5, 0.1], "face": "S"}]}, CAT, [lv])
        self.assertAlmostEqual(m["free_wall_m"], 18.0 - 1.4, places=2)
        self.assertAlmostEqual(m["lined_m"], 1.0, places=2)

    def test_a_story_needs_its_parts_near(self) -> None:
        res = [{"id": "armchair", "at": [1, 0, 1], "fp": (0.5, 0.5, 1.5, 1.5)},
               {"id": "floor_lamp", "at": [2, 0, 1], "fp": (1.8, 0.8, 2.2, 1.2)},
               {"id": "small_table", "at": [0, 0, 2], "fp": (0.1, 1.7, 0.6, 2.3)},
               {"id": "book_stack", "at": [0, 0.7, 2], "fp": (0.2, 1.9, 0.4, 2.1)}]
        self.assertEqual(hf.stories(res), ["reading corner"])
        res[3] = dict(res[3], fp=(5.0, 5.0, 5.2, 5.2))
        self.assertEqual(hf.stories(res), [])


class House(unittest.TestCase):
    def test_every_room_is_fuller_than_on_main(self) -> None:
        data = hl.load()
        cat = hd.catalogue(hd.spec_paths(data["settings"]))
        rows = {m["room"]: m for m in hf.table(data, hd.load(hl.LAYOUT_DIR / data["settings"]["dressing_dir"]), cat)}
        self.assertEqual(len(rows), 21)
        for rid, m in rows.items():
            self.assertEqual(m["heights"], "FST", rid)
            self.assertGreaterEqual(m["wall_pct"], MAIN_WALL[rid] + 5, rid)  # main 3c8add0, pass 1


# main 3c8add0's wall lining per room (pass 1, measured 2026-10-10 with this module)
MAIN_WALL = {"storage": 33.2, "darkroom": 20.9, "corridor": 6.0, "boiler_room": 5.5, "generator_hall": 7.7,
             "pump_room": 5.1, "switch_room": 21.1, "passage": 0.0, "wc": 12.6, "pantry": 26.7, "dining_room": 15.5,
             "living_room": 30.7, "stairs": 24.4, "kitchen": 29.6, "hallway": 24.6, "bedroom": 30.9,
             "kids_room": 27.0, "landing": 16.8, "study": 22.4, "bathroom": 18.4, "guest_room": 28.5}


if __name__ == "__main__":
    unittest.main()
