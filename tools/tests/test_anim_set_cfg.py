"""An animation set's settings (tools/blender/anim_set_cfg.py, art #33): the MVP set parses and passes, and every
rule of a set refuses what breaks it. Pure Python; no Blender needed."""

from __future__ import annotations

import copy
import sys
import unittest

from runner import common
from runner.commands import _anim, _anim_set

sys.path.insert(0, str(common.ROOT / "tools" / "blender"))
import anim_set_cfg as asc  # noqa: E402

SOURCES = {"pack", "ual", "ual2", "tm"}


def small() -> dict:
    return {"title": "t", "fps": 30, "stem": "s", "upper": "Torso", "clips": [
        {"name": "Jog_Fwd_Loop", "source": "ual:Jog_Fwd_Loop", "loop": True, "speed_m_s": 4.5,
         "edits": [{"op": "stride", "speed_m_s": 4.5, "cadence": 2.8}],
         "needs": [{"need": "walk", "no": 2, "layer": "full", "speed_m_s": 4.5, "rate": 1.0},
                   {"need": "sprint", "no": 6, "speed_m_s": 7.0, "rate": 1.556}]},
        {"name": "Jog_Bwd_Loop", "from": "Jog_Fwd_Loop", "loop": True, "edits": [{"op": "reverse"}]},
        {"name": "Knife_Swing", "source": "pack:Sword_Slash", "loop": False, "export": False,
         "edits": [{"op": "retime", "seconds": 0.45}], "needs": [{"need": "knife", "layer": "upper"}]},
    ]}


def errors(cfg: dict) -> list[str]:
    return asc.check(cfg, SOURCES)


class MvpSetTest(unittest.TestCase):
    def test_the_mvp_set_passes(self) -> None:
        cfg = _anim.load_config()
        path, data = _anim_set.load(cfg, "mvp")
        self.assertEqual(path.name, "mvp.toml")
        self.assertEqual(asc.check(data, _anim.sources(cfg) - set(cfg["sets"])), [])
        names = [c["name"] for c in data["clips"]]
        for need in ("Idle_Loop", "Jog_Fwd_Loop", "Jog_Bwd_Loop", "Strafe_Left_Loop", "Strafe_Right_Loop",
                     "Sprint_Fwd_Loop", "Turn_Left", "Turn_Right", "Jump_Start", "Jump_Air_Loop", "Jump_Land",
                     "Shove_Stumble", "Push_Upper_Loop", "Knife_Swing", "Carry_Upper_Loop", "Pickup_One",
                     "Putdown_One", "Pickup_Package", "Putdown_Package", "Knockdown", "Crawl_Loop", "Getup_Back",
                     "Raise_In", "Raise_Work_Loop", "Raise_Out", "Talk_Upper_Loop"):
            self.assertIn(need, names)
        self.assertEqual(data["upper"], "Torso")
        layers = {n["layer"] for c in data["clips"] for n in c.get("needs", [])}
        self.assertEqual(layers, {"full", "upper"})

    def test_the_set_is_a_source_of_the_review(self) -> None:
        cfg = _anim.load_config()
        self.assertIn("mvp", _anim.sources(cfg))
        keys = _anim.set_keys(cfg)
        self.assertIn("mvp:Jog_Fwd_Loop", keys)
        self.assertEqual(_anim.set_keys(cfg, {"ual"}), [])

    def test_an_unknown_set_is_refused(self) -> None:
        with self.assertRaises(common.Failure):
            _anim_set.load(_anim.load_config(), "nope")


