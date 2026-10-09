"""The clay look's pure-Python rules (tools/blender/um/claylook.py): the recipe's `look` and `clay` keys, the texture
sizes and margins of the bake, and the clay library's piece keys (docs/assembly.md, "The clay look")."""

from __future__ import annotations

import copy
import unittest

from runner.commands import _assembly

recipe = _assembly.recipe_module()
from um import claylook as L  # noqa: E402  (importable once recipe_module() put tools/blender on the path)

CHAR = {
    "id": "m1", "gender": "M", "skin": [0.6, 0.39, 0.27],
    "head": {"file": "Beach Character.glb", "object": "Beach_Head", "keep": ["Skin"]},
    "hair": {"file": "Beach Character.glb", "object": "Beach_Head", "materials": ["Hair"]},
    "extras": [{"role": "accessory", "gender": "W", "file": "Sci Fi Character.glb", "object": "SciFi_Head",
                "materials": ["Blue"]}],
    "top": {"file": "Adventurer.glb", "object": "Adventurer_Body"},
    "bottom": {"file": "Adventurer.glb", "object": "Adventurer_Legs"},
    "shoes": {"file": "Worker.glb", "object": "Worker_Feet"},
    "eyes": {"style": "dots"}, "brows": {"style": "raised_thick"}, "mouth": {"style": "smile"},
    "pose": {"action": "Idle", "frame": 0},
}
RECIPE = {"face": {"M": {"mouth_dz": -0.088}}, "face_shading": "smooth", "look": "clay", "characters": [CHAR]}


class LookAndSettings(unittest.TestCase):
    def test_look_defaults_to_pack(self) -> None:
        self.assertEqual(L.look_of({}), "pack")
        self.assertEqual(L.look_of({"look": "clay"}), "clay")
        self.assertEqual(L.look_of({"look": "clay"}, "pack"), "pack")

    def test_settings_override_one_kind(self) -> None:
        cfg = L.settings({"clay": {"budget": {"top": 2000}, "head_scale": 1.2}})
        self.assertEqual(cfg["budget"]["top"], 2000)
        self.assertEqual(cfg["budget"]["shoes"], L.BUDGET["shoes"])
        self.assertEqual(cfg["head_scale"], 1.2)

    def test_check_accepts_a_good_recipe(self) -> None:
        self.assertEqual(L.check(RECIPE), [])
        self.assertEqual(L.check({"clay": {"lump": {"hair": 0.001}, "density": {"head": 2048}}}), [])

    def test_check_names_each_problem(self) -> None:
        bad = L.check({"look": "wax", "clay": {"head_scale": 5, "budget": {"top": -1}, "boil": 1, "lump": []}})
        joined = "\n".join(bad)
        for where in ("look:", "clay.head_scale", "clay.budget.top", "clay.boil", "clay.lump"):
            self.assertIn(where, joined)

    def test_recipe_structure_runs_the_clay_check(self) -> None:
        problems = recipe.check_structure({"look": "wax"})
        self.assertTrue(any(p.startswith("look:") for p in problems), problems)


class BakeSizes(unittest.TestCase):
    def test_pick_size_reaches_the_density(self) -> None:
        # 0.25 m2 at 60 % UV use: 512 px/m wants 512 / sqrt(0.6 / 0.25) = 330 px -> 512 (90 % rule)
        self.assertEqual(L.pick_size(0.25, 0.6, 512), 512)
        self.assertEqual(L.pick_size(0.0001, 0.6, 512), L.MIN_SIZE)
        self.assertEqual(L.pick_size(10.0, 0.1, 1024), L.MAX_SIZE)

    def test_colour_map_and_margin(self) -> None:
        self.assertEqual(L.colour_size(1024), 512)
        self.assertEqual(L.colour_size(64), 64)
        self.assertAlmostEqual(L.margin_needed(512), 3 / 512)
        self.assertAlmostEqual(L.texel_density(1024, 0.25, 1.0), 512.0)

    def test_srgb_round_trip(self) -> None:
        for c in (0.0, 0.02, 0.5, 1.0):
            self.assertAlmostEqual(L.linear_to_srgb(L.srgb_to_linear(c)), c, places=6)


class PieceKeys(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = L.settings(RECIPE)

    def test_every_part_has_a_key(self) -> None:
        keys = L.keys_for(RECIPE, CHAR, self.cfg)
        self.assertEqual(sorted(keys), sorted(["head", "hair", "accessory", "top", "bottom", "shoes", "eyes", "brows",
                                               "mouth"]))
        self.assertTrue(all(len(k) == 16 for k in keys.values()))

    def test_same_piece_same_key_across_characters(self) -> None:
        other = copy.deepcopy(CHAR)
        other.update(id="m9", hair={"file": "Punk.glb", "object": "Punk_Head", "materials": ["Hair"]})
        a, b = L.keys_for(RECIPE, CHAR, self.cfg), L.keys_for(RECIPE, other, self.cfg)
        for role in ("top", "bottom", "shoes", "accessory"):
            self.assertEqual(a[role], b[role], role)
        self.assertNotEqual(a["hair"], b["hair"])
        self.assertNotEqual(a["head"], b["head"])  # the head's key holds the hair it is built under

    def test_skin_and_settings_change_the_key(self) -> None:
        darker = copy.deepcopy(CHAR)
        darker["skin"] = [0.13, 0.07, 0.04]
        a, b = L.keys_for(RECIPE, CHAR, self.cfg), L.keys_for(RECIPE, darker, self.cfg)
        self.assertNotEqual(a["top"], b["top"])  # the top's bare arms bake in the skin tone
        self.assertEqual(a["hair"], b["hair"])
        cfg2 = L.settings({"clay": {"budget": {"top": 2000}}})
        self.assertNotEqual(a["top"], L.keys_for(RECIPE, CHAR, cfg2)["top"])
        self.assertEqual(a["shoes"], L.keys_for(RECIPE, CHAR, cfg2)["shoes"])


if __name__ == "__main__":
    unittest.main()
