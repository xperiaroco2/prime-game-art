"""The frames command (docs/godot.md): which frames a sheet shows, the spec, the joint comparison; and, on a desktop with
Godot, Blender, the validator and the packs, one sheet rendered in an off-screen window with Blender's comparison."""

from __future__ import annotations

import json
import os
import unittest

from runner.commands import _frames, _review

from . import _export_fixture as fx

HAVE_DISPLAY = os.name == "nt" or bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
IN_CI = bool(os.environ.get("CI"))


class TimesTest(unittest.TestCase):
    def test_whole_frames_eight_or_twelve(self) -> None:
        self.assertEqual(_frames.times(40 / 24, "Idle"), [round(f / 24, 6) for f in (0, 5, 10, 15, 20, 25, 30, 35)])
        walk = _frames.times(32 / 24, "Walk")
        self.assertEqual(len(walk), 12)
        self.assertEqual([round(t * 24) for t in walk], [0, 3, 5, 8, 11, 13, 16, 19, 21, 24, 27, 29])
        death = _frames.times(25 / 24, "Death")  # a one-off: first to last frame
        self.assertEqual([round(t * 24) for t in death], [0, 4, 7, 11, 14, 18, 21, 25])
        self.assertEqual(len(_frames.times(1.0, "Run_Left")), 12)

    def test_an_open_cycle_is_one_frame_longer_than_its_keys(self) -> None:
        open_seam, closed_seam = {"position_mm": 103.3, "rotation_deg": 18.4}, {"position_mm": 0.01, "rotation_deg": 0.04}
        run = _frames.cycle(19 / 24, "Run", open_seam)
        self.assertEqual((run["open_cycle"], run["video_frames"], run["cycle_s"]), (True, 20, round(20 / 24, 6)))
        self.assertIn("its last key is not its first", run["note"])
        walk = _frames.cycle(32 / 24, "Walk", closed_seam)
        self.assertEqual((walk["open_cycle"], walk["video_frames"]), (False, 32))  # frame 32 is frame 0 again
        wave = _frames.cycle(40 / 24, "Wave", open_seam)  # a one-off shows its last frame too
        self.assertEqual((wave["loop"], wave["open_cycle"], wave["video_frames"]), (False, False, 41))
        self.assertEqual([round(t * 24) for t in _frames.times(19 / 24, "Run", open_cycle=True)][:4], [0, 2, 3, 5])
        self.assertEqual(_frames.times(20 / 24, "Run"), _frames.times(19 / 24, "Run", open_cycle=True))

    def test_spec(self) -> None:
        spec = _frames.spec("x", {"CharacterArmature|Wave": 40 / 24, "CharacterArmature|Run": 19 / 24}, ["Wave"], ["Run"])
        self.assertEqual([c["label"] for c in spec["clips"]], ["Run", "Wave"])
        run, wave = spec["clips"]
        self.assertEqual((run["loop"], run["keep"], run["video"], run["video_frames"]), (True, False, True, 19))
        self.assertEqual((wave["loop"], wave["keep"], wave["video"]), (False, True, False))
        self.assertEqual(spec["cell"], list(_frames.CELL))

    def test_compare_joints(self) -> None:
        godot = {"clips": {"Wave": {"times": [0.0, 0.5], "joints": [{"Head": [0, 1.6, 0]}, {"Head": [0, 1.6, 0.012]}]}}}
        blender = {"joints": {"Wave": [{"Head": [0, 1.6, 0]}, {"Head": [0, 1.6, 0]}]}}
        r = _frames.compare_joints(godot, blender)["Wave"]
        self.assertEqual((r["max_mm"], r["where"], r["per_time_mm"], r["match"]), (12.0, "Head at 0.500 s", [0.0, 12.0], False))

    def test_a_leaf_bone_turned_in_place_fails_through_its_axis_points(self) -> None:
        # Head is a leaf: its joint stays put when it turns, its axis points do not
        godot = {"clips": {"Idle": {"times": [0.0], "joints": [{"Head": [0, 1.6, 0], "Head+x": [0.1, 1.6, 0], "Head+y": [0, 1.7, 0]}]}}}
        blender = {"joints": {"Idle": [{"Head": [0, 1.6, 0], "Head+x": [0.0995, 1.6, -0.01], "Head+y": [0, 1.7, 0]}]}}
        r = _frames.compare_joints(godot, blender)["Idle"]
        self.assertEqual((r["joints"], r["axis_points"], r["where"], r["match"]), (1, 2, "Head+x at 0.000 s", False))

    def test_unknown_clips_are_refused_before_godot_starts(self) -> None:
        folder = fx.OUT / "refusal"  # a stand-in GLB: frames reads only its export.json before Godot starts
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "x.glb").write_bytes(b"glTF")
        info = {"parts": {}, "bones": [], "actions": {"CharacterArmature|Idle": [0, 40]}, "fps": 24}
        (folder / "x.export.json").write_text(json.dumps(info), encoding="utf-8")
        code, out = fx.run_cli("frames", str(folder / "x.glb"), "--clips", "Moonwalk")
        self.assertEqual(code, 1)
        self.assertIn("unknown clips Moonwalk", out)


@unittest.skipUnless(fx.CAN_EXPORT and fx.HAVE_GODOT and HAVE_DISPLAY and not IN_CI,
                     fx.SKIP_EXPORT + ", Godot (GODOT_BIN) and a desktop session (the frames need a real window)")
class FramesInGodotTest(unittest.TestCase):
    def test_a_sheet_from_an_off_screen_window_and_the_comparison(self) -> None:
        code, out = fx.exported()
        self.assertEqual(code, 0, out)
        folder = fx.OUT / "frames" / "w1_ivy"
        code, out = fx.run_cli("frames", str(fx.glb("w1_ivy")), "--clips", "Wave", "--compare", "Wave", "--out", str(folder))
        self.assertEqual(code, 0, out)
        width, height = _review.png_size(folder / "sheets" / "Wave.png")
        self.assertEqual(width, 4 * _frames.CELL[0] + 5 * 4)  # 8 frames in 4 columns, 4 px apart
        self.assertEqual(height, 52 + 2 * _frames.CELL[1] + 3 * 4)
        record = json.loads((folder / "frames.json").read_text(encoding="utf-8"))
        self.assertEqual(record["window"], list(_frames.WINDOW))
        self.assertEqual(len(record["clips"]["Wave"]["joints"]), 8)
        result = json.loads((folder / "compare" / "compare.json").read_text(encoding="utf-8"))
        self.assertTrue(result["Wave"]["match"], result)
        self.assertTrue((folder / "compare" / "Wave.png").is_file())


if __name__ == "__main__":
    unittest.main()
