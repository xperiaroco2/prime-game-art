"""The dining room's new props (#153, docs/props.md "World look rules"): every one builds at its size_m (never more
than 15 mm over it), at its pivot and under its class's triangle budget; the dining chair collides with its seat and
its back, the display cabinet with one box, the detail layer has no collider; the wall art's drawn layers stay inside
the frame's depth; and every detail prop on the dining table stands on its top with a 1 cm margin while the table's
middle stays clear for the game's drop-offs. Pure Python, no Blender (the library-wide checks are test_props_geom's)."""

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
TASKS = {p["id"]: p for p in tomllib.loads((common.ROOT / "props" / "tasks.toml").read_text(encoding="utf-8"))["props"]}

ART = ("art_still_life", "art_delivery", "art_gazebo")
DETAIL = ("art_delivery", "art_gazebo", "place_setting", "serving_board", "fruit_dish", "tulip_vase", "homework",
          "mail_stack")
NEW = DETAIL + ("dining_chair", "chandelier", "dining_rug", "display_cabinet", "art_still_life", "bottle_rack")
OVER_M = 0.015  # a prop may stand at most this far over its size_m
TOP_MARGIN_M = 0.01  # a detail prop on the table keeps this far inside the top's edge
CLEAR_X = (6.25, 6.7)  # room-local x band across the table's middle kept free for the game's drop-offs
DRESSING = common.ROOT / "layouts" / "house" / "dressing" / "dining_room.toml"
FACES = {"S": 0, "E": 90, "N": 180, "W": -90}  # house_dressing.FACES


def _build(pid: str) -> dict:
    return prop_geom.build(BY_ID[pid], SPEC, STYLE)


def _footprint(item: dict, built: dict) -> list[tuple[float, float]]:
    """The four room-local (x, z) corners of a placed prop's bounds."""
    b = built["bounds_m"]
    a = math.radians(float(item.get("yaw", FACES[item.get("face", "S")])))
    out = []
    for x in (b["min"][0], b["max"][0]):
        for z in (b["min"][2], b["max"][2]):
            out.append((item["at"][0] + x * math.cos(a) + z * math.sin(a),
                        item["at"][2] - x * math.sin(a) + z * math.cos(a)))
    return out


class DiningRoomPropsTest(unittest.TestCase):
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
            if p["pivot"] == "ceiling":
                self.assertAlmostEqual(hi[1], 0.0, places=4, msg=f"{pid}: not hung from its top")
                self.assertAlmostEqual(lo[2] + hi[2], 0.0, places=3, msg=f"{pid}: not centred in depth")
                continue
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

    def test_the_chair_and_the_cabinet_collide_with_boxes(self):
        self.assertEqual(len(self.built["dining_chair"]["colliders"]), 2, "the chair: its seat and its back")
        self.assertEqual(len(self.built["display_cabinet"]["colliders"]), 1)
        for pid in ("dining_chair", "display_cabinet"):
            sx, sy, sz = _props.size_xyz(BY_ID[pid]["size_m"])  # a box may fill the size, past a tapered mesh
            for c in self.built[pid]["colliders"]:
                for pt in c["points"]:
                    self.assertLessEqual(abs(pt[0]), sx / 2 + 1e-4, pid)
                    self.assertLessEqual(abs(pt[2]), sz / 2 + 1e-4, pid)
                    self.assertTrue(-1e-3 <= pt[1] <= sy + 1e-3, pid)

    def test_the_pendant_has_a_light_anchor_under_its_shades(self):
        d = self.built["chandelier"]
        anchor = d.get("light_anchor")
        self.assertIsNotNone(anchor, "the pendant has no light anchor")
        self.assertLess(anchor[1], 0.0)
        self.assertGreaterEqual(anchor[1], d["bounds_m"]["min"][1] - 1e-4)

    def test_the_detail_layer_has_no_collider(self):
        for pid in DETAIL + ("bottle_rack", "art_still_life", "dining_rug"):
            self.assertEqual(BY_ID[pid]["collision"], "none", pid)
            self.assertEqual(self.built[pid]["colliders"], [], pid)
        for pid in DETAIL:
            self.assertEqual(BY_ID[pid]["class"], "clutter", pid)

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

    def test_the_table_top_items_stand_on_the_top_and_leave_its_middle_clear(self):
        items = tomllib.loads(DRESSING.read_text(encoding="utf-8"))["props"]
        table = next(i for i in items if i["id"] == "dining_table")
        t = TASKS["dining_table"]
        x0, x1 = table["at"][0] - t["w"] / 2 + TOP_MARGIN_M, table["at"][0] + t["w"] / 2 - TOP_MARGIN_M
        z0, z1 = table["at"][2] - t["d"] / 2 + TOP_MARGIN_M, table["at"][2] + t["d"] / 2 - TOP_MARGIN_M
        on = [i for i in items if abs(i["at"][1] - t["h"]) < 1e-6 and x0 < i["at"][0] < x1 and z0 < i["at"][2] < z1]
        self.assertGreaterEqual(sum(i["id"] == "place_setting" for i in on), 4, "the table is not half-set")
        for item in on:
            built = self.built.get(item["id"]) or _build(item["id"])
            for x, z in _footprint(item, built):
                msg = f"{item['id']} at {item['at']}: a corner at ({x:.3f}, {z:.3f}) is off the table's top"
                self.assertTrue(x0 <= x <= x1 and z0 <= z <= z1, msg)
            xs = [x for x, _ in _footprint(item, built)]
            self.assertTrue(max(xs) <= CLEAR_X[0] or min(xs) >= CLEAR_X[1],
                            f"{item['id']} at {item['at']} reaches into the table's clear middle {CLEAR_X}")


if __name__ == "__main__":
    unittest.main()
