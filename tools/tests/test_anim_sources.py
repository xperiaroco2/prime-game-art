"""The animation source record (sources/quaternius_ual1_standard.toml) in the source record format of art issue #17,
until #17's manifest-check validates sources/; the raw files are re-hashed when the raw folder is present."""

from __future__ import annotations

import datetime
import hashlib
import re
import tomllib
import unittest

from runner import common

RECORD = common.ROOT / "sources" / "quaternius_ual1_standard.toml"
REQUIRED = {"id", "title", "author", "url", "licence", "licence_url", "public_repo_ok", "ai_generated",
            "downloaded_at", "raw"}
OPTIONAL = {"credit", "notes"}
LICENCES = {"CC0-1.0", "CC-BY-4.0", "owned-paid-output", "own-work", "restricted"}


class SourceRecordTest(unittest.TestCase):
    def setUp(self) -> None:
        self.data = tomllib.loads(RECORD.read_text(encoding="utf-8"))

    def test_fields(self) -> None:
        d = self.data
        self.assertEqual(REQUIRED - set(d), set())
        self.assertEqual(set(d) - REQUIRED - OPTIONAL, set())
        self.assertEqual(d["id"], RECORD.stem)
        self.assertRegex(d["id"], r"^[a-z0-9_]+$")
        self.assertIn(d["licence"], LICENCES)
        self.assertEqual(d["licence"], "CC0-1.0")
        for key in ("url", "licence_url"):
            self.assertRegex(d[key], r"^https?://")
        self.assertIs(d["public_repo_ok"], True)
        self.assertIs(d["ai_generated"], False)
        self.assertIsInstance(d["downloaded_at"], datetime.date)

    def test_raw_entries(self) -> None:
        files = [r["file"] for r in self.data["raw"]]
        self.assertEqual(len(files), len(set(files)))
        self.assertTrue(any(f.endswith("UAL1_Standard.glb") for f in files))
        self.assertTrue(any(f.endswith("UAL1_Standard_RM.glb") for f in files))
        self.assertTrue(any(f.endswith(".zip") for f in files))
        for r in self.data["raw"]:
            self.assertEqual(set(r), {"file", "sha256"})
            self.assertNotIn("\\", r["file"])
            self.assertNotIn("..", r["file"].split("/"))
            self.assertFalse(r["file"].startswith("/"))
            self.assertRegex(r["sha256"], r"^[0-9a-f]{64}$")

    def test_raw_hashes(self) -> None:
        raw = common.raw_dir()
        if not raw.is_dir():
            self.skipTest(f"no raw folder {raw}")
        for r in self.data["raw"]:
            path = raw / r["file"]
            with self.subTest(file=r["file"]):
                self.assertTrue(path.is_file(), path)
                digest = hashlib.sha256()
                with path.open("rb") as f:
                    for block in iter(lambda: f.read(1 << 20), b""):
                        digest.update(block)
                self.assertEqual(digest.hexdigest(), r["sha256"])

    def test_the_notes_name_the_clip_count(self) -> None:
        self.assertTrue(re.search(r"\b43 clips\b", self.data["title"] + self.data["notes"]))


if __name__ == "__main__":
    unittest.main()
