"""The attic's room-by-room pass (#168, docs/props.md "World look rules", docs/house.md "The attic and the free roof"):
its new and rebuilt props build at their size_m (never more than 15 mm over it), at their floor pivot and under their
class's triangle budget; the furniture collides inside its size (a box or a hull), the detail-layer delivery bag has
no collider; the dressing keeps 0.3 m from the HidingSpots station and the Knife3 spawn marker (read from
layouts/house/attic.toml, asserted), off the kept-free floor (the hatch's apron, the dormer's climb-out, round
Knife3) and the chimneys, keeps its twelve hiding spots where they were, keeps main's big furniture, is never emptier
than main's 44 old things, and keeps the Name label out of every piece and light fixture. Pure Python, no Blender."""

from __future__ import annotations

import json
import math
import sys
import tomllib
import unittest

from runner import common, house_attic, house_layout, house_lights
from runner.commands import _props

sys.path.insert(0, str(common.ROOT / "tools" / "blender"))
import prop_geom  # noqa: E402

LIB = _props.load()
KIT = json.loads((common.ROOT / LIB["kit_spec"]).read_text(encoding="utf-8"))
SPEC = prop_geom.lib_spec(LIB, KIT)
STYLE = prop_geom.Style.from_lib(LIB)
BY_ID = {p["id"]: p for p in LIB["prop"]}
LAYOUT = common.ROOT / "layouts" / "house"
HOUSE = tomllib.loads((LAYOUT / "house.toml").read_text(encoding="utf-8"))
DATA = house_layout.load()
ATTIC = house_attic.load("attic")

BEFORE = 44  # main's [[items]] before the pass (items against items: the spots and roof items are not counted)
# main's hiding spots: their names and places stay (the game's packages lie there)
SPOTS = {"TrunkNorth": [22, 24.5], "WardrobeTopNorth": [20, 24.5], "SheetNorth": [33.5, 25], "SheetWest": [19, 30.2],
         "WardrobeSouth": [19, 43.5], "TrunkSouthWest": [21, 43.5], "CrateWest": [21.5, 38.6],
         "SheetSouthWest": [22.9, 42.4], "BoxSouth": [25.1, 43.05], "TrunkSouthEast": [31.6, 43.5],
         "BicycleBasket": [39, 43.45], "SheetEast": [40.9, 27.6]}
POINTS = {"HidingSpots": (22.0, 39.0), "Knife3": (36.0, 37.0)}
# the floor kept free: the hatch and its 1 m apron, the dormer's climb-out, 1 m round Knife3 ([x, y, w, d])
CLEAR = [[26, 27, 4, 4], [33.4, 39.5, 3.2, 4.5], [35, 36, 2, 2]]
# main's big furniture, kept (a group's ids together at least this many)
BIG = [(("old_wardrobe",), 2), (("trunk",), 6), (("sheeted_furniture", "sheeted_sofa", "sheeted_dresser"), 5),
       (("old_bicycle",), 1), (("mannequin",), 1), (("rocking_horse",), 1), (("standing_mirror",), 1),
       (("rolled_carpet",), 3), (("rug",), 2)]
NEW = ("old_wardrobe", "sheeted_furniture", "trunk", "old_bicycle", "attic_shelving", "attic_shelving_b",
       "storage_box", "storage_crate", "holiday_decor", "burger_sign", "delivery_bag", "generator_part", "sports_kit",
       "leaning_frames", "sheeted_sofa", "sheeted_dresser", "mannequin", "rocking_horse")
DETAIL = ("delivery_bag",)
OVER_M = 0.015
CLEAR_M = 0.3


def _box_dist(poly, x: float, y: float) -> float:
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    return math.hypot(max(min(xs) - x, 0.0, x - max(xs)), max(min(ys) - y, 0.0, y - max(ys)))


def _overlaps(poly, r) -> bool:
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    return min(xs) < r[0] + r[2] - 1e-6 and max(xs) > r[0] + 1e-6 and min(ys) < r[1] + r[3] - 1e-6 \
        and max(ys) > r[1] + 1e-6


class AtticPropsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.built = {pid: prop_geom.build(BY_ID[pid], SPEC, STYLE) for pid in NEW}

    def test_every_new_prop_builds_at_its_size(self):
        for pid in NEW:
            want, got = _props.size_xyz(BY_ID[pid]["size_m"]), self.built[pid]["size_m"]
            for g, w in zip(got, want):
                msg = f"{pid}: built {got}, want {want}"
                self.assertLessEqual(g, w + OVER_M, msg)
                self.assertGreaterEqual(g, w - max(0.03, 0.12 * w), msg)

    def test_every_new_prop_sits_at_its_floor_pivot(self):
        for pid in NEW:
            self.assertEqual(BY_ID[pid].get("pivot", "floor"), "floor", pid)
            lo, hi = self.built[pid]["bounds_m"]["min"], self.built[pid]["bounds_m"]["max"]
            self.assertAlmostEqual(lo[0] + hi[0], 0.0, places=3, msg=f"{pid}: not centred across")
            self.assertAlmostEqual(lo[1], 0.0, places=4, msg=f"{pid}: not on its base")
            self.assertAlmostEqual(lo[2] + hi[2], 0.0, places=3, msg=f"{pid}: not centred in depth")

    def test_every_new_prop_keeps_its_class_budget(self):
        for pid in NEW:
            _, hi = LIB["budgets"][BY_ID[pid]["class"]]
            self.assertTrue(0 < self.built[pid]["triangles"] <= hi, f"{pid}: {self.built[pid]['triangles']}")

    def test_the_furniture_collides_inside_its_size_and_the_detail_props_not(self):
        for pid in NEW:
            p, d = BY_ID[pid], self.built[pid]
            if pid in DETAIL:
                self.assertEqual(p["collision"], "none", pid)
                self.assertEqual(LIB["layers"][p["class"]], "detail", pid)
                self.assertEqual(d["colliders"], [], pid)
                continue
            self.assertIn(p["collision"], ("box", "hull"), pid)
            self.assertTrue(d["colliders"], pid)
            if p["collision"] == "hull":
                self.assertEqual(len(d["colliders"]), 1, pid)
            sx, sy, sz = _props.size_xyz(p["size_m"])
            for c in d["colliders"]:
                for pt in c["points"]:
                    self.assertLessEqual(abs(pt[0]), sx / 2 + OVER_M, pid)
                    self.assertTrue(-1e-3 <= pt[1] <= sy + OVER_M, pid)
                    self.assertLessEqual(abs(pt[2]), sz / 2 + OVER_M, pid)

    def test_the_points_are_the_layouts(self):
        room = next(r for r in house_attic._level(DATA, "attic")["rooms"] if r["id"] == "attic")
        rx, ry = room["rect"][0], room["rect"][1]
        got = {s["name"]: (rx + s["at"][0], ry + s["at"][2]) for s in room.get("stations", []) + room.get("markers", [])
               if s["name"] in POINTS}
        self.assertEqual(got, POINTS)
        self.assertEqual(ATTIC["clear"], CLEAR)

    def test_the_dressing_keeps_clear_of_the_station_and_the_spawn(self):
        for it in ATTIC["items"]:
            fp = house_attic.footprint(it)
            for name, (x, y) in POINTS.items():
                self.assertGreaterEqual(_box_dist(fp, x, y), CLEAR_M, f"{it['id']} at {it['at']} within {CLEAR_M} m "
                                                                       f"of {name}")

    def test_the_kept_free_floor_and_the_chimneys_stay_free(self):
        chim = [c["poly"] for c in house_attic.chimneys(DATA) if c["base"] <= 0]
        self.assertTrue(chim)
        for it in ATTIC["items"]:
            if it["h"] < house_attic.FLAT_H:
                continue
            fp = house_attic.footprint(it)
            for r in CLEAR:
                self.assertFalse(_overlaps(fp, r), f"{it['id']} at {it['at']} on the kept-free floor {r}")
            for c in chim:
                xs, ys = [p[0] for p in c], [p[1] for p in c]
                r = [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)]
                self.assertFalse(_overlaps(fp, r), f"{it['id']} at {it['at']} on a chimney")

    def test_the_hiding_spots_stay_and_are_reachable(self):
        self.assertEqual({s["name"]: s["at"] for s in ATTIC["spots"]}, SPOTS)
        spots = house_attic.reach(ATTIC, DATA)
        self.assertEqual([s["name"] for s in spots if not (s["reachable"] and s["host"] is not None)], [])

    def test_the_attic_is_never_emptier_than_before(self):
        raw = tomllib.loads((house_attic.DRESSING / "attic.toml").read_text(encoding="utf-8"))
        self.assertEqual(len(ATTIC["items"]), len(raw["items"]))
        self.assertGreaterEqual(len(raw["items"]), BEFORE)
        self.assertEqual(sum(house_attic.COUNTS["attic"].values()), len(raw["items"]))

    def test_the_attic_keeps_mains_big_furniture(self):
        ids = [it["id"] for it in ATTIC["items"]]
        for group, n in BIG:
            self.assertGreaterEqual(sum(ids.count(i) for i in group), n, f"{group}: fewer than main's {n}")

    def test_the_name_label_sits_in_no_piece_and_on_no_fixture(self):
        room = next(r for r in house_attic._level(DATA, "attic")["rooms"] if r["id"] == "attic")
        x, y, w, d = room["rect"]
        lx, ly = room["label_at"] if room.get("label_at") else (x + w / 2, y + d / 2)
        h = HOUSE["export"]["label"]["h"]
        for it in ATTIC["items"]:
            self.assertFalse(_box_dist(house_attic.footprint(it), lx, ly) < 0.2 and h < it["h"] + 0.3,
                             f"the Name label at ({lx}, {h}, {ly}) is inside {it['id']} at {it['at']}")
        fixtures = [f for f in house_lights.plan(house_lights.load(), DATA) if f["room"] == "attic"
                    and f["type"] != "moon"]
        self.assertTrue(fixtures)
        floor_y = house_attic._level(DATA, "attic")["floor_y"]
        for f in fixtures:
            near = math.hypot(f["x"] - lx, f["y"] - ly) < 0.5
            self.assertFalse(near and abs(f["h"] - floor_y - h) < 0.5,
                             f"the Name label at ({lx}, {h}, {ly}) is on the fixture {f['name']}")
            if f["h"] - floor_y < 1.5:  # a standing lamp: no piece over it
                for it in ATTIC["items"]:
                    self.assertGreaterEqual(_box_dist(house_attic.footprint(it), f["x"], f["y"]), CLEAR_M,
                                            f"{it['id']} at {it['at']} on the lamp {f['name']}")


if __name__ == "__main__":
    unittest.main()
