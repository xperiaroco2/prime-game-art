"""The living room's round-2 props (#150, docs/props.md): the floor plant collides only with its pot, the detail
layer's small props have no collider and keep to the clutter budget, and the wall art's drawn layers stay inside the
frame's depth on the wall. Pure Python, no Blender (the generic checks are test_props_geom's)."""

from __future__ import annotations

import json
import sys
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
DETAIL = ("table_plant", "side_lamp", "game_console", "board_games", "slippers", "laptop", "deco_vase", "deco_bowl",
          "coffee_books", "candle_jars", "art_photos", "art_score")


def _build(pid: str) -> dict:
    return prop_geom.build(BY_ID[pid], SPEC, STYLE)


class LivingRoundTwoTest(unittest.TestCase):
    def test_the_floor_plant_collides_with_its_pot_only(self):
        d = _build("floor_plant")
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
            d = _build(pid)
            self.assertEqual(d["colliders"], [], pid)
            self.assertLessEqual(d["triangles"], tri_max, pid)

    def test_the_wall_art_stays_inside_its_frame_depth(self):
        for pid in ART:
            p = BY_ID[pid]
            self.assertEqual(p["pivot"], "wall", pid)
            depth = p["size_m"][1]
            b = _build(pid)["bounds_m"]
            self.assertGreaterEqual(b["min"][2], -1e-4, f"{pid}: behind the wall")
            self.assertLessEqual(b["max"][2], depth + 1e-4, f"{pid}: deeper than its frame")
            self.assertAlmostEqual(b["max"][0] - b["min"][0], p["size_m"][0], delta=0.01, msg=pid)
            self.assertAlmostEqual(b["max"][1] - b["min"][1], p["size_m"][2], delta=0.01, msg=pid)


if __name__ == "__main__":
    unittest.main()
