"""UAL2 as one more source of the animation review (art #24): the clip keys (tools/blender/anim_keys.py), the review
settings' libraries, layer, pairs and rates, the clip list and measures merge per source, and the commands' options;
no Blender needed."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import unittest

from runner import cli, common
from runner.commands import _anim

sys.path.insert(0, str(common.ROOT / "tools" / "blender"))
import anim_keys  # noqa: E402

OUT = common.OUT / "tests" / "anim_ual2"


class KeysTest(unittest.TestCase):
    def test_plain_layered_and_blended_keys(self) -> None:
        self.assertEqual(anim_keys.split("ual2:Walk_Carry_Loop"), ("ual2", "Walk_Carry_Loop"))
        self.assertEqual(anim_keys.needs("ual:Idle_Loop|ual2:Walk_Carry_Loop"), ["ual:Idle_Loop", "ual2:Walk_Carry_Loop"])
        self.assertEqual(anim_keys.needs("blend:Walk_Loop+Jog_Fwd_Loop|ual2:Walk_Carry_Loop"),
                         ["ual:Walk_Loop", "ual:Jog_Fwd_Loop", "ual2:Walk_Carry_Loop"])
        self.assertEqual(anim_keys.needs("blend:ual2:Walk_Carry_Loop+Walk_Loop"),
                         ["ual2:Walk_Carry_Loop", "ual:Walk_Loop"])
        self.assertEqual(anim_keys.sources_of("blend:Walk_Loop+Jog_Fwd_Loop|ual2:Walk_Carry_Loop"), {"ual", "ual2"})
        self.assertEqual(anim_keys.layer("pack:Walk"), ("pack:Walk", None))

    def test_bad_keys_are_refused(self) -> None:
        for bad in ("Walk", "ual2:", ":Walk", "ual:A|", "ual:A|ual2:B|ual2:C", "blend:A", "blend:A+B+C", "ual:A+B"):
            with self.subTest(key=bad), self.assertRaises(ValueError):
                anim_keys.needs(bad)

    def test_rows_are_selected_by_source(self) -> None:
        row = ["blend:Walk_Loop+Jog_Fwd_Loop|ual2:Walk_Carry_Loop", "blend:Walk_Loop+Jog_Fwd_Loop"]
        self.assertTrue(anim_keys.selected(row, {"ual2"}))
        self.assertFalse(anim_keys.selected(row, {"pack"}))
        self.assertTrue(anim_keys.selected(row, None))
        self.assertIsNone(anim_keys.parse_sources("all", {"pack", "ual"}))
        self.assertEqual(anim_keys.parse_sources("ual2,pack", {"pack", "ual", "ual2"}), {"ual2", "pack"})
        with self.assertRaises(ValueError):
            anim_keys.parse_sources("ual3", {"pack", "ual", "ual2"})

    def test_a_rates_run_over_some_sources_keeps_the_other_rows(self) -> None:
        old = {"body": "men", "natural_speed_m_s": {"ual:Jog_Fwd_Loop": 5.5},
               "rows": {"walk_4.5": {"lanes": [1]}, "carry_4.5": {"lanes": ["old"]}}}
        new = {"body": "men", "natural_speed_m_s": {"ual2:Walk_Carry_Loop": 0.67},
               "rows": {"carry_4.5": {"lanes": ["new"]}}}
        merged = anim_keys.merge_rates(old, new)
        self.assertEqual(merged["rows"], {"walk_4.5": {"lanes": [1]}, "carry_4.5": {"lanes": ["new"]}})
        self.assertEqual(merged["natural_speed_m_s"], {"ual:Jog_Fwd_Loop": 5.5, "ual2:Walk_Carry_Loop": 0.67})
        self.assertIs(anim_keys.merge_rates(None, new), new)

    def test_both_pair_forms(self) -> None:
        cfg = {"pairs": [{"pack": "Wave", "ual": ["Idle_Talking_Loop"]},
                         {"name": "carry", "clips": ["ual2:Walk_Carry_Loop", "ual:Idle_Loop|ual2:Walk_Carry_Loop"]}]}
        self.assertEqual(anim_keys.pairs(cfg), [
            {"name": "Wave", "clips": ["pack:Wave", "ual:Idle_Talking_Loop"]},
            {"name": "carry", "clips": ["ual2:Walk_Carry_Loop", "ual:Idle_Loop|ual2:Walk_Carry_Loop"]}])
        for bad in ({"pairs": [{"name": "x", "clips": ["Walk"]}]}, {"pairs": [{"name": "x", "clips": []}]},
                    {"pairs": [{"pack": "Wave"}]}, {"pairs": [{"pack": "Wave", "ual": ["A"], "clips": ["ual:A"]}]},
                    {"pairs": [{"name": "x", "clips": ["ual:A"]}, {"name": "x", "clips": ["ual:B"]}]}):
            with self.subTest(cfg=bad), self.assertRaises(ValueError):
                anim_keys.pairs(bad)


class SettingsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = _anim.load_config()

    def test_ual2_is_one_more_library(self) -> None:
        libs = _anim.libraries(self.cfg)
        self.assertEqual(list(libs)[:2], ["ual", "ual2"])  # Meshy's follow (art #25)
        self.assertTrue(libs["ual"]["file"].endswith("UAL1_Standard.glb"))
        self.assertTrue(libs["ual2"]["file"].endswith("UAL2_Standard.glb"))
        self.assertTrue(libs["ual2"]["rm"].endswith("UAL2_Standard_RM.glb"))
        self.assertEqual(libs["ual2"]["label"], "UAL2")
        self.assertLessEqual({"pack", "ual", "ual2"}, _anim.sources(self.cfg))
        self.assertEqual(self.cfg["layer"]["upper"], "Torso")

    def test_every_pair_and_rates_lane_parses_and_names_known_sources(self) -> None:
        known = _anim.sources(self.cfg)
        pairs = anim_keys.pairs(self.cfg)
        self.assertEqual(sum(p["name"] == "Wave" for p in pairs), 1)  # art #20's pairs keep their names
        for p in pairs:
            for k in p["clips"]:
                self.assertLessEqual(anim_keys.sources_of(k), known, k)
        ual2 = [p for p in pairs if anim_keys.selected(p["clips"], {"ual2"})]
        self.assertGreaterEqual(len(ual2), 5)
        for row in self.cfg["rates"]:
            for lane in row["clips"]:
                self.assertLessEqual(anim_keys.sources_of(lane), known, lane)
        carry = next(r for r in self.cfg["rates"] if r["name"] == "carry_4.5")
        self.assertEqual(carry["speed"], 4.5)

    def test_a_library_with_a_reserved_name_is_refused(self) -> None:
        OUT.mkdir(parents=True, exist_ok=True)
        path = OUT / "bad_library.toml"
        text = (common.ROOT / "tools" / "blender" / "anim_review.toml").read_text(encoding="utf-8")
        for name in ("pack", "ual", "layer", "ual2_rm"):  # "<key>_rm" names a library's root-motion file
            path.write_text(text.replace("[libraries.ual2]", f"[libraries.{name}]"), encoding="utf-8")
            with self.subTest(name=name), self.assertRaises(common.Failure):
                _anim.load_config(path)


class ClipListTest(unittest.TestCase):
    INV = {"libraries": ["ual", "ual2"],
           "pack": {"men": {"actions": {"Walk": {"seconds": 1.3}}}},
           "ual": {"ual": {"clips": {"Walk_Loop": {"seconds": 1.3}}}, "ual_rm": {"clips": {}},
                   "ual2": {"clips": {"Walk_Carry_Loop": {"seconds": 2.0}, "Yes": {"seconds": 2.5}}},
                   "ual2_rm": {"clips": {}}}}

    def test_clip_keys_per_source(self) -> None:
        self.assertEqual(_anim.clip_keys(self.INV, "men"),
                         ["pack:Walk", "ual:Walk_Loop", "ual2:Walk_Carry_Loop", "ual2:Yes"])
        self.assertEqual(_anim.clip_keys(self.INV, "men", {"ual2"}), ["ual2:Walk_Carry_Loop", "ual2:Yes"])
        self.assertEqual(_anim.clip_seconds(self.INV, "men")["ual2:Yes"], 2.5)
        old = {k: v for k, v in self.INV.items() if k != "libraries"}  # an inventory of art #20: UAL1 alone
        self.assertEqual(_anim.clip_keys(old, "men"), ["pack:Walk", "ual:Walk_Loop"])

    def test_layered_clips_join_full_and_source_runs(self) -> None:
        cfg = {"layer": {"upper": "Torso", "clips": ["ual:Idle_Loop|ual2:Walk_Carry_Loop"]}}
        self.assertEqual(_anim.layered_keys(cfg), ["ual:Idle_Loop|ual2:Walk_Carry_Loop"])
        self.assertEqual(_anim.layered_keys(cfg, {"ual2"}), ["ual:Idle_Loop|ual2:Walk_Carry_Loop"])
        self.assertEqual(_anim.layered_keys(cfg, {"pack"}), [])
        self.assertEqual(_anim.layered_keys({}), [])
        for bad in ("ual:Idle_Loop", "ual:A|ual2:B|ual2:C", "ual:A|B", "ual:A|:B"):
            with self.subTest(key=bad), self.assertRaises(common.Failure):
                _anim.layered_keys({"layer": {"clips": [bad]}})
        real = _anim.load_config()
        self.assertIn("ual:Idle_Loop|ual2:Walk_Carry_Loop", _anim.layered_keys(real, {"ual2"}))
        for key in _anim.layered_keys(real):
            self.assertEqual(len(anim_keys.needs(key)), 2, key)

    def test_measures_merge_full_then_source_then_partial_runs(self) -> None:
        shutil.rmtree(OUT / "metrics", ignore_errors=True)
        (OUT / "metrics").mkdir(parents=True)
        self.assertEqual(_anim.run_tag(None), "_c")
        self.assertEqual(_anim.run_tag({"ual2", "pack"}), "_spack+ual2_c")
        files = {"men_c0": {"ual2:Yes": 1, "pack:Walk": 1}, "men_sual2_c0": {"ual2:Yes": 2, "ual2:Walk_Carry_Loop": 2},
                 "men_part_c0": {"ual2:Walk_Carry_Loop": 3}, "women_c0": {"ual2:Yes": 4}}
        for stem, data in files.items():
            (OUT / "metrics" / f"{stem}.json").write_text(json.dumps(data), encoding="utf-8")
        merged = _anim.merge(OUT / "metrics")
        self.assertEqual(merged["men"], {"ual2:Yes": 2, "pack:Walk": 1, "ual2:Walk_Carry_Loop": 3})
        self.assertEqual(merged["women"], {"ual2:Yes": 4})

    def test_of_two_overlapping_source_runs_the_later_wins(self) -> None:
        shutil.rmtree(OUT / "metrics", ignore_errors=True)
        (OUT / "metrics").mkdir(parents=True)
        # "men_sual+ual2" sorts before "men_sual2" by name ('+' < '2'), yet it ran later
        older, newer = OUT / "metrics" / "men_sual2_c0.json", OUT / "metrics" / "men_sual+ual2_c0.json"
        older.write_text(json.dumps({"ual2:Yes": "old"}), encoding="utf-8")
        newer.write_text(json.dumps({"ual2:Yes": "new", "ual:Walk_Loop": "new"}), encoding="utf-8")
        os.utime(older, ns=(1_000_000_000, 1_000_000_000))
        os.utime(newer, ns=(2_000_000_000, 2_000_000_000))
        self.assertEqual(_anim.merge(OUT / "metrics")["men"], {"ual2:Yes": "new", "ual:Walk_Loop": "new"})
        os.utime(older, ns=(3_000_000_000, 3_000_000_000))  # the ual2 run again, after the other one
        self.assertEqual(_anim.merge(OUT / "metrics")["men"], {"ual2:Yes": "old", "ual:Walk_Loop": "new"})


class CommandTest(unittest.TestCase):
    def test_the_new_options(self) -> None:
        modules = cli.discover()
        parser = argparse.ArgumentParser()
        modules["anim-review"].add_arguments(parser)
        args = parser.parse_args(["clips", "--sources", "ual2", "--out", str(OUT)])
        self.assertEqual(args.sources, "ual2")
        parser = argparse.ArgumentParser()
        modules["retarget"].add_arguments(parser)
        self.assertEqual(parser.parse_args(["--library", "ual2"]).library, "ual2")
        self.assertEqual(parser.parse_args([]).library, "ual")

    def test_unknown_sources_and_libraries_are_refused(self) -> None:
        modules = cli.discover()
        parser = argparse.ArgumentParser()
        modules["anim-review"].add_arguments(parser)
        with self.assertRaises(common.Failure):
            modules["anim-review"].run(parser.parse_args(["table", "--sources", "ual3", "--out", str(OUT)]))
        with self.assertRaisesRegex(common.Failure, "not both"):  # --sources beside --clips would be ignored
            modules["anim-review"].run(parser.parse_args(
                ["table", "--clips", "ual2:Yes", "--sources", "ual2", "--out", str(OUT)]))
        parser = argparse.ArgumentParser()
        modules["retarget"].add_arguments(parser)
        with self.assertRaises(common.Failure):
            modules["retarget"].run(parser.parse_args(["--library", "ual3", "--out", str(OUT)]))


if __name__ == "__main__":
    unittest.main()
