"""godot-check (docs/godot.md): the assertions on a synthetic description of an imported character, the import file,
Godot's noteworthy output lines, the humanoid trial's bone map; and, with Godot, Blender, the validator and the packs,
the real check of an exported man and woman."""

from __future__ import annotations

import copy
import json
import unittest

from runner.commands import _godot, _humanoid

from . import _export_fixture as fx

BONES = ["Root", "Hips", "Head", "Wrist.L", "Wrist.R", "Foot.L", "Foot.R"]
PARENTS = [-1, 0, 1, 1, 1, 1, 1]
JOINTS = {"Root": [0, 0, 0], "Hips": [0, 0.9, 0], "Head": [0, 1.59, 0.04], "Wrist.L": [0.57, 1.43, 0.08],
          "Wrist.R": [-0.57, 1.43, 0.08], "Foot.L": [0.12, 0.02, 0.06], "Foot.R": [-0.12, 0.02, 0.06]}
CONTRACT = {"body": {"height_m": 1.75, "height_min_m": 1.70, "height_max_m": 1.80, "eye_height_m": 1.6,
                     "eye_tolerance_m": 0.08, "feet_tolerance_m": 0.01},
            "kinds": {"body": {"height": "fail", "eyes": "warn", "feet": "fail", "facing": "fail"}}}
ANIMS = {"CharacterArmature|Idle": 40 / 24, "CharacterArmature|Walk": 32 / 24}


def mesh(name: str, lo: list[float], hi: list[float]) -> dict:
    return {"name": name, "path": f"x_rig/Skeleton3D/{name}", "skeleton": "x_rig/Skeleton3D", "skeleton_is_skeleton3d": True,
            "skin": True, "binds": list(BONES), "unresolved_binds": [], "surfaces": 1, "vertices": 100,
            "materials": [{"name": "m", "albedo": [0.5, 0.5, 0.5], "metallic": 0.4, "roughness": 0.4, "textured": False}],
            "rest_bounds": {"min": lo, "max": hi}}


def dump() -> dict:
    return {
        "godot": "4.7.2-stable (official)",
        "skeletons": [{"path": "x_rig/Skeleton3D", "bones": list(BONES), "parents": list(PARENTS), "rest_joints": copy.deepcopy(JOINTS)}],
        "meshes": [mesh("x_head", [-0.1, 1.45, -0.04], [0.1, 1.76, 0.17]),
                   mesh("x_eyes", [-0.06, 1.60, 0.14], [0.06, 1.63, 0.17]),
                   mesh("x_shoes", [-0.19, -0.001, -0.001], [0.19, 0.24, 0.29])],
        "players": [{"path": "AnimationPlayer", "animations": {
            name: {"length": length, "loop_mode": 1, "tracks": 7, "track_types": {"2": 7}, "unresolved": [],
                   "motion": {"max_rotation_deg": 12.0, "max_translation_m": 0.0, "most_moved_bone": "Hips"}}
            for name, length in ANIMS.items()}}],
    }


def expect() -> dict:
    return {"source": "x.export.json", "parts": ["x_eyes", "x_head", "x_shoes"], "bones": list(BONES),
            "bone_parents": {b: (BONES[p] if p >= 0 else None) for b, p in zip(BONES, PARENTS)},
            "rest_heads_m": copy.deepcopy(JOINTS), "animations": dict(ANIMS), "height_m": 1.761}


def statuses(d: dict, e: dict | None = None, output: list[str] | None = None, strict: bool = False) -> dict[str, str]:
    return {c["check"]: c["status"] for c in _godot.evaluate(d, e or expect(), CONTRACT, output or [], strict_contract=strict)}


