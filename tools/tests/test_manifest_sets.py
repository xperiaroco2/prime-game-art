"""manifest-check's House kinds and set manifests (#118): kit, room and environment, and [[files]] checked against the
source records their pack-made files name."""

from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import tempfile
import unittest
from pathlib import Path

from runner import cli, common
from runner.commands import _manifest

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "manifest"


def load(path: Path) -> dict:
    data, problem = _manifest.load(path)
    assert data is not None, problem
    return data


def kit() -> dict:
    return load(FIXTURES / "pass" / "assets" / "kit" / "fixture_kit" / "manifest.toml")


def records(tree: str) -> dict[str, dict]:
    return {path.stem: load(path) for path in _manifest.find_sources(FIXTURES / tree)}


class SetManifestTest(unittest.TestCase):
    def test_the_set_fixture_is_valid(self) -> None:
        self.assertEqual(_manifest.validate(kit(), "kit", "fixture_kit", records("pass")), [])

    def test_the_house_kinds_fill_no_slot(self) -> None:
        for kind in ("kit", "room", "environment"):
            data = copy.deepcopy(kit())
            data["kind"] = kind
            with self.subTest(kind=kind):
                self.assertEqual(_manifest.validate(data, kind, "fixture_kit", records("pass")), [])
                data["slot"] = "top"
                self.assertIn("slot 'top' is not allowed", "\n".join(_manifest.validate(data)))

    def test_a_set_needs_raw_or_files(self) -> None:
        data = copy.deepcopy(kit())
        del data["files"]
        self.assertIn("missing key 'raw'", "\n".join(_manifest.validate(data)))

    def test_a_character_kind_cannot_be_a_set(self) -> None:
        data = copy.deepcopy(kit())
        data["kind"] = "clothing"
        data["slot"] = "top"
        self.assertIn("kind 'clothing' cannot be a set", "\n".join(_manifest.validate(data)))

    def test_the_broken_set_names_each_rule(self) -> None:
        data = load(FIXTURES / "fail" / "assets" / "kit" / "kit_bad" / "manifest.toml")
        errors = "\n".join(_manifest.validate(data, "kit", "kit_bad", records("fail")))
        for expected in (
            "files[0]: name must be a relative path",
            "files[0]: file must be a relative path inside the raw folder",
            "files[0]: sha256 must be 64 lowercase hex",
            "files[1]: 'env/private/private-pack/shade.glb' is not a [[raw]] file of sources/private_pack.toml",
            "files[1]: the set is public_repo_ok but source 'private_pack' may not reach the public game repo",
            "files[2]: source 'no_such_pack' has no record sources/no_such_pack.toml",
            "files[3]: from needs source",
            "files[3]: unknown key 'colour'",
            "files: name 'lamp.glb' is listed twice",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, errors)

    def test_a_private_set_may_use_a_private_pack(self) -> None:
        data = load(FIXTURES / "fail" / "assets" / "kit" / "kit_bad" / "manifest.toml")
        data["public_repo_ok"] = False
        errors = "\n".join(_manifest.validate(data, None, None, records("fail")))
        self.assertNotIn("may not reach the public game repo", errors)

    def test_the_command_checks_files_against_the_records(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["manifest-check", "--root", str(FIXTURES / "fail")])
        self.assertEqual(code, 1, out.getvalue())
        self.assertIn("FAIL  assets/kit/kit_bad/manifest.toml", out.getvalue())
        self.assertIn("source 'no_such_pack' has no record", out.getvalue())

    def test_file_and_export_hashes(self) -> None:
        common.OUT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=common.OUT, prefix="settest-") as tmp:
            raw_dir, asset_dir = Path(tmp) / "raw", Path(tmp) / "asset"
            (raw_dir / "k").mkdir(parents=True)
            (raw_dir / "k" / "wall.glb").write_bytes(b"wall")
            data = copy.deepcopy(kit())
            data["files"] = [{"name": "wall.glb", "file": "k/wall.glb", "sha256": hashlib.sha256(b"wall").hexdigest()}]
            self.assertEqual(_manifest.check_raw_hashes(data, raw_dir), [])
            self.assertEqual(_manifest.check_export_hashes(data, asset_dir), [], "a file not exported yet is skipped")
            (asset_dir / "export").mkdir(parents=True)
            (asset_dir / "export" / "wall.glb").write_bytes(b"changed")
            self.assertIn("not the recorded one", "\n".join(_manifest.check_export_hashes(data, asset_dir)))
            data["files"][0]["file"] = "k/missing.glb"
            self.assertIn("files[0]: ", "\n".join(_manifest.check_raw_hashes(data, raw_dir)))


if __name__ == "__main__":
    unittest.main()
