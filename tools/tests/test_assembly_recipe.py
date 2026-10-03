"""Recipes (tools/blender/um/recipe.py, pure Python): structure, "extends", and the checks against the packs, with a
fake raw folder of tiny GLBs; the repo's recipes against the real packs when they are on this PC."""

from __future__ import annotations

import copy
import json
import struct
import tempfile
import unittest
from pathlib import Path

from runner import common
from runner.commands import _assembly

recipe = _assembly.recipe_module()
from um import glb  # noqa: E402  (importable once recipe_module() put tools/blender on the path)

RAW = common.raw_dir()
HAVE_PACKS = (RAW / "refs" / "Ultimate_Modular_Men_Pack").is_dir() and (RAW / "refs" / "Ultimate_Modular_Women_Pack").is_dir()

MEN = {
    "Base.glb": ({"Base_Head": ["Skin", "Eye", "Hair"], "Base_Body": ["Suit", "Skin"], "Base_Legs": ["Suit"],
                  "Base_Feet": ["Black"]}, ["Idle", "Wave", "Walk"]),
    "Punk.glb": ({"Punk_Head": ["Skin", "Red", "Eye"], "Punk_Feet": ["Black"]}, ["Idle", "Wave", "Walk"]),
}
WOMEN = {"Suit.glb": ({"Suit_Head": ["Skin", "Brown"], "Suit_Feet": ["Black"]}, ["Idle", "Walk"])}


def write_glb(path: Path, objects: dict[str, list[str]], actions: list[str]) -> None:
    """A GLB with only a JSON chunk: what um/glb.py reads (plus the stray Icosphere every pack file has)."""
    materials = sorted({m for ms in objects.values() for m in ms})
    names = list(objects)
    gltf = {
        "asset": {"version": "2.0"},
        "materials": [{"name": m} for m in materials],
        "meshes": [{"name": n, "primitives": [{"attributes": {}, "material": materials.index(m)} for m in objects[n]]}
                   for n in names],
        "nodes": [{"name": n, "mesh": i} for i, n in enumerate(names)] + [{"name": "Icosphere", "mesh": 0}],
        "animations": [{"name": "CharacterArmature|" + a, "channels": [], "samplers": []} for a in actions],
    }
    body = json.dumps(gltf).encode()
    body += b" " * (-len(body) % 4)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"glTF" + struct.pack("<II", 2, 20 + len(body)) + struct.pack("<II", len(body), glb.JSON_CHUNK) + body)


def mini() -> dict:
    return {
        "packs": {"M": "packs/men", "W": "packs/women"},
        "skeleton": {"M": "Base.glb", "W": "Suit.glb"},
        "head_bone_rest": [-0.0003, -0.0431, 1.5873],
        "face_shading": "flat",
        "face": {"M": {"mouth_dz": -0.088}, "W": {"mouth_dz": -0.072}},
        "characters": [{
            "id": "m9_test", "gender": "M",
            "head": {"file": "Base.glb", "object": "Base_Head", "keep": ["Skin"], "eye_materials": ["Eye"], "tuck_ears": 0.08},
            "hair": {"file": "Punk.glb", "object": "Punk_Head", "materials": ["Red"], "cut": ["chin_tuft"], "inflate": 0.006},
            "top": {"file": "Base.glb", "object": "Base_Body"},
            "bottom": {"file": "Base.glb", "object": "Base_Legs"},
            "shoes": {"file": "Punk.glb", "object": "Punk_Feet"},
            "eyes": {"style": "dots"},
            "brows": {"style": "thin_arch", "rgb": {"from_part": "hair", "material": "Red"}},
            "mouth": {"style": "o"},
            "recolor": [{"part": "shoes", "material": "Black", "rgb": [0.1, 0.1, 0.1]}],
            "pose": {"action": "Wave", "frame": 20, "curl": {"Middle.R": [10, 20, 30]}},
        }],
        "hands": [{"id": "m9_test", "shots": [["L", "front"], ["R", "in34", 62]]}],
    }


