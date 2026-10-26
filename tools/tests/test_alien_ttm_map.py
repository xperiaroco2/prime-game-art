"""The text-to-motion map onto the contract skeleton (tools/blender/retarget_maps/smpl_contract.toml, art #196 option A
step 2): it loads, names only contract bones, covers every one of them, its legs are whole FK chains of the contract
and it reads the same SMPL-H rig as the Ultimate Modular map. No Blender."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
import retarget_map  # noqa: E402

MAP = retarget_map.MAPS / "smpl_contract.toml"


def contract() -> dict:
    data = json.loads((ROOT / "contract" / "humanoid.json").read_text(encoding="utf-8"))
    return {b["name"]: b["parent"] or None for b in data["bones"]}


class SmplContractMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = retarget_map.load(MAP)
        cls.bones = contract()

    def test_target_rig_is_the_contract(self):
        self.assertEqual(self.m["target_bones"], list(self.bones))

    def test_every_named_target_bone_exists(self):
        named = set(self.m["bones"].values()) | set(self.m["rest"]) | set(self.m["follow"]) | set(
            self.m["follow"].values()) | set(self.m["height"]["target"]) | {self.m["hips"][1]}
        for leg in self.m["legs"]:
            named |= set(leg["target"])
        self.assertEqual(sorted(named - set(self.bones)), [])

    def test_every_contract_bone_is_mapped_or_at_rest(self):
        self.assertEqual(sorted(set(self.bones) - set(self.m["bones"].values()) - set(self.m["rest"])), [])
        self.assertEqual(self.m["rest"], ["Root", "Jaw", "LeftEye", "RightEye"])

    def test_legs_are_whole_fk_chains(self):
        self.assertEqual(len(self.m["legs"]), 2)
        inv = {t: s for s, t in self.m["bones"].items()}
        for leg, side, s in zip(self.m["legs"], ("Left", "Right"), ("L", "R")):
            upper, lower, foot = leg["target"]
            self.assertEqual(leg["target"], [f"{side}UpperLeg", f"{side}LowerLeg", f"{side}Foot"])
            self.assertEqual(self.bones[upper], "Hips")
            self.assertEqual(self.bones[lower], upper)
            self.assertEqual(self.bones[foot], lower)  # FK: the foot hangs from the lower leg, no IK target
            self.assertEqual(self.m["follow"][foot], self.bones[foot])  # [follow] names its own parent
            self.assertEqual(self.bones[f"{side}Toes"], foot)
            self.assertEqual(leg["source_foot"], f"{s}_Ankle")
            self.assertEqual([inv[b] for b in leg["target"] + [f"{side}Toes"]],
                             [f"{s}_Hip", f"{s}_Knee", f"{s}_Ankle", f"{s}_Foot"])

    def test_sides_and_fingers_pair_up(self):
        for s, t in self.m["bones"].items():
            if s[:2] in ("L_", "R_"):
                self.assertTrue(t.startswith("Left" if s[0] == "L" else "Right"), (s, t))
        self.assertEqual(self.m["bones"]["L_Pinky3"], "LeftLittleDistal")
        self.assertEqual(self.m["bones"]["R_Thumb1"], "RightThumbMetacarpal")

    def test_same_source_rig_as_the_um_map(self):
        um = retarget_map.load(retarget_map.MAPS / "smpl_um.toml")
        self.assertEqual(self.m["source_bones"], um["source_bones"])
        self.assertEqual(self.m["hips"], ("Pelvis", "Hips"))
        self.assertIsNone(self.m["root"])


if __name__ == "__main__":
    unittest.main()