class RulesTest(unittest.TestCase):
    def test_a_good_set_passes(self) -> None:
        self.assertEqual(errors(small()), [])

    def test_names_must_be_unique_and_plain(self) -> None:
        cfg = small()
        cfg["clips"][2]["name"] = "Jog_Fwd_Loop"
        self.assertTrue(any("second clip named Jog_Fwd_Loop" in e for e in errors(cfg)))
        cfg = small()
        cfg["clips"][2]["name"] = "Knife Swing"
        self.assertTrue(any("must match" in e for e in errors(cfg)))

    def test_a_loop_ends_in_loop_and_only_a_loop(self) -> None:
        cfg = small()
        cfg["clips"][0]["loop"] = False
        self.assertTrue(any("ends in _Loop exactly when" in e for e in errors(cfg)))
        cfg = small()
        cfg["clips"][2]["loop"] = True
        self.assertTrue(any("ends in _Loop exactly when" in e for e in errors(cfg)))

    def test_one_source_or_an_earlier_clip(self) -> None:
        cfg = small()
        cfg["clips"][1]["source"] = "ual:Idle_Loop"
        self.assertTrue(any("one of them" in e for e in errors(cfg)))
        cfg = small()
        cfg["clips"][1]["from"] = "Knife_Swing"  # a later clip
        self.assertTrue(any("names no earlier clip" in e for e in errors(cfg)))
        cfg = small()
        cfg["clips"][0]["source"] = "nope:Jog"
        self.assertTrue(any("no source 'nope'" in e for e in errors(cfg)))
        cfg["clips"][0]["source"] = "blend:Walk_Loop+Jog_Fwd_Loop"
        self.assertTrue(any("not one clip" in e for e in errors(cfg)))
        cfg["clips"][0]["source"] = "Jog_Fwd_Loop"
        self.assertTrue(any("not a clip key" in e for e in errors(cfg)))

    def test_the_edits_are_checked_by_the_edit_schema(self) -> None:
        cfg = small()
        cfg["clips"][0]["edits"] = [{"op": "stride", "cadence": 2.8}, {"op": "wobble"}]
        found = errors(cfg)
        self.assertTrue(any("speed_m_s" in e for e in found), found)
        self.assertTrue(any("wobble" in e for e in found), found)
        cfg["clips"][0]["edits"] = [{"op": "retime", "seconds": 1.0, "body": "kids"}]
        self.assertTrue(any("kids" in e for e in errors(cfg)))

    def test_needs_have_a_layer_a_rate_and_a_consistent_speed(self) -> None:
        cfg = small()
        cfg["clips"][2]["needs"][0]["layer"] = "lower"
        self.assertTrue(any("layer 'lower'" in e for e in errors(cfg)))
        cfg = small()
        cfg["clips"][0]["needs"][1]["rate"] = 0
        self.assertTrue(any("rate must be a number > 0" in e for e in errors(cfg)))
        cfg = small()
        cfg["clips"][0]["needs"][1]["rate"] = 1.3  # 4.5 x 1.3 is not 7.0
        self.assertTrue(any("is not the clip's 4.5 m/s at rate 1.3" in e for e in errors(cfg)))
        cfg = small()
        cfg["clips"][0]["needs"][0]["speed_m_s"] = -1
        self.assertTrue(any("speed_m_s must be a number >= 0" in e for e in errors(cfg)))
        cfg = small()
        del cfg["clips"][2]["needs"][0]["need"]
        self.assertTrue(any("need (the game's need" in e for e in errors(cfg)))

    def test_the_set_itself(self) -> None:
        cfg = small()
        cfg["fps"] = 24
        cfg["colour"] = "red"
        found = errors(cfg)
        self.assertTrue(any("fps 24" in e for e in found))
        self.assertTrue(any("unknown keys ['colour']" in e for e in found))
        self.assertEqual(errors({"title": "t"}), ["no [[clips]]"])


class SelectionTest(unittest.TestCase):
    def test_a_clip_brings_the_clips_it_is_made_from(self) -> None:
        cfg = small()
        self.assertEqual(asc.closure(cfg, ["Jog_Bwd_Loop"]), ["Jog_Fwd_Loop", "Jog_Bwd_Loop"])
        self.assertEqual(asc.closure(cfg, "all"), ["Jog_Fwd_Loop", "Jog_Bwd_Loop", "Knife_Swing"])
        self.assertEqual(asc.sources(cfg, ["Jog_Bwd_Loop"]), ["ual:Jog_Fwd_Loop"])
        with self.assertRaises(ValueError):
            asc.closure(cfg, ["Nope"])
        with self.assertRaises(common.Failure):
            _anim_set.selected(cfg, "Nope")

    def test_exported_clips_and_speeds(self) -> None:
        cfg = small()
        self.assertEqual(asc.exported(cfg), ["Jog_Fwd_Loop", "Jog_Bwd_Loop"])
        table = asc.clips(cfg)
        self.assertEqual(asc.speed_of(table["Jog_Fwd_Loop"]), 4.5)
        self.assertIsNone(asc.speed_of(table["Knife_Swing"]))
        no_speed = copy.deepcopy(table["Jog_Fwd_Loop"])
        del no_speed["speed_m_s"]
        no_speed["needs"] = [{"need": "x", "speed_m_s": 7.0, "rate": 1.4}]
        self.assertAlmostEqual(asc.speed_of(no_speed), 5.0)


if __name__ == "__main__":
    unittest.main()
