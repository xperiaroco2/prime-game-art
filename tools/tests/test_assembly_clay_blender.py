"""The clay look in headless Blender (skipped when Blender or the Ultimate Modular packs are missing): round D's woman
w1 (recipes/clay_round_d.json) built in the clay look, and built again from the per-piece clay library, which then
bakes nothing (skipped unless the library in the raw folder already holds her pieces, so the test never writes there).
docs/assembly.md, "The clay look". Two Blender runs, about 30 s."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import unittest

from runner import cli, common, pins
from runner.commands import _assembly

_assembly.recipe_module()
from um import claylook as L  # noqa: E402  (importable once recipe_module() put tools/blender on the path)

OUT = common.OUT / "tests" / "assembly_clay"
RECIPE = common.ROOT / "recipes" / "clay_round_d.json"
RAW = common.raw_dir()
LIB = RAW / "clay-lib"
HAVE_BLENDER = bool((path := common.tool_path(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)) and path.is_file())
HAVE_PACKS = (RAW / "refs" / "Ultimate_Modular_Men_Pack").is_dir() and (RAW / "refs" / "Ultimate_Modular_Women_Pack").is_dir()
SKIP = f"needs Blender {pins.BLENDER} ({path}) and the Ultimate Modular packs in {RAW.as_posix()}/refs"
BAKED_ROLES = ("head", "hair", "top", "bottom", "shoes")  # w1's baked pieces (the kit face in the head); her eyes stay plain glossy


def run_cli(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(list(argv))
    return code, out.getvalue()


def w1_pieces() -> list:
    recipe = json.loads(RECIPE.read_text(encoding="utf-8"))
    w1 = next(c for c in recipe["characters"] if c["id"] == "w1")
    keys = L.keys_for(recipe, w1, L.settings(recipe))
    return [LIB / "W" / role / keys[role] / "piece.json" for role in BAKED_ROLES]


@unittest.skipUnless(HAVE_BLENDER and HAVE_PACKS, SKIP)
class ClayPassTest(unittest.TestCase):
    def test_the_clay_pass_meets_its_budgets(self) -> None:
        out = OUT / "pass"
        shutil.rmtree(out, ignore_errors=True)
        code, text = run_cli("assemble", str(RECIPE), "--ids", "w1", "--modes", "none", "--out", str(out))
        self.assertEqual(code, 0, text)
        rep = json.loads((out / "build_report.json").read_text(encoding="utf-8"))["characters"]["w1"]
        self.assertEqual(rep["look"], "clay")
        self.assertNotIn("clay_bake", rep)  # no --bake: the procedural clay only
        for role in ("top", "bottom", "shoes", "hair"):
            self.assertLessEqual(rep["triangles"][role], L.BUDGET[role] + 2, role)  # the decimator's +-1 per island
        self.assertGreater(rep["triangles_total"], 0)
        self.assertIn("triangles_total_pack", rep)
        # the face kit's face (um/clayface) instead of the scripted one: no collisions, no brow in an eye white, the
        # expressions on the face joined into the head, the ears as her hair item sets them
        kit = rep["face_kit"]
        self.assertEqual(kit["collisions"], {})
        self.assertEqual(kit["brow_in_white"], 0)
        self.assertFalse(kit["nose_meets_pupils"])
        self.assertIn("mouth_a", kit["keys"]["face"])
        self.assertIn("look_l", kit["keys"]["eyes"])
        self.assertEqual(kit["ears_state"], kit["flags"]["ears"])
        self.assertNotIn("brows", rep["triangles"])
        self.assertEqual(rep["clay"]["joined_into_head"], ["face"])


@unittest.skipUnless(HAVE_BLENDER and HAVE_PACKS, SKIP)
@unittest.skipUnless(LIB.is_dir() and all(p.is_file() for p in w1_pieces()),
                     f"needs w1's baked pieces in {LIB.as_posix()} (assemble clay_round_d --bake)")
class ClayLibraryTest(unittest.TestCase):
    def test_a_character_from_the_library_bakes_nothing(self) -> None:
        out = OUT / "library"
        shutil.rmtree(out, ignore_errors=True)
        code, text = run_cli("assemble", str(RECIPE), "--ids", "w1", "--modes", "none", "--bake", "--out", str(out))
        self.assertEqual(code, 0, text)
        bake = json.loads((out / "build_report.json").read_text(encoding="utf-8"))["characters"]["w1"]["clay_bake"]
        sources = {role: part["from"] for role, part in bake["parts"].items()}
        self.assertEqual({sources[r] for r in BAKED_ROLES}, {"library"}, sources)
        self.assertNotIn("baked", sources.values())
        self.assertLessEqual(bake["surfaces"], 8)  # the contract's surfaces_per_character_cap
