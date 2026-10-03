"""Source records (sources/*.toml) and their check in manifest-check."""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from runner import cli, common
from runner.commands import _manifest

GOOD = '''id = "{id}"
title = "Some Pack"
author = "Someone"
url = "https://example.org/pack.html"
licence = "CC0-1.0"
licence_url = "https://creativecommons.org/publicdomain/zero/1.0/"
public_repo_ok = true
ai_generated = false
downloaded_at = 2026-10-03

[[raw]]
file = "refs/Some Pack.zip"
sha256 = "{sha}"
'''
SHA = "0" * 64


def run_cli(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(list(argv))
    return code, out.getvalue()


class SourceRulesTest(unittest.TestCase):
    def parse(self, text: str) -> dict:
        import tomllib

        return tomllib.loads(text)

    def test_a_good_record_passes(self) -> None:
        self.assertEqual(_manifest.validate_source(self.parse(GOOD.format(id="some_pack", sha=SHA)), "some_pack"), [])

    def test_each_rule_is_named(self) -> None:
        text = GOOD.format(id="Some-Pack", sha="abc").replace('licence = "CC0-1.0"', 'licence = "restricted"')
        text = text.replace('url = "https://example.org/pack.html"', 'url = "example.org"')
        text = text.replace("downloaded_at = 2026-10-03", 'downloaded_at = "yesterday"\nwhen = 1')
        text = text.replace('author = "Someone"\n', "")
        text += '\n[[raw]]\nfile = "refs/Some Pack.zip"\nsha256 = "' + SHA + '"\n'
        errors = "\n".join(_manifest.validate_source(self.parse(text), "some_pack"))
        for expected in (
            "missing key 'author'",
            "unknown key 'when'",
            "id must be lowercase",
            "url must be the http(s) page",
            "downloaded_at must be a TOML date",
            "raw[0]: sha256 must be 64 lowercase hex digits",
            "raw file 'refs/Some Pack.zip' is listed twice",
            "public_repo_ok is true but licence 'restricted'",
        ):
            self.assertIn(expected, errors)

    def test_cc_by_needs_credit_and_the_id_matches_the_file(self) -> None:
        data = self.parse(GOOD.format(id="some_pack", sha=SHA).replace("CC0-1.0", "CC-BY-4.0"))
        errors = "\n".join(_manifest.validate_source(data, "other_name"))
        self.assertIn("a CC-BY-4.0 source needs credit", errors)
        self.assertIn("id 'some_pack' differs from its file name other_name.toml", errors)


class SourceCommandTest(unittest.TestCase):
    def test_manifest_check_validates_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sources").mkdir()
            (root / "sources" / "good_pack.toml").write_text(GOOD.format(id="good_pack", sha=SHA), encoding="utf-8")
            code, out = run_cli("manifest-check", "--root", str(root))
            self.assertEqual(code, 0, out)
            self.assertIn("ok    sources/good_pack.toml", out)
            self.assertIn("0 manifest(s), 1 source record(s), 0 problem(s)", out)
            (root / "sources" / "bad_pack.toml").write_text(GOOD.format(id="bad_pack", sha="x"), encoding="utf-8")
            code, out = run_cli("manifest-check", "--root", str(root))
            self.assertEqual(code, 1, out)
            self.assertIn("FAIL  sources/bad_pack.toml", out)
            self.assertIn("0 manifest(s), 2 source record(s), 1 problem(s)", out)

    def test_hashes_are_checked_in_the_raw_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp)
            (raw / "refs").mkdir()
            (raw / "refs" / "Some Pack.zip").write_bytes(b"zip")
            data = {"raw": [{"file": "refs/Some Pack.zip", "sha256": SHA}, {"file": "refs/gone.glb", "sha256": SHA}]}
            errors = "\n".join(_manifest.check_raw_hashes(data, raw))
            self.assertIn("raw[0]: ", errors)
            self.assertIn("not the recorded one", errors)
            self.assertIn("raw[1]: ", errors)
            self.assertIn("is missing", errors)


class RepoSourcesTest(unittest.TestCase):
    PACKS = ("quaternius_ultimate_modular_men", "quaternius_ultimate_modular_women")

    def test_the_repo_records_are_valid(self) -> None:
        paths = _manifest.find_sources(common.ROOT)
        self.assertTrue({p.stem for p in paths} >= set(self.PACKS))
        for path in paths:
            with self.subTest(record=path.name):
                data, problem = _manifest.load(path)
                self.assertIsNone(problem)
                self.assertEqual(_manifest.validate_source(data or {}, path.stem), [])

    def test_the_pack_records(self) -> None:
        for stem, count in zip(self.PACKS, (11, 10)):
            data, _ = _manifest.load(common.ROOT / "sources" / f"{stem}.toml")
            assert data is not None
            self.assertEqual((data["licence"], data["public_repo_ok"], data["ai_generated"]), ("CC0-1.0", True, False))
            self.assertEqual(data["licence_url"], "https://creativecommons.org/publicdomain/zero/1.0/")
            self.assertTrue(data["url"].startswith("https://quaternius.com/packs/"))
            files = [r["file"] for r in data["raw"]]
            self.assertEqual(len([f for f in files if f.endswith(".glb")]), count)
            self.assertEqual(len([f for f in files if f.endswith(".zip")]), 1)

    @unittest.skipUnless((common.raw_dir() / "refs").is_dir(), f"no raw folder at {common.raw_dir().as_posix()}")
    def test_the_pack_hashes_match_the_raw_files(self) -> None:
        for stem in self.PACKS:
            data, _ = _manifest.load(common.ROOT / "sources" / f"{stem}.toml")
            self.assertEqual(_manifest.check_raw_hashes(data or {}, common.raw_dir()), [])


if __name__ == "__main__":
    unittest.main()