class EvaluateTest(unittest.TestCase):
    def test_a_good_import_passes_everything(self) -> None:
        got = statuses(dump())
        self.assertEqual({k for k, v in got.items() if v != "pass"}, set(), got)
        self.assertEqual(set(got), {"one_skeleton", "skeleton_bones", "bone_hierarchy", "rest_joints", "parts_separate",
                                    "parts_skinned", "one_animation_player", "animations", "animation_lengths",
                                    "tracks_resolve", "animations_move", "size_kept", "feet_at_zero", "facing_plus_z",
                                    "contract_height", "contract_eye_height", "flat_colours", "godot_output",
                                    "loop_modes"})

    def test_each_failure_is_caught(self) -> None:
        def unskin(d: dict) -> None:
            d["meshes"][0]["skin"] = False

        cases = {
            "one_skeleton": lambda d: d["skeletons"].append(copy.deepcopy(d["skeletons"][0])),
            "skeleton_bones": lambda d: d["skeletons"][0]["bones"].__setitem__(2, "Head_renamed"),
            "bone_hierarchy": lambda d: d["skeletons"][0]["parents"].__setitem__(2, 0),
            "rest_joints": lambda d: d["skeletons"][0]["rest_joints"].__setitem__("Head", [0, 1.6, 0.04]),
            "parts_separate": lambda d: d["meshes"].pop(),
            "parts_skinned": unskin,
            "animations": lambda d: d["players"][0]["animations"].pop("CharacterArmature|Walk"),
            "animation_lengths": lambda d: d["players"][0]["animations"]["CharacterArmature|Walk"].update(length=1.0),
            "tracks_resolve": lambda d: d["players"][0]["animations"]["CharacterArmature|Idle"].update(unresolved=["x:Gone"]),
            "animations_move": lambda d: d["players"][0]["animations"]["CharacterArmature|Idle"]["motion"].update(max_rotation_deg=0.1),
            "size_kept": lambda d: d["meshes"][0]["rest_bounds"]["max"].__setitem__(1, 1.80),
            "feet_at_zero": lambda d: d["meshes"][2]["rest_bounds"]["min"].__setitem__(1, 0.05),
            "facing_plus_z": lambda d: d["meshes"][1]["rest_bounds"].update(min=[-0.06, 1.68, -0.1], max=[0.06, 1.71, -0.08]),
            "flat_colours": lambda d: d["meshes"][0]["materials"][0].update(textured=True),
        }
        for check, mutate in cases.items():
            with self.subTest(check):
                d = dump()
                mutate(d)
                self.assertEqual(statuses(d)[check], "fail")

    def test_unresolved_track_warnings_and_errors_in_godots_output_fail(self) -> None:
        got = statuses(dump(), output=["WARNING: AnimationMixer: 'Walk', couldn't resolve track: 'x:Toe'.", "ERROR: boom"])
        self.assertEqual((got["tracks_resolve"], got["godot_output"]), ("fail", "fail"))

    def test_the_contract_v1_gates_warn_unless_strict(self) -> None:
        d = dump()
        d["meshes"][0]["rest_bounds"]["max"][1] = 1.967  # m1_rex with his hair
        e = expect()
        e["height_m"] = 1.968
        self.assertEqual(statuses(d, e)["contract_height"], "warn")
        self.assertEqual(statuses(d, e, strict=True)["contract_height"], "fail")
        d["meshes"][1]["rest_bounds"].update(min=[-0.06, 1.69, 0.14], max=[0.06, 1.70, 0.17])  # eyes at 1.695 m
        self.assertEqual(statuses(d, e, strict=True)["contract_eye_height"], "warn")  # the contract's eyes rule is warn

    def test_a_barefoot_body_faces_by_its_foot_and_toe_skin(self) -> None:
        def barefoot(toe_z: float, heel_z: float) -> dict:
            d = dump()
            body = mesh("x_body", [-0.19, -0.001, heel_z], [0.19, 1.76, 0.2])
            body["bone_bounds"] = {"Head": {"min": [-0.1, 1.45, -0.04], "max": [0.1, 1.76, 0.17]},
                                   "Foot.L": {"min": [0.05, 0.0, heel_z], "max": [0.19, 0.1, 0.12]},
                                   "Toe.L": {"min": [0.06, 0.0, 0.12], "max": [0.18, 0.05, toe_z]},
                                   "Foot.R": {"min": [-0.19, 0.0, heel_z], "max": [-0.05, 0.1, 0.12]}}
            d["meshes"][1]["bone_bounds"] = {"Head": {"min": [-0.06, 1.60, 0.14], "max": [0.06, 1.63, 0.17]}}
            d["meshes"] = [body, d["meshes"][1]]
            return d

        def facing(d: dict) -> dict:
            e = {**expect(), "parts": ["x_body", "x_eyes"]}
            return next(c for c in _godot.evaluate(d, e, CONTRACT, []) if c["check"] == "facing_plus_z")

        good = facing(barefoot(toe_z=0.25, heel_z=-0.02))
        self.assertEqual(good["status"], "pass", good)
        self.assertIn("bare feet reach 19.0 cm forward and 8.0 cm back", good["detail"])
        stray = barefoot(toe_z=0.25, heel_z=-0.02)  # the eyes' skin on a foot bone would move the toes 64 cm out
        stray["meshes"][1]["bone_bounds"]["Toe.L"] = {"min": [0.0, 1.6, 0.1], "max": [0.01, 1.61, 0.7]}
        self.assertIn("bare feet reach 19.0 cm forward", facing(stray)["detail"])
        backwards = facing(barefoot(toe_z=0.08, heel_z=-0.2))  # heels further out than toes: the feet face -Z
        self.assertEqual(backwards["status"], "fail", backwards)
        bare = barefoot(toe_z=0.25, heel_z=-0.02)
        bare["meshes"][0]["bone_bounds"] = {"Head": bare["meshes"][0]["bone_bounds"]["Head"]}  # no skin on the feet
        unsure = facing(bare)
        self.assertEqual(unsure["status"], "fail")
        self.assertTrue(unsure["detail"].startswith("cannot tell"), unsure)
        older = barefoot(toe_z=0.25, heel_z=-0.02)  # an inspect.json from before bone_bounds
        older["meshes"][0].pop("bone_bounds")
        self.assertTrue(facing(older)["detail"].startswith("cannot tell"))

    def test_the_shoes_part_wins_over_the_body_feet(self) -> None:
        d = dump()
        d["meshes"][0]["bone_bounds"] = {"Foot.L": {"min": [0.05, 0.0, -0.5], "max": [0.19, 0.1, 0.0]}}  # would fail
        got = next(c for c in _godot.evaluate(d, expect(), CONTRACT, []) if c["check"] == "facing_plus_z")
        self.assertEqual(got["status"], "pass", got)
        self.assertIn("shoes reach", got["detail"])

    def test_renamed_bones_are_compared_through_the_map(self) -> None:
        renamed = {"Wrist.L": "LeftHand", "Wrist.R": "RightHand", "Foot.L": "LeftFoot", "Foot.R": "RightFoot"}
        d = dump()
        sk = d["skeletons"][0]
        sk["bones"] = [renamed.get(b, b) for b in sk["bones"]]
        sk["rest_joints"] = {renamed.get(b, b): v for b, v in sk["rest_joints"].items()}
        got = {c["check"]: c["status"] for c in _godot.evaluate(d, expect(), CONTRACT, [], renamed=renamed)}
        self.assertEqual(got["skeleton_bones"], "pass")
        self.assertEqual(got["facing_plus_z"], "pass")
        self.assertNotIn("rest_joints", got)


