"""The committed parts catalogue (catalogue/ultimate_modular.json, docs/catalogue.md): its schema and the facts known
from the final character test (xperiaroco2/prime-game#165) and from the packs themselves. Pure Python, no Blender."""

from __future__ import annotations

import unittest

from runner.commands import _catalogue

DATA = _catalogue.load()
OK = ("ok", "ok_tucked", "ok_over")


def cells(name: str, g: str) -> list[dict]:
    return DATA["matrices"][name][g]["cells"]


class SchemaTest(unittest.TestCase):
    def test_valid(self) -> None:
        self.assertEqual(_catalogue.validate(DATA), [])

    def test_stable_order(self) -> None:
        for name, per in DATA["matrices"].items():
            for g, m in per.items():
                self.assertEqual(m["rows"], sorted(m["rows"]), f"{name}.{g} rows")
                self.assertEqual(m["cols"], sorted(m["cols"]), f"{name}.{g} cols")
                self.assertEqual([(c["a"], c["b"]) for c in m["cells"]], [(a, b) for a in m["rows"] for b in m["cols"]])

    def test_every_rule_is_a_plain_condition(self) -> None:
        for rule in DATA["rules"]:
            self.assertTrue(rule["condition"].strip())
            self.assertEqual(set(rule["verdicts"]), set(_catalogue.MATRICES[rule["id"]]))


class CharactersTest(unittest.TestCase):
    def test_counts(self) -> None:
        ch = DATA["characters"]
        self.assertEqual((ch["M"], ch["W"], ch["total"]), (11, 10, 21))
        self.assertEqual(len(DATA["parts"]), 63)  # 21 tops, 21 bottoms, 21 shoes
        self.assertEqual(len(DATA["heads"]), 21)

    def test_the_two_animated_woman_files_are_two_characters(self) -> None:
        aw = DATA["characters"]["animated_woman"]
        self.assertEqual(aw["verdict"], "different characters")
        self.assertEqual(aw["meshes_with_equal_positions"], 0)
        self.assertTrue(aw["animations_equal"])
        self.assertNotEqual(aw["sha256"][0], aw["sha256"][1])
        chars = {f["file"]: f["character"] for f in DATA["files"] if f["body_type"] == "W"}
        self.assertEqual(chars["Animated Woman.glb"], "casual")
        self.assertEqual(chars["Animated Woman-nIItLV9nxS.glb"], "formal")

    def test_one_animation_set_and_24_actions_per_body_type(self) -> None:
        self.assertEqual(DATA["characters"]["animation_sets_per_body_type"], {"M": 1, "W": 1})
        self.assertTrue(all(f["animations"] == 24 for f in DATA["files"]))


class HeadsTest(unittest.TestCase):
    def test_skull_types(self) -> None:
        types = {hid: h["skull_type"] for hid, h in DATA["heads"].items()}
        full = {"head_m_adventurer", "head_m_beach", "head_m_business", "head_m_casual", "head_m_hoodie", "head_m_king",
                "head_w_casual", "head_w_formal", "head_w_medieval", "head_w_scifi", "head_w_suit", "head_w_witch"}
        open_top = {"head_m_farmer", "head_m_punk", "head_m_worker", "head_w_adventurer", "head_w_punk",
                    "head_w_soldier", "head_w_worker"}
        self.assertEqual({h for h, t in types.items() if t == "full"}, full)
        self.assertEqual({h for h, t in types.items() if t == "open_top"}, open_top)
        self.assertEqual({h for h, t in types.items() if t == "none"}, {"head_m_astronaut", "head_m_swat"})

    def test_skull_tops(self) -> None:
        for hid, h in DATA["heads"].items():
            if h["skull_type"] == "full":
                self.assertAlmostEqual(h["skin_top_m"], 1.826 if "_m_" in hid else 1.789, delta=0.002, msg=hid)
            elif h["skull_type"] == "open_top":
                self.assertLess(h["skin_top_m"], 1.77, hid)

    def test_mixed_materials_are_split_by_geometry(self) -> None:
        items = DATA["items"]
        for iid in ("beard_m_adventurer", "moustache_m_adventurer", "beard_m_king", "moustache_m_king", "goatee_m_punk",
                    "moustache_m_worker", "stubble_m_casual", "brows_w_formal", "brows_w_medieval",
                    "hair_m_farmer_buzz", "hair_m_worker_buzz"):
            self.assertIn(iid, items)
        self.assertEqual(items["goatee_m_punk"]["materials"], ["Red"])  # Punk "Red" holds the mohawk and a goatee
        self.assertEqual(items["brows_w_formal"]["materials"], ["Brown"])  # women's "Brown" holds eyes and brows
        self.assertEqual(items["hair_m_worker_buzz"]["materials"], ["Eyebrows"])  # the scalp cap is in "Eyebrows"
        self.assertTrue(items["stubble_m_casual"]["painted"])
        self.assertEqual(items["hair_m_punk_mohawk"]["recipe"]["cut"], ["chin_tuft"])

    def test_hair_styles_follow_the_source_skull(self) -> None:
        for iid, e in DATA["items"].items():
            if e["kind"] == "hair":
                self.assertEqual(e["style"], {"open_top": "cap", "full": "shell"}[e["source_skull_type"]], iid)

    def test_every_item_recipe_is_exact_by_piece(self) -> None:
        for iid, e in DATA["items"].items():
            self.assertEqual(e["recipe_check"]["mismatch_by_piece"], 0, iid)


