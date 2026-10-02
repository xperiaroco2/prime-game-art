"""The runner finds its command modules and refuses broken ones."""

import unittest

from runner import cli


class DiscoverTest(unittest.TestCase):
    def test_finds_pins(self) -> None:
        self.assertIn("pins", cli.discover())

    def test_every_command_has_the_contract(self) -> None:
        for name, module in cli.discover().items():
            with self.subTest(name=name):
                self.assertEqual(module.NAME, name)
                self.assertTrue(module.HELP)
                self.assertTrue(callable(module.add_arguments))
                self.assertTrue(callable(module.run))

    def test_pins_get(self) -> None:
        self.assertEqual(cli.main(["pins", "--get", "BLENDER"]), 0)


if __name__ == "__main__":
    unittest.main()
