"""The `mannequin` command: our own low-poly base body, built by tools/blender/mannequin.py in headless Blender
(skipped with a message when Blender is missing)."""

from __future__ import annotations

import ast
import contextlib
import io
import json
import shutil
import unittest
from pathlib import Path

from runner import cli, common, pins
from runner.commands import mannequin

OUT = common.OUT / "tests" / "mannequin"
SCRIPT = common.ROOT / "tools" / "blender" / "mannequin.py"
HAVE_BLENDER = bool((path := common.tool_path(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)) and path.is_file())
SKIP = f"Blender {pins.BLENDER} not found at {path}; set {pins.BLENDER_ENV} or install it there"

# Shells of the body: head, nose, two ears, neck, torso, and per side an arm, a palm, five fingers, a leg, a foot and
# five toes.
BODY_SHELLS = 6 + 2 * (1 + 1 + 5 + 1 + 1 + 5)


def run_cli(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(list(argv))
    return code, out.getvalue()


def script_presets() -> list[str]:
    """The keys of PRESETS in tools/blender/mannequin.py, read without Blender."""
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "PRESETS":
            return [key.value for key in node.value.keys]
    raise AssertionError("no PRESETS in mannequin.py")


class WithoutBlenderTest(unittest.TestCase):
    def test_the_command_knows_the_scripts_presets(self) -> None:
        self.assertEqual(sorted(mannequin.PRESETS), sorted(script_presets()))

    def test_the_command_is_found(self) -> None:
        self.assertIn("mannequin", cli.discover())

    def test_refuses_tiny_images(self) -> None:
        code, output = run_cli("mannequin", "--out", str(OUT / "tiny"), "--size", "16")
        self.assertEqual(code, 1)
        self.assertIn("at least 64", output)

    def test_the_default_output_is_the_raw_folder(self) -> None:
        self.assertEqual(mannequin.default_out(), common.raw_dir() / "mannequin")


@unittest.skipUnless(HAVE_BLENDER, SKIP)
class BuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        shutil.rmtree(OUT, ignore_errors=True)
        cls.code, cls.output = run_cli("mannequin", "--preset", "lanky", "--out", str(OUT), "--size", "128",
                                       "--cell", "128")
        cls.folder = OUT / "lanky"
        info = cls.folder / "info.json"
        cls.info = json.loads(info.read_text(encoding="utf-8")) if info.is_file() else {}
        stats = cls.folder / "sheet" / "stats.json"
        cls.stats = json.loads(stats.read_text(encoding="utf-8")) if stats.is_file() else {}

    def test_exits_zero(self) -> None:
        self.assertEqual(self.code, 0, self.output)

    def test_writes_the_model_and_the_blend(self) -> None:
        self.assertTrue((self.folder / "mannequin_lanky.glb").is_file())
        self.assertTrue((self.folder / "mannequin_lanky.blend").is_file())
        self.assertEqual(Path(self.info["glb"]).name, "mannequin_lanky.glb")

    def test_is_175_cm_tall_with_the_feet_at_zero_and_the_eyes_near_160(self) -> None:
        self.assertEqual(self.info["height"], 1.75)
        self.assertEqual(self.info["lowest"], 0.0)
        self.assertAlmostEqual(self.info["eye_height"], 1.6, delta=0.04)

    def test_body_shirt_and_shorts_are_separate_with_five_fingers_and_five_toes(self) -> None:
        objects = self.info["objects"]
        self.assertEqual(sorted(objects), ["Body", "Shirt", "Shorts"])
        self.assertEqual(objects["Body"]["shells"], BODY_SHELLS)
        self.assertEqual(objects["Shirt"]["shells"], 3)  # the body and two sleeves
        self.assertEqual(objects["Shorts"]["shells"], 3)  # the hips and two legs

    def test_stays_low_poly(self) -> None:
        self.assertLess(self.info["triangles"], 6000)

    def test_references_are_square_on_white_and_filled(self) -> None:
        refs = self.info["refs"]
        self.assertEqual(sorted(refs["files"]), ["back", "front", "side"])
        for name, measured in refs["measured"].items():
            self.assertTrue(Path(refs["files"][name]).is_file())
            self.assertEqual(measured["corners"], [[255, 255, 255]] * 4, name)
        left, top, right, bottom = refs["measured"]["front"]["content_box"]
        self.assertGreater(max(right - left, bottom - top), 0.9 * 128)
        self.assertEqual(self.info["refs_flat"]["light"], "flat")

    def test_the_review_sheet_sees_the_same_model(self) -> None:
        self.assertAlmostEqual(self.stats["height"], 1.75, delta=0.005)
        self.assertTrue(self.stats["feet_at_zero"])
        self.assertEqual(self.stats["materials"], 3)
        self.assertEqual(self.stats["color_type"], "MATERIAL")
        self.assertEqual(self.stats["armatures"], 0)
