"""The off-screen review window (#214, docs/godot.md): the runner's check of the OFFSCREEN lines, the window settings
of every Godot project that opens a window, and that every window run goes through _godot.window() and every window
script places its window first. Plain Python, no Godot."""

from __future__ import annotations

import re
import unittest

from runner import common
from runner.commands import _godot, _house_export, _house_review

SCREEN = "0,0,2560,1440"
ROOT = common.ROOT


def line(x: int, y: int, w: int, h: int, screens: str = SCREEN) -> str:
    return f"OFFSCREEN window {x},{y} {w}x{h} screens {screens} ticks 1200"


class Problems(unittest.TestCase):
    def test_off_screen_passes(self):
        self.assertEqual(_godot.offscreen_problems("start\n" + line(-30000, -30000, 480, 600) + "\nFRAMES saved x"), [])

    def test_no_line_is_refused(self):
        problems = _godot.offscreen_problems("FRAMES saved x")
        self.assertEqual(len(problems), 1)
        self.assertIn("no OFFSCREEN line", problems[0])

    def test_the_corner_godot_clamps_to_is_refused(self):
        # What Godot 4.7.2 does with --position -30000,-30000 alone: the window at the screen's top-left corner.
        problems = _godot.offscreen_problems(line(-8, -31, 496, 639))
        self.assertEqual(len(problems), 1)
        self.assertIn("on screen 0", problems[0])

    def test_one_pixel_on_screen_is_refused(self):
        self.assertTrue(_godot.offscreen_problems(line(2559, 1439, 480, 600)))
        self.assertEqual(_godot.offscreen_problems(line(2560, 0, 480, 600)), [])  # touching the edge is off it
        self.assertEqual(_godot.offscreen_problems(line(-480, 0, 480, 600)), [])

    def test_every_screen_counts(self):
        screens = SCREEN + ";-1920,0,1920,1080"
        self.assertIn("on screen 1", _godot.offscreen_problems(line(-1000, 100, 480, 600, screens))[0])
        self.assertEqual(_godot.offscreen_problems(line(-30000, -30000, 480, 600, screens)), [])

    def test_a_later_line_on_screen_is_refused(self):
        out = line(-30000, -30000, 480, 600) + "\n" + line(0, 0, 1920, 1080)
        self.assertEqual(len(_godot.offscreen_problems(out)), 1)

    def test_ansi_colour_is_ignored(self):
        self.assertEqual(_godot.offscreen_problems("\x1b[0m" + line(-30000, -30000, 64, 64) + "\x1b[0m"), [])

    def test_the_window_starts_as_one_pixel_far_right(self):
        """Godot clamps the start to the usable area's far edge minus a third of the size: 0 for 1x1 px (#214)."""
        args = _godot.WINDOW_START
        self.assertEqual(args[args.index("--resolution") + 1], "1x1")
        x, y = (int(v) for v in args[args.index("--position") + 1].split(","))
        self.assertGreater(min(x, y), 16384)  # past any screen's far edge, so the clamp puts it there

    def test_window_size_argument(self):
        self.assertEqual(_godot.window_env((480, 600)), {_godot.WINDOW_ENV: "480x600"})
        with self.assertRaises(ValueError):
            _godot.window_env((0, 600))


class Projects(unittest.TestCase):
    """Every Godot project that opens a window starts it borderless and unfocused, so the 1x1 px start is one pixel."""

    def assert_settings(self, name: str, text: str) -> None:
        display = text.split("[display]", 1)
        self.assertEqual(len(display), 2, f"{name}: no [display] section")
        section = display[1].split("\n[", 1)[0]
        for setting in _godot.WINDOW_SETTINGS:
            self.assertIn(setting, section.splitlines(), f"{name}: {setting} missing from [display]")

    def test_committed_projects(self):
        for path in (ROOT / "godot" / "project.godot", ROOT / "godot" / "ragdoll" / "project.godot"):
            self.assert_settings(path.relative_to(ROOT).as_posix(), path.read_text(encoding="utf-8"))

    def test_generated_projects(self):
        self.assert_settings("_house_export.PROJECT", _house_export.PROJECT)
        self.assert_settings("_house_review.PROJECT", _house_review.PROJECT)


class CallSites(unittest.TestCase):
    def test_no_runner_passes_position_or_resolution(self):
        """--position does not work (#214) and --resolution would open the window at full size on screen."""
        for path in sorted((ROOT / "tools" / "runner").rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            for flag in ('"--position"', '"--resolution"'):
                if flag in text and path.name != "_godot.py":
                    self.fail(f"{path.relative_to(ROOT).as_posix()} passes {flag}: run windows through _godot.window()")

    def test_every_window_script_places_its_window(self):
        """A script that checks for a real window (or draws frames) calls Offscreen.place() in _initialize."""
        scripts = [p for p in sorted((ROOT / "godot").rglob("*.gd"))
                   if "import" not in p.relative_to(ROOT / "godot").parts[:1]
                   and re.search(r'get_name\(\) == "headless"|get_texture\(\)\.get_image\(\)', p.read_text(encoding="utf-8"))]
        self.assertGreaterEqual(len(scripts), 12, [p.name for p in scripts])
        shared = {"lib/offscreen.gd", "house/draw_cost.gd"}  # the helper itself; an overlay walk.gd and bake_shots.gd use
        for path in scripts:
            rel = path.relative_to(ROOT / "godot").as_posix()
            if rel in shared:
                continue
            text = path.read_text(encoding="utf-8")
            if text.startswith('extends "res://'):  # garden/proof.gd inherits outdoor/proof.gd's _initialize
                continue
            self.assertIn("Offscreen.place(", text, f"godot/{rel} draws pictures but never places its window off-screen")


if __name__ == "__main__":
    unittest.main()
