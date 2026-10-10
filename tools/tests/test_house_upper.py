"""The House map's second floor (art #76, docs/house.md "Dressing"): the seven rooms' dressing files against the plan's
inventory (section 5), the study's Printer station, the hatch ladder and the external stairs reached by the capsule."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runner import house_dressing as hd  # noqa: E402
from runner import house_layout as hl  # noqa: E402

# room-defining and task-critical props per room (inventory.md section 5; the rocking horse is hero class, not made)
ROOMS = {
    "bedroom": {"double_bed", "wardrobe", "nightstand", "dresser"},
    "kids_room": {"bunk_bed", "desk", "bookcase", "toy_chest"},
    "landing": {"landing_bench", "console_table"},
    "study": {"desk", "computer_set", "photo_printer", "office_chair", "bookcase", "filing_cabinet"},
    "bathroom": {"bathtub", "toilet", "basin"},
    "guest_room": {"single_bed", "wardrobe", "nightstand"},
    "balcony": {"balcony_chair", "small_table", "planter_pot"},
}
FIXTURES = {
    "bedroom": {"table_lamp": 2, "pendant_shade": 1}, "kids_room": {"table_lamp": 1, "pendant_shade": 1},
    "landing": {"wall_sconce": 4, "pendant_shade": 2}, "study": {"table_lamp": 1, "pendant_shade": 1},
    "bathroom": {"wall_sconce": 2}, "guest_room": {"table_lamp": 2},
    "balcony": {"lantern": 2, "string_lights": 1},
}


class SecondFloor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = hl.load()
        cls.files = hd.load(hl.LAYOUT_DIR / cls.data["settings"]["dressing_dir"])
        cls.level = next(lv for lv in cls.data["levels"] if lv["level"] == "upper")
        cls.rooms = {r["id"]: r for r in cls.level["rooms"]}

    def test_seven_rooms(self):
        self.assertEqual(set(self.rooms), set(ROOMS))
        self.assertEqual({r for r in self.files if r in self.rooms}, set(ROOMS))

    def test_room_defining_props_and_fixtures(self):
        for rid, want in ROOMS.items():
            ids = {it["id"] for it in self.files[rid].get("props", [])}
            self.assertTrue(want <= ids, f"{rid}: missing {sorted(want - ids)}")
            got: dict = {}
            for it in self.files[rid].get("fixtures", []):
                got[it["id"]] = got.get(it["id"], 0) + 1
            self.assertEqual(got, FIXTURES[rid], rid)

    def test_the_printer_station_is_the_desk_set(self):
        st = next(s for s in self.rooms["study"]["stations"] if s["name"] == "Printer")
        rx, ry = self.rooms["study"]["rect"][:2]
        self.assertEqual((rx + st["at"][0], ry + st["at"][2]), (40, 29))  # the plan's computer desk
        props = self.files["study"]["props"]
        tagged = {it["id"] for it in props if it.get("station") == "Printer"}
        self.assertEqual(tagged, {"desk", "computer_set", "photo_printer", "office_chair"})
        desk = next(it for it in props if it["id"] == "desk")
        self.assertLess(abs(desk["at"][0] - st["at"][0]) + abs(desk["at"][2] - st["at"][2]), 0.1)
        for pid in ("computer_set", "photo_printer"):  # on the desk top
            it = next(i for i in props if i["id"] == pid)
            self.assertAlmostEqual(it["at"][1], 0.75)
            self.assertLess(abs(it["at"][0] - desk["at"][0]), 0.35)
            self.assertLess(abs(it["at"][2] - desk["at"][2]), 0.7)

    def test_the_hatch_ladder_stands_on_the_landing(self):
        attic = next(lv for lv in self.data["levels"] if lv["level"] == "attic")
        lad = next(s for s in attic["stairs"] if s["id"] == "hatch_ladder")
        x, y, w, d = lad["rect"]
        dx, dy = hl.CLIMB[lad["climb"]]
        foot = (x + w / 2 - dx * (w / 2 + 0.8), y + d / 2 - dy * (d / 2 + 0.8))
        self.assertTrue(hl.inside(self.rooms["landing"]["rect"], *foot))
        well = next(h for h in self.level["holes"] if h["id"] == "main_stairs")["rect"]
        self.assertFalse(hl.inside(well, *foot), "the ladder's foot over the stairwell")

    def test_the_checks_hold_and_reach_the_ladder_and_the_stairs(self):
        paths = hd.spec_paths(self.data["settings"])
        rep = hd.check(self.data, {r: self.files[r] for r in ROOMS}, hd.catalogue(paths))
        self.assertEqual(rep["problems"], [])
        self.assertTrue(rep["rooms"]["landing"]["reach"]["hatch_ladder foot"])
        self.assertTrue(rep["rooms"]["balcony"]["reach"]["door N (9, 0)"])  # the gap at the external stairs' top
        for rid in ROOMS:
            self.assertTrue(all(v for k, v in rep["rooms"][rid]["reach"].items() if k.startswith("door")), rid)

    def test_review_shots_and_lamps(self):
        paths = [p for p in hd.spec_paths(self.data["settings"]) if p.is_file()]
        rep = hd.check(self.data, {r: self.files[r] for r in ROOMS}, hd.catalogue(paths))
        req = hd.review_request(self.data, rep["rooms"])
        shots = {s["room"]: s for s in req["room_shots"]}
        self.assertEqual(set(shots), set(ROOMS))
        fy = self.level["floor_y"]
        for rid, s in shots.items():  # upper.png: from its door at 1.6 m above the second floor, looking inside
            self.assertEqual(s["level"], "upper")
            rx, rz, w, d = self.rooms[rid]["rect"]
            for x, _, z in (s["from"], s["to"]):
                self.assertTrue(rx < x < rx + w and rz < z < rz + d, f"{rid}: {s}")
            self.assertAlmostEqual(s["from"][1], fy + hd.EYE)
        self.assertEqual(len(req["lamps"]), sum(sum(f.values()) for f in FIXTURES.values()))
        self.assertTrue(all(fy < lp["at"][1] < fy + 3.2 for lp in req["lamps"]))

    def test_the_balcony_loop_is_walked_at_the_game_speed(self):
        loop = next(w for w in hl.walk_request(self.data)["walks"] if w["name"] == "loop:balcony_loop")
        self.assertEqual((loop["kind"], loop["speed"], loop["doc_m"], loop["doc_s"]), ("loop", 4.5, 46, 10.2))
        pts = loop["points"]
        self.assertEqual(pts[0], pts[-1])
        plan = [(round(x, 1), round(y, 1)) for x, _, y in pts]
        for door in ((32, 30), (32, 24), (36, 24)):  # stairs room, balcony, terrace door: crossed between two points
            self.assertTrue(any(min(a[0], b[0]) <= door[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= door[1] <= max(a[1], b[1])
                                for a, b in zip(plan, plan[1:])), door)
        self.assertIn([39.0, 3.2, 21.0], pts)  # the external stairs' top
        self.assertIn([39.0, 0.0, 14.2], pts)  # off their foot on the yard (Q6: the last step ends at y 15)
        length, _ = hl.loop_length(pts)
        self.assertGreater(length, 46 - 12)  # the doc counts each level change as 6 m


if __name__ == "__main__":
    unittest.main()
