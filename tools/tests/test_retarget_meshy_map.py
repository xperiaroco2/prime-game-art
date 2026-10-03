"""Meshy's bone maps (art #25: tools/blender/retarget_maps/meshy_um*.toml), maps without a root bone and rest
alignment in the map checker, and the review's clip-key variants ("meshy_own:", "ual_rigid:"); no Blender needed."""

from __future__ import annotations

import copy
import sys
import tomllib
import unittest

from runner import common
from runner.commands import _anim

sys.path.insert(0, str(common.ROOT / "tools" / "blender"))
import anim_keys  # noqa: E402
import retarget_map  # noqa: E402

MESHY = retarget_map.MAPS / "meshy_um.toml"
RIGID = retarget_map.MAPS / "meshy_um_rigid.toml"
RAW = tomllib.loads(MESHY.read_text(encoding="utf-8"))


class MeshyMapTest(unittest.TestCase):
    def setUp(self) -> None:
        self.m = retarget_map.load(MESHY)
        self.rigid = retarget_map.load(RIGID)

    def test_meshys_rig_as_read_from_the_files(self) -> None:
        self.assertEqual(len(self.m["source_bones"]), 24)
        self.assertEqual(self.m["source_bones"][0], "Hips")
        self.assertIn("LeftToeBase", self.m["source_bones"])
        self.assertFalse([b for b in self.m["source_bones"] if any(f in b for f in ("Thumb", "Index", "Pinky"))])
        self.assertEqual(sorted(self.m["target_bones"]), sorted(retarget_map.load()["target_bones"]))

    def test_no_root_the_hips_carry_the_travel(self) -> None:
        self.assertIsNone(self.m["root"])
        self.assertEqual(self.m["hips"], ("Hips", "Body"))
        self.assertIn("Root", self.m["rest"])
        self.assertIn("Hips", self.m["rest"])  # our Hips: Body carries the pelvis

    def test_toes_and_fingers(self) -> None:
        self.assertEqual((self.m["bones"]["LeftToeBase"], self.m["bones"]["RightToeBase"]), ("Toe.L", "Toe.R"))
        for side in "LR":
            for bone in (f"Thumb1.{side}", f"Index2.{side}", f"Pinky4.{side}"):
                self.assertIn(bone, self.m["rest"])  # no fingers in the source: a flat hand
        self.assertIn("Toe.L", self.rigid["rest"])
        self.assertIn("LeftToeBase", self.rigid["unused"])
        others = {k: v for k, v in self.m["bones"].items() if not k.endswith("ToeBase")}
        self.assertEqual(self.rigid["bones"], others)

    def test_the_upper_arms_are_aligned_and_the_legs_carry_the_ik(self) -> None:
        self.assertEqual(self.m["align"], ["UpperArm.L", "UpperArm.R"])
        self.assertEqual([leg["source_foot"] for leg in self.m["legs"]], ["LeftFoot", "RightFoot"])
        self.assertEqual(self.m["height"]["source"], ["LeftUpLeg", "RightUpLeg"])

    def test_the_ual_maps_keep_their_root_and_align_nothing(self) -> None:
        ual = retarget_map.load()
        self.assertEqual(ual["root"], ("root", "Root"))
        self.assertEqual(ual["align"], [])

    def test_an_aligned_bone_must_be_mapped(self) -> None:
        bad = copy.deepcopy(RAW)
        bad["align"] = {"bones": ["Index1.L"]}
        with self.assertRaisesRegex(retarget_map.MapError, "must be a mapped target bone"):
            retarget_map.check(bad)

    def test_a_root_pair_given_must_still_be_mapped(self) -> None:
        bad = copy.deepcopy(RAW)
        bad["root"] = ["Hips", "Root"]
        with self.assertRaisesRegex(retarget_map.MapError, "root must be"):
            retarget_map.check(bad)

    def test_the_review_settings_name_these_maps(self) -> None:
        cfg = _anim.load_config()
        for lib in ("meshy", "meshyw"):
            entry = cfg["libraries"][lib]
            self.assertEqual((entry["map"], entry["rigid_map"]), ("meshy_um.toml", "meshy_um_rigid.toml"))
            self.assertNotIn("rm", entry)
            self.assertIn("clip0", entry["skip"])


class VariantKeyTest(unittest.TestCase):
    def test_variants_name_their_library(self) -> None:
        self.assertEqual(anim_keys.base_source("meshy_own"), "meshy")
        self.assertEqual(anim_keys.base_source("ual_rigid"), "ual")
        self.assertEqual(anim_keys.base_source("ual2"), "ual2")
        self.assertEqual(anim_keys.sources_of("meshy_own:Walking|ual2:Walk_Carry_Loop"), {"meshy", "ual2"})
        self.assertTrue(anim_keys.selected(["meshy_own:Walking"], {"meshy"}))

    def test_a_pair_may_keep_to_one_body_type(self) -> None:
        cfg = {"pairs": [{"name": "x", "clips": ["meshy_own:Walking", "ual:Walk_Loop"], "body": "men"}]}
        self.assertEqual(anim_keys.pairs(cfg)[0]["body"], "men")
        cfg["pairs"][0]["colour"] = "red"
        with self.assertRaises(ValueError):
            anim_keys.pairs(cfg)

    def test_every_meshy_row_names_known_sources(self) -> None:
        cfg = _anim.load_config()
        known = _anim.sources(cfg)
        rows = [p["clips"] for p in anim_keys.pairs(cfg) if p["name"].startswith("meshy_")]
        rows += [lanes for r in cfg["feet"] for lanes in r.get("sets", [])]
        self.assertGreaterEqual(len(rows), 20)
        for keys in rows:
            for k in keys:
                self.assertLessEqual(anim_keys.sources_of(k), known, k)


if __name__ == "__main__":
    unittest.main()
