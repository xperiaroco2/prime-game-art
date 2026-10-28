"""The check rules on hand-made measurements: pure Python, no Blender."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from runner import common
from runner.commands import _checks, _contract


# The real Quaternius rig (xperiaroco2/prime-game-art#5), as `check` measured it in UAL1_Standard.glb and
# Superhero_Male_FullBody.gltf (the same 65 bones and parents in both): (name, parent), in file order.
QUATERNIUS_RIG = [
    ("root", ""), ("pelvis", "root"), ("spine_01", "pelvis"), ("spine_02", "spine_01"), ("spine_03", "spine_02"),
    ("neck_01", "spine_03"), ("Head", "neck_01"), ("clavicle_l", "spine_03"), ("upperarm_l", "clavicle_l"),
    ("lowerarm_l", "upperarm_l"), ("hand_l", "lowerarm_l"), ("index_01_l", "hand_l"), ("index_02_l", "index_01_l"),
    ("index_03_l", "index_02_l"), ("index_04_leaf_l", "index_03_l"), ("middle_01_l", "hand_l"),
    ("middle_02_l", "middle_01_l"), ("middle_03_l", "middle_02_l"), ("middle_04_leaf_l", "middle_03_l"),
    ("pinky_01_l", "hand_l"), ("pinky_02_l", "pinky_01_l"), ("pinky_03_l", "pinky_02_l"),
    ("pinky_04_leaf_l", "pinky_03_l"), ("ring_01_l", "hand_l"), ("ring_02_l", "ring_01_l"),
    ("ring_03_l", "ring_02_l"), ("ring_04_leaf_l", "ring_03_l"), ("thumb_01_l", "hand_l"),
    ("thumb_02_l", "thumb_01_l"), ("thumb_03_l", "thumb_02_l"), ("thumb_04_leaf_l", "thumb_03_l"),
    ("clavicle_r", "spine_03"), ("upperarm_r", "clavicle_r"), ("lowerarm_r", "upperarm_r"),
    ("hand_r", "lowerarm_r"), ("index_01_r", "hand_r"), ("index_02_r", "index_01_r"), ("index_03_r", "index_02_r"),
    ("index_04_leaf_r", "index_03_r"), ("middle_01_r", "hand_r"), ("middle_02_r", "middle_01_r"),
    ("middle_03_r", "middle_02_r"), ("middle_04_leaf_r", "middle_03_r"), ("pinky_01_r", "hand_r"),
    ("pinky_02_r", "pinky_01_r"), ("pinky_03_r", "pinky_02_r"), ("pinky_04_leaf_r", "pinky_03_r"),
    ("ring_01_r", "hand_r"), ("ring_02_r", "ring_01_r"), ("ring_03_r", "ring_02_r"),
    ("ring_04_leaf_r", "ring_03_r"), ("thumb_01_r", "hand_r"), ("thumb_02_r", "thumb_01_r"),
    ("thumb_03_r", "thumb_02_r"), ("thumb_04_leaf_r", "thumb_03_r"), ("thigh_l", "pelvis"), ("calf_l", "thigh_l"),
    ("foot_l", "calf_l"), ("ball_l", "foot_l"), ("ball_leaf_l", "ball_l"), ("thigh_r", "pelvis"),
    ("calf_r", "thigh_r"), ("foot_r", "calf_r"), ("ball_r", "foot_r"), ("ball_leaf_r", "ball_r"),
]
# Meshy's auto-rig as measured on 2026-10-18 (batch 2026-10-18-alien-3d-base2, t2-rig, art#196): names and parents.
MESHY_RIG = [
    ("Hips", ""), ("Spine02", "Hips"), ("Spine01", "Spine02"), ("Spine", "Spine01"), ("neck", "Spine"),
    ("Head", "neck"), ("head_end", "Head"), ("headfront", "Head"), ("LeftShoulder", "Spine"),
    ("LeftArm", "LeftShoulder"), ("LeftForeArm", "LeftArm"), ("LeftHand", "LeftForeArm"), ("RightShoulder", "Spine"),
    ("RightArm", "RightShoulder"), ("RightForeArm", "RightArm"), ("RightHand", "RightForeArm"),
    ("LeftUpLeg", "Hips"), ("LeftLeg", "LeftUpLeg"), ("LeftFoot", "LeftLeg"), ("LeftToeBase", "LeftFoot"),
    ("RightUpLeg", "Hips"), ("RightLeg", "RightUpLeg"), ("RightFoot", "RightLeg"), ("RightToeBase", "RightFoot"),
]


def bone_heads() -> dict[str, list[float]]:
    heads = {
        "LeftEye": [0.05, 1.6, 0.08],
        "RightEye": [-0.05, 1.6, 0.08],
        "LeftFoot": [0.1, 0.05, 0.0],
        "RightFoot": [-0.1, 0.05, 0.0],
        "LeftToes": [0.1, 0.05, 0.15],
        "RightToes": [-0.1, 0.05, 0.15],
        "LeftHand": [0.65, 1.3, 0.0],
        "RightHand": [-0.65, 1.3, 0.0],
    }
    return heads


def good_body(profile: dict) -> dict:
    """The measurements of a body that meets the contract: every profile bone, weighted where it must be."""
    parents = _contract.profile_parents(profile)
    heads = bone_heads()
    bones = [
        {"name": n, "parent": p, "head": heads.get(n, [0.0, 1.0, 0.0]), "tail": [0.0, 1.1, 0.0], "deform": n != "Root"}
        for n, p in parents.items()
    ]
    identity = {"location": [0.0, 0.0, 0.0], "rotation_deg": 0.0, "scale": [1.0, 1.0, 1.0]}
    mesh = {
        "name": "Body",
        "vertices": 4000,
        "triangles": 5800,
        "faces": 5800,
        "ngons": 0,
        "loose_vertices": 0,
        "loose_edges": 0,
        "non_manifold_edges": 0,
        "boundary_edges": 0,
        "islands": 1,
        "small_islands": 0,
        "uv_layers": 1,
        "uv_loops_out_of_range": 0,
        "materials": 1,
        "shape_keys": 0,
        "modifiers": [],
        "skinned": True,
        "transform": dict(identity),
        "min": [-0.87, 0.0, -0.13],
        "max": [0.87, 1.75, 0.26],
        "weights": {
            "groups": 55,
            "groups_without_bone": [],
            "max_influences": 4,
            "vertices_over_limit": 0,
            "unweighted_vertices": 0,
            "vertices_below_min_weight": 0,
            "vertices_not_normalized": 0,
            "weighted_bones": {n: 10 for n in parents if n not in ("Root", "Jaw", "LeftEye", "RightEye")},
        },
    }
    return {
        "model": "body.glb",
        "meshes": [mesh],
        "armatures": [{"name": "Armature", "transform": dict(identity), "bones": bones}],
        "empties": [],
        "other_objects": [],
    }


def rigid_piece(triangles: int) -> dict:
    measure = good_body(_contract.load_profile())
    measure["armatures"] = []
    mesh = measure["meshes"][0]
    mesh.update(skinned=False, triangles=triangles, vertices=triangles, min=[-0.1, 0.0, -0.1], max=[0.1, 0.2, 0.1])
    mesh["weights"].update(weighted_bones={}, groups=0)
    return measure


class EvaluateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = _contract.load_profile()
        self.contract = _contract.load_contract()

    def evaluate(self, measure: dict, kind: str = "body", bone_map: dict | None = None) -> dict:
        return _checks.evaluate(measure, kind, self.contract, self.profile, bone_map)

    def statuses(self, report: dict) -> dict[str, str]:
        return {r["check"]: r["status"] for r in report["results"]}

    def test_a_good_body_passes(self) -> None:
        report = self.evaluate(good_body(self.profile))
        failures = [r for r in report["results"] if r["status"] != _checks.PASS]
        self.assertEqual(failures, [])
        self.assertEqual(report["verdict"], _checks.PASS)

    def test_budget_target_warns_and_cap_fails(self) -> None:
        budget = self.contract["budgets"]["body"]  # the numbers come from the contract (art #212)
        measure = good_body(self.profile)
        measure["meshes"][0]["triangles"] = budget["triangles_target"] + 1
        self.assertEqual(self.statuses(self.evaluate(measure))["triangles"], _checks.WARN)
        measure["meshes"][0]["triangles"] = budget["triangles_cap"] + 1
        report = self.evaluate(measure)
        self.assertEqual(self.statuses(report)["triangles"], _checks.FAIL)
        self.assertEqual(report["verdict"], _checks.FAIL)

    def test_topology_failures(self) -> None:
        measure = good_body(self.profile)
        measure["meshes"][0].update(ngons=2, loose_vertices=1, non_manifold_edges=3, uv_layers=0)
        statuses = self.statuses(self.evaluate(measure))
        for check in ("ngons", "loose_geometry", "non_manifold_edges", "uvs"):
            self.assertEqual(statuses[check], _checks.FAIL, check)

    def test_unapplied_transform_fails(self) -> None:
        measure = good_body(self.profile)
        measure["armatures"][0]["transform"]["scale"] = [0.01, 0.01, 0.01]
        self.assertEqual(self.statuses(self.evaluate(measure))["transforms_applied"], _checks.FAIL)

    def test_height_feet_and_facing(self) -> None:
        measure = good_body(self.profile)
        measure["meshes"][0]["min"][1] = 0.05
        measure["meshes"][0]["max"][1] = 1.95
        for bone in measure["armatures"][0]["bones"]:
            bone["head"] = [-bone["head"][0], bone["head"][1], -bone["head"][2]]
        statuses = self.statuses(self.evaluate(measure))
        self.assertEqual(statuses["height"], _checks.FAIL)
        self.assertEqual(statuses["feet_at_zero"], _checks.FAIL)
        self.assertEqual(statuses["facing"], _checks.FAIL)

    def test_bone_and_weight_failures(self) -> None:
        measure = good_body(self.profile)
        bones = measure["armatures"][0]["bones"]
        bones[:] = [b for b in bones if b["name"] != "LeftRingDistal"]
        hat = {"name": "Socket_Hat", "parent": "Head", "head": [0, 1.7, 0], "tail": [0, 1.8, 0], "deform": False}
        bones.append(hat)
        weights = measure["meshes"][0]["weights"]
        weights.update(vertices_over_limit=2, max_influences=5, unweighted_vertices=1)
        weights["weighted_bones"]["Root"] = 3
        del weights["weighted_bones"]["LeftLittleIntermediate"]
        statuses = self.statuses(self.evaluate(measure))
        for check in (
            "missing_bones",
            "extra_bones",
            "weights_per_vertex",
            "unweighted_vertices",
            "root_unweighted",
            "finger_chains",
        ):
            self.assertEqual(statuses[check], _checks.FAIL, check)

    def test_wrong_parent_fails(self) -> None:
        measure = good_body(self.profile)
        for bone in measure["armatures"][0]["bones"]:
            if bone["name"] == "LeftHand":
                bone["parent"] = "LeftUpperArm"
        self.assertEqual(self.statuses(self.evaluate(measure))["bone_parents"], _checks.FAIL)

    def test_a_mapped_mixamo_rig_passes(self) -> None:
        mixamo = _contract.load_map("mixamo")
        to_mixamo = {target: "mixamorig:" + source for source, target in mixamo["rename"].items()}
        measure = good_body(self.profile)
        for bone in measure["armatures"][0]["bones"]:
            bone["name"] = to_mixamo.get(bone["name"], bone["name"])
            bone["parent"] = to_mixamo.get(bone["parent"], bone["parent"])
        weights = measure["meshes"][0]["weights"]
        weights["weighted_bones"] = {to_mixamo.get(n, n): c for n, c in weights["weighted_bones"].items()}
        self.assertEqual(self.evaluate(measure)["verdict"], _checks.FAIL)
        report = self.evaluate(measure, bone_map=mixamo)
        self.assertEqual(report["verdict"], _checks.PASS, report["results"])
        self.assertEqual(report["map"], "mixamo")

    def test_a_weighted_end_bone_hands_its_weights_to_its_parent(self) -> None:
        bone_map = {"name": "test", "confirmed": False, "prefix_pattern": "", "rename": {}, "drop": ["LeftIndexTip"]}
        measure = good_body(self.profile)
        tip = {"name": "LeftIndexTip", "parent": "LeftIndexDistal", "head": [0, 1, 0], "tail": [0, 1.1, 0]}
        tip["deform"] = True
        measure["armatures"][0]["bones"].append(tip)
        weights = measure["meshes"][0]["weights"]["weighted_bones"]
        weights["LeftIndexTip"] = 4
        del weights["LeftIndexDistal"]
        self.assertEqual(self.statuses(self.evaluate(measure))["extra_bones"], _checks.FAIL)
        report = self.evaluate(measure, bone_map=bone_map)
        statuses = self.statuses(report)
        self.assertEqual(statuses["extra_bones"], _checks.PASS, report["results"])
        self.assertEqual(statuses["finger_chains"], _checks.PASS, report["results"])
        detail = {r["check"]: r["detail"] for r in report["results"]}["dropped_bones"]
        self.assertIn("weights move from LeftIndexTip to LeftIndexDistal", detail)

    def test_a_weighted_dropped_bone_without_a_kept_ancestor_stays(self) -> None:
        bone_map = {"name": "test", "confirmed": False, "prefix_pattern": "", "rename": {}, "drop": ["Root"]}
        measure = good_body(self.profile)
        measure["meshes"][0]["weights"]["weighted_bones"]["Root"] = 2
        statuses = self.statuses(self.evaluate(measure, bone_map=bone_map))
        self.assertNotIn("dropped_bones", statuses)
        self.assertEqual(statuses["root_unweighted"], _checks.FAIL)

    def test_the_quaternius_map_fits_the_real_rig(self) -> None:
        quaternius = _contract.load_map("quaternius")
        self.assertTrue(quaternius["confirmed"])
        self.assertEqual(len(QUATERNIUS_RIG), 65)
        parents = _contract.profile_parents(self.profile)
        kept = [n for n, _ in QUATERNIUS_RIG if not _contract.is_dropped(n, quaternius)]
        self.assertEqual(len(kept), 53)
        self.assertEqual(sorted(n for n, _ in QUATERNIUS_RIG if n not in kept), sorted(quaternius["drop"]))
        mapped = {_contract.mapped_name(n, quaternius) for n in kept}
        self.assertEqual(sorted(set(parents) - mapped), ["Jaw", "LeftEye", "RightEye"])
        self.assertEqual(sorted(mapped - set(parents)), [])
        rig_names = {n for n, _ in QUATERNIUS_RIG}
        self.assertEqual([n for n in quaternius["rename"] if n not in rig_names], [], "map entries the rig lacks")

    def test_the_meshy_map_fits_the_real_rig(self) -> None:
        meshy = _contract.load_map("meshy")
        self.assertTrue(meshy["confirmed"])
        self.assertEqual(len(MESHY_RIG), 24)
        parents = _contract.profile_parents(self.profile)
        dropped = sorted(n for n, _ in MESHY_RIG if _contract.is_dropped(n, meshy))
        self.assertEqual(dropped, ["head_end", "headfront"])
        mapped = {n: _contract.mapped_name(n, meshy) for n, _ in MESHY_RIG if n not in dropped}
        self.assertEqual(sorted(t for t in mapped.values() if t not in parents), [])
        for name, parent in MESHY_RIG:
            if name in mapped and parent:
                with self.subTest(bone=name):
                    self.assertEqual(parents[mapped[name]], mapped[parent])
        # the hand is one bone: no fingers, eyes, jaw or root in Meshy's rig
        missing = set(parents) - set(mapped.values())
        self.assertIn("Jaw", missing)
        self.assertIn("LeftIndexProximal", missing)
        self.assertEqual(len(missing), len(parents) - 22)

    def test_a_quaternius_body_passes_but_for_the_jaw_and_eyes(self) -> None:
        quaternius = _contract.load_map("quaternius")
        from_profile = {target: source for source, target in quaternius["rename"].items()}
        heads = bone_heads()
        bones = []
        for name, parent in QUATERNIUS_RIG:
            head = heads.get(_contract.mapped_name(name, quaternius), [0.0, 1.0, 0.0])
            bones.append({"name": name, "parent": parent, "head": head, "tail": [0.0, 1.1, 0.0], "deform": True})
        measure = good_body(self.profile)
        measure["armatures"][0]["bones"] = bones
        weights = measure["meshes"][0]["weights"]
        weights["weighted_bones"] = {from_profile[n]: c for n, c in weights["weighted_bones"].items()}
        weights["weighted_bones"]["index_04_leaf_l"] = 3  # the Base Characters weight the finger tips
        report = self.evaluate(measure, bone_map=quaternius)
        failed = sorted(r["check"] for r in report["results"] if r["status"] == _checks.FAIL)
        self.assertEqual(failed, ["missing_bones"], report["results"])
        detail = {r["check"]: r["detail"] for r in report["results"]}
        self.assertEqual(detail["missing_bones"], "missing: LeftEye, RightEye, Jaw")
        self.assertEqual(self.statuses(report)["bone_parents"], _checks.PASS)

    def test_a_slot_budget_wins_over_the_kind(self) -> None:
        contract = self.contract
        contract["budgets"]["head_item"].update(triangles_target=500, triangles_cap=600)
        hair = _contract.checkable_slot(contract, "hair_or_hat")
        report = _checks.evaluate(rigid_piece(700), "accessory", contract, self.profile, slot=hair)
        self.assertEqual((report["budget"], report["slot"]), ("head_item", "hair_or_hat"))
        self.assertEqual(self.statuses(report)["triangles"], _checks.FAIL)
        self.assertEqual(self.statuses(self.evaluate(rigid_piece(700), "accessory"))["triangles"], _checks.PASS)

    def test_a_slot_without_a_model_cannot_be_checked(self) -> None:
        with self.assertRaises(common.Failure):
            _contract.checkable_slot(self.contract, "skin_colour")
        with self.assertRaises(common.Failure):
            _contract.checkable_slot(self.contract, "cape")

    def test_rigid_accessory(self) -> None:
        budget = self.contract["budgets"]["accessory"]
        report = self.evaluate(rigid_piece(budget["triangles_target"] + 100), "accessory")
        self.assertEqual(report["verdict"], _checks.PASS, report["results"])
        self.assertEqual(self.statuses(report)["triangles"], _checks.WARN)
        self.assertNotIn("height", self.statuses(report))
        self.assertEqual(self.evaluate(rigid_piece(budget["triangles_cap"] + 100), "accessory")["verdict"], _checks.FAIL)
        rigged = good_body(self.profile)
        self.assertEqual(self.statuses(self.evaluate(rigged, "accessory"))["rig"], _checks.FAIL)

    def test_clothing_may_use_a_subset_of_bones(self) -> None:
        measure = good_body(self.profile)
        measure["meshes"][0]["triangles"] = 1000
        measure["meshes"][0]["max"][1] = 1.0
        bones = measure["armatures"][0]["bones"]
        bones[:] = [b for b in bones if "Thumb" not in b["name"]]
        report = self.evaluate(measure, "clothing")
        self.assertEqual(report["verdict"], _checks.PASS, report["results"])
        self.assertNotIn("missing_bones", self.statuses(report))

    def test_a_body_needs_a_rig(self) -> None:
        self.assertEqual(self.statuses(self.evaluate(rigid_piece(5000)))["rig"], _checks.FAIL)


def four_finger_alien(profile: dict) -> dict:
    """A good body whose Little chains are present and carry no weights (the 2026-10-19 four-finger alien, art #223)."""
    measure = good_body(profile)
    painted = measure["meshes"][0]["weights"]["weighted_bones"]
    for name in [n for n in painted if "Little" in n]:
        del painted[name]
    return measure


class AlienFingersTest(unittest.TestCase):
    """kinds.alien: all five fingers weighted, as the body's, and the character budget (the engineer, art #196
    comment 6386685364); fingers_unweighted stays a rule any kind may carry."""

    setUp = EvaluateTest.setUp
    evaluate = EvaluateTest.evaluate
    statuses = EvaluateTest.statuses

    def finger_check(self, measure: dict, kind: str = "alien") -> dict:
        return next(r for r in self.evaluate(measure, kind)["results"] if r["check"] == "finger_chains")

    def test_five_weighted_fingers_pass(self) -> None:
        report = self.evaluate(good_body(self.profile), "alien")
        failures = [r for r in report["results"] if r["status"] != _checks.PASS]
        self.assertEqual(failures, [])
        self.assertEqual(report["verdict"], _checks.PASS)
        self.assertEqual(self.finger_check(good_body(self.profile))["detail"], "five weighted fingers per hand")

    def test_a_bare_little_fails_the_alien_now(self) -> None:
        for kind in ("alien", "body"):
            result = self.finger_check(four_finger_alien(self.profile), kind)
            self.assertEqual(result["status"], _checks.FAIL, kind)
            self.assertIn("LeftLittle is not weighted on LeftLittleProximal", result["detail"])

    def test_the_alien_is_held_to_the_character_budget(self) -> None:
        budget = self.contract["budgets"]["character"]
        self.assertEqual((budget["triangles_target"], budget["triangles_cap"]), (40000, 60000))
        measure = good_body(self.profile)
        for tris, alien, body in ((29000, _checks.PASS, _checks.WARN), (45000, _checks.WARN, _checks.FAIL),
                                  (60001, _checks.FAIL, _checks.FAIL)):
            measure["meshes"][0]["triangles"] = tris
            self.assertEqual(self.statuses(self.evaluate(measure, "alien"))["triangles"], alien, tris)
            self.assertEqual(self.statuses(self.evaluate(measure, "body"))["triangles"], body, tris)

    def test_a_missing_little_bone_fails(self) -> None:
        measure = good_body(self.profile)
        bones = measure["armatures"][0]["bones"]
        bones[:] = [b for b in bones if b["name"] != "RightLittleDistal"]
        result = self.finger_check(measure)
        self.assertEqual(result["status"], _checks.FAIL)
        self.assertIn("RightLittle lacks RightLittleDistal", result["detail"])
        self.assertEqual(self.statuses(self.evaluate(measure, "alien"))["missing_bones"], _checks.FAIL)

    def test_fingers_unweighted_still_works_for_a_kind_that_lists_it(self) -> None:
        self.contract = copy.deepcopy(self.contract)
        self.contract["kinds"]["alien"]["fingers_unweighted"] = ["Little"]
        result = self.finger_check(four_finger_alien(self.profile))
        self.assertEqual(result["status"], _checks.PASS)
        self.assertIn("4 weighted fingers per hand (Thumb, Index, Middle, Ring)", result["detail"])
        measure = four_finger_alien(self.profile)
        measure["meshes"][0]["weights"]["weighted_bones"]["LeftLittleIntermediate"] = 4
        result = self.finger_check(measure)
        self.assertEqual(result["status"], _checks.FAIL)
        self.assertIn("LeftLittle must carry no weights but is weighted on LeftLittleIntermediate", result["detail"])

    def test_another_unweighted_finger_fails(self) -> None:
        measure = good_body(self.profile)
        del measure["meshes"][0]["weights"]["weighted_bones"]["RightRingProximal"]
        result = self.finger_check(measure)
        self.assertEqual(result["status"], _checks.FAIL)
        self.assertIn("RightRing is not weighted on RightRingProximal", result["detail"])

    def test_whole_spring_sets_under_head_pass_and_other_extra_bones_fail(self) -> None:
        # [kinds.alien] bones = "all_and_springs" (art #196 comment 6374319309)
        def springs(parent: str, *names: str) -> dict:
            measure = good_body(self.profile)
            for name in names:
                measure["armatures"][0]["bones"].append({"name": name, "parent": parent, "head": [0, 1.8, 0],
                                                         "tail": [0, 1.85, 0], "deform": True})
                parent = name
            return measure

        crest = springs("Head", "Crest1", "Crest2", "Crest3")
        self.assertEqual(self.statuses(self.evaluate(crest, "alien"))["extra_bones"], _checks.PASS)
        self.assertEqual(self.statuses(self.evaluate(crest, "body"))["extra_bones"], _checks.FAIL)
        for measure in (springs("Head", "Crest1", "Crest2"), springs("Head", "Sword_Socket"),
                        springs("Hips", "Crest1", "Crest2", "Crest3"), springs("Head", "Crest3", "Crest1", "Crest2")):
            self.assertEqual(self.statuses(self.evaluate(measure, "alien"))["extra_bones"], _checks.FAIL)

        def with_gills(gill_l_parent: str) -> dict:
            measure = springs("Head", "Crest1", "Crest2", "Crest3")
            for parent, chain in ((gill_l_parent, ("GillL1", "GillL2", "GillL3")), ("Head", ("GillR1", "GillR2", "GillR3"))):
                for name in chain:
                    measure["armatures"][0]["bones"].append({"name": name, "parent": parent, "head": [0, 1.7, 0],
                                                             "tail": [0, 1.75, 0], "deform": True})
                    parent = name
            return measure

        self.assertEqual(self.statuses(self.evaluate(with_gills("Head"), "alien"))["extra_bones"], _checks.PASS)
        self.assertEqual(self.statuses(self.evaluate(with_gills("Crest2"), "alien"))["extra_bones"], _checks.FAIL)

    def test_the_alien_head_may_stand_above_the_capsule_up_to_its_cap(self) -> None:
        # [kinds.alien] head_top_max_m 1.95 (art #196 comment 6374319309); the body keeps height_max_m
        for top, alien, body in ((1.884, _checks.PASS, _checks.FAIL), (1.951, _checks.FAIL, _checks.FAIL)):
            measure = good_body(self.profile)
            measure["meshes"][0]["max"][1] = top
            self.assertEqual(self.statuses(self.evaluate(measure, "alien"))["height"], alien, top)
            self.assertEqual(self.statuses(self.evaluate(copy.deepcopy(measure), "body"))["height"], body, top)

    def test_the_alien_keeps_the_body_morph_rule(self) -> None:
        measure = with_keys(good_body(self.profile), {"belly": {"Spine": 30}})
        self.assertEqual(self.statuses(self.evaluate(measure, "alien"))["body_shape_morphs"], _checks.FAIL)


# An alien kit's character.json `nodes`, as tools/blender/alien_mouths.py writes them (S9d, art #196), cut down.
KIT_NODES = {
    "eyes": {
        "bored": {s: {"node": f"eye_bored_{s}", "ball": f"eye_bored_ball_{s}", "lid_upper": f"eye_bored_lid_upper_{s}",
                      "lid_lower": f"eye_bored_lid_lower_{s}"} for s in ("L", "R")},
        "manic": {s: {"node": f"eye_manic_{s}", "ball": f"eye_manic_ball_{s}"} for s in ("L", "R")},
    },
    "mouths": {
        "frog": {"rest": "mouth_frog_rest", "A": "mouth_frog_A"},
        "overbite": {"rest": "mouth_overbite_rest", "teeth": "mouth_overbite_teeth"},
    },
    "crests": ["crest_antennae", "crest_fins"],
}
REAL_KIT = common.raw_dir() / "review/char/alien-parts-kit/S9d/export/cage/character.json"


def alien_kit(profile: dict, part_triangles: dict[str, int] | None = None) -> dict:
    """A good five-finger alien Body plus every kit part as a rigid mesh off its socket (not at the origin)."""
    measure = good_body(profile)
    kit = _checks.kit_parts({"nodes": KIT_NODES})
    for name in sorted({n for choices in kit.values() for members in choices.values() for n in members}):
        part = rigid_piece((part_triangles or {}).get(name, 1000))["meshes"][0]
        part.update(name=name, min=[-0.05, 1.70, 0.0], max=[0.05, 1.86, 0.1])  # a crest above 1.80 m
        part["transform"] = {"location": [0.07, 1.55, 0.06], "rotation_deg": 11.5, "scale": [1.0, 1.0, 1.0]}
        measure["meshes"].append(part)
    return measure


class AlienKitTest(unittest.TestCase):
    """`check --kind alien` on a parts kit (art #226): Body as the alien, each part under its slot, the largest shown
    combination against the character budget."""

    setUp = EvaluateTest.setUp
    statuses = EvaluateTest.statuses

    def evaluate(self, measure: dict) -> dict:
        return _checks.evaluate_kit(measure, _checks.kit_parts({"nodes": KIT_NODES}), self.contract, self.profile)

    def test_the_kit_parts_are_read_by_group(self) -> None:
        kit = _checks.kit_parts({"nodes": KIT_NODES})
        self.assertEqual(kit["eyes"]["bored"], ["eye_bored_ball_L", "eye_bored_lid_lower_L", "eye_bored_lid_upper_L",
                                                "eye_bored_ball_R", "eye_bored_lid_lower_R", "eye_bored_lid_upper_R"])
        self.assertEqual(kit["mouths"]["mouth_overbite_rest"], ["mouth_overbite_rest", "mouth_overbite_teeth"])
        self.assertEqual(kit["mouths"]["mouth_frog_A"], ["mouth_frog_A"])
        self.assertNotIn("mouth_overbite_teeth", kit["mouths"])  # shown with every overbite piece, not alone
        self.assertEqual(kit["crests"], {"crest_antennae": ["crest_antennae"], "crest_fins": ["crest_fins"]})
        with self.assertRaises(ValueError):
            _checks.kit_parts({"glb": "export/alien_character.glb"})

    def test_a_good_kit_passes_with_its_parts_on_sockets(self) -> None:
        report = self.evaluate(alien_kit(self.profile))
        self.assertEqual(report["verdict"], _checks.PASS, [r for r in report["results"] if r["status"] != "pass"])
        statuses = self.statuses(report)
        self.assertEqual(statuses["transforms_applied"], _checks.PASS)  # the body's
        self.assertEqual(statuses["height"], _checks.PASS)  # Body alone: the crest reaches 1.86 m
        self.assertEqual(statuses["part crest_fins"], _checks.PASS)
        self.assertEqual(report["kit"]["parts"]["crest_fins"]["slot"], "hair_or_hat")
        self.assertEqual(report["kit"]["parts"]["mouth_frog_A"]["budget"], "accessory")
        eye = {r["check"]: r for r in report["kit"]["parts"]["eye_bored_ball_L"]["results"]}
        self.assertIn("rigid part on its socket", eye["transforms_applied"]["detail"])
        self.assertEqual(eye["rig"]["status"], _checks.PASS)

    def test_only_the_largest_shown_combination_counts(self) -> None:
        report = self.evaluate(alien_kit(self.profile, {"mouth_frog_A": 2400, "crest_fins": 1200}))
        combination = report["kit"]["combination"]
        # Body 5,800 + the bored eyes (6 x 1,000) + the frog's A (2,400) + crest_fins (1,200); not every part's sum
        self.assertEqual(combination["triangles"], 5800 + 6000 + 2400 + 1200)
        self.assertEqual(combination["choices"], {"eyes": "bored", "mouths": "mouth_frog_A", "crests": "crest_fins"})
        self.assertEqual(self.statuses(report)["character_triangles"], _checks.PASS)
        self.assertEqual(self.statuses(report)["triangles"], _checks.PASS)  # the body's own budget

    def test_part_failures_fail_the_kit(self) -> None:
        cap = self.contract["budgets"]["accessory"]["triangles_cap"]
        measure = alien_kit(self.profile, {"mouth_frog_A": cap + 1})
        next(m for m in measure["meshes"] if m["name"] == "crest_fins")["non_manifold_edges"] = 4
        next(m for m in measure["meshes"] if m["name"] == "eye_manic_ball_R")["skinned"] = True
        report = self.evaluate(measure)
        statuses = self.statuses(report)
        self.assertEqual(report["verdict"], _checks.FAIL)
        for part in ("part mouth_frog_A", "part crest_fins", "part eye_manic_ball_R"):
            self.assertEqual(statuses[part], _checks.FAIL, part)
        self.assertEqual(statuses["part mouth_frog_rest"], _checks.PASS)

    def test_the_combination_has_the_character_budget(self) -> None:
        cap = self.contract["budgets"]["character"]["triangles_cap"]
        measure = alien_kit(self.profile)
        measure["meshes"][0]["triangles"] = cap
        statuses = self.statuses(self.evaluate(measure))
        self.assertEqual(statuses["character_triangles"], _checks.FAIL)
        # the body alone at the cap: its own budget is the character's too (art #196 comment 6386685364), so it is
        # over the target but not over the cap
        self.assertEqual(statuses["triangles"], _checks.WARN)
        measure["meshes"][0]["triangles"] = cap + 1
        self.assertEqual(self.statuses(self.evaluate(measure))["triangles"], _checks.FAIL)

    def test_a_missing_part_warns(self) -> None:
        measure = alien_kit(self.profile)
        measure["meshes"] = [m for m in measure["meshes"] if m["name"] != "mouth_overbite_teeth"]
        self.assertEqual(self.statuses(self.evaluate(measure))["part mouth_overbite_teeth"], _checks.WARN)

    @unittest.skipUnless(REAL_KIT.is_file(), f"the S9d kit is not in {REAL_KIT.parent.as_posix()}")
    def test_the_real_kit_file(self) -> None:
        kit = _checks.kit_parts(json.loads(REAL_KIT.read_text(encoding="utf-8")))
        self.assertEqual(sorted(kit["eyes"]), ["bored", "manic"])
        self.assertTrue(all(len(members) == 6 for members in kit["eyes"].values()))
        self.assertEqual(len(kit["mouths"]), 24)  # two designs, six shapes, 3D pieces and flipbook shells
        self.assertEqual(sorted(kit["crests"]), ["crest_antennae", "crest_fins"])


class KitPathTest(unittest.TestCase):
    """check.py finds the kit's character.json beside an alien model, only with `nodes`."""

    def test_the_kit_beside_the_model(self) -> None:
        from runner.commands import check

        with tempfile.TemporaryDirectory() as tmp:
            model = Path(tmp) / "alien_character.glb"
            beside = Path(tmp) / "character.json"
            self.assertIsNone(check._kit_path(model, "alien", None))
            beside.write_text(json.dumps({"glb": "x.glb"}), encoding="utf-8")
            self.assertIsNone(check._kit_path(model, "alien", None))
            beside.write_text(json.dumps({"nodes": KIT_NODES}), encoding="utf-8")
            self.assertEqual(check._kit_path(model, "alien", None), beside)
            self.assertIsNone(check._kit_path(model, "body", None))
            self.assertEqual(check._kit_path(model, "alien", str(beside)), beside.resolve())
            with self.assertRaises(common.Failure):
                check._kit_path(model, "body", str(beside))


def with_keys(measure: dict, keys: dict[str, dict[str, int | tuple[int, float]]] | None) -> dict:
    """The measure's first mesh with shape keys; per key the moved vertices grouped by their main bones: a count
    (moved 5 mm) or (count, largest move in mm)."""
    mesh = measure["meshes"][0]
    mesh["shape_keys"] = len(keys or {}) or 3
    if keys is None:
        mesh.pop("shape_key_bones", None)  # an old measure, from before the per-key bones
        return measure
    mesh["shape_key_bones"] = {
        key: {
            group: {"vertices": m[0], "max_mm": m[1]} if isinstance(m, tuple) else {"vertices": m, "max_mm": 5.0}
            for group, m in groups.items()
        }
        for key, groups in keys.items()
    }
    return measure


class FaceMorphTest(unittest.TestCase):
    """Faces are morphs on the template head (docs/decisions/2026-10-18-faces-as-morphs.md, art #200)."""

    def setUp(self) -> None:
        self.profile = _contract.load_profile()
        self.contract = _contract.load_contract()

    def evaluate(
        self, measure: dict, kind: str = "body", bone_map: dict | None = None, slot: dict | None = None
    ) -> dict:
        return _checks.evaluate(measure, kind, self.contract, self.profile, bone_map, slot)

    def results(self, report: dict) -> dict[str, tuple[str, str]]:
        return {r["check"]: (r["status"], r["detail"]) for r in report["results"]}

    def test_face_morphs_on_the_head_pass(self) -> None:
        keys = {"mouth_a": {"Head": 120, "Jaw": 30}, "blink": {"Head": 80}, "look_l": {"LeftEye": 40}, "noop": {}}
        report = self.evaluate(with_keys(good_body(self.profile), keys))
        self.assertEqual(report["verdict"], _checks.PASS, report["results"])
        results = self.results(report)
        self.assertEqual(results["body_shape_morphs"][0], _checks.PASS)
        self.assertEqual(
            results["face_morphs"], (_checks.PASS, "face morphs on Body (4); at most 64 per mesh (provisional)")
        )
        self.assertNotIn("blend_shapes", results)

    def test_a_body_shape_morph_fails(self) -> None:
        keys = {"mouth_a": {"Head": 120}, "belly": {"Spine": 300, "Hips": 20}, "chin": {"Head": 50, "Neck": 4}}
        report = self.evaluate(with_keys(good_body(self.profile), keys))
        self.assertEqual(report["verdict"], _checks.FAIL)
        status, detail = self.results(report)["body_shape_morphs"]
        self.assertEqual(status, _checks.FAIL)
        self.assertIn("Body:belly moves skin on Hips (20 vertices, up to 5 mm), Spine (300 vertices, up to 5 mm)",
                      detail)
        self.assertIn("Body:chin moves skin on Neck (4 vertices, up to 5 mm)", detail)
        self.assertTrue(self.results(report)["face_morphs"][1].startswith("face morphs on Body (1);"))

    def test_a_soft_chin_morph_may_touch_the_neck_within_the_edge(self) -> None:
        # face.edge_bones and face.edge_mm: a soft falloff's tail on the neck is still a face morph.
        self.assertEqual((self.contract["face"]["edge_bones"], self.contract["face"]["edge_mm"]), (["Neck"], 2.0))
        keys = {"chin": {"Head": 50, "Jaw": 20, "Neck": (6, 2.0)}, "jaw_drop": {"Jaw": 80, "Neck": (3, 2.5)}}
        report = self.evaluate(with_keys(good_body(self.profile), keys))
        results = self.results(report)
        self.assertEqual(results["body_shape_morphs"],
                         (_checks.FAIL, "1 shape keys move skin off the head bones: "
                                        "Body:jaw_drop moves skin on Neck (3 vertices, up to 2.5 mm)"))
        self.assertEqual(results["face_morphs"], (_checks.PASS, "face morphs on Body (1); 1 move Neck skin by at "
                                                                "most 2 mm; at most 64 per mesh (provisional)"))

    def test_the_edge_is_only_for_the_neck(self) -> None:
        report = self.evaluate(with_keys(good_body(self.profile), {"slim": {"Head": 10, "UpperChest": (40, 1.0)}}))
        self.assertIn("Body:slim moves skin on UpperChest", self.results(report)["body_shape_morphs"][1])
        self.assertEqual(report["verdict"], _checks.FAIL)

    def test_the_edge_needs_head_skin_in_the_same_key(self) -> None:
        # A key that moves only neck skin, however little, is no face morph: the edge is a face morph's soft tail.
        report = self.evaluate(with_keys(good_body(self.profile), {"neck": {"Neck": (8, 1.0)}}))
        self.assertEqual(self.results(report)["body_shape_morphs"],
                         (_checks.FAIL, "1 shape keys move skin off the head bones: "
                                        "Body:neck moves skin on Neck (8 vertices, up to 1 mm)"))
        self.assertNotIn("face_morphs", self.results(report))

    def test_the_edge_is_not_for_a_neck_body_tie(self) -> None:
        # Every tied bone must be an edge bone: a Chest|Neck vertex is body skin, and 2 mm there still fails.
        report = self.evaluate(with_keys(good_body(self.profile), {"chin": {"Head": 12, "Chest|Neck": (2, 1.0)}}))
        self.assertEqual(self.results(report)["body_shape_morphs"],
                         (_checks.FAIL, "1 shape keys move skin off the head bones: "
                                        "Body:chin moves skin on Chest|Neck (2 vertices, up to 1 mm)"))

    def test_a_weight_tie_goes_to_the_head(self) -> None:
        # check_model.py joins the bones tied for a vertex's largest weight with "|" (0.5 Head, 0.5 Neck). The tie
        # rule, not the edge, passes it: it moves 5 mm, past face.edge_mm.
        report = self.evaluate(with_keys(good_body(self.profile), {"chin": {"Head|Neck": 12}}))
        results = self.results(report)
        self.assertEqual(results["body_shape_morphs"][0], _checks.PASS, results)
        self.assertEqual(results["face_morphs"],
                         (_checks.PASS, "face morphs on Body (1); at most 64 per mesh (provisional)"))
        report = self.evaluate(with_keys(good_body(self.profile), {"chest": {"Chest|Spine": 12}}))
        self.assertIn("Body:chest moves skin on Chest|Spine", self.results(report)["body_shape_morphs"][1])

    def test_unweighted_moved_vertices_are_not_a_face(self) -> None:
        report = self.evaluate(with_keys(good_body(self.profile), {"bump": {"": (5, 0.5), "Head": 9}}))
        self.assertIn("moves skin on no bone (5 vertices, up to 0.5 mm)", self.results(report)["body_shape_morphs"][1])
        self.assertEqual(report["verdict"], _checks.FAIL)

    def test_keys_without_the_per_key_measure_fail_on_a_body(self) -> None:
        report = self.evaluate(with_keys(good_body(self.profile), None))
        status, detail = self.results(report)["body_shape_morphs"]
        self.assertEqual((status, detail), (_checks.FAIL, "1 shape keys move skin off the head bones: "
                                                          "Body (3 keys, not measured per key)"))

    def test_more_face_morphs_than_the_target_warn(self) -> None:
        keys = {f"m{i}": {"Head": 10} for i in range(65)}
        report = self.evaluate(with_keys(good_body(self.profile), keys))
        self.assertEqual(self.results(report)["face_morphs"][0], _checks.WARN)
        self.assertEqual(report["verdict"], _checks.PASS)

    def test_the_bone_map_names_the_head(self) -> None:
        mixamo = _contract.load_map("mixamo")
        keys = {"mouth_a": {"mixamorig:Head": 100}, "belly": {"mixamorig:Spine": 100}}
        detail = self.results(self.evaluate(with_keys(good_body(self.profile), keys), bone_map=mixamo))
        self.assertEqual(
            detail["body_shape_morphs"][1],
            "1 shape keys move skin off the head bones: "
            "Body:belly moves skin on mixamorig:Spine (100 vertices, up to 5 mm)",
        )
        tie = self.evaluate(with_keys(good_body(self.profile), {"chin": {"mixamorig:Head|mixamorig:Neck": 9}}),
                            bone_map=mixamo)
        self.assertEqual(self.results(tie)["body_shape_morphs"][0], _checks.PASS)

    def test_other_kinds_warn_on_any_shape_key(self) -> None:
        for kind, measure in (("accessory", rigid_piece(500)), ("prop", rigid_piece(500))):
            with self.subTest(kind=kind):
                report = self.evaluate(with_keys(measure, {"look_l": {"": 40}}), kind)
                self.assertEqual(self.results(report)["blend_shapes"],
                                 (_checks.WARN, "1 shape keys on Body (1)"))
                self.assertNotIn("body_shape_morphs", self.results(report))
                self.assertNotIn("part_morphs", self.results(report))

    def test_the_eyes_slot_parts_may_carry_look_morphs(self) -> None:
        eyes = _contract.checkable_slot(self.contract, "eyes")
        self.assertEqual(eyes["part_morphs"], ["look_l", "look_r", "look_u", "look_d"])
        looks = {name: {"": 40} for name in eyes["part_morphs"]}
        report = self.evaluate(with_keys(rigid_piece(500), looks), "accessory", slot=eyes)
        results = self.results(report)
        self.assertEqual(results["part_morphs"], (_checks.PASS, "the eyes slot's part morphs on Body (4)"))
        self.assertNotIn("blend_shapes", results)
        self.assertEqual(report["verdict"], _checks.PASS, report["results"])
        report = self.evaluate(with_keys(rigid_piece(500), {**looks, "squash": {"": 40}}), "accessory", slot=eyes)
        self.assertEqual(self.results(report)["blend_shapes"], (_checks.WARN, "1 shape keys on Body (1)"))
        mouth = _contract.checkable_slot(self.contract, "mouth")  # teeth and tusks have no part morphs
        report = self.evaluate(with_keys(rigid_piece(500), looks), "accessory", slot=mouth)
        self.assertEqual(self.results(report)["blend_shapes"], (_checks.WARN, "4 shape keys on Body (4)"))


if __name__ == "__main__":
    unittest.main()
