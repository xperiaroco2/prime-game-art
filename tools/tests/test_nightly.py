"""`nightly` (#159): the night worktree's path, the log's outcome, the summary line and the issue text."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runner import common
from runner.commands import nightly

GREEN_LOG = """== verify: selftest
verify: full run, 89 fast and 20 heavy test files
slowest: test_kit_spec.py 115 s, test_anim_set.py 90 s
tests: 109 files, 1265 tests, 1 skipped, 0 red files, 591 s
== verify: manifest-check green (2.0 s)
verify: green (full: selftest, manifest-check) in 593 s
"""

RED_LOG = """== verify: selftest
== tests: 89 fast files, 8 at a time
  RED    12.5 s  test_house_layout.py
  RED     3.1 s  test_props_spec.py
== tests: the fast files are red; the 20 heavy files did not run
---- test_house_layout.py (exit 1) ----
AssertionError: the door is shut
tests: 89 files, 900 tests, 0 skipped, 2 red files, 130 s
verify: red at selftest; fix it and run verify again
"""


class PathTest(unittest.TestCase):
    def test_default_worktree_sits_beside_the_task_worktrees(self) -> None:
        self.assertEqual(
            nightly.default_worktree(Path("D:/prime-game-art")), Path("D:/prime-game-art-wt/nightly")
        )

    def test_the_main_checkout_and_task_worktrees_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            main = Path(tmp) / "repo"
            with self.assertRaises(common.Failure):
                nightly.check_worktree_path(main, main)
            with self.assertRaises(common.Failure):
                nightly.check_worktree_path(main / "nightly", main)
            with self.assertRaises(common.Failure):
                nightly.check_worktree_path(Path(tmp) / "repo-wt" / "verify159", main)
            nightly.check_worktree_path(Path(tmp) / "repo-wt" / "nightly", main)

    def test_log_path_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            first = nightly.log_path(out, "2026-10-14")
            self.assertEqual(first.name, "2026-10-14.log")
            first.write_text("x", encoding="utf-8")
            second = nightly.log_path(out, "2026-10-14")
            self.assertEqual(second.name, "2026-10-14-2.log")
            second.write_text("x", encoding="utf-8")
            self.assertEqual(nightly.log_path(out, "2026-10-14").name, "2026-10-14-3.log")


class OutcomeTest(unittest.TestCase):
    def test_green_log(self) -> None:
        outcome = nightly.parse_log(GREEN_LOG, 0, 600)
        self.assertTrue(outcome.green)
        self.assertEqual(outcome.red_files, [])
        line = nightly.summary_line("2026-10-14", "0123456789abcdef", outcome)
        self.assertEqual(
            line, "nightly 2026-10-14 012345678: green in 10.0 min "
            "(tests: 109 files, 1265 tests, 1 skipped, 0 red files, 591 s)"
        )
        self.assertNotIn("\n", line)

    def test_red_log_names_the_files_and_step(self) -> None:
        outcome = nightly.parse_log(RED_LOG, 1, 135)
        self.assertFalse(outcome.green)
        self.assertEqual(outcome.red_files, ["test_house_layout.py", "test_props_spec.py"])
        self.assertEqual(outcome.red_step, "selftest")
        line = nightly.summary_line("2026-10-14", "abc", outcome)
        self.assertIn("red in 2.2 min", line)
        self.assertIn("red files: test_house_layout.py, test_props_spec.py", line)

    def test_red_without_red_files(self) -> None:
        text = "tests: 109 files, 1265 tests, 0 skipped, 0 red files, 590 s\nverify: red at manifest-check (exit 1)\n"
        outcome = nightly.parse_log(text, 1, 60)
        self.assertEqual(outcome.red_step, "manifest-check")
        self.assertIn("red files: none (see the log)", nightly.summary_line("d", "c", outcome))
        crashed = nightly.parse_log("Traceback ...\n", 124, 60)
        self.assertEqual(crashed.red_step, "exit 124")


class IssueTest(unittest.TestCase):
    def test_issue_text_holds_the_files_log_and_tail(self) -> None:
        outcome = nightly.parse_log(RED_LOG, 1, 135)
        log = Path("D:/repo/tools/out/nightly/2026-10-14.log")
        long_log = "\n".join(f"line {i}" for i in range(100)) + "\n" + RED_LOG
        text = nightly.issue_text("2026-10-14", "abc123", outcome, log, long_log)
        self.assertIn("- `test_house_layout.py`", text)
        self.assertIn("- `test_props_spec.py`", text)
        self.assertIn(str(log), text)
        self.assertIn("verify: red at selftest", text)
        self.assertNotIn("line 0\n", text)
        fence = text.split("```text\n", 1)[1].split("\n```", 1)[0]
        self.assertEqual(len(fence.splitlines()), nightly.TAIL_LINES)

    def test_open_issue_is_found_by_exact_title(self) -> None:
        listed = json.dumps([
            {"number": 7, "title": "nightly: verify --full is red on main (old)"},
            {"number": 9, "title": nightly.NIGHTLY_TITLE},
        ])
        self.assertEqual(nightly.open_issue_number(listed), 9)
        self.assertIsNone(nightly.open_issue_number(json.dumps([{"number": 7, "title": "other"}])))
        self.assertIsNone(nightly.open_issue_number(""))


@unittest.skipUnless(shutil.which("git"), "needs git")
class PrepareTest(unittest.TestCase):
    """prepare() against a temp origin: creates the worktree, moves it to a new origin/main, refuses local edits."""

    def git(self, cwd: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.hooksPath=", *args],
            cwd=cwd, capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def commit(self, repo: Path, text: str) -> str:
        (repo / "a.txt").write_text(text, encoding="utf-8")
        self.git(repo, "add", "a.txt")
        self.git(repo, "commit", "-q", "-m", text)
        self.git(repo, "push", "-q", "origin", "HEAD:main")
        return self.git(repo, "rev-parse", "HEAD")

    def test_prepare(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.git(root, "init", "-q", "--bare", "-b", "main", "origin.git")
            self.git(root, "clone", "-q", str(root / "origin.git"), "repo")
            repo, night = root / "repo", root / "repo-wt" / "nightly"
            first = self.commit(repo, "one")
            with mock.patch.object(common, "ROOT", repo):
                self.assertEqual(nightly.prepare(night), first)
                second = self.commit(repo, "two")
                self.git(repo, "reset", "-q", "--hard", first)  # the checkout lags; prepare fetches
                self.assertEqual(nightly.prepare(night), second)
                (night / "a.txt").write_text("edited", encoding="utf-8")
                with self.assertRaises(common.Failure):
                    nightly.prepare(night)


if __name__ == "__main__":
    unittest.main()
