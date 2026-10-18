"""The committed contract agrees with itself and with the generated profile; the bone maps and helpers work.
Pure Python: no Blender, no Godot."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runner import common
from runner.commands import _contract


class ProfileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = _contract.load_profile()

    def test_has_the_56_humanoid_bones(self) -> None:
        parents = _contract.profile_parents(self.profile)
        self.assertEqual(len(parents), 56)
        self.assertEqual(self.profile["root_bone"], "Root")
        self.assertEqual(parents["Hips"], "Root")
        self.assertEqual(parents["LeftThumbMetacarpal"], "LeftHand")

    def test_every_bone_carries_its_data(self) -> None:
        for bone in self.profile["bones"]:
            with self.subTest(bone=bone["name"]):
                self.assertEqual(
                    set(bone),
                    {
                        "index",
                        "name",
                        "parent",
                        "reference_pose",
                        "group",
                        "tail_direction",
                        "tail",
                        "handle_offset",
                        "required",
                    },
                )
                self.assertEqual(set(bone["reference_pose"]), {"basis_x", "basis_y", "basis_z", "origin"})

    def test_five_fingers_of_three_bones_per_hand(self) -> None:
        chains = _contract.finger_chains(self.profile)
        self.assertEqual(len(chains), 10)
        self.assertEqual(chains["LeftThumb"], ["LeftThumbMetacarpal", "LeftThumbProximal", "LeftThumbDistal"])
        self.assertEqual(chains["RightLittle"], ["RightLittleProximal", "RightLittleIntermediate", "RightLittleDistal"])

    def test_format_is_deterministic(self) -> None:
        raw = copy.deepcopy(self.profile)
        raw["bones"].reverse()
        raw["bones"][0]["handle_offset"] = [-0.0, 0.1000000012]
        text = _contract.format_profile(raw)
        self.assertEqual(text, _contract.format_profile(copy.deepcopy(raw)))
        self.assertIn('"handle_offset": [0.0, 0.1]', text)
        self.assertLess(text.index('"name": "Root"'), text.index('"name": "Hips"'))

    def test_committed_file_is_formatted(self) -> None:
        text = _contract.HUMANOID_JSON.read_text(encoding="utf-8")
        self.assertEqual(text, _contract.format_profile(_contract.load_profile()))


class VersionGuardTest(unittest.TestCase):
    def test_only_the_pinned_stable_godot_is_accepted(self) -> None:
        for version, good in (("4.7.2.stable", True), ("4.7.20.stable", False), ("4.7.2.rc1", False)):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "dump.json"

                def fake_run(cmd, timeout, version=version, out=out):
                    out.write_text(json.dumps({"godot_version": version}), encoding="utf-8")
                    return mock.Mock(returncode=0, stdout="", stderr="")

                with mock.patch.object(common, "godot_bin", return_value="godot"), mock.patch.object(
                    common, "run", fake_run
                ):
                    if good:
                        self.assertEqual(_contract.dump_profile(out)["godot_version"], version)
                    else:
                        with self.assertRaises(common.Failure):
                            _contract.dump_profile(out)


class ContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = _contract.load_profile()
        self.contract = _contract.load_contract()

    def test_contract_agrees_with_the_profile(self) -> None:
        self.assertEqual(_contract.validate_contract(self.contract, self.profile), [])

    def test_a_socket_on_an_unknown_bone_is_caught(self) -> None:
        broken = copy.deepcopy(self.contract)
        broken["sockets"][0]["bone"] = "Skull"
        self.assertTrue(any("Skull" in e for e in _contract.validate_contract(broken, self.profile)))

    def test_a_bad_rule_value_is_caught(self) -> None:
        broken = copy.deepcopy(self.contract)
        broken["kinds"]["body"]["height"] = "error"
        broken["kinds"]["prop"]["rig"] = "maybe"
        errors = _contract.validate_contract(broken, self.profile)
        self.assertTrue(any("kinds.body.height is 'error'" in e for e in errors), errors)
        self.assertTrue(any("kinds.prop.rig is 'maybe'" in e for e in errors), errors)

    def test_a_face_morph_bone_outside_the_profile_is_caught(self) -> None:
        broken = copy.deepcopy(self.contract)
        broken["face"]["morph_bones"] = ["Head", "Brow"]
        errors = _contract.validate_contract(broken, self.profile)
        self.assertTrue(any("face.morph_bones names 'Brow'" in e for e in errors), errors)
        del broken["face"]["morph_bones"]
        errors = _contract.validate_contract(broken, self.profile)
        self.assertTrue(any("face.morph_bones is missing" in e for e in errors), errors)

    def test_the_face_edge_and_part_morphs_are_checked(self) -> None:
        broken = copy.deepcopy(self.contract)
        broken["face"]["edge_bones"] = ["Collar"]
        errors = _contract.validate_contract(broken, self.profile)
        self.assertTrue(any("face.edge_bones names 'Collar'" in e for e in errors), errors)
        del broken["face"]["edge_mm"]
        errors = _contract.validate_contract(broken, self.profile)
        self.assertTrue(any("face.edge_mm (a number) are missing" in e for e in errors), errors)
        slots = {s["id"]: s for s in broken["slots"]}
        slots["hair_or_hat"]["part_morphs"] = ["look_l"]
        slots["eyes"]["part_morphs"] = ["look_l", 2, ""]
        errors = _contract.validate_contract(broken, self.profile)
        for slot in ("hair_or_hat", "eyes"):
            message = f"slot {slot}: part_morphs must be a list of shape key names, on a slot with parts"
            self.assertTrue(any(message in e for e in errors), errors)

    def test_faces_are_morphs_on_one_template_head(self) -> None:
        # The engineer, 2026-10-18 (art #200): no face texture frames and no rigid faces laid on the head.
        face = self.contract["face"]
        self.assertEqual(face["morph_bones"], ["Head", "Jaw", "LeftEye", "RightEye"])
        self.assertIn("template", face["template"])
        for part in ("eyeballs", "teeth", "tusks", "hair", "crests", "clothes"):
            self.assertIn(part, face["separate"])
        slots = {s["id"]: s for s in self.contract["slots"]}
        for slot in ("eyes", "mouth"):
            self.assertEqual(slots[slot]["forms"], ["morph"])
            self.assertNotIn("frames", slots[slot])
            self.assertTrue(slots[slot]["expressions"])
        self.assertEqual(slots["eyes"]["parts"], ["eyeballs"])
        self.assertEqual(slots["eyes"]["part_morphs"], ["look_l", "look_r", "look_u", "look_d"])
        self.assertNotIn("part_morphs", slots["mouth"])
        self.assertEqual((face["edge_bones"], face["edge_mm"]), (["Neck"], 2.0))
        self.assertEqual(slots["mouth"]["parts"], ["teeth", "tusks"])
        self.assertIn("morphs", self.contract["animation"]["face"])
        limits = self.contract["budgets"]["limits"]
        self.assertEqual((limits["blend_shapes_body"], limits["face_morphs_target"]), (0, 64))

    def test_axes_height_and_weights(self) -> None:
        self.assertEqual((self.contract["axes"]["up"], self.contract["axes"]["front"]), ("+Y", "+Z"))
        self.assertEqual(self.contract["axes"]["rest_pose"], "T")
        self.assertEqual(self.contract["body"]["height_m"], 1.75)
        self.assertEqual(self.contract["body"]["eye_height_m"], 1.6)
        self.assertLessEqual(self.contract["body"]["height_max_m"], self.contract["body"]["capsule_height_m"])
        self.assertEqual(self.contract["skeleton"]["max_weights_per_vertex"], 4)
        self.assertTrue(self.contract["skeleton"]["fingers_weighted"])
        self.assertEqual(len(self.contract["skeleton"]["weighted"]), 22)

    def test_sockets(self) -> None:
        sockets = {s["name"]: s["bone"] for s in self.contract["sockets"]}
        self.assertEqual(
            sockets,
            {
                "Socket_Head": "Head",
                "Socket_Face": "Head",
                "Socket_HandR": "RightHand",
                "Socket_HandL": "LeftHand",
                "Socket_Carry": "Chest",
                "Socket_Belt": "Hips",
                "Socket_Back": "UpperChest",
            },
        )

    def test_greybox_positions_turn_into_model_space(self) -> None:
        by_name = {s["name"]: s for s in self.contract["sockets"]}
        self.assertEqual(by_name["Socket_HandR"]["scene_position"], [0.45, 0.95, -0.15])
        self.assertEqual(by_name["Socket_Belt"]["scene_position"], [-0.48, 0.85, 0.0])
        self.assertEqual(by_name["Socket_Carry"]["scene_position"], [0.0, 0.8, -0.72])
        self.assertEqual(_contract.model_from_scene([0.45, 0.95, -0.15]), [-0.45, 0.95, 0.15])

    def test_v1_slots(self) -> None:
        slots = [s["id"] for s in self.contract["slots"]]
        self.assertEqual(
            slots,
            ["skin_colour", "eyes", "mouth", "hair_or_hat", "top", "bottom", "shoes", "face_accessory", "back_item"],
        )
        types = {s["id"]: s["type"] for s in self.contract["slots"]}
        self.assertEqual(types["eyes"], "face")
        self.assertEqual(types["mouth"], "face")
        self.assertIn("preset", self.contract["sets"]["rule"])

    def test_budgets(self) -> None:
        budgets = self.contract["budgets"]
        self.assertEqual((budgets["body"]["triangles_target"], budgets["body"]["triangles_cap"]), (6000, 8000))
        character = budgets["character"]
        self.assertEqual((character["triangles_target"], character["triangles_cap"]), (8000, 12000))
        self.assertEqual((self.contract["body"]["height_min_m"], self.contract["body"]["height_max_m"]), (1.7, 1.8))
        self.assertEqual(self.contract["animation"]["ragdoll"], "knockdown")


class BoneMapTest(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = _contract.load_profile()

    def test_every_map_is_valid(self) -> None:
        self.assertEqual(_contract.map_names(), ["meshy", "mixamo", "quaternius"])
        for name in _contract.map_names():
            with self.subTest(map=name):
                self.assertEqual(_contract.validate_map(_contract.load_map(name), self.profile), [])

    def test_unconfirmed_maps_are_marked(self) -> None:
        self.assertTrue(_contract.load_map("mixamo")["confirmed"])
        self.assertFalse(_contract.load_map("meshy")["confirmed"])
        self.assertTrue(_contract.load_map("quaternius")["confirmed"])

    def test_mixamo_names(self) -> None:
        mixamo = _contract.load_map("mixamo")
        self.assertEqual(_contract.mapped_name("mixamorig:Spine1", mixamo), "Chest")
        self.assertEqual(_contract.mapped_name("mixamorig2:LeftHandPinky3", mixamo), "LeftLittleDistal")
        self.assertEqual(_contract.mapped_name("mixamorig:LeftHandThumb1", mixamo), "LeftThumbMetacarpal")
        self.assertEqual(_contract.mapped_name("Root", mixamo), "Root")
        self.assertTrue(_contract.is_dropped("mixamorig:HeadTop_End", mixamo))
        self.assertFalse(_contract.is_dropped("mixamorig:Head", mixamo))

    def test_mixamo_covers_all_but_root_and_jaw(self) -> None:
        targets = set(_contract.load_map("mixamo")["rename"].values())
        missing = [n for n in _contract.profile_parents(self.profile) if n not in targets]
        self.assertEqual(missing, ["Root", "Jaw"])

    def test_a_clash_is_caught(self) -> None:
        bone_map = _contract.load_map("mixamo")
        bone_map["rename"]["Spine2"] = "Chest"
        self.assertTrue(any("both map to 'Chest'" in e for e in _contract.validate_map(bone_map, self.profile)))


if __name__ == "__main__":
    unittest.main()
