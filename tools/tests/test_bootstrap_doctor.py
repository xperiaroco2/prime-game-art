"""doctor: the hooks path is set in a repository, and the Meshy key is reported as yes or no, never by value."""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runner import common, pins
from runner.commands import doctor


def capture(func, *args) -> tuple[doctor.Report, str]:
    report = doctor.Report()
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        func(report, *args)
    return report, out.getvalue()


class MeshyKeyTest(unittest.TestCase):
    def test_set_key_says_yes_and_never_the_value(self) -> None:
        secret = "test-value-that-must-not-appear-0123456789"
        with mock.patch.dict(os.environ, {pins.MESHY_KEY_ENV: secret}):
            report, out = capture(doctor.check_meshy_key)
        self.assertIn("is set: yes", out)
        self.assertNotIn(secret, out)
        self.assertNotIn(secret[:8], out)
        self.assertEqual(report.failures, 0)

    def test_missing_key_says_no_and_does_not_fail(self) -> None:
        with mock.patch.object(common, "env", return_value=None):
            report, out = capture(doctor.check_meshy_key)
        self.assertIn("is set: no", out)
        self.assertEqual(report.failures, 0)


@unittest.skipUnless(shutil.which("git"), "git is not on PATH")
class HooksPathTest(unittest.TestCase):
    def setUp(self) -> None:
        common.OUT.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.TemporaryDirectory(dir=common.OUT, prefix="doctortest-")
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True, capture_output=True)

    def hooks_path(self) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.repo), "config", "--get", "core.hooksPath"], capture_output=True, text=True
        )
        return result.stdout.strip()

    def test_sets_the_hooks_path_once(self) -> None:
        (self.repo / "tools" / "githooks").mkdir(parents=True)
        (self.repo / "tools" / "githooks" / "pre-push").write_text("#!/bin/sh\n", encoding="utf-8")
        report, out = capture(doctor.ensure_hooks_path, self.repo)
        self.assertEqual(report.failures, 0, out)
        self.assertIn("set to tools/githooks", out)
        self.assertEqual(self.hooks_path(), "tools/githooks")
        report, out = capture(doctor.ensure_hooks_path, self.repo)
        self.assertIn("core.hooksPath is tools/githooks", out)

    def test_missing_hook_fails_with_a_fix(self) -> None:
        report, out = capture(doctor.ensure_hooks_path, self.repo)
        self.assertEqual(report.failures, 1)
        self.assertIn("->", out)
        self.assertEqual(self.hooks_path(), "")


class MissingToolTest(unittest.TestCase):
    def test_missing_blender_prints_a_fix(self) -> None:
        with mock.patch.dict(os.environ, {pins.BLENDER_ENV: str(common.OUT / "no-such-blender.exe")}):
            report, out = capture(doctor.check_blender, True)
        self.assertEqual(report.failures, 1)
        self.assertIn("Blender not found", out)
        self.assertIn("->", out)


if __name__ == "__main__":
    unittest.main()
