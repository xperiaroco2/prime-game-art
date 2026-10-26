"""Every plain-Python runner script in tools/blender (`*_run.py`) parses.

No test imports these drivers, so a syntax error in one stays green in `verify` until someone runs it (art#263: a
quote inside a single-quoted f-string in board_run.py, found by the fix pass's review).
"""
import pathlib
import unittest

BLENDER = pathlib.Path(__file__).resolve().parents[1] / "blender"


class RunScriptsParse(unittest.TestCase):
    def test_every_run_script_compiles(self):
        scripts = sorted(BLENDER.glob("*_run.py"))
        self.assertTrue(scripts)
        for path in scripts:
            with self.subTest(script=path.name):
                compile(path.read_text(encoding="utf-8"), str(path), "exec")


if __name__ == "__main__":
    unittest.main()
