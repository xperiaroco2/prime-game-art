"""raw-backup: copies finished items to the backup folder and checks their sha256 (fake Meshy, temp folders)."""

from __future__ import annotations

import contextlib
import io
import os
import tomllib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from runner import cli
from runner.commands import _meshy_batch as batches
from runner.commands import _meshy_run as runs

from tests._meshy_fake import FakeMeshy
from tests.test_meshy_batch import batch_data


def write_toml(data: dict, path: Path) -> None:
    """A minimal TOML writer for the test batch (strings, ints, bools, lists of ints, nested tables, items)."""

    def value(v: object) -> str:
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, list):
            return "[" + ", ".join(value(x) for x in v) + "]"
        return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'

    def table(d: dict) -> str:
        return "{" + ", ".join(f"{k} = {table(v) if isinstance(v, dict) else value(v)}" for k, v in d.items()) + "}"

    lines = [f"{k} = {table(v) if isinstance(v, dict) else value(v)}" for k, v in data.items() if k != "items"]
    for item in data["items"]:
        lines.append("[[items]]")
        lines += [f"{k} = {table(v) if isinstance(v, dict) else value(v)}" for k, v in item.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tomllib.loads(path.read_text(encoding="utf-8"))


class RawBackupTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        root = Path(self._tmp.name)
        self.raw, self.backup, self.path = root / "raw", root / "backup", root / "t-batch.toml"
        write_toml(batch_data(items=batch_data()["items"][:2]), self.path)
        self.batch = batches.load(self.path)
        self.env = mock.patch.dict(os.environ, {"ART_RAW_DIR": str(self.raw), "ART_RAW_BACKUP_DIR": str(self.backup)})
        self.env.start()
        fake = FakeMeshy()
        runs.Runner(self.batch, fake.client(), raw=self.raw, only=["a-1"]).run()

    def tearDown(self) -> None:
        self.env.stop()
        self._tmp.cleanup()

    def backup_cmd(self, *items: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["raw-backup", str(self.path), *items])
        return code, out.getvalue()

    def test_copies_finished_items_with_their_record(self) -> None:
        code, out = self.backup_cmd()
        self.assertEqual(code, 0, out)
        dest = self.backup / "t-batch" / "a-1"
        self.assertTrue((dest / "generation.json").is_file())
        self.assertTrue((dest / "refine-model.glb").is_file())
        self.assertTrue((self.backup / "t-batch" / "log.csv").is_file())
        self.assertFalse((self.backup / "t-batch" / "b-1").exists())  # never run, so not copied
        self.assertIn("7 files copied", out)
        code, out = self.backup_cmd("a-1")
        self.assertIn("0 files copied, 7 already there", out)

    def test_refuses_an_unfinished_item_by_name(self) -> None:
        code, out = self.backup_cmd("b-1")
        self.assertEqual(code, 1)
        self.assertIn("not finished", out)

    def test_refuses_a_changed_file(self) -> None:
        (self.raw / "t-batch" / "a-1" / "refine-model.glb").write_bytes(b"edited")
        code, out = self.backup_cmd("a-1")
        self.assertEqual(code, 1)
        self.assertIn("no longer matches", out)

    def test_no_backup_folder(self) -> None:
        with mock.patch("runner.common.raw_backup_dir", return_value=None):
            code, out = self.backup_cmd()
        self.assertEqual(code, 1)
        self.assertIn("OneDrive", out)


if __name__ == "__main__":
    unittest.main()
