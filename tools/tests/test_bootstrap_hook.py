"""The pre-push hook refuses a push to main and a deletion of main, and lets a task branch through."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from runner import common

HOOKS = common.ROOT / "tools" / "githooks"


def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    result = subprocess.run(
        ["git", *args], cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60
    )
    if check and result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed:\n{result.stdout}{result.stderr}")
    return result


@unittest.skipUnless(shutil.which("git"), "git is not on PATH")
class PrePushHookTest(unittest.TestCase):
    def setUp(self) -> None:
        common.OUT.mkdir(parents=True, exist_ok=True)
        self._tmp = tempfile.TemporaryDirectory(dir=common.OUT, prefix="hooktest-")
        self.addCleanup(self._tmp.cleanup)
        tmp = Path(self._tmp.name)
        self.origin = tmp / "origin.git"
        self.clone = tmp / "clone"
        git(tmp, "init", "-q", "--bare", "-b", "main", str(self.origin))
        git(tmp, "init", "-q", "-b", "main", str(self.clone))
        for key, value in (
            ("user.name", "Hook Test"),
            ("user.email", "hook-test@example.invalid"),
            ("commit.gpgsign", "false"),
            ("core.hooksPath", HOOKS.as_posix()),
        ):
            git(self.clone, "config", key, value)
        git(self.clone, "remote", "add", "origin", str(self.origin))
        (self.clone / "a.txt").write_text("a\n", encoding="utf-8")
        git(self.clone, "add", "a.txt")
        git(self.clone, "commit", "-q", "-m", "a")

    def test_refuses_a_push_to_main(self) -> None:
        result = git(self.clone, "push", "origin", "HEAD:main", check=False)
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertIn("refused a push to main", result.stderr)
        self.assertEqual(git(self.origin, "branch", "--list", "main").stdout.strip(), "")

    def test_refuses_the_deletion_of_main(self) -> None:
        git(self.clone, "push", "-q", "--no-verify", "origin", "HEAD:main")
        result = git(self.clone, "push", "origin", ":main", check=False)
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertIn("refused the deletion of main", result.stderr)
        self.assertIn("main", git(self.origin, "branch", "--list", "main").stdout)

    def test_refuses_main_among_several_refs(self) -> None:
        result = git(self.clone, "push", "origin", "HEAD:refs/heads/tooling/9-ok", "HEAD:main", check=False)
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertIn("refused a push to main", result.stderr)

    @unittest.skipUnless(shutil.which("git-lfs"), "git-lfs is not installed: the hook needs it for allowed pushes")
    def test_lets_a_task_branch_through(self) -> None:
        result = git(self.clone, "push", "origin", "HEAD:refs/heads/tooling/9-task", check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("tooling/9-task", git(self.origin, "branch", "--list").stdout)


if __name__ == "__main__":
    unittest.main()
