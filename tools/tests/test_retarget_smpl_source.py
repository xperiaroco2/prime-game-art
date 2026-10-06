"""Meshy text to motion as a source of the retarget and the review (art #33): the settings' [libraries.tm] (one FBX per
clip, `format = "smplh_fbx"`, a `clips` table naming each clip's file), its bone map, its clips covering batch 5's
items and batch 4's crawl, and the settings checks that refuse a bad format or a missing clips table; no Blender
needed."""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from runner import common
from runner.commands import _anim

BATCH = common.ROOT / "batches" / "2026-10-b5-anim-mvp.toml"
TM = """
[libraries.tm2]
format = "smplh_fbx"
file = "a/crawl.fbx"
label = "TTM2"
map = "smpl_um.toml"
in_place = ["crawl"]
[libraries.tm2.clips]
crawl = "a/crawl.fbx"
turn = "b/turn.fbx"
"""


class TextToMotionSourceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = _anim.load_config()
        self.tm = self.cfg["libraries"]["tm"]

    def test_the_library(self) -> None:
        self.assertEqual(self.tm["format"], "smplh_fbx")
        self.assertEqual(self.tm["label"], "TTM")
        self.assertTrue((_anim.MAPS / self.tm["map"]).is_file())
        self.assertNotIn("rm", self.tm)
        self.assertIn(self.tm["file"], self.tm["clips"].values())  # the rig is one of the clips' files
        self.assertIn("tm", _anim.sources(self.cfg))
        self.assertLessEqual(set(self.tm["in_place"]), set(self.tm["clips"]))

    def test_the_clips_are_batch_5s_items_and_the_crawl(self) -> None:
        batch = tomllib.loads(BATCH.read_text(encoding="utf-8"))
        items = {i["id"] for i in batch["items"]}
        self.assertEqual(len(items), 7)
        self.assertEqual(set(self.tm["clips"]), items | {"crawl"})
        for item in items:
            self.assertEqual(self.tm["clips"][item], f"{batch['id']}/{item}/text_to_motion-clip.fbx")
        self.assertEqual(self.tm["clips"]["crawl"], "2026-10-b4-animations/crawl-motion/text_to_motion-clip.fbx")

    def test_every_clip_file_is_checked_before_blender_starts(self) -> None:
        lib = _anim.libraries(self.cfg)["tm"]
        self.assertEqual(lib["rm"], None)
        self.assertEqual(sorted({lib["file"], *lib["extra"]}), sorted(set(self.tm["clips"].values())))
        self.assertNotIn(lib["file"], lib["extra"])

    def write(self, tmp: str, extra: str) -> Path:
        path = Path(tmp) / "anim_review.toml"
        path.write_text(_anim.CONFIG.read_text(encoding="utf-8") + extra, encoding="utf-8")
        return path

    def test_the_settings_checks(self) -> None:
        with TemporaryDirectory() as tmp:
            self.assertIn("tm2", _anim.load_config(self.write(tmp, TM))["libraries"])
            bad = {
                "a bad format": TM.replace('format = "smplh_fbx"', 'format = "bvh"'),
                "no clips table": TM.split("[libraries.tm2.clips]")[0],
                "no format": TM.replace('format = "smplh_fbx"\n', ""),  # a GLB library with clips
                "a clip file that is no FBX": TM.replace('"b/turn.fbx"', '"b/turn.glb"'),
                "an absolute clip path": TM.replace('"b/turn.fbx"', '"D:/b/turn.fbx"'),
                "no map": TM.replace('map = "smpl_um.toml"\n', ""),
                "an extra file": TM.replace('label = "TTM2"', 'label = "TTM2"\nextra = ["c.fbx"]'),
                "in place names an unknown clip": TM.replace('in_place = ["crawl"]', 'in_place = ["walk"]'),
            }
            for why, text in bad.items():
                with self.subTest(why), self.assertRaises(common.Failure):
                    _anim.load_config(self.write(tmp, text))


if __name__ == "__main__":
    unittest.main()
