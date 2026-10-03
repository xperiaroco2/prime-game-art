"""The UAL2 source record (sources/quaternius_ual2_standard.toml, art #24) in the source record format of art issue
#17, until #17's manifest-check validates sources/: its fields, its raw files (the zip, both GLBs, the Female
Mannequin, License.txt) and, when the raw folder is present, their hashes; and that the review settings read their
UAL2 files from the record."""

from __future__ import annotations

import datetime
import hashlib
import tomllib
import unittest

from runner import common
from runner.commands import _anim

RECORD = common.ROOT / "sources" / "quaternius_ual2_standard.toml"
REQUIRED = {"id", "title", "author", "url", "licence", "licence_url", "public_repo_ok", "ai_generated",
            "downloaded_at", "raw"}
OPTIONAL = {"credit", "notes"}
ZIP_SHA256 = "4008ea208a604773a2b2177d965f0f5d3195498b5bf838c3f5785d68e95f2a68"  # the manager's download (art #24)


class Ual2SourceRecordTest(unittest.TestCase):
    def setUp(self) -> None:
        self.data = tomllib.loads(RECORD.read_text(encoding="utf-8"))
        self.files = {r["file"]: r["sha256"] for r in self.data["raw"]}

    def test_fields(self) -> None:
        d = self.data
        self.assertEqual(REQUIRED - set(d), set())
        self.assertEqual(set(d) - REQUIRED - OPTIONAL, set())
        self.assertEqual(d["id"], RECORD.stem)
        self.assertEqual(d["licence"], "CC0-1.0")
        self.assertEqual(d["url"], "https://quaternius.itch.io/universal-animation-library-2")
        self.assertRegex(d["licence_url"], r"^https://")
        self.assertIs(d["public_repo_ok"], True)
        self.assertIs(d["ai_generated"], False)
        self.assertEqual(d["downloaded_at"], datetime.date(2026, 10, 3))

    def test_raw_entries(self) -> None:
        self.assertEqual(len(self.files), len(self.data["raw"]))
        names = [f.rsplit("/", 1)[-1] for f in self.files]
        for name in ("Universal Animation Library 2 [Standard].zip", "UAL2_Standard.glb", "UAL2_Standard_RM.glb",
                     "Mannequin_F.glb", "Mannequin_F.blend", "Mannequin_F.fbx", "License.txt"):
            self.assertIn(name, names)
        self.assertEqual(self.files["quaternius/Universal Animation Library 2 [Standard].zip"], ZIP_SHA256)
        for r in self.data["raw"]:
            self.assertEqual(set(r), {"file", "sha256"})
            self.assertNotIn("\\", r["file"])
            self.assertNotIn("..", r["file"].split("/"))
            self.assertRegex(r["sha256"], r"^[0-9a-f]{64}$")

    def test_the_review_reads_the_recorded_files(self) -> None:
        lib = _anim.libraries(_anim.load_config())["ual2"]
        self.assertIn(lib["file"], self.files)
        self.assertIn(lib["rm"], self.files)

    def test_raw_hashes(self) -> None:
        raw = common.raw_dir()
        if not raw.is_dir():
            self.skipTest(f"no raw folder {raw}")
        for name, sha in self.files.items():
            path = raw / name
            with self.subTest(file=name):
                if not path.is_file():  # a raw folder without the UAL2 download (another PC): nothing to check
                    self.skipTest(f"no raw file {path}")
                digest = hashlib.sha256()
                with path.open("rb") as f:
                    for block in iter(lambda: f.read(1 << 20), b""):
                        digest.update(block)
                self.assertEqual(digest.hexdigest(), sha)


if __name__ == "__main__":
    unittest.main()
