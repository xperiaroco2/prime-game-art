"""The check rules on hand-made measurements: pure Python, no Blender."""

import copy
import unittest

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
        measure = good_body(self.profile)
        measure["meshes"][0]["triangles"] = 7000
        self.assertEqual(self.statuses(self.evaluate(measure))["triangles"], _checks.WARN)
        measure["meshes"][0]["triangles"] = 8001
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
        report = self.evaluate(rigid_piece(900), "accessory")
        self.assertEqual(report["verdict"], _checks.PASS, report["results"])
        self.assertEqual(self.statuses(report)["triangles"], _checks.WARN)
        self.assertNotIn("height", self.statuses(report))
        self.assertEqual(self.evaluate(rigid_piece(1300), "accessory")["verdict"], _checks.FAIL)
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


if __name__ == "__main__":
    unittest.main()
