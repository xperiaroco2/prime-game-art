"""The raw root and the design repository beside the main checkout, and references kept as text (#136, the D: loss)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runner import common, pins  # noqa: E402


class MainCheckoutTest(unittest.TestCase):
    def test_a_main_checkout_is_itself(self):
        with tempfile.TemporaryDirectory() as tmp:
            main = Path(tmp) / "prime-game-art"
            (main / ".git").mkdir(parents=True)
            self.assertEqual(pins.main_checkout(main), main)
            self.assertEqual(pins.beside_checkout("prime-art-raw", main), Path(tmp) / "prime-art-raw")

    def test_a_worktree_finds_its_main_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            main = Path(tmp) / "prime-game-art"
            (main / ".git" / "worktrees" / "task").mkdir(parents=True)
            wt = Path(tmp) / "prime-game-art-wt" / "task"
            wt.mkdir(parents=True)
            (wt / ".git").write_text(f"gitdir: {(main / '.git' / 'worktrees' / 'task').as_posix()}\n", encoding="utf-8")
            self.assertEqual(pins.main_checkout(wt), main)
            self.assertEqual(pins.beside_checkout("prime-art-raw", wt), Path(tmp) / "prime-art-raw")

    def test_a_relative_gitdir(self):
        with tempfile.TemporaryDirectory() as tmp:
            main = Path(tmp) / "repo"
            (main / ".git" / "worktrees" / "w").mkdir(parents=True)
            wt = Path(tmp) / "wt"
            wt.mkdir()
            (wt / ".git").write_text("gitdir: ../repo/.git/worktrees/w", encoding="utf-8")
            self.assertEqual(pins.main_checkout(wt).resolve(), main.resolve())

    def test_a_submodule_style_gitdir_is_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "sub"
            root.mkdir()
            (root / ".git").write_text("gitdir: ../.git/modules/sub", encoding="utf-8")
            self.assertEqual(pins.main_checkout(root), root)


class RawRootTest(unittest.TestCase):
    def test_the_default_is_beside_the_main_checkout(self):
        with mock.patch.object(common, "env", lambda name: None):
            self.assertEqual(common.raw_dir(), pins.beside_checkout(pins.RAW_DIRNAME))
            self.assertEqual(common.design_dir(), pins.beside_checkout(pins.DESIGN_DIRNAME))
            self.assertNotIn("D:", str(common.raw_dir()))

    def test_the_variables_win(self):
        values = {pins.RAW_ENV: "/data/raw", pins.DESIGN_ENV: "/data/design"}
        with mock.patch.object(common, "env", values.get):
            self.assertEqual(common.raw_dir(), Path("/data/raw"))
            self.assertEqual(common.design_dir(), Path("/data/design"))

    def test_references_resolve_their_root(self):
        values = {pins.RAW_ENV: "/data/raw", pins.DESIGN_ENV: "/data/design"}
        with mock.patch.object(common, "env", values.get):
            self.assertEqual(common.resolve_ref("<raw>/a/b.png"), "/data/raw/a/b.png")
            self.assertEqual(common.resolve_ref("<design>/ideas/c.jpg"), "/data/design/ideas/c.jpg")
            self.assertEqual(common.resolve_ref("D:/prime-art-raw/a/b.png"), "/data/raw/a/b.png")
            self.assertEqual(common.resolve_ref("D:/prime-game-design/ideas/c.jpg"), "/data/design/ideas/c.jpg")
            self.assertEqual(common.resolve_ref("relative/x.png"), "relative/x.png")


class NoDriveInCodeTest(unittest.TestCase):
    def test_no_code_defaults_to_the_lost_drive(self):
        """Python and GDScript under tools/ and godot/ name no D:/prime-art-raw or D:/prime-game-design path (the
        resolver's old-root table aside); comments say <raw>/ and <design>/."""
        root = Path(__file__).resolve().parents[2]
        bad = []
        for path in [*root.glob("tools/runner/**/*.py"), *root.glob("tools/blender/**/*.py"), *root.glob("godot/**/*.gd")]:
            text = path.read_text(encoding="utf-8", errors="replace")
            if path.name == "common.py" and path.parent.name == "runner":
                text = text.replace('"D:/prime-art-raw/": raw_dir', "").replace('"D:/prime-game-design/": design_dir', "")
            if "D:/prime-art-raw" in text or "D:/prime-game-design" in text:
                bad.append(path.relative_to(root).as_posix())
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
