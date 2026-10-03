"""The catalogue command without Blender: refusals before Blender starts, the schema check and the comparison of two
runs (docs/catalogue.md)."""

from __future__ import annotations

import contextlib
import copy
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runner import cli
from runner.commands import _catalogue


def run_cli(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(list(argv))
    return code, out.getvalue()


class RefusalsTest(unittest.TestCase):
    """Each refusal happens before Blender starts."""

    def run_quiet(self, *argv: str, raw: Path | None = None) -> tuple[int, str]:
        env = {"ART_RAW_DIR": str(raw)} if raw else {}
        with mock.patch.dict(os.environ, env), \
                mock.patch("runner.blender.run_script", side_effect=AssertionError("Blender must not start")):
            return run_cli("catalogue", *argv)

    def test_unknown_renders(self) -> None:
        code, out = self.run_quiet("--renders", "sheets,video")
        self.assertEqual(code, 1)
        self.assertIn("unknown renders video", out)

    def test_res_bounds(self) -> None:
        code, out = self.run_quiet("--res", "200")
        self.assertEqual(code, 1)
        self.assertIn("--res must be from 5 to 100", out)

    def test_missing_packs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self.run_quiet(raw=Path(tmp))
        self.assertEqual(code, 1)
        self.assertIn("no Ultimate_Modular_Men_Pack", out)


class ValidateTest(unittest.TestCase):
    data = _catalogue.load()

    def test_a_broken_catalogue_is_reported(self) -> None:
        bad = copy.deepcopy(self.data)
        bad["matrices"]["top_bottom"]["W"]["cells"][0]["verdict"] = "fine"
        bad["matrices"]["head_top"]["M"]["cells"].pop()
        first = sorted(bad["items"])[0]
        bad["items"][first]["kind"] = "hat"
        problems = "\n".join(_catalogue.validate(bad))
        self.assertIn("verdict 'fine'", problems)
        self.assertIn("cells for", problems)
        self.assertIn(f"items[{first}]: kind 'hat'", problems)

    def test_missing_keys(self) -> None:
        self.assertEqual(_catalogue.validate({"schema": _catalogue.SCHEMA}),
                         ["missing top-level keys: generated_by, sources, conventions, thresholds, characters, files, "
                          "parts, heads, items, proposed_zones, rules, matrices, summary"])

    def test_diff_names_the_paths(self) -> None:
        other = copy.deepcopy(self.data)
        other["matrices"]["bottom_shoes"]["M"]["cells"][3]["overlap_mm"] += 1.0
        self.assertEqual(_catalogue.diff(self.data, self.data), [])
        lines = _catalogue.diff(self.data, other)
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("/matrices/bottom_shoes/M/cells[3]/overlap_mm:"))

    def test_summary_lines(self) -> None:
        lines = _catalogue.summary(self.data)
        self.assertTrue(lines[0].startswith("characters: 11 men's, 10 women's (21)"))
        self.assertTrue(any(line.startswith("bottom_shoes M: 121 pairs") for line in lines))


if __name__ == "__main__":
    unittest.main()
