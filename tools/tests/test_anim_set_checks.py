"""The anim-set command's own checks (tools/runner/commands/_anim_set.py, art #33) on built, exported and imported
sets. Pure Python; no Blender or Godot needed."""

from __future__ import annotations

import copy
import unittest

from runner.commands import _anim_set


def report() -> dict:
    def clip(frames, loop, export=True, travel=0.0, steps=None, low=-0.4):
        return {"source": "ual:x", "from": None, "export": export, "loop": loop, "frames": frames,
                "seconds": round(frames / 30, 3), "speed_m_s": None, "travel_left_m": travel, "yaw_drift_deg": 0.0,
                "steps": steps or [], "lowest_cm": low, "lowest_at_s": 0.5}
    return {"exported": ["Jog_Fwd_Loop", "Knockdown"], "clips": {
        "Jog_Fwd_Loop": clip(21, True, steps=[{"op": "stride", "fit": "warn", "scale": 0.57, "cadence": 2.86,
                                               "step_m": 1.575}]),
        "Knockdown": clip(40, False, travel=0.4, low=-0.2),
        "Strafe_Left_Loop": {**clip(24, True), "speed_m_s": 4.5, "facing_mean_deg": 20.4, "head_facing_mean_deg": -17.7,
                             "seam_step_ratio": 2.1},
        "Jog_Bwd_TTM_Loop": clip(21, True, export=False, steps=[{"op": "stride", "fit": "fail", "scale": 8.1,
                                                                 "cadence": 2.8, "step_m": 1.6}], low=-2.5),
    }}


def data() -> dict:
    return {"clips": [{"name": "Jog_Fwd_Loop", "source": "ual:x", "loop": True},
                      {"name": "Knockdown", "source": "ual:x", "loop": False},
                      {"name": "Jog_Bwd_TTM_Loop", "source": "ual:x", "loop": True, "export": False}]}


class SetChecksTest(unittest.TestCase):
    def test_a_good_build_passes(self) -> None:
        self.assertEqual(_anim_set.check_build(report(), data(), ["Jog_Fwd_Loop", "Knockdown", "Jog_Bwd_TTM_Loop"]), [])

    def test_a_travelling_loop_or_a_missing_clip_fails(self) -> None:
        r = report()
        r["clips"]["Jog_Fwd_Loop"]["travel_left_m"] = 0.3
        del r["clips"]["Knockdown"]
        problems = _anim_set.check_build(r, data(), ["Jog_Fwd_Loop", "Knockdown"])
        self.assertTrue(any("travels 0.3 m" in p for p in problems), problems)
        self.assertTrue(any("Knockdown: not built" in p for p in problems), problems)

    def test_the_export_holds_the_exported_clips_closed(self) -> None:
        info = {"fps": 30, "actions": {"Jog_Fwd_Loop": [0, 21], "Knockdown": [0, 40]},
                "seams": {"Jog_Fwd_Loop": {"position_mm": 0.01, "rotation_deg": 0.0},
                          "Knockdown": {"position_mm": 300.0, "rotation_deg": 90.0}}}
        self.assertEqual(_anim_set.check_export(info, report()), [])
        bad = copy.deepcopy(info)
        bad["seams"]["Jog_Fwd_Loop"] = {"position_mm": 4.0, "rotation_deg": 2.0}
        bad["actions"]["Extra"] = [0, 10]
        bad["fps"] = 24
        problems = _anim_set.check_export(bad, report())
        self.assertEqual(len(problems), 3, problems)

    def test_godot_loops_exactly_the_loops(self) -> None:
        godot = {"animations": {"Jog_Fwd": {"length": 0.7, "loop_mode": 1}, "Knockdown": {"length": 4 / 3, "loop_mode": 0}}}
        self.assertEqual(_anim_set.check_godot(godot, report()), [])
        godot["animations"]["Knockdown"]["loop_mode"] = 1
        godot["animations"]["Jog_Fwd_Loop"] = godot["animations"].pop("Jog_Fwd")
        problems = _anim_set.check_godot(godot, report())
        self.assertTrue(any("no animation 'Jog_Fwd'" in p for p in problems), problems)
        self.assertTrue(any("Knockdown: imports as Knockdown with loop_mode 1" in p for p in problems), problems)

    def test_warnings_and_table(self) -> None:
        warnings = _anim_set.warnings(report())
        self.assertTrue(any("Jog_Fwd_Loop: stride scale 0.57 (warn)" in w for w in warnings), warnings)
        self.assertTrue(any("Jog_Bwd_TTM_Loop: stride scale 8.1 (fail)" in w for w in warnings), warnings)
        self.assertTrue(any("lowest vertex -2.5 cm" in w for w in warnings), warnings)
        self.assertTrue(any("Strafe_Left_Loop: faces 20.4 degrees (hips) and -17.7 (head)" in w for w in warnings),
                        warnings)
        self.assertTrue(any("Strafe_Left_Loop: its step onto the first frame is 2.1" in w for w in warnings), warnings)
        self.assertFalse(any(w.startswith("Jog_Fwd_Loop: faces") for w in warnings), warnings)
        self.assertEqual(len(_anim_set.table(report()).splitlines()), 6)
        self.assertEqual(_anim_set.summary({"checks": [{"status": "pass"}, {"status": "warn"}]}),
                         {"pass": 1, "warn": 1, "fail": 0})


if __name__ == "__main__":
    unittest.main()