class WithoutExportJsonTest(unittest.TestCase):
    def test_a_bare_glb_warns_and_is_held_to_the_pack_floor(self) -> None:
        bare = {**expect(), "source": "x.glb", "bone_parents": {}, "rest_heads_m": {}, "height_m": None}
        got = statuses(dump(), bare)
        self.assertEqual(got["expectations"], "warn")
        self.assertEqual(got["pack_floor"], "fail")  # the fixture has 7 bones and 2 animations
        self.assertNotIn("expectations", statuses(dump()))

    def test_a_bare_glb_expects_the_names_godot_gives(self) -> None:
        summary = {"meshes": {"m1_head": {}}, "skins": [["Root", "Hips"]],
                   "animations": {"Idle_Loop": {"duration_s": 2.5}, "Jump_Start": {"duration_s": 0.3}}}
        got = _godot.expect_from_summary("slice_m1.glb", summary)
        self.assertEqual(got["animations"], {"Idle": 2.5, "Jump_Start": 0.3})
        self.assertEqual(got["loop_suffix"], ["Idle"])
        self.assertEqual((got["source"], got["parts"], got["bones"]), ("slice_m1.glb", ["m1_head"], ["Root", "Hips"]))


A_BONES = ["Root", "Hips", "Head", "LeftEye", "RightEye", "LeftHand", "RightHand", "LeftFoot", "RightFoot", "LeftToes",
           "RightToes"]