class FakeRaw(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.raw = Path(self.tmp.name)
        for folder, files in (("packs/men", MEN), ("packs/women", WOMEN)):
            for name, (objects, actions) in files.items():
                write_glb(self.raw / folder / name, objects, actions)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, data: dict, name: str = "r.json") -> Path:
        path = self.raw / "recipes" / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def problems(self, data: dict) -> str:
        with self.assertRaises(recipe.RecipeError) as caught:
            recipe.load(self.write(data), self.raw)
        return str(caught.exception)


class GlbTest(FakeRaw):
    def test_contents_lists_objects_materials_and_actions(self) -> None:
        toc = glb.contents(self.raw / "packs/men/Punk.glb")
        self.assertEqual(toc["objects"], {"Punk_Head": ["Skin", "Red", "Eye"], "Punk_Feet": ["Black"]})
        self.assertEqual(toc["actions"], ["Idle", "Wave", "Walk"])  # the "CharacterArmature|" prefix is dropped

    def test_a_file_that_is_not_a_glb_is_refused(self) -> None:
        path = self.raw / "x.glb"
        path.write_bytes(b"not a glb at all, really")
        with self.assertRaises(glb.GlbError):
            glb.contents(path)


class ContentTest(FakeRaw):
    def test_the_mini_recipe_passes(self) -> None:
        data = recipe.load(self.write(mini()), self.raw)
        self.assertEqual(data["_name"], "r")
        self.assertEqual(recipe.modes(data), list(recipe.DEFAULT_MODES))

    def test_an_unknown_file_names_the_pack_files(self) -> None:
        data = mini()
        data["characters"][0]["hair"]["file"] = "Punkk.glb"
        self.assertIn("hair.file: 'Punkk.glb' is not in Men (packs/men); it has: Base.glb, Punk.glb", self.problems(data))

    def test_an_unknown_object_names_the_objects(self) -> None:
        data = mini()
        data["characters"][0]["top"]["object"] = "Base_Bodyy"
        self.assertIn("top.object: 'Base_Bodyy' is not an object in Men/Base.glb; it has: Base_Body, Base_Feet, "
                      "Base_Head, Base_Legs", self.problems(data))

    def test_an_unknown_material_names_the_materials(self) -> None:
        data = mini()
        data["characters"][0]["hair"]["materials"] = ["Blue"]
        self.assertIn("hair.materials: 'Blue' not on Punk_Head (Men/Punk.glb); it has: Skin, Red, Eye", self.problems(data))

    def test_a_recolour_needs_the_material_on_that_part(self) -> None:
        data = mini()
        data["characters"][0]["recolor"][0]["material"] = "Suit"
        self.assertIn("recolor[0].material: 'Suit' not on the shoes part; it has: Black", self.problems(data))

    def test_an_unknown_action_names_the_actions(self) -> None:
        data = mini()
        data["characters"][0]["pose"]["action"] = "Wav"
        self.assertIn("pose.action: 'Wav' is not an action of Men/Base.glb; it has: Idle, Wave, Walk", self.problems(data))

    def test_a_missing_pack_folder_is_named(self) -> None:
        data = mini()
        data["packs"]["W"] = "packs/nowhere"
        self.assertIn("packs.W: no folder", self.problems(data))

    def test_structure_only_without_a_raw_folder(self) -> None:
        data = mini()
        data["characters"][0]["hair"]["file"] = "Elsewhere.glb"
        self.assertEqual(recipe.load(self.write(data), None)["characters"][0]["hair"]["file"], "Elsewhere.glb")


