"""manifest-check: the passing fixture passes, the failing one names every broken rule."""

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


def run_cli(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(list(argv))
    return code, out.getvalue()


def good() -> dict:
    data, problem = _manifest.load(FIXTURES / "pass" / "assets" / "clothing" / "top_waders" / "manifest.toml")
    assert data is not None, problem
    return data


class ManifestCommandTest(unittest.TestCase):
    def test_passing_fixture_passes(self) -> None:
        code, out = run_cli("manifest-check", "--root", str(FIXTURES / "pass"))
        self.assertEqual(code, 0, out)
        self.assertIn("3 manifest(s), 0 problem(s)", out)

    def test_failing_fixture_fails(self) -> None:
        code, out = run_cli("manifest-check", "--root", str(FIXTURES / "fail"))
        self.assertEqual(code, 1, out)
        self.assertIn("assets/hair/no_manifest: no manifest.toml", out)
        self.assertIn("FAIL  assets/clothing/top_bad/manifest.toml", out)

    def test_a_tree_without_assets_passes(self) -> None:
        code, out = run_cli("manifest-check", "--root", str(FIXTURES))
        self.assertEqual(code, 0, out)
        self.assertIn("no manifests", out)


class ManifestRulesTest(unittest.TestCase):
    def test_failing_fixture_names_each_rule(self) -> None:
        data, problem = _manifest.load(FIXTURES / "fail" / "assets" / "clothing" / "top_bad" / "manifest.toml")
        self.assertIsNone(problem)
        errors = "\n".join(_manifest.validate(data or {}, "clothing", "top_bad"))
        for expected in (
            "id must be lowercase",
            "slot 'back_item' is not allowed for kind 'clothing'",
            "tools must be a non-empty list",
            "licence_url must be an http(s) URL",
            "public_repo_ok is true but licence 'restricted'",
            "approval is all or nothing",
            "unknown key 'colour'",
            "source: missing key 'generated_at'",
            "needs source.model_version",
            "at least one source.task_ids",
            "free-plan AI output is never used",
            "raw[0]: file must be a relative path",
            "raw[0]: sha256 must be 64 lowercase hex",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, errors)

    def test_good_manifest_is_valid(self) -> None:
        self.assertEqual(_manifest.validate(good(), "clothing", "top_waders"), [])

    def test_every_required_key_is_required(self) -> None:
        for key in _manifest.TOP_REQUIRED:
            data = good()
            del data[key]
            with self.subTest(key=key):
                self.assertIn(f"missing key {key!r}", "\n".join(_manifest.validate(data)))
        for key in _manifest.SOURCE_REQUIRED:
            data = good()
            del data["source"][key]
            with self.subTest(key=f"source.{key}"):
                self.assertIn(f"source: missing key {key!r}", "\n".join(_manifest.validate(data)))

    def test_folder_names_must_match(self) -> None:
        errors = "\n".join(_manifest.validate(good(), "accessory", "other_id"))
        self.assertIn("differs from its folder assets/accessory/", errors)
        self.assertIn("differs from its folder name 'other_id'", errors)

    def test_cc_by_needs_credit(self) -> None:
        data = good()
        data["licence"] = "CC-BY-4.0"
        self.assertIn("needs credit", "\n".join(_manifest.validate(data)))
        data["credit"] = "Model by Someone, CC BY 4.0"
        self.assertEqual(_manifest.validate(data), [])

    def test_face_slots_are_eyes_and_mouth(self) -> None:
        data = good()
        data["kind"] = "face"
        for slot in ("eyes", "mouth"):
            data["slot"] = slot
            self.assertEqual(_manifest.validate(data), [], slot)
        data["slot"] = "top"
        self.assertIn("not allowed for kind 'face'", "\n".join(_manifest.validate(data)))

    def test_slot_names_follow_the_character_contract(self) -> None:
        # contract/contract.toml (#4) names these slots; the short names an earlier draft used are refused.
        cases = {
            "hair": ("hair_or_hat",),
            "accessory": ("hair_or_hat", "face_accessory", "back_item"),
            "clothing": ("top", "bottom", "shoes"),
        }
        for kind, slots in cases.items():
            for slot in slots:
                data = good()
                data.update(kind=kind, slot=slot)
                self.assertEqual(_manifest.validate(data), [], f"{kind}/{slot}")
        for slot in ("head", "face_acc", "back"):
            data = good()
            data.update(kind="accessory", slot=slot)
            self.assertIn("not allowed for kind 'accessory'", "\n".join(_manifest.validate(data)), slot)

    def test_a_list_or_table_in_a_name_field_is_a_readable_error(self) -> None:
        for key, phrase in (("kind", "kind "), ("slot", "slot "), ("licence", "licence ")):
            for value in (["top"], {"a": 1}):
                with self.subTest(key=key, value=value):
                    data = good()
                    data[key] = value
                    self.assertIn(phrase, "\n".join(_manifest.validate(data)))

    def test_not_approved_is_valid(self) -> None:
        data = good()
        data.update(approved_by=[], approved_at="", approval_pr="")
        self.assertEqual(_manifest.validate(data), [])

    def test_approval_pr_must_be_a_pull_request(self) -> None:
        data = good()
        data["approval_pr"] = "https://github.com/xperiaroco2/prime-game-art/issues/12"
        self.assertIn("approval_pr must be a GitHub pull request URL", "\n".join(_manifest.validate(data)))

    def test_raw_hashes(self) -> None:
        common.OUT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=common.OUT, prefix="rawtest-") as tmp:
            raw_dir = Path(tmp)
            (raw_dir / "b").mkdir()
            (raw_dir / "b" / "x.glb").write_bytes(b"glb")
            data = copy.deepcopy(good())
            data["raw"] = [{"file": "b/x.glb", "sha256": hashlib.sha256(b"glb").hexdigest()}]
            self.assertEqual(_manifest.check_raw_hashes(data, raw_dir), [])
            data["raw"][0]["sha256"] = "0" * 64
            self.assertIn("not the recorded one", "\n".join(_manifest.check_raw_hashes(data, raw_dir)))
            data["raw"][0]["file"] = "b/missing.glb"
            self.assertIn("is missing", "\n".join(_manifest.check_raw_hashes(data, raw_dir)))

    def test_bad_toml_is_reported(self) -> None:
        common.OUT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=common.OUT, prefix="tomltest-") as tmp:
            path = Path(tmp) / "manifest.toml"
            path.write_text('id = "x\n', encoding="utf-8")
            data, problem = _manifest.load(path)
            self.assertIsNone(data)
            self.assertIn("not valid TOML", problem or "")


if __name__ == "__main__":
    unittest.main()