A_JOINTS = {"Root": [0, 0, 0], "Hips": [0, 0.9, 0], "Head": [0, 1.45, 0.02], "LeftEye": [0.06, 1.62, 0.13],
            "RightEye": [-0.06, 1.62, 0.13], "LeftHand": [0.5, 1.0, 0.05], "RightHand": [-0.5, 1.0, 0.05],
            "LeftFoot": [0.1, 0.08, 0.0], "RightFoot": [-0.1, 0.08, 0.0], "LeftToes": [0.1, 0.02, 0.1],
            "RightToes": [-0.1, 0.02, 0.1]}
A_CONTRACT = {**CONTRACT, "body": {**CONTRACT["body"], "plasticine_height_max_m": 2.0},
              "budgets": {"limits": {"texture_character_px": 2048, "surfaces_per_character_cap": 4,
                                     "surfaces_per_character_target": 2}}, "skeleton": {"weighted": ["Hips", "Head", "LeftHand", "RightHand", "LeftFoot", "RightFoot"]}}


def alien_dump(clips=_godot.ALIEN_CLIPS) -> dict:
    body = mesh("x_char", [-0.2, -0.001, -0.05], [0.2, 1.88, 0.2])
    body["binds"] = list(A_BONES)
    body["bone_bounds"] = {"LeftFoot": {"min": [0.05, 0.0, -0.04], "max": [0.15, 0.1, 0.08]},
                           "LeftToes": {"min": [0.05, 0.0, 0.08], "max": [0.15, 0.05, 0.16]},
                           "RightFoot": {"min": [-0.15, 0.0, -0.04], "max": [-0.05, 0.1, 0.08]}}
    body["eye_tones"] = {"vertices": 2000, "white": 900, "black": 60, "cap_m": 0.05}
    d = dump()
    d["skeletons"] = [{"path": "x_rig/Skeleton3D", "bones": list(A_BONES), "parents": [-1] + [0] * 10,
                       "rest_joints": copy.deepcopy(A_JOINTS)}]
    d["meshes"] = [body]
    d["players"][0]["animations"] = {f"CharacterArmature|{n}": next(iter(d["players"][0]["animations"].values()))
                                     for n in clips}
    return d


def alien(d: dict, profile: str = "alien") -> dict[str, dict]:
    e = {**expect(), "source": "x_char.glb", "parts": ["x_char"], "bones": list(A_BONES), "bone_parents": {},
         "rest_heads_m": {}, "height_m": None, "animations": {}}
    return {c["check"]: c for c in _godot.evaluate(d, e, A_CONTRACT, [], textured=True, profile=profile)}


