"""The catalogue regenerated in headless Blender (skipped when Blender or the Ultimate Modular packs are missing): the run
must reproduce the committed catalogue/ultimate_modular.json exactly (the determinism and drift check of
docs/catalogue.md). One Blender run of about two minutes."""

from __future__ import annotations

import contextlib
import io
import unittest

from runner import cli, common, pins

RAW = common.raw_dir()
HAVE_BLENDER = bool((path := common.tool_path(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)) and path.is_file())
HAVE_PACKS = (RAW / "refs" / "Ultimate_Modular_Men_Pack").is_dir() and (RAW / "refs" / "Ultimate_Modular_Women_Pack").is_dir()
SKIP = f"needs Blender {pins.BLENDER} ({path}) and the Ultimate Modular packs in {RAW.as_posix()}/refs"


@unittest.skipUnless(HAVE_BLENDER and HAVE_PACKS, SKIP)
class CatalogueInBlenderTest(unittest.TestCase):
    def test_the_regenerated_catalogue_equals_the_committed_file(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["catalogue", "--check", "--out", str(common.OUT / "tests" / "catalogue")])
        self.assertEqual(code, 0, out.getvalue()[-3000:])
        self.assertIn("the regenerated catalogue equals the committed file", out.getvalue())


if __name__ == "__main__":
    unittest.main()
