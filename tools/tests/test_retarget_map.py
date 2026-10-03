"""The retarget bone map (tools/blender/retarget_maps/ual_um.toml) and its checker; no Blender needed."""

from __future__ import annotations

import copy
import sys
import tomllib
import unittest

from runner import common

sys.path.insert(0, str(common.ROOT / "tools" / "blender"))
import retarget_map  # noqa: E402

RAW_MAP = tomllib.loads(retarget_map.DEFAULT.read_text(encoding="utf-8"))


class MapFileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.m = retarget_map.load()

    def test_rig_sizes(self) -> None:
        self.assertEqual(len(self.m["source_bones"]), 65)
        self.assertEqual(len(self.m["target_bones"]), 64)  # the pack's 62 and the toe bones (art #25)

    def test_toes_drive_the_toe_bones_and_the_rigid_variant_keeps_them_at_rest(self) -> None:
        self.assertEqual((self.m["bones"]["ball_l"], self.m["bones"]["ball_r"]), ("Toe.L", "Toe.R"))
        rigid = retarget_map.load(retarget_map.MAPS / "ual_um_rigid.toml")
        self.assertNotIn("ball_l", rigid["bones"])
        self.assertIn("Toe.L", rigid["rest"])
        self.assertIn("ball_r", rigid["unused"])
        self.assertEqual(sorted(rigid["target_bones"]), sorted(self.m["target_bones"]))
        others = {k: v for k, v in self.m["bones"].items() if not k.startswith("ball_")}
        self.assertEqual(rigid["bones"], others)  # otherwise the same map

    def test_every_bone_is_accounted_for_once(self) -> None:
        self.assertEqual(sorted(list(self.m["bones"].values()) + self.m["rest"]), sorted(self.m["target_bones"]))
        self.assertEqual(sorted(list(self.m["bones"]) + self.m["unused"]), sorted(self.m["source_bones"]))

    def test_source_names_match_the_contract_bone_map(self) -> None:
        path = common.ROOT / "contract" / "bone_maps" / "quaternius.toml"
        contract = tomllib.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(set(contract["rename"]) | set(contract["drop"]), set(self.m["source_bones"]))

    def test_fingers_skip_the_metacarpals(self) -> None:
        for side, s in (("l", "L"), ("r", "R")):
            for finger, f in (("index", "Index"), ("middle", "Middle"), ("ring", "Ring"), ("pinky", "Pinky")):
                for k in (1, 2, 3):
                    self.assertEqual(self.m["bones"][f"{finger}_0{k}_{side}"], f"{f}{k + 1}.{s}")
                self.assertIn(f"{f}1.{s}", self.m["rest"])
            for k in (1, 2, 3):
                self.assertEqual(self.m["bones"][f"thumb_0{k}_{side}"], f"Thumb{k}.{s}")

    def test_feet_follow_the_lower_legs_and_carry_the_ik(self) -> None:
        self.assertEqual(self.m["follow"], {"Foot.L": "LowerLeg.L", "Foot.R": "LowerLeg.R"})
        self.assertEqual([leg["source_foot"] for leg in self.m["legs"]], ["foot_l", "foot_r"])
        self.assertEqual(self.m["root"], ("root", "Root"))
        self.assertEqual(self.m["hips"], ("pelvis", "Body"))


class CheckerTest(unittest.TestCase):
    def broken(self, change) -> str:
        data = copy.deepcopy(RAW_MAP)
        change(data)
        with self.assertRaises(retarget_map.MapError) as ctx:
            retarget_map.check(data)
        return str(ctx.exception)

    def test_an_unmapped_target_bone_is_refused(self) -> None:
        msg = self.broken(lambda d: d["rest"]["bones"].remove("Hips"))
        self.assertIn("'Hips' is neither mapped nor kept at rest", msg)

    def test_an_unknown_source_bone_is_refused(self) -> None:
        msg = self.broken(lambda d: d["bones"].update({"spine_04": "Hips"}))
        self.assertIn("'spine_04' is not a source rig bone", msg)

    def test_two_sources_on_one_target_are_refused(self) -> None:
        msg = self.broken(lambda d: d["bones"].update({"spine_02": "Abdomen"}))
        self.assertIn("maps two source bones to one target bone", msg)

    def test_a_leg_whose_foot_does_not_follow_is_refused(self) -> None:
        msg = self.broken(lambda d: d["follow"].pop("Foot.L"))
        self.assertIn("must follow the lower leg", msg)

    def test_unknown_keys_and_bad_pairs_are_refused(self) -> None:
        msg = self.broken(lambda d: d.update({"hip": ["pelvis", "Body"], "root": ["root", "Body"]}))
        self.assertIn("unknown keys ['hip']", msg)
        self.assertIn("root must be [source, target]", msg)

    def test_a_missing_file_is_a_map_error(self) -> None:
        with self.assertRaises(retarget_map.MapError):
            retarget_map.load(common.OUT / "no-such-map.toml")


if __name__ == "__main__":
    unittest.main()