class RulesTest(unittest.TestCase):
    def test_bottom_and_shoe_gaps_of_the_final_test(self) -> None:
        self.assertEqual(DATA["summary"]["bottom_shoes"]["M"]["gap_over_5mm"], 12)
        self.assertEqual(DATA["summary"]["bottom_shoes"]["W"]["gap_over_5mm"], 24)
        women = {(c["a"], c["b"]) for c in cells("bottom_shoes", "W") if round(c["overlap_mm"]) < -5}
        knee = {"bottom_w_" + c for c in ("adventurer", "medieval", "punk", "scifi", "soldier", "witch")}
        low = {"shoes_w_" + c for c in ("casual", "formal", "suit", "worker")}
        self.assertEqual(women, {(b, s) for b in knee for s in low})
        for c in cells("bottom_shoes", "W"):
            if (c["a"], c["b"]) in women and c["overlap_mm"] < -30:
                self.assertEqual(c["verdict"], "gap")

    def test_the_worker_top_waist_gap(self) -> None:
        worker = {c["b"]: c for c in cells("top_bottom", "W") if c["a"] == "top_w_worker"}
        gaps = {b: c["overlap_mm"] for b, c in worker.items() if c["overlap_mm"] < 0}
        self.assertEqual(len(gaps), 6)
        self.assertEqual(round(min(gaps.values())), -21)
        self.assertEqual(min(gaps, key=gaps.get), "bottom_w_punk")
        self.assertEqual(worker["bottom_w_punk"]["verdict"], "gap")

    def test_pack_originals_are_ok(self) -> None:
        for name in ("bottom_shoes", "top_bottom"):
            for g in ("M", "W"):
                for c in cells(name, g):
                    if c["a"].split("_", 2)[2] == c["b"].split("_", 2)[2]:
                        self.assertIn(c["verdict"], OK, f"{name}: {c['a']} x {c['b']}")

    def test_cap_hair_only_on_its_skull_type(self) -> None:
        full = {c["b"]: c["verdict"] for c in cells("hair_skull", "M") if c["a"] == "hair_m_punk_mohawk"}
        self.assertEqual(full["skull_m_farmer"], "ok")  # the final test's m1_rex: Punk's cap on an open-top skull
        self.assertEqual(full["skull_m_business"], "poke")  # z-fights and cuts through on a full skull

    def test_needs_fix_names_a_measured_fix(self) -> None:
        for name, per in DATA["matrices"].items():
            for g, m in per.items():
                for c in m["cells"]:
                    if c["verdict"] == "needs_fix":
                        self.assertTrue(c["fix_tried"]["closes"], f"{name}: {c['a']} x {c['b']}")
                        self.assertEqual(c["fix"]["fix"], c["fix_tried"]["fix"])


if __name__ == "__main__":
    unittest.main()
