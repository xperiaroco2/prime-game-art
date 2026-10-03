"""The animation commands' helpers (tools/runner/commands/_anim.py), the review settings and the command wiring; no
Blender needed."""

from __future__ import annotations

import argparse
import json
import shutil
import unittest

from runner import cli, common
from runner.commands import _anim

OUT = common.OUT / "tests" / "anim"


def measures(source: str, clip: str, loop: bool) -> dict:
    return {
        "source": source, "clip": clip, "seconds": 1.333, "loop": loop,
        "foot_sliding": {"slide_mean_cm_s": 5.5, "slide_max_cm_s": 55.3},
        "lowest_vertex_cm": {"min": -0.4}, "hands_in_torso": {"max_depth_cm": 1.2, "frames_over_1cm": 3},
        "loop_seam": {"seam_deg": 0.0, "seam_ratio": 0.0},
        "hyperextension_deg": {"knee.L": 0.0, "knee.R": 2.5, "elbow.L": 0.0, "elbow.R": 0.0},
        "forearm_twist_deg": {"L": 12.0, "R": 30.5},
        "finger_curl_deg": {"L": {"min": 10.0, "max": 20.0}, "R": {"min": 5.0, "max": 25.0}},
        "root_motion": {"ground_speed_m_s": 0.98},
    }


class HelperTest(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(OUT, ignore_errors=True)
        (OUT / "metrics").mkdir(parents=True)

    def test_chunks_cover_every_clip_once_and_balance_the_load(self) -> None:
        keys = [f"pack:c{i}" for i in range(10)] + [f"ual:u{i}" for i in range(9)]
        seconds = {k: (5.0 if k == "ual:u0" else 1.0) for k in keys}
        parts = _anim.chunks(keys, 4, seconds)
        self.assertEqual(len(parts), 4)
        self.assertEqual(sorted(k for p in parts for k in p), sorted(keys))
        heavy = next(p for p in parts if "ual:u0" in p)
        self.assertLessEqual(len(heavy), min(len(p) for p in parts if p is not heavy))
        self.assertEqual(_anim.chunks(keys[:2], 8), [[keys[0]], [keys[1]]])

    def test_clip_keys_come_from_the_inventory(self) -> None:
        inv = {"pack": {"men": {"actions": {"Walk": {"seconds": 1.3}, "Idle": {"seconds": 1.7}}}},
               "ual": {"ual": {"clips": {"Walk_Loop": {"seconds": 1.3}}}}}
        self.assertEqual(_anim.clip_keys(inv, "men"), ["pack:Idle", "pack:Walk", "ual:Walk_Loop"])
        self.assertEqual(_anim.clip_seconds(inv, "men")["ual:Walk_Loop"], 1.3)

    def test_merge_and_table(self) -> None:
        (OUT / "metrics" / "men_c0.json").write_text(json.dumps({"pack:Walk": measures("pack", "Walk", True)}))
        (OUT / "metrics" / "men_c1.json").write_text(json.dumps({"ual:Death01": measures("ual", "Death01", False)}))
        merged = _anim.merge(OUT / "metrics")
        self.assertEqual(sorted(merged["men"]), ["pack:Walk", "ual:Death01"])
        text = _anim.table(merged, {"men:pack:Walk": "good"})
        lines = text.splitlines()
        self.assertEqual(len(lines), 4)
        self.assertIn("| men | pack | Walk | 1.33 | yes | 0.98 | 5.5 / 55.3 | -0.4 | 1.2 (3) | 0.0 (x0.0) | 2.5 / 0.0 "
                      "| 30.5 | 5.0-25.0 | good |", text)
        self.assertTrue(all(line.count("|") == lines[0].count("|") for line in lines))

    def test_the_review_settings_load(self) -> None:
        cfg = _anim.load_config()
        self.assertEqual(set(cfg["bodies"]), {"men", "women"})
        self.assertTrue(cfg["ual"].endswith("UAL1_Standard.glb"))
        for pair in cfg["pairs"]:
            self.assertTrue(pair["pack"] and pair["ual"])
        self.assertIn("Walk", cfg["loops"]["pack"])

    def test_broken_settings_are_refused(self) -> None:
        path = OUT / "broken.toml"
        path.write_text('ual = "x"\n', encoding="utf-8")
        with self.assertRaises(common.Failure) as ctx:
            _anim.load_config(path)
        self.assertIn("bodies", str(ctx.exception))


class CommandTest(unittest.TestCase):
    def test_the_commands_are_discovered_with_their_options(self) -> None:
        modules = cli.discover()
        for name in ("retarget", "anim-review"):
            self.assertIn(name, modules)
        parser = argparse.ArgumentParser()
        modules["anim-review"].add_arguments(parser)
        args = parser.parse_args(["clips", "--body", "women", "--jobs", "2", "--no-video"])
        self.assertEqual((args.step, args.body, args.jobs, args.no_video), ("clips", "women", 2, True))
        parser = argparse.ArgumentParser()
        modules["retarget"].add_arguments(parser)
        args = parser.parse_args(["--body", "men", "--clips", "Walk_Loop", "--blend"])
        self.assertEqual((args.body, args.clips, args.blend, args.no_ik), ("men", "Walk_Loop", True, False))

    def test_jobs_below_one_are_refused(self) -> None:
        parser = argparse.ArgumentParser()
        cli.discover()["anim-review"].add_arguments(parser)
        args = parser.parse_args(["table", "--jobs", "0", "--out", str(OUT)])
        with self.assertRaises(common.Failure):
            cli.discover()["anim-review"].run(args)


if __name__ == "__main__":
    unittest.main()