class AlienProfileTest(unittest.TestCase):
    """--profile alien (art #196 B2): the alien kind's own equivalents of the Ultimate Modular rules."""

    def test_an_alien_passes_its_own_rules(self) -> None:
        got = alien(alien_dump())
        for k in ("facing_plus_z", "eye_pupils", "pack_floor"):
            self.assertEqual(got[k]["status"], "pass", got[k])
            self.assertTrue(got[k]["detail"].startswith("alien profile"), got[k])
        self.assertIn("+11.0 cm ahead", got["facing_plus_z"]["detail"])

    def test_the_pack_rules_still_fail_an_alien(self) -> None:
        got = alien(alien_dump(), profile="pack")
        for k in ("facing_plus_z", "eye_pupils", "pack_floor"):
            self.assertEqual(got[k]["status"], "fail", got[k])

    def test_an_alien_facing_backwards_fails(self) -> None:
        d = alien_dump()
        for b in ("LeftEye", "RightEye"):
            d["skeletons"][0]["rest_joints"][b][2] = -0.1  # the eyes behind the Head joint: it faces -Z
        self.assertEqual(alien(d)["facing_plus_z"]["status"], "fail")
        d = alien_dump()
        j = d["skeletons"][0]["rest_joints"]
        j["LeftEye"], j["RightEye"] = j["RightEye"], j["LeftEye"]  # mirrored
        self.assertEqual(alien(d)["facing_plus_z"]["status"], "fail")

    def test_eyes_without_pupils_fail(self) -> None:
        d = alien_dump()
        d["meshes"][0]["eye_tones"]["black"] = 3
        self.assertEqual(alien(d)["eye_pupils"]["status"], "fail")
        d["meshes"][0].pop("eye_tones")
        self.assertIn("no eye caps", alien(d)["eye_pupils"]["detail"])

    def test_a_missing_clip_or_bone_fails_the_floor(self) -> None:
        got = alien(alien_dump(clips=_godot.ALIEN_CLIPS[:-1]))["pack_floor"]
        self.assertEqual(got["status"], "fail")
        self.assertIn("missing clips ['Walk']", got["detail"])
        d = alien_dump()
        d["skeletons"][0]["bones"].remove("LeftHand")
        self.assertIn("missing bones ['LeftHand']", alien(d)["pack_floor"]["detail"])

    def test_an_unknown_profile_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            alien(alien_dump(), profile="dragon")


class LoopModesTest(unittest.TestCase):
    def test_cycles_that_play_once_warn_and_open_cycles_are_named(self) -> None:
        d = dump()
        d["players"][0]["animations"]["CharacterArmature|Walk"]["loop_mode"] = 0
        e = {**expect(), "seams": {"CharacterArmature|Idle": {"position_mm": 90.0, "rotation_deg": 12.0}}}
        check = next(c for c in _godot.evaluate(d, e, CONTRACT, []) if c["check"] == "loop_modes")
        self.assertEqual(check["status"], "warn")
        self.assertIn("1 of 2 cycles import as loop_mode NONE (Walk)", check["detail"])
        self.assertIn("one frame longer than their keys: Idle", check["detail"])


class RefusalTest(unittest.TestCase):
    def test_a_missing_glb_is_refused(self) -> None:
        code, out = fx.run_cli("godot-check", "no/such.glb")
        self.assertEqual(code, 1)
        self.assertIn("no GLB no/such.glb", out)


class GodotHelpersTest(unittest.TestCase):
    def test_noteworthy_lines_keep_where_they_happened(self) -> None:
        output = "\x1b[1;31mERROR:\x1b[0m bad thing\n   at: f (x.cpp:1)\nplain\nWARNING: odd\n[ 50% ] import\n"
        self.assertEqual(_godot.noteworthy(output), ["ERROR: bad thing at: f (x.cpp:1)", "WARNING: odd"])

    def test_the_import_file_sets_only_our_options(self) -> None:
        text = _godot.import_file({**_godot.IMPORT_PARAMS, "nodes/root_name": "x"})
        self.assertIn('importer="scene"', text)
        self.assertIn("animation/fps=24", text)
        self.assertIn('nodes/root_name="x"', text)
        self.assertTrue(text.endswith("_subresources={}\n"))

    def test_import_lines_go_to_the_file_they_name(self) -> None:
        a, b = "res://import/m1_rex.glb", "res://import/m1_rex_humanoid.glb"
        lines = [f"ERROR: bad mesh in {b}", f"WARNING: odd key in {a}", "ERROR: says nothing about where"]
        self.assertEqual(_godot.lines_for(lines, a, [a, b]), [lines[1], lines[2]])
        self.assertEqual(_godot.lines_for(lines, b, [a, b]), [lines[0], lines[2]])

    def test_every_import_turns_the_animation_optimizer_off(self) -> None:
        self.assertEqual(_godot.subresources(), '{\n"nodes": {\n"PATH:AnimationPlayer": {\n"optimizer/enabled": false\n}\n}\n}')
        text = _godot.subresources({"PATH:x": {"a": _godot.Resource("res://y.tres"), "n": 1}})
        self.assertIn('"PATH:x": {\n"a": Resource("res://y.tres"),\n"n": 1\n}', text)
        self.assertIn('"optimizer/enabled": false', text)


