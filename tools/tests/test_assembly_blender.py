"""The assembler in headless Blender (skipped when Blender or the Ultimate Modular packs are missing): the final test's
four characters rebuilt at low resolution must match its numbers (tools/tests/fixtures/assembly/), and their saved
.blend files must follow the rules (docs/assembly.md). Between them they cover the rest-pose rebind (m2_walt's
Adventurer top moves 5.59 m), an extra part, colour references, the finger curl, the tucked bottom, edge extension,
flattened ears, the straightened neck ring and the poke-through probe. One Blender run, about 25 s."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import unittest

from runner import cli, common, pins
from runner.commands import _assembly, _review

OUT = common.OUT / "tests" / "assembly"
IDS = ("m1_rex", "m2_walt", "w1_ivy", "w2_nova")
REFERENCE = common.ROOT / "tools" / "tests" / "fixtures" / "assembly" / "final_test_reference.json"
RAW = common.raw_dir()
HAVE_BLENDER = bool((path := common.tool_path(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)) and path.is_file())
HAVE_PACKS = (RAW / "refs" / "Ultimate_Modular_Men_Pack").is_dir() and (RAW / "refs" / "Ultimate_Modular_Women_Pack").is_dir()
SKIP = f"needs Blender {pins.BLENDER} ({path}) and the Ultimate Modular packs in {RAW.as_posix()}/refs"


def run_cli(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(list(argv))
    return code, out.getvalue()


@unittest.skipUnless(HAVE_BLENDER and HAVE_PACKS, SKIP)
class AssembleInBlenderTest(unittest.TestCase):
    code: int
    out: str

    @classmethod
    def setUpClass(cls) -> None:
        shutil.rmtree(OUT, ignore_errors=True)
        cls.code, cls.out = run_cli("assemble", "um_final_test", "--ids", ",".join(IDS), "--modes", "chars",
                                    "--res", "10", "--blend", "--out", str(OUT), "--compare", str(REFERENCE))

    def sidecar(self, cid: str) -> dict:
        return json.loads((OUT / "blend" / f"{cid}.json").read_text(encoding="utf-8"))

    def test_the_build_matches_the_final_test(self) -> None:
        self.assertEqual(self.code, 0, self.out)
        self.assertIn("ok    matches", self.out)
        report = json.loads((OUT / "build_report.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(report["characters"]), list(IDS))
        self.assertEqual(report["characters"]["m2_walt"]["parts"]["top"]["rebind_max_move_m"], 5.586)

    def test_renders_at_the_requested_size(self) -> None:
        width, height = _review.png_size(OUT / "characters" / "w1_ivy_front.png")
        self.assertEqual(height, 120)  # 10 % of 1200 px
        self.assertGreater(width, 40)

    def test_each_saved_file_follows_the_rules(self) -> None:
        recipes = _assembly.recipe_module()
        from um import glb

        for cid in IDS:
            with self.subTest(character=cid):
                side = self.sidecar(cid)
                seen = side["inspected"]
                self.assertEqual(seen["problems"], [])
                slots = {"head", "hair", "top", "bottom", "shoes", "eyes", "brows", "mouth"}
                if cid == "m2_walt":
                    slots.add("moustache")
                self.assertEqual(set(seen["objects"]), {f"{cid}_rig"} | {f"{cid}_{s}" for s in slots})
                self.assertEqual(set(side["parts"]), slots)
                self.assertEqual(side["armature"]["bones"], 62)
                gender = side["body_type"]
                recipe = recipes.load(_assembly.RECIPES / "um_final_test.json", None)
                skeleton = recipes.pack_dir(recipe, RAW, gender) / recipe["skeleton"][gender]
                pack_actions = {glb.ACTION_PREFIX + a for a in glb.contents(skeleton)["actions"]}
                self.assertEqual(set(side["actions"]), pack_actions)
                self.assertEqual(set(seen["actions"]), pack_actions)
                self.assertTrue(all(a["fake_user"] for a in seen["actions"].values()))
                self.assertLess(side["transform_check_max_error_m"], 1e-4)
                self.assertLess(abs(seen["feet_z_m"]), 0.005)
                self.assertEqual(seen["height_m"], side["height_m"])
                self.assertEqual((seen["cameras"], seen["lights"], seen["worlds"]), (0, 0, 0))
                self.assertTrue(all(o["identity"] for o in seen["objects"].values()))


@unittest.skipUnless(HAVE_BLENDER and HAVE_PACKS, SKIP)
class StyleRefusalTest(unittest.TestCase):
    def test_an_unknown_face_style_is_refused_before_building(self) -> None:
        data = json.loads((_assembly.RECIPES / "um_final_test.json").read_text(encoding="utf-8"))
        data["characters"] = data["characters"][:1]
        data["characters"][0]["eyes"]["style"] = "laser"
        del data["hands"], data["crossgender"]
        path = OUT.parent / "assembly_bad_style.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
        code, out = run_cli("assemble", str(path), "--modes", "none", "--out", str(OUT.parent / "assembly_bad_style"))
        self.assertEqual(code, 1)
        self.assertIn("'laser' is not a face-kit style; it has: googly, dots, sleepy, cartoon", out)


if __name__ == "__main__":
    unittest.main()
