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
from um import glb, zones  # noqa: E402  (importable once recipe_module() put tools/blender on the path)

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

    def test_the_shared_skin_is_not_a_material_reference(self) -> None:
        # build_character swaps every part's Skin (and the head's as_skin) for <id>_skin before these are looked up
        data = mini()
        ch = data["characters"][0]
        ch["head"]["keep"] = ["Skin", "Hair"]
        ch["head"]["as_skin"] = ["Hair"]
        ch["brows"]["rgb"] = {"from_part": "head", "material": "Skin"}
        ch["recolor"] = [{"part": "top", "material": "Skin", "rgb": [0.5, 0.4, 0.3]},
                         {"part": "head", "material": "Hair", "rgb": [0.5, 0.4, 0.3]}]
        text = self.problems(data)
        for expected in ("brows.rgb.material: 'Skin' on the head part becomes the character's shared skin material "
                         "(m9_test_skin); set the skin colour with the character's 'skin' key",
                         "recolor[0].material: 'Skin' on the top part becomes",
                         "recolor[1].material: 'Hair' on the head part becomes"):
            self.assertIn(expected, text)

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

    def test_drop_pieces_names_a_piece_zone(self) -> None:
        """A part's drop_pieces (art #42 round 3: m2 drops the King's beard pieces) names zones.PIECE_ZONES only."""
        data = mini()
        data["characters"][0]["hair"]["drop_pieces"] = ["facial_hair"]
        recipe.load(self.write(data), self.raw)  # no RecipeError
        data["characters"][0]["hair"]["drop_pieces"] = ["chin_tuft"]
        self.assertIn("hair.drop_pieces: must be a list of piece zone names from facial_hair", self.problems(data))

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


class ExtrasCatalogueTest(unittest.TestCase):
    """recipe.check_extras: an extra is a whole catalogue item of the character's own body type (art #42)."""

    CAT = {"items": {
        "accessory_w_scifi_headset": {"kind": "accessory", "source": {"body_type": "W"},
                                      "recipe": {"file": "Sci Fi Character.glb", "object": "SciFi_Head", "materials": ["Blue"]}},
        "earrings_m_punk": {"kind": "earrings", "source": {"body_type": "M"},
                            "recipe": {"file": "Punk.glb", "object": "Punk_Head", "materials": ["Earrings"]}},
        "hair_m_punk": {"kind": "hair", "source": {"body_type": "M"},
                        "recipe": {"file": "Punk.glb", "object": "Punk_Head", "materials": ["Red"]}},
    }}

    def check(self, gender, extra):
        return recipe.check_extras({"characters": [{"id": "c1", "gender": gender, "extras": [extra]}]}, self.CAT)

    def test_whole_item_of_own_body_type_passes(self):
        self.assertEqual(self.check("M", {"role": "earrings", "file": "Punk.glb", "object": "Punk_Head",
                                          "materials": ["Earrings"]}), [])

    def test_other_gender_refused(self):
        problems = self.check("M", {"role": "accessory", "gender": "W", "file": "Sci Fi Character.glb",
                                    "object": "SciFi_Head", "materials": ["Blue"]})
        self.assertEqual(len(problems), 1)
        self.assertIn("not the character's 'M'", problems[0])

    def test_piece_that_is_no_item_refused(self):
        problems = self.check("M", {"role": "bits", "file": "Punk.glb", "object": "Punk_Head",
                                    "materials": ["Earrings", "Skin"]})
        self.assertEqual(len(problems), 1)
        self.assertIn("earrings_m_punk", problems[0])

    def test_hair_is_not_an_extra(self):
        self.assertEqual(len(self.check("M", {"role": "wig", "file": "Punk.glb", "object": "Punk_Head",
                                              "materials": ["Red"]})), 1)

    def test_repo_recipes_pass(self):
        cat = json.loads(recipe.CATALOGUE.read_text(encoding="utf-8"))
        for path in sorted((common.ROOT / "recipes").glob("*.json")):
            with self.subTest(recipe=path.name):
                self.assertEqual(recipe.check_extras(recipe.read(path), cat), [])


class HeadsCatalogueTest(unittest.TestCase):
    """recipe.check_heads: a head keeps its whole skull (art #42: m4's jaw)."""

    CAT = {"items": {"skull_m_casual": {"kind": "skull", "source": {"body_type": "M"}, "materials": ["Skin", "Skin_Darker"],
                                         "recipe": {"file": "Casual Character.glb", "object": "Casual2_Head"}}}}

    def check(self, head, gender="M"):
        return recipe.check_heads({"characters": [{"id": "c1", "gender": gender, "head": head}]}, self.CAT)

    def test_stubble_dropped_refused(self):
        problems = self.check({"file": "Casual Character.glb", "object": "Casual2_Head", "keep": ["Skin"]})
        self.assertEqual(len(problems), 1)
        self.assertIn("Skin_Darker", problems[0])

    def test_whole_skull_passes(self):
        self.assertEqual(self.check({"file": "Casual Character.glb", "object": "Casual2_Head", "keep": ["Skin"],
                                     "as_skin": ["Skin_Darker"]}), [])

    def test_unknown_head_not_compared(self):
        self.assertEqual(self.check({"file": "Other.glb", "object": "X_Head", "keep": ["Skin"]}), [])

    def test_repo_recipes_pass(self):
        cat = json.loads(recipe.CATALOGUE.read_text(encoding="utf-8"))
        for path in sorted((common.ROOT / "recipes").glob("*.json")):
            with self.subTest(recipe=path.name):
                self.assertEqual(recipe.check_heads(recipe.read(path), cat), [])


class PieceZones(unittest.TestCase):
    """art #42 round 3: zones.PIECE_ZONES on the pieces' measured centres (the probe in the zones' comments)."""

    @staticmethod
    def p(x, y, z):
        return type("P", (), {"x": x, "y": y, "z": z})()

    def test_the_kings_beard_goes_and_his_hair_stays(self) -> None:
        fh = zones.PIECE_ZONES["facial_hair"]
        self.assertTrue(fh(self.p(0.0, -0.12, 1.60)))  # beard
        self.assertTrue(fh(self.p(0.03, -0.13, 1.645)))  # moustache
        self.assertFalse(fh(self.p(0.0, -0.05, 1.80)))  # crown
        self.assertFalse(fh(self.p(0.09, -0.06, 1.64)))  # side lock by the ear

    def test_w4_keeps_the_crest_only(self) -> None:
        cap, strips = zones.PIECE_ZONES["punk_cap"], zones.PIECE_ZONES["punk_side_strips"]
        self.assertTrue(cap(self.p(0.0, -0.054, 1.742)))  # the skull cap's centre
        for x, z in ((0.0, 1.77), (0.02, 1.80), (-0.035, 1.86)):  # crest spikes: |x| < 0.036, z 1.77-1.86
            self.assertFalse(cap(self.p(x, -0.05, z)) or strips(self.p(x, -0.05, z)), (x, z))
        for x in (0.074, -0.095):  # the side strips by the ears
            self.assertTrue(strips(self.p(x, -0.09, 1.64)))
            self.assertFalse(cap(self.p(x, -0.09, 1.64)))
