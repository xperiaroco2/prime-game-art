"""The sheen on top of the House's bake (#83c; tools/runner/house_bake.py, docs/house.md "The sheen")."""

import tomllib
import unittest

from runner import common, house_bake as B, house_layout, house_lights
from runner.commands import _house_bake

LIGHTS = common.ROOT / "layouts" / "house" / "lights.toml"


class SheenModes(unittest.TestCase):
    def test_tokens(self):
        self.assertEqual(B.sheen_mode("lmspec5"), {"lm_specular": 0.5, "probes": False, "n": 0, "shadow": False})
        self.assertEqual(B.sheen_mode("lmspec10_probes"),
                         {"lm_specular": 1.0, "probes": True, "n": 0, "shadow": False})
        self.assertEqual(B.sheen_mode("sheen4_shadow"), {"lm_specular": 0.0, "probes": False, "n": 4, "shadow": True})
        self.assertEqual(B.sheen_mode("probes"), {"lm_specular": 0.0, "probes": True, "n": 0, "shadow": False})

    def test_not_a_sheen_mode(self):
        for mode in ("baked", "hybrid", "shadow", "probes_shadow", "lmspec", "sheen0", "lmspec0", "probes_", ""):
            self.assertIsNone(B.sheen_mode(mode), mode)

    def test_rows_carry_the_settings(self):
        rows = B.shot_rows("ground", [{"tag": "t8", "modes": ["baked", "lmspec10_probes"]}])
        self.assertEqual(rows[0], {"label": "ground_t8_baked", "tag": "t8", "mode": "baked"})
        self.assertEqual(rows[1]["label"], "ground_t8_lmspec10_probes")
        self.assertEqual(rows[1]["sheen"], B.sheen_mode("lmspec10_probes"))
        with self.assertRaises(ValueError):
            B.shot_rows("ground", [{"tag": "t8", "modes": ["probes_glitter"]}])


class SheenGrid(unittest.TestCase):
    def setUp(self):
        self.lights = tomllib.loads(LIGHTS.read_text(encoding="utf-8"))

    def test_three_bakes_at_most_nine_rows(self):
        base, direc, ld = B.sheen_variants(self.lights, "ground")
        texel = self.lights["zones"]["ground"]["texel_high"]
        self.assertEqual({v["texel"] for v in (base, direc, ld)}, {texel})
        self.assertEqual((base["bake"]["directional"], direc["bake"]["directional"]), (False, True))
        self.assertEqual(base["bake"]["specular_intensity"], 0.0)  # the lobe is set per row, at shot time
        self.assertEqual((ld["lights"], ld["modes"]), ("dynamic", ["hybrid"]))
        self.assertEqual(direc["tag"], base["tag"] + "_dir")
        rows = B.shot_rows("ground", [base, direc, ld])
        self.assertLessEqual(len(rows), 9)
        self.assertEqual([r["mode"] for r in rows if "sheen" not in r], ["baked", "hybrid"])
        modes = [r["mode"] for r in rows]  # the engineer's choice: the sheen lights and the probes together
        self.assertIn("sheen12_shadow_probes", modes)
        self.assertEqual(B.sheen_mode("sheen12_shadow_probes"), {"lm_specular": 0.0, "probes": True, "n": 12,
                                                                 "shadow": True})
        for r in rows:  # a lightmap lobe needs the directional bake
            if r.get("sheen", {}).get("lm_specular"):
                self.assertEqual(r["tag"], direc["tag"])

    def test_references_hybrid_then_the_bake(self):
        rows = [{**r, "zone": "ground"} for r in B.shot_rows("ground", B.sheen_variants(self.lights, "ground"))]
        refs = _house_bake.references("ground", rows, False, sheen=True)
        self.assertEqual(refs, ["ground_t8_d0_e15_ld_hybrid", "ground_t8_d0_e15_baked"])

    def test_glow_types(self):
        types = B.glow_types(self.lights)
        self.assertEqual(types, sorted(types))
        self.assertTrue(types)
        self.assertTrue(all(self.lights["types"][t]["glow"] for t in types))
        self.assertTrue(any(not v.get("glow") for v in self.lights["types"].values()))

    def test_probe_boxes_cover_their_rooms(self):
        data = house_layout.load()
        rooms = house_lights.zone_rooms(self.lights, data)["ground"]
        boxes = B.probe_boxes(data, rooms)
        self.assertEqual([b["room"] for b in boxes], rooms)
        found = {r["id"]: (r["rect"], lv["floor_y"]) for lv in data["levels"] for r in lv["rooms"]}
        for b in boxes:
            (x, z, w, d), y = found[b["room"]]
            self.assertEqual(b["size"], [w, 3.0, d])
            self.assertEqual(b["center"], [x + w / 2, y + 1.5, z + d / 2])
        with self.assertRaises(ValueError):
            B.probe_boxes(data, ["ballroom"])


class PresetSheen(unittest.TestCase):
    def setUp(self):
        self.lights = tomllib.loads(LIGHTS.read_text(encoding="utf-8"))
        self.data = house_layout.load()

    def test_the_presets_name_shadowed_sheen_modes(self):
        """High and Low take the grid's measured rows: specular-only lights, shadowed (no sheen through walls), as
        many as the preset's glow_count."""
        for name, p in self.lights["presets"].items():
            s = B.sheen_mode(p["sheen"])
            self.assertIsNotNone(s, name)
            self.assertTrue(s["shadow"], name)
            self.assertEqual(s["n"], p["glow_count"], name)
        self.assertEqual(house_lights.validate(self.lights, self.data), [])

    def test_a_bad_sheen_is_refused(self):
        self.lights["presets"]["low"]["sheen"] = "glitter"
        self.assertTrue(any("presets.low: sheen" in p for p in house_lights.validate(self.lights, self.data)))

    def test_a_sheen_count_off_glow_count_is_refused(self):
        self.lights["presets"]["high"]["sheen"] = "sheen8_shadow"
        self.assertTrue(any("presets.high: sheen 'sheen8_shadow' lights 8 lamps, glow_count is 12" in p
                            for p in house_lights.validate(self.lights, self.data)))


class SheenNumbers(unittest.TestCase):
    def test_costs_per_camera(self):
        shots = [{"row": "g_a", "cam": 1, "rt_lights": 4, "shadowed": 4, "draw_calls": 70.0},
                 {"row": "g_a", "cam": 0, "rt_lights": 3, "shadowed": 0, "draw_calls": 61.0},
                 {"row": "g_b", "cam": 0, "draw_calls": 30}]  # #83b's shots have no light counts
        self.assertEqual(B.shot_costs(shots), {"g_a": "3/0, 61; 4/4, 70", "g_b": "0/0, 30"})

    def test_numbers_with_a_cost_column(self):
        m = lambda lum: {"L_mean": lum, "dark_pct": 10.0, "C_p90": 20.0}
        md = B.numbers_md("g", {"g_h": [m(10.0)], "g_b": [m(8.0)]}, ["g_h", "g_b"], ["seam"],
                          extra={"g_b": "0/0, 30"})
        self.assertIn("| real-time / shadowed lights, draw calls (per camera) |", md)
        self.assertIn("|---|---|---|---|---|", md)
        self.assertIn("| g_b | 8.0 / 10.0 / 20.0 | -2.0 (-2.0) |  | 0/0, 30 |", md)
        self.assertIn("| g_h | 10.0 / 10.0 / 20.0 |  | +2.0 (+2.0) |  |", md)
        self.assertNotIn("draw calls", B.numbers_md("g", {"g_h": [m(10.0)]}, "g_h", ["seam"]))


if __name__ == "__main__":
    unittest.main()