class StructureTest(FakeRaw):
    def test_every_problem_is_reported_at_once(self) -> None:
        data = mini()
        ch = data["characters"][0]
        ch["colour"] = "red"
        del ch["mouth"]
        ch["pose"] = {"action": "Wave", "frame": -1, "curl": {"Toe.R": [10]}}
        ch["hair"]["cut"] = ["nose"]
        ch["brows"]["rgb"] = {"from_part": "hat", "material": "Red"}
        ch["extras"] = [{"role": "top", "file": "Punk.glb", "object": "Punk_Head", "materials": ["Red"]}]
        ch["skin"] = [1.5, 0, 0]
        data["hands"][0]["shots"].append(["L", "upside"])
        text = self.problems(data)
        for expected in (
            "unknown key 'colour'",
            "missing key 'mouth'",
            "pose.frame: must be a whole frame number from 0",
            "'Toe.R' must be <finger>.<L|R>",
            "hair.cut: must be a list of zone names from chin_tuft, ears, over_ears",
            "brows.rgb: from_part 'hat' is not a pack part",
            "extras[0].role: 'top' must be a new lowercase name",
            "skin: must be [r, g, b]",
            "hands[0].shots[2]",
        ):
            self.assertIn(expected, text)
        self.assertGreaterEqual(len(text.splitlines()), 10)

    def test_ids_are_unique_and_hands_name_a_character(self) -> None:
        data = mini()
        data["characters"].append(copy.deepcopy(data["characters"][0]))
        data["hands"][0]["id"] = "nobody"
        text = self.problems(data)
        self.assertIn("characters[m9_test].id: is used twice", text)
        self.assertIn("hands[0].id: 'nobody' is not a character", text)

    def test_the_neutral_pose_and_too_many_curl_angles(self) -> None:
        data = mini()
        data["characters"][0]["pose"] = {"neutral": {"down_deg": 70}, "curl": {"Thumb.L": [1, 2, 3, 4]}}
        self.assertIn("curl.Thumb.L: must be 1 to 3 angles", self.problems(data))
        data["characters"][0]["pose"] = {"neutral": {}}
        recipe.load(self.write(data), self.raw)

    def test_a_variant_changes_every_character(self) -> None:
        self.write(mini(), "base.json")
        variant = self.write({"extends": "base.json", "modes": ["chars", "lineup"],
                              "every_character": {"pose": {"neutral": {"down_deg": 60}}}}, "variant.json")
        data = recipe.load(variant, self.raw)
        self.assertEqual(data["characters"][0]["pose"], {"neutral": {"down_deg": 60}})
        self.assertEqual(recipe.modes(data), ["chars", "lineup"])
        self.assertEqual(data["characters"][0]["hair"]["file"], "Punk.glb")

    def test_extends_loops_and_stray_every_character_are_refused(self) -> None:
        self.write({"extends": "b.json"}, "a.json")
        self.write({"extends": "a.json"}, "b.json")
        with self.assertRaises(recipe.RecipeError) as caught:
            recipe.load(self.raw / "recipes" / "a.json", self.raw)
        self.assertIn("extends loops back", str(caught.exception))
        data = mini()
        data["every_character"] = {"pose": {"neutral": {}}}
        self.assertIn("every_character needs extends", self.problems(data))

    def test_not_json(self) -> None:
        path = self.raw / "broken.json"
        path.write_text("{", encoding="utf-8")
        with self.assertRaises(recipe.RecipeError) as caught:
            recipe.load(path, self.raw)
        self.assertIn("not valid JSON", str(caught.exception))


class RepoRecipesTest(unittest.TestCase):
    def test_the_repo_recipes_are_well_formed(self) -> None:
        for path in sorted(_assembly.RECIPES.glob("*.json")):
            with self.subTest(recipe=path.name):
                data = recipe.load(path, None)
                self.assertTrue(data["characters"])

    def test_the_final_test_recipes(self) -> None:
        base = recipe.load(_assembly.RECIPES / "um_final_test.json", None)
        self.assertEqual([c["id"] for c in base["characters"]], ["m1_rex", "m2_walt", "w1_ivy", "w2_nova"])
        self.assertEqual(base["characters"][1]["pose"]["curl"]["Middle.R"], [60, 70, 40])
        neutral = recipe.load(_assembly.RECIPES / "um_final_test_neutral.json", None)
        self.assertEqual({json.dumps(c["pose"]) for c in neutral["characters"]}, {'{"neutral": {"down_deg": 70.0}}'})
        self.assertEqual(recipe.modes(neutral), ["chars", "lineup"])

    @unittest.skipUnless(HAVE_PACKS, f"the Ultimate Modular packs are not in {RAW.as_posix()}/refs")
    def test_the_repo_recipes_match_the_packs(self) -> None:
        for path in sorted(_assembly.RECIPES.glob("*.json")):
            with self.subTest(recipe=path.name):
                recipe.load(path, RAW)


if __name__ == "__main__":
    unittest.main()
