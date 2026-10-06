"""The SMPL-H bone map of Meshy's text-to-motion clips (art #33: tools/blender/retarget_maps/smpl_um.toml): the rig as
read from the files, no root, the IK legs on the ankle joints, the toes on the ball joints, the fingers by anatomy and
no rest alignment; no Blender needed."""

from __future__ import annotations

import sys
import unittest

from runner import common

sys.path.insert(0, str(common.ROOT / "tools" / "blender"))
import retarget_map  # noqa: E402

SMPL = retarget_map.MAPS / "smpl_um.toml"
FINGERS = ("Index", "Middle", "Ring", "Pinky")


class SmplMapTest(unittest.TestCase):
    def setUp(self) -> None:
        self.m = retarget_map.load(SMPL)

    def test_the_rig_as_read_from_the_files(self) -> None:
        self.assertEqual(len(self.m["source_bones"]), 52)
        self.assertEqual(self.m["source_bones"][0], "Pelvis")  # the top bone, in the files' order
        self.assertEqual(len(self.m["target_bones"]), 64)
        self.assertEqual(sorted(self.m["target_bones"]), sorted(retarget_map.load()["target_bones"]))
        self.assertEqual(len(self.m["bones"]), 52)  # every source bone drives one of ours
        self.assertEqual(self.m["unused"], [])

    def test_no_root_the_pelvis_carries_the_travel(self) -> None:
        self.assertIsNone(self.m["root"])
        self.assertEqual(self.m["hips"], ("Pelvis", "Body"))
        self.assertEqual(self.m["height"], {"source": ["L_Hip", "R_Hip"], "target": ["UpperLeg.L", "UpperLeg.R"]})
        self.assertEqual(self.m["align"], [])  # the upper arms rest 2.6 degrees apart

    def test_legs_on_the_ankles_toes_on_the_balls(self) -> None:
        legs = {leg["target"][2]: leg for leg in self.m["legs"]}
        for s, side in (("L", "L"), ("R", "R")):
            self.assertEqual(legs[f"Foot.{side}"]["source_foot"], f"{s}_Ankle")
            self.assertEqual(legs[f"Foot.{side}"]["target"], [f"UpperLeg.{side}", f"LowerLeg.{side}", f"Foot.{side}"])
            self.assertEqual(self.m["bones"][f"{s}_Ankle"], f"Foot.{side}")
            self.assertEqual(self.m["bones"][f"{s}_Foot"], f"Toe.{side}")
            self.assertEqual(self.m["follow"][f"Foot.{side}"], f"LowerLeg.{side}")

    def test_fingers_by_anatomy(self) -> None:
        for s in "LR":
            for f in FINGERS:
                for k in (1, 2, 3):  # SMPL-H's phalanges 1..3 are our 2..4; our metacarpal 1 rests
                    self.assertEqual(self.m["bones"][f"{s}_{f}{k}"], f"{f}{k + 1}.{s}")
                self.assertIn(f"{f}1.{s}", self.m["rest"])
            for k in (1, 2, 3):
                self.assertEqual(self.m["bones"][f"{s}_Thumb{k}"], f"Thumb{k}.{s}")

    def test_what_rests(self) -> None:
        metacarpals = [f"{f}1.{s}" for s in "LR" for f in FINGERS]
        self.assertEqual(sorted(self.m["rest"]), sorted(["Root", "Hips", "PT.L", "PT.R", *metacarpals]))
        self.assertEqual(len(self.m["bones"]) + len(self.m["rest"]), len(self.m["target_bones"]))


if __name__ == "__main__":
    unittest.main()
