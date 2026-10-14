"""The living room's new props (#150, docs/props.md): every one builds at its size_m (never more than 15 mm over it,
so a detail prop does not overhang the top it stands on), at its pivot and under its class's triangle budget; the
floor plant collides only with its pot, the detail layer's small props have no collider and keep to the clutter
budget, the wall art's drawn layers stay inside the frame's depth on the wall, and a detail prop on a round side
table stands fully on its top with a 1 cm margin. Pure Python, no Blender (the library-wide checks are
test_props_geom's)."""

from __future__ import annotations

import json
import math
import sys
import tomllib
import unittest

from runner import common
from runner.commands import _props

sys.path.insert(0, str(common.ROOT / "tools" / "blender"))
import prop_geom  # noqa: E402

LIB = _props.load()
KIT = json.loads((common.ROOT / LIB["kit_spec"]).read_text(encoding="utf-8"))
SPEC = prop_geom.lib_spec(LIB, KIT)
STYLE = prop_geom.Style.from_lib(LIB)
BY_ID = {p["id"]: p for p in LIB["prop"]}

ART = ("art_abstract", "art_city", "art_burger", "art_photos", "art_score")
DETAIL = ("living_tray", "magazine_fan", "mantel_clock", "standing_frame", "throw_basket", "candle_pair",
          "table_plant", "side_lamp", "game_console", "board_games", "slippers", "laptop", "deco_vase", "deco_bowl",
          "coffee_books", "candle_jars", "art_photos", "art_score")
NEW = DETAIL + ("floor_plant", "art_abstract", "art_city", "art_burger")
OVER_M = 0.015  # a detail prop may stand at most this far over its size_m
TOP_MARGIN_M = 0.01  # a detail prop on a side table keeps this far inside the top's edge
DRESSING = common.ROOT / "layouts" / "house" / "dressing" / "living_room.toml"
FACES = {"S": 0, "E": 90, "N": 180, "W": -90}  # house_dressing.FACES


def _build(pid: str) -> dict:
    return prop_geom.build(BY_ID[pid], SPEC, STYLE)


class LivingRoundTwoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.built = {pid: _build(pid) for pid in NEW}

    def test_every_new_prop_builds_at_its_size(self):
        for pid in NEW:
            p, d = BY_ID[pid], self.built[pid]
            want = _props.size_xyz(p.get("built_size_m", p["size_m"]))
            for got, w in zip(d["size_m"], want):
                msg = f"{pid}: built {d['size_m']}, want {want}"
                self.assertLessEqual(got, w + OVER_M, msg)
                self.assertGreaterEqual(got, w - max(0.03, 0.12 * w), msg)

    def test_every_new_prop_sits_at_its_pivot(self):
        for pid in NEW:
            p, b = BY_ID[pid], self.built[pid]["bounds_m"]
            lo, hi = b["min"], b["max"]
            self.assertAlmostEqual(lo[0] + hi[0], 0.0, places=3, msg=f"{pid}: not centred across")
            self.assertAlmostEqual(lo[1], 0.0, places=4, msg=f"{pid}: not on its base")
            if p["pivot"] == "wall":
                self.assertAlmostEqual(lo[2], 0.0, places=4, msg=f"{pid}: its back is off the wall")
            else:
                self.assertEqual(p["pivot"], "floor", pid)
                self.assertAlmostEqual(lo[2] + hi[2], 0.0, places=3, msg=f"{pid}: not centred in depth")

    def test_every_new_prop_keeps_its_class_budget(self):
        for pid in NEW:
            p = BY_ID[pid]
            self.assertLessEqual(self.built[pid]["triangles"], LIB["budgets"][p["class"]][1], pid)

    def test_the_floor_plant_collides_with_its_pot_only(self):
        d = self.built["floor_plant"]
        self.assertEqual(BY_ID["floor_plant"]["collision"], "box")
        self.assertEqual(len(d["colliders"]), 1)
        pts = d["colliders"][0]["points"]
        top = max(p[1] for p in pts)
        self.assertLess(top, 0.4 * d["bounds_m"]["max"][1], "the collider reaches above the pot")
        self.assertLessEqual(max(abs(p[0]) for p in pts), d["bounds_m"]["max"][0] + 1e-4)

    def test_the_detail_layer_has_no_collider_and_keeps_the_clutter_budget(self):
        tri_max = LIB["budgets"]["clutter"][1]
        for pid in DETAIL:
            p = BY_ID[pid]
            self.assertEqual(p["class"], "clutter", pid)
            self.assertEqual(p["collision"], "none", pid)
            d = self.built[pid]
            self.assertEqual(d["colliders"], [], pid)
            self.assertLessEqual(d["triangles"], tri_max, pid)

    def test_the_wall_art_stays_inside_its_frame_depth(self):
        for pid in ART:
            p = BY_ID[pid]
            self.assertEqual(p["pivot"], "wall", pid)
            depth = p["size_m"][1]
            b = self.built[pid]["bounds_m"]
            self.assertGreaterEqual(b["min"][2], -1e-4, f"{pid}: behind the wall")
            self.assertLessEqual(b["max"][2], depth + 1e-4, f"{pid}: deeper than its frame")
            self.assertAlmostEqual(b["max"][0] - b["min"][0], p["size_m"][0], delta=0.01, msg=pid)
            self.assertAlmostEqual(b["max"][1] - b["min"][1], p["size_m"][2], delta=0.01, msg=pid)

    def test_the_detail_on_a_side_table_stands_on_its_top(self):
        items = tomllib.loads(DRESSING.read_text(encoding="utf-8"))["props"]
        tables = [i for i in items if i["id"] == "small_table"]
        r = min(BY_ID["small_table"]["size_m"][:2]) / 2  # prop_geom.build_side_table: a round top
        top = BY_ID["small_table"]["size_m"][2]
        # the side lamp's shade may reach past the top over its much smaller round base: its bounds do not tell
        on = [(i, t) for i in items if i["id"] in DETAIL and i["id"] != "side_lamp" and abs(i["at"][1] - top) < 1e-6
              for t in tables if math.dist((i["at"][0], i["at"][2]), (t["at"][0], t["at"][2])) < r]
        self.assertTrue(any(i["id"] == "standing_frame" for i, _ in on), "no standing frame on a side table")
        for item, table in on:
            if item["id"] not in self.built:
                continue
            b = self.built[item["id"]]["bounds_m"]
            a = math.radians(float(item.get("yaw", FACES[item.get("face", "S")])))
            half = ((b["max"][0] - b["min"][0]) / 2, (b["max"][2] - b["min"][2]) / 2)
            mid = ((b["max"][0] + b["min"][0]) / 2, (b["max"][2] + b["min"][2]) / 2)
            if abs(half[0] - half[1]) < 0.05 * max(half):  # a square footprint is a round prop (the bowl): its disc
                pts, extra = [mid], max(half)
            else:  # a rectangle (the frame): its four corners
                pts, extra = [(mid[0] + sx * half[0], mid[1] + sz * half[1]) for sx in (-1, 1) for sz in (-1, 1)], 0.0
            for x, z in pts:
                wx = item["at"][0] + x * math.cos(a) + z * math.sin(a)
                wz = item["at"][2] - x * math.sin(a) + z * math.cos(a)
                d = math.dist((wx, wz), (table["at"][0], table["at"][2])) + extra
                self.assertLessEqual(d, r - TOP_MARGIN_M, f"{item['id']} at {item['at']}: reaches {d:.3f} m "
                                     f"from the side table's centre, its top's radius {r} m")


if __name__ == "__main__":
    unittest.main()