class HumanoidMapTest(unittest.TestCase):
    def test_the_bone_map_covers_the_profile_and_the_rig(self) -> None:
        profile = json.loads((fx.common.ROOT / "contract" / "humanoid.json").read_text(encoding="utf-8"))
        names = {b["name"] for b in profile["bones"]}
        self.assertEqual(set(_humanoid.BONE_MAP) | set(_humanoid.PROFILE_ONLY), names)
        self.assertEqual(len(_humanoid.BONE_MAP), 51)
        self.assertEqual(len(set(_humanoid.BONE_MAP.values())), 51)  # no rig bone used twice
        self.assertEqual(_humanoid.BONE_MAP["LeftIndexProximal"], "Index2.L")  # Index1 is the metacarpal
        self.assertEqual(_humanoid.BONE_MAP["RightLittleDistal"], "Pinky4.R")

    def test_a_contract_named_rig_maps_to_itself(self) -> None:
        rig = ["Root", "Hips", "Spine", "Chest", "UpperChest", "Neck", "Head", "LeftUpperLeg", "LeftLittleProximal"]
        mapping = _humanoid.mapping_for(rig)
        self.assertEqual(mapping["Chest"], "Chest")
        self.assertEqual(mapping["UpperChest"], "UpperChest")
        self.assertEqual(mapping["LeftLittleProximal"], "LeftLittleProximal")
        self.assertNotIn("LeftEye", mapping)  # only the profile bones the rig has
        self.assertEqual(_humanoid.mapping_for(["Hips", "Abdomen", "Torso", "Chest"]), _humanoid.BONE_MAP)

    def test_the_bone_map_resource_text(self) -> None:
        text = _humanoid.bone_map_tres({"Hips": "Hips", "Spine": "Abdomen"})
        self.assertIn('[gd_resource type="BoneMap" load_steps=2 format=3]', text)
        self.assertIn('profile = SubResource("SkeletonProfileHumanoid_um")', text)
        self.assertIn('bone_map/Spine = &"Abdomen"', text)
        self.assertIn('"PATH:x_rig/Skeleton3D": {\n"retarget/bone_map": Resource("res://import/um_humanoid_bone_map.tres")',
                      _godot.subresources(_humanoid.nodes("x_rig/Skeleton3D")))

    def test_pose_deviation(self) -> None:
        plain = {"poses": {"A": {"0.0": {"Wrist.L": [0, 0, 0], "Body": [0, 0, 0]}}}}
        other = {"poses": {"A": {"0.0": {"LeftHand": [0, 0.003, 0.004]}}}}
        dev = _humanoid.pose_deviation(plain, other, {"Wrist.L": "LeftHand"})
        self.assertEqual((dev["max_mm"], dev["joints_compared"]), (5.0, 1))


@unittest.skipUnless(fx.CAN_EXPORT and fx.HAVE_GODOT, fx.SKIP_EXPORT + " and Godot (GODOT_BIN)")
class GodotCheckTest(unittest.TestCase):
    def test_the_exported_characters_pass_in_godot(self) -> None:
        code, out = fx.exported()
        self.assertEqual(code, 0, out)
        code, out = fx.run_cli("godot-check", *(str(fx.glb(c)) for c in fx.IDS), "--out", str(fx.OUT / "godot"))
        self.assertEqual(code, 0, out)
        for cid in fx.IDS:
            with self.subTest(character=cid):
                report = json.loads((fx.OUT / "godot" / cid / "report.json").read_text(encoding="utf-8"))
                self.assertTrue(report["passed"])
                self.assertTrue(report["godot"].startswith("4.7.2-stable"))
                got = {c["check"]: c["status"] for c in report["checks"]}
                self.assertEqual(got["tracks_resolve"], "pass")
                self.assertEqual(len(report["animations"]), 24)
                self.assertEqual(len(report["parts"]), 8)



if __name__ == "__main__":
    unittest.main()
