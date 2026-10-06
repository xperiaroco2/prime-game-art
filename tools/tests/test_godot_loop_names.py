"""Godot's names for loop clips (_godot.godot_name, art #33): a clip named "<x>_Loop" imports as "<x>" with
LOOP_LINEAR, so godot-check and frames expect the names Godot gives, assert that such clips loop and import an
animation set at its own 30 fps. Pure Python; no Godot needed."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from runner.commands import _frames, _godot

from .test_godot_check import CONTRACT, dump, expect


class GodotNamesTest(unittest.TestCase):
    def test_a_loop_suffix_is_dropped_and_loops(self) -> None:
        self.assertEqual(_godot.godot_name("Idle_Loop"), ("Idle", True))
        self.assertEqual(_godot.godot_name("Jog_Fwd_Loop"), ("Jog_Fwd", True))
        self.assertEqual(_godot.godot_name("Walk-cycle"), ("Walk", True))
        self.assertEqual(_godot.godot_name("Run_loop2"), ("Run2", True))  # trailing digits stay after the cut
        self.assertEqual(_godot.godot_name("Knockdown"), ("Knockdown", False))
        self.assertEqual(_godot.godot_name("CharacterArmature|Walk"), ("CharacterArmature|Walk", False))
        self.assertEqual(_godot.godot_name("Loopy"), ("Loopy", False))

    def test_the_export_fps_is_the_import_fps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            glb = Path(tmp) / "s.glb"
            self.assertEqual(_godot.import_params(glb), {"animation/fps": 24})
            glb.with_name("s.export.json").write_text(json.dumps({"fps": 30}), encoding="utf-8")
            self.assertEqual(_godot.import_params(glb), {"animation/fps": 30})

    def test_expectations_use_godot_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            glb = Path(tmp) / "s.glb"
            info = {"parts": {"a": {}}, "bones": ["Root"], "actions": {"Idle_Loop": [0, 60], "Knockdown": [0, 40]},
                    "fps": 30, "seams": {"Idle_Loop": {"position_mm": 0.0, "rotation_deg": 0.0}}}
            glb.with_name("s.export.json").write_text(json.dumps(info), encoding="utf-8")
            e = _godot.expectations(glb)
        self.assertEqual(e["animations"], {"Idle": 2.0, "Knockdown": 40 / 30})
        self.assertEqual(e["actions"], {"Idle": "Idle_Loop", "Knockdown": "Knockdown"})
        self.assertEqual(e["loop_suffix"], ["Idle"])
        self.assertEqual(list(e["seams"]), ["Idle"])
        self.assertEqual(e["fps"], 30)

    def test_a_loop_named_clip_must_import_looping(self) -> None:
        d = dump()
        e = {**expect(), "loop_suffix": ["CharacterArmature|Walk"]}
        check = next(c for c in _godot.evaluate(d, e, CONTRACT, []) if c["check"] == "loop_suffix")
        self.assertEqual(check["status"], "pass")
        d["players"][0]["animations"]["CharacterArmature|Walk"]["loop_mode"] = 0
        check = next(c for c in _godot.evaluate(d, e, CONTRACT, []) if c["check"] == "loop_suffix")
        self.assertEqual(check["status"], "fail")
        self.assertNotIn("loop_suffix", {c["check"] for c in _godot.evaluate(dump(), expect(), CONTRACT, [])})

    def test_frames_spec_at_the_export_fps_with_named_loops(self) -> None:
        spec = _frames.spec("s", {"Jog_Fwd": 0.7, "Knockdown": 1.333}, [], [], None, 30, {"Jog_Fwd"})
        clips = {c["name"]: c for c in spec["clips"]}
        self.assertEqual(spec["fps"], 30)
        self.assertTrue(clips["Jog_Fwd"]["loop"])
        self.assertEqual(clips["Jog_Fwd"]["cycle_s"], 0.7)
        self.assertEqual(len(clips["Jog_Fwd"]["times"]), 8)
        self.assertFalse(clips["Knockdown"]["loop"])
        self.assertEqual(clips["Knockdown"]["times"][-1], round(40 / 30, 6))


if __name__ == "__main__":
    unittest.main()
