"""The glTF export (docs/godot.md): the fixed options, the checks of an exported GLB against what Blender exported, the
validator's report; and, with Blender, the validator and the packs, a real export of a man and a woman."""

from __future__ import annotations

import copy
import json
import sys
import unittest

from runner import common
from runner.commands import _export

from . import _export_fixture as fx

sys.path.insert(0, str(common.ROOT / "tools" / "blender"))
import export_glb  # noqa: E402  (pure at import: bpy only inside main())

BONES = ["Root", "Hips", "Head"]
ACTIONS = {"CharacterArmature|Idle": [0, 40], "CharacterArmature|Wave": [0, 24]}


def info() -> dict:
    return {"armature": "x_rig", "bones": list(BONES), "parts": {"x_head": {}, "x_top": {}}, "actions": dict(ACTIONS), "fps": 24}


def summary() -> dict:
    return {
        "roots": ["x_rig"],
        "meshes": {"x_head": 0, "x_top": 0},
        "skins": [["Hips", "Root", "Head"]],  # the exporter orders joints by hierarchy
        "animations": {"CharacterArmature|Idle": {"duration_s": 40 / 24, "channels": 9, "nodes": 3},
                       "CharacterArmature|Wave": {"duration_s": 1.0, "channels": 9, "nodes": 3}},
        "animation_names": list(ACTIONS),
        "materials": ["skin"],
        "cameras": 0, "lights": 0, "images": 0, "extensions": [],
    }


class OptionsTest(unittest.TestCase):
    def test_the_options_the_export_depends_on(self) -> None:
        o = export_glb.EXPORT_OPTIONS
        self.assertEqual(o["export_format"], "GLB")
        self.assertTrue(o["export_yup"] and o["export_skins"] and o["export_animations"])
        self.assertEqual(o["export_animation_mode"], "ACTIONS")
        self.assertFalse(o["export_apply"])  # applying the Armature modifier would bake one pose into the meshes
        self.assertFalse(o["export_def_bones"])  # every bone of the rig, so every action's tracks have a bone
        self.assertEqual(o["export_influence_nb"], 4)
        self.assertFalse(o["export_cameras"] or o["export_lights"] or o["export_morph"])
        self.assertEqual((o["export_image_format"], o["export_vertex_color"]), ("NONE", "NONE"))
        self.assertFalse(o["export_draco_mesh_compression_enable"])  # Godot cannot read Draco

    def test_gltf_axes(self) -> None:
        self.assertEqual(export_glb.gltf_axes((1.0, -2.0, 3.0)), [1.0, 3.0, 2.0])  # Blender front -Y is glTF +Z


class CheckTest(unittest.TestCase):
    def test_a_good_export(self) -> None:
        self.assertEqual(_export.check(info(), summary()), [])

    def test_each_problem_is_named(self) -> None:
        cases = {
            "2 skins, not 1": lambda s: s["skins"].append(["Root"]),
            "differ from the armature's 3 bones": lambda s: s["skins"][0].remove("Head"),
            "mesh nodes without a skin: x_top": lambda s: s["meshes"].update(x_top=None),
            "mesh nodes ['x_head', 'x_top', 'x_x'], parts": lambda s: s["meshes"].update(x_x=0),
            "not just the armature": lambda s: s["roots"].append("Camera"),
            "were not exported": lambda s: s["animation_names"].remove("CharacterArmature|Wave"),
            "CharacterArmature|Wave: 1.5000 s long": lambda s: s["animations"]["CharacterArmature|Wave"].update(duration_s=1.5),
            "animates 2 of the 3 bones": lambda s: s["animations"]["CharacterArmature|Idle"].update(nodes=2),
            "1 cameras": lambda s: s.update(cameras=1),
            "two animations share a name": lambda s: s["animation_names"].append("CharacterArmature|Idle"),
        }
        for expected, mutate in cases.items():
            with self.subTest(expected):
                s = copy.deepcopy(summary())
                mutate(s)
                problems = _export.check(info(), s)
                self.assertTrue(any(expected in p for p in problems), problems)

    def test_summarize_reads_names_and_durations(self) -> None:
        gltf = {
            "scene": 0, "scenes": [{"nodes": [2]}],
            "nodes": [{"name": "Root"}, {"name": "x_head", "mesh": 0, "skin": 0}, {"name": "x_rig", "children": [0, 1]}],
            "skins": [{"joints": [0]}],
            "accessors": [{"max": [1.25]}, {}],
            "animations": [{"name": "CharacterArmature|Run", "samplers": [{"input": 0, "output": 1}],
                            "channels": [{"sampler": 0, "target": {"node": 0, "path": "rotation"}}]}],
        }
        s = _export.summarize(gltf)
        self.assertEqual(s["roots"], ["x_rig"])
        self.assertEqual(s["meshes"], {"x_head": 0})
        self.assertEqual(s["skins"], [["Root"]])
        self.assertEqual(s["animations"]["CharacterArmature|Run"], {"duration_s": 1.25, "channels": 1, "nodes": 1})

    def test_validator_messages_are_grouped_by_code(self) -> None:
        report = {"issues": {"messages": [
            {"code": "NODE_SKINNED_MESH_NON_ROOT", "message": "m", "severity": 1, "pointer": f"/nodes/{i}"} for i in range(6)
        ] + [{"code": "ACCESSOR_INVALID", "message": "bad", "severity": 0, "pointer": "/accessors/1"}]}}
        found = _export.issues(report)
        self.assertEqual(found["warning"], ["NODE_SKINNED_MESH_NON_ROOT x6: m (/nodes/0, /nodes/1, /nodes/2, /nodes/3, ...)"])
        self.assertEqual(found["error"], ["ACCESSOR_INVALID x1: bad (/accessors/1)"])


class RefusalTest(unittest.TestCase):
    def test_a_missing_or_wrong_file_is_refused(self) -> None:
        code, out = fx.run_cli("export", "no/such.blend")
        self.assertEqual(code, 1)
        self.assertIn("no saved character file no/such.blend", out)


@unittest.skipUnless(fx.CAN_EXPORT, fx.SKIP_EXPORT)
class ExportInBlenderTest(unittest.TestCase):
    code: int
    out: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.code, cls.out = fx.exported()

    def test_the_command_passes(self) -> None:
        self.assertEqual(self.code, 0, self.out)
        self.assertEqual(self.out.count("glTF-Validator 2.0.0-dev.3.10: 0 errors"), len(fx.IDS), self.out)

    def test_each_glb_holds_the_character(self) -> None:
        for cid in fx.IDS:
            with self.subTest(character=cid):
                path = fx.glb(cid)
                s = _export.summarize(_export.glb_json(path))
                self.assertEqual(len(s["skins"]), 1)
                self.assertEqual(len(s["skins"][0]), 62)
                self.assertEqual(set(s["meshes"]), {f"{cid}_{p}" for p in
                                                    ("head", "hair", "top", "bottom", "shoes", "eyes", "brows", "mouth")})
                self.assertEqual(len(s["animation_names"]), 24)
                self.assertTrue(all(n.startswith("CharacterArmature|") for n in s["animation_names"]))
                self.assertEqual((s["cameras"], s["lights"], s["images"]), (0, 0, 0))
                report = json.loads((path.parent / "report.json").read_text(encoding="utf-8"))
                self.assertEqual(report["issues"]["numErrors"], 0)
                info = json.loads((path.parent / f"{cid}.export.json").read_text(encoding="utf-8"))
                self.assertLess(abs(info["feet_y_m"]), 0.005)
                self.assertEqual(info["options"], export_glb.EXPORT_OPTIONS)


if __name__ == "__main__":
    unittest.main()
