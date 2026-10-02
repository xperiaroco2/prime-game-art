"""The probe, the fixture and the review sheets, through headless Blender (skipped when Blender is missing)."""

from __future__ import annotations

import json
import shutil
import unittest
import zlib
from pathlib import Path

from runner import cli, common, pins
from runner.commands import _review

OUT = common.OUT / "tests" / "blender"
HAVE_BLENDER = bool((path := common.tool_path(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)) and path.is_file())
SKIP = f"Blender {pins.BLENDER} not found at {path}; set {pins.BLENDER_ENV} or install it there"


def tiny_png(width: int, height: int) -> bytes:
    def chunk(kind: bytes, body: bytes) -> bytes:
        return len(body).to_bytes(4, "big") + kind + body + zlib.crc32(kind + body).to_bytes(4, "big")

    header = width.to_bytes(4, "big") + height.to_bytes(4, "big") + bytes((8, 2, 0, 0, 0))
    raw = b"".join(b"\x00" + b"\x80" * 3 * width for _ in range(height))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


class WithoutBlenderTest(unittest.TestCase):
    """Argument and file handling that needs no Blender."""

    def setUp(self) -> None:
        OUT.mkdir(parents=True, exist_ok=True)

    def test_png_size_reads_the_header(self) -> None:
        path = OUT / "tiny.png"
        path.write_bytes(tiny_png(7, 3))
        self.assertEqual(_review.png_size(path), (7, 3))

    def test_png_size_refuses_other_files(self) -> None:
        path = OUT / "not.png"
        path.write_bytes(b"GIF89a" + bytes(30))
        with self.assertRaises(common.Failure):
            _review.png_size(path)

    def test_render_refuses_a_missing_model(self) -> None:
        self.assertEqual(cli.main(["render", str(OUT / "missing.glb")]), 1)

    def test_render_refuses_an_unknown_format(self) -> None:
        path = OUT / "model.stl"
        path.write_bytes(b"solid x\nendsolid x\n")
        self.assertEqual(cli.main(["render", str(path)]), 1)

    def test_commands_are_found(self) -> None:
        self.assertIn("probe", cli.discover())
        self.assertIn("render", cli.discover())


@unittest.skipUnless(HAVE_BLENDER, SKIP)
class ProbeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.out = OUT / "probe"
        shutil.rmtree(cls.out, ignore_errors=True)
        cls.code = cli.main(["probe", "--out", str(cls.out), "--no-fixtures"])
        report = cls.out / "report.json"
        cls.report = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}

    def test_exits_zero(self) -> None:
        self.assertEqual(self.code, 0)

    def test_reports_the_pinned_blender(self) -> None:
        self.assertTrue(self.report["blender"]["version_string"].startswith(pins.BLENDER))

    def test_has_the_exporter_properties_with_defaults(self) -> None:
        export = self.report["gltf_export"]
        self.assertGreater(len(export), 50)
        self.assertEqual(export["export_format"]["default"], "GLB")
        self.assertIn("GLTF_SEPARATE", export["export_format"]["items"])
        self.assertIs(export["export_yup"]["default"], True)
        self.assertIn("default", export["export_animation_mode"])

    def test_has_the_importer_properties(self) -> None:
        self.assertIn("bone_heuristic", self.report["gltf_import"])

    def test_engines_and_numpy(self) -> None:
        self.assertIn("BLENDER_WORKBENCH", self.report["render_engines"]["settable"])
        self.assertTrue(self.report["numpy"]["imports"])

    def test_renders_workbench_and_records_eevee(self) -> None:
        renders = self.report["renders"]
        self.assertTrue(renders["workbench"]["ok"])
        self.assertTrue((self.out / "workbench.png").is_file())
        self.assertIn("ok", renders["eevee"])
        if not renders["eevee"]["ok"]:
            self.assertTrue(renders["eevee"]["error"])


@unittest.skipUnless(HAVE_BLENDER, SKIP)
class ReviewSheetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        shutil.rmtree(OUT / "fixtures", ignore_errors=True)
        shutil.rmtree(OUT / "renders", ignore_errors=True)
        cls.fixtures = {path.stem: path for path in _review.make_fixtures(OUT / "fixtures")}
        cls.plain_out = OUT / "renders" / "humanoid"
        cls.stats = _review.render(cls.fixtures["humanoid"], cls.plain_out)

    def test_fixture_is_a_glb(self) -> None:
        self.assertEqual(self.fixtures["humanoid"].read_bytes()[:4], b"glTF")

    def test_sheet_is_4_by_2_cells_of_512(self) -> None:
        self.assertEqual(_review.png_size(self.plain_out / "sheet.png"), (2048, 1024))

    def test_writes_the_eight_views_front_first(self) -> None:
        views = sorted((self.plain_out / "views").glob("*.png"))
        self.assertEqual(len(views), 8)
        self.assertEqual(views[0].name, "0_000_front.png")
        self.assertEqual(self.stats["views"][0], "0 FRONT")

    def test_stats_fields(self) -> None:
        for field in ("triangles", "vertices", "objects", "materials", "bones", "bounding_box", "height",
                      "feet_at_zero", "color_type"):
            self.assertIn(field, self.stats)
        self.assertEqual(set(self.stats["bounding_box"]), {"min", "max", "size"})
        self.assertGreater(self.stats["triangles"], 0)
        self.assertEqual(self.stats["bones"], 17)
        self.assertEqual(self.stats["materials"], 5)

    def test_stands_1_75_m_on_the_ground(self) -> None:
        self.assertAlmostEqual(self.stats["height"], 1.75, delta=0.01)
        self.assertTrue(self.stats["feet_at_zero"])

    def test_untextured_uses_material_colours(self) -> None:
        self.assertEqual(self.stats["color_type"], "MATERIAL")

    def test_textured_uses_texture_colours_and_a_smaller_cell(self) -> None:
        out = OUT / "renders" / "humanoid_textured"
        stats = _review.render(self.fixtures["humanoid_textured"], out, cell=128)
        self.assertEqual(stats["color_type"], "TEXTURE")
        self.assertEqual(_review.png_size(out / "sheet.png"), (512, 256))

    def test_animation_contact_sheet(self) -> None:
        out = OUT / "renders" / "humanoid_anim"
        stats = _review.render(self.fixtures["humanoid"], out, cell=128, anim="Wave", frames=4)
        self.assertEqual(len(stats["anim"]["frames"]), 4)
        self.assertEqual(_review.png_size(Path(stats["anim"]["sheet"])), (512, 128))

    def test_an_unknown_action_fails_with_the_known_ones(self) -> None:
        with self.assertRaises(common.Failure) as caught:
            _review.render(self.fixtures["humanoid"], OUT / "renders" / "nope", cell=64, anim="Nope")
        self.assertIn("Wave", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
