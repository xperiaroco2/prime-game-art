"""verify runs selftest, then manifest-check; selftest discovers every task's tests."""

import unittest

from runner import cli
from runner.commands import selftest, verify


class VerifyTest(unittest.TestCase):
    def test_steps_are_selftest_then_manifest_check(self) -> None:
        self.assertEqual(verify.STEPS, ("selftest", "manifest-check"))

    def test_every_step_is_a_command(self) -> None:
        commands = cli.discover()
        for step in verify.STEPS:
            with self.subTest(step=step):
                self.assertIn(step, commands)

    def test_selftest_discovers_tools_tests(self) -> None:
        cmd = selftest.command()
        self.assertEqual(cmd[1:4], ["-m", "unittest", "discover"])
        self.assertEqual(cmd[cmd.index("-s") + 1], "tools/tests")
        self.assertEqual(cmd[cmd.index("-t") + 1], "tools")


if __name__ == "__main__":
    unittest.main()
