"""The heavy-run lock: one Blender or Godot process at a time on the machine, across checkouts and worktrees."""

import os
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from unittest import mock

from runner import common

TOOLS = common.ROOT / "tools"

# A second process takes the lock at argv[1] and holds it for argv[2] seconds, printing "held" once it has it.
HOLDER = textwrap.dedent(
    """
    import sys, time
    sys.path.insert(0, sys.argv[3])
    from runner import common
    with common.heavy_lock("test holder"):
        print("held", flush=True)
        time.sleep(float(sys.argv[2]))
    """
)


class IsHeavyTest(unittest.TestCase):
    def test_blender_and_godot_are_heavy(self) -> None:
        self.assertTrue(common.is_heavy(["D:/tools/blender/5.2.2/blender.exe", "-b"]))
        self.assertTrue(common.is_heavy([Path("C:/x/Godot_v4.7.2-stable_win64_console.exe"), "--headless"]))
        self.assertTrue(common.is_heavy(["blender"]))

    def test_other_tools_are_not(self) -> None:
        self.assertFalse(common.is_heavy(["git", "status"]))
        self.assertFalse(common.is_heavy(["D:/tools/gltf-validator/gltf_validator.exe"]))
        self.assertFalse(common.is_heavy([]))


class HeavyLockTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.lock = Path(self.tmp.name) / "locks" / "heavy.lock"
        patcher = mock.patch.dict(os.environ, {common.HEAVY_LOCK_ENV: str(self.lock)})
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop(common.HEAVY_HELD_ENV, None)

    def hold_in_child(self, seconds: float) -> subprocess.Popen:
        child = subprocess.Popen(
            [sys.executable, "-c", HOLDER, str(self.lock), str(seconds), str(TOOLS)],
            stdout=subprocess.PIPE,
            text=True,
            env={**os.environ, common.HEAVY_LOCK_ENV: str(self.lock)},
        )
        self.addCleanup(child.wait)
        self.assertEqual(child.stdout.readline().strip(), "held")
        return child

    def test_path_off_and_explicit(self) -> None:
        self.assertEqual(common.heavy_lock_path(), self.lock)
        with mock.patch.dict(os.environ, {common.HEAVY_LOCK_ENV: "off"}):
            self.assertIsNone(common.heavy_lock_path())

    def test_takes_and_releases(self) -> None:
        with common.heavy_lock("first"):
            self.assertEqual(os.environ.get(common.HEAVY_HELD_ENV), "1")
            self.assertIn("first", self.lock.with_name("heavy.lock.holder").read_text(encoding="utf-8"))
        self.assertIsNone(os.environ.get(common.HEAVY_HELD_ENV))
        with common.heavy_lock("second", wait=1):
            pass

    def test_waits_for_another_process_then_fails(self) -> None:
        child = self.hold_in_child(30)
        self.addCleanup(child.kill)
        start = time.monotonic()
        with self.assertRaises(common.Failure) as caught:
            with common.heavy_lock("blocked", wait=1.5):
                self.fail("took a lock another process holds")
        self.assertGreaterEqual(time.monotonic() - start, 1.5)
        self.assertIn("test holder", str(caught.exception))

    def test_takes_it_once_the_holder_ends(self) -> None:
        self.hold_in_child(1)
        with common.heavy_lock("after", wait=30):
            pass

    def test_released_when_the_holder_dies(self) -> None:
        child = self.hold_in_child(60)
        child.kill()
        child.wait()
        with common.heavy_lock("after a kill", wait=30):
            pass

    def test_a_child_of_the_holder_does_not_wait(self) -> None:
        with common.heavy_lock("parent", wait=1):
            child = self.hold_in_child(0)  # inherits HEAVY_HELD_ENV: prints "held" at once, no wait
            child.wait()
        self.assertEqual(child.returncode, 0)

    def test_run_takes_the_lock_for_heavy_commands_only(self) -> None:
        child = self.hold_in_child(30)
        self.addCleanup(child.kill)
        result = common.run([sys.executable, "-c", "print('light')"], 30)
        self.assertEqual(result.stdout.strip(), "light")
        with mock.patch.dict(os.environ, {common.HEAVY_WAIT_ENV: "1"}):
            with self.assertRaises(common.Failure):
                common.run(["blender", "--version"], 30)


if __name__ == "__main__":
    unittest.main()
